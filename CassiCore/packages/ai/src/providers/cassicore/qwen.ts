/**
 * Qwen Provider for CassiCore
 * 
 * Alibaba Qwen models via OpenAI-compatible API.
 * Supports multi-account load balancing and OAuth authentication.
 * Extended with CassiCore-specific runtime implementation.
 */

import type { Api, Model, KnownProvider } from "../../types.js";

export type QwenModel = "qwen3-coder-plus" | "qwen3-coder-flash" | "qwen3-vl-plus" | "qwen-max";

const QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";

export const qwenModels: Array<Model<"openai-completions">> = [
  {
    id: "qwen3-coder-plus",
    name: "Qwen3 Coder Plus",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.3, output: 0.6, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 65536,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  },
  {
    id: "qwen3-coder-flash",
    name: "Qwen3 Coder Flash",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: false,
    input: ["text"],
    cost: { input: 0.1, output: 0.2, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 65536,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false
    }
  },
  {
    id: "qwen3-vl-plus",
    name: "Qwen3 VL Plus",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 1.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 262144,
    maxTokens: 32768,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  },
  {
    id: "qwen-max",
    name: "Qwen Max",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.8, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  }
];

export interface QwenAccount {
  profileId: string;
  credentials: QwenOAuthCredentials;
  baseUrl?: string;
}

/**
 * Qwen Load Balancer
 * Distributes requests across multiple Qwen accounts
 */
export class QwenLoadBalancer {
  private accounts: QwenAccount[];
  private currentIndex = 0;
  private cooldowns = new Map<string, number>();
  private cooldownMs: number;
  maxRetries: number;

  constructor(options: {
    accounts: QwenAccount[];
    strategy?: "round-robin" | "random";
    cooldownMs?: number;
    maxRetries?: number;
  }) {
    this.accounts = options.accounts;
    this.cooldownMs = options.cooldownMs || 60000;
    this.maxRetries = options.maxRetries || 2;
  }

  /**
   * Get next available account
   */
  getNextAccount(): QwenAccount | undefined {
    const now = Date.now();
    
    // Filter out accounts in cooldown
    const available = this.accounts.filter(acc => {
      const cooldownEnd = this.cooldowns.get(acc.profileId);
      return !cooldownEnd || now > cooldownEnd;
    });

    if (available.length === 0) {
      // All accounts in cooldown, reset and try again
      this.cooldowns.clear();
      return this.accounts[0];
    }

    const account = available[this.currentIndex % available.length];
    this.currentIndex++;
    return account;
  }

  /**
   * Mark account as failed (put in cooldown)
   */
  markFailed(profileId: string): void {
    this.cooldowns.set(profileId, Date.now() + this.cooldownMs);
  }
}

/**
 * Get Qwen model by ID
 */
export function getQwenModel(modelId: QwenModel): Model<"openai-completions"> | undefined {
  return qwenModels.find(m => m.id === modelId);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Runtime Provider Implementation
// ═══════════════════════════════════════════════════════════════════════════════

import type { 
  Message, 
  ContentBlock, 
  CompletionOpts, 
  CompletionChunk, 
  ImageAttachment 
} from "../../cassicore-types/index.js";

const DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";
const QWEN_DEVICE_CODE_ENDPOINT = "https://chat.qwen.ai/api/v1/oauth2/device/code";
const QWEN_TOKEN_ENDPOINT = "https://chat.qwen.ai/api/v1/oauth2/token";
const QWEN_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56";
const QWEN_SCOPE = "openid profile email model.completion";
const QWEN_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code";

/** OAuth credentials interface for Qwen */
export interface QwenOAuthCredentials {
  refresh: string;
  access: string;
  expires: number;
  enterpriseUrl?: string;
}

/** Device code response */
interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  expires_in: number;
  interval?: number;
}

/** Token response */
interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  resource_url?: string;
}

/** Qwen provider implementation with OAuth support */
export class QwenProvider {
  readonly id = "qwen";
  readonly models = [
    "coder-model",
    "vision-model",
  ];

