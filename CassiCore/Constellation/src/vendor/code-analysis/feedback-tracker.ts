/** VENDORED TYPE STUB — mirrors `code-analysis/feedback-tracker.js`. Surface: ContextFeedbackTracker. */
export type ContextMode = 'full' | 'file_only' | 'skip'

export interface ContextFeedbackTracker {
  recommendMode(score: number): { mode: ContextMode; confidence?: number; reason?: string } | null
  recordInjection(helixId: string, goal: string, score: number, mode: string, suggestedFiles: string[]): string
  recordUsage(feedbackId: string, filesUsed: string[]): void
  [key: string]: unknown
}
