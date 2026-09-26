/**
 * @cassicore/mind-runtime — context candidate service (P8 shared context seam).
 *
 * Backs `POST /v1/context/candidates` + `POST /v1/context/feedback`. The spine
 * asks the runtime for typed Mnemic context candidates for a turn and reports
 * which candidate IDs the plan accepted/rejected.
 *
 * Hard guarantees:
 * - Bounded + validated request fields (malformed → `ContextRequestError` 400).
 * - The exact store exposes only a bounded opaque address manifest. CassiFI's
 *   Qi field selects one whole address or abstains; exact bytes are resolved
 *   only after selection. There is no FTS relevance fallback.
 * - Provider failures remain observable as source errors and return no memory.
 * - Hard request-side deadline: recall races the deadline and FAILS OPEN — a
 *   timeout returns 200 with empty candidates plus a timeout source status,
 *   never a 5xx and never a stalled request.
 * - Optional field shadow (`includeFieldShadow`): a CACHED, bounded summary of
 *   the 7599 readout (`mode:'shadow'`). It is advisory-only — it never alters
 *   candidate scores and candidate responses NEVER wait on a fresh 7599 read.
 *   At most one background field read runs at a time (concurrent triggers
 *   coalesce); grid arrays are dropped immediately after summarizing; offline
 *   or disabled telemetry degrades to `fieldAdvisory: null` + status.
 * - Feedback accepts IDs/outcome only, publishes an observable retained bus
 *   event (`cassi.context.feedback`), and may trigger the next cached field
 *   refresh. It never writes raw transcript text or fabricates outcomes.
 */

import { createHash } from 'node:crypto'
import { setTimeout as delay } from 'node:timers/promises'

import type { IEventBus, ILogger } from '@cassicore/foundation'
import type {
  MnemicActionFinish,
  MnemicActionEffect,
  MnemicActionStart,
  MnemicExactStore,
  MnemicFieldCandidate,
  MnemicFieldEvent,
  MnemicFieldEventPayload,
} from '@cassicore/mnemic-field'
import type { MemoryHitView } from '../memory/backend.js'
import type { FieldTelemetrySnapshot, FieldTelemetryStatus } from '../field/telemetry.js'
import type {
  ContextCandidate,
  ContextCandidatesRequest,
  ContextActionRequest,
  ContextActionResponse,
  ContextCandidatesResponse,
  ContextFeedbackOutcome,
  ContextFeedbackToolResult,
  ContextFeedbackRequest,
  ContextFeedbackResponse,
  ContextSourceStatus,
  FieldAdvisory,
  ContextCounterflowBucket,
  ContextCounterflowStatus,
  ContextFieldFailureCode,
} from '../channel/protocol.js'

/** Exact address manifest and record resolution used by field-native recall. */
export interface ContextMemorySurface {
  fieldAddressManifest(excludeSessionId: string): readonly string[]
  resolveFieldAddress(address: string): MemoryHitView | null
  rememberContextTurn?(
    sessionId: string,
    turnId: number,
    query: string,
    candidates: readonly MnemicFieldCandidate[],
  ): void
  consumeContextFeedback?(
    sessionId: string,
    turnId: number,
    includedCandidateIds: readonly string[],
    outcome: ContextFeedbackOutcome,
    toolResult?: ContextFeedbackToolResult,
  ): void
  startActionEpisode?(input: MnemicActionStart): void
  finishActionEpisode?(input: MnemicActionFinish): void
}

/** The narrow field-telemetry surface (satisfied by `MindFieldTelemetry`). */
export interface ContextFieldTelemetrySurface {
  read(): Promise<FieldTelemetrySnapshot | null>
  status(): FieldTelemetryStatus
}

export interface ContextFieldRecallResult {
  address: string | null
  signal: number
  selectionMargin: number
  availability: number
}

export type ContextFieldRecaller = (request: {
  sessionId: string
  query: string
  addresses: readonly string[]
  deadlineMs: number
}) => Promise<ContextFieldRecallResult>


export interface ContextCounterflowFeatures {
  failureInhibition?: boolean
  actionRoleAbstraction?: boolean
  lineageRoleAbstraction?: boolean
  multiActionTrajectories?: boolean
  shadowSupportThreshold?: number
}


export interface ContextFieldClientErrorOptions {
  statusCode?: number
  cause?: unknown
}

export class ContextFieldClientError extends Error {
  readonly statusCode: number | undefined

  constructor(
    public readonly code: ContextFieldFailureCode,
    message: string,
    options: ContextFieldClientErrorOptions = {},
  ) {
    super(message, { cause: options.cause })
    this.name = 'ContextFieldClientError'
    this.statusCode = options.statusCode
  }
}

export interface ContextFieldClientOptions extends ContextCounterflowFeatures {}
export interface ContextFieldClient {
  recall: ContextFieldRecaller
  notify(): void
  flush(): Promise<void>
  close(): Promise<void>
  status(): ContextCounterflowStatus
}

const SHARED_CONTEXT_FIELD_SESSION = 'cassicore-context'
const FIELD_QUERY_MAX_BYTES = 8 * 1_024

function truncateUtf8(value: string, maxBytes: number): string {
  let bytes = 0
  let end = 0
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0
    const width = codePoint <= 0x7f ? 1 : codePoint <= 0x7ff ? 2 : codePoint <= 0xffff ? 3 : 4
    if (bytes + width > maxBytes) break
    bytes += width
    end += character.length
  }
  return end === value.length ? value : value.slice(0, end)
}

type MnemicMemoryEvent = Extract<MnemicFieldEventPayload, { kind: 'memory' }>
type MnemicEventRecord = MnemicMemoryEvent['record']

const NO_COUNTERFLOW_TRANSITION: Record<string, unknown> = {
  mode: 'plan',
  observations: [],
  trajectory: [],
  policy: {},
}

interface CounterflowRequest {
  body: Record<string, unknown>
  predictive: boolean
  hasTrainingData: boolean
}

function counterflowExactIdentity(
  recordId: string,
  revision: string,
  startByte: number,
  endByte: number,
  semanticKind: string,
): Record<string, unknown> {
  const address = createHash('sha256')
    .update(JSON.stringify([
      'cassicore.mnemic.counterflow-address.v1',
      recordId,
      revision,
      startByte,
      endByte,
      semanticKind,
    ]))
    .digest()
    .subarray(0, 16)
    .toString('hex')
  return {
    record_id: recordId,
    address,
    revision,
    start_byte: startByte,
    end_byte: endByte,
    semantic_kind: semanticKind,
  }
}

function counterflowIdentity(record: MnemicEventRecord): Record<string, unknown> {
  return counterflowExactIdentity(
    record.id,
    record.revision,
    0,
    Buffer.byteLength(record.content),
    record.node_type || 'memory',
  )
}

function counterflowActionEffectIdentity(effect: MnemicActionEffect): Record<string, unknown> {
  return counterflowExactIdentity(
    effect.record_id,
    effect.after_revision,
    effect.start_byte,
    effect.end_byte,
    effect.semantic_kind,
  )
}

function actionOutcomeIdentity(payload: MnemicMemoryEvent): Record<string, unknown> {
  const effects = payload.action?.effects ?? []
  return effects.length === 1
    ? counterflowActionEffectIdentity(effects[0]!)
    : counterflowIdentity(payload.record)
}

