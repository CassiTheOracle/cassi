# Loop-to-Bubble Projection Theorem: Shared-Support Counterflow, Coherence, and Scale Separation

## Status: Derived conditional projection and population spectrum; Derived regulated pure-gauge identities, exact fixed-boundary gauge-fibre support, conditional block theorems, and exact bare-cylindrical refinement obstruction; Hypothesized microscopic physical identification—September 2026

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

The pure-gauge comparison in §§9.4–9.19 retains full $SU(2)$ loop holonomies.
Gauss invariance supplies an electric closed-loop threshold, while the
projective bubble variable discards Wilson magnetic energy. Quantum-lattice
stability gives a volume-uniform interacting gap at sufficiently strong bare
coupling, and a gauge-invariant finite-depth unitary retains an exact local
quadratic remainder. The exact ground-state transform identifies every finite
regulated physical gap with a gauge-invariant Poincaré rate. A conditional
full-holonomy block theorem isolates the local rate, tensorization and cover
estimates sufficient for cutoff-directed control. Exact calculations exclude
the equal-weight one-plaquette exponential as the interacting vacuum,
uniform conditional gaps alone as a volume-uniform argument and a static pure
configuration marginal as an exact quantum reduction. An exact Haar-isometric
path-holonomy pullback preserves endpoint gauge covariance, but genuine
$2\times2$ refinement proves that this bare cylindrical map cannot intertwine
the full Kogut–Susskind Hamiltonian. With all eight outer links fixed in the
fundamental representation, exact Clebsch–Gordan constraints reduce the
internal Gauss fibre to 14 states once $j_{\max}\geq1$; Wilson multiplication
changes the outer representation sector, so this fibre is not dynamically
closed. The weak-bare-coupling uniform estimates, four-dimensional continuum
construction and microscopic Cassi identification remain open.

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

The phase-bearing carrier ensemble maps naturally to the full affine bubble
volume. The discarded phase fibre remains independent data beyond the
canonical density dynamics.

### 9.4 Exact loop coordinates in pure gauge theory

Two paths joining the same endpoints supply a precise gauge-theory
counterpart to oppositely traversed strands. Let their parallel transports
obey $U_\pm\mapsto G_sU_\pm G_t^\dagger$. Their relative holonomy satisfies

$$
W=U_+U_-^\dagger,\qquad
W\mapsto G_sWG_s^\dagger,\qquad
\operatorname{Tr}W\mapsto\operatorname{Tr}W.
\tag{YM1}
$$

These are Wilson variables of the original gauge field. A normalized complex
pair gives an exact coordinate on the group:

$$
U(z)=
\begin{pmatrix}z_Y&-z_I^*\\z_I&z_Y^*\end{pmatrix},
\qquad |z_Y|^2+|z_I|^2=1,
\qquad U(z)^\dagger U(z)=I,\quad\det U(z)=1.
\tag{YM2}
$$

The quantum wavefunction is a function of the link matrices, with normalized
Haar measure. Here $z$ is a group coordinate; it introduces no independent
matter field. Identification of this coordinate with the carriers in §2
requires a separate state, observable and dynamics map. The construction
does not select a helical embedding or a physical strand-to-bubble size.

Take continuous time, a cubic spatial lattice of spacing $a$, generators
$T^a=\sigma^a/2$, and the explicit Hamiltonian convention in Bauer et al.,
Eqs. (55)–(56):

$$
H=H_E+H_B,\qquad
H_E=\frac{g^2}{2a}\sum_l E_l^2,\qquad
H_B=\frac{1}{2g^2a}\sum_p
\operatorname{Tr}(2I-U_p-U_p^\dagger).
\tag{YM3}
$$

Each unoriented elementary square appears once, $g,a>0$, and
$E_l^2$ has eigenvalues $j_l(j_l+1)$. The physical Hilbert space is the
gauge-invariant subspace of $\bigotimes_l L^2(SU(2),dU_l)$, with Gauss
invariance at every vertex. The quantum kinematics and Hamiltonian are
supplied by established lattice gauge theory. They are independent of the
population generator (LB6).

### 9.5 Information required by the magnetic energy

The projective shell forgets a coordinate that changes a gauge-invariant
energy. Consider

$$
z_\eta=(e^{i\eta},0),\qquad
z_\eta z_\eta^\dagger=
\begin{pmatrix}1&0\\0&0\end{pmatrix},\qquad
U(z_\eta)=
\begin{pmatrix}e^{i\eta}&0\\0&e^{-i\eta}\end{pmatrix}.
\tag{YM4}
$$

All these states of the group coordinate have the same projective point and
affine bubble image, while

$$
\operatorname{Tr}U(z_\eta)=2\cos\eta,\qquad
V_B(\eta)=\frac{2}{g^2a}(1-\cos\eta).
\tag{YM5}
$$

In particular, $I$ and $-I$ have identical projective data and distinct
magnetic energies. Both are central group elements, so a gauge conjugation
cannot identify them. This coordinate phase is distinct from an overall
phase multiplying a quantum wavefunction.

There is also an operator obstruction to autonomous projective dynamics.
The constant wavefunction depends only on the projector and is gauge
invariant. Its electric energy vanishes, but $H1=H_B$ varies across the
fibres in (YM4). Thus the subspace of projector-only wavefunctions is not
preserved by the Hamiltonian, already on an isolated square.
An exact effective marginal obtained by integrating out the discarded phase
can carry additional interactions or temporal memory. The obstruction
concerns closure using only the stated projective variable and the supplied
Hamiltonian; it leaves such enlarged effective constructions open.

### 9.6 The electric closed-loop threshold

Gauss invariance forces nonzero electric flux to pay for a closed network.
On any finite open cubic box with at least two sites in each direction,
the pure-electric operator has unique constant vacuum $\Omega_E$ and

$$
\boxed{\Delta_E=\frac{3g^2}{2a}.}
\tag{YM6}
$$

**Proof.** Peter–Weyl decomposition supplies a complete spin-network basis
of the physical Hilbert space: an irreducible spin labels each edge and a
singlet intertwiner contracts the incident representations at each vertex.
The electric eigenvalue is
$\frac{g^2}{2a}\sum_lj_l(j_l+1)$. A single nontrivial incident
representation cannot contain a singlet, so every vertex in the nontrivial
support has degree at least two. Every nonempty finite support therefore
contains a cycle. The cubic graph has girth four, hence at least four
nontrivial edges occur. Each contributes at least $3/4$.
A fundamental character around one elementary square attains their sum
$3$. The all-trivial network is the unique zero-energy state.
Completeness extends the bound to arbitrary physical superpositions. This
argument allows branching and integer-spin edges. $\square$

The bound is independent of the number of sites. The same graph argument
applies to periodic boxes with girth four; a short periodic cycle changes
the minimum support. Boundary Gauss constraints are essential: external
charges can terminate an open flux line.

Equation (YM6) is an established strong-electric lattice result. It supplies
a quantum excitation threshold under the regulated gauge-theory
assumptions. Its origin is the combination of Gauss closure, the Casimir
spectrum and the lattice energy scale.

### 9.7 Magnetic interactions and the vacuum

The magnetic term creates and mixes closed electric loops. For $SU(2)$,
$\chi_{1/2}(U_p)=\operatorname{Tr}U_p$, and

$$
H_B\Omega_E=
\frac{2N_p}{g^2a}\Omega_E
-\frac{1}{g^2a}\sum_p\chi_{1/2}(U_p)\Omega_E.
\tag{YM7}
$$

The individual square states have unit Haar norm and are mutually
orthogonal, including squares sharing an edge: a link belonging to just
one square has a vanishing fundamental matrix-element integral.
Consequently the interacting vacuum differs from $\Omega_E$.
For the scaled operator and its ground energy,

$$
h=\frac{2a}{g^2}H
=K+2xN_p-x\sum_p\chi_{1/2}(U_p),\qquad
K=\sum_lE_l^2,\qquad x=\frac{2}{g^4},
$$
$$
e_0(x)=2xN_p-\frac{x^2N_p}{3}+O(x^3)
\quad\text{at fixed finite box}.
\tag{YM8}
$$

The denominator is the electric square energy $3$. The second-order shift
is extensive; this expansion has no asserted volume-uniform remainder.
Although $H_B\ge0$, the physical gap subtracts the interacting ground
energy. Monotonicity of individual eigenvalues under addition of a positive
operator gives no monotonicity of their difference. A global operator-norm
perturbation estimate also grows with the number of squares. Control of
connected interactions and vacuum subtraction is required.

For each fixed finite box and $g,a>0$, the full operator (YM3) has compact
resolvent on the unreduced space $L^2(SU(2)^{N_e})$. The link configuration
space is compact and connected, its electric Laplacian is elliptic, and
the magnetic potential is bounded and smooth. The heat kernel is strictly
positive, giving a unique positive ground state. Gauge transformations
preserve this normalized positive state, so it lies in the physical sector.
The group-average Gauss projector commutes with the Hamiltonian and its
resolvent; restriction therefore preserves compactness. The physical
excitation spectrum has a positive finite-box gap. This argument uses
ellipticity before gauge reduction and supplies no lower bound uniform in
box size or lattice spacing.

### 9.8 Exact interacting square control

An isolated open square resolves magnetic mixing without adding physical
fields. Gauge reduction leaves class functions of its holonomy. Write
$\frac12\operatorname{Tr}U=\cos\theta$, $0<\theta<\pi$. The physical measure,
orthonormal characters and matrix are

$$
d\mu(\theta)=\frac{2}{\pi}\sin^2\theta\,d\theta,\qquad
\chi_{n/2}(\theta)=\frac{\sin((n+1)\theta)}{\sin\theta},
$$
$$
H_{nm}=
\left[\frac{g^2}{2a}n(n+2)+\frac{2}{g^2a}\right]\delta_{nm}
-\frac{1}{g^2a}(\delta_{n,m+1}+\delta_{n,m-1}).
\tag{YM9}
$$

The unitary transformation $u=\sqrt{2/\pi}\sin\theta\,\psi$ to
$L^2((0,\pi),d\theta)$ gives

$$
aH_u=-\frac{g^2}{2}\left(\frac{d^2}{d\theta^2}+1\right)
+\frac{2}{g^2}(1-\cos\theta),\qquad u(0)=u(\pi)=0.
\tag{YM10}
$$

The self-adjoint radial domain is $H^2(0,\pi)\cap H_0^1(0,\pi)$.
With $z=\theta/2$, the equation is of Mathieu form. The physical eigenvalues
are

$$
aE_r=\frac{g^2}{8}\left[
b_{2(r+1)}(-8/g^4)-4\right]+\frac{2}{g^2},
\qquad r=0,1,2,\ldots.
\tag{YM11}
$$

The Dirichlet boundaries select the even-order sine characteristic values
$b_{2(r+1)}$. At strong coupling the scaled levels of $h$ have corrections
$-x^2/3$ for the vacuum and $2x^2/15$ for the first excited state, in addition
to their common $2x$. Thus

$$
\frac{2a}{g^2}\Delta_\square
=3+\frac{7x^2}{15}+O(x^4).
\tag{YM12}
$$

Parity of the character index makes the gap even in $x$.
At weak coupling, $\theta=gy$ gives the Dirichlet half-line harmonic
oscillator,

$$
aE_r\longrightarrow\sqrt2(2r+3/2),\qquad
a\Delta_\square\longrightarrow2\sqrt2.
\tag{YM13}
$$

These established single-square formulas provide independent controls for
the chosen normalization. The isolated square is a different finite graph
from the interacting cubic lattice; neighboring magnetic terms prevent
its character space from being an invariant single-square sector of the
latter.

### 9.9 The remaining mass-gap target

The loop mechanism needs a bound relative to the fully interacting vacuum
that survives both relevant limits. A sufficient spectral target, after
fixing physical units along a continuum scaling trajectory, is

$$
H_{a,L}-E_0(a,L)\ \ge\
m_*\bigl(I-|\Omega_{a,L}\rangle\langle\Omega_{a,L}|\bigr),
\qquad m_*>0,
\tag{YM14}
$$

