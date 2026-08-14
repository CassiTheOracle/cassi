/**
 * @cassicore/dreamer-reverie-subconscious — package barrel.
 *
 * Re-exports the three reflective-cognition sub-barrels (dreamer, reverie,
 * subconscious). Inbound consumers (foundation's DreamerConfig, constellation's
 * SubconsciousConfig) import the package root. History-preserved import splice
 * from cassicore's core/intelligence/{dreamer,reverie,subconscious}.
 */

export * from './dreamer/index.js'
export * from './reverie/index.js'
export * from './subconscious/index.js'
