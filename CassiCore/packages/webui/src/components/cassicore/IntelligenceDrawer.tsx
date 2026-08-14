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

interface PersonaSection {
  label: string
  content: string
  source: string
  charCount: number
}

interface InjectionPart {
  source: string
  content: string
  charCount: number
}

type Tab = 'modules' | 'thinker' | 'subconscious' | 'events' | 'prompt' | 'context'


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
  'self-healer':           { label: 'Self Healer',         desc: 'repairs',             color: 'bg-rose-400' },
}


const SOURCE_COLORS: Record<string, string> = {
  optimizer: 'bg-teal-400',
  thinker: 'bg-amber-300',
  cognitive: 'bg-sky-400',
  dialectic: 'bg-purple-400',
  subconscious: 'bg-cyan-300',
  'session-digest': 'bg-blue-400',
}

const SOURCE_CAPS: Record<string, number> = {
  optimizer: 4000,
  thinker: 2000,
  cognitive: 3000,
  dialectic: 3000,
  subconscious: 8000,
  'session-digest': 2000,
}

const TOTAL_INJECTION_CAP = 16000


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
        <div className="flex items-center justify-between">
          <span className={`truncate font-dmmono text-[10px] ${color}`}>{event.type}</span>
          <span className="ml-1 shrink-0 font-dmmono text-[9px] text-muted/40">{ageStr}</span>
        </div>
        {event.data && Object.keys(event.data).length > 0 && (
          <pre className="truncate font-dmmono text-[9px] text-muted/50">
            {JSON.stringify(event.data).slice(0, 120)}
          </pre>
        )}
      </div>
    </motion.div>
  )
}


const PromptSectionCard = ({ section, onSave }: { section: PersonaSection; onSave: (label: string, content: string) => void }) => {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(section.content)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setDraft(section.content)
  }, [section.content])

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 400)}px`
    }
  }, [editing])

  const handleSave = () => {
    onSave(section.label, draft)
    setEditing(false)
  }

  return (
    <div className="rounded-md border border-primary/10 bg-background-secondary/50">
      <button
        onClick={() => setExpanded(!expanded)}
        type="button"
        className="flex w-full items-center justify-between px-3 py-2"
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium uppercase text-primary">{section.label}</span>
          <span className="font-dmmono text-[9px] text-muted/40">{section.charCount} chars</span>
        </div>
        <Icon type={expanded ? 'chevron-up' : 'chevron-down'} size="xxs" className="text-muted/40" />
      </button>
      {expanded && (
        <div className="border-t border-primary/5 px-3 py-2">
          {editing ? (
            <div className="flex flex-col gap-2">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => {
                  setDraft(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 400)}px`
                }}
                className="w-full resize-none rounded bg-background p-2 font-dmmono text-[11px] text-primary outline-none ring-1 ring-primary/10 focus:ring-brand/50"
                rows={6}
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={() => { setDraft(section.content); setEditing(false) }}
                  type="button"
                  className="rounded px-2 py-1 text-[10px] text-muted hover:text-primary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  type="button"
                  className="rounded bg-brand/20 px-2 py-1 text-[10px] text-brand hover:bg-brand/30"
                >
                  Save
                </button>
              </div>
            </div>
          ) : (
            <div className="group relative">
              <pre className="max-h-[300px] overflow-y-auto whitespace-pre-wrap font-dmmono text-[10px] text-muted/70">
                {section.content || '(empty)'}
              </pre>
              <button
                onClick={() => setEditing(true)}
                type="button"
                className="absolute right-0 top-0 rounded bg-background/80 px-2 py-0.5 text-[9px] text-muted opacity-0 transition-opacity hover:text-primary group-hover:opacity-100"
              >
                Edit
              </button>
            </div>
          )}
          <p className="mt-1 font-dmmono text-[8px] text-muted/30">{section.source}</p>
        </div>
      )}
    </div>
  )
}


