/**
 * Scout Skip Heuristics
 *
 * Fast checks to determine whether the scout should run for a given message.
 * Avoids wasting time and tokens on trivial messages (acknowledgments,
 * confirmations, short follow-ups) that don't benefit from pre-search.
 */

import type { Message } from '@cassicore/foundation'


const TRIVIAL_PATTERNS = [
  /^(yes|no|ok|okay|sure|yep|nope|nah|yea|yeah|yup|uh huh|mhm)\.?$/i,
  /^(thanks|thank you|thx|ty|cheers|appreciated)\.?!?$/i,
  /^(go ahead|proceed|continue|do it|sounds good|lgtm|ship it)\.?!?$/i,
  /^(got it|understood|makes sense|i see|right|correct)\.?!?$/i,
  /^(please|pls)$/i,
  /^(nice|great|good|perfect|awesome|cool|sweet)\.?!?$/i,
  /^(stop|cancel|abort|nevermind|never mind|nvm)\.?!?$/i,
  /^(what|huh|hmm|um)\??$/i,
  /^[👍👎✅❌🎉💯🙏]+$/,
]


const SEARCH_INDICATORS = [
  // File paths
  /[\w-]+\.(ts|js|go|py|rs|tsx|jsx|css|html|json|yaml|yml|toml|md)/i,
  // Function/class references
  /\b(function|class|method|interface|type|enum|struct|trait|impl)\s+\w+/i,
  // Error traces
  /\b(error|exception|stack\s*trace|traceback|failed|crash|panic)\b/i,
  // Specific code references
  /`[^`]+`/,
  // Import/require patterns (handles both `import 'x'` and `require('x')`)
  /\b(import|require|from)\s*['"`(]/,
  // Questions about code
  /\b(how does|what does|where is|where are|show me|find|look at|check)\b/i,
  // Change/refactor intent
  /\b(add|remove|change|rename|refactor|fix|update|implement|create|delete|move)\b/i,
]

/**
 * Determine whether the scout should skip this message.
 *
 * @returns A skip reason string if the scout should skip, or `null` if it should run.
 * @dep callers: scout.test.ts (tests/scout.test.ts), createMiddleware (core/scout/index.ts)
 * @dep calls: trim, test
 * @dep module: Scout
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function shouldSkipScout(
  messageContent: string,
  history: Message[],
  isFirstMessage: boolean,
): string | null {
  const trimmed = messageContent.trim()

  // Empty messages — skip
  if (trimmed.length === 0) {
    return 'empty message'
  }

  // First message in session — always scout (most valuable)
  if (isFirstMessage) {
    return null
  }

  // Very short messages — check if trivial
  if (trimmed.length < 20) {
    for (const pattern of TRIVIAL_PATTERNS) {
      if (pattern.test(trimmed)) {
        return `trivial message: "${trimmed}"`
      }
    }
  }

  // Very short messages without search indicators — skip
  if (trimmed.length < 15 && !SEARCH_INDICATORS.some(p => p.test(trimmed))) {
    return `short message without search indicators (${trimmed.length} chars)`
  }

  // Messages with strong search indicators — always scout
  if (SEARCH_INDICATORS.some(p => p.test(trimmed))) {
    return null
  }

  // Medium-length messages — scout (likely substantive)
  if (trimmed.length >= 50) {
    return null
  }

  // Questions — scout
  if (trimmed.includes('?')) {
    return null
  }

  // Default for short-ish messages without clear indicators — skip
  if (trimmed.length < 30) {
    return `ambiguous short message (${trimmed.length} chars)`
  }

  // Default — run the scout
  return null
}
