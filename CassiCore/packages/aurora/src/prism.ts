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

/**
 * B8.P.2 — criteria for white standing. Defaults are conservative
 * (spec §5 + W2): high balance, substantial weight, broad color
 * coverage, witnesses spread temporally + structurally.
 */
export interface WhitePromotionCriteria {
  /** Min balance score in [0, 1]. Default 0.85. */
  minBalance: number
  /** Min total decayed weight summed across all colors. Default 30. */
  minTotalWeight: number
  /** Min number of distinct colors with any weight. Default 6 (of 12). */
  minColors: number
  /** Whether to exclude already-contested nodes. Default true. */
  contestedExcluded: boolean
  /** Min days between earliest and latest witness. W3 temporal spread guard. Default 7. */
  witnessTemporalSpreadDaysMin: number
  /** Min distinct perturbation kinds across witnesses. W3 structural diversity. Default 3. */
  witnessKindDiversityMin: number
}

export const DEFAULT_WHITE_CRITERIA: WhitePromotionCriteria = {
  minBalance: 0.85,
  minTotalWeight: 30,
  minColors: 6,
  contestedExcluded: true,
  witnessTemporalSpreadDaysMin: 7,
  witnessKindDiversityMin: 3,
}

/**
 * B8.P.2 — record of a promotion-to-white event. Demotion preserves
 * the record (sets demoted_at + demoted_reason) — white is reversible
 * but the history persists for audit (W4).
 */
export interface WhiteRecord {
  conceptId: string
  promotedAt: string
  promotedBy: 'cassi' | 'operator'
  /** Fork ids whose contributions counted as witnesses for promotion. */
  witness: string[]
  /** The criteria values that were met at promotion time, for audit. */
  criteriaSnapshot: {
    balance: number
    totalWeight: number
    colorCount: number
    witnessTemporalSpreadDays: number
    witnessKindDiversity: number
  }
  demotedAt: string | null
  demotedReason: 'contested' | 'decay' | 'manual' | null
  contestedSince: string | null
  metadata: Record<string, unknown>
}

/**
 * B8.P.3 — Reverie-synthesized invariant engram payload. Lands in
 * Mnemic Field as `engramType: 'synthesized_invariant'`. Citation
 * chain: invariant → witness fork ids → trace records (B3).
 *
 * `affectSignature: 'balanced'` for white-standing concepts;
 * degrades to a single AffectColor when synthesized on a non-white
 * (lower-confidence) node — though gatherSynthesisInputs throws on
 * non-white inputs by default.
 */
