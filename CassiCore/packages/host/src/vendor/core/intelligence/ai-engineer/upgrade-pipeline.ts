/**
 * AI Engineer — Upgrade Pipeline
 *
 * Manages the full lifecycle of a single upgrade attempt:
 *
 *   IDLE → SELECTING → DRAFTING → CRITIQUING → TRIALING → CONCLUDING → IDLE
 *
 * Responsibilities:
 *   - Target selection based on module health and cooldown state
 *   - Coordinating the PromptEvolver to produce a validated proposal
 *   - Applying and reverting upgrades via KV store
 *   - Tracking trial turns and collecting metrics
 *   - Emitting outcome events on the EventBus
 *   - Persisting state to KV for daemon restarts
 *
 * One pipeline instance handles one active trial at a time to prevent
 * confounding variables from concurrent experiments.
 */

import { type PerformanceMonitor } from './performance-monitor.js'
import { PromptEvolver } from './prompt-evolver.js'
import { UpgradeCatalog } from './upgrade-catalog.js'

import type {
  UpgradePhase,
  UpgradeTarget,
  UpgradeProposal,
  UpgradeTrial,
  EngineerState,
  TrialOutcome,
  UpgradeBackup,
  PreConcludeResult,
} from './upgrade-types.js'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus } from '@cassicore/foundation'


/** Global cooldown (turns) after any trial concludes before the next can start. */
const GLOBAL_COOLDOWN_TURNS = 100

/** KV key for persisted engineer state. */
const STATE_KV_KEY = 'ai-engineer:state'

/** Maximum recent trials to keep in persisted state. */
const MAX_RECENT_TRIALS = 20

/** KV key for backup history stack. */
const BACKUP_HISTORY_KEY = 'ai-engineer:backup-history'

/** Maximum backups to retain in history. */
const MAX_BACKUPS = 20


export class UpgradePipeline {
  private phase: UpgradePhase = 'idle'
  private activeTrial?: UpgradeTrial
  private activeProposal?: UpgradeProposal

  /** targetId → timestamp of last attempt (ms). */
  private cooldowns = new Map<string, number>()

  private lastTrialConcludedAt?: number
  private globalCooldownTurnsRemaining = 0

  private totalProposals = 0
  private totalAccepted = 0
  private totalRejected = 0
  private recentTrials: UpgradeTrial[] = []

  private readonly evolver: PromptEvolver

  /** External gate delegate — when set, conclude() pauses at pre_conclude */
  private gateDelegate?: (result: PreConcludeResult) => Promise<'accepted' | 'rejected'>

  constructor(
    private readonly catalog: UpgradeCatalog,
    private readonly monitor: PerformanceMonitor,
    private readonly logger: ILogger,
  ) {
    this.evolver = new PromptEvolver(logger)
  }


  /** Advance the pipeline by one turn.  Called from AIEngineer.onTurnEnd(). */
  async tick(
    memory: IMemory,
    eventBus: IEventBus,
    currentTurn: number,
  ): Promise<void> {
    // Decrement global cooldown counter
    if (this.globalCooldownTurnsRemaining > 0) {
      this.globalCooldownTurnsRemaining--
    }

    // Advance active trial if one exists
    if (this.activeTrial && this.activeTrial.phase === 'active') {
      this.activeTrial.turnsObserved++

      const target = this.catalog.get(this.activeTrial.targetId)
      const trialTurns = target ? UpgradeCatalog.trialTurnsFor(target) : 30

      if (this.activeTrial.turnsObserved >= trialTurns) {
        await this.conclude(memory, eventBus)
      }
      return // While a trial is active, don't start another
    }

    // If on global cooldown, do nothing
    if (this.globalCooldownTurnsRemaining > 0) return

    // Otherwise, we are IDLE — run the selection + drafting pipeline
    this.phase = 'idle'
    await this.attemptCycle(memory, eventBus, currentTurn)
  }

