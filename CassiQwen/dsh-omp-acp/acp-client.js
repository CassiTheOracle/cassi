/**
 * Minimal Agent Client Protocol (ACP v1) client over one stdio connection.
 *
 * Framing is newline-delimited JSON in both directions, as measured against
 * oh-my-pi 18.2.8 (`omp acp`). The client owns request/response correlation,
 * routes agent-initiated requests (permission prompts) to one handler, and
 * broadcasts notifications (`session/update`) to subscribers.
 *
 * @module dsh-omp-acp/acp-client
 */
import { spawn } from "node:child_process";

const DEFAULT_REQUEST_TIMEOUT_MS = 60_000;
const STDERR_TAIL_CHARS = 4_000;

/** Failure raised for a JSON-RPC error reply, a dead connection, or a timeout. */
export class AcpTransportError extends Error {
  /**
   * @param {string} message - human-readable failure text.
   * @param {{ code?: string, data?: unknown, cause?: unknown }} [details] - JSON-RPC code and payload.
   */
  constructor(message, details = {}) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause });
    this.name = "AcpTransportError";
    this.code = details.code;
    this.data = details.data;
  }
}

/**
 * One ACP connection to an agent process.
 *
 * A connection is single-use: after the child exits, every later request fails
 * fast so callers can rebuild it instead of hanging on a dead pipe.
 */
export class AcpConnection {
  #executable;
  #args;
  #cwd;
  #env;
  #requestTimeoutMs;
  #child;
  #pending = new Map();
  #nextId = 1;
  #buffer = "";
  #decoder = new TextDecoder();
  #stderrDecoder = new TextDecoder();
  #notifications = new Set();
  #requestHandler;
  #stderr = "";
  #exit = null;
  #disposed = false;

  /**
   * @param {object} options - launch and timeout configuration.
   * @param {string} options.executable - absolute path to the agent executable.
   * @param {string[]} [options.args] - argv after the executable (default `["acp"]`).
   * @param {string} [options.cwd] - working directory for the agent process.
   * @param {Record<string, string>} [options.env] - extra environment entries.
   * @param {number} [options.requestTimeoutMs] - per-request deadline in milliseconds.
   */
  constructor({ executable, args = ["acp"], cwd, env, requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS }) {
    if (typeof executable !== "string" || executable.length === 0) throw new TypeError("AcpConnection needs an executable path");
    this.#executable = executable;
    this.#args = [...args];
    this.#cwd = cwd;
    this.#env = env;
    this.#requestTimeoutMs = requestTimeoutMs;
  }

  /** Whether the agent child is running. */
  get alive() {
    return this.#child !== undefined && this.#exit === null && !this.#disposed;
  }

  /** PID of the agent child, or `undefined` before it starts. */
  get pid() {
    return this.#child?.pid;
  }

  /** Captured stderr tail, for diagnostics on failure. */
  get stderrTail() {
    return this.#stderr;
  }

