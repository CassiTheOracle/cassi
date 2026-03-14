import { bus } from '../event-bus.js'
import { rootLogger } from '../logger.js'

import type { ToolDefinition, ToolHandler, ToolCategory } from './types.js'
import type { ILogger } from '../../types/interfaces.js'

const logger: ILogger = rootLogger.child('tool-registry')

type Entry = { definition: ToolDefinition; handler: ToolHandler }

export class ToolRegistry {
  private tools = new Map<string, Entry>()

  register(definition: ToolDefinition, handler: ToolHandler): void {
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

  list(): ToolDefinition[] {
    return [...this.tools.values()].map(e => e.definition)
  }

  /** Anthropic tool format for API requests */
  toAnthropicSchema(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    return [...this.tools.values()].map(e => ({
      name: e.definition.name,
      description: e.definition.description,
      input_schema: e.definition.parameters as unknown as Record<string, unknown>,
    }))
  }

  /** OpenAI function format for API requests */
  toOpenAISchema(): Array<{
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
  getByCategory(category: ToolCategory): ToolDefinition[] {
    return [...this.tools.values()]
      .filter(e => (e.definition.category ?? 'core') === category)
      .map(e => e.definition)
  }

  /** Get tools matching multiple categories */
  getByCategories(categories: ToolCategory[]): ToolDefinition[] {
    const categorySet = new Set(categories)
    return [...this.tools.values()]
      .filter(e => categorySet.has(e.definition.category ?? 'core'))
      .map(e => e.definition)
  }
}
