/**
 * Dream Engine — discovers hidden connections by walking engrams through the vindex.
 *
 * During consolidation's "dreaming" phase, high-potentiation engrams are
 * tokenized and walked through the model's knowledge graph (gate KNN).
 * When two engrams activate the same features at the same layers,
 * they're semantically connected in the model's knowledge even if the
 * Mnemic Field has no synapse between them. The dream engine creates
 * these discovery synapses, strengthening the memory graph with
 * associations the model knows about but we haven't explicitly linked.
 *
 * This is analogous to biological dreaming: replaying recent memories
 * through associative networks to discover hidden patterns.
 */

import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from '@cassicore/mnemic-field'
import type { Engram, SynapseType } from '@cassicore/mnemic-field'

/**
 * Feature activation fingerprint for a single engram.
 * Maps (layer, featureIndex) pairs to gate scores.
 */
interface FeatureFingerprint {
  engramId: string
  contentPreview: string
  /** Map key = "L{layer}:F{feature}", value = gate score */
  features: Map<string, number>
  /** Total features collected across all scanned layers */
  totalFeatures: number
  /** Timestamp of fingerprinting */
  computedAt: number
  /** Semantic classification label from Thalamus write-side routing */
  semanticType?: string
}

/**
 * A discovered connection between two engrams via shared features.
 */
export interface DreamDiscovery {
  sourceId: string
  targetId: string
  /** Number of shared features across all scanned layers */
  sharedFeatureCount: number
  /** Jaccard similarity: |intersection| / |union| of feature sets */
  jaccardSimilarity: number
  /** Cosine similarity of gate score vectors over shared features */
  gateScoreCorrelation: number
  /** Which layers had the most overlap */
  topOverlapLayers: Array<{ layer: number; sharedCount: number }>
  /** Combined similarity score used for synapse weight */
  combinedScore: number
}

/**
 * Result of a dreaming cycle.
 */
export interface DreamResult {
  /** Engrams selected as dream seeds */
  seedCount: number
  /** Feature fingerprints computed */
  fingerprintsComputed: number
  /** Engram pairs with significant feature overlap */
  discoveries: DreamDiscovery[]
  /** Synapses actually created (after dedup with existing) */
  synapsesCreated: number
  /** Total duration in ms */
  durationMs: number
}

/**
 * Configuration for the dream engine.
 */
export interface DreamConfig {
  /** Max engrams to use as dream seeds per cycle */
  maxSeeds: number
  /** Minimum potentiation to be selected as a seed */
  minPotentiation: number
  /** Knowledge layers to scan (default: L14-L27 for Gemma 3 4B) */
  knowledgeLayers: number[]
  /** Top-K features per layer per engram */
  featuresPerLayer: number
  /** Minimum Jaccard similarity to create a synapse */
  minJaccardSimilarity: number
  /** Minimum shared features to consider a connection */
  minSharedFeatures: number
  /** Synapse type for dream-discovered connections */
  synapseType: SynapseType
  /** Base weight for dream-discovered synapses (scaled by similarity) */
  baseSynapseWeight: number
  /** Maximum synapses to create per dream cycle */
  maxSynapsesPerCycle: number
}

export const DREAM_DEFAULTS: DreamConfig = {
  maxSeeds: 20,
  minPotentiation: 0.3,
  knowledgeLayers: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
  featuresPerLayer: 10,
  minJaccardSimilarity: 0.15,
  minSharedFeatures: 3,
  synapseType: 'similar_to',
  baseSynapseWeight: 0.5,
  maxSynapsesPerCycle: 50,
}

/**
 * Callback for vindex gate KNN operations.
 * Abstracts the LARQL native bindings so the dream engine
 * can be tested without the native module.
 */
export interface VindexGateKnnProvider {
  /** Tokenize text and return token IDs */
  tokenize(text: string): number[]
  /** Run gate KNN for a token at a layer, return (featureIndex, score) pairs */
  gateKnn(layer: number, tokenId: number, topK: number): Array<{ featureIndex: number; score: number }>
}

/** Feature index interface for cross-modal discovery. */
export interface FeatureIndexForDream {
  findCorrelated(
    engramId: string,
    options?: { minOverlap?: number; limit?: number; sameSourceOnly?: boolean },
  ): Array<{ engramId: string; sharedFeatureCount: number }>
}

