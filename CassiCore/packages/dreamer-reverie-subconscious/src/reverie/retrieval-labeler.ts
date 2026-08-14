/**
 * Pure heuristic labeler for retrieval events.
 *
 * Given a window of recent retrievals, the candidate engrams they returned,
 * and the primary's subsequent tool rounds, this function produces
 * (retrievalId, candidateId, label, evidence) triples for Lightning Indexer
 * training. No LLM calls, no I/O.
 *
 * Signals applied per (retrieval, candidate):
 *   1. Jaccard 2-gram overlap — candidate content vs. subsequent tool args/results
 *   2. Tag co-occurrence — candidate tags appearing as keywords in tool calls
 *   3. mnemic.promote — candidate was promoted by Reverie (strong positive)
 *
 * "Ignored" is the default when no positive signal fires within the window.
 * If no subsequent rounds exist in the window, the retrieval is skipped entirely
 * (the labeler will revisit it on a later Reverie tick when more context exists).
 */

import type {
  LabelerInputs,
  LabelerThresholds,
  RetrievalLabel,
  RetrievalLabelEvidence,
  RetrievalLabelTriple,
} from './retrieval-labeler-types.js'
import { DEFAULT_LABELER_THRESHOLDS } from './retrieval-labeler-types.js'

const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'this', 'that', 'these', 'those',
  'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
  'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with', 'as', 'from', 'into', 'about',
  'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her', 'its', 'their',
  'not', 'no', 'yes', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
  'so', 'just', 'only', 'than', 'also', 'very', 'too', 'much', 'more', 'most', 'some',
  'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must', 'shall',
])

export function tokenize(text: string, maxTokens?: number): string[] {
  if (!text) return []
  const tokens = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]+/gu, ' ')
    .split(/\s+/)
    .filter(t => t.length > 1 && !STOPWORDS.has(t))
  return maxTokens !== undefined ? tokens.slice(0, maxTokens) : tokens
}

export function bigrams(tokens: string[]): Set<string> {
  const out = new Set<string>()
  for (let i = 0; i < tokens.length - 1; i++) {
    out.add(`${tokens[i]} ${tokens[i + 1]}`)
  }
  return out
}

export function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0
  let inter = 0
  for (const x of a) if (b.has(x)) inter++
  const union = a.size + b.size - inter
  return union === 0 ? 0 : inter / union
}

export function labelRetrievals(
  inputs: LabelerInputs,
  thresholds: LabelerThresholds = DEFAULT_LABELER_THRESHOLDS,
  now: () => string = () => new Date().toISOString(),
): RetrievalLabelTriple[] {
  const triples: RetrievalLabelTriple[] = []

  for (const r of inputs.retrievals) {
    const createdAtMs = Date.parse(r.createdAt)
    if (Number.isNaN(createdAtMs)) continue

    const subsequentRounds = inputs.toolRounds
      .filter(t => t.at >= createdAtMs)
      .slice(0, thresholds.jaccardIgnoredMaxRounds)

    if (subsequentRounds.length === 0) continue

    const subsequentTexts: string[] = []
    for (const round of subsequentRounds) {
      for (const tc of round.toolCalls) {
        if (tc.argsPreview) subsequentTexts.push(tc.argsPreview)
      }
      for (const res of round.results) {
        if (res.contentPreview) subsequentTexts.push(res.contentPreview)
      }
    }
    const subsequentTokens = tokenize(subsequentTexts.join(' '))
    const subsequentTokenSet = new Set(subsequentTokens)
    const subsequentBigrams = bigrams(subsequentTokens)

    for (let i = 0; i < r.candidateIds.length; i++) {
      const cid = r.candidateIds[i]
      const cand = inputs.candidates.get(cid)
      if (!cand) continue

      const candTokens = tokenize(cand.content, thresholds.contentMaxTokens)
      const candBigrams = bigrams(candTokens)
      const evidence: RetrievalLabelEvidence[] = []
      let label: RetrievalLabel = 'ignored'
      let weight = 0.5
      const observedAt = now()

      const j = jaccard(candBigrams, subsequentBigrams)
      if (j >= thresholds.jaccardUsedThreshold) {
        label = 'used'
        weight = Math.min(1.0, 0.5 + j)
        evidence.push({
          signal: 'jaccard_overlap',
          observedAt,
          details: { jaccard: j, candTokens: candTokens.length },
        })
      } else {
        evidence.push({
          signal: 'jaccard_below_threshold',
          observedAt,
          details: { jaccard: j, threshold: thresholds.jaccardUsedThreshold },
        })
      }

      const matchingTags: string[] = []
      for (const tag of cand.tags) {
        for (const t of tokenize(tag)) {
          if (subsequentTokenSet.has(t)) {
            matchingTags.push(tag)
            break
          }
        }
      }
      if (matchingTags.length > 0) {
        if (label === 'ignored') {
          label = 'used'
          weight = Math.max(weight, 0.7)
        } else {
          weight = Math.min(1.0, weight + 0.1)
        }
        evidence.push({
          signal: 'tag_cooccurrence',
          observedAt,
          details: { tags: matchingTags },
        })
      }

      if (inputs.promotedEngramIds.has(cid)) {
        label = 'used'
        weight = 1.0
        evidence.push({
          signal: 'mnemic_promotion',
          observedAt,
        })
      }

      triples.push({
        retrievalId: r.retrievalId,
        candidateId: cid,
        label,
        weight,
        evidence,
        indexerScore: r.indexerScores?.[i],
        rerankerScore: r.rerankerScores?.[i],
      })
    }
  }

  return triples
}
