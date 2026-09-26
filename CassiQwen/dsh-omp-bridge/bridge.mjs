#!/usr/bin/env node
/**
 * DeepSeek Harness sessions, selectable as models in oh-my-pi — the reverse of
 * `dsh-omp-acp`.
 *
 * A small OpenAI-compatible server:
 *
 *   GET  /v1/models              every live harness session, plus `new`
 *   POST /v1/chat/completions    one user turn in that session, streamed back
 *   GET  /health
 *
 * One request sends the newest user message into the harness session and
 * streams the assistant's own answer back out. The session keeps its history,
 * its workspace, its tools and its agent — this server owns no conversation
 * state beyond remembering which harness session a `new` conversation created.
 *
 * The bridge also answers the harness's *approval* questions, so a session
 * driven from oh-my-pi can run a tool that needs consent without a browser
 * open. The harness pushes `approval/requested` frames to every event feed and
 * replays them to a feed that opens while one is pending; the bridge decides
 * (policy, or the console) and posts the answer back against the frame's own
 * `rpcId`. Only sessions this bridge has served are answered, so a browser
 * session's questions stay with the browser.
 *
 * Nothing about the harness session's own system prompt, tools, or compaction
 * is simulated here: they belong to the harness.
 */
import { createServer } from "node:http";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";
import { DshWire, DshWireError } from "./dsh-wire.mjs";

/** Model id that asks the bridge for a fresh harness session. */
export const NEW_SESSION_MODEL = "new";
/** How many `new` conversations keep their created session. */
const NEW_SESSION_MEMORY = 64;
/** How many session logs a listing reads titles from at once. */
const TITLE_READ_CONCURRENCY = 4;
const MAX_BODY_BYTES = 8 * 1024 * 1024;

/** How the bridge answers a harness approval question. */
export const APPROVAL_POLICIES = ["allow", "reject", "ask"];
/** Which sessions' approvals the bridge answers. */
export const APPROVAL_SCOPES = ["bridge", "all"];

/**
 * The console decider for `--approval ask`: print the question, read one line,
 * and fall back to `onTimeout` when nobody answers in time or stdin is not a
 * terminal (a piped stdin must not hang a turn).
 *
 * @param {object} question - `{sessionId, toolName, reason}`.
 * @param {{timeoutMs: number, onTimeout: "allowed-once" | "rejected", alwaysAllow: Set<string>, log: (level: string, message: string) => void}} context
 * @returns {Promise<"allowed-once" | "rejected">}
 */
export async function askOnConsole(question, { timeoutMs, onTimeout, alwaysAllow, log }) {
  if (alwaysAllow.has(question.toolName)) return "allowed-once";
  const detail = question.reason === undefined ? "" : ` — ${question.reason}`;
  const prompt = `[bridge approval] session ${question.sessionId} wants to run "${question.toolName}"${detail}\n  allow once? [y]es / [a]lways for this tool / [N]o: `;
  if (process.stdin.isTTY !== true) {
    log("warn", `approval for "${question.toolName}" in ${question.sessionId} has no terminal to ask on → ${onTimeout}`);
    return onTimeout;
  }
  const { createInterface } = await import("node:readline");
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  return await new Promise((resolve) => {
    let settled = false;
    const finish = (outcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rl.close();
      resolve(outcome);
    };
    const timer = setTimeout(() => {
      process.stderr.write("\n");
      log("warn", `approval for "${question.toolName}" in ${question.sessionId} timed out after ${timeoutMs} ms → ${onTimeout}`);
      finish(onTimeout);
    }, timeoutMs);
    rl.question(prompt, (answer) => {
      const choice = String(answer ?? "").trim().toLowerCase();
      if (choice === "a" || choice === "always") {
        alwaysAllow.add(question.toolName);
        finish("allowed-once");
        return;
      }
      finish(choice === "y" || choice === "yes" ? "allowed-once" : "rejected");
    });
  });
}

/** @param {unknown} value @returns {string | undefined} */
const asText = (value) => (typeof value === "string" && value.length > 0 ? value : undefined);

