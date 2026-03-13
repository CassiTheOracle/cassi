/**
 * ConversationPanel — renders message history and live streaming turn.
 *
 * Exports:
 *   - MessageBlock:       renders a single completed message (for Static items)
 *   - LiveTurn:           renders the current streaming turn (for dynamic area)
 *   - ConversationPanel:  combines both (legacy, still usable)
 *
 * Each message is styled by role:
 *   - user:      dimmed, prefixed with >
 *   - assistant: main text with tool calls and thinking
 *   - command:   boxed output via CommandOutput
 *   - system:    dimmed italic (connection messages, session switches)
 */

import React from 'react'
import { Box, Text } from 'ink'
import Spinner from 'ink-spinner'
import { CommandOutput } from './CommandOutput.js'
import { ToolCallBlock } from './ToolCallBlock.js'
import { MarkdownText } from './MarkdownText.js'
import type { DisplayMessage } from '../types/index.js'
import type { ToolCall, ToolResult } from '../hooks/index.js'
import { trunc } from '../utils/format-tool.js'

function countWords(text: string): number {
  return text.split(/\s+/).filter(Boolean).length
}

// ── Types ───────────────────────────────────────────────────────────────────

export interface CurrentTurn {
  text: string
  thinking: string
  toolCalls: ToolCall[]
  toolResults: ToolResult[]
  isStreaming: boolean
  error: string | null
}

// ── MessageBlock — renders a single completed message ───────────────────────

interface MessageBlockProps {
  message: DisplayMessage
  onAction?: (command: string) => void
}

export function MessageBlock({
  message: msg,
  onAction,
}: MessageBlockProps): React.ReactElement {
  // User messages
  if (msg.role === 'user') {
    return (
      <Box marginTop={1}>
        <Text dimColor bold>{'> '}</Text>
        <Text dimColor>{trunc(msg.content, 2000)}</Text>
      </Box>
    )
  }

  // Command responses
  if (msg.role === 'command') {
    return (
      <CommandOutput
        commandName={msg.commandName ?? ''}
        text={msg.content}
        actions={msg.actions}
        onAction={onAction}
      />
    )
  }

  // System messages (session switches, connections, etc.)
  if (msg.role === 'system') {
    return (
      <Box marginTop={1}>
        <Text dimColor italic>{msg.content}</Text>
      </Box>
    )
  }

  // Assistant messages — the main content
  return (
    <Box flexDirection="column" marginTop={1}>
      {/* Thinking (collapsed indicator with word count) */}
      {msg.thinking ? (
        <Box>
          <Text color="magenta" dimColor>
            {`  \u25B6 thinking (${countWords(msg.thinking)} words)`}
          </Text>
        </Box>
      ) : null}

      {/* Tool calls */}
      {msg.toolCalls?.map((tc) => {
        const result = msg.toolResults?.find((r) => r.toolCallId === tc.id)
        return (
          <ToolCallBlock
            key={tc.id}
            call={tc}
            result={result}
          />
        )
      })}

      {/* Text content — render as markdown */}
      {msg.content ? (
        <MarkdownText content={msg.content} />
      ) : null}
    </Box>
  )
}

// ── LiveTurn — renders the current streaming turn ───────────────────────────

interface LiveTurnProps {
  turn: CurrentTurn
}

export function LiveTurn({ turn }: LiveTurnProps): React.ReactElement | null {
  if (!turn.isStreaming) return null

  return (
    <Box flexDirection="column" marginTop={1}>
      {/* Thinking stream */}
      {turn.thinking ? (
        <Box>
          <Text color="magenta" dimColor>{'[thinking] '}</Text>
          <Text dimColor>{trunc(turn.thinking, 200)}</Text>
        </Box>
      ) : null}

      {/* In-progress tool calls */}
      {turn.toolCalls.map((tc) => {
        const result = turn.toolResults.find((r) => r.toolCallId === tc.id)
        return (
          <ToolCallBlock
            key={tc.id}
            call={tc}
            result={result}
          />
        )
      })}

      {/* Streaming text — render as markdown (may be partial) */}
      {turn.text ? (
        <Box flexDirection="column">
          <MarkdownText content={turn.text} streaming />
          <Text color="cyan">{'_'}</Text>
        </Box>
      ) : null}

      {/* Waiting indicator */}
      {!turn.text && !turn.thinking && turn.toolCalls.length === 0 ? (
        <Box>
          <Text color="cyan">
            <Spinner type="dots" />
          </Text>
          <Text dimColor>{' thinking...'}</Text>
        </Box>
      ) : null}

      {/* Error */}
      {turn.error ? (
        <Box>
          <Text color="red" bold>{'Error: '}</Text>
          <Text color="red">{turn.error}</Text>
        </Box>
      ) : null}
    </Box>
  )
}

// ── ConversationPanel — combined view (legacy) ──────────────────────────────

interface Props {
  messages: DisplayMessage[]
  currentTurn: CurrentTurn | null
  onAction?: (command: string) => void
}

export function ConversationPanel({
  messages,
  currentTurn,
  onAction,
}: Props): React.ReactElement {
  return (
    <Box flexDirection="column" flexGrow={1}>
      {messages.map((msg) => (
        <MessageBlock key={msg.id} message={msg} onAction={onAction} />
      ))}

      {currentTurn?.isStreaming ? (
        <LiveTurn turn={currentTurn} />
      ) : null}

      {messages.length === 0 && !currentTurn?.isStreaming ? (
        <Text dimColor>{'Type a message or /help for commands.'}</Text>
      ) : null}
    </Box>
  )
}
