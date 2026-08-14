/**
 * VENDOR TYPE STUB — `core/intelligence/module-session-registry.ts`
 *
 * Type-only placeholder for the `ModuleSessionRegistry` surface consumed by the P1 live-set
 * (`base/cognitive-module.ts`). Self-contained; builtin types only; no runtime.
 * Re-pointed to `@cassicore/workspace` at P5.
 */

/** A registered persistent debug session. */
export interface ModuleSession {
  key: string
}

/** Registry mapping module keys to persistent debug sessions. */
export class ModuleSessionRegistry {
  /** Create/load the session for a module key (persisted to disk). */
  getOrCreate(moduleKey: string): ModuleSession {
    throw new Error('vendor stub: no runtime implementation')
  }

  /** Get the session id for a module key, if one is registered. */
  getSessionId(moduleKey: string): string | undefined {
    throw new Error('vendor stub: no runtime implementation')
  }
}
