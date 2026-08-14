/**
 * Collect Thoughts Tool — the primary thinking tool for all agents.
 *
 * Each tool call is a bidirectional intelligence exchange:
 *   1. Agent externalizes a thought step
 *   2. CassiCore processes through ThoughtObserver, CognitiveBridge, memory
 *   3. CassiCore responds with enriched context
 *   4. Agent incorporates enrichment into its next step
 *
 * Enrichment pipeline (Stages 1-4, fast path):
 *   Stage 1: STORE   — BranchingConversation.addTurn(); revision/branch routing
 *   Stage 2: EXTRACT — ThoughtObserver.extractSignalsFromText()
 *   Stage 3: PEER    — CognitiveBridge.getFusedSignals() + getResonancePatterns()
 *   Stage 4: ROUTE   — Route signals to peers; emit axon:step event
 *
 * Context-dependent enrichment (replaces stages 5-6):
 *   Constellation context → Memory search + Synapse LLM + Corpus guidance
 *   Main agent context    → Parallel Thinker session (async LLM partner)
 *
 * Neural metaphor:
 *   Axon    — the structured thought chain (sessions/trees managed here)
 *   Synapse — fires guidance at junctions between thoughts
 *   Dendrites — memory, signals, peers feeding into each step
 *   Thinker — parallel reasoning partner for the main agent
 */

import type { ToolDefinition, ToolHandler } from '../types.js'
import type { BranchingConversationManager } from '../../vendor/core/intelligence/branching-conversation/manager.js'
import type { ThoughtObserver, CognitiveSignal } from '../../vendor/core/intelligence/thought-observer.js'
import type { CognitiveBridge, ResonancePattern } from '../../vendor/core/intelligence/cognitive-bridge.js'
import type { IMemory } from "@cassicore/foundation"
import type { IEventBus, ILogger } from "@cassicore/foundation"
import type {
  CollectThoughtsResult,
  CollectThoughtsConfig,
  CollectThoughtsInput,
  AxonSessionState,
  SynapseGuidance,
} from "@cassicore/foundation"
import { DEFAULT_COLLECT_THOUGHTS_CONFIG } from "@cassicore/foundation"
import { generateShortId } from '../../vendor/core/utils/ids.js'
import type { Synapse } from '../../vendor/core/intelligence/synapse/index.js'
import type { ThinkerSession } from '../../vendor/core/intelligence/thinker/thinker-session.js'


/** Constellation-level guidance provider for thought enrichment.
 *  Returns strategic context from the Corpus based on the current thought. */
export interface ConstellationGuidanceProvider {
  /** Get guidance for a specific thought step.
   *  @param thought The current thought text
   *  @param step The step number
   *  @param sessionId The Helix session ID
   *  @returns Strategic guidance text, or null if no relevant guidance exists */
  getGuidanceForThought(thought: string, step: number, sessionId: string): string | null
}


export interface CollectThoughtsDeps {
  branchingManager: BranchingConversationManager
  thoughtObserver?: ThoughtObserver
  cognitiveBridge?: CognitiveBridge
  memory?: IMemory
  /** Modern long-term retrieval — preferred over deprecated memory search. */
  mnemicField?: {
    retrieve(query: string, options?: { limit?: number }): Promise<Array<{ content: string; score?: number }>> | Array<{ content: string; score?: number }>
  }
  bus?: IEventBus
  logger: ILogger
  config?: Partial<CollectThoughtsConfig>
  synapse?: Synapse
  /** Reasoning Bank for injecting past successful reasoning traces */
  reasoningBank?: import('../../intelligence/reasoning-bank/index.js').ReasoningBank
  /** Constellation guidance provider — returns strategic context from the Corpus
   *  for the current thought step. Set by the Constellation pipeline when running
   *  inside a Helix branch. Returns null if no relevant guidance exists. */
  constellationProvider?: ConstellationGuidanceProvider
  /** Session-scoped registry of guidance providers. The Constellation pipeline
   *  registers per-branch providers here; collect_thoughts looks up by sessionId. */
  constellationGuidanceRegistry?: import('../../intelligence/constellation/guidance-provider.js').ConstellationGuidanceRegistry
  /** Resolve the parallel Thinker session for the current host session. */
  getThinkerSession?: (sessionId: string) => ThinkerSession | undefined
}


