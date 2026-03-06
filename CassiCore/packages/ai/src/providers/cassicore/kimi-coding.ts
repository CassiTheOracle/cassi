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

// ── Message format helpers ───────────────────────────────────────────────────

function toOpenAIMessages(
  messages: Message[],
  attachmentsByIndex?: Map<number, ImageAttachment[]>,
): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    const attachments = attachmentsByIndex?.get(i) ?? [];

    if (msg.role === "system") {
      out.push({ role: "system", content: typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content) });
      continue;
    }

    if (typeof msg.content === "string") {
      if (attachments.length === 0) {
        // Kimi requires reasoning_content on all assistant messages when reasoning is active
        if (msg.role === "assistant") {
          out.push({ role: "assistant", content: msg.content, reasoning_content: "" });
        } else {
          out.push({ role: msg.role, content: msg.content });
        }
      } else {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: "image_url",
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }));
        if (msg.content) parts.push({ type: "text", text: msg.content });
        out.push({ role: msg.role, content: parts, ...(msg.role === "assistant" ? { reasoning_content: "" } : {}) });
      }
      continue;
    }

    // ContentBlock[] — handle tool_use / tool_result / text properly for OpenAI format
    const blocks = msg.content as ContentBlock[];
    const toolUseBlocks = blocks.filter(
      (b): b is Extract<ContentBlock, { type: "tool_use" }> => b.type === "tool_use"
    );
    const toolResults = blocks.filter(
      (b): b is Extract<ContentBlock, { type: "tool_result" }> => b.type === "tool_result"
    );
    const textBlocks = blocks.filter(b => b.type === "text");

    // Assistant messages with tool_use blocks → OpenAI tool_calls format
    if (toolUseBlocks.length > 0) {
      const textContent = textBlocks
        .map(b => b.type === "text" ? b.text : "")
        .join("");

      const toolCalls = toolUseBlocks.map(b => ({
        id: b.id,
        type: "function",
        function: {
          name: b.name,
          arguments: JSON.stringify(b.input ?? {}),
        },
      }));

      const assistantMsg: Record<string, unknown> = {
        role: "assistant",
        content: textContent || "",
        tool_calls: toolCalls,
        // Kimi K2.5 requires reasoning_content on all assistant messages when
        // reasoning mode is enabled — even on tool_call messages that have no
        // thinking tokens.
        reasoning_content: " ",
      };

      if (attachments.length > 0) {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: "image_url",
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }));
        if (textContent) parts.push({ type: "text", text: textContent });
        assistantMsg.content = parts;
      }

      out.push(assistantMsg);
    } else if (textBlocks.length > 0 && toolResults.length === 0) {
      // Pure text message (no tool blocks)
      const textContent = textBlocks
        .map(b => b.type === "text" ? b.text : "")
        .join("");

      if (attachments.length > 0) {
        const parts: Array<Record<string, unknown>> = attachments.map(att => ({
          type: "image_url",
          image_url: { url: `data:${att.mediaType};base64,${att.data}` },
        }));
        if (textContent) parts.push({ type: "text", text: textContent });
        out.push({ role: msg.role, content: parts, reasoning_content: msg.role === "assistant" ? "" : undefined });
      } else if (msg.role === "assistant") {
        // Kimi requires reasoning_content on all assistant messages when reasoning is active
        out.push({ role: "assistant", content: textContent, reasoning_content: "" });
      } else {
        out.push({ role: msg.role, content: textContent });
      }
    }

    // tool_result blocks → OpenAI role: 'tool' messages with tool_call_id
    for (const r of toolResults) {
      out.push({
        role: "tool",
        tool_call_id: r.tool_use_id,
        content: r.content,
      });
    }
  }

  // Filter out empty messages, but preserve assistant messages that have tool_calls
  return out.filter(m => {
    // Always keep messages with tool_calls (assistant tool invocations)
    if (m.tool_calls && Array.isArray(m.tool_calls) && (m.tool_calls as unknown[]).length > 0) return true;
    // Always keep tool result messages
    if (m.role === "tool") return true;
    const content = m.content;
    if (content === null) return true; // null content is valid for tool-calling assistant messages
    if (typeof content === "string") return content.length > 0;
    if (Array.isArray(content)) return content.length > 0;
    return true;
  });
}

