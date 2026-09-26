/**
 * Optimized write_file tool
 * 
 * Improvements over original:
 * - Async I/O (non-blocking)
 * - Batch write support for multiple files
 * - Atomic writes (write to temp, then rename)
 * - Directory caching to avoid redundant mkdir calls
 * - Stream-based writes for large files
 */

import { createWriteStream } from 'node:fs'
import { readFile as fsReadFile, writeFile, mkdir, rename, unlink, stat } from 'node:fs/promises'
import { resolve, dirname, basename, join, relative } from 'node:path'
import { execFile } from 'node:child_process'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import { getRepoRoot } from '@cassicore/foundation'


/**
 * Stage a file with `git add`. Fire-and-forget — failures are logged but
 * never propagate to the caller.  This makes every agent file-write
 * recoverable via `git checkout -- <file>`.
 * @dep callers: writeFileHandler (core/tools/implementations/write-file.ts), writeFilesBatch (core/tools/implementations/write-file.ts)
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function gitStage(absPath: string, workingDir: string, logger: ToolExecutionContext['logger']): void {
  try {
    execFile('git', ['add', '--', absPath], { cwd: workingDir, timeout: 5_000 }, (err) => {
      if (err) {
        logger.debug?.('[write_file] git-add failed (non-fatal)', { path: absPath, error: String(err) })
      }
    })
  } catch {
    // execFile itself threw — git not available, etc.  Silently ignore.
  }
}

// ── CassiCore Code Store Integration ───────────────────────────────

const CODE_STORE_SOURCE_EXTS = new Set(['ts', 'tsx', 'js', 'jsx', 'json', 'yaml', 'yml', 'md', 'sh'])

/**
 * Check if a file path is a CassiCore source file that should be managed
 * by the code store (mnemic field database).
 */
function isCassiCoreSourceFile(absPath: string): { is: boolean; relPath: string } {
  const repoRoot = getRepoRoot()
  if (!absPath.startsWith(repoRoot)) return { is: false, relPath: '' }

  const relPath = relative(repoRoot, absPath)

  // Skip generated/vendored directories
  if (relPath.startsWith('dist/') || relPath.startsWith('node_modules/')) {
    return { is: false, relPath }
  }

  const ext = absPath.split('.').pop() ?? ''
  if (!CODE_STORE_SOURCE_EXTS.has(ext)) return { is: false, relPath }

  return { is: true, relPath }
}

// Session-scoped changeset tracking: one active changeset per session
const activeChangesets = new Map<string, string>()

/**
 * Get or create an active changeset for this session.
 */
function getOrCreateChangeset(ctx: ToolExecutionContext): string | null {
  const codeStore = ctx._codeStore
  if (!codeStore) return null

  const existing = activeChangesets.get(ctx.sessionId)
  if (existing) {
    const cs = codeStore.getChangeset(existing)
    if (cs && cs.status === 'pending') return existing
    activeChangesets.delete(ctx.sessionId)
  }

  try {
    const cs = codeStore.createChangeset({
      description: `Session ${ctx.sessionId} code changes`,
      authorSessionId: ctx.sessionId,
      authorAgentId: ctx.sessionType ? `${ctx.sessionType}/${ctx.sessionId}` : ctx.sessionId,
    })
    activeChangesets.set(ctx.sessionId, cs.id)
    return cs.id
  } catch (err) {
    ctx.logger.warn?.('[write_file] failed to create changeset', { error: String(err) })
    return null
  }
}

/**
 * Write a CassiCore source file directly to the code store (DB-authoritative).
 * The file is stored as an engram in the mnemic field within a changeset.
 * Returns a result string, or null if code store is unavailable (fall back to filesystem).
 */
