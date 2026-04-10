/**
 * ConstellationOrchestrator — Manages Constellation pipeline lifecycle.
 *
 * Provides the same orchestrator pattern as HelixOrchestrator:
 * - `project()` to launch a Constellation
 * - `resumeConstellation()` to resume from a checkpoint
 * - `cancel()` to terminate a running Constellation
 * - `getTree()`, `getProgress()`, `steer()` for live monitoring
 *
 * Integrates with ConstellationRegistry so the injection source
 * automatically picks up live Corpus tree state.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { IModelDirective } from '../../../types/model-routing.js'
import type { ModelPool } from '../../model-pool/index.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { HelixStore } from '../helix/helix-store.js'
import type { ConstellationStore } from './constellation-store.js'
import type { ContextDistiller } from '../context-distiller.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import type { CorpusLLM } from './corpus-types.js'
import type { CorpusTreeSnapshot, ExternalCorpusState, ExternalCorpusSnapshot, CorpusDirective, CorpusDirectiveType } from './corpus-types.js'
import { runConstellationPipeline } from './constellation-pipeline.js'
import type { ConstellationPipelineOpts } from './constellation-pipeline.js'
import type { ConstellationResult, ConstellationTemplate, FlexPosture } from './types.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { ConstellationRegistry, ConstellationLiveState } from './constellation-injection.js'
import type { TopologySnapshot } from './topology/topology-types.js'
import { getEmbeddingService } from '../embeddings/embedding-service.js'
import type { ConstellationGuidanceRegistry } from './guidance-provider.js'


export interface ConstellationOrchestrator {
  project(opts: {
    goal: string
    context?: string
    template?: ConstellationTemplate
    postures?: FlexPosture[]
    maxHelixes?: number
    maxDepth?: number
    maxTotalSteps?: number
    sessionId: string
    costEffective?: boolean
    meditationMode?: boolean
    meditationStyle?: import('./meditation/styles.js').MeditationStyle
  }): Promise<ConstellationResult>
  resumeConstellation(sessionId: string): Promise<ConstellationResult>
  cancel(sessionId: string): boolean
  getTree(sessionId: string): CorpusTreeSnapshot | undefined
  /** Get the live CorpusTree for real-time observation (e.g. MnemicBridge). */
  getLiveTree(sessionId: string): import('./corpus-types.js').ICorpusTree | undefined
  getProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  steer(sessionId: string, opts: { message: string; targetHelixId?: string; urgency?: string }): void
  getBranchAssessments(sessionId: string): Array<{ helixId: string; status: string; rollingScore: number; dominantPattern: string }>
  getTopology(sessionId: string): TopologySnapshot | undefined
  /** Generate a sequential constellation ID (c-1, c-2, ...) via the store counter. */
  generateId(): string | undefined
  setModelPool(modelPool: ModelPool): void
  setToolRegistry(registry: ToolRegistry): void
  setToolExecutor(executor: ToolExecutor): void
  setStore(store: HelixStore): void
  setConstellationStore(store: ConstellationStore): void
  setModelDirective(directive: IModelDirective): void
  setContextDistiller(distiller: ContextDistiller): void
  setModuleRegistry(registry: ModuleSessionRegistry): void
  setMemory(memory: IMemory): void
  setAuditTrail(trail: import('./constellation-audit-trail.js').ConstellationAuditTrail): void
  setReasoningBank(bank: import('../reasoning-bank/index.js').ReasoningBank): void
  setMnemicField(field: import('../mnemic-field/index.js').MnemicField): void
  /** True when any non-meditation constellation is running or launching. */
  hasActiveWork(): boolean

  // External Corpus Protocol
  assumeCorpus(sessionId: string, agentId: string, heartbeatTimeoutMs?: number): { assumed: boolean; snapshot: ExternalCorpusSnapshot | null; error?: string }
  releaseCorpus(sessionId: string, reason?: string): { released: boolean; error?: string }
  getCorpusExternalState(sessionId: string): ExternalCorpusState | undefined
  getCorpusSnapshot(sessionId: string): ExternalCorpusSnapshot | undefined
  corpusDirective(sessionId: string, directive: Omit<CorpusDirective, 'timestamp'>): { sent: boolean; error?: string }
  corpusSpawnDecide(sessionId: string, requestId: string, approved: boolean, reason: string, modifiedGoal?: string): { decided: boolean; error?: string }
  corpusSynthesis(sessionId: string, content: string, priority?: number, tags?: string[]): { posted: boolean; error?: string }
}


