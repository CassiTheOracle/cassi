import type { ILogger } from '../../../types/interfaces.js'
import type { CompressionConfig, CurationConfig, RerankerCacheEntry, RerankerChunk, RerankerCompressionCache } from './types.js'
import { classifyTool } from './classifier.js'
import { getRerankerService } from '../embeddings/reranker-service.js'

interface CompressionResult {
  messages: any[]
  compressed: number
}

type ToolStrategy = (content: string, maxChars: number) => string

const READ_PATTERN = /^(Read|cassi_read|cassi_file.*read|mcp__\w+__read)$/i
const SEARCH_PATTERN = /^(Grep|Glob|mcp__\w+__search|mcp__\w+__file)$/i
const BASH_PATTERN = /^(Bash|cassi_bash|mcp__\w+__bash)$/i

function compressRead(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 20) return content

  const head = lines.slice(0, 15)
  const tail = lines.slice(-5)
  const omitted = lines.length - 20
  return [...head, `[${omitted} lines omitted]`, ...tail].join('\n').slice(0, maxChars)
}

function compressSearch(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 10) return content

  const head = lines.slice(0, 10)
  const remaining = lines.length - 10
  return [...head, `[${remaining} more matches]`].join('\n').slice(0, maxChars)
}

function compressBash(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 15) return content

  const head = lines.slice(0, 10)
  const tail = lines.slice(-5)
  const omitted = lines.length - 15
  return [...head, `[${omitted} lines omitted]`, ...tail].join('\n').slice(0, maxChars)
}

function compressGeneric(content: string, maxChars: number): string {
  if (content.length <= maxChars) return content

  const headLen = Math.floor(maxChars * 0.6)
  const tailLen = Math.floor(maxChars * 0.2)
  const head = content.slice(0, headLen)
  const tail = content.slice(-tailLen)
  const omitted = content.length - headLen - tailLen
  return `${head}\n[compressed ${content.length}→${headLen + tailLen} chars, ${omitted} omitted]\n${tail}`
}

/**
 * Select compression strategy. Prefers _thalamus annotation tool class
 * (set by slots during processing), falls back to regex matching on
 * tool name for un-annotated messages.
 */
function getStrategy(toolName: string, toolClass?: string): ToolStrategy {
  // Use annotation-based class if available (from slot processing)
  if (toolClass) {
    switch (toolClass) {
      case 'fs':       return compressRead
      case 'code':     return compressSearch
      case 'shell':    return compressBash
      case 'memory':
      case 'archive':
      case 'sessions': return compressSearch
      default:         return compressGeneric
    }
  }

  // Fallback: regex matching for un-annotated messages
  if (READ_PATTERN.test(toolName)) return compressRead
  if (SEARCH_PATTERN.test(toolName)) return compressSearch
  if (BASH_PATTERN.test(toolName)) return compressBash

  // Last resort: try classifier
  const cls = classifyTool(toolName)
  if (cls === 'fs') return compressRead
  if (cls === 'code') return compressSearch
  if (cls === 'shell') return compressBash

  return compressGeneric
}

export class ToolResultCompressor {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('thalamus-compressor')
  }

  compress(
    messages: any[],
    recentWindowStart: number,
    config: CompressionConfig,
    protectedIndices: Set<number> = new Set(),
  ): CompressionResult {
    const toolUseMap = this.buildToolUseMap(messages)

    const result: any[] = []
    let compressed = 0

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]

      // Never compress messages in the protected recent window
      if (i >= recentWindowStart) {
        result.push(msg)
        continue
      }

      // Never compress messages explicitly marked as protected (e.g. latest reads)
      if (protectedIndices.has(i)) {
        result.push(msg)
        continue
      }

      if (msg?.role !== 'user' || !Array.isArray(msg.content)) {
        result.push(msg)
        continue
      }

      let modified = false
      const newContent = msg.content.map((block: any) => {
        if (block?.type !== 'tool_result') return block

        const toolName = toolUseMap.get(block.tool_use_id) ?? ''
        const content = typeof block.content === 'string' ? block.content : ''
        if (!content) return block

        if (content.length <= config.toolResultMaxChars) return block

        // Use _thalamus annotation tool class if available
        const toolClass: string | undefined = msg._thalamus?.tool?.class
        const strategy = getStrategy(toolName, toolClass)
        const compressedContent = strategy(content, config.toolResultMaxChars)
        modified = true
        compressed++
        return { ...block, content: compressedContent }
      })

      result.push(modified ? { ...msg, content: newContent } : msg)
    }

    return { messages: result, compressed }
  }

  private buildToolUseMap(messages: any[]): Map<string, string> {
    const map = new Map<string, string>()
    for (const msg of messages) {
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && block.id && block.name) {
          map.set(block.id, block.name)
        }
      }
    }
    return map
  }
}

