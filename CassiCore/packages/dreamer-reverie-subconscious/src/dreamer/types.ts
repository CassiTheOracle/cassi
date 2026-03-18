/**
 * Dreamer — Type Definitions
 *
 * The Dreamer module processes memory archives during idle periods to form
 * novel cross-session insights and maintain a curated active memory garden.
 */

// ─── Configuration ───────────────────────────────────────────────────────────

export interface DreamerConfig {
  /** Whether the dreamer is active. Default: true */
  enabled: boolean
  /** How often (ms) to check if idle and dream. Default: 300_000 (5 min) */
  checkIntervalMs: number
  /** Must be idle (no turns) for this long (ms) before dreaming. Default: 600_000 (10 min) */
  idleThresholdMs: number
  /** Number of archive entries to sample per dream. Default: 40 */
  archiveSampleSize: number
  /** Max age (days) of entries eligible for random deep sampling. Default: 30 */
  archiveLookbackDays: number
  /** Guaranteed-fresh window (hours) — always sample from this range. Default: 24 */
  recentWindowHours: number
  /** Max new insight memories created per dream. Default: 5 */
  maxInsightsPerDream: number
  /** Min cluster size of episodics needed to distill + retire them. Default: 3 */
  minClusterSizeForGarden: number
  /** Create archive_links between conceptually related entries. Default: true */
  enableLinking: boolean
  /** Distill episodic clusters → semantic insights and retire originals. Default: true */
  enableGardening: boolean
  /** Inject recent dream insights into turn context. Default: true */
  injectContextEnabled: boolean
  /** A dream insight must be newer than this many hours to be injected. Default: 4 */
  injectContextWindowHours: number
  /** Optional model spec override (e.g. "github-copilot/gpt-4o"). Falls back to module default. */
  model?: string
}

export const DEFAULT_DREAMER_CONFIG: DreamerConfig = {
  enabled: true,
  checkIntervalMs: 300_000,
  idleThresholdMs: 600_000,
  archiveSampleSize: 40,
  archiveLookbackDays: 30,
  recentWindowHours: 24,
  maxInsightsPerDream: 5,
  minClusterSizeForGarden: 3,
  enableLinking: true,
  enableGardening: true,
  injectContextEnabled: true,
  injectContextWindowHours: 4,
}

// ─── Dream Artifacts ─────────────────────────────────────────────────────────

/** A single insight distilled during a dream cycle. */
export interface DreamInsight {
  /** Concise semantic insight content. */
  content: string
  /** Confidence in the insight (0–1). */
  confidence: number
  /** IDs of archive entries that contributed to this insight. */
  sourceEntryIds: string[]
  /** Topics this insight relates to. */
  topics?: string[]
  /** Optional title / label. */
  title?: string
}

/**
 * A cluster of related episodic memories that have been distilled into a
 * semantic insight. The episodics are eligible for deep-archive retirement.
 */
export interface GardenCluster {
  /** Memory IDs of the episodic entries to retire. */
  episodicIds: string[]
  /** The memory ID of the new synthesized insight. */
  synthesizedInsightId: string
  /** Human-readable reasoning for why the originals were retired. */
  reasoning: string
}

/** Full record of a completed dream cycle (stored as archive entry). */
export interface DreamRecord {
  id: string
  startedAt: number
  completedAt: number
  durationMs: number
  /** IDs of archive entries that were sampled for this dream. */
  archiveEntriesProcessed: string[]
  /** Memory IDs of newly created insight entries. */
  insightsCreated: string[]
  /** Memory IDs of episodic memories retired to the deep archive. */
  episodicsRetired: string[]
  /** Number of archive_links created. */
  linksCreated: number
  /** The raw free-association text from Phase 2 (trimmed to 2,000 chars for storage). */
  rawAnalysis?: string
  /**
   * Content of the highest-confidence insight from this cycle.
   * Used for direct context injection without a follow-up memory query.
   */
  topInsightContent?: string
}

/** Serialized form stored in the archive entry metadata. */
export type DreamRecordMeta = Omit<DreamRecord, 'id'>

// ─── Dream Engine Inputs ─────────────────────────────────────────────────────

export interface DreamSampleOpts {
  sampleSize: number
  recentWindowHours: number
  lookbackDays: number
}

export interface CrystallizeOpts {
  maxInsights: number
  sourceEntries: Array<{ id: string; type: string; content: string }>
}

export interface GardenOpts {
  minClusterSize: number
  episodicMemories: Array<{ id: string; content: string; cognitiveClass?: string }>
  insights: DreamInsight[]
}
