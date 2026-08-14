/**
 * Event Query Types — Universal information querying for the EventBus
 *
 * Supports both complex structured queries for precise filtering
 * and simple natural language queries for quick exploration.
 */

import type { EventType, RuntimeEvent } from "./events.js";

// Time Specifications

/** Relative time string like "5m", "1h", "30s", "2d" */
export type RelativeTime = `${number}${"s" | "m" | "h" | "d"}`;

/** Absolute or relative time */
export type TimeSpec = Date | RelativeTime | string;

// Query Conditions (MongoDB-like operators)

export interface QueryOperators<T = any> {
  /** Equal */
  $eq?: T;
  /** Not equal */
  $ne?: T;
  /** Greater than */
  $gt?: number;
  /** Greater than or equal */
  $gte?: number;
  /** Less than */
  $lt?: number;
  /** Less than or equal */
  $lte?: number;
  /** In array */
  $in?: T[];
  /** Not in array */
  $nin?: T[];
  /** String contains */
  $contains?: string;
  /** Regex pattern match */
  $regex?: string;
  /** Field exists */
  $exists?: boolean;
}

/** A condition can be a direct value or operators */
export type QueryCondition<T = any> = T | QueryOperators<T>;

/** Where clause maps field paths to conditions */
export type WhereClause = {
  [fieldPath: string]: QueryCondition;
};

// Aggregation

export interface AggregationSpec {
  /** Group results by this field path */
  groupBy?: string;
  /** Return count per group */
  count?: boolean;
  /** Sum this numeric field */
  sum?: string;
  /** Average this numeric field */
  avg?: string;
  /** Minimum of this field */
  min?: string;
  /** Maximum of this field */
  max?: string;
}

// Sorting

export interface SortSpec {
  /** Field to sort by */
  field: "timestamp" | "type" | string;
  /** Sort order */
  order: "asc" | "desc";
}

// Complex Query (Structured)

export interface ComplexEventQuery {
  mode: "complex";

  /** Start time (ISO date or relative like "5m", "1h") */
  since?: TimeSpec;

  /** End time (ISO date or relative) */
  until?: TimeSpec;

  /** Filter by specific event types */
  types?: EventType[];

  /** Wildcard pattern for event types (e.g., "subagent:*", "provider:*") */
  typePattern?: string;

  /** Field conditions using operators */
  where?: WhereClause;

  /** Aggregation specification */
  aggregate?: AggregationSpec;

  /** Maximum results to return (default: 100, max: 1000) */
  limit?: number;

  /** Pagination offset */
  offset?: number;

  /** Sort specification */
  sort?: SortSpec;

  /** Output format */
  format?: "full" | "summary" | "count" | "timeline" | "json";
}

// Simple Query (Natural Language)

export interface SimpleEventQuery {
  mode: "simple";

  /** Natural language query description */
  query: string;

  /** Maximum results (default: 50) */
  limit?: number;
}

// Union Type

export type EventQuery = ComplexEventQuery | SimpleEventQuery;

// Event History Store Types

export interface EventHistoryConfig {
  /** Maximum events to keep in buffer (default: 10000) */
  maxEvents: number;

  /** Maximum age in milliseconds (default: 1 hour) */
  maxAgeMs: number;

  /** Persist to disk for crash recovery (default: false) */
  persistToDisk?: boolean;

  /** Which event types to capture (default: "all") */
  captureEventTypes?: EventType[] | "all";

  /** Redact sensitive fields from payloads (default: true) */
  redactSensitive?: boolean;
}

export interface EventMetadata {
  /** Module/component that emitted the event */
  source: string;

  /** Associated session ID */
  sessionId?: string;

  /** Associated agent ID */
  agentId?: string;

  /** Additional context */
  context?: Record<string, unknown>;
}

export interface StoredEvent {
  /** Unique event ID (ULID) */
  id: string;

  /** Event timestamp */
  timestamp: Date;

  /** Event type */
  type: EventType;

  /** Full event payload */
  payload: RuntimeEvent;

  /** Event metadata */
  metadata: EventMetadata;
}

// Query Results

export interface QueryMetadata {
  /** Total matching events in history */
  totalAvailable: number;

  /** Events returned in this response */
  returned: number;

  /** Query execution time in milliseconds */
  executionTimeMs: number;

  /** Time range of results */
  timeRange: {
    from: Date;
    to: Date;
  };

  /** Whether results were truncated */
  truncated: boolean;
}

export interface AggregationGroup {
  /** Group key value */
  key: string;

  /** Count in this group */
  count: number;

  /** Sum of field (if requested) */
  sum?: number;

  /** Average of field (if requested) */
  avg?: number;

  /** Minimum of field (if requested) */
  min?: number;

  /** Maximum of field (if requested) */
  max?: number;
}

export interface AggregationResult {
  /** Grouped results */
  groups: AggregationGroup[];

  /** Overall totals */
  totals?: {
    count: number;
    sum?: number;
    avg?: number;
  };
}

export interface EventQueryResult {
  /** Original query info */
  query: {
    mode: "complex" | "simple";
    /** The actual executed query (after simple→complex translation) */
    executedQuery: ComplexEventQuery;
    /** If simple query, shows the translation explanation */
    translation?: string;
  };

  /** Result metadata */
  metadata: QueryMetadata;

  /** Query results */
  results: StoredEvent[] | AggregationResult;
}

// Preset Queries

export interface QueryPreset {
  /** Preset name */
  name: string;

  /** Human-readable description */
  description: string;

  /** Category for grouping */
  category: string;

  /** The query definition */
  query: ComplexEventQuery;
}

// Event History Interface

export interface IEventHistory {
  /** Capture an event to history */
  capture(event: RuntimeEvent, metadata: EventMetadata): void;

  /** Execute a query against history */
  query(filter: ComplexEventQuery): EventQueryResult;

  /** Get recent events */
  getRecent(count: number, type?: EventType): StoredEvent[];

  /** Get events since timestamp */
  getSince(timestamp: Date, type?: EventType): StoredEvent[];

  /** Get events by session ID */
  getBySession(sessionId: string): StoredEvent[];

  /** Get events by type pattern */
  getByTypePattern(pattern: string): StoredEvent[];

  /** Get current event count */
  size(): number;

  /** Clear all history */
  clear(): void;
}
