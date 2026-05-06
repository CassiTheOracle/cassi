/**
 * A2 vector-projection composer (Aurora side).
 *
 * Today the spec's §4.2 reads `node.gateVectors` — a `Map<LayerIndex,
 * Float32Array>` per cognitive node. Our N-API binding doesn't surface raw
 * gate vectors yet (browse mode only), so this composer cannot produce the
 * actual residual-stream deltas. What it CAN do today:
 *
 *  - Compute salience per active node from confidence + centrality + resonance
 *    + edge count (the math from §4.2's `computeSalience`)
 *  - Aggregate which layers receive contributions (using `node.modelLayers`)
 *  - Emit empty `Float32Array`s at each contributing layer so callers can
 *    type against the real shape
 *  - Surface a `contributions[]` array driving the A2.4 annotation rendering
 *
 * When the Rust hook + N-API gate-vector exposure land, only the Float32Array
 * fill changes — the contributions stay the same shape.
 *
 * See: docs/design/aurora-vector-projection.md §4
 */

import type {
  CognitiveNode,
  GateContribution,
  MentalState,
  UnifiedGraph,
  VectorProjection,
  VectorProjectionOptions,
} from '../types.js'

const DEFAULT_MAGNITUDE_SCALE = 0.1
const DEFAULT_MAX_NODES = 32

export interface ProjectionContext {
  vindexId?: string | null
  targetModelId?: string | null
}

/**
 * Caller-provided lookup that resolves a `(node, layer)` pair into a raw
 * gate-vector Float32Array. When supplied to `composeVectorProjection`,
 * the composer accumulates `vec * weight` per-layer into the projection's
 * `perLayer` map, replacing the empty-Float32Array placeholder behavior.
 *
 * The callback is intentionally per-(node, layer) so callers control HOW
 * to pick a feature index for each contributing node — Aurora's typical
 * impl uses gate_knn against the node's tokenized label; tests can hand
 * back synthetic vectors keyed by node/layer; etc.
 */
export type GateVectorSource = (node: import('../types.js').CognitiveNode, layer: number) => Float32Array | null

/**
 * Caller-provided lookup that returns the typical residual L2 norm at the
 * given layer (e.g. measured during vindex build or via a probe pass). When
 * supplied alongside `targetResidualFraction`, the composer rescales each
 * layer's accumulated vector so its L2 = `target_fraction * baseline_norm`.
 * This implements spec §4.3 static calibration.
 *
 * Returns `null` when the norm is unknown for that layer; the composer
 * falls back to the un-rescaled vector in that case.
 */
export type BaselineNormSource = (layer: number) => number | null

/**
 * Compose a vector projection from the current mental state.
 *
 * Pure function — caller passes the state plus an optional context with
 * vindex / target-model ids for the projection metadata. Returns `null`
 * when the state has no activated nodes (caller should treat as no-op).
 *
 * When `vectorSource` is supplied, the composer accumulates real
 * `Float32Array` content into `perLayer` (weighted sum across all
 * contributing nodes at each layer). Without it, `perLayer` carries
 * length-zero Float32Array placeholders at each contributing layer —
 * the contributions[] array is still meaningful and feeds A2.4 annotation.
 */
