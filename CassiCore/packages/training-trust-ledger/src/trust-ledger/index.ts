/**
 * Trust Ledger — Per-domain Bayesian trust scoring.
 *
 * Priority: 80 (runs early — trust scores are consulted by Permission Oracle)
 *
 * The Trust Ledger maintains a Beta-Binomial model for each trust domain.
 * It aggregates evidence from:
 *   - OutcomeTracker feedback signals (positive/negative user feedback)
 *   - Tool execution outcomes (success/failure rates)
 *   - Consequence accuracy (how well did we predict the actual outcome?)
 *   - Explicit human trust signals (approval/rejection patterns)
 *
 * Trust is domain-specific: being good at file reads doesn't earn trust
 * for shell execution. Each domain has independent alpha/beta parameters.
 *
 * Events emitted:
 *   - trust:score-updated — whenever a domain's trust score changes
 *   - trust:domain-created — when a new domain is initialized
 *   - trust:decay-applied — when time-based decay reduces trust
 *   - trust:outcome-recorded — when evidence is ingested
 *
 * Events consumed:
 *   - verification:trust-updated — from existing self-verification system
 *   - permission:human-response — human approval/rejection as evidence
 */

import { TTLCache } from '../vendor/core/utils/ttl-cache.js'
import { BaseCognitiveModule } from '@cassicore/foundation'

import {
  DEFAULT_TRUST_LEDGER_CONFIG,
  betaMean,
  betaConfidence,
  trustToAutonomyLevel,
} from './types.js'

import type {
  TrustDomain,
  TrustScore,
  TrustEvidence,
  TrustLedgerConfig,
  TrustSummary,
  AutonomyLevel,
} from './types.js'
import type { ILogger } from '@cassicore/foundation'
import type Database from 'better-sqlite3'




export class TrustLedger extends BaseCognitiveModule {
  readonly name = 'trust-ledger'
  readonly priority = 80

  private cfg: TrustLedgerConfig = { ...DEFAULT_TRUST_LEDGER_CONFIG }
  private db?: Database.Database

  /** In-memory cache of trust scores (authoritative source is DB) */
  private scores: TTLCache<TrustDomain, TrustScore> = new TTLCache({ maxSize: 200, ttlMs: 5 * 60 * 1000 }) // 5 min TTL

  /** Stats tracking */
  private totalEvidenceIngested = 0
  private totalDecaysApplied = 0

  // Instead of hitting SQLite on every tool call, buffer dirty domains and
  // flush periodically. This reduces DB writes from N-per-turn to 1-per-flush.
  private dirtyDomains = new Set<TrustDomain>()
  private flushTimer?: ReturnType<typeof setInterval>
  private static readonly FLUSH_INTERVAL_MS = 30_000  // 30 seconds
  private static readonly FLUSH_THRESHOLD = 50        // Flush early if this many evidence items buffered

  constructor(logger: ILogger) {
    super(logger)
    this.logger = logger.child('trust-ledger')
  }


  override async init(): Promise<void> {
    await super.init()

    // Load config overrides
    if (this.config) {
      try {
        const cfgOverrides = this.config.get<Partial<TrustLedgerConfig>>('intelligence.trustLedger')
        if (cfgOverrides) {
          this.cfg = { ...DEFAULT_TRUST_LEDGER_CONFIG, ...cfgOverrides }
        }
      } catch {
        // Non-fatal: use defaults
      }
    }

    // Initialize database if Memory module provides one
    if (this.memory && typeof (this.memory as any).getDb === 'function') {
      this.db = (this.memory as any).getDb() as Database.Database
      if (this.db) {
        this.initSchema()
        this.loadScoresFromDb()
      }
    }
  }

  override async start(): Promise<void> {
    await super.start()

    // Start periodic flush timer for batched DB persistence
    this.flushTimer = setInterval(() => this.flushDirtyScores(), TrustLedger.FLUSH_INTERVAL_MS)
    this.flushTimer.unref() // Don't keep the process alive for this

    this.logger.info('Trust Ledger started', {
      domains: this.scores.size,
      config: {
        priorAlpha: this.cfg.priorAlpha,
        priorBeta: this.cfg.priorBeta,
        decayPerHour: this.cfg.decayFactorPerHour,
      },
    })
  }

