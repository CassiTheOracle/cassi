# Quark–Meson Carrier Resolution Qualification

## Status: Preregistered—September 2026

## Abstract

The regular quark–meson carrier calculation passes its action, current and cosmological initial-condition checks, while its frozen spectral gate fails four numerical checks. The independent two-sided shooting solution gives a localized nodeless endpoint level at $42.74444856698\ \mathrm{MeV}$ and an RMS radius of $0.66302931195\ \mathrm{fm}$. The finite-grid Wilson calculation gives $46.23864550303\ \mathrm{MeV}$ at $N_r=1200$ and $44.48317699788\ \mathrm{MeV}$ at $N_r=2400$. This qualification tests whether that disagreement follows the declared vanishing Wilson regulator, whether the low-overlap transitions lie outside the independently resolved energy window, and whether a continuum-extrapolated reduced formation barrier remains below the frozen QCD crossover scale.

The QMC2 verdict remains `FAIL`. This protocol can qualify the physical content carried by its convergent subsequence; it cannot replace or edit the frozen verdict.

<!-- qcd-quark-meson-carrier-qualification:start -->

## 1. Immutable inputs

The accepted inputs and their SHA-256 identities are:

| Input | SHA-256 |
|---|---|
| `runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/results.json` | `6f067ee37527ccf04c562a5345331ee84d9cc2d6102c3cd997ff1624c3e14870` |
| `runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/arrays.npz` | `0e9e5458f4f659fe92574951c1780120ed41973bb520eb41b38bd12410586abe` |
| `runs/20260910_qcd_quark_meson_carrier/amendment-2/verification/verification.json` | `59e18ba7208ad94a4997e6b36b4b9364bdabd78e676613dfc075eb2e4f357c76` |
| `runs/20260910_qcd_quark_meson_carrier/amendment-2/verification/verification_arrays.npz` | `e568846985cc4f3ea03ad7c557a16a518170806d3baa5bcfcad354dc737f01a3` |

The action, physical parameters, fixed profiles and radial Hamiltonian are those in `computations/qcd-quark-meson-carrier-prereg.md` §§1–3. The endpoint radius is fixed to

$$R_0=0.5368112726086816\ {\rm fm}.$$


## 2. Vanishing-regulator sequence

Reconstruct the cell-centred weighted radial Hamiltonian without importing either upstream calculation program. At each requested field point compute the nodeless in-gap state of smallest $|E|$ on

$$N_r\in\{1200,2400,4800,9600\},\qquad r_{\max}=12\ {\rm fm}.$$

The Wilson term remains

$$
\mathcal W_{\Delta r}
=\frac{\hbar c\,\Delta r}{2}D_h^\dagger{}_WD_h,
$$

so its leading regulator bias is linear in $h=1/N_r$. Fit all four values by unweighted least squares to

$$
E_N=E_\infty+c_1h+c_2h^2.
$$

Also fit the last three values to the same form. Record the four-point RMS residual and the difference between the two intercepts. The retained extrapolation uncertainty is

$$
\delta E_\infty
=\max\!\left(
0.20\ {\rm MeV},
2|E_\infty^{(4)}-E_\infty^{(3)}|,
2\,\mathrm{RMS}_{(4)}
\right).
$$

The $0.20\ {\rm MeV}$ floor is fixed before the calculation and exceeds the shooting solver’s root tolerance by many orders of magnitude.

Run this sequence at $R_0,a=1$ and at every retained primary envelope point with

$$a=0.40,0.45,\ldots,1.00.$$

Meson energies are taken from the immutable primary receipt because the independent 512-point Gauss–Legendre reconstruction agrees with them below $5\times10^{-15}$ relative error at every checked point.

## 3. Resolved-branch overlap

The independent shooting scan searched only

$$-0.999M_q\le E\le0.999M_q.$$

Classify a finite-grid state as independently resolvable for this diagnostic exactly when its frozen primary energy lies in that same closed interval. For each consecutive pair of resolvable rows, retain the corresponding frozen weighted overlap. Calculate the endpoint-radius and fixed-radius-amplitude minima separately. Rows outside the independent window remain part of QMC2’s frozen failure and cannot be relabelled as resolved states.

