import { createHash } from 'node:crypto'
import Database from 'better-sqlite3'
import { parentPort, workerData } from 'node:worker_threads'

interface FtsWorkerData {
  dbPath: string
  query: string
  limit: number
}

interface RawEngramRow {
  id: string
  content: string
  node_type: string
  x: number
  y: number
  z: number | null
  t: number
  potentiation: number
  cluster_id: string | null
  tags: string | null
  provenance: string | null
  created_at: string
  accessed_at: string | null
  metadata: string | null
}

function parseJson<T>(value: string | null, fallback: T): T {
  if (!value) return fallback
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

const MAX_CONTENT_CHARS = 2048

function safeOpaqueId(value: string): string {
  if (/^[A-Za-z0-9._:-]{1,128}$/.test(value)) return value
  return `sha256:${createHash('sha256').update(value).digest('hex').slice(0, 32)}`
}

const data = workerData as FtsWorkerData

try {
  const db = new Database(data.dbPath, { readonly: true, fileMustExist: true })
  const results = (() => {
    try {
      db.pragma('query_only = ON')
      db.pragma('busy_timeout = 50')
      const rows = db.prepare(`
        SELECT e.id, e.content, e.node_type, e.metadata FROM engrams_fts fts
        JOIN engrams e ON e.rowid = fts.rowid
        WHERE engrams_fts MATCH ?
        ORDER BY rank LIMIT ?
      `).all(data.query, data.limit) as RawEngramRow[]
      return rows
        .filter(row => row.node_type !== 'bridge')
        .map((row, index) => ({
          engram: {
            id: safeOpaqueId(row.id),
            content: row.content.slice(0, MAX_CONTENT_CHARS),
            nodeType: row.node_type.slice(0, 64),
            x: 0,
            y: 0,
            z: 0,
            t: 0,
            potentiation: 0,
            clusterId: null,
            embedding: null,
            tags: [],
            provenance: '',
            createdAt: '',
            accessedAt: null,
            metadata: (() => {
              const metadata = parseJson<Record<string, unknown>>(row.metadata, {})
              return typeof metadata.sessionId === 'string'
                ? { sessionId: metadata.sessionId.slice(0, 128) }
                : {}
            })(),
          },
          score: 1 - (index / data.limit),
        }))
    } finally {
      db.close()
    }
  })()
  parentPort?.postMessage({ ok: true, results })
} catch {
  // Never serialize the query or SQLite's query-bearing error across the boundary.
  parentPort?.postMessage({ ok: false, error: 'fts-search-failed' })
}
