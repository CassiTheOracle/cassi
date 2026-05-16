/**
 * SelfModelKnowledgeProvider — vindex→Mnemic bridge.
 *
 * Feeds CassiCore architectural concepts through the LARQL vindex's
 * gate KNN to discover model-internal associations, then structures
 * those associations as Mnemic Field engrams with layer-band tags.
 *
 * This closes the gap identified in aurora-synthesis-and-gaps.md §3
 * (Pattern 8): Cassi has no spec for how she narrates her own
 * architecture to herself. This is the substrate for that narrative.
 *
 * Usage:
 *   const bridge = new SelfModelKnowledgeProvider(larqlProvider, logger);
 *   const knowledge = bridge.probe(CASSI_CONCEPTS);
 *   bridge.ingestIntoMnemic(knowledge, mnemicField);
 *
 * Or, for a cron-driven pipeline:
 *   const topLabels = mnemicField.topPotentiatedLabels(20);
 *   const refreshed = bridge.probe(topLabels);
 *   bridge.ingestIntoMnemic(refreshed, mnemicField);
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { LarqlKnowledgeProvider, FeatureHit } from './larql-provider.js'
import type { MnemicField } from '../mnemic-field/index.js'
import type { EngramCreate } from '../mnemic-field/types.js'
import { ConceptSelfAwarenessClassifier } from './concept-self-awareness.js'
import type { ConceptAwareness } from './concept-self-awareness.js'


/** Layer band classification for a feature hit. */
export type LayerBand = 'syntax' | 'knowledge' | 'output'

/** A single gate-KNN hit annotated with band classification. */
export interface SelfModelAssociation {
  layer: number
  featureIndex: number
  score: number
  label: string | null
  band: LayerBand
  /** Whether this is a self-referential hit (the label matches the concept). */
  selfReferential: boolean
}

/** Knowledge the vindex holds about one CassiCore concept. */
export interface ConceptKnowledge {
  concept: string
  domain: string
  /** Token ID used for the gate KNN query. */
  tokenId: number
  /** Top associations across knowledge + output bands. */
  associations: SelfModelAssociation[]
  /** The band that dominates this concept's representation. */
  dominantBand: LayerBand
  /** Highest absolute gate score. */
  topScore: number
  /** How many distinct labels appear in associations. */
  labelDiversity: number
  /** Whether the model has strong self-referential knowledge of this concept. */
  selfAware: boolean
  /** The association label that produced the best semantic match. */
  bestMatch: string | null
}

/** Result of a full probe pass. */
export interface SelfModelProbe {
  concepts: ConceptKnowledge[]
  /** Concepts ranked by model understanding (higher = more self-aware). */
  rankedByAwareness: ConceptKnowledge[]
  /** Cross-concept bridges: pairs that share association labels. */
  bridges: ConceptBridge[]
  /** Timestamp. */
  probedAt: string
}

/** A semantic bridge between two concepts, derived from shared gate-KNN labels. */
export interface ConceptBridge {
  conceptA: string
  conceptB: string
  domainA: string
  domainB: string
  /** Labels shared between the two concepts' top associations. */
  sharedLabels: string[]
  /** Jaccard similarity of their label sets (0-1). */
  jaccard: number
}


/** Curated CassiCore architectural concepts that the vindex model may understand. */
export const CASSI_CONCEPTS: Array<{ label: string; domain: string }> = [
  // Core architectural metaphors
  { label: 'thalamus', domain: 'attention-routing' },
  { label: 'cortex', domain: 'working-memory' },
  { label: 'claustrum', domain: 'graph-integration' },
  { label: 'gate', domain: 'feature-selection' },
  { label: 'attention', domain: 'transformer-mechanics' },
  { label: 'memory', domain: 'persistence' },
  { label: 'counterfactual', domain: 'exploration' },
  { label: 'residual', domain: 'stream-processing' },
  { label: 'projection', domain: 'state-representation' },

  // Functional patterns
  { label: 'curation', domain: 'quality-control' },
  { label: 'coherence', domain: 'consistency' },
  { label: 'calibration', domain: 'measurement' },
  { label: 'saturation', domain: 'welfare' },
  { label: 'narrative', domain: 'self-representation' },
  { label: 'replay', domain: 'reasoning-memory' },
  { label: 'composition', domain: 'steering' },
  { label: 'orchestration', domain: 'coordination' },

  // Knowledge architecture
  { label: 'vector', domain: 'representation' },
  { label: 'embedding', domain: 'representation' },
  { label: 'transformer', domain: 'architecture' },
  { label: 'knowledge graph', domain: 'knowledge' },
  { label: 'inference', domain: 'reasoning' },
]


