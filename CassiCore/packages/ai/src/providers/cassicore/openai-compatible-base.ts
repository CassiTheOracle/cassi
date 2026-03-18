/**
 * OpenAI-Compatible Base Provider
 * 
 * Abstract base class that deduplicates code across OpenAI-compatible providers.
 * Provides common implementations for message conversion, streaming, ping, and token counting.
 */

import type {
  Message,
  ContentBlock,
  CompletionOpts,
  CompletionChunk,
  ImageAttachment,
} from "../../cassicore-types/index.js";

/** Accumulator state for tool calls during streaming */
interface ToolCallAccumulator {
  id: string;
  name: string;
  argsJson: string;
}

/** Result of parsing JSON fragments */
interface JSONParseResult {
  parsed: Record<string, unknown>[];
  remainder: string;
}

/**
 * Abstract base class for OpenAI-compatible providers
 */
export abstract class OpenAICompatibleBase {
  abstract readonly id: string;
  abstract readonly models: string[];

  /**
   * Get the base URL for API requests
   */
  protected abstract getBaseUrl(): string;

  /**
   * Get headers for API requests
   */
  protected abstract getHeaders(): Record<string, string>;

  /**
   * Build the request body for chat completions
   */
  protected abstract buildRequestBody(
    model: string,
    messages: Array<Record<string, unknown>>,
    opts: CompletionOpts,
  ): Record<string, unknown>;

  /**
   * Parse a stream delta and yield appropriate chunks.
   * Implementations should use `yield` to emit CompletionChunk values.
   * Tool call deltas are accumulated via the mutable `accumulators.toolCallAccum` map
   * and flushed by `flushToolCalls` at the end of the stream.
   */
  protected abstract parseStreamDelta(
    delta: Record<string, unknown>,
    accumulators: {
      toolCallAccum: Map<number, ToolCallAccumulator>;
      receivedAnyChunks: boolean;
    },
  ): Generator<CompletionChunk, void, unknown>;

  /**
   * Resolve model ID to actual API model name (for aliasing)
   */
  protected resolveModel(model: string): string {
    return model;
  }

  /**
   * Whether to inject reasoning_content on assistant messages
   * Override to return true for providers like Kimi that require this
   */
  protected shouldInjectReasoningContent(): boolean {
    return false;
  }

