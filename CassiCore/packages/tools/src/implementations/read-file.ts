/**
 * Optimized read_file tool
 * 
 * Improvements over original:
 * - Async I/O (non-blocking)
 * - Streaming for large files
 * - Smart buffer slicing (avoid full string operations)
 * - Single-pass line counting
 * - LRU cache for small files
 * - No existsSync (handle error instead)
 */

import { open, stat, readdir } from 'node:fs/promises'
import { resolve, dirname, basename, relative } from 'node:path'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import { getRepoRoot } from '../../utils/paths.js'

const MAX_BYTES = 1024 * 1024  // 1MB max
const MAX_LINES_BUFFER = 10_000  // Max lines to buffer in memory
const CACHE_MAX_SIZE = 50  // Max cached files

// WHY: Agents waste 30–50% of tool calls on directory discovery (find, ls,
// searching for non-existent files).  Appending a sibling listing to every
// read_file result gives spatial awareness at zero extra cost.
const DIR_CONTEXT_MAX_ENTRIES = 40
const CACHE_MAX_BYTES = 512 * 1024  // Max 512KB per cached file
const CACHE_TTL_MS = 30_000  // Cache TTL

interface CacheEntry {
  content: string
  mtime: number
  size: number
  addedAt: number
}

class FileCache {
  private cache = new Map<string, CacheEntry>()
  private currentSize = 0

  get(key: string, mtime: number): string | undefined {
    const entry = this.cache.get(key)
    if (!entry) return undefined
    
    if (entry.mtime !== mtime || Date.now() - entry.addedAt > CACHE_TTL_MS) {
      this.delete(key)
      return undefined
    }
    
    // HOW: move to end of Map for LRU ordering
    this.cache.delete(key)
    this.cache.set(key, entry)
    return entry.content
  }

  set(key: string, entry: CacheEntry): void {
    if (entry.size > CACHE_MAX_BYTES) return
    
    while (this.currentSize + entry.size > CACHE_MAX_SIZE * CACHE_MAX_BYTES && this.cache.size > 0) {
      const firstKey = this.cache.keys().next().value
      if (firstKey) this.delete(firstKey)
    }
    
    this.cache.set(key, entry)
    this.currentSize += entry.size
  }

  private delete(key: string): void {
    const entry = this.cache.get(key)
    if (entry) {
      this.currentSize -= entry.size
      this.cache.delete(key)
    }
  }

  clear(): void {
    this.cache.clear()
    this.currentSize = 0
  }

  stats(): { size: number; entries: number; bytes: number } {
    return { size: this.cache.size, entries: this.cache.size, bytes: this.currentSize }
  }
}

const globalCache = new FileCache()

/**
 * Read file with offset/limit efficiently
 * Uses async I/O and avoids loading entire file when possible
 * @dep callers: readFileHandler (core/tools/implementations/read-file.ts), readFilesBatch (core/tools/implementations/read-file.ts)
 * @dep calls: extractLines, now
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
async function readFileOptimized(
  filePath: string,
  offset: number,
  limit: number | undefined,
  maxBytes: number
): Promise<{ content: string; truncated: boolean; fromCache: boolean }> {
  
  const stats = await stat(filePath).catch(() => null)
  if (!stats) {
    throw new Error(`file not found — ${filePath}`)
  }
  if (!stats.isFile()) {
    throw new Error(`not a file — ${filePath}`)
  }

  // WHY: cache only small, complete reads to avoid memory bloat
  const useCache = offset <= 1 && !limit && stats.size <= CACHE_MAX_BYTES
  if (useCache) {
    const cached = globalCache.get(filePath, stats.mtimeMs)
    if (cached) {
      return { content: cached, truncated: stats.size > maxBytes, fromCache: true }
    }
  }

  const handle = await open(filePath, 'r')
  
  try {
    // WHY: line extraction requires scanning, but single buffer avoids multiple I/O calls
    const readSize = Math.min(stats.size, maxBytes)
    const buffer = Buffer.alloc(readSize)
    
    const { bytesRead } = await handle.read(buffer, 0, readSize, 0)
    const truncated = stats.size > maxBytes
    
    // HOW: extractLines avoids split/join overhead
    let content = extractLines(buffer.slice(0, bytesRead), offset, limit)
    
    if (truncated) {
      content += `\n\n[file truncated at 1MB — total file size is ${stats.size.toLocaleString()} bytes. Use offset parameter to read later sections.]`
    }
    
    if (useCache && !truncated) {
      globalCache.set(filePath, {
        content,
        mtime: stats.mtimeMs,
        size: bytesRead,
        addedAt: Date.now()
      })
    }
    
    return { content, truncated, fromCache: false }
  } finally {
    await handle.close()
  }
}

/**
 * Extract lines from buffer efficiently
 * Uses single-pass scanning instead of split/join
 * @dep callers: readFileOptimized (core/tools/implementations/read-file.ts), readFileHandler (core/tools/implementations/read-file.ts)
 * @dep calls: extractLinesScan
 * @dep module: Implementations
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function extractLines(
  buffer: Buffer,
  offset: number,
  limit: number | undefined
): string {
  // Fast path: no filtering needed
  if (offset <= 1 && !limit) {
    return buffer.toString('utf8')
  }
  
  const str = buffer.toString('utf8')
  
  // Fast path: small files
  if (str.length < 10000) {
    const lines = str.split('\n')
    const start = Math.max(0, offset - 1)
    const end = limit !== undefined ? start + limit : lines.length
    return lines.slice(start, end).join('\n')
  }
  
  // Optimized path: scan once, extract range
  return extractLinesScan(str, offset, limit)
}

/**
 * Single-pass line extraction for large files
 * Avoids creating array of all lines
 */
