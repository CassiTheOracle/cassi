/**
 * Concrete ThinkerToolProvider — wires to CassiCore FS, memory, and blackboard.
 *
 * Provides read-only filesystem access (workspace-bounded), memory search/store,
 * and blackboard read/post capabilities for the ThinkerSession's scoped tools.
 *
 * Safety:
 *   - All file paths are resolved and validated against the workspace root
 *   - File reads are capped at TOOL_LIMITS.maxFileBytes
 *   - Search results capped at TOOL_LIMITS.maxSearchResults
 *   - No filesystem write operations
 */

import { createReadStream } from 'node:fs'
import { readdir as readdirAsync, stat as statAsync } from 'node:fs/promises'
import { resolve, relative } from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import type { ILogger } from '@cassicore/foundation'
import type { IMemory } from '@cassicore/foundation'
import type { GlobalBlackboardRegistry } from '@cassicore/flux-team'
import type { ThinkerToolProvider } from './thinker-tools.js'
import { TOOL_LIMITS } from './thinker-tools.js'

const execFileAsync = promisify(execFile)

export interface ConcreteThinkerToolProviderDeps {
  workspaceRoot: string
  logger: ILogger
  memory?: IMemory
  blackboardRegistry?: GlobalBlackboardRegistry
}

export class ConcreteThinkerToolProvider implements ThinkerToolProvider {
  private readonly workspaceRoot: string
  private readonly logger: ILogger
  private readonly memory?: IMemory
  private blackboardRegistry?: GlobalBlackboardRegistry

  constructor(deps: ConcreteThinkerToolProviderDeps) {
    this.workspaceRoot = resolve(deps.workspaceRoot)
    this.logger = deps.logger.child?.('thinker-tool-provider') ?? deps.logger
    this.memory = deps.memory
    this.blackboardRegistry = deps.blackboardRegistry
  }

  /**
   * Wire the blackboard registry post-construction.
   * Used when the registry isn't available at construction time (modular boot).
   */
  setBlackboardRegistry(registry: GlobalBlackboardRegistry): void {
    this.blackboardRegistry = registry
    this.logger.debug('Blackboard registry wired')
  }

  /**
   * Resolve and validate a path against the workspace root.
   * Throws if the resolved path escapes the workspace.
   */
  private resolveSafePath(inputPath: string): string {
    const resolved = resolve(this.workspaceRoot, inputPath)
    const rel = relative(this.workspaceRoot, resolved)
    if (rel.startsWith('..') || rel.startsWith('/')) {
      throw new Error(`Path escapes workspace: ${inputPath}`)
    }
    return resolved
  }

