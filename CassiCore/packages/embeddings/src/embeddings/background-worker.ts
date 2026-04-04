/**
 * BackgroundEmbeddingWorker — pre-computes embeddings for archived content.
 *
 * Runs on a configurable interval, scanning archives and memory entries
 * that lack pre-computed embeddings, then embeds them in batches and stores
 * the vectors in SqliteVectorIndex.
 *
 * This accelerates retrieval pipelines: instead of embedding documents
 * on-demand during search, pre-computed vectors are read from SQLite.
 *
 * Lifecycle: instantiate once, call start(), call stop() on shutdown.
 *
 * Configuration via environment variables:
 *   EMB_BG_INTERVAL_MS   - Tick interval (default: 300000 = 5 min)
 *   EMB_BG_BATCH_SIZE    - Documents per batch (default: 32)
 *   EMB_BG_MAX_PER_TICK  - Max documents per tick (default: 200)
 */
import fs from 'fs'
import path from 'path'

import Database from 'better-sqlite3'

import { getEmbeddingService } from './embedding-service.js'
import { getVectorIndex } from './sqlite-index.js'

import type { EmbeddingService } from './embedding-service.js'
import type { SqliteVectorIndex } from './sqlite-index.js'
import type { ILogger } from '../../../types/interfaces.js'




const TICK_INTERVAL_MS = Number(process.env.EMB_BG_INTERVAL_MS || '300000')  // 5 min
const BATCH_SIZE = Number(process.env.EMB_BG_BATCH_SIZE || '32')
const MAX_PER_TICK = Number(process.env.EMB_BG_MAX_PER_TICK || '200')

export interface BackgroundWorkerStats {
  isRunning: boolean
  totalEmbedded: number
  totalSkipped: number
  totalErrors: number
  lastTickAt: number | null
  lastTickDurationMs: number
  lastTickEmbedded: number
  archivesEmbedded: number
  memoriesEmbedded: number
}

export class BackgroundEmbeddingWorker {
  private logger: ILogger
  private embSvc: EmbeddingService
  private vecIdx: SqliteVectorIndex
  private archiveDb?: Database.Database
  private memoryDb?: Database.Database

  private timer: NodeJS.Timeout | null = null
  private running = false
  private ticking = false

  // Stats
  private stats: BackgroundWorkerStats = {
    isRunning: false,
    totalEmbedded: 0,
    totalSkipped: 0,
    totalErrors: 0,
    lastTickAt: null,
    lastTickDurationMs: 0,
    lastTickEmbedded: 0,
    archivesEmbedded: 0,
    memoriesEmbedded: 0,
  }

  constructor(logger: ILogger) {
    this.logger = logger.child?.('bg-embedding-worker') ?? logger
    this.embSvc = getEmbeddingService(this.logger)
    this.vecIdx = getVectorIndex(this.logger)

    // Open read-only connections to archive and memory databases
    const homedir = process.env.HOME || require('os').homedir()
    const dataDir = path.join(homedir!, '.cassicore', 'data')

    this.openArchiveDb(dataDir)
    this.openMemoryDb(dataDir)
  }

  // LIFECYCLE

  /** Start the background worker. */
  start(): void {
    if (this.running) return
    this.running = true
    this.stats.isRunning = true

    this.logger.info('BackgroundEmbeddingWorker: started', {
      intervalMs: TICK_INTERVAL_MS,
      batchSize: BATCH_SIZE,
      maxPerTick: MAX_PER_TICK,
    })

    // Run first tick after a short delay (let the system settle)
    setTimeout(() => this.tick(), 10_000)

    // Schedule recurring ticks
    this.timer = setInterval(() => this.tick(), TICK_INTERVAL_MS)
  }

  /** Stop the background worker. */
  stop(): void {
    this.running = false
    this.stats.isRunning = false
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    this.logger.info('BackgroundEmbeddingWorker: stopped', { stats: this.stats })
  }

  /** Get current worker statistics. */
  getStats(): BackgroundWorkerStats {
    return { ...this.stats }
  }

  /** Manually trigger a tick (for testing / admin API). */
  async triggerTick(): Promise<{ embedded: number; errors: number }> {
    return this.tick()
  }

  // TICK — main processing loop

