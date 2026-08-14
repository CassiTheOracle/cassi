/**
 * SDK Tagger — runs the training annotation pipeline through the Copilot SDK
 * tool loop, giving powerful models access to inspect objects and produce
 * higher-quality structured annotations.
 *
 * Instead of a simple system+user → JSON completion, the SDK model:
 * 1. Calls `get_batch` to receive untagged objects with their content
 * 2. Analyzes each object using its full reasoning capability
 * 3. Calls `submit_annotations` with structured annotations for all objects
 *
 * All tool loop iterations count as a single premium request when using the SDK.
 *
 * @dep callers: handleTrainingRoutes (core/admin-api/training.ts)
 * @dep module: Training
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { TrainingObjectType } from './training-types.js'
import { TrainingStore } from './training-store.js'
import { TrainingTagger, type TaggerBatchResult } from './training-tagger.js'
import type { TaggerResponse } from './training-types.js'

// SDK TAGGER TYPES

export interface SdkTaggerOptions {
  /** Objects per batch. Default: 10 */
  batchSize?: number
  /** Object scope. Default: 'message' */
  scope?: 'chunk' | 'message' | 'turn' | 'session'
  /** Minimum content length to tag. Default: 20 */
  minContentLength?: number
  /** Specific object types. Default: inferred from scope */
  objectTypes?: TrainingObjectType[]
}

export interface SdkTaggerResult extends TaggerBatchResult {
  /** Model used for annotation */
  model: string
  /** Provider used */
  provider: string
}

// SDK TAGGER TOOLS — registered in the Copilot SDK session

interface BatchObject {
  object_id: string
  object_type: string
  subtype: string | null
  content: string
}

// WHY: We define a minimal annotation type here instead of reusing TaggerResponse
// because the SDK tool schema needs a flat, self-contained JSON schema that the
// model can fill in without referencing external types.
interface ObjectAnnotation {
  object_id: string
  summary: string
  topics: string[]
  domain: string | null
  entities: string[]
  task_type: string | null
  interaction_pattern: string | null
  difficulty: number
  training_value: string
  privacy_risk: string
  error_taxonomy: string | null
  memory_class: string | null
  suggested_labels: Array<{
    namespace: string
    name: string
    confidence: number
  }>
}

const ANNOTATION_SCHEMA = {
  type: 'object',
  properties: {
    annotations: {
      type: 'array',
      description: 'Annotations for each object in the batch',
      items: {
        type: 'object',
        properties: {
          object_id: { type: 'string', description: 'The object_id from get_batch' },
          summary: { type: 'string', description: '1-2 sentence summary' },
          topics: {
            type: 'array',
            items: { type: 'string' },
            description: 'Lowercase technical topics (e.g., "typescript", "sqlite")',
          },
          domain: {
            type: ['string', 'null'],
            description: 'Semantic domain — use one of: "cassicore-runtime", "provider-management", "tool-execution", "intelligence-modules", "multi-agent-orchestration", "terminal-ui", "training-pipeline", "embedding-pipeline", "session-management", "mcp-gateway", "database-storage", "configuration", "security-auth", "testing", "devops-ci", "code-analysis", "web-development", "general-programming". Or a concise lowercase domain name (NEVER file paths).',
          },
          entities: {
            type: 'array',
            items: { type: 'string' },
            description: 'Specific proper nouns, tool names, and function/class names mentioned. Do NOT include file paths.',
          },
          task_type: {
            type: 'string',
            enum: ['coding', 'debugging', 'explaining', 'refactoring', 'reviewing', 'planning', 'research', 'config', 'testing', 'other', null],
            description: 'Primary task type',
          },
          interaction_pattern: {
            type: 'string',
            enum: ['single_turn', 'multi_turn', 'tool_heavy', 'reasoning', 'delegation', 'error_recovery', null],
            description: 'Conversation pattern',
          },
          difficulty: { type: 'number', description: '0.0 (trivial) to 1.0 (expert-level)' },
          training_value: {
            type: 'string',
            enum: ['high', 'medium', 'low', 'skip'],
            description: 'Training value: high=novel/instructive, low=trivial, skip=noise',
          },
          privacy_risk: {
            type: 'string',
            enum: ['none', 'low', 'medium', 'high'],
            description: 'PII/secrets/credentials risk level',
          },
          error_taxonomy: { type: ['string', 'null'], description: 'Error type if content contains an error' },
          memory_class: {
            type: ['string', 'null'],
            enum: ['episodic', 'semantic', 'procedural', null],
            description: 'Cognitive memory class',
          },
          suggested_labels: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                namespace: { type: 'string' },
                name: { type: 'string' },
                confidence: { type: 'number' },
              },
              required: ['namespace', 'name', 'confidence'],
            },
            description: 'Additional labels. Do NOT use "domain" as namespace — use "topic", "task", "quality", "agent_role", "error_type", etc.',
          },
        },
        required: ['object_id', 'summary', 'topics', 'domain', 'entities', 'difficulty', 'training_value', 'privacy_risk'],
      },
    },
  },
  required: ['annotations'],
}

