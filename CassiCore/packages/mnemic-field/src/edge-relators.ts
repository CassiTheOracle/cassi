import type { SynapseType } from './types.js'

export interface PhrasePrototypeSet {
  phrases: Record<string, string[]>
  labels: string[]
}

export interface ClassificationResult {
  label: string | null
  score: number
}

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

export const EDGE_RELATORS_PHRASE_SET: PhrasePrototypeSet = {
  phrases: RELATIONAL_PHRASES,
  labels: RELATIONAL_PHRASE_EDGE_TYPES as unknown as string[],
}

export interface EdgeClassification {
  edgeType: SynapseType | null
  score: number
}

function extractKeywords(content: string, phrases: Record<string, string[]>, labels: string[]): string[] {
  const keywords = new Set<string>()
  for (const label of labels) {
    for (const phrase of phrases[label] ?? []) {
      if (content.toLowerCase().includes(phrase)) {
        keywords.add(phrase)
      }
    }
  }
  return Array.from(keywords)
}

export function extractRelationalKeywords(content: string): string[] {
  return extractKeywords(content, RELATIONAL_PHRASES, RELATIONAL_PHRASE_EDGE_TYPES as unknown as string[])
}

export function classifyWithPhrases(
  text: string,
  prototypeSet: PhrasePrototypeSet,
  phraseEmbeddings: Map<string, Float32Array>,
  textEmbedding: Float32Array | null,
  cosineSimilarity: (a: ArrayLike<number>, b: ArrayLike<number>) => number,
  threshold = 0.35,
): ClassificationResult {
  if (!textEmbedding || phraseEmbeddings.size === 0) {
    return { label: null, score: 0 }
  }

  let bestLabel: string | null = null
  let bestScore = threshold

  for (const label of prototypeSet.labels) {
    const emb = phraseEmbeddings.get(`embed:${label}`)
    if (!emb) continue

    const score = cosineSimilarity(textEmbedding, emb)
    if (score > bestScore) {
      bestScore = score
      bestLabel = label
    }
  }

  if (bestLabel === null) {
    const lexicalHits = extractKeywords(text, prototypeSet.phrases, prototypeSet.labels)
    for (const label of prototypeSet.labels) {
      const phrases = prototypeSet.phrases[label] ?? []
      const matched = lexicalHits.some(h => phrases.includes(h))
      if (matched) {
        bestLabel = label
        bestScore = threshold + 0.05
        break
      }
    }
  }

  return { label: bestLabel, score: bestScore }
}

export function classifyEdge(
  sourceContent: string,
  targetContent: string,
  phraseEmbeddings: Map<string, Float32Array>,
  combinedEmbedding: Float32Array | null,
  cosineSimilarity: (a: ArrayLike<number>, b: ArrayLike<number>) => number,
  threshold = 0.35,
): EdgeClassification {
  const combined = `${sourceContent.slice(0, 200)} ${targetContent.slice(0, 200)}`
  const result = classifyWithPhrases(
    combined,
    EDGE_RELATORS_PHRASE_SET,
    phraseEmbeddings,
    combinedEmbedding,
    cosineSimilarity,
    threshold,
  )
  return { edgeType: result.label as SynapseType | null, score: result.score }
}