  private async tick(): Promise<{ embedded: number; errors: number }> {
    if (this.ticking || !this.running) return { embedded: 0, errors: 0 }
    if (!this.embSvc.available) {
      this.logger.debug('BackgroundEmbeddingWorker: embedding service unavailable, skipping tick')
      return { embedded: 0, errors: 0 }
    }

    this.ticking = true
    const tickStart = Date.now()
    let totalEmbedded = 0
    let totalErrors = 0

    try {
      // Phase 1: Embed un-embedded archive entries
      const archiveResult = await this.embedArchiveEntries()
      totalEmbedded += archiveResult.embedded
      totalErrors += archiveResult.errors
      this.stats.archivesEmbedded += archiveResult.embedded

      // Phase 2: Embed un-embedded memory entries
      if (totalEmbedded < MAX_PER_TICK) {
        const memoryResult = await this.embedMemoryEntries(MAX_PER_TICK - totalEmbedded)
        totalEmbedded += memoryResult.embedded
        totalErrors += memoryResult.errors
        this.stats.memoriesEmbedded += memoryResult.embedded
      }

      // Update stats
      this.stats.totalEmbedded += totalEmbedded
      this.stats.totalErrors += totalErrors
      this.stats.lastTickAt = tickStart
      this.stats.lastTickDurationMs = Date.now() - tickStart
      this.stats.lastTickEmbedded = totalEmbedded

      if (totalEmbedded > 0) {
        this.logger.info('BackgroundEmbeddingWorker: tick completed', {
          embedded: totalEmbedded,
          errors: totalErrors,
          durationMs: this.stats.lastTickDurationMs,
        })
      }
    } catch (err) {
      this.logger.error('BackgroundEmbeddingWorker: tick failed', { error: String(err) })
      totalErrors++
    } finally {
      this.ticking = false
    }

    return { embedded: totalEmbedded, errors: totalErrors }
  }

  // ARCHIVE EMBEDDING

  private async embedArchiveEntries(): Promise<{ embedded: number; errors: number }> {
    if (!this.archiveDb) return { embedded: 0, errors: 0 }

    let embedded = 0
    let errors = 0

    try {
      // Get archive IDs that don't have vectors yet
      const allIds = this.archiveDb.prepare(
        `SELECT id, content FROM archives
         WHERE LENGTH(content) > 20
         ORDER BY timestamp DESC
         LIMIT ?`
      ).all(MAX_PER_TICK * 2) as Array<{ id: string; content: string }>

      // Filter out entries that already have vectors
      const candidates: Array<{ id: string; content: string }> = []
      for (const row of allIds) {
        if (candidates.length >= MAX_PER_TICK) break
        const vecId = `archive:${row.id}`
        if (!this.vecIdx.hasVector(vecId)) {
          candidates.push(row)
        } else {
          this.stats.totalSkipped++
        }
      }

      if (candidates.length === 0) return { embedded: 0, errors: 0 }

      // Embed in batches
      for (let i = 0; i < candidates.length; i += BATCH_SIZE) {
        if (!this.running) break  // Respect shutdown
        const batch = candidates.slice(i, i + BATCH_SIZE)
        const texts = batch.map(c => c.content.slice(0, 2000))

        try {
          const vectors = await this.embSvc.embedBatch(texts, 'document')
          const entries: Array<{ id: string; vector: number[]; meta?: any }> = []

          for (let j = 0; j < batch.length; j++) {
            const vec = vectors[j]
            if (vec) {
              entries.push({
                id: `archive:${batch[j].id}`,
                vector: vec,
                meta: { type: 'archive', sourceId: batch[j].id },
              })
            }
          }

          if (entries.length > 0) {
            const inserted = this.vecIdx.addVectorBatch(entries)
            embedded += inserted
          }
        } catch (err) {
          errors++
          this.logger.debug('BackgroundEmbeddingWorker: archive batch failed', {
            batchStart: i,
            error: String(err),
          })
        }
      }
    } catch (err) {
      this.logger.error('BackgroundEmbeddingWorker: archive embedding failed', { error: String(err) })
      errors++
    }

    return { embedded, errors }
  }

  // MEMORY EMBEDDING

