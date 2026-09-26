import * as net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { StandardMindFieldEncoder } from '../field-encoder/index.js';
import type { MindFieldEncoder } from '../field-encoder/types.js';
import type { ILogger } from '@cassicore/foundation';

/**
 * Shadow-bridge drainer: pulls pending deposits out of the MnemicField
 * encoder queue and pushes them to the field engine's loopback TCP bridge
 * (line-delimited JSON, one request per line, one reply per request).
 *
 * Stage-1 semantics: the bridge is a SHADOW. Deposits are fire-and-forget
 * and never affect brain behavior; a field failure (engine down, socket
 * error, timeout) is swallowed and the brain keeps running bit-identical.
 * The parity gate holds by construction: with the feature disabled or the
 * engine unreachable, deposits simply stay queued and nothing else in the
 * brain observes the field. When deposits are dropped (engine down), the
 * drainer logs one bounded warning, never a throw.
 *
 * The drain cadence is a managed interval, mirroring the plugin heartbeat.
 * The engine applies queued deposits on its next field step.
 *
 * Wire-up in daemon boot: new FieldShadowBridge(standard, callbackQueue,
 * { enabled: config }, logger).start(); the queue callback pulls from
 * field.drainFieldDeposits().
 */

export interface DrainConfig {
  host?: string;
  port?: number;
  /** ms between drain attempts. */
  intervalMs?: number;
  /** ms socket connect timeout. */
  timeoutMs?: number;
  /** Disable the bridge entirely (parity mode). */
  enabled: boolean;
  /**
   * Stage-4 loop A/B: when set, `drain()` also appends queued retrieval
   * positions (from `queue.retrievals()`) as JSONL lines to this file, in
   * addition to its normal deposit behavior. When UNSET (default) the
   * retrieval flush is disabled and `drain()` is bit-identical to before.
   */
  retrievalLogPath?: string;
}

/** A queued retrieval-position record: `t` ISO timestamp + brain [-1,1]³ hits. */
export interface RetrievalPositionRecord {
  t: string;
  hits: Array<{ x: number; y: number; z: number }>;
}

export interface DrainQueue {
  dequeue(): number[][];
  /** Optional Stage-4 retrieval-position drain. Absent → no retrieval flush. */
  retrievals?(): RetrievalPositionRecord[];
}

export interface ShadowBridgeStatus {
  enabled: boolean;
  connected: boolean;
  depositsSent: number;
  engineStep: number | null;
}

/** A single top-attractor field cell as returned by the engine `project` command. */
export interface ProjectionCell {
  i: number;
  gx: number;
  gy: number;
  gz: number;
  x: number;
  y: number;
  z: number;
  ey: number;
  ei: number;
  q: number;
}

/**
 * Parse an engine `project` reply (as produced by `requestObject`) into
 * ProjectionCells, defensively. Coerces every numeric field with Number()/
 * defaults, tolerates missing fields, treats a non-array `cells` as [] and a
 * non-ok reply as []. Engines send cells pre-sorted by q DESC; we re-sort
 * DESC here so callers are order-tolerant (a malformed/unsorted reply cannot
 * mislead positional agreement). Bounded to the first `limit` cells.
 */
export function parseProjectionReply(
  reply: Record<string, unknown> | null,
  limit?: number,
): ProjectionCell[] {
  if (!reply || reply.ok !== true) return [];
  const raw = Array.isArray(reply.cells) ? reply.cells : [];
  const cells: ProjectionCell[] = [];
  for (const c of raw) {
    if (c === null || typeof c !== 'object') continue;
    const o = c as Record<string, unknown>;
    cells.push({
      i: Number(o.i ?? 0) || 0,
      gx: Number(o.gx ?? 0) || 0,
      gy: Number(o.gy ?? 0) || 0,
      gz: Number(o.gz ?? 0) || 0,
      x: Number(o.x ?? 0) || 0,
      y: Number(o.y ?? 0) || 0,
      z: Number(o.z ?? 0) || 0,
      ey: Number(o.ey ?? 0) || 0,
      ei: Number(o.ei ?? 0) || 0,
      q: Number(o.q ?? 0) || 0,
    });
  }
  cells.sort((a, b) => b.q - a.q);
  return limit != null && limit > 0 ? cells.slice(0, limit) : cells;
}

interface PendingSend {
  cmd: Record<string, unknown>;
  resolve: (ok: boolean) => void;
  /** Used by the projection read path: resolves with the full parsed reply object. */
  resolveObj?: (obj: Record<string, unknown> | null) => void;
}

