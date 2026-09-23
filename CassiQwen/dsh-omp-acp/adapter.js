/**
 * The oh-my-pi provider adapter: `omp` sessions appear to DeepSeek Harness as
 * selectable models, and one prompt continues that session in place.
 *
 * Every model id this adapter advertises is a durable oh-my-pi session id. A
 * conversation request forwards only its newest user message, because the omp
 * session already owns the history; auxiliary calls (titles, compaction) are
 * stateless and run in a throwaway session so they never touch a real one.
 *
 * One advertised id is not a session: {@link NEW_SESSION_MODEL} asks oh-my-pi
 * for a fresh session on the first message of each harness conversation, then
 * continues the session it created.
 *
 * Tool activity is reported as transcript records rather than as harness
 * tool-call blocks, on purpose: the agent loop dispatches EVERY `tool-call`
 * block an adapter emits (`dsh-agent-loop`: `message.content.filter((block) =>
 * block.type === 'tool-call')` → `executeToolCalls`), so re-emitting oh-my-pi's
 * calls would make the harness execute its own tools a second time with
 * oh-my-pi's arguments. The agent that owns a tool call is the agent that runs
 * it; the harness sees what happened.
 *
 * @module dsh-omp-acp/adapter
 */
import { homedir } from "node:os";
import { join } from "node:path";
import { EMPTY_RESPONSE_CODE, LlmAdapter, LlmError, resolveRetryPolicy } from "@deepseek-ai/dsh-llm";

const DEFAULT_MODEL_LIMIT = 25;
const DEFAULT_MAX_TOKENS = 8_192;
const REQUEST_FAILED_CODE = "REQUEST_FAILED";
const EMPTY_REQUEST_CODE = "EMPTY_REQUEST";

/**
 * Model id that means "start a fresh oh-my-pi session". Chosen so it cannot
 * collide with a session id (oh-my-pi ids are lowercase hex with dashes).
 */
export const NEW_SESSION_MODEL = "new-session";

/** Cap on the tool output kept in one tool record. */
const TOOL_OUTPUT_LIMIT = 1_200;

/** Retry nothing: every attempt re-sends a user message into a live session. */
const NO_RETRY = resolveRetryPolicy({ mode: "normal", maxRetries: 0 }, "dsh-omp-acp");

/** Queue that turns push-style ACP updates into a pull-style async stream. */
class UpdateQueue {
  #items = [];
  #waiter;
  #ended = false;

  /** Add one update. */
  push(item) {
    if (this.#ended) return;
    this.#items.push(item);
    this.#wake();
  }

  /** Mark the producer finished. */
  end() {
    this.#ended = true;
    this.#wake();
  }

  /** Await the next update, or `undefined` once the producer finished. */
  async shift() {
    while (this.#items.length === 0) {
      if (this.#ended) return undefined;
      await new Promise((resolve) => {
        this.#waiter = resolve;
      });
    }
    return this.#items.shift();
  }

  #wake() {
    const waiter = this.#waiter;
    this.#waiter = undefined;
    waiter?.();
  }
}

/** Assembles ACP session updates into the harness streaming chunk protocol. */
class BlockStream {
  #index = -1;
  #type = null;
  #block = null;
  #closed = 0;

  /** Whether the stream produced no content at all. */
  get isEmpty() {
    return this.#closed === 0 && this.#type === null;
  }

