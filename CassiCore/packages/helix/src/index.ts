/**
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
import type { BlackboardChannel, BlackboardEntry, BlackboardState } from '../../../types/flux-team.js'
import type { Blackboard, BlackboardSummary } from '../flux-team/blackboard.js'
import type { WorkStream } from '../dyad/work-stream.js'
import type { DialecticChannel } from '../lumen/dialectic-channel.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import { runHelixPipeline } from './helix-pipeline.js'

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
  lines.push(`- Work units reviewed: ${stats.workUnitsReviewed}/${stats.workUnits}`)
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


export interface HelixOrchestrator {
  project(opts: HelixProjectOpts): Promise<HelixResult>
  cancel(sessionId: string): boolean
  getActiveSessions(): string[]
  getActiveBlackboard(sessionId: string): BlackboardState | undefined
  getActiveSummary(sessionId: string): BlackboardSummary | undefined
  getActiveChannel(sessionId: string, channel: BlackboardChannel, limit?: number): BlackboardEntry[] | undefined
  getActiveProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  setModelPool(modelPool: ModelPool): void
  setToolRegistry(registry: ToolRegistry): void
  setToolExecutor(executor: ToolExecutor): void
  setStore(store: DyadStore): void
  setModelDirective(directive: IModelDirective): void
  setContextDistiller(distiller: ContextDistiller): void
  setModuleRegistry(registry: ModuleSessionRegistry): void
  getHealth(): { healthy: boolean; lastRun?: Date; errorCount: number; activeSessionCount: number; modelPoolAvailable: boolean }
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

    getActiveSummary(sessionId: string): BlackboardSummary | undefined {
      return activeBlackboards.get(sessionId)?.getSummary()
    },

    getActiveChannel(sessionId: string, channel: BlackboardChannel, limit?: number): BlackboardEntry[] | undefined {
      return activeBlackboards.get(sessionId)?.getChannelEntries(channel, limit)
    },

    getActiveProgress(sessionId: string) {
      const ws = activeWorkStreams.get(sessionId)
      const dc = activeDialecticChannels.get(sessionId)
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
          // Note: isYangDone() checks if the primary worker (Unity) signaled done — method name is legacy from Dyad
          unityDone: ws.isYangDone(),
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