function actionCounterflowRequest(
  event: MnemicFieldEvent,
  outbox: MnemicExactStore,
  features: Required<Omit<ContextCounterflowFeatures, 'shadowSupportThreshold'>>,
): CounterflowRequest | null {
  const payload = event.payload
  if (payload.kind !== 'memory' || !payload.action) return null
  const action = payload.action
  const currentRecord = action.stage === 'start'
    ? payload.record
    : payload.previous_record
  if (!currentRecord || currentRecord.id !== payload.record.id) {
    throw new Error('mnemic-counterflow-action-state-mismatch')
  }

  if (features.multiActionTrajectories && action.stage === 'outcome') {
    const outcomes = outbox.fieldActionOutcomeEvents(event.sequence, 128)
      .filter(candidate => candidate.payload.kind === 'memory'
        && candidate.payload.context_session_id === payload.context_session_id
        && candidate.payload.action?.stage === 'outcome'
        && candidate.payload.action.outcome === 'completed'
        && candidate.payload.previous_record !== undefined)
    const observations = outcomes.slice(1).map((nextEvent, index) => {
      const previous = outcomes[index]!.payload as MnemicMemoryEvent
      const next = nextEvent.payload as MnemicMemoryEvent
      const evidence = next.action!
      return {
        id: `trajectory:${outcomes[index]!.eventId}:${nextEvent.eventId}`,
        before: actionOutcomeIdentity(previous),
        after: counterflowIdentity(next.previous_record!),
        symbol: `trajectory:${evidence.kind}`,
        outcome: evidence.outcome,
        action: {
          id: evidence.action_id,
          kind: evidence.kind,
          required_authority: evidence.required_authority,
          reversible: evidence.reversible,
          effects: evidence.effects ?? [],
        },
      }
    }).slice(-8)
    const body: Record<string, unknown> = {
      mode: 'predict',
      observations,
      current: actionOutcomeIdentity(payload),
      observed_outcome: action.outcome,
      policy: {
        eligible_observation_ids: observations.map(observation => observation.id),
        permitted_action_kinds: [...new Set(observations.map(observation => observation.action.kind))],
        authority: action.required_authority,
        authorization_path: action.authorization_path,
      },
      trajectory_mode: 'next-action',
    }
    if (features.failureInhibition) body.failure_inhibition = true
    return {
      body,
      predictive: true,
      hasTrainingData: observations.length > 0,
    }
  }

  const sourceEvents = features.actionRoleAbstraction
    ? outbox.fieldActionOutcomeEvents(event.sequence, 128)
    : outbox.fieldRecordEvents(payload.record.id, event.sequence, 64)
  const trainingEvents = sourceEvents
    .filter(candidate => {
      if (candidate.payload.kind !== 'memory') return false
      const evidence = candidate.payload.action
      if (
        evidence?.stage !== 'outcome'
        || candidate.eventId === event.eventId
        || candidate.payload.previous_record === undefined
        || (evidence.outcome !== 'completed'
          && !(features.failureInhibition && evidence.outcome === 'error'))
      ) return false
      return evidence.action_id === action.action_id
        || (
          features.actionRoleAbstraction
          && evidence.kind === action.kind
          && evidence.required_authority === action.required_authority
          && evidence.reversible === action.reversible
        )
    })
    .slice(-8)
  const observations = trainingEvents.map(trainingEvent => {
    const transition = trainingEvent.payload as MnemicMemoryEvent
    const evidence = transition.action!
    return {
      id: trainingEvent.eventId,
      before: counterflowIdentity(transition.previous_record!),
      after: actionOutcomeIdentity(transition),
      symbol: evidence.kind,
      outcome: evidence.outcome,
      action: {
        id: features.actionRoleAbstraction ? action.action_id : evidence.action_id,
        kind: action.kind,
        required_authority: action.required_authority,
        reversible: action.reversible,
        effects: evidence.effects ?? [],
      },
    }
  })
  const body: Record<string, unknown> = {
    mode: 'predict',
    observations,
    current: counterflowIdentity(currentRecord),
    policy: {
      eligible_observation_ids: observations.map(observation => observation.id),
      permitted_action_kinds: [action.kind],
      authority: action.required_authority,
      authorization_path: action.authorization_path,
    },
  }
  if (features.failureInhibition) body.failure_inhibition = true
  if (action.stage === 'outcome') {
    body.expected = actionOutcomeIdentity(payload)
    body.observed_outcome = action.outcome
  }
  return {
    body,
    predictive: true,
    hasTrainingData: observations.length > 0,
  }
}

function memoryUpdate(event: MnemicFieldEvent): MnemicMemoryEvent | null {
  const payload = event.payload
  if (
    payload.kind !== 'memory'
    || payload.action
    || payload.operation !== 'update'
    || !payload.previous_record
  ) return null
  if (payload.previous_record.id !== payload.record.id) {
    throw new Error('mnemic-counterflow-update-id-mismatch')
  }
  if (payload.previous_record.revision === payload.record.revision) return null
  return payload
}

function counterflowRequest(
  event: MnemicFieldEvent,
  outbox: MnemicExactStore,
  features: Required<Omit<ContextCounterflowFeatures, 'shadowSupportThreshold'>>,
): CounterflowRequest {
  const action = actionCounterflowRequest(event, outbox, features)
  if (action) return action
  const current = memoryUpdate(event)
  if (!current) {
    return {
      body: NO_COUNTERFLOW_TRANSITION,
      predictive: false,
      hasTrainingData: false,
    }
  }

  const updates = outbox
    .fieldRecordEvents(current.record.id, event.sequence, 16)
    .filter(candidate => memoryUpdate(candidate) !== null)
  const currentIndex = updates.findIndex(candidate => candidate.eventId === event.eventId)
  if (currentIndex < 0) throw new Error('mnemic-counterflow-lineage-missing-current')
  const lineage = [updates[currentIndex]!]
  for (let index = currentIndex - 1; index >= 0 && lineage.length < 7; index--) {
    const previous = memoryUpdate(updates[index]!)!
    const next = memoryUpdate(lineage[0]!)!
    if (
      previous.record.id !== next.previous_record!.id
      || previous.record.revision !== next.previous_record!.revision
    ) break
    lineage.unshift(updates[index]!)
  }

  const heldOut = memoryUpdate(lineage.at(-1)!)!
  const roleEvents = features.lineageRoleAbstraction
    ? outbox.fieldSemanticUpdateEvents(current.record.node_type, event.sequence, 32)
    : []
  const seen = new Set<string>()
  const trainingEvents = [...roleEvents, ...lineage.slice(0, -1)]
    .filter(candidate => candidate.eventId !== event.eventId && !seen.has(candidate.eventId) && seen.add(candidate.eventId))
    .slice(-16)
  const observations = trainingEvents.map(trainingEvent => {
    const transition = memoryUpdate(trainingEvent)!
    return {
      id: trainingEvent.eventId,
      before: counterflowIdentity(transition.previous_record!),
      after: counterflowIdentity(transition.record),
      symbol: 'mnemic:update',
    }
  })
  const before = counterflowIdentity(heldOut.previous_record!)
  const after = counterflowIdentity(heldOut.record)
  if (before.address === after.address) {
    throw new Error('mnemic-counterflow-address-collision')
  }
  return {
    predictive: true,
    hasTrainingData: observations.length > 0,
    body: {
      mode: 'predict',
      observations,
      current: before,
      expected: after,
      policy: {
        eligible_observation_ids: observations.map(observation => observation.id),
        permitted_action_kinds: [],
        authority: 1,
        authorization_path: features.lineageRoleAbstraction
          ? ['mnemic:exact-journal', 'mnemic:semantic-lineage-role']
          : ['mnemic:exact-journal', 'mnemic:continuous-lineage'],
      },
    },
  }
}

