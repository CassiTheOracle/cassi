# Loop-to-Bubble Projection Theorem: Shared-Support Counterflow, Coherence, and Scale Separation

## Status: Derived conditional projection, bubble map, and population spectrum; Hypothesized microscopic physical identification—August 2026

## Abstract

A phase-bearing Yang/Yin carrier state on one closed loop can project exactly
to the canonical real two-fluid PDE. The minimal shared-support state has four
nonnegative populations: Yang and Yin carriers in the two orientations of one
loop. Periodic loop transport, loop diffusion, and symmetric direction
exchange disappear or conserve under the complete loop average. Direction-
preserving Yang/Yin conversion then projects to the canonical
$q$-gated conversion law when the gate is evaluated on the projected
densities and is common around the loop.

The same microscopic amplitudes define a $2\times2$ species coherence matrix.
Its normalized Bloch vector lies in the unit ball by Cauchy–Schwarz. An affine
axis map sends the ball to the quadratic bubble volume. Fully coherent,
rank-one loop states lie on the shell used by the string-to-bubble projective
map; unresolved phase structure lies in the interior. Equal contributions
whose relative phases alternate by $\pi$ cancel the transverse coherence
exactly in even pairs.

The frozen internal population generator has an explicit Fourier spectrum.
Its nonzero-mode gap gives a dynamical criterion for when a bubble-scale
observer may retain only the loop zero mode. The gap is a rate separation. A
universal spatial ratio between strand and bubble scales requires additional
geometry or dynamics. The construction supplies a conditional carrier-to-
density projection and a coherence-sensitive bubble coordinate. A physical
phase law, a map from the regulated quantum configuration to these carriers,
$\hbar$, quantum statistics, and measurement dynamics remain separate inputs.

---

## 1. Scope and dependency boundary

The construction combines four existing parts of the theory:

1. the canonical real densities and $q$-gated rank-one conversion in
   `foundations/cassi-first-principles.md`;
2. the finite carrier-to-density limit in
   `foundations/quantum-measurement-derivation.md` §8.4;
3. the direction-resolved diagnostic in
   `foundations/qi-flow-double-helix.md`;
4. the pure-state projective shell map in
   `foundations/string-bubble-projective-map.md`.

The theorem adds one closed internal coordinate and one direction label to the
carrier description. It uses a single geometric support. The labels $s=+1$
and $s=-1$ denote the two counterorientations of that support.

Three claims have separate statuses:

- **Derived conditional:** the stated microscopic population equation projects
  exactly to the canonical two-fluid PDE.
- **Derived conditional:** the species coherence matrix maps to the affine
  bubble volume, with the coherent rank-one boundary mapping to the shell.
- **Hypothesized:** physical Yang/Yin microcarriers occupy such a loop and the
  complex amplitudes carry the microscopic phase of nature.

The inverse reconstruction is underdetermined because the projection is many
to one.

---

## 2. Shared-support microscopic state

### 2.1 Loop fibre over the bubble-scale base

Let $B$ be the spatial domain on which the canonical fields are resolved. At
each $x\in B$, attach one closed internal coordinate

$$
\chi\in S^1\cong[0,2\pi),
\qquad
\chi\sim\chi+2\pi.
$$

A circular realization may have physical radius $R>0$ and arclength
$\ell=R\chi$. The theorem only uses closure and periodicity. The physical
embedding may be noncircular provided its transport coefficients are written
in a periodic loop coordinate.

For carrier label $a\in\{Y,I\}$ and orientation $s\in\{+1,-1\}$, define a
phase-bearing amplitude

$$
\psi_{a,s}(x,\chi,t)
:=\sqrt{f_{a,s}(x,\chi,t)}\,
 e^{i\theta_{a,s}(x,\chi,t)},
$$

with

$$
f_{a,s}\geq0,
\qquad
\psi_{a,s}(x,\chi+2\pi,t)=\psi_{a,s}(x,\chi,t).
$$

The amplitudes provide a kinematic phase lift of the populations. The
population theorem below specifies the evolution of $f_{a,s}$. It leaves the
phase law for $\theta_{a,s}$ open.

### 2.2 Complete loop projection

