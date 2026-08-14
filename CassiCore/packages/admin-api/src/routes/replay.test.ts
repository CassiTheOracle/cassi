import { describe, expect, it } from 'vitest'

import { MnemicField } from '@cassicore/mnemic-field'
import { handleReplayRoutes } from './replay.js'

function logger(): any {
  const l = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, child: () => l }
  return l
}

function deps(field: MnemicField, legacySessions: any[] = []) {
  const out: { code?: number; body?: any } = {}
  return {
    out,
    deps: {
      daemon: { __mnemicFieldForCode: field },
      runtime: {
        getLegacySessionStore: () => ({
          list: () => legacySessions,
          get: (id: string) => legacySessions.find(s => s.id === id),
        }),
      },
      logger: logger(),
      sendJSON: (_res: any, code: number, body: unknown) => { out.code = code; out.body = body },
    } as any,
  }
}

describe('admin replay routes', () => {
  it('returns replay session events and summaries', async () => {
    const field = new MnemicField(logger(), ':memory:')
    field.store({ id: 'session:s1', content: '{}', nodeType: 'session', createdAt: '2026-01-01T00:00:00.000Z' })
    field.store({ id: 'turn:s1:1', content: 'hello', nodeType: 'episode', createdAt: '2026-01-01T00:00:01.000Z' })
    field.store({ id: 'session_summary:s1', content: 'summary', nodeType: 'abstraction' })
    field.connect({ sourceId: 'turn:s1:1', targetId: 'session:s1', edgeType: 'part_of' })
    field.connect({ sourceId: 'session_summary:s1', targetId: 'session:s1', edgeType: 'part_of' })
    const ctx = deps(field)

    expect(await handleReplayRoutes(ctx.deps, {} as any, {} as any, 'GET', '/replay/session/s1')).toBe(true)
    expect(ctx.out.code).toBe(200)
    expect(ctx.out.body.events.map((e: any) => e.id)).toContain('turn:s1:1')

    expect(await handleReplayRoutes(ctx.deps, {} as any, {} as any, 'GET', '/session-summary/s1')).toBe(true)
    expect(ctx.out.body.summary.id).toBe('session_summary:s1')

    field.close()
  })

  it('returns read-only legacy session views', async () => {
    const field = new MnemicField(logger(), ':memory:')
    const session = { id: 'legacy-1', channelId: 'web', senderId: 'user', history: [{ role: 'user', content: 'hi' }], tokenCount: 1, config: { title: 'Legacy' } }
    const ctx = deps(field, [session])

    expect(await handleReplayRoutes(ctx.deps, {} as any, {} as any, 'GET', '/legacy-sessions')).toBe(true)
    expect(ctx.out.body.sessions[0]).toMatchObject({ id: 'legacy-1', title: 'Legacy', historyLength: 1 })

    expect(await handleReplayRoutes(ctx.deps, {} as any, {} as any, 'GET', '/legacy-sessions/legacy-1')).toBe(true)
    expect(ctx.out.body.session).toBe(session)

    field.close()
  })
})
