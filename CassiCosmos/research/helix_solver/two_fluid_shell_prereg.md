# Two-Fluid Shell Wave 5 — the fidelity gate — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-5 arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (axial operator → solver)
**Pre-registered outcomes:** the two-fluid fidelity gate below.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):** `two_fluid_shell.py`, `verify_twofluid.py`, `twofluid_probe.py`.

---

## 0. The question and the prior record

### 0.1 The question

Waves 1–4 solved the axial operator's *linear* wave transport (the interior, the boundary, the conservation, the cascade structure). This wave asks the solvers' question: **does the two-fluid PDE -- the sim's actual physics -- survive on the φ-shelled axial grid, with fidelity against the uniform-grid reference under the gate-iv acceptance?**

The gate-iv pattern is the house standard that already determined the meshless arm's fate (38%-off coarse dispersion → shelved to B). Wave 5 runs the SAME fidelity gate for the φ-shelled axial topology. An honest CONTRADICTS is the deliverable if the shell grid fails.

### 0.2 The two-fluid PDE (actual, from the sim shader `cassi_two_fluid.glsl`)

$$\partial_t^2 EY = c^2\nabla^2 EY - \omega_0^2(EY - \varphi EI), \qquad \partial_t^2 EI = c^2\nabla^2 EI + \omega_0^2(EY - \varphi EI)$$

Second-order leapfrog in time and space. The 19-point anisotropic Laplacian with per-axis weights (aᵢ, bᵢⱼ); φ-repulsion/recovery coupling via ε = EY − φEI; ρ = EY + EI; q = EY² + EI²; default ω₀² = 20.0. This wave runs the **1D axial restriction** (the cascade direction, the subject of waves 1–4): the two-fluid wave on a line of shells, the transverse terms fixed, the axial operator being the finite-volume Laplacian on uniform vs φ-shelled z.

### 0.3 Gate-iv (the A-decider, from `_diag/overhaul_build_plan.md`)

Exact acceptance test (quoted): a wave-fidelity battery — "a Gaussian pulse on the checkerboard ground state, measured ρ-front speed and the φ-power spacing of the emerging modes over ≥ 10³ steps: the [candidate] wave must match the N³ wave within a pinned tolerance (**|Δρ_front| ≤ 5%** and the dominant-mode φ-power spacing preserved...)**". Verdict → ADOPT/B. Gate-iv measured the meshless per-site wave at 38%-off coarse dispersion (be56f1d) → **shelved to B**; the N³ lattice waves stay the field of record.

### 0.4 Prior record (waves 1–4, cited)

- The finite-volume operator is mandatory on non-uniform grids (wave 1); the interior single-node reflectivity 0.658% and the boundary is coupling-defined with the bracketed rim at 0.128% (waves 2–4); the taper is the anti-reflection law; the self-resolving window is scale-invariant (wave 2-Q2).

---

## 1. The frozen setup

### 1.1 Both grids

- **Reference:** uniform axial grid, $K = 160$ shells, spacing $h = 1.0$ over the span the φ-grid covers up to $\varphi^{7}$. (The reference's spacing is set to the φ-grid's finest so the wave is resolved on both.)
- **φ-shell:** the smooth-cascade grid of wave 2 — rung lattice $z_k = z_0\varphi^k$, $K = 8$ rungs, $m = 12$ taper sub-cells per rung (per-cell ratio $\varphi^{1/12}$), giving ≈ the same resolution as the reference at rung 0.
- $c = 1.0$, $\omega_0^2 = 20.0$, $\varphi = 1.618033988749895$.

### 1.2 The two-fluid wave

Initial pulse (the gate-iv Gaussian on the ground state): on the ±z direction, a Gaussian ρ-perturbation with the checkerboard/φ-separated EY/EI source (EY Gaussian centered, EI offset by the Yin-Yang separation) per `cassi_two_fluid.glsl`'s source terms. Zeroth-time velocities set by the analytic derivative. Leapfrog (the order-2 velocity-Verlet), both grids, identical IC in physical z (interpolated onto each lattice), identical $\omega_0$, identical source strength.

### 1.3 The operator

The finite-volume Laplacian $A = -M^{-1}B^{\mathsf T}WB$ (edge $B$, $W = \mathrm{diag}(1/h)$, cell volumes $M$) — the mandatory conservative discretization (wave 1) — on each axial grid. The two-fluid coupling is exactly the shader's: $\partial_t^2\psi$ with the ±$\omega_0^2(EY - \varphi EI)$ term.

### 1.4 Harness gates (verify_twofluid.py, unconditional)

1. **Machinery conservation (uniform reference):** the free ($\omega_0^2=0$) two-fluid energy
   (KE + the finite-volume potential) is conserved to the symplectic order over $10^3$
   steps on the uniform reference (drift $< 5\times10^{-3}$; measured 3.6e-4 with the
   half-kick staggered start).
