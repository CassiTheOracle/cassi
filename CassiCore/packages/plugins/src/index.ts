// core/plugins/index.ts — Barrel export for the plugin system

export { PluginRegistry } from './plugin-registry.js'
export { PluginAPI } from './plugin-api.js'
export type { PluginAPIDeps, PluginAPIResult } from './plugin-api.js'
export { CassiCoreClient } from './client-sdk.js'
export type { CassiCoreClientConfig } from './client-sdk.js'

// External client integration layer (thalamus-based context curation for editors)
export { ExternalClientCurator } from './external-clients/index.js'
export type {
  ExternalCurateRequest,
  ExternalCurationResult,
  ExternalMessageDigest,
  CurationGap,
} from './external-clients/index.js'
