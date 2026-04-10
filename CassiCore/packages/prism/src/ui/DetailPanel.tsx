import { useStore } from '../store.js'
import { api } from '../api/client.js'

const TYPE_COLORS: Record<string, string> = {
  fact: '#4FC3F7', episode: '#AB47BC', decision: '#FF7043', pattern: '#66BB6A',
  abstraction: '#FFCA28', goal: '#EF5350', file: '#78909C', tool: '#26C6DA',
  session: '#7E57C2', outcome: '#FFA726', source_file: '#8D6E63',
  changeset: '#EC407A', artifact: '#26A69A',
}

export function DetailPanel() {
  const selectedEngram = useStore((s) => s.selectedEngram)
  const detailData = useStore((s) => s.detailData)
  const setSelectedEngram = useStore((s) => s.setSelectedEngram)
  const setDetailData = useStore((s) => s.setDetailData)

  if (!selectedEngram || !detailData) return null

  const { center, neighbors, synapses } = detailData

  return (
    <div className="absolute top-4 right-4 w-96 max-h-[80vh] overflow-y-auto bg-zinc-900/95 border border-zinc-700 rounded-lg p-4 text-zinc-100 text-sm backdrop-blur-sm">
      <div className="flex justify-between items-start mb-3">
        <span
          className="px-2 py-0.5 rounded text-xs font-mono font-semibold"
          style={{ backgroundColor: TYPE_COLORS[center.nodeType] ?? '#666', color: '#000' }}
        >
          {center.nodeType}
        </span>
        <button
          onClick={() => { setSelectedEngram(null); setDetailData(null) }}
          className="text-zinc-400 hover:text-white text-lg leading-none"
        >
          &times;
        </button>
      </div>

      <div className="mb-3 text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
        {center.content}
      </div>

      <div className="flex gap-3 text-xs text-zinc-500 mb-3">
        <span>potentiation: {center.potentiation.toFixed(3)}</span>
        <span>{center.createdAt.slice(0, 10)}</span>
      </div>

      {center.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {center.tags.map((t) => (
            <span key={t} className="px-1.5 py-0.5 bg-zinc-800 rounded text-xs text-zinc-400">
              {t}
            </span>
          ))}
        </div>
      )}

      <div className="mb-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        Potentiation
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full mb-4">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min(center.potentiation * 100, 100)}%`,
            backgroundColor: TYPE_COLORS[center.nodeType] ?? '#666',
          }}
        />
      </div>

      {synapses.length > 0 && (
        <>
          <div className="mb-2 text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            Synapses ({synapses.length})
          </div>
          <div className="space-y-1.5">
            {synapses.slice(0, 20).map((s, i) => {
              const neighbor = neighbors.find(
                (n) => n.id === (s.sourceId === center.id ? s.targetId : s.sourceId)
              )
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-xs p-1.5 rounded bg-zinc-800/50 cursor-pointer hover:bg-zinc-800"
                  onClick={() => {
                    if (neighbor) {
                      setSelectedEngram(neighbor.id)
                      api.getNeighbors(neighbor.id).then(setDetailData)
                    }
                  }}
                >
                  <span className="text-zinc-500 font-mono w-28 shrink-0">{s.edgeType}</span>
                  <span className="text-zinc-400 truncate">{neighbor?.content.slice(0, 60) ?? '...'}</span>
                  <span className="text-zinc-600 ml-auto shrink-0">{s.weight.toFixed(2)}</span>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
