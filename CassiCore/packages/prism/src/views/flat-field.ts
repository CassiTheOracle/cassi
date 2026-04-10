import type { EngramPosition } from '../api/client.js'
import type { ViewModeTransform } from './types.js'

export const flatField: ViewModeTransform = {
  id: 'flat-field',
  label: 'Flat Field',
  compute(positions: EngramPosition[]): Float32Array {
    const arr = new Float32Array(positions.length * 3)
    const SPATIAL_SCALE = 50
    for (let i = 0; i < positions.length; i++) {
      const p = positions[i]
      arr[i * 3] = p.x * SPATIAL_SCALE
      arr[i * 3 + 1] = p.y * SPATIAL_SCALE
      arr[i * 3 + 2] = 0
    }
    return arr
  },
}
