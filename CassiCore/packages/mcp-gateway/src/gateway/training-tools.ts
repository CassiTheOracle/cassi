/**
 * Training Warehouse Tools Module
 * MCP gateway wrappers for the training warehouse admin API.
 *
 * Tools:
 *   training_stats       — Get warehouse statistics (object/chunk/label counts)
 *   training_search      — Full-text search over training chunks
 *   training_objects     — Filtered object search with label/quality constraints
 *   training_resolve     — Resolve a ref key or object ID to full detail
 *   training_labels      — Get label distribution (optional namespace filter)
 *   training_quality     — Get quality metric distribution for a metric
 *   training_annotations — Get annotation run summary
 *   training_ingest      — Trigger ingest from operational databases
 *   training_tag         — Trigger LLM tagging batch
 *   training_export      — Export training examples as JSON or JSONL
 */

import { fetchWithTimeout } from './helpers.js'
import type { ILogger } from '@cassicore/foundation'


export const TRAINING_TOOLS = [
  {
    name: 'training_stats',
    description: 'Get training warehouse statistics — object counts, chunk counts, label distribution, annotation runs, and database size.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'training_search',
    description: 'Full-text search over training chunks. Returns matching chunks with context (role, chunk type, session ID). Uses SQLite FTS5 for fast search across all ingested training data.',
    inputSchema: {
      type: 'object',
      properties: {
        q: {
          type: 'string',
          description: 'Search query (FTS5 syntax supported)',
        },
        limit: {
          type: 'number',
          description: 'Maximum results to return (default: 50)',
        },
        offset: {
          type: 'number',
          description: 'Offset for pagination (default: 0)',
        },
        role: {
          type: 'string',
          description: 'Filter by message role (e.g. "user", "assistant", "system")',
        },
        chunk_type: {
          type: 'string',
          description: 'Filter by chunk type (e.g. "paragraph", "code", "heading")',
        },
        session_id: {
          type: 'string',
          description: 'Filter by session ID',
        },
      },
      required: ['q'],
    },
  },
  {
    name: 'training_objects',
    description: 'Search training objects with filters. Objects represent sessions, turns, messages, tool calls, reasoning traces, artifacts, and events. Supports label and quality-based filtering.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum results (default: 50)',
        },
        offset: {
          type: 'number',
          description: 'Offset for pagination (default: 0)',
        },
        types: {
          type: 'string',
          description: 'Comma-separated object types to filter by (e.g. "session,message,tool_call")',
        },
        session_id: {
          type: 'string',
          description: 'Filter by session ID',
        },
        start_time: {
          type: 'number',
          description: 'Filter objects created after this Unix timestamp (ms)',
        },
        end_time: {
          type: 'number',
          description: 'Filter objects created before this Unix timestamp (ms)',
        },
        labels: {
          type: 'string',
          description: 'Comma-separated label filters in namespace:name format (e.g. "topic:typescript,task:coding")',
        },
        min_quality: {
          type: 'string',
          description: 'Minimum quality filter in metric:value format (e.g. "trainability:0.5")',
        },
      },
    },
  },
  {
    name: 'training_resolve',
    description: 'Resolve a ref key or object ID to its full detail including all chunks, labels, quality metrics, and annotations.',
    inputSchema: {
      type: 'object',
      properties: {
        ref: {
          type: 'string',
          description: 'The ref key or object ID to resolve',
        },
      },
      required: ['ref'],
    },
  },
  {
    name: 'training_labels',
    description: 'Get the distribution of taxonomy labels in the training warehouse. Shows how many objects are tagged with each label.',
    inputSchema: {
      type: 'object',
      properties: {
        namespace: {
          type: 'string',
          description: 'Optional namespace filter (e.g. "topic", "task", "domain")',
        },
      },
    },
  },
  {
    name: 'training_quality',
    description: 'Get the distribution of a quality metric across all training objects. Shows min, max, mean, and histogram buckets.',
    inputSchema: {
      type: 'object',
      properties: {
        metric: {
          type: 'string',
          description: 'Quality metric name (e.g. "trainability", "coherence", "privacy_risk")',
        },
      },
      required: ['metric'],
    },
  },
  {
    name: 'training_annotations',
    description: 'Get a summary of all annotation runs — LLM tagging batches, their status, object counts, and provenance.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'training_ingest',
    description: 'Trigger ingest from operational databases (memory.db, lumen.db, dyad.db) into the training warehouse. Resumable — only new/updated records are ingested. Returns per-source ingest statistics.',
    inputSchema: {
      type: 'object',
      properties: {
        batchSize: {
          type: 'number',
          description: 'Number of records to process per batch (default: 500)',
        },
      },
    },
  },
  {
    name: 'training_tag',
    description: 'Trigger LLM tagging batch on training objects. The LLM generates taxonomy labels, quality scores, and annotations. Uses the daemon-configured tagger adapter (background-tier provider).',
    inputSchema: {
      type: 'object',
      properties: {
        scope: {
          type: 'string',
          description: 'Scope of objects to tag (e.g. "message", "session"). Default: "message".',
        },
        batchSize: {
          type: 'number',
          description: 'Number of objects to tag per batch (default: 50)',
        },
        dryRun: {
          type: 'boolean',
          description: 'If true, report what would be tagged without actually tagging (default: false)',
        },
      },
    },
  },
  {
    name: 'training_export',
    description: 'Export training examples for model fine-tuning. Returns assembled conversation examples with quality and privacy filtering. Supports JSON and JSONL formats.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum examples to export (default: 100)',
        },
        min_trainability: {
          type: 'number',
          description: 'Minimum trainability score filter (0-1)',
        },
        max_privacy_risk: {
          type: 'number',
          description: 'Maximum privacy risk score filter (0-1)',
        },
        session_types: {
          type: 'string',
          description: 'Comma-separated session types to include',
        },
        format: {
          type: 'string',
          description: 'Export format: "json" (default) or "jsonl"',
          enum: ['json', 'jsonl'],
        },
      },
    },
  },
]