/**
 * A picker-safe slug for a session title. oh-my-pi names a discovered model
 * after its id — a `name` field on the wire is overwritten — so a readable row
 * means a readable id, and the id has to stay resolvable.
 */
export function titleSlug(title, maxLength = 48) {
  return String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+/, "")
    .slice(0, maxLength)
    .replace(/-+$/, "");
}

/** The short fragment that carries a session's identity inside a decorated id. */
export function sessionFragment(sessionId) {
  const bare = sessionId.startsWith("session-") ? sessionId.slice("session-".length) : sessionId;
  return bare.replace(/[^a-z0-9]/gi, "").slice(0, 8).toLowerCase();
}

/** The text of an OpenAI message content field (string or part array). */
function messageText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return undefined;
  const parts = content.map((part) => asText(part?.text) ?? asText(part?.content)).filter((text) => text !== undefined);
  return parts.length > 0 ? parts.join("\n") : undefined;
}

/** The newest user-authored message text in an OpenAI request. */
function latestUserText(messages) {
  if (!Array.isArray(messages)) return undefined;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role !== "user") continue;
    const text = messageText(message.content);
    if (text !== undefined) return text;
  }
  return undefined;
}

/** Read and parse a JSON request body, with a byte ceiling. */
async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new DshWireError(`request body larger than ${MAX_BODY_BYTES} bytes`);
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  if (text.trim().length === 0) return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new DshWireError(`request body is not JSON: ${error?.message ?? error}`);
  }
}

function sendJson(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "content-length": Buffer.byteLength(payload) });
  response.end(payload);
}

function sendError(response, status, message, type = "invalid_request_error") {
  sendJson(response, status, { error: { message, type, code: null, param: null } });
}

/**
 * @param {object} options
 * @param {string} options.harnessUrl - harness origin, e.g. `http://127.0.0.1:8787`.
 * @param {string} [options.cwd] - workspace a `new` session is created in.
 * @param {number} [options.turnTimeoutMs] - budget for one whole turn.
 * @param {"allow" | "reject" | "ask"} [options.approval] - how harness approval questions are answered.
 * @param {"bridge" | "all"} [options.approvalScope] - answer only sessions this bridge serves, or every session on the harness.
 * @param {number} [options.approvalTimeoutMs] - how long `ask` waits for a console answer.
 * @param {"allowed-once" | "rejected"} [options.approvalOnTimeout] - `ask`'s fallback when nobody answers.
 * @param {(question: object, context: object) => Promise<"allowed-once" | "rejected">} [options.ask] - the `ask` decider (defaults to the console).
 * @param {(level: "info" | "debug" | "warn", message: string) => void} [options.log]
 */
