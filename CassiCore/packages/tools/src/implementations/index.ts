import { getEventBus, getContextWindowDebugger } from '../../events/index.js'

import { registerCassandraEventTools } from './cassandra-event.js'
import {
  reflectDefinition, makeReflectHandler,
  cognitiveRememberDefinition, makeCognitiveRememberHandler,
  probeDefinition, makeProbeHandler,
  type CognitiveToolDeps, type ProbeDeps,
} from './cognitive-tools.js'
import { listToolsDefinition, listToolsHandler } from './list-tools.js'
import {
  autofixDefinition, makeAutofixHandler,
  type AutofixDeps,
} from './autofix-tool.js'
import {
  coordinateDefinition, makeCoordinateHandler,
  checkPeersDefinition, makeCheckPeersHandler,
  type PeerToolDeps,
} from './peer-coordination.js'
import { registerContextWindowTools } from './context-window-tools.js'
import { desktopVisionDefinition, desktopVisionHandler } from './desktop-vision.js'
import { getSubagentResultDefinition, makeGetSubagentResultHandler } from './get-subagent-result.js'
import { getSubagentStatusDefinition, makeGetSubagentStatusHandler } from './get-subagent-status.js'
import { listSubagentsDefinition, makeListSubagentsHandler } from './list-subagents.js'
import { memorySearchDefinition, makeMemorySearchHandler, rememberDefinition, makeRememberHandler } from './memory-search.js'
import { createQueryEventsTool, listPresetsForTool } from './query-events.js'
import { readFileDefinition, readFileHandler } from './read-file.js'
import { readFilesDefinition, readFilesHandler } from './read-files.js'
import { shellExecDefinition, shellExecHandler } from './shell-exec.js'
import { createSubagentSpawnFunction } from './spawn-subagent-impl.js'
import { spawnSubagentDefinition, makeSpawnSubagentHandler } from './spawn-subagent.js'
import { webFetchDefinition, webFetchHandler } from './web-fetch.js'
import { webSearchDefinition, webSearchHandler } from './web-search.js'
import { writeFileDefinition, writeFileHandler } from './write-file.js'
import { runTestsDefinition, runTestsHandler } from './run-tests.js'
import { runBackgroundDefinition, makeRunBackgroundHandler } from './run-background.js'
import { checkJobDefinition, makeCheckJobHandler } from './check-job.js'
import { waitJobDefinition, makeWaitJobHandler } from './wait-job.js'
import {
  teamDashboardDefinition, makeTeamDashboardHandler,
  type TeamDashboardDeps,
} from './team-dashboard.js'
import {
  systemHealthDefinition, makeSystemHealthHandler,
  type SystemHealthDeps,
} from './system-health.js'
import {
  debugSessionDefinition, makeDebugSessionHandler,
  type DebugSessionDeps,
} from './debug-session.js'
import {
  universalSearchDefinition, makeUniversalSearchHandler,
  type UniversalSearchDeps,
} from './universal-search.js'

import type { IMemory } from '../../../types/intelligence.js'
import type { ISessionManager } from '../../../types/runtime.js'
import type { ToolRegistry } from '../registry.js'
import type { TurnPipeline } from '../../turn-pipeline.js'
import type { IEventBus, ILogger } from '../../../types/interfaces.js'
import type { SessionStore } from '../../session-store.js'
import type { EventHistory } from '../../event-history.js'



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
  /** Dependencies for probe tool (_probe) — extends cognitive deps with drone swarm */
  probeDeps?: ProbeDeps
  /** Dependencies for autofix tool (_autofix) — full autonomous fix pipeline */
  autofixDeps?: AutofixDeps
  /** Dependencies for peer coordination tools (_coordinate, _check_peers) */
  peerToolDeps?: PeerToolDeps
  /** Lazy getter for the background job manager */
  getJobManager?: () => import('../../jobs/job-manager.js').JobManager | undefined
}

/**
 * @dep callers: start (core/daemon.ts)
 * @dep calls: getEventBus, execute, register, getContextWindowDebugger, makeWaitJobHandler [+22]
 * @dep flows: RegisterCoreTools → EstimateChars (1/4), RegisterCoreTools → FormatMemoryResult (1/3)
 * @dep module: Implementations
 * @dep risk: LOW | 1 caller, 2 flows, 1 module
 */

export function registerCoreTools(registry: ToolRegistry, deps: CoreToolDeps): void {
  // Shell execution
  registry.register(shellExecDefinition, shellExecHandler)

  // File I/O
  registry.register(readFileDefinition, readFileHandler)
  registry.register(readFilesDefinition, readFilesHandler)
  registry.register(writeFileDefinition, writeFileHandler)

  // Desktop Vision (Linux/KDE window capture)
  registry.register(desktopVisionDefinition, desktopVisionHandler)

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
    // memory_search is DEPRECATED - use universal_search instead
    registry.register(
      memorySearchDefinition, 
      makeMemorySearchHandler(deps.memory)
    )
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
  }

  // Cognitive probe tool — _probe
  // Dispatches targeted drone swarms to investigate cognitive signals.
  // Maps signal kinds to investigation strategies, spawns free scout drones,
  // and returns aggregated findings + resonance patterns.
  if (deps.probeDeps) {
    registry.register(probeDefinition, makeProbeHandler(deps.probeDeps))
  }

  // Autofix tool — _autofix
  // Full autonomous bug fix pipeline: investigate → generate patch → validate → apply → journal.
  // Composes drone swarm (free), tsc validation, test runner, and improvement journal.
  if (deps.autofixDeps) {
    registry.register(autofixDefinition, makeAutofixHandler(deps.autofixDeps))
  }

  // Peer coordination tools — CONSOLIDATED (Phase 1)
  // _coordinate: Unified tool for signal, broadcast, shared_note, link_brain actions
  // _check_peers: Kept separate (discovery vs action)
  if (deps.peerToolDeps) {
    registry.register(coordinateDefinition, makeCoordinateHandler(deps.peerToolDeps))
    registry.register(checkPeersDefinition, makeCheckPeersHandler(deps.peerToolDeps))
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

  // Composite Tools - Aggregated views across multiple data sources
  // These tools aggregate data from multiple sources into unified responses
  
  // Get daemon reference for composite tools
  const daemon = (deps as any).daemon

  // team_dashboard: Unified team status, goal tree, budget, and events
  const triadTeam = daemon?.intelligence?.triadTeam
  if (triadTeam || deps.sessionManager) {
    const teamDashboardDeps: TeamDashboardDeps = {
      getTriadTeam: () => triadTeam,
      getEventBus: () => deps.bus,
    }
    registry.register(teamDashboardDefinition, makeTeamDashboardHandler(teamDashboardDeps))
  }

  // system_health: Comprehensive system status with providers, sessions, teams, and memory
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

  // universal_search: Unified memory and archive search with deduplication
  if (deps.memory) {
    // Archive is optional - tool handles gracefully if not available
    const archive = daemon?.archive
    const universalSearchDeps: UniversalSearchDeps = {
      memory: deps.memory,
      archive: archive || undefined,
    }
    registry.register(universalSearchDefinition, makeUniversalSearchHandler(universalSearchDeps))
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
