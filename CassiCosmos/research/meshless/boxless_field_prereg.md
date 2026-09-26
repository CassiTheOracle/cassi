# Boxless-field pre-registration — Lever 2: true boxless via the moving-Voronoi mesh

Date: 2026-08-17
Owner: Carina
Status: PRE-REGISTERED (frozen before any engine edit)
Series: MESHLESS_PLAN.md §10 follow-on — the "truly boxless sim" lever-2 arm

## 1. Problem (the owner's words)

> "Are we any closer to a truly boxless sim? The tracking envelope doesn't adjust quickly,
> or accurately, enough."

Envelope throttles identified (read: envelope_tracker.gd, cassi_physics_engine.gd, cassi_sim.gd):

- `ENV_TRACK_CADENCE_MS = 2000` — re-fit every 2 s, not per-step
- `COM_MOVE_CAP_FRAC = 0.25` — origin move capped at ¼ min extent per tick
- `COM_DEAD_BAND_FRAC = 0.02`, percentile 0.5/99.5, `PAD = 1.05`
- Aspect-preserving uniform `box_scale` — cannot reshape/rotate/stretch
- Re-fit requires `reinit()` (extents encoded at setup); only the center moves live

The conclusion from the scope read: the **envelope is only chasing the render grid**.
The **field evolution is already boxless** (see §3). Lever 2 makes the readers
(render/instancer/qhist + the grid-carrier physics readers) source coherence/phase
directly from the Voronoi sites, so nothing needs the periodic raster grid as a
carrier and the tracking envelope becomes an optional render attachment instead of
a physics requirement.

## 2. Goal (frozen)

Make the meshless field's **output surface** (not its evolution, which is already
site-resident) read from the **Voronoi sites** directly — a point-locate into the
moving mesh — so that:

- The periodic raster grid (`_field_ey/_field_ei/_field_q`) is **no longer a physics
  carrier**: it becomes an optional render/display attachment.
- The **tracking envelope** is no longer needed to keep the physics correct — a
  particle's field influence and coherence are read at its own mesh cell regardless
  of where the structure has drifted.
- This is the stepping stone to a future fully boxless run where the periodic grid
  (and thus the 2 s/25% envelope) can be shrunk or eliminated entirely.

Concretely implemented behind a **default-off additive toggle** (`boxless_field`, 0/off):
the render/instancer/qhist coherence+phase reads switch to a site-direct path.
Bit-identical default battery is the acceptance gate.

## 3. What the scope read established (facts, not assumptions)

The meshless step chain (engine run_steps, meshless branch):

```
mass deposit (poisson mode 3 clear → deposit → convert) → rho_mass[] scratch grid
→ [meshless] mode 10 grad-zero → mode 0 lap → mode 1 leapfrog → mode 12 least-squares
→ raster (site state → _field_ey/_field_ei/_field_q periodic grid)
```

- **Field evolution is site-resident and boxless already**: modes 0/1/12 evolve
  `_ml_psi_y/_ml_psi_i` (+ `_ml_pi_*`, `_ml_lap_*`) **on the Voronoi sites**, which
  follow the structure via steering/remap (the moving-Voronoi/ALE mesh). No `%N`
  periodic wrap, no box extent, in the state evolution's RHS.
- The only grid reads inside the sites' evolution are **per-site mass density**
  (from the same-step `rho_mass` scratch) and the site-local lap/coherence — both
  site-resident after deposit.
- **The raster (`cassi_voronoi_raster.glsl`) is the ONLY surface that writes the
  periodic grid** — one thread per grid cell, a Barth–Jespersen slope-limited linear
  reconstruction of the site state. Its 26-neighbourhood stencil uses `%N` periodic
  indexing (a small edge artifact of the lookup, not a physics wrap).
- **Readers of the periodic grid** (map): `cassi_field_render.glsl` (render target),
  `cassi_instancer.glsl` `tri_coherence`/`tri_phase` (per-particle trilinear sample),
  `cassi_qhist.glsl` (per-particle coherence at particle positions), and the
  grid-carrier physics readers `cassi_condensation.glsl`, `cassi_nbody_gravity.glsl`
  (river gradient), `cassi_particle_merge.glsl`, `cassi_bh_integrate.glsl`.

Thus the periodic grid is a **projection/carrier for readers**, not the field's home.

## 4. Non-goals (frozen — deliberately out of scope for this arm)

1. **No change to the sites' field evolution** (modes 0/1/12, the lap/leapfrog/lsm
   RHS, the winding term, steering/remap cadence). The physics that produces the
   field stays exactly as shipped.
2. **No change to the mass deposit** (the rho scratch grid + the mode-3 centroid /
   mode-0 lap density feed stay; the deposit's fixed-point determinism stays). The
   mesh must still follow the deposited material.
3. **No elimination of the render grid in one shot.** A display still needs a grid
   or a scatter every frame; this arm covers the *reader side* (site-direct samples)
   and the *gating* of the grid-carrier physics readers to their non-boxless paths.
   The periodic grid is *demoted* to an attachment, not deleted.
4. **No movement to per-particle/truly-boundary-free cells** — the Voronoi cells
   already define a local partition; "boxless" here means "no periodic grid carrier
   required for correctness," not a floating-domain re-partition (that is a future
   arm).
