/**
 * AI Engineer — Main Module
 *
 * The AI Engineer is a proactive self-upgrading agent that continuously
 * improves the cognitive programs (prompts, behavioral configs) of all
 * other intelligence modules.
 *
 * Architecture:
 *   ┌──────────────────────────────────────────────────────────────────────┐
 *   │  EventBus signals → PerformanceMonitor (health scores per module)   │
 *   │                                                                      │
 *   │  Every ENGINEER_CYCLE_TURNS:                                         │
 *   │    UpgradePipeline.tick() →                                          │
 *   │      Select weakest eligible target                                  │
 *   │      → PromptEvolver (critique → improve → validate)                 │
 *   │      → Apply proposal to KV + emit reload event                      │
 *   │      → Monitor for TRIAL_TURNS turns                                 │
 *   │      → Compare metrics → accept or revert                            │
 *   └──────────────────────────────────────────────────────────────────────┘
 *
 * Distinct from:
 *   AI Scientist  — tunes numerical parameters via A/B experiments
 *   Self-Healer   — reactively repairs crashed or broken code
 *   Adaptive Behavior — selects between strategies via epsilon-greedy bandit
 *
 * The AI Engineer uniquely owns: prompt quality, behavioral config quality,
 * and the evolution of "what each module thinks/says" over time.
 */

import { PerformanceMonitor } from './performance-monitor.js'
import { UpgradeCatalog } from './upgrade-catalog.js'
import { UpgradePipeline } from './upgrade-pipeline.js'

import type { EngineerSummary, UpgradeTrial } from './upgrade-types.js'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus, IntelligenceModule } from '@cassicore/foundation'
import type { GlobalBlackboardRegistry } from '@cassicore/flux-team'


export interface AIEngineerConfig {
  enabled: boolean
  /**
   * How many turns between upgrade cycle checks.
   * The pipeline may still be in a trial when this fires; in that case the
   * tick() call simply advances the trial counter and returns.
   */
  engineerCycleTurns: number
  /** LLM model to use for evolution steps. */
  evolverModel?: string
}

const DEFAULT_CONFIG: AIEngineerConfig = {
  enabled: true,
  engineerCycleTurns: 100,
}


export class AIEngineer implements IntelligenceModule {
  readonly name = 'ai-engineer'
  /** Run after AI Scientist (priority 20) but before adaptive-behavior (priority 45). */
  readonly priority = 25

  private logger: ILogger
  private config: AIEngineerConfig

  private eventBus?: IEventBus
  private memory?: IMemory
  private globalBlackboardRegistry?: GlobalBlackboardRegistry

  private readonly catalog: UpgradeCatalog
  private readonly monitor: PerformanceMonitor
  private readonly pipeline: UpgradePipeline

  // Self-improvement loop integration
  private improvementOrchestrator?: any

  private totalTurns = 0
  private turnsSinceCycle = 0
  private lastConcludedProposalId?: string


  constructor(logger: ILogger, config?: Partial<AIEngineerConfig>) {
    this.logger = logger.child?.('ai-engineer') ?? logger
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.catalog = new UpgradeCatalog()
    this.monitor = new PerformanceMonitor()
    this.pipeline = new UpgradePipeline(this.catalog, this.monitor, this.logger)
  }

  /** Wire the improvement orchestrator for verification-gated upgrades */
  setImprovementOrchestrator(orchestrator: any): void {
    this.improvementOrchestrator = orchestrator
  }

  start(): void {
    if (!this.config.enabled) return
    this.logger.info('AI Engineer: started', {
      engineerCycleTurns: this.config.engineerCycleTurns,
      targets: this.catalog.all().length,
    })
  }

  stop(): void {
    if (this.memory) {
      // Best-effort: abort active trial and persist state
      this.pipeline.abortActiveTrial(this.memory).catch(() => {})
      this.pipeline.persistState(this.memory).catch(() => {})
    }
    this.logger.info('AI Engineer: stopped')
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
    this.wireEvents(bus)
  }

  setMemory(mem: IMemory): void {
    this.memory = mem
    // Restore persisted state (async — errors are non-fatal)
    this.pipeline.restoreState(mem).catch(err => {
      this.logger.debug('AI Engineer: state restore error', { error: String(err) })
    })
  }

