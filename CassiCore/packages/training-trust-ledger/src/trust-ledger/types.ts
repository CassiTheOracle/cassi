/**
 * Trust Ledger — Type Definitions
 *
 * The Trust Ledger maintains per-domain Bayesian trust scores that aggregate
 * evidence from across the system: outcome tracking, feedback detection,
 * consequence accuracy, and explicit human signals.
 *
 * Trust is domain-specific: competence at file operations doesn't grant
 * trust for network operations. Each domain accumulates its own evidence.
 *
 * The Bayesian model uses a Beta distribution:
 *   - α (alpha) = successful outcomes + prior
 *   - β (beta) = failed outcomes + prior
 *   - trust score = α / (α + β) (posterior mean)
 *   - confidence = 1 - variance = α + β (more evidence → higher confidence)
 *
 * This means trust starts at 0.5 (uninformative prior) and converges
 * toward the true success rate as evidence accumulates. A single failure
 * after 100 successes barely dents trust, while a failure after 2 successes
 * drops it significantly. This is exactly the behavior we want.
 */


/**
 * Pre-defined trust domains corresponding to categories of actions.
 * New domains can be created dynamically, but these are the canonical ones.
 */
export type CanonicalDomain =
  | 'file-read'         // Reading files, searching, grepping
  | 'file-write'        // Writing, editing, creating files
  | 'file-delete'       // Deleting files or directories
  | 'shell-execution'   // Running shell commands
  | 'network-fetch'     // HTTP requests, web fetching
  | 'git-operations'    // Git commands (commit, push, branch)
  | 'system-config'     // Modifying system or daemon configuration
  | 'memory-operations' // Memory store, search, delete
  | 'agent-management'  // Spawning agents, managing teams
  | 'provider-routing'  // Choosing or switching LLM providers

/** Trust domain can be canonical or a custom string */
export type TrustDomain = CanonicalDomain | string


/**
 * A trust score for a single domain.
 * Uses the Beta-Binomial Bayesian model.
 */
export interface TrustScore {
  /** The domain this score applies to */
  domain: TrustDomain
  /** Beta distribution α parameter (successes + prior) */
  alpha: number
  /** Beta distribution β parameter (failures + prior) */
  beta: number
  /** Posterior mean: α / (α + β). This is the "trust score" (0.0–1.0) */
  score: number
  /** Confidence in the score: 1 - variance. Higher = more evidence */
  confidence: number
  /** Total evidence count (α + β - prior) */
  evidenceCount: number
  /** Last time this score was updated */
  lastUpdatedAt: number
  /** Last time evidence was added */
  lastEvidenceAt: number
  /** Last time decay was applied */
  lastDecayAt: number
}


/**
 * A piece of evidence that updates a trust score.
 * Evidence can be positive (success) or negative (failure),
 * with an optional weight to control the strength of the update.
 */
export interface TrustEvidence {
  /** Which domain this evidence applies to */
  domain: TrustDomain
  /** Was the action successful? */
  success: boolean
  /** Weight of this evidence (default 1.0). Use < 1.0 for weak signals */
  weight: number
  /** Source of this evidence (e.g., 'outcome-tracker', 'feedback', 'human') */
  source: string
  /** Description of what happened */
  description: string
  /** How accurately did the consequence estimator predict the outcome? (0.0–1.0) */
  consequenceAccuracy?: number
  /** Session where this occurred */
  sessionId?: string
  /** Unix timestamp */
  timestamp: number
}


/**
 * Configuration for the Trust Ledger.
 */
export interface TrustLedgerConfig {
  /** Whether the trust ledger is enabled */
  enabled: boolean
  /** Prior α for new domains (default 1.0 — weak prior at 0.5) */
  priorAlpha: number
  /** Prior β for new domains (default 1.0 — weak prior at 0.5) */
  priorBeta: number
  /** Time-based decay factor per hour (default 0.999 — very slow decay) */
  decayFactorPerHour: number
  /** Minimum decay interval in ms (don't decay more often than this) */
  minDecayIntervalMs: number
  /** Maximum evidence weight from any single event */
  maxEvidenceWeight: number
  /** How much consequence accuracy affects trust updates */
  consequenceAccuracyWeight: number
}

