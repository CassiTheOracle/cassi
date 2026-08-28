/**
 * WorkflowEventBus — scoped event system for reactive workflow patterns.
 *
 * Provides pub/sub within a single workflow run. Steps emit events via
 * ctx.emit(channel, data), and ListenNodes subscribe to channels.
 *
 * Events are buffered: if a listener isn't yet registered when an event
 * fires, the event is queued and delivered when the listener subscribes.
 * This handles the common case where emit happens in step N but the
 * listener is defined later in the workflow.
 */

import type { ILogger } from '@cassicore/foundation'

export interface WorkflowEvent {
  channel: string
  data: unknown
  timestamp: Date
  emittedByNodeId?: string
}

export type EventHandler = (event: WorkflowEvent) => void | Promise<void>

export class WorkflowEventBus {
  private readonly listeners = new Map<string, Set<EventHandler>>()
  private readonly buffer = new Map<string, WorkflowEvent[]>()
  private readonly allHandlers = new Set<EventHandler>()
  private readonly logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('workflow-events')
  }

  /** Emit an event to a channel. Notifies all subscribers and buffers for future subscribers. */
  emit(channel: string, data: unknown, emittedByNodeId?: string): void {
    const event: WorkflowEvent = {
      channel,
      data,
      timestamp: new Date(),
      emittedByNodeId,
    }

    // Buffer the event for late subscribers
    const buf = this.buffer.get(channel) ?? []
    buf.push(event)
    this.buffer.set(channel, buf)

    // Notify channel-specific listeners
    const handlers = this.listeners.get(channel)
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(event)
        } catch (err) {
          this.logger.warn('Event handler error', { channel, error: String(err) })
        }
      }
    }

    // Notify wildcard listeners
    for (const handler of this.allHandlers) {
      try {
        handler(event)
      } catch (err) {
        this.logger.warn('Wildcard event handler error', { channel, error: String(err) })
      }
    }
  }

  /** Subscribe to events on a specific channel. Returns unsubscribe function. */
  on(channel: string, handler: EventHandler): () => void {
    let handlers = this.listeners.get(channel)
    if (!handlers) {
      handlers = new Set()
      this.listeners.set(channel, handlers)
    }
    handlers.add(handler)

    return () => {
      handlers!.delete(handler)
    }
  }

  /** Subscribe to one event on a channel. Auto-unsubscribes after first fire. */
  once(channel: string, handler: EventHandler): () => void {
    const unsub = this.on(channel, (event) => {
      unsub()
      handler(event)
    })
    return unsub
  }

  /** Subscribe to all events on all channels. Returns unsubscribe function. */
  onAll(handler: EventHandler): () => void {
    this.allHandlers.add(handler)
    return () => {
      this.allHandlers.delete(handler)
    }
  }

  /**
   * Wait for the next event on any of the specified channels.
   * Returns a promise that resolves with the event.
   * Checks the buffer first for already-emitted events.
   */
  waitFor(
    channels: string[],
    opts?: { timeoutMs?: number; afterTimestamp?: Date },
  ): Promise<WorkflowEvent> {
    const afterTs = opts?.afterTimestamp?.getTime() ?? 0

    // Check buffer for existing events
    for (const channel of channels) {
      const buf = this.buffer.get(channel) ?? []
      for (const event of buf) {
        if (event.timestamp.getTime() > afterTs) {
          return Promise.resolve(event)
        }
      }
    }

    // No buffered event — wait for the next one
    return new Promise((resolve, reject) => {
      let settled = false
      const unsubs: Array<() => void> = []

      const cleanup = () => {
        for (const unsub of unsubs) unsub()
        if (timer) clearTimeout(timer)
      }

      const handler: EventHandler = (event) => {
        if (settled) return
        if (event.timestamp.getTime() <= afterTs) return
        settled = true
        cleanup()
        resolve(event)
      }

      for (const channel of channels) {
        unsubs.push(this.on(channel, handler))
      }

      // Timeout
      let timer: ReturnType<typeof setTimeout> | undefined
      const timeoutMs = opts?.timeoutMs ?? 0
      if (timeoutMs > 0) {
        timer = setTimeout(() => {
          if (settled) return
          settled = true
          cleanup()
          reject(new Error(`Timed out waiting for events on channels: ${channels.join(', ')}`))
        }, timeoutMs)
      }
    })
  }

  /** Get all buffered events for a channel. */
  getBuffered(channel: string): WorkflowEvent[] {
    return [...(this.buffer.get(channel) ?? [])]
  }

  /** Get all buffered events across all channels. */
  getAllBuffered(): WorkflowEvent[] {
    const all: WorkflowEvent[] = []
    for (const events of this.buffer.values()) {
      all.push(...events)
    }
    return all.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
  }

  /** Clear all listeners and buffers. */
  clear(): void {
    this.listeners.clear()
    this.buffer.clear()
    this.allHandlers.clear()
  }
}