const InjectionSourceCard = ({ part }: { part: InjectionPart }) => {
  const [expanded, setExpanded] = useState(false)
  const cap = SOURCE_CAPS[part.source] ?? TOTAL_INJECTION_CAP
  const pct = Math.min(100, Math.round((part.charCount / cap) * 100))
  const color = SOURCE_COLORS[part.source] ?? 'bg-slate-400'

  return (
    <div className="rounded-md border border-primary/10 bg-background-secondary/50">
      <button
        onClick={() => setExpanded(!expanded)}
        type="button"
        className="flex w-full items-center gap-2 px-3 py-1.5"
      >
        <div className={`size-2 shrink-0 rounded-full ${color}`} />
        <span className="text-[10px] font-medium text-primary">{part.source}</span>
        <div className="flex-1" />
        <span className="font-dmmono text-[9px] text-muted/40">{part.charCount}/{cap}</span>
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-primary/5">
          <div className={`h-full rounded-full ${color} opacity-60`} style={{ width: `${pct}%` }} />
        </div>
      </button>
      {expanded && (
        <div className="border-t border-primary/5 px-3 py-2">
          <pre className="max-h-[200px] overflow-y-auto whitespace-pre-wrap font-dmmono text-[9px] text-muted/60">
            {part.content || '(empty)'}
          </pre>
        </div>
      )}
    </div>
  )
}


const DEFAULT_HEIGHT = 320
const MIN_HEIGHT = 200
const MAX_HEIGHT_RATIO = 0.7