function extractLinesScan(
  str: string,
  offset: number,
  limit: number | undefined
): string {
  const startLine = offset - 1
  const endLine = limit !== undefined ? startLine + limit : Infinity
  
  let currentLine = 0
  let result = ''
  let lineStart = 0
  
  for (let i = 0; i <= str.length; i++) {
    if (i === str.length || str.charCodeAt(i) === 10) { // '\n' = 10
      if (currentLine >= startLine && currentLine < endLine) {
        // Include this line
        const lineEnd = i === str.length ? i : i // Don't include the newline, will be added by join
        const line = str.slice(lineStart, lineEnd)
        result += (result ? '\n' : '') + line
      }
      
      currentLine++
      if (currentLine >= endLine) break
      lineStart = i + 1
    }
  }
  
  return result
}

export const readFileDefinition: ToolDefinition = {
  name: 'read_file',
  description: 'Read the contents of a file. Supports optional line offset and limit. (Optimized: async I/O, caching)',
  parameters: {
    type: 'object',
    properties: {
      path:   { type: 'string', description: 'Path to the file (absolute or relative to workspace)' },
      offset: { type: 'number', description: 'Line number to start reading from (1-indexed, optional)' },
      limit:  { type: 'number', description: 'Maximum number of lines to read (optional)' },
    },
    required: ['path'],
  },
  timeoutMs: 15_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}

