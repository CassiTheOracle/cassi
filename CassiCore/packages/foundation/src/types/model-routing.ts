/**
 * Model Directive Types
 *
 * Central model/provider selection for all LLM operations (Lumen, Teams,
 * intelligence modules, etc.). Instead of specifying provider/model per-tool-call,
 * a single routing directive controls which model is used, with layered scopes
 * for override control and dotted-hierarchy slots for per-component granularity.
 *
 * Complementary to the existing ModelRouter (budget-based routing in
 * core/providers/model-router.ts):
 * - ModelDirective: "What provider+model should be used?" (scope overrides)
 * - ModelRouter: "Given budget, should I degrade or skip?" (cost awareness)
 */


/** A resolved provider + model pair */
export interface ModelConfig {
  provider: string
  model: string
}

/** Routing scope determines lifetime and priority of an override */
export type RoutingScope = 'next' | 'next-job' | 'job' | 'default'

/**
 * Named tiers ranked by capability/cost.
 *
 * | Tier       | Provider       | Model            | Character                  |
 * |------------|----------------|------------------|----------------------------|
 * | fast       | alibaba-coding | MiniMax-M2.5     | Fastest, lightweight       |
 * | swift      | alibaba-coding | qwen3.5-plus     | Fast, decent reasoning     |
 * | standard   | alibaba-coding | glm-5            | Solid mid-range            |
 * | balanced   | alibaba-coding | kimi-k2.5        | Best mid-tier reasoning    |
 * | premium    | copilot-sdk    | claude-opus-4.6  | Complex, high-stakes       |
 * | background | github-copilot | gpt-4o           | Unlimited, every-turn      |
 */
export type RoutingTier = 'fast' | 'swift' | 'standard' | 'balanced' | 'premium' | 'background'


/** Input schema for the model_directive MCP tool */
export interface ModelDirectiveInput {
  action: 'set' | 'get' | 'clear'
  scope: RoutingScope

  /** Named tier (alternative to raw provider+model) */
  tier?: RoutingTier

  /** Raw provider ID (e.g. "alibaba-coding", "copilot-sdk") */
  provider?: string

  /** Raw model name (e.g. "kimi-k2.5", "claude-opus-4.6") */
  model?: string

  /** Team or Lumen session ID — required for scope="job" */
  jobId?: string

  /**
   * Dotted-hierarchy slot for per-component granularity.
   * Examples: "lumen.yang", "lumen.yin", "lumen.executive",
   *           "dialectic.yang", "dialectic.yin", "thinker", "subconscious"
   *
   * When set, the override only applies to that specific slot.
   * Without a slot, the override applies to all slots at that scope.
   */
  slot?: string
}

/** Output from model_directive get action */
export interface ModelDirectiveState {
  /** The effective routing after resolution */
  effective: ModelConfig
  /** What set the effective routing (includes slot qualifier if applicable) */
  source: 'next' | 'next:slot' | 'next-job' | 'next-job:slot' | 'job:slot' | 'job' | 'default:slot' | 'default' | 'hardcoded'
  /** Current next-call override, if any */
  next: ModelConfig | null
  /** Pending next-job overrides (accumulated per-slot, consumed when next job starts) */
  nextJob: Record<string, ModelConfig> | null
  /** Job override for the specified jobId, if any */
  job: ModelConfig | null
  /** Persistent default from config */
  default: ModelConfig
  /** All active job overrides */
  activeJobs: Record<string, ModelConfig>
}


/** Interface for the central model directive */
export interface IModelDirective {
  /**
   * Set routing at a given scope.
   * For scope="next", consumed after the next LLM operation.
   * For scope="next-job", accumulated per-slot and consumed when the next job starts.
   * For scope="job", scoped to a team/lumen session ID.
   * For scope="default", persisted in daemon config.
   *
   * If `slot` is provided, the override only applies to that slot.
   * Without a slot, the override applies to all slots at that scope.
   */
  set(scope: RoutingScope, config: ModelConfig, jobId?: string, slot?: string): void

  /**
   * Resolve the effective routing.
   * Priority: next:slot > next > job:slot > job > default:slot > default > hardcoded.
   *
   * @param jobId - Team or Lumen session ID for job-scoped resolution
   * @param slot - Dotted-hierarchy slot (e.g. "lumen.yang", "thinker")
   */
  resolve(jobId?: string, slot?: string): ModelConfig

  /** Get the full directive state for diagnostics */
  getState(jobId?: string): ModelDirectiveState

  /** Clear an override at the given scope */
  clear(scope: RoutingScope, jobId?: string, slot?: string): void

  /** Remove all job-scoped overrides for a job (called when a team completes/cancels) */
  clearJob(jobId: string): void

  /**
   * Consume next-job overrides by transferring them to job-scoped overrides.
   * Called by Lumen/Dyad/Team at job startup so the models are available from iteration 1.
   * Returns the number of entries transferred.
   */
  consumeNextJob(jobId: string): number

  /** Resolve a named tier to a ModelConfig */
  resolveTier(tier: RoutingTier): ModelConfig

  /** List available tiers with their current mappings */
  listTiers(): Record<RoutingTier, ModelConfig>

  /** Validate that a provider is available in the daemon */
  validateProvider(provider: string): { valid: boolean; error?: string }
}
