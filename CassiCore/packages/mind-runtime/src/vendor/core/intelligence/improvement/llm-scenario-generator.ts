/**
 * LLM-Assisted Scenario Generator — Uses language models to create
 * rich, context-aware verification scenarios when template-based
 * generation is insufficient.
 *
 * Uses constrained generation: the LLM selects from a catalog of
 * pre-validated step/assertion types, and output is schema-validated
 * before storage.
 *
 * Rate-limited and opt-in (disabled by default).
 */

import type { ILogger } from '@cassicore/foundation'
import type { ScenarioStore } from '../../testing/scenarios/scenario-store.js'
import type { WorkflowScenario, StepAction, StepAssertion, ScenarioStep } from '../../testing/verification/scenario-types.js'

export interface LLMScenarioConfig {
  enabled: boolean
  maxGenerationsPerHour: number
  validationStrict: boolean
  temperature: number
}

export const DEFAULT_LLM_SCENARIO_CONFIG: LLMScenarioConfig = {
  enabled: false,
  maxGenerationsPerHour: 10,
  validationStrict: true,
  temperature: 0.3,
}

export interface ScenarioGenRequest {
  description: string
  context?: {
    recentEvents?: string[]
    moduleStates?: Record<string, unknown>
    activeExperiments?: string[]
  }
  constraints?: {
    maxSteps?: number
    maxTimeoutMs?: number
    requiredAssertions?: string[]
    forbiddenActions?: string[]
  }
}

/** Provider router interface (minimal — just what we need) */
interface ProviderRouter {
  generateText(opts: {
    prompt: string
    systemPrompt?: string
    temperature?: number
    maxTokens?: number
  }): Promise<{ text: string }>
}

const SYSTEM_PROMPT = `You are a test scenario generator for CassiCore, a cognitive AI daemon.
Generate workflow verification scenarios as JSON.

AVAILABLE ACTIONS:
- { "type": "turn", "message": "..." }           — Send a user message
- { "type": "wait", "ms": N }                     — Wait N milliseconds
- { "type": "snapshot", "label": "..." }           — Capture state snapshot

AVAILABLE ASSERTIONS:
- { "type": "event-emitted", "event": "..." }
- { "type": "no-event", "event": "..." }
- { "type": "event-count", "event": "...", "min": N, "max": N }
- { "type": "event-sequence", "events": ["...", "..."] }
- { "type": "session-state", "path": "...", "equals": V }
- { "type": "session-state", "path": "...", "greaterThan": N }
- { "type": "session-state", "path": "...", "lessThan": N }
- { "type": "snapshot-diff", "fromLabel": "...", "changed": [...], "unchanged": [...] }
- { "type": "response-contains", "text": "..." }
- { "type": "response-matches", "pattern": "..." }

COMMON EVENT TYPES: turn:start, turn:end, plugin:crashed, intelligence:processor-error, consciousness:anomaly, thinker:insight-applied, dialectic:signal

RULES:
1. Always start with a snapshot step for baseline
2. Each turn step should have at least one assertion
3. End with a verification snapshot comparing to baseline
4. Keep scenarios focused — max 6 steps
5. Use specific, realistic test messages

OUTPUT FORMAT (JSON only, no markdown):
{
  "name": "kebab-case-name",
  "description": "What this scenario tests",
  "timeoutMs": 60000,
  "steps": [...]
}`;

// Valid types for schema validation
const VALID_ACTION_TYPES = new Set(['turn', 'wait', 'snapshot', 'inject-event'])
const VALID_ASSERTION_TYPES = new Set([
  'event-emitted', 'event-sequence', 'no-event', 'event-count',
  'session-state', 'snapshot-diff', 'response-contains', 'response-matches',
])

export class LLMScenarioGenerator {
  private readonly logger: ILogger
  private readonly scenarioStore: ScenarioStore
  private readonly config: LLMScenarioConfig
  private providerRouter?: ProviderRouter

  // Rate limiting
  private generationsThisHour = 0
  private hourResetAt = Date.now() + 3_600_000

  // Cache: description hash → scenario
  private cache = new Map<string, WorkflowScenario>()

  constructor(deps: {
    logger: ILogger
    scenarioStore: ScenarioStore
    config?: Partial<LLMScenarioConfig>
  }) {
    this.logger = deps.logger.child?.('llm-scenario-gen') ?? deps.logger
    this.scenarioStore = deps.scenarioStore
    this.config = { ...DEFAULT_LLM_SCENARIO_CONFIG, ...deps.config }
  }

  /** Set the provider router for LLM calls */
  setProviderRouter(router: ProviderRouter): void {
    this.providerRouter = router
  }

  /** Check if LLM generation is available and enabled */
  isAvailable(): boolean {
    return this.config.enabled && !!this.providerRouter
  }