function counterflowObservedCommit(event: MnemicFieldEvent): Record<string, unknown> | null {
  const payload = event.payload
  if (payload.kind !== 'memory') return null

  let observation: Record<string, unknown>
  let status: 'committed' | 'completed' | 'error'
  let authorizationPath: readonly string[]
  if (payload.action?.stage === 'outcome') {
    if (!payload.previous_record) {
      throw new Error('mnemic-counterflow-action-outcome-missing-before')
    }
    const action = payload.action
    if (action.outcome !== 'completed' && action.outcome !== 'error') {
      throw new Error('mnemic-counterflow-action-outcome-invalid')
    }
    observation = {
      id: event.eventId,
      before: counterflowIdentity(payload.previous_record),
      after: actionOutcomeIdentity(payload),
      symbol: action.kind,
      outcome: action.outcome,
      action: {
        id: action.action_id,
        kind: action.kind,
        required_authority: action.required_authority,
        reversible: action.reversible,
        effects: action.effects ?? [],
      },
    }
    status = action.outcome
    authorizationPath = action.authorization_path
  } else {
    const update = memoryUpdate(event)
    if (!update) return null
    observation = {
      id: event.eventId,
      before: counterflowIdentity(update.previous_record!),
      after: counterflowIdentity(update.record),
      symbol: 'mnemic:update',
    }
    status = 'committed'
    authorizationPath = ['mnemic:exact-journal']
  }

  const before = observation.before as Record<string, unknown>
  const after = observation.after as Record<string, unknown>
  return {
    user: SHARED_CONTEXT_FIELD_SESSION,
    observation,
    acknowledgment: {
      stream_id: event.streamId,
      sequence: event.sequence,
      event_id: event.eventId,
      status,
      before_revision: before.revision,
      after_revision: after.revision,
      authorization_path: authorizationPath,
    },
  }
}

function validateCounterflowCommitReceipt(
  receipt: Record<string, unknown>,
  event: MnemicFieldEvent,
): void {
  if (
    receipt.schema !== 'cassi.counterflow.observed-commit-receipt.v1'
    || receipt.session_id !== SHARED_CONTEXT_FIELD_SESSION
    || receipt.stream_id !== event.streamId
    || receipt.sequence !== event.sequence
    || receipt.event_id !== event.eventId
    || (receipt.status !== 'committed'
      && receipt.status !== 'completed'
      && receipt.status !== 'error'
      && receipt.status !== 'duplicate')
    || typeof receipt.state_sha256 !== 'string'
    || !/^[0-9a-f]{64}$/.test(receipt.state_sha256)
    || typeof receipt.counterflow_state_out_sha256 !== 'string'
    || !/^[0-9a-f]{64}$/.test(receipt.counterflow_state_out_sha256)
  ) throw new Error('field-counterflow-invalid-commit-response')
}


function validateCounterflowReceipt(
  receipt: Record<string, unknown>,
  request: CounterflowRequest,
): void {
  const status = receipt.status
  const validStatus = !request.predictive || !request.hasTrainingData
    ? status === 'no_transition_data'
    : status === 'predicted'
      || status === 'ambiguous'
      || status === 'no_eligible_transition_data'
  if (
    receipt.schema !== 'cassi.counterflow.derived-runtime.v2'
    || receipt.schema_version !== 2
    || !validStatus
    || receipt.mode !== (request.predictive ? 'predict' : 'plan')
    || receipt.derived !== true
    || receipt.persistent_state !== false
    || receipt.session_id !== SHARED_CONTEXT_FIELD_SESSION
    || typeof receipt.state_sha256 !== 'string'
    || !/^[0-9a-f]{64}$/.test(receipt.state_sha256)
    || receipt.primary_field_sha256 !== receipt.state_sha256
    || typeof receipt.counterflow_state_sha256 !== 'string'
    || !/^[0-9a-f]{64}$/.test(receipt.counterflow_state_sha256)
    || (request.hasTrainingData && receipt.inference_memory_frozen !== true)
  ) throw new Error('field-counterflow-invalid-response')
}

interface MutableCounterflowBucket {
  evaluated: number
  predicted: number
  improved: number
  proposals: number
}

function counterflowBucket(support: number | null): string {
  if (support === null) return 'none'
  if (support < 1) return '0'
  if (support < 2) return '1'
  if (support < 4) return '2-3'
  if (support < 8) return '4-7'
  return '8+'
}

function snapshotCounterflowBucket(bucket: MutableCounterflowBucket): ContextCounterflowBucket {
  return {
    ...bucket,
    precision: bucket.predicted > 0 ? bucket.improved / bucket.predicted : null,
    coverage: bucket.evaluated > 0 ? bucket.predicted / bucket.evaluated : null,
  }
}

function classifyFieldFailure(error: unknown): ContextFieldFailureCode {
  if (error instanceof ContextFieldClientError) return error.code
  const message = String(error).toLowerCase()
  if (message.includes('authority')) return 'authority'
  if (message.includes('event_id') || message.includes('event id') || message.includes('sha256') || message.includes('hash')) {
    return 'journal-hash'
  }
  if (message.includes('journal') || message.includes('divergence') || message.includes('conflict') || message.includes('gap')) {
    return 'journal-conflict'
  }
  if (message.includes('timeout')) return 'provider-timeout'
  if (message.includes('fetch') || message.includes('socket') || message.includes('econn')) return 'provider-unavailable'
  if (message.includes('invalid')) return 'invalid-response'
  return 'provider-http'
}

function classifyFieldHttpFailure(statusCode: number, body: string): ContextFieldFailureCode {
  const detail = body.toLowerCase()
  if (detail.includes('authority')) return 'authority'
  if (detail.includes('event_id') || detail.includes('event id') || detail.includes('sha256') || detail.includes('hash')) {
    return 'journal-hash'
  }
  if (statusCode === 409 || detail.includes('journal') || detail.includes('divergence') || detail.includes('conflict')) {
    return 'journal-conflict'
  }
  return 'provider-http'
}