5. **No touching owner-live files**: nothing under `main.tscn`, `project.godot`,
   owner `research/`, `tools/`, `scenes/mind_engine*`, `verify_telescoping_weak.*`.

## 5. Statistic / metric / decision tree (frozen)

The gate is the **default-off bit-identical battery**, exactly the contract
established for the winding port (`assert_layout 0 mismatches` + the cells verify
arms + exact r(t) regression trajectories).

### 5a. Bit-identity (MUST pass — the hard gate)

- `assert_layout` reports **0 mismatches** (shader PC count ↔ `layout.gd` ↔ host
  `_cell_pc_bytes` / `*_pc_bytes` allocations).
- `verify_voronoi3d`, `verify_voronoi3d_moving`, `verify_meshless_reconstruct`
  **all PASS with default `boxless_field = 0`** and, where the existing arms pin
  exact trajectories, the trajectories are **bit-identical to the pre-change run**
  (the additive-off gate: the new toggle must be a no-op when off).
- The default sim run with `boxless_field = 0` produces **no change to any
  `_field_*` buffer** the battery checks.

### 5b. Toggle-on correctness (MUST pass — the point of the arm)

With `boxless_field = 1`, in a probe/verify scene that asserts coherence/phase at
particles:

- `tri_coherence` / `tri_phase` (or the qhist histogram) **site-direct** readings
  match the **rasterized-grid** readings to within the raster's own linear-recon
  tolerance on a known structure (e.g. a single coherent blob where the site value
  is flat). Decision: PASS if max |Δq| ≤ 1e-3, else FAIL-review.

### 5c. Decision tree (frozen, no post-hoc tuning)

1. If **5a fails** (bit-identity broken / assert_layout mismatch / battery red):
   verdict **REJECT** — revert the engine change, keep only the scope + design
   learnings.
2. Else if **5b fails** (site-direct readings disagree with rasterized):
   verdict **FAIL** — the site-direct path is wrong; fix or drop; do NOT ship a
   toggle that changes physics with default-off (a toggle is only acceptable if it
   is genuinely bit-identical off AND correct on).
3. Else: verdict **SUPPORTS** — the site-direct reader path is correct and the
   periodic grid is demoted to an attachment. Record the report; hand the "shrink /
   drop the periodic grid + drop the envelope" next arm to the owner for sign-off.

## 6. Pre-registered run plan (frozen)

1. Implement `boxless_field` (default 0) gated site-direct reader path:
   - Add a site-direct sample (nearest-cell via the JFA labels, or a point-locate
     into the exposed `_ml_sites` if cheaper) — a small GLSL helper sharing the
     same Cartesian convention as `tri_coherence`.
   - Gate the render + instancer + qhist field reads to the site-direct path when
     the toggle is on; leave the grid-carrier physics readers gated to the
     non-boxless/river paths as today (they already are in the meshless+tree arm).
   - Default-off additive + `>0` guard (bit-identical by construction).
2. Parse-gate the edited GDScript; glslangValidator standalone compile the edited
   GLSL (careful: **no `atan2` in desktop GLSL 4.50** — use `atan(y,x)` two-arg).
3. Godot `--import`, then run the cells battery arms (windowed, this rig's global RD
   has no headless device) + `assert_layout`.
4. `boxless_field = 1` probe comparing site-direct vs rasterized coherence/phase on
   a known blob; record max |Δq|.
5. Write `boxless_field_report.md`; get owner sign-off before shrinking/dropping the
   periodic grid in a follow-up.

## 7. Risks & mitigations (recorded at pre-reg, not resolved)

- **Raster is the output surface for condensation/BH/river too.** If any of those
  readers must run in the meshless+boxless arm, they need site-direct reads as well
  (extension of this arm). Mitigation: today those readers run on the river/legacy
  grid path; under `meshless_gravity` the tree arm already skips the Poisson chain
  (engine line 2334–2335), so the grid-carrier readers are not on the meshless+tree
  hot path. Recorded; revisit if the owner wants condensation/BH in boxless mode.
- **Point-locate cost / determinism.** A per-particle nearest-site lookup changes
  the instancer's sample pattern. Mitigation: reuse the JFA labels (already computed
  per rebuild) as the site index per cell, so a site-direct sample is a `labels[cell]`
  + a site-buffer read — deterministic, no new search. This is the primary design.
- **`atan2` GLSL trap** (the rig's known silent-SPIRV-failure): the phase must use
  two-arg `atan(ei, ey)`, never the one-arg form. Stated because a future phase
  helper is a likely source of the failure; verified with glslangValidator.

## 8. Acceptance

- `assert_layout` 0 mismatch.
- 3 cells-battery arms green + exact-trajectory arms bit-identical (default off).
- `boxless_field = 1` site-direct probe: max |Δq| ≤ 1e-3 vs rasterized on a known
  blob.
- Working tree clean of the manager's changes except the intended files; all Godot
  churn (`.glsl.import`, `project.godot`, `main.tscn`) reverted.
- No owner-live file touched.

Pre-registered signature: this document is frozen. Any change to §2/§3/§5/§6 during
implementation requires a new pre-reg version and owner acknowledgement.
