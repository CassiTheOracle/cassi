import type { IMemory, MemoryEntry, SearchResult } from "@cassicore/foundation"
import type { ToolDefinition, ToolHandler } from '../types.js'

export const memorySearchDefinition: ToolDefinition = {
  name: 'memory_search',
  description: 'Search CassiCore memory for relevant information from past conversations, facts, or insights. Uses full-text search (FTS5) for fast semantic retrieval.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'What to search for - describe the information you need in natural language'
      },
      limit: {
        type: 'number',
        description: 'Maximum number of results to return (default: 5, max: 20)'
      },
      type: {
        type: 'string',
        enum: ['conversation', 'fact', 'insight', 'reflection', 'error', 'success'],
        description: 'Optional: filter by memory type'
      },
      threshold: {
        type: 'number',
        description: 'Minimum relevance score 0-1 (default: 0.3). Higher values = more strict matching'
      }
    },
    required: ['query'],
  },
  timeoutMs: 15_000,
  category: 'cognitive',
  requiredPermission: 'read-only',
}

interface MemorySearchInput {
  query: string
  limit?: number
  type?: MemoryEntry['type']
  threshold?: number
}

/**
 * @dep callers: makeMemorySearchHandler (core/tools/implementations/memory-search.ts)
 * @dep flows: RegisterCoreTools → FormatMemoryResult (3/3)
 * @dep module: Memory
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function formatMemoryResult(result: SearchResult, index: number): string {
  const entry = result.entry
  const score = result.score
  const date = entry.createdAt.toLocaleString()
  const type = entry.type
  const metadata = entry.metadata ? Object.entries(entry.metadata).map(([k, v]) => `${k}=${v}`).join(', ') : ''

  const importancePart = entry.importance !== undefined ? ` imp:${entry.importance.toFixed(1)}` : ''
  const pinnedPart = entry.pinned ? ' [PINNED]' : ''
  const confidencePart = result.confidence ? ` [${result.confidence.toUpperCase()}]` : ''

  let output = `[${index + 1}] ${type.toUpperCase()} (relevance: ${(score * 100).toFixed(0)}%${importancePart}${pinnedPart}${confidencePart}, ${date})`
  if (metadata) {
    output += `\n    meta: {${metadata}}`
  }
  output += `\n    ${entry.content.slice(0, 500)}${entry.content.length > 500 ? '...' : ''}`
  return output
}

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts)
 * @dep calls: search, trim, formatMemoryResult
 * @dep flows: RegisterCoreTools → EstimateChars (2/4), RegisterCoreTools → FormatMemoryResult (2/3)
 * @dep module: Memory
 * @dep risk: LOW | 1 caller, 2 flows, 1 module
 */

export function makeMemorySearchHandler(memory: IMemory): ToolHandler {
  return async (input, context) => {
    const params = input as unknown as MemorySearchInput
    const query = params.query?.trim()

    if (!query) {
      return 'Error: query parameter is required'
    }

    const limit = Math.min(Math.max(params.limit ?? 5, 1), 20)
    const threshold = Math.min(Math.max(params.threshold ?? 0.3, 0), 1)
    const typeFilter = params.type

    try {
      // Search the memory module
      const results = await memory.search(query, {
        limit: limit * 2, // Fetch more to filter by threshold
        type: typeFilter,
      })

      // Filter by threshold and limit
      const filteredResults = results
        .filter(r => r.score >= threshold)
        .slice(0, limit)

      if (filteredResults.length === 0) {
        // Try a broader search with no threshold
        const allResults = await memory.search(query, { limit: 3 })
        if (allResults.length === 0) {
          return `No memories found matching "${query}".`
        }
        return `No strong matches found for "${query}" (threshold: ${threshold}).\n\nClosest results:\n\n${ 
          allResults.slice(0, 3).map((r, i) => formatMemoryResult(r, i)).join('\n\n')}`
      }

      // Format results
      const formatted = filteredResults.map((r, i) => formatMemoryResult(r, i)).join('\n\n')

      return `Found ${filteredResults.length} memory(s) matching "${query}":\n\n${formatted}`

    } catch (err) {
      context.logger.error('memory_search tool failed', { error: String(err), query })
      return `Error searching memory: ${String(err)}`
    }
  }
}

// Additional tool: remember (store a fact)
export const rememberDefinition: ToolDefinition = {
  name: 'remember',
  description: 'Store a note in CassiCore memory for future recall via memory_search.',
  parameters: {
    type: 'object',
    properties: {
      note: {
        type: 'string',
        description: 'The information to remember - be clear and specific'
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Optional tags to categorize this memory'
      },
      importance: {
        type: 'number',
        description: 'Importance score 0-10 (default: 5.5 for facts). Higher values surface this memory more prominently in search results.'
      },
      pinned: {
        type: 'boolean',
        description: 'If true, this memory will never decay or be archived by the Dreamer. Automatically sets importance to at least 9.0.'
      }
    },
    required: ['note'],
  },
  timeoutMs: 5_000,
  category: 'cognitive',
}

export function makeRememberHandler(memory: IMemory): ToolHandler {
  return async (input, context) => {
    const note = input['note'] as string
    const tags = (input['tags'] as string[] | undefined) ?? []
    const importance = input['importance'] as number | undefined
    const pinned = input['pinned'] as boolean | undefined

    if (!note?.trim()) {
      return 'Error: note parameter is required'
    }

    try {
      const storeEntry: Omit<MemoryEntry, 'id' | 'createdAt'> & { importance?: number; pinned?: boolean } = {
        type: 'fact',
        content: note,
        metadata: { tags, sessionId: context.sessionId },
        ...(importance !== undefined ? { importance } : {}),
        ...(pinned !== undefined ? { pinned } : {}),
      }

      const id = await memory.store(storeEntry as any)

      const pinnedNote = pinned ? ' (pinned — decay-resistant)' : ''
      const impNote = importance !== undefined ? ` importance=${importance.toFixed(1)}` : ''
      return `✓ Stored memory (id: ${id}${impNote}${pinnedNote})`
    } catch (err) {
      context.logger.error('remember tool failed', { error: String(err) })
      return `Error storing memory: ${String(err)}`
    }
  }
}
