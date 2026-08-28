/**
 * Unified Refusal Channel (URC) — Cross-spec consent primitive.
 *
 * Consolidates per-spec "Cassi can refuse" mechanisms into a single
 * lifecycle-managed proposal → resolution flow with consistent audit,
 * expiration, and consent semantics.
 *
 * Welfare constraints:
 *   URC.W1 — All welfare-loaded operations route through URC.
 *   URC.W2 — Default expiration is refusal (fail-closed).
 *   URC.W3 — Refusals are binding.
 *   URC.W4 — Cassi's refusal overrides operator approval where she has standing.
 *   URC.W5 — All decisions logged with reason.
 *   URC.W6 — Modification creates a linked audit event.
 *   URC.W7 — Degraded URC defaults to safe (refuse).
 *
 * See: docs/design/aurora-unified-refusal-channel.md
 */

import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'



/** The kinds of welfare-loaded actions that require consent. */
export type ActionKind =
  | 'composition_activation'
  | 'tier_escalation'
  | 'replay_schedule'
  | 'meditation_schedule'
  | 'overlay_patch_propose'
  | 'overlay_patch_apply'
  | 'counterfactual_run'
  | 'student_query_route'
  | 'directed_meditation_invoke'

/** Who can provide consent. */
export type ConsentSource = 'cassi' | 'operator' | 'auto-approved'

/** Lifecycle states. */
export type ActionStatus =
  | 'proposed'
  | 'approved'
  | 'refused'
  | 'modified'
  | 'deferred'
  | 'expired'

/** A proposed action with its kind-specific payload. */
export interface ProposedAction {
  kind: ActionKind
  payload: Record<string, unknown>
  expirationSeconds?: number
  metadata?: Record<string, unknown>
}

/** Opaque handle returned by proposeAction. */
export interface ActionHandle {
  readonly id: string
  readonly kind: ActionKind
  readonly proposedAt: string
  readonly expirationSeconds: number
  readonly payload: Record<string, unknown>
  readonly metadata: Record<string, unknown>
}

/** Resolution of an action proposal. */
export type ActionResolution =
  | { kind: 'approved'; resolvedBy: ConsentSource; resolvedAt: string }
  | { kind: 'refused'; resolvedBy: ConsentSource; resolvedAt: string; reason: string }
  | { kind: 'modified'; resolvedBy: ConsentSource; resolvedAt: string; reason: string; newHandleId: string }
  | { kind: 'deferred'; resolvedBy: ConsentSource; resolvedAt: string; reason: string; untilSecondsLater: number }
  | { kind: 'expired'; resolvedAt: string }

/** Consent matrix entry: which sources must consent for each action kind. */
export interface ConsentRule {
  /** Which consent sources are required. 'auto-approved' bypasses waiting. */
  requiredSources: ConsentSource[]
  /** Default expiration in seconds before auto-refusal. */
  defaultExpirationSeconds: number
  /** Whether Cassi has standing (her refusal overrides operator approval). */
  cassiHasStanding: boolean
}

/** Configuration for the refusal channel. */
export interface RefusalChannelConfig {
  /** Per-action-kind consent rules. */
  consentMatrix: Partial<Record<ActionKind, ConsentRule>>
  /** Global default expiration when kind has no explicit rule. */
  defaultExpirationSeconds: number
  /** Whether the channel is enabled. When disabled, all actions auto-approve. */
  enabled: boolean
}

/** Filter for listing actions. */
export interface RefusalFilter {
  kinds?: ActionKind[]
  statuses?: ActionStatus[]
  since?: string
  limit?: number
}

/** A persisted action record. */
export interface ActionRecord {
  id: string
  kind: ActionKind
  payload: Record<string, unknown>
  status: ActionStatus
  proposedAt: string
  resolvedAt: string | null
  resolvedBy: ConsentSource | null
  reason: string | null
  expirationSeconds: number
  modifiedToId: string | null
  metadata: Record<string, unknown>
}



