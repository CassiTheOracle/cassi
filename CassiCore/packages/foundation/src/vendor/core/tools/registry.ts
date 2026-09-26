/**
 * VENDOR TYPE STUB — `core/tools/registry.ts`
 *
 * Type-only placeholder for the `ToolRegistry` class surface consumed by the P1 live-set
 * (`types/cassi-agent.ts`, `base/cognitive-module.ts`). Self-contained; builtin types only;
 * no runtime. Re-pointed to `@cassicore/tools` at P6, then deleted.
 */

/** Registry of named tool definitions + handlers. */
export class ToolRegistry {
  /** Register a tool definition + handler. */
  register(definition: ToolDefinition, handler: ToolHandler): void {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Look up a tool entry by name. */
  get(name: string): ToolEntry | undefined {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** List registered tool definitions. */
  list(options?: ToolListOptions): ToolDefinition[] {
    throw new Error('vendor stub: no runtime implementation')
  }
}

/** A tool's definition (type surface). */
export interface ToolDefinition {
  name: string
  description?: string
  parameters?: Record<string, unknown>
  requiredPermission?: string
  visibleToAgent?: boolean
  timeoutMs?: number
  fallbackTool?: string
}

/** A registered tool entry: definition + handler. */
export interface ToolEntry {
  definition: ToolDefinition
  handler: ToolHandler
}

/** A tool handler function. */
export type ToolHandler = (
  input: Record<string, unknown>,
  ctx: Record<string, unknown>,
) => Promise<unknown>

/** Options for listing tools. */
export interface ToolListOptions {
  includeHidden?: boolean
}

/** Tool category literal. */
export type ToolCategory = string
