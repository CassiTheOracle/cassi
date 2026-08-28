/**
 * Improvement Orchestrator — Self-improvement loop coordinator.
 *
 * A CycleHook that runs on the Unified Intelligence Loop, coordinating:
 *   1. Proposal queue intake (from AdaptiveBehavior, AIEngineer, AIScientist)
 *   2. Gate evaluation (scenario-backed verification before/after adaptation)
 *   3. Journal recording (persistent traceability of all attempts)
 *   4. Meta-learning (analyze the journal, adjust own parameters)
 *   5. Staleness detection (mark always-passing scenarios as stale)
 *
 * Priority: 15 (runs after all other modules — purely meta-level)
 *
 * The orchestrator does NOT generate improvements itself — it coordinates
 * existing modules, keeping concerns separated.
 */

import os from 'node:os'
import path from 'node:path'

import Database from 'better-sqlite3'

import { ImprovementGate } from './improvement-gate.js'
import { ImprovementJournal } from './improvement-journal.js'
import { ScenarioGenerator } from './scenario-generator.js'
import { DEFAULT_IMPROVEMENT_CONFIG } from './types.js'
import { ScenarioStore } from '../../testing/scenarios/scenario-store.js'
import { LiveWorkflowHarness } from '../../testing/live/index.js'

import type { CycleHook } from '../unified-loop.js'
import type { ILogger, IEventBus, IntelligenceModule } from '@cassicore/foundation'
import type {
  ImprovementConfig,
  ImprovementProposal,
  ImprovementEntry,
  ImprovementVerdict,
  ImprovementProposalClass,
  ImprovementVerificationStatus,
  JournalStats,
  GateMode,
} from './types.js'

type ProposalEvaluation = {
  accepted: boolean
  normalized: ImprovementProposal
  qualityScore: number
  reasons: string[]
}

export class ImprovementOrchestrator implements IntelligenceModule, CycleHook {
  readonly name = 'improvement-orchestrator'
  readonly priority = 15
  readonly cadence = 5 // Every 5th cycle (~5 min at 60s default)

  private readonly logger: ILogger
  private config: ImprovementConfig
  private eventBus?: IEventBus

  // Sub-components
  private gate: ImprovementGate
  private journal: ImprovementJournal
  private generator: ScenarioGenerator
  private scenarioStore: ScenarioStore
  private db?: Database.Database

  // Proposal queue
  private proposalQueue: ImprovementProposal[] = []
  private recentQueuedKeys = new Map<string, number>()

  // Metrics
  private totalProposalsReceived = 0
  private totalProposalsProcessed = 0
  private totalGatePassed = 0
  private totalGateFailed = 0
  private totalGateSkipped = 0
  private lastCycleAt = 0
  private metaLearningCycleCount = 0


  constructor(logger: ILogger, config?: Partial<ImprovementConfig>) {
    this.logger = logger.child?.('improvement-orchestrator') ?? logger
    this.config = { ...DEFAULT_IMPROVEMENT_CONFIG, ...config }

    this.scenarioStore = new ScenarioStore(this.logger)
    this.journal = new ImprovementJournal(this.logger)
    this.generator = new ScenarioGenerator({
      logger: this.logger,
      scenarioStore: this.scenarioStore,
      config: this.config,
    })
    this.gate = new ImprovementGate({
      logger: this.logger,
      config: this.config,
      scenarioStore: this.scenarioStore,
    })
  }

  start(): void {
    if (!this.config.enabled) {
      this.logger.info('Disabled by config')
      return
    }

    this.initPersistence()
    this.logger.info('Started', {
      gateMode: this.config.gateMode,
      lowRiskAsyncAllowed: this.config.lowRiskAsyncAllowed,
      metaLearningCadence: this.config.metaLearningCadence,
    })
  }

  stop(): void {
    this.gate.cancelPending()
    this.logger.info('Stopped', {
      proposalsProcessed: this.totalProposalsProcessed,
      gatePassed: this.totalGatePassed,
      gateFailed: this.totalGateFailed,
    })
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
    this.generator.initialize(bus)
    this.gate.setEventBus(bus)

    if (!this.gate.hasBackend()) {
      const backend = new LiveWorkflowHarness({ autoPrune: false })
      this.gate.setBackend(backend, 'live-harness')
      this.logger.info('Improvement gate wired to live verification backend')
    }
  }


