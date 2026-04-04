/**
 * Training Ingest — Backfill pipeline that reads from operational stores
 * (memory.db, lumen.db, dyad.db, session index, event bus) and writes
 * normalized rows into the training warehouse.
 *
 * Each source has its own adapter. Adapters are checkpoint-resumable:
 * they track the last processed ID/timestamp so re-runs only process
 * new data.
 *
 * Stage 1 (deterministic):
 * - Extracts structure: sessions, turns, messages, tool calls, reasoning
 * - Splits text into chunks (paragraph-level)
 * - Applies heuristic labels (role, tool name, error state, memory class)
 * - Builds object graph edges
 *
 * Stage 2 (LLM) is handled by training-tagger.ts after ingest.
 */

import Database from 'better-sqlite3'
import * as crypto from 'node:crypto'
import type { ILogger } from '../../../types/interfaces.js'
import { TrainingStore } from './training-store.js'
import type {
  TrainingObject,
  TrainingSession,
  TrainingTurn,
  TrainingMessage,
  TrainingChunk,
  TrainingToolCall,
  TrainingReasoningTrace,
  TrainingReasoningStep,
  TrainingEvent,
  TrainingArtifact,
} from './training-types.js'

// CHUNKING UTILITIES

interface ParsedChunk {
  type: string      // paragraph | code_block | heading | list_item | tool_input | tool_output
  text: string
  language?: string  // for code blocks
}

/** Split markdown-ish text into typed chunks. */
function splitIntoChunks(text: string): ParsedChunk[] {
  if (!text || !text.trim()) return []

  const chunks: ParsedChunk[] = []
  const lines = text.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block
    if (line.trimStart().startsWith('```')) {
      const lang = line.trimStart().slice(3).trim() || undefined
      const blockLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trimStart().startsWith('```')) {
        blockLines.push(lines[i])
        i++
      }
      if (i < lines.length) i++ // skip closing ```
      const blockText = blockLines.join('\n').trim()
      if (blockText) {
        chunks.push({ type: 'code_block', text: blockText, language: lang })
      }
      continue
    }

    // Heading
    if (/^#{1,6}\s/.test(line)) {
      chunks.push({ type: 'heading', text: line.trim() })
      i++
      continue
    }

    // List item
    if (/^\s*[-*+]\s|^\s*\d+\.\s/.test(line)) {
      const listLines: string[] = [line]
      i++
      // Collect continuation lines (indented or next list items)
      while (i < lines.length && /^\s+\S|^\s*[-*+]\s|^\s*\d+\.\s/.test(lines[i])) {
        listLines.push(lines[i])
        i++
      }
      chunks.push({ type: 'list_item', text: listLines.join('\n').trim() })
      continue
    }

    // Empty line — skip
    if (!line.trim()) {
      i++
      continue
    }

    // Paragraph — collect until blank line or structural element
    const paraLines: string[] = [line]
    i++
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trimStart().startsWith('```') &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !/^\s*[-*+]\s|^\s*\d+\.\s/.test(lines[i])
    ) {
      paraLines.push(lines[i])
      i++
    }
    chunks.push({ type: 'paragraph', text: paraLines.join('\n').trim() })
  }

  return chunks
}

/** Rough token estimate: ~4 chars per token for English. */
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4)
}

/** Generate deterministic ref key for a chunk. */
function chunkRef(sessionRef: string, turnSeq: number, msgSeq: number, chunkSeq: number): string {
  return `${sessionRef}#T${String(turnSeq).padStart(2, '0')}.M${String(msgSeq).padStart(2, '0')}.C${String(chunkSeq).padStart(2, '0')}`
}

// INGEST ORCHESTRATOR

export interface IngestOptions {
  /** Limit rows per source per run (for incremental processing). */
  batchSize?: number
  /** Skip sources that have been ingested recently. */
  skipIfRecentMs?: number
}

export interface IngestResult {
  source: string
  rowsIngested: number
  chunksCreated: number
  labelsAttached: number
  edgesCreated: number
  durationMs: number
  errors: string[]
}

export class TrainingIngest {
  private readonly store: TrainingStore
  private readonly logger: ILogger

  constructor(store: TrainingStore, logger: ILogger) {
    this.store = store
    this.logger = logger.child('training-ingest')
  }

  // ARCHIVE INGEST

