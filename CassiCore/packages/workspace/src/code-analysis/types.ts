/**
 * Shared types for Code Analysis features.
 *
 * Covers dead-code detection, hotspot analysis, git co-change correlation,
 * context assembly, specificity scoring, and feedback tracking.
 */


/** A symbol that appears to be unused (no callers, no importers). */
export interface DeadCodeResult {
  /** Fully-qualified symbol name */
  symbolName: string
  /** File path relative to repo root */
  filePath: string
  /** LSP symbol kind (function, class, method, …) */
  kind: string
  /** Lines of code in the symbol body */
  lineCount: number
  /** ISO-8601 date this file was last modified (from git) */
  lastModified: string
  /** Confidence that the symbol is truly dead (0–1) */
  confidence: number
  /** Why we think it is dead */
  reason: string
}

/** Options for the dead-code analyzer. */
export interface DeadCodeOptions {
  /** Scope analysis to this directory (relative to repo root) */
  path?: string
  /** Minimum confidence to include (default 0.7) */
  minConfidence?: number
  /** Include symbols only referenced from test files */
  includeTestOnly?: boolean
  /** Repo name for GitNexus multi-repo setups */
  repo?: string
}


/** A file ranked by composite risk score. */
export interface HotspotResult {
  filePath: string
  /** Composite score 0–1 */
  score: number
  /** Individual dimension scores (each 0–1) */
  dimensions: {
    size: number
    complexity: number
    coupling: number
  }
  /** Raw metrics behind each dimension */
  raw: {
    lineCount: number
    symbolCount: number
    incomingEdges: number
    outgoingEdges: number
  }
}

/** Options for the hotspot analyzer. */
export interface HotspotOptions {
  /** Scope to a directory */
  path?: string
  /** Max results to return (default 20) */
  limit?: number
  /** Repo name for GitNexus multi-repo setups */
  repo?: string
}


/** Two files that frequently change together. */
export interface CochangeResult {
  /** The paired file */
  filePath: string
  /** Jaccard-like score = cochanges / max(changesA, changesB) */
  score: number
  /** Absolute number of commits where both files changed */
  cochangeCount: number
  /** Total individual changes of the paired file */
  fileChangeCount: number
}

/** Options for the cochange analyzer. */
export interface CochangeOptions {
  /** Target file to find co-movers for */
  target: string
  /** Max results (default 10) */
  limit?: number
  /** Minimum co-occurrences to include (default 3) */
  minCommits?: number
  /** Git date filter (default '6 months ago') */
  since?: string
}


/** A key file in the prepared context. */
export interface PreparedFile {
  filePath: string
  /** Why this file was selected */
  reason: string
  /** Relevance score 0–1 */
  relevance: number
  /** Key symbol names in this file */
  keySymbols: string[]
  /** Short excerpt (if include_content enabled) */
  excerpt?: string
}

/** Full result of a prepare_context call. */
export interface PreparedContext {
  /** One-paragraph summary of the relevant code surface */
  summary: string
  /** Ranked key files */
  files: PreparedFile[]
  /** How many tokens the context occupies (approximate) */
  estimatedTokens: number
  /** Keywords extracted from the task description */
  extractedKeywords: string[]
}

/** Options for context assembly. */
export interface PrepareContextOptions {
  /** Task description */
  task: string
  /** Token budget for the assembled context (default 8000) */
  tokenBudget?: number
  /** Include file excerpts (default true) */
  includeContent?: boolean
  /** Scope to a directory */
  scope?: string
  /** Repo name for GitNexus multi-repo setups */
  repo?: string
}


/** Result of a specificity assessment. */
export interface SpecificityScore {
  /** Overall score 0–1 */
  score: number
  /** Recommended context mode based on score */
  mode: 'full' | 'file_only' | 'skip'
  /** Signals that contributed to the score */
  signals: SpecificitySignal[]
}

/** An individual signal in the specificity assessment. */
export interface SpecificitySignal {
  /** What was detected */
  type: 'file_path' | 'symbol_name' | 'error_trace' | 'line_number' | 'vague_modifier' | 'code_reference'
  /** Weight applied (+positive or -negative) */
  weight: number
  /** The matched text */
  match: string
}


/** Record of a code-context injection and whether it helped. */
export interface ContextFeedbackRecord {
  id: string
  sessionId: string
  queryText: string
  specificityScore: number
  contextMode: 'full' | 'file_only' | 'skip'
  filesSuggested: string[]
  filesActuallyUsed: string[]
  wasUseful: boolean
  timestamp: number
}


/** Metadata about a single SQLite table. */
export interface TableSchema {
  name: string
  columns: Array<{ name: string; type: string; notnull: boolean; pk: boolean }>
  rowCount: number
}

/** Metadata about a single SQLite database. */
export interface DatabaseSchema {
  name: string
  path: string
  sizeBytes: number
  tables: TableSchema[]
}

/** Full schema introspection result. */
export interface SchemaIntrospectionResult {
  databases: DatabaseSchema[]
  totalTables: number
  totalRows: number
}