export const TRAINING_TOOL_NAMES = new Set(TRAINING_TOOLS.map(t => t.name))


/**
 * Execute a training warehouse tool via CassiCore admin API.
 */
export async function executeTrainingTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger,
): Promise<any> {
  logger.info('Executing training tool', { tool: toolName })

  switch (toolName) {
    case 'training_stats':
      return await fetchTrainingStats(baseUrl, logger)
    case 'training_search':
      return await fetchTrainingSearch(baseUrl, args, logger)
    case 'training_objects':
      return await fetchTrainingObjects(baseUrl, args, logger)
    case 'training_resolve':
      return await fetchTrainingResolve(baseUrl, args, logger)
    case 'training_labels':
      return await fetchTrainingLabels(baseUrl, args, logger)
    case 'training_quality':
      return await fetchTrainingQuality(baseUrl, args, logger)
    case 'training_annotations':
      return await fetchTrainingAnnotations(baseUrl, logger)
    case 'training_ingest':
      return await executeTrainingIngest(baseUrl, args, logger)
    case 'training_tag':
      return await executeTrainingTag(baseUrl, args, logger)
    case 'training_export':
      return await fetchTrainingExport(baseUrl, args, logger)
    default:
      throw new Error(`Unknown training tool: ${toolName}`)
  }
}


