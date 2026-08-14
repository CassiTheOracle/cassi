import Database from 'better-sqlite3'
import type { ILogger } from '../../../types/interfaces.js'
import { MnemicField } from './index.js'
import type { EngramType, SynapseType } from './types.js'

interface LegacyMemoryRow {
  id: string
  type: string
  content: string
  metadata: string | null
  session_id: string | null
  created_at: number
  cognitive_class?: string | null
  importance?: number | null
  pinned?: number | null
  valid_at?: number | null
  invalid_at?: number | null
  access_count?: number | null
  last_accessed_at?: number | null
  archived_at?: number | null
}

interface ArchiveRow {
  id: string
  type: string
  content: string
  thinking?: string | null
  analysis_json?: string | null
  metadata_json?: string | null
  session_id: string | null
  parent_id?: string | null
  importance?: number | null
  sentiment?: string | null
  topics_json?: string | null
  entities_json?: string | null
  tags_json?: string | null
  source?: string | null
  timestamp: number
  created_at?: number | null
  dreamed_at?: number | null
  title?: string | null
  summary?: string | null
}

interface ArchiveTagRow { archive_id: string; tag: string }
interface ArchiveEntityRow { archive_id: string; entity: string }
interface ArchiveTopicRow { archive_id: string; topic: string }
interface ArchiveLinkRow { source_id: string; target_id: string; relationship?: string; relation?: string }

export interface MemoryMigrationOptions {
  sourceDbPath: string
  targetField: MnemicField
  includeArchived?: boolean
  migrateArchives?: boolean
  inferSynapses?: boolean
  limit?: number
  archiveLimit?: number
  archiveLinkLimit?: number
  embeddingProvider?: (text: string) => Promise<number[] | null>
  enableMicroChunking?: boolean
  microChunkTokenTarget?: number
}

export interface MemoryMigrationResult {
  migrated: number
  archivedMigrated: number
  skipped: number
  synapsesCreated: number
  fragmentEngramsCreated: number
  errors: string[]
}

export interface ChunkedMigrationProgress extends MemoryMigrationResult {
  nextMemoryOffset: number
  nextArchiveOffset: number
  nextLinkOffset: number
  phase: ChunkedMigrationPhase
  done: boolean
}

export type ChunkedMigrationPhase = 'memories' | 'archives' | 'links' | 'synapses' | 'consolidation' | 'done'

export interface ChunkedMigrationOptions extends MemoryMigrationOptions {
  memoryOffset?: number
  archiveOffset?: number
  linkOffset?: number
  memoryBatchSize?: number
  archiveBatchSize?: number
  linkBatchSize?: number
  phase?: ChunkedMigrationPhase
}

interface GranularityPlan {
  createFragments: boolean
  fragments: string[]
}

export async function migrateMemoryOnly(
  logger: ILogger,
  options: MemoryMigrationOptions,
): Promise<MemoryMigrationResult> {
  return migrateIntoField(logger, options, { memories: true, archives: false })
}

export async function migrateMemoryAndArchives(
  logger: ILogger,
  options: MemoryMigrationOptions,
): Promise<MemoryMigrationResult> {
  return migrateIntoField(logger, options, { memories: true, archives: true })
}

async function migrateIntoField(
  logger: ILogger,
  options: MemoryMigrationOptions,
  scope: { memories: boolean; archives: boolean },
): Promise<MemoryMigrationResult> {
  const log = logger.child ? logger.child('mnemic-memory-migrator') : logger
  const source = new Database(options.sourceDbPath, { readonly: true })
  const result: MemoryMigrationResult = {
    migrated: 0,
    archivedMigrated: 0,
    skipped: 0,
    synapsesCreated: 0,
    fragmentEngramsCreated: 0,
    errors: [],
  }

  try {
    if (scope.memories) {
      const rows = loadLegacyRows(source, options.includeArchived ?? false, options.limit)
      await migrateMemoryRows(rows, options, result)
    }

    if (scope.archives || options.migrateArchives) {
      const archiveRows = loadArchiveRows(source, options.archiveLimit ?? options.limit)
      await migrateArchiveRows(source, archiveRows, options, result)
    }

    if (options.inferSynapses ?? true) {
      result.synapsesCreated += inferSeedSynapses(options.targetField)
    }

    log.info('Migration complete', {
      migrated: result.migrated,
      archivedMigrated: result.archivedMigrated,
      skipped: result.skipped,
      synapsesCreated: result.synapsesCreated,
      fragmentEngramsCreated: result.fragmentEngramsCreated,
      errors: result.errors.length,
    })

    return result
  } finally {
    source.close()
  }
}

