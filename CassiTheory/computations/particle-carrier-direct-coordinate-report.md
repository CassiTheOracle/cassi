# Particle Carrier Direct-Coordinate Recovery Report

## Status: Tested—September 2026

## Abstract

A direct fixed-charge carrier coordinate removes the softplus saturation that hid a large physical carrier residual in the stationary particle calculation. At the Mapped density-depletion coupling $h_C=2.9598260763447164$ and fixed carrier charge $q_C=4$, the recovered primary field is physically stationary, nodeless, localized, and energetically retained below the exterior threshold. The branch passes a larger-domain control and survives four same-domain resolutions; the two finest adjacent comparisons satisfy the frozen observable tolerances, and the absolute energy drift contracts twice. The finest $N=29$ artifact's six independently matched lowest constrained $C_4$ finite-grid PA42 eigenpairs contain one numerically near-zero carrier-phase symmetry mode, no negative mode, and five positive modes. The symmetry mode retains high-frequency odd-even structure, so localized Hessian resolution, continuum existence, PA43 dynamics, and physical particle identity remain open.

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

The canonical field-map interface accepts the stationary solver's charge argument, applies the required scalar projector, and writes to the declared evidentiary output path. Its requirements are frozen by `computations/particle-carrier-direct-coordinate-execution-amendment.md`. The physical inputs, statistics, thresholds, and decision branches are those declared in the preregistration.

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

The physical residual falls by more than three orders of magnitude from the same source field's $6.08\times10^{-4}$ residual. Because the action and coefficient are unchanged between that source and this endpoint, the improvement demonstrates that carrier parameterization materially obstructed the optimization. Residuals on positive carrier cells also contribute to the carrier-sector diagnosis, so this comparison does not establish the parameterization as the sole obstruction. The selected coefficient has no theoretical derivation or measured-particle calibration.

## 4. Domain and resolution comparisons

A larger box at the same lattice spacing converges independently from the frozen analytic separated-core seed. It remains physically stationary, nodeless, localized, and retained. Relative to the primary branch, its energy differs by $0.740\%$, its carrier radius by $0.881\%$, its core length by $0.0213$, and its carrier frequency by $0.00374$. Every larger-domain comparison passes, so the localized branch is not set by the primary box boundary at this spacing.

On the original $R=4$ box, the $N=21$ endpoint also converges independently from the analytic seed and passes stationarity, nodelessness, localization, retention, gauge, boundary, and outer-flux conditions. Its energy differs from the $N=17$ endpoint by $8.43\%$, outside the direct-coordinate campaign's frozen $5\%$ pairwise tolerance. Two further independently seeded refinements at $N=25$ and $N=29$ resolve that finite-grid boundary: their adjacent energy differences are $2.829\%$ and $1.245\%$, and their carrier-radius, core-length, and carrier-frequency differences all pass the frozen tolerances.

| Role | $N$ | Domain radius | Spacing | Physical gradient RMS | Energy | Carrier radius | $\widehat\omega_C$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary | 17 | $4$ | $0.5$ | $1.07\times10^{-7}$ | $1.3402012490$ | $1.5607471807$ | $-0.0448188349$ |
| larger domain | 21 | $5$ | $0.5$ | $6.62\times10^{-10}$ | $1.3302846266$ | $1.5746156666$ | $-0.0485608421$ |
| first same-domain refinement | 21 | $4$ | $0.4$ | $1.59\times10^{-7}$ | $1.4635886842$ | $1.6238815830$ | $-0.0095220668$ |
| second same-domain refinement | 25 | $4$ | $1/3$ | $2.40\times10^{-7}$ | $1.5062009945$ | $1.6167873281$ | $0.0019425599$ |
| third same-domain refinement | 29 | $4$ | $2/7$ | $3.09\times10^{-7}$ | $1.5251878560$ | $1.6314313026$ | $0.0034164532$ |

The same-domain absolute energy differences contract from $0.1233874$ to $0.0426123$ and then to $0.0189869$. The frozen resolution-recovery decision tree therefore returns `EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH`.

The larger-domain artifact hash is `54ea983bb78783f2e0619851741f47167a2c9d6fb08757ce70361b0d1369c460`. The same-domain refinement artifact hashes are `8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f` at $N=21$, `c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393` at $N=25$, and `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0` at $N=29$.

The resolution-recovery manifest, primary result, and independent verification have SHA-256 hashes `8d1f18cb18d3635960ec7be1076688bcbd1f1fbc5fda1d86e851c46f8b3ff853`, `11b6518897683636f0890936ae31d2d17516b9b79716a97b4919cbc60e0b6121`, and `94dcc278ef3418c00ca4cb71fa9066712713216c8c645a0db45dff8f45a39170`, respectively. The independent verification passes with zero mismatches.

## 5. Result and remaining boundary

The direct-coordinate and resolution-recovery calculations establish a nodeless, localized, fixed-charge stationary solution of the complete registered finite-grid action at the Mapped density-depletion coupling. The branch is independently reproducible from the analytic separated-core basin, insensitive to the tested box enlargement, and resolution-consistent across the three finest same-domain grids.

The constrained physical Hessian on the finest localized artifact has no
negative mode among the six independently matched lowest modes. Its one
numerically near-zero mode is identified with the analytic global carrier-phase
direction, and the first positive eigenvalue is $0.01527618220595$ above the
uncertainty $6.092903959\times10^{-4}$. The phase mode's high-frequency
fraction $0.8744032081$ fails the frozen spatial cutoff, and no localized
Hessian-resolution sequence exists. The finite-grid PA42 sign classification
therefore remains separate from continuum energetic stability and PA43 temporal
stability.

The density-depletion coefficient remains an uncalibrated model input selected by the numerical search. The carrier charge is an auxiliary global $U(1)_C$ number with no demonstrated identification as electric charge, baryon number, lepton number, spin, or a Standard Model species. Dynamic persistence, topology-changing formation, annihilation, and observable quantum-number matching remain separate requirements.

## References

- `computations/particle-carrier-direct-coordinate-prereg.md`—frozen physical question, coefficient order, endpoint conditions, and verdict tree.
- `computations/particle-carrier-direct-coordinate-execution-amendment.md`—frozen canonical field-map interface requirements.
- `computations/particle-carrier-direct-coordinate-receipt-binding.md`—canonical downstream receipt and artifact hashes.
- `computations/particle_carrier_direct_coordinate.py`—primary recovery calculation.
- `computations/verify_particle_carrier_direct_coordinate.py`—independent artifact and verdict verifier.
- `computations/particle-carrier-localization-report.md`—source scan and carrier-residual diagnosis.
- `computations/particle-carrier-resolution-recovery-prereg.md`—frozen same-domain refinement sequence, convergence statistics, tolerances, and verdict tree.
- `computations/particle-carrier-resolution-recovery-verification-amendment.md`—frozen verifier schema requirements.
- `computations/particle_carrier_resolution_recovery_manifest.json`—hash-bound resolution code, source artifacts, grids, and optimizer schedule.
- `computations/particle-carrier-resolution-recovery-report.md`—independently verified refinement measurements and present finite-grid boundary.
- `computations/particle-localized-physical-hessian-report.md`—constrained finite-grid spectrum of the finest localized artifact.
- `foundations/particle-stationary-action-closure.md`—complete stationary action and particle-completion criteria.
