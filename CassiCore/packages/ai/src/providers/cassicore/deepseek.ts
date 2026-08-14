import type {
  Message,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from "../../cassicore-types/index.js";
import { OpenAICompatibleBase } from "./openai-compatible-base.js";

const BASE_URL = "https://api.deepseek.com";

const DEEPSEEK_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"] as const;

interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

export class DeepSeekProvider extends OpenAICompatibleBase {
  readonly id = "deepseek";
  readonly models: string[] = [...DEEPSEEK_MODELS];

  private readonly apiKey: string;

  constructor(apiKey?: string) {
    super();
    this.apiKey =
      apiKey ||
      process.env.DEEPSEEK_API_KEY ||
      "";
    if (!this.apiKey) {
      throw new Error(
        "DeepSeekProvider: no API key — set DEEPSEEK_API_KEY or pass key to constructor",
      );
    }
  }

  protected getBaseUrl(): string {
    return BASE_URL;
  }

  protected getHeaders(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
    };
  }

  protected resolveModel(model: string): string {
    if (model === "flash" || model === "deepseek/flash") {
      return "deepseek-v4-flash";
    }
    if (model === "pro" || model === "deepseek/pro") {
      return "deepseek-v4-pro";
    }
    return model.replace("deepseek/", "");
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
      max_tokens: opts.maxTokens ?? 16384,
    };

    if (opts.thinking && opts.thinking !== "none") {
      body.thinking = { type: "enabled" };
      const effortMap: Record<string, string> = {
        low: "high",
        medium: "high",
        high: "high",
        "max": "max",
      };
      body.reasoning_effort = effortMap[opts.thinking] ?? "high";
    } else {
      body.temperature = opts.temperature ?? 0.6;
    }

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

    if (
      typeof delta["reasoning_content"] === "string" &&
      delta["reasoning_content"]
    ) {
      yield { type: "thinking", text: delta["reasoning_content"] };
    }

    if (Array.isArray(delta["tool_calls"])) {
      const tcs = delta["tool_calls"] as Array<Record<string, unknown>>;
      for (const tc of tcs) {
        const index = typeof tc["index"] === "number" ? tc["index"] : 0;
        const function_ = tc["function"] as
          | Record<string, unknown>
          | undefined;
        const id = (tc["id"] as string) || "";
        const name = (function_?.["name"] as string) || "";
        const arguments_ = (function_?.["arguments"] as string) || "";

        const existing = accumulators.toolCallAccum.get(index);
        if (existing) {
          existing.argsJson += arguments_;
        } else {
          accumulators.toolCallAccum.set(index, {
            id,
            name,
            argsJson: arguments_,
          });
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
      opts.model || this.models[0],
      messages,
      opts,
      attachments,
      signal,
    );
  }
}
