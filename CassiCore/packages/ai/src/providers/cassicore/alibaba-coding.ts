/**
 * Alibaba Coding Plan Provider for CassiCore
 *
 * Alibaba's unified coding platform providing access to models from multiple
 * vendors (Qwen, Zhipu/GLM, Kimi, MiniMax) through a single API key.
 *
 * Supports two API protocols:
 * - OpenAI-compatible (Qwen models): https://coding-intl.dashscope.aliyuncs.com/v1
 * - Anthropic-compatible (GLM, Kimi, MiniMax): https://coding-intl.dashscope.aliyuncs.com/apps/anthropic
 *
 * This runtime provider handles the OpenAI-compatible Qwen models.
 * Anthropic-protocol models are dispatched by the existing anthropic-messages
 * API handler in @cassicore/ai via their model definitions.
 */

import type {
  Message,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

const OPENAI_BASE_URL = "https://coding-intl.dashscope.aliyuncs.com/v1";

/** Models available through the OpenAI-compatible endpoint */
const ALIBABA_CODING_OPENAI_MODELS = [
  "qwen3.6-plus",
  "qwen3-max-2026-01-23",
] as const;

/** Models available through the Anthropic-compatible endpoint (handled by anthropic-messages API handler) */
const ALIBABA_CODING_ANTHROPIC_MODELS = [
  "glm-5",
  "kimi-k2.5",
  "MiniMax-M2.5",
] as const;

/** All models available through Alibaba Coding Plan */
export const ALIBABA_CODING_ALL_MODELS = [
  ...ALIBABA_CODING_OPENAI_MODELS,
  ...ALIBABA_CODING_ANTHROPIC_MODELS,
] as const;

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/**
 * Alibaba Coding Plan provider — OpenAI-compatible Chat Completions API
 * Base URL: https://coding-intl.dashscope.aliyuncs.com/v1
 *
 * Handles Qwen models via the OpenAI-compatible endpoint.
 * GLM/Kimi/MiniMax models use the Anthropic endpoint and are handled by the
 * existing anthropic-messages API handler at the @cassicore/ai layer.
 */
export class AlibabaCodingProvider extends OpenAICompatibleBase {
  readonly id = "alibaba-coding";
  readonly models: string[] = [...ALIBABA_CODING_ALL_MODELS];

  private readonly apiKey: string;

  constructor(apiKey?: string) {
    super();
    this.apiKey = apiKey || process.env.ALIBABA_CODING_API_KEY || "";
    if (!this.apiKey) {
      throw new Error(
        "AlibabaCodingProvider: no API key — set ALIBABA_CODING_API_KEY or pass key to constructor",
      );
    }
  }

  /**
   * Get the API key for external use (e.g., by the Anthropic-protocol models
   * that share the same credential but go through a different API handler).
   */
  getApiKey(): string {
    return this.apiKey;
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

    // Enable Qwen thinking mode for reasoning-capable models
    if (model === "qwen3.6-plus" || model === "qwen3-max-2026-01-23") {
      body.enable_thinking = true;
    }

    // Tool definitions — normalize to OpenAI function-call format
    // Handles both Anthropic-format {name, description, input_schema} and
    // already-wrapped OpenAI-format {type: "function", function: {...}} tools
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

    // Qwen thinking/reasoning content
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
      opts.model || "qwen3.6-plus",
      messages,
      opts,
      attachments,
      signal,
    );
  }
}
