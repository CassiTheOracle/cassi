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
import type { BrainstemDeps, SharedTreeReader } from '../helix/brainstem-types.js'
import type { HelixBrainstem } from '../helix/brainstem.js'
import { BrainstemMiniHelix } from '../helix/brainstem-mini-helix.js'
import { CorpusMiniHelix } from './corpus-mini-helix.js'
import { runHelixPipeline } from '../helix/helix-pipeline.js'
import { Blackboard } from '../flux-team/blackboard.js'
import { BlackboardBridge } from './blackboard-bridge.js'
import { Corpus } from './corpus.js'
import { CorpusTree } from './corpus-tree.js'
import { CrossHelixDialectic } from './cross-helix-dialectic.js'
import { readFile as fsReadFile } from 'node:fs/promises'
import { resolve as pathResolve } from 'node:path'
import type { CorpusLLM } from './corpus-types.js'
import type { GoalDecomposition, GoalSubTask } from './corpus-types.js'
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

/**
 * Simple complexity check for goal decomposition.
 * Returns true if the goal is likely complex enough to benefit from decomposition.
 */
function isGoalComplex(goal: string): boolean {
  // Heuristics: long goals, multiple sections, mentions multiple modules/directories
  if (goal.length > 500) return true
  if ((goal.match(/\n##/g) ?? []).length >= 2) return true
  if ((goal.match(/(?:core\/|src\/|lib\/)[^\s,]+/g) ?? []).length >= 3) return true
  if ((goal.match(/\d+\.\s/g) ?? []).length >= 3) return true // numbered list with 3+ items
  return false
}

/**
 * Run pre-flight goal decomposition via a planning Helix.
 * For complex goals, spawns a short-lived full Helix that reads the codebase,
 * validates paths, and produces a structured decomposition.
 * For simple goals, returns a pass-through (no decomposition).
 */
async function runGoalDecomposition(opts: {
  goal: string
  context?: string
  launchHelix: (goal: string, context: string | undefined, template: ConstellationTemplate | undefined, depth: number) => Promise<{ helixId: string; promise: Promise<HelixResult> }>
  corpus: Corpus
  log: ILogger
  readFile: (path: string) => Promise<string | null>
}): Promise<GoalDecomposition> {
  const startTime = Date.now()

  if (!isGoalComplex(opts.goal)) {
    opts.log.info('Goal is simple, skipping decomposition')
    return {
      decomposed: false,
      originalGoal: opts.goal,
      subTasks: [{ goal: opts.goal, priority: 1 }],
      strategy: 'parallel',
      durationMs: Date.now() - startTime,
    }
  }

  opts.log.info('Goal is complex, launching planning Helix for decomposition', {
    goalLength: opts.goal.length,
  })

  const plannerGoal = `Analyze and decompose the following goal into concrete sub-tasks.

## Original Goal
${opts.goal}
${opts.context ? `\n## Additional Context\n${opts.context}` : ''}

## Task
1. Use read_file and list_directory to explore the codebase — these are the ONLY tools you should use for exploration
2. Do NOT use collect_thoughts, serena_*, or gitnexus_* tools — they are not useful for this task
3. Identify 2-5 concrete, independent sub-tasks that together achieve the goal
4. For each sub-task, validate that referenced file paths actually exist
5. Call signal_done with the decomposition in the conclusion field using the format below

## Output Format (put this in signal_done's conclusion field)

DECOMPOSITION_START
STRATEGY: parallel|sequential|tree
SHARED_CONTEXT: <any context all sub-tasks need>

SUBTASK: <focused goal for sub-task 1>
FILES: <comma-separated file paths relevant to this sub-task>
PRIORITY: <1-5, higher is more important>

SUBTASK: <focused goal for sub-task 2>
FILES: <comma-separated file paths>
PRIORITY: <1-5>

... (repeat for each sub-task)
DECOMPOSITION_END

## Rules
- Each SUBTASK must be specific enough to execute independently
- Validate all file paths with read_file before including them
- Keep sub-tasks focused — prefer 2-3 well-scoped tasks over 5+ vague ones
- If the goal is actually simple and doesn't need decomposition, output a single SUBTASK with the original goal
- Call signal_done within 10 iterations — do not endlessly explore`

  try {
    const plannerHelix = await opts.launchHelix(plannerGoal, undefined, 'minimal', 0)

    // Wait for planning Helix with a timeout (5 minutes max for planning)
    const timeoutPromise = new Promise<HelixResult>((_, reject) => {
      setTimeout(() => reject(new Error('Planning Helix timed out')), 300_000)
    })

    const result = await Promise.race([plannerHelix.promise, timeoutPromise])

    // Parse the decomposition from the result
    const decomposition = parseDecompositionResult(result, opts.goal, startTime)
    opts.log.info('Decomposition complete', {
      decomposed: decomposition.decomposed,
      subTasks: decomposition.subTasks.length,
      strategy: decomposition.strategy,
      durationMs: decomposition.durationMs,
    })

    return decomposition
  } catch (error) {
    opts.log.warn('Goal decomposition failed, falling back to single Helix', {
      error: String(error),
    })
    return {
      decomposed: false,
      originalGoal: opts.goal,
      subTasks: [{ goal: opts.goal, priority: 1 }],
      strategy: 'parallel',
      durationMs: Date.now() - startTime,
    }
  }
}

/**
 * Parse the structured decomposition from a planning Helix result.
 */
function parseDecompositionResult(
  result: HelixResult,
  originalGoal: string,
  startTime: number,
): GoalDecomposition {
  // Look for DECOMPOSITION_START...DECOMPOSITION_END in the result
  const conclusion = result.unityConclusion ?? result.mentorSynthesis ?? ''
  const fullText = `${conclusion}\n${result.unitySummary ?? ''}\n${result.unityKeyPoints?.join('\n') ?? ''}`

  const decompMatch = fullText.match(/DECOMPOSITION_START\s*\n([\s\S]*?)DECOMPOSITION_END/)
  if (!decompMatch) {
    // No decomposition block found — return as single task
    return {
      decomposed: false,
      originalGoal,
      subTasks: [{ goal: originalGoal, priority: 1 }],
      strategy: 'parallel',
      durationMs: Date.now() - startTime,
    }
  }

  const block = decompMatch[1]

  // Parse strategy
  const strategyMatch = block.match(/STRATEGY:\s*(parallel|sequential|tree)/i)
  const strategy = (strategyMatch?.[1]?.toLowerCase() ?? 'parallel') as 'parallel' | 'sequential' | 'tree'

  // Parse shared context
  const sharedContextMatch = block.match(/SHARED_CONTEXT:\s*(.+?)(?=\n\nSUBTASK:|\n$)/s)
  const sharedContext = sharedContextMatch?.[1]?.trim()

  // Parse sub-tasks
  const subTaskPattern = /SUBTASK:\s*(.+?)(?:\nFILES:\s*(.+?))?(?:\nPRIORITY:\s*(\d))?(?=\n\nSUBTASK:|\nDECOMPOSITION_END|$)/gs
  const subTasks: GoalSubTask[] = []

  let match
  while ((match = subTaskPattern.exec(block)) !== null) {
    const goal = match[1].trim()
    const files = match[2]?.trim().split(',').map(f => f.trim()).filter(Boolean)
    const priority = parseInt(match[3] ?? '1', 10) || 1

    if (goal) {
      subTasks.push({
        goal,
        relevantFiles: files?.length ? files : undefined,
        priority,
      })
    }
  }

  if (subTasks.length === 0) {
    return {
      decomposed: false,
      originalGoal,
      subTasks: [{ goal: originalGoal, priority: 1 }],
      strategy: 'parallel',
      durationMs: Date.now() - startTime,
    }
  }

  return {
    decomposed: subTasks.length > 1,
    originalGoal,
    subTasks: subTasks.sort((a, b) => b.priority - a.priority),
    strategy,
    sharedContext: sharedContext || undefined,
    durationMs: Date.now() - startTime,
  }
}

/**
 * Safe file reader for brainstem/corpus path validation.
 * Returns file content or null if not found. Scoped to workspace root.
 * @dep callers: runConstellationPipeline (core/intelligence/constellation/constellation-pipeline.ts), launchHelix (core/intelligence/constellation/constellation-pipeline.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function safeReadFile(path: string, workspaceRoot: string): Promise<string | null> {
  try {
    const resolved = pathResolve(workspaceRoot, path)
    // Security: ensure the resolved path is within the workspace
    if (!resolved.startsWith(workspaceRoot)) return null
    const content = await fsReadFile(resolved, 'utf-8')
    return content
  } catch {
    return null
  }
}

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

  /** Maximum total steps across all branches before forced completion. Default: 100 */
  maxTotalSteps?: number

  /** Enable cross-Helix dialectic between spawned branches. Default: true */
  enableCrossHelixDialectic?: boolean

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

  // ── Mini-Helix Configuration ────────────────────────────────────

  /**
   * Enable mini-Helix mode for the Corpus.
   * When true, the Corpus runs as a self-driving mini-Helix session
   * instead of using the legacy LLM analysis path.
   * Default: false (opt-in until validated)
   */
  useMiniHelixCorpus?: boolean

  /**
   * Enable mini-Helix mode for Brainstems.
   * When true, Brainstems run as sidecar mini-Helix sessions instead
   * of the legacy processSingleWorkUnit loop.
   * Default: false (opt-in until validated)
   */
  useMiniHelixBrainstem?: boolean

  /**
   * Corpus mini-Helix model configuration.
   * Default model tier: 'balanced', can be overridden with modelName.
   */
  corpusMiniHelix?: {
    modelTier?: string
    modelName?: string
    maxIterationsPerCycle?: number
    cycleTimeoutMs?: number
  }

  /**
   * Brainstem mini-Helix model configuration.
   * Default model tier: 'fast', can be overridden with modelName.
   */
  brainstemMiniHelix?: {
    modelTier?: string
    modelName?: string
    maxIterationsPerCycle?: number
    cycleTimeoutMs?: number
    cyclePollMs?: number
  }
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
  brainstemMiniHelix?: BrainstemMiniHelix
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

  // Create cross-Helix dialectic for inter-branch communication
  const crossHelixDialectic = (opts.enableCrossHelixDialectic !== false)
    ? new CrossHelixDialectic(log)
    : undefined

  const corpus = new Corpus(
    corpusTree,
    {
      llm: corpusLLM,
      logger,
      goal,
      constellationId,
      eventBus,
      blackboard: constellationBlackboard,
      crossHelixDialectic,
      readFile: (path: string) => safeReadFile(path, process.cwd()),
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
  // Corpus Mini-Helix (optional — self-driving analysis loop)
  // ═════════════════════════════════════════════════════════════════

  let corpusMiniHelix: CorpusMiniHelix | undefined

  if (opts.useMiniHelixCorpus) {
    corpusMiniHelix = new CorpusMiniHelix(
      corpusTree,
      {
        llm: corpusLLM,
        logger,
        goal,
        constellationId,
        eventBus,
        blackboard: constellationBlackboard,
        crossHelixDialectic,
        readFile: (path: string) => safeReadFile(path, process.cwd()),
        onSpawnRequest: (req) => {
          const spawnRequest: SpawnRequest = {
            requestId: `spawn-corpus-mh-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
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
        },
      },
      {
        logger,
        eventBus,
        handleFactory: async (config) => {
          return opts.handleFactory({
            tier: config.tier,
            purpose: config.purpose,
            sessionId: config.sessionId,
          })
        },
      },
      {
        corpus: { maxBranches: maxHelixes, maxDepth },
        miniHelix: opts.corpusMiniHelix,
      },
      // Provide available worker tool names for Corpus system prompt awareness
      toolRegistry ? toolRegistry.list().map((t) => t.name) : [],
    )

    await corpusMiniHelix.start()
    log.info('Corpus mini-Helix started')
  }

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

    // Create Brainstem deps with corpus tree integration
    // NOTE: The actual Brainstem instance is created and started inside runHelixPipeline.
    // We capture it via the onBrainstemCreated callback for Corpus registration.
    //
    // The sharedTree reader provides each Brainstem with read/write access to
    // the Shared Thought Tree for stigmergic self-organization.
    const sharedTreeReader = createSharedTreeReaderForHelix(helixId, corpusTree)

    const brainstemDeps: BrainstemDeps = {
      llm: corpusLLM,
      logger,
      goal: helixGoal,
      sessionId: helixId,
      eventBus,
      corpusTree,
      helixId,
      readFile: (path: string) => safeReadFile(path, process.cwd()),
      sharedTree: sharedTreeReader,
      escalateToCorpus: (reason: string, context: Record<string, unknown>) => {
        corpus.receiveEscalation(reason, { ...context, helixId })
      },
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

    // The actual brainstem reference — set by onBrainstemCreated when the pipeline starts it
    let activeBrainstem: HelixBrainstem | undefined

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
      // Constellation Helixes run longer tool-call chains (drone scouts, file reads, etc.)
      // Relax inactivity thresholds: warn=5min, escalate=10min, kill=15min
      inactivityThresholds: {
        warnMs: 300_000,
        escalateMs: 600_000,
        killMs: 900_000,
      },
      onWorkUnit: (wu, iteration) => {
        // Feed work units to the RUNNING brainstem (captured from onBrainstemCreated)
        if (activeBrainstem) {
          activeBrainstem.onWorkUnit(wu, iteration)
        }
      },
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

        // Bridge blackboard findings into cross-Helix dialectic.
        // When this branch posts a finding, forward it to other branches.
        if (crossHelixDialectic) {
          childBlackboard.subscribe('findings', undefined, (entry: { content: string; tags?: string[] }) => {
            crossHelixDialectic.postFinding(helixId, entry.content, {
              tags: entry.tags,
            })
          })
          childBlackboard.subscribe('concerns', undefined, (entry: { content: string; tags?: string[] }) => {
            crossHelixDialectic.postFinding(helixId, `[CONCERN] ${entry.content}`, {
              tags: [...(entry.tags ?? []), 'concern'],
            })
          })
        }
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
        // Capture the pipeline's brainstem (which is started and has its runLoop active)
        // and register it with the Corpus for tree integration
        activeBrainstem = bs
        corpus.registerBrainstem(helixId, bs)
        helixLog.info('Pipeline Brainstem registered with Corpus')

        // Update the RunningHelix reference so cancel can stop the brainstem
        const rh = runningHelixes.get(helixId)
        if (rh) rh.brainstem = bs

        // Register with cross-Helix dialectic so inter-branch messages can flow
        if (crossHelixDialectic) {
          crossHelixDialectic.registerBranch(helixId, bs, helixGoal)
        }

        // Optionally start a Brainstem mini-Helix sidecar
        if (opts.useMiniHelixBrainstem) {
          // Collect available worker tool names so Brainstem knows what tools the worker has
          const workerToolNames = toolRegistry
            ? toolRegistry.list().map((t) => t.name)
            : []

          const brainstemMH = new BrainstemMiniHelix({
            helixId,
            goal: helixGoal,
            constellationGoal: goal,
            constellationId,
            logger,
            availableToolNames: workerToolNames,
            miniHelixDeps: {
              logger,
              eventBus,
              handleFactory: (config) => opts.handleFactory({
                tier: config.tier,
                purpose: config.purpose,
                sessionId: config.sessionId,
              }),
            },
            sharedTree: sharedTreeReader,
            escalateToCorpus: (reason, context) => {
              corpus.receiveEscalation(reason, { ...context, helixId })
            },
            onInjectGuidance: (content, urgency) => {
              // The mini-Helix brainstem injects guidance through the legacy brainstem's
              // pending guidance queue — this gets consumed by Unity on the next iteration
              const guidance: import('../helix/brainstem-types.js').PendingGuidance = {
                text: content,
                urgency,
                fromStep: 0,
                triggeredBy: 'none',
                timestamp: Date.now(),
              }
              ;(bs as any).guidanceQueue?.push(guidance)
            },
            config: opts.brainstemMiniHelix,
          })

          // Register mini-Helix brainstem with Corpus
          if (corpusMiniHelix) {
            corpusMiniHelix.registerBrainstem(helixId, { onCorpusDirective: (d) => brainstemMH.onCorpusDirective(d) })
          }

          const rhForMH = runningHelixes.get(helixId)
          if (rhForMH) rhForMH.brainstemMiniHelix = brainstemMH

          brainstemMH.start().catch((err) => {
            helixLog.error('Brainstem mini-Helix failed to start', { error: String(err) })
          })
        }
      },
    })

    // Race between completion and cancellation
    // NOTE: Do NOT chain .finally() here — node.status is set in the .then()/.catch()
    // below. Chaining .finally() on the race would execute before .then(), causing
    // branches to always be closed as 'failed' (the initial status).
    const promise = Promise.race([helixPromise, cancelPromise])

    const runningHelix: RunningHelix = {
      helixId,
      node,
      promise,
      cancel: cancelFn || (() => {}),
      handles,
      brainstem: activeBrainstem,
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
      .finally(async () => {
        // Close branch in corpus tree — node.status is now correct after .then()/.catch()
        corpusTree.closeBranch(helixId, node.status === 'completed' ? 'completed' : 'failed')
        // Unregister from cross-Helix dialectic
        crossHelixDialectic?.unregisterBranch(helixId)
        // Stop Brainstem mini-Helix sidecar if it was running
        const rh = runningHelixes.get(helixId)
        if (rh?.brainstemMiniHelix) {
          await rh.brainstemMiniHelix.stop().catch((err) => {
            helixLog.warn('Error stopping Brainstem mini-Helix', { error: String(err) })
          })
        }
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

    // ── Pre-flight Goal Decomposition ──────────────────────────────
    // For complex goals, run a short planning Helix to decompose the goal
    // into validated sub-tasks before launching execution Helixes.
    const decomposition = await runGoalDecomposition({
      goal,
      context,
      launchHelix,
      corpus,
      log,
      readFile: (path: string) => safeReadFile(path, process.cwd()),
    })

    if (decomposition.decomposed && decomposition.subTasks.length > 1) {
      log.info('Goal decomposed into sub-tasks', {
        subTasks: decomposition.subTasks.length,
        strategy: decomposition.strategy,
        durationMs: decomposition.durationMs,
      })

      // Launch Helixes based on decomposition
      const helixPromises: Array<{ helixId: string; promise: Promise<HelixResult> }> = []
      for (const subTask of decomposition.subTasks) {
        const subContext = [
          decomposition.sharedContext,
          subTask.context,
          subTask.relevantFiles?.length
            ? `Relevant files: ${subTask.relevantFiles.join(', ')}`
            : undefined,
        ].filter(Boolean).join('\n\n')

        const h = await launchHelix(subTask.goal, subContext || undefined, subTask.template, 0)
        helixPromises.push(h)
      }
      rootHelixId = helixPromises[0]?.helixId ?? ''

      // Start spawn request polling
      const spawnPoller = pollSpawnRequests()

      // Wait for all sub-task Helixes to complete
      log.info('Waiting for decomposed sub-task Helixes', { count: helixPromises.length })
      await Promise.race([
        Promise.all(helixPromises.map(h => h.promise)),
        cancelPromise,
      ])

      void spawnPoller // spawnPoller is a Promise, not a timer — it exits on its own
    } else {
      // Simple goal or decomposition failed — launch single root Helix (original behavior)
      if (decomposition.decomposed) {
        log.info('Decomposition returned single task, proceeding with single Helix')
      }

      // Launch root Helix
      const rootHelix = await launchHelix(goal, context, undefined, 0)
      rootHelixId = rootHelix.helixId

      // Start spawn request polling
      const spawnPoller = pollSpawnRequests()

      // Start periodic progress checkpoints (every 60s)
      // Also checks maxTotalSteps limit.
      const CHECKPOINT_INTERVAL_MS = 60_000
      const maxTotalSteps = opts.maxTotalSteps ?? 100
      if (constellationStore) {
        checkpointHandle = setInterval(() => {
          try {
            const nodeArr = Array.from(nodes.values())
            const totalSteps = corpusTree.getSnapshot().branches.reduce(
              (sum, b) => sum + b.stepCount, 0
            )

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

            // Check max steps limit
            if (totalSteps >= maxTotalSteps) {
              log.warn('Max total steps reached, cancelling Constellation', {
                totalSteps,
                maxTotalSteps,
                branches: nodeArr.length,
              })
              for (const running of runningHelixes.values()) {
                try { running.cancel() } catch (_e) { /* best effort */ }
              }
            }
          } catch (err) {
            log.warn('Checkpoint save failed', { error: String(err) })
          }
        }, CHECKPOINT_INTERVAL_MS)
      }

      // Wait for root Helix completion
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

      void spawnPoller // spawnPoller is a Promise, not a timer — it exits on its own
    }

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

    // Cancel any remaining Helixes and stop their Brainstems
    for (const [id, helix] of runningHelixes) {
      log.info('Cancelling Helix', { helixId: id })
      try {
        helix.cancel()
      } catch (err) {
        log.warn('Error cancelling Helix', { helixId: id, error: String(err) })
      }
      // Explicitly stop the Brainstem to prevent zombie LLM calls
      if (helix.brainstem) {
        try {
          await helix.brainstem.stop()
          log.info('Brainstem stopped', { helixId: id })
        } catch (err) {
          log.warn('Error stopping Brainstem', { helixId: id, error: String(err) })
        }
      }
      // Stop Brainstem mini-Helix sidecar if running
      if (helix.brainstemMiniHelix) {
        try {
          await helix.brainstemMiniHelix.stop()
          log.info('Brainstem mini-Helix stopped', { helixId: id })
        } catch (err) {
          log.warn('Error stopping Brainstem mini-Helix', { helixId: id, error: String(err) })
        }
      }
    }

    // Stop Corpus
    log.info('Stopping Corpus')
    try {
      await corpus.stop()
    } catch (err) {
      log.warn('Error stopping Corpus', { error: String(err) })
    }

    // Stop Corpus mini-Helix if running
    if (corpusMiniHelix) {
      try {
        await corpusMiniHelix.stop()
        log.info('Corpus mini-Helix stopped')
      } catch (err) {
        log.warn('Error stopping Corpus mini-Helix', { error: String(err) })
      }
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


// ═══════════════════════════════════════════════════════════════════
// Shared Thought Tree: SharedTreeReader Factory
// ═══════════════════════════════════════════════════════════════════

/**
 * Create a SharedTreeReader bound to a specific Helix.
 * This provides the Brainstem with read/write access to the
 * Shared Thought Tree, scoped to its own branch.
 *
 * All read operations exclude the caller's own data where appropriate.
 * All write operations automatically set the helixId.
 */
function createSharedTreeReaderForHelix(
  helixId: string,
  tree: CorpusTree
): SharedTreeReader {
  return {
    // ── Read operations ───────────────────────────────────────
    getPeerDigests: () => tree.getDigestsExcluding(helixId),
    getRelevantDigests: () => tree.getRelevantDigests(helixId),
    findRelatedTopics: (files, goalKeywords) => tree.findRelatedTopics(files, goalKeywords),
    getAllTopics: () => tree.getAllTopics(),
    getElevatedPatterns: () => tree.getElevatedPatterns(),
    getAllRetrospectives: () => tree.getAllRetrospectives(),
    getEffectivenessStats: () => tree.getEffectivenessStats(),

    // ── Write operations ──────────────────────────────────────
    updateDigest: (digest) => tree.updateDigest(helixId, digest),
    createTopic: (name, contribution) => tree.createTopic(name, helixId, contribution),
    contributeTopic: (topicId, contribution) => tree.contributeTopic(topicId, contribution),
    recordRetrospective: (retrospective) => tree.recordRetrospective(helixId, retrospective),
    recordEffectiveness: (record) => tree.recordEffectiveness(record),
  }
}