  private initPersistence(): void {
    try {
      const dataDir = path.join(os.homedir(), '.cassicore', 'data')
      const dbPath = path.join(dataDir, 'system-state.db')
      this.db = new Database(dbPath)
      this.db.pragma('journal_mode = WAL')

      this.journal.initialize(this.db)
      this.scenarioStore.initialize(this.db)

      this.logger.info('Persistence ready', { dbPath })
    } catch (err) {
      this.logger.error('Persistence init failed', { error: String(err) })
    }
  }


  /**
   * Submit an improvement proposal. Called by AdaptiveBehavior, AIEngineer,
   * AIScientist, or manually via admin API/MCP.
   *
   * Proposals are queued and processed on the next cycle.
   */
  propose(proposal: ImprovementProposal): void {
    if (!this.config.enabled) return

    const evaluation = this.evaluateProposal(proposal)
    if (!evaluation.accepted) {
      this.logger.debug('Proposal rejected', {
        proposalId: proposal.id,
        confidence: proposal.confidence,
        qualityScore: evaluation.qualityScore,
        reasons: evaluation.reasons,
      })
      return
    }

    const normalized = evaluation.normalized
    if (normalized.dedupeKey) {
      this.recentQueuedKeys.set(normalized.dedupeKey, Date.now())
    }

    this.proposalQueue.push(normalized)
    this.totalProposalsReceived++

    this.emitEvent('improvement:proposal-queued', {
      proposalId: normalized.id,
      trigger: normalized.trigger,
      source: normalized.source,
      confidence: normalized.confidence,
      qualityScore: normalized.qualityScore,
    })

    this.logger.info('Proposal queued', {
      proposalId: normalized.id,
      trigger: normalized.trigger,
      source: normalized.source,
      qualityScore: normalized.qualityScore,
      queueDepth: this.proposalQueue.length,
    })
  }


  async execute(cycleNumber: number): Promise<string | void> {
    if (!this.config.enabled) return

    const now = Date.now()
    const actions: string[] = []

    try {
      // 1. Process proposals from the queue
      if (this.proposalQueue.length > 0) {
        const processed = await this.processProposals()
        if (processed > 0) actions.push(`processed ${processed} proposal(s)`)
      }

      // 2. Meta-learning pass (at lower cadence)
      this.metaLearningCycleCount++
      if (this.metaLearningCycleCount >= this.config.metaLearningCadence) {
        this.metaLearningCycleCount = 0
        const metaResult = await this.runMetaLearning()
        if (metaResult) actions.push(metaResult)
      }

      this.lastCycleAt = now

      if (actions.length > 0) {
        return `improvement: ${actions.join(', ')}`
      }
    } catch (err) {
      this.logger.error('Cycle failed', {
        error: String(err),
        cycleNumber,
      })
    }
  }


  async onTurnStart(_ctx: Record<string, unknown>): Promise<void> {
    // No per-turn actions needed
  }

  async onTurnEnd(_ctx: Record<string, unknown>): Promise<void> {
    // No per-turn actions needed — the orchestrator operates at cycle level
  }

  async injectContext(_ctx: Record<string, unknown>): Promise<string | null> {
    // The orchestrator doesn't inject into conversation context
    return null
  }


  private async processProposals(): Promise<number> {
    // Sort by confidence × risk-inverse (high confidence + high risk first for sync gate)
    const ranked = this.proposalQueue.sort((a, b) => {
      const riskWeight = { high: 3, moderate: 2, low: 1 }
      const scoreA = a.confidence * (riskWeight[a.riskLevel] || 1)
      const scoreB = b.confidence * (riskWeight[b.riskLevel] || 1)
      return scoreB - scoreA
    })

    const toProcess = ranked.slice(0, this.config.maxConcurrentProposals)
    this.proposalQueue = ranked.slice(this.config.maxConcurrentProposals)

    let processed = 0

    for (const proposal of toProcess) {
      try {
        await this.processOneProposal(proposal)
        processed++
      } catch (err) {
        this.logger.error('Proposal processing failed', {
          proposalId: proposal.id,
          error: String(err),
        })
      }
    }

    return processed
  }

