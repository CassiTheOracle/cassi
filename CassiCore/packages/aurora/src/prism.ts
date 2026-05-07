/**
 * Aurora Prism (B8) — Spectral counterfactual accumulation.
 *
 * The Prism is a single, persistent multi-spectral graph that records
 * B7 counterfactual fork explorations as colored spectral deposits.
 * Each fork emits one resolved color (its effective affect at observation
 * time) plus a list of activated nodes; deposits accumulate as weighted
 * spectra per `(concept_id, color)` with hydration-time exponential decay.
 *
 * Phase P.1 ships spectral accumulation + read affordances. White
 * standing (P.2), Reverie synthesis (P.3), and gap-driven exploration
 * as a generative loop (P.4) build on this foundation.
 *
 * Storage: own SQLite connection to `aurora.db` (or any path passed in).
 * Two-connection coexistence with `AuroraPersistence` is well-defined
 * under WAL mode and serves as the integration story until AP is wired
 * at the boot site.
 *
 * See: docs/design/aurora-prism.md
 */

import path from 'node:path'
import fs from 'node:fs'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { AffectLabel } from '../mnemic-field/types.js'
import type { ForkContribution, Perturbation } from './counterfactual-engine.js'


export type AffectColor = AffectLabel

/**
 * Locally-listed enumeration of all AffectColors. Mirrors the union in
 * `mnemic-field/types.ts::AffectLabel`. If new labels are added there,
 * update this array — there is no runtime validation that catches drift.
 */
export const ALL_AFFECT_COLORS: AffectColor[] = [
  'excited', 'delighted', 'engaged',
  'content', 'warm', 'calm',
  'frustrated', 'alarmed', 'uneasy',
  'melancholy', 'fatigued', 'neutral',
]

export interface PrismConfig {
  /** Spectrum decay half-life in days. Default: 21. */
  decayHalfLifeDays?: number
  /** Sub-threshold weight floor; values below this are skipped on read. Default: 0.05. */
  minThreshold?: number
}

export interface ColorWeight {
  weight: number
  /** ISO 8601 of most recent reinforcement (or initial deposit) for this (concept, color). */
  lastSeen: string
  /** Number of distinct contributions that built this weight. */
  contributionCount: number
}

export type Spectrum = Map<AffectColor, ColorWeight>

export interface PrismNode {
  conceptId: string
  spectrum: Spectrum
  totalWeight: number
  /** Shannon-entropy-based balance score in [0, 1]; 1.0 = uniform across all 12 colors. */
  balanceScore: number
  /** True if this node was introduced via a B7 `add_nodes` perturbation and has no live-claustrum counterpart. */
  forkOnly: boolean
  createdAt: string
  updatedAt: string
}

export interface ForkSuggestion {
  fork: string
  perturbation: { type: 'affect'; affect: AffectColor }
}

export interface GapReport {
  conceptId: string
  explored: AffectColor[]
  missing: AffectColor[]
  suggestion: ForkSuggestion | null
}


const DEFAULT_HALF_LIFE_DAYS = 21
const DEFAULT_MIN_THRESHOLD = 0.05
const MS_PER_DAY = 86_400_000


export const PRISM_SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS prism_nodes (
    concept_id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_deposit_at TEXT NOT NULL,
    total_weight REAL NOT NULL DEFAULT 0,
    fork_only INTEGER NOT NULL DEFAULT 0,
    metadata TEXT DEFAULT '{}'
  );

  CREATE TABLE IF NOT EXISTS prism_spectra (
    concept_id TEXT NOT NULL,
    color TEXT NOT NULL,
    weight REAL NOT NULL,
    last_seen_at TEXT NOT NULL,
    contribution_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (concept_id, color)
  );

  CREATE TABLE IF NOT EXISTS prism_fork_contributions (
    fork_id TEXT PRIMARY KEY,
    color TEXT NOT NULL,
    valence REAL,
    arousal REAL,
    perturbation_kinds TEXT NOT NULL DEFAULT '[]',
    perturbation_json TEXT NOT NULL DEFAULT '[]',
    observed_at TEXT NOT NULL,
    session_id TEXT,
    metadata TEXT DEFAULT '{}'
  );

  CREATE INDEX IF NOT EXISTS idx_prism_fork_contributions_observed_at
    ON prism_fork_contributions(observed_at);
