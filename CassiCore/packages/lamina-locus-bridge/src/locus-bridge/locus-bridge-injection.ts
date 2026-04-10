import type { ILogger } from '../../../types/interfaces.js'
import type { InjectionSource } from '../injection-aggregator.js'
import type { LocusBridge } from './index.js'
import type { CuratedContext } from './types.js'

export class LocusBridgeInjectionSource implements InjectionSource {
  readonly name = 'locus-bridge'
  readonly priority = 8

  private lastCurated: CuratedContext | null = null
  private lastCuratedAt = 0
  private static readonly CACHE_TTL_MS = 5_000

  constructor(
    private readonly locusBridge: LocusBridge,
    private readonly logger: ILogger,
  ) {}

  async getInjection(sessionId: string, _turnContext?: unknown): Promise<string | null> {
    if (!this.locusBridge.enabled) return null

    try {
      const now = Date.now()
      if (this.lastCurated && now - this.lastCuratedAt < LocusBridgeInjectionSource.CACHE_TTL_MS) {
        return this.formatContext(this.lastCurated)
      }

      const curated = await this.locusBridge.curate()
      this.lastCurated = curated
      this.lastCuratedAt = now

      return this.formatContext(curated)
    } catch (err) {
      this.logger.warn('LocusBridge injection source failed', { error: String(err), sessionId: sessionId.slice(-8) })
      return null
    }
  }

  private formatContext(ctx: CuratedContext): string | null {
    const sections: string[] = []

    if (ctx.focusSummary) {
      sections.push(`### Attentional Focus\n${ctx.focusSummary}`)
    }

    if (ctx.memories.length > 0) {
      const memLines = ctx.memories.map(m =>
        `- [${m.source}] (relevance: ${(m.score * 100).toFixed(0)}%) ${m.content.slice(0, 300)}`
      )
      sections.push(`### Retrieved Memories\n${memLines.join('\n')}`)
    }

    if (ctx.code.length > 0) {
      const codeLines = ctx.code.map(c => {
        const loc = c.lines ? `:${c.lines[0]}-${c.lines[1]}` : ''
        const snippet = c.content.length > 200 ? `${c.content.slice(0, 200)}\n...` : c.content
        return `#### ${c.path}${loc}\n\`\`\`\n${snippet}\n\`\`\``
      })
      sections.push(`### Relevant Code\n${codeLines.join('\n\n')}`)
    }

    if (ctx.signals.length > 0) {
      const sigLines = ctx.signals.map(s =>
        `- [${s.source}] ${s.content.slice(0, 200)}`
      )
      sections.push(`### Intelligence Signals\n${sigLines.join('\n')}`)
    }

    if (sections.length === 0) return null

    return `### Cassi — Locus Context\n\n${sections.join('\n\n')}`
  }
}