export function createBridge({
  harnessUrl,
  cwd = process.cwd(),
  turnTimeoutMs = 900_000,
  approval = "ask",
  approvalScope = "bridge",
  approvalTimeoutMs = 120_000,
  approvalOnTimeout = "rejected",
  ask,
  log = () => {},
} = {}) {
  const wire = new DshWire({ baseUrl: harnessUrl });
  /** @type {Map<string, string>} conversation key → harness session id */
  const newSessions = new Map();
  /** Sessions this bridge has driven a turn for — the default approval scope. */
  const servedSessions = new Set();
  /** @type {Map<string, Array<{at: number, text: string}>>} sessionId → decisions awaiting a turn to ride out on. */
  const approvalNotes = new Map();
  /** Tools a console answer allowed for the rest of this run. */
  const alwaysAllow = new Set();
  /** @type {Map<string, {title: string | undefined, at: number}>} sessionId → title, with the log position it was read at. */
  const titles = new Map();
  /** @type {Map<string, string>} advertised model id → session id, from the last listing. */
  const advertised = new Map();
  /** @type {Set<string>} session ids the last listing served bare. */
  const knownSessions = new Set();
  let stopped = false;
  let feed;
  let reconnectTimer;

  /** The harness session a request should be answered from. */
  async function resolveSession(model, body, headers) {
    if (model === NEW_SESSION_MODEL) {
      // A conversation is named by the `x-dsh-session` header or the standard
      // `user` field; a client that names none shares the one scratch session,
      // which is what oh-my-pi itself does.
      const key = asText(headers["x-dsh-session"]) ?? asText(body?.user) ?? "default";
      const existing = newSessions.get(key);
      if (existing !== undefined) return { sessionId: existing, created: false, key };
      const created = await wire.createSession({ cwd });
      if (typeof created?.sessionId !== "string") throw new DshWireError(`the harness did not return a session id: ${JSON.stringify(created)}`);
      newSessions.set(key, created.sessionId);
      while (newSessions.size > NEW_SESSION_MEMORY) newSessions.delete(newSessions.keys().next().value);
      log("info", `new harness session ${created.sessionId} for conversation ${JSON.stringify(key)}`);
      return { sessionId: created.sessionId, created: true, key };
    }
    if (advertised.has(model)) return { sessionId: advertised.get(model), created: false, key: undefined };
    if (knownSessions.has(model)) return { sessionId: model, created: false, key: undefined };
    // A decorated id from an earlier listing (the session was renamed, or the
    // bridge restarted): its trailing fragment still names the session.
    const fragment = model.includes("-") ? model.slice(model.lastIndexOf("-") + 1) : model;
    if (/^[a-z0-9]{4,}$/i.test(fragment)) {
      const sessions = await wire.listSessions();
      const hit = sessions.find((session) => sessionFragment(String(session.sessionId)) === fragment.toLowerCase());
      if (hit !== undefined) {
        log("debug", `model ${model} resolved to session ${hit.sessionId} by fragment`);
        return { sessionId: String(hit.sessionId), created: false, key: undefined };
      }
    }
    return { sessionId: model, created: false, key: undefined };
  }

  /** The title the session's own log carries, read once per log position. */
  async function titleFor(session) {
    const sessionId = String(session.sessionId);
    const cached = titles.get(sessionId);
    const updatedAt = Number(session.updatedAt ?? 0);
    if (cached !== undefined && cached.at >= updatedAt) return cached.title;
    const history = await wire.call("session.history", { sessionId }).catch((error) => {
      log("debug", `could not read the title of ${sessionId}: ${error?.message ?? error}`);
      return undefined;
    });
    const events = Array.isArray(history?.events) ? history.events : [];
    let title;
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const event = events[index]?.event ?? events[index];
      if (event?.type === "session/title" && typeof event.data?.title === "string") {
        title = event.data.title;
        break;
      }
    }
    titles.set(sessionId, { title, at: updatedAt });
    return title;
  }

  /** The model id a session is advertised under: its title when it has one. */
  function modelIdFor(session, title) {
    const slug = titleSlug(title);
    const sessionId = String(session.sessionId);
    return slug.length === 0 ? sessionId : `${slug}-${sessionFragment(sessionId)}`;
  }

  /** Record one decision so the turn that raised it carries the outcome. */
  function noteApproval(sessionId, text) {
    const notes = approvalNotes.get(sessionId) ?? [];
    notes.push({ at: Date.now(), text });
    approvalNotes.set(sessionId, notes);
  }

  /** Take the notes raised during a turn; older ones stay for their own turn. */
  function drainApprovalNotes(sessionId, since) {
    const notes = approvalNotes.get(sessionId) ?? [];
    const taken = notes.filter((note) => note.at >= since);
    const kept = notes.filter((note) => note.at < since);
    if (kept.length > 0) approvalNotes.set(sessionId, kept);
    else approvalNotes.delete(sessionId);
    return taken.map((note) => note.text);
  }

  /** Apply the configured policy to one question. */
  async function decideApproval(question) {
    if (approval === "allow") return "allowed-once";
    if (approval === "reject") return "rejected";
    const decider = ask ?? askOnConsole;
    return await decider(question, { timeoutMs: approvalTimeoutMs, onTimeout: approvalOnTimeout, alwaysAllow, log });
  }

  /** Answer one `approval/requested` frame and record what was decided. */
  async function answerApproval({ rpcId, payload }) {
    const question = {
      sessionId: String(payload.sessionId),
      approvalId: String(payload.approvalId),
      toolName: String(payload.toolName),
      callId: payload.callId,
      reason: payload.reason,
    };
    if (approvalScope === "bridge" && !servedSessions.has(question.sessionId)) {
      log("debug", `approval for "${question.toolName}" in ${question.sessionId} is outside this bridge's scope — leaving it to another client`);
      return;
    }
    const outcome = await decideApproval(question);
    const receipt = await wire.respond({ rpcId, sessionId: question.sessionId, approvalId: question.approvalId, outcome });
    const settled = receipt?.accepted === true ? outcome : `unanswered (${receipt?.reason ?? "unknown"})`;
    log("info", `approval ${settled} for "${question.toolName}" in ${question.sessionId}${question.reason === undefined ? "" : ` (${question.reason})`}`);
    if (receipt?.accepted === true) {
      noteApproval(question.sessionId, `[bridge: harness approval ${outcome} for ${question.toolName}${question.reason === undefined ? "" : ` — ${question.reason}`}]`);
    }
  }

  /** Open (or reopen) the feed that carries the harness's questions. */
  function openQuestionFeed() {
    feed = wire.subscribe({
      onEvent: ({ sessionId, event }) => {
        // A title change is cheaper to keep than to re-read: remember it, and
        // let the log position decide when a real read wins.
        if (event?.type === "session/title" && typeof event.data?.title === "string") titles.set(sessionId, { title: event.data.title, at: Date.now() });
      },
      onServerRequest: (frame) => {
        if (frame.payload?.type !== "approval/requested") {
          log("debug", `ignoring harness question ${frame.payload?.type}`);
          return;
        }
        answerApproval(frame).catch((error) => log("warn", `could not answer the approval in ${frame.payload?.sessionId}: ${error?.message ?? error}`));
      },
      onError: (error) => {
        log("warn", `question feed: ${error?.message ?? error}`);
        scheduleReconnect();
      },
    });
    feed.ready.catch((error) => {
      log("warn", `question feed did not open: ${error?.message ?? error}`);
      scheduleReconnect();
    });
  }

  /** A dropped feed must not silently turn every later approval into "unavailable". */
  function scheduleReconnect() {
    if (stopped || reconnectTimer !== undefined) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined;
      if (!stopped) openQuestionFeed();
    }, 2_000);
    reconnectTimer.unref?.();
  }

  /** One complete turn, streamed through `onDelta`, carrying any approval decision with it. */
  async function runTurn({ sessionId, text, onDelta }) {
    servedSessions.add(sessionId);
    const startedAt = Date.now();
    const turn = await wire.runTurn({ sessionId, text, onDelta, timeoutMs: turnTimeoutMs });
    const notes = drainApprovalNotes(sessionId, startedAt);
    if (notes.length === 0) return turn;
    const note = `\n\n${notes.join("\n")}`;
    onDelta?.(note);
    return { ...turn, text: `${turn.text}${note}`, approvalNotes: notes };
  }

  openQuestionFeed();

  const server = createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    const path = url.pathname.replace(/\/+$/, "") || "/";
    try {
      if (request.method === "GET" && path === "/health") {
        const sessions = await wire.listSessions();
        sendJson(response, 200, { ok: true, harness: wire.baseUrl, sessions: sessions.length });
        return;
      }
      if (request.method === "GET" && (path === "/v1/models" || path === "/models")) {
        const sessions = await wire.listSessions();
        const created = Math.floor(Date.now() / 1000);
        // Titles live in each session's own log, so a listing reads them once
        // per log position — a few at a time, since a long session's history
        // is not small.
        const titled = [];
        for (let index = 0; index < sessions.length; index += TITLE_READ_CONCURRENCY) {
          const slice = sessions.slice(index, index + TITLE_READ_CONCURRENCY);
          titled.push(...(await Promise.all(slice.map(async (session) => ({ session, title: await titleFor(session) })))));
        }
        advertised.clear();
        knownSessions.clear();
        const rows = titled.map(({ session, title }) => {
          const sessionId = String(session.sessionId);
          const id = modelIdFor(session, title);
          advertised.set(id, sessionId);
          knownSessions.add(sessionId);
          return {
            id,
            object: "model",
            created: Math.floor(Number(session.updatedAt ?? Date.now()) / 1000),
            owned_by: "dsh",
          };
        });
        sendJson(response, 200, {
          object: "list",
          data: [{ id: NEW_SESSION_MODEL, object: "model", created, owned_by: "dsh" }, ...rows],
        });
        return;
      }
      if (request.method === "POST" && (path === "/v1/chat/completions" || path === "/chat/completions")) {
        const body = await readJsonBody(request);
        const model = asText(body?.model);
        if (model === undefined) {
          sendError(response, 400, "no model was named");
          return;
        }
        const text = latestUserText(body?.messages);
        if (text === undefined) {
          sendError(response, 400, "the request carried no user message text");
          return;
        }
        const { sessionId, created } = await resolveSession(model, body, request.headers);
        const stream = body?.stream !== false;
        const id = `chatcmpl-${randomUUID()}`;
        const created_ = Math.floor(Date.now() / 1000);
        log("debug", `${stream ? "stream" : "answer"} model=${model} session=${sessionId}${created ? " (created)" : ""} chars=${text.length} keys=${Object.keys(body ?? {}).join(",")}`);

        if (!stream) {
          const turn = await runTurn({ sessionId, text });
          sendJson(response, 200, {
            id,
            object: "chat.completion",
            created: created_,
            model,
            choices: [{ index: 0, message: { role: "assistant", content: turn.text }, finish_reason: "stop" }],
            usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
          });
          return;
        }

        response.writeHead(200, {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          connection: "keep-alive",
          "x-accel-buffering": "no",
        });
        const send = (chunk) => response.write(`data: ${JSON.stringify(chunk)}\n\n`);
        const envelope = (delta, finish) => ({ id, object: "chat.completion.chunk", created: created_, model, choices: [{ index: 0, delta, finish_reason: finish }] });
        send(envelope({ role: "assistant", content: "" }, null));
        let closed = false;
        request.on("close", () => {
          closed = true;
        });
        try {
          const turn = await runTurn({
            sessionId,
            text,
            onDelta: (delta) => {
              if (!closed) send(envelope({ content: delta }, null));
            },
          });
          if (closed) return;
          send(envelope({}, "stop"));
          if (body?.stream_options?.include_usage === true) {
            send({ id, object: "chat.completion.chunk", created: created_, model, choices: [], usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 } });
          }
          response.write("data: [DONE]\n\n");
          response.end();
        } catch (error) {
          log("warn", `turn in ${sessionId} failed: ${error?.message ?? error}`);
          if (!closed) {
            send({ error: { message: String(error?.message ?? error), type: "upstream_error" } });
            response.write("data: [DONE]\n\n");
            response.end();
          }
        }
        return;
      }
      sendError(response, 404, `no such route: ${request.method} ${path}`, "not_found_error");
    } catch (error) {
      const status = error instanceof DshWireError && /unknown session|not found/i.test(String(error.message)) ? 404 : 502;
      log("warn", `${request.method} ${path} failed: ${error?.message ?? error}`);
      if (!response.headersSent) sendError(response, status, String(error?.message ?? error), status === 404 ? "invalid_request_error" : "upstream_error");
      else response.end();
    }
  });

  server.on("clientError", (error, socket) => {
    log("warn", `client error: ${error?.message ?? error}`);
    socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
  });

  /** Stop answering questions and close the feed. */
  function stop() {
    stopped = true;
    if (reconnectTimer !== undefined) clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
    feed?.close();
  }

  return { server, wire, harnessUrl: wire.baseUrl, newSessions, servedSessions, stop };
}