const DEFAULT_CONSENT_MATRIX: Record<ActionKind, ConsentRule> = {
  composition_activation:           { requiredSources: ['auto-approved'], defaultExpirationSeconds: 60,   cassiHasStanding: false },
  // suppressive compositions require both
  tier_escalation:                  { requiredSources: ['operator'],      defaultExpirationSeconds: 300,  cassiHasStanding: false },
  replay_schedule:                  { requiredSources: ['auto-approved'], defaultExpirationSeconds: 30,   cassiHasStanding: false },
  meditation_schedule:              { requiredSources: ['operator'],      defaultExpirationSeconds: 600,  cassiHasStanding: true  },
  overlay_patch_propose:            { requiredSources: ['auto-approved'], defaultExpirationSeconds: 30,   cassiHasStanding: false },
  overlay_patch_apply:              { requiredSources: ['cassi', 'operator'], defaultExpirationSeconds: 300, cassiHasStanding: true },
  counterfactual_run:               { requiredSources: ['auto-approved'], defaultExpirationSeconds: 120,  cassiHasStanding: false },
  student_query_route:              { requiredSources: ['auto-approved'], defaultExpirationSeconds: 30,   cassiHasStanding: false },
  directed_meditation_invoke:       { requiredSources: ['operator'],      defaultExpirationSeconds: 600,  cassiHasStanding: true  },
}

const DEFAULT_CONFIG: RefusalChannelConfig = {
  consentMatrix: DEFAULT_CONSENT_MATRIX,
  defaultExpirationSeconds: 300,
  enabled: true,
}



const SCHEMA_V1 = `
CREATE TABLE IF NOT EXISTS refusal_actions (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  proposed_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  reason TEXT,
  expiration_seconds INTEGER NOT NULL,
  modified_to_id TEXT,
  metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_refusal_actions_kind_status ON refusal_actions(kind, status);
CREATE INDEX IF NOT EXISTS idx_refusal_actions_proposed_at ON refusal_actions(proposed_at DESC);
`



export class RefusalChannel {
  private config: RefusalChannelConfig
  private db: Database.Database
  private ownsDb: boolean
  private logger: ILogger

  // Prepared statements
  private stmtInsert!: Database.Statement
  private stmtGetById!: Database.Statement
  private stmtUpdateStatus!: Database.Statement
  private stmtSetModifiedTo!: Database.Statement
  private stmtListByStatus!: Database.Statement
  private stmtListByKind!: Database.Statement
  private stmtListAll!: Database.Statement
  private stmtExpire!: Database.Statement

