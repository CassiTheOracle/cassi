/**
 * ConstellationInjectionSource — Injects live Corpus tree state into Cassi's context.
 *
 * When a Constellation is running, this source provides a compact summary of the
 * Corpus reasoning tree to the injection aggregator. This means Cassi (the main
 * session) automatically has strategic awareness of what every Helix is doing
 * without having to call `cassi_agent(type: 'constellation', action: 'tree')`.
 *
 * The injection includes:
 *   - Branch count and status summary
 *   - Per-branch: goal, score, step count, dominant pattern, health status
 *   - Active cross-Helix patterns detected by the Corpus
 *   - Recent Corpus interventions
 *
 * Registered as an InjectionSource with the InjectionAggregator at boot time.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { InjectionSource } from '../injection-aggregator.js'
import type { CorpusTreeSnapshot, CrossHelixPattern, CorpusIntervention, BranchAssessment, BranchHealthStatus } from './corpus-types.js'


/** Minimal interface for a running Constellation's live state */
export interface ConstellationLiveState {
  constellationId: string
  goal: string
  getTreeSnapshot(): CorpusTreeSnapshot
  getCrossPatterns(): CrossHelixPattern[]
  getInterventions(): CorpusIntervention[]
  getBranchAssessments(): Array<{ helixId: string; status: BranchHealthStatus; rollingScore: number; dominantPattern: string }>
}


/**
 * Registry of active Constellations.
 * The admin API registers/unregisters Constellations as they start/stop.
 */
export class ConstellationRegistry {
  private active = new Map<string, ConstellationLiveState>()

  register(state: ConstellationLiveState): void {
    this.active.set(state.constellationId, state)
  }

  unregister(constellationId: string): void {
    this.active.delete(constellationId)
  }

  getAll(): ConstellationLiveState[] {
    return [...this.active.values()]
  }

  get size(): number {
    return this.active.size
  }
}


/**
 * InjectionSource that provides live Corpus tree state to the main session.
 */
export class ConstellationInjectionSource implements InjectionSource {
  readonly name = 'constellation'
  readonly priority = 5  // Medium priority — after optimizer/thinker, before session-digest

  constructor(
    private readonly registry: ConstellationRegistry,
    private readonly logger: ILogger,
  ) {}

  async getInjection(_sessionId: string, _turnContext?: unknown): Promise<string | null> {
    const constellations = this.registry.getAll()
    if (constellations.length === 0) return null

    try {
      const sections: string[] = []

      for (const constellation of constellations) {
        const tree = constellation.getTreeSnapshot()
        const patterns = constellation.getCrossPatterns()
        const interventions = constellation.getInterventions()
        const assessments = constellation.getBranchAssessments()

        sections.push(this.formatConstellationSummary(
          constellation.constellationId,
          constellation.goal,
          tree,
          assessments,
          patterns,
          interventions,
        ))
      }

      const content = `### Cassi — Active Constellation${constellations.length > 1 ? 's' : ''}\n\n${sections.join('\n\n')}`

      return content
    } catch (err) {
      this.logger.warn('Failed to build constellation injection', { error: String(err) })
      return null
    }
  }

  private formatConstellationSummary(
    id: string,
    goal: string,
    tree: CorpusTreeSnapshot,
    assessments: Array<{ helixId: string; status: BranchHealthStatus; rollingScore: number; dominantPattern: string }>,
    patterns: CrossHelixPattern[],
    interventions: CorpusIntervention[],
  ): string {
    const lines: string[] = []

    lines.push(`**Constellation** \`${id}\`: ${goal}`)
    lines.push(`Branches: ${tree.activeBranches} active / ${tree.branches.length} total, ${tree.totalSteps} steps`)

    // Per-branch summary (compact)
    if (assessments.length > 0) {
      for (const a of assessments) {
        const score = a.rollingScore.toFixed(2)
        const statusIcon = a.status === 'productive' ? '●' :
          a.status === 'struggling' ? '▼' :
          a.status === 'drifting' ? '◇' :
          a.status === 'stuck' ? '■' : '○'
        const branch = tree.branches.find(b => b.helixId === a.helixId)
        const goalSnippet = branch?.goal?.slice(0, 60) ?? '?'
        lines.push(`  ${statusIcon} \`${a.helixId}\` [${score}] ${a.status} — ${goalSnippet} (${branch?.stepCount ?? 0} steps, ${a.dominantPattern})`)
      }
    }

    // Cross-Helix patterns (only active/unresolved)
    const activePatterns = patterns.filter(p => !p.actedUpon)
    if (activePatterns.length > 0) {
      lines.push(`Cross-patterns: ${activePatterns.map(p => `${p.severity.toUpperCase()} ${p.type} [${p.helixIds.join(',')}]`).join('; ')}`)
    }

    // Recent interventions (last 3)
    const recent = interventions.slice(-3)
    if (recent.length > 0) {
      lines.push(`Recent interventions: ${recent.map(i => `→${i.targetHelixId} ${i.type}[${i.urgency}]`).join(', ')}`)
    }

    return lines.join('\n')
  }
}


/**
 * Create and return the constellation injection source + registry.
 * Call this during intelligence layer boot.
 */
export function createConstellationInjection(logger: ILogger): {
  source: ConstellationInjectionSource
  registry: ConstellationRegistry
} {
  const registry = new ConstellationRegistry()
  const source = new ConstellationInjectionSource(registry, logger)
  return { source, registry }
}