export const collectThoughtsDefinition: ToolDefinition = {
  name: 'collect_thoughts',
  readOnly: true,
  description:
    'Organize multi-step reasoning with intelligence enrichment. Steps are enriched with ' +
    'signal extraction, memory recall, and peer activity. Supports branching (explore ' +
    'alternatives) and revision (reconsider earlier steps). Use sparingly — prefer direct ' +
    'action with tools over extended deliberation.',
  parameters: {
    type: 'object',
    properties: {
      thought: {
        type: 'string',
        description: 'Your current thought — what you are considering, your hypothesis, analysis, or conclusion.',
      },
      step: {
        type: 'number',
        description: 'Step number in the thought chain (1-indexed).',
      },
      estimated_steps: {
        type: 'number',
        description: 'Estimated total steps. Can be adjusted upward with needs_more_steps.',
      },
      continue_thinking: {
        type: 'boolean',
        description: 'Whether more thinking steps are needed after this one.',
      },
      is_revision: {
        type: 'boolean',
        description: 'Set to true if this step reconsiders a previous step.',
      },
      revises_step: {
        type: 'number',
        description: 'Which step number is being reconsidered (requires is_revision: true).',
      },
      branch_from_step: {
        type: 'number',
        description: 'Create a new thinking branch starting from this step number.',
      },
      branch_id: {
        type: 'string',
        description: 'Identifier for the new branch (e.g., "alternative-approach", "risk-assessment").',
      },
      needs_more_steps: {
        type: 'boolean',
        description: 'Set to true to extend the total beyond original estimate.',
      },
      session_id: {
        type: 'string',
        description: 'Resume a previous axon session by its ID.',
      },
      posture_energy: {
        type: 'string',
        enum: ['expansive', 'contractive', 'unifying', 'neutral'],
        description: 'Posture energy for Synapse guidance adaptation. In Helix context: unity=unifying, yang=expansive, yin=contractive.',
      },
      related_context_mode: {
        type: 'string',
        enum: ['none', 'safe-mnemic', 'mnemic', 'memory'],
        description: 'Control related context retrieval. Default is mnemic (preferred). safe-mnemic filters chat-style leakage, memory is deprecated unrestricted search, none disables retrieval.',
      },
    },
    required: ['thought', 'step', 'estimated_steps', 'continue_thinking'],
  },
  timeoutMs: 60_000,
  category: 'cognitive',
  requiredPermission: 'read-only',
}


/** In-memory axon session state, keyed by axon session ID */
const sessionStates = new Map<string, AxonSessionState>()


const RESULT_HARD_CAP = 2_000


