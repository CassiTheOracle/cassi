/**
 * ConsolidatedDialecticProcessor — Single-call Yang + Yin + Serenity
 *
 * Replaces the parallel processor's 3-7 separate LLM requests with ONE
 * consolidated prompt that produces all three dialectic analyses in a single
 * response. This is the optimal strategy for request-based providers where
 * every API call counts equally regardless of size.
 *
 * The consolidated prompt asks the model to:
 *   1. YANG: Generate expansion branches (alternative interpretations, edge cases, etc.)
 *   2. YIN: Provide baseline assessment + self-critique
 *   3. SERENITY: Synthesize Yang and Yin into actionable signals
 *
 * The response is parsed back into the same typed structures (YangOutput,
 * YinBaselineOutput, SerenityOutput) so downstream code is unaffected.
 *
 * Request savings: 3-7 requests → 1 request per turn.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type {
  YangOutput,
  YangBranch,
  YinBaselineOutput,
  YinBaselineBranch,
  YinCritique,
  SerenityOutput,
  YangContext,
  DialecticStreamEvent,
  ParallelDialecticResult,
  SignalType,
  Urgency,
} from '../../../types/dialectic.js'
import type { IProvider } from '../../../types/runtime.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { PromptOptimizer } from './prompt-optimizer.js'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ConsolidatedConfig {
  /** Observer timeout in ms (for the single consolidated call) */
  observerTimeoutMs: number
  /** Max Yang branches to request */
  maxBranches: number
  /** Min confidence for branch filtering */
  minConfidence: number
  /** Temperature for the consolidated call */
  temperature: number
  /** Model to use (provider/model format) */
  model: string
}

export interface ConsolidatedOptions {
  providers?: {
    consolidated?: IProvider | { model: string }
  }
  signal?: AbortSignal
}

// ─── Default Config ──────────────────────────────────────────────────────────

const DEFAULT_CONFIG: ConsolidatedConfig = {
  observerTimeoutMs: 30_000,
  maxBranches: 3,
  minConfidence: 0.3,
  temperature: 0.7,
  model: 'gpt-5-mini',
}

// ─── Processor ───────────────────────────────────────────────────────────────

export class ConsolidatedDialecticProcessor {
  private logger: ILogger
  private config: ConsolidatedConfig
  private provider: IProvider | undefined
  private eventBus: IEventBus | undefined
  private memory: IMemory | undefined
  private promptOptimizer: PromptOptimizer | undefined

