/**
 * DialecticEngine — Pure reasoning kernel
 *
 * String in → String out. No side effects, no sessions, no persistence.
 *
 * Data flow:
 *   Input → Yang ∥ Yin (parallel, independent) → Unity (arbitration)
 *
 * Yang and Yin each independently work the problem. Unity reviews both
 * and selects Option A (Yang), Option B (Yin), or Option C (custom synthesis).
 *
 * Usage:
 *   const engine = new DialecticEngine(logger)
 *   engine.setProvider(provider)
 *
 *   // Simple: string → string
 *   const result = await engine.reason("Should we use Redis or Postgres for this cache?")
 *
 *   // Structured: for training data, debugging, inspection
 *   const structured = await engine.reasonStructured("Should we use Redis or Postgres?")
 *   // structured.yang, structured.yin, structured.unity, structured.output
 */

import type { ILogger } from '@cassicore/foundation'
import type { IProvider } from '@cassicore/foundation'
import type {
  DialecticEngineConfig,
  ReasonOptions,
  DialecticStructuredResult,
  EngineDialecticMode as DialecticMode,
  IDialecticEngine,
  YangApproach,
  EngineYangBranch as YangBranch,
  YangBranchType,
  YinApproach,
  YinBaseline,
  YinBaselineType,
  YinCritique,
  UnityDecision,
  UnitySelection,
  DialecticEngineSignal,
  DialecticSignalType,
} from '@cassicore/foundation'

// Default Configuration ─────────────────────────────────────────

const DEFAULT_CONFIG: DialecticEngineConfig = {
  maxBranches: 3,
  yangTemperature: 0.8,
  yinTemperature: 0.3,
  unityTemperature: 0.4,
  model: 'gpt-4o',
  maxTokens: 2000,
  postureTimeoutMs: 30_000,
}

// Prompts ───────────────────────────────────────────────────────

function buildYangPrompt(input: string, context: string | undefined, maxBranches: number): string {
  const parts: string[] = []

  parts.push(`You are YANG — the principle of expansion and creative exploration.

You will produce an independent approach to the input below. Your job is to think broadly:
explore alternatives, challenge assumptions, find edge cases, and consider cross-domain insights.

Your response has two parts:
1. A recommended RESPONSE — your best approach to addressing the input
2. Supporting BRANCHES — the expansive observations that inform your approach`)

  if (context) {
    parts.push(`## CONTEXT
${context}`)
  }

  parts.push(`## INPUT
"""${input.slice(0, 4000)}"""

## INSTRUCTIONS

Produce your output as valid JSON — no markdown fences, no commentary.

{
  "response": "Your recommended approach/response to the input (2-6 sentences of well-reasoned guidance)",
  "branches": [
    {
      "type": "alternative_interpretation | edge_case | cross_domain | what_if | assumption_challenge",
      "content": "The observation (2-4 sentences)",
      "confidence": 0.0-1.0,
      "novelty": 0.0-1.0
    }
  ]
}

Generate ${maxBranches} branches using diverse types. Each branch should pass the surprise test:
would this make someone pause and reconsider? If not, find a more interesting angle.

Your RESPONSE should synthesize your branches into actionable guidance — not just list findings.

Return ONLY valid JSON.`)

  return parts.join('\n\n')
}

function buildYinPrompt(input: string, context: string | undefined): string {
  const parts: string[] = []

  parts.push(`You are YIN — the principle of grounding and rigorous assessment.

You will produce an independent approach to the input below. Your job is to think carefully:
identify constraints, check assumptions against reality, assess risks, and prioritize what matters.

Your response has two parts:
1. A recommended RESPONSE — your best approach, grounded in practical constraints
2. Supporting BASELINES — the grounding observations that inform your approach`)

  if (context) {
    parts.push(`## CONTEXT
${context}`)
  }

  parts.push(`## INPUT
"""${input.slice(0, 4000)}"""

## INSTRUCTIONS

Produce your output as valid JSON — no markdown fences, no commentary.

{
  "response": "Your recommended approach/response to the input (2-6 sentences of well-reasoned, grounded guidance)",
  "baselines": [
    {
      "type": "grounding | constraint | reality_check | prioritization | risk_assessment",
      "content": "The assessment (2-4 sentences)",
      "confidence": 0.0-1.0,
      "relevance": 0.0-1.0
    }
  ]
}

Generate 2-4 baselines using diverse types. Focus on what the input DOESN'T say — implicit
assumptions, hidden constraints, unstated priorities, and risks that aren't being considered.

Your RESPONSE should be practical and actionable. If the expansive approach is wrong, say so directly.

Return ONLY valid JSON.`)

  return parts.join('\n\n')
}

