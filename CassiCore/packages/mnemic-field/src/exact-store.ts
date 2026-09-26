import Database from 'better-sqlite3'
import { createHash, randomUUID } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { getDataDir, type ILogger } from '@cassicore/foundation'

import { Cortex } from './cortex.js'
import type {
  Engram,
  EngramCreate,
  EngramSearchResult,
  EngramUpdate,
  FieldStats,
  MnemicRetrievalHit,
  MnemicSynapse,
  SynapseCreate,
} from './types.js'

export type MnemicRecordOperation = 'store' | 'update' | 'delete' | 'connect' | 'disconnect'
export type MnemicFeedbackOutcome = 'completed' | 'error' | 'unknown' | 'cancelled'

export interface MnemicFieldCandidate {
  id: string
  recordId: string
  startByte: number
  endByte: number
  text: string
  revision: string
  fieldAddress?: string
}
export interface MnemicFieldToolResult {
  id: string
  name: string
  isError: boolean
}
export interface MnemicFieldEventToolResult {
  id: string
  name: string
  is_error: boolean
}
export interface MnemicFieldEventCandidate {
  id: string
  record_id: string
  start_byte: number
  end_byte: number
  text: string
  revision: string
  field_address?: string
}

export interface MnemicObservationInput {
  contextSessionId: string
  recordId: string
  packetSha256: string
  packetObjectSha256: string
  payloadManifestSha256: string
  journalHeadSha256: string
  viewSha256: string
  codecId: string
  sourceStreamId: string
  sourceSequence: number
  sourcePath?: readonly (string | number)[]
  sourceSpan?: readonly [number, number]
}

export interface MnemicObservationReference {
  packet_sha256: string
  packet_object_sha256: string
  payload_manifest_sha256: string
  journal_head_sha256: string
  view_sha256: string
  codec_id: string
  source_stream_id: string
  source_sequence: number
  source_path: (string | number)[]
  source_span?: [number, number]
}

export type MnemicActionOutcome = 'completed' | 'error'

export interface MnemicActionEffect {
  record_id: string
  before_revision: string
  after_revision: string
  semantic_kind: string
  start_byte: number
  end_byte: number
}

export interface MnemicActionStart {
  contextSessionId: string
  turnId: number
  planId: string
  toolCallId: string
  toolName: string
  argumentsSha256: string
  requiredAuthority: number
  reversible: boolean
}

export interface MnemicActionFinish {
  contextSessionId: string
  turnId: number
  planId: string
  toolCallId: string
  isError: boolean
  effects?: readonly MnemicActionEffect[]
}

export interface MnemicFieldActionEvent {
  episode_id: string
  action_id: string
  kind: string
  stage: 'start' | 'outcome'
  required_authority: number
  reversible: boolean
  authorization_path: string[]
  effects?: MnemicActionEffect[]
  outcome?: MnemicActionOutcome
}

interface MnemicFieldEventRecord {
  id: string
  content: string
  node_type: string
  revision: string
  field_address?: string
}


export type MnemicFieldEventPayload =
  | {
    kind: 'memory'
    context_session_id: string
    operation: MnemicRecordOperation
    record: MnemicFieldEventRecord
    previous_record?: MnemicFieldEventRecord
    action?: MnemicFieldActionEvent
  }
  | {
    kind: 'feedback'
    context_session_id: string
    turn_id: number
    query: string
    candidates: MnemicFieldEventCandidate[]
    outcome: MnemicFeedbackOutcome
    tool_result?: MnemicFieldEventToolResult
  }
  | {
    kind: 'observation'
    context_session_id: string
    operation: 'store' | 'update'
    record: {
      id: string
      revision: string
      previous_revision?: string
    }
    reference: MnemicObservationReference
  }

export interface MnemicFieldEvent {
  streamId: string
  sequence: number
  previousEventId: string
  eventId: string
  payload: MnemicFieldEventPayload
}

export interface MnemicFieldStreamStatus {
  streamId: string
  headSequence: number
  headEventId: string
  acknowledgedSequence: number
}

export type MnemicFieldJournalVerificationCode =
  | 'acknowledgement-gap'
  | 'canonical-payload'
  | 'event-hash'
  | 'head-mismatch'
  | 'previous-event'
  | 'sequence-gap'
  | 'stream-mismatch'

export interface MnemicFieldJournalVerification {
  schemaVersion: 1
  status: 'valid' | 'invalid' | 'not-run'
  streamId: string
  checkedThroughSequence: number
  acknowledgedSequence: number
  acknowledgedPrefixValid: boolean
  headSequence: number
  headEventId: string
  checkedAt: number | null
  failure?: {
    code: MnemicFieldJournalVerificationCode
    sequence: number
    message: string
  }
}

export interface MnemicUnresolvedActionEpisode {
  episodeId: string
  recordId: string
  actionId: string
  kind: string
  contextSessionId: string
  turnId: number
  planId: string
  toolCallId: string
  requiredAuthority: number
  reversible: boolean
  startedAt: number
}

export interface MnemicFieldAddressInput {
  recordId: string
  revision: string
  startByte: number
  endByte: number
  semanticKind: string
}

export interface MnemicFieldAddressEntry {
  address: string
  recordId: string
  fieldRecordId: string
  revision: string
  startByte: number
  endByte: number
  semanticKind: string
  contentSha256: string
}

export interface MnemicFieldAddressManifestOptions {
  maxEntries?: number
  excludeSessionId?: string
}

export interface MnemicFieldAddressResolution extends MnemicFieldAddressEntry {
  record: Engram
}

export class MnemicFieldJournalError extends Error {
  readonly code = 'mnemic-journal-invalid'

  constructor(public readonly verification: MnemicFieldJournalVerification) {
    super(`exact action start blocked: ${verification.failure?.code ?? 'journal-invalid'}`)
    this.name = 'MnemicFieldJournalError'
  }
}

const EMPTY_EVENT_ID = '0'.repeat(64)
const MAX_FIELD_CONTENT_BYTES = 16 * 1_024
const MAX_FIELD_QUERY_BYTES = 8 * 1_024
const MAX_MNEMIC_FIELD_ADDRESSES = 65_536

export const MNEMIC_CONDENSATION_ADDRESS_SCHEMA = 'cassicore.mnemic.condensation-address.v1'