function writeToCodeStore(
  absPath: string,
  relPath: string,
  content: string,
  ctx: ToolExecutionContext,
): string | null {
  const codeStore = ctx._codeStore
  if (!codeStore) return null

  const changesetId = getOrCreateChangeset(ctx)
  if (!changesetId) return null

  try {
    const { engram, operation } = codeStore.writeFileInChangeset(changesetId, relPath, content)
    const meta = engram.metadata as Record<string, unknown>

    ctx.logger.debug?.('[write_file] wrote to code store (DB-authoritative)', {
      path: relPath,
      operation,
      changesetId,
      engramId: engram.id,
    })

    const sizeBytes = meta.sizeBytes ?? Buffer.byteLength(content, 'utf8')
    return `Wrote ${sizeBytes} bytes to code store: ${relPath} (${operation}, changeset: ${changesetId.slice(0, 8)})`
  } catch (err) {
    ctx.logger.warn?.('[write_file] code store write failed, falling back to filesystem', {
      path: relPath,
      error: String(err),
    })
    return null
  }
}

/**
 * Commit the active changeset for a session. Called when a batch of changes
 * is complete (e.g., end of turn or explicit commit).
 */
export function commitSessionChangeset(sessionId: string, codeStore: import('@cassicore/mnemic-field').CodeStore): string | null {
  const changesetId = activeChangesets.get(sessionId)
  if (!changesetId) return null

  const cs = codeStore.commitChangeset(changesetId)
  activeChangesets.delete(sessionId)
  return cs?.id ?? null
}

/**
 * Clean up the active changeset for a session without committing.
 * Call on session end to prevent memory leaks in the activeChangesets map.
 */
export function discardSessionChangeset(sessionId: string): void {
  activeChangesets.delete(sessionId)
}

// ── EditMagnitudeGuard ──────────────────────────────────────────────

interface MagnitudeThresholds {
  // WHY: Helix agents run autonomously and have historically truncated files.
  // Stricter thresholds for autonomous sessions prevent catastrophic data loss.
  maxDeletionRatio: number   // 0–1, fraction of lines deleted
  maxNetDeletion: number     // absolute count of net lines removed
}

const HELIX_THRESHOLDS: MagnitudeThresholds = {
  maxDeletionRatio: 0.50,    // block if >50% of lines would be deleted
  maxNetDeletion: 100,       // block if >100 net lines removed
}

const DEFAULT_THRESHOLDS: MagnitudeThresholds = {
  maxDeletionRatio: 0.70,    // block if >70% of lines would be deleted
  maxNetDeletion: 200,       // block if >200 net lines removed
}

// WHY: Files below this line count are too small for ratio-based detection
// to be meaningful (e.g., a 10-line file losing 6 lines is normal editing).
const MIN_LINES_FOR_GUARD = 30

interface MagnitudeCheckResult {
  allowed: boolean
  reason?: string
  oldLines: number
  newLines: number
  deletionRatio: number
  netDeletion: number
  existingContent?: string  // returned for downstream use (backup) when file exists
}

/**
 * Check whether a write_file call would destructively reduce an existing file.
 * Returns { allowed: true } for new files, small files, or writes within thresholds.
 * Returns { allowed: false, reason } when the write looks destructive.
 */
