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
    contextWindow: 1000000,
    maxTokens: 65536,
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
    cost: { input: 2.4, output: 9.6, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 32000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  }
];

/** Qwen account for load balancing */
export interface QwenAccount {
  profileId: string;
  apiKey?: string;
  credentials?: QwenOAuthCredentials;
  baseUrl?: string;
}

/** OAuth endpoints for Qwen */
const QWEN_AUTH_BASE = "https://auth.alibabacloud.com";
const QWEN_DEVICE_CODE_ENDPOINT = `${QWEN_AUTH_BASE}/oauth2/device/code`;
const QWEN_TOKEN_ENDPOINT = `${QWEN_AUTH_BASE}/oauth2/token`;
const QWEN_CLIENT_ID = "qwen-copilot";
const QWEN_SCOPE = "qwen.copilot.all";

const DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";

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

/** Multi-account load balancer for Qwen */
export class QwenLoadBalancer {
  private accounts: QwenAccount[];
  private currentIndex = 0;
  private cooldowns = new Map<string, number>();
  private cooldownMs: number;
  private maxRetries: number;

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

// Runtime Provider Implementation

import type { 
  Message, 
  CompletionOpts, 
  CompletionChunk, 
  ImageAttachment 
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/** Qwen provider implementation with OAuth support */
export class QwenProvider extends OpenAICompatibleBase {
  readonly id = "qwen";
  readonly models = [
    "coder-model",
    "vision-model",
  ];

  private apiKey: string;
  private baseUrl: string;
  private credentials?: QwenOAuthCredentials;

  constructor(apiKey: string, baseUrl?: string, credentials?: QwenOAuthCredentials) {
    super();
    this.apiKey = apiKey;
    this.baseUrl = baseUrl || DEFAULT_BASE_URL;
    this.credentials = credentials;
  }

  protected getBaseUrl(): string {
    return this.baseUrl;
  }

  protected getHeaders(): Record<string, string> {
    const token = this.credentials?.access || this.apiKey;
    return {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    };
  }

  protected buildRequestBody(
    model: string,
    messages: Array<Record<string, unknown>>,
    opts: CompletionOpts,
  ): Record<string, unknown> {
    const body: Record<string, unknown> = {
      model,
      messages,
      stream: true,
      stream_options: { include_usage: true },
      max_tokens: opts.maxTokens || 4096,
      temperature: opts.temperature ?? 0.7,
    };

    if (opts.tools?.length) {
      const normalized = this.normalizeToolsToOpenAI(opts.tools);
      if (normalized.length) {
        body.tools = normalized;
        body.tool_choice = "auto";
      }
    }

    return body;
  }

  protected *parseStreamDelta(
    delta: Record<string, unknown>,
    accumulators: {
      toolCallAccum: Map<number, ToolCallAccumulator>;
      receivedAnyChunks: boolean;
    },
  ): Generator<CompletionChunk, void, unknown> {
    if (typeof delta["content"] === "string" && delta["content"]) {
      yield { type: "token", text: delta["content"] };
    }

    if (Array.isArray(delta["tool_calls"])) {
      const tcs = delta["tool_calls"] as Array<Record<string, unknown>>;
      for (const tc of tcs) {
        const index = typeof tc["index"] === "number" ? tc["index"] : 0;
        const function_ = tc["function"] as Record<string, unknown> | undefined;
        const id = (tc["id"] as string) || "";
        const name = (function_?.["name"] as string) || "";
        const arguments_ = (function_?.["arguments"] as string) || "";

        const existing = accumulators.toolCallAccum.get(index);
        if (existing) {
          existing.argsJson += arguments_;
        } else {
          accumulators.toolCallAccum.set(index, { id, name, argsJson: arguments_ });
        }
      }
    }
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Auto-refresh token if expired or expiring within 5 minutes
    if (this.credentials && this.credentials.expires < Date.now() + 5 * 60 * 1000) {
      try {
        this.credentials = await QwenProvider.refreshToken(this.credentials);
      } catch {
        // Continue with existing token, will fail with auth error if truly expired
      }
    }

    const model = opts.model || "coder-model";

    // Build attachment map: last user message → attachments
    const attachmentMap = new Map<number, ImageAttachment[]>();
    if (attachments?.length) {
      const lastUserIdx = messages.map(m => m.role).lastIndexOf("user");
      if (lastUserIdx >= 0) attachmentMap.set(lastUserIdx, attachments);
    }

    const openaiMessages = this.convertMessages(messages, attachmentMap);
    
    // Inject system prompt if provided and not already in messages
    if (opts.systemPrompt && !messages.find(m => m.role === "system")) {
      openaiMessages.unshift({ role: "system", content: opts.systemPrompt });
    }

    const body = this.buildRequestBody(model, openaiMessages, opts);

    const controller = new AbortController();
    // Connection timeout only — cleared once SSE stream starts
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    let res: Response;
    try {
      if (signal) {
        if (signal.aborted) {
          try {
            controller.abort();
          } catch {}
        } else {
          signal.addEventListener("abort", () => {
            try {
              controller.abort();
            } catch {}
          });
        }
      }

      res = await fetch(`${this.baseUrl}/chat/completions`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      clearTimeout(timeoutId);
      yield { type: "error", error: String(err) };
      return;
    }

    if (!res.ok) {
      clearTimeout(timeoutId);
      let errText = "";
      try {
        errText = await res.text();
      } catch {}
      yield { type: "error", error: `HTTP ${res.status}: ${errText || res.statusText}` };
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      clearTimeout(timeoutId);
      yield { type: "error", error: "No response body" };
      return;
    }

    // Connection established — clear the connection timeout
    // (the stream itself may take minutes for large completions)
    clearTimeout(timeoutId);

    let receivedAnyChunks = false;
    let jsonAccumulator = "";
    const toolCallAccum = new Map<number, ToolCallAccumulator>();
    let eventLines: string[] = [];

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          const trimmed = line.trim();

          // Empty line signals the end of an event
          if (trimmed === "") {
            if (eventLines.length > 0) {
              const dataCombined = eventLines.join("\n");
              eventLines = [];

              jsonAccumulator += dataCombined.trim();

              if (jsonAccumulator.trim() === "[DONE]") {
                yield* this.flushToolCalls(toolCallAccum, model, 0);
                return;
              }

              const { parsed: parsedObjs, remainder } = this.extractCompleteJSONObjects(jsonAccumulator);
              jsonAccumulator = remainder;

              if (parsedObjs && parsedObjs.length > 0) {
                for (const evt of parsedObjs) {
                  const choices = evt["choices"] as Array<Record<string, unknown>> | undefined;

                  if (choices && Array.isArray(choices) && choices.length > 0) {
                    const choice = choices[0];
                    const delta = choice["delta"] as Record<string, unknown> | undefined;

                    if (delta && typeof delta === "object") {
                      const chunks = this.parseStreamDelta(delta, {
                        toolCallAccum,
                        receivedAnyChunks,
                      });

                      if (chunks) {
                        for (const chunk of chunks) {
                          if (chunk.type !== "error") {
                            receivedAnyChunks = true;
                          }
                          yield chunk;
                        }
                      }
                    }
                  }
                }
              }
            }
            continue;
          }

          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;

          if (data === "[DONE]") {
            yield* this.flushToolCalls(toolCallAccum, model, 0);
            return;
          }

          eventLines.push(data);
        }
      }
    } finally {
      clearTimeout(timeoutId);
      reader.releaseLock();
    }

    yield* this.flushToolCalls(toolCallAccum, model, 0);
  }

