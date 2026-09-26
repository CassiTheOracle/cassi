/**
 * @cassicore/foundation — Version metadata (pure constants).
 *
 * Substrate-safe home for the reported CassiCore release/build constants,
 * migrated from the tools/mcp `vendor/core/version.ts` stubs (P1 cycle fix).
 *
 * The host remains the single source of truth for the ACTUAL build identity
 * (`packages/host/src/version.ts` derives it from git/package.json at boot);
 * these constants are the STATIC REPORTING values that retained packages
 * (tools' hermes-mcp-client, mcp client) use for client-info labels. Hosted in
 * foundation (not the host) so tools/mcp/mcp-gateway can consume them with
 * zero `tools/mcp → host` dependency edge — resolving the host↔tools|mcp cycle
 * without a new injection seam for what is static metadata.
 */

/** Release version of this build. */
export const CASSICORE_VERSION: string = '0.1.0'

/** Build version string. */
export const CASSICORE_BUILD: string = '0.1.0'

/** Full build string. */
export const CASSICORE_BUILD_STRING: string = '0.1.0'

/** Next version bump. */
export const NEXT_BUMP: 'major' | 'minor' | 'patch' | 'none' = 'none'

/** Current git ref. */
export const GIT_REF: string = ''

/** Whether the working tree is dirty. */
export const BUILD_DIRTY: boolean = false

/** Gateway version (same as release). */
export const GATEWAY_VERSION: string = CASSICORE_VERSION

/** Build identifier shape. */
export interface BuildIdentifier {
  buildId: string
  gitRef: string
  dirty: boolean
  releaseVersion: string
  buildVersion: string
}

/** Get the build identifier for this build. */
export function getBuildIdentifier(): BuildIdentifier {
  return {
    buildId: CASSICORE_VERSION,
    gitRef: GIT_REF,
    dirty: BUILD_DIRTY,
    releaseVersion: CASSICORE_VERSION,
    buildVersion: CASSICORE_BUILD,
  }
}

/** Format a build identifier into a display string. */
export function formatBuildId(id?: BuildIdentifier): string {
  const b = id ?? getBuildIdentifier()
  return `${b.releaseVersion} (${b.buildId}${b.dirty ? '-dirty' : ''})`
}
