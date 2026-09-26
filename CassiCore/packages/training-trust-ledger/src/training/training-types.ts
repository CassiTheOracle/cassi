/**
 * Training Warehouse Types — All exported types and interfaces for the
 * training-oriented data warehouse (training.db).
 *
 * Design goals:
 * - Every piece of data is an addressable "object" with a stable ref key
 * - Taxonomy labels are controlled vocabularies, not free-form strings
 * - Every label has provenance (heuristic / llm / human) and confidence
 * - Chunks are the atomic search/training unit; everything else aggregates
 * - Quality metrics live in a tall table so new dimensions are additive
 * - Privacy spans mark sensitive regions without deleting raw data
 *
 * Built to later absorb memory.db, lumen.db, and dyad.db once parity is proven.
 */

// OBJECT MODEL

/** Top-level object types stored in the warehouse. */
export type TrainingObjectType =
  | 'session'
  | 'turn'
  | 'message'
  | 'chunk'
  | 'tool_call'
  | 'reasoning_trace'
  | 'reasoning_step'
  | 'event'
  | 'artifact'
  | 'memory'
  | 'insight'
  | 'pattern'
  | 'dream';

/** Subtypes refine object_type within certain categories. */
export type TrainingObjectSubtype =
  // session subtypes
  | 'interactive' | 'batch' | 'delegation' | 'subagent' | 'lumen' | 'dyad' | 'flux_team'
  // message subtypes
  | 'user' | 'assistant' | 'system' | 'tool_result'
  // chunk subtypes
  | 'paragraph' | 'code_block' | 'heading' | 'list_item' | 'tool_input' | 'tool_output'
  | 'reasoning_content' | 'artifact_excerpt' | 'error_message'
  // reasoning subtypes
  | 'dialectic' | 'chain_of_thought' | 'tree_of_thought' | 'reflection'
  // reasoning step subtypes
  | 'yang' | 'yin' | 'executive' | 'serenity' | 'synthesis' | 'decision'
  // event subtypes
  | 'lifecycle' | 'error' | 'metric' | 'observation'
  // artifact subtypes
  | 'file' | 'diff' | 'report' | 'blackboard_snapshot'
  | string; // extensible

/** The core object record in the warehouse. */
export interface TrainingObject {
  object_id: string;
  object_type: TrainingObjectType;
  subtype: TrainingObjectSubtype | null;
  parent_object_id: string | null;
  root_session_id: string | null;
  ref_key: string;
  source_db: string | null;        // 'memory' | 'archive' | 'lumen' | 'dyad' | 'session_index' | 'event_bus'
  source_id: string | null;        // original ID in source DB
  created_at: number;               // unix ms
  ingested_at: number;              // unix ms
  raw_json: string | null;          // full original blob for fidelity
}

// SESSIONS

export interface TrainingSession {
  object_id: string;
  session_type: string;             // interactive | batch | delegation | subagent | lumen | dyad
  channel: string | null;           // opencode | mcp | api | tui
  parent_session_id: string | null;
  started_at: number;
  ended_at: number | null;
  status: string;                   // active | completed | failed | timeout
  turn_count: number;
  total_tokens: number;
  model_primary: string | null;
  provider_primary: string | null;
}

// TURNS

export interface TrainingTurn {
  object_id: string;
  session_id: string;
  sequence: number;
  role: string;                     // user | assistant | system
  subrole: string | null;           // proposer | critic | executor | yang | yin | executive
  branch_id: string | null;
  prev_turn_id: string | null;
  next_turn_id: string | null;
  parent_turn_id: string | null;
  has_tool_calls: number;           // 0 | 1
  has_reasoning: number;            // 0 | 1
  has_error: number;                // 0 | 1
  is_recovery: number;             // 0 | 1
  outcome: string | null;           // success | partial | failure | null
  token_count_in: number | null;
  token_count_out: number | null;
  latency_ms: number | null;
  started_at: number;
  ended_at: number | null;
}

// MESSAGES

