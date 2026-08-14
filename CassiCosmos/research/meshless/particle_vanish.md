# Particle Vanish — Reproduction, Timeline, Cause, Fix Design
**Status:** Diagnosed (reproduced + controlled), SIM FIX DEFERRED to a later turn
**Date:** 2026-08-13 · rig: RX 7900 XTX, Godot 4.7.1 mono console (windowed), `_diag/godot_runtime`
**Driver:** `scenes/verify_particle_vanish.tscn` + `scripts/verify_particle_vanish.gd`
**Test harness log:** `_diag/vanish.log` (tree mode), `_diag/vanish_river.log` (river control)

## TL;DR
The "ALL particles vanish" bug **reproduces deterministically** on the meshless tree
gravity arm (meshless_mode + meshless_gravity ON, gravity_mode→5). It is **not** a NaN
injection into the field/sites/deposit/mass, and **not** BH accretion, and **not** `pos.w`
corruption, and **not** a stale/garbage local-RD readback. It is a **catastrophic,
unbounded **force blow-up in the Barnes–Hut walk's near-field** (unsoftened quadrupole +
river-calibrated `G_N` applied to the tree's direct-sum force) that ejects the galaxy's
particles one by one; once (i) enough particles reach huge radii and (ii) the dt·a
overflows float32, the positions go NaN and the whole population "vanishes" (NaN
positions → NaN deposit → NaN field → NaN sites, all at once). The **first-bad quantity
in the timeline is `tgrad` (the tree per-particle force) growing without bound**, closely
followed by particle positions leaving the box. Everything else stays clean through the
entire ejection phase.

## Reproduction
Config (mirrors the user: meshless + tree on, `dt=0.05`, BH enabled, field attractor):
`grid_N=64, N_particles=4000, dt=0.05, meshless_mode=true, meshless_gravity=true,
gravity_mode=5, black_holes_enabled=true, field_attractor_init=true, suppress_readbacks=true`.

