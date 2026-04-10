import { useStore } from '../store.js'
import type { ViewMode } from '../store.js'
import { getAllViewModes } from '../scene/view-utils.js'

export function ViewSwitcher() {
  const viewMode = useStore((s) => s.viewMode)
  const setViewMode = useStore((s) => s.setViewMode)

  return (
    <div className="absolute top-4 left-4 flex gap-1 bg-zinc-900/90 border border-zinc-700 rounded-lg p-1 backdrop-blur-sm">
      {getAllViewModes().map((vm) => (
        <button
          key={vm.id}
          onClick={() => setViewMode(vm.id as ViewMode)}
          className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
            viewMode === vm.id
              ? 'bg-indigo-600 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
        >
          {vm.label}
        </button>
      ))}
    </div>
  )
}
