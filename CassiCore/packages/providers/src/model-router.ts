/**
 * Model Router — Purpose-based model selection with budget awareness.
 *
 * Selects the optimal provider/model for each request type by considering:
 * 1. The purpose of the request (user-facing vs. background intelligence)
 * 2. Current budget usage tier (normal → cautious → frugal → critical)
 * 3. Cost classification (free vs. metered vs. local)
 *
 * Core principle: user-facing requests never degrade. Background tasks
 * are progressively offloaded to free models as budget depletes.
 */

import { getModelSpec, MODEL_DEFAULTS } from '@cassicore/foundation'

import { type BudgetTracker, type BudgetTier } from './budget-tracker.js'
import { getCostClassifier, type RequestCost } from './cost-classifier.js'

import type { ILogger } from '@cassicore/foundation'


/**
 * The purpose of an LLM request, used to determine routing priority.
 *
 * - 'user-facing'  — main turn response to the user (never degraded)
 * - 'dialectic'    — Yang/Yin/Serenity analysis
 * - 'thinker'      — background meta-reflection
 * - 'archival'     — memory analysis for archival
 * - 'background'   — other background tasks (search planning, entity extraction)
 */
export type RequestPurpose =
  | 'user-facing'
  | 'dialectic'
  | 'thinker'
  | 'archival'
  | 'background'

/**
 * Routing decision returned by the model router.
 */
export interface RoutingDecision {
  /** The fully-qualified model spec to use (e.g., 'github-copilot/gpt-5-mini') */
  model: string
  /** Why this model was chosen */
  reason: string
  /** The cost classification of the chosen model */
  cost: RequestCost
  /** Whether the request was downgraded from the preferred model */
  downgraded: boolean
  /** Whether the request should be skipped entirely (budget critical + non-essential) */
  skip: boolean
}


/**
 * The free model to use for offloading background tasks.
 * Must be classified as 'free' by the CostClassifier.
 */
const FREE_OFFLOAD_MODEL = 'github-copilot/gpt-5-mini'

/**
 * Routing table: for each (purpose, budget tier), what model to use.
 *
 * 'preferred' = use the caller's requested model
 * 'free'      = use FREE_OFFLOAD_MODEL
 * 'skip'      = skip the request entirely
 * 'heuristic' = fall back to non-LLM heuristic (caller handles this)
 */
type RouteAction = 'preferred' | 'free' | 'skip' | 'heuristic'

const ROUTING_TABLE: Record<RequestPurpose, Record<BudgetTier, RouteAction>> = {
  'user-facing': {
    normal:   'preferred',
    cautious: 'preferred',
    frugal:   'preferred',
    critical: 'preferred',  // Never degrade user-facing
  },
  'dialectic': {
    normal:   'preferred',
    cautious: 'free',
    frugal:   'free',
    critical: 'skip',
  },
  'thinker': {
    normal:   'preferred',
    cautious: 'free',
    frugal:   'skip',
    critical: 'skip',
  },
  'archival': {
    normal:   'free',       // Always use free model for archival
    cautious: 'free',
    frugal:   'free',
    critical: 'heuristic',  // Fall back to non-LLM analysis
  },
  'background': {
    normal:   'free',       // Background tasks default to free
    cautious: 'free',
    frugal:   'free',
    critical: 'skip',
  },
}


export class ModelRouter {
  private readonly logger: ILogger
  private readonly classifier = getCostClassifier()
  private budgetTracker: BudgetTracker | undefined

  constructor(logger: ILogger, budgetTracker?: BudgetTracker) {
    this.logger = logger
    this.budgetTracker = budgetTracker
  }

  /**
   * Set the budget tracker (allows deferred wiring after construction).
   */
  setBudgetTracker(tracker: BudgetTracker): void {
    this.budgetTracker = tracker
  }

  /**
   * Resolve the best model for a given request purpose.
   *
   * @param purpose     Why the request is being made
   * @param preferred   The caller's preferred model (e.g., from config or user request)
   * @returns           Routing decision with the model to use
   */
  resolve(purpose: RequestPurpose, preferred?: string): RoutingDecision {
    const preferredModel = preferred ?? getModelSpec('reasoning')

    // Determine budget tier from the provider in the preferred model
    const preferredProviderId = preferredModel.split('/')[0]
    const tier = this.budgetTracker?.getTier(preferredProviderId) ?? 'normal'

    // Look up the routing action
    const action = ROUTING_TABLE[purpose]?.[tier] ?? 'preferred'

    switch (action) {
      case 'preferred': {
        const cost = this.classifier.classify(preferredModel)
        return {
          model: preferredModel,
          reason: `${purpose} @ ${tier} tier → preferred model`,
          cost,
          downgraded: false,
          skip: false,
        }
      }
      case 'free': {
        const cost = this.classifier.classify(FREE_OFFLOAD_MODEL)
        const downgraded = preferredModel !== FREE_OFFLOAD_MODEL
        if (downgraded) {
          this.logger.debug('ModelRouter: offloading to free model', {
            purpose, tier, preferred: preferredModel, resolved: FREE_OFFLOAD_MODEL,
          })
        }
        return {
          model: FREE_OFFLOAD_MODEL,
          reason: `${purpose} @ ${tier} tier → free offload`,
          cost,
          downgraded,
          skip: false,
        }
      }
      case 'heuristic':
        return {
          model: preferredModel,
          reason: `${purpose} @ ${tier} tier → heuristic fallback (no LLM)`,
          cost: 'free',
          downgraded: true,
          skip: false,
        }
      case 'skip':
        this.logger.info('ModelRouter: skipping request due to budget', {
          purpose, tier, preferred: preferredModel,
        })
        return {
          model: preferredModel,
          reason: `${purpose} @ ${tier} tier → skipped (budget)`,
          cost: 'metered',
          downgraded: true,
          skip: true,
        }
      default:
        return {
          model: preferredModel,
          reason: `${purpose} → fallback to preferred`,
          cost: this.classifier.classify(preferredModel),
          downgraded: false,
          skip: false,
        }
    }
  }

  /**
   * Convenience: resolve and return just the model string (or null if skipped).
   */
  resolveModel(purpose: RequestPurpose, preferred?: string): string | null {
    const decision = this.resolve(purpose, preferred)
    return decision.skip ? null : decision.model
  }

  /**
   * Get current budget tier for a provider.
   */
  getCurrentTier(providerId: string): BudgetTier {
    return this.budgetTracker?.getTier(providerId) ?? 'normal'
  }

  /**
   * Get the free offload model spec.
   */
  getFreeModel(): string {
    return FREE_OFFLOAD_MODEL
  }

  /**
   * Get the routing table (for diagnostics / admin API).
   */
  getRoutingTable(): typeof ROUTING_TABLE {
    return ROUTING_TABLE
  }
}


let _defaultRouter: ModelRouter | undefined

export function getModelRouter(logger?: ILogger, budgetTracker?: BudgetTracker): ModelRouter {
  if (!_defaultRouter) {
    if (!logger) throw new Error('ModelRouter not initialized — provide a logger on first call')
    _defaultRouter = new ModelRouter(logger, budgetTracker)
  }
  return _defaultRouter
}

export function createModelRouter(logger: ILogger, budgetTracker?: BudgetTracker): ModelRouter {
  _defaultRouter = new ModelRouter(logger, budgetTracker)
  return _defaultRouter
}
