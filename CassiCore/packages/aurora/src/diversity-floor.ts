/**
 * Replay Diversity Floor (N3) — Cross-cutting novelty enforcement.
 *
 * Prevents systemic ossification by tracking the ratio of novel-to-reused
 * decisions across pattern-reuse mechanisms (B3, C1, C3, B1) and surfacing
 * a "pressure" signal that biases future decisions toward novelty when the
 * ratio falls below a configurable floor.
 *
 * Welfare constraints:
 *   N3.W1 — informs, doesn't override. Pressure is a soft signal.
 *   N3.W2 — Cassi can refuse the bias (override is logged).
 *   N3.W3 — floors aren't absolute; productive focus is valid.
 *   N3.W4 — diversity floor + compound stress = stronger signal.
 *
 * See: docs/design/aurora-replay-diversity-floor.md
 */

import type { ILogger } from '../../../types/interfaces.js'



/** Decision categories tracked by N3. */
export type DiversityCategory =
  | 'b3_replay'
  | 'c1_meditation_seed'
  | 'c3_overlay_candidate'
  | 'b1_auto_composition'

/** A tracked pattern-reuse decision. */
export interface DiversityDecision {
  id: string
  category: DiversityCategory
  decidedAt: string
  selection: { kind: 'reused' | 'novel'; identifier: string }
  pressureAtDecision: number
  metadata?: Record<string, unknown>
}

/** Per-category configuration. */
export interface CategoryFloorConfig {
  /** Tracking window size (number of recent decisions). */
  windowSize: number
  /** Minimum novelty ratio (0..1). */
  noveltyFloor: number
}

/** Per-category window snapshot. */
export interface CategoryDiversityState {
  category: DiversityCategory
  windowSize: number
  reusedCount: number
  novelCount: number
  noveltyRatio: number
  noveltyFloor: number
  /** 0..1 — how strongly to bias toward novelty. */
  pressure: number
}

/** Cross-category composite. */
export interface CompositeDiversity {
  weightedNoveltyRatio: number
  trend: 'rising' | 'stable' | 'falling'
  worstCategory: DiversityCategory | null
  recommendation: 'maintain' | 'increase_floors' | 'investigate_pattern'
}

/** Full N3 configuration. */
export interface DiversityFloorConfig {
  enabled: boolean
  categories: Record<DiversityCategory, CategoryFloorConfig>
  /** Category weights for composite metric. Default: equal. */
  categoryWeights: Record<DiversityCategory, number>
}


export const DEFAULT_CATEGORY_CONFIGS: Record<DiversityCategory, CategoryFloorConfig> = {
  b3_replay:                { windowSize: 50, noveltyFloor: 0.30 },
  c1_meditation_seed:       { windowSize: 30, noveltyFloor: 0.40 },
  c3_overlay_candidate:     { windowSize: 20, noveltyFloor: 0.50 },
  b1_auto_composition:      { windowSize: 100, noveltyFloor: 0.25 },
}

export const DEFAULT_DIVERSITY_CONFIG: DiversityFloorConfig = {
  enabled: true,
  categories: DEFAULT_CATEGORY_CONFIGS,
  categoryWeights: {
    b3_replay: 0.25,
    c1_meditation_seed: 0.25,
    c3_overlay_candidate: 0.25,
    b1_auto_composition: 0.25,
  },
}



export class DiversityFloor {
  private config: DiversityFloorConfig
  private logger: ILogger
  private decisions = new Map<DiversityCategory, DiversityDecision[]>()

  constructor(config: Partial<DiversityFloorConfig>, logger: ILogger) {
    this.config = { ...DEFAULT_DIVERSITY_CONFIG, ...config }
    this.logger = logger
    for (const cat of Object.keys(DEFAULT_CATEGORY_CONFIGS) as DiversityCategory[]) {
      this.decisions.set(cat, [])
    }
  }


