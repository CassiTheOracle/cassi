/**
 * Constellation Pipeline — Main runner that orchestrates a tree of Helix sessions.
 *
 * A Constellation is a tree of Helix sessions coordinated by a Corpus.
 * The Corpus maintains a shared reasoning tree where each Helix's Brainstem
 * pushes annotations. The Corpus detects cross-Helix patterns and sends
 * directives back through child Brainstems.
 *
 * Cassi (the main session) sits on top and can read the tree for strategic awareness.
 *
 * Named after multiple Helix "stars" forming dynamic patterns — extending
 * the stellar metaphor (Helix = double helix of binary stars).
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ModelHandle } from '../../model-pool/types.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { HelixStore } from '../helix/helix-store.js'
import type { HelixResult } from '../helix/types.js'
import type { ConstellationStore, ProgressSnapshot } from './constellation-store.js'
import type { BrainstemDeps } from '../helix/brainstem-types.js'
import type { HelixBrainstem } from '../helix/brainstem.js'
import { runHelixPipeline } from '../helix/helix-pipeline.js'
import { createHelixBrainstem } from '../helix/brainstem.js'
import { Blackboard } from '../flux-team/blackboard.js'
import { BlackboardBridge } from './blackboard-bridge.js'
import { Corpus } from './corpus.js'
import { CorpusTree } from './corpus-tree.js'
import type { CorpusLLM } from './corpus-types.js'
import type {
  FlexPosture,
  ConstellationTemplate,
  ConstellationNode,
  ConstellationNodeStatus,
  ConstellationResult,
  SpawnRequest,
} from './types.js'
import type { ConstellationLiveState } from './constellation-injection.js'
import { getTemplatePostures } from './templates.js'

// ═══════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════

const DEFAULT_MAX_HELIXES = 16
const DEFAULT_MAX_DEPTH = 4
const SPAWN_CHECK_INTERVAL_MS = 1000

// ═══════════════════════════════════════════════════════════════════
// Pipeline Options
// ═══════════════════════════════════════════════════════════════════

export interface ConstellationPipelineOpts {
  /** The main goal for this Constellation */
  goal: string

  /** Additional context or constraints */
  context?: string

  /** Unique identifier for this Constellation */
  constellationId: string

  /** Template to use for posture configuration */
  template?: ConstellationTemplate

  /** Custom postures (overrides template if provided) */
  postures?: FlexPosture[]

  /** Maximum number of Helixes in the tree */
  maxHelixes?: number

  /** Maximum depth of the tree */
  maxDepth?: number

  /** Overall timeout for the Constellation */
  timeoutMs?: number

  /** Logger instance */
  logger: ILogger

  /** Optional event bus for emitting events */
  eventBus?: IEventBus

  /** Tool executor for Helix sessions */
  toolExecutor?: ToolExecutor

  /** Tool registry for Helix sessions */
  toolRegistry?: ToolRegistry

  /** Helix store for session persistence */
  store?: HelixStore

  /** Constellation store for archiving completed sessions */
  constellationStore?: ConstellationStore

  /**
   * Factory function to acquire model handles.
   * Same pattern as helix/index.ts
   */
  handleFactory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<ModelHandle>

  /** Corpus LLM adapter for cross-Helix analysis */
  corpusLLM: CorpusLLM

  /** Callback when a node is created */
  onNodeCreated?: (node: ConstellationNode) => void

  /** Callback when a node completes */
  onNodeCompleted?: (node: ConstellationNode) => void

  /**
   * Callback fired after the Corpus starts, before the first Helix launches.
   * Receives a ConstellationLiveState adapter that exposes tree/patterns/interventions
   * for the injection source and admin API polling.
   */
  onCorpusReady?: (liveState: ConstellationLiveState) => void

  /**
   * Callback to receive a cancel function. The orchestrator calls the returned
   * function to cancel the constellation from outside.
   */
  onCancelRegistered?: (cancel: () => void) => void
}

// ═══════════════════════════════════════════════════════════════════
// Internal State
// ═══════════════════════════════════════════════════════════════════

interface RunningHelix {
  helixId: string
  node: ConstellationNode
  promise: Promise<HelixResult>
  cancel: () => void
  handles: ModelHandle[]
  brainstem?: HelixBrainstem
  parentId?: string
  depth: number
}