async function migrateMemoryRows(
  rows: LegacyMemoryRow[],
  options: MemoryMigrationOptions,
  result: MemoryMigrationResult,
): Promise<void> {
  const embeddingRows: Array<{ row: LegacyMemoryRow; embedding: number[] | null }> = []
  for (const row of rows) {
    let embedding: number[] | null = null
    if (options.embeddingProvider) {
      try {
        embedding = await options.embeddingProvider(row.content)
      } catch (err) {
        result.errors.push(`embedding:${row.id}:${String(err)}`)
      }
    }
    embeddingRows.push({ row, embedding })
  }

  for (const { row, embedding } of embeddingRows) {
    try {
      const mapped = mapLegacyRow(row, embedding)
      options.targetField.store(mapped)
      result.migrated++
      result.fragmentEngramsCreated += createFragmentsForParent(options.targetField, mapped, row.content, options)
    } catch (err) {
      result.skipped++
      result.errors.push(`migrate:${row.id}:${String(err)}`)
    }
  }

  if (embeddingRows.length > 1) {
    await options.targetField.reprojectAllAsync()
  }
}

async function migrateArchiveRows(
  db: Database.Database,
  rows: ArchiveRow[],
  options: MemoryMigrationOptions,
  result: MemoryMigrationResult,
  opts?: { skipLinks?: boolean },
): Promise<void> {
  const tags = loadArchiveTags(db)
  const entities = loadArchiveEntities(db)
  const topics = loadArchiveTopics(db)
  const links = loadArchiveLinks(db, options.archiveLinkLimit)

  const tagsById = bucketBy(tags, row => row.archive_id, row => row.tag)
  const entitiesById = bucketBy(entities, row => row.archive_id, row => row.entity)
  const topicsById = bucketBy(topics, row => row.archive_id, row => row.topic)

  for (const row of rows) {
    try {
      const id = `archive:${row.id}`
      const metadata = parseJsonSafe(row.metadata_json ?? null)
      const analysis = parseJsonSafe(row.analysis_json ?? null)
      const inlineTopics = parseJsonStringArray(row.topics_json ?? null)
      const inlineEntities = parseJsonStringArray(row.entities_json ?? null)
      const inlineTags = parseJsonStringArray(row.tags_json ?? null)
      const content = [row.title, row.summary, row.content, row.thinking].filter(Boolean).join('\n\n')
      const archiveTags = [
        ...(tagsById.get(row.id) ?? []),
        ...(topicsById.get(row.id) ?? []),
        ...inlineTopics,
        ...inlineTags,
        ...((entitiesById.get(row.id) ?? []).map(entity => `entity:${entity}`)),
        ...(inlineEntities.map(entity => `entity:${entity}`)),
        'granularity:macro',
        `archive-type:${row.type}`,
        ...(row.session_id ? [`session:${row.session_id}`] : []),
      ]
      const rawTime = row.timestamp ?? row.created_at ?? 0
      const timeMs = rawTime > 1e10 ? rawTime : rawTime * 1000

      options.targetField.store({
        id,
        content,
        nodeType: mapArchiveType(row.type),
        t: timeMs,
        createdAt: new Date(timeMs).toISOString(),
        tags: [...new Set(archiveTags)],
        provenance: row.source || (row.session_id ? `archive:${row.session_id}` : 'archive:migrated'),
        metadata: {
          granularity: 'macro',
          sourceArchiveId: row.id,
          archiveType: row.type,
          dreamedAt: row.dreamed_at ?? null,
          entities: [...new Set([...(entitiesById.get(row.id) ?? []), ...inlineEntities])],
          topics: [...new Set([...(topicsById.get(row.id) ?? []), ...inlineTopics])],
          legacyMetadata: metadata,
          analysis,
          parentId: row.parent_id ?? null,
          importance: row.importance ?? null,
          sentiment: row.sentiment ?? null,
        },
      })
      result.archivedMigrated++

      result.fragmentEngramsCreated += createFragmentsForParent(options.targetField, {
        id,
        content,
        nodeType: mapArchiveType(row.type),
        t: timeMs,
        createdAt: new Date(timeMs).toISOString(),
        tags: [...new Set(archiveTags)],
        provenance: row.source || (row.session_id ? `archive:${row.session_id}` : 'archive:migrated'),
        metadata: { granularity: 'macro' },
      }, content, options)
    } catch (err) {
      result.skipped++
      result.errors.push(`archive:${row.id}:${String(err)}`)
    }
  }

  if (!opts?.skipLinks) {
    for (const link of links) {
      const sourceId = `archive:${link.source_id}`
      const targetId = `archive:${link.target_id}`
      const source = options.targetField.get(sourceId)
      const target = options.targetField.get(targetId)
      if (!source || !target) continue

      options.targetField.connect({
        sourceId,
        targetId,
        edgeType: mapArchiveRelation(link.relationship ?? link.relation ?? 'similar_to'),
        weight: 0.7,
        metadata: { inferredFrom: 'archive-link', relation: (link.relationship ?? link.relation ?? 'similar_to') },
      })
      result.synapsesCreated++
    }
  }
}