// ── Helper: robust JSON extractor for fragmented SSE payloads ───────────────

/**
 * Extract complete JSON objects/arrays from a possibly-fragmented string.
 * Returns an array of parsed objects (skips incomplete trailing fragments).
 */
function extractCompleteJSONObjects(s: string): { parsed: any[]; remainder: string } {
  const parsed: any[] = [];
  let i = 0;
  const len = s.length;
  let lastConsumed = 0;

  while (i < len) {
    // Skip whitespace until a JSON start token
    while (i < len && /\s/.test(s[i])) i++;
    if (i >= len) break;

    const startChar = s[i];
    if (startChar !== "{" && startChar !== "[") {
      // Find next possible start
      const idx1 = s.indexOf("{", i);
      const idx2 = s.indexOf("[", i);
      let idx = -1;
      if (idx1 === -1) idx = idx2;
      else if (idx2 === -1) idx = idx1;
      else idx = Math.min(idx1, idx2);
      if (idx === -1) break;
      i = idx;
    }

    const openChar = s[i];
    const closeChar = openChar === "{" ? "}" : "]";
    let depth = 0;
    let inString = false;
    let escape = false;
    let j = i;
    for (; j < len; j++) {
      const ch = s[j];
      if (inString) {
        if (escape) {
          escape = false;
          continue;
        }
        if (ch === "\\") {
          escape = true;
          continue;
        }
        if (ch === '"') {
          inString = false;
          continue;
        }
      } else {
        if (ch === '"') {
          inString = true;
          continue;
        }
        if (ch === openChar) {
          depth++;
          continue;
        }
        if (ch === closeChar) {
          depth--;
          if (depth === 0) {
            const jsonStr = s.slice(i, j + 1);
            try {
              parsed.push(JSON.parse(jsonStr));
            } catch (err) {
              // If parse fails even though braces balanced, skip it
            }
            lastConsumed = j + 1;
            i = j + 1;
            break;
          }
        }
      }
    }

    // If loop ended without closing the JSON, it's incomplete — stop
    if (j >= len) break;
  }

  return { parsed, remainder: s.slice(lastConsumed) };
}

// ── Provider ─────────────────────────────────────────────────────────────────

/** 
 * Kimi Coding provider — OpenAI-compatible Chat Completions API
 * Base URL: https://api.kimi.com/coding/v1
 * Model: kimi-for-coding (k2.5)
 * Requires User-Agent: KimiCLI/1.0 to identify as a coding agent
 */
export class KimiCodingProvider {
  readonly id = "kimi-coding";
  readonly models: string[] = [...KIMI_CODING_MODELS];

  private readonly apiKey: string;

  constructor(apiKey?: string) {
    this.apiKey = apiKey || process.env.KIMI_API_KEY || process.env.KIMICODE_API_KEY || "";
    if (!this.apiKey) {
      throw new Error("KimiCodingProvider: no API key — set KIMI_API_KEY or pass key to constructor");
    }
  }

  private get headers(): Record<string, string> {
    return {
      ...KIMI_CODING_HEADERS,
      "Authorization": `Bearer ${this.apiKey}`,
    };
  }

  /**
   * Map model alias to actual API model name
   */
  private resolveModel(model: string): string {
    if (model === "k2p5" || model === "kimi-coding/k2p5") {
      return "kimi-for-coding";
    }
    return model.replace("kimi-coding/", "");
  }

  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const model = this.resolveModel(opts.model || this.models[0]);

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

    // Kimi K2.5 requires reasoning_content on ALL assistant messages when
    // reasoning mode is active. Ensure it's present even on messages that
    // were constructed by the pipeline or intelligence modules.
    // NOTE: Empty string "" is rejected — must be at least a non-empty string.
    for (const m of openaiMessages) {
      if ((m as any).role === "assistant" && !(m as any).reasoning_content) {
        (m as any).reasoning_content = " ";
      }
    }

