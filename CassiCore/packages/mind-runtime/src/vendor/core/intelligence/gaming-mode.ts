/**
 * Gaming mode — transient runtime flag that pauses non-essential background work.
 *
 * When active, background modules (embedding worker, LLM observer, dreamer,
 * consolidation engine, unified intelligence loop) skip their ticks/cycles
 * to minimise CPU, I/O, and subprocess activity while the user is gaming.
 *
 * Two activation paths:
 *   1. Automatic — external GPU monitoring sets this when
 *      external GPU usage is detected (e.g. a game), and clears it when
 *      the GPU becomes free.
 *   2. Manual — the admin API exposes a toggle so the user (or an agent)
 *      can enable gaming mode regardless of GPU state.
 *
 * This is intentionally a simple in-memory flag with no persistence,
 * event bus coupling, or config dependency. It resets on daemon restart.
 */

import { rootLogger } from '@cassicore/events'

const logger = rootLogger.child('gaming-mode')

let _active = false
/** True when the GPU guard is driving the flag (vs. manual toggle). */
let _autoManaged = false

/** Whether gaming mode is currently active. */
export function isGamingMode(): boolean {
  return _active
}

/**
 * Set gaming mode on or off.
 *
 * @param active  Whether to enable gaming mode.
 * @param auto    True when called by the GPU guard (auto-managed).
 *                Manual calls should omit this or pass false.
 */
export function setGamingMode(active: boolean, auto = false): void {
  if (_active === active) return  // no-op on duplicate calls

  _active = active
  _autoManaged = auto

  if (active) {
    logger.info('Gaming mode activated', { auto })
  } else {
    logger.info('Gaming mode deactivated', { auto })
  }
}

/** Whether gaming mode was auto-activated by the GPU guard. */
export function isGamingModeAutoManaged(): boolean {
  return _autoManaged
}
