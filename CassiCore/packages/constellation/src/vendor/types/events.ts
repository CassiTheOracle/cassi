/**
 * VENDORED TYPE STUB — mirrors `types/events.js` (CassiCore) RuntimeEvent federation.
 * The full CassiCore event graph lives in the daemon. This stub reproduces the event
 * surface used by the vendored runtime + constellation code: the event types the
 * vendored `base/cognitive-module.ts` dispatches on AND every event type emitted
 * across `src/` (each with an index signature so arbitrary payload fields flow).
 */
export type RuntimeEvent =
  // cognitive-module dispatch surface
  | { type: 'turn:start'; sessionId: string; message: string; [key: string]: unknown }
  | { type: 'turn:end'; sessionId: string; response: string; durationMs: number; [key: string]: unknown }
  | { type: 'daemon:ready'; startedAt?: Date; [key: string]: unknown }
  | { type: 'daemon:shutdown'; reason: string; [key: string]: unknown }
  | { type: 'daemon:restarting'; reason: string; expectedDowntimeMs?: number; [key: string]: unknown }
  | { type: 'plugin:crashed'; pluginId: string; error: string; crashCount?: number; [key: string]: unknown }
  | {
      type: 'tool:round-complete'
      sessionId?: string
      round?: number
      toolCalls?: Array<{ name: string; id: string }>
      results?: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>
      [key: string]: unknown
    }
  // event types emitted by constellation/src
  | { type: 'constellation:started'; [key: string]: unknown }
  | { type: 'constellation:completed'; [key: string]: unknown }
  | { type: 'constellation:failed'; [key: string]: unknown }
  | { type: 'constellation:cancelled'; [key: string]: unknown }
  | { type: 'constellation:decomposing'; [key: string]: unknown }
  | { type: 'constellation:decomposed'; [key: string]: unknown }
  | { type: 'constellation:executing'; [key: string]: unknown }
  | { type: 'constellation:checkpoint'; [key: string]: unknown }
  | { type: 'constellation:stagnation'; [key: string]: unknown }
  | { type: 'constellation:branch:created'; [key: string]: unknown }
  | { type: 'constellation:branch:launched'; [key: string]: unknown }
  | { type: 'constellation:branch:completed'; [key: string]: unknown }
  | { type: 'constellation:branch:failed'; [key: string]: unknown }
  | { type: 'constellation:branch:degraded'; [key: string]: unknown }
  | { type: 'constellation:cluster-observer:broadcast'; [key: string]: unknown }
  | { type: 'constellation:corpus-observer:broadcast'; [key: string]: unknown }
  | { type: 'corpus:steer'; [key: string]: unknown }
  | { type: 'mini-helix:cycle:started'; [key: string]: unknown }
  | { type: 'thinker:insight'; [key: string]: unknown }
  | { type: 'topology:updated'; [key: string]: unknown }

export type EventType = RuntimeEvent['type']

/** Extract the event shape for a given type literal */
export type EventOf<T extends EventType> = Extract<RuntimeEvent, { type: T }>

/** Unsubscribe function returned by EventBus.on() */
export type Unsubscribe = () => void
