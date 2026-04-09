/**
 * Locus Bridge Types — Persistent attentional context assembly
 *
 * Bridge-adapted versions of Constellation's Locus types, designed for
 * session-level attention rather than multi-branch orchestration.
 *
 * The Bridge Locus maintains 5 capacity-limited foci that track what
 * the system is paying attention to across the session. These foci
 * drive context assembly: curated memories, code, signals, and
 * dynamically-scored history turns.
 */

// Spark types — what kind of content enters the attentional workspace

/**
 * Bridge spark types — session events rather than branch digests.
 */
export type BridgeSparkType =
  | 'user-intent'              // Parsed from user prompt
  | 'tool-discovery'           // Significant tool result (file reads, searches)
  | 'memory-recall'            // Memory surfaced by enrichment
  | 'code-reference'           // Code file referenced or modified
  | 'constellation-radiance'   // Forwarded from active Constellation
  | 'compaction-recovery'      // Focus state preserved across compaction


/**
 * A BridgeSpark is a proposal from a session event competing for focus.
 * Adapted from Constellation's Spark: uses session context instead of
 * branch topology.
 */
export interface BridgeSpark {
  sparkId: string
  /** Session that produced this spark */
  sourceSessionId: string
  /** The content being proposed for attentional focus */
  content: string
  /** What kind of content this is */
  type: BridgeSparkType
  /** Composite salience score determining competition outcome */
  luminance: BridgeLuminanceScore
  /** When this spark was generated */
  sparkedAt: number
  /** Current task/intent at spark time */
  sourceGoal: string
  /** Files relevant to this spark */
  relevantFiles: string[]
}


/**
 * Bridge luminance scoring — adapted for session context.
 * Uses relevance (to active files/queries) instead of crossRelevance
 * (topology distances), and sourceCredibility from GlobalWorkspace.
 */
export interface BridgeLuminanceScore {
  /** 0-1: How new compared to current foci content */
  novelty: number
  /** 0-1: How time-sensitive (base by spark type) */
  urgency: number
  /** 0-1: Overlap with active files/queries */
  relevance: number
  /** 0-1: From GlobalWorkspace credibility tracking */
  sourceCredibility: number
  /** Weighted combination — the competition score */
  composite: number
}

/**
 * Weights for bridge luminance scoring.
 */
export interface BridgeLuminanceWeights {
  novelty: number
  urgency: number
  relevance: number
  sourceCredibility: number
}

export const DEFAULT_BRIDGE_LUMINANCE_WEIGHTS: BridgeLuminanceWeights = {
  novelty: 0.30,
  urgency: 0.30,
  relevance: 0.20,
  sourceCredibility: 0.20,
}


// Focus — Bridge-adapted workspace slots

/**
 * A BridgeFocus is a single slot in the bridge's attentional workspace.
 * Same structure as Constellation's Focus but typed for BridgeSpark.
 */
export interface BridgeFocus {
  slotIndex: number
  spark: BridgeSpark | null
  occupiedSince: number | null
  occupancyTicks: number
  eclipsedSparkId?: string
}


// Kindling Events — spark entering workspace

/**
 * Records a bridge spark entering the attentional workspace.
 */
export interface BridgeKindlingEvent {
  eventId: string
  spark: BridgeSpark
  slotIndex: number
  eclipse: BridgeEclipseEvent | null
  kindlingLuminance: number
  timestamp: number
}

/**
 * Records when a new spark displaces an existing focus occupant.
 */
export interface BridgeEclipseEvent {
  eclipsedSpark: BridgeSpark
  eclipsingSpark: BridgeSpark
  luminanceDelta: number
  occupancyAtEclipse: number
}


// Configuration

export interface LocusBridgeConfig {
  enabled: boolean
  /** Number of focus slots (workspace capacity). Default: 5 */
  foci: number
  /** Minimum luminance for a spark to compete. Default: 0.25 */
  kindlingThreshold: number
  /** Max ticks before natural focus expiry. Default: 15 */
  maxOccupancyTicks: number
  /** Hysteresis margin for eclipse. Default: 0.05 */
  eclipseMargin: number

