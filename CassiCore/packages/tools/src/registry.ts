import type { ToolDefinition, ToolHandler } from './types.js'

type Entry = { definition: ToolDefinition; handler: ToolHandler }

export class ToolRegistry {
  private tools = new Map<string, Entry>()

  register(definition: ToolDefinition, handler: ToolHandler): void {
    this.tools.set(definition.name, { definition, handler })
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
}
