/**
 * VENDOR TYPE STUB — mcp/gateway/index.ts
 * Faithful type surface for the consolidated code/browser/web tool schemas +
 * execute fns that helix-posture-runner consumes. Schema consts are real shapes
 * (pushed into tools at runtime); execute fns are throwing stubs.
 * Re-pointed to `@cassicore/tools/gateway` at P6; delete this stub then.
 */
import type { ILogger } from '@cassicore/foundation'

/** Anthropic-style tool schema shape. */
export interface ToolSchema {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/** The consolidated code-tool schema builder (read-only flag exposed to agents). */
export function getCodeConsolidatedToolSchema(readOnly: boolean): ToolSchema {
  void readOnly
  return { name: 'code', description: '', input_schema: {} } as ToolSchema
}

/** Consolidated code tool schema constant. */
export const CODE_CONSOLIDATED_TOOL: ToolSchema = {
  name: 'code',
  description: '',
  input_schema: {},
}

/** Consolidated web tool schema constant. */
export const WEB_CONSOLIDATED_TOOL: ToolSchema = {
  name: 'web',
  description: '',
  input_schema: {},
}

/** Consolidated browser tool schema constant. */
export const BROWSER_CONSOLIDATED_TOOL: ToolSchema = {
  name: 'browser',
  description: '',
  input_schema: {},
}

/** Execute a consolidated code tool call. */
export async function executeCodeConsolidatedTool(
  input: Record<string, unknown>,
  logger: ILogger,
  routeTool?: (name: string, args: Record<string, unknown>) => Promise<unknown>,
): Promise<unknown> {
  void input
  void logger
  void routeTool
  throw new Error('not connected (lands at P6 @cassicore/tools/gateway)')
}

/** Execute a consolidated browser tool call. */
export async function executeBrowserConsolidatedTool(
  input: Record<string, unknown>,
  logger: ILogger,
  routeTool?: (name: string, args: Record<string, unknown>) => Promise<unknown>,
): Promise<unknown> {
  void input
  void logger
  void routeTool
  throw new Error('not connected (lands at P6 @cassicore/tools/gateway)')
}

/** Execute a consolidated web tool call. */
export async function executeWebConsolidatedTool(
  baseUrl: string,
  input: Record<string, unknown>,
  logger: ILogger,
  routeTool?: (name: string, args: Record<string, unknown>) => Promise<unknown>,
): Promise<unknown> {
  void baseUrl
  void input
  void logger
  void routeTool
  throw new Error('not connected (lands at P6 @cassicore/tools/gateway)')
}
