/**
 * Context Assembler — One-shot context preparation for delegated agents.
 *
 * Takes a task description, extracts keywords, runs hybrid search via GitNexus,
 * and assembles ranked file context within a token budget.
 *
 * Designed for Dyad workers, Flux cells, and other delegated agents that need
 * code context without making multiple round-trips.
 *
 * WHY: Hybrid merge approach instead of blocking on withAutoReindex:
 *  - Run GitNexus graph query and git-grep keyword search concurrently
 *  - Merge results: files found by both sources get a relevance boost
 *  - GitNexus contributes execution-flow context and symbol names
 *  - Grep contributes keyword-match precision for literal terms
 *  - Background: Trigger non-blocking reindex if index is stale
 * This guarantees relevant results within the timeout even when GitNexus
 * returns low-relevance matches or is unavailable.
 */

import { exec } from 'node:child_process'
import { promisify } from 'node:util'
import type { ILogger } from '../../../types/interfaces.js'
import type { PreparedContext, PreparedFile, PrepareContextOptions } from './types.js'
import { isIndexAvailable, ensureFreshIndexBackground, safeParseJson } from './gitnexus-bridge.js'

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
 * Assemble context for a task using hybrid search (GitNexus + grep merged).
 *
 * WHY: The old two-tier approach (try GitNexus, fall back to grep) had a flaw:
 * when GitNexus returned low-relevance semantic matches, grep never ran — even
 * though grep would have found the actual files. The hybrid approach runs both
 * concurrently and merges results, so keyword-precise grep results combine with
 * GitNexus's execution-flow context for the best overall ranking.
 *
 * How it works:
 *  1. Launch GitNexus query and git-grep concurrently (both time-budgeted)
 *  2. Merge into a single file map — files found by both sources get a boost
 *  3. GitNexus contributes: execution flow context, symbol names, content excerpts
 *  4. Grep contributes: keyword match counts (high precision for literal terms)
 *  5. Background: trigger reindex if index is stale, so it's fresh next time
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

  logger.debug('Preparing context', { keywords, tokenBudget, timeoutMs })

  // Trigger background reindex if needed (never blocks)
  ensureFreshIndexBackground(logger)

  // Time budgets: 70% shared (both run concurrently), leaves 30% for merge + assembly
  const searchTimeout = Math.floor(timeoutMs * 0.7)

  // --- Run both searches concurrently ---
  type GnxItem = { filePath: string; reason: string; relevance: number; symbols: string[]; content?: string }
  type GrepItem = { filePath: string; matchCount: number }

  const gnxPromise: Promise<GnxItem[]> = isIndexAvailable()
    ? Promise.race([
      router('gitnexus_query', {
        query: keywords.join(' '),
        goal: task,
        task_context: task,
        include_content: includeContent,
        limit: 8,
        max_symbols: 6,
        repo,
      }).then(parseQueryResult),
      rejectAfterMs(searchTimeout, 'GitNexus query'),
    ]).catch(err => {
      logger.debug('GitNexus query failed or timed out', { error: String(err) })
      return [] as GnxItem[]
    })
    : Promise.resolve([] as GnxItem[])

  const grepPromise: Promise<GrepItem[]> = grepFallback(keywords, scope, searchTimeout, logger)
    .catch(err => {
      logger.debug('Grep search failed', { error: String(err) })
      return [] as GrepItem[]
    })

  const [gnxResults, grepResults] = await Promise.all([gnxPromise, grepPromise])

  // --- Merge results into a unified file map ---
  const merged = new Map<string, {
    relevance: number
    reason: string
    symbols: string[]
    content?: string
    sources: ('graph' | 'grep')[]
    grepMatches: number
  }>()

  // Add GitNexus results
  for (const item of gnxResults) {
    if (scope && !item.filePath.startsWith(scope)) continue
    merged.set(item.filePath, {
      relevance: item.relevance,
      reason: item.reason,
      symbols: item.symbols,
      content: item.content,
      sources: ['graph'],
      grepMatches: 0,
    })
  }

  // Merge grep results — boost files found by both
  for (const gf of grepResults) {
    if (scope && !gf.filePath.startsWith(scope)) continue

    const grepRelevance = Math.min(1, gf.matchCount / Math.max(keywords.length, 1))
    const existing = merged.get(gf.filePath)

    if (existing) {
      // WHY: File found by both sources — boost relevance by 20% (capped at 1.0)
      // and combine metadata. This rewards files that are both semantically
      // relevant (GitNexus) AND textually match the keywords (grep).
      existing.relevance = Math.min(1, Math.max(existing.relevance, grepRelevance) * 1.2)
      existing.sources.push('grep')
      existing.grepMatches = gf.matchCount
      existing.reason = `${existing.reason} + matched ${gf.matchCount} keyword(s)`
    } else {
      merged.set(gf.filePath, {
        relevance: grepRelevance,
        reason: `Matched ${gf.matchCount} keyword(s) via text search`,
        symbols: [],
        sources: ['grep'],
        grepMatches: gf.matchCount,
      })
    }
  }

  // Sort by relevance descending, cap at 20 files
  const ranked = [...merged.entries()]
    .sort((a, b) => b[1].relevance - a[1].relevance)
    .slice(0, 20)

  // --- Assemble into PreparedFile[] within token budget ---
  const files: PreparedFile[] = []
  let usedChars = 0

  for (const [filePath, entry] of ranked) {
    const excerpt = includeContent ? entry.content?.slice(0, 500) : undefined
    const excerptChars = excerpt?.length || 0

    if (usedChars + excerptChars > charBudget) {
      // Over budget — add without content
      files.push({
        filePath,
        reason: entry.reason,
        relevance: entry.relevance,
        keySymbols: entry.symbols,
      })
      usedChars += filePath.length + 80
      continue
    }

    usedChars += excerptChars + filePath.length + 50
    files.push({
      filePath,
      reason: entry.reason,
      relevance: entry.relevance,
      keySymbols: entry.symbols,
      excerpt,
    })
  }

  // Determine source label
  const hasGraph = gnxResults.length > 0
  const hasGrep = grepResults.length > 0
  const source = hasGraph && hasGrep ? 'hybrid (graph + text)'
    : hasGraph ? 'graph'
    : hasGrep ? 'text search'
    : 'none'

  // Build summary
  let summary: string
  if (files.length > 0) {
    const topFiles = files.slice(0, 5).map(f => f.filePath.split('/').pop()).join(', ')
    const symbolList = files.flatMap(f => f.keySymbols).slice(0, 8).join(', ')
    const bothCount = ranked.filter(([, e]) => e.sources.length > 1).length
    const boostNote = bothCount > 0 ? ` (${bothCount} files boosted by both sources)` : ''
    summary = `Key code surface for "${task.slice(0, 80)}": ${files.length} relevant files found via ${source}${boostNote}. Top files: ${topFiles}. Primary symbols: ${symbolList || 'none'}.`
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

// WHY: safeParseJson is now shared from gitnexus-bridge.ts — see import above.

/**
 * Parse GitNexus query result into a uniform shape.
 *
 * WHY: GitNexus returns { processes, process_symbols, definitions }. Processes
 * contain execution flows with ranked relevance. Definitions contain standalone
 * types/interfaces. The result may arrive as:
 *  - Raw JSON object (direct call)
 *  - MCP envelope: { content: [{ type: 'text', text: '...' }] } (via router)
 *  - Markdown string (from some MCP layers)
 *
 * This parser normalizes all formats into a flat file list.
 *
 * Known quirks handled:
 *  - Processes are often empty for keyword-centric queries (no execution flows match)
 *  - File-type definitions (name matches filePath basename) are noise — skip them
 *  - process_symbols may be top-level (not nested inside each process)
 *  - Definitions lack a relevance score — we use 0.5 instead of the old 0.4
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

  // WHY: The router returns MCP-format { content: [{ type: 'text', text }] }.
  // The text inside may itself be a JSON envelope from the daemon's tool executor:
  //   { toolCallId, content: "<actual tool output JSON>", isError, durationMs }
  // We need to unwrap both layers to get the actual GitNexus response.
  let raw: any = result
  if (raw?.content && Array.isArray(raw.content)) {
    const textPart = raw.content.find((c: any) => c.type === 'text')
    if (textPart?.text) {
      try {
        raw = JSON.parse(textPart.text)
      } catch {
        raw = textPart.text
      }
    }
  }
  // HOW: Second unwrap — if raw is the daemon's tool executor envelope,
  // extract the actual content. The envelope has { toolCallId, content, isError }.
  if (raw?.toolCallId && typeof raw.content === 'string') {
    raw = safeParseJson(raw.content) ?? raw.content
  }
  // HOW: If raw.content is a string (direct daemon response without MCP wrapping)
  if (typeof raw === 'object' && raw !== null && !raw.processes && !raw.definitions && typeof raw.content === 'string') {
    raw = safeParseJson(raw.content) ?? raw.content
  }

  // Try structured JSON
  try {
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw

    // --- Process symbols (from execution flows) ---
    if (parsed.processes && Array.isArray(parsed.processes)) {
      const allSymbols = parsed.process_symbols || []
      for (const proc of parsed.processes) {
        const procSymbols = proc.symbols || allSymbols.filter(
          (s: any) => s.processName === (proc.name || proc.heuristicLabel)
        )

        for (const sym of procSymbols.slice(0, 6)) {
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

    // --- Definitions (standalone types/interfaces/classes) ---
    if (parsed.definitions && Array.isArray(parsed.definitions)) {
      for (const def of parsed.definitions) {
        if (!def.filePath) continue

        // WHY: Skip File-type entries — they're just container nodes, not meaningful
        // symbols. They appear as { id: "File:path/to/file.ts", name: "file.ts" }.
        const isFileEntry = def.id?.startsWith('File:') ||
          def.name === def.filePath.split('/').pop()
        if (isFileEntry) continue

        items.push({
          filePath: def.filePath,
          reason: `Definition: ${def.name}${def.module ? ` (${def.module})` : ''}`,
          relevance: 0.5,
          symbols: [def.name].filter(Boolean),
          content: def.content,
        })
      }
    }
  } catch {
    // Not JSON — parse as markdown/text output
    const output = typeof raw === 'string'
      ? raw
      : (raw?.output || raw?.markdown || JSON.stringify(raw))

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

  // Deduplicate by filePath, keeping highest relevance and merging symbols
  const byPath = new Map<string, typeof items[0]>()
  for (const item of items) {
    const existing = byPath.get(item.filePath)
    if (!existing || item.relevance > existing.relevance) {
      if (existing) {
        item.symbols = [...new Set([...existing.symbols, ...item.symbols])]
      }
      byPath.set(item.filePath, item)
    }
  }

  return [...byPath.values()].sort((a, b) => b.relevance - a.relevance)
}
