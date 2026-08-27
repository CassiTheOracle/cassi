/**
 * @cassicore/mind-runtime — context candidate service (P8 shared context seam).
 *
 * Backs `POST /v1/context/candidates` + `POST /v1/context/feedback`. The spine
 * asks the runtime for typed Mnemic context candidates for a turn and reports
 * which candidate IDs the plan accepted/rejected.
 *
 * Hard guarantees:
 * - Bounded + validated request fields (malformed → `ContextRequestError` 400).
 * - Mnemic lookup uses the adapter's strict, read-only FTS path. A provider-bound
 *   prompt is never persisted as retrieval telemetry or broadcast/activation state,
 *   and backend failures remain observable as source errors.
 * - Results are post-filtered to exclude the requesting session.
 * - Hard request-side deadline: the search races the deadline and FAILS OPEN —
 *   a timeout returns 200 with empty candidates + `sources[].status === 'timeout'`,
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
import type { MemoryHitView } from '../memory/backend.js'
import type { FieldTelemetrySnapshot, FieldTelemetryStatus } from '../field/telemetry.js'
import type {
  ContextCandidate,
  ContextCandidatesRequest,
  ContextCandidatesResponse,
  ContextFeedbackOutcome,
  ContextFeedbackRequest,
  ContextFeedbackResponse,
  ContextSourceStatus,
  FieldAdvisory,
} from '../channel/protocol.js'

/** The narrow, non-persisting memory surface the service needs (satisfied by `MnemicMemoryAdapter`). */
export interface ContextMemorySurface {
  searchReadOnly(
    query: string,
    opts?: { limit?: number; type?: string; sessionId?: string; deadlineMs?: number },
  ): Promise<MemoryHitView[]>
}

/** The narrow field-telemetry surface (satisfied by `MindFieldTelemetry`). */
export interface ContextFieldTelemetrySurface {
  read(): Promise<FieldTelemetrySnapshot | null>
  status(): FieldTelemetryStatus
}

export interface RuntimeContextCandidateServiceOptions {
  /** Max candidates returned (default 8). */
  maxCandidates?: number
  /** Max chars per candidate content; longer content is truncated (default 1200). */
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

    // ── Mnemic source: bounded, validated, hard request-side deadline ──────
    let candidates: ContextCandidate[] = []
    let mnemic: ContextSourceStatus = { source: 'mnemic', status: 'ready', latencyMs: 0 }
    try {
      // Fetch a little slack so the same-session post-filter can't starve the cap.
      // This strict path must propagate backend failures and must never record the
      // raw provider-bound query as Mnemic retrieval telemetry.
      const raw = await withDeadline(
        () => this.memory.searchReadOnly(query, {
          limit: Math.min(limit * 2, this.opts.maxCandidates * 2),
          sessionId,
          deadlineMs: Math.max(1, deadline - Date.now()),
        }),
        deadline,
      )
      candidates = toCandidates(raw, sessionId, limit, this.opts.maxCandidateChars)
      mnemic = { source: 'mnemic', status: 'ready', latencyMs: Date.now() - started }
    } catch (err) {
      const timedOut = err instanceof DeadlineExceededError || (err instanceof Error && err.name === 'AbortError')
      mnemic = {
        source: 'mnemic',
        status: timedOut ? 'timeout' : 'error',
        latencyMs: Date.now() - started,
        error: timedOut ? 'mnemic-deadline-exceeded' : 'mnemic-search-failed',
      }
      // Fail-open: candidates stay empty; the request still succeeds.
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
   * Serve `POST /v1/context/feedback` — turn-level plan receipt: IDs (planId +
   * included candidate IDs) + plan outcome only. Publishes an observable
   * retained bus event and may refresh the cached field shadow in the
   * background. Never writes raw transcript text; never fabricates retrieval
   * outcomes.
   */
  async feedback(req: ContextFeedbackRequest): Promise<ContextFeedbackResponse> {
    const { sessionId, turnId, planId, includedCandidateIds, outcome } = validateFeedbackRequest(req)

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
        timestamp: new Date(),
      } as never)
    } catch (err) {
      // Bus emission is advisory — never fail the ack for a slow/closed bus.
      this.logger.warn('context feedback bus emit failed (non-fatal)', { error: String(err) })
    }

    // Feedback may trigger the next cached field refresh (coalesced, background).
    if (!this.cachedFieldShadow || this.shadowStale()) {
      void this.refreshFieldShadow('feedback')
    }

    this.logger.debug('[context] feedback', { sessionId, turnId, planId, included: includedCandidateIds.length, outcome })
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
} {
  if (!req || typeof req !== 'object') throw new ContextRequestError(400, 'request body must be an object')
  const { sessionId, turnId, planId, includedCandidateIds, outcome } = req
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
  if (outcome !== 'completed' && outcome !== 'error' && outcome !== 'unknown') {
    throw new ContextRequestError(400, 'outcome must be completed | error | unknown')
  }
  return { sessionId, turnId, planId, includedCandidateIds, outcome }
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

/** Map Mnemic hits → typed candidates with same-session filtering + caps. */
function toCandidates(hits: MemoryHitView[], sessionId: string, limit: number, maxCandidateChars: number): ContextCandidate[] {
  const out: ContextCandidate[] = []
  for (const hit of hits) {
    if (out.length >= limit) break
    const meta = hit.metadata
    const hitSession = meta && typeof meta.sessionId === 'string' ? meta.sessionId : undefined
    // Current-session content is already in OMP's canonical transcript. Only
    // global or cross-session memories may become supplemental candidates.
    if (hitSession === sessionId) continue
    const text = hit.content ?? ''
    const truncated = text.length > maxCandidateChars
    const id = safeOpaqueId(hit.id)
    out.push({
      id,
      source: 'mnemic',
      text: truncated ? text.slice(0, maxCandidateChars) : text,
      score: hit.score,
      sourceRefs: [id],
      metadata: {
        ...(hit.nodeType ? { nodeType: hit.nodeType.slice(0, 64) } : {}),
        ...(truncated ? { truncated: true } : {}),
      },
    })
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
