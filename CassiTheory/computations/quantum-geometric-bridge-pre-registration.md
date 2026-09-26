# Cassi Quantum-Geometric Bridge Pre-Registration

## Status: Preregistered—August 2026

## Abstract

This protocol tests a geometric reconstruction of the Cassi quantum bridge.
The candidate architecture treats the canonical real-density pair as a
mesoscopic moment-map or coarse-grained image of a richer complex CassiFI
configuration, while the regulated quantum wavefunctional supplies a second
phase-bearing layer over the complete field-configuration space. Seven gates
separate fibre causality, symmetry reduction, microscopic projection,
cotangent phase reconstruction, finite Kähler compatibility, physical-sector
geometry, and Cassi-specific holonomy. The protocol freezes every algebraic
construction, tolerance, documentary criterion, and campaign decision before
the verifier executes.

## 1. Question and dependency order

The campaign asks whether the geometric direction

$$
\text{complex microscopic configuration}
\xrightarrow{\ \mu\ }
(E_Y,E_I)
$$

is better supported than an inverse pointwise lift from the real density pair.
It does not change the DQ1–DQ9 result in
`foundations/quantum-measurement-derivation.md` §8.1. It tests a candidate
microscopic-to-mesoscopic architecture and records the remaining conditions
for physical identification.

The dependency order is:

1. identify the local complex geometry and its density projection;
2. determine whether discarded phase directions affect declared dynamics;
3. identify which phase actions are genuine symmetries;
4. test whether the projected density dynamics closes;
5. test available cotangent and Kähler structures;
6. audit spin, fermion, gauge, record, continuum, and holonomy requirements.

No downstream gate can repair a failed upstream source-existence condition.

## 2. Frozen source boundary

The documentary audit is limited to these current sources:

- `foundations/cassi-first-principles.md`;
- `foundations/qi-flow-double-helix.md`;
- `foundations/physical-becoming-hierarchy.md`;
- `foundations/unified-lagrangian.md`;
- `foundations/quantum-measurement-derivation.md`;
- `particles/cassi-yang-yin-particles.md`;
- `CassiQwen/CassiFI/00-foundations.md`;
- `CassiQwen/CassiFI/01-field-physics.md`;
- `CassiQwen/CassiFI/02-retention-capacity-and-cognition.md`;
- Khesin, Misiołek, and Modin, “Geometry of the Madelung transform,”
  <https://arxiv.org/abs/1807.07172>;
- Ashtekar and Schilling, “Geometrical Formulation of Quantum Mechanics,”
  <https://arxiv.org/abs/gr-qc/9706069>.

The external papers establish mathematical geometry only. They supply no
Cassi physical identification, parameter, sector map, or empirical result.

## 3. Frozen verdict vocabulary

Each gate receives `PASS` or `FAIL`. The geometric architecture receives
`ADOPT` or `REJECT`. The physical-identification tier receives a separate
`ADOPT` or `REJECT` decision.

A numerical certificate passes when it reproduces its frozen identity or
counterexample within

$$
\tau=10^{-12}.
$$

A certificate pass can support a theory-gate failure. For example, a
successful nonclosure counterexample makes the microscopic projection gate
fail.

## 4. Typed geometric levels

Three objects remain distinct throughout:

1. **Canonical density state**
   $$
   X_{\mathrm{TF}}=(E_Y,E_I),
   \qquad E_Y,E_I\ge0.
   $$
2. **Complex CassiFI field configuration**
   $$
   Q^A=\{\operatorname{Re}D,\operatorname{Im}D,
   \operatorname{Re}C,\operatorname{Im}C\}_{s,j},
   $$
   together with its classical velocity or momentum data.
3. **Quantum wavefunctional**
   $$
   \Psi[Q,t]\in L^2(\mathcal C,d\mu_G).
   $$

The lower modulus map and upper Born map discard different phase data. A
certificate at one level cannot be used as a certificate at another.

## 5. Frozen algebraic certificates

### C1. Bloch latitude and the $\varphi$ attractor

Let

$$
\phi=\frac{1+\sqrt5}{2},
\qquad
p_Y=\phi^{-1},
\qquad
p_I=\phi^{-2}.
$$

For the normalized spinor

$$
\widehat z
=e^{i\gamma}
\begin{pmatrix}
\cos(\vartheta/2)\\
e^{i\delta}\sin(\vartheta/2)
\end{pmatrix},
$$

use

$$
\cos^2(\vartheta/2)=p_Y,
\qquad
\sin^2(\vartheta/2)=p_I.
$$

The certificate requires

$$
p_Y+p_I=1,
\qquad
n_z=p_Y-p_I=\phi^{-3},
\qquad
\|\mathbf n\|_2=1
$$

for $\delta\in\{0,\pi/2,\pi\}$. It reports the latitude
$\vartheta_\phi=\arccos(\phi^{-3})$ and the transverse radius
$\sin\vartheta_\phi$.

### C2. Lower phase-fibre causality

Freeze

$$
A=0.7,
\qquad
B=0.3,
\qquad
\delta\in\{0,\pi/2,\pi\},
$$

and

