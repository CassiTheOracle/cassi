import type { MessageSlot, ThalamusAnnotation, SlotContext } from '../types.js'
import type { SystemLuminanceScore } from '../../workspace/cognitive-signal.js'
import { extractMessageContent } from '../scorer.js'

/**
 * SystemSlot — processes `role: 'system'` messages.
 *
 * System messages are small and critical (pineal, context injections,
 * tool instructions). They are never compressed and always retained
 * during curation.
 */
export class SystemSlot implements MessageSlot {
  readonly type = 'system' as const

  matches(msg: any): boolean {
    return msg?.role === 'system'
  }

  augment(msg: any, ctx: SlotContext): any {
    const content = extractMessageContent(msg)

    // Try to identify the source of the system message
    let source = 'system'
    const lower = content.toLowerCase()
    if (lower.includes('pineal') || lower.includes('identity')) source = 'pineal'
    else if (lower.includes('context') || lower.includes('enrich')) source = 'context-injection'
    else if (lower.includes('tool') || lower.includes('instruction')) source = 'tool-instructions'

    const annotation: ThalamusAnnotation = {
      ts: ctx.timestamp,
      slot: 'system',
      chars: content.length,
      source,
    }

    return { ...msg, _thalamus: annotation }
  }

  compress(msg: any, _annotation: ThalamusAnnotation, _maxChars: number): any {
    // System messages are never compressed
    return msg
  }

  adjustScore(score: SystemLuminanceScore, _annotation: ThalamusAnnotation): SystemLuminanceScore {
    // System messages always pass the ignition threshold
    return {
      ...score,
      composite: 1.0,
      sourceCredibility: 1.0,
    }
  }

  renderPrefix(_annotation: ThalamusAnnotation): string {
    return ''
  }
}