  protected override registerSubscriptions(): void {
    // Listen for human approval/rejection as strong trust evidence
    this.subscribe('permission:human-response', (e) => {
      // Determine domain from tool name (will be set by Permission Oracle)
      const domain = (e as any).domain || 'shell-execution'
      this.recordEvidence({
        domain,
        success: e.approved,
        weight: 2.0, // Human signals are strong evidence
        source: 'human-approval',
        description: e.approved
          ? `Human approved ${e.toolName}`
          : `Human rejected ${e.toolName}`,
        sessionId: e.sessionId,
        timestamp: Date.now(),
      })
    })

    // Listen for existing trust updates from self-verification
    this.subscribe('verification:trust-updated', (e) => {
      // Map source module to domain (rough mapping)
      const domain = this.moduleToDefaultDomain(e.sourceModule)
      const success = e.newTrust > e.oldTrust
      this.recordEvidence({
        domain,
        success,
        weight: 0.5, // Indirect signal
        source: 'self-verification',
        description: `${e.sourceModule} trust ${e.oldTrust.toFixed(2)} → ${e.newTrust.toFixed(2)}`,
        timestamp: Date.now(),
      })
    })
  }


  /**
   * Record a piece of evidence that updates a domain's trust score.
   */
  recordEvidence(evidence: TrustEvidence): void {
    const { domain, success, weight, consequenceAccuracy } = evidence

    // Get or create domain score
    let score = this.scores.get(domain)
    if (!score) {
      score = this.createDomain(domain)
    }

    const oldScore = score.score

    // Clamp weight
    const clampedWeight = Math.min(evidence.weight, this.cfg.maxEvidenceWeight)

    // Apply consequence accuracy bonus/penalty
    let effectiveWeight = clampedWeight
    if (consequenceAccuracy !== undefined) {
      // Good prediction → bonus evidence weight; bad prediction → penalty
      effectiveWeight *= (1.0 + (consequenceAccuracy - 0.5) * this.cfg.consequenceAccuracyWeight)
    }

    // Update Beta distribution parameters
    if (success) {
      score.alpha += effectiveWeight
    } else {
      score.beta += effectiveWeight
    }

    // Recompute derived values
    score.score = betaMean(score.alpha, score.beta)
    score.confidence = betaConfidence(score.alpha, score.beta)
    score.evidenceCount = (score.alpha - this.cfg.priorAlpha) + (score.beta - this.cfg.priorBeta)
    score.lastUpdatedAt = Date.now()
    score.lastEvidenceAt = Date.now()

    this.scores.set(domain, score)
    this.totalEvidenceIngested++

    // Mark domain as dirty for batched persistence (replaces per-call DB write)
    this.dirtyDomains.add(domain)

    // Flush early if buffer is large (prevents stale data on high-throughput bursts)
    if (this.dirtyDomains.size >= TrustLedger.FLUSH_THRESHOLD) {
      this.flushDirtyScores()
    }

    // Emit events
    const delta = score.score - oldScore
    this.emit({
      type: 'trust:score-updated',
      domain,
      oldScore,
      newScore: score.score,
      delta,
      reason: evidence.description,
      evidence: `${evidence.source}: ${success ? 'success' : 'failure'} (w=${effectiveWeight.toFixed(2)})`,
      timestamp: new Date(),
    })

    this.emit({
      type: 'trust:outcome-recorded',
      domain,
      action: evidence.description,
      success,
      consequenceAccuracy: consequenceAccuracy ?? 0,
      timestamp: new Date(),
    })

    this.logger.debug('Evidence recorded', {
      domain,
      success,
      weight: effectiveWeight.toFixed(2),
      oldScore: oldScore.toFixed(3),
      newScore: score.score.toFixed(3),
      alpha: score.alpha.toFixed(1),
      beta: score.beta.toFixed(1),
    })
  }

  /**
   * Get the trust score for a specific domain.
   * Returns undefined if the domain has never been scored.
   */
  getDomainScore(domain: TrustDomain): TrustScore | undefined {
    const score = this.scores.get(domain)
    if (!score) return undefined

    // Apply time decay if needed
    this.maybeApplyDecay(score)
    return { ...score }
  }

