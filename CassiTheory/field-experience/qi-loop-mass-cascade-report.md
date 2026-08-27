# Qi-Loop Mass-Cascade Report

## Status: Tested—August 2026

## Abstract

This report records one frozen evaluation of a conditional compact two-fluid
ring. The declared phase-gradient de-resonance ratio
\(\alpha=\varphi\) produces the Fibonacci near-closure branch and a positive
stationary loop sector under the supplied Hamiltonian. The branch passes the
arithmetic, loop-stability, and supplied scale-covariance gates. It does not
supply unique mass positions: the primitive-mode scan retains 1,163 stable
modes across occupied cascade cells, and the coefficient-sensitivity gate
fails at the low-winding end. The resulting terminal outcomes are
**EMERGES CONDITIONAL** for the closed Qi-loop skeleton and **DOES NOT EMERGE**
for unique mass positions.

The compact phases, ring topology, normalized coefficients, and tension law
are declared test architecture. The canonical state remains the real-density
pair \(E_Y,E_I\) with scalar coherence diagnostic \(q\); the winding symbol
\(q_{\mathrm w}\) in this report is an integer Yin winding and carries no
canonical-Qi meaning. No particle catalog or measured particle mass enters the
calculation.

---

## 1. Frozen record

| Item | Frozen artifact |
|---|---|
| Protocol | `field-experience/qi-loop-mass-cascade-pre-registration.md` |
| Primary probe | `field-experience/qi_loop_mass_cascade_probe.py` |
| Primary receipt | `runs/20260827T120451Z_qi_loop_mass_cascade/results.json` |
| Independent verifier | `field-experience/verify_qi_loop_mass_cascade.py` |
| Verification receipt | `runs/20260827T120451Z_qi_loop_mass_cascade/verification.json` |

The primary source hash is
`f4cd6a6431b53512b1687284e50dd44216562a6831643194ef1d00fdb5c99003`.
The frozen protocol hash is
`6bf48044459cee2453ae97c09f10fbc81c3b0eacdd38ca8208ec3c7ab2c587c2`.
The independent-verifier hash is
`8ed9da873d1be88a61b0d0a6614671e49b42de57b338e06e12c48ca2191f04ed`.
The verifier recomputes 172 Boolean values and 692 finite scalars, reports
zero differences, and passes Q5.

The primary and verifier execute once each. The raw receipts remain
untracked regeneration artifacts; their documented exemption is in
`BROKEN_REFS.md`.

---

## 2. Conditional model

Let the compact phase windings be \(p,q_{\mathrm w}\in\mathbb Z_{>0}\),
with the declared de-resonance proposal expressed as a preferred gradient
ratio \(q_{\mathrm w}/p=\alpha=\varphi\). The test Hamiltonian is

\[
H_\alpha=T L+\frac12\int_0^L\!\left[
K_Y(\theta_Y')^2+K_I(\theta_I')^2+
K_\Delta(\theta_I'-\alpha\theta_Y')^2
\right]ds,
\]

with \(T=K_Y=K_I=K_\Delta=1\) as normalized probe controls. Uniform winding
gives

\[
A_\alpha(p,q_{\mathrm w})=
K_Yp^2+K_Iq_{\mathrm w}^2+
K_\Delta(q_{\mathrm w}-\alpha p)^2,
\]

\[
H_\alpha(L;p,q_{\mathrm w})=TL+
\frac{2\pi^2A_\alpha(p,q_{\mathrm w})}{L},
\qquad
L_*=\sqrt{\frac{2\pi^2A_\alpha}{T}},
\qquad
H_*=2\sqrt{2\pi^2TA_\alpha}.
\]

The optional scale-covariance arm declares
\(T_N=\varphi^{-2N}T_0\) with fixed \(K\), yielding
\(L_{*,N}=\varphi^N L_{*,0}\) and
\(H_{*,N}=\varphi^{-N}H_{*,0}\). That tension law is supplied separately
from the phase-gradient ratio.

---

## 3. Arithmetic and loop gates

### 3.1 De-resonant near closure

The retained \(\varphi\) records through denominator 144 are

\[
(1,2),(2,3),(3,5),(5,8),(8,13),(13,21),(21,34),
(34,55),(55,89),(89,144),(144,233).
\]

They equal the frozen Fibonacci list. The identity

\[
F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}
\]

has maximum observed absolute residual
\(1.0165147637976205\times10^{-14}\), below the \(10^{-12}\) gate.
The rational control closes at \((2,3)\) exactly. The finite-denominator
contrast with the \(\sqrt2\) control is

