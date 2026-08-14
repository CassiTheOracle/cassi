import { describe, it, expect } from 'vitest'
import { MessageLuminanceScorer } from '../src/scorer.js'
import { classifyMessage } from '../src/classifier.js'
import { createSlots } from '../src/slots/index.js'
import type { BrainContext, ScoredMessage, SlotContext } from '../src/types.js'
import { MESSAGE_CREDIBILITY_PRIORS } from '../src/types.js'
import { mockLogger } from './helpers.ts'

/**
 * Regression coverage: AskUserQuestion (`question` tool) answers arrive as
 * tool_result blocks but represent user input. The Thalamus must treat them
 * as user messages — same slot routing, same urgency floor, same credibility
 * prior — so they survive PCPM scoring rounds and don't get dropped first
 * during context curation.
 */

function emptyBrainContext(): BrainContext {
  return {
    foci: [],
    workspaceSignals: [],
    focusTerms: new Set(),
    focusFiles: new Set(),
    cortexSignals: [],
    cortexIndex: { byType: {}, byRegion: {}, workingMemory: [], highSalience: [], threats: [] },
    affectState: null,
    workingMemoryTerms: new Set(),
    mnemonicTerms: new Set(),
    architecturalTerms: new Set(),
    architecturalConcepts: new Set(),
    architecturalHits: [],
    pinealTerms: new Set(),
    pinealPriorities: new Map(),
    recentMessageTerms: new Set(),
    recentMessageFiles: new Set(),
    phaseCoherence: 1.0,
  }
}

function questionAnswerMessage(answer: string, ts?: string): any {
  return {
    role: 'user',
    content: [
      {
        type: 'tool_result',
        tool_use_id: 'tu_question_1',
        tool_name: 'question',
        content: answer,
      },
    ],
    ...(ts ? { _thalamus: { ts, slot: 'user', chars: answer.length } } : {}),
  }
}

function bashResultMessage(output: string, ts?: string): any {
  return {
    role: 'user',
    content: [
      {
        type: 'tool_result',
        tool_use_id: 'tu_bash_1',
        tool_name: 'bash',
        content: output,
      },
    ],
    ...(ts
      ? {
          _thalamus: {
            ts,
            slot: 'tool_result',
            chars: output.length,
            tool: { name: 'bash', class: 'shell', durationMs: 10, outputBytes: output.length, isError: false },
          },
        }
      : {}),
  }
}

describe('AskUserQuestion answers — slot routing', () => {
  const slots = createSlots()
  const findSlot = (type: string) => slots.find(s => s.type === type)!

  it('classifyMessage treats question tool_result as a user message', () => {
    const msg = questionAnswerMessage('option B')
    expect(classifyMessage(msg)).toBe('user')
  })

  it('classifyMessage still treats ordinary tool_result as tool_result', () => {
    const msg = bashResultMessage('total 42')
    expect(classifyMessage(msg)).toBe('tool_result')
  })

  it('UserSlot matches question tool_result messages', () => {
    expect(findSlot('user').matches(questionAnswerMessage('A'))).toBe(true)
  })

  it('ToolResultSlot does NOT match question tool_result messages', () => {
    expect(findSlot('tool_result').matches(questionAnswerMessage('A'))).toBe(false)
  })

  it('ToolResultSlot still matches bash tool_result messages', () => {
    expect(findSlot('tool_result').matches(bashResultMessage('hi'))).toBe(true)
  })

  it('classifyMessage resolves question via toolUseMap when tool_name is absent', () => {
    // Anthropic-format tool_result blocks often carry only tool_use_id,
    // not tool_name. Without the map the message would be misclassified
    // as tool_result and routed to ToolResultSlot (no composite recalc).
    const msg = {
      role: 'user',
      content: [
        {
          type: 'tool_result',
          tool_use_id: 'tu_question_2',
          // tool_name deliberately omitted
          content: 'option C',
        },
      ],
    }
    const map = new Map([['tu_question_2', 'question']])
    expect(classifyMessage(msg, map)).toBe('user')
    // Without the map it falls back to tool_result — the old buggy path.
    expect(classifyMessage(msg)).toBe('tool_result')
  })

  it('UserSlot.augment does NOT attach a tool annotation for question answers', () => {
    const slot = findSlot('user')
    const ctx: SlotContext = {
      timestamp: new Date().toISOString(),
      sessionStart: new Date().toISOString(),
      lastUserMessageAt: null,
      toolMetrics: new Map(),
      toolUseMap: new Map(),
      previousMessageTs: null,
    }
    const augmented = slot.augment(questionAnswerMessage('option B'), ctx)
    expect(augmented._thalamus.slot).toBe('user')
    expect(augmented._thalamus.tool).toBeUndefined()
  })
})

