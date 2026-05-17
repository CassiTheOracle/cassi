import { AutonomousAgentLoop } from '../intelligence/autonomous-loop.js'
import { createExecutionBackend } from '../intelligence/execution-backends/index.js'
import { ScoutModule } from '../scout/index.js'
// REMOVED: registerTeamTools — team-coordinator.ts deleted with TriadTeam
import { ModuleSessionRegistry } from '../intelligence/module-session-registry.js'
import { ModuleSessionCompactor } from '../intelligence/module-session-compactor.js'

// PinealInjectionSource deprecated — Thalamus now owns Pineal injection via PinealAssembler
import { PinealAssembler } from '../intelligence/pineal/assembler.js'
import type { PinealModule } from '../intelligence/pineal/index.js'

import type { IEventBus, IConfig, ILogger, IPluginHost } from '../../types/interfaces.js'
import type { IntelligenceLayer } from '../intelligence/index.js'
import type { TurnPipeline } from '../turn-pipeline.js'
import type { ToolExecutor } from '../tools/executor.js'
import type { ToolRegistry } from '../tools/registry.js'
import type { SessionStore } from '../session-store.js'
import type { SessionDigestStore } from '../intelligence/session-digest.js'
import type { ContextDistiller } from '../intelligence/context-distiller.js'
import type { ExecutionBackendType, OpenCodeBackendConfig } from '../../types/execution-backend.js'
import type { SessionManager } from '../session-manager.js'
import type { IProvider } from '../../types/runtime.js'
import { DmnObserver, type DmnObserverLLM } from '../intelligence/dmn/observer.js'

function extractObservation(raw: string): string {
  const re = /<observation>[\s\S]*?<\/observation>/i
  const m = raw.match(re)
  return m ? m[0] : ''
}

export interface IntelligencePostBootDeps {
  bus: IEventBus
  config: IConfig
  logger: ILogger
  intelligence: IntelligenceLayer
  pipeline: TurnPipeline
  sessionPipeline?: {
    processTurn(
      sessionId: string,
      content: string,
      options?: Record<string, unknown>,
    ): Promise<{ response: string; sessionId: string; model?: string; tokensUsed?: number; durationMs?: number }>
  }
  sessions: SessionManager
  sessionStore: SessionStore
  sessionDigestStore?: SessionDigestStore
  autonomousLoop?: AutonomousAgentLoop
  toolRegistry: ToolRegistry
  toolExecutor: ToolExecutor
  pluginHost?: IPluginHost
  compactionProvider?: IProvider
  modelPool?: any
  contextDistiller?: ContextDistiller
  handleFactory?: (config: { tier: string; purpose: string; sessionId: string }) => Promise<any>
}

/**
 * @dep flows: BootIntelligencePostPipeline → CalculatePercentUsed (1/8), BootIntelligencePostPipeline → GetLimit (1/8), BootIntelligencePostPipeline → IsVisibleToAgent (1/7) [+8]
 * @dep module: Unknown
 * @dep risk: CRITICAL | 0 callers, 11 flows, 1 module
 */

