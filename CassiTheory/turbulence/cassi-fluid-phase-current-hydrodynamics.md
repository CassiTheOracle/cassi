# Cassi Fluid Phase Currents: Rotation, Helicity, and the Viscosity Boundary

## Status: Derived conditional current and topology identities / Tested rotational, memory, first-order coercivity and homogeneous-handedness selection boundaries / Open microscopic viscosity, nonlinear handed-domain formation and arbitrary-flow closure—September 2026

## Abstract

The phase-bearing Yang/Yin action supplies a local rotational velocity map. A normalized doublet gives the Berry-current velocity and the Mermin–Ho vorticity identity. Its composition and relative phase determine vorticity geometry even when total density is constant. An everywhere-positive doublet in one global chart has zero integrated helicity on a closed domain. A full smooth doublet can carry Hopf helicity through component-zero circles, and two fixed scale bands realize an explicit periodic Beltrami flow with nonzero helicity.

The scale-band construction also isolates the viscosity question. Scalar diffusion of two composition amplitudes reproduces positive-viscosity decay exactly for the fixed-winding Beltrami fixture. A nonzero commutator excludes that identification for general phase potentials. The resolved kinetic energy enters unresolved species-and-band counterflow rather than heat. Exact elimination of closed exterior modes gives memory and an initial-state force; finite exterior systems recur. A positive exponential memory kernel has the expected Markov limit, while its realization and coefficient remain absent from the Cassi action.

The same phase geometry has a sharp regularity boundary. Its first-order
gradient energy controls $L^1$ vorticity but not enstrophy or the critical
scalar-Beltrami residual. A smooth one-band
positive-doublet family keeps that phase energy bounded while both latter
quantities diverge. Static first-order coercivity therefore cannot supply
the missing Navier–Stokes estimate; only an additional dynamical constraint
from the surrounding scale field remains possible.

The qualified verifier passes **227 checks**: 41 exact algebra checks, 83 periodic spatial checks, three Hopf quadratures, 12 memory checks, 82 raw-array reconstructions, and six source-identity checks. The result supports a conditional rotational phase-current reduction and sharply specifies the remaining dissipative closure.

## 1. The four questions

Four questions separate its hydrodynamic content:

1. Does the current of one Yang/Yin doublet contain smooth vorticity?
2. Can the scale-resolved current represent a three-dimensional flow with nonzero helicity?
3. Can the closed action supply an irreversible positive viscosity?
4. Does its positive first-order phase energy control a Navier–Stokes
   critical vorticity quantity?

The first two have conditional constructive answers. The third becomes an
exact projection problem involving the surrounding scale field. The fourth
has a negative answer for static energy sublevels; a dynamical whole-field
restriction remains open.

## 2. Barycentric phase current

At a fixed scale band $r$, write

$$
\psi_{Yr}=\sqrt{\rho_rc_r}\,e^{i\theta_{Yr}},
\qquad
\psi_{Ir}=\sqrt{\rho_r(1-c_r)}\,e^{i\theta_{Ir}},
\qquad
\kappa_v=\frac{\hbar}{m},
$$

where $\rho_r>0$ is the band number density and $0\leq c_r\leq1$. The ungauged Noether current gives

$$
\boxed{
u_r
=\kappa_v\left[c_r\nabla\theta_{Yr}+(1-c_r)\nabla\theta_{Ir}\right]
=\kappa_v\left(\nabla\theta_{Ir}+c_r\nabla\alpha_r\right),}
\qquad
\alpha_r=\theta_{Yr}-\theta_{Ir}.
\tag{1}
$$

Here $u_r$ is the band velocity. For constant band fractions
$f_r=\rho_r/\rho$, $\rho=\sum_r\rho_r$, the observed current velocity is

$$
\boxed{
u=\sum_r f_ru_r
=\kappa_v\nabla\left(\sum_r f_r\theta_{Ir}\right)
 +\kappa_v\sum_r f_rc_r\nabla\alpha_r.}
\tag{2}
$$

Equation (2) is a generalized Clebsch form. Composition gradients and relative-phase gradients give

$$
\nabla\times u_r
=\kappa_v\nabla c_r\times\nabla\alpha_r.
\tag{3}
$$