/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts), synapse-integration.test.ts (tests/synapse-integration.test.ts), collect-thoughts.test.ts (tests/collect-thoughts.test.ts)
 * @dep calls: computeNextSynapseEligible, resolveAxonSession, switchBranch, forkBranch, getRemainingBudget [+13]
 * @dep module: Implementations
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function makeCollectThoughtsHandler(deps: CollectThoughtsDeps): ToolHandler {
  const log = deps.logger.child?.('collect-thoughts') ?? deps.logger
  const cfg: CollectThoughtsConfig = {
    ...DEFAULT_COLLECT_THOUGHTS_CONFIG,
    ...deps.config,
  }

  return async (rawInput, context) => {
    const input = rawInput as unknown as CollectThoughtsInput

    // Validate required fields
    if (!input.thought || typeof input.thought !== 'string') {
      return JSON.stringify({ error: 'thought is required and must be a string' })
    }
    if (typeof input.step !== 'number' || input.step < 1) {
      return JSON.stringify({ error: 'step is required and must be >= 1' })
    }
    if (typeof input.estimated_steps !== 'number' || input.estimated_steps < 1) {
      return JSON.stringify({ error: 'estimated_steps is required and must be >= 1' })
    }

    const { state, isNew } = resolveAxonSession(
      input,
      context.sessionId,
      cfg,
      deps.branchingManager,
      log,
    )

    if (input.needs_more_steps) {
      // Agent is signaling it needs more steps than originally estimated
      // estimated_steps should already be the new (higher) value
    }

    let activeBranchId = 'main'
    if (input.branch_from_step && input.branch_id) {
      const branchId = input.branch_id
      const session = deps.branchingManager.getSession(state.axonSessionId)
      if (session && !session.branches.has(branchId)) {
        // Find the turn ID for the branch point
        const branchPointTurnId = state.stepToTurnId.get(input.branch_from_step)
        if (branchPointTurnId) {
          // Switch to the branch point first, then fork
          deps.branchingManager.switchBranch(state.axonSessionId, 'main')
          deps.branchingManager.forkBranch(state.axonSessionId, branchId, {
            name: branchId,
            description: `Branch from step ${input.branch_from_step}`,
          })
          deps.branchingManager.switchBranch(state.axonSessionId, branchId)
        }
      } else if (session?.branches.has(branchId)) {
        // Branch already exists, just switch to it
        deps.branchingManager.switchBranch(state.axonSessionId, branchId)
      }
      activeBranchId = branchId
    }

    // Record the thought as a turn in the BranchingConversation
    const parentTurnId = input.is_revision && input.revises_step
      ? state.stepToTurnId.get(input.revises_step)
      : undefined

    const turnId = deps.branchingManager.addTurn(
      state.axonSessionId,
      {
        role: 'assistant',
        content: `[Step ${input.step}/${input.estimated_steps}] ${input.thought}`,
      },
      parentTurnId,
    )
    state.stepToTurnId.set(input.step, turnId)

    if (input.is_revision) {
      state.revisionsCount++
    }

    // Map posture_energy to contributor role name
    const contributorRole = input.posture_energy ?? 'neutral'
    const currentCount = state.contributors.get(contributorRole) ?? 0
    state.contributors.set(contributorRole, currentCount + 1)

    // Extract cognitive signals from the thought text
    let signals: CognitiveSignal[] = []
    if (deps.thoughtObserver) {
      signals = deps.thoughtObserver.extractSignalsFromText(input.thought)

      // Revision delta extraction — when revising, also extract signals from
      // the gap between original and revised thinking
      if (input.is_revision && input.revises_step) {
        const originalSignals = state.signalsByStep.get(input.revises_step) ?? []
        const originalKinds = new Set(originalSignals.map(s => s.kind))
        const newKinds = signals.filter(s => !originalKinds.has(s.kind))
        if (newKinds.length > 0) {
          // The delta signals are the ones in the revision that weren't in the original
          signals = [...signals, ...newKinds.map(s => ({
            ...s,
            text: `[revision delta] ${s.text}`,
            confidence: Math.min(s.confidence + 0.1, 1.0), // slight boost for revision insights
          }))]
        }
      }
    }
    state.signalsByStep.set(input.step, signals)

    // Gather fused signals and resonance patterns from peer sessions
    let peerSignals: CognitiveSignal[] = []
    let resonancePatterns: ResonancePattern[] = []
    if (deps.cognitiveBridge) {
      const allFused = deps.cognitiveBridge.getFusedSignals(context.sessionId)
      // Filter to recent high-confidence, cap at maxPeerSignals
      peerSignals = allFused
        .filter(s => s.confidence >= 0.5)
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, cfg.maxPeerSignals)

      resonancePatterns = deps.cognitiveBridge.getResonancePatterns(context.sessionId)
    }

    // Route signals to peers and emit axon:step event
    if (deps.thoughtObserver && signals.length > 0) {
      deps.thoughtObserver.storeSignals(context.sessionId, signals)
    }
    if (deps.cognitiveBridge && signals.length > 0) {
      deps.cognitiveBridge.routeSignals(context.sessionId, signals)
    }

    // Emit axon:step event
    if (deps.bus) {
      deps.bus.emit({
        type: 'axon:step',
        sessionId: context.sessionId,
        axonSessionId: state.axonSessionId,
        step: input.step,
        totalSteps: input.estimated_steps,
        thought: input.thought.slice(0, 500), // truncate for event payload
        signals,
        branchId: activeBranchId,
        isRevision: input.is_revision ?? false,
        timestamp: new Date(),
      })

      // Emit branch event if we just created a branch
      if (input.branch_from_step && input.branch_id) {
        deps.bus.emit({
          type: 'axon:branch',
          sessionId: context.sessionId,
          axonSessionId: state.axonSessionId,
          fromStep: input.branch_from_step,
          branchId: input.branch_id,
          timestamp: new Date(),
        })
      }
    }

    const relatedContextMode = input.related_context_mode ?? 'mnemic'

    // Related-context retrieval is explicit now. Helix/Constellation should use
    // 'none' or 'safe-memory' to avoid leaking main-session chat fragments into
    // autonomous branches. Unrestricted 'memory' is still available for callers
    // that genuinely want raw memory retrieval.
    let relatedContext: string[] = []
    if (deps.mnemicField && (relatedContextMode === 'mnemic' || relatedContextMode === 'safe-mnemic')) {
      try {
        const results = await Promise.resolve(deps.mnemicField.retrieve(input.thought, {
          limit: cfg.maxMemoryResults + cfg.maxArchiveResults,
        }))
        relatedContext = results
          .filter(r => (r.score ?? 1) >= 0.3)
          .slice(0, cfg.maxMemoryResults + cfg.maxArchiveResults)
          .map(r => (r.content ?? '').slice(0, 200))
          .filter(t => t.length > 0)

        if (relatedContextMode === 'safe-mnemic') {
          relatedContext = relatedContext.filter(t => {
            const lower = t.toLowerCase()
            if (lower.includes('user:') || lower.includes('assistant:')) return false
            if (lower.includes('system:')) return false
            return true
          })
        }
      } catch (err) {
        log.warn('Mnemic Field retrieval failed in thinking step', { error: String(err) })
      }
    } else if (deps.memory && relatedContextMode === 'memory') {
      try {
        const results = await deps.memory.search(input.thought, {
          limit: cfg.maxMemoryResults + cfg.maxArchiveResults,
        })
        relatedContext = results
          .filter(r => r.score >= 0.3)
          .slice(0, cfg.maxMemoryResults + cfg.maxArchiveResults)
          .map(r => {
            const text = r.entry?.content ?? ''
            return text.slice(0, 200)
          })
          .filter(t => t.length > 0)

      } catch (err) {
        log.warn('Deprecated memory search failed in thinking step', { error: String(err) })
      }
    }

    // Stage 5b: REASONING BANK — Search past successful reasoning traces
    // HOW: Only search on step 1 (initial context) and every 3 steps (to avoid
    // bloating every tool result). Cap at 2 traces, 300 chars each.
    let reasoningBankContext: string[] = []
    if (deps.reasoningBank && (input.step === 1 || input.step % 3 === 0)) {
      try {
        const rbResults = deps.reasoningBank.search({
          query: input.thought,
          minQuality: 0.7,
          successOnly: true,
          limit: 2,
        })
        reasoningBankContext = rbResults.map(r =>
          `[Past approach] ${r.trace.approach.slice(0, 100)}: ${r.trace.content.slice(0, 200)}`
        )
      } catch (err) {
        log.warn('Reasoning bank search failed in thinking step', { error: String(err) })
      }
    }

    // Conditional LLM call that provides meta-cognitive guidance.
    // Fires only when gating conditions pass (budget, signal confidence, etc.)
    let synapseGuidance: SynapseGuidance | null = null
    let synapseFired = false
    let synapseLatencyMs = 0
    if (deps.synapse) {
      const gating = deps.synapse.shouldFire(
        input.step,
        state.axonSessionId,
        signals,
        input.is_revision ?? false,
        input.branch_from_step,
      )
      if (gating.shouldFire) {
        synapseFired = true
        const synapseStart = Date.now()
        log.info('Synapse firing', {
          step: input.step,
          reason: gating.reason,
          remaining: deps.synapse.getRemainingBudget(state.axonSessionId),
        })
        try {
          // Build compressed tree summary for the Synapse context
          const session = deps.branchingManager.getSession(state.axonSessionId)
          const treeSummary = session
            ? `${session.branches.size} branches, ${state.stepToTurnId.size} steps, ${state.revisionsCount} revisions`
            : `${state.stepToTurnId.size} steps`

          synapseGuidance = await deps.synapse.generateGuidance(
            {
              tree: treeSummary,
              currentStep: { number: input.step, content: input.thought },
              signals,
              relatedMemory: relatedContext,
              peerSignals,
              resonance: resonancePatterns,
              energy: input.posture_energy,
              isRevision: input.is_revision,
              revisesStep: input.revises_step,
            },
            state.axonSessionId,
          )
          if (synapseGuidance) {
            state.synapseBudget = deps.synapse.getRemainingBudget(state.axonSessionId)
          }
          synapseLatencyMs = Date.now() - synapseStart
          log.info('Synapse completed', {
            step: input.step,
            latencyMs: synapseLatencyMs,
            hasGuidance: !!synapseGuidance,
            remaining: deps.synapse.getRemainingBudget(state.axonSessionId),
          })
          // Emit synapse:fired event for observability
          if (deps.bus) {
            deps.bus.emit({
              type: 'synapse:fired',
              sessionId: context.sessionId,
              axonSessionId: state.axonSessionId,
              step: input.step,
              reason: gating.reason,
              latencyMs: synapseLatencyMs,
              hasGuidance: !!synapseGuidance,
              remaining: deps.synapse.getRemainingBudget(state.axonSessionId),
              energy: input.posture_energy,
              timestamp: new Date(),
            })
          }
        } catch (err) {
          synapseLatencyMs = Date.now() - synapseStart
          log.warn('Synapse guidance failed', { error: String(err), step: input.step, latencyMs: synapseLatencyMs })
        }
      } else {
        log.debug('Synapse gating: skip', { step: input.step, reason: gating.reason })
      }
    }

    // Stage 6b: CONSTELLATION GUIDANCE — Pull strategic guidance from the Corpus.
    // HOW: The provider is resolved in priority order:
    //   1. Direct provider on deps (backward compat / tests)
    //   2. Registry lookup by session ID (production path — Constellation pipeline
    //      registers a per-branch provider keyed by the Helix session ID)
    let constellationGuidance: string | null = null
    const guidanceProvider = deps.constellationProvider
      ?? deps.constellationGuidanceRegistry?.get(context.sessionId)
    if (guidanceProvider) {
      try {
        constellationGuidance = guidanceProvider.getGuidanceForThought(
          input.thought,
          input.step,
          context.sessionId,
        )
        if (constellationGuidance) {
          log.info('Constellation guidance injected', {
            step: input.step,
            guidanceLength: constellationGuidance.length,
          })
        }
      } catch (err) {
        log.warn('Constellation guidance failed', { error: String(err) })
      }
    }

    // Stage 7: THINKER — Parallel reasoning partner for main-agent context.
    // When a ThinkerSession is present and we're NOT inside a Constellation branch,
    // enqueue the current thought for async processing and collect any buffered
    // output from previous steps. On step 1, sync-wait for the initial response
    // to seed the first turn with Thinker context.
    let thinkerGuidance: string | null = null
    const isConstellationContext = !!(deps.constellationProvider
      || deps.constellationGuidanceRegistry?.get(context.sessionId))
    const thinkerSession = deps.getThinkerSession?.(context.sessionId)
    if (thinkerSession && !isConstellationContext) {
      try {
        thinkerSession.enqueueThought(input.thought, {
          step: input.step,
          estimatedSteps: input.estimated_steps,
          isRevision: input.is_revision ?? false,
          branchId: activeBranchId,
        })

        if (input.step === 1) {
          const hasResponse = await thinkerSession.waitForResponse(5000)
          if (hasResponse) {
            const buffered = thinkerSession.drainBuffer()
            if (buffered.length > 0) {
              thinkerGuidance = buffered[buffered.length - 1].content
              log.info('Thinker initial guidance received', {
                step: input.step,
                guidanceLength: thinkerGuidance!.length,
              })
            }
          }
        } else {
          const buffered = thinkerSession.drainBuffer()
          if (buffered.length > 0) {
            thinkerGuidance = buffered[buffered.length - 1].content
            log.info('Thinker buffered guidance collected', {
              step: input.step,
              bufferedCount: buffered.length,
              guidanceLength: thinkerGuidance!.length,
            })
          }
        }
      } catch (err) {
        log.warn('Thinker guidance failed', { error: String(err), step: input.step })
      }
    }

    if (!input.continue_thinking && deps.bus) {
      deps.bus.emit({
        type: 'axon:complete',
        sessionId: context.sessionId,
        axonSessionId: state.axonSessionId,
        totalSteps: input.step,
        summary: `Thinking complete: ${input.step} steps, ${state.revisionsCount} revisions`,
        timestamp: new Date(),
      })
    }

    const session = deps.branchingManager.getSession(state.axonSessionId)
    const branches = session ? Array.from(session.branches.keys()) : [activeBranchId]

    const nextSynapseStep = computeNextSynapseEligible(
      input.step,
      cfg.synapseInterval,
      state.synapseBudget,
    )

    const contributorsRecord: Record<string, number> = {}
    for (const [role, count] of state.contributors) {
      contributorsRecord[role] = count
    }

    const result: CollectThoughtsResult = {
      step: {
        number: input.step,
        of: input.estimated_steps,
        recorded: true,
        isRevision: input.is_revision ?? false,
        branchId: activeBranchId,
      },
      signals: signals.slice(0, 10), // Cap signals in result
      relatedContext,
      reasoningBankContext,
      peerSignals,
      resonance: resonancePatterns.map(r => ({
        kind: r.kind,
        summary: r.kind === 'resonance'
          ? `Convergence: "${r.signalA.signal.text.slice(0, 100)}"`
          : `Tension: "${r.signalA.signal.text.slice(0, 60)}" vs "${r.signalB.signal.text.slice(0, 60)}"`,
        confidence: r.amplifiedConfidence,
      })),
      synapse: synapseGuidance,
      constellationGuidance,
      thinkerGuidance,
      tree: {
        totalSteps: state.stepToTurnId.size,
        activeBranch: activeBranchId,
        branches,
        revisionsCount: state.revisionsCount,
      },
      contributors: contributorsRecord,
      meta: {
        synapseCallsRemaining: state.synapseBudget,
        nextSynapseEligible: nextSynapseStep,
        synapseFired,
        synapseLatencyMs,
      },
    }

    // Stringify and enforce hard cap
    let jsonResult = JSON.stringify(result)
    if (jsonResult.length > RESULT_HARD_CAP) {
      // Trim relatedContext and peerSignals first, then signals
      const trimmed = { ...result }
      trimmed.relatedContext = trimmed.relatedContext.slice(0, 2)
      trimmed.reasoningBankContext = trimmed.reasoningBankContext.slice(0, 1)
      trimmed.peerSignals = trimmed.peerSignals.slice(0, 2)
      trimmed.signals = trimmed.signals.slice(0, 5)
      trimmed.resonance = trimmed.resonance.slice(0, 2)
      jsonResult = JSON.stringify(trimmed)
      if (jsonResult.length > RESULT_HARD_CAP) {
        jsonResult = jsonResult.slice(0, RESULT_HARD_CAP)
      }
    }

    log.info(`[step ${input.step}/${input.estimated_steps}]`, {
      sessionId: context.sessionId.slice(-8),
      axonSession: state.axonSessionId.slice(-8),
      signals: signals.length,
      peers: peerSignals.length,
      memory: relatedContext.length,
      reasoningBank: reasoningBankContext.length,
      branch: activeBranchId,
      revision: input.is_revision ?? false,
      contributors: contributorsRecord,
      hasThinkerGuidance: !!thinkerGuidance,
    })

    return jsonResult
  }
}


