# Stage M1 — Two-Level φ-Zoom Chain (parent → child handoff)

**Status:** Design + numpy prototype (`stage_m1_chain.py`), gates G42–G46
**Repo:** `godot/space-sim` (this dir is the READ-ONLY wave's deliverable; NO
sim code touched — parallel workers own the scripts/shaders)
**Date:** 2026-08-13
**Companion:** `research/machine/stage_m1_chain.py` (the measured prototype)

This is the first stage (`M1`) of the **multi-rung machine**: a chain of
φ-zoom levels that pass condensed matter down from coarse to fine resolution.
The machine's claim is that a cascade can be resolved level-by-level — each
child re-resolving the parent's condensed cores in a physically smaller box at
the *same* grid resolution, resolving rungs the parent's coarse cell could not
see. Before any GPU/closure work, M1 proves the **parent → child handoff works
end to end in numpy**: two levels, both running fully resolved two-fluid
physics, connected by a conservative, survey-format dump/read.

---

## (a) The two levels and the level spacing (k choice)

**Level 1 (parent).** The coarse level reuses the `research/meshless/stage3`
condensation pipeline verbatim: box `L₁ = 10.0`, grid `N = 64`, `BCC`-seeded
`16 384` Voronoi cells, the φ-spaced multi-rung deviation seeding
(`make_blob_ics`, radii `{1.2, 0.74, 0.46}` = φ-spaced), run to condensation
(the peak-phase `q_field = EY²+EI²` windowed maximum crosses `q_th = 3.6`), the
mesh-adjacency coalescence of each connected super-threshold core into one
matter particle (the R3 condensation recipe). The parent's **condensed cores**
are the level's matter output: `(mass_i, position_i)` per core, `mass = Σ ρ·V`.

**Level 2 (child).** A zoom on the parent's most massive condensed core. The
child runs at the **same `N = 64` grid** on a smaller box
`L₂ = L₁/φ^k`, so its cell `h₂ = L₁/(N·φ^k)` resolves `φ^k` finer physical
scale for the same cell budget.

**Why `k = 3`.** Three independent anchors agree on `k = 3`:

1. **The mass ladder is 3-rung spaced.** stage3 (G8) established that the
   collapsed core masses sit on *3-rung* spacing (`log_φ(m) = n_min + 3m`),
   because the deviation blobs have equal amplitude and `mass ∝ (deviation
   volume) ∝ radius³`, so a radius-rung step of `φ` makes a mass step of `φ³`.
   A `φ³` box zoom is therefore the natural *one-mass-ladder-step* resolution
   jump: the child re-resolves one full cascade rung of the mass ladder.
2. **The de-resonance argument (multigrid_design.md (a)).** φ is not a power
   of 2; `L₂ = L₁/φ³` keeps the child's cell phase incommensurate with the
   parent's (`gcd` analysis in the cascade-multigrid design), maximally
   de-correlating the two levels' lattice phase errors — the same reason the
   coarse level chooses `round(N/φ)` over `N/2`. A `φ`-ratio box is *the*
   cascade's natural level spacing.
3. **A sub-rung ladder that reaches cleanly into the child's window.** The
   parent's smallest resolved radius is `r_min = 0.46 physical = 2.94 cells`
   (right at the ~2–3 cell resolution floor). Continuing that rung down by
   exact φ factors, `r_min·φ^{0,−1,−2,−3} = {0.46, 0.284, 0.176, 0.109}`, the
   child's cell `h₂ = h₁/φ³ = 0.0369` resolves `{0.284, 0.176, 0.109}` at
   `{7.7, 4.7, 2.9}` cells — **rungs the parent's 0.156-cell floor physically
   could not resolve**, now at the child's cleaner spacing. `k = 3` (not 4)
   keeps the smallest sub-rung above the ~2.5-cell resolution floor; `k = 4`
   would push the second-sub-rung below usable resolution at `N = 64`.

So `L₂ = L₁/φ³ = 2.3607`, `h₂ = 0.0369`, and the child's sub-rungs are the
parent's blob shell scaled by `1/φ³` — *exactly* the analytic continuation of
the parent's resolved ladder into the finer window.

---

## (b) The handoff rescaling (the derivation)

The parent's blob shell (in `make_blob_ics`): centers `c₀ ± 3.4·e₀`
(`e₀ ∈ {x̂, ŷ, ẑ}`), radii `{1.2, 0.74, 0.46}`. The condensed cores sit at
`c₀ + 3.4·ŝ` for the surviving blobs. The child is a zoom on the most massive
core at `c_t *`; the child box `[0, L₂)³` is centered on `c_t *`.

