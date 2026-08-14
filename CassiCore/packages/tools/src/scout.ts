/**
 * Scout — research subagent pool for CassiCore observers.
 *
 * Wraps `delegate_task` (via the Hermes MCP client) so that callers
 * — the DMN observer, Helix postures, Constellation corpus — can
 * dispatch research investigations without knowing about subagent
 * mechanics.  The Scout owns the subagent prompt, tool selection,
 * concurrency limiting, result caching, file injection, and session
 * context injection.
 *
 * Context enrichment (transparent to callers):
 *   1. File paths found in the `context` string are read and their
 *      contents injected into the subagent prompt — the subagent
 *      doesn't need to re-read files the caller already referenced.
 *   2. When a `sessionContextProvider` is installed, the Scout pulls
 *      recent session context and includes it — the observer doesn't
 *      need to manually extract and inline conversation history.
 *
 * Investigations are read-only: web_search, read_file, search_files,
 * web_extract, and terminal.  No session_search (privacy boundary).
 */

import { readFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { getHermesMcpClient } from './hermes-mcp-client.js'
import { rootLogger } from '../vendor/core/logger.js'
import type { ILogger } from "@cassicore/foundation"

const logger: ILogger = rootLogger.child('scout')

export interface ScoutInvestigation {
  /** What to research — the observer's question. */
  topic: string
  /** Background context. May mention file paths — they'll be read and injected. */
  context: string
  /** Explicit file paths to read and inject into the subagent prompt. */
  files?: string[]
  /** Session ID for context injection (requires sessionContextProvider). */
  sessionId?: string
  /** Max subagent iterations (default: 12). */
  maxIterations?: number
  /** Timeout in ms (default: 120_000). */
  timeoutMs?: number
}

export interface ScoutFindings {
  /** The subagent's synthesized answer. */
  summary: string
  /** Key sources referenced (URLs, file paths). */
  sources: string[]
  /** Confidence estimate from the subagent (0–1). */
  confidence: number
  /** Number of tool calls the subagent made. */
  toolCalls: number
  /** How long the investigation took (ms). */
  durationMs: number
  /** When these findings were produced (epoch ms). */
  timestamp: number
}

/** Provider for session context injection — set once at construction. */
export type SessionContextProvider = (sessionId: string, maxMessages?: number) => Promise<string>

export interface ScoutOptions {
  maxConcurrent?: number
  sessionContextProvider?: SessionContextProvider
}

const DEFAULT_MAX_ITERATIONS = 12
const DEFAULT_TIMEOUT_MS = 120_000
const DEFAULT_MAX_CONCURRENT = 3
const MAX_FILE_CHARS = 8_000
const MAX_INJECTED_CHARS = 20_000
const MAX_SESSION_CONTEXT_CHARS = 6_000

const SCOUT_TOOLS = [
  'web_search',
  'web_extract',
  'read_file',
  'search_files',
  'terminal',
]

const CACHE_TTL_MS = 120_000

/**
 * Extract probable file paths from a free-text context string.
 * Matches absolute and relative paths ending in a known extension.
 */
const FILE_PATH_RE = /(?:\/[\w.~-][\w\/.~-]*\.\w{1,10})|(?:[\w.-]+(?:\/[\w.-]+)+\.\w{1,10})/g

function extractFilePaths(text: string): string[] {
  const matches = text.match(FILE_PATH_RE)
  if (!matches) return []
  const seen = new Set<string>()
  const paths: string[] = []
  for (const m of matches) {
    const clean = m.replace(/^["'`]|["'`]$/g, '').trim()
    if (clean && !seen.has(clean) && /\.[a-z]{1,10}$/i.test(clean)) {
      seen.add(clean)
      paths.push(clean)
    }
  }
  return paths.slice(0, 5)
}

function buildScoutPrompt(
  topic: string,
  context: string,
  enrichedContext: string,
): string {
  const parts = [
    `You are a research scout for CassiCore's observer network.`,
    `Your job is to investigate a specific topic and return structured findings.`,
    '',
    `## Rules`,
    `- Use ONLY read-only tools: search the web, read files, search the codebase, run terminal commands.`,
    `- Do NOT modify any files or perform destructive actions.`,
    `- Be thorough but concise.  Your findings will be synthesized by an observer.`,
    `- You have been provided with pre-loaded file contents and session context.  Use them.`,
    '',
    `## Output Format`,
    `Respond with exactly this structure (no other text):`,
    '',
    `SUMMARY: <2–5 sentences answering the research question>`,
    `SOURCES:`,
    `- <source URL or file path>`,
    `- <source URL or file path>`,
    `CONFIDENCE: <0.0–1.0>`,
    '',
    `## Research Topic`,
    topic,
  ]

  if (enrichedContext) {
    parts.push('', `## Pre-loaded Context`, enrichedContext)
  }

  parts.push('', `## Caller Context`, context)
  return parts.join('\n')
}

async function enrichContext(
  params: ScoutInvestigation,
  sessionProvider?: SessionContextProvider,
): Promise<string> {
  const sections: string[] = []
  let totalChars = 0

  const extractedPaths = extractFilePaths(params.context)
  const allFilePaths = dedupePaths([...extractedPaths, ...(params.files ?? [])])

  if (allFilePaths.length > 0) {
    const fileContents: string[] = []
    for (const filePath of allFilePaths) {
      if (totalChars >= MAX_INJECTED_CHARS) break
      const content = await readFileForInjection(filePath)
      if (content) {
        const chunk = content.slice(0, Math.min(MAX_FILE_CHARS, MAX_INJECTED_CHARS - totalChars))
        fileContents.push(`### File: ${filePath}\n\`\`\`\n${chunk}\n\`\`\``)
        totalChars += chunk.length
      }
    }
    if (fileContents.length > 0) {
      sections.push(`<injected_files>\n${fileContents.join('\n\n')}\n</injected_files>`)
    }
  }

  if (params.sessionId && sessionProvider) {
    try {
      const sessionCtx = await sessionProvider(params.sessionId, 20)
      if (sessionCtx) {
        const capped = sessionCtx.slice(0, MAX_SESSION_CONTEXT_CHARS)
        sections.push(`<session_context sessionId="${params.sessionId}">\n${capped}\n</session_context>`)
      }
    } catch (err) {
      logger.debug('Session context injection failed', { error: String(err) })
    }
  }

  return sections.join('\n\n')
}

function dedupePaths(paths: string[]): string[] {
  const seen = new Set<string>()
  return paths.filter(p => {
    if (seen.has(p)) return false
    seen.add(p)
    return true
  })
}

async function readFileForInjection(filePath: string): Promise<string | null> {
  try {
    if (!existsSync(filePath)) return null
    const content = await readFile(filePath, 'utf-8')
    if (content.length === 0) return null
    return content
  } catch {
    return null
  }
}

interface CacheEntry {
  topic: string
  findings: ScoutFindings
  cachedAt: number
}

export class Scout {
  private active = 0
  private maxConcurrent: number
  private cache = new Map<string, CacheEntry>()
  private sessionContextProvider?: SessionContextProvider
  private queue: Array<() => void> = []

  constructor(opts: ScoutOptions = {}) {
    this.maxConcurrent = opts.maxConcurrent ?? DEFAULT_MAX_CONCURRENT
    this.sessionContextProvider = opts.sessionContextProvider
  }

  /**
   * Dispatch a research investigation.  Returns cached results if the
   * same topic was investigated recently.  Queues when the pool is full
   * (event-driven, no spin-wait).
   *
   * Context enrichment is transparent:
   *   - File paths in `context` or `files` are read and injected.
   *   - When `sessionId` is set and a sessionContextProvider was
   *     configured at construction, recent session context is injected.
   *
   * Throws on timeout or subagent failure.
   */
  async investigate(params: ScoutInvestigation): Promise<ScoutFindings> {
    const cacheKey = this.cacheKey(params.topic, params.context)
    const cached = this.cache.get(cacheKey)
    if (cached && (Date.now() - cached.cachedAt) < CACHE_TTL_MS) {
      logger.debug('Scout cache hit', { topic: params.topic.slice(0, 80) })
      return cached.findings
    }

    await this.acquireSlot()

    const startTime = Date.now()
    try {
      const findings = await this.runInvestigation(params)
      findings.timestamp = Date.now()

      this.cache.set(cacheKey, { topic: params.topic, findings, cachedAt: Date.now() })
      this.pruneCache()

      return findings
    } finally {
      this.releaseSlot()
      logger.debug('Scout investigation complete', {
        topic: params.topic.slice(0, 80),
        durationMs: Date.now() - startTime,
        active: this.active,
      })
    }
  }

  get activeCount(): number {
    return this.active
  }

  clearCache(): void {
    this.cache.clear()
  }

  private cacheKey(topic: string, context: string): string {
    const key = `${topic.slice(0, 200)}|${context.slice(0, 200)}`
    let hash = 0
    for (let i = 0; i < key.length; i++) {
      hash = ((hash << 5) - hash) + key.charCodeAt(i)
      hash |= 0
    }
    return String(hash)
  }

  private async acquireSlot(): Promise<void> {
    if (this.active < this.maxConcurrent) {
      this.active++
      return
    }
    return new Promise<void>(resolve => {
      this.queue.push(() => {
        this.active++
        resolve()
      })
    })
  }

  private releaseSlot(): void {
    this.active--
    const next = this.queue.shift()
    if (next) next()
  }

  private async runInvestigation(params: ScoutInvestigation): Promise<ScoutFindings> {
    const maxIterations = params.maxIterations ?? DEFAULT_MAX_ITERATIONS
    const timeoutMs = params.timeoutMs ?? DEFAULT_TIMEOUT_MS

    const enriched = await enrichContext(params, this.sessionContextProvider)

    const prompt = buildScoutPrompt(params.topic, params.context, enriched)

    logger.info('Scout dispatching investigation', {
      topic: params.topic.slice(0, 80),
      maxIterations,
      enrichedChars: enriched.length,
    })

    const client = getHermesMcpClient()

    const rawResult = await Promise.race([
      client.callTool('delegate_task', {
        goal: prompt,
        toolsets: SCOUT_TOOLS,
      }),
      new Promise<string>((_, reject) =>
        setTimeout(() => reject(new Error('Scout investigation timed out')), timeoutMs),
      ),
    ])

    return this.parseFindings(rawResult, Date.now())
  }

  private parseFindings(raw: string, startTime: number): ScoutFindings {
    let summary = ''
    let sources: string[] = []
    let confidence = 0.5

    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object' && !parsed.error) {
        summary = parsed.summary ?? parsed.result ?? parsed.content ?? raw
        sources = Array.isArray(parsed.sources) ? parsed.sources : []
        confidence = typeof parsed.confidence === 'number'
          ? Math.max(0, Math.min(1, parsed.confidence))
          : 0.5
      } else if (parsed?.error) {
        summary = `Scout error: ${String(parsed.error).slice(0, 500)}`
      }
    } catch {
      const lines = raw.split('\n')
      let section: 'summary' | 'sources' | 'confidence' | 'none' = 'none'
      const summaryLines: string[] = []

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        if (/^SUMMARY:/i.test(trimmed)) {
          section = 'summary'
          const content = trimmed.replace(/^SUMMARY:\s*/i, '')
          if (content) summaryLines.push(content)
          continue
        }
        if (/^SOURCES?:/i.test(trimmed)) {
          section = 'sources'
          continue
        }
        if (/^CONFIDENCE:/i.test(trimmed)) {
          section = 'confidence'
          const val = parseFloat(trimmed.replace(/^CONFIDENCE:\s*/i, ''))
          if (!isNaN(val)) confidence = Math.max(0, Math.min(1, val))
          continue
        }

        switch (section) {
          case 'summary':
            summaryLines.push(trimmed)
            break
          case 'sources':
            const source = trimmed.replace(/^[-*]\s*/, '').trim()
            if (source && !source.startsWith('#')) {
              sources.push(source)
            }
            break
        }
      }
      summary = summaryLines.join(' ').trim()
    }

    if (!summary) {
      summary = raw.slice(0, 2000)
    }

    return {
      summary,
      sources,
      confidence,
      toolCalls: 0,
      durationMs: Date.now() - startTime,
      timestamp: Date.now(),
    }
  }

  private pruneCache(): void {
    const cutoff = Date.now() - CACHE_TTL_MS * 2
    this.cache.forEach((entry, key) => {
      if (entry.cachedAt < cutoff) {
        this.cache.delete(key)
      }
    })
  }
}

let _instance: Scout | null = null

export function getScout(opts?: ScoutOptions): Scout {
  if (!_instance) {
    _instance = new Scout(opts)
  }
  return _instance
}
