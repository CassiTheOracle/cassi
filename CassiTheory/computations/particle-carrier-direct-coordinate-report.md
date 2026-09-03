# Particle Carrier Direct-Coordinate Recovery Report

## Status: Tested—September 2026

## Abstract

A direct fixed-charge carrier coordinate removes the softplus saturation that hid a large physical carrier residual in the stationary particle calculation. At density-depletion coupling $h_C=2.9598260763447164$ and fixed carrier charge $q_C=4$, the recovered primary field is physically stationary to gradient RMS $1.07\times10^{-7}$, nodeless, localized, and energetically retained below the exterior threshold. The same branch survives a larger domain and a finer grid as a qualified localized solution. The larger-domain observables agree with the primary calculation, while the finer-grid energy differs by $8.43\%$, above the frozen $5\%$ tolerance. The measured conclusion is therefore a finite-grid stationary branch, not a resolution-qualified continuum solution.

## 1. Question and intervention

The source calculation represented the nonnegative carrier amplitude through a softplus coordinate. Its terminal fields looked localized, but the physical fixed-charge residual was dominated by the carrier equation even when the optimizer-coordinate gradient was small. Thousands of carrier coordinates had saturated at numerical zero, so the optimizer could not follow physical descent directions.

The recovery calculation instead optimized a signed carrier shape $z$ and normalized it exactly at every evaluation,

$$
c(z)=\sqrt{q_C}\,
\frac{M\mathcal P_{C_4}z}
{\left[\int (M\mathcal P_{C_4}z)^2\,d^3x\right]^{1/2}}.
$$

Here $M$ fixes the Dirichlet shell and $\mathcal P_{C_4}$ preserves the registered quarter-turn scalar symmetry. The action, coefficient bracket, source fields, grids, optimizer schedule, physical stationarity statistic, localization conditions, and comparison tolerances remained fixed. A valid endpoint also had to be nodeless after one global sign choice; sign-changing excited states could not count as the recovered ground branch.

## 2. Execution integrity

The independent preflight reconstructed all five source artifacts, reproduced their physical diagnostics, verified their hashes, and recovered the fixed charge through the direct coordinate with maximum round-trip error below $5\times10^{-12}$. It reported zero mismatches before the evidentiary calculation began.

A callable-interface defect produced a non-evidentiary receipt before any optimization block started. The frozen repair in `computations/particle-carrier-direct-coordinate-execution-amendment.md` made the field map accept the stationary solver's charge argument, applied the already-required scalar projector, and moved the calculation to a fresh output directory. No physical or numerical decision rule changed.

The canonical execution is bound by these receipts:

| Item | SHA-256 |
|---|---|
| manifest | `d602e50f0a8d9a4c8f306930017d92101b797d695daaf3315a79a423c6f20f77` |
| preflight | `7d95a1cc48b5fcb287e3af4d296e481ff34150c8be0ac5fa9b4d9b1519247404` |
| primary result | `59f39d6e565ab24faab705094ea5ee1001d7ab3939d8a923db091dc903e44c73` |
| independent verification | `b858d05df7db577896f6f5ff325efba2922d90cc9359c9a7264631ad1c314629` |

The independent final verifier reproduced every terminal diagnostic and comparison from the stored arrays, confirmed every source and terminal artifact hash, reconstructed the stopping rule and verdict, and reported zero mismatches.

## 3. Recovered primary branch

The first frozen coefficient candidate, $h_C=2.9598260763447164$, converged in one continuation block. This is half the analytic retention-buffer reference value and was selected by the preregistered scan order, not fitted to an observed particle.

| Quantity | Measured value | Frozen condition |
|---|---:|---:|
| physical gradient RMS | $1.0725740534\times10^{-7}$ | $\le 1.20\times10^{-4}$ |
| fixed charge | $4.0000000000$ | relative error $\le10^{-10}$ |
| carrier frequency $\widehat\omega_C$ | $-0.0448188349$ | $<0.73$ |
| carrier RMS radius | $1.5607471807$ | $\le2.40$ |
| outer carrier fraction | $5.0019014022\times10^{-4}$ | $\le0.08$ |
| maximum density depletion | $0.9862695726$ | $\ge0.05$ |
| oriented negative-norm fraction | $0$ | $\le10^{-12}$ |
| physical energy | $1.3402012490$ | recorded observable |

