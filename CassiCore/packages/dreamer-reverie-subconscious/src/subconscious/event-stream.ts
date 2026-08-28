/**
 * EventStream — Universal system event tap and ring buffer.
 *
 * The stream of consciousness: every event that flows through the EventBus
 * passes through here, giving the Subconscious complete system awareness.
 *
 * Architecture:
 * - Connects to the EventBus via onAll() — zero coupling to specific event types
 * - Stores events in a fixed-size ring buffer (configurable, default 10,000)
 * - Maintains a per-session index for fast session-scoped queries
 * - Tracks event rates and type distributions
 * - Produces StreamSummary snapshots for LLM consumption
 */

import type { EventStreamConfig, EventStreamEntry, StreamSummary } from "./types.js";
import type { RuntimeEvent, EventType, Unsubscribe } from "@cassicore/foundation";
import type { IEventBus, ILogger } from "@cassicore/foundation";

export class EventStream {
  private readonly logger: ILogger;
  private readonly config: Required<EventStreamConfig>;

  // Fixed-size ring buffer — never grows, never allocates after construction
  private readonly buffer: (EventStreamEntry | undefined)[];
  private writeHead = 0;
  private full = false;

  // Per-session event index: sessionId → array of buffer indices
  private readonly sessionIndex = new Map<string, number[]>();

  // Running type counts
  private readonly typeCounts = new Map<string, number>();

  // Rate calculation: sliding window of timestamps
  private readonly rateSamples: number[] = [];
  private static readonly RATE_SAMPLE_LIMIT = 1000;

  private unsub?: Unsubscribe;

  constructor(logger: ILogger, config?: Partial<EventStreamConfig>) {
    this.logger = logger.child?.("event-stream") ?? logger;
    this.config = {
      maxBufferSize: config?.maxBufferSize ?? 10_000,
      sessionBufferSize: config?.sessionBufferSize ?? 2_000,
    };
    // Pre-allocate buffer slots — avoids GC pressure during steady-state operation
    this.buffer = new Array<EventStreamEntry | undefined>(this.config.maxBufferSize).fill(undefined);
  }


  /**
   * Connect to an EventBus via onAll(). After this call the stream
   * will observe every event emitted on the bus.
   */
  connect(bus: IEventBus): void {
    this.unsub?.();
    this.unsub = bus.onAll((event) => this.ingest(event));
    this.logger.debug("EventStream connected — observing all events");
  }

  /** Disconnect from the EventBus. */
  disconnect(): void {
    this.unsub?.();
    this.unsub = undefined;
    this.logger.debug("EventStream disconnected");
  }


  private ingest(event: RuntimeEvent): void {
    // Skip high-frequency chunk events — they flood the ring buffer and
    // dominate the LLM observer summary.  request_start / request_end
    // already capture the provider lifecycle.
    if (event.type === 'provider:request_chunk') return

    const entry: EventStreamEntry = { event, receivedAt: Date.now() };
    const idx = this.writeHead;

    this.buffer[idx] = entry;
    this.writeHead = (idx + 1) % this.config.maxBufferSize;
    if (this.writeHead === 0) this.full = true;

    // Update type counts
    const prev = this.typeCounts.get(event.type) ?? 0;
    this.typeCounts.set(event.type, prev + 1);

    // Rate sampling
    this.rateSamples.push(entry.receivedAt);
    if (this.rateSamples.length > EventStream.RATE_SAMPLE_LIMIT) {
      this.rateSamples.shift();
    }

    // Session index — any event with a sessionId property gets indexed
    const sessionId = (event as Record<string, unknown>).sessionId as string | undefined;
    if (sessionId) {
      let indices = this.sessionIndex.get(sessionId);
      if (!indices) {
        indices = [];
        this.sessionIndex.set(sessionId, indices);
      }
      indices.push(idx);
      // Trim to configured per-session limit
      if (indices.length > this.config.sessionBufferSize) {
        indices.shift();
      }
    }
  }


  /**
   * Get all buffered events in chronological order (oldest → newest).
   */
  getAll(): EventStreamEntry[] {
    if (!this.full) {
      // Buffer hasn't wrapped yet — take only the filled portion
      return (this.buffer.slice(0, this.writeHead) as EventStreamEntry[]).filter(Boolean);
    }
    // Reorder the ring: [writeHead..end] + [0..writeHead-1]
    const tail = (this.buffer.slice(this.writeHead) as EventStreamEntry[]).filter(Boolean);
    const head = (this.buffer.slice(0, this.writeHead) as EventStreamEntry[]).filter(Boolean);
    return [...tail, ...head];
  }

