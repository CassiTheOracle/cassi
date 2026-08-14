/**
 * InferenceTraceProvider — multi-token inference bridge.
 *
 * Feeds compound prompts through the model's full attention path
 * (EXPLAIN INFER) and captures per-layer feature activation traces.
 * These attention-mediated traces reveal how concepts *interact* during
 * inference — not just static feature associations.
 *
 * Two backends:
 *   - CLI: spawns `larql lql 'EXPLAIN INFER ...'` and parses output.
 *     Works today, ~8s per pair. Used as fallback.
 *   - N-API: calls `traceForward()` directly (Rust extension, Path B).
 *     ~500ms per pair. Preferred when available.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { ConceptBridge } from './self-model-knowledge.js'


export interface TracedFeature {
  layer: number
  featureIndex: number
  gate: number
  topToken: string
  downTokens: string[]
}

export interface BandActivity {
  label: string
  range: string
  featureCount: number
  maxGate: number
  maxToken: string
  maxLayer: number
  meanAbsGate: number
}

export interface BridgeTrace {
  conceptA: string
  conceptB: string
  prompt: string
  /** All captured features from the inference trace. */
  features: TracedFeature[]
  /** Per-band activity summary. */
  bands: {
    syntax: BandActivity | null
    knowledge: BandActivity | null
    output: BandActivity | null
  }
  /** Cross-band amplification ratio (output mean / syntax mean). */
  amplificationRatio: number
  /** Wall-clock duration in ms. */
  durationMs: number
  /** Backend used. */
  backend: 'cli' | 'napi'
}

export interface InferenceTraceResult {
  traces: BridgeTrace[]
  /** Pairs that share co-activated tokens. */
  crossPairTokens: Map<string, string[]>
  totalDurationMs: number
  probedAt: string
}


interface BandBounds { syntax: { start: number; end: number }; knowledge: { start: number; end: number }; output: { start: number; end: number } }

const BAND_BOUNDS: Record<string, BandBounds> = {
  // Gemma 4 E2B: 35 layers
  '35': { syntax: { start: 0, end: 13 }, knowledge: { start: 14, end: 27 }, output: { start: 28, end: 34 } },
  // Gemma 4 26B: 30 layers
  '30': { syntax: { start: 0, end: 11 }, knowledge: { start: 12, end: 23 }, output: { start: 24, end: 29 } },
  // Default fallback
  'default': { syntax: { start: 0, end: 13 }, knowledge: { start: 14, end: 27 }, output: { start: 28, end: 34 } },
}

function getBandBounds(numLayers: number): BandBounds {
  return BAND_BOUNDS[String(numLayers)] ?? BAND_BOUNDS['default']!
}


/** Construct a compound prompt for a concept pair bridge. */
function buildPrompt(a: string, b: string): string {
  // Use relational phrasing that encourages the model to process
  // the concepts together through attention.
  const templates = [
    `${a} and ${b} work together through`,
    `the relationship between ${a} and ${b} involves`,
    `${a} mechanisms connect to ${b} by`,
  ]
  return templates[Math.floor(Math.random() * templates.length)]!
}


// All inference traces go through the N-API traceForward() function.
// No CLI fallback — the Rust extension is always available on daemon boot.

function analyzeBand(features: TracedFeature[], start: number, end: number, label: string): BandActivity | null {
  const band = features.filter(f => f.layer >= start && f.layer <= end)
  if (band.length === 0) return null
  const max = band.reduce((a, b) => Math.abs(a.gate) > Math.abs(b.gate) ? a : b)
  const mean = band.reduce((s, f) => s + Math.abs(f.gate), 0) / band.length
  return {
    label,
    range: `${start}-${end}`,
    featureCount: band.length,
    maxGate: max.gate,
    maxToken: max.topToken,
    maxLayer: max.layer,
    meanAbsGate: mean,
  }
}


export class InferenceTraceProvider {
  private logger: ILogger
  private vindexPath: string
  private numLayers: number
  private napiBackend: {
    handle: any
    tokenize: (text: string) => number[]
    traceForward: (tokens: number[], layerStart: number, layerEnd: number, topK: number) => any
  } | null = null

  constructor(opts: {
    logger: ILogger
    vindexPath: string
    numLayers: number
  }) {
    this.logger = opts.logger.child ? opts.logger.child('inference-trace') : opts.logger
    this.vindexPath = opts.vindexPath
    this.numLayers = opts.numLayers
  }

  /** Wire the N-API backend (Path B). Preferred over CLI for speed. */
  setNapiBackend(backend: {
    handle: any
    tokenize: (text: string) => number[]
    traceForward: (tokens: number[], layerStart: number, layerEnd: number, topK: number) => any
  }): void {
    this.napiBackend = backend
  }

