/**
 * Helix — Inverted-Pyramid Agent Pattern
 *
 * One worker (Unity) at the base, two concurrent reviewers (Yang + Yin) above,
 * and a Mentor overseeing the dialectic.
 *
 * Communication topology:
 *   Unity <-> Reviewers: WorkStream (work units, nudges)
 *   Yang  <-> Yin:       DialecticChannel (findings, challenges, concessions)
 *   Mentor -> All:       Steering injection, context, synthesis
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { IModelDirective } from '../../../types/model-routing.js'
import type { ContextDistiller } from '../context-distiller.js'
import type { ModelPool } from '../../model-pool/index.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { HelixProjectOpts, HelixResult } from './types.js'
import type { HelixStore } from './helix-store.js'
import type { BlackboardChannel, BlackboardEntry, BlackboardState } from '../../../types/flux-team.js'
import type { Blackboard, BlackboardSummary } from '../flux-team/blackboard.js'
import type { WorkStream } from '../dyad/work-stream.js'
import type { DialecticChannel } from '../lumen/dialectic-channel.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import type { ResearchSpawner } from './helix-posture-runner.js'
import { runHelixPipeline } from './helix-pipeline.js'
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
  // Show broadcast progress if using native coordinator, otherwise legacy counters
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


/**
 * Build a ResearchSpawner that uses ModelPool + ToolExecutor for lightweight
 * read-only research. Results are posted to the Blackboard via HelixResearcher.
 *
 * The spawner acquires a temporary model handle, runs a short agentic loop
 * with read-only tools, then posts findings to the blackboard and releases.
 */