function buildUnityPrompt(
  input: string,
  yangApproach: YangApproach,
  yinApproach: YinApproach,
): string {
  const yangBranchSummary = yangApproach.branches
    .map((b, i) => `  ${i + 1}. [${b.type}] ${b.content} (confidence: ${b.confidence})`)
    .join('\n')

  const yinBaselineSummary = yinApproach.baselines
    .map((b, i) => `  ${i + 1}. [${b.type}] ${b.content} (relevance: ${b.relevance})`)
    .join('\n')

  return `You are UNITY — the principle of arbitration and synthesis.

Two independent approaches have been developed for the input below. You must review both and make a decision.

## ORIGINAL INPUT
"""${input.slice(0, 3000)}"""

## OPTION A — Yang's Approach (Expansive)
Response: ${yangApproach.response}

Supporting observations:
${yangBranchSummary || '  (none)'}

## OPTION B — Yin's Approach (Grounded)
Response: ${yinApproach.response}

Supporting observations:
${yinBaselineSummary || '  (none)'}

## YOUR TASK

Compare both approaches and select the best option:
- **A**: Yang's approach is clearly better — use it as-is
- **B**: Yin's approach is clearly better — use it as-is
- **C**: Neither is sufficient alone — create a custom synthesis combining the best of both

Evaluate on: correctness, completeness, actionability, and whether it actually addresses the input.

Produce your output as valid JSON — no markdown fences, no commentary.

{
  "selected": "A" | "B" | "C",
  "output": "The final response — either the selected approach verbatim, or your custom synthesis (2-8 sentences)",
  "reasoning": "Why you chose this option (1-3 sentences)",
  "comparison": {
    "yangStrengths": "What Yang got right (1 sentence)",
    "yangWeaknesses": "What Yang missed or got wrong (1 sentence)",
    "yinStrengths": "What Yin got right (1 sentence)",
    "yinWeaknesses": "What Yin missed or got wrong (1 sentence)"
  },
  "synthesis": null,
  "confidence": 0.0-1.0,
  "signal": {
    "type": "edge_case | alternative | assumption | connection | contradiction | convergence | tension | gap",
    "content": "The single most important insight from this dialectic (1-2 sentences, or null if nothing noteworthy)",
    "confidence": 0.0-1.0,
    "urgency": "immediate | background"
  }
}

If you select C, populate the "synthesis" field:
{
  "synthesis": {
    "fromYang": "What you took from Yang's approach",
    "fromYin": "What you took from Yin's approach",
    "novel": "What you added that neither had"
  }
}

If no dialectic signal is genuinely noteworthy, set "signal" to null.

Return ONLY valid JSON.`
}

// JSON Helpers ──────────────────────────────────────────────────

function extractJson(text: string): string {
  let cleaned = text.trim()
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '')
  }
  const start = cleaned.indexOf('{')
  const end = cleaned.lastIndexOf('}')
  if (start >= 0 && end > start) {
    return cleaned.slice(start, end + 1)
  }
  return cleaned
}

function repairJson(text: string): string {
  let s = text
  // Strip JS-style comments
  s = s.replace(/\/\/[^\n]*/g, '')
  s = s.replace(/\/\*[\s\S]*?\*\//g, '')
  // Bare-word values
  s = s.replace(
    /:\s*(?!true\b|false\b|null\b|"|\[|\{|-?\d)([a-zA-Z_]\w*(?:[- ]\w+)*)/g,
    ': "$1"',
  )
  // Unquoted keys
  s = s.replace(/([{,]\s*)([a-zA-Z_]\w*)\s*:/g, '$1"$2":')
  // Single-quoted strings
  s = s.replace(/'([^'\\]*(?:\\.[^'\\]*)*)'/g, '"$1"')
  // Trailing commas
  s = s.replace(/,\s*([}\]])/g, '$1')
  // NaN / Infinity
  s = s.replace(/:\s*NaN\b/g, ': null')
  s = s.replace(/:\s*-?Infinity\b/g, ': null')
  return s
}

function safeJsonParse(text: string): any | null {
  const jsonStr = extractJson(text)
  try {
    return JSON.parse(jsonStr)
  } catch {
    try {
      return JSON.parse(repairJson(jsonStr))
    } catch {
      return null
    }
  }
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v))
}