/** Start the bridge and resolve once it is listening. */
export async function startBridge({ host = "127.0.0.1", port = 8791, harnessUrl, cwd, turnTimeoutMs, approval, approvalScope, approvalTimeoutMs, approvalOnTimeout, ask, log } = {}) {
  if (harnessUrl === undefined) throw new DshWireError("--dsh <harness url> is required, e.g. --dsh http://127.0.0.1:8787");
  const bridge = createBridge({ harnessUrl, cwd, turnTimeoutMs, approval, approvalScope, approvalTimeoutMs, approvalOnTimeout, ask, log });
  await new Promise((resolve, reject) => {
    bridge.server.once("error", reject);
    bridge.server.listen(port, host, resolve);
  });
  const address = bridge.server.address();
  const url = `http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${address.port}`;
  bridge.url = url;
  bridge.close = () => new Promise((resolve) => {
    bridge.stop();
    bridge.server.close(resolve);
  });
  return bridge;
}

function parseArgs(argv) {
  const options = { host: "127.0.0.1", port: 8791, logLevel: "info" };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const next = () => {
      const value = argv[index + 1];
      if (value === undefined) throw new Error(`${flag} needs a value`);
      index += 1;
      return value;
    };
    if (flag === "--dsh") options.harnessUrl = next();
    else if (flag === "--host") options.host = next();
    else if (flag === "--port") options.port = Number(next());
    else if (flag === "--cwd") options.cwd = next();
    else if (flag === "--timeout-ms") options.turnTimeoutMs = Number(next());
    else if (flag === "--approval") {
      const value = next();
      if (!APPROVAL_POLICIES.includes(value)) throw new Error(`--approval must be one of ${APPROVAL_POLICIES.join(", ")}`);
      options.approval = value;
    } else if (flag === "--approval-scope") {
      const value = next();
      if (!APPROVAL_SCOPES.includes(value)) throw new Error(`--approval-scope must be one of ${APPROVAL_SCOPES.join(", ")}`);
      options.approvalScope = value;
    } else if (flag === "--approval-timeout-ms") options.approvalTimeoutMs = Number(next());
    else if (flag === "--approval-on-timeout") {
      const value = next();
      if (value !== "allow" && value !== "reject") throw new Error("--approval-on-timeout must be allow or reject");
      options.approvalOnTimeout = value === "allow" ? "allowed-once" : "rejected";
    } else if (flag === "--log-level") options.logLevel = next();
    else if (flag === "--help" || flag === "-h") options.help = true;
    else throw new Error(`unknown flag ${flag}`);
  }
  return options;
}

