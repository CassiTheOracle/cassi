/**
 * ToolCallBlock — renders a single tool call with its result.
 *
 * Display modes:
 *   - Running:  spinner + tool name + summary of input
 *   - Done:     checkmark + tool name + summary + output preview (collapsed by default)
 *   - Failed:   cross + tool name + error message
 *
 * The block is compact by default (single line). When expanded,
 * it shows the tool input parameters and result content.
 */

import React, { useState } from 'react'
import { Box, Text, useInput } from 'ink'
import Spinner from 'ink-spinner'
import {
  formatToolName,
  formatToolSummary,
  formatToolOutput,
  byteSize,
  trunc,
} from '../utils/format-tool.js'

export interface ToolCallData {
  id: string
  name: string
  input: string
  finished: boolean
  startedAt?: number
  finishedAt?: number
}

export interface ToolResultData {
  toolCallId: string
  name: string
  content: string
  isError: boolean
}

interface Props {
  call: ToolCallData
  result?: ToolResultData
  /** Whether this block can be expanded (only in history, not during streaming). */
  interactive?: boolean
  /** Whether this tool block currently has focus for keyboard interaction. */
  focused?: boolean
}

export function ToolCallBlock({
  call,
  result,
  interactive = false,
  focused = false,
}: Props): React.ReactElement {
  const [expanded, setExpanded] = useState(false)

  // Toggle expand on Enter when focused
  useInput(
    (_input, key) => {
      if (key.return && interactive && focused) {
        setExpanded((e) => !e)
      }
    },
    { isActive: interactive && focused },
  )

  const status = result
    ? result.isError
      ? 'failed'
      : 'done'
    : call.finished
      ? 'done'
      : 'running'

  const displayName = formatToolName(call.name)
  const summary = formatToolSummary(call.name, call.input)

  // Duration: frozen at finishedAt if available, otherwise live elapsed
  const durationStr = call.startedAt
    ? call.finishedAt
      ? formatDuration(call.finishedAt - call.startedAt)
      : call.finished
        ? null  // Finished but no finishedAt (historical data)
        : formatDuration(Date.now() - call.startedAt)  // Still running — live counter
    : null

  return (
    <Box flexDirection="column">
      {/* Main summary line */}
      <Box>
        <StatusIcon status={status} />
        <Text bold color={statusColor(status)}>
          {displayName}
        </Text>
        {summary ? (
          <Text dimColor>{` ${trunc(summary, 55)}`}</Text>
        ) : null}
        {/* Metadata: size, duration */}
        <MetaBadges
          result={result}
          durationStr={durationStr}
          expanded={expanded}
          interactive={interactive}
        />
      </Box>

      {/* Expanded detail */}
      {expanded && result ? (
        <ExpandedResult result={result} call={call} />
      ) : null}

      {/* Inline error for failed tools (always visible, not just when expanded) */}
      {!expanded && result?.isError ? (
        <Box marginLeft={3}>
          <Text color="red">{trunc(result.content, 120)}</Text>
        </Box>
      ) : null}
    </Box>
  )
}


function StatusIcon({ status }: { status: string }): React.ReactElement {
  if (status === 'running') {
    return (
      <Box marginRight={1}>
        <Text color="yellow">
          <Spinner type="dots" />
        </Text>
      </Box>
    )
  }

  const icon = status === 'failed' ? '\u2718' : '\u2714'
  const color = status === 'failed' ? 'red' : 'green'

  return (
    <Box marginRight={1}>
      <Text color={color} bold>
        {icon}
      </Text>
    </Box>
  )
}

function MetaBadges({
  result,
  durationStr,
  expanded,
  interactive,
}: {
  result?: ToolResultData
  durationStr: string | null
  expanded: boolean
  interactive: boolean
}): React.ReactElement {
  // Combine size and duration into a single compact badge: (497B, 800ms)
  const parts: string[] = []
  if (result && !result.isError && result.content) {
    parts.push(byteSize(result.content))
  }
  if (durationStr) {
    parts.push(durationStr)
  }

  return (
    <Box>
      {parts.length > 0 ? (
        <Text dimColor>{` (${parts.join(', ')})`}</Text>
      ) : null}
      {/* Expand hint */}
      {interactive && result ? (
        <Text dimColor>{expanded ? ' [-]' : ' [+]'}</Text>
      ) : null}
    </Box>
  )
}

function ExpandedResult({
  result,
  call,
}: {
  result: ToolResultData
  call: ToolCallData
}): React.ReactElement {
  const { preview, overflow } = formatToolOutput(result.content, 15)

  return (
    <Box flexDirection="column" marginLeft={3} marginBottom={0}>
      {/* Tool input (dimmed) */}
      {call.input ? (
        <Box>
          <Text dimColor italic>
            {'input: '}
            {trunc(call.input, 200)}
          </Text>
        </Box>
      ) : null}

      {/* Result content */}
      {result.isError ? (
        <Text color="red">{preview}</Text>
      ) : (
        <Text dimColor>{preview}</Text>
      )}

      {/* Overflow indicator */}
      {overflow ? (
        <Text dimColor italic>
          {overflow}
        </Text>
      ) : null}
    </Box>
  )
}


function statusColor(status: string): string {
  switch (status) {
    case 'failed':
      return 'red'
    case 'done':
      return 'green'
    default:
      return 'yellow'
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}m`
}
