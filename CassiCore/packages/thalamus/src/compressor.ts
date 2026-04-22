import type { ILogger } from '../../../types/interfaces.js'
import type { CompressionConfig } from './types.js'
import { classifyTool } from './classifier.js'

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
