# Boxless site hash — report — Arm 4: spatial-hash nearest-coherent-site

Date: 2026-08-17
Pre-reg: `research/meshless/boxless_site_hash_prereg.md` (frozen, §3 decision tree)
Verdict: **SUPPORTS** — the boxless instancer's nearest-coherent-site lookup is now a
bounded growing-ring spatial-hash query (exact by construction), default-off
bit-identical, instead of a linear O(shortlist) scan.

## 1. What shipped (default-OFF additive, bit-identical battery)

A new shader `compute/cassi_site_hash.glsl` buckets the Arm-1 coherence-filtered
shortlist into a fixed-resolution uniform grid (HASH_H=32 cells/axis, 32768 cells at
base extents) over the sim box. Mode-staged exactly like the tree/shortlist in-list
passes: reset → histogram → exclusive prefix → scatter (each cell's shortlist slots
land in a contiguous run `[cell_start[c], cell_start[c+1])`). The shader reads the
**live shortlist count** via binding 4 (after the shortlist's barrier), so it never
buckets stale slots and needs no host readback / extra sync — works on both the local
and global RD paths.

`compute/cassi_instancer.glsl`'s boxless branch (`nearest_shortlist_site`) becomes a
**growing-Chebyshev-ring query** over the hash: scan all cells in rings ≤ r, break on
the distance bound `bd < (r·cs)²` (an unscanned cell at Chebyshev ≥ r+1 has its nearest
point ≥ r·cs). This is **exact at any distance** — a closer site would live in an
earlier, already-scanned ring — and terminates at worst scanning the whole grid (r ≤ H
hard cap = brute-force equivalence, guarding degenerate inputs from hanging the GPU).
Cost: 27 cells (r=1) in the dense-blob case, growing only in sparse voids where there
are few sites.

Wiring: `scripts/contracts/layout.gd` (cassi_site_hash PC 6 / bindings 0-4 covered,
instancer 0-13), `scripts/cassi_physics_engine.gd` + `scripts/cassi_sim.gd` (hash
buffers + shader/pipe + set + in-list dispatch after the shortlist in `_mesh_rebuild`,
free-list entries), and all 12 instancer uniform-set variants bind the hash buffers
(11 cell_start, 12 cell_sites, 13 cfg) — read only inside `boxless_active()`.

## 2. Verification (pre-reg §3) — all green

**Bit-identity (MUST pass):**
- Parse gate: engine + sim + layout + probes — PASS.
- glslangValidator: `cassi_site_hash`, `cassi_instancer`, probe kernel — clean.
- `assert_layout`: **PASS, 0 mismatches** (hash PC/bindings + instancer 0-13 covered).
- Battery (default OFF, hash never read by the picture): `verify_voronoi3d_moving`
  **10/10** (exact `max|r−r0|=0.2478` pin), `verify_meshless_reconstruct` **7/7**,
  `verify_meshless_gravity` **PASS** + `stage5b_verify.py` **G16 3.831e-07** (GPU vs
  prototype tree, exact). G17/G18 are the documented pre-existing intentional FAILs
  (`theta_sweep_report.md`), unchanged. Working tree churn reverted.

**ON-correctness (all MUST pass), probe `_diag/arm4_probe.gd` (local RD):**

```
shortlist count = 952 (of 8192)
P1 hash==bruteforce: mismatches=0 over 2048 queries  PASS   (exact)
P2 ring<=3 (dense-blob): 1843/1843 = 1.0000         PASS   (all-queries 0.9697)
P3 no-miss: misplaced=0                              PASS
RESULT: PASS (failures=0)
```

- **P1 exactness**: the hash-query nearest matches a host brute-force scan on
  2048/2048 particles (coherent blob + void) — equals the linear scan, every time.
- **P2 cost win**: in the dense coherent blob every query exits in ≤ 3 rings (100%),
  i.e. the O(1)-ish lookup; the whole picture's per-frame boxless scan now tracks
  coherent bucket occupancy, not the shortlist count.
- **P3 no-miss**: no query returns not-found when a nearest exists.

## 3. Decision-tree application (frozen §3)

1. Bit-identity passes → **SUPPORTS**.
2. ON-correctness (hash == brute force, 0 mismatches; blob ring ≤ 3; no-miss) passes →
   **SUPPORTS**.
3. → **SUPPORTS** for the boxless spatial-hash arm; recorded here.

## 4. Honest scope / follow-ons

- This arm is the instancer **display read** only; the field-carrier physics
  (condensation, river gradient, merge, field evolution) still reads the raster grid —
  migrating those is a separately pre-registered arm, not claimed here.
- The hash rebuilds on the steer cadence (like the shortlist), one cadence stale — the
  whole boxless render is already bounded by that cadence.
- The ring exit is distance-bound exact; the `r ≤ H` cap is a degenerate-input guard,
  not a truncation (at r = H it scans the full grid = brute force).
- P2's all-queries ring fraction (0.9697) is dragged by far-void queries that correctly
  grow to larger rings — the pre-reg gate is defined over the dense blob (100%).