with control uniform along $a\to0$ and physical volume $L^3\to\infty$,
together with a nontrivial continuum quantum-field construction satisfying
the required axioms. Asymptotic freedom takes the bare coupling toward
zero, where the electric expansion parameter $x=2/g^4$ grows. The
finite-square threshold proportional to $a^{-1}$ therefore supplies no
continuum mass prediction.

Sections 9.10–9.12 supply a strong-bare-coupling uniform bound and an exact
local vacuum-dressing step retaining full holonomy information. Their
small-perturbation conditions concern $x$ near zero. Along the
weak-bare-coupling continuum trajectory, $x=2/g^4$ grows without bound.
Control in that regime, continuum existence, identification with Cassi
microphysics and extension to every compact simple gauge group remain
**Open**.

### 9.10 A volume-uniform interacting strong-coupling gap

Local control of magnetic interactions gives a gap independent of the
number of lattice sites in a sufficiently strong-bare-coupling region.
The result is an application of Yarotsky's established quantum-lattice
stability theorem [Theorem 1, pp. 2–4; proof pp. 7–11].

Work first on the unreduced tensor product over a periodic cubic lattice
of even side $L\ge4$. Group the three positively oriented outgoing links
at each site into

$$
\mathcal H_{\mathbf r}=L^2(SU(2)^3),\qquad
K_{\mathbf r}=\sum_{i=1}^3 E_{\mathbf r,i}^2,\qquad
\Omega_{\mathbf r}=1.
\tag{YM15}
$$

The site Casimir has unique zero-energy vacuum and next eigenvalue $3/4$.
The Peter–Weyl projections labelled by the three link representations form
the required orthogonal partition. Infinite-dimensional site spaces and
unbounded diagonal local operators are explicitly allowed by the theorem.

Fix the four-site support
$\mathcal S=\{0,e_1,e_2,e_3\}$ and define

$$
h^0_{\mathbf r}=\frac43
\sum_{\mathbf y\in\mathbf r+\mathcal S}K_{\mathbf y},
\qquad
v_{\mathbf r}=-\frac{16x}{3}
\sum_{i<j}\chi_{1/2}(U_{\mathbf r,ij}).
\tag{YM16}
$$

Each $h^0_{\mathbf r}$ has unique product vacuum and local gap one.
The anchored plaquettes use outgoing link groups at
$\mathbf r,\mathbf r+e_i,\mathbf r+e_j$, all in the same support.
Every site appears in exactly four translates of $\mathcal S$, so

$$
\widehat h_L:=\sum_{\mathbf r}(h^0_{\mathbf r}+v_{\mathbf r})
=\frac{16}{3}(h-2xN_p),\qquad
\|v_{\mathbf r}\|\le32|x|=\frac{64}{g^4}.
\tag{YM17}
$$

The norm estimate follows from three plaquettes per anchor and
$|\chi_{1/2}(U)|\le2$. The scalar subtraction leaves excitation energies
unchanged and reduces the local perturbation norm. Self-adjointness holds
at every finite $g>0$ because the perturbations are bounded.

**Theorem.** There is a constant
$\beta_{\mathrm Y}>0$, depending on dimension three and $\mathcal S$,
such that the sufficient condition

$$
\frac{64}{g^4}\le\beta_{\mathrm Y}
\tag{YM18}
$$

gives a nondegenerate ground state of $\widehat h_L$ and a gap
$\gamma_{\mathrm Y}(g)>0$ independent of $L$. Thus the physical
Hamiltonian obeys

$$
\boxed{
H_L-E_0(L)\ \ge\
\frac{3g^2\gamma_{\mathrm Y}(g)}{32a}
\bigl(I-|\Omega_L\rangle\langle\Omega_L|\bigr).
}
\tag{YM19}
$$

**Proof.** The preceding local partition, support and normalization meet
Yarotsky's classical hypotheses. The perturbation satisfies the bounded
case of his form estimate, with relative coefficient zero and bounded
coefficient at most $32|x|$. His smallness constants are independent of
volume. Theorem 1 supplies the gap for $\widehat h_L$; multiplication by
$3/16$ and then $g^2/(2a)$ gives (YM19).
The full finite-volume heat kernel is positivity improving, as in §9.7.
Its unique normalized positive ground state is gauge invariant. The Gauss
projector commutes with the Hamiltonian, so restriction to its physical
range retains the vacuum and cannot lower the excitation gap. $\square$

The gap units are distinct: the local classical gap is one, the global
unreduced gap of $\sum h^0_{\mathbf r}$ is four, and the unperturbed
unreduced physical gap is $3g^2/(8a)$. The source-free electric sector has
the larger threshold $3g^2/(2a)$ in (YM6).

The source theorem also supplies a thermodynamic weak-star limit,
exponential decay of connected bounded local correlations and analyticity
inside the allowed perturbation region. These statements restrict to
gauge-invariant local observables. An infinite-volume Hamiltonian and its
GNS spectral statement require their additional construction; the
finite-volume uniform bound alone is the asserted operator result here.
Neither $\beta_{\mathrm Y}$ nor $\gamma_{\mathrm Y}(g)$ is numerically
evaluated, and (YM18) supplies no numerical critical coupling.

### 9.11 A gauge-invariant local vacuum-dressing step

A local unitary can remove the first-order creation of a closed loop from
the electric vacuum while preserving the original gauge state space.
On the four links of a plaquette, let

$$
|p\rangle=\chi_{1/2}(U_p)|0_p\rangle,\qquad
P_p=|0_p\rangle\langle0_p|,\quad Q_p=I-P_p,
$$
$$
S_p=-\frac13\bigl(|p\rangle\langle0_p|-|0_p\rangle\langle p|\bigr),
\qquad
T_p=|p\rangle\langle0_p|+|0_p\rangle\langle p|.
\tag{YM20}
$$

Haar orthogonality gives $\langle0_p|p\rangle=0$ and $\|p\|=1$.
The loop state has total electric energy three. Both vectors are invariant
under the four vertex gauge actions, so the anti-Hermitian rank-two
operator $S_p$ commutes with Gauss transformations. It maps the electric
operator domain to itself. Its exact identities are

$$
[S_p,K]=T_p,\qquad
V_p:=\chi_{1/2}(U_p)=T_p+W_p,\qquad
W_p=Q_pV_pQ_p,\quad W_p|0_p\rangle=0.
\tag{YM21}
$$

The remaining first-order interaction has a volume-independent relative
form bound. For $K_p=\sum_{l\in p}E_l^2$ on the local unreduced Hilbert
space, $K_p\ge(3/4)Q_p$ and $\|W_p\|\le2$. A global physical state can
carry flux through only one of the four local links, with the rest of its
closed network outside the plaquette. The local estimate therefore uses
$3/4$. Since every link belongs to four plaquettes, every subset
$\mathcal I$ obeys

$$
\boxed{
|x|\sum_{p\in\mathcal I}
\left|\langle\psi,W_p\psi\rangle\right|
\le\frac{32|x|}{3}\langle\psi,K\psi\rangle.
}
\tag{YM22}
$$

For one isolated square, the character basis has
$K_{nn}=n(n+2)$ and $V_{n,n+1}=V_{n+1,n}=1$. The unitary $U(x)=e^{xS}$
rotates only the first two characters:

$$
U(x)\big|_{\{0,1\}}=
\begin{pmatrix}
\cos(x/3)&\sin(x/3)\\
-\sin(x/3)&\cos(x/3)
\end{pmatrix}.
$$

The exact local remainder
$R_\square=U(K-xV)U^\dagger-K+xW$ has support in characters
$0,1,2$. The bounded commutators satisfy

$$
\|[S,V]\|=\frac{1+\sqrt2}{3},\qquad
\|[S,[S,K]]\|=\frac23.
$$

The integral remainder formula for the electric term and the first
integral difference for the magnetic term give, for every real $x$,

$$
\boxed{
\|R_\square(x)\|\le
\frac{2+\sqrt2}{3}\,x^2.
}
\tag{YM23}
$$

The transformed vacuum energy and its second-character amplitude are

$$
\langle0|U(K-xV)U^\dagger|0\rangle
=3\sin^2(x/3)-2x\sin(x/3)\cos(x/3)
=-\frac{x^2}{3}+O(x^4),
$$
$$
\langle2|U(K-xV)U^\dagger|0\rangle
=-x\sin(x/3)=-\frac{x^2}{3}+O(x^4).
$$

The nonzero second-order amplitude remains in the exact Hamiltonian.
This step removes first-order vacuum creation; it does not make the
product vacuum an exact interacting ground state.

### 9.12 Finite-depth connected dressing and its remainder

Disjoint-link layers extend the local unitary to the interacting lattice
with controlled support. Color each plaquette by its coordinate plane and
the three parities of its anchor. On even periodic lattices, the resulting
24 color classes have disjoint link supports within each class. Order the
planes and then parity triples lexicographically, and let

$$
U_c(x)=\prod_{p\in c}e^{xS_p},\qquad
D(x)=U_{24}(x)\cdots U_1(x).
$$

This is an exact finite-depth unitary on the unreduced link tensor product.
Each factor commutes with Gauss transformations, so $D(x)$ preserves the
physical sector. It is periodic under translations by two lattice sites.
Expansion only to identify its first derivative gives

$$
D(x)(h-2xN_p)D(x)^\dagger
=K-x\sum_pW_p+R_D(x),
\tag{YM24}
$$

where $R_D(x)$ denotes the exact difference, including every order.
The cancellation follows from
$D'(0)=\sum_pS_p$ and (YM21), independently of layer order.

**Local remainder bound.** A bounded local operator acquires only a finite
neighborhood under 24 layers. The number of relevant gates is bounded by
the fixed layer count and lattice coordination, independently of total
volume. Derivatives of their products are therefore norm bounded uniformly
on any fixed finite interval of $x$.

The electric operator is unbounded, but its first commutators are bounded:
for $l\in p$,

$$
[S_p,E_l^2]=\frac14T_p,\qquad
\|[S_p,E_l^2]\|=\frac14,\qquad
\|[S_p,[S_p,E_l^2]]\|=\frac16;
$$

outside $p$ the commutators vanish. A plaquette-anchored telescoping
identity makes the local cancellation explicit. Write
$\mathcal L_c(A)=U_{24}\cdots U_{c+1} A U_{c+1}^\dagger\cdots U_{24}^\dagger$
and define

$$
k_p(x)=x^2\int_0^1(1-t)e^{txS_p}
[S_p,[S_p,K_p]]e^{-txS_p}\,dt,\qquad
\|k_p(x)\|\le\frac{x^2}{3}.
$$

Disjoint links within a layer imply
$U_cKU_c^\dagger-K=\sum_{p\in c}(xT_p+k_p)$.
Telescoping across the layers therefore gives the exact decomposition

$$
R_D(x)=\sum_c\sum_{p\in c}r_p(x),\qquad
r_p=x\bigl(\mathcal L_c(T_p)-T_p\bigr)
+\mathcal L_c(k_p)-x\bigl(DV_pD^\dagger-V_p\bigr).
$$

Each conjugation difference of a fixed bounded local operator is
$O(|x|)$ in operator norm, with a volume-independent constant: only
finitely many bounded generators meet its 24-layer neighborhood.
Thus every $r_p$ has a fixed finite support, vanishing value and
derivative at zero, and norm bounded by a constant times $x^2$.
This uses bounded commutators throughout.

Group $2\times2\times2$ sites into coarse cells so the circuit and all
transformed interactions are translation invariant on the coarse lattice.
Assign the transformed terms to their original coarse anchors. For
sufficiently large even tori this gives a common finite interaction
support $\mathcal R$ and a decomposition

$$
R_D(x)=\sum_B r_B(x),\qquad
r_B(0)=r_B'(0)=0,\qquad
\|r_B(x)\|\le C_Dx^2
\quad (|x|\le x_0),
\tag{YM25}
$$

