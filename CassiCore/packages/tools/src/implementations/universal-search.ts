import { createHash } from 'node:crypto'
import type { ToolDefinition, ToolHandler } from '../types.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { FileArtifactStore } from '../../file-artifact-store.js'

export interface UniversalSearchDeps {
  memory?: IMemory
  archive?: {
    search: (query: string, options?: any) => Promise<any[]>
    getStats?: () => Promise<any>
  }
  fileArtifactStore?: FileArtifactStore
}

export const universalSearchDefinition: ToolDefinition = {
  name: 'universal_search',
  description: 'Unified search across memory, archive, and file artifacts with intelligent deduplication. Searches CassiCore memory (conversations, facts, insights), session archive (historical turns, tool calls), and shared file artifacts returning consolidated, ranked results.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Search query - describe what you are looking for in natural language.'
      },
      sources: {
        type: 'array',
        items: { type: 'string', enum: ['memory', 'archive', 'artifacts', 'both', 'all'] },
        default: ['all'],
        description: 'Which sources to search. "both" = memory + archive (legacy), "all" = memory + archive + artifacts. Default is all.'
      },
      limit: {
        type: 'number',
        default: 15,
        description: 'Maximum total results to return (default: 15, max: 50).'
      },
      memoryLimit: {
        type: 'number',
        default: 10,
        description: 'Maximum results from memory (default: 10, max: 30).'
      },
      archiveLimit: {
        type: 'number',
        default: 10,
        description: 'Maximum results from archive (default: 10, max: 30).'
      },
      type: {
        type: 'string',
        enum: ['conversation', 'fact', 'insight', 'reflection', 'error', 'success', 'turn', 'tool_call', 'any'],
        description: 'Filter by result type. Default is any type.'
      },
      threshold: {
        type: 'number',
        default: 0.3,
        description: 'Minimum relevance score 0-1 (default: 0.3). Higher values = stricter matching.'
      },
      sessionId: {
        type: 'string',
        description: 'Optional: filter results to a specific session ID.'
      },
      deduplicate: {
        type: 'boolean',
        default: true,
        description: 'Enable intelligent deduplication using content hash + sessionId strategy.'
      },
      sortBy: {
        type: 'string',
        enum: ['relevance', 'recency', 'source'],
        default: 'relevance',
        description: 'Sort results by relevance score, recency, or grouped by source.'
      }
    },
    required: ['query']
  },
  timeoutMs: 30000
}

interface UniversalSearchInput {
  query: string
  sources?: ('memory' | 'archive' | 'artifacts' | 'both' | 'all')[]
  limit?: number
  memoryLimit?: number
  archiveLimit?: number
  type?: string
  threshold?: number
  sessionId?: string
  deduplicate?: boolean
  sortBy?: 'relevance' | 'recency' | 'source'
}

interface SearchResult {
  id: string
  source: 'memory' | 'archive' | 'artifacts'
  type: string
  content: string
  score: number
  timestamp: string
  sessionId?: string
  metadata?: Record<string, unknown>
  contentHash?: string
}

interface UniversalSearchResponse {
  query: string
  totalResults: number
  resultsReturned: number
  sources: {
    memory: {
      searched: boolean
      resultsFound: number
      error?: string
    }
    archive: {
      searched: boolean
      resultsFound: number
      error?: string
    }
    artifacts: {
      searched: boolean
      resultsFound: number
      error?: string
    }
  }
  results: SearchResult[]
  deduplication: {
    enabled: boolean
    duplicatesRemoved: number
    strategy: 'content-hash+sessionId' | 'none'
  }
  searchDurationMs: number
  error?: string
}