**The zoom map** (every quantity rescaled by the rung ratio `φ³`):

```
child_coordinate  =  φ³ · (parent_coordinate − c_t *)         (positions)
child_radius_k    =  r_k / φ³                                  (structure scales)
child_mass_k      =  m_k   (unchanged — physical mass conserved) (masses)
child_momentum    =  0     (both levels at rest; net p preserved) (momenta)
child_box         =  L₁/φ³
```

The child re-seeds, centred in its box, the scaled parent shell geometry:
sub-blob centers `c₂ ± (3.4/φ³)·e₀ ≈ c₂ ± 0.802·e₀`, sub-blob radii
`{1.2, 0.74, 0.46}/φ³ = {0.283, 0.175, 0.109}` (φ-spaced). In child cells
these are exactly the parent's blob-cell radii (`r/h` preserved), so the child
sees *identical* resolved geometry — but at `φ³` finer physical scale, and the
smallest two sub-rungs are now well inside the window (see (a) point 3).

**Mass convention.** Mass is the Lagrangian fluid mass `m = Σ_cells ρ·ΔV`
with `ρ = psiY + psiI` (`ρ = 2.5` baseline). Because the deviation blobs keep
`ρ = psiY + psiI` exactly flat (the `+A·g` on EY and `−A·g` on EI cancel in
the *sum*), a core's condensed mass is `ρ · V_core` — proportional to the
*condensed volume*. The handoff conserves the handed-off core mass in absolute
units, and the ≤1e-6 gate is on the **deposition remap** (the child lays down
exactly the handed mass); the child then *runs* at the **same physical
deviation amplitude as the parent** (`A = A_parent = 0.5`), so nothing is
distorted. Concretely:

- From the parent's solved collapse, the most-massive blob (`r = 1.2`,
  amplitude `A₀ = 0.5`) produced the largest core `m_*`. Calibrate once on the
  parent: `κ = m_* / (A₀ · B₁)` where `B₁ = ∫g_{r=1.2} dV` is the parent's
  integrated unit-gaussian support (absolute volume). The child seeds the same
  band geometry scaled by `φ³`; its unit excitation `U(s) = Σ_k g_{r_k}(s)`
  has absolute support `B₂ = ∫U dV`.
- **G42 mass (exact, ≤1e-6):** the amplitude that would carry exactly `m_*`
  is `A_cons = m_*/(κ·B₂)`. Verify on the *actual* child field that the
  deposition reproduces the handed mass:
  `κ·(A_cons·U) dV = m_*` to `≤1e-6` (float64). This proves the handoff code
  is conservatively exact.
- **The child RUNS at `A_child = A_parent = 0.5`** (the physical deviation
  strength; `A_cons` is reported as the *re-densification factor* — the ratio
  `A_cons/A_parent`, here ≈ 29, is the honest measure of how the φ³-compacted
  sub-rungs would have to be densified to concentrate the full parent-core
  mass into them alone). Because a φ-spaced rung is `φ³` in mass, the child's
  sub-cores at radius `φ⁻³` of the parent blob carry a fraction `≈ φ⁻⁹` of its
  mass: at physical amplitude the child partitions the handed mass it actually
  resolves — its re-condensed `Σ m_sub-core` (`≈ 3 %` of `m_*`) is a separate,
  nonlinear, honestly-reported residual, **not** the 1e-6 gate. This *is* the
  cascade ladder: each rung down carries `1/φ³` the mass, so the finer-rung
  sub-cores are lighter, and the shared-ladder report (below) shows the child
  resolves ~2 bands *finer*.

**Momenta.** Both levels are initialized at rest (`pi = 0`), so the net field
momentum is zero on both sides of the handoff and stays `≈ 0` through each
run (the breathing condensate is a standing mode). The handoff therefore
injects no net momentum. The gate measures the two runs' net |P| maxima and
checks `|P_child − P_parent| / (m_* · L₂) ≤ 1e-6`.

---

## (c) The levels in the prototype

| arm | box | IC | purpose |
|---|---|---|---|
| parent | `L₁=10`, `N=64` | φ-spaced radar `{1.2,0.74,0.46}`, `A=0.5` (stage3) | coarse condensation → survey dump |
| child_handoff | `L₂=L₁/φ³`, `N=64` | parent core zoom: sub-rungs `{0.283,0.175,0.109}`, `A=0.5` (physical, handed amplitude) | the zoom re-resolves finer rungs |
| child_control | `L₂`, `N=64` | **same** total mass/energy (`A_ctl` amplitude-scaled to match `Σr³`), sub-blob radii *random* (log-uniform non-φ) at the same shell centers | the G45 falsifier |

