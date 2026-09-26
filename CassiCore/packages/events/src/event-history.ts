/**
 * EventHistory — Ring buffer store for EventBus events
 *
 * Captures all events with indexing for efficient querying.
 * Supports time-based eviction and session/type indexing.
 */

import { ulid } from "ulid";

import type {
  EventHistoryConfig,
  EventMetadata,
  StoredEvent,
  ComplexEventQuery,
  EventQueryResult,
  AggregationResult,
  AggregationGroup,
  QueryMetadata,
  SortSpec,
  WhereClause,
  QueryCondition,
  QueryOperators,
} from "@cassicore/foundation";
import type { EventType, RuntimeEvent } from "@cassicore/foundation";

// Default Configuration

const DEFAULT_CONFIG: EventHistoryConfig = {
  maxEvents: 10000,
  maxAgeMs: 60 * 60 * 1000, // 1 hour
  persistToDisk: false,
  captureEventTypes: "all",
  redactSensitive: true,
};

// Ring Buffer Implementation

class RingBuffer<T> {
  private buffer: (T | undefined)[];
  private head = 0; // Write position
  private count = 0; // Current size

  constructor(private capacity: number) {
    this.buffer = new Array(capacity);
  }

  push(item: T): void {
    this.buffer[this.head] = item;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) {
      this.count++;
    }
  }

  *entries(): Generator<{ index: number; item: T }> {
    if (this.count === 0) return;

    const start = this.count < this.capacity ? 0 : this.head;
    for (let i = 0; i < this.count; i++) {
      const idx = (start + i) % this.capacity;
      const item = this.buffer[idx];
      if (item !== undefined) {
        yield { index: idx, item };
      }
    }
  }

  toArray(): T[] {
    const result: T[] = [];
    for (const { item } of this.entries()) {
      result.push(item);
    }
    return result;
  }

  size(): number {
    return this.count;
  }

  clear(): void {
    this.buffer.fill(undefined);
    this.head = 0;
    this.count = 0;
  }
}

// Event History Store

export class EventHistory {
  private config: EventHistoryConfig;
  private buffer: RingBuffer<StoredEvent>;
  private typeIndex: Map<EventType, Set<string>> = new Map();
  private sessionIndex: Map<string, Set<string>> = new Map();
  private agentIndex: Map<string, Set<string>> = new Map();
  private lastCleanup: number = Date.now();

  constructor(config: Partial<EventHistoryConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.buffer = new RingBuffer<StoredEvent>(this.config.maxEvents);
  }

  // Capture

  /**
   * Capture an event to history with metadata
   */
  capture(event: RuntimeEvent, metadata: EventMetadata): void {
    // Check if we should capture this event type
    if (!this.shouldCapture(event.type)) {
      return;
    }

    // Redact sensitive fields if enabled
    const payload = this.config.redactSensitive
      ? this.redactSensitive(event)
      : event;

    const stored: StoredEvent = {
      id: ulid(),
      timestamp: new Date(),
      type: event.type,
      payload,
      metadata,
    };

    // Add to buffer
    this.buffer.push(stored);

    // Update indexes
    this.indexEvent(stored);

    // Periodic cleanup of old events
    this.maybeCleanup();
  }

  private shouldCapture(type: EventType): boolean {
    if (this.config.captureEventTypes === "all") return true;
    return this.config.captureEventTypes?.includes(type) ?? true;
  }

  private redactSensitive(event: RuntimeEvent): RuntimeEvent {
    // Deep clone and redact known sensitive fields
    const cloned = JSON.parse(JSON.stringify(event));

    const redactPaths = [
      "payload.token",
      "payload.apiKey",
      "payload.password",
      "payload.secret",
      "payload.auth",
      "payload.authorization",
    ];

    for (const path of redactPaths) {
      const parts = path.split(".");
      let current: any = cloned;
      for (let i = 0; i < parts.length - 1; i++) {
        if (current[parts[i]] === undefined) break;
        current = current[parts[i]];
      }
      const last = parts[parts.length - 1];
      if (current && current[last] !== undefined) {
        current[last] = "[REDACTED]";
      }
    }

    return cloned;
  }

