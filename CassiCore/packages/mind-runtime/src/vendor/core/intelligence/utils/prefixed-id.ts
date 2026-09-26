/**
 * Shared prefixed ID generator — timestamp + random + monotonic counter.
 *
 * Format: `${prefix}_${tsBase36}${randBase36}${counterBase36}`
 *
 * The counter breaks ties on same-millisecond calls so generated IDs are
 * strictly monotonic within a process. SQLite tables use these as primary
 * keys; the monotonic suffix makes ORDER BY id behave like ORDER BY created_at
 * without needing a secondary index.
 */

let counter = 0

export function prefixedId(prefix: string): string {
  const ts = Date.now().toString(36)
  const rand = Math.random().toString(36).slice(2, 6)
  return `${prefix}_${ts}${rand}${(counter++).toString(36)}`
}