/** Result of a cross-modal discovery cycle. */
export interface CrossModalResult {
  textEngramsScanned: number
  spatialMatchesFound: number
  synapsesCreated: number
  durationMs: number
}

/**
 * DreamEngine — discovers hidden connections during consolidation.
 */
export class DreamEngine {
  private config: DreamConfig
  private logger: ILogger
  private featureIndex: FeatureIndexForDream | null = null

  constructor(
    private cortex: Cortex,
    private vindexProvider: VindexGateKnnProvider,
    logger: ILogger,
    config?: Partial<DreamConfig>,
  ) {
    this.logger = logger.child ? logger.child('dream-engine') : logger
    this.config = { ...DREAM_DEFAULTS, ...config }
  }

  /** Wire the FeatureIndex for cross-modal discovery. */
  setFeatureIndex(fi: FeatureIndexForDream | null): void {
    this.featureIndex = fi
  }

  /**
   * Run a dreaming cycle: fingerprint seeds, find overlaps, create synapses.
   */
  async dream(): Promise<DreamResult> {
    const start = Date.now()

    // Phase 1: Select dream seeds (high-potentiation engrams)
    const seeds = this.selectSeeds()
    if (seeds.length < 2) {
      this.logger.debug('Not enough seeds for dreaming', { seedCount: seeds.length })
      return { seedCount: seeds.length, fingerprintsComputed: 0, discoveries: [], synapsesCreated: 0, durationMs: Date.now() - start }
    }

    // Phase 2: Compute feature fingerprints for each seed
    const fingerprints: FeatureFingerprint[] = []
    for (const seed of seeds) {
      const fp = this.fingerprint(seed)
      if (fp.totalFeatures > 0) {
        fingerprints.push(fp)
      }
      // Yield to event loop between fingerprints (each does ~14 KNN calls)
      await new Promise(resolve => setImmediate(resolve))
    }

    // Phase 3: Compare all pairs, find discoveries
    const discoveries = this.findDiscoveries(fingerprints)

    // Phase 4: Create synapses for discoveries (skip existing)
    let synapsesCreated = 0
    for (const discovery of discoveries) {
      if (synapsesCreated >= this.config.maxSynapsesPerCycle) break

      const created = this.maybeCreateSynapse(discovery)
      if (created) synapsesCreated++
    }

    const durationMs = Date.now() - start

    this.logger.info('Dream cycle complete', {
      seeds: seeds.length,
      fingerprints: fingerprints.length,
      discoveries: discoveries.length,
      synapsesCreated,
      durationMs,
    })

    return {
      seedCount: seeds.length,
      fingerprintsComputed: fingerprints.length,
      discoveries,
      synapsesCreated,
      durationMs,
    }
  }

  /**
   * Select high-potentiation engrams as dream seeds.
   */
  private selectSeeds(): Engram[] {
    const engrams = this.cortex.listEngrams(this.config.maxSeeds * 2) // fetch extra for filtering
    return engrams
      .filter(e => e.potentiation >= this.config.minPotentiation)
      .slice(0, this.config.maxSeeds)
  }

  /**
   * Compute a feature fingerprint for an engram by walking it through the vindex.
   *
   * Tokenizes the engram content, takes the last meaningful token,
   * and runs gate KNN across all knowledge layers.
   */
  private fingerprint(engram: Engram): FeatureFingerprint {
    const features = new Map<string, number>()

    // Tokenize the engram content (truncate to first 100 chars for efficiency)
    const text = engram.content.slice(0, 100)
    const tokens = this.vindexProvider.tokenize(text)

    if (tokens.length === 0) {
      return { engramId: engram.id, contentPreview: text.slice(0, 50), features, totalFeatures: 0, computedAt: Date.now() }
    }

    // Use the last non-special token as the query
    // (it carries the most semantic weight in autoregressive models)
    const queryToken = tokens[tokens.length - 1]

    // Walk across knowledge layers using multiple tokens for broader coverage.
    // Using only the last token discards ~99% of the engram's content — a 2000-char
    // decision engram would be reduced to one token's feature neighborhood.
    const queryTokens = [
      tokens[0],                          // first meaningful token
      tokens[tokens.length - 1],          // last token
      tokens[Math.floor(tokens.length / 2)],  // midpoint token
    ]
    const seenFeatures = new Set<string>()
    for (const queryToken of [...new Set(queryTokens)]) {
      for (const layer of this.config.knowledgeLayers) {
        const hits = this.vindexProvider.gateKnn(layer, queryToken, this.config.featuresPerLayer)
        for (const hit of hits) {
          const key = `L${layer}:F${hit.featureIndex}`
          if (seenFeatures.has(key)) continue
          seenFeatures.add(key)
          features.set(key, hit.score)
        }
      }
    }

    return {
      engramId: engram.id,
      contentPreview: text.slice(0, 50),
      features,
      totalFeatures: features.size,
      computedAt: Date.now(),
      semanticType: engram.metadata?.semanticType as string | undefined,
    }
  }

