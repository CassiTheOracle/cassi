/**
 * Tool-Result Compressor — Phase 1 reranker-driven extractive compression.
 *
 * Replaces the old head/tail truncation strategy with the same reranker-driven
 * approach used by ToolResultDistiller (Phase 3). For each large tool result:
 *   1. Chunk by code-block boundaries (fs/read tools), grep-line matches
 *      (search tools), or paragraphs (shell/generic tools).
 *   2. Build a relevance query from the tool name + recent user/assistant context.
 *   3. Score chunks against the query via the local reranker service.
 *   4. Select the top-scoring chunks that fit within `toolResultMaxChars`.
 *   5. Restore 3 lines of context above and below each kept chunk.
 *
 * A bounded per-instance cache deduplicates reranker calls for the same
 * content in the same curation pass (content-hash keyed, LRU eviction).
 *
 * When the reranker is unavailable, falls back to a clean head-only truncation
 * with an `[N chars omitted]` note — strictly better than the old head+tail
 * clipping that frequently interleaved unrelated fragments.
 */

import type { ILogger } from '@cassicore/foundation'
import type { CompressionConfig } from './types.js'
import { classifyTool } from './classifier.js'
import { buildToolUseMapFromMessages } from './vendor/core/pipeline/turn/overflow.js'
import {
  type ContentChunk,
  hashContent,
  chunkByCodeBlocks,
  chunkByParagraphs,
  chunkByMatches,
  addContextLines,
  selectChunks,
} from './distiller.js'
import { getRerankerService } from './vendor/core/intelligence/embeddings/reranker-service.js'

interface CompressionResult {
  messages: any[]
  compressed: number
}

const MAX_CACHE_SIZE = 100
const FALLBACK_CHARS = 3000 // for head-only truncation when reranker unavailable

/**
 * Choose chunking strategy based on tool class (annotation) or tool name (regex).
 * Mirrors the distiller's logic so both phases produce compatible chunks.
 */
function getChunkStrategy(toolClass: string | null | undefined, toolName: string) {
  if (toolClass === 'fs' || /^(Read|cassi_read|read_file|write_file|patch|mcp__\w+__(read|write_file|patch))$/i.test(toolName)) {
    return chunkByCodeBlocks
  }
  if (toolClass === 'code' || /^(Grep|Glob|search_files|web_search|web_extract|browser_navigate|browser_click|browser_snapshot|browser_type|browser_scroll|browser_vision|browser_back|browser_press|browser_console|browser_get_images|vision_analyze|video_analyze|skill_view|skills_list|session_search|memory|mcp__\w+__(search|file|web))$/i.test(toolName)) {
    return chunkByMatches
  }
  if (toolClass === 'shell') return chunkByParagraphs

  // Fallback: run classifier
  const cls = classifyTool(toolName)
  if (cls === 'fs') return chunkByCodeBlocks
  if (cls === 'code') return chunkByMatches
  return chunkByParagraphs
}

export class ToolResultCompressor {
  private logger: ILogger
  /** Simple bounded cache keyed by content hash — survives one curation pass */
  private contentCache = new Map<string, string>()

  constructor(logger: ILogger) {
    this.logger = logger.child('thalamus-compressor')
  }

  async compress(
    messages: any[],
    recentWindowStart: number,
    config: CompressionConfig,
    protectedIndices: Set<number> = new Set(),
  ): Promise<CompressionResult> {
    const toolUseMap = buildToolUseMapFromMessages(messages)
    const reranker = getRerankerService(this.logger)
    const rerankerAvailable = reranker.available

    // Scan backward for recent conversational context to build the reranker query.
    // Matches the shape used by ToolResultDistiller for consistent scoring.
    let recentUserPrompt = ''
    let recentAssistantThinking = ''
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (!msg) continue
      if (!recentUserPrompt && msg.role === 'user') {
        const text = typeof msg.content === 'string' ? msg.content
          : Array.isArray(msg.content) ? msg.content.map((b: any) => typeof b === 'string' ? b : '').join(' ')
          : ''
        recentUserPrompt = text.slice(0, 500)
        if (recentUserPrompt) continue // keep scanning for assistant
      }
      if (!recentAssistantThinking && msg.role === 'assistant') {
        const text = typeof msg.content === 'string' ? msg.content : ''
        recentAssistantThinking = text.slice(-300) // tail — most likely thinking
        if (recentAssistantThinking) break
      }
    }

