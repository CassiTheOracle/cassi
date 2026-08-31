# Qi-Loop Mass Cascade: Conditional Two-Fluid De-Resonant Rings

## Status: Derived conditional counterflow selection and supplied-ring algebra / Tested conditional branches / Hypothesized physical realization—August 2026

## Abstract

The canonical density conversion, combined with counteroriented compact-phase
currents, equal mobilities, zero net current, and adiabatic current adjustment,
conditionally selects the local phase-gradient ratio
\(\alpha=\theta_I'/\theta_Y'\to\varphi\). Finite compact windings realize
rational ratios whose Fibonacci pairs are the record approximants to the
irrational target. With a positive supplied ring Hamiltonian, those
near-closures have a stable
stationary length and a conditional \(\varphi\)-scaled energy branch. The
frozen computation in `field-experience/qi-loop-mass-cascade-report.md`
verifies that branch and leaves the physical mass selector open: many stable
primitive modes occupy each cascade cell, and the low-winding energies depend
on the declared inter-fluid coefficient.

This document keeps the canonical density state unchanged. Its scalar
coherence diagnostic is \(q\), while \(q_{\mathrm w}\) below is only a
compact Yin winding. A compact phase, ring topology, and physical particle
identification require additional constitutive structure.

---

## 1. Two roles for \(\varphi\)

The dimensionful cascade uses \(\varphi\) as a separation between adjacent
scale rungs,

\[
\ell_N=\ell_{\rm Pl}\varphi^N.
\]

The de-resonance proposal has a second, coordinate-specific role for
\(\varphi\). For compact phase-gradient magnitudes
\(k_Y=\theta_Y'>0\) and \(k_I=\theta_I'>0\), counteroriented strand currents
obey

\[
J_Y=+\mu_YE_Yk_Y,
\qquad
J_I=-\mu_IE_Ik_I.
\]

Equal mobilities and zero net current give

\[
\alpha\equiv\frac{k_I}{k_Y}=\frac{E_Y}{E_I}.
\]

The canonical homogeneous conversion law therefore selects
\(\alpha\to\varphi\) under adiabatic enforcement of this current closure.
`principles/de-resonance-principle.md` gives the exact transient, stability
proof, controls, and PC1–PC7 verification. Uniform finite winding restricts
\(\alpha\) to \(q_{\mathrm w}/p\), whose record approximants form the
Fibonacci branch used below. A fixed winding sector cannot track the
continuous local target; physical tracking requires local noncompact
gradients or phase slips between sectors. Separate compact phases, a common
ordinary loop, opposite orientation, equal effective mobilities, zero net
current, adiabatic adjustment, and winding-sector dynamics remain explicit
physical assumptions.

---

## 2. Conditional compact-ring algebra

Let \(s\in[0,L]\) and impose

\[
\theta_Y(s+L)=\theta_Y(s)+2\pi p,
\qquad
\theta_I(s+L)=\theta_I(s)+2\pi q_{\mathrm w},
\qquad
p,q_{\mathrm w}\in\mathbb Z_{>0}.
\]

For positive \(T,K_Y,K_I,K_\Delta\), declare

\[
H_\alpha=T L+\frac12\int_0^L\!\left[
K_Y(\theta_Y')^2+K_I(\theta_I')^2+
K_\Delta(\theta_I'-\alpha\theta_Y')^2
\right]ds.
\]

Uniform winding gives

\[
\theta_Y'=\frac{2\pi p}{L},
\qquad
\theta_I'=\frac{2\pi q_{\mathrm w}}{L},
\]

and therefore

\[
A_\alpha=K_Yp^2+K_Iq_{\mathrm w}^2+
K_\Delta(q_{\mathrm w}-\alpha p)^2,
\]

\[
H_\alpha(L)=TL+\frac{2\pi^2A_\alpha}{L}.
\]

The stationary radius and energy are

\[
L_*=\sqrt{\frac{2\pi^2A_\alpha}{T}},
\qquad
H_*=2\sqrt{2\pi^2TA_\alpha},
\qquad
H_\alpha''(L_*)=\frac{4\pi^2A_\alpha}{L_*^3}>0.
\]

The phase-gradient Hessian is

\[
G_\alpha=
\begin{pmatrix}
K_Y+\alpha^2K_\Delta&-\alpha K_\Delta\\
-\alpha K_\Delta&K_I+K_\Delta
\end{pmatrix}.
\]

Positive coefficients make \(G_\alpha\) positive definite. The corresponding
uniform currents are

\[
J_Y=(K_Y+\alpha^2K_\Delta)\theta_Y'-\alpha K_\Delta\theta_I',
\qquad
J_I=(K_I+K_\Delta)\theta_I'-\alpha K_\Delta\theta_Y'.
\]

These facts are algebraic consequences of the supplied compact Hamiltonian.
They do not supply a compact coordinate, an energy functional, or a
circulation law for the canonical PDE.

---

## 3. Fibonacci near closure

For irrational \(\alpha=\varphi\), finite integer windings cannot satisfy
\(q_{\mathrm w}=\varphi p\) exactly. The Fibonacci pairs satisfy the exact
identity

\[
F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}.
\]

