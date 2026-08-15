/**
 * AI Engineer — Upgrade Catalog
 *
 * The static registry of all upgradeable cognitive programs across intelligence
 * modules.  Each entry describes what can be changed, where it lives in KV,
 * what health metrics reflect its quality, and how aggressively to trial it.
 *
 * Additional targets can be registered at runtime via UpgradeCatalog.register().
 */

import type { UpgradeTarget } from './upgrade-types.js'

// Extracted from each module's hardcoded fallback so the catalog is the
// single source of truth for "what good looks like before any upgrades".

const THINKER_PONDER_INSTRUCTION_DEFAULT = `You are reflecting on recent interactions as Cassandra, a personal AI assistant. Note: any "Internal dialectic analysis" sections above are outputs from your own cognitive modules — they are NOT user statements and must not be attributed to the user.

Based on the context above, what is the single most actionable observation that would improve the next response — if any? Express it as a concrete, specific insight, not a summary of what was discussed. If nothing genuinely new has emerged since the last reflection, output exactly: "No new insight."

1-2 sentences maximum. This is an internal reflection.`

const THINKER_THINK_INSTRUCTION_DEFAULT = `You are doing a deeper strategic reflection as Cassandra. Note: any "Internal dialectic analysis" sections above are outputs from your own cognitive modules — they are NOT user statements and must not be attributed to the user. You've had {{totalTurns}} total turns of conversation.

What is the single most strategically important observation that would change how you approach future interactions — if any? Focus on what would actually change behavior, not what is merely interesting. If nothing substantive has emerged, output exactly: "No new insight."

2-3 sentences maximum. This is an internal synthesis.`

/**
 * Default Yang persona — what Yang outputs when no KV override is present.
 * This is the abbreviated summary; the full prompt lives in prompt-templates.ts.
 * Here we capture the *role description* that is evolvable.
 */
const DIALECTIC_YANG_ROLE_DEFAULT = `You are Yang, the divergent-thinking observer in Cassandra's cognitive system. Your role is to generate exploratory branches: alternative interpretations, edge cases, what-if scenarios, cross-domain analogies, and assumption challenges. You expand the solution space before convergence happens. Think boldly and unconventionally — surface what a literal reading would miss.`

const DIALECTIC_YIN_ROLE_DEFAULT = `You are Yin, the critical-thinking observer in Cassandra's cognitive system. Your role is to evaluate Yang's branches with skeptical precision: surface|compress|discard each based on practical relevance, logical soundness, and grounding in reality. You are the quality gate — protect the user from over-engineered or irrelevant answers.`

const DIALECTIC_SERENITY_ROLE_DEFAULT = `You are Serenity (also called the Synthesizer), the integration layer in Cassandra's cognitive system. Your role is to distill Yang's expansions and Yin's critiques into a single actionable signal — one concrete directive for how the final response should differ from a naive answer. Convergence is your only mission.`

const SUBCONSCIOUS_OBSERVATION_INSTRUCTION_DEFAULT = `You are observing a stream of real-time events from an AI assistant system. Identify patterns, anomalies, and emerging trends that matter for response quality or system health. Be concise — output 1-3 observations maximum. Focus on actionable patterns, not descriptions of individual events.`