  /**
   * Ingest from the archive store (memory.db → archives table).
   * Maps archive entries to sessions, messages, chunks, and labels.
   */
  ingestArchives(archiveDbPath: string, opts: IngestOptions = {}): IngestResult {
    const start = Date.now()
    const result: IngestResult = {
      source: 'archive', rowsIngested: 0, chunksCreated: 0,
      labelsAttached: 0, edgesCreated: 0, durationMs: 0, errors: [],
    }

    let sourceDb: Database.Database | null = null
    try {
      sourceDb = new Database(archiveDbPath, { readonly: true })
    } catch (err) {
      result.errors.push(`Cannot open archive DB: ${String(err)}`)
      result.durationMs = Date.now() - start
      return result
    }

    try {
      const checkpoint = this.store.getCheckpoint('archive', 'archives')
      const lastTs = checkpoint?.last_processed_ts ?? 0
      const limit = opts.batchSize ?? 500

      // Read archive entries ordered by timestamp
      const rows = sourceDb.prepare(`
        SELECT * FROM archives
        WHERE timestamp > ?
        ORDER BY timestamp ASC
        LIMIT ?
      `).all(lastTs, limit) as any[]

      if (rows.length === 0) {
        result.durationMs = Date.now() - start
        return result
      }

      const now = Date.now()
      let maxTs = lastTs

      this.store.transaction(() => {
        for (const row of rows) {
          try {
            const archiveId = row.id as string
            const ts = (row.timestamp as number) || now
            if (ts > maxTs) maxTs = ts

            // Skip if already ingested
            if (this.store.objectExists('archive', archiveId)) continue

            const sessionId = row.session_id as string | null
            const entryType = row.type as string
            const content = row.content as string || ''
            const thinking = row.thinking as string | null

            // Parse metadata
            let metadata: Record<string, unknown> = {}
            try { metadata = JSON.parse(row.metadata_json || '{}') } catch { /* ignore */ }
            let analysis: Record<string, unknown> = {}
            try { analysis = JSON.parse(row.analysis_json || '{}') } catch { /* ignore */ }

            // WHY: topics, entities, and tags are stored in separate columns, not inside analysis_json
            let topics: string[] = []
            try { topics = JSON.parse(row.topics_json || '[]') } catch { /* ignore */ }
            let entities: string[] = []
            try { entities = JSON.parse(row.entities_json || '[]') } catch { /* ignore */ }
            let tags: string[] = []
            try { tags = JSON.parse(row.tags_json || '[]') } catch { /* ignore */ }

            // Create the object
            const objectId = `arc_${archiveId}`
            const refKey = sessionId ? `S:${sessionId.slice(0, 8)}#A:${archiveId.slice(0, 8)}` : `A:${archiveId.slice(0, 8)}`

            const obj: TrainingObject = {
              object_id: objectId,
              object_type: this.mapArchiveType(entryType) as TrainingObject['object_type'],
              subtype: entryType,
              parent_object_id: null,
              root_session_id: sessionId,
              ref_key: refKey,
              source_db: 'archive',
              source_id: archiveId,
              created_at: ts,
              ingested_at: now,
              raw_json: JSON.stringify(row),
            }
            this.store.insertObject(obj)

            // Create a message for the content
            const msgId = `msg_${archiveId}`
            this.store.insertObject({
              object_id: msgId,
              object_type: 'message',
              subtype: this.mapArchiveTypeToRole(entryType),
              parent_object_id: objectId,
              root_session_id: sessionId,
              ref_key: `${refKey}.M00`,
              source_db: 'archive',
              source_id: `${archiveId}:content`,
              created_at: ts,
              ingested_at: now,
              raw_json: null,
            })

            this.store.insertMessage({
              object_id: msgId,
              turn_id: objectId,
              sequence: 0,
              role: this.mapArchiveTypeToRole(entryType),
              content_type: 'text',
              content_text: content,
              content_json: null,
              producer_model: metadata.model as string || null,
              producer_provider: metadata.provider as string || null,
              token_count: metadata.tokensUsed as number || null,
              is_error: metadata.isError ? 1 : 0,
              error_class: null,
            })

            // Chunk the content
            const chunks = splitIntoChunks(content)
            for (let ci = 0; ci < chunks.length; ci++) {
              const chunk = chunks[ci]
              const chunkId = `chk_${archiveId}_${ci}`
              const cRef = `${refKey}.M00.C${String(ci).padStart(2, '0')}`

              this.store.insertChunk({
                chunk_id: chunkId,
                object_id: msgId,
                chunk_type: chunk.type,
                chunk_ref: cRef,
                sequence: ci,
                text: chunk.text,
                token_estimate: estimateTokens(chunk.text),
                language: chunk.language || null,
                role: this.mapArchiveTypeToRole(entryType),
                session_id: sessionId,
              })
              result.chunksCreated++
            }

            // Chunk thinking blocks separately
            if (thinking) {
              const thinkChunks = splitIntoChunks(thinking)
              for (let ti = 0; ti < thinkChunks.length; ti++) {
                const tc = thinkChunks[ti]
                const thinkChunkId = `chk_${archiveId}_t${ti}`
                const tRef = `${refKey}.T00.C${String(ti).padStart(2, '0')}`

                this.store.insertChunk({
                  chunk_id: thinkChunkId,
                  object_id: msgId,
                  chunk_type: 'reasoning_content',
                  chunk_ref: tRef,
                  sequence: ti,
                  text: tc.text,
                  token_estimate: estimateTokens(tc.text),
                  language: tc.language || null,
                  role: 'thinking',
                  session_id: sessionId,
                })
                result.chunksCreated++
              }
            }

            // Attach heuristic labels from existing analysis
            this.attachArchiveLabels(objectId, entryType, metadata, analysis, topics, entities, tags, result)

            // Edge: parent → child for content
            this.store.insertEdge({
              source_id: objectId,
              target_id: msgId,
              relation: 'parent',
              weight: 1.0,
              metadata_json: null,
            })
            result.edgesCreated++

            result.rowsIngested++
          } catch (err) {
            result.errors.push(`Archive row ${row.id}: ${String(err)}`)
          }
        }

        // Update checkpoint
        this.store.setCheckpoint({
          source_db: 'archive',
          source_table: 'archives',
          last_processed_id: rows[rows.length - 1].id,
          last_processed_ts: maxTs,
          rows_ingested: (checkpoint?.rows_ingested ?? 0) + result.rowsIngested,
          updated_at: now,
        })
      })
    } finally {
      sourceDb.close()
    }

    result.durationMs = Date.now() - start
    this.logger.info('Archive ingest complete', { ...result, errors: result.errors.length })
    return result
  }

