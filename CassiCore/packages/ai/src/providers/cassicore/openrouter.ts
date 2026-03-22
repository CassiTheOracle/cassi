/**
 * OpenRouter Provider for CassiCore
 *
 * Unified API for 100+ models via OpenRouter.
 * Extended with CassiCore-specific routing preferences and runtime implementation.
 */

import type {
  Api,
  Model,
  KnownProvider,
  OpenRouterRouting,
} from "../../types.js";

export type OpenRouterModel =
  | "anthropic/claude-sonnet-4"
  | "anthropic/claude-opus-4"
  | "openai/gpt-5"
  | "openai/gpt-5-mini"
  | "google/gemini-2.5-pro"
  | "meta/llama-4-maverick"
  | "deepseek/deepseek-chat-v3"
  | "xai/grok-3";

const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";

export const openrouterModels: Array<Model<"openai-completions">> = [
  {
    id: "anthropic/claude-sonnet-4",
    name: "Claude Sonnet 4 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
    contextWindow: 200000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      openRouterRouting: {
        order: ["anthropic"],
      },
    },
  },
  {
    id: "anthropic/claude-opus-4",
    name: "Claude Opus 4 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 15, output: 75, cacheRead: 1.5, cacheWrite: 18.75 },
    contextWindow: 200000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      openRouterRouting: {
        order: ["anthropic"],
      },
    },
  },
  {
    id: "openai/gpt-5",
    name: "GPT-5 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 5, output: 15, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "openai/gpt-5-mini",
    name: "GPT-5 Mini (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: false,
    input: ["text", "image"],
    cost: { input: 0.5, output: 1.5, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "google/gemini-2.5-pro",
    name: "Gemini 2.5 Pro (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 1.25, output: 10, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "meta/llama-4-maverick",
    name: "Llama 4 Maverick (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: false,
    input: ["text", "image"],
    cost: { input: 0.2, output: 0.8, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "deepseek/deepseek-chat-v3",
    name: "DeepSeek Chat V3 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.07, output: 0.28, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 64000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "xai/grok-3",
    name: "Grok 3 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 3, output: 15, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 100000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
];

/**
 * Get OpenRouter model by ID
 */
export function getOpenRouterModel(modelId: OpenRouterModel): Model<"openai-completions"> | undefined {
  return openrouterModels.find(m => m.id === modelId);
}

// Runtime Provider Implementation

import type {
  Message,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

const BASE_URL = "https://openrouter.ai/api/v1";

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/**
 * OpenRouter provider — OpenAI-compatible Chat Completions API
 * Base URL: https://openrouter.ai/api/v1
 * Supports 100+ models with unified routing
 * Requires HTTP-Referer and X-Title headers
 */
export class OpenRouterProvider extends OpenAICompatibleBase {
  readonly id = "openrouter";
  readonly models: string[] = openrouterModels.map(m => m.id);

  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly routing?: OpenRouterRouting;

  constructor(apiKey?: string, baseUrlOrRouting?: string | OpenRouterRouting) {
    super();
    this.apiKey = apiKey || process.env.OPENROUTER_API_KEY || "";
    if (!this.apiKey) {
      throw new Error(
        "OpenRouterProvider: no API key — set OPENROUTER_API_KEY or pass key to constructor",
      );
    }
    
    // Handle both string baseUrl (legacy) and OpenRouterRouting object
    if (typeof baseUrlOrRouting === "string") {
      this.baseUrl = baseUrlOrRouting || BASE_URL;
      this.routing = undefined;
    } else {
      this.baseUrl = BASE_URL;
      this.routing = baseUrlOrRouting;
    }
  }

  protected getBaseUrl(): string {
    return this.baseUrl;
  }

  protected getHeaders(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
      "HTTP-Referer": "https://cassicore.dev",
      "X-Title": "CassiCore",
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
      max_tokens: opts.maxTokens ?? 4096,
      temperature: opts.temperature ?? 0.7,
    };

    if (opts.tools?.length) {
      const normalized = this.normalizeToolsToOpenAI(opts.tools);
      if (normalized.length) {
        body.tools = normalized;
        body.tool_choice = "auto";
      }
    }

    if (this.routing) {
      body.provider = { order: this.routing.order };
    }

    return body;
  }

  /**
   * Override convertMessages to handle OpenRouter-specific tool_result mapping
   */
  protected convertMessages(
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
      const blocks = msg.content;

      // Check if this is a tool execution role mapping
      const isToolResult = blocks.some(b => b.type === "tool_result");
      if (isToolResult) {
        for (const b of blocks) {
          if (b.type === "tool_result") {
            const tr = b as { tool_use_id: string; content: string };
            out.push({
              role: "tool",
              tool_call_id: tr.tool_use_id,
              content: tr.content ?? "null"
            });
          }
        }
        continue;
      }

      const toolUses = blocks.filter(b => b.type === "tool_use") as Array<{ type: string; id: string; name: string; input?: Record<string, unknown> }>;
      const others = blocks.filter(b => b.type !== "tool_use" && b.type !== "tool_result") as Array<{ type: string; text?: string }>;

      if (toolUses.length > 0) {
        const textContent = others
          .map(b => (b.type === "text" ? b.text ?? "" : ""))
          .filter(Boolean)
          .join("");

        const toolCalls = toolUses.map(b => ({
          id: b.id,
          type: "function",
          function: {
            name: b.name,
            arguments: JSON.stringify(b.input ?? {}),
          },
        }));

        out.push({
          role: "assistant",
          content: textContent || "",
          tool_calls: toolCalls,
        });
      } else if (others.length > 0) {
        const textContent = others
          .map(b => (b.type === "text" ? b.text ?? "" : ""))
          .filter(Boolean)
          .join("");

        if (attachments.length > 0) {
          const parts: Array<Record<string, unknown>> = attachments.map(att => ({
            type: "image_url",
            image_url: { url: `data:${att.mediaType};base64,${att.data}` },
          }));
          if (textContent) parts.push({ type: "text", text: textContent });
          out.push({ role: msg.role, content: parts });
        } else {
          out.push({ role: msg.role, content: textContent });
        }
      }
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
    if (typeof delta["reasoning_content"] === "string" && delta["reasoning_content"]) {
      yield { type: "thinking", text: delta["reasoning_content"] };
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
    yield* this.streamChatCompletion(opts.model || this.models[0], messages, opts, attachments, signal);
  }
}
