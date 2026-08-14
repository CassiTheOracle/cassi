import { bus } from './vendor/core/event-bus.js'
import { rootLogger } from './vendor/core/logger.js'

import type { ToolDefinition, ToolHandler, ToolCategory } from './types.js'
import type { ILogger } from "@cassicore/foundation"

const logger: ILogger = rootLogger.child('tool-registry')

type Entry = { definition: ToolDefinition; handler: ToolHandler }

export interface ToolListOptions {
  includeHidden?: boolean
}

/**
 * @dep callers: getByCategories (core/tools/registry.ts), getByCategory (core/tools/registry.ts), list (core/tools/registry.ts)
 * @dep module: Tools
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function isVisibleToAgent(definition: ToolDefinition): boolean {
  return definition.visibleToAgent !== false
}

export class ToolRegistry {
  private tools = new Map<string, Entry>()

  register(definition: ToolDefinition, handler: ToolHandler): void {
    if (!definition.name) {
      logger.warn('Skipping tool registration: empty or missing name', {
        description: definition.description?.slice(0, 80),
      })
      return
    }
    const existed = this.tools.has(definition.name)
    this.tools.set(definition.name, { definition, handler })

    // Emit a lightweight event so other subsystems (e.g., multi-agent) can
    // react to newly-available tools in real-time.
    try {
      if (!existed) {
        const server = definition.name.includes('__') ? definition.name.split('__')[0] : undefined
        bus.emit({
          type: 'tool:registered',
          name: definition.name,
          description: definition.description,
          parameters: (definition.parameters as unknown) ?? {},
          server,
        } as any)
      }
    } catch (err) {
      // Best-effort: do not fail registration if event emission fails
      logger.warn('failed to emit tool:registered event', { error: String(err) })
    }
  }

  get(name: string): Entry | undefined {
    return this.tools.get(name)
  }

  list(options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    return [...this.tools.values()]
      .map(e => e.definition)
      .filter(definition => includeHidden || isVisibleToAgent(definition))
  }

  /** Anthropic tool format for API requests */
  toAnthropicSchema(options: ToolListOptions = {}): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    return this.list(options).map(e => ({
      name: e.name,
      description: e.description,
      input_schema: e.parameters as unknown as Record<string, unknown>,
    }))
  }

  /** Anthropic tool format for API requests, including hidden/internal tools. */
  toAnthropicSchemaAll(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    return [...this.tools.values()].map(e => ({
      name: e.definition.name,
      description: e.definition.description,
      input_schema: e.definition.parameters as unknown as Record<string, unknown>,
    }))
  }

  /** OpenAI function format for API requests */
  toOpenAISchema(options: ToolListOptions = {}): Array<{
    type: 'function';
    function: { name: string; description: string; parameters: Record<string, unknown> };
  }> {
    return this.list(options).map(e => ({
      type: 'function' as const,
      function: {
        name: e.name,
        description: e.description,
        parameters: e.parameters as unknown as Record<string, unknown>,
      },
    }))
  }

  /** OpenAI function format for API requests, including hidden/internal tools. */
  toOpenAISchemaAll(): Array<{
    type: 'function';
    function: { name: string; description: string; parameters: Record<string, unknown> };
  }> {
    return [...this.tools.values()].map(e => ({
      type: 'function' as const,
      function: {
        name: e.definition.name,
        description: e.definition.description,
        parameters: e.definition.parameters as unknown as Record<string, unknown>,
      },
    }))
  }

  /** Get tools by category */
  getByCategory(category: ToolCategory, options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    return [...this.tools.values()]
      .filter(e => (e.definition.category ?? 'core') === category)
      .filter(e => includeHidden || isVisibleToAgent(e.definition))
      .map(e => e.definition)
  }

  /** Get tools matching multiple categories */
  getByCategories(categories: ToolCategory[], options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    const categorySet = new Set(categories)
    return [...this.tools.values()]
      .filter(e => categorySet.has(e.definition.category ?? 'core'))
      .filter(e => includeHidden || isVisibleToAgent(e.definition))
      .map(e => e.definition)
  }

  /** Get tool definition by name */
  getDefinition(name: string): ToolDefinition | undefined {
    const entry = this.tools.get(name)
    return entry?.definition
  }
}
