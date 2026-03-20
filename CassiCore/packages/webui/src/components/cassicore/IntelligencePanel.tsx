'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '@/store'
import Icon from '@/components/ui/icon'


interface LiveEvent {
  id: string
  type: string
  data: Record<string, unknown>
  timestamp: number
}

interface ThinkerStats {
  totalInsights: number
  totalTurns: number
  ponderInterval: number
  thinkInterval: number
  lastPonderAt: string | null
  insightCount: number
}

interface SubconsciousStats {
  totalEvents: number
  activeSessions: number
  eventRate: number
  totalObservations: number
  totalAnomalies: number
  activeAnomalies: number
  patternsRecognized: number
  averageConfidence: number
  lastUpdate: number
  topEventTypes: Array<{ type: string; count: number }>
}

type Tab = 'modules' | 'thinker' | 'subconscious' | 'events'


const MODULE_META: Record<string, { label: string; desc: string; color: string }> = {
  'memory':                { label: 'Memory',              desc: 'persistent',        color: 'bg-pink-400' },
  'rule-enforcer':         { label: 'Rule Enforcer',       desc: 'safety',            color: 'bg-red-400' },
  'continuity':            { label: 'Continuity',          desc: 'sessions',          color: 'bg-blue-400' },
  'context-manager':       { label: 'Context',             desc: 'ctx window',        color: 'bg-sky-400' },
  'trust-ledger':          { label: 'Trust Ledger',        desc: 'reputation',        color: 'bg-amber-400' },
  'permission-oracle':     { label: 'Permissions',         desc: 'authz',             color: 'bg-orange-400' },
  'consequence-estimator': { label: 'Consequence Est.',    desc: 'risk',              color: 'bg-red-300' },
  'error-learner':         { label: 'Error Learner',       desc: 'learn + recover',   color: 'bg-violet-400' },
  'optimizer':             { label: 'Optimizer',           desc: 'adaptive',          color: 'bg-teal-400' },
  'drone-swarm':           { label: 'Drone Swarm',         desc: 'parallel',          color: 'bg-cyan-400' },
  'thinker':               { label: 'Thinker',             desc: 'insights',          color: 'bg-amber-300' },
  'dialectic':             { label: 'Dialectic',           desc: 'Yang/Yin/Synth',    color: 'bg-purple-400' },
  'team-orchestrator':     { label: 'Team Orchestrator',   desc: 'multi-agent',       color: 'bg-indigo-400' },
  'subconscious':          { label: 'Subconscious',        desc: 'observer',          color: 'bg-cyan-300' },
  'ai-engineer':           { label: 'AI Engineer',         desc: 'code',              color: 'bg-emerald-400' },
  'ai-scientist':          { label: 'AI Scientist',        desc: 'research',          color: 'bg-green-300' },
  'multi-agent':           { label: 'Multi-Agent',         desc: 'swarm',             color: 'bg-violet-300' },
  'self-healer':           { label: 'Self Healer',         desc: 'repairs',           color: 'bg-rose-400' },
}


