import { AutonomousAgentLoop } from '../intelligence/autonomous-loop.js'
import { createExecutionBackend } from '../intelligence/execution-backends/index.js'
import { ScoutModule } from '../scout/index.js'
import { registerDroneTools } from '../tools/implementations/drone-swarm.js'
import { registerTeamTools } from '../tools/implementations/team-coordinator.js'

import type { IEventBus, IConfig, ILogger, IPluginHost } from '../../types/interfaces.js'
import type { IntelligenceLayer } from '../intelligence/index.js'
import type { TurnPipeline } from '../turn-pipeline.js'
import type { ToolExecutor } from '../tools/executor.js'
import type { ToolRegistry } from '../tools/registry.js'
import type { SessionStore } from '../session-store.js'
import type { SessionDigestStore } from '../intelligence/session-digest.js'
import type { ExecutionBackendType, OpenCodeBackendConfig } from '../../types/execution-backend.js'
import type { SessionManager } from '../session-manager.js'

export interface IntelligencePostBootDeps {
  bus: IEventBus
  config: IConfig
  logger: ILogger
  intelligence: IntelligenceLayer
  pipeline: TurnPipeline
  sessions: SessionManager
  sessionStore: SessionStore
  sessionDigestStore?: SessionDigestStore
  autonomousLoop?: AutonomousAgentLoop
  toolRegistry: ToolRegistry
  toolExecutor: ToolExecutor
  pluginHost?: IPluginHost
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
  } = deps

  try {
    intelligence.injectionAggregator.setDependencies({
      pipeline,
      dialectic: intelligence.dialectic as any,
      subconscious: intelligence.subconscious,
      digestStore: sessionDigestStore!,
      contextManager: intelligence.contextManager as any,
      eventBus: bus,
    })
    pipeline.setInjectionAggregator(intelligence.injectionAggregator)
    logger.info('InjectionAggregator wired to pipeline')
  } catch (err) {
    logger.warn(`Failed to wire InjectionAggregator: ${String(err)}`)
  }

  try {
    intelligence.thoughtObserver.onEventBus(bus)
    logger.info('ThoughtObserver wired to event bus')
  } catch (err) {
    logger.warn(`Failed to wire ThoughtObserver: ${String(err)}`)
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

  intelligence.optimizer.setSessions(sessions)
  intelligence.optimizer.setPipeline(pipeline)
  logger.info('Optimizer wired to session manager and pipeline')

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
    intelligence.thinker.__awaitingWiring.setPipelineGetter(() => pipeline)
    logger.info('Thinker wired to session manager and pipeline for subagent spawning')
  }

  if (intelligence.droneSwarm && typeof intelligence.thinker.setDroneSwarm === 'function') {
    intelligence.thinker.setDroneSwarm(intelligence.droneSwarm)
    logger.info('Thinker wired to drone swarm controller')
  }
  await intelligence.thinker.start?.()

  let autonomousLoop: AutonomousAgentLoop | undefined
  try {
    autonomousLoop = new AutonomousAgentLoop(logger.child('autonomous-loop'))
    autonomousLoop.setPipeline(pipeline)
    autonomousLoop.setEventBus(bus)
    if (intelligence.memory) autonomousLoop.setMemory(intelligence.memory)
    if (sessionDigestStore) autonomousLoop.setDigestStore(sessionDigestStore)
    autonomousLoop.setSessions(sessions)
    if (intelligence.dialectic) autonomousLoop.setDialectic(intelligence.dialectic as any)
    if (intelligence.multiAgent) {
      autonomousLoop.setMultiAgent(intelligence.multiAgent as any)
      intelligence.multiAgent.setAutonomousLoop?.(autonomousLoop)
    }

    const backendType = config.get<ExecutionBackendType>('intelligence.executionBackend.type', 'cassicore')
    if (backendType !== 'cassicore') {
      const openCodeConfig = config.get<OpenCodeBackendConfig>('intelligence.executionBackend.opencode', {})
      const executionBackend = createExecutionBackend(backendType, logger.child('execution-backend'), {
        pipeline,
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

  try {
    const triadTeam = intelligence.triadTeam
    if (triadTeam) {
      // TriadTeamOrchestrator is not registered in the IntelligenceRegistry
      // (it's in intelligence.all but created separately), so its lifecycle
      // methods aren't called by registry.initAll()/startAll(). Call them explicitly.
      await triadTeam.init()
      await triadTeam.start()

      // TriadTeamOrchestrator inherits eventBus from BaseCognitiveModule via the registry.
      // Wire optional dependencies that are only available post-boot.
      if (sessionDigestStore) (triadTeam as any).setDigestStore?.(sessionDigestStore)
      if (autonomousLoop) (triadTeam as any).setAutonomousLoop?.(autonomousLoop)
      if (intelligence.droneSwarm) (triadTeam as any).setDroneSwarm?.(intelligence.droneSwarm)
      logger.info('TriadTeamOrchestrator wired with available post-boot dependencies')

      registerTeamTools(toolRegistry, {
        triadTeam,
        digestStore: sessionDigestStore,
        logger,
      })
      logger.info('Team tools registered: check_team_status, send_team_message, get_cell_result, list_team_cells, update_team_plan, complete_team_goal, get_team_cell_tree, approve_checkpoint')
    }
  } catch (err) {
    logger.warn('Failed to wire TriadTeamOrchestrator', { error: String(err) })
  }

  try {
    if (intelligence.droneSwarm) {
      registerDroneTools(toolRegistry, {
        droneSwarm: intelligence.droneSwarm,
        logger,
      })
      logger.info('Drone tools registered: drone_swarm, drone_scout, drone_cancel')
    }
  } catch (err) {
    logger.warn('Failed to register drone tools', { error: String(err) })
  }

  return autonomousLoop
}
