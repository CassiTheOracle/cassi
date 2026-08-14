import fs from 'node:fs'
import path from 'node:path'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'
import { getDataDir } from '../utils/paths.js'

export interface MaintenanceRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<unknown>
}

const SIX_HOURS_MS = 6 * 60 * 60 * 1000

export function startPeriodicCheckpoint(daemon: any, logger: ILogger): NodeJS.Timeout {
  const timer = setInterval(() => {
    void runCheckpointAll(daemon, logger)
  }, SIX_HOURS_MS)
  timer.unref()
  logger.info('Periodic WAL checkpoint timer started', { intervalHours: 6 })
  return timer
}

async function runCheckpointAll(daemon: any, logger: ILogger): Promise<void> {
  const results: Record<string, { walBefore: number; walAfter: number; status: string }> = {}
  const dataDir = getDataDir()
  const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.db'))

  for (const dbFile of files) {
    const dbPath = path.join(dataDir, dbFile)
    try {
      const Database = (await import('better-sqlite3')).default
      const db = new Database(dbPath)
      const walPath = dbPath + '-wal'
      const walBefore = fs.existsSync(walPath) ? fs.statSync(walPath).size : 0
      db.pragma('wal_checkpoint(TRUNCATE)')
      const walAfter = fs.existsSync(walPath) ? fs.statSync(walPath).size : 0
      db.close()
      results[dbFile] = { walBefore, walAfter, status: 'ok' }
    } catch (err) {
      results[dbFile] = { walBefore: 0, walAfter: 0, status: String(err) }
    }
  }

  logger.info('Periodic WAL checkpoint completed', {
    databases: files.length,
    freedBytes: Object.values(results).reduce((sum, r) => sum + (r.walBefore - r.walAfter), 0),
  })
}

export async function handleMaintenanceRoutes(
  deps: MaintenanceRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody } = deps
  const url = new URL(req.url || '/', `http://${req.headers.host}`)
  const pathname = url.pathname.replace(/^\/+/, '').replace(/\/+$/, '')

  if (!pathname.startsWith('maintenance')) return false

  if (method === 'POST' && pathname === 'maintenance/checkpoint') {
    const results: Record<string, { walBefore: number; walAfter: number; status: string }> = {}
    const dataDir = getDataDir()
    const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.db'))

    for (const dbFile of files) {
      const dbPath = path.join(dataDir, dbFile)
      try {
        const Database = (await import('better-sqlite3')).default
        const db = new Database(dbPath)
        const walPath = dbPath + '-wal'
        const walBefore = fs.existsSync(walPath) ? fs.statSync(walPath).size : 0
        db.pragma('wal_checkpoint(TRUNCATE)')
        const walAfter = fs.existsSync(walPath) ? fs.statSync(walPath).size : 0
        db.close()
        results[dbFile] = { walBefore, walAfter, status: 'ok' }
      } catch (err) {
        results[dbFile] = { walBefore: 0, walAfter: 0, status: String(err) }
      }
    }

    const totalFreed = Object.values(results).reduce((sum, r) => sum + (r.walBefore - r.walAfter), 0)
    sendJSON(res, 200, { action: 'checkpoint', databases: results, totalFreedBytes: totalFreed })
    return true
  }

  if (method === 'POST' && pathname === 'maintenance/purge-filaments') {
    const dataDir = getDataDir()
    const dbPath = path.join(dataDir, 'mnemic-field.db')
    const results: Record<string, unknown> = {}

    try {
      const Database = (await import('better-sqlite3')).default
      const db = new Database(dbPath)
      db.pragma('busy_timeout = 30000')

      const beforeSynapses = (db.prepare('SELECT COUNT(*) as cnt FROM filament_synapses').get() as any).cnt
      const beforeFilaments = (db.prepare('SELECT COUNT(*) as cnt FROM filaments').get() as any).cnt
      const beforeEntities = (db.prepare('SELECT COUNT(*) as cnt FROM filament_entities').get() as any).cnt

      db.exec('DELETE FROM filament_synapses')
      db.exec('DELETE FROM filaments')
      db.exec('DELETE FROM filament_entities')
      db.pragma('wal_checkpoint(TRUNCATE)')

      const afterSynapses = (db.prepare('SELECT COUNT(*) as cnt FROM filament_synapses').get() as any).cnt
      const afterFilaments = (db.prepare('SELECT COUNT(*) as cnt FROM filaments').get() as any).cnt
      const afterEntities = (db.prepare('SELECT COUNT(*) as cnt FROM filament_entities').get() as any).cnt

      db.close()

      let hnswDeleted = false
      let metaDeleted = false
      const hnswPath = path.join(dataDir, 'filament-ann.hnsw')
      const metaPath = path.join(dataDir, 'filament-ann.meta.json')
      if (fs.existsSync(hnswPath)) { fs.unlinkSync(hnswPath); hnswDeleted = true }
      if (fs.existsSync(metaPath)) { fs.unlinkSync(metaPath); metaDeleted = true }

      results['filament_synapses'] = { before: beforeSynapses, after: afterSynapses }
      results['filaments'] = { before: beforeFilaments, after: afterFilaments }
      results['filament_entities'] = { before: beforeEntities, after: afterEntities }
      results['filament-ann.hnsw'] = { deleted: hnswDeleted }
      results['filament-ann.meta.json'] = { deleted: metaDeleted }

      logger.info('Filament purge completed', results)
      sendJSON(res, 200, { action: 'purge-filaments', results })
    } catch (err) {
      sendJSON(res, 500, { action: 'purge-filaments', error: String(err) })
    }
    return true
  }

  if (method === 'POST' && pathname === 'maintenance/vacuum') {
    const dataDir = getDataDir()
    const dbPath = path.join(dataDir, 'mnemic-field.db')
    const results: Record<string, unknown> = {}

    try {
      const beforeSize = fs.statSync(dbPath).size

      const Database = (await import('better-sqlite3')).default
      const db = new Database(dbPath)
      db.pragma('busy_timeout = 60000')
      db.exec('VACUUM')
      db.close()

      const afterSize = fs.statSync(dbPath).size
      results['beforeBytes'] = beforeSize
      results['afterBytes'] = afterSize
      results['freedBytes'] = beforeSize - afterSize

      logger.info('VACUUM completed', results)
      sendJSON(res, 200, { action: 'vacuum', results })
    } catch (err) {
      sendJSON(res, 500, { action: 'vacuum', error: String(err) })
    }
    return true
  }

  if (method === 'POST' && pathname === 'maintenance/delete-vectors-db') {
    const dataDir = getDataDir()
    const dbPath = path.join(dataDir, 'vectors.db')
    const results: Record<string, unknown> = {}

    try {
      let deletedMain = false
      let deletedWal = false
      let deletedShm = false

      if (fs.existsSync(dbPath)) { fs.unlinkSync(dbPath); deletedMain = true }
      const walPath = dbPath + '-wal'
      if (fs.existsSync(walPath)) { fs.unlinkSync(walPath); deletedWal = true }
      const shmPath = dbPath + '-shm'
      if (fs.existsSync(shmPath)) { fs.unlinkSync(shmPath); deletedShm = true }

      results['vectors.db'] = { deleted: deletedMain }
      results['vectors.db-wal'] = { deleted: deletedWal }
      results['vectors.db-shm'] = { deleted: deletedShm }

      logger.info('Legacy vectors.db deleted', results)
      sendJSON(res, 200, { action: 'delete-vectors-db', results })
    } catch (err) {
      sendJSON(res, 500, { action: 'delete-vectors-db', error: String(err) })
    }
    return true
  }

  return false
}
