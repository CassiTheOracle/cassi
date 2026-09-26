import fs from 'node:fs'
import { createHash } from 'node:crypto'
import os from 'node:os'
import path from 'node:path'
import Database from 'better-sqlite3'
import { describe, expect, it, vi } from 'vitest'

import { initMnemicFieldSchema } from '../src/schema.js'
import {
  MnemicExactStore,
  MnemicFieldJournalError,
  mnemicFieldAddress,
  mnemicFieldCanonicalJson,
  mnemicRecordRevision,
} from '../src/exact-store.js'
import { mockLogger } from './helpers.js'

describe('MnemicExactStore', () => {
  it('keeps exact records inert and journals every durable mutation', () => {
    const store = new MnemicExactStore(mockLogger(), ':memory:')
    const wake = vi.fn()
    store.onFieldEvent = wake

    const first = store.store({
      id: 'memory-a',
      content: 'alpha exact memory',
      nodeType: 'fact',
      x: 0.9,
      y: -0.8,
      z: 0.7,
      initialPotentiation: 9,
      embedding: [1, 2, 3],
      metadata: { sessionId: 'session-a' },
    })
    store.store({ id: 'memory-b', content: 'beta exact memory', nodeType: 'fact' })

    expect(first).toMatchObject({ x: 0, y: 0, z: 0, potentiation: 0, embedding: null })
    expect(store.update('memory-a', { x: 1, potentiation: 10, content: 'alpha updated' }))
      .toMatchObject({ x: 0, y: 0, z: 0, potentiation: 0, embedding: null, content: 'alpha updated' })

    store.connect({
      sourceId: 'memory-a',
      targetId: 'memory-b',
      edgeType: 'related_to',
      metadata: { sessionId: 'session-a' },
    })
    expect(store.disconnect('memory-a', 'memory-b', 'related_to')).toBe(true)

    store.store({
      id: 'checkpoint-a',
      content: 'context checkpoint',
      nodeType: 'session',
      provenance: 'cassi-context-compaction',
      metadata: { sessionId: 'session-a', candidateIds: ['memory-a', 'memory-b'] },
    })
    expect(store.getMany(['memory-b', 'memory-a', 'memory-b']).map(record => record.id))
      .toEqual(['memory-b', 'memory-a'])
    expect(store.delete('memory-a')).toBe(true)

    const events = store.fieldEventsAfter(0)
    expect(events.map(event => event.payload.kind === 'memory' ? event.payload.operation : null))
      .toEqual(['store', 'store', 'update', 'connect', 'disconnect', 'store', 'delete'])
    expect(events[0].payload).toMatchObject({
      kind: 'memory',
      context_session_id: 'session-a',
      record: { id: 'memory-a', revision: expect.stringMatching(/^[0-9a-f]{64}$/) },
    })
    const updatePayload = events[2]?.payload
    if (updatePayload?.kind !== 'memory') throw new Error('missing update payload')
    expect(updatePayload).toMatchObject({
      operation: 'update',
      previous_record: {
        id: 'memory-a',
        content: 'alpha exact memory',
        node_type: 'fact',
        revision: expect.stringMatching(/^[0-9a-f]{64}$/),
      },
      record: {
        id: 'memory-a',
        content: 'alpha updated',
        node_type: 'fact',
        revision: expect.stringMatching(/^[0-9a-f]{64}$/),
      },
    })
    expect(updatePayload.previous_record?.revision).not.toBe(updatePayload.record.revision)
    expect(events.every((event, index) => (
      event.sequence === index + 1
      && event.previousEventId === (index === 0 ? '0'.repeat(64) : events[index - 1].eventId)
    ))).toBe(true)
    expect(wake).toHaveBeenCalledTimes(7)
    expect(store.fieldRecordEvents('memory-a', events.at(-1)!.sequence).map(event => event.sequence))
      .toEqual([1, 3, 7])

    store.acknowledgeFieldEventsThrough(events[4].sequence, events[4].eventId)
    expect(store.fieldStreamStatus()).toMatchObject({
      headSequence: 7,
      headEventId: events[6].eventId,
      acknowledgedSequence: 5,
    })
    store.close()
  })

  it('rolls back the record and R-tree when journal insertion fails', () => {
    const db = new Database(':memory:')
    const store = new MnemicExactStore(mockLogger(), db)
    db.exec(`
      CREATE TRIGGER reject_field_event
      BEFORE INSERT ON mnemic_field_events
      BEGIN
        SELECT RAISE(ABORT, 'forced field journal failure');
      END
    `)

    expect(() => store.store({
      id: 'must-rollback',
      content: 'never partially commit',
      nodeType: 'fact',
    })).toThrow(/forced field journal failure/)
    expect(store.get('must-rollback')).toBeNull()
    expect(db.prepare('SELECT COUNT(*) AS count FROM engram_rtree').get()).toEqual({ count: 0 })
    expect(store.fieldStreamStatus()).toMatchObject({ headSequence: 0, acknowledgedSequence: 0 })
    store.close()
  })

  it('tracks a collision-checked exact address manifest transactionally', () => {
    const db = new Database(':memory:')
    const store = new MnemicExactStore(mockLogger(), db)
    const first = store.store({
      id: 'memory-a',
      content: 'alpha exact memory',
      nodeType: 'fact',
    })
    const [initial] = store.fieldAddressManifest()
    expect(initial).toMatchObject({
      recordId: first.id,
      fieldRecordId: first.id,
      revision: createHash('sha256')
        .update(first.id)
        .update('\0')
        .update(first.nodeType)
        .update('\0')
        .update(first.content)
        .digest('hex'),
      startByte: 0,
      endByte: Buffer.byteLength(first.content),
      semanticKind: first.nodeType,
      contentSha256: createHash('sha256').update(first.content).digest('hex'),
    })
    expect(store.resolveFieldAddress(initial!.address)?.record.content)
      .toBe('alpha exact memory')
    const queryPlan = db.prepare(`
      EXPLAIN QUERY PLAN
      SELECT record_id FROM mnemic_field_address_manifest WHERE address = ?
    `).all(initial!.address) as Array<{ detail: string }>
    expect(queryPlan.some(row => row.detail.includes('SEARCH mnemic_field_address_manifest'))).toBe(true)

    store.update(first.id, { content: 'alpha exact memory updated' })
    const [updated] = store.fieldAddressManifest()
    expect(updated!.address).not.toBe(initial!.address)
    expect(store.resolveFieldAddress(initial!.address)).toBeNull()
    expect(store.resolveFieldAddress(updated!.address)?.record.content)
      .toBe('alpha exact memory updated')

    store.delete(first.id)
    expect(store.fieldAddressManifest()).toEqual([])
    expect(store.resolveFieldAddress(updated!.address)).toBeNull()
    store.close()
  })

  it('excludes current-session records before field address recall', () => {
    const store = new MnemicExactStore(mockLogger(), ':memory:')
    store.store({
      id: 'current',
      content: 'current session memory',
      nodeType: 'fact',
      metadata: { sessionId: 'session-a' },
    })
    store.store({
      id: 'prior',
      content: 'prior session memory',
      nodeType: 'fact',
      metadata: { sessionId: 'session-b' },
    })
    store.store({
      id: 'unscoped',
      content: 'unscoped memory',
      nodeType: 'fact',
    })

    expect(
      store.fieldAddressManifest({ excludeSessionId: 'session-a' })
        .map(entry => entry.recordId)
        .sort(),
    ).toEqual(['prior', 'unscoped'])
    expect(() => store.fieldAddressManifest({ excludeSessionId: '' }))
      .toThrow('excludeSessionId must be a bounded opaque identifier')
    expect(() => store.fieldAddressManifest({ excludeSessionId: 'x'.repeat(129) }))
      .toThrow('excludeSessionId must be a bounded opaque identifier')
    store.close()
  })

  it('announces legacy exact records to the field exactly once', () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'mnemic-address-migration-'))
    const databasePath = path.join(directory, 'field.db')
    let store: MnemicExactStore | null = null
    let database: Database.Database | null = null
    const durableCounts = (): { events: number; announcements: number; head: number } => {
      const inspection = new Database(databasePath, { readonly: true })
      try {
        const events = inspection.prepare(`
          SELECT COUNT(*) AS count FROM mnemic_field_events
        `).get() as { count: number }
        const announcements = inspection.prepare(`
          SELECT COUNT(*) AS count FROM mnemic_field_address_announcements
        `).get() as { count: number }
        const stream = inspection.prepare(`
          SELECT last_sequence FROM mnemic_field_stream WHERE singleton = 1
        `).get() as { last_sequence: number }
        return {
          events: events.count,
          announcements: announcements.count,
          head: stream.last_sequence,
        }
      } finally {
        inspection.close()
      }
    }
    try {
      database = new Database(databasePath)
      initMnemicFieldSchema(database)
      const record = {
        id: 'legacy-memory',
        content: 'legacy exact content',
        nodeType: 'fact',
      }
      database.prepare(`
        INSERT INTO engrams (id, content, node_type, created_at, metadata)
        VALUES (?, ?, ?, ?, ?)
      `).run(
        record.id,
        record.content,
        record.nodeType,
        new Date(0).toISOString(),
        JSON.stringify({ sessionId: 'legacy-session' }),
      )
      const streamId = 'legacy-field-stream'
      const previousEventId = '0'.repeat(64)
      const payload = {
        kind: 'memory',
        context_session_id: 'legacy-session',
        operation: 'store',
        record: {
          id: record.id,
          content: record.content,
          node_type: record.nodeType,
          revision: mnemicRecordRevision(record),
        },
      }
      const eventId = createHash('sha256').update(mnemicFieldCanonicalJson({
        stream_id: streamId,
        sequence: 1,
        previous_event_id: previousEventId,
        payload,
      })).digest('hex')
      database.exec(`
        CREATE TABLE mnemic_field_stream (
          singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
          stream_id TEXT NOT NULL UNIQUE,
          last_sequence INTEGER NOT NULL,
          head_event_id TEXT NOT NULL
        );
        CREATE TABLE mnemic_field_events (
          stream_id TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          previous_event_id TEXT NOT NULL,
          event_id TEXT NOT NULL UNIQUE,
          payload TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          acknowledged_at INTEGER,
          PRIMARY KEY (stream_id, sequence)
        );
      `)
      database.prepare(`
        INSERT INTO mnemic_field_stream
          (singleton, stream_id, last_sequence, head_event_id)
        VALUES (1, ?, 1, ?)
      `).run(streamId, eventId)
      database.prepare(`
        INSERT INTO mnemic_field_events
          (stream_id, sequence, previous_event_id, event_id, payload, created_at)
        VALUES (?, 1, ?, ?, ?, ?)
      `).run(
        streamId,
        previousEventId,
        eventId,
        mnemicFieldCanonicalJson(payload),
        Date.now(),
      )
      database.close()
      database = null

      store = new MnemicExactStore(mockLogger(), databasePath)
      const address = store.fieldAddressManifest()[0]?.address
      const migrated = store.fieldEventsAfter(0)
      expect(migrated).toHaveLength(2)
      expect(migrated[0]?.payload).toMatchObject({
        kind: 'memory',
        record: { id: record.id },
      })
      expect(
        migrated[0]?.payload.kind === 'memory'
          ? migrated[0].payload.record.field_address
          : undefined,
      ).toBeUndefined()
      expect(migrated[1]?.payload).toMatchObject({
        kind: 'memory',
        operation: 'store',
        record: {
          id: record.id,
          field_address: address,
        },
      })
      store.close()
      store = null
      expect(durableCounts()).toEqual({ events: 2, announcements: 1, head: 2 })

      store = new MnemicExactStore(mockLogger(), databasePath)
      expect(store.fieldEventsAfter(0)).toHaveLength(2)
      store.close()
      store = null
      expect(durableCounts()).toEqual({ events: 2, announcements: 1, head: 2 })

      store = new MnemicExactStore(mockLogger(), databasePath)
      expect(store.fieldEventsAfter(0)).toHaveLength(2)
      store.close()
      store = null
      expect(durableCounts()).toEqual({ events: 2, announcements: 1, head: 2 })
    } finally {
      if (database?.open) database.close()
      store?.close()
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })


  it('matches the CassiFI condensation address codec', () => {
    expect(mnemicFieldAddress({
      recordId: 'memory-a',
      revision: '1'.repeat(64),
      startByte: 0,
      endByte: 18,
      semanticKind: 'fact',
    })).toBe('c8c53e532f28b177acd4d477e0660fc0')
  })

  it('retains feedback eligibility across long delays and process restart', () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'mnemic-eligibility-'))
    const databasePath = path.join(directory, 'field.db')
    let store: MnemicExactStore | null = null
    try {
      store = new MnemicExactStore(mockLogger(), databasePath)
      for (let turnId = 0; turnId < 129; turnId += 1) {
        store.rememberContextTurn('session-a', turnId, `query ${turnId}`, [{
          id: `memory-${turnId}`,
          recordId: `memory-${turnId}`,
          startByte: 0,
          endByte: Buffer.byteLength(`candidate ${turnId}`),
          text: `candidate ${turnId}`,
          revision: turnId.toString(16).padStart(64, '0'),
        }])
      }
      store.close()
      store = null

      store = new MnemicExactStore(mockLogger(), databasePath)
      const event = store.consumeContextFeedback('session-a', 0, ['memory-0'], 'completed')
      expect(event?.payload).toEqual({
        kind: 'feedback',
        context_session_id: 'session-a',
        turn_id: 0,
        query: 'query 0',
        candidates: [{
          id: 'memory-0',
          record_id: 'memory-0',
          start_byte: 0,
          end_byte: Buffer.byteLength('candidate 0'),
          text: 'candidate 0',
          revision: '0'.repeat(64),
        }],
        outcome: 'completed',
      })
      expect(store.consumeContextFeedback('session-a', 0, ['memory-0'], 'completed')).toBeNull()
    } finally {
      store?.close()
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })
  it('resolves feedback received before eligibility exactly once after restart', () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'mnemic-feedback-first-'))
    const databasePath = path.join(directory, 'field.db')
    let store: MnemicExactStore | null = null
    try {
      store = new MnemicExactStore(mockLogger(), databasePath)
      expect(store.consumeContextFeedback(
        'session-a',
        7,
        ['memory-a'],
        'completed',
        { id: 'tc-7', name: 'pytest', isError: false },
      )).toBeNull()
      store.close()
      store = null

      store = new MnemicExactStore(mockLogger(), databasePath)
      const wake = vi.fn()
      store.onFieldEvent = wake
      store.rememberContextTurn('session-a', 7, 'late query', [{
        id: 'memory-a',
        recordId: 'memory-a',
        startByte: 0,
        endByte: Buffer.byteLength('late candidate'),
        text: 'late candidate',
        revision: 'a'.repeat(64),
      }])

      expect(store.fieldEventsAfter(0).map(event => event.payload)).toEqual([{
        kind: 'feedback',
        context_session_id: 'session-a',
        turn_id: 7,
        query: 'late query',
        candidates: [{
          id: 'memory-a',
          record_id: 'memory-a',
          start_byte: 0,
          end_byte: Buffer.byteLength('late candidate'),
          text: 'late candidate',
          revision: 'a'.repeat(64),
        }],
        outcome: 'completed',
        tool_result: { id: 'tc-7', name: 'pytest', is_error: false },
      }])
      expect(wake).toHaveBeenCalledTimes(1)

      store.rememberContextTurn('session-a', 7, 'duplicate query', [])
      expect(store.consumeContextFeedback('session-a', 7, [], 'cancelled')).toBeNull()
      expect(store.fieldEventsAfter(0)).toHaveLength(1)
      expect(wake).toHaveBeenCalledTimes(1)
    } finally {
      store?.close()
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })

  it('persists exact action starts and outcomes across restart', () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'mnemic-actions-'))
    const databasePath = path.join(directory, 'field.db')
    const argumentsSha256 = 'a'.repeat(64)
    let store: MnemicExactStore | null = null
    try {
      store = new MnemicExactStore(mockLogger(), databasePath)
      const start = store.startActionEpisode({
        contextSessionId: 'session-a',
        turnId: 1,
        planId: 'plan-1',
        toolCallId: 'call-1',
        toolName: 'read',
        argumentsSha256,
        requiredAuthority: 0.8,
        reversible: true,
      })
      expect(start?.payload).toMatchObject({
        kind: 'memory',
        operation: 'store',
        record: { content: '', node_type: 'action' },
        action: {
          episode_id: 'call-1',
          kind: 'tool:read',
          stage: 'start',
          required_authority: 0.8,
          reversible: true,
          authorization_path: ['thalamus:plan:plan-1', 'omp:tool-call:call-1'],
        },
      })
      const recordId = start?.payload.kind === 'memory' ? start.payload.record.id : ''
      const actionId = start?.payload.kind === 'memory' ? start.payload.action?.action_id : ''
      store.close()
      store = null

      store = new MnemicExactStore(mockLogger(), databasePath)
      const completed = store.finishActionEpisode({
        contextSessionId: 'session-a',
        turnId: 1,
        planId: 'plan-1',
        toolCallId: 'call-1',
        isError: false,
      })
      expect(completed?.payload).toMatchObject({
        kind: 'memory',
        operation: 'update',
        previous_record: { id: recordId, content: '', node_type: 'action' },
        record: { id: recordId, content: 'completed', node_type: 'action' },
        action: { action_id: actionId, stage: 'outcome', outcome: 'completed' },
      })
      expect(store.finishActionEpisode({
        contextSessionId: 'session-a',
        turnId: 1,
        planId: 'plan-1',
        toolCallId: 'call-1',
        isError: false,
      })).toBeNull()

      const repeated = store.startActionEpisode({
        contextSessionId: 'session-a',
        turnId: 2,
        planId: 'plan-2',
        toolCallId: 'call-2',
        toolName: 'read',
        argumentsSha256,
        requiredAuthority: 0.8,
        reversible: true,
      })
      expect(repeated?.payload).toMatchObject({
        kind: 'memory',
        operation: 'update',
        previous_record: { id: recordId, content: 'completed' },
        record: { id: recordId, content: '' },
        action: { action_id: actionId, stage: 'start' },
      })
      const failed = store.finishActionEpisode({
        contextSessionId: 'session-a',
        turnId: 2,
        planId: 'plan-2',
        toolCallId: 'call-2',
        isError: true,
      })
      expect(failed?.payload).toMatchObject({
        kind: 'memory',
        previous_record: { id: recordId, content: '' },
        record: { id: recordId, content: 'error' },
        action: { action_id: actionId, stage: 'outcome', outcome: 'error' },
      })
      expect(store.fieldRecordEvents(recordId, failed!.sequence)).toHaveLength(4)
    } finally {
      store?.close()
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })

  it('rejects attention ranks at the normalized action-authority boundary', () => {
    const store = new MnemicExactStore(mockLogger(), ':memory:')
    expect(() => store.startActionEpisode({
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      toolName: 'read',
      argumentsSha256: 'a'.repeat(64),
      requiredAuthority: 2,
      reversible: true,
    })).toThrow(/invalid exact action episode/)
    store.close()
  })

  it('matches the cross-language canonical wire fixtures', () => {
    const fixture = JSON.parse(fs.readFileSync(
      new URL('./fixtures/mnemic_canonical_wire_v1.json', import.meta.url),
      'utf8',
    )) as {
      schema: string
      cases: Array<{ value: unknown; canonical: string; sha256: string }>
      noncanonical: Array<{ wire: string; canonical: string }>
    }
    expect(fixture.schema).toBe('cassicore.mnemic.field-canonical-fixtures.v1')
    for (const item of fixture.cases) {
      expect(mnemicFieldCanonicalJson(item.value)).toBe(item.canonical)
      expect(createHash('sha256').update(item.canonical).digest('hex')).toBe(item.sha256)
    }
    for (const item of fixture.noncanonical) {
      expect(mnemicFieldCanonicalJson(JSON.parse(item.wire))).toBe(item.canonical)
      expect(item.wire).not.toBe(item.canonical)
    }
  })

  it('verifies raw journal bytes and gates only explicitly installed invalid acknowledged prefixes', () => {
    const db = new Database(':memory:')
    const store = new MnemicExactStore(mockLogger(), db)
    const record = store.store({
      id: 'memory-a',
      content: 'ordinary reads stay available',
      nodeType: 'fact',
    })
    const event = store.fieldEventsAfter(0)[0]!
    store.acknowledgeFieldEventsThrough(event.sequence, event.eventId)
    expect(store.fieldJournalVerificationStatus()).toMatchObject({
      status: 'not-run',
      acknowledgedPrefixValid: true,
    })

    const raw = db.prepare('SELECT payload FROM mnemic_field_events WHERE sequence = 1')
      .get() as { payload: string }
    const payload = JSON.parse(raw.payload) as Record<string, unknown>
    payload.wire_number = 1
    const noncanonical = mnemicFieldCanonicalJson(payload)
      .replace('"wire_number":1', '"wire_number":1.0')
    db.prepare('UPDATE mnemic_field_events SET payload = ? WHERE sequence = 1')
      .run(noncanonical)

    expect(store.get(record.id)?.content).toBe('ordinary reads stay available')
    const verification = store.verifyFieldJournal()
    expect(verification).toMatchObject({
      status: 'invalid',
      acknowledgedPrefixValid: false,
      failure: { code: 'canonical-payload', sequence: 1 },
    })
    expect(store.get(record.id)?.content).toBe('ordinary reads stay available')

    store.requireVerifiedActionJournal(verification)
    expect(() => store.startActionEpisode({
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      toolName: 'read',
      argumentsSha256: 'a'.repeat(64),
      requiredAuthority: 1,
      reversible: true,
    })).toThrow(MnemicFieldJournalError)
    store.close()
  })

  it('keeps exact action retries idempotent and grounds supplied effects in later journal revisions', () => {
    const store = new MnemicExactStore(mockLogger(), ':memory:')
    store.store({
      id: 'memory-a',
      content: 'before',
      nodeType: 'fact',
      metadata: { sessionId: 'session-a' },
    })
    const startInput = {
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      toolName: 'edit',
      argumentsSha256: 'b'.repeat(64),
      requiredAuthority: 1,
      reversible: false,
    } as const
    const start = store.startActionEpisode(startInput)
    expect(start).not.toBeNull()
    expect(store.startActionEpisode(startInput)).toBeNull()
    expect(store.unresolvedActionEpisodes()).toEqual([
      expect.objectContaining({
        episodeId: 'call-1',
        requiredAuthority: 1,
        reversible: false,
      }),
    ])
    expect(() => store.startActionEpisode({ ...startInput, reversible: true }))
      .toThrow(/conflicting exact action episode/)

    store.update('memory-a', { content: 'after' })
    const update = store.fieldEventsAfter(start!.sequence)
      .find(candidate => candidate.payload.kind === 'memory'
        && candidate.payload.record.id === 'memory-a')
    if (!update || update.payload.kind !== 'memory' || !update.payload.previous_record) {
      throw new Error('missing exact action effect revision')
    }
    const effect = {
      record_id: 'memory-a',
      before_revision: update.payload.previous_record.revision,
      after_revision: update.payload.record.revision,
      semantic_kind: 'mnemic:update',
      start_byte: 0,
      end_byte: Buffer.byteLength('after'),
    }
    expect(() => store.finishActionEpisode({
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      isError: false,
      effects: [{ ...effect, after_revision: '0'.repeat(64) }],
    })).toThrow(/effect is not present/)
    expect(store.unresolvedActionEpisodes()).toHaveLength(1)

    const outcome = store.finishActionEpisode({
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      isError: false,
      effects: [effect],
    })
    expect(outcome?.payload).toMatchObject({
      kind: 'memory',
      action: {
        stage: 'outcome',
        outcome: 'completed',
        required_authority: 1,
        reversible: false,
        effects: [effect],
      },
    })
    expect(store.unresolvedActionEpisodes()).toEqual([])
    expect(store.finishActionEpisode({
      contextSessionId: 'session-a',
      turnId: 1,
      planId: 'plan-1',
      toolCallId: 'call-1',
      isError: false,
    })).toBeNull()
    store.close()
  })

  it('adds action policy and effect columns to an existing exact journal', () => {
    const db = new Database(':memory:')
    db.exec(`
      CREATE TABLE mnemic_action_episodes (
        session_id TEXT NOT NULL,
        episode_id TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        turn_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        outcome TEXT,
        created_at INTEGER NOT NULL,
        resolved_at INTEGER,
        PRIMARY KEY (session_id, episode_id)
      )
    `)
    const store = new MnemicExactStore(mockLogger(), db)
    const columns = db.prepare('PRAGMA table_info(mnemic_action_episodes)')
      .all() as Array<{ name: string }>
    expect(columns.map(column => column.name)).toEqual(expect.arrayContaining([
      'required_authority',
      'reversible',
      'start_sequence',
      'effects',
    ]))
    store.close()
  })
  it('retains exact ingress packet references idempotently across restart', () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'mnemic-observations-'))
    const databasePath = path.join(directory, 'field.db')
    const input = {
      contextSessionId: 'session-a',
      recordId: 'observation-a',
      packetSha256: 'a'.repeat(64),
      packetObjectSha256: 'b'.repeat(64),
      payloadManifestSha256: 'c'.repeat(64),
      journalHeadSha256: 'd'.repeat(64),
      viewSha256: 'e'.repeat(64),
      codecId: 'cassi.codec.json-utf8.v1',
      sourceStreamId: 'world:json',
      sourceSequence: 7,
      sourcePath: ['objects#1', 0, 'position#1'],
      sourceSpan: [4, 19] as const,
    }
    let store: MnemicExactStore | null = null
    try {
      store = new MnemicExactStore(mockLogger(), databasePath)
      const first = store.rememberObservation(input)
      expect(store.rememberObservation(input)).toEqual(first)
      expect(first.payload).toMatchObject({
        kind: 'observation',
        context_session_id: 'session-a',
        operation: 'store',
        record: { id: 'observation-a', revision: expect.stringMatching(/^[0-9a-f]{64}$/) },
        reference: {
          packet_sha256: input.packetSha256,
          payload_manifest_sha256: input.payloadManifestSha256,
          journal_head_sha256: input.journalHeadSha256,
          view_sha256: input.viewSha256,
          codec_id: input.codecId,
          source_path: input.sourcePath,
          source_span: input.sourceSpan,
        },
      })
      expect(store.fieldEventsAfter(0)).toHaveLength(1)
      store.close()
      store = null

      store = new MnemicExactStore(mockLogger(), databasePath)
      expect(store.rememberObservation(input).sequence).toBe(first.sequence)
      const updated = store.rememberObservation({
        ...input,
        viewSha256: 'f'.repeat(64),
        sourceSequence: 8,
      })
      expect(updated.payload).toMatchObject({
        kind: 'observation',
        operation: 'update',
        record: {
          id: 'observation-a',
          previous_revision: first.payload.kind === 'observation'
            ? first.payload.record.revision
            : '',
        },
      })
      expect(store.fieldEventsAfter(0)).toHaveLength(2)
      expect(() => store!.rememberObservation({
        ...input,
        packetSha256: 'not-a-digest',
      })).toThrow(/packetSha256/)
    } finally {
      store?.close()
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })


})
