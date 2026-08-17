# Boxless site hash — pre-registration — Arm: spatial-hash nearest-coherent-site

Date: 2026-08-17
Predecessor: `research/meshless/coherence_adaptive_prereg.md` (arms 1/2/3, SUPPORTS,
committed) — this is the deferred follow-on ("a truly boxless picture needs the
spatial-hash-of-sites optimization — recorded, not shipped", boxless_field_report.md §3).
Status: **frozen before any GPU probe** (measured-verdict discipline, no post-hoc tuning).

## 1. Problem

The boxless instancer's nearest-coherent-site lookup (`nearest_shortlist_site`,
`compute/cassi_instancer.glsl` ~373) is a **linear O(shortlist) scan per particle**.
Arm 1 shrank the scan from the full 8192-site mesh to the coherent subset (~271 in a
sparse field, 33× smaller), so the *constant* is small — but it is still a linear scan:
per-frame cost = N_particles × O(shortlist). The boxless report's deferred work was the
spatial hash that makes the lookup **O(1)-ish** (a bounded-cell neighborhood scan), so
the per-frame boxless render tracks coherent *content* (bucket occupancy), not the
shortlist *count*, and stays cheap as sites scale toward galaxy density.

## 2. What ships (default-OFF additive, bit-identical battery)

A new shader `compute/cassi_site_hash.glsl`, run on the steer cadence immediately
after the Arm-1 shortlist build (inside the same `_mesh_rebuild()` list). It buckets
the shortlisted coherent sites into a fixed-resolution uniform grid over the sim
window extents:

- **Cell index** = floor((site − window/box min) / cell_side), with `cell_side =
  (box extents) / H`, `H` a fixed power-of-two cell count per axis (default 32 →
  32768 cells at base extents). Compacted so per cell we store a contiguous run of
  shortlist slots.
- **Buffers (set 0):**
  - `0 cell_start  uint[n_cells+1]` — prefix sum (cell_start[c], cell_start[c+1]) =
    the run [lo, hi) of shortlist slots in cell c (atomic count + prefix, same
    pattern as the tree's range compaction).
  - `1 cell_sites  uint[shortlist_count]` — the shortlist slots compacted by cell.
  - `2 cell_count  uint[n_cells]` (coherent atomic compaction cursor, optional for
    host readback; the prefix buffer is authoritative).
  - Reuses the shortlist `vec4[] pos.xyz+w` and the site psi buffers (already bound
    in the boxless instancer set).
- **PC:** `n_cells_per_axis` (H), `cell_side`, `n_shortlist`, `mode` (0 = reset,
  1 = bucket+compact — in-list reset+bucket, same as the shortlist/tree passes).

`compute/cassi_instancer.glsl` gains a **guarded boxless branch**: when
`boxless_active()`, `nearest_shortlist_site` becomes a **growing-ring spatial-hash
query** — scan the query cell + its 26 neighbors (Chebyshev radius 1); if empty,
expand to radius 2 (125 cells) and so on up to a frozen **MAX_QUERY_R (5)**; the
first non-empty ring bounds the answer, and the global min over ALL found shortlist
slots in rings ≤ that radius is the exact nearest (strictly: any closer site would
live in an earlier ring, which was already scanned empty). **A growing full-ring scan
is exact by construction — it is equivalent to the brute-force global nearest** — the
probe confirms equivalence rather than tuning it. Default (`flag.y ≤ 0.5`) → the grid
trilinear paths unchanged, bit-identical.

Wiring: `scripts/contracts/layout.gd` (new `cassi_site_hash` block + instancer
bindings for the hash set), `scripts/cassi_physics_engine.gd` + `scripts/cassi_sim.gd`
(allocate the hash buffers + set, dispatch after the shortlist in `_mesh_rebuild()`,
bind them into the boxless instancer set variant only), free-list entries.

## 3. Statistic / metric / decision tree (frozen, no post-hoc tuning)

**Bit-identity (MUST pass; default OFF):**
- `assert_layout` — **0 mismatches** (new shader block + instancer bindings covered).
- `verify_voronoi3d` 9/9, `verify_voronoi3d_moving` 10/10, `verify_meshless_reconstruct`
  7/7, `verify_meshless_gravity` + `stage5b_verify.py`, `verify_fmm` — ALL green with the
  new toggles OFF (the hash dispatch is always on at the steer cadence, but with default
  `boxless` the instancer never reads it → the picture is bit-identical; the hash build
  itself is a read-only gather of the shortlist, no field/force change).
- GDScript parse-gate (engine + sim + layout load, exit 0); glslangValidator both
  shaders clean.

**ON-correctness (MUST pass):**
- **Hash == brute-force nearest (exact):** in the ON probe, for EVERY particle the
  hash-query nearest shortlisted site index equals the brute-force global scan's —
  **0 mismatches** on ≥ 1000 particles over a planted coherent blob + sparse void
  (the growing-ring query is exact by construction; this gate confirms the build).
- **Cost win:** measured hash-query cell-ring iterations are **≤ 3 for ≥ 99% of
  particles in a dense blob** (i.e. the lookup exits in ≤ the 27-cell first ring for
  virtually all — the O(1) claim) — reported; vs the linear-scan baseline length
  (the shortlist size) for the same particles.
- **No NaN / no miss:** `boxless_active` query never returns not-found for a particle
  whose brute-force scan finds a site (growing-ring reaches MAX_QUERY_R before
  concluding empty; parity gate).

**Decision tree:**
1. Bit-identity fails → **REJECT** (revert; keep pre-reg/design).
2. Bit-identity passes, ON-correctness fails → **FAIL-review** (fix or drop; a
   hash-vs-brute mismatch means the bucketing/ring is wrong — fix the builder, not a
   tuning dial).
3. Both pass → **SUPPORTS** for the boxless spatial-hash arm.

## 4. Pre-registered run plan

1. GPU probes windowed (this rig's local RD needs a window): the ON probe plants a
   coherent blob + void, builds the shortlist then the hash on a local RD, and runs
   the boxless instancer path reading hash-vs-brute nearest + the ring-iteration
   histogram.
2. Battery arms windowed per contract; `assert_layout` after wiring.
3. Revert all GPU churn (`--import`/windowed rewrites) before commit; path-limited
   commit; working tree clean of the owner's live files.

## 5. Honest scope / non-goals

- This arm is the **instancer display read only** — the field-carrier physics
  (condensation, river gradient, merge, field evolution) still reads the periodic
  raster grid; migrating those is a separately pre-registered arm, not claimed here.
- Not a general nearest-neighbor library; purpose-built for the coherent-site boxless
  read at the sim's scale.
- The hash is rebuilt on the steer cadence (like the shortlist), not per frame — a
  one-cadence-stale read is inherent and matches the shortlist's own staleness.
