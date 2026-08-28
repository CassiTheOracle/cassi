# Two-fluid Hamiltonian φ-completion — does symmetrizing the coupling restore conservation? (wave 13 / U1)

**Pre-registered 2026-08-16.** The engine's two-fluid coupling is non-Hamiltonian; this wave tests
the director-verified Hamiltonian completion that symmetrizes it while preserving the φ-attractor
null mode. Freeze the math, arms, statistics, and decision tree BEFORE any run.

## 0. The math (director-verified, frozen)

Engine coupling (`cassi_two_fluid.glsl`; `two_fluid_shell.py` L5-8, L68-71):
```
d2EY/dt2 = c^2 nabla^2 EY - w0^2 (EY - phi EI)
d2EI/dt2 = c^2 nabla^2 EI + w0^2 (EY - phi EI)
```
Coupling matrix `M_eng = [[1,-phi],[-1,phi]]` — asymmetric, non-Hamiltonian. Eigenvalues
`{0, 1+phi} = {0, phi^2}`: one ZERO mode `EY = phi EI` (the kernel, wave-5's "φ-attractor
direction") and one anti-phase SHO at `w0*sqrt(1+phi) = w0*phi`.

Hamiltonian completion: `M_ham = [[1,-phi],[-phi,phi^2]]` — the symmetric rank-1 projector with the
SAME kernel. Eigenvalues `{0, 1+phi^2} = {0, phi+2} = {0, 3.618}`. **(NOTE: φ+2 = 3.618, NOT
φ³ = 4.236.)** Null mode invariant: `M_ham·(φ,1)ᵀ = 0`. Anti-phase frequency shifts
`w0*sqrt(1+phi)` → `w0*sqrt(1+phi^2) = w0*sqrt(phi+2) ≈ 1.902·w0`. Frequency ratio
`B/A = sqrt(1+phi^2)/sqrt(1+phi) = sqrt(3.618/2.618) ≈ 1.176`.

Completed form is the Euler-Lagrange system of `V = ½w0²(EY−φEI)²` (+ kinetic + c² stiffness), so it
conserves `E = ½(Ẏ²+İ²) + ½c²(|∇EY|²+|∇EI|²) + ½w0²(EY−φEI)²`; the engine form (asymmetric) has
secular energy drift. The ONLY code difference: the EI-row coupling multiplies by φ —
`+w0²(EY−φEI)` → `+φ·w0²(EY−φEI)`.

## 1. Frozen setup (pins — NEVER changed after freezing; amendments dated)

- **Reuse wave-5 machinery verbatim:** `two_fluid_shell.TwoFluidLine`, `make_ic`, `make_reference`
  (uniform line, FV Laplacian, leapfrog + staggered kick), and wave-5's discrete energy
  `tf_energy(ey,ei,vey,vei,A,w0_2) = ½Σ(v²) + ½(−eyᵀAey − eiᵀAei) + ½w0²Σ(ey−φei)²` (the same E).
- **Spatial setup (wave-5 g2):** `span = φ⁷`, `z = make_reference(span, 160)` (uniform, 160 cells),
  `make_ic(z)` Gaussian (amp 0.05, width 0.02·span, EI offset by 0.2·span), `w0_2 = 20.0`, `c = 1.0`,
  `dt = 0.05·min(diff(z))`.
- **Arm A** = engine form (`TwoFluidLine`, `aei = c²Aei + w0²·d`). **Anchor:** must reproduce wave-5's
  g2 — the anti-phase SHO period (zero-crossings of `d = EY−φEI`) within the wave-5 ±30% dispersion
  band around the k=0 prediction `2π/sqrt(w0²(1+φ))/dt ≈ 96` steps (wave-5 measured ~83).
- **Arm B** = completed form (subclass overriding `kick`/`step`: `aei = c²Aei + φ·w0²·d`), IDENTICAL
  spatial operator, parameters, dt, and IC — only M changed.
- **Statistics** (both arms, same window):
  (i) null-mode stationarity — initialize `EY = φ·EI` (d = 0); `d = EY−φEI` must stay at its initial
  value (0) in BOTH arms (invariance of the kernel; `M_ham·(φ,1)ᵀ = 0`);
  (ii) anti-phase SHO frequency `f_A`, `f_B` from FFT of the `d` time series at the center probe;
  (iii) energy-drift rate of E (`tf_energy`) over the same `NSTEPS = 1200` window in both arms.

## 2. Frozen decision tree

- **SUPPORTS** if (i) the null mode is invariant (|d| stays < 1e-12 in BOTH arms), AND (ii) the
  frequency ratio `f_B/f_A ∈ [1.141, 1.211]` (= 1.176 ± 3%; finite-dt + dispersion shift absolute
  frequencies but the RATIO is the robust statistic), AND (iii) `drift_B < 0.1 × drift_A` over the
  same window.
- **CONTRADICTS** if the null mode differs between arms (i.e. the completion does not preserve the
  kernel), OR the frequency does NOT shift per the predicted ratio (outside ±3%).
- **INCONCLUSIVE** on NaN / instability / no clean FFT peak.
- No threshold is weakened to make a gate pass.

## 3. Harness gates (`verify_twofluid_hcompletion.py` → `ALL CHECKS PASSED`)

1. **G1 arm-A anchor:** anti-phase period within wave-5's ±30% dispersion band of the k=0 prediction
   (zero-crossings), i.e. the engine form reproduces wave-5 g2.
2. **G2 determinism:** arm A and arm B 100-step double runs bitwise identical.
3. **G3 no-NaN:** both arms finite over a short run.
4. **G4 null-mode:** `EY=φEI` IC → `d` stays < 1e-12 in BOTH arms.
5. **G5 frequency-ratio:** `f_B/f_A ∈ [1.141, 1.211]` (FFT peaks).
6. **G6 energy-drift (REPORTED):** `drift_A` and `drift_B` printed; the `drift_B < 0.1×drift_A`
   criterion is evaluated in the probe's decision tree.

### Amended-rule clause

The wave-5 numbers (period ~83 vs 96, ±30% band) are the calibration anchor, not gates except G1.
Any post-freeze change to §1 is FORBIDDEN; a necessary change is disclosed as a dated amendment.
Decision trees and thresholds are never weakened to make a gate pass.
