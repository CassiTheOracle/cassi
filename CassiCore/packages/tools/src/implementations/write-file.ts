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

import { writeFile, mkdir, rename, unlink } from 'node:fs/promises'
import { resolve, dirname, basename, join } from 'node:path'
import { createWriteStream } from 'node:fs'
import { pipeline } from 'node:stream/promises'
import { Readable } from 'node:stream'
import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

// ============================================================================
// Constants
// ============================================================================

const MAX_SYNC_SIZE = 1024 * 1024  // 1MB - sync writes below this
const STREAM_THRESHOLD = 10 * 1024 * 1024  // 10MB - stream writes above this
const ATOMIC_WRITE = true  // Use atomic writes (temp file + rename)

// ============================================================================
// Directory Cache
// ============================================================================

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

// ============================================================================
// Optimized Write Operations
// ============================================================================

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

// ============================================================================
// Tool Definition
// ============================================================================

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
  timeoutMs: 10_000,
}

// ============================================================================
// Tool Handler
// ============================================================================

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
    
    return `Wrote ${result.bytesWritten} bytes to ${absPath} (${result.method}, ${result.durationMs}ms)`
  } catch (err) {
    return `Error writing file: ${String(err)}`
  }
}

// ============================================================================
// Batch Write Support
// ============================================================================

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
      } catch (err) {
        results.set(key, { success: false, bytesWritten: 0, error: String(err) })
      }
    }))
  }
  
  return results
}

// Export cache for management
export { globalDirCache as dirCache }