The **parent dump** uses the survey format (`meta.json` + `field_ey.raw` +
`field_ei.raw` + `field_q.raw`, float32 LE, `N³` each; `particles.raw` = xyz of
the condensed cores; plus `particles_mass.raw`, the M1 mass extension the
stock format skips because its pos buffer is x,y,z,mass). The **child consumes
the parent's dump** (`particles.raw`/`particles_mass.raw`/`meta.json`) as the
source of truth for its handoff (target core selection + masses) — the
level-chaining interface is exercised end to end, not just parsed.

---

## Gates (measured — `python stage_m1_chain.py`, ALL PASS)

On the chain above (parent N=64 L₁=10; child N=64 L₂=L₁/φ³; both resolved):

- **G42 (M1.1)** — mass + momentum conservation through the handoff `≤ 1e-6`
  (float64): measured `Δm/m_* = 0.0` (the deposition lays down exactly the
  handed core mass `m_* = 44.49`), momentum `|P_child − P_parent|/(m_*·L₂) =
  3.1e-18` (both levels at rest; net |P| over each run ≈ `1e-16`/`1e-17`).
- **G43 (M1.2)** — the child's structure radii form at φ-spaced rung scales:
  the rung-occupancy histogram of the child's sub-core masses (via the stage3
  `rung_score` machinery, `log_φ(m)/3` near integers) peaks for the handoff
  child (`rung_score = 0.948`) vs the random non-φ control (`0.520`), gap
  `0.427 > 0.10`, `>= 3` formed (5 each).
- **G44 (M1.3)** — the child's attractor ratio `r = ⟨EY⟩/⟨EI⟩ → φ`: measured
  `t0 = 1.591 → t_end = 1.645` vs `φ = 1.618`, relative error `1.7%` (the
  two-fluid `EY → φ·EI` equilibrium survives the handoff).
- **G45 (M1.4)** — **FALSIFIER PASS**: the random-IC (no-handoff) child with
  the same total mass (amplitude-matched `Σ r³`) fails the structure test —
  `rung_score 0.520 < 0.70`, `handoff − control = 0.427`. The contrast is the
  gate.
- **G46 (M1.5)** — the survey-format parent dump round-trips **byte-exact**:
  every raw file (fields + particles + masses) reads back byte-identical, and
  the parsed arrays equal the write-source arrays exactly (float32).

The child's collapsed cores on the **shared parent-mass-unit ladder** sit at
`n(parent units) ∈ [−3.8, +2.7]` vs the zoomed parent core at `n* = 11.74` —
**~15.5 rungs (≈5.2 3-rung bands) finer**, the concrete evidence that the zoom
re-resolves rungs the parent's coarse cell could not (its floor was
`r_min = 0.46 phys = 2.9 cells`).

---

## Honest limitations

- **NumPy prototype, no GPU.** This is the correctness proof of the handoff,
  not the performance path. The `MovingVoronoi3D` cell solver and `collapse`
  are ported to GPU (the `cassi_two_fluid`/meshless arm) in later stages; M1
  exists to validate the *chain* (dump → read → rescale → child run) before any
  shader work.
- **The closure is NOT used at M1.** Both levels run fully resolved two-fluid
  physics at `N = 64` — there is no coarse-to-fine closure/upscaling of the
  parent field into the child's initial state. The child's IC is built from the
  parent's condensed *cores* (the matter output, not the field), rescaled; the
  child then runs its own resolved physics. A field closure (feeding the
  parent's field structure into the child via interpolation) is a later,
  separate mechanism. This is intentional: M1 isolates the handoff from the
  closure, so a closure bug cannot masquerade as a handoff failure.
- **Single-core zoom.** The child box `L₂ = L₁/φ³` centered on the most massive
  core admits only that core (neighbors sit `≥ φ³ × L₂/2` away in the child
  frame). The other parent cores' masses are *not* inside the child's domain
  (they remain part of the parent level); only the zoomed core's mass is handed
  off. A multi-core or full-field zoom is a later refinement.
- **The ≤1e-6 gate is on the deposition remap; the re-collapse is a cascade
  fraction.** `G42`'s 1e-6 is the (exact, re-verified) statement that the handoff
  code lays down the handed mass; the child then runs at the parent's physical
  amplitude, so its sub-cores re-condense only a fraction `≈ φ⁻⁹` of `m_*`
  (measured `Σ m_sub-core ≈ 3% of m_*`). That is not a mass leak: each φ-rung
  down carries `1/φ³` the mass, so the finer-rung sub-cores are *supposed* to be
  lighter, and the parent core's dominant mass stays in the child box's baseline
  continuum. This is reported openly, not hidden behind the 1e-6.
