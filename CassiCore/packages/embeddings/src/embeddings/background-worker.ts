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
import { isGamingMode } from '../vendor/core/intelligence/gaming-mode.js'

import type { EmbeddingService } from './embedding-service.js'
import type { SqliteVectorIndex } from './sqlite-index.js'
import type { ILogger } from '@cassicore/foundation'




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
  trainingEmbedded: number
}

export class BackgroundEmbeddingWorker {
  private logger: ILogger
  private embSvc: EmbeddingService
  private vecIdx: SqliteVectorIndex
  private archiveDb?: Database.Database
  private memoryDb?: Database.Database
  private trainingDb?: Database.Database

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
    trainingEmbedded: 0,
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
    this.openTrainingDb(dataDir)
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

    // WHY: Skip the tick entirely when gaming mode is active (GPU in use by
    // another application). Without this, the worker would query databases,
    // build candidate lists, and attempt HTTP calls against dead inference
    // servers — wasting CPU and I/O every 5 minutes.
    if (isGamingMode()) {
      this.logger.debug('BackgroundEmbeddingWorker: gaming mode active, skipping tick')
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

      // WHY: Yield to the event loop between phases so HTTP requests and
      // timers are not starved by back-to-back synchronous SQLite reads.
      await new Promise(resolve => setImmediate(resolve))

      // Phase 2: Embed un-embedded memory entries
      if (totalEmbedded < MAX_PER_TICK) {
        const memoryResult = await this.embedMemoryEntries(MAX_PER_TICK - totalEmbedded)
        totalEmbedded += memoryResult.embedded
        totalErrors += memoryResult.errors
        this.stats.memoriesEmbedded += memoryResult.embedded
      }

      await new Promise(resolve => setImmediate(resolve))

      // Phase 3: Embed un-embedded training objects
      if (totalEmbedded < MAX_PER_TICK) {
        const trainingResult = await this.embedTrainingObjects(MAX_PER_TICK - totalEmbedded)
        totalEmbedded += trainingResult.embedded
        totalErrors += trainingResult.errors
        this.stats.trainingEmbedded += trainingResult.embedded
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
      // HOW: Fast pre-check — compare source count vs embedded count.
      // If they match, skip the expensive ID-set materialization entirely.
      const sourceCount = (this.archiveDb.prepare(
        'SELECT COUNT(*) as cnt FROM archives WHERE LENGTH(content) > 20'
      ).get() as { cnt: number }).cnt
      const embeddedCount = this.vecIdx.countByPrefix('archive:')

      if (sourceCount <= embeddedCount) {
        this.stats.totalSkipped += sourceCount
        return { embedded: 0, errors: 0 }
      }

      // HOW: Use prefix-filtered ID lookup instead of listAll() — reads only
      // IDs from the PRIMARY KEY index, skips the meta column and JSON parsing.
      const existingIds = this.vecIdx.getIdsByPrefix('archive:')

      // Get archive entries that don't have vectors yet
      const allRows = this.archiveDb.prepare(
        `SELECT id, content FROM archives
         WHERE LENGTH(content) > 20
         ORDER BY timestamp DESC`
      ).all() as Array<{ id: string; content: string }>

      const candidates: Array<{ id: string; content: string }> = []
      for (const row of allRows) {
        if (candidates.length >= MAX_PER_TICK) break
        if (!existingIds.has(`archive:${row.id}`)) {
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
      // HOW: Fast pre-check — compare source count vs embedded count.
      const sourceCount = (this.memoryDb.prepare(
        'SELECT COUNT(*) as cnt FROM memories WHERE LENGTH(content) > 20'
      ).get() as { cnt: number }).cnt
      const embeddedCount = this.vecIdx.countByPrefix('memory:')

      if (sourceCount <= embeddedCount) {
        this.stats.totalSkipped += sourceCount
        return { embedded: 0, errors: 0 }
      }

      // HOW: Use prefix-filtered ID lookup instead of listAll().
      const existingIds = this.vecIdx.getIdsByPrefix('memory:')

      const allEntries = this.memoryDb.prepare(
        `SELECT id, content, context_prefix FROM memories
         WHERE LENGTH(content) > 20
         ORDER BY created_at DESC`
      ).all() as Array<{ id: string; content: string; context_prefix: string | null }>

      // Filter out entries that already have vectors
      const candidates: Array<{ id: string; content: string; context_prefix: string | null }> = []
      for (const row of allEntries) {
        if (candidates.length >= limit) break
        if (!existingIds.has(`memory:${row.id}`)) {
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

  // TRAINING EMBEDDING

  private async embedTrainingObjects(limit: number): Promise<{ embedded: number; errors: number }> {
    if (!this.trainingDb) return { embedded: 0, errors: 0 }

    let embedded = 0
    let errors = 0

    try {
      // HOW: Find objects that don't have embeddings yet by LEFT JOINing with object_embeddings.
      // Concatenate each object's chunk texts to form the embeddable document.
      const candidates = this.trainingDb.prepare(`
        SELECT o.object_id, GROUP_CONCAT(c.text, ' ') as combined_text
        FROM objects o
        JOIN chunks c ON c.object_id = o.object_id
        LEFT JOIN object_embeddings oe ON oe.object_id = o.object_id
        WHERE oe.object_id IS NULL
        GROUP BY o.object_id
        LIMIT ?
      `).all(limit) as Array<{ object_id: string; combined_text: string }>

      if (candidates.length === 0) return { embedded: 0, errors: 0 }

      const modelId = 'local-embedding'

      // Embed in batches
      for (let i = 0; i < candidates.length; i += BATCH_SIZE) {
        if (!this.running) break
        const batch = candidates.slice(i, i + BATCH_SIZE)
        const texts = batch.map(c => (c.combined_text || '').slice(0, 2000))

        try {
          const vectors = await this.embSvc.embedBatch(texts, 'document')

          for (let j = 0; j < batch.length; j++) {
            const vec = vectors[j]
            if (vec) {
              this.trainingDb.prepare(`
                INSERT OR REPLACE INTO object_embeddings
                  (object_id, model_id, vector_json, dimensions, created_at)
                VALUES (?, ?, ?, ?, ?)
              `).run(
                batch[j].object_id,
                modelId,
                JSON.stringify(vec),
                vec.length,
                Date.now(),
              )
              embedded++
            }
          }
        } catch (err) {
          errors++
          this.logger.debug('BackgroundEmbeddingWorker: training batch failed', {
            batchStart: i,
            error: String(err),
          })
        }
      }
    } catch (err) {
      this.logger.error('BackgroundEmbeddingWorker: training embedding failed', { error: String(err) })
      errors++
    }

    return { embedded, errors }
  }

  // DATABASE CONNECTIONS

  private openArchiveDb(dataDir: string): void {
    // WHY: The archives table lives in memory.db, not a separate archives.db.
    const dbPath = path.join(dataDir, 'memory.db')
    if (!fs.existsSync(dbPath)) {
      this.logger.debug('BackgroundEmbeddingWorker: memory.db not found, archive embedding disabled')
      return
    }
    try {
      this.archiveDb = new Database(dbPath, { readonly: true })
      this.archiveDb.pragma('busy_timeout = 3000')
      this.logger.debug('BackgroundEmbeddingWorker: opened memory.db for archives', { dbPath })
    } catch (err) {
      this.logger.warn('BackgroundEmbeddingWorker: failed to open memory.db for archives', { error: String(err) })
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

  private openTrainingDb(dataDir: string): void {
    const dbPath = path.join(dataDir, 'training.db')
    if (!fs.existsSync(dbPath)) {
      this.logger.debug('BackgroundEmbeddingWorker: training.db not found, training embedding disabled')
      return
    }
    try {
      // WHY: Read-write because we insert into object_embeddings during backfill.
      this.trainingDb = new Database(dbPath)
      this.trainingDb.pragma('busy_timeout = 3000')
      this.trainingDb.pragma('journal_mode = WAL')
      this.logger.debug('BackgroundEmbeddingWorker: opened training.db', { dbPath })
    } catch (err) {
      this.logger.warn('BackgroundEmbeddingWorker: failed to open training.db', { error: String(err) })
      this.trainingDb = undefined
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
