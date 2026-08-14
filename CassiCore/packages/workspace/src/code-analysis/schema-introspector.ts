/**
 * Schema Introspector — Discover CassiCore's internal SQLite databases.
 *
 * Enumerates all .db files under the CassiCore data directory, extracts
 * table schemas (columns, types, row counts), and returns structured metadata.
 *
 * Useful for debugging, self-improvement, and understanding what data
 * CassiCore has accumulated.
 */

import { existsSync, readdirSync, statSync } from 'node:fs'
import { join, basename } from 'node:path'
import Database from 'better-sqlite3'
import type { ILogger } from '../../../types/interfaces.js'
import type { DatabaseSchema, TableSchema, SchemaIntrospectionResult } from './types.js'

/** Known CassiCore data directories to scan. */
function getDataDirs(): string[] {
  const home = process.env.HOME || '/tmp'
  return [
    join(home, '.cassi', 'data'),
    join(home, '.cassi', 'memory'),
    join(home, '.cassi'),
    join(process.cwd(), '.gitnexus'),
  ]
}

/**
 * Find all .db files in a directory (non-recursive for safety).
 */
function findDbFiles(dir: string): string[] {
  if (!existsSync(dir)) return []
  try {
    return readdirSync(dir)
      .filter(f => f.endsWith('.db') || f.endsWith('.sqlite') || f.endsWith('.sqlite3'))
      .map(f => join(dir, f))
      .filter(f => {
        try { return statSync(f).isFile() } catch { return false }
      })
  } catch {
    return []
  }
}

/**
 * Extract table schema from a SQLite database.
 */
function extractTableSchema(dbPath: string, logger: ILogger): TableSchema[] {
  let db: Database.Database | null = null
  try {
    db = new Database(dbPath, { readonly: true, fileMustExist: true })

    // Get all tables
    const tables = db.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name`,
    ).all() as Array<{ name: string }>

    const result: TableSchema[] = []

    for (const table of tables) {
      try {
        // Get column info
        const columns = db.prepare(`PRAGMA table_info("${table.name}")`).all() as Array<{
          name: string
          type: string
          notnull: number
          pk: number
        }>

        // Get row count (with timeout protection)
        let rowCount = 0
        try {
          const row = db.prepare(`SELECT COUNT(*) as c FROM "${table.name}"`).get() as any
          rowCount = row?.c || 0
        } catch {
          rowCount = -1 // Indicates count failed
        }

        result.push({
          name: table.name,
          columns: columns.map(c => ({
            name: c.name,
            type: c.type || 'TEXT',
            notnull: c.notnull === 1,
            pk: c.pk > 0,
          })),
          rowCount,
        })
      } catch (err) {
        logger.debug('Failed to read table schema', { table: table.name, error: String(err) })
      }
    }

    return result
  } catch (err) {
    logger.debug('Failed to open database', { path: dbPath, error: String(err) })
    return []
  } finally {
    try { db?.close() } catch { /* best-effort */ }
  }
}

/**
 * Run schema introspection across all CassiCore databases.
 */
export function introspectSchemas(
  logger: ILogger,
  options?: { database?: string; table?: string },
): SchemaIntrospectionResult {
  const allDirs = getDataDirs()
  const databases: DatabaseSchema[] = []
  let totalTables = 0
  let totalRows = 0

  for (const dir of allDirs) {
    const dbFiles = findDbFiles(dir)

    for (const dbPath of dbFiles) {
      const name = basename(dbPath).replace(/\.(db|sqlite|sqlite3)$/, '')

      // Filter by database name if specified
      if (options?.database && !name.toLowerCase().includes(options.database.toLowerCase())) {
        continue
      }

      let sizeBytes = 0
      try { sizeBytes = statSync(dbPath).size } catch { /* skip */ }

      let tables = extractTableSchema(dbPath, logger)

      // Filter by table name if specified
      if (options?.table) {
        tables = tables.filter(t => t.name.toLowerCase().includes(options.table!.toLowerCase()))
      }

      if (tables.length > 0) {
        databases.push({ name, path: dbPath, sizeBytes, tables })
        totalTables += tables.length
        totalRows += tables.reduce((sum, t) => sum + Math.max(0, t.rowCount), 0)
      }
    }
  }

  // Sort by size descending
  databases.sort((a, b) => b.sizeBytes - a.sizeBytes)

  return { databases, totalTables, totalRows }
}
