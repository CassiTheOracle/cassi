/**
 * MnemicField interface augmentation — host-wired /memory/mnemic/tier3 endpoint.
 *
 * core/admin-api/memory.ts calls `field.runTier3Analysis()` on an MnemicField
 * for the POST /memory/mnemic/tier3 route. The landed `@cassicore/mnemic-field`
 * MnemicField class does not declare this method (nor does D: core/anything —
 * the daemon's __mnemicField is host-injected and may carry host-only members).
 * Declared on the type so the migrated endpoint typechecks as-written (the D:
 * route calls it unconditionally). No implementation is invented — @cassicore/
 * host's daemon field must provide it at runtime. Re-visit when the host's
 * daemon/mnemic field publishes.
 *
 * NOTE: the top-level `import type` is REQUIRED for TypeScript to treat this
 * as a module augmentation (interface merge) rather than a shorthand ambient
 * declaration that would REPLACE the real module surface.
 */
import type { MnemicField } from '@cassicore/mnemic-field'

declare module '@cassicore/mnemic-field' {
  interface MnemicField {
    runTier3Analysis(): Promise<unknown>
  }
}
