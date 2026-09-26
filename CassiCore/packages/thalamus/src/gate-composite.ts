import type { SystemLuminanceScore } from './vendor/core/intelligence/workspace/cognitive-signal.js';
import type { BrainContext, ScoredMessage } from './types.js';

/**
 * Gate-shaped composite scorer (Stage 2, off by default).
 *
 * Replaces ONLY the static-weights composite in `MessageLuminanceScorer.scoreAll`
 * (the per-axis scores are unchanged). Idea from the Cassi gate: a message's
 * composite shouldn't be a fixed weighted average — when the discourse is
 * attractor-locked toward the current focus (high phase-coherence), the
 * relevance axis should dominate; when exploring, attention should widen
 * toward novelty/strategic axes.
 *
 * q_weight(relevance) = base(relevance) * (0.5 + pc), renormalized so the six
 * weights still sum to 1 — a ke-ring notion (one channel's dominance restrains
 * its counterpart) applied to the score axes, preserving a probability-like
 * budget. This is the same discipline as the δ-scheduler: the WEIGHTS move by a
 * derived law, never tuned per-transcript.
 *
 * Not wired in by default: `intelligence.thalamus.gateComposite` must be `cascade`
 * to select it. See plan §14 (pre-registered A/B). Field-openness modulation
 * (the live (1−q) term) is deliberately out of scope here — Stage 4.
 */

const BASE_WEIGHTS = {
  novelty: 0.10,
  urgency: 0.12,
  relevance: 0.35,
  sourceCredibility: 0.13,
  cognitiveResonance: 0.15,
  strategicImportance: 0.15,
} as const;

export class GateCompositeScorer {
  /**
   * Recompute composites for an already-scored set. `ctx` supplies the phase
   * coherence. Returns a NEW array (does not mutate input for bit-identical
   * parity when disabled).
   */
  reweight(scored: ScoredMessage[], ctx: BrainContext): ScoredMessage[] {
    const pc = Math.max(0, Math.min(1, ctx.phaseCoherence ?? 1.0));
    const out: ScoredMessage[] = new Array(scored.length);

    for (let i = 0; i < scored.length; i++) {
      const sm = scored[i];
      // Keep the all-ones sentinel (protected messages) untouched.
      if (this.isProtected(sm.luminance)) {
        out[i] = sm;
        continue;
      }
      const weights = this.gateWeights(pc);
      const l = sm.luminance;
      const composite = Math.min(
        1,
        weights.novelty * l.novelty +
          weights.urgency * l.urgency +
          weights.relevance * l.relevance +
          weights.sourceCredibility * l.sourceCredibility +
          weights.cognitiveResonance * l.cognitiveResonance +
          weights.strategicImportance * l.strategicImportance,
      );
      out[i] = { messageIndex: sm.messageIndex, estimatedChars: sm.estimatedChars, luminance: { ...l, composite } };
    }
    return out;
  }

  /** Derived, normalized weights under a given phase-coherence (the six axes; composite is computed). */
  private gateWeights(pc: number): Record<Exclude<keyof SystemLuminanceScore, 'composite'>, number> {
    const rel = BASE_WEIGHTS.relevance * (0.5 + pc);
    const othersTotal = BASE_WEIGHTS.novelty + BASE_WEIGHTS.urgency + BASE_WEIGHTS.sourceCredibility +
      BASE_WEIGHTS.cognitiveResonance + BASE_WEIGHTS.strategicImportance;
    const scale = (1 - rel) / othersTotal;
    return {
      novelty: BASE_WEIGHTS.novelty * scale,
      urgency: BASE_WEIGHTS.urgency * scale,
      relevance: rel,
      sourceCredibility: BASE_WEIGHTS.sourceCredibility * scale,
      cognitiveResonance: BASE_WEIGHTS.cognitiveResonance * scale,
      strategicImportance: BASE_WEIGHTS.strategicImportance * scale,
    };
  }

  private isProtected(l: SystemLuminanceScore): boolean {
    return l.novelty === 1 && l.urgency === 1 && l.relevance === 1 &&
      l.sourceCredibility === 1 && l.cognitiveResonance === 1 && l.strategicImportance === 1;
  }
}