export default function IntelligenceDrawer() {
  const {
    selectedEndpoint, isEndpointActive, intelligenceActivity,
    intelPanelOpen, setIntelPanelOpen,
    dialecticVisible, setDialecticVisible,
  } = useStore()

  const isOpen = intelPanelOpen
  const [tab, setTab] = useState<Tab>('modules')
  const [height, setHeight] = useState(DEFAULT_HEIGHT)
  const [events, setEvents] = useState<LiveEvent[]>([])
  const [thinker, setThinker] = useState<ThinkerStats | null>(null)
  const [subconscious, setSubconscious] = useState<SubconsciousStats | null>(null)
  const [promptSections, setPromptSections] = useState<PersonaSection[]>([])
  const [promptTotalChars, setPromptTotalChars] = useState(0)
  const [injections, setInjections] = useState<InjectionPart[]>([])
  const [injectionTotal, setInjectionTotal] = useState(0)
  const eventSourceRef = useRef<AbortController | null>(null)
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null)

  // Restore persisted height
  useEffect(() => {
    const stored = localStorage.getItem('cassi-drawer-height')
    if (stored) setHeight(Number(stored))
  }, [])

  const handleOpen = (open: boolean) => {
    setIntelPanelOpen(open)
  }

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

  // Fetch system prompt sections
  const fetchPrompt = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/system-prompt`)
      if (res.ok) {
        const data = await res.json()
        setPromptSections(data.sections ?? [])
        setPromptTotalChars(data.totalChars ?? 0)
      }
    } catch { /* non-critical */ }
  }, [selectedEndpoint, isEndpointActive])

  // Fetch current injections
  const fetchInjections = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/context/injections`)
      if (res.ok) {
        const data = await res.json()
        setInjections(data.parts ?? [])
        setInjectionTotal(data.totalChars ?? 0)
      }
    } catch { /* non-critical */ }
  }, [selectedEndpoint, isEndpointActive])

  // Save a prompt section
  const handleSaveSection = useCallback(async (label: string, content: string) => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/system-prompt/sections/${label}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (res.ok) {
        fetchPrompt() // Refresh after save
      }
    } catch { /* non-critical */ }
  }, [selectedEndpoint, isEndpointActive, fetchPrompt])

  // Reload prompt from disk
  const handleReloadPrompt = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      await fetch(`${selectedEndpoint}/api/cassicore/system-prompt/reload`, { method: 'POST' })
      fetchPrompt()
    } catch { /* non-critical */ }
  }, [selectedEndpoint, isEndpointActive, fetchPrompt])

  useEffect(() => {
    if (!isOpen) return
    fetchStats()
    if (tab === 'prompt') fetchPrompt()
    if (tab === 'context') fetchInjections()
    const timer = setInterval(() => {
      fetchStats()
      if (tab === 'prompt') fetchPrompt()
      if (tab === 'context') fetchInjections()
    }, 15_000)
    return () => clearInterval(timer)
  }, [isOpen, tab, fetchStats, fetchPrompt, fetchInjections])

  // SSE event stream — connect when Events tab is open
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

            // Parse SSE fields
            let eventType = 'message'
            let eventData = ''
            for (const line of raw.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.slice(7).trim()
              else if (line.startsWith('data: ')) eventData += line.slice(6)
            }
            if (!eventData) continue

            try {
              const parsed = JSON.parse(eventData)
              const newEvent: LiveEvent = {
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                type: parsed.type ?? eventType,
                data: parsed,
                timestamp: parsed.timestamp ? new Date(parsed.timestamp).getTime() : Date.now(),
              }
              setEvents(prev => [newEvent, ...prev].slice(0, 200))

              // Auto-refresh injections on turn events
              if (parsed.type?.startsWith('turn:') || parsed.type?.startsWith('injection:')) {
                fetchInjections()
              }
            } catch { /* skip malformed */ }
          }
        }
      } catch { /* connection closed */ }
    })()

    eventSourceRef.current = controller
    return () => {
      controller.abort()
      eventSourceRef.current = null
    }
  }, [isOpen, tab, selectedEndpoint, isEndpointActive, fetchInjections])

  // Resize drag handlers
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = { startY: e.clientY, startHeight: height }
    
    const handleDragMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const delta = dragRef.current.startY - ev.clientY
      const maxH = window.innerHeight * MAX_HEIGHT_RATIO
      const newHeight = Math.max(MIN_HEIGHT, Math.min(maxH, dragRef.current.startHeight + delta))
      setHeight(newHeight)
    }
    
    const handleDragEnd = () => {
      dragRef.current = null
      localStorage.setItem('cassi-drawer-height', String(height))
      document.removeEventListener('mousemove', handleDragMove)
      document.removeEventListener('mouseup', handleDragEnd)
    }
    
    document.addEventListener('mousemove', handleDragMove)
    document.addEventListener('mouseup', handleDragEnd)
  }, [height])

  function formatAge(ts: number) {
    const age = Date.now() - ts
    if (age < 60_000) return `${Math.floor(age / 1000)}s ago`
    if (age < 3_600_000) return `${Math.floor(age / 60_000)}m ago`
    return `${Math.floor(age / 3_600_000)}h ago`
  }

  const TABS: Array<{ id: Tab; label: string }> = [
    { id: 'modules', label: 'Modules' },
    { id: 'thinker', label: 'Thinker' },
    { id: 'subconscious', label: 'Observer' },
    { id: 'events', label: 'Events' },
    { id: 'prompt', label: 'Prompt' },
    { id: 'context', label: 'Context' },
  ]

  const totalInjectionPct = Math.min(100, Math.round((injectionTotal / TOTAL_INJECTION_CAP) * 100))

  return (
    <>
      {/* Toggle buttons — fixed at bottom center */}
      <div className="fixed bottom-3 left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5">
        {/* Dialectic toggle */}
        <button
          onClick={() => setDialecticVisible(!dialecticVisible)}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[10px] font-medium uppercase transition-all ${
            dialecticVisible
              ? 'bg-purple-500/10 text-purple-400'
              : 'bg-background/80 text-muted hover:bg-purple-500/10 hover:text-purple-400'
          } border border-primary/10 backdrop-blur-sm`}
          type="button"
          title="Toggle dialectic columns"
        >
          <span className="font-dmmono">Dialectic</span>
        </button>

        {/* Intel toggle */}
        <button
          onClick={() => handleOpen(!isOpen)}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[10px] font-medium uppercase transition-all ${
            isOpen ? 'bg-accent text-primary' : 'bg-background/80 text-muted hover:bg-accent hover:text-primary'
          } border border-primary/10 backdrop-blur-sm`}
          type="button"
        >
          <Icon type="reasoning" size="xxs" />
          <span className="font-dmmono">Intel</span>
          {tab === 'events' && events.length > 0 && (
            <span className="flex size-4 items-center justify-center rounded-full bg-brand text-[9px] text-white">
              {events.length > 99 ? '99+' : events.length}
            </span>
          )}
          <Icon type={isOpen ? 'chevron-down' : 'chevron-up'} size="xxs" className="ml-1 text-muted/40" />
        </button>
      </div>

      {/* Drawer */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height, opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed bottom-0 left-0 right-0 z-30 flex flex-col overflow-hidden border-t border-primary/10 bg-background"
          >
            {/* Resize handle */}
            <div
              onMouseDown={handleDragStart}
              className="flex h-2 shrink-0 cursor-ns-resize items-center justify-center hover:bg-primary/5"
            >
              <div className="h-0.5 w-8 rounded-full bg-primary/20" />
            </div>

            {/* Header + Tabs */}
            <div className="flex shrink-0 items-center border-b border-primary/10 px-4">
              <span className="mr-4 text-xs font-medium uppercase text-primary">Intelligence</span>
              <div className="flex flex-1">
                {TABS.map(t => (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    type="button"
                    className={`px-3 py-2 text-[10px] font-medium uppercase transition-colors ${
                      tab === t.id
                        ? 'border-b-2 border-brand text-primary'
                        : 'text-muted/60 hover:text-muted'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <button onClick={() => handleOpen(false)} type="button" className="text-muted hover:text-primary">
                <Icon type="x" size="xs" />
              </button>
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto px-4 py-3">

              {/* ── Modules tab ─────────────────────────────────── */}
              {tab === 'modules' && (
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Cognitive Modules</span>
                    <span className="font-dmmono text-[10px] text-muted/40">{modules.length} active</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {modules.map((m) => {
                      const name = String(m.name)
                      const meta = MODULE_META[name]
                      const lastActive = m.lastActive ? formatAge(m.lastActive as number) : '—'
                      return (
                        <div
                          key={name}
                          className="flex items-center gap-1.5 rounded-md bg-background-secondary/50 px-2 py-1"
                        >
                          <div className={`size-1.5 rounded-full ${meta?.color ?? 'bg-slate-400'}`} />
                          <span className="text-[10px] font-medium text-primary">
                            {meta?.label ?? name}
                          </span>
                          <span className="font-dmmono text-[9px] text-muted/40">{lastActive}</span>
                        </div>
                      )
                    })}
                    {modules.length === 0 && (
                      <p className="text-[10px] text-muted/40">No active modules</p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Thinker tab ─────────────────────────────────── */}
              {tab === 'thinker' && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-md bg-background-secondary/50 p-3">
                    <p className="text-[9px] uppercase text-muted/40">Insights</p>
                    <p className="font-dmmono text-lg text-amber-300">{thinker?.insightCount ?? '—'}</p>
                  </div>
                  <div className="rounded-md bg-background-secondary/50 p-3">
                    <p className="text-[9px] uppercase text-muted/40">Total Turns</p>
                    <p className="font-dmmono text-lg text-primary">{thinker?.totalTurns ?? '—'}</p>
                  </div>
                  <div className="rounded-md bg-background-secondary/50 p-3">
                    <p className="text-[9px] uppercase text-muted/40">Ponder Interval</p>
                    <p className="font-dmmono text-lg text-primary">{thinker?.ponderInterval ? `${Math.round(thinker.ponderInterval / 1000)}s` : '—'}</p>
                  </div>
                  <div className="rounded-md bg-background-secondary/50 p-3">
                    <p className="text-[9px] uppercase text-muted/40">Last Ponder</p>
                    <p className="font-dmmono text-sm text-primary">{thinker?.lastPonderAt ? formatAge(new Date(thinker.lastPonderAt).getTime()) : '—'}</p>
                  </div>
                </div>
              )}

              {/* ── Observer tab ─────────────────────────────────── */}
              {tab === 'subconscious' && (
                <div>
                  <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-md bg-background-secondary/50 p-3">
                      <p className="text-[9px] uppercase text-muted/40">Events</p>
                      <p className="font-dmmono text-lg text-cyan-300">{subconscious?.totalEvents ?? '—'}</p>
                    </div>
                    <div className="rounded-md bg-background-secondary/50 p-3">
                      <p className="text-[9px] uppercase text-muted/40">Observations</p>
                      <p className="font-dmmono text-lg text-primary">{subconscious?.totalObservations ?? '—'}</p>
                    </div>
                    <div className="rounded-md bg-background-secondary/50 p-3">
                      <p className="text-[9px] uppercase text-muted/40">Anomalies</p>
                      <p className="font-dmmono text-lg text-rose-400">{subconscious?.activeAnomalies ?? '—'}/{subconscious?.totalAnomalies ?? '—'}</p>
                    </div>
                    <div className="rounded-md bg-background-secondary/50 p-3">
                      <p className="text-[9px] uppercase text-muted/40">Patterns</p>
                      <p className="font-dmmono text-lg text-primary">{subconscious?.patternsRecognized ?? '—'}</p>
                    </div>
                  </div>
                  {subconscious?.topEventTypes && subconscious.topEventTypes.length > 0 && (
                    <div>
                      <p className="mb-1 text-[10px] font-medium uppercase text-muted/60">Top Event Types</p>
                      <div className="flex flex-wrap gap-1">
                        {subconscious.topEventTypes.slice(0, 8).map(et => (
                          <span key={et.type} className="rounded bg-background-secondary/50 px-2 py-0.5 font-dmmono text-[9px] text-muted/60">
                            {et.type}: {et.count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ── Events tab ──────────────────────────────────── */}
              {tab === 'events' && (
                <div className="flex flex-col gap-0.5">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-[10px] font-medium uppercase text-muted/60">Live Events</span>
                    {events.length > 0 && (
                      <button
                        onClick={() => setEvents([])}
                        type="button"
                        className="text-[9px] text-muted/40 hover:text-primary"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  <AnimatePresence initial={false}>
                    {events.length === 0 ? (
                      <p className="text-[10px] text-muted/40">Waiting for events...</p>
                    ) : (
                      events.map((event) => (
                        <EventItem key={event.id} event={event} />
                      ))
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* ── Prompt tab ──────────────────────────────────── */}
              {tab === 'prompt' && (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-medium uppercase text-muted/60">System Prompt</span>
                      <span className="ml-2 font-dmmono text-[9px] text-muted/40">
                        {promptTotalChars} chars / ~{Math.ceil(promptTotalChars / 4)} tokens
                      </span>
                    </div>
                    <button
                      onClick={handleReloadPrompt}
                      type="button"
                      className="rounded bg-background-secondary/50 px-2 py-1 text-[9px] text-muted hover:text-primary"
                    >
                      Reload from disk
                    </button>
                  </div>
                  <div className="flex flex-col gap-2">
                    {promptSections.map(section => (
                      <PromptSectionCard
                        key={section.label}
                        section={section}
                        onSave={handleSaveSection}
                      />
                    ))}
                    {promptSections.length === 0 && (
                      <p className="text-[10px] text-muted/40">Loading prompt sections...</p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Context tab ─────────────────────────────────── */}
              {tab === 'context' && (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-medium uppercase text-muted/60">Context Injections</span>
                      <div className="flex items-center gap-1.5">
                        <div className="h-2 w-24 overflow-hidden rounded-full bg-primary/5">
                          <div
                            className={`h-full rounded-full transition-all ${totalInjectionPct > 80 ? 'bg-rose-400' : 'bg-brand'} opacity-60`}
                            style={{ width: `${totalInjectionPct}%` }}
                          />
                        </div>
                        <span className="font-dmmono text-[9px] text-muted/40">
                          {injectionTotal}/{TOTAL_INJECTION_CAP}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={fetchInjections}
                      type="button"
                      className="rounded bg-background-secondary/50 px-2 py-1 text-[9px] text-muted hover:text-primary"
                    >
                      Refresh
                    </button>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {injections.map(part => (
                      <InjectionSourceCard key={part.source} part={part} />
                    ))}
                    {injections.length === 0 && (
                      <p className="text-[10px] text-muted/40">No active injections</p>
                    )}
                  </div>
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
