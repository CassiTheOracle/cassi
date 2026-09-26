/**
 * @cassicore/lamina-locus-bridge — package barrel.
 *
 * Re-exports the lamina (LaminaField/LaminaStore) and locus-bridge
 * (LocusBridge + helpers) sub-barrels. Inbound consumers (helix, constellation)
 * re-point their vendored `lamina/index.ts` LaminaField stub here.
 * History-preserved import splice from cassicore's
 * core/intelligence/{lamina,locus-bridge}.
 */

export * from './lamina/index.js'
export * from './locus-bridge/index.js'
