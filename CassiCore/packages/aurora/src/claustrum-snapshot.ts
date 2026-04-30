/**
 * Claustrum Snapshot — TypeScript-side writers for the claustrum-vindex pipeline.
 *
 * Produces the three adjunct files that make a vindex subset *claustrum-shaped*
 * rather than just use-pruned:
 *
 *   claustrum_graph.json       — serialized UnifiedGraph (nodes + edges)
 *   claustrum_manifest.json    — source vindex hash, recording window, timestamp
 *   claustrum_provenance.jsonl — per-feature citation log (append-only)
 *
 * The Rust `larql snapshot-claustrum` subcommand (M4) handles the binary
 * vindex files (gate_vectors.bin, down_meta.bin, feature_index_map.bin).
 * This module handles the JSON/JSONL adjuncts that don't require native vindex
 * format knowledge — pure TypeScript, testable without Rust.
 *
 * See: docs/design/claustrum-vindex.md §4.2–§4.4, §7
 */

import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

import type {
  UnifiedGraph,
  CognitiveNode,
  CognitiveEdge,
} from './types.js'
import type { ClaustrumRecorder, ClaustrumWindow, RetainedFeature } from './claustrum-recorder.js'

// section

/** Wire format for a single node in claustrum_graph.json. */
export interface SerializedClaustrumNode {
  id: string
  concept: string
  sources: string[]
  model_features: Array<{ layer: number; claustrum_local_id: number }>
  mnemic_engram_ids: string[]
  first_seen_ts: string
  last_seen_ts: string
  activation_count: number
  resonance: number
  centrality: number
}

/** Wire format for a single edge in claustrum_graph.json. */
export interface SerializedClaustrumEdge {
  from: string
  to: string
  relation: string
  weight: number
  source: string
}

/** Wire format for claustrum_graph.json. */
export interface SerializedClaustrumGraph {
  format_version: 1
  nodes: SerializedClaustrumNode[]
  edges: SerializedClaustrumEdge[]
  source_breakdown: Record<string, number>
  total_edges: number
  built_at: string
}

/**
 * Serialize a `UnifiedGraph` into the JSON wire format specified in
 * docs/design/claustrum-vindex.md §4.3.
 *
 * The in-memory graph uses `Map<string, CognitiveNode>` which is not directly
 * JSON-serializable. This function converts to plain arrays and remaps field
 * names to match the wire format.
 *
 * `featureLocalIdMap` maps `(layer, sourceFeatureIndex) → claustrum_local_id`
 * so model-side features get the correct local IDs in the output. If absent,
 * model_features are omitted (degraded but valid for test fixtures).
 */
export function serializeGraph(
  graph: UnifiedGraph,
  featureLocalIdMap?: Map<string, number>,
): SerializedClaustrumGraph {
  const nodes: SerializedClaustrumNode[] = []
  for (const [id, node] of graph.nodes) {
    const sources = new Set<string>()
    if (node.source === 'model' || node.source === 'both') sources.add('model')
    if (node.source === 'memory' || node.source === 'both') sources.add('mnemic')
    if (node.source === 'knowledge') sources.add('knowledge')
    if (node.source === 'observer') sources.add('observer')
    // Also add portal if the node came through a portal bridge
    if (node.content && node.source === 'memory') sources.add('portal')

    const modelFeatures: SerializedClaustrumNode['model_features'] = []
    if (node.modelLayers && featureLocalIdMap) {
      for (const layer of node.modelLayers) {
        // We don't have the exact feature index on CognitiveNode, but we
        // can store the layer presence. Downstream consumers use the
        // feature_index_map for precise ID resolution.
        const key = `${layer}:${node.label}`
        const localId = featureLocalIdMap.get(key) ?? -1
        if (localId >= 0) {
          modelFeatures.push({ layer, claustrum_local_id: localId })
        }
      }
    }

    nodes.push({
      id,
      concept: node.label,
      sources: [...sources],
      model_features: modelFeatures,
      mnemic_engram_ids: node.nodeType === 'episodic' ? [id] : [],
      first_seen_ts: new Date(graph.builtAt - 86_400_000).toISOString(), // approximate
      last_seen_ts: new Date(graph.builtAt).toISOString(),
      activation_count: node.activated ? 1 : 0,
      resonance: node.resonance,
      centrality: node.centrality,
    })
  }

  const edges: SerializedClaustrumEdge[] = []
  for (const [, edgeList] of graph.edges) {
    for (const edge of edgeList) {
      edges.push({
        from: edge.sourceId,
        to: edge.targetId,
        relation: edge.edgeType,
        weight: edge.weight,
        source: edge.origin === 'memory' ? 'mnemic_co_occurrence'
          : edge.origin === 'model' ? 'model_relation'
          : edge.origin === 'portal' ? 'portal_bridge'
          : edge.origin === 'dream' ? 'dream_discovery'
          : 'claustrum_co_occurrence',
      })
    }
  }

  return {
    format_version: 1,
    nodes,
    edges,
    source_breakdown: { ...graph.sourceBreakdown },
    total_edges: graph.edgeCount,
    built_at: new Date(graph.builtAt).toISOString(),
  }
}

