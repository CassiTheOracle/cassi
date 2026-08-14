/**
 * Dialectic Thought Formatter
 *
 * Converts a DialecticStructuredResult into natural inner-monologue prose,
 * suitable for injection as an assistant message. The model sees it as
 * its own prior reasoning about the user's question — not as external
 * instructions.
 *
 * Design principles:
 *   - No labels like "Yang:" or "Yin:" — those are structural artifacts
 *   - No JSON, no bullet points, no numbered lists
 *   - Natural thought flow: explore → ground → decide
 *   - Conversational but precise — how a thoughtful person actually thinks
 *   - Tension and disagreement are preserved, not smoothed over
 */

import type { DialecticStructuredResult } from '../../../types/dialectic-engine.js'

/**
 * Format a DialecticStructuredResult as inner-monologue prose.
 *
 * The output reads as if the assistant paused to think through the problem
 * before responding. This is injected as an assistant message so the model
 * treats it as its own established reasoning.
 */
export function formatDialecticAsThoughts(result: DialecticStructuredResult): string {
  const parts: string[] = []

  // Opening: the expansive exploration
  if (result.yang.response) {
    parts.push(
      `Let me think through this carefully. ${result.yang.response}`
    )

    // Weave in high-novelty branches as exploratory tangents
    const interestingBranches = result.yang.branches
      .filter(b => b.novelty > 0.5 || b.confidence > 0.7)
      .slice(0, 2)

    for (const branch of interestingBranches) {
      const connector = branch.type === 'edge_case'
        ? 'There\'s an edge case worth considering:'
        : branch.type === 'assumption_challenge'
          ? 'Actually, I should question an assumption here:'
          : branch.type === 'cross_domain'
            ? 'This connects to something broader:'
            : branch.type === 'what_if'
              ? 'What if I\'m looking at this wrong —'
              : 'Something else comes to mind:'

      parts.push(`${connector} ${branch.content}`)
    }
  }

  // Grounding: the reality check
  if (result.yin.response) {
    const tension = result.quality.tension

    // Higher tension = more explicit disagreement with the expansive view
    if (tension > 0.6) {
      parts.push(
        `But wait — stepping back and being honest about the constraints: ${result.yin.response}`
      )
    } else if (tension > 0.3) {
      parts.push(
        `That said, I need to ground this. ${result.yin.response}`
      )
    } else {
      parts.push(
        `And this aligns with the practical reality: ${result.yin.response}`
      )
    }

    // Include high-relevance baselines as grounding observations
    const keyBaselines = result.yin.baselines
      .filter(b => b.relevance > 0.6)
      .slice(0, 2)

    for (const baseline of keyBaselines) {
      const framing = baseline.type === 'risk_assessment'
        ? 'A risk I shouldn\'t ignore:'
        : baseline.type === 'constraint'
          ? 'There\'s a real constraint here:'
          : baseline.type === 'reality_check'
            ? 'Being realistic:'
            : 'Worth noting:'

      parts.push(`${framing} ${baseline.content}`)
    }
  }

  // Resolution: Unity's decision
  if (result.unity.output) {
    const { selected, reasoning, comparison, synthesis } = result.unity

    if (selected === 'C' && synthesis) {
      // Custom synthesis — the most interesting case
      parts.push(
        `Weighing both sides: ${reasoning} So the right approach combines ${synthesis.fromYang.toLowerCase()} with ${synthesis.fromYin.toLowerCase()}.${synthesis.novel ? ` And beyond both: ${synthesis.novel}` : ''}`
      )
    } else if (selected === 'A') {
      // Yang won — the expansive view prevailed
      if (comparison.yinStrengths) {
        parts.push(
          `The expansive approach wins here, though the grounded view correctly noted that ${comparison.yinStrengths.toLowerCase()}. ${reasoning}`
        )
      }
    } else if (selected === 'B') {
      // Yin won — the grounded view prevailed
      if (comparison.yangStrengths) {
        parts.push(
          `The practical approach is right here, even though the exploratory view had a point about ${comparison.yangStrengths.toLowerCase()}. ${reasoning}`
        )
      }
    }
  }

  // Signal: if the dialectic surfaced something genuinely noteworthy
  if (result.signal && result.signal.confidence > 0.5) {
    const signalFraming = result.signal.type === 'tension'
      ? 'I\'m noticing a tension I should flag:'
      : result.signal.type === 'gap'
        ? 'There\'s a gap I should address:'
        : result.signal.type === 'assumption'
          ? 'I\'m making an assumption I should be explicit about:'
          : result.signal.type === 'contradiction'
            ? 'I\'m seeing a contradiction:'
            : result.signal.type === 'edge_case'
              ? 'There\'s an edge case that matters:'
              : null

    if (signalFraming) {
      parts.push(`${signalFraming} ${result.signal.content}`)
    }
  }

  // Close with confidence calibration if quality is notable
  if (result.quality.dialecticQuality < 0.4) {
    parts.push(
      'I\'m not very confident in this reasoning — the different perspectives didn\'t produce much clarity. I should be upfront about that.'
    )
  }

  return parts.join('\n\n')
}
