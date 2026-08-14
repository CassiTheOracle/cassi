/**
 * Tool-Result Distiller — reranker-driven extractive compression.
 *
 * For each large tool result, chunk it (by code-block boundaries, paragraphs,
 * or grep-line matches depending on tool class), score chunks against the
 * recent user-prompt + assistant-thinking via the reranker service, and
 * select the top chunks that fit `distillationTargetChars`. Three lines of
 * context above and below each kept chunk are added back so the model
 * sees enough surround to interpret each match.
 *
 * Distillation is *extractive*, not generative: the output is a subset of
 * the original content. The model's linguistics are irrelevant — there's
 * no LLM call here. The previous LLM-summary distiller is gone (see
 * `docs/design/cassi-tool-result-distillation.md` and the 2026-05-07
 * empirical evaluation that showed model quality varied too sharply for
 * production reliability — Sonnet/Opus 89% planted-ID recall vs GLM-5.1
 * 33% with two outright failures).
 * Live-reads (the latest read of a file with no later write to that path)
 * must survive distillation byte-for-byte — the next edit's match string
 * needs them. The caller passes those indices in `protectedIndices`.
 */

import type { ILogger } from '@cassicore/foundation'
import { createHash } from 'node:crypto'
import type { CurationConfig, RerankerCacheEntry, RerankerChunk, RerankerCompressionCache } from './types.js'
import { classifyTool } from './classifier.js'
import { buildToolUseMapFromMessages } from '@cassicore/pipeline'
import { getRerankerService } from './vendor/core/intelligence/embeddings/reranker-service.js'

export interface ContentChunk {
  text: string
  startLine: number
  endLine: number
  summary: string
}

export function hashContent(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex').slice(0, 12)
}