  /**
   * Get the trust score for a domain, creating it with prior if it doesn't exist.
   */
  getOrCreateDomainScore(domain: TrustDomain): TrustScore {
    let score = this.scores.get(domain)
    if (!score) {
      score = this.createDomain(domain)
    }
    this.maybeApplyDecay(score)
    return { ...score }
  }

  /**
   * Get a complete trust summary across all domains.
   */
  getSummary(): TrustSummary {
    // Apply decay to all domains
    for (const [, score] of this.scores.entries()) {
      this.maybeApplyDecay(score)
    }

    let totalWeightedScore = 0
    let totalWeight = 0
    let strongest: { domain: TrustDomain; score: number } | undefined
    let weakest: { domain: TrustDomain; score: number } | undefined
    let totalEvidence = 0

    for (const [domain, score] of this.scores.entries()) {
      const weight = score.evidenceCount + 1 // +1 to avoid zero-weight
      totalWeightedScore += score.score * weight
      totalWeight += weight
      totalEvidence += score.evidenceCount

      if (!strongest || score.score > strongest.score) {
        strongest = { domain, score: score.score }
      }
      if (!weakest || score.score < weakest.score) {
        weakest = { domain, score: score.score }
      }
    }

    const overallScore = totalWeight > 0 ? totalWeightedScore / totalWeight : 0.5

    return {
      domains: new Map(this.scores),
      overallScore,
      autonomyLevel: trustToAutonomyLevel(overallScore),
      totalEvidence,
      strongestDomain: strongest,
      weakestDomain: weakest,
    }
  }

  /**
   * Get the current autonomy level.
   */
  getAutonomyLevel(): AutonomyLevel {
    return this.getSummary().autonomyLevel
  }

  /**
   * Get stats for the Trust Ledger.
   */
  getStats(): {
    domainCount: number
    totalEvidence: number
    totalDecays: number
    overallScore: number
    autonomyLevel: AutonomyLevel
  } {
    const summary = this.getSummary()
    return {
      domainCount: this.scores.size,
      totalEvidence: this.totalEvidenceIngested,
      totalDecays: this.totalDecaysApplied,
      overallScore: summary.overallScore,
      autonomyLevel: summary.autonomyLevel,
    }
  }


  /**
   * Flush all dirty trust scores to SQLite in one pass.
   * Called periodically by the flush timer and on shutdown.
   */
  private flushDirtyScores(): void {
    if (this.dirtyDomains.size === 0) return

    const flushed = this.dirtyDomains.size
    for (const domain of this.dirtyDomains) {
      const score = this.scores.get(domain)
      if (score) this.persistScore(score)
    }
    this.dirtyDomains.clear()

    this.logger.debug('Trust scores flushed to DB', { domains: flushed })
  }

  /**
   * Stop the flush timer and persist any remaining dirty scores.
   * Should be called on daemon shutdown.
   */
  async shutdown(): Promise<void> {
    if (this.flushTimer) {
      clearInterval(this.flushTimer)
      this.flushTimer = undefined
    }
    // Final flush to ensure no evidence is lost
    this.flushDirtyScores()
  }


  /**
   * Create a new trust domain with uninformative prior.
   */
  private createDomain(domain: TrustDomain): TrustScore {
    const now = Date.now()
    const score: TrustScore = {
      domain,
      alpha: this.cfg.priorAlpha,
      beta: this.cfg.priorBeta,
      score: betaMean(this.cfg.priorAlpha, this.cfg.priorBeta),
      confidence: betaConfidence(this.cfg.priorAlpha, this.cfg.priorBeta),
      evidenceCount: 0,
      lastUpdatedAt: now,
      lastEvidenceAt: now,
      lastDecayAt: now,
    }

    this.scores.set(domain, score)
    this.persistScore(score)

    this.emit({
      type: 'trust:domain-created',
      domain,
      initialScore: score.score,
      timestamp: new Date(),
    })

    this.logger.info('New trust domain created', { domain, score: score.score })
    return score
  }