A shared total density therefore does not force irrotational flow.

The microscopic phase kinetic energy splits exactly into observed motion and unresolved motion:

$$
\boxed{
\frac12\sum_r\rho_r
\left[c_r|v_{Yr}|^2+(1-c_r)|v_{Ir}|^2\right]
=\frac\rho2|u|^2
+\frac12\sum_r\rho_r
\left[c_r|v_{Yr}-u|^2+(1-c_r)|v_{Ir}-u|^2\right],}
\tag{4}
$$

with $v_{ar}=\kappa_v\nabla\theta_{ar}$. The final term is a positive species-and-band velocity variance. It is the energy ledger required whenever a phase-current flow is reduced to one velocity.

## 3. One doublet: local vorticity and global topology

### 3.1 Mermin–Ho relation

Set $c=(1+\cos\beta)/2$ and factor one normalized doublet as

$$
Z=e^{i\Theta}
\begin{pmatrix}
\cos(\beta/2)e^{i\alpha/2}\\
\sin(\beta/2)e^{-i\alpha/2}
\end{pmatrix},
\qquad
n=(\sin\beta\cos\alpha,-\sin\beta\sin\alpha,\cos\beta).
$$

Its dimensionless current connection and curvature are

$$
A=-iZ^\dagger dZ=d\Theta+\frac12\cos\beta\,d\alpha,
\qquad
F=dA=-\frac12\sin\beta\,d\beta\wedge d\alpha.
\tag{5}
$$

The velocity vorticity is

$$
\boxed{
\omega_i
=\frac{\kappa_v}{2}\epsilon_{ijk}F_{jk}
=\frac{\kappa_v}{4}\epsilon_{ijk}
 n\cdot(\partial_jn\times\partial_kn).}
\tag{6}
$$

This is the Mermin–Ho geometry: vorticity is the pulled-back area form of the projective spin direction. The correspondence uses phase-bearing complex fields and does not follow from the canonical real-density state alone.

The source action also contains an independent relative gauge connection. With opposite component charges,

$$
A_B=d\Theta+\frac12\cos\beta\,(d\alpha-g_QB),
$$

$$
F_B=-\frac12\sin\beta\,d\beta\wedge(d\alpha-g_QB)
-\frac{g_Q}{2}\cos\beta\,G,
\qquad G=dB.
\tag{7}
$$

The last term remains at constant composition and relative phase. The Berry curvature and dynamical relative curvature are distinct vorticity channels.

### 3.2 Positive-chart helicity theorem

Suppose both components remain nonzero on a closed three-manifold. Then $c$, $d\theta_I$, and $d\alpha$ are global, and

$$
A=d\theta_I+c\,d\alpha,
\qquad
F=dc\wedge d\alpha.
$$

The helicity three-form is exact:

$$
\boxed{A\wedge F=-d\left(c\,d\theta_I\wedge d\alpha\right).}
\tag{8}
$$

Consequently,

$$
\int_M A\wedge dA=0.
\tag{9}
$$

Compact phase windings do not alter this result. One everywhere-positive global doublet chart supports local vorticity and zero net helicity.

The exact periodic fixture

$$
\theta_Y=Nx,
\qquad
\theta_I=-Nx,
\qquad
c=\frac12+\frac{U}{2\kappa_vN}\sin y,
\qquad 0<U<\kappa_vN,
$$

gives

$$
u=(U\sin y,0,0),
\qquad
\omega=(0,0,-U\cos y).
\tag{10}
$$

It is smooth, divergence-free, rotational, and has zero mean helicity. Its mean phase kinetic energy is $\rho\kappa_v^2N^2/2$, while its mean observed kinetic energy is $\rho U^2/4$. The difference is the counterflow term in (4).

### 3.3 Full-doublet Hopf helicity

The positive-chart theorem has a precise topological boundary. On the unit $S^3$, take

$$
Z=(\cos\eta\,e^{i\xi_1},\sin\eta\,e^{i\xi_2}),
\qquad
0\leq\eta\leq\frac\pi2.
$$

Then