function loadLegacyRows(db: Database.Database, includeArchived: boolean, limit?: number): LegacyMemoryRow[] {
  const where = includeArchived ? '' : 'WHERE archived_at IS NULL'
  const limitClause = limit ? `LIMIT ${limit}` : ''
  return db.prepare(`
    SELECT id, type, content, metadata, session_id, created_at,
           cognitive_class, importance, pinned, valid_at, invalid_at,
           access_count, last_accessed_at, archived_at
    FROM memories
    ${where}
    ORDER BY created_at ASC
    ${limitClause}
  `).all() as LegacyMemoryRow[]
}

function loadArchiveRows(db: Database.Database, limit?: number): ArchiveRow[] {
  const limitClause = limit ? `LIMIT ${limit}` : ''
  const cols = db.prepare(`PRAGMA table_info(archives)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  const select = [
    'id',
    'type',
    names.has('content') ? 'content' : `'' AS content`,
    names.has('thinking') ? 'thinking' : `NULL AS thinking`,
    names.has('analysis_json') ? 'analysis_json' : `NULL AS analysis_json`,
    names.has('metadata_json') ? 'metadata_json' : (names.has('metadata') ? 'metadata AS metadata_json' : `NULL AS metadata_json`),
    names.has('session_id') ? 'session_id' : `NULL AS session_id`,
    names.has('parent_id') ? 'parent_id' : `NULL AS parent_id`,
    names.has('importance') ? 'importance' : `NULL AS importance`,
    names.has('sentiment') ? 'sentiment' : `NULL AS sentiment`,
    names.has('topics_json') ? 'topics_json' : `NULL AS topics_json`,
    names.has('entities_json') ? 'entities_json' : `NULL AS entities_json`,
    names.has('tags_json') ? 'tags_json' : `NULL AS tags_json`,
    names.has('source') ? 'source' : `NULL AS source`,
    names.has('timestamp') ? 'timestamp' : (names.has('created_at') ? 'created_at AS timestamp' : '0 AS timestamp'),
    names.has('created_at') ? 'created_at' : `NULL AS created_at`,
    names.has('dreamed_at') ? 'dreamed_at' : `NULL AS dreamed_at`,
    names.has('title') ? 'title' : `NULL AS title`,
    names.has('summary') ? 'summary' : `NULL AS summary`,
  ]
  return db.prepare(`
    SELECT ${select.join(', ')}
    FROM archives
    ORDER BY timestamp ASC
    ${limitClause}
  `).all() as ArchiveRow[]
}

function loadArchiveTags(db: Database.Database): ArchiveTagRow[] {
  return db.prepare(`SELECT archive_id, tag FROM archive_tags`).all() as ArchiveTagRow[]
}

function loadArchiveEntities(db: Database.Database): ArchiveEntityRow[] {
  return db.prepare(`SELECT archive_id, entity FROM archive_entities`).all() as ArchiveEntityRow[]
}

function loadArchiveTopics(db: Database.Database): ArchiveTopicRow[] {
  return db.prepare(`SELECT archive_id, topic FROM archive_topics`).all() as ArchiveTopicRow[]
}

function loadArchiveLinks(db: Database.Database, limit?: number): ArchiveLinkRow[] {
  const cols = db.prepare(`PRAGMA table_info(archive_links)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  const relationExpr = names.has('relationship')
    ? 'relationship, relationship AS relation'
    : (names.has('relation') ? 'relation, relation AS relationship' : `'similar_to' AS relation, 'similar_to' AS relationship`)
  const limitClause = limit ? ` LIMIT ${limit}` : ''
  return db.prepare(`SELECT source_id, target_id, ${relationExpr} FROM archive_links${limitClause}`).all() as ArchiveLinkRow[]
}

function mapLegacyRow(row: LegacyMemoryRow, embedding: number[] | null): {
  id: string
  content: string
  nodeType: EngramType
  t: number
  createdAt: string
  embedding?: number[] | null
  tags?: string[]
  provenance?: string
  metadata?: Record<string, unknown>
} {
  const metadata = parseJsonSafe(row.metadata)
  const nodeType = mapLegacyType(row.type)
  const tags = extractTags(metadata, row)
  const provenance = buildProvenance(row, metadata)
  const createdMs = row.created_at * 1000

  const engramMeta: Record<string, unknown> = {
    legacyType: row.type,
    sessionId: row.session_id,
    cognitiveClass: row.cognitive_class ?? null,
    importance: row.importance ?? null,
    pinned: !!row.pinned,
    validAt: row.valid_at ?? null,
    invalidAt: row.invalid_at ?? null,
    accessCount: row.access_count ?? 0,
    lastAccessedAt: row.last_accessed_at ?? null,
    legacyMetadata: metadata,
    granularity: 'meso',
  }

  return {
    id: row.id,
    content: row.content,
    nodeType,
    t: createdMs,
    createdAt: new Date(createdMs).toISOString(),
    ...(embedding ? { embedding } : {}),
    ...(tags.length > 0 ? { tags } : {}),
    provenance,
    metadata: engramMeta,
  }
}

function createFragmentsForParent(
  field: MnemicField,
  parent: { id: string; content: string; nodeType: EngramType; t: number; createdAt?: string; tags?: string[]; provenance?: string; metadata?: Record<string, unknown> },
  content: string,
  options: MemoryMigrationOptions,
): number {
  if (!(options.enableMicroChunking ?? true)) return 0
  const plan = planGranularity(content, options.microChunkTokenTarget ?? 180)
  if (!plan.createFragments) return 0

  let created = 0
  for (let i = 0; i < plan.fragments.length; i++) {
    const fragmentId = `${parent.id}::frag:${i + 1}`
    field.store({
      id: fragmentId,
      content: plan.fragments[i],
      nodeType: parent.nodeType,
      t: parent.t,
      createdAt: parent.createdAt,
      tags: [...(parent.tags ?? []), 'granularity:micro', `parent:${parent.id}`],
      provenance: `${parent.provenance ?? 'migrated'}:fragment`,
      metadata: {
        ...(parent.metadata ?? {}),
        parentId: parent.id,
        granularity: 'micro',
        fragmentIndex: i,
        fragmentCount: plan.fragments.length,
      },
    })
    field.connect({
      sourceId: parent.id,
      targetId: fragmentId,
      edgeType: 'part_of',
      weight: 0.8,
      metadata: { inferredFrom: 'migration-fragmentation' },
    })
    created++
  }
  return created
}

function mapLegacyType(type: string): EngramType {
  switch (type) {
    case 'fact':
      return 'fact'
    case 'conversation':
    case 'thinking':
    case 'dialectic_yang':
    case 'dialectic_yin':
    case 'dialectic_serenity':
      return 'episode'
    case 'insight':
    case 'reflection':
    case 'pattern':
      return 'pattern'
    case 'task':
      return 'goal'
    case 'tool_call':
      return 'tool'
    case 'error':
    case 'success':
      return 'outcome'
    case 'event':
      return 'session'
    default:
      return 'fact'
  }
}

function mapArchiveType(type: string): EngramType {
  switch (type) {
    case 'conversation':
    case 'document':
      return 'episode'
    case 'insight':
    case 'pattern':
      return 'pattern'
    case 'event':
      return 'session'
    case 'tool_call':
      return 'tool'
    default:
      return 'episode'
  }
}

function mapArchiveRelation(relation: string): SynapseType {
  switch (relation) {
    case 'contradicts':
      return 'contradicts'
    case 'supports':
      return 'supports'
    case 'caused_by':
      return 'caused_by'
    case 'led_to':
      return 'led_to'
    case 'supersedes':
      return 'supersedes'
    case 'part_of':
      return 'part_of'
    default:
      return 'similar_to'
  }
}

function extractTags(metadata: Record<string, unknown>, row: LegacyMemoryRow): string[] {
  const tags = new Set<string>()
  const explicit = metadata.tags
  if (Array.isArray(explicit)) {
    for (const tag of explicit) {
      if (typeof tag === 'string' && tag.trim()) tags.add(tag.trim())
    }
  }
  tags.add(`legacy:${row.type}`)
  if (row.cognitive_class) tags.add(`cognitive:${row.cognitive_class}`)
  if (row.session_id) tags.add(`session:${row.session_id}`)
  tags.add('granularity:meso')
  return [...tags]
}

function buildProvenance(row: LegacyMemoryRow, metadata: Record<string, unknown>): string {
  if (typeof metadata.source === 'string' && metadata.source) return metadata.source
  if (row.session_id) return `memory:${row.session_id}`
  return 'memory:migrated'
}

function parseJsonSafe(raw: string | null): Record<string, unknown> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
  } catch {
    return {}
  }
}

