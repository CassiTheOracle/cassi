import { MODEL_DEFAULTS, getModelSpec } from '@cassicore/foundation'
import { writeThoughtRequestLog, writeThoughtResultLog } from '@cassicore/events'

import { createAIEngineer } from "./ai-engineer/index.js"
import { createAIScientist } from "./ai-scientist/index.js"
import { IntelligenceRegistry } from "./base/registry.js"
import { createCognitiveBridge, type CognitiveBridge } from "./cognitive-bridge.js"
import { createConsequenceEstimator, type ConsequenceEstimator } from "./consequence-estimator/index.js"
import { createContextManager } from "./context-manager.js"
import { createContinuity } from "./continuity/index.js"
import { createDialecticSystem } from "@cassicore/cortex-pineal-dialectic"
import { createDmn, type Dmn } from "./dmn/index.js"
// REMOVED: createMemory — MemoryModule deleted. MemoryShim provides IMemory compat.
import { createMemoryShim } from './memory-shim.js'
import type { MemoryShim } from './memory-shim.js'
// REMOVED: createOptimizer — OptimizerModule deleted (all actions were no-op or destructive).
import { createPermissionOracle, type PermissionOracle } from "./permission-oracle/index.js"
import { createErrorLearner } from "./error-learner/index.js"
import { createReflex } from "./reflex/index.js"
import { createRuleEnforcer } from "./rule-enforcer/index.js"
import { createSelfHealingAgent, type SelfHealerConfig } from "./self-healer/index.js"
import { createSmartRulesModule } from "./smart-rules/index.js"
import { createSubconscious } from "@cassicore/dreamer-reverie-subconscious"
// REMOVED: TriadTeamOrchestrator and FluxTeamOrchestrator are deprecated.
// All orchestration now uses Helix and Constellation.
import { createThoughtObserver, type ThoughtObserver } from "./thought-observer.js"
import { createThinker } from "./thinker/index.js"
import { createTrustLedger, type TrustLedger } from "@cassicore/training-trust-ledger"
import { createHelix, type HelixOrchestrator } from "@cassicore/helix"
import { createConstellationOrchestrator, type ConstellationOrchestrator } from "@cassicore/constellation"
import { ConstellationRegistry } from "@cassicore/constellation"
import { ConstellationGuidanceRegistry } from "@cassicore/constellation"
import { createImprovementOrchestrator, type ImprovementOrchestrator } from "./improvement/index.js"
import { createDreamer } from "@cassicore/dreamer-reverie-subconscious"
import { createMeditationController } from "@cassicore/constellation"
import type { MeditationController } from "@cassicore/constellation"
import createHeartModule from "./heart/index.js"
import { GlobalWorkspace } from "./workspace/index.js"
import type { GlobalWorkspace as GlobalWorkspaceType } from "./workspace/index.js"
import { LocusBridge } from "./locus-bridge/index.js"
import type { LocusBridge as LocusBridgeType } from "./locus-bridge/index.js"
import { CorticalField } from '@cassicore/cortex-pineal-dialectic'
import type { CorticalField as CorticalFieldType } from '@cassicore/cortex-pineal-dialectic'
import { LaminaField, ClaudeMemoryImporter } from '@cassicore/lamina-locus-bridge'
import type { LaminaField as LaminaFieldType } from '@cassicore/lamina-locus-bridge'
import { ReverieModule } from '@cassicore/dreamer-reverie-subconscious'
import { ContextRepo } from './context-repo/index.js'
import { MnemicWritebackTarget } from './context-repo/mnemic-writeback-target.js'
import { AuditStore } from '../runtime/audit/index.js'
import type { AuditStore as AuditStoreType } from '../runtime/audit/index.js'
import { homedir } from 'node:os'
import path from 'node:path'
import { TrainingWarehouse } from '@cassicore/training-trust-ledger'
import { ReasoningBank } from './reasoning-bank/index.js'
import type { TaggerLLM } from '@cassicore/training-trust-ledger'

// REMOVED: IMemory import — MemoryModule deleted. MemoryShim implements the interface.
import type { ILogger, IntelligenceModule, IConfig, ThinkerDeferredWiring, IEventBus } from "@cassicore/foundation"

// REMOVED: Triad Team and Flux Team orchestrators are deleted.
// All orchestration now uses Helix (single-session) and Constellation (multi-Helix).

type PrioritizedModule = { name: string; priority: number }
type ThinkerWithDeferredWiring = ReturnType<typeof createThinker> & { __awaitingWiring?: ThinkerDeferredWiring }


