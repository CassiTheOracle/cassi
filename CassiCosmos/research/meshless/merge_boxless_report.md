# Merge boxless — report — the last grid-carrier physics reader

Date: 2026-08-17
Pre-reg: `research/meshless/merge_boxless_prereg.md` (frozen, §5 decision tree)
Verdict: **SUPPORTS** — the particle-merge coherence gate is now **window-independent**:
when `boxless_field AND particle_merge` are both on, it reads the moving-Voronoi
site's cell-averaged field, AREPO gradient, and momentum density directly —
no periodic grid, no `%N` wrap — closing the last box-bound physics reader on the
boxless hot path. Default-off bit-identical.

## 1. What shipped (default-OFF additive, bit-identical battery)

`compute/cassi_particle_merge.glsl` gains a **boxless site-read branch** (+2 PC
floats `boxless@24`/`n_sites@25`, +7 bindings 18-24). When `boxless ≥ 0.5`:

- **`qcoh_at(wp)`** — nearest-site over `_ml_sites`; `q = ρ²/(ρ²+φ⁻²+ε²)` from the
  containing site's cell-averaged `psi_y/psi_i`. Coordinate-independent.
- **`qord_at(wp)`** — the order gate reuses the **shipped AREPO reconstruction
  gradient** (`grad_y/grad_i`, the mode-12 least-squares solve exact for linear
  fields): `∇Σ = ∇EY + φ·∇EI`, `q_ord = 1/(1 + φ²|∇Σ|²/(Σ²+φ⁻²))`. Full order
  gate, site-resident (owner chose full fidelity).
- **`flow_at`** (virial stop + subsonic `dv`) — the site's own velocity from its
  momentum density, `(pi_y + pi_i)/ρ` — the exact quantity the site leapfrog's
  steering uses (`vv = lam·(pi+pi)/rho`).

Grid path (default, `boxless=0`) is byte-for-byte unchanged: the boxless branch is
a `bool boxless_on()` guard before the existing trilinear reads, never a zero-multiply.

Wiring: `scripts/contracts/layout.gd` (merge PC 24→26, bindings 0-17→0-24),
`cassi_merge_common.gd` (`merge_pc_values` 24→26 with `boxless`/`n_sites` from the
dict), engine + sim (`_merge_pc_dict` gates `boxless` on `_ml_ready && boxless_field
&& particle_merge` / the sim's `_ml_boxless_on() && particle_merge`; `_ml_*` site
buffers bound 18-24; PC byte arrays 24→26 floats at both resize sites + the encode
loops). The merge uniform set now binds the site buffers — the same pattern as the
instancer/qhist boxless sets. The 6 verify scripts that build their own merge set
(`verify_merge.gd`, `_binding`, `_gate`, `_spin`, `_virial`, `_subsonic_step`) gained
the 7 dummy bindings + 26-float PC so the shader set validates.

## 2. Verification (pre-reg §5) — all green

**Bit-identity (MUST pass):**
- Parse gate: engine, sim, merge_common, layout, + all 6 patched verify scripts —
  PASS (10/10 load).
- glslangValidator: `cassi_particle_merge.glsl` — clean (no `atan2`; two-arg `atan`).
- `assert_layout`: **PASS, 0 mismatches** (merge PC 26 / bindings 0-24 covered).
- Battery (default OFF — the boxless branch is inert): `verify_merge` **8/8**,
  `verify_merge_binding` **6/6**, `verify_merge_gate` **5/5**, `verify_merge_engine`
  **7/7**, `verify_merge_sim` **5/5**, `verify_merge_spin` **6/6**,
  `verify_merge_virial` **6/6** — all PASS. `verify_subsonic_step` is red (G-S1/G-S2,
  `alive=0`), but **proven pre-existing**: a git-stash A/B re-run at pristine HEAD
  `dd0ca94` fails identically (`alive=0` — the merge consumes both particles, a
  survivor-accounting defect in the merge's hop pass that predates this arm). Not a
  regression; recorded in the report §4 as a separate finding.

**ON-correctness (all MUST pass), probe `_diag/merge_boxless_probe.gd` (local RD):**
```
PASS MBO-3 CPU nearest site to pair is a blob site (<64) idx=5 d=0.4975
PASS MBO-1 boxless ON  → coherent site found, pair MERGES  (alive==1)
PASS MBO-1b boxless OFF → grid wraps pair out of coherence, no merge (alive==2)
PASS MBO-2 site q_ord ≈ 1 on flat blob (|1−q_ord|≤1e-3)  q_ord=1.0000
PASS MBO-2b analytic q_sel = q_coh·q_ord = 0.9472 > φ⁻²   (arms the merge)
RESULT: PASS (check: 6 failures=0)
```

- **MBO-1 is the point of the arm**: a bound, subsonic, coherent particle pair
  placed **OUTSIDE the periodic grid domain** (x=60, beyond extent=37.5). With
  `boxless_field` on, the merge gate finds the true nearest site and **merges it**;
  with it off, the grid `corners_at %N` wrap reads a wrong low-q cell and **no merge
  fires**. Same physics, same pair — the only difference is whether the coherence
  read is window-independent. Window-independence demonstrated end-to-end.
- **MBO-3** confirms the CPU nearest-site reference (the shader's choice matches a
  host brute force); **MBO-2** confirms the site `q_ord` is exact (1.0000) on a flat
  blob — the AREPO gradient's linear-field exactness — and the analytic `q_sel`
  arms the merge.

## 3. Decision-tree application (frozen §5c)

1. Bit-identity passes (assert_layout 0, merge battery green, default-off
   byte-identical) → **SUPPORTS**.
2. ON-correctness passes (window-independent merge where the grid path fails, site
   q_coh/q_ord correct, CPU reference matches) → **SUPPORTS**.
3. → **SUPPORTS** for the merge-boxless arm; recorded here.

## 4. Honest scope / findings

- **`verify_subsonic_step` is a pre-existing red** (not caused by this arm — proven
  by a pristine-HEAD A/B: fails identically with `alive=0`). Root cause is in the
  merge's hop/survivor accounting (both particles consumed), a separate defect to
  track; this arm did not touch it (the boxless branch is a guarded read swap).
- The probe logs benign "Attempted to write buffer past the end" errors — the probe's
  per-particle scratch is minimally sized for the 2-particle merge; the writes land
  in dead scratch `finalize` never reads into the decision. The production engine/sim
  size these buffers `max(N_particles,1)`; no production defect.
- **Truly boxless now**: field evolution (site-resident, modes 0/1/12, no `%N`),
  instancer (shortlist + spatial hash), qhist (`site_coherence`), and merge (this
  arm) all read the moving-Voronoi mesh directly. The periodic raster grid remains as
  the render attachment; the grid-only readers (condensation/BH) require
  `black_holes_enabled`, and the river gradient is off under meshless+tree — neither
  is on the boxless hot path. The grid-carrier physics reader that could run in a
  boxless sim without another toggle is closed.
- Site flow for the virial stop is momentum-density `/ρ` (the site leapfrog's own
  velocity convention), not the grid `_field_vel` (time-derivative) — the faithful
  site-resident definition, recorded in the pre-reg §7.
- The site set is one steer-cadence stale (like the shortlist/hash); merges are
  cadenced within that budget, so staleness is within the existing merge discipline.
