/** VENDORED TYPE STUB — mirrors `thalamus/types.js`. Surface: TopicSummary. */
export interface TopicSummary {
  id: string
  label: string
  summary: string
  status: 'active' | 'archived' | string
  keyTerms: string[]
  filesTouched?: string[]
  importanceScore: number
  [key: string]: unknown
}