export async function checkEditMagnitude(
  absPath: string,
  newContent: string,
  ctx: ToolExecutionContext,
): Promise<MagnitudeCheckResult> {
  // HOW: Read the existing file; if it doesn't exist this is a create — always allowed.
  let existingContent: string
  try {
    existingContent = await fsReadFile(absPath, 'utf8')
  } catch {
    return { allowed: true, oldLines: 0, newLines: newContent.split('\n').length, deletionRatio: 0, netDeletion: 0 }
  }

  const oldLines = existingContent.split('\n').length
  const newLines = newContent.split('\n').length

  // Small files: skip guard (ratio is unreliable for tiny files)
  if (oldLines < MIN_LINES_FOR_GUARD) {
    return { allowed: true, oldLines, newLines, deletionRatio: 0, netDeletion: 0, existingContent }
  }

  const netDeletion = oldLines - newLines
  const deletionRatio = netDeletion > 0 ? netDeletion / oldLines : 0

  // Pick thresholds based on session type
  const thresholds = ctx.sessionType === 'helix'
    ? HELIX_THRESHOLDS
    : DEFAULT_THRESHOLDS

  // Check thresholds — both must be exceeded to block
  // WHY: A single threshold isn't enough. A 200-line file losing 60% is different
  // from a 2000-line file losing 60%. We require BOTH ratio AND absolute count
  // to exceed thresholds, reducing false positives for legitimate refactors.
  if (deletionRatio > thresholds.maxDeletionRatio && netDeletion > thresholds.maxNetDeletion) {
    const sessionLabel = ctx.sessionType === 'helix' ? 'Helix session' : 'Session'
    return {
      allowed: false,
      reason: `EditMagnitudeGuard: ${sessionLabel} blocked from overwriting ${absPath} — `
        + `would delete ${netDeletion} of ${oldLines} lines (${(deletionRatio * 100).toFixed(1)}% reduction). `
        + `Thresholds: >${(thresholds.maxDeletionRatio * 100).toFixed(0)}% ratio AND >${thresholds.maxNetDeletion} net lines. `
        + `Use incremental edits (edit_file / replace_content) instead of full-file rewrites.`,
      oldLines,
      newLines,
      deletionRatio,
      netDeletion,
    }
  }

  return { allowed: true, oldLines, newLines, deletionRatio, netDeletion, existingContent }
}

// ── Pre-Write Backup ────────────────────────────────────────────────

// WHY: Files above this line count are worth snapshotting before overwrite.
// Below this threshold, git recovery is sufficient.
// Constants

const MAX_SYNC_SIZE = 1024 * 1024  // 1MB - sync writes below this
const STREAM_THRESHOLD = 10 * 1024 * 1024  // 10MB - stream writes above this
const ATOMIC_WRITE = true  // Use atomic writes (temp file + rename)

// Directory Cache

class DirectoryCache {
  private cache = new Set<string>()

  async ensure(dirPath: string): Promise<void> {
    if (this.cache.has(dirPath)) return
    
    await mkdir(dirPath, { recursive: true })
    this.cache.add(dirPath)
    
    // Also cache parent directories
    let parent = dirPath
    while (parent !== dirname(parent)) {
      parent = dirname(parent)
      if (this.cache.has(parent)) break
      this.cache.add(parent)
    }
  }

  invalidate(path: string): void {
    // Remove this path and all children from cache
    for (const cached of this.cache) {
      if (cached.startsWith(path)) {
        this.cache.delete(cached)
      }
    }
  }

  clear(): void {
    this.cache.clear()
  }
}

const globalDirCache = new DirectoryCache()

// Optimized Write Operations

interface WriteOptions {
  path: string
  content: string
  atomic?: boolean
}

/**
 * Write file with optimizations
 * - Small files: direct async write
 * - Large files: streaming write
 * - Atomic option: temp file + rename
 * @dep callers: writeFileHandler (core/tools/implementations/write-file.ts), writeFilesBatch (core/tools/implementations/write-file.ts)
 * @dep calls: ensure, writeStreaming, now
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function writeFileOptimized(
  options: WriteOptions,
  ctx: ToolExecutionContext
): Promise<{ bytesWritten: number; durationMs: number; method: string }> {
  const startTime = Date.now()
  const { path: filePath, content, atomic = ATOMIC_WRITE } = options
  
  const contentBytes = Buffer.byteLength(content, 'utf8')
  const dirPath = dirname(filePath)
  
  // Ensure directory exists (cached)
  await globalDirCache.ensure(dirPath)
  
  // Choose write strategy based on size
  if (contentBytes > STREAM_THRESHOLD) {
    // Streaming write for very large files
    await writeStreaming(filePath, content, atomic)
    return {
      bytesWritten: contentBytes,
      durationMs: Date.now() - startTime,
      method: atomic ? 'stream-atomic' : 'stream'
    }
  }
  
  // Standard async write
  if (atomic) {
    // Atomic write: write to temp, then rename
    const tempPath = join(dirPath, `.tmp-${basename(filePath)}-${Date.now()}`)
    try {
      await writeFile(tempPath, content, 'utf8')
      await rename(tempPath, filePath)
    } catch (err) {
      // Cleanup temp file on error
      try { await unlink(tempPath) } catch {}
      throw err
    }
  } else {
    await writeFile(filePath, content, 'utf8')
  }
  
  return {
    bytesWritten: contentBytes,
    durationMs: Date.now() - startTime,
    method: atomic ? 'atomic' : 'direct'
  }
}

/**
 * Stream write for large files
 */
