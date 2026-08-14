import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import { getDataDir } from '@cassicore/foundation'
import { prefixedId } from '../../vendor/core/intelligence/utils/prefixed-id.js'

import {
  DEFAULT_CHAR_LIMIT,
  LaminaAuthorityError,
  LaminaCasConflict,
  LaminaOverflow,
} from './types.js'

import type { ILogger } from '@cassicore/foundation'
import type { Provenance } from '../../vendor/core/runtime/audit/index.js'
import type {
  Lamina,
  LaminaAppend,
  LaminaCreate,
  LaminaQuery,
  LaminaReplace,
  LaminaRethink,
  LaminaScope,
} from './types.js'

const DB_NAME = 'system-state.db'

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS laminae (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    char_limit INTEGER NOT NULL DEFAULT 8000,
    description TEXT,
    owner TEXT NOT NULL,
    owner_exclusive INTEGER NOT NULL DEFAULT 0,
    read_only INTEGER NOT NULL DEFAULT 0,
    scope_kind TEXT NOT NULL DEFAULT 'global',
    scope_value TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    last_write_provenance TEXT,
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
  );

  CREATE UNIQUE INDEX IF NOT EXISTS uniq_lamina_label_scope
    ON laminae(label, scope_kind, COALESCE(scope_value, ''));
  CREATE INDEX IF NOT EXISTS idx_lamina_owner ON laminae(owner);
  CREATE INDEX IF NOT EXISTS idx_lamina_pinned ON laminae(pinned);
  CREATE INDEX IF NOT EXISTS idx_lamina_scope ON laminae(scope_kind, scope_value);
