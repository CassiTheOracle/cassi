/**
 * AI Scientist — Active Research Engine
 *
 * This module is the cognitive self-improvement researcher of CassiCore.
 * It functions as an autonomous AI engineer running a continuous scientific
 * method loop focused on four research tracks:
 *
 *   Aging         — detecting and reversing cognitive degradation over time
 *   Development   — tracking and amplifying capability growth
 *   Performance   — active A/B experiments on cognitive parameters
 *   Self-Improvement — meta-research on the research process itself
 *
 * Architecture:
 *   ┌─────────────────────────────────────────────────────────────────────┐
 *   │  Turn events → metric collection → AgingAnalyzer (continuous feed) │
 *   │                                                                     │
 *   │  Every RESEARCH_CYCLE_TURNS:                                        │
 *   │    1. Analyse aging trends                                          │
 *   │    2. Synthesise hypothesis via LLM (using aging + history)         │
 *   │    3. Enqueue experiment into ExperimentEngine                      │
 *   │    4. Feed current metrics to engine (may activate next experiment) │
 *   │    5. Collect conclusions → archive breakthroughs                  │
 *   │    6. Emit events for Thinker / rest of intelligence stack          │
 *   └─────────────────────────────────────────────────────────────────────┘
 *
 * Statistical gate: changes are only applied permanently when p < 0.05
 * and Cohen's |d| ≥ 0.2.  All experiments and conclusions are archived
 * for longitudinal analysis.
 */

import os from 'node:os'
import path from 'node:path'

import Database from 'better-sqlite3'

import { AgingAnalyzer, type AgingReport } from './aging-analyzer.js'
import { ExperimentEngine, type Experiment, type ExperimentMetric, type ExperimentConclusion } from './experiment-engine.js'

import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus, IntelligenceModule } from '@cassicore/foundation'
import type { GlobalBlackboardRegistry } from '@cassicore/flux-team'


export interface AIScientistConfig {
  enabled: boolean
  dataDir: string
  /** How many turns between full research cycles (default 50). */
  researchCycleTurns: number
  /** How many turns between aging snapshots (default 5). */
  agingSnapshotTurns: number
  /** Legacy: kept for backward compat with admin config. Maps to researchCycleTurns × estimated turns-per-hour. */
  studyIntervalHours?: number
  reportRetentionDays: number
  minSampleSize: number
  /** LLM model to use for hypothesis generation. */
  researchModel?: string
}


/** Kept for getRecentStudies() backward compat with admin API. */
export interface StudyResult {
  id: string
  timestamp: number
  type: string
  title: string
  summary: string
  findings: string
  recommendations: string
  confidence: number
  track?: string
  experimentId?: string
  outcomeType?: string
  pValue?: number
  effectSize?: number
  applied?: boolean
}


export interface Breakthrough {
  id: string
  timestamp: number
  track: string
  title: string
  description: string
  metric: string
  deltaPercent: number
  effectSize: number
  pValue: number
  kvKey: string
  appliedValue: unknown
}


export class AIScientist implements IntelligenceModule {
  readonly name = 'ai-scientist'
  readonly priority = 20

  private logger: ILogger
  private config: AIScientistConfig
  private eventBus?: IEventBus
  private memory?: IMemory
  private globalBlackboardRegistry?: GlobalBlackboardRegistry
  private db?: Database.Database

  // Research infrastructure
  private engine?: ExperimentEngine
  private aging = new AgingAnalyzer()
  private breakthroughs: Breakthrough[] = []
  private lastAgingReport?: AgingReport

  // Turn counters
  private turnsSinceResearch = 0
  private turnsSinceAgingSnapshot = 0
  private totalTurns = 0

  // Live metric accumulators (reset each turn)
  private currentTurnMetrics: Partial<Record<ExperimentMetric, number>> = {}

  // Thinker strategy cache (needed to build treatments)
  private thinkerStrategy: Record<string, unknown> = {}

