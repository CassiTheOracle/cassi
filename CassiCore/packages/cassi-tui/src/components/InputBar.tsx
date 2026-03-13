/**
 * InputBar — user input area at the bottom of the TUI.
 *
 * Features:
 *   - Text entry with Enter to submit
 *   - Alt+Enter or Ctrl+J to insert newline (multi-line input)
 *   - Ctrl+C escalation: cancel streaming → clear input → exit
 *   - Ctrl+L to clear screen (triggers onClear callback)
 *   - Tab completion for slash commands (cycles through matches)
 *   - Up/Down arrow for command history recall
 *   - Inline ghost text showing the top completion
 *   - Cursor position tracking for multi-line editing
 */

import React, { useState, useRef, useCallback } from 'react'
import { Box, Text, useInput } from 'ink'

interface Props {
  onSubmit: (text: string) => void
  onCancel: () => void
  isStreaming: boolean
  placeholder?: string
  /** All known command names for tab completion. */
  completions?: string[]
  /** Command input history for up-arrow recall. */
  commandHistory?: string[]
  /** Filter completions by partial input. */
  getCompletions?: (partial: string) => string[]
  /** Clear the conversation display (Ctrl+L). */
  onClear?: () => void
}

/** Maximum lines to show in the input area before truncating the top. */
const MAX_VISIBLE_LINES = 8

