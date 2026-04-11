import type { CorticalSignal } from '../cortex/types.js'

export interface CurationConfig {
  charBudget: number
  recentWindowSize: number
  toolResultMaxChars: number
  excludeSessionPrefixes: string[]
}

export const DEFAULT_CURATION_CONFIG: CurationConfig = {
  charBudget: 400_000,
  recentWindowSize: 20,
  toolResultMaxChars: 4000,
  excludeSessionPrefixes: ['meditation:', 'module:', 'helix-review:'],
}

export interface ScoredMessage {
  messageIndex: number
  score: number
  estimatedChars: number
  mnemonicallyCovered: boolean
}

export interface CurationMeta {
  originalCount: number
  curatedCount: number
  originalChars: number
  curatedChars: number
  compressed: number
  deduped: number
  dropped: number
  gapNotes: number
  durationMs: number
  skipped?: boolean
  reason?: string
}

export interface CurationResult {
  messages: any[]
  meta: CurationMeta
}

export interface CachedScore {
  score: number
  mnemonicallyCovered: boolean
  hash: number
}

export interface CurationSession {
  sessionId: string
  scoreCache: Map<string, CachedScore>
  fileReadMap: Map<string, number>
  lastCuratedAt: number
  totalCurations: number
}

export interface BrainContext {
  cortexSignals: CorticalSignal[]
  cortexTerms: Set<string>
  cortexFiles: Set<string>
  mnemonicTerms: Set<string>
  recentMessageTerms: Set<string>
  recentMessageFiles: Set<string>
}

export interface CompressionConfig {
  toolResultMaxChars: number
}
