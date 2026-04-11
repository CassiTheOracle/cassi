import type { CorticalSignal } from '../cortex/types.js'
import type { CognitiveSignal, SystemLuminanceScore } from '../workspace/cognitive-signal.js'
import type { BridgeFocus } from '../locus-bridge/types.js'

export interface CurationConfig {
  charBudget: number
  recentWindowSize: number
  toolResultMaxChars: number
  ignitionThreshold: number
  excludeSessionPrefixes: string[]
}

export const DEFAULT_CURATION_CONFIG: CurationConfig = {
  charBudget: 120_000,
  recentWindowSize: 6,
  toolResultMaxChars: 2000,
  ignitionThreshold: 0.20,
  excludeSessionPrefixes: ['meditation:', 'module:', 'helix-review:'],
}

export interface ScoredMessage {
  messageIndex: number
  luminance: SystemLuminanceScore
  estimatedChars: number
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

export interface CurationSession {
  sessionId: string
  fileReadMap: Map<string, number>
  lastCuratedAt: number
  totalCurations: number
}

export interface BrainContext {
  foci: BridgeFocus[]
  workspaceSignals: CognitiveSignal[]
  focusTerms: Set<string>
  focusFiles: Set<string>

  cortexSignals: CorticalSignal[]
  mnemonicTerms: Set<string>

  recentMessageTerms: Set<string>
  recentMessageFiles: Set<string>
}

export const MESSAGE_CREDIBILITY_PRIORS: Record<string, number> = {
  'user': 0.90,
  'user:tool_result': 0.70,
  'assistant:tool_use': 0.65,
  'assistant': 0.40,
  'system': 0.20,
}

export interface CompressionConfig {
  toolResultMaxChars: number
}
