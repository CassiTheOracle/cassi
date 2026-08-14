/**
 * VENDOR TYPE STUB — core/tools/types.ts
 * Faithful type surface for helix consumers via core/tools executor/registry stubs.
 * No runtime. Re-pointed to `@cassicore/tools` at P6; delete this stub then.
 * Only foundation + builtin types; self-contained.
 */
import type { ILogger } from '@cassicore/foundation'

/** JSON Schema subset for tool parameter property definitions */
export interface ToolParamProperty {
  type: string
  description?: string
  enum?: string[]
  default?: unknown
  items?: ToolParamProperty & { required?: string[]; properties?: Record<string, ToolParamProperty> }
}

/** JSON Schema subset for tool parameter definitions */
export interface ToolParamSchema {
  type: 'object'
  properties: Record<string, ToolParamProperty>
  required?: string[]
}

/** Tool category for progressive discovery */
export type ToolCategory = 'core' | 'cognitive' | 'debug' | 'coordination' | 'extended'

export interface ToolDefinition {
  name: string
  description: string
  parameters: ToolParamSchema
  /** Max execution time in ms. Default 30_000. */
  timeoutMs?: number
  /** Tool category for progressive discovery. Default: 'core' */
  category?: ToolCategory
  /** Fallback tool name to use when this tool's circuit breaker is open */
  fallbackTool?: string
  /** Whether this tool is read-only (safe for parallel execution). Default: false */
  readOnly?: boolean
  /** Whether this tool should be shown to agents/clients. Default: true */
  visibleToAgent?: boolean
  /** Backend/provider that implements this tool (e.g. cassi, serena, gitnexus, scip). */
  backend?: string
  /** Semantic capability group for routing and discovery (e.g. workspace.read, code.find_symbol). */
  capability?: string
  /** Preferred alias names that should resolve to this tool. */
  aliases?: string[]
  /** Minimum permission tier required to execute this tool. */
  requiredPermission?: 'read-only' | 'workspace-write' | 'full-access'
}

/** A single tool call parsed from the provider stream */
export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
}

export interface ToolResult {
  toolCallId: string
  toolName: string
  content: string
  isError: boolean
  /** Raw output before presentation formatting */
  rawContent?: string
  /** Tool exit code (for shell tools) */
  exitCode?: number
  /** Execution duration in ms */
  durationMs?: number
}

export type ToolHandler = (
  input: Record<string, unknown>,
  context: ToolExecutionContext,
) => Promise<string>

export interface ToolExecutionContext {
  sessionId: string
  workingDir: string
  allowedPaths: string[]
  networkAllowlist: string[]
  logger: ILogger
  registry?: unknown
  _codeStore?: unknown
  _globalBlackboardRegistry?: unknown
  _cortex?: unknown
  _memory?: unknown
  artifactNamespace?: string
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  teamId?: string
}
