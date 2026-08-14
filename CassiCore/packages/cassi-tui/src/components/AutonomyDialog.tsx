/**
 * AutonomyDialog — blocking confirmation prompt for multi-agent operations.
 *
 * When the daemon's autonomy system requires human approval, this component
 * renders a blocking dialog with approve/reject options.
 */

import React, { useState } from 'react'
import { Box, Text, useInput } from 'ink'

interface Props {
  id: string
  agentId: string
  tool: string
  reason: string
  onApprove: (id: string) => void
  onReject: (id: string) => void
}

export function AutonomyDialog({
  id,
  agentId,
  tool,
  reason,
  onApprove,
  onReject,
}: Props): React.ReactElement {
  const [selected, setSelected] = useState<'approve' | 'reject'>('approve')

  useInput((_input, key) => {
    if (key.leftArrow || key.rightArrow) {
      setSelected((s) => (s === 'approve' ? 'reject' : 'approve'))
    }
    if (key.return) {
      if (selected === 'approve') {
        onApprove(id)
      } else {
        onReject(id)
      }
    }
  })

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor="yellow"
      paddingX={1}
      paddingY={0}
    >
      <Text bold color="yellow">
        {'Autonomy Approval Required'}
      </Text>

      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text bold>{'Agent: '}</Text>
          <Text>{agentId}</Text>
        </Text>
        <Text>
          <Text bold>{'Tool: '}</Text>
          <Text>{tool}</Text>
        </Text>
        <Text>
          <Text bold>{'Reason: '}</Text>
          <Text>{reason}</Text>
        </Text>
      </Box>

      <Box marginTop={1} gap={2}>
        <Text
          color={selected === 'approve' ? 'green' : undefined}
          bold={selected === 'approve'}
          inverse={selected === 'approve'}
        >
          {' Approve '}
        </Text>
        <Text
          color={selected === 'reject' ? 'red' : undefined}
          bold={selected === 'reject'}
          inverse={selected === 'reject'}
        >
          {' Reject '}
        </Text>
        <Text dimColor>{'(arrow keys to select, Enter to confirm)'}</Text>
      </Box>
    </Box>
  )
}
