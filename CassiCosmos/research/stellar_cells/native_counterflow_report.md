# Native Yang/Yin counterflow and paired-helix measurement

## Status: INCONCLUSIVE—no qualifying helix detected in retained samples

The registered current measurements detect **no counterdirected double helix** and **no sustained species-associated radial counterflow**. The six primary evolving runs supply 246 final-window observations, all with nonzero radial power available for comparison. None satisfies the radial-opposition predicate; none contains a resolved pair of helical current channels.

A numerical-quality condition prevents a clean native-resolution physics verdict. At site 512, every 8,192-site arm has only two graph neighbors. Its regularized least-squares gradient is ill-conditioned, and the GPU values disagree with the double-precision reconstruction beyond the frozen tolerance. The independent auditor reproduces that failure. Consequently, the primary radial and helical hypotheses remain **INCONCLUSIVE**, rather than receiving an unqualified negative verdict.

This is an analysis of the retained native-sphere campaign. No new GPU simulation, production-source change, helical force, phase field, material mode or black-hole sector is introduced.

## What is measured

The native state contains two signed wave amplitudes and their momenta. It does not identify independently advected Yang/Yin material populations. The measured quantities are component **graph wave-energy currents**, derived from the executed reciprocal-graph operator. The derivation, source precision and thresholds are fixed in [the preregistration](native_counterflow_prereg.md) and [machine-readable specification](native_counterflow_spec.json).

For each component, the exact bond-power calculation uses the neighboring amplitude difference, the endpoint momentum sum, the native wave coefficient and the minimum-image edge distance. Sphere-cut measurements retain four nonnegative powers: Yang-out, Yang-in, Yin-out and Yin-in. These are power categories, not numbers or masses of particles.

The primary radial statistic is the directional bias at radius R/2:

    bias = (outward power - inward power) / (outward power + inward power)

A qualifying frame requires opposite component biases, both magnitudes at least 0.5, sufficient component throughput balance and at least 32 crossing edges. Persistence requires at least 80% of all final-window observations.

The helix detector requires two spatially separated, adequately sampled current channels, at least six consecutive resolved axial slices, at least half a spatial turn, bounded adjacent angle increments, coherent currents aligned with the channel tangents, and opposing axial directions. It does not require same-site current opposition: spatially separate counterflows need not overlap.

The positive graph energy uses the native symmetrizing node weight V^(1/3). It is not a calibrated SI energy or a physical-volume material energy. Its checked local balance is a semidiscrete identity, not a claim that the finite integrator conserves that energy exactly.

## Coverage and observed results

- **25 arms, 4,029 retained snapshots**, code times 0 through 32.
- **Six primary evolving arms:** R = 12, 9 and 6, each with two seeds.
- **41 observations per arm** in the primary window, t = 24 through 32.
- The remaining arms retain frozen-field controls, kicks, timestep/particle/site refinements, source and conversion ablations, and a repeated run.
- **No detected paired helix in any of the 4,029 snapshots.**
- **No qualifying radial opposition in any of the 1,025 final-window snapshots.** Frozen zero-current controls are included in that last denominator but are not eligible transport comparisons; the primary comparison has 246/246 eligible observations.

| Initial radius | Primary final-window observations, both seeds | Qualifying radial opposition | Qualifying paired helix | Maximum channel-centroid separation / site spacing |
|---|---:|---:|---:|---:|
| 12 | 82 | 0 | 0 | 0.715 |
| 9 | 82 | 0 | 0 | 1.002 |
| 6 | 82 | 0 | 0 | 0.928 |

The frozen separation requirement is **at least 2 site spacings**. Even the maximum measured centroid separation, before requiring adequate width separation or all other predicates, remains below that boundary. None of the primary final-window frames has a resolved slice pair. A unique covariance axis is available in only one of the 246 frames; candidate-axis diagnostics are nevertheless calculated when uniqueness fails.

The radial biases vary across the saved times. They do not separate into persistent Yang-out/Yin-in roles or the reverse. The even/odd subsample persistence fractions are both zero for both registered predicates. This diagnostic does not establish what happens between saved observations.

![Measured radial biases and channel separation, with explicit numerical-quality qualification](../../_diag/native_counterflow_20260915/measurement_summary.png)

The figure shows actual measurements, not rendered or inferred flow paths. Its points are time medians, whiskers are the complete saved-time ranges, and separation bars are maxima across final-window slices and observations.

## Calibration and independent verification

The detector recognizes the prescribed analytic counterdirected helix and its rotated counterpart. They yield approximately **0.852** and **0.849 turns**, respectively, with eight consecutive resolved slices. It rejects the straight counterflow, helical coflow, coincident channels, radial flow and zero-current cases. In particular, the coflowing helix has the same spatial winding as the positive calibration but fails the opposing-direction predicate.

The current calibration agrees with analytic traveling-wave bond powers, the regular-grid gradient and Laplacian, radial-counterwave powers, and pointwise semidiscrete energy balance. An initial calibration assertion incorrectly expected the 24-edge innermost radial cut to pass a 32-edge eligibility requirement. That assertion is corrected to expect rejection; the threshold and analytic input are unchanged. The initial failed receipt is retained in the initial-gradient-check archive.