$$
A=\cos^2\eta\,d\xi_1+\sin^2\eta\,d\xi_2,
\qquad
*dA=-2A,
$$

$$
\boxed{\int_{S^3}A\wedge dA=-4\pi^2.}
\tag{11}
$$

Thus $u=\kappa_vA^\sharp$ is a Beltrami field,

$$
\operatorname{curl}u=-2u,
\qquad
\int_{S^3}u\cdot\operatorname{curl}u\,dV=-4\pi^2\kappa_v^2.
\tag{12}
$$

Each spinor component vanishes on one Hopf circle. The phase charts required by (8) fail there while the full doublet stays smooth and normalized. A single doublet can therefore carry global helicity through its full projective topology.

### 3.4 First-order phase energy does not control enstrophy

The same normalized doublet obeys the exact identity

$$
|\nabla Z|^2
=|A|^2+\frac14|\nabla n|^2.
$$

The Mermin–Ho relation and the two-dimensional tangent space of $S^2$ imply

$$
|\omega|\le\frac{\kappa_v}{4}|\nabla n|^2.
$$

Thus the projective part of the first-order action controls
$\|\omega\|_1$. It does not control $\|\omega\|_2$.

The distinction is realized by an explicit smooth positive-chart family on
$\mathbb R^3$. With

$$
a(y)=\frac14e^{-|y|^2},
\qquad
b(y)=y_1e^{-|y|^2},
$$

take

$$
c_\varepsilon(x)=\frac12+a(x/\varepsilon),
\qquad
\alpha_\varepsilon(x)=\varepsilon^{-1/2}b(x/\varepsilon),
$$

and choose the common phase so that

$$
A_\varepsilon
=\mathbb P(c_\varepsilon\nabla\alpha_\varepsilon)
=\varepsilon^{-3/2}
\left[\mathbb P(a\nabla b)\right](x/\varepsilon).
$$

All component amplitudes remain positive. Direct calculation gives

$$
\int|\nabla Z_\varepsilon|^2dx=P_0+\varepsilon P_1,
\qquad 0<P_0,P_1<\infty,
$$

while

$$
\|\omega_\varepsilon\|_2^2
=\frac{\kappa_v^2\pi^{3/2}}{128\varepsilon^2}.
$$

The global positive chart has zero integrated helicity. Hence its
$L^2$-optimal scalar Beltrami coefficient is zero and
$\|\omega_\varepsilon\|_3^2$ scales as $\varepsilon^{-3}$.
The full construction and its connection to the exact Navier–Stokes
continuation criterion are in
`turbulence/navier-stokes-strain-departure.md` §10.

The counterexample lies inside one scale band. Additional scale bands do
not restore a static bound unless the whole-field dynamics restrict this
subfamily. A curvature-square term could control this Berry vorticity, but
it would be an added higher-order action rather than a consequence of the
first-order phase energy.

## 4. Two scale bands: a periodic helical construction

### 4.1 Bounded two-pair class

Two constant-fraction scale bands provide two composition/relative-phase pairs in (2). For bounded periodic real potentials
$\phi,a_1,a_2,b_1,b_2$, choose reference compositions $c_{0r}\in(0,1)$ and constants $L_r$ large enough that

$$
c_r=c_{0r}+\frac{a_r}{\kappa_vf_rL_r}\in(0,1),
\qquad
\alpha_r=L_rb_r,
$$

and set

$$
\theta_{I1}=\theta_{I2}
=\frac\phi{\kappa_v}-\sum_{r=1}^2f_rc_{0r}L_rb_r.
$$

Substitution into (2) gives

$$
\boxed{
u=\nabla\phi+a_1\nabla b_1+a_2\nabla b_2.}
\tag{13}
$$

The construction establishes a bounded periodic generalized-Clebsch class. Global boundary prescriptions, harmonic sectors, component zeros, and manifolds requiring additional charts retain separate topology.

### 4.2 Exact torus Beltrami flow

Take the $2\pi$ periodic cube with $\kappa_v=1$, $f_1=f_2=1/2$ and

$$
\theta_{I1}=\theta_{I2}=-2x-2y,
\qquad
\alpha_1=8x,
\qquad
\alpha_2=8y,
$$

