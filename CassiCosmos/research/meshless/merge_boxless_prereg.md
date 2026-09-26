# Merge-boxless pre-registration — the last grid-carrier physics reader

Date: 2026-08-17
Owner: Carina
Status: PRE-REGISTERED (frozen before any engine edit)
Series: boxless_field_prereg.md §4 non-goal 4 / boxless_field_report.md §3 — "the grid-carrier physics readers ... a separately pre-registered future arm". This is that arm, scoped to the *only* grid-carrier reader reachable in a boxless run: the particle-merge coherence gate.

## 1. Goal (frozen)

Make the **particle-merge coherence gate** (`cassi_particle_merge.glsl`) read its
coherence source from the **moving-Voronoi sites directly** (the cell-averaged
EY/EI the site leapfrog evolves) instead of the periodic raster grid, whenever
`boxless_field AND particle_merge` are both on — so merge correctness no longer
depends on the tracking envelope catching up with the structure.

This closes the last box-bound *physics* reader. After this arm:

- Field evolution: **already site-resident** (modes 0/1/12, no `%N` — frozen #1).
- Instancer coherence/phase: **already boxless** (Arm 1-4, shortlist + spatial hash).
- qhist coherence (color band / p1-p99): **already boxless** (`site_coherence`).
- **Merge coherence gate: boxless after this arm** (the sole grid-carrier reader
  that can run in a boxless sim without another opt-in toggle — see §3).

The periodic raster grid then carries only the *render* (and the grid-only
readers that require `black_holes_enabled` / the legacy river path, which are not
on the boxless track). Truly boxless physics.

## 2. Problem (from the code)

`cassi_particle_merge.glsl` pass_best (the qualified-pair test) reads coherence
from the **periodic truncated grid**:

```
qcoh_at(mid)   — trilinear EY/EI at the pair midpoint, %N periodic wrap
qord_at(mid)   — gradient-ratio order gate, 6 sigma_at(...) trilinear fetches + 8
                 corner Σ-fetches (~32 fetches), %N wrap
flow_at(pos[j])— virial-stop flow velocity, trilinear, %N wrap
virialized(j)  — uses flow_at(pos[j].xyz)
```

`corners_at` maps `gc = (wp·inv_ext)·hn + hn` then wraps `%N` on each axis. A
particle outside the tracked window (envelope lag) wraps to the opposite box face
and reads the **wrong** field — the same box exposure the boxless_field arm
eliminated for instancer/qhist, still live here.

## 3. Scope read (facts — why merge is the only reachable grid-carrier reader)

From `cassi_physics_engine.gd`:

| Reader | Grid read? | Active in a boxless (`boxless_field && meshless`) run? |
|---|---|---|
| `cassi_particle_merge.glsl` (`qcoh_at`/`qord_at`/`flow_at`) | yes | **yes — gated only on `particle_merge`.** This is the reachable one. |
| `cassi_condensation.glsl` (BH nucleation) | yes | only if `black_holes_enabled` (separate opt-in). |
| `cassi_bh_integrate.glsl` / `cassi_bh_accretion.glsl` | field reads | only if `black_holes_enabled` / `bh_accretion`. |
| `cassi_nbody_gravity.glsl` river gradient (pass_mode 1) | ∇Φ | skipped when `meshless_mode and meshless_gravity` (engine line ~2597: the tree arm produces ∇Φ directly). |

So **merge is the only grid-carrier physics reader on the boxless hot path.**
Condensation/BH are off under a plain boxless run (they need `black_holes_enabled`);
the river gradient is off under meshless+tree. This arm migrates merge and
records condensation/BH as coverage only if the owner subsequently turns
`black_holes_enabled` on in a boxless run (a follow-up, gated identically).

## 4. Design (the boxless merge read — full fidelity, per owner sign-off)

When `boxless_field` AND `particle_merge` are both on (a new merge-PC flag), the
merge's **entire coherence description** reads from the **moving-Voronoi sites**
at a point, per the boxless_field_design.md §3 reader math (frozen, already
shipped in qhist's `site_coherence`):

1. Find the site `s` whose cell contains `wp` — **nearest site** over the live
   `_ml_sites` (8192 = 2·16³ at N=64). Coordinate-independent — no window, no
   extent, no `%N`.
2. Read `_ml_psi_y[s]`, `_ml_psi_i[s]` — the cell-averaged field.
3. `q_coh(wp) = (ey+ei)² / ((ey+ei)² + φ⁻² + (ey−φ·ei)²)` — identical formula to
   the grid path.

**Full fidelity (owner chose "Add the site-stencil q_ord too").** The site
gradient the order gate needs **already exists**: `cassi_voronoi_cells.glsl`
modes 10/12 compute the production-AREPO least-squares (face-normal)
reconstruction gradient `grad_y`/`grad_i` per site (cell-PC bindings 16/17,
`_ml_grad_y`/`_ml_grad_i`), exact for linear fields on any mesh — the same
gradient the raster consumes. The boxless `q_ord` reuses it (no second
convention):

```
Σ_s   = psi_y[s] + φ·psi_i[s]              (cell-averaged, same Σ as grid path)
∇Σ_s  = grad_y[s].xyz + φ·grad_i[s].xyz    (the AREPO face-normal site gradient)
q_ord(s)= 1 / (1 + φ²·|∇Σ_s|² / (Σ_s² + φ⁻²))   — identical ratio, site-resident
```

**Site flow for the virial stop (full fidelity):** the virial stop's flow
reference (`flow_at`, grid `_field_vel` = `(∂EY/∂t, ∂EI/∂t, 0, ε²)`) has a
site-resident analog: the site's own velocity implied by its momentum density,
`v_flow_site(s) = (pi_y[s] + pi_i[s]) / ρ_s` — the exact quantity the site
leapfrog's steering uses (`vv = lam·(pi_y+pi_i)/rho`, cell-shader mode 4). In the
boxless path `virialized(j)` and the subsonic-run `dv` use this site flow.

So in the boxless path **`q_sel = q_coh · q_ord` (full order gate)** and the
virial/subsonic runs use the site flow. This is a **behavior change when both
toggles are on** — the boxless merge is window-independent AND keeps the full
order/virial discrimination. It is exactly why the frozen-gate discipline
matters: the ON-probe (5b) measures the intended window-independence and the
read-location equivalence, not a hidden regression.

## 5. Statistic / metric / decision tree (frozen)

### 5a. Bit-identity (MUST pass — the hard gate)

- Default (`boxless_field = 0`, or `boxless_field = 1` with `particle_merge = 0`):
  the merge shader is **byte-for-byte unchanged** — the new flag is a guarded
  branch (≥0.5), dead when off, no zero-multiply.
- `assert_layout` reports **0 mismatches** (merge PC 24→26 floats, bindings 0-17→0-23).
- `verify_merge`, `verify_merge_gate`, `verify_merge_binding`, `verify_merge_spin`,
  `verify_merge_virial`, `verify_subsonic_step`, `verify_merge_engine` all **PASS
  byte-identical to the pre-change run** with default flags.
- The default sim run with `boxless_field = 0` produces **no change to any**
  `_field_*` **or merge buffer** the battery checks.

### 5b. Toggle-on correctness (MUST pass — the point of the arm)

With `boxless_field = 1` AND `particle_merge = 1` in a probe scene:

- **Window-independence**: place a known coherent blob of particles and a strong
  grid field; move the probe's tracked window OFF the blob (simulating a lagging
  envelope). Assert the boxless merge gate still reads the blob's site coherence
  (max |Δq| ≤ 1e-3 from the in-blob site value), while the grid trilinear
  (post-`%N` wrap) would return a wrong value. Record both. Decision: PASS if the
  boxless read matches the in-blob site value, FAIL-review otherwise.
- **Site-read correctness**: a site-direct `q_coh`/`q_ord` at a point identically
  reproduces the CPU nearest-site reference (`q_coh`: the site's cell-averaged
  value, 0 mismatch; `q_ord`: the ratio from `grad_y/grad_i`, 0 mismatch on a
  linear field — the AREPO gradient is exact there). The readers are correct.
- **Order-gate equivalence**: on a smooth standing wave (Σ locally constant,
  ∇Σ → 0) the site `q_ord` matches the grid `q_ord` to within the gradient
  reconstruction tolerance (the two are both ≈ 1).

### 5c. Decision tree (frozen)

1. If **5a fails** (bit-identity broken / assert_layout / battery red):
   verdict **REJECT** — revert; keep only the scope + design learnings.
2. Else if **5b fails** (site-direct read is wrong or still window-dependent):
   verdict **FAIL** — the boxless merge is not correct; fix or drop; do NOT ship.
3. Else: verdict **SUPPORTS** — merge is window-independent in boxless mode and
   the last grid-carrier physics reader is closed. Record the report; the periodic
   grid is now a pure render attachment for the boxless track.

## 6. Pre-registered run plan (frozen)

1. Implement the merge-boxless flag (default 0):
   - `cassi_particle_merge.glsl`: add a `boxless` PC float (append, default 0);
     in the boxless branch, `q_coh`, `q_ord`, and the virial/subsonic flow read
     the containing site's cell-averaged field + gradient + momentum density
     (nearest-site over `_ml_sites`) instead of the grid trilinear. Add bindings
     18-23 = `_ml_sites`, `_ml_psi_y`, `_ml_psi_i`, `_ml_grad_y`, `_ml_grad_i`,
     `_ml_pi_y`/`_ml_pi_i` (immutable; zero-cost when unread).
   - `scripts/contracts/layout.gd`: merge PC 24→26, bindings 0-17→0-23.
   - `cassi_merge_common.gd` (`_merge_pc_values`): append the `boxless` slot so
     engine + sim twins stay in sync. Host encodes `boxless` when
     `boxless_field AND particle_merge` (the sim passes `boxless_field`; engine
     gets it from the sim config).
   - Default-off additive + `>0` guard (bit-identical by construction).
2. Parse-gate the edited GDScript; glslangValidator the edited GLSL (**no `atan2`**
   — two-arg `atan(y,x)`).
3. Godot `--import`, then run the merge battery arms + `assert_layout`.
4. `boxless_field = 1` + `particle_merge = 1` probe: window-independence + site
   correctness + order-gate equivalence per 5b; record max |Δq|.
5. Write `merge_boxless_report.md`; owner sign-off.

## 7. Risks & mitigations (recorded at pre-reg, not resolved)

- **Site `q_ord` reuses the AREPO reconstruction gradient** (`grad_y/grad_i`, mode
  12 solve). It is exact for linear fields; on strongly curved fields it is the
  same production gradient the raster uses, so a site-vs-grid `q_ord` difference
  is bounded by the reconstruction tolerance (measured by the 5b order-gate
  equivalence probe). If the difference is unexpectedly large, record it — the
  site value is the *more* physical one (the mesh's own reconstructed gradient).
- **Site flow for the virial stop is momentum-density `/ρ`**, the site leapfrog's
  own velocity convention (mode-4 steering `vv`) — not the grid `_field_vel`
  (time-derivative). This is the faithful site-resident flow; the two agree where
  the field evolves slowly. Recorded as the intended definition.
- **Behavior change when both toggles on** (boxless merge is window-independent
  AND order-gated). The pre-reg names it (§4) so the ON-probe measures the
  intended window-independence, not a hidden regression.
- **Merge cadence / TDR**: the merge passing site reads adds no host sync; the
  site buffers are always allocated in meshless mode. The batched-merge TDR guard
  (MAX_CELL_SCAN) is untouched.
- **`_ml_sites` is steer-cadence-stale** (like the shortlist/hash): the site
  indices are a frame old. Merges are cadenced (1/2 R_m reaction budget), so a
  one-cadence-stale site partition is within the existing merge staleness; the
  window-independent read is what this arm guarantees.

## 8. Acceptance

- `assert_layout` 0 mismatch.
- Merge battery arms green + byte-identical (default off).
- `boxless_field = 1` + `particle_merge = 1` probe: site read window-independent
  (max |Δq| ≤ 1e-3 vs in-blob site value), CPU nearest-site reference 0 mismatch.
- Working tree clean of the manager's changes except the intended files; all Godot
  churn (`.glsl.import`, `project.godot`, `main.tscn`) reverted.
- No owner-live file touched.

Pre-registered signature: this document is frozen. Any change to §4/§5/§6 during
implementation requires a new pre-reg version and owner acknowledgement.
