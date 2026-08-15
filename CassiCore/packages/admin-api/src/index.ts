/**
 * @cassicore/admin-api root barrel.
 *
 * Re-exports the admin API surface the host mounts: `createAdminApi(daemon, logger)`
 * + the runtime facade + the route modules (via ./routes). This file is the package's
 * `main`/`types` root (package.json exports "."); the route modules are also available
 * as the `@cassicore/admin-api/routes` subpath.
 */
export { createAdminApi } from './admin-api.js'
export { createAdminRuntimeFacade, type AdminRuntimeFacade } from './routes/runtime.js'
export { executeTurn, getPreferredTurnEngine } from './routes/turn-routing.js'
export type { ILogger } from '@cassicore/foundation'