Use the normalized loop average

$$
\langle g\rangle_\chi
:=\frac{1}{2\pi}\int_0^{2\pi}g(\chi)\,d\chi.
$$

Define the projected species densities by

$$
\boxed{
E_a(x,t)
:=\sum_{s=\pm1}\langle f_{a,s}(x,\cdot,t)\rangle_\chi
},
\qquad a\in\{Y,I\}.
\tag{LB1}
$$

The canonical combinations are

$$
\rho:=E_Y+E_I,
\qquad
\varepsilon:=E_Y-\varphi E_I,
\tag{LB2}
$$

and

$$
q(E_Y,E_I)
:=
\frac{\rho^2}
{\rho^2+\varphi^{-2}+\varepsilon^2}.
\tag{LB3}
$$

Here $E_Y$, $E_I$, $\rho$, and $\varepsilon$ are the reference-normalized
dimensionless densities defined in `foundations/cassi-first-principles.md`
§2.1. A physical-density interpretation requires its external scale
$\rho_*$.

For finite nonnegative densities, $0\leq q<1$.

### 2.3 Information retained and discarded

Equation (LB1) retains two real numbers at each $(x,t)$. It discards:

- every nonzero loop Fourier mode;
- the orientation-resolved density difference;
- all four phases and their winding;
- phase correlations between Yang and Yin;
- correlations between carrier label and orientation.

Distinct microscopic loop states therefore have identical canonical
$(E_Y,E_I)$. Sections 4 and 5 retain one additional phase-sensitive moment
without changing the density projection.

---

## 3. Minimal loop population dynamics

### 3.1 Conditional generator

Let $\mathbf u(x,t)$ be the common exterior velocity and $D_x\geq0$ the
common exterior diffusivity. For a circular loop, define

$$
\Omega:=\frac{v}{R},
\qquad
d:=\frac{D_\ell}{R^2},
\tag{LB4}
$$

where $v$ is the oriented loop speed and $D_\ell\geq0$ is the arclength
diffusivity. Let $r\geq0$ be the symmetric direction-exchange rate and

$$
\kappa(x,t):=\lambda[1-q(E_Y(x,t),E_I(x,t))],
\qquad \lambda\geq0.
\tag{LB5}
$$

The minimal shared-support population law is

$$
\boxed{
\begin{aligned}
\partial_t f_{Y,s}
={}&-(\mathbf u\cdot\nabla)f_{Y,s}
+D_x\nabla^2f_{Y,s}
-s\Omega\partial_\chi f_{Y,s}
+d\partial_\chi^2f_{Y,s}\\
&+r(f_{Y,-s}-f_{Y,s})
-\kappa f_{Y,s}
+\varphi\kappa f_{I,s},\\[2mm]
\partial_t f_{I,s}
={}&-(\mathbf u\cdot\nabla)f_{I,s}
+D_x\nabla^2f_{I,s}
-s\Omega\partial_\chi f_{I,s}
+d\partial_\chi^2f_{I,s}\\
&+r(f_{I,-s}-f_{I,s})
+\kappa f_{Y,s}
-\varphi\kappa f_{I,s}.
\end{aligned}
}
\tag{LB6}
$$

The conversion is direction preserving. The independent $r$ term exchanges
the two orientations while preserving each species total. More general
direction-mixing conversion matrices project to the same canonical law when
their columns sum to one; (LB6) is the smallest explicit member needed here.

### 3.2 Projection theorem

**Theorem 1—Exact loop-zero-mode closure.** Assume:

1. every $f_{a,s}$ is periodic in $\chi$ and regular enough for the displayed
   derivatives and averages;
2. $\mathbf u$ and $D_x$ are shared by all four channels and independent of
   $\chi$;
3. $\Omega$, $d$, and $r$ are independent of $\chi$;
4. the conversion gate $\kappa$ is computed from the projected densities in
   (LB1)–(LB5), so it is common around each loop.

Then the projection (LB1) of every solution of (LB6) obeys

