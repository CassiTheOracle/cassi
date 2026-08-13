/** VENDORED TYPE STUB — mirrors `tools/executor.js`. Surface: ToolExecutor. */
export interface ToolCall {
  id?: string
  name: string
  input?: Record<string, unknown>
  arguments?: Record<string, unknown>
  [key: string]: unknown
}
export interface ToolResult {
  toolCallId?: string
  toolName?: string
  content: string
  isError: boolean
  [key: string]: unknown
}
export interface ToolExecutor {
  execute(toolCall: ToolCall, sessionId: string): Promise<ToolResult>
  executeAll(toolCalls: ToolCall[], sessionId: string): Promise<ToolResult[]>
  [key: string]: unknown
}