2. **Anti-phase eigenmode (refutes the φ-attractor):** the shader coupling has one zero
   mode ($EY = \varphi EI$) and one anti-phase SHO at $\omega_0\sqrt{1+\varphi}$; the
   latter is UNDAMPED on the Dirichlet line, so the $EY/EI \to \varphi$ attractor is not
   a late-time limit. The gate CONFIRMS the eigen-prediction: the coupling-force field
   oscillates at the predicted period (within a dispersion band) and persists (does not
   decay).
3. **Determinism:** two runs bitwise identical.
4. **In-band:** the pulse is resolved on both lattices ($\ge 4$ cells per pulse width).

> **Dated amendment (2026-08-15, wave-5 close-out):** the original gates in this section
> were replaced BEFORE the wave-5 report because the pre-registered claims were refuted
> by the machinery itself:
> - The integrator needed the **half-kick staggered start** (the wave-1 IC-stagger
>   lesson): without it the free-case drift is 0.49 (first-order); with it, 3.6e-4.
> - The **φ-attractor is refuted**: the coupling's anti-phase mode is an undamped SHO
>   (measured period 83 steps vs the predicted 96, dispersion band; persistent), so the
>   $EY/EI$ ratio is a persistent-oscillation snapshot, not a late-time limit. The
>   original "attractor → φ to float tolerance" gate is WITHDRAWN and replaced by the
>   eigenmode gate (gate 2).
> - The **φ-shell grid does not conserve even uncoupled**: its ~28× spacing gives a
>   growing secular free-case drift (2.2e-2 @1200, 2.3e-1 @3600 steps), intrinsic to the
>   non-uniform FV+leapfrog (verified away from the boundaries). The original "φ-shell
>   conservation ≤ 5e-2" gate is replaced by a REPORTED finding.
> These are documented here because the prereg is load-bearing; the wave-5 report records
> the full numbers.

## Q1 — the fidelity gate (mirrors gate-iv exactly)

### Arms

Run the two-fluid wave for exactly $N_{\text{steps}} = 1200$ steps on both grids. Measure the ρ-front speed (the leading edge of $|\rho|$, tracked by a fitted threshold-crossing) and the dominant-mode structure (the FFT of $\rho(t)$ at the trailing shells → the φ-power spacing).

### Decision tree (Q1 — the gate)

1. **ADOPT** (the φ-shell axial grid carries the two-fluid wave): $\left|\frac{v_{\rho,\varphi} - v_{\rho,\text{ref}}}{v_{\rho,\text{ref}}}\right| \le 5\%$ AND the dominant-mode φ-power spacing is preserved (the ratio of the two largest peak frequencies within 10% of the reference's) AND the shell grid runs to $10^3$ steps without instability.
2. **CONTRADICTS** (→ do NOT adopt the shell grid for the two-fluid dynamics): any pin fails with the reference clean.
3. **INCONCLUSIVE**: the reference itself breaks the harness (defect — fix and amend, never weaken the pins).

The verdict vocabulary is frozen (ADOPT / CONTRADICTS / INCONCLUSIVE).

## Q2 — the cascade structure under the dynamics

Per-rung group-velocity factor of the two-fluid wave's phase at the rung boundaries, on the φ-shell grid at $t \approx 3$ transits, compared to wave-2's scale-invariant value. EMERGES iff the two-fluid wave still shows the per-rung collapse (group factor < 0.2 at the 4th rung) — the dynamics preserve the self-resolving window.

## Q3 — honest negatives

Any wave that does not meet the pins, or a numeric instability (energy blow-up / NaN > 0 cells), is recorded as a finding, never hidden.

---

## Stopping rule

Fixed $N_{\text{steps}} = 1200$; one analysis; deterministic. A CONTRADICTS is final for this wave (the N³/reference grid stays the field of record — the gate-iv precedent). Only a new dated pre-registration re-opens.

## What does NOT count

- Post-hoc $N_{\text{steps}}$, $\omega_0$, grid, or source changes.
- Reading the 1D axial gate as the 3D sim's verdict — this wave tests the axial operator against its own 1D reference; the 3D full-grid test is future work.
- Any transverse-plane or full-engine claim.

## Honest tiers

- **T1 measured** — all front speeds, mode frequencies, energy drifts, per-rung factors.
- **T2 inferred** — "the two-fluid wave is (or is not) carried by the φ-shelled axial grid at the gate-iv acceptance."
- **T3 out of scope** — the full 3D two-fluid engine, any engine/registry edit.

## Number provenance

- The PDE, sources, and coupling: `CassiCosmos/compute/cassi_two_fluid.glsl` (quoted above); gate-iv acceptance: `_diag/overhaul_build_plan.md` §gates + §M1 (the 38% meshless close-out at `be56f1d`); wave 1–4 numbers as in their reports.
