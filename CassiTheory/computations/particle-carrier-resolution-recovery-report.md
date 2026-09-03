# Particle Carrier Resolution-Recovery Report

## Status: Tested—September 2026

## Abstract

The source-free fixed-charge particle action supports one localized, nodeless, carrier-retaining stationary branch across four same-domain spatial resolutions. Two new refinements at $N=25$ and $N=29$ independently converged from the same analytic separated-core seed, passed every frozen physical qualification, agreed with their adjacent coarser solutions, and reduced the absolute energy drift at each step. Independent artifact reconstruction found no mismatch. The result establishes a three-comparison finite-grid resolution-consistent branch at the numerically selected coefficient $h_C=2.9598260763447164$; it does not establish a continuum solution, static stability of this branch, real-time persistence, or proton identity.

## 1. Question and fixed system

The calculation asks whether the localized retained branch found with the direct normalized carrier coordinate survives systematic refinement on the same physical cube. The action, charge $Q_C=4$, boundary conditions, analytic seed, optimizer, continuation schedule, physical qualification thresholds, adjacent-grid tolerances, stopping rule, and verdict tree were frozen before execution in `computations/particle-carrier-resolution-recovery-prereg.md`.

The campaign holds the physical half-width at $R=4$ while reducing the spacing through

$$
\Delta x\in\left\{\frac12,\frac25,\frac13,\frac27\right\}
$$

on $N\in\{17,21,25,29\}$ grids. The two inherited endpoints are immutable source artifacts. Each new refinement begins from the same analytic separated-core field rather than from interpolation of a coarser numerical solution, so agreement cannot be attributed to transporting a discrete minimum between grids.

## 2. Execution and verification

The verifier schema retains only independently reproducible physical diagnostics for inherited source levels and reads analytic-seed conversion from the established `source_reconstruction` field. Its requirements are frozen by `computations/particle-carrier-resolution-recovery-verification-amendment.md`. The canonical result satisfies this schema, while the physical inputs, statistics, thresholds, and decision branches remain those declared in the preregistration.

The canonical campaign passes independent preflight, completes both new refinements in their first continuation blocks, and passes independent final verification with zero mismatches. The verifier reconstructs source and refinement fields from the stored artifacts, recomputes physical diagnostics, re-evaluates qualification and localization, checks optimizer budgets and stopping, recomputes adjacent-grid statistics and energy-difference contraction, and derives the verdict without importing the primary resolution driver.

| Canonical receipt | SHA-256 |
|---|---|
| `runs/20260902_particle_carrier_resolution_recovery/preflight_verification.json` | `6f9729dcf60e50db6ed4350f9763190aa9f5fc6efd7a9d0e602ae018572ec96f` |
| `runs/20260902_particle_carrier_resolution_recovery/results.json` | `11b6518897683636f0890936ae31d2d17516b9b79716a97b4919cbc60e0b6121` |
| `runs/20260902_particle_carrier_resolution_recovery/verification.json` | `94dcc278ef3418c00ca4cb71fa9066712713216c8c645a0db45dff8f45a39170` |

The canonical manifest hash is `8d1f18cb18d3635960ec7be1076688bcbd1f1fbc5fda1d86e851c46f8b3ff853`.

## 3. Stationary endpoints

All four endpoints are deeply localized relative to the frozen one-percent exterior-carrier bound. The carrier radius remains between $1.56$ and $1.64$ throughout the sequence, while the negative carrier-norm fraction is zero on both new grids. The new physical-gradient residuals remain below the frozen $5\times10^{-7}$ stationarity threshold.

| $N$ | $\Delta x$ | $E_P$ | physical gradient RMS | $\omega_C$ | carrier radius | core length | outer carrier fraction | maximum density depletion |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.500000 | 1.3402012490 | $1.073\times10^{-7}$ | $-0.04481883$ | 1.560747 | 2.235230 | $5.002\times10^{-4}$ | 0.986270 |
| 21 | 0.400000 | 1.4635886842 | $1.586\times10^{-7}$ | $-0.00952207$ | 1.623882 | 2.345582 | $1.871\times10^{-4}$ | 0.971651 |
| 25 | 0.333333 | 1.5062009945 | $2.404\times10^{-7}$ | $0.00194256$ | 1.616787 | 2.297394 | $9.080\times10^{-5}$ | 0.978351 |
| 29 | 0.285714 | 1.5251878560 | $3.090\times10^{-7}$ | $0.00341645$ | 1.631431 | 2.297794 | $1.071\times10^{-4}$ | 0.985629 |

