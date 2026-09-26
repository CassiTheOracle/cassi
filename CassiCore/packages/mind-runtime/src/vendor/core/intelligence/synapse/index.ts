/**
 * Synapse — Per-Posture Guidance Brain
 *
 * The Synapse sits at the junction between a posture's thinking and the
 * intelligence layer. It receives a thought from the axon (collect_thoughts),
 * processes it through an LLM with energy-adaptive prompting, and transmits
 * guidance back.
 *
 * Gating Rules:
 *   - step >= 2
 *   - budget > 0
 *   - AND (signals confidence >= 0.7 OR is_revision OR branch_from_step OR step % 3 === 0)
 *
 * Budget: 5 calls/session
 * Timeout: 3000ms
 */

import type { ILogger } from '@cassicore/foundation'
import type {
  SynapseConfig,
  SynapseContext,
  SynapseGuidance,
  SynapseGatingResult,
  SynapseDeps,
  PostureEnergy,
  GuidanceType,
  GuidanceEffectiveness,
} from './types.js'
import { DEFAULT_SYNAPSE_CONFIG } from './types.js'


/** Default budget for Synapse calls per session */
const DEFAULT_BUDGET = 5

/** Default timeout for LLM calls in milliseconds */
const DEFAULT_TIMEOUT_MS = 3000

/** Default signal confidence threshold */
const DEFAULT_SIGNAL_THRESHOLD = 0.7


/**
 * Per-posture guidance brain that processes reasoning steps through an LLM
 * to generate tactical guidance.
 *
 * GWT Integration:
 * - Broadcasts guidance to Global Workspace for cross-posture visibility
 * - Uses Thalamus-curated context when available
 * - Stores guidance in Cortex working memory for effectiveness tracking
 */
export class Synapse {
  private config: SynapseConfig
  private deps: SynapseDeps
  private log: ILogger

  /** Per-session budget tracking: sessionId -> remaining calls */
  private sessionBudgets = new Map<string, number>()
  /** Guidance history for effectiveness tracking */
  private guidanceHistory = new Map<string, SynapseGuidance[]>()
  /** Effectiveness tracking: sessionId -> effectiveness records */
  private effectivenessRecords = new Map<string, GuidanceEffectiveness[]>()

  constructor(deps: SynapseDeps, config?: Partial<SynapseConfig>) {
    this.deps = deps
    this.config = { ...DEFAULT_SYNAPSE_CONFIG, ...config }
    this.log = deps.logger.child?.('synapse') ?? deps.logger
  }

  /**
   * Evaluate gating rules to determine if Synapse should fire.
   *
   * Gating rules:
   *   - step >= 2 (skip first step — too early for guidance)
   *   - budget > 0 (session has remaining calls)
   *   - AND at least one of:
   *     - signals confidence >= threshold (high-confidence signals present)
   *     - is_revision (reconsidering a previous step)
   *     - branch_from_step (creating a new branch)
   *     - step % 3 === 0 (periodic check-in every 3 steps)
   */
  shouldFire(
    thoughtNumber: number,
    sessionId: string,
    signals: Array<{ confidence: number }>,
    isRevision: boolean,
    branchFromThought: number | undefined,
  ): SynapseGatingResult {
    // Check basic prerequisites
    if (!this.config.enabled) {
      return { shouldFire: false, reason: 'synapse disabled' }
    }

    if (thoughtNumber < 2) {
      return { shouldFire: false, reason: 'too early (step < 2)' }
    }

    // Check budget
    const remaining = this.getRemainingBudget(sessionId)
    if (remaining <= 0) {
      return { shouldFire: false, reason: 'budget exhausted' }
    }

    // Check trigger conditions
    const hasHighConfidenceSignal = signals.some(
      (s) => s.confidence >= this.config.signalThreshold,
    )
    const isPeriodicCheckin = thoughtNumber % this.config.interval === 0
    const isBranching = branchFromThought !== undefined

    if (hasHighConfidenceSignal) {
      return { shouldFire: true, reason: 'high-confidence signal detected' }
    }

    if (isRevision) {
      return { shouldFire: true, reason: 'revision step' }
    }

    if (isBranching) {
      return { shouldFire: true, reason: 'branching step' }
    }

    if (isPeriodicCheckin) {
      return { shouldFire: true, reason: 'periodic check-in' }
    }

    return { shouldFire: false, reason: 'no trigger condition met' }
  }