export function composeVectorProjection(
  state: MentalState,
  options: VectorProjectionOptions = {},
  ctx: ProjectionContext = {},
  vectorSource?: GateVectorSource,
  baselineNormSource?: BaselineNormSource,
): VectorProjection | null {
  const magnitudeScale = options.magnitudeScale ?? DEFAULT_MAGNITUDE_SCALE
  const maxNodes = options.maxNodes ?? DEFAULT_MAX_NODES
  const layerSubset = options.layerSubset ? new Set(options.layerSubset) : null
  const targetFraction = options.targetResidualFraction

  const activated = activatedNodes(state.graph)
  if (activated.length === 0) return null

  const maxEdgeCount = computeMaxEdgeCount(state.graph)
  const ranked = activated
    .map(node => ({ node, salience: computeSalience(node, state.graph, maxEdgeCount) }))
    .filter(x => x.salience > 0)
    .sort((a, b) => b.salience - a.salience)
    .slice(0, maxNodes)

  if (ranked.length === 0) return null

  const contributions: GateContribution[] = []
  const perLayer = new Map<number, Float32Array>()

  for (const { node, salience } of ranked) {
    const layers = (node.modelLayers ?? []).filter(l =>
      layerSubset === null ? true : layerSubset.has(l),
    )
    if (layers.length === 0) continue

    const weight = salience * magnitudeScale
    contributions.push({
      nodeId: node.id,
      label: node.label,
      layers: [...layers].sort((a, b) => a - b),
      salience,
      weight,
    })

    for (const layer of layers) {
      const vec = vectorSource ? vectorSource(node, layer) : null
      if (vec === null) {
        // Placeholder: ensure layer is keyed in the map even though no
        // real bytes were resolved.
        if (!perLayer.has(layer)) perLayer.set(layer, new Float32Array(0))
        continue
      }
      const existing = perLayer.get(layer)
      if (!existing || existing.length === 0) {
        const fresh = new Float32Array(vec.length)
        for (let i = 0; i < vec.length; i++) fresh[i] = vec[i] * weight
        perLayer.set(layer, fresh)
      } else if (existing.length === vec.length) {
        for (let i = 0; i < vec.length; i++) existing[i] += vec[i] * weight
      } else {
        // Dimension mismatch — refuse to mix; keep existing.
        // (This shouldn't happen across layers from the same vindex; if it
        // does, the caller's vectorSource is producing inconsistent output.)
      }
    }
  }

  if (contributions.length === 0) return null

  if (targetFraction !== undefined && baselineNormSource && targetFraction > 0) {
    rescaleToCalibrationTarget(perLayer, baselineNormSource, targetFraction)
  }

  return {
    perLayer,
    contributions,
    metadata: {
      contributingNodes: contributions.map(c => c.nodeId),
      targetModelId: ctx.targetModelId ?? null,
      vindexId: ctx.vindexId ?? null,
      composedAt: new Date().toISOString(),
    },
  }
}

/**
 * Rescale each layer's accumulated vector to `target_fraction × baseline`
 * (per spec §4.3 static calibration). Mutates the map in place. Layers
 * with empty placeholders (length 0) and layers whose baseline norm comes
 * back null are left untouched.
 */
function rescaleToCalibrationTarget(
  perLayer: Map<number, Float32Array>,
  baselineNormSource: BaselineNormSource,
  targetFraction: number,
): void {
  for (const [layer, vec] of perLayer) {
    if (vec.length === 0) continue
    const baseline = baselineNormSource(layer)
    if (baseline === null || !Number.isFinite(baseline) || baseline <= 0) continue
    const currentNorm = l2Norm(vec)
    if (currentNorm === 0) continue
    const target = targetFraction * baseline
    const scale = target / currentNorm
    for (let i = 0; i < vec.length; i++) vec[i] *= scale
  }
}

function l2Norm(vec: Float32Array): number {
  let sum = 0
  for (let i = 0; i < vec.length; i++) sum += vec[i] * vec[i]
  return Math.sqrt(sum)
}

function activatedNodes(graph: UnifiedGraph): CognitiveNode[] {
  const out: CognitiveNode[] = []
  for (const node of graph.nodes.values()) {
    if (node.activated) out.push(node)
  }
  return out
}

function computeMaxEdgeCount(graph: UnifiedGraph): number {
  let max = 1
  for (const list of graph.edges.values()) {
    if (list.length > max) max = list.length
  }
  return max
}

/**
 * Salience formula from spec §4.2 (computeSalience). Mapped onto fields
 * we actually have on `CognitiveNode`:
 *
 *   base       = node.modelConfidence (or fallback to resonance)
 *   connectivity = 1 + edgeCount(node) / maxEdgeCount   (well-connected weighs more)
 *   centrality   = 1 + node.centrality                  (PageRank top-up)
 *
 * The spec also calls for affect-bias modulation and momentum dampening.
 * Both depend on signals we don't yet route into the projection (B2 affect
 * coupling lands those properly). For now they're flat at 1.0 — a follow-up
 * once B2 retrieval policies feed in. Output is clamped to [0, 1].
 */
function computeSalience(
  node: CognitiveNode,
  graph: UnifiedGraph,
  maxEdgeCount: number,
): number {
  const base = node.modelConfidence ?? node.resonance ?? 0
  if (base <= 0) return 0
  const edgeCount = (graph.edges.get(node.id)?.length ?? 0)
    + (graph.reverseEdges.get(node.id)?.length ?? 0)
  const connectivity = 1 + edgeCount / Math.max(1, maxEdgeCount)
  const centrality = 1 + (node.centrality ?? 0)
  const raw = base * connectivity * centrality * 0.5
  return Math.min(1, Math.max(0, raw))
}