/** Loopback field client backed by the exact SQLite transition journal. */
export function createHttpContextFieldClient(
  baseUrl: string,
  outbox: MnemicExactStore,
  logger?: ILogger,
  options: ContextFieldClientOptions = {},
): ContextFieldClient {
  const features = {
    failureInhibition: options.failureInhibition === true,
    actionRoleAbstraction: options.actionRoleAbstraction === true,
    lineageRoleAbstraction: options.lineageRoleAbstraction === true,
    multiActionTrajectories: options.multiActionTrajectories === true,
  }
  const shadowSupportThreshold = typeof options.shadowSupportThreshold === 'number'
    && Number.isFinite(options.shadowSupportThreshold)
    && options.shadowSupportThreshold >= 0
    ? options.shadowSupportThreshold
    : null
  const receiptCounts: Record<string, number> = {}
  const failures: Record<ContextFieldFailureCode, number> = {
    'action-error': 0,
    authority: 0,
    'invalid-response': 0,
    'journal-conflict': 0,
    'journal-hash': 0,
    'provider-http': 0,
    'provider-timeout': 0,
    'provider-unavailable': 0,
  }
  const supportBuckets: Record<string, MutableCounterflowBucket> = {
    none: { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
    '0': { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
    '1': { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
    '2-3': { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
    '4-7': { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
    '8+': { evaluated: 0, predicted: 0, improved: 0, proposals: 0 },
  }
  const shadowMetrics: MutableCounterflowBucket = {
    evaluated: 0,
    predicted: 0,
    improved: 0,
    proposals: 0,
  }
  let predictionResidualCount = 0
  let identityResidualCount = 0
  let predictionResidualTotal = 0
  let identityResidualTotal = 0
  let predictionResidualLast: number | null = null
  let identityResidualLast: number | null = null
  let evaluated = 0
  let improved = 0
  let proposalCount = 0
  let proposalSupportTotal = 0
  let proposalSupportCount = 0
  let proposalSupportLast: number | null = null
  let proposalMarginTotal = 0
  let proposalMarginCount = 0
  let proposalMarginLast: number | null = null
  let latencyTotal = 0
  let latencyCount = 0
  let latencyLast: number | null = null
  let latencyMax: number | null = null
  let lastAbstention: { code: string; evidence: Record<string, unknown> } | null = null
  const recallEndpoint = new URL('/v1/context/recall', baseUrl)
  const observeEndpoint = new URL('/v1/context/observe', baseUrl)
  const statusEndpoint = new URL('/v1/context/status', baseUrl)
  const resetEndpoint = new URL('/v1/context/reset', baseUrl)
  const counterflowEndpoint = new URL('/v1/counterflow/plan', baseUrl)
  const counterflowCommitEndpoint = new URL('/v1/counterflow/commit', baseUrl)
  for (const endpoint of [
    recallEndpoint,
    observeEndpoint,
    statusEndpoint,
    resetEndpoint,
    counterflowEndpoint,
    counterflowCommitEndpoint,
  ]) {
    if (
      endpoint.protocol !== 'http:'
      || !['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname)
    ) throw new Error('field context client must use loopback HTTP')
  }

  const postJson = async (
    endpoint: URL,
    body: Record<string, unknown>,
    timeoutMs = 10_000,
  ): Promise<Record<string, unknown>> => {
    let response: Response
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ user: SHARED_CONTEXT_FIELD_SESSION, ...body }),
        signal: AbortSignal.timeout(timeoutMs),
      })
    } catch (error) {
      const timeout = error instanceof Error
        && (error.name === 'TimeoutError' || error.name === 'AbortError')
      throw new ContextFieldClientError(
        timeout ? 'provider-timeout' : 'provider-unavailable',
        `field-context-${timeout ? 'timeout' : 'unavailable'}-${endpoint.pathname}`,
        { cause: error },
      )
    }
    const text = await response.text()
    if (!response.ok) {
      throw new ContextFieldClientError(
        classifyFieldHttpFailure(response.status, text),
        `field-context-http-${response.status}-${endpoint.pathname}: ${text.slice(0, 256)}`,
        { statusCode: response.status },
      )
    }
    let value: unknown
    try {
      value = JSON.parse(text)
    } catch (error) {
      throw new ContextFieldClientError(
        'invalid-response',
        `field-context-invalid-json-${endpoint.pathname}`,
        { cause: error },
      )
    }
    if (!value || typeof value !== 'object') {
      throw new ContextFieldClientError(
        'invalid-response',
        `field-context-invalid-response-${endpoint.pathname}`,
      )
    }
    return value as Record<string, unknown>
  }

  const countedFailures = new WeakSet<object>()
  const recordFailure = (error: unknown): void => {
    if (error !== null && typeof error === 'object') {
      if (countedFailures.has(error)) return
      countedFailures.add(error)
    }
    failures[classifyFieldFailure(error)]++
  }

  const recordCounterflowReceipt = (
    receipt: Record<string, unknown>,
    request: CounterflowRequest,
    elapsedMs: number,
  ): void => {
    const status = typeof receipt.status === 'string' ? receipt.status : 'invalid'
    receiptCounts[status] = (receiptCounts[status] ?? 0) + 1
    latencyCount++
    latencyTotal += elapsedMs
    latencyLast = elapsedMs
    latencyMax = Math.max(latencyMax ?? 0, elapsedMs)

    const prediction = receipt.prediction && typeof receipt.prediction === 'object'
      ? receipt.prediction as Record<string, unknown>
      : null
    const evaluation = receipt.evaluation && typeof receipt.evaluation === 'object'
      ? receipt.evaluation as Record<string, unknown>
      : null
    const support = typeof prediction?.support === 'number' && Number.isFinite(prediction.support)
      ? prediction.support
      : null
    const margin = typeof prediction?.margin === 'number' && Number.isFinite(prediction.margin)
      ? prediction.margin
      : null
    const proposal = receipt.action_proposal !== null
      && typeof receipt.action_proposal === 'object'
    const predicted = status === 'predicted'
    const improvedReceipt = evaluation?.improved_over_identity === true
    const bucket = supportBuckets[counterflowBucket(support)]!

    if (evaluation) {
      evaluated++
      bucket.evaluated++
      if (predicted) bucket.predicted++
      if (improvedReceipt) {
        improved++
        bucket.improved++
      }
      if (shadowSupportThreshold !== null && support !== null && support >= shadowSupportThreshold) {
        shadowMetrics.evaluated++
        if (predicted) shadowMetrics.predicted++
        if (improvedReceipt) shadowMetrics.improved++
      }
      const predictionResidual = evaluation.prediction_residual
      if (typeof predictionResidual === 'number' && Number.isFinite(predictionResidual)) {
        predictionResidualLast = predictionResidual
        predictionResidualTotal += predictionResidual
        predictionResidualCount++
      }
      const identityResidual = evaluation.identity_baseline_residual
      if (typeof identityResidual === 'number' && Number.isFinite(identityResidual)) {
        identityResidualLast = identityResidual
        identityResidualTotal += identityResidual
        identityResidualCount++
      }
    }
    if (proposal) {
      proposalCount++
      bucket.proposals++
      if (shadowSupportThreshold !== null && support !== null && support >= shadowSupportThreshold) {
        shadowMetrics.proposals++
      }
      if (support !== null) {
        proposalSupportLast = support
        proposalSupportTotal += support
        proposalSupportCount++
      }
      if (margin !== null) {
        proposalMarginLast = margin
        proposalMarginTotal += margin
        proposalMarginCount++
      }
    }
    if (request.body.observed_outcome === 'error') failures['action-error']++

    const abstention = receipt.abstention
    if (
      abstention
      && typeof abstention === 'object'
      && 'code' in abstention
      && typeof abstention.code === 'string'
    ) {
      const rawEvidence = 'evidence' in abstention ? abstention.evidence : null
      lastAbstention = {
        code: abstention.code,
        evidence: rawEvidence && typeof rawEvidence === 'object'
          ? rawEvidence as Record<string, unknown>
          : {},
      }
    }
  }

  const planCounterflowEvent = async (event: MnemicFieldEvent): Promise<void> => {
    const request = counterflowRequest(event, outbox, features)
    const startedAt = performance.now()
    const receipt = await postJson(counterflowEndpoint, request.body)
    try {
      validateCounterflowReceipt(receipt, request)
    } catch (error) {
      throw new ContextFieldClientError(
        'invalid-response',
        'field-counterflow-invalid-response',
        { cause: error },
      )
    }
    recordCounterflowReceipt(receipt, request, performance.now() - startedAt)
    logger?.debug('CassiFI counterflow plan evaluated', {
      sequence: event.sequence,
      status: receipt.status,
      stateSha256: receipt.state_sha256,
      counterflowStateSha256: receipt.counterflow_state_sha256,
    })
  }

  const commitCounterflowEvent = async (event: MnemicFieldEvent): Promise<void> => {
    const request = counterflowObservedCommit(event)
    if (!request) return
    const receipt = await postJson(counterflowCommitEndpoint, request)
    try {
      validateCounterflowCommitReceipt(receipt, event)
    } catch (error) {
      throw new ContextFieldClientError(
        'invalid-response',
        'field-counterflow-invalid-commit-response',
        { cause: error },
      )
    }
    logger?.debug('CassiFI observed counterflow transition committed', {
      sequence: event.sequence,
      status: receipt.status,
      stateSha256: receipt.state_sha256,
      counterflowStateSha256: receipt.counterflow_state_out_sha256,
    })
  }

  let accepting = true
  let dirty = false
  let draining: Promise<void> | null = null

  const syncOnce = async (): Promise<void> => {
    const local = outbox.fieldStreamStatus()
    let status = await postJson(statusEndpoint, { stream_id: local.streamId })
    const checkpoint = status.checkpoint
    if (!checkpoint || typeof checkpoint !== 'object' || !('status' in checkpoint)) {
      throw new Error('field-context-status-missing-checkpoint')
    }
    const checkpointRecord = checkpoint as Record<string, unknown>
    const checkpointStatus = checkpointRecord.status
    if (checkpointStatus === 'incompatible') {
      status = await postJson(resetEndpoint, {
        stream_id: local.streamId,
        checkpoint_sha256: checkpointRecord.sha256,
        checkpoint_engine_fingerprint: checkpointRecord.engine_fingerprint,
      })
    } else if (checkpointStatus !== 'compatible' && checkpointStatus !== 'missing') {
      throw new Error('field-context-status-invalid-checkpoint')
    }

    const remote = status.stream
    if (
      !remote
      || typeof remote !== 'object'
      || !('stream_id' in remote)
      || remote.stream_id !== local.streamId
      || !('sequence' in remote)
      || typeof remote.sequence !== 'number'
      || !Number.isInteger(remote.sequence)
      || remote.sequence < 0
      || !('event_id' in remote)
      || typeof remote.event_id !== 'string'
    ) throw new Error('field-context-status-invalid-stream')
    if (remote.sequence > local.headSequence) {
      throw new Error('field-context-provider-ahead-of-exact-journal')
    }
    if (remote.sequence > local.acknowledgedSequence) {
      let recoveredSequence = local.acknowledgedSequence
      while (recoveredSequence < remote.sequence) {
        const events = outbox.fieldEventsAfter(recoveredSequence)
        if (events.length === 0 || events[0]?.sequence !== recoveredSequence + 1) {
          throw new Error('field-counterflow-journal-gap')
        }
        for (const event of events) {
          if (event.sequence > remote.sequence) break
          await commitCounterflowEvent(event)
          recoveredSequence = event.sequence
        }
      }
      outbox.acknowledgeFieldEventsThrough(remote.sequence, remote.event_id)
    }

    let cursor = remote.sequence
    for (;;) {
      const events = outbox.fieldEventsAfter(cursor)
      if (events.length === 0) break
      for (const event of events) {
        await planCounterflowEvent(event)
        const response = await postJson(observeEndpoint, {
          stream_id: event.streamId,
          sequence: event.sequence,
          previous_event_id: event.previousEventId,
          event_id: event.eventId,
          payload: event.payload,
        })
        const watermark = response.stream
        if (
          !watermark
          || typeof watermark !== 'object'
          || !('sequence' in watermark)
          || watermark.sequence !== event.sequence
          || !('event_id' in watermark)
          || watermark.event_id !== event.eventId
        ) throw new Error(`field-context-invalid-commit-${event.sequence}`)
        await commitCounterflowEvent(event)
        outbox.acknowledgeFieldEventsThrough(event.sequence, event.eventId)
        cursor = event.sequence
      }
    }

  }

  const drain = (): Promise<void> => {
    dirty = true
    if (draining) return draining
    draining = (async () => {
      do {
        dirty = false
        await syncOnce()
      } while (dirty)
    })().catch(error => {
      recordFailure(error)
      throw error
    }).finally(() => { draining = null })
    return draining
  }

  const notify = (): void => {
    if (!accepting) return
    void drain().catch(error => {
      logger?.warn('CassiFI context journal drain failed (non-fatal)', { error: String(error) })
    })
  }

  const recallImpl: ContextFieldRecaller = async request => {
    await drain()
    const addresses = [...new Set(request.addresses)]
    const body = await postJson(recallEndpoint, {
      context_session_id: request.sessionId.slice(0, 256),
      query: truncateUtf8(request.query, FIELD_QUERY_MAX_BYTES),
      addresses,
    }, request.deadlineMs)
    const address = body.address
    if (
      address !== null
      && (
        typeof address !== 'string'
        || !/^[0-9a-f]{32}$/.test(address)
        || !addresses.includes(address)
      )
    ) throw new Error('field-context-recall-invalid-address')
    if (
      typeof body.signal !== 'number'
      || !Number.isFinite(body.signal)
      || typeof body.selection_margin !== 'number'
      || !Number.isFinite(body.selection_margin)
      || typeof body.availability !== 'number'
      || !Number.isFinite(body.availability)
    ) throw new Error('field-context-recall-invalid-response')
    return {
      address,
      signal: body.signal,
      selectionMargin: body.selection_margin,
      availability: body.availability,
    }
  }

  const recall: ContextFieldRecaller = async request => {
    try {
      return await recallImpl(request)
    } catch (error) {
      recordFailure(error)
      throw error
    }
  }

  const status = (): ContextCounterflowStatus => ({
    schemaVersion: 1,
    features: { ...features },
    pending: draining !== null || dirty,
    receipts: { ...receiptCounts },
    residuals: {
      evaluated,
      predictionLast: predictionResidualLast,
      predictionMean: predictionResidualCount > 0
        ? predictionResidualTotal / predictionResidualCount
        : null,
      identityLast: identityResidualLast,
      identityMean: identityResidualCount > 0
        ? identityResidualTotal / identityResidualCount
        : null,
      improved,
    },
    proposals: {
      count: proposalCount,
      supportLast: proposalSupportLast,
      supportMean: proposalSupportCount > 0
        ? proposalSupportTotal / proposalSupportCount
        : null,
      marginLast: proposalMarginLast,
      marginMean: proposalMarginCount > 0
        ? proposalMarginTotal / proposalMarginCount
        : null,
    },
    latencyMs: {
      count: latencyCount,
      last: latencyLast,
      mean: latencyCount > 0 ? latencyTotal / latencyCount : null,
      max: latencyMax,
    },
    failures: { ...failures },
    supportBuckets: Object.fromEntries(
      Object.entries(supportBuckets).map(([name, bucket]) => [
        name,
        snapshotCounterflowBucket(bucket),
      ]),
    ),
    shadowThreshold: {
      support: shadowSupportThreshold,
      metrics: snapshotCounterflowBucket(shadowMetrics),
    },
    lastAbstention,
  })

  return {
    recall,
    notify,
    flush: drain,
    status,
    close: async () => {
      accepting = false
      try {
        await drain()
      } catch (error) {
        logger?.warn('CassiFI context journal remains pending at shutdown', { error: String(error) })
      }
    },
  }
}


export interface RuntimeContextCandidateServiceOptions {
  /** Max candidates returned (default 8). */
  maxCandidates?: number
  /** Max UTF-8 bytes per exact candidate span (default 1200). */
  maxCandidateChars?: number
  /** Max chars for the query; longer queries are truncated (default 1000). */
  maxQueryChars?: number
  /** Default request-side deadline when the caller omits `deadlineMs` (default 2500). */
  defaultDeadlineMs?: number
  /** Hard lower bound for caller-supplied `deadlineMs` (default 100). */
  minDeadlineMs?: number
  /** Hard upper bound for caller-supplied `deadlineMs` (default 10_000). */
  maxDeadlineMs?: number
  /** Cached shadow age beyond which a background refresh is re-scheduled (default 10_000). */
  fieldShadowMaxAgeMs?: number
  /** Minimum delay between background 7599 refreshes (default 1_000). */
  fieldShadowMinRefreshIntervalMs?: number
}

/** Observability/status surface (used by tests + diagnostics). */
export interface ContextCandidateServiceStatus {
  cachedFieldShadow: { available: boolean; capturedAt: number | null; ageMs: number | null }
  refreshInFlight: boolean
  lastRefreshAt: number | null
  telemetryEnabled: boolean
  counterflow: ContextCounterflowStatus | null
}

/** Reject a malformed candidate/feedback request with an HTTP-mappable status. */
export class ContextRequestError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message)
    this.name = 'ContextRequestError'
  }
}