export class FieldShadowBridge {
  private readonly encoder: MindFieldEncoder;
  private readonly queue: DrainQueue;
  private readonly config: DrainConfig;
  private readonly logger: ILogger;
  private timer: ReturnType<typeof setInterval> | null = null;
  private socket: net.Socket | null = null;
  private buf = '';
  private inflight: PendingSend | null = null;
  private waiting: PendingSend[] = [];
  private connected = false;
  private lastEngineStep: number | null = null;
  private droppedLogged = 0;
  private retrievalFlushWarnings = 0;

  constructor(encoder: MindFieldEncoder, queue: DrainQueue, config: DrainConfig, logger: ILogger) {
    this.encoder = encoder;
    this.queue = queue;
    this.config = config;
    this.logger = logger.child ? logger.child('field-shadow-bridge') : logger;
  }

  /** The encoder to attach to the MnemicField (call setFieldEncoder(encoder)). */
  encoderRef(): MindFieldEncoder {
    return this.encoder;
  }

  status(): ShadowBridgeStatus {
    return {
      enabled: this.config.enabled,
      connected: this.connected,
      depositsSent: this.encoder.depositsSent(),
      engineStep: this.lastEngineStep,
    };
  }

  /** Start the background drain loop. Returns false if disabled or already started. */
  start(): boolean {
    if (!this.config.enabled) {
      this.logger.info('Field shadow bridge disabled (parity mode)');
      return false;
    }
    if (this.timer) return true;
    const ms = this.config.intervalMs ?? 2000;
    this.timer = setInterval(() => this.drain().catch(() => { /* never throw */ }), ms);
    void this.drain().catch(() => {});
    this.logger.info('Field shadow bridge started', {
      host: this.config.host ?? '127.0.0.1',
      port: this.config.port ?? 7599,
      everyMs: ms,
    });
    return true;
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.close();
    this.logger.info('Field shadow bridge stopped');
  }

  /** Manual drain (also used by tests). Returns deposits pushed. */
  async drain(): Promise<number> {
    // Stage-4 retrieval telemetry flush runs FIRST, before the enabled/
    // connectivity gate: the measurement must capture retrievals even when
    // the deposit bridge is disabled or the engine is unreachable. When
    // `retrievalLogPath` is unset this is a no-op and drain() is bit-identical.
    this.flushRetrievalPositions();

    if (!this.config.enabled || this.inflight) return 0;
    if (!this.connected && !(await this.connect())) {
      const n = this.queue.dequeue().length;
      if (n > 0 && this.droppedLogged < 3) {
        this.droppedLogged += 1;
        this.logger.warn('Field shadow bridge: engine unreachable, deposits dropped', { dropped: n });
      }
      return 0;
    }
    const deposits = this.queue.dequeue();
    if (deposits.length === 0) {
      await this.request({ cmd: 'ping' });
      return 0;
    }
    let sent = 0;
    for (const d of deposits) {
      const ok = await this.request({
        cmd: 'deposit', x: d[0], y: d[1], z: d[2], cy: d[3], ci: d[4], sigma: d[5],
      });
      if (!ok) break;
      sent += 1;
    }
    if (sent < deposits.length) this.logger.warn('Field shadow bridge: partial deposit', { sent, total: deposits.length });
    if (sent > 0) await this.request({ cmd: 'state' }); // refresh status().engineStep
    return sent;
  }

  /**
   * Read the field's top-attractor cells (projection). Parity by construction:
   * returns [] when the bridge is disabled or the engine is unreachable, and
   * never throws. Reads never write to the engine — projection is measurement
   * only and leaves the field state untouched.
   */
  async readProjection(k = 8): Promise<ProjectionCell[]> {
    if (!this.config.enabled) return [];
    try {
      if (!this.connected && !(await this.connect())) return [];
      const reply = await this.requestObject({ cmd: 'project', k });
      return parseProjectionReply(reply, k);
    } catch {
      return [];
    }
  }

