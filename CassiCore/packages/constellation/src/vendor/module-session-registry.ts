/** VENDORED TYPE STUB — mirrors `module-session-registry.js`. Surface: ModuleSessionRegistry. */
export interface ModuleSessionRegistry {
  getOrCreate(name: string): { id: string }
  getSessionId(name: string): string | undefined
  [key: string]: unknown
}