$$
\boxed{
\begin{aligned}
\partial_tE_Y
&=-(\mathbf u\cdot\nabla)E_Y
+D_x\nabla^2E_Y
-\lambda(1-q)\varepsilon,\\
\partial_tE_I
&=-(\mathbf u\cdot\nabla)E_I
+D_x\nabla^2E_I
+\lambda(1-q)\varepsilon.
\end{aligned}
}
\tag{LB7}
$$

These are the canonical Yang/Yin equations.

**Proof.** Periodicity gives

$$
\langle\partial_\chi f_{a,s}\rangle_\chi=0,
\qquad
\langle\partial_\chi^2 f_{a,s}\rangle_\chi=0.
\tag{LB8}
$$

Summing the direction-exchange terms over $s$ gives

$$
\sum_s r\langle f_{a,-s}-f_{a,s}\rangle_\chi=0.
\tag{LB9}
$$

The common exterior operators commute with the finite direction sum and loop
average. The projected Yang conversion term is

$$
\sum_s\langle-\kappa f_{Y,s}
+\varphi\kappa f_{I,s}\rangle_\chi
=-\kappa(E_Y-\varphi E_I)
=-\lambda(1-q)\varepsilon.
\tag{LB10}
$$

The Yin term is its negative. Substitution gives (LB7). $\square$

### 3.3 Conservation, positivity, and fixed composition

Adding the two equations in (LB7) gives

$$
\partial_t\rho
=-(\mathbf u\cdot\nabla)\rho+D_x\nabla^2\rho.
\tag{LB11}
$$

Conversion therefore conserves total density locally. Under a divergence-free
$\mathbf u$ and periodic or no-flux exterior boundary conditions, the spatial
integral of $\rho$ is conserved. For a compressible flow, the conservative
transport form is $-\nabla\cdot(\mathbf uE_a)$, as in the finite carrier
construction.

At fixed $(x,\chi,t)$, the conversion and direction-exchange matrix has
nonnegative off-diagonal entries and zero column sums. Together with periodic
transport and diffusion, this is a positivity-preserving generator under the
standard parabolic regularity assumptions. No clipping or reflection at
$f_{a,s}=0$ is required.

The uniform direction-balanced fixed ray is

$$
f_{Y,+}=f_{Y,-}=\varphi C,
\qquad
f_{I,+}=f_{I,-}=C,
\qquad C\geq0.
\tag{LB12}
$$

Its projection satisfies

$$
\frac{E_Y}{E_I}=\varphi,
\qquad
\varepsilon=0.
\tag{LB13}
$$

### 3.4 Exact closure boundary

The common projected gate in assumption 4 is essential to exact closure. If a
microscopic gate $\kappa(\chi)$ is used, let

$$
Z(\chi):=\sum_s[f_{Y,s}(\chi)-\varphi f_{I,s}(\chi)].
$$

The projected Yang conversion becomes

$$
-\langle\kappa Z\rangle_\chi
=-\langle\kappa\rangle_\chi\,\varepsilon
-\operatorname{Cov}_\chi(\kappa,Z).
\tag{LB14}
$$

The covariance term is an unresolved closure correction. Direction-dependent
exterior velocities or diffusivities similarly leave unresolved projected
fluxes. The canonical PDE is exact for (LB6) because these terms are excluded
by the stated common-coefficient contract.

---

## 4. Coherence-matrix bubble theorem

### 4.1 Species Gram matrix

At fixed $(x,t)$, regard each species amplitude as a vector in

$$
\mathcal K
:=L^2(S^1,d\chi/2\pi)\otimes\mathbb C^2_{\rm dir}.
$$

Its inner product is

$$
\langle u,v\rangle_{\mathcal K}
:=\sum_s\langle u_s^*v_s\rangle_\chi.
$$

Then

$$
E_Y=\|\psi_Y\|_{\mathcal K}^2,
\qquad
E_I=\|\psi_I\|_{\mathcal K}^2,
\qquad
c:=\langle\psi_Y,\psi_I\rangle_{\mathcal K}.
\tag{LB15}
$$

Define the Hermitian species coherence matrix

$$
\Gamma
:=
\begin{pmatrix}
E_Y&c^*\\
c&E_I
\end{pmatrix}.
\tag{LB16}
$$