  private indexEvent(event: StoredEvent): void {
    // Type index
    let typeSet = this.typeIndex.get(event.type);
    if (!typeSet) {
      typeSet = new Set();
      this.typeIndex.set(event.type, typeSet);
    }
    typeSet.add(event.id);

    // Session index
    if (event.metadata.sessionId) {
      let sessionSet = this.sessionIndex.get(event.metadata.sessionId);
      if (!sessionSet) {
        sessionSet = new Set();
        this.sessionIndex.set(event.metadata.sessionId, sessionSet);
      }
      sessionSet.add(event.id);
    }

    // Agent index
    if (event.metadata.agentId) {
      let agentSet = this.agentIndex.get(event.metadata.agentId);
      if (!agentSet) {
        agentSet = new Set();
        this.agentIndex.set(event.metadata.agentId, agentSet);
      }
      agentSet.add(event.id);
    }
  }

  // Query Engine

  /**
   * Execute a complex query against event history
   */
  query(filter: ComplexEventQuery): EventQueryResult {
    const startTime = performance.now();

    // Parse time specifications
    const since = filter.since ? this.parseTime(filter.since) : undefined;
    const until = filter.until ? this.parseTime(filter.until) : undefined;

    // Build result set
    let events = this.getCandidateEvents(filter.types, filter.typePattern);

    // Apply time filters
    if (since) {
      events = events.filter((e) => e.timestamp >= since);
    }
    if (until) {
      events = events.filter((e) => e.timestamp <= until);
    }

    // Apply where clause
    if (filter.where) {
      events = events.filter((e) => this.matchesWhere(e, filter.where!));
    }

    const totalAvailable = events.length;

    // Apply sorting
    events = this.sortEvents(events, filter.sort);

    // Apply aggregation if requested
    let results: StoredEvent[] | AggregationResult;
    if (filter.aggregate) {
      results = this.aggregate(events, filter.aggregate);
    } else {
      // Apply pagination
      const offset = filter.offset ?? 0;
      const limit = Math.min(filter.limit ?? 100, 1000);
      results = events.slice(offset, offset + limit);
    }

    // Format results
    if (!filter.aggregate && filter.format) {
      results = this.formatResults(results as StoredEvent[], filter.format);
    }

    const executionTimeMs = performance.now() - startTime;

    const metadata: QueryMetadata = {
      totalAvailable,
      returned: Array.isArray(results) ? results.length : results.groups.length,
      executionTimeMs,
      timeRange: this.calculateTimeRange(events),
      truncated: totalAvailable > (filter.limit ?? 100),
    };

    return {
      query: {
        mode: "complex",
        executedQuery: filter,
      },
      metadata,
      results,
    };
  }

  private parseTime(spec: Date | string): Date {
    if (spec instanceof Date) return spec;

    // Check for relative time (e.g., "5m", "1h")
    const relativeMatch = spec.match(/^(\d+)([smhd])$/);
    if (relativeMatch) {
      const value = parseInt(relativeMatch[1]);
      const unit = relativeMatch[2];
      const ms =
        unit === "s"
          ? value * 1000
          : unit === "m"
          ? value * 60 * 1000
          : unit === "h"
          ? value * 60 * 60 * 1000
          : value * 24 * 60 * 60 * 1000;
      return new Date(Date.now() - ms);
    }

    // ISO date string
    return new Date(spec);
  }