  /** Force-abort an active trial and revert the upgrade.  Used by stop(). */
  async abortActiveTrial(memory: IMemory): Promise<void> {
    if (!this.activeTrial || this.activeTrial.phase !== 'active') return
    await this.revertTrial(memory, this.activeTrial, 'error')
  }

  /** Return the current pipeline phase. */
  getPhase(): UpgradePhase {
    return this.phase
  }

  /** Return the active trial if one is running. */
  getActiveTrial(): UpgradeTrial | undefined {
    return this.activeTrial?.phase === 'active' ? this.activeTrial : undefined
  }

  /** Return the active proposal if one is in flight. */
  getActiveProposal(): UpgradeProposal | undefined {
    return this.activeProposal
  }

  /** Summary statistics. */
  stats(): { totalProposals: number; totalAccepted: number; totalRejected: number; recentTrials: UpgradeTrial[] } {
    return {
      totalProposals: this.totalProposals,
      totalAccepted: this.totalAccepted,
      totalRejected: this.totalRejected,
      recentTrials: [...this.recentTrials],
    }
  }

  /** Persist pipeline state to KV for daemon restarts. */
  async persistState(memory: IMemory): Promise<void> {
    try {
      const state: EngineerState = {
        phase: this.phase,
        activeTrial: this.activeTrial,
        activeProposal: this.activeProposal,
        cooldowns: Object.fromEntries(this.cooldowns.entries()),
        lastTrialConcludedAt: this.lastTrialConcludedAt,
        totalProposals: this.totalProposals,
        totalAccepted: this.totalAccepted,
        totalRejected: this.totalRejected,
        recentTrials: this.recentTrials,
      }
      await memory.kv_set(STATE_KV_KEY, state)
    } catch (err) {
      this.logger.debug('UpgradePipeline: state persist failed', { error: String(err) })
    }
  }

  /** Restore pipeline state from KV on daemon restart. */
  async restoreState(memory: IMemory): Promise<void> {
    try {
      const state = await memory.kv_get<EngineerState>(STATE_KV_KEY)
      if (!state) return

      this.cooldowns = new Map(Object.entries(state.cooldowns ?? {}))
      this.lastTrialConcludedAt = state.lastTrialConcludedAt
      this.totalProposals = state.totalProposals ?? 0
      this.totalAccepted = state.totalAccepted ?? 0
      this.totalRejected = state.totalRejected ?? 0
      this.recentTrials = state.recentTrials ?? []

      // If there was an active trial when the daemon died, we cannot safely
      // resume it (we don't know whether the upgraded value is live or not).
      // Revert to backed-up value and reset to idle.
      if (state.activeTrial?.phase === 'active') {
        this.logger.warn('UpgradePipeline: active trial found on restore — reverting', {
          trialId: state.activeTrial.id,
          targetId: state.activeTrial.targetId,
        })
        await this.revertTrial(memory, state.activeTrial, 'error')
      }

      this.phase = 'idle'
      this.logger.info('UpgradePipeline: state restored', {
        totalProposals: this.totalProposals,
        totalAccepted: this.totalAccepted,
        recentTrials: this.recentTrials.length,
      })
    } catch (err) {
      this.logger.debug('UpgradePipeline: state restore failed', { error: String(err) })
    }
  }


  private async attemptCycle(
    memory: IMemory,
    eventBus: IEventBus,
    _currentTurn: number,
  ): Promise<void> {
    this.phase = 'selecting'
    const target = this.selectTarget()
    if (!target) {
      this.phase = 'idle'
      emitEvent(eventBus, 'ai-engineer:upgrade-skipped', { reason: 'all targets on cooldown or no weak module found' })
      return
    }

    this.logger.debug('UpgradePipeline: target selected', { targetId: target.id, moduleId: target.moduleId })

    this.phase = 'drafting'

    // Read current live value (or fall back to catalog default)
    const currentValue = await readCurrentValue(memory, target)

    this.phase = 'critiquing'
    const proposal = await this.evolver.evolve(target, currentValue, memory)
    this.totalProposals++

    if (!proposal) {
      // Evolution failed validation gate — put target on short cooldown
      this.setCooldown(target.id, 50)
      this.phase = 'idle'
      emitEvent(eventBus, 'ai-engineer:upgrade-skipped', {
        targetId: target.id,
        reason: 'proposal failed validation gate',
      })
      return
    }

    this.phase = 'trialing'
    this.activeProposal = proposal
    await this.startTrial(target, proposal, memory, eventBus)
  }


