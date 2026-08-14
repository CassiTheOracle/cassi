# @cassicore/host

The **thin host** package — the composition root that boots every landed CassiCore
package. Migrated (history-preserved) from the D: source repo, committed at
cassicore `d63358da`.

## What lives here

| source (D:) | dest (here) |
|---|---|
| `core/entry/` (5) | `src/entry/` — supervisor, daemon-main, vindex-loader, code-extractor |
| `core/daemon.ts` (166 KB) | `src/daemon.ts` — the composition/boot class |
| `core/daemon/boot-intelligence-post.ts` + `primary-session-router.ts` | `src/daemon/` — live daemon modules |
| `core/cli/` (12) | `src/cli/` — the `cassicore` CLI + runtime |
| `core/bridge/` (6 live) | `src/bridge/` — ACP (bin/client/server/translator/types) + openai createBridge |
| `core/version.ts` | `src/version.ts` — `CASSICORE_VERSION` / `CASSICORE_BUILD_STRING` |
| `scripts/qwen-renew-accounts.ts` | `src/scripts/` — P8 AI deps re-point |
| `bin/cassicore`, `bin/cassi-acp` | `bin/` — launcher scripts |

**Excluded (DEAD):** `core/daemon/{boot-channels,boot-providers,boot-types,channel-loader}.ts`.
**Quarantined (UNCERTAIN):** `core/daemon/{boot-configuration,boot-intelligence-pre,boot-pipeline-tools,intelligence-wiring}.ts`,
`core/bridge/acp/index.ts`.

## Wiring seams this host grounds (P7 §7)

`setRootResolver` (foundation), `setDataDirRoot` (constellation),
`createAdminApi(daemon, logger).start()` (admin-api), `registerCoreTools(deps)` (tools),
`PluginHost.load(…)` per channel (plugins), `resolveWorker('@cassicore/workers/…')`
(workers), `createModelRouter`/`createBudgetTracker` (providers), and the
supervisor/fork + CLI bins. See `P7-host-entry-migration-table.md` §7.

## daemon decomposition

(b)-lite: `core/daemon.ts`'s structure is preserved verbatim; only its imports and
the §7 package-boundary wiring calls were rewritten. Full phase-splitting is
deferred to the overhaul session.
