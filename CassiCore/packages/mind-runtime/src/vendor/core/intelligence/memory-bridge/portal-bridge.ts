/**
 * Portal Bridge — connects LARQL features to Mnemic Field engrams.
 *
 * Portal pairs create bidirectional activation pathways:
 * - When a LARQL feature fires during walk → boost related engrams during kindling
 * - When a Mnemic Field engram activates → boost related features during walk
 *
 * Auto-discovery via correlation:
 * - Run TRACE (LARQL) + Kindle (Mnemic Field) on same query
 * - Correlate high-contribution features with high-charge engrams
 * - Create portal pairs for correlations above threshold
 */

import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from '@cassicore/mnemic-field'
import type { FeatureEngramPortal } from './types.js'
import { randomUUID } from 'node:crypto'

export const PORTAL_BRIDGE_DEFAULTS = {
  correlationThreshold: 0.7,
  minActivations: 3,
  maxPortals: 1000,
  decayRate: 0.1,  // Decay strength if not activated
} as const

export interface PortalDiscoveryConfig {
  correlationThreshold: number
  minActivations: number
  maxPortals: number
  decayRate: number
}

/**
 * PortalBridge — manages feature-engram portal pairs.
 */
export class PortalBridge {
  private logger: ILogger
  private config: PortalDiscoveryConfig
  private portals: Map<string, FeatureEngramPortal> = new Map()
  private featureIndex: Map<string, Set<string>> = new Map()  // featureKey → portalIds
  private engramIndex: Map<string, Set<string>> = new Map()   // engramId → portalIds
  private cortexes: Map<string, Cortex> = new Map()            // fieldId → cortex

  constructor(
    cortex: Cortex,
    logger: ILogger,
    config?: Partial<PortalDiscoveryConfig>,
  ) {
    this.logger = logger.child ? logger.child('portal-bridge') : logger
    this.config = { ...PORTAL_BRIDGE_DEFAULTS, ...config }
    this.cortexes.set('episodic', cortex)

    this.logger.info('PortalBridge initialized', {
      correlationThreshold: this.config.correlationThreshold,
      maxPortals: this.config.maxPortals,
    })
  }

  /**
   * Register an additional cortex (e.g. knowledge field) for portal lookups.
   */
  registerCortex(fieldId: string, cortex: Cortex): void {
    this.cortexes.set(fieldId, cortex)
    this.logger.info('Registered cortex with PortalBridge', { fieldId })
  }

  /**
   * Create a portal pair connecting a feature to an engram.
   */
  createPortal(
    feature: { layer: number; featureIndex: number; label?: string },
    engramId: string,
    connectionType: FeatureEngramPortal['connectionType'],
    correlationScore?: number,
  ): FeatureEngramPortal | null {
    if (this.portals.size >= this.config.maxPortals) {
      this.logger.warn('Portal limit reached', {
        current: this.portals.size,
        max: this.config.maxPortals,
      })
      return null
    }

    const id = randomUUID()
    const featureKey = `${feature.layer}:${feature.featureIndex}`

    // Get engram content preview — check all registered cortexes
    let engram = null
    for (const cortex of this.cortexes.values()) {
      engram = cortex.getEngram(engramId)
      if (engram) break
    }
    const contentPreview = engram?.content.slice(0, 100) ?? ''

    const portal: FeatureEngramPortal = {
      id,
      feature: {
        layer: feature.layer,
        featureIndex: feature.featureIndex,
        label: feature.label,
      },
      engram: {
        id: engramId,
        nodeType: engram?.nodeType ?? 'fact',
        contentPreview,
      },
      connectionType,
      strength: correlationScore ?? 0.8,
      discoveryMethod: correlationScore ? 'correlation' : 'manual',
      correlationScore,
      createdAt: new Date().toISOString(),
      activationCount: 0,
    }

    // Store portal
    this.portals.set(id, portal)

    // Update indexes
    if (!this.featureIndex.has(featureKey)) {
      this.featureIndex.set(featureKey, new Set())
    }
    this.featureIndex.get(featureKey)!.add(id)

    if (!this.engramIndex.has(engramId)) {
      this.engramIndex.set(engramId, new Set())
    }
    this.engramIndex.get(engramId)!.add(id)

    this.logger.debug('Portal created', {
      id,
      featureKey,
      engramId,
      connectionType,
      strength: portal.strength,
    })

    return portal
  }

