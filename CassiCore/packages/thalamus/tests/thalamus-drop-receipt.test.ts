/**
 * Tests for the drop-receipt module — verify that curation generates accurate,
 * terse, and noteworthy receipts. The receipt is the visibility mechanism for
 * silent message removal, so its correctness is load-bearing.
 */

import { describe, it, expect } from 'vitest'
import {
  buildDropReceipt,
  renderDropReceiptBlock,
  type BuildReceiptInput,
} from '../src/drop-receipt.js'
import type { ScoredMessage, ThalamusAnnotation, RerankerCompressionCache } from '../src/types.js'

const ts = '2026-04-29T10:00:00.000Z'

function ann(slot: ThalamusAnnotation['slot'], chars: number, extra: Partial<ThalamusAnnotation> = {}): ThalamusAnnotation {
  return { ts, slot, chars, ...extra }
}

function mkUser(content: string): any {
  return { role: 'user', content, _thalamus: ann('user', content.length) }
}

function mkAssistant(content: string): any {
  return { role: 'assistant', content, _thalamus: ann('assistant', content.length) }
}

function mkToolResult(content: string): any {
  return {
    role: 'user',
    content: [{ type: 'tool_result', tool_use_id: 'toolu_x', content }],
    _thalamus: ann('tool_result', content.length, { tool: { name: 'read', class: 'fs', durationMs: 0, outputBytes: content.length, isError: false } }),
  }
}

function scoreFor(messages: any[]): ScoredMessage[] {
  return messages.map((_, i) => ({
    messageIndex: i,
    luminance: { composite: 0.1, prior: 0.5, urgency: 0.1, credibility: 0.5, focus: 0, confirmation: 0 } as any,
    estimatedChars: messages[i]?._thalamus?.chars ?? 0,
  }))
}

function input(messages: any[], includedIndices: Set<number>, protectedIndices: Set<number> = new Set()): BuildReceiptInput {
  const charsUsed = [...includedIndices].reduce((sum, i) => sum + (messages[i]?._thalamus?.chars ?? 0), 0)
  return {
    before: messages,
    scored: scoreFor(messages),
    includedIndices,
    protectedIndices,
    charBudget: 100_000,
    charsUsed,
  }
}

describe('buildDropReceipt', () => {
  it('returns receipt with dropped:0 when nothing was dropped', () => {
    const messages = [mkUser('hi')]
    const receipt = buildDropReceipt(input(messages, new Set([0])))
    expect(receipt).not.toBeNull()
    expect(receipt!.dropped).toBe(0)
  })

  it('summarizes a small drop set with per-slot breakdown', () => {
    const messages = [
      mkUser('original directive'),
      mkAssistant('chatter that was scored low'),
      mkToolResult('big tool output'),
      mkUser('the latest user prompt'),
    ]
    const receipt = buildDropReceipt(input(messages, new Set([0, 3])))
    expect(receipt).not.toBeNull()
    expect(receipt!.dropped).toBe(2)
    expect(receipt!.bySlot.assistant).toBe(1)
    expect(receipt!.bySlot.tool_result).toBe(1)
    expect(receipt!.summary).toContain('2 message')
    expect(receipt!.summary.toLowerCase()).toMatch(/assistant|tool_result/)
  })

  it('does not count protected indices as dropped', () => {
    const messages = [mkUser('a'), mkAssistant('b'), mkUser('c')]
    const receipt = buildDropReceipt(input(messages, new Set([0]), new Set([2])))
    expect(receipt).not.toBeNull()
    expect(receipt!.dropped).toBe(1) // only index 1, since 2 is protected
  })

  it('flags a recent dropped user message as anomalous', () => {
    const messages = [
      mkUser('directive 1'),
      mkUser('directive 2'),
      mkUser('directive 3'),
      mkUser('latest user message'),
    ]
    const receipt = buildDropReceipt(input(messages, new Set([0, 3])))
    expect(receipt).not.toBeNull()
    const joined = receipt!.anomalies.join(' ').toLowerCase()
    expect(joined).toContain('user')
  })

  it('flags pinned overrides when a pinned message is dropped', () => {
    const pinned = mkUser('pinned answer')
    pinned._thalamus.pinned = true
    pinned._thalamus.pinReason = 'AskUserQuestion'
    const messages = [mkUser('a'), pinned, mkUser('latest')]
    const receipt = buildDropReceipt(input(messages, new Set([0, 2])))
    expect(receipt).not.toBeNull()
    const joined = receipt!.anomalies.join(' ').toLowerCase()
    expect(joined).toMatch(/pin/)
  })
})

describe('renderDropReceiptBlock', () => {
  it('returns a compact text block with summary and recovery hint', () => {
    const messages = [mkUser('a'), mkAssistant('b')]
    const receipt = buildDropReceipt(input(messages, new Set([0])))!
    const out = renderDropReceiptBlock(receipt)
    expect(out).toContain('thalamus dropped 1 message')
    expect(out.toLowerCase()).toContain('cassi_context')
  })

  it('includes anomaly lines when present', () => {
    const pinned = mkUser('pinned answer')
    pinned._thalamus.pinned = true
    pinned._thalamus.pinReason = 'AskUserQuestion'
    const messages = [mkUser('a'), pinned, mkUser('latest')]
    const receipt = buildDropReceipt(input(messages, new Set([0, 2])))!
    const out = renderDropReceiptBlock(receipt).toLowerCase()
    expect(out).toContain('anomalies')
    expect(out).toMatch(/pin/)
  })

  it('includes reranker compression summary when cache has entries', () => {
    const cache: RerankerCompressionCache = {
      entries: new Map([
        ['toolu_abc123', {
          toolUseId: 'toolu_abc123',
          contentHash: 'hash1',
          originalContent: 'a'.repeat(5000),
          compressedContent: 'b'.repeat(500),
          keptChunks: [
            { text: 'chunk1', startLine: 1, endLine: 10, score: 0.9, summary: 'important lines 1-10' },
            { text: 'chunk2', startLine: 11, endLine: 20, score: 0.8, summary: 'important lines 11-20' },
          ],
          droppedChunks: [],
          totalChunks: 2,
          originalChars: 5000,
          compressedChars: 500,
          timestamp: Date.now(),
        }],
      ]),
      expansions: new Map(),
    }
    const messages = [mkUser('a'), mkToolResult('tool result')]
    const receipt = buildDropReceipt({ ...input(messages, new Set([0, 1])), rerankerCache: cache })!
    expect(receipt.rerankerSummary).toBeDefined()
    expect(receipt.rerankerSummary).toContain('5K → 1K')
    expect(receipt.rerankerSummary).toContain('2/2 chunks')
    expect(receipt.rerankerSummary).toContain('important lines 1-10')
    expect(receipt.rerankerSummary).toContain('cassi_context({action: "expand"')
  })
})