export interface TrainingMessage {
  object_id: string;
  turn_id: string;
  sequence: number;                 // order within the turn
  role: string;
  content_type: string;             // text | tool_use | tool_result | image | thinking
  content_text: string | null;      // extracted text for search (null for binary)
  content_json: string | null;      // structured content if applicable
  producer_model: string | null;
  producer_provider: string | null;
  token_count: number | null;
  is_error: number;                 // 0 | 1
  error_class: string | null;
}

// SEARCH CHUNKS — the atomic training/retrieval unit

export interface TrainingChunk {
  chunk_id: string;
  object_id: string;                // parent object (message, reasoning_step, artifact, etc.)
  chunk_type: string;               // paragraph | code_block | tool_input | tool_output | reasoning_content | error_message
  chunk_ref: string;                // human-readable ref e.g. S12#T04.M00.C03
  sequence: number;                 // order within parent
  text: string;
  token_estimate: number;
  language: string | null;          // for code blocks
  role: string | null;              // inherited from message
  session_id: string | null;
}

// TOOL CALLS

export interface TrainingToolCall {
  object_id: string;
  turn_id: string;
  message_id: string | null;
  tool_name: string;
  tool_use_id: string | null;
  input_json: string | null;
  output_json: string | null;
  status: string;                   // success | error | timeout
  error_class: string | null;
  duration_ms: number | null;
  sequence: number;
}

// REASONING

export interface TrainingReasoningTrace {
  object_id: string;
  turn_id: string;
  reasoning_type: string;           // dialectic | chain_of_thought | tree_of_thought | reflection
  depth: string | null;             // ponder | think | deep
  synthesis: string | null;
  decision: string | null;
  overall_confidence: number | null;
  step_count: number;
}

export interface TrainingReasoningStep {
  object_id: string;
  trace_id: string;
  step_type: string;                // yang | yin | executive | serenity | synthesis | decision | step
  sequence: number;
  content: string;
  confidence: number | null;
  tokens_used: number | null;
}

// EVENTS & ARTIFACTS

export interface TrainingEvent {
  object_id: string;
  session_id: string | null;
  event_type: string;
  event_subtype: string | null;
  content_json: string | null;
  severity: string | null;          // info | warn | error | critical
  timestamp: number;
}

export interface TrainingArtifact {
  object_id: string;
  session_id: string | null;
  artifact_type: string;            // file | diff | report | blackboard_snapshot
  name: string | null;
  content_text: string | null;
  content_json: string | null;
  mime_type: string | null;
  byte_size: number | null;
}

// EDGES — graph relations between objects

export type EdgeRelation =
  | 'parent'
  | 'next'
  | 'prev'
  | 'tool_of'
  | 'result_of'
  | 'delegates_to'
  | 'references'
  | 'derived_from'
  | 'similar'
  | 'corrects'
  | 'continues'
  | 'branches_from';

export interface ObjectEdge {
  source_id: string;
  target_id: string;
  relation: EdgeRelation;
  weight: number;                   // 0-1 strength/confidence
  metadata_json: string | null;
}

// TAXONOMY & LABELING

/** Controlled vocabulary namespaces. */
export type TaxonomyNamespace =
  | 'topic'
  | 'task'
  | 'domain'
  | 'entity'
  | 'interaction_pattern'
  | 'tool'
  | 'error_type'
  | 'quality'
  | 'privacy'
  | 'memory_class'
  | 'training_value'
  | string; // extensible

/** Where the label came from. */
export type LabelSource = 'heuristic' | 'llm' | 'human' | 'imported';

export interface TaxonomyLabel {
  label_id: string;
  namespace: TaxonomyNamespace;
  name: string;
  display_name: string | null;
  description: string | null;
  parent_label_id: string | null;   // hierarchical labels
}

export interface ObjectLabel {
  object_id: string;
  label_id: string;
  confidence: number;               // 0-1
  source: LabelSource;
  annotation_run_id: string | null;
  is_primary: number;               // 0 | 1
  created_at: number;
}

// ANNOTATION RUNS — provenance for LLM tagging

