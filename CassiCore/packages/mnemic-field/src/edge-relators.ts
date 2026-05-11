import type { SynapseType } from './types.js'

export const RELATIONAL_PHRASES: Record<string, string[]> = {
  contradicts: [
    'this contradicts the previous finding',
    'the opposite was found',
    'this approach failed because',
    'an alternative that avoids this problem',
    'however this conflicts with',
    'this disagrees with the earlier conclusion',
  ],
  supports: [
    'this confirms the earlier approach',
    'building on the established pattern',
    'consistent with what was learned',
    'this reinforces the previous finding',
    'further evidence for the same conclusion',
    'aligned with the earlier analysis',
  ],
  caused_by: [
    'this error was caused by',
    'the root cause was traced to',
    'resulted from the previous change',
    'triggered by the earlier modification',
    'this happened because of',
  ],
  led_to: [
    'as a result of this change',
    'this led to the discovery that',
    'consequence of the previous step',
    'this enabled the subsequent work',
    'the outcome was that',
  ],
  supersedes: [
    'this replaces the previous implementation',
    'refactored to use the new approach',
    'the old method is now deprecated',
    'this supersedes the earlier version',
    'a better solution that obsoletes the old one',
  ],
  evolved_from: [
    'refined based on experience',
    'improved version of the earlier pattern',
    'learned that a better approach is',
    'evolution of the original concept',
    'iterated on the previous design',
  ],
  enables: [
    'this makes it possible to',
    'now we can proceed with',
    'unlocked by the previous work',
    'this paves the way for',
    'enables the following capability',
  ],
  constrains: [
    'limited by the constraint that',
    'cannot proceed because',
    'blocked by a dependency on',
    'this restricts the approach to',
    'constrained by the requirement that',
  ],
  depends_on: [
    'requires the following prerequisite',
    'this builds on top of',
    'needs the output from',
    'has a dependency on',
    'prerequisite for this work',
  ],
  mitigates: [
    'this prevents the issue where',
    'workaround for the known problem',
    'reduces the risk of',
    'a fix that addresses',
    'mitigates the impact of',
  ],
}

export const RELATIONAL_PHRASE_EDGE_TYPES: SynapseType[] = [
  'contradicts', 'supports', 'caused_by', 'led_to',
  'supersedes', 'evolved_from', 'enables', 'constrains',
  'depends_on', 'mitigates',
]

export interface EdgeClassification {
  edgeType: SynapseType | null
  score: number
}

export function extractRelationalKeywords(content: string): string[] {
  const keywords = new Set<string>()
  for (const edgeType of RELATIONAL_PHRASE_EDGE_TYPES) {
    for (const phrase of RELATIONAL_PHRASES[edgeType]) {
      if (content.toLowerCase().includes(phrase)) {
        keywords.add(phrase)
      }
    }
  }
  return Array.from(keywords)
}

export function classifyEdge(
  sourceContent: string,
  targetContent: string,
  phraseEmbeddings: Map<string, Float32Array>,
  combinedEmbedding: Float32Array | null,
  cosineSimilarity: (a: ArrayLike<number>, b: ArrayLike<number>) => number,
  threshold = 0.35,
): EdgeClassification {
  if (!combinedEmbedding || phraseEmbeddings.size === 0) {
    return { edgeType: null, score: 0 }
  }

  let bestType: SynapseType | null = null
  let bestScore = threshold

  const combined = `${sourceContent.slice(0, 200)} ${targetContent.slice(0, 200)}`

  for (const edgeType of RELATIONAL_PHRASE_EDGE_TYPES) {
    const prototypes = phraseEmbeddings.get(edgeType)
    if (!prototypes) continue

    const emb = phraseEmbeddings.get(`embed:${edgeType}`)
    if (!emb) continue

    const score = cosineSimilarity(combinedEmbedding, emb)
    if (score > bestScore) {
      bestScore = score
      bestType = edgeType
    }
  }

  if (bestType === null) {
    const lexicalHits = extractRelationalKeywords(combined)
    for (const edgeType of RELATIONAL_PHRASE_EDGE_TYPES) {
      const phrases = RELATIONAL_PHRASES[edgeType]
      const matched = lexicalHits.some(h => phrases.includes(h))
      if (matched) {
        bestType = edgeType
        bestScore = threshold + 0.05
        break
      }
    }
  }

  return { edgeType: bestType, score: bestScore }
}