const HELP = `dsh-omp-bridge — harness sessions as oh-my-pi models

  node bridge.mjs --dsh <harness url> [--host 127.0.0.1] [--port 8791]
                  [--cwd <dir>] [--timeout-ms 900000] [--log-level info|debug|silent]
                  [--approval ask|allow|reject] [--approval-scope bridge|all]
                  [--approval-timeout-ms 120000] [--approval-on-timeout reject|allow]

  --dsh         harness webserver origin, e.g. http://127.0.0.1:8787
  --port        0 lets the OS pick a free port
  --cwd         workspace a "new" session is created in (default: current dir)
  --approval    how a tool call that needs consent is answered: ask on this
                console (default), always allow once, or always reject
  --approval-scope
                bridge (default) answers only sessions this bridge drives;
                all answers every session on the harness, including a browser's
  --approval-on-timeout
                what an unanswered console prompt means (default reject: a
                question nobody answered is not a yes)
`;

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const options = parseArgs(process.argv.slice(2));
  if (options.help === true) {
    process.stdout.write(HELP);
    process.exit(0);
  }
  const level = { silent: 0, info: 1, debug: 2 }[options.logLevel] ?? 1;
  const log = (kind, message) => {
    const rank = kind === "debug" ? 2 : kind === "info" ? 1 : 0;
    if (rank > level) return;
    process.stderr.write(`[bridge ${kind}] ${message}\n`);
  };
  const bridge = await startBridge({ ...options, log });
  process.stdout.write(`dsh-omp-bridge listening on ${bridge.url} → harness ${bridge.harnessUrl}\n`);
  const stop = () => void bridge.close().then(() => process.exit(0));
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
}
