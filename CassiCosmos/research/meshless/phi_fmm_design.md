# φ-Native FMM — can the tree carry the cascade?

**Status**: research design + numpy prototype (`stage7_phi_fmm.py`), gates
G42/G43/G44. Design-only for the sim — no `.glsl`/`.gd` changes.

## The question

The current tree (stage5_fmm.BHOctree, wave 2 GPU) is a **binary/standard
octree**: every level halves the box (`half → half/2`), so its multipole
ladder has level radii `h·2⁻ᵈ` (powers of 2). The Cassi framework is built
on φ-rung cascades (φ⁶ coupling, CASCADE_GRID.md). This doc + prototype
asks: **can the tree itself carry the cascade** — multipole levels spaced
at φ-rungs and an opening criterion set by the de-resonance principle —
instead of the standard binary octree?

Two concrete proposals, both prototyped:

### (a) φ-spaced level tree (box fractions φ⁻¹, φ⁻², φ⁻³ per axis)

A Barnes–Hut tree whose node box half follows

```
half_d = half_0 · φ⁻ᵈ        (φ-rung levels: h, h/φ, h/φ², h/φ³, …)
```

A node of half `h` splits into **8 children**, each of half `h/φ` (=
`h_{d+1}`), centered at the 8 positions `c + s·h·(1 − 1/φ)` for `s∈{±1}³`.
Because `2/φ = 1.236 ≠ 2`, the 8 children **overlap** (their total volume
`8·(2h/φ)³ = 8·(1.236)³·h³ ≈ 15.1·h³` exceeds the parent `(2h)³ = 8h³`).
Sources are assigned to the **nearest** child center (a Voronoi-style
partition over 8 overlapping centers).

**Honest integer/hashing consequence (documented)**: the φ-contraction is
**incommensurate with integer/Morton subdivision** — a power-of-2 Morton
key interleaves bits per octant (2-bit/axis level), which is exact ONLY for
binary (half) splits. At φ⁻¹-per-axis splits there is no finite-bit octant
code, so:
* the φ-tree cannot use Morton-key contiguous-range octree construction;
* its children overlap, so there is no exact space partition (a source's
  assigned child's box may not strictly contain it — the multipole is then
  expanded about the child COM, the same order of error as a source at a
  child's edge);
* a **rational approximant** φ⁻¹ ≈ 5/8 (the Fibonacci convergent, 0.625 vs
  0.618) restores integer-ish levels at the cost of re-introducing lattice
  commensurability (measured in G43 as the "rational φ" arm).

### (b) φ-irrational / de-resonance opening criterion

In a standard 2-spaced tree, the opening shells live at `sep ≈ h·2⁻ᵈ/θ`.
On a lattice-symmetric source (G43), a target sits at separations that are
**exact multiples of the level shelf sizes** — so multiple levels "fire"
in coherent phase with the lattice → the classic force anisotropy along
grid lines. The de-resonance principle proposes an **irrational level
ratio** so no target separation is commensurate with multiple level shells:

```
open(node, target)  ⟺  half_d / |target − COM| > θ_eff
θ_eff = θ · (1/φ)^fract( log_φ( |target−COM| / h ) )     (proposal)
```

Concretely and testably: the **φ-spaced level radii themselves** are the
de-resonance — consecutive shells sit at an irrational ratio φ, so a target
distance cannot be an exact multiple of two different φ-powers (φ is
irrational; `r₁/r₂ = φᵏ` with integer k≠0 is impossible for k≠0,1
multiplicatively incommensurate). We TEST whether the φ-tree's force is
less lattice-anisotropic than the standard octree (G43). A second, blended
arm applies a mild level-index θ modulation `θ_eff = θ·(1+0.5·sin(2π·d·φ))`
to a STANDARD octree as a control ("θ-ℵ") — probing whether the de-resonance
can be injected into the opening without φ-geometry.

## Gates (stage7_phi_fmm.py)

* **G42** — φ-tree vs direct O(N²) median force error **at equal interaction
  budget**. Report which of {standard octree, φ-tree (irrational),
  φ-tree (rational 5/8)} wins at the same mean interactions/target. A null
  (standard wins) is honest — the φ-tree's overlapping children cost
  accuracy per node.
* **G43** — force anisotropy (ring metric) on a **lattice-symmetric source**:
  sources on a simple-cubic lattice, targets at a fixed radius ring; the
  θ-average of |a| / |a|_min is the anisotropy. Measure for the standard
  octree vs the φ-tree. The whole POINT is less grid bias — measure it.
* **G44** — energy drift in the G15 bound-cluster test (truncated Plummer,
  ~12 crossing times, θ=0.3) with the φ-tree ≤ the standard octree's, or
  honestly reported.

## Status / measured result (stage7_phi_fmm.py run)

The three gates run and report honestly (seed 20260813):

| Gate | Octree (2-spaced) | φ-tree (irrational) | φ-tree (5/8) | Verdict |
|---|---|---|---|---|
| G42 median force err @ equal budget (~270 int/target) | θ=0.406 → **3.12e-3** | θ=0.937 → 3.17e-3 | σ-budget-infeasible (saturates 320) → 2.60e-3 | **null** — φ-tree ties the octree; no accuracy-per-interaction win |
| G43 lattice anisotropy (729-point cubic lattice, ring r=1.5) | 65.41 (dir err 0.59) | **27.11** (dir err 0.063) | — | **support** — φ-tree 2.4× less grid-biased, 9× more accurate |
| G44 energy drift (G15 bound cluster, N=600, ~12 crossing times) | **0.0728** | 0.0839 | — | **honest fail** — φ-tree slightly worse |

**Interpretation.** φ-rung level spacing DOES deliver its advertised benefit —
the de-resonance principle works: on a lattice-symmetric source the φ-tree's
force is dramatically less anisotropic (2.4× lower max/min, 9× lower
directional error) because its irrational level shells do not resonate with
the cubic grid. But the φ-tree does NOT win on accuracy-per-interaction
(ties at equal budget — the overlapping nearest-center children cost the
accuracy the φ-spacing might otherwise give) and is ~15% worse at conserving
energy in the bound-cluster test (again the child overlap). 

**Bottom line for the sim**: the current wave-2 binary octree stays the
kernel; φ-spacing is attractive only where grid/lattice bias dominates (a
lattice-symmetric internal structure), at which point a dedicated
de-resonance opening on the EXISTING octree may capture most of the benefit
without the overlap overhead — a follow-up arm (θ-ℵ, proposed in section
(b)) worth prototyping before any φ-geometry lands in a shader.
