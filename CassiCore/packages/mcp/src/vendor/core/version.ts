/**
 * VENDOR RUNTIME STUB — `core/version.ts` (pure constants).
 *
 * Faithful pure-constant surface (avoiding the execSync/git describe used by
 * the source). Owned home `[OPEN]` (a tiny `@cassicore/version` or folded into
 * foundation at P7 — plan Open-4). Consumed by `hermes-mcp-client.ts`
 * (CASSICORE_VERSION) and `@cassicore/mcp` later.
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