function parseJsonStringArray(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

function planGranularity(content: string, tokenTarget: number): GranularityPlan {
  const approxTokens = estimateTokens(content)
  const hasManyParagraphs = content.split(/\n\s*\n/).filter(Boolean).length >= 3
  const referenceDense = /`[^`]+`|\b[A-Za-z0-9_./-]+\.[a-z]{2,4}\b|\b(?:npm|npx|git|curl|node|bun)\b|^\d+\./m.test(content)
  const claimDense = /(\n\s*[-*]\s+|\n\s*\d+\.\s+)/.test(content)

  const shouldChunk = approxTokens > 800 || (approxTokens > 400 && (hasManyParagraphs || referenceDense || claimDense))
  if (!shouldChunk) return { createFragments: false, fragments: [] }

  const blocks = content
    .split(/\n\s*\n/)
    .map(part => part.trim())
    .filter(Boolean)

  const fragments: string[] = []
  let current = ''
  let currentTokens = 0

  for (const block of blocks) {
    const blockTokens = estimateTokens(block)
    const wouldOverflow = currentTokens > 0 && currentTokens + blockTokens > tokenTarget
    if (wouldOverflow) {
      fragments.push(current.trim())
      current = block
      currentTokens = blockTokens
    } else {
      current = current ? `${current}\n\n${block}` : block
      currentTokens += blockTokens
    }
  }

  if (current.trim()) fragments.push(current.trim())

  return {
    createFragments: fragments.length > 1,
    fragments,
  }
}

function estimateTokens(text: string): number {
  return Math.ceil(text.trim().split(/\s+/).filter(Boolean).length * 1.3)
}

function inferSeedSynapses(field: MnemicField): number {
  let created = 0
  const engrams = field.list(100000)
  const mesoLikeEngrams = engrams.filter(e => !e.tags.includes('granularity:micro'))
  const bySession = new Map<string, typeof mesoLikeEngrams>()

  for (const engram of mesoLikeEngrams) {
    const sessionTag = engram.tags.find(tag => tag.startsWith('session:'))
    if (!sessionTag) continue
    const sessionId = sessionTag.slice('session:'.length)
    const bucket = bySession.get(sessionId) ?? []
    bucket.push(engram)
    bySession.set(sessionId, bucket)
  }

  for (const [, bucket] of bySession) {
    bucket.sort((a, b) => a.t - b.t)
    for (let i = 0; i < bucket.length - 1; i++) {
      field.connect({
        sourceId: bucket[i].id,
        targetId: bucket[i + 1].id,
        edgeType: 'temporal_neighbor',
        weight: 0.5,
      })
      created++
    }
  }

  const tagBuckets = new Map<string, typeof mesoLikeEngrams>()
  for (const engram of mesoLikeEngrams) {
    for (const tag of engram.tags.filter(tag => !tag.startsWith('session:') && !tag.startsWith('granularity:'))) {
      const bucket = tagBuckets.get(tag) ?? []
      bucket.push(engram)
      tagBuckets.set(tag, bucket)
    }
  }

  for (const [tag, bucket] of tagBuckets) {
    if (bucket.length < 2 || bucket.length > 25) continue
    for (let i = 0; i < bucket.length; i++) {
      for (let j = i + 1; j < bucket.length; j++) {
        field.connect({
          sourceId: bucket[i].id,
          targetId: bucket[j].id,
          edgeType: 'similar_to',
          weight: 0.4,
          metadata: { inferredFrom: 'shared-tag', tag },
        })
        created++
      }
    }
  }

  return created
}


export async function migrateChunk(
  logger: ILogger,
  options: ChunkedMigrationOptions,
): Promise<ChunkedMigrationProgress> {
  const phase = options.phase ?? 'memories'
  const result: ChunkedMigrationProgress = {
    migrated: 0,
    archivedMigrated: 0,
    skipped: 0,
    synapsesCreated: 0,
    fragmentEngramsCreated: 0,
    errors: [],
    nextMemoryOffset: options.memoryOffset ?? 0,
    nextArchiveOffset: options.archiveOffset ?? 0,
    nextLinkOffset: options.linkOffset ?? 0,
    phase,
    done: false,
  }

  if (phase === 'synapses') {
    if (options.inferSynapses ?? true) {
      result.synapsesCreated = inferSeedSynapses(options.targetField)
    }
    result.phase = 'consolidation'
    return result
  }

  if (phase === 'consolidation') {
    try {
      options.targetField.consolidate({
        skipDrift: true,
        skipNuclei: true,
        skipAbstractions: true,
        skipPruning: true,
      })
    } catch (err) {
      logger.warn('Post-migration consolidation failed (non-fatal)', { error: String(err) })
    }
    result.phase = 'done'
    result.done = true
    return result
  }

  if (phase === 'done') {
    result.done = true
    return result
  }

  const source = new Database(options.sourceDbPath, { readonly: true })
  try {
    if (phase === 'memories') {
      const memoryBatchSize = nextBatchSize(result.nextMemoryOffset, options.limit, options.memoryBatchSize ?? 250)
      const memoryRows = memoryBatchSize > 0
        ? loadLegacyRowsChunk(source, options.includeArchived ?? false, result.nextMemoryOffset, memoryBatchSize)
        : []
      if (memoryRows.length > 0) {
        await migrateMemoryRows(memoryRows, options, result)
        result.nextMemoryOffset += memoryRows.length
        result.phase = 'memories'
        return result
      }
      result.phase = options.migrateArchives ? 'archives' : 'synapses'
      return result
    }

    if (phase === 'archives') {
      const archiveBatchSize = nextBatchSize(result.nextArchiveOffset, options.archiveLimit, options.archiveBatchSize ?? 200)
      const archiveRows = archiveBatchSize > 0
        ? loadArchiveRowsChunk(source, result.nextArchiveOffset, archiveBatchSize)
        : []
      if (archiveRows.length > 0) {
        await migrateArchiveRows(source, archiveRows, options, result, { skipLinks: true })
        result.nextArchiveOffset += archiveRows.length
        result.phase = 'archives'
        return result
      }
      result.phase = 'links'
      return result
    }

    if (phase === 'links') {
      const linkBatchSize = nextBatchSize(result.nextLinkOffset, options.archiveLinkLimit, options.linkBatchSize ?? 1000)
      const linkRows = linkBatchSize > 0
        ? loadArchiveLinksChunk(source, result.nextLinkOffset, linkBatchSize)
        : []
      if (linkRows.length > 0) {
        result.synapsesCreated += importArchiveLinks(options.targetField, linkRows)
        result.nextLinkOffset += linkRows.length
        result.phase = 'links'
        return result
      }
      result.phase = 'synapses'
      return result
    }

    result.done = true
    return result
  } finally {
    source.close()
  }
}

function nextBatchSize(offset: number, totalLimit: number | undefined, defaultBatch: number): number {
  if (typeof totalLimit !== 'number') return defaultBatch
  const remaining = totalLimit - offset
  if (remaining <= 0) return 0
  return Math.min(defaultBatch, remaining)
}

function loadLegacyRowsChunk(db: Database.Database, includeArchived: boolean, offset: number, limit: number): LegacyMemoryRow[] {
  const where = includeArchived ? '' : 'WHERE archived_at IS NULL'
  return db.prepare(`
    SELECT id, type, content, metadata, session_id, created_at,
           cognitive_class, importance, pinned, valid_at, invalid_at,
           access_count, last_accessed_at, archived_at
    FROM memories
    ${where}
    ORDER BY created_at ASC
    LIMIT ? OFFSET ?
  `).all(limit, offset) as LegacyMemoryRow[]
}

function loadArchiveRowsChunk(db: Database.Database, offset: number, limit: number): ArchiveRow[] {
  const cols = db.prepare(`PRAGMA table_info(archives)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  const select = [
    'id',
    'type',
    names.has('content') ? 'content' : `'' AS content`,
    names.has('thinking') ? 'thinking' : `NULL AS thinking`,
    names.has('analysis_json') ? 'analysis_json' : `NULL AS analysis_json`,
    names.has('metadata_json') ? 'metadata_json' : (names.has('metadata') ? 'metadata AS metadata_json' : `NULL AS metadata_json`),
    names.has('session_id') ? 'session_id' : `NULL AS session_id`,
    names.has('parent_id') ? 'parent_id' : `NULL AS parent_id`,
    names.has('importance') ? 'importance' : `NULL AS importance`,
    names.has('sentiment') ? 'sentiment' : `NULL AS sentiment`,
    names.has('topics_json') ? 'topics_json' : `NULL AS topics_json`,
    names.has('entities_json') ? 'entities_json' : `NULL AS entities_json`,
    names.has('tags_json') ? 'tags_json' : `NULL AS tags_json`,
    names.has('source') ? 'source' : `NULL AS source`,
    names.has('timestamp') ? 'timestamp' : (names.has('created_at') ? 'created_at AS timestamp' : '0 AS timestamp'),
    names.has('created_at') ? 'created_at' : `NULL AS created_at`,
    names.has('dreamed_at') ? 'dreamed_at' : `NULL AS dreamed_at`,
    names.has('title') ? 'title' : `NULL AS title`,
    names.has('summary') ? 'summary' : `NULL AS summary`,
  ]
  return db.prepare(`
    SELECT ${select.join(', ')}
    FROM archives
    ORDER BY timestamp ASC
    LIMIT ? OFFSET ?
  `).all(limit, offset) as ArchiveRow[]
}

