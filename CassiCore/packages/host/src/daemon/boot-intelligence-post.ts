import { AutonomousAgentLoop } from '../intelligence/autonomous-loop.js'
import { createExecutionBackend } from '../intelligence/execution-backends/index.js'
import { ScoutModule } from '../scout/index.js'
// REMOVED: registerTeamTools — team-coordinator.ts deleted with TriadTeam
import { ModuleSessionRegistry } from '../intelligence/module-session-registry.js'
import { ModuleSessionCompactor } from '../intelligence/module-session-compactor.js'
import { SkillEffectivenessSource } from '../intelligence/skill-metrics.js'
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
      intelligence.dmn.setOnFire(async (_reason, sessionId) => {
        try {
          const session = sessions.get(sessionId)
          const history = session?.history ?? []
          if (history.length === 0) return null

          const recent = history.slice(-HISTORY_WINDOW)
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

          const result = await intelligence.dialectic.processTurn(
            sessionId,
            `dmn-${Date.now()}`,
            userMessage,
            {
              recentMemories: [],
              availableTools: [],
              sessionHistory: recent as any,
              taskGuide: 'DMN observation pass: surface what is most load-bearing about the recent conversation state.',
            } as any,
            { skipCache: true } as any,
          ) as any

          const synthesis = result?.serenity?.synthesis
          if (!synthesis) return null
          return synthesis
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

      // Hand distillation triggering to Reverie. The design assigns Reverie
      // ownership of stateful background work; Thalamus retains queue + summary
      // storage but Reverie decides WHEN to fire. enableExternalDistillationTrigger
      // suppresses Thalamus.curate's inline spawn so we don't double-queue.
      if (
        intelligence.reverie &&
        typeof (intelligence.reverie as any).setDistillationTrigger === 'function' &&
        typeof (thalamus as any).queueBackgroundDistillations === 'function' &&
        typeof (thalamus as any).enableExternalDistillationTrigger === 'function'
      ) {
        (intelligence.reverie as any).setDistillationTrigger(
          (sid: string) => (thalamus as any).queueBackgroundDistillations(sid),
        )
        ;(thalamus as any).enableExternalDistillationTrigger()
      }

      // Wire Aurora (cognitive state loop) into Thalamus
      if (mnemicField && typeof mnemicField.getCortex === 'function') {
        try {
          const { Aurora } = await import('../intelligence/aurora/index.js')

          let modelProvider: any = null
          try {
            const { LarqlKnowledgeProvider } = await import('../intelligence/aurora/larql-provider.js')
            const { existsSync, readdirSync, statSync } = await import('node:fs')
            const { join } = await import('node:path')
            const { homedir } = await import('node:os')
            const modelsDir = join(homedir(), '.cassicore', 'models')
            if (existsSync(modelsDir)) {
              const vindexes = readdirSync(modelsDir)
                .filter(n => n.endsWith('.vindex'))
                .map(n => ({ name: n, path: join(modelsDir, n), mtime: statSync(join(modelsDir, n)).mtimeMs }))
                .sort((a, b) => b.mtime - a.mtime)
              if (vindexes.length > 0) {
                const attempted: Array<{ name: string; reason: string }> = []
                let chosen: { name: string; path: string } | null = null
                for (const candidate of vindexes) {
                  const provider = new LarqlKnowledgeProvider(logger)
                  let loaded = false
                  try {
                    loaded = await provider.load(candidate.path)
                  } catch (err) {
                    attempted.push({ name: candidate.name, reason: `threw: ${String(err)}` })
                    continue
                  }
                  if (loaded) {
                    modelProvider = provider
                    chosen = { name: candidate.name, path: candidate.path }
                    logger.info('LarqlKnowledgeProvider loaded', {
                      vindex: candidate.name,
                      attemptedBefore: attempted.length,
                    })
                    try {
                      const { ClaustrumRecorder } = await import('../intelligence/aurora/claustrum-recorder.js')
                      const recorder = new ClaustrumRecorder(logger, candidate.path)
                      provider.setRecorder(recorder)
                      logger.info('ClaustrumRecorder attached — gate-KNN provenance will be logged for snapshotting', {
                        source: candidate.name,
                      })
                    } catch (err) {
                      logger.warn('Failed to attach ClaustrumRecorder — Aurora will run without provenance logging', {
                        error: String(err),
                      })
                    }
                    break
                  }
                  attempted.push({ name: candidate.name, reason: 'load returned false (likely unsupported architecture for browse-only mode)' })
                }
                if (!chosen) {
                  logger.warn('No vindex could be loaded — Aurora will run without model knowledge', {
                    attempted: attempted.map(a => `${a.name}: ${a.reason}`),
                  })
                } else if (attempted.length > 0) {
                  logger.info('Skipped earlier vindexes before loading a compatible one', {
                    skipped: attempted.map(a => a.name),
                    loaded: chosen.name,
                  })
                }
              }
            }
          } catch (err) {
            logger.warn('Failed to load LarqlKnowledgeProvider — Aurora will run without model knowledge', { error: String(err) })
          }

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

          const aurora = new Aurora(
            mnemicField.getCortex(),
            modelProvider,
            knowledgeField,
            null,
            logger,
            undefined,
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
        } catch (err) {
          logger.warn('Failed to wire Aurora to Thalamus', { error: String(err) })
        }
      }

      // Wire PinealAssembler into Thalamus for identity injection
      const pinealModule = intelligence.registry.get('pineal') as
        import('../intelligence/pineal/index.js').PinealModule | undefined
      if (pinealModule) {
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

        // Wire distillation factory — uses kimi-for-coding provider specifically
        // ModelPool only exposes acquire(), not getProvider(). Probe with a
        // speculative acquire/release cycle to confirm availability.
        if (typeof thalamus.setDistillationFactory === 'function' && deps.modelPool) {
          try {
            const probe = await deps.modelPool!.acquire('unity', 'background', '__probe__', { provider: 'kimi-coding', model: 'kimi-for-coding' })
            probe.release()
            const distillationFactory: typeof deps.handleFactory = async (cfg) => {
              return deps.modelPool!.acquire('unity', cfg.tier, cfg.sessionId, { provider: 'kimi-coding', model: 'kimi-for-coding' })
            }
            thalamus.setDistillationFactory(distillationFactory)
            logger.info('Thalamus distillationFactory wired (kimi-coding / kimi-for-coding)')
          } catch {
            logger.info('Thalamus distillationFactory: kimi-coding provider not available, falling back to handleFactory')
          }
        }
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

  return autonomousLoop
}