export function chunkByCodeBlocks(content: string, chunkSize: number): ContentChunk[] {
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

export function chunkByParagraphs(content: string, chunkSize: number): ContentChunk[] {
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

export function chunkByMatches(content: string): ContentChunk[] {
  return content.split('\n').filter(l => l.trim()).map((line, i) => ({
    text: line,
    startLine: i,
    endLine: i,
    summary: line.slice(0, 60),
  }))
}

export function addContextLines(
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

export function selectChunks(
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

export class ToolResultDistiller {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child?.('tool-result-distiller') ?? logger
  }

  async distill(
    messages: any[],
    includedIndices: Set<number>,
    cache: RerankerCompressionCache,
    config: CurationConfig,
    recentContext: { userPrompt: string; assistantThinking: string },
    protectedIndices: Set<number> = new Set(),
  ): Promise<{ messages: any[]; distilled: number }> {
    if (!config.distillationEnabled) return { messages, distilled: 0 }
    const reranker = getRerankerService(this.logger)
    if (!reranker.available) {
      this.logger.warn('Reranker unavailable, skipping distillation')
      return { messages, distilled: 0 }
    }

    interface PendingTask {
      msgIdx: number
      blockIdx: number
      content: string
      contentHash: string
      toolUseId: string
      toolClass: string | null
    }
    interface ImmediateReplacement {
      msgIdx: number
      blockIdx: number
      newContent: string
    }
    const pending: PendingTask[] = []
    const immediate: ImmediateReplacement[] = []
    const touchedMsgIdx = new Set<number>()

    for (const idx of includedIndices) {
      // Live-reads (and other protected indices) must survive both heuristic
      // compression and distillation. The next edit's exact-match step requires
      // the original byte-for-byte content. Distilling here would force a
      // re-read on the next turn and break the read-then-edit chain.
      if (protectedIndices.has(idx)) continue
      const msg = messages[idx]
      if (msg?.role !== 'user' || !Array.isArray(msg.content)) continue
      for (let blockIdx = 0; blockIdx < msg.content.length; blockIdx++) {
        const block = msg.content[blockIdx]
        if (block?.type !== 'tool_result') continue
        const content = typeof block.content === 'string' ? block.content : ''
        if (content.length < config.distillationMinChars) continue

        const contentHash = hashContent(content)
        const cached = this.getCachedByHash(cache, block.tool_use_id, contentHash)
        if (cached) {
          immediate.push({ msgIdx: idx, blockIdx, newContent: cached.compressedContent })
          touchedMsgIdx.add(idx)
          continue
        }

        pending.push({
          msgIdx: idx,
          blockIdx,
          content,
          contentHash,
          toolUseId: block.tool_use_id,
          toolClass: msg._thalamus?.tool?.class ?? null,
        })
      }
    }

    if (pending.length === 0 && immediate.length === 0) {
      return { messages, distilled: 0 }
    }

    const result = [...messages]
    const toolUseMap = pending.length > 0 ? buildToolUseMapFromMessages(messages) : null

    // Dispatch phase: run all rerank() calls in parallel. Each call hits the
    // local zerank-server (or vLLM /v1/completions) independently; the server
    // handles concurrency and the circuit-breaker in RerankerService trips
    // uniformly across tasks if it's overloaded.
    type RankResolution = { task: PendingTask; entry: RerankerCacheEntry | null }
    const rankSettled = await Promise.allSettled(
      pending.map(async (task): Promise<RankResolution> => {
        const toolName = toolUseMap?.get(task.toolUseId) ?? ''
        const toolClass = task.toolClass ?? classifyTool(toolName)
        const entry = await this.rerank(
          task.content,
          task.contentHash,
          task.toolUseId,
          toolName,
          toolClass,
          config,
          recentContext,
          reranker,
        )
        return { task, entry }
      }),
    )

    let distilled = 0
    const computed: ImmediateReplacement[] = []
    for (const settled of rankSettled) {
      if (settled.status === 'rejected') {
        this.logger.warn('Distillation failed, keeping naive fallback', {
          error: String(settled.reason),
        })
        continue
      }
      const { task, entry } = settled.value
      if (!entry) continue
      this.setCache(cache, entry, config.distillationCacheMaxEntries)
      computed.push({ msgIdx: task.msgIdx, blockIdx: task.blockIdx, newContent: entry.compressedContent })
      touchedMsgIdx.add(task.msgIdx)
      distilled++
    }

    // Apply phase: rebuild only the messages that have replacements. For each,
    // walk the original content[] in order and substitute by blockIdx. Order
    // is preserved by indexing — Set iteration order doesn't influence the
    // final layout.
    const replacementMap = new Map<number, Map<number, string>>()
    for (const r of immediate) {
      if (!replacementMap.has(r.msgIdx)) replacementMap.set(r.msgIdx, new Map())
      replacementMap.get(r.msgIdx)!.set(r.blockIdx, r.newContent)
    }
    for (const r of computed) {
      if (!replacementMap.has(r.msgIdx)) replacementMap.set(r.msgIdx, new Map())
      replacementMap.get(r.msgIdx)!.set(r.blockIdx, r.newContent)
    }

    for (const msgIdx of touchedMsgIdx) {
      const msg = messages[msgIdx]
      const blockReplacements = replacementMap.get(msgIdx)
      if (!blockReplacements) continue
      const newContent = msg.content.map((block: any, blockIdx: number) => {
        const replaced = blockReplacements.get(blockIdx)
        if (replaced === undefined) return block
        return { ...block, content: replaced }
      })
      result[msgIdx] = { ...msg, content: newContent }
    }

    return { messages: result, distilled }
  }

  private async rerank(
    content: string,
    contentHashCache: string,
    toolUseId: string,
    toolName: string,
    toolClass: string,
    config: CurationConfig,
    recentContext: { userPrompt: string; assistantThinking: string },
    reranker: any,
  ): Promise<RerankerCacheEntry | null> {
    const chunks = toolClass === 'fs' || /Read/i.test(toolName)
      ? chunkByCodeBlocks(content, config.distillationChunkSize)
      : toolClass === 'code' || /Grep|Search/i.test(toolName)
        ? chunkByMatches(content)
        : chunkByParagraphs(content, config.distillationChunkSize)

    if (chunks.length <= 3) return null

    const query = this.buildQuery(toolName, recentContext)
    const docTexts = chunks.map(c => c.text)

    const ranked = await reranker.rerank(query, docTexts, docTexts.length)
    if (!ranked.length) return null

    const selected = selectChunks(ranked, chunks, config.distillationTargetChars)
    if (selected.length === 0) return null

    const allLines = content.split('\n')
    const assembled = addContextLines(selected, allLines, 3)
    const compressedContent = assembled.join('\n')

    const scoreByPosition = new Map<number, number>()
    for (const r of ranked as Array<{ index: number; relevanceScore: number }>) {
      scoreByPosition.set(r.index, r.relevanceScore)
    }
    const positionByChunk = new Map<ContentChunk, number>()
    for (let i = 0; i < chunks.length; i++) positionByChunk.set(chunks[i], i)

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
      contentHash: contentHashCache,
      originalContent: content,
      compressedContent,
      keptChunks: selected.map(c => ({
        text: c.text,
        startLine: c.startLine,
        endLine: c.endLine,
        score: scoreByPosition.get(positionByChunk.get(c) ?? -1) ?? 0,
        summary: c.summary,
      })),
      droppedChunks,
      totalChunks: chunks.length,
      originalChars: content.length,
      compressedChars: compressedContent.length,
      timestamp: Date.now(),
    }
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

  private getCachedByHash(cache: RerankerCompressionCache, toolUseId: string, contentHash: string): RerankerCacheEntry | null {
    const entry = cache.entries.get(toolUseId)
    if (!entry) return null
    if (entry.contentHash !== contentHash) return null
    return entry
  }

  /**
   * Insert into the per-session cache and FIFO-evict by `timestamp` when the
   * map exceeds `maxEntries`. Long autonomous sessions can otherwise hold
   * every original tool result indefinitely (each entry retains
   * `originalContent` for `Thalamus.expandToolResult` recall).
   */
  private setCache(cache: RerankerCompressionCache, entry: RerankerCacheEntry, maxEntries: number): void {
    cache.entries.set(entry.toolUseId, entry)
    if (maxEntries <= 0 || cache.entries.size <= maxEntries) return
    let oldestId: string | null = null
    let oldestTs = Infinity
    for (const [id, e] of cache.entries) {
      if (e.timestamp < oldestTs) { oldestTs = e.timestamp; oldestId = id }
    }
    if (oldestId !== null) cache.entries.delete(oldestId)
  }
}
