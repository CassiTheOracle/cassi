/**
 * Context Assembler — One-shot context preparation for delegated agents.
 *
 * Takes a task description, extracts keywords, runs hybrid search via GitNexus,
 * and assembles ranked file context within a token budget.
 *
 * Designed for Dyad workers, Flux cells, and other delegated agents that need
 * code context without making multiple round-trips.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { PreparedContext, PreparedFile, PrepareContextOptions } from './types.js'
import { withAutoReindex } from './gitnexus-bridge.js'

/** Rough chars-per-token estimate (aligned with Dyad context-curator). */
const CHARS_PER_TOKEN = 3.5

/** Stop-words to filter from keyword extraction. */
const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'ought',
  'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it',
  'they', 'them', 'their', 'this', 'that', 'these', 'those',
  'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as',
  'into', 'through', 'during', 'before', 'after', 'above', 'below',
  'and', 'but', 'or', 'not', 'if', 'then', 'else', 'when', 'while',
  'all', 'each', 'every', 'both', 'few', 'more', 'most', 'some', 'any',
  'how', 'what', 'which', 'who', 'where', 'why',
  'add', 'change', 'update', 'fix', 'implement', 'create', 'make',
  'use', 'using', 'file', 'code', 'function', 'class', 'method',
])

/**
 * Extract meaningful keywords from a task description.
 */
