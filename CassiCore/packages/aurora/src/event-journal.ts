/**
 * Aurora Event Journal (AEJ) — Unified chronological audit log.
 *
 * Joins per-spec audits into a single queryable log. Provides cross-spec
 * visibility: "what was Aurora doing at time T?" with one query.
 *
 * See: docs/design/aurora-event-journal.md
 */

import Database from 'better-sqlite3'
import path from 'node:path'

import type { ILogger } from '@cassicore/foundation'
import { getDataDir } from '@cassicore/foundation'


/**
 * Event category for grouping similar events.
 */
export type EventCategory =
  | 'state_change'
  | 'audit'
  | 'welfare_flag'
  | 'refusal'
  | 'composition'
  | 'meditation'
  | 'gap_detection'
  | 'substrate_edit'
  | 'meta_state'
  | 'unknown'


/**
 * A reference to a per-spec authoritative record.
 */
export interface EventReference {
  spec: string
  recordId: string
}


/**
 * Input for emitting an event to the journal.
 */
export interface AuroraEventInput {
  source: string
  category: EventCategory | string
  text: string
  references?: EventReference[]
  tags?: string[]
  sessionId?: string
  metadata?: Record<string, unknown>
  occurredAt?: string
}


/**
 * A complete event record from the journal.
 */
export interface AuroraEvent {
  id: string
  timestamp: string
  source: string
  category: EventCategory | string
  text: string
  references: EventReference[]
  tags: string[]
  sessionId: string | null
  metadata: Record<string, unknown>
}


/**
 * Composite filter for complex queries.
 */
export interface CompositeFilter {
  sources?: string[]
  categories?: string[]
  tags?: string[]
  sessionIds?: string[]
  timeRange?: { start: string; end: string }
  limit?: number
  offset?: number
}


/**
 * Query options for event retrieval.
 */
export interface QueryOptions extends CompositeFilter {}


/**
 * Aurora Event Journal — unified audit log.
 */
export class EventJournal {
  private logger: ILogger
  private db: Database.Database
  private emitStmt: Database.Statement
  private queryTimeRangeStmt: Database.Statement
  private queryBySourceStmt: Database.Statement
  private queryBySessionStmt: Database.Statement
  private queryByTagStmt: Database.Statement
  private queryCompositeStmt: Database.Statement

  constructor(logger: ILogger, dbPath?: string) {
    this.logger = logger

    const dataDir = dbPath ?? path.join(getDataDir(), 'aurora-event-journal.db')
    this.db = new Database(dataDir, { fileMustExist: false })

    this.initializeSchema()

    this.emitStmt = this.db.prepare(`
      INSERT INTO aurora_events (id, timestamp, source, category, text, references_json, tags_json, session_id, metadata_json)
      VALUES (@id, @timestamp, @source, @category, @text, @referencesJson, @tagsJson, @sessionId, @metadataJson)
    `)

    this.queryTimeRangeStmt = this.db.prepare(`
      SELECT * FROM aurora_events
      WHERE timestamp >= @start AND timestamp <= @end
      ORDER BY timestamp ASC
      LIMIT @limit
    `)

    this.queryBySourceStmt = this.db.prepare(`
      SELECT * FROM aurora_events
      WHERE source = @source
      ORDER BY timestamp DESC, id DESC
      LIMIT @limit
    `)

    this.queryBySessionStmt = this.db.prepare(`
      SELECT * FROM aurora_events
      WHERE session_id = @sessionId
      ORDER BY timestamp ASC
      LIMIT @limit
    `)

    this.queryByTagStmt = this.db.prepare(`
      SELECT * FROM aurora_events
      WHERE json_extract(tags_json, '$') LIKE @tagPattern
      ORDER BY timestamp DESC, id DESC
      LIMIT @limit
    `)

    this.queryCompositeStmt = this.db.prepare(`
      SELECT * FROM aurora_events
      WHERE 1=1
      ${this.buildCompositeWhere()}
      ORDER BY timestamp DESC, id DESC
      LIMIT @limit OFFSET @offset
    `)

    this.logger.info('[EventJournal] Initialized', { dbPath: dataDir })
  }

