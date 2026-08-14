/**
 * VENDOR TYPE/runtime STUB — core/daemon.ts version surface (host, P7 host publishes).
 *
 * health.ts imports the daemon's version constants (CASSICORE_VERSION,
 * CASSICORE_BUILD [BuildIdentifier object], CASSICORE_BUILD_STRING) and reads
 * CASSICORE_BUILD.version / .gitRef. Re-points to @cassicore/host's version.ts
 * (or daemon) when the host publishes.
 */

/** The daemon's build identifier object. */
export interface BuildIdentifier {
  version: string
  gitRef: string
  buildDate?: string
  [key: string]: string | undefined
}

export const CASSICORE_VERSION = 'unknown'
export const CASSICORE_BUILD: BuildIdentifier = {
  version: 'unknown',
  gitRef: 'unknown',
}
export const CASSICORE_BUILD_STRING = 'unknown'
