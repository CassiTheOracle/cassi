/**
 * GitNexus Bridge — Shared wrapper for all GitNexus tool calls.
 *
 * Features:
 *  - Automatic stale-index detection via meta.json vs `git rev-parse HEAD`
 *  - Auto-reindex when stale (runs `npx gitnexus analyze` transparently)
 *  - Reindex lock to prevent concurrent rebuilds
 *  - Graceful fallback messaging when GitNexus is unavailable
 */

import { execSync, exec } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { promisify } from 'node:util'
import type { ILogger } from '../../../types/interfaces.js'

const execAsync = promisify(exec)

/** How many seconds between staleness checks (avoid hammering git on every call). */
const STALENESS_CHECK_INTERVAL_MS = 60_000

/** How many commits behind HEAD the index can be before we consider it stale. */
const MAX_STALE_COMMITS = 30

/** Maximum time to wait for a reindex (5 minutes). */
const REINDEX_TIMEOUT_MS = 300_000

/** GitNexus index metadata shape. */
interface GitNexusMeta {
  repoPath: string
  lastCommit: string
  indexedAt: string
  stats: {
    files: number
    nodes: number
    edges: number
    communities: number
    processes: number
  }
}

/** Cached state to avoid repeated fs/git checks. */
let lastCheckTs = 0
let cachedFresh = false
let reindexInProgress: Promise<boolean> | null = null

/**
 * Resolve the repo root (where .gitnexus/ lives).
 * @dep callers: isIndexFresh (core/intelligence/code-analysis/gitnexus-bridge.ts), reindex (core/intelligence/code-analysis/gitnexus-bridge.ts)
 * @dep module: Code-analysis
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function repoRoot(): string {
  try {
    return execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim()
  } catch {
    return process.cwd()
  }
}

/**
 * Read the GitNexus meta.json if it exists.
 */
function readMeta(root: string): GitNexusMeta | null {
  const metaPath = join(root, '.gitnexus', 'meta.json')
  if (!existsSync(metaPath)) return null
  try {
    return JSON.parse(readFileSync(metaPath, 'utf-8'))
  } catch {
    return null
  }
}

/**
 * Get current HEAD commit.
 */
function currentHead(root: string): string | null {
  try {
    return execSync('git rev-parse HEAD', { encoding: 'utf-8', cwd: root }).trim()
  } catch {
    return null
  }
}

/**
 * Check whether the graph database exists.
 * WHY: GitNexus v1.3.x used KuzuDB (.gitnexus/kuzu as file or directory),
 * while v1.5.x uses LadybugDB (.gitnexus/lbug). We check for either to
 * support both versions transparently.
 */
function graphDbExists(root: string): boolean {
  const gnDir = join(root, '.gitnexus')
  return existsSync(join(gnDir, 'kuzu')) || existsSync(join(gnDir, 'lbug'))
}

/**
 * Count commits between the indexed commit and HEAD.
 * Returns -1 if the count cannot be determined.
 */
function commitsBehind(root: string, indexedCommit: string, head: string): number {
  if (indexedCommit === head) return 0
  try {
    const count = execSync(`git rev-list --count ${indexedCommit}..${head}`, {
      encoding: 'utf-8',
      cwd: root,
    }).trim()
    return parseInt(count, 10) || -1
  } catch {
    return -1
  }
}