with fixed $x_0>0$ and finite $C_D$ independent of volume. Explicitly,
$r_B$ sums the 24 plaquette remainders whose anchors lie in coarse cell
$B$. The cancellation holds for each $r_p$ before this grouping.
The constants and enlarged range arise from the finite gate
neighborhoods; the isolated-square constant in (YM23) is a different
quantity.

This decomposition also fits the relatively bounded version of
Yarotsky's theorem. Let $K_B$ collect the original outgoing-link Casimirs
inside coarse cell $B$, set
$c_{\mathcal R}=4|\mathcal R|/3$, and use local classical operators
$(4/3)\sum_{B'\in B+\mathcal R}K_{B'}$. Their sum is
$c_{\mathcal R}K$ and their local gap is one. Apply the theorem to
$c_{\mathcal R}D(h-2xN_p)D^\dagger$, using coarse-cell perturbations
$-c_{\mathcal R}x\sum_{p:\,\mathrm{anchor}(p)\in B}W_p+c_{\mathcal R}r_B$.
Equation (YM22) verifies the partial-sum relative estimate in
Yarotsky's Remark, Eq. (6), with

$$
\alpha_{\mathrm{rel}}=\frac{32|x|}{3},\qquad
\beta_{\mathrm{rem}}\le c_{\mathcal R}C_Dx^2.
$$

For example, Theorem 2 with its auxiliary exponent $\kappa=2$ applies
whenever $0<\alpha_{\mathrm{rel}}<1$ and

$$
c_{\mathcal R}C_Dx^2
\le\delta_{\mathrm Y}(1-\alpha_{\mathrm{rel}})^8,
\qquad \delta_{\mathrm Y}>0.
\tag{YM26}
$$

These sufficient conditions hold for sufficiently small $|x|$. The
construction retains the exact remainder and preserves the full spectrum
by unitary equivalence. It exposes a purely relative first-order
interaction and a bounded quadratic remainder. It establishes no
quantitative enlargement of the coupling region in (YM18), and
$\alpha_{\mathrm{rel}}$ diverges along $g\to0$.

### 9.13 The exact vacuum-measure gap criterion

The finite-regulator mass-gap question has an exact formulation in terms of
the full interacting vacuum. Let $e_0(a,L)$ be the lowest eigenvalue of $h$
and let $\Omega_{a,L}>0$ be its normalized ground state. The bounded magnetic
potential, compact resolvent and positivity-improving heat kernel on the
connected compact link manifold give a smooth, strictly positive
$\Omega_{a,L}$.

Throughout §§9.13–9.16, use the real-flow left-invariant derivative

$$
X_e^Af(U):=
\left.\frac{d}{dt}
f(\ldots,e^{it\sigma_A/2}U_e,\ldots)\right|_{t=0},
\qquad
K=-\sum_{e,A}(X_e^A)^2.
$$

Define $d\mu_{a,L}=\Omega_{a,L}^2dU$. Multiplication by $\Omega_{a,L}$ is a unitary
map from $L^2(\mu_{a,L})$ to $L^2(dU)$, and its closed quadratic form obeys

$$
\left\langle f\Omega_{a,L},(h-e_0)f\Omega_{a,L}\right\rangle_{dU}
=\sum_{e,A}\int\left|X_e^Af\right|^2\,d\mu_{a,L}.
\tag{YM27}
$$

For real $f$, the identity follows by expanding $X_e^A(f\Omega)$ and using
the weak ground-state equation with test function $f^2$; the complex form
follows by polarization. Its form domain is $H^1(\mu_{a,L})$ with smooth
functions as a core. The ground state is gauge
invariant by positivity and uniqueness, so multiplication by $\Omega$ maps
the gauge-invariant subspace onto itself. Consequently,

$$
\boxed{
\Delta_{\mathrm{phys}}(a,L)=\frac{g^2}{2a}\lambda_{\mathrm{gi}}(\mu_{a,L}),
\qquad
\lambda_{\mathrm{gi}}(\mu):=
\inf_{\substack{f\in H^1(\mu)\ {\rm gauge\ invariant}\\
\mu(f)=0}}
\frac{\sum_{e,A}\int|X_e^Af|^2\,d\mu}
{\int|f|^2\,d\mu}.
}
\tag{YM28}
$$

Thus the regulated physical gap is exactly the gauge-invariant Poincaré rate
of the probability measure defined by the true vacuum. This identity does
not construct the continuum measure. It identifies the quantitative estimate
that a continuum-directed vacuum construction must preserve.

### 9.14 Conditional full-holonomy blocks

Let $B$ range over finite sets of links, with nonnegative weights $w_B$, and
condition the exact measure on the exterior link values
$U_{B^c}=\eta$. Suppose that, for almost every $\eta$, the conditional
measure $\mu_B^\eta$ obeys

$$
\operatorname{Var}_{\mu_B^\eta}F
\le\frac1{\lambda_B(\eta)}
\sum_{e\in B,A}\int|X_e^AF|^2\,d\mu_B^\eta,
\qquad
\lambda_B(\eta)\ge\lambda_{\mathrm{loc}}>0.
\tag{YM29}
$$

For the physical gap it suffices to impose this inequality on the fibre
functions induced by globally gauge-invariant $f$. Such functions are
invariant under vertex transformations supported strictly inside $B$.
Requiring (YM29) for every fibre function is a stronger condition.

Assume also, for every gauge-invariant $f\in L^2(\mu)$ in the form domain,
the approximate tensorization and cover bounds

$$
\operatorname{Var}_{\mu}f
\le A_{\mathrm{AT}}\sum_Bw_B\,
\mathbb E_\mu\!\left[
\operatorname{Var}_{\mu_B^{U_{B^c}}}f\right],
\qquad
\sup_e\sum_{B\ni e}w_B\le\rho.
$$

Apply (YM29) inside each conditional integral and then sum the resulting
Dirichlet forms. No commutation of $X_e^A$ with conditional expectation is
required. The cover multiplicity gives

$$
\lambda_{\mathrm{gi}}(\mu)\ge
\frac{\lambda_{\mathrm{loc}}}{A_{\mathrm{AT}}\rho},
\qquad
\boxed{
\Delta_{\mathrm{phys}}(a,L)\ge
\frac{g^2\lambda_{\mathrm{loc}}}
{2aA_{\mathrm{AT}}\rho}.
}
\tag{YM30}
$$

The local rate in (YM29) belongs to the conditional density
$\Omega(U_B,\eta)^2dU_B$. A block Hamiltonian with boundary data $\eta$ has
its own ground state $\omega_B^\eta$ and measure
$d\nu_B^\eta\propto|\omega_B^\eta|^2dU_B$.

For each boundary value set

$$
C_B(\eta):=
\operatorname{osc}_{U_B}
\log\frac{d\mu_B^\eta}{d\nu_B^\eta},
\qquad
C_B:=\mathop{\rm ess\,sup}_{\eta}C_B(\eta),
$$

and suppose $C_B<\infty$. Direct comparison of variances and Dirichlet
forms then gives, for almost every $\eta$,

$$
\lambda_B^\mu(\eta)
\ge e^{-C_B(\eta)}\lambda_B^\nu(\eta)
\ge e^{-C_B}\lambda_B^\nu(\eta).
\tag{YM31}
$$

Strict positivity makes the pointwise oscillation $C_B(\eta)$ finite for
each fixed finite system and fixed boundary. It does not by itself control
the essential supremum uniformly in the block size, boundary,
$x=2/g^4$, volume or cutoff. One may instead prove (YM29) directly on the
gauge quotient. Either route requires new interacting-vacuum control, and
$A_{\mathrm{AT}}$ remains an independent infrared quantity.

For a fixed target $m_*>0$, (YM30) is sufficient when

$$
\frac{\lambda_{\mathrm{loc}}}{A_{\mathrm{AT}}\rho}
\ge\frac{2am_*}{g^2}.
$$

At fixed bare $g$ the right-hand side tends to zero. The relevant comparison
is along the asymptotically free trajectory $g=g(a)$, jointly with the
thermodynamic limit. The criterion is sufficient; failure of this particular
block estimate does not imply a zero spectral gap.

### 9.15 An exact one-plaquette vacuum obstruction

A common local trial state is

$$
\Phi_\kappa(U)=Z_\kappa^{-1/2}
\exp\!\left(\kappa S(U)\right),
\qquad S=\sum_pV_p,\qquad \kappa\in\mathbb R.
$$

Since $KS=3S$, direct differentiation gives the exact local energy

$$
\frac{h\Phi_\kappa}{\Phi_\kappa}
=2xN_p+(3\kappa-x)S
-\kappa^2\sum_{e,A}(X_e^AS)^2.
\tag{YM32}
$$

At a link shared by plaquettes $p$ and $q$, orient both based holonomies
$A_p,A_q$ to begin with that link. The $SU(2)$ completeness relation and
Cayley–Hamilton identity give

$$
\sum_A(X_e^AV_p)(X_e^AV_q)
=\frac14V_pV_q-\frac12\operatorname{Tr}(A_pA_q),
\qquad
\sum_{e\in p,A}(X_e^AV_p)^2=4-V_p^2.
\tag{YM33}
$$

Fix an elementary plaquette $p$ and project (YM32), in product Haar measure,
onto the normalized characters
$\chi_{1/2}(U_p)=V_p$ and $\chi_1(U_p)=V_p^2-1$. The self term of $p$ is
$4-V_p^2=3-\chi_1(U_p)$. Cross terms between $p$ and a neighboring
plaquette contain an unpaired coefficient of every exterior link of that
neighbor and integrate to zero. A neighboring self term can leave a function
of the single shared link. Such a function still has zero pairing with
$\chi_{1/2}(U_p)$ and $\chi_1(U_p)$ because it omits three links of $p$.
The same coverage argument removes every term supported on a proper subset
of the four plaquette links. The two nonconstant coefficients are therefore

$$
\boxed{
\mathcal C_{p,1/2}\!\left(\frac{h\Phi_\kappa}{\Phi_\kappa}\right)
=3\kappa-x,\qquad
\mathcal C_{p,1}\!\left(\frac{h\Phi_\kappa}{\Phi_\kappa}\right)
=\kappa^2.
}
\tag{YM34}
$$

An eigenfunction has constant local energy. Equation (YM34) would require
$\kappa=0$ and then $x=0$. Hence, for every $x>0$, no member of

$$
\left\{\exp\!\left(\kappa\sum_p\operatorname{Tr}U_p\right):
\kappa\in\mathbb R\right\}
$$

is the exact vacuum on an ordinary periodic cubic lattice of even side
$L\ge4$. The result also holds on open boxes with embedded elementary
plaquettes. It excludes
the equal-weight one-plaquette exponential family. Exponentials containing
larger loops have additional gradient cross terms and require their own
analysis.

### 9.16 Weak-field kernels and exact Gaussian block controls

#### 9.16.1 The transverse vacuum kernel

Write $U_e=\exp(iA_e^A\sigma_A/2)$ and let $C$ be the linear plaquette-curl
map. On the nonzero transverse subspace, the quadratic Hamiltonian is

$$
H^{(2)}=\frac1{2a}
\left[g^2p^Tp+\frac1{2g^2}A^TC^TCA\right].
\tag{YM35}
$$

Its positive ground state and mode frequencies are

$$
\Omega^{(2)}(A)\propto
\exp\!\left[-\frac12A^T
\frac{\sqrt{C^TC}}{\sqrt2g^2}A\right],
\qquad
\omega_\lambda=\frac{\sqrt\lambda}{\sqrt2a}.
\tag{YM36}
$$

The one-plaquette exponential instead has quadratic exponent
$-\kappa A^TC^TCA/4$. Matching (YM36) on an eigenvalue $\lambda>0$ requires
$\kappa=\sqrt2/(g^2\sqrt\lambda)$. A single $\kappa$ cannot match two
distinct positive eigenvalues. For the isolated square $\lambda=4$ gives
$\kappa=\sqrt{x}/2$, while its two-quantum gauge-singlet radial-ladder
spacing is $2\sqrt2/a$, as in (YM13). The square-root kernel in (YM36) is nonlocal in
lattice position. Pure-gauge and global flat modes are excluded from this
quadratic inverse, and nonlinear magnetic and Gauss terms enter beyond the
transverse approximation.

