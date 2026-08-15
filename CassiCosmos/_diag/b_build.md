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

**Commit: `<pending>`**

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

## Piece 2 — gate-vi: the patch-interface coupling design (ON PAPER — gated)

The interface scheme is designed BEFORE the coupling implementation (the mission's
build order). Gate-vi's acceptance: a wave crossing the coarse-fine interface must
not reflect — reflectivity <= a pinned threshold.

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

## Piece 3 — the fine patches + the coupling (GATED — after gate-vi passes)

- The patch shader family: the same N³ kernels with the per-patch extent/offset
  PCs (the contract schema already pins the PC layout conventions) + the
  rim/downsample passes at the re-tile cadence.
- The patch lifecycle: spawn on the structure's local condensations (the
  envelope tracker's per-cluster decomposition — the same percentile logic at a
  smaller scale), re-tile at the pinned ML_REBUILD cadence, die when the
  condensation dissolves.
- The capability probe (the owner's science goal, item 4): a two-cluster run
  whose separation exceeds the OLD box period — the tracked coarse grid follows
  (piece 1), the patches ride the clusters, NO periodic image (the structure's
  field stays inside the tracked tile).

## Landed / gated status
| Piece | Status | Commit |
|---|---|---|
| 1 — tracking envelope (module + unit battery + probe battery + docs) | LANDED, gated on the battery 8/8 + the probe PASS | `<pending>` |
| 2 — gate-vi design (interface scheme + battery + threshold) | ON PAPER (this doc) — the coupling implementation GATED on the battery build | — |
| 3 — fine patches + coupling | GATED (after gate-vi passes) | — |
| 4 — expands-past-any-finite-tile probe | folds into piece 1's mechanism + piece 3's patch story | — |
