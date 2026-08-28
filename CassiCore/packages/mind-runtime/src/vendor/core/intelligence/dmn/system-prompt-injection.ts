/**
 * Format a DMN digest as an `<observers>` block suitable for
 * appending to a main-session system prompt.
 *
 * Returns an empty string when the synthesis has no signal — the block
 * is omitted entirely from the prompt rather than included with an
 * "(empty)" body. Cassi-the-host should not see noise from observers
 * who had nothing to say.
 */

import type { DigestSynthesis } from './digest-cache.js'
import { decayedConfidence } from './digest-cache.js'

export function formatObserversBlock(synthesis: DigestSynthesis | null): string {
  if (!synthesis) return ''
  if (!synthesis.hasSignal || !synthesis.signal) return ''

  const { confidence, elapsedMs, isStale } = decayedConfidence(synthesis)

  if (isStale) return ''

  const { type, content, urgency } = synthesis.signal
  const urgencyTag = urgency ? ` [${urgency}]` : ''
  const originalConf = synthesis.signal.confidence
  // Only show decay detail when confidence has measurably changed
  const confidenceStr = originalConf - confidence > 0.01
    ? `${confidence.toFixed(2)} (was ${originalConf.toFixed(2)}, ${Math.round(elapsedMs / 1000)}s ago)`
    : `${confidence.toFixed(2)}`

  return `<observers>
Your advisors observed ${type}${urgencyTag} (confidence ${confidenceStr}): ${content}
</observers>`
}