async function writeStreaming(
  filePath: string,
  content: string,
  atomic: boolean
): Promise<void> {
  const targetPath = atomic ? `${filePath}.tmp` : filePath
  const stream = createWriteStream(targetPath)
  const readable = Readable.from([content])
  
  await pipeline(readable, stream)
  
  if (atomic) {
    await rename(targetPath, filePath)
  }
}

// Tool Definition

export const writeFileDefinition: ToolDefinition = {
  name: 'write_file',
  description: 'Write content to a file. Creates parent directories automatically. Uses atomic writes for data safety.',
  parameters: {
    type: 'object',
    properties: {
      path:    { type: 'string', description: 'Destination path (absolute or relative to workspace)' },
      content: { type: 'string', description: 'Content to write' },
      atomic:  { type: 'boolean', description: 'Use atomic write (default: true)' },
    },
    required: ['path', 'content'],
  },
  timeoutMs: 15_000,
  category: 'core',
  requiredPermission: 'workspace-write',
}

// Tool Handler

export const writeFileHandler: ToolHandler = async (
  input: Record<string, unknown>,
  ctx: ToolExecutionContext
): Promise<string> => {
  
  const rawPath = input['path'] as string
  const content = input['content'] as string
  const atomic = (input['atomic'] as boolean | undefined) ?? ATOMIC_WRITE

  // Path resolution
  const absPath = rawPath.startsWith('/') ? rawPath : resolve(ctx.workingDir, rawPath)

  // Security check
  const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
  if (!allowed) {
    return `Error: access denied — ${absPath} is outside allowed paths`
  }

  // DB-authoritative path: CassiCore source files write to code store
  // WHY: When running in a worktree (e.g. constellation branch isolation),
  // skip the code store and write directly to the filesystem. The code store
  // is DB-authoritative for the main repo only; worktrees need real files.
  const codeCheck = isCassiCoreSourceFile(absPath)
  const isWorktree = ctx.workingDir !== getRepoRoot()
  if (codeCheck.is && ctx._codeStore && !isWorktree) {
    // EditMagnitudeGuard still runs — compare against code store content
    const existingEngram = ctx._codeStore.getFileByPath(codeCheck.relPath)
    if (existingEngram) {
      const oldLines = existingEngram.content.split('\n').length
      const newLines = content.split('\n').length
      const netDeletion = oldLines - newLines
      const deletionRatio = netDeletion > 0 ? netDeletion / oldLines : 0
      const thresholds = ctx.sessionType === 'helix' ? HELIX_THRESHOLDS : DEFAULT_THRESHOLDS

      if (oldLines >= MIN_LINES_FOR_GUARD
        && deletionRatio > thresholds.maxDeletionRatio
        && netDeletion > thresholds.maxNetDeletion) {
        return `Error: EditMagnitudeGuard blocked — would delete ${netDeletion} of ${oldLines} lines (${(deletionRatio * 100).toFixed(1)}%). Use incremental edits instead.`
      }
    }

    const result = writeToCodeStore(absPath, codeCheck.relPath, content, ctx)
    if (result) return result
    // If code store write failed, fall through to filesystem
  }

  // EditMagnitudeGuard — block destructive overwrites
  const magnitudeCheck = await checkEditMagnitude(absPath, content, ctx)
  if (!magnitudeCheck.allowed) {
    ctx.logger.warn?.('[write_file] EditMagnitudeGuard BLOCKED write', {
      path: absPath,
      oldLines: magnitudeCheck.oldLines,
      newLines: magnitudeCheck.newLines,
      deletionRatio: magnitudeCheck.deletionRatio.toFixed(3),
      netDeletion: magnitudeCheck.netDeletion,
      sessionType: ctx.sessionType ?? 'unknown',
      sessionId: ctx.sessionId,
    })
    return `Error: ${magnitudeCheck.reason}`
  }

  try {
    const result = await writeFileOptimized(
      { path: absPath, content, atomic },
      ctx
    )

    ctx.logger.debug?.('[write_file] completed', {
      path: absPath,
      bytes: result.bytesWritten,
      method: result.method,
      duration: `${result.durationMs}ms`
    })

    // Stage in git (protection against accidental deletion)
    gitStage(absPath, ctx.workingDir, ctx.logger)

    return `Wrote ${result.bytesWritten} bytes to ${absPath} (${result.method}, ${result.durationMs}ms)`
  } catch (err) {
    return `Error writing file: ${String(err)}`
  }
}