const DEFAULT_LIMIT = 5
const MAX_FEEDBACK_IDS = 64

interface ServiceDeps {
  memory: ContextMemorySurface
  bus: IEventBus
  logger: ILogger
  fieldTelemetry?: ContextFieldTelemetrySurface
  fieldRecall?: ContextFieldRecaller
  counterflowStatus?: () => ContextCounterflowStatus
}

type ResolvedOptions = Required<RuntimeContextCandidateServiceOptions>

function resolveOptions(opts: RuntimeContextCandidateServiceOptions = {}): ResolvedOptions {
  return {
    maxCandidates: opts.maxCandidates ?? 8,
    maxCandidateChars: opts.maxCandidateChars ?? 1200,
    maxQueryChars: opts.maxQueryChars ?? 1000,
    defaultDeadlineMs: opts.defaultDeadlineMs ?? 2500,
    minDeadlineMs: opts.minDeadlineMs ?? 100,
    maxDeadlineMs: opts.maxDeadlineMs ?? 10_000,
    fieldShadowMaxAgeMs: opts.fieldShadowMaxAgeMs ?? 10_000,
    fieldShadowMinRefreshIntervalMs: opts.fieldShadowMinRefreshIntervalMs ?? 1_000,
  }
}

/**
 * The runtime's context candidate + feedback handler. Instantiated by boot.ts
 * and exposed as `runtime.context`; the channel server's `/v1/context/*` routes
 * are thin passthroughs.
 */
