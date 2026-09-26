/**
 * VENDORED RUNTIME STUB — faithful copy of `core/intelligence/gaming-mode.ts`
 * (`isGamingMode` & friends), with the host-owned `rootLogger` dependency
 * replaced by a minimal local no-op/console logger so the stub stays
 * self-contained.
 *
 * Re-point to the owning auxiliary package at P5-A/P6 (§P5b table §A2.2 / Open
 * Flag 5). Do NOT vendor against foundation — gaming-mode is a standalone
 * sibling, not part of the P1 substrate.
 */

/** Minimal host-free logger mirroring the shape gaming-mode uses. */
const logger = {
  child: () => logger,
  info: (_msg: string, _meta?: Record<string, unknown>): void => {
    /* no-op in the vendored context */
  },
  debug: (_msg: string, _meta?: Record<string, unknown>): void => {
    /* no-op */
  },
  warn: (_msg: string, _meta?: Record<string, unknown>): void => {
    /* no-op */
  },
}

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
