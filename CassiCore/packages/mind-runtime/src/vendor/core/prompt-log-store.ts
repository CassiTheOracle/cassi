/**
 * PromptLogStore — persistent, structured storage for every prompt sent to a provider.
 *
 * Captures the exact message array right before `provider.complete()` is called,
 * with ZERO content truncation. Every provider call across the entire system is
 * logged: session pipeline, Lumen postures, Dialectic, Thinker, Subconscious, etc.
 *
 * Stored in a dedicated SQLite database (`~/.cassicore/data/prompt-log.db`) for
 * size isolation from the main session/memory databases.
 */

import { createHash } from 'node:crypto'
import { existsSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'
import type { Message, ContentBlock, CompletionOpts } from '@cassicore/foundation'


export interface PromptLogEntry {
  id: string
  timestamp: number

  // Source identification
  providerId: string
  model: string
  source: string | null
  trigger: string | null

  // Session context (nullable for background calls)
  sessionId: string | null

  // The actual prompt — full, untruncated
  messages: SerializedMessage[]

  // Quick-lookup metadata
  messageCount: number
  systemPromptPreview: string | null
  totalChars: number
  estimatedTokens: number
  hasTools: boolean
  toolCount: number

  // Model parameters
  temperature: number | null
  maxTokens: number | null
  thinkingLevel: string | null
}

/** Compact list entry — no messages_json for performance */
export interface PromptLogListEntry {
  id: string
  timestamp: number
  providerId: string
  model: string
  source: string | null
  trigger: string | null
  sessionId: string | null
  messageCount: number
  systemPromptPreview: string | null
  totalChars: number
  estimatedTokens: number
  hasTools: boolean
  toolCount: number
  temperature: number | null
  maxTokens: number | null
  thinkingLevel: string | null
}

export interface PromptLogSessionSummary {
  sessionId: string
  entryCount: number
  firstTimestamp: number
  lastTimestamp: number
  sources: string[]
  models: string[]
  totalEstimatedTokens: number
}

export interface PromptLogStats {
  totalEntries: number
  totalSizeBytes: number
  oldestTimestamp: number
  newestTimestamp: number
  bySource: Array<{ source: string; count: number }>
  byProvider: Array<{ providerId: string; count: number }>
}

export interface SerializedMessage {
  role: 'system' | 'user' | 'assistant'
  content: string | SerializedContentBlock[]
  estimatedTokens?: number
}

export interface SerializedContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'thinking'
  text?: string
  toolUseId?: string
  toolName?: string
  input?: string
  content?: string
  isError?: boolean
}


const DEFAULT_RETENTION_DAYS = 7
const CHARS_PER_TOKEN = 3
const SYSTEM_PROMPT_PREVIEW_LENGTH = 200


export class PromptLogStore {
  private db: Database.Database
  private logger: ILogger
  private insertStmt!: Database.Statement
  private getByIdStmt!: Database.Statement
  private updateResponseStmt!: Database.Statement
  private retentionDays: number
  private seq = 0

