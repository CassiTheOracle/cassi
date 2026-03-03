/**
 * SSE Connection Manager
 *
 * Uses fetch() + manual SSE parsing instead of the native EventSource API.
 * The native EventSource only fires handlers registered for specific named event
 * types — it cannot catch-all over arbitrary `event: <type>` fields in the stream.
 * A fetch-based parser routes every event to both named handlers AND catch-all
 * handlers, enabling the event log and rate chart to work correctly.
 */

export type SseEventHandler = (data: unknown, rawEvent: MessageEvent) => void;

export interface EventStreamOptions {
  /** Max reconnect delay in ms (default 30s) */
  maxRetryMs?: number;
  /** Base reconnect delay in ms (default 1s) */
  baseRetryMs?: number;
  /** Called when connection state changes */
  onStateChange?: (state: EventStreamState) => void;
}

export type EventStreamState = "connecting" | "connected" | "reconnecting" | "closed";

export class EventStreamManager {
  private url: string;
  private handlers = new Map<string, Set<SseEventHandler>>();
  private catchAllHandlers = new Set<SseEventHandler>();
  private state: EventStreamState = "closed";
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private opts: Required<EventStreamOptions>;
  private closed = false;
  private abortController: AbortController | null = null;

  constructor(url: string, opts: EventStreamOptions = {}) {
    this.url = url;
    this.opts = {
      maxRetryMs: opts.maxRetryMs ?? 30_000,
      baseRetryMs: opts.baseRetryMs ?? 1_000,
      onStateChange: opts.onStateChange ?? (() => {}),
    };
  }

  /** Start the SSE connection. */
  connect(): this {
    this.closed = false;
    this.openConnection();
    return this;
  }

  /** Permanently close. No more reconnects. */
  close(): void {
    this.closed = true;
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.abortController?.abort();
    this.abortController = null;
    this.setState("closed");
  }

  /**
   * Listen for a named SSE event type (e.g. "turn:start").
   * Returns an unsubscribe function.
   */
  on(eventType: string, handler: SseEventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);
    return () => this.handlers.get(eventType)?.delete(handler);
  }

  /**
   * Listen for ALL events (any type). Useful for the event log and rate chart.
   * Returns an unsubscribe function.
   */
  onAll(handler: SseEventHandler): () => void {
    this.catchAllHandlers.add(handler);
    return () => this.catchAllHandlers.delete(handler);
  }

  get currentState(): EventStreamState {
    return this.state;
  }

  // ---- private ----

  private openConnection(): void {
    this.setState(this.retryCount === 0 ? "connecting" : "reconnecting");
    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    this.fetchStream(controller).catch(() => {
      // handled inside fetchStream
    });
  }

  private async fetchStream(controller: AbortController): Promise<void> {
    try {
      const response = await fetch(this.url, {
        signal: controller.signal,
        headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      this.retryCount = 0;
      this.setState("connected");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // SSE field accumulators (reset after each blank-line dispatch)
      let eventType = "message";
      let eventData = "";
      let eventId = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split("\n");
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line === "" || line === "\r") {
            // Blank line = end of event — dispatch if we have data
            if (eventData !== "") {
              const fakeEvent = new MessageEvent(eventType, {
                data: eventData,
                lastEventId: eventId,
              });
              this.dispatch(eventType, fakeEvent);
            }
            // Reset accumulators
            eventType = "message";
            eventData = "";
            eventId = "";
          } else if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const chunk = line.slice(5).trimStart();
            eventData = eventData === "" ? chunk : eventData + "\n" + chunk;
          } else if (line.startsWith("id:")) {
            eventId = line.slice(3).trim();
          }
          // Ignore "retry:" and comment lines (":...")
        }
      }

      // Stream ended cleanly — reconnect unless closed
      if (!this.closed) {
        this.scheduleReconnect();
      }
    } catch (err) {
      if (this.closed) return;
      if ((err as { name?: string }).name === "AbortError") return;
      this.scheduleReconnect();
    }
  }

  private dispatch(type: string, e: MessageEvent): void {
    let data: unknown = e.data;
    try {
      data = JSON.parse(e.data as string);
    } catch {
      // keep raw string
    }

    // Named handlers
    this.handlers.get(type)?.forEach((h) => h(data, e));

    // Catch-all handlers — merge type into the data object
    const payload =
      typeof data === "object" && data !== null
        ? { type, ...(data as Record<string, unknown>) }
        : { type, raw: data };
    this.catchAllHandlers.forEach((h) => h(payload, e));
  }

  private scheduleReconnect(): void {
    this.setState("reconnecting");
    const delay = Math.min(
      this.opts.baseRetryMs * 2 ** this.retryCount,
      this.opts.maxRetryMs
    );
    this.retryCount++;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      if (!this.closed) this.openConnection();
    }, delay);
  }

  private setState(s: EventStreamState): void {
    if (this.state !== s) {
      this.state = s;
      this.opts.onStateChange(s);
    }
  }
}
