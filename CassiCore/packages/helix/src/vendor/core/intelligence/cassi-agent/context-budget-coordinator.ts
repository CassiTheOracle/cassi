/**
 * VENDORED — faithful type surface of `core/intelligence/cassi-agent/context-budget-coordinator.ts`.
 * Consumed by helix (helix-pipeline.ts) as `ContextBudgetCoordinator`.
 *
 * Self-contained stub: imports only shared types from `@cassicore/foundation`.
 */
import type { ILogger } from '@cassicore/foundation'

/** Surface of the shared IntelligentContextWindow scoring engine. */
export interface IntelligentContextMessage {
  role?: string
  content: string | unknown[]
}

export interface ICWScoreAndSelectResult<T> {
  messages: T[]
  stats: Record<string, unknown>
}

/**
 * Minimal local surface of the ICW scoring engine — only the members the
 * coordinator and posture runners access.
 */
export class IntelligentContextWindow {
  constructor(_sessionIndexer?: unknown, _logger?: ILogger) {
    // no-op stub — scoring engine is vendored elsewhere
  }

  scoreAndSelect<T extends IntelligentContextMessage>(
    messages: T[],
    query: string,
    _maxChars: number,
    _opts?: { anchorTurns?: number; tailAnchorTurns?: number; weights?: { recency?: number; relevance?: number } },
  ): ICWScoreAndSelectResult<T> {
    // Faithful marker: select up to the whole message set, scoring deferred.
    return { messages, stats: { omitted: 0 } }
  }
}

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
  yang: {
    maxContextChars: 3_700_000,
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_500_000,
    weights: { recency: 0.45, relevance: 0.55 },
    anchorTurns: 2,
    tailAnchorTurns: 4,
  },
  unity: {
    maxContextChars: 3_700_000,
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_500_000,
    weights: { recency: 0.45, relevance: 0.55 },
    anchorTurns: 2,
    tailAnchorTurns: 4,
  },
  yin: {
    maxContextChars: 3_700_000,
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_000_000,
    weights: { recency: 0.40, relevance: 0.60 },
    anchorTurns: 2,
    tailAnchorTurns: 3,
  },
  apex: {
    maxContextChars: 3_700_000,
    maxToolResultChars: 50_000,
    maxTotalToolOutputChars: 2_000_000,
    weights: { recency: 0.50, relevance: 0.50 },
    anchorTurns: 2,
    tailAnchorTurns: 3,
  },
  executive: {
    maxContextChars: 3_700_000,
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

  recordToolOutput(chars: number): void {
    this._toolCallCount++
    this._totalToolOutputChars += chars
  }

  get overBudget(): boolean {
    return this._totalToolOutputChars > this.config.maxTotalToolOutputChars
  }

  get budgetUsedPct(): number {
    return Math.round((this._totalToolOutputChars / this.config.maxTotalToolOutputChars) * 100)
  }

  get effectiveMaxToolResultChars(): number {
    const remaining = this.config.maxTotalToolOutputChars - this._totalToolOutputChars
    if (remaining <= 0) return 2_000
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

  getICW(): IntelligentContextWindow {
    return this.icw
  }

  getPostureConfig(role: string): PostureBudgetConfig {
    return this.getOrCreatePosture(role).config
  }

  recordToolOutput(role: string, chars: number): void {
    this.getOrCreatePosture(role).recordToolOutput(chars)
  }

  getEffectiveMaxToolResultChars(role: string): number {
    return this.getOrCreatePosture(role).effectiveMaxToolResultChars
  }

  isOverBudget(role: string): boolean {
    return this.getOrCreatePosture(role).overBudget
  }

  snapshot(): PostureBudgetSnapshot[] {
    return Array.from(this.postures.values()).map(p => p.snapshot())
  }
}