  /** Total token budget for assembled window. Default: 100_000 */
  tokenBudget: number
  /** Reserve for system prompt (SOUL + AGENTS + base). Default: 15_000 */
  systemPromptReserve: number
  /** Soft cap for curated context. Default: 30_000 */
  curatedContextMax: number
  /** Minimum history tokens (always keep at least this). Default: 10_000 */
  historyMinTokens: number
  /** Minimum number of most-recent messages to always keep regardless of score. Default: 20 */
  recentWindowMinMessages: number

  /** Max memory results per focus. Default: 10 */
  memoryRetrievalLimit: number
  /** Max code results per focus. Default: 5 */
  codeRetrievalLimit: number

  luminanceWeights: BridgeLuminanceWeights
  /** Max events to keep in history. Default: 100 */
  maxEventHistory: number
}

export const DEFAULT_LOCUS_BRIDGE_CONFIG: LocusBridgeConfig = {
  enabled: true,
  foci: 5,
  kindlingThreshold: 0.25,
  maxOccupancyTicks: 15,
  eclipseMargin: 0.05,
  tokenBudget: 100_000,
  systemPromptReserve: 15_000,
  curatedContextMax: 30_000,
  historyMinTokens: 10_000,
  recentWindowMinMessages: 20,
  memoryRetrievalLimit: 10,
  codeRetrievalLimit: 5,
  luminanceWeights: DEFAULT_BRIDGE_LUMINANCE_WEIGHTS,
  maxEventHistory: 100,
}


// Curated Context — retrieved content for system prompt

export interface CuratedMemory {
  content: string
  source: string
  score: number
}

export interface CuratedCode {
  path: string
  content: string
  lines?: [number, number]
}

export interface CuratedSignal {
  content: string
  source: string
}

export interface CuratedContext {
  /** Summary of current attentional focus */
  focusSummary: string
  /** Retrieved memories relevant to current foci */
  memories: CuratedMemory[]
  /** Code snippets relevant to current foci */
  code: CuratedCode[]
  /** Intelligence signals (thinker insights, anomalies, etc.) */
  signals: CuratedSignal[]
  /** Estimated token count of all curated content */
  totalTokens: number
}


// History Scoring

export interface ScoredTurn {
  /** Index in the original messages array */
  messageIndex: number
  /** Composite score (0-1) */
  score: number
  /** Which task segment this turn belongs to */
  taskId: string
  /** Whether this turn is in the current task */
  isCurrentTask: boolean
  /** Estimated token count of this turn */
  estimatedTokens: number
}


// Assembled Window — the final output

export interface AssembledWindow {
  /** Curated content blocks for system prompt injection */
  systemContext: string[]
  /** Selected history turns (original message format, re-ordered) */
  messages: any[]
  /** Assembly metadata for debugging and feedback */
  meta: AssemblyMeta
}

export interface AssemblyMeta {
  tokenBudget: number
  systemPromptTokens: number
  curatedContextTokens: number
  historyTokens: number
  turnsIncluded: number
  turnsDropped: number
  keptMessageIndices: number[]
  fociSnapshot: Array<{ slotIndex: number; content: string | null; luminance: number }>
  taskBoundaries: number[]
  assembledAt: number
}


// Bridge Snapshot — full state for inspection

export interface LocusBridgeSnapshot {
  foci: BridgeFocus[]
  recentKindlings: BridgeKindlingEvent[]
  totalSparksProcessed: number
  totalKindlings: number
  kindlingRate: number
  taskBoundaries: number[]
  lastAssemblyMeta: AssemblyMeta | null
  snapshotAt: number
}


// Persistence — serialized state for KV store

export interface LocusBridgePersistedState {
  foci: BridgeFocus[]
  kindlingHistory: BridgeKindlingEvent[]
  totalSparksProcessed: number
  totalKindlings: number
  taskBoundaries: number[]
  lastAssemblyMeta: AssemblyMeta | null
  persistedAt: number
}