  /**
   * Flush accumulated tool calls and yield done chunk (Qwen override)
   */
  protected override *flushToolCalls(
    toolCallAccum: Map<number, ToolCallAccumulator>,
    model: string,
    _totalTokensUsed: number,
  ): Generator<CompletionChunk, void, unknown> {
    if (toolCallAccum.size > 0) {
      for (const tc of Array.from(toolCallAccum.values())) {
        let parsed: Record<string, unknown> = {};
        try {
          parsed = JSON.parse(tc.argsJson);
        } catch {
          // empty args
        }
        yield {
          type: "tool_use",
          toolCall: { id: tc.id, name: tc.name, input: parsed },
        };
      }
    }
    yield { type: "done", model };
  }

  /** OAuth: Start device flow */
  static async startDeviceFlow(): Promise<{ deviceCode: DeviceCodeResponse; verifier: string }> {
    const { generatePKCE } = await import("../../utils/oauth/pkce.js");
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

      await new Promise(resolve => setTimeout(resolve, intervalMs));

      const body = new URLSearchParams({
        client_id: QWEN_CLIENT_ID,
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
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

      if (response.status === 428) {
        // Authorization pending - continue polling
        continue;
      }

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Token request failed: ${response.status} ${text}`);
      }

      const data = (await response.json()) as TokenResponse;

      if (!data.access_token) {
        throw new Error("Invalid token response: missing access_token");
      }

      return {
        access: data.access_token,
        refresh: data.refresh_token || "",
        expires: Date.now() + data.expires_in * 1000,
        enterpriseUrl: data.resource_url,
      };
    }

    throw new Error("Device code expired");
  }

  /** OAuth: Refresh access token */
  static async refreshToken(credentials: QwenOAuthCredentials): Promise<QwenOAuthCredentials> {
    if (!credentials.refresh) {
      throw new Error("No refresh token available");
    }

    const body = new URLSearchParams({
      client_id: QWEN_CLIENT_ID,
      grant_type: "refresh_token",
      refresh_token: credentials.refresh,
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
      throw new Error("Invalid token response: missing access_token");
    }

    return {
      access: data.access_token,
      refresh: data.refresh_token || credentials.refresh,
      expires: Date.now() + data.expires_in * 1000,
      enterpriseUrl: data.resource_url || credentials.enterpriseUrl,
    };
  }
}
