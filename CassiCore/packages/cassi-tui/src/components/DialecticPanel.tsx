/**
 * DialecticPanel — displays Yang/Yin/Serenity analysis.
 *
 * Shows the latest dialectic signal from the daemon's SSE stream
 * as a compact three-voice summary.
 */

import React from 'react'
import { Box, Text } from 'ink'
import type { DialecticSignalPayload } from '../types/index.js'

interface Props {
  signal: DialecticSignalPayload | null
}

export function DialecticPanel({ signal }: Props): React.ReactElement | null {
  if (!signal) return null

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan" paddingX={1}>
      <Text bold color="cyan">
        {'Dialectic'}
      </Text>

      <VoiceLine label="Yang" color="red" voice={signal.yang} />
      <VoiceLine label="Yin" color="blue" voice={signal.yin} />
      <VoiceLine label="Synth" color="green" voice={signal.serenity} />
    </Box>
  )
}

function VoiceLine({
  label,
  color,
  voice,
}: {
  label: string
  color: string
  voice: { analysis: string; position: string; confidence: number }
}): React.ReactElement {
  return (
    <Box marginTop={0}>
      <Text color={color} bold>
        {`${label} `}
      </Text>
      <Text dimColor>{`(${voice.confidence}%) `}</Text>
      <Text>{truncate(voice.position || voice.analysis, 120)}</Text>
    </Box>
  )
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, max) + '...'
}