## 1. Reproduces on BOTH drive paths.
The two paths differ only in *who* calls `_run_physics_steps`:
- **Direct** (`playing=false`, scene calls `_sim._run_physics_steps(1)` per frame): **yes — classic vanish.**
- **`_process` catch-up** (`playing=true`, the sim's own `_process` accumulator drives):
  **yes — same physics, same vanish.** Both funnel into `_run_physics_steps`, and both
  went all-NaN. (Path B in the tree run *inherited* path A's already-NaN state; the root
  cause is path-independent.)

## 2. Decisive control — the river arm NEVER vanishes.
Same scene/config with `meshless_gravity=false, gravity_mode=0` (`-- --river`):
- `acc_max` peaks ~2870 during the collapse, then **settles to ~7–10**; galaxy core stays
  bound; 2579/4000 retained at frame 1200 (a few halo escapers to r≈12k, no vanish).
- **No NaN anywhere**, field/sites/deposit/mass clean, on both paths.
- The tree arm at the SAME config: `acc_max` explodes to **56 450**, `tgrad_max` to
  **237 116**, and 3987/4000 ejected by frame 300.
→ The tree walk is the ejector. Field/site/deposit/BH/river are exonerated.

## Timeline (tree mode, path A — see `_diag/vanish.log`)
```
fr=020 alive=4000 |pos|[50.97..65.84] nan=0 | acc_max=189 tgrad_max=799 nnode=1031 | all clean
fr=080 alive=4000 |pos|[34.95..101.89] nan=0 | acc_max=91  tgrad_max=391             | collapse
fr=140 alive=4000 |pos|[32.26..247.73] nan=0 | acc_max=118 tgrad_max=480  nnode=1076  | core:~248
fr=160 alive=3999 |pos|[41.73..6284.72] nan=0 | acc_max=105 tgrad_max=447             | <-- FIRST
fr=180 alive=3996 |pos|[55.91..40741.62] nan=0| acc_max=744 tgrad_max=3012            |   ESCAPER
fr=200 alive=3989 |pos|[73.16..156402.39] nan=0| acc_max=56450 tgrad_max=237116       | runaway
fr=220 alive=1671 |pos|[89.07..92105308.11] nan=0| acc_max=7537 tgrad_max=32048       | mass eject
fr=300 alive=143  |pos|[149.59..618420405] nan=0 | ...                                | cascade
fr=440 alive=13   |pos|[220.46..1539472150] nan=0| ...                                | all blown out
fr>=600 all NaN (pos/acc/tgrad 12 000, field ey/ei 262144, psiY/I 8192, sites 24576)   # overflow
```

### What breaks FIRST
1. **fr≈160–200 — `tgrad` (tree force) blows up** (max 799 → 237 116 ≈ 300×, unbounded).
2. Then particle positions leave the box (**fr=160 first escaper**, 6284 → 41k → 156k → 9e7 → …).
3. `acc_max` follows `tgrad_max` (mode-5 acc = `G_N·(π/ρ)·tgrad`).
4. Field ey/ei, meshless sites psiY/psiI, `_mass_density_buf`, `pos.w` (Salpeter mass
   0.300–27.628), and all NaN counts are **0 through the entire ejection phase** — they are
   NEVER the first-bad signal. The all-NaN at fr≥600 is the **downstream float overflow**
   of already-ejected huge positions (`/dt·a` overflows float32 → NaN → NaN deposit →
   NaN field → NaN sites), i.e. the *visible* "vanish".

### Eliminated suspects (with evidence)
- **#3 mass corruption**: the KDK preserves `pos[i].w` exactly
  (`nbody_gravity.glsl:839 pos[i]=vec4(p_new,pos[i].w)`); `particle_merge.glsl` (the only
  other `pos[i].w` writer) is **never dispatched** by the sim; IC writes Salpeter mass in
  [0.3,30]; the timeline shows `pw=[0.300..27.628]` constant and NaN-free. **Eliminated.**
- **#4 BH deletes particles**: `cassi_bh_integrate.glsl` touches only the 15 BH slots in
  the 36-vec4 header (grows mass, ages, expires slots) — it never writes `_pos_buf`.
  BH count stayed 0/3000 here (no condensation nucleated at Np=4000), and the river
  control with BH enabled+gravity_mode=0 was stable. **Eliminated.**
- **#2 π/ρ blow-up in mode 5**: `tree_river_field_acc` calls the SAME `chord_g_from` as
  mode 0 (`rho_f<1e-6` guard + clamp [0,0.72]) — identical clamp logic. **Eliminated.**
- **#5 local-RD readback staleness/zeros**: the walk reads `_tl_tpos` = a coherent
  end-of-previous-frame `_pos_buf` snapshot (global-RD `buffer_get_data` self-stalls, then
  uploads to global `_ml_tree_grad` before `compute_list_begin`). `nnode` healthy
  (975–2349); if the walk got zero/garbage targets the force would be zero, not 237k.
  Not the cause; the tree produces the *right-shaped* but *unphysically-large* force.
- **Field/sites/deposit source NaNs**: all clean through fr=440. **Eliminated.**

## Root cause (two compounding defects in the tree arm)
### (a) Unbounded near-field force in the walk — `compute/cassi_tree_gravity.glsl`
The walk's accepted-node force is
```
monopole  invR3 = 1/(R2·sqrt(R2)), R2 = ds2 + eps2        (softened, eps2 = 1e-6)
quadrupole invR7 = 1/(R2q³·sqrt(R2q)), R2q = max(ds2, 1e-30)   (UNSOFTENED)
```
The **quadrupole is not softened** (`R2q` uses `max(ds2,1e-30)`, not `ds2+eps2`), so a
particle passing close to a node's COM at `ds2 ≈ 1e-12` gets a quadrupole term
`∝ 1/ds2³` ≈ 1e36 · Q — astronomically large *finite* force. In the collapsed core
(fr≈140–200, min position ~28 → particles clustering with sites at small separations)
this singles blow-ups eject the first particles. `eps2=1e-6` (softening length 1e-3 in a
box of extent ~100) is far too small to damp close encounters at core densities.

### (b) River-calibrated `G_N` applied to the tree's direct-sum force — 
`compute/cassi_nbody_gravity.glsl:538 tree_river_field_acc` + `scripts/cassi_sim.gd`
`_apply_gravity_calibration`
`G_N = 4π / (π_ref·g_ref·V_cell·m_mean)` is calibrated so the **river/spectral-Poisson**
arm gives `|a| ≈ M_count/r²` (IC convention) — the Poisson-solved ∇Φ carries an implicit
`V_cell/(4π r²)` suppression that the calibration inverts. The tree's `tgrad = −∇(Σ w_s/
|r−r_s|)` is a **direct Newtonian field** with NO such suppression (and its site weights
`w_s = m_s·g_s` with `g_s ≈ ξ = 17.9` for coherent sites, already doubled by the ξ
coupling). Applying the same river `G_N` therefore **over-multiplies the tree force** in
the near field by roughly `4π r²/(V_cell·π_ref·g_ref)` — a large, radius-dependent
over-force. River control `acc_max` (~2870 peak, bounded) vs tree `acc_max`/`tgrad_max`
(56k–237k, unbounded) is the measured ×100–×10⁴ gap.

## Fix design (for the next turn — do NOT edit sim/GLSL this turn)

### 1. Soften the walk's near field — `compute/cassi_tree_gravity.glsl` (region: accept-block, lines ~119–143)
- Make the quadrupole denominator use the same softening as the monopole:
  ```glsl
  float R2q = ds2 + pc.eps2;                       // was: max(ds2, 1e-30)
  ```
- Raise the actual softening to a **physical scale** for the force field, not 1e-6:
  `ML_TREE_EPS2` in `scripts/cassi_sim.gd` (~line 495) from `1e-6` to roughly
  `(0.02·extent_min)²` (a small fraction of a leaf/spiral-core scale), so close encounters
  are damped (Barnes–Hut standard practice). This alone stops the single-encounter ejections.

### 2. Calibrate the tree force magnitude to match the river/IC convention — 
`compute/cassi_nbody_gravity.glsl:538 tree_river_field_acc` + `scripts/cassi_sim.gd`
`_tree_local` / `_apply_gravity_calibration`
- Introduce a **tree-specific effective `G_tree`** (or a `tgrad` scale factor) so that at a
  matched source/target configuration the tree force equals the river force. The exact
  coupling is already measured by `verify_meshless_gravity`'s G30 gate (GPU tree gradient
  vs stage5_fmm, median 1.22e-5 shape agreement) — reuse that recipe to fit the scalar that
  makes `|a_tree| = M_count/r²` at a test cluster, then emit it in the mode-5 seam
  (`bh[1].w` is the river constant; multiply `tgrad` by `(G_tree/G_N)` or carry a second
  header float). Do not blindly reuse the river `G_N` for the tree arm.

### 3. Hardening guard (belt-and-suspenders) — `scripts/cassi_sim.gd` / nbody pass
- Cap per-particle |Δv| and/or |pos| (the codebase already has `_enforce_camera_max_distance`
  for the camera but **no particle-position/velocity clamp**). A `|v| ≤ v_max` per-step cap
  (and, symmetrically, a `|acc|` cap in the KDK) guarantees a close encounter can never
  eject a particle or overflow float32 regardless of calibration. This is what converts
  "catastrophic vanish" into "bounded, recoverable transient" structurally.

**Order of work (next turn):** (1) soften the quadrupole + raise eps2 → re-run this verify
(expected: no fr=160 ejection); (2) fit `G_tree` → re-run (expected: tree acc ≈ river acc);
(3) add the |Δv|/|pos| guard → re-run the full 2×N frames on both paths and require
`alive ≥ 0.98·N` with `nan=0` everywhere, matching the river control baseline.

## Re-run instructions
```
_diag/godot_runtime/Godot_v4.7.1-stable_mono_win64_console.exe \
  --path C:/Users/Carina/workspaces/physics/godot/space-sim \
  res://scenes/verify_particle_vanish.tscn > _diag/vanish.log 2>&1     # tree mode (buggy)
_diag/godot_runtime/Godot_v4.7.1-stable_mono_win64_console.exe \
  --path C:/Users/Carina/workspaces/physics/godot/space-sim \
  res://scenes/verify_particle_vanish.tscn -- --river > _diag/vanish_river.log 2>&1  # control
```
Windowed (never `--headless` — the tree arm + GPU-direct instancer need a real GPU).
