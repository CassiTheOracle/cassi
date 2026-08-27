/**
 * @cassicore/mind-runtime — channel contract types (request/response framing).
 *
 * The mind runtime OWNS the channel contract. The spine (ohmypi extension) talks
 * to the runtime ONLY over this protocol — it never imports mind internals. Every
 * request carries an optional JSON `requestId` echoed verbatim in the response for
 * correlation/logging. Auth is loopback-bind + an optional shared bearer token from
 * `CASSI_MIND_TOKEN`.
 *
 * Transport: HTTP/1.1, `Content-Type: application/json`, one request–response per
 * call. No streaming on `tools/execute` for P3 (retained tools return complete
 * string results). Endpoint table in `boot.ts` / the README.
 *
 * Mind-mind boundary rule: `@cassicore/spine` imports types from this module;
 * `@cassicore/mind-runtime` never imports spine. These types form the stable seam
 * between the always-on runtime (host-agnostic core) and the ohmypi adapter.
 */

/** Lifecycle event a session mirror can carry. Mirrors recon §1.7 post-events. */
export type SessionMirrorEvent = 'start' | 'switch' | 'branch' | 'compact' | 'shutdown'

/** A single mirrored ohmypi session (weak structural shape the retained tools read). */
export interface MindMirroredSession {
  id: string
  channelId?: string
  history?: unknown[]
  config?: Record<string, unknown>
  createdAt?: string
  lastActiveAt?: string
  tokenCount?: number
  status?: string
  lastEvent?: SessionMirrorEvent
  /** Branch point entryId for `branch` events (recon §1.7). */
  branchFrom?: string
  /** Compaction summary for `compact` events. */
  summary?: string
  /** Session cwd captured at `start` so the runtime can attach path context. */
  cwd?: string
}

// ── Generic framing ──────────────────────────────────────────────────────────

/** Envelope: optional requestId echoed in the response. */
export interface ChannelRequest {
  requestId?: string
}

/** Envelope: result with the echoed requestId. */
export interface ChannelResponse {
  requestId?: string
}

/** Tool execution result returned by `tools/execute` (retained handlers return strings). */
export interface ToolExecuteResponse extends ChannelResponse {
  ok: boolean
  /** Retained handler's string/JSON result, verbatim (ToolHandler → AgentToolResult.content). */
  result?: string
  error?: string
}

// ── Endpoint request/response payloads ───────────────────────────────────────

/** `POST /v1/tools/execute` — dispatch a retained mind tool to the runtime. */
export interface ExecuteToolRequest extends ChannelRequest {
  tool: string
  params: Record<string, unknown>
  sessionId?: string
}

/** `POST /v1/session/mirror` — mirror a session lifecycle event from the spine. */
export interface MirrorSessionRequest extends ChannelRequest {
  event: SessionMirrorEvent
  sessionId: string
  cwd?: string
  branchFrom?: string
  summary?: string
}
export interface MirrorSessionResponse extends ChannelResponse {
  ack: true
}

/** `POST /v1/events/push` — push a harness event (mcp_notification, others) into the mind. */
export interface PushEventRequest extends ChannelRequest {
  type: string
  payload: unknown
  sessionId?: string
}
export interface PushEventResponse extends ChannelResponse {
  ack: true
}

/** `POST /v1/snapshot` — fetch mind-state for the spine's appendEntry journal. */
export interface SnapshotResponse extends ChannelResponse {
  state: MindSnapshot
}

/** Mind-state snapshot (memory/store stats, active loops, session mirrors). */
export interface MindSnapshot {
  memory: SnapshotMemory
  loops: {
    unifiedLoopRunning: boolean
    cortexOscillation: boolean
  }
  sessions: Array<{ id: string; lastEvent?: string; lastActiveAt?: string }>
  uptimeMs: number
  health: 'ok'
}

export interface SnapshotMemory {
  engrams?: number
  stats?: Record<string, unknown> | null
  lightning?: Record<string, unknown> | null
}

/** `GET /v1/health` (plain) + `POST /v1/health` (verbose). */
export interface HealthResponse extends ChannelResponse {
  status: 'ok'
  uptimeMs: number
  fieldStats?: Record<string, unknown> | null
  lightningStatus?: Record<string, unknown> | null
  /** P5 retained mind-health read slice (admin-api fold): cortex/pineal/thalamus/memory/replay/observability. */
  retained?: MindHealthSnapshot
}

/**
 * The retained mind-health read snapshot (host-agnostic, read-only over the field).
 * Mirrors `packages/mind-runtime/src/health/index.ts`'s `MindHealthSnapshot`.
 */
