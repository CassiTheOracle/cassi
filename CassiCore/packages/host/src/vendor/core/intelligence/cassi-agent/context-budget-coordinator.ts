/**
 * ContextBudgetCoordinator — Session-level context budget tracking for multi-agent systems.
 *
 * Manages per-posture context budgets and provides the IntelligentContextWindow
 * scoring algorithm to BasePostureRunner.manageContextPressure().
 *
 * Created per pipeline session (e.g., per Dyad run, per Lumen analysis) and
 * shared across all posture agents in that session.
 *
 * Architecture:
 *   Pipeline (Dyad/Lumen/Helix)
 *     └─ ContextBudgetCoordinator (one per session)
 *         ├─ ICW instance (shared scoring engine, no SessionIndexer needed)
 *         ├─ PostureBudget('yang')  — tracks Yang's context usage
 *         ├─ PostureBudget('yin')   — tracks Yin's context usage
 *         └─ PostureBudget('apex')  — tracks Apex's context usage
 */

import type { ILogger } from '@cassicore/foundation'
import { IntelligentContextWindow } from '../context-window/index.js'
import { estimateChars } from '../shared/token-estimation.js'



export interface PostureBudgetConfig {
  /** Maximum context window characters for this posture (default: 350K chars ≈ 100K tokens) */
  maxContextChars: number
  /** Maximum characters per individual tool result (default: 12,000) */
  maxToolResultChars: number
  /** Maximum total accumulated tool output characters across ALL tool calls (default: 200,000) */
  maxTotalToolOutputChars: number
  /** ICW scoring weight overrides for this posture */
  weights?: Partial<{ recency: number; relevance: number }>
  /** Anchor turns to always keep from the head (default: 2) */
  anchorTurns?: number
  /** Anchor turns to always keep from the tail (default: 3) */
  tailAnchorTurns?: number
}

export interface PostureBudgetSnapshot {
  role: string
  toolCallCount: number
  totalToolOutputChars: number
  maxTotalToolOutputChars: number
  budgetUsedPct: number
  overBudget: boolean
}

/** Default configs per posture role */
const DEFAULT_POSTURE_CONFIGS: Record<string, Partial<PostureBudgetConfig>> = {
  // Yang/Unity = primary worker, reads lots of files — generous tool budget
  // 1M tokens = 3.7M chars at 3.7 chars/token
  yang: {
    maxContextChars: 3_700_000,       // 1M tokens
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_500_000,
    weights: { recency: 0.45, relevance: 0.55 },
    anchorTurns: 2,
    tailAnchorTurns: 4,
  },
  unity: {
    maxContextChars: 3_700_000,       // 1M tokens
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_500_000,
    weights: { recency: 0.45, relevance: 0.55 },
    anchorTurns: 2,
    tailAnchorTurns: 4,
  },
  // Yin = reviewer/refiner — moderate tool budget, higher relevance weight
  yin: {
    maxContextChars: 3_700_000,       // 1M tokens
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_000_000,
    weights: { recency: 0.40, relevance: 0.60 },
    anchorTurns: 2,
    tailAnchorTurns: 3,
  },
  // Apex/Executive = overseer — smaller budget, balanced scoring
  apex: {
    maxContextChars: 3_700_000,       // 1M tokens
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_000_000,
    weights: { recency: 0.50, relevance: 0.50 },
    anchorTurns: 2,
    tailAnchorTurns: 3,
  },
  executive: {
    maxContextChars: 3_700_000,       // 1M tokens
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_000_000,
    weights: { recency: 0.50, relevance: 0.50 },
    anchorTurns: 2,
    tailAnchorTurns: 3,
  },
}

const FALLBACK_CONFIG: PostureBudgetConfig = {
  maxContextChars: 300_000,
  maxToolResultChars: 12_000,
  maxTotalToolOutputChars: 200_000,
  weights: { recency: 0.50, relevance: 0.50 },
  anchorTurns: 2,
  tailAnchorTurns: 3,
}