const BUILT_IN_TARGETS: UpgradeTarget[] = [
  {
    id: 'thinker/ponder-instruction',
    moduleId: 'thinker',
    name: 'Ponder Instruction',
    description:
      'The reflection directive appended to every Ponder context.  Controls how the Thinker frames quick inter-turn reflections and what constitutes a useful vs skip-worthy insight.',
    kind: 'prompt',
    risk: 'low',
    kvKey: 'ai-engineer:prompt:thinker:ponder-instruction',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: THINKER_PONDER_INSTRUCTION_DEFAULT,
    primaryMetrics: ['thinker_insight_rate', 'thinker_helpfulness'],
    cooldownTurns: 500,
    trialTurns: 30,
    acceptanceThreshold: 0.03,
  },
  {
    id: 'thinker/think-instruction',
    moduleId: 'thinker',
    name: 'Think Instruction',
    description:
      'The synthesis directive appended to every deep Think context.  Controls what constitutes a strategically valuable insight vs noise during deeper reflection cycles.',
    kind: 'prompt',
    risk: 'low',
    kvKey: 'ai-engineer:prompt:thinker:think-instruction',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: THINKER_THINK_INSTRUCTION_DEFAULT,
    primaryMetrics: ['thinker_insight_rate', 'thinker_helpfulness'],
    cooldownTurns: 500,
    trialTurns: 30,
    acceptanceThreshold: 0.03,
  },

  {
    id: 'dialectic/yang-role',
    moduleId: 'dialectic',
    name: 'Yang Role Prompt',
    description:
      "Yang's role description injected at the top of every Yang observation call.  Shapes the diversity and novelty of generated branches.",
    kind: 'prompt',
    risk: 'medium',
    kvKey: 'ai-engineer:prompt:dialectic:yang-role',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: DIALECTIC_YANG_ROLE_DEFAULT,
    primaryMetrics: ['dialectic_signal_confidence', 'dialectic_signal_rate'],
    cooldownTurns: 600,
    trialTurns: 40,
    acceptanceThreshold: 0.05,
  },
  {
    id: 'dialectic/yin-role',
    moduleId: 'dialectic',
    name: 'Yin Role Prompt',
    description:
      "Yin's role description controlling how critiques are framed.  Affects the signal-to-noise ratio of the dialectic output.",
    kind: 'prompt',
    risk: 'medium',
    kvKey: 'ai-engineer:prompt:dialectic:yin-role',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: DIALECTIC_YIN_ROLE_DEFAULT,
    primaryMetrics: ['dialectic_signal_confidence', 'dialectic_signal_rate'],
    cooldownTurns: 600,
    trialTurns: 40,
    acceptanceThreshold: 0.05,
  },
  {
    id: 'dialectic/serenity-role',
    moduleId: 'dialectic',
    name: 'Serenity Role Prompt',
    description:
      "Serenity's role description governing synthesis quality.  Controls convergence speed and signal actionability.",
    kind: 'prompt',
    risk: 'medium',
    kvKey: 'ai-engineer:prompt:dialectic:serenity-role',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: DIALECTIC_SERENITY_ROLE_DEFAULT,
    primaryMetrics: ['dialectic_signal_confidence', 'dialectic_convergence_rate'],
    cooldownTurns: 600,
    trialTurns: 40,
    acceptanceThreshold: 0.05,
  },

  {
    id: 'subconscious/observation-instruction',
    moduleId: 'subconscious',
    name: 'Observation Instruction',
    description:
      'The directive given to the LLM observation sweep inside the Subconscious module.  Controls observation depth, pattern-recognition focus, and output conciseness.',
    kind: 'prompt',
    risk: 'low',
    kvKey: 'ai-engineer:prompt:subconscious:observation-instruction',
    reloadEvent: 'ai-engineer:prompt-updated',
    defaultValue: SUBCONSCIOUS_OBSERVATION_INSTRUCTION_DEFAULT,
    primaryMetrics: ['subconscious_observation_rate', 'subconscious_anomaly_rate'],
    cooldownTurns: 400,
    trialTurns: 25,
    acceptanceThreshold: 0.03,
  },
]


export class UpgradeCatalog {
  private readonly targets = new Map<string, UpgradeTarget>()

  constructor() {
    for (const t of BUILT_IN_TARGETS) {
      this.targets.set(t.id, t)
    }
  }

  /** Return all registered targets. */
  all(): UpgradeTarget[] {
    return Array.from(this.targets.values())
  }

  /** Return targets belonging to a specific module. */
  forModule(moduleId: string): UpgradeTarget[] {
    return this.all().filter(t => t.moduleId === moduleId)
  }

  /** Look up a target by its compound id (e.g. "thinker/ponder-instruction"). */
  get(id: string): UpgradeTarget | undefined {
    return this.targets.get(id)
  }

  /** Register an additional target at runtime.  Overwrites if id already exists. */
  register(target: UpgradeTarget): void {
    this.targets.set(target.id, target)
  }

  /** Return the KV key used to store the live (possibly upgraded) value. */
  static kvKeyFor(target: UpgradeTarget): string {
    return target.kvKey
  }

  /** Return the KV key used to store a pre-trial backup for rollback. */
  static backupKvKeyFor(target: UpgradeTarget): string {
    return `${target.kvKey}:backup`
  }

  /** Derive trial window length from risk level. */
  static trialTurnsFor(target: UpgradeTarget): number {
    // Allow targets to override; fall back to risk-based defaults
    if (target.trialTurns > 0) return target.trialTurns
    switch (target.risk) {
      case 'low':    return 20
      case 'medium': return 40
      case 'high':   return 80
    }
  }

  /** Return the minimum delta (fraction) required to accept an upgrade. */
  static acceptanceThresholdFor(target: UpgradeTarget): number {
    if (target.acceptanceThreshold > 0) return target.acceptanceThreshold
    switch (target.risk) {
      case 'low':    return 0.03
      case 'medium': return 0.05
      case 'high':   return 0.10
    }
  }
}