`

function hashContent(s: string): string {
  return crypto.createHash('sha256').update(s, 'utf8').digest('hex').slice(0, 32)
}

function scopeToColumns(scope: LaminaScope): { kind: string; value: string | null } {
  switch (scope.kind) {
    case 'global': return { kind: 'global', value: null }
    case 'session': return { kind: 'session', value: scope.sessionId }
    case 'channel': return { kind: 'channel', value: scope.channel }
    case 'agent': return { kind: 'agent', value: scope.agentId }
  }
}

function scopeFromColumns(kind: string, value: string | null): LaminaScope {
  switch (kind) {
    case 'session': return { kind: 'session', sessionId: value ?? '' }
    case 'channel': return { kind: 'channel', channel: value ?? '' }
    case 'agent': return { kind: 'agent', agentId: value ?? '' }
    default: return { kind: 'global' }
  }
}

function rowToLamina(row: Record<string, unknown>): Lamina {
  return {
    id: row.id as string,
    label: row.label as string,
    content: row.content as string,
    contentHash: row.content_hash as string,
    charLimit: row.char_limit as number,
    description: (row.description as string | null) ?? null,
    owner: row.owner as string,
    ownerExclusive: !!row.owner_exclusive,
    readOnly: !!row.read_only,
    scope: scopeFromColumns(row.scope_kind as string, (row.scope_value as string | null) ?? null),
    tags: JSON.parse((row.tags as string) ?? '[]'),
    lastWriteProvenance: row.last_write_provenance
      ? (JSON.parse(row.last_write_provenance as string) as Provenance)
      : null,
    pinned: !!row.pinned,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
    version: row.version as number,
  }
}

export interface LaminaStoreOptions {
  dbPath?: string
}

/** Caller identity for authority checks. */
export interface LaminaCaller {
  agentId: string
  /** Provenance for the audit trail attached to writes. */
  provenance: Provenance
}

export class LaminaStore {
  private db: Database.Database
  private logger: ILogger

  private insertStmt: Database.Statement
  private selectByIdStmt: Database.Statement
  private selectByLabelStmt: Database.Statement
  private deleteStmt: Database.Statement
  private updateContentStmt: Database.Statement
  private countTotalStmt: Database.Statement
  private countPinnedStmt: Database.Statement
  private countByOwnerStmt: Database.Statement

  // Read-through snapshot cache for get/findByLabel. Busted on every write.
  // Lamina is read-heavy (every turn queries by label for injection) but
  // mutations are rare, so bust-the-world is simpler than entry-level invalidation.
  private snapshot: Map<string, Lamina | null> = new Map()

  constructor(logger: ILogger, opts: LaminaStoreOptions = {}) {
    this.logger = logger.child?.('lamina-store') ?? logger
    const finalPath = opts.dbPath ?? path.join(getDataDir(), DB_NAME)
    fs.mkdirSync(path.dirname(finalPath), { recursive: true })
    this.db = new Database(finalPath)
    this.db.pragma('journal_mode = WAL')
    this.db.exec(SCHEMA_SQL)

    this.insertStmt = this.db.prepare(`
      INSERT INTO laminae
        (id, label, content, content_hash, char_limit, description, owner, owner_exclusive,
         read_only, scope_kind, scope_value, tags, last_write_provenance, pinned, created_at, updated_at, version)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    `)
    this.selectByIdStmt = this.db.prepare(`SELECT * FROM laminae WHERE id = ?`)
    this.selectByLabelStmt = this.db.prepare(
      `SELECT * FROM laminae WHERE label = ? AND scope_kind = ? AND COALESCE(scope_value, '') = COALESCE(?, '')`
    )
    this.deleteStmt = this.db.prepare(`DELETE FROM laminae WHERE id = ?`)
    this.updateContentStmt = this.db.prepare(`
      UPDATE laminae
      SET content = ?, content_hash = ?, last_write_provenance = ?, updated_at = ?, version = version + 1
      WHERE id = ?
    `)
    this.countTotalStmt = this.db.prepare(`SELECT COUNT(*) AS n FROM laminae`)
    this.countPinnedStmt = this.db.prepare(`SELECT COUNT(*) AS n FROM laminae WHERE pinned = 1`)
    this.countByOwnerStmt = this.db.prepare(`SELECT owner, COUNT(*) AS n FROM laminae GROUP BY owner`)
  }

  private invalidate(): void {
    this.snapshot.clear()
  }

  close(): void {
    try { this.db.close() } catch { /* ignore */ }
  }

  // CRUD

  create(input: LaminaCreate, caller: LaminaCaller): Lamina {
    const id = prefixedId('lam')
    const now = new Date().toISOString()
    const content = input.content ?? ''
    const charLimit = input.charLimit ?? DEFAULT_CHAR_LIMIT
    if (content.length > charLimit) {
      throw new LaminaOverflow(input.label, content.length, charLimit)
    }
    const scope = input.scope ?? { kind: 'global' }
    const { kind: scopeKind, value: scopeValue } = scopeToColumns(scope)
    const contentHash = hashContent(content)

    try {
      this.insertStmt.run(
        id, input.label, content, contentHash, charLimit, input.description ?? null,
        input.owner, input.ownerExclusive ? 1 : 0, input.readOnly ? 1 : 0,
        scopeKind, scopeValue,
        JSON.stringify(input.tags ?? []),
        JSON.stringify(caller.provenance),
        input.pinned ? 1 : 0, now, now,
      )
      this.invalidate()
    } catch (err) {
      if (String(err).includes('UNIQUE')) {
        // Idempotent: return the existing one
        const existing = this.findByLabel(input.label, scope)
        if (existing) return existing
      }
      throw err
    }

    return {
      id,
      label: input.label,
      content,
      contentHash,
      charLimit,
      description: input.description ?? null,
      owner: input.owner,
      ownerExclusive: input.ownerExclusive ?? false,
      readOnly: input.readOnly ?? false,
      scope,
      tags: input.tags ?? [],
      lastWriteProvenance: caller.provenance,
      pinned: input.pinned ?? false,
      createdAt: now,
      updatedAt: now,
      version: 1,
    }
  }

  /** Create-if-missing — returns existing lamina without overwrite. */
  ensure(input: LaminaCreate, caller: LaminaCaller): Lamina {
    const scope = input.scope ?? { kind: 'global' }
    const existing = this.findByLabel(input.label, scope)
    if (existing) return existing
    return this.create(input, caller)
  }

  get(id: string): Lamina | null {
    const key = `id:${id}`
    if (this.snapshot.has(key)) return this.snapshot.get(key) ?? null
    const row = this.selectByIdStmt.get(id) as Record<string, unknown> | undefined
    const result = row ? rowToLamina(row) : null
    this.snapshot.set(key, result)
    return result
  }

  findByLabel(label: string, scope: LaminaScope = { kind: 'global' }): Lamina | null {
    const { kind, value } = scopeToColumns(scope)
    const key = `lbl:${label}|${kind}|${value ?? ''}`
    if (this.snapshot.has(key)) return this.snapshot.get(key) ?? null
    const row = this.selectByLabelStmt.get(label, kind, value) as Record<string, unknown> | undefined
    const result = row ? rowToLamina(row) : null
    this.snapshot.set(key, result)
    return result
  }

  list(query: LaminaQuery = {}): Lamina[] {
    const where: string[] = []
    const args: unknown[] = []

    if (query.owner) { where.push('owner = ?'); args.push(query.owner) }
    if (query.label) { where.push('label = ?'); args.push(query.label) }
    if (query.pinned !== undefined) { where.push('pinned = ?'); args.push(query.pinned ? 1 : 0) }
    if (query.scope) {
      const { kind, value } = scopeToColumns(query.scope)
      where.push('scope_kind = ?'); args.push(kind)
      where.push(`COALESCE(scope_value, '') = COALESCE(?, '')`); args.push(value)
    } else if (query.matchScope) {
      // Return globals + the matching scope
      const { kind, value } = scopeToColumns(query.matchScope)
      where.push(`(scope_kind = 'global' OR (scope_kind = ? AND COALESCE(scope_value, '') = COALESCE(?, '')))`)
      args.push(kind, value)
    }

    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''
    const limit = Math.max(1, Math.min(query.limit ?? 200, 1000))
    // list() keeps an inline prepare() — the WHERE clause varies per call,
    // so each distinct shape would need its own cached statement. Not worth it.
    const rows = this.db
      .prepare(`SELECT * FROM laminae ${whereSql} ORDER BY pinned DESC, updated_at DESC LIMIT ?`)
      .all(...args, limit) as Record<string, unknown>[]

    let result = rows.map(rowToLamina)
    if (query.tags && query.tags.length > 0) {
      const wanted = new Set(query.tags)
      result = result.filter(l => l.tags.some(t => wanted.has(t)))
    }
    return result
  }

  // Mutations — all CAS-aware

  replace(label: string, scope: LaminaScope, input: LaminaReplace, caller: LaminaCaller): Lamina {
    return this.db.transaction(() => {
      const current = this.findByLabel(label, scope)
      if (!current) {
        throw new Error(`Lamina '${label}' not found`)
      }
      this.assertWritable(current, caller, 'replace', input.asOwner === true)
      if (input.expectedHash !== null && input.expectedHash !== current.contentHash) {
        throw new LaminaCasConflict(label, current.contentHash, input.expectedHash, current.content)
      }
      if (input.content.length > current.charLimit) {
        throw new LaminaOverflow(label, input.content.length, current.charLimit)
      }
      return this.writeContent(current, input.content, caller, input.reason ?? null)
    })()
  }

  append(label: string, scope: LaminaScope, input: LaminaAppend, caller: LaminaCaller): Lamina {
    return this.db.transaction(() => {
      const current = this.findByLabel(label, scope)
      if (!current) throw new Error(`Lamina '${label}' not found`)
      this.assertWritable(current, caller, 'append', false)
      const sep = input.separator ?? '\n'
      const next = current.content.length === 0 ? input.content : current.content + sep + input.content
      if (next.length > current.charLimit) {
        throw new LaminaOverflow(label, next.length, current.charLimit)
      }
      return this.writeContent(current, next, caller, input.reason ?? null)
    })()
  }

  rethink(label: string, scope: LaminaScope, input: LaminaRethink, caller: LaminaCaller): Lamina {
    return this.db.transaction(() => {
      const current = this.findByLabel(label, scope)
      if (!current) throw new Error(`Lamina '${label}' not found`)
      // Rethink requires owner authority on owner-exclusive laminae
      if (current.ownerExclusive && current.owner !== caller.agentId) {
        throw new LaminaAuthorityError(label, 'rethink', caller.agentId, current.owner)
      }
      if (current.readOnly && current.owner !== caller.agentId) {
        throw new LaminaAuthorityError(label, 'rethink', caller.agentId, current.owner)
      }
      if (input.content.length > current.charLimit) {
        throw new LaminaOverflow(label, input.content.length, current.charLimit)
      }
      return this.writeContent(current, input.content, caller, input.reason)
    })()
  }

  delete(id: string): boolean {
    const res = this.deleteStmt.run(id)
    if (res.changes > 0) this.invalidate()
    return res.changes > 0
  }

  // Internals

  private assertWritable(lamina: Lamina, caller: LaminaCaller, action: string, asOwner: boolean): void {
    if (lamina.readOnly && lamina.owner !== caller.agentId) {
      throw new LaminaAuthorityError(lamina.label, action, caller.agentId, lamina.owner)
    }
    // Owner-exclusive normally only blocks rethink (handled in rethink()), so append/replace pass.
    if (asOwner && lamina.owner !== caller.agentId) {
      this.logger.warn?.(`asOwner override on lamina '${lamina.label}' by non-owner ${caller.agentId}`)
    }
  }

  private writeContent(current: Lamina, next: string, caller: LaminaCaller, reason: string | null): Lamina {
    const now = new Date().toISOString()
    const hash = hashContent(next)
    const provenance = reason ? { ...caller.provenance, reason } : caller.provenance
    this.updateContentStmt.run(next, hash, JSON.stringify(provenance), now, current.id)
    this.invalidate()
    return {
      ...current,
      content: next,
      contentHash: hash,
      lastWriteProvenance: provenance,
      updatedAt: now,
      version: current.version + 1,
    }
  }

  // Metrics

  metrics(): { total: number; byOwner: Record<string, number>; pinned: number } {
    const total = (this.countTotalStmt.get() as { n: number }).n
    const pinned = (this.countPinnedStmt.get() as { n: number }).n
    const rows = this.countByOwnerStmt.all() as Array<{ owner: string; n: number }>
    const byOwner: Record<string, number> = {}
    for (const r of rows) byOwner[r.owner] = r.n
    return { total, byOwner, pinned }
  }
}
