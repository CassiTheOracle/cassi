/**
 * Permission Oracle — Trust-adjusted risk gating for tool execution.
 *
 * Priority: 76 (runs after Trust Ledger but before Consequence Estimator's consumers)
 *
 * The Permission Oracle is the final decision-maker for every gated action.
 * It combines:
 *   1. RiskAssessment from the Consequence Estimator
 *   2. TrustScore from the Trust Ledger (domain-specific)
 *   3. Hard gates (non-negotiable safety constraints)
 *
 * Decision logic:
 *   1. Check hard gates first (critical risk, irreversible actions, etc.)
 *   2. Compute effectiveThreshold = baseThreshold × (1 + trustBonus × domainTrust)
 *   3. If riskScore < effectiveThreshold → allow
 *   4. If riskScore ≥ effectiveThreshold → escalate
 *   5. If hard gate fires → escalate or deny (depends on gate)
 *
 * Events emitted:
 *   - permission:decision — every decision with full reasoning trail
 *   - permission:escalated — when a human is asked for approval
 *
 * Events consumed:
 *   - permission:human-response — to feed back into trust scoring
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { trustToAutonomyLevel, betaMean } from '@cassicore/training-trust-ledger'

import { resolveToolDomain ,
  DEFAULT_PERMISSION_ORACLE_CONFIG,
} from './types.js'

import type {
  PermissionDecision,
  PermissionVerdict,
  HardGate,
  PermissionOracleConfig,
} from './types.js'
import type { ILogger } from '@cassicore/foundation'
import type { ConsequenceEstimator } from '../consequence-estimator/index.js'
import type { RiskAssessment, RiskDimensions, AssessmentContext } from '../consequence-estimator/types.js'
import type { TrustLedger } from '@cassicore/training-trust-ledger'
import type { TrustScore, AutonomyLevel } from '@cassicore/training-trust-ledger'


/** A pending escalation awaiting human decision */
export interface PendingApproval {
  /** Unique ID for this pending approval */
  id: string
  /** The verdict that triggered escalation */
  verdict: PermissionVerdict
  /** When the approval request was created */
  createdAt: number
  /** Timeout timer handle */
  timeoutHandle: ReturnType<typeof setTimeout>
  /** Promise resolve — call with true (approved) or false (rejected) */
  resolve: (approved: boolean) => void
}

/** Serializable pending approval for API responses */
export interface PendingApprovalInfo {
  id: string
  toolName: string
  sessionId: string
  riskScore: number
  riskLevel: string
  trustScore: number
  autonomyLevel: string
  reasoning: string
  inputSummary: string
  createdAt: number
  timeoutMs: number
}


export class PermissionOracle extends BaseCognitiveModule {
  readonly name = 'permission-oracle'
  readonly priority = 76

  private cfg: PermissionOracleConfig = { ...DEFAULT_PERMISSION_ORACLE_CONFIG }

  /** Cross-module references (wired by daemon) */
  private consequenceEstimator?: ConsequenceEstimator
  private trustLedger?: TrustLedger

  /** Decision history for audit trail */
  private decisionLog: PermissionVerdict[] = []
  private maxDecisionLog = 200

  /** Stats */
  private totalDecisions = 0
  private allowCount = 0
  private denyCount = 0
  private escalateCount = 0

  /** Pending approval queue — escalated requests awaiting human decision */
  private pendingApprovals: Map<string, PendingApproval> = new Map()
  private approvalCounter = 0
  private totalApprovals = 0
  private totalRejections = 0
  private totalTimeouts = 0

  constructor(logger: ILogger) {
    super(logger)
    this.logger = logger.child('permission-oracle')
  }


  override async init(): Promise<void> {
    await super.init()

    // Load config overrides
    if (this.config) {
      try {
        const cfgOverrides = this.config.get<Partial<PermissionOracleConfig>>('intelligence.permissionOracle')
        if (cfgOverrides) {
          this.cfg = {
            ...DEFAULT_PERMISSION_ORACLE_CONFIG,
            ...cfgOverrides,
            hardGates: cfgOverrides.hardGates ?? DEFAULT_PERMISSION_ORACLE_CONFIG.hardGates,
          }
        }
      } catch {
        // Non-fatal: use defaults
      }
    }
  }

  override async start(): Promise<void> {
    await super.start()
    this.logger.info('Permission Oracle started', {
      baseThreshold: this.cfg.baseThreshold,
      trustBonusFactor: this.cfg.trustBonusFactor,
      hardGates: this.cfg.hardGates.length,
      fallbackDecision: this.cfg.fallbackDecision,
    })
  }


