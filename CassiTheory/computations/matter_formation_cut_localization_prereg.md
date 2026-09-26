# Compact-Cut Localization Diagnosis for Charged Wave Capture

## Status: Preregistered diagnostic calculation—September 2026

## Abstract

This calculation determines whether the remaining spatial discrepancy in the charged-wave binding ratio is caused by a compact-cut observable that is poorly conditioned after the carrier has dispersed, or by a genuinely unresolved field contribution. It post-processes the preserved primary and independent raw states from the spatial-convergence campaign. It does not evolve a new trajectory, change a preparation, retune a cutoff, relax a gate, or establish matter formation.

## 1. Frozen inputs and scope

The input primary receipt is
`runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911/result.json`, SHA-256 `c9619d8e431c840b8656ec470ec411ede23614bb20d8b200fbd6f7fd8b356ae9`.

The input campaign-bound independent receipt is
`runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911/verification.json`, SHA-256 `45755f677b83b11a65f1fb2271f6c85fa4844e068cc482e4cbb1c74a220abf64`.

The analysis reads only the retained primary states under `primary/` and the retained independent states under `verification_independent_states/`. It requires the exact six-array archive schema (`fields`, `velocities`, `r`, `axial`, `volume`, `time`), float64 arrays, finite values, embedded times, declared hashes, and the geometry recorded by the campaign. The campaign receipts and source snapshots remain immutable.

The target rows are `pair256` and `antiphase256` at `S0`, `S1`, and `S2`. The independent cross-check uses the separately integrated `S1` states for both target arms. The archived snapshots are $t=0,32,40,48$; late-window summaries in this diagnostic use the three retained states at $t=32,40,48$ and are not substituted for the campaign's full $32\le t\le48$ trace means.

## 2. Reconstructed observables

The analysis reconstructs the action energy, signed charge, absolute charge, origin-centred core charge and RMS, core energy, interface-shell energy, smooth-cut energy, smooth-cut charge, cut axial momentum, binding radicand, and binding ratio directly from the archived fields. The default cut is the campaign cut,

$$
w(r)=1-3s^2+2s^3,
\qquad s=\operatorname{clamp}\left(\frac{r-8}{4},0,1\right),
$$

with

$$
\mathcal B=\frac{\sqrt{E_{\mathrm{cut}}^2-v_*^2P_{\mathrm{cut}}^2}}{\Omega_\infty|Q_{\mathrm{cut}}|}.
$$

The cut acts on both fields and velocities before reconstructing its energy and momentum, including the cut-generated gradient energy. All discrete gradient, boundary, cell-volume, charge, and momentum terms follow the archived campaign action and geometry.

## 3. Frozen diagnostic matrix

The smooth-cut sensitivity matrix contains every pair

$$
r_{\mathrm{in}}\in\{4,6,8,10,12\},
\qquad
w\in\{2,4,6\}.
$$

The hard radial localization profile uses the fixed radii

$$
r\in\{4,6,8,10,12,16,24,32\}.
$$

No member of this matrix is selected as a replacement acceptance cut. For each matrix member and target arm, the analysis reports late snapshot means at `S0`, `S1`, and `S2`, adjacent-level differences in cut energy, cut charge, charge fraction, binding ratio, and the energy/charge terms entering the ratio. It also reports signed-charge, absolute-charge, and energy profiles in fixed radial shells.
The fixed-core predicate is independent of the smooth cut: for every target arm and every target grid, compute

$$
F_{\mathrm{core}}=\max_{t\in\{32,40,48\}}
\frac{\int_{r^2+\zeta^2<8^2}|\rho|\,dV}{|Q_{\mathrm{initial}}|}.
$$

`fixed_core_no_retained_localized_charge` passes only when every one of the six
target rows has $F_{\mathrm{core}}<0.25$, using the campaign's retained-charge
threshold. The predicate uses absolute charge so cancellation cannot hide a
localized carrier.


## 4. Independent checks and tolerances

Before interpretation, the script must pass:

1. exact primary receipt hash and exact independent receipt hash;
2. state path containment, declared SHA-256, archive keys, dtype, shape, finite-array, time, coordinate, and volume checks;
3. default-cut reconstruction against every target primary snapshot recorded in the primary receipt, with each compared scalar satisfying
   $|x-y|\le 5\times10^{-8}\max(1,|y|)$;
4. default-cut reconstruction against every independent target snapshot recorded in the independent receipt under the same tolerance;
5. finite JSON output with no missing matrix entries.

These are data-integrity and reconstruction checks. They do not change the spatial-convergence verdict.

## 5. Diagnostic decision tree

The result is classified from the fixed matrix without selecting a favorable cut:

For branch 3, a substantial-charge comparison is an `S1->S2` matrix member
whose left and right late-mean smooth-cut charge fractions are each at least
$0.25$. Only these comparisons can activate the `FIELD-LEVEL` branch; the
`S0` sensitivity values are reported but do not substitute for an
adjacent-level comparison.
The component comparison tolerance is $0.05$ in the normalized matrix
errors. A substantial-charge member activates `FIELD-LEVEL` only when its
binding-ratio error is at least $0.05$ and both its normalized cut-energy and
cut-charge errors are at least $0.05$.

1. If the default campaign cut reconstructs incorrectly, the diagnostic is `INCONCLUSIVE—archive reconstruction failure`.
2. If the S1-to-S2 discrepancy remains concentrated in the binding ratio while cut charge is a small fraction of the declared charge and `fixed_core_no_retained_localized_charge` passes, the result is `DISPERSIVE—binding ratio is ill-conditioned on the dispersed tail`.
3. If the discrepancy persists for a substantial-charge comparison and the binding ratio, cut energy, and cut charge each disagree beyond the component tolerance, the result is `FIELD-LEVEL—localized dynamics remain unresolved`.
4. If the ratio is stable across the matrix but the retained charge remains below the campaign retained-charge threshold, the result is `NO REMNANT—observable robustness does not imply formation`.
5. Any other combination is `INCONCLUSIVE—diagnostic branches do not separate`.

The diagnostic does not authorize a new formation claim. A subsequent change to width, charge, phase, coupling, domain, grid, or final time requires a separate preregistered evolution campaign.

## References

- `computations/matter_formation_wave_capture_spatial_convergence_prereg.md`—spatial-convergence protocol and retained-state archive contract.
- `computations/matter_formation_wave_capture.py`—action, finite-volume energy, charge, and compact-cut definitions.
- `computations/verify_matter_formation_wave_capture_spatial_convergence.py`—independent archive and reconstruction contract.
- `foundations/matter-completion-boundary.md` §§16–18—charged coexistence, radial condensation, and localized minimizer scope.
