/**
 * Training Tagger — LLM-powered annotation pipeline for the training warehouse.
 *
 * Three-stage approach:
 * 1. Select untagged objects at a given scope (chunk, message, turn, session)
 * 2. Build a prompt with content + context, call an LLM for structured tagging
 * 3. Normalize the LLM response into controlled taxonomy labels,
 *    quality metrics, and privacy spans
 *
 * All runs are recorded in annotation_runs for full provenance.
 * Unknown labels go into a review queue (inserted with low confidence)
 * rather than polluting the taxonomy.
 */

import * as crypto from 'node:crypto'
import type { ILogger } from '@cassicore/foundation'
import type { GlobalBlackboardRegistry } from '@cassicore/flux-team'
import { TrainingStore } from './training-store.js'
import type {
  TaggerRequest,
  TaggerResponse,
  AnnotationRun,
  AnnotationEvidence,
  TrainingObjectType,
} from './training-types.js'

// LLM INTERFACE — abstract so callers can plug in any provider

export interface TaggerLLM {
  /** Model identifier for provenance. */
  model: string
  /** Provider identifier for provenance. */
  provider: string
  /** Call the LLM with a system+user prompt, expect JSON response. */
  complete(system: string, user: string): Promise<{ text: string; tokensUsed: number }>
}

// PROMPT TEMPLATES

const PROMPT_VERSION = 'v1.1.0'

const TAGGER_SYSTEM_PROMPT = `You are a training data annotator for an AI coding assistant's conversation corpus.
Your job is to analyze each piece of content and produce structured metadata for training dataset curation.

Respond ONLY with valid JSON matching this schema:
{
  "summary": "1-2 sentence summary of what this content is about",
  "topics": ["topic1", "topic2"],
  "domain": "semantic-domain-name",
  "entities": ["entity1", "entity2"],
  "task_type": "coding|debugging|explaining|refactoring|reviewing|planning|research|config|testing|other|null",
  "interaction_pattern": "single_turn|multi_turn|tool_heavy|reasoning|delegation|error_recovery|null",
  "difficulty": 0.0-1.0,
  "training_value": "high|medium|low|skip",
  "privacy_risk": "none|low|medium|high",
  "error_taxonomy": "null or specific error type if content contains an error",
  "memory_class": "episodic|semantic|procedural|null",
  "suggested_labels": [
    {"namespace": "topic|task|quality", "name": "label_name", "confidence": 0.0-1.0}
  ]
}

Guidelines:
- topics: lowercase, specific technical terms (e.g., "typescript", "sqlite", "error-handling")
- domain: the broad semantic domain — use one of these when applicable: "cassicore-runtime", "provider-management", "tool-execution", "intelligence-modules", "multi-agent-orchestration", "terminal-ui", "training-pipeline", "embedding-pipeline", "session-management", "mcp-gateway", "database-storage", "configuration", "security-auth", "testing", "devops-ci", "code-analysis", "web-development", "general-programming". For other domains, use a concise lowercase name (NEVER file paths or code symbols).
- entities: specific proper nouns, tool names, and function/class names mentioned. Do NOT include file paths — those belong in topics if relevant.
- training_value: "high" = novel, complete, instructive; "low" = boilerplate, trivial; "skip" = noise
- difficulty: 0 = trivial, 0.5 = moderate, 1.0 = expert-level reasoning
- privacy_risk: flag PII, secrets, API keys, credentials, personal info
- memory_class: "episodic" = specific events/conversations, "semantic" = facts/knowledge, "procedural" = how-to/processes
- suggested_labels: add labels that don't fit the fixed fields. Do NOT use "domain" as a namespace — use "topic", "task", "quality", "agent_role", "error_type", etc.`

function buildTaggerUserPrompt(req: TaggerRequest): string {
  const lines = [
    `## Content to Annotate`,
    `**Object Type:** ${req.object_type}${req.subtype ? ` (${req.subtype})` : ''}`,
    `**Scope:** ${req.scope}`,
    `**Object ID:** ${req.object_id}`,
    '',
  ]

  if (req.context) {
    lines.push(`## Context`, req.context, '')
  }

  lines.push(`## Content`, '```', req.content, '```')

  return lines.join('\n')
}

