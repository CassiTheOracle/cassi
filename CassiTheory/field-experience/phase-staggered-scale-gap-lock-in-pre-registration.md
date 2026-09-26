# Phase-staggered scale-gap lock-in closure pre-registration

## Status: Preregistered—August 2026

## 1. Trigger and question

The amended time-domain execution in

```text
runs/20260827T093616Z_phase_staggered_scale_gap/results.json
```

satisfies parent radial physics metrics D2–D7. Parent Stage D remains
`INCONCLUSIVE`: D1 sub-gap attenuation fails, and the strict all-metrics-finite
reading also flags the intentionally undefined D0/D3 reference and fit fields.
Parent Stage C separately fails registered C4 despite passing the executed
looser Boolean. This closure does not relabel any parent stage. The D0 lock-in
retains a travelling turn-on component with

\[
k=0.210257903848,
\qquad
R^2=0.982455621465,
\]

although the locked drive frequency is below the imbalance propagation
threshold. The undamped continuum contains arbitrarily slow above-gap
transients, so no finite waiting horizon isolates the steady harmonic response
by transit time alone.

This closure probe asks whether the exact locked-frequency boundary-value
problem has the declared evanescent D0 channel while preserving the D1 and D2
propagating dispersion measurements.

## 2. Frozen equation

For either radial normal mode $a\in\{\rho,\epsilon\}$, set

\[
u_a(r,t)=\Re[U_a(r)e^{-i\Omega t}].
\]

The live continuum equations reduce to

\[
U_a''+k_a^2U_a=-f(r),
\]

with

\[
k_\rho^2=\Omega^2,
\qquad
k_\epsilon^2=\Omega^2-\varphi^2.
\]

Use

\[
\varphi=\frac{1+\sqrt5}{2},
\qquad
c=\omega_0=1,
\]

and the same source profile as the parent probe,

\[
f(r)=r\exp[-r^2/(2\sigma^2)],
\qquad
\sigma=0.4.
\]

The source is normalized to unit maximum. No random number, optimization,
frequency scan, or adaptive window is permitted.

## 3. Frozen discretization and boundaries

| Quantity | Value |
|---|---:|
| $r_{\max}$ | $60$ |
| $\Delta r$ | $0.025$ |
| fit window, propagating | $10\le r\le40$ |
| fit window, evanescent | $2\le r\le10$ |

Use centered second differences on the same $2{,}401$ radial points as the
parent probe. Set

\[
U(0)=0.
\]

At $r=r_{\max}$ use the exact channel-type boundary:

\[
U'(r_{\max})=ikU(r_{\max})
\]

for $k^2>0$, and

\[
U'(r_{\max})=-\kappa U(r_{\max}),
\qquad
\kappa=\sqrt{-k^2},
\]

for $k^2<0$.

Solve the resulting complex tridiagonal system with the Thomas algorithm.
No dense inverse is permitted.

## 4. Frozen arms

| Arm | $\Omega$ | Channel |
|---|---:|---|
| L0 | $0.9\varphi$ | $\epsilon$ |
| L1 | $\varphi^{3/2}$ | $\rho$ and $\epsilon$ |
| L2 | $2.5$ | $\rho$ and $\epsilon$ |

For propagating channels, fit unwrapped phase to $kr+\delta$ on
$10\le r\le40$. For L0, fit

\[
\ln|U_\epsilon|=-\kappa r+b
\]

on $2\le r\le10$.

## 5. Quality gates

- **Q1—finite:** all matrix coefficients, solutions, fits, and metrics are finite;
- **Q2—linear residual:**

  \[
  \frac{\|AU-b\|_\infty}{\max(\|b\|_\infty,1)}<10^{-10};
  \]

- **Q3—fit quality:** every declared phase or log-amplitude fit has $R^2\ge0.99$;
- **Q4—amplitude:** median amplitude in each fit window exceeds $10^{-12}$.

Failure of any quality gate gives `INCONCLUSIVE`. No replacement run is
permitted.

## 6. Physics gates

- **L1—sub-gap decay:** fitted $\kappa$ agrees with

  \[
  \sqrt{\varphi^2-(0.9\varphi)^2}
  \]

  within $2\%$;
- **L2—sub-gap attenuation:**

  \[
  |U_\epsilon(30)|/|U_\epsilon(12)|\le10^{-2};
  \]

- **L3—tuned propagation:** the L1 fitted ratio

  \[
  k_\rho/k_\epsilon
  \]

  agrees with $\varphi$ within $2\%$;
- **L4—generic control:** the L2 fitted ratio differs from $\varphi$ by at least $0.1$;
- **L5—parent agreement:** the L1 and L2 fitted wavenumbers agree with the valid parent time-domain fits within $2\%$.

## 7. Decision tree

- `PASS` if Q1–Q4 and L1–L5 pass.
- `FAIL` if Q1–Q4 pass and any physics gate fails.
- `INCONCLUSIVE` if any quality gate fails.

A `PASS` closes the parent D0 quality question and establishes the conditional
frequency-domain channel gap. It does not convert the parent time-domain run
into a pass; both raw receipts remain recorded. The combined campaign may use
the valid parent D2–D7 metrics together with this independent closure of parent D1.

## 8. Raw artifact and stopping rule

The single execution writes

```text
runs/<UTC timestamp>_phase_staggered_scale_gap_lockin/results.json
```

Permitted preflight is limited to source inspection and `python -m py_compile`.
Run once after the script is frozen. A failed gate is the final closure result.
