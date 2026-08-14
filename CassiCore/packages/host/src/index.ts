/**
 * @cassicore/host root barrel.
 *
 * Re-exports the host's own composition surface + host-vendored core modules
 * that P7 re-points consumers to (version, session-store, turn-pipeline).
 * This file is the package `main`/`types` root.
 */
export * from './version.js'
export { SessionStore, type SessionRow, OptimisticLockError } from './vendor/core/session-store.js'
export { TurnPipeline, type TurnMiddleware, setContextWindowDebugger, contextWindowDebugMiddleware } from './vendor/core/turn-pipeline.js'