    const result: any[] = []
    let compressed = 0

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]

      // Never compress protected messages
      if (i >= recentWindowStart || protectedIndices.has(i)) {
        result.push(msg)
        continue
      }

      if (msg?.role !== 'user' || !Array.isArray(msg.content)) {
        result.push(msg)
        continue
      }

      let modified = false
      const newContent: any[] = []

      for (const block of msg.content) {
        if (block?.type !== 'tool_result') {
          newContent.push(block)
          continue
        }

        const toolName = toolUseMap.get(block.tool_use_id) ?? ''
        const content = typeof block.content === 'string' ? block.content : ''
        if (!content || content.length <= config.toolResultMaxChars) {
          newContent.push(block)
          continue
        }

        // Try cache before hitting the reranker
        const h = hashContent(content)
        const cached = this.contentCache.get(h)
        if (cached) {
          newContent.push({ ...block, content: cached })
          modified = true
          compressed++
          continue
        }

        // No reranker available — clean head truncation with size annotation
        if (!rerankerAvailable) {
          const truncated = content.length > FALLBACK_CHARS
            ? `${content.slice(0, FALLBACK_CHARS)}\n[compressed ${content.length}→${FALLBACK_CHARS} chars, ${content.length - FALLBACK_CHARS} omitted]`
            : content
          newContent.push({ ...block, content: truncated })
          modified = true
          compressed++
          this.setCache(h, truncated)
          continue
        }

        // Reranker-driven extractive compression
        const toolClass: string | null | undefined = msg._thalamus?.tool?.class
        const chunkFn = getChunkStrategy(toolClass, toolName)
        const chunkSize = Math.round(config.toolResultMaxChars / 4) + 200

        const chunks = chunkFn(content, chunkSize)
        if (chunks.length <= 3) {
          // Too few chunks to meaningfully select — skip reranker, keep head
          const truncated = content.slice(0, config.toolResultMaxChars)
          newContent.push({ ...block, content: truncated })
          modified = true
          compressed++
          this.setCache(h, truncated)
          continue
        }

        const query = buildCompressorQuery(toolName, recentUserPrompt, recentAssistantThinking)
        const docTexts = chunks.map(c => c.text)

        try {
          const ranked = await reranker.rerank(query, docTexts, docTexts.length)
          if (!ranked || ranked.length === 0) {
            const truncated = content.slice(0, config.toolResultMaxChars)
            newContent.push({ ...block, content: truncated })
            modified = true
            compressed++
            this.setCache(h, truncated)
            continue
          }

          const selected = selectChunks(ranked, chunks, config.toolResultMaxChars)
          if (selected.length === 0) {
            const truncated = content.slice(0, config.toolResultMaxChars)
            newContent.push({ ...block, content: truncated })
            modified = true
            compressed++
            this.setCache(h, truncated)
            continue
          }

          const allLines = content.split('\n')
          const assembled = addContextLines(selected, allLines, 3)
          const compressedContent = assembled.join('\n')

          // Truncate if still over budget (addContextLines expands context lines)
          const finalContent = compressedContent.length > config.toolResultMaxChars * 1.5
            ? `${compressedContent.slice(0, config.toolResultMaxChars)}\n[... ${content.length} bytes compressed to ${config.toolResultMaxChars} chars ...]`
            : compressedContent

          this.setCache(h, finalContent)
          newContent.push({ ...block, content: finalContent })
          modified = true
          compressed++
        } catch (err) {
          this.logger.warn('Reranker compression failed, using head truncation', {
            error: String(err),
            toolName,
            contentLen: content.length,
          })
          const truncated = content.slice(0, config.toolResultMaxChars)
          newContent.push({ ...block, content: truncated })
          modified = true
          compressed++
          this.setCache(h, truncated)
        }
      }

      result.push(modified ? { ...msg, content: newContent } : msg)
    }

    return { messages: result, compressed }
  }

  /** Insert into cache with bounded FIFO eviction */
  private setCache(key: string, value: string): void {
    this.contentCache.set(key, value)
    if (this.contentCache.size > MAX_CACHE_SIZE) {
      const firstKey = this.contentCache.keys().next().value
      if (firstKey !== undefined) this.contentCache.delete(firstKey)
    }
  }
}

/**
 * Build reranker query from tool name and recent conversational context.
 * Mirrors the distiller's buildQuery logic.
 */
function buildCompressorQuery(
  toolName: string,
  userPrompt: string,
  assistantThinking: string,
): string {
  const parts = [toolName || 'tool']
  if (userPrompt) parts.push(userPrompt.slice(0, 200))
  if (assistantThinking) parts.push(assistantThinking.slice(0, 200))
  return parts.join(' | ')
}