  constructor(
    dbPath: string,
    logger: ILogger,
    opts?: { retentionDays?: number },
  ) {
    this.logger = logger.child ? logger.child('prompt-log-store') : logger
    this.retentionDays = opts?.retentionDays ?? DEFAULT_RETENTION_DAYS

    // Ensure directory exists
    const dir = dirname(dbPath)
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })

    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.initSchema()

    this.logger.info('PromptLogStore initialized', { dbPath, retentionDays: this.retentionDays })
  }


  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS prompt_log (
        id                  TEXT PRIMARY KEY,
        timestamp           INTEGER NOT NULL,

        -- Source identification
        provider_id         TEXT NOT NULL,
        model               TEXT NOT NULL,
        source              TEXT,
        trigger_field       TEXT,

        -- Session context (nullable for background calls)
        session_id          TEXT,

        -- The actual prompt (FULL, UNTRUNCATED)
        messages_json       TEXT NOT NULL,
        storage_kind        TEXT NOT NULL DEFAULT 'full',
        content_hash        TEXT,
        base_prompt_id      TEXT,
        delta_messages_json TEXT,
        chain_depth         INTEGER NOT NULL DEFAULT 0,

        -- Quick-lookup metadata
        message_count       INTEGER NOT NULL,
        system_prompt_preview TEXT,
        total_chars         INTEGER NOT NULL,
        estimated_tokens    INTEGER NOT NULL,
        has_tools           INTEGER DEFAULT 0,
        tool_count          INTEGER DEFAULT 0,

        -- Model parameters
        temperature         REAL,
        max_tokens          INTEGER,
        thinking_level      TEXT,

        -- LLM response (populated after streaming completes)
        response_json       TEXT,
        response_tokens     INTEGER,
        response_stop_reason TEXT,
        response_duration_ms INTEGER
      );

      CREATE INDEX IF NOT EXISTS idx_pl_session   ON prompt_log(session_id, timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_source    ON prompt_log(source, timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_time      ON prompt_log(timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_provider  ON prompt_log(provider_id, timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_hash      ON prompt_log(content_hash, timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_base      ON prompt_log(base_prompt_id);
    `)

    const columns = this.db.prepare(`PRAGMA table_info(prompt_log)`).all() as Array<{ name: string }>
    const existing = new Set(columns.map((c) => c.name))
    const missingColumns: Array<{ name: string; sql: string }> = [
      { name: 'storage_kind', sql: `ALTER TABLE prompt_log ADD COLUMN storage_kind TEXT NOT NULL DEFAULT 'full'` },
      { name: 'content_hash', sql: 'ALTER TABLE prompt_log ADD COLUMN content_hash TEXT' },
      { name: 'base_prompt_id', sql: 'ALTER TABLE prompt_log ADD COLUMN base_prompt_id TEXT' },
      { name: 'delta_messages_json', sql: 'ALTER TABLE prompt_log ADD COLUMN delta_messages_json TEXT' },
      { name: 'chain_depth', sql: 'ALTER TABLE prompt_log ADD COLUMN chain_depth INTEGER NOT NULL DEFAULT 0' },
      { name: 'response_json', sql: 'ALTER TABLE prompt_log ADD COLUMN response_json TEXT' },
      { name: 'response_tokens', sql: 'ALTER TABLE prompt_log ADD COLUMN response_tokens INTEGER' },
      { name: 'response_stop_reason', sql: 'ALTER TABLE prompt_log ADD COLUMN response_stop_reason TEXT' },
      { name: 'response_duration_ms', sql: 'ALTER TABLE prompt_log ADD COLUMN response_duration_ms INTEGER' },
    ]
    for (const column of missingColumns) {
      if (!existing.has(column.name)) this.db.exec(column.sql)
    }
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_pl_hash ON prompt_log(content_hash, timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_pl_base ON prompt_log(base_prompt_id);
    `)

    this.insertStmt = this.db.prepare(`
      INSERT INTO prompt_log (
        id, timestamp, provider_id, model, source, trigger_field, session_id,
        messages_json, storage_kind, content_hash, base_prompt_id, delta_messages_json,
        chain_depth, message_count, system_prompt_preview, total_chars,
        estimated_tokens, has_tools, tool_count, temperature, max_tokens,
        thinking_level
      ) VALUES (
        @id, @timestamp, @providerId, @model, @source, @triggerField, @sessionId,
        @messagesJson, @storageKind, @contentHash, @basePromptId, @deltaMessagesJson,
        @chainDepth, @messageCount, @systemPromptPreview, @totalChars,
        @estimatedTokens, @hasTools, @toolCount, @temperature, @maxTokens,
        @thinkingLevel
      )
    `)

    this.getByIdStmt = this.db.prepare('SELECT * FROM prompt_log WHERE id = ?')
    this.updateResponseStmt = this.db.prepare(`
      UPDATE prompt_log SET
        response_json = @responseJson,
        response_tokens = @responseTokens,
        response_stop_reason = @stopReason,
        response_duration_ms = @durationMs
      WHERE id = @id
    `)
  }


  /**
   * Capture a prompt right before it's sent to the provider.
   * Called by the provider wrapper — fire-and-forget, never throws.
   */
  capture(
    providerId: string,
    messages: Message[],
    opts: CompletionOpts,
  ): string | null {
    const id = `pl_${Date.now()}_${++this.seq}`
    const timestamp = Date.now()

    try {
      const serialized = this.serializeMessages(messages)
      const totalChars = this.countChars(serialized)
      const estimatedTokens = Math.ceil(totalChars / CHARS_PER_TOKEN)
      const messagesJson = JSON.stringify(serialized)
      const contentHash = this.hashMessages(messagesJson)
      const storage = this.chooseStorage(providerId, serialized, messagesJson, contentHash, opts)

      // Extract system prompt preview
      const systemMsg = serialized.find(m => m.role === 'system')
      const systemPromptPreview = systemMsg
        ? (typeof systemMsg.content === 'string'
          ? systemMsg.content.slice(0, SYSTEM_PROMPT_PREVIEW_LENGTH)
          : '[structured content]')
        : null

      // Extract thinking level
      const thinkingLevel = typeof opts.thinking === 'string'
        ? opts.thinking
        : opts.thinking ? 'enabled' : null

      this.insertStmt.run({
        id,
        timestamp,
        providerId,
        model: opts.model ?? 'unknown',
        source: opts.source ?? null,
        triggerField: opts.trigger ?? null,
        sessionId: opts.sessionId ?? null,
        messagesJson: storage.messagesJson,
        storageKind: storage.kind,
        contentHash,
        basePromptId: storage.basePromptId,
        deltaMessagesJson: storage.deltaMessagesJson,
        chainDepth: storage.chainDepth,
        messageCount: serialized.length,
        systemPromptPreview,
        totalChars,
        estimatedTokens,
        hasTools: opts.tools && opts.tools.length > 0 ? 1 : 0,
        toolCount: opts.tools?.length ?? 0,
        temperature: opts.temperature ?? null,
        maxTokens: opts.maxTokens ?? null,
        thinkingLevel,
      })

      return id
    } catch (err) {
      this.logger.error('Failed to capture prompt log', { error: String(err), id, providerId })
      return null
    }
  }


  /**
   * Capture the LLM response after streaming completes.
   * Called by the provider wrapper with the accumulated response content blocks.
   */
  captureResponse(
    promptLogId: string,
    contentBlocks: ContentBlock[],
    stopReason: string | null,
    durationMs: number,
    outputTokens?: number,
  ): void {
    try {
      const serialized = contentBlocks.map(block => {
        const b = block as any
        if (b.type === 'text') return { type: 'text', text: b.text }
        if (b.type === 'tool_use') return { type: 'tool_use', toolName: b.name, toolUseId: b.id, input: JSON.stringify(b.input) }
        if (b.type === 'thinking') return { type: 'thinking', text: b.thinking ?? b.text }
        return { type: b.type }
      })
      this.updateResponseStmt.run({
        id: promptLogId,
        responseJson: JSON.stringify(serialized),
        responseTokens: outputTokens ?? null,
        stopReason: stopReason ?? null,
        durationMs: Math.round(durationMs),
      })
    } catch (err) {
      this.logger.error('Failed to capture prompt log response', { error: String(err), id: promptLogId })
    }
  }


  /**
   * Get a single entry by ID, including full messages.
   */
  getById(id: string): PromptLogEntry | undefined {
    const row = this.getByIdStmt.get(id) as Record<string, unknown> | undefined
    if (!row) return undefined
    return this.rowToEntry(row)
  }

  /**
   * List entries with filtering (no messages_json for performance).
   */
  list(filters?: {
    sessionId?: string
    source?: string
    providerId?: string
    model?: string
    since?: number
    until?: number
    limit?: number
  }): PromptLogListEntry[] {
    const conditions: string[] = []
    const params: unknown[] = []

    if (filters?.sessionId) {
      conditions.push('session_id = ?')
      params.push(filters.sessionId)
    }
    if (filters?.source) {
      conditions.push('source = ?')
      params.push(filters.source)
    }
    if (filters?.providerId) {
      conditions.push('provider_id = ?')
      params.push(filters.providerId)
    }
    if (filters?.model) {
      conditions.push('model = ?')
      params.push(filters.model)
    }
    if (filters?.since) {
      conditions.push('timestamp >= ?')
      params.push(filters.since)
    }
    if (filters?.until) {
      conditions.push('timestamp <= ?')
      params.push(filters.until)
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
    const limit = filters?.limit ?? 50
    params.push(limit)

    const rows = this.db.prepare(
      `SELECT id, timestamp, provider_id, model, source, trigger_field, session_id,
              message_count, system_prompt_preview, total_chars, estimated_tokens,
              has_tools, tool_count, temperature, max_tokens, thinking_level
       FROM prompt_log ${where} ORDER BY timestamp DESC LIMIT ?`,
    ).all(...params) as Array<Record<string, unknown>>

    return rows.map(r => this.rowToListEntry(r))
  }

  /**
   * List sessions that have prompt log entries, with counts and time ranges.
   */
  listSessions(limit = 50): PromptLogSessionSummary[] {
    const rows = this.db.prepare(`
      SELECT
        session_id,
        COUNT(*) as entry_count,
        MIN(timestamp) as first_ts,
        MAX(timestamp) as last_ts,
        GROUP_CONCAT(DISTINCT source) as sources,
        GROUP_CONCAT(DISTINCT model) as models,
        SUM(estimated_tokens) as total_tokens
      FROM prompt_log
      WHERE session_id IS NOT NULL
      GROUP BY session_id
      ORDER BY MAX(timestamp) DESC
      LIMIT ?
    `).all(limit) as Array<Record<string, unknown>>

    return rows.map(r => ({
      sessionId: r.session_id as string,
      entryCount: r.entry_count as number,
      firstTimestamp: r.first_ts as number,
      lastTimestamp: r.last_ts as number,
      sources: (r.sources as string || '').split(',').filter(Boolean),
      models: (r.models as string || '').split(',').filter(Boolean),
      totalEstimatedTokens: r.total_tokens as number,
    }))
  }

  /**
   * Get storage statistics.
   */
  getStats(): PromptLogStats {
    const total = this.db.prepare(
      'SELECT COUNT(*) as cnt FROM prompt_log',
    ).get() as { cnt: number }

    const size = this.db.prepare(
      'SELECT SUM(LENGTH(messages_json) + COALESCE(LENGTH(delta_messages_json), 0)) as sz FROM prompt_log',
    ).get() as { sz: number | null }

    const oldest = this.db.prepare(
      'SELECT MIN(timestamp) as ts FROM prompt_log',
    ).get() as { ts: number | null }

    const newest = this.db.prepare(
      'SELECT MAX(timestamp) as ts FROM prompt_log',
    ).get() as { ts: number | null }

    const bySource = this.db.prepare(
      'SELECT COALESCE(source, \'[unknown]\') as source, COUNT(*) as cnt FROM prompt_log GROUP BY source ORDER BY cnt DESC',
    ).all() as Array<{ source: string; cnt: number }>

    const byProvider = this.db.prepare(
      'SELECT provider_id, COUNT(*) as cnt FROM prompt_log GROUP BY provider_id ORDER BY cnt DESC',
    ).all() as Array<{ provider_id: string; cnt: number }>

    return {
      totalEntries: total.cnt,
      totalSizeBytes: size.sz ?? 0,
      oldestTimestamp: oldest.ts ?? 0,
      newestTimestamp: newest.ts ?? 0,
      bySource: bySource.map(r => ({ source: r.source, count: r.cnt })),
      byProvider: byProvider.map(r => ({ providerId: r.provider_id, count: r.cnt })),
    }
  }


  /**
   * Remove entries older than retention period.
   */
  cleanup(): number {
    const cutoff = Date.now() - (this.retentionDays * 24 * 60 * 60 * 1000)
    const result = this.db.prepare(
      `DELETE FROM prompt_log
       WHERE timestamp < ?
         AND id NOT IN (
           SELECT DISTINCT base_prompt_id FROM prompt_log WHERE base_prompt_id IS NOT NULL
         )`,
    ).run(cutoff)
    if (result.changes > 0) {
      this.logger.info(`Cleaned up ${result.changes} old prompt log entries`)
    }
    return result.changes
  }

  /**
   * Close the database connection.
   */
  close(): void {
    try { this.db.close() } catch {}
  }


  private serializeMessages(messages: Message[]): SerializedMessage[] {
    return messages.map(m => this.serializeMessage(m))
  }

  private serializeMessage(msg: Message): SerializedMessage {
    if (typeof msg.content === 'string') {
      return {
        role: msg.role as 'system' | 'user' | 'assistant',
        content: msg.content,
        estimatedTokens: Math.ceil(msg.content.length / CHARS_PER_TOKEN),
      }
    }

    if (!Array.isArray(msg.content)) {
      // Edge case: unknown content type — stringify fully
      const str = JSON.stringify(msg.content ?? '')
      return {
        role: msg.role as 'system' | 'user' | 'assistant',
        content: str,
        estimatedTokens: Math.ceil(str.length / CHARS_PER_TOKEN),
      }
    }

    const blocks = msg.content as ContentBlock[]
    const serialized: SerializedContentBlock[] = blocks.map(b => this.serializeBlock(b))
    const chars = this.countBlockChars(serialized)

    return {
      role: msg.role as 'system' | 'user' | 'assistant',
      content: serialized,
      estimatedTokens: Math.ceil(chars / CHARS_PER_TOKEN),
    }
  }

  private serializeBlock(block: ContentBlock): SerializedContentBlock {
    if (block.type === 'text') {
      return { type: 'text', text: block.text }
    }
    if (block.type === 'tool_use') {
      const inputStr = typeof block.input === 'string'
        ? block.input
        : JSON.stringify(block.input ?? {})
      return {
        type: 'tool_use',
        toolUseId: block.id,
        toolName: block.name,
        input: inputStr, // NO TRUNCATION
      }
    }
    if (block.type === 'tool_result') {
      const content = typeof block.content === 'string'
        ? block.content
        : JSON.stringify(block.content ?? '')
      return {
        type: 'tool_result',
        toolUseId: (block as unknown as { tool_use_id?: string }).tool_use_id,
        content, // NO TRUNCATION
        isError: (block as unknown as { is_error?: boolean }).is_error,
      }
    }
    // Extended types (thinking, etc.)
    const anyBlock = block as unknown as Record<string, unknown>
    if (anyBlock.type === 'thinking') {
      return { type: 'thinking', text: (anyBlock.text as string) ?? '' }
    }
    // Unknown block type — serialize fully
    return { type: 'text', text: JSON.stringify(block) }
  }

  private countChars(messages: SerializedMessage[]): number {
    return messages.reduce((sum, m) => {
      if (typeof m.content === 'string') return sum + m.content.length
      return sum + this.countBlockChars(m.content)
    }, 0)
  }

  private countBlockChars(blocks: SerializedContentBlock[]): number {
    return blocks.reduce(
      (s, b) => s + (b.text?.length ?? b.content?.length ?? b.input?.length ?? 0),
      0,
    )
  }

  private hashMessages(messagesJson: string): string {
    return createHash('sha256').update(messagesJson).digest('hex')
  }

  private chooseStorage(
    providerId: string,
    serialized: SerializedMessage[],
    messagesJson: string,
    contentHash: string,
    opts: CompletionOpts,
  ): {
    kind: 'full' | 'delta' | 'ref'
    messagesJson: string
    basePromptId: string | null
    deltaMessagesJson: string | null
    chainDepth: number
  } {
    const exactMatch = this.db.prepare(
      `SELECT id, chain_depth FROM prompt_log
       WHERE content_hash = ?
       ORDER BY timestamp DESC
       LIMIT 1`,
    ).get(contentHash) as { id: string; chain_depth: number } | undefined

    if (exactMatch) {
      return {
        kind: 'ref',
        messagesJson: '',
        basePromptId: exactMatch.id,
        deltaMessagesJson: null,
        chainDepth: (exactMatch.chain_depth ?? 0) + 1,
      }
    }

    if (!opts.sessionId) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    const previous = this.db.prepare(
      `SELECT id FROM prompt_log
       WHERE session_id = ?
         AND provider_id = ?
         AND model = ?
         AND COALESCE(source, '') = COALESCE(?, '')
       ORDER BY timestamp DESC
       LIMIT 1`,
    ).get(
      opts.sessionId,
      providerId,
      opts.model ?? 'unknown',
      opts.source ?? null,
    ) as { id: string } | undefined

    if (!previous) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    const previousMessages = this.loadMessagesById(previous.id)
    if (!previousMessages || previousMessages.length === 0 || previousMessages.length >= serialized.length) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    const sharedPrefixLength = this.sharedPrefixLength(previousMessages, serialized)
    if (sharedPrefixLength !== previousMessages.length || sharedPrefixLength < 2) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    const previousRow = this.getByIdStmt.get(previous.id) as Record<string, unknown> | undefined
    const previousDepth = Number(previousRow?.chain_depth ?? 0)
    if (previousDepth >= 8) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    const deltaMessages = serialized.slice(sharedPrefixLength)
    const deltaMessagesJson = JSON.stringify(deltaMessages)
    if (deltaMessagesJson.length >= messagesJson.length * 0.6) {
      return {
        kind: 'full',
        messagesJson,
        basePromptId: null,
        deltaMessagesJson: null,
        chainDepth: 0,
      }
    }

    return {
      kind: 'delta',
      messagesJson: '',
      basePromptId: previous.id,
      deltaMessagesJson,
      chainDepth: previousDepth + 1,
    }
  }

  private sharedPrefixLength(a: SerializedMessage[], b: SerializedMessage[]): number {
    const max = Math.min(a.length, b.length)
    for (let i = 0; i < max; i++) {
      if (JSON.stringify(a[i]) !== JSON.stringify(b[i])) return i
    }
    return max
  }

  private loadMessagesById(id: string, visited = new Set<string>()): SerializedMessage[] | null {
    if (visited.has(id)) return null
    visited.add(id)
    const row = this.getByIdStmt.get(id) as Record<string, unknown> | undefined
    if (!row) return null
    return this.resolveMessages(row, visited)
  }

  private resolveMessages(row: Record<string, unknown>, visited = new Set<string>()): SerializedMessage[] | null {
    const storageKind = (row.storage_kind as string | null) ?? 'full'
    if (storageKind === 'full' || !row.base_prompt_id) {
      return JSON.parse((row.messages_json as string) || '[]') as SerializedMessage[]
    }

    const baseMessages = this.loadMessagesById(row.base_prompt_id as string, visited)
    if (!baseMessages) return null

    if (storageKind === 'ref') return baseMessages

    const deltaMessages = JSON.parse((row.delta_messages_json as string) || '[]') as SerializedMessage[]
    return [...baseMessages, ...deltaMessages]
  }


  private rowToEntry(row: Record<string, unknown>): PromptLogEntry {
    const messages = this.resolveMessages(row) ?? []
    return {
      id: row.id as string,
      timestamp: row.timestamp as number,
      providerId: row.provider_id as string,
      model: row.model as string,
      source: row.source as string | null,
      trigger: row.trigger_field as string | null,
      sessionId: row.session_id as string | null,
      messages,
      messageCount: row.message_count as number,
      systemPromptPreview: row.system_prompt_preview as string | null,
      totalChars: row.total_chars as number,
      estimatedTokens: row.estimated_tokens as number,
      hasTools: !!(row.has_tools as number),
      toolCount: row.tool_count as number,
      temperature: row.temperature as number | null,
      maxTokens: row.max_tokens as number | null,
      thinkingLevel: row.thinking_level as string | null,
    }
  }

  private rowToListEntry(row: Record<string, unknown>): PromptLogListEntry {
    return {
      id: row.id as string,
      timestamp: row.timestamp as number,
      providerId: row.provider_id as string,
      model: row.model as string,
      source: row.source as string | null,
      trigger: row.trigger_field as string | null,
      sessionId: row.session_id as string | null,
      messageCount: row.message_count as number,
      systemPromptPreview: row.system_prompt_preview as string | null,
      totalChars: row.total_chars as number,
      estimatedTokens: row.estimated_tokens as number,
      hasTools: !!(row.has_tools as number),
      toolCount: row.tool_count as number,
      temperature: row.temperature as number | null,
      maxTokens: row.max_tokens as number | null,
      thinkingLevel: row.thinking_level as string | null,
    }
  }
}
