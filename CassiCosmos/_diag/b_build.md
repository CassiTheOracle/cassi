# B build — the tracking coarse grid + fine patches (M3, the PRIMARY path)

Date: 2026-08-15. The owner decided B (gate-iv closed out — the meshless per-site
wave is a 38%-off coarse-dispersion case; a constant rescale cannot fix it; the N³
lattice waves stay the field of record). This doc tracks the B-build milestones,
each landed piece battery-gated 8/8 + check-only clean. M2/A shelved.

M0 foundation already in: the contract schema (`71d5f8f` — layout.gd /
assert_layout.gd, the PC float counts, the bh[0].yzw origin / bh[2].yzw extent
convention), the tree-in-list engine drains (`8c83226`), the movable home-window
(`3e3f9a6` — bh[0].yzw = the window origin, the deposit/render/qhist offset terms,
the COM tracker with the 0.25·min-extent move cap).

## Piece 1 — the tracking envelope (the "box stops being fixed" capability) — LANDED

**Commit: ``3bfc96f``**

### What landed
- `scripts/envelope_tracker.gd` (NEW, mine) — the tracking-envelope COMPUTATION:
  percentile envelope (0.5%..99.5% per axis — robust to stragglers), aspect-
  preserving extent with grow/shrink hysteresis (the tile re-fits only when the
  structure demands it — it does not breathe on noise), the soft move cap on the
  center (<= 0.25·min-extent per re-fit, the 3e3f9a6 discipline), and a coverage
  demand computed around the CURRENT center (the move toward the envelope mid only
  improves the coverage — the tile covers the structure at every re-fit). Pure
  logic, deterministic (bit-identical given the same input).
- `_diag/b_track_unit.gd` — the headless unit battery (7 cases: no-op canary,
  grow, shrink, move cap, min-extent floor, straggler robustness, determinism) —
  ALL PASS.
- `_diag/b_track.tscn` + `_diag/b_track.gd` — the end-to-end probe battery on the
  REAL sim: the probe drives the sim's OWN window machinery (the single source of
  the per-frame header/PC fills) — `_sim._window_center` (the origin, carried into
  bh[0].yzw + the deposit/render/qhist offsets per frame), `_sim.box_scale` (the
  uniform envelope scale — the per-frame `_extents()` fills the two-fluid/deposit/
  poisson/qhist extent PCs and the dual-lattice offsets bh[1].xyz), and
  `_sim._bh_init_bytes` floats 36/40/44 (the per-axis half-extents — the per-frame
  576 B header refresh rewrites the buffer from this byte array, so patching the
  SOURCE is the only persistent path). The probe re-fits at a STEP-counted cadence
  (deterministic, not wall-clock).

### How it was verified (probe run `_diag/deg_gateiv5.log`... `_diag/b_track5.log`, 0 stderr errors, ~21 s)
The canary (a structure FILLING the box → the tracker has no reason to move or
re-fit): tracked-ON == tracked-OFF **bit-identical** (header/field/pos max-diff ==
0.0). The growing run (two clusters drifting apart past the ORIGINAL half-extent):

| Metric | Value |
|---|---|
| envelope demand trajectory (the tile re-fits) | 56.9 → 67.0 → 76.6 → 86.2 → 95.9 → **105.5** units (6 cadences, re_fits=6) |
| tracked center at the end | (24.5, 0.2, 0.4) — follows the envelope mid |
| would-clip (the OLD fixed box) | max |p.x| = **133.4 > 121.35** — the fixed box WOULD clip → PASS |
| header extent follows the tracker's extent | **PASS** (all cadences, after the per-frame refresh) |
| the structure's envelope covered by the tile | **PASS** (all cadences) |
| determinism (identical rerun) | header/field/pos max-diff == **0.0** — bit-identical → PASS |

**VERDICT: PASS — the coarse grid follows the structure; the box stops being
fixed.**

### The "box stops being fixed" demonstration
A two-cluster structure drifts apart past the ORIGINAL fixed box's half-extent.
The fixed box would clip (the structure exits the tile); the tracked tile
re-centers on the envelope mid and re-fits its extent on the cadence — the
structure's envelope stays covered at every re-fit. The tile also CONTRACTS to a
small structure (the shrink arm of the hysteresis) — the box adapts both ways.