export interface IntelligenceLayer {
  /** REMOVED: MemoryModule deleted. MemoryShim provides backward-compatible IMemory. */
  memory: MemoryShim
  continuity: ReturnType<typeof createContinuity>
  recover: ReturnType<typeof createErrorLearner>
  reflect: ReturnType<typeof createErrorLearner>
  thinker: ReturnType<typeof createThinker>
  // REMOVED: optimizer — OptimizerModule deleted
  dialectic: ReturnType<typeof createDialecticSystem>
  aiScientist: ReturnType<typeof createAIScientist>
  ruleEnforcer: ReturnType<typeof createRuleEnforcer>
  subconscious: ReturnType<typeof createSubconscious>
  contextManager: ReturnType<typeof createContextManager>
  /** Three-posture collaborative pattern — Unity, Yang, Yin as equally capable agents */
  helix: HelixOrchestrator
  /** Constellation — multi-Helix orchestration with Corpus tree reasoning */
  constellation: ConstellationOrchestrator
  /** Proactive context enrichment — observes thinking stream, gathers context via persistent Helix co-pilot */
  /** Autonomous code repair — detects TypeError/interface mismatches and patches them */
  selfHealer: ReturnType<typeof createSelfHealingAgent>
  /** Proactive cognitive program upgrader — evolves prompts and configs of all modules */
  aiEngineer: ReturnType<typeof createAIEngineer>
  /** Risk assessment for tool calls — heuristic + LLM consequence prediction */
  consequenceEstimator: ConsequenceEstimator
  /** Per-domain Bayesian trust scoring — aggregates evidence from across the system */
  trustLedger: TrustLedger
  /** Trust-adjusted risk gating — allow/deny/escalate decisions for every gated action */
  permissionOracle: PermissionOracle
  /** REMOVED: injectionAggregator — deprecated. Now uses Thalamus/GlobalWorkspace. */
  /** Extracts cognitive signals from the LLM's thinking stream — zero extra requests */
  thoughtObserver: ThoughtObserver
  /** Links sessions into a shared cognitive space for cross-session signal routing */
  cognitiveBridge: CognitiveBridge
  /** Self-improvement loop — verification-gated adaptation orchestrator */
  improvementOrchestrator: ImprovementOrchestrator
  /** Dead-end detection and recovery — detects empty responses, deflections, tool loops */
  smartRules: ReturnType<typeof createSmartRulesModule>
  /** Fast-path routing for deterministic/recurring patterns — bypasses LLM for common operations */
  reflex: ReturnType<typeof createReflex>
  /** Idle-time memory synthesis — forms novel cross-session insights, curates the memory garden */
  dreamer: ReturnType<typeof createDreamer>
  /** Idle-time constellation exploration — solitary Helixes explore with no objective */
  meditation?: MeditationController
  /** Periodic autonomous agent heartbeats — reads HEARTBEAT.md, routes actionable results to channels */
  heart: ReturnType<typeof createHeartModule>
  /** Cortical field — self-organizing working memory with activation dynamics */
  cortex?: CorticalFieldType
  /** Lamina — labeled, CAS-edited, tool-writable memory blocks */
  lamina?: LaminaFieldType
  /** Run/Step audit store — provenance for all memory writes */
  audit?: AuditStoreType
  /** Reverie — ambient in-flight memory curator */
  reverie?: ReverieModule
  /** Context Repository — git-backed projection of memory */
  contextRepo?: ContextRepo
  /** Pineal — stable identity module with facet-based self-model */
  pineal?: import('@cassicore/cortex-pineal-dialectic').PinealModule
  /** Aurora — cognitive state loop over the Claustrum (unified model + memory graph) */
  aurora?: import('@cassicore/aurora').Aurora
  /** Default Mode Network — activity-gated dialectic observer for user-facing main sessions */
  dmn?: Dmn
  /** Dynamic module registry — auto-discovers BaseCognitiveModule subclasses */
  registry: IntelligenceRegistry
  /** Training data warehouse — separate DB for granular search, LLM tagging, JSONL export */
  training?: TrainingWarehouse
  /** Reasoning Bank — cached high-quality reasoning traces from Helix sessions. Used by
   *  Constellation pipeline (ingestion/retrieval), collect_thoughts (retrieval), and Dreamer (synthesis). */
  reasoningBank?: ReasoningBank
  /** LLM adapter for training warehouse tagging — wired by daemon after providers are available */
  tagger?: TaggerLLM
  /** Session-scoped registry of per-branch guidance providers. Shared between the
   *  Constellation pipeline (registers providers) and collect_thoughts (looks up by sessionId). */
  constellationGuidanceRegistry?: ConstellationGuidanceRegistry
  /** Wire the CorpusLLM (Brainstem + Corpus) to a ModelHandle. Called by daemon after providers are available. */
  setCorpusLLMProvider?: (handle: import('@cassicore/model-pool').ModelHandle, model?: string) => void
  /** Wire the BrainstemLLM to a separate ModelHandle. Falls back to CorpusLLM when not wired. */
  setBrainstemLLMProvider?: (handle: import('@cassicore/model-pool').ModelHandle, model?: string) => void
  /** Global Workspace — GWT-based attention and broadcasting across all cognitive modules */
  globalWorkspace?: GlobalWorkspaceType
  /** LocusBridge — persistent attentional context assembly for session-level GWT */
  locusBridge?: LocusBridgeType
  /** Wire the model pool into the meditation controller for evaluation mini-helix */
  setMeditationHandleFactory?: (factory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<any>) => void
  all: PrioritizedModule[] // sorted by priority desc
}