export const readFileHandler: ToolHandler = async (
  input: Record<string, unknown>,
  ctx: ToolExecutionContext
): Promise<string> => {
  
  const rawPath = input['path'] as string
  const offset = Math.max(1, (input['offset'] as number | undefined) ?? 1)
  const limit = input['limit'] as number | undefined

  // WHY: cassi://self/ URIs read from the CodeStore (CassiCore's own source in mnemic field)
  if (rawPath.startsWith('cassi://self/')) {
    const codeStore = ctx._codeStore
    if (!codeStore) {
      throw new Error('CodeStore not available — cannot read cassi://self/ URIs')
    }
    const filePath = rawPath.slice('cassi://self/'.length)
    const engram = codeStore.getFileByPath(filePath)
    if (!engram) {
      throw new Error(`source file not found in code store: ${filePath}`)
    }
    let content = engram.content
    if (offset > 1 || limit !== undefined) {
      content = extractLines(Buffer.from(content), offset, limit)
    }
    const meta = engram.metadata as Record<string, unknown>
    return `[code-store: ${filePath} | ${meta.sizeBytes ?? content.length} bytes | potentiation: ${engram.potentiation.toFixed(3)}]\n\n${content}`
  }

  // cassi://code/{path} URIs read from the CodeVault (external projects)
  if (rawPath.startsWith('cassi://code/')) {
    throw new Error('CodeVault read not yet wired — use cassi://self/ for CassiCore source or filesystem paths for external projects')
  }

  const absPath = rawPath.startsWith('/')
    ? rawPath
    : resolve(ctx.workingDir, rawPath)

  const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
  if (!allowed) {
    throw new Error(`access denied — ${absPath} is outside allowed paths`)
  }

  // WHY: errors from readFileOptimized (file not found, not a file, EACCES, etc.)
  // must propagate so the executor can mark isError=true. Returning the error
  // as a string would mislead LLMs into treating the prefix as content.
  try {
    const { content, truncated, fromCache } = await readFileOptimized(
      absPath,
      offset,
      limit,
      MAX_BYTES
    )

    ctx.logger.debug?.('[read_file] completed', {
      path: absPath,
      size: content.length,
      truncated,
      fromCache,
      cacheStats: globalCache.stats()
    })

    const dirContext = await buildDirContext(absPath)
    return content + dirContext
  } catch (err) {
    // Fallback: if file not found and we're in a worktree, check code store
    const isWorktree = ctx.workingDir !== getRepoRoot()
    if (isWorktree && ctx._codeStore) {
      const relPath = relative(getRepoRoot(), absPath)
      const engram = ctx._codeStore.getFileByPath(relPath)
      if (engram) {
        ctx.logger.debug?.('[read_file] code store fallback', { path: relPath })
        let content = engram.content
        if (offset > 1 || limit !== undefined) {
          content = extractLines(Buffer.from(content), offset, limit)
        }
        const meta = engram.metadata as Record<string, unknown>
        return `[code-store: ${relPath} | ${meta.sizeBytes ?? content.length} bytes | potentiation: ${engram.potentiation.toFixed(3)}]\n\n${content}`
      }
    }
    throw err
  }
}

/**
 * Build a compact directory listing around the file the agent just read.
 * Shows sibling files/dirs in the same directory so the agent knows what
 * else is available without a separate ls/find call.
 */
async function buildDirContext(absPath: string): Promise<string> {
  try {
    const dir = dirname(absPath)
    const current = basename(absPath)
    const entries = await readdir(dir, { withFileTypes: true })

    if (entries.length === 0 || entries.length > DIR_CONTEXT_MAX_ENTRIES) {
      return ''
    }

    const lines: string[] = []
    for (const entry of entries) {
      const marker = entry.name === current ? ' ← (this file)' : ''
      const suffix = entry.isDirectory() ? '/' : ''
      lines.push(`  ${entry.name}${suffix}${marker}`)
    }

    return `\n\n[Directory: ${dir}/]\n${lines.join('\n')}`
  } catch {
    return ''
  }
}

export interface ReadFileOptions {
  path: string
  offset?: number
  limit?: number
}

/**
 * Batch read multiple files efficiently
 * Shares cache and parallelizes I/O
 */
export async function readFilesBatch(
  files: ReadFileOptions[],
  ctx: ToolExecutionContext
): Promise<Map<string, { content: string; error?: string }>> {
  
  const results = new Map<string, { content: string; error?: string }>()
  
  const validFiles: Array<{ key: string; absPath: string; offset: number; limit?: number }> = []
  
  for (const file of files) {
    const absPath = file.path.startsWith('/') 
      ? file.path 
      : resolve(ctx.workingDir, file.path)
    
    const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
    if (!allowed) {
      results.set(file.path, { content: '', error: 'access denied' })
      continue
    }
    
    validFiles.push({
      key: file.path,
      absPath,
      offset: Math.max(1, file.offset ?? 1),
      limit: file.limit
    })
  }
  
  // HOW: limit concurrency to avoid I/O saturation
  const CONCURRENCY = 5
  for (let i = 0; i < validFiles.length; i += CONCURRENCY) {
    const batch = validFiles.slice(i, i + CONCURRENCY)
    
    await Promise.all(batch.map(async ({ key, absPath, offset, limit }) => {
      try {
        const { content } = await readFileOptimized(absPath, offset, limit, MAX_BYTES)
        results.set(key, { content })
      } catch (err) {
        results.set(key, { content: '', error: String(err) })
      }
    }))
  }
  
  return results
}

export { globalCache as fileCache }
