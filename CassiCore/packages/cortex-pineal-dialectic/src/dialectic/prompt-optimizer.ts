/**
 * PromptOptimizer — Epsilon-greedy prompt variant selection with quality feedback.
 *
 * Each dialectic observer (Yang, Yin, Serenity) has multiple prompt variants.
 * The optimizer selects among them using epsilon-greedy (exploit best, explore random)
 * and updates variant scores via EMA after each dialectic turn completes.
 *
 * Persistence: variant scores saved to JSON file for cross-session learning.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';

import {
  YANG_VARIANTS,
  YIN_CRITIQUE_VARIANTS,
  YIN_BASELINE_VARIANTS,
  SERENITY_VARIANTS,
  ALL_VARIANTS,
} from './prompt-templates.js';

import type {
  PromptVariant,
  PromptVariantScore,
  PromptQualityFeedback,
  PromptOptimizerConfig,
  PromptOptimizerState,
  PromptObserverRole,
} from '../../../types/dialectic.js';
import type { ILogger } from '../../../types/interfaces.js';

// ─── Default Config ─────────────────────────────────────────────────────────

const DEFAULT_CONFIG: PromptOptimizerConfig = {
  enabled: true,
  epsilon: 0.2,
  alpha: 0.3,
  minUsesForExploitation: 3,
  persistPath: '',  // Set at construction time
};

const STATE_VERSION = 1;

// ─── PromptOptimizer ────────────────────────────────────────────────────────

export class PromptOptimizer {
  private readonly logger: ILogger;
  private readonly config: PromptOptimizerConfig;
  private readonly variants: Map<string, PromptVariant> = new Map();
  private readonly scores: Map<string, PromptVariantScore> = new Map();
  private totalTurns = 0;
  private dirty = false;
  private persistTimer: ReturnType<typeof setInterval> | null = null;

  /**
   * Track which variant was last selected per observer, so callers
   * can report feedback without needing to know the variant IDs.
   */
  private lastSelected: Map<PromptObserverRole, string> = new Map();

  constructor(logger: ILogger, config?: Partial<PromptOptimizerConfig>) {
    this.logger = logger;
    this.config = { ...DEFAULT_CONFIG, ...config };

    // Register all built-in variants
    for (const v of ALL_VARIANTS) {
      this.variants.set(v.id, v);
    }

    // Initialize scores for all variants
    for (const v of ALL_VARIANTS) {
      this.scores.set(v.id, {
        variantId: v.id,
        observer: v.observer,
        score: 0.5,  // neutral starting score
        uses: 0,
        lastUsedAt: 0,
      });
    }
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────────

  /**
   * Load persisted scores from disk and start auto-save timer.
   */
  async init(): Promise<void> {
    if (!this.config.enabled) return;

    if (this.config.persistPath) {
      await this.loadState();
    }

    // Auto-persist every 60s if dirty
    this.persistTimer = setInterval(() => {
      if (this.dirty) {
        this.saveState().catch(err => {
          this.logger.warn('PromptOptimizer: auto-save failed', { error: String(err) });
        });
      }
    }, 60_000);

    this.logger.info('PromptOptimizer: initialized', {
      variants: this.variants.size,
      persistPath: this.config.persistPath || '(none)',
      epsilon: this.config.epsilon,
    });
  }

  /**
   * Flush state to disk and stop timers.
   */
  async stop(): Promise<void> {
    if (this.persistTimer) {
      clearInterval(this.persistTimer);
      this.persistTimer = null;
    }
    if (this.dirty && this.config.persistPath) {
      await this.saveState();
    }
  }

  // ─── Selection ──────────────────────────────────────────────────────────

  /**
   * Select a Yang prompt variant (for observe() single-call mode).
   */
  selectYang(): PromptVariant {
    return this.select(YANG_VARIANTS);
  }

  /**
   * Select a Yin critique prompt variant (for critiquing Yang branches).
   */
  selectYinCritique(): PromptVariant {
    return this.select(YIN_CRITIQUE_VARIANTS);
  }

  /**
   * Select a Yin baseline prompt variant (for parallel mode independent analysis).
   */
  selectYinBaseline(): PromptVariant {
    return this.select(YIN_BASELINE_VARIANTS);
  }

  /**
   * Select a Serenity dual synthesis prompt variant.
   */
  selectSerenity(): PromptVariant {
    return this.select(SERENITY_VARIANTS);
  }

  /**
   * Get the last selected variant ID for an observer role.
   * Used by the feedback system to attribute quality back to variants.
   */
  getLastSelected(observer: PromptObserverRole): string | undefined {
    return this.lastSelected.get(observer);
  }

  /**
   * Epsilon-greedy selection from a pool of variants.
   */
  private select(pool: PromptVariant[]): PromptVariant {
    if (!this.config.enabled || pool.length === 0) {
      const fallback = pool[0] ?? Array.from(this.variants.values())[0];
      return fallback;
    }

    if (pool.length === 1) {
      this.lastSelected.set(pool[0].observer, pool[0].id);
      return pool[0];
    }

    // Explore: random variant
    if (Math.random() < this.config.epsilon) {
      const idx = Math.floor(Math.random() * pool.length);
      const selected = pool[idx];
      this.lastSelected.set(selected.observer, selected.id);
      this.logger.debug('PromptOptimizer: explore', { selected: selected.id });
      return selected;
    }

    // Exploit: pick highest-scoring variant that has enough uses
    let best: PromptVariant = pool[0];
    let bestScore = -1;

    for (const variant of pool) {
      const scoreEntry = this.scores.get(variant.id);
      if (!scoreEntry) continue;

      // If variant hasn't been used enough, treat it as exploration candidate
      if (scoreEntry.uses < this.config.minUsesForExploitation) {
        // Bonus for under-explored variants (optimistic initialization)
        const explorationBonus = 1.0 - (scoreEntry.uses / this.config.minUsesForExploitation) * 0.5;
        if (explorationBonus > bestScore) {
          bestScore = explorationBonus;
          best = variant;
        }
      } else if (scoreEntry.score > bestScore) {
        bestScore = scoreEntry.score;
        best = variant;
      }
    }

    this.lastSelected.set(best.observer, best.id);
    this.logger.debug('PromptOptimizer: exploit', { selected: best.id, score: bestScore.toFixed(3) });
    return best;
  }

  // ─── Feedback ───────────────────────────────────────────────────────────

  /**
   * Record quality feedback from a completed dialectic turn.
   * Updates variant scores using exponential moving average (EMA).
   */
  recordFeedback(feedback: PromptQualityFeedback): void {
    if (!this.config.enabled) return;

    const compositeScore = this.computeCompositeScore(feedback);

    // Update Yang variant
    this.updateScore(feedback.selectedVariants.yang, compositeScore);

    // Update Yin variant
    this.updateScore(feedback.selectedVariants.yin, compositeScore);

    // Update Serenity variant
    this.updateScore(feedback.selectedVariants.serenity, compositeScore);

    this.totalTurns++;
    this.dirty = true;

    this.logger.debug('PromptOptimizer: feedback recorded', {
      turn: this.totalTurns,
      compositeScore: compositeScore.toFixed(3),
      yang: feedback.selectedVariants.yang,
      yin: feedback.selectedVariants.yin,
      serenity: feedback.selectedVariants.serenity,
    });
  }

  /**
   * Compute a composite quality score (0-1) from dialectic turn metrics.
   *
   * Weights:
   *   - synthesisConfidence: 0.35 (Serenity's overall judgment)
   *   - dialecticTension:    0.25 (diversity of thought — we want healthy tension)
   *   - yangYinAgreement:    0.20 (convergence signal)
   *   - signal bonus:        0.20 (did the turn produce an actionable signal?)
   */
  computeCompositeScore(feedback: PromptQualityFeedback): number {
    const { yangYinAgreement, dialecticTension, synthesisConfidence, hasSignal } = feedback.quality;
    const signalBonus = hasSignal ? 1.0 : 0.0;

    return (
      synthesisConfidence * 0.35 +
      dialecticTension * 0.25 +
      yangYinAgreement * 0.20 +
      signalBonus * 0.20
    );
  }

  /**
   * Update a single variant's EMA score.
   */
  private updateScore(variantId: string, compositeScore: number): void {
    const entry = this.scores.get(variantId);
    if (!entry) return;

    const alpha = this.config.alpha;
    // EMA: new_score = alpha * observation + (1 - alpha) * old_score
    entry.score = alpha * compositeScore + (1 - alpha) * entry.score;
    entry.uses++;
    entry.lastUsedAt = Date.now();
  }

  // ─── Metrics ────────────────────────────────────────────────────────────

  /**
   * Get all variant scores for a given observer role.
   */
  getScores(observer?: PromptObserverRole): PromptVariantScore[] {
    const all = Array.from(this.scores.values());
    if (observer) {
      return all.filter(s => s.observer === observer);
    }
    return all;
  }

  /**
   * Get the total number of turns processed.
   */
  getTotalTurns(): number {
    return this.totalTurns;
  }

  /**
   * Get a snapshot of the current state for diagnostics.
   */
  getState(): PromptOptimizerState {
    const scores: Record<string, PromptVariantScore> = {};
    for (const [id, entry] of Array.from(this.scores.entries())) {
      scores[id] = { ...entry };
    }
    return {
      version: STATE_VERSION,
      scores,
      totalTurns: this.totalTurns,
      lastUpdatedAt: Date.now(),
    };
  }

  // ─── Variant Management ─────────────────────────────────────────────────

  /**
   * Register a custom variant (e.g., from config or LLM-generated mutations).
   */
  registerVariant(variant: PromptVariant): void {
    this.variants.set(variant.id, variant);
    if (!this.scores.has(variant.id)) {
      this.scores.set(variant.id, {
        variantId: variant.id,
        observer: variant.observer,
        score: 0.5,
        uses: 0,
        lastUsedAt: 0,
      });
    }
    this.logger.info('PromptOptimizer: variant registered', { id: variant.id, observer: variant.observer });
  }

  /**
   * Get a variant by ID.
   */
  getVariant(id: string): PromptVariant | undefined {
    return this.variants.get(id);
  }

  /**
   * Check if the optimizer is enabled.
   */
  get enabled(): boolean {
    return this.config.enabled;
  }

  // ─── Persistence ────────────────────────────────────────────────────────

  /**
   * Load persisted state from disk. Merges with built-in variants
   * (new variants get default scores, removed variants are dropped).
   */
  private async loadState(): Promise<void> {
    if (!this.config.persistPath) return;

    try {
      const raw = await readFile(this.config.persistPath, 'utf-8');
      const state: PromptOptimizerState = JSON.parse(raw);

      if (state.version !== STATE_VERSION) {
        this.logger.warn('PromptOptimizer: state version mismatch, starting fresh', {
          expected: STATE_VERSION,
          found: state.version,
        });
        return;
      }

      // Merge persisted scores into current scores (only for variants that still exist)
      let restored = 0;
      for (const [id, persisted] of Object.entries(state.scores)) {
        if (this.scores.has(id)) {
          const current = this.scores.get(id)!;
          current.score = persisted.score;
          current.uses = persisted.uses;
          current.lastUsedAt = persisted.lastUsedAt;
          restored++;
        }
      }

      this.totalTurns = state.totalTurns || 0;

      this.logger.info('PromptOptimizer: loaded persisted state', {
        restored,
        totalTurns: this.totalTurns,
      });
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
        this.logger.debug('PromptOptimizer: no persisted state found, starting fresh');
      } else {
        this.logger.warn('PromptOptimizer: failed to load state', { error: String(err) });
      }
    }
  }

  /**
   * Save current state to disk.
   */
  private async saveState(): Promise<void> {
    if (!this.config.persistPath) return;

    try {
      const dir = dirname(this.config.persistPath);
      await mkdir(dir, { recursive: true });

      const state = this.getState();
      await writeFile(this.config.persistPath, JSON.stringify(state, null, 2), 'utf-8');
      this.dirty = false;

      this.logger.debug('PromptOptimizer: state persisted', {
        variants: Object.keys(state.scores).length,
        totalTurns: state.totalTurns,
      });
    } catch (err) {
      this.logger.warn('PromptOptimizer: failed to save state', { error: String(err) });
    }
  }
}

// ─── Template Utility ───────────────────────────────────────────────────────

/**
 * Replace `{{key}}` placeholders in a template with values from the vars map.
 * Unknown placeholders are replaced with empty string.
 */
export function fillTemplate(template: string, vars: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => vars[key] ?? '');
}

// ─── Factory ────────────────────────────────────────────────────────────────

export const createPromptOptimizer = (
  logger: ILogger,
  config?: Partial<PromptOptimizerConfig>,
): PromptOptimizer => new PromptOptimizer(logger, config);
