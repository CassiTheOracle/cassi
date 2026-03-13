'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '@/store'
import Icon from '@/components/ui/icon'

// ── Types ────────────────────────────────────────────────────────────────────

interface DialecticEntry {
  id: string
  voice: 'yang' | 'yin' | 'serenity'
  content: string
  confidence: number
  timestamp: number
  turnIndex?: number
  sessionId?: string
}

interface DialecticColumnProps {
  voice: 'yin' | 'yang'
  collapsed: boolean
  onToggle: () => void
}

// ── Voice theme config ───────────────────────────────────────────────────────

const VOICE_THEMES = {
  yin: {
    label: 'Yin',
    subtitle: 'Caution & Nuance',
    accentColor: 'text-blue-400',
    bgAccent: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
    dotColor: 'bg-blue-400',
    barColor: 'bg-blue-400',
    headerBg: 'bg-blue-500/5',
    side: 'left' as const,
  },
  yang: {
    label: 'Yang',
    subtitle: 'Drive & Action',
    accentColor: 'text-red-400',
    bgAccent: 'bg-red-500/10',
    borderColor: 'border-red-500/20',
    dotColor: 'bg-red-400',
    barColor: 'bg-red-400',
    headerBg: 'bg-red-500/5',
    side: 'right' as const,
  },
}

// ── Entry component ──────────────────────────────────────────────────────────

