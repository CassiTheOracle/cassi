/**
 * VENDOR TYPE STUB — `core/intelligence/trust-ledger/index.ts` (`TrustLedger`).
 *
 * Type-placeholder for the trust-ledger surface consumed by executor.ts
 * (tools): `recordEvidence` + `getDomainScore` (type-only — 2 calls).
 * The landed `@cassicore/training-trust-ledger` root export does not currently
 * expose `TrustLedger` (its `.` export is the training sub-module), so tools
 * vendors the type surface rather than depending on the subpath export.
 * Re-pointed to the owning package's root when it publishes the symbol (Open-6).
 */

/** A domain the trust ledger scores (string-domained via tool resolution). */
export type TrustDomain = string

/** A trust score for a domain. */
export interface TrustScore {
  domain: TrustDomain
  score: number
  version: number
  updatedAt: number
}

/** An evidence record fed into the trust ledger. */
export interface TrustEvidence {
  domain: TrustDomain
  success: boolean
  weight?: number
  source?: string
  description?: string
  sessionId?: string
  timestamp?: number
}

/** Cross-domain trust ledger consumed by the tools executor. */
export interface TrustLedger {
  recordEvidence(evidence: TrustEvidence): void
  getDomainScore(domain: TrustDomain): TrustScore | undefined
}
