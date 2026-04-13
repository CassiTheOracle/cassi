import type { MessageSlot, ThalamusAnnotation, SlotContext } from '../types.js'
import type { SystemLuminanceScore } from '../../workspace/cognitive-signal.js'
import { classifyTool, extractToolResults } from '../classifier.js'

/**
 * ToolResultSlot — processes `role: 'user'` messages containing tool_result blocks.
 *
 * This is the slot that absorbs cassi_do's core functionality. It attaches
 * execution metadata (duration, output size, tool class, error status) and
 * renders a compact status prefix. During curation, it applies type-specific
 * compression strategies keyed by tool class.
 */
export class ToolResultSlot implements MessageSlot {
  readonly type = 'tool_result' as const

  matches(msg: any): boolean {
    return (
      msg?.role === 'user' &&
      Array.isArray(msg.content) &&
      msg.content.some((c: any) => c?.type === 'tool_result')
    )
  }

  augment(msg: any, ctx: SlotContext): any {
    const results = extractToolResults(msg)

    // Use the first tool result as the primary annotation
    // (multi-result messages are rare but possible with parallel tool calls)
    const primary = results[0]
    const toolUseId = primary?.toolUseId ?? ''
    const toolName = ctx.toolUseMap.get(toolUseId) ?? ''
    const toolClass = toolName ? classifyTool(toolName) : 'tool'
    const metrics = ctx.toolMetrics.get(toolUseId)

    // Compute total content chars across all result blocks
    const totalChars = results.reduce((sum, r) => sum + r.content.length, 0)
    const totalBytes = Buffer.byteLength(
      results.map(r => r.content).join('\n'),
      'utf8',
    )

    const annotation: ThalamusAnnotation = {
      ts: ctx.timestamp,
      slot: 'tool_result',
      chars: totalChars,
      tool: {
        name: toolName,
        class: toolClass,
        durationMs: metrics?.durationMs ?? 0,
        outputBytes: metrics?.outputBytes ?? totalBytes,
        isError: primary?.isError ?? false,
      },
    }

    return { ...msg, _thalamus: annotation }
  }

  compress(msg: any, annotation: ThalamusAnnotation, maxChars: number): any {
    if (!Array.isArray(msg.content)) return msg

    const toolClass = annotation.tool?.class ?? 'tool'
    const strategy = getCompressionStrategy(toolClass)

    const compressed = msg.content.map((block: any) => {
      if (block?.type !== 'tool_result') return block
      const content = typeof block.content === 'string' ? block.content : ''
      if (!content || content.length <= maxChars) return block
      return { ...block, content: strategy(content, maxChars) }
    })

    return { ...msg, content: compressed }
  }

  adjustScore(score: SystemLuminanceScore, annotation: ThalamusAnnotation): SystemLuminanceScore {
    let adjustedUrgency = score.urgency
    let adjustedCredibility = score.sourceCredibility

    // Errors get an urgency boost — they're likely still relevant
    if (annotation.tool?.isError) {
      adjustedUrgency = Math.max(adjustedUrgency, 0.40)
    }

    // Long-duration tools likely returned important data
    const duration = annotation.tool?.durationMs ?? 0
    if (duration > 3000) {
      adjustedCredibility = Math.max(adjustedCredibility, 0.80)
    } else if (duration > 1000) {
      adjustedCredibility = Math.max(adjustedCredibility, 0.75)
    }

    // Very small outputs from known-important tool classes
    // (e.g. a 50-byte bash result = command output, probably important)
    const bytes = annotation.tool?.outputBytes ?? 0
    if (bytes < 200 && bytes > 0) {
      adjustedCredibility = Math.max(adjustedCredibility, 0.78)
    }

    return {
      ...score,
      urgency: adjustedUrgency,
      sourceCredibility: adjustedCredibility,
    }
  }

  renderPrefix(annotation: ThalamusAnnotation): string {
    if (!annotation.tool) return ''

    const { name, durationMs, outputBytes, isError } = annotation.tool
    const displayName = name || 'tool'

    let size: string
    if (outputBytes < 1_024) size = `${outputBytes}B`
    else if (outputBytes < 1_048_576) size = `${(outputBytes / 1_024).toFixed(1)}KB`
    else size = `${(outputBytes / 1_048_576).toFixed(1)}MB`

    const status = isError ? '✗' : '✓'

    return `[${displayName} · ${durationMs}ms · ${size} · ${status}]`
  }
}


// Absorbed from compressor.ts — keyed by tool class instead of regex.

type CompressionStrategy = (content: string, maxChars: number) => string

function compressFs(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 20) return content.slice(0, maxChars)

  const head = lines.slice(0, 15)
  const tail = lines.slice(-5)
  const omitted = lines.length - 20
  return [...head, `[${omitted} lines omitted]`, ...tail].join('\n').slice(0, maxChars)
}

function compressCode(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 10) return content.slice(0, maxChars)

  const head = lines.slice(0, 10)
  const remaining = lines.length - 10
  return [...head, `[${remaining} more results]`].join('\n').slice(0, maxChars)
}

function compressShell(content: string, maxChars: number): string {
  const lines = content.split('\n')
  if (lines.length <= 15) return content.slice(0, maxChars)

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

function getCompressionStrategy(toolClass: string): CompressionStrategy {
  switch (toolClass) {
    case 'fs':        return compressFs
    case 'code':      return compressCode
    case 'shell':     return compressShell
    case 'memory':
    case 'archive':
    case 'sessions':  return compressCode  // search-like results
    default:          return compressGeneric
  }
}
