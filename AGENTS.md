# Repository Guidelines

Governance for AI assistants working in the unified Cassi workspace: `C:/Users/Carina/workspaces/cassi`. Four **independent nested git repos** sit under a **docs-only root repo** — no submodules, no shared build system (by design). This file governs cross-repo work and the repos without their own guidelines; where it conflicts with a sub-repo's own rules, the sub-repo wins.

## Project Overview

The unification program (see `UNIFICATION.md`): build a "field-AI" on the thesis that intelligence is steering the flow of coherence. The two-fluid Yang/Yin field **is** the computation; the AI is whatever steers it.

| Repo | Role |
|---|---|
| `CassiCosmos/` | **The substrate.** Godot 4.7.1 Mono GPU space-sim; the field runs on the RX 7900 XTX as a live physics engine with TCP bridges. Most active repo. |
| `CassiCore/` | **Orchestration + memory.** npm-workspaces TS monorepo, 22 retained `@cassicore/*` packages; mind-runtime (HTTP 7273), mnemic-field, ohmypi spine. |
| `CassiTheory/` | **The laws.** Markdown theory doc-graph + Python solvers/pipelines. Has its own `CassiTheory/AGENTS.md` — read it before any CassiTheory edit. |
| `CassiAI/` | **Archive, reference only.** Python/PyTorch+Vulkan predecessors. Code is never used or modified; lessons (steering over prediction, increment metric) are consulted. Its own `CassiAI/AGENTS.md` describes the old stack as live — stale, do not follow. |

Root repo tracks `README.md`, `UNIFICATION.md`, this guidance, and the integrated project trees; generated/local artifacts stay ignored. The physics parent (`C:/Users/Carina/workspaces/physics`) is outside this workspace and out of scope, as is `D:/carina/workspaces/cassicore` (read-only migration source; never run git operations there).

## Architecture & Data Flow

The closed integration loop (all pieces landed):

```
MnemicField engrams (CassiCore, SQLite/LMDB)
  → MindFieldEncoder → FieldShadowBridge   (vendored: CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/)
  → TCP 127.0.0.1:7599 deposit             (Godot mind engine: CassiCosmos/scripts/cassi_mind_engine.gd)
  → two-fluid PDE step on local RenderingDevice
  → readout / project k                    (top-k attractor cells by q = EY²+EI²)
  → back into CassiCore as salience/projection
```

The bridge is shadow/parity by construction: engine down = swallowed, brain bit-identical.

- **7599** — line-delimited JSON TCP: `ping`, `clear`, `deposit`, `step n`, `state`, `project k`, `readout` (base64 ey/ei/q/eps²), `snapshot`. Read = readout/project; write = deposit.
- **7273** — HTTP JSON loopback (`CassiCore/packages/mind-runtime/src/channel/server.ts`): `/v1/tools/execute`, `/v1/session/mirror`, `/v1/events/push`, `/v1/snapshot`, `/v1/health`, `/v1/memory/*`, `/v1/shutdown`.

Per-repo structure:

- **CassiCosmos**: `scripts/cassi_sim.gd` (main orchestrator, inline global-RD chain or decoupled engine) and `scripts/cassi_physics_engine.gd` (standalone RefCounted engine: mass deposit → spectral Poisson FFT → two-fluid PDE → BH sector → ∇(g·Φ) → Yin/Yang dual lattice → cached-acc KDK, on global or worker-thread local RD). Shader vocabulary in `CassiCosmos/compute/*.glsl` (`cassi_two_fluid.glsl`, `cassi_poisson.glsl`, `cassi_voronoi_cells.glsl`, `cassi_qi_time.glsl`, …). Entry scene `scenes/main.tscn`; **no autoloads**.
- **CassiCore**: everything under `packages/` (there is no root `src/`; ports live inside packages, e.g. `packages/tools/src/ports`). Composition root `packages/mind-runtime/src/boot.ts` (run via `packages/mind-runtime/src/run.ts`, bin `cassi-mind`). `packages/spine` is the only package that touches ohmypi.
- **CassiTheory**: document graph — `foundations/` wedge docs → domain papers → three master registries as source of truth (`open-questions-cassi-answers.md`, `parameter-inventory.md`, `predictions/falsifiable-predictions.md`).

## Key Directories