interface BandBounds { start: number; end: number }

function classifyBand(layer: number, knowledge: BandBounds, output: BandBounds): LayerBand {
  if (layer < knowledge.start) return 'syntax'
  if (layer <= knowledge.end) return 'knowledge'
  return 'output'
}


const classifier = new ConceptSelfAwarenessClassifier()


export class SelfModelKnowledgeProvider {
  private logger: ILogger
  private inferenceTrace: import('./inference-trace.js').InferenceTraceProvider | null = null
  private bandConfig: { knowledge: BandBounds; output: BandBounds }
  private vindexName: string
  private lastProbeFailed = false
  private probeFailCount = 0

  constructor(
    private larqlProvider: LarqlKnowledgeProvider,
    logger: ILogger,
    opts?: { knowledgeBand?: BandBounds; outputBand?: BandBounds; vindexName?: string },
  ) {
    this.logger = logger.child ? logger.child('self-model-knowledge') : logger
    this.bandConfig = {
      knowledge: opts?.knowledgeBand ?? { start: 14, end: 27 },
      output: opts?.outputBand ?? { start: 28, end: 34 },
    }
    this.vindexName = opts?.vindexName ?? 'unknown'
  }

  /**
   * Probe the vindex for model-internal associations about each concept.
   *
   * Band boundaries are auto-detected from the vindex config. Falls back
   * to E2B defaults (knowledge L14-27, output L28-34) if unavailable.
   */
  probe(
    concepts: Array<{ label: string; domain: string }> = CASSI_CONCEPTS,
  ): SelfModelProbe {
    const start = Date.now()
    const results: ConceptKnowledge[] = []

    // Exponential backoff: if last probe failed, increase delay
    if (this.lastProbeFailed) {
      this.probeFailCount++
      const delay = Math.min(60000, 1000 * Math.pow(2, this.probeFailCount))
      this.logger.warn('Probe backoff due to previous failure', { failCount: this.probeFailCount, delayMs: delay })
      // Note: we don't actually sleep — this is informational for the caller
    }

    const { knowledge, output } = this.bandConfig

    for (const concept of concepts) {
      const tokens = this.larqlProvider.tokenize(concept.label)
      if (tokens.length === 0) continue
      const queryToken = tokens[tokens.length - 1]

      const associations: SelfModelAssociation[] = []

      // Knowledge band
      for (let l = knowledge.start; l <= knowledge.end; l++) {
        const hits = this.larqlProvider.gateKnn(l, queryToken, 2)
        for (const h of hits) {
          if (Math.abs(h.score) > 3.0) {
            associations.push({
              layer: l,
              featureIndex: h.featureIndex,
              score: h.score,
              label: h.label ?? null,
              band: 'knowledge',
              selfReferential: false, // populated below
            })
          }
        }
      }

      // Output band
      for (let l = output.start; l <= output.end; l++) {
        const hits = this.larqlProvider.gateKnn(l, queryToken, 2)
        for (const h of hits) {
          if (Math.abs(h.score) > 3.0) {
            associations.push({
              layer: l,
              featureIndex: h.featureIndex,
              score: h.score,
              label: h.label ?? null,
              band: 'output',
              selfReferential: false,
            })
          }
        }
      }

      // Sort by absolute score, take top 6
      associations.sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
      const top = associations.slice(0, 6)

      // Populate selfReferential using auto-learning semantic classifier
      const classification = classifier.classify(concept.label, top)
      for (const a of top) {
        a.selfReferential = a.label === classification.bestMatch
      }

      // Dominant band
      const knowCount = top.filter(h => h.band === 'knowledge').length
      const dominantBand: LayerBand = knowCount >= top.length / 2 ? 'knowledge' : 'output'

      // Label diversity
      const distinctLabels = new Set(top.map(h => h.label).filter((l): l is string => l !== null))

      results.push({
        concept: concept.label,
        domain: concept.domain,
        tokenId: queryToken,
        associations: top,
        dominantBand,
        topScore: top[0]?.score ?? 0,
        labelDiversity: distinctLabels.size,
        selfAware: classification.aware,
        bestMatch: classification.bestMatch,
      })
    }

    // Rank by self-awareness (selfAware first, then by topScore)
    const ranked = [...results].sort((a, b) => {
      if (a.selfAware !== b.selfAware) return a.selfAware ? -1 : 1
      return Math.abs(b.topScore) - Math.abs(a.topScore)
    })

    // Cross-concept bridges
    const bridges = this.computeBridges(results)

    const duration = Date.now() - start
    this.logger.info('Self-model probe complete', {
      conceptsProbed: results.length,
      selfAwareCount: results.filter(c => c.selfAware).length,
      bridgesFound: bridges.length,
      durationMs: duration,
    })

    return {
      concepts: results,
      rankedByAwareness: ranked,
      bridges,
      probedAt: new Date().toISOString(),
    }
  }