const DialecticEntryCard = ({ entry, theme }: { entry: DialecticEntry; theme: typeof VOICE_THEMES[keyof typeof VOICE_THEMES] }) => {
  const [expanded, setExpanded] = useState(false)
  const age = Date.now() - entry.timestamp
  const ageStr = age < 60_000 ? `${Math.floor(age / 1000)}s` : age < 3_600_000 ? `${Math.floor(age / 60_000)}m` : `${Math.floor(age / 3_600_000)}h`
  const confidencePct = Math.round(entry.confidence * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className={`rounded-md border ${theme.borderColor} ${theme.bgAccent} p-2`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        type="button"
        className="flex w-full items-center gap-1.5"
      >
        <div className={`size-1.5 shrink-0 rounded-full ${theme.dotColor}`} />
        <div className="flex flex-1 items-center justify-between">
          <div className="flex items-center gap-1">
            <span className="font-dmmono text-[9px] text-muted/40">{ageStr}</span>
            {entry.turnIndex !== undefined && (
              <span className="font-dmmono text-[8px] text-muted/30">T{entry.turnIndex}</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <div className="h-1 w-8 overflow-hidden rounded-full bg-primary/5">
              <div className={`h-full rounded-full ${theme.barColor} opacity-60`} style={{ width: `${confidencePct}%` }} />
            </div>
            <span className="font-dmmono text-[8px] text-muted/40">{confidencePct}%</span>
          </div>
        </div>
      </button>
      
      <p className={`mt-1.5 text-[10px] leading-relaxed ${expanded ? 'text-primary/80' : 'line-clamp-3 text-muted/60'}`}>
        {entry.content}
      </p>
    </motion.div>
  )
}

// ── Main Column ──────────────────────────────────────────────────────────────

export default function DialecticColumn({ voice, collapsed, onToggle }: DialecticColumnProps) {
  const { selectedEndpoint, isEndpointActive } = useStore()
  const [entries, setEntries] = useState<DialecticEntry[]>([])
  const sseRef = useRef<AbortController | null>(null)
  const theme = VOICE_THEMES[voice]

  // Subscribe to SSE events for this voice's signals
  useEffect(() => {
    if (collapsed || !isEndpointActive || !selectedEndpoint) return

    const controller = new AbortController()
    const url = `${selectedEndpoint}/api/cassicore/events`

    ;(async () => {
      try {
        const res = await fetch(url, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' },
        })
        if (!res.ok || !res.body) return

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          let idx: number
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const raw = buffer.slice(0, idx)
            buffer = buffer.slice(idx + 2)

            let eventData = ''
            for (const line of raw.split('\n')) {
              if (line.startsWith('data: ')) eventData += line.slice(6)
            }
            if (!eventData) continue

            try {
              const parsed = JSON.parse(eventData)
              const eventType = parsed.type ?? ''

              // Filter for dialectic events matching this voice
              if (eventType === 'dialectic:signal' || eventType === 'dialectic:stream' || eventType === 'dialectic:complete') {
                const voiceType = (parsed.voice ?? parsed.data?.voice ?? '').toLowerCase()
                if (voiceType === voice) {
                  const content = parsed.content ?? parsed.data?.content ?? parsed.text ?? ''
                  if (content) {
                    const newEntry: DialecticEntry = {
                      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                      voice,
                      content,
                      confidence: parsed.confidence ?? parsed.data?.confidence ?? 0.5,
                      timestamp: parsed.timestamp ? new Date(parsed.timestamp).getTime() : Date.now(),
                      turnIndex: parsed.turnIndex ?? parsed.data?.turnIndex,
                      sessionId: parsed.sessionId ?? parsed.data?.sessionId,
                    }
                    setEntries(prev => [newEntry, ...prev].slice(0, 50))
                  }
                }
              }
            } catch { /* skip malformed */ }
          }
        }
      } catch { /* connection closed */ }
    })()

    sseRef.current = controller
    return () => {
      controller.abort()
      sseRef.current = null
    }
  }, [collapsed, selectedEndpoint, isEndpointActive, voice])

  // Collapsed state — show a thin toggle strip
  if (collapsed) {
    return (
      <button
        onClick={onToggle}
        type="button"
        className={`flex h-full w-8 shrink-0 flex-col items-center justify-center gap-1 border-primary/5 transition-colors hover:bg-primary/5 ${
          voice === 'yin' ? 'border-r' : 'border-l'
        }`}
        title={`Show ${theme.label}`}
      >
        <span className={`text-[9px] font-medium uppercase ${theme.accentColor} [writing-mode:vertical-lr] ${voice === 'yin' ? 'rotate-180' : ''}`}>
          {theme.label}
        </span>
        {entries.length > 0 && (
          <span className={`flex size-4 items-center justify-center rounded-full ${theme.bgAccent} text-[8px] ${theme.accentColor}`}>
            {entries.length}
          </span>
        )}
      </button>
    )
  }

  // Expanded state
  return (
    <div className={`flex h-full w-[180px] shrink-0 flex-col ${voice === 'yin' ? 'border-r' : 'border-l'} border-primary/10`}>
      {/* Header */}
      <div className={`flex items-center justify-between px-3 py-2 ${theme.headerBg}`}>
        <div>
          <span className={`text-[10px] font-medium uppercase ${theme.accentColor}`}>{theme.label}</span>
          <span className="ml-1.5 text-[8px] text-muted/40">{theme.subtitle}</span>
        </div>
        <button onClick={onToggle} type="button" className="text-muted/40 hover:text-primary">
          <Icon type="x" size="xxs" />
        </button>
      </div>

      {/* Entries */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        <AnimatePresence initial={false}>
          {entries.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-8 text-center"
            >
              <div className={`mb-2 size-6 rounded-full ${theme.bgAccent} flex items-center justify-center`}>
                <div className={`size-2 rounded-full ${theme.dotColor} opacity-40`} />
              </div>
              <p className="text-[10px] text-muted/40">No active analysis</p>
              <p className="mt-0.5 text-[8px] text-muted/30">
                {voice === 'yin' ? 'Caution signals will appear here' : 'Action signals will appear here'}
              </p>
            </motion.div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {entries.map(entry => (
                <DialecticEntryCard key={entry.id} entry={entry} theme={theme} />
              ))}
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer stats */}
      {entries.length > 0 && (
        <div className="flex items-center justify-between border-t border-primary/5 px-3 py-1.5">
          <span className="font-dmmono text-[8px] text-muted/30">{entries.length} entries</span>
          <button
            onClick={() => setEntries([])}
            type="button"
            className="text-[8px] text-muted/30 hover:text-primary"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  )
}