  private async embedMemoryEntries(limit: number): Promise<{ embedded: number; errors: number }> {
    if (!this.memoryDb) return { embedded: 0, errors: 0 }

    let embedded = 0
    let errors = 0

    try {
      const allEntries = this.memoryDb.prepare(
        `SELECT id, content, context_prefix FROM memories
         WHERE LENGTH(content) > 20
         ORDER BY created_at DESC
         LIMIT ?`
      ).all(limit * 2) as Array<{ id: string; content: string; context_prefix: string | null }>

      // Filter out entries that already have vectors
      const candidates: Array<{ id: string; content: string; context_prefix: string | null }> = []
      for (const row of allEntries) {
        if (candidates.length >= limit) break
        const vecId = `memory:${row.id}`
        if (!this.vecIdx.hasVector(vecId)) {
          candidates.push(row)
        } else {
          this.stats.totalSkipped++
        }
      }

      if (candidates.length === 0) return { embedded: 0, errors: 0 }

      // Embed in batches
      for (let i = 0; i < candidates.length; i += BATCH_SIZE) {
        if (!this.running) break
        const batch = candidates.slice(i, i + BATCH_SIZE)
        // WHY: Prepend context_prefix for Contextual Retrieval — improves embedding quality
        const texts = batch.map(c => {
          const prefix = c.context_prefix ? c.context_prefix + ' ' : '';
          return (prefix + c.content).slice(0, 2000);
        })

        try {
          const vectors = await this.embSvc.embedBatch(texts, 'document')
          const entries: Array<{ id: string; vector: number[]; meta?: any }> = []

          for (let j = 0; j < batch.length; j++) {
            const vec = vectors[j]
            if (vec) {
              entries.push({
                id: `memory:${batch[j].id}`,
                vector: vec,
                meta: { type: 'memory', sourceId: batch[j].id },
              })
            }
          }

          if (entries.length > 0) {
            const inserted = this.vecIdx.addVectorBatch(entries)
            embedded += inserted
          }
        } catch (err) {
          errors++
          this.logger.debug('BackgroundEmbeddingWorker: memory batch failed', {
            batchStart: i,
            error: String(err),
          })
        }
      }
    } catch (err) {
      this.logger.error('BackgroundEmbeddingWorker: memory embedding failed', { error: String(err) })
      errors++
    }

    return { embedded, errors }
  }

  // DATABASE CONNECTIONS

  private openArchiveDb(dataDir: string): void {
    const dbPath = path.join(dataDir, 'archives.db')
    if (!fs.existsSync(dbPath)) {
      this.logger.debug('BackgroundEmbeddingWorker: archives.db not found, archive embedding disabled')
      return
    }
    try {
      this.archiveDb = new Database(dbPath, { readonly: true })
      this.archiveDb.pragma('busy_timeout = 3000')
      this.logger.debug('BackgroundEmbeddingWorker: opened archives.db', { dbPath })
    } catch (err) {
      this.logger.warn('BackgroundEmbeddingWorker: failed to open archives.db', { error: String(err) })
      this.archiveDb = undefined
    }
  }

  private openMemoryDb(dataDir: string): void {
    const dbPath = path.join(dataDir, 'memory.db')
    if (!fs.existsSync(dbPath)) {
      this.logger.debug('BackgroundEmbeddingWorker: memory.db not found, memory embedding disabled')
      return
    }
    try {
      this.memoryDb = new Database(dbPath, { readonly: true })
      this.memoryDb.pragma('busy_timeout = 3000')
      this.logger.debug('BackgroundEmbeddingWorker: opened memory.db', { dbPath })
    } catch (err) {
      this.logger.warn('BackgroundEmbeddingWorker: failed to open memory.db', { error: String(err) })
      this.memoryDb = undefined
    }
  }
}


let _instance: BackgroundEmbeddingWorker | null = null

/** Get or create the BackgroundEmbeddingWorker singleton. Does NOT auto-start. */
export function getBackgroundEmbeddingWorker(
  logger?: ILogger,
): BackgroundEmbeddingWorker {
  if (!_instance) {
    const fallbackLogger: ILogger = {
      debug() {}, info() {}, warn() {}, error() {},
      child() { return this },
    }
    _instance = new BackgroundEmbeddingWorker(logger || fallbackLogger)
  }
  return _instance
}

/** Reset the singleton (useful for tests). */
export function resetBackgroundEmbeddingWorker(): void {
  _instance?.stop()
  _instance = null
}
