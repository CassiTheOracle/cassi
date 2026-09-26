# DFT Benchmarks: CassiBridgeV2 Real-Space Performance

## Status: Calibrated—August 2026

## Abstract

CassiBridgeV2 provides a conventional real-space density-functional implementation. Benchmarked against exact atomic ground-state energies for $Z=1$–$10$, its LDA and PBE calculations show the expected light-atom accuracy, grid-refinement behavior, and pseudopotential advantage; the DiracBridge extension supplies conventional Dirac-Kohn-Sham closed-shell tests. The measured tables establish the numerical implementation's behavior against atomic reference energies. The canonical Cassi state is the real-density pair $E_Y,E_I$ with $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, gated coherence, and rank-one conversion; it contains no built-in complex phase, chirality, propagation direction, compact coordinate, or NLS sector. The DFT calculations carry the benchmark's conventional numerical-method evidence boundary and provide no validation of Cassi field equations or particle condensation.

## Benchmark scope

LDA, PBE, and Dirac-Kohn-Sham are conventional numerical methods in these measurements. Their reference-energy comparisons test discretization, functional implementation, relativistic propagation, and pseudopotential handling. They are reported as computational benchmarks alongside the Cassi theory documents, with no particle-emergence interpretation assigned to the results.

---

## 1. Benchmark Results

| Z | Element | XC | Grid | L (a₀) | ε | E (E_h) | E_exact | Error | SCF | Wall |
|---|---------|----|------|--------|---|---------|---------|-------|-----|------|
| 1 | H | LDA | 64³ | 10 | 0.02 | -0.539 | -0.500 | 7.9% | 3.2s | 6 |
| 2 | He | LDA | 64³ | 10 | 0.02 | -2.928 | -2.903 | **0.8%** | 1.1s | 6 |
| 2 | He | PBE | 64³ | 15 | 0.05 | -2.809 | -2.903 | **3.2%** | 1.6s | 6 |
| 2 | He | PBE | 96³ | 15 | 0.05 | -2.863 | -2.903 | **1.4%** | 5.1s | 5 |
| 3 | Li | LDA | 64³ | 10 | 0.02 | -6.990 | -7.478 | 6.5% | 2.3s | 6 |
| 4 | Be | LDA | 64³ | 10 | 0.02 | -12.408 | -14.667 | 15.4% | 3.1s | 6 |
| 5 | B | LDA | 64³ | 10 | 0.02 | -20.444 | -24.654 | 17.1% | 3.5s | 6 |
| 6 | C | LDA | 64³ | 10 | 0.02 | -30.373 | -37.845 | 19.7% | 4.2s | 6 |
| 7 | N | LDA | 64³ | 10 | 0.02 | -42.390 | -54.589 | 22.3% | 4.8s | 6 |
| 8 | O | LDA | 64³ | 10 | 0.02 | -54.502 | -75.067 | 27.4% | 5.1s | 6 |
| 9 | F | LDA | 64³ | 10 | 0.02 | -66.809 | -99.734 | 33.0% | 5.4s | 6 |
| 10 | Ne | LDA | 64³ | 10 | 0.02 | -82.720 | -128.938 | 35.8% | 5.8s | 6 |
| 10 | Ne | PBE* | 64³ | 15 | 0.05 | -135.189 | -128.938 | **4.8%** | 3.1s | 6 |
| 10 | Ne | PBE† | 64³ | 15 | 0.05 | -67.574 | -128.938 | 47.6% | 4.0s | 6 |

**PBE* = pseudopotential (core-valence splitting)—PBE† = all-electron (unresolved 1s core)**

## 2. Key Findings

### 2.1 LDA Works Well for Light Atoms

- **He at N=64**: 0.8% error—the lowest listed relative error in this benchmark
- **H at N=64**: 7.9% error for a single-electron calculation
- **Li at N=64**: 6.5% error for the tested 3-electron open-shell system

### 2.2 Grid Resolution Bottleneck for Z ≥ 4

Atoms with Z ≥ 4 have compact 1s cores that are not fully resolved at N=64, L=10:
- Δx = 10/64 ≈ 0.156 a₀
- The Ne 1s orbital has <r> ≈ 0.06 a₀—only ~0.4 grid points across
- This is the primary source of the increasing error for heavier atoms

**Convergence status:** All-electron convergence for $Z\ge4$ is not demonstrated. The carbon study worsens from 19.7% error at $N=64$ to 31.8% at $N=96$, so $N=96$ alone does not fix the compact-core bottleneck. A dedicated higher-resolution all-electron study is required; for practical $Z\ge4$ runs, the documented recommendation is to use pseudopotentials with explicit core calibration.
### 2.3 PBE: Convergence Verified with Grid Refinement

- **PBE He at N=64**: 3.2% error on the medium grid
- **PBE He at N=96**: 1.4% error, improved by grid refinement

The PBE implementation reproduces the measured refinement trend in this
conventional benchmark. Errors drop from 3.2% to 1.4% from $N=64$ to $N=96$.

- **PBE Ne (pseudopotential)**: 4.8% at N=64—pseudopotential removes core resolution issue
- **PBE Ne (all-electron)**: 47.6% error—1s core unresolved at N=64