// Response Parsers ──────────────────────────────────────────────

const VALID_YANG_TYPES: YangBranchType[] = [
  'alternative_interpretation', 'edge_case', 'cross_domain', 'what_if', 'assumption_challenge',
]

const VALID_YIN_TYPES: YinBaselineType[] = [
  'grounding', 'constraint', 'reality_check', 'prioritization', 'risk_assessment',
]

const VALID_SIGNAL_TYPES: DialecticSignalType[] = [
  'edge_case', 'alternative', 'assumption', 'connection',
  'contradiction', 'convergence', 'tension', 'gap',
]

function parseYangResponse(text: string, latencyMs: number, model?: string): YangApproach {
  const raw = safeJsonParse(text)
  if (!raw) {
    return {
      response: text.slice(0, 2000),
      branches: [],
      meta: { latencyMs, model },
    }
  }

  const branches: YangBranch[] = (raw.branches || [])
    .map((b: any) => ({
      type: VALID_YANG_TYPES.includes(b.type) ? b.type as YangBranchType : 'what_if' as const,
      content: String(b.content || ''),
      confidence: clamp(Number(b.confidence) || 0.5, 0, 1),
      novelty: clamp(Number(b.novelty ?? b.noveltyScore) || 0.5, 0, 1),
    }))
    .filter((b: YangBranch) => b.content.length > 0)

  return {
    response: String(raw.response || text.slice(0, 2000)),
    branches,
    meta: { latencyMs, model },
  }
}

function parseYinResponse(text: string, latencyMs: number, model?: string): YinApproach {
  const raw = safeJsonParse(text)
  if (!raw) {
    return {
      response: text.slice(0, 2000),
      baselines: [],
      critiques: [],
      meta: { latencyMs, model },
    }
  }

  const baselines: YinBaseline[] = (raw.baselines || [])
    .map((b: any) => ({
      type: VALID_YIN_TYPES.includes(b.type) ? b.type as YinBaselineType : 'grounding' as const,
      content: String(b.content || ''),
      confidence: clamp(Number(b.confidence) || 0.5, 0, 1),
      relevance: clamp(Number(b.relevance ?? b.relevanceScore) || 0.5, 0, 1),
    }))
    .filter((b: YinBaseline) => b.content.length > 0)

  return {
    response: String(raw.response || text.slice(0, 2000)),
    baselines,
    critiques: [], // Critiques are not self-generated — Unity produces them if needed
    meta: { latencyMs, model },
  }
}

function parseUnityResponse(
  text: string,
  latencyMs: number,
  model?: string,
): { decision: UnityDecision; signal: DialecticEngineSignal | null } {
  const raw = safeJsonParse(text)
  if (!raw) {
    return {
      decision: {
        selected: 'C' as const,
        output: text.slice(0, 2000),
        reasoning: 'Parse failed — returning raw Unity output',
        comparison: {
          yangStrengths: '',
          yangWeaknesses: '',
          yinStrengths: '',
          yinWeaknesses: '',
        },
        confidence: 0.3,
        meta: { latencyMs, model },
      },
      signal: null,
    }
  }

  const validSelections: UnitySelection[] = ['A', 'B', 'C']
  const selected = validSelections.includes(raw.selected)
    ? raw.selected as UnitySelection
    : 'C' as const

  const decision: UnityDecision = {
    selected,
    output: String(raw.output || ''),
    reasoning: String(raw.reasoning || ''),
    comparison: {
      yangStrengths: String(raw.comparison?.yangStrengths || ''),
      yangWeaknesses: String(raw.comparison?.yangWeaknesses || ''),
      yinStrengths: String(raw.comparison?.yinStrengths || ''),
      yinWeaknesses: String(raw.comparison?.yinWeaknesses || ''),
    },
    synthesis: selected === 'C' && raw.synthesis ? {
      fromYang: String(raw.synthesis.fromYang || ''),
      fromYin: String(raw.synthesis.fromYin || ''),
      novel: String(raw.synthesis.novel || ''),
    } : undefined,
    confidence: clamp(Number(raw.confidence) || 0.5, 0, 1),
    meta: { latencyMs, model },
  }

  let signal: DialecticEngineSignal | null = null
  if (raw.signal && raw.signal.content) {
    signal = {
      type: VALID_SIGNAL_TYPES.includes(raw.signal.type)
        ? raw.signal.type as DialecticSignalType
        : 'convergence' as const,
      content: String(raw.signal.content),
      confidence: clamp(Number(raw.signal.confidence) || 0.5, 0, 1),
      urgency: raw.signal.urgency === 'immediate' ? 'immediate' : 'background',
    }
  }

  return { decision, signal }
}

