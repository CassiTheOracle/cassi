import type { ChatStreamEvent, SessionNotification } from './types.js'

export function chatEventToSessionUpdate(
  event: ChatStreamEvent,
  sessionId: string,
): SessionNotification | null {
  switch (event.type) {
    case 'token':
      return {
        sessionId,
        update: {
          sessionUpdate: 'agent_message_chunk',
          content: { type: 'text', text: event.token },
        },
      }
    case 'response':
      if (!event.text) return null
      return {
        sessionId,
        update: {
          sessionUpdate: 'agent_message_chunk',
          content: { type: 'text', text: event.text },
        },
      }
    case 'tool_call':
      return {
        sessionId,
        update: {
          sessionUpdate: 'tool_call',
          toolCallId: event.toolCallId ?? `cassi-${Date.now()}`,
          title: event.tool,
          rawInput: event.input as Record<string, unknown> | undefined,
        },
      }
    case 'tool_result': {
      if (!event.toolCallId) return null
      const status = event.isError ? 'failed' : 'completed'
      const update: SessionNotification['update'] = {
        sessionUpdate: 'tool_call_update',
        toolCallId: event.toolCallId,
        status,
      }
      if (event.content !== undefined && event.content !== '') {
        const text = typeof event.content === 'string' ? event.content : JSON.stringify(event.content)
        ;(update as { content?: Array<{ type: 'content'; content: { type: 'text'; text: string } }> }).content = [
          { type: 'content', content: { type: 'text', text } },
        ]
      }
      return { sessionId, update }
    }
    case 'error':
      return null
  }
}

export function extractPromptText(prompt: ReadonlyArray<{ type: string; text?: string }>): string {
  const parts: string[] = []
  for (const block of prompt) {
    if (block.type === 'text' && block.text) parts.push(block.text)
  }
  return parts.join('')
}