It is the species Gram matrix after the loop and direction labels have been
traced out. This is an algebraic partial trace; no quantum-state identification
is needed for the result.

### 4.2 Bloch-ball and affine-bubble map

For $\rho>0$, define

$$
\boxed{
\mathbf n(\Gamma)
:=\frac{1}{\rho}
\begin{pmatrix}
2\operatorname{Re}c\\
2\operatorname{Im}c\\
E_Y-E_I
\end{pmatrix}
}
\tag{LB17}
$$

and let

$$
D:=\operatorname{diag}(a_x,a_y,a_z),
\qquad a_x,a_y,a_z>0.
\tag{LB18}

$$

The frozen certificate instantiates this general map with
$D=\operatorname{diag}(3,2,5/4)$ as a declared verifier example. The physical
bubble axes remain open.

The affine bubble point is

$$
\boxed{
\mathbf X(\Gamma):=D\mathbf n(\Gamma).
}
\tag{LB19}
$$

**Theorem 2—Loop coherence maps to the bubble volume.** Every state in
(LB15) satisfies

$$
|c|^2\leq E_YE_I,
\tag{LB20}
$$

$$
\|\mathbf n\|^2
=\frac{(E_Y-E_I)^2+4|c|^2}{\rho^2}
\leq1,
\tag{LB21}
$$

and

$$
\boxed{
\mathbf X^TD^{-2}\mathbf X\leq1.
}
\tag{LB22}
$$

Equality holds exactly when $\psi_Y$ and $\psi_I$ are linearly dependent in
$\mathcal K$, including either vector being zero. The equality set maps to the
quadratic shell. Strict inequality maps to its interior.

**Proof.** Equation (LB20) is Cauchy–Schwarz in $\mathcal K$. Since

$$
(E_Y-E_I)^2+4E_YE_I=(E_Y+E_I)^2=\rho^2,
$$

substitution of (LB20) gives (LB21). Equation (LB22) follows from
$\mathbf X=D\mathbf n$. Equality in Cauchy–Schwarz holds exactly for linearly
dependent vectors. $\square$

### 4.3 Recovery of the projective shell map

On the equality set with $E_YE_I>0$, write

$$
\psi_I
=e^{i\delta}\sqrt{\frac{E_I}{E_Y}}\,\psi_Y.
\tag{LB23}
$$

Then

$$
c=\sqrt{E_YE_I}\,e^{i\delta},
\tag{LB24}
$$

and (LB17) becomes

$$
\mathbf n
=
\begin{pmatrix}
2\sqrt{E_YE_I}\cos\delta/\rho\\
2\sqrt{E_YE_I}\sin\delta/\rho\\
(E_Y-E_I)/\rho
\end{pmatrix}.
\tag{LB25}
$$

The endpoint cases $E_YE_I=0$ are the two poles of the shell and follow
directly from (LB17).

This is the normalized complex Yang/Yin map in
`foundations/string-bubble-projective-map.md`. The pure projective sphere is
the rank-one boundary of the loop-derived coherence ball.

Define the normalized coherence

$$
\eta_c
:=\frac{|c|}{\sqrt{E_YE_I}}
\in[0,1]
\tag{LB26}
$$

when $E_YE_I>0$. At fixed composition
$s_\rho=(E_Y-E_I)/\rho$, the transverse radius is

$$
\sqrt{n_x^2+n_y^2}
=\eta_c\sqrt{1-s_\rho^2}.
\tag{LB27}
$$

Thus $\eta_c$ is the shell-visibility coordinate: $\eta_c=1$ reaches the
shell, while phase decorrelation contracts the point toward the bubble axis.

### 4.4 Canonical Qi and phase coherence are independent observables

The canonical $q$ in (LB3) depends on $E_Y$, $E_I$, and $\rho$. It contains no
$c$. At the conversion attractor,

$$
\frac{E_Y}{E_I}=\varphi,
\qquad
n_z=\frac{E_Y-E_I}{\rho}=\varphi^{-3},
\tag{LB28}
$$

while every value $0\leq\eta_c\leq1$ remains possible. Density equilibrium
fixes the attractor latitude. The phase-sensitive moment fixes the transverse
radius and longitude. A density-only Qi diagnostic cannot distinguish a
coherent shell state from a dephased interior state at the same composition.