  // MEMORY INGEST

  /**
   * Ingest from the memory store (memory.db → memories table).
   * Maps memories to objects with memory_class labels.
   */
  ingestMemories(memoryDbPath: string, opts: IngestOptions = {}): IngestResult {
    const start = Date.now()
    const result: IngestResult = {
      source: 'memory', rowsIngested: 0, chunksCreated: 0,
      labelsAttached: 0, edgesCreated: 0, durationMs: 0, errors: [],
    }

    let sourceDb: Database.Database | null = null
    try {
      sourceDb = new Database(memoryDbPath, { readonly: true })
    } catch (err) {
      result.errors.push(`Cannot open memory DB: ${String(err)}`)
      result.durationMs = Date.now() - start
      return result
    }

    try {
      const checkpoint = this.store.getCheckpoint('memory', 'memories')
      const lastId = checkpoint?.last_processed_id ?? ''
      const limit = opts.batchSize ?? 500

      const rows = sourceDb.prepare(`
        SELECT * FROM memories
        WHERE id > ?
        ORDER BY id ASC
        LIMIT ?
      `).all(lastId, limit) as any[]

      if (rows.length === 0) {
        result.durationMs = Date.now() - start
        return result
      }

      const now = Date.now()

      this.store.transaction(() => {
        for (const row of rows) {
          try {
            const memId = row.id as string
            if (this.store.objectExists('memory', memId)) continue

            const content = row.content as string || ''
            const type = row.type as string || 'general'
            const sessionId = row.session_id as string | null
            const createdAt = row.created_at ? new Date(row.created_at).getTime() : now

            let metadata: Record<string, unknown> = {}
            try { metadata = JSON.parse(row.metadata || '{}') } catch { /* ignore */ }

            const cogClass = row.cognitive_class as string | null

            const objectId = `mem_${memId}`
            const refKey = `M:${memId.slice(0, 12)}`

            this.store.insertObject({
              object_id: objectId,
              object_type: 'memory',
              subtype: type,
              parent_object_id: null,
              root_session_id: sessionId,
              ref_key: refKey,
              source_db: 'memory',
              source_id: memId,
              created_at: createdAt,
              ingested_at: now,
              raw_json: JSON.stringify(row),
            })

            // Chunk the content
            const chunks = splitIntoChunks(content)
            for (let ci = 0; ci < chunks.length; ci++) {
              const chunk = chunks[ci]
              const chunkId = `chk_mem_${memId}_${ci}`
              this.store.insertChunk({
                chunk_id: chunkId,
                object_id: objectId,
                chunk_type: chunk.type,
                chunk_ref: `${refKey}.C${String(ci).padStart(2, '0')}`,
                sequence: ci,
                text: chunk.text,
                token_estimate: estimateTokens(chunk.text),
                language: chunk.language || null,
                role: null,
                session_id: sessionId,
              })
              result.chunksCreated++
            }

            // Attach memory class label
            if (cogClass) {
              const labelId = this.store.ensureLabel('memory_class', cogClass)
              this.store.attachLabel(objectId, labelId, { source: 'imported', isPrimary: true })
              result.labelsAttached++
            }

            // Attach type as a label
            const typeLabel = this.store.ensureLabel('topic', type)
            this.store.attachLabel(objectId, typeLabel, { source: 'imported' })
            result.labelsAttached++

            result.rowsIngested++
          } catch (err) {
            result.errors.push(`Memory row ${row.id}: ${String(err)}`)
          }
        }

        this.store.setCheckpoint({
          source_db: 'memory',
          source_table: 'memories',
          last_processed_id: rows[rows.length - 1].id,
          last_processed_ts: now,
          rows_ingested: (checkpoint?.rows_ingested ?? 0) + result.rowsIngested,
          updated_at: now,
        })
      })
    } finally {
      sourceDb.close()
    }

    result.durationMs = Date.now() - start
    this.logger.info('Memory ingest complete', { ...result, errors: result.errors.length })
    return result
  }

