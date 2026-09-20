import { createHash } from "node:crypto";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);
const MAX_MESSAGE_BYTES = 24_000;
const MAX_EVIDENCE_BYTES = 16_384;

function assertLoopbackUrl(raw) {
  const url = new URL(raw);
  if (url.protocol !== "http:" || !LOOPBACK_HOSTS.has(url.hostname)) {
    throw new Error("Cassi entity URL must be an HTTP loopback origin");
  }
  url.pathname = url.pathname.replace(/\/$/, "");
  if (url.search || url.hash) throw new Error("Cassi entity URL cannot contain query or fragment");
  return url;
}

function boundedText(value, label, maxBytes = MAX_MESSAGE_BYTES) {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${label} must be non-empty text`);
  if (Buffer.byteLength(value, "utf8") > maxBytes) throw new RangeError(`${label} exceeds ${maxBytes} UTF-8 bytes`);
  return value;
}

function boundedId(value, label) {
  return boundedText(value, label, 256);
}

function canonical(value) {
  return JSON.stringify(value, Object.keys(value).sort());
}
function parseSse(bytes) {
  const text = new TextDecoder().decode(bytes);
  return text
    .split(/\r?\n\r?\n/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const fields = {};
      for (const line of block.split(/\r?\n/)) {
        const separator = line.indexOf(":");
        if (separator < 0) continue;
        fields[line.slice(0, separator)] = line.slice(separator + 1).trimStart();
      }
      return {
        id: fields.id,
        kind: fields.event,
        data: fields.data ? JSON.parse(fields.data) : null,
      };
    });
}

export function stableRequestId(prefix, value) {
  const digest = createHash("sha256").update(canonical(value)).digest("hex").slice(0, 48);
  return `${prefix}:${digest}`;
}

export class CassiEntityHttpError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "CassiEntityHttpError";
    this.status = status;
    this.body = body;
  }
}

export class CassiEntityClient {
  constructor({
    baseUrl = "http://127.0.0.1:8090",
    token,
    fetchImpl = globalThis.fetch,
    maxEvidenceBytes = MAX_EVIDENCE_BYTES,
  } = {}) {
    if (typeof fetchImpl !== "function") throw new Error("fetch is required for the Cassi entity client");
    if (typeof token !== "string" || token.length < 32) throw new Error("Cassi entity bearer token is missing or too short");
    this.baseUrl = assertLoopbackUrl(baseUrl);
    this.token = token;
    this.fetch = fetchImpl;
    this.maxEvidenceBytes = Math.min(Math.max(Number(maxEvidenceBytes) || MAX_EVIDENCE_BYTES, 1), MAX_EVIDENCE_BYTES);
  }

  async request(path, { method = "GET", body, signal, accept = "application/json" } = {}) {
    if (typeof path !== "string" || !path.startsWith("/v1/")) throw new Error("Cassi entity path is outside the declared API");
    const url = new URL(path, this.baseUrl);
    if (url.origin !== this.baseUrl.origin) throw new Error("Cassi entity request escaped its configured origin");
    const headers = {
      authorization: `Bearer ${this.token}`,
      accept,
      "cache-control": "no-store",
    };
    const init = { method, headers, signal };
    if (body !== undefined) {
      headers["content-type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const response = await this.fetch(url, init);
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json() : new Uint8Array(await response.arrayBuffer());
    if (!response.ok) {
      const detail = payload && typeof payload === "object" && !ArrayBuffer.isView(payload) ? payload.error ?? `HTTP ${response.status}` : `HTTP ${response.status}`;
      throw new CassiEntityHttpError(String(detail), response.status, payload);
    }
    return payload;
  }

  state(signal) {
    return this.request("/v1/state", { signal });
  }

  health(signal) {
    return this.request("/v1/health", { signal });
  }

  researchStatus(signal) {
    return this.request("/v1/research/status", { signal });
  }

  researchCapabilities(signal) {
    return this.request("/v1/research/capabilities", { signal });
  }

  listPrograms(signal) {
    return this.request("/v1/programs", { signal });
  }

  getProgram(programId, signal) {
    return this.request(`/v1/programs/${encodeURIComponent(boundedId(programId, "program_id"))}`, { signal });
  }

  sendMessage({ requestId, conversationId, projectId, content, observedAt = new Date().toISOString(), signal }) {
    return this.request("/v1/messages", {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        conversation_id: boundedId(conversationId, "conversation_id"),
        project_id: boundedId(projectId, "project_id"),
        content: boundedText(content, "content"),
        observed_at: observedAt,
      },
    });
  }

  auxiliary({ requestId, purpose, prompt, maxTokens = 256, signal }) {
    if (purpose !== "compaction" && purpose !== "session-title") {
      throw new TypeError(`unsupported auxiliary purpose ${JSON.stringify(purpose)}`);
    }
    if (!Number.isInteger(maxTokens) || maxTokens < 1 || maxTokens > 4_096) {
      throw new RangeError("max_tokens must be an integer in 1..4096");
    }
    return this.request("/v1/auxiliary", {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        purpose,
        prompt: boundedText(prompt, "prompt", 48_000),
        max_tokens: maxTokens,
      },
    });
  }

  createTurn({
    turnId,
    requestId,
    conversationId,
    projectId,
    content,
    kind = "user-message",
    source,
    toolCatalog,
    hostScope,
    observedAt = new Date().toISOString(),
    signal,
  }) {
    return this.request("/v1/turns", {
      method: "POST",
      signal,
      body: {
        turn_id: boundedId(turnId, "turn_id"),
        request_id: boundedId(requestId, "request_id"),
        conversation_id: boundedId(conversationId, "conversation_id"),
        project_id: boundedId(projectId, "project_id"),
        content: boundedText(content, "content"),
        kind: boundedId(kind, "kind"),
        observed_at: observedAt,
        ...(source === undefined ? {} : { source }),
        ...(toolCatalog === undefined ? {} : { tool_catalog: toolCatalog }),
        ...(hostScope === undefined ? {} : { host_scope: hostScope }),
      },
    });
  }

  getTurn(turnId, signal) {
    return this.request(`/v1/turns/${encodeURIComponent(boundedId(turnId, "turn_id"))}`, { signal });
  }

  async turnEvents(turnId, { after = 0, wait = 0, signal } = {}) {
    if (!Number.isInteger(after) || after < 0) throw new TypeError("after must be a nonnegative integer");
    if (!Number.isFinite(wait) || wait < 0) throw new TypeError("wait must be finite and nonnegative");
    const payload = await this.request(
      `/v1/turns/${encodeURIComponent(boundedId(turnId, "turn_id"))}/events?after=${after}&wait=${Math.min(wait, 60)}`,
      { signal, accept: "text/event-stream" },
    );
    return parseSse(payload);
  }

  cancelTurn({ turnId, requestId, observedAt = new Date().toISOString(), signal }) {
    return this.request(`/v1/turns/${encodeURIComponent(boundedId(turnId, "turn_id"))}/cancel`, {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        observed_at: observedAt,
      },
    });
  }

  submitTurnToolResults({ turnId, requestId, results, observedAt = new Date().toISOString(), signal }) {
    if (!Array.isArray(results)) throw new TypeError("results must be an array");
    return this.request(`/v1/turns/${encodeURIComponent(boundedId(turnId, "turn_id"))}/tool-results`, {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        results,
        observed_at: observedAt,
      },
    });
  }

  admitProgram({ requestId, programId, projectId, title, mission, initialQuestion, cycleLimit, allowedRoots, allowedTools, networkHosts, observedAt = new Date().toISOString(), signal }) {
    return this.request("/v1/programs", {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        program_id: boundedId(programId, "program_id"),
        project_id: boundedId(projectId, "project_id"),
        title: boundedText(title, "title", 512),
        mission: boundedText(mission, "mission", 8_000),
        initial_question: boundedText(initialQuestion, "initial_question", 8_000),
        observed_at: observedAt,
        ...(cycleLimit === undefined ? {} : { cycle_limit: Math.max(1, Math.min(10_000, Number(cycleLimit))) }),
        ...(allowedRoots === undefined ? {} : { allowed_roots: allowedRoots }),
        ...(allowedTools === undefined ? {} : { allowed_tools: allowedTools }),
        ...(networkHosts === undefined ? {} : { network_hosts: networkHosts }),
      },
    });
  }

  addGuidance({ requestId, programId, content, observedAt = new Date().toISOString(), signal }) {
    return this.request(`/v1/programs/${encodeURIComponent(boundedId(programId, "program_id"))}/guidance`, {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        content: boundedText(content, "content", 8_000),
        observed_at: observedAt,
      },
    });
  }

  controlProgram({ requestId, programId, action, message, observedAt = new Date().toISOString(), signal }) {
    const actions = new Set(["pause", "resume", "cancel", "complete", "wake"]);
    if (!actions.has(action)) throw new TypeError(`unsupported program action ${JSON.stringify(action)}`);
    return this.request(`/v1/programs/${encodeURIComponent(boundedId(programId, "program_id"))}/control`, {
      method: "POST",
      signal,
      body: {
        request_id: boundedId(requestId, "request_id"),
        action,
        observed_at: observedAt,
        ...(message === undefined ? {} : { message: boundedText(message, "message", 2_000) }),
      },
    });
  }

  async readEvidence(sha256, maxBytes = this.maxEvidenceBytes, signal) {
    if (!/^[0-9a-f]{64}$/i.test(sha256)) throw new TypeError("sha256 must be a 64-character hexadecimal digest");
    const requested = Math.min(Math.max(Number(maxBytes) || this.maxEvidenceBytes, 1), this.maxEvidenceBytes);
    const bytes = await this.request(`/v1/research/artifacts/${sha256.toLowerCase()}`, { signal, accept: "application/octet-stream" });
    const bounded = bytes.slice(0, requested);
    return {
      sha256: sha256.toLowerCase(),
      byte_length: bytes.byteLength,
      returned_bytes: bounded.byteLength,
      truncated: bounded.byteLength < bytes.byteLength,
      content_base64: Buffer.from(bounded).toString("base64"),
    };
  }
}