export class RuntimeContextCandidateService {
  private readonly memory: ContextMemorySurface
  private readonly bus: IEventBus
  private readonly logger: ILogger
  private readonly fieldTelemetry: ContextFieldTelemetrySurface | undefined
  private readonly fieldRecall: ContextFieldRecaller | undefined
  private readonly counterflowStatus: (() => ContextCounterflowStatus) | undefined
  private readonly opts: ResolvedOptions

  private cachedFieldShadow: { advisory: FieldAdvisory; capturedAt: number } | null = null
  private refreshInFlight = false
  private lastRefreshAt = 0
  private closed = false

  constructor(deps: ServiceDeps, opts: RuntimeContextCandidateServiceOptions = {}) {
    this.memory = deps.memory
    this.bus = deps.bus
    this.logger = deps.logger
    this.fieldTelemetry = deps.fieldTelemetry
    this.fieldRecall = deps.fieldRecall
    this.counterflowStatus = deps.counterflowStatus
    this.opts = resolveOptions(opts)
  }

  /**
   * Serve `POST /v1/context/candidates`. Never throws for runtime failures
   * (deadline/search errors fail open to empty candidates); throws
   * `ContextRequestError` (400) only for malformed requests.
   */
  async candidates(req: ContextCandidatesRequest): Promise<ContextCandidatesResponse> {
    const { sessionId, turnId, query, limit, deadlineMs, includeFieldShadow } = validateCandidatesRequest(req, this.opts)
    const started = Date.now()
    const deadline = started + deadlineMs

    // The exact store supplies only opaque addresses. The Qi field is the sole
    // relevance authority and may either select one whole address or abstain.
    let candidates: ContextCandidate[] = []
    let mnemic: ContextSourceStatus
    if (!this.fieldRecall) {
      mnemic = {
        source: 'mnemic',
        status: 'disabled',
        latencyMs: 0,
        error: 'field-native-recall-disabled',
      }
    } else {
      try {
        const addresses = this.memory.fieldAddressManifest(sessionId)
        const fieldResult = await withDeadline(
          () => this.fieldRecall!({
            sessionId,
            query,
            addresses,
            deadlineMs: Math.max(1, deadline - Date.now()),
          }),
          deadline,
        )
        if (fieldResult.address !== null) {
          if (!addresses.includes(fieldResult.address)) {
            throw new Error('field-selected-address-not-in-request-manifest')
          }
          const hit = this.memory.resolveFieldAddress(fieldResult.address)
          if (!hit) throw new Error('field-selected-address-not-in-exact-manifest')
          if (hit.metadata?.sessionId === sessionId) {
            throw new Error('field-selected-address-is-not-session-eligible')
          }
          candidates = toCandidates(
            [hit],
            sessionId,
            this.opts.maxCandidates,
            this.opts.maxCandidateChars,
            query,
            true,
          ).map(candidate => ({
            ...candidate,
            score: fieldResult.signal,
          }))
        }
        mnemic = {
          source: 'mnemic',
          status: 'ready',
          latencyMs: Date.now() - started,
        }
      } catch (err) {
        const timedOut = err instanceof DeadlineExceededError
          || (err instanceof Error && (
            err.name === 'AbortError'
            || err.name === 'TimeoutError'
          ))
        mnemic = {
          source: 'mnemic',
          status: timedOut ? 'timeout' : 'error',
          latencyMs: Date.now() - started,
          error: timedOut
            ? 'field-recall-deadline-exceeded'
            : 'field-recall-failed',
        }
      }
    }
    candidates = candidates.slice(0, limit)
    try {
      this.memory.rememberContextTurn?.(
        sessionId,
        turnId,
        query,
        candidates.map(candidate => ({
          id: candidate.id,
          recordId: candidate.recordId ?? candidate.id,
          startByte: candidate.startByte ?? 0,
          endByte: candidate.endByte ?? Buffer.byteLength(candidate.text),
          text: candidate.text,
          revision: candidate.revision ?? createHash('sha256')
            .update(candidate.id)
            .update('\0')
            .update(candidate.text)
            .digest('hex'),
          fieldAddress: candidate.fieldAddress,
        })),
      )
    } catch (err) {
      this.logger.warn('context feedback eligibility persistence failed (non-fatal)', { error: String(err) })
    }

    // ── Field shadow: cached-only, advisory-only, never blocks on a fresh read ──
    let fieldAdvisory: FieldAdvisory | null = null
    if (includeFieldShadow) {
      const cached = this.cachedFieldAdvisory()
      const stale = this.shadowStale()
      fieldAdvisory = stale ? null : cached
      if (!cached || stale) {
        // First-miss / stale: schedule a background refresh (coalesced). The
        // response never awaits it — 7599 reads happen at most one at a time.
        void this.refreshFieldShadow('candidate-miss')
      }
    }

    const sources: ContextSourceStatus[] = [mnemic]
    if (includeFieldShadow) sources.push(this.fieldShadowStatus())

    this.logger.debug('[context] candidates', {
      sessionId,
      turnId,
      queryLen: query.length,
      candidates: candidates.length,
      ms: Date.now() - started,
    })
    return { candidates, sources, fieldAdvisory }
  }

  /**
   * Serve `POST /v1/context/feedback` — turn-level IDs, plan outcome, and an
   * optional text-free tool outcome. Publishes an observable retained bus
   * event and may refresh the cached field shadow in the background.
   */
  async feedback(req: ContextFeedbackRequest): Promise<ContextFeedbackResponse> {
    const { sessionId, turnId, planId, includedCandidateIds, outcome, toolResult } = validateFeedbackRequest(req)

    try {
      await this.bus.emit({
        type: 'cassi.context.feedback',
        // Global EventBus history is bounded. The bus treats this high-churn
        // observability event as non-session-retained while preserving its
        // public `sessionId` field for subscribers.
        sessionId,
        turnId,
        planId,
        includedCandidateIds,
        outcome,
        ...(toolResult ? { toolResult } : {}),
        timestamp: new Date(),
      } as never)
    } catch (err) {
      // Bus emission is advisory — never fail the ack for a slow/closed bus.
      this.logger.warn('context feedback bus emit failed (non-fatal)', { error: String(err) })
    }
    try {
      this.memory.consumeContextFeedback?.(
        sessionId,
        turnId,
        includedCandidateIds,
        outcome,
        toolResult,
      )
    } catch (err) {
      this.logger.warn('context field feedback journal failed (non-fatal)', { error: String(err) })
    }

    // Feedback may trigger the next cached field refresh (coalesced, background).
    if (!this.cachedFieldShadow || this.shadowStale()) {
      void this.refreshFieldShadow('feedback')
    }

    this.logger.debug('[context] feedback', { sessionId, turnId, planId, included: includedCandidateIds.length, outcome })
    return { ack: true }
  }

  async action(req: ContextActionRequest): Promise<ContextActionResponse> {
    const action = validateActionRequest(req)
    try {
      if (action.operation === 'start') {
        if (!this.memory.startActionEpisode) {
          throw new ContextRequestError(503, 'exact action journal is unavailable')
        }
        this.memory.startActionEpisode({
          contextSessionId: action.sessionId,
          turnId: action.turnId,
          planId: action.planId,
          toolCallId: action.toolCallId,
          toolName: action.toolName,
          argumentsSha256: action.argumentsSha256,
          requiredAuthority: action.requiredAuthority,
          reversible: action.reversible,
        })
      } else {
        if (!this.memory.finishActionEpisode) {
          throw new ContextRequestError(503, 'exact action journal is unavailable')
        }
        this.memory.finishActionEpisode({
          contextSessionId: action.sessionId,
          turnId: action.turnId,
          planId: action.planId,
          toolCallId: action.toolCallId,
          isError: action.isError,
        })
      }
    } catch (error) {
      if (error instanceof ContextRequestError) throw error
      this.logger.warn('exact action journal rejected an episode', { error: String(error) })
      throw new ContextRequestError(409, 'exact action episode conflicts with durable state')
    }
    return { ack: true }
  }