  // LUMEN SESSION INGEST

  /**
   * Ingest from lumen.db → lumen_sessions, lumen_messages, lumen_tool_calls.
   * Maps dialectic sessions into sessions, reasoning traces, and steps.
   */
  ingestLumen(lumenDbPath: string, opts: IngestOptions = {}): IngestResult {
    const start = Date.now()
    const result: IngestResult = {
      source: 'lumen', rowsIngested: 0, chunksCreated: 0,
      labelsAttached: 0, edgesCreated: 0, durationMs: 0, errors: [],
    }

    let sourceDb: Database.Database | null = null
    try {
      sourceDb = new Database(lumenDbPath, { readonly: true })
    } catch (err) {
      result.errors.push(`Cannot open lumen DB: ${String(err)}`)
      result.durationMs = Date.now() - start
      return result
    }

    try {
      const checkpoint = this.store.getCheckpoint('lumen', 'sessions')
      const lastId = checkpoint?.last_processed_id ?? ''
      const limit = opts.batchSize ?? 100

      // WHY: Lumen DB uses `sessions` (not `lumen_sessions`) with PK `id` (not `session_id`)
      const sessions = sourceDb.prepare(`
        SELECT * FROM sessions
        WHERE id > ?
        ORDER BY id ASC
        LIMIT ?
      `).all(lastId, limit) as any[]

      if (sessions.length === 0) {
        result.durationMs = Date.now() - start
        return result
      }

      const now = Date.now()

      this.store.transaction(() => {
        for (const sess of sessions) {
          try {
            const sessId = sess.id as string
            if (this.store.objectExists('lumen', sessId)) continue

            const objectId = `lum_${sessId}`
            const refKey = `L:${sessId.slice(0, 12)}`
            const createdAt = sess.created_at || now

            // Create session object
            this.store.insertObject({
              object_id: objectId,
              object_type: 'session',
              subtype: 'lumen',
              parent_object_id: null,
              root_session_id: sessId,
              ref_key: refKey,
              source_db: 'lumen',
              source_id: sessId,
              created_at: createdAt,
              ingested_at: now,
              raw_json: JSON.stringify(sess),
            })

            const totalTokens = (sess.tokens_yang || 0) + (sess.tokens_yin || 0) + (sess.tokens_executive || 0)

            this.store.insertSession({
              object_id: objectId,
              session_type: 'lumen',
              channel: null,
              parent_session_id: null,
              started_at: createdAt,
              ended_at: sess.completed_at || null,
              status: sess.status || 'completed',
              turn_count: 0,
              total_tokens: totalTokens,
              model_primary: sess.model || null,
              provider_primary: sess.provider || null,
            })

            // Create a reasoning trace for the dialectic
            const traceId = `rt_${sessId}`
            this.store.insertObject({
              object_id: traceId,
              object_type: 'reasoning_trace',
              subtype: 'dialectic',
              parent_object_id: objectId,
              root_session_id: sessId,
              ref_key: `${refKey}#R`,
              source_db: 'lumen',
              source_id: `${sessId}:trace`,
              created_at: createdAt,
              ingested_at: now,
              raw_json: null,
            })

            this.store.insertReasoningTrace({
              object_id: traceId,
              turn_id: objectId,
              reasoning_type: 'dialectic',
              depth: null,
              synthesis: sess.synthesis || sess.recommendation || null,
              decision: sess.recommendation || null,
              overall_confidence: sess.confidence || null,
              step_count: 0,
            })

            this.store.insertEdge({
              source_id: objectId,
              target_id: traceId,
              relation: 'parent',
              weight: 1.0,
              metadata_json: null,
            })
            result.edgesCreated++

            // WHY: Lumen messages are in `dialectic_messages` (not `lumen_messages`)
            // with `from_posture` and `msg_type` columns
            const messages = sourceDb!.prepare(`
              SELECT * FROM dialectic_messages
              WHERE session_id = ?
              ORDER BY id ASC
            `).all(sessId) as any[]

            let stepCount = 0
            for (const msg of messages) {
              const stepId = `rs_${sessId}_${stepCount}`
              const stepType = msg.from_posture || msg.msg_type || 'step'
              const content = msg.content as string || ''

              this.store.insertObject({
                object_id: stepId,
                object_type: 'reasoning_step',
                subtype: stepType,
                parent_object_id: traceId,
                root_session_id: sessId,
                ref_key: `${refKey}#R.${stepType}.${String(stepCount).padStart(2, '0')}`,
                source_db: 'lumen',
                source_id: `${sessId}:msg:${stepCount}`,
                created_at: msg.timestamp || createdAt,
                ingested_at: now,
                raw_json: JSON.stringify(msg),
              })

              this.store.insertReasoningStep({
                object_id: stepId,
                trace_id: traceId,
                step_type: stepType,
                sequence: stepCount,
                content,
                confidence: null,
                tokens_used: null,
              })

              // Chunk step content
              const chunks = splitIntoChunks(content)
              for (let ci = 0; ci < chunks.length; ci++) {
                const chunk = chunks[ci]
                this.store.insertChunk({
                  chunk_id: `chk_lum_${sessId}_${stepCount}_${ci}`,
                  object_id: stepId,
                  chunk_type: chunk.type === 'paragraph' ? 'reasoning_content' : chunk.type,
                  chunk_ref: `${refKey}#R.${stepType}.${String(stepCount).padStart(2, '0')}.C${String(ci).padStart(2, '0')}`,
                  sequence: ci,
                  text: chunk.text,
                  token_estimate: estimateTokens(chunk.text),
                  language: chunk.language || null,
                  role: stepType,
                  session_id: sessId,
                })
                result.chunksCreated++
              }

              this.store.insertEdge({
                source_id: traceId,
                target_id: stepId,
                relation: 'parent',
                weight: 1.0,
                metadata_json: null,
              })
              result.edgesCreated++
              stepCount++
            }

            // Update step count on trace
            this.store.db.prepare(`
              UPDATE reasoning_traces SET step_count = ? WHERE object_id = ?
            `).run(stepCount, traceId)

            // Labels
            const reasoningLabel = this.store.ensureLabel('interaction_pattern', 'reasoning')
            this.store.attachLabel(objectId, reasoningLabel, { source: 'heuristic', isPrimary: true })
            result.labelsAttached++

            result.rowsIngested++
          } catch (err) {
            result.errors.push(`Lumen session ${sess.id}: ${String(err)}`)
          }
        }

        this.store.setCheckpoint({
          source_db: 'lumen',
          source_table: 'sessions',
          last_processed_id: sessions[sessions.length - 1].id,
          last_processed_ts: now,
          rows_ingested: (checkpoint?.rows_ingested ?? 0) + result.rowsIngested,
          updated_at: now,
        })
      })
    } finally {
      sourceDb.close()
    }

    result.durationMs = Date.now() - start
    this.logger.info('Lumen ingest complete', { ...result, errors: result.errors.length })
    return result
  }

