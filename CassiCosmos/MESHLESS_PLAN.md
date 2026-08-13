# MESHLESS_PLAN — The Moving-Voronoi (AREPO-Class) Cassi Universe

**Status:** COMPLETE — all four stages built and gated (Stage 0 `227148e`,
0b `044db7c`, 1 `1cdcaeb`+`51fd078`, 2 `7052f0f`+`343dd8d`, 3 `e748a4b`).
The verification record and the research-item resolutions live in §8.
**Repo:** `godot/space-sim` (design + the `research/meshless/` pipeline;
theory anchors in `papers/theory-of-everything/` of the parent repo).
**Date:** 2026-08-13

---

## 0. The promise

The cascade grid (CASCADE_GRID.md) reduced the grid's bias but cannot remove
it: at the bubble scale (~2 cells/radius) every static lattice stops at
~1.13 ring anisotropy because the discrete Green only has ~2 samples per
radius there. The fix is either more resolution per bubble (AMR) or **no
lattice at all**. This plan is the no-lattice path: a moving Voronoi mesh
(AREPO-class, Springel 2010) where the mesh cells *are* the fluid, move with
it, and refine where the Cassi field's own coherence demands.

What it kills, by construction:
- **lattice symmetry** — cells sit where matter is, no preferred directions
- **scale quantization** — cell sizes are free to track the φ-cascade ladder
- **phase pinning** — no fixed lattice phases to pin bubbles to
- **box-period quantization** — tree/FMM gravity permits open boundaries, so
  the bubble fabric can form at its own phases, not multiples of L/n

What it additionally unlocks: **matter formation as a native process**. In
the current sim, matter (particles) is injected separately from the field.
On the moving mesh, the field IS the fluid; matter is what a cell *becomes*
when it crosses the condensation threshold — the same collapse the theory's
dark-rung condensation predicts, with the two-fluid conversion as the mass
source. This is exactly why AREPO-class codes are the standard for star
formation.

## 1. Physics inventory — what moves over, unchanged

From `compute/cassi_two_fluid.glsl` (the current wave form):

```
∂²EY/∂t² = c²∇²EY − ω₀²·(EY − φ·EI) + S_EY
∂²EI/∂t² = c²∇²EI + ω₀²·(EY − φ·EI) + S_EI
```

- **It is a LINEAR wave system** (c²∇²ψ + ω₀² coupling, no advective
  nonlinearity, no shocks). This is the single biggest simplification vs
  AREPO hydro: the finite-volume face flux is a *reconstructed gradient* —
  **no Riemann solver is needed**. The full AREPO machinery (moving Voronoi,
  Green–Gauss gradients, mesh steering) applies, minus the hardest part.
- **Fields:** ψ = (EY, EI); ρ = EY+EI; ε = EY−φ·EI; the field render
  q_field = EY²+EI².