#### 9.16.2 Conditional gaps and tensorization

The finite Gaussian family

$$
D_N(m)=\operatorname{tridiag}(-1,2+m^2,-1),\qquad
Q=\sqrt{D_N(m)},\qquad
d\mu_N\propto e^{-q^TQq}\,dq
$$

separates local conditional control from global infrared control. Let
$d_i=Q_{ii}$ and $D=\operatorname{diag}(d)$. The global Poincaré rate,
single-coordinate conditional rates, and optimal all-function
conditional-variance tensorization constant are

$$
\lambda_{\mathrm{glob}}=2\lambda_{\min}(Q),\qquad
\lambda_i^{\mathrm{cond}}=2d_i,\qquad
\boxed{
A_{\mathrm{AT}}=
\frac1{\lambda_{\min}(D^{-1/2}QD^{-1/2})}.
}
\tag{YM37}
$$

For completeness, let $P_i f=\mathbb E(f\mid q_{-i})$. In the first Gaussian
chaos, $I-P_i$ projects onto the normalized conditional residual

$$
\widehat g_i=
\frac{q_i-\mathbb E(q_i\mid q_{-i})}{\sqrt{1/(2d_i)}}.
$$

The Gram matrix of these residuals is
$D^{-1/2}QD^{-1/2}$. Thus the first-chaos deficit
$\sum_i(I-P_i)$ has the gap in (YM37), and a linear function in its bottom
eigendirection attains the bound. On chaos $n$, $P_i$ acts as
$R_i^{\otimes_s n}$, where $R_i$ is the first-chaos projection onto the
variables $q_{-i}$. The range inclusion

$$
\operatorname{ran}\!\left((I-R_i)\otimes I^{\otimes(n-1)}\right)
\subseteq\operatorname{ran}\!\left(I-R_i^{\otimes n}\right)
$$

gives the same lower deficit on every higher chaos. Summing the orthogonal
chaoses proves the all-function value in (YM37).

For $m=0$,

$$
\lambda_{\min}(Q)=2\sin\frac{\pi}{2(N+1)},\qquad
1\le d_i\le\sqrt2.
$$

The lower diagonal bound follows from
$\sqrt t\ge t/2$ on the spectrum $0<t<4$ of $D_N(0)$; the upper bound follows
from $d_i^2\le(Q^2)_{ii}=2$. The generalized Rayleigh quotient then gives

$$
\boxed{
\frac1{\lambda_{\min}(Q)}
\le A_{\mathrm{AT}}\le
\frac{\sqrt2}{\lambda_{\min}(Q)}.
}
\tag{YM38}
$$

Every single-coordinate conditional rate remains between $2$ and
$2\sqrt2$, while $A_{\mathrm{AT}}$ grows linearly and the global rate tends
to zero. This exact family disproves any implication from uniformly positive
conditional gaps alone to a volume-uniform global gap. The tensorization
constant carries the missing long-distance information.

#### 9.16.3 Exact state reduction

Partition a positive Gaussian precision matrix into retained and eliminated
coordinates. Configuration marginalization gives

$$
Q_{\mathrm{eff}}=Q_{RR}-Q_{RE}Q_{EE}^{-1}Q_{ER},
\qquad
Q_{\mathrm{eff}}^{-1}=(Q^{-1})_{RR}.
$$

The true reduced quantum state has

$$
C_q=\frac12Q_{\mathrm{eff}}^{-1},\qquad
C_p=\frac12Q_{RR}.
$$

The pure wavefunction obtained from the square root of the configuration
marginal has the same $C_q$ and
$C_p^{\mathrm{pure}}=Q_{\mathrm{eff}}/2$. Its missing momentum covariance is

$$
\boxed{
C_p-C_p^{\mathrm{pure}}
=\frac12Q_{RE}Q_{EE}^{-1}Q_{ER}\succeq0.
}
\tag{YM39}
$$

The symplectic eigenvalues of the true reduced covariance satisfy

$$
\nu_k=\frac12
\sqrt{\lambda_k(Q_{\mathrm{eff}}^{-1}Q_{RR})}\ge\frac12.
\tag{YM40}
$$

The reduced state is mixed exactly when $Q_{RE}\ne0$: at least one
$\nu_k$ then exceeds $1/2$. Every symplectic eigenvalue exceeds $1/2$ when
$Q_{RE}$ has full row rank. A configuration marginal therefore preserves
all position observables while losing part of the quantum momentum data.

For an exact spectral reduction, let $P_{\mathcal H}$ be a gauge-compatible
Hilbert-space projection and $\overline P=I-P_{\mathcal H}$. Whenever
$z$ lies in the resolvent set of
$\overline P H\overline P$ and the off-diagonal coupling satisfies the
required form bounds, the Feshbach–Schur operator is

$$
F(z)=P_{\mathcal H}HP_{\mathcal H}
-P_{\mathcal H}H\overline P
(\overline P H\overline P-z)^{-1}
\overline P H P_{\mathcal H}.
\tag{YM41}
$$

Its energy dependence and discarded-sector resolvent retain information
absent from a static pure marginal. Uniform gap transfer additionally needs
uniform control of that resolvent and coupling. Equations (YM27)–(YM41)
reduce the next weak-coupling step to quantitative estimates on the exact
conditional vacuum measures and their tensorization along $g=g(a)$. Those
interacting estimates and the continuum construction remain open.

### 9.17 Exact cylindrical maps and refined-plaquette leakage

The block question admits an exact kinematic map before any approximation is
made. Let $\Gamma_f$ and $\Gamma_c$ be finite fine and coarse graphs. For each
coarse edge $c$, choose a nonempty edge-simple oriented fine path

$$
P_c=(e_{c,1}^{\sigma_{c,1}},\ldots,e_{c,n_c}^{\sigma_{c,n_c}}),
\qquad \sigma_{c,j}\in\{-1,+1\},
$$

with the paths pairwise edge-disjoint. Choose a consistent fine-vertex
representative $\iota(v)$ for every coarse endpoint, and define

$$
\pi(U)_c
=U_{e_{c,1}}^{\sigma_{c,1}}\cdots
 U_{e_{c,n_c}}^{\sigma_{c,n_c}},
\qquad
(Jf)(U)=f(\pi(U)).
\tag{YM42}
$$

Normalized Haar measure is invariant under inversion, and a product of
independent Haar variables is Haar. Pairwise edge-disjoint paths therefore
give the joint pushforward
$\pi_*\mu_f=\mu_c$ and

$$
J^*J=I,\qquad
\pi(U^h)_c
=h_{\iota(s(c))}\pi(U)_c h_{\iota(t(c))}^{-1}.
\tag{YM43}
$$

Internal fine-vertex transformations telescope along the path. Coarse
gauge-invariant functions consequently pull back to fine gauge-invariant
functions when the endpoint representatives are consistent. Overlapping or
repeated paths require a separate joint-Haar and derivative analysis; they
are outside (YM42).

Let

$$
\mathcal E_f=-\sum_{e,A}(X_e^A)^2
$$

use the same orthonormal Lie-algebra basis as the coarse electric operator.
A left derivative on a forward path edge induces a conjugated left
derivative of the coarse holonomy. A reversed edge induces a conjugated right
derivative with a minus sign. The adjoint matrices are orthogonal, and the
left and right quadratic Casimirs agree. On the smooth cylindrical core this
gives the stronger intertwining identity

$$
\mathcal E_fJ
=J\sum_c n_c\mathcal E_c^{(c)},
\qquad
J^*\mathcal E_fJ
=\sum_c n_c\mathcal E_c^{(c)}.
\tag{YM44}
$$

For uniform path length $n_c=b$, $a_c=ba_f$ and no separate energy
rescaling, matching the physical electric coefficients requires

$$
\frac{g_f^2}{2a_f}\,b
=\frac{g_c^2}{2a_c},
\qquad
\boxed{g_c^2=b^2g_f^2},
\qquad
x_c=\frac{x_f}{b^4}.
\tag{YM45}
$$

This is the exact coupling relation for the one-path cylindrical
intertwiner. It is not a Yang–Mills beta function. In particular, a physical
coarse electric flux normally combines parallel fine fluxes across a dual
face, information absent from the single-path construction.

#### 9.17.1 Conditional expectation and the exact invariance criterion

Let $\mathcal A_c=\sigma(\pi)$,
$\mathcal I=\operatorname{Ran}J$, $P=JJ^*$ and $Q=I-P$. The orthogonal
projection is conditional expectation onto the coarse holonomies. For every
bounded multiplication operator $M_F$,

$$
J^*M_FJ
=M_{\mathbb E_{\mathrm H}[F\mid\mathcal A_c]}.
\tag{YM46}
$$

Write

$$
W_f=\sum_{p\in P_f}\chi_{1/2}(U_p),
\qquad
h_f=\mathcal E_f+2x_fN_{p,f}-x_fW_f.
$$

Because $1\in\mathcal I$ and multiplication by an
$\mathcal A_c$-measurable function preserves $\mathcal I$,

$$
M_{W_f}\mathcal I\subseteq\mathcal I
\quad\Longleftrightarrow\quad
W_f\in\mathcal I
\quad\Longleftrightarrow\quad
QW_f=0.
\tag{YM47}
$$

Equation (YM44) shows that the electric term preserves $\mathcal I$. Thus
$QW_f$ is the exact obstruction to invariance of this cylindrical subspace
under the full Hamiltonian. An individual fine plaquette can have a nonzero
conditional mean, and residuals from several plaquettes can correlate. The
general normalized-Haar quantity is

$$
\begin{aligned}
\sigma_f^2
&:=\|QW_f\|_2^2\\
&=\sum_{p,q}
\left[
\langle\chi_p,\chi_q\rangle
-\left\langle
\mathbb E(\chi_p\mid\mathcal A_c),
\mathbb E(\chi_q\mid\mathcal A_c)
\right\rangle
\right].
\end{aligned}
\tag{YM48}
$$

This conditional-variance formula, rather than a count of nominally
discarded plaquettes, determines the leakage.

#### 9.17.2 A genuine $2\times2$ spatial refinement

Take an open square divided into four elementary fine plaquettes. Its nine
vertices and twelve links include four interior links. The four coarse
boundary edges are the counterclockwise products of two fine boundary links
each; no interior link occurs in a coarse path. Every elementary plaquette
contains an interior witness link that is independent of $\mathcal A_c$ and
appears once in its character. Peter–Weyl orthogonality gives

$$
\mathbb E_{\mathrm H}(\chi_p\mid\mathcal A_c)=0,
\qquad
\langle\chi_p,\chi_q\rangle=\delta_{pq},
\qquad p,q\in\{1,2,3,4\},
\tag{YM49}
$$

for the unnormalized fundamental character
$\chi_{1/2}=\operatorname{Tr}$, whose $L^2$ norm is one. The four plaquette
characters are pairwise orthogonal because each pair has a fine edge
belonging to only one member.

For the normalized constant coarse state,

$$
Qh_fJ1
=-x_f\sum_{p=1}^4\chi_p,
\qquad
\boxed{\|Qh_fJ1\|_2=2x_f}.
\tag{YM50}
$$

The constant $2x_fN_{p,f}$ lies in $\mathcal I$. Any scalar vacuum-energy
subtraction therefore leaves (YM50) unchanged. Each $\chi_p$ is a closed
Wilson loop, so the same leakage lies in the Gauss-invariant physical
Hilbert space. In physical units,

$$
\boxed{
\|QH_fJ1\|_2
=\frac{g_f^2}{2a_f}(2x_f)
=\frac{2}{a_fg_f^2}.
}
\tag{YM51}
$$

Compression also displays the magnetic mismatch. If
$\mathcal E_c$ is the sum over the four coarse boundary edges, then