  /**
   * Generate a scenario from a natural-language description.
   */
  async generate(request: ScenarioGenRequest): Promise<WorkflowScenario | null> {
    if (!this.isAvailable()) {
      this.logger.debug('Not available (disabled or no provider)')
      return null
    }

    // Rate limiting
    if (!this.checkRateLimit()) {
      this.logger.warn('Rate limit reached')
      return null
    }

    // Cache check
    const cacheKey = this.hashRequest(request)
    const cached = this.cache.get(cacheKey)
    if (cached) {
      this.logger.debug('Returning cached scenario', { name: cached.name })
      return cached
    }

    try {
      const prompt = this.buildPrompt(request)
      const result = await this.providerRouter!.generateText({
        prompt,
        systemPrompt: SYSTEM_PROMPT,
        temperature: this.config.temperature,
        maxTokens: 2000,
      })

      const scenario = this.parseAndValidate(result.text, request)
      if (!scenario) return null

      // Cache and store
      this.cache.set(cacheKey, scenario)
      this.scenarioStore.add(scenario, {
        triggerType: 'manual',
        tags: ['generated', 'llm-generated'],
      })

      this.generationsThisHour++
      this.logger.info('Generated scenario', { name: scenario.name })
      return scenario
    } catch (err) {
      this.logger.error('Generation failed', { error: String(err) })
      return null
    }
  }

  /**
   * Enhance an existing scenario with additional context-aware steps.
   */
  async enhance(scenario: WorkflowScenario, context: {
    reason: string
    additionalAssertions?: string[]
  }): Promise<WorkflowScenario | null> {
    if (!this.isAvailable()) return null
    if (!this.checkRateLimit()) return null

    try {
      const prompt = `Enhance this existing verification scenario.

CURRENT SCENARIO:
${JSON.stringify(scenario, null, 2)}

ENHANCEMENT REQUEST: ${context.reason}
${context.additionalAssertions ? `REQUIRED ASSERTIONS: ${context.additionalAssertions.join(', ')}` : ''}

Add 1-2 additional steps that specifically test the enhancement concern.
Do not remove or reorder existing steps — only add new ones.
Return the COMPLETE enhanced scenario as JSON.`

      const result = await this.providerRouter!.generateText({
        prompt,
        systemPrompt: SYSTEM_PROMPT,
        temperature: this.config.temperature,
        maxTokens: 3000,
      })

      const enhanced = this.parseAndValidate(result.text, { description: context.reason })
      if (!enhanced) return null

      // Verify existing steps are preserved
      if (enhanced.steps.length < scenario.steps.length) {
        this.logger.warn('Enhanced scenario has fewer steps — rejected')
        return null
      }

      this.generationsThisHour++
      this.logger.info('Enhanced scenario', {
        name: enhanced.name,
        originalSteps: scenario.steps.length,
        enhancedSteps: enhanced.steps.length,
      })
      return enhanced
    } catch (err) {
      this.logger.error('Enhancement failed', { error: String(err) })
      return null
    }
  }

  /** Get generation stats */
  getStats(): { generationsThisHour: number; cacheSize: number; available: boolean } {
    return {
      generationsThisHour: this.generationsThisHour,
      cacheSize: this.cache.size,
      available: this.isAvailable(),
    }
  }


  private buildPrompt(request: ScenarioGenRequest): string {
    let prompt = `Generate a verification scenario for:\n${request.description}\n`

    if (request.context?.recentEvents?.length) {
      prompt += `\nRECENT EVENTS:\n${request.context.recentEvents.slice(0, 10).join('\n')}\n`
    }
    if (request.context?.moduleStates) {
      prompt += `\nMODULE STATES:\n${JSON.stringify(request.context.moduleStates, null, 2)}\n`
    }
    if (request.constraints) {
      const c = request.constraints
      prompt += '\nCONSTRAINTS:\n'
      if (c.maxSteps) prompt += `- Maximum ${c.maxSteps} steps\n`
      if (c.maxTimeoutMs) prompt += `- Maximum timeout: ${c.maxTimeoutMs}ms\n`
      if (c.requiredAssertions?.length) prompt += `- Must include assertions: ${c.requiredAssertions.join(', ')}\n`
      if (c.forbiddenActions?.length) prompt += `- Do NOT use actions: ${c.forbiddenActions.join(', ')}\n`
    }

    return prompt
  }

  private parseAndValidate(text: string, request: ScenarioGenRequest | { description: string }): WorkflowScenario | null {
    // Extract JSON from response (may be wrapped in markdown code blocks)
    const jsonMatch = text.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      this.logger.warn('No JSON found in response')
      return null
    }

    let parsed: any
    try {
      parsed = JSON.parse(jsonMatch[0])
    } catch (err) {
      this.logger.warn('JSON parse failed', { error: String(err) })
      return null
    }