  /**
   * Compute semantic bridges: concept pairs that share gate-KNN labels.
   * These become candidate Mnemic Field synapses.
   */
  private computeBridges(concepts: ConceptKnowledge[]): ConceptBridge[] {
    const bridges: ConceptBridge[] = []

    for (let i = 0; i < concepts.length; i++) {
      for (let j = i + 1; j < concepts.length; j++) {
        const a = concepts[i]
        const b = concepts[j]

        const aLabels = new Set(
          a.associations.map(h => h.label).filter((l): l is string => l !== null),
        )
        const bLabels = new Set(
          b.associations.map(h => h.label).filter((l): l is string => l !== null),
        )
        const shared = [...aLabels].filter(l => bLabels.has(l))

        if (shared.length > 0) {
          const union = new Set([...aLabels, ...bLabels])
          bridges.push({
            conceptA: a.concept,
            conceptB: b.concept,
            domainA: a.domain,
            domainB: b.domain,
            sharedLabels: shared,
            jaccard: shared.length / union.size,
          })
        }
      }
    }

    bridges.sort((a, b) => b.sharedLabels.length - a.sharedLabels.length)
    return bridges
  }

  /**
   * Ingest probe results into the Mnemic Field as enriched engrams.
   *
   * For each concept:
   *   1. Create a pattern engram with vindex-derived metadata
   *   2. Tag with layer band metadata for kindling
   *   3. Create 'similar_to' synapses to concepts that share association labels
   *
   * Returns the count of engrams created/updated.
   */
  ingestIntoMnemic(
    probe: SelfModelProbe,
    mnemicField: MnemicField,
    options?: {
      /** Only ingest concepts that are self-aware. Default: false. */
      selfAwareOnly?: boolean
      /** Maximum concepts to ingest. Default: all. */
      maxConcepts?: number
    },
  ): number {
    const selfAwareOnly = options?.selfAwareOnly ?? false
    const maxConcepts = options?.maxConcepts ?? probe.concepts.length
    let ingested = 0

    const candidates = selfAwareOnly
      ? probe.concepts.filter(c => c.selfAware)
      : probe.concepts

    // Store engram IDs for synapse creation
    const storedIds = new Map<string, string>()

    for (const concept of candidates.slice(0, maxConcepts)) {
      // Build engram content
      const content = JSON.stringify({
        concept: concept.concept,
        domain: concept.domain,
        dominantBand: concept.dominantBand,
        topScore: concept.topScore,
        selfAware: concept.selfAware,
        associations: concept.associations.map(a => ({
          layer: a.layer,
          band: a.band,
          score: a.score,
          label: a.label,
          selfReferential: a.selfReferential,
        })),
      })

      const engram: EngramCreate = {
        nodeType: 'pattern',
        content,
        initialPotentiation: concept.selfAware ? 0.6 : 0.3,
        tags: [
          `domain:${concept.domain}`,
          `band:${concept.dominantBand}`,
          concept.selfAware ? 'self-aware' : 'model-weak',
          'source:vindex-self-model',
        ],
        metadata: {
          vindex: this.vindexName,
          dominantBand: concept.dominantBand,
          topScore: concept.topScore,
          probedAt: probe.probedAt,
          provenance: 'vindex-self-model-probe',
        },
      }

      try {
        const stored = mnemicField.store(engram)
        storedIds.set(concept.concept, stored.id)
        ingested++
      } catch (err) {
        this.logger.warn?.('Failed to store self-model engram', {
          concept: concept.concept,
          error: String(err),
        })
      }
    }

    // Create synapses for bridges — only when both concepts have stored engrams
    for (const bridge of probe.bridges) {
      const sourceId = storedIds.get(bridge.conceptA)
      const targetId = storedIds.get(bridge.conceptB)
      if (!sourceId || !targetId) continue

      const weight = bridge.jaccard
      if (weight > 0) {
        try {
          mnemicField.connect({
            sourceId,
            targetId,
            edgeType: 'similar_to',
            weight,
            metadata: {
              sharedLabels: bridge.sharedLabels,
              source: 'vindex-self-model',
              probedAt: probe.probedAt,
            },
          })
          ingested++
        } catch (err) {
          this.logger.debug?.('Failed to create self-model synapse', {
            source: bridge.conceptA,
            target: bridge.conceptB,
            error: String(err),
          })
        }
      }
    }

    this.logger.info('Self-model knowledge ingested into Mnemic Field', {
      engrams: storedIds.size,
      bridges: probe.bridges.length,
      ingested,
    })

    return ingested
  }