$$
J^*h_fJ=2\mathcal E_c+8x_fI.
\tag{YM52}
$$

The standard one-plaquette coarse magnetic operator instead contains
$2x_c-x_c\chi_{1/2}(U_{\partial B})$. The outer character is retained by
$\pi$, but it is not generated by the first-order compression of the four
elementary fine characters.

For every coarse operator $A$ whose image is carried back by $J$,
orthogonality gives

$$
\|h_fJ1-JA1\|_2
\ge\|Qh_fJ1\|_2
=2x_f.
\tag{YM53}
$$

Hence no coarse operator exactly intertwines the full $h_f$ with this bare
cylindrical $J$ on the refined block. For a fundamental plaquette character,
$\mathcal E_f\chi_p=3\chi_p$ and
$\langle\chi_p,h_f1\rangle=-x_f$. The dimensionless electric Casimir
eigenvalue is therefore $3$, while the magnetic vacuum-to-plaquette matrix
element has magnitude $x_f$. The ratio $x_f/3$ grows without bound as
$g_f\to0$. This excludes an $x_f$-uniform unweighted $L^2$ or electric-vacuum
graph-norm smallness estimate for this fixed map. It does not exclude a
resolvent-weighted Feshbach estimate: the discarded-sector energy can scale
with $x_f$ as well. At every fixed finite lattice the magnetic multiplication
operator remains bounded, with an $x_f$-dependent bound.

Pure graph subdivision supplies the required control. Subdivide each edge of
one square while retaining the outer square as the only face. Its face
holonomy is the product of complete coarse path holonomies, so $QW_f=0$ and
the magnetic term preserves $\mathcal I$. This operation adds no elementary
spatial faces and does not lower the plaquette cutoff. Path length $b>1$
alone therefore does not determine magnetic leakage.

#### 9.17.3 The remaining dynamical map

Disintegrate fine Haar measure over the coarse variables as
$d\mu_f=d\mu_c(v)\,d\nu_v(r)$. A normalized, gauge-compatible fibre family
defines another exact isometry,

$$
(J_\omega f)(U)
=f(\pi(U))\omega_{\pi(U)}(r),
\qquad
\int|\omega_v(r)|^2\,d\nu_v(r)=1.
\tag{YM54}
$$

Its dynamical closure condition is

$$
(I-J_\omega J_\omega^*)H_fJ_\omega=0.
\tag{YM55}
$$

A coarse-holonomy-dependent fibre can encode the interacting eliminated
sector. Fine electric derivatives then act on both $f$ and $\omega_v$,
generally producing connection, Born–Huang, coarse–fibre cross and scalar
terms. Magnetic compression generates boundary-dependent and multi-loop
interactions. Gauge constraints can add boundary representation sectors.
Replacing (YM55) by the Feshbach operator (YM41) retains the corresponding
energy-dependent discarded-sector resolvent. None of these terms is supplied
by the bare map (YM42), and none is excluded by (YM50).

The physical-gap units impose a separate exact requirement. For a fixed
physical box with $a_c=ba_f$ and the corresponding lattice-site count
reduced by $b$ in each blocked direction,

$$
\frac{g_f^2}{2a_f}\widehat\Delta_f
=\frac{g_c^2}{2ba_f}\widehat\Delta_c,
\qquad
\boxed{
\widehat\Delta_c
=\frac{b g_f^2}{g_c^2}\widehat\Delta_f.
}
\tag{YM56}
$$

Under the kinematic electric matching (YM45), this becomes
$\widehat\Delta_c=\widehat\Delta_f/b$. It is a unit relation, not a spectral
conclusion, because (YM50) prevents restriction of the full fine Hamiltonian
to $\mathcal I$. A finite continuum mass $m_*$ still requires

$$
\widehat\Delta(a,L(a))
\sim\frac{2a\,m_*}{g(a)^2}
$$

together with thermodynamic control and construction of the continuum
quantum field.

The exact bare map therefore fixes one proof boundary. Section 9.19 gives the
finite representation support of one fundamental-boundary sector. A viable
next map must carry an interacting gauge-compatible fibre or an equivalent
transfer operator, transport boundary sectors consistently, retain every
generated interaction, control the off-diagonal resolvent uniformly, and
obey (YM56). The hypothesized Cassi scale law supplies none of those
gauge-theory structures. The continuum existence and mass-gap questions
remain open.

The source-bound primary schedule passes 53 checks. A separate JavaScript
implementation reconstructs the fixed inventories, quaternion moments,
Casimirs, path controls, scale identities and every primary detail in 169
checks. Post-reconstruction analytical review assigns **ADOPT** to
(YM42)–(YM48) under their stated finite-graph hypotheses and to
(YM49)–(YM53) at the fixed refinement. The finite controls **SUPPORT** the
declared fixtures. Exact full-Hamiltonian intertwining by the bare
cylindrical map is **CONTRADICTED** only on the fixed genuine
$2\times2$ refinement. Dynamically closed boundary-sector fibres, uniform
resolvent control, weak-coupling volume bounds, the thermodynamic and
continuum limits, the continuum mass gap and Cassi microscopic identification
remain **UNRESOLVED**.

### 9.18 Continuous-$SU(2)$ radial Feshbach transfer

This section gives the exact cutoff reduction for one continuous-$SU(2)$
isolated open square. The electric-character cutoff produces a finite
Feshbach pencil whose discarded tail is an energy-dependent scalar
self-energy. The same calculation shows why a cutoff of order
$x^{1/4}$ can isolate a fixed low-energy window while bare compression
requires a cutoff whose ratio to $x^{1/4}$ diverges.

#### 9.18.1 Radial Hilbert space and operator domain

The continuous group is represented by the normalized Haar class-function
sector, so the character index is an infinite Hilbert-space coordinate rather
than a finite quadrature label. With $n=2j$, the orthonormal basis,
Haar measure, and character functions are

$$
\mathcal H_\square
:=L^2\!\left([0,\pi],\frac{2}{\pi}\sin^2\theta\,d\theta\right),
\qquad
\mathcal H_\square\xrightarrow[\{|n\rangle\}]{\cong}\ell^2(\mathbb N_0),
\qquad
|n\rangle:=\chi_{n/2},\qquad
d\mu(\theta)=\frac{2}{\pi}\sin^2\theta\,d\theta,
\qquad
\chi_{n/2}(\theta)=\frac{\sin((n+1)\theta)}{\sin\theta}.
\tag{YM57}
$$

The character basis in (YM57) supplies the coordinate realization of the same
continuous-group Hilbert space. Define
$k_n=n(n+2)$. The multiplication recurrence
$\chi_{1/2}\chi_{n/2}=\chi_{(n-1)/2}+\chi_{(n+1)/2}$, with the first term
absent at $n=0$, gives the half-line Jacobi operator below:

$$
\begin{aligned}
K|n\rangle&=k_n|n\rangle,\qquad
D(K)=\left\{f\in\ell^2:\sum_{n=0}^{\infty}k_n^2|f_n|^2<\infty\right\},\\
T|0\rangle&=|1\rangle,\qquad
T|n\rangle=|n-1\rangle+|n+1\rangle\quad(n\geq1),\qquad
\|T\|=2,\\
\langle f,(2I-T)f\rangle
&=|f_0|^2+\sum_{n=0}^{\infty}|f_{n+1}-f_n|^2\geq0.
\end{aligned}
\tag{YM58}
$$

The last identity first holds for finitely supported $f$ and then by
closure. The bound $\|T\|\leq2$ follows from the two nearest-neighbor
terms, and long constant blocks give approximate vectors with Rayleigh
quotient tending to $2$, proving equality. Thus $K$ is nonnegative
self-adjoint on $D(K)$, while $T$ is bounded self-adjoint. For $g,a>0$,
use exactly

$$
x=\frac{2}{g^4},\qquad
h_x=K+x(2I-T),\qquad
H_\square=\frac{g^2}{2a}h_x,\qquad
D(h_x)=D(K),\qquad h_x\geq0.
\tag{YM59}
$$

The bounded-perturbation theorem gives self-adjointness on $D(K)$.
Since $(K+1)^{-1}$ is compact, the resolvent identity for a bounded
perturbation gives compact resolvent for $h_x$. The same argument on
$Q_N\mathcal H_\square$ gives self-adjointness on $Q_ND(K)$, compact
resolvent, and discrete spectrum for every tail used below.

The radial unitary $U:\mathcal H_\square\to L^2((0,\pi),d\theta)$ is
$(U\psi)(\theta)=\sqrt{2/\pi}\sin\theta\,\psi(\theta)$. Since
$U|n\rangle=\sqrt{2/\pi}\sin((n+1)\theta)$, direct differentiation and
multiplication by $1-\cos\theta$ give

$$
U h_xU^{-1}
=\widetilde h_x
:=-\frac{d^2}{d\theta^2}-1+2x(1-\cos\theta),
\qquad
D(\widetilde h_x)=H^2(0,\pi)\cap H_0^1(0,\pi).
\tag{YM60}
$$

The endpoint conditions are the radial Dirichlet conditions. This establishes
the continuous-$SU(2)$ operator before any finite-section or numerical
approximation.

#### 9.18.2 Exact Schur reduction and Weyl identities

For $N\geq0$, retain characters $0,\ldots,N$ and write

$$
P_N=\sum_{n=0}^{N}|n\rangle\langle n|,\qquad
Q_N=I-P_N,\qquad
A_N=P_Nh_xP_N,\qquad
D_N=Q_Nh_xQ_N,\qquad
V_N=P_Nh_xQ_N=-x|N\rangle\langle N+1|.
\tag{YM61}
$$

For $z\in\rho(D_N)$, put $B_N(z)=D_N-z$ and
$
m_{N+1}(z):=\langle N+1|B_N(z)^{-1}|N+1\rangle .
$
Eliminating the $Q_N$-component is an exact operation on the operator
domain. The block Gaussian factorization is

$$
\begin{pmatrix}A_N-z&V_N\\ V_N^*&B_N(z)\end{pmatrix}
=
\begin{pmatrix}I&V_NB_N(z)^{-1}\\0&I\end{pmatrix}
\begin{pmatrix}F_N(z)&0\\0&B_N(z)\end{pmatrix}
\begin{pmatrix}I&0\\B_N(z)^{-1}V_N^*&I\end{pmatrix},
\tag{YM62}
$$

where

$$
F_N(z)
:=A_N-zP_N-V_NB_N(z)^{-1}V_N^*
:=P_N(h_x-z)P_N
-x^2m_{N+1}(z)|N\rangle\langle N|.
\tag{YM63}
$$

The two triangular factors in (YM62) are boundedly invertible. Therefore,
including algebraic multiplicity of a finite-order spectral zero,

$$
z\in\sigma(h_x)
\quad\Longleftrightarrow\quad
0\in\sigma(F_N(z)),
\qquad z\in\rho(D_N).
\tag{YM64}
$$

Indeed, if $p=P_N\psi$, the second block equation gives the unique
discarded component

$$
Q_N\psi
=-(D_N-z)^{-1}V_N^*p
=x\,p_N(D_N-z)^{-1}|N+1\rangle,
\qquad p_N=\langle N|p\rangle.
\tag{YM65}
$$

Conversely, (YM65) reconstructs a vector in the domain from every
$p\in\ker F_N(z)$. This gives the eigenspace correspondence directly;
the factorization gives the corresponding analytic multiplicity statement.

To make the tail scalar explicit, let $D^{(n)}$ be the restriction of
$h_x$ to $\ell^2(\{n,n+1,\ldots\})$, define
$m_n(z)=\langle n|(D^{(n)}-z)^{-1}|n\rangle$, and set
$d_n=k_n+2x$. Schur elimination of the first tail site gives

$$
m_n(z)=\frac{1}{d_n-z-x^2m_{n+1}(z)}.
\tag{YM66}
$$

For the finite tail $n,\ldots,M$, define