  /**
   * Get portals for a feature.
   */
  getPortalsForFeature(layer: number, featureIndex: number): FeatureEngramPortal[] {
    const featureKey = `${layer}:${featureIndex}`
    const portalIds = this.featureIndex.get(featureKey)
    if (!portalIds) return []

    return Array.from(portalIds)
      .map(id => this.portals.get(id))
      .filter((p): p is FeatureEngramPortal => p !== undefined)
  }

  /**
   * Get portals for an engram.
   */
  getPortalsForEngram(engramId: string): FeatureEngramPortal[] {
    const portalIds = this.engramIndex.get(engramId)
    if (!portalIds) return []

    return Array.from(portalIds)
      .map(id => this.portals.get(id))
      .filter((p): p is FeatureEngramPortal => p !== undefined)
  }

  /**
   * Get engrams related to a feature (for kindling boost).
   */
  getEngramsForFeature(layer: number, featureIndex: number): Array<{
    engramId: string
    strength: number
    contentPreview: string
  }> {
    return this.getPortalsForFeature(layer, featureIndex)
      .map(p => ({
        engramId: p.engram.id,
        strength: p.strength,
        contentPreview: p.engram.contentPreview,
      }))
  }

  /**
   * Get features related to an engram (for walk boost).
   */
  getFeaturesForEngram(engramId: string): Array<{
    layer: number
    featureIndex: number
    strength: number
    label?: string
  }> {
    return this.getPortalsForEngram(engramId)
      .map(p => ({
        layer: p.feature.layer,
        featureIndex: p.feature.featureIndex,
        strength: p.strength,
        label: p.feature.label,
      }))
  }

  /**
   * Activate a portal (called when feature fires or engram activates).
   * Increases activation count and updates last activation time.
   */
  activatePortal(portalId: string): void {
    const portal = this.portals.get(portalId)
    if (!portal) return

    portal.activationCount++
    portal.lastActivatedAt = new Date().toISOString()

    // Boost strength slightly on activation (reinforcement)
    portal.strength = Math.min(1.0, portal.strength + 0.01)
  }

  /**
   * Decay portals that haven't been activated recently.
   * Called during consolidation.
   */
  decayInactivePortals(): number {
    let decayed = 0
    const now = Date.now()
    const decayMs = 24 * 60 * 60 * 1000  // 24 hours

    for (const portal of this.portals.values()) {
      if (!portal.lastActivatedAt) continue

      const lastActivation = new Date(portal.lastActivatedAt).getTime()
      if (now - lastActivation > decayMs) {
        portal.strength *= (1 - this.config.decayRate)
        decayed++

        // Remove portal if strength drops too low
        if (portal.strength < 0.1) {
          this.removePortal(portal.id)
        }
      }
    }

    if (decayed > 0) {
      this.logger.debug('Decayed inactive portals', { count: decayed })
    }

    return decayed
  }

  /**
   * Remove a portal.
   */
  removePortal(portalId: string): void {
    const portal = this.portals.get(portalId)
    if (!portal) return

    const featureKey = `${portal.feature.layer}:${portal.feature.featureIndex}`
    this.featureIndex.get(featureKey)?.delete(portalId)
    this.engramIndex.get(portal.engram.id)?.delete(portalId)

    this.portals.delete(portalId)

    this.logger.debug('Portal removed', { portalId })
  }