// TAGGER CLASS

export interface TaggerOptions {
  /** Max items per batch. Default: 50 */
  batchSize?: number
  /** Minimum content length to bother tagging. Default: 20 chars */
  minContentLength?: number
  /** Skip objects that already have LLM-sourced labels. Default: true */
  skipAlreadyTagged?: boolean
  /** Specific object types to tag. Default: all */
  objectTypes?: TrainingObjectType[]
  /** Dry run: build prompts but don't call LLM. Default: false */
  dryRun?: boolean
}

export interface TaggerBatchResult {
  processed: number
  tagged: number
  skipped: number
  failed: number
  labelsCreated: number
  metricsSet: number
  totalTokens: number
  durationMs: number
  errors: string[]
}

export class TrainingTagger {
  private readonly store: TrainingStore
  private readonly logger: ILogger
  private globalBlackboardRegistry?: GlobalBlackboardRegistry

  constructor(store: TrainingStore, logger: ILogger) {
    this.store = store
    this.logger = logger.child('training-tagger')
  }

  setGlobalBlackboardRegistry(registry: GlobalBlackboardRegistry): void {
    this.globalBlackboardRegistry = registry
  }

  /**
   * Post an entry to a named global board. Fire-and-forget — never throws.
   */
  private postToBoard(
    boardName: string,
    channel: 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests' | 'bugs',
    content: string,
    opts?: { author?: string; tags?: string[]; priority?: number },
  ): void {
    try {
      const board = this.globalBlackboardRegistry?.getOrCreate(boardName, { persist: true })
      board?.post(channel, {
        content,
        author: opts?.author ?? 'training-tagger',
        tags: opts?.tags ?? [],
        priority: opts?.priority ?? 0,
      })
    } catch (err) {
      this.logger.debug('Blackboard post failed (non-fatal)', { error: String(err), boardName, channel })
    }
  }

  // TAG BATCH — main entry point

  /**
   * Tag a batch of untagged objects at a given scope.
   * Returns results including counts and any errors.
   */
  async tagBatch(
    llm: TaggerLLM,
    scope: 'chunk' | 'message' | 'turn' | 'session',
    opts: TaggerOptions = {},
  ): Promise<TaggerBatchResult> {
    const start = Date.now()
    const batchSize = opts.batchSize ?? 50
    const minLen = opts.minContentLength ?? 20
    const skipTagged = opts.skipAlreadyTagged ?? true

    const result: TaggerBatchResult = {
      processed: 0, tagged: 0, skipped: 0, failed: 0,
      labelsCreated: 0, metricsSet: 0, totalTokens: 0,
      durationMs: 0, errors: [],
    }

    // Select candidates
    const candidates = this.selectCandidates(scope, batchSize, skipTagged, opts.objectTypes)

    for (const candidate of candidates) {
      result.processed++

      // Build content from the object
      const content = this.extractContent(candidate, scope)
      if (!content || content.length < minLen) {
        result.skipped++
        continue
      }

      if (opts.dryRun) {
        result.skipped++
        continue
      }

      // Create annotation run
      const runId = TrainingStore.genId('ar')
      const inputHash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 16)

      const run: AnnotationRun = {
        run_id: runId,
        model: llm.model,
        provider: llm.provider,
        prompt_version: PROMPT_VERSION,
        input_hash: inputHash,
        target_object_id: candidate.object_id,
        target_scope: scope,
        tokens_used: null,
        cost_estimate: null,
        status: 'running',
        response_json: null,
        started_at: Date.now(),
        completed_at: null,
      }
      this.store.insertAnnotationRun(run)

      try {
        // Build request
        const req: TaggerRequest = {
          object_id: candidate.object_id,
          scope,
          content,
          object_type: candidate.object_type as TrainingObjectType,
          subtype: candidate.subtype,
        }

        // Call LLM
        const userPrompt = buildTaggerUserPrompt(req)
        const { text: responseText, tokensUsed } = await llm.complete(TAGGER_SYSTEM_PROMPT, userPrompt)
        result.totalTokens += tokensUsed

        // Parse response
        const response = this.parseResponse(responseText)
        if (!response) {
          this.store.failAnnotationRun(runId, 'Failed to parse LLM response')
          result.failed++
          continue
        }

        // Store raw response
        this.store.completeAnnotationRun(runId, JSON.stringify(response), tokensUsed)

        // Normalize into labels and metrics
        this.store.transaction(() => {
          this.applyResponse(candidate.object_id, response, runId, result)
        })

        result.tagged++
      } catch (err) {
        this.store.failAnnotationRun(runId, String(err))
        result.failed++
        result.errors.push(`${candidate.object_id}: ${String(err)}`)
      }
    }