describe('AskUserQuestion answers — luminance scoring', () => {
  const scorer = new MessageLuminanceScorer(mockLogger())

  it('credibility for a question answer matches plain user, not user:tool_result', () => {
    const ctx = emptyBrainContext()
    const ts = new Date().toISOString()

    const plainUser: any = {
      role: 'user',
      content: 'I prefer option B because it preserves history.',
      _thalamus: { ts, slot: 'user', chars: 50 },
    }
    const questionAnswer = questionAnswerMessage(
      'I prefer option B because it preserves history.',
      ts,
    )
    const bashResult = bashResultMessage('drwxr-xr-x  3 user user 4096 .', ts)

    const messages = [plainUser, questionAnswer, bashResult]
    // protectedStart > length means none are in the protected (recent) zone,
    // so every message goes through the full luminance path.
    const realScores: ScoredMessage[] = scorer.scoreAll(messages, ctx, messages.length + 1)

    const userPrior = MESSAGE_CREDIBILITY_PRIORS['user'] ?? 0.9
    const toolResultPrior = MESSAGE_CREDIBILITY_PRIORS['user:tool_result'] ?? 0.7

    // Question-answer credibility tracks the plain-user prior.
    expect(realScores[1].luminance.sourceCredibility).toBeCloseTo(
      realScores[0].luminance.sourceCredibility,
      5,
    )
    // The bash tool_result starts from the lower prior — must score below user.
    expect(realScores[2].luminance.sourceCredibility).toBeLessThan(
      realScores[1].luminance.sourceCredibility,
    )
    // Sanity: the user-prior path actually starts above the tool-result prior.
    expect(userPrior).toBeGreaterThan(toolResultPrior)
  })

  it('urgency floor (0.25) applies to question answers, same as plain user', () => {
    const ctx = emptyBrainContext()
    // Old timestamp so temporal urgency naturally decays to ~0.
    const old = new Date(Date.now() - 60 * 60 * 1000).toISOString()

    const plainUser: any = {
      role: 'user',
      content: 'pick option A',
      _thalamus: { ts: old, slot: 'user', chars: 20 },
    }
    const questionAnswer = questionAnswerMessage('pick option A', old)
    const bashResult = bashResultMessage('lots of bash noise output here', old)

    const messages = [plainUser, questionAnswer, bashResult]
    const scores = scorer.scoreAll(messages, ctx, messages.length + 1)

    // User and question-answer hit the 0.25 user-role floor (raised from 0.15
    // in the in-flight scorer.ts change to give user-directed content more
    // headroom before getting filtered).
    expect(scores[0].luminance.urgency).toBeCloseTo(0.25, 2)
    expect(scores[1].luminance.urgency).toBeCloseTo(0.25, 2)
    // Plain bash tool_result decays past the floor and lands lower.
    expect(scores[2].luminance.urgency).toBeLessThan(scores[1].luminance.urgency)
  })

  it('composite luminance ranks question answer above bash tool noise', () => {
    const ctx = emptyBrainContext()
    const old = new Date(Date.now() - 60 * 60 * 1000).toISOString()

    const messages = [
      questionAnswerMessage('use the second approach', old),
      bashResultMessage('noisy build output we do not care about', old),
    ]

    const scores = scorer.scoreAll(messages, ctx, messages.length + 1)
    expect(scores[0].luminance.composite).toBeGreaterThan(scores[1].luminance.composite)
  })

  it('user messages survive phase transitions via composite floor', () => {
    // Simulate a harsh phase transition: zero relevance, zero novelty,
    // zero resonance. The UserSlot.adjustScore floor must still keep
    // the composite above the default ignition threshold (0.20).
    const slot = createSlots().find(s => s.type === 'user')!
    const score = {
      novelty: 0,
      urgency: 0.02,
      relevance: 0,
      sourceCredibility: 0.20,
      composite: 0.05,
    }
    const adjusted = slot.adjustScore(score, {
      ts: new Date().toISOString(),
      slot: 'user',
      chars: 20,
    })
    expect(adjusted.composite).toBeGreaterThanOrEqual(0.25)
  })
})
