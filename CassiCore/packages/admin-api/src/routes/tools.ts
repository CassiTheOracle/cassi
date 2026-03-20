import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

import type { AdminRuntimeFacade } from './runtime.js'
import {
  CORE_TOOLS,
  SESSION_TOOLS,
  MEMORY_TOOLS,
  CONFIG_ADMIN_TOOLS,
  FLUX_TOOLS,
  ADMIN_API_TOOLS,
  DIALECTIC_TOOLS,
  INTELLIGENCE_TOOLS,
  DYAD_TOOLS,
  LUMEN_TOOLS,
  MODEL_DIRECTIVE_TOOLS,
  DO_TOOLS,
  ENRICH_TOOLS,
  BLACKBOARD_TOOLS,
  TRAINING_TOOLS,
} from '../../mcp/gateway/index.js'

/** Category labels for grouping tools in the catalog */
const TOOL_CATEGORIES: Array<{ label: string; tools: readonly { name: string; description: string; inputSchema: unknown }[] }> = [
  { label: 'core',         tools: CORE_TOOLS },
  { label: 'session',      tools: SESSION_TOOLS },
  { label: 'memory',       tools: MEMORY_TOOLS },
  { label: 'intelligence', tools: INTELLIGENCE_TOOLS },
  { label: 'lumen',        tools: LUMEN_TOOLS },
  { label: 'dyad',         tools: DYAD_TOOLS },
  { label: 'flux',         tools: FLUX_TOOLS },
  { label: 'config',       tools: CONFIG_ADMIN_TOOLS },
  { label: 'admin',        tools: ADMIN_API_TOOLS },
  { label: 'blackboard',   tools: BLACKBOARD_TOOLS },
  { label: 'training',     tools: TRAINING_TOOLS },
  { label: 'meta',         tools: [...DO_TOOLS, ...ENRICH_TOOLS, ...DIALECTIC_TOOLS, ...MODEL_DIRECTIVE_TOOLS] },
]

function buildCatalog() {
  const all: { name: string; description: string; inputSchema: unknown; category: string }[] = []
  const categories: Record<string, string[]> = {}
  for (const { label, tools } of TOOL_CATEGORIES) {
    categories[label] = []
    for (const t of tools) {
      all.push({ name: t.name, description: t.description, inputSchema: t.inputSchema, category: label })
      categories[label].push(t.name)
    }
  }
  return { tools: all, categories, count: all.length }
}

export interface ToolsRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  pathname: string
}

export async function handleToolsRoutes(
  deps: ToolsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { runtime, sendJSON, parseBody, pathname } = deps

  // GET /tools/catalog — full MCP tool catalog grouped by category
  if (method === 'GET' && pathname === '/tools/catalog') {
    try {
      sendJSON(res, 200, buildCatalog())
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // POST /tools/execute
  if (method === 'POST' && pathname === '/tools/execute') {
    try {
      const body = await parseBody(req)
      const toolName = body?.tool || body?.name
      const input = body?.input || {}
      const sessionId = body?.sessionId || null
      if (!toolName) {
        sendJSON(res, 400, { error: 'missing tool name (tool)' })
        return true
      }
      const exec = runtime.getToolExecutor()
      if (!exec || typeof exec.execute !== 'function') {
        sendJSON(res, 503, { error: 'toolExecutor not available' })
        return true
      }
      const { randomUUID } = await import('node:crypto')
      const call = { id: randomUUID(), name: toolName, input }
      try {
        const result = await exec.execute(call, sessionId || `admin-${Date.now()}`)
        sendJSON(res, 200, result)
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /tools/registry
  if (method === 'GET' && pathname === '/tools/registry') {
    try {
      const toolRegistry = runtime.getToolRegistry()
      if (!toolRegistry || typeof toolRegistry.list !== 'function') {
        sendJSON(res, 503, { error: 'tool registry not initialised' })
        return true
      }
      const list = toolRegistry.list().map((t: any) => ({ name: t.name, description: t.description, parameters: t.parameters }))
      sendJSON(res, 200, list)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
