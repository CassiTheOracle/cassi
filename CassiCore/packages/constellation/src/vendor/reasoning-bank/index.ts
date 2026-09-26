/**
 * VENDORED TYPE STUB — mirrors `reasoning-bank/index.js` (CassiCore inline type).
 * Surface used by constellation-pipeline: retrieveForBranch / store.
 */
export interface ReasoningBankStoreInput {
  sourceHelixId: string
  goal: string
  approach: string
  content: string
  qualityScore: number
  succeeded: boolean
  relevantFiles?: string[]
  [key: string]: unknown
}

export interface ReasoningBank {
  retrieveForBranch(goal: string): string | null
  store(input: ReasoningBankStoreInput): void
  [key: string]: unknown
}