/**
 * Determine whether the GitNexus index is fresh enough for use.
 *
 * Fresh means:
 *  1. `.gitnexus/kuzu` (KuzuDB) or `.gitnexus/lbug` (LadybugDB) exists
 *  2. `meta.json` exists
 *  3. The indexed commit is within MAX_STALE_COMMITS of HEAD
 *
 * WHY: Using a commit threshold instead of exact HEAD match avoids
 * triggering expensive reindexes after every commit during active sessions.
 * The withAutoReindex wrapper handles the case where a query fails because
 * the index is too far behind.
 * @dep callers: reindex (core/intelligence/code-analysis/gitnexus-bridge.ts), ensureFreshIndex (core/intelligence/code-analysis/gitnexus-bridge.ts)
 * @dep calls: commitsBehind, graphDbExists, currentHead, readMeta, repoRoot [+1]
 * @dep module: Code-analysis
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function isIndexFresh(logger?: ILogger): boolean {
  const now = Date.now()
  if (now - lastCheckTs < STALENESS_CHECK_INTERVAL_MS) return cachedFresh

  const root = repoRoot()
  const meta = readMeta(root)
  const head = currentHead(root)

  if (!meta || !head || !graphDbExists(root)) {
    cachedFresh = false
    lastCheckTs = now
    logger?.debug('GitNexus index missing or incomplete', { hasMeta: !!meta, hasGraphDb: graphDbExists(root) })
    return false
  }

  if (meta.lastCommit === head) {
    cachedFresh = true
    lastCheckTs = now
    return true
  }

  const behind = commitsBehind(root, meta.lastCommit, head)
  cachedFresh = behind >= 0 && behind <= MAX_STALE_COMMITS
  lastCheckTs = now
  if (!cachedFresh) {
    logger?.debug('GitNexus index too stale, reindex needed', {
      indexedCommit: meta.lastCommit.slice(0, 7),
      currentHead: head.slice(0, 7),
      commitsBehind: behind,
    })
  } else if (behind > 0) {
    logger?.debug('GitNexus index slightly stale but usable', {
      indexedCommit: meta.lastCommit.slice(0, 7),
      currentHead: head.slice(0, 7),
      commitsBehind: behind,
    })
  }
  return cachedFresh
}

/**
 * Force-clear the staleness cache so the next call re-checks.
 */
export function invalidateStalenessCache(): void {
  lastCheckTs = 0
  cachedFresh = false
}

/**
 * Run `npx gitnexus analyze` to rebuild the index.
 * Returns true on success, false on failure.
 * Serialised: concurrent callers share the same promise.
 * @dep callers: ensureFreshIndex (core/intelligence/code-analysis/gitnexus-bridge.ts), withAutoReindex (core/intelligence/code-analysis/gitnexus-bridge.ts)
 * @dep calls: invalidateStalenessCache, isIndexFresh, repoRoot
 * @dep module: Code-analysis
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function reindex(logger?: ILogger): Promise<boolean> {
  if (reindexInProgress) {
    logger?.debug('GitNexus reindex already in progress, waiting…')
    return reindexInProgress
  }

  reindexInProgress = (async () => {
    const root = repoRoot()
    logger?.info('GitNexus auto-reindex starting…', { cwd: root })

    try {
      // WHY: Using async exec instead of execSync to avoid blocking the Node.js
      // event loop for minutes. execSync freezes the entire MCP server, making
      // all other tool calls time out during the reindex.
      const { stdout } = await execAsync('npx gitnexus analyze', {
        cwd: root,
        timeout: REINDEX_TIMEOUT_MS,
        encoding: 'utf-8',
      })
      invalidateStalenessCache()

      if (isIndexFresh(logger)) {
        logger?.info('GitNexus auto-reindex complete', { output: (stdout ?? '').slice(0, 200) })
        return true
      }
      logger?.warn('GitNexus reindex ran but index still appears stale')
      return false
    } catch (err) {
      logger?.error('GitNexus auto-reindex failed', { error: String(err) })
      return false
    } finally {
      reindexInProgress = null
    }
  })()

  return reindexInProgress
}

/**
 * Ensure the GitNexus index is fresh, reindexing automatically if stale.
 *
 * Usage — call before any GitNexus operation:
 *
 * ```ts
 * await ensureFreshIndex(logger)
 * const result = await router('gitnexus_query', args)
 * ```
 * @dep callers: executeCodeConsolidatedTool (mcp/gateway/consolidated-code-tools.ts), withAutoReindex (core/intelligence/code-analysis/gitnexus-bridge.ts)
 * @dep calls: reindex, isIndexFresh
 * @dep module: Code-analysis
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function ensureFreshIndex(logger?: ILogger): Promise<boolean> {
  if (isIndexFresh(logger)) return true
  return reindex(logger)
}

/**
 * Check whether the GitNexus index exists (kuzu DB present), regardless of freshness.
 *
 * WHY: For latency-sensitive callers like prepare_context, a stale index is
 * better than no index. This check is fast (stat() only, no git ops) and
 * lets callers decide whether to query directly vs fall back to grep.
 */
export function isIndexAvailable(): boolean {
  const root = repoRoot()
  return graphDbExists(root)
}

/**
 * Trigger a background reindex if the index is stale. Returns immediately.
 *
 * WHY: Callers that can't afford to block (prepare_context) use this to
 * improve the index for next time without paying the cost now.
 *
 * Returns true if a reindex was triggered, false if already fresh or in progress.
 */