const EventItem = ({ event }: { event: LiveEvent }) => {
  const typeColors: Record<string, string> = {
    'dialectic:stream':           'text-purple-400',
    'dialectic:complete':         'text-purple-300',
    'thinker:insight':            'text-amber-400',
    'thinker:ponder':             'text-amber-300',
    'tool:executed':              'text-blue-400',
    'tool:registered':            'text-blue-300',
    'turn:start':                 'text-green-400',
    'turn:complete':              'text-green-300',
    'subconscious:observation':   'text-cyan-400',
    'memory:stored':              'text-pink-400',
    'provider:request_start':     'text-sky-400',
    'provider:request_end':       'text-sky-300',
    'worker:message':             'text-slate-400',
  }
  // Match by prefix
  const matchedKey = Object.keys(typeColors).find(k => event.type.startsWith(k.split(':')[0] + ':') && event.type === k)
  const prefixMatch = Object.keys(typeColors).find(k => event.type.startsWith(k))
  const color = matchedKey ? typeColors[matchedKey] : (prefixMatch ? typeColors[prefixMatch] : 'text-muted')
  const age = Math.floor((Date.now() - event.timestamp) / 1000)
  const ageStr = age < 60 ? `${age}s` : `${Math.floor(age / 60)}m`

  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-start gap-2 border-b border-primary/5 py-1.5 last:border-0"
    >
      <div className={`mt-1 size-1.5 shrink-0 rounded-full ${color.replace('text-', 'bg-')}`} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center justify-between gap-2">
          <span className={`font-dmmono text-[10px] ${color}`}>{event.type}</span>
          <span className="shrink-0 font-dmmono text-[10px] text-muted/40">{ageStr}</span>
        </div>
        {typeof event.data.content === 'string' && event.data.content.length > 0 && (
          <p className="line-clamp-1 text-[11px] text-muted/60">
            {event.data.content.slice(0, 80)}
          </p>
        )}
      </div>
    </motion.div>
  )
}

const StatRow = ({ label, value, mono = false }: { label: string; value: string | number; mono?: boolean }) => (
  <div className="flex items-center justify-between py-1">
    <span className="text-[11px] text-muted/70">{label}</span>
    <span className={`text-[11px] text-primary ${mono ? 'font-dmmono' : ''}`}>{value}</span>
  </div>
)