async function fetchTrainingStats(baseUrl: string, logger: ILogger): Promise<any> {
  const resp = await fetchWithTimeout(`${baseUrl}/training/stats`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training stats failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingSearch(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  if (!args?.q) throw new Error('q (search query) is required')
  const params = new URLSearchParams()
  params.set('q', args.q)
  if (args?.limit) params.set('limit', String(args.limit))
  if (args?.offset) params.set('offset', String(args.offset))
  if (args?.role) params.set('role', args.role)
  if (args?.chunk_type) params.set('chunk_type', args.chunk_type)
  if (args?.session_id) params.set('session_id', args.session_id)

  const resp = await fetchWithTimeout(`${baseUrl}/training/search?${params}`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training search failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingObjects(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  const params = new URLSearchParams()
  if (args?.limit) params.set('limit', String(args.limit))
  if (args?.offset) params.set('offset', String(args.offset))
  if (args?.types) params.set('types', args.types)
  if (args?.session_id) params.set('session_id', args.session_id)
  if (args?.start_time) params.set('start_time', String(args.start_time))
  if (args?.end_time) params.set('end_time', String(args.end_time))
  if (args?.labels) params.set('labels', args.labels)
  if (args?.min_quality) params.set('min_quality', args.min_quality)

  const qs = params.toString()
  const resp = await fetchWithTimeout(`${baseUrl}/training/objects${qs ? '?' + qs : ''}`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training objects search failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingResolve(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  if (!args?.ref) throw new Error('ref is required')
  const ref = encodeURIComponent(args.ref)
  const resp = await fetchWithTimeout(`${baseUrl}/training/resolve/${ref}`, { method: 'GET' })
  if (!resp.ok) {
    if (resp.status === 404) return { error: 'Object not found', ref: args.ref }
    throw new Error(`Training resolve failed: ${resp.status}`)
  }
  return await resp.json()
}


async function fetchTrainingLabels(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  const params = new URLSearchParams()
  if (args?.namespace) params.set('namespace', args.namespace)
  const qs = params.toString()
  const resp = await fetchWithTimeout(`${baseUrl}/training/labels${qs ? '?' + qs : ''}`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training labels failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingQuality(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  if (!args?.metric) throw new Error('metric is required')
  const resp = await fetchWithTimeout(`${baseUrl}/training/quality/${encodeURIComponent(args.metric)}`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training quality failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingAnnotations(baseUrl: string, logger: ILogger): Promise<any> {
  const resp = await fetchWithTimeout(`${baseUrl}/training/annotations`, { method: 'GET' })
  if (!resp.ok) throw new Error(`Training annotations failed: ${resp.status}`)
  return await resp.json()
}


async function executeTrainingIngest(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  const body: Record<string, unknown> = {}
  if (args?.batchSize) body.batchSize = args.batchSize

  const resp = await fetchWithTimeout(`${baseUrl}/training/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    timeoutMs: 120_000, // ingest can take a while
  })
  if (!resp.ok) throw new Error(`Training ingest failed: ${resp.status}`)
  return await resp.json()
}


async function executeTrainingTag(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  const body: Record<string, unknown> = {}
  if (args?.scope) body.scope = args.scope
  if (args?.batchSize) body.batchSize = args.batchSize
  if (args?.dryRun !== undefined) body.dryRun = args.dryRun

  const resp = await fetchWithTimeout(`${baseUrl}/training/tag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    timeoutMs: 120_000, // tagging can take a while
  })
  if (!resp.ok) throw new Error(`Training tag failed: ${resp.status}`)
  return await resp.json()
}


async function fetchTrainingExport(baseUrl: string, args: any, logger: ILogger): Promise<any> {
  const params = new URLSearchParams()
  if (args?.limit) params.set('limit', String(args.limit))
  if (args?.min_trainability) params.set('min_trainability', String(args.min_trainability))
  if (args?.max_privacy_risk) params.set('max_privacy_risk', String(args.max_privacy_risk))
  if (args?.session_types) params.set('session_types', args.session_types)
  // Always request JSON via MCP (JSONL streaming is for direct HTTP)
  params.set('format', 'json')

  const qs = params.toString()
  const resp = await fetchWithTimeout(`${baseUrl}/training/export${qs ? '?' + qs : ''}`, {
    method: 'GET',
    timeoutMs: 60_000,
  })
  if (!resp.ok) throw new Error(`Training export failed: ${resp.status}`)
  return await resp.json()
}


export function getTrainingTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...TRAINING_TOOLS]
}