export const DEFAULT_TRUST_LEDGER_CONFIG: TrustLedgerConfig = {
  enabled: true,
  priorAlpha: 1.0,
  priorBeta: 1.0,
  decayFactorPerHour: 0.999,
  minDecayIntervalMs: 60_000, // 1 minute
  maxEvidenceWeight: 3.0,
  consequenceAccuracyWeight: 0.5,
}


/**
 * Graduated autonomy levels based on overall trust.
 *
 * These map to progressively broader permission thresholds:
 *   supervised  (trust < 0.3): human approval for everything
 *   guided      (trust 0.3–0.6): auto-approve low risk, escalate moderate+
 *   autonomous  (trust 0.6–0.85): auto-approve up to moderate risk
 *   trusted     (trust > 0.85): auto-approve up to high risk (critical always escalates)
 */
export type AutonomyLevel = 'supervised' | 'guided' | 'autonomous' | 'trusted'

/**
 * @dep callers: trust-ledger.test.ts (tests/trust-ledger.test.ts), getSummary (core/intelligence/trust-ledger/index.ts), judge (core/intelligence/permission-oracle/index.ts)
 * @dep module: Trust-ledger
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function trustToAutonomyLevel(score: number): AutonomyLevel {
  if (score < 0.3) return 'supervised'
  if (score < 0.6) return 'guided'
  if (score < 0.85) return 'autonomous'
  return 'trusted'
}


/**
 * Aggregated trust summary across all domains.
 */
export interface TrustSummary {
  /** Per-domain trust scores */
  domains: Map<TrustDomain, TrustScore>
  /** Weighted average trust across all domains */
  overallScore: number
  /** Current autonomy level based on overall score */
  autonomyLevel: AutonomyLevel
  /** Total evidence across all domains */
  totalEvidence: number
  /** Most trusted domain */
  strongestDomain?: { domain: TrustDomain; score: number }
  /** Least trusted domain */
  weakestDomain?: { domain: TrustDomain; score: number }
}


/** Compute the posterior mean of a Beta distribution */
/**
 * @dep callers: trust-ledger.test.ts (tests/trust-ledger.test.ts), maybeApplyDecay (core/intelligence/trust-ledger/index.ts), createDomain (core/intelligence/trust-ledger/index.ts), recordEvidence (core/intelligence/trust-ledger/index.ts)
 * @dep module: Trust-ledger
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function betaMean(alpha: number, beta: number): number {
  return alpha / (alpha + beta)
}

/** Compute the variance of a Beta distribution */
export function betaVariance(alpha: number, beta: number): number {
  const total = alpha + beta
  return (alpha * beta) / (total * total * (total + 1))
}

/** Compute confidence as 1 - normalized variance (higher = more confident) */
/**
 * @dep callers: trust-ledger.test.ts (tests/trust-ledger.test.ts), maybeApplyDecay (core/intelligence/trust-ledger/index.ts), createDomain (core/intelligence/trust-ledger/index.ts), recordEvidence (core/intelligence/trust-ledger/index.ts)
 * @dep module: Trust-ledger
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function betaConfidence(alpha: number, beta: number): number {
  // Confidence based on total evidence: more evidence → higher confidence
  // At prior (alpha=1, beta=1): total=2, confidence=0
  // At total=12 (10 evidence): confidence ≈ 0.83
  // At total=102 (100 evidence): confidence ≈ 0.98
  const total = alpha + beta
  const evidence = total - 2 // Subtract prior (alpha_0=1, beta_0=1)
  if (evidence <= 0) return 0
  return 1 - 1 / (1 + evidence * 0.1)
}
