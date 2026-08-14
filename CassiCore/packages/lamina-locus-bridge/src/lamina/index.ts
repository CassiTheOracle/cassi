/**
 * Lamina — labeled, CAS-edited, tool-writable memory blocks.
 *
 * Public API:
 *   - `LaminaField` — the high-level facade
 *   - `LaminaStore` — direct SQLite access (advanced)
 *
 * See `project_lamina_primitive_design.md` for the architectural rationale.
 */

export { LaminaField } from './lamina-field.js'
export { LaminaStore } from './lamina-store.js'
export {
  LaminaCasConflict,
  LaminaOverflow,
  LaminaAuthorityError,
  DEFAULT_CHAR_LIMIT,
} from './types.js'
export type {
  Lamina,
  LaminaCreate,
  LaminaReplace,
  LaminaAppend,
  LaminaRethink,
  LaminaQuery,
  LaminaScope,
} from './types.js'
export type { LaminaCaller } from './lamina-store.js'
