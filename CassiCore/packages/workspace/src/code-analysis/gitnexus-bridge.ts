/**
 * GitNexus Bridge — Shared wrapper for all GitNexus tool calls.
 *
 * Features:
 *  - Automatic stale-index detection via meta.json vs `git rev-parse HEAD`
 *  - Auto-reindex when stale (runs `npx gitnexus analyze` transparently)
 *  - Reindex lock to prevent concurrent rebuilds
 *  - Graceful fallback messaging when GitNexus is unavailable
 */

import { execSync, exec, type ExecSyncOptions } from 'node:child_process'
import { readFileSync, existsSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { promisify } from 'node:util'
import type { ILogger } from '../../../types/interfaces.js'

const execAsync = promisify(exec)

/** How many seconds between staleness checks (avoid hammering git on every call). */
const STALENESS_CHECK_INTERVAL_MS = 60_000

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
 * Check whether the KuzuDB directory exists (the actual graph database).
 */
function kuzuExists(root: string): boolean {
  const kuzuDir = join(root, '.gitnexus', 'kuzu')
  return existsSync(kuzuDir) && statSync(kuzuDir).isDirectory()
}

/**
 * Determine whether the GitNexus index is fresh.
 *
 * Fresh means:
 *  1. `.gitnexus/kuzu` directory exists
 *  2. `meta.json` exists and its `lastCommit` matches `git rev-parse HEAD`
 */
export function isIndexFresh(logger?: ILogger): boolean {
  const now = Date.now()
  if (now - lastCheckTs < STALENESS_CHECK_INTERVAL_MS) return cachedFresh

  const root = repoRoot()
  const meta = readMeta(root)
  const head = currentHead(root)

  if (!meta || !head || !kuzuExists(root)) {
    cachedFresh = false
    lastCheckTs = now
    logger?.debug('GitNexus index missing or incomplete', { hasMeta: !!meta, hasKuzu: kuzuExists(root) })
    return false
  }

  cachedFresh = meta.lastCommit === head
  lastCheckTs = now
  if (!cachedFresh) {
    logger?.debug('GitNexus index stale', {
      indexedCommit: meta.lastCommit.slice(0, 7),
      currentHead: head.slice(0, 7),
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
 */
export async function ensureFreshIndex(logger?: ILogger): Promise<boolean> {
  if (isIndexFresh(logger)) return true
  return reindex(logger)
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
