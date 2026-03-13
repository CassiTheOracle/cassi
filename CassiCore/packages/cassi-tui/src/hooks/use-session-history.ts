/**
 * Hook that loads session message history from the daemon on mount
 * and when the session ID changes.
 *
 * Converts raw SessionMessage[] (provider format) into DisplayMessage[]
 * suitable for rendering.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useDaemon } from './use-daemon.js'
import type { SessionMessage, ContentBlock, DisplayMessage } from '../types/index.js'

let historyCounter = 0
function makeHistoryId(): string {
  return `hist_${++historyCounter}`
}

/**
 * Extract plain text from a SessionMessage content field.
 * Content can be a string, or an array of content blocks from the provider.
 */
function extractText(content: string | ContentBlock[]): string {
  if (typeof content === 'string') return content

  const parts: string[] = []
  for (const block of content) {
    if (typeof block === 'string') {
      parts.push(block)
    } else if ('type' in block && block.type === 'text') {
      parts.push(block.text)
    } else if ('content' in block) {
      // Nested content block — recurse
      parts.push(extractText(block.content))
    }
  }
  return parts.join('')
}

/**
 * Extract tool_use blocks from an assistant message's content array.
 * Provider messages use { type: 'tool_use', id, name, input } blocks.
 */
function extractToolCalls(content: string | ContentBlock[]): DisplayMessage['toolCalls'] {
  if (typeof content === 'string') return undefined

  const calls: NonNullable<DisplayMessage['toolCalls']> = []
  for (const block of content) {
    if (typeof block !== 'string' && 'type' in block) {
      const b = block as Record<string, unknown>
      if (b.type === 'tool_use') {
        calls.push({
          id: String(b.id ?? ''),
          name: String(b.name ?? ''),
          input: typeof b.input === 'string' ? b.input : JSON.stringify(b.input ?? {}),
          finished: true,
        })
      }
    }
  }
  return calls.length > 0 ? calls : undefined
}

/**
 * Extract tool_result blocks from a message's content array.
 * These typically appear in user-role messages that follow an assistant tool_use.
 */
function extractToolResults(content: string | ContentBlock[]): DisplayMessage['toolResults'] {
  if (typeof content === 'string') return undefined

  const results: NonNullable<DisplayMessage['toolResults']> = []
  for (const block of content) {
    if (typeof block !== 'string' && 'type' in block) {
      const b = block as Record<string, unknown>
      if (b.type === 'tool_result') {
        results.push({
          toolCallId: String(b.tool_use_id ?? b.toolCallId ?? ''),
          name: String(b.name ?? ''),
          content: typeof b.content === 'string' ? b.content : JSON.stringify(b.content ?? ''),
          isError: Boolean(b.is_error ?? b.isError ?? false),
        })
      }
    }
  }
  return results.length > 0 ? results : undefined
}

/**
 * Extract thinking/reasoning blocks from a message's content array.
 */
function extractThinking(content: string | ContentBlock[]): string | undefined {
  if (typeof content === 'string') return undefined

  const parts: string[] = []
  for (const block of content) {
    if (typeof block !== 'string' && 'type' in block) {
      const b = block as Record<string, unknown>
      if (b.type === 'thinking' && typeof b.thinking === 'string') {
        parts.push(b.thinking)
      }
    }
  }
  return parts.length > 0 ? parts.join('\n') : undefined
}

/**
 * Convert a raw SessionMessage from the daemon into a DisplayMessage.
 * Handles both simple string content and complex content block arrays.
 */
function toDisplayMessage(msg: SessionMessage, index: number): DisplayMessage | null {
  const role = msg.role
  // Skip system messages from history (they're internal context)
  if (role === 'system') return null

  // Skip user messages that are purely tool results (no user-visible text)
  if (role === 'user' && Array.isArray(msg.content)) {
    const hasToolResults = (msg.content as unknown[]).some(
      (b) => typeof b === 'object' && b !== null && (b as Record<string, unknown>).type === 'tool_result',
    )
    const text = extractText(msg.content)
    if (hasToolResults && !text.trim()) return null
  }

  const text = extractText(msg.content)
  const toolCalls = role === 'assistant' ? extractToolCalls(msg.content) : undefined
  const toolResults = role === 'assistant' ? extractToolResults(msg.content) : undefined
  const thinking = role === 'assistant' ? extractThinking(msg.content) : undefined

  return {
    id: makeHistoryId(),
    role: role as 'user' | 'assistant',
    content: text,
    timestamp: Date.now() - (1000 * (1000 - index)), // Approximate ordering
    thinking,
    toolCalls,
    toolResults,
  }
}

export interface UseSessionHistoryReturn {
  /** Loaded messages from history. */
  messages: DisplayMessage[]
  /** Whether history is currently loading. */
  loading: boolean
  /** Error message if loading failed. */
  error: string | null
  /** Manually reload history for the current session. */
  reload: () => Promise<void>
}

export function useSessionHistory(sessionId: string): UseSessionHistoryReturn {
  const client = useDaemon()
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loadedSessionRef = useRef<string>('')

  const load = useCallback(async () => {
    if (!sessionId) return
    // Don't reload if we already loaded this session
    if (loadedSessionRef.current === sessionId) return

    setLoading(true)
    setError(null)

    try {
      const raw = await client.sessionMessages(sessionId, 200)
      const display = raw
        .map((msg, i) => toDisplayMessage(msg, i))
        .filter((m): m is DisplayMessage => m !== null)

      setMessages(display)
      loadedSessionRef.current = sessionId
    } catch (err) {
      // Session may not exist yet (new session) — that's fine
      setMessages([])
      setError(String(err))
      loadedSessionRef.current = sessionId
    } finally {
      setLoading(false)
    }
  }, [client, sessionId])

  // Load on mount and when sessionId changes
  useEffect(() => {
    loadedSessionRef.current = '' // Reset so we reload
    void load()
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(async () => {
    loadedSessionRef.current = '' // Force reload
    await load()
  }, [load])

  return { messages, loading, error, reload }
}
