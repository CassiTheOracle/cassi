#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'

import { SESSION_TOOLS, executeSessionTool } from './tools/sessions.js'
import { CURATION_TOOLS, executeCurationTool } from './tools/curation.js'
import { COGNITIVE_TOOLS, executeCognitiveTool } from './tools/cognitive.js'
import { ORCHESTRATION_TOOLS, executeOrchestrationTool } from './tools/orchestration.js'
import { ROUTING_TOOLS, executeRoutingTool } from './tools/routing.js'
import { log, formatError, formatText } from './helpers.js'
import type { ToolHandler } from './types.js'

const ADMIN_URL = process.env.CASSICORE_URL || 'http://localhost:7433'
const HERMES_DB_PATH = process.env.HERMES_STATE_DB || ''

const ALL_TOOLS: Array<{ name: string; description: string; inputSchema: any }> = [
  ...SESSION_TOOLS,
  ...CURATION_TOOLS,
  ...COGNITIVE_TOOLS,
  ...ORCHESTRATION_TOOLS,
  ...ROUTING_TOOLS,
].map(t => ({ name: t.name, description: t.description, inputSchema: t.inputSchema }))

const TOOL_MAP = new Map<string, ToolHandler>()
for (const t of SESSION_TOOLS) TOOL_MAP.set(t.name, executeSessionTool)
for (const t of CURATION_TOOLS) TOOL_MAP.set(t.name, executeCurationTool)
for (const t of COGNITIVE_TOOLS) TOOL_MAP.set(t.name, executeCognitiveTool)
for (const t of ORCHESTRATION_TOOLS) TOOL_MAP.set(t.name, executeOrchestrationTool)
for (const t of ROUTING_TOOLS) TOOL_MAP.set(t.name, executeRoutingTool)

function createServer() {
  const server = new Server(
    { name: 'cassicore-hermes-gateway', version: '0.1.0' },
    { capabilities: { tools: { listChanged: true } } },
  )

  server.onerror = (error: Error) => {
    log('Server error:', String(error))
  }

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: ALL_TOOLS }))

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params
    const handler = TOOL_MAP.get(name)
    if (!handler) {
      return formatError(new Error(`Unknown tool: ${name}`))
    }
    try {
      const result = await handler(ADMIN_URL, name, args ?? {}, HERMES_DB_PATH, { info: log, error: log })
      if (result?.isError) {
        log('Tool error:', name, result.content?.[0]?.text)
      }
      return result ?? formatText('No result')
    } catch (err: any) {
      log('Tool threw:', name, String(err))
      return formatError(err)
    }
  })

  return server
}

async function start() {
  log('Starting CassiCore Hermes Gateway (stdio mode)')
  log('CassiCore admin URL:', ADMIN_URL)
  log('Hermes state.db:', HERMES_DB_PATH || '(default path)')
  log(`Registered ${ALL_TOOLS.length} tools`)

  const server = createServer()
  const transport = new StdioServerTransport()

  server.onclose = () => { log('MCP server closed -- exiting'); process.exit(0) }

  process.stdin.on('end', () => {
    log('stdin ended -- client disconnected, closing')
    server.close().catch(() => {})
    setTimeout(() => process.exit(0), 500)
  })
  process.stdin.on('close', () => {
    log('stdin closed -- exiting')
    server.close().catch(() => {})
    setTimeout(() => process.exit(0), 500)
  })

  for (const sig of ['SIGTERM', 'SIGINT', 'SIGHUP'] as const) {
    process.on(sig, () => {
      log(`Received ${sig} -- shutting down`)
      server.close().catch(() => {})
      setTimeout(() => process.exit(0), 500)
    })
  }

  await server.connect(transport)
  log('Gateway ready')
}

start().catch((err) => {
  log('Failed to start:', String(err))
  process.exit(1)
})
