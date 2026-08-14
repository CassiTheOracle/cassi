/**
 * Constellation Guidance Provider — Bridges the Corpus and collect_thoughts.
 *
 * Created by the Constellation pipeline and registered in the global
 * ConstellationGuidanceRegistry keyed by Helix session ID. The collect_thoughts
 * tool looks up the provider for the current session at execution time.
 *
 * Sources of guidance:
 * 1. Elevated patterns — successful approaches from peer branches
 * 2. Cross-branch directives — pending guidance from the Corpus
 * 3. Goal alignment — whether the current thought is on-track for the branch goal
 */

import type { ConstellationGuidanceProvider } from './vendor/tools/implementations/collect-thoughts.js'
import type { CorpusTree } from './corpus-tree.js'
import type { ILogger } from './vendor/types/interfaces.js'


/**
 * Session-scoped registry for Constellation guidance providers.
 *
 * WHY: collect_thoughts is a globally-registered tool with deps captured at
 * boot time. But each Helix branch in a Constellation needs its own guidance
 * provider (scoped to its goal, corpus tree, and surfaced-pattern state).
 * This registry is the bridge: the Constellation pipeline registers a provider
 * per branch (keyed by session ID), and collect_thoughts looks it up at
 * execution time via context.sessionId.
 */
export class ConstellationGuidanceRegistry {
  private providers = new Map<string, ConstellationGuidanceProvider>()

  /** Register a guidance provider for a specific Helix session. */
  register(sessionId: string, provider: ConstellationGuidanceProvider): void {
    this.providers.set(sessionId, provider)
  }

  /** Unregister the guidance provider when a Helix session completes. */
  unregister(sessionId: string): void {
    this.providers.delete(sessionId)
  }

  /** Look up the guidance provider for a session. Returns undefined if
   *  the session is not running under a Constellation. */
  get(sessionId: string): ConstellationGuidanceProvider | undefined {
    return this.providers.get(sessionId)
  }

  /** Number of active registrations (for diagnostics). */
  get size(): number {
    return this.providers.size
  }
}

/**
 * Options for constructing a guidance provider.
 */
export interface ConstellationGuidanceProviderOpts {
  corpusTree: CorpusTree
  helixId: string
  branchGoal: string
  logger: ILogger
}

/**
 * Create a ConstellationGuidanceProvider that queries the Corpus tree for
 * strategic context relevant to a specific Helix branch.
 *
 * WHY: This is a factory function (not a class) because each Helix branch
 * needs its own provider with its own helixId and goal context. The factory
 * captures these in the closure.
 */
export function createConstellationGuidanceProvider(
  opts: ConstellationGuidanceProviderOpts,
): ConstellationGuidanceProvider {
  const { corpusTree, helixId, branchGoal, logger } = opts
  const log = logger.child('constellation-guidance')

  // Track which patterns we've already surfaced to avoid repetition
  const surfacedPatternIds = new Set<string>()

  // Rate-limit: only provide guidance every N steps to avoid noise
  let lastGuidanceStep = 0
  const MIN_STEP_INTERVAL = 2

  return {
    getGuidanceForThought(thought: string, step: number, _sessionId: string): string | null {
      // Rate limit — don't inject guidance on every step
      if (step - lastGuidanceStep < MIN_STEP_INTERVAL && step > 1) {
        return null
      }

      const sections: string[] = []

      // 1. Elevated patterns — filter to those relevant to this thought
      try {
        const patterns = corpusTree.getElevatedPatterns()
        const thoughtLower = thought.toLowerCase()
        const goalKeywords = branchGoal.toLowerCase().split(/\s+/).filter(w => w.length > 3)

        const relevantPatterns = patterns.filter(p => {
          if (surfacedPatternIds.has(p.id)) return false
          const patternText = `${p.applicableContext} ${p.approach} ${p.description}`.toLowerCase()
          return goalKeywords.some(kw => patternText.includes(kw)) ||
            thoughtLower.split(/\s+/).filter(w => w.length > 3).some(w => patternText.includes(w))
        })

        if (relevantPatterns.length > 0) {
          // Only surface the top 1-2 most relevant patterns
          const top = relevantPatterns.slice(0, 2)
          const patternLines = top.map(p => {
            surfacedPatternIds.add(p.id)
            return `- [${p.approach}] (score: ${p.achievedScore.toFixed(2)}): ${p.description.slice(0, 150)}`
          })
          sections.push(`Constellation knowledge (successful peer approaches):\n${patternLines.join('\n')}`)
        }
      } catch (err) {
        log.warn('Failed to query elevated patterns', { error: String(err) })
      }

      // 2. Cross-branch awareness — summary of what other branches are doing
      try {
        const snapshot = corpusTree.getSnapshot()
        const activeBranches = snapshot.branches.filter(b =>
          b.helixId !== helixId && b.status === 'active'
        )

        if (activeBranches.length > 0 && step <= 3) {
          // Only include on early steps to set the stage
          const branchSummary = activeBranches
            .slice(0, 3)
            .map(b => `- ${b.goal.slice(0, 80)}`)
            .join('\n')
          sections.push(`Other active branches (avoid overlap):\n${branchSummary}`)
        }
      } catch (err) {
        log.warn('Failed to get cross-branch snapshot', { error: String(err) })
      }

      if (sections.length === 0) return null

      lastGuidanceStep = step
      return sections.join('\n\n')
    },
  }
}
