/**
 * ThinkerIndicator — shows when the Thinker module is active.
 *
 * Displays a spinner and the trigger reason while Think/Ponder cycles run.
 */

import React from 'react'
import { Box, Text } from 'ink'
import Spinner from 'ink-spinner'

interface Props {
  active: boolean
  level: string
  trigger: string
  lastInsight: string | null
}

export function ThinkerIndicator({
  active,
  level,
  trigger,
  lastInsight,
}: Props): React.ReactElement | null {
  if (!active && !lastInsight) return null

  return (
    <Box flexDirection="column">
      {active ? (
        <Box>
          <Text color="magenta">
            <Spinner type="dots" />
          </Text>
          <Text color="magenta" bold>
            {` ${level || 'Thinking'}...`}
          </Text>
          {trigger ? <Text dimColor>{` ${trigger}`}</Text> : null}
        </Box>
      ) : null}
      {lastInsight ? (
        <Box marginTop={0}>
          <Text color="magenta" dimColor>
            {'insight: '}
          </Text>
          <Text dimColor>{truncate(lastInsight, 200)}</Text>
        </Box>
      ) : null}
    </Box>
  )
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '...'
}