### 4.5 Projection non-injectivity

For any fixed populations, changing the relative phase

$$
\theta_{I,s}(\chi)-\theta_{Y,s}(\chi)
$$

leaves $(E_Y,E_I)$ unchanged and generally changes $c$. A common local phase
multiplying both species in the same $(s,\chi)$ channel cancels from (LB15).
Independent relative phases remain observable through $c$.

The density projection (LB1) therefore has a large fibre. The coherence map
(LB15) retains one complex second moment of that fibre and still discards
higher loop correlations and cross-direction coherence.

---

## 5. Alternating phase layers

Suppose a coarse observation combines $K$ contributions with common
composition and coherence magnitude. Let their normalized weights satisfy
$w_j\geq0$ and $\sum_jw_j=1$, and let their relative phases be $\delta_j$.
Their transverse coherence is multiplied by

$$
\zeta_K
:=\sum_{j=0}^{K-1}w_j e^{i\delta_j}.
\tag{LB29}
$$

For equal weights and alternating average phase,

$$
\delta_j=\delta_0+j\pi,
\qquad
w_j=\frac1K,
\tag{LB30}
$$

so

$$
\boxed{
\zeta_{2N}=0,
\qquad
|\zeta_{2N+1}|=\frac{1}{2N+1}.
}
\tag{LB31}
$$

Even layer pairs cancel the transverse bubble coordinate exactly. An odd
unpaired layer leaves a residual that falls as $1/K$. Unequal opposite-phase
weights $w_+$ and $w_-$ leave the normalized residual
$|w_+-w_-|/(w_++w_-)$. This is a precise mechanism by which layer averaging
can sharpen a coherence-visibility transition.

Equation (LB31) is a projection effect. It supplies neither the radial layer
spacing nor the physical law that produces the alternating phases.

---

## 6. Internal population spectrum and gap

### 6.1 Frozen Fourier generator

Freeze $(x,t)$, suppress exterior derivatives, and treat
$\kappa=\lambda(1-q)$ as constant. Expand each population in loop Fourier
modes $e^{im\chi}$, $m\in\mathbb Z$.

In species order $(Y,I)$, conversion has matrix

$$
C
:=\kappa
\begin{pmatrix}
-1&\varphi\\
1&-\varphi
\end{pmatrix},
\qquad
\operatorname{spec}C
=\{0,-\kappa(1+\varphi)\}.
\tag{LB32}
$$

In direction order $(+,-)$, the $m$th transport-exchange block is

$$
B_m
:=
\begin{pmatrix}
-r-im\Omega&r\\
r&-r+im\Omega
\end{pmatrix},
\tag{LB33}
$$

with

$$
\operatorname{spec}B_m
=
\left\{-r\pm\sqrt{r^2-m^2\Omega^2}\right\}.
\tag{LB34}
$$

Because conversion is direction preserving, the four-channel generator is
the Kronecker sum

$$
A_m
=C\otimes I_2+I_2\otimes B_m-dm^2I_4.
\tag{LB35}
$$

### 6.2 Exact spectrum

The Kronecker-sum spectrum is

$$
\boxed{
\Lambda_{m,c,\pm}
=-dm^2+c-r\pm\sqrt{r^2-m^2\Omega^2},
\qquad
c\in\{0,-\kappa(1+\varphi)\}.
}
\tag{LB36}
$$

The principal square root is used. For $m=0$,

$$
\operatorname{spec}A_0
=
\left\{
0,
-2r,
-\kappa(1+\varphi),
-2r-\kappa(1+\varphi)
\right\}.
\tag{LB37}
$$

The zero eigenvector is the uniform fixed ray (LB12). The other three
uniform modes are direction imbalance, species imbalance, and their combined
mode.

### 6.3 Real spectral gap

For nonzero integer $m$, the slow direction branch has decay rate

$$
g_m
:=dm^2+r-\operatorname{Re}
\sqrt{r^2-m^2\Omega^2}.
\tag{LB38}
$$

