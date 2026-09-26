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

A Cassi-specific prediction requires a physical preparation map that supplies
the spatial state and its effective action:

$$
\mathfrak M_{\mathrm{atom}}:
(\text{species},F,m_F,\rho_{\mathrm{atom}},
\text{interactions},\text{environment},\text{frame},\text{resolution})
\longrightarrow
\left(X_B(\mathbf x),S_B^{\mathrm{eff}}\right),
\tag{QG33}
$$

where $X_B$ contains $E_Y,E_I,\rho_\star$, carrier amplitudes, phases,
currents, and any additional state needed by the observable. The induced
action must determine the inertial coefficient, internal energies, magnetic
response, and whichever gravity branch is selected in §6. A phenomenological
map may use independently measured inputs, with that calibration declared;
a first-principles claim must derive the same inputs from the physical carrier.
Matter-wave visibility and condensate fraction are separate observables.

The localized carrier branch establishes a finite variational configuration
within one regulated class. Its six-mode constrained low-spectrum result
leaves continuum, unrestricted dynamical stability, physical particle
identity, and calibrated atomic interactions open
(`foundations/matter-completion-boundary.md` §§9–12). It supplies no
rubidium realization of (QG33).

### 9.1 Physical domain and information loss

The canonical density restrictions place a stronger bound on $q$ than
$0\leq q<1$. With $\rho_\star>0$ and $\rho>0$,

$$
E_Y=\frac{\varphi\rho+\varepsilon}{1+\varphi},\qquad
E_I=\frac{\rho-\varepsilon}{1+\varphi},\qquad
-\varphi\rho\leq\varepsilon\leq\rho,
$$

so

$$
\boxed{
\frac{\rho^2}{(1+\varphi^2)\rho^2+\varphi^{-2}\rho_\star^2}
\leq q\leq
\frac{\rho^2}{\rho^2+\varphi^{-2}\rho_\star^2}<1.
}
\tag{QG34}
$$

At fixed nonzero density, composition changes cannot send $q$ to zero.
For fixed positive $\rho_\star$, the canonical $q\to0$ limit requires
$\rho/\rho_\star\to0$. The high-density lower endpoint is
$1/(1+\varphi^2)=0.276393202250\ldots$. These bounds concern the
instantaneous canonical $\varepsilon^2$ diagnostic; an optional
memory-replaced diagnostic requires its own state and domain.

Equal $q$ also leaves the signed composition unresolved. The two admissible
states $\rho=\rho_\star=1$, $\varepsilon=\pm1/2$ give

| $\varepsilon$ | $E_Y$ | $E_I$ | $q$ | $s=\pi/\rho$ | $\mathcal G_C$ |
|---|---:|---:|---:|---:|---:|
| $+1/2$ | 0.809016994375 | 0.190983005625 | 0.612757859604 | 0.618033988750 | 7.034917602017 |
| $-1/2$ | 0.427050983125 | 0.572949016875 | 0.612757859604 | -0.145898033750 | -1.660718770186 |

Here

$$
s_\pm=\frac{\varphi^{-1}\pm1}{\varphi^2}.
\tag{QG35}
$$

Thus $q$ alone does not even determine the sign of the optional coupling
diagnostic. Neither entry in the last column is a physical gravitational
response. Retaining $(q,s)$ still leaves dimensional normalization, spatial
profiles, currents, quantum phases, and the gravity action to be supplied.

Spatial averaging loses additional information. For two equal-volume cells
in the states above,

$$
\left\langle q\right\rangle=0.612757859604\ldots,\qquad
q(\langle E_Y\rangle,\langle E_I\rangle)
=0.723606797750\ldots.
\tag{QG36}
$$

An atomic map must therefore specify the averaging kernel, frame, and
resolution, and control the discarded correlations. A scalar evaluated on
mean densities cannot be substituted for the mean local scalar without
that closure. The existing many-to-one loop projection has the same
observable-sufficiency requirement
(`foundations/loop-to-bubble-projection-theorem.md` §§2,7).

### 9.2 Internal energy and the quantum equivalence principle

Composite atoms require a response law for internal energy as well as for
centre-of-mass motion. In the standard weak-field test framework, introduce
rest, inertial, and gravitational mass-energy operators,