/**
 * @dep callers: bootIntelligencePre (core/daemon/boot-intelligence-pre.ts), start (core/daemon.ts)
 * @dep calls: createConsequenceEstimator, createDialecticSystem, createAIEngineer, createAIScientist, createConstellationOrchestrator [+40]
 * @dep flows: BootIntelligencePre → CreateDialecticSystem (2/3), BootIntelligencePre → GetModelSpec (2/3), BootIntelligencePre → CreateErrorLearner (2/3) [+1]
 * @dep module: Intelligence
 * @dep risk: MEDIUM | 2 callers, 4 flows, 1 module
 */

export function createIntelligence(logger: ILogger, config?: IConfig, eventBus?: IEventBus): IntelligenceLayer {
  // REMOVED: createMemory() — MemoryModule deleted.
  // MemoryShim provides backward-compatible IMemory interface.
  // MnemicField is created separately by the daemon.
  const memory = createMemoryShim(logger.child('memory-shim'))
  // REMOVED: Continuity adapter — MemoryModule deleted. Stubs for backward compat.
  const continuity = {
    saveTurn: memory.saveTurn.bind(memory),
    getRecent: memory.getRecentTurns.bind(memory),
    searchHistory: memory.searchTurnHistory.bind(memory),
    prune: memory.pruneConversations.bind(memory),
  } as unknown as ReturnType<typeof createContinuity>
  const errorLearner = createErrorLearner(logger.child("error-learner"))
  // WHY: recover and reflect are named aliases for errorLearner — the unified module
  // implements both IRecover and IReflect interfaces. Consumers access whichever
  // semantic name fits their use case (e.g., optimizer uses reflect, daemon uses recover).
  const recover = errorLearner
  const reflect = errorLearner

  let thinkerConfig: { enabled?: boolean; ponderInterval?: number; thinkInterval?: number } | undefined
  try {
    thinkerConfig = config?.get?.('intelligence.thinker')
  } catch {
    thinkerConfig = undefined
  }
  const thinker = createThinker(logger.child("thinker"), thinkerConfig, memory)

  // REMOVED: optimizer construction — OptimizerModule deleted

  let dialecticConfig: {
    enabled?: boolean;
    mode?: 'sequential' | 'parallel' | 'adaptive';
    parallel?: { maxWaitMs?: number; observerTimeoutMs?: number; partialResultsOnFailure?: boolean; synchronization?: 'wait-for-both' | 'best-effort' };
    adaptive?: { complexityThreshold?: number; qualityThreshold?: number; historyWindowSize?: number };
    injectAsThoughts?: { enabled?: boolean; mode?: 'parallel' | 'consolidated'; timeoutMs?: number };
    yang?: any;
    yin?: any;
    serenity?: any;
    taskGuide?: any
  } | undefined
  try {
    dialecticConfig = config?.get?.('intelligence.dialectic')
  } catch {
    dialecticConfig = undefined
  }

  // WHY: Parallel mode is fastest for dialectic observers on every turn
  dialecticConfig = dialecticConfig || {}
  dialecticConfig.mode = dialecticConfig.mode ?? 'parallel'
  dialecticConfig.parallel = dialecticConfig.parallel || {
    maxWaitMs: 30000,
    observerTimeoutMs: 15000,
    partialResultsOnFailure: true,
    synchronization: 'best-effort' as const
  }

  // WHY: Wire central runtime default model into dialectic observers when not explicitly configured
  try {
    const defaultProvider = config?.get?.('intelligence.defaultProvider', MODEL_DEFAULTS.fast.provider) as string
    const configuredModel = config?.get?.('intelligence.defaultModel', MODEL_DEFAULTS.fast.model) as string
    const defaultModelFull = configuredModel ? `${defaultProvider}/${configuredModel}` : getModelSpec('reasoning')

    dialecticConfig.yang = dialecticConfig.yang || {}
    dialecticConfig.yin = dialecticConfig.yin || {}
    dialecticConfig.serenity = dialecticConfig.serenity || {}
    dialecticConfig.taskGuide = dialecticConfig.taskGuide || {}

    // WHY: Use background tier model (gpt-4o via github-copilot) for dialectic observers.
    // These run on every turn and need to be unlimited. Model selection can be
    // overridden at runtime via ModelDirective (slot: "dialectic.yang", etc.)
    const dialecticModel = 'github-copilot/gpt-4o'
    dialecticConfig.yang.model = dialecticConfig.yang.model ?? dialecticModel
    dialecticConfig.yin.model = dialecticConfig.yin.model ?? dialecticModel
    dialecticConfig.serenity.model = dialecticConfig.serenity.model ?? dialecticModel

    dialecticConfig.taskGuide.model = dialecticConfig.taskGuide.model ?? 'gpt-4o'
  } catch (err) {
    // WHY: Non-fatal — if config unavailable, proceed with whatever dialecticConfig was provided
    try { logger?.warn?.('createIntelligence: failed to wire default dialectic model from runtime config', { error: String(err) }) } catch { }
  }

  const dialectic = createDialecticSystem(logger.child("dialectic"), dialecticConfig)

  const dmnEnabled = config?.get?.<boolean>('intelligence.dmn.enabled', false) === true
  const dmn = createDmn({
    logger: logger.child('dmn'),
    config: { enabled: dmnEnabled },
  })

  let aiScientistConfig: { enabled?: boolean; studyIntervalHours?: number } | undefined
  try {
    aiScientistConfig = config?.get?.('intelligence.aiScientist')
  } catch {
    aiScientistConfig = undefined
  }
  const aiScientist = createAIScientist(logger.child("ai-scientist"), aiScientistConfig)

  let ruleEnforcerConfig: { enabled?: boolean; strictMode?: boolean; selfCorrect?: boolean } | undefined
  try {
    ruleEnforcerConfig = config?.get?.('intelligence.ruleEnforcer')
  } catch {
    ruleEnforcerConfig = undefined
  }
  const ruleEnforcer = createRuleEnforcer(logger.child("rule-enforcer"), ruleEnforcerConfig)

  let subconsciousConfig: { enabled?: boolean; consolidationIntervalMs?: number } | undefined
  try {
    subconsciousConfig = config?.get?.('intelligence.subconscious')
  } catch {
    subconsciousConfig = undefined
  }
  const subconscious = createSubconscious(logger.child("subconscious"), subconsciousConfig)

  const contextManager = createContextManager(logger.child('context-manager'), memory)

  // REMOVED: Triad Team and Flux Team orchestrators — deprecated systems deleted.
  // All orchestration now uses Helix (single-session inverted pyramid) and 
  // Constellation (multi-Helix tree with Corpus reasoning).

  // SelfHealingAgent — monitors intelligence:processor-error events, locates
  // call sites, proposes and applies patches, then rebuilds and restarts.
  let selfHealerConfig: SelfHealerConfig | undefined
  try {
    selfHealerConfig = config?.get?.('intelligence.selfHealer')
  } catch {
    selfHealerConfig = undefined
  }
  const selfHealer = createSelfHealingAgent(logger.child("self-healer"), selfHealerConfig)
  selfHealer.setMemory?.(memory)

  // AI Engineer — proactive prompt/config evolution for all intelligence modules
  let aiEngineerConfig: { enabled?: boolean; engineerCycleTurns?: number } | undefined
  try {
    aiEngineerConfig = config?.get?.('intelligence.aiEngineer')
  } catch {
    aiEngineerConfig = undefined
  }
  const aiEngineer = createAIEngineer(logger.child("ai-engineer"), aiEngineerConfig)
  aiEngineer.setMemory?.(memory)

  // These three modules form the graduated autonomy system.
  // ConsequenceEstimator: assesses risk of tool calls (priority 75)
  // TrustLedger: maintains per-domain Bayesian trust scores (priority 80)
  // PermissionOracle: combines risk + trust to make allow/deny/escalate decisions (priority 76)
  const consequenceEstimator = createConsequenceEstimator(logger.child("consequence-estimator"))
  consequenceEstimator.setMemory?.(memory)

  const trustLedger = createTrustLedger(logger.child("trust-ledger"))
  trustLedger.setMemory?.(memory)

  const permissionOracle = createPermissionOracle(logger.child("permission-oracle"))
  permissionOracle.setConsequenceEstimator(consequenceEstimator)
  permissionOracle.setTrustLedger(trustLedger)

  // REMOVED: InjectionAggregator — deprecated. Now uses Thalamus/GlobalWorkspace.
  // Thought Observer and CognitiveBridge no longer need injection aggregator wiring.

  // Thought Observer — extracts cognitive signals from the LLM thinking stream.
  const thoughtObserver = createThoughtObserver(logger.child("thought-observer"))
  thoughtObserver.setContextManager(contextManager)

  // CognitiveBridge — links sessions into a shared cognitive space.
  const cognitiveBridge = createCognitiveBridge(logger.child("cognitive-bridge"))
  thoughtObserver.setCognitiveBridge(cognitiveBridge)

  thinker.setMemory?.(memory)

  // deferred until daemon sets them after initialization
  ;(thinker as ThinkerWithDeferredWiring).__awaitingWiring = {
      setSessionManager: () => {},
      setPipelineGetter: () => {},
    } satisfies ThinkerDeferredWiring

  dialectic.setMemory?.(memory)
  aiScientist.setMemory?.(memory)
  ruleEnforcer.setMemory?.(memory)
  subconscious.setMemory?.(memory)

  // REMOVED: triadTeam and fluxTeam memory wiring — deprecated systems deleted

  // Smart Rules Recovery Module — dead-end detection and recovery
  let smartRulesConfig: { enabled?: boolean; maxRetries?: number; minResponseLength?: number; loopDetectionWindow?: number; confidenceThreshold?: number } | undefined
  try {
    smartRulesConfig = config?.get?.('intelligence.smartRules')
  } catch {
    smartRulesConfig = undefined
  }
  const smartRules = createSmartRulesModule(logger.child("smart-rules"))

  // Reflex Module — fast-path routing for deterministic/recurring patterns
  let reflexConfig: { enabled?: boolean; minConfidence?: number; directExecutionThreshold?: number; enableLearning?: boolean } | undefined
  try {
    reflexConfig = config?.get?.('intelligence.reflex')
  } catch {
    reflexConfig = undefined
  }
  const reflex = createReflex(logger.child("reflex"), reflexConfig)

  // Create the IntelligenceRegistry for auto-discovered modules.
  // The registry is synchronously constructed here but async operations
  // (discover, wire, init, start) happen in the daemon boot sequence.
  const registry = new IntelligenceRegistry(logger.child('intelligence-registry'))

  const helix = createHelix(logger.child('helix'), eventBus)

  // Constellation — multi-Helix orchestration with Corpus tree reasoning
  // The CorpusLLM starts as a deferred stub. The daemon wires it to a real
  // ModelHandle once providers are available (see daemon.ts wireProviders).
  let corpusHandle: import('@cassicore/model-pool').ModelHandle | undefined
  let corpusLLMModel = 'claude-opus-4-7'
  const corpusLLM: import('@cassicore/constellation').CorpusLLM = {
    async complete(opts) {
      const corpusLogger = logger.child('corpus-llm')
      if (!corpusHandle) {
        corpusLogger.warn('CorpusLLM called before handle wired — returning empty')
        return { content: '', truncated: false }
      }
      const messages = [{ role: 'user' as const, content: opts.prompt }]
      let content = ''
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), opts.timeoutMs)
      const requestId = `corpus-${Date.now()}`
      writeThoughtRequestLog({
        provider: corpusHandle.provider,
        model: corpusLLMModel,
        sessionId: 'corpus',
        requestId,
        messages,
        toolCount: opts.tools?.length ?? 0,
        timeoutMs: opts.timeoutMs,
      })
      const toolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = []
      try {
        const streamOpts: Record<string, unknown> = {
          model: corpusLLMModel,
          maxTokens: opts.maxTokens,
          thinking: 'none',
          signal: controller.signal,
        }
        if (opts.tools) streamOpts.tools = opts.tools
        if (opts.toolChoice) streamOpts.tool_choice = opts.toolChoice
        for await (const chunk of corpusHandle.stream(messages, streamOpts as any)) {
          if (chunk.type === 'token' && chunk.text) content += chunk.text
          if (chunk.type === 'tool_use' && chunk.toolCall) {
            toolCalls.push(chunk.toolCall)
          }
        }
        writeThoughtResultLog('● CORPUS  complete', {
          requestId,
          model: corpusLLMModel,
          contentLength: content.length,
          toolCallCount: toolCalls.length,
          timeoutMs: opts.timeoutMs,
        })
      } catch (err) {
        corpusLogger.error('CorpusLLM call failed', {
          error: String(err),
          model: corpusLLMModel,
          providerId: corpusHandle.provider,
          promptLength: opts.prompt.length,
          timeoutMs: opts.timeoutMs,
        })
        writeThoughtResultLog('● CORPUS  error', {
          requestId,
          model: corpusLLMModel,
          error: String(err),
        })
        throw err
      } finally { clearTimeout(timeout) }
      return { content, truncated: false, toolCalls: toolCalls.length > 0 ? toolCalls : undefined }
    },
  }
  /** Wire the CorpusLLM to a ModelHandle. Called by the daemon after providers are available. */
  const setCorpusLLMProvider = (handle: import('@cassicore/model-pool').ModelHandle, model?: string) => {
    corpusHandle = handle
    if (model) corpusLLMModel = model
    logger.child('corpus-llm').info('CorpusLLM handle wired', {
      model: corpusLLMModel,
      providerId: handle.provider,
    })
  }

  // Separate LLM for Brainstem annotation — can be a different provider/model
  // than the Corpus organizer. Falls back to corpusLLM when not wired.
  let brainstemHandle: import('@cassicore/model-pool').ModelHandle | undefined
  let brainstemLLMModel = 'claude-haiku-4-5'
  const brainstemLLM: import('@cassicore/constellation').CorpusLLM = {
    async complete(opts) {
      const bsLogger = logger.child('brainstem-llm')
      // HOW: Fall back to corpusLLM when brainstem handle is not explicitly wired
      if (!brainstemHandle) {
        return corpusLLM.complete(opts)
      }
      const messages = [{ role: 'user' as const, content: opts.prompt }]
      let content = ''
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), opts.timeoutMs)
      const requestId = `brainstem-${Date.now()}`
      writeThoughtRequestLog({
        provider: brainstemHandle.provider,
        model: brainstemLLMModel,
        sessionId: 'brainstem',
        requestId,
        messages,
        toolCount: 0,
        timeoutMs: opts.timeoutMs,
      })
      try {
        for await (const chunk of brainstemHandle.stream(messages, {
          model: brainstemLLMModel,
          maxTokens: opts.maxTokens,
          thinking: 'none',
          signal: controller.signal,
        })) {
          if (chunk.type === 'token' && chunk.text) content += chunk.text
        }
        writeThoughtResultLog('● BRAINSTEM  complete', {
          requestId,
          model: brainstemLLMModel,
          contentLength: content.length,
          timeoutMs: opts.timeoutMs,
        })
      } catch (err) {
        bsLogger.error('BrainstemLLM call failed', {
          error: String(err),
          model: brainstemLLMModel,
          providerId: brainstemHandle.provider,
          promptLength: opts.prompt.length,
          timeoutMs: opts.timeoutMs,
        })
        writeThoughtResultLog('● BRAINSTEM  error', {
          requestId,
          model: brainstemLLMModel,
          error: String(err),
        })
        throw err
      } finally { clearTimeout(timeout) }
      return { content, truncated: false }
    },
  }
  /** Wire the BrainstemLLM to a ModelHandle. Called by the daemon after providers are available. */
  const setBrainstemLLMProvider = (handle: import('@cassicore/model-pool').ModelHandle, model?: string) => {
    brainstemHandle = handle
    if (model) brainstemLLMModel = model
    logger.child('brainstem-llm').info('BrainstemLLM handle wired', {
      model: brainstemLLMModel,
      providerId: handle.provider,
    })
  }
  const constellationRegistry = new ConstellationRegistry()
  const constellationGuidanceRegistry = new ConstellationGuidanceRegistry()
  const constellation = createConstellationOrchestrator({
    logger: logger.child('constellation'),
    eventBus: eventBus! as any,
    corpusLLM,
    brainstemLLM,
    registry: constellationRegistry,
    guidanceRegistry: constellationGuidanceRegistry,
  })

  // REMOVED: constellation.setMemory/setMnemicField — MemoryModule deleted.
  // MnemicField is wired by the daemon after boot.

  // Improvement Orchestrator — self-improvement loop with verification-gated adaptations.
  // Coordinates AdaptiveBehavior, AIEngineer, AIScientist through a scenario-backed gate.
  let improvementConfig: { enabled?: boolean; gateMode?: 'sync' | 'async' } | undefined
  try {
    improvementConfig = config?.get?.('intelligence.improvementOrchestrator')
  } catch {
    improvementConfig = undefined
  }
  const improvementOrchestrator = createImprovementOrchestrator(logger.child("improvement-orchestrator"), improvementConfig)

  // Dreamer — idle-time memory synthesis and garden curation
  let dreamerConfig: Record<string, unknown> | undefined
  try {
    dreamerConfig = config?.get?.('intelligence.dreamer')
  } catch {
    dreamerConfig = undefined
  }
  const dreamer = createDreamer(logger.child("dreamer"), dreamerConfig)
  dreamer.setFullMemory(memory)

  // Reasoning Bank — shared reasoning trace cache
  let reasoningBank: ReasoningBank | undefined
  try {
    reasoningBank = new ReasoningBank(logger)
    dreamer.setReasoningBank(reasoningBank)
  } catch (err) {
    try { logger?.warn?.('Reasoning Bank failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // Meditation — idle-time constellation exploration
  let meditationConfig: Record<string, unknown> | undefined
  let meditation: MeditationController | undefined
  try {
    meditationConfig = config?.get?.('intelligence.meditation')
  } catch {
    meditationConfig = undefined
  }
  try {
    meditation = createMeditationController(logger.child("meditation"), meditationConfig)
    meditation.setOrchestrator(constellation)
    meditation.setConstellationRegistry(constellationRegistry)
    // REMOVED: meditation.setMemory/setMnemicField — MemoryModule deleted.
    // MnemicField is wired by the daemon after boot.
    if (eventBus) (meditation as any).setEventBus(eventBus)
  } catch (err) {
    try { logger?.warn?.('Meditation controller failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  const setMeditationHandleFactory = meditation
    ? (factory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<any>) => meditation!.setHandleFactory(factory)
    : undefined

  // Heart Module — periodic autonomous agent heartbeats
  let heartConfig: Record<string, unknown> | undefined
  try {
    heartConfig = config?.get?.('intelligence.heart')
  } catch {
    heartConfig = undefined
  }
  const heart = createHeartModule(logger.child("heart"))
  heart.wire({ memory, eventBus, config, pipeline: undefined, sessionManager: undefined, pluginHost: undefined })

  // Training Warehouse — separate database for training data collection and export.
  // Uses the daemon's dataDir to locate both training.db and source operational databases.
  let training: TrainingWarehouse | undefined
  try {
    let trainingDataDir = ''
    try {
      trainingDataDir = String(config?.get?.('dataDir') ?? '')
    } catch {
      trainingDataDir = ''
    }
    if (!trainingDataDir) {
      trainingDataDir = path.join(homedir(), '.cassicore', 'data')
    }
    const sources = TrainingWarehouse.detectSources(trainingDataDir)
    training = new TrainingWarehouse({ dataDir: trainingDataDir, sources }, logger)
  } catch (err) {
    try { logger?.warn?.('Training warehouse failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // Global Workspace — GWT-based attention and broadcasting
  let globalWorkspace: GlobalWorkspaceType | undefined
  try {
    globalWorkspace = new GlobalWorkspace(logger.child('workspace'))
    if (eventBus) globalWorkspace.setEventBus(eventBus)
  } catch (err) {
    try { logger?.warn?.('Global Workspace failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // Wire Global Workspace into all modules that support it
  if (globalWorkspace) {
    const wireTarget = [memory, recover, thinker, aiScientist, aiEngineer, ruleEnforcer, subconscious, contextManager, selfHealer, consequenceEstimator, trustLedger, permissionOracle, improvementOrchestrator, smartRules, reflex, dreamer, heart]
    for (const mod of wireTarget) {
      if (mod && typeof (mod as any).setGlobalWorkspace === 'function') {
        (mod as any).setGlobalWorkspace(globalWorkspace)
      }
    }
    if (meditation && typeof (meditation as any).setGlobalWorkspace === 'function') {
      (meditation as any).setGlobalWorkspace(globalWorkspace)
    }
  }

  // LocusBridge — persistent attentional context assembly
  let locusBridge: LocusBridgeType | undefined
  try {
    const bridgeConfig: Record<string, any> = {}
    try {
      const raw = config?.get?.('intelligence.locusBridge') as Record<string, any> | undefined
      if (raw) Object.assign(bridgeConfig, raw)
    } catch { /* no config section — use defaults */ }

    locusBridge = new LocusBridge({
      logger: logger.child('locus-bridge'),
      config: bridgeConfig,
    })

    // Wire memory retriever — MemoryShim provides the search backend
    locusBridge.setMemoryRetriever({
      search: async (query: string, opts?: { limit?: number }) => {
        const results = await memory.search(query, { limit: opts?.limit ?? 10 })
        return results.map(r => ({
          entry: { content: r.entry?.content || '', type: r.entry?.type || 'memory' },
          score: r.score ?? 0,
          source: 'memory',
        }))
      },
    })
  } catch (err) {
    try { logger?.warn?.('LocusBridge failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // CorticalField — self-organizing working memory surface
  let cortex: CorticalFieldType | undefined
  try {
    cortex = new CorticalField(logger)
    const cortexTargets = [subconscious, thinker, dialectic, meditation]
    for (const mod of cortexTargets) {
      if (mod && typeof (mod as any).setCortex === 'function') {
        (mod as any).setCortex(cortex)
      }
    }
  } catch (err) {
    try { logger?.warn?.('CorticalField failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // AuditStore + LaminaField — provenance + labeled memory blocks
  let audit: AuditStoreType | undefined
  let lamina: LaminaFieldType | undefined
  try {
    audit = new AuditStore(logger)
    lamina = new LaminaField(logger)
    lamina.seedDefaults()
    // REMOVED: LaminaInjectionSource registration — InjectionAggregator deleted.
    // Lamina content is now accessed directly by Thalamus.
    constellation.setLamina(lamina)
    logger?.info?.('Lamina + Audit initialized', { metrics: lamina.metrics() })
  } catch (err) {
    try { logger?.warn?.('Lamina/Audit failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // .claude memory bridge — one-way import of Claude Code's per-project memory.
  // See docs/CLAUDE_MEMORY_BRIDGE.md.
  if (lamina && process.env.CASSICORE_DISABLE_CLAUDE_IMPORT !== '1') {
    try {
      // Static import — keeps createIntelligence synchronous
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const importer = new ClaudeMemoryImporter(logger, lamina as any, {}, undefined, memory as any, audit as any)
      // Fire-and-forget; never block boot
      importer.importAll().then((summary: { files: number }) => {
        if (summary.files > 0) logger?.info?.('[claude-import] complete', summary)
      }).catch((err: unknown) => logger?.debug?.('[claude-import] failed', { error: String(err) }))
    } catch (err) {
      try { logger?.debug?.('Claude memory importer disabled', { error: String(err) }) } catch { /* best-effort */ }
    }
  }

  // Reverie — ambient in-flight memory curator (depends on Lamina + Audit)
  let reverie: ReverieModule | undefined
  if (lamina && audit) {
    try {
      reverie = new ReverieModule(logger)
      reverie.setLamina(lamina)
      reverie.setAudit(audit as any)
      registry.registerInstance(reverie as any)
      logger?.info?.('Reverie initialized')
    } catch (err) {
      try { logger?.warn?.('Reverie failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
    }
  }

  // Context Repository — git-backed memory projection (Phase 3, default disabled)
  let contextRepo: ContextRepo | undefined
  try {
    const projectPath = process.env.CASSICORE_PROJECT_PATH || process.cwd()
    const enabled = process.env.CASSICORE_CONTEXT_REPO !== '0'
    contextRepo = new ContextRepo(logger, projectPath, { enabled })
    if (enabled) {
      logger?.info?.('Context Repository enabled', { projectPath })
      // REMOVED: ContextRepoInjectionSource — InjectionAggregator deleted.
      if (eventBus) contextRepo.subscribeToEventBus(eventBus, meditation as any)
      // Wire writeback — manual edits in context-repo files propagate back to Mnemic
      if (meditation) {
        const mnemicField = (meditation as any).getMnemicField?.()
        if (mnemicField) {
          const target = new MnemicWritebackTarget(mnemicField, logger.child('writeback'))
          contextRepo.configureWriteback(target, logger.child('writeback'))
          contextRepo.startScanLoop(30_000)
          logger?.info?.('ContextRepo writeback wired to MnemicField')
        }
      }
    }
  } catch (err) {
    try { logger?.warn?.('ContextRepo failed to initialize', { error: String(err) }) } catch { /* best-effort */ }
  }

  // WHY: `continuity` is a plain adapter object (no name/priority) — excluded from all[].
  // WHY: `reflect` is the same ErrorLearner instance as `recover` — only `recover` is in
  // all[] to prevent the same module's hooks running twice per turn.
  // REMOVED: triadTeam and fluxTeam from allModules — deprecated systems deleted
  // REMOVED: memory from allModules — MemoryShim is not a PrioritizedModule (no name/priority)
  const allModules: PrioritizedModule[] = [recover, thinker, dialectic as unknown as PrioritizedModule, aiScientist, aiEngineer, ruleEnforcer, subconscious, contextManager, selfHealer, consequenceEstimator, trustLedger, permissionOracle, improvementOrchestrator, smartRules, reflex, dreamer, heart]
  if (meditation) allModules.push(meditation as unknown as PrioritizedModule)
  const all = allModules.sort((a, b) => b.priority - a.priority)

  // REMOVED: triadTeam and fluxTeam from return — deprecated systems deleted
  return { memory, continuity, recover, reflect, thinker, dialectic, dmn, aiScientist, aiEngineer, ruleEnforcer, subconscious, contextManager, helix, constellation, selfHealer, consequenceEstimator, trustLedger,   permissionOracle, thoughtObserver, cognitiveBridge, improvementOrchestrator, smartRules, reflex, dreamer, meditation, heart, registry, training, reasoningBank, constellationGuidanceRegistry, setCorpusLLMProvider, setBrainstemLLMProvider, setMeditationHandleFactory, globalWorkspace, locusBridge, cortex, lamina, audit, reverie, contextRepo, all }
}
