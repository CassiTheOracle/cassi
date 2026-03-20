/**
 * ModelSelector — interactive model picker with health indicators.
 *
 * Features:
 *   - Arrow key navigation (Up/Down)
 *   - Type-to-filter (any keystrokes narrow the list)
 *   - Enter to select, Esc to cancel
 *   - Shows context window, reasoning badge, provider health
 *   - Groups by provider, marks currently active model
 */

import React, { useState, useEffect } from 'react'
import { Box, Text, useInput } from 'ink'
import type { ModelInfo } from '../types/index.js'

interface Props {
  models: ModelInfo[]
  currentModel: string | null
  onSelect: (modelId: string) => void
  onCancel: () => void
}

export function ModelSelector({
  models,
  currentModel,
  onSelect,
  onCancel,
}: Props): React.ReactElement {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [filter, setFilter] = useState('')

  // Filter models by typed text
  const filtered = models.filter(
    (m) =>
      m.shortName.toLowerCase().includes(filter.toLowerCase()) ||
      m.providerId.toLowerCase().includes(filter.toLowerCase()),
  )

  // Ensure selected index is in bounds
  useEffect(() => {
    if (selectedIndex >= filtered.length) {
      setSelectedIndex(Math.max(0, filtered.length - 1))
    }
  }, [filtered.length])

  useInput((value, key) => {
    // Escape — cancel
    if (key.escape) {
      onCancel()
      return
    }

    // Enter — select
    if (key.return) {
      if (filtered.length > 0) {
        onSelect(filtered[selectedIndex]!.id)
      }
      return
    }

    // Up arrow
    if (key.upArrow) {
      setSelectedIndex((i) => Math.max(0, i - 1))
      return
    }

    // Down arrow
    if (key.downArrow) {
      setSelectedIndex((i) => Math.min(filtered.length - 1, i + 1))
      return
    }

    // Page up/down
    if (key.pageDown) {
      setSelectedIndex((i) => Math.min(filtered.length - 1, i + 5))
      return
    }
    if (key.pageUp) {
      setSelectedIndex((i) => Math.max(0, i - 5))
      return
    }

    // Tab — cycle through matches
    if (key.tab) {
      setSelectedIndex((i) => (i + 1) % filtered.length)
      return
    }

    // Regular character input — filter
    if (value && !key.ctrl && !key.meta) {
      setFilter((f) => f + value)
      setSelectedIndex(0)
      return
    }

    // Backspace — clear filter char
    if (key.backspace || key.delete) {
      setFilter((f) => f.slice(0, -1))
      setSelectedIndex(0)
      return
    }
  })

  // Group by provider with offset tracking
  const grouped = filtered.reduce((acc, m) => {
    acc[m.providerId] = acc[m.providerId] || []
    acc[m.providerId]!.push(m)
    return acc
  }, {} as Record<string, ModelInfo[]>)

  const providerOrder = Object.keys(grouped)

  // Build a flat list with global indices for rendering
  const flatList: Array<{ model: ModelInfo; providerId: string; globalIndex: number }> = []
  let idx = 0
  for (const providerId of providerOrder) {
    for (const model of grouped[providerId]!) {
      flatList.push({ model, providerId, globalIndex: idx++ })
    }
  }

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan" paddingX={1}>
      {/* Header */}
      <Box justifyContent="space-between">
        <Text bold color="cyan">
          {'Select Model'}
        </Text>
        <Text dimColor>
          {filter ? `filter: "${filter}"` : 'type to filter'}
        </Text>
      </Box>

      <Box marginBottom={0}>
        <Text dimColor>
          {'↑↓ navigate  Enter select  Esc cancel  Tab cycle'}
        </Text>
      </Box>

      {/* Model list */}
      <Box flexDirection="column" marginTop={0}>
        {flatList.length === 0 ? (
          <Text dimColor>{'No models match filter'}</Text>
        ) : (
          providerOrder.map((providerId) => {
            const providerModels = grouped[providerId]!
            const startIndex = flatList.findIndex((item) => item.providerId === providerId)
            return (
              <ProviderGroup
                key={providerId}
                providerId={providerId}
                models={providerModels}
                startIndex={startIndex}
                selectedIndex={selectedIndex}
                currentModel={currentModel}
              />
            )
          })
        )}
      </Box>

      {/* Selected model preview */}
      {filtered.length > 0 ? (
        <ModelPreview model={filtered[selectedIndex]!} />
      ) : null}
    </Box>
  )
}


function ProviderGroup({
  providerId,
  models,
  startIndex,
  selectedIndex,
  currentModel,
}: {
  providerId: string
  models: ModelInfo[]
  startIndex: number
  selectedIndex: number
  currentModel: string | null
}): React.ReactElement {
  const healthColor =
    models[0]?.providerStatus === 'ok'
      ? 'green'
      : models[0]?.providerStatus === 'degraded'
        ? 'yellow'
        : 'red'

  const healthDot =
    models[0]?.providerStatus === 'ok'
      ? '●'
      : models[0]?.providerStatus === 'degraded'
        ? '◐'
        : '○'

  return (
    <Box flexDirection="column" marginTop={0}>
      <Box>
        <Text color={healthColor} bold>
          {`${healthDot} ${providerId}`}
        </Text>
      </Box>
      {models.map((m, localIdx) => {
        const globalIndex = startIndex + localIdx
        const isSelected = globalIndex === selectedIndex
        const isCurrent = m.id === currentModel

        return (
          <ModelRow
            key={m.id}
            model={m}
            isSelected={isSelected}
            isCurrent={isCurrent}
          />
        )
      })}
    </Box>
  )
}


function ModelRow({
  model,
  isSelected,
  isCurrent,
}: {
  model: ModelInfo
  isSelected: boolean
  isCurrent: boolean
}): React.ReactElement {
  const ctxLabel = formatContextWindow(model.contextWindow)
  const reasonBadge = model.reasoning ? '[reasoning]' : ''

  return (
    <Box>
      {/* Selection indicator */}
      <Text color={isSelected ? 'cyan' : undefined}>
        {isSelected ? '▸ ' : isCurrent ? '• ' : '  '}
      </Text>

      {/* Model name */}
      <Text bold={isSelected} color={isSelected ? 'cyan' : undefined}>
        {model.shortName.padEnd(25)}
      </Text>

      {/* Context window */}
      <Text dimColor>{` ${ctxLabel}`}</Text>

      {/* Reasoning badge */}
      {reasonBadge ? (
        <Text dimColor color={model.reasoning ? 'magenta' : undefined}>
          {` ${reasonBadge}`}
        </Text>
      ) : null}

      {/* Current marker */}
      {isCurrent && !isSelected ? (
        <Text color="green" bold>
          {' (current)'}
        </Text>
      ) : null}
    </Box>
  )
}


function ModelPreview({ model }: { model: ModelInfo }): React.ReactElement {
  return (
    <Box marginTop={0} paddingTop={0} borderStyle="single" borderColor="gray">
      <Text dimColor>
        {`${model.name} • ${model.api} • max ${formatTokens(model.maxTokens)}`}
      </Text>
    </Box>
  )
}


function formatContextWindow(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(0)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(0)}k`
  return `${tokens}`
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(0)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(0)}k`
  return `${tokens}`
}