| Path | Purpose |
|---|---|
| `CassiCosmos/scripts/` | GDScript: sim orchestrator, physics engine, mind engine (7599), tree worker, UI (`sim_ui.gd` + `addons/cassi_ui`), verify arms |
| `CassiCosmos/compute/` | GLSL compute shaders (the physics vocabulary) |
| `CassiCosmos/scenes/` | Godot scenes: `main.tscn`, `verify_*.tscn` battery arms, `mind_engine*.tscn` sidecars |
| `CassiCosmos/verify/` | Battery runner `run_all.gd` + `README.md` (the contract) |
| `CassiCosmos/tools/` | Python bridge clients: `engine_cache_writer.py` (→ `CassiAI/datasets/physics_cache_engine.pt`), `field_steer.py`, `field_collector_git.py` |
| `CassiCosmos/research/` | Per-area R&D: `*_design.md`, `*_prereg.md`, `*_report.md`, `*_verify.py` (numpy gates), e.g. `research/meshless/`, `research/steering/` |
| `CassiCosmos/_diag/` | Gitignored run dumps (battery logs, verify JSONs consumed by numpy gates) |
| `CassiCore/packages/` | 22 retained `@cassicore/*` packages; `packages/mind-runtime/src/vendor/core/intelligence/` holds vendored retained intelligence modules (field-bridge, unified-loop, workspace, …) |
| `CassiCore/scripts/` | `verify-focus-gate.mjs` (zero-import acceptance gate) |
| `CassiTheory/` | Domain dirs (`foundations/`, `cosmology/`, `consciousness/`, …), `two-fluid/` (solvers), `computations/` (verify pipelines), `experiments/`, `field-experience/` (pre-registered probes + ledger) |
| `CassiAI/cassi/` | Archive: `qi_field.py`, `qi_fluid.py`, `fluid_cord.py`, `physics_field_model.py` |

## Development Commands

**CassiCosmos** (run from the repo dir, i.e. where `project.godot` lives). Godot console exe:

```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe"
```

```
# Full 30-arm verify battery (~8–9 min; runner may be headless, arms NEVER)
"<exe>" --path . --headless -s res://verify/run_all.gd

# Single arm (ALWAYS windowed)
"<exe>" --path . res://scenes/verify_<name>.tscn

# Stale shaders after edits ("No loader found for res://compute/..."): import once, re-run
"<exe>" --headless --import

# Python tools (numpy/torch, from repo root)
python tools/engine_cache_writer.py --runs 4 --frames 640
python tools/field_steer.py --per-step --strength 0.25 --rungs 4
```

**CassiCore** (npm; Node ≥20):

```
npm install        # allowScripts already permits better-sqlite3@11.10.0 postinstall
npm run build      # ordered tsc chain: foundation → mnemic-field → mini-helix → helix → constellation → flux-team
npm test           # vitest across all workspaces (2336 tests)
npm run test --workspace=@cassicore/<name>   # one package
npm run verify:focus   # zero-import gate — must stay green
```

**CassiTheory** (system Python, run from repo root; no build/lint/test tooling exists — do not introduce any):

```
python two-fluid/cassi_two_fluid_3d_gpu.py --mode cosmos --N 128
python computations/verify_planck_crossover.py    # prints gate numbers, ends "ALL CHECKS PASSED"
manim -pql visual-explainers/resonant_pond.py ResonantPond
```

Recording: `powershell -File record.ps1 -Out myvideo.avi -Duration 60` (see `CassiCosmos/RECORDING.md`).

## Code Conventions & Common Patterns

**Owner-live workspace.** Parallel sessions (human + agents) edit the same trees concurrently. Never edit `UNIFICATION.md` unless asked (owner carries uncommitted edits there). Commit path-limited (`git commit -- <paths>`); when a file mixes your edits with a live collaborator's, stage only your hunks. One session pushes. If a file looks mid-write, report uncertainty instead of guessing.

**Measured-verdict discipline (workspace-wide).** Pre-register before any run: statistic, decision tree, stopping rule — frozen in a `*_prereg.md` before the probe script runs. Gates are G-numbered (`verify_mind_engine` Gate A–C, G52–G60…). Verdict vocabulary is frozen: `PASS/FAIL/NULL/ADOPT/REJECT` for stage gates; `SUPPORTS/CONTRADICTS/EMERGES/DOES NOT EMERGE/INCONCLUSIVE` for probes; honest negatives are deliverables. Never re-run a rejected hypothesis at full cost.

**Default-off additive toggles.** New engine features ship disabled and must leave the default battery bit-identical (`cassi_qi_time.glsl` OFF = bit-identical copy is the model). The no-op contracts that actually exist today: the attractor-ratio dormant-deposit gate (`verify_mind_engine`) and toggle-off bit-identity (G57 etc.). `verify_river_isotropy.gd` pins the default CUBE grid-river chain bit-identical with fixed numeric anchors — treat its anchors as load-bearing.

**Godot/GDScript patterns.** Cleanup on the physics engine is `shutdown()`, never `free()` (4.7 RefCounted shadowing). Local RenderingDevices must be created **on** the worker thread that uses them; `RDShaderFile` loading is not thread-safe — pre-extract SPIR-V (`cfg.spirv`) before handing off. Never commit `.godot/`, `*.uid`, `*.spv`, or the `.glsl.import` churn Godot rewrites every run. One Godot instance at a time (`tasklist | findstr /i Godot`; never kill the Mono editor). Stale cache recovery: delete `.godot/shader_cache`, re-`--import`.