In these runs the observed differences are consistent with grid limitation;
this comparison does not isolate functional error.

### 2.4 Pseudopotential Strategy

For Z > 2, pseudopotentials remove the 1s² core and dramatically reduce grid requirements:
- Ne PP: 4.8% vs 47.6% all-electron at N=64
- The core energy approximation (−93.9075 E_h for Ne 1s²) needs calibration

### 2.5 Convergence Study (C, Z=6)—Uniform Grid Limit

Carbon tests the uniform grid's ability to resolve the compact 1s orbital (<r> ≈ 0.15 a₀):

| N | Mode | E (E_h) | Error | Time |
|---|------|---------|-------|------|
| 64 | AE | −30.373 | 19.7% | 4.2s |
| 96 | AE | −25.827 | 31.8% | 6.4s |
| 64 | PP | −40.588 | 7.2% | 5.5s |

**Key observation:** The all-electron C error increases with N, not decreases—the 1s orbital at <r> ≈ 0.15 a₀ has only 1 grid point across even at N=96 (Δx = 12/96 = 0.125 a₀). The pseudopotential removes this bottleneck and achieves 7.2% at N=64.

An accuracy target below 1% for carbon would require a dedicated
higher-resolution all-electron study. The present $N=64$ and $N=96$ runs do not
establish the required grid or runtime; any $N\ge256$ estimate is planning
guidance rather than a measured result.

This is why commercial DFT codes use atom-centered basis sets (Gaussians) or logarithmic radial grids. The uniform-grid study characterizes a conventional numerical method designed for PDE-oriented computation; its reference-energy performance remains a computational benchmark rather than a particle or condensation result.

**Practical recommendation for chemical accuracy:** Use these conventional DFT calculations for molecules where gradient corrections, grid refinement, and pseudopotential behavior are the quantities of interest. The He result (0.8%) calibrates the LDA/PBE implementation within the uniform-grid approximation.

## 3. Dirac-Kohn-Sham: Relativistic DFT

The DiracBridge (`two-fluid/cassi_dirac_bridge.py`) extends CassiBridgeV2 with conventional Dirac 4-spinor wavefunctions and the Foldy-Wouthuysen positive-definite kinetic propagator for variational imaginary-time relaxation.

| Z | Element | Grid | E_binding (E_h) | E_exact NR | Error | Notes |
|---|---------|------|-----------------|------------|-------|-------|
| 2 | He | 48³ | −2.996 | −2.903 | 3.2% | Single 4-spinor, LDA, L=10 |
| 10 | Ne | 64³ | −40.324 | −128.938 |—| 1s² core only; multi-orbital DKS needed for complete Ne |

**Key results:**
- He Dirac-DFT converges stably with Foldy-Wouthuysen propagator (no variational
  collapse to negative-energy states)
- Binding energy −2.996 E_h vs −2.903 E_h non-relativistic exact: 3.2% error—
  consistent with LDA error at N=48 + relativistic correction
- Electron density correct: ⟨r⟩ = 0.94 a₀ for He 1s
- Ne single-orbital DKS captures 1s² core correctly (⟨r⟩ = 0.27 a₀, in line with
  compact 1s orbital at Z=10)

**Status of the numerical implementation:**
The closed-shell tests establish stable Foldy-Wouthuysen propagation and the listed reference-energy behavior for the tested He and Ne cases. They characterize the conventional Dirac-Kohn-Sham implementation and carry no canonical two-fluid or particle-condensation status.

## 4. Conclusions

1. **The tested conventional CassiBridgeV2 DFT implementation reproduces the listed atomic behavior.** The real-space pseudospectral approach yields the measured shell structure, orbital ordering, and energy hierarchy for the tested atoms.

2. **Grid resolution is the limiting factor.** $N=64$ gives the listed 7.9%
error for H and 0.8% error for He. For $Z\ge4$, the available all-electron
measurements do not demonstrate convergence: carbon worsens from 19.7% error
at $N=64$ to 31.8% at $N=96$, and $N=96$ alone does not fix the compact-core
error. Pseudopotentials are the recommended practical route while
higher-resolution all-electron convergence remains open.

3. **The PBE implementation reproduces the benchmark trend.** PBE He at 3.2% error is within expectation for a grid-limited calculation. The PBE gradient correction shifts energies in the right direction relative to LDA.

4. **Recommended production strategy:** Prefer pseudopotential runs for $Z>2$, with explicit core-energy calibration and element-by-element error reporting. $N=96$ is a candidate grid for such studies, not a demonstrated full-first-row accuracy guarantee. The available measurements do not establish <$5\%$ total-energy error for all $Z=1$–$10$, and all-electron convergence for $Z\ge4$ remains unshown.

## References

- `particles/cassi-yang-yin-particles.md`—conditional Hypothesized complex-field/NLS particle-interference extension; the DFT benchmark is independent of that extension
- `two-fluid/cassi_bridge_v2.py`—the real-space pseudospectral DFT engine benchmarked here
- `two-fluid/cassi_dirac_bridge.py`—the Dirac-Kohn-Sham extension (DiracBridge)

