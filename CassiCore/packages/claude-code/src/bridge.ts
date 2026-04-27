/**
 * CassiCore Admin API bridge client.
 *
 * Communicates with the CassiCore daemon via Unix socket (primary)
 * or TCP fallback (port 7433). Adapted from the OpenCode ContextBridge.
 */

import http from "node:http";
import os from "node:os";
import path from "node:path";

// ── Configuration ───────────────────────────────────────────────────────────

const SOCKET_PATH = path.join(os.homedir(), ".cassicore", "admin.sock");
const TCP_BASE = "http://localhost:7433";
const DEFAULT_TIMEOUT = 1000;
const LONG_TIMEOUT = 60_000;

// ── Transport ───────────────────────────────────────────────────────────────

function request(
  method: string,
  pathname: string,
  body?: unknown,
  ms = DEFAULT_TIMEOUT,
  socketPath?: string,
): Promise<any> {
  return new Promise((resolve) => {
    const payload = body ? JSON.stringify(body) : undefined;
    const headers: Record<string, string> = payload
      ? { "content-type": "application/json", "content-length": String(Buffer.byteLength(payload)) }
      : {};

    const opts: http.RequestOptions = socketPath
      ? { socketPath, path: pathname, method, headers, timeout: ms }
      : (() => {
          const url = new URL(pathname, TCP_BASE);
          return {
            hostname: url.hostname,
            port: url.port || 7433,
            path: url.pathname + url.search,
            method,
            headers,
            timeout: ms,
          };
        })();

    const req = http.request(opts, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString()));
        } catch {
          resolve(null);
        }
      });
    });

    req.on("error", () => resolve(null));
    req.on("timeout", () => { req.destroy(); resolve(null); });

    if (payload) req.write(payload);
    req.end();
  });
}

async function send(method: string, pathname: string, body?: unknown, ms?: number): Promise<any> {
  const timeout = ms ?? DEFAULT_TIMEOUT;
  // Try Unix socket first, fall back to TCP
  const result = await request(method, pathname, body, timeout, SOCKET_PATH);
  if (result !== null && !result?.error) return result;
  return request(method, pathname, body, timeout);
}

// ── Public API ──────────────────────────────────────────────────────────────

export async function available(): Promise<boolean> {
  const res = await send("GET", "/health");
  return res !== null && res.status === "ok";
}

// ── Context ─────────────────────────────────────────────────────────────────

export interface InjectData {
  updatedAt: number;
  insight: string | null;
  learnings: Array<{ clusterLabel: string; summary: string; occurrences?: number }>;
  sessions: Record<string, { items: Array<{ source: string; content: string; relevance: number }>; previousContext?: string }>;
  focusStates?: Record<string, any>;
  sessionHealth?: Record<string, any>;
  anomalies?: Array<{ id: string; type: string; summary: string; severity: string; detectedAt: number }>;
  teams?: { active: any[]; pendingCheckpoints: any[]; recentlyCompleted?: any[] };
  dialecticLatest?: Record<string, any>;
  crossSessionPatterns?: Array<{ category: string; description: string; confidence: number; sessionCount: number }>;
  delegationRequests?: any[];
  siblingLearnings?: Record<string, any>;
  handoffSuggestions?: Record<string, any>;
}

let contextCache: { data: InjectData | null; ts: number } = { data: null, ts: 0 };
const CONTEXT_CACHE_TTL = 2000;

export async function fetchContext(): Promise<InjectData | null> {
  const now = Date.now();
  if (now - contextCache.ts < CONTEXT_CACHE_TTL && contextCache.data) return contextCache.data;
  const data = await send("GET", "/context") as InjectData | null;
  if (data) contextCache = { data, ts: now };
  return data ?? contextCache.data;
}

// ── Global Workspace Context ───────────────────────────────────────────────

let workspaceCache: { data: any; ts: number } = { data: null, ts: 0 };
const WORKSPACE_CACHE_TTL = 2000;

export async function workspaceContext(sessionId: string): Promise<{ parts: Array<{ content: string; source: string }>; attentionSchema: any; threshold: number } | null> {
  const now = Date.now();
  if (now - workspaceCache.ts < WORKSPACE_CACHE_TTL && workspaceCache.data) return workspaceCache.data;
  const data = await send("GET", `/intelligence/workspace/context?sessionId=${encodeURIComponent(sessionId)}`);
  if (data) workspaceCache = { data, ts: now };
  return data ?? workspaceCache.data;
}