The direct carrier-coordinate conversion reproduced the analytic seed to maximum absolute error $1.11\times10^{-16}$ on the $N=25$ grid and exactly at stored precision on the $N=29$ grid. The terminal artifacts are

| Grid | Artifact | SHA-256 |
|---|---|---|
| $N=25$ | `fields_resolution_X1_block01.npz` | `c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393` |
| $N=29$ | `fields_resolution_X2_block01.npz` | `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0` |

## 4. Adjacent-grid agreement

The independently seeded $N=25$ endpoint agrees with the $N=21$ endpoint in energy, carrier radius, core length, and carrier frequency. The independently seeded $N=29$ endpoint agrees with the $N=25$ endpoint by still narrower margins. Every comparison lies inside its frozen tolerance.

| Adjacent pair | relative energy difference | relative carrier-radius difference | absolute core-length difference | absolute $\omega_C$ difference | Pass |
|---|---:|---:|---:|---:|:---:|
| $N=21\leftrightarrow25$ | 0.0282913 | 0.00436870 | 0.0481881 | 0.0114646 | yes |
| $N=25\leftrightarrow29$ | 0.0124489 | 0.00897615 | 0.000399751 | 0.00147389 | yes |

The absolute energy differences contract twice:

$$
|E_{17}-E_{21}|=0.1233874,
\qquad
|E_{21}-E_{25}|=0.0426123,
\qquad
|E_{25}-E_{29}|=0.0189869.
$$

Both strict inequalities required by the stopping rule hold. The reduction factors are approximately $0.345$ and $0.446$.

## 5. Verdict

The frozen decision tree returns

$$
\boxed{\text{EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH}.}
$$

This verdict means that one numerically selected coefficient point of the registered source-free fixed-charge action has a localized, nodeless, carrier-retaining stationary solution whose principal observables agree across three adjacent same-domain resolution comparisons and whose absolute energy drift decreases twice. The result closes the finite-grid localization, carrier-retention, and tested resolution-consistency questions for this branch.

The calculation does not combine this localized branch with the nonnegative low-mode Hessian measured on the distinct diffuse background. Static stability therefore remains untested for the localized branch itself. A continuum limit also remains open because four finite grids do not prove convergence as $\Delta x\to0$. Real-time persistence, robustness across basins and coefficients, physical normalization, particle quantum numbers, formation from generic initial data, and identification with the proton remain separate requirements.

## 6. Next discriminating calculation

The next calculation should evaluate the constrained physical Hessian on the finest localized artifact, with the fixed-charge direction, gauge image, shell mask, and global carrier phase treated explicitly. A verified negative mode would reject static stability of this candidate; a stable low spectrum would justify a real-time perturbation-and-formation campaign. The diffuse background's existing Hessian cannot answer that question because stability is local to the field configuration being perturbed.

## References

- `computations/particle-carrier-resolution-recovery-prereg.md`—frozen resolution ladder, diagnostics, tolerances, stopping rule, and verdict tree.
- `computations/particle-carrier-resolution-recovery-verification-amendment.md`—frozen verifier schema requirements.
- `computations/particle_carrier_resolution_recovery_manifest.json`—hash-bound code, source artifacts, coefficients, grids, and schedules.
- `computations/particle_carrier_resolution_recovery.py`—primary deterministic refinement driver.
- `computations/verify_particle_carrier_resolution_recovery.py`—independent final verifier.
- `computations/particle-carrier-direct-coordinate-report.md`—source localized branch and its initial finite-grid boundary.
- `foundations/particle-stationary-action-closure.md`—registered source-free fixed-charge action and fluctuation problem.
