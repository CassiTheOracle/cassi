/**
 * VENDOR TYPE STUB — `core/event-history.ts` (host, P7).
 *
 * Type placeholder for query-events.ts (tools). `EventHistory` is a host-side
 * (P7) runtime surface; tools only consume it as a type + `history.query(...)`.
 * Re-pointed to the owning host package at P7.
 */
import type { ComplexEventQuery, EventQueryResult, EventType, RuntimeEvent } from '@cassicore/foundation'

/** Metadata attached to a captured event. */
export interface EventMetadata {
  source?: string
  sessionId?: string
  agentId?: string
  [key: string]: unknown
}

/** A single stored event with metadata. */
export interface StoredEvent {
  event: RuntimeEvent
  metadata: EventMetadata
  capturedAt: number
}

/** In-memory, ring-buffer-backed event history (host-side). */
export interface EventHistory {
  capture(event: RuntimeEvent, metadata: EventMetadata): void
  query(filter: ComplexEventQuery): EventQueryResult
  getRecent(count: number, type?: EventType): StoredEvent[]
  getSince(timestamp: Date, type?: EventType): StoredEvent[]
  getBySession(sessionId: string): StoredEvent[]
  getByTypePattern(pattern: string): StoredEvent[]
  size(): number
  clear(): void
}

/** Get the shared EventHistory singleton (host-side). */
export function getEventHistory(): EventHistory | undefined {
  return undefined
}

/** Set the shared EventHistory singleton (host-side). */
export function setEventHistory(_history: EventHistory): void {
  /* host-side wiring — no-op placeholder */
}