export async function workspaceEnrich(query: string, sessionId: string): Promise<{ submitted: number } | null> {
  return send("POST", "/intelligence/workspace/enrich", { query, sessionId });
}

export async function inject(sessionId: string): Promise<string[]> {
  const res = await send("GET", `/context/inject/${sessionId}`);
  if (!res || !Array.isArray(res.parts)) return [];
  return res.parts.filter((p: any) => p.content && p.charCount > 0).map((p: any) => p.content);
}

export function index(sessionId: string, messages: any[]): void {
  send("POST", "/context/index", { sessionId, messages }).catch(() => {});
}

// Curation via Thalamus module

export async function curate(
  sessionId: string,
  messages: any[],
  config?: Record<string, unknown>,
): Promise<{ messages: any[]; meta: any } | null> {
  return send("POST", "/context/curate", { sessionId, messages, config }, LONG_TIMEOUT);
}

// ── Memory ──────────────────────────────────────────────────────────────────

export async function memorySearch(query: string, limit = 5): Promise<any[]> {
  const res = await send("POST", "/memory/search", { query, limit });
  return res?.results ?? [];
}

export async function memoryStore(content: string, tags?: string[], type = "insight"): Promise<string> {
  const res = await send("POST", "/memory/store", { type, content, metadata: { tags: tags ?? [], source: "claude-code" } });
  return res?.id ?? "";
}

export async function kvGet(key: string): Promise<any> {
  return send("GET", `/memory/kv/${encodeURIComponent(key)}`);
}

export function kvSet(key: string, value: unknown): void {
  send("POST", "/memory/kv", { key, value }).catch(() => {});
}

// ── Blackboard ──────────────────────────────────────────────────────────────

export async function blackboardRead(name: string, channel?: string): Promise<any> {
  const qs = channel ? `?channel=${encodeURIComponent(channel)}` : "";
  return send("GET", `/blackboard/${encodeURIComponent(name)}${qs}`);
}

export async function blackboardPost(
  name: string,
  content: string,
  channel: string,
  author = "claude-code",
  tags: string[] = [],
  priority = "medium",
): Promise<void> {
  await send("POST", `/blackboard/${encodeURIComponent(name)}/post`, {
    content, channel, author, tags, priority,
  });
}

export async function blackboardSearch(pattern: string): Promise<any> {
  return send("GET", `/blackboard/search?pattern=${encodeURIComponent(pattern)}`);
}

// ── Agent (Constellation / Helix / Flux) ────────────────────────────────────

export async function agentConstellation(action: string, params: Record<string, unknown>): Promise<any> {
  if (action === "project") {
    return send("POST", "/agent/constellation/project", params, LONG_TIMEOUT);
  }
  if (action === "watch") {
    return send("GET", `/agent/constellation/watch/${params.sessionId}`, undefined, LONG_TIMEOUT);
  }
  if (action === "steer") {
    return send("POST", `/agent/constellation/steer/${params.sessionId}`, { message: params.message }, LONG_TIMEOUT);
  }
  return send("POST", `/agent/constellation/${action}`, params, LONG_TIMEOUT);
}

// ── Intelligence ────────────────────────────────────────────────────────────

export async function intelligence(action: string, params?: Record<string, unknown>): Promise<any> {
  if (action === "activity") return send("GET", "/intelligence/activity");
  if (action === "schema") return send("GET", `/intelligence/schema${params?.path ? `?path=${params.path}` : ""}`);
  if (action === "trust") return send("GET", "/intelligence/trust");
  if (action === "budget") return send("GET", "/intelligence/budget");
  if (action === "effectiveness") return send("GET", "/intelligence/effectiveness");
  return send("GET", `/intelligence/${action}`);
}

// ── Session ─────────────────────────────────────────────────────────────────

export async function sessionList(): Promise<any[]> {
  const res = await send("GET", "/session/list");
  return res?.sessions ?? [];
}

// ── Event Ingestion ─────────────────────────────────────────────────────────