This is nondecreasing with $|m|\geq1$: below the turning point, both the
$dm^2$ term and
$r-\sqrt{r^2-m^2\Omega^2}$ increase; above it, the square root is imaginary
and the real part vanishes. The first loop harmonic is therefore the slowest
nonuniform mode.

After excluding the one conserved total-density mode, the frozen internal real
spectral gap is

$$
\boxed{
g_{\rm int}
=
\min\left\{
\kappa(1+\varphi),
2r,
d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}
\right\}.
}
\tag{LB39}
$$

A positive gap requires all three entries to be positive. The following
boundaries close it:

- $\kappa=0$: the species-composition mode is conserved;
- $r=0$: the uniform direction imbalance is conserved;
- $d=0$ and $\Omega=0$: loop-nonuniform direction-symmetric modes are
  conserved.

For pure ballistic circulation, $d=r=0$, the nonzero loop modes have imaginary
frequencies $\pm m\Omega$ and zero real decay. Loop closure discretizes their
integer $m$ labels while leaving the real gap zero.

### 6.4 Total loop current

Let

$$
F_s:=f_{Y,s}+f_{I,s},
\qquad
F:=F_++F_-,
\qquad
H:=F_+-F_-.
\tag{LB40}
$$

The conversion terms cancel, and the internal equations become

$$
\partial_tF
=-\Omega\partial_\chi H+d\partial_\chi^2F,
\tag{LB41}
$$

$$
\partial_tH
=-\Omega\partial_\chi F+d\partial_\chi^2H-2rH.
\tag{LB42}
$$

For a circular loop, the physical oriented current is

$$
j_\ell:=vH,
\tag{LB43}
$$

and (LB41) is the loop continuity equation

$$
\partial_tF+\frac1R\partial_\chi j_\ell
=d\partial_\chi^2F.
\tag{LB44}
$$

The complete loop average obeys

$$
\frac{d}{dt}\langle H\rangle_\chi
=-2r\langle H\rangle_\chi
\tag{LB45}
$$

when exterior terms are suppressed. Passive direction exchange balances the
net orientation by damping it. With $r=0$, persistent countercirculation is
possible and the uniform direction mode remains ungapped. A persistent
nonzero current together with a positive relaxation gap requires a declared
drive or another nonequilibrium source.

This current is absent from the density pair (LB1). An identification of Qi
flow with $j_\ell$, a species-resolved counterpart, or the phase coherence
$c$ requires an additional observable map.

---

## 7. Strand-to-bubble scale separation

### 7.1 Exact kinematic scale switch

The loop average is an exact Fourier projector:

$$
P_0\left[\sum_{m\in\mathbb Z}f_m e^{im\chi}\right]=f_0.
\tag{LB46}
$$

A strand-resolving description retains $m\neq0$, direction, phase, and
coherence data. The bubble density description retains the two species zero
modes. This gives a precise microscopic-to-mesoscopic change of state space.

### 7.2 Dynamical validity of the reduced description

Let $T_B$ be the shortest bubble-scale evolution time relevant to an
observation. When

$$
\boxed{
g_{\rm int}T_B\gg1,}
\tag{LB47}
$$

unforced internal population modes relax before the projected fields change
appreciably. The zero-mode PDE is then dynamically autonomous after the
internal transient as well as algebraically closed by construction. For a
physically embedded loop, local homogenization also requires its size to be
small compared with the exterior variation length, conventionally
$R/L_B\ll1$.

### 7.3 Scale-ratio boundary

Equations (LB4) and (LB39) depend on the supplied quantities
$(R,v,D_\ell,r,\lambda,q)$. Topological loop closure fixes
$m\in\mathbb Z$, while $R$, $L_B$, and their ratio remain supplied scales.
The golden ratio controls the species equilibrium and conversion eigenvalue;
the geometric relation between loop and bubble sizes remains independent.

The theorem therefore derives a rate-controlled coarse-graining criterion and
an exact phase-cancellation mechanism. A universal $\varphi$-spaced
strand-to-bubble scale jump requires a separate measured or derived relation
among $R$, $L_B$, and the cascade dynamics.

---

## 8. Fivefold orbit and pentagram visibility

At the attractor composition, let