$$
\Delta_{n,M}(z)
:=(d_n-z)\Delta_{n+1,M}(z)-x^2\Delta_{n+2,M}(z),
\qquad
\Delta_{M+1,M}=1,\qquad
\Delta_{M+2,M}=0,
\qquad
m_n^{(M)}(z)=\frac{\Delta_{n+1,M}(z)}{\Delta_{n,M}(z)}.
\tag{YM67}
$$

The finite resolvents converge at a fixed resolvent point to the half-line
resolvent, so $m_n^{(M)}(z)$ converges to $m_n(z)$. If
$h_x^{(M)}=P_Mh_xP_M$ and $D_N^{(M)}$ is its restriction to
$N+1,\ldots,M$, the same block factorization gives the determinant
identity

$$
\frac{\det(h_x^{(M)}-z)}
{\det(D_N^{(M)}-z)}
=\det F_N^{(M)}(z).
\tag{YM68}
$$

For real $E<\inf\sigma(D_N)$, the spectral measure $\nu_{N+1}$ of
$D_N$ at $|N+1\rangle$ yields

$$
m_{N+1}(E)
=\int\frac{d\nu_{N+1}(\lambda)}{\lambda-E}>0,\qquad
m_{N+1}'(E)
=\int\frac{d\nu_{N+1}(\lambda)}{(\lambda-E)^2}>0,\qquad
m_n'(E)=m_n(E)^2\bigl(1+x^2m_{n+1}'(E)\bigr).
\tag{YM69}
$$

The first two identities follow by differentiating the resolvent under the
spectral integral; the last follows by differentiating (YM66). They provide
the derivative needed for both the pole test and tail reconstruction.

#### 9.18.3 Jensen, free-tail, and self-energy bounds

Let $r=N+1$, $E<k_r$, and $\delta=k_r-E>0$. On the tail, let $L_+$
be the Dirichlet half-line Laplacian,
$(L_+f)_r=2f_r-f_{r+1}$ and
$(L_+f)_n=2f_n-f_{n-1}-f_{n+1}$ for $n>r$. Since $k_n\geq k_r$,

$$
B_N(E):=D_N-E\geq\delta I+xL_+,\qquad
\langle r|B_N(E)|r\rangle=\delta+2x,\qquad
m_r(E)\geq\frac{1}{\delta+2x}.
\tag{YM70}
$$

The last inequality is Jensen's inequality for $t\mapsto t^{-1}$ applied
to the spectral measure of $B_N(E)$:
$\int t^{-1}d\nu(t)\geq(\int t\,d\nu)^{-1}$. The operator order in the
first inequality reverses under inversion. The boundary Green function of
the free comparison tail therefore satisfies

$$
\begin{aligned}
g_+(\delta,x)
&:=\langle r|(\delta I+xL_+)^{-1}|r\rangle
=\frac{1}{\delta+2x-x^2g_+(\delta,x)}\\
&=\frac{\delta+2x-\sqrt{\delta(\delta+4x)}}{2x^2}
=\frac{2}{\delta+2x+\sqrt{\delta(\delta+4x)}}.
\end{aligned}
\tag{YM71}
$$

The positive solution is selected by $g_+>0$. Define
$\Sigma_N(E)=x^2m_r(E)$ and
$
s(\delta,x):=x^2g_+(\delta,x)
$
to obtain the complete self-energy bracket

$$
\boxed{
\frac{x^2}{\delta+2x}
\leq\Sigma_N(E)
\leq s(\delta,x)
:=\frac{\delta+2x-\sqrt{\delta(\delta+4x)}}{2}
:=\frac{2x^2}{\delta+2x+\sqrt{\delta(\delta+4x)}}
\leq\min\left\{x,\frac{x^2}{\delta}\right\}.
}
\tag{YM72}
$$

The two final estimates follow directly from the two forms of $s$. Since
$F_N(E)=A_N-E-\Sigma_N(E)|N\rangle\langle N|$, (YM72) also gives

$$
A_N-E-s(\delta,x)|N\rangle\langle N|
\leq F_N(E)
\leq A_N-E-\frac{x^2}{\delta+2x}|N\rangle\langle N|.
\tag{YM73}
$$

At an eigenvalue $E<\inf\sigma(D_N)$, choose $p\in\ker F_N(E)$ with
$\|p\|=1$. Equations (YM65) and (YM69) then give

$$
\|Q_N\psi\|^2
=x^2|p_N|^2m_{N+1}'(E),\qquad
-F_N'(E)
=I+x^2m_{N+1}'(E)|N\rangle\langle N|.
\tag{YM74}
$$

Thus the discarded probability and the normalization correction are obtained
from the differentiated Weyl function itself. In particular,
$\delta=o(x)$ forces $\Sigma_N(E)=\Theta(x)$, while
$\delta/x\to\infty$ gives $\Sigma_N(E)\sim x^2/\delta$. The exact
self-energy is consequently of the same order as the magnetic diagonal
term whenever the tail threshold approaches the low energy on a scale
smaller than $x$.

#### 9.18.4 Negative-axis resolvent estimates

Set $z=-\eta$ with $\eta>0$, $B_\eta=D_N+\eta$, and
$
S_\eta:=A_N+\eta-V_NB_\eta^{-1}V_N^* .
$
Because $D_N>0$, $h_x\geq0$ implies
$A_N-V_ND_N^{-1}V_N^*\geq0$. Also
$B_\eta^{-1}\leq D_N^{-1}$, so $S_\eta\geq\eta P_N$. Block inversion
therefore gives

$$
P_N(h_x+\eta)^{-1}P_N=S_\eta^{-1},\qquad
Q_N(h_x+\eta)^{-1}P_N
=-B_\eta^{-1}V_N^*S_\eta^{-1}.
\tag{YM75}
$$

Now $\|B_\eta^{-1}\|\leq(k_r+\eta)^{-1}$,
$\|V_N\|=x$, and both $S_\eta^{-1}$ and
$(A_N+\eta)^{-1}$ have norm at most $\eta^{-1}$. The inverse identity
$
S_\eta^{-1}-(A_N+\eta)^{-1}
=S_\eta^{-1}V_NB_\eta^{-1}V_N^*(A_N+\eta)^{-1}
$
then proves

$$
\left\|P_N(h_x+\eta)^{-1}P_N-(A_N+\eta)^{-1}\right\|
\leq\frac{x^2}{\eta^2(k_r+\eta)}.
\tag{YM76}
$$

The off-diagonal block in (YM75) gives the companion estimate

$$
\left\|Q_N(h_x+\eta)^{-1}P_N\right\|
\leq\frac{x}{\eta(k_r+\eta)}.
\tag{YM77}
$$

At $\eta=c\sqrt{x}$, the first right-hand side tends to zero under the
sufficient unweighted condition $N/\sqrt{x}\to\infty$, because
$k_r\sim N^2$. To make it negligible compared with the natural resolvent
scale $x^{-1/2}$, the sufficient condition is
$N/x^{3/4}\to\infty$. These are conservative operator-norm estimates and
do not replace the low-energy form argument below.

#### 9.18.5 Weak-coupling Mathieu scale

The radial equation becomes a Mathieu equation after $z=\theta/2$:

$$
\frac{d^2u}{dz^2}
+\left[4(\lambda+1-2x)+8x\cos(2z)\right]u=0,
\qquad
a_{\mathrm M}=4(\lambda+1-2x),\qquad
q_{\mathrm M}=-4x=-\frac{8}{g^4}.
\tag{YM78}
$$

The Dirichlet endpoints select the even-order sine characteristic values.
For the fixed-level asymptotics, put $y=x^{1/4}\theta$. Taylor expansion of
the same differential operator gives, on every fixed $y$-compact set,

$$
x^{-1/2}\widetilde h_x
=-\frac{d^2}{dy^2}+y^2
+x^{-1/2}\left(-1-\frac{y^4}{12}\right)
+O(x^{-1}y^6),
\qquad
0<y<\pi x^{1/4}.
\tag{YM79}
$$

The limiting operator is the Dirichlet half-line oscillator. Its $j$-th
state is the odd full-line oscillator state of index $2j+1$, with energy
$4j+3$. The first perturbation is obtained by taking the expectation of
$-1-y^4/12$. Writing $y=(a+a^\dagger)/\sqrt2$ in oscillator units and
normal-ordering $y^4$ gives the displayed fourth moment:

$$
\left\langle\phi_{2j+1},y^4\phi_{2j+1}\right\rangle
=6j^2+9j+\frac{15}{4},\qquad
c_j=-1-\frac{1}{12}\left(6j^2+9j+\frac{15}{4}\right),
\qquad
\lambda_j(h_x)=(4j+3)\sqrt{x}+c_j+O(x^{-1/2}).
\tag{YM80}
$$

The oscillator states are exponentially localized while the far endpoint is
$\pi x^{1/4}$, so the Taylor remainder and endpoint error have the stated
order for each fixed $j$.

Subtracting the $j=0$ expansion gives the gap formula below. Since
$c_1-c_0=-5/4$ and $\sqrt{x}=\sqrt2/g^2$, multiplication by
$g^2/(2a)$ gives the isolated-square physical spacing

$$
\lambda_j(h_x)-\lambda_0(h_x)
=4j\sqrt{x}
-\left(\frac{j^2}{2}+\frac{3j}{4}\right)
+O(x^{-1/2}),
\qquad
\Delta_{\square,1}
=\frac{g^2}{2a}\bigl[\lambda_1(h_x)-\lambda_0(h_x)\bigr]
=\frac{2\sqrt2}{a}-\frac{5g^2}{8a}+O(g^4/a).
\tag{YM81}
$$

The leading $2\sqrt2/a$ has status solely as an isolated ultraviolet
plaquette normalization; volume-uniform interacting masses and continuum
predictions remain outside this result.

#### 9.18.6 Retained and discarded forms

For $f=(f_0,\ldots,f_N)$, the retained finite section has the exact form

$$
\begin{aligned}
\langle f,A_Nf\rangle
={}&\sum_{n=0}^{N}k_n|f_n|^2\\
&+x\left(
|f_0|^2+|f_N|^2+\sum_{n=0}^{N-1}|f_{n+1}-f_n|^2
\right).
\end{aligned}
\tag{YM82}
$$

The bracketed term is the Dirichlet discrete Laplacian on
$0,\ldots,N$. Its sine eigenvectors have lowest eigenvalue
$4\sin^2[\pi/(2(N+2))]$, hence

$$
\lambda_0(A_N)\geq
4x\sin^2\frac{\pi}{2(N+2)}.
\tag{YM83}
$$

For $f=(f_{N+1},f_{N+2},\ldots)$, the discarded tail has the different
boundary form

$$
\begin{aligned}
\langle f,D_Nf\rangle
={}&\sum_{n=N+1}^{\infty}k_n|f_n|^2\\
&+x\left(
|f_{N+1}|^2+\sum_{n=N+1}^{\infty}|f_{n+1}-f_n|^2
\right).
\end{aligned}
\tag{YM84}
$$

These identities retain the electric potential and every boundary term; the
bare section $A_N$ simply removes the tail and its self-energy.

Let $\varepsilon=x^{-1/4}$, $y_n=\varepsilon n$, $C_x=\varepsilon N$,
and rescale a sequence by $u_n=\varepsilon^{-1/2}f_n$, so
$\sum_n|f_n|^2$ is a Riemann sum for $\int|u|^2dy$. Then

$$
\frac{k_n}{\sqrt{x}}=y_n^2+2\varepsilon y_n,\qquad
x^{-1/2}x\sum_n|f_{n+1}-f_n|^2
=\varepsilon^{-1}\sum_n|u_{n+1}-u_n|^2,\qquad
x^{-1/2}x|f_n|^2=\varepsilon^{-1}|u_n|^2.
\tag{YM85}
$$

The middle expression converges to $\int|u'|^2dy$ under piecewise-linear
interpolation. The last expression diverges unless the interpolated function
vanishes at the associated finite endpoint. Thus the two boundary penalties
in (YM82) impose Dirichlet data at $y=0,C$, while the one in (YM84) imposes
Dirichlet data at $y=C$.

