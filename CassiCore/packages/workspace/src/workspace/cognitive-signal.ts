/**
 * CognitiveSignal — The unit of workspace competition.
 *
 * Every cognitive module submits CognitiveSignals to the Global Workspace.
 * Signals are scored on luminance (salience) and compete for limited
 * workspace slots. Only signals that cross the ignition threshold enter
 * consciousness — the rest remain unconscious, processed locally by
 * their producing module but never reaching the LLM.
 *
 * This is the system-level generalization of Constellation's Spark type.
 * Where Sparks represent branch-level discoveries within a Constellation,
 * CognitiveSignals represent module-level contributions to the global
 * cognitive context.
 *
 * Inspired by Global Workspace Theory (Baars, 1988): specialist processors
 * compete for access to a capacity-limited broadcast medium.
 */


/**
 * Signal categories produced by cognitive modules.
 * Maps to the functional role of the signal in the workspace.
 */
export type SignalType =
  | 'insight'       // Thinker, Heart: strategic realization or deep inference
  | 'observation'   // Subconscious: pattern detected across events
  | 'warning'       // Optimizer, SmartRules: problem or risk detected
  | 'memory'        // Memory retrieval: relevant past experience surfaced
  | 'tension'       // Dialectic: contradiction or conflict found
  | 'convergence'   // CognitiveBridge: cross-session agreement
  | 'suggestion'    // Optimizer, Reflex: behavioral guidance
  | 'context'       // Session-digest, Blackboard: background information
  | 'enrichment'    // RadianceLoop: novelty/external observation


/**
 * System-level luminance score — four dimensions of salience.
 *
 * Adapted from Constellation's LuminanceScore. The fourth dimension
 * changes from `qualityDelta` (branch trajectory) to `sourceCredibility`
 * (learned module trustworthiness), creating a feedback loop where
 * modules that produce useful signals gain influence over time.
 */
export interface SystemLuminanceScore {
  /** 0-1: Is this information new relative to what's already in the workspace? */
  novelty: number
  /** 0-1: How time-sensitive? Warnings score high, background context low. */
  urgency: number
  /** 0-1: How many active sessions / processing contexts benefit? */
  relevance: number
  /** 0-1: Track record of this source producing useful signals. Learned from feedback. */
  sourceCredibility: number
  /** 0-1: Alignment with current cognitive state — focus terms, cortex resonance. */
  cognitiveResonance: number
  /** 0-1: Enduring significance — user decisions, cross-topic landmarks, error anchors. */
  strategicImportance: number
  /** Weighted composite — the actual competition score. */
  composite: number
}


/**
 * Weights for combining luminance dimensions into the composite score.
 * System level weights urgency slightly higher than Locus (0.30 vs 0.25)
 * because system-level signals have broader impact.
 */
export interface SystemLuminanceWeights {
  novelty: number
  urgency: number
  relevance: number
  sourceCredibility: number
}

export const DEFAULT_LUMINANCE_WEIGHTS: SystemLuminanceWeights = {
  novelty: 0.25,
  urgency: 0.30,
  relevance: 0.25,
  sourceCredibility: 0.20,
}


/**
 * Base urgency by signal type. Modules can add urgency hints on top.
 */
export const BASE_URGENCY: Record<SignalType, number> = {
  warning: 0.85,
  tension: 0.75,
  insight: 0.60,
  convergence: 0.55,
  observation: 0.50,
  suggestion: 0.45,
  enrichment: 0.40,
  memory: 0.35,
  context: 0.30,
}


/**
 * A cognitive signal submitted by a module to the Global Workspace.
 */
export interface CognitiveSignal {
  /** Unique identifier for this signal */
  signalId: string
  /** Module that produced this signal (e.g. 'thinker', 'subconscious') */
  source: string
  /** Session this signal applies to (or '*' for global signals) */
  sessionId: string
  /** Functional category */
  type: SignalType
  /** The actual payload — what the module wants to communicate */
  content: string
  /** Luminance score (set by the workspace's luminance scorer) */
  luminance: SystemLuminanceScore
  /** Coalition IDs this signal has joined (populated by workspace) */
  coalitionIds?: string[]
  /** When this signal was created */
  createdAt: number
  /** Optional urgency hint from the module (added to base urgency) */
  urgencyHint?: number
  /** Module-specific metadata for downstream tracing */
  metadata?: Record<string, unknown>
}


/**
 * A workspace slot — one position in the capacity-limited workspace.
 */
export interface WorkspaceSlot {
  /** Slot index (0-based) */
  index: number
  /** The signal occupying this slot, or null if empty */
  signal: CognitiveSignal | null
  /** When this slot was occupied */
  occupiedSince: number | null
  /** How many ticks this signal has occupied the slot */
  occupancyTicks: number
  /** If this slot was eclipsed, the ID of the signal that was displaced */
  eclipsedSignalId?: string
}


/**
 * Configuration for the Global Workspace.
 */
export interface GlobalWorkspaceConfig {
  /** Number of signal slots (workspace capacity). Default: 7 */
  slots: number
  /** Minimum composite luminance for competition entry. Default: 0.25 */
  ignitionThreshold: number
  /** Total character budget for workspace content. Default: 16000 */
  totalBudget: number
  /** Per-slot character budget. Default: 4000 */
  slotBudget: number
  /** Eclipse margin — new signal must exceed incumbent by this. Default: 0.05 */
  eclipseMargin: number
  /** Max ticks before occupancy decay forces eclipse. Default: 8 */
  maxOccupancyTicks: number
  /** Enable adaptive threshold. Default: true */
  adaptiveThreshold: boolean
  /** Adaptive threshold bounds */
  thresholdMin: number
  thresholdMax: number
  /** Luminance scoring weights */
  weights: SystemLuminanceWeights
  /** Enable coalition detection. Default: true */
  coalitionsEnabled: boolean
  /** Enable feedback tracking. Default: true */
  feedbackEnabled: boolean
  /** Inject attention schema into LLM context. Default: false */
  injectAttentionSchema: boolean
}

export const DEFAULT_WORKSPACE_CONFIG: GlobalWorkspaceConfig = {
  slots: 7,
  ignitionThreshold: 0.25,
  totalBudget: 16_000,
  slotBudget: 4_000,
  eclipseMargin: 0.05,
  maxOccupancyTicks: 8,
  adaptiveThreshold: true,
  thresholdMin: 0.15,
  thresholdMax: 0.60,
  weights: DEFAULT_LUMINANCE_WEIGHTS,
  coalitionsEnabled: true,
  feedbackEnabled: true,
  injectAttentionSchema: false,
}