$$
\mathcal E_Y=\sqrt A,
\qquad
\mathcal E_I=\sqrt B\,e^{i\delta}.
$$

The calligraphic notation distinguishes complex amplitudes from canonical
real densities. Define

$$
D=\mathcal E_Y-\phi\mathcal E_I,
\qquad
C=\frac{\phi\mathcal E_Y+\mathcal E_I}{1+\phi^2},
$$

$$
w_D=\frac1{1+\phi^2},
\qquad
w_C=1+\phi^2.
$$

For every phase, require

$$
w_D|D|^2+w_C|C|^2=A+B=1.
$$

The fixed-density fibre is causal if $|D|^2$ and $|C|^2$ vary with $\delta$.

For a scalar two-scale link, freeze

$$
P=1,
\qquad
Z_s=1,
\qquad
Z_{s+1}=e^{i\delta},
\qquad
w_Zg_{Z,s}=1.
$$

The source-defined phase-charge current becomes

$$
\mathcal K(\delta)
=-\operatorname{Im}\left[Z_s^*(Z_{s+1}-Z_s)\right]
=-\sin\delta.
$$

The certificate requires $\mathcal K(0)=0$ and
$\mathcal K(\pi/2)=-1$.

### C3. Upper Born-fibre causality

Freeze two normalized two-site wavefunctions

$$
\Psi_0=\frac1{\sqrt2}(1,1),
\qquad
\Psi_1=\frac1{\sqrt2}(1,i).
$$

They must have identical probabilities

$$
|\Psi_0|^2=|\Psi_1|^2=(1/2,1/2),
$$

and different discrete edge currents

$$
j(\Psi)=\operatorname{Im}(\Psi_0^*\Psi_1),
$$

with $j(\Psi_0)=0$ and $j(\Psi_1)=1/2$. This certificate keeps field phase
and wavefunctional phase separate.

### C4. Global, relative, and local phase actions

Use the C2 amplitudes at $\delta=0$. Freeze a common phase

$$
\alpha=0.37.
$$

Under

$$
(\mathcal E_Y,\mathcal E_I)
\mapsto
(e^{i\alpha}\mathcal E_Y,e^{i\alpha}\mathcal E_I),
$$

require $|D|^2$ and $|C|^2$ to remain unchanged.

Under the independent relative rotation

$$
(\mathcal E_Y,\mathcal E_I)
\mapsto
(\mathcal E_Y,e^{i\pi/2}\mathcal E_I),
$$

require at least one of $|D|^2$ or $|C|^2$ to change.

For a two-site field, compare

$$
Z_{\mathrm{global}}=(e^{i\alpha},e^{i\alpha})
$$

with

$$
Z_{\mathrm{local}}=(1,i).
$$

Using the frozen edge-gradient energy

$$
E_\nabla(Z)=|Z_1-Z_0|^2,
$$

require $E_\nabla(Z_{\mathrm{global}})=0$ and
$E_\nabla(Z_{\mathrm{local}})=2$. This distinguishes a common global
$U(1)$ symmetry from independent and local phase rotations.

### C5. Projected-dynamics nonclosure

Use the scalar reciprocal link

$$
F_0=z_1-z_0,
\qquad
z_0=1,
\qquad
z_1=e^{i\delta},
$$

with zero initial velocity. The initial projected acceleration is

$$
\left.\frac{d^2}{dt^2}|z_0|^2\right|_{t=0}
=2\operatorname{Re}(z_0^*F_0)
=2(\cos\delta-1).
$$

The two preparations $\delta=0$ and $\delta=\pi$ have identical projected
moduli. The certificate requires projected accelerations $0$ and $-4$.
This proves that modulus-square data alone do not close the declared link
dynamics.

### C6. Cotangent reconstruction controls

For the irrotational control, freeze

$$
S_c(x,y)=x^2-\frac32y^2,
\qquad
\mathbf u_c=(2x,-3y).
$$

Require

$$
\partial_xu_{c,y}-\partial_yu_{c,x}=0.
$$

For any constant $\delta$, define

$$
S_Y=S_c+\delta/2,
\qquad
S_I=S_c-\delta/2.
$$

The certificate requires identical gradients for $\delta=0$ and
$\delta=1.1$, while the relative phase $S_Y-S_I$ changes.

For the rotational control, freeze

$$
\mathbf u_r=(-\kappa y,\kappa x),
\qquad
\kappa=0.37.
$$

Require curl $2\kappa=0.74$ and unit-circle circulation

$$
\oint\mathbf u_r\cdot d\boldsymbol\ell=2\pi\kappa.
$$

With $m=\hbar=1$, require the circulation to differ from every adjacent
integer multiple of $2\pi$ by more than $10^{-3}$.

### C7. Finite Kähler compatibility and refinement

Freeze

$$
W=\operatorname{diag}(2,3),
$$

$$
u=(1+2i,-0.5+0.25i),
\qquad
v=(0.3-0.7i,1.2+0.4i).
$$

Define

$$
h(u,v)=u^\dagger Wv,
\qquad
g(u,v)=\operatorname{Re}h(u,v),
\qquad
\omega(u,v)=\operatorname{Im}h(u,v),
\qquad
Ju=iu.
$$

