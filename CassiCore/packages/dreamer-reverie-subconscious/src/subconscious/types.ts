/**
 * Subconscious (Conscious Observer) — Type Definitions
 *
 * Types for the new stream-of-consciousness architecture:
 * - Universal event observation via EventStream
 * - Real-time heuristic pattern detection
 * - Periodic LLM observer sweeps
 * - System-wide mental model (SystemModel)
 */

// ─── Core Observation Types ───────────────────────────────────────────────────

/** Source of an observation — heuristic (real-time rule) or llm (periodic sweep) */
export type ObservationSource = "heuristic" | "llm";

/** A structured observation produced by the HeuristicObserver or LLMObserver */
export interface Observation {
  id: string;
  summary: string;
  patterns: string[];
  confidence: number;
  source: ObservationSource;
  relatedEventTypes: string[];
  /** Unix timestamp (ms) */
  timestamp: number;
  /** Optional session this observation applies to */
  sessionId?: string;
  /**
   * SessionRef citation for the source moment that triggered this observation,
   * e.g. "S2#M7.B0". Present when the observation was triggered by an indexed
   * session message that could be resolved to a compact reference.
   */
  sessionRef?: string;
}

/** A concern or anomaly worth surfacing to the system */
export interface Anomaly {
  id: string;
  description: string;
  severity: "low" | "medium" | "high";
  eventTypes: string[];
  suggestedAction?: string;
  /** Unix timestamp (ms) */
  timestamp: number;
  /** Optional session this anomaly applies to */
  sessionId?: string;
  /** Whether this anomaly has been acknowledged */
  acknowledged?: boolean;
  /**
   * SessionRef citation pointing to the historical moment most relevant to
   * this anomaly, e.g. "S1#M4.B1". Populated via async cross-session lookup.
   */
  sessionRef?: string;
}

// ─── EventStream Types ────────────────────────────────────────────────────────

export interface EventStreamEntry {
  event: import("../../../types/events.js").RuntimeEvent;
  receivedAt: number;
}

export interface StreamSummary {
  windowMs: number;
  totalEvents: number;
  eventsPerSecond: number;
  topTypes: Array<{ type: string; count: number }>;
  recentSequence: string[];
  activeSessions: number;
}

export interface EventStreamConfig {
  /** Total events to retain in the ring buffer (default: 10_000) */
  maxBufferSize: number;
  /** Events per session index (default: 2_000) */
  sessionBufferSize: number;
}

// ─── LLM Observer Types ───────────────────────────────────────────────────────

export interface LLMObservation {
  id: string;
  summary: string;
  patterns: string[];
  concerns: string[];
  opportunities: string[];
  confidence: number;
  /** Unix timestamp (ms) */
  timestamp: number;
  windowMs: number;
  eventCount: number;
  /**
   * Top matching fragments from past indexed sessions, used as historical
   * context in the LLM sweep prompt. Each entry carries a compact SessionRef
   * (e.g. "S3#M11.B0"), a content snippet, and the FTS relevance score.
   */
  crossSessionMatches?: Array<{ ref: string; snippet: string; score: number }>;
}

export interface LLMObserverConfig {
  enabled: boolean;
  /** How often to run a sweep (ms, default: 30_000) */
  intervalMs: number;
  /** How far back to look per sweep (ms, default: 60_000) */
  windowMs: number;
  maxRetries: number;
  /** Override model (defaults to MODEL_DEFAULTS.fast) */
  model?: string;
}

// ─── System Model Types ───────────────────────────────────────────────────────

export interface SessionState {
  sessionId: string;
  startedAt: number;
  lastActivityAt: number;
  turnCount: number;
  tokenCount: number;
  phase: "initial" | "active" | "concluding";
  currentTopic?: string;
  recentToolCalls: string[];
}

export interface SystemModelSnapshot {
  capturedAt: number;
  sessionCount: number;
  providerHealth: Record<string, "healthy" | "degraded" | "error" | "rate_limited">;
  pluginStatus: Record<string, "healthy" | "crashed" | "stopped">;
  budgetTiers: Record<string, string>;
  activeDrones: number;
  activeTeams: number;
  recentPatterns: string[];
  observationCount: number;
  systemHealth: "healthy" | "degraded" | "critical";
}

// ─── Subconscious Config ──────────────────────────────────────────────────────

export interface SubconsciousConfig {
  /** Enable the subconscious module (default: true) */
  enabled?: boolean;
  /** Priority in the intelligence layer (default: 40) */
  priority?: number;
  /** Background persistence interval (ms, default: 60_000) */
  persistenceIntervalMs?: number;

  /** EventStream ring buffer size (default: 10_000) */
  eventBufferSize?: number;

  /** LLM observer settings */
  llmObserver?: Partial<LLMObserverConfig>;
}

export const DEFAULT_SUBCONSCIOUS_CONFIG: Required<SubconsciousConfig> = {
  enabled: true,
  priority: 40,
  persistenceIntervalMs: 60_000,
  eventBufferSize: 10_000,
  llmObserver: {
    enabled: true,
    intervalMs: 30_000,
    windowMs: 60_000,
    maxRetries: 2,
  },
};

// ─── Legacy compat (used by session-digest.ts and other consumers) ────────────

/** Conversation phase — kept for SessionDigest compat */
export type ConversationPhase =
  | "initial"
  | "exploration"
  | "deep_dive"
  | "resolution"
  | "wrap_up";

/** @deprecated Use Observation instead */
export interface SubconsciousSignal {
  type: string;
  confidence: number;
  description: string;
  sessionId?: string;
  timestamp: number;
}
