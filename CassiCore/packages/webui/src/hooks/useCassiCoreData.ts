'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '@/store'

/**
 * Polls CassiCore daemon endpoints to keep sidebar status fresh.
 * Runs on mount + every 15s while the endpoint is active.
 */
export function useCassiCoreData() {
  const {
    selectedEndpoint,
    isEndpointActive,
    setDaemonInfo,
    setProviderHealth,
    setAvailableModels,
    setIntelligenceActivity
  } = useStore()
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchAll = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return

    const base = selectedEndpoint

    // Health → daemonInfo
    try {
      const res = await fetch(`${base}/api/health`)
      if (res.ok) {
        const data = await res.json()
        setDaemonInfo(data)

        // Extract provider list from health checks
        const providersCheck = (data.checks as Array<Record<string, unknown>>)?.find(
          (c) => c.name === 'providers'
        )
        if (providersCheck?.meta) {
          const providerIds = (providersCheck.meta as Record<string, unknown>).providers as string[] | undefined
          if (providerIds) {
            setProviderHealth(
              providerIds.map((id) => ({ id, status: 'ok' }))
            )
          }
        }
      }
    } catch {
      // Daemon unreachable — will be caught by health monitor
    }

    // Models
    try {
      const res = await fetch(`${base}/api/cassicore/models`)
      if (res.ok) {
        const data = await res.json()
        setAvailableModels(data.models ?? [])
      }
    } catch {
      // non-critical
    }

    // Intelligence activity
    try {
      const res = await fetch(`${base}/api/cassicore/intelligence`)
      if (res.ok) {
        const data = await res.json()
        setIntelligenceActivity(data)
      }
    } catch {
      // non-critical
    }
  }, [selectedEndpoint, isEndpointActive, setDaemonInfo, setProviderHealth, setAvailableModels, setIntelligenceActivity])

  useEffect(() => {
    fetchAll()
    timerRef.current = setInterval(fetchAll, 15_000)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [fetchAll])
}
