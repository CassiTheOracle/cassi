# Yin–Yang–Qi Dynamical Geometry Closure Preregistration

## Status: Preregistered—September 2026

## 1. Question

Can the canonical Yin/Yang density dynamics, the positive Hermitian coherence fibre, the conditional relative-$U(1)_Q$ transport sector, and the charged-endpoint ledgers be assembled into one explicit **open-system effective closure** without presenting a microscopic unified action that has not been derived?

This receipt tests seven conditional claims:

1. the canonical scalar $q(E_Y,E_I)$ satisfies $0\le q<1$ for every finite nonnegative density state;
2. the two-jump nonlinear pointwise Lindblad-form conversion vector field reduces exactly to the canonical $q$-gated diagonal PDE, preserves the positive cone, and preserves total density;
3. the conversion generator is covariant under the declared relative $U(1)_Q$ frame transformation;
4. its normalized Bloch-coordinate reduction gives the registered composition and transverse-coherence rates;
5. the undriven homogeneous minimal lift cannot support nonzero stationary transverse coherence at finite density when $\lambda>0$;
6. the rail source, endpoint source, and Wilson transport incidence close the total endpoint-number and relative-charge ledgers under the registered orientation;
7. the zero-conversion, diagonal-state, and zero-Wilson-coupling controls recover their registered boundaries.

The closure under test is an effective open dynamical system. It is not a single microscopic action. The conservative graph action, reduced conversion generator, and endpoint channels retain their separate source status.

## 2. Source Boundary

The frozen authorities are:

- `foundations/cassi-first-principles.md` §§1.3 and 2.1—the canonical real-density state, scalar $q$, and gated rank-one conversion;
- `foundations/physical-becoming-hierarchy.md` §4—the gradient-flow form, optional Markov bath, response functional, and reservoir boundary;
- `foundations/geometric-manifold-completion.md` §§2–4—the two-rail scale graph, positive Hermitian fibre, conditional relative-$U(1)_Q$ action, matrix continuity ansatz, and minimal two-jump conversion lift;
- `foundations/interscale-stress-attenuation-boundary.md` §§2–4—the distinction between number current, gauge current, mixed momentum stress, and physical force;
- `foundations/endpoint-link-and-localization-boundary.md` §§3.9–3.11—the endpoint continuity law, closed-domain zero mode, and separately declared Wilson transport;
- `foundations/particle-stationary-action-closure.md` §§1 and 8–9—the separate local-$SU(2)_Q$, second-order, fixed-$Q_C$ particle branch and its registered numerical boundary.

The final source remains downstream. Its gauge group, temporal order, carrier charge, and Gauss closure differ from the Abelian first-order graph sector. This receipt does not merge the two actions or reinterpret the registered particle campaign.

## 3. Canonical State and Gate

For finite reference-normalized densities,

$$
E_Y\ge0,
\qquad
E_I\ge0,
\qquad
\rho:=E_Y+E_I,
\qquad
\varepsilon:=E_Y-\varphi E_I.
$$

The canonical scalar diagnostic is

$$
\boxed{
q(E_Y,E_I)
:=
\frac{\rho^2}
{\rho^2+\varphi^{-2}+\varepsilon^2}.}
$$

The conversion rate is

$$
\boxed{
\gamma_{\rm conv}
:=\lambda(1-q),
\qquad
\lambda\ge0.}
$$

The additive $\varphi^{-2}$ term gives

$$
0\le q<1
$$

for every finite nonnegative state. The scalar $q$ remains a density-and-composition diagnostic. It is not identified with the optional off-diagonal fibre coherence, the relative connection, or its curvature.

## 4. Positive Hermitian Fibre and Conversion Lift

The conditional coherence fibre is

$$
\boxed{
\Gamma
:=
\begin{pmatrix}
E_Y&c^*\\
c&E_I
\end{pmatrix}
\in\operatorname{Herm}_2^+,}
\qquad
|c|^2\le E_YE_I.
$$

The canonical real-density sector is the diagonal subcone $c=0$.

Define the two directed jumps

$$
L_{Y\to I}
:=
\sqrt{\gamma_{\rm conv}}\,|I\rangle\langle Y|,
\qquad
L_{I\to Y}
:=
\sqrt{\varphi\gamma_{\rm conv}}\,|Y\rangle\langle I|.
$$

The frozen conversion generator is

$$
\boxed{
\mathcal L_{\rm conv}[\Gamma]
:=
\sum_{a\in\{Y\to I,I\to Y\}}
\left(
L_a\Gamma L_a^\dagger
-
\frac12\{L_a^\dagger L_a,\Gamma\}
\right).}
$$

The expected component reduction is

