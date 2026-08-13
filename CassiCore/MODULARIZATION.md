# CassiCore Modularization — Workspace Blueprint

**Status:** In progress — first module (Constellation) extracted; the rest slated to follow.
**Root:** `C:\Users\Carina\Workspaces\CassiCore\`
**Date:** 2026-08-13

---

## (a) Vision

CassiCore (`D:\carina\workspaces\cassicore`) is a TypeScript ESM monorepo (Node ≥ 20)
containing a daemon, an intelligence layer, an admin API, and an MCP gateway. Today it is
one coupled tree. The goal of this workspace is to progressively decompose it into a set of
**standalone, testable, plugin-ready TypeScript packages** that can eventually ship as
**ohmpy-style extensions** (`(pi: ExtensionAPI) => …`).

Each extracted module becomes its own package under this root. The first extraction —
**Constellation** — is the template. Everything a future module needs (recon → dependency
classification → vendor-vs-port decision → mechanical copy waves → integration → verification)
is captured in this document and in `Constellation/EXTRACTION-PLAN.md`.

Why extract:

- Keeps constellation's ~2.5 MB / 87-file subsystem testable in isolation.
- Replaces invisible cross-tree coupling with explicit package boundaries and ports.
- Turns future ohmypi adaptation into a **wiring problem** (swap ports) instead of a surgery problem.

Non-goals (this phase):

- Refactoring the subsystem's internals — only its package boundaries change.
- Wiring the package into the CassiCore daemon or any ohmypi host — that is a later phase.
- Modifying anything under `D:\carina\workspaces\cassicore`.

---

## (b) The Extraction Recipe (demonstrated on Constellation)

Repeat for every future module. Step order is fixed; each step has an explicit stop condition.

1. **Reconnaissance (read-only).** Produce a dependency map:
   - File inventory of the subsystem (`.ts` files, sizes, subdir structure).
   - Full import extraction: all `from '…'`, side-effect imports, and inline `import('…')` type refs.
   - Classification of every **external target** as TYPE-ONLY vs RUNTIME (per-symbol).
   - Consumer map (who outside the subsystem imports it) + the adapter/call boundary.
   - Test inventory.
   Output: `recon.md` (see `D:\carina\workspaces\cassicore\.opencode\plans\constellation-extraction-recon.md`).

2. **Dependency classification.** For every runtime external target, read the actual source and
   judge **transitive weight**:
   - Does it pull daemon/process/gateway code? → **PORT**.
   - Is it self-contained (only builtins / type-only / sibling runtime it can carry)? → **VENDOR**.
   All TYPE-ONLY targets → **vendor type stub**.
   Record VENDOR vs PORT + rationale per target in `EXTRACTION-PLAN.md`.

3. **Vendor-vs-Port decision rule.**
   - **VENDOR**: copy the file into `src/vendor/` (plus its transitive type-only deps). If a
     vendored file has its own RUNTIME transitive deps that pull daemon code → fold back to PORT.
   - **PORT**: define a minimal interface in `src/ports/<name>.ts` covering exactly the surface
     the subsystem uses, plus a default implementation — functional where cheap (in-memory
     logger/bus, fs-backed store), explicit `throw new ...('not connected')` where real
     integration is required (helix pipeline, MCP consolidated tools).
     Ports make future ohmypi adaptation a wiring problem.

4. **Migration table.** Per source file: `source → dest` under `src/` (mirror the subdir structure),
   plus exact import-rewrite pairs. Rules MUST be mechanical string substitutions — an executor
   applies them verbatim with sed-like edits, zero judgment required. Include inline
   `import('…')` type-expression rewrites.

5. **Mechanical copy waves.** Copy 87 files (unchanged bodies), apply the rewrite table verbatim.

6. **Integration.** Wire setter/injection surface (e.g. the `createConstellationOrchestrator`
   factory + `setModelPool`/`setMnemicField`/etc. adapter points from recon §3F) behind ports.

7. **Verification.** `tsc --noEmit` clean under the module's own tsconfig + `src/vendor`/`src/ports`
   compile independently. Tests are ported later, not in this phase.

---

## (c) Package Conventions

Each module under this root follows the Constellation template:

- **Name:** `@cassicore/<module>` (e.g. `@cassicore/constellation`).
- **Layout:**
  ```
  CassiCore/<Module>/
    package.json          name @cassicore/<module>, "type": "module", exports ./dist/index.js
    tsconfig.json         mirrors CassiCore compiler settings; rootDir src; outDir dist; declaration true
    vitest.config.ts      minimal
    README.md             what/status/build/test/ports concept
    src/
      index.ts            barrel (planned public surface)
      <subdir>…           the extracted files, subdir structure mirrored
      ports/              port interfaces + default implementations (self-contained)
      vendor/             vendored runtime utilities + type stubs (faithful copies)
      vendor/types/       type stubs mirroring types/*.js (e.g. types/interfaces.js → vendor/types/interfaces.ts)
  ```
- **Import style:** ESM with `.js` extensions (matches CassiCore source). Local/internal imports
  keep `.js`.
- **Ports pattern:** a port is a plain TypeScript interface + a default impl. Self-contained — no
  imports from CassiCore. The port file is the ONLY seam between the module and the host.
- **Vendor rule:** faithful copies, do not trim fields. Vendored runtime utilities live at
  `src/vendor/`; type stubs mirror original paths under `src/vendor/<area>/…`.

---

## (d) Foundation-Package Roadmap (from recon §7)

The recon identified the most pervasive shared dependencies across `core/intelligence/`.
These become the first shared foundation packages so future extractions don't re-vendor them:

| Priority | Candidate | Surface | Consumers (other dirs) |
|---|---|---|---|
| Tier 1 | `types/interfaces.js` | `ILogger`, `IEventBus` (+ `IConfig`, `WiringDependencies`, `IntelligenceModule`) | 47 dirs |
| Tier 1 | `types/runtime.js` / `types/intelligence.js` / `types/model-routing.js` | `ThinkingLevel`, `Message`, `ContentBlock`, `CompletionChunk`; `IMemory`, `SearchResult`; `IModelDirective`, `RoutingTier` | 16 / 14 / 5 dirs |
| Tier 1 | `base/cognitive-module.js` | `BaseCognitiveModule` (+ `model-config`, `inference`) | 18 dirs |
| Tier 1 | `utils/paths.js` | `getDataDir`/`getCassiCoreHome` (parameterize data dir) | 11 dirs |
| Tier 1 | `config/system-settings.js` | `MODEL_DEFAULTS` (+ `SYSTEM_SETTINGS`) | 8 dirs |
| Tier 1 | `mnemic-field/types.js` | `SynapseType`, `Engram`, `SYNAPSE_PROPAGATION` | 11 dirs |
| Tier 1 | `phrase-prototypes.js` | phrase sets | 6 dirs |
| Tier 2 | `embeddings/embedding-service.js` · `cortex/index.js` · `module-session-registry.js` · `types/flux-team.js` · `gaming-mode.js` · `node:*`/`better-sqlite3`/`uuid` utility surface | | multiple |

In this first extraction these are handled module-locally (VENDOR type stubs / ports). A later
**foundation** package (`@cassicore/foundation`) should absorb Tier-1 items and be shared, so
future modules import the shared package instead of re-vendoring.

---

## (e) Phased Order for Future Module Extractions

Approximate plan — each phase is one module extraction following the recipe. Order minimizes
foundation re-vendoring and respects the dependency tiers (extract the most-shared foundations
early, modules that depend on them later).

1. **Foundation package** — `types/*` (interfaces, runtime, intelligence, model-routing,
   flux-team, workflow), `utils/paths`, `config/system-settings`, `phrase-prototypes`,
   `base/cognitive-module` cluster, `node:*` utility surface. This is the shared substrate.
2. **helix** — (helix-pipeline, brainstem, brainstem-mini-helix, observer-activity-scheduler,
   helix-store, helix-synapse, posture-runner, work-stream, coordinator…). Large runtime surface;
   deepest dependencies. Needs the foundation first.
3. **flux-team** — (blackboard, blackboard-search, global-blackboard-registry…). Depends on
   foundation + helix.
4. **mini-helix** — (mini-helix-runner, mini-helix-types). Depends on foundation.
5. **mnemic-field** — (index, graph-attn-propagator, types, edge-relators, self-model/*).
   Depends on foundation + embeddings.
6. **embeddings** — (embedding-service). Foundation.
7. **intelligence core** — the `core/intelligence/*` siblings not yet extracted
   (cortex, aurora, lamina, thalamus, workspace, code-analysis, context-distiller,
   module-session-registry, shared/posture-store, gaming-mode).
8. **workflow engine** — `core/workflow/{builder,steps,templates}` (self-contained; could be
   extracted earlier).
9. **mcp/gateway** — the consolidated tools + agent-tools + admin-api adapter. This is the
   host-facing seam; extracted last as it binds everything together.
10. **daemon + providers + model-pool + tools** — remaining root-level infrastructure.

Each module ships with its own `EXTRACTION-PLAN.md` mirroring the Constellation template.

---

## (f) Known ohmypi Adaptation Notes (NOT implemented — for later)

Recorded here so future wiring work doesn't rediscover them. Do NOT act on them in this phase.

- **`better-sqlite3` → `bun:sqlite`.** All stores (constellation-store, meditation-store,
  constellation-analyzer) use `better-sqlite3` `Database`. The ohmypi/omp host is Bun-based;
  `bun:sqlite` is the natural replacement. The port seam for DB access should hide this swap.
- **`vitest` → `bun:test`.** Test syntax (describe/it/expect) is compatible; the runner differs.
  `vitest.config.ts` exists now; a `bun:test` variant is trivial later.
- **Extension factory shape `(pi: ExtensionAPI)`.** ohmpy extensions are factories taking an
  `ExtensionAPI`; the Constellation package should expose a `createConstellationOrchestrator`
  factory (already its natural shape) that could be adapted to `pi` without structural change.
- **Package scope mapping.** `@cassicore/*` npm packages map onto the ohmypi extension naming/
  registry. Ports (`src/ports/*`) are the wiring seams; the same ports appear in ohmypi as the
  host's `ExtensionAPI` surface.
- **Path/data-dir parameterization.** `utils/paths.js` hardcodes `~/.cassicore`. For standalone +
  plugin use, `getDataDir` must be parameterized (inject a data root) rather than read
  `~/.cassicore`. Ports should accept an explicit base dir.

---

## How to run the received package

```bash
cd C:\Users\Carina\Workspaces\CassiCore\Constellation
npm install              # after reviewer/wiring completes
npm run build            # tsc → dist/
npm test                 # vitest run
```

See `Constellation/README.md` and `Constellation/EXTRACTION-PLAN.md`.

---

## Appendix — Template handoff checklist (for each future module)

- [ ] recon.md exists with file inventory, import map, external target classification, consumers, tests.
- [ ] EXTRACTION-PLAN.md has a VENDOR/PORT decision for every external runtime target + a complete per-file migration table with mechanical rewrite rules.
- [ ] package.json + tsconfig.json + vitest.config.ts + .gitignore + README present.
- [ ] `src/ports/*` and `src/vendor/**` self-contained and compile alone.
- [ ] source files not yet copied (that is a later parallel wave) unless the module boundary is committed.
