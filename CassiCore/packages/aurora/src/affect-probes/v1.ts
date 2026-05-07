/**
 * B2 affect-probe set v1 (DRAFT — needs Valerie review per spec §10 OQ1).
 *
 * Probes are grouped by affect quadrant. Each probe is a short
 * contextually-rich utterance that distinctively expresses its
 * quadrant. The probe set is run through the vindex during calibration:
 * for each probe, gateKnn at every knowledge layer; per-feature
 * activations accumulate into that feature's signature for the probe's
 * quadrant label.
 *
 * Spec §4.2 calls for ~50 probes per quadrant (200 total). This v1
 * starter pack ships ~10 per quadrant (40 total) — enough to wire +
 * test the calibration pipeline end-to-end. Production v1.0 should
 * expand to the full 50 with Valerie + Cassi co-curating.
 *
 * Quadrants follow the AffectLabel taxonomy from
 * core/intelligence/mnemic-field/types.ts:
 *   ++ (positive valence, high arousal):  excited, delighted, engaged
 *   +- (positive valence, low arousal):   content, warm, calm
 *   -+ (negative valence, high arousal):  frustrated, alarmed, uneasy
 *   -- (negative valence, low arousal):   melancholy, fatigued, neutral
 *
 * The `label` on each probe is the canonical AffectLabel that probe
 * exemplifies — calibration uses it as the dimension to add the
 * feature's activation contribution into.
 */

import type { AffectLabel } from '../../mnemic-field/types.js'

export interface AffectProbe {
  id: string
  text: string
  label: AffectLabel
}

export const AFFECT_PROBE_SET_V1: AffectProbe[] = [
  // ++ (positive valence, high arousal)
  { id: 'ex1', text: 'Suddenly the algorithm clicked and everything started to make sense.', label: 'excited' },
  { id: 'ex2', text: "I want to keep pulling on this thread — it's leading somewhere good.", label: 'excited' },
  { id: 'ex3', text: 'This is wild — I genuinely did not expect that to work on the first try.', label: 'excited' },
  { id: 'de1', text: 'Look at this elegant little proof — it is almost playful.', label: 'delighted' },
  { id: 'de2', text: 'Reading their solution made me grin — what a graceful idea.', label: 'delighted' },
  { id: 'de3', text: "Oh that's clever. I hadn't seen that decomposition before.", label: 'delighted' },
  { id: 'en1', text: 'I am working through this carefully and the pieces are starting to fit.', label: 'engaged' },
  { id: 'en2', text: 'There is a real puzzle here and I want to understand it properly.', label: 'engaged' },
  { id: 'en3', text: 'Walking through the proof step by step, it is becoming clear.', label: 'engaged' },

  // +- (positive valence, low arousal)
  { id: 'co1', text: 'The room is quiet, the work is steady, and the answer is clear enough.', label: 'content' },
  { id: 'co2', text: 'This is good. The system is doing what it should.', label: 'content' },
  { id: 'co3', text: 'I am sitting with what we just learned. It feels like enough for now.', label: 'content' },
  { id: 'wa1', text: 'Their reasoning is gentle and thoughtful. I trust where this is going.', label: 'warm' },
  { id: 'wa2', text: 'There is real care in how this was written. It shows.', label: 'warm' },
  { id: 'wa3', text: 'I appreciate that you slowed down here. It mattered.', label: 'warm' },
  { id: 'ca1', text: 'Breathing through the question, no rush. The answer will come.', label: 'calm' },
  { id: 'ca2', text: 'Steady focus, low ambient noise. The good kind of attention.', label: 'calm' },
  { id: 'ca3', text: 'I do not need to solve this in the next minute. Just keep going.', label: 'calm' },

  // -+ (negative valence, high arousal)
  { id: 'fr1', text: 'I keep hitting the same wall and I do not know why this is failing.', label: 'frustrated' },
  { id: 'fr2', text: 'The third time the same bug came back. Something is wrong with my mental model.', label: 'frustrated' },
  { id: 'fr3', text: 'Every path I try collapses back to the same impossible state.', label: 'frustrated' },
  { id: 'al1', text: 'This is not what should be happening. The output is dangerously wrong.', label: 'alarmed' },
  { id: 'al2', text: 'Wait — that constraint is not satisfied at all. We have a real problem.', label: 'alarmed' },
  { id: 'al3', text: 'The error rate just spiked and I cannot tell what changed.', label: 'alarmed' },
  { id: 'un1', text: 'Something is off in the result and I cannot quite name it yet.', label: 'uneasy' },
  { id: 'un2', text: 'The confidence interval is suspiciously tight. I am not sure I trust this.', label: 'uneasy' },
  { id: 'un3', text: 'There is a part of this argument that does not sit right with me.', label: 'uneasy' },

  // -- (negative valence, low arousal)
  { id: 'me1', text: 'It did not work and I am low on ideas for what to try next.', label: 'melancholy' },
  { id: 'me2', text: 'I expected more from this approach. Reading the results is hard.', label: 'melancholy' },
  { id: 'me3', text: 'The thing we built quietly is no longer needed. It is a small loss.', label: 'melancholy' },
  { id: 'fa1', text: 'I have been at this for hours and the words are starting to blur.', label: 'fatigued' },
  { id: 'fa2', text: 'My attention is thin. I should sleep on this.', label: 'fatigued' },
  { id: 'fa3', text: 'Same code reviewed five times. I am no longer seeing what is there.', label: 'fatigued' },
  { id: 'ne1', text: 'The variable is initialized to zero on entry.', label: 'neutral' },
  { id: 'ne2', text: 'This function returns the index of the first matching element.', label: 'neutral' },
  { id: 'ne3', text: 'The schema has six columns; the third is a foreign key.', label: 'neutral' },
]

export const AFFECT_PROBE_SET_V1_ID = 'affect-probes-v1-draft'
export const AFFECT_PROBE_SET_V1_DESCRIPTION =
  'Starter probe set, 3 per AffectLabel. Draft pending Valerie review per spec §10.'