$$
\boxed{
\begin{aligned}
\dot E_Y\big|_{\rm conv}
&=-\gamma_{\rm conv}(E_Y-\varphi E_I),\\
\dot E_I\big|_{\rm conv}
&=+\gamma_{\rm conv}(E_Y-\varphi E_I),\\
\dot c\big|_{\rm conv}
&=-\frac{\varphi^2}{2}\gamma_{\rm conv}c.
\end{aligned}}
$$

Its diagonal reduction must agree exactly with the canonical PDE conversion block. Because $\gamma_{\rm conv}$ depends on $\Gamma$ through $q$, the full vector field is nonlinear. At fixed $q$, the displayed generator is an ordinary linear GKSL generator and defines a completely positive semigroup. For the state-dependent flow,

$$
\mathcal L_{\rm conv}[\Gamma]
=
\gamma_{\rm conv}(\Gamma)\,\mathcal L_0[\Gamma],
$$

with $\gamma_{\rm conv}\ge0$ and fixed linear GKSL generator $\mathcal L_0$. Each trajectory is a nondecreasing time reparametrization of the $\mathcal L_0$ flow, so the positive cone is preserved. The nonlinear evolution is not itself a linear completely positive map or semigroup. The checker tests the component identities, nonnegative rate, and time-reparametrization factor rather than substituting a finite-step numerical integrator for this analytic statement.

## 5. Relative-Frame Covariance

The declared relative frame transformation is

$$
U_Q(\alpha)
:=
\exp\!\left(-\frac{i\alpha}{2}\sigma_3\right),
\qquad
\Gamma\longmapsto U_Q\Gamma U_Q^\dagger.
$$

The jumps transform by phase,

$$
U_QL_{Y\to I}U_Q^\dagger
=e^{+i\alpha}L_{Y\to I},
\qquad
U_QL_{I\to Y}U_Q^\dagger
=e^{-i\alpha}L_{I\to Y},
$$

so the expected covariance identity is

$$
\boxed{
\mathcal L_{\rm conv}[U_Q\Gamma U_Q^\dagger]
=
U_Q\mathcal L_{\rm conv}[\Gamma]U_Q^\dagger.}
$$

This receipt tests constant frame covariance. A time-dependent transformation requires the temporal relative connection in the conservative sector and is outside the conversion-only check.

## 6. Bloch Reduction and Coherence-Support Boundary

For $\rho>0$, define

$$
z:=\frac{E_Y-E_I}{\rho},
\qquad
z_\varphi:=\varphi^{-3}.
$$

Because conversion preserves $\rho$,

$$
E_Y-\varphi E_I
=
\frac{\rho\varphi^2}{2}(z-z_\varphi).
$$

The expected conversion rates are

$$
\boxed{
\dot z\big|_{\rm conv}
=-\varphi^2\gamma_{\rm conv}(z-z_\varphi),}
$$

and

$$
\boxed{
\frac{d}{dt}|c|^2\bigg|_{\rm conv}
=-\varphi^2\gamma_{\rm conv}|c|^2.}
$$

For finite $\rho$, $\lambda>0$, and $c\ne0$,

$$
q<1
\quad\Longrightarrow\quad
\gamma_{\rm conv}>0
\quad\Longrightarrow\quad
\frac{d}{dt}|c|^2<0.
$$

Therefore the undriven homogeneous minimal lift has no finite-density stationary state with $c\ne0$. This is a conditional support obstruction for the declared lift. It does not establish global nonexistence. A coherent Hamiltonian source, protected sector, modified reservoir, boundary influx, transport-supported state, or different lift can change the transverse equation.

## 7. Effective Open Dynamical Closure

The present synthesis retains the matrix continuity ansatz

$$
\boxed{
\nabla_t^B\Gamma
+
\nabla_i^B\mathcal J^i
+
\nabla_{\mathfrak s}^B\mathcal J^{\mathfrak s}
=
\mathcal L_{\rm conv}[\Gamma]
+
\mathcal L_{\rm end}[\Gamma]
+
\Xi.}
$$

Its sectors retain distinct status:

- the covariant currents and connection belong to the conditional conservative relative-$U(1)_Q$ graph action;
- $\mathcal L_{\rm conv}$ is the reduced mesoscopic conversion generator;
- $\mathcal L_{\rm end}$ contains resolved endpoint channels;
- $\Xi$ contains declared reservoir or fluctuation terms after a normalization and stochastic convention are selected.

A microscopic action is not obtained by adding these terms. A candidate unified action must include explicit reservoir variables and reproduce the exact $q$-gated diagonal drift, fluctuation structure, and positivity boundary after reduction while retaining the conservative currents.

## 8. Integrated Endpoint Ledger

Use the registered stationary rail-source orientation

$$
\Gamma_-:=+\mathcal J_Q,
\qquad
\Gamma_+:=-\mathcal J_Q,
$$

and endpoint transport orientation

$$
\begin{aligned}
\partial_tn_-+\nabla\cdot\mathbf J_{\Upsilon,-}
&=\Gamma_- - I_{-\to+},\\
\partial_tn_++\nabla\cdot\mathbf J_{\Upsilon,+}
&=\Gamma_+ + I_{-\to+}.
\end{aligned}
$$