$$
s_\varphi:=\varphi^{-3},
\qquad
r_\varphi:=\sqrt{1-\varphi^{-6}},
\qquad
\delta_j:=\delta_0+\frac{2\pi j}{5}.
\tag{LB48}
$$

For normalized coherence $\eta_c$, the five projected points are

$$
\boxed{
\mathbf X_j(\eta_c)
=D
\begin{pmatrix}
\eta_c r_\varphi\cos\delta_j\\
\eta_c r_\varphi\sin\delta_j\\
s_\varphi
\end{pmatrix}.
}
\tag{LB49}
$$

At $\eta_c=1$, these are the shell pentagon and step-two pentagram of
`foundations/string-bubble-projective-map.md`. At
$0<\eta_c<1$, they are similar fivefold figures in an interior latitude
plane. Every transverse chord is multiplied by $\eta_c$. In normalized
coordinates, equivalently in the affine bubble's pullback metric $D^{-2}$,

$$
\frac{L_{\rm step\,2}^{\rm norm}}{L_{\rm step\,1}^{\rm norm}}=\varphi.
\tag{LB50}
$$

The ordinary Euclidean ratio after applying an anisotropic $D$ depends on
the orbit angle. At $\eta_c=0$, all five transverse points coincide on the
bubble axis and the fivefold visibility vanishes.

The fivefold selector remains the supplied conditional $w=5$ subgroup. The
loop projection preserves and attenuates that supplied orbit. Selection of
$w=5$ requires separate dynamics. A rotating pentagon additionally requires a
phase law for $\delta_0(t)$. The population circulation rate $\Omega$ becomes
that projective longitude rate only after an explicit phase-to-geometry
identification.

---

## 9. Quantum consequences and limits

### 9.1 Mathematics supplied by the loop theorem

The construction supplies the following finite-resolution ingredients:

1. complex phase-bearing carrier coordinates on a closed internal fibre;
2. an exact many-to-one projection to two real canonical densities;
3. a positive species coherence matrix obtained by tracing out loop and
   direction labels;
4. a Bloch-ball geometry whose rank-one boundary is the existing projective
   bubble shell;
5. integer loop Fourier sectors and an explicit population spectrum;
6. a concrete example in which equal densities carry distinct phase-sensitive
   coherence and bubble coordinates.

These results sharpen the carrier-to-density part of
`foundations/quantum-measurement-derivation.md` §8.4 by resolving each carrier
population on a shared loop and by retaining the cross-species coherence
moment $c$.

### 9.2 Quantum premises that remain independent

The amplitude notation in §2 is kinematic. Equation (LB6) specifies a positive
population law. A linear unitary amplitude equation, a coefficient with units
of action, and symplectic or commutator normalization remain absent.
Consequently, the following inputs remain open:

- the map from the QF1 regulated complex configuration to
  $\psi_{a,s}(x,\chi)$;
- a phase evolution law and its coupling to the population generator;
- the Fisher coefficient $\hbar^2/8$ and Schrödinger dynamics;
- a guidance-current selection law;
- quantum-equilibrium preparation and Born frequencies;
- tensor-product, spin, fermion, gauge, particle, and apparatus record maps;
- an interacting regulator-removal limit.

Periodic scalar amplitudes give integer winding. Half-integer spin requires a
spinor bundle or antiperiodic lift outside (LB6). Likewise, the Gram matrix has
the algebraic form of a reduced two-level density matrix. A physical quantum
density-operator interpretation additionally requires the QF1 state
identification and an observable algebra.

### 9.3 Relation to the existing projection gate

The finite carrier-reservoir theorem already derives the canonical density
law from density-dependent Markov jumps. Equations (LB1)–(LB10) provide a
loop-resolved realization of that carrier law. The physical map between the
QF1 complex field and carrier occupations remains Open, so the DQ and GQ
promotion verdicts in `foundations/quantum-measurement-derivation.md` remain
unchanged.

The new result advances the projective research direction by proving that a
phase-bearing carrier ensemble maps naturally to the full affine bubble
volume. The discarded phase fibre remains independent data beyond the
canonical density dynamics.

---

## 10. Physical tests and rejection conditions

The conditional microphysics separates into independently testable contracts:

