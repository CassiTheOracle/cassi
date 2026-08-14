/**
 * Tests for SDK event-mapper context health capture.
 *
 * Validates that session.usage_info, session.truncation,
 * session.compaction_start, and session.compaction_complete events
 * are correctly captured into SdkTurnState.contextHealth.
 */

import { describe, it, expect, vi } from 'vitest'
import { createTurnState, mapSdkEvent, type SdkTurnState, type SdkContextHealth } from '../../src/copilot-sdk/event-mapper.js'
import type { IEventBus } from '@cassicore/foundation'

function makeMockBus(): IEventBus & { emitted: Array<{ type: string; [key: string]: any }> } {
  const emitted: Array<{ type: string; [key: string]: any }> = []
  return {
    emit: (event: any) => { emitted.push(event) },
    on: vi.fn().mockReturnValue(() => {}),
    once: vi.fn(),
    off: vi.fn(),
    listenerCount: vi.fn().mockReturnValue(0),
    onAll: vi.fn().mockReturnValue(() => {}),
    emitted,
  } as any
}

function makeEvent(type: string, data: any): any {
  return { type, data, id: 'test', timestamp: new Date().toISOString(), parentId: null }
}

describe('mapSdkEvent — context health capture', () => {
  it('should populate contextHealth from session.usage_info event', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    const done = mapSdkEvent(
      makeEvent('session.usage_info', {
        tokenLimit: 200000,
        currentTokens: 80000,
        messagesLength: 25,
      }),
      state,
      bus,
    )

    expect(done).toBe(false)
    expect(state.contextHealth).toBeDefined()
    expect(state.contextHealth!.tokenLimit).toBe(200000)
    expect(state.contextHealth!.currentTokens).toBe(80000)
    expect(state.contextHealth!.fillLevel).toBeCloseTo(0.40)
    expect(state.contextHealth!.messagesLength).toBe(25)
    expect(state.contextHealth!.isCompacting).toBe(false)
  })

  it('should update existing contextHealth on subsequent usage_info events', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 80000, messagesLength: 20,
    }), state, bus)

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 120000, messagesLength: 30,
    }), state, bus)

    expect(state.contextHealth!.currentTokens).toBe(120000)
    expect(state.contextHealth!.fillLevel).toBeCloseTo(0.60)
    expect(state.contextHealth!.messagesLength).toBe(30)
  })

  it('should set isCompacting on compaction_start', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 160000, messagesLength: 40,
    }), state, bus)

    mapSdkEvent(makeEvent('session.compaction_start', {}), state, bus)

    expect(state.contextHealth!.isCompacting).toBe(true)
  })

  it('should handle compaction_complete with success', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 160000, messagesLength: 40,
    }), state, bus)

    mapSdkEvent(makeEvent('session.compaction_start', {}), state, bus)
    expect(state.contextHealth!.isCompacting).toBe(true)

    mapSdkEvent(makeEvent('session.compaction_complete', {
      success: true,
      preCompactionTokens: 160000,
      postCompactionTokens: 80000,
      messagesRemoved: 15,
      tokensRemoved: 80000,
      summaryContent: 'Summarized conversation about refactoring.',
    }), state, bus)

    expect(state.contextHealth!.isCompacting).toBe(false)
    expect(state.contextHealth!.compactionsDuringTurn).toBe(1)
    expect(state.contextHealth!.tokensRecoveredByCompaction).toBe(80000)
    expect(state.contextHealth!.currentTokens).toBe(80000)
    expect(state.contextHealth!.fillLevel).toBeCloseTo(0.40)
    expect(state.contextHealth!.compactionSummary).toBe('Summarized conversation about refactoring.')
  })

  it('should emit provider:request_error on compaction failure', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 180000, messagesLength: 50,
    }), state, bus)

    mapSdkEvent(makeEvent('session.compaction_complete', {
      success: false,
      error: 'LLM timeout during compaction',
    }), state, bus)

    const errorEvents = bus.emitted.filter(e => (e as any).type === 'provider:request_error')
    expect(errorEvents).toHaveLength(1)
    expect((errorEvents[0] as any).error).toContain('Compaction failed')
    expect((errorEvents[0] as any).error).toContain('LLM timeout')
  })

  it('should track truncation events', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 190000, messagesLength: 60,
    }), state, bus)

    mapSdkEvent(makeEvent('session.truncation', {
      tokenLimit: 200000,
      preTruncationTokensInMessages: 190000,
      preTruncationMessagesLength: 60,
      postTruncationTokensInMessages: 140000,
      postTruncationMessagesLength: 45,
      tokensRemovedDuringTruncation: 50000,
      messagesRemovedDuringTruncation: 15,
      performedBy: 'BasicTruncator',
    }), state, bus)

    expect(state.contextHealth!.truncationsDuringTurn).toBe(1)
    expect(state.contextHealth!.tokensRemovedByTruncation).toBe(50000)
    expect(state.contextHealth!.currentTokens).toBe(140000)
    expect(state.contextHealth!.fillLevel).toBeCloseTo(0.70)
    expect(state.contextHealth!.messagesLength).toBe(45)
  })

  it('should handle zero tokenLimit gracefully', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 0, currentTokens: 0, messagesLength: 0,
    }), state, bus)

    expect(state.contextHealth!.fillLevel).toBe(0)
  })

  it('should accumulate multiple compaction/truncation events in one turn', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('session.usage_info', {
      tokenLimit: 200000, currentTokens: 180000, messagesLength: 50,
    }), state, bus)

    mapSdkEvent(makeEvent('session.compaction_complete', {
      success: true, preCompactionTokens: 180000, postCompactionTokens: 120000,
    }), state, bus)

    mapSdkEvent(makeEvent('session.truncation', {
      tokenLimit: 200000,
      postTruncationTokensInMessages: 100000,
      postTruncationMessagesLength: 30,
      tokensRemovedDuringTruncation: 20000,
    }), state, bus)

    expect(state.contextHealth!.compactionsDuringTurn).toBe(1)
    expect(state.contextHealth!.truncationsDuringTurn).toBe(1)
    expect(state.contextHealth!.tokensRecoveredByCompaction).toBe(60000)
    expect(state.contextHealth!.tokensRemovedByTruncation).toBe(20000)
    expect(state.contextHealth!.currentTokens).toBe(100000)
  })
})

