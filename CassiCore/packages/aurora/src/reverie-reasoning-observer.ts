/**
 * ReverieReasoningObserver — LLM-powered semantic analysis of reasoning text.
 *
 * Bridges Aurora's fast-path concept extraction with Reverie's slow-path
 * semantic curation. Analyzes reasoning text for contradictions, gaps,
 * assumptions, confidence, task-alignment, and breakthroughs.
 *
 * This is a lightweight observer that uses Reverie's inference infrastructure
 * but is specialized for reasoning analysis (not lamina curation).
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { MentalState, ReverieInsight, ReverieInferenceProvider, ReasoningAnalysisInput } from './types.js'

const OBSERVER_SYSTEM_PROMPT = `I am observing my own reasoning. I analyze the reasoning text for semantic patterns that regex-based concept extraction cannot detect.

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

let ridCounter = 0
function makeId(): string {
  return `rro_${Date.now().toString(36)}_${(ridCounter++).toString(36)}`
}

export class ReverieReasoningObserver {
  private logger: ILogger

  constructor(
    private inference: ReverieInferenceProvider,
    logger: ILogger,
  ) {
    this.logger = logger.child ? logger.child('reverie-reasoning-observer') : logger
  }

  /**
   * Analyze reasoning text for semantic patterns.
   * Returns insights within the configured timeout.
   */
  async analyze(
    input: ReasoningAnalysisInput,
    timeoutMs: number,
  ): Promise<ReverieInsight[]> {
    const start = Date.now()

    // Build context about current mental state
    const stateContext = this.buildStateContext(input)

    const userPrompt = this.buildPrompt(input, stateContext)

    let raw = ''
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), timeoutMs)
      raw = await this.inference.infer([
        { role: 'system', content: OBSERVER_SYSTEM_PROMPT },
        { role: 'user', content: userPrompt },
      ], { maxTokens: 1024, temperature: 0.3, signal: ctrl.signal })
      clearTimeout(timer)
    } catch (err) {
      this.logger.debug('Reverie reasoning analysis failed', { error: String(err), durationMs: Date.now() - start })
      return []
    }

    const insights = this.parseInsights(raw)
    this.logger.debug('Reverie reasoning analysis complete', {
      insights: insights.length,
      durationMs: Date.now() - start,
    })

    return insights
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
