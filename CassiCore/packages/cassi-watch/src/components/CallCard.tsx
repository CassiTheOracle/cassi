/**
 * CallCard — Display a single LLM call
 */

import React from 'react'
import { Box, Text } from 'ink'

import type { LLMCall } from '../types/index.js'

interface CallCardProps {
  call: LLMCall
  isSelected: boolean
  showDetails: boolean
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatLatency(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function getStatusIndicator(status: LLMCall['status']): string {
  switch (status) {
    case 'success':
      return '✓'
    case 'pending':
      return '⟳'
    case 'error':
      return '✗'
    case 'cancelled':
      return '○'
    default:
      return '?'
  }
}

function getStatusColor(status: LLMCall['status']): string {
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

function truncate(str: string | null, maxLen: number): string {
  if (!str) return ''
  if (str.length <= maxLen) return str
  return str.slice(0, maxLen - 3) + '...'
}

export function CallCard({ call, isSelected, showDetails }: CallCardProps): React.ReactElement {
  const statusColor = getStatusColor(call.status)
  const statusIndicator = getStatusIndicator(call.status)

  return (
    <Box
      flexDirection="column"
      borderStyle={isSelected ? 'double' : 'single'}
      borderColor={isSelected ? 'yellow' : statusColor}
      padding={isSelected ? 1 : 0}
      marginBottom={1}
    >
      {/* Header row */}
      <Box justifyContent="space-between">
        <Box>
          <Text color={statusColor} bold>
            {statusIndicator}{' '}
          </Text>
          <Text bold>{call.provider}</Text>
          <Text dimColor> / </Text>
          <Text color="magenta">{call.model}</Text>
        </Box>

        <Box>
          <Text dimColor>{formatTime(call.timestamp)}</Text>
          <Text dimColor> | </Text>
          <Text color={call.latencyMs ? 'yellow' : 'gray'}>
            {formatLatency(call.latencyMs)}
          </Text>
        </Box>
      </Box>

      {/* Details row */}
      <Box marginTop={0} justifyContent="space-between">
        <Box flexDirection="column">
          <Text dimColor>
            Session: <Text color="cyan">{call.sessionId.slice(0, 12)}...</Text>
          </Text>
          {call.tokens && (
            <Text dimColor>
              Tokens:{' '}
              <Text color="blue">
                {call.tokens.input}→{call.tokens.output} ({call.tokens.total})
              </Text>
            </Text>
          )}
        </Box>

        {call.error && (
          <Box flexDirection="column" width={40}>
            <Text color="red" wrap="truncate">
              Error: {truncate(call.error, 50)}
            </Text>
          </Box>
        )}
      </Box>

      {/* Output preview (if enabled and available) */}
      {showDetails && call.outputPreview && (
        <Box
          marginTop={1}
          flexDirection="column"
          borderStyle="single"
          borderColor="gray"
          padding={1}
        >
          <Text bold dimColor>Output Preview:</Text>
          <Text color="white" wrap="wrap">
            {truncate(call.outputPreview, 200)}
          </Text>
        </Box>
      )}
    </Box>
  )
}
