/**
 * Helix — Inverted-Pyramid Agent Pattern
 *
 * One worker (Unity) at the base, two concurrent reviewers (Yang + Yin) above,
 * and a Brainstem serving as cognitive organizer.
 *
 * Communication topology:
 *   Unity <-> Reviewers: WorkStream (work units, nudges)
 *   Yang  <-> Yin:       DialecticChannel (findings, challenges, concessions)
 *   Brainstem -> Unity:  Guidance injection, annotations, pattern detection
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { IModelDirective } from '../../../types/model-routing.js'
import type { ContextDistiller } from '../context-distiller.js'
import type { ModelPool } from '../../model-pool/index.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { HelixProjectOpts, HelixResult } from './types.js'
import type { HelixStore, TestLockRow } from './helix-store.js'
// REMOVED: Blackboard imports — deprecated. Now uses LaminaField + GlobalWorkspace
// import type { BlackboardChannel, BlackboardEntry, BlackboardState } from '../../../types/flux-team.js'
// import type { Blackboard, BlackboardSummary } from '../flux-team/blackboard.js'
import type { WorkStream } from './work-stream.js'
import type { DialecticChannel } from './dialectic-channel.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import type { HelixSynapseLLM } from './helix-synapse.js'
import { runHelixPipeline, SessionState } from './helix-pipeline.js'
import { HelixWorkStream, HelixCoordinator } from './helix-coordinator.js'

function buildHelixProgressMarkdown(ws: WorkStream, dc?: DialecticChannel): string {
  const stats = ws.getStats()
  const roleActivity = ws.getRoleActivity()
  const unity = roleActivity.unity
  const yang = roleActivity.yang
  const yin = roleActivity.yin

  const formatRoleStatus = (role: typeof unity) => {
    if (role.concluded) return role.errored ? `ERRORED: ${role.errorMessage}` : 'COMPLETED'
    return `ACTIVE (iteration ${role.iterationCount})`
  }

  const formatRecentTools = (calls: Array<{ name: string; isError: boolean }>) => {
    if (calls.length === 0) return undefined
    return calls.slice(-5).map(call => `\`${call.name}\`${call.isError ? ' [ERROR]' : ''}`).join(' -> ')
  }

  const lines: string[] = ['## Pipeline Status', '']

  lines.push(`### Unity (Worker): ${formatRoleStatus(unity)}`)
  lines.push(`- Iterations: ${unity.iterationCount} | Tool calls: ${unity.toolCallCount} | Tokens: ${unity.tokensUsed}`)
  if (unity.lastToolName) {
    const ago = Math.round((Date.now() - unity.lastToolTimestamp) / 1000)
    lines.push(`- Last tool: \`${unity.lastToolName}\` (${ago}s ago)`)
  }
  const unityRecent = formatRecentTools(unity.recentToolCalls)
  if (unityRecent) lines.push(`- Recent tools: ${unityRecent}`)
  lines.push(`- Work units produced: ${stats.workUnits}`)
  lines.push('')

  lines.push(`### Yang (Reviewer): ${formatRoleStatus(yang)}`)
  lines.push(`- Iterations: ${yang.iterationCount} | Tool calls: ${yang.toolCallCount} | Tokens: ${yang.tokensUsed}`)
  if (yang.lastToolName) {
    const ago = Math.round((Date.now() - yang.lastToolTimestamp) / 1000)
    lines.push(`- Last tool: \`${yang.lastToolName}\` (${ago}s ago)`)
  }
  const yangRecent = formatRecentTools(yang.recentToolCalls)
  if (yangRecent) lines.push(`- Recent tools: ${yangRecent}`)
  lines.push('')

  lines.push(`### Yin (Reviewer): ${formatRoleStatus(yin)}`)
  lines.push(`- Iterations: ${yin.iterationCount} | Tool calls: ${yin.toolCallCount} | Tokens: ${yin.tokensUsed}`)
  if (yin.lastToolName) {
    const ago = Math.round((Date.now() - yin.lastToolTimestamp) / 1000)
    lines.push(`- Last tool: \`${yin.lastToolName}\` (${ago}s ago)`)
  }
  const yinRecent = formatRecentTools(yin.recentToolCalls)
  if (yinRecent) lines.push(`- Recent tools: ${yinRecent}`)
  // Native HelixWorkStream uses broadcast coordination; legacy uses sequential review
  if (ws instanceof HelixWorkStream) {
    const yangProgress = ws.getReviewerProgress('yang')
    const yinProgress = ws.getReviewerProgress('yin')
    lines.push(`- Broadcast: Yang ${yangProgress.cursor}/${yangProgress.total} WUs | Yin ${yinProgress.cursor}/${yinProgress.total} WUs`)
  } else {
    lines.push(`- Work units reviewed: ${stats.workUnitsReviewed}/${stats.workUnits}`)
  }
  lines.push('')

  lines.push('### Work Stream')
  lines.push(`- Work units: ${stats.workUnits} total, ${stats.workUnitsReviewed} reviewed, ${stats.workUnitsUnreviewed} unreviewed`)
  lines.push(`- Nudges: ${stats.nudges.low} low, ${stats.nudges.high} high (${stats.nudges.acknowledged} acknowledged)`)
  lines.push(`- Refinements: ${stats.refinements}`)
  lines.push(`- Research injected: ${stats.research} | Guidance: ${stats.guidance}`)
  lines.push('')

  const recentWUs = ws.getAllWorkUnits().slice(-3)
  if (recentWUs.length > 0) {
    lines.push('### Recent Work Units')
    for (const wu of recentWUs) {
      lines.push(`- **${wu.id}** (iter ${wu.iteration ?? 0}): ${wu.reasoning?.slice(0, 150) ?? 'no reasoning'}`)
    }
    lines.push('')
  }

  const activeNudges = ws.getAllNudges().filter(n => !n.acknowledged)
  if (activeNudges.length > 0) {
    lines.push('### Active Nudges (unacknowledged)')
    for (const nudge of activeNudges.slice(-5)) {
      lines.push(`- [${nudge.severity}] ${nudge.content}`)
    }
    lines.push('')
  }

  const dialecticStats = dc?.getStats()
  if (dialecticStats) {
    lines.push('### Reviewer Dialectic')
    lines.push(`- Findings: ${dialecticStats.findings} | Challenges: ${dialecticStats.challenges} | Concessions: ${dialecticStats.concessions}`)
    lines.push(`- Investigation requests: ${dialecticStats.investigationRequests} | Executive injections: ${dialecticStats.executiveInjections}`)
  }

  return lines.join('\n')
}


function isReadOnlyName(name: string): boolean {
  const readPrefixes = [
    'read', 'grep', 'glob', 'find_', 'get_symbols_overview', 'search_for_pattern',
    'list_dir', 'web_search', 'web_fetch', 'memory_kv_get',
    'gitnexus_query', 'gitnexus_context', 'gitnexus_impact', 'gitnexus_cypher',
    'universal_search', 'archive_search',
  ]
  return readPrefixes.some(p => name.startsWith(p))
}


export interface HelixOrchestrator {
  project(opts: HelixProjectOpts): Promise<HelixResult>
  cancel(sessionId: string): boolean
  getActiveSessions(): string[]
  /** REMOVED: getActiveBlackboard — Blackboard deprecated. Use getActiveProgress or getActiveBrainstemInspection */
  getActiveProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  setModelPool(modelPool: ModelPool): void
  getActiveBrainstemInspection(sessionId: string): ReturnType<import('./brainstem.js').HelixBrainstem['getInspectionState']> | undefined
  getActiveBrainstemIds(): string[]
  setToolRegistry(registry: ToolRegistry): void
  setToolExecutor(executor: ToolExecutor): void
  setStore(store: HelixStore): void
  setModelDirective(directive: IModelDirective): void
  setThalamus(thalamus: import('../thalamus/index.js').ThalamusModule): void
  setContextDistiller(distiller: ContextDistiller): void
  setModuleRegistry(registry: ModuleSessionRegistry): void
  getHealth(): { healthy: boolean; lastRun?: Date; errorCount: number; activeSessionCount: number; modelPoolAvailable: boolean }
}


