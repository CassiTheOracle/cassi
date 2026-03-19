/**
 * StatsPanel — Summary statistics display
 */

import React from 'react'
import { Box, Text } from 'ink'

import type { WatchStats, LLMCallStatus } from '../types/index.js'

interface StatsPanelProps {
  stats: WatchStats
  filters: {
    provider: string | null
    model: string | null
    status: string | null
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function formatLatency(ms: number | null): string {
  if (ms === null) return 'N/A'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function getStatusColor(status: LLMCallStatus): string {
  switch (status) {
    case 'success':
      return 'green'
    case 'pending':
      return 'yellow'
    case 'error':
      return 'red'
    case 'cancelled':
      return 'gray'
    default:
      return 'white'
  }
}

export function StatsPanel({ stats, filters }: StatsPanelProps): React.ReactElement {
  const filterInfo = []
  if (filters.provider) filterInfo.push(`provider:${filters.provider}`)
  if (filters.model) filterInfo.push(`model:${filters.model}`)
  if (filters.status) filterInfo.push(`status:${filters.status}`)

  return (
    <Box flexDirection="column" borderStyle="round" borderColor="cyan" padding={1} marginBottom={1}>
      <Box justifyContent="space-between">
        <Text bold>📊 LLM Call Statistics</Text>
        {filterInfo.length > 0 && (
          <Text dimColor>Filters: {filterInfo.join(' | ')}</Text>
        )}
      </Box>

      <Box marginTop={1} justifyContent="space-between">
        <Box flexDirection="column">
          <Text>
            <Text bold>Total Calls: </Text>
            <Text color="cyan">{formatNumber(stats.totalCalls)}</Text>
          </Text>
          <Text>
            <Text bold>Avg Latency: </Text>
            <Text color="yellow">{formatLatency(stats.avgLatencyMs)}</Text>
          </Text>
          <Text>
            <Text bold>Error Rate: </Text>
            <Text color={stats.errorRate > 0.1 ? 'red' : 'green'}>
              {(stats.errorRate * 100).toFixed(1)}%
            </Text>
          </Text>
        </Box>

        <Box flexDirection="column" alignItems="flex-end">
          <Text>
            <Text bold>Tokens: </Text>
            <Text color="magenta">{formatNumber(stats.totalTokens)}</Text>
          </Text>
          <Text>
            <Text bold>Calls/min: </Text>
            <Text color="blue">{formatNumber(stats.callsPerMinute)}</Text>
          </Text>
        </Box>
      </Box>

      <Box marginTop={1} flexDirection="column">
        <Text bold dimColor>By Status:</Text>
        <Box justifyContent="space-between">
          <Text>
            <Text color="green">●</Text> Success: {stats.byStatus.success}
          </Text>
          <Text>
            <Text color="yellow">●</Text> Pending: {stats.byStatus.pending}
          </Text>
          <Text>
            <Text color="red">●</Text> Errors: {stats.byStatus.error}
          </Text>
          <Text>
            <Text color="gray">●</Text> Cancelled: {stats.byStatus.cancelled}
          </Text>
        </Box>
      </Box>

      {Object.keys(stats.byProvider).length > 0 && (
        <Box marginTop={1} flexDirection="column">
          <Text bold dimColor>By Provider:</Text>
          <Box flexWrap="wrap">
            {Object.entries(stats.byProvider)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 5)
              .map(([provider, count]) => (
                <Text key={provider} >
                  <Text color="cyan">{provider}:</Text> {count}
                </Text>
              ))}
          </Box>
        </Box>
      )}

      {Object.keys(stats.byModel).length > 0 && (
        <Box marginTop={1} flexDirection="column">
          <Text bold dimColor>Top Models:</Text>
          <Box flexWrap="wrap">
            {Object.entries(stats.byModel)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 5)
              .map(([model, count]) => (
                <Text key={model} >
                  <Text color="magenta">{model}:</Text> {count}
                </Text>
              ))}
          </Box>
        </Box>
      )}
    </Box>
  )
}
