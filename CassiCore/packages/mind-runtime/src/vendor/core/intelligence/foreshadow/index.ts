/**
 * Foreshadow — Phase 1a instrumentation.
 *
 * Hooks into MnemicField.retrieve(), runs N-back centroid + last-query
 * baseline predictors in parallel, and logs each predictor's cosine
 * similarity against the next observed query embedding. No prefetch
 * buffer, no verification — that's Phase 1b, contingent on Phase 1a
 * showing prediction signal beyond temporal locality.
 *
 * Plain class on purpose: not a BaseCognitiveModule. Foreshadow runs no
 * LLM inference and has no event-bus surface; it's a passive logger
 * triggered by MnemicField. Living outside the auto-discovery path
 * also avoids the registry instantiating a second copy that fights
 * for the same SQLite file.
 */

import Database from 'better-sqlite3'
import { dirname, join } from 'node:path'
import { mkdirSync } from 'node:fs'
import type { ILogger } from '@cassicore/foundation'
import { getEmbeddingService } from '@cassicore/embeddings'
import { initForeshadowSchema } from './schema.js'
import type { Predictor } from './predictors.js'
import { NBackCentroid, LastQueryBaseline } from './predictors.js'

const DEFAULT_DB_PATH = join(process.env.HOME || '/tmp', '.cassicore', 'data', 'foreshadow.db')

export class Foreshadow {
  private db: Database.Database
  private predictors: Predictor[]
  private insertObservation: Database.Statement
  private insertPrediction: Database.Statement

  constructor(private readonly logger: ILogger, dbPath: string = DEFAULT_DB_PATH) {
    mkdirSync(dirname(dbPath), { recursive: true })
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    initForeshadowSchema(this.db)

    this.predictors = [new NBackCentroid(4), new LastQueryBaseline()]

    this.insertObservation = this.db.prepare(`
      INSERT INTO foreshadow_observations
        (ts, query, query_embedding, embedding_available, was_cache_hit, session_id)
      VALUES (?, ?, ?, ?, ?, ?)
    `)
    this.insertPrediction = this.db.prepare(`
      INSERT INTO foreshadow_predictions (observation_id, predictor_id, similarity_to_actual)
      VALUES (?, ?, ?)
    `)
  }

  /**
   * Best-effort observation. Never throws — instrumentation must not break
   * the retrieve path. Cache hits are logged for sequence integrity but
   * skip predictor scoring/update (otherwise LastQueryBaseline trivially
   * scores 1.0 on every repeat and contaminates the analysis).
   */
  async observe(args: {
    query: string
    sessionId?: string
    wasCacheHit: boolean
  }): Promise<void> {
    try {
      const embSvc = getEmbeddingService(this.logger)
      const vec = !args.wasCacheHit && embSvc.available ? await embSvc.embed(args.query, 'query') : null
      const embedding = vec ? new Float32Array(vec) : null

      const blob = embedding ? Buffer.from(embedding.buffer.slice(0)) : null
      const info = this.insertObservation.run(
        Date.now(),
        args.query,
        blob,
        embedding ? 1 : 0,
        args.wasCacheHit ? 1 : 0,
        args.sessionId ?? null,
      )
      const observationId = Number(info.lastInsertRowid)

      if (args.wasCacheHit) return

      for (const p of this.predictors) {
        const sim = embedding ? p.scoreAgainst(embedding) : null
        this.insertPrediction.run(observationId, p.id, sim)
        if (embedding) p.update(embedding)
      }
    } catch (err) {
      this.logger.debug?.('Foreshadow.observe failed (non-fatal)', { error: String(err) })
    }
  }

  close(): void {
    try { this.db.close() } catch { /* best-effort */ }
  }
}