  /**
   * Pick the best upgrade target to work on:
   *   1. Targets whose module has the lowest health score
   *   2. Among those, prefer targets that have been idle the longest
   *   3. Skip targets on cooldown
   */
  private selectTarget(): UpgradeTarget | null {
    const now = Date.now()
    const allTargets = this.catalog.all()

    // Build eligible set: not on cooldown
    const eligible = allTargets.filter(t => {
      const lastAttempt = this.cooldowns.get(t.id) ?? 0
      const cooldownMs = t.cooldownTurns * 5_000 // Approximate: 5 s per turn
      return now - lastAttempt >= cooldownMs
    })

    if (eligible.length === 0) return null

    // Score each eligible target: lower module health = higher priority
    const scored = eligible.map(t => ({
      target: t,
      moduleHealthScore: this.monitor.healthScore(t.moduleId),
      lastAttempt: this.cooldowns.get(t.id) ?? 0,
    }))

    // Sort: lowest health first, then longest-idle first
    scored.sort((a, b) => {
      const healthDiff = a.moduleHealthScore - b.moduleHealthScore
      if (Math.abs(healthDiff) > 0.05) return healthDiff
      return a.lastAttempt - b.lastAttempt // older attempt = higher priority
    })

    return scored[0]?.target ?? null
  }


