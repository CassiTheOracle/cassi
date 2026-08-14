import { describe, expect, it } from 'vitest'
import Database from 'better-sqlite3'

import { MnemicField } from '@cassicore/mnemic-field'
import { BranchingConversationManager } from './manager.js'
import { BranchingSessionStore } from './session-store.js'
import type { ILogger } from '@cassicore/foundation'

function logger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => logger(),
  }
}

describe('BranchingSessionStore replay bridge', () => {
  it('dual-writes branching turns into replay engrams and branch edges', () => {
    const db = new Database(':memory:')
    const field = new MnemicField(logger(), ':memory:')
    const store = new BranchingSessionStore(db, field)
    const manager = new BranchingConversationManager()
    const session = manager.createSession('branch-s1', 'web', 'user-1', { model: 'test' })

    const root = manager.addTurn('branch-s1', { role: 'user', content: 'root' })
    manager.addTurn('branch-s1', { role: 'assistant', content: 'main response' })
    manager.forkBranch('branch-s1', 'alt')
    manager.switchBranch('branch-s1', 'alt')
    const alt = manager.addTurn('branch-s1', { role: 'assistant', content: 'alternate response' }, root)

    store.save(session)

    expect(store.load('branch-s1')?.turnTree.size).toBe(3)
    expect(field.get('session:branch-s1')?.nodeType).toBe('session')
    expect(field.get(`turn:branch-s1:${alt}`)?.metadata).toMatchObject({
      sessionId: 'branch-s1',
      parentTurnId: root,
      branchPath: 'alt',
    })

    const sessionGraph = field.getReplaySubgraph('session:branch-s1')
    expect(sessionGraph.nodes.map(n => n.engram.id)).toContain(`turn:branch-s1:${root}`)
    expect(sessionGraph.nodes.map(n => n.engram.id)).toContain(`turn:branch-s1:${alt}`)
    expect(sessionGraph.synapses.map(s => `${s.sourceId}->${s.targetId}:${s.edgeType}`)).toContain(
      `turn:branch-s1:${alt}->turn:branch-s1:${root}:spawned_from`,
    )

    store.remove('branch-s1')
    field.close()
    db.close()
  })

  it('keeps legacy save working when replay bridge fails', () => {
    const db = new Database(':memory:')
    const failingField = {
      get: () => null,
      store: () => { throw new Error('mnemic unavailable') },
      delete: () => false,
      connect: () => undefined,
      getEngramsByIdPrefix: () => [],
    } as unknown as MnemicField
    const store = new BranchingSessionStore(db, failingField)
    const manager = new BranchingConversationManager()
    const session = manager.createSession('branch-fail', 'web', 'user-1', { model: 'test' })
    manager.addTurn('branch-fail', { role: 'user', content: 'root' })

    expect(() => store.save(session)).not.toThrow()
    expect(store.load('branch-fail')?.turnTree.size).toBe(1)

    db.close()
  })
})