  /**
   * Compare all fingerprint pairs and find significant overlaps.
   */
  private findDiscoveries(fingerprints: FeatureFingerprint[]): DreamDiscovery[] {
    const discoveries: DreamDiscovery[] = []

    for (let i = 0; i < fingerprints.length; i++) {
      for (let j = i + 1; j < fingerprints.length; j++) {
        const a = fingerprints[i]
        const b = fingerprints[j]

        const discovery = this.comparePair(a, b)
        if (discovery) {
          discoveries.push(discovery)
        }
      }
    }

    // Sort by combined score descending
    discoveries.sort((a, b) => b.combinedScore - a.combinedScore)

    return discoveries
  }

  /**
   * Compare two fingerprints and return a discovery if they overlap significantly.
   */
  private comparePair(a: FeatureFingerprint, b: FeatureFingerprint): DreamDiscovery | null {
    // Find shared feature keys
    const sharedKeys: string[] = []
    for (const key of a.features.keys()) {
      if (b.features.has(key)) {
        sharedKeys.push(key)
      }
    }

    if (sharedKeys.length < this.config.minSharedFeatures) {
      return null
    }

    // Jaccard similarity: |A ∩ B| / |A ∪ B|
    const unionSize = new Set([...a.features.keys(), ...b.features.keys()]).size
    const jaccardSimilarity = sharedKeys.length / unionSize

    if (jaccardSimilarity < this.config.minJaccardSimilarity) {
      return null
    }

    // Gate score correlation over shared features
    let dotProduct = 0
    let normA = 0
    let normB = 0
    for (const key of sharedKeys) {
      const scoreA = a.features.get(key)!
      const scoreB = b.features.get(key)!
      dotProduct += scoreA * scoreB
      normA += scoreA * scoreA
      normB += scoreB * scoreB
    }
    const gateScoreCorrelation = (normA > 0 && normB > 0)
      ? dotProduct / (Math.sqrt(normA) * Math.sqrt(normB))
      : 0

    // Per-layer overlap counts
    const layerOverlaps = new Map<number, number>()
    for (const key of sharedKeys) {
      const layer = parseInt(key.split(':')[0].slice(1))
      layerOverlaps.set(layer, (layerOverlaps.get(layer) ?? 0) + 1)
    }
    const topOverlapLayers = [...layerOverlaps.entries()]
      .map(([layer, sharedCount]) => ({ layer, sharedCount }))
      .sort((a, b) => b.sharedCount - a.sharedCount)
      .slice(0, 5)

    // Combined score: weighted blend of Jaccard and gate correlation
    let combinedScore = 0.6 * jaccardSimilarity + 0.4 * Math.max(0, gateScoreCorrelation)

    // Type boost: same semantic type (both decisions, both insights, etc.)
    // increases the connection score by 25% — the system discovers more
    // relationships between engrams of the same conceptual kind.
    if (a.semanticType && a.semanticType === b.semanticType) {
      combinedScore *= 1.25
    }

    return {
      sourceId: a.engramId,
      targetId: b.engramId,
      sharedFeatureCount: sharedKeys.length,
      jaccardSimilarity,
      gateScoreCorrelation,
      topOverlapLayers,
      combinedScore,
    }
  }