class PostureBudget {
  readonly role: string
  readonly config: PostureBudgetConfig

  private _toolCallCount = 0
  private _totalToolOutputChars = 0

  constructor(role: string, config: PostureBudgetConfig) {
    this.role = role
    this.config = config
  }

  /** Record a tool output's character count */
  recordToolOutput(chars: number): void {
    this._toolCallCount++
    this._totalToolOutputChars += chars
  }

  /** Whether the posture has exceeded its total tool output budget */
  get overBudget(): boolean {
    return this._totalToolOutputChars > this.config.maxTotalToolOutputChars
  }

  /** Percentage of tool output budget used */
  get budgetUsedPct(): number {
    return Math.round((this._totalToolOutputChars / this.config.maxTotalToolOutputChars) * 100)
  }

  /** Effective max chars for a single tool result — shrinks when budget is running low */
  get effectiveMaxToolResultChars(): number {
    const remaining = this.config.maxTotalToolOutputChars - this._totalToolOutputChars
    if (remaining <= 0) return 2_000 // Minimum — still allow short results
    // When >80% budget used, start shrinking individual tool results
    const budgetPct = this._totalToolOutputChars / this.config.maxTotalToolOutputChars
    if (budgetPct > 0.8) {
      return Math.max(2_000, Math.round(this.config.maxToolResultChars * (1 - budgetPct)))
    }
    return this.config.maxToolResultChars
  }

  snapshot(): PostureBudgetSnapshot {
    return {
      role: this.role,
      toolCallCount: this._toolCallCount,
      totalToolOutputChars: this._totalToolOutputChars,
      maxTotalToolOutputChars: this.config.maxTotalToolOutputChars,
      budgetUsedPct: this.budgetUsedPct,
      overBudget: this.overBudget,
    }
  }
}



export class ContextBudgetCoordinator {
  private readonly icw: IntelligentContextWindow
  private readonly postures = new Map<string, PostureBudget>()
  private readonly logger: ILogger

  constructor(logger: ILogger, configOverrides?: Record<string, Partial<PostureBudgetConfig>>) {
    this.logger = logger
    // Create ICW without SessionIndexer — for scoring-only use
    this.icw = new IntelligentContextWindow(undefined, logger)
    if (configOverrides) {
      for (const [role, config] of Object.entries(configOverrides)) {
        this.getOrCreatePosture(role, config)
      }
    }
  }

  /** Get or create a posture budget tracker */
  getOrCreatePosture(role: string, overrides?: Partial<PostureBudgetConfig>): PostureBudget {
    let posture = this.postures.get(role)
    if (!posture) {
      const defaults = DEFAULT_POSTURE_CONFIGS[role] ?? {}
      const config: PostureBudgetConfig = {
        ...FALLBACK_CONFIG,
        ...defaults,
        ...overrides,
        weights: { ...FALLBACK_CONFIG.weights, ...defaults.weights, ...overrides?.weights },
      }
      posture = new PostureBudget(role, config)
      this.postures.set(role, posture)
    }
    return posture
  }

  /** Get the shared ICW instance for scoring */
  getICW(): IntelligentContextWindow {
    return this.icw
  }

  /** Get per-posture config (creates if needed) */
  getPostureConfig(role: string): PostureBudgetConfig {
    return this.getOrCreatePosture(role).config
  }

  /** Record a tool output for a posture */
  recordToolOutput(role: string, chars: number): void {
    this.getOrCreatePosture(role).recordToolOutput(chars)
  }

  /** Get effective max tool result chars for a posture (shrinks as budget fills) */
  getEffectiveMaxToolResultChars(role: string): number {
    return this.getOrCreatePosture(role).effectiveMaxToolResultChars
  }

  /** Check if a posture is over its tool output budget */
  isOverBudget(role: string): boolean {
    return this.getOrCreatePosture(role).overBudget
  }

  /** Get snapshot of all posture budgets */
  snapshot(): PostureBudgetSnapshot[] {
    return Array.from(this.postures.values()).map(p => p.snapshot())
  }
}
