# @cassicore/flux-team

> **DEPRECATED:** blackboard is superseded by GlobalWorkspace + HelixSynapse (per
> docs/design/constellation-enhancements-roadmap.md); this package is migrated as-is for
> live blackboard consumers until the overhaul session's GlobalWorkspace migration
> supersedes it at P5.

FluxTeam blackboard subsystem extracted from CassiCore (history-preserved) into a
standalone TypeScript ESM package. Owns the `Blackboard`, `GlobalBlackboardRegistry`,
blackboard-tools routing, and the blackboard-search cursor/pagination runtime helpers.

## Status

Migrated at **P3** of the cassi-mind plan. The 6 live files under `src/` carry their
cassicore git history via an import splice. Two kinds of import rewiring were applied:

1. **`@cassicore/foundation`** — the shared substrate (types + search constants).
   Blackboard and its siblings import the type surface from the P1 foundation package.
2. **`src/vendor/**`** — a single **runtime exact-copy** stub:
   `src/vendor/core/intelligence/shared-tools/commit-tool.ts` (`COMMIT_CHANGES_TOOL` +
   `handleCommitChanges`) — a pure tool factory + `execSync` wrapper, self-contained on
   `@cassicore/foundation` + `child_process`. It is a faithful copy of the D: original;
   it re-points to `@cassicore/*-shared-tools` at P5.

### Deprecation contract

The `src/index.ts` entry barrel carries the source "Pending Removal (Phase 2)" banner
verbatim. The package is **deprecated in source**; release as-is for live blackboard
consumers, with **no** runtime deprecation warnings or behavioral changes. Deletion is
phase-gated (follows the D: debt scrub) after flux-team's migration is verified.

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite
```