  setGlobalBlackboardRegistry(registry: GlobalBlackboardRegistry): void {
    this.globalBlackboardRegistry = registry
  }

  /**
   * Post an entry to a named global board. Fire-and-forget — never throws.
   */
  private postToBoard(
    boardName: string,
    channel: 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests' | 'bugs',
    content: string,
    opts?: { author?: string; tags?: string[]; priority?: number },
  ): void {
    try {
      const board = this.globalBlackboardRegistry?.getOrCreate(boardName, { persist: true })
      board?.post(channel, {
        content,
        author: opts?.author ?? this.name,
        tags: opts?.tags ?? [],
        priority: opts?.priority ?? 0,
      })
    } catch (err) {
      this.logger.debug('Blackboard post failed (non-fatal)', { error: String(err), boardName, channel })
    }
  }


  async onTurnStart(_ctx: Record<string, unknown>): Promise<void> {
    // No per-turn start actions needed
  }

  async onTurnEnd(_ctx: Record<string, unknown>): Promise<void> {
    if (!this.config.enabled) return
    this.totalTurns++
    this.turnsSinceCycle++

    // Tick the pipeline on every turn (it manages its own internal counters)
    if (this.memory && this.eventBus && this.turnsSinceCycle >= this.config.engineerCycleTurns) {
      this.turnsSinceCycle = 0
      await this.runCycle()
    } else if (this.memory && this.eventBus && this.pipeline.getActiveTrial()) {
      // Always advance an active trial even between cycles
      await this.pipeline.tick(this.memory, this.eventBus, this.totalTurns)
      await this.pipeline.persistState(this.memory)
    }
  }

  async injectContext(
    _ctx: Record<string, unknown>,
  ): Promise<string | null> {
    // AI Engineer does not inject into conversation context
    return null
  }


  private async runCycle(): Promise<void> {
    if (!this.memory || !this.eventBus) return

    this.logger.debug('AI Engineer: running upgrade cycle', {
      totalTurns: this.totalTurns,
      phase: this.pipeline.getPhase(),
    })

    try {
      await this.pipeline.tick(this.memory, this.eventBus, this.totalTurns)
      await this.pipeline.persistState(this.memory)
      this.maybeProposeCompletedUpgrade()
    } catch (err) {
      this.logger.error('AI Engineer: cycle error', { error: String(err) })
    }
  }


