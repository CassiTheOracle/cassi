import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import type { IEventBus, ILogger } from '@cassicore/foundation'
import { MnemicExactStore } from '@cassicore/mnemic-field'
import { describe, expect, it } from 'vitest'

import { RuntimeContextCandidateService } from '../src/context/candidates.js'
import { MnemicMemoryAdapter } from '../src/memory/backend.js'

const logger: ILogger = {
  debug: () => {}, info: () => {}, warn: () => {}, error: () => {},
  child: () => logger,
}
const bus = { emit: async () => {} } as unknown as IEventBus

describe('context compaction restart', () => {
  it('re-evokes exact selected memories without relying on lexical search', async () => {
    const directory = mkdtempSync(join(tmpdir(), 'cassi-context-restart-'))
    const database = join(directory, 'memory.sqlite')

    try {
      const before = new MnemicExactStore(logger, database)
      try {
        before.store({
          id: 'selected-memory',
          content: 'the hidden cobalt procedure uses clockwise turns',
          nodeType: 'fact',
          metadata: { sessionId: 'session-prior' },
        })
        before.store({
          id: 'checkpoint',
          content: 'Cassi context checkpoint session-a:4',
          nodeType: 'session',
          provenance: 'cassi-context-compaction',
          metadata: { sessionId: 'session-a', candidateIds: ['selected-memory'] },
        })
      } finally {
        before.close()
      }

      const after = new MnemicExactStore(logger, database)
      try {
        const service = new RuntimeContextCandidateService({
          memory: new MnemicMemoryAdapter(after),
          bus,
          logger,
          fieldRecall: async request => {
            const address = request.addresses.find(candidate =>
              after.resolveFieldAddress(candidate)?.record.id === 'selected-memory'
            ) ?? null
            return {
              address,
              signal: address ? 1 : 0,
              selectionMargin: address ? 1 : 0,
              availability: address ? 1 : 0,
            }
          },
        })
        try {
          const response = await service.candidates({
            sessionId: 'session-a',
            turnId: 5,
            query: 'lexically unrelated zephyr',
          })

          expect(response.candidates).toEqual([
            expect.objectContaining({
              id: 'selected-memory',
              text: 'the hidden cobalt procedure uses clockwise turns',
            }),
          ])
        } finally {
          service.close()
        }
      } finally {
        after.close()
      }
    } finally {
      rmSync(directory, { recursive: true, force: true })
    }
  })
})
