import { CONTEXT_SETTINGS } from '@cassicore/foundation'

import { assembleContext } from './context-assembler.js'

import type { IExecutionBackend } from '@cassicore/foundation'
import type { IMemory } from '@cassicore/foundation'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { ISessionManager } from '@cassicore/foundation'
import type { TurnPipeline } from '../turn-pipeline.js'



export interface ContextManagerOpts {
  enabled?: boolean
  syncIntervalMs?: number
  defaultCharBudget?: number
}

export interface EffectiveContextResult {
  assembled: Awaited<ReturnType<typeof assembleContext>>
  globalContext?: unknown
  merged: string
}

/**
 * @dep callers: createIntelligence (core/intelligence/index.ts), createTestPipeline (tests/run-compaction.test.ts)
 * @dep module: Tests
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createContextManager(logger: ILogger, memory?: IMemory, cfg?: ContextManagerOpts) {
  const name = 'context-manager'
  const priority = 85

  let _memory: IMemory | undefined = memory
  let _sessions: ISessionManager | undefined = undefined
  let _pipeline: TurnPipeline | undefined = undefined
  let _bus: IEventBus | undefined = undefined
  let _executionBackend: IExecutionBackend | undefined = undefined
  let _syncTimer: ReturnType<typeof setInterval> | null = null
  let _syncInProgress = false

  // Per-session debounce for turn:end triggered syncs to prevent sync storms
  const _syncDebounce = new Map<string, ReturnType<typeof setTimeout>>()
  const SYNC_DEBOUNCE_MS = 5_000  // Batch rapid turns into one sync per 5 seconds

  // Track sessions that have had activity since last periodic sync.
  // Only these sessions need re-syncing in syncAll() to avoid redundant work.
  const _dirtySessions = new Set<string>()

  // Last fingerprint per session to skip unchanged content in syncOne()
  const _lastSyncFingerprint = new Map<string, string>()

  // Lightweight in-memory cache and inflight promise map to avoid repeated heavy assembly
  const _inflight = new Map<string, Promise<EffectiveContextResult>>()
  const _cache = new Map<string, { merged: string; assembled?: Awaited<ReturnType<typeof assembleContext>>; ts: number }>()
  const CACHE_TTL_MS = Number(process.env.CONTEXT_MANAGER_CACHE_TTL_MS || '5000') || 5000

  // Fingerprint helper for deduplication
  function fingerprint(s: string) {
    try {
      // dynamic require to keep top-level import style consistent with dist build
      const { createHash } = require('node:crypto')
      return createHash('sha256').update(String(s)).digest('hex').slice(0, 10)
    } catch { return String(s).slice(0, 10) }
  }

  const config: ContextManagerOpts = {
    enabled: cfg?.enabled ?? true,
    syncIntervalMs: cfg?.syncIntervalMs ?? CONTEXT_SETTINGS.contextRefreshIntervalMs,
    defaultCharBudget: cfg?.defaultCharBudget ?? CONTEXT_SETTINGS.contextManagerCharBudget,
  }

  function keyForSession(sessionId: string) {
    return `context:global:${sessionId}`
  }

  function cognitiveKeyForSession(sessionId: string) {
    return `context:cognitive:${sessionId}`
  }

  async function fetchGlobal(sessionId: string) {
    if (!_memory) return undefined
    try {
      return await _memory.kv_get(keyForSession(sessionId))
    } catch (err) {
      logger.warn('failed to fetch global context', { sessionId, error: String(err) })
      return undefined
    }
  }

  /** Fetch persisted cognitive signals for a session (from ThoughtObserver) */
  async function fetchCognitiveSignals(sessionId: string): Promise<any[] | undefined> {
    if (!_memory) return undefined
    try {
      const data = await _memory.kv_get(cognitiveKeyForSession(sessionId))
      if (data && typeof data === 'object' && Array.isArray((data as any).signals)) {
        return (data as any).signals
      }
      return undefined
    } catch {
      return undefined
    }
  }

  async function getPersistedCognitiveSignals(sessionId: string): Promise<Array<{ kind: string; text: string; confidence: number; extractedAt?: number }>> {
    return (await fetchCognitiveSignals(sessionId)) ?? []
  }

  /**
   * Merge cognitive signals into the session's persisted cognitive context.
   * Used by ThoughtObserver to persist high-confidence signals extracted from
   * the thinking stream. Uses a separate KV key from global context to avoid
   * interference with the syncOne() flow.
   */
  async function mergeCognitiveSignals(
    sessionId: string,
    newSignals: Array<{ kind: string; text: string; confidence: number; extractedAt?: number }>,
  ): Promise<void> {
    if (!_memory) return
    const MAX_PERSISTED = 15

    try {
      const existing = await fetchCognitiveSignals(sessionId) ?? []

      // Dedup by kind + first 60 chars of text
      const seen = new Set(existing.map((s: any) => `${s.kind}::${String(s.text ?? '').slice(0, 60).toLowerCase()}`))
      const novel = newSignals.filter(s => !seen.has(`${s.kind}::${s.text.slice(0, 60).toLowerCase()}`))

      if (novel.length === 0) return

      // Keep the latest N signals, newest first
      const merged = [...novel.map(s => ({ ...s, extractedAt: s.extractedAt ?? Date.now() })), ...existing]
        .slice(0, MAX_PERSISTED)

      await _memory.kv_set(cognitiveKeyForSession(sessionId), {
        signals: merged,
        updatedAt: Date.now(),
      })

      logger.debug?.('merged cognitive signals', {
        sessionId: sessionId.slice(-8),
        newCount: novel.length,
        totalCount: merged.length,
      })
    } catch (err) {
      logger.debug?.('failed to merge cognitive signals', {
        sessionId: sessionId.slice(-8),
        error: String(err),
      })
    }
  }

  function mergeContexts(assembled: Awaited<ReturnType<typeof assembleContext>>, globalCtx: any, charBudget?: number, cognitiveSignals?: any[]) {
    const budgetNumber: number = typeof charBudget === 'number' ? charBudget : (config.defaultCharBudget ?? 50000)
    const parts: string[] = []

    // Include cognitive signals from ThoughtObserver if available
    if (cognitiveSignals && cognitiveSignals.length > 0) {
      try {
        const formatted = cognitiveSignals
          .map((s: any) => {
            const prefix = (s.kind ?? 'insight').toUpperCase().replace('_', ' ')
            const conf = typeof s.confidence === 'number' ? ` (${(s.confidence * 100).toFixed(0)}%)` : ''
            return `  [${prefix}]${conf} ${s.text ?? ''}`
          })
          .join('\n')
        parts.push(`COGNITIVE OBSERVATIONS (from thinking analysis):\n${formatted}`)
      } catch {
        // best-effort
      }
    }

    if (globalCtx) {
      try {
        // Fix: Extract summary from nested global context to prevent recursion
        let gtxt: string
        if (typeof globalCtx === 'string') {
          gtxt = globalCtx
        } else if (globalCtx && typeof globalCtx === 'object') {
          // If it has a summary field, use that directly (it's already merged)
          if (globalCtx.summary && typeof globalCtx.summary === 'string') {
            // Check if summary itself contains nested GLOBAL CONTEXT
            const summary = globalCtx.summary
            if (summary.startsWith('GLOBAL CONTEXT:')) {
              // Extract just the inner content
              const match = summary.match(/GLOBAL CONTEXT:\s*({[\s\S]*}|.*)/)
              gtxt = match ? match[1] : summary
            } else {
              gtxt = summary
            }
          } else {
            gtxt = JSON.stringify(globalCtx, null, 2)
          }
        } else {
          gtxt = String(globalCtx)
        }
        // Prevent recursive nesting - don't add GLOBAL CONTEXT prefix if already present
        const content = gtxt.startsWith('GLOBAL CONTEXT:') ? gtxt : `GLOBAL CONTEXT:\n${  gtxt}`
        parts.push(content.slice(0, Math.max(0, Math.floor(budgetNumber * 0.25))))
      } catch {
        parts.push('GLOBAL CONTEXT: (unserializable)')
      }
    }

    if (assembled.sessionSummary) {
      parts.push(`SESSION SUMMARY:\n${  assembled.sessionSummary.slice(0, Math.max(0, Math.floor(budgetNumber * 0.25)))}`)
    } else if (assembled.sessionHistory && assembled.sessionHistory.length > 0) {
      const hist = assembled.sessionHistory.slice(-6).map((s) => s.replace(/\n+/g, ' ').slice(0, 800)).join('\n---\n')
      parts.push(`PREVIOUS CONTEXT (older than recent messages):\n${  hist}`)
    }

    if (assembled.recentMemories && assembled.recentMemories.length > 0) {
      const mems = assembled.recentMemories.slice(0, 6).map(m => `- ${  m.replace(/\n+/g, ' ').slice(0, 400)}`).join('\n')
      parts.push(`RECENT MEMORIES:\n${  mems}`)
    }

    if (assembled.taskGuide) {
      parts.push(`TASK GUIDE:\n${  assembled.taskGuide.slice(0, Math.max(0, Math.floor(budgetNumber * 0.15)))}`)
    }

    if (assembled.availableTools && assembled.availableTools.length > 0) {
      parts.push(`AVAILABLE_TOOLS: ${  assembled.availableTools.join(', ').slice(0, 200)}`)
    }

    // Files (small snippets)
    if (assembled.files && assembled.files.length > 0) {
      const ftxt = assembled.files.slice(0, 3).map(f => `FILE ${f.path}: ${f.content.replace(/\n+/g, ' ').slice(0, 300)}`).join('\n')
      parts.push(`FILES:\n${  ftxt}`)
    }

    let merged = parts.join('\n\n')
    if (merged.length > budgetNumber) merged = `${merged.slice(0, budgetNumber)  }\n\n// ...truncated`
    return merged
  }

  async function getEffectiveContext(sessionId: string, opts: { query?: string, includeHistory?: boolean, memoryLimit?: number, files?: string[], extra?: string, charBudget?: number } = {}): Promise<EffectiveContextResult> {
    let mnemicField: import('@cassicore/mnemic-field').MnemicField | undefined
    try {
      mnemicField = (_executionBackend as any)?.daemon?.__mnemicField
        ?? (_bus as any)?.daemon?.__mnemicField
        ?? undefined
    } catch {
      mnemicField = undefined
    }

    const assembled = await assembleContext({ memory: _memory, mnemicField, sessionManager: _sessions, getPipeline: () => _pipeline, logger }, {
      sessionId,
      query: opts.query,
      includeHistory: opts.includeHistory,
      memoryLimit: opts.memoryLimit,
      files: opts.files,
      extra: opts.extra,
      charBudget: opts.charBudget ?? config.defaultCharBudget,
    })

    const globalCtx = await fetchGlobal(sessionId)
    const cogSignals = await fetchCognitiveSignals(sessionId)
    const merged = mergeContexts(assembled, globalCtx, opts.charBudget, cogSignals ?? undefined)
    return { assembled, globalContext: globalCtx, merged }
  }

  async function setGlobalContext(sessionId: string, ctx: unknown) {
    if (!_memory) throw new Error('memory not wired')
    try {
      await _memory.kv_set(keyForSession(sessionId), ctx)
      logger.info('global context updated', { sessionId })
      await _bus?.emit?.({ type: 'context-manager:global-updated', sessionId, ctx } as any)
    } catch (err) {
      logger.warn('failed to set global context', { sessionId, error: String(err) })
      throw err
    }
  }

  async function syncOne(sessionId: string) {
    try {
      const res = await getEffectiveContext(sessionId, { charBudget: config.defaultCharBudget || 50000 })
      const summary = res.assembled.taskGuide || res.assembled.sessionSummary || res.merged.slice(0, 800)

      // Skip KV write + event emission if content hasn't changed since last sync
      const fp = fingerprint(summary)
      if (_lastSyncFingerprint.get(sessionId) === fp) {
        logger.debug?.('syncOne skipped (unchanged)', { sessionId })
        return
      }
      _lastSyncFingerprint.set(sessionId, fp)

      const payload = { summary, updatedAt: Date.now() }
      await _memory?.kv_set(keyForSession(sessionId), payload)
      logger.debug?.('synced session context', { sessionId })
      await _bus?.emit?.({ type: 'context-manager:sync', sessionId, payload } as any)


    } catch (err) {
      logger.warn?.('syncOne failed', { sessionId, error: String(err) })
    }
  }

  async function syncAll() {
    if (_syncInProgress) return
    if (!_sessions) return
    if (!_memory) return
    _syncInProgress = true
    try {
      // Only sync sessions that have been marked dirty (had turn:end activity
      // since the daemon started). On first run, _dirtySessions is empty —
      // we intentionally skip syncing all stale sessions to avoid flooding
      // the event loop when thousands of sessions exist in the database.
      // Stale sessions will be lazily synced when they become active again.
      const toSync = _sessions.list().filter(s => _dirtySessions.has(s.id))

      if (toSync.length > 0) {
        logger.debug?.('syncAll: syncing dirty sessions', { count: toSync.length })
      }

      // Clear dirty set before syncing — new activity during sync will re-dirty
      _dirtySessions.clear()

      for (const s of toSync) {
        try {
          await syncOne(s.id)
        } catch (err) {
          logger.warn?.('failed syncing session', { sessionId: s.id, error: String(err) })
        }
      }
    } catch (err) {
      logger.warn?.('syncAll failed', { error: String(err) })
    } finally {
      _syncInProgress = false
    }
  }

  function start(opts?: { intervalMs?: number }) {
    const interval = opts?.intervalMs ?? config.syncIntervalMs ?? 60_000
    if (_syncTimer) clearInterval(_syncTimer as any)
    _syncTimer = setInterval(async () => {
      try { await syncAll() } catch (err) { logger.warn('periodic sync failed', { error: String(err) }) }
    }, interval)
    try { (_syncTimer as any).unref?.() } catch {}
    // run an initial sync in background
    void syncAll()
    logger.info('started periodic sync', { intervalMs: interval })
  }

  function stop() {
    if (_syncTimer) {
      clearInterval(_syncTimer as any)
      _syncTimer = null
    }
    // Clear all pending debounce timers and tracking state
    for (const timer of _syncDebounce.values()) {
      clearTimeout(timer)
    }
    _syncDebounce.clear()
    _dirtySessions.clear()
    _lastSyncFingerprint.clear()
    logger.info('stopped')
  }

  function onEventBus(bus: IEventBus) {
    _bus = bus
    // React to turn:end events with per-session debounce to prevent sync storms.
    // Rapid successive turns batch into a single sync after SYNC_DEBOUNCE_MS quiet period.
    try {
      bus.on('turn:end', (e: any) => {
        try {
          const sid = (e as any).sessionId as string | undefined
          if (!sid) return
          // Mark session as dirty so syncAll will include it
          _dirtySessions.add(sid)
          // Clear any pending sync for this session and schedule a new one
          const existing = _syncDebounce.get(sid)
          if (existing) clearTimeout(existing)
          const timer = setTimeout(() => {
            _syncDebounce.delete(sid)
            void syncOne(sid)
          }, SYNC_DEBOUNCE_MS)
          try { (timer as any).unref?.() } catch {}
          _syncDebounce.set(sid, timer)
        } catch (err) {
          logger.warn('turn:end handler failed', { error: String(err) })
        }
      })
      // Clean up debounce timers and tracking when sessions end
      bus.on('session:ended', (e: any) => {
        const sid = (e as any).sessionId
        if (sid) {
          const timer = _syncDebounce.get(sid)
          if (timer) {
            clearTimeout(timer)
            _syncDebounce.delete(sid)
          }
          _dirtySessions.delete(sid)
          _lastSyncFingerprint.delete(sid)
        }
      })
    } catch (err) {
      logger.warn('failed to attach to event bus', { error: String(err) })
    }
  }

  function setMemory(mem: IMemory) { _memory = mem }
  function setSessions(sessions: ISessionManager) { _sessions = sessions }
  function setExecutionBackend(backend: IExecutionBackend) {
    _executionBackend = backend
    logger.info('wired to execution backend', { backendName: backend.name })
  }
  function setPipeline(p: TurnPipeline) {
    _pipeline = p
    try {
      // Middleware that injects an assembled/merged context as a SYSTEM block and
      // also appends it to ctx.opts.systemPrompt so providers see it. Uses a
      // cheap fast-path (in-memory cache / periodic global summary) and falls
      // back to the heavier assembleContext only when needed.
      const mw = async (ctx: any, next: () => Promise<any>) => {
        try {
          const md = (ctx?.inbound && ctx.inbound.metadata) ? ctx.inbound.metadata as any : {}
          const opts: any = {
            // Fall back to inbound content as the semantic recall query when no explicit query is set
            query: md.contextQuery ?? md.query ?? (typeof ctx?.inbound?.content === 'string' ? ctx.inbound.content : undefined),
            includeHistory: typeof md.contextIncludeHistory === 'boolean' ? md.contextIncludeHistory : (typeof md.includeHistory === 'boolean' ? md.includeHistory : undefined),
            memoryLimit: md.contextMemoryLimit ?? md.memoryLimit,
            files: md.contextFiles ?? md.files,
            extra: md.contextExtra ?? md.extra,
            charBudget: typeof md.contextCharBudget === 'number' ? md.contextCharBudget : (typeof md.charBudget === 'number' ? md.charBudget : undefined),
          }

          const charBudget = opts.charBudget ?? config.defaultCharBudget
          const key = `${String(ctx.session?.id)}::${charBudget}::${opts.includeHistory?1:0}::${(opts.files || []).join(',')}`

          // 1) In-memory cache fast-path
          const cached = _cache.get(key)
          if (cached && (Date.now() - (cached.ts || 0)) < CACHE_TTL_MS) {
            let merged = cached.merged
            const fp = fingerprint(merged)
            const marker = `[CTX-FP:${fp}]`
            // Ensure marker is present in the injected text for future dedupe
            if (!merged.includes(marker)) merged = `${merged}\n${marker}`

            if (merged && !ctx.messages.find((m: any) => m.role === 'system' && typeof m.content === 'string' && m.content.includes(marker))) {
              const sysIdx = ctx.messages.findIndex((m: any) => m.role === 'system')
              const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0
              ctx.messages = [
                ...ctx.messages.slice(0, insertAt),
                { role: 'system', content: merged },
                ...ctx.messages.slice(insertAt),
              ]
              ctx.opts = { ...ctx.opts, systemPrompt: (`${ctx.opts.systemPrompt || ''  }\n\n${  merged}`).trim() }
            }
            return next()
          }

          // 2) Try periodic global summary stored in memory (cheap)
          let globalCtx: any = undefined
          try { globalCtx = await fetchGlobal(ctx.session.id) } catch {}

          if (globalCtx && !md.contextForceFull) {
            let merged = ''
            try {
              if (typeof globalCtx === 'string') merged = String(globalCtx)
              else if (globalCtx && typeof globalCtx === 'object' && (globalCtx as any).summary) merged = String((globalCtx as any).summary)
              else merged = JSON.stringify(globalCtx)
            } catch {}

            if (merged) {
              const max = charBudget || config.defaultCharBudget || 50000
              if (merged.length > max) merged = `${merged.slice(0, max)  }\n\n// ...truncated`
              const wrapped = `GLOBAL CONTEXT:\n${  merged}`

              const fp = fingerprint(wrapped)
              const marker = `[CTX-FP:${fp}]`
              let wrappedWithMarker = wrapped
              if (!wrappedWithMarker.includes(marker)) wrappedWithMarker = `${wrappedWithMarker}\n${marker}`

              if (!ctx.messages.find((m: any) => m.role === 'system' && typeof m.content === 'string' && m.content.includes(marker))) {
                const sysIdx = ctx.messages.findIndex((m: any) => m.role === 'system')
                const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0
                ctx.messages = [
                  ...ctx.messages.slice(0, insertAt),
                  { role: 'system', content: wrappedWithMarker },
                  ...ctx.messages.slice(insertAt),
                ]
                ctx.opts = { ...ctx.opts, systemPrompt: (`${ctx.opts.systemPrompt || ''  }\n\n${  wrappedWithMarker}`).trim() }
              }

              try { _cache.set(key, { merged: wrappedWithMarker, assembled: undefined, ts: Date.now() }) } catch {}
              return next()
            }
          }

          // 3) Full assembly (dedupe concurrent in-flight assemblies)
          if (_inflight.has(key)) {
            try {
              const res = await _inflight.get(key)!
              if (res && res.merged) {
                let merged = res.merged
                const fp = fingerprint(merged)
                const marker = `[CTX-FP:${fp}]`
                if (!merged.includes(marker)) merged = `${merged}\n${marker}`

                if (!ctx.messages.find((m: any) => m.role === 'system' && typeof m.content === 'string' && m.content.includes(marker))) {
                  const sysIdx = ctx.messages.findIndex((m: any) => m.role === 'system')
                  const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0
                  ctx.messages = [
                    ...ctx.messages.slice(0, insertAt),
                    { role: 'system', content: merged },
                    ...ctx.messages.slice(insertAt),
                  ]
                  ctx.opts = { ...ctx.opts, systemPrompt: (`${ctx.opts.systemPrompt || ''  }\n\n${  merged}`).trim() }
                }
              }
            } catch (e) { /* best-effort */ }
            return next()
          }

          const inflightP = (async () => {
            try {
              const res = await getEffectiveContext(ctx.session.id, {
                query: opts.query,
                includeHistory: opts.includeHistory,
                memoryLimit: opts.memoryLimit,
                files: opts.files,
                extra: opts.extra,
                charBudget: opts.charBudget ?? config.defaultCharBudget,
              })
              try {
                let mm = res.merged || ''
                const fp2 = fingerprint(mm)
                const marker2 = `[CTX-FP:${fp2}]`
                if (!mm.includes(marker2)) mm = `${mm}\n${marker2}`
                _cache.set(key, { merged: mm, assembled: res.assembled, ts: Date.now() })
              } catch {}
              return res
            } finally {
              _inflight.delete(key)
            }
          })()

          _inflight.set(key, inflightP)
          const res = await inflightP

          if (res && res.merged) {
            let merged = res.merged
            const fp = fingerprint(merged)
            const marker = `[CTX-FP:${fp}]`
            if (!merged.includes(marker)) merged = `${merged}\n${marker}`

            if (!ctx.messages.find((m: any) => m.role === 'system' && typeof m.content === 'string' && m.content.includes(marker))) {
              const sysIdx = ctx.messages.findIndex((m: any) => m.role === 'system')
              const insertAt = sysIdx >= 0 ? sysIdx + 1 : 0
              ctx.messages = [
                ...ctx.messages.slice(0, insertAt),
                { role: 'system', content: merged },
                ...ctx.messages.slice(insertAt),
              ]
              ctx.opts = { ...ctx.opts, systemPrompt: (`${ctx.opts.systemPrompt || ''  }\n\n${  merged}`).trim() }
            }
          }
        } catch (err) {
          logger.warn?.('middleware failed', { error: String(err) })
        }
        return next()
      }

      // Insert middleware into pipeline at a sensible position:
      // - Prefer after systemPromptMiddleware when present
      // - Otherwise before contextWindowMiddleware
      // - Fallback to prepend
      try {
        if (typeof (p as any).insertMiddlewareAt === 'function') {
          const arr = (p as any).middlewares as any[] || []
          let insertAt = 0
          const sysIdx = arr.findIndex((m: any) => m && m.name === 'systemPromptMiddleware')
          if (sysIdx >= 0) insertAt = sysIdx + 1
          else {
            const ctxIdx = arr.findIndex((m: any) => m && m.name === 'contextWindowMiddleware')
            insertAt = ctxIdx >= 0 ? ctxIdx : 0
          }
          ;(p as any).insertMiddlewareAt(insertAt, mw)
        } else if (typeof (p as any).prependMiddleware === 'function') {
          ;(p as any).prependMiddleware(mw)
        } else if ((p as any).middlewares && Array.isArray((p as any).middlewares)) {
          (p as any).middlewares.unshift(mw)
        }
      } catch (err) {
        logger.warn?.('failed to inject middleware into pipeline', { error: String(err) })
      }
    } catch (err) {
      logger.warn?.('setPipeline failed', { error: String(err) })
    }
  }

  async function manualSync(sessionId: string) { return syncOne(sessionId) }

  function getStats() {
    return { syncTimerActive: !!_syncTimer, syncInProgress: _syncInProgress }
  }

  async function cleanup() { stop() }

  return {
    name,
    priority,
    onEvent: async (e: any) => { /* optional handler */ },
    setMemory,
    setSessions,
    setExecutionBackend,
    setPipeline,
    onEventBus,
    start,
    stop,
    manualSync,
    getEffectiveContext,
    setGlobalContext,
    mergeCognitiveSignals,
    getPersistedCognitiveSignals,
    mergeContexts,
    getStats,
    cleanup,
  }
}
