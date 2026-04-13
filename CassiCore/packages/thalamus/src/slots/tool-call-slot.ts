import type { MessageSlot, ThalamusAnnotation, SlotContext } from '../types.js'
import type { SystemLuminanceScore } from '../../workspace/cognitive-signal.js'
import { classifyTool, extractToolUses } from '../classifier.js'
import { extractMessageContent } from '../scorer.js'

/**
 * ToolCallSlot — processes `role: 'assistant'` messages containing tool_use blocks.
 *
 * Tool call messages are structural — they record what the assistant invoked
 * and with what parameters. They're worthless without their paired tool_result,
 * so scoring is linked to the result pair. Compression targets bulky input
 * params while preserving tool names and key file paths.
 */
export class ToolCallSlot implements MessageSlot {
  readonly type = 'tool_call' as const

  matches(msg: any): boolean {
    return (
      msg?.role === 'assistant' &&
      Array.isArray(msg.content) &&
      msg.content.some((c: any) => c?.type === 'tool_use')
    )
  }

  augment(msg: any, ctx: SlotContext): any {
    const content = extractMessageContent(msg)
    const toolUses = extractToolUses(msg)

    // Classify the first tool (for the primary annotation) — most messages have one
    const primaryTool = toolUses[0]
    const toolName = primaryTool?.name ?? ''
    const toolClass = toolName ? classifyTool(toolName) : 'tool'

    // Register tool uses in the context map so ToolResultSlot can reference them
    for (const tu of toolUses) {
      ctx.toolUseMap.set(tu.id, tu.name)
    }

    const annotation: ThalamusAnnotation = {
      ts: ctx.timestamp,
      slot: 'tool_call',
      chars: content.length,
      tool: {
        name: toolName,
        class: toolClass,
        durationMs: 0,
        outputBytes: 0,
        isError: false,
      },
    }

    return { ...msg, _thalamus: annotation }
  }

  compress(msg: any, _annotation: ThalamusAnnotation, maxChars: number): any {
    if (!Array.isArray(msg.content)) return msg

    const compressed = msg.content.map((block: any) => {
      if (block?.type !== 'tool_use') return block

      const input = block.input
      if (!input || typeof input !== 'object') return block

      const inputStr = JSON.stringify(input)
      if (inputStr.length <= maxChars) return block

      // Preserve key paths and truncate bulky params
      const summary: Record<string, unknown> = {}
      for (const [key, val] of Object.entries(input)) {
        if (typeof val === 'string' && val.length > 200) {
          summary[key] = val.slice(0, 150) + `[…${val.length - 150} chars]`
        } else {
          summary[key] = val
        }
      }

      return { ...block, input: summary }
    })

    return { ...msg, content: compressed }
  }

  adjustScore(score: SystemLuminanceScore, _annotation: ThalamusAnnotation): SystemLuminanceScore {
    // Tool calls inherit their result's score — no independent adjustment
    // except a slight credibility boost (they represent concrete action)
    return {
      ...score,
      sourceCredibility: Math.max(score.sourceCredibility, 0.65),
    }
  }

  renderPrefix(_annotation: ThalamusAnnotation): string {
    // Tool calls don't get a prefix — the tool_use structure is already descriptive
    return ''
  }
}