export function extractKeywords(task: string): string[] {
  // Extract camelCase/PascalCase identifiers
  const identifiers = task.match(/[A-Z][a-zA-Z0-9]+|[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*/g) || []

  // Extract file paths
  const paths = task.match(/[\w/.-]+\.\w{1,4}/g) || []

  // Extract quoted strings
  const quoted = task.match(/["'`]([^"'`]+)["'`]/g)?.map(s => s.slice(1, -1)) || []

  // Extract remaining meaningful words (3+ chars, not stop words)
  const words = task
    .replace(/[^\w\s-]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length >= 3 && !STOP_WORDS.has(w.toLowerCase()))
    .map(w => w.toLowerCase())

  // Deduplicate preserving order
  const seen = new Set<string>()
  const result: string[] = []

  for (const kw of [...identifiers, ...paths, ...quoted, ...words]) {
    const lower = kw.toLowerCase()
    if (!seen.has(lower)) {
      seen.add(lower)
      result.push(kw)
    }
  }

  return result.slice(0, 15) // Cap at 15 keywords
}

/** Default timeout for prepare_context (30s). */
const DEFAULT_PREPARE_TIMEOUT_MS = 30_000

/**
 * Assemble context for a task using GitNexus hybrid search.
 *
 * WHY: withAutoReindex can block for minutes (ensureFreshIndex up to 300s,
 * query up to 120s, retry-reindex another 300s). Without a timeout cap,
 * the caller hangs indefinitely. On timeout we return a degraded result
 * with extracted keywords but no files — still useful for delegation.
 */
export async function prepareContext(
  router: (tool: string, args: any) => Promise<any>,
  options: PrepareContextOptions,
  logger: ILogger,
): Promise<PreparedContext> {
  const {
    task,
    tokenBudget = 8000,
    includeContent = true,
    scope,
    repo,
    timeoutMs = DEFAULT_PREPARE_TIMEOUT_MS,
  } = options

  const keywords = extractKeywords(task)
  const charBudget = tokenBudget * CHARS_PER_TOKEN
  let usedChars = 0

  logger.debug('Preparing context', { keywords, tokenBudget, timeoutMs })

  const files: PreparedFile[] = []
  let summary = ''

  // Run GitNexus query for execution flows, with a timeout cap
  try {
    const queryPromise = withAutoReindex(
      () => router('gitnexus_query', {
        query: keywords.join(' '),
        goal: task,
        task_context: task,
        include_content: includeContent,
        limit: 8,
        max_symbols: 6,
        repo,
      }),
      logger,
    )

    const queryResult = await Promise.race([
      queryPromise,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`prepare_context timed out after ${timeoutMs}ms`)), timeoutMs)
      ),
    ])

    // Parse GitNexus query result
    const parsed = parseQueryResult(queryResult)

    for (const item of parsed) {
      if (scope && !item.filePath.startsWith(scope)) continue

      const excerpt = includeContent ? item.content?.slice(0, 500) : undefined
      const excerptChars = excerpt?.length || 0

      if (usedChars + excerptChars > charBudget) {
        // Over budget — add without content
        files.push({
          filePath: item.filePath,
          reason: item.reason,
          relevance: item.relevance,
          keySymbols: item.symbols,
        })
        continue
      }

      usedChars += excerptChars + item.filePath.length + 50 // overhead
      files.push({
        filePath: item.filePath,
        reason: item.reason,
        relevance: item.relevance,
        keySymbols: item.symbols,
        excerpt,
      })
    }

    // Build summary from top results
    const topFiles = files.slice(0, 5).map(f => f.filePath.split('/').pop()).join(', ')
    summary = `Key code surface for "${task.slice(0, 80)}": ${files.length} relevant files found. Top files: ${topFiles}. Primary symbols: ${files.flatMap(f => f.keySymbols).slice(0, 8).join(', ')}.`

  } catch (err) {
    const errMsg = String(err)
    const isTimeout = errMsg.includes('timed out')
    logger.warn(isTimeout ? 'Context preparation timed out' : 'GitNexus query failed during context preparation', { error: errMsg, timeoutMs })
    summary = isTimeout
      ? `Context preparation timed out after ${timeoutMs}ms. Keywords extracted: ${keywords.join(', ')}`
      : `Context preparation partially failed: ${errMsg}. Keywords extracted: ${keywords.join(', ')}`
  }

  return {
    summary,
    files,
    estimatedTokens: Math.ceil(usedChars / CHARS_PER_TOKEN),
    extractedKeywords: keywords,
  }
}

/**
 * Parse GitNexus query result into a uniform shape.
 */
function parseQueryResult(result: any): Array<{
  filePath: string
  reason: string
  relevance: number
  symbols: string[]
  content?: string
}> {
  const items: Array<{
    filePath: string
    reason: string
    relevance: number
    symbols: string[]
    content?: string
  }> = []

  if (!result) return items

  // Handle structured result (processes + process_symbols)
  const output = typeof result === 'string' ? result : (result.output || result.markdown || JSON.stringify(result))

  // Try to parse as JSON first
  try {
    const parsed = typeof result === 'string' ? JSON.parse(result) : result
    if (parsed.processes) {
      for (const proc of parsed.processes) {
        const symbols = (proc.symbols || parsed.process_symbols || [])
          .filter((s: any) => s.processName === proc.name || !proc.name)
          .slice(0, 5)

        for (const sym of symbols) {
          if (!sym.filePath) continue
          items.push({
            filePath: sym.filePath,
            reason: `Part of execution flow: ${proc.name || proc.heuristicLabel || 'unknown'}`,
            relevance: proc.relevance || 0.5,
            symbols: [sym.name || sym.symbolName].filter(Boolean),
            content: sym.content,
          })
        }
      }
    }
    if (parsed.definitions) {
      for (const def of parsed.definitions) {
        items.push({
          filePath: def.filePath,
          reason: `Type/interface definition`,
          relevance: 0.4,
          symbols: [def.name].filter(Boolean),
          content: def.content,
        })
      }
    }
  } catch {
    // Not JSON — parse as markdown
    // Extract file paths from markdown output
    const pathMatches = output.match(/[\w/.-]+\.(?:ts|js|tsx|jsx)/g) || []
    const seen = new Set<string>()
    for (const p of pathMatches) {
      if (seen.has(p)) continue
      seen.add(p)
      items.push({
        filePath: p,
        reason: 'Found in search results',
        relevance: 0.5,
        symbols: [],
      })
    }
  }

  // Deduplicate by filePath, keeping highest relevance
  const byPath = new Map<string, typeof items[0]>()
  for (const item of items) {
    const existing = byPath.get(item.filePath)
    if (!existing || item.relevance > existing.relevance) {
      if (existing) {
        // Merge symbols
        item.symbols = [...new Set([...existing.symbols, ...item.symbols])]
      }
      byPath.set(item.filePath, item)
    }
  }

  return [...byPath.values()].sort((a, b) => b.relevance - a.relevance)
}