export async function bootIntelligencePostPipeline(deps: IntelligencePostBootDeps): Promise<AutonomousAgentLoop | undefined> {
  const {
    bus,
    config,
    logger,
    intelligence,
    pipeline,
    sessions,
    sessionStore,
    sessionDigestStore,
    toolRegistry,
    toolExecutor,
    compactionProvider,
    contextDistiller,
  } = deps

  // REMOVED: InjectionAggregator wiring — deprecated. Now uses Thalamus/GlobalWorkspace.

  try {
  if (intelligence.globalWorkspace) {
      const useGwt = config?.get?.('intelligence.workspace.enabled') === true
      pipeline.setGlobalWorkspace(intelligence.globalWorkspace, useGwt)
      logger.info('GlobalWorkspace wired to pipeline', { enabled: useGwt })

      // Radiance Loop: bidirectional workspace feedback with surprise-gated observer
      const radianceEnabled = config?.get?.('intelligence.workspace.radiance.enabled') === true
      if (radianceEnabled && useGwt) {
        const { RadianceLoop } = await import('../intelligence/workspace/radiance-loop.js')
        const radianceLoop = new RadianceLoop(intelligence.globalWorkspace, logger, {
          enabled: true,
          warmupCycles: 10,
          surpriseThreshold: 0.3,
        })
        if (intelligence.cortex) radianceLoop.setCortex(intelligence.cortex)
        if (bus) radianceLoop.setEventBus(bus)

        if (deps.handleFactory) {
          radianceLoop.setHandleFactory(deps.handleFactory, toolExecutor, toolRegistry, bus)
          logger.info('RadianceLoop observer wired with model handle factory')
        }

        pipeline.setRadianceLoop(radianceLoop)

        // Event-bus trigger: the SessionPipeline doesn't call RadianceLoop directly
        // (only the legacy TurnPipeline does), so we also listen on turn:end.
        // The cycle is async fire-and-forget — observations feed the NEXT turn.
        bus.on('turn:end', () => {
          queueMicrotask(() => {
            radianceLoop.cycle().catch(() => { /* non-critical */ })
          })
        })

        logger.info('RadianceLoop wired to pipeline and event bus')
      }
    }

    // Pineal — set on intelligence layer for other modules to access
    const pineal = intelligence.registry.get('pineal') as PinealModule | undefined
    if (pineal) {
      intelligence.pineal = pineal
    }
  } catch (err) {
    logger.warn(`GlobalWorkspace/RadianceLoop wiring failed: ${String(err)}`)
  }

  try {
    intelligence.thoughtObserver.onEventBus(bus)
    logger.info('ThoughtObserver wired to event bus')
  } catch (err) {
    logger.warn(`Failed to wire ThoughtObserver: ${String(err)}`)
  }

  // DMN — Default Mode Network. Autonomous AGOP tick loop per session;
  // turn boundaries are not the trigger.
  if (intelligence.dmn?.enabled) {
    try {
      // Substrate sampler: SessionManager.get is the in-memory accessor
      // — avoids an SQLite hit + JSON parse on every tick.
      intelligence.dmn.setActivitySnapshotProvider((sessionId) => {
        const session = sessions.get(sessionId)
        if (!session) return null
        return { historyLength: session.history?.length ?? 0 }
      })

      const HISTORY_WINDOW = 24
      const mnemicField = (intelligence as any).__mnemicField as {
        getCortex(): { getEngramsBySessionId(sessionId: string, limit?: number): any[] }
        buildShadowContext(): string | null
        getHarmony(): number
      } | undefined

      const fetchSessionEngrams = (sessionId: string): any[] => {
        if (!mnemicField) return []
        try {
          const engrams = mnemicField.getCortex().getEngramsBySessionId(sessionId, HISTORY_WINDOW)
          if (!engrams || engrams.length === 0) return []
          return engrams.map(e => ({
            id: e.id,
            content: e.content,
            nodeType: e.nodeType,
            tags: e.tags,
            potentiation: e.potentiation,
            provenance: e.provenance,
          }))
        } catch {
          return []
        }
      }

      // Per-session DMN observers (two-layer: scout + synthesis)
      const dmnObservers = new Map<string, DmnObserver>()

      // LLM adapter wrapping the model pool for observer synthesis.
      const observerLLM: DmnObserverLLM = {
        async complete(opts) {
          const handle = await deps.modelPool?.acquire('dmn-observer', undefined, '')
          if (!handle) throw new Error('ModelPool unavailable for DMN observer')
          try {
            const messages = [{ role: 'user' as const, content: opts.prompt }]
            const result = await handle.complete(messages as any, {
              maxTokens: opts.maxTokens,
              thinking: opts.thinking ?? 'none',
            } as any)
            return { content: result?.content ?? '' }
          } finally {
            handle.release?.()
          }
        },
      }

      intelligence.dmn.setOnFire(async (reason, sessionId) => {
        try {
          const session = sessions.get(sessionId)
          const history = session?.history ?? []

          const recent = history.slice(-HISTORY_WINDOW)
          let observationPrompt: string | null = null
          const recentHistory: unknown[] = []

          if (session && recent.length > 0) {
            const lastUser = [...recent].reverse().find(m => (m as any).role === 'user')
            const userMessage = (() => {
              const c = (lastUser as any)?.content
              if (typeof c === 'string') return c
              if (Array.isArray(c)) {
                return c.map((b: any) => b?.text ?? '').filter(Boolean).join('\n')
              }
              return ''
            })()
            if (!userMessage) return null

            const recentAssistantMessages = recent
              .filter(m => (m as any).role === 'assistant')
              .slice(-4)
            const assistantOutput = recentAssistantMessages
              .map(m => {
                const c = (m as any).content
                if (typeof c === 'string') return c.slice(0, 600)
                if (Array.isArray(c)) {
                  return c
                    .map((b: any) => {
                      if (b.type === 'tool_use') return `[Tool call: ${b.name}(${JSON.stringify(b.input).slice(0, 120)})]`
                      if (b.type === 'tool_result') return `[Tool result: ${(b.content ?? '').slice(0, 200)}${(b as any).isError ? ' ERROR' : ''}]`
                      return (b.text ?? '').slice(0, 300)
                    })
                    .filter(Boolean)
                    .join('\n')
                    .slice(0, 800)
                }
                return ''
              })
              .filter(Boolean)
              .join('\n---\n')
              .slice(0, 2000)

            const toolCallsInWindow = recent
              .flatMap(m => {
                const c = (m as any).content
                if (Array.isArray(c)) return c.filter((b: any) => b.type === 'tool_use')
                return []
              })
            const toolSummary = toolCallsInWindow.length > 0
              ? `\n${toolCallsInWindow.length} tool calls in window: ${toolCallsInWindow.map((t: any) => t.name).join(', ')}`
              : ''

            observationPrompt = [
              `User message: ${userMessage.slice(0, 1000)}`,
              assistantOutput ? `\nAssistant recent output:\n${assistantOutput}` : '',
              toolSummary,
              `\nSession engram context: ${fetchSessionEngrams(sessionId).map((e: any) => `[${e.nodeType}] ${e.content.slice(0, 200)}`).join('\n').slice(0, 1500) || '(none yet)'}`,
            ].join('\n')

            recentHistory.push(...recent as unknown[])
          } else {
            const ext = intelligence.dmn!.getExternalSnapshot(sessionId)
            if (!ext) return null

            const parts: string[] = []
            if (ext.lastUserMessage) {
              parts.push(`User message: ${ext.lastUserMessage.slice(0, 1000)}`)
            }
            if (ext.lastAssistantText) {
              parts.push(`\nAssistant recent output:\n${ext.lastAssistantText.slice(0, 2000)}`)
            }
            if (ext.toolCallCount != null && ext.toolCallCount > 0) {
              parts.push(`\nTool calls tracked: ${ext.toolCallCount}`)
            }
            observationPrompt = parts.join('\n') || null
          }

          // Inject shadow context (Phase 0: Yin/Yang Harmony)
          // Builds awareness of blind spots and field balance for the DMN observer
          if (observationPrompt && mnemicField) {
            try {
              const shadowCtx = mnemicField.buildShadowContext()
              if (shadowCtx) {
                observationPrompt += '\n\n' + shadowCtx
              }
            } catch { /* never block observer fire for shadow context failures */ }
          }

          if (!observationPrompt) return null

          let observer = dmnObservers.get(sessionId)
          if (!observer) {
            observer = new DmnObserver({
              sessionId,
              logger,
              llm: observerLLM,
              eventBus: bus as any,
            })
            dmnObservers.set(sessionId, observer)
          }

          return await observer.fire(String(reason), observationPrompt)
        } catch (err) {
          logger.debug('DMN onFire failed', { error: String(err), sessionId })
          return null
        }
      })

      bus.on('session:created' as any, (e: any) => {
        try {
          const sessionId = e?.sessionId
          const channelId: string | undefined = e?.channelId
          if (!sessionId) return
          if (sessionId.startsWith('module:')) return
          if (channelId && !channelId.startsWith('channel:')) return
          intelligence.dmn!.attachSession(sessionId)
        } catch (err) {
          logger.debug('DMN session:created handler error', { error: String(err) })
        }
      })

      bus.on('session:ended' as any, (e: any) => {
        try {
          const sessionId = e?.sessionId
          if (sessionId) {
            void intelligence.dmn!.detachSession(sessionId)
          }
        } catch (err) {
          logger.debug('DMN session:ended handler error', { error: String(err) })
        }
      })

      logger.info('DMN wired (AGOP tick loop, session:created, session:ended)')
    } catch (err) {
      logger.warn(`Failed to wire DMN: ${String(err)}`)
    }
  }

  try {
    if (intelligence.locusBridge) {
      intelligence.locusBridge.onEventBus(bus)
      logger.info('LocusBridge wired to event bus')
    }
  } catch (err) {
    logger.warn(`Failed to wire LocusBridge to event bus: ${String(err)}`)
  }

  try {
    intelligence.cognitiveBridge.onEventBus(bus)
    intelligence.cognitiveBridge.setSessionManager(sessions)
    logger.info('CognitiveBridge wired to event bus + session manager')
  } catch (err) {
    logger.warn(`Failed to wire CognitiveBridge: ${String(err)}`)
  }

  // Wire Heart Module
  try {
    const heart = intelligence.heart as any
    if (heart) {
      heart.wire({
        pipeline,
        sessionPipeline: deps.sessionPipeline,
        sessionManager: sessions,
        pluginHost: (deps as any).pluginHost,
        workspaceRoot: process.cwd(),
      })
      await heart.init()
      await heart.start()
      logger.info('Heart module wired and started')
    }
  } catch (err) {
    logger.warn(`Failed to wire Heart module: ${String(err)}`)
  }

  // Start Meditation controller (idle-check loop + MeditationStore)
  try {
    const meditation = intelligence.meditation
    if (meditation && typeof (meditation as any).start === 'function') {
      await (meditation as any).start()
      logger.info('Meditation controller started')
    }
  } catch (err) {
    logger.warn(`Failed to start Meditation controller: ${String(err)}`)
  }

  // Wire Thalamus to GWT systems + secondary brain inputs
  try {
    const thalamus = intelligence.registry.get('thalamus') as
      import('../intelligence/thalamus/index.js').ThalamusModule | undefined
    if (thalamus) {
      if (intelligence.globalWorkspace) thalamus.setGlobalWorkspace(intelligence.globalWorkspace)
      if (intelligence.locusBridge) thalamus.setLocusBridge(intelligence.locusBridge)
      if (intelligence.cortex) thalamus.setCortex(intelligence.cortex)
      const mnemicField = (intelligence as any).__mnemicField
      if (mnemicField) thalamus.setMnemicField(mnemicField)

      // Wire Self-Model Field for architectural relevance scoring
      const selfModelField = (intelligence as any).__selfModelField
      if (selfModelField && typeof thalamus.setSelfModelField === 'function') {
        thalamus.setSelfModelField(selfModelField)
      }

      // Wire Pineal FacetManager for identity/wisdom credibility and resonance
      const pineal = intelligence.registry.get('pineal') as
        import('../intelligence/pineal/index.js').PinealModule | undefined
      if (pineal && typeof thalamus.setPinealFacets === 'function') {
        thalamus.setPinealFacets(pineal.getFacetManager())
      }

      // Wire Thalamus into Meditation for always-on context management
      const meditation = intelligence.meditation
      if (meditation && typeof (meditation as any).setThalamus === 'function') {
        (meditation as any).setThalamus(thalamus)
      }

      // Wire Thalamus into Helix for context curation during long-running sessions
      if (intelligence.helix && typeof (intelligence.helix as any).setThalamus === 'function') {
        (intelligence.helix as any).setThalamus(thalamus)
      }

      // Wire <note for="reverie"> thought-command handoff. Without this, the
      // 'note' branch in Thalamus.processThoughtCommands logs and drops the
      // message — Reverie never sees it. Closes the design contract from
      // cassi-context-awareness.md (note routing).
      if (intelligence.reverie && typeof (thalamus as any).setReverieNoteSink === 'function') {
        (thalamus as any).setReverieNoteSink(
          (sid: string, rec: string, msg: string) => intelligence.reverie!.receiveNote(sid, rec, msg),
        )
      }

      // Wire Aurora (cognitive state loop) into Thalamus
      if (mnemicField && typeof mnemicField.getCortex === 'function') {
        try {
          const { Aurora } = await import('../intelligence/aurora/index.js')

          // WHY: Vindex loading deferred — admin API starts without waiting for the
          // vindex (10s per candidate). The load function is stored on the intelligence
          // layer and called from daemon.scheduleDeferredStartup() after the admin API
          // is live. Aurora starts without a model provider and gets wired later via
          // aurora.setModelProvider().
          const loadVindex = async (): Promise<{ provider: any; name: string; path: string } | null> => {
            try {
              const { LarqlKnowledgeProvider } = await import('../intelligence/aurora/larql-provider.js')
              const { existsSync, readdirSync, statSync } = await import('node:fs')
              const { join } = await import('node:path')
              const { homedir } = await import('node:os')
              const modelsDir = join(homedir(), '.cassicore', 'models')
              if (!existsSync(modelsDir)) return null

              const preferredVindex = config?.get?.('intelligence.aurora.vindex') as string | undefined
              const VINDEX_LOAD_TIMEOUT_MS = 10_000

              const tryLoad = async (candidatePath: string, candidateName: string): Promise<{ provider: any; name: string; path: string } | { error: string }> => {
                const provider = new LarqlKnowledgeProvider(logger)
                const timedOut = Symbol('timedOut')
                try {
                  const result = await Promise.race([
                    provider.load(candidatePath),
                    new Promise<symbol>(resolve =>
                      setTimeout(() => resolve(timedOut), VINDEX_LOAD_TIMEOUT_MS),
                    ),
                  ])
                  if (result === timedOut) return { error: `timed out after ${VINDEX_LOAD_TIMEOUT_MS}ms` }
                  if (result) return { provider, name: candidateName, path: candidatePath }
                  return { error: 'load returned false (unsupported architecture or missing files)' }
                } catch (err) {
                  return { error: `threw: ${String(err)}` }
                }
              }

              let chosen: { name: string; path: string } | null = null
              let modelProvider: any = null

              if (preferredVindex) {
                const preferredPath = join(modelsDir, preferredVindex)
                if (existsSync(preferredPath)) {
                  const result = await tryLoad(preferredPath, preferredVindex)
                  if ('provider' in result) {
                    modelProvider = result.provider
                    chosen = { name: result.name, path: result.path }
                    logger.info('LarqlKnowledgeProvider loaded (preferred)', { vindex: preferredVindex })
                  } else {
                    logger.warn('Preferred vindex failed, falling back to auto-discovery', { vindex: preferredVindex, reason: result.error })
                  }
                } else {
                  logger.warn('Preferred vindex not found', { vindex: preferredVindex, modelsDir })
                }
              }

              if (!chosen) {
                const vindexes = readdirSync(modelsDir)
                  .filter(n => n.endsWith('.vindex'))
                  .map(n => {
                    const p = join(modelsDir, n)
                    const hasWeights = existsSync(join(p, 'down_weights.bin')) ||
                      existsSync(join(p, 'attn_weights_q4k.bin'))
                    return { name: n, path: p, mtime: statSync(p).mtimeMs, hasWeights }
                  })
                  .sort((a, b) => {
                    if (a.hasWeights !== b.hasWeights) return a.hasWeights ? 1 : -1
                    return b.mtime - a.mtime
                  })
                const attempted: Array<{ name: string; reason: string }> = []
                for (const candidate of vindexes) {
                  const result = await tryLoad(candidate.path, candidate.name)
                  if ('provider' in result) {
                    modelProvider = result.provider
                    chosen = { name: result.name, path: result.path }
                    logger.info('LarqlKnowledgeProvider loaded', { vindex: candidate.name, attemptedBefore: attempted.length })
                    break
                  }
                  attempted.push({ name: candidate.name, reason: result.error })
                }
                if (!chosen) {
                  logger.warn('No vindex could be loaded', { attempted: attempted.map(a => `${a.name}: ${a.reason}`) })
                } else if (attempted.length > 0) {
                  logger.info('Skipped earlier vindexes', { skipped: attempted.map(a => a.name), loaded: chosen.name })
                }
              }

              if (chosen && modelProvider) {
                try {
                  const { ClaustrumRecorder } = await import('../intelligence/aurora/claustrum-recorder.js')
                  const recorder = new ClaustrumRecorder(logger, chosen.path)
                  modelProvider.setRecorder(recorder)
                  logger.info('ClaustrumRecorder attached', { source: chosen.name })
                } catch (err) {
                  logger.warn('ClaustrumRecorder failed', { error: String(err) })
                }
                return { provider: modelProvider, name: chosen.name, path: chosen.path }
              }
              return null
            } catch (err) {
              logger.warn('Vindex loading failed', { error: String(err) })
              return null
            }
          }
          ;(intelligence as any).__loadVindex = loadVindex

          // Create Aurora without model provider — gets wired later via setModelProvider()
          let modelProvider: any = null

          const knowledgeField = (intelligence as any).__knowledgeField ?? null

          let auroraPersistence: import('../intelligence/aurora/persistence.js').AuroraPersistence | undefined
          if (config?.get?.('intelligence.aurora.persistence.enabled') === true) {
            try {
              const { AuroraPersistence } = await import('../intelligence/aurora/persistence.js')
              const { getDataDir } = await import('../utils/paths.js')
              const path = await import('node:path')
              const dbPath = path.join(getDataDir(), 'aurora.db')
              auroraPersistence = new AuroraPersistence(dbPath, logger)
              logger.info('AuroraPersistence wired (cross-session continuity B6.1 active)', { dbPath })
            } catch (err) {
              logger.warn('Failed to construct AuroraPersistence — Aurora will run in-memory', {
                error: String(err),
              })
            }
          }

          const auroraConfig: Partial<import('../intelligence/aurora/types.js').AuroraConfig> = {}

          // Self-model knowledge bridge: vindex → Mnemic architectural awareness
          if (config?.get?.('intelligence.aurora.selfModelKnowledge.enabled') === true) {
            auroraConfig.selfModelKnowledgeEnabled = true
            logger.info('SelfModelKnowledge bridge enabled (vindex → Mnemic)')
          }

          const aurora = new Aurora(
            mnemicField.getCortex(),
            modelProvider,
            knowledgeField,
            null,
            logger,
            auroraConfig,
            auroraPersistence,
          )
          thalamus.setAurora(aurora)
          intelligence.aurora = aurora

          // C1.3 Sub6 inlet: meditation drains Aurora's auto-scheduled seeds
          // each idle tick and runs focused sessions against their topics.
          if (intelligence.meditation && typeof (intelligence.meditation as any).setAurora === 'function') {
            (intelligence.meditation as any).setAurora(aurora)
            logger.info('Aurora wired to MeditationController (auto-schedule inlet)')
          }

          // Wire Reverie inference provider into Aurora for the reasoning slow path.
          // ReverieModule exposes inferForObserver() which matches ReverieInferenceProvider.
          if (intelligence.reverie) {
            try {
              const reverieProvider: import('../intelligence/aurora/types.js').ReverieInferenceProvider = {
                infer: (messages, options) => intelligence.reverie!.inferForObserver(messages, options),
              }
              thalamus.setReverieInferenceProvider(reverieProvider)
              logger.info('Reverie wired to Aurora reasoning observer')
            } catch (err) {
              logger.debug('Failed to wire Reverie to Aurora', { error: String(err) })
            }
          }

          logger.info('Aurora wired to Thalamus', {
            hasModelProvider: !!modelProvider,
            hasKnowledgeProvider: !!knowledgeField,
            hasReverie: !!intelligence.reverie,
          })

          // WHY: Deferred — boot-time probe removed (saved ~17 min). The periodic
          // refresh below covers the same ground within 30 min, and vindex gate-KNN
          // is too slow (2.2s/call × 462 calls) to block the event loop on boot.
          if (aurora.hasSelfModelKnowledge) {
            // Gap 4: Periodic self-model refresh every 30 minutes
            const REFRESH_INTERVAL_MS = 30 * 60 * 1000
            const interval = setInterval(() => {
              try { aurora.refreshSelfModelKnowledge() }
              catch { /* best-effort */ }
            }, REFRESH_INTERVAL_MS)
            interval.unref()  // don't keep process alive for this
            logger.info('Self-model periodic refresh scheduled', { intervalMs: REFRESH_INTERVAL_MS })
          }

          // Wire MnemicField to Aurora for persistence (Gap 1)
          if (mnemicField && typeof aurora.setMnemicField === 'function') {
            aurora.setMnemicField(mnemicField)
          }

          // C5 Resonance pipeline: observe each completed turn's response
          // through Aurora, then run steered generation from the updated
          // mental state and observe the steered text back into the graph.
          if (bus && typeof thalamus.observeReasoning === 'function') {
            bus.onAll((event: any) => {
              if (event?.type !== 'turn:end') return
              const text: string = event?.response ?? ''
              if (text.length > 20) {
                queueMicrotask(() => {
                  try { thalamus.observeReasoning(text) }
                  catch { /* best-effort */ }
                })
              }
            })
            logger.info('Resonance pipeline wired to turn:end')
          }
        } catch (err) {
          logger.warn('Failed to wire Aurora to Thalamus', { error: String(err) })
        }
      }

      // Wire PinealAssembler into Thalamus for identity injection
      const pinealModule = intelligence.registry.get('pineal') as
        import('../intelligence/pineal/index.js').PinealModule | undefined
      if (pinealModule) {
        // Wire MnemicField into Pineal for radial topology — Pineal facets
        // are stored as engrams at (0,0), anchoring the tonic center.
        pinealModule.setMnemicField(mnemicField)
        const seeded = pinealModule.seedMnemicFieldFacets()
        if (seeded > 0) {
          logger.info('Pineal facets seeded into MnemicField at origin', { count: seeded })
        }
        const reconciled = pinealModule.reconcileFromField()
        if (reconciled > 0) {
          logger.info('Pineal facets reconciled from MnemicField', { count: reconciled })
        }

        const assembler = new PinealAssembler(pinealModule.getStore(), logger.child('pineal-assembler'))
        thalamus.setPinealAssembler(assembler)
        logger.info('Pineal assembler wired to Thalamus with turn reinforcement')

        // Mirror Pineal facets into read-only laminae
        if (intelligence.lamina) {
          try {
            const { PinealLaminaBridge } = await import('../intelligence/lamina/pineal-bridge.js')
            const bridge = new PinealLaminaBridge(pinealModule, intelligence.lamina, logger.child('pineal-lamina-bridge'))
            const labels = bridge.syncOnce()
            logger.info('Pineal facets mirrored to laminae', { labels })
          } catch (err) {
            logger.warn('Pineal→Lamina bridge failed', { error: String(err) })
          }
        }
      }

      // Wire handleFactory for background LLM calls (topic archiving, gap summaries)
      if (deps.handleFactory && typeof thalamus.setHandleFactory === 'function') {
        thalamus.setHandleFactory(deps.handleFactory)
        logger.info('Thalamus handleFactory wired for background LLM topic archiving')
      }

      // Wire ThalamusStore for drop history persistence (SQLite)
      if (typeof thalamus.setStore === 'function') {
        try {
          const { ThalamusStore } = await import('../intelligence/thalamus/thalamus-store.js')
          const thalamusStore = ThalamusStore.open(logger.child('thalamus-store'))
          thalamus.setStore(thalamusStore)
          logger.info('ThalamusStore wired (SQLite persistence)')
        } catch (err) {
          logger.warn('ThalamusStore failed to initialize', { error: String(err) })
        }
      }

      logger.info('Thalamus wired', {
        gwt: !!intelligence.globalWorkspace,
        locus: !!intelligence.locusBridge,
        cortex: !!intelligence.cortex,
        mnemic: !!mnemicField,
        selfModel: !!selfModelField,
        pinealFacets: !!(pineal),
        aurora: !!mnemicField,
        meditation: !!(meditation && typeof (meditation as any).setThalamus === 'function'),
        helix: !!(intelligence.helix && typeof (intelligence.helix as any).setThalamus === 'function'),
        topicArchiving: !!(deps.handleFactory),
      })
    }
  } catch (err) {
    logger.warn('Failed to wire Thalamus', { error: String(err) })
  }

  pipeline.mountIntelligence({ continuity: intelligence.continuity as any })
  pipeline.setIntelligence(intelligence)

  try {
    const cm = intelligence.contextManager as any
    if (cm) {
      if (typeof cm.setSessions === 'function') cm.setSessions(sessions)
      if (typeof cm.setPipeline === 'function') cm.setPipeline(pipeline)
      if (typeof cm.onEventBus === 'function') cm.onEventBus(bus)
      try {
        const enabled = config.get<boolean>('intelligence.contextManager.enabled', true)
        const intervalMs = config.get<number>('intelligence.contextManager.syncIntervalMs', 60000)
        if (enabled && typeof cm.start === 'function') cm.start({ intervalMs })
        logger.info('ContextManager wired to session manager and pipeline')
      } catch (err) {
        logger.warn('ContextManager: failed to start sync', { error: String(err) })
      }
    }
  } catch (err) {
    logger.warn('failed to wire context manager', { error: String(err) })
  }

  // REMOVED: optimizer wiring — OptimizerModule deleted

  try {
    const scoutEnabled = config.get<boolean>('intelligence.scout.enabled', true)
    if (scoutEnabled) {
      const scoutModule = new ScoutModule(logger.child('scout'), {
        enabled: true,
        providerId: config.get<string>('intelligence.scout.providerId', undefined),
        model: config.get<string>('intelligence.scout.model', undefined),
        maxToolRounds: config.get<number>('intelligence.scout.maxToolRounds', undefined),
        timeoutMs: config.get<number>('intelligence.scout.timeoutMs', undefined),
        maxContextChars: config.get<number>('intelligence.scout.maxContextChars', undefined),
      })
      scoutModule.setToolRegistry(toolRegistry)
      scoutModule.setToolExecutor(toolExecutor)
      scoutModule.setEventBus(bus)
      await scoutModule.init()
      scoutModule.setPipeline(pipeline)
      await scoutModule.start()
      logger.info('Scout module wired to pipeline, tool registry, and event bus')
    }
  } catch (err) {
    logger.warn('Failed to wire Scout module', { error: String(err) })
  }

  if (intelligence.thinker.__awaitingWiring) {
    intelligence.thinker.__awaitingWiring.setSessionManager(sessions, sessionStore)
    intelligence.thinker.__awaitingWiring.setPipelineGetter(() => deps.sessionPipeline ?? pipeline)
    logger.info('Thinker wired to session manager and pipeline for subagent spawning')
  }

  // Create stable persistent sessions for every LLM-calling module.
  // These power Telegram topic debugging and smart history compaction.
  try {
    const moduleRegistry = new ModuleSessionRegistry(sessions, logger)
    const compactor = new ModuleSessionCompactor(sessions, logger)
    moduleRegistry.setCompactor(compactor)
    if (compactionProvider) compactor.setProvider(compactionProvider)

    // Wire registry into every LLM-calling module
    const thinkerWiring = intelligence.thinker.__awaitingWiring ?? intelligence.thinker
    if (typeof (thinkerWiring as any).setModuleRegistry === 'function') {
      ;(thinkerWiring as any).setModuleRegistry(moduleRegistry)
    }
    if (intelligence.subconscious) {
      const obs = (intelligence.subconscious as any).llmObserver ?? intelligence.subconscious
      if (typeof (obs as any).setModuleRegistry === 'function') {
        ;(obs as any).setModuleRegistry(moduleRegistry)
      } else if (typeof (intelligence.subconscious as any).setModuleRegistry === 'function') {
        ;(intelligence.subconscious as any).setModuleRegistry(moduleRegistry)
      }
    }
    if (typeof (intelligence.dialectic as any).setModuleRegistry === 'function') {
      ;(intelligence.dialectic as any).setModuleRegistry(moduleRegistry)
    }
    if (typeof (intelligence.dreamer as any).setModuleRegistry === 'function') {
      ;(intelligence.dreamer as any).setModuleRegistry(moduleRegistry)
    }
    // Memory sub-modules
    const mem = intelligence.memory as any
    if (mem) {
      if (typeof mem.archiveAnalyzer?.setModuleRegistry === 'function') {
        mem.archiveAnalyzer.setModuleRegistry(moduleRegistry)
      }
      if (typeof mem.continuousSearchManager?.setModuleRegistry === 'function') {
        mem.continuousSearchManager.setModuleRegistry(moduleRegistry)
      }
    }
    // Scout (wired during scout creation above — wire here if ScoutModule exposes it)
    // (ScoutEngine exposes setModuleRegistry, but ScoutModule wraps it — wire the engine)
    if (typeof (intelligence as any).scout?.setModuleRegistry === 'function') {
      ;(intelligence as any).scout.setModuleRegistry(moduleRegistry)
    }
    // Context Distiller
    if (typeof contextDistiller?.setModuleRegistry === 'function') {
      contextDistiller.setModuleRegistry(moduleRegistry)
    }
    // Orchestrators
    if (typeof intelligence.helix?.setModuleRegistry === 'function') {
      intelligence.helix.setModuleRegistry(moduleRegistry)
    }
    // Triad team member sessions are created dynamically — wire registry via fleet coordinator
    if (typeof (intelligence as any).triadTeam?.setModuleRegistry === 'function') {
      ;(intelligence as any).triadTeam.setModuleRegistry(moduleRegistry)
    }

    // Pre-warm all sessions from disk
    await moduleRegistry.warmAll()

    // Store on intelligence layer for cognitive feed and admin API access
    ;(intelligence as any).moduleRegistry = moduleRegistry

    logger.info('ModuleSessionRegistry initialized and wired to all modules')
  } catch (err) {
    logger.warn('Failed to initialize ModuleSessionRegistry', { error: String(err) })
  }

  await intelligence.thinker.start?.()

  let autonomousLoop: AutonomousAgentLoop | undefined
  try {
    autonomousLoop = new AutonomousAgentLoop(logger.child('autonomous-loop'))
    // setPipeline() was removed from AutonomousAgentLoop — execution is now driven via setBackend()
    // (CassiCoreExecutionBackend wrapping SessionPipeline). Backend is wired below.
    autonomousLoop.setEventBus(bus)
    if (intelligence.memory) autonomousLoop.setMemory(intelligence.memory)
    if (sessionDigestStore) autonomousLoop.setDigestStore(sessionDigestStore)
    autonomousLoop.setSessions(sessions)
    if (intelligence.dialectic) autonomousLoop.setDialectic(intelligence.dialectic as any)

    const backendType = config.get<ExecutionBackendType>('intelligence.executionBackend.type', 'cassicore')
    if (backendType !== 'cassicore') {
      const openCodeConfig = config.get<OpenCodeBackendConfig>('intelligence.executionBackend.opencode', {})
      const executionBackend = createExecutionBackend(backendType, logger.child('execution-backend'), {
        sessionPipeline: deps.sessionPipeline,
        openCodeConfig,
      })
      autonomousLoop.setBackend(executionBackend)
      logger.info(`Execution backend set: ${executionBackend.name}`)

      const cm = intelligence.contextManager as any
      if (cm && typeof cm.setExecutionBackend === 'function') {
        cm.setExecutionBackend(executionBackend)
        logger.info('ContextManager wired to execution backend for push updates')
      }
    }

    logger.info('AutonomousAgentLoop engine initialized and wired')
  } catch (err) {
    logger.warn('Failed to initialize AutonomousAgentLoop', { error: String(err) })
    autonomousLoop = undefined
  }

  // REMOVED: TriadTeam wiring — deprecated system deleted.
  // REMOVED: drone tools registration — DroneSwarm removed.

  // Deferred Thalamus wiring — the MnemicField may not have been
  // initialized when the main wiring block ran (race between Phase 5
  // Pipeline creation and this post-boot hook). Re-check and wire if missed.
  try {
    const thalamus = intelligence.registry.get('thalamus') as any
    const mnemicField = (intelligence as any).__mnemicField
    if (thalamus && mnemicField && typeof thalamus.setMnemicField === 'function') {
      // Only wire if not already wired (avoid double-wire)
      // The setMnemicField is idempotent — safe to call multiple times
      thalamus.setMnemicField(mnemicField)
      logger.info('Thalamus MnemicField deferred-wired (post-boot catch-up)')
    }
  } catch (err) {
    // Non-fatal — Thalamus will skip engram storage until next restart
    logger.warn('Deferred Thalamus MnemicField wiring failed', { error: String(err) })
  }

  return autonomousLoop
}
