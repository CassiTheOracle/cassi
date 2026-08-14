/**
 * VENDORED RUNTIME STUB — faithful copy of
 * `core/intelligence/utils/prefixed-id.ts` (`prefixedId`).
 *
 * Shared prefixed ID generator — timestamp + random + monotonic counter.
 * Re-point to `@cassicore/utils` at P6 (§P5b table §B2.2).
 */

let counter = 0

export function prefixedId(prefix: string): string {
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 6)
  return `${prefix}_${ts}${rand}${(counter++).toString(36)}`
}
