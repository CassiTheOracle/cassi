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