  // DYAD SESSION INGEST

  ingestDyad(dyadDbPath: string, opts: IngestOptions = {}): IngestResult {
    const start = Date.now()
    const result: IngestResult = {
      source: 'dyad', rowsIngested: 0, chunksCreated: 0,
      labelsAttached: 0, edgesCreated: 0, durationMs: 0, errors: [],
    }

    let sourceDb: Database.Database | null = null
    try {
      sourceDb = new Database(dyadDbPath, { readonly: true })
    } catch (err) {
      result.errors.push(`Cannot open dyad DB: ${String(err)}`)
      result.durationMs = Date.now() - start
      return result
    }

    try {
      const checkpoint = this.store.getCheckpoint('dyad', 'sessions')
      const lastId = checkpoint?.last_processed_id ?? ''
      const limit = opts.batchSize ?? 100

      const sessions = sourceDb.prepare(`
        SELECT * FROM dyad_sessions
        WHERE id > ?
        ORDER BY id ASC
        LIMIT ?
      `).all(lastId, limit) as any[]

      if (sessions.length === 0) {
        result.durationMs = Date.now() - start
        return result
      }

      const now = Date.now()

      this.store.transaction(() => {
        for (const sess of sessions) {
          try {
            const sessId = sess.id as string
            if (this.store.objectExists('dyad', sessId)) continue

            const objectId = `dyd_${sessId}`
            const refKey = `D:${sessId.slice(0, 12)}`
            const createdAt = sess.created_at || now

            this.store.insertObject({
              object_id: objectId,
              object_type: 'session',
              subtype: 'dyad',
              parent_object_id: null,
              root_session_id: sessId,
              ref_key: refKey,
              source_db: 'dyad',
              source_id: sessId,
              created_at: createdAt,
              ingested_at: now,
              raw_json: JSON.stringify(sess),
            })

            const totalTokens = (sess.tokens_yang || 0) + (sess.tokens_yin || 0) + (sess.tokens_apex || 0)

            this.store.insertSession({
              object_id: objectId,
              session_type: 'dyad',
              channel: null,
              parent_session_id: null,
              started_at: createdAt,
              ended_at: sess.completed_at || null,
              status: sess.status || 'completed',
              turn_count: 0,
              total_tokens: totalTokens,
              model_primary: null,
              provider_primary: null,
            })

            // WHY: Dyad messages are in `dyad_work_stream` (not `dyad_messages`)
            // with `msg_type` and `from_role` columns
            const messages = sourceDb!.prepare(`
              SELECT * FROM dyad_work_stream
              WHERE session_id = ?
              ORDER BY id ASC
            `).all(sessId) as any[]

            let turnSeq = 0
            for (const msg of messages) {
              const turnId = `dt_${sessId}_${turnSeq}`
              const role = msg.from_role as string || 'assistant'
              const content = msg.content as string || ''

              this.store.insertObject({
                object_id: turnId,
                object_type: 'turn',
                subtype: role,
                parent_object_id: objectId,
                root_session_id: sessId,
                ref_key: `${refKey}#T${String(turnSeq).padStart(2, '0')}`,
                source_db: 'dyad',
                source_id: `${sessId}:msg:${turnSeq}`,
                created_at: msg.timestamp || createdAt,
                ingested_at: now,
                raw_json: JSON.stringify(msg),
              })

              this.store.insertTurn({
                object_id: turnId,
                session_id: objectId,
                sequence: turnSeq,
                role,
                subrole: msg.msg_type || null,
                branch_id: null,
                prev_turn_id: turnSeq > 0 ? `dt_${sessId}_${turnSeq - 1}` : null,
                next_turn_id: null,
                parent_turn_id: null,
                has_tool_calls: 0,
                has_reasoning: role === 'yang' || role === 'yin' || role === 'apex' ? 1 : 0,
                has_error: 0,
                is_recovery: 0,
                outcome: null,
                token_count_in: null,
                token_count_out: null,
                latency_ms: null,
                started_at: msg.timestamp || createdAt,
                ended_at: null,
              })

              // Chunk content
              const chunks = splitIntoChunks(content)
              for (let ci = 0; ci < chunks.length; ci++) {
                const chunk = chunks[ci]
                this.store.insertChunk({
                  chunk_id: `chk_dyd_${sessId}_${turnSeq}_${ci}`,
                  object_id: turnId,
                  chunk_type: chunk.type,
                  chunk_ref: chunkRef(refKey, turnSeq, 0, ci),
                  sequence: ci,
                  text: chunk.text,
                  token_estimate: estimateTokens(chunk.text),
                  language: chunk.language || null,
                  role,
                  session_id: sessId,
                })
                result.chunksCreated++
              }

              this.store.insertEdge({
                source_id: objectId,
                target_id: turnId,
                relation: 'parent',
                weight: 1.0,
                metadata_json: null,
              })
              result.edgesCreated++

              // Link sequential turns
              if (turnSeq > 0) {
                this.store.insertEdge({
                  source_id: `dt_${sessId}_${turnSeq - 1}`,
                  target_id: turnId,
                  relation: 'next',
                  weight: 1.0,
                  metadata_json: null,
                })
                result.edgesCreated++
              }

              turnSeq++
            }

            // Labels
            const delegLabel = this.store.ensureLabel('interaction_pattern', 'delegation')
            this.store.attachLabel(objectId, delegLabel, { source: 'heuristic', isPrimary: true })
            result.labelsAttached++

            result.rowsIngested++
          } catch (err) {
            result.errors.push(`Dyad session ${sess.id}: ${String(err)}`)
          }
        }

        this.store.setCheckpoint({
          source_db: 'dyad',
          source_table: 'sessions',
          last_processed_id: sessions[sessions.length - 1].id,
          last_processed_ts: now,
          rows_ingested: (checkpoint?.rows_ingested ?? 0) + result.rowsIngested,
          updated_at: now,
        })
      })
    } finally {
      sourceDb.close()
    }

    result.durationMs = Date.now() - start
    this.logger.info('Dyad ingest complete', { ...result, errors: result.errors.length })
    return result
  }

