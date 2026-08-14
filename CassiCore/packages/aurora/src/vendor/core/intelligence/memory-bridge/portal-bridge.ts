/**
 * VENDORED — faithful type surface of `core/intelligence/memory-bridge/portal-bridge.ts`.
 * Consumed by @cassicore/aurora (claustrum.ts, index.ts) as `PortalBridge` (type-only).
 *
 * Self-contained stub: declares the `PortalBridge` class type. No runtime
 * dependency on the portal subsystem. Re-point to `@cassicore/*-memory-bridge`
 * when that package lands (P5 repoint log).
 */

/** Feature-engram portal discovery config (type surface). */
export interface PortalDiscoveryConfig {
  correlationThreshold: number
  minActivations: number
  maxPortals: number
  decayRate: number
}

export const PORTAL_BRIDGE_DEFAULTS = {
  correlationThreshold: 0.7,
  minActivations: 3,
  maxPortals: 1000,
  decayRate: 0.1,
} as const

/** A feature↔engram portal pair (type surface, from memory-bridge/types.js). */
export interface FeatureEngramPortal {
  id: string
  feature: { layer: number; featureIndex: number; gateScore?: number; label?: string }
  engram: { id: string; nodeType: string; contentPreview: string }
  connectionType: 'semantic' | 'temporal' | 'causal' | 'structural'
  strength: number
  discoveryMethod: 'auto' | 'manual' | 'correlation'
  correlationScore?: number
  createdAt: string
  lastActivatedAt?: string
  activationCount: number
}

/** Manages feature-engram portal pairs (type surface). */
export declare class PortalBridge {
  /** Portals for an engram (by engram id). */
  getPortalsForEngram(engramId: string): FeatureEngramPortal[]
}