  /**
   * Apply time-based decay to a trust score.
   * Decay pulls the score toward 0.5 (uninformative prior) over time.
   * This prevents stale evidence from maintaining high/low trust indefinitely.
   */
  private maybeApplyDecay(score: TrustScore): void {
    const now = Date.now()
    const elapsed = now - score.lastDecayAt

    if (elapsed < this.cfg.minDecayIntervalMs) return

    const hours = elapsed / (60 * 60 * 1000)
    const decayFactor = Math.pow(this.cfg.decayFactorPerHour, hours)

    const oldScore = score.score

    // Decay alpha and beta toward prior, proportionally
    const excessAlpha = score.alpha - this.cfg.priorAlpha
    const excessBeta = score.beta - this.cfg.priorBeta

    score.alpha = this.cfg.priorAlpha + excessAlpha * decayFactor
    score.beta = this.cfg.priorBeta + excessBeta * decayFactor

    // Recompute
    score.score = betaMean(score.alpha, score.beta)
    score.confidence = betaConfidence(score.alpha, score.beta)
    score.lastDecayAt = now

    this.totalDecaysApplied++

    if (Math.abs(score.score - oldScore) > 0.001) {
      // Mark for batched persistence since decay changed the score
      this.dirtyDomains.add(score.domain)

      this.emit({
        type: 'trust:decay-applied',
        domain: score.domain,
        oldScore,
        newScore: score.score,
        decayFactor,
        timestamp: new Date(),
      })
    }
  }

  /**
   * Map intelligence module names to default trust domains.
   */
  private moduleToDefaultDomain(moduleName: string): TrustDomain {
    const mapping: Record<string, TrustDomain> = {
      'thinker': 'agent-management',
      'optimizer': 'agent-management',
      'dialectic': 'agent-management',
      'subconscious': 'agent-management',
      'self-healer': 'system-config',
      'ai-engineer': 'system-config',
    }
    return mapping[moduleName] ?? 'agent-management'
  }


  private initSchema(): void {
    if (!this.db) return

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS trust_scores (
        domain TEXT PRIMARY KEY,
        alpha REAL NOT NULL,
        beta REAL NOT NULL,
        score REAL NOT NULL,
        confidence REAL NOT NULL,
        evidence_count REAL NOT NULL DEFAULT 0,
        last_updated_at INTEGER NOT NULL,
        last_evidence_at INTEGER NOT NULL,
        last_decay_at INTEGER NOT NULL
      );

      CREATE TABLE IF NOT EXISTS trust_evidence_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        success INTEGER NOT NULL,
        weight REAL NOT NULL,
        source TEXT NOT NULL,
        description TEXT NOT NULL,
        consequence_accuracy REAL,
        session_id TEXT,
        timestamp INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_trust_evidence_domain ON trust_evidence_log(domain);
      CREATE INDEX IF NOT EXISTS idx_trust_evidence_timestamp ON trust_evidence_log(timestamp);
    `)
  }

  private loadScoresFromDb(): void {
    if (!this.db) return

    try {
      const rows = this.db.prepare('SELECT * FROM trust_scores').all() as any[]
      for (const row of rows) {
        this.scores.set(row.domain, {
          domain: row.domain,
          alpha: row.alpha,
          beta: row.beta,
          score: row.score,
          confidence: row.confidence,
          evidenceCount: row.evidence_count,
          lastUpdatedAt: row.last_updated_at,
          lastEvidenceAt: row.last_evidence_at,
          lastDecayAt: row.last_decay_at,
        })
      }
      this.logger.info('Loaded trust scores from database', { domains: rows.length })
    } catch (err) {
      this.logger.warn('Failed to load trust scores from database', { error: String(err) })
    }
  }

  private persistScore(score: TrustScore): void {
    if (!this.db) return

    try {
      this.db.prepare(`
        INSERT OR REPLACE INTO trust_scores
          (domain, alpha, beta, score, confidence, evidence_count, last_updated_at, last_evidence_at, last_decay_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        score.domain,
        score.alpha,
        score.beta,
        score.score,
        score.confidence,
        score.evidenceCount,
        score.lastUpdatedAt,
        score.lastEvidenceAt,
        score.lastDecayAt,
      )
    } catch (err) {
      this.logger.warn('Failed to persist trust score', { domain: score.domain, error: String(err) })
    }
  }


}


export const MODULE_CLASS = TrustLedger


export function createTrustLedger(logger: ILogger): TrustLedger {
  return new TrustLedger(logger)
}
