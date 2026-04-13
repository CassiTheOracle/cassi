import type { MessageSlot, ThalamusAnnotation, SlotContext } from '../types.js'
import type { SystemLuminanceScore } from '../../workspace/cognitive-signal.js'
import { extractMessageContent } from '../scorer.js'

const CODE_BLOCK_RE = /```[\s\S]*?```/g

/**
 * AssistantSlot — processes `role: 'assistant'` text-only messages (no tool_use blocks).
 *
 * Assistant prose is the least credible message type — it's generated text,
 * not ground truth from tools or explicit user instructions. During compression,
 * code blocks are preserved while explanatory prose is aggressively trimmed.
 */
export class AssistantSlot implements MessageSlot {
  readonly type = 'assistant' as const

  matches(msg: any): boolean {
    if (msg?.role !== 'assistant') return false
    if (Array.isArray(msg.content) && msg.content.some((c: any) => c?.type === 'tool_use')) {
      return false
    }
    return true
  }

  augment(msg: any, ctx: SlotContext): any {
    const content = extractMessageContent(msg)
    const hasCode = CODE_BLOCK_RE.test(content)

    const annotation: ThalamusAnnotation = {
      ts: ctx.timestamp,
      slot: 'assistant',
      chars: content.length,
      hasCode,
    }

    return { ...msg, _thalamus: annotation }
  }

  compress(msg: any, annotation: ThalamusAnnotation, maxChars: number): any {
    const content = extractMessageContent(msg)
    if (content.length <= maxChars) return msg

    if (annotation.hasCode) {
      return this.compressPreservingCode(msg, content, maxChars)
    }

    // Pure prose — aggressive head+tail compression
    const headLen = Math.floor(maxChars * 0.7)
    const tailLen = Math.floor(maxChars * 0.15)
    const head = content.slice(0, headLen)
    const tail = content.slice(-tailLen)
    const omitted = content.length - headLen - tailLen

    const compressed = `${head}\n[${omitted} chars of assistant prose omitted]\n${tail}`
    return this.replaceContent(msg, compressed)
  }

  adjustScore(score: SystemLuminanceScore, annotation: ThalamusAnnotation): SystemLuminanceScore {
    let adjustedCred = Math.min(score.sourceCredibility, 0.60)

    // Code-heavy assistant messages are slightly more credible
    // (they contain concrete implementation, not just prose)
    if (annotation.hasCode) {
      adjustedCred = Math.max(adjustedCred, 0.55)
    }

    return {
      ...score,
      sourceCredibility: adjustedCred,
    }
  }

  renderPrefix(_annotation: ThalamusAnnotation): string {
    return ''
  }

  /**
   * Compress while preserving code blocks — extract code blocks first,
   * then compress the surrounding prose.
   */
  private compressPreservingCode(msg: any, content: string, maxChars: number): any {
    const codeBlocks: string[] = []
    const withoutCode = content.replace(CODE_BLOCK_RE, (match) => {
      codeBlocks.push(match)
      return `\n__CODE_BLOCK_${codeBlocks.length - 1}__\n`
    })

    // Budget: code blocks get priority, prose gets the remainder
    const codeChars = codeBlocks.reduce((sum, b) => sum + b.length, 0)
    const proseMax = Math.max(200, maxChars - codeChars)

    let compressedProse = withoutCode
    if (withoutCode.length > proseMax) {
      const headLen = Math.floor(proseMax * 0.7)
      const head = withoutCode.slice(0, headLen)
      const omitted = withoutCode.length - headLen
      compressedProse = `${head}\n[${omitted} chars of prose omitted]`
    }

    // Re-insert code blocks
    let result = compressedProse
    for (let i = 0; i < codeBlocks.length; i++) {
      result = result.replace(`__CODE_BLOCK_${i}__`, codeBlocks[i])
    }

    // Final cap if still over budget (shouldn't happen often)
    if (result.length > maxChars) {
      result = result.slice(0, maxChars) + '\n[truncated]'
    }

    return this.replaceContent(msg, result)
  }

  private replaceContent(msg: any, newContent: string): any {
    if (typeof msg.content === 'string') {
      return { ...msg, content: newContent }
    }
    if (Array.isArray(msg.content)) {
      const updated = msg.content.map((block: any) => {
        if (block?.type === 'text') {
          return { ...block, text: newContent }
        }
        return block
      })
      return { ...msg, content: updated }
    }
    return msg
  }
}
