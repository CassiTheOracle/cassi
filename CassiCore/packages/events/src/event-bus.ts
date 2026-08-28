import { rootLogger } from './logger.js';

import type { EventType, EventOf, Unsubscribe, RuntimeEvent } from "@cassicore/foundation";
import type { IEventBus, ILogger } from "@cassicore/foundation";

const logger: ILogger = rootLogger.child('event-bus');

// Ring Buffer — O(1) add, bounded memory, insertion-order retrieval

class RingBuffer<T> {
  private items: T[] = [];
  private startIndex = 0;

  constructor(public readonly maxSize: number = 10000) {}

  add(item: T): void {
    if (this.items.length < this.maxSize) {
      this.items.push(item);
    } else {
      this.items[this.startIndex] = item;
      this.startIndex = (this.startIndex + 1) % this.maxSize;
    }
  }

  /** All items in insertion order */
  getAll(): T[] {
    if (this.startIndex === 0) return [...this.items];
    return [
      ...this.items.slice(this.startIndex),
      ...this.items.slice(0, this.startIndex),
    ];
  }

  /** Last N items in insertion order */
  getRecent(count: number): T[] {
    const all = this.getAll();
    return all.slice(-count);
  }

  /** Items matching a predicate, in insertion order */
  filter(predicate: (item: T) => boolean): T[] {
    return this.getAll().filter(predicate);
  }

  get size(): number {
    return this.items.length;
  }

  clear(): void {
    this.items = [];
    this.startIndex = 0;
  }
}

// Event History Configuration

export interface EventHistoryOptions {
  /** Max events per session ring buffer (default: 10000) */
  sessionMaxSize?: number;
  /** Max events in global ring buffer (default: 10000) */
  globalMaxSize?: number;
}

// EventBus — typed event bus with session history tracking

/**
 * EventBus — typed event bus with built-in session history.
 *
 * Internals:
 * - Uses a Map<EventType, Set<handler>> to store listeners. Sets prevent
 *   duplicate handler registrations and make removal by reference straightforward.
 * - A separate Set of global listeners supports the onAll() universal tap,
 *   which is used by the Subconscious EventStream to observe all system events.
 * - Session history is tracked via per-session RingBuffers; events with a
 *   `sessionId` field are auto-stored on emit(). A global RingBuffer captures
 *   all events regardless.
 */
export class EventBus implements IEventBus {
  private listeners: Map<EventType, Set<(...args: unknown[]) => void>>;
  private globalListeners: Set<(event: RuntimeEvent) => void>;

  // Handler failure tracking — auto-remove after MAX_HANDLER_FAILURES consecutive errors
  private handlerFailures: WeakMap<Function, number> = new WeakMap();
  private static readonly MAX_HANDLER_FAILURES = 5;

  // Session history tracking
  private sessionHistory: Map<string, RingBuffer<RuntimeEvent>>;
  private globalHistory: RingBuffer<RuntimeEvent>;
  private sessionMaxSize: number;

  constructor(options: EventHistoryOptions = {}) {
    this.listeners = new Map();
    this.globalListeners = new Set();
    this.sessionHistory = new Map();
    this.sessionMaxSize = options.sessionMaxSize ?? 10000;
    this.globalHistory = new RingBuffer(options.globalMaxSize ?? 10000);
  }


  /**
   * Emit an event into bounded global history, optionally retain it per session,
   * then notify global and typed listeners. High-churn context feedback remains
   * global-only so arbitrary feedback session IDs cannot grow `sessionHistory`.
   */
  async emit<T extends RuntimeEvent>(event: T): Promise<void> {
    this.globalHistory.add(event);
    const sessionId = (event as Record<string, unknown>).sessionId as string | undefined;
    const retainInSessionHistory = (event as { type: string }).type !== 'cassi.context.feedback';
    if (sessionId && retainInSessionHistory) {
      let buffer = this.sessionHistory.get(sessionId);
      if (!buffer) {
        buffer = new RingBuffer(this.sessionMaxSize);
        this.sessionHistory.set(sessionId, buffer);
      }
      buffer.add(event);
    }

    // Notify typed listeners — snapshot to avoid issues if handlers modify the set
    const set = this.listeners.get(event.type as EventType);
    if (set) {
      const handlers = Array.from(set);
      for (const h of handlers) {
        try {
          // Use Promise.resolve() to handle both sync and async handlers transparently
          await Promise.resolve(h(event));
          // Reset failure count on success
          this.handlerFailures.delete(h);
        } catch (err) {
          // Track consecutive failures
          const failures = (this.handlerFailures.get(h) ?? 0) + 1;
          this.handlerFailures.set(h, failures);

          // Preserve stack traces by checking if err is an Error instance
          const errorInfo: Record<string, unknown> = {
            eventType: event.type,
            message: err instanceof Error ? err.message : String(err),
            consecutiveFailures: failures,
          };
          if (err instanceof Error && err.stack) {
            errorInfo.stack = err.stack;
          }

          if (failures >= EventBus.MAX_HANDLER_FAILURES) {
            set.delete(h);
            this.handlerFailures.delete(h);
            logger.error('Handler auto-removed after repeated failures', errorInfo);
          } else {
            logger.error('Error in handler', errorInfo);
          }
        }
      }
    }

    // Notify universal (onAll) listeners — snapshot to prevent mutation during iteration
    if (this.globalListeners.size > 0) {
      const globals = Array.from(this.globalListeners);
      for (const h of globals) {
        try {
          // Use Promise.resolve() to handle both sync and async handlers transparently
          await Promise.resolve(h(event));
          // Reset failure count on success
          this.handlerFailures.delete(h);
        } catch (err) {
          // Track consecutive failures
          const failures = (this.handlerFailures.get(h) ?? 0) + 1;
          this.handlerFailures.set(h, failures);

          // Preserve stack traces by checking if err is an Error instance
          const errorInfo: Record<string, unknown> = {
            eventType: event.type,
            message: err instanceof Error ? err.message : String(err),
            consecutiveFailures: failures,
          };
          if (err instanceof Error && err.stack) {
            errorInfo.stack = err.stack;
          }

          if (failures >= EventBus.MAX_HANDLER_FAILURES) {
            this.globalListeners.delete(h);
            this.handlerFailures.delete(h);
            logger.error('Global handler auto-removed after repeated failures', errorInfo);
          } else {
            logger.error('Error in global handler', errorInfo);
          }
        }
      }
    }
  }

