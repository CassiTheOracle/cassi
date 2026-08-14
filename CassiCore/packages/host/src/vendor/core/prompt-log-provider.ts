/**
 * Prompt-Logging Provider Wrapper
 *
 * Wraps any IProvider to transparently capture every prompt (messages array)
 * sent to `provider.complete()` AND the LLM response when streaming completes.
 *
 * The capture is fire-and-forget — it never blocks or throws. All other
 * IProvider methods (ping, countTokens, id, models) pass through directly.
 *
 * Usage in daemon:
 *   for (const [id, provider] of this.providers) {
 *     this.providers.set(id, withPromptLogging(provider, promptLogStore, id))
 *   }
 */

import type { IProvider, Message, CompletionOpts, CompletionChunk, ImageAttachment, ContentBlock } from '@cassicore/foundation'
import type { PromptLogStore } from './prompt-log-store.js'

/**
 * Wrap a provider to log every prompt AND response.
 *
 * @param provider   - The real IProvider implementation
 * @param store      - PromptLogStore instance for persistence
 * @param providerId - Provider identifier (e.g. 'github-copilot', 'alibaba-coding')
 */
export function withPromptLogging(
  provider: IProvider,
  store: PromptLogStore,
  providerId: string,
): IProvider {
  return {
    get id() { return provider.id },
    get models() { return provider.models },

    complete(
      messages: Message[],
      opts: CompletionOpts,
      attachments?: ImageAttachment[],
      signal?: AbortSignal,
    ): AsyncIterable<CompletionChunk> {
      // Fire-and-forget capture — never block the provider call
      let promptLogId: string | null = null
      try {
        promptLogId = store.capture(providerId, messages, opts)
      } catch {
        // Silently swallow — prompt logging must never break the provider
      }

      const stream = provider.complete(messages, opts, attachments, signal)

      // If we didn't get a log ID, just pass through the raw stream
      if (!promptLogId) return stream

      // Wrap the stream to capture response content blocks on completion
      const capturedId = promptLogId
      const startTime = Date.now()
      return wrapStreamForResponseCapture(stream, store, capturedId, startTime)
    },

    countTokens(messages: Message[]) {
      return provider.countTokens(messages)
    },

    ping() {
      return provider.ping()
    },
  }
}


/**
 * Wrap an async iterable stream to capture response content blocks.
 * Accumulates text/tool_use/thinking chunks, then persists on the 'done' chunk.
 */
async function* wrapStreamForResponseCapture(
  stream: AsyncIterable<CompletionChunk>,
  store: PromptLogStore,
  promptLogId: string,
  startTime: number,
): AsyncIterable<CompletionChunk> {
  const contentBlocks: ContentBlock[] = []
  let currentText = ''
  let currentThinking = ''
  let stopReason: string | null = null
  let outputTokens: number | undefined

  try {
    for await (const chunk of stream) {
      // Accumulate content
      if (chunk.type === 'token' && chunk.text) {
        currentText += chunk.text
      } else if (chunk.type === 'thinking' && chunk.text) {
        currentThinking += chunk.text
      } else if (chunk.type === 'tool_use' && chunk.toolCall) {
        // Flush any accumulated text before tool_use
        if (currentText) {
          contentBlocks.push({ type: 'text', text: currentText } as ContentBlock)
          currentText = ''
        }
        contentBlocks.push({
          type: 'tool_use',
          name: chunk.toolCall.name,
          id: chunk.toolCall.id,
          input: chunk.toolCall.input,
        } as unknown as ContentBlock)
      } else if (chunk.type === 'done') {
        stopReason = 'end_turn'
        outputTokens = chunk.tokenBreakdown?.output ?? chunk.tokensUsed
      } else if (chunk.type === 'error') {
        stopReason = 'error'
      }

      // Always yield the original chunk unchanged
      yield chunk
    }

    // Flush remaining text
    if (currentThinking) {
      contentBlocks.unshift({ type: 'thinking' as any, text: currentThinking } as ContentBlock)
    }
    if (currentText) {
      contentBlocks.push({ type: 'text', text: currentText } as ContentBlock)
    }

    // Persist response
    const durationMs = Date.now() - startTime
    try {
      store.captureResponse(promptLogId, contentBlocks, stopReason, durationMs, outputTokens)
    } catch {
      // Non-fatal
    }
  } catch (err) {
    // If the stream errors, still try to persist what we captured
    if (currentText) {
      contentBlocks.push({ type: 'text', text: currentText } as ContentBlock)
    }
    try {
      store.captureResponse(promptLogId, contentBlocks, 'error', Date.now() - startTime, outputTokens)
    } catch {
      // Non-fatal
    }
    throw err
  }
}