  /**
   * Convert messages to OpenAI format
   */
  protected convertMessages(
    messages: Message[],
    attachmentsByIndex?: Map<number, ImageAttachment[]>,
  ): Array<Record<string, unknown>> {
    const out: Array<Record<string, unknown>> = [];
    const injectReasoning = this.shouldInjectReasoningContent();

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
          const roleMsg: Record<string, unknown> = { role: msg.role, content: msg.content };
          if (injectReasoning && msg.role === "assistant") {
            roleMsg.reasoning_content = "";
          }
          out.push(roleMsg);
        } else {
          const parts: Array<Record<string, unknown>> = attachments.map(att => ({
            type: "image_url",
            image_url: { url: `data:${att.mediaType};base64,${att.data}` },
          }));
          if (msg.content) parts.push({ type: "text", text: msg.content });
          const roleMsg: Record<string, unknown> = { role: msg.role, content: parts };
          if (injectReasoning && msg.role === "assistant") {
            roleMsg.reasoning_content = "";
          }
          out.push(roleMsg);
        }
        continue;
      }

      // ContentBlock[] — handle tool_use / tool_result / text properly for OpenAI format
      const blocks = msg.content as ContentBlock[];
      const toolUseBlocks = blocks.filter(
        (b): b is Extract<ContentBlock, { type: "tool_use" }> => b.type === "tool_use",
      );
      const toolResults = blocks.filter(
        (b): b is Extract<ContentBlock, { type: "tool_result" }> => b.type === "tool_result",
      );
      const textBlocks = blocks.filter(b => b.type === "text");

      if (toolUseBlocks.length > 0) {
        // Assistant message with tool calls
        const textContent = textBlocks
          .map(b => (b.type === "text" ? b.text : ""))
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
        };

        if (injectReasoning) {
          assistantMsg.reasoning_content = " ";
        }

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
          .map(b => (b.type === "text" ? b.text : ""))
          .join("");

        if (attachments.length > 0) {
          const parts: Array<Record<string, unknown>> = attachments.map(att => ({
            type: "image_url",
            image_url: { url: `data:${att.mediaType};base64,${att.data}` },
          }));
          if (textContent) parts.push({ type: "text", text: textContent });
          out.push({
            role: msg.role,
            content: parts,
            ...(injectReasoning && msg.role === "assistant" ? { reasoning_content: "" } : {}),
          });
        } else if (textContent || msg.role === "assistant") {
          const roleMsg: Record<string, unknown> = { role: msg.role, content: textContent };
          if (injectReasoning && msg.role === "assistant") {
            roleMsg.reasoning_content = "";
          }
          out.push(roleMsg);
        }
      }

      // tool_result blocks → "tool" role messages following the assistant message
      if (toolResults.length > 0) {
        for (const tr of toolResults) {
          // Find matching tool_use to get the name
          const matchingToolUse = out
            .flatMap(m => (m["tool_calls"] as Array<Record<string, unknown>>) || [])
            .find(tc => tc["id"] === tr.tool_use_id);

          out.push({
            role: "tool",
            tool_call_id: tr.tool_use_id,
            name: (matchingToolUse?.["function"] as Record<string, string>)?.["name"] || "tool",
            content: tr.content ?? "null",
          });
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

  /**
   * Extract complete JSON objects from a string fragment.
   * Handles cases where JSON objects are split across SSE chunks.
   */
  protected extractCompleteJSONObjects(s: string): JSONParseResult {
    const parsed: Record<string, unknown>[] = [];
    let lastConsumed = 0;
    const len = s.length;
    let i = 0;

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
              } catch {
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

  /**
   * Stream chat completion from an OpenAI-compatible API
   */
  protected async *streamChatCompletion(
    model: string,
    messages: Message[],
    opts: CompletionOpts,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const resolvedModel = this.resolveModel(model);

    // Build attachment map: last user message → attachments
    const attachmentMap = new Map<number, ImageAttachment[]>();
    if (attachments?.length) {
      const lastUserIdx = messages.map(m => m.role).lastIndexOf("user");
      if (lastUserIdx >= 0) attachmentMap.set(lastUserIdx, attachments);
    }

    const openaiMessages = this.convertMessages(messages, attachmentMap);
    const body = this.buildRequestBody(resolvedModel, openaiMessages, opts);
    const bodyJson = JSON.stringify(body);
    const url = `${this.getBaseUrl()}/chat/completions`;
    const headers = this.getHeaders();

    // Retry transient network failures (fetch failed, 429, 502, 503, 504)
    const MAX_FETCH_RETRIES = 3;
    let lastError = "";

    for (let attempt = 0; attempt <= MAX_FETCH_RETRIES; attempt++) {
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

        res = await fetch(url, {
          method: "POST",
          headers,
          body: bodyJson,
          signal: controller.signal,
        });
      } catch (err) {
        clearTimeout(timeoutId);
        lastError = String(err);
        // Retry on transient network errors
        if (attempt < MAX_FETCH_RETRIES) {
          const delay = Math.pow(2, attempt) * 1000 + Math.random() * 500;
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }
        yield { type: "error", error: lastError };
        return;
      }

      if (!res.ok) {
        clearTimeout(timeoutId);
        let errText = "";
        try {
          errText = await res.text();
        } catch {}

        // Retry on rate-limit or server errors
        const retryable = res.status === 429 || res.status >= 500;
        if (retryable && attempt < MAX_FETCH_RETRIES) {
          lastError = `HTTP ${res.status}: ${errText || res.statusText}`;
          const delay = Math.pow(2, attempt) * 1000 + Math.random() * 500;
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }

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
    let totalTokensUsed = 0;
    let tokenBreakdown: { input: number; output: number; cacheRead: number; cacheWrite: number } | undefined;
    // Event boundary accumulator: lines belonging to the current SSE event
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

              // If the accumulator explicitly signals end-of-stream, flush and finish
              if (jsonAccumulator.trim() === "[DONE]") {
                yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
                return;
              }

              const { parsed: parsedObjs, remainder } = this.extractCompleteJSONObjects(jsonAccumulator);
              jsonAccumulator = remainder;

              if (parsedObjs && parsedObjs.length > 0) {
                for (const evt of parsedObjs) {
                  // Extract usage from final usage chunk (empty choices, has usage field)
                  const usage = evt["usage"] as Record<string, unknown> | undefined;
                  if (usage && typeof usage["total_tokens"] === "number") {
                    totalTokensUsed = usage["total_tokens"];
                    const promptTokens = (usage["prompt_tokens"] as number) || 0;
                    const completionTokens = (usage["completion_tokens"] as number) || 0;
                    const details = usage["prompt_tokens_details"] as Record<string, unknown> | undefined;
                    const cachedTokens = (details?.["cached_tokens"] as number) || 0;
                    tokenBreakdown = {
                      input: promptTokens,
                      output: completionTokens,
                      cacheRead: cachedTokens,
                      cacheWrite: 0,
                    };
                  }

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

          // Non-empty line
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;

          // If the line itself signals end of stream, process immediately
          if (data === "[DONE]") {
            yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
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
                yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
                return;
              }

              const { parsed: parsedObjs, remainder } = this.extractCompleteJSONObjects(jsonAccumulator);
              jsonAccumulator = remainder;

              if (parsedObjs && parsedObjs.length > 0) {
                for (const evt of parsedObjs) {
                  // Extract usage from final usage chunk (empty choices, has usage field)
                  const usage = evt["usage"] as Record<string, unknown> | undefined;
                  if (usage && typeof usage["total_tokens"] === "number") {
                    totalTokensUsed = usage["total_tokens"];
                    const promptTokens = (usage["prompt_tokens"] as number) || 0;
                    const completionTokens = (usage["completion_tokens"] as number) || 0;
                    const details = usage["prompt_tokens_details"] as Record<string, unknown> | undefined;
                    const cachedTokens = (details?.["cached_tokens"] as number) || 0;
                    tokenBreakdown = { input: promptTokens, output: completionTokens, cacheRead: cachedTokens, cacheWrite: 0 };
                  }

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

                // Check for finish_reason to flush tool calls
                const finishReason = choice["finish_reason"];
                if (finishReason === "tool_calls" || finishReason === "stop") {
                  yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
                  return;
                }
              }
            }
          }
        } catch {
          // Ignore errors processing final event lines
        }
      }

      // Handle any remaining accumulator content
      if (jsonAccumulator.trim()) {
        try {
          if (jsonAccumulator.trim() === "[DONE]") {
            yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
            return;
          }

          const { parsed: parsedObjs, remainder } = this.extractCompleteJSONObjects(jsonAccumulator);

          if (parsedObjs && parsedObjs.length > 0) {
            for (const evt of parsedObjs) {
              // Extract usage from final usage chunk (empty choices, has usage field)
              const usage = evt["usage"] as Record<string, unknown> | undefined;
              if (usage && typeof usage["total_tokens"] === "number") {
                totalTokensUsed = usage["total_tokens"];
                const promptTokens = (usage["prompt_tokens"] as number) || 0;
                const completionTokens = (usage["completion_tokens"] as number) || 0;
                const details = usage["prompt_tokens_details"] as Record<string, unknown> | undefined;
                const cachedTokens = (details?.["cached_tokens"] as number) || 0;
                tokenBreakdown = { input: promptTokens, output: completionTokens, cacheRead: cachedTokens, cacheWrite: 0 };
              }

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

                // Check for finish_reason to flush tool calls
                const finishReason = choice["finish_reason"];
                if (finishReason === "tool_calls" || finishReason === "stop") {
                  yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);
                  return;
                }
              }
            }
          }

          jsonAccumulator = remainder;
        } catch {
          // Ignore errors processing final content
        }
      }

      clearTimeout(timeoutId);
      reader.releaseLock();
    }

    yield* this.flushToolCalls(toolCallAccum, resolvedModel, totalTokensUsed, tokenBreakdown);

    // If we get here, the stream completed successfully — exit retry loop
    return;
    } // end retry loop
  }

  /**
   * Flush accumulated tool calls and yield done chunk
   */
  protected *flushToolCalls(
    toolCallAccum: Map<number, ToolCallAccumulator>,
    model: string,
    totalTokensUsed: number,
    tokenBreakdown?: { input: number; output: number; cacheRead: number; cacheWrite: number },
  ): Generator<CompletionChunk, void, unknown> {
    for (const tc of toolCallAccum.values()) {
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
    toolCallAccum.clear();
    yield { type: "done", model, tokensUsed: totalTokensUsed, tokenBreakdown };
  }

  /**
   * Ping the API to check if it's available
   */
  async ping(signal?: AbortSignal): Promise<boolean> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
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
      const res = await fetch(`${this.getBaseUrl()}/models`, {
        headers: this.getHeaders(),
        signal: controller.signal,
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Count tokens in messages (estimated)
   */
  async countTokens(messages: Message[]): Promise<number> {
    // Estimate tokens: ~4 chars per token
    return Math.ceil(
      messages.reduce((s, m) => {
        const textLen =
          typeof m.content === "string"
            ? m.content.length
            : m.content.reduce((cs, b) => cs + ("text" in b ? (b as { text: string }).text.length : 50), 0);
        return s + textLen;
      }, 0) / 4,
    );
  }
}