// ═══════════════════════════════════════════════════════════════════
// Main Pipeline Function
// ═══════════════════════════════════════════════════════════════════

export async function runConstellationPipeline(
  opts: ConstellationPipelineOpts
): Promise<ConstellationResult> {
  const startTime = Date.now()
  const {
    goal,
    context,
    constellationId,
    template = 'standard',
    postures: customPostures,
    maxHelixes = DEFAULT_MAX_HELIXES,
    maxDepth = DEFAULT_MAX_DEPTH,
    logger,
    eventBus,
    toolExecutor,
    toolRegistry,
    store,
    constellationStore,
    handleFactory,
    corpusLLM,
    onNodeCreated,
    onNodeCompleted,
  } = opts

  const log = logger.child('constellation-pipeline')
  log.info('Constellation pipeline starting', {
    constellationId,
    goal: goal.slice(0, 200),
    template,
    maxHelixes,
    maxDepth,
  })

  // Emit start event
  eventBus?.emit({
    type: 'team:event' as any,
    teamId: constellationId,
    data: { event: 'constellation:started', goal, timestamp: Date.now() },
  } as any)

  // ═════════════════════════════════════════════════════════════════
  // Create session in ConstellationStore (if provided)
  // ═════════════════════════════════════════════════════════════════

  if (constellationStore) {
    try {
      constellationStore.createSession(constellationId, goal, {
        context,
        template,
        maxHelixes,
        maxDepth,
      })
      log.debug('Created ConstellationStore session', { constellationId })
    } catch (err) {
      log.warn('Failed to create ConstellationStore session', { error: String(err) })
    }
  }

  // ═════════════════════════════════════════════════════════════════
  // Create Corpus Tree, Blackboard, and Corpus
  // ═════════════════════════════════════════════════════════════════

  const corpusTree = new CorpusTree(logger)

  // Create constellation-level blackboard for cross-Helix communication
  const constellationBlackboard = new Blackboard(log, constellationId)
  constellationBlackboard.initPlan(goal)
  constellationBlackboard.initReport(goal)

  const corpus = new Corpus(
    corpusTree,
    {
      llm: corpusLLM,
      logger,
      goal,
      constellationId,
      eventBus,
      blackboard: constellationBlackboard,
      onSpawnRequest: (req) => {
        const spawnRequest: SpawnRequest = {
          requestId: `spawn-corpus-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          requestingHelixId: req.requestingHelixId,
          requestingPosture: 'corpus',
          targetDepth: (runningHelixes.get(req.requestingHelixId)?.depth ?? 0) + 1,
          goal: req.goal,
          context: req.context,
          template: (req.template as ConstellationTemplate) ?? template,
          status: 'pending',
          timestamp: Date.now(),
        }
        spawnQueue.push(spawnRequest)
        log.info('Spawn request queued from Corpus', {
          requestId: spawnRequest.requestId,
          requestingHelixId: req.requestingHelixId,
          goal: req.goal.slice(0, 100),
        })
      },
    },
    {
      maxBranches: maxHelixes,
      maxDepth,
    }
  )

  // Start Corpus
  await corpus.start()
  log.info('Corpus started')

  // ═════════════════════════════════════════════════════════════════
  // Notify orchestrator — corpus is live, tree state is available
  // ═════════════════════════════════════════════════════════════════

  if (opts.onCorpusReady) {
    const liveState: ConstellationLiveState = {
      constellationId,
      goal,
      getTreeSnapshot: () => corpusTree.getSnapshot(),
      getCrossPatterns: () => corpus.getResult().crossPatterns,
      getInterventions: () => corpus.getResult().interventions,
      getBranchAssessments: () => corpus.getResult().branchAssessments,
    }
    opts.onCorpusReady(liveState)
    log.debug('onCorpusReady callback invoked')
  }

  // ═════════════════════════════════════════════════════════════════
  // State Tracking
  // ═════════════════════════════════════════════════════════════════

  const nodes = new Map<string, ConstellationNode>()
  const runningHelixes = new Map<string, RunningHelix>()
  const spawnQueue: SpawnRequest[] = []
  const blackboardBridges = new Map<string, BlackboardBridge>()
  let rootHelixId: string | undefined
  let completed = false

  // ═════════════════════════════════════════════════════════════════
  // Helper: Resolve Postures
  // ═════════════════════════════════════════════════════════════════

  function resolvePostures(): FlexPosture[] {
    if (customPostures && customPostures.length > 0) {
      log.info('Using custom postures', { count: customPostures.length })
      return customPostures
    }
    log.info('Using template postures', { template })
    return getTemplatePostures(template)
  }

  // ═════════════════════════════════════════════════════════════════
  // Helper: Launch Helix
  // ═════════════════════════════════════════════════════════════════

  async function launchHelix(
    helixGoal: string,
    helixContext: string | undefined,
    parentId: string | undefined,
    depth: number
  ): Promise<RunningHelix> {
    const helixId = `helix-${constellationId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const helixLog = log.child(helixId)

    helixLog.info('Launching Helix', {
      parentId,
      depth,
      goal: helixGoal.slice(0, 100),
    })

    // Register branch in corpus tree
    corpusTree.registerBranch(helixId, helixGoal, depth, parentId)

    // Create node
    const node: ConstellationNode = {
      helixId,
      config: {
        goal: helixGoal,
        context: helixContext,
        parentId,
        depth,
      },
      parentId,
      childIds: [],
      depth,
      status: 'running',
      startedAt: Date.now(),
      tokensUsed: 0,
      postureResults: new Map(),
    }
    nodes.set(helixId, node)
    onNodeCreated?.(node)

    // Acquire model handles
    const postures = resolvePostures()
    const handles: ModelHandle[] = []

    try {
      // Acquire handles for each posture that needs one
      // Unity, Yang, Yin always need handles
      // Additional postures may need handles based on their configuration
      const unityHandle = await handleFactory({
        tier: 'performance',
        purpose: 'unity',
        sessionId: helixId,
      })
      handles.push(unityHandle)

      const yangHandle = await handleFactory({
        tier: 'balanced',
        purpose: 'yang',
        sessionId: helixId,
      })
      handles.push(yangHandle)

      const yinHandle = await handleFactory({
        tier: 'balanced',
        purpose: 'yin',
        sessionId: helixId,
      })
      handles.push(yinHandle)

      // TODO: Acquire handles for additional postures based on template
      // For now, we use the three main handles for all postures
    } catch (err) {
      helixLog.error('Failed to acquire model handles', { error: String(err) })
      node.status = 'failed'
      corpusTree.closeBranch(helixId, 'failed')
      onNodeCompleted?.(node)
      throw err
    }

    // Create Brainstem with corpus tree integration
    const brainstemDeps: BrainstemDeps = {
      llm: corpusLLM,
      logger,
      goal: helixGoal,
      sessionId: helixId,
      eventBus,
      corpusTree,
      helixId,
      onSpawnRequest: (req) => {
        const spawnRequest: SpawnRequest = {
          requestId: `spawn-${helixId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          requestingHelixId: helixId,
          requestingPosture: 'brainstem',
          targetDepth: depth + 1,
          goal: req.goal,
          context: req.context,
          template: (req.template as ConstellationTemplate) ?? template,
          status: 'pending',
          timestamp: Date.now(),
        }
        spawnQueue.push(spawnRequest)
        log.info('Spawn request queued from Brainstem', {
          requestId: spawnRequest.requestId,
          helixId,
          goal: req.goal.slice(0, 100),
        })
      },
    }

    const brainstem = createHelixBrainstem(brainstemDeps)
    corpus.registerBrainstem(helixId, brainstem)

    // Create cancellation mechanism
    let cancelFn: (() => void) | undefined
    const cancelPromise = new Promise<never>((_, reject) => {
      cancelFn = () => reject(new Error('Helix cancelled'))
    })

    // Run the Helix pipeline
    // No timeout — Constellation manages lifecycle through Corpus coordination
    // and external cancellation, not arbitrary time limits.
    const helixPromise = runHelixPipeline({
      goal: helixGoal,
      context: helixContext,
      sessionId: helixId,
      logger,
      timeoutMs: 24 * 60 * 60 * 1000, // 24h — effectively unlimited; Corpus handles lifecycle
      unityHandle: handles[0],
      yangHandle: handles[1],
      yinHandle: handles[2],
      toolExecutor,
      toolRegistry,
      store,
      eventBus,
      useNativeCoordinator: true,
      brainstemDeps,
      onBlackboardCreated: (childBlackboard) => {
        // Wire a BlackboardBridge between the constellation blackboard and this Helix's blackboard
        const bridge = new BlackboardBridge({
          parent: constellationBlackboard,
          child: childBlackboard,
          childHelixId: helixId,
          logger,
        })
        bridge.start()
        blackboardBridges.set(helixId, bridge)
        helixLog.debug('Blackboard bridge started', { helixId })
      },
      onCancelRegistered: (fn) => {
        // Store the cancel function
        if (cancelFn) {
          const originalCancel = cancelFn
          cancelFn = () => {
            originalCancel()
            fn()
          }
        }
      },
      onBrainstemCreated: (bs) => {
        // Brainstem is already created and registered above
        helixLog.debug('Brainstem created callback received')
      },
    })

    // Race between completion and cancellation
    const promise = Promise.race([helixPromise, cancelPromise]).finally(() => {
      // Close branch in corpus tree
      corpusTree.closeBranch(helixId, node.status === 'completed' ? 'completed' : 'failed')
    })

    const runningHelix: RunningHelix = {
      helixId,
      node,
      promise,
      cancel: cancelFn || (() => {}),
      handles,
      brainstem,
      parentId,
      depth,
    }

    runningHelixes.set(helixId, runningHelix)

    // Track completion
    promise
      .then((result) => {
        helixLog.info('Helix completed', {
          completionStatus: result.completionStatus,
          durationMs: Date.now() - (node.startedAt ?? Date.now()),
        })
        node.status = result.completionStatus.complete ? 'completed' : 'failed'
        node.completedAt = Date.now()
        onNodeCompleted?.(node)
      })
      .catch((err) => {
        helixLog.error('Helix failed', { error: String(err) })
        node.status = 'failed'
        node.completedAt = Date.now()
        onNodeCompleted?.(node)
      })
      .finally(() => {
        runningHelixes.delete(helixId)
      })

    return runningHelix
  }

  // ═════════════════════════════════════════════════════════════════
  // Helper: Handle Spawn Request
  // ═════════════════════════════════════════════════════════════════

  async function handleSpawnRequest(request: SpawnRequest): Promise<void> {
    log.info('Processing spawn request', {
      requestId: request.requestId,
      requestingHelixId: request.requestingHelixId,
      goal: request.goal.slice(0, 100),
    })

    // Check limits
    if (runningHelixes.size >= maxHelixes) {
      log.warn('Max Helixes reached, rejecting spawn request', {
        requestId: request.requestId,
        current: runningHelixes.size,
        max: maxHelixes,
      })
      // TODO: Notify requester of rejection
      return
    }

    const parentHelix = runningHelixes.get(request.requestingHelixId)
    const depth = (parentHelix?.depth ?? 0) + 1

    if (depth > maxDepth) {
      log.warn('Max depth reached, rejecting spawn request', {
        requestId: request.requestId,
        depth,
        maxDepth,
      })
      // TODO: Notify requester of rejection
      return
    }

    // Evaluate via Corpus
    const decision = await corpus.evaluateSpawnRequest(request)

    if (!decision.approved) {
      log.info('Spawn request rejected by Corpus', {
        requestId: request.requestId,
        reason: decision.reason,
      })
      // TODO: Notify requester of rejection
      return
    }

    // Launch child Helix
    try {
      const childGoal = decision.suggestedGoal || request.goal
      await launchHelix(
        childGoal,
        request.context,
        request.requestingHelixId,
        depth
      )
      log.info('Child Helix launched', {
        requestId: request.requestId,
        parentId: request.requestingHelixId,
        depth,
      })
    } catch (err) {
      log.error('Failed to launch child Helix', {
        requestId: request.requestId,
        error: String(err),
      })
    }
  }

  // ═════════════════════════════════════════════════════════════════
  // Helper: Poll for Spawn Requests
  // ═════════════════════════════════════════════════════════════════

  async function pollSpawnRequests(): Promise<void> {
    // TODO: Implement proper spawn request polling
    // For now, we check the spawnQueue periodically
    while (!completed) {
      while (spawnQueue.length > 0) {
        const request = spawnQueue.shift()
        if (request) {
          await handleSpawnRequest(request)
        }
      }
      await new Promise((resolve) => setTimeout(resolve, SPAWN_CHECK_INTERVAL_MS))
    }
  }

  // ═════════════════════════════════════════════════════════════════
  // Main Execution
  // ═════════════════════════════════════════════════════════════════

  let result: ConstellationResult
  let checkpointHandle: ReturnType<typeof setInterval> | undefined

  try {
    // Set up external cancel mechanism
    let externalCancel: () => void = () => {}
    const cancelPromise = new Promise<never>((_, reject) => {
      externalCancel = () => {
        log.info('Constellation cancelled externally')
        for (const running of runningHelixes.values()) {
          try { running.cancel() } catch (_e) { /* best effort */ }
        }
        reject(new Error('Constellation cancelled'))
      }
    })
    opts.onCancelRegistered?.(externalCancel)

    // Launch root Helix
    const rootHelix = await launchHelix(goal, context, undefined, 0)
    rootHelixId = rootHelix.helixId

    // Start spawn request polling
    const spawnPoller = pollSpawnRequests()

    // Start periodic progress checkpoints (every 60s)
    const CHECKPOINT_INTERVAL_MS = 60_000
    if (constellationStore) {
      checkpointHandle = setInterval(() => {
        try {
          const nodeArr = Array.from(nodes.values())
          constellationStore.saveCheckpoint(constellationId, {
            tree: corpusTree.getSnapshot(),
            progress: corpus.getProgressSnapshot(),
            sweepCount: corpus.getResult().sweepCount,
            totalBranches: nodeArr.length,
            completedBranches: nodeArr.filter((n) => n.status === 'completed').length,
            failedBranches: nodeArr.filter((n) => n.status === 'failed').length,
            tokensUsed: nodeArr.reduce((sum, n) => sum + n.tokensUsed, 0),
            durationMs: Date.now() - startTime,
          })
        } catch (err) {
          log.warn('Checkpoint save failed', { error: String(err) })
        }
      }, CHECKPOINT_INTERVAL_MS)
    }

    // Wait for root Helix completion (no timeout — Constellation runs to completion)
    // Note: We don't wait for all children — the root's completion signals
    // that the main goal is achieved. Children may still be running cleanup.
    log.info('Waiting for root Helix completion', { rootHelixId })

    await Promise.race([rootHelix.promise, cancelPromise])

    // Give children a grace period to complete
    log.info('Root Helix completed, waiting for children', {
      childrenCount: runningHelixes.size - 1,
    })

    const gracePeriodMs = 120_000 // 2 minute grace period for children to finish work
    const gracePromise = new Promise<void>((resolve) => {
      setTimeout(resolve, gracePeriodMs)
    })

    // Wait for either all children to complete or grace period
    const childPromises = Array.from(runningHelixes.values())
      .filter((h) => h.helixId !== rootHelixId)
      .map((h) => h.promise)

    await Promise.race([Promise.all(childPromises), gracePromise])

    log.info('Constellation execution complete', {
      totalNodes: nodes.size,
      completedNodes: Array.from(nodes.values()).filter((n) => n.status === 'completed').length,
      failedNodes: Array.from(nodes.values()).filter((n) => n.status === 'failed').length,
    })

    // Build result
    result = {
      constellationId,
      rootHelixId: rootHelixId!,
      nodes,
      constellationBlackboard: constellationBlackboard.getSnapshot(),
      totalTokensUsed: Array.from(nodes.values()).reduce((sum, n) => sum + n.tokensUsed, 0),
      totalDurationMs: Date.now() - startTime,
      corpus: corpus.getResult(),
      spawnRequests: [],
    }

    // Emit completion event
    eventBus?.emit({
      type: 'team:event' as any,
      teamId: constellationId,
      data: {
        event: 'constellation:completed',
        durationMs: result.totalDurationMs,
        nodeCount: nodes.size,
        timestamp: Date.now(),
      },
    } as any)

    // Archive to ConstellationStore (if provided)
    if (constellationStore) {
      try {
        const corpusResult = corpus.getResult()
        const treeSnapshot = corpusTree.getSnapshot()
        const progressSnapshot: ProgressSnapshot = {
          markdown: `Constellation completed: ${nodes.size} nodes, ${result.totalDurationMs}ms`,
          data: {
            activeBranches: 0,
            totalBranches: nodes.size,
            completedBranches: Array.from(nodes.values()).filter(n => n.status === 'completed').length,
            failedBranches: Array.from(nodes.values()).filter(n => n.status === 'failed').length,
            sweepCount: corpusResult.sweepCount,
            lastSweepAt: Date.now(),
          },
        }
        constellationStore.completeSession(constellationId, {
          tree: treeSnapshot,
          progress: progressSnapshot,
          // Convert simplified branchAssessments to full BranchAssessment format
          branchAssessments: corpusResult.branchAssessments.map(a => ({
            helixId: a.helixId,
            status: a.status,
            rollingScore: a.rollingScore,
            scoreTrajectory: [],
            dominantPattern: a.dominantPattern as any,
            filesModified: new Set<string>(),
            decliningScoreStreak: 0,
            lastActivityAt: Date.now(),
          })),
          crossPatterns: corpusResult.crossPatterns,
          interventions: corpusResult.interventions,
          sweepCount: corpusResult.sweepCount,
          helixSessionIds: Array.from(nodes.keys()),
          totalBranches: nodes.size,
          completedBranches: progressSnapshot.data.completedBranches,
          failedBranches: progressSnapshot.data.failedBranches,
          tokensUsed: result.totalTokensUsed,
          durationMs: result.totalDurationMs,
        })
        log.info('Archived completed session to ConstellationStore', { constellationId })
      } catch (err) {
        log.warn('Failed to archive session to ConstellationStore', { error: String(err) })
      }
    }
  } catch (err) {
    log.error('Constellation pipeline failed', { error: String(err) })

    // Build partial result
    result = {
      constellationId,
      rootHelixId: rootHelixId ?? constellationId,
      nodes,
      constellationBlackboard: constellationBlackboard.getSnapshot(),
      totalTokensUsed: Array.from(nodes.values()).reduce((sum, n) => sum + n.tokensUsed, 0),
      totalDurationMs: Date.now() - startTime,
      corpus: corpus.getResult(),
      spawnRequests: [],
      error: String(err),
    }

    // Emit failure event
    eventBus?.emit({
      type: 'team:event' as any,
      teamId: constellationId,
      data: {
        event: 'constellation:failed',
        error: String(err),
        timestamp: Date.now(),
      },
    } as any)

    // Archive failure to ConstellationStore (if provided)
    if (constellationStore) {
      try {
        constellationStore.failSession(constellationId, String(err), Date.now() - startTime)
        log.info('Archived failed session to ConstellationStore', { constellationId })
      } catch (storeErr) {
        log.warn('Failed to archive failure to ConstellationStore', { error: String(storeErr) })
      }
    }

    throw err
  } finally {
    completed = true

    // Stop checkpoint timer
    if (checkpointHandle) {
      clearInterval(checkpointHandle)
    }

    // Cancel any remaining Helixes
    for (const [id, helix] of runningHelixes) {
      log.info('Cancelling Helix', { helixId: id })
      try {
        helix.cancel()
      } catch (err) {
        log.warn('Error cancelling Helix', { helixId: id, error: String(err) })
      }
    }

    // Stop Corpus
    log.info('Stopping Corpus')
    try {
      await corpus.stop()
    } catch (err) {
      log.warn('Error stopping Corpus', { error: String(err) })
    }

    // Stop all blackboard bridges
    for (const [id, bridge] of blackboardBridges) {
      try {
        bridge.stop()
      } catch (err) {
        log.warn('Error stopping blackboard bridge', { helixId: id, error: String(err) })
      }
    }

    // Release all model handles
    log.info('Releasing model handles')
    for (const [id, helix] of runningHelixes) {
      for (const handle of helix.handles) {
        try {
          await handle.release()
        } catch (err) {
          log.warn('Error releasing model handle', { helixId: id, error: String(err) })
        }
      }
    }

    log.info('Constellation pipeline cleanup complete')
  }

  return result
}
