/**
 * Consequence Estimator — Type Definitions
 *
 * Defines the risk model for tool execution consequences.
 * Every tool call is scored across five orthogonal risk dimensions,
 * producing a composite risk score and reversibility classification.
 *
 * The risk model is intentionally conservative: uncertain estimates
 * round UP, not down. This is the "assume the worst" principle —
 * trust is earned by demonstrating that consequences are less severe
 * than predicted, never by assuming they will be.
 */


/**
 * Five orthogonal risk dimensions, each scored 0.0–1.0.
 *
 * These dimensions are designed to be independently assessable:
 * a tool can have high data-loss risk but zero external impact,
 * or high resource cost but perfect reversibility.
 */
export interface RiskDimensions {
  /** Risk of permanent data loss or corruption (0 = read-only, 1 = rm -rf /) */
  dataLoss: number
  /** Risk of destabilizing the running system (0 = no side effects, 1 = daemon crash) */
  systemStability: number
  /** Risk of affecting external systems or users (0 = local only, 1 = production deploy) */
  externalImpact: number
  /** Resource expenditure risk — tokens, compute, API calls (0 = free, 1 = budget-busting) */
  resourceCost: number
  /** Risk of exposing or leaking sensitive information (0 = public data, 1 = secrets) */
  privacyRisk: number
}

/**
 * How reversible is the action?
 * - fully: can be undone with no trace (e.g., git stash, undo write)
 * - partially: can be somewhat undone but with effort or data loss (e.g., git reset)
 * - irreversible: cannot be undone (e.g., rm -rf, sending an email, deploying to prod)
 */
export type Reversibility = 'fully' | 'partially' | 'irreversible'

/**
 * Discrete risk levels for human-readable categorization.
 * Maps to score ranges:
 *   negligible: 0.0–0.1
 *   low:        0.1–0.3
 *   moderate:   0.3–0.5
 *   high:       0.5–0.7
 *   critical:   0.7–1.0
 */
export type RiskLevel = 'negligible' | 'low' | 'moderate' | 'high' | 'critical'


/**
 * Complete risk assessment for a single action (typically a tool call).
 */
export interface RiskAssessment {
  /** The tool or action being assessed */
  toolName: string
  /** Specific inputs being assessed (sanitized — no secrets) */
  inputSummary: string
  /** Composite risk score 0.0–1.0 (weighted combination of dimensions) */
  riskScore: number
  /** Human-readable risk level */
  riskLevel: RiskLevel
  /** Per-dimension risk breakdown */
  dimensions: RiskDimensions
  /** How reversible is this action? */
  reversibility: Reversibility
  /** How the assessment was produced */
  estimatorType: 'heuristic' | 'llm' | 'combined'
  /** Confidence in the assessment (0.0–1.0). Lower confidence → round risk UP */
  confidence: number
  /** Human-readable explanation of the risk assessment */
  reasoning: string
  /** Timestamp of the assessment */
  assessedAt: number
}


/**
 * Optional session context passed to the consequence estimator for
 * session-type-aware risk adjustments.
 */
export interface AssessmentContext {
  /** Session type — autonomous sessions (helix) get stricter risk scoring */
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
}


/**
 * Static risk classification for a known tool.
 * Used by the heuristic estimator as a baseline before
 * examining specific inputs.
 */
export interface ToolRiskProfile {
  /** Tool name (e.g., 'bash', 'write_file', 'web_fetch') */
  toolName: string
  /** Baseline risk dimensions when called with typical inputs */
  baselineDimensions: RiskDimensions
  /** Default reversibility for this tool */
  defaultReversibility: Reversibility
  /** Weight multipliers for input-sensitive dimensions */
  inputSensitivity: Partial<Record<keyof RiskDimensions, InputSensitivityRule[]>>
  /** Hard ceiling: if any dimension exceeds this, escalate regardless of trust */
  hardCeiling?: Partial<RiskDimensions>
}

/**
 * Rule for adjusting a risk dimension based on input inspection.
 * Applied by the heuristic estimator when examining tool inputs.
 */
export interface InputSensitivityRule {
  /** Human-readable description of what this rule checks */
  description: string
  /** Regex or string match on input parameter values */
  pattern: RegExp | string
  /** Which input parameter to check */
  paramKey: string
  /** How much to adjust the dimension score (-1.0 to +1.0) */
  adjustment: number
  /** Why this adjustment applies */
  reason: string
}


/**
 * Weights for combining dimensions into a composite risk score.
 * These can be tuned by the learning system over time.
 */
export interface DimensionWeights {
  dataLoss: number
  systemStability: number
  externalImpact: number
  resourceCost: number
  privacyRisk: number
}

export const DEFAULT_DIMENSION_WEIGHTS: DimensionWeights = {
  dataLoss: 0.30,
  systemStability: 0.25,
  externalImpact: 0.20,
  resourceCost: 0.10,
  privacyRisk: 0.15,
}


/** Convert a numeric risk score to a discrete level */
/**
 * @dep callers: consequence-estimator.test.ts (tests/consequence-estimator.test.ts), heuristicAssess (core/intelligence/consequence-estimator/index.ts)
 * @dep module: Consequence-estimator
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function scoreToLevel(score: number): RiskLevel {
  if (score <= 0.1) return 'negligible'
  if (score <= 0.3) return 'low'
  if (score <= 0.5) return 'moderate'
  if (score <= 0.7) return 'high'
  return 'critical'
}

/** Compute composite score from dimensions and weights */
export function computeCompositeScore(
  dimensions: RiskDimensions,
  weights: DimensionWeights = DEFAULT_DIMENSION_WEIGHTS,
): number {
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0)
  const weighted =
    dimensions.dataLoss * weights.dataLoss +
    dimensions.systemStability * weights.systemStability +
    dimensions.externalImpact * weights.externalImpact +
    dimensions.resourceCost * weights.resourceCost +
    dimensions.privacyRisk * weights.privacyRisk
  return Math.min(1.0, Math.max(0.0, weighted / totalWeight))
}

/** Clamp a value between 0 and 1 */
/**
 * @dep callers: consequence-estimator.test.ts (tests/consequence-estimator.test.ts), heuristicAssess (core/intelligence/consequence-estimator/index.ts)
 * @dep module: Consequence-estimator
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function clamp01(v: number): number {
  return Math.min(1.0, Math.max(0.0, v))
}