| Verification quantity | Attempted comparisons | Result |
|---|---:|---|
| Producer pointwise semidiscrete energy balance, all snapshots | 30,697,472 node comparisons | 0 tolerance violations |
| Independent final-state bond powers and current vectors, all 25 arms | 3,610,402 scalar comparisons | Agreement within 1e-10 absolute + relative tolerance |
| Independent final-state radial cut powers | 400 | Agreement within 1e-10 absolute + relative tolerance |
| Independent geometry values, including analytic winding | 3,103 | Agreement; unavailable zero-current quantities remain unavailable |
| Independent raw GPU endpoint gradient/Laplacian comparison | 3,047,424 scalar comparisons | 265 gradient disagreements; 0 Laplacian disagreements |

The independent verifier imports no current or geometry measurement implementation. It reloads source arrays, checks their stored and decoded hashes, reconstructs bond powers and current moments, recalculates cuts and geometry, and independently reproduces the endpoint failure counts. Source hashes bind the executed operator, analysis modules, specification, calibration, receipts and generated frame artifacts.

A numeric firing check modifies a **copy of an actual nonzero measured bond power**. Reversing that single Yang bond power produces exactly one formula mismatch and two local energy-balance violations. The original artifact remains unchanged. The check therefore demonstrates that the zero-mismatch branches are capable of rejecting a real numerical discrepancy.

The independent result is **VERIFIED_INCONCLUSIVE**: the observations and the reason the science-quality check fails are independently reproduced. This status does not turn the failed physics-quality check into a pass.

## Numerical and resolution qualifications

### Native-resolution endpoint discrepancy

All 23 arms with 8,192 sites exhibit the endpoint gradient discrepancy at **site 512**, which has **two neighbors**. The double-precision normal matrices there have condition numbers of approximately **1.18 million**. Across both endpoint fields and all arms, 265 scalar gradient values exceed the registered tolerance, with maximum absolute disagreement approximately **0.001301**. No Laplacian comparison fails.

The radial and local graph-current calculations do not use the least-squares gradient; they use the directly reconstructed bond powers. Nevertheless, the preregistered endpoint-quality condition fails. The engine's use of gradients elsewhere is not bypassed, and no claim is made that the discrepancy is harmless to the underlying dynamics. The native-resolution hypotheses remain INCONCLUSIVE.

This run does not modify the topology, regularizer, shader precision, thresholds or particle dynamics to remove the discrepancy. The next numerical task would be to address the sparse-neighbor gradient reconstruction and then repeat the same measurement criteria.

### Coarse-site control

The two 1,024-site arms pass the endpoint comparison. They are not a clean negative helix control: their fixed axial slice width is 2.25, below their site spacing of approximately 2.976. The frozen spatial-sampling requirement cannot be met. Their helical interpretation is therefore also **INCONCLUSIVE**, rather than treating a structurally unpassable detector as evidence of absence. The final artifacts expose this eligibility explicitly.

### Other boundaries

- Frozen-field arms have exactly zero bond currents. They are negative controls, not positive conservation or transport evidence from an attempted nonzero-flow comparison.
- No frame reaches the registered helix predicate, and no primary arm has persistent radial opposition. The conditional dense-run trigger is empty, so no new GPU arms are launched.
- The observational statement is bounded to the saved times and the registered axis-resolved channel class. It does not exclude every bent, knotted, toroidal, transient or sub-resolution flow.
- Identifying these wave currents with actual expansive/contractive material populations remains **INCONCLUSIVE** because the native state supplies no independent material-current map.

## Artifacts and reproduction

To regenerate the analysis, run from the CassiCosmos repository directory with a new, unused output directory:

```text
python research/stellar_cells/native_counterflow_calibrate.py --output _diag/native_counterflow_recheck
python research/stellar_cells/native_counterflow_analyze.py --output _diag/native_counterflow_recheck
python research/stellar_cells/native_counterflow_verify.py --output _diag/native_counterflow_recheck
```

The analyzer refuses to overwrite a completed analysis. The existing analyzer exit code is **2**, corresponding to the retained numerical-quality failure. The independent audit exits **0** with status **VERIFIED_INCONCLUSIVE**, meaning the evidence and its fail-closed classification are verified. It is not a successful science gate.

To audit the retained result without regenerating the measurements, run `python research/stellar_cells/native_counterflow_verify.py` with no output override.

- [Analysis and per-arm summaries](../../_diag/native_counterflow_20260915/analysis.json)
- [Independent verification and mutation evidence](../../_diag/native_counterflow_20260915/verification.json)
- [Analytic calibration](../../_diag/native_counterflow_20260915/calibration.json)
- [Source campaign](../../_diag/native_sphere_20260915d/campaign.json)
- [Measured figure generator](../../_diag/native_counterflow_20260915/plot_measurements.py)

Each arm directory contains frame-level measurements, raw hash bindings and a final-current witness. The initial-gradient-check and endpoint-audited analysis directories are retained separately. Audit/classification refinements leave the original measurements, bond-current witnesses and raw bindings byte-identical; no simulation is rerun to obtain a different outcome.
