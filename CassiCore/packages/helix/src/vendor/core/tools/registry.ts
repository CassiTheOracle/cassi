/**
 * VENDOR TYPE STUB — core/tools/registry.ts
 * Faithful type surface for helix consumers (ToolRegistry class). No runtime.
 * Re-pointed to `@cassicore/tools` at P6; delete this stub then.
 * Sibling tools/types only; self-contained.
 */
import type { ToolDefinition, ToolHandler, ToolCategory } from './types.js'

type Entry = { definition: ToolDefinition; handler: ToolHandler }

export interface ToolListOptions {
  includeHidden?: boolean
}

/** Central registry of tool definitions + handlers. */
export class ToolRegistry {
  private tools = new Map<string, Entry>()

  register(definition: ToolDefinition, handler: ToolHandler): void {
    void handler
    if (!definition.name) return
    this.tools.set(definition.name, { definition, handler })
  }

  get(name: string): Entry | undefined {
    return this.tools.get(name)
  }

  list(options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    return [...this.tools.values()]
      .map((e) => e.definition)
      .filter((d) => includeHidden || d.visibleToAgent !== false)
  }

  toAnthropicSchema(options: ToolListOptions = {}): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    return this.list(options).map((e) => ({
      name: e.name,
      description: e.description,
      input_schema: e.parameters as unknown as Record<string, unknown>,
    }))
  }

  toAnthropicSchemaAll(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    return [...this.tools.values()].map((e) => ({
      name: e.definition.name,
      description: e.definition.description,
      input_schema: e.definition.parameters as unknown as Record<string, unknown>,
    }))
  }

  toOpenAISchema(options: ToolListOptions = {}): Array<{
    type: 'function'
    function: { name: string; description: string; parameters: Record<string, unknown> }
  }> {
    return this.list(options).map((e) => ({
      type: 'function' as const,
      function: {
        name: e.name,
        description: e.description,
        parameters: e.parameters as unknown as Record<string, unknown>,
      },
    }))
  }

  toOpenAISchemaAll(): Array<{
    type: 'function'
    function: { name: string; description: string; parameters: Record<string, unknown> }
  }> {
    return [...this.tools.values()].map((e) => ({
      type: 'function' as const,
      function: {
        name: e.definition.name,
        description: e.definition.description,
        parameters: e.definition.parameters as unknown as Record<string, unknown>,
      },
    }))
  }

  getByCategory(category: ToolCategory, options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    return [...this.tools.values()]
      .filter((e) => (e.definition.category ?? 'core') === category)
      .filter((e) => includeHidden || e.definition.visibleToAgent !== false)
      .map((e) => e.definition)
  }

  getByCategories(categories: ToolCategory[], options: ToolListOptions = {}): ToolDefinition[] {
    const includeHidden = options.includeHidden ?? false
    const categorySet = new Set(categories)
    return [...this.tools.values()]
      .filter((e) => categorySet.has(e.definition.category ?? 'core'))
      .filter((e) => includeHidden || e.definition.visibleToAgent !== false)
      .map((e) => e.definition)
  }

  getDefinition(name: string): ToolDefinition | undefined {
    return this.tools.get(name)?.definition
  }
}
