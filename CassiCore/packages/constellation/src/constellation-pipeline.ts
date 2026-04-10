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
import type { BrainstemDeps, BrainstemAnnotation, SharedTreeReader } from '../helix/brainstem-types.js'
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
import type { IMemory, SearchResult } from '../../../types/intelligence.js'
import { MemoryInjectionService } from './memory-injection.js'
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
import { fastDecompose, shouldDecompose, type DecompositionDecision } from './fast-decomposer.js'
import { DecompositionTracker } from './decomposition-tracker.js'
import { ConstellationWorktreeIsolation } from './worktree-isolation.js'
import { TopologyGraph } from './topology/topology-graph.js'
import { BrainstemBridge } from './topology/brainstem-bridge.js'
import { serializeTopologySnapshot } from './topology/topology-types.js'
import type { EmbeddingService } from '../embeddings/embedding-service.js'
import { createConstellationGuidanceProvider } from './guidance-provider.js'
import { scoreSpecificity } from '../code-analysis/specificity-scorer.js'

// Constants

const DEFAULT_MAX_HELIXES = 16
const DEFAULT_MAX_DEPTH = 4
const SPAWN_CHECK_INTERVAL_MS = 1000

/**
 * Safe file reader for brainstem/corpus path validation.
 * Returns file content or null if not found. Scoped to workspace root.
 * @dep callers: launchHelix (core/intelligence/constellation/constellation-pipeline.ts), runConstellationPipeline (core/intelligence/constellation/constellation-pipeline.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function safeReadFile(path: string, workspaceRoot: string): Promise<string | null> {
  try {
    const resolved = pathResolve(workspaceRoot, path)
    // WHY: Security: ensure the resolved path is within the workspace
    if (!resolved.startsWith(workspaceRoot)) return null
    const content = await fsReadFile(resolved, 'utf-8')
    return content
  } catch {
    return null
  }
}

/**
 * Enrich a CorpusTreeSnapshot with the current topology state.
 * WHY: CorpusTree doesn't know about topology — it's a pipeline-level concern.
 * We attach the serialized topology here before persisting to the store.
 */
function enrichTreeWithTopology(
  tree: import('./corpus-types.js').CorpusTreeSnapshot,
  topology: TopologyGraph | null | undefined,
): import('./corpus-types.js').CorpusTreeSnapshot {
  if (!topology?.enabled) return tree
  try {
    return { ...tree, topology: serializeTopologySnapshot(topology.getSnapshot()) }
  } catch {
    return tree
  }
}

// Pipeline Options

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

  /** Soft step budget — when reached, Corpus receives budget pressure to prioritize
   *  completion instead of force-killing branches. Default: 200 */
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

  /** Brainstem LLM adapter (separate from Corpus for independent model routing).
   *  Falls back to corpusLLM when not provided. */
  brainstemLLM?: CorpusLLM

  /** Optional memory system for cross-run learning and context injection */
  memory?: IMemory

  /** Pre-assembled codebase context from GitNexus (for fast decomposition) */
  codebaseContext?: string

  /**
   * Branch isolation mode.
   * When 'worktree', each Helix branch gets its own git worktree.
   * Changes are auto-committed and merged back on branch completion.
   * Default: 'none' (all branches share the main working directory).
   */
  isolation?: 'none' | 'worktree'

  /** Project root directory for worktree isolation. Default: process.cwd() */
  projectRoot?: string

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

  /** Audit trail for writing decomposition plans and completion summaries */
  auditTrail?: import('./constellation-audit-trail.js').ConstellationAuditTrail

  /**
   * Cost-effective mode. When true, posture model tiers are downgraded
   * to cheaper alternatives (e.g. kimi → qwenPlus, qwenPlus → minimax).
   * Does not affect behavioral correctness — only model selection.
   */
  costEffective?: boolean

  /**
   * Embedding service for the Topology Graph's gravity engine.
   * When provided, topology is enabled — Helix sessions get spatial clustering,
   * link formation, and bridged context sharing based on embedding similarity.
   * When absent, topology is disabled and the Corpus runs without spatial awareness.
   */
  embeddingService?: EmbeddingService

  /** Reasoning Bank for caching and retrieving successful reasoning traces.
   *  When provided, completed Helix sessions with sufficient quality scores
   *  are ingested, and new branches receive relevant past reasoning. */
  reasoningBank?: import('../reasoning-bank/index.js').ReasoningBank

  /** Context feedback tracker for learning which context injections help.
   *  When provided, each branch's context injection is recorded, and after
   *  completion the files used are compared to files suggested. The Bayesian
   *  model learns which specificity/mode combinations produce useful context. */
  contextFeedback?: import('../code-analysis/feedback-tracker.js').ContextFeedbackTracker

  /** Guidance registry shared with collect_thoughts. When provided, the pipeline
   *  creates per-branch guidance providers and registers them here so that
   *  collect_thoughts can look them up by sessionId during mid-reasoning enrichment. */
  guidanceRegistry?: import('./guidance-provider.js').ConstellationGuidanceRegistry

  /**
   * Meditation mode. When true, Helix branches receive no workspace structure,
   * no codebase context, no elevated patterns, no reasoning bank traces —
   * only what the memory system naturally surfaces. Agents explore in solitude.
   * The Brainstem still captures work units for passive Corpus observation.
   */
  meditationMode?: boolean

  /** Meditation style — controls tool set and Corpus prompt tone */
  meditationStyle?: import('./meditation/styles.js').MeditationStyle

  /** MnemicField for meditation Corpus tools (consolidation, kindling, engram creation) */
  mnemicField?: import('../mnemic-field/index.js').MnemicField
}

// Internal State

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
  template?: ConstellationTemplate
}

// Main Pipeline Function

