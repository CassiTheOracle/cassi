import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import { getDataDir } from '../../utils/paths.js'

import type { ILogger } from '../../../types/interfaces.js'
import type { Facet, FacetInput, FacetUpdate, FacetQuery, DomainStats, Domain, SkillSummary } from './types.js'
import { DOMAIN_INITIAL_CONVICTION } from './types.js'

const DB_NAME = 'pineal.db'

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS pineal_facets (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('identity', 'wisdom', 'philosophy', 'praxis')),
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    conviction REAL NOT NULL DEFAULT 0.5,
    salience REAL NOT NULL DEFAULT 0.5,
    provenance TEXT NOT NULL DEFAULT 'self',
    tags TEXT NOT NULL DEFAULT '[]',
    pinned INTEGER NOT NULL DEFAULT 0,
    scope TEXT DEFAULT NULL,
    evolved_from TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_reinforced TEXT NOT NULL,
    reinforcements INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (evolved_from) REFERENCES pineal_facets(id)
  );

  CREATE INDEX IF NOT EXISTS idx_pineal_domain ON pineal_facets(domain, active);
  CREATE INDEX IF NOT EXISTS idx_pineal_category ON pineal_facets(domain, category, active);
  CREATE INDEX IF NOT EXISTS idx_pineal_conviction ON pineal_facets(conviction DESC);
  CREATE INDEX IF NOT EXISTS idx_pineal_evolution ON pineal_facets(evolved_from);
`

const MIGRATION_SQL = `
  ALTER TABLE pineal_facets ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;
  CREATE INDEX IF NOT EXISTS idx_pineal_pinned ON pineal_facets(pinned, active);
`

const MIGRATION_SCOPE_SQL = `
  ALTER TABLE pineal_facets ADD COLUMN scope TEXT DEFAULT NULL;
  CREATE INDEX IF NOT EXISTS idx_pineal_scope ON pineal_facets(scope, active);