// Quality Metrics ───────────────────────────────────────────────

function calculateAgreement(yang: YangApproach, yin: YinApproach): number {
  const tokenize = (s: string) => new Set(
    s.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 3),
  )

  const jaccard = (a: Set<string>, b: Set<string>) => {
    const intersection = [...a].filter(x => b.has(x)).length
    const union = new Set([...a, ...b]).size
    return union === 0 ? 0 : intersection / union
  }

  return jaccard(tokenize(yang.response), tokenize(yin.response))
}

function calculateTension(yang: YangApproach, yin: YinApproach): number {
  return 1 - calculateAgreement(yang, yin)
}

// Provider Call ─────────────────────────────────────────────────

async function callProvider(
  provider: IProvider,
  prompt: string,
  opts: { model: string; temperature: number; maxTokens: number; signal?: AbortSignal },
): Promise<string> {
  const messages = [{ role: 'user' as const, content: prompt }]

  const slashIdx = opts.model.indexOf('/')
  const modelName = slashIdx >= 0 ? opts.model.slice(slashIdx + 1) : opts.model

  const stream = (provider as any).complete(messages, {
    model: modelName,
    maxTokens: opts.maxTokens,
    temperature: opts.temperature,
    thinking: 'off',
    allowConcurrent: true,
    dedupe: false,
    source: 'dialectic-engine',
  }, undefined, opts.signal) as AsyncIterable<any>

  let text = ''
  for await (const chunk of stream) {
    if (chunk.type === 'token') text += chunk.text
    else if (chunk.type === 'done') break
  }
  return text
}

// Engine Implementation ─────────────────────────────────────────

export class DialecticEngine implements IDialecticEngine {
  private logger: ILogger
  private config: DialecticEngineConfig
  private provider: IProvider | undefined

  constructor(logger: ILogger, config?: Partial<DialecticEngineConfig>) {
    this.logger = logger.child?.('dialectic-engine') ?? logger
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider
  }

  async reason(input: string, opts?: ReasonOptions): Promise<string> {
    const result = await this.reasonStructured(input, opts)
    return result.output
  }

  async reasonStructured(input: string, opts?: ReasonOptions): Promise<DialecticStructuredResult> {
    const startTime = Date.now()
    const provider = opts?.provider ?? this.provider
    if (!provider) {
      throw new Error('DialecticEngine: no provider configured. Call setProvider() first.')
    }

    const mode: DialecticMode = opts?.mode ?? 'parallel'
    const model = opts?.model ?? this.config.model
    const maxBranches = opts?.maxBranches ?? this.config.maxBranches

    this.logger.info('DialecticEngine: starting', { mode, model })

    if (mode === 'consolidated') {
      return this.runConsolidated(input, provider, model, opts)
    }

    return this.runParallel(input, provider, model, maxBranches, opts)
  }

  // Parallel Mode: Yang ∥ Yin → Unity ─────────────────────────

