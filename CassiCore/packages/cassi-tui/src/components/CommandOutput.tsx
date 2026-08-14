/**
 * CommandOutput — styled display for a slash command result.
 *
 * Shows the command name as a header, the result text body, and optional
 * action buttons (from the daemon's CommandResult.actions array).
 */

import React from 'react'
import { Box, Text } from 'ink'
import type { CommandAction } from '../types/index.js'

interface Props {
  commandName: string
  text: string
  actions?: CommandAction[]
  onAction?: (command: string) => void
}

export function CommandOutput({
  commandName,
  text,
  actions,
}: Props): React.ReactElement {
  return (
    <Box flexDirection="column" marginY={0}>
      <Box>
        <Text color="yellow" bold>{commandName}</Text>
      </Box>
      {text ? (
        <Box paddingLeft={2}>
          <Text>{text}</Text>
        </Box>
      ) : null}
      {actions && actions.length > 0 ? (
        <Box paddingLeft={2} gap={1} marginTop={0}>
          {actions.map((a, i) => (
            <Text key={i} dimColor>
              {`[${a.label}: ${a.command}]`}
            </Text>
          ))}
        </Box>
      ) : null}
    </Box>
  )
}