/**
 * Resolve or create the axon session state for this tool call.
 */
function resolveAxonSession(
  input: CollectThoughtsInput,
  ownerSessionId: string,
  cfg: CollectThoughtsConfig,
  branchingManager: BranchingConversationManager,
  log: ILogger,
): { state: AxonSessionState; isNew: boolean } {
  // Resume existing session
  if (input.session_id) {
    const existing = sessionStates.get(input.session_id)
    if (existing) {
      return { state: existing, isNew: false }
    }
    log.warn('Requested axon session not found, creating new', {
      requestedId: input.session_id,
    })
  }

  // Check if we already have a session for this owner + step 1
  // (handles the common case of a single thought chain per session)
  if (input.step === 1) {
    // Always create a new session for step 1
    const axonSessionId = `axon-${generateShortId(8)}`

    branchingManager.createSession(
      axonSessionId,
      ownerSessionId,
      'collect-thoughts',
      { model: 'n/a', thinking: 'none' },
    )

    const state: AxonSessionState = {
      axonSessionId,
      ownerSessionId,
      stepToTurnId: new Map(),
      revisionsCount: 0,
      synapseBudget: cfg.maxSynapseCalls,
      signalsByStep: new Map(),
      createdAt: Date.now(),
      contributors: new Map(),
    }
    sessionStates.set(axonSessionId, state)

    log.info('Created axon session', {
      axonSessionId: axonSessionId.slice(-8),
      ownerSession: ownerSessionId.slice(-8),
    })
    return { state, isNew: true }
  }

  // For steps > 1 without an explicit session_id,
  // find the most recent session for this owner
  for (const [, s] of sessionStates) {
    if (s.ownerSessionId === ownerSessionId) {
      return { state: s, isNew: false }
    }
  }

  // Fallback: create a new session mid-chain (shouldn't happen normally)
  log.warn('No existing axon session found for mid-chain step, creating new', {
    stepNumber: input.step,
    ownerSession: ownerSessionId,
  })
  const axonSessionId = `axon-${generateShortId(8)}`
  branchingManager.createSession(
    axonSessionId,
    ownerSessionId,
    'collect-thoughts',
    { model: 'n/a', thinking: 'none' },
  )
  const state: AxonSessionState = {
    axonSessionId,
    ownerSessionId,
    stepToTurnId: new Map(),
    revisionsCount: 0,
    synapseBudget: cfg.maxSynapseCalls,
    signalsByStep: new Map(),
    createdAt: Date.now(),
    contributors: new Map(),
  }
  sessionStates.set(axonSessionId, state)
  return { state, isNew: true }
}