export function ensureFreshIndexBackground(logger?: ILogger): boolean {
  if (isIndexFresh(logger)) return false
  if (reindexInProgress) {
    logger?.debug('Background reindex already in progress, skipping trigger')
    return false
  }
  reindex(logger).catch(err => {
    logger?.warn('Background reindex failed', { error: String(err) })
  })
  return true
}

/**
 * Wrap a GitNexus tool call with auto-reindex.
 *
 * If the call fails with a KuzuDB-related error, attempts one reindex + retry.
 */
export async function withAutoReindex<T>(
  fn: () => Promise<T>,
  logger?: ILogger,
): Promise<T> {
  // Pre-flight: ensure index is fresh
  await ensureFreshIndex(logger)

  try {
    return await fn()
  } catch (err: any) {
    const msg = String(err)
    const isKuzuError = msg.includes('KuzuDB not found')
      || msg.includes('kuzu')
      || msg.includes('No index found')
      || msg.includes('not indexed')

    if (!isKuzuError) throw err

    logger?.warn('GitNexus call failed with index error, attempting reindex…', { error: msg })
    const ok = await reindex(logger)
    if (!ok) throw new Error(`GitNexus index unavailable: ${msg}`)

    // Retry once
    return await fn()
  }
}

/**
 * Safely parse JSON from a string that may have trailing non-JSON content.
 *
 * WHY: Older tool results (e.g., cached responses, replayed prompt logs) may
 * have a trust banner like "━━ CassiCore ━ trust ████ 0.92 ━━" appended. The
 * banner is no longer emitted by the tool executor (trust state is delivered
 * via the tool:enriched event sidecar instead), but defensive parsing remains
 * to handle legacy artifacts and other trailing-noise sources. Strategies:
 *  1. Direct JSON.parse (fastest, works for clean JSON)
 *  2. Strip after common separators (--- or ━━)
 *  3. Find the last balanced brace/bracket
 */
export function safeParseJson(text: string): any | null {
  try {
    return JSON.parse(text)
  } catch { /* continue */ }

  const trimmed = text.trim()
  for (const sep of ['\n---\n', '\n━━', '\n\n---']) {
    const idx = trimmed.indexOf(sep)
    if (idx > 0) {
      try {
        return JSON.parse(trimmed.slice(0, idx).trim())
      } catch { /* continue */ }
    }
  }

  const firstChar = trimmed[0]
  if (firstChar === '{' || firstChar === '[') {
    const closer = firstChar === '{' ? '}' : ']'
    let depth = 0
    let inString = false
    let escape = false
    for (let i = 0; i < trimmed.length; i++) {
      const ch = trimmed[i]
      if (escape) { escape = false; continue }
      if (ch === '\\') { escape = true; continue }
      if (ch === '"') { inString = !inString; continue }
      if (inString) continue
      if (ch === firstChar) depth++
      if (ch === closer) {
        depth--
        if (depth === 0) {
          try {
            return JSON.parse(trimmed.slice(0, i + 1))
          } catch { /* continue */ }
        }
      }
    }
  }

  return null
}

/**
 * Unwrap a router response that may be in MCP envelope format.
 *
 * WHY: When calling GitNexus tools through the daemon's router, responses arrive
 * in a multi-layered envelope:
 *   { content: [{ type: 'text', text: '{ "toolCallId": "...", "content": "{actual JSON}\\n...trust bar" }' }] }
 *
 * This function peels all layers and returns the inner payload object.
 * Falls back to the raw input if unwrapping fails.
 */
export function unwrapRouterResponse(raw: any): any {
  if (!raw) return raw

  // Layer 1: MCP envelope { content: [{ type: 'text', text: '...' }] }
  if (raw.content && Array.isArray(raw.content) && raw.content[0]?.text) {
    const parsed = safeParseJson(raw.content[0].text)
    if (parsed) raw = parsed
  }

  // Layer 2: Daemon envelope { content: "{ ... }" | "{ ... }\n...trust bar" }
  if (typeof raw.content === 'string') {
    const parsed = safeParseJson(raw.content)
    if (parsed) raw = parsed
  }

  // Layer 3: rawContent field (some daemon responses include this pre-stripped)
  if (typeof raw.rawContent === 'string') {
    const parsed = safeParseJson(raw.rawContent)
    if (parsed) return parsed
  }

  return raw
}
