/**
 * HelpOverlay — Keyboard shortcuts and help
 */

import React from 'react'
import { Box, Text } from 'ink'

interface HelpOverlayProps {
  isVisible: boolean
}

export function HelpOverlay({ isVisible }: HelpOverlayProps): React.ReactElement {
  if (!isVisible) {
    return <></>
  }

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor="cyan"
      padding={1}
      
    >
      <Text bold color="cyan">
        ❓ Keyboard Shortcuts (Press '?' or 'h' to toggle)
      </Text>

      <Box  flexDirection="column">
        <Text bold>Navigation:</Text>
        <Box flexDirection="column" marginLeft={2}>
          <Text>↑/↓ — Scroll through calls</Text>
          <Text>PageUp/PageDown — Scroll by page</Text>
          <Text>Home/End — Jump to start/end</Text>
          <Text>Enter — Toggle call selection</Text>
        </Box>

        <Text bold >Filters:</Text>
        <Box flexDirection="column" marginLeft={2}>
          <Text>f — Toggle filter panel</Text>
          <Text>p — Filter by provider</Text>
          <Text>m — Filter by model</Text>
          <Text>s — Filter by status</Text>
          <Text>e — Toggle errors only</Text>
          <Text>0-9 — Set latency thresholds</Text>
          <Text>r — Reset all filters</Text>
        </Box>

        <Text bold >View Options:</Text>
        <Box flexDirection="column" marginLeft={2}>
          <Text>d — Toggle details view</Text>
          <Text>t — Toggle token display</Text>
          <Text>c — Clear call history</Text>
        </Box>

        <Text bold >Application:</Text>
        <Box flexDirection="column" marginLeft={2}>
          <Text>?/h — Toggle this help</Text>
          <Text>q — Quit</Text>
          <Text>Ctrl+C — Force quit</Text>
        </Box>
      </Box>

      <Box  justifyContent="space-between">
        <Text dimColor>
          Status: <Text color="green">●</Text> Success{' '}
          <Text color="yellow">●</Text> Pending{' '}
          <Text color="red">●</Text> Error{' '}
          <Text color="gray">●</Text> Cancelled
        </Text>
      </Box>
    </Box>
  )
}