interface ContentChunk {
  text: string
  startLine: number
  endLine: number
  summary: string
}

function hashContent(content: string): string {
  let h = 0
  for (let i = 0; i < content.length; i++) {
    h = ((h << 5) - h + content.charCodeAt(i)) | 0
  }
  return h.toString(36)
}

function chunkByCodeBlocks(content: string, chunkSize: number): ContentChunk[] {
  const lines = content.split('\n')
  const chunks: ContentChunk[] = []
  let start = 0
  while (start < lines.length) {
    let end = start + Math.ceil(chunkSize / 40)
    let boundary = -1
    for (let i = end; i < Math.min(end + 15, lines.length); i++) {
      if (/^\s*(function |class |export |const |let |var |if |for |while |\/\/|#)/.test(lines[i])) {
        boundary = i
        break
      }
    }
    if (boundary > 0) end = boundary
    end = Math.min(end, lines.length)
    const text = lines.slice(start, end).join('\n')
    if (text.trim()) {
      chunks.push({
        text,
        startLine: start,
        endLine: end - 1,
        summary: text.split('\n').find(l => l.trim())?.slice(0, 60) ?? '',
      })
    }
    start = end
  }
  return chunks
}

function chunkByParagraphs(content: string, chunkSize: number): ContentChunk[] {
  const blocks = content.split(/\n\s*\n+/)
  const chunks: ContentChunk[] = []
  let lineOffset = 0
  let buffer = ''
  let bufStartLine = 0
  for (const block of blocks) {
    if (!block.trim()) {
      lineOffset += block.split('\n').length + 1
      continue
    }
    if (buffer.length + block.length > chunkSize && buffer.trim()) {
      chunks.push({
        text: buffer,
        startLine: bufStartLine,
        endLine: bufStartLine + buffer.split('\n').length - 1,
        summary: buffer.split('\n').find(l => l.trim())?.slice(0, 60) ?? '',
      })
      buffer = ''
    }
    if (!buffer) bufStartLine = lineOffset
    buffer += (buffer ? '\n\n' : '') + block
    lineOffset += block.split('\n').length + 1
  }
  if (buffer.trim()) {
    chunks.push({
      text: buffer,
      startLine: bufStartLine,
      endLine: bufStartLine + buffer.split('\n').length - 1,
      summary: buffer.split('\n').find(l => l.trim())?.slice(0, 60) ?? '',
    })
  }
  return chunks
}

function chunkByMatches(content: string): ContentChunk[] {
  return content.split('\n').filter(l => l.trim()).map((line, i) => ({
    text: line,
    startLine: i,
    endLine: i,
    summary: line.slice(0, 60),
  }))
}

function addContextLines(
  selectedChunks: ContentChunk[],
  allLines: string[],
  contextLines: number,
): string[] {
  const lineSet = new Set<number>()
  for (const chunk of selectedChunks) {
    for (let l = chunk.startLine; l <= chunk.endLine; l++) lineSet.add(l)
    for (let i = 1; i <= contextLines; i++) {
      if (chunk.startLine - i >= 0) lineSet.add(chunk.startLine - i)
      if (chunk.endLine + i < allLines.length) lineSet.add(chunk.endLine + i)
    }
  }
  const sorted = [...lineSet].sort((a, b) => a - b)
  const result: string[] = []
  let prev = -2
  for (const line of sorted) {
    if (line > prev + 1) {
      if (result.length > 0) result.push(`[... ${line - prev - 1} lines omitted ...]`)
    }
    result.push(allLines[line])
    prev = line
  }
  return result
}

export class RerankerCompressor {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child?.('reranker-compressor') ?? logger
  }

  async compress(
    messages: any[],
    includedIndices: Set<number>,
    cache: RerankerCompressionCache,
    config: CurationConfig,
    recentContext: { userPrompt: string; assistantThinking: string },
  ): Promise<{ messages: any[]; rerankerCompressed: number }> {
    if (!config.rerankerCompressionEnabled) return { messages, rerankerCompressed: 0 }
    const reranker = getRerankerService(this.logger)
    if (!reranker.available) {
      this.logger.warn('Reranker unavailable, skipping smart compression')
      return { messages, rerankerCompressed: 0 }
    }

    const toolUseMap = this.buildToolUseMap(messages)
    const result = [...messages]
    let rerankerCompressed = 0

    for (const idx of includedIndices) {
      const msg = messages[idx]
      if (msg?.role !== 'user' || !Array.isArray(msg.content)) continue

      let modified = false
      const newContent = []
      for (const block of msg.content) {
        if (block?.type !== 'tool_result') {
          newContent.push(block)
          continue
        }
        const content = typeof block.content === 'string' ? block.content : ''
        if (content.length < config.rerankerMinChars) {
          newContent.push(block)
          continue
        }

        const cached = this.getCached(cache, block.tool_use_id, content)
        if (cached) {
          newContent.push({ ...block, content: cached.compressedContent })
          modified = true
          continue
        }

        try {
          const toolName = toolUseMap.get(block.tool_use_id) ?? ''
          const toolClass = msg._thalamus?.tool?.class ?? classifyTool(toolName)
          const entry = await this.rerank(
            content,
            block.tool_use_id,
            toolName,
            toolClass,
            config,
            recentContext,
            reranker,
          )
          if (entry) {
            this.setCache(cache, entry)
            newContent.push({ ...block, content: entry.compressedContent })
            rerankerCompressed++
            modified = true
          } else {
            newContent.push(block)
          }
        } catch (err) {
          this.logger.warn('Reranker compression failed, keeping naive fallback', {
            toolUseId: block.tool_use_id,
            error: String(err),
          })
          newContent.push(block)
        }
      }
      if (modified) {
        result[idx] = { ...msg, content: newContent }
      }
    }
    return { messages: result, rerankerCompressed }
  }

  private async rerank(
    content: string,
    toolUseId: string,
    toolName: string,
    toolClass: string,
    config: CurationConfig,
    recentContext: { userPrompt: string; assistantThinking: string },
    reranker: any,
  ): Promise<RerankerCacheEntry | null> {
    const chunks = toolClass === 'fs' || /Read/i.test(toolName)
      ? chunkByCodeBlocks(content, config.rerankerChunkSize)
      : toolClass === 'code' || /Grep|Search/i.test(toolName)
        ? chunkByMatches(content)
        : chunkByParagraphs(content, config.rerankerChunkSize)

    if (chunks.length <= 3) return null

    const query = this.buildQuery(toolName, recentContext)
    const docTexts = chunks.map(c => c.text)

    const ranked = await reranker.rerank(query, docTexts, docTexts.length)
    if (!ranked.length) return null

    const selected = this.selectChunks(ranked, chunks, config.rerankerTargetChars)
    if (selected.length === 0) return null

    const allLines = content.split('\n')
    const assembled = addContextLines(selected, allLines, 3)
    const compressedContent = assembled.join('\n')

    const selectedSet = new Set(selected.map(c => c.startLine))
    const droppedChunks: RerankerChunk[] = chunks
      .filter(c => !selectedSet.has(c.startLine))
      .map(c => ({
        text: c.text,
        startLine: c.startLine,
        endLine: c.endLine,
        score: 0,
        summary: c.summary,
      }))

    return {
      toolUseId,
      contentHash: hashContent(content),
      originalContent: content,
      compressedContent,
      keptChunks: selected.map(c => ({
        text: c.text,
        startLine: c.startLine,
        endLine: c.endLine,
        score: ranked.find((r: { index: number; relevanceScore: number }) => r.index === chunks.indexOf(c))?.relevanceScore ?? 0,
        summary: c.summary,
      })),
      droppedChunks,
      totalChunks: chunks.length,
      originalChars: content.length,
      compressedChars: compressedContent.length,
      timestamp: Date.now(),
    }
  }

  private selectChunks(
    ranked: Array<{ index: number; relevanceScore: number }>,
    chunks: ContentChunk[],
    maxChars: number,
  ): ContentChunk[] {
    const selected: ContentChunk[] = []
    let used = 0
    const overhead = 30

    for (const r of ranked) {
      const chunk = chunks[r.index]
      if (!chunk) continue
      if (used + chunk.text.length + overhead > maxChars) continue
      selected.push(chunk)
      used += chunk.text.length + overhead
    }

    return selected.sort((a, b) => a.startLine - b.startLine)
  }

  private buildQuery(
    toolName: string,
    recentContext: { userPrompt: string; assistantThinking: string },
  ): string {
    const parts = [toolName]
    if (recentContext.userPrompt) parts.push(recentContext.userPrompt.slice(0, 200))
    if (recentContext.assistantThinking) parts.push(recentContext.assistantThinking.slice(0, 200))
    return parts.join(' | ')
  }

  private getCached(cache: RerankerCompressionCache, toolUseId: string, content: string): RerankerCacheEntry | null {
    const entry = cache.entries.get(toolUseId)
    if (!entry) return null
    if (entry.contentHash !== hashContent(content)) return null
    return entry
  }

  private setCache(cache: RerankerCompressionCache, entry: RerankerCacheEntry): void {
    cache.entries.set(entry.toolUseId, entry)
  }

  private buildToolUseMap(messages: any[]): Map<string, string> {
    const map = new Map<string, string>()
    for (const msg of messages) {
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use' && block.id && block.name) {
          map.set(block.id, block.name)
        }
      }
    }
    return map
  }
}
