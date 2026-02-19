import type { ToolRegistry } from '../registry.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { ISessionManager } from '../../../types/runtime.js'

import { shellExecDefinition, shellExecHandler } from './shell-exec.js'
import { readFileDefinition, readFileHandler } from './read-file.js'
import { readFilesDefinition, readFilesHandler } from './read-files.js'
import { writeFileDefinition, writeFileHandler } from './write-file.js'
import { webFetchDefinition, webFetchHandler } from './web-fetch.js'
import { memorySearchDefinition, makeMemorySearchHandler } from './memory-search.js'

export interface CoreToolDeps {
  memory?: IMemory
  sessionManager?: ISessionManager
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

  // Memory search (requires memory module)
  if (deps.memory) {
    registry.register(memorySearchDefinition, makeMemorySearchHandler(deps.memory))
  }

  // list_sessions — inline (simple)
  registry.register(
    {
      name: 'list_sessions',
      description: 'List all active ClaraCore sessions with their IDs and last activity.',
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
}
