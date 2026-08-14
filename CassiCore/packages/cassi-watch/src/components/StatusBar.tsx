/**
 * StatusBar — Connection status and quick info
 */

import React from 'react'
import { Box, Text } from 'ink'

interface StatusBarProps {
  connected: boolean
  connectionString: string
  callCount: number
  errorCount: number
  lastUpdateTime: number | null
}

function formatTimeAgo(timestamp: number | null): string {
  if (!timestamp) return 'Never'
  const diff = Date.now() - timestamp
  if (diff < 1000) return 'Just now'
  if (diff < 60000) return `${Math.round(diff / 1000)}s ago`
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`
  return `${Math.round(diff / 3600000)}h ago`
}

export function StatusBar({
  connected,
  connectionString,
  callCount,
  errorCount,
  lastUpdateTime,
}: StatusBarProps): React.ReactElement {
  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={connected ? 'green' : 'red'}
      padding={1}
      marginTop={1}
    >
      <Box justifyContent="space-between">
        <Box>
          <Text
            color={connected ? 'green' : 'red'}
            bold
          >
            {connected ? '●' : '○'}{' '}
            {connected ? 'Connected' : 'Disconnected'}
          </Text>
          <Text dimColor> | </Text>
          <Text dimColor>{connectionString}</Text>
        </Box>

        <Box>
          <Text dimColor>
            Calls: <Text color="cyan">{callCount}</Text>
          </Text>
          {errorCount > 0 && (
            <>
              <Text dimColor> | </Text>
              <Text color="red">
                Errors: {errorCount}
              </Text>
            </>
          )}
          <Text dimColor> | </Text>
          <Text dimColor>
            Updated: {formatTimeAgo(lastUpdateTime)}
          </Text>
        </Box>
      </Box>
    </Box>
  )
}