**CassiCore patterns.** ESM + strict TS (`tsconfig.base.json`, nodenext). Cross-imports only via `@cassicore/*` workspace deps. The DELEGATE-SURFACE seam is law: retained packages must not import the 17 deleted packages or bare `core/intelligence|core/daemon` paths — vendored `./vendor/` copies are the exemption (`packages/tools/DELEGATE-SURFACE.md`, `packages/model-pool/DELEGATE-SURFACE.md`, enforced by `verify:focus`). Coding tools (shell/file I/O/web/tests/jobs) are ohmypi-owned; only the mind-tool surface is retained. `bin/cassicore` is a stale pre-migration launcher — ignore it.

**CassiTheory conventions** are codified in `CassiTheory/AGENTS.md` and win over this file: present-state-only prose (no "previously/was withdrawn"; git history is the changelog), `## Status: <tier>—<date>` headers, backtick root-relative cross-refs, registry sync in the same commit, commit + `git push origin master` at the end of every task, no AI-isms (no "honest", no X-not-Y framing, closed em-dashes, no throat-clearing).

**CassiAI**: read-only archive. Consult lessons; never import, modify, or "fix" its code or its AGENTS.md.

## Important Files

| File | Why |
|---|---|
| `UNIFICATION.md` | The program: present-state map, seams, phases, risk ledger (owner-live) |
| `CassiCosmos/scripts/cassi_sim.gd` | Main sim orchestrator (inline chain + decoupled mirror) |
| `CassiCosmos/scripts/cassi_physics_engine.gd` | Standalone GPU engine; `shutdown()` lifecycle; threaded local RD |
| `CassiCosmos/scripts/cassi_mind_engine.gd` | The 7599 field I/O primitive |
| `CassiCosmos/verify/README.md` | Battery contract — read before touching anything GPU-side |
| `CassiCosmos/MESHLESS_PLAN.md`, `MACHINE_PLAN.md` | Status/road-map docs; house style for staged plans with hard gates |
| `CassiCosmos/cassi_contract.py` | Buffer/push-constant layout doc (historical; live shader headers are authoritative) |
| `CassiCore/package.json` | Workspace scripts; build order; allowScripts |
| `CassiCore/MIGRATION-STATUS.md` | Current-state authority (22 packages, 2336 tests, focus gate) — supersedes the P1–P7 planning tables, which stay untracked |
| `CassiCore/packages/mind-runtime/src/channel/server.ts` | 7273 HTTP channel |
| `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/` | The 7599↔7273 bridge |
| `CassiTheory/AGENTS.md` | Theory-repo constitution |
| `CassiTheory/reading-guide.md` | TOC + reading paths into the theory repo |

## Runtime/Tooling Preferences

- **Godot 4.7.1 Mono** console exe (WinGet path above). Scene arms **always windowed** — this rig's global RenderingDevice has no headless device; only the battery runner may be `--headless`. GPU: RX 7900 XTX.
- **Node ≥20 + npm** for CassiCore (no packageManager field; lockfileVersion 3). No lint tooling exists; `typecheck` = `tsc --noEmit` per package.
- **System Python 3.12** everywhere; torch is the ROCm build (device reports `cuda`). No `requirements.txt`/`pyproject.toml` anywhere — environments are pre-installed; keep scripts dependency-light.
- **AMD/ROCm env** (archive-era, still the machine convention): `CUDA_VISIBLE_DEVICES=1` (GPU 0 is the iGPU — never used), `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, `HSA_ENABLE_SDMA=0`.
- Windows paths with forward slashes in commands; bash available for Python/npm orchestration.
- Shader SPIR-V: Godot imports `.glsl` itself (via `--import`). The `glslangValidator` loop (`CassiAI/build_shaders.sh`) is an archive pattern, not used by CassiCosmos.

## Testing & QA

**CassiCosmos — the 30-arm battery is the contract.** `verify/run_all.gd` runs 30 scenes serially (they share the GPU); each arm exits 0/1; battery exit 0 only on 30/30. Per-arm timeout 240 s (`ARM_TIMEOUT_SEC`), hung arms killed with `taskkill /T /F` (the console exe wraps a child process — the tree must die). Logs: `res://_diag/battery_logs/armNN_<name>.log`. `verify_particle_vanish` is a diagnostic, not a gate (always exits 0; findings are in its printed timeline). Numpy gates (`research/meshless/stage5_verify.py` etc.) consume `_diag` dumps and are run separately — the arm's exit code is the battery contract. Expected runtime ≈8–9 min when green; a run with timeout arms takes much longer. After any engine/shader change, green battery before claiming a gain.

**CassiCore — vitest per package.** 2336 tests green, 0 typecheck errors across the 22 retained packages. Host-wired suites live in `packages/*/tests/host-wired/` and are **permanently quarantined** (excluded via per-package vitest configs; they wired against deleted `core/daemon.js`) — do not "fix" them into the default run. `npm run verify:focus` after any dependency-surface change.

**CassiTheory — QA is documentary.** No test suite, by policy. A claim is verified by a script run from repo root that prints its numbers (`computations/verify_*.py` → `ALL CHECKS PASSED`); consistency is the 7-grep checklist inside `CassiTheory/AGENTS.md`; the three registries win any conflict. Probes record verbatim verdicts in `field-experience/probe-outcome-ledger.md`.

**CassiAI — archive.** No suite; do not add one.