  /**
   * Create a synapse for a discovery, unless one already exists.
   */
  private maybeCreateSynapse(discovery: DreamDiscovery): boolean {
    // Check if synapse already exists (either direction)
    const existing = this.cortex.getSynapse(
      discovery.sourceId,
      discovery.targetId,
      this.config.synapseType,
    )
    if (existing) return false

    const reverse = this.cortex.getSynapse(
      discovery.targetId,
      discovery.sourceId,
      this.config.synapseType,
    )
    if (reverse) return false

    // Create the synapse with weight proportional to combined score
    const weight = this.config.baseSynapseWeight * discovery.combinedScore

    this.cortex.createSynapse({
      sourceId: discovery.sourceId,
      targetId: discovery.targetId,
      edgeType: this.config.synapseType,
      weight,
      metadata: {
        discoveredBy: 'dream-engine',
        sharedFeatures: discovery.sharedFeatureCount,
        jaccardSimilarity: discovery.jaccardSimilarity,
        gateCorrelation: discovery.gateScoreCorrelation,
        topLayers: discovery.topOverlapLayers.slice(0, 3),
      },
    })

    this.logger.debug('Dream synapse created', {
      source: discovery.sourceId,
      target: discovery.targetId,
      sharedFeatures: discovery.sharedFeatureCount,
      jaccard: discovery.jaccardSimilarity.toFixed(3),
      weight: weight.toFixed(3),
    })

    return true
  }

  /**
   * Discover cross-modal connections between text engrams and spatial (3D) engrams.
   *
   * Iterates text engrams, queries FeatureIndex with sameSourceOnly=false to find
   * spatial engrams that share vindex features. Creates `cross_modal` synapses
   * where text and 3D content activate the same model features.
   *
   * This is the "killer feature" — text queries retrieving 3D engrams via
   * cross-modal synapses, enabled by the TRELLIS.2 vindex sharing the same
   * S¹⁵³⁵ gate vector space as Gemma.
   */
  async discoverCrossModalConnections(): Promise<CrossModalResult> {
    const start = Date.now()

    if (!this.featureIndex) {
      this.logger.debug('Cross-modal discovery skipped: no FeatureIndex wired')
      return { textEngramsScanned: 0, spatialMatchesFound: 0, synapsesCreated: 0, durationMs: 0 }
    }

    const allEngrams = this.cortex.listEngrams(this.config.maxSeeds * 5)
    const textEngrams = allEngrams.filter(e =>
      e.nodeType !== 'spatial_feature' && e.content && e.content.length > 20,
    )
    const spatialIds = new Set(
      allEngrams.filter(e => e.nodeType === 'spatial_feature').map(e => e.id),
    )

    if (textEngrams.length === 0 || spatialIds.size === 0) {
      this.logger.debug('Cross-modal discovery skipped: no text or spatial engrams', {
        textCount: textEngrams.length,
        spatialCount: spatialIds.size,
      })
      return { textEngramsScanned: 0, spatialMatchesFound: 0, synapsesCreated: 0, durationMs: Date.now() - start }
    }

    let spatialMatchesFound = 0
    let synapsesCreated = 0
    const maxCrossModal = Math.min(this.config.maxSynapsesPerCycle, 30)

    for (const textEngram of textEngrams) {
      if (synapsesCreated >= maxCrossModal) break

      const correlated = this.featureIndex.findCorrelated(textEngram.id, {
        sameSourceOnly: false,
        minOverlap: this.config.minSharedFeatures,
        limit: 10,
      })

      for (const match of correlated) {
        if (synapsesCreated >= maxCrossModal) break
        if (!spatialIds.has(match.engramId)) continue

        spatialMatchesFound++

        const existing = this.cortex.getSynapse(textEngram.id, match.engramId, 'cross_modal')
          ?? this.cortex.getSynapse(match.engramId, textEngram.id, 'cross_modal')
        if (existing) continue

        const weight = this.config.baseSynapseWeight * Math.min(1, match.sharedFeatureCount / 10) * 1.3

        this.cortex.createSynapse({
          sourceId: textEngram.id,
          targetId: match.engramId,
          edgeType: 'cross_modal',
          weight,
          metadata: {
            discoveredBy: 'dream-engine-cross-modal',
            sharedFeatures: match.sharedFeatureCount,
            textContent: textEngram.content.slice(0, 80),
          },
        })

        synapsesCreated++

        this.logger.debug('Cross-modal synapse created', {
          text: textEngram.id.slice(0, 12),
          spatial: match.engramId.slice(0, 12),
          sharedFeatures: match.sharedFeatureCount,
          weight: weight.toFixed(3),
        })
      }

      await new Promise(resolve => setImmediate(resolve))
    }

    const durationMs = Date.now() - start

    this.logger.info('Cross-modal discovery complete', {
      textScanned: textEngrams.length,
      spatialAvailable: spatialIds.size,
      spatialMatchesFound,
      synapsesCreated,
      durationMs,
    })

    return { textEngramsScanned: textEngrams.length, spatialMatchesFound, synapsesCreated, durationMs }
  }
}