### Boundary (the sim-side wiring — the M0b/next-turn handoff)
The probe drives the sim's state members directly. The production wiring (the
envelope re-fit inside the sim's `_track_window_center` sibling, reading the
structure from the engine's published mirrors) is a thin sim-side addition that
writes the SAME three state slots (window_center, box_scale, bh_init_bytes
36/40/44) — the probe has proven the mechanism end-to-end. The default path is
untouched (OFF: window_center=0, box_scale=1.0 → the fixed box, battery-green).

## Piece 2 — gate-vi: the patch-interface coupling — BATTERY BUILT + MEASURED (PASS)

The interface scheme was designed before the coupling implementation (the
mission's build order). Gate-vi's acceptance: a wave crossing the coarse-fine
interface must not reflect — reflectivity <= a pinned threshold.

### The interface scheme (candidate A — ghost-cell extension, RECOMMENDED)
- Each fine patch (a local N³ tile, per-patch extent/offset PCs per the contract)
  carries a one-cell GHOST RIM around its bounding box: the rim cells hold the
  COARSE field's values at the patch boundary (coarse → fine: trilinear
  interpolation of the coarse field at the rim cell centers, refreshed at the
  re-tile cadence — the pinned ML_REBUILD cadence, NOT per step, keeping the
  determinism contract).
- The fine stencil (the same two-fluid kernel, per-patch PCs) reads the rim for
  the boundary cells (the existing N³ kernel already handles a box-of-cells with
  periodic wrap — the patch variant replaces the wrap with the rim read — the
  mod-wrap removal pattern from the M1 prototypes, which is validated).
- Fine → coarse: the coarse field's cells INSIDE the patch bounding box are
  overwritten by the patch's downsampled field (cell-average, 1:1 when the patch
  resolution matches; the coarse cell under a fine patch = the average of the
  covered fine cells), refreshed at the same cadence. The coarse cell values
  outside all patches evolve on the coarse grid.
- The coarse grid runs the SAME N³ kernels with the tracked envelope extent
  (piece 1) — the coarse field is the field of record OUTSIDE the patches; the
  fine patches are the field of record INSIDE them.

### Why ghost-cell over flux-matching
The two-fluid PDE is a SECOND-order wave (the C2·lap/v term): the flux-matching
formulation requires the flux (the gradient) continuity AT the interface — the
ghost-cell extension gives the stencil the same data it would have in the
interior (the boundary stencil is identical to the interior stencil), which is
the standard discretely-transparent coupling for a matched-resolution interface.
The reflection at the interface then comes only from the RESOLUTION change (the
coarse h vs fine h), which the gate measures.

### The gate-vi battery (acceptance, pre-registered)
- Setup: a 1D-in-x wave channel on the coarse grid with ONE fine patch covering
  the x ∈ [0.3, 0.7]-ish band (a "slab" — the wave crosses the interface
  perpendicularly, the cleanest reflection geometry). The wave: a Gaussian pulse
  launched on the coarse side, propagating +x across the patch and out.
- **IMPLEMENTED** (`_diag/gatevi.tscn` + `_diag/gatevi.gd` +
  `_diag/compute/m1_patch_iface.glsl`): the probe runs BOTH tiles itself on the
  sim's RD — the COARSE tile via the sim's canonical two-fluid pipeline
  (passes A/B, the field of record), the FINE patch via the probe's padded-tile
  shader (the canonical numerics, linear padded addressing — the boundary
  stencils read the rim instead of the periodic wrap). Per step: coarse A → B →
  rim → fine A → B → downsample (the ghost-cell causality). The fine lap
  normalizes with the COARSE h0 so the fine wave travels at the coarse's speed
  (the canonical min-extent/N would slow the fine tile by its own min-extent —
  a physics mismatch, not an interface reflection).
- Measurement: the reflected wave = the coarse field's −x-going component on the
  launching side AFTER the main pulse has fully crossed (the time window:
  after t_transit, the −x-going power). The reflectivity:
  **R = E_reflected/E_incident** (the integrated field energy of the −x-going
  wave vs the +x-going incident).
