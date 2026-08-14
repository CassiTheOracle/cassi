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

export { MindChannelServer } from './channel/server.js'
export type { ChannelServerOptions } from './channel/server.js'

export { MnemicMemoryAdapter } from './memory/backend.js'
export type {
  MnemicMemoryAdapterOptions,
  MemorySaveEntry,
  MemoryHitView,
} from './memory/backend.js'

export { MindSessionMirror } from './session-store.js'
export type { MindSessionManagerSurface } from './session-store.js'

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
} from './channel/protocol.js'
