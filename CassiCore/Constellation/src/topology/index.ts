/**
 * Topology Module — Public exports for the Helix Topology Graph.
 *
 * Usage:
 *   import { TopologyGraph } from './topology/index.js'
 *   const topology = new TopologyGraph({ embeddingService, logger })
 *   await topology.onDigestUpdate(helixId, digest)
 *   const snapshot = topology.getSnapshot()
 */

export { TopologyGraph } from './topology-graph.js'
export type { TopologyGraphDeps } from './topology-graph.js'

export { GravityEngine } from './gravity-engine.js'
export type { GravityEngineDeps } from './gravity-engine.js'

export { LinkManager } from './link-manager.js'
export type { LinkManagerDeps } from './link-manager.js'

export { ClusterTracker } from './cluster-tracker.js'
export type { ClusterTrackerDeps } from './cluster-tracker.js'

export { BrainstemBridge } from './brainstem-bridge.js'
export type {
  BrainstemBridgeDeps,
  BrainstemStateAccessor,
  ShallowContextPack,
  MediumContextPack,
  DeepContextPack,
  BridgeInjection,
} from './brainstem-bridge.js'

export { TopologyEmbeddingCache } from './embedding-cache.js'
export type {
  TopologyEmbeddingCacheMetrics,
  EmbeddingField,
} from './embedding-cache.js'

export type {
  HelixPosition,
  HelixTopologyState,
  GravityWeights,
  GravityConfig,
  TopologyLink,
  MergeDepth,
  LinkConfig,
  TopologyCluster,
  TopologyGraphConfig,
  TopologySnapshot,
  SerializableTopologySnapshot,
} from './topology-types.js'

export {
  DEFAULT_GRAVITY_WEIGHTS,
  DEFAULT_GRAVITY_CONFIG,
  DEFAULT_LINK_CONFIG,
  DEFAULT_TOPOLOGY_CONFIG,
  serializeTopologySnapshot,
  deserializeTopologySnapshot,
} from './topology-types.js'