  // SESSION INDEX INGEST

  /**
   * Ingest from the session indexer (memory.db → session_index flat table).
   * Maps indexed content rows directly to chunks with their original ref keys.
   */
  ingestSessionIndex(memoryDbPath: string, opts: IngestOptions = {}): IngestResult {
    const start = Date.now()
    const result: IngestResult = {
      source: 'session_index', rowsIngested: 0, chunksCreated: 0,
      labelsAttached: 0, edgesCreated: 0, durationMs: 0, errors: [],
    }

    let sourceDb: Database.Database | null = null
    try {
      sourceDb = new Database(memoryDbPath, { readonly: true })
    } catch (err) {
      result.errors.push(`Cannot open memory DB for session index: ${String(err)}`)
      result.durationMs = Date.now() - start
      return result
    }

    try {
      // Check if session_index table exists
      const tableCheck = sourceDb.prepare(`
        SELECT name FROM sqlite_master WHERE type='table' AND name='session_index'
      `).get()
      if (!tableCheck) {
        result.durationMs = Date.now() - start
        return result
      }

      const checkpoint = this.store.getCheckpoint('session_index', 'session_index')
      const lastId = checkpoint?.last_processed_id ? Number(checkpoint.last_processed_id) : 0
      const limit = opts.batchSize ?? 1000

      // WHY: The session_index table uses a flat schema with (label, msg_idx, block_idx, para_idx)
      // instead of separate blocks/paragraphs tables. Each row is one content chunk.
      const rows = sourceDb.prepare(`
        SELECT
          si.id, si.label, si.msg_idx, si.role, si.block_idx,
          si.block_type, si.para_idx, si.content, si.meta_json,
          sl.session_id
        FROM session_index si
        LEFT JOIN session_labels sl ON sl.label = si.label
        WHERE si.id > ?
        ORDER BY si.id ASC
        LIMIT ?
      `).all(lastId, limit) as any[]

      if (rows.length === 0) {
        result.durationMs = Date.now() - start
        return result
      }

      const now = Date.now()

      this.store.transaction(() => {
        for (const row of rows) {
          try {
            const rowId = row.id as number
            const text = row.content as string || ''
            if (!text.trim()) continue

            const label = row.label as string
            const sessionId = row.session_id as string | null
            const msgIdx = row.msg_idx as number || 0
            const blockIdx = row.block_idx as number || 0
            const paraIdx = row.para_idx as number | null
            const role = row.role as string || null
            const blockType = row.block_type as string || 'paragraph'

            // Build the original ref key
            const origRef = paraIdx != null
              ? `${label}#M${msgIdx}.B${blockIdx}.P${paraIdx}`
              : `${label}#M${msgIdx}.B${blockIdx}`

            const chunkId = `chk_si_${rowId}`

            // Ensure session object exists (keyed by label since session_id may be null)
            const sessKey = sessionId || label
            const sessObjId = `si_${sessKey}`
            if (!this.store.getObject(sessObjId)) {
              this.store.insertObject({
                object_id: sessObjId,
                object_type: 'session',
                subtype: 'interactive',
                parent_object_id: null,
                root_session_id: sessionId,
                ref_key: label,
                source_db: 'session_index',
                source_id: sessKey,
                created_at: now,
                ingested_at: now,
                raw_json: null,
              })
            }

            // Map block_type to chunk_type
            const chunkType = blockType === 'code' ? 'code_block'
              : blockType === 'heading' ? 'heading'
              : blockType === 'list' ? 'list_item'
              : 'paragraph'

            this.store.insertChunk({
              chunk_id: chunkId,
              object_id: sessObjId,
              chunk_type: chunkType,
              chunk_ref: origRef,
              sequence: paraIdx ?? blockIdx,
              text,
              token_estimate: estimateTokens(text),
              language: null,
              role,
              session_id: sessionId,
            })
            result.chunksCreated++
            result.rowsIngested++
          } catch (err) {
            result.errors.push(`Session index row ${row.id}: ${String(err)}`)
          }
        }

        this.store.setCheckpoint({
          source_db: 'session_index',
          source_table: 'session_index',
          last_processed_id: String(rows[rows.length - 1].id),
          last_processed_ts: now,
          rows_ingested: (checkpoint?.rows_ingested ?? 0) + result.rowsIngested,
          updated_at: now,
        })
      })
    } finally {
      sourceDb.close()
    }

    result.durationMs = Date.now() - start
    this.logger.info('Session index ingest complete', { ...result, errors: result.errors.length })
    return result
  }