export async function ingestEvents(sessionId: string, events: Record<string, unknown>[]): Promise<void> {
  await send("POST", "/events/ingest", { sessionId, events }).catch(() => {});
}

/**
 * Emit a canonical `turn:start` runtime event. Cognitive modules (Reverie,
 * memory, thinker) subscribe to this on the daemon bus; without it, nothing
 * downstream wakes up for a Claude Code turn.
 */
export async function emitTurnStart(sessionId: string, message: string): Promise<void> {
  await send("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "turn:start",
      sessionId,
      message,
      source: "claude-code",
      timestamp: Date.now(),
    }],
  }).catch(() => {});
}

/**
 * Emit a canonical `turn:end` runtime event with the assistant response so
 * Reverie's onTurnEnd hook fires and triggers ambient curation.
 */
export async function emitTurnEnd(sessionId: string, response: string, durationMs: number): Promise<void> {
  await send("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "turn:end",
      sessionId,
      response,
      durationMs,
      source: "claude-code",
      timestamp: Date.now(),
    }],
  }).catch(() => {});
}

/**
 * Emit a canonical `tool:round-complete` event so Reverie's sliding tool log,
 * loop detection, and Reflex hooks fire on every Claude Code tool round.
 */
export async function emitToolRound(
  sessionId: string,
  round: number,
  toolCalls: Array<{ name: string; id: string }>,
  results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>,
): Promise<void> {
  await send("POST", "/events/ingest", {
    sessionId,
    events: [{
      type: "tool:round-complete",
      sessionId,
      round,
      toolCalls,
      results,
      source: "claude-code",
      timestamp: Date.now(),
    }],
  }).catch(() => {});
}

/** Ping Reverie directly to schedule a curation pass. */
export async function reveriePing(sessionId: string, reason: string): Promise<void> {
  await send("POST", `/reverie/ping?sessionId=${encodeURIComponent(sessionId)}&reason=${encodeURIComponent(reason)}`).catch(() => {});
}

/** Post a perception signal to the Cortex (working memory). */
export async function cortexSignal(
  sessionId: string,
  type: string,
  region: string,
  content: string,
  tags: string[] = [],
): Promise<void> {
  await send("POST", "/cortex/signal", {
    sessionId,
    type,
    region,
    content,
    tags,
    author: "claude-code",
    salience: 0.5,
  }).catch(() => {});
}

// ── Chunk Storage ───────────────────────────────────────────────────────────

export async function storeChunks(sessionId: string, chunks: any[]): Promise<any> {
  return send("POST", "/context/chunks/store", { sessionId, chunks });
}

export async function expandChunks(sessionId: string, chunkIds: string[]): Promise<any[]> {
  const res = await send("POST", "/context/chunks/retrieve", { sessionId, chunkIds });
  return res?.chunks ?? [];
}

// ── Cognitive Status ────────────────────────────────────────────────────────

export async function cognitiveStatus(): Promise<any> {
  const [activity, teams, lumen] = await Promise.all([
    send("GET", "/intelligence/activity", undefined, 2000),
    send("GET", "/teams", undefined, 2000),
    send("GET", "/lumen/jobs", undefined, 2000),
  ]);
  if (!activity) return null;
  return {
    modules: activity.modules ?? [],
    thinker: activity.thinker ?? null,
    dialectic: activity.dialectic ?? null,
    memory: activity.memory ?? null,
    teams: teams?.teams ?? null,
    lumen: lumen?.jobs ?? null,
  };
}

// ── Aurora ──────────────────────────────────────────────────────────────────

export async function auroraState(): Promise<any> {
  return send("GET", "/intelligence/aurora", undefined, 2000);
}

export async function auroraSerialized(): Promise<string | null> {
  const res = await send("GET", "/intelligence/aurora/serialize", undefined, 2000);
  return res?.context ?? null;
}

export async function auroraObserve(text: string): Promise<any> {
  return send("POST", "/intelligence/aurora/observe", { text }, 2000);
}

// ── Compaction ───────────────────────────────────────────────────────────────

export async function compact(sessionId: string, messages: any[]): Promise<any> {
  return send("POST", `/context/compact/${sessionId}`, { messages }, LONG_TIMEOUT);
}