export const MNEMIC_FIELD_CANONICAL_SCHEMA = 'cassicore.mnemic.field-canonical-json.v1'
export function mnemicFieldCanonicalJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(mnemicFieldCanonicalJson).join(',')}]`
  const object = value as Record<string, unknown>
  return `{${Object.keys(object).sort().map(key => `${JSON.stringify(key)}:${mnemicFieldCanonicalJson(object[key])}`).join(',')}}`
}

export function mnemicFieldAddress(input: MnemicFieldAddressInput): string {
  if (!input.recordId || Buffer.byteLength(input.recordId) > 256) {
    throw new Error('field address recordId must be bounded nonempty UTF-8 text')
  }
  exactSha256(input.revision, 'field address revision')
  if (
    !Number.isInteger(input.startByte)
    || !Number.isInteger(input.endByte)
    || input.startByte < 0
    || input.endByte < input.startByte
  ) throw new Error('field address span must be an ordered byte interval')
  if (!input.semanticKind || Buffer.byteLength(input.semanticKind) > 128) {
    throw new Error('field address semanticKind must be bounded nonempty UTF-8 text')
  }
  return createHash('sha256')
    .update(mnemicFieldCanonicalJson([
      MNEMIC_CONDENSATION_ADDRESS_SCHEMA,
      input.recordId,
      input.revision,
      input.startByte,
      input.endByte,
      input.semanticKind,
    ]))
    .digest('hex')
    .slice(0, 32)
}

function exactFieldAddress(value: string, name: string): string {
  if (!/^[0-9a-f]{32}$/.test(value)) throw new Error(`${name} must be a lowercase 16-byte field address`)
  return value
}
function exactSha256(value: string, name: string): string {
  if (!/^[0-9a-f]{64}$/.test(value)) throw new Error(`${name} must be a lowercase SHA-256 digest`)
  return value
}

function observationReference(input: MnemicObservationInput): MnemicObservationReference {
  if (!Number.isInteger(input.sourceSequence) || input.sourceSequence < 0) {
    throw new Error('sourceSequence must be a non-negative integer')
  }
  if (!/^[A-Za-z0-9._:+-]{1,128}$/.test(input.codecId)) {
    throw new Error('codecId must be a bounded deterministic codec identifier')
  }
  if (!input.sourceStreamId || Buffer.byteLength(input.sourceStreamId) > 256) {
    throw new Error('sourceStreamId must be nonempty and at most 256 UTF-8 bytes')
  }
  const sourcePath = [...(input.sourcePath ?? [])]
  if (
    sourcePath.length > 64
    || sourcePath.some(segment => (
      typeof segment === 'number'
        ? !Number.isInteger(segment) || segment < 0
        : typeof segment !== 'string' || Buffer.byteLength(segment) > 256
    ))
  ) throw new Error('sourcePath is invalid')
  const span = input.sourceSpan
  if (
    span
    && (
      span.length !== 2
      || !Number.isInteger(span[0])
      || !Number.isInteger(span[1])
      || span[0] < 0
      || span[1] < span[0]
    )
  ) throw new Error('sourceSpan must be an ordered byte interval')
  return {
    packet_sha256: exactSha256(input.packetSha256, 'packetSha256'),
    packet_object_sha256: exactSha256(input.packetObjectSha256, 'packetObjectSha256'),
    payload_manifest_sha256: exactSha256(input.payloadManifestSha256, 'payloadManifestSha256'),
    journal_head_sha256: exactSha256(input.journalHeadSha256, 'journalHeadSha256'),
    view_sha256: exactSha256(input.viewSha256, 'viewSha256'),
    codec_id: input.codecId,
    source_stream_id: input.sourceStreamId,
    source_sequence: input.sourceSequence,
    source_path: sourcePath,
    ...(span ? { source_span: [span[0], span[1]] } : {}),
  }
}

export function mnemicObservationRevision(input: MnemicObservationInput): string {
  return createHash('sha256').update(mnemicFieldCanonicalJson({
    schema: 'cassi.mnemic-observation-reference.v1',
    record_id: input.recordId,
    reference: observationReference(input),
  })).digest('hex')
}


function truncateUtf8(value: string, maxBytes: number): string {
  const bytes = Buffer.from(value)
  if (bytes.length <= maxBytes) return value
  return new TextDecoder().decode(bytes.subarray(0, maxBytes)).replace(/\uFFFD$/u, '')
}

function isBoundedOpaqueId(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._:-]{1,128}$/.test(value)
}

function safeOpaqueId(value: string): string {
  if (isBoundedOpaqueId(value)) return value
  return `sha256:${createHash('sha256').update(value).digest('hex').slice(0, 32)}`
}

export function mnemicRecordRevision(record: {
  id: string
  content: string
  nodeType: string
}): string {
  return createHash('sha256')
    .update(record.id)
    .update('\0')
    .update(record.nodeType)
    .update('\0')
    .update(record.content)
    .digest('hex')
}

function fieldEventRecord(
  record: { id: string; content: string; nodeType: string },
  recallable = false,
): MnemicFieldEventRecord {
  const id = safeOpaqueId(record.id)
  const revision = mnemicRecordRevision(record)
  return {
    id,
    content: truncateUtf8(record.content, MAX_FIELD_CONTENT_BYTES),
    node_type: record.nodeType.slice(0, 64),
    revision,
    ...(recallable ? {
      field_address: mnemicFieldAddress({
        recordId: id,
        revision,
        startByte: 0,
        endByte: Buffer.byteLength(record.content),
        semanticKind: record.nodeType,
      }),
    } : {}),
  }
}

/** Exact durable records and their exact field-transition journal. */
export class MnemicExactStore {
  readonly cortex: Cortex
  onFieldEvent?: () => void

  private readonly db: Database.Database
  private readonly logger: ILogger
  private actionJournalVerification: MnemicFieldJournalVerification | null = null
  private lastJournalVerification: MnemicFieldJournalVerification | null = null

  constructor(logger: ILogger, dbOrPath?: Database.Database | string) {
    this.logger = logger.child?.('mnemic-exact-store') ?? logger
    if (typeof dbOrPath === 'object') {
      this.db = dbOrPath
    } else {
      const dbPath = dbOrPath ?? path.join(getDataDir(), 'mnemic-field.db')
      fs.mkdirSync(path.dirname(dbPath), { recursive: true })
      this.db = new Database(dbPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('foreign_keys = ON')
    }
    this.cortex = new Cortex(this.db, this.logger)
    this.initializeFieldJournal()
    this.logger.info('Exact Mnemic record store initialized')
  }

  store(input: EngramCreate): Engram {
    return this.commit(
      () => this.cortex.createEngram({
        ...input,
        x: 0,
        y: 0,
        z: 0,
        initialPotentiation: 0,
        embedding: null,
      }),
      record => {
        this.upsertFieldAddress(record)
        return this.memoryPayload('store', record, record.metadata.sessionId, undefined, true)
      },
    )
  }

  get(id: string): Engram | null {
    return this.cortex.getEngram(id)
  }

  getMany(ids: readonly string[]): Engram[] {
    const records: Engram[] = []
    const seen = new Set<string>()
    for (const id of ids) {
      if (seen.has(id)) continue
      seen.add(id)
      const record = this.cortex.getEngram(id)
      if (record) records.push(record)
    }
    return records
  }

  fieldAddressManifest(
    options: MnemicFieldAddressManifestOptions = {},
  ): MnemicFieldAddressEntry[] {
    const {
      maxEntries = MAX_MNEMIC_FIELD_ADDRESSES,
      excludeSessionId,
    } = options
    if (!Number.isInteger(maxEntries) || maxEntries < 1 || maxEntries > MAX_MNEMIC_FIELD_ADDRESSES) {
      throw new Error(`maxEntries must be an integer in [1, ${MAX_MNEMIC_FIELD_ADDRESSES}]`)
    }
    if (excludeSessionId !== undefined && !isBoundedOpaqueId(excludeSessionId)) {
      throw new Error('excludeSessionId must be a bounded opaque identifier when supplied')
    }
    const excluded = excludeSessionId ?? null
    const count = this.db.prepare(`
      SELECT COUNT(*) AS count
      FROM mnemic_field_address_manifest AS manifest
      INNER JOIN engrams AS records ON records.id = manifest.record_id
      WHERE ? IS NULL
        OR COALESCE(json_extract(records.metadata, '$.sessionId'), '') <> ?
    `).get(excluded, excluded) as { count: number }
    if (count.count > maxEntries) {
      throw new Error(`exact field address manifest exceeds the ${maxEntries}-entry request bound`)
    }
    const rows = this.db.prepare(`
      SELECT
        manifest.address,
        manifest.record_id,
        manifest.field_record_id,
        manifest.revision,
        manifest.start_byte,
        manifest.end_byte,
        manifest.semantic_kind,
        manifest.content_sha256
      FROM mnemic_field_address_manifest AS manifest
      INNER JOIN engrams AS records ON records.id = manifest.record_id
      WHERE ? IS NULL
        OR COALESCE(json_extract(records.metadata, '$.sessionId'), '') <> ?
      ORDER BY manifest.address ASC
    `).all(excluded, excluded) as Array<{
      address: string
      record_id: string
      field_record_id: string
      revision: string
      start_byte: number
      end_byte: number
      semantic_kind: string
      content_sha256: string
    }>
    return rows.map(row => ({
      address: row.address,
      recordId: row.record_id,
      fieldRecordId: row.field_record_id,
      revision: row.revision,
      startByte: row.start_byte,
      endByte: row.end_byte,
      semanticKind: row.semantic_kind,
      contentSha256: row.content_sha256,
    }))
  }

  resolveFieldAddress(address: string): MnemicFieldAddressResolution | null {
    const exactAddress = exactFieldAddress(address, 'address')
    const row = this.db.prepare(`
      SELECT
        address, record_id, field_record_id, revision,
        start_byte, end_byte, semantic_kind, content_sha256
      FROM mnemic_field_address_manifest
      WHERE address = ?
    `).get(exactAddress) as {
      address: string
      record_id: string
      field_record_id: string
      revision: string
      start_byte: number
      end_byte: number
      semantic_kind: string
      content_sha256: string
    } | undefined
    if (!row) return null
    const record = this.cortex.getEngram(row.record_id)
    if (!record) throw new Error('field address manifest references a missing exact record')
    const expected = this.fieldAddressEntry(record)
    if (
      row.address !== expected.address
      || row.field_record_id !== expected.fieldRecordId
      || row.revision !== expected.revision
      || row.start_byte !== expected.startByte
      || row.end_byte !== expected.endByte
      || row.semantic_kind !== expected.semanticKind
      || row.content_sha256 !== expected.contentSha256
    ) throw new Error('field address manifest does not match its exact record')
    return { ...expected, record }
  }
  rememberObservation(input: MnemicObservationInput): MnemicFieldEvent {
    if (!input.recordId || Buffer.byteLength(input.recordId) > 256) {
      throw new Error('recordId must be nonempty and at most 256 UTF-8 bytes')
    }
    const revision = mnemicObservationRevision(input)
    const reference = observationReference(input)
    let appended = false
    const event = this.db.transaction(() => {
      const existing = this.db.prepare(`
        SELECT revision, event_sequence FROM mnemic_observation_records
        WHERE record_id = ?
      `).get(input.recordId) as { revision: string; event_sequence: number } | undefined
      if (existing?.revision === revision) {
        const retained = this.fieldEvent(existing.event_sequence)
        if (!retained) throw new Error('retained observation event is missing')
        return retained
      }
      const payload: Extract<MnemicFieldEventPayload, { kind: 'observation' }> = {
        kind: 'observation',
        context_session_id: input.contextSessionId.slice(0, 256),
        operation: existing ? 'update' : 'store',
        record: {
          id: input.recordId,
          revision,
          ...(existing ? { previous_revision: existing.revision } : {}),
        },
        reference,
      }
      const next = this.appendFieldEvent(payload)
      this.db.prepare(`
        INSERT INTO mnemic_observation_records
          (record_id, revision, event_sequence, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(record_id) DO UPDATE SET
          revision = excluded.revision,
          event_sequence = excluded.event_sequence,
          updated_at = excluded.updated_at
      `).run(input.recordId, revision, next.sequence, Date.now())
      appended = true
      return next
    })()
    if (appended) this.wakeFieldDrainer()
    return event
  }


  update(id: string, update: EngramUpdate): Engram | null {
    const previous = this.cortex.getEngram(id)
    return this.commit(
      () => this.cortex.updateEngram(id, {
        ...update,
        potentiation: 0,
        clusterId: null,
        embedding: null,
        x: 0,
        y: 0,
        z: 0,
      }),
      record => {
        if (!record) return null
        this.upsertFieldAddress(record)
        return this.memoryPayload(
          'update',
          record,
          record.metadata.sessionId,
          previous ?? undefined,
          true,
        )
      },
    )
  }

  delete(id: string): boolean {
    const result = this.commit(
      () => {
        const previous = this.cortex.getEngram(id)
        return { previous, removed: previous ? this.cortex.deleteEngram(id) : false }
      },
      ({ previous, removed }) => {
        if (!removed || !previous) return null
        this.deleteFieldAddress(previous.id)
        return this.memoryPayload(
          'delete',
          previous,
          previous.metadata.sessionId,
          undefined,
          true,
        )
      },
    )
    return result.removed
  }

  connect(input: SynapseCreate): MnemicSynapse {
    return this.commit(
      () => this.cortex.createSynapse(input),
      relation => this.memoryPayload('connect', {
        id: `${relation.sourceId}:${relation.edgeType}:${relation.targetId}`,
        content: JSON.stringify(relation.metadata),
        nodeType: 'relation',
      }, relation.metadata.sessionId),
    )
  }

  disconnect(sourceId: string, targetId: string, edgeType: string): boolean {
    const relation = {
      id: `${sourceId}:${edgeType}:${targetId}`,
      content: '',
      nodeType: 'relation',
    }
    return this.commit(
      () => this.cortex.deleteSynapse(sourceId, targetId, edgeType),
      removed => removed ? this.memoryPayload('disconnect', relation) : null,
    )
  }

  getEngramsByIdPrefix(
    prefix: string,
    opts: { limit?: number; offset?: number; order?: 'asc' | 'desc' } = {},
  ): Engram[] {
    return this.cortex.getEngramsByIdPrefix(prefix, opts)
  }

  searchTextStrict(query: string, limit = 20): EngramSearchResult[] {
    return this.cortex.searchTextStrict(query, limit)
  }

  async searchTextStrictAsync(
    query: string,
    limit = 20,
    _timeoutMs = 300,
  ): Promise<EngramSearchResult[]> {
    return this.cortex.searchTextStrict(query, limit)
  }

  async retrieve(query: string, options: { limit?: number } = {}): Promise<MnemicRetrievalHit[]> {
    return this.cortex.searchTextStrict(query, options.limit ?? 5).map(result => ({
      id: result.engram.id,
      content: result.engram.content,
      nodeType: result.engram.nodeType,
      score: result.score,
      charge: result.score,
      potentiation: result.engram.potentiation,
      provenance: result.engram.provenance,
      tags: result.engram.tags,
      metadata: result.engram.metadata,
    }))
  }

  rememberContextTurn(
    sessionId: string,
    turnId: number,
    query: string,
    candidates: readonly MnemicFieldCandidate[],
  ): void {
    let event: MnemicFieldEvent | null = null
    this.db.transaction(() => {
      const settled = this.db.prepare(`
        SELECT resolved_at FROM mnemic_context_feedback
        WHERE session_id = ? AND turn_id = ?
      `).get(sessionId, turnId) as { resolved_at: number | null } | undefined
      if (settled?.resolved_at != null) return

      this.db.prepare(`
        INSERT INTO mnemic_context_eligibility (session_id, turn_id, query, candidates, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_id, turn_id) DO UPDATE SET
          query = excluded.query,
          candidates = excluded.candidates,
          created_at = excluded.created_at
      `).run(
        sessionId,
        turnId,
        truncateUtf8(query, MAX_FIELD_QUERY_BYTES),
        mnemicFieldCanonicalJson(candidates.slice(0, 32).map(candidate => {
          const text = truncateUtf8(candidate.text, MAX_FIELD_CONTENT_BYTES)
          return {
            id: safeOpaqueId(candidate.id),
            record_id: safeOpaqueId(candidate.recordId),
            revision: candidate.revision,
            start_byte: candidate.startByte,
            end_byte: candidate.startByte + Buffer.byteLength(text),
            text,
            ...(candidate.fieldAddress
              ? { field_address: exactFieldAddress(candidate.fieldAddress, 'candidate fieldAddress') }
              : {}),
          }
        })),
        Date.now(),
      )
      event = this.resolveContextFeedback(sessionId, turnId)
    })()
    if (event) this.wakeFieldDrainer()
  }

  consumeContextFeedback(
    sessionId: string,
    turnId: number,
    includedCandidateIds: readonly string[],
    outcome: MnemicFeedbackOutcome,
    toolResult?: MnemicFieldToolResult,
  ): MnemicFieldEvent | null {
    let event: MnemicFieldEvent | null = null
    this.db.transaction(() => {
      this.db.prepare(`
        INSERT INTO mnemic_context_feedback
          (session_id, turn_id, included_candidate_ids, outcome, tool_result, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, turn_id) DO NOTHING
      `).run(
        sessionId,
        turnId,
        mnemicFieldCanonicalJson([...new Set(includedCandidateIds.map(safeOpaqueId))].slice(0, 8)),
        outcome,
        toolResult ? mnemicFieldCanonicalJson({
          id: safeOpaqueId(toolResult.id),
          name: safeOpaqueId(toolResult.name),
          is_error: toolResult.isError,
        }) : null,
        Date.now(),
      )
      event = this.resolveContextFeedback(sessionId, turnId)
    })()
    if (event) this.wakeFieldDrainer()
    return event
  }

  startActionEpisode(input: MnemicActionStart): MnemicFieldEvent | null {
    if (this.actionJournalVerification?.acknowledgedPrefixValid === false) {
      throw new MnemicFieldJournalError(this.actionJournalVerification)
    }
    if (
      !Number.isInteger(input.turnId)
      || input.turnId < 0
      || !/^[0-9a-f]{64}$/.test(input.argumentsSha256)
      || !Number.isFinite(input.requiredAuthority)
      || input.requiredAuthority < 0
      || input.requiredAuthority > 1
      || typeof input.reversible !== 'boolean'
    ) throw new Error('invalid exact action episode')
    const sessionId = input.contextSessionId.slice(0, 256)
    const episodeId = safeOpaqueId(input.toolCallId)
    const toolName = safeOpaqueId(input.toolName)
    const planId = safeOpaqueId(input.planId)
    const actionId = `tool:${createHash('sha256')
      .update(mnemicFieldCanonicalJson(['cassicore.action-signature.v1', toolName, input.argumentsSha256]))
      .digest('hex')
      .slice(0, 32)}`
    const recordId = `action:${createHash('sha256')
      .update(mnemicFieldCanonicalJson(['cassicore.action-record.v1', sessionId, actionId]))
      .digest('hex')
      .slice(0, 32)}`
    const kind = `tool:${toolName}`
    const authorizationPath = [
      `thalamus:plan:${planId}`,
      `omp:tool-call:${episodeId}`,
    ]
    let event: MnemicFieldEvent | null = null
    this.db.transaction(() => {
      const existing = this.db.prepare(`
        SELECT record_id, action_id, kind, turn_id, plan_id, required_authority, reversible
        FROM mnemic_action_episodes
        WHERE session_id = ? AND episode_id = ?
      `).get(sessionId, episodeId) as {
        record_id: string
        action_id: string
        kind: string
        turn_id: number
        plan_id: string
        required_authority: number
        reversible: number
      } | undefined
      if (existing) {
        if (
          existing.record_id !== recordId
          || existing.action_id !== actionId
          || existing.kind !== kind
          || existing.turn_id !== input.turnId
          || existing.plan_id !== planId
          || existing.required_authority !== input.requiredAuthority
          || Boolean(existing.reversible) !== input.reversible
        ) throw new Error('conflicting exact action episode')
        return
      }
      const state = this.db.prepare(`
        SELECT content, active_episode_id
        FROM mnemic_action_state
        WHERE record_id = ?
      `).get(recordId) as {
        content: string
        active_episode_id: string | null
      } | undefined
      if (state?.active_episode_id) {
        throw new Error('exact action signature already has an active episode')
      }
      const now = Date.now()
      this.db.prepare(`
        INSERT INTO mnemic_action_episodes
          (
            session_id, episode_id, record_id, action_id, kind, turn_id, plan_id,
            required_authority, reversible, start_sequence, effects, created_at
          )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '[]', ?)
      `).run(
        sessionId,
        episodeId,
        recordId,
        actionId,
        kind,
        input.turnId,
        planId,
        input.requiredAuthority,
        input.reversible ? 1 : 0,
        now,
      )
      this.db.prepare(`
        INSERT INTO mnemic_action_state
          (record_id, session_id, action_id, kind, content, active_episode_id, updated_at)
        VALUES (?, ?, ?, ?, '', ?, ?)
        ON CONFLICT(record_id) DO UPDATE SET
          content = '',
          active_episode_id = excluded.active_episode_id,
          updated_at = excluded.updated_at
      `).run(recordId, sessionId, actionId, kind, episodeId, now)
      const record = { id: recordId, content: '', nodeType: 'action' }
      const previous = state
        ? { id: recordId, content: state.content, nodeType: 'action' }
        : undefined
      const payload = this.memoryPayload(
        previous ? 'update' : 'store',
        record,
        sessionId,
        previous,
      ) as Extract<MnemicFieldEventPayload, { kind: 'memory' }>
      payload.action = {
        episode_id: episodeId,
        action_id: actionId,
        kind,
        stage: 'start',
        required_authority: input.requiredAuthority,
        reversible: input.reversible,
        authorization_path: authorizationPath,
      }
      event = this.appendFieldEvent(payload)
      this.db.prepare(`
        UPDATE mnemic_action_episodes SET start_sequence = ?
        WHERE session_id = ? AND episode_id = ?
      `).run(event.sequence, sessionId, episodeId)
    })()
    if (event) this.wakeFieldDrainer()
    return event
  }

  finishActionEpisode(input: MnemicActionFinish): MnemicFieldEvent | null {
    const sessionId = input.contextSessionId.slice(0, 256)
    const episodeId = safeOpaqueId(input.toolCallId)
    const outcome: MnemicActionOutcome = input.isError ? 'error' : 'completed'
    let event: MnemicFieldEvent | null = null
    this.db.transaction(() => {
      const episode = this.db.prepare(`
        SELECT
          record_id, action_id, kind, turn_id, plan_id, outcome,
          required_authority, reversible, start_sequence, effects
        FROM mnemic_action_episodes
        WHERE session_id = ? AND episode_id = ?
      `).get(sessionId, episodeId) as {
        record_id: string
        action_id: string
        kind: string
        turn_id: number
        plan_id: string
        outcome: MnemicActionOutcome | null
        required_authority: number
        reversible: number
        start_sequence: number
        effects: string
      } | undefined
      if (!episode) throw new Error('exact action episode was not started')
      if (
        episode.turn_id !== input.turnId
        || episode.plan_id !== safeOpaqueId(input.planId)
      ) throw new Error('exact action outcome provenance does not match its start')
      if (episode.outcome) {
        if (episode.outcome !== outcome) {
          throw new Error('conflicting exact action outcome')
        }
        return
      }
      const state = this.db.prepare(`
        SELECT content, active_episode_id
        FROM mnemic_action_state
        WHERE record_id = ?
      `).get(episode.record_id) as {
        content: string
        active_episode_id: string | null
      } | undefined
      if (!state || state.active_episode_id !== episodeId || state.content !== '') {
        throw new Error('exact action episode state is inconsistent')
      }
      const effects = this.actionEffects(sessionId, episode.start_sequence, input.effects)
      const now = Date.now()
      this.db.prepare(`
        UPDATE mnemic_action_state
        SET content = ?, active_episode_id = NULL, updated_at = ?
        WHERE record_id = ?
      `).run(outcome, now, episode.record_id)
      this.db.prepare(`
        UPDATE mnemic_action_episodes
        SET outcome = ?, effects = ?, resolved_at = ?
        WHERE session_id = ? AND episode_id = ?
      `).run(outcome, mnemicFieldCanonicalJson(effects), now, sessionId, episodeId)
      const previous = { id: episode.record_id, content: '', nodeType: 'action' }
      const record = { id: episode.record_id, content: outcome, nodeType: 'action' }
      const payload = this.memoryPayload(
        'update',
        record,
        sessionId,
        previous,
      ) as Extract<MnemicFieldEventPayload, { kind: 'memory' }>
      payload.action = {
        episode_id: episodeId,
        action_id: episode.action_id,
        kind: episode.kind,
        stage: 'outcome',
        required_authority: episode.required_authority,
        reversible: Boolean(episode.reversible),
        authorization_path: [
          `thalamus:plan:${episode.plan_id}`,
          `omp:tool-call:${episodeId}`,
        ],
        outcome,
        ...(effects.length > 0 ? { effects } : {}),
      }
      event = this.appendFieldEvent(payload)
    })()
    if (event) this.wakeFieldDrainer()
    return event
  }

  fieldStreamStatus(): MnemicFieldStreamStatus {
    const stream = this.db.prepare(`
      SELECT stream_id, last_sequence, head_event_id
      FROM mnemic_field_stream WHERE singleton = 1
    `).get() as { stream_id: string; last_sequence: number; head_event_id: string }
    const acknowledged = this.db.prepare(`
      SELECT COALESCE(MAX(sequence), 0) AS sequence
      FROM mnemic_field_events WHERE acknowledged_at IS NOT NULL
    `).get() as { sequence: number }
    return {
      streamId: stream.stream_id,
      headSequence: stream.last_sequence,
      headEventId: stream.head_event_id,
      acknowledgedSequence: acknowledged.sequence,
    }
  }

  verifyFieldJournal(): MnemicFieldJournalVerification {
    const stream = this.fieldStreamStatus()
    const checkedAt = Date.now()
    const rows = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events
      ORDER BY sequence ASC
    `).all() as Array<{
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    }>
    const invalid = (
      code: MnemicFieldJournalVerificationCode,
      sequence: number,
      checkedThroughSequence: number,
      message: string,
    ): MnemicFieldJournalVerification => {
      const verification: MnemicFieldJournalVerification = {
        schemaVersion: 1,
        status: 'invalid',
        streamId: stream.streamId,
        checkedThroughSequence,
        acknowledgedSequence: stream.acknowledgedSequence,
        acknowledgedPrefixValid: sequence > stream.acknowledgedSequence,
        headSequence: stream.headSequence,
        headEventId: stream.headEventId,
        checkedAt,
        failure: { code, sequence, message },
      }
      this.lastJournalVerification = verification
      return verification
    }

    let previousEventId = EMPTY_EVENT_ID
    let checkedThroughSequence = 0
    for (const row of rows) {
      const expectedSequence = checkedThroughSequence + 1
      if (row.sequence !== expectedSequence) {
        return invalid('sequence-gap', expectedSequence, checkedThroughSequence, 'field event sequence is not contiguous')
      }
      if (row.stream_id !== stream.streamId) {
        return invalid('stream-mismatch', row.sequence, checkedThroughSequence, 'field event belongs to another stream')
      }
      if (row.previous_event_id !== previousEventId) {
        return invalid('previous-event', row.sequence, checkedThroughSequence, 'field event predecessor does not match')
      }
      let payload: unknown
      try {
        payload = JSON.parse(row.payload) as unknown
      } catch {
        return invalid('canonical-payload', row.sequence, checkedThroughSequence, 'field event payload is not JSON')
      }
      if (mnemicFieldCanonicalJson(payload) !== row.payload) {
        return invalid('canonical-payload', row.sequence, checkedThroughSequence, 'field event payload is not canonical wire JSON')
      }
      const expectedEventId = createHash('sha256').update(mnemicFieldCanonicalJson({
        stream_id: row.stream_id,
        sequence: row.sequence,
        previous_event_id: row.previous_event_id,
        payload,
      })).digest('hex')
      if (row.event_id !== expectedEventId) {
        return invalid('event-hash', row.sequence, checkedThroughSequence, 'field event hash does not match its wire payload')
      }
      previousEventId = row.event_id
      checkedThroughSequence = row.sequence
    }

    const acknowledgementGap = this.db.prepare(`
      SELECT MIN(sequence) AS sequence
      FROM mnemic_field_events
      WHERE sequence <= ? AND acknowledged_at IS NULL
    `).get(stream.acknowledgedSequence) as { sequence: number | null }
    if (acknowledgementGap.sequence != null) {
      return invalid(
        'acknowledgement-gap',
        acknowledgementGap.sequence,
        checkedThroughSequence,
        'acknowledged field prefix contains an unacknowledged event',
      )
    }
    if (checkedThroughSequence !== stream.headSequence || previousEventId !== stream.headEventId) {
      return invalid(
        'head-mismatch',
        Math.max(1, checkedThroughSequence),
        checkedThroughSequence,
        'field stream head does not match its exact events',
      )
    }
    const verification: MnemicFieldJournalVerification = {
      schemaVersion: 1,
      status: 'valid',
      streamId: stream.streamId,
      checkedThroughSequence,
      acknowledgedSequence: stream.acknowledgedSequence,
      acknowledgedPrefixValid: true,
      headSequence: stream.headSequence,
      headEventId: stream.headEventId,
      checkedAt,
    }
    this.lastJournalVerification = verification
    return verification
  }

  requireVerifiedActionJournal(verification: MnemicFieldJournalVerification | null): void {
    if (verification && verification.streamId !== this.fieldStreamStatus().streamId) {
      throw new Error('journal verification belongs to another exact stream')
    }
    this.actionJournalVerification = verification
  }

  fieldJournalVerificationStatus(): MnemicFieldJournalVerification {
    if (this.lastJournalVerification) return this.lastJournalVerification
    const stream = this.fieldStreamStatus()
    return {
      schemaVersion: 1,
      status: 'not-run',
      streamId: stream.streamId,
      checkedThroughSequence: 0,
      acknowledgedSequence: stream.acknowledgedSequence,
      acknowledgedPrefixValid: true,
      headSequence: stream.headSequence,
      headEventId: stream.headEventId,
      checkedAt: null,
    }
  }

  unresolvedActionEpisodes(limit = 64): MnemicUnresolvedActionEpisode[] {
    const rows = this.db.prepare(`
      SELECT
        session_id, episode_id, record_id, action_id, kind, turn_id, plan_id,
        required_authority, reversible, created_at
      FROM mnemic_action_episodes
      WHERE outcome IS NULL
      ORDER BY created_at ASC, episode_id ASC
      LIMIT ?
    `).all(Math.min(256, Math.max(1, Math.floor(limit)))) as Array<{
      session_id: string
      episode_id: string
      record_id: string
      action_id: string
      kind: string
      turn_id: number
      plan_id: string
      required_authority: number
      reversible: number
      created_at: number
    }>
    return rows.map(row => ({
      episodeId: row.episode_id,
      recordId: row.record_id,
      actionId: row.action_id,
      kind: row.kind,
      contextSessionId: row.session_id,
      turnId: row.turn_id,
      planId: row.plan_id,
      toolCallId: row.episode_id,
      requiredAuthority: row.required_authority,
      reversible: Boolean(row.reversible),
      startedAt: row.created_at,
    }))
  }

  fieldEvent(sequence: number): MnemicFieldEvent | null {
    const row = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events WHERE sequence = ?
    `).get(sequence) as {
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    } | undefined
    return row ? this.mapFieldEvent(row) : null
  }

  fieldEventsAfter(sequence: number, limit = 256): MnemicFieldEvent[] {
    const rows = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events
      WHERE sequence > ?
      ORDER BY sequence ASC
      LIMIT ?
    `).all(sequence, Math.min(1_024, Math.max(1, Math.floor(limit)))) as Array<{
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    }>
    return rows.map(row => this.mapFieldEvent(row))
  }

  fieldRecordEvents(
    recordId: string,
    throughSequence: number,
    limit = 16,
  ): MnemicFieldEvent[] {
    const rows = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events
      WHERE sequence <= ?
        AND json_extract(payload, '$.kind') = 'memory'
        AND json_extract(payload, '$.record.id') = ?
      ORDER BY sequence DESC
      LIMIT ?
    `).all(
      Math.max(0, Math.floor(throughSequence)),
      safeOpaqueId(recordId),
      Math.min(64, Math.max(1, Math.floor(limit))),
    ) as Array<{
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    }>
    return rows.map(row => this.mapFieldEvent(row)).reverse()
  }

  fieldSemanticUpdateEvents(
    semanticKind: string,
    throughSequence: number,
    limit = 32,
  ): MnemicFieldEvent[] {
    const rows = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events
      WHERE sequence < ?
        AND json_extract(payload, '$.kind') = 'memory'
        AND json_extract(payload, '$.operation') = 'update'
        AND json_type(payload, '$.action') IS NULL
        AND json_type(payload, '$.previous_record') = 'object'
        AND json_extract(payload, '$.record.node_type') = ?
      ORDER BY sequence DESC
      LIMIT ?
    `).all(
      Math.max(0, Math.floor(throughSequence)),
      safeOpaqueId(semanticKind),
      Math.min(64, Math.max(1, Math.floor(limit))),
    ) as Array<{
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    }>
    return rows.map(row => this.mapFieldEvent(row)).reverse()
  }

  fieldActionOutcomeEvents(
    throughSequence: number,
    limit = 64,
  ): MnemicFieldEvent[] {
    const rows = this.db.prepare(`
      SELECT stream_id, sequence, previous_event_id, event_id, payload
      FROM mnemic_field_events
      WHERE sequence < ?
        AND json_extract(payload, '$.kind') = 'memory'
        AND json_extract(payload, '$.action.stage') = 'outcome'
      ORDER BY sequence DESC
      LIMIT ?
    `).all(
      Math.max(0, Math.floor(throughSequence)),
      Math.min(128, Math.max(1, Math.floor(limit))),
    ) as Array<{
      stream_id: string
      sequence: number
      previous_event_id: string
      event_id: string
      payload: string
    }>
    return rows.map(row => this.mapFieldEvent(row)).reverse()
  }

  acknowledgeFieldEventsThrough(sequence: number, eventId: string): void {
    if (sequence === 0) return
    const event = this.fieldEvent(sequence)
    if (!event || event.eventId !== eventId) {
      throw new Error(`field event watermark mismatch at sequence ${sequence}`)
    }
    this.db.prepare(`
      UPDATE mnemic_field_events
      SET acknowledged_at = COALESCE(acknowledged_at, ?)
      WHERE sequence <= ?
    `).run(Date.now(), sequence)
  }

  stats(): FieldStats {
    return this.cortex.stats()
  }

  close(): void {
    this.cortex.close()
  }

  private initializeFieldJournal(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS mnemic_field_stream (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        stream_id TEXT NOT NULL UNIQUE,
        last_sequence INTEGER NOT NULL,
        head_event_id TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS mnemic_field_events (
        stream_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        previous_event_id TEXT NOT NULL,
        event_id TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        acknowledged_at INTEGER,
        PRIMARY KEY (stream_id, sequence)
      );
      CREATE TABLE IF NOT EXISTS mnemic_context_eligibility (
        session_id TEXT NOT NULL,
        turn_id INTEGER NOT NULL,
        query TEXT NOT NULL,
        candidates TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        PRIMARY KEY (session_id, turn_id)
      );
      CREATE TABLE IF NOT EXISTS mnemic_context_feedback (
        session_id TEXT NOT NULL,
        turn_id INTEGER NOT NULL,
        included_candidate_ids TEXT NOT NULL,
        outcome TEXT NOT NULL,
        tool_result TEXT,
        created_at INTEGER NOT NULL,
        resolved_at INTEGER,
        PRIMARY KEY (session_id, turn_id)
      );
      CREATE TABLE IF NOT EXISTS mnemic_action_state (
        record_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        action_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        active_episode_id TEXT,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS mnemic_observation_records (
        record_id TEXT PRIMARY KEY,
        revision TEXT NOT NULL,
        event_sequence INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS mnemic_field_address_manifest (
        address TEXT PRIMARY KEY,
        record_id TEXT NOT NULL UNIQUE REFERENCES engrams(id) ON DELETE CASCADE,
        field_record_id TEXT NOT NULL,
        revision TEXT NOT NULL,
        start_byte INTEGER NOT NULL,
        end_byte INTEGER NOT NULL,
        semantic_kind TEXT NOT NULL,
        content_sha256 TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS mnemic_field_address_announcements (
        address TEXT PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        announced_at INTEGER NOT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS idx_mnemic_action_state_session_action
        ON mnemic_action_state(session_id, action_id);
      CREATE TABLE IF NOT EXISTS mnemic_action_episodes (
        session_id TEXT NOT NULL,
        episode_id TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        turn_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        required_authority REAL NOT NULL DEFAULT 1,
        reversible INTEGER NOT NULL DEFAULT 0,
        start_sequence INTEGER NOT NULL DEFAULT 0,
        effects TEXT NOT NULL DEFAULT '[]',
        outcome TEXT,
        created_at INTEGER NOT NULL,
        resolved_at INTEGER,
        PRIMARY KEY (session_id, episode_id)
      );
      CREATE INDEX IF NOT EXISTS idx_mnemic_action_episodes_record
        ON mnemic_action_episodes(record_id, created_at);
    `)
    const feedbackColumns = this.db.prepare('PRAGMA table_info(mnemic_context_feedback)').all() as Array<{ name: string }>
    if (!feedbackColumns.some(column => column.name === 'tool_result')) {
      this.db.exec('ALTER TABLE mnemic_context_feedback ADD COLUMN tool_result TEXT')
    }
    const actionColumns = this.db.prepare('PRAGMA table_info(mnemic_action_episodes)').all() as Array<{ name: string }>
    const actionMigrations = [
      ['required_authority', 'REAL NOT NULL DEFAULT 1'],
      ['reversible', 'INTEGER NOT NULL DEFAULT 0'],
      ['start_sequence', 'INTEGER NOT NULL DEFAULT 0'],
      ['effects', "TEXT NOT NULL DEFAULT '[]'"],
    ] as const
    for (const [name, declaration] of actionMigrations) {
      if (!actionColumns.some(column => column.name === name)) {
        this.db.exec(`ALTER TABLE mnemic_action_episodes ADD COLUMN ${name} ${declaration}`)
      }
    }
    this.db.prepare(`
      INSERT OR IGNORE INTO mnemic_field_stream
        (singleton, stream_id, last_sequence, head_event_id)
      VALUES (1, ?, 0, ?)
    `).run(randomUUID(), EMPTY_EVENT_ID)
    this.db.transaction(() => {
      const records = this.db.prepare(`
        SELECT id, content, node_type FROM engrams ORDER BY id
      `).all() as Array<{ id: string; content: string; node_type: string }>
      for (const record of records) {
        this.upsertFieldAddress({
          id: record.id,
          content: record.content,
          nodeType: record.node_type,
        })
      }

      const historical = this.db.prepare(`
        SELECT
          json_extract(events.payload, '$.record.field_address') AS address,
          events.event_id,
          events.created_at
        FROM mnemic_field_events AS events
        INNER JOIN mnemic_field_address_manifest AS manifest
          ON manifest.address = json_extract(events.payload, '$.record.field_address')
        WHERE json_type(events.payload, '$.record.field_address') = 'text'
        ORDER BY events.sequence
      `).all() as Array<{ address: string; event_id: string; created_at: number }>
      for (const event of historical) {
        this.recordFieldAddressAnnouncement(event.address, event.event_id, event.created_at)
      }

      const unannounced = this.db.prepare(`
        SELECT manifest.record_id
        FROM mnemic_field_address_manifest AS manifest
        LEFT JOIN mnemic_field_address_announcements AS announcements
          ON announcements.address = manifest.address
        WHERE announcements.address IS NULL
        ORDER BY manifest.record_id
      `).all() as Array<{ record_id: string }>
      for (const row of unannounced) {
        const record = this.cortex.getEngram(row.record_id)
        if (!record) throw new Error('field address manifest record is missing')
        const event = this.appendFieldEvent(this.memoryPayload(
          'store',
          record,
          record.metadata.sessionId,
          undefined,
          true,
        ))
        this.announceFieldEvent(event)
      }
    })()
  }

  private actionEffects(
    sessionId: string,
    startSequence: number,
    supplied: readonly MnemicActionEffect[] = [],
  ): MnemicActionEffect[] {
    const normalize = (effect: MnemicActionEffect): MnemicActionEffect => {
      if (
        !/^[0-9a-f]{64}$/.test(effect.before_revision)
        || !/^[0-9a-f]{64}$/.test(effect.after_revision)
        || !Number.isInteger(effect.start_byte)
        || !Number.isInteger(effect.end_byte)
        || effect.start_byte < 0
        || effect.end_byte < effect.start_byte
      ) throw new Error('invalid exact action effect')
      return {
        record_id: safeOpaqueId(effect.record_id),
        before_revision: effect.before_revision,
        after_revision: effect.after_revision,
        semantic_kind: safeOpaqueId(effect.semantic_kind),
        start_byte: effect.start_byte,
        end_byte: effect.end_byte,
      }
    }
    const exact = new Map<string, MnemicActionEffect>()
    const rows = this.db.prepare(`
      SELECT payload
      FROM mnemic_field_events
      WHERE sequence > ?
        AND json_extract(payload, '$.context_session_id') = ?
        AND json_extract(payload, '$.kind') = 'memory'
        AND json_type(payload, '$.action') IS NULL
        AND json_type(payload, '$.previous_record') = 'object'
      ORDER BY sequence ASC
      LIMIT 32
    `).all(Math.max(0, Math.floor(startSequence)), sessionId) as Array<{ payload: string }>
    for (const row of rows) {
      const payload = JSON.parse(row.payload) as Extract<MnemicFieldEventPayload, { kind: 'memory' }>
      if (!payload.previous_record) continue
      const effect = normalize({
        record_id: payload.record.id,
        before_revision: payload.previous_record.revision,
        after_revision: payload.record.revision,
        semantic_kind: `mnemic:${payload.operation}`,
        start_byte: 0,
        end_byte: Buffer.byteLength(payload.record.content),
      })
      exact.set(mnemicFieldCanonicalJson(effect), effect)
    }
    for (const effect of supplied.map(normalize)) {
      if (!exact.has(mnemicFieldCanonicalJson(effect))) {
        throw new Error('exact action effect is not present after its action start')
      }
    }
    return [...exact.values()]
  }

  private resolveContextFeedback(sessionId: string, turnId: number): MnemicFieldEvent | null {
    const feedback = this.db.prepare(`
      SELECT included_candidate_ids, outcome, tool_result, resolved_at
      FROM mnemic_context_feedback
      WHERE session_id = ? AND turn_id = ?
    `).get(sessionId, turnId) as {
      included_candidate_ids: string
      outcome: MnemicFeedbackOutcome
      tool_result: string | null
      resolved_at: number | null
    } | undefined
    if (!feedback || feedback.resolved_at != null) return null

    const eligibility = this.db.prepare(`
      SELECT query, candidates FROM mnemic_context_eligibility
      WHERE session_id = ? AND turn_id = ?
    `).get(sessionId, turnId) as { query: string; candidates: string } | undefined
    if (!eligibility) return null

    const included = new Set(JSON.parse(feedback.included_candidate_ids) as string[])
    const stored = JSON.parse(eligibility.candidates) as MnemicFieldEventCandidate[]
    const payload: Extract<MnemicFieldEventPayload, { kind: 'feedback' }> = {
      kind: 'feedback',
      context_session_id: sessionId.slice(0, 256),
      turn_id: turnId,
      query: eligibility.query,
      candidates: stored.filter(candidate => included.has(candidate.id)).slice(0, 8),
      outcome: feedback.outcome,
    }
    if (feedback.tool_result) {
      payload.tool_result = JSON.parse(feedback.tool_result) as MnemicFieldEventToolResult
    }
    const event = this.appendFieldEvent(payload)
    this.db.prepare(`
      DELETE FROM mnemic_context_eligibility
      WHERE session_id = ? AND turn_id = ?
    `).run(sessionId, turnId)
    this.db.prepare(`
      UPDATE mnemic_context_feedback
      SET resolved_at = ?
      WHERE session_id = ? AND turn_id = ?
    `).run(Date.now(), sessionId, turnId)
    return event
  }

  private commit<T>(
    mutate: () => T,
    payloadFor: (value: T) => MnemicFieldEventPayload | null,
  ): T {
    let appended = false
    const value = this.db.transaction(() => {
      const result = mutate()
      const payload = payloadFor(result)
      if (payload) {
        const event = this.appendFieldEvent(payload)
        this.announceFieldEvent(event)
        appended = true
      }
      return result
    })()
    if (appended) this.wakeFieldDrainer()
    return value
  }

  private fieldAddressEntry(
    record: { id: string; content: string; nodeType: string },
  ): MnemicFieldAddressEntry {
    const fieldRecordId = safeOpaqueId(record.id)
    const revision = mnemicRecordRevision(record)
    const startByte = 0
    const endByte = Buffer.byteLength(record.content)
    const semanticKind = record.nodeType
    return {
      address: mnemicFieldAddress({
        recordId: fieldRecordId,
        revision,
        startByte,
        endByte,
        semanticKind,
      }),
      recordId: record.id,
      fieldRecordId,
      revision,
      startByte,
      endByte,
      semanticKind,
      contentSha256: createHash('sha256').update(record.content).digest('hex'),
    }
  }

  private upsertFieldAddress(
    record: { id: string; content: string; nodeType: string },
  ): void {
    const entry = this.fieldAddressEntry(record)
    const existing = this.db.prepare(`
      SELECT
        address, field_record_id, revision, start_byte, end_byte,
        semantic_kind, content_sha256
      FROM mnemic_field_address_manifest
      WHERE record_id = ?
    `).get(entry.recordId) as {
      address: string
      field_record_id: string
      revision: string
      start_byte: number
      end_byte: number
      semantic_kind: string
      content_sha256: string
    } | undefined
    if (
      existing?.address === entry.address
      && existing.field_record_id === entry.fieldRecordId
      && existing.revision === entry.revision
      && existing.start_byte === entry.startByte
      && existing.end_byte === entry.endByte
      && existing.semantic_kind === entry.semanticKind
      && existing.content_sha256 === entry.contentSha256
    ) return
    this.db.prepare('DELETE FROM mnemic_field_address_manifest WHERE record_id = ?')
      .run(entry.recordId)
    this.db.prepare(`
      INSERT INTO mnemic_field_address_manifest (
        address, record_id, field_record_id, revision,
        start_byte, end_byte, semantic_kind, content_sha256
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      entry.address,
      entry.recordId,
      entry.fieldRecordId,
      entry.revision,
      entry.startByte,
      entry.endByte,
      entry.semanticKind,
      entry.contentSha256,
    )
  }

  private deleteFieldAddress(recordId: string): void {
    this.db.prepare('DELETE FROM mnemic_field_address_manifest WHERE record_id = ?')
      .run(recordId)
  }

  private memoryPayload(
    operation: MnemicRecordOperation,
    record: { id: string; content: string; nodeType: string },
    contextSessionId?: unknown,
    previousRecord?: { id: string; content: string; nodeType: string },
    recallable = false,
  ): MnemicFieldEventPayload {
    const payload: Extract<MnemicFieldEventPayload, { kind: 'memory' }> = {
      kind: 'memory',
      context_session_id: typeof contextSessionId === 'string'
        ? contextSessionId.slice(0, 256)
        : '',
      operation,
      record: fieldEventRecord(record, recallable),
    }
    if (previousRecord) {
      payload.previous_record = fieldEventRecord(previousRecord, recallable)
    }
    return payload
  }
  private recordFieldAddressAnnouncement(
    address: string,
    eventId: string,
    announcedAt = Date.now(),
  ): void {
    this.db.prepare(`
      INSERT OR IGNORE INTO mnemic_field_address_announcements
        (address, event_id, announced_at)
      VALUES (?, ?, ?)
    `).run(address, eventId, announcedAt)
  }

  private announceFieldEvent(event: MnemicFieldEvent): void {
    if (event.payload.kind !== 'memory') return
    const address = event.payload.record.field_address
    if (!address) return
    this.recordFieldAddressAnnouncement(address, event.eventId)
  }


  private appendFieldEvent(payload: MnemicFieldEventPayload): MnemicFieldEvent {
    const stream = this.db.prepare(`
      SELECT stream_id, last_sequence, head_event_id
      FROM mnemic_field_stream WHERE singleton = 1
    `).get() as { stream_id: string; last_sequence: number; head_event_id: string }
    const sequence = stream.last_sequence + 1
    const identity = {
      stream_id: stream.stream_id,
      sequence,
      previous_event_id: stream.head_event_id,
      payload,
    }
    const eventId = createHash('sha256').update(mnemicFieldCanonicalJson(identity)).digest('hex')
    const payloadJson = mnemicFieldCanonicalJson(payload)
    this.db.prepare(`
      INSERT INTO mnemic_field_events
        (stream_id, sequence, previous_event_id, event_id, payload, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      stream.stream_id,
      sequence,
      stream.head_event_id,
      eventId,
      payloadJson,
      Date.now(),
    )
    this.db.prepare(`
      UPDATE mnemic_field_stream
      SET last_sequence = ?, head_event_id = ?
      WHERE singleton = 1
    `).run(sequence, eventId)
    return {
      streamId: stream.stream_id,
      sequence,
      previousEventId: stream.head_event_id,
      eventId,
      payload,
    }
  }

  private mapFieldEvent(row: {
    stream_id: string
    sequence: number
    previous_event_id: string
    event_id: string
    payload: string
  }): MnemicFieldEvent {
    return {
      streamId: row.stream_id,
      sequence: row.sequence,
      previousEventId: row.previous_event_id,
      eventId: row.event_id,
      payload: JSON.parse(row.payload) as MnemicFieldEventPayload,
    }
  }

  private wakeFieldDrainer(): void {
    try {
      this.onFieldEvent?.()
    } catch (error) {
      this.logger.warn('Mnemic field drainer wake failed (non-fatal)', { error: String(error) })
    }
  }
}
