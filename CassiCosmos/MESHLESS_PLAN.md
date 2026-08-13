# MESHLESS_PLAN — The Moving-Voronoi (AREPO-Class) Cassi Universe

**Status:** Research program design — no code yet. Committed as the roadmap for
the meshless redesign.
**Repo:** `godot/space-sim` (design lives here; theory anchors live in
`papers/theory-of-everything/` of the parent repo).
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
