/**
 * OpenCode Go Provider for CassiCore
 *
 * OpenCode's unified API gateway providing OpenAI-compatible access to models
 * from multiple vendors (DeepSeek, Qwen, GLM, Kimi, MiniMax, MiMo, Hunyuan)
 * through a single endpoint.
 *
 * Base URL: https://opencode.ai/zen/go/v1
 * Model list: fetched dynamically from /v1/models on initialization
 */

import type {
  Message,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

const OPENAI_BASE_URL = "https://opencode.ai/zen/go/v1";

/** Fallback models used before the async fetch completes */
const FALLBACK_MODELS = [
  "deepseek-v4-pro",
  "deepseek-v4-flash",
  "qwen3.6-plus",
  "qwen3.5-plus",
  "glm-5",
  "glm-5.1",
  "kimi-k2.5",
  "kimi-k2.6",
  "minimax-m2.5",
  "minimax-m2.7",
  "mimo-v2-pro",
  "mimo-v2-omni",
  "mimo-v2.5",
  "mimo-v2.5-pro",
  "hy3-preview",
] as const;

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/**
 * OpenCode Go provider — OpenAI-compatible Chat Completions API
 *
 * All models are served through a single OpenAI-compatible endpoint.
 * The provider dynamically fetches the model list on construction and
 * falls back to a static list if the fetch fails.
 */
export class OpenCodeGoProvider extends OpenAICompatibleBase {
  readonly id = "opencode-go";

  private _models: string[] = [...FALLBACK_MODELS];
  private readonly apiKey: string;

  constructor(apiKey?: string) {
    super();
    this.apiKey = apiKey || process.env.OPENCODE_API_KEY || "";
    if (!this.apiKey) {
      throw new Error(
        "OpenCodeGoProvider: no API key — set OPENCODE_API_KEY or pass key to constructor",
      );
    }

    // Async fetch to discover current model list
    this.fetchModels()
      .then((models) => {
        if (models.length > 0) {
          this._models = models;
        }
      })
      .catch(() => {});
  }

  get models(): string[] {
    return this._models;
  }

  protected getBaseUrl(): string {
    return OPENAI_BASE_URL;
  }

  protected getHeaders(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
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
      max_tokens: opts.maxTokens ?? 8192,
      temperature: opts.temperature ?? 0.6,
    };

    // Enable thinking for reasoning-capable models
    // DeepSeek models use thinking: { type: "enabled" }
    if (model.startsWith("deepseek-")) {
      if (opts.thinking) {
        body.thinking = { type: "enabled" };
        body.reasoning_effort = "high";
      }
    } else {
      // Qwen/GLM/Kimi/MiniMax models use enable_thinking
      body.enable_thinking = true;
    }

    // Tool definitions — normalize to OpenAI function-call format
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
    // Text content
    if (typeof delta["content"] === "string" && delta["content"]) {
      yield { type: "token", text: delta["content"] };
    }

    // Reasoning/thinking content (used by Qwen, DeepSeek, GLM, Kimi, MiniMax)
    if (typeof delta["reasoning_content"] === "string" && delta["reasoning_content"]) {
      yield { type: "thinking", text: delta["reasoning_content"] };
    }

    // Tool calls (accumulated via mutable Map, flushed by flushToolCalls)
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
    yield* this.streamChatCompletion(
      opts.model || "deepseek-v4-pro",
      messages,
      opts,
      attachments,
      signal,
    );
  }
}