\[
144\,|233-144\varphi|-70\,|99-70\sqrt2|
=0.09366495891647209,
\]

above the preregistered \(0.08\) floor. Stage A passes.

### 3.2 Positive supplied ring sector

Nineteen modes cover all \(\varphi\) records and both control record lists.
The maximum stationarity residual is
\(4.440892098500626\times10^{-16}\). The minimum radial Hessian is
\(0.005176983387919623\), the minimum one-percent energy excess is
\(0.0011106234451273543\), and the minimum phase-Hessian eigenvalue is
\(0.4384471871911697\). The centered periodic current-divergence maximum is
zero while the minimum current norm is \(0.3484501483718822\).

The supplied scale arm has maximum relative residuals
\(5.525059302249192\times10^{-16}\) for \(L_*\) and
\(6.107686171369736\times10^{-16}\) for \(H_*\). Stage B passes. These
numbers establish the conditional ring construction and supplied tension law;
they do not establish spontaneous compact topology, open-space binding, or an
endogenous tension selector.

---

## 4. Mass-position sufficiency gates

The classical loop proxy is \(m^{\rm loop}_{p,q_{\mathrm w}}=H_*\) in
\(c=1\) units. It is a conditional loop-energy proxy, with no
\(\hbar\Omega\) single-quantum identification.

| Gate | Frozen discriminator | Receipt | Terminal reading |
|---|---|---:|---|
| C1 | One stable primitive mode per occupied \(\varphi\)-log cell | 1,163 stable primitive modes; up to 528 in one cell | FAIL |
| C2 | Constitutive span \(\le0.01\) rung across \(K_\Delta\in\{0,0.25,1,4\}\) | \(0.1146965060733196\) rung at \((1,2)\) | FAIL |
| C3 | Fibonacci-branch energy ratio residual \(<10^{-4}\) | \(1.060031841522592\times10^{-6}\) | PASS |
| C4 | Fibonacci-branch integer-label distance \(<10^{-4}\) rung | \(2.578928547167112\times10^{-6}\) rung | PASS |

The high-winding records approach constitutive insensitivity within this
finite arm: the span is \(0\) at the \((13,21)\) anchor and remains below
\(8.1\times10^{-6}\) rung from \((21,34)\) through \((144,233)\). The
registered C2 discriminator covers the complete frozen record list, so its
\((1,2)\) failure controls the unique-position verdict.

The receipt therefore separates two statements:

\[
\text{Fibonacci near-closure branch: EMERGES CONDITIONAL},
\]

\[
\text{unique physical mass-position law: DOES NOT EMERGE}.
\]

---

## 5. Interpretation boundary

The result gives a compact way to express the two roles of \(\varphi\):
scale separation between adjacent cascade rungs and de-resonant separation of
the declared Yang/Yin phase gradients. Irrationality prevents exact finite
winding closure, while the Fibonacci pairs provide its best finite
near-closures. The positive ring Hamiltonian makes those pairs a stable
conditional branch.

A physical mass construction still needs a selector. Conditional on both an
external cascade anchor and a physical loop identification, it has the form

\[
m_{N,a}=M_{\rm Pl}\,\varphi^{-N}\eta_a,
\]

where \(a\) labels a topological/constitutive mode and \(\eta_a\) remains
unselected. C1 and C2 show that the present supplied ring law leaves this
factor open. `field-experience/phase-staggered-scale-gap-report.md` provides
a separate boundary: a phase-only chain is gapless, and physical link-magnitude
modulation requires a supplied constitutive relation.

The next decisive construction must derive or constrain compact topology,
mode selection, and the coefficient law from a specified field dynamics. It
requires a new preregistration and must retain the same separation between
conditional algebra, physical identification, and particle data.

---

## References

- `field-experience/qi-loop-mass-cascade-pre-registration.md`—frozen equations, gates, and verdict tree
- `foundations/qi-loop-mass-cascade.md`—conditional ring algebra and framework boundary
- `principles/de-resonance-principle.md`—Hurwitz/Lagrange arithmetic and physical de-resonance scope
- `foundations/qi-flow-double-helix.md`—canonical scalar \(q\) and conditional spatial phase lifts
- `foundations/dimensionful-cascade.md`—externally anchored \(\varphi\)-ladder
- `foundations/rung-offset-mechanism.md`—catalog selection boundary
- `field-experience/phase-staggered-scale-gap-report.md`—phase-only gap and supplied link-modulation result
