/**
 * gaming-mode — Port over CassiCore's `core/intelligence/gaming-mode.js` (isGamingMode).
 *
 * The original is an in-memory runtime flag (pause non-essential background work while
 * the user is gaming) that imports `rootLogger` from CassiCore's logger (deep daemon code).
 * Constellation only reads the flag. This port keeps the same in-memory semantics, dropped
 * the logging import, and is fully self-contained.
 *
 * ohmypi note: a host that manages gaming mode can call `setGamingMode`; the flag is per-process.
 *
 * Self-contained: no imports.
 */

let _active = false
let _autoManaged = false

/** Whether gaming mode is currently active. */
export function isGamingMode(): boolean {
  return _active
}

/**
 * Set gaming mode on or off.
 *
 * @param active Whether to enable gaming mode.
 * @param auto   True when called by a GPU guard (auto-managed). Manual calls omit it.
 */
export function setGamingMode(active: boolean, auto = false): void {
  if (_active === active) return // no-op on duplicate calls
  _active = active
  _autoManaged = auto
}

/** Whether gaming mode was auto-activated by the GPU guard. */
export function isGamingModeAutoManaged(): boolean {
  return _autoManaged
}
