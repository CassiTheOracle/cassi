/**
 * Kimi Coding Provider for CassiCore
 * 
 * Moonshot AI's Kimi models (k2.5 series) via OpenAI-compatible API.
 * Extended with CassiCore-specific features and runtime implementation.
 */

import type { Api, Model, KnownProvider } from "../../types.js";

export type KimiModel = "k2.5" | "k2.5-long" | "k2.5-vision";

const KIMI_BASE_URL = "https://api.moonshot.cn/v1";

export const kimiModels: Array<Model<"openai-completions">> = [
  {
    id: "k2.5",
    name: "Kimi K2.5",
    api: "openai-completions",
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  },
  {
    id: "k2.5-long",
    name: "Kimi K2.5 (Long Context)",
    api: "openai-completions", 
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 2000000, // 2M context
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  },
  {
    id: "k2.5-vision",
    name: "Kimi K2.5 Vision",
    api: "openai-completions",
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  }
];

/**
 * Get Kimi model by ID
 */
export function getKimiModel(modelId: KimiModel): Model<"openai-completions"> | undefined {
  return kimiModels.find(m => m.id === modelId);
}

// Runtime Provider Implementation

import type { 
  Message, 
  CompletionOpts, 
  CompletionChunk, 
  ImageAttachment 
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

const BASE_URL = "https://api.kimi.com/coding/v1";

const KIMI_CODING_HEADERS = {
  "User-Agent": "KimiCLI/1.0",
  "Content-Type": "application/json",
};

/** Models supported by Kimi Coding */
const KIMI_CODING_MODELS = [
  "kimi-for-coding",  // Kimi K2.5 - the primary coding model (k2p5 alias)
  "k2p5",             // Alias that maps to kimi-for-coding
] as const;

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/** 
 * Kimi Coding provider — OpenAI-compatible Chat Completions API
 * Base URL: https://api.kimi.com/coding/v1
 * Model: kimi-for-coding (k2.5)
 * Requires User-Agent: KimiCLI/1.0 to identify as a coding agent
 */
export class KimiCodingProvider extends OpenAICompatibleBase {
  readonly id = "kimi-coding";
  readonly models: string[] = [...KIMI_CODING_MODELS];

  private readonly apiKey: string;

  constructor(apiKey?: string) {
    super();
    this.apiKey = apiKey || process.env.KIMI_API_KEY || process.env.KIMICODE_API_KEY || "";
    if (!this.apiKey) {
      throw new Error("KimiCodingProvider: no API key — set KIMI_API_KEY or pass key to constructor");
    }
  }

  protected getBaseUrl(): string {
    return BASE_URL;
  }

  protected getHeaders(): Record<string, string> {
    return {
      ...KIMI_CODING_HEADERS,
      "Authorization": `Bearer ${this.apiKey}`,
    };
  }

  /**
   * Kimi requires reasoning_content on all assistant messages
   */
  protected shouldInjectReasoningContent(): boolean {
    return true;
  }

  /**
   * Map model alias to actual API model name
   */
  protected resolveModel(model: string): string {
    if (model === "k2p5" || model === "kimi-coding/k2p5") {
      return "kimi-for-coding";
    }
    return model.replace("kimi-coding/", "");
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
