# Boxless field — design — site-direct per-particle coherence/phase

Date: 2026-08-17
Scope: carries `boxless_field_prereg.md` into a concrete reader design (pre-reg §6 step 1).
Frozen acceptance: boxless_field_prereg.md §5 (5a bit-identity MUST, 5b toggle-on correctness).

## 1. Design goal (one sentence)

Make a **particle's field coherence/phase read from the Voronoi site whose cell
contains it** (a coordinate-independent point-locate into the moving mesh), so the
read no longer depends on the periodic raster grid, the tracked window, or the box
extent — the reader is boxless by construction and stops caring whether the tracking
envelope kept up.

## 2. What the three per-particle readers do today (from the code)

All three sample the **rasterized periodic grid** at a particle position:

- `cassi_instancer.glsl` `tri_coherence`/`tri_phase` (world pos `wp`):
  `gc = wp·inv_ext·hn + hn`, **periodic `%N` wrap**, trilinear over the grid.
- `cassi_qhist.glsl` `main` (particle `i`):
  `gc = (pos[i]−win)·inv_ext·hn + hn`, **periodic `%N` wrap**, trilinear.
- `cassi_particle_merge.glsl` (bindings 6/7 = `_field_ey/_field_ei`): grid q source.

The `%N` wrap + `win`/`ext` dependence is the box exposure: a particle outside the
tracked window wraps to the opposite side and reads the wrong field.

## 3. The boxless sample (frozen reader math)

The moving-Voronoi cell partition is the set of points nearest each site (modulo the
Lloyd steering). A boxless field read at world point `p` is:

1. Find the site `s` whose cell contains `p` — by **nearest site** over the live
   `_ml_sites` (8192 = 2·16³ sites; coordinate-independent, no window/extent/`%N`).
2. Read `psi_y[s]`, `psi_i[s]` — the cell-averaged field the physics already evolves.
3. Return `q = (ey+ei)² / ((ey+ei)² + φ⁻² + (ey−φ·ei)²)` and
   `θ = atan(ei, ey)/(2π) + 0.5` — the same bounded-coherence + phase formulas the
   instancer already uses, from the site's own cell-averaged (EY, EI).

This is the AREPO cell-averaged field at the particle — exactly the field the site
leapfrog evolves, so the reader is consistent with the physics by construction.

Brute-force 8192 nearest-site per sample is fine for **qhist** (strided diagnostic)
and for the **probe/verify** (a controlled blob). For the per-frame **instancer**
(N_p × 8192) it is a real cost; the design keeps the instancer's *color display* on
the rasterized grid (a display attachment per pre-reg §4 non-goal 3) and defers a
spatial-hash of sites to a follow-up, recording it in the report.

## 4. Wiring (additive default-off toggle `boxless_field`)

- **New engine var** `boxless_field: bool = false` (cfg-key `boxless_field`),
  following the `ham_completion`/`winding_coupling` additive pattern.
- **New GLSL** `compute/cassi_site_sample.glsl` (or a shared `#include`) exposing
  `site_coherence(vec3 wp)` / `site_phase(vec3 wp)` over the live `_ml_sites` +
  `_ml_psi_y/_ml_psi_i`, guarded so it only runs when `boxless_field` is on.
- **qhist** (`cassi_qhist.glsl`): when `boxless_field` PC flag is ≥0.5, read the boxless
  site sample instead of the grid trilinear. This is the primary physics-correctness
  reader (it's what re-fits the color band and the `p1/p99` spread).
- **instancer** (`cassi_instancer.glsl`): keep grid display; when `boxless_field` is on,
  drive the color *coherence/phase axis* from the boxless site sample too (accept the
  per-frame cost; report it). This is what makes the *picture* stop jumping when the
  envelope lags.
- **merge** (`cassi_particle_merge.glsl`): when `boxless_field` AND `particle_merge`
  are both on, the coherence gate (`q_ord`/`q_coh > φ⁻²`) reads the boxless site sample
  so merge correctness doesn't depend on the window. (Only relevant if the owner turns
  both on; gated and bit-identical otherwise.)

The default (`boxless_field = 0`) keeps every reader **exactly as today** — the toggle
is a hard no-op off (guarded branch, no zero-multiply), so the battery is bit-identical
by construction (pre-reg §5a).

## 5. Uniform-set / PC wiring notes

- The boxless readers need `_ml_sites`, `_ml_psi_y`, `_ml_psi_i` + `n_sites` in their
  sets. qhist and instancer currently bind only grid buffers; add the three site
  buffers as a new binding when `boxless_field` is on (or always, immutable, since
  they're always allocated and zero-cost when unread). `assert_layout` stays the gate.
- The site sample needs `n_sites` (already in the cell PC; add to the reader PCs as a
  dedicated slot — appended default 0, guarded).

## 6. Verification plan (pre-reg §6, unchanged)

1. Implement + wire (toggle off).
2. Parse-gate edited GDScript; glslangValidator the edited/added GLSL (**two-arg
   `atan(ei,ey)`, never one-arg `atan2`** — the rig's known silent-SPIRV trap).
3. Godot `--import`; cells battery arms + `assert_layout` (bit-identical default).
4. `boxless_field = 1` probe: a known coherent blob; move the probe's tracked window
   OFF the blob (simulating a lagging envelope); assert the boxless site sample still
   reads the blob's coherence (max |Δq| ≤ 1e-3 from the in-blob site value), while the
   grid trilinear (post-`%N` wrap) would return a wrong value. Record both.
5. Write `boxless_field_report.md`; owner sign-off before shrinking/dropping the grid.

## 7. Open items (recorded, not resolved at pre-reg)

- Per-frame instancer nearest-site cost (N_p·8192): defer spatial-hash-of-sites to a
  follow-up; report the measured cost in the report.
- Whether merge-in-boxless should be exercised (owner must enable both); the gate is
  additive and off-off by default.

## 8. Coherence-gated adaptive compute (owner proposal — recorded follow-ons)

Carina: "can we use coherence to optimize any of these algorithms?" The merge gate
already does q-filtering (`q > φ⁻²` prunes the search). The pattern generalizes to
"the computation spends its budget where the coherence is" — intelligence-as-steering
applied to the solver's own cost. Three hooks, in proximity order:

1. **Coherence-filtered boxless locate** (improves §3's brute-force nearest-site):
   low-q sites are voids whose psi ≈ 0; skip them (or gate the search by a q floor),
   or build a q-split site hierarchy (fine in high-q condensate, coarse in voids).
   Collapses the 8192-site read to the structured subset. Highest-value, closest to
   the change being shipped now.
2. **Coherence-adaptive Barnes-Hut θ(q)**: tighten the opening criterion in high-q
   condensate (where the force field is genuinely organized), loosen it in incoherent
   voids (coarse multipole fine) — fewer node evaluations exactly where the field has
   no structure. Principled, measurable (probeable against the bit-identical default).
3. **Coherence-gated steering/JFA cadence + q-weighted envelope centroid**: high-q
   cells move rigidly (phase-lock), so they stay valid longer — rebuild the mesh less
   there, more where q is low. And the boxless tracking envelope should follow the
   **coherent core**, not the raw particle cloud — a q-weighted centroid stops the
   envelope being dragged by stray void particles. Directly answers the owner's
   "doesn't adjust accurately" complaint at the source.

These are follow-up arms (not this change); each needs its own pre-reg. Recorded here
so the thesis framing ("coherence-gated adaptive compute = the field-AI thesis applied
to the solver") is captured in the project record.