  private async startTrial(
    target: UpgradeTarget,
    proposal: UpgradeProposal,
    memory: IMemory,
    eventBus: IEventBus,
  ): Promise<void> {
    const backupKey = UpgradeCatalog.backupKvKeyFor(target)

    // Step 1: Capture baseline metrics (snapshot before applying change)
    const baselineMetrics = this.monitor.snapshotMetrics(
      target.moduleId,
      target.primaryMetrics,
      UpgradeCatalog.trialTurnsFor(target),
    )

    // Step 2: Save backup of current value to KV
    try {
      const current = await readCurrentValue(memory, target)
      await memory.kv_set(backupKey, current)
    } catch (err) {
      this.logger.warn('UpgradePipeline: failed to save backup before trial', {
        targetId: target.id, error: String(err),
      })
    }

    // Step 3: Write the new value to KV
    try {
      await memory.kv_set(target.kvKey, proposal.after)
    } catch (err) {
      this.logger.error('UpgradePipeline: failed to apply upgrade to KV', {
        targetId: target.id, error: String(err),
      })
      this.phase = 'idle'
      this.activeProposal = undefined
      return
    }

    // Step 4: Emit reload event so the target module picks up the change
    if (target.reloadEvent) {
      emitEvent(eventBus, target.reloadEvent, { targetId: target.id, moduleId: target.moduleId })
    }

    // Step 5: Create trial record
    const trial: UpgradeTrial = {
      id: `trial-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      proposalId: proposal.id,
      targetId: target.id,
      moduleId: target.moduleId,
      phase: 'active',
      startedAt: Date.now(),
      turnsObserved: 0,
      backupKey,
      baselineMetrics,
      trialMetrics: {},
    }

    this.activeTrial = trial
    this.monitor.recordUpgradeAttempt(target.moduleId)
    this.setCooldown(target.id, target.cooldownTurns)

    emitEvent(eventBus, 'ai-engineer:upgrade-proposed', {
      trialId: trial.id,
      targetId: target.id,
      moduleId: target.moduleId,
      rationale: proposal.rationale,
      validationScore: proposal.validationScore,
    })

    this.logger.info('UpgradePipeline: trial started', {
      trialId: trial.id,
      targetId: target.id,
      trialTurns: UpgradeCatalog.trialTurnsFor(target),
    })
  }


  private async conclude(memory: IMemory, eventBus: IEventBus): Promise<void> {
    const result = await this.preConclude(memory)
    if (!result) {
      // preConclude already handled the error case (reverted)
      if (this.activeTrial) this.finaliseConclusion(this.activeTrial, eventBus)
      return
    }

    if (this.gateDelegate) {
      // Delegate to external gate (ImprovementOrchestrator)
      try {
        const verdict = await this.gateDelegate(result)
        await this.concludeWithVerdict(memory, eventBus, verdict,
          verdict === 'accepted' ? `Gate confirmed: ${result.reason}` : 'Gate rejected — regressions detected')
      } catch (err) {
        this.logger.warn('UpgradePipeline: gate delegate failed, self-concluding', { error: String(err) })
        await this.concludeWithVerdict(memory, eventBus,
          result.recommendation === 'accepted' ? 'accepted' : 'rejected', result.reason)
      }
    } else {
      await this.concludeWithVerdict(memory, eventBus,
        result.recommendation === 'accepted' ? 'accepted' : 'rejected', result.reason)
    }
  }

  private finaliseConclusion(trial: UpgradeTrial, _eventBus: IEventBus): void {
    this.recentTrials.unshift(trial)
    if (this.recentTrials.length > MAX_RECENT_TRIALS) {
      this.recentTrials = this.recentTrials.slice(0, MAX_RECENT_TRIALS)
    }

    this.activeTrial = undefined
    this.activeProposal = undefined
    this.lastTrialConcludedAt = Date.now()
    this.globalCooldownTurnsRemaining = GLOBAL_COOLDOWN_TURNS
    this.phase = 'idle'
  }


  private async revertTrial(
    memory: IMemory,
    trial: UpgradeTrial,
    outcome: TrialOutcome,
    eventBus?: IEventBus,
  ): Promise<void> {
    const target = this.catalog.get(trial.targetId)
    try {
      const backup = await memory.kv_get<string | Record<string, unknown>>(trial.backupKey)
      if (backup !== null && backup !== undefined) {
        await memory.kv_set(trial.targetId.replace('/', ':'), backup)
        // Write back using the target's actual KV key
        const kvKey = target?.kvKey ?? trial.backupKey.replace(':backup', '')
        await memory.kv_set(kvKey, backup)
      } else {
        // No backup — delete the key so the module falls back to its hardcoded default
        // We can't delete KV keys directly; write the catalog default instead
        if (target) {
          await memory.kv_set(target.kvKey, target.defaultValue)
        }
      }
    } catch (err) {
      this.logger.error('UpgradePipeline: revert failed', {
        targetId: trial.targetId, error: String(err),
      })
    }

    trial.outcome = outcome
    trial.phase = 'concluded'
    trial.concludedAt = Date.now()

    // Emit reload event to pick up reverted value
    if (eventBus && target?.reloadEvent) {
      emitEvent(eventBus, target.reloadEvent, { targetId: trial.targetId, moduleId: target?.moduleId })
    }
  }


  private setCooldown(targetId: string, turns: number): void {
    // Convert turns to ms at ~5 s/turn approximation
    this.cooldowns.set(targetId, Date.now() + turns * 5_000)
  }

  /** True if a target is currently on cooldown. */
  isOnCooldown(targetId: string): boolean {
    const expires = this.cooldowns.get(targetId) ?? 0
    return Date.now() < expires
  }

  /** Turns remaining until a target's cooldown expires (approximate). */
  turnsUntilEligible(targetId: string): number {
    const expires = this.cooldowns.get(targetId) ?? 0
    const remaining = expires - Date.now()
    return remaining <= 0 ? 0 : Math.ceil(remaining / 5_000)
  }


  /** Set external gate delegate. When set, conclude() pauses at pre_conclude and delegates. */
  setGateDelegate(fn: ((result: PreConcludeResult) => Promise<'accepted' | 'rejected'>) | undefined): void {
    this.gateDelegate = fn
  }


  /** Push a backup entry to the history stack. */
  private async pushBackupHistory(memory: IMemory, backup: UpgradeBackup): Promise<void> {
    try {
      const history = await memory.kv_get<UpgradeBackup[]>(BACKUP_HISTORY_KEY) ?? []
      history.unshift(backup)
      if (history.length > MAX_BACKUPS) {
        history.length = MAX_BACKUPS
      }
      await memory.kv_set(BACKUP_HISTORY_KEY, history)
    } catch (err) {
      this.logger.debug('UpgradePipeline: backup history push failed', { error: String(err) })
    }
  }

  /** Retrieve the full backup history. */
  async getBackupHistory(memory: IMemory): Promise<UpgradeBackup[]> {
    try {
      return await memory.kv_get<UpgradeBackup[]>(BACKUP_HISTORY_KEY) ?? []
    } catch {
      return []
    }
  }

  /** Revert to a specific backup version (admin API). */
  async revertToVersion(
    memory: IMemory,
    eventBus: IEventBus,
    targetId: string,
    versionIndex?: number,
  ): Promise<{ success: boolean; detail: string }> {
    const history = await this.getBackupHistory(memory)
    const targetBackups = history.filter(b => b.targetId === targetId)
    if (targetBackups.length === 0) {
      return { success: false, detail: 'No backups found for target' }
    }
    const backup = targetBackups[versionIndex ?? 0]
    if (!backup) {
      return { success: false, detail: `Version index ${versionIndex} out of range (${targetBackups.length} backups)` }
    }
    try {
      await memory.kv_set(backup.kvKey, backup.value)
      const target = this.catalog.get(targetId)
      if (target?.reloadEvent) {
        emitEvent(eventBus, target.reloadEvent, { targetId, moduleId: target.moduleId })
      }
      return { success: true, detail: `Reverted ${targetId} to backup from trial ${backup.trialId}` }
    } catch (err) {
      return { success: false, detail: `Revert failed: ${String(err)}` }
    }
  }


  /** Evaluate metrics and compute recommendation WITHOUT applying verdict */
  async preConclude(memory: IMemory): Promise<PreConcludeResult | null> {
    if (!this.activeTrial) return null
    this.phase = 'pre_conclude'
    const trial = this.activeTrial
    const target = this.catalog.get(trial.targetId)
    if (!target) {
      await this.revertTrial(memory, trial, 'error')
      return null
    }

    const trialMetrics = this.monitor.snapshotMetrics(
      target.moduleId, target.primaryMetrics, UpgradeCatalog.trialTurnsFor(target),
    )
    trial.trialMetrics = trialMetrics

    const deltaPercent: Record<string, number> = {}
    for (const metric of target.primaryMetrics) {
      const baseline = trial.baselineMetrics[metric]
      const trialVal = trialMetrics[metric]
      if (baseline !== undefined && trialVal !== undefined && baseline !== 0) {
        deltaPercent[metric] = ((trialVal - baseline) / baseline) * 100
      }
    }
    trial.deltaPercent = deltaPercent
    const { outcome, reason } = evaluateOutcome(target, deltaPercent)

    return { trial, target, deltaPercent, recommendation: outcome, reason }
  }

  /** Apply the given verdict (accept or revert) */
  async concludeWithVerdict(
    memory: IMemory,
    eventBus: IEventBus,
    verdict: 'accepted' | 'rejected',
    reason: string,
  ): Promise<void> {
    if (!this.activeTrial) return
    this.phase = 'concluding'
    const trial = this.activeTrial
    const target = this.catalog.get(trial.targetId)

    trial.outcome = verdict === 'accepted' ? 'accepted' : 'rejected'
    trial.outcomeReason = reason
    trial.phase = 'concluded'
    trial.concludedAt = Date.now()

    if (verdict === 'accepted') {
      this.totalAccepted++
      this.logger.info('UpgradePipeline: trial ACCEPTED (gate-delegated)', {
        targetId: trial.targetId, deltaPercent: trial.deltaPercent, reason,
      })
      emitEvent(eventBus, 'ai-engineer:upgrade-applied', {
        trialId: trial.id, targetId: trial.targetId,
        moduleId: trial.moduleId, deltaPercent: trial.deltaPercent ?? {}, reason,
      })
    } else {
      await this.revertTrial(memory, trial, 'rejected', eventBus)
      this.totalRejected++
      this.logger.info('UpgradePipeline: trial REVERTED (gate-delegated)', {
        targetId: trial.targetId, outcome: 'rejected', reason,
      })
      emitEvent(eventBus, 'ai-engineer:upgrade-reverted', {
        trialId: trial.id, targetId: trial.targetId,
        moduleId: trial.moduleId, outcome: 'rejected',
        deltaPercent: trial.deltaPercent ?? {}, reason,
      })
    }

    this.finaliseConclusion(trial, eventBus)
  }
}


function evaluateOutcome(
  target: UpgradeTarget,
  deltaPercent: Record<string, number>,
): { outcome: TrialOutcome; reason: string } {
  const threshold = UpgradeCatalog.acceptanceThresholdFor(target) * 100 // convert to %
  const deltas = Object.entries(deltaPercent)

  if (deltas.length === 0) {
    return { outcome: 'inconclusive', reason: 'no metrics available for comparison' }
  }

  const improvements = deltas.filter(([, d]) => d >= threshold)
  const regressions = deltas.filter(([, d]) => d <= -threshold * 2)

  if (regressions.length > 0) {
    const worst = regressions.sort(([, a], [, b]) => a - b)[0]!
    return {
      outcome: 'rejected',
      reason: `regression in ${worst[0]}: ${worst[1].toFixed(1)}%`,
    }
  }

  if (improvements.length > 0) {
    const best = improvements.sort(([, a], [, b]) => b - a)[0]!
    return {
      outcome: 'accepted',
      reason: `${best[0]} improved by ${best[1].toFixed(1)}% (threshold: ${threshold.toFixed(1)}%)`,
    }
  }

  return {
    outcome: 'inconclusive',
    reason: `no metric met the ${threshold.toFixed(1)}% improvement threshold`,
  }
}


/**
 * @dep callers: startTrial (core/intelligence/ai-engineer/upgrade-pipeline.ts), attemptCycle (core/intelligence/ai-engineer/upgrade-pipeline.ts)
 * @dep module: Ai-engineer
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

async function readCurrentValue(
  memory: IMemory,
  target: UpgradeTarget,
): Promise<string | Record<string, unknown>> {
  try {
    const kv = await memory.kv_get<string | Record<string, unknown>>(target.kvKey)
    if (kv !== null && kv !== undefined) return kv
  } catch {}
  return target.defaultValue
}

/**
 * @dep callers: concludeWithVerdict (core/intelligence/ai-engineer/upgrade-pipeline.ts), revertToVersion (core/intelligence/ai-engineer/upgrade-pipeline.ts), revertTrial (core/intelligence/ai-engineer/upgrade-pipeline.ts), startTrial (core/intelligence/ai-engineer/upgrade-pipeline.ts), attemptCycle (core/intelligence/ai-engineer/upgrade-pipeline.ts)
 * @dep calls: emit
 * @dep module: Ai-engineer
 * @dep risk: MEDIUM | 5 callers, 0 flows, 1 module
 */

function emitEvent(bus: IEventBus, type: string, payload: Record<string, unknown>): void {
  try {
    ;(bus as any).emit?.({ type, ...payload })
  } catch {}
}