// Batch Write Support

export interface WriteFileOptions {
  path: string
  content: string
  atomic?: boolean
}

/**
 * Write multiple files efficiently
 * - Parallel directory creation
 * - Parallel writes
 * - Shared directory cache
 */
export async function writeFilesBatch(
  files: WriteFileOptions[],
  ctx: ToolExecutionContext
): Promise<Map<string, { success: boolean; bytesWritten: number; error?: string }>> {
  
  const results = new Map<string, { success: boolean; bytesWritten: number; error?: string }>()
  
  // Pre-validate all paths
  const validFiles: Array<{ key: string; absPath: string; options: WriteOptions }> = []
  
  for (const file of files) {
    const absPath = file.path.startsWith('/') 
      ? file.path 
      : resolve(ctx.workingDir, file.path)
    
    const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
    if (!allowed) {
      results.set(file.path, { success: false, bytesWritten: 0, error: 'access denied' })
      continue
    }
    
    validFiles.push({
      key: file.path,
      absPath,
      options: { path: absPath, content: file.content, atomic: file.atomic }
    })
  }
  
  // Ensure all directories first (sequential for cache efficiency)
  const uniqueDirs = new Set(validFiles.map(f => dirname(f.absPath)))
  for (const dir of uniqueDirs) {
    await globalDirCache.ensure(dir)
  }
  
  // Parallel writes with concurrency limit
  const CONCURRENCY = 5
  for (let i = 0; i < validFiles.length; i += CONCURRENCY) {
    const batch = validFiles.slice(i, i + CONCURRENCY)
    
    await Promise.all(batch.map(async ({ key, absPath, options }) => {
      try {
        // DB-authoritative path for CassiCore source files (skip in worktrees)
        const codeCheck = isCassiCoreSourceFile(absPath)
        const isWorktreeBatch = ctx.workingDir !== getRepoRoot()
        if (codeCheck.is && ctx._codeStore && !isWorktreeBatch) {
          const csResult = writeToCodeStore(absPath, codeCheck.relPath, options.content, ctx)
          if (csResult) {
            results.set(key, { success: true, bytesWritten: Buffer.byteLength(options.content, 'utf8') })
            return
          }
        }

        const result = await writeFileOptimized(options, ctx)
        results.set(key, { success: true, bytesWritten: result.bytesWritten })
        gitStage(absPath, ctx.workingDir, ctx.logger)
      } catch (err) {
        results.set(key, { success: false, bytesWritten: 0, error: String(err) })
      }
    }))
  }
  
  return results
}

// Export cache for management
export { globalDirCache as dirCache }
