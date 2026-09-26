/**
 * Built-in Corpus strategies — workflow-dispatched coordination for
 * cross-helix patterns detected by the Corpus organizer.
 */

export { createConflictResolutionStrategy } from './conflict-resolution.js'
export { createCascadeRecoveryStrategy } from './cascade-recovery.js'
export { createConvergenceSynthesisStrategy } from './convergence-synthesis.js'
export { createStuckRedecompositionStrategy } from './stuck-redecomposition.js'
export { createRedundancyStrategy } from './redundancy.js'
export { createDivergenceStrategy } from './divergence.js'
export { createResourceImbalanceStrategy } from './resource-imbalance.js'