  // Self-improvement loop integration
  private improvementOrchestrator?: any


  constructor(logger: ILogger, config?: Partial<AIScientistConfig>) {
    this.logger = logger.child?.('ai-scientist') ?? logger
    this.config = {
      enabled:              config?.enabled              ?? true,
      dataDir:              config?.dataDir              ?? path.join(os.homedir(), '.cassicore', 'data'),
      researchCycleTurns:   config?.researchCycleTurns   ?? 50,
      agingSnapshotTurns:   config?.agingSnapshotTurns   ?? 5,
      studyIntervalHours:   config?.studyIntervalHours,
      reportRetentionDays:  config?.reportRetentionDays  ?? 90,
      minSampleSize:        config?.minSampleSize        ?? 30,
      researchModel:        config?.researchModel,
    }

    if (this.config.enabled) this.initPersistence()
  }

  /** Wire the improvement orchestrator for verification-gated breakthroughs */
  setImprovementOrchestrator(orchestrator: any): void {
    this.improvementOrchestrator = orchestrator
  }

  start(): void {
    if (!this.config.enabled) return
    this.logger.info('AI Scientist: started', {
      researchCycleTurns: this.config.researchCycleTurns,
      agingSnapshotTurns: this.config.agingSnapshotTurns,
    })
    this.restoreState()
  }

  stop(): void {
    this.persistState()
    this.logger.info('AI Scientist: stopped')
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
    this.engine = new ExperimentEngine(this.logger, this.memory!, bus)
    this.wireEvents(bus)
  }

  setMemory(mem: IMemory): void {
    this.memory = mem
    if (this.eventBus) {
      this.engine = new ExperimentEngine(this.logger, mem, this.eventBus)
    }
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
    this.currentTurnMetrics = {}
  }

  async onTurnEnd(ctx: Record<string, unknown>): Promise<void> {
    if (!this.config.enabled) return

    this.totalTurns++
    this.turnsSinceAgingSnapshot++
    this.turnsSinceResearch++

    // Collect turn latency if available
    if (typeof ctx.durationMs === 'number') {
      this.currentTurnMetrics.turn_latency_ms = ctx.durationMs
    }

    // Collect thinker helpfulness from insight history
    await this.collectThinkerMetrics()

    // Feed aging analyzer periodically
    if (this.turnsSinceAgingSnapshot >= this.config.agingSnapshotTurns) {
      this.snapshotToAgingAnalyzer()
      this.turnsSinceAgingSnapshot = 0
    }

    // Feed experiment engine every turn
    if (this.engine) {
      this.engine.recordBaseline(this.currentTurnMetrics)
      const conclusions = await this.engine.onTurn(this.currentTurnMetrics)
      for (const c of conclusions) {
        await this.processConclusion(c)
      }
    }

    // Full research cycle
    if (this.turnsSinceResearch >= this.config.researchCycleTurns) {
      this.turnsSinceResearch = 0
      await this.runResearchCycle()
    }
  }


  private async runResearchCycle(): Promise<void> {
    this.logger.info('AI Scientist: research cycle starting', { totalTurns: this.totalTurns })

    try {
      // 1. Refresh aging report
      this.lastAgingReport = this.aging.analyse()
      if (this.lastAgingReport.hasActiveDegradation) {
        this.logger.warn('AI Scientist: aging degradation detected', {
          narrative: this.lastAgingReport.narrative,
        })
      }

      // 2. Generate a new hypothesis
      const hypothesis = await this.generateHypothesis()
      if (!hypothesis) {
        this.logger.debug('AI Scientist: no new hypothesis generated this cycle')
        return
      }

      // 3. Build and enqueue experiment
      if (this.engine) {
        const exp = await this.buildExperiment(hypothesis)
        if (exp) this.engine.enqueue(exp)
      }

      // 4. Persist state
      this.persistState()

    } catch (err) {
      this.logger.error('AI Scientist: research cycle failed', { error: String(err) })
    }
  }


