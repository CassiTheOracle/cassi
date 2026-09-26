/**
 * DreamerConfig — configuration for the Dreamer cognitive module.
 * Self-contained local type (foundation is the shared substrate and must not
 * depend on @cassicore/dreamer-reverie-subconscious, which itself depends on
 * foundation — a package cycle would make the workspace unbuildable). Shape
 * matches core/intelligence/dreamer/types.ts's DreamerConfig; re-pointed back
 * to the real @cassicore/dreamer-reverie-subconscious at P7 host wiring.
 */
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
