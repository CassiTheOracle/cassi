import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

// Brave Search API Response Types
interface BraveWebResult {
  title: string
  url: string
  description: string
}

interface BraveSearchResponse {
  web?: {
    results?: BraveWebResult[]
  }
}

// Perplexity API Response Types
interface PerplexityChoice {
  message: {
    content: string
  }
}

interface PerplexityResponse {
  choices?: PerplexityChoice[]
  citations?: string[]
}

export const webSearchDefinition: ToolDefinition = {
  name: 'web_search',
  description: 'Search the web using Brave Search API (with Perplexity fallback). Supports single "query" or multiple "queries" (array).',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Search query string'
      },
      queries: {
        type: 'array',
        items: { type: 'string' },
        description: 'Multiple search queries to run in parallel'
      },
      count: {
        type: 'number',
        description: 'Number of results to return (1-10, default 5)',
        default: 5
      },
      country: {
        type: 'string',
        description: '2-letter country code for region-specific results (e.g., "US", "DE", "ALL")',
        default: 'US'
      },
      freshness: {
        type: 'string',
        description: 'Filter by recency: pd (past day), pw (past week), pm (past month), py (past year)',
        enum: ['pd', 'pw', 'pm', 'py']
      }
    }
  },
  timeoutMs: 30_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}

export const webSearchHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  let queries: string[] = []
  if (input['queries'] && Array.isArray(input['queries'])) {
    queries = input['queries'] as string[]
  } else if (input['query']) {
    queries = [input['query'] as string]
  }

  if (queries.length === 0) {
    return 'Error: No query or queries provided.'
  }

  const count = Math.min(Math.max((input['count'] as number | undefined) ?? 5, 1), 10)
  const country = (input['country'] as string | undefined) ?? 'US'
  const freshness = input['freshness'] as string | undefined

  // Check for API keys in environment
  const braveApiKey = process.env['BRAVE_API_KEY']
  const perplexityApiKey = process.env['PERPLEXITY_API_KEY']

  if (!braveApiKey && !perplexityApiKey) {
    return 'Error: No search API key configured. Please set BRAVE_API_KEY or PERPLEXITY_API_KEY environment variable.'
  }

  // Run all queries in parallel
  const results = await Promise.all(queries.map(async (query) => {
    // Try Brave Search first
    if (braveApiKey) {
      try {
        const res = await searchBrave(query, count, country, freshness, braveApiKey)
        return formatBraveResults(res, query)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err)
        ctx.logger.warn(`Brave Search failed for "${query}": ${errorMsg}`)

        // Fall back to Perplexity if available
        if (perplexityApiKey) {
          ctx.logger.info(`Falling back to Perplexity API for "${query}"`)
          try {
            const res = await searchPerplexity(query, count, perplexityApiKey)
            return formatPerplexityResults(res, query)
          } catch (pErr) {
            const pErrorMsg = pErr instanceof Error ? pErr.message : String(pErr)
            return `Error for "${query}": Both search providers failed. Brave: ${errorMsg}. Perplexity: ${pErrorMsg}`
          }
        }

        return `Error for "${query}": Brave Search failed and no fallback available: ${errorMsg}`
      }
    }

    // Only Perplexity available
    if (perplexityApiKey) {
      try {
        const res = await searchPerplexity(query, count, perplexityApiKey)
        return formatPerplexityResults(res, query)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err)
        return `Error for "${query}": Perplexity search failed: ${errorMsg}`
      }
    }

    return `Error for "${query}": No search API key available.`
  }))

  return results.join(`\n\n${  '='.repeat(40)  }\n\n`)
}

async function searchBrave(
  query: string,
  count: number,
  country: string,
  freshness: string | undefined,
  apiKey: string
): Promise<BraveSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    count: String(Math.min(count, 20)), // Brave max is 20
    offset: '0',
  })

  if (country && country !== 'ALL') {
    params.append('country', country)
  }

  // Brave uses 'freshness' parameter with specific values
  if (freshness) {
    const freshnessMap: Record<string, string> = {
      'pd': 'day',
      'pw': 'week',
      'pm': 'month',
      'py': 'year'
    }
    if (freshnessMap[freshness]) {
      params.append('freshness', freshnessMap[freshness])
    }
  }

  const response = await fetch(`https://api.search.brave.com/res/v1/web/search?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Accept-Encoding': 'gzip',
      'X-Subscription-Token': apiKey,
    },
    signal: AbortSignal.timeout(25_000),
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error')
    throw new Error(`HTTP ${response.status}: ${errorText}`)
  }

  return response.json() as Promise<BraveSearchResponse>
}

function formatBraveResults(response: BraveSearchResponse, query: string): string {
  const results = response.web?.results ?? []

  if (results.length === 0) {
    return `No web results found for: "${query}"`
  }

  const lines: string[] = [`Web search results for: "${query}"\n`]

  for (let i = 0; i < results.length; i++) {
    const r = results[i]
    lines.push(`${i + 1}. ${r.title}`)
    lines.push(`   URL: ${r.url}`)
    lines.push(`   ${r.description}`)
    lines.push('')
  }

  lines.push(`Provider: Brave Search (${results.length} results)`)

  return lines.join('\n')
}

async function searchPerplexity(
  query: string,
  count: number,
  apiKey: string
): Promise<PerplexityResponse> {
  const response = await fetch('https://api.perplexity.ai/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'sonar-reasoning',
      messages: [
        {
          role: 'system',
          content: 'You are a helpful search assistant. Provide accurate, up-to-date information with citations.'
        },
        {
          role: 'user',
          content: query
        }
      ],
      max_tokens: 2000,
    }),
    signal: AbortSignal.timeout(25_000),
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error')
    throw new Error(`HTTP ${response.status}: ${errorText}`)
  }

  return response.json() as Promise<PerplexityResponse>
}

function formatPerplexityResults(response: PerplexityResponse, query: string): string {
  const content = response.choices?.[0]?.message?.content
  const citations = response.citations ?? []

  if (!content) {
    return `No results found for: "${query}"`
  }

  const lines: string[] = [`Web search results for: "${query}"\n`]
  lines.push(content)

  if (citations.length > 0) {
    lines.push('\n---\nCitations:')
    for (let i = 0; i < citations.length; i++) {
      lines.push(`${i + 1}. ${citations[i]}`)
    }
  }

  lines.push('\nProvider: Perplexity AI')

  return lines.join('\n')
}
