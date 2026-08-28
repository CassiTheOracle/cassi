/**
 * List Tools — Meta-discovery tool for progressive tool discovery
 * 
 * This tool allows the agent to discover tools that are not currently
 * visible in the progressive discovery context. It lists all available
 * tools with their descriptions, optionally filtered by category.
 * 
 * Usage:
 * - When the agent needs a tool but it's not in the current context
 * - To explore what capabilities are available
 * - During early conversation turns for tool discovery
 */

import type { ToolDefinition, ToolHandler, ToolCategory } from '../types.js'

export const listToolsDefinition: ToolDefinition = {
  name: 'list_tools',
  description: 'List all available tools with their descriptions. Use this to discover tools not visible in the current context.',
  parameters: {
    type: 'object',
    properties: {
      category: {
        type: 'string',
        description: 'Filter by category: all, core, cognitive, debug, coordination, extended',
        enum: ['all', 'core', 'cognitive', 'debug', 'coordination', 'extended'],
        default: 'all',
      },
    },
    required: [],
  },
  timeoutMs: 5_000,
  category: 'debug',
  requiredPermission: 'read-only',
}

export const listToolsHandler: ToolHandler = async (input, ctx) => {
  const category = (input['category'] as string | undefined) ?? 'all'
  
  // Get the registry from context (injected by the tool executor)
  const registry = (ctx as any).registry
  if (!registry) {
    return 'Error: Tool registry not available. This tool requires the ToolRegistry to be injected.'
  }

  const tools: ToolDefinition[] = category === 'all'
    ? registry.list()
    : registry.getByCategory(category as ToolCategory)

  if (tools.length === 0) {
    return `No tools found in category '${category}'.`
  }

  // Group tools by category for better readability
  const toolsByCategory = new Map<ToolCategory, ToolDefinition[]>()
  for (const tool of tools) {
    const cat = tool.category ?? 'core'
    if (!toolsByCategory.has(cat)) {
      toolsByCategory.set(cat, [])
    }
    toolsByCategory.get(cat)!.push(tool)
  }

  const lines: string[] = []
  lines.push('# Available Tools')
  lines.push('')

  // Sort categories in a logical order
  const categoryOrder: ToolCategory[] = ['core', 'cognitive', 'coordination', 'debug', 'extended']
  
  for (const cat of categoryOrder) {
    const catTools = toolsByCategory.get(cat)
    if (!catTools || catTools.length === 0) continue

    lines.push(`## ${capitalize(cat)} Tools (${catTools.length})`)
    lines.push('')
    
    for (const tool of catTools) {
      lines.push(`### ${tool.name}`)
      lines.push(`${tool.description}`)
      lines.push('')
    }
  }

  return lines.join('\n')
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
