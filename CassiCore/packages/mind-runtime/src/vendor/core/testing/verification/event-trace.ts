/**
 * EventTraceCollector — captures and asserts on event streams.
 *
 * Works in two modes:
 * - **Live mode**: taps EventBus.onAll() to capture events in-process
 * - **Static mode**: wraps a pre-collected array (for replay or HTTP-collected events)
 *
 * Assertions use "subsequence" semantics by default: assertSequence([A, B, C])
 * passes even if the actual trace is [A, X, B, Y, C]. This prevents tests from
 * breaking when debug-level events are added later.
 */

import type { RuntimeEvent, EventType, EventOf, Unsubscribe } from '@cassicore/foundation'
import type { IEventBus } from '@cassicore/foundation'

/** An event with capture metadata attached */
export type TracedEvent = RuntimeEvent & {
  _tracedAt: number
  _index: number
}

/**
 * Partial matcher for events — type is required, other fields are optional
 * deep-partial matches against the event payload.
 */
export interface EventMatcher {
  /** Event type to match */
  type: EventType
  /** Partial payload match — each key/value must exist on the event */
  has?: Record<string, unknown>
  /** Max ms since previous matched event (only meaningful in sequences) */
  withinMs?: number
}

export class EventTraceCollector {
  private events: TracedEvent[] = []
  private unsub: Unsubscribe | null = null
  private counter = 0


  /** Create a live collector that taps into an EventBus */
  static live(bus: IEventBus): EventTraceCollector {
    const collector = new EventTraceCollector()
    collector.unsub = bus.onAll((event: RuntimeEvent) => {
      collector.events.push({
        ...event,
        _tracedAt: Date.now(),
        _index: collector.counter++,
      } as TracedEvent)
    })
    return collector
  }

  /** Create a static collector from a pre-collected event array */
  static fromArray(events: Array<RuntimeEvent & { _tracedAt?: number }>): EventTraceCollector {
    const collector = new EventTraceCollector()
    collector.events = events.map((e, i) => ({
      ...e,
      _tracedAt: e._tracedAt ?? Date.now(),
      _index: i,
    } as TracedEvent))
    collector.counter = events.length
    return collector
  }


  /** All captured events of a specific type */
  ofType<T extends EventType>(type: T): Array<EventOf<T> & { _tracedAt: number; _index: number }> {
    return this.events.filter(e => e.type === type) as any[]
  }

  /** Events between two event types (inclusive of both boundaries) */
  between(startType: EventType, endType: EventType): TracedEvent[] {
    const startIdx = this.events.findIndex(e => e.type === startType)
    if (startIdx === -1) return []
    const endIdx = this.events.findIndex((e, i) => i > startIdx && e.type === endType)
    if (endIdx === -1) return this.events.slice(startIdx)
    return this.events.slice(startIdx, endIdx + 1)
  }

  /** Count of events matching a type */
  count(type: EventType): number {
    return this.events.filter(e => e.type === type).length
  }

  /** Total number of captured events */
  get length(): number {
    return this.events.length
  }

  /** Get all events matching a matcher */
  matching(matcher: EventMatcher): TracedEvent[] {
    return this.events.filter(e => this.matchesEvent(e, matcher))
  }


  /**
   * Assert events appear in the given order (subsequence match).
   * Other events may appear between matched events.
   * Throws with a descriptive message on failure.
   */
  assertSequence(expected: EventMatcher[]): void {
    let searchFrom = 0

    for (let i = 0; i < expected.length; i++) {
      const matcher = expected[i]
      let found = false

      for (let j = searchFrom; j < this.events.length; j++) {
        if (this.matchesEvent(this.events[j], matcher)) {
          // Check timing constraint if present and not the first matcher
          if (matcher.withinMs !== undefined && i > 0) {
            const prevMatch = this.findPreviousMatch(expected[i - 1], j)
            if (prevMatch !== null) {
              const gap = this.events[j]._tracedAt - this.events[prevMatch]._tracedAt
              if (gap > matcher.withinMs) {
                throw new TraceAssertionError(
                  `Sequence step ${i} (${matcher.type}) found but ${gap}ms after previous match (limit: ${matcher.withinMs}ms)`,
                  expected,
                  this.events,
                )
              }
            }
          }
          searchFrom = j + 1
          found = true
          break
        }
      }

      if (!found) {
        throw new TraceAssertionError(
          `Sequence step ${i} not found: expected event "${matcher.type}"` +
          (matcher.has ? ` with ${JSON.stringify(matcher.has)}` : '') +
          ` (searched from index ${searchFrom - (i > 0 ? 1 : 0)}, ${this.events.length} total events)`,
          expected,
          this.events,
        )
      }
    }
  }