  private apiKey: string;
  private baseUrl: string;
  private credentials?: QwenOAuthCredentials;

  constructor(apiKey: string, baseUrl?: string, credentials?: QwenOAuthCredentials) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl || DEFAULT_BASE_URL;
    this.credentials = credentials;
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const model = opts.model || "coder-model";
    const maxTokens = opts.maxTokens || 4096;
    const temperature = opts.temperature ?? 0.7;

    // Auto-refresh token if expired or expiring within 5 minutes
    if (this.credentials && this.credentials.expires < Date.now() + 5 * 60 * 1000) {
      try {
        this.credentials = await QwenProvider.refreshToken(this.credentials);
      } catch (err) {
        yield { type: "error", error: `Token refresh failed: ${String(err)}` };
        return;
      }
    }

    // Use credentials access token if available
    const token = this.credentials?.access || this.apiKey;

    // Build attachment map: last user message → attachments
    const attachmentMap = new Map<number, ImageAttachment[]>();
    if (attachments?.length) {
      const lastUserIdx = messages.map(m => m.role).lastIndexOf("user");
      if (lastUserIdx >= 0) attachmentMap.set(lastUserIdx, attachments);
    }

    const openaiMessages = toOpenAIMessages(messages, attachmentMap);
    
    // Inject system prompt if provided and not already in messages
    if (opts.systemPrompt && !messages.find(m => m.role === "system")) {
      openaiMessages.unshift({ role: "system", content: opts.systemPrompt });
    }

    const body: Record<string, unknown> = {
      model,
      messages: openaiMessages,
      stream: true,
      max_tokens: maxTokens,
      temperature,
    };

    // Handle Qwen reasoning format
    if (opts.thinking && opts.thinking !== "none") {
      body.enable_thinking = true;
    }