const SYSTEM_PROMPT = `You are a training data annotator for CassiCore, an AI coding assistant.
Your job is to analyze conversation content and produce high-quality structured metadata for training dataset curation.

## Workflow
1. Call \`get_batch\` to receive a batch of untagged objects with their content
2. Analyze each object carefully — consider the technical domain, complexity, and training value
3. Call \`submit_annotations\` with your annotations for ALL objects in the batch
4. If get_batch returns empty, you are done

## Annotation Guidelines
- **topics**: lowercase, specific technical terms (e.g., "typescript", "sqlite", "error-handling", "embedding")
- **domain**: the broad semantic domain — use one of these preferred values when applicable: "cassicore-runtime", "provider-management", "tool-execution", "intelligence-modules", "multi-agent-orchestration", "terminal-ui", "training-pipeline", "embedding-pipeline", "session-management", "mcp-gateway", "database-storage", "configuration", "security-auth", "testing", "devops-ci", "code-analysis", "web-development", "general-programming". For other domains, use a concise lowercase name (NEVER file paths or code symbols).
- **entities**: specific proper nouns, tool names, and function/class names. Do NOT include file paths — those belong in topics if relevant.
- **training_value**: "high" = novel, complete, instructive content; "low" = boilerplate/trivial; "skip" = noise/system messages
- **difficulty**: 0 = trivial, 0.5 = moderate, 1.0 = expert-level reasoning
- **privacy_risk**: flag PII, secrets, API keys, credentials, personal info
- **memory_class**: "episodic" = specific events/conversations, "semantic" = facts/knowledge, "procedural" = how-to/processes
- **suggested_labels**: add labels that don't fit the fixed fields. Do NOT use "domain" as a namespace — use "topic", "task", "quality", "agent_role", "error_type", etc.

Be precise. Be thorough. Your annotations directly affect training data quality.
Start by calling get_batch.`

// SDK TAGGER CLASS

export class SdkTagger {
  private readonly store: TrainingStore
  private readonly logger: ILogger
  private batchObjects: BatchObject[] = []
  private result: SdkTaggerResult

  constructor(store: TrainingStore, logger: ILogger) {
    this.store = store
    this.logger = logger.child('sdk-tagger')
    this.result = this.freshResult()
  }

  private freshResult(): SdkTaggerResult {
    return {
      processed: 0,
      tagged: 0,
      skipped: 0,
      failed: 0,
      labelsCreated: 0,
      metricsSet: 0,
      totalTokens: 0,
      durationMs: 0,
      errors: [],
      model: '',
      provider: '',
    }
  }

