/**
 * VENDOR TYPE STUB — `core/intelligence/flux-team/global-blackboard-registry.ts`
 *
 * Type-only placeholder for the `GlobalBlackboardRegistry` surface consumed by the P1 live-set
 * (`base/cognitive-module.ts`). Self-contained; builtin types only; no runtime.
 * Re-pointed to `@cassicore/flux-team` at P3.
 */

import type { Blackboard } from './blackboard.js'

/** Registry of named global blackboards. */
export class GlobalBlackboardRegistry {
  /** Get or create the blackboard with the given name. */
  getOrCreate(name: string, opts?: { persist?: boolean }): Blackboard {
    throw new Error('vendor stub: no runtime implementation')
  }
}
