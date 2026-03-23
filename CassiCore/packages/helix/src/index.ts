/*
 * Helix — Inverted-Pyramid Agent Pattern
 *
 * One worker (Unity) at the base, two concurrent reviewers (Yang + Yin) above.
 * Named after the double helix trail of binary stars — Unity is the barycenter,
 * Yang and Yin are the orbiting stars.
 *
 * Communication topology:
 *   Unity <-> Reviewers: WorkStream (work units, nudges)
 *   Yang  <-> Yin:       DialecticChannel (findings, challenges, concessions)
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { IModelDirective } from '../../../types/model-routing.js'
import type { ContextDistiller } from '../context-distiller.js'
import type { ModelPool } from '../../model-pool/index.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { HelixProjectOpts, HelixResult } from './types.js'
import type { DyadStore } from '../dyad/dyad-store.js'
import type { BlackboardState } from '../../../types/flux-team.js'
import type { Blackboard } from '../flux-team/blackboard.js'
import type { WorkStream } from '../dyad/work-stream.js'
import type { DialecticChannel } from '../lumen/dialectic-channel.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import { runHelixPipeline } from './helix-pipeline.js'


export interface HelixOrchestrator {
  project(opts: HelixProjectOpts): Promise<HelixResult>
  cancel(sessionId: string): boolean
  getActiveSessions(): string[]
  getActiveBlackboard(sessionId: string): BlackboardState | undefined
  getActiveProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  setModelPool(modelPool: ModelPool): void
  setToolRegistry(registry: ToolRegistry): void
  setToolExecutor(executor: ToolExecutor): void
  setStore(store: DyadStore): void
  setModelDirective(directive: IModelDirective): void
  setContextDistiller(distiller: ContextDistiller): void
  setModuleRegistry(registry: ModuleSessionRegistry): void
  getHealth(): { healthy: boolean; lastRun?: Date; errorCount: number }
}


export function createHelix(
  logger: ILogger,
  eventBus?: IEventBus,
  modelPool?: ModelPool,
): HelixOrchestrator {
  let lastRun: Date | undefined
  let errorCount = 0
  let storedModelPool: ModelPool | undefined = modelPool
  let storedEventBus: IEventBus | undefined = eventBus
  let storedToolRegistry: ToolRegistry | undefined
  let storedToolExecutor: ToolExecutor | undefined
  let storedStore: DyadStore | undefined
  let storedModelDirective: IModelDirective | undefined
  let storedContextDistiller: ContextDistiller | undefined
  let storedModuleDebugSessionId: string | undefined
  const activeSessions = new Map<string, () => void>()
  const activeWorkStreams = new Map<string, WorkStream>()
  const activeDialecticChannels = new Map<string, DialecticChannel>()
  const activeBlackboards = new Map<string, Blackboard>()

  return {
    cancel(sessionId: string): boolean {
      const cancelFn = activeSessions.get(sessionId)
      if (!cancelFn) return false
      cancelFn()
      return true
    },

    getActiveSessions(): string[] {
      return Array.from(activeSessions.keys())
    },

    getActiveBlackboard(sessionId: string): BlackboardState | undefined {
      return activeBlackboards.get(sessionId)?.getSnapshot()
    },

    getActiveProgress(sessionId: string) {
      const ws = activeWorkStreams.get(sessionId)
      const dc = activeDialecticChannels.get(sessionId)
      if (!ws) return undefined

      // Defensive, race-safe projection: WorkStream may be partially initialized
      // when callers request progress. Guard against undefined fields on work
      // units and role activity to avoid runtime crashes.
      const safeStats = (() => {
        try { return ws.getStats() } catch { return { workUnits: 0, workUnitsProcessed: 0, workUnitsPending: 0, workUnitsReviewed: 0, workUnitsUnreviewed: 0, refinements: 0, nudges: { low: 0, high: 0, acknowledged: 0 }, research: 0, guidance: 0 } }
      })()

      const roleActivity = (() => {
        try { return ws.getRoleActivity() } catch { return { yang: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] }, yin: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] }, apex: { iterationCount: 0, toolCallCount: 0, tokensUsed: 0, lastToolName: null, lastToolTimestamp: 0, concluded: false, errored: false, errorMessage: null, recentToolCalls: [] } } } })()

      const recentWUs = (() => {
        try { return ws.getAllWorkUnits().slice(-5) } catch { return [] as any[] }
      })()

      return {
        markdown: (() => { try { return ws.getRichProgress() } catch { return 'No progress available' } })(),
        data: {
          stats: safeStats,
          dialecticStats: dc?.getStats() ?? { findings: 0, challenges: 0, concessions: 0, investigationRequests: 0, executiveInjections: 0 },
          convergencePoints: dc?.buildConvergencePoints() ?? [],
          roleActivity,
          recentWorkUnits: recentWUs.map(wu => ({
            id: wu?.id,
            iteration: wu?.iteration ?? 0,
            reasoning: wu?.reasoning ? String(wu.reasoning).slice(0, 300) : undefined,
            filesModified: Array.isArray(wu?.filesModified) ? wu.filesModified : [],
            processed: !!wu?.processed,
          })),
          activeNudges: (() => { try { return ws.getAllNudges().filter(n => !n.acknowledged) } catch { return [] } })(),
          unityDone: (() => { try { return ws.isYangDone() } catch { return false } })(),
        },
      }
    },

    setModelPool(mp: ModelPool): void {
      storedModelPool = mp
    },

    setToolRegistry(registry: ToolRegistry): void {
      storedToolRegistry = registry
    },

    setToolExecutor(executor: ToolExecutor): void {
      storedToolExecutor = executor
    },

    setStore(store: DyadStore): void {
      storedStore = store
    },

    setModelDirective(directive: IModelDirective): void {
      storedModelDirective = directive
    },

    setContextDistiller(distiller: ContextDistiller): void {
      storedContextDistiller = distiller
    },

    setModuleRegistry(registry: ModuleSessionRegistry): void {
      storedModuleDebugSessionId = registry.getOrCreate('helix').id
    },

    async project(opts: HelixProjectOpts): Promise<HelixResult> {
      const sessionId = opts.sessionId || `helix-${Date.now()}`
      let registry: import('../flux-team/global-blackboard-registry.js').GlobalBlackboardRegistry | undefined
      let effectiveBlackboard = opts.blackboard
      const effectiveModelPool = storedModelPool || modelPool
      const effectiveEventBus = storedEventBus || eventBus

      if (!effectiveModelPool) {
        throw new Error('Helix requires a ModelPool')
      }
      if (!effectiveEventBus) {
        throw new Error('Helix requires an IEventBus')
      }

      if (!effectiveBlackboard && opts.blackboardId) {
        const { GlobalBlackboardRegistry } = await import('../flux-team/global-blackboard-registry.js')
        registry = new GlobalBlackboardRegistry(logger.child('global-blackboard-registry'))
        await registry.load(opts.blackboardId)
        effectiveBlackboard = registry.getOrCreate(opts.blackboardId, { persist: true })
        if (!effectiveBlackboard.getPlan()) effectiveBlackboard.initPlan(opts.goal)
        if (!effectiveBlackboard.getReport()) effectiveBlackboard.initReport(opts.goal)
      }

      try {
        // Phase Zero: Distill context from parent conversation + memory
        let effectiveGoal = opts.goal
        let effectiveContext = opts.context
        if (storedContextDistiller) {
          try {
            const distilled = await storedContextDistiller.distill({
              goal: opts.goal,
              context: opts.context,
              parentSessionId: opts.parentSessionId,
              sessionId,
              jobId: opts.jobId,
              spawnToolName: 'helix_project',
            })
            if (distilled.distilledContext) {
              effectiveContext = distilled.distilledContext
            }
            logger.info('helix:phase-zero:complete', {
              sessionId,
              contextTokenEstimate: distilled.contextTokenEstimate,
              durationMs: distilled.durationMs,
              sections: Object.keys(distilled.sections),
            })
          } catch (err) {
            logger.warn('helix:phase-zero:failed', { error: String(err), sessionId })
          }
        }

        // Consume any pre-seeded next-job directives
        storedModelDirective?.consumeNextJob(sessionId)

        const unityOverride = storedModelDirective?.resolve(opts.jobId, 'helix.unity')
        const yangOverride = storedModelDirective?.resolve(opts.jobId, 'helix.yang')
        const yinOverride = storedModelDirective?.resolve(opts.jobId, 'helix.yin')

        const [unityHandle, yangHandle, yinHandle] = await Promise.all([
          effectiveModelPool.acquire('unity', undefined, sessionId, unityOverride),
          effectiveModelPool.acquire('yang', undefined, sessionId, yangOverride),
          effectiveModelPool.acquire('yin', undefined, sessionId, yinOverride),
        ])

        const handleFactory = (config: { provider: string; model: string }) =>
          effectiveModelPool.acquire('helix', undefined, sessionId, { provider: config.provider, model: config.model })


        try {
          const result = await runHelixPipeline({
            goal: effectiveGoal,
            context: effectiveContext,
            timeoutMs: opts.timeoutMs,
            sessionId,
            jobId: opts.jobId,
            eventBus: effectiveEventBus,
            logger,
            unityHandle,
            yangHandle,
            yinHandle,
            toolExecutor: storedToolExecutor,
            toolRegistry: storedToolRegistry,
            store: storedStore,
            blackboard: effectiveBlackboard,
            onCancelRegistered: (cancelFn) => {
              activeSessions.set(sessionId, cancelFn)
            },
            onWorkStreamCreated: (ws) => {
              activeWorkStreams.set(sessionId, ws)
            },
            onDialecticChannelCreated: (dc) => {
              activeDialecticChannels.set(sessionId, dc)
            },
            onBlackboardCreated: (blackboard) => {
              activeBlackboards.set(sessionId, blackboard)
            },
            modelDirective: storedModelDirective,
            handleFactory,
            moduleDebugSessionId: storedModuleDebugSessionId,
            artifactNamespace: opts.artifactNamespace,
            sessionType: opts.sessionType ?? 'helix',
            teamId: opts.teamId,
          })

          lastRun = new Date()
          if (registry && opts.blackboardId) {
            await registry.save(opts.blackboardId)
          }
          return result
        } finally {
          activeSessions.delete(sessionId)
          activeWorkStreams.delete(sessionId)
          activeDialecticChannels.delete(sessionId)
          activeBlackboards.delete(sessionId)
          unityHandle.release()
          yangHandle.release()
          yinHandle.release()
        }
      } catch (err) {
        errorCount++
        throw err
      }
    },

    getHealth() {
      return {
        healthy: errorCount === 0,
        lastRun,
        errorCount,
      }
    },
  }
}


export type {
  HelixProjectOpts,
  HelixResult,
  HelixRole,
  HelixPosture,
  HelixPostureResult,
  HelixCompletionStatus,
} from './types.js'

export {
  UNITY_POSTURE,
  YANG_POSTURE,
  YIN_POSTURE,
  YANG_REVIEWER_POSTURE,
  YIN_REVIEWER_POSTURE,
  HELIX_POSTURES,
} from './helix-postures.js'

export {
  UNITY_TOOLS,
  REVIEWER_TOOLS,
  ALL_UNITY_TOOLS,
  ALL_YANG_TOOLS,
  ALL_YIN_TOOLS,
  isHelixMetaTool,
  getHelixToolSchemas,
} from './helix-tools.js'

export { HelixAgentSession } from './helix-agent-session.js'
export { runHelixPipeline } from './helix-pipeline.js'
export type { HelixPipelineOpts } from './helix-pipeline.js'

export const HELIX_MODEL_SLOTS = {
  UNITY: 'helix.unity',
  YANG: 'helix.yang',
  YIN: 'helix.yin',
} as const