  private async generateHypothesis(): Promise<HypothesisResponse | null> {
    // Build context for the LLM
    const agingNarrative = this.lastAgingReport?.narrative ?? 'No aging data yet.'
    const recentBreakthroughs = this.breakthroughs.slice(-5).map(b =>
      `[${b.track}] ${b.title}: ${b.deltaPercent.toFixed(1)}% improvement in ${b.metric} (p=${b.pValue.toFixed(3)}, d=${b.effectSize.toFixed(2)})`
    ).join('\n') || 'None yet.'

    const recentConclusions = (this.engine?.getConcluded() ?? []).slice(-5).map(e =>
      `${e.title} → ${e.outcome} (p=${e.pValue?.toFixed(3) ?? '?'}, d=${e.effectSize?.toFixed(2) ?? '?'})`
    ).join('\n') || 'None yet.'

    const activeExperiments = (this.engine?.getActive() ?? []).map(e => e.treatment.kvKey)
    const queuedExperiments = (this.engine?.getQueue() ?? []).map(e => e.title)

    // Avoid proposing experiments that are already running or queued
    const busyKeys = [...activeExperiments, ...queuedExperiments]

    // Determine which track to focus on this cycle
    const track = this.selectResearchTrack()

    const prompt = buildHypothesisPrompt({
      track,
      agingNarrative,
      recentBreakthroughs,
      recentConclusions,
      thinkerStrategy: this.thinkerStrategy,
      totalTurns: this.totalTurns,
      hasActiveDegradation: this.lastAgingReport?.hasActiveDegradation ?? false,
    })

    try {
      const raw = await this.callLLM(prompt)
      if (!raw) return null
      const parsed = parseHypothesisJSON(raw)
      if (!parsed) return null

      // Check the proposed KV key isn't already under experiment
      const kvKey = parsed.treatment.kvKey
      if (busyKeys.some(k => k === kvKey || k.includes(kvKey))) {
        this.logger.debug('AI Scientist: proposed parameter already under experiment, skipping', { kvKey })
        return null
      }

      return parsed
    } catch (err) {
      this.logger.warn('AI Scientist: hypothesis generation failed', { error: String(err) })
      return null
    }
  }

  /** Round-robin through research tracks, prioritising aging when degradation is active. */
  private selectResearchTrack(): string {
    if (this.lastAgingReport?.hasActiveDegradation) return 'aging'
    const tracks = ['performance', 'development', 'self-improvement', 'aging']
    return tracks[this.totalTurns % tracks.length]
  }

