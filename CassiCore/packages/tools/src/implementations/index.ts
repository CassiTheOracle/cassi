import { getEventBus, getContextWindowDebugger } from '@cassicore/events'

import { registerCassandraEventTools } from './cassandra-event.js'
import {
  reflectDefinition, makeReflectHandler,
  cognitiveRememberDefinition, makeCognitiveRememberHandler,
  type CognitiveToolDeps,
} from './cognitive-tools.js'
import { listToolsDefinition, listToolsHandler } from './list-tools.js'
import {
  coordinateDefinition, makeCoordinateHandler,
  checkPeersDefinition, makeCheckPeersHandler,
  type PeerToolDeps,
} from './peer-coordination.js'
import {
  collectThoughtsDefinition, makeCollectThoughtsHandler,
  type CollectThoughtsDeps,
} from './collect-thoughts.js'
import { registerContextWindowTools } from './context-window-tools.js'
import { desktopVisionDefinition, desktopVisionHandler } from './desktop-vision.js'
import { vybitDefinition, vybitHandler } from './vybit.js'

import { getSubagentResultDefinition, makeGetSubagentResultHandler } from './get-subagent-result.js'
import { getSubagentStatusDefinition, makeGetSubagentStatusHandler } from './get-subagent-status.js'
import { listSubagentsDefinition, makeListSubagentsHandler } from './list-subagents.js'
import {
  rememberDefinition, makeRememberHandler,
  memorySearchDefinition, makeMemorySearchHandler,
} from './memory-search.js'
import { createQueryEventsTool, listPresetsForTool } from './query-events.js'
import { readFileDefinition, readFileHandler } from './read-file.js'
import { readFilesDefinition, readFilesHandler } from './read-files.js'
import { shellExecDefinition, shellExecHandler } from './shell-exec.js'
import { cassiShellDefinition, cassiShellHandler, setCassiShellDeps } from './cassi-shell.js'
import { createSubagentSpawnFunction } from './spawn-subagent-impl.js'
import { spawnSubagentDefinition, makeSpawnSubagentHandler } from './spawn-subagent.js'
import { webFetchDefinition, webFetchHandler } from './web-fetch.js'
import { webSearchDefinition, webSearchHandler } from './web-search.js'
import { writeFileDefinition, writeFileHandler } from './write-file.js'
import { todoWriteDefinition, todoWriteHandler } from './todo-write.js'
import { runTestsDefinition, runTestsHandler } from './run-tests.js'
import { runBackgroundDefinition, makeRunBackgroundHandler } from './run-background.js'
import { checkJobDefinition, makeCheckJobHandler } from './check-job.js'
import { waitJobDefinition, makeWaitJobHandler } from './wait-job.js'
import {
  systemHealthDefinition, makeSystemHealthHandler,
  type SystemHealthDeps,
} from './system-health.js'
import { graphDiscoverDefinition, graphDiscoverHandler } from './graph-discover.js'
import {
  debugSessionDefinition, makeDebugSessionHandler,
  type DebugSessionDeps,
} from './debug-session.js'
import {
  universalSearchDefinition, makeUniversalSearchHandler,
  type UniversalSearchDeps,
} from './universal-search.js'
import { workflowDefinition, makeWorkflowHandler } from './workflow.js'

import type { IMemory } from "@cassicore/foundation"
import type { ISessionManager } from "@cassicore/foundation"
import type { ToolRegistry } from '../registry.js'
import type { TurnPipeline } from '../ports/turn-pipeline.js'
import type { IEventBus, ILogger } from "@cassicore/foundation"
import type { SessionStore } from '../ports/session-store.js'
import type { EventHistory } from '@cassicore/events'



export interface CoreToolDeps {
  memory?: IMemory
  sessionManager?: ISessionManager
  sessionStore?: SessionStore
  bus?: IEventBus
  logger?: ILogger
  /** Lazy getter for pipeline - needed because tools are registered before pipeline is created */
  getPipeline?: () => TurnPipeline
  /** Subagent tracker for inspection tools */
  subagentTracker?: {
    list(): Array<any>
    get(runId: string): any | undefined
    getByParent(parentSessionId: string): Array<any>
    getResult(runId: string): { result?: string; error?: string; durationMs?: number } | undefined
  }
  /** Event history store for query_events tool */
  eventHistory?: EventHistory
  /** Dependencies for cognitive tools (_reflect, _remember) */
  cognitiveToolDeps?: CognitiveToolDeps
  /** Dependencies for peer coordination tools (_coordinate, _check_peers) */
  peerToolDeps?: PeerToolDeps
  /** Lazy getter for the background job manager */
  getJobManager?: () => import('../vendor/core/jobs/job-manager.js').JobManager | undefined
  /** Dependencies for collect_thoughts tool */
  collectThoughtsDeps?: CollectThoughtsDeps

