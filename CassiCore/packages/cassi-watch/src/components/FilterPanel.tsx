/**
 * FilterPanel — Interactive filter controls
 */

import React from 'react'
import { Box, Text } from 'ink'

import type { WatchFilters, LLMCallStatus } from '../types/index.js'

interface FilterPanelProps {
  filters: WatchFilters
  isOpen: boolean
  availableProviders: string[]
  availableModels: string[]
}

export function FilterPanel({
  filters,
  isOpen,
  availableProviders,
  availableModels,
}: FilterPanelProps): React.ReactElement {
  if (!isOpen) {
    return (
      <Box borderStyle="single" borderColor="yellow" padding={1} marginBottom={1}>
        <Text color="yellow">
          Filters: [
          {filters.provider && <Text> provider:{filters.provider} </Text>}
          {filters.model && <Text> model:{filters.model} </Text>}
          {filters.status && <Text> status:{filters.status} </Text>}
          {filters.minLatency && <Text> min:{filters.minLatency}ms </Text>}
          {filters.maxLatency && <Text> max:{filters.maxLatency}ms </Text>}
          {filters.errorsOnly && <Text> errors-only </Text>}
          {!filters.provider && !filters.model && !filters.status && !filters.minLatency && !filters.maxLatency && !filters.errorsOnly && (
            <Text dimColor> none </Text>
          )}
          ] — Press 'f' to edit
        </Text>
      </Box>
    )
  }

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor="yellow"
      padding={1}
      marginBottom={1}
    >
      <Text bold color="yellow">
        🔍 Filter Controls (Press 'f' to close)
      </Text>

      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text bold>Provider:</Text>{' '}
          {filters.provider || <Text dimColor>any</Text>}
        </Text>
        {availableProviders.length > 0 && (
          <Box flexWrap="wrap" marginTop={0}>
            {availableProviders.map((p) => (
              <Text
                key={p}
                color={filters.provider === p ? 'green' : 'gray'}
                
              >
                [{p}]
              </Text>
            ))}
          </Box>
        )}
      </Box>

      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text bold>Model:</Text>{' '}
          {filters.model || <Text dimColor>any</Text>}
        </Text>
        {availableModels.length > 0 && (
          <Box flexWrap="wrap" marginTop={0}>
            {availableModels.slice(0, 10).map((m) => (
              <Text
                key={m}
                color={filters.model === m ? 'green' : 'gray'}
                
              >
                [{m}]
              </Text>
            ))}
          </Box>
        )}
      </Box>

      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text bold>Status:</Text>{' '}
          {filters.status || <Text dimColor>any</Text>}
        </Text>
        <Box flexWrap="wrap" marginTop={0}>
          {(['pending', 'success', 'error', 'cancelled'] as LLMCallStatus[]).map((s) => (
            <Text
              key={s}
              color={filters.status === s ? 'green' : 'gray'}
              
            >
              [{s}]
            </Text>
          ))}
        </Box>
      </Box>

      <Box marginTop={1} flexDirection="column">
        <Text>
          <Text bold>Latency Range:</Text>{' '}
          {filters.minLatency || 0}ms — {filters.maxLatency || '∞'}ms
        </Text>
        <Text dimColor>
          Use number keys to set min latency, Shift+number for max
        </Text>
      </Box>

      <Box marginTop={1}>
        <Text
          color={filters.errorsOnly ? 'red' : 'gray'}
        >
          [e] Errors only: {filters.errorsOnly ? 'ON' : 'OFF'}
        </Text>
      </Box>

      <Box marginTop={1}>
        <Text dimColor>
          Press 'r' to reset all filters
        </Text>
      </Box>
    </Box>
  )
}
