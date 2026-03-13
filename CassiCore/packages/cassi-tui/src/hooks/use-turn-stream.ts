/**
 * Hook for streaming turns through the daemon.
 *
 * Returns `{ sendTurn, text, thinking, toolCalls, toolResults, isStreaming, error }`.
 * Components re-render as tokens arrive (~30fps throttle).
 */

import { useState, useCallback, useRef } from 'react'
import { useDaemon } from './use-daemon.js'
import type {
  TurnEvent,
  TurnTokenEvent,
  TurnThinkingEvent,
  TurnToolCallEvent,
  TurnToolResultEvent,
  TurnDoneEvent,
  TurnErrorEvent,
  DaemonImageAttachment,
} from '../types/index.js'

export interface ToolCall {
  id: string
  name: string
  input: string
  finished: boolean
  /** Timestamp when the tool call started (for duration tracking). */
  startedAt?: number
  /** Timestamp when the tool result arrived. */
  finishedAt?: number
}

export interface ToolResult {
  toolCallId: string
  name: string
  content: string
  isError: boolean
}

export interface TurnStreamState {
  text: string
  thinking: string
  toolCalls: ToolCall[]
  toolResults: ToolResult[]
  isStreaming: boolean
  error: string | null
  tokenCount: number
  inputTokens: number
  outputTokens: number
  lastUsedModel: string | null
}

export interface UseTurnStreamReturn extends TurnStreamState {
  sendTurn: (
    sessionId: string,
    content: string,
    model?: string,
    attachments?: DaemonImageAttachment[],
  ) => Promise<void>
  cancel: () => void
  reset: () => void
}

const INITIAL_STATE: TurnStreamState = {
  text: '',
  thinking: '',
  toolCalls: [],
  toolResults: [],
  isStreaming: false,
  error: null,
  tokenCount: 0,
  inputTokens: 0,
  outputTokens: 0,
  lastUsedModel: null,
}

export function useTurnStream(): UseTurnStreamReturn {
  const client = useDaemon()
  const [state, setState] = useState<TurnStreamState>(INITIAL_STATE)
  const abortRef = useRef<AbortController | null>(null)

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
      setState((prev: TurnStreamState) => ({ ...prev, isStreaming: false }))
  }, [])

  const reset = useCallback(() => {
    cancel()
    setState(INITIAL_STATE)
  }, [cancel])

  const sendTurn = useCallback(
    async (
      sessionId: string,
      content: string,
      model?: string,
      attachments?: DaemonImageAttachment[],
    ) => {
      cancel()

      const controller = new AbortController()
      abortRef.current = controller

      // Reset state for new turn
      setState({ ...INITIAL_STATE, isStreaming: true })

      // Accumulate locally and batch-set state at ~30fps
      let text = ''
      let thinking = ''
      const toolCalls: ToolCall[] = []
      const toolResults: ToolResult[] = []
      let tokenCount = 0
      let inputTokens = 0
      let outputTokens = 0
      let lastUsedModel: string | null = null
      let lastFlush = 0

      const flush = () => {
        setState({
          text,
          thinking,
          toolCalls: [...toolCalls],
          toolResults: [...toolResults],
          isStreaming: true,
          error: null,
          tokenCount,
          inputTokens,
          outputTokens,
          lastUsedModel,
        })
        lastFlush = Date.now()
      }

      const maybeFlush = () => {
        if (Date.now() - lastFlush > 33) flush()
      }

      try {
        const stream = await client.streamTurn(
          sessionId,
          content,
          model,
          attachments,
          controller.signal,
        )

        for await (const event of stream) {
          if (controller.signal.aborted) break
          processEvent(event, { text, thinking, toolCalls, toolResults, tokenCount, inputTokens, outputTokens, lastUsedModel }, (updates) => {
            if (updates.text !== undefined) text = updates.text
            if (updates.thinking !== undefined) thinking = updates.thinking
            if (updates.tokenCount !== undefined) tokenCount = updates.tokenCount
            if (updates.inputTokens !== undefined) inputTokens = updates.inputTokens
            if (updates.outputTokens !== undefined) outputTokens = updates.outputTokens
            if (updates.lastUsedModel !== undefined) lastUsedModel = updates.lastUsedModel
          })
          maybeFlush()
        }

        // Final flush
        setState((prev: TurnStreamState) => ({ ...prev, text, thinking, toolCalls: [...toolCalls], toolResults: [...toolResults], isStreaming: false, tokenCount, inputTokens, outputTokens, lastUsedModel }))
      } catch (err) {
        if (!controller.signal.aborted) {
          setState((prev: TurnStreamState) => ({
            ...prev,
            isStreaming: false,
            error: String(err),
          }))
        }
      }
    },
    [client, cancel],
  )

  return { ...state, sendTurn, cancel, reset }
}

// ── Event processing ────────────────────────────────────────────────────────

interface Accumulators {
  text: string
  thinking: string
  toolCalls: ToolCall[]
  toolResults: ToolResult[]
  tokenCount: number
  inputTokens: number
  outputTokens: number
  lastUsedModel: string | null
}

function processEvent(
  event: TurnEvent,
  acc: Accumulators,
  update: (partial: Partial<Accumulators>) => void,
): void {
  switch (event.type) {
    case 'token': {
      const data = event.data as TurnTokenEvent
      const chunk = data.content ?? data.token ?? ''
      update({ text: acc.text + chunk, tokenCount: acc.tokenCount + 1 })
      break
    }

    case 'thinking': {
      const data = event.data as TurnThinkingEvent
      const chunk = data.content ?? data.token ?? ''
      update({ thinking: acc.thinking + chunk })
      break
    }

    case 'tool_call': {
      const data = event.data as TurnToolCallEvent
      const id = data.id ?? data.toolCallId ?? ''
      const name = data.name ?? data.tool ?? ''
      acc.toolCalls.push({
        id,
        name,
        input: data.input != null ? JSON.stringify(data.input) : '',
        finished: false,
        startedAt: Date.now(),
      })
      break
    }

    case 'tool_result': {
      const data = event.data as TurnToolResultEvent
      const toolCallId = data.toolCallId ?? data.id ?? ''
      const now = Date.now()
      // Mark the corresponding tool call as finished with timestamp
      for (const tc of acc.toolCalls) {
        if (tc.id === toolCallId) {
          tc.finished = true
          tc.finishedAt = now
          if (!data.name) data.name = tc.name
        }
      }
      acc.toolResults.push({
        toolCallId,
        name: data.name ?? '',
        content: data.content,
        isError: data.isError,
      })
      break
    }

    case 'done': {
      const data = event.data as TurnDoneEvent
      if (!acc.text && data.response) {
        update({ text: data.response })
      }
      if (data.model) {
        update({ lastUsedModel: data.model })
      }
      if (data.inputTokens) {
        update({ inputTokens: data.inputTokens })
      }
      if (data.outputTokens) {
        update({ outputTokens: data.outputTokens })
      }
      break
    }

    case 'error': {
      const data = event.data as TurnErrorEvent
      update({ text: acc.text + `\n\n**Error:** ${data.error}` })
      break
    }
  }
}