    result.durationMs = Date.now() - start
    this.logger.info('Tagger batch complete', {
      scope,
      processed: result.processed,
      tagged: result.tagged,
      failed: result.failed,
      tokens: result.totalTokens,
    })
    return result
  }

  // TAG SINGLE OBJECT

  /**
   * Tag a single specific object. Useful for on-demand annotation.
   */
  async tagObject(
    llm: TaggerLLM,
    objectId: string,
    scope: 'chunk' | 'message' | 'turn' | 'session',
  ): Promise<TaggerResponse | null> {
    const obj = this.store.getObject(objectId)
    if (!obj) {
      this.logger.warn('Object not found for tagging', { objectId })
      return null
    }

    const content = this.extractContent(obj as any, scope)
    if (!content) return null

    const runId = TrainingStore.genId('ar')
    const inputHash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 16)

    this.store.insertAnnotationRun({
      run_id: runId,
      model: llm.model,
      provider: llm.provider,
      prompt_version: PROMPT_VERSION,
      input_hash: inputHash,
      target_object_id: objectId,
      target_scope: scope,
      tokens_used: null,
      cost_estimate: null,
      status: 'running',
      response_json: null,
      started_at: Date.now(),
      completed_at: null,
    })

    try {
      const req: TaggerRequest = {
        object_id: objectId,
        scope,
        content,
        object_type: obj.object_type as unknown as TrainingObjectType,
        subtype: obj.subtype,
      }

      const userPrompt = buildTaggerUserPrompt(req)
      const { text: responseText, tokensUsed } = await llm.complete(TAGGER_SYSTEM_PROMPT, userPrompt)

      const response = this.parseResponse(responseText)
      if (!response) {
        this.store.failAnnotationRun(runId, 'Failed to parse LLM response')
        return null
      }

      this.store.completeAnnotationRun(runId, JSON.stringify(response), tokensUsed)

      const dummyResult: TaggerBatchResult = {
        processed: 0, tagged: 0, skipped: 0, failed: 0,
        labelsCreated: 0, metricsSet: 0, totalTokens: 0,
        durationMs: 0, errors: [],
      }

      this.store.transaction(() => {
        this.applyResponse(objectId, response, runId, dummyResult)
      })

      return response
    } catch (err) {
      this.store.failAnnotationRun(runId, String(err))
      this.logger.error('Single-object tagging failed', { objectId, error: String(err) })
      return null
    }
  }

  // INTERNALS

  // WHY: When no explicit objectTypes are provided, we infer valid types from the
  // scope so that extractContent can actually find content for the selected candidates.
  // Without this, a scope='message' request could select reasoning_step objects that
  // have no rows in the messages table, causing all candidates to be skipped.
  private static readonly SCOPE_DEFAULT_TYPES: Record<string, TrainingObjectType[]> = {
    chunk: ['message', 'reasoning_step', 'event', 'artifact', 'memory', 'insight', 'pattern'],
    message: ['message'],
    turn: ['turn'],
    session: ['session'],
  }

  private selectCandidates(
    scope: string,
    limit: number,
    skipTagged: boolean,
    objectTypes?: TrainingObjectType[],
  ): Array<{ object_id: string; object_type: string; subtype: string | null }> {
    const types = objectTypes?.length
      ? objectTypes
      : TrainingTagger.SCOPE_DEFAULT_TYPES[scope]

    const typeFilter = types?.length
      ? `AND o.object_type IN (${types.map(() => '?').join(',')})`
      : ''

    const skipFilter = skipTagged
      ? `AND NOT EXISTS (
            SELECT 1 FROM object_labels ol
            WHERE ol.object_id = o.object_id AND ol.source = 'llm'
          )`
      : ''

    const sql = `
      SELECT o.object_id, o.object_type, o.subtype
      FROM objects o
      WHERE 1=1
        ${typeFilter}
        ${skipFilter}
      ORDER BY o.created_at DESC
      LIMIT ?
    `

    const params: unknown[] = []
    if (types?.length) params.push(...types)
    params.push(limit)

    return this.store.db.prepare(sql).all(...params) as any[]
  }

  private extractContent(
    candidate: { object_id: string; object_type: string },
    scope: string,
  ): string | null {
    // For chunks, read directly from chunks table
    if (scope === 'chunk') {
      const chunk = this.store.db.prepare(`
        SELECT text FROM chunks WHERE object_id = ? OR chunk_id = ? LIMIT 1
      `).get(candidate.object_id, candidate.object_id) as { text: string } | undefined
      return chunk?.text || null
    }

    // For messages, read content_text
    if (scope === 'message') {
      const msg = this.store.db.prepare(`
        SELECT content_text FROM messages WHERE object_id = ? LIMIT 1
      `).get(candidate.object_id) as { content_text: string } | undefined
      return msg?.content_text || null
    }

    // For turns, concatenate all message content
    if (scope === 'turn') {
      const msgs = this.store.db.prepare(`
        SELECT role, content_text FROM messages WHERE turn_id = ? ORDER BY sequence
      `).all(candidate.object_id) as Array<{ role: string; content_text: string }>
      if (!msgs.length) return null
      return msgs.map(m => `[${m.role}] ${m.content_text || ''}`).join('\n\n')
    }

    // For sessions, concatenate all turns
    if (scope === 'session') {
      const turns = this.store.db.prepare(`
        SELECT t.sequence, t.role, m.content_text
        FROM turns t
        LEFT JOIN messages m ON m.turn_id = t.object_id
        WHERE t.session_id = ?
        ORDER BY t.sequence, m.sequence
      `).all(candidate.object_id) as Array<{ sequence: number; role: string; content_text: string }>
      if (!turns.length) return null
      return turns.map(t => `[Turn ${t.sequence} - ${t.role}] ${t.content_text || ''}`).join('\n\n')
    }

    // Fallback: try chunks
    const chunks = this.store.db.prepare(`
      SELECT text FROM chunks WHERE object_id = ? ORDER BY sequence
    `).all(candidate.object_id) as Array<{ text: string }>
    if (chunks.length) return chunks.map(c => c.text).join('\n\n')

    return null
  }

  private parseResponse(text: string): TaggerResponse | null {
    try {
      // Strip markdown code fences if present
      let cleaned = text.trim()
      if (cleaned.startsWith('```')) {
        cleaned = cleaned.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '')
      }

      const parsed = JSON.parse(cleaned)

      // Validate required fields with defaults
      return {
        summary: parsed.summary || '',
        topics: Array.isArray(parsed.topics) ? parsed.topics : [],
        domain: typeof parsed.domain === 'string' ? parsed.domain : null,
        entities: Array.isArray(parsed.entities) ? parsed.entities : [],
        task_type: parsed.task_type || null,
        interaction_pattern: parsed.interaction_pattern || null,
        difficulty: typeof parsed.difficulty === 'number' ? Math.max(0, Math.min(1, parsed.difficulty)) : 0.5,
        training_value: ['high', 'medium', 'low', 'skip'].includes(parsed.training_value) ? parsed.training_value : 'medium',
        privacy_risk: ['none', 'low', 'medium', 'high'].includes(parsed.privacy_risk) ? parsed.privacy_risk : 'none',
        error_taxonomy: parsed.error_taxonomy || null,
        memory_class: ['episodic', 'semantic', 'procedural'].includes(parsed.memory_class) ? parsed.memory_class : null,
        suggested_labels: Array.isArray(parsed.suggested_labels) ? parsed.suggested_labels : [],
      }
    } catch {
      return null
    }
  }

  private applyResponse(
    objectId: string,
    response: TaggerResponse,
    runId: string,
    result: TaggerBatchResult,
  ): void {
    // Topics → labels
    for (const topic of response.topics) {
      const labelId = this.store.ensureLabel('topic', topic)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.85,
        source: 'llm',
        runId,
      })
      this.insertEvidence(runId, labelId, objectId, 0.85, `Topic: ${topic}`)
      result.labelsCreated++
    }

    // Domain → label (semantic domain, not file paths)
    if (response.domain) {
      const labelId = this.store.ensureLabel('domain', response.domain)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.9,
        source: 'llm',
        runId,
        isPrimary: true,
      })
      this.insertEvidence(runId, labelId, objectId, 0.9, `Domain: ${response.domain}`)
      result.labelsCreated++
    }

    // Entities → entity namespace (proper nouns, tool names, symbols)
    for (const entity of response.entities) {
      const labelId = this.store.ensureLabel('entity', entity)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.75,
        source: 'llm',
        runId,
      })
      result.labelsCreated++
    }

    // Task type
    if (response.task_type) {
      const labelId = this.store.ensureLabel('task', response.task_type)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.9,
        source: 'llm',
        runId,
        isPrimary: true,
      })
      this.insertEvidence(runId, labelId, objectId, 0.9, `Task type: ${response.task_type}`)
      result.labelsCreated++
    }

    // Interaction pattern
    if (response.interaction_pattern) {
      const labelId = this.store.ensureLabel('interaction_pattern', response.interaction_pattern)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.85,
        source: 'llm',
        runId,
      })
      result.labelsCreated++
    }

    // Training value
    if (response.training_value) {
      const labelId = this.store.ensureLabel('training_value', response.training_value)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.9,
        source: 'llm',
        runId,
        isPrimary: true,
      })
      result.labelsCreated++
    }

    // Memory class
    if (response.memory_class) {
      const labelId = this.store.ensureLabel('memory_class', response.memory_class)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.8,
        source: 'llm',
        runId,
      })
      result.labelsCreated++
    }

    // Error taxonomy
    if (response.error_taxonomy) {
      const labelId = this.store.ensureLabel('error_type', response.error_taxonomy)
      this.store.attachLabel(objectId, labelId, {
        confidence: 0.8,
        source: 'llm',
        runId,
      })
      result.labelsCreated++
    }

    // Suggested labels (lower confidence for unknown namespaces)
    for (const sl of response.suggested_labels) {
      const labelId = this.store.ensureLabel(sl.namespace, sl.name)
      this.store.attachLabel(objectId, labelId, {
        confidence: sl.confidence * 0.7, // discount for suggested
        source: 'llm',
        runId,
      })
      result.labelsCreated++
    }

    // Quality metrics
    this.store.setQualityMetric({
      object_id: objectId,
      metric: 'difficulty',
      value: response.difficulty,
      source: 'llm',
      annotation_run_id: runId,
      updated_at: Date.now(),
    })
    result.metricsSet++

    this.store.setQualityMetric({
      object_id: objectId,
      metric: 'trainability',
      value: response.training_value === 'high' ? 0.9
        : response.training_value === 'medium' ? 0.6
        : response.training_value === 'low' ? 0.3 : 0.0,
      source: 'llm',
      annotation_run_id: runId,
      updated_at: Date.now(),
    })
    result.metricsSet++

    // Privacy risk as metric
    const privacyScore = response.privacy_risk === 'high' ? 1.0
      : response.privacy_risk === 'medium' ? 0.6
      : response.privacy_risk === 'low' ? 0.3 : 0.0
    this.store.setQualityMetric({
      object_id: objectId,
      metric: 'privacy_risk',
      value: privacyScore,
      source: 'llm',
      annotation_run_id: runId,
      updated_at: Date.now(),
    })
    result.metricsSet++
  }

  private insertEvidence(
    runId: string,
    labelId: string,
    objectId: string,
    score: number,
    explanation: string,
  ): void {
    this.store.insertEvidence({
      evidence_id: TrainingStore.genId('ev'),
      run_id: runId,
      label_id: labelId,
      chunk_id: null,
      object_id: objectId,
      score,
      explanation,
    })
  }
}
