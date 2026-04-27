import type { InjectionSource } from '../injection-aggregator.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { LaminaField } from './lamina-field.js'

/**
 * LaminaInjectionSource — exposes labeled memory blocks as turn-start context.
 *
 * Priority 10 places this above cortex (8) and mnemic-field (3) — laminae
 * represent intentionally-curated state and should anchor the context.
 *
 * Format:
 *   <laminae>
 *   ## active-task
 *   <content>
 *
 *   ## user-model
 *   <content>
 *   </laminae>
 */
export class LaminaInjectionSource implements InjectionSource {
  readonly name = 'lamina'
  readonly priority = 10
  /** Hard cap on injected payload — defensive. */
  private readonly maxChars: number

  constructor(
    private field: LaminaField,
    private logger: ILogger,
    opts: { maxChars?: number } = {},
  ) {
    this.maxChars = opts.maxChars ?? 6_000
  }

  async getInjection(sessionId: string): Promise<string | null> {
    try {
      const laminae = this.field.list({
        matchScope: { kind: 'session', sessionId },
        limit: 50,
      })
      if (laminae.length === 0) return null

      const eligible = laminae.filter(l => l.content.trim().length > 0)
      if (eligible.length === 0) return null

      // Pinned first, then by recency (already sorted that way by store).
      const lines: string[] = ['<laminae>']
      let total = '<laminae>\n</laminae>'.length

      for (const lamina of eligible) {
        const block = `## ${lamina.label}\n${lamina.content}`
        if (total + block.length + 2 > this.maxChars) break
        lines.push(block)
        lines.push('') // blank line between blocks
        total += block.length + 2
      }
      // Drop trailing blank
      if (lines[lines.length - 1] === '') lines.pop()
      lines.push('</laminae>')
      return lines.join('\n')
    } catch (err) {
      this.logger.debug?.('[lamina-injection] failed', { error: String(err) })
      return null
    }
  }
}
