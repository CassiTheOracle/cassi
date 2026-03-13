/**
 * Hook for fetching and caching model list + provider health.
 *
 * Fetches models on mount, polls provider health every 30s, merges into
 * enriched ModelInfo[] with health status.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useDaemon } from './use-daemon.js'
import type { DaemonModel, ProviderHealth, ModelInfo } from '../types/index.js'

const HEALTH_POLL_MS = 30_000

export interface UseModelsReturn {
  /** All available models with health status. */
  models: ModelInfo[]
  /** Raw provider health data. */
  providerHealth: ProviderHealth[]
  /** True while initial fetch is in progress. */
  loading: boolean
  /** Error message if fetch failed. */
  error: string | null
  /** Find models by partial match (fuzzy on shortName). */
  findModels: (partial: string) => ModelInfo[]
  /** Get a single model by ID. */
  getModelInfo: (id: string) => ModelInfo | null
  /** Get short name from full model ID. */
  getShortName: (id: string) => string
  /** Force refresh of model list and health. */
  refresh: () => Promise<void>
}

function parseModelId(id: string): { providerId: string; shortName: string } {
  const parts = id.split('/')
  if (parts.length >= 2) {
    return { providerId: parts[0]!, shortName: parts.slice(1).join('/') }
  }
  return { providerId: 'unknown', shortName: id }
}

function mergeModelsWithHealth(
  models: DaemonModel[],
  health: ProviderHealth[],
): ModelInfo[] {
  const healthMap = new Map<string, ProviderHealth>()
  for (const h of health) {
    healthMap.set(h.id, h)
  }

  return models.map((m) => {
    const { providerId, shortName } = parseModelId(m.id)
    const provider = healthMap.get(providerId)
    return {
      id: m.id,
      name: m.name,
      shortName,
      providerId,
      api: m.api,
      reasoning: m.reasoning,
      contextWindow: m.contextWindow,
      maxTokens: m.maxTokens,
      providerStatus: provider?.status ?? 'ok',
    }
  })
}

export function useModels(): UseModelsReturn {
  const client = useDaemon()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [providerHealth, setProviderHealth] = useState<ProviderHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const [modelsResp, healthResp] = await Promise.all([
        client.models(),
        client.providerHealth(),
      ])

      if (!mountedRef.current) return

      const merged = mergeModelsWithHealth(modelsResp, healthResp)
      setModels(merged)
      setProviderHealth(healthResp)
      setError(null)
    } catch (err) {
      if (!mountedRef.current) return
      setError(String(err))
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [client])

  useEffect(() => {
    mountedRef.current = true
    refresh()

    // Poll provider health every 30s
    const interval = setInterval(() => {
      client.providerHealth().then((health) => {
        if (!mountedRef.current) return
        setProviderHealth(health)
        // Re-merge to update providerStatus on existing models
        client.models().then((models) => {
          if (!mountedRef.current) return
          setModels(mergeModelsWithHealth(models, health))
        })
      }).catch(() => {
        // Silently ignore polling errors
      })
    }, HEALTH_POLL_MS)

    return () => {
      mountedRef.current = false
      clearInterval(interval)
    }
  }, [refresh, client])

  const findModels = useCallback(
    (partial: string): ModelInfo[] => {
      const lower = partial.toLowerCase()
      return models.filter(
        (m) =>
          m.shortName.toLowerCase().includes(lower) ||
          m.providerId.toLowerCase().includes(lower) ||
          m.id.toLowerCase().includes(lower),
      )
    },
    [models],
  )

  const getModelInfo = useCallback(
    (id: string): ModelInfo | null => {
      return models.find((m) => m.id === id) ?? null
    },
    [models],
  )

  const getShortName = useCallback((id: string): string => {
    const { shortName } = parseModelId(id)
    return shortName
  }, [])

  return {
    models,
    providerHealth,
    loading,
    error,
    findModels,
    getModelInfo,
    getShortName,
    refresh,
  }
}