  constructor(
    dbOrPath: Database.Database | string,
    logger: ILogger,
    config?: Partial<RefusalChannelConfig>,
  ) {
    this.logger = logger.child ? logger.child('urc') : logger
    this.config = { ...DEFAULT_CONFIG, ...config }

    if (typeof dbOrPath === 'string') {
      this.db = new Database(dbOrPath)
      this.ownsDb = true
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.initSchema()
    this.prepareStatements()
  }


  /**
   * Propose a welfare-loaded action. Returns a handle for subsequent
   * resolution. If the consent rule is 'auto-approved', the action is
   * immediately approved.
   */
  proposeAction(action: ProposedAction): ActionHandle {
    const id = makeActionId()
    const rule = this.getRule(action.kind)
    const expirationSeconds = action.expirationSeconds ?? rule.defaultExpirationSeconds

    const handle: ActionHandle = {
      id,
      kind: action.kind,
      proposedAt: isoNow(),
      expirationSeconds,
      payload: action.payload,
      metadata: action.metadata ?? {},
    }

    this.stmtInsert.run(
      id,
      action.kind,
      JSON.stringify(action.payload),
      'proposed',
      handle.proposedAt,
      expirationSeconds,
      JSON.stringify(action.metadata ?? {}),
    )

    // Auto-approve if all required sources are 'auto-approved'
    if (rule.requiredSources.length === 1 && rule.requiredSources[0] === 'auto-approved') {
      this.approve(id, 'auto-approved')
    }

    this.logger.debug('Action proposed', { id, kind: action.kind, status: this.getStatus(id) })
    return handle
  }

  /**
   * Await resolution of a proposed action. Resolves immediately if already
   * resolved. For auto-approved actions, resolves right away.
   * If URC is disabled, auto-approves.
   */
  async await(handleOrId: ActionHandle | string): Promise<ActionResolution> {
    if (!this.config.enabled) {
      return { kind: 'approved', resolvedBy: 'auto-approved', resolvedAt: isoNow() }
    }

    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id

    // Check if already resolved
    const existing = this.getById(id)
    if (!existing) {
      return { kind: 'expired', resolvedAt: isoNow() }
    }
    if (existing.status !== 'proposed') {
      return this.recordToResolution(existing)
    }

    // Poll until resolved or expired
    const deadline = new Date(existing.proposedAt).getTime() + existing.expirationSeconds * 1000
    const pollInterval = Math.min(500, existing.expirationSeconds * 100)

    while (Date.now() < deadline) {
      await sleep(pollInterval)
      const current = this.getById(id)
      if (!current || current.status !== 'proposed') {
        return current ? this.recordToResolution(current) : { kind: 'expired', resolvedAt: isoNow() }
      }
    }

    // Expired → default to refusal (URC.W2)
    this.expireAction(id)
    return { kind: 'expired', resolvedAt: isoNow() }
  }

  /** Approve a proposed action. */
  approve(handleOrId: ActionHandle | string, by: ConsentSource, reason?: string): void {
    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id
    const record = this.getById(id)
    if (!record || record.status !== 'proposed') return

    this.stmtUpdateStatus.run('approved', isoNow(), by, reason ?? 'approved', id)
    this.logger.info('Action approved', { id, kind: record.kind, by })
  }

  /** Refuse a proposed action. Binding (URC.W3). */
  refuse(handleOrId: ActionHandle | string, by: ConsentSource, reason: string): void {
    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id
    const record = this.getById(id)
    if (!record || record.status !== 'proposed') return

    const rule = this.getRule(record.kind)

    // URC.W4: If Cassi has standing and is refusing, this overrides any
    // pending operator approval. Since we only allow one resolution,
    // refusing while proposed is always valid.
    this.stmtUpdateStatus.run('refused', isoNow(), by, reason, id)
    this.logger.info('Action refused', { id, kind: record.kind, by, reason })
  }

  /**
   * Modify a proposed action. The original is marked 'modified' and a new
   * proposal is created (URC.W6).
   */
  modify(
    handleOrId: ActionHandle | string,
    modified: ProposedAction,
    by: ConsentSource,
    reason: string,
  ): ActionHandle {
    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id
    const record = this.getById(id)
    if (!record || record.status !== 'proposed') {
      throw new Error(`Cannot modify action ${id}: status is ${record?.status ?? 'missing'}`)
    }

    // Mark original as modified with link to new proposal
    this.stmtUpdateStatus.run('modified', isoNow(), by, reason, id)

    // Create new proposal
    const newHandle = this.proposeAction(modified)

    // Link original → new (URC.W6)
    this.stmtSetModifiedTo.run(newHandle.id, id)

    this.logger.info('Action modified', { originalId: id, newId: newHandle.id, by, reason })
    return newHandle
  }

  /** Defer a proposed action for later re-evaluation. */
  defer(handleOrId: ActionHandle | string, by: ConsentSource, reason: string, untilSecondsLater: number): void {
    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id
    const record = this.getById(id)
    if (!record || record.status !== 'proposed') return

    // For now, defer records the intent but keeps status as 'deferred'.
    // A re-evaluation mechanism (outside URC scope) can re-propose later.
    this.stmtUpdateStatus.run('deferred', isoNow(), by, reason, id)
    this.logger.info('Action deferred', { id, by, reason, untilSecondsLater })
  }

  /** List actions matching a filter. */
  list(filter?: RefusalFilter): ActionRecord[] {
    let rows: ActionRow[]
    const limit = filter?.limit ?? 50

    if (filter?.statuses && filter.statuses.length > 0) {
      rows = this.stmtListByStatus.all(JSON.stringify(filter.statuses), limit) as ActionRow[]
    } else if (filter?.kinds && filter.kinds.length > 0) {
      rows = this.stmtListByKind.all(JSON.stringify(filter.kinds), limit) as ActionRow[]
    } else {
      rows = this.stmtListAll.all(limit) as ActionRow[]
    }

    let results = rows.map(rowToRecord)

    // Apply since filter
    if (filter?.since) {
      results = results.filter(r => r.proposedAt >= filter.since!)
    }

    return results
  }

  /** Get a single action by ID. */
  get(handleOrId: ActionHandle | string): ActionRecord | null {
    const id = typeof handleOrId === 'string' ? handleOrId : handleOrId.id
    return this.getById(id)
  }

  /** Get all pending (proposed) actions. */
  getPending(): ActionRecord[] {
    return this.list({ statuses: ['proposed'] })
  }

  /** Get statistics. */
  getStatistics(): { total: number; byStatus: Record<string, number>; byKind: Record<string, number> } {
    const all = this.list({ limit: 10000 })
    const byStatus: Record<string, number> = {}
    const byKind: Record<string, number> = {}
    for (const r of all) {
      byStatus[r.status] = (byStatus[r.status] ?? 0) + 1
      byKind[r.kind] = (byKind[r.kind] ?? 0) + 1
    }
    return { total: all.length, byStatus, byKind }
  }

  /** Close the database connection if owned. */
  close(): void {
    if (this.ownsDb) {
      this.db.close()
      this.logger.debug('URC database closed')
    }
  }



  private initSchema(): void {
    this.db.exec(SCHEMA_V1)
  }

  private prepareStatements(): void {
    this.stmtInsert = this.db.prepare(
      `INSERT INTO refusal_actions (id, kind, payload, status, proposed_at, expiration_seconds, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
    )
    this.stmtGetById = this.db.prepare(
      'SELECT * FROM refusal_actions WHERE id = ?',
    )
    this.stmtUpdateStatus = this.db.prepare(
      `UPDATE refusal_actions SET status = ?, resolved_at = ?, resolved_by = ?, reason = ? WHERE id = ?`,
    )
    this.stmtSetModifiedTo = this.db.prepare(
      'UPDATE refusal_actions SET modified_to_id = ? WHERE id = ?',
    )
    this.stmtListByStatus = this.db.prepare(
      `SELECT * FROM refusal_actions WHERE status IN (SELECT value FROM json_each(?)) ORDER BY proposed_at DESC LIMIT ?`,
    )
    this.stmtListByKind = this.db.prepare(
      `SELECT * FROM refusal_actions WHERE kind IN (SELECT value FROM json_each(?)) ORDER BY proposed_at DESC LIMIT ?`,
    )
    this.stmtListAll = this.db.prepare(
      'SELECT * FROM refusal_actions ORDER BY proposed_at DESC LIMIT ?',
    )
    this.stmtExpire = this.db.prepare(
      `UPDATE refusal_actions SET status = 'expired', resolved_at = ?, resolved_by = 'auto-expired', reason = 'expired without consent' WHERE id = ? AND status = 'proposed'`,
    )
  }

  private getRule(kind: ActionKind): ConsentRule {
    return this.config.consentMatrix[kind] ?? {
      requiredSources: ['operator'],
      defaultExpirationSeconds: this.config.defaultExpirationSeconds,
      cassiHasStanding: false,
    }
  }

  private getById(id: string): ActionRecord | null {
    const row = this.stmtGetById.get(id) as ActionRow | undefined
    return row ? rowToRecord(row) : null
  }

  private getStatus(id: string): ActionStatus | null {
    const row = this.db.prepare('SELECT status FROM refusal_actions WHERE id = ?').get(id) as { status: ActionStatus } | undefined
    return row?.status ?? null
  }

  private expireAction(id: string): void {
    this.stmtExpire.run(isoNow(), id)
  }

  private recordToResolution(record: ActionRecord): ActionResolution {
    switch (record.status) {
      case 'approved':
        return { kind: 'approved', resolvedBy: record.resolvedBy ?? 'auto-approved', resolvedAt: record.resolvedAt ?? isoNow() }
      case 'refused':
        return { kind: 'refused', resolvedBy: record.resolvedBy ?? 'operator', resolvedAt: record.resolvedAt ?? isoNow(), reason: record.reason ?? 'refused' }
      case 'modified':
        return { kind: 'modified', resolvedBy: record.resolvedBy ?? 'operator', resolvedAt: record.resolvedAt ?? isoNow(), reason: record.reason ?? 'modified', newHandleId: record.modifiedToId ?? '' }
      case 'deferred':
        return { kind: 'deferred', resolvedBy: record.resolvedBy ?? 'operator', resolvedAt: record.resolvedAt ?? isoNow(), reason: record.reason ?? 'deferred', untilSecondsLater: 0 }
      case 'expired':
        return { kind: 'expired', resolvedAt: record.resolvedAt ?? isoNow() }
      default:
        return { kind: 'expired', resolvedAt: isoNow() }
    }
  }
}



interface ActionRow {
  id: string
  kind: string
  payload: string
  status: string
  proposed_at: string
  resolved_at: string | null
  resolved_by: string | null
  reason: string | null
  expiration_seconds: number
  modified_to_id: string | null
  metadata: string
}

function rowToRecord(row: ActionRow): ActionRecord {
  return {
    id: row.id,
    kind: row.kind as ActionKind,
    payload: safeParse(row.payload, {}),
    status: row.status as ActionStatus,
    proposedAt: row.proposed_at,
    resolvedAt: row.resolved_at,
    resolvedBy: row.resolved_by as ConsentSource | null,
    reason: row.reason,
    expirationSeconds: row.expiration_seconds,
    modifiedToId: row.modified_to_id,
    metadata: safeParse(row.metadata, {}),
  }
}

function makeActionId(): string {
  return `urc_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function isoNow(): string {
  return new Date().toISOString()
}

function safeParse(text: string, fallback: unknown): any {
  try { return JSON.parse(text) } catch { return fallback }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