If $N/x^{1/4}\to C\in(0,\infty)$, the Riemann-sum calculation, lower
semicontinuity, and compactly supported recovery sequences give the form
limits

$$
x^{-1/2}A_N\xrightarrow{\mathrm{form}}
H_{\mathrm{osc}}^{(0,C)}
:=-\frac{d^2}{dy^2}+y^2
\quad\hbox{on }(0,C),
\qquad
x^{-1/2}D_N\xrightarrow{\mathrm{form}}
H_{\mathrm{osc}}^{(C,\infty)}
:=-\frac{d^2}{dy^2}+y^2
\quad\hbox{on }(C,\infty).
\tag{YM86}
$$

The first limit has Dirichlet conditions at both $0$ and $C$; the second
has Dirichlet data at $C$ and the usual form condition at infinity. More
explicitly, the limiting form domains are
$H_0^1(0,C)\cap L^2((0,C),y^2dy)$ and
$\{u\in H^1(C,\infty):u(C)=0,\ yu\in L^2(C,\infty)\}$.
Min--max convergence gives, for ordered eigenvalues $\mu_j(C)$ and the
tail bottom $\nu_0(C)$,

$$
\frac{\lambda_j(A_N)}{\sqrt{x}}\longrightarrow\mu_j(C),\qquad
\mu_j(C)>4j+3,\qquad
\nu_0(C):=\inf\sigma(H_{\mathrm{osc}}^{(C,\infty)})\geq C^2,\qquad
\frac{\inf\sigma(D_N)}{\sqrt{x}}\longrightarrow\nu_0(C).
\tag{YM87}
$$

The inequality for $\mu_j(C)$ is the min--max comparison with the
half-line oscillator. Equality would require the same-index half-line
eigenfunction to satisfy the extra Dirichlet condition at $C$; Sturm
oscillation and uniqueness rule that out. The bound on $\nu_0(C)$ follows
from $y^2\geq C^2$ on the tail.

#### 9.18.7 Fixed-window isolation and the bare-tail condition

Take the frozen low window $J=2$, the margin
$\delta_{\mathrm{iso}}=1$, and $C_J=4$. Since
$C_J^2=16>4J+3+2\delta_{\mathrm{iso}}=13$, set

$$
N_{\mathrm{iso}}=\left\lceil4x^{1/4}\right\rceil,\qquad
\frac{\lambda_J(h_x)}{\sqrt{x}}\longrightarrow11,\qquad
\frac{k_{N_{\mathrm{iso}}+1}}{\sqrt{x}}\longrightarrow16,\qquad
\frac{\inf\sigma(D_{N_{\mathrm{iso}}})}{\sqrt{x}}
\longrightarrow\nu_0(4)\geq16.
\tag{YM88}
$$

Consequently, for all sufficiently large $x$,

$$
\lambda_J(h_x)
<k_{N_{\mathrm{iso}}+1}-\delta_{\mathrm{iso}}\sqrt{x}
\leq\inf\sigma(D_{N_{\mathrm{iso}}})
-\delta_{\mathrm{iso}}\sqrt{x}.
\tag{YM89}
$$

Every eigenvalue $\lambda_j(h_x)$ with $0\leq j\leq J$ therefore lies
below the first discarded eigenvalue by a fixed $O(\sqrt{x})$ margin. The
Weyl function has no tail pole in this fixed window, and (YM63)--(YM65)
recover each low eigenpair exactly through the Feshbach pencil, including
the full self-energy. This is exact spectral isolation; it does not assert
that the bare matrix $A_{N_{\mathrm{iso}}}$ has the half-line spectrum.

The distinction follows from (YM86)--(YM87). If
$N/x^{1/4}\to C<\infty$, the bare matrix converges to the finite-interval
oscillator and retains the nonzero boundary error $\mu_j(C)-(4j+3)$.
If $N=o(x^{1/4})$, (YM83) gives
$\lambda_0(A_N)/\sqrt{x}\to\infty$. Recovery of the half-line values in
the natural $\sqrt{x}$-scaled problem, together with vanishing discarded
probability for every fixed low eigenstate, requires the expanding endpoint

$$
\boxed{
\frac{N}{x^{1/4}}\longrightarrow\infty,
\qquad\text{equivalently}\qquad
gN\longrightarrow\infty.
}
\tag{YM90}
$$

For this condition, the finite-interval forms exhaust the half-line form
domain, $\mu_j(C_x)\to4j+3$ as $C_x=N/x^{1/4}\to\infty$, and the
oscillator tail beyond $C_x$ has vanishing probability.
The frozen choices $N_{\mathrm{fixed}}=8$,
$N_C=\lceil2x^{1/4}\rceil$,
$N_{\mathrm{iso}}=\lceil4x^{1/4}\rceil$,
$N_{\mathrm{grow}}=\lceil x^{1/4}\log(2+x)\rceil$, and
$N_{1/2}=\lceil2\sqrt{x}\rceil$ consequently classify as follows:
$N_{\mathrm{fixed}}$ and $N_C$ have bounded ratios and fail bare
convergence; $N_{\mathrm{iso}}$ supplies fixed-window exact isolation;
and $N_{\mathrm{grow}}$ and $N_{1/2}$ satisfy (YM90).

#### 9.18.8 Scope of the result

Equations (YM57)--(YM90) concern one finite regulated isolated square in the
continuous-$SU(2)$ class-function sector. They do not construct a full
interacting $2\times2$ fibre, transport neighboring-plaquette or boundary
representation sectors, or provide volume-uniform resolvent estimates. They
also do not establish a thermodynamic limit, a continuum quantum field, a
Yang--Mills mass gap, or a microscopic Cassi identification. Finite-group
quadrature can serve as a numerical control of the continuous formulas, but
it cannot replace the domain, form, or resolvent arguments. The only physical
spacing identified here, $2\sqrt2/a$, is the isolated ultraviolet
plaquette normalization in (YM81).

### 9.19 Fundamental-boundary gauge fibre of the refined square

The fibre requirement in (YM54)–(YM55) contains a finite
representation-support problem before any magnetic amplitude or resolvent
estimate enters. For the open $2\times2$ graph in §9.17.2, fix all eight
boundary links in the fundamental representation. Write $V_n$ for the
irreducible $SU(2)$ representation of spin $n/2$ and dimension $n+1$. The
Clebsch–Gordan rule is

$$
V_m\otimes V_n
=\bigoplus_{\substack{r=|m-n|\\r\equiv m+n\ ({\rm mod}\ 2)}}^{m+n}V_r.
\tag{YM91}
$$

The four corner intertwiners are unique. Let
$s_{\mathrm N},s_{\mathrm E},s_{\mathrm S},s_{\mathrm W}$ denote the
integer labels on the four links from the boundary midpoints to the centre.
Since $SU(2)$ representations are self-dual, gauge invariance at each
midpoint gives

$$
b(s):=\dim\operatorname{Inv}(V_1\otimes V_1\otimes V_s)
=
\begin{cases}
1,&s\in\{0,2\},\\
0,&s\notin\{0,2\}.
\end{cases}
\tag{YM92}
$$

Resolve the four-valent central intertwiner by pairing
$(\mathrm N,\mathrm E)$ and $(\mathrm S,\mathrm W)$. If
$N_{mn}^{r}\in\{0,1\}$ is the multiplicity of $V_r$ in (YM91), the central
singlet multiplicity is

$$
d(\mathbf s)
:=\dim\operatorname{Inv}
\left(
V_{s_{\mathrm N}}\otimes V_{s_{\mathrm E}}
\otimes V_{s_{\mathrm S}}\otimes V_{s_{\mathrm W}}
\right)
=\sum_{r\geq0}
N_{s_{\mathrm N}s_{\mathrm E}}^{r}
N_{s_{\mathrm S}s_{\mathrm W}}^{r}.
\tag{YM93}
$$

The pairing selects a basis coordinate and leaves the dimension invariant.
Let $k$ be the number of spokes with label $2$. Equations (YM91)–(YM93)
give the complete fixed-boundary count:

| $k$ | spoke-label choices | $d(\mathbf s)$ per choice | fibre states | $K_\partial$ |
|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | 1 | 6 |
| 1 | 4 | 0 | 0 | 8, inadmissible |
| 2 | 6 | 1 | 6 | 10 |
| 3 | 4 | 1 | 4 | 12 |
| 4 | 1 | 3 | 3 | 14 |

For $k=4$, the common recoupling label is $r=0,2,$ or $4$, producing the
three intertwiners. Every two-spoke configuration has one common channel, as
does every three-spoke configuration. Consequently,

$$
\boxed{\dim\mathcal H_{\partial,\,j_{\max}\geq1}=1+6+4+3=14.}
\tag{YM94}
$$

Here the cutoff refers to the four internal spokes. The fixed boundary
condition excludes every spoke label above $2$, so increasing the internal
cutoff beyond $j_{\max}=1$ adds no state to this fibre. At
$j_{\max}=1/2$, only the all-zero-spoke state remains.

The dimensionless electric Casimir on these twelve graph links is

$$
K_\partial(\mathbf s)
=8\frac34+\sum_{i\in\{\mathrm N,\mathrm E,\mathrm S,\mathrm W\}}
\frac{s_i(s_i+2)}4
=6+2k.
\tag{YM95}
$$

The first gauge-admissible internal excitation therefore has the conditional
electric-only spacing

$$
\Delta E_{\mathrm{el},\partial}
=\frac{g^2}{2a}(10-6)
=\frac{2g^2}{a}.
\tag{YM96}
$$

This spacing belongs to a fixed nonvacuum boundary-representation fibre and
vanishes at weak bare coupling. It supplies no continuum mass lower bound.

#### 9.19.1 Field-owned support calculation

A September 2026 CassiFI run encoded (YM92)–(YM93) as exactly-one and
incompatibility clauses in one `ClauseFieldState` tensor per fixed query.
The source-declared cutoffs $n_{\max}=1,2,4$ generated respectively
$3$, $80$, and $144$ spoke-channel candidates, for $227$ fixed candidate
classifications. Every reported status matched the algebraic support above.
Direct clause evaluation checked each reported SAT assignment. A
left-associated tensor-product recurrence in the same implementation
accumulated the same $SU(2)$ fusion rule and matched the paired-channel
multiplicity configuration by configuration.

The source-declared one-active-spoke query returned `UNSAT`; the adjacent
two-active-spoke query returned `SAT` with a directly checked assignment.
Representative terminal tensors survived an exact descriptor round trip.
The schedule used no host-adaptive search, learned side table, or model call.
The receipt contains no source-independent reconstruction or global audit of
the `UNSAT` derivations. Its role is an implementation check and a measured
demonstration of field-owned finite gauge-support search. Equations
(YM91)–(YM94) carry the mathematical count.

#### 9.19.2 Dynamical boundary and next operator

Let $P_\partial$ project onto the fixed fundamental-boundary sector above and
$Q_\partial=I-P_\partial$. Fundamental plaquette multiplication on any
boundary link uses
$V_1\otimes V_1=V_0\oplus V_2$. It therefore transports the boundary label
$1$ into the $0$ and $2$ sectors. On the refined graph,

$$
Q_\partial W_pP_\partial\neq0
\tag{YM97}
$$

for a boundary-touching elementary plaquette $p$. The 14-state fibre gives a
finite representation basis for $P_\partial(H-z)P_\partial$. For
$z\in\rho(Q_\partial H Q_\partial)$, the exact reduction contains

$$
\mathcal F_\partial(z)
:=P_\partial(H-z)P_\partial
-P_\partial H Q_\partial
\left[Q_\partial(H-z)Q_\partial\right]^{-1}
Q_\partial H P_\partial.
\tag{YM98}
$$