/**
 * Compute when the next Synapse call is eligible.
 */
function computeNextSynapseEligible(
  currentStep: number,
  interval: number,
  budgetRemaining: number,
): string {
  if (budgetRemaining <= 0) return 'budget exhausted'
  const nextPeriodicStep = Math.ceil(currentStep / interval) * interval + interval
  return `step ${nextPeriodicStep} or next revision/branch`
}

/**
 * Clean up old axon sessions to prevent memory leaks.
 * Called periodically or when sessions complete.
 */
export function cleanupAxonSessions(maxAgeMs: number = 30 * 60 * 1_000): number {
  const now = Date.now()
  let cleaned = 0
  for (const [id, state] of sessionStates) {
    if (now - state.createdAt > maxAgeMs) {
      sessionStates.delete(id)
      cleaned++
    }
  }
  return cleaned
}

/** Exposed for testing */
export function getAxonSessionState(axonSessionId: string): AxonSessionState | undefined {
  return sessionStates.get(axonSessionId)
}

/** Exposed for testing */
/**
 * @dep callers: synapse-integration.test.ts (tests/synapse-integration.test.ts), collect-thoughts.test.ts (tests/collect-thoughts.test.ts)
 * @dep calls: clear
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function clearAllSessionStates(): void {
  sessionStates.clear()
}