  /**
   * Wire the Consequence Estimator dependency.
   * Called by the daemon after all modules are constructed.
   */
  setConsequenceEstimator(estimator: ConsequenceEstimator): void {
    this.consequenceEstimator = estimator
  }

  /**
   * Wire the Trust Ledger dependency.
   * Called by the daemon after all modules are constructed.
   */
  setTrustLedger(ledger: TrustLedger): void {
    this.trustLedger = ledger
  }


  /**
   * Judge whether a tool call should be allowed, denied, or escalated.
   *
   * This is the primary entry point. It:
   *   1. Gets a risk assessment from the Consequence Estimator
   *   2. Looks up the domain trust from the Trust Ledger
   *   3. Checks hard gates
   *   4. Computes the trust-adjusted threshold
   *   5. Makes the allow/deny/escalate decision
   *
   * @param toolName - The tool being called
   * @param input - The tool's input parameters
   * @param sessionId - Session context
   * @returns Complete permission verdict with reasoning trail
   */
  judge(toolName: string, input: Record<string, unknown>, sessionId: string, context?: AssessmentContext): PermissionVerdict {
    // Short-circuit: when disabled, always allow without risk/trust evaluation.
    // The trust scoring subsystem is disabled — it blocks autonomous agent tool calls
    // with no meaningful safety benefit (risk scores are heuristic, trust never warms
    // in headless mode, and the escalation timeout silently denies).
    if (!this.cfg.enabled) {
      const domain = resolveToolDomain(toolName)
      const trustScore = this.trustLedger?.getOrCreateDomainScore(domain) ?? this.fallbackTrustScore(domain)
      const riskAssessment = this.fallbackRiskAssessment(toolName)
      return {
        toolName,
        decision: 'allow',
        riskAssessment,
        trustScore,
        effectiveThreshold: 1.0,
        autonomyLevel: 'trusted',
        reasoning: 'Permission oracle disabled — all tool calls allowed',
        sessionId,
        decidedAt: Date.now(),
      }
    }

    // Step 1: Get risk assessment
    let riskAssessment: RiskAssessment
    if (this.consequenceEstimator) {
      riskAssessment = this.consequenceEstimator.assess(toolName, input, sessionId, context)
    } else {
      // No estimator available — use conservative fallback
      riskAssessment = this.fallbackRiskAssessment(toolName)
    }

    // Step 2: Get trust score for the relevant domain
    const domain = resolveToolDomain(toolName)
    let trustScore: TrustScore
    if (this.trustLedger) {
      trustScore = this.trustLedger.getOrCreateDomainScore(domain)
    } else {
      // No trust ledger — use uninformative prior (trust = 0.5)
      trustScore = this.fallbackTrustScore(domain)
    }

    // Step 3: Check hard gates
    const hardGateResult = this.checkHardGates(riskAssessment)

    // Step 4: Compute trust-adjusted threshold
    const effectiveThreshold = this.cfg.baseThreshold * (1 + this.cfg.trustBonusFactor * trustScore.score)

    // Step 5: Make decision
    let decision: PermissionDecision
    let reasoning: string
    let hardGate: string | undefined

    if (hardGateResult) {
      // Hard gate fires — non-negotiable
      decision = hardGateResult.action
      reasoning = `Hard gate: ${hardGateResult.description}`
      hardGate = hardGateResult.id
    } else if (riskAssessment.riskScore < effectiveThreshold) {
      // Risk is below threshold — auto-approve
      decision = 'allow'
      reasoning = `Risk ${riskAssessment.riskScore.toFixed(3)} < threshold ${effectiveThreshold.toFixed(3)} (base=${this.cfg.baseThreshold}, trust=${trustScore.score.toFixed(2)})`
    } else {
      // Risk exceeds threshold — escalate to human
      decision = 'escalate'
      reasoning = `Risk ${riskAssessment.riskScore.toFixed(3)} ≥ threshold ${effectiveThreshold.toFixed(3)} (base=${this.cfg.baseThreshold}, trust=${trustScore.score.toFixed(2)})`
    }

    const autonomyLevel = trustToAutonomyLevel(trustScore.score)

    // Build verdict
    const verdict: PermissionVerdict = {
      toolName,
      decision,
      riskAssessment,
      trustScore,
      effectiveThreshold,
      autonomyLevel,
      reasoning,
      hardGate,
      sessionId,
      decidedAt: Date.now(),
    }

    // Update stats
    this.totalDecisions++
    if (decision === 'allow') this.allowCount++
    else if (decision === 'deny') this.denyCount++
    else this.escalateCount++

    // Log to audit trail
    this.logDecision(verdict)

    // Emit events
    this.emit({
      type: 'permission:decision',
      sessionId,
      toolName,
      decision,
      riskScore: riskAssessment.riskScore,
      trustScore: trustScore.score,
      threshold: effectiveThreshold,
      reason: reasoning,
      timestamp: new Date(),
    })

    if (decision === 'escalate') {
      this.emit({
        type: 'permission:escalated',
        sessionId,
        toolName,
        reason: reasoning,
        riskLevel: riskAssessment.riskLevel,
        timestamp: new Date(),
      })
    }

    this.emit({
      type: 'autonomy:trust-gate',
      sessionId,
      action: toolName,
      gateResult: decision === 'allow' ? 'passed' : decision === 'escalate' ? 'escalated' : 'blocked',
      trustScore: trustScore.score,
      requiredThreshold: effectiveThreshold,
      riskScore: riskAssessment.riskScore,
      timestamp: new Date(),
    })

    this.logger.debug('Permission decision', {
      toolName,
      decision,
      riskScore: riskAssessment.riskScore.toFixed(3),
      trustScore: trustScore.score.toFixed(3),
      threshold: effectiveThreshold.toFixed(3),
      domain,
      autonomyLevel,
      hardGate,
    })

    return verdict
  }

