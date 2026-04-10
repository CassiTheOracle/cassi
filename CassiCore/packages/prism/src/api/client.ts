export interface EngramPosition {
  id: string
  x: number
  y: number
  t: number
  potentiation: number
  nodeType: string
  clusterId: string | null
}

export interface Engram {
  id: string
  content: string
  nodeType: string
  x: number
  y: number
  t: number
  potentiation: number
  clusterId: string | null
  tags: string[]
  provenance: string
  createdAt: string
  accessedAt: string | null
  metadata: Record<string, unknown>
}

export interface MnemicSynapse {
  sourceId: string
  targetId: string
  edgeType: string
  weight: number
  createdAt: string
  metadata: Record<string, unknown>
}

export interface KindlingTrace {
  iteration: number
  charges: Record<string, number>
}

export interface ChargedEngram {
  engram: Engram
  charge: number
}

export interface LuminalSet {
  engrams: ChargedEngram[]
  totalCharge: number
  seedCount: number
  iterationsUsed: number
  sparkPoint: number
  taskComplexity: string
  durationMs: number
  trace?: KindlingTrace[]
}

export interface FieldStats {
  engramCount: number
  synapseCount: number
  spikeCount: number
  nucleusCount: number
  avgPotentiation: number
}

export interface NeighborResponse {
  center: Engram
  neighbors: Engram[]
  synapses: MnemicSynapse[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  getPositions: () =>
    request<{ count: number; positions: EngramPosition[] }>('/prism/positions'),

  getSpatial: (bounds: Record<string, number>) =>
    request<{ count: number; engrams: Engram[] }>('/prism/spatial', {
      method: 'POST',
      body: JSON.stringify(bounds),
    }),

  getNeighbors: (id: string) =>
    request<NeighborResponse>(`/prism/neighbors/${encodeURIComponent(id)}`),

  kindle: (query: string, complexity = 'normal') =>
    request<{ luminalSet: LuminalSet }>('/prism/kindle', {
      method: 'POST',
      body: JSON.stringify({ query, complexity }),
    }),

  getStats: () =>
    request<{ stats: FieldStats }>('/prism/stats'),
}