export interface AnnotationRun {
  run_id: string;
  model: string;
  provider: string | null;
  prompt_version: string;
  input_hash: string | null;
  target_object_id: string | null;
  target_scope: string;             // chunk | message | turn | session | batch
  tokens_used: number | null;
  cost_estimate: number | null;
  status: string;                   // pending | running | completed | failed
  response_json: string | null;     // raw LLM output
  started_at: number;
  completed_at: number | null;
}

export interface AnnotationEvidence {
  evidence_id: string;
  run_id: string;
  label_id: string;
  chunk_id: string | null;
  object_id: string;
  score: number;                    // 0-1
  explanation: string | null;
}

// QUALITY METRICS — tall table, one row per (object, metric)

export type QualityMetricName =
  | 'trainability'
  | 'completeness'
  | 'novelty'
  | 'groundedness'
  | 'tool_success'
  | 'human_reviewed'
  | 'privacy_risk'
  | 'difficulty'
  | 'coherence'
  | 'informativeness'
  | string; // extensible

export interface QualityMetric {
  object_id: string;
  metric: QualityMetricName;
  value: number;                    // 0-1
  source: LabelSource;
  annotation_run_id: string | null;
  updated_at: number;
}

// PRIVACY SPANS

export interface PrivacySpan {
  span_id: string;
  chunk_id: string;
  start_offset: number;
  end_offset: number;
  category: string;                 // pii_name | pii_email | secret | api_key | path | ip_address
  severity: string;                 // low | medium | high | critical
  redacted: number;                 // 0 | 1
  replacement: string | null;       // e.g. "[REDACTED_EMAIL]"
}

// MODELS REGISTRY

export interface ModelRecord {
  model_id: string;
  provider: string;
  model_name: string;
  version: string | null;
  fingerprint: string | null;
  role: string;                     // producer | annotator | embedder
  first_seen_at: number;
}

// EMBEDDINGS

export interface ObjectEmbedding {
  object_id: string;
  model_id: string;
  vector_json: string;              // JSON-encoded float array
  dimensions: number;
  created_at: number;
}

// EXPORT / ASSEMBLY

/** A fully assembled training example ready for JSONL export. */
export interface TrainingExample {
  id: string;
  session_id: string;
  turns: AssembledTurn[];
  labels: Record<string, string[]>;
  quality: Record<string, number>;
  metadata: Record<string, unknown>;
}

export interface AssembledTurn {
  role: string;
  content: string;
  tool_calls?: Array<{ name: string; input: unknown; output: unknown; status: string }>;
  reasoning?: { type: string; steps: Array<{ role: string; content: string; confidence: number }> };
}

// INGEST BOOKKEEPING

export interface IngestCheckpoint {
  source_db: string;
  source_table: string;
  last_processed_id: string | null;
  last_processed_ts: number | null;
  rows_ingested: number;
  updated_at: number;
}

// WAREHOUSE STATS

export interface TrainingWarehouseStats {
  total_objects: number;
  by_type: Record<string, number>;
  total_chunks: number;
  total_labels: number;
  total_edges: number;
  total_annotation_runs: number;
  total_embeddings: number;
  total_privacy_spans: number;
  schema_version: string;
  db_size_bytes: number;
}

/** Tagger request for LLM annotation. */
export interface TaggerRequest {
  object_id: string;
  scope: 'chunk' | 'message' | 'turn' | 'session';
  content: string;
  context?: string;
  object_type: TrainingObjectType;
  subtype?: string | null;
}

/** Structured tagger response from LLM. */
export interface TaggerResponse {
  summary: string;
  topics: string[];
  domain: string | null;              // semantic domain (e.g., "cassicore-runtime", "provider-management")
  entities: string[];
  task_type: string | null;
  interaction_pattern: string | null;
  difficulty: number;               // 0-1
  training_value: string;           // high | medium | low | skip
  privacy_risk: string;             // none | low | medium | high
  error_taxonomy: string | null;
  memory_class: string | null;      // episodic | semantic | procedural
  suggested_labels: Array<{
    namespace: string;
    name: string;
    confidence: number;
  }>;
}
