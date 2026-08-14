/**
 * VENDORED TYPE STUB — mirrors `code-analysis/types.js`. Surface: PreparedContext,
 * PrepareContextOptions, SpecificityScore, SpecificitySignal.
 */
export interface PreparedContextFile {
  filePath: string
  relevance: number
  reason: string
  keySymbols: string[]
  excerpt?: string
  [key: string]: unknown
}

export interface PreparedContext {
  text?: string
  files: PreparedContextFile[]
  extractedKeywords: string[]
  summary?: string
  estimatedTokens?: number
  usedCodebaseIndex?: boolean
  reachedCharBudget?: boolean
  error?: string
  [key: string]: unknown
}
export interface PrepareContextOptions {
  repoPath?: string
  goal?: string
  task?: string
  tokenBudget?: number
  includeContent?: boolean
  [key: string]: unknown
}

export type SpecificitySignalType =
  | 'file_path'
  | 'symbol_name'
  | 'error_trace'
  | 'line_number'
  | 'code_reference'
  | 'vague_modifier'

export interface SpecificitySignal {
  type: SpecificitySignalType
  weight: number
  match?: string
}

export interface SpecificityScore {
  score: number
  mode: 'full' | 'file_only' | 'skip'
  signals: SpecificitySignal[]
  adaptiveOverride?: {
    originalMode: 'full' | 'file_only' | 'skip'
    confidence?: number
    reason?: string
  }
}
