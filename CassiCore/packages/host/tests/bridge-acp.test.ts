/**
 * Unit tests for the ACP bridge translator.
 *
 * Pure event-shape coverage — does not require a daemon.
 */

import { describe, it, expect } from 'vitest'

import {
  chatEventToSessionUpdate,
  extractPromptText,
} from '../src/bridge/acp/translator.js'
import type { ChatStreamEvent } from '../src/bridge/acp/types.js'

const SID = 'test-session-id'

describe('chatEventToSessionUpdate', () => {
  it('maps a token event to an agent_message_chunk text content block', () => {
    const evt: ChatStreamEvent = { type: 'token', token: 'Hello, ' }
    const out = chatEventToSessionUpdate(evt, SID)
    expect(out).toEqual({
      sessionId: SID,
      update: {
        sessionUpdate: 'agent_message_chunk',
        content: { type: 'text', text: 'Hello, ' },
      },
    })
  })

  it('maps a tool_call event to a tool_call session update', () => {
    const evt: ChatStreamEvent = {
      type: 'tool_call',
      tool: 'cassi_memory',
      input: { action: 'search', query: 'test' },
    }
    const out = chatEventToSessionUpdate(evt, SID)
    expect(out?.sessionId).toBe(SID)
    if (!out) throw new Error('expected non-null')
    const update = out.update as Record<string, unknown>
    expect(update.sessionUpdate).toBe('tool_call')
    expect(update.title).toBe('cassi_memory')
    expect(update.rawInput).toEqual({ action: 'search', query: 'test' })
  })

  it('uses the daemon-provided toolCallId when present', () => {
    const evt: ChatStreamEvent = {
      type: 'tool_call',
      toolCallId: 'tool_call_42',
      tool: 'cassi_cortex',
      input: { action: 'signal' },
    }
    const out = chatEventToSessionUpdate(evt, SID)
    expect(out?.update).toMatchObject({
      sessionUpdate: 'tool_call',
      toolCallId: 'tool_call_42',
      title: 'cassi_cortex',
    })
  })

  it('maps a tool_result event to a tool_call_update with completed status', () => {
    const evt: ChatStreamEvent = {
      type: 'tool_result',
      toolCallId: 'tool_call_42',
      tool: 'cassi_cortex',
      isError: false,
      content: 'ok',
    }
    const out = chatEventToSessionUpdate(evt, SID)
    expect(out?.sessionId).toBe(SID)
    expect(out?.update).toMatchObject({
      sessionUpdate: 'tool_call_update',
      toolCallId: 'tool_call_42',
      status: 'completed',
    })
  })

  it('marks a failed tool_result as failed and serializes structured content', () => {
    const evt: ChatStreamEvent = {
      type: 'tool_result',
      toolCallId: 'tool_call_99',
      isError: true,
      content: { error: 'boom' },
    }
    const out = chatEventToSessionUpdate(evt, SID)
    const update = out?.update as { sessionUpdate: string; status?: string; content?: unknown }
    expect(update.sessionUpdate).toBe('tool_call_update')
    expect(update.status).toBe('failed')
    expect(JSON.stringify(update.content)).toContain('boom')
  })

  it('drops tool_result events that lack a toolCallId (cannot correlate)', () => {
    const evt: ChatStreamEvent = { type: 'tool_result', tool: 'x', content: 'y' }
    expect(chatEventToSessionUpdate(evt, SID)).toBeNull()
  })

  it('returns undefined for terminal done events (handled by stop reason)', () => {
    expect(chatEventToSessionUpdate({ type: 'done' }, SID)).toBeUndefined()
  })

  it('returns null for error events (handled by promise rejection)', () => {
    expect(chatEventToSessionUpdate({ type: 'error', error: 'boom' }, SID)).toBeNull()
  })
})

describe('extractPromptText', () => {
  it('joins consecutive text content blocks', () => {
    const blocks = [
      { type: 'text', text: 'Hello, ' },
      { type: 'text', text: 'world!' },
    ]
    expect(extractPromptText(blocks)).toBe('Hello, world!')
  })

  it('skips non-text content blocks', () => {
    const blocks = [
      { type: 'text', text: 'caption: ' },
      { type: 'image' as const },
      { type: 'text', text: 'a sunset' },
    ] as Array<{ type: string; text?: string }>
    expect(extractPromptText(blocks)).toBe('caption: a sunset')
  })

  it('returns an empty string for empty input', () => {
    expect(extractPromptText([])).toBe('')
  })

  it('returns an empty string when no text blocks are present', () => {
    expect(extractPromptText([{ type: 'image' }] as Array<{ type: string; text?: string }>)).toBe('')
  })
})
