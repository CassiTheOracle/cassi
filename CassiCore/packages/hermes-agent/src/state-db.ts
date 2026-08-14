import Database from 'better-sqlite3'
import os from 'node:os'
import type { HermesSessionRow, HermesMessageRow, HermesSessionDetail, SearchResult } from './types.js'

function defaultDbPath(): string {
  return process.env.HERMES_STATE_DB || os.homedir() + '/.hermes/state.db'
}

export function openHermesDb(path?: string): Database.Database {
  const resolved = path || defaultDbPath()
  const db = new Database(resolved, { readonly: true, fileMustExist: false })
  try { db.pragma('journal_mode = WAL') } catch { /* readonly is fine */ }
  return db
}

export function openHermesDbForWrite(path?: string): Database.Database {
  const resolved = path || defaultDbPath()
  const db = new Database(resolved, { readonly: false, fileMustExist: false })
  db.pragma('journal_mode = WAL')
  db.pragma('foreign_keys = ON')
  return db
}

export function listSessions(
  db: Database.Database,
  limit = 20,
  offset = 0,
  source?: string,
): HermesSessionRow[] {
  if (source) {
    return db.prepare(
      'SELECT * FROM sessions WHERE source = ? ORDER BY started_at DESC LIMIT ? OFFSET ?',
    ).all(source, limit, offset) as HermesSessionRow[]
  }
  return db.prepare(
    'SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?',
  ).all(limit, offset) as HermesSessionRow[]
}

export function getSessionById(db: Database.Database, sessionId: string): HermesSessionRow | undefined {
  return db.prepare('SELECT * FROM sessions WHERE id = ?').get(sessionId) as HermesSessionRow | undefined
}

export function getSessionMessages(
  db: Database.Database,
  sessionId: string,
  limit = 200,
  offset = 0,
): HermesMessageRow[] {
  return db.prepare(
    'SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ? OFFSET ?',
  ).all(sessionId, limit, offset) as HermesMessageRow[]
}

export function getSessionDetail(
  db: Database.Database,
  sessionId: string,
): HermesSessionDetail | undefined {
  const session = getSessionById(db, sessionId)
  if (!session) return undefined
  const messages = getSessionMessages(db, sessionId)
  const childSessions = db.prepare(
    'SELECT id, title, message_count, started_at FROM sessions WHERE parent_session_id = ? ORDER BY started_at DESC LIMIT 10',
  ).all(sessionId) as HermesSessionDetail['child_sessions']
  return { ...session, messages, child_sessions: childSessions }
}

export function searchSessions(
  db: Database.Database,
  query: string,
  limit = 20,
): SearchResult[] {
  if (!query || query.trim().length === 0) return []

  try {
    const ftsResults = db.prepare(`
      SELECT m.session_id, m.role, substr(m.content, 1, 300) as content_preview,
             m.timestamp, 'fts5' as match_type
      FROM messages_fts f
      JOIN messages m ON f.rowid = m.id
      WHERE messages_fts MATCH ?
      ORDER BY rank
      LIMIT ?
    `).all(sanitizeFts5Query(query), limit) as SearchResult[]
    if (ftsResults.length > 0) return ftsResults
  } catch {
    // FTS5 might not be available; fall through to trigram
  }

  try {
    return db.prepare(`
      SELECT m.session_id, m.role, substr(m.content, 1, 300) as content_preview,
             m.timestamp, 'trigram' as match_type
      FROM messages_fts_trigram f
      JOIN messages m ON f.rowid = m.id
      WHERE messages_fts_trigram MATCH ?
      ORDER BY rank
      LIMIT ?
    `).all(sanitizeFts5Query(query), limit) as SearchResult[]
  } catch {
    return []
  }
}

function sanitizeFts5Query(query: string): string {
  const s = query.replace(/['"]/g, '').trim()
  return s.includes(' ') ? `"${s}"` : s
}

export function countSessions(
  db: Database.Database,
  source?: string,
): number {
  if (source) {
    const row = db.prepare('SELECT COUNT(*) as count FROM sessions WHERE source = ?').get(source) as { count: number }
    return row.count
  }
  const row = db.prepare('SELECT COUNT(*) as count FROM sessions').get() as { count: number }
  return row.count
}

export function getSessionCounts(
  db: Database.Database,
): Array<{ source: string; count: number; total_messages: number; total_tokens: number }> {
  return db.prepare(`
    SELECT source, COUNT(*) as count, COALESCE(SUM(message_count), 0) as total_messages,
           COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
    FROM sessions GROUP BY source ORDER BY count DESC
  `).all() as any
}

export function pruneSessions(
  db: Database.Database,
  olderThanDays: number,
  dryRun = true,
): { removed: number; kept: number } {
  const cutoff = Date.now() / 1000 - olderThanDays * 86400
  const keepCount = (db.prepare('SELECT COUNT(*) as count FROM sessions WHERE started_at >= ?').get(cutoff) as { count: number }).count
  const removeCount = (db.prepare('SELECT COUNT(*) as count FROM sessions WHERE started_at < ?').get(cutoff) as { count: number }).count

  if (dryRun) {
    return { removed: removeCount, kept: keepCount }
  }

  const removable = db.prepare('SELECT id FROM sessions WHERE started_at < ?').all(cutoff) as Array<{ id: string }>
  const deleteMsgs = db.prepare('DELETE FROM messages WHERE session_id = ?')
  for (const row of removable) {
    deleteMsgs.run(row.id)
  }
  db.prepare('DELETE FROM sessions WHERE started_at < ?').run(cutoff)

  try { db.prepare('DELETE FROM messages_fts WHERE rowid NOT IN (SELECT id FROM messages)').run() } catch { /* best-effort */ }
  try { db.prepare('DELETE FROM messages_fts_trigram WHERE rowid NOT IN (SELECT id FROM messages)').run() } catch { /* best-effort */ }

  return { removed: removeCount, kept: keepCount }
}

export function getSessionTokenUsage(
  db: Database.Database,
  sessionId: string,
): { input_tokens: number; output_tokens: number; total_tokens: number; estimated_cost_usd: number | null } {
  const row = db.prepare(
    'SELECT input_tokens, output_tokens, estimated_cost_usd FROM sessions WHERE id = ?',
  ).get(sessionId) as { input_tokens: number; output_tokens: number; estimated_cost_usd: number | null } | undefined
  if (!row) return { input_tokens: 0, output_tokens: 0, total_tokens: 0, estimated_cost_usd: null }
  return {
    input_tokens: row.input_tokens,
    output_tokens: row.output_tokens,
    total_tokens: row.input_tokens + row.output_tokens,
    estimated_cost_usd: row.estimated_cost_usd,
  }
}