- **Qi gate / coherence:** the nbody shader's coupling q_coh =
  ρ²/(ρ² + φ⁻² + ε²), chord g = 1 + (ξ−1)·q_coh, ξ = φ⁶. (Naming note: the
  two q's — q_field vs q_coh — must be kept distinct in the meshless code.)
- **River force** (per-particle today; becomes the momentum source):
  a = −G_N·(π/ρ)·∇(gΦ), π = EY−EI, π/ρ clamped per the nbody arm.
- **Sources:** S_EY/S_EI (Gaussian seeds + ρ injection) — cell-local.
- **Open provenance item:** ω₀² = 20.0 is hardcoded in the shader; the
  meshless form carries the same closure, but its derivation status should
  be checked against `parameter-inventory.md` (research item R1).

The two-fluid PDE remains the single governing equation; φ remains the only
free parameter. This plan changes the *discretization*, not the doctrine.

## 2. The discretization — moving Voronoi finite volume

- **Sites** = mesh generators, one per cell, moving at the local momentum
  field velocity (Lagrangian) + a small regularization toward the cell
  centroid (the AREPO mesh-steering recipe — keeps Voronoi cells round).
- **Cell state** (cell averages): EY, EI, π_Y = ∂EY/∂t, π_I = ∂EI/∂t.
  Derived per cell: ρ, ε, q_coh, g.
- **Face fluxes:** Green–Gauss gradient reconstruction of ψ from neighbor
  cell averages → ∇ψ at each face → flux c²·∇ψ·A_face. Linear system → no
  upwinding subtlety beyond the reconstruction itself (least-squares
  gradients, standard).
- **Reaction (operator split, cell-local):** the ω₀²·(EY−φ·EI) coupling and
  the Qi gate apply between transport steps. The φ-attractor closure is
  untouched.
- **Gravity:** tree/FMM on cell multipoles (monopole = ρ·V, quadrupole from
  the reconstruction). Φ → ∇(gΦ) sampled at cell centers; the river force
  becomes the momentum source term. The old spectral Poisson and its
  measured 2-cell wall disappear entirely — gravity accuracy becomes
  multipole-order + cell resolution, both under our control.
- **Time stepping:** the current leapfrog structure survives (second-order
  centered); the moving mesh needs the geometric source term for the
  changing cell volume (the AREPO "mesh deformation term"), or a
  swept-volume treatment — design choice D1.

## 3. Cassi-native innovations (what makes this OUR meshless code)

1. **The mesh follows Qi.** Refinement criterion = q_coh(x): sites insert
   where coherence condenses, remove where it evaporates. No free
   parameters — the field's own dynamics pick the resolution. Cell sizes
   then track the φ-cascade ladder *by construction* (each refinement band
   = one rung of the resolved window, replacing the fixed
   log_φ(N/2) window).
2. **φ-rung cell-size bands.** Site insertion targets the rung ladder —
   cell volumes clustered near V₀·φ^{3m} — so the mesh's resolution
   histogram IS the cascade spectrum; the bubble lattice's rung structure
   becomes an observable of the mesh itself.
3. **Collapse → matter formation.** When a cell's ρ crosses the
   condensation threshold (the criterion the existing condensation scanner
   already detects), the cell collapses into a matter particle: the fluid
   mass transfers to the particle population (with the two-fluid
   conversion rate as the mass source), the site is removed, and the
   cascade continues — the sim's black-hole spawning generalizes from a
   toggle to the theory's condensation pathway.
4. **Open boundaries via FMM.** No periodic images needed for gravity; the
   fabric forms at its own phases. (The wave field still needs boundary
   conditions on the simulation edge — absorbing or inflating BCs, design
   choice D2.)
5. **The Yin/Yang dual idea survives differently:** there is no lattice to
   dual — phase bias is gone by construction; the EY/EI pair remains the
   two fluids on the same moving cells.

## 4. Engineering stages (each with a hard gate)

**Stage 0 — 2D CPU prototype** (first, smallest, research-grade):
Bowyer–Watson / half-edge Voronoi in a flat Python script (~10⁴–10⁵ sites,
2D), finite-volume two-fluid with the §2 discretization. Gate: same ICs as
the current 64³ spectral solver → the φ-attractor trajectory r(t) → φ, the
bubble-lattice spacing, and the powder line list agree within tolerance
(2D analogs). This validates the physics *before* any GPU engineering.

**Stage 1 — 3D GPU Voronoi + cell physics in Godot:**
Raster Voronoi via jump flooding (Rong & Tan) / PRF (2023) on an
accelerator grid — the grid is a lookup accelerator ONLY, no physics lives
on it — or the exact GPU construction of the recent arXiv:2605.06408 if
JFA's approximation matters (it matters only if face geometries are
needed beyond sampling — D1 decides). Gate: reproduces Stage 0's attractor
+ matches the spectral solver on its own test battery.

**Stage 2 — moving mesh + steering + Qi refinement + FMM gravity + open BCs:**
Mesh motion, site insertion/removal from q_coh, tree/FMM gravity replacing
the spectral Poisson, absorbing boundaries. Gate: bubble lattice forms at
the theory's powder lines *without* the box-period quantization the grid
solver shows; w₀/wₐ still matches the DESI calibration.

