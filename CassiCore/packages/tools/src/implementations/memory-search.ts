import type { ToolDefinition, ToolHandler } from '../types.js'
import type { IMemory } from '../../../types/intelligence.js'

export const memorySearchDefinition: ToolDefinition = {
  name: 'memory_search',
  description: 'Semantically search your memory for relevant past conversations, facts, or context.',
  parameters: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'Search query' },
      limit: { type: 'number', description: 'Maximum results to return (default 10)' },
    },
    required: ['query'],
  },
  timeoutMs: 10_000,
}

export function makeMemorySearchHandler(memory: IMemory): ToolHandler {
  return async (input) => {
    const query = input['query'] as string
    const limit = (input['limit'] as number | undefined) ?? 10

    try {
      const results = await memory.search(query, { limit })
      if (results.length === 0) return 'No relevant memories found.'

      return results
        .map((r, i) => `[${i + 1}] (score: ${r.score.toFixed(2)}) ${r.entry.content}`)
        .join('\n\n')
    } catch (err) {
      return `Error searching memory: ${String(err)}`
    }
  }
}