  /**
   * Build SDK tools for the tagger session.
   * Returns tools that the SDK model can call during the tool loop.
   */
  buildTools(opts: SdkTaggerOptions = {}): Array<{
    name: string
    description: string
    parameters: Record<string, unknown>
    handler: (args: unknown) => Promise<{ textResultForLlm: string; resultType: 'success' | 'error' }>
  }> {
    const batchSize = opts.batchSize ?? 10
    const minLen = opts.minContentLength ?? 20
    const scope = opts.scope ?? 'message'
    const objectTypes = opts.objectTypes

    return [
      {
        name: 'get_batch',
        description: `Get a batch of up to ${batchSize} untagged ${scope}-scope objects with their content for annotation. Returns objects with their IDs, types, and text content. Call this first to get work.`,
        parameters: {
          type: 'object',
          properties: {},
        },
        handler: async () => {
          try {
            const objects = this.selectAndExtractBatch(scope, batchSize, minLen, objectTypes)
            this.batchObjects = objects

            if (objects.length === 0) {
              return {
                textResultForLlm: JSON.stringify({ status: 'empty', message: 'No untagged objects remaining. You are done.' }),
                resultType: 'success' as const,
              }
            }

            return {
              textResultForLlm: JSON.stringify({
                status: 'ok',
                count: objects.length,
                objects: objects.map(o => ({
                  object_id: o.object_id,
                  object_type: o.object_type,
                  subtype: o.subtype,
                  content_length: o.content.length,
                  content: o.content.slice(0, 2000), // cap per-object to avoid overwhelming
                })),
              }),
              resultType: 'success' as const,
            }
          } catch (err) {
            this.logger.error('get_batch failed', { error: String(err) })
            return {
              textResultForLlm: JSON.stringify({ status: 'error', message: String(err) }),
              resultType: 'error' as const,
            }
          }
        },
      },
      {
        name: 'submit_annotations',
        description: 'Submit structured annotations for objects from the current batch. Each annotation must reference an object_id from get_batch.',
        parameters: ANNOTATION_SCHEMA,
        handler: async (args: unknown) => {
          try {
            const { annotations } = args as { annotations: ObjectAnnotation[] }
            if (!Array.isArray(annotations)) {
              return {
                textResultForLlm: JSON.stringify({ status: 'error', message: 'annotations must be an array' }),
                resultType: 'error' as const,
              }
            }

            const batchIds = new Set(this.batchObjects.map(o => o.object_id))
            let accepted = 0
            let rejected = 0

            for (const ann of annotations) {
              if (!batchIds.has(ann.object_id)) {
                this.logger.warn('Annotation for unknown object_id', { objectId: ann.object_id })
                rejected++
                continue
              }

              try {
                this.applyAnnotation(ann)
                accepted++
                this.result.tagged++
              } catch (err) {
                this.logger.error('Failed to apply annotation', { objectId: ann.object_id, error: String(err) })
                this.result.failed++
                this.result.errors.push(`${ann.object_id}: ${String(err)}`)
                rejected++
              }
            }

            this.result.processed += this.batchObjects.length

            return {
              textResultForLlm: JSON.stringify({
                status: 'ok',
                accepted,
                rejected,
                total_tagged_so_far: this.result.tagged,
              }),
              resultType: 'success' as const,
            }
          } catch (err) {
            this.logger.error('submit_annotations failed', { error: String(err) })
            return {
              textResultForLlm: JSON.stringify({ status: 'error', message: String(err) }),
              resultType: 'error' as const,
            }
          }
        },
      },
    ]
  }

  /**
   * Get the system prompt for the SDK tagger session.
   */
  getSystemPrompt(): string {
    return SYSTEM_PROMPT
  }

  /**
   * Get the initial user prompt.
   */
  getUserPrompt(opts: SdkTaggerOptions = {}): string {
    return `Annotate a batch of ${opts.batchSize ?? 10} untagged training objects (scope: ${opts.scope ?? 'message'}). Start by calling get_batch, then submit_annotations for each batch. Keep going until get_batch returns empty.`
  }

  /**
   * Get the accumulated result.
   */
  getResult(): SdkTaggerResult {
    return { ...this.result }
  }

  /**
   * Set model/provider info for provenance.
   */
  setProvenance(model: string, provider: string): void {
    this.result.model = model
    this.result.provider = provider
  }

  // INTERNALS

  private static readonly SCOPE_TYPES: Record<string, TrainingObjectType[]> = {
    chunk: ['message', 'reasoning_step', 'event', 'artifact', 'memory', 'insight', 'pattern'],
    message: ['message'],
    turn: ['turn'],
    session: ['session'],
  }

