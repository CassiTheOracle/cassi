import { createHash } from 'node:crypto'
import Database from 'better-sqlite3'
import { parentPort, workerData } from 'node:worker_threads'

const MAX_CONTENT_CHARS = 2048

function safeOpaqueId(value) {
  if (/^[A-Za-z0-9._:-]{1,128}$/.test(value)) return value
  return `sha256:${createHash('sha256').update(value).digest('hex').slice(0, 32)}`
}

function parseJson(value, fallback) {
  if (!value) return fallback
  try { return JSON.parse(value) } catch { return fallback }
}

const { dbPath, query, limit } = workerData
try {
  const db = new Database(dbPath, { readonly: true, fileMustExist: true })
  try {
    db.pragma('query_only = ON')
    db.pragma('busy_timeout = 50')
    const rows = db.prepare(`
      SELECT e.id, e.content, e.node_type, e.metadata FROM engrams_fts fts
      JOIN engrams e ON e.rowid = fts.rowid
      WHERE engrams_fts MATCH ?
      ORDER BY rank LIMIT ?
    `).all(query, limit)
    const results = rows
      .filter(row => row.node_type !== 'bridge')
      .map((row, index) => {
        const metadata = parseJson(row.metadata, {})
        return {
          engram: {
            id: safeOpaqueId(row.id),
            content: String(row.content).slice(0, MAX_CONTENT_CHARS),
            nodeType: String(row.node_type).slice(0, 64),
            x: 0, y: 0, z: 0, t: 0, potentiation: 0, clusterId: null,
            embedding: null, tags: [], provenance: '', createdAt: '', accessedAt: null,
            metadata: typeof metadata.sessionId === 'string' ? { sessionId: metadata.sessionId.slice(0, 128) } : {},
          },
          score: 1 - (index / limit),
        }
      })
    parentPort?.postMessage({ ok: true, results })
  } finally { db.close() }
} catch {
  parentPort?.postMessage({ ok: false, error: 'fts-search-failed' })
}