    const body: Record<string, unknown> = {
      model,
      messages: openaiMessages,
      stream: true,
      stream_options: { include_usage: true },
      max_tokens: opts.maxTokens ?? 8192,
      temperature: opts.temperature ?? 0.6,
    };

    // Tool definitions — tools arrive in OpenAI schema format from the pipeline
    if (opts.tools?.length) {
      body.tools = opts.tools;
      body.tool_choice = "auto";
    }

    let res: Response;
    try {
      res = await fetch(`${BASE_URL}/chat/completions`, {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(body),
        signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        yield { type: "error", error: signal?.aborted ? "cancelled" : `network error: ${String(err)}` };
      } else {
        yield { type: "error", error: `network error: ${String(err)}` };
      }
      return;
    }

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      yield { type: "error", error: `http ${res.status}: ${text}` };
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      yield { type: "error", error: "no response body" };
      return;
    }

    const decoder = new TextDecoder();
    let buf = "";
    let jsonAccumulator = "";
    // Accumulate streaming tool calls by index
    const toolCallAccum = new Map<number, { id: string; name: string; argsJson: string }>();

    // Debug counters
    let streamClosedNormally = false;

    // Track if we received any meaningful content from the stream
    let receivedAnyChunks = false;

    // Accumulate token usage from the final streaming usage chunk
    let totalTokensUsed = 0;

    // For proper SSE parsing we accumulate 'data:' lines that belong to a single event.
    // SSE events are separated by a blank line. Multiple 'data:' lines within the same event
    // should be concatenated with '\n'. We collect those lines here and process on event boundary.
    let eventLines: string[] = [];