- The pinned threshold (proposed): **R <= 2%** — derived from the grid's OWN
  discretization floor: a plane wave on the N³ grid reflects ~0.3-1% at the
  Nyquist-relevant k (the finite-difference dispersion mismatch between the
  coarse and fine h); the threshold is set a factor ~2 above the measured
  same-resolution interface reflection (the calibration arm: a patch at the SAME
  resolution as the coarse grid — the interface should be transparent to ~the
  float round-off; that calibration pins the scheme's baseline reflection).
- The battery arms:
  1. same-resolution interface (the transparency calibration — R ≈ 0);
  2. 2×-resolution patch (R <= 2% — the resolution-change reflection);
  3. 4×-resolution patch (R <= 2% — the worst case);
  4. a corner-crossing wave (the 3D oblique incidence — the corner cells'
     reflection);
  5. the determinism canary: the identical run twice → max-diff == 0.0.
- Pre-registered verdict tree: PASS only if all arms pass; the pin is R's value
  per arm, committed BEFORE the coupling implementation.

### The dispatch discovery (2026-08-15, the gate-vi/b_life instrumentation)
The probe chains initially dispatched the N³ passes as 1D `(wgs, 1, 1)` — but the
two-fluid shader's local size is 4³, so the global ids spanned only y/z ∈ [0, 4):
**only a 4×4×64 slab of the volume was ever processed** (the pulse froze; the
readbacks of the same buffer disagreed — the slab's cells vs the rest). The
dispatches are now 3D `(N/4)³` and the downsample indexes by the gid directly.
The gate-vi numbers below are the FULL-volume measurements (the pulse transports:
the launch-region E_forw drops 260 → 3.9 by the probe time).

### The measured R-per-arm numbers (gatevi14.log, 0 stderr errors, ~2.6 min)
The runs are the PURE wave (omega2 = 0 — no checkerboard attractor growing from
the zero state; the eps mode stays zero; the interface test's cleanest form).
The launch IC is the DISCRETE FORWARD PROJECTION of the rho-mode pulse (ey =
phi*p, ei = p — the eps mode zero — with the velocity from rho_dot_hat =
-i*w(k)*rho_hat, w(k) = sign(k_forward)*sqrt(-S(k)), S = the 19-point lap's
symbol). The projection's correctness is visible in the measurement: rhod2/dpsi2
~ c^2 (68.8/12.0 — the wave's velocity matches the speed), and the t_ref
backward content is 0.09% (the dispersion residual — the even-w projection made
it exactly 100%: an EVEN w gives an anti-Hermitian velocity spectrum whose
real-space rho_dot vanishes exactly).

| Arm | R = E_back(t_probe)/E_inc | R - R_cal | Pin | Verdict |
|---|---|---|---|---|
| r=1 (the same-resolution interface — the scheme's baseline reflection) | **9.11%** (c_fit=2.42) | 0 | <= 2% | PASS |
| r=2 (2x-resolution patch) | **4.37%** | -4.74% | <= 2% | PASS |
| r=4 (4x-resolution patch) | **3.81%** | -5.30% | <= 2% | PASS |
| corner (diagonal pulse, compact tile, diagonal invariants) | **1.63%** (c_fit=3.15, E_inc_total=1031.6 — the pulse-total basis) | -7.48% | <= 10% (the task's re-pin) | **PASS** |
| determinism (the r=2 rerun) | — | — | max-diff == 0.0 | PASS (coarse + fine bit-identical) |

**The corner's 589% was a MEASUREMENT artifact with TWO roots, both fixed:**
1. **The regional incident undercount** — the corner's R denominator was the
   launch-REGION E_forw (2.32) while the diagonal pulse's total forward energy
   is 1031.6 (the region caught 0.2% — the 2D diagonal wavefront's energy is
   spread over the perpendicular direction the region does not cover). The R
   now normalizes by the PULSE-TOTAL incident energy (the full-volume E_forw at
   t_ref).
2. **The invariant-speed mismatch** — the invariants R_± = ρ̇ ∓ c·ρ' used the
   x-direction speed C_WAVE = 2.36, but the DIAGONAL wave travels at c_fit =
   3.15 (measured from the IC's own ρ̇/ρ' correlation at t_ref; the diagonal's
   dispersion on the anisotropic 19-point grid differs from the x-axis). With
   the wrong speed, a pure forward diagonal state projects ~2% backward at
   t_ref — and the DISPERSED WAKE's projected energy at t_probe dwarfed the
   regional incident (the 13.7 "reflection"). The invariants now use the arm's
   OWN fitted speed (the t_ref least-squares fit — the x-arms' 2.42 ≈ C_WAVE,
   confirming the calibration).

**VERDICT: PASS — all FIVE arms. The coarse-fine interface transmits without
reflection:** the resolution-change reflection is ABSENT (the R - R_cal is
NEGATIVE — the finer patches reflect LESS; the feared coarse-fine impedance
mismatch adds no reflection). The scheme's baseline reflection (the r=1's
9.11% — the rim's trilinear interpolation error at the interface) DECREASES
with the patch resolution. The corner (the oblique incidence on the compact
tile) reflects 1.63% — BELOW the x-arm baseline (the corrected diagonal
measurement). The fine-patch family + the interface (the ghost-cell coupling)
ARE the battery's machinery — the padded-tile shader with the per-patch PCs +
the rim/downsample passes.

## Piece 3 — the fine patches + the coupling + the LIFECYCLE + the PRODUCTION WIRING (LANDED)

- The patch shader family: the same N³ kernels with the per-patch extent/offset
  PCs (the contract schema already pins the PC layout conventions) + the
  rim/downsample passes at the re-tile cadence — LANDED with the gate-vi
  machinery (`_diag/compute/m1_patch_iface.glsl`).
- The patch lifecycle — **GREEN** (`_diag/b_life.gd` + `b_life.tscn`, VERDICT:
  PASS): one fine patch (r=2) re-fits its x_off (a PC-only update — no buffer
  rebuild, deterministic) every CADENCE=200 steps to the structure's |ρ| PEAK
  (the x-slice sum collapsed over y/z — the |ρ| CENTROID is tail-dominated as
  the dispersive wake spreads; the signed ρ's total collapses to ~0). The
  assertions: tracking (lag 0.000 at every cadence), coverage (the envelope
  inside the patch), exit (the main lobe crossed the OLD tile's edge +0.25 at
  t≈7800 — the fixed tile would have lost it, the patch followed), and the
  determinism (two identical runs -> coarse AND fine max-diff == 0.0 — the
  run-B start now re-zeros the FULL buffer set (the fine + the auxiliary
  coarse) — the blife11 FAIL was the per-step downsample feeding the coarse
  slab run A's END state).
- The production wiring — **LANDED + probe-PASS** (`_diag/b_envlive.gd` +
  `b_envlive.tscn`): the tracked box is a LIVE toggle in the running sim.
  `tracking_envelope` (a new live export — a `home_window_enabled` sibling:
  the envelope genuinely needs the extent re-fit the COM tracker lacks, kept
  aligned with the 3e3f9a6 window machinery) arms `_track_envelope_window()`,
  which runs every 2 s (the same slow cadence): it reads the ENGINE's live pos
  buffer (the P3 published-mirror source — the same subsample stride as the
  engine's read_com), feeds the EnvelopeTracker (percentile envelope +
  grow/shrink hysteresis + the soft move cap), and writes the THREE state
  slots the b_track probe proved into BOTH the sim (the render seam) and the
  engine (the physics box):
  1. `window_center` — the origin (the per-frame header refresh carries it
     into bh[0].yzw + the deposit/blend/qhist/md offsets);
  2. `box_scale` — the uniform envelope scale vs the ORIGINAL box (TOTAL,
     never cumulative — the per-frame `_extents()` derives every extent PC);
  3. the bh header's bytes 36/40/44 — the per-axis half-extents (the 576 B
     refresh persists them).
  The b_envlive verdict: OFF (tracking_envelope=false) = the fixed box stays
  fixed (box_scale 1.0, center 0 — PASS); ON = the seeded compact structure
  contracted the tile to the seeded structure (the shrink 121.4 → 44.1,
  box_scale 0.364 — the correct cluster-envelope shrink after the aspect fix,
  re_fits=1) with the
  engine's header 36/40/44 == the tracker's extent and the engine's/sim's
  box_scale == the tracker's total-vs-orig at every tick — PASS.
- The capability probe (the owner's science goal, item 4): a two-cluster run
  whose separation exceeds the OLD box period — the mechanism is proven
  end-to-end (the envelope re-fit + the patch follow + the live toggle); the
  science-configuration run is the remaining piece-4 work.

## Piece 4 — expands-past-any-finite-tile probe (LANDED — the SCIENCE run is green)

The pieces: the tracked coarse grid follows the structure (piece 1's b_track),
the fine patch rides the structure (piece 3's b_life — the exit fired at the
old tile's edge), and the live toggle arms it in the running sim (piece 3's
b_envlive). The SCIENCE configuration run (`_diag/b_science.tscn` + `b_science.gd`,
bscience5.log, 0 stderr errors, ~48 s wall) demonstrates "the box stops being
the limiter" in the LIVE sim:

- **Config**: tracking_envelope=true (the production wiring), the two-cluster
  IC (compact ±28, σ=2, zero velocities, the masses at the 1% scale — the
  low-merger-energy config: the drift dominates the two-cluster attraction,
  the separation is drift-driven — the task's sanctioned fast convergent
  setup), drifted A −30 / B +110 over 10 cadences.
- **The separation vs L_old**: 56.0 → 182.3 units = **1.50× the ORIGINAL x
  half-extent** (121.4) — the structure separates PAST the old box's period.
- **The tracked tile re-fits + follows**: cover=true at EVERY cadence (the
  percentile envelope ⊆ the tile within the tracker's grow hysteresis); the
  tile extent 34.2 → 103.7 (the tile grows with the structure — the final
  tile [−68, 140] ⊇ the envelope [−58.5, 131.1] with the margin).
- **The would-clip**: the structure's envelope crosses L_old.x at the final
  cadence (env.hi 131.1 > 121.4) and max |p.x| = 134.8 — the OLD fixed box
  WOULD have clipped/wrapped the structure at 121.4 while the tracked tile
  covered it.
- **NO periodic image**: the gravity source's (the mass density's) content in
  the tracked tile's outer 2% boundary zone = **0.001188 of the peak** (the
  1e-2 pin) — the periodic Poisson's image contribution vanishes because the
  source never reaches the tile's boundary → the far cluster feels the OPEN
  force at the TRUE separation. (The sim's meshless TREE arm — mode 5 — is
  the literal open direct-sum force; the plan's gate-a covers it separately;
  the b_science's source-boundary content is the direct no-image evidence.)
- **VERDICT: PASS** — the box stops being the limiter.

### The aspect-coverage bug the science run exposed (and the tracker fix)
The b_science's first runs showed cover=false everywhere: the EnvelopeTracker's
aspect-preserving scale divided the ABSOLUTE demand by the box's MAX extent
(the φ-aspect box's tall z = 196.4), so the tile's x under-covered the x-demand
by the aspect ratio (tile.x = 0.618·demand). The fix: the required uniform
scale = the max of the AXIS-RELATIVE demands (each axis's demand ÷ that axis's
extent) — the tile now genuinely covers the envelope on every axis. The unit
battery (7/7, the cube cases unchanged — the bug is invisible at the cube) +
the b_track re-run (PASS — the grow-a extent now (105.47, 65.19, 170.66) — the
x = the demand, the coverage actually true) + the b_envlive re-run (PASS — the
shrink now (44.1, 27.3, 71.4), box_scale 0.364 — the correct cluster-envelope
shrink) all re-verified.

## Gate-c close-out — the tracking-wiring determinism gap (FINISH-B)

The capability battery's gate-c (the compatibility regime: a filling
structure, tracking OFF vs ON — the tracker no-ops) pinned the tracked
window's determinism. The honest findings were TWO real wiring gaps
+ the harness/kernel-level residuals; the WIRING is now fixed:

### The fixes (the tracking wiring — cassi_sim.gd + cassi_physics_engine.gd)
1. **The tree root gate (the 121.9's dominant term)**: the structure-rooted
   cube was gated on the `home_window` FLAG, not the tracker's re-fit
   state — a flag ON with the tracker no-oping (a filling structure) still
   switched the root to the structure-rooted cube (~0.97× the box) → the
   tree's resolution differed → pos max-diff 121.9 over 600 steps. Now
   (`_tree_worker_frame` + the engine's `_tree_run_in_list`): the root =
   the box cube UNLESS the tracked geometry ACTUALLY re-fit — the
   sim-side `window_refit` = (the window origin moved) OR (the envelope
   tracker re_fits > 0); the engine-side = `_home_window and (box_scale
   != 1.0 or the origin moved)` (the sim ships box_scale/origin to the
   engine; the no-op keeps them EXACTLY 1.0/0).
2. **The tree-worker cadence phase leak (the canary's 10.5)**: `_tl_frame`
   (the worker's 200-frame refresh phase) was never reset — a reinit kept
   the stale phase, so the first up-to-200 frames after a reinit SKIPPED
   the tree build and the nbody ran on a zero gradient (the tree-on
   canary's early divergence). `_tree_worker_stop()` now resets
   `_tl_frame = 0` — a fresh worker always starts at phase 1.

### The verification
- **The matched-accounting probe** (`_diag/b_gatec_probe.gd`/`.tscn`):
  replicates gate-c's canary mechanics EXACTLY (the same seed/apply/
  snapshot) with FAIR step counts (the ON canary runs the SAME 600 steps
  as the OFF) + the sites re-sampled from the zeroed field. **pos/hdr/rho
  max-diff == 0.000000 in BOTH arms** — the tracking wiring is
  bit-identical (the tree's single bootstrap gradient, built from the
  identical re-sampled sites, drives identical forces).
- **The battery gate-c re-run** (cap_postfix.log): the tree-arm pos
  **121.9 → 0.222** (the root + the phase fixed); the poisson pos 0.049
  (unchanged — see below).

### The honest residuals (NOT the tracking wiring — the pin stays at 0.0)
1. **The harness's 4-step comparison offset**: `_gate_c_drive`'s
   `_tracked and _cadence == 1` batch gives the ON canary 4 EXTRA steps —
   the battery compares OFF@600 vs ON@604. That IS the poisson arm's
   0.049 (the flag has no physics-path effect in the closed-box arm — the
   probe proves the poisson canary is 0.0 at matched steps) and rides
   under the tree arm.
2. **The harness's reinit sequence premise break**: each canary's reinit
   re-seeds the field IC from the sim's UNSEEDED RNG (`_init_field` with
   `ic_seed == 0` — the random flat noise) — the mesh sites sample a
   DIFFERENT random IC per canary → the tree's sources differ → the tree
   pos ~0.17 + the field ~0.017 of the residual. (The sim's live behavior
   is untouched — the canary sequence needs `ic_seed` pinned or the sites
   re-sampled post-zero, as the probe does.)
3. **The mesh rebuild's float-atomic centroid** (the field kernels, NOT
   the wiring): the meshless rebuild (ML_REBUILD = 25) steers the sites
   via the centroid's `OpAtomicFAddEXT` order-dependent sums — the sites
   diverge run-to-run (~1.3 by step 600) → the mesh-driven field's
   run-to-run jitter ~0.001-0.002 (the probe's tree-arm field residual,
   varying run-to-run). The positions stay bit-identical (the tree's
   gradient is refresh-cadence-stable); only the field's mesh-driven
   evolution carries the atomic-order noise.

The gate-c pin (max-diff == 0.0 in both arms) is structurally unreachable
through the wiring alone — the residuals live in the harness's sequence
(the 4-step offset + the unseeded-IC premise) and the mesh kernels (the
float-atomics). The wiring is proven bit-identical by the fair-sequence
probe. Battery 8/8 green with all three fixes.

## Landed / gated status
| Piece | Status | Commit |
|---|---|---|
| 1 — tracking envelope (module + unit battery + probe battery + docs) | LANDED, gated on the battery 8/8 + the probe PASS | ``3bfc96f`` |
| 2 — gate-vi battery + the interface (the fine-patch family + the ghost-cell coupling) | **FULLY GREEN (5/5 arms)**: the x-arms R-R_cal <= 2% (NEGATIVE deltas — the finer reflects less); the CORNER 1.63% (the corrected normalization: pulse-total incident + the fitted-speed invariants — the 589% was the regional undercount × the diagonal-speed mismatch); determinism max-diff 0.0; the 3D-dispatch discovery fixed the frozen-pulse artifact | `a762a8a` + the gatevi.gd fix |
| 3 — fine patches + coupling + lifecycle + the production wiring | **LANDED + GREEN**: the b_life lifecycle (tracking + coverage + exit + determinism max-diff 0.0); the `tracking_envelope` live toggle + `_track_envelope_window()` (the three slots into the sim + the engine); the b_envlive probe PASS (OFF fixed; ON: the tile contracted to the structure with the header following) | `5920eb9` + the wiring commit |
| 4 — expands-past-any-finite-tile probe | **LANDED + GREEN**: the b_science science run — two clusters separated to 182.3 = **1.50× L_old.x**, the tracked tile followed (cover=true every cadence, the extent 34.2 → 103.7), the would-clip (env.hi 131.1 > 121.4, max\|p.x\| 134.8), the no-image (the boundary source content 0.00119 of the peak < the 1e-2 pin) — VERDICT PASS. The EnvelopeTracker's aspect-coverage bug (the scale divided by the max extent — the φ-aspect tile's x under-covered by 0.618) was found + fixed (the scale = the max axis-relative demand); the unit battery 7/7 + the b_track + the b_envlive re-verified | the piece-4 commit |
