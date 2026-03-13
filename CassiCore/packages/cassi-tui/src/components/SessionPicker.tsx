/**
 * SessionPicker — interactive session browser with preview.
 *
 * Features:
 *   - Arrow key navigation (Up/Down)
 *   - Type-to-filter (keystrokes narrow the list by title/message)
 *   - Enter to select, Esc to cancel
 *   - Shows session title, last message preview, age, message count
 *   - Highlights the currently active session
 *   - "New Session" option at the top
 */

import React, { useState, useEffect } from 'react'
import { Box, Text, useInput } from 'ink'
import type { DaemonSession } from '../types/index.js'

interface Props {
  sessions: DaemonSession[]
  currentSessionId: string
  loading?: boolean
  onSelect: (sessionId: string) => void
  onNewSession: () => void
  onCancel: () => void
}

/** Items in the picker list. Index 0 is always "New Session". */
interface PickerItem {
  type: 'new' | 'session'
  session?: DaemonSession
}

export function SessionPicker({
  sessions,
  currentSessionId,
  loading = false,
  onSelect,
  onNewSession,
  onCancel,
}: Props): React.ReactElement {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [filter, setFilter] = useState('')

  // Build filtered item list: "New Session" + filtered sessions
  const filteredSessions = sessions.filter((s) => {
    if (!filter) return true
    const lower = filter.toLowerCase()
    return (
      s.id.toLowerCase().includes(lower) ||
      (s.title ?? '').toLowerCase().includes(lower) ||
      s.firstMessage.toLowerCase().includes(lower) ||
      s.lastMessage.toLowerCase().includes(lower)
    )
  })

  const items: PickerItem[] = [
    { type: 'new' },
    ...filteredSessions.map((s) => ({ type: 'session' as const, session: s })),
  ]

  // Keep selection in bounds
  useEffect(() => {
    if (selectedIndex >= items.length) {
      setSelectedIndex(Math.max(0, items.length - 1))
    }
  }, [items.length]) // eslint-disable-line react-hooks/exhaustive-deps

  useInput((value, key) => {
    if (key.escape) {
      onCancel()
      return
    }

    if (key.return) {
      const item = items[selectedIndex]
      if (item?.type === 'new') {
        onNewSession()
      } else if (item?.session) {
        onSelect(item.session.id)
      }
      return
    }

    if (key.upArrow) {
      setSelectedIndex((i) => Math.max(0, i - 1))
      return
    }

    if (key.downArrow) {
      setSelectedIndex((i) => Math.min(items.length - 1, i + 1))
      return
    }

    if (key.backspace || key.delete) {
      setFilter((f) => f.slice(0, -1))
      return
    }

    // Type to filter
    if (value && !key.ctrl && !key.meta && !key.tab) {
      setFilter((f) => f + value)
    }
  })

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor="cyan"
      paddingX={1}
    >
      {/* Header */}
      <Box>
        <Text bold color="cyan">{'Sessions'}</Text>
        {filter ? (
          <Text dimColor>{` — filter: "${filter}"`}</Text>
        ) : null}
        <Box flexGrow={1} />
        <Text dimColor>{'Esc to close'}</Text>
      </Box>

      {/* Loading state */}
      {loading ? (
        <Box marginTop={1}>
          <Text dimColor>{'Loading sessions...'}</Text>
        </Box>
      ) : null}

      {/* Item list */}
      {!loading ? (
        <Box flexDirection="column" marginTop={1}>
          {items.map((item, i) => (
            <SessionItem
              key={item.type === 'new' ? '__new__' : item.session!.id}
              item={item}
              selected={i === selectedIndex}
              isCurrent={
                item.type === 'session' && item.session!.id === currentSessionId
              }
            />
          ))}

          {items.length === 1 && filter ? (
            <Text dimColor>{'No sessions match filter'}</Text>
          ) : null}
        </Box>
      ) : null}

      {/* Footer */}
      <Box marginTop={1}>
        <Text dimColor>
          {`${filteredSessions.length} session${filteredSessions.length === 1 ? '' : 's'}`}
        </Text>
      </Box>
    </Box>
  )
}

// ── Session item row ────────────────────────────────────────────────────────

function SessionItem({
  item,
  selected,
  isCurrent,
}: {
  item: PickerItem
  selected: boolean
  isCurrent: boolean
}): React.ReactElement {
  if (item.type === 'new') {
    return (
      <Box>
        <Text color={selected ? 'cyan' : undefined} bold={selected}>
          {selected ? '> ' : '  '}
        </Text>
        <Text color="green" bold>{'+ New Session'}</Text>
      </Box>
    )
  }

  const s = item.session!
  const title = s.title ?? truncate(s.firstMessage, 40) ?? s.id
  const age = relativeTime(s.lastActiveAt)
  const shortId = s.id.length > 12 ? s.id.slice(0, 12) : s.id

  return (
    <Box>
      {/* Selection indicator */}
      <Text color={selected ? 'cyan' : undefined} bold={selected}>
        {selected ? '> ' : '  '}
      </Text>

      {/* Current session marker */}
      {isCurrent ? (
        <Text color="green">{'● '}</Text>
      ) : (
        <Text>{'  '}</Text>
      )}

      {/* Title / first message preview */}
      <Text bold={selected}>{truncate(title, 45)}</Text>

      {/* Metadata */}
      <Box flexGrow={1} />
      <Text dimColor>{`${s.historyLength}msg `}</Text>
      <Text dimColor>{age}</Text>
      <Text dimColor>{` ${shortId}`}</Text>
    </Box>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function truncate(s: string, max: number): string {
  if (!s) return ''
  const clean = s.replace(/\n/g, ' ').trim()
  if (clean.length <= max) return clean
  return clean.slice(0, max) + '...'
}

function relativeTime(ts: number): string {
  const diff = Date.now() - ts
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}
