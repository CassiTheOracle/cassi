/** VENDORED TYPE STUB — mirrors `tools/types.js` (core/tools). Surface: ToolDefinition, ToolHandler, ToolSchema. */
export interface ToolDefinition {
  name: string
  description?: string
  handler?: ToolHandler
  [key: string]: unknown
}
export interface ToolHandler {
  (input: Record<string, unknown>, ...rest: unknown[]): Promise<unknown> | unknown
}
/** Anthropic-style tool schema emitted by ToolRegistry.toAnthropicSchema(). */
export interface ToolSchema {
  name: string
  description?: string
  input_schema?: Record<string, unknown>
  [key: string]: unknown
}