Thus \((p,q_{\mathrm w})=(F_n,F_{n+1})\) approaches the declared
phase-gradient ratio exponentially. The receipt verifies the frozen record
sequence through denominator 144 and distinguishes it from a rational
\(3/2\) exact-closure control and a \(\sqrt2\) irrational control. This
establishes a conditional arithmetic skeleton for the compact construction.

---

## 4. Conditional scale covariance

The phase-gradient ratio does not determine a tension law. If one separately
declares

\[
T_N=\varphi^{-2N}T_0,
\qquad K_{Y,I,\Delta;N}=K_{Y,I,\Delta;0},
\]

then the ring formulas give

\[
L_{*,N}=\varphi^N L_{*,0},
\qquad
H_{*,N}=\varphi^{-N}H_{*,0}.
\]

The equality is conditional on the supplied scaling relation. It provides a
consistent bridge from the compact branch to the external scale ladder in
`foundations/dimensionful-cascade.md`.

---

## 5. What the receipt selects

The tested branch satisfies the arithmetic and positive-loop gates, with
Fibonacci energy-ratio residual
\(1.060031841522592\times10^{-6}\) and rung-label residual
\(2.578928547167112\times10^{-6}\). It therefore gives

\[
\boxed{\text{closed Qi-loop skeleton: EMERGES CONDITIONAL}.}
\]

The same receipt scans all primitive \(1\le p\le34\),
\(1\le q_{\mathrm w}\le55\) modes. It finds 1,163 stable modes, as many as
528 in one occupied \(\varphi\)-log energy cell. Across the declared
\(K_\Delta\in\{0,0.25,1,4\}\) arm, the largest relative-rung span is
\(0.1146965060733196\), above the frozen \(0.01\)-rung selector threshold.
Consequently,

\[
\boxed{\text{unique mass positions: DOES NOT EMERGE}.}
\]

The conditional loop energy may be written \(m^{\rm loop}_{p,q_{\mathrm w}}=H_*\)
in \(c=1\) units. A physical hierarchy would require a separate dimensional
map and a selector factor,

\[
m_{N,a}=M_{\rm Pl}\varphi^{-N}\eta_a,
\]

where \(a\) labels an allowed mode and \(\eta_a\) is unresolved. The receipt
shows that the present ring Hamiltonian does not determine this factor.

---

## 6. Framework boundary

The canonical two-fluid model remains a nonnegative real-density system. Its
\(q\) is a scalar diagnostic, and its density-plane conversion is rank-one
relaxation. `foundations/qi-flow-double-helix.md` supplies exact coordinate
lifts and records the extra assumptions required for compact spatial phases.
`field-experience/phase-staggered-scale-gap-report.md` separately finds that a
phase-only chain has no spectral gap and that link-magnitude modulation needs a
supplied constitutive law.

`computations/phase-slip-selection-report.md` tests one passive
complex-amplitude candidate $M_0$ for the required transition law. The frozen
$N=64$ and $N=96$ arms both pass sampled descent and return zero
$\varphi$-band counteroriented sectors. Its protocol verdict is
$\mathrm{REJECT}\ M_0$; a physical compact-current and phase-slip law remains
open.

The preregistered open-space campaign in
`field-experience/toroidal-coherence-survival-report.md` supplies a complex
two-component Schrödinger–Poisson realization. V5 passes G1–G4 and Q1–Q5
with independent verification, then fails all three survival gates. The
declared seed changes Yang winding from `+2` to `+3`, contracts to radius
ratio `0.4468592782418393`, and retains `0.3459793652013782` of its initial
helical order by `t=4`. Its registered finite-time result is `DOES NOT
EMERGE`.

The compact-loop result therefore adds a narrow conditional result: \(\varphi\)
can organize the finite near-closure sequence of a declared two-fluid
phase-gradient ratio. The physical questions are topology formation, coupling
selection, dimensional conversion, and a particle-independent observable.

---

## References

- `field-experience/qi-loop-mass-cascade-pre-registration.md`—frozen model and decision tree
- `field-experience/qi-loop-mass-cascade-report.md`—executed receipt and independent verification
- `field-experience/toroidal-coherence-survival-report.md`—three-dimensional V1–V5 receipts and adopted campaign verdict
- `field-experience/toroidal-coherence-survival-pre-registration.md`—frozen V1 open-space protocol
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`—frozen V2 initialization protocol
- `field-experience/toroidal-coherence-survival-v3-pre-registration.md`—frozen V3 normalized-phase and arm protocol
- `field-experience/toroidal-coherence-survival-v4-pre-registration.md`—frozen V4 complex128 convergence protocol
- `field-experience/toroidal-coherence-survival-v5-pre-registration.md`—frozen V5 fourth-order diagnostic-precision protocol
- `principles/de-resonance-principle.md`—arithmetic extremality and physical mapping boundary
- `computations/phase-slip-selection-report.md`—tested passive compact-field candidate and $\mathrm{REJECT}\ M_0$ receipt
- `foundations/dimensionful-cascade.md`—external Planck anchor and rung ladder
- `foundations/qi-flow-double-helix.md`—canonical \(q\), density-plane angle, and phase-lift boundary
- `foundations/cassi-first-principles.md`—canonical real-density PDE and conversion law
- `field-experience/phase-staggered-scale-gap-report.md`—conditional phase/gap evidence
