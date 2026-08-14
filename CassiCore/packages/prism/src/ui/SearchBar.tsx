import { useState, useCallback } from 'react'
import { api } from '../api/client.js'
import { useStore } from '../store.js'

const COMPLEXITIES = ['simple', 'normal', 'complex'] as const

export function SearchBar() {
  const [query, setQuery] = useState('')
  const [complexity, setComplexity] = useState<string>('normal')
  const [loading, setLoading] = useState(false)
  const setKindle = useStore((s) => s.setKindle)

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || loading) return
    setLoading(true)
    try {
      const { luminalSet } = await api.kindle(query, complexity)
      setKindle({
        luminalSet,
        frame: 0,
        playing: true,
        speed: 1,
      })
    } finally {
      setLoading(false)
    }
  }, [query, complexity, loading, setKindle])

  const handleReset = useCallback(() => {
    setKindle({ luminalSet: null, frame: 0, playing: false })
  }, [setKindle])

  return (
    <form
      onSubmit={handleSubmit}
      className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-zinc-900/90 border border-zinc-700 rounded-lg px-3 py-2 backdrop-blur-sm"
    >
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Kindle the field..."
        className="bg-transparent text-zinc-100 text-sm outline-none w-64 placeholder:text-zinc-600"
      />
      <select
        value={complexity}
        onChange={(e) => setComplexity(e.target.value)}
        className="bg-zinc-800 text-zinc-300 text-xs rounded px-1.5 py-1 border border-zinc-700 outline-none"
      >
        {COMPLEXITIES.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <button
        type="submit"
        disabled={loading}
        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-700 text-white text-xs rounded font-medium"
      >
        {loading ? '...' : 'Kindle'}
      </button>
      <button
        type="button"
        onClick={handleReset}
        className="px-2 py-1 text-zinc-500 hover:text-zinc-300 text-xs"
      >
        Reset
      </button>
    </form>
  )
}