  private selectAndExtractBatch(
    scope: string,
    limit: number,
    minContentLength: number,
    objectTypes?: TrainingObjectType[],
  ): BatchObject[] {
    const types = objectTypes ?? SdkTagger.SCOPE_TYPES[scope]
    const typeFilter = types?.length
      ? `AND o.object_type IN (${types.map(() => '?').join(',')})`
      : ''

    // WHY: Filter at SQL level for objects that have extractable content meeting the
    // minimum length. Without the length check, the over-select may grab only short-
    // content objects (e.g., memory chunks with 5-char text), causing get_batch to
    // return empty even when countUntagged reports hundreds remaining.
    const minLen = minContentLength
    const contentExistsFilter = `
      AND (
        EXISTS (SELECT 1 FROM messages m WHERE m.object_id = o.object_id AND length(m.content_text) >= ${minLen})
        OR EXISTS (SELECT 1 FROM chunks c WHERE c.object_id = o.object_id AND length(c.text) >= ${minLen})
        OR EXISTS (SELECT 1 FROM reasoning_steps rs WHERE rs.object_id = o.object_id AND length(rs.content) >= ${minLen})
        OR EXISTS (SELECT 1 FROM reasoning_traces rt WHERE rt.object_id = o.object_id AND (length(rt.synthesis) >= ${minLen} OR length(rt.decision) >= ${minLen}))
        OR EXISTS (SELECT 1 FROM events e WHERE e.object_id = o.object_id)
      )
    `

    const sql = `
      SELECT o.object_id, o.object_type, o.subtype
      FROM objects o
      WHERE 1=1
        ${typeFilter}
        AND NOT EXISTS (
          SELECT 1 FROM object_labels ol
          WHERE ol.object_id = o.object_id AND ol.source = 'llm'
        )
        ${contentExistsFilter}
      ORDER BY o.created_at DESC
      LIMIT ?
    `

    const params: unknown[] = []
    if (types?.length) params.push(...types)
    params.push(limit * 2)

    const candidates = this.store.db.prepare(sql).all(...params) as Array<{
      object_id: string; object_type: string; subtype: string | null
    }>

    const results: BatchObject[] = []
    for (const candidate of candidates) {
      if (results.length >= limit) break

      const content = this.extractContent(candidate, scope)
      if (!content || content.length < minContentLength) continue

      results.push({
        object_id: candidate.object_id,
        object_type: candidate.object_type,
        subtype: candidate.subtype,
        content,
      })
    }

    return results
  }

  // WHY: Content extraction is type-aware, not scope-aware. Each object type
  // stores content in a different table. We try the type-specific source first,
  // then fall back to chunks, then to any available source.
  private extractContent(
    candidate: { object_id: string; object_type: string },
    _scope: string,
  ): string | null {
    const { object_id, object_type } = candidate

    // Type-specific extraction
    switch (object_type) {
      case 'message': {
        const msg = this.store.db.prepare(
          `SELECT content_text FROM messages WHERE object_id = ? LIMIT 1`,
        ).get(object_id) as { content_text: string } | undefined
        if (msg?.content_text) return msg.content_text
        break
      }
      case 'reasoning_step': {
        const step = this.store.db.prepare(
          `SELECT content FROM reasoning_steps WHERE object_id = ? LIMIT 1`,
        ).get(object_id) as { content: string } | undefined
        if (step?.content) return step.content
        break
      }
      case 'reasoning_trace': {
        const trace = this.store.db.prepare(
          `SELECT synthesis, decision FROM reasoning_traces WHERE object_id = ? LIMIT 1`,
        ).get(object_id) as { synthesis: string | null; decision: string | null } | undefined
        if (trace) {
          const parts = [trace.synthesis, trace.decision].filter(Boolean)
          if (parts.length) return parts.join('\n\n')
        }
        break
      }
      case 'event': {
        const evt = this.store.db.prepare(
          `SELECT event_type, event_subtype, content_json FROM events WHERE object_id = ? LIMIT 1`,
        ).get(object_id) as { event_type: string; event_subtype: string | null; content_json: string | null } | undefined
        if (evt) {
          const header = `[${evt.event_type}${evt.event_subtype ? ':' + evt.event_subtype : ''}]`
          return evt.content_json ? `${header} ${evt.content_json}` : header
        }
        break
      }
      case 'turn': {
        const msgs = this.store.db.prepare(
          `SELECT role, content_text FROM messages WHERE turn_id = ? ORDER BY sequence`,
        ).all(object_id) as Array<{ role: string; content_text: string }>
        if (msgs.length) return msgs.map(m => `[${m.role}] ${m.content_text || ''}`).join('\n\n')
        break
      }
      case 'session': {
        const turns = this.store.db.prepare(`
          SELECT t.sequence, t.role, m.content_text
          FROM turns t LEFT JOIN messages m ON m.turn_id = t.object_id
          WHERE t.session_id = ? ORDER BY t.sequence, m.sequence
        `).all(object_id) as Array<{ sequence: number; role: string; content_text: string }>
        if (turns.length) return turns.map(t => `[Turn ${t.sequence} - ${t.role}] ${t.content_text || ''}`).join('\n\n')
        break
      }
      // memory, insight, pattern, artifact — no dedicated text column
    }

    // Fallback: try chunks (works for memory, insight, and any object with chunked content)
    const chunks = this.store.db.prepare(
      `SELECT text FROM chunks WHERE object_id = ? ORDER BY sequence`,
    ).all(object_id) as Array<{ text: string }>
    if (chunks.length) return chunks.map(c => c.text).join('\n\n')

    return null
  }