  /**
   * Get recent decision history.
   */
  getDecisionLog(limit = 20): PermissionVerdict[] {
    return this.decisionLog.slice(-limit)
  }

  /**
   * Get decision statistics.
   */
  getStats(): {
    totalDecisions: number
    allowCount: number
    denyCount: number
    escalateCount: number
    allowRate: number
    escalateRate: number
    pendingApprovals: number
    totalApprovals: number
    totalRejections: number
    totalTimeouts: number
  } {
    return {
      totalDecisions: this.totalDecisions,
      allowCount: this.allowCount,
      denyCount: this.denyCount,
      escalateCount: this.escalateCount,
      allowRate: this.totalDecisions > 0 ? this.allowCount / this.totalDecisions : 0,
      escalateRate: this.totalDecisions > 0 ? this.escalateCount / this.totalDecisions : 0,
      pendingApprovals: this.pendingApprovals.size,
      totalApprovals: this.totalApprovals,
      totalRejections: this.totalRejections,
      totalTimeouts: this.totalTimeouts,
    }
  }


  /**
   * Request human approval for an escalated tool call.
   * Returns a Promise that resolves to true (approved) or false (rejected/timed out).
   *
   * This is called by the Tool Executor when an escalation verdict is received.
   * The promise blocks tool execution until the human responds or timeout fires.
   *
   * @param verdict - The escalation verdict from judge()
   * @returns Promise<boolean> — true if approved, false if rejected or timed out
   */
  requestApproval(verdict: PermissionVerdict): Promise<boolean> {
    const id = `perm-${++this.approvalCounter}-${Date.now()}`

    return new Promise<boolean>((resolve) => {
      // Timeout: auto-resolve based on fallback decision
      const timeoutHandle = setTimeout(() => {
        if (this.pendingApprovals.has(id)) {
          this.pendingApprovals.delete(id)
          this.totalTimeouts++
          const fallbackApproved = this.cfg.fallbackDecision === 'allow'

          this.logger.warn('Permission escalation timed out', {
            id,
            toolName: verdict.toolName,
            timeoutMs: this.cfg.escalationTimeoutMs,
            fallbackDecision: this.cfg.fallbackDecision,
          })

          this.emit({
            type: 'permission:human-response',
            sessionId: verdict.sessionId,
            toolName: verdict.toolName,
            approved: fallbackApproved,
            responseTimeMs: this.cfg.escalationTimeoutMs,
            timestamp: new Date(),
          })

          resolve(fallbackApproved)
        }
      }, this.cfg.escalationTimeoutMs)

      const pending: PendingApproval = {
        id,
        verdict,
        createdAt: Date.now(),
        timeoutHandle,
        resolve,
      }

      this.pendingApprovals.set(id, pending)

      this.logger.info('Permission escalation queued', {
        id,
        toolName: verdict.toolName,
        sessionId: verdict.sessionId,
        riskScore: verdict.riskAssessment.riskScore.toFixed(3),
        trustScore: verdict.trustScore.score.toFixed(3),
        timeoutMs: this.cfg.escalationTimeoutMs,
      })
    })
  }