export interface MindHealthSnapshot {
  cortex: {
    available: boolean
    regions?: Array<{ name: string; activation: number }>
    activeSignals?: number
    affect?: Record<string, unknown> | null
    stats?: Record<string, unknown> | null
    oscillation?: { running: boolean }
  }
  pineal: {
    available: boolean
    domains?: string[]
    facets?: number
    pinned?: number
  }
  thalamus: {
    available: boolean
    activeSession?: string | null
    contextStats?: Record<string, unknown> | null
  }
  memory: {
    available: boolean
    engrams?: number
    stats?: Record<string, unknown> | null
    lightning?: Record<string, unknown> | null
    harmony?: Record<string, unknown> | null
  }
  replay: {
    available: boolean
    loops?: { unifiedLoop: boolean; cortexOscillation: boolean }
    sessions?: number
    uptimeMs?: number
  }
  observability: {
    available: boolean
    modules?: number
    busEventsTracked?: number
    startedAt?: number
  }
}

// ── Memory backend endpoints ─────────────────────────────────────────────────

/** `POST /v1/memory/status` — the ohmypi memory-backend adapter's `status()`. */
export interface MemoryStatusResponse extends ChannelResponse {
  backend: 'mnemic-field'
  stats?: Record<string, unknown> | null
}

/** `POST /v1/memory/search` — the adapter's `search(query, opts)`. */
export interface MemorySearchRequest extends ChannelRequest {
  query: string
  limit?: number
  type?: string
  sessionId?: string
}
export interface MemoryHit {
  id: string
  content: string
  score: number
  nodeType?: string | null
  metadata?: Record<string, unknown>
}
export interface MemorySearchResponse extends ChannelResponse {
  results: MemoryHit[]
}

/** `POST /v1/memory/save` — the adapter's `save(entry)`. */
export interface MemorySaveRequest extends ChannelRequest {
  content: string
  type?: string
  metadata?: Record<string, unknown>
  sessionId?: string
}
export interface MemorySaveResponse extends ChannelResponse {
  id: string
}

/** `POST /v1/shutdown` — graceful stop. */
export interface ShutdownRequest extends ChannelRequest { }
export interface ShutdownResponse extends ChannelResponse {
  ok: true
}

// ── Shared context seam (P8): candidate + feedback protocol ──────────────────
//
// The spine asks the runtime for context candidates for a turn and reports which
// ones the plan actually used. Requests are deliberately narrow: the candidate
// request carries ONLY {sessionId, turnId, query, limit?, deadlineMs?,
// includeFieldShadow?} and the feedback carries ONLY IDs + a plan outcome — no
// raw transcript text ever crosses this seam in either direction.
//
// The shared concepts (`ContextCandidate`, `ContextSourceStatus`, `FieldAdvisory`)
// are OWNED by `@cassicore/thalamus/attention` (a leaf subpath that never
// evaluates the legacy Thalamus graph) and re-exported here so the spine keeps
// importing the whole contract from the mind-runtime barrel.

import type { ContextCandidate, ContextSourceStatus, FieldAdvisory } from '@cassicore/thalamus/attention'
export type { ContextCandidate, ContextSourceStatus, FieldAdvisory }

/**
 * `POST /v1/context/candidates` — typed Mnemic candidate lookup for a turn.
 * All fields are validated and bounded server-side; the request never carries
 * transcript content or raw 7599 arrays.
 */
export interface ContextCandidatesRequest extends ChannelRequest {
  sessionId: string
  turnId: number
  query: string
  /** Max candidates (clamped into [1, service max]; default 5). */
  limit?: number
  /** Request-side deadline in ms (clamped into service bounds; default 2500). */
  deadlineMs?: number
  /** Attach the cached field shadow advisory (never waits for a fresh read). */
  includeFieldShadow?: boolean
}

export interface ContextCandidatesResponse extends ChannelResponse {
  candidates: ContextCandidate[]
  sources: ContextSourceStatus[]
  /** Cached field advisory; null on first-miss/stale/offline/disabled. */
  fieldAdvisory: FieldAdvisory | null
}

/** Turn-level plan outcome for the feedback channel — ID-only, never raw text. */
export type ContextFeedbackOutcome = 'completed' | 'error' | 'unknown'

/**
 * `POST /v1/context/feedback` — turn-level plan receipt: IDs + plan outcome
 * only. No raw transcript text is accepted, stored, or forwarded; retrieval
 * outcomes are never fabricated.
 */
export interface ContextFeedbackRequest extends ChannelRequest {
  sessionId: string
  turnId: number
  /** The plan id from `ContextPlanReceipt` (or the plan the turn ran). */
  planId: string
  /** Candidate IDs the turn-level plan included (≤ 64). */
  includedCandidateIds: string[]
  outcome: ContextFeedbackOutcome
}

export interface ContextFeedbackResponse extends ChannelResponse {
  ack: true
}
