# Quantum Free Fall as a Cassi Correspondence Boundary

## Status: Derived conditional correspondence / Hypothesized Cassi field identification—September 2026

## Abstract

The Quantum Galileo Interferometer (QGI) observes the mass-dependent phase of a
ballistic $^{87}\mathrm{Rb}$ wave packet relative to a magnetically held wave
packet. In the ideal closing-condition limit, the measured phase is
$-mg^2T^3/(3\hbar)$. This paper derives that phase from Cassi's conditional
centre-of-mass Schrödinger sector after the uniform external potential is
supplied. With distinct inertial and gravitational coefficients, the phase is
$-m_g^2g^2T^3/(3\hbar m_i)$. The same derivation exposes an identifiability
boundary: expressing the phase in the ballistic arm's locally calibrated
acceleration removes the separate source-field and response-ratio factors.

The canonical two-fluid PDE supplies neither the Earth potential nor an atomic
map to $(E_Y,E_I,q)$. The Qi-gravity expression is therefore retained as a
coupling-magnitude diagnostic and possible scalar-tensor matching input, rather
than identified with the atom's $m_g/m_i$. The composition attractor is named as
the full $\varepsilon=0$ density line; $q=0$ denotes only its dilute endpoint,
while the registered reference-density point has
$q_{\mathrm{eq}}=\varphi^2/3\approx0.872678$. A constant common lapse cancels
when the phase duration is expressed in the same physical clock. Differential
field-state, source, or clock predictions require additional derived maps and
are registered as conditional tests.

## 1. Empirical target and scope

