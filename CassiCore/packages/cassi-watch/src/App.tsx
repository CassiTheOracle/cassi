/**
 * CassiWatch App — Main application component
 */

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Box, Text, useApp, useInput } from 'ink'

import { WatchClient } from './client/watch-client.js'
import { StatsPanel } from './components/StatsPanel.js'
import { CallList } from './components/CallList.js'
import { FilterPanel } from './components/FilterPanel.js'
import { HelpOverlay } from './components/HelpOverlay.js'
import { StatusBar } from './components/StatusBar.js'

import type {
  LLMCall,
  WatchFilters,
  WatchStats,
  DEFAULT_FILTERS as DefaultFilters,
  DEFAULT_DISPLAY_CONFIG as DefaultDisplayConfig,
  ProviderStartEvent,
  ProviderEndEvent,
  ProviderErrorEvent,
} from './types/index.js'
import { DEFAULT_FILTERS, DEFAULT_DISPLAY_CONFIG } from './types/index.js'

interface AppProps {
  client: WatchClient
  daemonUrl?: string
}

/** Generate unique ID for LLM calls */
function generateCallId(): string {
  return `call_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

/** Calculate statistics from calls */
function calculateStats(calls: LLMCall[], filters: WatchFilters): WatchStats {
  const filteredCalls = filterCalls(calls, filters)

  const byStatus: Record<string, number> = {
    pending: 0,
    success: 0,
    error: 0,
    cancelled: 0,
  }

  const byProvider: Record<string, number> = {}
  const byModel: Record<string, number> = {}
  let totalLatency = 0
  let latencyCount = 0
  let totalTokens = 0

  for (const call of filteredCalls) {
    byStatus[call.status] = (byStatus[call.status] || 0) + 1
    byProvider[call.provider] = (byProvider[call.provider] || 0) + 1
    byModel[call.model] = (byModel[call.model] || 0) + 1

    if (call.latencyMs !== null) {
      totalLatency += call.latencyMs
      latencyCount++
    }

    if (call.tokens) {
      totalTokens += call.tokens.total
    }
  }

  const completedCalls = filteredCalls.filter((c) => c.status !== 'pending')
  const errorCount = byStatus.error || 0

  return {
    totalCalls: filteredCalls.length,
    byStatus: byStatus as WatchStats['byStatus'],
    byProvider,
    byModel,
    avgLatencyMs: latencyCount > 0 ? totalLatency / latencyCount : null,
    errorRate: completedCalls.length > 0 ? errorCount / completedCalls.length : 0,
    totalTokens,
    callsPerMinute: filteredCalls.length > 0
      ? Math.round((filteredCalls.length / 5) * 60) // Estimate based on last 5 seconds
      : 0,
  }
}

/** Filter calls based on active filters */
function filterCalls(calls: LLMCall[], filters: WatchFilters): LLMCall[] {
  return calls.filter((call) => {
    if (filters.provider && !call.provider.toLowerCase().includes(filters.provider.toLowerCase())) {
      return false
    }
    if (filters.model && !call.model.toLowerCase().includes(filters.model.toLowerCase())) {
      return false
    }
    if (filters.status && call.status !== filters.status) {
      return false
    }
    if (filters.sessionId && !call.sessionId.toLowerCase().includes(filters.sessionId.toLowerCase())) {
      return false
    }
    if (filters.minLatency !== null && call.latencyMs !== null && call.latencyMs < filters.minLatency) {
      return false
    }
    if (filters.maxLatency !== null && call.latencyMs !== null && call.latencyMs > filters.maxLatency) {
      return false
    }
    if (filters.errorsOnly && call.status !== 'error') {
      return false
    }
    return true
  })
}

export function App({ client }: AppProps): React.ReactElement {
  const { exit } = useApp()

  // Connection state
  const [connected, setConnected] = useState(false)
  const [connectionString, setConnectionString] = useState('')
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Call data
  const [calls, setCalls] = useState<LLMCall[]>([])
  const [inflightRequests, setInflightRequests] = useState<Map<string, {
    provider: string
    model: string
    sessionId: string
    requestId: string
    timestamp: number
  }>>(new Map())

  // UI state
  const [filterPanelOpen, setFilterPanelOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [showTokenDetails, setShowTokenDetails] = useState(true)

  // Filters
  const [filters, setFilters] = useState<WatchFilters>({ ...DEFAULT_FILTERS })

  // Scroll state
  const [scrollOffset, setScrollOffset] = useState(0)
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)

  // Stats
  const [stats, setStats] = useState<WatchStats>(calculateStats([], DEFAULT_FILTERS))
  const [lastUpdateTime, setLastUpdateTime] = useState<number | null>(null)

  // Available filters (discovered from data)
  const [availableProviders, setAvailableProviders] = useState<string[]>([])
  const [availableModels, setAvailableModels] = useState<string[]>([])

  // Track connection
  useEffect(() => {
    // Ping daemon
    client.ping()
      .then((info) => {
        setConnected(true)
        setConnectionString(client.connectionString)
        setConnectionError(null)

        // Start streaming
        client.startStream().catch((err) => {
          setConnectionError(String(err))
          setConnected(false)
        })
      })
      .catch((err) => {
        setConnectionError(String(err))
        setConnected(false)
      })

    // Event handlers
    const handleStart = (data: ProviderStartEvent) => {
      setInflightRequests((prev) => {
        const next = new Map(prev)
        next.set(data.requestId, {
          provider: data.providerId,
          model: data.model,
          sessionId: data.sessionId,
          requestId: data.requestId,
          timestamp: data.timestamp,
        })
        return next
      })

      // Create pending call
      const callId = generateCallId()
      const newCall: LLMCall = {
        id: callId,
        timestamp: data.timestamp,
        provider: data.providerId,
        model: data.model,
        sessionId: data.sessionId,
        status: 'pending',
        latencyMs: null,
        tokens: null,
        error: null,
        outputPreview: null,
        requestId: data.requestId,
      }

      setCalls((prev) => [newCall, ...prev].slice(0, 500)) // Keep last 500 calls
      setLastUpdateTime(Date.now())
    }

    const handleEnd = (data: ProviderEndEvent) => {
      setInflightRequests((prev) => {
        const next = new Map(prev)
        const inflight = next.get(data.requestId)
        next.delete(data.requestId)
        return next
      })

      // Update the matching call
      setCalls((prev) =>
        prev.map((call) => {
          if (call.requestId === data.requestId) {
            return {
              ...call,
              status: data.error ? 'error' : 'success',
              latencyMs: data.durationMs,
              tokens: {
                input: Math.round(data.tokensUsed * 0.3), // Estimate
                output: Math.round(data.tokensUsed * 0.7),
                total: data.tokensUsed,
              },
              error: data.error,
            }
          }
          return call
        }),
      )
      setLastUpdateTime(Date.now())
    }

    const handleError = (data: ProviderErrorEvent) => {
      setInflightRequests((prev) => {
        const next = new Map(prev)
        next.delete(data.requestId)
        return next
      })

      setCalls((prev) =>
        prev.map((call) => {
          if (call.requestId === data.requestId) {
            return {
              ...call,
              status: 'error',
              error: data.error,
            }
          }
          return call
        }),
      )
      setLastUpdateTime(Date.now())
    }

    const handleDisconnect = () => {
      setConnected(false)
    }

    const handleReconnecting = () => {
      setConnectionError('Reconnecting...')
    }

    client.on('provider:request_start', handleStart)
    client.on('provider:request_end', handleEnd)
    client.on('provider:request_error', handleError)
    client.on('provider:request_timeout', handleEnd)
    client.on('disconnected', handleDisconnect)
    client.on('reconnecting', handleReconnecting)

    return () => {
      client.off('provider:request_start', handleStart)
      client.off('provider:request_end', handleEnd)
      client.off('provider:request_error', handleError)
      client.off('provider:request_timeout', handleEnd)
      client.off('disconnected', handleDisconnect)
      client.off('reconnecting', handleReconnecting)
      client.stopStream()
    }
  }, [client])

  // Update stats periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(calculateStats(calls, filters))

      // Update available providers/models
      const providers = Array.from(new Set(calls.map((c) => c.provider))).sort()
      const models = Array.from(new Set(calls.map((c) => c.model))).sort()
      setAvailableProviders(providers)
      setAvailableModels(models)
    }, DEFAULT_DISPLAY_CONFIG.statsRefreshMs)

    return () => clearInterval(interval)
  }, [calls, filters])

  // Keyboard shortcuts
  useInput((input, key) => {
    if (input === 'q' || (key.ctrl && input === 'c')) {
      client.stopStream()
      exit()
      return
    }

    if (input === '?' || input === 'h') {
      setHelpOpen((prev) => !prev)
      return
    }

    if (input === 'f') {
      setFilterPanelOpen((prev) => !prev)
      return
    }

    if (input === 'd') {
      setShowDetails((prev) => !prev)
      return
    }

    if (input === 't') {
      setShowTokenDetails((prev) => !prev)
      return
    }

    if (input === 'c') {
      setCalls([])
      setInflightRequests(new Map())
      return
    }

    if (input === 'r') {
      setFilters({ ...DEFAULT_FILTERS })
      return
    }

    // Provider filter shortcuts
    if (input === 'p' && availableProviders.length > 0) {
      const currentIndex = availableProviders.indexOf(filters.provider || '')
      const nextIndex = (currentIndex + 1) % (availableProviders.length + 1)
      setFilters((prev) => ({
        ...prev,
        provider: nextIndex === availableProviders.length ? null : availableProviders[nextIndex],
      }))
      return
    }

    // Model filter shortcuts
    if (input === 'm' && availableModels.length > 0) {
      const currentIndex = availableModels.indexOf(filters.model || '')
      const nextIndex = (currentIndex + 1) % (availableModels.length + 1)
      setFilters((prev) => ({
        ...prev,
        model: nextIndex === availableModels.length ? null : availableModels[nextIndex],
      }))
      return
    }

    // Status filter shortcuts
    if (input === 's') {
      const statuses: Array<WatchFilters['status']> = [null, 'pending', 'success', 'error', 'cancelled']
      const currentIndex = statuses.indexOf(filters.status)
      const nextIndex = (currentIndex + 1) % statuses.length
      setFilters((prev) => ({
        ...prev,
        status: statuses[nextIndex],
      }))
      return
    }

    // Errors only toggle
    if (input === 'e') {
      setFilters((prev) => ({
        ...prev,
        errorsOnly: !prev.errorsOnly,
      }))
      return
    }

    // Number keys for latency filters
    if (input >= '0' && input <= '9') {
      const value = parseInt(input) * 100
      if (key.shift) {
        setFilters((prev) => ({ ...prev, maxLatency: value || null }))
      } else {
        setFilters((prev) => ({ ...prev, minLatency: value || null }))
      }
      return
    }
  })

  const handleScroll = useCallback((offset: number) => {
    setScrollOffset(offset)
  }, [])

  const handleSelectCall = useCallback((callId: string | null) => {
    setSelectedCallId(callId)
  }, [])

  const filteredCalls = filterCalls(calls, filters)

  return (
    <Box flexDirection="column">
      {/* Header */}
      <Box marginBottom={1}>
        <Text bold color="cyan">
          ═══════════════════════════════════════════════════════════
        </Text>
      </Box>
      <Box marginBottom={1} justifyContent="space-between">
        <Text bold color="white">
          🎯 CassiWatch — Real-time LLM Call Monitor
        </Text>
        <Text dimColor>v0.1.0</Text>
      </Box>

      {/* Connection error */}
      {connectionError && !connected && (
        <Box
          marginBottom={1}
          padding={1}
          borderStyle="round"
          borderColor="red"
        >
          <Text color="red">⚠ {connectionError}</Text>
        </Box>
      )}

      {/* Filter panel */}
      <FilterPanel
        filters={filters}
        isOpen={filterPanelOpen}
        availableProviders={availableProviders}
        availableModels={availableModels}
      />

      {/* Statistics panel */}
      <StatsPanel stats={stats} filters={{
        provider: filters.provider,
        model: filters.model,
        status: filters.status,
      }} />

      {/* Call list */}
      <CallList
        calls={filteredCalls}
        maxDisplay={DEFAULT_DISPLAY_CONFIG.maxDisplayCalls}
        onScroll={handleScroll}
        scrollOffset={scrollOffset}
        selectedCallId={selectedCallId}
        onSelectCall={handleSelectCall}
        showDetails={showDetails}
      />

      {/* Help overlay */}
      <HelpOverlay isVisible={helpOpen} />

      {/* Status bar */}
      <StatusBar
        connected={connected}
        connectionString={connectionString}
        callCount={calls.length}
        errorCount={stats.byStatus.error}
        lastUpdateTime={lastUpdateTime}
      />
    </Box>
  )
}
