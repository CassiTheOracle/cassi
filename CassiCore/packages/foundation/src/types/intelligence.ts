/**
 * Extended IntelligenceModule interfaces for CassiCore Phase 2.
 * Intelligence modules run in the main process (core-resident, not workers).
 * They have full access to EventBus, Logger, and each other via dependency injection.
 */

import type { RuntimeEvent } from "./events.js";

// ─── Memory ─────────────────────────────────────────────────────────────────

export interface MemoryEntry {
  id: string;
  type: "conversation" | "fact" | "error" | "success" | "reflection" | "insight";
  content: string;
  embedding?: number[];
  metadata?: Record<string, unknown>;
  sessionId?: string;
  createdAt: Date;
}

export interface SearchOpts {
  limit?: number;
  type?: MemoryEntry["type"];
  minScore?: number;
  sessionId?: string;
}

export interface SearchResult {
  entry: MemoryEntry;
  score: number;
}

export interface IMemory {
  /** Store a memory entry. Returns the generated id. */
  store(entry: Omit<MemoryEntry, "id" | "createdAt">): Promise<string>;

  /** Semantic + full-text search. Returns scored results. */
  search(query: string, opts?: SearchOpts): Promise<SearchResult[]>;

  /** Key-value store (replaces JSON state files) */
  kv_get<T>(key: string): Promise<T | undefined>;
  kv_set(key: string, value: unknown): Promise<void>;
  kv_del(key: string): Promise<void>;

  /** Stats for /memory stats command */
  stats(): Promise<Record<string, number>>;
}

// ─── Continuity ──────────────────────────────────────────────────────────────

export interface ConversationTurn {
  id: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  tokensUsed?: number;
  model?: string;
  timestamp: Date;
}

export interface IContinuity {
  /** Save a conversation turn */
  saveTurn(turn: Omit<ConversationTurn, "id" | "timestamp">): Promise<void>;

  /** Get recent turns for a session */
  getRecent(sessionId: string, limit?: number): Promise<ConversationTurn[]>;

  /** Search conversation history semantically */
  searchHistory(query: string, limit?: number): Promise<ConversationTurn[]>;

  /** Prune entries older than retentionDays */
  prune(retentionDays?: number): Promise<number>;
}

// ─── Recover ─────────────────────────────────────────────────────────────────

export type RecoveryStrategy = "retry" | "retry-with-backoff" | "fallback-model" | "skip";

export interface RecoveryPattern {
  errorPattern: string;
  strategy: RecoveryStrategy;
  fallbackModel?: string;
  maxAttempts: number;
}

export interface IRecover {
  /** Register a recovery pattern */
  register(pattern: RecoveryPattern): void;

  /** Attempt recovery for an error. Returns strategy used or null if no match. */
  handleError(error: Error, context: Record<string, unknown>): Promise<RecoveryStrategy | null>;

  /** Record a successful recovery */
  recordSuccess(errorPattern: string, strategy: RecoveryStrategy): Promise<void>;
}

// ─── Reflect ─────────────────────────────────────────────────────────────────

export interface ReflectionPattern {
  id: string;
  pattern: string;
  category: string;
  fix?: string;
  occurrences: number;
  resolved: boolean;
  createdAt: Date;
}

export interface IReflect {
  /** Add a new error/success pattern */
  add(entry: { pattern: string; category: string; fix?: string; context?: string }): Promise<string>;

  /** Search for known patterns */
  search(query: string, limit?: number): Promise<ReflectionPattern[]>;

  /** Resolve a pattern (mark as fixed) */
  resolve(id: string, fix: string): Promise<void>;

  /** Get unresolved patterns */
  unresolved(limit?: number): Promise<ReflectionPattern[]>;
}

// ─── Thinker ─────────────────────────────────────────────────────────────────

export interface ThinkerStats {
  totalInsights: number;   // cumulative insights emitted
  totalTurns: number;      // cumulative turns processed
  lastPonderAt?: Date;
  lastThinkAt?: Date;
  ponderInterval: number;
  thinkInterval: number;
  // New: cumulative number of insights emitted (distinct from totalTurns)
  insightCount?: number;
}

export interface IThinker {
  /** Get current stats */
  stats(): Promise<ThinkerStats>;

  /** Manually trigger a thinking cycle */
  think(depth: "Ponder" | "Think"): Promise<string>;
}

// ─── Optimizer ──────────────────────────────────────────────────────────────

export type OptimizationAction = 
  | "summarize"       // inject summary, agent continues
  | "steer"           // send corrective prompt
  | "context-reset"   // kill + respawn with compressed context  
  | "kill"            // terminate, no respawn
  | "none"            // healthy, no action needed

export interface SessionHealth {
  sessionKey: string
  label?: string
  model: string
  estimatedTokens: number
  tokenVelocity: number      // tokens added per minute
  outputVelocity: number     // distinct output chunks per minute
  loopScore: number          // 0-1, higher = more repeated content
  stuckScore: number         // 0-1, higher = no meaningful progress
  lastProgressAt: Date
  runtime: number            // ms since session started
  interventionCount: number
  lastAction?: OptimizationAction
}

export interface OptimizationDecision {
  sessionKey: string
  action: OptimizationAction
  reason: string
  confidence: number         // 0-1
  estimatedSavings?: number  // estimated tokens saved
}

export interface OptimizationOutcome {
  decisionId: string
  sessionKey: string
  action: OptimizationAction
  tokensBefore: number
  tokensAfter: number
  sessionCompleted: boolean
  sessionSuccess: boolean
  timestamp: Date
}

export interface IOptimizer {
  /** Run an optimization cycle over all active sessions */
  optimize(): Promise<OptimizationDecision[]>
  
  /** Get health score for a specific session */
  scoreSession(sessionKey: string): Promise<SessionHealth | null>
  
  /** Get learned strategy weights (what has worked) */
  strategyWeights(): Promise<Record<OptimizationAction, number>>
  
  /** Get recent optimization history */
  history(limit?: number): Promise<OptimizationOutcome[]>
}