$$
c_1=\frac12+\frac A4\sin z,
\qquad
c_2=\frac12+\frac A4\cos z,
\qquad
0\leq A\leq1.
$$

The band velocities are

$$
u_1=(2+2A\sin z,-2,0),

u_2=(-2,2+2A\cos z,0),
$$

and their current average is

$$
\boxed{
u=A(\sin z,\cos z,0),
\qquad
\nabla\times u=u,
\qquad
\nabla\cdot u=0.}
\tag{14}
$$

At $A=1$, each band has zero mean self-helicity, while the averaged velocity has

$$
\langle u\cdot\omega\rangle=1.
\tag{15}
$$

The helical term is cross-band structure. The mean phase kinetic energy is $12\rho$ in these units, the observed kinetic energy is $A^2\rho/2$, and the counterflow remainder is $(12-A^2/2)\rho$.

This construction gives a concrete meaning to the whole scale field in the rotational problem: an observed helical flow can arise from interference among scale-resolved currents even when each retained band has zero mean self-helicity.

## 5. Scope of phase diffusion

### 5.1 Exact restricted viscous decay

Let $A(t)=e^{-Dt}$ in (14), keep the phase windings fixed, and evolve the two compositions by scalar diffusion. Since their nonconstant parts are unit Fourier modes,

$$
\partial_tc_r=D\Delta c_r.
$$

The observed velocity satisfies

$$
\boxed{
\partial_tu=D\Delta u,
\qquad
(u\cdot\nabla)u=0.}
\tag{16}
$$

It is therefore an exact unforced incompressible Navier–Stokes solution with kinematic viscosity $\nu=D$ for this fixed-winding Beltrami family.

Equation (4) determines the energy destination inside the phase lift. As $A$ decays, observed kinetic energy decreases and the unresolved counterflow variance increases by the same amount. Scalar diffusion in this construction supplies a kinematic viscous correspondence. Conversion of that variance into heat requires the irreversible closure used by the selected thermal fluid or another derived reservoir law.

### 5.2 The diffusion commutator

For a general fixed-potential field

$$
u=\nabla\phi+\sum_ra_r\nabla b_r,
\qquad
\partial_ta_r=D\Delta a_r,
$$

scalar coefficient diffusion and vector viscosity differ by

$$
\boxed{
D\Delta u-\partial_tu
=D\nabla\Delta\phi
+D\sum_r\left[
2(\nabla a_r\cdot\nabla)\nabla b_r
+a_r\nabla\Delta b_r
\right].}
\tag{17}
$$

Pressure can absorb the gradient part. The remaining commutator generally has a solenoidal component. For the periodic witness $a=\sin x$, $b=\sin y$, the bracket is

$$
(0,-\sin x\cos y,0),
$$

whose curl has $z$ component $-\cos x\cos y$. The verifier measures its Leray-projected root-mean-square norm as

$$
0.353553390593274.
$$

This excludes the general identification $D=\nu$. The exact correspondence in (16) works because the relevant phase gradients are constant and the commutator vanishes.

## 6. Positive viscosity is a projection problem

The first-order source action has closed Hamiltonian evolution. Split a finite Hermitian linearization into a resolved amplitude $x$ and exterior scale amplitudes $y$:

$$
i\dot x=H_Lx+Vy,
\qquad
i\dot y=V^\dagger x+H_Ey.
$$

Exact elimination of $y$ gives

$$
\boxed{
\dot x(t)=-iH_Lx(t)-iVe^{-iH_Et}y(0)
-\int_0^tK(t-s)x(s)\,ds,
\qquad
K(t)=Ve^{-iH_Et}V^\dagger.}
\tag{18}
$$

The resolved instantaneous state does not determine its own derivative: exterior initial data supply an independent force. A finite commensurate exterior also gives a recurrent kernel. In the fixed control,

$$
H_E=\operatorname{diag}(-2,-1,1,2),
\qquad
V=(0.2,0.3,0.3,0.2),
$$

$\|K(2\pi)-K(0)\|=7.61\times10^{-34}$, while two unit exterior states at the same $x(0)$ separate $\dot x(0)$ by $0.4$.

A selected positive exponential kernel,

