/** VENDORED TYPE STUB — mirrors `flux-team/global-blackboard-registry.js`. Surface used by cognitive-module. */
export interface GlobalBlackboardRegistry {
  getOrCreate(name: string, opts?: { persist?: boolean }): Blackboard
  [key: string]: unknown
}
import type { Blackboard } from './blackboard.js'