The QGI result is reported in
[arXiv:2502.14535](https://arxiv.org/abs/2502.14535) and published at
[doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045).
One spin-state wave packet follows a ballistic trajectory while another is held
by a magnetic gradient. Recombination reads their relative phase as an output
population. The experiment resolves about thirteen oscillations and roughly
$80$ radians, with an approximately $2.5\%$ residual between the data and its
blind numerical model. The reported comparison places few-percent sensitivity
on changes to the ideal phase prefactor under the apparatus model.

The apparatus model includes finite kick and holding pulses, magnetic curvature,
second-order Zeeman shifts, wave-packet shape evolution, interactions, and
three-dimensional trajectory corrections. The exact experimental phase is
therefore the action of the measured piecewise Hamiltonian. The compact
expression below is its uniform-field, ideal-pulse, closed-path limit.

The empirical result establishes a weak-field quantum correspondence target.
It measures quantum matter evolving in an externally modeled Earth field. The
gravitational field is not prepared in a quantum superposition, and the result
contains no direct probe of Cassi's $\varphi$ scale hierarchy, $\sigma$ regulator,
or proposed composite graviton.

## 2. Conditional centre-of-mass Hamiltonian

The regulated Cassi quantum construction admits a collective coordinate with
metric $G_{zz}=m_i$ and the generic equation

$$
i\hbar\partial_t\psi_N
=
\left[-\frac{\hbar^2}{2m_i}\partial_z^2+V(z,t)\right]\psi_N.
\tag{QG1}
$$

For the QGI correspondence calculation, supply the uniform external potential

$$
V_g(z)=m_g g z,
\tag{QG2}
$$

where $g>0$ is the source field in the chosen laboratory coordinate,
$m_i>0$ is the inertial coefficient, and $m_g>0$ is the test response
coefficient. Equation (QG2) is an explicit weak-field input. The canonical
real-density PDE does not derive it.

The complete arm action has the form

$$
S_a
=
\int dt\left[
\frac12m_{i,a}\dot z_a^2
-m_{g,a}gz_a
-V_{\mathrm{mag},a}(z_a,t)
-E_{\mathrm{int},a}(t)
\right]
+\hbar\sum_k\Phi_{k,a},
\tag{QG3}
$$

where $a$ labels an interferometer arm and $\Phi_{k,a}$ contains the phase of
each state-transfer or momentum-transfer pulse. The observable is

$$
\Delta\phi=\frac{S_b-S_r}{\hbar}.
\tag{QG4}
$$

Equation (QG3) is the required interface to the measured pulse sequence. The
published numerical model supplies its apparatus-specific magnetic and atomic
terms. Cassi-specific physics may enter only through a separately derived
response, source, or lapse term; every standard apparatus term remains in the
joint fit.

## 3. Accelerated-frame gauge phase

Define

$$
r:=\frac{m_g}{m_i},
\qquad
\zeta=z+\frac12rgt^2,
\tag{QG5}
$$

and write

$$
\psi_N(z,t)
=e^{if(z,t)/\hbar}\psi_E(\zeta,t).
\tag{QG6}
$$

Substitution of (QG6) into (QG1) fixes the first-derivative coefficient through

$$
\partial_z f=-m_g gt.
\tag{QG7}
$$

The remaining scalar term fixes

$$
\boxed{
f(z,t)
=-m_g gtz-\frac{m_g^2}{6m_i}g^2t^3
}.
\tag{QG8}
$$

With (QG8), $\psi_E$ obeys the free Schrödinger equation. For $m_g=m_i=m$,

$$
\frac{f}{\hbar}
=-\frac{m}{\hbar}\left(gzt+\frac16g^2t^3\right),
\tag{QG9}
$$

which is the QGI gauge phase. It is the projective mass phase of the quantum
wavefunction under the accelerating-frame transformation. Cassi's scalar $q$,
positive-root density-plane angle, and optional relative-$U(1)_Q$ phase are
distinct defined objects.

## 4. Closed ballistic action

Take $0\le t\le2T$ and impose the closing velocity

$$
v_0=rgT.
\tag{QG10}
$$

The ballistic path is

$$
z_b(t)=rgTt-\frac12rgt^2,
\qquad
\dot z_b(t)=rg(T-t),
\tag{QG11}
$$

so $z_b(0)=z_b(2T)=0$. A reference arm held at $z_r=0$ has zero ideal
centre-of-mass action in this coordinate convention. Direct integration gives

$$
S_K
=\int_0^{2T}\frac12m_i\dot z_b^2dt
=\frac{m_g^2}{3m_i}g^2T^3,
\tag{QG12}
$$

and

$$
S_V
=-\int_0^{2T}m_ggz_bdt
=-\frac{2m_g^2}{3m_i}g^2T^3.
\tag{QG13}
$$

Therefore

$$
\boxed{
\Delta\phi_{
m ideal}
=-\frac{m_g^2}{3\hbar m_i}g^2T^3
}.
\tag{QG14}
$$

The equivalence value $m_g=m_i=m$ gives

$$
\boxed{
\Delta\phi_{\rm EP}
=-\frac{mg^2T^3}{3\hbar}
}.
\tag{QG15}
$$

Equations (QG8) and (QG14) reproduce the ideal primary-source result. The
Cassi contribution at this stage is a conditional centre-of-mass host for the
standard external-potential calculation.

## 5. Local-acceleration identifiability

The ballistic acceleration magnitude is

$$
g_b=rg=\frac{m_g}{m_i}g.
\tag{QG16}
$$

Equation (QG14) can then be written

$$
\boxed{
\Delta\phi_{
m ideal}
=-\frac{m_i g_b^2T^3}{3\hbar}
}.
\tag{QG17}
$$

A phase prediction expressed in the same preparation's locally calibrated
acceleration contains no separate measurement of $r$ and $g$. A uniform change
in the source field or gravitational coupling can be absorbed into $g_b$.
This blocks a numerical inference of Cassi $q$ from the reported phase residual.

A differential response becomes available when the ballistic and held
preparations are independently calibrated against the same source. Let

$$
g_b=r_bg,
\qquad
a_h=r_rg,
\tag{QG18}
$$

where $a_h$ is the upward magnetic acceleration required to hold the reference
preparation. In the ideal limit,

$$
\boxed{
\mathcal R_{br}
:=\sqrt{
\frac{-3\hbar\Delta\phi_b}{m_iT^3a_h^2}}
=\left|\frac{r_b}{r_r}\right|
}.
\tag{QG19}
$$

The common source field cancels. Equation (QG19) is an effective response-ratio
observable, subject to the finite-pulse and magnetic corrections in (QG3). A
Cassi interpretation requires a state map that assigns $r_b$ and $r_r$ before
the phase data are examined.

## 6. Gravity branches and source/test roles

### 6.1 Constant-$G_N$ metric branch

The closed matter-plus-gravity boundary uses

$$
S
=
\frac{1}{16\pi G_N}
\int d^4x\sqrt{-g}\,R
+S_m[g,\Phi_{\mathrm{matter}}],
\tag{QG20}
$$

with a conserved total matter stress tensor. Universal minimal matter coupling
gives the standard local weak-field potential and the QGI correspondence
(QG15). This branch is the current low-energy empirical baseline.

### 6.2 Variable gravitational-sector branch

The covariant variable-coupling candidate has

$$
S_{g\chi}
=
\int d^4x\sqrt{-g}\left[
\frac12F(\chi)R
-\frac12K_{AB}(\chi)\nabla_\mu\chi^A\nabla^\mu\chi^B
-U(\chi)
\right]
+S_m[g,\psi_m].
\tag{QG21}
$$

Universal Jordan-frame matter coupling in (QG21) preserves one matter metric.
A varying $F$ changes the sourced metric and can add scalar exchange; it does
not by itself define a body-dependent $m_g/m_i$. Body dependence requires the
body sensitivities and scalar profile obtained from a completed matter and
screening model.

The Cassi coupling-magnitude diagnostic

$$
\mathcal G_C(E_Y,E_I)
=
\frac{\pi}{\rho}
\left[1+(\varphi^6-1)q\right]
\tag{QG22}
$$

may enter a positive-branch matching such as
$F\simeq M_{\mathrm{Pl}}^2/\mathcal G_C$, with scalar-exchange corrections.
Equation (QG22) supplies no independent scalar equation, source profile,
screening scale, or atomic sensitivity. It therefore remains separate from the
QGI coefficient $m_g/m_i$.

### 6.3 Direct response-charge branch

A phenomenological direct-charge completion can be declared through the
operational ratio

$$
r_B:=\frac{m_{g,B}}{m_{i,B}}.
\tag{QG23}
$$

If a future microscopic map assigns a Cassi state $X_B$ to body $B$, a
reference-normalized ansatz is

$$
\widehat{\mathcal G}_B(X_B\mid X_\star)
:=\frac{\mathcal G_C(X_B)}{\mathcal G_C(X_\star)},
\qquad
r_B\stackrel{\mathrm{hyp}}{=}
\widehat{\mathcal G}_B.
\tag{QG24}
$$

The reference normalization makes the laboratory baseline unity and keeps the
bare coupling separate from measured $G_N$. A reciprocal two-body Newtonian
ansatz would use one normalized factor for the source and one for the test:

$$
U_{SB}^{\mathrm{hyp}}(R)
=-\frac{G_Nm_{i,S}m_{i,B}}{R}
\widehat{\mathcal G}_S\widehat{\mathcal G}_B.
\tag{QG25}
$$

Equations (QG24) and (QG25) are Hypothesized matching rules. They are not
consequences of (QG21), and the current carrier calculation supplies no atomic
$X_B$. QGI constrains this branch only after the state map, reference state,
and apparatus model are frozen.

## 7. Attractor-line normalization

Write

$$
s:=\frac{\pi}{\rho},
\qquad
\varepsilon=E_Y-\varphi E_I.
\tag{QG26}
$$

The composition attractor is the line $\varepsilon=0$. Along it,

$$
E_Y=\varphi E_I,
\qquad
s=\varphi^{-3},
\tag{QG27}
$$

while the physical-density form of the coherence diagnostic is

$$
q_{\mathrm{eq}}(\rho)
=
\frac{\rho^2}
{\rho^2+\varphi^{-2}\rho_\star^2}.
\tag{QG28}
$$

Thus the composition ratio is fixed while $q$ remains a density coordinate.
Two named limits must remain distinct:

1. **Dilute attractor endpoint:** $\rho/\rho_\star\to0$, so $q\to0$ and
   $\mathcal G_C\to\varphi^{-3}$.
2. **Registered reference-density point:** with the dimensionless convention
   $\rho_\star=1$ and $\rho=\varphi$,
   $$
   q_{\mathrm{eq}}=\frac{\varphi^2}{3}
   \approx0.872677996,
   \qquad
   \mathcal G_C=\frac{5\sqrt5}{3}
   \approx3.726779963.
   \tag{QG29}
   $$

The phrase “$q=0$ attractor” refers only to the dilute endpoint. Laboratory
matter receives no position on (QG28) until $\rho_\star$ and the physical
projection to $E_Y,E_I$ are supplied.

## 8. Candidate common lapse

For a constant positive lapse $d\tau=Ndt$, the one-dimensional worldline action
corresponding to (QG2) is

$$
S_N
=
\int dt\left[
\frac{m_i}{2N}\dot z^2-Nm_ggz
\right].
\tag{QG30}
$$

The coordinate-time acceleration is $N^2(m_g/m_i)g$. Repeating the closed-path
calculation gives

$$
\Delta\phi_N
=-\frac{N^3m_g^2}{3\hbar m_i}g^2T^3.
\tag{QG31}
$$

The same physical clock reports the half-duration $\mathcal T=NT$, so

$$
\boxed{
\Delta\phi_N
=-\frac{m_g^2}{3\hbar m_i}g^2\mathcal T^3
}.
\tag{QG32}
$$

The constant common lapse cancels. A measurable common-lapse test requires
worldlines sampling different $N_q$, the full variational constraint linking
$N$ and $q$, and an independently calibrated clock sector. The present QGI
contains no resolved $q$ contrast and does not implement CT-2.

## 9. Atomic state-map requirement

A Cassi-specific prediction requires a frozen projection

$$
\mathfrak M_{\mathrm{atom}}:
(\text{species},F,m_F,\rho_{\mathrm{atom}},
\text{interactions},\text{environment})
\longrightarrow
X_B=(E_Y,E_I,\rho_\star,\text{carrier data}),
\tag{QG33}
$$

followed by a derivation of either the scalar-tensor body sensitivity in
(QG21) or the direct response in (QG23). Matter-wave visibility and condensate
fraction are separate observables and do not define $q$.

The current localized carrier branch establishes a finite variational
configuration within one regulated class. Its physical particle identity,
continuum qualification, calibrated coefficients, and gravity selection remain
open. It therefore supplies no rubidium map for (QG33).

## 10. Falsifiable QGI boundary

The registered QGI test has three layers:

1. **Correspondence gate:** the supplied external-potential COM sector must
   reproduce (QG8), (QG14), and the full standard apparatus phase.
2. **State-response gate:** a frozen $\mathfrak M_{\mathrm{atom}}$ and gravity
   completion must predict $\mathcal R_{br}$ in (QG19) before a spin-state,
   isotope, density, or species comparison is examined.
3. **Clock gate:** a common-lapse claim must predict two independent clock
   sectors and the conversion clock across one frozen $q$ contrast, as required
   by CT-2.

A useful experimental sequence reverses the ballistic and held internal states,
repeats the geometry with a second isotope or species, and fits the phase and
trajectory channels jointly. A direct-charge map is rejected when its predicted
state-dependent $\mathcal R_{br}$ is absent at the pre-registered sensitivity.
A universal minimally coupled metric branch predicts the standard response
apart from its completed scalar-screening corrections.

The published QGI result passes the standard correspondence target at its
reported sensitivity. It supplies no Cassi-specific verdict because
$\mathfrak M_{\mathrm{atom}}$, the covariant source solution, and a declared
Cassi response contrast are absent.

`computations/quantum_free_fall_correspondence_prereg.md` governs the eight
proof obligations verified by
`computations/verify_quantum_free_fall_correspondence.py`:

- the accelerated-frame first-derivative and scalar cancellations;
- the closed unequal-mass ballistic action;
- the equivalence-limit phase;
- the local-acceleration degeneracy;
- the differential held-arm response ratio;
- constant-lapse clock-coordinate invariance;
- the attractor-line and reference-density identities;
- dimensional closure.

The independent derivation is preserved at
`computations/quantum_free_fall_correspondence_cleanroom_receipt.md`; the
gate table and verifier stdout are preserved at
`computations/quantum_free_fall_correspondence_report.md`.

The algebraic correspondence is **Derived conditional** on (QG1) and (QG2).
The Cassi atomic state map, variable-coupling gravity completion, direct-charge
matching, screening solution, path-dependent common lapse, and distinctive
experimental signal remain **Hypothesized**.

## References

- Y. Margalit *et al.*, “Observation of the quantum phase of free fall and the consistency with the equivalence principle,” *Science Advances* (2026), [doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045); accessible derivation at [arXiv:2502.14535](https://arxiv.org/abs/2502.14535).
- `foundations/quantum-measurement-derivation.md`—conditional regulated quantum mechanics and centre-of-mass reduction.
- `foundations/physical-becoming-hierarchy.md`—covariant scalar-tensor completion boundary and local PPN constraint.
- `foundations/matter-completion-boundary.md`—constant-$G_N$ closed-action gravity branch and particle-state boundary.
- `foundations/unified-lagrangian.md`—candidate common-lapse action criterion.
- `predictions/falsifiable-predictions.md`—QGI-1 and CT-2 experimental contracts.