  /** Spawn the agent process. Idempotent. */
  start() {
    if (this.#child !== undefined) return this;
    if (this.#disposed) throw new AcpTransportError("the ACP connection is disposed");
    const child = spawn(this.#executable, this.#args, {
      cwd: this.#cwd,
      env: this.#env === undefined ? process.env : { ...process.env, ...this.#env },
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.#child = child;
    child.stdout.on("data", (chunk) => this.#ingest(chunk));
    child.stderr.on("data", (chunk) => {
      this.#stderr = (this.#stderr + this.#stderrDecoder.decode(chunk, { stream: true })).slice(-STDERR_TAIL_CHARS);
    });
    child.on("error", (error) => this.#settle(new AcpTransportError(`ACP agent failed to start: ${error.message}`, { cause: error })));
    child.on("exit", (code, signal) => {
      const detail = this.#stderr.trim();
      const reason = `ACP agent exited (code ${code ?? "null"}${signal ? `, signal ${signal}` : ""})${detail ? `: ${detail}` : ""}`;
      this.#settle(new AcpTransportError(reason, { code: "AGENT_EXITED" }));
    });
    return this;
  }

  /**
   * Send one request and await its result.
   *
   * @param {string} method - JSON-RPC method name.
   * @param {unknown} params - request parameters.
   * @param {{ timeoutMs?: number, signal?: AbortSignal }} [options] - per-call deadline and cancellation.
   * @returns {Promise<unknown>} the result payload.
   */
  request(method, params, { timeoutMs = this.#requestTimeoutMs, signal } = {}) {
    if (this.#disposed) return Promise.reject(new AcpTransportError("the ACP connection is disposed"));
    if (this.#exit !== null) return Promise.reject(this.#exit);
    this.start();
    const id = this.#nextId++;
    return new Promise((resolve, reject) => {
      let timer;
      const settle = (fn) => (value) => {
        clearTimeout(timer);
        signal?.removeEventListener("abort", onAbort);
        this.#pending.delete(id);
        fn(value);
      };
      const onAbort = () => settle(reject)(new AcpTransportError(`ACP request "${method}" was cancelled`, { code: "ABORTED" }));
      if (signal?.aborted) {
        reject(new AcpTransportError(`ACP request "${method}" was cancelled`, { code: "ABORTED" }));
        return;
      }
      if (timeoutMs > 0) {
        timer = setTimeout(() => settle(reject)(new AcpTransportError(`ACP request "${method}" timed out after ${timeoutMs} ms`, { code: "TIMEOUT" })), timeoutMs);
        timer.unref?.();
      }
      signal?.addEventListener("abort", onAbort, { once: true });
      this.#pending.set(id, { resolve: settle(resolve), reject: settle(reject), method });
      this.#write({ jsonrpc: "2.0", id, method, params: params ?? {} });
    });
  }

  /**
   * Send one notification (no reply expected).
   *
   * @param {string} method - JSON-RPC method name.
   * @param {unknown} params - notification parameters.
   */
  notify(method, params) {
    if (this.#disposed || this.#exit !== null) return;
    this.#write({ jsonrpc: "2.0", method, params: params ?? {} });
  }

  /**
   * Subscribe to agent notifications such as `session/update`.
   *
   * @param {(notification: { method: string, params: unknown }) => void} handler - called for every notification.
   * @returns {() => void} unsubscribe.
   */
  onNotification(handler) {
    this.#notifications.add(handler);
    return () => this.#notifications.delete(handler);
  }

  /**
   * Install the handler for agent-initiated requests (ACP permission prompts).
   *
   * @param {(method: string, params: unknown) => Promise<unknown>} handler - resolves with the request result.
   */
  setRequestHandler(handler) {
    this.#requestHandler = handler;
  }

  /** Terminate the agent process and fail every pending request. */
  dispose() {
    if (this.#disposed) return;
    this.#disposed = true;
    this.#settle(new AcpTransportError("the ACP connection was disposed", { code: "DISPOSED" }));
    this.#child?.stdin?.end?.();
    this.#child?.kill?.();
  }

  #write(message) {
    const stdin = this.#child?.stdin;
    if (stdin === undefined) return;
    try {
      stdin.write(`${JSON.stringify(message)}\n`);
    } catch (error) {
      this.#settle(new AcpTransportError(`ACP write failed: ${error.message}`, { cause: error }));
    }
  }

  #ingest(chunk) {
    this.#buffer += this.#decoder.decode(chunk, { stream: true });
    let index;
    while ((index = this.#buffer.indexOf("\n")) >= 0) {
      const line = this.#buffer.slice(0, index).trim();
      this.#buffer = this.#buffer.slice(index + 1);
      if (!line) continue;
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        continue;
      }
      this.#dispatch(message);
    }
  }

  #dispatch(message) {
    if (message.id !== undefined && message.method === undefined) {
      const pending = this.#pending.get(message.id);
      if (pending === undefined) return;
      if (message.error) {
        const detail = message.error;
        pending.reject(new AcpTransportError(`${pending.method} failed: ${detail?.message ?? JSON.stringify(detail)}`, { code: detail?.code, data: detail }));
        return;
      }
      pending.resolve(message.result);
      return;
    }
    if (message.id !== undefined && typeof message.method === "string") {
      this.#answer(message);
      return;
    }
    if (typeof message.method === "string") {
      for (const handler of this.#notifications) {
        try {
          handler({ method: message.method, params: message.params });
        } catch {
          // A subscriber failure must never take down the transport.
        }
      }
    }
  }

  #answer(message) {
    const respond = (payload) => this.#write({ jsonrpc: "2.0", id: message.id, ...payload });
    if (this.#requestHandler === undefined) {
      respond({ error: { code: -32601, message: `no client handler for ${message.method}` } });
      return;
    }
    Promise.resolve()
      .then(() => this.#requestHandler(message.method, message.params))
      .then(
        (result) => respond({ result: result ?? {} }),
        (error) => respond({ error: { code: -32603, message: error?.message ?? String(error) } }),
      );
  }

  #settle(error) {
    this.#exit = error;
    const pending = [...this.#pending.values()];
    this.#pending.clear();
    for (const entry of pending) entry.reject(error);
  }
}
