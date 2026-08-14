/**
 * VENDOR RUNTIME STUB — `core/events/index.ts` (minimal events surface).
 *
 * RUNTIME verbatim-backed surface used by the tools impls at load/register
 * time (`getEventBus`, `getContextWindowDebugger`). Owned by
 * `@cassicore/events` (P6 turn 3); re-pointed there when it publishes.
 * Backed by the vendored `core/event-bus.js` + `core/events/context-window-debug.js`.
 */
import { bus } from '../event-bus.js'
import type { EventBus } from '../event-bus.js'
import { getContextWindowDebugger } from './context-window-debug.js'
export type { EventBus } from '../event-bus.js'

/** Get the shared EventBus singleton. Same instance as `bus` in core/event-bus.ts. */
export function getEventBus(): EventBus {
  return bus
}

/** Clear all event history from the shared bus. */
export function resetEventBus(): void {
  bus.clear()
}

export {
  ContextWindowDebugger,
  initContextWindowDebugger,
  getContextWindowDebugger,
  resetContextWindowDebugger,
} from './context-window-debug.js'
export type {
  ContextWindowSnapshot,
  ContextWindowDiff,
} from './context-window-debug.js'
