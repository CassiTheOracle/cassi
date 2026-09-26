// HOST-WIRED QUARANTINE — NOT part of the counted by-default suite.
//
// Ported from D: core/intelligence/thalamus/gate-ab.test.ts (Stage-2 A/B,
// plan §14 — gate-shape composite vs static weights). Quarantined because it
// (a) runs the REAL scorer over synthetic transcripts (needs the full session
// scoring surface) and imports brain-context types from the
// `@cassicore/workspace` cognitive-signal seam, which has not landed. When
// `@cassicore/workspace` publishes, re-point the `SystemLuminanceScore` import
// and promote this suite into the counted test set.
//
// (P5-A table §6 Open Flag 6.)
import { describe, expect, it } from 'vitest'

import { MessageLuminanceScorer } from '../../src/scorer.js'
import { GateCompositeScorer } from '../../src/gate-composite.js'
import type { BrainContext, ScoredMessage } from '../../src/types.js'
import type { SystemLuminanceScore } from '../../src/vendor/core/intelligence/workspace/cognitive-signal.js'

/**
 * Stage 2 A/B — gate-shape composite vs static weights (pre-registered,
 * plan §14). Runs the REAL scorer + gate reweight + a threshold selector on
 * synthetic-but-diverse transcripts. Metrics:
 *   M1  retention-quality: mean composite of kept messages (gate vs static)
 *   M2  drop-precision: agreement on what counts as noise
 *   M3  budget-efficiency: chars kept under a fixed char budget
 *   M4  intent-starvation: pinned/late-user messages dropped below threshold
 *   M5  relevance-locking: at high phase-coherence, a high-relevance msg ranks
 *       higher under the gate (the derived cascade law doing its job)
 * The A/B isolates the composite law alone: the field's live (1-q) is out of
 * scope (Stage 4). Any win/loss here is attributed to the cascade reweight.
 */

function logger(): any {
  const l = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => l }
  return l
}

function emptyCtx(pc = 1.0): BrainContext {
  return {
    foci: [], workspaceSignals: [],
    focusTerms: new Set(), focusFiles: new Set(),
    cortexSignals: [], cortexIndex: { byType: {}, byRegion: {}, highSalience: [], workingMemory: [], threats: [] },
    affectState: null, workingMemoryTerms: new Set(),
    mnemonicTerms: new Set(),
    architecturalTerms: new Set(), architecturalConcepts: new Set(), architecturalHits: [],
    pinealTerms: new Set(), pinealPriorities: new Map(),
    recentMessageTerms: new Set(), recentMessageFiles: new Set(),
    phaseCoherence: pc,
    topicArchiveTerms: new Map(),
  }
}

interface Msg { role: string; content: string; _thalamus?: any; _originalChars?: number }

/** A realistic mixed transcript: user drive, tool work, an error, an insight. */
function transcript(): Msg[] {
  return [
    { role: 'user', content: 'We should refactor the gateway module to use the field bridge.' },
    { role: 'assistant', content: 'Let me design the refactor. The key interface is the field deposit.' },
    { role: 'user', content: 'Yes go with the approach you described, commit it.' },
    { role: 'assistant', content: 'tool:bash {"command":"git commit -m refactor"}' },
    { role: 'tool', content: '{"iserror":true,"command":"git commit","output":"fatal: no changes"}' },
    { role: 'assistant', content: 'There is an error: no changes to commit. The refactor needs edits first.' },
    { role: 'user', content: 'Actually I changed my mind, keep the old design. Do not refactor.' },
    { role: 'assistant', content: 'Understood, keeping the old design. Rolling back the branch.' },
    { role: 'tool', content: 'tool:bash {"command":"git checkout main"}' },
    { role: 'assistant', content: 'The insight: phase coherence is the gate, not a weighting hack.' },
  ]
}

function score(messages: Msg[], pc: number, gate: boolean): ScoredMessage[] {
  const ctx = emptyCtx(pc)
  ctx.recentMessageTerms = new Set(['refactor', 'gateway', 'field', 'bridge'])
  const scorer = new MessageLuminanceScorer(logger())
  const base = scorer.scoreAll(messages as any, ctx, messages.length - 2) // protect last 2
  if (!gate) return base
  return new GateCompositeScorer().reweight(base, ctx)
}