/**
 * @dep callers: createIntelligence (core/intelligence/index.ts), helix-wiring.test.ts (tests/helix-wiring.test.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

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
  let storedStore: HelixStore | undefined
  let storedModelDirective: IModelDirective | undefined
  let storedContextDistiller: ContextDistiller | undefined
  let storedModuleDebugSessionId: string | undefined
  let storedThalamus: import('../thalamus/index.js').ThalamusModule | undefined
  const activeSessions = new Map<string, () => void>()
  const activeWorkStreams = new Map<string, WorkStream>()
  const activeDialecticChannels = new Map<string, DialecticChannel>()
  // REMOVED: activeBlackboards — Blackboard deprecated. Now uses LaminaField + GlobalWorkspace
  const activeCoordinators = new Map<string, HelixCoordinator>()
  const activeBrainstems = new Map<string, import('./brainstem.js').HelixBrainstem>()

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

    getActiveProgress(sessionId: string) {
      const ws = activeWorkStreams.get(sessionId)
      const dc = activeDialecticChannels.get(sessionId)
      const coord = activeCoordinators.get(sessionId)
      if (!ws) return undefined
      return {
        markdown: buildHelixProgressMarkdown(ws, dc),
        data: {
          stats: ws.getStats(),
          dialecticStats: dc?.getStats() ?? { findings: 0, challenges: 0, concessions: 0, investigationRequests: 0, executiveInjections: 0 },
          convergencePoints: dc?.buildConvergencePoints() ?? [],
          roleActivity: ws.getRoleActivity(),
          recentWorkUnits: ws.getAllWorkUnits().slice(-5).map(wu => ({
            id: wu.id,
            iteration: wu.iteration ?? 0,
            reasoning: wu.reasoning?.slice(0, 300) ?? '',
            filesModified: wu.filesModified ?? [],
            processed: wu.processed,
          })),
          activeNudges: ws.getAllNudges().filter(n => !n.acknowledged),
          unityDone: ws.isWorkerDone(),
          broadcastProgress: ws instanceof HelixWorkStream ? {
            yang: ws.getReviewerProgress('yang'),
            yin: ws.getReviewerProgress('yin'),
          } : undefined,
          metrics: coord?.getMetricsSnapshot(),
        },
      }
    },

    setModelPool(mp: ModelPool): void {
      storedModelPool = mp
    },

    getActiveBrainstemInspection(sessionId: string) {
      const bs = activeBrainstems.get(sessionId)
      if (!bs) return undefined
      return bs.getInspectionState()
    },

    getActiveBrainstemIds(): string[] {
      return Array.from(activeBrainstems.keys())
    },

    setToolRegistry(registry: ToolRegistry): void {
      storedToolRegistry = registry
    },

    setToolExecutor(executor: ToolExecutor): void {
      storedToolExecutor = executor
    },

    setStore(store: HelixStore): void {
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

    setThalamus(thalamus: import('../thalamus/index.js').ThalamusModule): void {
      storedThalamus = thalamus
    },

    async project(opts: HelixProjectOpts): Promise<HelixResult> {
      const sessionId = opts.sessionId || `helix-${Date.now()}`
      // REMOVED: GlobalBlackboardRegistry — Blackboard deprecated
      let effectiveSessionState = opts.blackboard ?? new SessionState()
      if (!opts.blackboard) {
        effectiveSessionState.initPlan(opts.goal)
        effectiveSessionState.initReport(opts.goal)
      }
      const effectiveModelPool = storedModelPool || modelPool
      const effectiveEventBus = storedEventBus || eventBus

      if (!effectiveModelPool) {
        throw new Error('Helix requires a ModelPool')
      }
      if (!effectiveEventBus) {
        throw new Error('Helix requires an IEventBus')
      }

      try {
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

        storedModelDirective?.consumeNextJob(sessionId)

        const postureMo = opts.modelOverride
        const unityOverride = postureMo ?? storedModelDirective?.resolve(opts.jobId, 'helix.unity')
        const yangOverride = postureMo ?? storedModelDirective?.resolve(opts.jobId, 'helix.yang')
        const yinOverride = postureMo ?? storedModelDirective?.resolve(opts.jobId, 'helix.yin')

        const [unityHandle, yangHandle, yinHandle] = await Promise.all([
          effectiveModelPool.acquire('unity', undefined, sessionId, unityOverride),
          effectiveModelPool.acquire('yang', undefined, sessionId, yangOverride),
          effectiveModelPool.acquire('yin', undefined, sessionId, yinOverride),
        ])

        const mentorHandle: undefined = undefined

        let brainstemDeps: import('./brainstem-types.js').BrainstemDeps | undefined
        let synapseDeps: { llm: HelixSynapseLLM } | undefined
        if (effectiveModelPool) {
          try {
            const brainstemHandle = await effectiveModelPool.acquire('brainstem', undefined, sessionId)
            const synapseHandle = await effectiveModelPool.acquire('synapse', undefined, sessionId)
            brainstemDeps = {
              llm: {
                async complete(opts: { prompt: string; modelTier: string; maxTokens: number; timeoutMs: number }) {
                  const messages = [{ role: 'user' as const, content: opts.prompt }]
                  const result = await brainstemHandle.complete(messages as any, {
                    maxTokens: opts.maxTokens,
                    thinking: 'none',
                  } as any)
                  return { content: result.response, truncated: false }
                },
              },
              logger: logger.child?.('brainstem') ?? logger,
              goal: effectiveGoal,
              sessionId,
              eventBus: effectiveEventBus,
              readFile: async (path: string) => {
                try {
                  const { readFile: fsRead } = await import('node:fs/promises')
                  const { resolve } = await import('node:path')
                  const resolved = resolve(process.cwd(), path)
                  if (!resolved.startsWith(process.cwd())) return null
                  return await fsRead(resolved, 'utf-8')
                } catch { return null }
              },
            }
            synapseDeps = {
              llm: {
                async complete(opts: { prompt: string; modelTier: string; maxTokens: number; timeoutMs: number }) {
                  const messages = [{ role: 'user' as const, content: opts.prompt }]
                  const result = await synapseHandle.complete(messages as any, {
                    maxTokens: opts.maxTokens,
                    thinking: 'none',
                  } as any)
                  return { content: result.response, truncated: false }
                },
              },
            }
            logger.info('helix:brainstem:adapter-created', { sessionId })
          } catch (err) {
            logger.warn('helix:brainstem:handle-acquisition-failed', { error: String(err), sessionId })
          }
        }

        const handleFactory = (config: { provider: string; model: string }) =>
          effectiveModelPool.acquire('helix', undefined, sessionId, { provider: config.provider, model: config.model })

        // REMOVED: PlanHandler — Blackboard deprecated. Plan state managed via LaminaField
        let planHandler: undefined

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
            mentorHandle,
            toolExecutor: storedToolExecutor,
            toolRegistry: storedToolRegistry,
            store: storedStore,
            // REMOVED: blackboard — deprecated
            planHandler: undefined,
            useNativeCoordinator: true,
            brainstemDeps,
            synapseDeps,
            thalamus: storedThalamus,
            onCancelRegistered: (cancelFn) => {
              activeSessions.set(sessionId, cancelFn)
            },
            onWorkStreamCreated: (ws) => {
              activeWorkStreams.set(sessionId, ws)
            },
            onDialecticChannelCreated: (dc) => {
              activeDialecticChannels.set(sessionId, dc)
            },
            // REMOVED: onBlackboardCreated — Blackboard deprecated
            onCoordinatorCreated: (coord) => {
              activeCoordinators.set(sessionId, coord)
            },
            onBrainstemCreated: (bs) => {
              activeBrainstems.set(sessionId, bs)
            },
            onWorkUnit: (wu, iteration) => {
              const bs = activeBrainstems.get(sessionId)
              bs?.onWorkUnit(wu, iteration)
            },
            modelDirective: storedModelDirective,
            handleFactory,
            moduleDebugSessionId: storedModuleDebugSessionId,
            artifactNamespace: opts.artifactNamespace,
            sessionType: opts.sessionType ?? 'helix',
            teamId: opts.teamId,
            unityStatusThresholds: opts.unityStatusThresholds,
          })

          lastRun = new Date()
          // REMOVED: registry.save — Blackboard deprecated

          return result
        } finally {
          activeSessions.delete(sessionId)
          activeWorkStreams.delete(sessionId)
          activeDialecticChannels.delete(sessionId)
          // REMOVED: activeBlackboards.delete — Blackboard deprecated
          activeCoordinators.delete(sessionId)
          activeBrainstems.delete(sessionId)
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
        healthy: errorCount < 5 && !!storedModelPool,
        lastRun,
        errorCount,
        activeSessionCount: activeSessions.size,
        modelPoolAvailable: !!storedModelPool,
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
  ALL_UNITY_TOOLS,
  ALL_YANG_TOOLS,
  ALL_YIN_TOOLS,
  ALL_MENTOR_TOOLS,
  isHelixMetaTool,
  getHelixToolSchemas,
  TESTLOCK_TOOL_NAMES,
  YIN_TESTLOCK_TOOLS,
  UNITY_TESTLOCK_TOOLS,
  YANG_TESTLOCK_TOOLS,
} from './helix-tools.js'

export { HelixPostureRunner } from './helix-posture-runner.js'
/** @deprecated Use HelixPostureRunner — postures are not agents, they are behavioral modes */
export { HelixPostureRunner as HelixAgentSession } from './helix-posture-runner.js'
export { runHelixPipeline } from './helix-pipeline.js'
export type { HelixPipelineOpts } from './helix-pipeline.js'

export { TestLock } from './testlock.js'
export type { SealedTestSpec, TestLockVerification, TestLockSeverity, TestLockVerificationStatus, TestLockPersistence } from './testlock.js'

export const HELIX_MODEL_SLOTS = {
  UNITY: 'helix.unity',
  YANG: 'helix.yang',
  YIN: 'helix.yin',
  MENTOR: 'helix.mentor',
} as const


export { BrainstemMiniHelix } from './brainstem-mini-helix.js'
export type { BrainstemMiniHelixConfig } from './brainstem-mini-helix.js'

export { createBrainstemTools, buildBrainstemSystemPrompt } from './brainstem-tools.js'
export type { BrainstemToolContext } from './brainstem-tools.js'