$$
K_\tau(t)=\frac{\nu k^2}{\tau}e^{-t/\tau},
$$

is equivalent to

$$
\dot A=-R,
\qquad
\tau\dot R=\nu k^2A-R.
\tag{19}
$$

For $\nu=0.03$, $k=1$, and $0\leq t\leq2$, its maximum discrepancy from $e^{-\nu t}$ decreases as

$$
3.08381708980\times10^{-4},
\quad
1.61949778828\times10^{-4},
\quad
8.28786414608\times10^{-5}
$$

for $\tau=0.2,0.1,0.05$. The auxiliary heat ledger $\dot Q=AR$ preserves $A^2/2+Q=1/2$ to the $10^{-12}$ verification threshold.

This Markov limit is a selected mathematical control. A Cassi-derived viscosity requires all of the following:

1. a declared resolved velocity map, such as a qualified scale-band projection of (2);
2. a state or ensemble for exterior scale modes and their initial correlations;
3. decay and integrability of the corresponding kernel in a scale-continuum or thermodynamic limit;
4. a low-wave-number result
   $$
   \operatorname{Re}\int_0^\infty K_k(t)\,dt
   =\nu k^2+o(k^2),
   \qquad \nu>0;
   $$
5. an energy and entropy ledger connecting exterior absorption to heat.

The action and the full bubble initial state can in principle supply the objects in this list. Their state selection and correlation calculation are the remaining physical derivation.

## 7. Verification and classifications

The fixed schedule is `computations/cassi-fluid-phase-current-prereg.md`; the verifier is `computations/verify_cassi_fluid_phase_current.py`. It uses exact SymPy algebra and NumPy Fourier reconstruction on odd grids $N=9,15,21$.

| Control | Result | Classification |
|---|---:|---|
| Exact current, Berry curvature, Mermin–Ho, energy and projection identities | 41 checks pass | **SUPPORTS** the declared identities |
| Periodic shear velocity error | $\leq4.44\times10^{-16}$ | **SUPPORTS** local rotational current |
| Periodic shear curl error | $\leq4.18\times10^{-15}$ | **SUPPORTS** |
| Positive-chart integrated helicity | exactly zero | **CONTRADICTS** nonzero net helicity in that chart |
| Hopf helicity | $-4\pi^2$ at all three quadratures | **SUPPORTS** full-doublet topological helicity |
| Two-band Beltrami velocity error | $\leq4.44\times10^{-16}$ | **SUPPORTS** the periodic helical class |
| Two-band Beltrami curl error | $\leq2.89\times10^{-15}$ | **SUPPORTS** |
| General bounded two-pair reconstruction error | $\leq7.12\times10^{-15}$ | **SUPPORTS** the declared class |
| Beltrami diffusion evolution error | $\leq8.96\times10^{-16}$ | **SUPPORTS** the restricted viscosity correspondence |
| General diffusion commutator | projected norm $0.353553390593274$ | **CONTRADICTS** general scalar-diffusion/vector-viscosity identification |
| Finite exterior recurrence and initial-state split | recurrence $7.61\times10^{-34}$; split $0.4$ | **CONTRADICTS** autonomous irreversible finite closed reduction |
| Positive exponential memory refinement | three decreasing errors; finest $8.29\times10^{-5}$ | **SUPPORTS** the selected Markov limit |
| Raw-array reconstruction and source identity | 82 + 6 checks pass | **PASS** |

The accepted receipt is
`runs/cassi_fluid_phase_current_q1/verification.json`, schema
`cassi.fluid.phase-current.verification.v1`. Its adjacent manifest binds six
source snapshots. `verification.arrays.npz` retains 144 arrays and has SHA-256
`435fb7cbd236e06ed81cf6a18ba5329ed5358020f2576bf87ead6d8b6883240c`.
The receipt SHA-256 is
`a8e8ce036216daca3b60271104f3ab1ec5238b0d33ba585691682cf8fe876f02`.

