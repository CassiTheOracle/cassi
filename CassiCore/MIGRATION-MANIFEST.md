# MIGRATION-MANIFEST — Exclusion Baseline (committed Debt Baseline)

**Root:** workspace (CassiCore)
**Source of truth:** `recon-data.json` (`deadFiles` + `uncertainFiles` arrays), derived by `recon-analysis2.cjs`.
**Committed in P0** so every later phase reuses a closed, reviewer-verified exclusion set.

---

## Purpose

These files **never migrate** from `D:\carina\workspaces\cassicore` into the workspace
`@cassicore/*` packages. The exclusion baseline is authoritative for all P1–P8 phases:
each phase diffs its `--path` import set against this manifest before touching git.

- **DEAD** files (classified unreachable by import BFS + the three mechanism-aware overrides) → never migrate, never delete from D: until the phase-gated debt scrub (CASSI-MIND-PLAN.md §5).
- **UNCERTAIN** files (carry `@dep callers:` / name-string references; only import-reachable by a live file at runtime) → quarantine; do NOT import until a worker resolves intent from the referencing live file.

---

## Totals (as of scan date 2026-08-13, from `recon-data.json`)

| Category | Files | Total size |
|---|---|---|
| **deadFiles** | **249** | ~1901.0 KB |
| **uncertainFiles** | **84** | ~447.4 KB |

---

## Dead (`deadFiles`) per subsystem — 249 files, ~1901 KB

| Count | Subsystem |
|---|---|
| 62 | `webui/src` |
| 49 | `core/intelligence` |
| 17 | `webui/observatory` |
| 14 | `scripts` |
| 10 | `core/tools` |
| 10 | `scripts/fluid-field` |
| 7 | `core/utils` |
| 7 | `integrations/claude-code` |
| 6 | `core/lsp` |
| 6 | `types` |
| 6 | `integrations/hermes-agent` |
| 6 | `webui` |
| 5 | `core/ingestion` |
| 5 | `core/providers` |
| 4 | `core/daemon` |
| 4 | `tests/core` |
| 4 | `tests` |
| 3 | `core/adapters` |
| 3 | `core/admin-api` |
| 3 | `core` |
| 3 | `core/deploy` |
| 3 | `scripts/restructure` |
| 3 | `tests/self-monitoring` |
| 2 | `tests/fixtures` |
| 2 | `tests/helpers` |
| 1 | `core/model-pool` |
| 1 | `core/unified` |
| 1 | `integrations/opencode` |
| 1 | `prism/src` |
| 1 | `prism` |

## Uncertain (`uncertainFiles`) per subsystem — 84 files, ~447 KB

| Count | Subsystem |
|---|---|
| 29 | `webui/src` |
| 14 | `core/intelligence` |
| 6 | `core/tools` |
| 4 | `core/daemon` |
| 4 | `core/providers` |
| 4 | `integrations/claude-code` |
| 3 | `integrations/hermes-agent` |
| 2 | `core/ingestion` |
| 2 | `core/utils` |
| 2 | `tests/core` |
| 1 | `core/admin-api` |
| 1 | `core/bridge` |
| 1 | `core` |
| 1 | `core/mcp` |
| 1 | `core/observability` |
| 1 | `core/testing` |
| 1 | `core/unified` |
| 1 | `cassi-tui/src` |
| 1 | `webui/observatory` |
| 1 | `ai/src` |
| 1 | `scripts/restructure` |
| 1 | `tests/api-spec` |
| 1 | `tests/fixtures` |
| 1 | `tests/helpers` |

---

## The Rule

> **DEAD files never cross.** UNCERTAIN files never cross until a worker resolves their intent.
>
> - A file is DEAD iff it is in the `deadFiles` manifest (import-BFS-unreachable under any override).
> - A file is UNCERTAIN iff it is in the `uncertainFiles` manifest — it carries a name-string
>   reference and needs intent resolution before migration. Default: quarantine (do not import).
> - Each phase MUST diff its `--path` set against this manifest and report the intersection as
>   "excluded (baseline)" — never silently import an excluded file.

Full per-file `rel` paths live in `recon-data.json`. This manifest is the committed baseline;
regenerate via `node recon-analysis2.cjs` only when recon is intentionally re-run (not this phase).

---

## History-import infrastructure (per-phase git-temp pattern)

All history-import temps live on the **D: drive** for hardlinked fast clones; nothing is ever written
inside the live `D:\carina\workspaces\cassicore` repo itself.

- **Persistent mirror (kept permanently; refreshed per phase):**
  `D:\carina\.cassi-mirror` — `git clone --no-checkout "D:/carina/workspaces/cassicore"` (history only).
  Refresh command: `git -C "D:/carina/.cassi-mirror" fetch origin main:main` (default branch is `main`).
- **Phase temp (deleted at end of each phase; hardlinks → near-instant):**
  `D:\carina\.cassi-tmp-p<phase>` — `git clone --no-checkout "D:/carina/.cassi-mirror"`.
- **filter-repo:** `C:\Users\Carina\AppData\Local\Programs\Python\Python312\Scripts\git-filter-repo.exe`
  (verify with `--version`; add `echo n |` + `--force` when filtering the temp clone).
- **Import sequence:** filter-repo `--path`/`--path-rename` in the phase temp → `git fetch <temp> main:import/<pkg>`
  → `git merge --allow-unrelated-histories --no-commit import/<pkg>` → resolve add/add by `--theirs`
  (history-bearing side) → `git branch -D import/<pkg>` → delete phase temp (KEEP the mirror).