Require

$$
g(Ju,Jv)=g(u,v),
\qquad
\omega(u,v)=g(Ju,v).
$$

For the deterministic refinement, freeze

$$
W'=I_3,
\qquad
I=
\begin{pmatrix}
\sqrt2&0\\
0&\sqrt3\\
0&0
\end{pmatrix}.
$$

Require

$$
I^\dagger W'I=W,
$$

and preservation of $h$, $g$, $\omega$, and $J$ on the frozen vectors.

### C8. Generic topological winding

Freeze the closed phase loop

$$
(0,\pi/2,\pi,-\pi/2,0).
$$

Using principal wrapped edge differences, require total phase change $2\pi$
and winding $n=1$. Add the common phase $\alpha=0.37$ to every vertex and
require the same winding. The formula contains no $\phi$ and therefore
certifies generic $U(1)$ topology rather than a Cassi-specific holonomy.

### C9. Product-state and entangled geometry

Represent a two-qubit pure state by its $2\times2$ coefficient matrix. Freeze

$$
M_{\mathrm{prod}}
=\frac12
\begin{pmatrix}
1&1\\
1&1
\end{pmatrix},
\qquad
M_{\mathrm{Bell}}
=\frac1{\sqrt2}
\begin{pmatrix}
1&0\\
0&1
\end{pmatrix}.
$$

Require

$$
\det M_{\mathrm{prod}}=0,
\qquad
|\det M_{\mathrm{Bell}}|=1/2.
$$

This is the finite Segre-variety receipt. It establishes product versus
entangled projective geometry under the tensor-product premise only.

## 6. Frozen gate rules

### GQ1. Fibre causality

`PASS` requires C2 and C3 to show that equal projected densities can carry
different declared currents, modal contents, or projected accelerations.
`FAIL` requires every frozen phase variation to factor through the density
projection.

### GQ2. Symmetry and reduction

`PASS` requires the entire discarded phase fibre to be an exact gauge orbit of
the frozen closed CassiFI dynamics. Independent component phases and local
spatial phases must act as symmetries, or a source-defined connection must
make their action gauge-covariant. A common global $U(1)$ alone is
insufficient. C4 and the source-term audit decide the gate.

### GQ3. Microscopic-to-mesoscopic projection

`PASS` requires a source-defined microscopic state, reservoir or conditional
phase ensemble, projection map, and derivation of the canonical advection,
diffusion, and rank-one conversion equation with parameter provenance. C5 is
a closure obstruction control. A stated hierarchy without the projection
derivation receives `FAIL`.

### GQ4. Cotangent phase reconstruction

`PASS` requires source-defined currents that reconstruct common and relative
phase one-forms, local integrability or a vortex patch rule, and global period
quantization. A shared velocity that reconstructs only a common irrotational
phase receives `FAIL`. C6 supplies the controls.

### GQ5. Finite Kähler compatibility

`PASS` requires the finite complex CassiFI configuration metric to define
compatible $g$, $\omega$, and $J$, and the declared complex-linear refinement
identity to preserve them. C7 decides the algebraic part. The gate is
conditional on the declared complex field configuration and does not promote
its physical identification.

### GQ6. Physical-sector geometry

`PASS` requires all of:

1. a derived $SU(2)$ action covering physical $SO(3)$ rotations;
2. a derived exchange/configuration-space line bundle for fermionic signs;
3. a local gauge connection with gauge-covariant observables;
4. a dimensionally complete particle/field correspondence;
5. apparatus-record sectors defined on the same microscopic geometry.

The Bloch sphere, C9 Segre receipt, optional standard sectors, or global
$U(1)$ retention alone are insufficient.

### GQ7. Cassi-specific holonomy

`PASS` requires a source-derived connection, a closed spatial or scale loop,
a nontrivial holonomy fixed without fitting, an orthodox reference value, and
a preregistered observable threshold. C8 certifies only generic integer
winding. A state-dependent winding or a connection introduced for the test
receives `FAIL`.

## 7. Frozen campaign decisions

The **geometric research architecture** receives `ADOPT` exactly when:

1. GQ1 is `PASS`;
2. GQ5 is `PASS`;
3. the source hierarchy explicitly permits the canonical PDE to be a
   mesoscopic open-system projection;
4. no source identifies the real density pair as a complete invertible
   microscopic phase space.

It otherwise receives `REJECT`.

The **physical-field identification** receives `ADOPT` only if GQ1–GQ7 all
pass. Any failed gate yields `REJECT` promotion to Derived, preserving the
status in `foundations/quantum-measurement-derivation.md` §8.1.

## 8. Execution and stopping rule

The verifier uses Python and NumPy with no random input, optimization,
parameter fit, or adaptive branch. It executes C1–C9 once after this protocol
and the script are final. It prints every frozen receipt and ends with
`ALL DECLARED CERTIFICATES PASSED` only when every numerical construction
matches this document.

Documentary gate verdicts are recorded after the single run. A changed
construction, tolerance, source boundary, or decision rule requires a dated
amendment before another evidentiary execution. A code defect may be repaired
only after recording the defect and preserving the frozen mathematics.