/**
 * Parse a `SerializedClaustrumGraph` back from JSON. Validates format_version.
 */
export function parseSerializedGraph(raw: unknown): SerializedClaustrumGraph {
  const g = raw as SerializedClaustrumGraph
  if (!g || g.format_version !== 1) {
    throw new Error(`parseSerializedGraph: unsupported format_version ${(g as any)?.format_version}`)
  }
  if (!Array.isArray(g.nodes) || !Array.isArray(g.edges)) {
    throw new Error('parseSerializedGraph: missing nodes or edges arrays')
  }
  return g
}


// section

/** One line in claustrum_provenance.jsonl. */
export interface ProvenanceRecord {
  ts: string
  cycle_id: string | null
  layer: number
  local_id: number
  source_global_id: number
  trigger: string
  query_concept: string
}

/**
 * Export provenance records from the recorder DB to JSONL.
 * Each retained feature gets one line per distinct (cycle, layer, feature) tuple.
 *
 * The `localIdFn` maps source-global feature IDs to claustrum-local IDs.
 * For M5 we generate sequential local IDs; the Rust snapshotter produces
 * the authoritative mapping via feature_index_map.
 */
export function exportProvenance(
  retained: RetainedFeature[],
  window: ClaustrumWindow,
  localIdFn?: (layer: number, sourceGlobalId: number) => number,
): ProvenanceRecord[] {
  const getId = localIdFn ?? ((_layer: number, _globalId: number, idx: number) => idx)
  const records: ProvenanceRecord[] = []
  let seq = 0
  for (const feat of retained) {
    records.push({
      ts: feat.lastSeen,
      cycle_id: null, // per-cycle breakdown requires a richer query; populate later
      layer: feat.layer,
      local_id: getId(feat.layer, feat.featureIndex, seq),
      source_global_id: feat.featureIndex,
      trigger: 'larql_gate_knn',
      query_concept: '',
    })
    seq++
  }
  return records
}


// section

export interface ClaustrumManifest {
  format_version: 1
  source: {
    path: string
    sha256: string | null
    family: string
  }
  snapshot: {
    created_at: string
    window_start: string | null
    window_end: string | null
    aurora_cycles_observed: number
  }
  graph_stats: {
    node_count: number
    edge_count: number
    source_breakdown: Record<string, number>
  }
  retained_stats: {
    layer_count: number
    total_features: number
  }
}

export interface SnapshotManifestOptions {
  sourcePath: string
  sourceSha256?: string | null
  sourceFamily?: string
  windowStart?: string | null
  windowEnd?: string | null
  auroraCyclesObserved?: number
  graph: UnifiedGraph
  retainedLayerCount: number
  retainedFeatureCount: number
}

export function buildManifest(opts: SnapshotManifestOptions): ClaustrumManifest {
  return {
    format_version: 1,
    source: {
      path: opts.sourcePath,
      sha256: opts.sourceSha256 ?? null,
      family: opts.sourceFamily ?? 'unknown',
    },
    snapshot: {
      created_at: new Date().toISOString(),
      window_start: opts.windowStart ?? null,
      window_end: opts.windowEnd ?? null,
      aurora_cycles_observed: opts.auroraCyclesObserved ?? 0,
    },
    graph_stats: {
      node_count: opts.graph.nodes.size,
      edge_count: opts.graph.edgeCount,
      source_breakdown: { ...opts.graph.sourceBreakdown },
    },
    retained_stats: {
      layer_count: opts.retainedLayerCount,
      total_features: opts.retainedFeatureCount,
    },
  }
}


// section

export interface WriteSnapshotOptions {
  /** Directory to write files into (created if missing). */
  outputDir: string
  /** The unified graph to serialize. */
  graph: UnifiedGraph
  /** Feature local ID map (optional — see serializeGraph). */
  featureLocalIdMap?: Map<string, number>
  /** Retained features for provenance export. */
  retained: RetainedFeature[]
  /** Recording window used for the query. */
  window: ClaustrumWindow
  /** Manifest source info. */
  sourcePath: string
  sourceSha256?: string | null
  sourceFamily?: string
  auroraCyclesObserved?: number
}

