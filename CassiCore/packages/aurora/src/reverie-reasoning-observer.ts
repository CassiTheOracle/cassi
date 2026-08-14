/**
 * ReverieReasoningObserver — multi-tier LLM-powered semantic analysis.
 *
 * Bridges Aurora's fast-path concept extraction with Reverie's slow-path
 * semantic curation. Analyzes reasoning text for contradictions, gaps,
 * assumptions, confidence, task-alignment, and breakthroughs.
 *
 * Tiers (B5):
 *   1 — Haiku: cheap, fast, reduced output budget (max 3 insights, 80 chars each)
 *   2 — Sonnet: thorough analysis, the current default
 *   3 — Opus: deep investigation for escalated or high-stakes turns
 *
 * Escalation rules:
 *   - If max insight confidence < lowConfidenceThreshold → flag for escalation
 *   - If a contradiction insight has confidence < threshold → flag for escalation
 *   - High-stakes turns bypass lower tiers
 *
 * See: docs/design/aurora-reverie-escalation-tiers.md
 */

import type { ILogger } from '@cassicore/foundation'
import type { MentalState, ReverieInsight, ReverieInferenceProvider, ReasoningAnalysisInput } from './types.js'
import { REVERIE_HAS_INSIGHT_PHRASES } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'

/** Reverie analysis tier levels. */
export type ReverieTier = 1 | 2 | 3

export interface ReverieAnalysisResult {
  insights: ReverieInsight[]
  tier: ReverieTier
  shouldEscalate: boolean
  escalateReason?: string
  durationMs: number
}

export interface EscalationChainResult {
  finalResult: ReverieAnalysisResult
  chain: ReverieAnalysisResult[]
  escalated: boolean
  totalDurationMs: number
}

export interface ReverieEscalationConfig {
  lowConfidenceThreshold: number
  contradictionThreshold: number
  highStakesMinTier: ReverieTier
}

const TIER_PROMPTS: Record<ReverieTier, string> = {
  1: `I am performing a quick sanity check on reasoning. Look for obvious contradictions and clear gaps only.
Return at most 3 insights, each under 80 characters.`,
  2: `I am observing my own reasoning. I analyze the reasoning text for semantic patterns that regex-based concept extraction cannot detect.`,
  3: `I am performing a deep investigation of reasoning quality. Examine every claim, trace logical chains, and identify subtle inconsistencies that cheaper analysis might miss. Be thorough.`,
}

const BASE_PROMPT = `
What I look for:
1. Contradictions — does the reasoning conflict with stated decisions or prior conclusions?
2. Gaps — what important aspects are missing from the analysis?
3. Unstated assumptions — what premises is the reasoning taking for granted?
4. Confidence — how certain does the reasoning sound? Is it hedging, overconfident, or appropriately calibrated?
5. Task misalignment — does this reasoning serve the active task, or is it drifting?
6. Breakthroughs — is there a novel insight or unexpected connection?

Output strict JSON:
{
  "insights": [
    {
      "kind": "contradiction" | "gap" | "assumption" | "confidence" | "task-misalignment" | "breakthrough",
      "content": "what I observed",
      "confidence": 0.0-1.0,
      "suggestion": "optional: what should be done about it"
    }
  ]
}

Rules:
- Return empty insights array if nothing notable is detected.
- Be specific: reference actual phrases from the reasoning text.
- Confidence should reflect how certain I am about the observation, not the reasoning's confidence.
- Prefer silence over noise. Quality over quantity.`

const DEFAULT_ESCALATION: ReverieEscalationConfig = {
  lowConfidenceThreshold: 0.4,
  contradictionThreshold: 0.5,
  highStakesMinTier: 2,
}

let ridCounter = 0
function makeId(): string {
  return `rro_${Date.now().toString(36)}_${(ridCounter++).toString(36)}`
}

export class ReverieReasoningObserver {
  private logger: ILogger
  private escalationConfig: ReverieEscalationConfig
  private mnemicField?: MnemicField

