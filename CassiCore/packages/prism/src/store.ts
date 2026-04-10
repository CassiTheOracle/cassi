import { create } from 'zustand'
import type {
  EngramPosition, NeighborResponse, LuminalSet, FieldStats,
} from './api/client.js'

export type ViewMode = 'temporal-depth' | 'potentiation-landscape' | 'flat-field'

export interface KindleState {
  luminalSet: LuminalSet | null
  frame: number
  playing: boolean
  speed: number
}

export interface PrismStore {
  positions: EngramPosition[]
  setPositions: (p: EngramPosition[]) => void

  viewMode: ViewMode
  setViewMode: (m: ViewMode) => void

  selectedEngram: string | null
  setSelectedEngram: (id: string | null) => void

  hoveredEngram: string | null
  setHoveredEngram: (id: string | null) => void

  detailData: NeighborResponse | null
  setDetailData: (d: NeighborResponse | null) => void

  kindle: KindleState
  setKindle: (k: Partial<KindleState>) => void

  stats: FieldStats | null
  setStats: (s: FieldStats) => void
}

export const useStore = create<PrismStore>((set) => ({
  positions: [],
  setPositions: (positions) => set({ positions }),

  viewMode: 'temporal-depth',
  setViewMode: (viewMode) => set({ viewMode }),

  selectedEngram: null,
  setSelectedEngram: (selectedEngram) => set({ selectedEngram }),

  hoveredEngram: null,
  setHoveredEngram: (hoveredEngram) => set({ hoveredEngram }),

  detailData: null,
  setDetailData: (detailData) => set({ detailData }),

  kindle: { luminalSet: null, frame: 0, playing: false, speed: 1 },
  setKindle: (k) => set((s) => ({ kindle: { ...s.kindle, ...k } })),

  stats: null,
  setStats: (stats) => set({ stats }),
}))
