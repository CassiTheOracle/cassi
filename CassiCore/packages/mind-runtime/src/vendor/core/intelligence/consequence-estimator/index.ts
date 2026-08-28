/**
 * Consequence Estimator — Heuristic + LLM risk assessment for tool calls.
 *
 * Priority: 75 (runs after Memory/Continuity/Recover but before Thinker/Optimizer)
 *
 * Architecture:
 *   1. Heuristic layer: fast, deterministic risk scoring from the tool risk table
 *      + input-sensitive adjustment rules. No LLM call needed. ~0ms.
 *   2. LLM layer (future Phase 2): for ambiguous cases where heuristic confidence
 *      is low, escalate to an LLM for semantic risk analysis.
 *   3. Combined: take the maximum of heuristic and LLM scores (conservative).
 *
 * The Consequence Estimator does NOT make decisions — it only produces
 * RiskAssessments. The Permission Oracle consumes these assessments.
 *
 * Events emitted:
 *   - consequence:estimated — after every successful risk assessment
 *   - consequence:estimation-failed — when assessment fails
 *
 * Events consumed:
 *   - tool:registered / tool:unregistered — to track available tools
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'

import { getToolRiskProfile } from './tool-risk-table.js'
import {
  DEFAULT_DIMENSION_WEIGHTS,
  computeCompositeScore,
  scoreToLevel,
  clamp01,
} from './types.js'

import type {
  RiskAssessment,
  RiskDimensions,
  Reversibility,
  InputSensitivityRule,
  DimensionWeights,
  AssessmentContext,
} from './types.js'
import type { ILogger } from '@cassicore/foundation'


export class ConsequenceEstimator extends BaseCognitiveModule {
  readonly name = 'consequence-estimator'
  readonly priority = 75

  private dimensionWeights: DimensionWeights = { ...DEFAULT_DIMENSION_WEIGHTS }
  private assessmentCount = 0
  private failureCount = 0

  constructor(logger: ILogger) {
    super(logger)
    this.logger = logger.child('consequence-estimator')
  }


  override async init(): Promise<void> {
    await super.init()

    // Load custom dimension weights from config if available
    if (this.config) {
      try {
        const weights = this.config.get<Partial<DimensionWeights>>('intelligence.consequenceEstimator.weights')
        if (weights) {
          this.dimensionWeights = { ...DEFAULT_DIMENSION_WEIGHTS, ...weights }
          this.logger.info('Loaded custom dimension weights from config', { weights: this.dimensionWeights })
        }
      } catch {
        // Non-fatal: use defaults
      }
    }
  }

  override async start(): Promise<void> {
    await super.start()
    this.logger.info('Consequence Estimator started', {
      weights: this.dimensionWeights,
      knownTools: Object.keys(getToolRiskProfile('__probe__')).length,
    })
  }


  /**
   * Assess the risk of a tool call.
   *
   * This is the primary entry point. It runs the heuristic estimator
   * and optionally the LLM estimator (Phase 2), returning a complete
   * RiskAssessment.
   *
   * @param toolName - The tool being called
   * @param input - The tool's input parameters
   * @param sessionId - Session context for event emission
   * @returns Complete risk assessment
   */
  assess(toolName: string, input: Record<string, unknown>, sessionId: string, context?: AssessmentContext): RiskAssessment {
    try {
      const assessment = this.heuristicAssess(toolName, input)

      // Layer 4: Session-type risk multiplier
      // WHY: Helix agents run autonomously with no human in the loop.
      // Bumping dataLoss and systemStability for helix sessions makes
      // the Permission Oracle more likely to escalate or deny risky writes.
      if (context?.sessionType === 'helix') {
        const HELIX_RISK_BOOST = 0.15
        assessment.dimensions.dataLoss = clamp01(assessment.dimensions.dataLoss + HELIX_RISK_BOOST)
        assessment.dimensions.systemStability = clamp01(assessment.dimensions.systemStability + HELIX_RISK_BOOST)
        assessment.riskScore = computeCompositeScore(assessment.dimensions, this.dimensionWeights)
        assessment.riskLevel = scoreToLevel(assessment.riskScore)
        assessment.reasoning += `; helix session: dataLoss +${HELIX_RISK_BOOST}, systemStability +${HELIX_RISK_BOOST}`
      }

      this.assessmentCount++

      // Emit event
      this.emit({
        type: 'consequence:estimated',
        sessionId,
        toolName,
        riskLevel: assessment.riskLevel,
        riskScore: assessment.riskScore,
        reversibility: assessment.reversibility,
        dimensions: assessment.dimensions,
        estimatorType: assessment.estimatorType,
        timestamp: new Date(),
      })

      return assessment
    } catch (err) {
      this.failureCount++
      this.logger.error('Risk assessment failed', { toolName, error: String(err) })

      // Emit failure event
      this.emit({
        type: 'consequence:estimation-failed',
        sessionId,
        toolName,
        error: String(err),
        timestamp: new Date(),
      })

      // Conservative fallback: assume high risk when estimation fails
      return this.conservativeFallback(toolName, input)
    }
  }

  /**
   * Get assessment statistics.
   */
  getStats(): { assessments: number; failures: number; failureRate: number } {
    return {
      assessments: this.assessmentCount,
      failures: this.failureCount,
      failureRate: this.assessmentCount > 0 ? this.failureCount / this.assessmentCount : 0,
    }
  }

  /**
   * Update dimension weights (e.g., from the learning system).
   */
  updateWeights(weights: Partial<DimensionWeights>): void {
    const oldWeights = { ...this.dimensionWeights }
    this.dimensionWeights = { ...this.dimensionWeights, ...weights }
    this.logger.info('Dimension weights updated', { old: oldWeights, new: this.dimensionWeights })
  }


  /**
   * Fast, deterministic risk assessment using the tool risk table
   * and input-sensitive adjustment rules.
   */
  private heuristicAssess(toolName: string, input: Record<string, unknown>): RiskAssessment {
    const profile = getToolRiskProfile(toolName)
    const dimensions = { ...profile.baselineDimensions }
    let reversibility: Reversibility = profile.defaultReversibility
    const reasons: string[] = [`Baseline: ${toolName} (${profile.defaultReversibility})`]

    // Apply input-sensitive adjustments
    for (const [dimKey, rules] of Object.entries(profile.inputSensitivity)) {
      if (!rules) continue
      const dimension = dimKey as keyof RiskDimensions

      for (const rule of rules as InputSensitivityRule[]) {
        const paramValue = this.getInputValue(input, rule.paramKey)
        if (paramValue === undefined) continue

        const matches = this.matchesPattern(paramValue, rule.pattern)
        if (matches) {
          dimensions[dimension] = clamp01(dimensions[dimension] + rule.adjustment)
          reasons.push(`${dimension} +${rule.adjustment}: ${rule.reason}`)

          // Upgrade reversibility if data loss or system stability is high
          if (dimension === 'dataLoss' && dimensions.dataLoss > 0.6) {
            reversibility = 'irreversible'
          }
        }
      }
    }

    // Apply hard ceilings
    if (profile.hardCeiling) {
      for (const [dimKey, ceiling] of Object.entries(profile.hardCeiling)) {
        const dimension = dimKey as keyof RiskDimensions
        if (ceiling !== undefined && dimensions[dimension] > ceiling) {
          dimensions[dimension] = ceiling
          reasons.push(`${dimension} capped at ${ceiling}`)
        }
      }
    }

    // Compute composite score
    const riskScore = computeCompositeScore(dimensions, this.dimensionWeights)

    // Build input summary (sanitized — no secrets)
    const inputSummary = this.sanitizeInputSummary(toolName, input)

    return {
      toolName,
      inputSummary,
      riskScore,
      riskLevel: scoreToLevel(riskScore),
      dimensions,
      reversibility,
      estimatorType: 'heuristic',
      confidence: 0.8, // Heuristic confidence is high for known tools
      reasoning: reasons.join('; '),
      assessedAt: Date.now(),
    }
  }


  /**
   * Conservative fallback when estimation fails entirely.
   * Assumes high risk across all dimensions.
   */
  private conservativeFallback(toolName: string, input: Record<string, unknown>): RiskAssessment {
    return {
      toolName,
      inputSummary: `[fallback] ${toolName}`,
      riskScore: 0.7,
      riskLevel: 'high',
      dimensions: {
        dataLoss: 0.5,
        systemStability: 0.5,
        externalImpact: 0.5,
        resourceCost: 0.3,
        privacyRisk: 0.3,
      },
      reversibility: 'partially',
      estimatorType: 'heuristic',
      confidence: 0.2, // Low confidence = conservative
      reasoning: 'Fallback assessment due to estimation failure',
      assessedAt: Date.now(),
    }
  }

  /**
   * Extract a value from tool input, handling nested paths.
   */
  private getInputValue(input: Record<string, unknown>, paramKey: string): string | undefined {
    const value = input[paramKey]
    if (value === undefined || value === null) return undefined
    return String(value)
  }

  /**
   * Check if a string value matches a pattern (regex or string).
   */
  private matchesPattern(value: string, pattern: RegExp | string): boolean {
    if (pattern instanceof RegExp) {
      return pattern.test(value)
    }
    return value.toLowerCase().includes(pattern.toLowerCase())
  }

  /**
   * Create a sanitized summary of tool inputs (no secrets or long content).
   */
  private sanitizeInputSummary(toolName: string, input: Record<string, unknown>): string {
    const parts: string[] = []
    const sensitiveKeys = /(?:key|secret|token|password|credential|auth)/i

    for (const [key, value] of Object.entries(input)) {
      if (sensitiveKeys.test(key)) {
        parts.push(`${key}=[REDACTED]`)
      } else if (typeof value === 'string') {
        parts.push(`${key}="${value.length > 80 ? `${value.slice(0, 80)  }...` : value}"`)
      } else if (value !== undefined) {
        parts.push(`${key}=${JSON.stringify(value).slice(0, 50)}`)
      }
    }

    return `${toolName}(${parts.join(', ')})`
  }
}


export const MODULE_CLASS = ConsequenceEstimator


export function createConsequenceEstimator(logger: ILogger): ConsequenceEstimator {
  return new ConsequenceEstimator(logger)
}
