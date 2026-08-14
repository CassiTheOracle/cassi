/**
 * Reasoning Bank Types
 *
 * Type definitions for the reasoning trace cache. Stores high-quality
 * reasoning traces from Helix sessions for retrieval and reuse in
 * future sessions with similar goals.
 */

/** A cached reasoning trace from a completed Helix session */
export interface ReasoningTrace {
  id: string
  /** Source Helix session that produced this trace */
  sourceHelixId: string
  /** Goal the reasoning was applied to */
  goal: string
  /** Short summary of the approach taken */
  approach: string
  /** Full reasoning content (synthesis of the session's output) */
  content: string
  /** Quality score from Brainstem (0-1) */
  qualityScore: number
  /** Whether the session completed successfully */
  succeeded: boolean
  /** Files that were relevant to this reasoning */
  relevantFiles: string[]
  /** Task type classification */
  taskType: 'implementation' | 'research' | 'review' | 'refactor' | 'bugfix' | 'general'
  /** Number of times this trace has been retrieved and used */
  referenceCount: number
  /** Timestamp when the trace was created */
  createdAt: number
  /** Timestamp when the trace was last retrieved */
  lastRetrievedAt: number | null
}

/** Options for storing a reasoning trace */
export interface StoreTraceOpts {
  sourceHelixId: string
  goal: string
  approach: string
  content: string
  qualityScore: number
  succeeded: boolean
  relevantFiles?: string[]
  taskType?: ReasoningTrace['taskType']
}

/** Options for searching reasoning traces */
export interface SearchTracesOpts {
  /** Natural language query to match against goal/content */
  query: string
  /** Minimum quality score (0-1) */
  minQuality?: number
  /** Only return successful traces */
  successOnly?: boolean
  /** Filter by task type */
  taskType?: ReasoningTrace['taskType']
  /** Filter by relevant files */
  relevantFiles?: string[]
  /** Maximum results to return */
  limit?: number
}

/** Result from a reasoning trace search */
export interface SearchResult {
  trace: ReasoningTrace
  /** Relevance score from search (0-1) */
  relevance: number
}

/** Reasoning Bank statistics */
export interface ReasoningBankStats {
  totalTraces: number
  successfulTraces: number
  averageQuality: number
  totalReferences: number
  tracesNeverReferenced: number
  byTaskType: Record<string, number>
}

/** Options for the Reasoning Bank module */
export interface ReasoningBankOpts {
  /** Database file path (default: ~/.cassicore/data/reasoning-bank.db) */
  dbPath?: string
  /** Minimum quality score to accept a trace (default: 0.6) */
  minQualityThreshold?: number
  /** Maximum age in days before traces are eligible for pruning (default: 90) */
  maxAgeDays?: number
  /** Maximum traces to store (default: 1000) */
  maxTraces?: number
}