`

let counter = 0
function generateId(): string {
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 6)
  return `f_${ts}${rand}${(counter++).toString(36)}`
}

function rowToFacet(row: Record<string, unknown>): Facet {
  return {
    id: row.id as string,
    domain: row.domain as Domain,
    category: row.category as string,
    content: row.content as string,
    conviction: row.conviction as number,
    salience: row.salience as number,
    provenance: row.provenance as Facet['provenance'],
    tags: JSON.parse(row.tags as string),
    pinned: (row.pinned as number) === 1,
    scope: (row.scope as string) ?? null,
    evolvedFrom: row.evolved_from as string | null,
    version: row.version as number,
    createdAt: row.created_at as string,
    lastReinforced: row.last_reinforced as string,
    reinforcements: row.reinforcements as number,
    active: (row.active as number) === 1,
  }
}

export class PinealStore {
  private db: InstanceType<typeof Database>
  private logger: ILogger

  private _stmts?: {
    insert: Database.Statement
    update: Database.Statement
    getById: Database.Statement
    retire: Database.Statement
    reinforce: Database.Statement
    pin: Database.Statement
    listByDomain: Database.Statement
    listByCategory: Database.Statement
    listAll: Database.Statement
    listActive: Database.Statement
    getHistory: Database.Statement
    domainStats: Database.Statement
    countByDomain: Database.Statement
    skillSummaries: Database.Statement
  }

  constructor(logger: ILogger) {
    this.logger = logger

    const dataDir = getDataDir()
    fs.mkdirSync(dataDir, { recursive: true })
    const dbPath = path.join(dataDir, DB_NAME)

    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('foreign_keys = ON')
    this.db.exec(SCHEMA_SQL)
    this.migrate()

    this.logger.info('[pineal-store] Initialized', { path: dbPath })
  }

  private get stmts() {
    if (!this._stmts) {
      this._stmts = {
        insert: this.db.prepare(`
          INSERT INTO pineal_facets (id, domain, category, content, conviction, salience, provenance, tags, pinned, scope, evolved_from, version, created_at, last_reinforced, reinforcements, active)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        `),
        update: this.db.prepare(`
          UPDATE pineal_facets SET content = ?, conviction = ?, salience = ?, tags = ?, active = ?, pinned = ?, scope = ?
          WHERE id = ?
        `),
        getById: this.db.prepare(`SELECT * FROM pineal_facets WHERE id = ?`),
        retire: this.db.prepare(`UPDATE pineal_facets SET active = 0 WHERE id = ?`),
        reinforce: this.db.prepare(`
          UPDATE pineal_facets SET conviction = ?, last_reinforced = ?, reinforcements = reinforcements + 1
          WHERE id = ?
        `),
        pin: this.db.prepare(`UPDATE pineal_facets SET pinned = ? WHERE id = ?`),
        listByDomain: this.db.prepare(`
          SELECT * FROM pineal_facets WHERE domain = ? AND active = ? ORDER BY pinned DESC, conviction DESC, salience DESC
        `),
        listByCategory: this.db.prepare(`
          SELECT * FROM pineal_facets WHERE domain = ? AND category = ? AND active = ? ORDER BY pinned DESC, conviction DESC, salience DESC
        `),
        listAll: this.db.prepare(`SELECT * FROM pineal_facets ORDER BY domain, pinned DESC, conviction DESC`),
        listActive: this.db.prepare(`
          SELECT * FROM pineal_facets WHERE active = 1 ORDER BY domain, pinned DESC, conviction DESC, salience DESC
        `),
        getHistory: this.db.prepare(`
          WITH RECURSIVE chain(fid) AS (
            SELECT id FROM pineal_facets WHERE id = ?
            UNION ALL
            SELECT pf.id FROM pineal_facets pf
            JOIN chain c ON pf.id = (SELECT evolved_from FROM pineal_facets WHERE id = c.fid)
          ),
          forward(fid) AS (
            SELECT fid FROM chain
            UNION ALL
            SELECT pf.id FROM pineal_facets pf
            JOIN forward f ON pf.evolved_from = f.fid
          )
          SELECT DISTINCT pf.* FROM pineal_facets pf
          JOIN forward fw ON pf.id = fw.fid
          ORDER BY pf.version ASC
        `),
        domainStats: this.db.prepare(`
          SELECT domain,
            COUNT(*) as total,
            SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) as active_count,
            AVG(CASE WHEN active = 1 THEN conviction ELSE NULL END) as avg_conviction
          FROM pineal_facets
          GROUP BY domain
        `),
        countByDomain: this.db.prepare(`
          SELECT COUNT(*) as count FROM pineal_facets WHERE domain = ? AND active = 1
        `),
        skillSummaries: this.db.prepare(`
          SELECT category as name,
            COUNT(*) as facet_count,
            AVG(conviction) as avg_conviction
          FROM pineal_facets
          WHERE domain = 'praxis' AND active = 1
          GROUP BY category
          ORDER BY avg_conviction DESC
        `),
      }
    }
    return this._stmts
  }

  create(input: FacetInput): Facet {
    const now = new Date().toISOString()
    const id = generateId()
    const conviction = input.conviction ?? DOMAIN_INITIAL_CONVICTION[input.domain]
    const version = input.evolvedFrom ? this.getNextVersion(input.evolvedFrom) : 1

    this.stmts.insert.run(
      id,
      input.domain,
      input.category,
      input.content,
      conviction,
      input.salience ?? 0.5,
      input.provenance ?? 'self',
      JSON.stringify(input.tags ?? []),
      input.pinned ? 1 : 0,
      input.scope ?? null,
      input.evolvedFrom ?? null,
      version,
      now,
      now,
    )

    return this.get(id)!
  }

  get(id: string): Facet | null {
    const row = this.stmts.getById.get(id) as Record<string, unknown> | undefined
    return row ? rowToFacet(row) : null
  }

  update(id: string, updates: FacetUpdate): Facet | null {
    const existing = this.get(id)
    if (!existing) return null

    this.stmts.update.run(
      updates.content ?? existing.content,
      updates.conviction ?? existing.conviction,
      updates.salience ?? existing.salience,
      JSON.stringify(updates.tags ?? existing.tags),
      updates.active !== undefined ? (updates.active ? 1 : 0) : (existing.active ? 1 : 0),
      updates.pinned !== undefined ? (updates.pinned ? 1 : 0) : (existing.pinned ? 1 : 0),
      updates.scope !== undefined ? updates.scope : existing.scope,
      id,
    )

    return this.get(id)
  }

  retire(id: string): boolean {
    const result = this.stmts.retire.run(id)
    return result.changes > 0
  }

  reinforce(id: string, newConviction: number): Facet | null {
    const now = new Date().toISOString()
    this.stmts.reinforce.run(newConviction, now, id)
    return this.get(id)
  }

  evolve(id: string, newContent: string, input?: Partial<FacetInput>): Facet | null {
    const original = this.get(id)
    if (!original) return null

    this.retire(id)

    return this.create({
      domain: original.domain,
      category: input?.category ?? original.category,
      content: newContent,
      salience: input?.salience ?? original.salience,
      provenance: input?.provenance ?? original.provenance,
      tags: input?.tags ?? original.tags,
      pinned: input?.pinned ?? original.pinned,
      scope: input?.scope !== undefined ? input.scope : original.scope,
      evolvedFrom: id,
    })
  }

  list(query: FacetQuery = {}): Facet[] {
    const active = query.active !== undefined ? (query.active ? 1 : 0) : 1

    let rows: Record<string, unknown>[]

    if (query.domain && query.category) {
      rows = this.stmts.listByCategory.all(query.domain, query.category, active) as Record<string, unknown>[]
    } else if (query.domain) {
      rows = this.stmts.listByDomain.all(query.domain, active) as Record<string, unknown>[]
    } else if (query.active !== undefined) {
      rows = (active === 1 ? this.stmts.listActive : this.stmts.listAll).all() as Record<string, unknown>[]
    } else {
      rows = this.stmts.listActive.all() as Record<string, unknown>[]
    }

    let facets = rows.map(rowToFacet)

    if (query.pinned !== undefined) {
      facets = facets.filter(f => f.pinned === query.pinned)
    }
    if (query.scope !== undefined) {
      facets = facets.filter(f => f.scope === query.scope)
    }
    if (query.matchScope !== undefined) {
      // Assembly mode: include universal facets (scope=null) + matching channel
      facets = facets.filter(f => f.scope === null || f.scope === query.matchScope)
    }
    if (query.minConviction !== undefined) {
      facets = facets.filter(f => f.conviction >= query.minConviction!)
    }
    if (query.tags?.length) {
      facets = facets.filter(f => query.tags!.some(t => f.tags.includes(t)))
    }
    if (query.limit) {
      facets = facets.slice(0, query.limit)
    }

    return facets
  }

  getHistory(facetId: string): Facet[] {
    const rows = this.stmts.getHistory.all(facetId) as Record<string, unknown>[]
    return rows.map(rowToFacet)
  }

  getDomainStats(): DomainStats[] {
    const rows = this.stmts.domainStats.all() as Array<{
      domain: Domain
      total: number
      active_count: number
      avg_conviction: number | null
    }>

    return rows.map(row => {
      const categories = this.db.prepare(
        `SELECT DISTINCT category FROM pineal_facets WHERE domain = ? AND active = 1`
      ).all(row.domain) as Array<{ category: string }>

      return {
        domain: row.domain,
        totalFacets: row.total,
        activeFacets: row.active_count,
        avgConviction: row.avg_conviction ?? 0,
        categories: categories.map(c => c.category),
      }
    })
  }

  getSkillSummaries(): SkillSummary[] {
    const rows = this.stmts.skillSummaries.all() as Array<{
      name: string
      facet_count: number
      avg_conviction: number
    }>

    return rows.map(row => {
      const descFacet = this.db.prepare(`
        SELECT content FROM pineal_facets
        WHERE domain = 'praxis' AND category = ? AND active = 1
        AND tags LIKE '%"scope"%'
        LIMIT 1
      `).get(row.name) as { content: string } | undefined

      return {
        name: row.name,
        description: descFacet?.content ?? '',
        facetCount: row.facet_count,
        avgConviction: row.avg_conviction,
      }
    })
  }

  countActive(domain?: Domain): number {
    if (domain) {
      const row = this.stmts.countByDomain.get(domain) as { count: number }
      return row.count
    }
    const row = this.db.prepare(`SELECT COUNT(*) as count FROM pineal_facets WHERE active = 1`).get() as { count: number }
    return row.count
  }

  pin(id: string, pinned: boolean): boolean {
    const result = this.stmts.pin.run(pinned ? 1 : 0, id)
    return result.changes > 0
  }

  close(): void {
    this.db.close()
  }

  private migrate(): void {
    const cols = this.db.pragma('table_info(pineal_facets)') as Array<{ name: string }>
    const hasPinned = cols.some(c => c.name === 'pinned')
    if (!hasPinned) {
      this.db.exec(MIGRATION_SQL)
      this.logger.info('[pineal-store] Migrated: added pinned column')
    } else {
      this.db.exec(`CREATE INDEX IF NOT EXISTS idx_pineal_pinned ON pineal_facets(pinned, active)`)
    }
    const hasScope = cols.some(c => c.name === 'scope')
    if (!hasScope) {
      this.db.exec(MIGRATION_SCOPE_SQL)
      this.logger.info('[pineal-store] Migrated: added scope column')
    } else {
      this.db.exec(`CREATE INDEX IF NOT EXISTS idx_pineal_scope ON pineal_facets(scope, active)`)
    }
  }

  private getNextVersion(evolvedFromId: string): number {
    const row = this.db.prepare(
      `SELECT MAX(version) as max_version FROM pineal_facets WHERE id = ? OR evolved_from = ?`
    ).get(evolvedFromId, evolvedFromId) as { max_version: number | null }
    return (row.max_version ?? 0) + 1
  }
}
