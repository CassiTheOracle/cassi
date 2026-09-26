/**
 * @cassicore/mind-runtime — barrel.
 *
 * Exposes the channel client **contract types** (the spine imports these — the
 * runtime owns the contract, §1 mind-mind boundary) + the server + memory backend
 * + boot entry. `@cassicore/spine` imports ONLY the types from here (host-agnostic
 * seam); the spine never imports the retained mind internals.
 */

export { createMindRuntime } from './boot.js'
export type {
  MindRuntime,
  MindRuntimeOptions,
} from './boot.js'
export { MindFieldTelemetry } from './field/telemetry.js'
export type {
  FieldTelemetryConfig,
  FieldTelemetryStatus,
  FieldTelemetrySnapshot,
  FieldBalanceSummary,
  ThetaTemporalResultant,
  JProxySummary,
  FixedHelicalScanSummary,
} from './field/telemetry.js'

export { MindChannelServer } from './channel/server.js'
export type { ChannelServerOptions } from './channel/server.js'

export { MnemicMemoryAdapter } from './memory/backend.js'
export type {
  MnemicMemoryAdapterOptions,
  MemorySaveEntry,
  MemoryHitView,
} from './memory/backend.js'

// ── Context candidate service (P8 shared context seam) ───────────────────────
export { RuntimeContextCandidateService, ContextRequestError } from './context/candidates.js'
export type {
  RuntimeContextCandidateServiceOptions,
  ContextCandidateServiceStatus,
  ContextMemorySurface,
  ContextFieldTelemetrySurface,
} from './context/candidates.js'

export { MindSessionMirror } from './session-store.js'
export type { MindSessionManagerSurface } from './session-store.js'

// ── Retained mind-health read slice (admin-api fold, §5 #27) ─────────────────
export { collectMindHealth } from './health/index.js'
export type {
  CortexHealth,
  PinealHealth,
  MemoryHealth,
  ReplayHealth,
  ObservabilityHealth,
  MindHealthSnapshot,
} from './health/index.js'

// ── Channel contract types (the stable seam spine imports) ──────────────────
export type {
  SessionMirrorEvent,
  MindMirroredSession,
  ChannelRequest,
  ChannelResponse,
  ToolExecuteResponse,
  ExecuteToolRequest,
  MirrorSessionRequest,
  MirrorSessionResponse,
  PushEventRequest,
  PushEventResponse,
  SnapshotResponse,
  MindSnapshot,
  SnapshotMemory,
  HealthResponse,
  MemoryStatusResponse,
  MemorySearchRequest,
  MemoryHit,
  MemorySearchResponse,
  MemorySaveRequest,
  MemorySaveResponse,
  ShutdownRequest,
  ShutdownResponse,
  ContextCandidate,
  ContextActionRequest,
  ContextActionResponse,
  ContextCounterflowBucket,
  ContextCounterflowStatus,
  ContextFieldFailureCode,
  ContextStatusResponse,
  ContextCandidatesRequest,
  ContextCandidatesResponse,
  ContextFeedbackOutcome,
  ContextFeedbackToolResult,
  ContextFeedbackRequest,
  ContextFeedbackResponse,
  ContextSourceStatus,
  FieldAdvisory,
} from './channel/protocol.js'