  /** Service status for diagnostics + tests (cache state, refresh in-flight). */
  status(): ContextCandidateServiceStatus {
    const cached = this.cachedFieldShadow
    return {
      cachedFieldShadow: cached
        ? { available: true, capturedAt: cached.capturedAt, ageMs: Date.now() - cached.capturedAt }
        : { available: false, capturedAt: null, ageMs: null },
      refreshInFlight: this.refreshInFlight,
      lastRefreshAt: this.lastRefreshAt || null,
      telemetryEnabled: !!this.fieldTelemetry,
      counterflow: this.counterflowStatus?.() ?? null,
    }
  }

  /** Stop scheduling background 7599 reads (in-flight reads drain naturally). */
  close(): void {
    this.closed = true
  }

  // ── field shadow internals ─────────────────────────────────────────────────

  private cachedFieldAdvisory(): FieldAdvisory | null {
    if (!this.fieldTelemetry || this.closed) return null
    return this.cachedFieldShadow?.advisory ?? null
  }

  private shadowStale(): boolean {
    const cached = this.cachedFieldShadow
    if (!cached) return true
    return Date.now() - cached.capturedAt >= this.opts.fieldShadowMaxAgeMs
  }

  /**
   * One background 7599 read at a time (single-flight + interval throttle).
   * Summarizes the snapshot and drops the grid arrays immediately; offline or
   * failed reads leave the cache untouched and never throw.
   */
  private async refreshFieldShadow(reason: string): Promise<void> {
    if (!this.fieldTelemetry || this.closed) return
    if (this.refreshInFlight) return
    const now = Date.now()
    if (now - this.lastRefreshAt < this.opts.fieldShadowMinRefreshIntervalMs) return
    this.refreshInFlight = true
    this.lastRefreshAt = now
    try {
      const snapshot = await this.fieldTelemetry.read()
      if (snapshot) {
        const capturedAt = Date.now()
        // Copy ONLY the bounded scalar summaries — the grid arrays
        // (ey/ei/fieldPower/eps2) are discarded as soon as `snapshot` drops
        // out of scope and are never retained by the service.
        this.cachedFieldShadow = { advisory: summarizeFieldSnapshot(snapshot, capturedAt), capturedAt }
      }
      // snapshot === null (offline/malformed reply): keep whatever cache exists;
      // on a cold start the shadow simply stays absent — neutral, never fatal.
    } catch (err) {
      this.logger.warn('field shadow refresh failed (non-fatal)', { error: String(err), reason })
    } finally {
      this.refreshInFlight = false
    }
  }

  private fieldShadowStatus(): ContextSourceStatus {
    if (!this.fieldTelemetry) {
      return { source: 'field', status: 'disabled', error: 'field telemetry not enabled' }
    }
    const cached = this.cachedFieldShadow
    if (cached && !this.shadowStale()) {
      return { source: 'field', status: 'ready', latencyMs: Date.now() - cached.capturedAt }
    }
    if (cached) {
      return { source: 'field', status: 'offline', latencyMs: Date.now() - cached.capturedAt, error: 'cached field shadow is stale' }
    }
    const st = this.fieldTelemetry.status()
    if (st.connected && st.lastError) return { source: 'field', status: 'error', latencyMs: 0, error: st.lastError }
    return { source: 'field', status: 'offline', latencyMs: 0, error: st.connected ? 'no cached shadow yet' : 'offline' }
  }
}


// ── validation ────────────────────────────────────────────────────────────────

interface ValidatedCandidatesRequest {
  sessionId: string
  turnId: number
  query: string
  limit: number
  deadlineMs: number
  includeFieldShadow: boolean
}

function validateCandidatesRequest(req: ContextCandidatesRequest, opts: ResolvedOptions): ValidatedCandidatesRequest {
  if (!req || typeof req !== 'object') throw new ContextRequestError(400, 'request body must be an object')
  const { sessionId, turnId, query, limit, deadlineMs, includeFieldShadow } = req
  if (!isBoundedOpaque(sessionId)) throw new ContextRequestError(400, 'sessionId must be a bounded opaque ID')
  if (typeof turnId !== 'number' || !Number.isInteger(turnId) || turnId < 0) {
    throw new ContextRequestError(400, 'turnId must be a non-negative integer')
  }
  if (typeof query !== 'string' || !query.trim()) throw new ContextRequestError(400, 'query is required')
  if (includeFieldShadow !== undefined && typeof includeFieldShadow !== 'boolean') {
    throw new ContextRequestError(400, 'includeFieldShadow must be a boolean')
  }
  const q = query.length > opts.maxQueryChars ? query.slice(0, opts.maxQueryChars) : query
  const lim = limit === undefined ? DEFAULT_LIMIT : limitInt(limit, opts.maxCandidates)
  const deadline = deadlineMs === undefined ? opts.defaultDeadlineMs : clampInt(deadlineMs, opts.minDeadlineMs, opts.maxDeadlineMs, 'deadlineMs')
  return { sessionId, turnId, query: q, limit: lim, deadlineMs: deadline, includeFieldShadow: includeFieldShadow ?? false }
}

function validateFeedbackRequest(req: ContextFeedbackRequest): {
  sessionId: string
  turnId: number
  planId: string
  includedCandidateIds: string[]
  outcome: ContextFeedbackOutcome
  toolResult?: ContextFeedbackToolResult
} {
  if (!req || typeof req !== 'object') throw new ContextRequestError(400, 'request body must be an object')
  const { sessionId, turnId, planId, includedCandidateIds, outcome, toolResult } = req
  if (!isBoundedOpaque(sessionId)) throw new ContextRequestError(400, 'sessionId must be a bounded opaque ID')
  if (typeof turnId !== 'number' || !Number.isInteger(turnId) || turnId < 0) {
    throw new ContextRequestError(400, 'turnId must be a non-negative integer')
  }
  if (!isBoundedOpaque(planId)) throw new ContextRequestError(400, 'planId must be a bounded opaque ID')
  if (!Array.isArray(includedCandidateIds)) {
    throw new ContextRequestError(400, 'includedCandidateIds must be an array')
  }
  if (includedCandidateIds.length > MAX_FEEDBACK_IDS) {
    throw new ContextRequestError(400, `includedCandidateIds must contain at most ${MAX_FEEDBACK_IDS} IDs`)
  }
  if (includedCandidateIds.some(id => !isBoundedOpaque(id))) {
    throw new ContextRequestError(400, 'includedCandidateIds must contain bounded opaque IDs')
  }
  if (outcome !== 'completed' && outcome !== 'error' && outcome !== 'unknown' && outcome !== 'cancelled') {
    throw new ContextRequestError(400, 'outcome must be completed | error | unknown | cancelled')
  }
  if (toolResult !== undefined) {
    if (
      !toolResult
      || typeof toolResult !== 'object'
      || Object.keys(toolResult).sort().join(',') !== 'id,isError,name'
      || !isBoundedOpaque(toolResult.id)
      || !isBoundedOpaque(toolResult.name)
      || typeof toolResult.isError !== 'boolean'
      || (outcome !== 'completed' && outcome !== 'error')
      || toolResult.isError !== (outcome === 'error')
    ) throw new ContextRequestError(400, 'toolResult must be a bounded text-free outcome consistent with outcome')
  }
  return {
    sessionId,
    turnId,
    planId,
    includedCandidateIds,
    outcome,
    ...(toolResult ? { toolResult } : {}),
  }
}