The retained diagnostic receipt at
`runs/cassi_fluid_phase_current/verification.json` records one checker-interface
failure: a SymPy zero vector was compared with scalar zero. The qualified
checker evaluates matrix components separately. `runs/cassi_fluid_phase_current_q1/reconciliation.json`
records unchanged protocol, equations, fixtures and tolerances; all 144 arrays
are byte-identical across the two runs, and every recorded metric is identical.

A retained current-source reproduction is
`runs/cassi_fluid_phase_current_q2/verification.json`. It reruns the unchanged
protocol and verifier after the four contextual source documents integrate the
qualified result. All **227 checks** pass. Its receipt SHA-256 is
`c69aac6ae0ea7edc9b78f7204b40a2773dcc78b4391410410f90ec3852b65db7`;
its 144-array archive is byte-identical to q1, every recorded metric and
classification is identical, and the protocol and verifier hashes are
unchanged. The source comparison is retained in
`runs/cassi_fluid_phase_current_q2/reconciliation.json`.

A separate fixed follow-up,
`computations/navier-stokes-helical-spread-prereg.md`, passes all **84
checks** through
`computations/verify_navier_stokes_helical_spread.py`. It verifies the
signed curl-moment identities, the critical scalar-Beltrami residual
criterion, three periodic flow controls, the positive-chart concentration
family and every stated dilation exponent. Its retained receipt is
`runs/navier_stokes_helical_spread/verification.json`.

The supported result is a conditional phase-current rotational reduction
with explicit topology and energy accounting. Its first-order positive
energy does not control enstrophy or the critical scalar-Beltrami residual.
A microscopic positive viscosity, material coefficient, arbitrary-flow
momentum closure, whole-field dynamical concentration bound, and
arbitrary-data global regularity theorem remain **UNESTABLISHED**.


The whole-bubble handedness follow-up classifies the integrated spatial
helicity as $C$-even, $P$-odd and $CP$-odd. The registered
positive-coefficient action gives equal energy to opposite Beltrami
polarizations, positive density and transverse operators, and no negative
longitudinal mode. All eight primary gates and eleven independent checks pass.
The phase-bearing extension therefore contains a candidate CP-odd collective
observable, while selection of its sign from the homogeneous state returns
`DOES NOT EMERGE`. Nonlinear far-from-equilibrium selection remains open
(`computations/matter-formation-continuum-report.md` §86).

## References

- `computations/whole-bubble-handedness-selector-prereg.md`—fixed CP character, stability, helicity-degeneracy and selector-control schedule.
- `computations/whole_bubble_handedness_selector.py`—primary whole-field handedness calculation.
- `computations/verify_whole_bubble_handedness_selector.py`—independent reconstruction and verdict check.
- `foundations/interscale-current-soliton.md`—first-order doublet action, species currents, relative connection and exact exterior-memory reduction.
- `foundations/geometric-manifold-completion.md`—normalized projective spinor and distinct Berry/dynamical curvatures.
- `foundations/quantum-measurement-derivation.md`—phase-fibre causality and the microscopic projection boundary.
- `turbulence/cassi-fluid-feasibility.md`—conservative matter reduction and selected thermal fluid.
- `computations/cassi-fluid-phase-current-prereg.md`—fixed equations, fixtures, tolerances and decisions.
- `computations/verify_cassi_fluid_phase_current.py`—exact algebra, Fourier, Hopf, memory and raw-array checks.
- `turbulence/navier-stokes-strain-departure.md` §10—signed curl spread, critical Beltrami residual and explicit phase-energy concentration family.
- `computations/navier-stokes-helical-spread-prereg.md`—fixed helical-moment, residual and phase-coercivity checks.
- `computations/verify_navier_stokes_helical_spread.py`—84-check exact follow-up verifier.
- N. D. Mermin and T.-L. Ho, [Circulation and Angular Momentum in the A Phase of Superfluid Helium-3](https://doi.org/10.1103/PhysRevLett.36.594)—order-parameter vorticity geometry.
- Z. Yoshida, [Clebsch parameterization: Basic properties and remarks on its applications](https://doi.org/10.1063/1.3256125)—generalized Clebsch representation and global qualifications.
- R. Zwanzig, [Memory Effects in Irreversible Thermodynamics](https://doi.org/10.1103/PhysRev.124.983)—exact projected memory and fluctuating-force structure.