  async readFile(path: string, maxBytes: number): Promise<string> {
    const safePath = this.resolveSafePath(path)
    const fileStat = await statAsync(safePath)
    if (!fileStat.isFile()) throw new Error(`Not a file: ${path}`)

    const cap = Math.min(maxBytes, TOOL_LIMITS.maxFileBytes)
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      let bytesRead = 0
      let resolved = false
      const finish = () => {
        if (resolved) return
        resolved = true
        const content = Buffer.concat(chunks).toString('utf-8')
        const truncated = bytesRead >= cap ? `\n\n[Truncated at ${cap} bytes]` : ''
        resolve(content + truncated)
      }
      const stream = createReadStream(safePath, { end: cap - 1 })
      stream.on('data', (chunk: string | Buffer) => {
        const buf = typeof chunk === 'string' ? Buffer.from(chunk) : chunk
        chunks.push(buf)
        bytesRead += buf.length
        if (bytesRead >= cap) stream.destroy()
      })
      stream.on('end', finish)
      stream.on('close', () => {
        if (bytesRead > 0) finish()
      })
      stream.on('error', (err) => {
        if (!resolved) reject(err)
      })
    })
  }

  async searchCode(
    pattern: string,
    options?: { path?: string; maxResults?: number },
  ): Promise<Array<{ file: string; line: number; text: string }>> {
    const maxResults = Math.min(
      options?.maxResults ?? TOOL_LIMITS.maxSearchResults,
      TOOL_LIMITS.maxSearchResults,
    )
    const searchDir = options?.path
      ? this.resolveSafePath(options.path)
      : this.workspaceRoot

    try {
      const { stdout } = await execFileAsync('rg', [
        '--line-number',
        '--no-heading',
        '--max-count', String(maxResults),
        '--max-filesize', '1M',
        '--color', 'never',
        pattern,
        searchDir,
      ], { maxBuffer: 1024 * 1024, timeout: 10_000 })

      return this.parseSearchOutput(stdout, maxResults)
    } catch (rgErr: any) {
      if (rgErr?.code === 1 && !rgErr?.stderr) return []

      try {
        const { stdout } = await execFileAsync('grep', [
          '-rn',
          '--include=*.ts',
          '--include=*.js',
          '--include=*.json',
          '--include=*.md',
          pattern,
          searchDir,
        ], { maxBuffer: 1024 * 1024, timeout: 10_000 })

        return this.parseSearchOutput(stdout, maxResults)
      } catch (grepErr: any) {
        if (grepErr?.code === 1 && !grepErr?.stderr) return []
        throw new Error(`Search failed: ${String(grepErr)}`)
      }
    }
  }

  private parseSearchOutput(
    stdout: string,
    maxResults: number,
  ): Array<{ file: string; line: number; text: string }> {
    const results: Array<{ file: string; line: number; text: string }> = []
    for (const line of stdout.split('\n')) {
      if (!line.trim() || results.length >= maxResults) break
      const match = line.match(/^(.+?):(\d+):(.*)$/)
      if (match) {
        results.push({
          file: relative(this.workspaceRoot, match[1]),
          line: parseInt(match[2], 10),
          text: match[3].trim(),
        })
      }
    }
    return results
  }

  async listDirectory(path: string): Promise<string[]> {
    const safePath = this.resolveSafePath(path)
    const dirStat = await statAsync(safePath)
    if (!dirStat.isDirectory()) throw new Error(`Not a directory: ${path}`)

    const entries = await readdirAsync(safePath, { withFileTypes: true })
    return entries
      .map(e => e.isDirectory() ? `${e.name}/` : e.name)
      .sort()
  }

  async memorySearch(
    query: string,
    limit: number,
  ): Promise<Array<{ content: string; tags?: string[]; key?: string }>> {
    if (!this.memory) throw new Error('Memory not available')

    const results = await this.memory.search(query, { limit })
    return results.map(r => ({
      content: r.entry.content,
      tags: r.entry.metadata?.tags as string[] | undefined,
      key: r.entry.metadata?.key as string | undefined,
    }))
  }

  async memoryStore(content: string, tags?: string[]): Promise<string> {
    if (!this.memory) throw new Error('Memory not available')

    return this.memory.store({
      type: 'insight',
      content,
      metadata: { tags: tags ?? ['thinker'], source: 'thinker-session' },
    })
  }

  async blackboardRead(name: string, channel?: string): Promise<string> {
    if (!this.blackboardRegistry) throw new Error('Blackboard not available')

    let board = this.blackboardRegistry.get(name)
    if (!board) {
      await this.blackboardRegistry.load(name)
      board = this.blackboardRegistry.get(name)
      if (!board) return `Board '${name}' not found.`
    }

    if (channel) {
      const entries = this.blackboardRegistry.getChannelEntries(name, channel as any)
      if (!entries || entries.length === 0) return `No entries in ${name}/${channel}.`
      return entries.map(e => `[${e.author}] ${e.content}`).join('\n\n')
    }

    const summary = this.blackboardRegistry.getSummary(name)
    if (!summary) return `Board '${name}' is empty.`
    return JSON.stringify(summary, null, 2)
  }

  async blackboardPost(
    name: string,
    content: string,
    channel: string,
    tags?: string[],
  ): Promise<void> {
    if (!this.blackboardRegistry) throw new Error('Blackboard not available')

    const board = this.blackboardRegistry.getOrCreate(name, { persist: true })
    board.post(channel as any, {
      author: 'thinker',
      content,
      tags: tags ?? [],
      priority: 1,
    })

    try {
      await this.blackboardRegistry.save(name)
    } catch {
      // best-effort persistence
    }
  }

  async kvGet(key: string): Promise<unknown> {
    if (!this.memory) throw new Error('Memory not available')
    return this.memory.kv_get(key)
  }

  async kvSet(key: string, value: unknown): Promise<void> {
    if (!this.memory) throw new Error('Memory not available')
    await this.memory.kv_set(key, value)
  }
}