    // Schema validation
    if (!parsed.name || typeof parsed.name !== 'string') {
      parsed.name = `llm-${Date.now()}`
    }
    if (!parsed.description || typeof parsed.description !== 'string') {
      parsed.description = 'description' in request ? request.description : 'LLM-generated scenario'
    }
    if (!Array.isArray(parsed.steps) || parsed.steps.length === 0) {
      this.logger.warn('No valid steps in generated scenario')
      return null
    }

    // Validate and sanitize steps
    const validSteps: ScenarioStep[] = []
    for (const step of parsed.steps) {
      const validatedStep = this.validateStep(step)
      if (validatedStep) validSteps.push(validatedStep)
    }

    if (validSteps.length === 0) {
      this.logger.warn('No valid steps after validation')
      return null
    }

    // Apply constraints
    const maxSteps = ('constraints' in request && request.constraints?.maxSteps) || 6
    if (validSteps.length > maxSteps) {
      validSteps.length = maxSteps
    }

    const timeoutMs = parsed.timeoutMs && typeof parsed.timeoutMs === 'number'
      ? Math.min(parsed.timeoutMs, ('constraints' in request && request.constraints?.maxTimeoutMs) || 120_000)
      : 60_000

    // Ensure name is kebab-case and unique
    const name = `llm-${parsed.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50)}`

    return {
      name,
      description: parsed.description,
      timeoutMs,
      steps: validSteps,
    }
  }

  private validateStep(step: any): ScenarioStep | null {
    if (!step || typeof step !== 'object') return null
    if (!step.action || typeof step.action !== 'object') return null

    // Validate action
    const action = step.action as any
    if (!VALID_ACTION_TYPES.has(action.type)) return null

    let validAction: StepAction
    switch (action.type) {
      case 'turn':
        if (typeof action.message !== 'string') return null
        validAction = { type: 'turn', message: action.message }
        break
      case 'wait':
        if (typeof action.ms !== 'number') return null
        validAction = { type: 'wait', ms: Math.min(action.ms, 30_000) }
        break
      case 'snapshot':
        if (typeof action.label !== 'string') return null
        validAction = { type: 'snapshot', label: action.label }
        break
      default:
        return null
    }

    // Validate assertions
    const validAssertions: StepAssertion[] = []
    if (Array.isArray(step.assertions)) {
      for (const assertion of step.assertions) {
        const validated = this.validateAssertion(assertion)
        if (validated) validAssertions.push(validated)
      }
    }

    return {
      label: typeof step.label === 'string' ? step.label : undefined,
      action: validAction,
      assertions: validAssertions.length > 0 ? validAssertions : undefined,
    }
  }

  private validateAssertion(assertion: any): StepAssertion | null {
    if (!assertion || typeof assertion !== 'object') return null
    if (!VALID_ASSERTION_TYPES.has(assertion.type)) return null

    // Basic type validation for each assertion type
    switch (assertion.type) {
      case 'event-emitted':
        if (typeof assertion.event !== 'string') return null
        return { type: 'event-emitted', event: assertion.event as any, ...(assertion.has ? { has: assertion.has } : {}) }
      case 'no-event':
        if (typeof assertion.event !== 'string') return null
        return { type: 'no-event', event: assertion.event as any }
      case 'event-count':
        if (typeof assertion.event !== 'string') return null
        return { type: 'event-count', event: assertion.event as any, min: assertion.min, max: assertion.max, exact: assertion.exact }
      case 'event-sequence':
        if (!Array.isArray(assertion.events)) return null
        return { type: 'event-sequence', events: assertion.events as any }
      case 'session-state':
        if (typeof assertion.path !== 'string') return null
        return { type: 'session-state', path: assertion.path, equals: assertion.equals, greaterThan: assertion.greaterThan, lessThan: assertion.lessThan, contains: assertion.contains }
      case 'snapshot-diff':
        if (typeof assertion.fromLabel !== 'string') return null
        return { type: 'snapshot-diff', fromLabel: assertion.fromLabel, changed: assertion.changed, unchanged: assertion.unchanged }
      case 'response-contains':
        if (typeof assertion.text !== 'string') return null
        return { type: 'response-contains', text: assertion.text }
      case 'response-matches':
        if (typeof assertion.pattern !== 'string') return null
        return { type: 'response-matches', pattern: assertion.pattern }
      default:
        return null
    }
  }

  private checkRateLimit(): boolean {
    const now = Date.now()
    if (now > this.hourResetAt) {
      this.generationsThisHour = 0
      this.hourResetAt = now + 3_600_000
    }
    return this.generationsThisHour < this.config.maxGenerationsPerHour
  }

  private hashRequest(request: ScenarioGenRequest): string {
    // Simple hash from description + constraints
    const key = `${request.description}:${JSON.stringify(request.constraints ?? {})}`
    let hash = 0
    for (let i = 0; i < key.length; i++) {
      hash = ((hash << 5) - hash) + key.charCodeAt(i)
      hash |= 0
    }
    return `gen-${hash.toString(36)}`
  }
}