  /** Lazy getter for workflow engine */
  getWorkflowEngine?: () => import('../vendor/core/workflow/engine.js').WorkflowEngine | null
  /** Lazy getter for workflow definitions map (id -> definition) */
  getWorkflowDefinitions?: () => Map<string, import("@cassicore/foundation").WorkflowDefinition>
  /** Lazy getter for workflow run store (persistence) */
  getWorkflowStore?: () => import('../vendor/core/workflow/persistence.js').WorkflowStore | null
  /** Lazy getter for workflow definition store (persistence) */
  getWorkflowDefStore?: () => import('../vendor/core/workflow/definition-store.js').WorkflowDefinitionStore | null
}

/**
 * @dep callers: buildTools (core/daemon/boot-pipeline-tools.ts), start (core/daemon.ts)
 * @dep calls: makeAutofixHandler, registerCassandraEventTools, setCassiShellDeps, makeCheckJobHandler, makeProbeHandler [+24]
 * @dep flows: BootPipelineTools → MakeWaitJobHandler (3/4), BootPipelineTools → MakeCheckJobHandler (3/4), BootPipelineTools → MakeRunBackgroundHandler (3/4) [+1]
 * @dep module: Implementations
 * @dep risk: MEDIUM | 2 callers, 4 flows, 1 module
 */