The next interacting-block calculation must therefore include the boundary
sectors reached by plaquette multiplication, evaluate the Clebsch–Gordan and
$6j$ amplitudes, and control the resulting self-energy uniformly in volume,
cutoff, and the continuum scaling $g=g(a)$. Field-owned exact search can
enumerate this representation support and reject incompatible channels. The
matrix amplitudes, operator domains, and uniform inequalities remain separate
analytical obligations.

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
| Pure-gauge loop coordinates (YM1)–(YM2) | **Derived** | Supplied $SU(2)$ quantum gauge framework; carrier identification remains open |
| Electric closed-loop gap (YM6) | **Derived** within established lattice theory | Fixed $g,a$, source-free Gauss law and girth-four graph |
| Autonomous projector-only Yang–Mills Hamiltonian | **Excluded** by (YM4)–(YM5) | Wilson energy varies on projective fibres |
| Full interacting finite-box gap | **Derived** within established lattice theory | Compact configuration space; its argument supplies no uniform estimate |
| Volume-uniform interacting strong-coupling gap (YM19) | **Derived** by application of an established stability theorem | Sufficient local smallness (YM18); theorem constants unevaluated |
| Finite-depth gauge-invariant vacuum dressing (YM24)–(YM26) | **Derived** regulated operator identities and local bounds | Full holonomies and exact remainder retained; weak-coupling control absent |
| Exact vacuum-measure gap identity (YM27)–(YM28) | **Derived** within each finite regulated theory | Continuum construction and cutoff-uniform estimates remain open |
| Conditional full-holonomy block bound (YM29)–(YM31) | **Derived conditional** | Exact-vacuum fibre rates, boundary-uniform density comparison and tensorization are required |
| Equal-weight one-plaquette exponential vacuum | **Excluded** for every $x>0$ by (YM34) | Richer loop functionals remain available |
| Gaussian conditional-gap-only implication | **Excluded** by (YM37)–(YM38) | Exact quadratic control; no interacting-vacuum estimate |
| Static pure configuration-marginal blocking | **Excluded** as an exact quantum reduction by (YM39)–(YM41) | Mixed reduced states or energy-dependent resolvents retain the missing data |
| Exact path-holonomy pullback (YM42)–(YM48) | **Derived** regulated kinematic identities | Edge-simple disjoint paths, normalized Haar measure and compatible endpoint gauge action |
| Bare cylindrical full-Hamiltonian block map | **Excluded** on the fixed $2\times2$ refinement by (YM49)–(YM53) | Interacting fibres or energy-dependent reductions must retain discarded plaquette information |
| Fixed fundamental-boundary internal Gauss fibre (YM91)–(YM96) | **Derived** within established $SU(2)$ representation theory | Exactly 14 states for $j_{\max}\geq1$; Wilson multiplication exits the fixed boundary sector |
| Continuum Yang–Mills existence and mass gap | **Open** | Vacuum-subtracted uniform control and continuum construction |

The completion ansatz in
`foundations/geometric-manifold-completion.md` identifies the species Gram
matrix with the positive Hermitian fibre of one stratified bundle. Its
normalized section is the Bloch ball, the rank-one stratum is the projective
shell, and the affine bubble map has the same normalized pullback metric. The
minimal positivity-preserving two-jump conversion lift extends the diagonal
population law with the conditional coherence rate
$\gamma_c=\gamma_\varepsilon/2$. With state-dependent $q$, the complete lift
is nonlinear; its trajectories reparametrize a fixed linear GKSL flow. The
rate and the associated finite-density coherence-support boundary are specific
to that lift and do not follow from the loop projection alone. See
`foundations/yin-yang-qi-dynamical-geometry.md` §§5–7.

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

The separate pure-gauge schedule is
`computations/yang-mills-loop-gap-prereg.md`. Its primary and independent
implementations are `computations/verify_yang_mills_loop_gap.py` and
`computations/verify_yang_mills_loop_gap_independent.py`. They test group
identities, projective information loss, finite spin-network accounting,
the radial quadratic form and the character/Mathieu square spectra.
The graph theorem and infinite-dimensional domain statements require the
analytical arguments in §§9.4–9.9; a finite matrix calculation cannot establish
the continuum claim.

The qualified receipts in
`runs/yang_mills_loop_gap/prufer_recovery/` pass **66 primary checks** and
**11 independent qualification checks**. The three graph fixtures have
$3,11,1013$ admissible spin labelings, respectively, and electric gap $3$
in units $g^2/(2a)$. All 24 independent energy/gap comparisons pass; the
maximum normalized discrepancy is $3.44777127772\times10^{-12}$ against
$10^{-8}$. The $64$-versus-$128$ character-cutoff discrepancy is at most
$3.71888228001\times10^{-13}$, and the radial quadratic-form discrepancy
is at most $6.22335148571\times10^{-14}$.

The independent evaluator solves the same Mathieu/Dirichlet problem by
two-sided Prüfer-phase shooting. The retained
`runs/yang_mills_loop_gap/independent.json` records a failed direct
special-function evaluation at $g=1/8$: its first three energies are
misordered and its gap is negative. That receipt is unqualified.
The accepted computation retains every coupling, cutoff and threshold;
all primary scientific controls are unchanged. Source identities, raw
receipt hashes and classifications are in
`runs/yang_mills_loop_gap/reconciliation.json`. The outcome is
**SUPPORTS** for the regulated electric and square controls,
**CONTRADICTS** for autonomous projector-only Hamiltonian closure, and
**UNRESOLVED** for the weak-bare-coupling uniform estimate and continuum construction.

The connected-block schedule in
`computations/yang-mills-connected-block-prereg.md` is implemented by
`computations/verify_yang_mills_connected_blocks.py`. It passes **79 checks**:
the periodic lattices of side $4,6,8$ have $192,648,1536$ links and the same
24 disjoint-link plaquette layers. The 21 local matrix cases use sizes
$3,5,8$ and the seven fixed values of $x$. Their maximum absolute identity
discrepancy is $4.97379915032\times10^{-14}$ against $10^{-11}$.
The largest measured $\|R_\square(x)\|/x^2$ is $0.539326266409$,
below the exact coefficient $(2+\sqrt2)/3=1.13807118746$.

A separate raw-artifact reconciliation passes **31 checks**, including
source/snapshot SHA-256 bindings, complete geometry inventories and direct
JavaScript reconstruction of every local rotation and transformed matrix.
Its maximum matrix discrepancy is $4.44089209850\times10^{-16}$; a separate
three-dimensional Jacobi calculation reproduces the remainder norms within
$3.46944695195\times10^{-18}$. The receipt, source manifest and frozen
source bytes are in `runs/yang_mills_connected_blocks/verification.json`,
`runs/yang_mills_connected_blocks/verification.inputs.json` and
`runs/yang_mills_connected_blocks/verification.sources/`.

The finite geometry and operator controls classify **SUPPORTS**.
The volume-uniform strong-coupling gap and exact finite-depth dressing
classify **ADOPT** through the analytical arguments in §§9.10–9.12 and
the two reconciled mathematical reviews. Their classification is separate
from the finite matrix checks. The local `reconcile.mjs` and
`reconciliation.json` in the same run directory bind the raw reviews,
receipt and audit source. Weak-bare-coupling uniform control, continuum
construction, continuum mass and Cassi microscopic identification remain
**UNRESOLVED**.

The exact-vacuum block schedule in
`computations/yang-mills-vacuum-block-prereg.md` is implemented by
`computations/verify_yang_mills_vacuum_blocks.py`. Its immutable primary
receipt passes **305 checks** over five full-holonomy fixtures, 45 local-energy
rows and ten connected Gaussian rows. The maximum group-identity,
gauge-invariance, first-derivative, normalized local-energy and Gaussian
square-root errors are respectively
$1.33226762955\times10^{-15}$,
$4.44089209850\times10^{-16}$,
$6.30606677987\times10^{-13}$,
$3.27656206611\times10^{-8}$ and
$9.27383170257\times10^{-15}$.

The final independent JavaScript reconciliation passes **120 checks**. Its
maximum full-holonomy reconstruction, exact local-row, finite-difference
derivative, normalized local-energy, Gaussian-matrix and Gaussian-scalar
discrepancies are respectively
$3.55271367880\times10^{-15}$,
$2.84217094304\times10^{-14}$,
$5.35738120533\times10^{-13}$,
$1.66022970927\times10^{-8}$,
$1.77080572428\times10^{-14}$ and
$9.76996261670\times10^{-13}$. The primary receipt, input manifest, frozen
sources, two analytical reviews and reconciliation chain are in
`runs/yang_mills_vacuum_blocks/`. Its `publication.json` seals the current
theorem, fixed protocol, bound verifier, independent checker and receipt
hashes without rerunning the scientific schedule. The initial
`reconciliation.json`, `reconciliation_recovery.json`,
`reconciliation_recovery2.json` and `reconciliation_recovery3.json` remain as
failed audit implementations; the qualified source and receipt are
`reconcile_recovery4.mjs` and `reconciliation_recovery4.json`.

The finite group, derivative and Gaussian controls classify **SUPPORTS**.
The exact vacuum-measure identity classifies **ADOPT** within each finite
regulator, and the weighted full-holonomy block estimate classifies
**ADOPT CONDITIONAL** on its displayed exact-vacuum rates, tensorization and
cover hypotheses. The equal-weight one-plaquette vacuum, a
conditional-gap-only volume-uniform implication and a static pure
configuration marginal as an exact quantum block each classify
**CONTRADICTS**. Interacting-vacuum tensorization, weak-bare-coupling uniform
control, the continuum quantum field and its mass remain **UNRESOLVED**.

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
- `foundations/geometric-manifold-completion.md`—positive coherence fibre,
  metric compatibility, two-rail scale graph, and exact diagonal reduction
- `computations/loop-to-bubble-projection-pre-registration.md`—frozen gates
- `computations/verify_loop_to_bubble_projection.py`—independent certificate
- J. Kogut and L. Susskind, [Hamiltonian formulation of Wilson's lattice gauge theories](https://doi.org/10.1103/PhysRevD.11.395)—Hamiltonian gauge framework
- A. Ashtekar and J. Lewandowski, [Differential geometry on the space of
  connections via graphs and projective limits](https://arxiv.org/abs/hep-th/9412073),
  §§3.2–3.4—consistent graph projections and normalized Haar cylinder measures
- W. Donnelly, [Decomposition of entanglement entropy in lattice gauge
  theory](https://arxiv.org/abs/1109.0036), §§II–III—Haar-isometric link
  splitting and boundary gauge sectors
- J. A. Zapata, [Local gauge theory and coarse
  graining](https://arxiv.org/abs/1203.2306)—macroscopic holonomy data and
  microscopic information under gauge coarse graining
- C. W. Bauer, I. D'Andrea, M. Freytsis and D. M. Grabowska, [A new basis for Hamiltonian SU(2) simulations](https://arxiv.org/abs/2307.11829), §§II–IV and Appendix B—normalization, gauge reduction and physical square spectrum
- NIST Digital Library of Mathematical Functions, [§28.8, Mathieu large-parameter asymptotics](https://dlmf.nist.gov/28.8)—fixed-level characteristic-value asymptotics
- A. Jaffe and E. Witten, [Quantum Yang–Mills Theory](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), §4—continuum existence and mass-gap requirements
- D. A. Yarotsky, [Ground states in relatively bounded quantum perturbations of classical lattice systems](https://arxiv.org/abs/math-ph/0412040), Theorems 1–2 and Remark Eq. (6)—volume-uniform strong-coupling stability, connected correlations and relatively bounded perturbations
- `computations/yang-mills-connected-block-prereg.md`—fixed connected-block geometry and local operator schedule
- `computations/verify_yang_mills_connected_blocks.py`—connected-block controls and immutable source-bound receipt
- `computations/yang-mills-vacuum-block-prereg.md`—fixed vacuum geometry,
  Gaussian block and RG-sign controls
- `computations/verify_yang_mills_vacuum_blocks.py`—source-bound finite
  group, derivative and Gaussian controls
- S. Janson, *Gaussian Hilbert Spaces*, Cambridge University Press
  (1997)—Wiener chaos and conditional Gaussian factorization
- M. Griesemer and D. Hasler, [On the Smooth Feshbach–Schur
  Map](https://arxiv.org/abs/0704.3244)—spectral reduction conditions
