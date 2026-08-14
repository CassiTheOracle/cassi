/**
 * StatusBar — top bar showing connection status, model, and session info.
 *
 * Shows enriched model display with health indicators, short name,
 * and token usage from the last turn.
 */

import React from 'react'
import { Box, Text } from 'ink'
import type { ModelInfo } from '../types/index.js'

interface Props {
  connected: boolean
  connectionString: string
  model: string | null
  modelInfo: ModelInfo | null
  sessionId: string | null
  isStreaming: boolean
  tokenCount: number
  inputTokens: number
  outputTokens: number
}

export function StatusBar({
  connected,
  connectionString,
  model,
  modelInfo,
  sessionId,
  isStreaming,
  tokenCount,
  inputTokens,
  outputTokens,
}: Props): React.ReactElement {
  // Model display with health indicator
  const modelHealthColor = modelInfo?.providerStatus === 'ok'
    ? 'green'
    : modelInfo?.providerStatus === 'degraded'
      ? 'yellow'
      : 'red'

  const modelDot = modelInfo?.providerStatus === 'ok'
    ? '●'
    : modelInfo?.providerStatus === 'degraded'
      ? '◐'
      : '○'

  const modelDisplay = modelInfo
    ? `${modelDot} ${modelInfo.shortName}`
    : model
      ? model
      : null

  return (
    <Box paddingX={1} justifyContent="space-between">
      <Box gap={2}>
        <Text bold color="cyan">
          {'cassi'}
        </Text>
        <Text color={connected ? 'green' : 'red'}>
          {connected ? `connected (${connectionString})` : 'disconnected'}
        </Text>
        {modelDisplay ? (
          <Text color={modelHealthColor} dimColor={!modelInfo}>
            {modelDisplay}
          </Text>
        ) : null}
      </Box>

      <Box gap={2}>
        {/* Token usage from last turn */}
        {(inputTokens > 0 || outputTokens > 0) && !isStreaming ? (
          <Text dimColor>
            {`${formatTokens(inputTokens)}in/${formatTokens(outputTokens)}out`}
          </Text>
        ) : null}

        {/* Streaming indicator */}
        {isStreaming ? (
          <Text color="yellow">{`streaming (${formatTokens(tokenCount)})`}</Text>
        ) : null}

        {/* Session ID */}
        {sessionId ? (
          <Text dimColor>{`session:${truncateId(sessionId)}`}</Text>
        ) : null}
      </Box>
    </Box>
  )
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return `${n}`
}

function truncateId(id: string): string {
  // Keep the prefix (e.g., "oc:") and first 8 chars of the hash
  const parts = id.split(':')
  if (parts.length >= 2) {
    const prefix = parts.slice(0, -1).join(':')
    const hash = parts[parts.length - 1]!
    return `${prefix}:${hash.slice(0, 8)}`
  }
  return id.slice(0, 12)
}