  /** Get events received at or after `sinceMs` (Unix ms timestamp). */
  getSince(sinceMs: number): EventStreamEntry[] {
    // Walk backward from the newest entry — stop at first entry older than sinceMs
    // This is faster than filtering the full ordered array for recent windows.
    const all = this.getAll();
    let lo = 0;
    let hi = all.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if ((all[mid]?.receivedAt ?? 0) < sinceMs) lo = mid + 1;
      else hi = mid;
    }
    return all.slice(lo);
  }

  /** Get the most recent `count` events. */
  getRecent(count: number): EventStreamEntry[] {
    const all = this.getAll();
    return all.slice(-count);
  }

  /** Get events matching one or more event types. */
  getByType(...types: EventType[]): EventStreamEntry[] {
    const typeSet = new Set<string>(types);
    return this.getAll().filter((e) => typeSet.has(e.event.type));
  }

  /** Get all buffered events for a specific session. */
  getBySession(sessionId: string): EventStreamEntry[] {
    const indices = this.sessionIndex.get(sessionId);
    if (!indices || indices.length === 0) return [];
    return indices
      .map((i) => this.buffer[i])
      .filter((e): e is EventStreamEntry => e !== undefined)
      .sort((a, b) => a.receivedAt - b.receivedAt);
  }


  /**
   * Observed events per second over the last `windowSecs` seconds.
   * Uses the sampled timestamp array — accurate up to the last 1000 events.
   */
  getRate(windowSecs = 60): number {
    if (windowSecs <= 0) return 0;
    const cutoff = Date.now() - windowSecs * 1000;
    const recent = this.rateSamples.filter((t) => t >= cutoff);
    return recent.length / windowSecs;
  }

  /** Event type distribution for the last `lastN` events. */
  getTypeDistribution(lastN = 1000): Record<string, number> {
    const recent = this.getRecent(lastN);
    const dist: Record<string, number> = {};
    for (const e of recent) {
      dist[e.event.type] = (dist[e.event.type] ?? 0) + 1;
    }
    return dist;
  }

  /** Cumulative event counts by type since the stream started. */
  getTypeCounts(): ReadonlyMap<string, number> {
    return this.typeCounts;
  }

  /** Total events ingested (sum of all type counts). */
  get totalCount(): number {
    let total = 0;
    for (const c of this.typeCounts.values()) total += c;
    return total;
  }

  /** Sessions currently in the session index. */
  get activeSessions(): string[] {
    return Array.from(this.sessionIndex.keys());
  }


  /** Remove session from the index when it ends (frees memory). */
  cleanupSession(sessionId: string): void {
    this.sessionIndex.delete(sessionId);
  }

  /**
   * Remove all session index entries whose IDs are not in the provided valid set.
   * Prevents unbounded growth of the sessionIndex when session:ended events are
   * missed or when sessions are pruned at the daemon level without event dispatch.
   *
   * @returns Number of stale session entries removed
   */
  pruneStaleSessions(validSessionIds: Set<string>): number {
    let removed = 0;
    for (const sessionId of this.sessionIndex.keys()) {
      if (!validSessionIds.has(sessionId)) {
        this.sessionIndex.delete(sessionId);
        removed++;
      }
    }
    if (removed > 0) {
      this.logger.debug("EventStream pruned stale session indices", {
        removed,
        remaining: this.sessionIndex.size,
      });
    }
    return removed;
  }


  /**
   * Summarize the event stream over the last `windowMs` milliseconds.
   * Used by the LLMObserver to build its observer prompt.
   */
  summarize(windowMs = 60_000): StreamSummary {
    const recent = this.getSince(Date.now() - windowMs);

    const typeDist: Record<string, number> = {};
    const sourceDist: Record<string, number> = {};
    const sequences: string[] = [];
    let prevType: string | undefined;

    for (const entry of recent) {
      const t = entry.event.type;
      typeDist[t] = (typeDist[t] ?? 0) + 1;
      // Record type transitions — consecutive same-type events collapse to one entry
      if (t !== prevType) {
        sequences.push(t);
        prevType = t;
      }
      // Extract source attribution from provider events
      if (t.startsWith('provider:')) {
        const src = (entry.event as Record<string, unknown>).source
        if (typeof src === 'string') {
          sourceDist[src] = (sourceDist[src] ?? 0) + 1
        }
      }
    }

    // Top 10 event types by count
    const topTypes = Object.entries(typeDist)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([type, count]) => ({ type, count }));

    // Provider source breakdown (only if provider events exist)
    const providerSources = Object.keys(sourceDist).length > 0
      ? Object.entries(sourceDist)
          .sort((a, b) => b[1] - a[1])
          .map(([source, count]) => ({ source, count }))
      : undefined

    return {
      windowMs,
      totalEvents: recent.length,
      eventsPerSecond: windowMs > 0 ? recent.length / (windowMs / 1000) : 0,
      topTypes,
      recentSequence: sequences.slice(-50),
      activeSessions: this.sessionIndex.size,
      providerSources,
    };
  }
}