  /**
   * Run inference traces for the top N concept bridges.
   *
   * Each bridge gets a compound prompt run through EXPLAIN INFER,
   * capturing per-layer feature activations across the full attention path.
   *
   * @param bridges Top bridges from SelfModelProbe
   * @param maxPairs Maximum pairs to trace (default 5 to keep latency reasonable)
   * @param topK Features per layer (default 2, matching EXPLAIN INFER default)
   */
  traceBridges(
    bridges: ConceptBridge[],
    maxPairs = 5,
    topK = 2,
  ): InferenceTraceResult {
    const start = Date.now()
    const traces: BridgeTrace[] = []
    const bands = getBandBounds(this.numLayers)

    for (const bridge of bridges.slice(0, maxPairs)) {
      const prompt = buildPrompt(bridge.conceptA, bridge.conceptB)
      const t0 = Date.now()
      let features: TracedFeature[] = []
      let backend: 'cli' | 'napi' = 'cli'

      // N-API backend (only path — CLI fallback removed)
      if (!this.napiBackend) {
        this.logger.warn('No N-API backend wired — inference traces unavailable')
        continue
      }
      try {
        const tokens = this.napiBackend.tokenize(prompt)
        if (tokens.length === 0) continue
        const result = this.napiBackend.traceForward(
          tokens,
          bands.knowledge.start,
          bands.output.end,
          topK,
        )
        if (result?.features) {
          features = result.features.map((f: any) => ({
            layer: f.layer,
            featureIndex: f.featureIndex,
            gate: f.score,
            topToken: f.label ?? '?',
            downTokens: [],
          }))
          backend = 'napi'
        }
      } catch (err) {
        this.logger.warn('N-API traceForward failed for bridge', {
          pair: `${bridge.conceptA}↔${bridge.conceptB}`,
          error: String(err),
        })
        continue
      }

      const elapsed = Date.now() - t0
      const syntax = analyzeBand(features, bands.syntax.start, bands.syntax.end, 'Syntax')
      const knowledge = analyzeBand(features, bands.knowledge.start, bands.knowledge.end, 'Knowledge')
      const output = analyzeBand(features, bands.output.start, bands.output.end, 'Output')
      const amp = (output?.meanAbsGate ?? 1) / Math.max(1, syntax?.meanAbsGate ?? 1)

      traces.push({
        conceptA: bridge.conceptA,
        conceptB: bridge.conceptB,
        prompt,
        features,
        bands: { syntax, knowledge, output },
        amplificationRatio: amp,
        durationMs: elapsed,
        backend,
      })
    }

    // Cross-pair token sharing analysis
    const crossPairTokens = new Map<string, string[]>()
    for (let i = 0; i < traces.length; i++) {
      for (let j = i + 1; j < traces.length; j++) {
        const aTokens = new Set(traces[i]!.features.map(f => f.topToken))
        const bTokens = new Set(traces[j]!.features.map(f => f.topToken))
        const shared = [...aTokens].filter(t => bTokens.has(t))
        if (shared.length > 0) {
          const key = `${traces[i]!.conceptA}↔${traces[i]!.conceptB} & ${traces[j]!.conceptA}↔${traces[j]!.conceptB}`
          crossPairTokens.set(key, shared)
        }
      }
    }

    const totalDurationMs = Date.now() - start
    this.logger.info('Inference traces complete', {
      pairs: traces.length,
      totalDurationMs,
      avgMsPerPair: traces.length > 0 ? Math.round(totalDurationMs / traces.length) : 0,
      napiBackend: !!this.napiBackend,
    })

    return {
      traces,
      crossPairTokens,
      totalDurationMs,
      probedAt: new Date().toISOString(),
    }
  }

  /**
   * Generate enriched Mnemic metadata for a bridge trace.
   *
   * Produces tags and metadata suitable for EngramCreate.metadata
   * so the kindling system can surface inference-mediated connections.
   */
  traceMetadata(trace: BridgeTrace): Record<string, unknown> {
    return {
      inferenceBridge: true,
      prompt: trace.prompt,
      amplificationRatio: trace.amplificationRatio,
      syntaxMeanGate: trace.bands.syntax?.meanAbsGate,
      knowledgeMeanGate: trace.bands.knowledge?.meanAbsGate,
      outputMeanGate: trace.bands.output?.meanAbsGate,
      topFeatures: trace.features
        .sort((a, b) => Math.abs(b.gate) - Math.abs(a.gate))
        .slice(0, 5)
        .map(f => ({ layer: f.layer, gate: f.gate, token: f.topToken })),
      backend: trace.backend,
    }
  }
}