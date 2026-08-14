/**
 * workspace-luminance — Port over CassiCore's `workspace/luminance.js` (extractKeywords, keywordOverlap).
 *
 * Constellation uses only these two pure, stateless helpers. The original module imports the whole
 * workspace cognitive-signal system (runtime consts + types); re-implementing the two used helpers
 * here keeps the port self-contained with identical behavior.
 *
 * Self-contained: no imports.
 */

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'to', 'of',
  'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about',
  'that', 'this', 'these', 'those', 'it', 'its', 'and', 'or', 'but',
  'not', 'no', 'if', 'then', 'else', 'when', 'while', 'which', 'who',
  'what', 'where', 'how', 'all', 'each', 'every', 'both', 'some', 'any',
  'few', 'more', 'most', 'other', 'so', 'than', 'too', 'very', 'just',
])

/**
 * Extract meaningful keywords from text for novelty/coalition matching.
 * Filters stop words and short tokens.
 */
export function extractKeywords(text: string): Set<string> {
  const words = text.toLowerCase().replace(/[^a-z0-9\s-_]/g, ' ').split(/\s+/)
  const keywords = new Set<string>()
  for (const word of words) {
    if (word.length > 3 && !STOP_WORDS.has(word)) {
      keywords.add(word)
    }
  }
  return keywords
}

/**
 * Compute keyword overlap ratio between two sets. Returns 0–1 where 1 = identical sets.
 */
export function keywordOverlap(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0
  let shared = 0
  for (const word of a) {
    if (b.has(word)) shared++
  }
  return shared / Math.min(a.size, b.size)
}