  constructor(logger: ILogger, config?: Partial<ConsolidatedConfig>) {
    this.logger = logger
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  // ── Wiring ─────────────────────────────────────────────────────────────

  setProvider(provider: IProvider): void { this.provider = provider }
  setEventBus(bus: IEventBus): void { this.eventBus = bus }
  setMemory(memory: IMemory): void { this.memory = memory }
  setPromptOptimizer(optimizer: PromptOptimizer): void { this.promptOptimizer = optimizer }

  // ── Main Entry Point ───────────────────────────────────────────────────

  async processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext,
    emitStreamEvent: (event: DialecticStreamEvent) => void,
    opts?: ConsolidatedOptions,
  ): Promise<ParallelDialecticResult> {
    const startTime = Date.now()

    this.logger.info('ConsolidatedDialecticProcessor: starting consolidated turn', {
      sessionId, turnId,
    })

    // Resolve provider
    const providerToUse = this.resolveProvider(opts)
    if (!providerToUse) {
      this.logger.warn('ConsolidatedDialecticProcessor: no provider, returning empty result')
      return this.createEmptyResult(sessionId, turnId, startTime)
    }

    // Fetch relevant memories for context enrichment
    let relevantMemories: string[] = []
    if (this.memory) {
      try {
        const results = await this.memory.search(userMessage, { limit: 5 })
        relevantMemories = results.map(r => r.entry.content.slice(0, 8000))
      } catch (error) {
        this.logger.warn('ConsolidatedDialecticProcessor: failed to fetch memories', { error: String(error) })
      }
    }

    // Emit start
    emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'start', data: { mode: 'consolidated' } })

    try {
      // ── Build and send the consolidated prompt ───────────────────────────
      const prompt = this.buildConsolidatedPrompt(userMessage, context, relevantMemories)
      const modelSpec = this.resolveModel(opts)
      const slash = modelSpec.indexOf('/')
      const modelName = slash >= 0 ? modelSpec.slice(slash + 1) : modelSpec

      const response = await this.callProvider(providerToUse, prompt, modelName, opts?.signal)
      const callDuration = Date.now() - startTime

      // ── Parse the consolidated response ──────────────────────────────────
      const parsed = this.parseConsolidatedResponse(response)

      // Emit stage events
      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'yang', data: parsed.yang })
      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'yin', data: parsed.yin })
      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'serenity', data: parsed.serenity })

      // ── Build result ─────────────────────────────────────────────────────
      const totalLatencyMs = Date.now() - startTime

      const signalInjected = parsed.serenity.synthesis.hasSignal &&
        parsed.serenity.synthesis.signal?.urgency === 'immediate' &&
        (parsed.serenity.synthesis.signal?.confidence || 0) >= 0.6

      const result: ParallelDialecticResult = {
        sessionId,
        turnId,
        timestamp: startTime,
        level: 0,
        executionMode: 'parallel', // Keep compatible with existing type
        yang: parsed.yang,
        yin: parsed.yin,
        serenity: parsed.serenity,
        signalInjected,
        totalLatencyMs,
        totalCostUsd: 0, // Consolidated call — cost tracked at provider level
        timing: {
          yangDuration: callDuration,
          yinDuration: callDuration,
          serenityDuration: callDuration,
          totalParallelTime: totalLatencyMs,
          firstCompletion: 'yang',
        },
        quality: {
          yangYinAgreement: this.calculateAgreement(parsed.yang, parsed.yin),
          dialecticTension: this.calculateTension(parsed.yang, parsed.yin),
          synthesisConfidence: parsed.serenity.meta.dialecticQuality,
        },
      }

      // ── Archive to memory ────────────────────────────────────────────────
      if (this.memory && typeof (this.memory as any).archiveDialectic === 'function') {
        try {
          const mem = this.memory as any
          for (let i = 0; i < parsed.yang.branches.length; i++) {
            const branch = parsed.yang.branches[i]
            await mem.archiveDialectic(sessionId, 'yang', branch.content, undefined, {
              turnId, branchIndex: i, confidence: branch.confidence,
              source: 'dialectic:consolidated', tags: ['dialectic', 'yang', `turn:${turnId}`],
            })
          }
          for (let i = 0; i < parsed.yin.selfCritiques.length; i++) {
            const critique = parsed.yin.selfCritiques[i]
            await mem.archiveDialectic(sessionId, 'yin', critique.critique, undefined, {
              turnId, critiqueIndex: i, targetBranch: critique.yangBranchId,
              source: 'dialectic:consolidated', tags: ['dialectic', 'yin', `turn:${turnId}`],
            })
          }
          if (parsed.serenity.synthesis.signal) {
            await mem.archiveDialectic(sessionId, 'serenity',
              parsed.serenity.synthesis.signal.content || `Consolidated synthesis`, undefined, {
              turnId, hasSignal: parsed.serenity.synthesis.hasSignal,
              signalType: parsed.serenity.synthesis.signal.type,
              confidence: parsed.serenity.synthesis.signal.confidence,
              source: 'dialectic:consolidated', tags: ['dialectic', 'serenity', `turn:${turnId}`],
            })
          }
        } catch (err) {
          this.logger.warn('ConsolidatedDialecticProcessor: failed to archive', { error: String(err) })
        }
      }

      // ── Prompt optimizer feedback ────────────────────────────────────────
      if (this.promptOptimizer?.enabled) {
        this.promptOptimizer.recordFeedback({
          quality: {
            yangYinAgreement: result.quality.yangYinAgreement,
            dialecticTension: result.quality.dialecticTension,
            synthesisConfidence: result.quality.synthesisConfidence,
            hasSignal: result.signalInjected,
          },
          selectedVariants: {
            yang: 'consolidated-v1',
            yin: 'consolidated-v1',
            serenity: 'consolidated-v1',
          },
        })
      }

      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'complete' })

      this.logger.info('ConsolidatedDialecticProcessor: turn complete', {
        sessionId, turnId, totalLatencyMs,
        yangBranches: parsed.yang.branches.length,
        yinBaselines: parsed.yin.baselineBranches.length,
        signalInjected,
        requestsSaved: '3-7 → 1 (consolidated)',
      })

      return result
    } catch (error) {
      this.logger.error('ConsolidatedDialecticProcessor: turn failed', {
        sessionId, turnId, error: String(error),
      })
      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'error', data: { error: String(error) } })
      throw error
    }
  }

  // ── Prompt Building ──────────────────────────────────────────────────────

  private buildConsolidatedPrompt(
    userMessage: string,
    context: YangContext,
    memories: string[],
  ): string {
    const parts: string[] = []

    parts.push(`You are performing a comprehensive dialectic analysis of a conversation turn.
You will produce THREE analyses in a single response: Yang (expansion), Yin (baseline + critique), and Serenity (synthesis).

## CONTEXT`)

    if (context.sessionHistory?.length) {
      parts.push(`Recent conversation:\n${context.sessionHistory.slice(-3).map((h: any) =>
        `${h.role}: ${typeof h.content === 'string' ? h.content.slice(0, 500) : '[content blocks]'}`
      ).join('\n')}`)
    }

    if (context.taskGuide) {
      parts.push(`Task guide: ${context.taskGuide}`)
    }

    if (context.subconsciousPatterns?.length) {
      parts.push(`Detected patterns: ${context.subconsciousPatterns.map((p: any) => p.type || String(p)).join(', ')}`)
    }

    if (memories.length > 0) {
      parts.push(`Relevant memories:\n${memories.slice(0, 3).map((m, i) => `[${i + 1}] ${m.slice(0, 300)}`).join('\n')}`)
    }

    parts.push(`
## USER MESSAGE
"${userMessage.slice(0, 2000)}"

## INSTRUCTIONS

Produce ALL THREE sections below. Output ONLY valid JSON — no markdown fences, no commentary.

{
  "yang": {
    "branches": [
      {
        "type": "alternative_interpretation | edge_case | cross_domain | what_if | assumption_challenge",
        "content": "the expansion insight",
        "confidence": 0.0-1.0,
        "noveltyScore": 0.0-1.0
      }
    ]
  },
  "yin": {
    "baselines": [
      {
        "type": "grounding | constraint | reality_check | prioritization | risk_assessment",
        "content": "baseline assessment",
        "confidence": 0.0-1.0,
        "relevanceScore": 0.0-1.0
      }
    ],
    "critiques": [
      {
        "yangBranchIndex": 0,
        "valid": true,
        "critique": "why this branch is or isn't valid",
        "relevance": 0.0-1.0,
        "action": "keep | compress | discard | flag"
      }
    ]
  },
  "serenity": {
    "hasSignal": true,
    "signal": {
      "type": "edge_case | alternative | assumption | connection | contradiction | convergence | tension | gap",
      "content": "the synthesized actionable insight",
      "confidence": 0.0-1.0,
      "urgency": "immediate | background"
    },
    "branchesConsidered": 3,
    "branchesSurfaced": 1,
    "dialecticQuality": 0.0-1.0
  }
}

Generate ${this.config.maxBranches} Yang branches with diverse types.
Generate 1-2 Yin baselines and critiques for each Yang branch.
Serenity should synthesize the tension between Yang and Yin into an actionable signal.
Set hasSignal=false if no meaningful insight emerges.`)

    return parts.join('\n\n')
  }

  // ── Response Parsing ─────────────────────────────────────────────────────

  private parseConsolidatedResponse(text: string): {
    yang: YangOutput
    yin: YinBaselineOutput
    serenity: SerenityOutput
  } {
    try {
      // Try to extract JSON from the response
      const jsonStr = this.extractJson(text)
      const raw = JSON.parse(jsonStr)

      return {
        yang: this.parseYang(raw.yang),
        yin: this.parseYin(raw.yin, raw.yang),
        serenity: this.parseSerenity(raw.serenity),
      }
    } catch (err) {
      this.logger.warn('ConsolidatedDialecticProcessor: parse failed, returning defaults', { error: String(err) })
      return {
        yang: this.emptyYang(),
        yin: this.emptyYin(),
        serenity: this.emptySerenity(),
      }
    }
  }

  private extractJson(text: string): string {
    // Strip markdown fences if present
    let cleaned = text.trim()
    if (cleaned.startsWith('```')) {
      cleaned = cleaned.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '')
    }
    // Find the outermost JSON object
    const start = cleaned.indexOf('{')
    const end = cleaned.lastIndexOf('}')
    if (start >= 0 && end > start) {
      return cleaned.slice(start, end + 1)
    }
    return cleaned
  }

  private parseYang(raw: any): YangOutput {
    if (!raw?.branches || !Array.isArray(raw.branches)) return this.emptyYang()

    const validTypes = ['alternative_interpretation', 'edge_case', 'cross_domain', 'what_if', 'assumption_challenge']
    const branches: YangBranch[] = raw.branches
      .map((b: any, i: number) => ({
        id: `consolidated-yang-${i}`,
        type: validTypes.includes(b.type) ? b.type : 'what_if',
        content: String(b.content || ''),
        confidence: Math.max(0, Math.min(1, Number(b.confidence) || 0.5)),
        noveltyScore: Math.max(0, Math.min(1, Number(b.noveltyScore) || 0.5)),
      }))
      .filter((b: YangBranch) => b.content.length > 0 && b.confidence >= this.config.minConfidence)
      .slice(0, this.config.maxBranches)

    return {
      branches,
      meta: {
        expansionTemperature: this.config.temperature,
        generationTimeMs: 0, // Set by caller
        inputTokens: 0,
        outputTokens: 0,
      },
    }
  }

  private parseYin(raw: any, yangRaw: any): YinBaselineOutput {
    if (!raw) return this.emptyYin()

    const validBaseTypes = ['grounding', 'constraint', 'reality_check', 'prioritization', 'risk_assessment']
    const baselineBranches: YinBaselineBranch[] = (raw.baselines || [])
      .map((b: any, i: number) => ({
        id: `consolidated-yin-${i}`,
        type: validBaseTypes.includes(b.type) ? b.type : 'grounding',
        content: String(b.content || ''),
        confidence: Math.max(0, Math.min(1, Number(b.confidence) || 0.5)),
        relevanceScore: Math.max(0, Math.min(1, Number(b.relevanceScore) || 0.5)),
      }))
      .filter((b: YinBaselineBranch) => b.content.length > 0)

    const validActions: import('../../../types/dialectic.js').YinAction[] = ['surface', 'compress', 'discard']
    const yangBranches = yangRaw?.branches || []
    const selfCritiques: YinCritique[] = (raw.critiques || [])
      .map((c: any) => {
        const branchIdx = Number(c.yangBranchIndex) || 0
        // Support legacy 'keep'→'surface', 'flag'→'compress', old 'refine'→'compress', 'ignore'→'discard'
        const legacyMap: Record<string, import('../../../types/dialectic.js').YinAction> = { keep: 'surface', flag: 'compress', refine: 'compress', ignore: 'discard' }
        const rawAction = legacyMap[c.action] ?? c.action
        const action = (validActions.includes(rawAction) ? rawAction : 'surface') as import('../../../types/dialectic.js').YinAction
        return {
          yangBranchId: yangBranches[branchIdx]
            ? `consolidated-yang-${branchIdx}`
            : `consolidated-yang-0`,
          valid: action !== 'discard',
          essence: c.essence,
          critique: String(c.critique || ''),
          relevance: Math.max(0, Math.min(1, Number(c.relevance) || 0.5)),
          action,
        }
      })
      .filter((c: YinCritique) => c.critique.length > 0)

    return {
      baselineBranches,
      selfCritiques,
      meta: {
        compressionRatio: 1,
        processingTimeMs: 0,
        inputTokens: 0,
        outputTokens: 0,
        relativeTiming: 'concurrent',
      },
    }
  }

  private parseSerenity(raw: any): SerenityOutput {
    if (!raw) return this.emptySerenity()

    const validSignalTypes: SignalType[] = ['edge_case', 'alternative', 'assumption', 'connection', 'contradiction', 'convergence', 'tension', 'gap']
    const validUrgency: Urgency[] = ['immediate', 'background']

    const hasSignal = raw.hasSignal === true && !!raw.signal?.content
    const signal = hasSignal ? {
      type: (validSignalTypes.includes(raw.signal.type) ? raw.signal.type : 'convergence') as SignalType,
      content: String(raw.signal.content || ''),
      confidence: Math.max(0, Math.min(1, Number(raw.signal.confidence) || 0.5)),
      sourceBranches: [] as string[],
      urgency: (validUrgency.includes(raw.signal.urgency) ? raw.signal.urgency : 'background') as Urgency,
    } : undefined

    return {
      synthesis: {
        hasSignal,
        signal,
        branchesConsidered: Number(raw.branchesConsidered) || 0,
        branchesSurfaced: Number(raw.branchesSurfaced) || 0,
      },
      meta: {
        dialecticQuality: Math.max(0, Math.min(1, Number(raw.dialecticQuality) || 0.5)),
        processingTimeMs: 0,
        inputTokens: 0,
        outputTokens: 0,
      },
    }
  }

  // ── Provider Call ────────────────────────────────────────────────────────

  private async callProvider(
    provider: IProvider,
    prompt: string,
    model: string,
    signal?: AbortSignal,
  ): Promise<string> {
    const messages = [{ role: 'user' as const, content: prompt }]
    const stream = (provider as any).complete(messages, {
      model,
      maxTokens: 2000,
      temperature: this.config.temperature,
      thinking: 'off',
      allowConcurrent: true,
      dedupe: false,
    }, undefined, signal)

    let fullText = ''
    for await (const chunk of stream) {
      if (chunk.type === 'token') fullText += chunk.text
      else if (chunk.type === 'done') break
    }
    return fullText
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  private resolveProvider(opts?: ConsolidatedOptions): IProvider | undefined {
    if (opts?.providers?.consolidated) {
      const hint = opts.providers.consolidated
      if (typeof hint === 'object' && 'complete' in hint) return hint as IProvider
    }
    return this.provider
  }

  private resolveModel(opts?: ConsolidatedOptions): string {
    if (opts?.providers?.consolidated) {
      const hint = opts.providers.consolidated
      if (typeof hint === 'object' && 'model' in hint && !('complete' in hint)) {
        return (hint as { model: string }).model
      }
    }
    return this.config.model
  }

  private calculateAgreement(yang: YangOutput, yin: YinBaselineOutput): number {
    if (!yang.branches.length || !yin.selfCritiques.length) return 0.5
    const validCount = yin.selfCritiques.filter(c => c.valid).length
    return validCount / yin.selfCritiques.length
  }

  private calculateTension(yang: YangOutput, yin: YinBaselineOutput): number {
    if (!yang.branches.length) return 0
    const typeSet = new Set(yang.branches.map(b => b.type))
    return Math.min(1, typeSet.size / 3) // Diversity of thought
  }

  private emptyYang(): YangOutput {
    return {
      branches: [],
      meta: { expansionTemperature: this.config.temperature, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 },
    }
  }

  private emptyYin(): YinBaselineOutput {
    return {
      baselineBranches: [],
      selfCritiques: [],
      meta: { compressionRatio: 1, processingTimeMs: 0, inputTokens: 0, outputTokens: 0, relativeTiming: 'concurrent' },
    }
  }

  private emptySerenity(): SerenityOutput {
    return {
      synthesis: { hasSignal: false, branchesConsidered: 0, branchesSurfaced: 0 },
      meta: { dialecticQuality: 0, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 },
    }
  }

  private createEmptyResult(sessionId: string, turnId: string, startTime: number): ParallelDialecticResult {
    return {
      sessionId,
      turnId,
      timestamp: startTime,
      level: 0,
      executionMode: 'parallel',
      yang: this.emptyYang(),
      yin: this.emptyYin(),
      serenity: this.emptySerenity(),
      signalInjected: false,
      totalLatencyMs: Date.now() - startTime,
      totalCostUsd: 0,
      timing: { yangDuration: 0, yinDuration: 0, serenityDuration: 0, totalParallelTime: 0, firstCompletion: 'yang' },
      quality: { yangYinAgreement: 0, dialecticTension: 0, synthesisConfidence: 0 },
    }
  }
}

// ─── Factory ─────────────────────────────────────────────────────────────────

export function createConsolidatedDialecticProcessor(
  logger: ILogger,
  config?: Partial<ConsolidatedConfig>,
): ConsolidatedDialecticProcessor {
  return new ConsolidatedDialecticProcessor(logger, config)
}