  /**
   * Assert that events appear in strict consecutive order — no interspersed events.
   */
  assertStrictSequence(expected: EventMatcher[]): void {
    if (expected.length === 0) return
    if (expected.length > this.events.length) {
      throw new TraceAssertionError(
        `Expected ${expected.length} events but only ${this.events.length} captured`,
        expected,
        this.events,
      )
    }

    // Find starting position
    outer: for (let start = 0; start <= this.events.length - expected.length; start++) {
      for (let i = 0; i < expected.length; i++) {
        if (!this.matchesEvent(this.events[start + i], expected[i])) {
          continue outer
        }
      }
      return // Found a strict match
    }

    throw new TraceAssertionError(
      `Strict sequence not found in trace`,
      expected,
      this.events,
    )
  }

  /** Assert at least one event matches */
  assertContains(matcher: EventMatcher): void {
    const found = this.events.some(e => this.matchesEvent(e, matcher))
    if (!found) {
      throw new TraceAssertionError(
        `Expected event "${matcher.type}" not found` +
        (matcher.has ? ` with ${JSON.stringify(matcher.has)}` : '') +
        ` (${this.events.length} events captured: ${this.typesSummary()})`,
        [matcher],
        this.events,
      )
    }
  }

  /** Assert NO event of this type was emitted */
  assertNoEvent(type: EventType): void {
    const matches = this.events.filter(e => e.type === type)
    if (matches.length > 0) {
      throw new TraceAssertionError(
        `Expected no "${type}" events but found ${matches.length}`,
        [{ type }],
        this.events,
      )
    }
  }

  /** Assert event A always appears before event B in the trace */
  assertOrder(first: EventType, second: EventType): void {
    const firstIdx = this.events.findIndex(e => e.type === first)
    const secondIdx = this.events.findIndex(e => e.type === second)

    if (firstIdx === -1) {
      throw new TraceAssertionError(`First event "${first}" not found in trace`, [], this.events)
    }
    if (secondIdx === -1) {
      throw new TraceAssertionError(`Second event "${second}" not found in trace`, [], this.events)
    }
    if (firstIdx >= secondIdx) {
      throw new TraceAssertionError(
        `Expected "${first}" (index ${firstIdx}) before "${second}" (index ${secondIdx})`,
        [{ type: first }, { type: second }],
        this.events,
      )
    }
  }

  /**
   * Wait for a specific event type to appear within a timeout.
   * Useful for async event flows.
   */
  async assertEventuallyEmitted(type: EventType, timeoutMs = 5000): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      if (this.events.some(e => e.type === type)) return
      await new Promise(r => setTimeout(r, 50))
    }
    throw new TraceAssertionError(
      `Event "${type}" not emitted within ${timeoutMs}ms`,
      [{ type }],
      this.events,
    )
  }


  /** Clear all captured events */
  clear(): void {
    this.events = []
    this.counter = 0
  }

  /** Stop capturing (detach from EventBus) */
  stop(): void {
    this.unsub?.()
    this.unsub = null
  }

  /** Get all captured events (read-only snapshot) */
  dump(): ReadonlyArray<TracedEvent> {
    return [...this.events]
  }

  /** Summarize event types for error messages */
  typesSummary(): string {
    const counts = new Map<string, number>()
    for (const e of this.events) {
      counts.set(e.type, (counts.get(e.type) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([t, c]) => `${t}(${c})`)
      .join(', ')
  }

  /** Produce a compact timeline string for debugging */
  timeline(): string {
    if (this.events.length === 0) return '(empty trace)'
    const base = this.events[0]._tracedAt
    return this.events
      .map(e => `+${e._tracedAt - base}ms ${e.type}`)
      .join('\n')
  }


  private matchesEvent(event: TracedEvent, matcher: EventMatcher): boolean {
    if (event.type !== matcher.type) return false
    if (matcher.has) {
      for (const [key, value] of Object.entries(matcher.has)) {
        if (!deepPartialMatch((event as any)[key], value)) return false
      }
    }
    return true
  }

  private findPreviousMatch(matcher: EventMatcher, beforeIndex: number): number | null {
    for (let i = beforeIndex - 1; i >= 0; i--) {
      if (this.matchesEvent(this.events[i], matcher)) return i
    }
    return null
  }
}


export class TraceAssertionError extends Error {
  constructor(
    message: string,
    public readonly expected: EventMatcher[],
    public readonly actual: ReadonlyArray<TracedEvent>,
  ) {
    super(message)
    this.name = 'TraceAssertionError'
  }
}


/** Deep partial match — value matches if all specified keys/values match recursively */
/**
 * @dep callers: matchesEvent (src/testing/verification/event-trace.ts), deepPartialMatch (src/testing/verification/event-trace.ts)
 * @dep calls: deepPartialMatch
 * @dep module: Verification
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function deepPartialMatch(actual: unknown, expected: unknown): boolean {
  if (expected === actual) return true
  if (expected === undefined) return true
  if (actual === null || actual === undefined) return false

  if (typeof expected === 'object' && expected !== null && typeof actual === 'object' && actual !== null) {
    for (const [key, val] of Object.entries(expected)) {
      if (!deepPartialMatch((actual as any)[key], val)) return false
    }
    return true
  }

  return false
}