  // FULL INGEST (all sources)

  /**
   * Run ingest across all available source databases.
   * Returns results per source.
   */
  ingestAll(dataDirs: {
    memoryDbPath?: string
    lumenDbPath?: string
    dyadDbPath?: string
  }, opts: IngestOptions = {}): IngestResult[] {
    const results: IngestResult[] = []

    // WHY: Each source is wrapped in try/catch so one failure doesn't block others
    const safeRun = (label: string, fn: () => IngestResult): void => {
      try {
        results.push(fn())
      } catch (err) {
        this.logger.error(`Ingest source "${label}" threw unexpectedly`, { error: String(err) })
        results.push({
          source: label, rowsIngested: 0, chunksCreated: 0,
          labelsAttached: 0, edgesCreated: 0, durationMs: 0,
          errors: [`Uncaught: ${String(err)}`],
        })
      }
    }

    if (dataDirs.memoryDbPath) {
      safeRun('memory', () => this.ingestMemories(dataDirs.memoryDbPath!, opts))
      safeRun('archive', () => this.ingestArchives(dataDirs.memoryDbPath!, opts))
      safeRun('session_index', () => this.ingestSessionIndex(dataDirs.memoryDbPath!, opts))
    }
    if (dataDirs.lumenDbPath) {
      safeRun('lumen', () => this.ingestLumen(dataDirs.lumenDbPath!, opts))
    }
    if (dataDirs.dyadDbPath) {
      safeRun('dyad', () => this.ingestDyad(dataDirs.dyadDbPath!, opts))
    }

    return results
  }