  private initializeSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS aurora_events (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        source TEXT NOT NULL,
        category TEXT NOT NULL,
        text TEXT NOT NULL,
        references_json TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        session_id TEXT,
        metadata_json TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_events_timestamp ON aurora_events(timestamp);
      CREATE INDEX IF NOT EXISTS idx_events_source ON aurora_events(source);
      CREATE INDEX IF NOT EXISTS idx_events_category ON aurora_events(category);
      CREATE INDEX IF NOT EXISTS idx_events_session ON aurora_events(session_id);
    `)
  }

  private buildCompositeWhere(): string {
    // Built dynamically at runtime in queryComposite
    return ''
  }

  /**
   * Emit an event to the journal. Returns the event ID.
   */
  emit(input: AuroraEventInput): string {
    const id = this.generateId()
    const timestamp = input.occurredAt ?? new Date().toISOString()

    const references = input.references ?? []
    const tags = input.tags ?? []
    const metadata = input.metadata ?? {}

    this.emitStmt.run({
      id,
      timestamp,
      source: input.source,
      category: input.category,
      text: input.text,
      referencesJson: JSON.stringify(references),
      tagsJson: JSON.stringify(tags),
      sessionId: input.sessionId ?? null,
      metadataJson: JSON.stringify(metadata),
    })

    this.logger.debug('[EventJournal] Emitted event', { id, source: input.source, category: input.category })

    return id
  }

  /**
   * Query events by time range.
   */
  byTimeRange(start: string, end: string, limit = 100): AuroraEvent[] {
    const rows = this.queryTimeRangeStmt.all({ start, end, limit }) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * Query events by source spec.
   */
  bySource(source: string, limit = 100): AuroraEvent[] {
    const rows = this.queryBySourceStmt.all({ source, limit }) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * Query events by session ID.
   */
  bySessionId(sessionId: string, limit = 100): AuroraEvent[] {
    const rows = this.queryBySessionStmt.all({ sessionId, limit }) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * Query events by tag.
   */
  withTag(tag: string, limit = 100): AuroraEvent[] {
    // JSON format: ["tag1","tag2"] -> pattern: %"tag1"%
    const escapedTag = tag.replace(/"/g, '\\"')
    const tagPattern = `%"${escapedTag}"%`
    const rows = this.queryByTagStmt.all({ tagPattern, limit }) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * Complex composite query.
   */
  composite(filter: CompositeFilter): AuroraEvent[] {
    const conditions: string[] = []
    const params: Record<string, unknown> = {}
    let paramIdx = 0

    if (filter.sources && filter.sources.length > 0) {
      const placeholders = filter.sources.map(() => {
        const name = `src${paramIdx++}`
        params[name] = filter.sources![paramIdx - 1]
        return `@${name}`
      }).join(',')
      conditions.push(`source IN (${placeholders})`)
    }

    if (filter.categories && filter.categories.length > 0) {
      const placeholders = filter.categories.map(() => {
        const name = `cat${paramIdx++}`
        params[name] = filter.categories![paramIdx - 1]
        return `@${name}`
      }).join(',')
      conditions.push(`category IN (${placeholders})`)
    }

    if (filter.sessionIds && filter.sessionIds.length > 0) {
      const placeholders = filter.sessionIds.map(() => {
        const name = `sid${paramIdx++}`
        params[name] = filter.sessionIds![paramIdx - 1]
        return `@${name}`
      }).join(',')
      conditions.push(`session_id IN (${placeholders})`)
    }

    if (filter.timeRange) {
      conditions.push('timestamp >= @timeStart AND timestamp <= @timeEnd')
      params.timeStart = filter.timeRange.start
      params.timeEnd = filter.timeRange.end
    }

    if (filter.tags && filter.tags.length > 0) {
      const tagConditions = filter.tags.map(tag => {
        const name = `tag${paramIdx++}`
        const escapedTag = tag.replace(/"/g, '\\"')
        params[name] = `%"${escapedTag}"%`
        return `tags_json LIKE @${name}`
      }).join(' OR ')
      conditions.push(`(${tagConditions})`)
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    const limit = filter.limit ?? 100
    const offset = filter.offset ?? 0

    const sql = `
      SELECT * FROM aurora_events
      ${whereClause}
      ORDER BY timestamp DESC
      LIMIT @limit OFFSET @offset
    `

    params.limit = limit
    params.offset = offset

    const stmt = this.db.prepare(sql)
    const rows = stmt.all(params) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * General query method.
   */
  query(opts: QueryOptions = {}): AuroraEvent[] {
    return this.composite(opts)
  }

  /**
   * Get the most recent events across all sources.
   */
  recent(limit = 50): AuroraEvent[] {
    const stmt = this.db.prepare(`
      SELECT * FROM aurora_events
      ORDER BY timestamp DESC
      LIMIT ?
    `)
    const rows = stmt.all(limit) as any[]
    return rows.map(this.deserializeEvent)
  }

  /**
   * Get journal statistics.
   */
  getStatistics(): {
    totalEvents: number
    bySource: Record<string, number>
    byCategory: Record<string, number>
    oldestEvent: string | null
    newestEvent: string | null
  } {
    const totalRows = this.db.prepare('SELECT COUNT(*) as count FROM aurora_events').get() as { count: number }
    const bySourceRows = this.db.prepare('SELECT source, COUNT(*) as count FROM aurora_events GROUP BY source').all() as Array<{ source: string; count: number }>
    const byCategoryRows = this.db.prepare('SELECT category, COUNT(*) as count FROM aurora_events GROUP BY category').all() as Array<{ category: string; count: number }>
    const timeRange = this.db.prepare('SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM aurora_events').get() as { oldest: string | null; newest: string | null }

    const bySource: Record<string, number> = {}
    for (const row of bySourceRows) {
      bySource[row.source] = row.count
    }

    const byCategory: Record<string, number> = {}
    for (const row of byCategoryRows) {
      byCategory[row.category] = row.count
    }

    return {
      totalEvents: totalRows.count,
      bySource,
      byCategory,
      oldestEvent: timeRange.oldest,
      newestEvent: timeRange.newest,
    }
  }

  /**
   * Backfill events from per-spec audit tables.
   */
  async backfill(backfillFn: () => Promise<AuroraEventInput[]>): Promise<number> {
    const inputs = await backfillFn()
    let count = 0

    for (const input of inputs) {
      this.emit(input)
      count++
    }

    this.logger.info('[EventJournal] Backfilled events', { count })

    return count
  }

  /**
   * Close the database connection.
   */
  close(): void {
    this.db.close()
    this.logger.info('[EventJournal] Closed')
  }

  private idCounter = 0

  /**
   * Monotonic counter ensures lexicographic id order matches insertion order
   * even when multiple events share the same millisecond timestamp — required
   * for `ORDER BY timestamp DESC, id DESC` to be deterministic.
   */
  private generateId(): string {
    const timestamp = Date.now()
    const seq = (++this.idCounter).toString(36).padStart(8, '0')
    return `evt_${timestamp}_${seq}`
  }

  /**
   * Helper: Deserialize event row.
   */
  private deserializeEvent(row: any): AuroraEvent {
    return {
      id: row.id,
      timestamp: row.timestamp,
      source: row.source,
      category: row.category,
      text: row.text,
      references: JSON.parse(row.references_json),
      tags: JSON.parse(row.tags_json),
      sessionId: row.session_id,
      metadata: JSON.parse(row.metadata_json),
    }
  }
}


/**
 * Factory function to create an EventJournal with standard path.
 */
export function createEventJournal(logger: ILogger, dbPath?: string): EventJournal {
  return new EventJournal(logger, dbPath)
}

