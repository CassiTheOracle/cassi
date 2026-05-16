/**
 * MnemicSteeringBridge — closes the vindex↔Mnemic loop.
 *
 * Takes self-model engrams from the Mnemic Field (stored by the
 * SelfModelKnowledgeProvider probe) and converts them into LayerSteer
 * vectors that bias inference toward CassiCore's own architectural
 * understanding.
 *
 * This is the reverse half of the bidirectional loop:
 *   vindex → gate KNN → Mnemic engrams → steering vectors → vindex inference
 *
 * Usage:
 *   const bridge = new MnemicSteeringBridge(mnemicField, larqlProvider, logger);
 *   const steers = bridge.buildSteering('transformer-mechanics');
 *   const result = larqlProvider.generateWithSteering(prompt, steers, 50);
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { LarqlKnowledgeProvider } from './larql-provider.js'
import type { LayerBand } from './self-model-knowledge.js'


export interface LayerSteer {
  layer: number
  alpha: number
  vectorBytes: Uint8Array
}

export interface SteeringContext {
  /** Domain tag to query (e.g., 'transformer-mechanics', 'persistence'). */
  domain: string
  /** Maximum steering vectors to build. */
  maxVectors: number
  /** Base alpha multiplier (scaled by engram potentiation). */
  baseAlpha: number
  /** Only use engrams above this potentiation threshold. */
  minPotentiation: number
  /** Prefer engrams from this band (knowledge/output). */
  preferredBand?: LayerBand
}

const DEFAULT_CONTEXT: SteeringContext = {
  domain: '',
  maxVectors: 5,
  baseAlpha: 0.3,
  minPotentiation: 0.3,
}


/** Map a dominant band to a representative injection layer. */
function bandToLayer(band: LayerBand, defaultLayer: number): number {
  switch (band) {
    case 'knowledge': return 18  // mid-knowledge band
    case 'output':    return 26  // mid-output band
    default:          return defaultLayer
  }
}


export class MnemicSteeringBridge {
  private logger: ILogger

  constructor(
    private mnemicField: MnemicField,
    private larqlProvider: LarqlKnowledgeProvider,
    logger: ILogger,
  ) {
    this.logger = logger.child ? logger.child('mnemic-steering') : logger
  }

  /**
   * Build steering vectors from top-potentiated self-model engrams
   * matching a domain tag.
   *
   * The steering strength is proportional to engram potentiation:
   * a concept the system has reinforced through repeated use gets a
   * stronger injection. The injection layer is chosen from the engram's
   * dominant band metadata.
   */
  buildSteering(ctx: Partial<SteeringContext> = {}): LayerSteer[] {
    const c = { ...DEFAULT_CONTEXT, ...ctx }

    // Query Mnemic for self-model engrams matching the domain
    const candidates = this.queryCandidates(c.domain, c.minPotentiation)
    if (candidates.length === 0) return []

    // Sort by potentiation descending, take top N
    const ranked = candidates
      .sort((a, b) => b.potentiation - a.potentiation)
      .slice(0, c.maxVectors)

    const steers: LayerSteer[] = []

    for (const engram of ranked) {
      const label = engram.label
      if (!label) continue

      // Fetch the strongest gate vector for this concept label
      const vec = this.fetchGateVector(label)
      if (!vec) {
        this.logger.debug('No gate vector found for steering concept', { label })
        continue
      }

      // Determine injection layer from band metadata
      const band = (engram.metadata?.dominantBand as LayerBand) || 'knowledge'
      const layer = bandToLayer(band, 18)

      // Alpha = baseAlpha × potentiation (stronger concepts steer harder)
      const alpha = c.baseAlpha * Math.min(1.0, engram.potentiation)

      steers.push({ layer, alpha, vectorBytes: vec })

      this.logger.debug('Steering vector built', {
        concept: label,
        layer,
        alpha: alpha.toFixed(3),
        potentiation: engram.potentiation.toFixed(2),
        band,
      })
    }

    this.logger.info('Steering vectors built', {
      domain: c.domain,
      candidates: candidates.length,
      steers: steers.length,
    })

    return steers
  }

  /**
   * Run steered generation: build steering vectors from Mnemic engrams
   * matching the current reasoning domain, then inject them during inference.
   *
   * Falls back to unsteered generation when no steering engrams are found.
   */
  steerGeneration(
    prompt: string | number[],
    domain: string,
    maxNewTokens: number,
  ): ReturnType<LarqlKnowledgeProvider['generateWithSteering']> {
    const steers = this.buildSteering({ domain })
    if (steers.length === 0) {
      this.logger.debug('No steering engrams found — running unsteered', { domain })
      return this.larqlProvider.generateWithSteering(prompt, [], maxNewTokens)
    }
    return this.larqlProvider.generateWithSteering(prompt, steers, maxNewTokens)
  }

  /**
   * Build steering vectors for multiple domains simultaneously.
   * Useful when reasoning spans architectural boundaries.
   */
  buildMultiDomainSteering(domains: string[], maxPerDomain = 3): LayerSteer[] {
    const all: LayerSteer[] = []
    for (const domain of domains) {
      const steers = this.buildSteering({ domain, maxVectors: maxPerDomain })
      all.push(...steers)
    }
    return all
  }


  /** Query Mnemic Field for self-model engrams matching a domain tag. */
  private queryCandidates(
    domain: string,
    minPotentiation: number,
  ): Array<{ label: string; potentiation: number; metadata?: Record<string, unknown> }> {
    try {
      // Search for engrams tagged with the domain and source:vindex-self-model
      const query = `domain:${domain} source:vindex-self-model`
      const results = (this.mnemicField as any).search?.(query, 50) ?? []

      return results
        .filter((e: any) =>
          e.nodeType === 'pattern' &&
          e.potentiation >= minPotentiation &&
          e.label,
        )
        .map((e: any) => ({
          label: e.label as string,
          potentiation: e.potentiation as number,
          metadata: e.metadata as Record<string, unknown> | undefined,
        }))
    } catch (err) {
      this.logger.debug('Failed to query steering candidates', { domain, error: String(err) })
      return []
    }
  }

  /** Fetch the strongest gate vector for a concept label. */
  private fetchGateVector(label: string): Uint8Array | null {
    try {
      const tokens = this.larqlProvider.tokenize(label)
      if (tokens.length === 0) return null
      const queryToken = tokens[tokens.length - 1]

      // Search output band for the strongest gate vector
      let bestVec: Uint8Array | null = null
      let bestScore = -Infinity

      for (let layer = 24; layer <= 29; layer++) {
        const hits = (this.larqlProvider as any).gateKnn?.(layer, queryToken, 1)
        if (!hits?.length) continue
        const hit = hits[0]
        if (Math.abs(hit.score) > bestScore) {
          bestScore = Math.abs(hit.score)
          const vec = (this.larqlProvider as any).gateVector?.(layer, hit.featureIndex)
          if (vec) bestVec = vec
        }
      }

      return bestVec
    } catch (err) {
      this.logger.debug('Failed to fetch gate vector for steering', { label, error: String(err) })
      return null
    }
  }
}
