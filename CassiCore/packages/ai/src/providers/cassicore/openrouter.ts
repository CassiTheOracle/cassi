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
    contextWindow: 128000,
    maxTokens: 16384,
    compat: {
      supportsDeveloperRole: true,
      supportsReasoningEffort: true,
    },
  },
  {
    id: "openai/gpt-5-mini",
    name: "GPT-5 Mini (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 1.5, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 16384,
    compat: {
      supportsDeveloperRole: true,
      supportsReasoningEffort: true,
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
    maxTokens: 65536,
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
    cost: { input: 0.2, output: 0.6, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "deepseek/deepseek-chat-v3",
    name: "DeepSeek V3 (via OpenRouter)",
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
    contextWindow: 128000,
    maxTokens: 32768,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
];

/**
 * Get OpenRouter model by ID
 */
export function getOpenRouterModel(
  modelId: OpenRouterModel
): Model<"openai-completions"> | undefined {
  return openrouterModels.find((m) => m.id === modelId);
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

const DEFAULT_BASE_URL = "https://openrouter.ai/api/v1";

/** OpenRouter provider implementation */
export class OpenRouterProvider {
  readonly id = "openrouter";
  readonly models = [
    "google/gemini-2.5-pro-preview-03-25",
    "google/gemini-2.5-flash-preview",
    "anthropic/claude-sonnet-4",
    "anthropic/claude-opus-4",
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "qwen/qwen3-235b-a22b:free",
  ];

  private apiKey: string;
  private baseUrl: string;

  constructor(apiKey: string, baseUrl?: string) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl || DEFAULT_BASE_URL;
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const model = opts.model || "google/gemini-2.5-pro-preview-03-25";
    const maxTokens = opts.maxTokens || 4096;
    const temperature = opts.temperature ?? 0.7;

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
          "Authorization": `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://cassicore.local",
          "X-Title": "CassiCore",
        },
        body: JSON.stringify(body),
        signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Best-effort: yield cancellation as error chunk
        yield { type: "error", error: "cancelled" };
        return;
      }
      throw err;
    }

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`OpenRouter error ${res.status}: ${text}`);
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
        for (const tc of toolCallAccum.values()) {
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
      const res = await fetch(`${this.baseUrl}/models`, {
        headers: { "Authorization": `Bearer ${this.apiKey}` },
        signal: controller.signal,
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timeoutId);
    }
  }
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
      const parts = blocks.map(b => {
        if (b.type === "tool_result") {
          return {
            tool_call_id: b.tool_use_id,
            role: "tool",
            name: (b as any).name || "tool",
            content: b.content || "null"
          };
        }
        return null;
      }).filter(Boolean);
      
      out.push(...parts as any[]);
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
