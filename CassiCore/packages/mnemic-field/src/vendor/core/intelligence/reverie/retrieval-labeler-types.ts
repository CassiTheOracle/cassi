/**
 * TYPE STUB — Reverie retrieval labeler types
 * (core/intelligence/reverie/retrieval-labeler-types.ts).
 *
 * Faithful type surface (self-contained; consumed by mnemic-field as types
 * only). Re-point to the owning package at P5 via the repoint log.
 */

export type RetrievalLabel =
  | 'used'
  | 'ignored'
  | 'contradicted'
  | 'should_have_been_retrieved'

export type RetrievalLabelSignal =
  | 'jaccard_overlap'
  | 'jaccard_below_threshold'
  | 'tag_cooccurrence'
  | 'mnemic_promotion'
  | 'mnemic_promote_contradiction'
  | 'recall_counterfactual'
  | 'enrich_feedback'
  | 'cosine_similarity'

export interface RetrievalLabelEvidence {
  signal: RetrievalLabelSignal
  details?: Record<string, unknown>
  observedAt: string
}

export interface RetrievalLabelTriple {
  retrievalId: string
  candidateId: string
  label: RetrievalLabel
  weight: number
  evidence: RetrievalLabelEvidence[]
  indexerScore?: number
  rerankerScore?: number
}

export interface LabelerInputRetrieval {
  retrievalId: string
  sessionId?: string
  queryText: string
  queryEmbedding?: Float32Array
  candidateIds: string[]
  indexerScores?: number[]
  rerankerScores?: number[]
  createdAt: string
}

export interface LabelerInputCandidate {
  id: string
  content: string
  tags: string[]
  /** Optional: stored embedding for cosine similarity signal. */
  embedding?: Float32Array
}

export interface LabelerInputToolRound {
  round: number
  toolCalls: Array<{ name: string; id: string; argsPreview?: string }>
  results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>
  at: number
}

export interface LabelerInputs {
  retrievals: LabelerInputRetrieval[]
  candidates: Map<string, LabelerInputCandidate>
  toolRounds: LabelerInputToolRound[]
  promotedEngramIds: Set<string>
}

export interface LabelerThresholds {
  jaccardUsedThreshold: number
  jaccardIgnoredMaxRounds: number
  recallSimilarityThreshold: number
  contentMaxTokens: number
}

export const DEFAULT_LABELER_THRESHOLDS: LabelerThresholds = {
  jaccardUsedThreshold: 0.15,
  jaccardIgnoredMaxRounds: 5,
  recallSimilarityThreshold: 0.85,
  contentMaxTokens: 200,
}
