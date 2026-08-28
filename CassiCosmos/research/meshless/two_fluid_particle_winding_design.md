# Two-fluid winding on the particle doublet — Design (b)

**Status**: research design (owner-approved, "start b"; the goal is for the
simulator to simulate reality). Design-only — no `.glsl`/`.gd` changes yet.

## 1. The gap (why (a) isn't the full mechanism)

The meshless coherence-cluster depth probe (a) uses the solver's scalar per-
particle coherence `q_coh = ρ²/(ρ²+φ⁻²+ε²)` as the order parameter. That is a
real step toward multi-scale structure, but it **does not carry the winding**.
The theory (`foundations/qi-flow-double-helix.md`) is explicit that a particle
is a **standing wave of the doublet plus the winding that carries its identity**
(§"Matter as wound Qi"): the winding is the **phase sector** — the internal
SO(2) rotation of the doublet about the φ-line, with `θ = atan2(E_I, E_Y)`, and
the doublet's phase advances **π per cascade rung** (`P_∥ = 2`, §3.3). The
axial coherence current

```
J_z = R² ∂_z θ        (L3.2)
```

is coherence flowing *between scales* along the string axis — the thing that
couples rungs and closes the double helix. The (a) probe has no per-particle
phase, so it cannot represent `J_z` or the winding — only the amplitude-sector
coherence. **(b)** attaches the doublet + winding to the particles.

## 2. Theory equations to realize (frozen per the double-helix doc)

Per particle `i` carry the doublet components `(E_Yi, E_Ii)` (equivalently
`ρ_i = E_Yi+E_Ii`, `ε_i = E_Yi−φ·E_Ii`, `θ_i = atan2(E_Ii, E_Yi)`).

**Winding rate** (L"matter-as-wound-Qi", verified by `run_winding_rate_probe`,
gated by the openness):

```
dθ_i/dt = λ (1 − q_i) (ρ_i ε_i) / (E_Yi² + E_Ii²)
```

— the phase advances toward the φ-line from the excess ε_i, only while the
state is open `(1−q_i)`, and exactly vanishes on the φ-line (ε = 0).

**Coherence transport along the cascade** (L3.2): a particle's phase gradient
toward a neighbor at a different scale (rung separation Δn) transfers coherence
with the φ⁻¹-per-rung attenuation. The natural per-particle coupling is the
discrete `J_z`: for a neighbor pair at axial separation `δz` with phase
difference `δθ`,

```
J_ij = R_ij² (δθ_ij / δz_ij),   coupling ~ φ^{-Δn}
```

**Axial winding (the double helix)**: a particle belonging to a stack spanning
rungs accumulates `δθ = π·Δn/2` per `P_∥=2` cycle — the phase advances π per
rung, closing two turns per four rungs, etc.

## 3. Engine realization (concrete, on the real buffers)

Per-particle state currently in the engine (verified in
`compute/cassi_tree_gravity.glsl`, `compute/cassi_particle_merge.glsl`):

| engine state | buffer/slot | (b) extension |
|---|---|---|
| position, mass | `src[2i].xyz`, `src[2i].w` (20 B/particle) | — |
| coherence weight `g` (from q_coh) | in the tree force | recompute from the evolved doublet |
| per-particle `spin` | merge shader (persistent family) | **reuse for the winding doublet's L, or add θ** |
| field EY/EI | `_tl_psy`/`_tl_psi` + ρ grid | the per-cell field the doublet reads |

**Two concrete options.**

**(b1) Per-particle phase `θ_i` (minimal).** Add one float per particle (the
phase θ_i), evolved each physics pass by the winding rate above, with a
neighbor coupling `J_ij` computed in the tree walk (read the source's θ in the
same pass that reads its q_coh → weight `g`). The particle's coherence then
becomes phase-dependent: `q_sel` gains an **order term** `q_ord = 1/(1 +
φ²⟨|∇θ|²⟩/…)` — coherent phase-locked neighbors (small ∇θ, i.e. two-fluid
sound) bind; random-phase (decoherent) neighbors don't. This is the smallest
change that gives the winding substance: the double helix lives as a phase-
gradient structure on the particles, and `J_z` couples rung-separated neighbors
with φ⁻¹ attenuation.

**(b2) Full doublet per particle `(E_Yi, E_Ii)` (faithful).** Extend the
per-particle family with the two doublet components. The two-fluid RHS (the
shipped `cassi_two_fluid.glsl` terms, at the particle position) evolves them
each pass; the winding `θ_i` is derived (`atan2` — GLSL `atan(y,x)`, never the
forbidden `atan2`). The tree force reads the doublet for `q_coh`, `ε`, and the
`J_z` coupling; the merge gate's `q_sel = q_coh·q_ord` (already `Σ = EY+φEI`)
reads them directly. This is the faithful "the field IS on the particles" form.

**Recommendation.** Ship **(b1)** first — it is a one-float extension, it makes
the winding a real evolving degree of freedom, and it directly enables the
`q_ord` phase-coherence gate (closing the "phase-locked order vs loud noise"
distinction). Then extend to **(b2)** once (b1) verifies, because (b2) is
straightforward once the phase mechanism is in the engine. Both keep the
default-off additive-toggle rule and the battery bit-identical gate.

## 4. What (b1) verifies against (a)

- **The depth probe re-runs with per-particle phase**: does the φ-organized
  multi-rung cluster now hold its winding structure (θ gradient / `J_z` /
  `q_ord` order) longer with more rungs — the cascade-suppression signal that
  the scalar-q (a) version cannot show because it lacks the phase?
- **The sound/coherence test**: `c_s = h₀/dt` (subsonic gate) already couples
  to the ρ-wave; with θ the phase wave carries coherence and the subsonic gate
  becomes a phase-coherence statement.
- **The winding-rate check** against `run_winding_rate_probe`'s homogeneous
  arms: `dθ/dt = λ(1−q)ρε/M` must reproduce on the particle field (four-of-four
  homogeneous arms, the committed record).

## 5. Acceptance gate (frozen, same discipline as the engine battery)

1. Toggle-off **bit-identical**: `wind on = OFF` leaves the default battery
   (`verify_river_isotropy` anchors, etc.) unchanged (G57-style).
2. (b1) with a seeded phase gradient reproduces the winding rate to the
   homogeneous-arm record (rel. err on dθ/dt vs λ(1−q)ρε/M).
3. The phase-coherent cluster (small ∇θ core) holds structure longer than the
   same cluster with randomized initial phase — the winding is load-bearing.
4. Merge `q_ord` gate: phase-locked neighbors qualify, random-phase do not,
   at the frozen φ⁻² threshold.

**Relationship to (a)**: (a) is the amplitude-sector coherence (the dense
coherent core); (b1)/(b2) add the phase sector (the winding / `J_z` / `q_ord`).
The theory says the soliton needs both — the standing wave (amplitude) PLUS
the winding (phase). (b) is the half the (a) probe structurally cannot see.