export function registerCoreTools(registry: ToolRegistry, deps: CoreToolDeps): void {
  // Shell execution
  registry.register(shellExecDefinition, shellExecHandler)

  // Cassi unified shell — minimal context, full discovery
  registry.register(cassiShellDefinition, cassiShellHandler)
  if (deps.logger) {
    setCassiShellDeps({
      toolRegistry: registry,
      executeToolByName: async (name, input, ctx) => {
        const entry = registry.get(name)
        if (!entry) throw new Error(`Tool not found: ${name}`)
        return entry.handler(input, ctx)
      },
      workdir: process.cwd(),
      logger: deps.logger,
    })
  }

  // File I/O
  registry.register(readFileDefinition, readFileHandler)
  registry.register(readFilesDefinition, readFilesHandler)
  registry.register(writeFileDefinition, writeFileHandler)

  // Task tracking
  registry.register(todoWriteDefinition, todoWriteHandler)

  // Desktop Vision (Linux/KDE window capture)
  registry.register(desktopVisionDefinition, desktopVisionHandler)

  // VyBit visual browser editing integration
  registry.register(vybitDefinition, vybitHandler)

  // Network
  registry.register(webFetchDefinition, webFetchHandler)
  registry.register(webSearchDefinition, webSearchHandler)

  // Test runner (narrow-scope — vitest only, safe for critic use)
  registry.register(runTestsDefinition, runTestsHandler)

  // Background job tools (requires JobManager from daemon)
  if (deps.getJobManager) {
    registry.register(runBackgroundDefinition, makeRunBackgroundHandler(deps.getJobManager))
    registry.register(checkJobDefinition, makeCheckJobHandler(deps.getJobManager))
    registry.register(waitJobDefinition, makeWaitJobHandler(deps.getJobManager))
  }

  // Memory tools (requires memory module)
  if (deps.memory) {
    registry.register(rememberDefinition, makeRememberHandler(deps.memory))
  }

  // list_sessions — inline (simple)
  registry.register(
    {
      name: 'list_sessions',
      description: 'List all active CassiCore sessions with their IDs and last activity.',
      parameters: { type: 'object', properties: {}, required: [] },
      timeoutMs: 5_000,
      readOnly: true,
      category: 'debug',
    },
    async (_input, ctx) => {
      if (!deps.sessionManager) return 'Session manager not available.'
      const sessions = deps.sessionManager.list()
      if (sessions.length === 0) return 'No active sessions.'
      return sessions.map(s =>
        `${s.id} | channel:${s.channelId} | turns:${s.history.length} | active:${s.lastActiveAt.toISOString()}`
      ).join('\n')
    }
  )

  // list_tools — meta-discovery tool for progressive tool discovery
  // WHY: This tool needs the registry injected into its context at execution time
  registry.register(listToolsDefinition, listToolsHandler)

  // WHY: spawn_subagent is now unified under Thinker
  // Direct subagent spawning is disabled - all subagent operations go through Thinker
  // for centralized coordination and persistence.
  // 
  // The spawnFn is still created for Thinker's internal use:
  const spawnFn = deps.sessionManager && deps.bus && deps.logger && deps.getPipeline
    ? createSubagentSpawnFunction({
        sessionManager: deps.sessionManager,
        sessionStore: deps.sessionStore,
        bus: deps.bus,
        logger: deps.logger,
        getPipeline: deps.getPipeline,
      })
    : undefined

  // Store spawnFn on deps for Thinker to access
  ;(deps as any).spawnSubagentFn = spawnFn

  // Subagent inspection tools - now routed through Thinker when available
  // Thinker maintains a unified registry of all subagents for persistence
  const thinkerRef = deps.getPipeline ? (deps.getPipeline() as any)?.intelligence?.thinker : undefined
  
  if (deps.subagentTracker || thinkerRef) {
    registry.register(
      listSubagentsDefinition,
      makeListSubagentsHandler(deps.subagentTracker, thinkerRef)
    )
    registry.register(
      getSubagentStatusDefinition,
      makeGetSubagentStatusHandler(deps.subagentTracker, thinkerRef)
    )
    registry.register(
      getSubagentResultDefinition,
      makeGetSubagentResultHandler(deps.subagentTracker, thinkerRef)
    )
  }

  // Event query tool (requires event history)
  if (deps.eventHistory) {
    const queryTool = createQueryEventsTool(deps.eventHistory)
    registry.register(
      {
        name: queryTool.name,
        description: queryTool.description,
        parameters: queryTool.inputSchema,
        timeoutMs: 30_000,
      },
      async (input, ctx) => {
        const result = await queryTool.execute(input as any, ctx)
        if (result.success) {
          return result.result ?? 'Query completed with no results.'
        }
        return `Error: ${result.error ?? 'Unknown error'}`
      }
    )
  }

  // Cognitive tools — _reflect + _remember
  // These exploit the free tool loop in request-based billing providers.
  // They execute locally (instant) and route signals to the intelligence layer.
  if (deps.cognitiveToolDeps) {
    registry.register(reflectDefinition, makeReflectHandler(deps.cognitiveToolDeps))
    registry.register(cognitiveRememberDefinition, makeCognitiveRememberHandler(deps.cognitiveToolDeps))
    registry.register(graphDiscoverDefinition, graphDiscoverHandler)
  }

  // Peer coordination tools — CONSOLIDATED (Phase 1)
  // _coordinate: Unified tool for signal, broadcast, shared_note, link_brain actions
  // _check_peers: Kept separate (discovery vs action)
  if (deps.peerToolDeps) {
    registry.register(coordinateDefinition, makeCoordinateHandler(deps.peerToolDeps))
    registry.register(checkPeersDefinition, makeCheckPeersHandler(deps.peerToolDeps))
  }

  // Collect Thoughts — primary structured thinking with enrichment pipeline
  // Each step is processed through ThoughtObserver, CognitiveBridge, and memory search.
  // Supports branching (explore alternatives) and revision (reconsider earlier steps).
  if (deps.collectThoughtsDeps) {
    registry.register(collectThoughtsDefinition, makeCollectThoughtsHandler(deps.collectThoughtsDeps))
  }

  // Cassandra Event Stream Tools - CONSOLIDATED (Phase 2)
  // cassandra_query_events: Unified query interface (mode: state|history)
  // Eliminates: cassandra_subscribe, cassandra_invalidate_cache (documented alternatives)
  try {
    const eventBus = getEventBus()
    registerCassandraEventTools(registry, eventBus, () => {
      // Get current session ID from context if available
      return (deps.sessionManager as any)?.currentSessionId
    })
  } catch (err) {
    // Event bus not available, skip registration
  }

  // REMOVED: team_dashboard tool — deprecated TriadTeam orchestrator deleted
  // system_health: Comprehensive system status with providers, sessions, and memory
  const daemon = (deps as any).daemon
  const systemHealthDeps: SystemHealthDeps = {
    daemon: daemon,
    sessionManager: deps.sessionManager,
    memory: deps.memory,
  }
  registry.register(systemHealthDefinition, makeSystemHealthHandler(systemHealthDeps))

  // debug_session: Deep session debugging with context, turns, and cognitive state
  if (deps.sessionManager || deps.memory) {
    const debugSessionDeps: DebugSessionDeps = {
      sessionManager: deps.sessionManager,
      memory: deps.memory,
      getEventBus: () => deps.bus,
      getContextWindowDebugger: () => getContextWindowDebugger(),
    }
    registry.register(debugSessionDefinition, makeDebugSessionHandler(debugSessionDeps))
  }

  // universal_search: Unified memory + archive search with deduplication
  if (deps.memory) {
    const archive = daemon?.archive
    const universalSearchDeps: UniversalSearchDeps = {
      memory: deps.memory,
      archive: archive || undefined,
    }
    registry.register(universalSearchDefinition, makeUniversalSearchHandler(universalSearchDeps))
  }

  // Workflow tool: list, run, resume, cancel, manage workflow definitions
  if (deps.getWorkflowEngine) {
    registry.register(workflowDefinition, makeWorkflowHandler({
      getEngine: deps.getWorkflowEngine,
      getDefinitions: deps.getWorkflowDefinitions ?? (() => new Map()),
      getStore: deps.getWorkflowStore ?? (() => null),
      getDefStore: deps.getWorkflowDefStore ?? (() => null),
    }))
  }

  // Context Window Debugging Tools - CONSOLIDATED (Phase 2)
  // cassandra_context_inspect: Unified inspection (action: snapshot|history|stats)
  // Eliminates: cassandra_tail_context_window (documented alternative)
  try {
    registerContextWindowTools(registry, () => getContextWindowDebugger())
  } catch (err) {
    // Context window debugger not available, skip registration
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// registerMindTools — RETAINED MIND SLICE (CASSICORE-FOCUS §20 / DELEGATE-SURFACE)
//
// The P3 seam the focused mind runtime + spine mirror. Registers ONLY the retained
// mind tools (plan §4.2) + the P5-deletion seam tools (memory/peer/cognitive),
// against a `ToolRegistry`, with retained handler deps injected via `CoreToolDeps`
// (the retained dep-injection seam). `registerCoreTools` above is UNTOUCHED — the
// two coexist; the runtime calls this, the spine mirrors each tool via
// `pi.registerTool` and forwards `{tool, params, sessionId}` over the channel.
//
// Retained tools registered here (faithful to registerCoreTools' retained blocks):
//   collect_thoughts, graph_discover, _reflect, _remember, _coordinate, _check_peers,
//   list_sessions, list_subagents, get_subagent_status, get_subagent_result,
//   system_health, debug_session, universal_search, cassandra_query_events,
//   cassandra_context_inspect, query_events, remember, memory_search.
// {@link registerMindTools}
export function registerMindTools(registry: ToolRegistry, deps: CoreToolDeps): void {
  // list_sessions — inline (simple), mirrors §163-181.
  registry.register(
    {
      name: 'list_sessions',
      description: 'List all active CassiCore sessions with their IDs and last activity.',
      parameters: { type: 'object', properties: {}, required: [] },
      timeoutMs: 5_000,
      readOnly: true,
      category: 'debug',
    },
    async (_input, ctx) => {
      if (!deps.sessionManager) return 'Session manager not available.'
      const sessions = deps.sessionManager.list()
      if (sessions.length === 0) return 'No active sessions.'
      return sessions.map(s =>
        `${s.id} | channel:${s.channelId} | turns:${s.history.length} | active:${s.lastActiveAt.toISOString()}`
      ).join('\n')
    }
  )

  // list_subagents / get_subagent_status / get_subagent_result — via Thinker or tracker.
  // The pipeline's intelligence.thinker carries the unified subagent registry; it is
  // reachable only through the non-typed pipeline shape, so narrow through unknown.
  type ThinkerSubagentSink = {
    listSubagents?: (status?: string) => unknown[]
    getSubagent?: (runId: string) => { result?: string; error?: string; status?: string } | undefined
  }
  const pipelineIntelligence = deps.getPipeline?.() as unknown as { intelligence?: { thinker?: ThinkerSubagentSink } } | undefined
  const thinkerRef = pipelineIntelligence?.intelligence?.thinker
  if (deps.subagentTracker || thinkerRef) {
    registry.register(listSubagentsDefinition, makeListSubagentsHandler(deps.subagentTracker, thinkerRef))
    registry.register(getSubagentStatusDefinition, makeGetSubagentStatusHandler(deps.subagentTracker, thinkerRef))
    registry.register(getSubagentResultDefinition, makeGetSubagentResultHandler(deps.subagentTracker, thinkerRef))
  }

  // query_events — event-history query tool (retained bus history seam).
  if (deps.eventHistory) {
    const queryTool = createQueryEventsTool(deps.eventHistory)
    registry.register(
      {
        name: queryTool.name,
        description: queryTool.description,
        parameters: queryTool.inputSchema,
        timeoutMs: 30_000,
      },
      async (input, ctx) => {
        // QueryEventsTool.execute accepts the same `{input, ctx}` tool-call shape
        // as the ToolHandler — pass through directly, no cast required.
        const result = await queryTool.execute(input, ctx)
        if (result.success) return result.result ?? 'Query completed with no results.'
        return `Error: ${result.error ?? 'Unknown error'}`
      }
    )
  }

  // Cognitive tools — _reflect + _remember + graph_discover (retained seam).
  if (deps.cognitiveToolDeps) {
    registry.register(reflectDefinition, makeReflectHandler(deps.cognitiveToolDeps))
    registry.register(cognitiveRememberDefinition, makeCognitiveRememberHandler(deps.cognitiveToolDeps))
    registry.register(graphDiscoverDefinition, graphDiscoverHandler)
  }

  // Peer coordination tools — _coordinate + _check_peers (retained seam).
  if (deps.peerToolDeps) {
    registry.register(coordinateDefinition, makeCoordinateHandler(deps.peerToolDeps))
    registry.register(checkPeersDefinition, makeCheckPeersHandler(deps.peerToolDeps))
  }

  // Collect Thoughts — primary structured thinking tool.
  if (deps.collectThoughtsDeps) {
    registry.register(collectThoughtsDefinition, makeCollectThoughtsHandler(deps.collectThoughtsDeps))
  }

  // Cassandra Event Stream — cassandra_query_events (consolidated query interface).
  try {
    const eventBus = getEventBus()
    const currentSessionId = () => {
      const sm = deps.sessionManager as unknown as { currentSessionId?: string } | undefined
      return sm?.currentSessionId
    }
    registerCassandraEventTools(registry, eventBus, currentSessionId)
  } catch (err) {
    // Event bus not available, skip registration
  }

  // system_health — comprehensive status (retained read-only health surface).
  // The daemon-health slice is wired by the host/runtime; absent it, the handler
  // reports `daemon: unavailable` gracefully.
  type MindDaemonLike = { archive?: { search: (q: string, o?: unknown) => Promise<unknown[]> } }
  const daemon = (deps as unknown as { daemon?: MindDaemonLike }).daemon ?? undefined
  registry.register(systemHealthDefinition, makeSystemHealthHandler({
    daemon,
    sessionManager: deps.sessionManager,
    memory: deps.memory,
  }))

  // debug_session — deep session debugging.
  if (deps.sessionManager || deps.memory) {
    registry.register(debugSessionDefinition, makeDebugSessionHandler({
      sessionManager: deps.sessionManager,
      memory: deps.memory,
      getEventBus: () => deps.bus,
      getContextWindowDebugger: () => getContextWindowDebugger(),
    }))
  }

  // universal_search — unified memory + archive search.
  if (deps.memory) {
    registry.register(universalSearchDefinition, makeUniversalSearchHandler({
      memory: deps.memory,
      archive: daemon?.archive || undefined,
    }))
  }

  // Memory tools — remember + memory_search (P5-deletion seam; merge into ohmypi
  // memory built-ins once the backend lands). Kept registered behind deps.memory.
  if (deps.memory) {
    registry.register(rememberDefinition, makeRememberHandler(deps.memory))
    registry.register(memorySearchDefinition, makeMemorySearchHandler(deps.memory))
  }

  // Context Window Debugging — cassandra_context_inspect (consolidated inspection).
  try {
    registerContextWindowTools(registry, () => getContextWindowDebugger())
  } catch (err) {
    // Context window debugger not available, skip registration
  }
}
