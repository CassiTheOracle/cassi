/**
 * @cassicore/spine — MnemicField memory backend adapter (plan §3 / brief §2.9).
 *
 * The spine sits at the ohmypi `ctx` boundary, so it hosts the adapter mapping ohmypi's
 * memory-backend surface (`status / search / save`) onto the running MnemicField. The
 * field lives in the mind runtime (plan §4.3), so this adapter PROXIES over the channel's
 * `/v1/memory/*` endpoints. Both ohmypi's built-ins (recall/retain/reflect/memory_edit)
 * and the mind's own ops hit the SAME field (plan §3.2).
 *
 * [VERIFY] Wiring destination: `ctx.memory` on `ExtensionContext` is a READ-ONLY
 * `MemoryRuntimeContext` resolved by ohmypi from its configured `memory.backend` — an
 * extension cannot substitute it in-process. ohmypi's `MemoryBackendId` is a CLOSED
 * union (`"off"|"local"|"hindsight"|"mnemopi"`), so a custom `"mnemic-field"` id is not
 * representable without platform support. This adapter implements the
 * `MemoryRuntimeContext` shape; the `backend` field is the platform-configured id (the
 * caller substitutes the real id at resolution). Wiring MnemicField as the actual backend
 * requires ohmypi's custom-backend registration hook or the P4/P5 cutover routing
 * `ctx.memory` onto the shared field. Default this phase: implement the runtime-context
 * shape; document the resolution hook.
 */

import type {
  MemoryBackendSaveInput,
  MemoryBackendSearchOptions,
  MemoryBackendSearchResult,
  MemoryBackendStatus,
  MemoryRuntimeContext,
} from './oh-my-pi-types.js'

import type { ChannelClient } from './channel/client.js'

/** A `MemoryRuntimeContext`-shaped adapter whose status/search/save proxy the mind runtime field. */
export class MnemicMemoryBackend implements MemoryRuntimeContext {
  constructor(private readonly client: ChannelClient) {}

  async status(): Promise<MemoryBackendStatus> {
    try {
      const s = await this.client.memoryStatus()
      return {
        // The platform-configured backend id (ohmypi honors only its closed union);
        // the running field is always the Cassi mind runtime's MnemicField.
        backend: 'mnemic-field' as never as MemoryBackendStatus['backend'],
        active: true,
        writable: true,
        searchable: true,
        database: s.backend,
        message: 'MnemicField (CassiCore mind runtime)',
      }
    } catch (err) {
      return {
        backend: 'mnemic-field' as never as MemoryBackendStatus['backend'],
        active: false,
        writable: false,
        searchable: false,
        error: String(err),
      }
    }
  }

  async search(query: string, options?: MemoryBackendSearchOptions): Promise<MemoryBackendSearchResult> {
    try {
      const r = await this.client.memorySearch({ query, limit: options?.limit ?? 5 })
      return {
        backend: 'mnemic-field' as never as MemoryBackendSearchResult['backend'],
        query,
        count: r.results.length,
        items: r.results.map(hit => ({ id: hit.id, content: hit.content, score: hit.score })),
      }
    } catch (err) {
      return {
        backend: 'mnemic-field' as never as MemoryBackendSearchResult['backend'],
        query,
        count: 0,
        items: [],
        message: String(err),
      }
    }
  }

  async save(input: string | MemoryBackendSaveInput): Promise<MemoryRuntimeContext['save'] extends (i: string | MemoryBackendSaveInput) => Promise<infer R> ? R : never> {
    const isObj = typeof input === 'object' && input !== null
    const content = isObj ? (input as MemoryBackendSaveInput).content : (input as string)
    try {
      const r = await this.client.memorySave({
        content,
        type: 'fact',
        metadata: isObj ? {
          context: (input as MemoryBackendSaveInput).context,
          source: (input as MemoryBackendSaveInput).source,
          importance: (input as MemoryBackendSaveInput).importance,
        } : undefined,
      })
      return { backend: 'mnemic-field' as never as never, stored: 1, ids: [r.id] } as never
    } catch (err) {
      return { backend: 'mnemic-field' as never as never, stored: 0, message: String(err) } as never
    }
  }
}