export interface SynthesizedInvariant {
  engramType: 'synthesized_invariant'
  concept: string
  /** Text claims that hold across all colors in the spectrum. */
  invariants: string[]
  /** Affect colors present in the spectrum at synthesis time. */
  spectralProvenance: AffectColor[]
  /** Witness fork ids whose contributions sourced this invariant. */
  sourceContributions: string[]
  /** 'balanced' for white nodes; otherwise the dominant color. */
  affectSignature: 'balanced' | AffectColor
  /** Reverie's stated confidence in [0, 1]. */
  confidence: number
  /** Concept id for cross-engram lookup; matches `concept`. */
  conceptId: string
  /** ISO timestamp the synthesis was produced. */
  synthesizedAt: string
}

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

  -- B8.P.2 white-standing tracking. Promotion is rare + recorded;
  -- demotion is automatic on contest. demoted_at NULL → currently white.
  CREATE TABLE IF NOT EXISTS prism_white_records (
    concept_id        TEXT PRIMARY KEY,
    promoted_at       TEXT NOT NULL,
    promoted_by       TEXT NOT NULL DEFAULT 'cassi',
    witness_json      TEXT NOT NULL,
    criteria_json     TEXT NOT NULL,
    demoted_at        TEXT,
    demoted_reason    TEXT,
    contested_since   TEXT,
    metadata          TEXT NOT NULL DEFAULT '{}'
  );

  CREATE INDEX IF NOT EXISTS idx_prism_white_active
    ON prism_white_records(demoted_at) WHERE demoted_at IS NULL;
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
   * B8.P.2 — list candidates eligible for white promotion. Scans
   * non-promoted nodes that meet the criteria's spectral thresholds
   * (balance, total weight, color count). Witness validation
   * (temporal spread + kind diversity) is checked at promotion time,
   * not here, so candidates may still fail promotion if their
   * contribution log is too narrow.
   */
  whiteCandidates(criteria: Partial<WhitePromotionCriteria> = {}, now: number = Date.now()): PrismNode[] {
    if (this.closed) return []
    const c = { ...DEFAULT_WHITE_CRITERIA, ...criteria }
    const promoted = new Set(
      (this.db.prepare(`SELECT concept_id FROM prism_white_records WHERE demoted_at IS NULL`)
        .all() as Array<{ concept_id: string }>).map(r => r.concept_id),
    )
    const out: PrismNode[] = []
    for (const node of this.scanNodes(now)) {
      if (promoted.has(node.conceptId)) continue
      if (node.totalWeight < c.minTotalWeight) continue
      if (node.balanceScore < c.minBalance) continue
      if (node.spectrum.size < c.minColors) continue
      out.push(node)
    }
    return out
  }

  /**
   * B8.P.2 — promote a concept to white. Validates the witness set
   * against temporal-spread + kind-diversity gates (W3). Throws on
   * failed validation; succeeds with a stored WhiteRecord otherwise.
   *
   * Caller is responsible for spectral re-check (call whiteCandidates
   * first, or accept the risk that decay has moved the node out of
   * candidate range between scan and promotion).
   */
  promoteToWhite(
    conceptId: string,
    witness: string[],
    opts: { promotedBy?: 'cassi' | 'operator'; criteria?: Partial<WhitePromotionCriteria>; now?: number } = {},
  ): WhiteRecord {
    if (this.closed) throw new Error('Prism closed')
    const c = { ...DEFAULT_WHITE_CRITERIA, ...opts.criteria }
    const now = opts.now ?? Date.now()

    if (witness.length === 0) {
      throw new Error('promoteToWhite requires at least one witness fork')
    }

    // Pull witness contributions to check temporal spread + kind diversity.
    const placeholders = witness.map(() => '?').join(',')
    const rows = this.db.prepare(`
      SELECT fork_id, observed_at, perturbation_kinds
      FROM prism_fork_contributions
      WHERE fork_id IN (${placeholders})
    `).all(...witness) as Array<{ fork_id: string; observed_at: string; perturbation_kinds: string }>

    if (rows.length === 0) {
      throw new Error(`promoteToWhite: none of the ${witness.length} witness fork ids found in fork_contributions`)
    }

    const observedAtMs = rows.map(r => Date.parse(r.observed_at)).filter(Number.isFinite)
    const earliest = Math.min(...observedAtMs)
    const latest = Math.max(...observedAtMs)
    const spreadDays = (latest - earliest) / 86_400_000
    if (spreadDays < c.witnessTemporalSpreadDaysMin) {
      throw new Error(
        `promoteToWhite: witness temporal spread ${spreadDays.toFixed(1)} days < required ${c.witnessTemporalSpreadDaysMin}`,
      )
    }

    const distinctKinds = new Set<string>()
    for (const row of rows) {
      try {
        for (const k of JSON.parse(row.perturbation_kinds) as string[]) distinctKinds.add(k)
      } catch { /* skip malformed */ }
    }
    if (distinctKinds.size < c.witnessKindDiversityMin) {
      throw new Error(
        `promoteToWhite: witness kind diversity ${distinctKinds.size} < required ${c.witnessKindDiversityMin}`,
      )
    }

    // Snapshot current spectrum + balance for audit.
    const spectrum = this.spectrumAt(conceptId, now)
    const totalWeight = sumSpectrum(spectrum)
    const balance = computeBalance(spectrum, totalWeight)

    const record: WhiteRecord = {
      conceptId,
      promotedAt: new Date(now).toISOString(),
      promotedBy: opts.promotedBy ?? 'cassi',
      witness,
      criteriaSnapshot: {
        balance,
        totalWeight,
        colorCount: spectrum.size,
        witnessTemporalSpreadDays: Math.round(spreadDays * 10) / 10,
        witnessKindDiversity: distinctKinds.size,
      },
      demotedAt: null,
      demotedReason: null,
      contestedSince: null,
      metadata: {},
    }

    this.db.prepare(`
      INSERT INTO prism_white_records
        (concept_id, promoted_at, promoted_by, witness_json, criteria_json, metadata)
      VALUES (?, ?, ?, ?, ?, '{}')
      ON CONFLICT(concept_id) DO UPDATE SET
        promoted_at     = excluded.promoted_at,
        promoted_by     = excluded.promoted_by,
        witness_json    = excluded.witness_json,
        criteria_json   = excluded.criteria_json,
        demoted_at      = NULL,
        demoted_reason  = NULL,
        contested_since = NULL
    `).run(
      record.conceptId,
      record.promotedAt,
      record.promotedBy,
      JSON.stringify(record.witness),
      JSON.stringify(record.criteriaSnapshot),
    )
    this.logger.info?.('Prism: promoted to white', {
      conceptId, balance, totalWeight, colorCount: spectrum.size,
    })
    return record
  }

  /**
   * B8.P.2 — demote a previously-white node. Preserves the record
   * (W4 — reversibility): sets demoted_at + demoted_reason without
   * deleting the row. A subsequent promoteToWhite can re-promote
   * (clears the demotion fields).
   */
  demoteFromWhite(conceptId: string, reason: 'contested' | 'decay' | 'manual', now: number = Date.now()): boolean {
    if (this.closed) return false
    const result = this.db.prepare(`
      UPDATE prism_white_records
      SET demoted_at = ?, demoted_reason = ?
      WHERE concept_id = ? AND demoted_at IS NULL
    `).run(new Date(now).toISOString(), reason, conceptId)
    if (result.changes > 0) {
      this.logger.info?.('Prism: demoted from white', { conceptId, reason })
    }
    return result.changes > 0
  }

  /**
   * B8.P.2 — list currently-white nodes (demoted_at IS NULL).
   */
  whiteNodes(): WhiteRecord[] {
    if (this.closed) return []
    const rows = this.db.prepare(`
      SELECT * FROM prism_white_records WHERE demoted_at IS NULL ORDER BY promoted_at DESC
    `).all() as Array<{
      concept_id: string; promoted_at: string; promoted_by: string;
      witness_json: string; criteria_json: string;
      demoted_at: string | null; demoted_reason: string | null;
      contested_since: string | null; metadata: string;
    }>
    return rows.map(r => this.whiteRowToRecord(r))
  }

  /**
   * B8.P.2 — list nodes promoted to white but flagged as contested
   * (contested_since IS NOT NULL). Caller flags via `flagContested`
   * when dissonance signals fire (e.g., spectrum suddenly stark
   * after extended balanced period).
   */
  contestedNodes(): WhiteRecord[] {
    if (this.closed) return []
    const rows = this.db.prepare(`
      SELECT * FROM prism_white_records
      WHERE demoted_at IS NULL AND contested_since IS NOT NULL
      ORDER BY contested_since DESC
    `).all() as Array<{
      concept_id: string; promoted_at: string; promoted_by: string;
      witness_json: string; criteria_json: string;
      demoted_at: string | null; demoted_reason: string | null;
      contested_since: string | null; metadata: string;
    }>
    return rows.map(r => this.whiteRowToRecord(r))
  }

  /**
   * B8.P.2 — flag a white node as contested. Doesn't auto-demote;
   * caller observes the flag, decides whether to demote. Setting
   * contestedSince on an already-contested node is a no-op.
   */
  flagContested(conceptId: string, now: number = Date.now()): boolean {
    if (this.closed) return false
    const result = this.db.prepare(`
      UPDATE prism_white_records
      SET contested_since = ?
      WHERE concept_id = ? AND demoted_at IS NULL AND contested_since IS NULL
    `).run(new Date(now).toISOString(), conceptId)
    return result.changes > 0
  }

  /**
   * B8.P.3 — synthesize an invariant engram for a white concept.
   *
   * Pure-function shape: caller supplies an `llmCallback` that turns
   * the gathered inputs into invariant text + confidence. Prism
   * assembles the SynthesizedInvariant from the callback's output
   * plus the spectral provenance + witness citation chain.
   *
   * The callback is intentionally async to accommodate real Reverie
   * LLM calls, but tests can pass a sync mock that returns a
   * `Promise.resolve(...)`. Default behavior on callback throw: error
   * propagates; no partial engram is created.
   *
   * Caller is responsible for landing the result in the Mnemic Field
   * — Prism doesn't import the field directly to keep the dependency
   * direction clean.
   */
  async synthesizeWhiteInvariant(
    conceptId: string,
    llmCallback: (inputs: {
      conceptId: string
      spectrum: Spectrum
      balanceScore: number
      totalWeight: number
      record: WhiteRecord
      contributions: Array<{ forkId: string; color: AffectColor; observedAt: string; perturbationKinds: string[] }>
    }) => Promise<{ invariants: string[]; confidence: number }>,
    now: number = Date.now(),
  ): Promise<SynthesizedInvariant> {
    const inputs = this.gatherSynthesisInputs(conceptId, now)
    const llmResult = await llmCallback(inputs)
    if (!Array.isArray(llmResult.invariants)) {
      throw new Error('synthesizeWhiteInvariant: llmCallback must return invariants array')
    }
    return {
      engramType: 'synthesized_invariant',
      concept: conceptId,
      conceptId,
      invariants: llmResult.invariants,
      spectralProvenance: [...inputs.spectrum.keys()],
      sourceContributions: [...inputs.record.witness],
      affectSignature: 'balanced',
      confidence: Math.max(0, Math.min(1, llmResult.confidence)),
      synthesizedAt: new Date(now).toISOString(),
    }
  }

  /**
   * B8.P.3 — gather the inputs Reverie needs to synthesize an
   * invariant for a white-standing concept. Returns:
   *  - spectrum + balance + per-color weights at `now`
   *  - the white record (errors if not currently white — synthesis
   *    on non-white nodes degrades affectSignature, see spec §5.1)
   *  - witness fork ids + their full contribution rows for citation
   *
   * This is the read-only data assembly step. The Reverie LLM call
   * is the caller's responsibility — synthesizeWhiteInvariant takes
   * a callback that turns these inputs into invariant text.
   */
  gatherSynthesisInputs(conceptId: string, now: number = Date.now()): {
    conceptId: string
    spectrum: Spectrum
    balanceScore: number
    totalWeight: number
    record: WhiteRecord
    contributions: Array<{
      forkId: string
      color: AffectColor
      observedAt: string
      perturbationKinds: string[]
    }>
  } {
    if (this.closed) throw new Error('Prism closed')
    const recordRow = this.db.prepare(`
      SELECT * FROM prism_white_records
      WHERE concept_id = ? AND demoted_at IS NULL
    `).get(conceptId) as Parameters<typeof this.whiteRowToRecord>[0] | undefined
    if (!recordRow) {
      throw new Error(`gatherSynthesisInputs: '${conceptId}' is not currently white`)
    }
    const record = this.whiteRowToRecord(recordRow)
    const spectrum = this.spectrumAt(conceptId, now)
    const totalWeight = sumSpectrum(spectrum)
    const balanceScore = computeBalance(spectrum, totalWeight)

    const placeholders = record.witness.map(() => '?').join(',')
    const contribRows = record.witness.length === 0 ? [] : this.db.prepare(`
      SELECT fork_id, color, observed_at, perturbation_kinds
      FROM prism_fork_contributions
      WHERE fork_id IN (${placeholders})
    `).all(...record.witness) as Array<{
      fork_id: string; color: string; observed_at: string; perturbation_kinds: string;
    }>

    const contributions = contribRows.map(r => ({
      forkId: r.fork_id,
      color: r.color as AffectColor,
      observedAt: r.observed_at,
      perturbationKinds: (() => {
        try { return JSON.parse(r.perturbation_kinds) as string[] } catch { return [] }
      })(),
    }))

    return { conceptId, spectrum, balanceScore, totalWeight, record, contributions }
  }

  private whiteRowToRecord(row: {
    concept_id: string; promoted_at: string; promoted_by: string;
    witness_json: string; criteria_json: string;
    demoted_at: string | null; demoted_reason: string | null;
    contested_since: string | null; metadata: string;
  }): WhiteRecord {
    return {
      conceptId: row.concept_id,
      promotedAt: row.promoted_at,
      promotedBy: row.promoted_by as 'cassi' | 'operator',
      witness: JSON.parse(row.witness_json) as string[],
      criteriaSnapshot: JSON.parse(row.criteria_json) as WhiteRecord['criteriaSnapshot'],
      demotedAt: row.demoted_at,
      demotedReason: row.demoted_reason as WhiteRecord['demotedReason'],
      contestedSince: row.contested_since,
      metadata: row.metadata ? JSON.parse(row.metadata) : {},
    }
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