  /**
   * Generate guidance for the current reasoning step.
   * This consumes one unit of budget from the session.
   */
  async generateGuidance(
    context: SynapseContext,
    sessionId: string,
  ): Promise<SynapseGuidance | null> {
    // Double-check budget before consuming
    const remaining = this.getRemainingBudget(sessionId)
    if (remaining <= 0) {
      this.log.warn('generateGuidance called with exhausted budget', { sessionId })
      return null
    }

    // Consume budget
    this.sessionBudgets.set(sessionId, remaining - 1)

    try {
      const prompt = this.buildPrompt(context)
      const startTime = Date.now()

      this.log.debug('Synapse LLM call starting', {
        sessionId,
        step: context.currentStep.number,
        remaining: remaining - 1,
      })

      const llmPromise = this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      // Race against internal timeout as a safety net
      const timeoutPromise = new Promise<null>((resolve) =>
        setTimeout(() => resolve(null), this.config.timeoutMs + 500),
      )
      const response = await Promise.race([llmPromise, timeoutPromise])

      if (!response) {
        this.log.warn('Synapse LLM call timed out', { sessionId, step: context.currentStep.number })
        return null
      }

      const duration = Date.now() - startTime
      this.log.debug('Synapse LLM call completed', {
        sessionId,
        duration,
        truncated: response.truncated,
      })

      const guidance = this.parseGuidance(response.content, sessionId, context.currentStep.number, context.energy)

      // Broadcast to Global Workspace for cross-posture visibility
      if (this.config.broadcastToWorkspace && this.deps.globalWorkspace) {
        this.deps.globalWorkspace.submit({
          type: 'synapse:guidance',
          content: `${guidance.type}: ${guidance.observation}`,
          source: 'synapse',
          priority: guidance.confidence,
        })
      }

      // Store in Cortex working memory for effectiveness tracking
      if (this.config.trackEffectiveness && this.deps.cortex) {
        this.deps.cortex.signal(
          'working',
          'guidance',
          `${guidance.type} at step ${guidance.stepNumber}: ${guidance.observation}`,
          { tags: ['synapse', guidance.type, sessionId], salience: guidance.confidence },
        )
      }

      // Track guidance history
      if (this.config.trackEffectiveness) {
        const history = this.guidanceHistory.get(sessionId) ?? []
        history.push(guidance)
        this.guidanceHistory.set(sessionId, history)
      }

      return guidance
    } catch (error) {
      this.log.error('Synapse LLM call failed', {
        sessionId,
        error: error instanceof Error ? error.message : String(error),
      })
      // Don't consume budget on failure — allow retry
      this.sessionBudgets.set(sessionId, remaining)
      return null
    }
  }

  /**
   * Get remaining budget for a session.
   */
  getRemainingBudget(sessionId: string): number {
    return this.sessionBudgets.get(sessionId) ?? this.config.maxCallsPerSession
  }

  /**
   * Reset budget for a session (e.g., when session ends).
   */
  resetBudget(sessionId: string): void {
    this.sessionBudgets.delete(sessionId)
  }

  /**
   * Build energy-adaptive prompt based on context.
   * Uses Thalamus-curated context when available for better guidance quality.
   */
  private buildPrompt(context: SynapseContext): string {
    const energy = context.energy ?? 'neutral'
    const tone = this.getEnergyTone(energy)

    // Use curated context if available, otherwise fall back to raw tree
    const contextText = this.config.useCuratedContext && context.curatedContext
      ? context.curatedContext
      : context.tree

    const signalsText = this.formatSignals(context.signals)
    const peerSignalsText = this.formatSignals(context.peerSignals)
    const memoryText = context.relatedMemory.length > 0
      ? context.relatedMemory.map((m) => `- ${m}`).join('\n')
      : '(none)'
    const resonanceText = context.resonance.length > 0
      ? context.resonance.map((r) => `- ${r.kind}: "${r.signalA.signal.text?.slice(0, 60) ?? '?'}" (${(r.amplifiedConfidence * 100).toFixed(0)}%)`).join('\n')
      : '(none)'
    const workspaceText = context.workspaceFocus
      ? `**Global Workspace Focus:** ${context.workspaceFocus}`
      : ''
    const previousGuidanceText = context.previousGuidance && context.previousGuidance.length > 0
      ? context.previousGuidance.slice(-3).map(g => `- Step ${g.stepNumber} [${g.type}]: ${g.observation}`).join('\n')
      : '(none)'

    return `You are the Synapse — a GWT-aware guidance brain that provides tactical reasoning guidance across the cognitive system.

${tone}

## Reasoning Context

**Current Step (${context.currentStep.number}):** ${context.currentStep.content}

**Context:** ${contextText}

${workspaceText ? `${workspaceText}\n\n` : ''}
**Cognitive Signals:**
${signalsText}

**Peer Signals:**
${peerSignalsText}

**Related Memory:**
${memoryText}

**Resonance Patterns:**
${resonanceText}

**Previous Guidance:**
${previousGuidanceText}

${context.isRevision ? `**This is a REVISION of step ${context.revisesStep}**` : ''}

## Your Task

Provide structured tactical guidance as JSON:

\`\`\`json
{
  "type": "observation|branch|risk|synthesis|focus|correction",
  "observation": "1-2 sentence observation about the current reasoning",
  "branchSuggestion": "alternative reasoning path or null",
  "risk": "pitfall warning or null",
  "synthesis": "synthesis of perspectives or null",
  "focusSuggestion": "what to focus on next or null",
  "correction": "correction to previous reasoning or null",
  "confidence": 0.0-1.0
}
\`\`\`

Keep your response under 500 tokens. Be direct and actionable.`
  }