`


export class Prism {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly halfLifeMs: number
  private readonly minThreshold: number
  private readonly dbPath: string
  private closed = false

  private readonly upsertNode: Database.Statement
  private readonly upsertSpectrumExisting: Database.Statement
  private readonly insertSpectrumNew: Database.Statement
  private readonly selectSpectrum: Database.Statement
  private readonly insertContribution: Database.Statement
  private readonly addToTotal: Database.Statement
  private readonly depositTx: (c: ForkContribution, sessionId: string | null) => void

  constructor(dbPath: string, logger: ILogger, config?: PrismConfig) {
    this.logger = logger.child ? logger.child('prism') : logger
    this.halfLifeMs = (config?.decayHalfLifeDays ?? DEFAULT_HALF_LIFE_DAYS) * MS_PER_DAY
    this.minThreshold = config?.minThreshold ?? DEFAULT_MIN_THRESHOLD
    this.dbPath = dbPath

    const dir = path.dirname(dbPath)
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('busy_timeout = 5000')
    this.db.pragma('synchronous = NORMAL')
    this.db.exec(PRISM_SCHEMA_SQL)

    this.upsertNode = this.db.prepare(`
      INSERT INTO prism_nodes (concept_id, first_seen_at, last_deposit_at, total_weight, fork_only)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT (concept_id) DO UPDATE SET
        last_deposit_at = excluded.last_deposit_at,
        total_weight = total_weight + excluded.total_weight,
        fork_only = MAX(fork_only, excluded.fork_only)
    `)
    this.selectSpectrum = this.db.prepare(`
      SELECT color, weight, last_seen_at, contribution_count
      FROM prism_spectra WHERE concept_id = ?
    `)
    this.upsertSpectrumExisting = this.db.prepare(`
      UPDATE prism_spectra
      SET weight = ?, last_seen_at = ?, contribution_count = contribution_count + 1
      WHERE concept_id = ? AND color = ?
    `)
    this.insertSpectrumNew = this.db.prepare(`
      INSERT INTO prism_spectra (concept_id, color, weight, last_seen_at, contribution_count)
      VALUES (?, ?, ?, ?, 1)
    `)
    this.insertContribution = this.db.prepare(`
      INSERT INTO prism_fork_contributions
        (fork_id, color, valence, arousal, perturbation_kinds, perturbation_json, observed_at, session_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT (fork_id) DO UPDATE SET
        color = excluded.color,
        valence = excluded.valence,
        arousal = excluded.arousal,
        perturbation_kinds = excluded.perturbation_kinds,
        perturbation_json = excluded.perturbation_json,
        observed_at = excluded.observed_at,
        session_id = excluded.session_id
    `)
    this.addToTotal = this.db.prepare(`
      UPDATE prism_nodes SET total_weight = total_weight + ? WHERE concept_id = ?
    `)

    const selectExistingSpectrum = this.db.prepare(`
      SELECT weight, last_seen_at FROM prism_spectra
      WHERE concept_id = ? AND color = ?
    `)

    this.depositTx = this.db.transaction((c: ForkContribution, sessionId: string | null) => {
      const observedAtIso = new Date(c.observedAt).toISOString()
      const kinds = uniqueKinds(c.perturbations)
      this.insertContribution.run(
        c.forkId,
        c.color,
        c.effectiveAffect.valence,
        c.effectiveAffect.arousal,
        JSON.stringify(kinds),
        JSON.stringify(c.perturbations),
        observedAtIso,
        sessionId,
      )

      for (const node of c.contributedNodes) {
        if (node.salience <= 0) continue

        this.upsertNode.run(
          node.nodeId,
          observedAtIso,
          observedAtIso,
          0,
          node.forkOnly ? 1 : 0,
        )

        const existing = selectExistingSpectrum.get(node.nodeId, c.color) as
          | { weight: number; last_seen_at: string }
          | undefined

        let depositedWeight = node.salience
        if (existing) {
          const decayedPrior = decay(
            existing.weight,
            Date.parse(existing.last_seen_at),
            c.observedAt,
            this.halfLifeMs,
          )
          const newWeight = decayedPrior + node.salience
          this.upsertSpectrumExisting.run(newWeight, observedAtIso, node.nodeId, c.color)
          depositedWeight = newWeight - existing.weight
        } else {
          this.insertSpectrumNew.run(node.nodeId, c.color, node.salience, observedAtIso)
        }

        this.addToTotal.run(depositedWeight, node.nodeId)
      }
    })

    this.logger.info('Prism initialized', {
      dbPath,
      halfLifeDays: this.halfLifeMs / MS_PER_DAY,
      minThreshold: this.minThreshold,
    })
  }

  /**
   * Ingest a fork contribution: write the contribution row, upsert each
   * activated node, and accumulate per-color spectra (decay-on-write).
   */
  deposit(contribution: ForkContribution, sessionId: string | null = null): void {
    if (this.closed) {
      this.logger.warn('Prism deposit on closed instance', { forkId: contribution.forkId })
      return
    }
    this.depositTx(contribution, sessionId)
    this.logger.debug('Prism deposit', {
      forkId: contribution.forkId,
      color: contribution.color,
      nodeCount: contribution.contributedNodes.length,
    })
  }

  /**
   * Read the spectrum for a node, applying per-color decay against
   * `last_seen_at`. Sub-threshold colors are omitted.
   */
  spectrumAt(conceptId: string, now: number = Date.now()): Spectrum {
    if (this.closed) return new Map()
    const rows = this.selectSpectrum.all(conceptId) as Array<{
      color: string
      weight: number
      last_seen_at: string
      contribution_count: number
    }>
    const out: Spectrum = new Map()
    for (const row of rows) {
      const decayed = decay(row.weight, Date.parse(row.last_seen_at), now, this.halfLifeMs)
      if (decayed < this.minThreshold) continue
      out.set(row.color as AffectColor, {
        weight: decayed,
        lastSeen: row.last_seen_at,
        contributionCount: row.contribution_count,
      })
    }
    return out
  }

  /**
   * Return nodes whose decayed spectra reach `threshold` balance with at
   * least `minTotalWeight` total decayed weight. "Near-white" candidates.
   */
  balanced(threshold = 0.7, minTotalWeight = 10, now: number = Date.now()): PrismNode[] {
    return this.scanNodes(now).filter(n =>
      n.balanceScore >= threshold && n.totalWeight >= minTotalWeight
    )
  }

  /** Inverse of `balanced` — nodes dominated by a single color. */
  starkConcepts(maxBalance = 0.3, minTotalWeight = 1, now: number = Date.now()): PrismNode[] {
    return this.scanNodes(now).filter(n =>
      n.balanceScore <= maxBalance && n.totalWeight >= minTotalWeight
    )
  }

  /**
   * Report the explored vs. missing colors for a single node. P.1 surfaces
   * this as a read affordance; P.4 will turn the suggestion into a generative
   * fork loop.
   */
  gapReport(conceptId: string, now: number = Date.now()): GapReport {
    const spectrum = this.spectrumAt(conceptId, now)
    const explored: AffectColor[] = []
    const missing: AffectColor[] = []
    for (const c of ALL_AFFECT_COLORS) {
      if (spectrum.has(c)) explored.push(c)
      else missing.push(c)
    }
    const suggestion: ForkSuggestion | null = missing.length > 0
      ? { fork: conceptId, perturbation: { type: 'affect', affect: missing[0] } }
      : null
    return { conceptId, explored, missing, suggestion }
  }

  /**
   * Aggregate per-color exposure across the whole Prism. Useful for
   * dashboards and the projection text-block status line.
   */
  totalSpectrum(now: number = Date.now()): Map<AffectColor, number> {
    if (this.closed) return new Map()
    const rows = this.db.prepare(`
      SELECT color, weight, last_seen_at FROM prism_spectra
    `).all() as Array<{ color: string; weight: number; last_seen_at: string }>
    const out = new Map<AffectColor, number>()
    for (const row of rows) {
      const decayed = decay(row.weight, Date.parse(row.last_seen_at), now, this.halfLifeMs)
      if (decayed < this.minThreshold) continue
      const prev = out.get(row.color as AffectColor) ?? 0
      out.set(row.color as AffectColor, prev + decayed)
    }
    return out
  }

  /** Total node count (raw, not decay-aware). Cheap; for status surfaces. */
  nodeCount(): number {
    if (this.closed) return 0
    const row = this.db.prepare(`SELECT COUNT(*) AS n FROM prism_nodes`).get() as { n: number }
    return row.n
  }

  /**
   * B8.P.4 — projection-ready summary for Aurora's text projection.
   *
   * Returns the top-N stark concepts (single-color-dominated) plus
   * total-color exposure breakdown and node count. Stark concepts
   * surface in the projection as "gap candidates" — concepts the
   * model has only seen in one affective register and could be
   * usefully explored under a contrasting color.
   *
   * Sorted by `totalWeight` descending so the most-exposed stark
   * concepts come first (those most worth a counterfactual
   * exploration via B7).
   */
  getProjectionSummary(opts: { topN?: number; now?: number } = {}): {
    nodeCount: number
    totalSpectrum: Map<AffectColor, number>
    starkConcepts: Array<{
      conceptId: string
      dominantColor: AffectColor | null
      missing: AffectColor[]
      totalWeight: number
      balanceScore: number
    }>
  } {
    const topN = opts.topN ?? 5
    const now = opts.now ?? Date.now()
    if (this.closed) {
      return { nodeCount: 0, totalSpectrum: new Map(), starkConcepts: [] }
    }
    const stark = this.starkConcepts(0.4, 0.1, now)
      .sort((a, b) => b.totalWeight - a.totalWeight)
      .slice(0, topN)
    const summarized = stark.map(node => {
      // Find dominant color (highest decayed weight) and missing colors.
      let dominant: AffectColor | null = null
      let dominantWeight = -Infinity
      for (const [color, w] of node.spectrum) {
        if (w.weight > dominantWeight) {
          dominantWeight = w.weight
          dominant = color
        }
      }
      const missing: AffectColor[] = []
      for (const c of ALL_AFFECT_COLORS) {
        if (!node.spectrum.has(c)) missing.push(c)
      }
      return {
        conceptId: node.conceptId,
        dominantColor: dominant,
        missing,
        totalWeight: node.totalWeight,
        balanceScore: node.balanceScore,
      }
    })
    return {
      nodeCount: this.nodeCount(),
      totalSpectrum: this.totalSpectrum(now),
      starkConcepts: summarized,
    }
  }

  close(): void {
    if (this.closed) return
    this.db.close()
    this.closed = true
    this.logger.debug('Prism closed', { dbPath: this.dbPath })
  }

  private scanNodes(now: number): PrismNode[] {
    if (this.closed) return []
    const nodeRows = this.db.prepare(`
      SELECT concept_id, first_seen_at, last_deposit_at, fork_only FROM prism_nodes
    `).all() as Array<{
      concept_id: string
      first_seen_at: string
      last_deposit_at: string
      fork_only: number
    }>
    const out: PrismNode[] = []
    for (const row of nodeRows) {
      const spectrum = this.spectrumAt(row.concept_id, now)
      if (spectrum.size === 0) continue
      const totalWeight = sumSpectrum(spectrum)
      out.push({
        conceptId: row.concept_id,
        spectrum,
        totalWeight,
        balanceScore: computeBalance(spectrum, totalWeight),
        forkOnly: row.fork_only === 1,
        createdAt: row.first_seen_at,
        updatedAt: row.last_deposit_at,
      })
    }
    return out
  }
}


function decay(value: number, lastMs: number, nowMs: number, halfLifeMs: number): number {
  const elapsed = Math.max(0, nowMs - lastMs)
  return value * Math.exp(-elapsed / halfLifeMs * Math.LN2)
}

function uniqueKinds(perturbations: Perturbation[]): string[] {
  const seen = new Set<string>()
  for (const p of perturbations) seen.add(p.type)
  return [...seen]
}

function sumSpectrum(spectrum: Spectrum): number {
  let s = 0
  for (const c of spectrum.values()) s += c.weight
  return s
}

function computeBalance(spectrum: Spectrum, total: number): number {
  if (total <= 0 || spectrum.size === 0) return 0
  let entropy = 0
  for (const c of spectrum.values()) {
    const p = c.weight / total
    if (p > 0) entropy -= p * Math.log(p)
  }
  return entropy / Math.log(ALL_AFFECT_COLORS.length)
}
