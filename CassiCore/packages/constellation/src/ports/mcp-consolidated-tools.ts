/**
 * mcp-consolidated-tools — Port over CassiCore's `mcp/gateway/index.js` consolidated tools
 * used by `meditation/solo-runner.ts`.
 *
 * CassiCore's `mcp/gateway/index.js` re-exports the ENTIRE MCP tool router (30+ `*-tools.js`
 * modules bound to the daemon's fetch/SSE runtime). Constellation's solo-runner uses only six
 * consolidated symbols. This port pins that surface; the schema getters return minimal
 * tool-schema objects (functional), while the executors throw `not connected` until a host
 * wires the real MCP tools.
 *
 * Self-contained: depends only on built-ins.
 */

/** Shape of a single MCP tool definition the solo-runner builds. */
export interface ToolSchema {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/** The consolidated `code` tool schema. `includeFilesystem` historically extended it. */
export function getCodeConsolidatedToolSchema(_includeFilesystem = false): ToolSchema {
  return {
    name: 'code',
    description: 'Consolidated code tool (read/search/analyze repository code).',
    input_schema: {
      type: 'object',
      properties: { operation: { type: 'string' } },
    },
  }
}

/** The consolidated `filesystem` tool schema. */
export function getFilesystemConsolidatedToolSchema(_readOnly = false): ToolSchema {
  return {
    name: 'file',
    description: 'Consolidated filesystem tool (read/write/list files).',
    input_schema: {
      type: 'object',
      properties: { path: { type: 'string' } },
    },
  }
}

/** The consolidated web-searching tool definition. */
export const WEB_CONSOLIDATED_TOOL: ToolSchema = {
  name: 'web',
  description: 'Consolidated web tool (search and fetch web content).',
  input_schema: {
    type: 'object',
    properties: { query: { type: 'string' } },
  },
}

/** A routeTool callback shape (used to dispatch subgroup tools). */
export interface RouteTool {
  (toolName: string, toolArgs: unknown): Promise<unknown>
}

/** Result of a consolidated tool execution. */
export interface ConsolidatedToolResult {
  content: string
  isError: boolean
  [key: string]: unknown
}

export interface PortLogger {
  debug(msg: string, meta?: Record<string, unknown>): void
  info(msg: string, meta?: Record<string, unknown>): void
  warn(msg: string, meta?: Record<string, unknown>): void
  error(msg: string, meta?: Record<string, unknown>): void
  child?(component: string): PortLogger
}

/** Execute the consolidated `code` tool. Requires host wiring (real MCP tools). */
export function executeCodeConsolidatedTool(
  _input: Record<string, unknown>,
  _log: PortLogger,
  _routeTool: RouteTool,
): Promise<ConsolidatedToolResult> {
  return Promise.reject(
    new Error('[constellation] mcp-consolidated-tools not connected — wire executeCodeConsolidatedTool'),
  )
}

/** Execute the consolidated `filesystem` tool. Requires host wiring. */
export function executeFilesystemConsolidatedTool(
  _input: Record<string, unknown>,
  _log: PortLogger,
  _routeTool: RouteTool,
): Promise<ConsolidatedToolResult> {
  return Promise.reject(
    new Error(
      '[constellation] mcp-consolidated-tools not connected — wire executeFilesystemConsolidatedTool',
    ),
  )
}

/** Execute the consolidated `web` tool. Requires host wiring. */
export function executeWebConsolidatedTool(
  _baseUrl: string,
  _input: Record<string, unknown>,
  _log: PortLogger,
  _routeTool: RouteTool,
): Promise<ConsolidatedToolResult> {
  return Promise.reject(
    new Error('[constellation] mcp-consolidated-tools not connected — wire executeWebConsolidatedTool'),
  )
}
