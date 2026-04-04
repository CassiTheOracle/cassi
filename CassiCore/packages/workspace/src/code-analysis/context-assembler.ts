/**
 * Context Assembler — One-shot context preparation for delegated agents.
 *
 * Takes a task description, extracts keywords, runs hybrid search via GitNexus,
 * and assembles ranked file context within a token budget.
 *
 * Designed for Dyad workers, Flux cells, and other delegated agents that need
 * code context without making multiple round-trips.
 *
 * WHY: Two-tier approach instead of blocking on withAutoReindex:
 *  - Stage 1: Query GitNexus directly (stale index is fine, no blocking reindex)
 *  - Stage 2: Fall back to git-grep keyword search if GitNexus unavailable/fails
 *  - Background: Trigger non-blocking reindex if index is stale
 * This guarantees a useful result within the timeout even when GitNexus is
 * analyzing or the index doesn't exist yet.
 */

import { exec } from 'node:child_process'
import { promisify } from 'node:util'
import type { ILogger } from '../../../types/interfaces.js'
import type { PreparedContext, PreparedFile, PrepareContextOptions } from './types.js'
import { isIndexAvailable, ensureFreshIndexBackground } from './gitnexus-bridge.js'

const execAsync = promisify(exec)

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
 * Assemble context for a task using a two-tier search strategy.
 *
 * WHY: The old approach used withAutoReindex which blocks on ensureFreshIndex
 * (up to 300s for reindex + 120s for query + 300s for retry-reindex). Even
 * with a Promise.race timeout, the degraded result was just keywords with no
 * files — useless for delegation.
 *
 * New approach:
 *  1. If GitNexus index exists (even stale), query it directly — no blocking
 *     reindex. A stale index is better than no index.
 *  2. If GitNexus is unavailable or the query fails/times out, fall back to
 *     git-grep keyword search which always works and is fast.
 *  3. Trigger a background reindex if the index is stale, so it's fresh next time.
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
  let source = 'none'

  // Allocate time budgets: 60% for GitNexus attempt, 35% for grep fallback
  const gnxTimeout = Math.floor(timeoutMs * 0.6)
  const grepTimeout = Math.floor(timeoutMs * 0.35)

  // --- Stage 1: Try GitNexus (non-blocking freshness) ---
  if (isIndexAvailable()) {
    // Trigger background reindex if stale — does NOT block
    ensureFreshIndexBackground(logger)

    try {
      const queryResult = await Promise.race([
        router('gitnexus_query', {
          query: keywords.join(' '),
          goal: task,
          task_context: task,
          include_content: includeContent,
          limit: 8,
          max_symbols: 6,
          repo,
        }),
        rejectAfterMs(gnxTimeout, 'GitNexus query'),
      ])

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

      if (files.length > 0) source = 'GitNexus'
    } catch (err) {
      logger.debug('GitNexus query failed or timed out, falling back to grep', { error: String(err) })
    }
  } else {
    logger.debug('GitNexus index not available, using grep fallback')
    // Trigger background reindex so the index exists next time
    ensureFreshIndexBackground(logger)
  }

  // --- Stage 2: Grep fallback if GitNexus didn't produce results ---
  if (files.length === 0) {
    try {
      const grepResults = await grepFallback(keywords, scope, grepTimeout, logger)

      for (const gf of grepResults) {
        if (usedChars > charBudget) break

        files.push({
          filePath: gf.filePath,
          reason: `Matched ${gf.matchCount} keyword(s) via text search`,
          relevance: Math.min(1, gf.matchCount / Math.max(keywords.length, 1)),
          keySymbols: [],
        })
        usedChars += gf.filePath.length + 80
      }

      if (files.length > 0) source = 'text search'
    } catch (err) {
      logger.warn('Grep fallback also failed', { error: String(err) })
    }
  }

  // Build summary
  if (files.length > 0) {
    const topFiles = files.slice(0, 5).map(f => f.filePath.split('/').pop()).join(', ')
    const symbolList = files.flatMap(f => f.keySymbols).slice(0, 8).join(', ')
    summary = `Key code surface for "${task.slice(0, 80)}": ${files.length} relevant files found via ${source}. Top files: ${topFiles}. Primary symbols: ${symbolList || 'none (text search only)'}.`
  } else {
    summary = `No files found for "${task.slice(0, 80)}". Keywords extracted: ${keywords.join(', ')}`
  }

  return {
    summary,
    files,
    estimatedTokens: Math.ceil(usedChars / CHARS_PER_TOKEN),
    extractedKeywords: keywords,
  }
}

/** Reject after `ms` milliseconds with a descriptive error. */
function rejectAfterMs(ms: number, label: string): Promise<never> {
  return new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
  )
}

/**
 * Grep-based fallback for context assembly when GitNexus is unavailable.
 *
 * WHY: git-grep is universally available, respects .gitignore, and completes
 * in <1s even on large repos. The results are less semantically rich than
 * GitNexus (no execution flows, no symbol context) but always produce
 * *something* useful for delegation — ranked files that mention the keywords.
 */
async function grepFallback(
  keywords: string[],
  scope: string | undefined,
  timeoutMs: number,
  logger: ILogger,
): Promise<Array<{ filePath: string; matchCount: number }>> {
  const searchKeywords = keywords.slice(0, 5)
  const perKeywordTimeout = Math.min(3000, Math.floor(timeoutMs / Math.max(searchKeywords.length, 1)))
  const fileMatches = new Map<string, number>()

  for (const keyword of searchKeywords) {
    if (keyword.length < 2) continue

    try {
      // Escape special regex chars for safe shell interpolation
      const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      // WHY: Using -- pathspec to restrict to code files. When scope is given,
      // search within that directory. Otherwise search all TS/JS/TSX/JSX files.
      const pathSpec = scope
        ? `-- "${scope}"`
        : '-- "*.ts" "*.tsx" "*.js" "*.jsx"'

      const { stdout } = await execAsync(
        `git grep -l -i -- "${escaped}" ${pathSpec}`,
        { timeout: perKeywordTimeout, encoding: 'utf-8' },
      )

      for (const file of stdout.trim().split('\n').filter(Boolean)) {
        fileMatches.set(file, (fileMatches.get(file) || 0) + 1)
      }
    } catch {
      // git grep returns exit code 1 when no matches — expected
    }
  }

  const results = [...fileMatches.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([filePath, matchCount]) => ({ filePath, matchCount }))

  if (results.length > 0) {
    logger.debug('Grep fallback found files', { count: results.length, topFile: results[0].filePath })
  }

  return results
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
