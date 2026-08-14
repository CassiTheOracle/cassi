/**
 * TimelineStore — unified, chronological store of ALL CassiCore system data.
 *
 * Purpose: see everything that happened in a given time period at once,
 * and scroll through the timeline efficiently.
 *
 * Lives at ~/.cassicore/data/timeline.db
 *
 * Ingests from:
 *  - daemon.bus (EventBus)   — all typed RuntimeEvents
 *  - daemon internal bus     — cognitive/intelligence events
 *
 * All writes are buffered in memory and flushed in batches to avoid
 * blocking the event loop. A single writer loop drains the buffer
 * at a configurable interval.
 *
 * Queries use cursor-based pagination for efficient scrolling.
 */

import { existsSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'



export interface TimelineEntry {
  id: number
  ts_ms: number
  ts: string
  type: string
  source: string | null
  session_id: string | null
  provider: string | null
  severity: string | null
  summary: string | null
  payload_json: string | null
  metadata_json: string | null
}

export interface TimelineQueryOptions {
  /** Epoch ms lower bound (inclusive) */
  start?: number
  /** Epoch ms upper bound (inclusive) */
  end?: number
  /** Filter by event type(s) */
  types?: string[]
  /** Filter by source module */
  source?: string
  /** Filter by session ID */
  sessionId?: string
  /** Filter by provider ID */
  provider?: string
  /** Filter by severity */
  severity?: string
  /** Full-text search in payload */
  search?: string
  /** Page size (default 100, max 1000) */
  limit?: number
  /** Opaque cursor from a previous query */
  cursor?: string
  /** Sort direction: 'desc' (newest first, default) or 'asc' (oldest first) */
  order?: 'asc' | 'desc'
}

export interface TimelineQueryResult {
  entries: TimelineEntry[]
  /** Total entries matching filters in the range (capped at 10000 for perf) */
  total: number
  /** Next cursor for pagination (null if no more results) */
  nextCursor: string | null
  /** Whether there are more results beyond this page */
  hasMore: boolean
}

export interface TimelineRetentionConfig {
  /** Default TTL in days for all event types */
  defaultDays: number
  /** Per-type TTL overrides in days */
  perType: Record<string, number>
}

export interface TimelineStats {
  totalEntries: number
  oldestTs: number | null
  newestTs: number | null
  dbSizeBytes: number
  byType: Array<{ type: string; count: number }>
  bySource: Array<{ source: string; count: number }>
  bufferSize: number
}



interface CursorData {
  ts_ms: number
  id: number
}

/**
 * @dep callers: query (core/timeline-store.ts), buildWatchResult (core/intelligence/flux-team/blackboard.ts), blackboard-search.test.ts (tests/flux-team/blackboard-search.test.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function encodeCursor(data: CursorData): string {
  return Buffer.from(JSON.stringify(data)).toString('base64url')
}

/**
 * @dep callers: handleBlackboardRoutes (core/admin-api/blackboard.ts), query (core/timeline-store.ts), searchChannel (core/intelligence/flux-team/blackboard.ts), searchScratchpad (core/intelligence/flux-team/blackboard.ts), searchToolLog (core/intelligence/flux-team/blackboard.ts) [+5]
 * @dep module: Unknown
 * @dep risk: HIGH | 10 callers, 0 flows, 1 module
 */

function decodeCursor(cursor: string): CursorData | null {
  try {
    const json = Buffer.from(cursor, 'base64url').toString('utf8')
    const data = JSON.parse(json) as CursorData
    if (typeof data.ts_ms !== 'number' || typeof data.id !== 'number') return null
    return data
  } catch {
    return null
  }
}



const DEFAULT_BATCH_SIZE = 500
const DEFAULT_FLUSH_INTERVAL_MS = 2000
const DEFAULT_PAGE_SIZE = 100
const MAX_PAGE_SIZE = 1000
const MAX_COUNT_ESTIMATE = 10000
const DEFAULT_RETENTION_DAYS = 30
const CLEANUP_CHUNK_SIZE = 10000
const CLEANUP_CHUNK_DELAY_MS = 200



/** Extract a short human-readable summary from event data. */
function extractSummary(type: string, data: Record<string, unknown>): string | null {
  // Type-specific extractors for high-volume event types that previously produced blank summaries
  const safe = (val: unknown): string => (val != null ? String(val) : 'unknown')

  switch (type) {
    // Provider events
    case 'provider:request_start': {
      const model = safe(data.model)
      const providerId = safe(data.providerId)
      return `${model} on ${providerId}`
    }
    case 'provider:request_end': {
      const model = safe(data.model)
      const tokensIn = safe(data.tokens_in ?? data.tokensIn)
      const tokensOut = safe(data.tokens_out ?? data.tokensOut)
      const durationMs = safe(data.durationMs)
      return `${model}: ${tokensIn}→${tokensOut} (${durationMs}ms)`
    }

    // Tool events
    case 'tool:executed': {
      const toolName = safe(data.toolName)
      const durationMs = safe(data.durationMs)
      return `${toolName} (${durationMs}ms)`
    }
    case 'tool:registered': {
      const toolName = safe(data.toolName)
      return toolName
    }

    // Daemon events
    case 'daemon:health': {
      const sessions = safe(data.sessions)
      const providers = safe(data.providers)
      return `sessions:${sessions} providers:${providers}`
    }

    // Trust events
    case 'trust:outcome-recorded': {
      const domain = safe(data.domain)
      const outcome = safe(data.outcome)
      return `${domain}: ${outcome}`
    }
    case 'trust:score-updated': {
      const domain = safe(data.domain)
      const score = safe(data.score)
      return `${domain}: ${score}`
    }

    // Autonomy events
    case 'autonomy:trust-gate': {
      const action = safe(data.action)
      const decision = safe(data.decision)
      return `${action}: ${decision}`
    }
    case 'consequence:estimated': {
      const action = safe(data.action)
      const risk = safe(data.risk)
      return `${action}: risk=${risk}`
    }
    case 'permission:decision': {
      const action = safe(data.action)
      const decision = safe(data.decision)
      return `${action}: ${decision}`
    }

    // Channel events
    case 'channel:tool_update': {
      const toolName = safe(data.toolName)
      return toolName
    }

    // Lumen events
    case 'lumen:posture:iteration': {
      const posture = safe(data.posture)
      const iteration = safe(data.iteration)
      return `${posture} iter ${iteration}`
    }
    case 'lumen:dialectic:finding': {
      const fromPosture = safe(data.fromPosture)
      const topic = safe(data.topic)
      return `${fromPosture}: ${topic}`
    }
    case 'lumen:dialectic:challenge': {
      const fromPosture = safe(data.fromPosture)
      const target = safe(data.target)
      return `${fromPosture} challenges ${target}`
    }

    // Dyad events
    case 'dyad:work-unit': {
      const fromRole = safe(data.fromRole)
      const summary = safe(data.summary)
      return `${fromRole}: ${summary}`
    }
    case 'dyad:refinement': {
      const fromRole = safe(data.fromRole)
      const summary = safe(data.summary)
      return `${fromRole}: ${summary}`
    }

    // Session events
    case 'session:created': {
      const sessionId = safe(data.sessionId)
      return sessionId
    }

    // Helix events
    case 'helix:completed': {
      const entity = safe(data.entity)
      return `${entity} completed`
    }
    case 'helix:inactivity:warned': {
      const entity = safe(data.entity)
      return `${entity} inactive`
    }
    case 'helix:inactivity:escalated': {
      const entity = safe(data.entity)
      return `${entity} escalated`
    }
  }

  // For messages, capture a snippet
  if (data.message && typeof data.message === 'string') {
    return data.message.length > 200 ? `${data.message.slice(0, 200)}...` : data.message
  }
  if (data.response && typeof data.response === 'string') {
    return data.response.length > 200 ? `${data.response.slice(0, 200)}...` : data.response
  }
  if (data.error && typeof data.error === 'string') {
    return data.error.length > 200 ? `${data.error.slice(0, 200)}...` : data.error
  }
  if (data.reason && typeof data.reason === 'string') {
    return data.reason
  }
  if (data.pluginId && typeof data.pluginId === 'string') {
    return `plugin: ${data.pluginId}`
  }
  if (data.key && typeof data.key === 'string') {
    return `config: ${data.key}`
  }
  return null
}

/** Infer severity from event type. */
function inferSeverity(type: string, data: Record<string, unknown>): string {
  if (type.includes('error') || type.includes('crash') || type.includes('failed')) return 'error'
  if (type.includes('warn') || type.includes('degraded') || type.includes('timeout')) return 'warn'
  if (type.includes('debug')) return 'debug'
  if (data.error) return 'error'
  return 'info'
}

/** Infer source module from event type. */
function inferSource(type: string, data: Record<string, unknown>): string {
  if (type.startsWith('daemon:')) return 'daemon'
  if (type.startsWith('turn:')) return 'turn'
  if (type.startsWith('plugin:')) return 'plugin'
  if (type.startsWith('config:')) return 'config'
  if (type.startsWith('provider:')) return 'provider'
  if (type.startsWith('thinker:')) return 'thinker'
  if (type.startsWith('dialectic:')) return 'dialectic'
  if (type.startsWith('consciousness:') || type.startsWith('subconscious:')) return 'subconscious'
  if (type.startsWith('team:') || type.startsWith('drone:') || type.startsWith('agent:')) return 'multi-agent'
  if (type.startsWith('session:')) return 'session'
  if (type.startsWith('channel:')) return 'channel'
  if (type.startsWith('worker:')) return 'worker'
  if (type.startsWith('memory:')) return 'memory'
  if (type.startsWith('scout:')) return 'scout'
  if (type.startsWith('lumen:')) return 'lumen'
  if (type.startsWith('dyad:')) return 'dyad'
  if (type.startsWith('flux:')) return 'flux'
  // REMOVED: 'optimizer:' prefix — OptimizerModule deleted
  if (type.startsWith('autonomy:')) return 'autonomy'
  if (type.startsWith('macro-dialectic:')) return 'macro-dialectic'
  if (type.startsWith('reflect:')) return 'reflect'
  if (type.startsWith('helix:')) return 'helix'
  if ((data as Record<string, unknown>).source && typeof (data as Record<string, unknown>).source === 'string') {
    return (data as Record<string, unknown>).source as string
  }
  return 'system'
}



export class TimelineStore {
  private db: Database.Database
  private logger: ILogger

  // Write buffer
  private buffer: Array<{
    ts_ms: number
    ts: string
    type: string
    source: string | null
    session_id: string | null
    provider: string | null
    severity: string | null
    summary: string | null
    payload_json: string | null
    metadata_json: string | null
  }> = []
  private flushTimer: ReturnType<typeof setInterval> | null = null
  private batchSize: number
  private flushIntervalMs: number

  // Retention
  private retention: TimelineRetentionConfig

  // Prepared statements (lazily initialized after schema)
  private insertStmt!: Database.Statement
  private cleanupTimer: ReturnType<typeof setInterval> | null = null

  // SSE live-tail subscribers
  private liveSubscribers: Set<(entry: TimelineEntry) => void> = new Set()

  // Optional callback for retention events (so wiring code can emit bus events)
  public onRetention?: (deleted: number) => void


  constructor(
    dbPath: string,
    logger: ILogger,
    opts?: {
      batchSize?: number
      flushIntervalMs?: number
      retention?: Partial<TimelineRetentionConfig>
    },
  ) {
    this.logger = logger.child ? logger.child('timeline-store') : logger
    this.batchSize = opts?.batchSize ?? DEFAULT_BATCH_SIZE
    this.flushIntervalMs = opts?.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS
    this.retention = {
      defaultDays: opts?.retention?.defaultDays ?? DEFAULT_RETENTION_DAYS,
      perType: {
        'provider:request_start': 7,
        'provider:request_end': 7,
        'provider:request_prompt': 7,
        'provider:request_error': 180,
        'plugin:crashed': 180,
        'daemon:health': 3,
        ...opts?.retention?.perType,
      },
    }

    // Ensure directory exists
    const dir = dirname(dbPath)
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })

    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('temp_store = MEMORY')
    this.db.pragma('busy_timeout = 5000')
    this.db.pragma('cache_size = -8000') // 8MB cache

    this.initSchema()
    this.startFlushLoop()

    // Daily retention cleanup
    this.cleanupTimer = setInterval(() => {
      try { this.runRetention() } catch {}
    }, 24 * 60 * 60 * 1000)
    this.cleanupTimer.unref()

    this.logger.info('TimelineStore initialized', { dbPath })
  }



  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS timeline (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_ms       INTEGER NOT NULL,
        ts          TEXT    NOT NULL,
        type        TEXT    NOT NULL,
        source      TEXT,
        session_id  TEXT,
        provider    TEXT,
        severity    TEXT,
        summary     TEXT,
        payload_json TEXT,
        metadata_json TEXT
      );

      -- Primary chronological index (newest-first)
      CREATE INDEX IF NOT EXISTS idx_tl_ts_ms
        ON timeline(ts_ms DESC);

      -- Composite for type + time filtering
      CREATE INDEX IF NOT EXISTS idx_tl_type_ts
        ON timeline(type, ts_ms DESC);

      -- Session-scoped queries
      CREATE INDEX IF NOT EXISTS idx_tl_session_ts
        ON timeline(session_id, ts_ms DESC);

      -- Source module queries
      CREATE INDEX IF NOT EXISTS idx_tl_source_ts
        ON timeline(source, ts_ms DESC);

      -- Provider-scoped queries
      CREATE INDEX IF NOT EXISTS idx_tl_provider_ts
        ON timeline(provider, ts_ms DESC);

      -- Full-text search on payload
      CREATE VIRTUAL TABLE IF NOT EXISTS timeline_fts USING fts5(
        summary,
        payload_json,
        content='timeline',
        content_rowid='id'
      );

      -- Triggers to keep FTS in sync
      CREATE TRIGGER IF NOT EXISTS tl_ai AFTER INSERT ON timeline BEGIN
        INSERT INTO timeline_fts(rowid, summary, payload_json)
        VALUES (new.id, new.summary, new.payload_json);
      END;

      CREATE TRIGGER IF NOT EXISTS tl_ad AFTER DELETE ON timeline BEGIN
        INSERT INTO timeline_fts(timeline_fts, rowid, summary, payload_json)
        VALUES ('delete', old.id, old.summary, old.payload_json);
      END;
    `)

    this.insertStmt = this.db.prepare(`
      INSERT INTO timeline (
        ts_ms, ts, type, source, session_id, provider,
        severity, summary, payload_json, metadata_json
      ) VALUES (
        @ts_ms, @ts, @type, @source, @session_id, @provider,
        @severity, @summary, @payload_json, @metadata_json
      )
    `)
  }



  /**
   * Ingest a raw event into the timeline buffer.
   * Non-blocking — queues for the next batch flush.
   */
  ingest(event: Record<string, unknown>): void {
    const type = String(event.type ?? 'unknown')

    // Skip provider:request_prompt — full prompts are already captured in prompt-log.db
    // and account for ~70% of timeline.db size with minimal timeline value
    if (type === 'provider:request_prompt') return

    const now = Date.now()

    // Extract timestamp — support Date objects, epoch ms, or ISO strings
    let ts_ms: number
    const rawTs = event.timestamp
    if (rawTs instanceof Date) {
      ts_ms = rawTs.getTime()
    } else if (typeof rawTs === 'number') {
      ts_ms = rawTs
    } else if (typeof rawTs === 'string') {
      const parsed = new Date(rawTs).getTime()
      ts_ms = isNaN(parsed) ? now : parsed
    } else {
      ts_ms = now
    }

    const ts = new Date(ts_ms).toISOString()

    // Build the payload — exclude noisy/redundant fields
    const { type: _t, timestamp: _ts, ...rest } = event
    const payloadJson = Object.keys(rest).length > 0 ? JSON.stringify(rest) : null

    const source = inferSource(type, event)
    const severity = inferSeverity(type, event)
    const summary = extractSummary(type, event)

    // HOW: Coerce to primitives — event fields may contain objects from
    // tool inputs or malformed events. SQLite can only bind primitives.
    const sessionId = typeof event.sessionId === 'string' ? event.sessionId
      : event.sessionId != null ? JSON.stringify(event.sessionId)
      : null
    const providerId = typeof event.providerId === 'string' ? event.providerId
      : event.providerId != null ? String(event.providerId)
      : null

    this.buffer.push({
      ts_ms,
      ts,
      type,
      source,
      session_id: sessionId,
      provider: providerId,
      severity,
      summary,
      payload_json: payloadJson,
      metadata_json: null,
    })

    // Flush immediately if buffer hits batch size
    if (this.buffer.length >= this.batchSize) {
      this.flush()
    }
  }



  private startFlushLoop(): void {
    this.flushTimer = setInterval(() => {
      if (this.buffer.length > 0) {
        this.flush()
      }
    }, this.flushIntervalMs)
    this.flushTimer.unref()
  }

  /** Flush the buffer to SQLite in a single transaction. */
  flush(): void {
    if (this.buffer.length === 0) return

    const batch = this.buffer.splice(0)
    const insertMany = this.db.transaction((items: typeof batch) => {
      for (const item of items) {
        try {
          const result = this.insertStmt.run(item)

          // Notify live-tail subscribers
          if (this.liveSubscribers.size > 0) {
            const entry: TimelineEntry = {
              id: result.lastInsertRowid as number,
              ...item,
            }
            for (const sub of this.liveSubscribers) {
              try { sub(entry) } catch {}
            }
          }
        } catch (itemErr) {
          // WHY: One bad event should not block the entire batch. Log and skip.
          this.logger.debug('Timeline insert skipped — bad binding', {
            type: item.type, error: String(itemErr),
          })
        }
      }
    })

    try {
      insertMany(batch)
    } catch (err) {
      this.logger.error('Timeline flush failed', { error: String(err), batchSize: batch.length })
      // WHY: Only re-queue if the transaction error is transient (e.g. BUSY/LOCKED).
      // For binding errors, items were already handled individually above.
      const msg = String(err)
      if (msg.includes('BUSY') || msg.includes('LOCKED')) {
        this.buffer.unshift(...batch)
      }
    }
  }



  /**
   * Query the timeline with filters, cursor pagination, and optional FTS.
   */
  query(opts: TimelineQueryOptions = {}): TimelineQueryResult {
    const limit = Math.min(Math.max(opts.limit ?? DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    const order = opts.order ?? 'desc'
    const isDesc = order === 'desc'

    // Build WHERE conditions
    const conditions: string[] = []
    const params: Record<string, unknown> = {}

    if (opts.start != null) {
      conditions.push('t.ts_ms >= @start')
      params.start = opts.start
    }
    if (opts.end != null) {
      conditions.push('t.ts_ms <= @end')
      params.end = opts.end
    }
    if (opts.types && opts.types.length > 0) {
      const placeholders = opts.types.map((_, i) => `@type_${i}`)
      conditions.push(`t.type IN (${placeholders.join(', ')})`)
      opts.types.forEach((t, i) => { params[`type_${i}`] = t })
    }
    if (opts.source) {
      conditions.push('t.source = @source')
      params.source = opts.source
    }
    if (opts.sessionId) {
      conditions.push('t.session_id = @sessionId')
      params.sessionId = opts.sessionId
    }
    if (opts.provider) {
      conditions.push('t.provider = @provider')
      params.provider = opts.provider
    }
    if (opts.severity) {
      conditions.push('t.severity = @severity')
      params.severity = opts.severity
    }

    // Cursor-based pagination
    const cursorData = opts.cursor ? decodeCursor(opts.cursor) : null
    if (cursorData) {
      if (isDesc) {
        conditions.push('(t.ts_ms < @cursor_ts OR (t.ts_ms = @cursor_ts AND t.id < @cursor_id))')
      } else {
        conditions.push('(t.ts_ms > @cursor_ts OR (t.ts_ms = @cursor_ts AND t.id > @cursor_id))')
      }
      params.cursor_ts = cursorData.ts_ms
      params.cursor_id = cursorData.id
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
    const orderClause = isDesc ? 'ORDER BY t.ts_ms DESC, t.id DESC' : 'ORDER BY t.ts_ms ASC, t.id ASC'

    let entries: TimelineEntry[]

    if (opts.search) {
      // FTS-based query — join with timeline_fts
      const sql = `
        SELECT t.*
        FROM timeline t
        INNER JOIN timeline_fts f ON f.rowid = t.id
        ${whereClause}${conditions.length > 0 ? ' AND' : 'WHERE'} timeline_fts MATCH @search
        ${orderClause}
        LIMIT @limit_plus_one
      `
      params.search = opts.search
      params.limit_plus_one = limit + 1
      entries = this.db.prepare(sql).all(params) as TimelineEntry[]
    } else {
      const sql = `
        SELECT t.*
        FROM timeline t
        ${whereClause}
        ${orderClause}
        LIMIT @limit_plus_one
      `
      params.limit_plus_one = limit + 1
      entries = this.db.prepare(sql).all(params) as TimelineEntry[]
    }

    // Check if there are more results
    const hasMore = entries.length > limit
    if (hasMore) entries = entries.slice(0, limit)

    // Build next cursor from the last entry
    let nextCursor: string | null = null
    if (hasMore && entries.length > 0) {
      const last = entries[entries.length - 1]
      nextCursor = encodeCursor({ ts_ms: last.ts_ms, id: last.id })
    }

    // Estimate total count (capped for performance)
    let total = entries.length
    if (!cursorData && !hasMore) {
      // Exact count — small result set
      total = entries.length
    } else {
      // Estimate via COUNT with cap
      try {
        const countConditions = conditions.filter(c => !c.includes('cursor_'))
        const countWhere = countConditions.length > 0 ? `WHERE ${countConditions.join(' AND ')}` : ''
        const countParams = { ...params }
        delete countParams.cursor_ts
        delete countParams.cursor_id
        delete countParams.limit_plus_one

        if (opts.search) {
          const countSql = `
            SELECT MIN(COUNT(*), ${MAX_COUNT_ESTIMATE}) as cnt
            FROM timeline t
            INNER JOIN timeline_fts f ON f.rowid = t.id
            ${countWhere}${countConditions.length > 0 ? ' AND' : 'WHERE'} timeline_fts MATCH @search
          `
          const row = this.db.prepare(countSql).get(countParams) as { cnt: number } | undefined
          total = row?.cnt ?? entries.length
        } else {
          const countSql = `
            SELECT MIN(COUNT(*), ${MAX_COUNT_ESTIMATE}) as cnt
            FROM timeline t
            ${countWhere}
          `
          const row = this.db.prepare(countSql).get(countParams) as { cnt: number } | undefined
          total = row?.cnt ?? entries.length
        }
      } catch {
        total = entries.length
      }
    }

    return { entries, total, nextCursor, hasMore }
  }


  /**
   * Get a single timeline entry by ID.
   */
  getById(id: number): TimelineEntry | undefined {
    return this.db.prepare('SELECT * FROM timeline WHERE id = ?').get(id) as TimelineEntry | undefined
  }


  /**
   * Get distinct event types in the store.
   */
  getEventTypes(): Array<{ type: string; count: number }> {
    return this.db.prepare(
      'SELECT type, COUNT(*) as count FROM timeline GROUP BY type ORDER BY count DESC'
    ).all() as Array<{ type: string; count: number }>
  }

  /**
   * Get distinct source modules in the store.
   */
  getSources(): Array<{ source: string; count: number }> {
    return this.db.prepare(
      'SELECT source, COUNT(*) as count FROM timeline WHERE source IS NOT NULL GROUP BY source ORDER BY count DESC'
    ).all() as Array<{ source: string; count: number }>
  }



  /**
   * Subscribe to new timeline entries as they're flushed.
   * Returns an unsubscribe function.
   */
  subscribe(handler: (entry: TimelineEntry) => void): () => void {
    this.liveSubscribers.add(handler)
    return () => { this.liveSubscribers.delete(handler) }
  }



  /**
   * Update retention configuration.
   */
  setRetention(config: Partial<TimelineRetentionConfig>): void {
    if (config.defaultDays != null) this.retention.defaultDays = config.defaultDays
    if (config.perType) {
      this.retention = {
        ...this.retention,
        perType: { ...this.retention.perType, ...config.perType },
      }
    }
  }

  /**
   * Get current retention configuration.
   */
  getRetention(): TimelineRetentionConfig {
    return { ...this.retention, perType: { ...this.retention.perType } }
  }

  /**
   * Run retention cleanup — chunked deletes to avoid locking.
   */
  runRetention(): { deleted: number } {
    let totalDeleted = 0

    // Per-type retention
    for (const [type, days] of Object.entries(this.retention.perType)) {
      const cutoff = Date.now() - days * 24 * 60 * 60 * 1000
      let chunk = 1
      while (chunk > 0) {
        const result = this.db.prepare(
          `DELETE FROM timeline WHERE id IN (
            SELECT id FROM timeline WHERE type = ? AND ts_ms < ? LIMIT ?
          )`
        ).run(type, cutoff, CLEANUP_CHUNK_SIZE)
        chunk = result.changes
        totalDeleted += chunk
        if (chunk >= CLEANUP_CHUNK_SIZE) {
          // Yield to other operations between large deletes
          // (sync sleep — acceptable for background cleanup)
          const start = Date.now()
          while (Date.now() - start < CLEANUP_CHUNK_DELAY_MS) { /* busy wait */ }
        }
      }
    }

    // Default retention for types not explicitly configured
    const configuredTypes = Object.keys(this.retention.perType)
    const cutoff = Date.now() - this.retention.defaultDays * 24 * 60 * 60 * 1000
    const typeNotIn = configuredTypes.length > 0
      ? `AND type NOT IN (${configuredTypes.map(() => '?').join(', ')})`
      : ''

    let chunk = 1
    while (chunk > 0) {
      const result = this.db.prepare(
        `DELETE FROM timeline WHERE id IN (
          SELECT id FROM timeline WHERE ts_ms < ? ${typeNotIn} LIMIT ?
        )`
      ).run(cutoff, ...configuredTypes, CLEANUP_CHUNK_SIZE)
      chunk = result.changes
      totalDeleted += chunk
      if (chunk >= CLEANUP_CHUNK_SIZE) {
        const start = Date.now()
        while (Date.now() - start < CLEANUP_CHUNK_DELAY_MS) { /* busy wait */ }
      }
    }

    if (totalDeleted > 0) {
      this.logger.info(`Timeline retention: deleted ${totalDeleted} entries`)
      this.onRetention?.(totalDeleted)
    }

    return { deleted: totalDeleted }
  }



  getStats(): TimelineStats {
    const totalRow = this.db.prepare('SELECT COUNT(*) as cnt FROM timeline').get() as { cnt: number }
    const rangeRow = this.db.prepare('SELECT MIN(ts_ms) as oldest, MAX(ts_ms) as newest FROM timeline').get() as { oldest: number | null; newest: number | null }

    // DB file size via PRAGMA
    const pageCount = (this.db.prepare('PRAGMA page_count').get() as Record<string, number>).page_count
    const pageSize = (this.db.prepare('PRAGMA page_size').get() as Record<string, number>).page_size
    const dbSizeBytes = pageCount * pageSize

    const byType = this.db.prepare(
      'SELECT type, COUNT(*) as count FROM timeline GROUP BY type ORDER BY count DESC LIMIT 50'
    ).all() as Array<{ type: string; count: number }>

    const bySource = this.db.prepare(
      'SELECT source, COUNT(*) as count FROM timeline WHERE source IS NOT NULL GROUP BY source ORDER BY count DESC LIMIT 20'
    ).all() as Array<{ source: string; count: number }>

    return {
      totalEntries: totalRow.cnt,
      oldestTs: rangeRow.oldest,
      newestTs: rangeRow.newest,
      dbSizeBytes,
      byType,
      bySource,
      bufferSize: this.buffer.length,
    }
  }



  /**
   * Flush remaining buffer and close the database.
   */
  close(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer)
      this.flushTimer = null
    }
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer)
      this.cleanupTimer = null
    }

    // Final flush
    try { this.flush() } catch {}

    this.liveSubscribers.clear()

    try { this.db.close() } catch {}
    this.logger.info('TimelineStore closed')
  }
}