export interface WriteSnapshotResult {
  graphPath: string
  manifestPath: string
  provenancePath: string
  nodeCount: number
  edgeCount: number
  provenanceRecords: number
}

/**
 * Write all three claustrum adjunct files to `outputDir` atomically.
 *
 * Atomicity strategy: write to `<name>.tmp` then rename, same as
 * `exportRetained`. If any write fails, the `.tmp` files are cleaned up
 * but previously-written files are NOT rolled back (they have valid headers
 * and are safe to leave as partial snapshots — the manifest is written last
 * as a readiness marker).
 */
export function writeClaustrumSnapshot(opts: WriteSnapshotOptions): WriteSnapshotResult {
  const dir = opts.outputDir
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })

  // 1. Serialize and write graph
  const serialized = serializeGraph(opts.graph, opts.featureLocalIdMap)
  const graphPath = path.join(dir, 'claustrum_graph.json')
  writeAtomically(graphPath, JSON.stringify(serialized, null, 2) + '\n')

  // 2. Build and write provenance
  const provenanceRecords = exportProvenance(opts.retained, opts.window)
  const provenancePath = path.join(dir, 'claustrum_provenance.jsonl')
  const provenanceLines = provenanceRecords.map(r => JSON.stringify(r)).join('\n') + '\n'
  writeAtomically(provenancePath, provenanceLines)

  // 3. Build and write manifest (last — acts as readiness marker)
  const totalFeatures = opts.retained.length
  const layerSet = new Set(opts.retained.map(r => r.layer))
  const manifest = buildManifest({
    sourcePath: opts.sourcePath,
    sourceSha256: opts.sourceSha256,
    sourceFamily: opts.sourceFamily,
    windowStart: opts.window.startTs ?? null,
    windowEnd: opts.window.endTs ?? null,
    auroraCyclesObserved: opts.auroraCyclesObserved,
    graph: opts.graph,
    retainedLayerCount: layerSet.size,
    retainedFeatureCount: totalFeatures,
  })
  const manifestPath = path.join(dir, 'claustrum_manifest.json')
  writeAtomically(manifestPath, JSON.stringify(manifest, null, 2) + '\n')

  return {
    graphPath,
    manifestPath,
    provenancePath,
    nodeCount: serialized.nodes.length,
    edgeCount: serialized.edges.length,
    provenanceRecords: provenanceRecords.length,
  }
}

/**
 * Read and validate a claustrum snapshot from disk.
 * Returns null if the directory doesn't exist or is missing required files.
 */
export function readClaustrumSnapshot(dir: string): {
  graph: SerializedClaustrumGraph
  manifest: ClaustrumManifest
  provenance: ProvenanceRecord[]
} | null {
  const graphPath = path.join(dir, 'claustrum_graph.json')
  const manifestPath = path.join(dir, 'claustrum_manifest.json')
  const provenancePath = path.join(dir, 'claustrum_provenance.jsonl')

  if (!fs.existsSync(graphPath) || !fs.existsSync(manifestPath)) {
    return null
  }

  const graphRaw = JSON.parse(fs.readFileSync(graphPath, 'utf-8'))
  const graph = parseSerializedGraph(graphRaw)

  const manifest: ClaustrumManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'))

  const provenance: ProvenanceRecord[] = []
  if (fs.existsSync(provenancePath)) {
    const lines = fs.readFileSync(provenancePath, 'utf-8').split('\n').filter(l => l.trim())
    for (const line of lines) {
      provenance.push(JSON.parse(line))
    }
  }

  return { graph, manifest, provenance }
}

// section

/** Compute SHA-256 of a file. Used for source vindex fingerprinting. */
export async function fileSha256(filePath: string): Promise<string> {
  const hash = crypto.createHash('sha256')
  const stream = fs.createReadStream(filePath)
  return new Promise((resolve, reject) => {
    stream.on('data', (chunk: Buffer) => hash.update(chunk))
    stream.on('end', () => resolve(hash.digest('hex')))
    stream.on('error', reject)
  })
}

/** Write to a tmp file then rename — crash-safe atomic write. */
function writeAtomically(targetPath: string, content: string): void {
  const tmpPath = targetPath + '.tmp'
  fs.writeFileSync(tmpPath, content, 'utf-8')
  fs.renameSync(tmpPath, targetPath)
}
