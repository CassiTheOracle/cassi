import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import Database from 'better-sqlite3'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { MnemicField } from '../src/index.js'
import { migrateMemoryAndArchives, migrateMemoryOnly } from '../src/migrate-memory.js'
import { mockLogger } from './helpers.js'

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'mnemic-migrate-'))
}

describe('Mnemic Field migration', () => {
  let dir: string
  let sourcePath: string
  let field: MnemicField

  beforeEach(() => {
    dir = makeTempDir()
    sourcePath = join(dir, 'memory.db')
    const source = new Database(sourcePath)
    source.exec(`
      CREATE TABLE memories (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata TEXT,
        session_id TEXT,
        created_at INTEGER NOT NULL,
        cognitive_class TEXT,
        archived_at INTEGER DEFAULT NULL,
        importance REAL DEFAULT 5.0,
        pinned INTEGER DEFAULT 0,
        valid_at INTEGER,
        invalid_at INTEGER DEFAULT NULL,
        access_count INTEGER DEFAULT 0,
        last_accessed_at INTEGER DEFAULT NULL
      );

      CREATE TABLE archives (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT,
        content TEXT NOT NULL,
        summary TEXT,
        metadata TEXT,
        session_id TEXT,
        created_at INTEGER NOT NULL,
        dreamed_at INTEGER DEFAULT NULL
      );

      CREATE TABLE archive_tags (
        archive_id TEXT NOT NULL,
        tag TEXT NOT NULL
      );

      CREATE TABLE archive_entities (
        archive_id TEXT NOT NULL,
        entity TEXT NOT NULL
      );

      CREATE TABLE archive_topics (
        archive_id TEXT NOT NULL,
        topic TEXT NOT NULL
      );

      CREATE TABLE archive_links (
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        relation TEXT NOT NULL
      );
    `)
    source.close()

    field = new MnemicField(mockLogger(), new Database(':memory:'))
  })

  afterEach(() => {
    field.close()
    rmSync(dir, { recursive: true, force: true })
  })

  describe('memory-only migration', () => {
    it('migrates legacy memories into meso engrams', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at, cognitive_class, importance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run('m1', 'fact', 'hello memory', '{"tags":["alpha"]}', 's1', 1700000000, 'semantic', 7.5)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      expect(result.migrated).toBe(1)
      const engrams = field.list(10)
      expect(engrams.length).toBe(1)
      expect(engrams[0].id).toBe('m1')
      expect(engrams[0].tags).toContain('granularity:meso')
      expect(engrams[0].metadata.granularity).toBe('meso')
    })

    it('maps legacy types to engram types', async () => {
      const source = new Database(sourcePath)
      const insert = source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      insert.run('c1', 'conversation', 'chat', '{}', 's1', 1700000000)
      insert.run('i1', 'insight', 'aha', '{}', 's1', 1700000001)
      insert.run('t1', 'tool_call', 'tool used', '{}', 's1', 1700000002)
      insert.run('o1', 'success', 'it worked', '{}', 's1', 1700000003)
      source.close()

      await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      const byId = new Map(field.list(10).map(e => [e.id, e]))
      expect(byId.get('c1')?.nodeType).toBe('episode')
      expect(byId.get('i1')?.nodeType).toBe('pattern')
      expect(byId.get('t1')?.nodeType).toBe('tool')
      expect(byId.get('o1')?.nodeType).toBe('outcome')
    })

    it('creates micro fragments only for large/reference-dense entries', async () => {
      const source = new Database(sourcePath)
      const large = Array.from({ length: 18 }, (_, i) =>
        `${i + 1}. Step ${i + 1} uses \`git status\` in core/daemon.ts and updates core/intelligence/memory/index.ts before running tests and documenting the result in docs/design/mnemic-field.md.`
      ).join('\n\n')

      source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run('big1', 'fact', large, '{}', 's1', 1700000000)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
        microChunkTokenTarget: 20,
      })

      expect(result.fragmentEngramsCreated).toBeGreaterThan(0)
      const fragments = field.list(100).filter(e => e.id.startsWith('big1::frag:'))
      expect(fragments.length).toBe(result.fragmentEngramsCreated)
      expect(fragments.every(f => f.tags.includes('granularity:micro'))).toBe(true)

      const parentLinks = field.neighbors('big1').synapses.filter(s => s.edgeType === 'part_of')
      expect(parentLinks.length).toBe(fragments.length)
    })

    it('does not micro-chunk small entries', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run('small1', 'fact', 'short note', '{}', 's1', 1700000000)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      expect(result.fragmentEngramsCreated).toBe(0)
      expect(field.list(100).filter(e => e.id.startsWith('small1::frag:')).length).toBe(0)
    })

    it('infers temporal neighbor synapses within sessions', async () => {
      const source = new Database(sourcePath)
      const insert = source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      insert.run('m1', 'fact', 'one', '{}', 'shared', 1700000000)
      insert.run('m2', 'fact', 'two', '{}', 'shared', 1700000001)
      insert.run('m3', 'fact', 'three', '{}', 'shared', 1700000002)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: true,
      })

      expect(result.synapsesCreated).toBeGreaterThanOrEqual(2)
      const neighbors = field.neighbors('m2').synapses.filter(s => s.edgeType === 'temporal_neighbor')
      expect(neighbors.length).toBeGreaterThan(0)
    })

    it('infers similarity from shared tags for meso engrams', async () => {
      const source = new Database(sourcePath)
      const insert = source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      insert.run('m1', 'fact', 'one', '{"tags":["shared"]}', 's1', 1700000000)
      insert.run('m2', 'fact', 'two', '{"tags":["shared"]}', 's2', 1700000001)
      source.close()

      await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: true,
      })

      const neighbors = field.neighbors('m1').synapses.filter(s => s.edgeType === 'similar_to')
      expect(neighbors.length).toBeGreaterThan(0)
    })
  })

  describe('archive migration', () => {
    it('migrates archives into macro engrams', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO archives (id, type, title, content, summary, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run('a1', 'conversation', 'Design Thread', 'Full archive content', 'Short summary', '{"source":"archivist"}', 's1', 1700000000)
      source.close()

      const result = await migrateMemoryAndArchives(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      expect(result.archivedMigrated).toBe(1)
      const imported = field.get('archive:a1')
      expect(imported).not.toBeNull()
      expect(imported!.tags).toContain('granularity:macro')
      expect(imported!.nodeType).toBe('episode')
      expect(imported!.content).toContain('Design Thread')
      expect(imported!.content).toContain('Short summary')
    })

    it('imports archive tags/entities/topics into macro engram tags', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO archives (id, type, title, content, summary, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run('a1', 'insight', 'Archive', 'Body', null, '{}', 's1', 1700000000)
      source.prepare(`INSERT INTO archive_tags (archive_id, tag) VALUES (?, ?)`).run('a1', 'memory')
      source.prepare(`INSERT INTO archive_entities (archive_id, entity) VALUES (?, ?)`).run('a1', 'CassiCore')
      source.prepare(`INSERT INTO archive_topics (archive_id, topic) VALUES (?, ?)`).run('a1', 'architecture')
      source.close()

      await migrateMemoryAndArchives(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      const imported = field.get('archive:a1')!
      expect(imported.tags).toContain('memory')
      expect(imported.tags).toContain('architecture')
      expect(imported.tags).toContain('entity:CassiCore')
      expect(imported.tags).toContain('archive-type:insight')
    })

    it('converts archive_links into graph synapses', async () => {
      const source = new Database(sourcePath)
      const insert = source.prepare(`
        INSERT INTO archives (id, type, title, content, summary, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `)
      insert.run('a1', 'conversation', 'A1', 'Body1', null, '{}', 's1', 1700000000)
      insert.run('a2', 'pattern', 'A2', 'Body2', null, '{}', 's1', 1700000001)
      source.prepare(`INSERT INTO archive_links (source_id, target_id, relation) VALUES (?, ?, ?)`).run('a1', 'a2', 'supports')
      source.close()

      const result = await migrateMemoryAndArchives(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      expect(result.synapsesCreated).toBe(1)
      const synapses = field.neighbors('archive:a1').synapses.filter(s => s.edgeType === 'supports')
      expect(synapses.length).toBe(1)
    })

    it('creates micro fragments for large archive bodies when warranted', async () => {
      const source = new Database(sourcePath)
      const large = Array.from({ length: 24 }, (_, i) =>
        `${i + 1}. Archive section ${i + 1} references core/daemon.ts, core/intelligence/memory/index.ts, docs/design/mnemic-field.md, and tests/mnemic-field-migration.test.ts while explaining migration, retrieval behavior, graph relationships, and chunk-level precision in detail for the new memory topology.`
      ).join('\n\n')
      source.prepare(`
        INSERT INTO archives (id, type, title, content, summary, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run('a1', 'document', 'Big Archive', large, 'Summary', '{}', 's1', 1700000000)
      source.close()

      const result = await migrateMemoryAndArchives(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
        microChunkTokenTarget: 20,
      })

      expect(result.fragmentEngramsCreated).toBeGreaterThan(0)
      const fragments = field.list(1000).filter(e => e.id.startsWith('archive:a1::frag:'))
      expect(fragments.length).toBeGreaterThan(0)
    })
  })

  describe('archived row policy', () => {
    it('skips archived memories by default', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run('m1', 'fact', 'archived', '{}', 's1', 1700000000, 1700000100)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
      })

      expect(result.migrated).toBe(0)
      expect(field.list(10).length).toBe(0)
    })

    it('can include archived memories when requested', async () => {
      const source = new Database(sourcePath)
      source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run('m1', 'fact', 'archived', '{}', 's1', 1700000000, 1700000100)
      source.close()

      const result = await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        includeArchived: true,
        inferSynapses: false,
      })

      expect(result.migrated).toBe(1)
      expect(field.list(10).length).toBe(1)
    })
  })

  describe('embedding-assisted import', () => {
    it('uses embedding provider and reprojects imported engrams', async () => {
      const source = new Database(sourcePath)
      const insert = source.prepare(`
        INSERT INTO memories (id, type, content, metadata, session_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      insert.run('m1', 'fact', 'alpha', '{}', 's1', 1700000000)
      insert.run('m2', 'fact', 'beta', '{}', 's1', 1700000001)
      source.close()

      await migrateMemoryOnly(mockLogger(), {
        sourceDbPath: sourcePath,
        targetField: field,
        inferSynapses: false,
        embeddingProvider: async (text) => text === 'alpha' ? [1, 0, 0] : [0, 1, 0],
      })

      const [a, b] = field.list(10)
      expect(a.x !== 0 || a.y !== 0 || b.x !== 0 || b.y !== 0).toBe(true)
    })
  })
})