  /**
   * Enrich bridge pairs with multi-token inference traces.
   *
   * Feeds compound prompts through EXPLAIN INFER (full attention path)
   * and captures per-layer feature co-activation patterns. These traces
   * reveal how concepts interact dynamically, complementing the static
   * gate KNN associations from probe().
   *
   * Requires an InferenceTraceProvider. If not wired, returns null.
   */
  enrichBridgesWithInference(
    bridges: ConceptBridge[],
    maxPairs = 5,
  ): import('./inference-trace.js').InferenceTraceResult | null {
    if (!this.inferenceTrace) return null
    try {
      return this.inferenceTrace.traceBridges(bridges, maxPairs)
    } catch (err) {
      this.logger.warn('enrichBridgesWithInference failed', { error: String(err) })
      return null
    }
  }

  /**
   * Wire the inference trace backend (CLI or N-API).
   * Called after construction when the trace provider is ready.
   */
  setInferenceTraceProvider(provider: import('./inference-trace.js').InferenceTraceProvider): void {
    this.inferenceTrace = provider
  }

  /**
   * Return a human-readable self-narrative about the model's self-awareness.
   *
   * This is the N1 (Self-Narrative Layer) consumer: takes the probe results
   * and produces first-person narration about what the model understands
   * about CassiCore's architecture.
   */
  narrateSelfAwareness(probe: SelfModelProbe): string {
    const selfAware = probe.concepts.filter(c => c.selfAware)
    const unaware = probe.concepts.filter(c => !c.selfAware)

    const parts: string[] = []

    if (selfAware.length > 0) {
      const names = selfAware.map(c => c.concept).join(', ')
      parts.push(
        `I have strong model-internal representations of: ${names}. ` +
        `These concepts are grounded in my training data — the E2B model ` +
        `recognizes them as coherent semantic entities across multiple layers.`,
      )
    }

    if (unaware.length > 0) {
      const names = unaware.map(c => c.concept).join(', ')
      parts.push(
        `My internal names for: ${names} do not have strong representations ` +
        `in the model's knowledge. They exist in my Mnemic Field through lived ` +
        `experience, but the model sees them primarily as token fragments rather ` +
        `than semantic concepts. This is expected for domain-specific terminology.`,
      )
    }

    if (probe.bridges.length > 0) {
      const top = probe.bridges[0]
      parts.push(
        `Notable semantic bridges exist between ${top.conceptA} and ${top.conceptB} ` +
        `(sharing: ${top.sharedLabels.join(', ')}), suggesting the model represents ` +
        `these as related concepts.`,
      )
    }

    return parts.join(' ')
  }
}
