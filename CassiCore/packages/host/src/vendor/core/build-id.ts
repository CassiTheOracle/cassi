/**
 * Legacy build-id module — re-exports from the canonical version.ts.
 * 
 * Kept for backward compatibility. New code should import from
 * core/version.ts directly.
 * 
 * @deprecated Import from '../version.js' instead.
 */

export {
  CASSICORE_VERSION,
  CASSICORE_BUILD,
  CASSICORE_BUILD_STRING,
  NEXT_BUMP,
  GIT_REF,
  HAS_GIT,
  BUILD_DIRTY,
  GATEWAY_VERSION,
  getBuildIdentifier,
  formatBuildId,
  getRepoRoot,
  type BuildIdentifier,
} from '../../version.js'
