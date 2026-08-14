/**
 * @cassicore/training-trust-ledger — package barrel.
 *
 * Re-exports the training (TrainingWarehouse + store/ingest/tagger/reader) and
 * trust-ledger (TrustLedger + createTrustLedger) sub-barrels. Inbound consumers
 * (permission-oracle at P5-A) import the package root. History-preserved import
 * splice from cassicore's core/intelligence/{training,trust-ledger}.
 */

export * from './training/index.js'
export * from './trust-ledger/index.js'
export type {
  TrustScore,
  TrustEvidence,
  TrustLedgerConfig,
  TrustDomain,
  CanonicalDomain,
  TrustSummary,
  AutonomyLevel,
} from './trust-ledger/types.js'
export { DEFAULT_TRUST_LEDGER_CONFIG, trustToAutonomyLevel, betaMean, betaVariance, betaConfidence } from './trust-ledger/types.js'
