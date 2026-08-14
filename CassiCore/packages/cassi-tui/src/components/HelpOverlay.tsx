/**
 * HelpOverlay — shows available keyboard shortcuts and commands.
 *
 * Triggered by /help (local) or Ctrl+? when no other overlay is active.
 * Press Esc or q to dismiss.
 */

import React from 'react'
import { Box, Text, useInput } from 'ink'

interface Props {
  onClose: () => void
}

export function HelpOverlay({ onClose }: Props): React.ReactElement {
  useInput((value, key) => {
    if (key.escape || value === 'q') {
      onClose()
    }
  })

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor="cyan"
      paddingX={2}
      paddingY={1}
    >
      <Text bold color="cyan">{'CassiTUI Help'}</Text>
      <Text>{''}</Text>

      <Text bold>{'Keyboard Shortcuts'}</Text>
      <Row label="Enter" desc="Send message" />
      <Row label="Alt+Enter / Ctrl+J" desc="Insert newline (multi-line input)" />
      <Row label="Ctrl+C" desc="Cancel stream / Clear input / Exit (escalating)" />
      <Row label="Ctrl+L" desc="Clear conversation display" />
      <Row label="Ctrl+U" desc="Clear current input line" />
      <Row label="Ctrl+W" desc="Delete last word" />
      <Row label="Escape" desc="Clear input / Close overlay" />
      <Row label="Up / Down" desc="Navigate command history" />
      <Row label="Tab" desc="Cycle slash command completions" />
      <Text>{''}</Text>

      <Text bold>{'Commands'}</Text>
      <Row label="/help" desc="Show this help" />
      <Row label="/model" desc="Open model selector" />
      <Row label="/model <name>" desc="Set model directly" />
      <Row label="/sessions" desc="Open session picker" />
      <Row label="/session" desc="Show current session ID" />
      <Row label="/session <id>" desc="Switch to session" />
      <Row label="/new" desc="Start a new session" />
      <Row label="/clear" desc="Clear conversation display" />
      <Row label="/exit, /quit, /q" desc="Exit CassiTUI" />
      <Text>{''}</Text>

      <Text dimColor>{'Other / commands are forwarded to the daemon.'}</Text>
      <Text dimColor>{'Press Esc or q to close this help.'}</Text>
    </Box>
  )
}

function Row({
  label,
  desc,
}: {
  label: string
  desc: string
}): React.ReactElement {
  return (
    <Box>
      <Box width={22}>
        <Text color="yellow">{label}</Text>
      </Box>
      <Text dimColor>{desc}</Text>
    </Box>
  )
}