/**
 * @dep callers: formatArchiveResult (core/tools/implementations/universal-search.ts), formatMemoryResult (core/tools/implementations/universal-search.ts), deduplicateResults (core/tools/implementations/universal-search.ts)
 * @dep module: Implementations
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function computeContentHash(content: string): string {
  return createHash('sha256').update(content).digest('hex').slice(0, 16)
}

function deduplicateResults(results: SearchResult[]): SearchResult[] {
  const seen = new Map<string, SearchResult>()
  
  for (const result of results) {
    // Key is content hash + sessionId for deduplication
    const key = `${result.contentHash || computeContentHash(result.content)}:${result.sessionId || 'global'}`
    
    const existing = seen.get(key)
    if (!existing) {
      seen.set(key, result)
    } else if (result.score > existing.score) {
      // Keep the higher-scoring result
      seen.set(key, result)
    }
  }
  
  return Array.from(seen.values())
}

function formatMemoryResult(entry: any, score: number): SearchResult {
  return {
    id: entry.id,
    source: 'memory',
    type: entry.type,
    content: entry.content,
    score,
    timestamp: entry.createdAt?.toISOString() || new Date().toISOString(),
    sessionId: entry.metadata?.sessionId,
    metadata: entry.metadata,
    contentHash: computeContentHash(entry.content),
  }
}

function formatArchiveResult(entry: any, score: number): SearchResult {
  return {
    id: entry.id || `archive-${Date.now()}-${Math.random()}`,
    source: 'archive',
    type: entry.type || 'turn',
    content: entry.content || entry.response || JSON.stringify(entry),
    score,
    timestamp: entry.timestamp?.toISOString() || entry.createdAt?.toISOString() || new Date().toISOString(),
    sessionId: entry.sessionId,
    metadata: entry.metadata,
    contentHash: computeContentHash(entry.content || JSON.stringify(entry)),
  }
}

export function makeUniversalSearchHandler(deps: UniversalSearchDeps): ToolHandler {
  return async (input, context) => {
    const params = input as unknown as UniversalSearchInput
    const startTime = Date.now()

    const response: UniversalSearchResponse = {
      query: params.query,
      totalResults: 0,
      resultsReturned: 0,
      sources: {
        memory: { searched: false, resultsFound: 0 },
        archive: { searched: false, resultsFound: 0 },
        artifacts: { searched: false, resultsFound: 0 },
      },
      results: [],
      deduplication: {
        enabled: params.deduplicate !== false,
        duplicatesRemoved: 0,
        strategy: params.deduplicate !== false ? 'content-hash+sessionId' : 'none',
      },
      searchDurationMs: 0,
    }

    // Validate query
    if (!params.query?.trim()) {
      response.error = 'Query parameter is required'
      response.searchDurationMs = Date.now() - startTime
      return JSON.stringify(response, null, 2)
    }

    const query = params.query.trim()
    const threshold = Math.min(Math.max(params.threshold ?? 0.3, 0), 1)
    const totalLimit = Math.min(params.limit ?? 15, 50)
    const memoryLimit = Math.min(params.memoryLimit ?? 10, 30)
    const archiveLimit = Math.min(params.archiveLimit ?? 10, 30)

    // Determine which sources to search
    const sources = params.sources || ['all']
    const searchMemory = sources.includes('memory') || sources.includes('both') || sources.includes('all')
    const searchArchive = sources.includes('archive') || sources.includes('both') || sources.includes('all')
    const searchArtifacts = sources.includes('artifacts') || sources.includes('all')

    const allResults: SearchResult[] = []

    // Search memory
    if (searchMemory && deps.memory) {
      try {
        response.sources.memory.searched = true
        
        // Build search options
        const searchOptions: any = {
          limit: memoryLimit * 2, // Fetch more to filter by threshold
          threshold,
        }

        // Add type filter if specified (excluding 'any')
        if (params.type && params.type !== 'any' && params.type !== 'turn' && params.type !== 'tool_call') {
          searchOptions.type = params.type
        }

        // Add session filter if specified
        if (params.sessionId) {
          searchOptions.sessionId = params.sessionId
        }

        const memoryResults = await deps.memory.search(query, searchOptions)
        
        // Filter by threshold and format
        const filteredMemory = memoryResults
          .filter((r: any) => r.score >= threshold)
          .slice(0, memoryLimit)
          .map((r: any) => formatMemoryResult(r.entry, r.score))

        response.sources.memory.resultsFound = filteredMemory.length
        allResults.push(...filteredMemory)
      } catch (err) {
        response.sources.memory.error = String(err)
        context.logger.error('universal_search memory query failed', { error: String(err), query })
      }
    } else if (searchMemory) {
      response.sources.memory.error = 'Memory module not available'
    }

    // Search archive
    if (searchArchive && deps.archive) {
      try {
        response.sources.archive.searched = true
        
        // Build search options
        const searchOptions: any = {
          limit: archiveLimit * 2,
          query,
        }

        // Add type filter if specified for archive types
        if (params.type && params.type !== 'any') {
          if (params.type === 'turn' || params.type === 'tool_call') {
            searchOptions.type = params.type
          }
        }

        // Add session filter if specified
        if (params.sessionId) {
          searchOptions.sessionId = params.sessionId
        }

        const archiveResults = await deps.archive.search(query, searchOptions)
        
        // Filter and format (archive may not have scores, assign based on recency)
        const filteredArchive = archiveResults
          .slice(0, archiveLimit)
          .map((r: any, idx: number) => {
            // Assign score based on position (archive may not have relevance scores)
            const score = r.score || (1 - (idx / archiveLimit)) * 0.8
            return formatArchiveResult(r, score)
          })

        response.sources.archive.resultsFound = filteredArchive.length
        allResults.push(...filteredArchive)
      } catch (err) {
        response.sources.archive.error = String(err)
        context.logger.error('universal_search archive query failed', { error: String(err), query })
      }
    } else if (searchArchive) {
      response.sources.archive.error = 'Archive module not available'
    }

    // Search file artifacts
    if (searchArtifacts && deps.fileArtifactStore) {
      try {
        response.sources.artifacts.searched = true

        // List artifacts with path prefix matching the query terms
        const artifactResults = deps.fileArtifactStore.list({
          pathPrefix: undefined,    // search all paths
          includePublic: true,
          includeShared: true,
          sessionId: context.sessionId,
          limit: archiveLimit,
        })

        // Filter by query relevance: match path, tags, or namespace
        const queryLower = query.toLowerCase()
        const queryTerms = queryLower.split(/\s+/)
        const matchedArtifacts = artifactResults.filter(file => {
          const searchText = [
            file.path,
            file.namespace,
            ...file.tags,
            file.mimeType ?? '',
          ].join(' ').toLowerCase()
          return queryTerms.some(term => searchText.includes(term))
        })

        const formattedArtifacts: SearchResult[] = matchedArtifacts.map((file, idx) => ({
          id: file.id,
          source: 'artifacts' as const,
          type: 'file-artifact',
          content: `cassi://files/${file.namespace}/${file.path} [v${file.currentVersionNumber}] (${file.visibility}, tags: ${file.tags.join(', ') || 'none'})`,
          score: (1 - (idx / Math.max(matchedArtifacts.length, 1))) * 0.7,
          timestamp: new Date(file.updatedAt).toISOString(),
          sessionId: file.ownerSessionId ?? undefined,
          metadata: {
            namespace: file.namespace,
            path: file.path,
            version: file.currentVersionNumber,
            visibility: file.visibility,
            tags: file.tags,
            mimeType: file.mimeType,
            uri: `cassi://files/${file.namespace}/${file.path}`,
          },
          contentHash: computeContentHash(file.id),
        }))

        response.sources.artifacts.resultsFound = formattedArtifacts.length
        allResults.push(...formattedArtifacts)
      } catch (err) {
        response.sources.artifacts.error = String(err)
        context.logger.error('universal_search artifacts query failed', { error: String(err), query })
      }
    } else if (searchArtifacts) {
      response.sources.artifacts.error = 'FileArtifactStore not available'
    }

    // Deduplicate if enabled
    let finalResults = allResults
    if (params.deduplicate !== false) {
      const beforeCount = allResults.length
      finalResults = deduplicateResults(allResults)
      response.deduplication.duplicatesRemoved = beforeCount - finalResults.length
    }

    // Sort results
    if (params.sortBy === 'recency') {
      finalResults.sort((a, b) => 
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
    } else if (params.sortBy === 'source') {
      // Group by source, then by relevance within each source
      finalResults.sort((a, b) => {
        if (a.source !== b.source) {
          return a.source === 'memory' ? -1 : 1
        }
        return b.score - a.score
      })
    } else {
      // Default: sort by relevance
      finalResults.sort((a, b) => b.score - a.score)
    }

    // Apply total limit
    finalResults = finalResults.slice(0, totalLimit)

    // Build final response
    response.totalResults = response.sources.memory.resultsFound + response.sources.archive.resultsFound + response.sources.artifacts.resultsFound
    response.resultsReturned = finalResults.length
    response.results = finalResults
    response.searchDurationMs = Date.now() - startTime

    return JSON.stringify(response, null, 2)
  }
}