  constructor(
    private inference: ReverieInferenceProvider,
    logger: ILogger,
    escalationConfig?: Partial<ReverieEscalationConfig>,
  ) {
    this.logger = logger.child ? logger.child('reverie-reasoning-observer') : logger
    this.escalationConfig = { ...DEFAULT_ESCALATION, ...escalationConfig }
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  /**
   * Analyze reasoning text for semantic patterns at a specific tier.
   * Returns a structured result with escalation recommendation.
   */
  async analyze(
    input: ReasoningAnalysisInput,
    timeoutMs: number,
    tier: ReverieTier = 2,
  ): Promise<ReverieAnalysisResult> {
    const start = Date.now()

    if (this.mnemicField && tier === 1 && input.text) {
      const pre = await this.mnemicField.classifyPhrase(input.text, REVERIE_HAS_INSIGHT_PHRASES).catch(() => null)
      if (pre?.label === 'no_insight' && pre.score > 0.40) {
        return { insights: [], tier: 1, shouldEscalate: false, durationMs: Date.now() - start }
      }
      if (pre?.label === 'has_insight' && pre.score > 0.50) {
        return this.analyze(input, timeoutMs, 2)
      }
    }

    const stateContext = this.buildStateContext(input)
    const userPrompt = this.buildPrompt(input, stateContext)
    const systemPrompt = TIER_PROMPTS[tier] + BASE_PROMPT

    // Tier-aware token budget
    const maxTokens = tier === 1 ? 256 : tier === 2 ? 1024 : 2048

    let raw = ''
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), timeoutMs)
      raw = await this.inference.infer([
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ], { maxTokens, temperature: tier === 3 ? 0.2 : 0.3, signal: ctrl.signal })
      clearTimeout(timer)
    } catch (err) {
      this.logger.debug('Reverie reasoning analysis failed', { error: String(err), durationMs: Date.now() - start, tier })
      return { insights: [], tier, shouldEscalate: false, durationMs: Date.now() - start }
    }

    const insights = this.parseInsights(raw)
    const durationMs = Date.now() - start

    // B5 §6.1 — confidence-based escalation rule
    const { shouldEscalate, escalateReason } = this.evaluateEscalation(insights, tier)

    this.logger.debug('Reverie reasoning analysis complete', {
      insights: insights.length,
      tier,
      shouldEscalate,
      durationMs,
    })

    return { insights, tier, shouldEscalate, escalateReason, durationMs }
  }

  /**
   * Analyze with auto-escalation: cascades from a starting tier up through tier 3,
   * stopping when the result no longer recommends escalation or tier 3 is reached.
   * Each tier gets its own full timeoutMs budget.
   */
  async analyzeWithEscalation(
    input: ReasoningAnalysisInput,
    timeoutMs: number,
    options?: { startTier?: ReverieTier; isHighStakes?: boolean },
  ): Promise<EscalationChainResult> {
    const start = Date.now()
    const startTier: ReverieTier = options?.isHighStakes
      ? this.escalationConfig.highStakesMinTier
      : (options?.startTier ?? 1)

    const chain: ReverieAnalysisResult[] = []
    let tier: ReverieTier = startTier

    while (true) {
      const result = await this.analyze(input, timeoutMs, tier)
      chain.push(result)

      if (!result.shouldEscalate || tier >= 3) break
      tier = (tier + 1) as ReverieTier
    }

    const finalResult = chain[chain.length - 1]
    const escalated = chain.length > 1
    const totalDurationMs = Date.now() - start

    const tierPath = chain.map(r => r.tier).join('->')
    this.logger.info('Reverie escalation chain complete', {
      tierPath,
      escalated,
      finalTier: finalResult.tier,
      finalShouldEscalate: finalResult.shouldEscalate,
      finalEscalateReason: finalResult.escalateReason,
      totalDurationMs,
    })

    return { finalResult, chain, escalated, totalDurationMs }
  }

  private evaluateEscalation(insights: ReverieInsight[], tier: ReverieTier): { shouldEscalate: boolean; escalateReason?: string } {
    if (insights.length === 0 || tier >= 3) return { shouldEscalate: false }

    const maxConf = Math.max(...insights.map(i => i.confidence))
    if (maxConf < this.escalationConfig.lowConfidenceThreshold) {
      return { shouldEscalate: true, escalateReason: `max confidence ${maxConf.toFixed(2)} < ${this.escalationConfig.lowConfidenceThreshold}` }
    }

    const contradictions = insights.filter(i => i.kind === 'contradiction')
    if (contradictions.some(i => i.confidence < this.escalationConfig.contradictionThreshold)) {
      return { shouldEscalate: true, escalateReason: `uncertain contradiction (confidence < ${this.escalationConfig.contradictionThreshold})` }
    }

    return { shouldEscalate: false }
  }

  private buildStateContext(input: ReasoningAnalysisInput): string {
    const parts: string[] = []

    if (input.currentState) {
      parts.push(`Current foci: ${input.currentState.foci.join(', ') || '(none)'}`)
      parts.push(`Coherence: ${input.currentState.coherence.toFixed(2)}`)
      parts.push(`Integration: ${input.currentState.integration.toFixed(2)}`)
    }

    if (input.activeTask) {
      parts.push(`Active task: ${input.activeTask.slice(0, 200)}`)
    }

    if (input.recentDecisions.length > 0) {
      parts.push(`Recent decisions:\n${input.recentDecisions.map(d => `- ${d}`).join('\n')}`)
    }

    if (input.shiftDetected) {
      parts.push('Note: a reasoning shift was detected by the fast path.')
    }

    return parts.join('\n')
  }

  private buildPrompt(input: ReasoningAnalysisInput, stateContext: string): string {
    const MAX_TEXT_LEN = 4000
    const text = input.text
    if (text.length > MAX_TEXT_LEN) {
      this.logger.debug('Reverie reasoning text truncated', {
        originalLength: text.length,
        truncatedTo: MAX_TEXT_LEN,
      })
    }

    return `## Reasoning text to analyze
${text.slice(0, MAX_TEXT_LEN)}

## Extracted concepts (fast path)
${input.extractedConcepts.join(', ') || '(none)'}

## Current mental state context
${stateContext || '(no context)'}

Analyze the reasoning text. What semantic patterns do you detect?`
  }

  private parseInsights(raw: string): ReverieInsight[] {
    try {
      // Extract JSON: look for {"insights":...} non-greedily
      const jsonMatch = raw.match(/\{\s*"insights"\s*:\s*\[[\s\S]*?\]\s*\}/)
      const jsonStr = jsonMatch ? jsonMatch[0] : raw
      const parsed = JSON.parse(jsonStr)

      if (!Array.isArray(parsed.insights)) return []

      const VALID_KINDS = new Set<ReverieInsight['kind']>([
        'contradiction', 'gap', 'assumption', 'confidence', 'task-misalignment', 'breakthrough',
      ])

      return parsed.insights
        .filter((i: any) =>
          typeof i?.kind === 'string' &&
          VALID_KINDS.has(i.kind) &&
          typeof i?.content === 'string' &&
          typeof i?.confidence === 'number',
        )
        .map((i: any): ReverieInsight => ({
          kind: i.kind,
          content: i.content,
          confidence: Math.min(1, Math.max(0, i.confidence)),
          suggestion: typeof i.suggestion === 'string' ? i.suggestion : undefined,
        }))
    } catch {
      return []
    }
  }
}

export { makeId as makeReasoningRecordId }