async function buildResearchSpawner(deps: {
  modelPool: ModelPool
  toolExecutor: ToolExecutor
  toolRegistry?: ToolRegistry
  logger: ILogger
  blackboard: Blackboard
}): Promise<ResearchSpawner> {
  // Lazy-load to avoid circular deps
  const { HelixResearcher } = await import('./helix-researcher.js')
  const { READ_ONLY_TOOLS } = await import('../../tools/read-tools.js')

  return async (opts) => {
    const requestId = `research-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const droneId = `drone-${requestId}`
    const log = deps.logger.child('research-spawner')

    // Create researcher for blackboard integration
    const researcher = new HelixResearcher({
      sessionId: opts.sessionId,
      blackboard: deps.blackboard,
      query: opts.query,
      label: opts.label,
      requestedBy: 'yang', // Use 'yang' as proxy — HelixResearcher expects DyadRole-compatible
      priority: opts.priority ?? 'medium',
      context: opts.context,
      logger: log,
    })

    // Post the research request
    await researcher.postRequest()

    // Spawn the research drone asynchronously — fire-and-forget
    void (async () => {
      let handle: import('../../model-pool/types.js').ModelHandle | undefined
      try {
        // Acquire a handle for the research drone
        handle = await deps.modelPool.acquire('helix', undefined, opts.sessionId)

        // Build tool schemas — use registry if available, else defaults
        let tools = READ_ONLY_TOOLS
        if (deps.toolRegistry) {
          const registryTools = deps.toolRegistry.toAnthropicSchema()
            .filter((tool: { name: string }) => isReadOnlyName(tool.name))
          if (registryTools.length > 0) tools = registryTools
        }

        const systemPrompt = [
          'You are a focused research agent for a Helix session.',
          'Your job is to investigate the given query using your read-only tools.',
          'Thoroughly search relevant files, patterns, and code structures.',
          'Return a clear, structured summary of your findings.',
          'Focus on facts: file contents, function signatures, type definitions, import chains.',
          'Be thorough but concise. Return raw findings, not interpretations.',
        ].join('\n')

        const userPrompt = [
          `## Research Query\n\n${opts.query}`,
          opts.context ? `\n\n## Context\n\n${opts.context}` : '',
        ].filter(Boolean).join('')

        // Simple agentic loop using ModelHandle.stream()
        const messages: import('../../../types/runtime.js').Message[] = [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ]

        let finalText = ''
        const maxIterations = 6

        for (let iteration = 0; iteration < maxIterations; iteration++) {
          const contentBlocks: import('../../../types/runtime.js').ContentBlock[] = []
          const pendingToolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = []
          let passText = ''

          for await (const chunk of handle.stream(messages, {
            model: handle.model,
            maxTokens: 4096,
            temperature: 0.2,
            source: 'helix:research-drone',
            tools,
          })) {
            if (chunk.type === 'token' && chunk.text) {
              passText += chunk.text
            } else if (chunk.type === 'tool_use' && chunk.toolCall) {
              pendingToolCalls.push(chunk.toolCall)
            }
          }

          finalText += passText

          // No tool calls → we're done
          if (pendingToolCalls.length === 0) break

          // Build assistant message
          if (passText) contentBlocks.push({ type: 'text', text: passText })
          for (const tc of pendingToolCalls) {
            contentBlocks.push({ type: 'tool_use', id: tc.id, name: tc.name, input: tc.input })
          }
          messages.push({ role: 'assistant', content: contentBlocks })

          // Execute tool calls
          const toolResults: import('../../../types/runtime.js').ContentBlock[] = []
          for (const tc of pendingToolCalls) {
            try {
              const toolResult = await deps.toolExecutor.execute({
                id: tc.id,
                name: tc.name,
                input: tc.input,
              }, opts.sessionId)
              toolResults.push({
                type: 'tool_result',
                tool_use_id: tc.id,
                content: toolResult.content,
              })
            } catch (err) {
              toolResults.push({
                type: 'tool_result',
                tool_use_id: tc.id,
                content: `Error: ${String(err)}`,
                is_error: true,
              })
            }
          }
          messages.push({ role: 'user', content: toolResults })
        }

        // Post findings to the blackboard
        if (finalText) {
          await researcher.streamFinding(finalText)
        }
        await researcher.complete(finalText || 'Research completed with no textual findings.', {
          additionalSignals: [],
        })

        log.info('Research drone completed', { requestId, label: opts.label, textLength: finalText.length })
      } catch (err) {
        log.warn('Research drone failed', { requestId, error: String(err), label: opts.label })
        // Post error as a finding so the mentor knows
        try {
          await researcher.streamFinding(`Research failed: ${String(err)}`)
          await researcher.complete(`Research failed: ${String(err)}`)
        } catch { /* best effort */ }
      } finally {
        handle?.release()
      }
    })()

    return { requestId, droneId }
  }
}

/** Check if a tool name is read-only (safe for research drones) */
function isReadOnlyName(name: string): boolean {
  const readPrefixes = [
    'read', 'grep', 'glob', 'find_', 'get_symbols_overview', 'search_for_pattern',
    'list_dir', 'web_search', 'web_fetch', 'memory_search', 'memory_kv_get',
    'gitnexus_query', 'gitnexus_context', 'gitnexus_impact', 'gitnexus_cypher',
    'universal_search', 'archive_search',
  ]
  return readPrefixes.some(p => name.startsWith(p))
}


export interface HelixOrchestrator {
  project(opts: HelixProjectOpts): Promise<HelixResult>
  cancel(sessionId: string): boolean
  getActiveSessions(): string[]
  getActiveBlackboard(sessionId: string): BlackboardState | undefined
  getActiveBlackboardInstance(sessionId: string): Blackboard | undefined
  getActiveSummary(sessionId: string): BlackboardSummary | undefined
  getActiveChannel(sessionId: string, channel: BlackboardChannel, limit?: number): BlackboardEntry[] | undefined
  getActiveProgress(sessionId: string): { markdown: string; data: Record<string, unknown> } | undefined
  setModelPool(modelPool: ModelPool): void
  getActiveBrainstemInspection(sessionId: string): ReturnType<import('./brainstem.js').HelixBrainstem['getInspectionState']> | undefined
  getActiveBrainstemIds(): string[]
  setToolRegistry(registry: ToolRegistry): void
  setToolExecutor(executor: ToolExecutor): void
  setStore(store: HelixStore): void
  setModelDirective(directive: IModelDirective): void
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
  const activeSessions = new Map<string, () => void>()
  const activeWorkStreams = new Map<string, WorkStream>()
  const activeDialecticChannels = new Map<string, DialecticChannel>()
  const activeBlackboards = new Map<string, Blackboard>()
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