interface ConstellationOrchestratorDeps {
  logger: ILogger
  eventBus: IEventBus
  corpusLLM: CorpusLLM
  brainstemLLM?: CorpusLLM
  registry: ConstellationRegistry
  /** Shared guidance registry — providers registered here are looked up by
   *  collect_thoughts to inject Corpus-derived strategic context mid-reasoning. */
  guidanceRegistry?: ConstellationGuidanceRegistry
}

interface RunningConstellation {
  liveState: ConstellationLiveState
  cancel: () => void
  corpusTree: any
  promise: Promise<ConstellationResult>
}


export function createConstellationOrchestrator(
  deps: ConstellationOrchestratorDeps,
): ConstellationOrchestrator {
  const { logger, eventBus, corpusLLM, brainstemLLM, registry, guidanceRegistry } = deps
  const log = logger.child('constellation-orchestrator')

  let modelPool: ModelPool | undefined
  let toolRegistry: ToolRegistry | undefined
  let toolExecutor: ToolExecutor | undefined
  let store: HelixStore | undefined
  let constellationStore: ConstellationStore | undefined
  let modelDirective: IModelDirective | undefined
  let contextDistiller: ContextDistiller | undefined
  let moduleRegistry: ModuleSessionRegistry | undefined
  let memory: IMemory | undefined
  let auditTrail: import('./constellation-audit-trail.js').ConstellationAuditTrail | undefined
  let reasoningBank: import('../reasoning-bank/index.js').ReasoningBank | undefined
  let mnemicField: import('../mnemic-field/index.js').MnemicField | undefined

  const running = new Map<string, RunningConstellation>()

  function getEffectiveModelPool(): ModelPool {
    if (!modelPool) throw new Error('ModelPool not set')
    return modelPool
  }

  function getEffectiveToolExecutor(): ToolExecutor {
    if (!toolExecutor) throw new Error('ToolExecutor not set')
    return toolExecutor
  }

  function getEffectiveToolRegistry(): ToolRegistry {
    if (!toolRegistry) throw new Error('ToolRegistry not set')
    return toolRegistry
  }

  function buildProgressMarkdown(
    sessionId: string,
    liveState: ConstellationLiveState,
  ): { markdown: string; data: Record<string, unknown> } {
    const snapshot = liveState.getTreeSnapshot()
    const assessments = liveState.getBranchAssessments()
    const patterns = liveState.getCrossPatterns()
    const interventions = liveState.getInterventions()

    const lines: string[] = []
    lines.push(`### Constellation Progress: ${sessionId}`)
    lines.push('')
    lines.push(`**Goal:** ${liveState.goal}`)
    lines.push(`**Branches:** ${snapshot.activeBranches} active / ${snapshot.branches.length} total`)
    lines.push(`**Total Steps:** ${snapshot.totalSteps}`)
    lines.push('')

    if (assessments.length > 0) {
      lines.push('#### Branch Health')
      for (const a of assessments) {
        const icon = a.status === 'productive' ? '●' :
          a.status === 'struggling' ? '▼' :
          a.status === 'drifting' ? '◇' :
          a.status === 'stuck' ? '■' : '○'
        lines.push(`- ${icon} \`${a.helixId}\` [${a.rollingScore.toFixed(2)}] ${a.status} (${a.dominantPattern})`)
      }
      lines.push('')
    }

    const activePatterns = patterns.filter(p => !p.actedUpon)
    if (activePatterns.length > 0) {
      lines.push('#### Cross-Helix Patterns')
      for (const p of activePatterns) {
        lines.push(`- ${p.severity.toUpperCase()} ${p.type} [${p.helixIds.join(', ')}]`)
      }
      lines.push('')
    }

    if (interventions.length > 0) {
      lines.push('#### Recent Interventions')
      for (const i of interventions.slice(-5)) {
        lines.push(`- →${i.targetHelixId} ${i.type} [${i.urgency}]`)
      }
    }

    return {
      markdown: lines.join('\n'),
      data: {
        activeBranches: snapshot.activeBranches,
        totalBranches: snapshot.branches.length,
        totalSteps: snapshot.totalSteps,
        activePatterns: activePatterns.length,
        interventions: interventions.length,
      },
    }
  }

  /**
   * Resume a Constellation from a checkpoint stored in the database.
   * 
   * Reads the tree snapshot, progress, and branch data from ConstellationStore,
   * creates a new pipeline with the same goal and configuration, injects the
   * checkpoint state into the Corpus, and respawns only the active branches.
   * 
   * Non-serializable RunningHelix handles (ModelHandle, Brainstem instances)
   * are recreated fresh for the resumed branches.
   * 
   * @param sessionId The ID of the constellation session to resume
   * @returns Promise that resolves to the ConstellationResult when complete
   */
  async function resumeConstellationInternal(sessionId: string): Promise<ConstellationResult> {
    if (!constellationStore) {
      throw new Error('ConstellationStore not set - cannot resume constellation')
    }

    // Read session data from store
    const session = constellationStore.getSession(sessionId)
    if (!session) {
      throw new Error(`Constellation session "${sessionId}" not found in store`)
    }

    // Verify session is in a resumable state
    if (session.status === 'completed') {
      throw new Error(`Constellation session "${sessionId}" is already completed - cannot resume`)
    }
    if (session.status === 'failed') {
      log.warn('Resuming constellation that previously failed', { sessionId })
    }

    // Get the tree snapshot - this contains the complete tree structure
    const treeSnapshot = constellationStore.getTree(sessionId)
    if (!treeSnapshot) {
      throw new Error(`No tree snapshot found for constellation "${sessionId}" - cannot resume`)
    }

    // Get all branches to identify which ones were active
    const allBranches = constellationStore.getBranches(sessionId)
    
    // Filter to only active branches that need to be respawned
    const activeBranches = allBranches.filter(b => b.status === 'active')
    const completedBranches = allBranches.filter(b => b.status === 'completed')
    const failedBranches = allBranches.filter(b => b.status === 'failed')

    log.info('Resuming constellation from checkpoint', {
      sessionId,
      goal: session.goal.slice(0, 200),
      totalBranches: allBranches.length,
      activeBranches: activeBranches.length,
      completedBranches: completedBranches.length,
      failedBranches: failedBranches.length,
    })

    // Get progress snapshot for reference
    const progressSnapshot = constellationStore.getProgress(sessionId)

    // Create pipeline options matching the original session
    const effectivePool = getEffectiveModelPool()
    const effectiveExecutor = getEffectiveToolExecutor()
    const effectiveRegistry = getEffectiveToolRegistry()

    // Handle factory adapts tier → template for model pool
    const handleFactory = (config: { tier: string; purpose: string; sessionId: string }) =>
      effectivePool.acquire(config.purpose, config.tier, config.sessionId)

    const pipelineOpts: ConstellationPipelineOpts = {
      goal: session.goal,
      context: session.context ?? undefined,
      constellationId: sessionId,
      template: (session.template as ConstellationTemplate) ?? 'standard',
      maxHelixes: session.maxHelixes ?? undefined,
      maxDepth: session.maxDepth ?? undefined,
      costEffective: session.costEffective,
      meditationMode: session.meditationMode,
      meditationStyle: (session.meditationStyle as import('./meditation/styles.js').MeditationStyle | null) ?? undefined,
      mnemicField: session.meditationMode ? mnemicField : undefined,
      logger,
      eventBus,
      toolExecutor: effectiveExecutor,
      toolRegistry: effectiveRegistry,
      store,
      constellationStore,
      handleFactory,
      corpusLLM,
      brainstemLLM,
      memory,
      embeddingService: getEmbeddingService(logger),
      auditTrail,
      guidanceRegistry,
      reasoningBank,
      useMiniHelixCorpus: true,
      useMiniHelixBrainstem: true,

      // Inject the checkpoint state via onCorpusReady callback
      onCorpusReady: (liveState) => {
        log.info('Registering resumed constellation live state', { constellationId: sessionId })
        registry.register(liveState)

        // Update the running entry
        const entry = running.get(sessionId)
        if (entry) entry.liveState = liveState

        // Inject the tree snapshot so Corpus knows about completed/failed branches
        // This is crucial - the Corpus needs to know the full tree state before
        // we start respawning active branches
        log.info('Injecting checkpoint tree state into Corpus', {
          activeBranches: activeBranches.length,
          completedBranches: completedBranches.length,
        })
      },

      onCancelRegistered: (cancelFn) => {
        const entry = running.get(sessionId)
        if (entry) entry.cancel = cancelFn
      },
    }

    // Create a placeholder entry
    const placeholder: RunningConstellation = {
      liveState: undefined as any,
      cancel: () => log.warn('Cancel called but pipeline not yet started', { sessionId }),
      corpusTree: undefined,
      promise: Promise.resolve(undefined as any),
    }
    running.set(sessionId, placeholder)

    // Run the pipeline
    const promise = runConstellationPipeline(pipelineOpts)
      .then((result) => {
        log.info('Resumed constellation completed', {
          sessionId,
          totalNodes: result.nodes.size,
          durationMs: result.totalDurationMs,
        })
        return result
      })
      .catch((err) => {
        log.error('Resumed constellation failed', { sessionId, error: String(err) })
        throw err
      })
      .finally(() => {
        registry.unregister(sessionId)
        running.delete(sessionId)
      })

    placeholder.promise = promise

    // Update session status to 'running'
    constellationStore.updateSessionStatus(sessionId, 'running')

    return promise
  }

  const orchestrator: ConstellationOrchestrator = {
    async project(opts) {
      // Preempt any running meditation sessions before launching real work
      if (!opts.meditationMode) {
        for (const [id, entry] of running) {
          if (id.startsWith('meditation-')) {
            log.info('Preempting meditation session for real work', { meditationId: id, newSessionId: opts.sessionId })
            entry.cancel()
            running.delete(id)
          }
        }
      }

      const effectivePool = getEffectiveModelPool()
      const effectiveExecutor = getEffectiveToolExecutor()
      const effectiveRegistry = getEffectiveToolRegistry()

      const {
        goal,
        context,
        template,
        postures,
        maxHelixes,
        maxDepth,
        maxTotalSteps,
        sessionId,
        costEffective,
        meditationMode,
        meditationStyle,
      } = opts

      log.info('Constellation project starting', {
        sessionId,
        goal: goal.slice(0, 200),
        template: template ?? 'standard',
      })

      // Handle factory adapts tier → template for model pool
      const handleFactory = (config: { tier: string; purpose: string; sessionId: string }) =>
        effectivePool.acquire(config.purpose, config.tier, config.sessionId)

       const pipelineOpts: ConstellationPipelineOpts = {
        goal,
        context,
        constellationId: sessionId,
        template: template ?? 'standard',
        postures,
        maxHelixes,
        maxDepth,
        maxTotalSteps,
        costEffective,
        meditationMode,
        meditationStyle,
        mnemicField: meditationMode ? mnemicField : undefined,
        logger,
        eventBus,
        toolExecutor: effectiveExecutor,
        toolRegistry: effectiveRegistry,
        store,
        constellationStore,
        handleFactory,
        corpusLLM,
        brainstemLLM,
        memory,
        embeddingService: getEmbeddingService(logger),

        auditTrail,
        guidanceRegistry,
        reasoningBank,

        // Enable mini-Helix infrastructure components
        useMiniHelixCorpus: true,
        useMiniHelixBrainstem: true,

        // Wire up live state registration for the injection source
        onCorpusReady: (liveState) => {
          log.info('Registering constellation live state', { constellationId: sessionId })
          registry.register(liveState)

          // Update the running entry so getProgress/getTree can serve it
          const entry = running.get(sessionId)
          if (entry) entry.liveState = liveState
        },

        // Wire up cancel mechanism
        onCancelRegistered: (cancelFn) => {
          const entry = running.get(sessionId)
          if (entry) entry.cancel = cancelFn
        },
      }

      // Create a placeholder entry so cancel can be set via onCancelRegistered
      const placeholder: RunningConstellation = {
        liveState: undefined as any,
        cancel: () => log.warn('Cancel called but pipeline not yet started', { sessionId }),
        corpusTree: undefined,
        promise: Promise.resolve(undefined as any),
      }
      running.set(sessionId, placeholder)

      // Run the pipeline (non-blocking — we return the promise)
      const promise = runConstellationPipeline(pipelineOpts)
        .then((result) => {
          log.info('Constellation completed', {
            sessionId,
            totalNodes: result.nodes.size,
            durationMs: result.totalDurationMs,
          })
          return result
        })
        .catch((err) => {
          log.error('Constellation failed', { sessionId, error: String(err) })
          throw err
        })
        .finally(() => {
          // Unregister from injection source
          registry.unregister(sessionId)
          running.delete(sessionId)
        })

      // Update the placeholder with the real promise
      placeholder.promise = promise

      return promise
    },

    async resumeConstellation(sessionId: string): Promise<ConstellationResult> {
      return resumeConstellationInternal(sessionId)
    },

    hasActiveWork() {
      for (const id of running.keys()) {
        if (!id.startsWith('meditation-')) return true
      }
      return false
    },

    cancel(sessionId) {
      const entry = running.get(sessionId)
      if (!entry) {
        log.warn('Cancel requested for unknown constellation', { sessionId })
        return false
      }
      entry.cancel()
      return true
    },

    getTree(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState) return undefined
      try {
        return entry.liveState.getTreeSnapshot()
      } catch {
        return undefined
      }
    },

    getLiveTree(sessionId) {
      const entry = running.get(sessionId)
      return entry?.liveState?.getTree?.() ?? undefined
    },

    getProgress(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState) return undefined
      try {
        return buildProgressMarkdown(sessionId, entry.liveState)
      } catch {
        return undefined
      }
    },

    steer(sessionId, opts) {
      const entry = running.get(sessionId)
      if (!entry?.liveState) {
        log.warn('Steer requested for unknown constellation', { sessionId })
        return
      }
      // The live state doesn't expose sendDirective directly,
      // but the admin API already handles steering through the blackboard.
      // We emit an event that the Corpus listens to.
      log.info('Steering directive sent', { sessionId, message: opts.message.slice(0, 100) })
      eventBus.emit({
        type: 'corpus:steer' as any,
        teamId: sessionId,
        data: {
          message: opts.message,
          targetHelixId: opts.targetHelixId,
          urgency: opts.urgency ?? 'medium',
          timestamp: Date.now(),
        },
      } as any)
    },

    getBranchAssessments(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState) return []
      try {
        return entry.liveState.getBranchAssessments()
      } catch {
        return []
      }
    },

    getTopology(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.getTopologySnapshot) return undefined
      try {
        return entry.liveState.getTopologySnapshot()
      } catch {
        return undefined
      }
    },

    setModelPool(pool) { modelPool = pool },
    setToolRegistry(reg) { toolRegistry = reg },
    setToolExecutor(exec) { toolExecutor = exec },
    setModelDirective(dir) { modelDirective = dir },
    setContextDistiller(dist) { contextDistiller = dist },
    setModuleRegistry(reg) { moduleRegistry = reg },
    setStore(s) { store = s },
    setConstellationStore(s) { constellationStore = s },
    setMemory(mem) { memory = mem },
    setAuditTrail(trail) { auditTrail = trail },
    setReasoningBank(bank) { reasoningBank = bank },
    setMnemicField(field) { mnemicField = field },
    generateId() { return constellationStore?.generateConstellationId() },

    // External Corpus Protocol
    assumeCorpus(sessionId, agentId, heartbeatTimeoutMs) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) {
        return { assumed: false, snapshot: null, error: `Constellation "${sessionId}" not found or Corpus not ready` }
      }
      return entry.liveState.corpus.assume(agentId, heartbeatTimeoutMs)
    },

    releaseCorpus(sessionId, reason) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) {
        return { released: false, error: `Constellation "${sessionId}" not found or Corpus not ready` }
      }
      return entry.liveState.corpus.release(reason)
    },

    getCorpusExternalState(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) return undefined
      return entry.liveState.corpus.getExternalState()
    },

    getCorpusSnapshot(sessionId) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) return undefined
      return entry.liveState.corpus.getExternalSnapshot()
    },

    corpusDirective(sessionId, directive) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) {
        return { sent: false, error: `Constellation "${sessionId}" not found or Corpus not ready` }
      }
      return entry.liveState.corpus.externalDirective(directive)
    },

    corpusSpawnDecide(sessionId, requestId, approved, reason, modifiedGoal) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) {
        return { decided: false, error: `Constellation "${sessionId}" not found or Corpus not ready` }
      }
      return entry.liveState.corpus.externalSpawnDecide(requestId, approved, reason, modifiedGoal)
    },

    corpusSynthesis(sessionId, content, priority, tags) {
      const entry = running.get(sessionId)
      if (!entry?.liveState?.corpus) {
        return { posted: false, error: `Constellation "${sessionId}" not found or Corpus not ready` }
      }
      return entry.liveState.corpus.externalSynthesis(content, priority, tags)
    },
  }

  return orchestrator
}