  #open(type) {
    if (this.#type === type) return [];
    const chunks = [...this.#close()];
    this.#index += 1;
    this.#type = type;
    this.#block = { type, text: "" };
    chunks.push({ type: "block-start", index: this.#index, blockType: type });
    return chunks;
  }

  #text(text) {
    if (this.#type === null || text.length === 0) return [];
    this.#block.text += text;
    return [{ type: this.#type === "reasoning" ? "reasoning-delta" : "text-delta", index: this.#index, text }];
  }

  #close() {
    if (this.#type === null) return [];
    const index = this.#index;
    const block = this.#block;
    this.#type = null;
    this.#block = null;
    this.#closed += 1;
    return [{ type: "block-end", index, block }];
  }

  /**
   * Translate one ACP session update into harness chunks.
   *
   * @param {object} update - one `session/update` payload.
   * @param {{ toolActivity: boolean }} options - whether tool steps are surfaced as transcript records.
   * @returns {object[]} harness chunks.
   */
  consume(update, { toolActivity }) {
    const kind = update?.sessionUpdate;
    if (kind === "agent_message_chunk") return this.#message(update.content, "text");
    if (kind === "agent_thought_chunk") return this.#message(update.content, "reasoning");
    if (!toolActivity) return [];
    if (kind === "tool_call") return this.#activity(toolRecord(update));
    if (kind === "tool_call_update") {
      const record = toolUpdateRecord(update);
      return record.length === 0 ? [] : this.#activity(record);
    }
    return [];
  }

  /** Every remaining chunk when the response settles. */
  finish() {
    return this.#close();
  }

  #message(content, type) {
    if (content?.type !== "text" || typeof content.text !== "string" || content.text.length === 0) return [];
    return [...this.#open(type), ...this.#text(content.text)];
  }

  #activity(line) {
    return [...this.#open("reasoning"), ...this.#text(line)];
  }
}

function describeTool(update) {
  const title = typeof update.title === "string" && update.title.length > 0 ? update.title : undefined;
  if (title !== undefined) return title;
  if (typeof update.kind === "string" && update.kind.length > 0) return update.kind;
  return "call";
}

/** One-line command/argument summary of a tool call, when the agent disclosed it. */
function toolArgumentSummary(update) {
  const input = update?.rawInput;
  if (input === undefined || input === null) return undefined;
  if (typeof input === "string") return compact(input);
  if (typeof input === "object") {
    for (const key of ["command", "cmd", "file_path", "path", "pattern", "query", "url", "title"]) {
      const value = input[key];
      if (typeof value === "string" && value.length > 0) return compact(value);
    }
    if (Array.isArray(input.command) && input.command.length > 0) return compact(input.command.join(" "));
    try {
      return compact(JSON.stringify(input));
    } catch {
      return undefined;
    }
  }
  return undefined;
}

/** Every text fragment one tool update carries, in order. */
function toolOutputText(update) {
  const parts = [];
  const visit = (value, depth) => {
    if (depth > 4 || value === undefined || value === null) return;
    if (typeof value === "string") return;
    if (Array.isArray(value)) {
      for (const item of value) visit(item, depth + 1);
      return;
    }
    if (typeof value !== "object") return;
    if (typeof value.text === "string" && value.text.length > 0) parts.push(value.text);
    if (typeof value.content === "string" && value.content.length > 0) parts.push(value.content);
    for (const key of ["content", "output", "result", "rawOutput"]) visit(value[key], depth + 1);
  };
  visit(update?.content, 0);
  visit(update?.rawOutput, 0);
  const unique = [...new Set(parts.map((part) => part.trim()).filter((part) => part.length > 0))];
  const joined = compact(unique.join(" ⏎ "));
  if (joined.length === 0) return undefined;
  return joined.length > TOOL_OUTPUT_LIMIT ? `${joined.slice(0, TOOL_OUTPUT_LIMIT)} …` : joined;
}

/** One transcript record for a newly announced tool call. */
export function toolRecord(update) {
  const parts = [`omp tool ${describeTool(update)}`, `(${typeof update.kind === "string" && update.kind.length > 0 ? update.kind : "call"})`];
  const argument = toolArgumentSummary(update);
  if (argument !== undefined) parts.push(`→ ${argument}`);
  return `${parts.join(" ")}\n`;
}

/** One transcript record for a tool call's status change, including its output. */
export function toolUpdateRecord(update) {
  const status = typeof update.status === "string" && update.status.length > 0 ? update.status : "update";
  if (status === "in_progress") return "";
  const lines = [`omp tool ${describeTool(update)}: ${status}`];
  const output = toolOutputText(update);
  if (output !== undefined) lines.push(`  ${output}`);
  return `${lines.join("\n")}\n`;
}

/** Collapse whitespace so one record stays one readable line. */
function compact(text) {
  return text.replace(/\s+/g, " ").trim();
}

/** Visible text of one content block. */
function blockText(block) {
  if (block?.type === "text" && typeof block.text === "string") return block.text;
  if (block?.type === "reasoning" && typeof block.text === "string") return block.text;
  if (block?.type === "tool-call") return `[tool ${block.name ?? "call"}] ${block.arguments ?? ""}`;
  if (block?.type === "tool-result") return (Array.isArray(block.content) ? block.content.map(blockText).join("\n") : "");
  return "";
}

/** Visible text of one message. */
function messageText(message) {
  const blocks = Array.isArray(message?.content) ? message.content : [];
  return blocks.map(blockText).filter((part) => part.length > 0).join("\n");
}

/**
 * Whether one message is a message the user actually sent.
 *
 * A harness request interleaves harness-authored material as user-role
 * messages too — workspace instructions (`agent-instructions`) and plugin
 * runtime snapshots (`plugin`). Those are context for a stateless provider,
 * never an instruction a live session should receive, so only messages with no
 * source or an explicit `user` source are candidates.
 *
 * @param {object} message - one request message.
 * @returns {boolean} whether the message is user-authored.
 */
export function isUserAuthored(message) {
  const kind = message?.source?.kind;
  return kind === undefined || kind === "user";
}

/**
 * The newest user-authored message text, which is the one instruction a
 * session prompt carries.
 *
 * @param {readonly object[]} messages - the assembled request history.
 * @returns {string} trimmed prompt text, empty when the request carries no user text.
 */
export function newestUserText(messages) {
  const list = Array.isArray(messages) ? messages : [];
  for (let index = list.length - 1; index >= 0; index -= 1) {
    if (list[index]?.role !== "user") continue;
    if (!isUserAuthored(list[index])) continue;
    const text = messageText(list[index]).trim();
    if (text.length > 0) return text;
  }
  return "";
}

/**
 * Flatten one stateless request into a single prompt for a throwaway session.
 *
 * @param {object} options - the harness request.
 * @returns {string} role-tagged request text.
 */
export function requestTranscript(options) {
  const parts = [];
  if (typeof options.system === "string" && options.system.trim().length > 0) parts.push(`system:\n${options.system.trim()}`);
  for (const message of Array.isArray(options.messages) ? options.messages : []) {
    if (message?.role === "user" && !isUserAuthored(message)) continue;
    const text = messageText(message).trim();
    if (text.length === 0) continue;
    parts.push(`${message?.role ?? "user"}:\n${text}`);
  }
  return parts.join("\n\n").trim();
}

/**
 * Convert oh-my-pi usage into the harness token vocabulary.
 *
 * oh-my-pi reports `inputTokens` as the whole prompt count with
 * `cachedReadTokens` as the cached part of it, while the harness keeps cached
 * input disjoint from `inputTokens`.
 *
 * @param {object} [usage] - ACP prompt usage.
 * @returns {object | undefined} harness usage, or undefined when unavailable.
 */
export function harnessUsage(usage) {
  if (usage === undefined || usage === null) return undefined;
  const input = Number(usage.inputTokens);
  const output = Number(usage.outputTokens);
  const cached = Number(usage.cachedReadTokens);
  const write = Number(usage.cacheWriteTokens);
  if (!Number.isFinite(input) && !Number.isFinite(output)) return undefined;
  const cachedRead = Number.isFinite(cached) ? cached : 0;
  return {
    inputTokens: Math.max(0, (Number.isFinite(input) ? input : 0) - cachedRead),
    outputTokens: Number.isFinite(output) ? output : 0,
    ...(cachedRead > 0 ? { cacheReadTokens: cachedRead } : {}),
    ...(Number.isFinite(write) && write > 0 ? { cacheWriteTokens: write } : {}),
  };
}

/** Map an ACP stop reason onto the harness finish reason. */
function finishReason(stopReason) {
  return stopReason === "max_tokens" ? { kind: "max-tokens" } : { kind: "stop" };
}

/** The oh-my-pi provider adapter. */
export class OmpAcpAdapter extends LlmAdapter {
  #sessions;
  #providerName;
  #modelLimit;
  #maxTokens;
  #auxiliary;
  #toolActivity;
  #newSession;
  #newSessionCwd;
  #newSessionName;
  #newSessions = new Map();

  /**
   * @param {import("./omp-sessions.js").OmpAcpSessions} sessions - the session pool.
   * @param {object} [config] - adapter configuration.
   * @param {string} [config.providerName] - display name for the provider route.
   * @param {number} [config.maxModels] - sessions advertised in the model list.
   * @param {number} [config.defaultMaxTokens] - per-request output cap materialized when the caller omits one.
   * @param {"ephemeral" | "local"} [config.auxiliary] - auxiliary call strategy.
   * @param {boolean} [config.toolActivity] - surface tool steps as transcript records (default true).
   * @param {boolean} [config.newSession] - advertise {@link NEW_SESSION_MODEL} (default true).
   * @param {string} [config.newSessionCwd] - working directory a fresh session starts in.
   * @param {string} [config.newSessionName] - picker label of the fresh-session entry.
   */
  constructor(sessions, config = {}) {
    super();
    if (sessions === undefined || sessions === null) throw new TypeError("OmpAcpAdapter needs a session pool");
    this.#sessions = sessions;
    this.#providerName = typeof config.providerName === "string" && config.providerName.length > 0 ? config.providerName : "Oh My Pi";
    this.#modelLimit = Number.isFinite(config.maxModels) ? Math.max(1, config.maxModels) : DEFAULT_MODEL_LIMIT;
    this.#maxTokens = Number.isFinite(config.defaultMaxTokens) ? config.defaultMaxTokens : DEFAULT_MAX_TOKENS;
    this.#auxiliary = config.auxiliary === "local" ? "local" : "ephemeral";
    this.#toolActivity = config.toolActivity !== false;
    this.#newSession = config.newSession !== false;
    this.#newSessionCwd = typeof config.newSessionCwd === "string" && config.newSessionCwd.length > 0 ? config.newSessionCwd : process.cwd();
    this.#newSessionName = typeof config.newSessionName === "string" && config.newSessionName.length > 0 ? config.newSessionName : "New oh-my-pi session";
  }

  /** @param {string} provider - the registered route. */
  providerInfo(provider) {
    return { id: provider, name: this.#providerName };
  }

  /** @param {string} _provider - the registered route. */
  providerRetryPolicy(_provider) {
    return NO_RETRY;
  }

  /**
   * Advertise the durable oh-my-pi sessions, newest first.
   *
   * @param {string} provider - the registered route.
   * @returns {Promise<object[]>} one model entry per session.
   */
  async listModels(provider) {
    const sessions = await this.#sessions.listSessions();
    const models = sessions
      .filter((session) => session.messageCount === undefined || session.messageCount > 0)
      .slice(0, this.#modelLimit)
      .map((session) => modelInfo(provider, session));
    if (this.#newSession) models.unshift(this.#newSessionModel(provider));
    return models;
  }

  /** The picker entry that starts a fresh oh-my-pi session. */
  #newSessionModel(provider) {
    return {
      provider,
      id: NEW_SESSION_MODEL,
      name: this.#newSessionName,
      description: `start a fresh oh-my-pi session in ${this.#newSessionCwd}`,
      inputModalities: ["text"],
    };
  }

  /**
   * Describe one exact session model.
   *
   * @param {string} provider - the registered route.
   * @param {string} model - an oh-my-pi session id.
   * @param {AbortSignal} [signal] - cancellation for the lookup.
   * @returns {Promise<object>} resolved model metadata.
   */
  async resolveModel(provider, model, signal) {
    if (model === NEW_SESSION_MODEL) {
      return {
        provider,
        id: model,
        name: this.#newSessionName,
        description: `start a fresh oh-my-pi session in ${this.#newSessionCwd}`,
        inputModalities: ["text"],
        defaultMaxTokens: this.#maxTokens,
      };
    }
    let session;
    try {
      const sessions = await this.#sessions.listSessions({ signal });
      session = sessions.find((candidate) => candidate.sessionId === model);
    } catch (error) {
      if (signal?.aborted) throw error;
      session = undefined;
    }
    return {
      provider,
      id: model,
      name: session === undefined ? `omp session ${model}` : modelName(session),
      description: session === undefined ? "oh-my-pi session (not in the current listing)" : modelDescription(session),
      inputModalities: ["text"],
      defaultMaxTokens: this.#maxTokens,
    };
  }

  /**
   * Stream one prompt through the selected oh-my-pi session.
   *
   * @param {object} options - the harness request.
   * @returns {AsyncIterable<object>} harness stream chunks.
   */
  async *stream(options) {
    const provider = options?.provider ?? "omp";
    const model = options?.model;
    if (typeof model !== "string" || model.length === 0) {
      throw new LlmError("dsh-omp-acp needs a session id as its model", EMPTY_REQUEST_CODE);
    }
    if (options.purpose === "compaction" || options.purpose === "session-title") {
      yield* this.#auxiliaryStream(options);
      return;
    }
    const text = newestUserText(options.messages);
    if (text.length === 0) {
      throw new LlmError("dsh-omp-acp requires a non-empty newest user message", EMPTY_REQUEST_CODE);
    }
    const sessionId = model === NEW_SESSION_MODEL
      ? await this.#freshSession(options.sessionId)
      : model;
    yield* this.#sessionStream({
      provider,
      sessionId,
      text,
      signal: options.signal,
      harnessSessionId: options.sessionId,
    });
  }

  /**
   * The oh-my-pi session one harness conversation owns, creating it on the
   * first message: the mapping makes "start a fresh session" a one-time act
   * per conversation. A conversation that cannot be identified creates a
   * session for that message alone rather than mixing two histories. The
   * mapping lives in memory, so a restarted bridge starts fresh sessions —
   * which is what asking for a fresh session means.
   *
   * @param {string | undefined} harnessSessionId - the harness conversation key.
   * @returns {Promise<string>} the oh-my-pi session id to prompt.
   */
  async #freshSession(harnessSessionId) {
    if (typeof harnessSessionId !== "string" || harnessSessionId.length === 0) {
      const created = await this.#sessions.createSession({ cwd: this.#newSessionCwd });
      return created.sessionId;
    }
    const known = this.#newSessions.get(harnessSessionId);
    if (known !== undefined) return known;
    const created = await this.#sessions.createSession({ cwd: this.#newSessionCwd });
    this.#newSessions.set(harnessSessionId, created.sessionId);
    return created.sessionId;
  }

  async *#sessionStream({ provider, sessionId, text, signal, harnessSessionId }) {
    const queue = new UpdateQueue();
    let outcome;
    let failure;
    const pending = Promise.resolve()
      .then(() => this.#sessions.prompt({ sessionId, text, signal, harnessSessionId, onUpdate: (update) => queue.push(update) }))
      .then(
        (result) => {
          outcome = result;
        },
        (error) => {
          failure = error;
        },
      )
      .finally(() => queue.end());
    const stream = new BlockStream();
    while (true) {
      const update = await queue.shift();
      if (update === undefined) break;
      for (const chunk of stream.consume(update, { toolActivity: this.#toolActivity })) yield chunk;
    }
    await pending;
    if (failure !== undefined) throw this.#failure(provider, sessionId, failure);
    if (signal?.aborted) throw new LlmError(`omp session ${sessionId} was cancelled`, "ABORTED");
    if (stream.isEmpty) {
      throw new LlmError(`omp session ${sessionId} produced no assistant content`, EMPTY_RESPONSE_CODE);
    }
    for (const chunk of stream.finish()) yield chunk;
    yield { type: "usage", usage: harnessUsage(outcome?.usage) ?? { inputTokens: 0, outputTokens: 0 } };
    yield { type: "finish", reason: finishReason(outcome?.stopReason) };
  }

  async *#auxiliaryStream(options) {
    const transcript = requestTranscript(options);
    if (transcript.length === 0) {
      throw new LlmError("dsh-omp-acp auxiliary request carried no content", EMPTY_REQUEST_CODE);
    }
    if (this.#auxiliary === "local") {
      const text = localAnswer(options, transcript);
      yield { type: "block-start", index: 0, blockType: "text" };
      yield { type: "text-delta", index: 0, text };
      yield { type: "block-end", index: 0, block: { type: "text", text } };
      yield { type: "usage", usage: { inputTokens: 0, outputTokens: 0 } };
      yield { type: "finish", reason: { kind: "stop" } };
      return;
    }
    const queue = new UpdateQueue();
    let outcome;
    let failure;
    const pending = Promise.resolve()
      .then(() => this.#sessions.auxiliary({ text: transcript, signal: options.signal, onUpdate: (update) => queue.push(update) }))
      .then(
        (result) => {
          outcome = result;
        },
        (error) => {
          failure = error;
        },
      )
      .finally(() => queue.end());
    const stream = new BlockStream();
    while (true) {
      const update = await queue.shift();
      if (update === undefined) break;
      for (const chunk of stream.consume(update, { toolActivity: false })) yield chunk;
    }
    await pending;
    if (failure !== undefined) throw this.#failure(options.provider, options.purpose ?? "auxiliary", failure);
    if (options.signal?.aborted) throw new LlmError("omp auxiliary call was cancelled", "ABORTED");
    if (stream.isEmpty) {
      throw new LlmError("omp auxiliary call produced no content", EMPTY_RESPONSE_CODE);
    }
    for (const chunk of stream.finish()) yield chunk;
    yield { type: "usage", usage: harnessUsage(outcome?.usage) ?? { inputTokens: 0, outputTokens: 0 } };
    yield { type: "finish", reason: finishReason(outcome?.stopReason) };
  }

  #failure(provider, model, error) {
    if (error instanceof LlmError) return error;
    const message = error instanceof Error ? error.message : String(error);
    return new LlmError(`omp acp ${provider}/${model} failed: ${message}`, REQUEST_FAILED_CODE, { cause: error });
  }
}

function modelName(session) {
  const title = session.title.trim();
  return title.length > 0 ? title : "(untitled omp session)";
}

function modelDescription(session) {
  const parts = [];
  if (session.cwd.length > 0) parts.push(session.cwd);
  if (session.updatedAt.length > 0) parts.push(`updated ${session.updatedAt}`);
  return parts.join(" · ");
}

function modelInfo(provider, session) {
  return {
    provider,
    id: session.sessionId,
    name: modelName(session),
    description: modelDescription(session),
    inputModalities: ["text"],
  };
}

/** Deterministic answer for `auxiliary: "local"`, which makes no model call. */
function localAnswer(options, transcript) {
  if (options.purpose === "session-title") {
    const first = transcript.split("\n").filter((line) => line.trim().length > 0).at(-1) ?? "omp session";
    const title = first.replace(/\s+/g, " ").trim().slice(0, 80);
    return title.length > 0 ? title : "omp session";
  }
  return transcript.slice(0, 4_000);
}
