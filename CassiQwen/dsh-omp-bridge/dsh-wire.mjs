/**
 * Minimal DeepSeek Harness wire client.
 *
 * The harness webserver exposes a JSON envelope over `POST /api/<method>` and a
 * live event feed over the `/api/events.mux` WebSocket:
 *
 *   request   { type: "client-request", rpcId, method, payload }
 *   response  { type: "server-response", rpcId, result: { ok: true, value } }
 *   mux frame { type: "server-request", rpcId, method: payload.type,
 *               payload: { type: "session/event", sessionId, event } }
 *
 * with `event` a SessionEvent such as
 *   { type: "turn/start",     data: { turn } }
 *   { type: "assistant/chunk", data: { turn, step, chunk } }   // chunk: StreamChunk
 *   { type: "turn/end",       data: { turn, reason } }
 *
 * The same feed also carries the harness's *questions* to a client — a
 * server-request whose payload is `approval/requested` (a tool call waiting for
 * a human) or `question/requested` (the model asking a question). Those are
 * answered out of band, not with a unary call: `POST /api/respond` carries a
 * `client-response` that echoes the frame's own `rpcId`, and the harness
 * returns a receipt `{accepted: true}` or `{accepted: false, reason}`. The
 * frame is pushed to every open feed and replayed to a feed that opens while it
 * is still pending, so a late subscriber still sees it.
 *
 * The `/api` fence is a browser-trust fence, not an auth layer: a client whose
 * `Host` is a loopback authority and which sends no `Origin` is accepted. Node
 * sets `Host` from the URL and sends no `Origin`, so nothing else is required.
 */
import { randomUUID } from "node:crypto";

/** A failure reported by the harness, or a transport failure talking to it. */
export class DshWireError extends Error {
  /** @param {string} message */
  constructor(message) {
    super(message);
    this.name = "DshWireError";
  }
}

/** Normalize a harness base URL: `http://127.0.0.1:8787` or `…/api` both work. */
function normalizeBaseUrl(baseUrl) {
  const trimmed = String(baseUrl ?? "").trim().replace(/\/+$/, "");
  if (trimmed.length === 0) throw new DshWireError("a harness base URL is required, e.g. http://127.0.0.1:8787");
  return trimmed.endsWith("/api") ? trimmed.slice(0, -4) : trimmed;
}

/** The text of one prompt content part, or `undefined` when it carries no text. */
function contentType(part) {
  return part?.type === "text" && typeof part.text === "string" ? part.text : undefined;
}

export class DshWire {
  #base;
  #timeoutMs;

  /**
   * @param {object} options
   * @param {string} options.baseUrl - harness origin, e.g. `http://127.0.0.1:8787`.
   * @param {number} [options.timeoutMs] - per-request timeout (default 30 s).
   */
  constructor({ baseUrl, timeoutMs = 30_000 }) {
    this.#base = normalizeBaseUrl(baseUrl);
    this.#timeoutMs = timeoutMs;
  }

  /** The harness origin this client talks to. */
  get baseUrl() {
    return this.#base;
  }

  /** WebSocket URL of the live event feed. */
  get muxUrl() {
    return `${this.#base.replace(/^http/, "ws")}/api/events.mux`;
  }

