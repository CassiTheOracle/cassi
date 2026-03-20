/**
 * Cost Classifier — Categorizes provider/model combinations by billing model.
 *
 * Request-based providers (like GitHub Copilot) charge per request regardless of
 * size, while token-based providers charge per token. Some models on request-based
 * providers are exempt from quota (e.g., gpt-5-mini on Copilot). Local models
 * have no cost at all.
 *
 * This classification drives the ModelRouter's decisions about where to send
 * background intelligence tasks to minimize premium request burn.
 */


/**
 * How a model is billed:
 * - 'free'     — does not count toward any quota (e.g., gpt-5-mini on Copilot)
 * - 'local'    — runs locally, zero network cost
 * - 'metered'  — counts against a request or token budget
 */
export type RequestCost = 'free' | 'metered' | 'local'

/**
 * A cost rule maps a provider/model pattern to a cost classification.
 * Patterns support simple glob: 'provider/*' matches any model on that provider.
 * Rules are evaluated first-match-wins, so specific rules must come before wildcards.
 */
export interface CostRule {
  /** Pattern like 'github-copilot/gpt-5-mini' or 'lmstudio/*' */
  pattern: string
  /** Cost classification */
  cost: RequestCost
}


/**
 * Default cost rules — ordered from most specific to least specific.
 * First match wins. Override via runtime config 'providers.costRules'.
 */
export const DEFAULT_COST_RULES: CostRule[] = [
  // Free models on metered providers (unlimited — no premium request cost)
  { pattern: 'github-copilot/gpt-5-mini',  cost: 'free' },
  { pattern: 'github-copilot/gpt-4o',      cost: 'free' },
  { pattern: 'github-copilot/gpt-4.1',     cost: 'free' },
  { pattern: 'github-copilot/gpt-4.1-mini', cost: 'free' },

  // Copilot SDK — metered but tool loops count as single premium request
  { pattern: 'copilot-sdk/gpt-5-mini',     cost: 'free' },
  { pattern: 'copilot-sdk/gpt-4o',         cost: 'free' },
  { pattern: 'copilot-sdk/gpt-4.1',        cost: 'free' },
  { pattern: 'copilot-sdk/gpt-4.1-mini',   cost: 'free' },
  { pattern: 'copilot-sdk/*',              cost: 'metered' },

  // Local providers — no network cost
  { pattern: 'lmstudio/*',  cost: 'local' },

  // Metered providers — everything else on these costs money/quota
  { pattern: 'github-copilot/*', cost: 'metered' },
  { pattern: 'kimi-coding/*',    cost: 'metered' },
  { pattern: 'openrouter/*',     cost: 'metered' },
  { pattern: 'qwen/*',           cost: 'metered' },
  { pattern: 'qwen-coder/*',     cost: 'metered' },
  { pattern: 'google-antigravity/*', cost: 'metered' },

  // Catch-all: unknown providers are assumed metered
  { pattern: '*/*', cost: 'metered' },
  { pattern: '*',   cost: 'metered' },
]


export class CostClassifier {
  private readonly rules: CostRule[]
  /** Cache: 'provider/model' → RequestCost */
  private readonly cache = new Map<string, RequestCost>()

  constructor(rules?: CostRule[]) {
    this.rules = rules ?? DEFAULT_COST_RULES
  }

  /**
   * Classify a fully-qualified model spec (e.g., 'github-copilot/claude-sonnet-4.5').
   * Returns 'metered' if no rule matches.
   */
  classify(providerModel: string): RequestCost {
    const cached = this.cache.get(providerModel)
    if (cached !== undefined) return cached

    const result = this.match(providerModel)
    this.cache.set(providerModel, result)
    return result
  }

  /**
   * Check whether a model spec is free (free or local).
   */
  isFree(providerModel: string): boolean {
    const cost = this.classify(providerModel)
    return cost === 'free' || cost === 'local'
  }

  /**
   * Check whether a model spec counts against a metered quota.
   */
  isMetered(providerModel: string): boolean {
    return this.classify(providerModel) === 'metered'
  }

  /**
   * Get the current ruleset (for diagnostics / admin API).
   */
  getRules(): readonly CostRule[] {
    return this.rules
  }


  private match(providerModel: string): RequestCost {
    for (const rule of this.rules) {
      if (matchPattern(rule.pattern, providerModel)) {
        return rule.cost
      }
    }
    return 'metered'
  }
}


/**
 * Simple glob match supporting '*' as wildcard segment.
 * - 'github-copilot/gpt-5-mini' matches exactly 'github-copilot/gpt-5-mini'
 * - 'github-copilot/*'           matches 'github-copilot/anything'
 * - 'lmstudio/*'                 matches 'lmstudio/anything'
 * - '*\/*'                       matches 'anything/anything'
 * - '*'                          matches everything
 */
function matchPattern(pattern: string, value: string): boolean {
  if (pattern === '*') return true

  // Split both by '/' and compare segments
  const patternParts = pattern.split('/')
  const valueParts = value.split('/')

  if (patternParts.length !== valueParts.length) {
    // Special case: single '*' already handled above
    return false
  }

  for (let i = 0; i < patternParts.length; i++) {
    const pp = patternParts[i]
    const vp = valueParts[i]
    if (pp === '*') continue
    if (pp !== vp) return false
  }

  return true
}


let _defaultClassifier: CostClassifier | undefined

/**
 * Get or create the default cost classifier singleton.
 * Override rules by passing custom rules on first call.
 * @dep callers: budget-tracker.ts (core/providers/budget-tracker.ts), model-router.ts (core/providers/model-router.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function getCostClassifier(rules?: CostRule[]): CostClassifier {
  if (!_defaultClassifier || rules) {
    _defaultClassifier = new CostClassifier(rules)
  }
  return _defaultClassifier
}