  private async runParallel(
    input: string,
    provider: IProvider,
    model: string,
    maxBranches: number,
    opts?: ReasonOptions,
  ): Promise<DialecticStructuredResult> {
    const startTime = Date.now()
    const context = opts?.context

    const yangModel = opts?.models?.yang ?? model
    const yinModel = opts?.models?.yin ?? model
    const unityModel = opts?.models?.unity ?? model

    // Phase 1: Yang and Yin run in parallel
    const yangPrompt = buildYangPrompt(input, context, maxBranches)
    const yinPrompt = buildYinPrompt(input, context)

    const yangStart = Date.now()
    const yinStart = Date.now()

    const [yangText, yinText] = await Promise.all([
      this.callWithTimeout(
        callProvider(provider, yangPrompt, {
          model: yangModel,
          temperature: this.config.yangTemperature,
          maxTokens: this.config.maxTokens,
          signal: opts?.signal,
        }),
        this.config.postureTimeoutMs,
        'yang',
      ),
      this.callWithTimeout(
        callProvider(provider, yinPrompt, {
          model: yinModel,
          temperature: this.config.yinTemperature,
          maxTokens: this.config.maxTokens,
          signal: opts?.signal,
        }),
        this.config.postureTimeoutMs,
        'yin',
      ),
    ])

    const yangApproach = parseYangResponse(yangText, Date.now() - yangStart, yangModel)
    const yinApproach = parseYinResponse(yinText, Date.now() - yinStart, yinModel)

    this.logger.info('DialecticEngine: Yang and Yin complete', {
      yangBranches: yangApproach.branches.length,
      yinBaselines: yinApproach.baselines.length,
      yangLatencyMs: yangApproach.meta.latencyMs,
      yinLatencyMs: yinApproach.meta.latencyMs,
    })

    // Phase 2: Unity arbitrates
    const unityPrompt = buildUnityPrompt(input, yangApproach, yinApproach)
    const unityStart = Date.now()

    const unityText = await this.callWithTimeout(
      callProvider(provider, unityPrompt, {
        model: unityModel,
        temperature: this.config.unityTemperature,
        maxTokens: this.config.maxTokens,
        signal: opts?.signal,
      }),
      this.config.postureTimeoutMs,
      'unity',
    )

    const { decision, signal } = parseUnityResponse(unityText, Date.now() - unityStart, unityModel)

    const totalLatencyMs = Date.now() - startTime
    const agreement = calculateAgreement(yangApproach, yinApproach)

    this.logger.info('DialecticEngine: complete', {
      selected: decision.selected,
      confidence: decision.confidence,
      totalLatencyMs,
      agreement: agreement.toFixed(2),
    })

    return {
      output: decision.output,
      yang: yangApproach,
      yin: yinApproach,
      unity: decision,
      signal,
      quality: {
        dialecticQuality: decision.confidence,
        tension: 1 - agreement,
        agreement,
      },
      meta: {
        totalLatencyMs,
        mode: 'parallel',
      },
    }
  }

  // Consolidated Mode: Single call (fast path) ────────────────

  private async runConsolidated(
    input: string,
    provider: IProvider,
    model: string,
    opts?: ReasonOptions,
  ): Promise<DialecticStructuredResult> {
    const startTime = Date.now()
    const context = opts?.context
    const maxBranches = opts?.maxBranches ?? this.config.maxBranches

    const prompt = this.buildConsolidatedPrompt(input, context, maxBranches)

    const responseText = await this.callWithTimeout(
      callProvider(provider, prompt, {
        model,
        temperature: this.config.unityTemperature,
        maxTokens: Math.round(this.config.maxTokens * 2),
        signal: opts?.signal,
      }),
      this.config.postureTimeoutMs * 2,
      'consolidated',
    )

    const raw = safeJsonParse(responseText)
    const latencyMs = Date.now() - startTime

    if (!raw) {
      return this.fallbackResult(responseText, latencyMs)
    }

    // Parse the consolidated response into the same structure
    const yangApproach = parseYangResponse(JSON.stringify({
      response: raw.yang?.response || '',
      branches: raw.yang?.branches || [],
    }), latencyMs, model)

    const yinApproach = parseYinResponse(JSON.stringify({
      response: raw.yin?.response || '',
      baselines: raw.yin?.baselines || [],
    }), latencyMs, model)

    const { decision, signal } = parseUnityResponse(JSON.stringify({
      selected: raw.unity?.selected || 'C',
      output: raw.unity?.output || raw.output || '',
      reasoning: raw.unity?.reasoning || '',
      comparison: raw.unity?.comparison || {},
      synthesis: raw.unity?.synthesis,
      confidence: raw.unity?.confidence || 0.5,
      signal: raw.signal || raw.unity?.signal,
    }), latencyMs, model)

    const agreement = calculateAgreement(yangApproach, yinApproach)

    return {
      output: decision.output || raw.output || responseText.slice(0, 2000),
      yang: yangApproach,
      yin: yinApproach,
      unity: decision,
      signal,
      quality: {
        dialecticQuality: decision.confidence,
        tension: 1 - agreement,
        agreement,
      },
      meta: {
        totalLatencyMs: latencyMs,
        mode: 'consolidated',
      },
    }
  }

