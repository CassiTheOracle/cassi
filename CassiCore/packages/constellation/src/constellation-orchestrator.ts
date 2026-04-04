/**
 * ConstellationOrchestrator — Manages Constellation pipeline lifecycle.
 *
 * Provides the same orchestrator pattern as HelixOrchestrator:
 * - `project()` to launch a Constellation
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


export interface ConstellationOrchestrator {
  project(opts: {
    goal: string
    context?: string
    template?: ConstellationTemplate
    postures?: FlexPosture[]
    maxHelixes?: number
    maxDepth?: number
    sessionId: string
    costEffective?: boolean
  }): Promise<ConstellationResult>
  cancel(sessionId: string): boolean
  getTree(sessionId: string): CorpusTreeSnapshot | undefined
  getProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  steer(sessionId: string, opts: { message: string; targetHelixId?: string; urgency?: string }): void
  getBranchAssessments(sessionId: string): Array<{ helixId: string; status: string; rollingScore: number; dominantPattern: string }>
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
  const { logger, eventBus, corpusLLM, brainstemLLM, registry } = deps
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

  const orchestrator: ConstellationOrchestrator = {
    async project(opts) {
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
        sessionId,
        costEffective,
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
        costEffective,
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

        auditTrail,

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
