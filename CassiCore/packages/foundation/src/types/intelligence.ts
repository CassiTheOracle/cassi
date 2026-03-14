/**
 * Extended IntelligenceModule interfaces for CassiCore Phase 2.
 * Intelligence modules run in the main process (core-resident, not workers).
 * They have full access to EventBus, Logger, and each other via dependency injection.
 */

import type { Message } from "./runtime.js";
import type { IndexEntry, IndexSearchResult, IndexStats } from "./session-ref.js";

// ─── Memory ─────────────────────────────────────────────────────────────────

export interface MemoryEntry {
  id: string;
  type: "conversation" | "fact" | "error" | "success" | "reflection" | "insight" | "thinking" | "dialectic_yang" | "dialectic_yin" | "dialectic_serenity" | "event" | "tool_call" | "task";
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
  cognitiveClass?: 'episodic' | 'semantic' | 'procedural';
}

export interface SearchResult {
  entry: MemoryEntry;
  score: number;
}

// ─── Smart Recall ────────────────────────────────────────────────────────────

/**
 * Options for the smart recall pipeline — general-purpose intelligent
 * memory retrieval that replaces naive raw-query searches.
 */
export interface SmartRecallOpts {
  /** Max total results to return. Default: 8 */
  limit?: number;
  /** Minimum relevance score to include. Default: 0.15 */
  minScore?: number;
  /**
   * Filter to specific memory types. null = all types.
   * Default: ['conversation', 'fact', 'insight', 'reflection']
   */
  types?: MemoryEntry["type"][] | null;
  /** Prefer memories from this session (cross-session fallback). */
  sessionId?: string;
  /** Max results from archive search. Default: 3 */
  archiveLimit?: number;
  /** Use embedding re-scoring if available. Default: true */
  useEmbeddingRerank?: boolean;
  /**
   * Recent conversation turns for context-aware query extraction.
   * The pipeline uses these to build more focused search queries.
   */
  conversationContext?: Array<{ role: string; content: string }>;
  /**
   * Use the local LLM to generate focused search queries.
   * Requires the local generative model (llama.cpp) to be running.
   * Default: false
   */
  useLLMQueryExtraction?: boolean;
  /** Timeout for LLM query extraction in ms. Default: 2500 */
  llmTimeoutMs?: number;
}

export interface SmartRecallResult {
  entry: MemoryEntry;
  /** Combined relevance score (0-1). */
  score: number;
  /** Source of this result: 'memory' (FTS/semantic) or 'archive'. */
  source: 'memory' | 'archive';
  /** Memory type label for display. */
  type: string;
}

export interface IMemory {
  /** Store a memory entry. Returns the generated id. */
  store(entry: Omit<MemoryEntry, "id" | "createdAt">): Promise<string>;

  /** Semantic + full-text search. Returns scored results. */
  search(query: string, opts?: SearchOpts): Promise<SearchResult[]>;

  /**
   * Smart recall — general-purpose intelligent memory retrieval pipeline.
   *
   * Extracts focused queries from the user message + conversation context,
   * searches both memories and archives with type/session filtering,
   * re-scores via embeddings + cross-encoder, and returns deduplicated,
   * score-gated results.
   *
   * Designed to replace naive `search(rawUserMessage)` calls across all
   * subsystems (dialectic, thinker, context-assembler, etc.).
   */
  smartRecall?(query: string, opts?: SmartRecallOpts): Promise<SmartRecallResult[]>;

  /** Key-value store (replaces JSON state files) */
  kv_get<T>(key: string): Promise<T | undefined>;
  kv_set(key: string, value: unknown): Promise<void>;
  kv_del(key: string): Promise<void>;

  /** Delete a memory entry by ID */
  delete?(id: string): Promise<boolean>;

  /** Stats for /memory stats command */
  stats(): Promise<Record<string, number>>;

  // Archivist methods (optional - for comprehensive archiving)
  archiveConversation?(sessionId: string, userContent: string, assistantContent: string, thinking?: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;
  archiveDialectic?(sessionId: string, branch: 'yang' | 'yin' | 'serenity', content: string, parentId?: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;
  archiveInsight?(content: string, level: 'ponder' | 'think' | 'deep', metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;
  archivePattern?(patternType: string, description: string, evidence: string[], confidence: number, sessionId?: string): Promise<{ id: string; analysis: any }>;
  archiveEvent?(eventType: string, content: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;
  archiveToolCall?(sessionId: string, toolName: string, input: unknown, output?: unknown, error?: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;
  /** Archive a markdown document and store it with LLM-generated metadata */
  archiveDocument?(title: string, content: string, originalPath: string, metadata?: Record<string, unknown>): Promise<{ id: string; analysis: any }>;

  /** Expose the raw database handle for subsystems needing direct table access */
  getDb?(): import('better-sqlite3').Database;

  // Session index methods (optional — for hierarchical message indexing)
  /** Index a full session history. Returns the short label assigned to it. */
  indexSession?(sessionId: string, history: Message[]): string;
  /** Incrementally index new messages from `fromMsgIdx` onwards. */
  indexIncremental?(sessionId: string, history: Message[], fromMsgIdx: number): string;
  /** Resolve a compact session ref (e.g. "S0#M1.B0.P2") to its content. */
  resolveRef?(ref: string): IndexEntry[];
  /** Full-text search across session indices. */
  searchIndex?(query: string, opts?: { label?: string; sessionId?: string; limit?: number }): IndexSearchResult[];
  /** Get index stats for a session (by label or session ID). */
  indexStats?(labelOrSessionId: string): IndexStats | undefined;
  /** Get or create a short label for a session ID. */
  getSessionLabel?(sessionId: string): string;
  /** Resolve a label back to the full session ID. */
  getSessionIdFromLabel?(label: string): string | undefined;
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
  totalToolCalls?: number; // cumulative tool calls processed
  toolCallsUntilPonder?: number; // tool calls remaining until next ponder
  lastPonderAt?: Date;
  lastThinkAt?: Date;
  ponderInterval: number;
  thinkInterval: number;
  ponderUnit?: 'tool-calls' | 'turns'; // what unit the intervals count
  // New: cumulative number of insights emitted (distinct from totalTurns)
  insightCount?: number;
  recentToolActivity?: number; // count of recent tool calls in buffer
}

export interface IThinker {
  /** Get current stats */
  stats(): Promise<ThinkerStats>;

  /** Manually trigger a thinking cycle */
  think(depth: "Ponder" | "Think", signal?: AbortSignal): Promise<string>;
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
