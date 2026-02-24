import type { ToolRegistry } from '../registry.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { ISessionManager } from '../../../types/runtime.js'
import type { TurnPipeline } from '../../turn-pipeline.js'
import type { IEventBus, ILogger } from '../../../types/interfaces.js'
import type { SessionStore } from '../../session-store.js'

import { shellExecDefinition, shellExecHandler } from './shell-exec.js'
import { readFileDefinition, readFileHandler } from './read-file.js'
import { readFilesDefinition, readFilesHandler } from './read-files.js'
import { writeFileDefinition, writeFileHandler } from './write-file.js'
import { webFetchDefinition, webFetchHandler } from './web-fetch.js'
import { webSearchDefinition, webSearchHandler } from './web-search.js'
import { memorySearchDefinition, makeMemorySearchHandler } from './memory-search.js'
import { spawnSubagentDefinition, makeSpawnSubagentHandler } from './spawn-subagent.js'
import { createSubagentSpawnFunction } from './spawn-subagent-impl.js'
import { thinkDefinition, makeThinkHandler } from './think.js'

export interface CoreToolDeps {
  memory?: IMemory
  sessionManager?: ISessionManager
  sessionStore?: SessionStore
  bus?: IEventBus
  logger?: ILogger
  /** Lazy getter for pipeline - needed because tools are registered before pipeline is created */
  getPipeline?: () => TurnPipeline
}

export function registerCoreTools(registry: ToolRegistry, deps: CoreToolDeps): void {
  // Shell execution
  registry.register(shellExecDefinition, shellExecHandler)

  // File I/O
  registry.register(readFileDefinition, readFileHandler)
  registry.register(readFilesDefinition, readFilesHandler)
  registry.register(writeFileDefinition, writeFileHandler)

  // Network
  registry.register(webFetchDefinition, webFetchHandler)
  registry.register(webSearchDefinition, webSearchHandler)

  // Memory search (requires memory module)
  if (deps.memory) {
    registry.register(memorySearchDefinition, makeMemorySearchHandler(deps.memory))
  }

  // list_sessions — inline (simple)
  registry.register(
    {
      name: 'list_sessions',
      description: 'List all active CassiCore sessions with their IDs and last activity.',
      parameters: { type: 'object', properties: {}, required: [] },
      timeoutMs: 5_000,
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

  // spawn_subagent — wired to real implementation when all deps available
  const spawnFn = deps.sessionManager && deps.bus && deps.logger && deps.getPipeline
    ? createSubagentSpawnFunction({
        sessionManager: deps.sessionManager,
        sessionStore: deps.sessionStore,
        bus: deps.bus,
        logger: deps.logger,
        getPipeline: deps.getPipeline,
      })
    : undefined

  registry.register(
    spawnSubagentDefinition,
    makeSpawnSubagentHandler(deps.sessionManager || ({} as ISessionManager), spawnFn)
  )

  // Think tool — trigger the dialectic with expanded context and return the synthesis
  if (deps.getPipeline) {
    registry.register(thinkDefinition, makeThinkHandler(deps))
  }
}
