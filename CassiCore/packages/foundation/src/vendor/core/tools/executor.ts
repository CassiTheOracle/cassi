/**
 * VENDOR TYPE STUB — `core/tools/executor.ts`
 *
 * Type-only placeholder for the `ToolExecutor` class surface consumed by the P1 live-set
 * (`types/cassi-agent.ts`, `base/cognitive-module.ts`). Self-contained; builtin types only;
 * no runtime. Re-pointed to `@cassicore/tools` at P6, then deleted.
 */

/** Executor that runs tools through the registry with safety + permission gating. */
export class ToolExecutor {
  /** Resolve a tool's registry entry and run it for a session. */
  execute(
    call: ToolCall,
    sessionId: string,
    opts?: { workingDir?: string },
  ): Promise<ToolResult> {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Execute up to the concurrency limit with error isolation. */
  executeAll(calls: ToolCall[], sessionId: string): Promise<ToolResult[]> {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Whether a tool is registered and available. */
  isAvailable(name: string): boolean {
    throw new Error('vendor stub: no runtime implementation')
  }
}

/** A structured tool call. */
export interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
}

/** The result of a tool execution. */
export interface ToolResult {
  toolCallId: string
  toolName: string
  content: string
  isError: boolean
  rawContent?: string
  exitCode?: number
  durationMs?: number
}

/** Execution context passed to a tool handler. */
export interface ToolExecutionContext {
  sessionId: string
  logger: { child(name: string): unknown }
  workingDir?: string
  sessionType?: string
  _cortex?: unknown
}
