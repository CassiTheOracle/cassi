import { useStore } from '../store.js'

export function StatsOverlay() {
  const positions = useStore((s) => s.positions)
  const stats = useStore((s) => s.stats)
  const kindle = useStore((s) => s.kindle)

  return (
    <div className="absolute bottom-4 left-4 text-xs font-mono text-zinc-600 space-y-0.5">
      <div>{positions.length.toLocaleString()} engrams</div>
      {stats && (
        <>
          <div>{stats.synapseCount.toLocaleString()} synapses</div>
          <div>avg potentiation: {stats.avgPotentiation.toFixed(3)}</div>
        </>
      )}
      {kindle.luminalSet && (
        <div className="text-indigo-400">
          kindle: {kindle.luminalSet.engrams.length} lit / {kindle.luminalSet.iterationsUsed} iter / {kindle.luminalSet.durationMs}ms
        </div>
      )}
    </div>
  )
}