    try {
      while (true) {
        if (signal?.aborted) { try { await reader.cancel(); } catch {} yield { type: "error", error: "cancelled" }; return; }
        const { done, value } = await reader.read();
        if (done) {
          streamClosedNormally = true;
          break;
        }
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";

        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, "");

          // Event boundary (empty line) — process accumulated data lines as one event
          if (line === "") {
            if (eventLines.length === 0) continue;
            const dataCombined = eventLines.join("\n");
            eventLines = [];

            // Append to the incremental JSON accumulator and try to parse complete objects
            try {
              jsonAccumulator += dataCombined.trim();

              // If the accumulator explicitly signals end-of-stream, flush and finish
              if (jsonAccumulator.trim() === "[DONE]") {
                for (const tc of toolCallAccum.values()) {
                  let parsed: Record<string, unknown> = {};
                  try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
                  yield {
                    type: "tool_use",
                    toolCall: { id: tc.id, name: tc.name, input: parsed },
                  };
                }
                toolCallAccum.clear();
                yield { type: "done", model, tokensUsed: totalTokensUsed };
                return;
              }

              const { parsed: parsedObjs, remainder } = extractCompleteJSONObjects(jsonAccumulator);
              jsonAccumulator = remainder;

              if (parsedObjs && parsedObjs.length > 0) {
                const out: CompletionChunk[] = [];

                for (const evt of parsedObjs) {
                  // Check for final usage chunk (choices is empty, usage is present)
                  const usage = evt["usage"] as Record<string, unknown> | undefined;
                  if (usage && typeof usage["total_tokens"] === "number") {
                    totalTokensUsed = usage["total_tokens"];
                  }

                  const choices = evt["choices"] as Array<Record<string, unknown>> | undefined;
                  if (!choices?.length) continue;

                  const choice = choices[0];
                  const delta = choice["delta"] as Record<string, unknown> | undefined;
                  if (!delta) continue;

                  if (typeof delta["content"] === "string" && delta["content"]) {
                    out.push({ type: "token", text: delta["content"] });
                  }
                  if (typeof delta["reasoning_content"] === "string" && delta["reasoning_content"]) {
                    out.push({ type: "thinking", text: delta["reasoning_content"] });
                  }

                  if (Array.isArray(delta["tool_calls"])) {
                    const tcs = delta["tool_calls"] as Array<Record<string, unknown>>;
                    for (const tc of tcs) {
                      const idx = tc["index"] as number;
                      const fn = tc["function"] as Record<string, unknown> | undefined;

                      if (!toolCallAccum.has(idx)) {
                        toolCallAccum.set(idx, {
                          id: (tc["id"] as string) ?? `call_${idx}`,
                          name: (fn?.["name"] as string) ?? "",
                          argsJson: "",
                        });
                      }
                      const acc = toolCallAccum.get(idx)!;
                      if (tc["id"]) acc.id = tc["id"] as string;
                      if (fn?.["name"]) acc.name = fn["name"] as string;
                      if (fn?.["arguments"]) acc.argsJson += fn["arguments"] as string;
                    }
                  }
                }

                if (out.length > 0) receivedAnyChunks = true;
                for (const c of out) yield c;
              }
            } catch (parseErr) {
              // Ignore partial/malformed JSON — wait for more chunks
            }

            continue;
          }

          // Non-empty line
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;

          // If the line itself signals end of stream, process immediately
          if (data === "[DONE]") {
            // Flush any accumulated tool calls
            for (const tc of toolCallAccum.values()) {
              let parsed: Record<string, unknown> = {};
              try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
              yield {
                type: "tool_use",
                toolCall: { id: tc.id, name: tc.name, input: parsed },
              };
            }
            toolCallAccum.clear();
            yield { type: "done", model, tokensUsed: totalTokensUsed };
            return;
          }

          // Otherwise, add payload to current event lines and wait for a blank line boundary
          eventLines.push(data);
        }
      }
    } finally {
      // Process any remaining accumulated event lines first
      if (eventLines.length > 0) {
        const dataCombined = eventLines.join("\n");
        eventLines = [];
        try {
          jsonAccumulator += dataCombined.trim();

          // If the accumulator explicitly signals end-of-stream, flush and finish
          if (jsonAccumulator.trim() === "[DONE]") {
            for (const tc of toolCallAccum.values()) {
              let parsed: Record<string, unknown> = {};
              try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
              yield {
                type: "tool_use",
                toolCall: { id: tc.id, name: tc.name, input: parsed },
              };
            }
            toolCallAccum.clear();
            yield { type: "done", model, tokensUsed: totalTokensUsed };
            return;
          }

          const { parsed: parsedObjs, remainder } = extractCompleteJSONObjects(jsonAccumulator);
          jsonAccumulator = remainder;

          if (parsedObjs && parsedObjs.length > 0) {
            for (const evt of parsedObjs) {
              // Extract usage from final usage chunk (empty choices, has usage field)
              const usage = evt["usage"] as Record<string, unknown> | undefined;
              if (usage && typeof usage["total_tokens"] === "number") {
                totalTokensUsed = usage["total_tokens"];
              }

              const choices = evt["choices"] as Array<Record<string, unknown>> | undefined;

              if (choices && Array.isArray(choices) && choices.length > 0) {
                const choice = choices[0];
                const delta = choice["delta"] as Record<string, unknown> | undefined;

                if (delta && typeof delta === "object") {
                  if (typeof delta["content"] === "string" && delta["content"]) {
                    yield { type: "token", text: delta["content"] };
                    receivedAnyChunks = true;
                  }
                  if (typeof delta["reasoning_content"] === "string" && delta["reasoning_content"]) {
                    yield { type: "thinking", text: delta["reasoning_content"] };
                    receivedAnyChunks = true;
                  }
                  if (Array.isArray(delta["tool_calls"])) {
                    const tcs = delta["tool_calls"] as Array<Record<string, unknown>>;
                    for (const tc of tcs) {
                      const idx = tc["index"] as number;
                      const fn = tc["function"] as Record<string, unknown> | undefined;
                      if (!toolCallAccum.has(idx)) {
                        toolCallAccum.set(idx, {
                          id: (tc["id"] as string) ?? `call_${idx}`,
                          name: (fn?.["name"] as string) ?? "",
                          argsJson: "",
                        });
                      }
                      const acc = toolCallAccum.get(idx)!;
                      if (tc["id"]) acc.id = tc["id"] as string;
                      if (fn?.["name"]) acc.name = fn["name"] as string;
                      if (fn?.["arguments"]) acc.argsJson += fn["arguments"] as string;
                    }
                  }
                }
              }
            }
          }

        } catch (parseErr) {
          // Silently skip malformed/incomplete accumulated events
        }
      }

      // Process any leftover buffer that didn't end with a newline
      if (buf && buf.trim()) {
        try {
          const dataStr = buf.trim().startsWith("data:") ? buf.trim().slice(5).trim() : buf.trim();
          if (dataStr && dataStr !== "[DONE]") {
            jsonAccumulator += dataStr;
            if (jsonAccumulator.trim() === "[DONE]") {
              for (const tc of toolCallAccum.values()) {
                let parsed: Record<string, unknown> = {};
                try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
                yield {
                  type: "tool_use",
                  toolCall: { id: tc.id, name: tc.name, input: parsed },
                };
              }
              toolCallAccum.clear();
              yield { type: "done", model, tokensUsed: totalTokensUsed };
              return;
            }

            const { parsed: parsedObjs, remainder } = extractCompleteJSONObjects(jsonAccumulator);
            jsonAccumulator = remainder;

            if (parsedObjs && parsedObjs.length > 0) {
              for (const evt of parsedObjs) {
                // Extract usage from final usage chunk (empty choices, has usage field)
                const usage = evt["usage"] as Record<string, unknown> | undefined;
                if (usage && typeof usage["total_tokens"] === "number") {
                  totalTokensUsed = usage["total_tokens"];
                }

                const choices = evt["choices"] as Array<Record<string, unknown>> | undefined;

                if (choices && Array.isArray(choices) && choices.length > 0) {
                  const choice = choices[0];
                  const delta = choice["delta"] as Record<string, unknown> | undefined;

                  if (delta && typeof delta === "object") {
                    if (typeof delta["content"] === "string" && delta["content"]) {
                      yield { type: "token", text: delta["content"] };
                      receivedAnyChunks = true;
                    }
                    if (typeof delta["reasoning_content"] === "string" && delta["reasoning_content"]) {
                      yield { type: "thinking", text: delta["reasoning_content"] };
                      receivedAnyChunks = true;
                    }
                    if (Array.isArray(delta["tool_calls"])) {
                      const tcs = delta["tool_calls"] as Array<Record<string, unknown>>;
                      for (const tc of tcs) {
                        const idx = tc["index"] as number;
                        const fn = tc["function"] as Record<string, unknown> | undefined;
                        if (!toolCallAccum.has(idx)) {
                          toolCallAccum.set(idx, {
                            id: (tc["id"] as string) ?? `call_${idx}`,
                            name: (fn?.["name"] as string) ?? "",
                            argsJson: "",
                          });
                        }
                        const acc = toolCallAccum.get(idx)!;
                        if (tc["id"]) acc.id = tc["id"] as string;
                        if (fn?.["name"]) acc.name = fn["name"] as string;
                        if (fn?.["arguments"]) acc.argsJson += fn["arguments"] as string;
                      }
                    }
                  }
                }
              }
            }
          }
        } catch (parseErr) {
          // Silently skip malformed remainder
        }
      }

      // Flush any accumulated tool calls
      if (toolCallAccum.size > 0) {
        for (const tc of toolCallAccum.values()) {
          let parsed: Record<string, unknown> = {};
          try { parsed = JSON.parse(tc.argsJson); } catch { /* empty args */ }
          yield {
            type: "tool_use",
            toolCall: { id: tc.id, name: tc.name, input: parsed },
          };
          receivedAnyChunks = true;
        }
        toolCallAccum.clear();
      }

      // Emit warning if stream terminated abnormally without any content
      if (!streamClosedNormally) {
        if (!receivedAnyChunks) {
          console.warn("[KimiCodingProvider] stream terminated unexpectedly (abnormal close) — no content received");
        }
      }

      reader.releaseLock();
    }

    if (streamClosedNormally && toolCallAccum.size === 0) {
      yield { type: "done", model, tokensUsed: totalTokensUsed };
    }
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
    const timeoutId = setTimeout(() => controller.abort(), 5_000);
    try {
      if (signal) {
        if (signal.aborted) try { controller.abort(); } catch {}
        else {
          signal.addEventListener("abort", () => { try { controller.abort(); } catch {} });
        }
      }
      const res = await fetch(`${BASE_URL}/models`, {
        headers: this.headers,
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