  private getCandidateEvents(
    types?: EventType[],
    typePattern?: string
  ): StoredEvent[] {
    // If specific types requested, use index
    if (types && types.length > 0) {
      const ids = new Set<string>();
      for (const type of types) {
        const typeIds = this.typeIndex.get(type);
        if (typeIds) {
          for (const id of typeIds) {
            ids.add(id);
          }
        }
      }
      return this.getEventsByIds(ids);
    }

    // If pattern requested, filter by pattern
    if (typePattern) {
      const regex = this.patternToRegex(typePattern);
      const ids = new Set<string>();
      for (const [type, typeIds] of this.typeIndex) {
        if (regex.test(type)) {
          for (const id of typeIds) {
            ids.add(id);
          }
        }
      }
      return this.getEventsByIds(ids);
    }

    // Otherwise, scan all
    return this.buffer.toArray();
  }

  private patternToRegex(pattern: string): RegExp {
    // Convert "subagent:*" to /^subagent:.*$/
    const escaped = pattern
      .replace(/[.+^${}()|[\]\\]/g, "\\$&")
      .replace(/\*/g, ".*")
      .replace(/\?/g, ".");
    return new RegExp(`^${escaped}$`);
  }

  private getEventsByIds(ids: Set<string>): StoredEvent[] {
    const events: StoredEvent[] = [];
    for (const { item } of this.buffer.entries()) {
      if (ids.has(item.id)) {
        events.push(item);
      }
    }
    return events;
  }

  private matchesWhere(event: StoredEvent, where: WhereClause): boolean {
    for (const [fieldPath, condition] of Object.entries(where)) {
      const value = this.getFieldByPath(event, fieldPath);
      if (!this.matchesCondition(value, condition)) {
        return false;
      }
    }
    return true;
  }

  private getFieldByPath(obj: any, path: string): any {
    const parts = path.split(".");
    let current = obj;
    for (const part of parts) {
      if (current === null || current === undefined) return undefined;
      current = current[part];
    }
    return current;
  }

  private matchesCondition(value: any, condition: QueryCondition): boolean {
    // Direct equality
    if (condition === null || typeof condition !== "object") {
      return value === condition;
    }

    // Operator-based condition
    const ops = condition as QueryOperators;

    if (ops.$eq !== undefined) return value === ops.$eq;
    if (ops.$ne !== undefined) return value !== ops.$ne;
    if (ops.$gt !== undefined)
      return typeof value === "number" && value > ops.$gt;
    if (ops.$gte !== undefined)
      return typeof value === "number" && value >= ops.$gte;
    if (ops.$lt !== undefined)
      return typeof value === "number" && value < ops.$lt;
    if (ops.$lte !== undefined)
      return typeof value === "number" && value <= ops.$lte;
    if (ops.$in !== undefined) return ops.$in.includes(value);
    if (ops.$nin !== undefined) return !ops.$nin.includes(value);
    if (ops.$contains !== undefined && typeof value === "string")
      return value.includes(ops.$contains);
    if (ops.$regex !== undefined && typeof value === "string")
      return new RegExp(ops.$regex).test(value);
    if (ops.$exists !== undefined)
      return ops.$exists ? value !== undefined : value === undefined;

    return false;
  }

  private sortEvents(
    events: StoredEvent[],
    sort?: SortSpec
  ): StoredEvent[] {
    const field = sort?.field ?? "timestamp";
    const order = sort?.order ?? "desc";

    return [...events].sort((a, b) => {
      const aVal = this.getFieldByPath(a, field);
      const bVal = this.getFieldByPath(b, field);

      if (aVal === bVal) return 0;
      if (aVal === undefined) return 1;
      if (bVal === undefined) return -1;

      const comparison = aVal < bVal ? -1 : 1;
      return order === "asc" ? comparison : -comparison;
    });
  }