The branch passes charge and boundary control, gauge control, outer-flux control, physical stationarity, localization, density depletion, carrier retention, and the nodeless condition. Its stored field artifact has SHA-256 `c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837`.

The physical residual falls by more than three orders of magnitude from the same source field's $6.08\times10^{-4}$ residual. Because the action and coefficient are unchanged between that source and this endpoint, the improvement isolates the carrier parameterization as the numerical obstruction. It does not establish that the selected coefficient follows from the theory or corresponds to a measured particle.

## 4. Domain and resolution comparisons

A larger box at the same lattice spacing converged independently from the frozen analytic separated-core seed. It remained physically stationary, nodeless, localized, and retained. Relative to the primary branch, its energy differed by $0.740\%$, its carrier radius by $0.881\%$, its core length by $0.0213$, and its carrier frequency by $0.00374$. Every larger-domain comparison passed, so the localized branch is not set by the primary box boundary at this spacing.

A finer grid on the original box also converged independently from the analytic seed. It passed the same stationarity, nodelessness, localization, retention, gauge, boundary, and outer-flux conditions. Its carrier radius differed by $3.89\%$, its core length by $0.110$, and its carrier frequency by $0.0353$, all within their frozen tolerances. Its physical energy was $1.4635886842$, which differs from the primary energy by $8.43\%$ and exceeds the frozen $5\%$ tolerance.

| Grid | Domain radius | Spacing | Physical gradient RMS | Energy | Carrier radius | $\widehat\omega_C$ |
|---|---:|---:|---:|---:|---:|---:|
| primary | $4$ | $0.5$ | $1.07\times10^{-7}$ | $1.3402012490$ | $1.5607471807$ | $-0.0448188349$ |
| larger domain | $5$ | $0.5$ | $6.62\times10^{-10}$ | $1.3302846266$ | $1.5746156666$ | $-0.0485608421$ |
| finer grid | $4$ | $0.4$ | $1.59\times10^{-7}$ | $1.4635886842$ | $1.6238815830$ | $-0.0095220668$ |

The larger-domain artifact hash is `54ea983bb78783f2e0619851741f47167a2c9d6fb08757ce70361b0d1369c460`; the finer-grid artifact hash is `8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f`.

## 5. Result and remaining boundary

The calculation establishes a nodeless, localized, fixed-charge stationary solution of the complete registered finite-grid action at the first tested density-depletion coefficient. The solution is independently reproducible from a separate basin on all three tested grids, physically stationary under the full constrained first variation, and insensitive to enlarging the box at fixed spacing.

The calculation does not yet establish a continuum particle. The finer-grid energy fails the registered cross-grid agreement condition even though the field remains localized and stationary. The next discriminating calculation must extend the same-domain resolution sequence at the selected coefficient and decide whether the energy difference contracts toward a common limit or remains resolution dependent.

The density-depletion coefficient remains an uncalibrated model input selected by this numerical search. The carrier charge is an auxiliary global $U(1)_C$ number with no demonstrated identification as electric charge, baryon number, lepton number, spin, or a Standard Model species. Dynamic persistence, fluctuation stability, topology-changing formation, annihilation, and observable quantum-number matching remain separate requirements.

## References

- `computations/particle-carrier-direct-coordinate-prereg.md`—frozen physical question, coefficient order, endpoint conditions, and verdict tree.
- `computations/particle-carrier-direct-coordinate-execution-amendment.md`—interface repair and fresh evidentiary output path.
- `computations/particle-carrier-direct-coordinate-receipt-binding.md`—canonical downstream receipt and artifact hashes.
- `computations/particle_carrier_direct_coordinate.py`—primary recovery calculation.
- `computations/verify_particle_carrier_direct_coordinate.py`—independent artifact and verdict verifier.
- `computations/particle-carrier-localization-report.md`—source scan and carrier-residual diagnosis.
- `foundations/particle-stationary-action-closure.md`—complete stationary action and particle-completion criteria.