function loadArchiveLinksChunk(db: Database.Database, offset: number, limit: number): ArchiveLinkRow[] {
  const cols = db.prepare(`PRAGMA table_info(archive_links)`).all() as Array<{ name: string }>
  const names = new Set(cols.map(c => c.name))
  const relationExpr = names.has('relationship')
    ? 'relationship, relationship AS relation'
    : (names.has('relation') ? 'relation, relation AS relationship' : `'similar_to' AS relation, 'similar_to' AS relationship`)
  return db.prepare(`SELECT source_id, target_id, ${relationExpr} FROM archive_links LIMIT ? OFFSET ?`).all(limit, offset) as ArchiveLinkRow[]
}

function importArchiveLinks(field: MnemicField, links: ArchiveLinkRow[]): number {
  let created = 0
  for (const link of links) {
    const sourceId = `archive:${link.source_id}`
    const targetId = `archive:${link.target_id}`
    const source = field.get(sourceId)
    const target = field.get(targetId)
    if (!source || !target) continue
    field.connect({
      sourceId,
      targetId,
      edgeType: mapArchiveRelation(link.relationship ?? link.relation ?? 'similar_to'),
      weight: 0.7,
      metadata: { inferredFrom: 'archive-link', relation: (link.relationship ?? link.relation ?? 'similar_to') },
    })
    created++
  }
  return created
}

function bucketBy<T>(rows: T[], keyFn: (row: T) => string, valueFn: (row: T) => string): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const row of rows) {
    const key = keyFn(row)
    const bucket = map.get(key) ?? []
    bucket.push(valueFn(row))
    map.set(key, bucket)
  }
  return map
}