  /**
   * Subscribe to a typed event. Returns an unsubscribe function.
   */
  on<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): Unsubscribe {
    let set = this.listeners.get(type);
    if (!set) {
      set = new Set();
      this.listeners.set(type, set);
    }
    set.add(handler as unknown as (...args: unknown[]) => void);

    return () => {
      this.off(type, handler);
    };
  }

  /**
   * Subscribe once — auto-unsubscribes after first fire.
   * Note: This wrapper is synchronous for backward compatibility.
   * The handler itself can be async and will be awaited by emit().
   */
  once<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void {
    const wrapped = async (e: EventOf<T>) => {
      try {
        await Promise.resolve(handler(e));
      } finally {
        this.off(type, wrapped as (e: EventOf<T>) => void);
      }
    };
    this.on(type, wrapped as (e: EventOf<T>) => void);
  }

  /**
   * Remove a specific handler by reference.
   * @param type - Event type to unsubscribe from
   * @param handler - The handler function to remove (must be the same reference passed to on())
   */
  off<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void {
    const set = this.listeners.get(type);
    if (!set) return;
    set.delete(handler as unknown as (...args: unknown[]) => void);
    if (set.size === 0) {
      this.listeners.delete(type);
    }
  }

  /**
   * Number of listeners currently registered for a type.
   * @param type - Event type to count listeners for
   * @returns The number of registered listeners for the given event type
   */
  listenerCount(type: EventType): number {
    const set = this.listeners.get(type);
    return set ? set.size : 0;
  }

  /**
   * Subscribe to ALL events regardless of type — the universal consciousness tap.
   * Used by the Subconscious EventStream to observe the complete system event flow.
   * Returns an unsubscribe function.
   */
  onAll(handler: (event: RuntimeEvent) => void): Unsubscribe {
    this.globalListeners.add(handler);
    return () => {
      this.globalListeners.delete(handler);
    };
  }


  /**
   * Get all events for a session, in chronological order.
   */
  getAllEvents(sessionId: string): RuntimeEvent[] {
    return this.sessionHistory.get(sessionId)?.getAll() ?? [];
  }

  /**
   * Get session events since a timestamp (inclusive).
   */
  getEventsSince(sessionId: string, timestamp: number): RuntimeEvent[] {
    return this.sessionHistory.get(sessionId)
      ?.filter(e => ((e as Record<string, unknown>).timestamp as number) >= timestamp) ?? [];
  }

  /**
   * Get the N most recent session events.
   */
  getRecentEvents(sessionId: string, count: number): RuntimeEvent[] {
    return this.sessionHistory.get(sessionId)?.getRecent(count) ?? [];
  }

  /**
   * Get all global events in chronological order.
   */
  getAllGlobalEvents(): RuntimeEvent[] {
    return this.globalHistory.getAll();
  }

  /**
   * Get global events since a timestamp (inclusive).
   */
  getGlobalEventsSince(timestamp: number): RuntimeEvent[] {
    return this.globalHistory.filter(
      e => ((e as Record<string, unknown>).timestamp as number) >= timestamp
    );
  }

  /**
   * Get the N most recent global events.
   */
  getRecentGlobalEvents(count: number): RuntimeEvent[] {
    return this.globalHistory.getRecent(count);
  }

  /**
   * Number of events stored for a session.
   */
  getSessionEventCount(sessionId: string): number {
    return this.sessionHistory.get(sessionId)?.size ?? 0;
  }

  /**
   * Clear history for a single session.
   */
  clearSession(sessionId: string): void {
    this.sessionHistory.delete(sessionId);
  }

  /**
   * Number of sessions with active history buffers.
   * Useful for monitoring memory growth.
   */
  get sessionHistoryCount(): number {
    return this.sessionHistory.size;
  }

  /**
   * Subscribe to session:ended events and auto-clean session history.
   * Call this after the EventBus is wired to the SessionManager to prevent
   * unbounded memory growth from retained session history buffers.
   */
  wireSessionCleanup(): void {
    this.on('session:ended' as EventType, (event: unknown) => {
      const sessionId = (event as Record<string, unknown>).sessionId as string | undefined;
      if (sessionId) {
        this.clearSession(sessionId);
        logger.debug('Auto-cleared session history', { sessionId: sessionId.slice(0, 8) });
      }
    });
    logger.info('Session history auto-cleanup wired');
  }

  /**
   * Clear all history (session + global).
   */
  clear(): void {
    this.sessionHistory.clear();
    this.globalHistory.clear();
  }
}

export const bus = new EventBus();