describe('mapSdkEvent — tool call tracking', () => {
  it('should track tool calls from execution_start to execution_complete', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('tool.execution_start', {
      toolCallId: 'tc-1',
      toolName: 'read_file',
    }), state, bus)

    expect(state.toolCalls).toHaveLength(0)

    mapSdkEvent(makeEvent('tool.execution_complete', {
      toolCallId: 'tc-1',
      success: true,
      result: { content: 'file contents here' },
    }), state, bus)

    expect(state.toolCalls).toHaveLength(1)
    expect(state.toolCalls[0].name).toBe('read_file')
    expect(state.toolCalls[0].durationMs).toBeGreaterThanOrEqual(0)

    expect(state.toolOutputs).toHaveLength(1)
    expect(state.toolOutputs[0].tool_name).toBe('read_file')
    expect(state.toolOutputs[0].output).toBe('file contents here')
    expect(state.toolOutputs[0].is_error).toBe(false)
  })

  it('should handle execution_complete without matching start', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('tool.execution_complete', {
      toolCallId: 'tc-orphan',
      success: false,
      result: { content: 'error' },
    }), state, bus)

    expect(state.toolCalls).toHaveLength(1)
    expect(state.toolCalls[0].name).toBe('sdk-tool')
    expect(state.toolCalls[0].durationMs).toBe(0)
    expect(state.toolOutputs[0].is_error).toBe(true)
  })

  it('should track multiple tool calls', () => {
    const state = createTurnState('test-session')
    const bus = makeMockBus()

    mapSdkEvent(makeEvent('tool.execution_start', { toolCallId: 'tc-1', toolName: 'read_file' }), state, bus)
    mapSdkEvent(makeEvent('tool.execution_complete', { toolCallId: 'tc-1', success: true, result: { content: 'ok' } }), state, bus)

    mapSdkEvent(makeEvent('tool.execution_start', { toolCallId: 'tc-2', toolName: 'memory_search' }), state, bus)
    mapSdkEvent(makeEvent('tool.execution_complete', { toolCallId: 'tc-2', success: true, result: { content: 'found' } }), state, bus)

    expect(state.toolCalls).toHaveLength(2)
    expect(state.toolCalls[0].name).toBe('read_file')
    expect(state.toolCalls[1].name).toBe('memory_search')
  })
})