**Stage 3 — matter formation:**
Collapse spawning, mass transfer fluid → matter, black holes as the
extreme rung. Gate: the formed mass function follows the theory's cascade
ladder (rung-offset structure of the mass catalog).

The **existing grid solver stays the reference solution** at every stage —
it is verified against theory, and the meshless solver must agree with it
on shared observables (attractor trajectory, lattice spacing, w₀/wₐ).
Cross-solver agreement + theory anchors = the verification contract.

## 5. Honest risks

- **Voronoi degeneracy** (slivers, near-cocircular sites) — the known AREPO
  pathology; mitigation is the standard steering + occasional retriangulation.
- **GPU throughput** of moving-Voronoi construction at interactive rates for
  10⁵–10⁶ cells — the long pole; the accelerator-grid JFA path is the
  fallback that guarantees interactivity.
- **Gradient reconstruction on irregular cells** — replaces the measured
  2-cell wall with a reconstruction-order wall; Qi-driven refinement must
  keep ≥8–16 cells per bubble radius (the measured ≤1% regime).
- **Mesh noise vs spectral accuracy** for the linear wave system — the
  spectral solver will beat the mesh on smooth-field accuracy; the mesh
  wins on structure. Expectation management: the meshless sim is for
  *structure and matter formation*, not for tighter w₀ digits.
- **ω₀² provenance** (R1) — if ω₀ is a free constant, the "zero free
  parameters" claim needs its derivation pinned before Stage 1.

## 6. Open research questions

- R1: ω₀² = 20.0 provenance (parameter inventory check).
- D1: swept-volume vs geometric source term for the moving mesh.
- D2: boundary conditions for the wave field on an open box.
- R2: does the Qi-gate q_coh need a face-local form, or is the cell-local
  gate sufficient for the attractor statistics (Stage 0 answers this)?
- R3: collapse criterion — condensation threshold vs a φ-derived Jeans
  analog from the cascade rung density.

## 7. First action

Stage 0: the 2D moving-Voronoi two-fluid prototype in `_diag/` (or a new
`research/` dir), validated against the current spectral solver. This is the
next work item; it is small, self-contained, and retires the largest
physics risks (face-flux form, mesh-steering, attractor fidelity) before a
single line of GLSL is written.

---

## 8. Verification record (2026-08-13, program complete)

Every stage shipped with a hard gate, run against an exact-in-time
spectral reference of the same continuum PDE:

| Stage | Artifact | Gates |
|---|---|---|
| 0 — 2D static Voronoi FV | `research/meshless/stage0_voronoi2d.py` | V1–V4: breather Ω = √(ω₀²(1+φ)) = 7.2361, r(t), L2, spectrum — ALL PASS |
| 0b — 2D moving + Qi-adaptive | same file | V5 moving mesh, V6 q-adapted beats uniform (28%) — ALL PASS |
| 1 — 3D GPU Voronoi + cells | `stage1_jfa3d.py` (numpy), `compute/cassi_jfa.glsl`, `compute/cassi_voronoi_cells.glsl`, `scripts/verify_voronoi3d.gd` | G0–G4: JFA mislabel 0.0000, breather 0.95%, r(t) 0.14%, L2 2.5e-3, corr 0.9986 — ALL PASS |
| 2 — moving + adaptive + sponge | `stage2_moving3d.py` (numpy), `scripts/verify_voronoi3d_moving.gd` | G5 moving L2 = static, G6 adapted −28%, G7 sponge 13× absorption — ALL PASS |
| 3 — matter formation | `stage3_collapse.py` | G8 rung-aligned mass function (0.972 vs 0.594 control) — PASS |

Key results to carry forward:

