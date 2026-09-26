/**
 * The oh-my-pi session pool: one ACP connection per omp session, plus one
 * control connection that lists the durable session store and runs stateless
 * auxiliary calls.
 *
 * Sessions stay on disk exactly as oh-my-pi wrote them; this module only
 * resumes them over the protocol. A resumed session keeps its own history, so
 * a DeepSeek Harness turn continues the very session the user sees in omp.
 *
 * @module dsh-omp-acp/omp-sessions
 */
import { readdirSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { AcpConnection, AcpTransportError } from "./acp-client.js";

const ACP_PROTOCOL_VERSION = 1;
const DEFAULT_MAX_LIVE_SESSIONS = 4;
const DEFAULT_IDLE_TIMEOUT_MS = 15 * 60_000;
const DEFAULT_PROMPT_TIMEOUT_MS = 30 * 60_000;
const DEFAULT_CANCEL_GRACE_MS = 15_000;
const DEFAULT_AUXILIARY_TIMEOUT_MS = 5 * 60_000;
const AUXILIARY_UNAVAILABLE = new Set(["compaction", "session-title"]);

/** Methods an ACP agent may address to its client that this harness never advertises. */
const UNSUPPORTED_CLIENT_METHODS = new Set([
  "fs/read_text_file",
  "fs/write_text_file",
  "terminal/create",
  "terminal/output",
  "terminal/wait_for_exit",
  "terminal/kill",
  "terminal/release",
]);

function normalizeSession(entry) {
  const sessionId = typeof entry?.sessionId === "string" && entry.sessionId.length > 0 ? entry.sessionId : undefined;
  if (sessionId === undefined) return undefined;
  return {
    sessionId,
    cwd: typeof entry.cwd === "string" ? entry.cwd : "",
    title: typeof entry.title === "string" ? entry.title : "",
    updatedAt: typeof entry.updatedAt === "string" ? entry.updatedAt : "",
    messageCount: Number.isFinite(entry?._meta?.messageCount) ? entry._meta.messageCount : undefined,
  };
}

function updatedAtMs(session) {
  const parsed = Date.parse(session.updatedAt);
  return Number.isFinite(parsed) ? parsed : 0;
}

/** The option id of one ACP permission option (`{ optionId, name, kind }`). */
export function permissionOptionId(option) {
  return typeof option?.optionId === "string" && option.optionId.length > 0 ? option.optionId : undefined;
}

/**
 * Select the permission option an ACP permission request should be answered with.
 *
 * oh-my-pi reads `optionId` from the response unconditionally, so an answer
 * without a selected option is not merely impolite — the agent reports
 * "Tool permission response used unknown option ID: undefined" and the tool
 * fails. This therefore always selects one of the options the agent offered:
 * the one whose kind or id reads as the requested direction, else the nearest
 * end of the list.
 *
 * @param {object} params - `session/request_permission` parameters.
 * @param {"allow" | "reject"} policy - configured answer policy.
 * @returns {object} an ACP permission outcome.
 */
export function selectPermission(params, policy) {
  const options = Array.isArray(params?.options) ? params.options : [];
  if (options.length === 0) return { outcome: { outcome: "cancelled" } };
  const reads = (option) => `${option?.kind ?? ""} ${permissionOptionId(option) ?? ""}`.toLowerCase();
  const wanted = policy === "reject" ? "reject" : "allow";
  const chosen = options.find((option) => reads(option).includes(wanted))
    ?? (policy === "reject" ? options.at(-1) : options[0]);
  return { outcome: { outcome: "selected", optionId: permissionOptionId(chosen) } };
}

/** Human-readable tool identity of one permission request. */
export function permissionToolName(params) {
  const toolCall = params?.toolCall;
  const candidate = toolCall?.title ?? params?.title ?? toolCall?.kind ?? params?.kind;
  return typeof candidate === "string" && candidate.trim().length > 0 ? candidate.trim() : "tool";
}

/**
 * Decide one `session/request_permission` with the configured policy, asking a
 * human first when the policy says to.
 *
 * An ask that cannot decide — refused, cancelled, unavailable or failing —
 * leaves the session usable by answering with the static allow the policy
 * itself would have given; the harness approval service reports its own
 * refusals, so no deadline is kept on this side.
 *
 * @param {object} params - `session/request_permission` parameters.
 * @param {object} config - decision configuration.
 * @param {"allow" | "reject" | "ask"} config.policy - configured answer policy.
 * @param {(request: { toolName: string, reason?: string }) => Promise<"allowed-once" | "rejected" | "cancelled" | "unavailable">} [config.ask] - human decision channel.
 * @returns {Promise<{ reply: object, decidedBy: "policy" | "human", outcome_: string }>} the ACP reply (exactly what the agent must receive) and how it was reached.
 */
export async function resolvePermission(params, { policy, ask }) {
  const staticPolicy = policy === "reject" ? "reject" : "allow";
  if (policy !== "ask" || ask === undefined) {
    return { reply: selectPermission(params, staticPolicy), decidedBy: "policy", outcome_: staticPolicy };
  }
  const toolName = permissionToolName(params);
  const reason = typeof params?.reason === "string" && params.reason.length > 0 ? params.reason : undefined;
  let decision;
  try {
    decision = await ask({ toolName, reason });
  } catch {
    decision = "unavailable";
  }
  if (decision === "rejected") return { reply: selectPermission(params, "reject"), decidedBy: "human", outcome_: "reject" };
  if (decision === "allowed-once") return { reply: selectPermission(params, "allow"), decidedBy: "human", outcome_: "allow" };
  return { reply: selectPermission(params, "allow"), decidedBy: "policy", outcome_: `allow (${decision})` };
}

/** The oh-my-pi session pool. */
export class OmpAcpSessions {
  #executable;
  #args;
  #spawnCwd;
  #env;
  #maxLiveSessions;
  #idleTimeoutMs;
  #promptTimeoutMs;
  #cancelGraceMs;
  #auxiliaryTimeoutMs;
  #permission;
  #askPermission;
  #auxiliaryCwd;
  #cleanupAuxiliarySessions;
  #sessionStoreRoot;
  #log;
  #control;
  #live = new Map();
  #auxiliaryIds = new Set();
  #cwdCache = new Map();
  #auxiliaryTail;
  #reaper;
  #exitHook;
  #disposed = false;

  /**
   * @param {object} [config] - pool configuration.
   * @param {string} [config.executable] - `omp` executable path (default `OMP_ACP_EXECUTABLE` or `omp`).
   * @param {string[]} [config.args] - argv after the executable (default `["acp"]`).
   * @param {string} [config.cwd] - working directory for spawned agent processes.
   * @param {Record<string, string>} [config.env] - extra environment for spawned agents.
   * @param {number} [config.maxLiveSessions] - concurrently resumed omp sessions before LRU eviction.
   * @param {number} [config.idleTimeoutMs] - idle milliseconds before a resumed session's process is released.
   * @param {number} [config.promptTimeoutMs] - hard deadline for one `session/prompt`.
   * @param {number} [config.cancelGraceMs] - grace period between cancellation and forced release.
   * @param {number} [config.auxiliaryTimeoutMs] - hard deadline for one auxiliary call.
   * @param {"allow" | "reject" | "ask"} [config.permission] - answer policy for agent permission requests.
   * @param {(request: { harnessSessionId: string, toolName: string, reason?: string, signal?: AbortSignal }) => Promise<string>} [config.askPermission] - human decision channel for `permission: "ask"`.
   * @param {string} [config.auxiliaryCwd] - working directory for throwaway auxiliary sessions.
   * @param {boolean} [config.cleanupAuxiliarySessions] - delete the session file of each throwaway session.
   * @param {string} [config.sessionStoreRoot] - oh-my-pi session store root.
   * @param {(level: string, message: string) => void} [config.onLog] - diagnostic sink.
   */
  constructor(config = {}) {
    const executable = config.executable ?? process.env.OMP_ACP_EXECUTABLE ?? "omp";
    if (typeof executable !== "string" || executable.length === 0) throw new TypeError("dsh-omp-acp needs an omp executable path");
    this.#executable = executable;
    this.#args = Array.isArray(config.args) && config.args.length > 0 ? [...config.args] : ["acp"];
    this.#spawnCwd = config.cwd ?? process.cwd();
    this.#env = config.env;
    this.#maxLiveSessions = Number.isFinite(config.maxLiveSessions) ? Math.max(1, config.maxLiveSessions) : DEFAULT_MAX_LIVE_SESSIONS;
    this.#idleTimeoutMs = Number.isFinite(config.idleTimeoutMs) ? Math.max(1_000, config.idleTimeoutMs) : DEFAULT_IDLE_TIMEOUT_MS;
    this.#promptTimeoutMs = Number.isFinite(config.promptTimeoutMs) ? config.promptTimeoutMs : DEFAULT_PROMPT_TIMEOUT_MS;
    this.#cancelGraceMs = Number.isFinite(config.cancelGraceMs) ? Math.max(0, config.cancelGraceMs) : DEFAULT_CANCEL_GRACE_MS;
    this.#auxiliaryTimeoutMs = Number.isFinite(config.auxiliaryTimeoutMs) ? config.auxiliaryTimeoutMs : DEFAULT_AUXILIARY_TIMEOUT_MS;
    this.#permission = config.permission === "ask" ? "ask" : config.permission === "reject" ? "reject" : "allow";
    this.#askPermission = typeof config.askPermission === "function" ? config.askPermission : undefined;
    this.#auxiliaryCwd = config.auxiliaryCwd ?? join(homedir(), ".omp", "acp-auxiliary");
    this.#cleanupAuxiliarySessions = config.cleanupAuxiliarySessions !== false;
    this.#sessionStoreRoot = config.sessionStoreRoot ?? join(homedir(), ".omp", "agent", "sessions");
    this.#log = config.onLog;
    this.#reaper = setInterval(() => this.#reap(), 60_000);
    this.#reaper.unref?.();
    // A harness shutdown that skips ctx.effect teardown must not leave agent
    // processes behind: on Windows an orphaned child outlives its parent.
    this.#exitHook = () => this.dispose();
    process.once("exit", this.#exitHook);
  }

  /** Live-session and control-connection diagnostics. */
  status() {
    return {
      controlAlive: this.#control?.conn.alive === true,
      controlPid: this.#control?.conn.pid,
      agent: this.#control?.agentInfo,
      liveSessions: [...this.#live.entries()].map(([sessionId, runner]) => ({ sessionId, cwd: runner.cwd, pid: runner.conn.pid, lastUsed: new Date(runner.lastUsed).toISOString() })),
      auxiliarySessions: [...this.#auxiliaryIds],
    };
  }

  #write(level, message) {
    try {
      this.#log?.(level, message);
    } catch {
      // Diagnostics never break a session.
    }
  }

  #connection(cwd) {
    const conn = new AcpConnection({ executable: this.#executable, args: this.#args, cwd, env: this.#env });
    conn.setRequestHandler((method, params) => this.#answerRequest(conn, method, params));
    return conn;
  }

  async #answerRequest(conn, method, params) {
    if (method === "session/request_permission") {
      const runner = [...this.#live.values()].find((candidate) => candidate.conn === conn);
      const ask = this.#askPermission === undefined || runner?.ask === undefined
        ? undefined
        : (request) => this.#askPermission({ ...request, harnessSessionId: runner.ask.harnessSessionId, signal: runner.ask.signal });
      const decision = await resolvePermission(params, { policy: this.#permission, ask });
      this.#write("info", `permission answered ${JSON.stringify(decision.reply?.outcome)} for ${JSON.stringify(permissionToolName(params))} (${decision.decidedBy})`);
      if (decision.reply?.outcome?.optionId === undefined) {
        this.#write("warn", `permission request carried no readable option id: ${JSON.stringify(params?.options)}`);
      }
      return decision.reply;
    }
    if (UNSUPPORTED_CLIENT_METHODS.has(method)) {
      throw new AcpTransportError(`the DeepSeek Harness ACP client does not implement ${method}`);
    }
    throw new AcpTransportError(`unsupported agent request ${method}`);
  }

  async #initialize(conn) {
    const result = await conn.request("initialize", { protocolVersion: ACP_PROTOCOL_VERSION, clientCapabilities: {} }, { timeoutMs: 30_000 });
    if (result?.protocolVersion !== ACP_PROTOCOL_VERSION) {
      throw new AcpTransportError(`omp acp negotiated protocol version ${result?.protocolVersion}, expected ${ACP_PROTOCOL_VERSION}`);
    }
    return result;
  }

  /** The shared control connection: lists the session store and hosts auxiliary calls. */
  async #controlConnection() {
    if (this.#disposed) throw new AcpTransportError("the omp session pool is disposed");
    if (this.#control !== undefined) {
      try {
        await this.#control.ready;
        return this.#control;
      } catch {
        this.#control = undefined;
      }
    }
    const conn = this.#connection(this.#spawnCwd);
    conn.start();
    const ready = this.#initialize(conn).then((info) => {
      this.#write("info", `omp acp ready: ${info.agentInfo?.title ?? info.agentInfo?.name ?? "agent"} ${info.agentInfo?.version ?? ""}`.trim());
      return info;
    });
    const control = { conn, ready, agentInfo: undefined };
    this.#control = control;
    try {
      control.agentInfo = await ready;
    } catch (error) {
      if (this.#control === control) this.#control = undefined;
      conn.dispose();
      throw error;
    }
    return control;
  }

  /**
   * List the durable oh-my-pi sessions, newest first.
   *
   * @param {{ signal?: AbortSignal }} [options] - cancellation for the listing.
   * @returns {Promise<Array<{ sessionId: string, cwd: string, title: string, updatedAt: string, messageCount?: number }>>} sessions.
   */
  async listSessions({ signal } = {}) {
    const control = await this.#controlConnection();
    const result = await control.conn.request("session/list", {}, { timeoutMs: 30_000, signal });
    const sessions = [];
    for (const entry of Array.isArray(result?.sessions) ? result.sessions : []) {
      const session = normalizeSession(entry);
      if (session === undefined) continue;
      if (this.#auxiliaryIds.has(session.sessionId)) continue;
      this.#cwdCache.set(session.sessionId, session.cwd);
      sessions.push(session);
    }
    sessions.sort((left, right) => updatedAtMs(right) - updatedAtMs(left));
    return sessions;
  }

  async #cwdFor(sessionId) {
    if (this.#cwdCache.has(sessionId)) return this.#cwdCache.get(sessionId);
    const sessions = await this.listSessions();
    const found = sessions.find((session) => session.sessionId === sessionId);
    if (found === undefined) throw new AcpTransportError(`oh-my-pi has no session ${sessionId}`);
    return found.cwd;
  }

  /**
   * Create one durable oh-my-pi session, which the caller then prompts like any
   * other session. Unlike {@link OmpAcpSessions#auxiliary} this session is a
   * real conversation: it is never closed or deleted by the pool.
   *
   * @param {{ cwd?: string, signal?: AbortSignal }} [options] - creation options.
   * @returns {Promise<{ sessionId: string, cwd: string }>} the created session.
   */
  async createSession({ cwd, signal } = {}) {
    const control = await this.#controlConnection();
    const directory = typeof cwd === "string" && cwd.length > 0 ? cwd : this.#spawnCwd;
    const created = await control.conn.request("session/new", { cwd: directory, mcpServers: [] }, { timeoutMs: 30_000, signal });
    const sessionId = typeof created?.sessionId === "string" && created.sessionId.length > 0 ? created.sessionId : undefined;
    if (sessionId === undefined) throw new AcpTransportError("omp acp session/new returned no session id");
    this.#cwdCache.set(sessionId, directory);
    this.#write("info", `created omp session ${sessionId} (${directory})`);
    return { sessionId, cwd: directory };
  }

  async #runner(sessionId) {
    if (this.#disposed) throw new AcpTransportError("the omp session pool is disposed");
    const existing = this.#live.get(sessionId);
    if (existing !== undefined && existing.conn.alive) {
      await existing.ready;
      return existing;
    }
    if (existing !== undefined) this.#release(sessionId, "agent process exited");
    const conn = this.#connection(this.#spawnCwd);
    conn.start();
    const runner = { sessionId, cwd: undefined, conn, ready: undefined, tail: Promise.resolve(), lastUsed: Date.now(), resumed: undefined };
    runner.ready = (async () => {
      const cwd = await this.#cwdFor(sessionId);
      runner.cwd = cwd;
      await this.#initialize(conn);
      runner.resumed = await conn.request("session/resume", { sessionId, cwd, mcpServers: [] }, { timeoutMs: 120_000 });
      this.#write("info", `resumed omp session ${sessionId} (${cwd})`);
    })();
    this.#live.set(sessionId, runner);
    try {
      await runner.ready;
    } catch (error) {
      if (this.#live.get(sessionId) === runner) this.#live.delete(sessionId);
      conn.dispose();
      throw error;
    }
    return runner;
  }

  #release(sessionId, reason) {
    const runner = this.#live.get(sessionId);
    if (runner === undefined) return;
    this.#live.delete(sessionId);
    this.#write("info", `released omp session ${sessionId} (${reason})`);
    runner.conn.dispose();
  }

  #reap() {
    const now = Date.now();
    for (const [sessionId, runner] of [...this.#live.entries()]) {
      if (now - runner.lastUsed > this.#idleTimeoutMs) this.#release(sessionId, "idle timeout");
    }
    if (this.#live.size <= this.#maxLiveSessions) return;
    const ordered = [...this.#live.entries()].sort((left, right) => left[1].lastUsed - right[1].lastUsed);
    while (ordered.length > 0 && this.#live.size > this.#maxLiveSessions) {
      const [sessionId] = ordered.shift();
      this.#release(sessionId, "live-session limit");
    }
  }

  #enqueue(runner, task) {
    const run = runner.tail.then(task, task);
    runner.tail = run.then(() => undefined, () => undefined);
    return run;
  }

  /**
   * Prompt one oh-my-pi session and stream its updates.
   *
   * @param {object} request - the prompt request.
   * @param {string} request.sessionId - oh-my-pi session id.
   * @param {string} request.text - prompt text.
   * @param {AbortSignal} [request.signal] - cancellation; sends `session/cancel`.
   * @param {string} [request.harnessSessionId] - the requesting harness session, which routes a permission ask to it.
   * @param {(update: object) => void} [request.onUpdate] - receives each `session/update` payload.
   * @returns {Promise<{ stopReason?: string, usage?: object }>} the prompt outcome.
   */
  async prompt({ sessionId, text, signal, harnessSessionId, onUpdate }) {
    const runner = await this.#runner(sessionId);
    this.#reap();
    runner.lastUsed = Date.now();
    runner.ask = typeof harnessSessionId === "string" && harnessSessionId.length > 0 ? { harnessSessionId, signal } : undefined;
    try {
      return await this.#enqueue(runner, () => this.#promptOnConnection(runner.conn, { sessionId, text, signal, onUpdate, timeoutMs: this.#promptTimeoutMs }));
    } catch (error) {
      // A dead agent process must not be reused: the next prompt rebuilds it.
      if (error instanceof AcpTransportError && error.code !== "ABORTED" && this.#live.get(sessionId) === runner) {
        this.#release(sessionId, `prompt failed: ${error.message}`);
      }
      throw error;
    } finally {
      if (runner.ask?.harnessSessionId === harnessSessionId) runner.ask = undefined;
    }
  }

  async #promptOnConnection(conn, { sessionId, text, signal, onUpdate, timeoutMs, auxiliary = false }) {
    const unsubscribe = onUpdate === undefined
      ? undefined
      : conn.onNotification((notification) => {
        if (notification.method !== "session/update") return;
        if (notification.params?.sessionId !== sessionId) return;
        onUpdate(notification.params.update ?? {});
      });
    let cancelled = null;
    const onAbort = () => {
      conn.notify("session/cancel", { sessionId });
      this.#write("info", `sent session/cancel for ${sessionId}`);
      cancelled = setTimeout(() => {
        const error = new AcpTransportError(`omp session ${sessionId} did not stop after cancellation`);
        if (!auxiliary) this.#release(sessionId, "cancellation grace elapsed");
        conn.dispose();
        this.#write("warn", error.message);
      }, this.#cancelGraceMs);
      cancelled.unref?.();
    };
    if (signal?.aborted) onAbort();
    else signal?.addEventListener("abort", onAbort, { once: true });
    try {
      const result = await conn.request("session/prompt", { sessionId, prompt: [{ type: "text", text }] }, { timeoutMs });
      return { stopReason: typeof result?.stopReason === "string" ? result.stopReason : undefined, usage: result?.usage };
    } finally {
      if (cancelled !== null) clearTimeout(cancelled);
      signal?.removeEventListener("abort", onAbort);
      unsubscribe?.();
    }
  }

  /**
   * Run one stateless auxiliary call in a throwaway oh-my-pi session so the
   * user's own sessions never receive harness bookkeeping prompts.
   *
   * @param {object} request - the auxiliary request.
   * @param {string} request.text - flattened request text.
   * @param {AbortSignal} [request.signal] - cancellation.
   * @param {(update: object) => void} [request.onUpdate] - receives each `session/update` payload.
   * @returns {Promise<{ stopReason?: string, usage?: object }>} the call outcome.
   */
  async auxiliary({ text, signal, onUpdate }) {
    const control = await this.#controlConnection();
    const task = async () => {
      const created = await control.conn.request("session/new", { cwd: this.#auxiliaryCwd, mcpServers: [] }, { timeoutMs: 60_000 });
      const sessionId = created?.sessionId;
      if (typeof sessionId !== "string" || sessionId.length === 0) throw new AcpTransportError("omp acp session/new returned no session id");
      this.#auxiliaryIds.add(sessionId);
      try {
        return await this.#promptOnConnection(control.conn, { sessionId, text, signal, onUpdate, timeoutMs: this.#auxiliaryTimeoutMs, auxiliary: true });
      } finally {
        try {
          await control.conn.request("session/close", { sessionId }, { timeoutMs: 30_000 });
        } catch (error) {
          this.#write("warn", `omp acp session/close failed for ${sessionId}: ${error.message}`);
        }
        if (this.#cleanupAuxiliarySessions) this.#deleteSessionFile(sessionId);
      }
    };
    const previous = this.#auxiliaryTail ?? Promise.resolve();
    const run = previous.then(task, task);
    this.#auxiliaryTail = run.then(() => undefined, () => undefined);
    return run;
  }

  /**
   * Delete the durable session file of a throwaway auxiliary session.
   *
   * @param {string} sessionId - the auxiliary session id.
   * @returns {boolean} whether a file was removed.
   */
  #deleteSessionFile(sessionId) {
    const suffix = `_${sessionId}.jsonl`;
    try {
      for (const entry of readdirSync(this.#sessionStoreRoot, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const directory = join(this.#sessionStoreRoot, entry.name);
        for (const file of readdirSync(directory)) {
          if (!file.endsWith(suffix)) continue;
          rmSync(join(directory, file), { force: true });
          this.#write("info", `removed auxiliary omp session file ${file}`);
          return true;
        }
      }
    } catch (error) {
      this.#write("warn", `could not remove auxiliary omp session file for ${sessionId}: ${error.message}`);
    }
    return false;
  }

  /** Stop every spawned agent process. */
  dispose() {
    if (this.#disposed) return;
    this.#disposed = true;
    if (this.#reaper !== undefined) clearInterval(this.#reaper);
    if (this.#exitHook !== undefined) process.off("exit", this.#exitHook);
    for (const sessionId of [...this.#live.keys()]) this.#release(sessionId, "pool disposed");
    this.#control?.conn.dispose();
    this.#control = undefined;
  }
}

export { AUXILIARY_UNAVAILABLE };