    getActiveBlackboard(sessionId: string): BlackboardState | undefined {
      return activeBlackboards.get(sessionId)?.getSnapshot()
    },

    getActiveBlackboardInstance(sessionId: string): Blackboard | undefined {
      return activeBlackboards.get(sessionId)
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
          // isWorkerDone() checks if the primary worker (Unity) signaled done
          unityDone: ws.isWorkerDone(),
          // Broadcast coordinator progress (native HelixWorkStream only)
          broadcastProgress: ws instanceof HelixWorkStream ? {
            yang: ws.getReviewerProgress('yang'),
            yin: ws.getReviewerProgress('yin'),
          } : undefined,
          // Consolidated metrics from HelixCoordinator
          metrics: coord?.getMetricsSnapshot(),
        },
      }
    },

    setModelPool(mp: ModelPool): void {
      storedModelPool = mp
    },

    /**
     * Get brainstem inspection state for a given Helix session.
     * Returns detailed queue depths, timing, recent annotations, and guidance.
     */
    getActiveBrainstemInspection(sessionId: string) {
      const bs = activeBrainstems.get(sessionId)
      if (!bs) return undefined
      return bs.getInspectionState()
    },

    /**
     * Get all active brainstem session IDs.
     */
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
        const mentorOverride = storedModelDirective?.resolve(opts.jobId, 'helix.mentor')

        const [unityHandle, yangHandle, yinHandle] = await Promise.all([
          effectiveModelPool.acquire('unity', undefined, sessionId, unityOverride),
          effectiveModelPool.acquire('yang', undefined, sessionId, yangOverride),
          effectiveModelPool.acquire('yin', undefined, sessionId, yinOverride),
        ])

        // Mentor handle is optional — only acquire if a model override is configured
        let mentorHandle: import('../../model-pool/types.js').ModelHandle | undefined
        if (mentorOverride) {
          try {
            mentorHandle = await effectiveModelPool.acquire('mentor', undefined, sessionId, mentorOverride)
          } catch (err) {
            logger.warn('helix:mentor:handle-acquisition-failed', { error: String(err), sessionId })
          }
        }

        // Create BrainstemDeps with a model-pool-based LLM adapter
        let brainstemDeps: import('./brainstem-types.js').BrainstemDeps | undefined
        if (effectiveModelPool) {
          try {
            const brainstemHandle = await effectiveModelPool.acquire('brainstem', undefined, sessionId)
            brainstemDeps = {
              llm: {
                async complete(opts: { prompt: string; modelTier: string; maxTokens: number; timeoutMs: number }) {
                  const messages = [{ role: 'user' as const, content: opts.prompt }]
                  const result = await brainstemHandle.complete(messages as any, {
                    maxTokens: opts.maxTokens,
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
              // Blackboard is resolved lazily via onBlackboardCreated callback below
            }
            logger.info('helix:brainstem:adapter-created', { sessionId })
          } catch (err) {
            logger.warn('helix:brainstem:handle-acquisition-failed', { error: String(err), sessionId })
          }
        }

        const handleFactory = (config: { provider: string; model: string }) =>
          effectiveModelPool.acquire('helix', undefined, sessionId, { provider: config.provider, model: config.model })

        // Create PlanHandler so Helix postures can decompose and track work
        let planHandler: import('../flux-team/plan-handler.js').PlanHandler | undefined
        try {
          const { PlanHandler } = await import('../flux-team/plan-handler.js')
          const { Blackboard } = await import('../flux-team/blackboard.js')
          // Use the provided blackboard, or create one eagerly so PlanHandler can bind to it.
          // The pipeline will use this same blackboard instance (passed via opts.blackboard).
          if (!effectiveBlackboard) {
            effectiveBlackboard = new Blackboard(logger, sessionId)
            effectiveBlackboard.initPlan(effectiveGoal)
            effectiveBlackboard.initReport(effectiveGoal)
          }
          planHandler = new PlanHandler(effectiveBlackboard, logger)
        } catch (err) {
          logger.warn('helix:plan-handler:init-failed', { error: String(err), sessionId })
        }

        // Build research spawner for mentor — deferred blackboard capture
        let resolvedBlackboard: Blackboard | undefined = effectiveBlackboard
        let researchSpawner: ResearchSpawner | undefined

        if (mentorHandle && storedToolExecutor) {
          // Create a lazy spawner that captures the blackboard when first invoked
          researchSpawner = async (spawnOpts) => {
            const bb = resolvedBlackboard ?? activeBlackboards.get(sessionId)
            if (!bb) throw new Error('No blackboard available for research spawner')
            const spawner = await buildResearchSpawner({
              modelPool: effectiveModelPool,
              toolExecutor: storedToolExecutor!,
              toolRegistry: storedToolRegistry,
              logger,
              blackboard: bb,
            })
            return spawner(spawnOpts)
          }
        }

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
            blackboard: effectiveBlackboard,
            planHandler,
            researchSpawner,
            useNativeCoordinator: true,
            brainstemDeps,
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
              resolvedBlackboard = blackboard
              // Wire blackboard into brainstemDeps (created before pipeline runs)
              if (brainstemDeps) {
                brainstemDeps.blackboard = blackboard
              }
            },
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
          if (registry && opts.blackboardId) {
            await registry.save(opts.blackboardId)
          }

          // ── Per-job git commit: attribute all file writes to this session ──
          if (storedToolExecutor) {
            try {
              const commitResult = await storedToolExecutor.commitSession({
                sessionId,
                sessionType: 'helix',
                goal: opts.goal,
                success: result.completionStatus.unityStatus === 'completed',
                durationMs: result.durationMs,
                toolCalls: result.toolCallCounts?.unity,
              })
              if (commitResult.committed) {
                logger.info('helix:session-committed', {
                  sessionId,
                  sha: commitResult.sha,
                  fileCount: commitResult.fileCount,
                })
              }
            } catch (commitErr) {
              logger.debug('helix:session-commit-failed', { sessionId, error: String(commitErr) })
            }
          }

          return result
        } finally {
          activeSessions.delete(sessionId)
          activeWorkStreams.delete(sessionId)
          activeDialecticChannels.delete(sessionId)
          activeBlackboards.delete(sessionId)
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

export type { ResearchSpawner } from './helix-posture-runner.js'

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
} from './helix-tools.js'

export { HelixPostureRunner } from './helix-posture-runner.js'
/** @deprecated Use HelixPostureRunner — postures are not agents, they are behavioral modes */
export { HelixPostureRunner as HelixAgentSession } from './helix-posture-runner.js'
export { runHelixPipeline } from './helix-pipeline.js'
export type { HelixPipelineOpts } from './helix-pipeline.js'

export const HELIX_MODEL_SLOTS = {
  UNITY: 'helix.unity',
  YANG: 'helix.yang',
  YIN: 'helix.yin',
  MENTOR: 'helix.mentor',
} as const

// ── Brainstem Mini-Helix ───────────────────────────────────────────────────

export { BrainstemMiniHelix } from './brainstem-mini-helix.js'
export type { BrainstemMiniHelixConfig } from './brainstem-mini-helix.js'

export { createBrainstemTools, buildBrainstemSystemPrompt } from './brainstem-tools.js'
export type { BrainstemToolContext } from './brainstem-tools.js'