$$
\widehat M_\alpha=m_\alpha I+\frac{\widehat H_{\mathrm{int},\alpha}}{c^2},
\quad \alpha\in\{r,i,g\},\qquad
\widehat H_{\mathrm{test}}
=\widehat M_r c^2+\frac{\widehat p^2}{2\widehat M_i}
+\widehat M_g\Phi+\widehat H_{\mathrm{EM}}.
\tag{QG37}
$$

This notation assumes internal operators commute with the centre-of-mass
coordinates before position-dependent environmental couplings are added.
It is the external test framework of Zych and Brukner
([doi:10.1038/s41567-018-0197-6](https://doi.org/10.1038/s41567-018-0197-6);
[arXiv:1502.00971](https://arxiv.org/abs/1502.00971)), with the apparatus
electromagnetic control written explicitly.

Equality of the three mass-energy operators, with a consistent rest-energy
reference, is stronger than equality of selected diagonal mass values.
Off-diagonal matrix elements can affect coherent internal-state evolution.
The scalar $m_i,m_g$ action in §2 is its fixed-state leading-order
specialization. Reproducing that action supplies no general test of all
operator-valued equivalence conditions. A Cassi atom model must specify the
internal operators and their couplings before applying a state-dependent
response to the interferometer's microwave and magnetic pulse sequence.

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
A universal minimally coupled metric branch predicts the standard
point-particle response. Additional scalar forces belong to the separately
specified scalar-tensor branch; their range, strength, and screening require
its completed source and body solutions.

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

## 11. Closure dependency inventory

The remaining work separates into material realization, gravity, clocks,
apparatus inference, and quantum gravity. The inventory covers the interfaces
used by the correspondence theorem and the linked quantum-gravity proposal;
it makes no claim to enumerate every open question in physics. Each row
states a missing object and an observable or mathematical closure criterion.
Existing finite or conditional results retain their stated scope.

**Route distinction.** The ideal external-field phase needs the supplied
Hamiltonian and closed paths already verified in §10. An effective Cassi
atomic test may use independently calibrated atomic physics, provided its
state-response map is fixed before the tested data. A first-principles atomic
claim additionally needs the carrier-to-atom derivation below. The clock
requirements apply only to a physical common-lapse claim. The quantum-gravity
requirements apply to the interacting quantum-gravity and black-hole claims;
they are not prerequisites for ordinary weak-field atomic interferometry.

### 11.1 Material realization

The finite carrier construction and conditional quantum sector supply useful
starting objects. They do not select a physical rubidium atom.

| ID | Missing object | Current boundary and closure criterion |
|---|---|---|
| A01 | Physical density-to-carrier dictionary | The positive-root lift and loop projection retain only selected information. Supply a phase-bearing spatial state and projection with controlled errors for every retained observable; identify which unresolved variables are needed by (QG33). Sources: `foundations/cassi-first-principles.md` §§1–2; `foundations/loop-to-bubble-projection-theorem.md` §§2,7. |
| A02 | Physical density units, frame, and coarse-graining | $\rho_\star$ is external and $q$ is nonlinear. Fix the measured density normalization, observer/slicing, smoothing scale, and sufficient state before computing $q$ or $\mathcal G_C$; control the mismatch in (QG36). Source: §9.1 and `foundations/cassi-first-principles.md` §2.1. |
| A03 | Physical carrier, exterior, interface, and environment action | The closed-action ledger is conditional. Supply $S_{\mathrm{out}},S_{\mathrm{int}},S_{\mathrm{env}}$, physical units, boundary realization, metric dependence, and the port/flux law. Derive energy and particle transfer from those actions rather than identifying a matrix norm with power. Source: `foundations/matter-completion-boundary.md` §§5,7–9,12. |
| A04 | Continuum and full dynamical particle qualification | Localization is supported on the sampled finite grids; the constrained six-mode spectrum is a restricted finite-grid result. Qualify domain/resolution limits, tails, Gauss and charge constraints, sectors outside $C_4$, the phase mode's high-frequency content, the mixed dynamical pencil, and real-time persistence or formation. Source: `foundations/matter-completion-boundary.md` §§10–12. |
| A05 | Kinetic metric and physical inertial mass | The COM Schrödinger equation assumes a positive metric and its mass coefficient. Derive the collective-coordinate kinetic metric, zero-mode normalization, dispersion, and physical unit map from the selected carrier; separate measured $\hbar,c$ and mass calibrations from derived dimensionless ratios. Source: `foundations/quantum-measurement-derivation.md` §§1–3,8; §2 here. |
| A06 | Physical particle sectors and statistics | The neutral carrier $U(1)_C$ charge is not an electric, baryon, or lepton charge. Derive the relevant spin/statistics, gauge representation, conserved charges, and physical Hilbert-space sectors before identifying electrons or nuclear constituents. Source: `foundations/particle-stationary-action-closure.md` §1.3; `foundations/matter-completion-boundary.md` §9.3. |
| A07 | Many-body binding and the rubidium spectrum | A retained carrier is not a nucleus or a bound atom. Derive interactions, exchange, nuclear/electronic binding, isotope content, and the $^{87}\mathrm{Rb}$ internal spectrum, or explicitly import measured atomic structure for an effective test. Source: `foundations/matter-completion-boundary.md` §§9,12; (QG33). |
| A08 | Hyperfine and electromagnetic response | The experiment distinguishes $F,m_F$ states through microwave transitions and Zeeman forces. Supply transition matrix elements, magnetic moments, quadratic Zeeman terms, interaction energies, and their dependence on the mapped state; reproduce independent spectroscopy and force calibrations. Sources: (QG37); the published QGI Methods. |
| A09 | Total mass-energy and physical readout | Derive how constituent, binding, field, and environment energies enter inertial/rest energy and the measured atom record. Use one energy partition so Qi is not counted both as added source matter and as a coupling enhancement. The conditional Born/instrument construction still requires physical state and apparatus identification. Sources: `foundations/quantum-measurement-derivation.md` §§2,8; `foundations/matter-completion-boundary.md` §§7–9; `open-questions-cassi-answers.md` C2. |

### 11.2 Classical gravity and material response

The constant-$G_N$ metric branch, variable scalar-tensor branch, and
direct-charge ansatz are distinct alternatives. A completion must choose and
close the applicable branch; it need not implement all three.

| ID | Missing object | Current boundary and closure criterion |
|---|---|---|
| G01 | Selected gravity action and branch | The scalar-tensor template supplies equations, not selected functions. Specify $F(\chi),K_{AB}(\chi),U(\chi),S_m$, dimensions, background and boundary terms, or retain the constant-$G_N$ minimally coupled branch. A direct-charge alternative needs its own reciprocal action. Source: `foundations/physical-becoming-hierarchy.md` §7.4; §6 here. |
| G02 | Healthy scalar and tensor modes | For the scalar branch require $F>0$, positive Einstein-frame field metric, a declared stable vacuum, and a physical scalar spectrum. Normalize perturbation modes and couplings with explicit units; a general curved field-space metric need not admit globally canonical coordinates. Source: `foundations/physical-becoming-hierarchy.md` §7.4, no-ghost conditions. |
| G03 | Total stress tensor and conservation | The constant-$G_N$ Ward/Bianchi witness is conditional on a completed metric-dependent action. Derive the source from all carrier, exterior, interface, environment, and scalar terms and verify their joint conservation. Substituting $G_{\mathrm{eff}}(q)T_{\mu\nu}$ alone leaves derivative terms unclosed. Source: `foundations/matter-completion-boundary.md` §§7–8. |
| G04 | Physical source solution and boundary data | Supply the Earth or other source's material state, scalar asymptotics/flux, interface conditions, initial constraints, and metric boundary data. Solve for the exterior field and its uniqueness or stated solution class. A supplied uniform $g$ in the QGI Hamiltonian bypasses this calculation. Sources: `foundations/physical-becoming-hierarchy.md` §7.4; `foundations/matter-completion-boundary.md` §7. |
| G05 | Attractive sign and reciprocal interaction | The displayed PDE has $+\nabla\Phi$ and is outward for positive imbalance when $\Phi=-GM/r$. Derive any attractive extension and both source/test charges from one action, including field momentum or a symmetric conservative two-body limit. A target-only multiplier in an external field is not a closed reciprocal gravity law. Source: `gravity/three-body-analytical.md` §§1–3; §6.3 here. |
| G06 | Body sensitivities and scalar profiles | $F(\chi)R$ does not determine atomic response. Derive body masses/charges as functions of the normalized ambient scalar, solve source and body profiles, and determine range, strength, and any screening. Heavy, weakly coupled, and screened scalars are alternative limits; local bounds do not uniquely select screening. Source: `foundations/physical-becoming-hierarchy.md` §7.4; §6.2 here. |
| G07 | Cavendish normalization and weak-field bounds | Match the action to measured $G_N$, including scalar exchange when present, and compute the applicable post-Newtonian and finite-range observables. $F(\chi_0)=(8\pi G_N)^{-1}$ alone is a valid laboratory identification only when the additional exchange is negligible in that regime. Source: `foundations/physical-becoming-hierarchy.md` §7.4, local PPN boundary. |
| G08 | Extended-body, mass-flow, and tidal closure | The blob ODE assumes relaxed, separated profiles; retained masses and imbalance evolve through flux and conversion. Derive profile/width evolution, boundary flux, self-energy, scalar charge and leading multipoles, with a controlled point-body limit. A regulator length alone supplies no material tidal coefficient. Source: `gravity/three-body-analytical.md` §§2–4. |
| G09 | Internal-energy equivalence and response matching | In the universal metric branch, complete internal energy contributes equally to metric weight and inertia. A scalar/direct-charge branch must derive the response of each internal energy increment, including off-diagonal operators when relevant. Match (QG37) and the source-normalized effective response without mistaking a universal rescaling for differential violation. Sources: §9.2; `foundations/matter-completion-boundary.md` §§7–9. |

### 11.3 Physical clocks

The canonical conversion trace fixes a product of kinetic and clock factors.
It supplies no independent measurement that the same factor governs other
physical clocks.

| ID | Missing object | Current boundary and closure criterion |
|---|---|---|
| C01 | Separation of kinetics from lapse | Conversion determines $K(q)N(q)=1-q$. Distinguish a universal lapse from gated kinetics with independent sectors and fixed intrinsic calibrations; another conversion receipt measures the same product. Source: `foundations/unified-lagrangian.md` §§1.6–1.7. |
| C02 | Complete variational lapse action | Supply the lapse constraint, its multiplier/backreaction, spatial metric, shift and boundary terms, then vary the complete action. Applying $N_q$ to selected solver updates establishes only sector-specific gating. Source: `foundations/unified-lagrangian.md` §1.7. |
| C03 | Metric and operational reference matching | Define $q$ covariantly or declare its observer/foliation, relate $N_q$ to worldline proper time and the reference clock, and retain transport and memory transformations. A constant common lapse cancels in physical QGI durations; any observable contrast needs a resolved path/location dependence or external clock comparison. Sources: §8; `hypotheses/scalar-time-reparameterization-applications.md` §§3–11. |
| C04 | Cross-clock calibration and measurability | Calibrate the conversion rate and at least two non-conversion clocks against the same reference, with resolved $q$ contrast, transport subtraction, declared memory and uncertainty. Exact $\varepsilon=0$ provides no logarithmic conversion tick; use a resolved perturbation/relaxation measurement where justified or report the missing clock receipt. Sources: `predictions/falsifiable-predictions.md` CT-2; `hypotheses/scalar-time-reparameterization-applications.md` §§11–12. |

### 11.4 Apparatus and inference

The published measurement contains state switches, finite forces and a phase
readout referenced to the apparatus. Its ideal cubic phase is only one limit
of that calculation.

| ID | Missing local bridge | Completion criterion |
|---|---|---|
| E01 | State-resolved pulse history | Propagate the actual $F=1,m_F=0$ and $F=2,m_F=1$ states through preparation, kicks, microwave swaps and recombination using (QG37). During kicks the arm/state assignments change; one constant response per entire arm is insufficient when testing state dependence. Source: published QGI Methods and author manuscript Methods. |
| E02 | Finite-pulse trajectories and wave-packet overlap | Include kick/delay/holding waveforms, magnetic curvature, expansion/rotation, residual second-order Zeeman forces, mean-field interactions, and final position/momentum/shape overlap. Reproduce the supplied apparatus model before attributing residual phase or lost visibility to Cassi. Source: published QGI Experiment, Results and Methods. |
| E03 | Complete measured phase | Compute propagation, internal-energy, microwave/control and separation phases with one port/sign convention and detection model. Recover the ideal action when the corresponding limits are taken; frame or gauge changes must leave the final probability invariant. Source: §§2–4; published QGI Methods. |
| E04 | Calibration covariance and identifiable likelihood | Jointly model phase, trajectories, holding acceleration, magnetic/current and timing calibrations, atom number and nuisance uncertainties. Distinguish an independent prediction from tuning within an uncertainty band. The few-percent apparatus residual is not a standalone bound on $q$ or a fundamental coupling. Source: published QGI Results; §5 here. |
| E05 | Frozen contrast and independent source normalization | Select a preparation/source comparison predicted to distinguish the chosen branch, freeze its state map before the tested data, and account for field calibration. The ideal local channel gives $m_i g_b^2$, while the differential channel gives only $\lvert r_b/r_r\rvert$; its square root loses the response sign. Use trajectory direction and additional controls where needed. Source: §5 and QGI-1. |
| E06 | Reproducible local data/model receipt | Acquire and identify the published data, pulse/calibration inputs and reconstruction code; reproduce the phase extraction and uncertainty accounting with source/version provenance. The article states that data and code are in the paper and/or supplement. The publisher supplement returned an access failure during this inventory; the accessible author manuscript is a separate version. No local shot-level reanalysis or claim that the authors' data are absent is made. Source: article Data, code, and materials availability; [arXiv:2502.14535v4](https://arxiv.org/abs/2502.14535v4). |

The article's finite levitation-mismatch expression,
$\Delta\phi=ma(a-2g)T^3/(3\hbar)$ in its signed ideal convention,
also illustrates why the holding calibration is part of the observable.
At $a=g$ it reduces to the ideal phase here, with a quadratic mismatch
$m(a-g)^2T^3/(3\hbar)$. This is a supplied apparatus result, not a
Cassi-specific force law.

### 11.5 Interacting quantum gravity

The free Euclidean candidate and the finite quantum construction leave the
following requirements for a physical interacting gravity theory. The
spectral row is a conditional obstruction; the remaining rows describe open
constructions or qualifications, with the rejected dispersion explicitly
identified.

| ID | Missing object or obstruction | Current boundary and closure criterion |
|---|---|---|
| U01 | Interacting action and vertices | Supply fields, units, regulator interpretation, interaction terms and vertices from one action. The constant-vertex radial prototype does not determine them. Source: `gravity/quantum-gravity.md` §§4–5. |
| U02 | Gauge symmetry, constraints and measure | Derive the constraint algebra, gauge fixing, measure and BRST or equivalent physical-sector construction; verify Ward identities. Imposed transverse-traceless conditions do not supply this structure. Source: `gravity/quantum-gravity.md` §§4.3,5. |
| U03 | Physical spin-2 excitation | Identify a physical operator, positive-norm massless pole, helicities and conserved-stress coupling, with extra modes constrained or consistently accounted for. The composite label alone does not derive two graviton polarizations. Source: `gravity/quantum-gravity.md` §4. |
| U04 | Lorentzian continuation | Specify the nonlocal contour, $i\epsilon$, growth conditions, vacuum and retarded/Feynman distributions. Derive consistency with the Euclidean object and any dispersion law; the separately assigned dispersion is not derived from the displayed propagator. Source: `gravity/quantum-gravity.md` §§3–4. |
| U05 | Standard positive spectral interpretation | At $\sigma>0$, $G_E(x)=e^{-\sigma^2x/2}/x$ fails the monotonicity required by an unsubtracted positive scalar spectral measure. A completion must change the physical covariance or the stated assumptions, or use this expression only as a regulator/auxiliary line and separately establish positivity of physical observables. This is not a general theorem of interacting nonunitarity. Source: `gravity/quantum-gravity.md` §3.1. |
| U06 | Causal response and observed propagation | Compute retarded support and front velocity in the selected Lorentzian theory. The implemented low-momentum speed $c_{\mathrm{eff}}/c\simeq1.0275$ is already rejected as the observed GW mode; a viable identified mode must recover the measured speed or the probe must be physically decoupled. Source: `gravity/quantum-gravity.md` §4.2; `audit.md` §3. |
| U07 | Interacting unitarity | With a defined physical state space and interaction, verify the optical theorem/cutting relations and exclude pathological interacting modes. Absence of extra free poles is insufficient, and the obstruction in U05 must first be addressed in the physical sector. Source: `gravity/quantum-gravity.md` §7.2. |
| U08 | Ultraviolet completion and counterterms | Determine the net vertex/propagator behavior, regulator or finite-$\sigma$ theory, symmetry-compatible counterterms and higher-loop observables. A single UV-convergent integral at supplied nonzero infrared cutoff is only a prototype. Source: `gravity/quantum-gravity.md` §§5.1–5.2. |
| U09 | Infrared and zero-mode prescription | Supply physical soft-mode, boundary or finite-volume treatment and demonstrate the claimed observable's infrared behavior. The uncut displayed radial integral is logarithmically infrared divergent; an external cosmological scale is an additional input. Source: `gravity/quantum-gravity.md` §5.1. |
| U10 | Renormalized Newton coupling | Define a measurable matching observable and its scale dependence, then compute any running of $G$. The number $\varphi^6/(16\pi^2)$ supplies no beta function. Source: `gravity/quantum-gravity.md` §5.3. |
| U11 | Low-energy general-relativistic matching | Recover the normalized tensor kinetic term, universal conserved-stress coupling, attractive Newtonian limit, observed propagation and required weak-field metric observables. Use G01–G09 as the classical matching target. Source: `gravity/quantum-gravity.md` §§4,9. |
| U12 | Physical interacting continuum sectors | Establish domains, regulator/refinement limits, physical gauge/particle sectors and convergent interacting observables. Finite self-adjointness and conditional COM dynamics do not establish the physical continuum theory. Source: `foundations/quantum-measurement-derivation.md` §§1–3,8. |
| U13 | Curved regulator, stress and backreaction | Derive a covariant regulator or a complete foliation theory, its metric/foliation variation and renormalized stress, and couple it consistently to geometry. The optional spatial hyperdiffusion term has no established $\sigma$ matching and supplies no closed covariant stress by itself. Source: `gravity/quantum-gravity.md` §7.4.2. |
| U14 | Horizon solution, state and Hawking flux | Construct the geometry and horizon boundary problem, select a definite vacuum/initial state, and compute mode propagation and renormalized flux with backreaction where claimed. Boulware and Unruh states are different boundary choices. A finite flat-space core proves neither horizon regularity nor modified Hawking radiation. Source: `gravity/quantum-gravity.md` §§7.1,7.3–7.4. |
| U15 | Entropy, capacity and information recovery | Define the relevant subsystem/state and compute entropy, purity and the evaporation endpoint. Derive the missing state-counting factor needed to relate the linear mass capacity estimate to area-law entropy, and control regulator dependence. A Page curve cannot be inferred from pole counting or core softening. Source: `gravity/quantum-gravity.md` §§7.4–7.6. |

### 11.6 Dependency order and usable stopping points

The shortest effective atomic route fixes the physical preparation/response
map and its calibrations, chooses the gravity branch, and reconstructs the
standard pulse-and-readout model. Only then can a preregistered contrast
between preparations or sources test a distinct Cassi response. A first-
principles claim must additionally derive the carrier, physical particle
sectors and bound atom before those inputs can be called predictions.

The universal metric branch is a valid conditional null target:
$\mathcal R_{br}=1$ in the ideal point-particle regime. Scalar/direct-charge
alternatives require their source and material response before predicting a
departure. The common-lapse branch additionally needs an independent
cross-clock comparison. The interacting quantum-gravity programme requires
its own physical covariance, gauge and interaction choices before expensive
loop or horizon calculations are informative.

These are separate stopping points. A conditional COM phase does not close
an atom map; an atom map does not close a source law; an external-field
experiment does not close interacting quantum gravity.

## 12. Algebraic verification and independent calculation

The physical-domain, state-information and spectral boundaries follow from
the frozen obligations in
`computations/quantum_free_fall_closure_prereg.md`, evaluated by
`computations/verify_quantum_free_fall_closure.py`. This calculation uses no
experimental fit and changes none of the ideal-QGI proof obligations.

| Obligation | Result | Measured or exact receipt |
|---|---|---|
| QFC1 physical interval | **PASS** | Both density endpoints and both positive-denominator difference identities vanish exactly; the dense lower endpoint is $0.276393202250\ldots$ |
| QFC2 equal-$q$ counterexample | **PASS** | Two positive density pairs have $q=0.612757859604\ldots$ and opposite signs of $s,\mathcal G_C$, as tabulated in §9.1 |
| QFC3 coarse-graining | **PASS** | $q(\langle E\rangle)-\langle q(E)\rangle=0.110848938146\ldots$ for the declared two-cell witness |
| QFC4 positive spectral obstruction | **PASS** | Positive spectral kernels make $xG_E$ nondecreasing; the Gaussian derivative is strictly negative for $a>0$. The $a=0$ massless control passes |

Independent calculations used the preregistered definitions without reading
or importing the verifier. The material-state calculation reconstructed both
density pairs, the two endpoint factorizations, and the averaged-state
mismatch. A separate spectral calculation obtained

```text
xG(x1),xG(x2)= 0.36787944117144233 0.1353352832366127
finite difference xG2-xG1= -0.23254415793482963 expected <0
a=0 control xG(x1),xG(x2), difference= 1.0 1.0 0.0
```

for $ax_1=1$, $ax_2=2$. The primary verifier ended

```text
QFC4 ax=1: xG=0.367879441171; ax=2: xG=0.135335283237
QFC4 two-point difference=-0.232544157935: PASS
QFC4 standard positive spectral interpretation at sigma>0: REJECT
QFC1-QFC4: PASS
ALL CHECKS PASSED
```

The four algebraic boundaries are **ADOPT** within their declared
assumptions. The **REJECT** applies specifically to the nonzero-$\sigma$
unsubtracted positive physical covariance, as detailed in
`gravity/quantum-gravity.md` §3.1. The state map, physical source/response,
clock universality, interacting quantum theory, and experimental discriminator
retain the open scopes listed in §11.

## References

- O. Dobkowski *et al.*, “Observation of the quantum phase of free fall and the consistency with the equivalence principle,” *Science Advances* (2026), [doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045); accessible author manuscript at [arXiv:2502.14535v4](https://arxiv.org/abs/2502.14535v4).
- M. Zych and Č. Brukner, “Quantum formulation of the Einstein equivalence principle,” *Nature Physics* **14**, 1027–1031 (2018), [doi:10.1038/s41567-018-0197-6](https://doi.org/10.1038/s41567-018-0197-6); [arXiv:1502.00971](https://arxiv.org/abs/1502.00971).
- H. Lehmann, “Über Eigenschaften von Ausbreitungsfunktionen und Renormierungskonstanten quantisierter Felder,” *Il Nuovo Cimento* **11**, 342–357 (1954), [doi:10.1007/BF02783624](https://doi.org/10.1007/BF02783624).
- K. Osterwalder and R. Schrader, “Axioms for Euclidean Green's functions,” *Communications in Mathematical Physics* **31**, 83–112 (1973), [doi:10.1007/BF01645738](https://doi.org/10.1007/BF01645738).
- `foundations/quantum-measurement-derivation.md`—conditional regulated quantum mechanics and centre-of-mass reduction.
- `foundations/physical-becoming-hierarchy.md`—covariant scalar-tensor completion boundary and local PPN constraint.
- `foundations/matter-completion-boundary.md`—constant-$G_N$ closed-action gravity branch and particle-state boundary.
- `foundations/unified-lagrangian.md`—candidate common-lapse action criterion.
- `predictions/falsifiable-predictions.md`—QGI-1 and CT-2 experimental contracts.
- `gravity/quantum-gravity.md`—Gaussian physical-covariance obstruction and interacting quantum-gravity boundary.