export default function IntelligencePanel() {
  const { selectedEndpoint, isEndpointActive, intelligenceActivity, intelPanelOpen, setIntelPanelOpen } = useStore()
  const [isOpen, setIsOpen] = useState(false)

  const handleOpen = (open: boolean) => {
    setIsOpen(open)
    setIntelPanelOpen(open)
  }
  const [tab, setTab] = useState<Tab>('modules')
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [thinker, setThinker] = useState<ThinkerStats | null>(null)
  const [subconscious, setSubconscious] = useState<SubconsciousStats | null>(null)
  const eventSourceRef = useRef<AbortController | null>(null)

  // Extract + deduplicate modules from store
  const activity = intelligenceActivity as Record<string, unknown> | null
  const rawModules = (activity?.modules as Array<Record<string, unknown>>) ?? []
  const modules = rawModules.reduce<Array<Record<string, unknown>>>((acc, m) => {
    if (!acc.some(x => x.name === m.name)) acc.push(m)
    return acc
  }, [])

  // Fetch thinker + subconscious stats when panel opens
  const fetchStats = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      const [tRes, sRes] = await Promise.all([
        fetch(`${selectedEndpoint}/api/cassicore/thinker`),
        fetch(`${selectedEndpoint}/api/cassicore/subconscious`),
      ])
      if (tRes.ok) {
        const d = await tRes.json()
        setThinker((d.stats ?? d) as ThinkerStats)
      }
      if (sRes.ok) {
        const d = await sRes.json()
        setSubconscious((d.stats ?? d) as SubconsciousStats)
      }
    } catch { /* non-critical */ }
  }, [selectedEndpoint, isEndpointActive])

  useEffect(() => {
    if (!isOpen) return
    fetchStats()
    const timer = setInterval(fetchStats, 15_000)
    return () => clearInterval(timer)
  }, [isOpen, fetchStats])

  // SSE event stream — connect when Events tab is open
  // Use fetch-based streaming instead of EventSource to handle named event types
  useEffect(() => {
    if (!isOpen || tab !== 'events' || !isEndpointActive || !selectedEndpoint) {
      return
    }

    const controller = new AbortController()
    const url = `${selectedEndpoint}/api/cassicore/events`

    ;(async () => {
      try {
        const res = await fetch(url, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' },
        })
        if (!res.body) return

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          // Parse SSE frames: split on double newline
          const frames = buffer.split('\n\n')
          buffer = frames.pop() ?? ''

          for (const frame of frames) {
            if (!frame.trim()) continue
            const lines = frame.split('\n')
            let eventType = 'message'
            let dataStr = ''
            for (const line of lines) {
              if (line.startsWith('event:')) eventType = line.slice(6).trim()
              if (line.startsWith('data:')) dataStr += line.slice(5).trim()
            }
            if (!dataStr) continue
            try {
              const data = JSON.parse(dataStr) as Record<string, unknown>
              // Skip connection handshake
              if (data.type === 'sse_connected') continue
              const type = (data.type as string) ?? eventType
              const newEvent: LiveEvent = {
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                type,
                data,
                timestamp: typeof data.timestamp === 'number' ? data.timestamp : Date.now(),
              }
              setEvents((prev) => [newEvent, ...prev].slice(0, 100))
            } catch { /* ignore parse errors */ }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.warn('[IntelligencePanel] SSE error:', err)
        }
      }
    })()

    return () => { controller.abort() }
  }, [isOpen, tab, isEndpointActive, selectedEndpoint])

  const formatTime = (iso: string | null) => {
    if (!iso) return '—'
    const d = new Date(iso)
    const age = Date.now() - d.getTime()
    if (age < 60_000) return `${Math.floor(age / 1000)}s ago`
    if (age < 3_600_000) return `${Math.floor(age / 60_000)}m ago`
    return `${Math.floor(age / 3_600_000)}h ago`
  }

  const TABS: Array<{ id: Tab; label: string }> = [
    { id: 'modules', label: 'Modules' },
    { id: 'thinker', label: 'Thinker' },
    { id: 'subconscious', label: 'Observer' },
    { id: 'events', label: 'Events' },
  ]

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => handleOpen(!isOpen)}
        className={`fixed right-3 top-3 z-40 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-medium uppercase transition-all ${
          isOpen ? 'bg-accent text-primary' : 'text-muted hover:bg-accent hover:text-primary'
        } ${intelPanelOpen ? 'right-[308px]' : 'right-3'}`}
        type="button"
      >
        <Icon type="reasoning" size="xxs" />
        <span className="font-dmmono">Intel</span>
        {tab === 'events' && events.length > 0 && (
          <span className="flex size-4 items-center justify-center rounded-full bg-brand text-[9px] text-white">
            {events.length > 99 ? '99+' : events.length}
          </span>
        )}
      </button>

      {/* Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 z-30 flex h-screen flex-col overflow-hidden border-l border-primary/10 bg-background"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-primary/10 px-4 py-3">
              <span className="text-xs font-medium uppercase text-primary">Intelligence</span>
              <button onClick={() => handleOpen(false)} type="button" className="text-muted hover:text-primary">
                <Icon type="x" size="xs" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-primary/10">
              {TABS.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  type="button"
                  className={`flex-1 py-2 text-[10px] font-medium uppercase transition-colors ${
                    tab === t.id
                      ? 'border-b-2 border-brand text-primary'
                      : 'text-muted/60 hover:text-muted'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto">

              {/* ── Modules tab ─────────────────────────────────────────── */}
              {tab === 'modules' && (
                <div className="px-4 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Cognitive Modules</span>
                    <span className="font-dmmono text-[10px] text-muted/40">{modules.length} active</span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    {modules.map((m) => {
                      const name = String(m.name)
                      const meta = MODULE_META[name]
                      const label = meta?.label ?? name.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                      const desc = meta?.desc
                      const dot = meta?.color ?? 'bg-positive'
                      const active = m.status === 'active' || m.status === 'ok'
                      return (
                        <div key={name} className="flex items-center justify-between py-1">
                          <div className="flex items-center gap-2">
                            <div className={`size-1.5 rounded-full ${active ? dot : 'bg-muted/30'}`} />
                            <span className="text-[11px] text-muted">{label}</span>
                          </div>
                          {desc && (
                            <span className="font-dmmono text-[10px] text-muted/40">{desc}</span>
                          )}
                        </div>
                      )
                    })}
                    {modules.length === 0 && (
                      <p className="py-4 text-center text-[11px] text-muted/40">Loading modules…</p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Thinker tab ──────────────────────────────────────────── */}
              {tab === 'thinker' && (
                <div className="px-4 py-3">
                  <div className="mb-3">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Thinker Stats</span>
                  </div>
                  {thinker ? (
                    <div className="divide-y divide-primary/5">
                      <StatRow label="Total Insights" value={thinker.totalInsights.toLocaleString()} mono />
                      <StatRow label="Total Turns" value={thinker.totalTurns.toLocaleString()} mono />
                      <StatRow label="Ponder Interval" value={`${thinker.ponderInterval}s`} mono />
                      <StatRow label="Think Interval" value={`${thinker.thinkInterval}s`} mono />
                      <StatRow label="Last Ponder" value={formatTime(thinker.lastPonderAt)} />
                    </div>
                  ) : (
                    <p className="py-4 text-center text-[11px] text-muted/40">Loading…</p>
                  )}

                  <div className="mt-4">
                    <span className="text-[10px] font-medium uppercase text-muted/60">About Thinker</span>
                    <p className="mt-2 text-[11px] leading-relaxed text-muted/60">
                      The Thinker module runs background reasoning cycles — pondering context
                      and generating insights that are injected into future turns to improve
                      response quality over time.
                    </p>
                  </div>
                </div>
              )}

              {/* ── Subconscious tab ─────────────────────────────────────── */}
              {tab === 'subconscious' && (
                <div className="px-4 py-3">
                  <div className="mb-3">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Conscious Observer</span>
                  </div>
                  {subconscious ? (
                    <>
                      <div className="divide-y divide-primary/5">
                        <StatRow label="Total Events" value={subconscious.totalEvents.toLocaleString()} mono />
                        <StatRow label="Active Sessions" value={subconscious.activeSessions.toLocaleString()} mono />
                        <StatRow label="Event Rate" value={`${subconscious.eventRate.toFixed(2)}/s`} mono />
                        <StatRow label="Observations" value={subconscious.totalObservations.toLocaleString()} mono />
                        <StatRow label="Patterns" value={subconscious.patternsRecognized.toLocaleString()} mono />
                        <StatRow label="Active Anomalies" value={subconscious.activeAnomalies.toLocaleString()} mono />
                        <StatRow label="Avg Confidence" value={`${(subconscious.averageConfidence * 100).toFixed(0)}%`} mono />
                      </div>

                      {subconscious.topEventTypes?.length > 0 && (
                        <div className="mt-4">
                          <span className="text-[10px] font-medium uppercase text-muted/60">Top Event Types</span>
                          <div className="mt-2 flex flex-col gap-1">
                            {subconscious.topEventTypes.slice(0, 8).map((t) => (
                              <div key={t.type} className="flex items-center justify-between">
                                <span className="font-dmmono text-[10px] text-muted/60 truncate">{t.type}</span>
                                <span className="font-dmmono text-[10px] text-muted/40 shrink-0 ml-2">{t.count}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="py-4 text-center text-[11px] text-muted/40">Loading…</p>
                  )}
                </div>
              )}

              {/* ── Events tab ───────────────────────────────────────────── */}
              {tab === 'events' && (
                <div className="px-4 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Live Event Stream</span>
                    <div className="flex items-center gap-2">
                      <span className="flex size-1.5 rounded-full bg-positive animate-pulse" />
                      {events.length > 0 && (
                        <button
                          onClick={() => setEvents([])}
                          className="text-[10px] text-muted/40 hover:text-muted"
                          type="button"
                        >
                          clear
                        </button>
                      )}
                    </div>
                  </div>
                  <AnimatePresence mode="popLayout">
                    {events.length === 0 ? (
                      <p className="py-6 text-center text-[11px] text-muted/40">
                        Waiting for events…
                      </p>
                    ) : (
                      events.map((event) => (
                        <EventItem key={event.id} event={event} />
                      ))
                    )}
                  </AnimatePresence>
                </div>
              )}

            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}
