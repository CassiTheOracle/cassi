/** VENDORED TYPE STUB — mirrors `tools/registry.js` (core/tools). Surface: ToolRegistry. */
import type { ToolDefinition, ToolSchema } from './types.js'

export interface ToolListOptions {
  enabled?: boolean
  kind?: string
  [key: string]: unknown
}

export interface ToolRegistry {
  get(name: string): unknown
  list(options?: ToolListOptions): ToolDefinition[]
  toAnthropicSchema(): ToolSchema[]
  [key: string]: unknown
}