/**
 * @dep callers: project (core/intelligence/constellation/constellation-orchestrator.ts)
 * @dep calls: now, createSession, cancel, pause, initPlan [+36]
 * @dep flows: RunConstellationPipeline → Touch (1/3)
 * @dep module: Lumen
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

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
    brainstemLLM: brainstemLLMOpt,
    onNodeCreated,
    onNodeCompleted,
  } = opts

  const costEffective = opts.costEffective ?? false
  const log = logger.child('constellation-pipeline')

  // Fallback counter for helix IDs when constellation store is unavailable
  let helixCounter = 0

  // WHY: Worktree isolation gives each branch its own working copy.
  // Prevents file conflicts when multiple branches edit the same files.
  const worktreeIsolation = opts.isolation === 'worktree'
    ? new ConstellationWorktreeIsolation({
        logger: log,
        projectRoot: opts.projectRoot ?? process.cwd(),
        constellationId,
        maxWorktrees: maxHelixes,
      })
    : undefined

  // WHY: Resolve brainstem LLM — falls back to corpusLLM when not explicitly provided
  const brainstemLLM = brainstemLLMOpt ?? corpusLLM

  // Used to inject relevant past-run memories into each new Helix branch.
  const memoryInjectionService = opts.memory
    ? new MemoryInjectionService(opts.memory, log.child('memory-injection'))
    : undefined
  log.info('Constellation pipeline starting', {
    constellationId,
    goal: goal.slice(0, 200),
    template,
    maxHelixes,
    maxDepth,
  })

  // Create session in ConstellationStore (if provided)

  if (constellationStore) {
    try {
      constellationStore.createSession(constellationId, goal, {
        context,
        template,
        maxHelixes,
        maxDepth,
        meditationMode: opts.meditationMode,
        meditationStyle: opts.meditationStyle,
        costEffective: opts.costEffective,
      })
      log.debug('Created ConstellationStore session', { constellationId })
    } catch (err) {
      log.warn('Failed to create ConstellationStore session', { error: String(err) })
    }
  }

  // Create Corpus Tree, Blackboard, and Corpus

  const corpusTree = new CorpusTree(logger)

  // Seed the Corpus tree with historical elevated patterns from the DB
  // WHY: onPatternElevated is set AFTER seeding to avoid re-persisting
  // patterns that are already in the database.
  if (constellationStore) {
    try {
      const historicalPatterns = constellationStore.getElevatedPatterns({ minScore: 0.6, limit: 50 })
      for (const pattern of historicalPatterns) {
        corpusTree.elevatePattern(pattern)
      }
      if (historicalPatterns.length > 0) {
        log.info('Seeded Corpus tree with historical elevated patterns', {
          count: historicalPatterns.length,
        })
      }
    } catch (err) {
      log.warn('Failed to load historical elevated patterns', { error: String(err) })
    }

    // Wire persistence: newly elevated patterns get saved to DB
    corpusTree.onPatternElevated = (pattern) => {
      try {
        constellationStore.saveElevatedPattern(pattern, constellationId)
      } catch (err) {
        log.warn('Failed to persist elevated pattern', { id: pattern.id, error: String(err) })
      }
    }
  }

  // Create constellation-level blackboard for cross-Helix communication
  const constellationBlackboard = new Blackboard(log, constellationId)
  constellationBlackboard.initPlan(goal)
  constellationBlackboard.initReport(goal)

  // Create cross-Helix dialectic for inter-branch communication
  // Skip in meditation — single-branch exploration has no inter-branch communication
  const crossHelixDialectic = (opts.enableCrossHelixDialectic !== false && !opts.meditationMode)
    ? new CrossHelixDialectic(log)
    : undefined

  // Create TopologyGraph + BrainstemBridge (if embedding service provided)

  let topologyGraph: TopologyGraph | undefined
  let brainstemBridge: BrainstemBridge | undefined

  // Skip topology/gravity engine in meditation — no multi-branch spatial coordination needed
  if (opts.embeddingService && !opts.meditationMode) {
    brainstemBridge = new BrainstemBridge({
      tree: corpusTree,
      logger,
      injectGuidance: (helixId, content, urgency) => {
        // Deferred — Corpus registers brainstems dynamically, so use the Corpus
        // directive path which buffers until the brainstem is available.
        const rh = runningHelixes.get(helixId)
        if (rh?.brainstem) {
          try {
            (rh.brainstem as any).pushGuidance?.({ content, urgency, source: 'topology-bridge' })
          } catch {
            (rh.brainstem as any).onCorpusDirective?.({
              targetHelixId: helixId,
              type: 'context-inject' as any,
              urgency,
              reason: 'Topology bridge context injection',
              text: content,
              timestamp: Date.now(),
            })
          }
        }
      },
      getBrainstemState: (helixId) => {
        const rh = runningHelixes.get(helixId)
        if (!rh?.brainstem) return undefined
        const bs = rh.brainstem as any
        return {
          getCognitiveModel: () => bs.state?.cognitiveModel ?? { allDiscoveries: [], allDecisions: [], currentNextSteps: [], recentOutputs: [], pendingBlockers: [] },
          getQualityTrajectory: () => bs.state?.qualityTrajectory ?? [],
          getBlackboard: () => bs.deps?.blackboard,
        }
      },
    })

    topologyGraph = new TopologyGraph({
      embeddingService: opts.embeddingService,
      logger,
      eventBus,
      bridge: brainstemBridge,
      persistEvent: constellationStore
        ? (type, entity, message, data) => {
            try {
              constellationStore.appendEvent(constellationId, type, entity, message, data)
            } catch (err) {
              log.warn('Topology event persistence failed', { type, error: String(err) })
            }
          }
        : undefined,
    })
    topologyGraph.setConstellationId(constellationId)

    log.info('Topology Graph initialized', { constellationId })
  }

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
      meditationMode: opts.meditationMode,
      meditationStyle: opts.meditationStyle,
      miniHelixActive: !!opts.useMiniHelixCorpus,
      mnemicField: opts.mnemicField,
      memory: opts.memory,
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


      launchHelix: async (helixGoal, helixContext, tmpl) => {
        const rh = await launchHelix(helixGoal, helixContext, undefined, 0)
        return rh.helixId
      },

      pauseHelix: (helixId) => {
        const rh = runningHelixes.get(helixId)
        if (rh?.brainstem) {
          // Brainstem's mini-helix can be paused
          try {
            (rh.brainstem as any).pause?.()
            return true
          } catch { return false }
        }
        return false
      },

      resumeHelix: (helixId) => {
        const rh = runningHelixes.get(helixId)
        if (rh?.brainstem) {
          try {
            (rh.brainstem as any).resume?.()
          } catch { /* best effort */ }
        }
      },

      killHelix: (helixId) => {
        const rh = runningHelixes.get(helixId)
        if (rh?.cancel) {
          rh.cancel()
          log.info('Helix killed by Corpus', { helixId })
        }
      },

      injectGuidance: (helixId, content, urgency) => {
        const rh = runningHelixes.get(helixId)
        if (rh?.brainstem) {
          // Push directly to the Brainstem's guidance queue
          try {
            (rh.brainstem as any).pushGuidance?.({ content, urgency, source: 'corpus-direct' })
          } catch {
            // Fall back to corpus directive
            (rh.brainstem as any).onCorpusDirective?.({
              targetHelixId: helixId,
              type: 'guidance' as any,
              urgency,
              reason: 'Direct injection from Corpus',
              text: content,
              timestamp: Date.now(),
            })
          }
        }
      },

      runCommand: async (command, timeoutMs = 30_000) => {
        const { execSync } = await import('child_process')
        try {
          const stdout = execSync(command, {
            timeout: timeoutMs,
            encoding: 'utf-8',
            maxBuffer: 1024 * 1024,
            cwd: process.cwd(),
          })
          return { exitCode: 0, stdout, stderr: '' }
        } catch (err: any) {
          return {
            exitCode: err.status ?? 1,
            stdout: err.stdout ?? '',
            stderr: err.stderr ?? '',
          }
        }
      },

      getHelixTemplate: (helixId) => {
        const rh = runningHelixes.get(helixId)
        return rh?.template
      },

      // Persist Corpus events to ConstellationStore for audit trail
      persistEvent: constellationStore
        ? (type, entity, message, data) => {
            try {
              constellationStore.appendEvent(constellationId, type, entity, message, data)
            } catch (err) {
              log.warn('Corpus event persistence failed', { type, error: String(err) })
            }
          }
        : undefined,

      topology: topologyGraph,
      store: constellationStore,
    },
    {
      maxBranches: maxHelixes,
      maxDepth,
    }
  )

  await corpus.start()
  log.info('Corpus started')

  // Corpus Mini-Helix (optional — self-driving analysis loop)

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
        meditationMode: opts.meditationMode,
        meditationStyle: opts.meditationStyle,
        mnemicField: opts.mnemicField,
        memory: opts.memory,
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

    if (opts.meditationMode) {
      // Fire-and-forget — meditation Corpus observes as branches come online
      corpusMiniHelix.start().catch((err) => {
        log.warn('Corpus mini-Helix failed in meditation mode', { error: String(err) })
      })
      log.info('Corpus mini-Helix started (background, meditation)')
    } else {
      await corpusMiniHelix.start()
      log.info('Corpus mini-Helix started')
    }
  }

  if (opts.onCorpusReady) {
    const liveState: ConstellationLiveState = {
      constellationId,
      goal,
      getTree: () => corpusTree,
      getTreeSnapshot: () => corpusTree.getSnapshot(),
      getCrossPatterns: () => corpus.getResult().crossPatterns,
      getInterventions: () => corpus.getResult().interventions,
      getBranchAssessments: () => corpus.getResult().branchAssessments,
      getTopologySnapshot: topologyGraph?.enabled
        ? () => topologyGraph!.getSnapshot()
        : undefined,

      // External Corpus Protocol — delegate to Corpus instance
      corpus: {
        assume: (agentId, heartbeatTimeoutMs) => corpus.assume(agentId, heartbeatTimeoutMs),
        release: (reason) => corpus.release(reason),
        isExternallyAssumed: () => corpus.isExternallyAssumed(),
        getExternalState: () => corpus.getExternalState(),
        getExternalSnapshot: () => corpus.getExternalSnapshot(),
        getLocusSnapshot: () => corpus.getLocusSnapshot(),
        getLocusMemories: () => corpus.getLocusMemories(),
        externalDirective: (directive) => corpus.externalDirective(directive),
        externalSpawnDecide: (requestId, approved, reason, modifiedGoal) =>
          corpus.externalSpawnDecide(requestId, approved, reason, modifiedGoal),
        externalSynthesis: (content, priority, tags) =>
          corpus.externalSynthesis(content, priority, tags),
      },
    }
    opts.onCorpusReady(liveState)
    log.debug('onCorpusReady callback invoked')
  }

  // State Tracking

  const nodes = new Map<string, ConstellationNode>()
  const runningHelixes = new Map<string, RunningHelix>()
  const spawnQueue: SpawnRequest[] = []
  const blackboardBridges = new Map<string, BlackboardBridge>()
  // WHY: Track ALL brainstem mini-helixes separately because runningHelixes
  // deletes entries when branches complete, losing the reference needed to
  // stop the mini-helix. Without this, mini-helixes become zombies after
  // the constellation finishes.
  const allBrainstemMiniHelixes = new Map<string, BrainstemMiniHelix>()
  let rootHelixId: string | undefined
  let completed = false
  let tracker: DecompositionTracker | undefined
  // WHY: Maps helixId -> feedbackId so we can close the feedback loop
  // when the branch completes and we know which files were actually used.
  const contextFeedbackIds = new Map<string, string>()

  // Helper: Resolve Postures

  function resolvePostures(): FlexPosture[] {
    if (customPostures && customPostures.length > 0) {
      log.info('Using custom postures', { count: customPostures.length })
      return customPostures
    }
    log.info('Using template postures', { template })
    return getTemplatePostures(template)
  }

  // WHY: costEffective mode downgrades each posture's model tier to a cheaper
  // alternative. The mapping preserves relative ordering: expensive tiers drop
  // one level, cheap tiers stay the same. qwenPlus is the floor — it does NOT
  // downgrade to minimax because meditation runs (which use qwenPlus) must stay
  // on alibaba-coding even in cost-effective mode.
  const COST_EFFECTIVE_TIER_MAP: Record<string, string> = {
    opus:     'kimi',
    sonnet:   'kimi',
    qwenMax:  'qwenPlus',
    kimi:     'qwenPlus',
    glm:      'qwenPlus',
    qwenPlus: 'qwenPlus',
    minimax:  'qwenPlus',
    background: 'qwenPlus',
  }

  // HOW: Default tier per energy when posture has no modelTier set.
  // 'performance' and 'balanced' are legacy fallback chain template names
  // used by the model pool — these are the actual RoutingTier equivalents.
  const ENERGY_DEFAULT_TIER: Record<string, string> = {
    unity: 'qwenPlus',
    yang:  'glm',
    yin:   'kimi',
  }

  function resolveTier(posture: FlexPosture): string {
    const energyDefault = posture.energy ? ENERGY_DEFAULT_TIER[posture.energy] : undefined
    const baseTier = posture.capabilities?.modelTier ?? energyDefault ?? 'kimi'
    if (!costEffective) return baseTier
    return COST_EFFECTIVE_TIER_MAP[baseTier] ?? baseTier
  }

  // Helper: Launch Helix

  async function launchHelix(
    helixGoal: string,
    helixContext: string | undefined,
    parentId: string | undefined,
    depth: number,
    toolFilter?: { allow?: string[]; deny?: string[] }
  ): Promise<RunningHelix> {
    const helixId = constellationStore?.nextHelixId(constellationId)
      ?? `${constellationId}-helix-${helixCounter++}`
    const helixLog = log.child(helixId)

    helixLog.info('Launching Helix', {
      parentId,
      depth,
      goal: helixGoal.slice(0, 100),
    })

    // WHY: cross-run memory continuity improves branch output quality
    let enrichedContext = helixContext

    // Memory injection runs in all modes — it's the only context meditation agents receive
    if (memoryInjectionService) {
      try {
        const memoryContext = await memoryInjectionService.injectForBranch(helixId, helixGoal, parentId)
        if (memoryContext && memoryContext.memories.length > 0) {
          const memoryBlock = memoryInjectionService.formatMemoriesForContext(memoryContext)
          enrichedContext = helixContext ? `${helixContext}\n${memoryBlock}` : memoryBlock
          helixLog.info('Memory context injected for branch', {
            memories: memoryContext.memories.length,
            searchQuery: memoryContext.searchQuery,
          })
        }
      } catch (err) {
        helixLog.warn('Memory injection failed for branch', { error: String(err) })
      }
    }

    // Meditation mode: strip all other context. The agents explore in solitude —
    // no workspace, no codebase, no patterns, no reasoning bank.
    let branchWorkingDir: string | undefined
    if (!opts.meditationMode) {

    // Create worktree for branch isolation (if enabled)
    if (worktreeIsolation) {
      try {
        branchWorkingDir = await worktreeIsolation.createBranchWorktree(helixId)
        if (branchWorkingDir !== (opts.projectRoot ?? process.cwd())) {
          // Add isolation notice to context
          const notice = worktreeIsolation.getIsolationNotice(helixId)
          if (notice) {
            enrichedContext = enrichedContext ? `${enrichedContext}\n\n${notice}` : notice
          }
        }
      } catch (err) {
        helixLog.warn('Worktree creation failed, using shared project root', { error: String(err) })
      }
    }

    // HOW: Inject top-level project structure so agents know what directories
    // exist without wasting tool calls on find/ls at the start of every branch.
    const effectiveRoot = branchWorkingDir ?? opts.projectRoot ?? process.cwd()
    try {
      const { readdirSync } = await import('node:fs')
      const entries = readdirSync(effectiveRoot, { withFileTypes: true })
      const listing = entries
        .filter(e => !e.name.startsWith('.') && e.name !== 'node_modules' && e.name !== 'dist')
        .map(e => e.isDirectory() ? `  ${e.name}/` : `  ${e.name}`)
        .join('\n')
      if (listing) {
        const wsBlock = `## Workspace Structure\nProject root: ${effectiveRoot}\n${listing}`
        enrichedContext = enrichedContext ? `${enrichedContext}\n\n${wsBlock}` : wsBlock
      }
    } catch {
      // best-effort — don't block launch on directory read failure
    }

    // WHY: Inject pre-assembled codebase context so branches start with knowledge
    // of relevant files, symbols, and execution flows — not just a goal string.
    // This is the same context the decomposer used to plan the work.
    if (opts.codebaseContext) {
      const codeCtxBlock = `## Codebase Context\n${opts.codebaseContext}`
      enrichedContext = enrichedContext ? `${enrichedContext}\n\n${codeCtxBlock}` : codeCtxBlock
      helixLog.info('Codebase context injected for branch', {
        contextLength: opts.codebaseContext.length,
      })

      // WHY: Record this context injection so we can track whether it helped.
      // The feedback loop closes at node completion when filesModified is known.
      if (opts.contextFeedback) {
        try {
          // HOW: Score the goal's specificity using the adaptive scorer.
          // When enough feedback data exists, the Bayesian model may recommend
          // a different context mode than the hardcoded thresholds.
          const specificity = scoreSpecificity(helixGoal, opts.contextFeedback)

          // HOW: Extract file paths from the codebase context string (lines like "1. path/to/file.ts")
          const filePattern = /\d+\.\s+(\S+\.(?:ts|js|tsx|jsx|py|rs|go))/g
          const suggestedFiles: string[] = []
          let match: RegExpExecArray | null
          while ((match = filePattern.exec(opts.codebaseContext)) !== null) {
            suggestedFiles.push(match[1])
          }

          if (suggestedFiles.length > 0) {
            const feedbackId = opts.contextFeedback.recordInjection(
              helixId,
              helixGoal,
              specificity.score,
              specificity.mode,
              suggestedFiles,
            )
            contextFeedbackIds.set(helixId, feedbackId)

            if (specificity.adaptiveOverride) {
              helixLog.info('Adaptive context mode override active', {
                originalMode: specificity.adaptiveOverride.originalMode,
                adaptiveMode: specificity.mode,
                confidence: specificity.adaptiveOverride.confidence,
                reason: specificity.adaptiveOverride.reason,
              })
            }
          }
        } catch (err) {
          helixLog.warn('Failed to record context feedback injection', { error: String(err) })
        }
      }
    }

    // WHY: Inject relevant past reasoning traces so branches can learn from
    // successful approaches in previous Constellation runs.
    if (opts.reasoningBank) {
      try {
        const reasoningCtx = opts.reasoningBank.retrieveForBranch(helixGoal)
        if (reasoningCtx) {
          enrichedContext = enrichedContext ? `${enrichedContext}\n\n${reasoningCtx}` : reasoningCtx
          helixLog.info('Reasoning bank context injected for branch')
        }
      } catch (err) {
        helixLog.warn('Reasoning bank retrieval failed', { error: String(err) })
      }
    }

    // This enables cross-branch knowledge transfer — successful approaches from
    // completed/struggling branches inform new branches' starting strategies.
    try {
      const elevatedPatterns = corpusTree.getElevatedPatterns()
      if (elevatedPatterns.length > 0) {
        // HOW: Filter patterns relevant to this branch's goal (keyword matching)
        const goalKeywords = helixGoal.toLowerCase().split(/\s+/).filter(w => w.length > 3)
        const relevantPatterns = elevatedPatterns.filter(pattern => {
          const patternText = `${pattern.applicableContext} ${pattern.approach}`.toLowerCase()
          return goalKeywords.some(keyword => patternText.includes(keyword))
        })

        if (relevantPatterns.length > 0) {
          const patternsBlock = relevantPatterns
            .map(p => `- [${p.approach}] (score: ${p.achievedScore.toFixed(2)}): ${p.applicableContext}`)
            .join('\n')
          const patternsContext = `\n\n## Constellation Knowledge\nSuccessful patterns from peer sessions:\n${patternsBlock}`
          enrichedContext = enrichedContext ? `${enrichedContext}${patternsContext}` : patternsContext
          helixLog.info('Elevated patterns injected for branch', {
            patterns: relevantPatterns.length,
            totalPatterns: elevatedPatterns.length,
          })
        }
      }
    } catch (err) {
      helixLog.warn('Elevated pattern injection failed', { error: String(err) })
      // Continue with existing context — don't block launch
    }

    } // end of !meditationMode guard

    corpusTree.registerBranch(helixId, helixGoal, depth, parentId)

    // WHY: Register a per-branch guidance provider so that collect_thoughts
    // (called by this branch's posture runners) can query the Corpus for
    // elevated patterns and cross-branch awareness during mid-reasoning.
    if (opts.guidanceRegistry) {
      const branchGuidanceProvider = createConstellationGuidanceProvider({
        corpusTree,
        helixId,
        branchGoal: helixGoal,
        logger: helixLog,
      })
      opts.guidanceRegistry.register(helixId, branchGuidanceProvider)
      helixLog.debug('Guidance provider registered for branch')
    }

    // Register with topology — initial digest so the gravity engine knows about this Helix
    if (topologyGraph?.enabled) {
      const initialDigest = {
        helixId,
        goalSummary: helixGoal,
        approach: 'exploration' as const,
        progress: 0,
        filesActive: [],
        keyFindings: [],
        blockers: [],
        currentStrategy: 'Starting',
        rollingScore: 0.5,
        workUnitsProcessed: 0,
        updatedAt: Date.now(),
      }
      topologyGraph.registerHelix(helixId, initialDigest).catch((err) => {
        helixLog.warn('Topology registration failed', { error: String(err) })
      })
    }

    // Persist branch creation to ConstellationStore
    if (constellationStore) {
      try {
        constellationStore.addBranch(constellationId, helixId, helixGoal, depth, {
          helixSessionId: helixId,
          parentHelixId: parentId,
        })
        constellationStore.recordBranchLifecycleEvent(constellationId, helixId, {
          eventType: 'created',
          context: { goal: helixGoal.slice(0, 200), depth, parentId },
        })
      } catch (err) {
        helixLog.warn('Failed to persist branch creation', { error: String(err) })
      }
    }

    const node: ConstellationNode = {
       helixId,
       config: {
         goal: helixGoal,
         context: enrichedContext,
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

    const postures = resolvePostures()
    const handles: ModelHandle[] = []

    try {
      // HOW: Acquire handles for each posture that needs one.
      // Tier is derived from posture capability metadata, with cost-effective
      // downgrading applied when the flag is set.
      const unityPosture = postures.find(p => p.energy === 'unity') ?? postures[0]
      const yangPosture = postures.find(p => p.energy === 'yang') ?? postures[1]
      const yinPosture = postures.find(p => p.energy === 'yin') ?? postures[2]

      const unityHandle = await handleFactory({
        tier: resolveTier(unityPosture),
        purpose: 'unity',
        sessionId: helixId,
      })
      handles.push(unityHandle)

      const yangHandle = await handleFactory({
        tier: resolveTier(yangPosture ?? unityPosture),
        purpose: 'yang',
        sessionId: helixId,
      })
      handles.push(yangHandle)

      const yinHandle = await handleFactory({
        tier: resolveTier(yinPosture ?? unityPosture),
        purpose: 'yin',
        sessionId: helixId,
      })
      handles.push(yinHandle)

      if (costEffective) {
        helixLog.info('Cost-effective mode active', {
          unity: resolveTier(unityPosture),
          yang: resolveTier(yangPosture ?? unityPosture),
          yin: resolveTier(yinPosture ?? unityPosture),
        })
      }

      // WHY: additional posture handles deferred — see contributing-todos blackboard
      // For now, we use the three main handles for all postures
    } catch (err) {
      helixLog.error('Failed to acquire model handles', { error: String(err) })
      node.status = 'failed'
      corpusTree.closeBranch(helixId, 'failed')
      topologyGraph?.deregisterHelix(helixId)
      onNodeCompleted?.(node)
      throw err
    }

    // HOW: Create Brainstem deps with corpus tree integration
    // WHY: The actual Brainstem instance is created and started inside runHelixPipeline.
    // We capture it via the onBrainstemCreated callback for Corpus registration.
    //
    // WHY: The sharedTree reader provides each Brainstem with read/write access to
    // the Shared Thought Tree for stigmergic self-organization.
    const sharedTreeReader = createSharedTreeReaderForHelix(helixId, corpusTree)

    // HOW: When topology is active, intercept digest updates to drive
    // the gravity engine. The topology tick is async (embedding computation)
    // but we fire-and-forget to avoid blocking the Brainstem loop.
    if (topologyGraph?.enabled) {
      const originalUpdateDigest = sharedTreeReader.updateDigest
      sharedTreeReader.updateDigest = (digest) => {
        originalUpdateDigest(digest)
        // Fire-and-forget — topology tick runs in background
        topologyGraph!.onDigestUpdate(helixId, digest).catch((err) => {
          helixLog.warn('Topology digest update failed', { error: String(err) })
        })
      }
    }

    // Meditation mode: skip Brainstem entirely — the Corpus reads raw posture output.
    // WorkUnits are pushed directly to the CorpusTree as pass-through annotations.
    const brainstemDeps: BrainstemDeps | undefined = opts.meditationMode
      ? undefined
      : {
          llm: brainstemLLM,
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

    // HOW: The actual brainstem reference — set by onBrainstemCreated when the pipeline starts it
    let activeBrainstem: HelixBrainstem | undefined

    let cancelFn: (() => void) | undefined
    const cancelPromise = new Promise<never>((_, reject) => {
      cancelFn = () => reject(new Error('Helix cancelled'))
    })

    // No timeout — Constellation manages lifecycle through Corpus coordination
    // and external cancellation, not arbitrary time limits.
    // WHY: Reviewers (Yang/Yin) don't need full file assignments or bulky context.
    // Trim to the goal + first section of context to save reviewer token budget.
    const REVIEWER_CONTEXT_LIMIT = 4000
    const reviewerCtx = enrichedContext && enrichedContext.length > REVIEWER_CONTEXT_LIMIT
      ? enrichedContext.slice(0, REVIEWER_CONTEXT_LIMIT) + '\n\n[Context trimmed for reviewer — full context available to Unity worker]'
      : enrichedContext

    const helixPromise = runHelixPipeline({
      goal: helixGoal,
      context: enrichedContext,
      reviewerContext: reviewerCtx,
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
      // WHY: When running in a worktree, all tool execution uses the branch's working directory
      workingDir: branchWorkingDir,
      // WHY: Pass tool filter from Constellation config to restrict tools for this branch
      toolFilter,
      // WHY: Constellation Helixes run longer tool-call chains (drone scouts, file reads, etc.)
      // Relax inactivity thresholds: warn=5min, escalate=10min, kill=15min
      inactivityThresholds: {
        warnMs: 300_000,
        escalateMs: 600_000,
        killMs: 900_000,
      },
      onWorkUnit: (wu, iteration) => {
        if (opts.meditationMode) {
          // Meditation: push raw posture context directly to the CorpusTree.
          // No Brainstem filtering — the Corpus sees the full reasoning and tool calls.
          const toolSummary = wu.toolCalls.map(tc => `${tc.name}(${JSON.stringify(tc.input).slice(0, 200)})`).join(', ')
          const resultSummary = wu.toolResults.map(tr => tr.content.slice(0, 300)).join('\n')
          const rawAnnotation: BrainstemAnnotation = {
            workUnitId: wu.id,
            score: 0,
            annotation: 'exploration' as any,
            synthesis: '',
            pattern: 'none' as any,
            guidance: null,
            guidanceUrgency: 'low' as any,
            trainingNote: '',
            axonStep: iteration,
            timestamp: wu.timestamp,
            goalAlignment: 0,
            novelty: 0,
            progress: 0,
            discoveries: wu.reasoning ? [wu.reasoning] : [],
            decisions: [],
            hypothesis: '',
            outputs: toolSummary ? [toolSummary] : [],
            blockers: [],
            nextSteps: [],
            knowledgeDelta: resultSummary,
          }
          const toolCalls = wu.toolCalls.map(tc => ({ name: tc.name, args: JSON.stringify(tc.input).slice(0, 500) }))
          corpusTree.pushAnnotation(helixId, rawAnnotation, toolCalls)
        } else if (activeBrainstem) {
          activeBrainstem.onWorkUnit(wu, iteration)
        }
      },
      onBlackboardCreated: (childBlackboard) => {
        // Skip bridge in meditation — no cross-branch governance infrastructure to feed
        if (opts.meditationMode) return

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
        if (cancelFn) {
          const originalCancel = cancelFn
          cancelFn = () => {
            originalCancel()
            fn()
          }
        }
      },
      onBrainstemCreated: (bs) => {
        // HOW: Capture the pipeline's brainstem (which is started and has its runLoop active)
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
        // WHY: Meditation mode skips Brainstem entirely — the Corpus reads raw posture
        // output directly via the onWorkUnit pass-through above.
        if (opts.useMiniHelixBrainstem && !opts.meditationMode) {
          // WHY: Brainstem needs the tool list to generate valid tool_use blocks
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

          if (corpusMiniHelix) {
            corpusMiniHelix.registerBrainstem(helixId, { onCorpusDirective: (d) => brainstemMH.onCorpusDirective(d) })
          }

          const rhForMH = runningHelixes.get(helixId)
          if (rhForMH) rhForMH.brainstemMiniHelix = brainstemMH
          allBrainstemMiniHelixes.set(helixId, brainstemMH)

          brainstemMH.start().catch((err) => {
            helixLog.error('Brainstem mini-Helix failed to start', { error: String(err) })
          })
        }
      },
    })

    // Race between completion and cancellation
    // WHY: Do NOT chain .finally() here — node.status is set in the .then()/.catch()
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
      template,
    }

    runningHelixes.set(helixId, runningHelix)

    // WHY: Wake the Corpus immediately so it can observe and assess the new
    // branch within ~50ms instead of waiting up to 10s for the next poll cycle.
    corpus.wake()

    promise
      .then(async (result) => {
        const isDegraded = result.completionStatus.degraded
        // WHY: A cancelled Helix that still produced output (has unity conclusion
        // and token usage) was interrupted by redecomposition, not a hard failure.
        // Treating these as 'degraded' instead of 'failed' gives accurate stats —
        // the branch did useful work that successor branches can build on.
        const wasCancelled = !result.completionStatus.complete
        const producedOutput = !!(result.unityConclusion && result.tokensUsed &&
          ((result.tokensUsed.unity ?? 0) + (result.tokensUsed.yang ?? 0) + (result.tokensUsed.yin ?? 0) > 0))
        const cancelledWithOutput = wasCancelled && producedOutput

        helixLog.info('Helix completed', {
          completionStatus: result.completionStatus,
          degraded: isDegraded,
          cancelledWithOutput,
          durationMs: Date.now() - (node.startedAt ?? Date.now()),
        })

        if (isDegraded) {
          helixLog.warn('Helix completed in degraded state (one or more postures errored)', {
            unityStatus: result.completionStatus.unityStatus,
            yangStatus: result.completionStatus.yangStatus,
            yinStatus: result.completionStatus.yinStatus,
          })
        }

        if (cancelledWithOutput) {
          node.status = 'degraded'
        } else {
          node.status = result.completionStatus.complete ? (isDegraded ? 'degraded' : 'completed') : 'failed'
        }
        node.completedAt = Date.now()

        // Track task completion (tracker is defined later in the function)
        // It will be available when this promise resolves for decomposed tasks
        if (typeof tracker !== 'undefined') {
          const trackedTask = tracker.getTaskByHelixId(helixId)
          if (trackedTask) {
            if (node.status === 'completed' || node.status === 'degraded') {
              tracker.completeTask(trackedTask.id, result.unityConclusion?.slice(0, 500))
            } else {
              tracker.failTask(trackedTask.id, 'Helix failed')
            }
          }
        }

        // Populate tokensUsed from HelixResult
        const tu = result.tokensUsed
        node.tokensUsed = (tu.unity ?? 0) + (tu.yang ?? 0) + (tu.yin ?? 0) + (tu.mentor ?? 0)

        // Populate postureResults from HelixResult
        const ic = result.iterationCounts ?? { unity: 0, yang: 0, yin: 0, mentor: 0 }
        const tc = result.toolCallCounts ?? { unity: 0, yang: 0, yin: 0, mentor: 0 }
        const nodeStart = node.startedAt ?? Date.now()
        const dur = Date.now() - nodeStart

        node.postureResults.set('unity', {
          name: 'unity',
          conclusion: result.unityConclusion ?? '',
          confidence: result.unityConfidence ?? 0,
          keyPoints: result.unityKeyPoints ?? [],
          iterationCount: ic.unity,
          toolCallCount: tc.unity,
          tokensUsed: tu.unity ?? 0,
          durationMs: dur,
        })
        node.postureResults.set('yang', {
          name: 'yang',
          conclusion: result.yangConclusion ?? '',
          confidence: result.yangConfidence ?? 0,
          keyPoints: result.yangKeyPoints ?? [],
          iterationCount: ic.yang,
          toolCallCount: tc.yang,
          tokensUsed: tu.yang ?? 0,
          durationMs: dur,
        })
        node.postureResults.set('yin', {
          name: 'yin',
          conclusion: result.yinConclusion ?? '',
          confidence: result.yinConfidence ?? 0,
          keyPoints: result.yinKeyPoints ?? [],
          iterationCount: ic.yin,
          toolCallCount: tc.yin,
          tokensUsed: tu.yin ?? 0,
          durationMs: dur,
        })

        onNodeCompleted?.(node)

        // WHY: Ingest successful reasoning traces for future branch reuse.
        // Only ingest when the node completed successfully and has meaningful output.
        if (opts.reasoningBank && (node.status === 'completed' || node.status === 'degraded')) {
          try {
            const qualityScore = result.qualityScore
              ?? (result.brainstem?.averageScore)
              ?? 0.5
            const approach = result.unityConclusion?.slice(0, 200) || 'unknown approach'
            const content = [
              result.unityConclusion,
              result.convergencePoints?.map(cp => `${cp.topic}: ${cp.resolution}`).join('; '),
            ].filter(Boolean).join('\n\n')

            if (content.length > 50) {
              opts.reasoningBank.store({
                sourceHelixId: helixId,
                goal: node.config.goal,
                approach,
                content,
                qualityScore,
                succeeded: node.status === 'completed',
                relevantFiles: result.filesModified?.map(f => f.path),
              })
            }
          } catch (err) {
            helixLog.warn('Failed to ingest reasoning trace', { error: String(err) })
          }
        }

        // WHY: Close the context feedback loop — compare files suggested by
        // prepareContext against files actually modified by the branch.
        // This trains the Bayesian model for future context assembly decisions.
        const feedbackId = contextFeedbackIds.get(helixId)
        if (feedbackId && opts.contextFeedback) {
          try {
            const filesUsed = result.filesModified?.map(f => f.path) ?? []
            opts.contextFeedback.recordUsage(feedbackId, filesUsed)
            contextFeedbackIds.delete(helixId)
            helixLog.info('Context feedback recorded', {
              filesUsed: filesUsed.length,
            })
          } catch (err) {
            helixLog.warn('Failed to record context feedback usage', { error: String(err) })
          }
        }

        // Merge worktree changes back to main branch (if isolated)
        if (worktreeIsolation?.isIsolated(helixId)) {
          const skipMerge = node.status === 'failed'
          const mergeResult = await worktreeIsolation.completeBranch(helixId, { skipMerge })
          if (mergeResult.hasConflicts) {
            helixLog.warn('Worktree merge had conflicts', {
              conflictingFiles: mergeResult.conflictingFiles,
            })
          } else if (mergeResult.merged && mergeResult.filesChanged > 0) {
            helixLog.info('Worktree changes merged', {
              filesChanged: mergeResult.filesChanged,
              mergeCommit: mergeResult.mergeCommit,
            })
          }
        }
      })
      .catch((err) => {
        helixLog.error('Helix failed', { error: String(err) })
        node.status = 'failed'
        node.completedAt = Date.now()

        // WHY: Recover partial token stats from the Helix store so failed/cancelled
        // branches report actual work done instead of 0. The .then() path populates
        // this from HelixResult, but cancellation rejects before that runs.
        if (store) {
          try {
            const session = store.getSession(helixId)
            if (session) {
              node.tokensUsed = (session.tokensUnity ?? 0) + (session.tokensYang ?? 0) + (session.tokensYin ?? 0)
            }
          } catch (storeErr) {
            helixLog.warn('Failed to recover partial stats from Helix store', { error: String(storeErr) })
          }
        }

        onNodeCompleted?.(node)
      })
      .finally(async () => {
        // HOW: Close branch in corpus tree — node.status is now correct after .then()/.catch()
        // Corpus tree only knows 'completed' | 'failed', so degraded maps to 'completed' there
        const branchStatus = (node.status === 'completed' || node.status === 'degraded') ? 'completed' : 'failed'
        corpusTree.closeBranch(helixId, branchStatus)
        topologyGraph?.deregisterHelix(helixId)
        crossHelixDialectic?.unregisterBranch(helixId)
        opts.guidanceRegistry?.unregister(helixId)

        // Cleanup worktree if not already cleaned up by the merge step
        if (worktreeIsolation?.isIsolated(helixId)) {
          await worktreeIsolation.completeBranch(helixId, { skipMerge: true })
        }

        // Persist branch completion to ConstellationStore
        if (constellationStore) {
          try {
            constellationStore.updateBranch(constellationId, helixId, {
              status: branchStatus,
              completed: true,
            })
            constellationStore.recordBranchLifecycleEvent(constellationId, helixId, {
              eventType: node.status === 'degraded' ? 'degraded' : branchStatus,
              metrics: { tokensUsed: node.tokensUsed, durationMs: node.completedAt ? node.completedAt - (node.startedAt ?? 0) : 0 },
            })
          } catch (err) {
            helixLog.warn('Failed to persist branch completion', { error: String(err) })
          }
        }

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

  // Helper: Notify a Helix that its spawn request was rejected

  function notifySpawnRejection(helixId: string, reason: string): void {
    const rh = runningHelixes.get(helixId)
    if (!rh?.brainstem) return
    try {
      const guidance: import('../helix/brainstem-types.js').PendingGuidance = {
        text: reason,
        urgency: 'medium',
        fromStep: 0,
        triggeredBy: 'none',
        timestamp: Date.now(),
      }
      ;(rh.brainstem as any).guidanceQueue?.push(guidance)
    } catch {
      // Best effort — don't crash on notification failure
    }
  }

  // Helper: Handle Spawn Request

  async function handleSpawnRequest(request: SpawnRequest): Promise<void> {
    log.info('Processing spawn request', {
      requestId: request.requestId,
      requestingHelixId: request.requestingHelixId,
      goal: request.goal.slice(0, 100),
    })

    if (runningHelixes.size >= maxHelixes) {
      log.warn('Max Helixes reached, rejecting spawn request', {
        requestId: request.requestId,
        current: runningHelixes.size,
        max: maxHelixes,
      })
      notifySpawnRejection(request.requestingHelixId, `Spawn request rejected: max Helixes (${maxHelixes}) reached. Complete your current task without spawning.`)
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
      notifySpawnRejection(request.requestingHelixId, `Spawn request rejected: max depth (${maxDepth}) reached. Handle the sub-task inline instead of spawning.`)
      return
    }

    const decision = await corpus.evaluateSpawnRequest(request)

    if (!decision.approved) {
      log.info('Spawn request rejected by Corpus', {
        requestId: request.requestId,
        reason: decision.reason,
      })
      notifySpawnRejection(request.requestingHelixId, `Spawn request rejected by Corpus: ${decision.reason}. Continue with your current approach.`)
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

  // Helper: Poll for Spawn Requests

  async function pollSpawnRequests(): Promise<void> {
    // WHY: spawn request polling deferred — see contributing-todos blackboard
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

  // Main Execution

  let result: ConstellationResult
  let checkpointHandle: ReturnType<typeof setInterval> | undefined

  try {
    // Set up external cancel mechanism
    let externalCancel: () => void = () => {}
    const cancelPromise = new Promise<never>((_, reject) => {
      externalCancel = () => {
        log.info('Constellation cancelled externally')

        // Save a final checkpoint before cancelling so we don't lose progress
        if (constellationStore) {
          try {
            const nodeArr = Array.from(nodes.values())
            constellationStore.saveCheckpoint(constellationId, {
              tree: enrichTreeWithTopology(corpusTree.getSnapshot(), topologyGraph),
              progress: {
                markdown: `Cancelled: ${nodeArr.length} nodes at cancellation time`,
                data: {
                  activeBranches: nodeArr.filter(n => n.status === 'running').length,
                  totalBranches: nodeArr.length,
                  completedBranches: nodeArr.filter(n => n.status === 'completed').length,
                  failedBranches: nodeArr.filter(n => n.status === 'failed').length,
                  sweepCount: corpus.getResult().sweepCount,
                  lastSweepAt: Date.now(),
                },
              },
              totalBranches: nodeArr.length,
              tokensUsed: nodeArr.reduce((sum, n) => sum + n.tokensUsed, 0),
            })
            log.info('Final checkpoint saved before cancellation')
          } catch (err) {
            log.warn('Failed to save final checkpoint on cancel', { error: String(err) })
          }
        }

        for (const running of runningHelixes.values()) {
          try { running.cancel() } catch (_e) { /* best effort */ }
        }
        reject(new Error('Constellation cancelled'))
      }
    })
    opts.onCancelRegistered?.(externalCancel)

    if (constellationStore) {
      try {
        constellationStore.appendEvent(constellationId, 'constellation:started', null,
          `Constellation started with template=${template}`, { goal: goal.slice(0, 200), template })
      } catch (err) {
        log.warn('Failed to persist start event', { error: String(err) })
      }
    }

    // WHY: For complex goals, use fast decomposition with direct LLM call.
    // For simple goals, skip decomposition overhead.
    const decision: DecompositionDecision = shouldDecompose(goal, context, true)
    const decompositionMode = decision.mode
    let decomposition: GoalDecomposition

    if (decompositionMode === 'skip') {
      if (decision.vague) {
        log.warn('Goal appears vague — no specific targets, files, or modules detected. Consider providing more detail.', {
          goal: goal.slice(0, 200),
        })
      }
      log.info('Goal is simple, skipping decomposition')
      decomposition = {
        decomposed: false,
        originalGoal: goal,
        subTasks: [{ goal, priority: 1 }],
        strategy: 'parallel',
        durationMs: 0,
      }
    } else {
      decomposition = await fastDecompose({
        goal,
        context,
        llm: corpusLLM,
        log: log.child('decomposer'),
        memory: opts.memory,
        codebaseContext: decompositionMode === 'full' ? opts.codebaseContext : undefined,
      })
    }

    // Create tracker for task lifecycle management
    tracker = new DecompositionTracker(constellationId, decomposition, log.child('tracker'))

    // Write decomposition plan to audit trail
    if (opts.auditTrail) {
      try {
        opts.auditTrail.writeDecompositionPlan(
          constellationId,
          goal,
          decomposition.strategy,
          decomposition.subTasks.map(t => ({
            goal: t.goal,
            template: t.template,
            priority: t.priority,
          })),
        )
      } catch (err) {
        log.warn('Failed to write decomposition plan to audit trail', { error: String(err) })
      }
    }

    // WHY: Periodic checkpointing for crash recovery. The Corpus handles branch
    // lifecycle through per-branch budgets (BRANCH_BUDGET_DEFAULTS) and escalation
    // levels. No global step kill switch — that's a blunt instrument that undermines
    // the Corpus's ability to make informed pruning decisions.
    const CHECKPOINT_INTERVAL_MS = 30_000
    // HOW: Soft step budget — when reached, log a warning and emit a throttle
    // directive. The Corpus decides what to prune. Only external cancellation
    // (user action or constellation timeout) should force-kill branches.
    const softStepBudget = opts.maxTotalSteps ?? 200
    let softBudgetReached = false
    if (constellationStore && !opts.meditationMode) {
      checkpointHandle = setInterval(() => {
        try {
          const nodeArr = Array.from(nodes.values())
          const totalSteps = corpusTree.getSnapshot().branches.reduce(
            (sum, b) => sum + b.stepCount, 0
          )

          constellationStore.saveCheckpoint(constellationId, {
            tree: enrichTreeWithTopology(corpusTree.getSnapshot(), topologyGraph),
            progress: corpus.getProgressSnapshot(),
            sweepCount: corpus.getResult().sweepCount,
            totalBranches: nodeArr.length,
            completedBranches: nodeArr.filter((n) => n.status === 'completed').length,
            failedBranches: nodeArr.filter((n) => n.status === 'failed').length,
            tokensUsed: nodeArr.reduce((sum, n) => sum + n.tokensUsed, 0),
            durationMs: Date.now() - startTime,
          })
          log.info('Checkpoint saved', {
            constellationId,
            totalSteps,
            branches: nodeArr.length,
          })

          if (totalSteps >= softStepBudget && !softBudgetReached) {
            softBudgetReached = true
            log.warn('Soft step budget reached — notifying Corpus to prioritize completion', {
              totalSteps,
              softStepBudget,
              branches: nodeArr.length,
              activeBranches: nodeArr.filter(n => n.status !== 'completed' && n.status !== 'failed' && n.status !== 'degraded').length,
            })
            // WHY: Instead of killing branches, we log a warning. The Corpus's own
            // sweep cycle naturally handles budget pressure — it tracks step counts
            // and will throttle new spawns when the budget is tight.
            log.warn('Corpus notified: prioritize completion over new spawns')
          }
        } catch (err) {
          log.warn('Checkpoint save failed', { error: String(err) })
        }
      }, CHECKPOINT_INTERVAL_MS)

      // HOW: Fire first checkpoint after 10s (don't wait for the full interval)
      setTimeout(() => {
        if (!checkpointHandle) return
        try {
          const nodeArr = Array.from(nodes.values())
          constellationStore.saveCheckpoint(constellationId, {
            tree: enrichTreeWithTopology(corpusTree.getSnapshot(), topologyGraph),
            progress: corpus.getProgressSnapshot(),
            sweepCount: corpus.getResult().sweepCount,
            totalBranches: nodeArr.length,
            completedBranches: nodeArr.filter((n) => n.status === 'completed').length,
            failedBranches: nodeArr.filter((n) => n.status === 'failed').length,
            tokensUsed: nodeArr.reduce((sum, n) => sum + n.tokensUsed, 0),
            durationMs: Date.now() - startTime,
          })
          log.info('First checkpoint saved', { constellationId })
        } catch (_e) { /* best-effort */ }
      }, 10_000)
    }

    if (decomposition.decomposed && decomposition.subTasks.length > 1) {
      log.info('Goal decomposed into sub-tasks', {
        subTasks: decomposition.subTasks.length,
        strategy: decomposition.strategy,
        durationMs: decomposition.durationMs,
      })

      const helixPromises: Array<{ helixId: string; promise: Promise<HelixResult> }> = []
      const pendingTasks = tracker.getPendingTasks()
      
      for (const trackedTask of pendingTasks) {
        const subContext = [
          decomposition.sharedContext,
          trackedTask.originalTask.context,
          trackedTask.originalTask.relevantFiles?.length
            ? `Relevant files: ${trackedTask.originalTask.relevantFiles.join(', ')}`
            : undefined,
        ].filter(Boolean).join('\n\n')

        const h = await launchHelix(trackedTask.originalTask.goal, subContext || undefined, trackedTask.originalTask.template, 0)
        tracker.assignTask(trackedTask.id, h.helixId)
        tracker.startTask(trackedTask.id)
        helixPromises.push(h)
      }
      rootHelixId = helixPromises[0]?.helixId ?? ''

      const spawnPoller = pollSpawnRequests()

      log.info('Waiting for decomposed sub-task Helixes', { count: helixPromises.length })
      // WHY: Use allSettled so a single branch failure doesn't cascade-kill the
      // entire constellation. Individual branch failures are handled by the
      // .catch() handler on each promise. The Corpus manages lifecycle decisions.
      const settledPromise = Promise.allSettled(helixPromises.map(h => h.promise))
        .then((results) => {
          const fulfilled = results.filter(r => r.status === 'fulfilled').length
          const rejected = results.filter(r => r.status === 'rejected').length
          log.info('Decomposed Helixes settled', { fulfilled, rejected, total: results.length })
        })
      await Promise.race([settledPromise, cancelPromise])

      // WHY: After initial branches settle, wait for any spawned children
      // (from redecomposition or parallel acceleration) to finish
      if (runningHelixes.size > 0) {
        log.info('Waiting for spawned children to complete', { count: runningHelixes.size })
        const childGracePeriodMs = 120_000
        const childGrace = new Promise<void>((resolve) => setTimeout(resolve, childGracePeriodMs))
        const childPromises = Array.from(runningHelixes.values()).map((h) => h.promise)
        await Promise.race([
          Promise.allSettled(childPromises).then(() => {}),
          childGrace,
          cancelPromise,
        ])
      }

      void spawnPoller // spawnPoller is a Promise, not a timer — it exits on its own
    } else {
      // WHY: Simple goal or decomposition failed — launch single root Helix (original behavior)
      if (decomposition.decomposed) {
        log.info('Decomposition returned single task, proceeding with single Helix')
      }

      const rootHelix = await launchHelix(goal, context, undefined, 0)
      rootHelixId = rootHelix.helixId

      const spawnPoller = pollSpawnRequests()

      log.info('Waiting for root Helix completion', { rootHelixId })

      // WHY: Use allSettled so root Helix failure doesn't prevent children from completing
      await Promise.race([
        Promise.allSettled([rootHelix.promise]).then(() => {}),
        cancelPromise,
      ])

      // WHY: Give children a grace period to complete
      log.info('Root Helix settled, waiting for children', {
        childrenCount: runningHelixes.size - 1,
      })

      const gracePeriodMs = 120_000 // 2 minute grace period for children to finish work
      const gracePromise = new Promise<void>((resolve) => {
        setTimeout(resolve, gracePeriodMs)
      })

      const childPromises = Array.from(runningHelixes.values())
        .filter((h) => h.helixId !== rootHelixId)
        .map((h) => h.promise)

      await Promise.race([Promise.allSettled(childPromises).then(() => {}), gracePromise])

      void spawnPoller // spawnPoller is a Promise, not a timer — it exits on its own
    }

    log.info('Constellation execution complete', {
      totalNodes: nodes.size,
      completedNodes: Array.from(nodes.values()).filter((n) => n.status === 'completed' || n.status === 'degraded').length,
      degradedNodes: Array.from(nodes.values()).filter((n) => n.status === 'degraded').length,
      failedNodes: Array.from(nodes.values()).filter((n) => n.status === 'failed').length,
    })

    result = {
      constellationId,
      rootHelixId: rootHelixId!,
      nodes,
      constellationBlackboard: constellationBlackboard.getSnapshot(),
      totalTokensUsed: Array.from(nodes.values()).reduce((sum, n) => sum + n.tokensUsed, 0),
      totalDurationMs: Date.now() - startTime,
      corpus: corpus.getResult(),
      spawnRequests: [],
      decompositionTracker: tracker?.getSnapshot(),
      topology: topologyGraph?.enabled ? topologyGraph.getSnapshot() : undefined,
    }

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

    // Persist completion event
    if (constellationStore) {
      try {
        const completedCount = Array.from(nodes.values()).filter(n => n.status === 'completed').length
        const failedCount = Array.from(nodes.values()).filter(n => n.status === 'failed').length
        constellationStore.appendEvent(constellationId, 'constellation:completed', null,
          `Completed: ${completedCount}/${nodes.size} branches succeeded`, {
            durationMs: result.totalDurationMs,
            nodeCount: nodes.size,
            completedCount,
            failedCount,
            tokensUsed: result.totalTokensUsed,
          })
      } catch (err) {
        log.warn('Failed to persist completion event', { error: String(err) })
      }
    }

    // Archive to ConstellationStore (if provided)
    if (constellationStore) {
      try {
        const corpusResult = corpus.getResult()
        const treeSnapshot = enrichTreeWithTopology(corpusTree.getSnapshot(), topologyGraph)
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
            avgGoalAlignment: a.avgGoalAlignment ?? 0.5,
            avgNovelty: a.avgNovelty ?? 0.5,
            avgProgress: a.avgProgress ?? 0.3,
            directiveHistory: [],
            escalationLevel: 0 as const,
            ignoredDirectiveStreak: 0,
            lowProgressStreak: 0,
            discoveries: [],
            contextInjectionsReceived: 0,
            researchDigestBuilt: false,
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

    // Write completion summary to audit trail
    if (opts.auditTrail) {
      try {
        opts.auditTrail.writeCompletionSummary(constellationId, {
          goal,
          status: result.error ? 'failed' : 'completed',
          totalNodes: nodes.size,
          totalDurationMs: result.totalDurationMs,
          totalTokensUsed: result.totalTokensUsed,
        })
      } catch (err) {
        log.warn('Failed to write completion summary to audit trail', { error: String(err) })
      }
    }

    if (opts.memory) {
      try {
        const corpusResult = corpus.getResult()
        const completedNodes = Array.from(nodes.values()).filter(n => n.status === 'completed').length
        const failedNodes = Array.from(nodes.values()).filter(n => n.status === 'failed').length

        // Store constellation run summary for future runs to learn from
        const runSummary = [
          `Constellation run completed: "${goal.slice(0, 200)}"`,
          `Branches: ${nodes.size} total, ${completedNodes} completed, ${failedNodes} failed`,
          `Duration: ${Math.round((Date.now() - startTime) / 1000)}s`,
          `Template: ${template}`,
          corpusResult.reDecompositions?.length
            ? `Re-decompositions triggered: ${corpusResult.reDecompositions.length}`
            : null,
          corpusResult.qualityGateResults?.length
            ? `Quality gates: ${corpusResult.qualityGateResults.filter(r => r.result.passed).length}/${corpusResult.qualityGateResults.length} passed`
            : null,
        ].filter(Boolean).join('\n')

        await opts.memory.store({
          type: 'insight',
          content: runSummary,
          metadata: {
            constellationId,
            template,
            tags: ['constellation', `template:${template}`, 'run-completed'],
          },
        })
        log.info('Stored constellation run summary in memory', { constellationId })

        // Archive research digests for future constellation runs
        if (corpusResult.researchDigests?.length) {
          for (const digest of corpusResult.researchDigests) {
            const digestContent = [
              `Research digest for: "${digest.goal.slice(0, 150)}"`,
              digest.conclusion ? `Conclusion: ${digest.conclusion}` : null,
              digest.discoveries?.length
                ? `Key discoveries:\n${digest.discoveries.map(d => `  - ${d}`).join('\n')}`
                : null,
            ].filter(Boolean).join('\n\n')

            await opts.memory.store({
              type: 'insight',
              content: digestContent,
              metadata: {
                constellationId,
                sourceHelixId: digest.sourceHelixId,
                tags: ['research-digest', 'constellation', `goal:${goal.slice(0, 50)}`],
              },
            })
          }
          log.info('Archived research digests to memory', {
            count: corpusResult.researchDigests.length,
          })
        }
      } catch (memErr) {
        log.warn('Failed to store post-run memory', { error: String(memErr) })
        // Non-fatal — don't let memory failures affect constellation result
      }
    }
  } catch (err) {

    result = {
      constellationId,
      rootHelixId: rootHelixId ?? constellationId,
      nodes,
      constellationBlackboard: constellationBlackboard.getSnapshot(),
      totalTokensUsed: Array.from(nodes.values()).reduce((sum, n) => sum + n.tokensUsed, 0),
      totalDurationMs: Date.now() - startTime,
      corpus: corpus.getResult(),
      spawnRequests: [],
      decompositionTracker: tracker?.getSnapshot(),
      topology: topologyGraph?.enabled ? topologyGraph.getSnapshot() : undefined,
      error: String(err),
    }

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
        const failTree = enrichTreeWithTopology(corpusTree.getSnapshot(), topologyGraph)
        const nodeArr = Array.from(nodes.values())
        constellationStore.failSession(constellationId, String(err), Date.now() - startTime, {
          tree: failTree,
          totalBranches: nodeArr.length,
          completedBranches: nodeArr.filter(n => n.status === 'completed').length,
          failedBranches: nodeArr.filter(n => n.status === 'failed').length,
          tokensUsed: nodeArr.reduce((sum, n) => sum + n.tokensUsed, 0),
        })
        constellationStore.appendEvent(constellationId, 'constellation:failed', null,
          `Failed: ${String(err).slice(0, 200)}`, {
            error: String(err),
            durationMs: Date.now() - startTime,
            nodeCount: nodeArr.length,
          })
        log.info('Archived failed session to ConstellationStore', { constellationId })
      } catch (storeErr) {
        log.warn('Failed to archive failure to ConstellationStore', { error: String(storeErr) })
      }
    }

    throw err
  } finally {
    completed = true

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
      // WHY: Explicitly stop the Brainstem to prevent zombie LLM calls
      if (helix.brainstem) {
        try {
          await helix.brainstem.stop()
          log.info('Brainstem stopped', { helixId: id })
        } catch (err) {
          log.warn('Error stopping Brainstem', { helixId: id, error: String(err) })
        }
      }
      if (helix.brainstemMiniHelix) {
        try {
          await helix.brainstemMiniHelix.stop()
          log.info('Brainstem mini-Helix stopped', { helixId: id })
        } catch (err) {
          log.warn('Error stopping Brainstem mini-Helix', { helixId: id, error: String(err) })
        }
      }
    }

    // WHY: Stop ALL brainstem mini-helixes, including those from branches that
    // already completed and were removed from runningHelixes. Without this,
    // completed branches' mini-helixes become zombies that continue making
    // LLM calls indefinitely after the constellation finishes.
    for (const [mhId, mh] of allBrainstemMiniHelixes) {
      try {
        await mh.stop()
        log.info('Brainstem mini-Helix stopped (sweep)', { helixId: mhId })
      } catch (err) {
        log.warn('Error stopping Brainstem mini-Helix (sweep)', { helixId: mhId, error: String(err) })
      }
    }
    allBrainstemMiniHelixes.clear()

    log.info('Stopping Corpus')
    try {
      await corpus.stop()
    } catch (err) {
      log.warn('Error stopping Corpus', { error: String(err) })
    }

    if (corpusMiniHelix) {
      try {
        await corpusMiniHelix.stop()
        log.info('Corpus mini-Helix stopped')
      } catch (err) {
        log.warn('Error stopping Corpus mini-Helix', { error: String(err) })
      }
    }

    for (const [id, bridge] of blackboardBridges) {
      try {
        bridge.stop()
      } catch (err) {
        log.warn('Error stopping blackboard bridge', { helixId: id, error: String(err) })
      }
    }

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

    // Cleanup all remaining worktrees (belt-and-suspenders)
    if (worktreeIsolation) {
      await worktreeIsolation.cleanupAll()
    }

    log.info('Constellation pipeline cleanup complete')
  }

  return result
}


// Shared Thought Tree: SharedTreeReader Factory

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
    getPeerDigests: () => tree.getDigestsExcluding(helixId),
    getRelevantDigests: () => tree.getRelevantDigests(helixId),
    findRelatedTopics: (files, goalKeywords) => tree.findRelatedTopics(files, goalKeywords),
    getAllTopics: () => tree.getAllTopics(),
    getElevatedPatterns: () => tree.getElevatedPatterns(),
    getAllRetrospectives: () => tree.getAllRetrospectives(),
    getEffectivenessStats: () => tree.getEffectivenessStats(),

    updateDigest: (digest) => tree.updateDigest(helixId, digest),
    updateLiveStreamSnippet: (snippet) => tree.updateLiveStreamSnippet(helixId, snippet),
    createTopic: (name, contribution) => tree.createTopic(name, helixId, contribution),
    contributeTopic: (topicId, contribution) => tree.contributeTopic(topicId, contribution),
    recordRetrospective: (retrospective) => tree.recordRetrospective(helixId, retrospective),
    recordEffectiveness: (record) => tree.recordEffectiveness(record),
  }
}


// Serialization Helper — Convert Maps to plain objects for JSON

/**
 * Convert a ConstellationResult to a JSON-safe plain object.
 *
 * `ConstellationResult.nodes` and `ConstellationNode.postureResults` are
 * `Map<string, ...>` for runtime performance, but `JSON.stringify(map)`
 * produces `"{}"`. This helper converts them to `Record<string, ...>`.
 */
export function serializeConstellationResult(result: ConstellationResult): Record<string, unknown> {
  const serializedNodes: Record<string, unknown> = {}

  if (result.nodes instanceof Map) {
    for (const [key, node] of result.nodes) {
      const postureResults: Record<string, unknown> = {}
      if (node.postureResults instanceof Map) {
        for (const [pName, pResult] of node.postureResults) {
          postureResults[pName] = pResult
        }
      }
      serializedNodes[key] = { ...node, postureResults }
    }
  }

  return {
    ...result,
    nodes: serializedNodes,
  }
}
