/**
 * CallList — Scrollable list of LLM calls
 */

import React, { useRef, useEffect } from 'react'
import { Box, Text, useInput } from 'ink'

import type { LLMCall } from '../types/index.js'
import { CallCard } from './CallCard.js'

interface CallListProps {
  calls: LLMCall[]
  maxDisplay: number
  onScroll: (offset: number) => void
  scrollOffset: number
  selectedCallId: string | null
  onSelectCall: (callId: string | null) => void
  showDetails: boolean
}

export function CallList({
  calls,
  maxDisplay,
  onScroll,
  scrollOffset,
  selectedCallId,
  onSelectCall,
  showDetails,
}: CallListProps): React.ReactElement {
  // Limit displayed calls
  const displayedCalls = calls.slice(0, maxDisplay)

  // Handle keyboard navigation
  useInput((input, key) => {
    if (key.upArrow) {
      onScroll(Math.max(0, scrollOffset - 1))
    } else if (key.downArrow) {
      onScroll(Math.min(calls.length - maxDisplay, scrollOffset + 1))
    } else if (key.pageUp) {
      onScroll(Math.max(0, scrollOffset - maxDisplay))
    } else if (key.pageDown) {
      onScroll(Math.min(calls.length - maxDisplay, scrollOffset + maxDisplay))
    } else if ((key as any).home) {
      onScroll(0)
    } else if ((key as any).end) {
      onScroll(Math.max(0, calls.length - maxDisplay))
    } else if (input === 'Enter' && displayedCalls.length > 0) {
      // Select the first visible call if none selected, or deselect
      if (!selectedCallId && displayedCalls[0]) {
        onSelectCall(displayedCalls[0].id)
      } else {
        onSelectCall(null)
      }
    }
  })

  if (calls.length === 0) {
    return (
      <Box
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        padding={3}
        borderStyle="round"
        borderColor="gray"
      >
        <Text dimColor>No LLM calls yet...</Text>
        <Text dimColor >
          Waiting for events from the daemon
        </Text>
      </Box>
    )
  }

  return (
    <Box flexDirection="column">
      {displayedCalls.map((call, index) => (
        <CallCard
          key={call.id}
          call={call}
          isSelected={call.id === selectedCallId}
          showDetails={showDetails}
        />
      ))}

      {calls.length > maxDisplay && (
        <Box justifyContent="space-between" >
          <Text dimColor>
            Showing {Math.min(maxDisplay, calls.length)} of {calls.length} calls
          </Text>
          <Text dimColor>
            Scroll: {scrollOffset + 1}-{Math.min(scrollOffset + maxDisplay, calls.length)} / {calls.length}
          </Text>
        </Box>
      )}
    </Box>
  )
}