  /**
   * Auto-discover portals from correlation data.
   *
   * Called after running TRACE + Kindle on same query, with:
   * - featureContributions: which features contributed (from TRACE)
   * - engramContributions: which engrams contributed (from Kindle)
   */
  discoverFromCorrelation(
    featureContributions: Array<{
      layer: number
      featureIndex: number
      contribution: number
      label?: string
    }>,
    engramContributions: Array<{
      engramId: string
      charge: number
    }>,
  ): number {
    let discovered = 0

    // Find correlated pairs
    for (const feature of featureContributions) {
      // Normalize contribution to 0-1
      const featureNorm = Math.min(1.0, feature.contribution / 100)

      for (const engram of engramContributions) {
        // Normalize charge to 0-1
        const engramNorm = Math.min(1.0, engram.charge)

        // Correlation score (simplified - would be more sophisticated in practice)
        const correlation = Math.sqrt(featureNorm * engramNorm)

        if (correlation >= this.config.correlationThreshold) {
          // Check if portal already exists
          const existing = this.findExistingPortal(
            feature.layer,
            feature.featureIndex,
            engram.engramId,
          )

          if (existing) {
            // Update existing portal strength
            existing.strength = Math.max(existing.strength, correlation)
            existing.correlationScore = correlation
          } else {
            // Create new portal
            const portal = this.createPortal(
              feature,
              engram.engramId,
              this.inferConnectionType(feature.layer),
              correlation,
            )
            if (portal) discovered++
          }
        }
      }
    }

    if (discovered > 0) {
      this.logger.info('Discovered portals from correlation', {
        discovered,
        featureCount: featureContributions.length,
        engramCount: engramContributions.length,
      })
    }

    return discovered
  }

  /**
   * Infer connection type from layer position.
   */
  private inferConnectionType(layer: number): FeatureEngramPortal['connectionType'] {
    // Early layers: structural (building representations)
    // Middle layers: semantic (knowledge positioning)
    // Late layers: causal (answer generation)
    if (layer < 14) return 'structural'
    if (layer < 22) return 'semantic'
    return 'causal'
  }

  /**
   * Find existing portal for a feature-engram pair.
   */
  private findExistingPortal(
    layer: number,
    featureIndex: number,
    engramId: string,
  ): FeatureEngramPortal | null {
    const featureKey = `${layer}:${featureIndex}`
    const portalIds = this.featureIndex.get(featureKey)
    if (!portalIds) return null

    for (const id of portalIds) {
      const portal = this.portals.get(id)
      if (portal && portal.engram.id === engramId) {
        return portal
      }
    }

    return null
  }

  /**
   * Get portal stats.
   */
  getStats(): {
    totalPortals: number
    byConnectionType: Record<string, number>
    byLayer: Record<number, number>
    avgStrength: number
    avgActivationCount: number
  } {
    const byConnectionType: Record<string, number> = {}
    const byLayer: Record<number, number> = {}
    let totalStrength = 0
    let totalActivations = 0

    for (const portal of this.portals.values()) {
      byConnectionType[portal.connectionType] =
        (byConnectionType[portal.connectionType] ?? 0) + 1
      byLayer[portal.feature.layer] =
        (byLayer[portal.feature.layer] ?? 0) + 1
      totalStrength += portal.strength
      totalActivations += portal.activationCount
    }

    return {
      totalPortals: this.portals.size,
      byConnectionType,
      byLayer,
      avgStrength: this.portals.size > 0 ? totalStrength / this.portals.size : 0,
      avgActivationCount: this.portals.size > 0 ? totalActivations / this.portals.size : 0,
    }
  }

  /**
   * Persist portals to database.
   * Would store in a dedicated table for portal pairs.
   */
  persist(): void {
    this.logger.debug('Portal persistence not yet implemented') // contributing:ignore
  }

  /**
   * Load portals from database on startup.
   */
  load(): number {
    this.logger.debug('Portal loading not yet implemented') // contributing:ignore
    return 0
  }
}