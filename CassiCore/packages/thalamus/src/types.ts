import type { CorticalSignal, SignalType, Affect } from '../cortex/types.js'
import type { CognitiveSignal, SystemLuminanceScore } from '../workspace/cognitive-signal.js'
import type { BridgeFocus } from '../locus-bridge/types.js'



/** The five slot types, one per message category */
export type MessageSlotType = 'user' | 'tool_call' | 'tool_result' | 'assistant' | 'system'

/** Tool-level metadata attached by ToolCallSlot and ToolResultSlot */
export interface ThalamusToolMeta {
  /** Resolved tool name (e.g. 'bash', 'read') */
  name: string
  /** High-level class (e.g. 'shell', 'fs', 'memory', 'orchestration') */
  class: string
  /** Wall-clock execution time in ms (tool_result only) */
  durationMs: number
  /** Raw output byte count (tool_result only) */
  outputBytes: number
  /** Whether the tool reported an error */
  isError: boolean
}

/** Temporal context computed during curation from the TemporalRegistry */
export interface ThalamusTemporalContext {
  /** Milliseconds since the previous message */
  msSincePrevious: number
  /** Milliseconds since the last user message */
  msSinceLastUser: number
  /** Milliseconds since the session started */
  sessionElapsedMs: number
}

/**
 * Structured annotation attached to every message as `msg._thalamus`.
 * Written at processing time (when the message arrives), enriched with
 * temporal context at curation time.
 */
export interface ThalamusAnnotation {
  /** ISO 8601 UTC timestamp when the message was processed */
  ts: string
  /** Which slot processed this message */
  slot: MessageSlotType
  /** Character count of the original message content */
  chars: number
  /** Tool metadata (present on tool_call and tool_result messages) */
  tool?: ThalamusToolMeta
  /** Temporal context (populated lazily during curation) */
  temporal?: ThalamusTemporalContext
  /** Whether this is a code-heavy assistant message */
  hasCode?: boolean
  /** Source tag for system messages (e.g. 'pineal', 'context-injection') */
  source?: string
}

/** Context passed to slot.augment() during real-time processing */
export interface SlotContext {
  /** Current ISO 8601 timestamp */
  timestamp: string
  /** When the session started */
  sessionStart: string
  /** Timestamp of the most recent user message, or null */
  lastUserMessageAt: string | null
  /** tool_use_id → { durationMs, outputBytes } recorded by the executor */
  toolMetrics: Map<string, { durationMs: number; outputBytes: number }>
  /** tool_use_id → tool name, built from preceding tool_use blocks */
  toolUseMap: Map<string, string>
  /** Timestamp of the immediately preceding message, or null */
  previousMessageTs: string | null
}

/**
 * Strategy interface for a message processing slot.
 * One implementation per MessageSlotType.
 */
export interface MessageSlot {
  readonly type: MessageSlotType

  /** Does this message belong to this slot? */
  matches(msg: any): boolean

  /** Attach type-specific metadata. Returns a new message with _thalamus. */
  augment(msg: any, ctx: SlotContext): any

  /** Type-specific compression during curation. Returns compressed message. */
  compress(msg: any, annotation: ThalamusAnnotation, maxChars: number): any

  /**
   * Adjust luminance scores using typed metadata.
   * Returns a new score with type-specific adjustments applied.
   */
  adjustScore(score: SystemLuminanceScore, annotation: ThalamusAnnotation): SystemLuminanceScore

  /**
   * Render a compact prefix for LLM-facing context.
   * Returns empty string if no prefix is needed for this slot type.
   */
  renderPrefix(annotation: ThalamusAnnotation): string
}

/** Per-type budget fractions for curation assembly (must sum to ≤ 1.0) */
export interface SlotBudgets {
  user: number
  tool_call: number
  tool_result: number
  assistant: number
  system: number
}

export const DEFAULT_SLOT_BUDGETS: SlotBudgets = {
  system: 1.0,        // always retained (budget is uncapped)
  user: 0.40,         // instructions are king
  tool_result: 0.30,  // ground truth from tools
  assistant: 0.20,    // least credible, most compressible
  tool_call: 0.10,    // mostly structural
}



export interface CurationConfig {
  charBudget: number
  recentWindowSize: number
  toolResultMaxChars: number
  ignitionThreshold: number
  excludeSessionPrefixes: string[]
  /** Per-type budget allocation fractions */
  slotBudgets: SlotBudgets
}

export const DEFAULT_CURATION_CONFIG: CurationConfig = {
  charBudget: 120_000,
  recentWindowSize: 6,
  toolResultMaxChars: 2000,
  ignitionThreshold: 0.20,
  excludeSessionPrefixes: ['meditation:', 'module:', 'helix-review:'],
  slotBudgets: DEFAULT_SLOT_BUDGETS,
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
  /** tool_use_id → tool name, accumulated across the session */
  toolUseMap: Map<string, string>
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
