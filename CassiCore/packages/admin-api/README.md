# @cassicore/admin-api

The CassiCore admin HTTP route registry + server mount, extracted from
`core/admin-api.ts` (`createAdminApi`) and `core/admin-api/`. History-preserved
import splice. Excluded (DEAD): `activity.ts`, `metrics.ts`, `team-timeline.ts`;
quarantined (UNCERTAIN): `system-prompt.ts`.

## Surface

- `src/admin-api.ts` — `createAdminApi(daemon, logger)` (route registry + server mount,
  Unix socket `~/.cassicore/admin.sock` + TCP `admin.host:admin.port` default
  `127.0.0.1:7433`, EADDRINUSE port-scan). The HTTP route contract (`parts[0]`-namespaced
  paths + method, per §1e of the P7 table) is preserved verbatim.
- `src/routes/` — 54 live route modules: `index.ts` (barrel) + `runtime.ts`
  (`createAdminRuntimeFacade`) + `turn-routing.ts` + the 51 `handleXxxRoutes` modules +
  `replay.test.ts`.

## Vendored / deferred

Host-coupled modules (re-point to `@cassicore/host` when the host publishes):
- `src/vendor/core/{timeline-store,session-store,turn-pipeline,tools-api}.ts` +
  `src/vendor/core/workspace/loader.ts` + `src/vendor/core/testing/*` +
  `src/vendor/core/scripts/qwen-renew-accounts.ts` + `src/vendor/core/daemon/daemon.ts`
  (`../daemon.js` in health.ts) + `src/vendor/core/runtime/audit/*`.

Brain-region modules not exposed by any landed package barrel:
- `src/vendor/core/intelligence/{context-repo,context-assembler,smart-compaction}.js` (when not
  re-pointed to a landed barrel).

Depends on foundation, providers, plugins, jobs, mcp-gateway and the landed
brain-region packages (mnemic-field, cortex-pineal-dialectic, lamina-locus-bridge,
dreamer-reverie-subconscious, helix, flux-team, embeddings, constellation, thalamus).