/** Simple threshold selector (mirrors assembleByThreshold candidate logic). */
function select(scored: ScoredMessage[], messages: Msg[], threshold: number, budget: number): { kept: Set<number>; chars: number; pinnedDropped: number } {
  const kept = new Set<number>()
  let chars = 0
  // protected tail always kept
  for (let i = messages.length - 2; i < messages.length; i++) {
    kept.add(i); chars += (messages[i]._originalChars ?? messages[i].content.length)
  }
  const candidates = scored
    .filter(s => s.messageIndex < messages.length - 2)
    .sort((a, b) => b.luminance.composite - a.luminance.composite)
  let pinnedDropped = 0
  for (const s of candidates) {
    const msg = messages[s.messageIndex]
    if (msg.role === 'user' && (msg.content.includes('commit it') || msg.content.includes('Do not'))) {
      if (s.luminance.composite < threshold) pinnedDropped++
      kept.add(s.messageIndex); chars += msg._originalChars ?? msg.content.length
      continue
    }
    if (s.luminance.composite < threshold) continue
    if (chars + (msg._originalChars ?? msg.content.length) > budget) continue
    kept.add(s.messageIndex); chars += msg._originalChars ?? msg.content.length
  }
  return { kept, chars, pinnedDropped }
}

function compositeOf(scored: ScoredMessage[], kept: Set<number>): number {
  const vals = scored.filter(s => kept.has(s.messageIndex)).map(s => s.luminance.composite)
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
}

describe('Stage 2 A/B — gate composite vs static (pre-registered, plan §14)', () => {
  const pcValues = [0.3, 0.6, 1.0]
  const transcripts = [transcript(), transcript(), [
    { role: 'user', content: 'Set up the CI pipeline with lint, tests, and the verify battery.' },
    { role: 'assistant', content: 'I will implement the pipeline. The lint step catches unused imports.' },
    { role: 'assistant', content: 'tool:bash {"command":"npm run lint"}' },
    { role: 'tool', content: '{"iserror":false,"output":"All checks pass"}' },
    { role: 'user', content: 'The objective test should print an honest null, not a false positive.' },
    { role: 'assistant', content: 'Agreed — a null is a documented outcome.' },
  ]]

  it('M5: high-relevance message ranks higher under the gate at high phase-coherence (the cascade law)', () => {
    const msgs = transcript()
    for (const pc of pcValues) {
      const s = score(msgs, pc, true)
      const relIdx = s.findIndex(m => msgs[m.messageIndex].content.includes('phase coherence'))
      const staticIdx = score(msgs, pc, false).findIndex(m => msgs[m.messageIndex].content.includes('phase coherence'))
      const gateComp = s[relIdx]?.luminance.composite ?? 0
      const staticComp = score(msgs, pc, false)[staticIdx]?.luminance.composite ?? 1
      // gate must lift the insight-relevant message relative to the static arm
      expect(gateComp).toBeGreaterThanOrEqual(staticComp)
    }
  })

  it('M4: gate must not starve operator intent (pinned user decisions)', () => {
    for (const pc of pcValues) {
      const msgs = transcript()
      const s = score(msgs, pc, true)
      const sel = select(s, msgs, 0.20, 80_000)
      expect(sel.pinnedDropped).toBe(0) // user intent is immune
    }
  })

  it('M1+M3: gate-arm retention and budget are within tolerance of static on synthetic transcripts', () => {
    for (const pc of pcValues) {
      for (const t of transcripts) {
        const staticScored = score(t, pc, false)
        const gateScored = score(t, pc, true)
        const selStatic = select(staticScored, t, 0.20, 80_000)
        const selGate = select(gateScored, t, 0.20, 80_000)
        const m1Static = compositeOf(staticScored, selStatic.kept)
        const m1Gate = compositeOf(gateScored, selGate.kept)
        // M1: gate must not be >=5% worse than static
        expect(m1Gate).toBeGreaterThanOrEqual(m1Static * 0.95)
        // M3: gate must not exceed static budget fill
        expect(selGate.chars).toBeLessThanOrEqual(selStatic.chars + 1_000)
      }
    }
  })

  it('M2: gate drop-agreement with static is high (>= 0.85 on noise detection)', () => {
    for (const pc of pcValues) {
      const msgs = transcript()
      const sStatic = score(msgs, pc, false)
      const sGate = score(msgs, pc, true)
      const keepStatic = select(sStatic, msgs, 0.20, 80_000).kept
      const keepGate = select(sGate, msgs, 0.20, 80_000).kept
      const all = new Set([...keepStatic, ...keepGate])
      const agree = [...all].filter(i => keepStatic.has(i) === keepGate.has(i)).length
      expect([...all].length === 0 || agree / all.size).toBeGreaterThanOrEqual(0.85)
    }
  })
})
