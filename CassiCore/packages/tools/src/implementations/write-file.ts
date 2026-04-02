/**
 * Optimized write_file tool
 * 
 * Improvements over original:
 * - Async I/O (non-blocking)
 * - Batch write support for multiple files
 * - Atomic writes (write to temp, then rename)
 * - Directory caching to avoid redundant mkdir calls
 * - Stream-based writes for large files
 * - cassi://files/ URI support for FileArtifactStore integration
 */

import { createWriteStream } from 'node:fs'
import { writeFile, mkdir, rename, unlink } from 'node:fs/promises'
import { resolve, dirname, basename, join, relative } from 'node:path'
import { execFile } from 'node:child_process'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import { parseFileArtifactUri, FileArtifactStore } from '../../file-artifact-store.js'

// ── Git staging helper ──────────────────────────────────────────────────────

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

/**
 * Mirror a filesystem write into the FileArtifactStore under the `workspace:`
 * namespace.  This provides attribution (who wrote what, when) and version
 * history for every agent file-write.  Fire-and-forget — failures are logged
 * but never block the write.
 * @dep callers: writeFileHandler (core/tools/implementations/write-file.ts), writeFilesBatch (core/tools/implementations/write-file.ts)
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function mirrorToArtifactStore(
  absPath: string,
  content: string,
  ctx: ToolExecutionContext,
): void {
  const store = ctx._fileArtifactStore
  if (!store) return

  const relPath = relative(ctx.workingDir, absPath)
  // Skip files outside the workspace (shouldn't happen but be safe)
  if (relPath.startsWith('..')) return

  try {
    store.write({
      namespace: 'workspace',
      path: relPath,
      content,
      sessionId: ctx.sessionId,
      agentId: ctx.sessionType ? `${ctx.sessionType}/${ctx.sessionId}` : ctx.sessionId,
      message: `write_file: ${relPath}`,
      visibility: 'public',  // workspace mirrors are always accessible
      tags: ['workspace-mirror', ctx.sessionType ?? 'unknown'].filter(Boolean),
    })
  } catch (err) {
    ctx.logger.debug?.('[write_file] artifact-store mirror failed (non-fatal)', {
      path: relPath,
      error: String(err),
    })
  }
}

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
  description: 'Write content to a file. Creates parent directories automatically. Uses atomic writes for data safety. Also writes to cassi://files/ URIs in the shared FileArtifactStore.',
  parameters: {
    type: 'object',
    properties: {
      path:    { type: 'string', description: 'Destination path (absolute, relative to workspace, or cassi://files/{namespace}/{path})' },
      content: { type: 'string', description: 'Content to write' },
      atomic:  { type: 'boolean', description: 'Use atomic write (default: true)' },
      message: { type: 'string', description: 'Commit message (for cassi://files/ writes only)' },
      visibility: { type: 'string', enum: ['private', 'shared', 'public'], description: 'Access visibility (for cassi://files/ writes only, default: private)' },
      tags:    { type: 'array', items: { type: 'string' }, description: 'Tags (for cassi://files/ writes only)' },
    },
    required: ['path', 'content'],
  },
  timeoutMs: 10_000,
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

  // ── cassi://files/ URI interception ──
  // Routes to FileArtifactStore instead of filesystem
  const artifactUri = parseFileArtifactUri(rawPath)
  if (artifactUri) {
    try {
      const store = ctx._fileArtifactStore
      if (!store) {
        return `Error: FileArtifactStore not available. Cannot write cassi:// URIs.`
      }
      const result = store.write({
        namespace: artifactUri.namespace,
        path: artifactUri.path,
        content,
        sessionId: ctx.sessionId,
        message: input['message'] as string | undefined,
        visibility: input['visibility'] as 'private' | 'shared' | 'public' | undefined,
        tags: input['tags'] as string[] | undefined,
      })
      const uri = `cassi://files/${result.file.namespace}/${result.file.path}@v${result.version.versionNumber}`
      return `${result.created ? 'Created' : 'Updated'} artifact: ${uri} (${result.version.size} bytes, v${result.version.versionNumber})`
    } catch (err) {
      return `Error writing artifact: ${String(err)}`
    }
  }
  
  // Path resolution
  const absPath = rawPath.startsWith('/') ? rawPath : resolve(ctx.workingDir, rawPath)
  
  // Security check
  const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
  if (!allowed) {
    return `Error: access denied — ${absPath} is outside allowed paths`
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

    // ── Post-write: attribution + recovery ──
    // Mirror into FileArtifactStore (attribution, version history, recovery)
    mirrorToArtifactStore(absPath, content, ctx)
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
        const result = await writeFileOptimized(options, ctx)
        results.set(key, { success: true, bytesWritten: result.bytesWritten })
        // Post-write: attribution + recovery (same as single-file path)
        mirrorToArtifactStore(absPath, options.content, ctx)
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