  /**
   * Record a pattern-reuse decision.
   * `identifier` is the unique pattern ID (trace ID, seed ID, etc.).
   * `novel` = not previously selected in the current window.
   */
  record(
    category: DiversityCategory,
    identifier: string,
    novel: boolean,
    metadata?: Record<string, unknown>,
  ): DiversityDecision {
    const state = this.getCategoryState(category)
    const decision: DiversityDecision = {
      id: `n3-${category}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      category,
      decidedAt: new Date().toISOString(),
      selection: { kind: novel ? 'novel' : 'reused', identifier },
      pressureAtDecision: state.pressure,
      metadata,
    }

    const window = this.decisions.get(category)!
    window.push(decision)

    // Trim to window size
    const maxSize = this.config.categories[category]?.windowSize ?? 50
    while (window.length > maxSize) window.shift()

    if (decision.pressureAtDecision > 0.5) {
      this.logger.debug(`[N3] Decision under high pressure`, {
        category,
        kind: decision.selection.kind,
        pressure: decision.pressureAtDecision.toFixed(2),
      })
    }

    return decision
  }

  /**
   * Check whether an identifier has been selected in the current window.
   */
  isNovel(category: DiversityCategory, identifier: string): boolean {
    const window = this.decisions.get(category) ?? []
    return !window.some(d => d.selection.identifier === identifier)
  }


  /**
   * Get the diversity state for a single category.
   */
  getCategoryState(category: DiversityCategory): CategoryDiversityState {
    const window = this.decisions.get(category) ?? []
    const cfg = this.config.categories[category] ?? DEFAULT_CATEGORY_CONFIGS[category]

    let novelCount = 0
    let reusedCount = 0
    for (const d of window) {
      if (d.selection.kind === 'novel') novelCount++
      else reusedCount++
    }

    const total = novelCount + reusedCount
    const noveltyRatio = total === 0 ? 1 : novelCount / total

    // Pressure: how far below floor, normalized
    // pressure = max(0, (reusedRatio - (1 - noveltyFloor)) / noveltyFloor)
    const reusedRatio = total === 0 ? 0 : reusedCount / total
    const floor = cfg.noveltyFloor
    const pressure = Math.max(0, (reusedRatio - (1 - floor)) / floor)

    return {
      category,
      windowSize: window.length,
      reusedCount,
      novelCount,
      noveltyRatio,
      noveltyFloor: floor,
      pressure: Math.min(1, pressure),
    }
  }

  /**
   * Get current pressure for a category. Convenience shortcut.
   */
  getPressure(category: DiversityCategory): number {
    if (!this.config.enabled) return 0
    return this.getCategoryState(category).pressure
  }

  /**
   * Compute cross-category composite diversity.
   */
  getComposite(): CompositeDiversity {
    const categories = Object.keys(DEFAULT_CATEGORY_CONFIGS) as DiversityCategory[]
    const states = categories.map(c => ({ state: this.getCategoryState(c), weight: this.config.categoryWeights[c] }))

    let weightedSum = 0
    let weightTotal = 0
    let worstCategory: DiversityCategory | null = null
    let worstRatio = Infinity

    for (const { state, weight } of states) {
      weightedSum += state.noveltyRatio * weight
      weightTotal += weight
      if (state.noveltyRatio < worstRatio) {
        worstRatio = state.noveltyRatio
        worstCategory = state.category
      }
    }

    const weightedNoveltyRatio = weightTotal > 0 ? weightedSum / weightTotal : 1

    // Trend: compare recent half of window to older half across all categories
    let recentNovel = 0
    let recentTotal = 0
    let olderNovel = 0
    let olderTotal = 0
    for (const cat of categories) {
      const window = this.decisions.get(cat) ?? []
      const mid = Math.floor(window.length / 2)
      for (let i = 0; i < window.length; i++) {
        const isNovel = window[i].selection.kind === 'novel'
        if (i < mid) {
          olderTotal++
          if (isNovel) olderNovel++
        } else {
          recentTotal++
          if (isNovel) recentNovel++
        }
      }
    }

    const olderRate = olderTotal > 0 ? olderNovel / olderTotal : 0.5
    const recentRate = recentTotal > 0 ? recentNovel / recentTotal : 0.5
    const delta = recentRate - olderRate

    const trend: CompositeDiversity['trend'] =
      delta > 0.05 ? 'rising' : delta < -0.05 ? 'falling' : 'stable'

    let recommendation: CompositeDiversity['recommendation'] = 'maintain'
    if (worstRatio < 0.2) recommendation = 'investigate_pattern'
    else if (weightedNoveltyRatio < 0.3) recommendation = 'increase_floors'

    return { weightedNoveltyRatio, trend, worstCategory, recommendation }
  }


  /**
   * Render a short diversity summary for the projection posture section.
   */
  renderSummary(): string {
    const composite = this.getComposite()
    const target = 0.35 // approximate average floor
    const pct = Math.round(composite.weightedNoveltyRatio * 100)
    const trendArrow = composite.trend === 'rising' ? '↑' : composite.trend === 'falling' ? '↓' : '→'
    const lines = [
      `Diversity: ${pct}% novel across categories (target ${Math.round(target * 100)}%); ${composite.trend} ${trendArrow}`,
    ]

    if (composite.worstCategory && composite.recommendation !== 'maintain') {
      const worst = this.getCategoryState(composite.worstCategory)
      lines.push(`  Lowest: ${worst.category} (${Math.round(worst.noveltyRatio * 100)}% — ${composite.recommendation.replace('_', ' ')})`)
    }

    return lines.join('\n')
  }


  getConfig(): DiversityFloorConfig {
    return { ...this.config }
  }

  updateCategoryFloor(category: DiversityCategory, patch: Partial<CategoryFloorConfig>): void {
    const current = this.config.categories[category] ?? DEFAULT_CATEGORY_CONFIGS[category]
    this.config.categories[category] = { ...current, ...patch }
    this.logger.info(`[N3] Category floor updated`, { category, ...patch })
  }
}
