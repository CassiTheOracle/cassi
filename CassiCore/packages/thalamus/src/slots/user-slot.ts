import type { MessageSlot, ThalamusAnnotation, SlotContext } from '../types.js'
import type { SystemLuminanceScore } from '../../workspace/cognitive-signal.js'
import { extractMessageContent } from '../scorer.js'
import { hasQuestionResult } from '../../../pipeline/turn/overflow.js'

/**
 * UserSlot — processes `role: 'user'` messages that carry user intent.
 *
 * Includes plain user prompts AND `AskUserQuestion` tool answers, both of
 * which are semantically user input. Excludes ordinary tool_result messages
 * (Bash output, file reads, etc.) which are routed to ToolResultSlot.
 *
 * User messages carry instructions and are the highest-credibility source
 * in the conversation. They get light compression (only very long pastes),
 * high credibility floors, and an urgency floor to prevent dropping active
 * instructions.
 */
export class UserSlot implements MessageSlot {
  readonly type = 'user' as const

  matches(msg: any, ctx?: SlotContext): boolean {
    if (msg?.role !== 'user') return false
    if (hasQuestionResult(msg, { toolUseMap: ctx?.toolUseMap })) return true
    if (Array.isArray(msg.content) && msg.content.some((c: any) => c?.type === 'tool_result')) {
      return false
    }
    return true
  }

  augment(msg: any, ctx: SlotContext): any {
    const content = extractMessageContent(msg)
    const annotation: ThalamusAnnotation = {
      ts: ctx.timestamp,
      slot: 'user',
      chars: content.length,
    }

    return { ...msg, _thalamus: annotation }
  }

  compress(msg: any, _annotation: ThalamusAnnotation, maxChars: number): any {
    if (typeof msg.content === 'string' && msg.content.length > maxChars) {
      const head = msg.content.slice(0, Math.floor(maxChars * 0.8))
      const omitted = msg.content.length - head.length
      return {
        ...msg,
        content: `${head}\n[${omitted} chars omitted from user message]`,
      }
    }
    return msg
  }

  adjustScore(score: SystemLuminanceScore, _annotation: ThalamusAnnotation): SystemLuminanceScore {
    const adjustedCred = Math.max(score.sourceCredibility, 0.90)
    const adjustedUrg = Math.max(score.urgency, 0.15)
    const resonance: number = (score as any).cognitiveResonance ?? 0
    const composite =
      0.12 * score.novelty +
      0.13 * adjustedUrg +
      0.40 * score.relevance +
      0.15 * adjustedCred +
      0.20 * resonance
    // User messages carry instructions and answers — they must survive
    // phase transitions where focus/cortex relevance gets suppressed.
    // Floor composite above the default ignition threshold (0.20) so
    // user intent is never lost during topic shifts.
    return {
      ...score,
      sourceCredibility: adjustedCred,
      urgency: adjustedUrg,
      composite: Math.max(score.composite, composite, 0.25),
    }
  }

  renderPrefix(annotation: ThalamusAnnotation): string {
    const time = annotation.ts ? new Date(annotation.ts).toISOString().slice(11, 19) : ''
    return time ? `[${time}]` : ''
  }
}
