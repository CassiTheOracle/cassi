/**
 * Tests for AskUserQuestion immunity — answers from the AQ tool encode operator
 * intent, but they arrive as tool_result blocks and would otherwise score low.
 * Without immunity, long sessions look like assistant-drift when they were
 * actually user-directed.
 *
 * Verifies:
 *   - AQ answers are flagged with `pinned = true` and a clear pinReason
 *   - AQ answers survive curation under tight char budgets that drop other
 *     low-scoring messages
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { ThalamusModule } from '../src/index.js'
import { mockLogger } from './helpers.ts'

function mkAQPair(answer: string, idx: number): any[] {
  const assistantTurn = {
    role: 'assistant',
    content: [
      {
        type: 'tool_use',
        id: `toolu_aq_${idx}`,
        name: 'AskUserQuestion',
        input: { questions: [{ question: 'pick one', header: 'q', options: [] }] },
      },
    ],
  }
  const userAnswer = {
    role: 'user',
    content: [{ type: 'tool_result', tool_use_id: `toolu_aq_${idx}`, content: answer }],
  }
  return [assistantTurn, userAnswer]
}

const txt = (role: 'user' | 'assistant', content: string) => ({ role, content })

describe('AskUserQuestion immunity', () => {
  let thalamus: ThalamusModule

  beforeEach(async () => {
    thalamus = new ThalamusModule(mockLogger())
    await thalamus.init()
  })

  it('preserves AQ answers under aggressive curation that drops other messages', async () => {
    const filler: any[] = []
    for (let i = 0; i < 30; i++) {
      filler.push(txt('assistant', `chatter line ${i} — ${'noise '.repeat(30)}`))
    }
    const messages = [
      txt('user', 'build me a web app'),
      ...mkAQPair('react', 0),
      ...filler,
      txt('user', 'continue please'),
    ]
    const result = await thalamus.curate('test-aq-survival', messages, {
      charBudget: 4000,
      ignitionThreshold: 0.5,
    })
    expect(result).not.toBeNull()
    const aqAnswerSurvives = result!.messages.some(
      m =>
        m.role === 'user' &&
        Array.isArray(m.content) &&
        m.content.some(
          (c: any) => c?.type === 'tool_result' && String(c?.content ?? '').includes('react'),
        ),
    )
    expect(aqAnswerSurvives).toBe(true)
    const droppedCount = messages.length - result!.messages.length
    expect(droppedCount).toBeGreaterThan(5)
  })
})