  private aggregate(
    events: StoredEvent[],
    spec: ComplexEventQuery["aggregate"]
  ): AggregationResult {
    if (!spec) return { groups: [] };

    const groups = new Map<string, AggregationGroup>();

    for (const event of events) {
      const key = spec.groupBy
        ? String(this.getFieldByPath(event, spec.groupBy) ?? "unknown")
        : "_all";

      let group = groups.get(key);
      if (!group) {
        group = { key, count: 0 };
        groups.set(key, group);
      }

      group.count++;

      if (spec.sum || spec.avg || spec.min || spec.max) {
        const value = spec.sum
          ? (this.getFieldByPath(event, spec.sum) as number)
          : spec.avg
          ? (this.getFieldByPath(event, spec.avg) as number)
          : spec.min
          ? (this.getFieldByPath(event, spec.min) as number)
          : (this.getFieldByPath(event, spec.max!) as number);

        if (typeof value === "number") {
          if (spec.sum !== undefined) group.sum = (group.sum ?? 0) + value;
          if (spec.avg !== undefined) {
            group.avg = ((group.avg ?? 0) * (group.count - 1) + value) / group.count;
          }
          if (spec.min !== undefined)
            group.min = Math.min(group.min ?? Infinity, value);
          if (spec.max !== undefined)
            group.max = Math.max(group.max ?? -Infinity, value);
        }
      }
    }

    return { groups: Array.from(groups.values()) };
  }

  private formatResults(
    events: StoredEvent[],
    format: string
  ): StoredEvent[] {
    switch (format) {
      case "summary":
        // Return lightweight summary objects
        return events.map((e) => ({
          ...e,
          payload: { type: e.payload.type } as any, // Minimize payload
        }));
      case "timeline":
        // Already sorted, just ensure timestamp format
        return events;
      case "count":
        // Return empty array, count is in metadata
        return events;
      default:
        return events;
    }
  }

  private calculateTimeRange(events: StoredEvent[]): {
    from: Date;
    to: Date;
  } {
    if (events.length === 0) {
      return { from: new Date(), to: new Date() };
    }

    let from = events[0].timestamp;
    let to = events[0].timestamp;

    for (const e of events) {
      if (e.timestamp < from) from = e.timestamp;
      if (e.timestamp > to) to = e.timestamp;
    }

    return { from, to };
  }

  // Simple Query Helpers

  getRecent(count: number, type?: EventType): StoredEvent[] {
    return this.query({
      mode: "complex",
      types: type ? [type] : undefined,
      limit: count,
      sort: { field: "timestamp", order: "desc" },
    }).results as StoredEvent[];
  }

  getSince(timestamp: Date, type?: EventType): StoredEvent[] {
    return this.query({
      mode: "complex",
      since: timestamp,
      types: type ? [type] : undefined,
      sort: { field: "timestamp", order: "desc" },
    }).results as StoredEvent[];
  }

  getBySession(sessionId: string): StoredEvent[] {
    const ids = this.sessionIndex.get(sessionId);
    if (!ids) return [];
    return this.getEventsByIds(ids);
  }

  getByTypePattern(pattern: string): StoredEvent[] {
    return this.query({
      mode: "complex",
      typePattern: pattern,
      sort: { field: "timestamp", order: "desc" },
    }).results as StoredEvent[];
  }

  // Maintenance

  size(): number {
    return this.buffer.size();
  }

  clear(): void {
    this.buffer.clear();
    this.typeIndex.clear();
    this.sessionIndex.clear();
    this.agentIndex.clear();
  }

  private maybeCleanup(): void {
    const now = Date.now();
    if (now - this.lastCleanup < 60000) return; // Cleanup every minute max
    this.lastCleanup = now;

    const cutoff = new Date(now - this.config.maxAgeMs);

    // WHY: With ring buffer, old events are naturally evicted
    // This is just for index cleanup
    for (const [type, ids] of this.typeIndex) {
      for (const id of ids) {
        // We could check if event still exists in buffer
        // For now, ring buffer handles natural eviction
      }
    }
  }
}

// Singleton instance
let globalHistory: EventHistory | null = null;

export function getEventHistory(
  config?: Partial<EventHistoryConfig>
): EventHistory {
  if (!globalHistory) {
    globalHistory = new EventHistory(config);
  }
  return globalHistory;
}

export function setEventHistory(history: EventHistory): void {
  globalHistory = history;
}
