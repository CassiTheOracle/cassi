import type { CorticalSignal, SignalType, Affect } from '../cortex/types.js'
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


/**
 * A cortical signal with pre-computed weight and extracted terms
 * for efficient matching during message scoring.
 */
export interface WeightedSignal {
  signal: CorticalSignal
  /** Pre-computed composite weight from type × region × salience × confidence */
  weight: number
  /** Extracted terms for content matching */
  terms: string[]
}

/**
 * Structured index of cortex signals, categorized for efficient access
 * during multi-axis scoring. Built once per curation call.
 */
export interface CortexIndex {
  /** Signals grouped by type — concern, decision, insight, etc. */
  byType: Partial<Record<SignalType, WeightedSignal[]>>
  /** Signals grouped by region — executive, limbic, etc. */
  byRegion: Partial<Record<string, WeightedSignal[]>>
  /** Signals currently in session working memory */
  workingMemory: WeightedSignal[]
  /** High-salience signals (>0.6) */
  highSalience: WeightedSignal[]
  /** Negative-valence signals representing threats or concerns */
  threats: WeightedSignal[]
}

/** Signal type importance for message scoring */
export const SIGNAL_TYPE_WEIGHTS: Record<string, number> = {
  concern: 1.5, anomaly: 1.5, decision: 1.3, insight: 1.3,
  request: 1.2, action: 1.1, association: 1.0, perception: 0.8,
}

/** Cortex region importance for message scoring */
export const REGION_WEIGHTS: Record<string, number> = {
  executive: 1.4, limbic: 1.3, monitor: 1.2,
  motor: 1.1, association: 1.0, sensory: 0.9,
}


/**
 * A self-model retrieval result enriched with concept metadata
 * for use in architectural relevance and novelty scoring.
 */
export interface SelfModelHit {
  content: string
  score: number
  nodeType: string     // module, capability, pattern, principle, weakness
  conceptName: string  // name extracted before " — " separator
}


export interface BrainContext {
  foci: BridgeFocus[]
  workspaceSignals: CognitiveSignal[]
  focusTerms: Set<string>
  focusFiles: Set<string>

  cortexSignals: CorticalSignal[]
  cortexIndex: CortexIndex
  affectState: Affect | null
  workingMemoryTerms: Set<string>

  mnemonicTerms: Set<string>

  architecturalTerms: Set<string>
  architecturalConcepts: Set<string>
  architecturalHits: SelfModelHit[]

  pinealTerms: Set<string>
  pinealPriorities: Map<string, number>

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