The endpoint-number ledger requires

$$
(\Gamma_- - I_{-\to+})
+
(\Gamma_+ + I_{-\to+})
=0.
$$

With rail relative-charge source $+g_Q\Gamma_v$ and endpoint source $-g_Q\Gamma_v$, each vertex source cancels locally. The Wilson edge carries the additional oriented charge current $-g_QI_{-\to+}$ whose incidence cancels the endpoint charge moved between vertices.

The checker tests these incidence identities. It does not rerun the SF1–SF6 or IT1–IT6 receipts or replace their frozen evidence.

## 9. Frozen Protocol

Use IEEE-754 double precision with

$$
\varphi=\frac{1+\sqrt5}{2},
\qquad
\lambda=0.02,
\qquad
\hbar=1.
$$

The deterministic state set is

$$
(E_Y,E_I)
\in
\left\{
(0,0),
(1,\varphi^{-1}),
(0.7,0.2),
(0,0.5),
(0.9,0)
\right\}.
$$

The covariance state is

$$
E_Y=0.8,
\qquad
E_I=0.3,
\qquad
c=0.4\sqrt{E_YE_I}\,e^{0.7i},
\qquad
\alpha=0.61.
$$

The integrated-ledger point is

$$
\mathcal J_Q=0.37,
\qquad
I_{-\to+}=0.29,
\qquad
g_Q=0.43.
$$

These values are normalized protocol data without physical calibration.

Use absolute tolerance $10^{-12}$ for algebraic identities and $10^{-14}$ for exact sign and bound classifications away from zero.

## 10. Gates

### DG1—Finite-State Qi Bound

`PASS` iff every frozen finite state satisfies $0\le q<1$, the vacuum has $q=0$, and the reference $\varphi$ composition satisfies the analytic finite-density value.

### DG2—Canonical Diagonal Reduction

`PASS` iff direct matrix evaluation of $\mathcal L_{\rm conv}$ matches all three component equations, preserves Hermiticity, gives zero trace, and has nonnegative jump rates at every frozen state.

### DG3—Relative-Frame Covariance

`PASS` iff the Frobenius norm of

$$
\mathcal L_{\rm conv}[U_Q\Gamma U_Q^\dagger]
-
U_Q\mathcal L_{\rm conv}[\Gamma]U_Q^\dagger
$$

is at most $10^{-12}$ at the frozen covariance point.

### DG4—Bloch-Rate Reduction

`PASS` iff direct component differentiation matches the frozen $\dot z$ and $d|c|^2/dt$ identities to $10^{-12}$.

### DG5—Finite-Density Coherence-Support Boundary

`PASS` iff every nonvacuum test point with $\lambda>0$ has $q<1$ and every valid $c\ne0$ test has $d|c|^2/dt<0$. The script must also verify analytically that the only zeros of the product are $\lambda=0$, $c=0$, or the unattained finite-state condition $q=1$.

### DG6—Integrated Endpoint and Charge Ledgers

`PASS` iff the endpoint-number incidence, rail-endpoint charge cancellation, and Wilson edge/vertex charge incidence each sum to zero at the frozen ledger point.

### DG7—Controls

`PASS` iff:

1. $\lambda=0$ makes $\mathcal L_{\rm conv}=0$;
2. $c=0$ remains on the diagonal subcone;
3. $t_\Upsilon=0$ removes Wilson transport and leaves the registered nonzero-source endpoint residual;
4. the separate local-$SU(2)_Q$ particle action is not imported into any tested equation.

## 11. Decision Rule

The overall verdict is `PASS` only if DG1–DG7 all pass. Any failed assertion fixes the first-execution verdict as `FAIL`; the script and raw output remain part of the record. No equation, state point, tolerance, control, or gate may be changed after the first execution.

A `PASS` establishes only the compatibility of the existing effective sectors and the conditional finite-density coherence-support boundary. It does not derive a microscopic reservoir, physical Qi field, Noether stress, geometry backreaction, local scale-bulk endpoint mediator, stationary particle, spectrum, mass, radius, lifetime, or empirical identification.

## References

- `foundations/cassi-first-principles.md`—canonical Yin/Yang densities and scalar Qi gate.
- `foundations/physical-becoming-hierarchy.md`—gradient-flow and Markov-bath reduction boundary.
- `foundations/geometric-manifold-completion.md`—positive coherence fibre and open matrix continuity ansatz.
- `foundations/interscale-stress-attenuation-boundary.md`—mixed-stress and force boundary.
- `foundations/endpoint-link-and-localization-boundary.md`—endpoint continuity, spatial flux, and Wilson transport.
- `foundations/particle-stationary-action-closure.md`—separate fixed-charge particle branch and registered numerical boundary.
