import type { InjectionSource } from '../injection-aggregator.js'
import type { CorticalField } from './index.js'
import type { ILogger } from '../../../types/interfaces.js'

const SIGNAL_PREFIXES: Record<string, string> = {
  concern: 'Concern',
  anomaly: 'Anomaly',
  decision: 'Decided',
  insight: 'Noticed',
}

/**
 * CortexInjectionSource — provides active working memory signals to the InjectionAggregator.
 *
 * Reads the cortical field for active signals and formats them as natural language
 * working memory. Signals with typed prefixes (concern, anomaly, decision, insight)
 * get labeled; perception/action/request signals pass through as plain content.
 */
export class CortexInjectionSource implements InjectionSource {
  readonly name = 'cortex'
  readonly priority = 8

  constructor(
    private cortex: CorticalField,
    private logger: ILogger,
  ) {}

  async getInjection(sessionId: string): Promise<string | null> {
    try {
      const signals = this.cortex.readActive({ limit: 12, sessionId })
      if (signals.length === 0) return null

      const lines: string[] = []
      for (const sig of signals) {
        const prefix = SIGNAL_PREFIXES[sig.type]
        lines.push(prefix ? `${prefix}: ${sig.content}` : sig.content)
      }

      return `<cortex>\n${lines.join('\n')}\n</cortex>`
    } catch (err) {
      this.logger.debug('[cortex-injection] Failed to read active signals', { error: String(err) })
      return null
    }
  }
}