  private wireEvents(bus: IEventBus): void {

    bus.on('thinker:feedback', (event: Record<string, unknown>) => {
      try {
        const helpful = event['helpful'] as boolean | undefined
        if (helpful !== undefined) {
          this.monitor.record('thinker', 'thinker_helpfulness', helpful ? 1 : 0, 'thinker:feedback')
        }
      } catch {}
    })

    bus.on('thinker:insight-applied', (_event: Record<string, unknown>) => {
      this.monitor.record('thinker', 'thinker_insight_rate', 1, 'thinker:insight-applied')
    })

    bus.on('thinker:ponder-skipped', (_event: Record<string, unknown>) => {
      // A skipped ponder means the instruction produced "No new insight" — lower rate
      this.monitor.record('thinker', 'thinker_insight_rate', 0, 'thinker:ponder-skipped')
    })


    bus.on('dialectic:signal', (event: Record<string, unknown>) => {
      try {
        const confidence = event['confidence'] as number | undefined
        if (typeof confidence === 'number') {
          this.monitor.record('dialectic', 'dialectic_signal_confidence', confidence, 'dialectic:signal')
        }
        this.monitor.record('dialectic', 'dialectic_signal_rate', 1, 'dialectic:signal')
      } catch {}
    })

    bus.on('dialectic:no-signal', (_event: Record<string, unknown>) => {
      this.monitor.record('dialectic', 'dialectic_signal_rate', 0, 'dialectic:no-signal')
    })

    bus.on('dialectic:convergence', (event: Record<string, unknown>) => {
      try {
        const converged = (event['converged'] as boolean | undefined) ?? true
        this.monitor.record(
          'dialectic',
          'dialectic_convergence_rate',
          converged ? 1 : 0,
          'dialectic:convergence',
        )
      } catch {}
    })


    bus.on('consciousness:observation', (_event: Record<string, unknown>) => {
      this.monitor.record('subconscious', 'subconscious_observation_rate', 1, 'consciousness:observation')
    })

    bus.on('subconscious:anomaly', (_event: Record<string, unknown>) => {
      this.monitor.record('subconscious', 'subconscious_anomaly_rate', 1, 'subconscious:anomaly')
    })


    bus.on('ai-engineer:upgrade-proposed', (event: Record<string, unknown>) => {
      // Post proposal to blackboard
      this.postToBoard('system:ai-engineer', 'findings', JSON.stringify({
        type: 'upgrade-proposal',
        trialId: event['trialId'],
        targetId: event['targetId'],
        moduleId: event['moduleId'],
        rationale: event['rationale'],
        validationScore: event['validationScore'],
      }), { tags: ['upgrade', 'proposal'] })
    })

    bus.on('ai-engineer:upgrade-applied', (event: Record<string, unknown>) => {
      this.logger.info('AI Engineer: upgrade permanently applied', {
        targetId: event['targetId'],
        moduleId: event['moduleId'],
        reason: event['reason'],
      })
      // Archive the successful upgrade in memory for longitudinal tracking
      if (this.memory) {
        this.memory.store({
          type: 'insight',
          content: `AI Engineer: upgrade applied to ${event['targetId']}\n${event['reason']}`,
          metadata: {
            tags: ['ai-engineer', 'upgrade', String(event['moduleId'] ?? '')],
            targetId: event['targetId'],
            deltaPercent: event['deltaPercent'],
          },
        }).catch(() => {})
      }

      this.maybeProposeCompletedUpgrade()
    })

    // Integration 2: Feed genome execution results into the performance monitor
    // so the AIEngineer can evolve genome directives based on observed quality.

    bus.on('flux:node:completed', (event: Record<string, unknown>) => {
      try {
        const genomeId = event['genomeId'] as string | undefined
        const success = event['success'] as boolean | undefined
        const confidence = event['confidence'] as number | undefined

        if (!genomeId) return

        // Module ID is the genome family (e.g., 'flux-genome')
        const moduleId = `flux-genome`

        // Record binary success rate per genome
        if (success !== undefined) {
          this.monitor.record(
            moduleId,
            `flux_node_success_rate:${genomeId}`,
            success ? 1 : 0,
            'flux:node:completed',
          )
          // Also record an aggregate across all genomes
          this.monitor.record(
            moduleId,
            'flux_node_success_rate',
            success ? 1 : 0,
            'flux:node:completed',
          )
        }

        // Record Lumen confidence score
        if (typeof confidence === 'number') {
          this.monitor.record(
            moduleId,
            `flux_node_confidence:${genomeId}`,
            confidence,
            'flux:node:completed',
          )
          this.monitor.record(
            moduleId,
            'flux_node_confidence',
            confidence,
            'flux:node:completed',
          )
        }

        // Record token efficiency (lower is better, normalise to 0–1 inverse)
        const tokensUsed = event['tokensUsed'] as number | undefined
        if (typeof tokensUsed === 'number' && tokensUsed > 0) {
          // Normalise: <5k tokens = 1.0, >100k tokens = 0.0
          const efficiency = Math.max(0, Math.min(1, 1 - (tokensUsed - 5000) / 95000))
          this.monitor.record(
            moduleId,
            `flux_token_efficiency:${genomeId}`,
            efficiency,
            'flux:node:completed',
          )
        }
      } catch {
        // Best effort — don't let metric recording break the event flow
      }
    })
  }

