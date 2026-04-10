import type { EngramPosition } from '../api/client.js'
import type { ViewModeTransform } from './types.js'

export const temporalDepth: ViewModeTransform = {
  id: 'temporal-depth',
  label: 'Temporal Depth',
  compute(positions: EngramPosition[]): Float32Array {
    const arr = new Float32Array(positions.length * 3)
    const SPATIAL_SCALE = 50
    const Z_RANGE = 40

    const indices = Array.from({ length: positions.length }, (_, i) => i)
    indices.sort((a, b) => positions[a].t - positions[b].t)

    const rank = new Float32Array(positions.length)
    const denom = positions.length - 1 || 1
    for (let r = 0; r < indices.length; r++) {
      rank[indices[r]] = r / denom
    }

    for (let i = 0; i < positions.length; i++) {
      const p = positions[i]
      arr[i * 3] = p.x * SPATIAL_SCALE
      arr[i * 3 + 1] = p.y * SPATIAL_SCALE
      arr[i * 3 + 2] = rank[i] * Z_RANGE - Z_RANGE / 2
    }
    return arr
  },
}