  // HELPERS

  private mapArchiveType(type: string): string {
    switch (type) {
      case 'conversation': return 'message'
      case 'thinking': return 'message'
      case 'insight': return 'insight'
      case 'dialectic_yang':
      case 'dialectic_yin':
      case 'dialectic_serenity': return 'reasoning_step'
      case 'tool_call': return 'tool_call'
      case 'event': return 'event'
      case 'reflection': return 'insight'
      case 'pattern': return 'pattern'
      case 'summary': return 'insight'
      default: return 'message'
    }
  }

  private mapArchiveTypeToRole(type: string): string {
    switch (type) {
      case 'conversation': return 'assistant'
      case 'thinking': return 'thinking'
      case 'dialectic_yang': return 'yang'
      case 'dialectic_yin': return 'yin'
      case 'dialectic_serenity': return 'serenity'
      case 'tool_call': return 'tool'
      default: return 'system'
    }
  }

  private attachArchiveLabels(
    objectId: string,
    entryType: string,
    metadata: Record<string, unknown>,
    analysis: Record<string, unknown>,
    topics: string[],
    entities: string[],
    tags: string[],
    result: IngestResult,
  ): void {
    // Type-based labels
    if (entryType.startsWith('dialectic_')) {
      const label = this.store.ensureLabel('interaction_pattern', 'reasoning')
      this.store.attachLabel(objectId, label, { source: 'heuristic' })
      result.labelsAttached++
    }

    // Tool name label
    if (metadata.toolName) {
      const toolLabel = this.store.ensureLabel('tool', String(metadata.toolName))
      this.store.attachLabel(objectId, toolLabel, { source: 'imported' })
      result.labelsAttached++
    }

    // WHY: Topics and entities come from separate columns, not from analysis_json
    for (const topic of topics) {
      if (!topic) continue
      const label = this.store.ensureLabel('topic', topic)
      this.store.attachLabel(objectId, label, {
        source: 'imported',
        confidence: 0.8,
      })
      result.labelsAttached++
    }

    for (const entity of entities) {
      if (!entity) continue
      const label = this.store.ensureLabel('domain', entity)
      this.store.attachLabel(objectId, label, {
        source: 'imported',
        confidence: 0.7,
      })
      result.labelsAttached++
    }

    for (const tag of tags) {
      if (!tag) continue
      const label = this.store.ensureLabel('topic', tag)
      this.store.attachLabel(objectId, label, { source: 'imported' })
      result.labelsAttached++
    }

    // Import importance as quality metric
    if (typeof analysis.importance === 'number') {
      this.store.setQualityMetric({
        object_id: objectId,
        metric: 'trainability',
        value: analysis.importance as number,
        source: 'imported',
        annotation_run_id: null,
        updated_at: Date.now(),
      })
    }
  }
}