export function InputBar({
  onSubmit,
  onCancel,
  isStreaming,
  placeholder = 'Type a message or / for commands...',
  completions = [],
  commandHistory = [],
  getCompletions,
  onClear,
}: Props): React.ReactElement {
  const [input, setInput] = useState('')

  // Tab completion state
  const tabIndexRef = useRef(-1)
  const tabMatchesRef = useRef<string[]>([])
  const tabBaseRef = useRef('')

  // History navigation state
  const historyIndexRef = useRef(-1)
  const savedInputRef = useRef('')

  // Ctrl+C escalation counter: 0 = cancel stream, 1 = clear input, 2 = exit
  const ctrlCCountRef = useRef(0)
  const ctrlCTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Compute the ghost (inline suggestion) — only for single-line slash commands
  const isMultiLine = input.includes('\n')
  const ghost = input.startsWith('/') && !isStreaming && !isMultiLine
    ? getGhost(input, getCompletions ?? defaultGetCompletions(completions))
    : ''

  const lines = input.split('\n')
  const lineCount = lines.length

  useInput((value, key) => {
    // ── Ctrl+C — escalating cancel ────────────────────────────────────
    if (key.ctrl && value === 'c') {
      // Reset the escalation timer on each press
      if (ctrlCTimerRef.current) clearTimeout(ctrlCTimerRef.current)
      ctrlCTimerRef.current = setTimeout(() => {
        ctrlCCountRef.current = 0
      }, 2000)

      if (isStreaming) {
        onCancel()
        ctrlCCountRef.current = 0
        return
      }

      if (input !== '') {
        setInput('')
        resetTab()
        resetHistory()
        ctrlCCountRef.current = 0
        return
      }

      // Input is already empty — escalate toward exit
      ctrlCCountRef.current++
      if (ctrlCCountRef.current >= 2) {
        process.exit(0)
      }
      return
    }

    // Any other key resets the Ctrl+C escalation counter
    ctrlCCountRef.current = 0

    // ── Ctrl+L — clear screen ─────────────────────────────────────────
    if (key.ctrl && value === 'l') {
      onClear?.()
      return
    }

    // ── Alt+Enter or Ctrl+J — insert newline ──────────────────────────
    if ((key.meta && key.return) || (key.ctrl && value === 'j')) {
      setInput((s) => s + '\n')
      resetTab()
      return
    }

    // ── Tab completion ────────────────────────────────────────────────
    if (key.tab && input.startsWith('/') && !isStreaming && !isMultiLine) {
      handleTab()
      return
    }

    // ── Up arrow — command history ────────────────────────────────────
    if (key.upArrow && commandHistory.length > 0 && !isMultiLine) {
      handleHistoryUp()
      return
    }

    // ── Down arrow — command history ─────────────────────────────────
    if (key.downArrow && !isMultiLine) {
      handleHistoryDown()
      return
    }

    // ── Enter — submit ──────────────────────────────────────────────
    if (key.return && !key.meta) {
      const trimmed = input.trim()
      if (trimmed && !isStreaming) {
        onSubmit(trimmed)
        setInput('')
        resetTab()
        resetHistory()
      }
      return
    }

    // ── Backspace ───────────────────────────────────────────────────
    if (key.backspace || key.delete) {
      setInput((s) => s.slice(0, -1))
      resetTab()
      return
    }

    // ── Escape — clear input ────────────────────────────────────────
    if (key.escape) {
      setInput('')
      resetTab()
      resetHistory()
      return
    }

    // ── Ctrl+U — clear line ──────────────────────────────────────────
    if (key.ctrl && value === 'u') {
      setInput('')
      resetTab()
      return
    }

    // ── Ctrl+W — delete last word ────────────────────────────────────
    if (key.ctrl && value === 'w') {
      setInput((s) => s.replace(/\S+\s*$/, ''))
      resetTab()
      return
    }

    // ── Regular character input ─────────────────────────────────────
    if (value && !key.ctrl && !key.meta) {
      setInput((s) => s + value)
      resetTab()
    }
  })

  // ── Tab completion logic ──────────────────────────────────────────────

  function handleTab(): void {
    const resolver = getCompletions ?? defaultGetCompletions(completions)

    if (tabIndexRef.current === -1) {
      const matches = resolver(input)
      if (matches.length === 0) return

      tabMatchesRef.current = matches
      tabBaseRef.current = input
      tabIndexRef.current = 0
      setInput(matches[0]! + ' ')
    } else {
      const matches = tabMatchesRef.current
      if (matches.length === 0) return

      tabIndexRef.current = (tabIndexRef.current + 1) % matches.length
      setInput(matches[tabIndexRef.current]! + ' ')
    }
  }

  function resetTab(): void {
    tabIndexRef.current = -1
    tabMatchesRef.current = []
    tabBaseRef.current = ''
  }

  // ── History navigation ────────────────────────────────────────────────

  function handleHistoryUp(): void {
    if (historyIndexRef.current === -1) {
      savedInputRef.current = input
    }

    const newIndex = Math.min(
      historyIndexRef.current + 1,
      commandHistory.length - 1,
    )

    if (newIndex !== historyIndexRef.current) {
      historyIndexRef.current = newIndex
      const fromEnd = commandHistory[commandHistory.length - 1 - newIndex]
      if (fromEnd) setInput(fromEnd)
    }
  }

  function handleHistoryDown(): void {
    if (historyIndexRef.current <= 0) {
      historyIndexRef.current = -1
      setInput(savedInputRef.current)
      return
    }

    historyIndexRef.current--
    const fromEnd = commandHistory[commandHistory.length - 1 - historyIndexRef.current]
    if (fromEnd) setInput(fromEnd)
  }

  function resetHistory(): void {
    historyIndexRef.current = -1
    savedInputRef.current = ''
  }

  // ── Render ────────────────────────────────────────────────────────────

  // For multi-line input, show only the last MAX_VISIBLE_LINES lines
  const visibleLines = isMultiLine
    ? lines.slice(-MAX_VISIBLE_LINES)
    : lines

  const truncatedLineCount = lines.length - visibleLines.length

  // Streaming indicator
  if (isStreaming) {
    return (
      <Box borderStyle="single" borderColor="yellow" paddingX={1}>
        <Text color="yellow">{'streaming... '}</Text>
        <Text dimColor>{'(Ctrl+C to cancel)'}</Text>
      </Box>
    )
  }

  // Ctrl+C exit hint
  const showExitHint = ctrlCCountRef.current >= 1 && input === ''

  return (
    <Box flexDirection="column">
      {/* Multi-line indicator */}
      {isMultiLine ? (
        <Box paddingX={1}>
          <Text dimColor>
            {`${lineCount} lines`}
            {truncatedLineCount > 0 ? ` (${truncatedLineCount} hidden)` : ''}
            {' — Enter to send, Alt+Enter for newline, Esc to clear'}
          </Text>
        </Box>
      ) : null}

      {/* Input area */}
      <Box borderStyle="single" borderColor={isMultiLine ? 'cyan' : 'gray'} paddingX={1}>
        <Box flexDirection="column" flexGrow={1}>
          {visibleLines.map((line, i) => (
            <Box key={i}>
              {/* Prompt indicator on first visible line */}
              {i === 0 && !isMultiLine ? (
                <Text color="green" bold>{'> '}</Text>
              ) : i === 0 && truncatedLineCount > 0 ? (
                <Text dimColor>{'  '}</Text>
              ) : isMultiLine ? (
                <Text dimColor>{'  '}</Text>
              ) : null}

              {/* Line content */}
              {line ? (
                <Text>{line}</Text>
              ) : i === 0 && !isMultiLine ? (
                <Text dimColor>{placeholder}</Text>
              ) : (
                <Text>{' '}</Text>
              )}

              {/* Ghost text (single-line only, on the last line) */}
              {i === visibleLines.length - 1 && ghost && !isMultiLine ? (
                <Text dimColor>{ghost}</Text>
              ) : null}

              {/* Cursor on the last line */}
              {i === visibleLines.length - 1 ? (
                <Text color="cyan">{'_'}</Text>
              ) : null}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Exit hint */}
      {showExitHint ? (
        <Box paddingX={1}>
          <Text dimColor>{'Press Ctrl+C again to exit'}</Text>
        </Box>
      ) : null}
    </Box>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function getGhost(
  input: string,
  resolver: (partial: string) => string[],
): string {
  if (!input || input.length < 2) return ''
  const matches = resolver(input)
  if (matches.length === 0) return ''
  const top = matches[0]!
  if (top.startsWith(input) && top !== input) {
    return top.slice(input.length)
  }
  return ''
}

function defaultGetCompletions(completions: string[]): (partial: string) => string[] {
  return (partial: string) => {
    const lower = partial.toLowerCase()
    return completions.filter((c) => c.startsWith(lower))
  }
}
