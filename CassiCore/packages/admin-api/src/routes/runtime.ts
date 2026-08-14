import {
  buildLegacySessionConfig,
  cancelTurn,
  ensureLegacySession,
  executeTurn,
  getAvailableToolNames,
  getPreferredTurnEngine,
  resolveStreamSessionId,
  runLegacyDialectic,
  type TurnCancellationResult,
  type TurnEngine,
  type TurnExecutionRequest,
  type TurnExecutionResult,
  type TurnRuntimeLike,
} from './turn-routing.js'

import type { ILogger } from '@cassicore/foundation'
import type { IConfig } from '@cassicore/foundation'
import type { RuntimeEvent } from '@cassicore/foundation'

interface ProviderMetricsSnapshot {
  id: string
  metrics: any
}

export interface AdminRuntimeFacade {
  readonly logger: ILogger
  readonly bus: { on(type: string, handler: (event: any) => void): void; off(type: string, handler: (event: any) => void): void; emit(event: any): void }
  preferredTurnEngine(): TurnEngine | null
  executeTurn(request: TurnExecutionRequest): Promise<TurnExecutionResult>
  cancelTurn(sessionId: string): TurnCancellationResult
  resolveStreamSessionId(requestedSessionId: string, channelId: string, senderId: string): string
  getLegacySession(request: { sessionId: string; channelId: string; senderId: string; model?: string; thinking?: string; systemPrompt?: string }): any
  buildLegacySessionConfig(request: { sessionId: string; channelId: string; senderId: string; model?: string; thinking?: string; systemPrompt?: string }): Record<string, unknown>
  runLegacyDialectic(request: { sessionId: string; turnId: string; content: string; sessionHistory: any[]; taskGuide?: string; dialecticMode?: string }): Promise<any | null>
  getAvailableToolNames(): string[]
  getLegacySessionStore(): any
  getPrimarySessionStore(): any
  getIntelligence(): any
  getContextWindow(): any
  getContextDistiller(): any
  getLumenModelPool(): any
  getPipeline(): any
  getProviders(): Map<string, any> | undefined
  getProviderMetrics(): { global: Record<string, unknown> | null; providers: ProviderMetricsSnapshot[] }
  getToolRegistry(): any
  getToolExecutor(): any
  getConfig(): IConfig | undefined
  reloadConfig(): Promise<void>
  emit(event: RuntimeEvent): Promise<void>
}

export function createAdminRuntimeFacade(daemon: TurnRuntimeLike & { logger: ILogger; bus: any; contextWindow?: any }): AdminRuntimeFacade {
  return {
    logger: daemon.logger,
    bus: daemon.bus,
    preferredTurnEngine: () => getPreferredTurnEngine(daemon),
    executeTurn: (request) => executeTurn(daemon, request),
    cancelTurn: (sessionId) => cancelTurn(daemon, sessionId),
    resolveStreamSessionId: (requestedSessionId, channelId, senderId) =>
      resolveStreamSessionId(daemon, requestedSessionId, channelId, senderId),
    getLegacySession: (request) => ensureLegacySession(daemon, request),
    buildLegacySessionConfig: (request) => buildLegacySessionConfig(daemon, request),
    runLegacyDialectic: (request) => runLegacyDialectic(daemon, request),
    getAvailableToolNames: () => getAvailableToolNames(daemon),
    getLegacySessionStore: () => (daemon as any).sessions,
    getPrimarySessionStore: () => (daemon as any).sessionPipeline?.getSessionManager?.() ?? (daemon as any).sessions,
    getIntelligence: () => (daemon as any).intelligence,
    getContextWindow: () => (daemon as any).contextWindow,
    getPipeline: () => (daemon as any).pipeline,
    getProviders: () => {
      const pipelineProviders = (daemon as any).pipeline?.providers
      if (pipelineProviders instanceof Map && pipelineProviders.size > 0) {
        return pipelineProviders
      }

      const providers = (daemon as any).providers
      return providers instanceof Map ? providers : undefined
    },
    getProviderMetrics: () => {
      const providers = (() => {
        const pipelineProviders = (daemon as any).pipeline?.providers
        if (pipelineProviders instanceof Map && pipelineProviders.size > 0) {
          return pipelineProviders
        }

        const rawProviders = (daemon as any).providers
        return rawProviders instanceof Map ? rawProviders : undefined
      })()

      if (!providers) {
        return { global: null, providers: [] }
      }

      const providerMetrics: ProviderMetricsSnapshot[] = []
      let globalConfig: Record<string, unknown> | null = null

      for (const [id, provider] of providers) {
        let metrics: any = null
        try {
          metrics = typeof (provider as any).getMetrics === 'function'
            ? (provider as any).getMetrics()
            : null
        } catch {
          metrics = null
        }

        providerMetrics.push({ id, metrics })
        if (!globalConfig && metrics?.globalConfig && typeof metrics.globalConfig === 'object') {
          globalConfig = metrics.globalConfig as Record<string, unknown>
        }
      }

      return { global: globalConfig, providers: providerMetrics }
    },
    getContextDistiller: () => (daemon as any).contextDistiller,
    getLumenModelPool: () => (daemon as any).lumenModelPool ?? (daemon as any).dyadModelPool,
    getToolRegistry: () => (daemon as any).toolRegistry ?? (daemon as any).pipeline?.toolRegistry,
    getToolExecutor: () => (daemon as any).toolExecutor,
    getConfig: () => (daemon as any).config,
    reloadConfig: async () => {
      if (typeof (daemon as any).reload === 'function') {
        await (daemon as any).reload()
        return
      }

      await daemon.bus.emit({ type: 'config:reloaded' } as RuntimeEvent)
    },
    emit: (event) => daemon.bus.emit(event),
  }
}