  /**
   * One `POST /api/<method>` round trip.
   *
   * @param {string} method - RPC method name, e.g. `session.list`.
   * @param {object} [payload] - method payload.
   * @param {{timeoutMs?: number}} [options]
   * @returns {Promise<any>} the `result.value` the harness returned.
   */
  async call(method, payload = {}, { timeoutMs = this.#timeoutMs } = {}) {
    const rpcId = `wire-${randomUUID()}`;
    let response;
    try {
      response = await fetch(`${this.#base}/api/${method}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ type: "client-request", rpcId, method, payload }),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (error) {
      throw new DshWireError(`${method} could not reach ${this.#base}: ${error?.message ?? error}`, { method, cause: error });
    }
    const text = await response.text();
    if (!response.ok) throw new DshWireError(`${method} → HTTP ${response.status}: ${text.slice(0, 300)}`, { method, status: response.status });
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      throw new DshWireError(`${method} → response was not JSON: ${text.slice(0, 300)}`, { method });
    }
    const result = body?.result;
    if (result?.ok !== true) {
      const detail = result?.error ?? body;
      throw new DshWireError(`${method} → ${JSON.stringify(detail).slice(0, 400)}`, { method, result: detail });
    }
    return result.value;
  }

  /** Newest-first session summaries: `{ sessionId, updatedAt, running, blank, cwd, … }`. */
  async listSessions() {
    const value = await this.call("session.list", {});
    return Array.isArray(value?.items) ? value.items : [];
  }

  /**
   * Answer one harness question frame (`approval/requested`).
   *
   * @param {object} options
   * @param {string} options.rpcId - the `rpcId` of the server-request frame.
   * @param {string} options.sessionId
   * @param {string} options.approvalId
   * @param {"allowed-once" | "rejected"} options.outcome
   * @param {number} [options.timeoutMs]
   * @returns {Promise<{accepted: boolean, reason?: string}>} the harness receipt.
   */
  async respond({ rpcId, sessionId, approvalId, outcome, timeoutMs = this.#timeoutMs }) {
    const message = { type: "client-response", rpcId, result: { ok: true, value: { sessionId, approvalId, outcome } } };
    let response;
    try {
      response = await fetch(`${this.#base}/api/respond`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(message),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (error) {
      throw new DshWireError(`respond could not reach ${this.#base}: ${error?.message ?? error}`, { cause: error });
    }
    const text = await response.text();
    if (!response.ok) throw new DshWireError(`respond → HTTP ${response.status}: ${text.slice(0, 300)}`, { status: response.status });
    try {
      return JSON.parse(text);
    } catch {
      throw new DshWireError(`respond → response was not JSON: ${text.slice(0, 300)}`);
    }
  }

  /** Create a session; returns `{ sessionId, agentPreset? }`. */
  async createSession({ cwd, agentPreset, sessionId } = {}) {
    const payload = {};
    if (cwd !== undefined) payload.cwd = cwd;
    if (agentPreset !== undefined) payload.agentPreset = agentPreset;
    if (sessionId !== undefined) payload.sessionId = sessionId;
    return await this.call("session.create", payload);
  }

  /**
   * Enqueue one user turn. Resolves with `{ accepted: true }` as soon as the
   * harness accepts it — the answer itself arrives on the event feed.
   *
   * @param {object} options
   * @param {string} options.sessionId
   * @param {string} options.text
   * @param {"queue" | "steer"} [options.mode]
   */
  async prompt({ sessionId, text, mode = "queue", clientTimeZone }) {
    const payload = { sessionId, mode, content: [{ type: "text", text }] };
    if (clientTimeZone !== undefined) payload.clientTimeZone = clientTimeZone;
    return await this.call("session.prompt", payload);
  }

  /**
   * Open the live event feed.
   *
   * @param {object} options
   * @param {(frame: {sessionId: string, event: object}) => void} options.onEvent
   * @param {(frame: {rpcId: string, method: string | undefined, payload: object}) => void} [options.onServerRequest] - harness questions (approvals, model questions) that need a `respond`.
   * @param {(error: Error) => void} [options.onError]
   * @param {number} [options.timeoutMs] - how long to wait for the socket to open.
   * @returns {{ready: Promise<void>, close: () => void}}
   */
  subscribe({ onEvent, onServerRequest, onError, timeoutMs = this.#timeoutMs }) {
    const socket = new WebSocket(this.muxUrl);
    let closed = false;
    const ready = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new DshWireError(`the event feed ${this.muxUrl} did not open within ${timeoutMs} ms`)), timeoutMs);
      timer.unref?.();
      socket.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      });
      socket.addEventListener("error", (event) => {
        clearTimeout(timer);
        reject(new DshWireError(`the event feed ${this.muxUrl} failed: ${event?.message ?? "socket error"}`));
      });
      socket.addEventListener("message", (message) => {
        let frame;
        try {
          frame = JSON.parse(typeof message.data === "string" ? message.data : String(message.data));
        } catch {
          return;
        }
        // The full envelope is `{type:"server-request", rpcId, method, payload}`; accept a bare payload too.
        const payload = frame?.payload ?? frame;
        if (payload?.type !== "session/event") {
          // A question the harness needs an answer to; the rpcId is the receipt key.
          if (onServerRequest !== undefined && typeof frame?.rpcId === "string" && payload?.type !== undefined) {
            try {
              onServerRequest({ rpcId: frame.rpcId, method: frame.method, payload });
            } catch (error) {
              onError?.(error);
            }
          }
          return;
        }
        try {
          onEvent({ sessionId: payload.sessionId, event: payload.event, view: payload.view });
        } catch (error) {
          onError?.(error);
        }
      });
      socket.addEventListener("close", () => {
        if (!closed) onError?.(new DshWireError("the event feed closed"));
      });
    });
    return {
      ready,
      close: () => {
        closed = true;
        try {
          socket.close();
        } catch {
          /* already closing */
        }
      },
    };
  }

  /**
   * Run one turn and collect its streamed answer.
   *
   * Subscribes before prompting, ignores session events until the harness has
   * accepted the prompt, then follows the first turn that reports a number
   * until its `turn/end`.
   *
   * @param {object} options
   * @param {string} options.sessionId
   * @param {string} options.text
   * @param {(text: string) => void} [options.onDelta] - called per text delta.
   * @param {number} [options.timeoutMs] - whole-turn budget.
   * @param {"queue" | "steer"} [options.mode]
   * @returns {Promise<{text: string, reason: string | undefined, turn: number | undefined}>}
   */
  async runTurn({ sessionId, text, onDelta, timeoutMs = 600_000, mode = "queue" }) {
    let armed = false;
    let turn;
    let answer = "";
    let settle;
    const finished = new Promise((resolve, reject) => {
      settle = {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      };
    });
    const timer = setTimeout(() => settle.reject(new DshWireError(`the turn in ${sessionId} produced no turn/end within ${timeoutMs} ms`)), timeoutMs);
    timer.unref?.();

    const stream = this.subscribe({
      onEvent: ({ sessionId: eventSession, event }) => {
        if (eventSession !== sessionId || !armed) return;
        const data = event?.data ?? {};
        if (turn === undefined && typeof data.turn === "number") turn = data.turn;
        if (data.turn !== turn) return;
        if (event.type === "assistant/chunk" && data.chunk?.type === "text-delta" && typeof data.chunk.text === "string") {
          answer += data.chunk.text;
          onDelta?.(data.chunk.text);
        } else if (event.type === "turn/end") {
          settle.resolve({ text: answer, reason: data.reason, turn });
        }
      },
      onError: (error) => {
        if (armed) settle.reject(error);
      },
    });

    try {
      await stream.ready;
      await this.prompt({ sessionId, text, mode });
      armed = true;
      return await finished;
    } finally {
      stream.close();
      clearTimeout(timer);
    }
  }
}

