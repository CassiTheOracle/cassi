/**
 * Legacy build-id module — retained in @cassicore/mind-runtime (P5).
 *
 * The host's canonical `version.ts` was retired with the standalone host surface
 * (CASSICORE-FOCUS §5 #26); the static reporting values now live in
 * `@cassicore/foundation`'s `config/version.ts` (P1 ports re-home). Kept as a thin
 * re-export for any retained vendored module that still references the old path.
 * `HAS_GIT` / `getRepoRoot` (host git-derivation) were dropped — nothing in the
 * retained brain uses them.
 */

export {
  CASSICORE_VERSION,
  CASSICORE_BUILD,
  CASSICORE_BUILD_STRING,
  NEXT_BUMP,
  GIT_REF,
  BUILD_DIRTY,
  GATEWAY_VERSION,
  getBuildIdentifier,
  formatBuildId,
  type BuildIdentifier,
} from '@cassicore/foundation'
