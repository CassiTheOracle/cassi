import type { EventType, EventOf, Unsubscribe, RuntimeEvent } from "../types/events.js";
import type { IEventBus } from "../types/interfaces.js";

/**
 * EventBus — simple typed event bus implementation.
 *
 * Internals:
 * - Uses a Map<EventType, Set<handler>> to store listeners. Sets prevent
 *   duplicate handler registrations and make removal by reference straightforward.
 * - A separate Set of global listeners supports the onAll() universal tap,
 *   which is used by the Subconscious EventStream to observe all system events.
 */
export class EventBus implements IEventBus {
  private listeners: Map<EventType, Set<(...args: unknown[]) => void>>;
  private globalListeners: Set<(event: RuntimeEvent) => void>;

  constructor() {
    this.listeners = new Map();
    this.globalListeners = new Set();
  }

  /**
   * Emit a typed event to all registered listeners for that event type,
   * then notify all global (onAll) listeners.
   * Handlers are invoked synchronously in registration order (Set iteration order).
   */
  emit<T extends RuntimeEvent>(event: T): void {
    const set = this.listeners.get(event.type as EventType);
    if (set) {
      // Snapshot handlers to avoid issues if handlers modify the set during iteration.
      const handlers = Array.from(set);
      for (const h of handlers) {
        try {
          // Type assertion: stored handlers follow the (e: EventOf<T>) => void shape
          (h as (e: T) => void)(event);
        } catch (err) {
          console.error(`[EventBus] Error in handler for event ${event.type}:`, err);
        }
      }
    }

    // Notify universal (onAll) listeners — snapshot to prevent mutation during iteration
    if (this.globalListeners.size > 0) {
      const globals = Array.from(this.globalListeners);
      for (const h of globals) {
        try {
          h(event);
        } catch (err) {
          console.error(`[EventBus] Error in global handler for event ${event.type}:`, err);
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
   */
  once<T extends EventType>(type: T, handler: (e: EventOf<T>) => void): void {
    const wrapped = (e: EventOf<T>) => {
      try {
        handler(e);
      } finally {
        this.off(type, wrapped as (e: EventOf<T>) => void);
      }
    };
    this.on(type, wrapped as (e: EventOf<T>) => void);
  }

  /**
   * Remove a specific handler by reference.
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
}

export const bus = new EventBus();