  private async processOneProposal(proposal: ImprovementProposal): Promise<void> {
    this.totalProposalsProcessed++

    // The gate needs applyFn and revertFn — since the orchestrator is generic,
    // these need to come from the original proposer. For now, we use the
    // proposal's config to emit adaptation events.
    const applyFn = async () => {
      this.emitEvent('improvement:applying', {
        proposalId: proposal.id,
        adaptation: proposal.adaptation,
        config: proposal.config,
      })
    }

    const revertFn = async () => {
      this.emitEvent('improvement:reverting', {
        proposalId: proposal.id,
        adaptation: proposal.adaptation,
      })
    }

    // Run the gate
    const gateResult = await this.gate.evaluate(proposal, applyFn, revertFn)

    // Determine verdict
    let verdict: ImprovementVerdict
    let verificationStatus: ImprovementVerificationStatus
    if (gateResult.verdict === 'failed') {
      verdict = 'reverted'
      verificationStatus = 'verified'
      this.totalGateFailed++
    } else if (gateResult.verdict === 'skipped') {
      verdict = 'inconclusive'
      verificationStatus = 'unverified'
      this.totalGateSkipped++
    } else {
      verdict = 'confirmed'
      verificationStatus = 'verified'
      this.totalGatePassed++
    }

    // Build journal entry
    const learnings = this.buildLearnings(proposal, gateResult, verdict)
    const entry: ImprovementEntry = {
      id: `imp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      proposalId: proposal.id,
      trigger: proposal.trigger,
      source: proposal.source,
      proposalClass: proposal.proposalClass ?? this.defaultProposalClass(proposal.trigger),
      hypothesis: proposal.hypothesis,
      adaptation: proposal.adaptation,
      config: proposal.config,
      dedupeKey: proposal.dedupeKey,
      confidence: proposal.confidence,
      qualityScore: proposal.qualityScore ?? 0,
      evidence: proposal.evidence,
      gateMode: gateResult.mode,
      gateVerdict: gateResult.verdict,
      verificationStatus,
      regressions: gateResult.regressions,
      improvements: gateResult.improvements,
      verdict,
      revertReason: gateResult.regressions.length > 0
        ? `Regressions in: ${gateResult.regressions.join(', ')}`
        : undefined,
      learnings,
      createdAt: Date.now(),
      concludedAt: Date.now(),
    }

    // Record in journal
    this.journal.record(entry)

    // Emit events
    if (verdict === 'confirmed') {
      this.emitEvent('improvement:confirmed', {
        proposalId: proposal.id,
        improvements: gateResult.improvements,
      })
    } else if (verdict === 'reverted') {
      this.emitEvent('improvement:reverted', {
        proposalId: proposal.id,
        reason: entry.revertReason,
      })
    }

    this.logger.info('Proposal processed', {
      proposalId: proposal.id,
      verdict,
      verificationStatus,
      gateVerdict: gateResult.verdict,
      regressions: gateResult.regressions.length,
      improvements: gateResult.improvements.length,
      durationMs: gateResult.durationMs,
    })
  }


  private async runMetaLearning(): Promise<string | null> {
    const stats = this.journal.getStats()

    // Need minimum data before meta-learning is useful
    if (stats.total < this.config.minJournalEntries) return null

    const adjustments: string[] = []

    // 1. Adjust confidence threshold based on revert rate
    if (stats.revertRate > 0.4 && this.config.confidenceThreshold < 0.9) {
      const oldThreshold = this.config.confidenceThreshold
      this.config.confidenceThreshold = Math.min(0.9, this.config.confidenceThreshold + 0.05)
      adjustments.push(`confidence threshold: ${oldThreshold.toFixed(2)} → ${this.config.confidenceThreshold.toFixed(2)}`)
    } else if (stats.revertRate < 0.1 && stats.total >= 10 && this.config.confidenceThreshold > 0.5) {
      // Low revert rate — we can be more permissive
      const oldThreshold = this.config.confidenceThreshold
      this.config.confidenceThreshold = Math.max(0.5, this.config.confidenceThreshold - 0.02)
      adjustments.push(`confidence threshold: ${oldThreshold.toFixed(2)} → ${this.config.confidenceThreshold.toFixed(2)}`)
    }

    // 2. Detect thrashing (same adaptation type reverted > 3 times)
    for (const [type, typeStats] of Object.entries(stats.byAdaptationType)) {
      if (typeStats.revertRate > 0.6 && typeStats.total > 3) {
        this.emitEvent('improvement:thrashing-detected', {
          adaptationType: type,
          revertRate: typeStats.revertRate,
          total: typeStats.total,
        })
        adjustments.push(`thrashing: ${type} (${(typeStats.revertRate * 100).toFixed(0)}% revert rate)`)
      }
    }

    // 3. Detect stale scenarios
    const staleScenarios = this.generator.detectStaleness()
    if (staleScenarios.length > 0) {
      adjustments.push(`stale scenarios: ${staleScenarios.length}`)
    }

    if (adjustments.length > 0) {
      this.emitEvent('improvement:meta-learning', { adjustments })
      this.logger.info('Meta-learning adjustments', { adjustments })
      return `meta-learning: ${adjustments.join(', ')}`
    }

    return null
  }


  /** Get the full orchestrator status for admin API / MCP */
  getStatus(): {
    enabled: boolean
    gateMode: GateMode
    queueDepth: number
    totalProposalsReceived: number
    totalProposalsProcessed: number
    totalGatePassed: number
    totalGateFailed: number
      totalGateSkipped: number
      confidenceThreshold: number
      lastCycleAt: number
      scenarioCount: number
      hasBackend: boolean
      backend: string | null
      proposalQualityThreshold: number
      journalStats: JournalStats
  } {
    return {
      enabled: this.config.enabled,
      gateMode: this.config.gateMode,
      queueDepth: this.proposalQueue.length,
      totalProposalsReceived: this.totalProposalsReceived,
      totalProposalsProcessed: this.totalProposalsProcessed,
      totalGatePassed: this.totalGatePassed,
      totalGateFailed: this.totalGateFailed,
      totalGateSkipped: this.totalGateSkipped,
      confidenceThreshold: this.config.confidenceThreshold,
      proposalQualityThreshold: this.config.proposalQualityThreshold,
      lastCycleAt: this.lastCycleAt,
      scenarioCount: this.scenarioStore.getAll().length,
      hasBackend: this.gate.hasBackend(),
      backend: this.gate.getBackendLabel() ?? null,
      journalStats: this.journal.getStats(),
    }
  }

  /** Query the journal (for admin API / MCP) */
  queryJournal(opts?: Parameters<ImprovementJournal['query']>[0]): ImprovementEntry[] {
    return this.journal.query(opts)
  }

  /** Get recent learnings */
  getRecentLearnings(limit = 10): string[] {
    return this.journal.getRecentLearnings(limit)
  }

  /** Get all scenarios (including generated) */
  getScenarios(): ReturnType<ScenarioStore['getAll']> {
    return this.scenarioStore.getAll()
  }

  /** Access the scenario generator for manual scenario creation */
  getGenerator(): ScenarioGenerator {
    return this.generator
  }


  private emitEvent(type: string, payload: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      (this.eventBus as any).emit({ type, ...payload, timestamp: new Date() })
    } catch { /* best effort */ }
  }

  private evaluateProposal(proposal: ImprovementProposal): ProposalEvaluation {
    this.pruneRecentQueuedKeys()

    const normalized: ImprovementProposal = {
      ...proposal,
      proposalClass: proposal.proposalClass ?? this.defaultProposalClass(proposal.trigger),
      dedupeKey: proposal.dedupeKey ?? this.buildDedupeKey(proposal),
    }

    const reasons: string[] = []
    let qualityScore = 0

    if (normalized.confidence < this.config.confidenceThreshold) {
      reasons.push(`confidence ${normalized.confidence.toFixed(2)} below threshold ${this.config.confidenceThreshold.toFixed(2)}`)
    } else {
      qualityScore += 0.35
    }

    if (normalized.hypothesis.trim().length >= 24) {
      qualityScore += 0.1
    } else {
      reasons.push('hypothesis too vague')
    }

    if (normalized.evidence?.targetMetric) {
      qualityScore += 0.15
    } else {
      reasons.push('missing target metric')
    }

    const evidenceCount = normalized.evidence?.dataPoints ?? normalized.evidence?.sampleSize
    if (typeof evidenceCount === 'number' && evidenceCount >= this.config.minEvidenceDataPoints) {
      qualityScore += 0.15
    } else if (normalized.proposalClass !== 'audit') {
      reasons.push('insufficient evidence data points')
    }

    if ((normalized.verificationScenarios?.length ?? 0) > 0) {
      qualityScore += 0.1
    } else if (normalized.proposalClass === 'experiment' || normalized.proposalClass === 'heuristic') {
      reasons.push('missing targeted verification scenarios')
    }

    const classBonus: Record<ImprovementProposalClass, number> = {
      experiment: 0.15,
      heuristic: 0.08,
      repair: 0.04,
      audit: -0.2,
    }
    qualityScore += classBonus[normalized.proposalClass ?? 'heuristic']

    if (normalized.source === 'AIEngineer' && normalized.proposalClass !== 'experiment') {
      qualityScore -= 0.1
      reasons.push('AI Engineer proposals require stronger evidence')
    }

    if (normalized.dedupeKey && this.isDuplicate(normalized.dedupeKey)) {
      reasons.push('duplicate proposal in dedupe window')
      qualityScore = Math.min(qualityScore, 0.1)
    }

    normalized.qualityScore = Math.max(0, Math.min(1, Number(qualityScore.toFixed(3))))

    return {
      accepted: reasons.length === 0 && normalized.qualityScore >= this.config.proposalQualityThreshold,
      normalized,
      qualityScore: normalized.qualityScore,
      reasons: reasons.length === 0 && normalized.qualityScore < this.config.proposalQualityThreshold
        ? [`quality ${normalized.qualityScore.toFixed(2)} below threshold ${this.config.proposalQualityThreshold.toFixed(2)}`]
        : reasons,
    }
  }

  private defaultProposalClass(trigger: ImprovementProposal['trigger']): ImprovementProposalClass {
    switch (trigger) {
      case 'ai-scientist': return 'experiment'
      case 'adaptive':
      case 'ai-engineer':
      case 'manual':
      case 'counter-hypothesis':
      case 'anomaly':
      case 'correlator':
      default:
        return 'heuristic'
    }
  }

  private buildDedupeKey(proposal: ImprovementProposal): string {
    const target = String(proposal.config.target ?? proposal.config.kvKey ?? proposal.config.filePath ?? proposal.source)
    return `${proposal.trigger}:${proposal.adaptation}:${target}`
  }

  private isDuplicate(dedupeKey: string): boolean {
    const since = Date.now() - this.config.dedupeWindowMs
    const queuedAt = this.recentQueuedKeys.get(dedupeKey)
    if (queuedAt && queuedAt >= since) return true
    return this.journal.hasRecentProposal(dedupeKey, since)
  }

  private pruneRecentQueuedKeys(): void {
    const cutoff = Date.now() - this.config.dedupeWindowMs
    for (const [key, ts] of this.recentQueuedKeys.entries()) {
      if (ts < cutoff) this.recentQueuedKeys.delete(key)
    }
  }

  private buildLearnings(
    proposal: ImprovementProposal,
    gateResult: { verdict: string; regressions: string[]; improvements: string[] },
    verdict: ImprovementVerdict,
  ): string[] {
    const learnings: string[] = []
    if (proposal.evidence?.targetMetric) {
      learnings.push(`target metric: ${proposal.evidence.targetMetric}`)
    }
    if (verdict === 'inconclusive') {
      learnings.push('proposal remained unverified because the gate skipped scenario execution')
    }
    if (gateResult.improvements.length > 0) {
      learnings.push(`improved scenarios: ${gateResult.improvements.join(', ')}`)
    }
    if (gateResult.regressions.length > 0) {
      learnings.push(`regressions: ${gateResult.regressions.join(', ')}`)
    }
    return learnings
  }
}


/**
 * @dep callers: improvement-orchestrator.test.ts (tests/improvement-orchestrator.test.ts), createIntelligence (core/intelligence/index.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createImprovementOrchestrator(
  logger: ILogger,
  config?: Partial<ImprovementConfig>,
): ImprovementOrchestrator {
  return new ImprovementOrchestrator(logger, config)
}