  /**
   * Get tone directive based on posture energy.
   */
  private getEnergyTone(energy: PostureEnergy): string {
    switch (energy) {
      case 'expansive':
        return 'Your tone is EXPANSIVE — encourage exploration, find opportunities, build on strengths. Be decisive and forward-looking.'
      case 'contractive':
        return 'Your tone is CONTRACTIVE — identify risks, challenge assumptions, find gaps. Be cautious and thorough.'
      case 'unifying':
        return 'Your tone is UNIFYING — synthesize perspectives, find common ground, integrate insights. Be balanced and holistic.'
      case 'neutral':
      default:
        return 'Your tone is NEUTRAL — provide balanced, objective guidance without strong directional bias.'
    }
  }

  /**
   * Format signals for the prompt.
   */
  private formatSignals(signals: Array<{ kind: string; text: string; confidence: number }>): string {
    if (signals.length === 0) return '(none)'
    return signals
      .map((s) => `- [${s.kind}] ${s.text} (${Math.round(s.confidence * 100)}% confidence)`)
      .join('\n')
  }

  /**
   * Parse LLM response into SynapseGuidance.
   * Handles both JSON and legacy text formats.
   */
  private parseGuidance(content: string, sessionId: string, stepNumber: number, targetPosture?: string): SynapseGuidance {
    // Try JSON parsing first
    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0])
        return {
          type: (parsed.type as GuidanceType) || 'observation',
          observation: parsed.observation || parsed.OBSERVATION || 'No observation provided.',
          branchSuggestion: parsed.branchSuggestion || parsed.BRANCH || null,
          risk: parsed.risk || parsed.RISK || null,
          synthesis: parsed.synthesis || parsed.SYNTHESIS || null,
          focusSuggestion: parsed.focusSuggestion || parsed.FOCUS || null,
          correction: parsed.correction || parsed.CORRECTION || null,
          confidence: parsed.confidence ?? 0.5,
          targetPosture,
          sessionId,
          stepNumber,
        }
      }
    } catch {
      // Fall through to text parsing
    }

    // Legacy text format fallback
    const observation = this.extractField(content, 'OBSERVATION')
    const branch = this.extractField(content, 'BRANCH')
    const risk = this.extractField(content, 'RISK')
    const synthesis = this.extractField(content, 'SYNTHESIS')
    const focus = this.extractField(content, 'FOCUS')
    const correction = this.extractField(content, 'CORRECTION')

    return {
      type: this.determineGuidanceType(observation, branch, risk, synthesis, focus, correction),
      observation: observation || 'No observation provided.',
      branchSuggestion: branch && branch.toUpperCase() !== 'NONE' ? branch : null,
      risk: risk && risk.toUpperCase() !== 'NONE' ? risk : null,
      synthesis: synthesis && synthesis.toUpperCase() !== 'NONE' ? synthesis : null,
      focusSuggestion: focus && focus.toUpperCase() !== 'NONE' ? focus : null,
      correction: correction && correction.toUpperCase() !== 'NONE' ? correction : null,
      confidence: 0.5,
      targetPosture,
      sessionId,
      stepNumber,
    }
  }

  /** Determine guidance type based on which fields are populated */
  private determineGuidanceType(
    observation: string | null,
    branch: string | null,
    risk: string | null,
    synthesis: string | null,
    focus: string | null,
    correction: string | null,
  ): GuidanceType {
    if (correction) return 'correction'
    if (synthesis) return 'synthesis'
    if (focus) return 'focus'
    if (branch) return 'branch'
    if (risk) return 'risk'
    return 'observation'
  }

  /**
   * Extract a field value from the LLM response.
   */
  private extractField(content: string, fieldName: string): string | null {
    const regex = new RegExp(`${fieldName}[:\s]+(.+?)(?:\\n|$)`, 'i')
    const match = content.match(regex)
    return match?.[1]?.trim() || null
  }
}


/**
 * Create a Synapse instance with the given dependencies.
 * @dep callers: start (core/daemon.ts), synapse.test.ts (tests/synapse.test.ts), synapse-integration.test.ts (tests/synapse-integration.test.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function createSynapse(deps: SynapseDeps, config?: Partial<SynapseConfig>): Synapse {
  return new Synapse(deps, config)
}