function validateActionRequest(req: ContextActionRequest): ContextActionRequest {
  if (!req || typeof req !== 'object') {
    throw new ContextRequestError(400, 'request body must be an object')
  }
  const { operation, sessionId, turnId, planId, toolCallId } = req
  if (operation !== 'start' && operation !== 'outcome') {
    throw new ContextRequestError(400, 'operation must be start or outcome')
  }
  if (
    !isBoundedOpaque(sessionId)
    || !Number.isInteger(turnId)
    || turnId < 0
    || !isBoundedOpaque(planId)
    || !isBoundedOpaque(toolCallId)
  ) throw new ContextRequestError(400, 'action provenance is invalid')
  if (operation === 'start') {
    if (
      !isBoundedOpaque(req.toolName)
      || !/^[0-9a-f]{64}$/.test(req.argumentsSha256)
      || typeof req.requiredAuthority !== 'number'
      || !Number.isFinite(req.requiredAuthority)
      || req.requiredAuthority < 0
      || req.requiredAuthority > 1
      || typeof req.reversible !== 'boolean'
    ) throw new ContextRequestError(400, 'action start is invalid')
  } else if (typeof req.isError !== 'boolean') {
    throw new ContextRequestError(400, 'action outcome is invalid')
  }
  return req
}

function isBoundedOpaque(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._:-]{1,128}$/.test(value)
}

function clampInt(value: unknown, min: number, max: number, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ContextRequestError(400, `${label} must be a number`)
  }
  return Math.min(max, Math.max(min, Math.round(value)))
}

/** Validate a caller-supplied `limit`: must be a finite number ≥ 1; oversized values clamp to the cap. */
function limitInt(value: unknown, max: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ContextRequestError(400, 'limit must be a number')
  }
  const rounded = Math.round(value)
  if (rounded < 1) throw new ContextRequestError(400, 'limit must be >= 1')
  return Math.min(max, rounded)
}

// ── mapping / bounding ────────────────────────────────────────────────────────

interface ExactSpan {
  text: string
  startByte: number
  endByte: number
}

function exactUtf8Spans(text: string, maxBytes: number): ExactSpan[] {
  const bytes = Buffer.from(text)
  const spans: ExactSpan[] = []
  const limit = Math.max(4, maxBytes)
  for (let start = 0; start < bytes.length;) {
    let end = Math.min(bytes.length, start + limit)
    while (end < bytes.length && end > start && (bytes[end]! & 0xc0) === 0x80) end -= 1
    if (end === start) {
      end = Math.min(bytes.length, start + limit)
      while (end < bytes.length && (bytes[end]! & 0xc0) === 0x80) end += 1
    }
    if (end < bytes.length) {
      const newline = bytes.lastIndexOf(0x0a, end - 1)
      if (newline >= start + Math.floor((end - start) / 2)) end = newline + 1
    }
    spans.push({
      text: bytes.subarray(start, end).toString('utf8'),
      startByte: start,
      endByte: end,
    })
    start = end
  }
  return spans
}

function spanTermScore(text: string, terms: readonly string[]): number {
  const normalized = text.normalize('NFKC').toLocaleLowerCase()
  return terms.reduce((score, term) => score + (normalized.includes(term) ? 1 : 0), 0)
}

/** Map exact Mnemic hits to revision-bound UTF-8 spans. */
function toCandidates(
  hits: MemoryHitView[],
  sessionId: string,
  limit: number,
  maxCandidateBytes: number,
  query: string,
  excludeCurrentSession = true,
): ContextCandidate[] {
  const terms = [...new Set(
    (query.normalize('NFKC').toLocaleLowerCase().match(/[\p{L}\p{N}_-]+/gu) ?? []).slice(0, 12),
  )]
  const groups: ContextCandidate[][] = []
  for (const hit of hits) {
    const meta = hit.metadata
    const hitSession = meta && typeof meta.sessionId === 'string' ? meta.sessionId : undefined
    if (excludeCurrentSession && hitSession === sessionId) continue
    const text = hit.content ?? ''
    const recordId = safeOpaqueId(hit.id)
    const revision = hit.revision ?? createHash('sha256')
      .update(hit.id)
      .update('\0')
      .update(hit.nodeType ?? '')
      .update('\0')
      .update(text)
      .digest('hex')
    const exactSpans = exactUtf8Spans(text, maxCandidateBytes)
    const multipleSpans = exactSpans.length > 1
    const spans = exactSpans
      .map((span, position) => ({ span, position, termScore: spanTermScore(span.text, terms) }))
      .sort((a, b) => b.termScore - a.termScore || a.position - b.position)
      .map(({ span }) => ({
        id: multipleSpans
          ? `span:${createHash('sha256')
            .update(recordId)
            .update('\0')
            .update(revision)
            .update('\0')
            .update(String(span.startByte))
            .update(':')
            .update(String(span.endByte))
            .digest('hex')
            .slice(0, 32)}`
          : recordId,
        recordId,
        revision,
        startByte: span.startByte,
        endByte: span.endByte,
        fieldAddress: hit.fieldAddress,
        source: 'mnemic' as const,
        text: span.text,
        score: hit.score,
        sourceRefs: [recordId],
        metadata: {
          ...(hit.nodeType ? { nodeType: hit.nodeType.slice(0, 64) } : {}),
          exactSpan: true,
        },
      }))
    if (spans.length > 0) groups.push(spans)
  }

  const out: ContextCandidate[] = []
  for (let position = 0; out.length < limit; position += 1) {
    let found = false
    for (const group of groups) {
      const candidate = group[position]
      if (!candidate) continue
      out.push(candidate)
      found = true
      if (out.length >= limit) break
    }
    if (!found) break
  }
  return out
}

function safeOpaqueId(value: string): string {
  if (/^[A-Za-z0-9._:-]{1,128}$/.test(value)) return value
  return `sha256:${createHash('sha256').update(value).digest('hex').slice(0, 32)}`
}

/** Copy ONLY the bounded scalar summaries out of a field snapshot. */
function summarizeFieldSnapshot(snapshot: FieldTelemetrySnapshot, observedAt: number): FieldAdvisory {
  const balance = snapshot.balance
    ? {
        meanRho: snapshot.balance.meanRho,
        meanEpsilon: snapshot.balance.meanEpsilon,
        meanFieldPower: snapshot.balance.meanFieldPower,
        meanCoherence: snapshot.balance.meanCoherence,
      }
    : undefined
  const temporal = snapshot.thetaTemporalResultant
    ? {
        resultant: snapshot.thetaTemporalResultant.resultant,
        weightedMeanAbsoluteIncrement: snapshot.thetaTemporalResultant.weightedMeanAbsoluteIncrement,
        samples: snapshot.thetaTemporalResultant.samples,
      }
    : undefined
  const jProxy = snapshot.jProxy ? { rms: snapshot.jProxy.rms, samples: snapshot.jProxy.samples } : undefined
  const helical = snapshot.helicalScan
    ? {
        canonicalSpiral: false as const,
        bestValue: snapshot.helicalScan.bestValue,
        bestAxis: snapshot.helicalScan.bestAxis,
        bestMode: snapshot.helicalScan.bestMode,
        modeZero: snapshot.helicalScan.modeZero,
        samples: snapshot.helicalScan.samples,
      }
    : undefined
  return {
    mode: 'shadow',
    observedAt,
    step: snapshot.step ?? null,
    time: snapshot.time ?? null,
    balance,
    temporal,
    jProxy,
    helical,
  }
}

// ── deadline helper ───────────────────────────────────────────────────────────

class DeadlineExceededError extends Error {
  constructor() {
    super('deadline exceeded')
    this.name = 'DeadlineExceededError'
  }
}

/** Start the operation only after arming a hard wall-clock deadline. */
async function withDeadline<T>(operation: () => Promise<T>, deadline: number): Promise<T> {
  const controller = new AbortController()
  const timeout = delay(Math.max(0, deadline - Date.now()), undefined, { signal: controller.signal })
    .then(() => { throw new DeadlineExceededError() })
  try {
    return await Promise.race([operation(), timeout])
  } finally {
    controller.abort()
  }
}