  private async buildExperiment(h: HypothesisResponse): Promise<Omit<Experiment, 'status' | 'baselineSamples' | 'treatmentSamples' | 'turnsElapsed'> | null> {
    // Resolve the current value of the parameter from KV
    let currentStrategy: Record<string, unknown> = {}
    try {
      currentStrategy = (await this.memory?.kv_get<Record<string, unknown>>(h.treatment.kvKey)) ?? {}
    } catch {}

    const baselineValue = { ...currentStrategy }
    const treatmentValue = {
      ...currentStrategy,
      [h.treatment.parameterName]: h.treatment.proposedValue,
    }

    return {
      id: `exp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      title: h.title,
      hypothesis: h.hypothesis,
      rationale: h.rationale,
      track: h.track as Experiment['track'],
      metric: h.metric as ExperimentMetric,
      higherIsBetter: h.higherIsBetter,
      treatment: {
        kvKey: h.treatment.kvKey,
        treatmentValue,
        baselineValue,
        reloadEvent: h.treatment.reloadEvent,
      },
      minSamples: 15,
      maxTurns: 60,
    }
  }


  private async processConclusion(conclusion: ExperimentConclusion): Promise<void> {
    const { experiment: exp, outcome, deltaPercent, pValue, effectSize, appliedPermanently, summary } = conclusion

    // Archive as a study (legacy compat)
    await this.archiveStudy({
      id: `study-${exp.id}`,
      timestamp: Date.now(),
      type: 'experiment',
      title: exp.title,
      summary,
      findings: `Hypothesis: ${exp.hypothesis}\nResult: ${outcome} (${deltaPercent.toFixed(1)}% on ${exp.metric.replace(/_/g, ' ')})`,
      recommendations: appliedPermanently
        ? `Applied: ${exp.treatment.kvKey} updated permanently.`
        : `Reverted: no significant improvement detected.`,
      confidence: pValue < 0.05 ? 0.95 : pValue < 0.1 ? 0.80 : 0.50,
      track: exp.track,
      experimentId: exp.id,
      outcomeType: outcome,
      pValue,
      effectSize,
      applied: appliedPermanently,
    })

    // Post decision to blackboard
    this.postToBoard('system:ai-scientist', 'decisions', JSON.stringify({
      type: 'parameter-change',
      outcome,
      kvKey: exp.treatment.kvKey,
      track: exp.track,
      title: exp.title,
      applied: appliedPermanently,
      deltaPercent: Number(deltaPercent.toFixed(2)),
    }), { tags: ['parameter', exp.track, outcome], priority: appliedPermanently ? 1 : 0 })

    // Store breakthrough
    if (outcome === 'improvement' && appliedPermanently) {
      const bt: Breakthrough = {
        id: `bt-${Date.now()}`,
        timestamp: Date.now(),
        track: exp.track,
        title: exp.title,
        description: `${exp.hypothesis} — confirmed: ${summary}`,
        metric: exp.metric,
        deltaPercent,
        effectSize,
        pValue,
        kvKey: exp.treatment.kvKey,
        appliedValue: exp.treatment.treatmentValue,
      }
      this.breakthroughs.push(bt)

      // Persist breakthrough to memory
      if (this.memory) {
        try {
          await this.memory.store({
            type: 'insight',
            content: `AI Scientist Breakthrough [${exp.track}]: ${exp.title}\n${exp.hypothesis}\nResult: +${deltaPercent.toFixed(1)}% ${exp.metric.replace(/_/g, ' ')} | p=${pValue.toFixed(3)} | d=${effectSize.toFixed(2)}`,
            metadata: { tags: ['ai-scientist', 'breakthrough', exp.track], pValue, effectSize, deltaPercent },
          })
        } catch {}
      }

      // Notify other modules
      ;(this.eventBus as any)?.emit?.({
        type: 'ai-scientist:breakthrough',
        track: exp.track,
        title: exp.title,
        metric: exp.metric,
        deltaPercent,
        effectSize,
        pValue,
      })

      this.logger.info('AI Scientist: BREAKTHROUGH', {
        track: exp.track, title: exp.title,
        metric: exp.metric, deltaPercent: deltaPercent.toFixed(1),
        pValue: pValue.toFixed(3), effectSize: effectSize.toFixed(2),
      })

      // Post breakthrough to blackboard
      this.postToBoard('system:ai-scientist', 'findings', JSON.stringify({
        type: 'experiment-conclusion',
        track: exp.track,
        title: exp.title,
        hypothesis: exp.hypothesis,
        metric: exp.metric,
        deltaPercent: Number(deltaPercent.toFixed(2)),
        pValue: Number(pValue.toFixed(4)),
        effectSize: Number(effectSize.toFixed(3)),
        applied: appliedPermanently,
      }), { tags: ['experiment', exp.track, 'breakthrough'] })

      // Notify improvement orchestrator for scenario-backed verification
      if (this.improvementOrchestrator) {
        try {
          this.improvementOrchestrator.propose({
            id: `sci-${exp.id}`,
            trigger: 'ai-scientist',
            source: 'AIScientist',
            proposalClass: 'experiment',
            hypothesis: `${exp.title}: ${exp.hypothesis}`,
            adaptation: 'parameter_tune',
            config: { track: exp.track, metric: exp.metric, kvKey: exp.treatment.kvKey, appliedValue: exp.treatment.treatmentValue, deltaPercent },
            dedupeKey: `ai-scientist:${exp.track}:${exp.metric}:${exp.treatment.kvKey}`,
            riskLevel: pValue < 0.01 ? 'low' : 'moderate',
            confidence: pValue < 0.05 ? 0.95 : pValue < 0.1 ? 0.80 : 0.60,
            evidence: {
              targetMetric: exp.metric,
              expectedDelta: Number(deltaPercent.toFixed(2)),
              observedDelta: Number(deltaPercent.toFixed(2)),
              sampleSize: exp.baselineSamples.length + exp.treatmentSamples.length,
              dataPoints: exp.baselineSamples.length + exp.treatmentSamples.length,
              pValue,
              effectSize,
              notes: [`track: ${exp.track}`, `kvKey: ${exp.treatment.kvKey}`],
            },
            verificationScenarios: ['multi-turn-context', 'thinker-injection'],
            timestamp: Date.now(),
          })
        } catch { /* best effort */ }
      }
    }

    // Always emit study-complete for Thinker
    ;(this.eventBus as any)?.emit?.({
      type: 'ai-scientist:study-complete',
      studyId: `study-${exp.id}`,
      track: exp.track,
      summary,
      outcome,
      applied: appliedPermanently,
    })
  }


  private async collectThinkerMetrics(): Promise<void> {
    if (!this.memory) return
    try {
      const history = await this.memory.kv_get<Array<{ helpful: boolean }>>('thinker:insight-history')
      if (!history || history.length < 3) return

      const recentN = history.slice(-20)
      const helpfulCount = recentN.filter(h => h.helpful).length
      this.currentTurnMetrics.thinker_helpfulness = helpfulCount / recentN.length
      this.currentTurnMetrics.thinker_insight_rate = recentN.length / 20

      // Refresh Thinker strategy cache
      const strategy = await this.memory.kv_get<Record<string, unknown>>('thinker:strategy')
      if (strategy) this.thinkerStrategy = strategy
    } catch {}
  }

  private snapshotToAgingAnalyzer(): void {
    const now = Date.now()
    for (const [metric, value] of Object.entries(this.currentTurnMetrics)) {
      if (value !== undefined) {
        this.aging.record(metric, value, now)
      }
    }
  }


  private initPersistence(): void {
    try {
      const dbPath = path.join(this.config.dataDir, 'ai_scientist.db')
      this.db = new Database(dbPath)
      this.db.pragma('journal_mode = WAL')
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS studies (
          id TEXT PRIMARY KEY,
          timestamp INTEGER NOT NULL,
          type TEXT NOT NULL,
          title TEXT NOT NULL,
          summary TEXT NOT NULL,
          findings TEXT NOT NULL,
          recommendations TEXT NOT NULL,
          confidence REAL NOT NULL,
          track TEXT,
          experiment_id TEXT,
          outcome_type TEXT,
          p_value REAL,
          effect_size REAL,
          applied INTEGER
        );
        CREATE TABLE IF NOT EXISTS breakthroughs (
          id TEXT PRIMARY KEY,
          timestamp INTEGER NOT NULL,
          track TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT NOT NULL,
          metric TEXT NOT NULL,
          delta_percent REAL NOT NULL,
          effect_size REAL NOT NULL,
          p_value REAL NOT NULL,
          kv_key TEXT NOT NULL,
          applied_value TEXT
        );
        CREATE TABLE IF NOT EXISTS aging_data (
          timestamp INTEGER NOT NULL,
          metric TEXT NOT NULL,
          value REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_aging_metric_time ON aging_data(metric, timestamp);
      `)
      this.logger.info('AI Scientist: persistence ready', { dbPath })
    } catch (err) {
      this.logger.error('AI Scientist: persistence init failed', { error: String(err) })
    }
  }

  private restoreState(): void {
    if (!this.db) return
    try {
      // Restore breakthroughs
      const rows = this.db.prepare(`SELECT * FROM breakthroughs ORDER BY timestamp ASC`).all() as any[]
      this.breakthroughs = rows.map(r => ({
        id: r.id,
        timestamp: r.timestamp,
        track: r.track,
        title: r.title,
        description: r.description,
        metric: r.metric,
        deltaPercent: r.delta_percent,
        effectSize: r.effect_size,
        pValue: r.p_value,
        kvKey: r.kv_key,
        appliedValue: r.applied_value ? JSON.parse(r.applied_value) : undefined,
      }))

      // Restore aging data
      const agingRows = this.db.prepare(`SELECT timestamp, metric, value FROM aging_data ORDER BY timestamp ASC`).all() as any[]
      this.aging.restore(agingRows.map(r => ({ timestamp: r.timestamp, metric: r.metric, value: r.value })))

      this.logger.info('AI Scientist: state restored', {
        breakthroughs: this.breakthroughs.length,
        agingPoints: agingRows.length,
      })
    } catch (err) {
      this.logger.warn('AI Scientist: state restore failed', { error: String(err) })
    }
  }

  private persistState(): void {
    if (!this.db) return
    try {
      // Persist new breakthroughs
      const insertBt = this.db.prepare(`
        INSERT OR IGNORE INTO breakthroughs
          (id, timestamp, track, title, description, metric, delta_percent, effect_size, p_value, kv_key, applied_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `)
      for (const bt of this.breakthroughs) {
        insertBt.run(bt.id, bt.timestamp, bt.track, bt.title, bt.description,
          bt.metric, bt.deltaPercent, bt.effectSize, bt.pValue, bt.kvKey,
          bt.appliedValue !== undefined ? JSON.stringify(bt.appliedValue) : null)
      }

      // Persist new aging data
      const insertAging = this.db.prepare(`INSERT INTO aging_data (timestamp, metric, value) VALUES (?, ?, ?)`)
      const exportedPoints = this.aging.export()
      // Only persist points from the last 90 days
      const cutoff = Date.now() - this.config.reportRetentionDays * 86_400_000
      const newPoints = exportedPoints.filter(p => p.timestamp > cutoff)
      // Avoid duplicates by clearing and re-inserting (acceptable for small datasets)
      this.db.exec(`DELETE FROM aging_data WHERE timestamp < ${cutoff}`)
      for (const p of newPoints.slice(-1000)) {  // limit writes per cycle
        try { insertAging.run(p.timestamp, p.metric, p.value) } catch {}
      }
    } catch (err) {
      this.logger.warn('AI Scientist: state persist failed', { error: String(err) })
    }
  }

  private async archiveStudy(study: StudyResult): Promise<void> {
    if (!this.db) return
    try {
      this.db.prepare(`
        INSERT OR REPLACE INTO studies
          (id, timestamp, type, title, summary, findings, recommendations, confidence,
           track, experiment_id, outcome_type, p_value, effect_size, applied)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        study.id, study.timestamp, study.type, study.title,
        study.summary, study.findings, study.recommendations, study.confidence,
        study.track ?? null, study.experimentId ?? null, study.outcomeType ?? null,
        study.pValue ?? null, study.effectSize ?? null,
        study.applied !== undefined ? (study.applied ? 1 : 0) : null,
      )
    } catch (err) {
      this.logger.warn('AI Scientist: study archive failed', { error: String(err) })
    }
  }


  private wireEvents(bus: IEventBus): void {
    // Collect turn latency
    ;(bus as any).on?.('turn:complete', (e: any) => {
      if (typeof e?.durationMs === 'number') {
        this.currentTurnMetrics.turn_latency_ms = e.durationMs
      }
    })

    // Collect dialectic signals
    ;(bus as any).on?.('dialectic:signal', (e: any) => {
      this.currentTurnMetrics.dialectic_signal_rate =
        (this.currentTurnMetrics.dialectic_signal_rate ?? 0) + 1
    })

    // Thinker strategy updates (keep cache fresh)
    ;(bus as any).on?.('thinker:strategy-updated', (e: any) => {
      if (e?.strategy) this.thinkerStrategy = e.strategy
    })
  }


  private async callLLM(prompt: string): Promise<string | null> {
    if (!this.memory) return null
    try {
      // Use the memory module's LLM access if available (injected via reflection)
      const llm = (this.memory as any).llm ?? (this as any).llm
      if (!llm) return null
      const response = await llm.complete(prompt, {
        model: this.config.researchModel,
        temperature: 0.3,
        maxTokens: 512,
        systemPrompt: 'You are an AI scientist. Respond only with valid JSON.',
        source: 'ai-scientist',
        trigger: 'experiment',
      })
      return response?.content ?? null
    } catch (err) {
      this.logger.debug('AI Scientist: LLM call failed', { error: String(err) })
      return null
    }
  }


  /** Backward-compat: returns recent archived studies for admin API. */
  async getRecentStudies(limit = 10): Promise<StudyResult[]> {
    if (!this.db) return []
    try {
      const rows = this.db.prepare(
        `SELECT * FROM studies ORDER BY timestamp DESC LIMIT ?`
      ).all(limit) as any[]
      return rows.map(r => ({
        id: r.id,
        timestamp: r.timestamp,
        type: r.type,
        title: r.title,
        summary: r.summary,
        findings: r.findings,
        recommendations: r.recommendations,
        confidence: r.confidence,
        track: r.track,
        experimentId: r.experiment_id,
        outcomeType: r.outcome_type,
        pValue: r.p_value,
        effectSize: r.effect_size,
        applied: r.applied !== null ? r.applied === 1 : undefined,
      }))
    } catch {
      return []
    }
  }

  /** Returns all confirmed breakthroughs in chronological order. */
  getBreakthroughs(): Breakthrough[] {
    return [...this.breakthroughs]
  }

  /** Returns the most recent aging analysis report. */
  getAgingReport(): AgingReport | null {
    return this.lastAgingReport ?? null
  }

  /** Returns experiments currently active or queued. */
  getActiveExperiments(): Experiment[] {
    return [...(this.engine?.getActive() ?? []), ...(this.engine?.getQueue() ?? [])]
  }

  /** Returns concluded experiments (most recent first). */
  getConcludedExperiments(limit = 20): Experiment[] {
    return (this.engine?.getConcluded() ?? []).slice(-limit).reverse()
  }

  /** Full research summary for Observatory and admin API. */
  getResearchSummary(): Record<string, unknown> {
    const aging = this.lastAgingReport
    return {
      totalTurns: this.totalTurns,
      breakthroughCount: this.breakthroughs.length,
      recentBreakthroughs: this.breakthroughs.slice(-3),
      activeExperiments: this.getActiveExperiments().length,
      queuedExperiments: this.engine?.getQueue().length ?? 0,
      concludedExperiments: this.engine?.getConcluded().length ?? 0,
      aging: aging ? {
        hasActiveDegradation: aging.hasActiveDegradation,
        hasActiveGrowth: aging.hasActiveGrowth,
        narrative: aging.narrative,
        trends: aging.trends,
      } : null,
      nextResearchCycleIn: Math.max(0, this.config.researchCycleTurns - this.turnsSinceResearch),
    }
  }
}


/**
 * @dep callers: thinker-adaptation.test.ts (tests/thinker-adaptation.test.ts), createIntelligence (core/intelligence/index.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export const createAIScientist = (
  logger: ILogger,
  config?: Partial<AIScientistConfig>,
): AIScientist => new AIScientist(logger, config)


interface HypothesisContext {
  track: string
  agingNarrative: string
  recentBreakthroughs: string
  recentConclusions: string
  thinkerStrategy: Record<string, unknown>
  totalTurns: number
  hasActiveDegradation: boolean
}

function buildHypothesisPrompt(ctx: HypothesisContext): string {
  return `You are an AI scientist researching self-improvement for an AI cognitive architecture named CassiCore.

Research focus for this cycle: **${ctx.track}**

## System State
- Total turns processed: ${ctx.totalTurns}
- Active degradation detected: ${ctx.hasActiveDegradation}
- Aging analysis: ${ctx.agingNarrative}

## Thinker Strategy (current)
${JSON.stringify(ctx.thinkerStrategy, null, 2)}

## Recent Breakthroughs
${ctx.recentBreakthroughs}

## Recent Experiment Outcomes
${ctx.recentConclusions}

## Task
Propose ONE specific, measurable experiment to improve CassiCore's cognitive performance.
The experiment MUST target the "${ctx.track}" research track.

Research tracks:
- **aging**: Reverse detected degradation, extend peak-performance lifetime
- **development**: Amplify learning, deepen capability across more domains
- **performance**: Direct A/B optimisation of cognitive parameters (latency, insight quality)
- **self-improvement**: Meta-research — improve the research/experiment process itself

Tunable parameters (via KV store):
- thinker:strategy → ponderInterval (int, turns between ponders, default 10)
- thinker:strategy → thinkInterval (int, turns between thinks, default 30)
- thinker:strategy → triggerSensitivity (float 0-1, event reactivity, default 0.5)
- thinker:strategy → ponderModel (string, model name)

Available metrics:
- thinker_helpfulness: fraction of insights rated helpful (higher=better)
- thinker_insight_rate: insights per turn (higher=better)
- turn_latency_ms: end-to-end turn time (lower=better)
- dialectic_signal_rate: dialectic signals per turn (higher=better)
- session_depth: avg turns per session (higher=better)

Respond ONLY with valid JSON matching exactly this schema:
{
  "title": "Short experiment title (≤60 chars)",
  "hypothesis": "If we change X from A to B, we expect Y because Z",
  "rationale": "One sentence scientific justification",
  "track": "${ctx.track}",
  "metric": "<one of the available metrics>",
  "higherIsBetter": true,
  "treatment": {
    "kvKey": "thinker:strategy",
    "parameterName": "<exact parameter name from strategy>",
    "currentValue": <current value>,
    "proposedValue": <proposed value>,
    "reloadEvent": "thinker:strategy-updated"
  }
}

Do not explain. Output only the JSON object.`
}

interface HypothesisResponse {
  title: string
  hypothesis: string
  rationale: string
  track: string
  metric: string
  higherIsBetter: boolean
  treatment: {
    kvKey: string
    parameterName: string
    currentValue: unknown
    proposedValue: unknown
    reloadEvent?: string
  }
}

function parseHypothesisJSON(raw: string): HypothesisResponse | null {
  try {
    // Strip markdown code fences if present
    const cleaned = raw.replace(/^```(?:json)?\n?/i, '').replace(/\n?```$/i, '').trim()
    const parsed = JSON.parse(cleaned)

    // Validate required fields
    if (
      typeof parsed.title === 'string' &&
      typeof parsed.hypothesis === 'string' &&
      typeof parsed.rationale === 'string' &&
      typeof parsed.track === 'string' &&
      typeof parsed.metric === 'string' &&
      typeof parsed.higherIsBetter === 'boolean' &&
      parsed.treatment?.kvKey &&
      parsed.treatment?.parameterName
    ) {
      return parsed as HypothesisResponse
    }
    return null
  } catch {
    return null
  }
}