  private applyAnnotation(ann: ObjectAnnotation): void {
    const runId = TrainingStore.genId('ar')

    // Record annotation run
    this.store.insertAnnotationRun({
      run_id: runId,
      model: this.result.model,
      provider: this.result.provider,
      prompt_version: 'sdk-v1.0.0',
      input_hash: null,
      target_object_id: ann.object_id,
      target_scope: 'batch',
      tokens_used: null,
      cost_estimate: null,
      status: 'completed',
      response_json: JSON.stringify(ann),
      started_at: Date.now(),
      completed_at: Date.now(),
    })

    // Apply in a transaction
    this.store.transaction(() => {
      // Topics → labels
      for (const topic of (ann.topics || [])) {
        const labelId = this.store.ensureLabel('topic', topic)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.85, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Domain → label (semantic domain, not file paths)
      if (ann.domain) {
        const labelId = this.store.ensureLabel('domain', ann.domain)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.9, source: 'llm', runId, isPrimary: true,
        })
        this.result.labelsCreated++
      }

      // Entities → entity namespace (proper nouns, tool names, symbols)
      for (const entity of (ann.entities || [])) {
        const labelId = this.store.ensureLabel('entity', entity)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.75, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Task type
      if (ann.task_type) {
        const labelId = this.store.ensureLabel('task', ann.task_type)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.9, source: 'llm', runId, isPrimary: true,
        })
        this.result.labelsCreated++
      }

      // Interaction pattern
      if (ann.interaction_pattern) {
        const labelId = this.store.ensureLabel('interaction_pattern', ann.interaction_pattern)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.85, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Training value
      if (ann.training_value) {
        const labelId = this.store.ensureLabel('training_value', ann.training_value)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.9, source: 'llm', runId, isPrimary: true,
        })
        this.result.labelsCreated++
      }

      // Memory class
      if (ann.memory_class) {
        const labelId = this.store.ensureLabel('memory_class', ann.memory_class)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.8, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Error taxonomy
      if (ann.error_taxonomy) {
        const labelId = this.store.ensureLabel('error_type', ann.error_taxonomy)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: 0.8, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Suggested labels
      for (const sl of (ann.suggested_labels || [])) {
        const labelId = this.store.ensureLabel(sl.namespace, sl.name)
        this.store.attachLabel(ann.object_id, labelId, {
          confidence: sl.confidence * 0.7, source: 'llm', runId,
        })
        this.result.labelsCreated++
      }

      // Quality metrics
      const difficulty = typeof ann.difficulty === 'number' ? Math.max(0, Math.min(1, ann.difficulty)) : 0.5
      this.store.setQualityMetric({
        object_id: ann.object_id, metric: 'difficulty', value: difficulty,
        source: 'llm', annotation_run_id: runId, updated_at: Date.now(),
      })
      this.result.metricsSet++

      const trainability = ann.training_value === 'high' ? 0.9
        : ann.training_value === 'medium' ? 0.6
        : ann.training_value === 'low' ? 0.3 : 0.0
      this.store.setQualityMetric({
        object_id: ann.object_id, metric: 'trainability', value: trainability,
        source: 'llm', annotation_run_id: runId, updated_at: Date.now(),
      })
      this.result.metricsSet++

      const privacyScore = ann.privacy_risk === 'high' ? 1.0
        : ann.privacy_risk === 'medium' ? 0.6
        : ann.privacy_risk === 'low' ? 0.3 : 0.0
      this.store.setQualityMetric({
        object_id: ann.object_id, metric: 'privacy_risk', value: privacyScore,
        source: 'llm', annotation_run_id: runId, updated_at: Date.now(),
      })
      this.result.metricsSet++
    })
  }
}
