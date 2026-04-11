import type { ILogger } from '../../../types/interfaces.js'
import type { CompressionConfig } from './types.js'

interface CompressionResult {
  messages: any[]
  compressed: number
  deduped: number
}

type ToolStrategy = (content: string, maxChars: number) => string

const READ_PATTERN = /^(Read|mcp__\w+__read)$/
const SEARCH_PATTERN = /^(Grep|Glob|mcp__\w+__search|mcp__\w+__file)$/
const BASH_PATTERN = /^(Bash|mcp__\w+__bash)$/

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

function getStrategy(toolName: string): ToolStrategy {
  if (READ_PATTERN.test(toolName)) return compressRead
  if (SEARCH_PATTERN.test(toolName)) return compressSearch
  if (BASH_PATTERN.test(toolName)) return compressBash
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
    fileReadMap: Map<string, number>,
  ): CompressionResult {
    const toolUseMap = this.buildToolUseMap(messages)

    this.updateFileReadMap(messages, toolUseMap, fileReadMap)

    const result: any[] = []
    let compressed = 0
    let deduped = 0

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]

      if (i >= recentWindowStart) {
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

        const dedupResult = this.checkDedup(block, toolName, i, fileReadMap)
        if (dedupResult !== null) {
          modified = true
          deduped++
          return { ...block, content: dedupResult }
        }

        if (content.length <= config.toolResultMaxChars) return block

        const strategy = getStrategy(toolName)
        const compressedContent = strategy(content, config.toolResultMaxChars)
        modified = true
        compressed++
        return { ...block, content: compressedContent }
      })

      result.push(modified ? { ...msg, content: newContent } : msg)
    }

    return { messages: result, compressed, deduped }
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

  private updateFileReadMap(
    messages: any[],
    toolUseMap: Map<string, string>,
    fileReadMap: Map<string, number>,
  ): void {
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]
      if (!Array.isArray(msg?.content)) continue
      for (const block of msg.content) {
        if (block?.type === 'tool_use') {
          const toolName = block.name ?? ''
          if (READ_PATTERN.test(toolName)) {
            const filePath = block.input?.filePath ?? block.input?.path ?? block.input?.file_path ?? ''
            if (filePath) {
              fileReadMap.set(filePath, i)
            }
          }
        }
      }
    }
  }

  private checkDedup(
    block: any,
    toolName: string,
    currentIndex: number,
    fileReadMap: Map<string, number>,
  ): string | null {
    if (!READ_PATTERN.test(toolName)) return null

    const content = typeof block.content === 'string' ? block.content : ''
    const pathMatch = content.match(/^\s*\d+\t/) ? null :
      content.match(/^(?:File|Reading|Content of)\s+[`"]?([^\s`"]+)/i)

    if (!pathMatch) return null

    const filePath = pathMatch[1]
    const latestIndex = fileReadMap.get(filePath)
    if (latestIndex !== undefined && latestIndex > currentIndex) {
      return `[Earlier read of ${filePath} — see message ${latestIndex} for latest]`
    }

    return null
  }
}