    if (opts.tools?.length) {
      body.tools = opts.tools.map(t => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.input_schema,
        },
      }));
      body.tool_choice = "auto";
    }

    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        yield { type: "error", error: "cancelled" };
        return;
      }
      throw err;
    }

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Qwen error ${res.status}: ${text}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";
    const toolCallAccum = new Map<number, { id: string; name: string; argsJson: string }>();

    try {
      while (true) {
        if (signal?.aborted) { try { await reader.cancel(); } catch {} yield { type: "error", error: "cancelled" }; return; }
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed === "data: [DONE]") continue;
          if (!trimmed.startsWith("data: ")) continue;

          try {
            const json = JSON.parse(trimmed.slice(6));
            const delta = json.choices?.[0]?.delta;
            if (!delta) continue;

            const text = delta.content || delta.text || "";
            const reasoning = delta.reasoning_content || delta.reasoning || "";

            if (text) {
              yield { type: "token", text };
            }
            if (reasoning) {
              yield { type: "thinking", text: reasoning };
            }

            if (Array.isArray(delta.tool_calls)) {
              for (const tc of delta.tool_calls) {
                const idx = tc.index as number;
                const fn = tc.function as Record<string, unknown> | undefined;

                if (!toolCallAccum.has(idx)) {
                  toolCallAccum.set(idx, {
                    id: (tc.id as string) ?? `call_${idx}`,
                    name: (fn?.name as string) ?? "",
                    argsJson: "",
                  });
                }
                const acc = toolCallAccum.get(idx)!;
                if (tc.id) acc.id = tc.id;
                if (fn?.name) acc.name = fn.name as string;
                if (fn?.arguments) acc.argsJson += fn.arguments as string;
              }
            }
          } catch (e) {
            // Ignore parse errors on individual lines
          }
        }
      }

      // Flush remaining tool calls
      if (toolCallAccum.size > 0) {
        for (const tc of Array.from(toolCallAccum.values())) {
          let parsed: Record<string, unknown> = {};
          try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
          yield {
            type: "tool_use",
            toolCall: { id: tc.id, name: tc.name, input: parsed },
          };
        }
        toolCallAccum.clear();
      }
    } finally {
      reader.releaseLock();
    }

    yield { type: "done", model };
  }

  async countTokens(messages: Message[]): Promise<number> {
    // Estimate tokens: ~4 chars per token
    return Math.ceil(messages.reduce((s, m) => {
      const textLen = typeof m.content === "string"
        ? m.content.length
        : m.content.reduce((cs, b) => cs + ("text" in b ? b.text.length : 50), 0);
      return s + textLen;
    }, 0) / 4);
  }

  async ping(signal?: AbortSignal): Promise<boolean> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      if (signal) {
        if (signal.aborted) try { controller.abort(); } catch {}
        else {
          signal.addEventListener("abort", () => { try { controller.abort(); } catch {} });
        }
      }
      const token = this.credentials?.access || this.apiKey;
      const res = await fetch(`${this.baseUrl}/models`, {
        headers: { "Authorization": `Bearer ${token}` },
        signal: controller.signal,
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /** OAuth: Start device flow */
  static async startDeviceFlow(): Promise<{ deviceCode: DeviceCodeResponse; verifier: string }> {
    const { verifier, challenge } = await generatePKCE();

    const body = new URLSearchParams({
      client_id: QWEN_CLIENT_ID,
      scope: QWEN_SCOPE,
      code_challenge: challenge,
      code_challenge_method: "S256",
    });

    const headers: Record<string, string> = {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept": "application/json",
    };
    const requestId = globalThis.crypto?.randomUUID?.();
    if (requestId) headers["x-request-id"] = requestId;

    const response = await fetch(QWEN_DEVICE_CODE_ENDPOINT, {
      method: "POST",
      headers,
      body: body.toString(),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Device code request failed: ${response.status} ${text}`);
    }

    const data = (await response.json()) as DeviceCodeResponse;

    if (!data.device_code || !data.user_code || !data.verification_uri) {
      throw new Error("Invalid device code response: missing required fields");
    }

    return { deviceCode: data, verifier };
  }

  /** OAuth: Poll for token */
  static async pollForToken(
    deviceCode: string,
    verifier: string,
    intervalSeconds: number | undefined,
    expiresIn: number,
    signal?: AbortSignal,
  ): Promise<QwenOAuthCredentials> {
    const deadline = Date.now() + expiresIn * 1000;
    const resolvedIntervalSeconds =
      typeof intervalSeconds === "number" && Number.isFinite(intervalSeconds) && intervalSeconds > 0
        ? intervalSeconds
        : 2;
    let intervalMs = Math.max(1000, Math.floor(resolvedIntervalSeconds * 1000));

    while (Date.now() < deadline) {
      if (signal?.aborted) {
        throw new Error("Login cancelled");
      }

      const body = new URLSearchParams({
        grant_type: QWEN_GRANT_TYPE,
        client_id: QWEN_CLIENT_ID,
        device_code: deviceCode,
        code_verifier: verifier,
      });

      const response = await fetch(QWEN_TOKEN_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Accept": "application/json",
        },
        body: body.toString(),
      });

      const responseText = await response.text();
      let data: (TokenResponse & { error?: string; error_description?: string }) | null = null;
      if (responseText) {
        try {
          data = JSON.parse(responseText) as TokenResponse & { error?: string; error_description?: string };
        } catch {
          data = null;
        }
      }

      const error = data?.error;

      if (!response.ok || error) {
        if (error === "authorization_pending") {
          await abortableSleep(intervalMs, signal);
          continue;
        } else if (error === "slow_down") {
          intervalMs = Math.min(intervalMs + 5000, 10000);
          await abortableSleep(intervalMs, signal);
          continue;
        } else if (error === "expired_token") {
          throw new Error("Device code expired. Please restart authentication.");
        } else if (error === "access_denied") {
          throw new Error("Authorization denied by user.");
        }
        throw new Error(`Token request failed: ${error} - ${data?.error_description || ""}`);
      }

      if (data?.access_token) {
        const expiresAt = Date.now() + data.expires_in * 1000 - 5 * 60 * 1000;
        return {
          refresh: data.refresh_token || "",
          access: data.access_token,
          expires: expiresAt,
          enterpriseUrl: data.resource_url,
        };
      }

      await abortableSleep(intervalMs, signal);
    }

    throw new Error("Authentication timed out. Please try again.");
  }

  /** OAuth: Refresh token */
  static async refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: credentials.refresh,
      client_id: QWEN_CLIENT_ID,
    });

    const response = await fetch(QWEN_TOKEN_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
      },
      body: body.toString(),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Token refresh failed: ${response.status} ${text}`);
    }

    const data = (await response.json()) as TokenResponse;

    if (!data.access_token) {
      throw new Error("Token refresh failed: no access token in response");
    }

    const expiresAt = Date.now() + data.expires_in * 1000 - 5 * 60 * 1000;

    return {
      refresh: data.refresh_token || credentials.refresh,
      access: data.access_token,
      expires: expiresAt,
      enterpriseUrl: data.resource_url ?? credentials.enterpriseUrl,
    };
  }
}

/** PKCE helpers */
async function generatePKCE(): Promise<{ verifier: string; challenge: string }> {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  const verifier = btoa(String.fromCharCode(...Array.from(array)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest("SHA-256", data);
  const challenge = btoa(String.fromCharCode(...Array.from(new Uint8Array(hash))))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  return { verifier, challenge };
}

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error("Login cancelled"));
      return;
    }
    const timeout = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timeout);
      reject(new Error("Login cancelled"));
    });
  });
}