  /**
   * Resolve a pending approval — called by the admin API when human responds.
   *
   * @param id - The pending approval ID
   * @param approved - true to approve, false to reject
   * @param responder - Optional name of the human responder
   * @returns true if the approval was found and resolved, false if not found
   */
  resolveApproval(id: string, approved: boolean, responder?: string): boolean {
    const pending = this.pendingApprovals.get(id)
    if (!pending) return false

    // Clean up
    clearTimeout(pending.timeoutHandle)
    this.pendingApprovals.delete(id)

    const responseTimeMs = Date.now() - pending.createdAt

    if (approved) {
      this.totalApprovals++
    } else {
      this.totalRejections++
    }

    // Emit human response event (Trust Ledger listens for this)
    this.emit({
      type: 'permission:human-response',
      sessionId: pending.verdict.sessionId,
      toolName: pending.verdict.toolName,
      approved,
      responder,
      responseTimeMs,
      timestamp: new Date(),
    })

    this.logger.info('Permission escalation resolved', {
      id,
      toolName: pending.verdict.toolName,
      approved,
      responder,
      responseTimeMs,
    })

    // Resolve the blocking promise
    pending.resolve(approved)
    return true
  }

  /**
   * List all pending approval requests (for admin API).
   */
  listPending(): PendingApprovalInfo[] {
    return Array.from(this.pendingApprovals.values()).map(p => ({
      id: p.id,
      toolName: p.verdict.toolName,
      sessionId: p.verdict.sessionId,
      riskScore: p.verdict.riskAssessment.riskScore,
      riskLevel: p.verdict.riskAssessment.riskLevel,
      trustScore: p.verdict.trustScore.score,
      autonomyLevel: p.verdict.autonomyLevel,
      reasoning: p.verdict.reasoning,
      inputSummary: p.verdict.riskAssessment.inputSummary,
      createdAt: p.createdAt,
      timeoutMs: this.cfg.escalationTimeoutMs,
    }))
  }

  /**
   * Get the count of pending approvals.
   */
  getPendingCount(): number {
    return this.pendingApprovals.size
  }


  /**
   * Check if any hard gate fires for this risk assessment.
   * Returns the first matching gate, or null if none fire.
   */
  private checkHardGates(risk: RiskAssessment): HardGate | null {
    for (const gate of this.cfg.hardGates) {
      // Check tool patterns
      if (gate.toolPatterns && gate.toolPatterns.length > 0) {
        const matches = gate.toolPatterns.some(pattern => {
          const regex = new RegExp(`^${  pattern.replace(/\*/g, '.*')  }$`, 'i')
          return regex.test(risk.toolName)
        })
        if (!matches) continue // Gate doesn't apply to this tool
      }

      // Check risk level
      const riskLevelOrder = { negligible: 0, low: 1, moderate: 2, high: 3, critical: 4 }
      const triggerOrder = riskLevelOrder[gate.triggerLevel]
      const actualOrder = riskLevelOrder[risk.riskLevel]

      if (actualOrder < triggerOrder) continue // Risk level too low for this gate

      // Check specific dimensions
      if (gate.dimensions && gate.dimensions.length > 0) {
        const dimensionTriggered = gate.dimensions.some(dim =>
          risk.dimensions[dim] >= 0.6, // Dimension must be meaningfully high
        )
        if (!dimensionTriggered) continue
      }

      // Check irreversibility gate
      if (gate.id === 'irreversible-always-escalate' && risk.reversibility !== 'irreversible') {
        continue
      }

      // Gate fires
      return gate
    }

    return null
  }


  private fallbackRiskAssessment(toolName: string): RiskAssessment {
    return {
      toolName,
      inputSummary: `[no estimator] ${toolName}`,
      riskScore: 0.5,
      riskLevel: 'moderate',
      dimensions: {
        dataLoss: 0.3,
        systemStability: 0.3,
        externalImpact: 0.2,
        resourceCost: 0.2,
        privacyRisk: 0.2,
      },
      reversibility: 'partially',
      estimatorType: 'heuristic',
      confidence: 0.3,
      reasoning: 'Fallback: no consequence estimator available',
      assessedAt: Date.now(),
    }
  }

  private fallbackTrustScore(domain: string): TrustScore {
    return {
      domain,
      alpha: 1.0,
      beta: 1.0,
      score: 0.5,
      confidence: 0.0,
      evidenceCount: 0,
      lastUpdatedAt: Date.now(),
      lastEvidenceAt: Date.now(),
      lastDecayAt: Date.now(),
    }
  }

  private logDecision(verdict: PermissionVerdict): void {
    this.decisionLog.push(verdict)
    if (this.decisionLog.length > this.maxDecisionLog) {
      this.decisionLog = this.decisionLog.slice(-this.maxDecisionLog)
    }
  }
}


export const MODULE_CLASS = PermissionOracle


export function createPermissionOracle(logger: ILogger): PermissionOracle {
  return new PermissionOracle(logger)
}
