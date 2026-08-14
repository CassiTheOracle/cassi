import type { EngramPosition } from '../api/client.js'

export type ViewModeId = 'temporal-depth' | 'potentiation-landscape' | 'flat-field'

export interface ViewModeTransform {
  id: ViewModeId
  label: string
  compute: (positions: EngramPosition[]) => Float32Array
}