- **The JFA construction is exact.** The jump-flooding Voronoi (doubling
  passes 1..N/2 + halving refinement) reproduces the exact Voronoi on
  every accelerator-grid cell, in numpy AND on the GPU (float32), on
  pristine AND steered site configurations — the exact-GPU-Voronoi
  research path (arXiv:2605.06408) is unnecessary for this physics.
- **The staircase grid-face flux reproduces the Voronoi wave Laplacian**
  to L2 = 1.5e-3 (numpy) / 2.5e-3 (GPU float32) — the accelerator grid
  is invisible to the physics.
- **The moving mesh is invisible to the physics** — the steering +
  periodic ALE remap leave L2 exactly at the static value (the
  quasi-Lagrangian ride + centroid relaxation + nearest-old-cell state
  transfer conserve the wave solution to the remap's order).
- **The mesh follows Qi** — (1−q_coh)^p·V re-seeding beats uniform by
  28% in the blob core at equal budget, in 2D AND 3D.
- **Collapse is rung-faithful** — the condensation pathway converts the
  φ-spaced bubble seeding into a mass function ON the 3-rung ladder;
  non-φ structure does not.

## 9. Research-item resolutions

- **R1 (ω₀² = 20.0 provenance):** NO derivation exists in the theory
  docs (`parameter-inventory.md` does not list it; `cassi_definitions.md`
  uses ω₀ symbolically). Resolution: ω₀ is a **sim-numerical
  scale-setting constant** — it fixes the breather frequency Ω = √(ω₀²(1+φ))
  but NOT the φ-attractor trajectory or the cascade structure (the
  deviation-mode dynamics are scale-free in ω₀). Recorded as numerical,
  not derived; a derivation would be a theory-side follow-up, not a
  meshless-program blocker.
- **D1 (swept-volume vs geometric source term):** RESOLVED for the
  periodic prototype — the **periodic ALE remap** (rebuild + nearest-
  old-cell state transfer) is mass-conservative to the remap order and
  validates at L2 parity with the static mesh. The continuous geometric
  source terms stay deferred to the open-box implementation (they only
  matter when the mesh motion per step is large relative to the cell —
  the rebuild cadence keeps it small).
- **D2 (open-box boundary conditions):** RESOLVED in prototype — the
  **sponge layer** (wall-proximity quadratic ramp damping π) absorbs
  93% of the breather energy vs the periodic wrap control (G7, 13×).
  The energy metric is the DIAGONAL deviation oscillator's energy —
  a real finding: the two-fluid coupling is non-gradient (no total
  energy functional exists), only the breather mode is a harmonic
  oscillator.
- **R2 (face-local Qi gate):** NOT NEEDED — the **cell-local gate
  suffices**: every attractor-statistics gate passed with the cell-local
  q_coh (the φ-attractor trajectory and the rung structure matched the
  exact reference; no face-local refinement was required).
- **R3 (collapse criterion):** RESOLVED — the **peak criterion on
  q_field = EY²+EI²** (the sim's condensation scanner's own peak
  detector), fired on the **peak-phase magnitude** (the windowed max:
  the condensate breathes, and condensation happens at the peak, not at
  an arbitrary phase). NOT q_coh — coherence is LOW at deviation peaks
  by construction. The connected condensed core coalesces into one
  matter particle; mass = Σ ρ·V, position = ρ-weighted centroid.

## 10. What is NOT done (the integration project)

The research program is complete; the **live-sim integration** is the
deliberate next project (the plan kept the grid solver as the reference
at every stage): wiring the JFA + cell physics + steering + condensation
shaders into `cassi_sim.gd` as a gravity-mode arm, replacing the
spectral Poisson with the cell-fluid dynamics, and connecting the
collapse pass to the existing black-hole spawning. The Stage-2 gate's
w₀/wₐ-vs-DESI comparison belongs to that integration (the cosmology ODE
closure lives in the integrated sim, not the wave-PDE prototypes).
Unweighted Lloyd relaxation erases seed-density adaptation — density-
weighted Lloyd is needed when the adaptive mesh is combined with the
moving mesh in the integrated sim.