  /**
   * Append queued retrieval-position records to the retrieval log as JSONL
   * lines: `{"t":"<ISO>","retrievals":[{x,y,z}...]}` (the record's own `t`
   * timestamp is reused as the pairing key). FIRE-AND-FORGET by construction:
   * never throws, never blocks the drain. A failed append (bad path, disk,
   * permissions) is swallowed with one bounded warning (max 3). Disabled
   * entirely when `retrievalLogPath` is unset or the queue has no
   * `retrievals()` drainer.
   */
  private flushRetrievalPositions(): void {
    const logPath = this.config.retrievalLogPath;
    if (!logPath) return;
    const drainer = this.queue?.retrievals;
    if (typeof drainer !== 'function') return;
    let records: RetrievalPositionRecord[];
    try {
      records = drainer();
    } catch (err) {
      this.warnRetrievalFlush(`retrieval drain failed`, err);
      return;
    }
    if (records.length === 0) return;
    try {
      fs.mkdirSync(path.dirname(logPath), { recursive: true });
      const lines = records.map((r) => JSON.stringify({ t: r.t, retrievals: r.hits }));
      fs.appendFileSync(logPath, lines.join('\n') + '\n', 'utf8');
    } catch (err) {
      this.warnRetrievalFlush(`retrieval log append failed`, err);
    }
  }

  private warnRetrievalFlush(message: string, err: unknown): void {
    if (this.retrievalFlushWarnings >= 3) return;
    this.retrievalFlushWarnings += 1;
    this.logger.warn(`Field shadow bridge: ${message}`, {
      warnings: this.retrievalFlushWarnings,
      error: String(err),
    });
  }

  private connect(): Promise<boolean> {
    const port = this.config.port ?? 7599;
    const host = this.config.host ?? '127.0.0.1';
    return new Promise((resolve) => {
      const s = net.connect({ port, host });
      const timer = setTimeout(() => {
        s.destroy();
        resolve(false);
      }, this.config.timeoutMs ?? 1500);
      s.on('connect', () => {
        clearTimeout(timer);
        this.socket = s;
        this.connected = true;
        s.on('data', (d) => this.onData(d.toString('utf8')));
        s.on('error', () => this.markOffline());
        s.on('close', () => this.markOffline());
        resolve(true);
      });
      s.on('error', () => {
        clearTimeout(timer);
        s.destroy();
        resolve(false);
      });
    });
  }

  private request(cmd: Record<string, unknown>): Promise<boolean> {
    if (!this.socket || !this.connected) return Promise.resolve(false);
    return new Promise((resolve) => {
      this.enqueue({ cmd, resolve });
    });
  }

  /** Like `request` but resolves with the full parsed reply object (or null),
   *  keeping the boolean `request` behavior bit-identical for the drainer. */
  private requestObject(cmd: Record<string, unknown>): Promise<Record<string, unknown> | null> {
    if (!this.socket || !this.connected) return Promise.resolve(null);
    return new Promise((resolve) => {
      this.enqueue({ cmd, resolve: () => {}, resolveObj: resolve });
    });
  }

  private enqueue(item: PendingSend): void {
    if (this.inflight) {
      // Engine answers one in-flight request at a time; hold others.
      this.waiting.push(item);
      return;
    }
    this.inflight = item;
    this.socket?.write(JSON.stringify(item.cmd) + '\n');
  }

  private onData(chunk: string): void {
    this.buf += chunk;
    let nl: number;
    while ((nl = this.buf.indexOf('\n')) >= 0) {
      const line = this.buf.slice(0, nl);
      this.buf = this.buf.slice(nl + 1);
      let obj: { ok?: boolean; step?: number };
      try {
        obj = JSON.parse(line);
      } catch {
        continue;
      }
      if (obj && typeof obj.step === 'number') this.lastEngineStep = obj.step;
      const done = this.inflight;
      this.inflight = null;
      if (done) {
        done.resolve(Boolean(obj?.ok));
        done.resolveObj?.(obj ?? null);
      }
      const next = this.waiting.shift();
      if (next && this.socket) {
        this.inflight = next;
        this.socket.write(JSON.stringify(next.cmd) + '\n');
      }
    }
  }

  private markOffline(): void {
    this.connected = false;
    this.lastEngineStep = null;
    try {
      this.socket?.destroy();
    } catch {
      // ignore
    }
    this.socket = null;
    while (this.waiting.length > 0) {
      const w = this.waiting.shift()!;
      w.resolve(false);
      w.resolveObj?.(null);
    }
    if (this.inflight) {
      this.inflight.resolve(false);
      this.inflight.resolveObj?.(null);
      this.inflight = null;
    }
  }

  private close(): void {
    this.markOffline();
  }
}

export { StandardMindFieldEncoder };
export type { MindFieldEncoder };