1. **Shared support.** Direction-resolved carriers occupy one closed support.
   A requirement for permanently separated centre-lines rejects the minimal
   state in §2.
2. **Common projected gate.** Conversion rates depend on the projected
   $q(E_Y,E_I)$ and remain common around one loop. A reproducible covariance
   term in (LB14) rejects exact canonical closure.
3. **Common exterior transport.** The four channels share exterior velocity
   and diffusivity. Resolved channel-dependent fluxes require additional
   projected variables.
4. **Passive internal spectrum.** Undriven perturbations follow (LB36).
   Persistent modes with decay rates inconsistent with every common
   $(d,\Omega,r,\kappa)$ reject (LB6).
5. **Coherence-sensitive geometry.** A physical bubble longitude and
   transverse radius require an observable proportional to $c$. Phase changes
   with fixed $(E_Y,E_I)$ that leave every candidate bubble observable
   unchanged reject the physical use of (LB19).
6. **Alternating-layer cancellation.** Equal opposite-phase contributions
   obey (LB31). A measured residual outside the independently calibrated
   weight and phase errors rejects that layer model.
7. **Scale law.** A claimed universal spatial jump must supply an independent
   relation for $R/L_B$. The projection theorem leaves that scale ratio
   unspecified.

These are rejection conditions for the stated loop model. A failure rejects
this realization while leaving the projected target available to other
microscopic completions.

---

## 11. Result ledger

| Result | Status | Boundary |
|---|---|---|
| Complete-loop zero-mode projection gives the canonical PDE | **Derived conditional** | Common projected gate and common exterior transport |
| Population positivity and local conversion conservation | **Derived conditional** | Nonnegative rates and standard transport boundary conditions |
| $E_Y/E_I=\varphi$ uniform fixed composition | **Derived conditional** | Frozen conversion ratio in (LB6) |
| Species coherence matrix maps to affine bubble volume | **Derived** algebraically | Phase-bearing amplitudes in $\mathcal K$ |
| Rank-one coherence maps to the projective shell | **Derived** algebraically | Linearly dependent Yang/Yin loop vectors |
| Alternating equal $\pi$-phase layers cancel in even pairs | **Derived** algebraically | Common composition and equal weights |
| Internal population spectrum and gap (LB36)–(LB39) | **Derived conditional** | Frozen linear coefficients in (LB6) |
| Persistent passive circulation with positive internal gap | **Excluded** by (LB39) and (LB45) | A drive or additional nonequilibrium term is required |
| Universal strand-to-bubble spatial ratio | **Open** | Geometry or dynamics fixing $R/L_B$ is absent |
| Physical loop-carrier and phase identification | **Hypothesized** | Direct carrier, phase, current, and closure tests |
| Quantum dynamics and statistics from the loop state | **Open** | QF1–QF4 and the remaining DQ/GQ artifacts |

---

## 12. Verification

The frozen protocol is
`computations/loop-to-bubble-projection-pre-registration.md`. The independent
certificate is
`computations/verify_loop_to_bubble_projection.py`. It checks:

- exact finite-grid projection to the canonical PDE;
- conservation, positivity-generator, and fixed-composition identities;
- Gram-matrix positivity and affine bubble inequalities;
- alternating-phase cancellation;
- the complete frozen Fourier spectrum and real gap;
- density-projection non-injectivity;
- fivefold visibility scaling and the retained $\varphi$ chord ratio.

---

## References

- `foundations/cassi-first-principles.md`—canonical densities, $q$, and
  rank-one conversion
- `foundations/quantum-measurement-derivation.md` §8.4—finite carrier
  reservoir and carrier-to-density limit
- `foundations/qi-flow-double-helix.md`—direction-resolved diagnostics,
  four-channel nonuniqueness, and passive-rotation limit
- `foundations/string-bubble-projective-map.md`—pure projective shell,
  affine orbit, and conditional fivefold map
- `foundations/bubble-edge-geometry.md`—quadratic bubble axes and boundary
- `computations/loop-to-bubble-projection-pre-registration.md`—frozen gates
- `computations/verify_loop_to_bubble_projection.py`—independent certificate