/** Convert messages to OpenAI format */
function toOpenAIMessages(
  messages: Message[],
  attachmentsByIndex?: Map<number, ImageAttachment[]>,
): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    const attachments = attachmentsByIndex?.get(i) ?? [];

    if (msg.role === "system") {
      out.push({
        role: "system",
        content: typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content),
      });
      continue;
    }

    if (typeof msg.content === "string") {
      if (attachments.length === 0) {
        out.push({ role: msg.role, content: msg.content });
      } else {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: "image_url",
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }));
        if (msg.content) parts.push({ type: "text", text: msg.content });
        out.push({ role: msg.role, content: parts });
      }
      continue;
    }

    // ContentBlock[]
    const blocks = msg.content as ContentBlock[];
    
    // Check if this is a tool execution role mapping
    const isToolResult = blocks.some(b => b.type === "tool_result");
    if (isToolResult) {
      for (const b of blocks) {
        if (b.type === "tool_result") {
          out.push({
            role: "tool",
            tool_call_id: b.tool_use_id,
            content: b.content || "null",
          });
        }
      }
      continue;
    }

    const toolUses = blocks.filter((b): b is Extract<ContentBlock, { type: "tool_use" }> => b.type === "tool_use");
    const others = blocks.filter(b => b.type !== "tool_use" && b.type !== "tool_result");

    const roleMsg: Record<string, unknown> = { role: msg.role };
    
    if (others.length > 0) {
      const textContent = others.map(b => b.type === "text" ? b.text : "").join("");
      
      if (attachments.length > 0) {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: "image_url",
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }));
        if (textContent) parts.push({ type: "text", text: textContent });
        roleMsg.content = parts;
      } else {
        roleMsg.content = textContent;
      }
    } else {
      roleMsg.content = "";
    }

    if (toolUses.length > 0) {
      roleMsg.tool_calls = toolUses.map(t => ({
        id: t.id,
        type: "function",
        function: {
          name: t.name,
          arguments: JSON.stringify(t.input)
        }
      }));
    }
    
    out.push(roleMsg);
  }

  return out.filter(m => {
    if (m.role === "tool") return true;
    if (m.tool_calls) return true;
    const content = m.content;
    if (typeof content === "string") return content.length > 0;
    if (Array.isArray(content)) return content.length > 0;
    return true;
  });
}
