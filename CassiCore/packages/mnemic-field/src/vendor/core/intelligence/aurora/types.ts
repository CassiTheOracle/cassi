/**
 * TYPE STUB — Aurora types (core/intelligence/aurora/types.ts).
 *
 * Faithful type surface for the symbols mnemic-field consumes:
 * `ModelKnowledgeProvider`, `ModelEntity`, `ModelEdge`, `ModelPath` (from
 * knowledge/knowledge-field) and `CycleIdAware` (from the larql-provider stub).
 * Re-point to the owning package at P5 via the repoint log.
 */

/** Marker interface for providers that support Aurora cycle-id provenance. */
export interface CycleIdAware {
  setCycleId(cycleId: string | null): void
}

/** Provider interface for model knowledge — abstracts LARQL. */
export interface ModelKnowledgeProvider {
  /** Get all known relations for an entity. */
  describe(entity: string): ModelEntity | null
  /** Get the subgraph around an entity. */
  subgraph(entity: string, radius: number): ModelEdge[]
  /** Find the shortest path between two entities. */
  shortestPath(from: string, to: string): ModelPath | null
  /** Check if an entity exists in the model's knowledge. */
  exists(entity: string): boolean
  /** Search for entities by keyword. */
  search(query: string, limit: number): ModelEntity[]
}

/** An entity from the model's knowledge graph. */
export interface ModelEntity {
  /** Entity name. */
  name: string
  /** All outgoing relations. */
  relations: ModelRelation[]
  /** Total relation count. */
  totalRelations: number
  /** Optional overlay attribution map. */
  overlayAttribution?: Map<string, string>
}

/** A relation from the model's knowledge graph. */
export interface ModelRelation {
  /** Relation type (e.g. "capital", "located_in"). */
  relation: string
  /** Target entity. */
  target: string
  /** Confidence score (gate score magnitude). */
  confidence: number
  /** Source of the label (Probe, Cluster, etc.). */
  labelSource?: string
  /** Layer range where this relation appears. */
  layerMin: number
  layerMax: number
}

/** An edge from the model's knowledge graph. */
export interface ModelEdge {
  /** Subject entity. */
  subject: string
  /** Relation type. */
  relation: string
  /** Object entity. */
  object: string
  /** Confidence. */
  confidence: number
  /** Layer range. */
  layerMin: number
  layerMax: number
}

/** A path through the model's knowledge graph. */
export interface ModelPath {
  /** Entity names along the path. */
  entities: string[]
  /** Relations along the path. */
  relations: string[]
  /** Total length. */
  length: number
}