  private maybeProposeCompletedUpgrade(): void {
    const recent = this.pipeline.stats().recentTrials[0]
    if (!recent) return
    if (recent.id === this.lastConcludedProposalId) return

    // Post upgrade outcome to blackboard
    if (recent.outcome === 'accepted' || recent.outcome === 'rejected') {
      this.postToBoard('system:ai-engineer', 'decisions', JSON.stringify({
        type: 'upgrade-outcome',
        targetId: recent.targetId,
        moduleId: recent.moduleId,
        outcome: recent.outcome,
        outcomeReason: recent.outcomeReason,
        deltaPercent: recent.deltaPercent,
      }), { tags: ['upgrade', recent.outcome], priority: recent.outcome === 'accepted' ? 1 : 0 })
    }

    if (!this.improvementOrchestrator) return
    if (recent.outcome !== 'accepted') return

    const quality = this.computeTrialConfidence(recent)
    if (quality < 0.65) return

    this.lastConcludedProposalId = recent.id

    try {
      this.improvementOrchestrator.propose({
        id: `eng-${recent.id}`,
        trigger: 'improvement',
        source: 'AIEngineer',
        proposalClass: 'heuristic',
        hypothesis: `Accepted AI Engineer upgrade for ${recent.targetId} improved monitored signals`,
        adaptation: 'parameter_tune',
        config: {
          targetId: recent.targetId,
          moduleId: recent.moduleId,
          trialId: recent.id,
          outcome: recent.outcome,
          outcomeReason: recent.outcomeReason,
        },
        dedupeKey: `ai-engineer:${recent.targetId}:${recent.id}`,
        riskLevel: 'moderate',
        confidence: quality,
        evidence: {
          targetMetric: this.primaryMetric(recent),
          observedDelta: this.primaryDelta(recent),
          dataPoints: Object.keys(recent.deltaPercent ?? {}).length,
          notes: [recent.outcomeReason ?? 'accepted trial'],
        },
        verificationScenarios: ['multi-turn-context'],
        timestamp: recent.concludedAt ?? Date.now(),
      })
    } catch {
      // best effort
    }
  }

  private primaryMetric(trial: UpgradeTrial): string | undefined {
    const entries = Object.entries(trial.deltaPercent ?? {})
    if (entries.length === 0) return undefined
    entries.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    return entries[0]?.[0]
  }

  private primaryDelta(trial: UpgradeTrial): number | undefined {
    const metric = this.primaryMetric(trial)
    if (!metric) return undefined
    return trial.deltaPercent?.[metric]
  }

  private computeTrialConfidence(trial: UpgradeTrial): number {
    const deltas = Object.values(trial.deltaPercent ?? {})
    if (deltas.length === 0) return 0

    const positive = deltas.filter(delta => delta > 0).length
    const strongest = Math.max(...deltas.map(delta => Math.abs(delta)))
    const ratio = positive / deltas.length
    const strength = Math.min(1, strongest / 25)
    return Number(Math.min(0.92, 0.45 + ratio * 0.25 + strength * 0.22).toFixed(2))
  }


  /**
   * Return a full summary for the admin API and Observatory dashboard.
   */
  getEngineerSummary(): EngineerSummary {
    const { totalProposals, totalAccepted, totalRejected, recentTrials } = this.pipeline.stats()
    const activeTrial = this.pipeline.getActiveTrial() ?? null
    const now = Date.now()

    return {
      phase: this.pipeline.getPhase(),
      totalProposals,
      totalAccepted,
      totalRejected,
      activeTrial,
      recentUpgrades: recentTrials
        .filter(t => t.outcome === 'accepted')
        .slice(0, 5)
        .map(t => ({
          targetId: t.targetId,
          moduleId: t.moduleId,
          concludedAt: t.concludedAt ?? 0,
          outcome: t.outcome!,
          deltaPercent: t.deltaPercent ?? {},
        })),
      moduleHealth: this.monitor.allHealth(),
      catalog: this.catalog.all().map(t => ({
        id: t.id,
        moduleId: t.moduleId,
        name: t.name,
        risk: t.risk,
        onCooldown: this.pipeline.isOnCooldown(t.id),
        turnsUntilEligible: this.pipeline.turnsUntilEligible(t.id),
      })),
    }
  }

  /**
   * Expose the catalog for external modules that want to register additional
   * upgradeable targets (e.g. a plugin registering its own prompts).
   */
  getCatalog(): UpgradeCatalog {
    return this.catalog
  }
}


export const createAIEngineer = (
  logger: ILogger,
  config?: Partial<AIEngineerConfig>,
): AIEngineer => new AIEngineer(logger, config)