## 4. Continuum binding and barrier

At the endpoint define

$$
E_{B,\infty}=3E_\infty+E_\Phi,
\qquad
\Delta_B=3M_q-E_{B,\infty}.
$$

Compare $E_\infty$ with the immutable independent shooting level and the independent radius reconstruction. Retain the independent shooting RMS radius.

For the formation envelope, the analytic $R\to0$ limit is $3M_q$ for $a\le0.35$. For every computed row with $a\ge0.40$, define

$$
B_a=3E_{\infty,a}+E_{\Phi,a}-3M_q,
\qquad
B_a^+=B_a+3\delta E_{\infty,a}.
$$

The reconstructed reduced barrier and its conservative upper value are

$$
B=\max(0,\max_a B_a),
\qquad
B^+=\max(0,\max_a B_a^+).
$$

This calculation evaluates the same fixed two-parameter hedgehog envelope. It supplies no path-integral rate or dynamical basin.

## 5. Frozen decisions

### QMQ1—regulator-bias identification

`PASS` requires all requested spectra to be finite and nodeless; every four-point fit RMS below $0.10\ {\rm MeV}$; every three-point/four-point intercept difference below $0.20\ {\rm MeV}$; endpoint $E_\infty$ within $0.50\ {\rm MeV}$ of the independent two-sided shooting value; endpoint total energy within $2\ {\rm MeV}$ of the independently reconstructed total; and the sign of $E_N-E_\infty$ to remain constant over the four endpoint grids. Otherwise QMQ1 is `FAIL`.

### QMQ2—resolved branch and conditional binding

`SUPPORTS` requires QMQ1, both resolved-overlap minima above $0.70$, $\Delta_B>5\ {\rm MeV}$ after subtracting $3\delta E_\infty$, an independent selected radius within $0.02\ {\rm fm}$ of $R_0$, and the independent RMS radius in $[0.2,1.5]\ {\rm fm}$. `CONTRADICTS` applies if the qualified upper endpoint energy lies at or above $3M_q$. Other outcomes are `INCONCLUSIVE`.

### QMQ3—reduced formation accessibility

`SUPPORTS` requires QMQ2 and $B^+\le155\ {\rm MeV}$. `CONTRADICTS` applies if QMQ2 is `CONTRADICTS`. Other outcomes are `INCONCLUSIVE`.

### QMQ4—physical completion

QMQ4 remains `FAIL`. The qualification adds no Cassi selection rule for the empirical action, renormalized Dirac sea, confinement, nonradial continuum stability, thermal formation rate, nucleon observable map or baryogenesis mechanism. It sets
`complete_physical_matter_formation=false`.

## 6. Independent reconstruction

The primary program writes every sparse-grid eigenvalue, fit input, fit coefficient and envelope bound to
`runs/20260910_qcd_quark_meson_carrier/qualification/primary/`. A separate verifier must not import the primary program. It must:

1. validate the four immutable input identities and all new source identities;
2. reconstruct both polynomial fits directly from the raw grid rows;
3. reproduce the uncertainty formula, resolved-pair selection, binding margin and barrier bounds;
4. compare every copied upstream value byte-for-byte with its source receipt;
5. require exact verdict agreement; and
6. fail closed on a missing, altered, nonfinite or schema-invalid input.

The independent output is
`runs/20260910_qcd_quark_meson_carrier/qualification/verification/`.

## 7. Stopping rule

Execute the frozen sequence once. Preserve a failed verdict. A code defect requires a named amendment, a changed protocol hash and fresh output directories. Physical parameters, grid counts, field points, fit forms, uncertainty floor and verdict thresholds cannot change after execution starts.

The original QMC2 `FAIL` remains the accepted verdict of `computations/qcd-quark-meson-carrier-prereg.md`. QMQ verdicts report only this declared numerical qualification.

<!-- qcd-quark-meson-carrier-qualification:end -->

## References

- `computations/qcd-quark-meson-carrier-prereg.md`—frozen action, state, discretization, current, initial conditions and QMC verdict tree.
- D. Diakonov, [“Chiral Quark-Soliton Model”](https://arxiv.org/abs/hep-ph/9802298)—continuum radial Hamiltonian and occupied valence branch.