  private buildConsolidatedPrompt(input: string, context: string | undefined, maxBranches: number): string {
    const parts: string[] = []

    parts.push(`You are performing a dialectic analysis with three perspectives.

Phase 1: YANG (expansion) and YIN (grounding) independently analyze the input.
Phase 2: UNITY reviews both and selects the best approach (A=Yang, B=Yin, C=synthesis).`)

    if (context) {
      parts.push(`## CONTEXT\n${context}`)
    }

    parts.push(`## INPUT
"""${input.slice(0, 3000)}"""

## INSTRUCTIONS

Produce ALL sections below as a single valid JSON object. No markdown fences, no commentary.

{
  "yang": {
    "response": "Yang's recommended approach (2-6 sentences)",
    "branches": [
      { "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",
        "content": "2-4 sentences", "confidence": 0.0-1.0, "novelty": 0.0-1.0 }
    ]
  },
  "yin": {
    "response": "Yin's recommended approach (2-6 sentences)",
    "baselines": [
      { "type": "grounding|constraint|reality_check|prioritization|risk_assessment",
        "content": "2-4 sentences", "confidence": 0.0-1.0, "relevance": 0.0-1.0 }
    ]
  },
  "unity": {
    "selected": "A" | "B" | "C",
    "output": "The final selected response",
    "reasoning": "Why this option was selected",
    "comparison": {
      "yangStrengths": "...", "yangWeaknesses": "...",
      "yinStrengths": "...", "yinWeaknesses": "..."
    },
    "synthesis": null,
    "confidence": 0.0-1.0
  },
  "signal": { "type": "...", "content": "...", "confidence": 0.0-1.0, "urgency": "..." } or null
}

Generate ${maxBranches} Yang branches and 2-4 Yin baselines.
Unity MUST genuinely compare the approaches — don't just repeat one of them.

Return ONLY valid JSON.`)

    return parts.join('\n\n')
  }

  // Helpers ───────────────────────────────────────────────────

  private async callWithTimeout<T>(
    promise: Promise<T>,
    timeoutMs: number,
    label: string,
  ): Promise<T> {
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(`DialecticEngine: ${label} timed out after ${timeoutMs}ms`)), timeoutMs),
    )
    return Promise.race([promise, timeoutPromise])
  }

  private fallbackResult(text: string, latencyMs: number): DialecticStructuredResult {
    return {
      output: text.slice(0, 2000),
      yang: { response: '', branches: [], meta: { latencyMs } },
      yin: { response: '', baselines: [], critiques: [], meta: { latencyMs } },
      unity: {
        selected: 'C',
        output: text.slice(0, 2000),
        reasoning: 'Consolidated parse failed — returning raw output',
        comparison: { yangStrengths: '', yangWeaknesses: '', yinStrengths: '', yinWeaknesses: '' },
        confidence: 0.3,
        meta: { latencyMs },
      },
      signal: null,
      quality: { dialecticQuality: 0.3, tension: 0, agreement: 0 },
      meta: { totalLatencyMs: latencyMs, mode: 'consolidated' },
    }
  }
}

// Factory ───────────────────────────────────────────────────────

export function createDialecticEngine(
  logger: ILogger,
  config?: Partial<DialecticEngineConfig>,
): DialecticEngine {
  return new DialecticEngine(logger, config)
}
