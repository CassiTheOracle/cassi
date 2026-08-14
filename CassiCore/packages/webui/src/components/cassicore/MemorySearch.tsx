'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '@/store'
import Icon from '@/components/ui/icon'

interface MemoryEntry {
  id: string
  key?: string
  content: string
  type?: string
  tags?: string[]
  score?: number
  created_at?: string
  sessionId?: string
}

/** Normalize the nested { entry, score } shape the daemon returns */
function normalizeEntries(raw: unknown): MemoryEntry[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    // { entry: {...}, score: number } shape
    if (item && typeof item === 'object' && 'entry' in item) {
      const e = (item as { entry: Record<string, unknown>; score?: number }).entry
      return {
        id: String(e.id ?? ''),
        key: e.key as string | undefined,
        content: String(e.content ?? ''),
        type: e.type as string | undefined,
        tags: ((e as Record<string, unknown>).tags ?? (e as Record<string, unknown>).meta) as string[] | undefined ?? [],
        score: (item as { score?: number }).score,
        created_at: (e.createdAt ?? e.created_at) as string | undefined,
        sessionId: e.sessionId as string | undefined,
      }
    }
    // Flat shape
    const e = item as Record<string, unknown>
    return {
      id: String(e.id ?? ''),
      key: e.key as string | undefined,
      content: String(e.content ?? ''),
      type: e.type as string | undefined,
      tags: (e.tags ?? []) as string[],
      score: e.score as number | undefined,
      created_at: (e.createdAt ?? e.created_at) as string | undefined,
      sessionId: e.sessionId as string | undefined,
    }
  }).filter(e => e.content)
}

export default function MemorySearch() {
  const { selectedEndpoint, isEndpointActive, intelPanelOpen } = useStore()
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MemoryEntry[]>([])
  const [recentMemories, setRecentMemories] = useState<MemoryEntry[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Keyboard shortcut: Ctrl+M to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'm') {
        e.preventDefault()
        setIsOpen((prev) => !prev)
      }
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen])

  // Focus input when opening
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
      // Load recent memories
      fetchRecent()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  const fetchRecent = useCallback(async () => {
    if (!isEndpointActive || !selectedEndpoint) return
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/memory/recent`)
      if (res.ok) {
        const data = await res.json()
        // daemon returns [] directly or { memories: [...] } or { entries: [...] }
        const raw = Array.isArray(data) ? data : (data.memories ?? data.entries ?? [])
        setRecentMemories(normalizeEntries(raw))
      }
    } catch {
      // non-critical
    }
  }, [selectedEndpoint, isEndpointActive])

  const handleSearch = useCallback(async () => {
    if (!query.trim() || !selectedEndpoint) return
    setIsSearching(true)
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), limit: 10 })
      })
      if (res.ok) {
        const data = await res.json()
        const raw = Array.isArray(data) ? data : (data.results ?? data.memories ?? [])
        setResults(normalizeEntries(raw))
      }
    } catch {
      // non-critical
    } finally {
      setIsSearching(false)
    }
  }, [query, selectedEndpoint])

  const displayEntries = query.trim() ? results : recentMemories

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed z-40 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-medium uppercase transition-all ${
          isOpen ? 'bg-accent text-primary' : 'text-muted hover:bg-accent hover:text-primary'
        } ${intelPanelOpen ? 'right-[308px]' : 'right-3'} top-12`}
        type="button"
        title="Memory Search (Ctrl+M)"
      >
        <Icon type="references" size="xxs" />
        <span className="font-dmmono">Memory</span>
      </button>

      {/* Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[15vh]"
            onClick={(e) => {
              if (e.target === e.currentTarget) setIsOpen(false)
            }}
          >
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className="w-full max-w-lg overflow-hidden rounded-xl border border-primary/10 bg-background shadow-2xl"
            >
              {/* Search input */}
              <div className="flex items-center gap-3 border-b border-primary/10 px-4 py-3">
                <Icon type="references" size="xs" className="text-muted" />
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Search memory..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSearch()
                  }}
                  className="flex-1 bg-transparent text-sm text-primary outline-none placeholder:text-muted/40"
                />
                {isSearching && (
                  <div className="size-4 animate-spin rounded-full border-2 border-muted/30 border-t-primary" />
                )}
                <kbd className="rounded bg-accent px-1.5 py-0.5 font-dmmono text-[10px] text-muted">
                  esc
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-[50vh] overflow-y-auto">
                {displayEntries.length === 0 ? (
                  <div className="px-4 py-8 text-center text-xs text-muted/40">
                    {query.trim()
                      ? 'No results found'
                      : 'Type to search or view recent memories'}
                  </div>
                ) : (
                  <div className="flex flex-col">
                    {!query.trim() && (
                      <div className="px-4 pt-2 text-[10px] font-medium uppercase text-muted/50">
                        Recent
                      </div>
                    )}
                    {displayEntries.map((entry, i) => (
                      <div
                        key={entry.id ?? i}
                        className="border-b border-primary/5 px-4 py-3 last:border-0 hover:bg-accent/50"
                      >
                        <div className="mb-1 flex items-center gap-2">
                          {entry.type && (
                            <span className="rounded bg-accent px-1.5 py-0.5 font-dmmono text-[9px] uppercase text-muted/60">
                              {entry.type}
                            </span>
                          )}
                          {entry.key && (
                            <span className="font-dmmono text-[10px] uppercase text-muted/60">
                              {entry.key}
                            </span>
                          )}
                          {entry.score !== undefined && (
                            <span className="ml-auto font-dmmono text-[10px] text-muted/40">
                              {(entry.score * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                        <p className="line-clamp-3 text-xs text-primary/80">
                          {entry.content}
                        </p>
                        {entry.sessionId && (
                          <p className="mt-1 font-dmmono text-[9px] text-muted/40 truncate">
                            {entry.sessionId}
                          </p>
                        )}
                        {entry.tags && entry.tags.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {entry.tags.map((tag) => (
                              <span
                                key={tag}
                                className="rounded-full bg-accent px-1.5 py-0.5 font-dmmono text-[9px] text-muted"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
