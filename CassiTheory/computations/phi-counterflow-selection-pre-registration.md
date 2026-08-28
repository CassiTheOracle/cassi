# Phi Counterflow Selection Verification Pre-Registration

## Status: Pre-registration—August 2026

## Purpose

This computation checks the exact conditional bridge from the canonical
Yang/Yin density attractor to the compact phase-gradient ratio used in
`foundations/qi-loop-mass-cascade.md`. The bridge adds a zero-net-current,
equal-mobility closure for two counteroriented phase currents. It checks the
conversion transient, the induced phase-ratio flow, the finite-exposure
boundary, the mobility and through-current controls, and the Fibonacci compact
near-closures.

The computation tests algebra within the stated closure. Physical realization
of separate compact phases, equal mobilities, zero net current, adiabatic
current adjustment, and persistent gate exposure remains an experimental
question.

## Frozen construction

For a homogeneous conversion-only parcel, define

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I,
\qquad
\kappa(t)=\lambda[1-q(t)]\geq0.
$$

The canonical conversion contribution is

$$
\dot E_Y=-\kappa\varepsilon,
\qquad
\dot E_I=+\kappa\varepsilon.
$$

The conditional compact-phase lift assigns nonnegative strand-coordinate
phase gradients $k_Y=\partial_s\theta_Y$ and
$k_I=\partial_s\theta_I$. The physical strand orientations are opposite, so
with positive mobilities $\mu_Y,\mu_I$ the signed currents are

$$
J_Y=+\mu_YE_Yk_Y,
\qquad
J_I=-\mu_IE_Ik_I.
$$

For imposed net current $J_0=J_Y+J_I$ and $k_Y>0$,

$$
\alpha\equiv\frac{k_I}{k_Y}
=\frac{\mu_Y}{\mu_I}\frac{E_Y}{E_I}
-\frac{J_0}{\mu_IE_Ik_Y}.
$$

The selection arm uses equal mobilities and zero net current, giving
$\alpha=E_Y/E_I$. A compact loop restricts the uniform gradient ratio to
$q_{\rm w}/p$ for positive integer windings $(p,q_{\rm w})$.

## Frozen inputs

- $\varphi=(1+\sqrt5)/2$.
- Constant-exposure arm: $\kappa=0.07$ in solver-time units and
  $t\in[0,120]$.
- Initial states: $(E_Y,E_I)=(2.0,0.7)$ and $(0.5,1.4)$.
- Numerical integration: fixed-step fourth-order Runge–Kutta with
  $\Delta t=0.002$.
- Finite accumulated exposures: $K\in\{0,0.4,50\}$, where
  $K=\int\kappa(t)\,dt$.
- Mobility controls: $\mu_Y/\mu_I\in\{0.5,1,1.7\}$.
- Through-current control: $\mu_Y=\mu_I=1$, $E_{I,*}=1$, $k_Y=0.8$,
 and $J_0\in\{-0.2,0,0.2\}$.
- Compact search: $1\leq p\leq144$ with
  $q_{\rm w}$ the nearest positive integer to $\varphi p$.
- Absolute tolerance $10^{-10}$ unless a gate states another bound.
- Python standard library only; no optimizer, fit, random input, or external
  data.

## Frozen gates

### PC1—Canonical conversion identities

The computed right-hand side must satisfy

$$
\dot\rho=0,
\qquad
\dot\varepsilon=-\kappa(1+\varphi)\varepsilon
=-\kappa\varphi^2\varepsilon
$$

for both initial states. Each residual must be at most $10^{-12}$.

### PC2—Counterflow phase-ratio identity

With $J_0=0$ and $\mu_Y=\mu_I$, the current closure must give

$$
\alpha=\frac{E_Y}{E_I}.
$$

The numerical current sum must be zero and the phase-ratio residual must be at
most $10^{-12}$ for both initial states.

### PC3—Exact transient and stability

For constant $\kappa$, define

$$
\varepsilon(t)=\varepsilon_0e^{-\varphi^2\kappa t},
\qquad
\alpha_{\rm exact}(t)
=\frac{\varphi\rho+\varepsilon(t)}{\rho-\varepsilon(t)}.
$$

The integrated density ratio must agree with $\alpha_{\rm exact}$ to
$10^{-9}$ at $t=120$. The ratio must move monotonically toward $\varphi$ from
both sides, remain positive, and finish within $10^{-8}$ of $\varphi$.

### PC4—Projective flow law

In the equal-mobility, zero-net-current arm, direct differentiation must give

$$
\dot\alpha=-\kappa(1+\alpha)(\alpha-\varphi).
$$

The right-hand side obtained from the two density equations and the displayed
closed form must agree to $10^{-12}$ at both initial states. Linearization at
the positive fixed point must give the negative eigenvalue
$-\kappa(1+\varphi)=-\kappa\varphi^2$.

### PC5—Exposure boundary

Using the exact exposure solution

$$
\varepsilon(K)=\varepsilon_0e^{-\varphi^2K},
$$

$K=0$ must leave the initial ratio unchanged, $K=0.4$ must leave a nonzero
phase-ratio residual, and $K=50$ must place the ratio within $10^{-12}$ of
$\varphi$. This gate records the requirement of unbounded accumulated exposure
for asymptotic selection.

### PC6—Mobility and through-current controls

At the density fixed point, zero net current must give

$$
\alpha_*=\frac{\mu_Y}{\mu_I}\varphi.
$$

The three frozen mobility ratios must produce three distinct phase ratios and
only the unit ratio may equal $\varphi$. With nonzero $J_0$,

$$
\alpha_*=\varphi-\frac{J_0}{\mu_IE_{I,*}k_Y},
$$

so the two nonzero through-current controls must lie on opposite sides of the
zero-current value. Equality residuals must be at most $10^{-12}$ and each
required separation must exceed $10^{-3}$.

### PC7—Compact Fibonacci near-closures

For $p=F_n$ and $q_{\rm w}=F_{n+1}$, $n=2,\ldots,12$, the computation must
verify

$$
F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}
$$

to $10^{-12}$. Exhaustive scanning through $p=144$ must show that each new
record minimum of $|q_{\rm w}-\varphi p|$ occurs at the Fibonacci denominators

$$
1,2,3,5,8,13,21,34,55,89,144.
$$

This gate tests the compact approximation sequence generated when an
irrational local target meets integer winding closure.
Winding-sector dynamics, energetic selection among record candidates, and a
physical cutoff on the winding search remain outside this gate.

## Decision and stopping rule

- **PASS:** PC1–PC7 all pass on the first protocol-complete execution.
- **FAIL:** any equality exceeds its tolerance, a monotonicity or sign condition
  fails, a required control separation is absent, or the record denominators
  differ from the frozen list.
- Execution stops after the first completed gate ledger. A source-code defect
  that prevents execution may be corrected without changing the construction,
  inputs, equations, tolerances, or decision rules; the correction must be
  reported with the result.

## Protocol normalization

PC6 uses $E_{I,*}=1$ in both the displayed denominator and the frozen-input
list, matching the verifier normalization. This value is part of the frozen
construction. A reportable ledger requires a protocol-complete execution with
the normalization explicitly specified.
