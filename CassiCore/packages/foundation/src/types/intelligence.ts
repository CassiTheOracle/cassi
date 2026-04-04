/**
 * Extended IntelligenceModule interfaces for CassiCore Phase 2.
 * Intelligence modules run in the main process (core-resident, not workers).
 * They have full access to EventBus, Logger, and each other via dependency injection.
 */

import type { Message } from "./runtime.js";
import type { IndexEntry, IndexSearchResult, IndexStats } from "./session-ref.js";


export interface MemoryEntry {
  id: string;
  type: "conversation" | "fact" | "error" | "success" | "reflection" | "insight" | "thinking" | "dialectic_yang" | "dialectic_yin" | "dialectic_serenity" | "event" | "tool_call" | "task";
  content: string;
  embedding?: number[];
  metadata?: Record<string, unknown>;
  sessionId?: string;
  createdAt: Date;
  /** Importance score 0-10. Higher = surfaces more in search. Default: 5.0 */
  importance?: number;
  /** If true, this memory resists temporal decay and cannot be deep-archived. Default: false */
  pinned?: boolean;
  /** When this fact becomes valid (epoch seconds). Defaults to createdAt. */
  validAt?: Date;
  /** When this fact was superseded (epoch seconds). null = still valid. */
  invalidAt?: Date | null;
}

export interface SearchOpts {
  limit?: number;
  type?: MemoryEntry["type"];
  minScore?: number;
  sessionId?: string;
  cognitiveClass?: 'episodic' | 'semantic' | 'procedural';
  /** Only return memories with importance >= this value. */
  minImportance?: number;
  /** If true, only return pinned memories. */
  pinnedOnly?: boolean;
  timeAfter?: Date;
  timeBefore?: Date;
  /** If true, exclude invalidated memories from results. Default: true */
  validOnly?: boolean;
  /** Point-in-time query — search as of this timestamp. Default: now */
  validAsOf?: Date;
}

/** Structured confidence level for search results */
export type RetrievalConfidence = 'high' | 'moderate' | 'low' | 'none';

export interface SearchResult {
  entry: MemoryEntry;
  score: number;
  /** Structured confidence derived from score thresholds */
  confidence?: RetrievalConfidence;
}


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
  /** Structured confidence derived from score thresholds */
  confidence?: RetrievalConfidence;
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

  /** Pin a memory — marks it as decay-resistant with importance >= 9.0. */
  pin?(id: string): Promise<boolean>;

  /** Unpin a previously pinned memory. */
  unpin?(id: string): Promise<boolean>;

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

  indexSession?(sessionId: string, history: Message[]): string;
  indexIncremental?(sessionId: string, history: Message[], fromMsgIdx: number): string;
  resolveRef?(ref: string): IndexEntry[];
  searchIndex?(query: string, opts?: { label?: string; sessionId?: string; limit?: number }): IndexSearchResult[];
  indexStats?(labelOrSessionId: string): IndexStats | undefined;
  getSessionLabel?(sessionId: string): string;
  getSessionIdFromLabel?(label: string): string | undefined;

  /** Invalidate a memory entry — mark it as superseded at the current time. */
  invalidate?(id: string, reason?: string): Promise<boolean>;

  /**
   * Supersede an existing memory with a new one.
   * Invalidates the old memory and creates a new entry linking to it via metadata.supersedes.
   */
  supersede?(oldId: string, newContent: string, metadata?: Record<string, unknown>): Promise<string>;
}


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
  saveTurn(turn: Omit<ConversationTurn, "id" | "timestamp">): Promise<void>;
  getRecent(sessionId: string, limit?: number): Promise<ConversationTurn[]>;
  searchHistory(query: string, limit?: number): Promise<ConversationTurn[]>;
  prune(retentionDays?: number): Promise<number>;
}


export type RecoveryStrategy = "retry" | "retry-with-backoff" | "fallback-model" | "skip";

export interface RecoveryPattern {
  errorPattern: string;
  strategy: RecoveryStrategy;
  fallbackModel?: string;
  maxAttempts: number;
}

export interface IRecover {
  register(pattern: RecoveryPattern): void;
  handleError(error: Error, context: Record<string, unknown>): Promise<RecoveryStrategy | null>;
  recordSuccess(errorPattern: string, strategy: RecoveryStrategy): Promise<void>;
}


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
  add(entry: { pattern: string; category: string; fix?: string; context?: string }): Promise<string>;
  search(query: string, limit?: number): Promise<ReflectionPattern[]>;
  resolve(id: string, fix: string): Promise<void>;
  unresolved(limit?: number): Promise<ReflectionPattern[]>;
}


export interface ThinkerStats {
  totalInsights: number;
  totalTurns: number;
  totalToolCalls?: number;
  toolCallsUntilPonder?: number;
  lastPonderAt?: Date;
  lastThinkAt?: Date;
  ponderInterval: number;
  thinkInterval: number;
  ponderUnit?: 'tool-calls' | 'turns';
  insightCount?: number;
  recentToolActivity?: number;
}

export interface IThinker {
  stats(): Promise<ThinkerStats>;
  think(depth: "Ponder" | "Think", signal?: AbortSignal): Promise<string>;
}


export type OptimizationAction =
  | "summarize"
  | "steer"
  | "context-reset"
  | "kill"
  | "none"

export interface SessionHealth {
  sessionKey: string
  label?: string
  model: string
  estimatedTokens: number
  tokenVelocity: number
  outputVelocity: number
  loopScore: number
  stuckScore: number
  lastProgressAt: Date
  runtime: number
  interventionCount: number
  lastAction?: OptimizationAction
}

export interface OptimizationDecision {
  sessionKey: string
  action: OptimizationAction
  reason: string
  confidence: number
  estimatedSavings?: number
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
  optimize(): Promise<OptimizationDecision[]>
  scoreSession(sessionKey: string): Promise<SessionHealth | null>
  strategyWeights(): Promise<Record<OptimizationAction, number>>
  history(limit?: number): Promise<OptimizationOutcome[]>
}


/**
 * Configuration for the Dreamer cognitive module.
 * Also available from core/intelligence/dreamer/types.ts (DreamerConfig).
 * This re-export here gives callers a single import path via types/intelligence.ts.
 */
export type { DreamerConfig } from '../core/intelligence/dreamer/types.js'
