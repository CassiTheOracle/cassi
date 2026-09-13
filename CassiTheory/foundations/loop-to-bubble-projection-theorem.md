# Loop-to-Bubble Projection Theorem: Shared-Support Counterflow, Coherence, and Scale Separation

## Status: Derived conditional projection and population spectrum; Derived regulated pure-gauge identities, exact isolated-square radial Feshbach transfer and weak-coupling cutoff theorem, exact character-cutoff form theorem on every fixed finite graph, volume-uniform local character-cutoff density theorem with an exact global-norm obstruction, conditional fixed-regulator thermodynamic ground-state subsequence, exact fixed-boundary gauge-fibre support, exact two-scale and $H^{-1}$ transport-score vacuum-measure recurrences, exact residual-recovery Gramian and score-penalty separation, exact tree-exterior boundary independence and the nodal Ritz obstruction for the finite cut-off block with its schedule-wide confinement along block paths, conditional block theorems, and exact bare-cylindrical refinement obstruction; Recovered finite $3\times2\times2$ $SU(2)$ Hamiltonian construction with frozen separation-based tail qualifications inconclusive; Hypothesized microscopic physical identification—September 2026

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

The pure-gauge comparison in §§9.4–9.27 retains full $SU(2)$ loop holonomies.
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
the full Kogut–Susskind Hamiltonian. The continuous-$SU(2)$ isolated square
admits an exact operator-domain Feshbach reduction. Its weak-coupling
character scale is $n=O(x^{1/4})$; a fixed scaled endpoint isolates any fixed
low-energy window through the exact self-energy, while bare spectral
convergence and vanishing discarded mass hold exactly when
$N/x^{1/4}\to\infty$. With all eight outer links fixed in the fundamental
representation, exact Clebsch–Gordan constraints reduce the internal Gauss
fibre to 14 states once $j_{\max}\geq1$; Wilson multiplication changes the
outer representation sector, so this fibre is not dynamically closed.

For an exact factor-two path block, the product Casimir metric has an
orthogonal horizontal/vertical splitting with electric coefficients $2$ and
$1/2$. Disintegration of the true vacuum along this connection gives an exact
conditional-score recurrence for the all-function fine Poincaré rate, which
lower-bounds the gauge-invariant physical rate. Its inputs are the
coarse-marginal rate, the conditional fibre rate and the transported
coarse–fibre score covariance. In the zero-score limit it reduces to
$\lambda_f\geq\min\{2\lambda_c,\lambda_{\mathrm{fib}}/2\}$. With nonzero score, preservation
of a fixed physical mass requires a strict coarse-rate margin. The score
retains every interaction generated by exact marginalization. The
conditional Poisson inverse measures it in the weaker $H^{-1}$ norm
$\vartheta$, replacing $\kappa/\sqrt{\lambda_{\mathrm{fib}}}$ in the
recurrence and yielding an exact
relative-margin budget: nonzero transport cost consumes both coarse and
vertical gap margin. A strict Gaussian fixture improves the squared score
coefficient by a factor of nine, while the massless weak-field chain retains
a vanishing coarse mode and produces no gap. The residual-recovery Gramian on
centered physical functions identifies
$A_{\mathrm{AT}}^{\mathrm{opt}}=\gamma_{\mathrm{rec}}^{-1}$ and gives
$\lambda_{\mathrm{gi}}\geq\gamma_{\mathrm{rec}}\lambda_{\mathrm{loc}}/\rho$
under the declared conditional and cover estimates. The transported-score
Gramian is a distinct upper penalty on coarse tangent directions. At finite
level, an explicitly defined triangular transport operator packages the
conditional shell estimates into one operator norm; a weighted Schur
row-and-column bound is sufficient for scale-uniform control. Product,
near-parallel and Gaussian controls show that a score kernel can contain a
physical direction and that exact finite-regulator rigidity can coexist with
a recovery floor tending to zero. The 58-check primary and 30-check
independent reconstructions pass. Uniform recovery, shell-rate and
score-transport bounds for the exact interacting vacuum, the four-dimensional
continuum construction and microscopic Cassi identification remain open.

On periodic cubic lattices, the normalized ground-space density has electric
energy at most $2x$ per link. A cutoff on any fixed finite link support
therefore has discarded mass at most $2x|S|/\kappa_C$, uniformly in spatial
volume. The induced local-observable error vanishes as $C\to\infty$ at fixed
$(x,S)$, and also along auxiliary schedules with $C(x)^2/x\to\infty$. A
gauge-invariant product family on edge-disjoint loops has bounded electric
energy density while its discarded whole-wavefunction norm tends to one at
every fixed cutoff. The local bound makes each fixed-support family of
reduced ground densities trace-norm precompact. Conditional on the
finite-volume ground densities and that analytic bound, a diagonal
subsequence defines a compatible, symmetry-invariant locally normal state
whose finite-character local observables satisfy the algebraic ground-state
inequality. The construction selects a subsequence at fixed regulator and
coupling. Full-sequence convergence, uniqueness, clustering, a uniform gap
and the continuum theory remain open.

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

#### 9.14.1 Fixed-regulator Haar comparison

At each fixed finite regulator, the exact conditional rate has a direct
positive lower bound. Let

$$
\omega_-:=\min_{U}\Omega_{a,L}(U)>0,
\qquad
\omega_+:=\max_{U}\Omega_{a,L}(U)<\infty.
\tag{YM31a}
$$

For a block $B$ and exterior value $\eta$, write the conditional density
relative to normalized product Haar measure $\nu_B$ as

$$
d\mu_B^\eta=p_\eta\,d\nu_B,
\qquad
p_\eta(U_B)
:=
\frac{\Omega_{a,L}(U_B,\eta)^2}{Z_\eta}.
\tag{YM31b}
$$

Then

$$
\frac{\omega_-^2}{Z_\eta}
\leq p_\eta(U_B)
\leq
\frac{\omega_+^2}{Z_\eta},
\qquad
\frac{\sup p_\eta}{\inf p_\eta}
\leq
\left(\frac{\omega_+}{\omega_-}\right)^2.
\tag{YM31c}
$$

If $\lambda_{\mathrm{Haar},B}$ is the product-Haar Poincare rate for the
block Dirichlet form, Haar Poincare and the two density bounds give

$$
\begin{aligned}
\operatorname{Var}_{\mu_B^\eta}F
&\leq
\sup(p_\eta)\operatorname{Var}_{\nu_B}F\\
&\leq
\frac{\sup(p_\eta)}{\lambda_{\mathrm{Haar},B}\inf(p_\eta)}
\sum_{e\in B,A}\int|X_e^AF|^2\,d\mu_B^\eta.
\end{aligned}
$$

Consequently,

$$
\boxed{
\lambda_B^\mu(\eta)
\geq
\lambda_{\mathrm{Haar},B}
\left(\frac{\omega_-}{\omega_+}\right)^2
}
\tag{YM31d}
$$

for every exterior value, and hence also on the gauge-invariant induced
fibre domain. With the present $SU(2)$ generator normalization,
$\lambda_{\mathrm{Haar},B}=3/4$ for a nonempty product block; for a compact
simple group it is the first nonzero Casimir in the selected metric.
The normalization factor $Z_\eta$ cancels, so this comparison is uniform in
the boundary at the fixed regulator.

The estimate makes the remaining issue explicit. The ratio
$\omega_-/\omega_+$ is a global exact-vacuum condition ratio; finite
positivity makes it nonzero, but no bound on it uniform in volume, block
size, weak coupling or refinement has been proved. Equation (YM31d) is
therefore a fixed-regulator realization of (YM29), not the missing
continuum estimate. It also leaves $A_{\mathrm{AT}}$ and the recovery floor
independent.

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


Put $\mathcal H_P:=P_N\mathcal H_\square$ and
$\mathcal H_Q:=Q_N\mathcal H_\square$. Since $\mathcal H_P$ is
finite-dimensional and $P_N$ removes only finitely many coordinates,

$$
D(h_x)=\mathcal H_P\oplus D(D_N),
\qquad
D(D_N)=Q_ND(K).
$$

Here $A_N$ is bounded self-adjoint on $\mathcal H_P$, while $D_N$ is
self-adjoint on $D(D_N)\subset\mathcal H_Q$. The $K$ and diagonal magnetic
terms have no $P_N$–$Q_N$ matrix element. Thus $V_N$, initially defined on
$D(D_N)$, extends to the displayed bounded rank-one map
$\mathcal H_Q\to\mathcal H_P$, with
$V_N^*=-x|N+1\rangle\langle N|$. The block operator in (YM62) is consequently
a closed map from $\mathcal H_P\oplus D(D_N)$ to
$\mathcal H_P\oplus\mathcal H_Q$.

For $z\in\rho(D_N)$, put $B_N(z)=D_N-z$ and
$
m_{N+1}(z):=\langle N+1|B_N(z)^{-1}|N+1\rangle .
$
Regard $B_N(z)$ as a bijection
$D(D_N)\to\mathcal H_Q$. Its inverse is bounded both
$\mathcal H_Q\to\mathcal H_Q$ and
$\mathcal H_Q\to D(D_N)$ when the latter carries its graph norm. Hence
$V_NB_N(z)^{-1}$ and $B_N(z)^{-1}V_N^*$ are bounded between their indicated
Hilbert spaces. Both triangular factors below are boundedly invertible and
preserve $\mathcal H_P\oplus D(D_N)$. Direct multiplication on this common
domain gives the block Gaussian factorization

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

The factorization and invertibility of its triangular factors, together with
$B_N(z)^{-1}$, show that $h_x-z$ has a bounded inverse precisely when
$F_N(z)$ is invertible. Thus (YM64) holds for every $z\in\rho(D_N)$.

$$
z\in\sigma(h_x)
\quad\Longleftrightarrow\quad
0\in\sigma(F_N(z)),
\qquad z\in\rho(D_N).
\tag{YM64}
$$

For the kernel correspondence write $\psi=p+q$, with
$p\in\mathcal H_P$ and $q\in D(D_N)$. The second block equation gives

$$
B_N(z)q=-V_N^*p,
\qquad
q=-B_N(z)^{-1}V_N^*p.
$$

Substitution in the first block equation gives $F_N(z)p=0$. Conversely,
the displayed $q$ belongs to $D(D_N)$ for every $p\in\ker F_N(z)$.
Consequently

$$
J_z:p\longmapsto p-B_N(z)^{-1}V_N^*p
$$

is a linear bijection
$\ker F_N(z)\to\ker(h_x-z)$ and yields

$$
Q_N\psi
=-(D_N-z)^{-1}V_N^*p
=x\,p_N(D_N-z)^{-1}|N+1\rangle,
\qquad p_N=\langle N|p\rangle.
\tag{YM65}
$$

The multiplicity statement for the present self-adjoint operator is completed
after (YM69), where the derivative of the pencil is available.

For $n\geq0$, let
$\mathcal H_n=\ell^2(\{n,n+1,\ldots\})$ and let $D^{(n)}$ be the
self-adjoint tail operator on

$$
D(D^{(n)})=
\left\{f\in\mathcal H_n:
\sum_{j=n}^{\infty}k_j^2|f_j|^2<\infty\right\},
$$

with the Dirichlet value $f_{n-1}=0$. Define
$m_n(z)=\langle n|(D^{(n)}-z)^{-1}|n\rangle$ only for
$z\in\rho(D^{(n)})$, and put $d_n=k_n+2x$. The one-step Schur elimination
requires
$z\in\rho(D^{(n)})\cap\rho(D^{(n+1)})$. The complete continued fraction is
defined on

$$
\Omega_n:=\bigcap_{j\geq n}\rho(D^{(j)}),
$$

which contains $\mathbb C\setminus\mathbb R$ and
$(-\infty,\inf\sigma(D^{(n)}))$. On this common-resolvent set, decomposing
$\mathcal H_n=\mathbb C|n\rangle\oplus\mathcal H_{n+1}$ gives

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

Fix $x>0$ and $n$. For $M\geq n$, let
$\mathcal E_{n,M}=\operatorname{span}\{|n\rangle,\ldots,|M\rangle\}$
inside $\mathcal H_n$, let $\iota_{n,M}$ be zero extension, and set
$D_{n,M}=\iota_{n,M}^*D^{(n)}\iota_{n,M}$. Its quadratic form is the
restriction of

$$
\begin{aligned}
\mathfrak q_n[f]
&=\sum_{j=n}^{\infty}k_j|f_j|^2
+x\left(
|f_n|^2+\sum_{j=n}^{\infty}|f_{j+1}-f_j|^2
\right),\\
Q(\mathfrak q_n)
&=\left\{f\in\mathcal H_n:
\sum_{j=n}^{\infty}k_j|f_j|^2<\infty\right\}.
\end{aligned}
$$

On $\mathcal E_{n,M}$ the same formula has $f_{M+1}=0$. Finite sequences
form a core for $\mathfrak q_n$: coordinate truncation converges in the
weighted diagonal form because $k_j\to\infty$, and the discrete-Laplacian
form is bounded by $4\|f\|^2$. The increasing Galerkin forms therefore give

$$
\iota_{n,M}(D_{n,M}-z)^{-1}\iota_{n,M}^*
\xrightarrow[M\to\infty]{\mathrm{SOT}}
(D^{(n)}-z)^{-1}
$$

for every fixed $z\in\mathbb C\setminus\mathbb R$. At a real
$z\in\rho(D^{(n)})$, min–max convergence of the discrete eigenvalues gives
eventual spectral separation and the same strong-resolvent limit. In
particular, it holds throughout the real interval below the tail bottom.
Taking the boundary matrix element proves
$m_n^{(M)}(z)\to m_n(z)$ wherever the displayed finite resolvents exist.
Expansion along the first row gives the recurrence and terminal values in
(YM67), while Cramer's rule gives its quotient only when
$\Delta_{n,M}(z)\ne0$.

For the finite full operator, take $M\geq N+1$, put
$h_x^{(M)}=P_Mh_xP_M$, and let $D_N^{(M)}$ be its restriction to
$N+1,\ldots,M$. For $z\in\rho(D_N^{(M)})$ define $F_N^{(M)}(z)$ by the
same Schur formula. The finite block factorization gives the determinant
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

For completeness, if $\nu_{N+1}$ is the spectral probability measure of
$D_N$ at $|N+1\rangle$, the integrands in (YM69) are uniformly dominated
on a neighborhood of every real $E\in\rho(D_N)$. Differentiation under the
spectral integral is therefore valid. In particular,

$$
m_{N+1}'(E)
=\langle N+1|(D_N-E)^{-2}|N+1\rangle>0.
$$

Now let $E\in\sigma(h_x)\cap\rho(D_N)$. Compact resolvent makes $E$ an
isolated eigenvalue, and self-adjointness makes its algebraic and geometric
multiplicities equal. The finite pencil is Hermitian at $E$, with

$$
F_N'(E)
=-I_{\mathcal H_P}
-x^2m_{N+1}'(E)|N\rangle\langle N|<0.
$$

Put $\mathcal K_E=\ker F_N(E)$ and decompose
$\mathcal H_P=\mathcal K_E\oplus\mathcal K_E^\perp$. The
$\mathcal K_E^\perp$ block of $F_N(E)$ is invertible and the off-diagonal
blocks vanish. Its Schur complement at $E+t$ is
$-tG+O(t^2)$, where

$$
G=
P_{\mathcal K_E}\bigl[-F_N'(E)\bigr]P_{\mathcal K_E}
\big|_{\mathcal K_E}>0.
$$

It follows that
$\det F_N(E+t)=c\,t^{\dim\mathcal K_E}
+O(t^{\dim\mathcal K_E+1})$ with $c\ne0$. Together with the kernel
bijection, this proves

$$
\operatorname{ord}_E\det F_N
=\dim\ker F_N(E)
=\dim\ker(h_x-E),
$$

the algebraic multiplicity of $E$.


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

The lower bound in (YM70) is Jensen's inequality for $t\mapsto t^{-1}$
applied to the spectral measure of $B_N(E)$ at $|r\rangle$:
$\int t^{-1}d\nu(t)\geq(\int t\,d\nu(t))^{-1}$. For the upper bound,
$k_n\geq k_r$ gives
$B_N(E)\geq\delta I+xL_+>0$. Inversion reverses the positive form order,
so $B_N(E)^{-1}\leq(\delta I+xL_+)^{-1}$. The boundary Green function of
this free comparison tail is

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

Both roots of the quadratic in (YM71) are positive. The operator definition
selects the displayed smaller root, equivalently the decaying Weyl branch
$0<xg_+<1$. Define
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

Writing $t=x^2|p_N|^2m_{N+1}'(E)$, (YM74) gives
$\|Q_N\psi\|^2=t$ and $\|\psi\|^2=1+t$ under the retained normalization
$\|p\|=1$. The corresponding unit full eigenvector
$\widehat\psi=\psi/\sqrt{1+t}$ has discarded probability $t/(1+t)$.
Thus the differentiated Weyl function gives both the tail norm and the full
normalization correction. In particular,
$\delta=o(x)$ forces $\Sigma_N(E)=\Theta(x)$, while
$\delta/x\to\infty$ gives $\Sigma_N(E)\sim x^2/\delta$. The exact
self-energy is consequently of the same order as the magnetic diagonal
term whenever the tail threshold approaches the low energy on a scale
smaller than $x$.

#### 9.18.4 Negative-axis resolvent estimates

Set $z=-\eta$ with $\eta>0$, $B_\eta=D_N+\eta$, and
$
S_\eta:=A_N+\eta P_N-V_NB_\eta^{-1}V_N^* .
$
Since $r=N+1\geq1$, $D_N\geq k_rI>0$ and $D_N^{-1}$ maps
$\mathcal H_Q$ boundedly into $D(D_N)$. For $p\in\mathcal H_P$, the vector
$(p,-D_N^{-1}V_N^*p)$ belongs to $D(h_x)$. Positivity of $h_x$ then gives

$$
A_N-V_ND_N^{-1}V_N^*\geq0.
$$

Functional calculus gives
$0\leq B_\eta^{-1}\leq D_N^{-1}$, and therefore

$$
S_\eta\geq\eta P_N,\qquad
\|S_\eta^{-1}\|\leq\eta^{-1},\qquad
\|(A_N+\eta P_N)^{-1}\|\leq\eta^{-1}.
$$

The domain-valid factorization at $z=-\eta$ now gives

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

Here is a fixed-level proof with the moving endpoint and remainder controlled.
Put $\varepsilon=x^{-1/4}$ and
$L_\varepsilon=\pi/\varepsilon$. The unitary map

$$
(U_\varepsilon f)(y)=\varepsilon^{1/2}f(\varepsilon y)
$$

sends $L^2(0,\pi)$ to $L^2(0,L_\varepsilon)$ and sends
$H_0^1(0,\pi)$ to $H_0^1(0,L_\varepsilon)$. Hence
$x^{-1/2}\widetilde h_x$ is unitarily equivalent to

$$
H_\varepsilon
=-\frac{d^2}{dy^2}+W_\varepsilon(y)-\varepsilon^2,
\qquad
W_\varepsilon(y)
=2\varepsilon^{-2}\bigl(1-\cos(\varepsilon y)\bigr)
$$

with Dirichlet data at $0$ and $L_\varepsilon$. On
$0\leq\varepsilon y\leq\pi$,

$$
\frac{4}{\pi^2}y^2\leq W_\varepsilon(y)\leq y^2,
\qquad
W_\varepsilon\longrightarrow y^2
\quad\text{locally uniformly}.
$$

Extend the form domain $H_0^1(0,L_\varepsilon)$ by zero into
$L^2(0,\infty)$. The lower bound gives uniform $H^1$ control and
$y^2$-tightness on every bounded-energy form sublevel. Weak lower
semicontinuity and local uniform convergence give the liminf inequality for

$$
H_0=-\frac{d^2}{dy^2}+y^2
\quad\text{on }L^2(0,\infty),\qquad u(0)=0,
$$

while every $C_c^\infty(0,\infty)$ function is eventually an exact recovery
test function. Compactness and the min–max principle therefore give, for
each fixed $j$,

$$
\mu_j(\varepsilon)
:=x^{-1/2}\lambda_j(h_x)
\longrightarrow E_j:=4j+3.
$$

The same compactness shows that the normalized eigenfunction converges in
$L^2$ to the simple Dirichlet half-line oscillator state $\phi_j$, up to a
phase. In particular, for a fixed interval
$I_j=(E_j-1,E_j+1)$, $H_\varepsilon$ has exactly one eigenvalue in $I_j$
for all sufficiently small $\varepsilon$. Otherwise two orthogonal
eigenvectors would have strongly convergent subsequences whose nonzero
orthogonal limits both solve $H_0u=E_ju$, contradicting simplicity.

It remains to control the first correction. Put

$$
V(y)=-1-\frac{y^4}{12},\qquad
c_j=\langle\phi_j,V\phi_j\rangle,
\qquad
R_j=(H_0-E_j)^{-1}(I-|\phi_j\rangle\langle\phi_j|),
$$

and

$$
\chi_j=-R_j(V-c_j)\phi_j,\qquad
w_{j,\varepsilon}=\phi_j+\varepsilon^2\chi_j.
$$

The reduced resolvent is bounded because the neighboring half-line
oscillator levels are separated by $4$. Multiplication by $y^4$ connects
only finitely many oscillator states, so $\chi_j$ is a polynomial times
$e^{-y^2/2}$, vanishes at $0$, and satisfies

$$
(H_0-E_j)\chi_j=-(V-c_j)\phi_j,\qquad
\langle\phi_j,\chi_j\rangle=0.
$$

Taylor's theorem with the sixth derivative bounded gives, throughout the
moving interval,

$$
r_\varepsilon(y)
:=W_\varepsilon(y)-y^2+\frac{\varepsilon^2y^4}{12},
\qquad
|r_\varepsilon(y)|
\leq\frac{\varepsilon^4y^6}{360}.
$$

For
$\nu_j(\varepsilon)=E_j+\varepsilon^2c_j$,
the cancellation equation for $\chi_j$ yields

$$
(H_\varepsilon-\nu_j)w_{j,\varepsilon}
=\varepsilon^4(V-c_j)\chi_j
+r_\varepsilon\phi_j
+\varepsilon^2r_\varepsilon\chi_j.
$$

Every term on the right has $L^2$ norm $O_j(\varepsilon^4)$. To impose the
far Dirichlet endpoint, choose a smooth $\eta_\varepsilon$ equal to $1$ on
$[0,L_\varepsilon-1]$, equal to $0$ at $L_\varepsilon$, and with its first
two derivatives bounded independently of $\varepsilon$. The cutoff
commutator is supported where the polynomial-Gaussian
$w_{j,\varepsilon}$ is $O_j(e^{-cL_\varepsilon^2})$. Thus

$$
\left\|
(H_\varepsilon-\nu_j)
\frac{\eta_\varepsilon w_{j,\varepsilon}}
{\|\eta_\varepsilon w_{j,\varepsilon}\|}
\right\|
\leq C_j\varepsilon^4.
$$

The spectral theorem places an eigenvalue within
$C_j\varepsilon^4$ of $\nu_j$, and the uniqueness in $I_j$ identifies it
as $\mu_j(\varepsilon)$. Hence

$$
\mu_j(\varepsilon)
=E_j+\varepsilon^2c_j+O_j(\varepsilon^4).
$$

The half-line state $\phi_j$ is the normalized restriction of the odd
full-line oscillator state of index $2j+1$. Ladder-operator evaluation gives

$$
\left\langle\phi_j,y^4\phi_j\right\rangle
=6j^2+9j+\frac{15}{4},\qquad
c_j=-1-\frac{1}{12}\left(6j^2+9j+\frac{15}{4}\right),
\qquad
\lambda_j(h_x)=(4j+3)\sqrt{x}+c_j+O_j(x^{-1/2}).
\tag{YM80}
$$

This establishes the expansion for every fixed $j$; the remainder constant
may depend on $j$.

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

Put $V_\varepsilon(y)=y^2+2\varepsilon y$,
$C_\varepsilon=\varepsilon N$, and
$r_\varepsilon=\varepsilon(N+1)=C_\varepsilon+\varepsilon$. Multiplying
(YM82) and (YM84) by $\varepsilon^2=x^{-1/2}$ gives the exact scaled
forms

$$
\begin{aligned}
\mathfrak q_\varepsilon^A[f]
&=\varepsilon\sum_{n=0}^{N}
V_\varepsilon(y_n)|u_n|^2\\
&\quad+\varepsilon^{-1}\left(
|u_0|^2+\sum_{n=0}^{N-1}|u_{n+1}-u_n|^2+|u_N|^2
\right),\\
\mathfrak q_\varepsilon^D[f]
&=\varepsilon\sum_{n=N+1}^{\infty}
V_\varepsilon(y_n)|u_n|^2\\
&\quad+\varepsilon^{-1}\left(
|u_{N+1}|^2+\sum_{n=N+1}^{\infty}|u_{n+1}-u_n|^2
\right).
\end{aligned}
$$

Use the fixed Hilbert space
$\mathcal H=L^2((0,\infty),dy)$. Define exact isometries by

$$
\begin{aligned}
(E_\varepsilon^Af)(y)
&=u_n &&(y\in[y_n,y_{n+1}),\ 0\leq n\leq N),\\
(E_\varepsilon^Df)(y)
&=u_n &&(y\in[y_n,y_{n+1}),\ n\geq N+1),
\end{aligned}
$$

and set each image to zero off the indicated cells. For compactness and
traces, let $L_\varepsilon^Af$ be linear through

$$
(0,0),(\varepsilon,u_0),(2\varepsilon,u_1),\ldots,
((N+1)\varepsilon,u_N),((N+2)\varepsilon,0)
$$

and zero above $(N+2)\varepsilon$. Let $L_\varepsilon^Df$ be linear through

$$
(C_\varepsilon,0),(r_\varepsilon,u_{N+1}),
(\varepsilon(N+2),u_{N+2}),\ldots .
$$

The one-cell shift between $E_\varepsilon^A$ and
$L_\varepsilon^A$ makes the left and right boundary penalties into genuine
interpolation edges. The derivative energies reproduce every difference
and boundary term:

$$
\begin{aligned}
\int_0^\infty |(L_\varepsilon^Af)'|^2dy
&=\varepsilon^{-1}\left(
|u_0|^2+\sum_{n=0}^{N-1}|u_{n+1}-u_n|^2+|u_N|^2
\right),\\
\int_0^\infty |(L_\varepsilon^Df)'|^2dy
&=\varepsilon^{-1}\left(
|u_{N+1}|^2+
\sum_{n=N+1}^{\infty}|u_{n+1}-u_n|^2
\right).
\end{aligned}
$$

On a cell, the squared $L^2$ difference between the step value and its
linear interpolation is $\varepsilon|\Delta u|^2/3$. Consequently

$$
\|L_\varepsilon^Af-E_\varepsilon^Af\|^2
\leq\frac{\varepsilon^2}{3}\mathfrak q_\varepsilon^A[f],
\qquad
\|L_\varepsilon^Df-E_\varepsilon^Df\|^2
\leq\frac{\varepsilon^2}{3}\mathfrak q_\varepsilon^D[f].
$$

Assume $C_\varepsilon\to C\in(0,\infty)$ and regard the two forms as
extended forms on $\mathcal H$, with value $+\infty$ off their step-image
subspaces. Their candidate limits are

$$
\begin{aligned}
\mathfrak q_C^A[u]
&=\int_0^C(|u'|^2+y^2|u|^2)\,dy,
&Q(\mathfrak q_C^A)&=H_0^1(0,C),\\
\mathfrak q_C^D[u]
&=\int_C^\infty(|u'|^2+y^2|u|^2)\,dy,
&Q(\mathfrak q_C^D)&=
\{u\in H^1(C,\infty):u(C)=0,\ yu\in L^2\}.
\end{aligned}
$$

Each function is extended by zero to the complementary part of
$\mathcal H$. For the weak liminf condition, suppose
$E_\varepsilon f_\varepsilon\rightharpoonup u$ and the corresponding scaled
forms are bounded. The endpoint penalties give

$$
|u_0|^2+|u_N|^2=O(\varepsilon)
\quad\text{for }\mathfrak q_\varepsilon^A,
\qquad
|u_{N+1}|^2=O(\varepsilon)
\quad\text{for }\mathfrak q_\varepsilon^D.
$$

The linear interpolants are bounded in $H^1$ on every compact interval and
differ from the step embeddings by $o(1)$ in $L^2$. Rellich compactness
identifies their local strong limit with $u$. Their supports and the
one-dimensional trace theorem give $u(0)=u(C)=0$ in the retained case and
$u(C)=0$ in the discarded case. Weak $H^1$ lower semicontinuity handles
the derivative terms. The retained potentials converge uniformly on their
bounded support. For the discarded potential, local convergence on
$(C,R)$ followed by $R\to\infty$, using
$V_\varepsilon(y_n)\geq y_n^2$, gives

$$
\liminf_{\varepsilon\to0}\mathfrak q_\varepsilon^A[f_\varepsilon]
\geq\mathfrak q_C^A[u],
\qquad
\liminf_{\varepsilon\to0}\mathfrak q_\varepsilon^D[f_\varepsilon]
\geq\mathfrak q_C^D[u].
$$

For recovery, sample
$f_n=\varepsilon^{1/2}u(y_n)$ first for
$u\in C_c^\infty(0,C)$ or $u\in C_c^\infty(C,\infty)$. The boundary terms
then vanish for small $\varepsilon$, and the norm, potential and difference
quotients converge by Riemann sums. These test spaces are dense in the
respective form norms; a diagonal approximation gives recovery for the full
domains. Thus both forms converge in the Mosco sense. This fixed-space
weak-liminf and strong-recovery statement is the meaning of
``$\xrightarrow{\mathrm{form}}$'' below:

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
has Dirichlet data at $C$ and the natural form condition at infinity. The
form sublevels are compact in the fixed Hilbert space. Retained sequences
use Rellich compactness on a uniformly bounded interval. Discarded sequences
use local Rellich compactness and the uniform tail estimate

$$
\int_R^\infty|E_\varepsilon^Df|^2dy
\leq(R-o(1))^{-2}\mathfrak q_\varepsilon^D[f]
\qquad(R>C).
$$

The min–max principle applied to the liminf and recovery sequences therefore
gives convergence of every fixed ordered eigenvalue. In particular,

$$
\frac{\lambda_j(A_N)}{\sqrt{x}}\longrightarrow\mu_j(C),\qquad
\mu_j(C)>4j+3,\qquad
\nu_0(C):=\inf\sigma(H_{\mathrm{osc}}^{(C,\infty)})\geq C^2,\qquad
\frac{\inf\sigma(D_N)}{\sqrt{x}}\longrightarrow\nu_0(C).
\tag{YM87}
$$

To prove the strict inequality, extend $H_0^1(0,C)$ functions by zero into
the half-line form domain. Min–max gives $\mu_j(C)\geq4j+3$. Regular
Dirichlet Sturm–Liouville eigenvalues are simple and strictly decrease with
the right endpoint; for a normalized eigenfunction $u_{j,C}$,

$$
\frac{d\mu_j(C)}{dC}=-|u_{j,C}'(C)|^2<0.
$$

Both $u_{j,C}(C)$ and $u_{j,C}'(C)$ cannot vanish for a nonzero solution.
Compactly supported recovery as $C\to\infty$ gives
$\mu_j(C)\downarrow4j+3$, proving $\mu_j(C)>4j+3$ for every finite $C$.
The tail bound in (YM87) follows directly from $y^2\geq C^2$.

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

There is a sharp distinction between exact Feshbach isolation and convergence
of the bare finite section. Let $C_x=N/x^{1/4}=\varepsilon N$ and consider
any schedule $N=N(x)$ for which the requested fixed eigenvalue is eventually
defined. If $C_x\to C\in(0,\infty)$, (YM86)--(YM87) give

$$
\frac{\lambda_j(A_N)}{\sqrt{x}}\longrightarrow\mu_j(C)>4j+3.
$$

If $C_x\to0$, (YM83), with
$\sin t\sim t$, gives
$\lambda_0(A_N)/\sqrt{x}\to\infty$, and the same follows for every higher
fixed eigenvalue. Thus any schedule on which $C_x$ fails to tend to infinity
has a subsequence with a bounded further subsequence
$C_x\to C\in[0,\infty)$, and bare half-line convergence fails on that
subsequence.

Conversely, suppose $C_x\to\infty$. Rayleigh--Ritz compression gives

$$
\lambda_j(A_N)\geq\lambda_j(h_x).
$$

For the reverse bound, fix $\delta>0$ and choose a
$(j+1)$-dimensional subspace of $C_c^\infty(0,\infty)$ whose largest
half-line oscillator Rayleigh quotient is at most $4j+3+\delta$. Sampling
these functions on the $\varepsilon$ lattice gives a
$(j+1)$-dimensional trial space for $A_N$ once $C_x$ exceeds their common
support. The same Riemann-sum and difference-quotient calculation used in
the recovery proof is uniform on this finite-dimensional space. Hence

$$
4j+3
\leq\liminf_{x\to\infty}\frac{\lambda_j(A_N)}{\sqrt{x}}
\leq\limsup_{x\to\infty}\frac{\lambda_j(A_N)}{\sqrt{x}}
\leq4j+3+\delta.
$$

Letting $\delta\downarrow0$ proves sufficiency for every fixed $j$.

The discarded-probability statement follows from the full, uncut Jacobi
form. For $f=(f_0,f_1,\ldots)$ its exact scaled form is

$$
\mathfrak q_\varepsilon^h[f]
=\varepsilon\sum_{n=0}^{\infty}
V_\varepsilon(y_n)|u_n|^2
+\varepsilon^{-1}\left(
|u_0|^2+\sum_{n=0}^{\infty}|u_{n+1}-u_n|^2
\right).
$$

The fixed-space interpolation, weak-liminf, compactness and recovery
arguments above, now without the moving right boundary, give compact Mosco
convergence to the Dirichlet half-line oscillator form. Because its
eigenvalues are simple, normalized character-basis eigenvectors
$\psi_j^{(x)}$ may be phased so that

$$
E_\varepsilon^h\psi_j^{(x)}
\longrightarrow\phi_j
\quad\text{strongly in }L^2(0,\infty),
$$

where $E_\varepsilon^h$ is the step isometry on all cells. The exact identity

$$
\|Q_N\psi_j^{(x)}\|^2
=\int_{r_\varepsilon}^{\infty}
|E_\varepsilon^h\psi_j^{(x)}(y)|^2\,dy
$$

then has two consequences. If $C_x\to C<\infty$, it converges to
$\int_C^\infty|\phi_j(y)|^2dy>0$. If $C_x\to\infty$, potential coercivity
and $\mathfrak q_\varepsilon^h[\psi_j^{(x)}]
=\lambda_j(h_x)/\sqrt{x}=O_j(1)$ give

$$
\|Q_N\psi_j^{(x)}\|^2
\leq r_\varepsilon^{-2}
\frac{\lambda_j(h_x)}{\sqrt{x}}
\longrightarrow0.
$$

Therefore, for every fixed low eigenvalue and eigenstate, both bare
finite-section convergence and vanishing discarded character probability
hold if and only if

$$
\boxed{
\frac{N}{x^{1/4}}\longrightarrow\infty,
\qquad\text{equivalently}\qquad
gN\longrightarrow\infty.
}
\tag{YM90}
$$

The frozen choices $N_{\mathrm{fixed}}=8$,
$N_C=\lceil2x^{1/4}\rceil$, and
$N_{\mathrm{iso}}=\lceil4x^{1/4}\rceil$ all have bounded $C_x$ and fail
bare convergence. The last nevertheless supplies the separate exact
fixed-window Feshbach isolation proved in (YM88)--(YM89).
$N_{\mathrm{grow}}=\lceil x^{1/4}\log(2+x)\rceil$ and
$N_{1/2}=\lceil2\sqrt{x}\rceil$ satisfy (YM90).

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

The four boundary-midpoint intertwiners are unique. Let
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

### 9.20 Poincaré geometry and an exact two-scale gap recurrence

The solved Poincaré conjecture and Perelman's geometric method suggest two
questions for the remaining weak-coupling problem. The first is whether a
closed bubble-sized spatial slice has useful topology. The second is whether
noncollapse under a scale flow has a functional-inequality analogue for the
interacting vacuum measure. These questions have different answers.

#### 9.20.1 Spatial topology, flat sectors and the infrared regulator

Let $\Sigma$ be a closed, connected, simply connected spatial
three-manifold. The Poincaré theorem gives

$$
\boxed{\Sigma\ \hbox{is homeomorphic to}\ S^3.}
\tag{YM99}
$$

This conclusion is conditional on all three hypotheses. The projective shell
in §§3–5 is a two-sphere of internal states and does not establish that the
physical spatial slice is closed or simply connected. The topology in (YM99)
also selects no metric or radius.

If a round metric of radius $R$ is chosen as a finite-volume regulator, the
coexact one-form spectrum is

$$
\lambda_{k,1}^{\mathrm{coex}}(S_R^3)
=\frac{(k+1)^2}{R^2},
\qquad k=1,2,\ldots.
\tag{YM100}
$$

The first coexact frequency of the free Maxwell/linearized spatial operator
is therefore $2/R$. It is a kinematic base-manifold mode, not the interacting
non-Abelian gauge-invariant Hamiltonian gap or evidence for confinement. The
round regulator has no physical boundary, but this frequency tends to zero
as $R\to\infty$. Spatial roundness supplies no regulator-independent mass.

The simply connected topology removes continuous flat-connection moduli.
A flat $SU(2)$ connection has trivial holonomy representation of
$\pi_1(S^3)$ and is gauge equivalent to the trivial connection. Principal
$SU(2)$ bundles over $S^3$ are also topologically trivial because
$\pi_2(SU(2))=0$. Large gauge transformations remain: the components of
$\operatorname{Map}(S^3,SU(2))$ are indexed by
$\pi_3(SU(2))\cong\mathbb Z$. Thus the topology simplifies the flat
background while retaining the usual winding and $\theta$-sector question.

The group identity $SU(2)\cong S^3$ is independent of (YM99). It is known
directly from the unit-quaternion representation and supplies the geometry
of each regulated link even when the spatial regulator is a torus or a box.

The base Hodge operator in (YM100) acts on spatial one-forms. The scalar
Casimir below acts on functions of one link coordinate. No equality between
their spectra, or between either spectrum and a gauge-orbit Poincaré rate, is
assumed.

#### 9.20.2 The fixed link-sphere curvature calculation

Use the electric normalization already fixed in (YM27):

$$
X^Af(U)
:=\left.\frac{d}{dt}
f(e^{it\sigma_A/2}U)\right|_{t=0},
\qquad
K=-\sum_A(X^A)^2.
\tag{YM101}
$$

In unit-quaternion coordinates $q=(q_0,\mathbf q)$, an $X^A$-unit tangent
has speed $1/2$ in the ambient unit sphere. The Casimir metric is therefore
the round metric of radius $2$, and

$$
K\chi_{n/2}=\frac{n(n+2)}4\chi_{n/2},
\qquad
\operatorname{Ric}=\frac12g.
\tag{YM102}
$$

Equivalently, $K$ is one quarter of the positive scalar Laplacian for the ambient
unit-round three-sphere. Its fundamental-character rate is $3/4$, whereas the
first nonconstant unit-sphere scalar eigenvalue is $3$.

This is the same $j(j+1)$ normalization used by the physical factor
$g^2/(2a)$ in (YM28). For the Wilson function

$$
W(q)=1-q_0,
$$

a Casimir-unit geodesic has
$q(t)=q\cos(t/2)+2v\sin(t/2)$ with ambient
$|v|=1/2$. Twice differentiating gives

$$
\operatorname{Hess}W=\frac{q_0}{4}g.
\tag{YM103}
$$

Consequently the one-link Wilson probability measure

$$
d\nu_\beta=Z_\beta^{-1}e^{-\beta W}\,dU
$$

has weighted Ricci tensor

$$
\operatorname{Ric}+\operatorname{Hess}(\beta W)
=\frac{2+\beta q_0}{4}g
\succeq\frac{2-\beta}{4}g.
\tag{YM104}
$$

For $0\leq\beta<2$, the Bakry–Émery criterion gives the all-function
Poincaré-rate lower bound $(2-\beta)/4$. At $\beta=2$ the pointwise lower
bound reaches zero at the antipode, and for $\beta>2$ this criterion gives no
positive rate. The compact smooth one-link measure still has a positive
spectral gap for every finite $\beta$; (YM104) locates the failure of this
pointwise curvature proof. Within this separately declared one-link Wilson
family, the criterion fails once $\beta\geq2$ and throughout any
$\beta\to\infty$ concentration limit. The auxiliary $\beta$ is not
identified here with the Hamiltonian coupling $g$, with $x=2/g^4$, or with
an exact interacting-vacuum conditional measure. Such a transfer requires an
explicit density or quadratic-form comparison. Any stronger estimate for the
one-link family must use localization, capacity or vacuum weighting rather
than the pointwise minimum.

For a finite graph the unreduced configuration manifold is
$SU(2)^E\cong(S^3)^E$, with the product Casimir metric. The gauge quotient is
stratified at configurations with non-free stabilizers. Compactness gives a
regulator-dependent positive first eigenvalue for each smooth positive finite
measure, not a volume-, cutoff- or refinement-uniform lower bound. A global
orbit-space Lichnerowicz argument would require a complete smooth
finite-dimensional domain, a uniform positive Ricci lower bound and control
of stratum boundaries.

No Cassi scale changes the metric in (YM101)–(YM104). In the coordinate chart
below, the comparison eigenvalues $(3\pm\sqrt5)/2$ arise from pulling back
this fixed Casimir metric. They are coordinate-condition numbers and carry
no cascade interpretation.

#### 9.20.3 Orthogonal geometry of an exact factor-two block

Let $G=SU(2)$ with the metric in (YM101) and consider

$$
m:G\times G\longrightarrow G,
\qquad
m(U_1,U_2)=U_1U_2.
\tag{YM105}
$$

Write right-trivialized tangent velocities as $a_i=\dot U_iU_i^{-1}$ and
$\eta=\dot V V^{-1}$. Then

$$
dm(a_1,a_2)=a_1+\operatorname{Ad}_{U_1}a_2.
$$

The kernel has vectors
$z(\zeta)=(\zeta,-\operatorname{Ad}_{U_1}^{-1}\zeta)$. Its orthogonal
complement has the horizontal lift

$$
h(\eta)
=\frac12\left(\eta,\operatorname{Ad}_{U_1}^{-1}\eta\right),
\qquad
\|h(\eta)\|^2=\frac12\|\eta\|^2,
\qquad
\|z(\zeta)\|^2=2\|\zeta\|^2.
\tag{YM106}
$$

For a smooth $F$ define $\nabla_HF$ and $\nabla_VF$ by differentiation
against $\eta$ and $\zeta$ in these displayed lifts. Orthogonal duality gives
the exact electric decomposition

$$
\boxed{
\Gamma_f(F)
=2|\nabla_HF|^2+\frac12|\nabla_VF|^2.
}
\tag{YM107}
$$

In the explicit coordinates

$$
(U_1,U_2)\longleftrightarrow(V,R)=(U_1U_2,U_1),
$$

the fixed-$R$ lift is
$c(\eta)=(0,\operatorname{Ad}_{R}^{-1}\eta)$ and

$$
c(\eta)-h(\eta)=z(-\eta/2).
\tag{YM108}
$$

This connection term is essential when differentiating a conditional
expectation. Direct coordinate pullback gives the tangent metric matrix

$$
\begin{pmatrix}1&-1\\-1&2\end{pmatrix},
\qquad
c_\pm=\frac{3\pm\sqrt5}{2},
\tag{YM109}
$$

which is equivalent to the orthogonal decomposition but less sharp for the
scale recurrence.

Normalized Haar measure factorizes exactly:

$$
\int_{G^2}F(U_1,U_2)\,dU_1dU_2
=\int_{G^2}F(R,R^{-1}V)\,dRdV.
\tag{YM110}
$$

For a base path with right velocity $\eta$, horizontal transport obeys
$\dot R R^{-1}=\eta/2$. Its fibre map is left multiplication by a group
element and preserves $dR$. Thus Haar is a connection-compatible reference
measure. Products of disjoint two-link paths inherit the same formulas. Any
unpaired fine links can be included in the fibre; their coefficient one is
larger than the conservative fibre coefficient $1/2$ in (YM107).

#### 9.20.4 Transported conditional score and the recurrence theorem

Let $\mu_f$ be the exact smooth positive vacuum measure from §9.13 on a
finite regulated graph, and let the path block in (YM105) be applied to a
set of edge-disjoint pairs. Disintegrate

$$
d\mu_f=d\bar\mu(V)\,d\nu_V(R),
\qquad
d\nu_V=p_V\,dR.
\tag{YM111}
$$

The notation includes all coarse and fibre variables. Along horizontal
transport $T_t:m^{-1}(V)\to m^{-1}(V_t)$, define the total transported score
$s_V$ by

$$
\left.\frac{d}{dt}\right|_{t=0}
(T_t^{-1})_\#\nu_{V_t}
=\langle s_V,\eta\rangle\nu_V.
\tag{YM112}
$$

The score $s_V$ is a cotangent vector on the coarse configuration space and
pairs with the tangent $\eta$.

Because horizontal transport preserves the Haar reference,
$s_V=\nabla_H\log p_V$. Equation (YM112), rather than a fixed-$R$
derivative, is the operative definition. Normalization gives
$\mathbb E_{\nu_V}s_V=0$, and differentiation under the integral gives

$$
\nabla\,\mathbb E_{\nu_V}F
=\mathbb E_{\nu_V}\nabla_HF
+\mathbb E_{\nu_V}
\left[
\left(F-\mathbb E_{\nu_V}F\right)s_V
\right].
\tag{YM113}
$$

Assume the following three finite-scale estimates:

$$
\begin{aligned}
\operatorname{Var}_{\bar\mu}u
&\leq\lambda_c^{-1}
\mathbb E_{\bar\mu}|\nabla u|^2,\\
\operatorname{Var}_{\nu_V}F
&\leq\lambda_{\mathrm{fib}}^{-1}
\mathbb E_{\nu_V}|\nabla_VF|^2
\quad\hbox{uniformly in }V,\\
\mathbb E_{\nu_V}\langle s_V,\xi\rangle^2
&\leq\kappa^2|\xi|^2
\quad\hbox{uniformly in }V\hbox{ and coarse tangent vectors }\xi.
\end{aligned}
\tag{YM114}
$$

The first line concerns the exact coarse marginal. The second can be imposed
on all fibre functions, which is sufficient for the physical sector. The
third is a covariance-operator bound on every interaction carried by the
conditional vacuum.

Set

$$
X^2=\mathbb E_{\mu_f}|\nabla_HF|^2,
\qquad
Y^2=\mathbb E_{\mu_f}|\nabla_VF|^2.
$$

Total variance, the second line of (YM114), (YM113), Cauchy–Schwarz and the
first and third lines of (YM114) give

$$
\operatorname{Var}_{\mu_f}F
\leq
\frac{Y^2}{\lambda_{\mathrm{fib}}}
+\frac1{\lambda_c}
\left(X+\frac{\kappa}{\sqrt{\lambda_{\mathrm{fib}}}}Y\right)^2.
\tag{YM115}
$$

For completeness, the score term obeys

$$
\left\|
\mathbb E_{\nu_V}
\left[
\left(F-\mathbb E_{\nu_V}F\right)s_V
\right]
\right\|_{L^2(\bar\mu)}
\leq\frac{\kappa}{\sqrt{\lambda_{\mathrm{fib}}}}Y,
$$

while conditional Jensen gives
$\|\mathbb E_{\nu_V}\nabla_HF\|_{L^2(\bar\mu)}\leq X$.
These are exactly the two summands in (YM115).

Compare the quadratic form in (YM115) with
$2X^2+Y^2/2$ from (YM107). Define

$$
A=\frac1{2\lambda_c},
\qquad
B=\frac{\kappa}{\lambda_c\sqrt{\lambda_{\mathrm{fib}}}},
\qquad
D=\frac2{\lambda_{\mathrm{fib}}}
\left(1+\frac{\kappa^2}{\lambda_c}\right),
\tag{YM116}
$$

and

$$
C_*=
\frac12\left[
A+D+\sqrt{(A-D)^2+4B^2}
\right].
\tag{YM117}
$$

The displayed number is the largest generalized eigenvalue of the
Minkowski-derived upper-bound quadratic form in (YM115) relative to the
electric metric $\operatorname{diag}(2,1/2)$.

**Two-scale vacuum-measure theorem.** Under (YM105)–(YM114), the
all-function Poincaré rate of the fine vacuum measure satisfies

$$
\boxed{\lambda_f\geq C_*^{-1}.}
\tag{YM118}
$$

Here $\lambda_f$ is the all-function fine-measure rate. Since the
gauge-invariant functions form a subspace,
$\lambda_{\mathrm{gi}}(\mu_f)\geq\lambda_f$, and (YM28) gives

$$
\Delta_{\mathrm{phys},f}
=\frac{g_f^2}{2a_f}\lambda_{\mathrm{gi}}(\mu_f)
\geq\frac{g_f^2}{2a_f}\lambda_f.
$$

This implication uses no gauge-restricted conditional inequality. A
recurrence using physical-sector coarse or fibre rates requires additional
invariance data. Take the regulated fine and coarse graphs to be finite and
connected, use the gauge-invariant Kogut–Susskind Hamiltonian and unique
positive vacuum from §9.13, choose endpoint representatives consistently as
in (YM42), and let their action induce the coarse gauge action. Choose the
smooth regular conditional disintegration in (YM111) equivariantly, and
require the horizontal connection and Haar fibre reference to be equivariant.
Then a globally gauge-invariant $F$ gives the coarse gauge-invariant function
$u(V)=\mathbb E_{\nu_V}F$, while its conditional fibre functions lie in the
declared induced invariant class. The same proof uses restricted coarse and
fibre inequalities only when they hold on exactly those domains.

If $\kappa=0$, (YM117) becomes

$$
C_*=\max\left\{\frac1{2\lambda_c},\frac2{\lambda_{\mathrm{fib}}}\right\},
\qquad
\boxed{\lambda_f\geq\min\{2\lambda_c,\lambda_{\mathrm{fib}}/2\}.}
\tag{YM119}
$$

This factor of two is the exact horizontal electric-energy gain of a
two-link path. It is lost by a uniform coordinate-condition estimate using
$c_-$ from (YM109).

#### 9.20.5 Physical mass induction and generated interactions

The exact finite-regulator identity (YM28) converts (YM118) to a physical
statement without changing normalization. For a target $m_*>0$, set

$$
r_f:=\frac{2a_fm_*}{g_f^2}.
\tag{YM120}
$$

Then $\Delta_{\mathrm{phys},f}\geq m_*$ follows whenever
$C_*\leq r_f^{-1}$. Since (YM117) is a two-dimensional symmetric eigenvalue,
this is equivalent to

$$
\boxed{
A\leq r_f^{-1},\qquad
D\leq r_f^{-1},\qquad
B^2\leq
\left(r_f^{-1}-A\right)
\left(r_f^{-1}-D\right).
}
\tag{YM121}
$$

For a factor-two block, $a_c=2a_f$. The pure-electric kinematic matching in
(YM45) is $g_c^2=4g_f^2$, so

$$
r_c:=\frac{2a_cm_*}{g_c^2}=\frac{r_f}{2}.
\tag{YM122}
$$

When $\kappa=0$, a coarse-marginal rate
$\lambda_c\geq r_c$ closes the horizontal branch exactly, and the vertical
branch requires $\lambda_{\mathrm{fib}}\geq2r_f$. If
$\lambda_c=r_c$ and $\kappa>0$, then $A=r_f^{-1}$ and the determinant
condition in (YM121) forces $B=0$. Every nonzero transported score therefore
requires a strict coarse-rate margin or a sharper signed cancellation beyond
the covariance estimate in (YM115).

The coarse marginal in (YM111) is exact and automatically contains every
interaction generated by integrating out the fibre. It need not be the
vacuum of the bare Kogut–Susskind family at parameters $(a_c,g_c)$. The
static-marginal obstruction in §9.16 already excludes that unqualified
closure. Iteration of (YM118) must either:

1. use the exact successive marginals, retaining all generated interactions;
   or
2. prove a quantitative comparison between each marginal and a declared
   coarse effective vacuum.

Thus a coarse-theory mass bound enters (YM121) only after an exact
renormalization closure or a density/form comparison transfers its
Poincaré rate to $\bar\mu$.

The score gives a concrete norm for the generated interaction. If

$$
p_V(R)=Z(V)^{-1}e^{-\mathcal S(V,R)},
$$

then horizontal differentiation yields

$$
s_V
=-\nabla_H\mathcal S
+\mathbb E_{\nu_V}\nabla_H\mathcal S.
\tag{YM123}
$$

If, for every unit coarse tangent vector $\xi$,

$$
\left|
\nabla_V\langle\nabla_H\mathcal S,\xi\rangle
\right|
\leq M
\quad\hbox{uniformly},
$$

the conditional Poincaré inequality in (YM114) gives

$$
\boxed{\kappa^2\leq\frac{M^2}{\lambda_{\mathrm{fib}}}.}
\tag{YM124}
$$

This converts the score problem into a mixed-Hessian estimate, but a global
supremum bound obtained directly from a weak-coupling Wilson coefficient
carries divergent powers of $x=2/g^4$. The useful estimate must be weighted
by the true vacuum, exploit localization or expose cancellations among the
generated terms. Equation (YM124) is a sufficient route and is not assumed
uniform.

#### 9.20.6 Relation to Perelman's method and the remaining theorem

Perelman's Ricci-flow argument controls geometric degeneration through
scale-normalized entropy and noncollapsing estimates. Equations
(YM111)–(YM124) provide a precise functional-inequality analogue: exact
marginalization is the scale flow, $\lambda_{\mathrm{fib}}$ prevents collapse inside a
fibre, $\lambda_c$ controls the retained geometry and $\kappa$ measures the
interaction generated between them. No monotone entropy or noncollapse
theorem for this vacuum-measure flow has been established here. Ricci flow
on a spatial three-manifold does not evolve the Yang–Mills ground-state
measure, and Perelman's theorem does not apply directly to the singular
infinite-dimensional orbit space.

The cited orbit-curvature program establishes nonnegative sectional
curvature for its regulated geometry and proposes a Ricci-based mechanism.
It supplies no uniform positive Ricci lower bound for the exact vacuum
measure. Lichnerowicz therefore does not transfer that result to the
stratified gauge quotient or its thermodynamic and continuum limits.

The covariance route produces the following sufficient $L^2$ target:

$$
\begin{gathered}
\inf_j\lambda_{\mathrm{fib},j}/r_j>2,\qquad
\lambda_{j+1}>r_{j+1}\ \hbox{with quantified margin},\\
\kappa_j\ \hbox{small enough for (YM121) at every scale},
\end{gathered}
\tag{YM125}
$$

for exact interacting marginals or rigorously compared effective vacua.
Equation (YM125) is the $L^2$-score sufficient route. Section 9.21 replaces
its third line by the weaker conditional-transport requirement (YM151);
either route still needs the displayed uniform fibre and coarse margins.
The inequalities must remain uniform in spatial volume, representation
support and the weak-bare-coupling refinement sequence. Establishing them,
together with the thermodynamic limit, reflection-positive continuum
construction and regulator-independent physical spectrum, remains the
Yang–Mills problem. The three-sphere topology supplies a clean infrared
setting and the link-sphere geometry supplies exact local constants; neither
supplies the missing scale-uniform interaction bound.

### 9.21 Conditional $H^{-1}$ transport score and exact margin transfer

The covariance estimate in (YM114) controls the transported score in
$L^2(\nu_V)$ and then spends the full fibre Poincaré constant in (YM115).
This can discard cancellations along stiff fibre directions. The exact
two-scale proof admits a weaker score norm.

#### 9.21.1 Conditional Poisson geometry

Retain the smooth exact disintegration (YM111). Assume each conditional fibre
is connected, has no boundary or the no-flux form domain, and has the
Poincaré rate $\lambda_{\mathrm{fib}}>0$ in (YM114). For almost every $V$,
let

$$
\begin{aligned}
\mathcal E_V(u,v)
&:=\mathbb E_{\nu_V}
\langle\nabla_Vu,\nabla_Vv\rangle,\\
\mathcal L_V
&:=-\operatorname{div}_{\nu_V}\nabla_V
\end{aligned}
\tag{YM126}
$$

be the vertical Dirichlet form and its nonnegative Friedrichs operator.
For a unit coarse tangent $\xi$, set
$s_{V,\xi}:=\langle s_V,\xi\rangle$. Centering means
$\langle s_{V,\xi},1\rangle_{H^{-1},H^1}=0$. Suppose these components are
measurable in $V$ and belong to the centered conditional $H^{-1}$ space.
Define

$$
\boxed{
\vartheta^2:=
\mathop{\mathrm{ess\,sup}}_V
\sup_{|\xi|=1}
\langle
s_{V,\xi},
\mathcal L_V^{-1}s_{V,\xi}
\rangle_{H^{-1},H^1}.
}
\tag{YM127}
$$

The same quantity has the dual and transport forms

$$
\begin{aligned}
\|s_{V,\xi}\|_{H^{-1}(\nu_V)}^2
&=
\sup_{\substack{f\in\mathcal D(\mathcal E_V)\\
\mathcal E_V(f,f)>0}}
\frac{
\langle s_{V,\xi},f-\mathbb E_{\nu_V}f\rangle_{H^{-1},H^1}^2}
{\mathcal E_V(f,f)},\\
&=
\inf_{\substack{u\in L^2(\nu_V;T\mathcal F_V)\\
-\operatorname{div}_{\nu_V}u=s_{V,\xi}\ {\rm weakly}}}
\mathbb E_{\nu_V}|u|^2.
\end{aligned}
\tag{YM128}
$$

The infimum is $+\infty$ when the weak divergence equation has no solution.
When finite, Lax–Milgram gives
$w=\mathcal L_V^{-1}s_{V,\xi}$. The vector field
$u_*=\nabla_Vw$ obeys
$-\operatorname{div}_{\nu_V}u_*=s_{V,\xi}$. The zero-score case is
immediate. For nonzero score and every other admissible $u$,

$$
\mathbb E_{\nu_V}|u|^2
\geq
\frac{
\left(\mathbb E_{\nu_V}\langle u,\nabla_Vw\rangle\right)^2}
{\mathbb E_{\nu_V}|\nabla_Vw|^2}
=\mathbb E_{\nu_V}|\nabla_Vw|^2,
\tag{YM129}
$$

so $u_*$ minimizes the kinetic cost. Thus $\vartheta$ is the least vertical
transport cost required to move the conditional law under a unit coarse
displacement.

#### 9.21.2 Sharpened two-scale recurrence

Let $F$ lie in the joint fine Dirichlet-form domain, with conditional slices
in the vertical form domain and square-integrable weak horizontal
derivative. When the score is only in $H^{-1}$, the expectation notation in
(YM113) and below denotes the $H^1$–$H^{-1}$ dual pairing. Pointwise in $V$,

$$
\left|
\mathbb E_{\nu_V}
\left[(F-\mathbb E_{\nu_V}F)s_{V,\xi}\right]
\right|^2
\leq
\vartheta^2
\mathbb E_{\nu_V}|\nabla_VF|^2
\qquad(|\xi|=1).
\tag{YM130}
$$

Taking the supremum over $\xi$, integrating over $\bar\mu$, and repeating
the total-variance proof of (YM115) gives

$$
\boxed{
\operatorname{Var}_{\mu_f}F
\leq
\frac{Y^2}{\lambda_{\mathrm{fib}}}
+\frac1{\lambda_c}(X+\vartheta Y)^2.
}
\tag{YM131}
$$

Against the exact electric form $2X^2+Y^2/2$, define

$$
\begin{gathered}
A_{-1}:=\frac1{2\lambda_c},
\qquad
B_{-1}:=\frac{\vartheta}{\lambda_c},
\qquad
D_{-1}:=
2\left(
\frac1{\lambda_{\mathrm{fib}}}
+\frac{\vartheta^2}{\lambda_c}
\right),\\
C_{-1}:=
\frac12\left[
A_{-1}+D_{-1}
+\sqrt{(A_{-1}-D_{-1})^2+4B_{-1}^2}
\right].
\end{gathered}
\tag{YM132}
$$

The same generalized-eigenvalue comparison as in (YM117) proves

$$
\boxed{\lambda_f\geq C_{-1}^{-1}.}
\tag{YM133}
$$

This is an all-function rate and therefore also lower-bounds the
gauge-invariant rate as in (YM118). A direct physical-sector proof retains
the gauge-equivariant disintegration and invariant-domain assumptions stated
there.

The old covariance hypothesis implies the new one. Indeed,
$\mathcal L_V\geq\lambda_{\mathrm{fib}}$ on centered functions, so

$$
\boxed{
\vartheta^2
\leq
\frac{\kappa^2}{\lambda_{\mathrm{fib}}}.
}
\tag{YM134}
$$

Substituting the right side into (YM132) recovers the coefficients in
(YM116). The $H^{-1}$ recurrence is therefore no weaker. It is strictly
stronger whenever the uniform bound satisfies
$\vartheta^2<\kappa^2/\lambda_{\mathrm{fib}}$.

#### 9.21.3 Exact physical-margin accounting

Let $r_f$ and $r_c=r_f/2$ be as in (YM120)–(YM122), with
$r_f,\lambda_c,\lambda_{\mathrm{fib}}>0$. For a desired relative fine
margin $\delta_f\geq0$, set

$$
h:=\frac{r_f}{2\lambda_c}
=\frac{r_c}{\lambda_c},
\qquad
v:=\frac{2r_f}{\lambda_{\mathrm{fib}}},
\qquad
t_f:=\frac1{1+\delta_f}.
\tag{YM135}
$$

Multiplication of the recurrence matrix by $r_f$ gives exactly

$$
r_f
\begin{pmatrix}
A_{-1}&B_{-1}\\
B_{-1}&D_{-1}
\end{pmatrix}
=
\begin{pmatrix}
h&2h\vartheta\\
2h\vartheta&v+4h\vartheta^2
\end{pmatrix}.
\tag{YM136}
$$

The recurrence certifies
$\lambda_f\geq(1+\delta_f)r_f$ precisely when this matrix is bounded above
by $t_fI$. The two-dimensional semidefinite condition simplifies to

$$
\boxed{
h\leq t_f,
\qquad
v\leq t_f,
\qquad
\vartheta^2
\leq
\frac{(t_f-h)(t_f-v)}{4ht_f}.
}
\tag{YM137}
$$

To see the cancellation, the determinant inequality is

$$
4h^2\vartheta^2
\leq
(t_f-h)(t_f-v-4h\vartheta^2).
$$

Moving the score term from the right leaves
$4ht_f\vartheta^2\leq(t_f-h)(t_f-v)$. Together with the separately retained
condition $v\leq t_f$, this score bound implies the second diagonal
condition.

Define the input margins

$$
\delta_c:=\frac{\lambda_c}{r_c}-1,
\qquad
\delta_v:=\frac{\lambda_{\mathrm{fib}}}{2r_f}-1.
\tag{YM138}
$$

Then $h=(1+\delta_c)^{-1}$ and $v=(1+\delta_v)^{-1}$, and (YM137) becomes

$$
\boxed{
\delta_c\geq\delta_f,
\qquad
\delta_v\geq\delta_f,
\qquad
\vartheta^2
\leq
\frac{
(\delta_c-\delta_f)(\delta_v-\delta_f)}
{4(1+\delta_f)(1+\delta_v)}.
}
\tag{YM139}
$$

This is the exact margin-transfer condition supplied by the recurrence.
Nonzero transport cost consumes both input margins. If either input margin
equals the requested output margin, the recurrence leaves zero transport
budget. For the unenhanced mass target $\delta_f=0$, the score budget is
$\delta_c\delta_v/[4(1+\delta_v)]$.

#### 9.21.4 Gaussian reconstruction

The meaning of the weaker score norm is exact for a Gaussian control. Let

$$
Q=
\begin{pmatrix}
Q_{VV}&Q_{VR}\\
Q_{RV}&Q_{RR}
\end{pmatrix}
\succ0,
\qquad
d\mu(v,r)\propto
e^{-(v,r)^TQ(v,r)}\,dv\,dr,
\tag{YM140}
$$

and define

$$
T:=-Q_{RR}^{-1}Q_{RV},
\qquad
Q_{\mathrm{eff}}
:=Q_{VV}-Q_{VR}Q_{RR}^{-1}Q_{RV}.
\tag{YM141}
$$

The conditional law of $r$ has mean $Tv$, exponent precision $Q_{RR}$,
statistical precision $2Q_{RR}$ and covariance $(2Q_{RR})^{-1}$. Writing
$z=r-Tv$, its score and minimum transport field are

$$
s_\xi
=2(T\xi)^TQ_{RR}z,
\qquad
u_\xi=T\xi,
\qquad
-\operatorname{div}_{\nu_v}u_\xi=s_\xi.
\tag{YM142}
$$

Consequently

$$
\begin{gathered}
\lambda_c=2\lambda_{\min}(Q_{\mathrm{eff}}),
\qquad
\lambda_{\mathrm{fib}}=2\lambda_{\min}(Q_{RR}),\\
\vartheta^2=\|T\|_{\mathrm{op}}^2,
\qquad
\kappa^2
=2\|Q_{VR}Q_{RR}^{-1}Q_{RV}\|_{\mathrm{op}}.
\end{gathered}
\tag{YM143}
$$

The matrix inequality
$Q_{RR}^{-2}\preceq
\lambda_{\min}(Q_{RR})^{-1}Q_{RR}^{-1}$
proves (YM134) directly.

For the anisotropic Gaussian form with
$G=\operatorname{diag}(2I_V,I_R/2)$, the exact all-function rate is

$$
\lambda_{\mathrm{exact}}
=2\lambda_{\min}(G^{1/2}QG^{1/2}).
\tag{YM144}
$$

The equality fixture

$$
Q^{(=)}
=
\begin{pmatrix}
2&-1&0\\
-1&2&0\\
0&0&2
\end{pmatrix}
\tag{YM145}
$$

has
$\vartheta^2=\kappa^2/\lambda_{\mathrm{fib}}=1/4$ and
$C_{-1}^{-1}=\lambda_{\mathrm{exact}}=5-\sqrt{13}$. The strict fixture

$$
Q^{(<)}
=
\begin{pmatrix}
4&0&-3\\
0&1&0\\
-3&0&9
\end{pmatrix}
\tag{YM146}
$$

has

$$
\vartheta^2=\frac19,
\qquad
\frac{\kappa^2}{\lambda_{\mathrm{fib}}}=1,
\qquad
\frac{\kappa^2/\lambda_{\mathrm{fib}}}{\vartheta^2}=9.
\tag{YM147}
$$

Its exact gap is $1$. The $H^{-1}$ recurrence gives
$216/(121+\sqrt{10753})\approx0.9613$, while the relaxed covariance
recurrence gives
$24/(17+\sqrt{241})\approx0.7379$. The improvement is a finite Gaussian
statement about the score estimate, not an interacting-vacuum estimate.

#### 9.21.5 Weak-field chain diagnostic

For the formal translation-invariant chain define

$$
\begin{aligned}
q_m(k)&:=\sqrt{m^2+4\sin^2(k/2)},\\
a_m(K)&:=
\frac{q_m(K/2)+q_m(K/2+\pi)}2,\\
|b_m(K)|&:=
\frac{|q_m(K/2)-q_m(K/2+\pi)|}{2}.
\end{aligned}
\tag{YM148}
$$

Even/odd aliasing gives the fibre symbol $a_m$. The transport multiplier has
modulus $|b_m|/a_m$; its phase depends on the cell convention. The coarse
Schur symbol is

$$
q_{\mathrm{eff},m}(K)
=a_m(K)-\frac{|b_m(K)|^2}{a_m(K)}
=\frac{q_m(K/2)q_m(K/2+\pi)}{a_m(K)}.
\tag{YM149}
$$

To establish the continuous-zone extrema, set
$y=\sin^2(K/4)\in[0,1/2]$,
$u_m(y)=\sqrt{m^2+4y}$ and
$w_m(y)=\sqrt{m^2+4(1-y)}$. On the interior,

$$
\frac{d}{dy}\frac{u_m+w_m}{2}
=\frac1{u_m}-\frac1{w_m}\geq0,
\qquad
\frac{d}{dy}\frac{w_m-u_m}{w_m+u_m}
=-\frac{4(u_m/w_m+w_m/u_m)}{(w_m+u_m)^2}<0.
$$

Continuity supplies the massless endpoint. Hence the fibre infimum and
transport supremum occur at $y=0$. For $s_m=\sqrt{m^2+4}$,

$$
\lambda_{\mathrm{fib},\infty}=m+s_m,
\qquad
\vartheta_\infty=\frac{s_m-m}{s_m+m},
\qquad
q_{\mathrm{eff},m}(0)=\frac{2ms_m}{m+s_m}.
\tag{YM150}
$$

At $m=0$, these formal symbol values are
$\lambda_{\mathrm{fib},\infty}=2$, $\vartheta_\infty=1$ and
$q_{\mathrm{eff},0}(0)=0$. Since
$q_0(k)^{-1}\sim|k|^{-1}$ is not locally integrable, the unpinned
bi-infinite massless field has no ordinary normalizable stationary Gaussian
probability. Finite open chains are positive, and the massive symbol defines
a stationary Gaussian control. In either case the calculation is a
weak-field diagnostic. The massless coarse branch retains the infrared
zero rather than manufacturing a gap from positive fibre control.

#### 9.21.6 Remaining interacting estimate

The exact improvement replaces the $L^2$ score target in (YM125) by the
weaker conditional transport target. At desired output margin $\delta_{f,j}$,
the required scale-by-scale estimate is

$$
\vartheta_j^2
\leq
\frac{
(\delta_{c,j}-\delta_{f,j})
(\delta_{v,j}-\delta_{f,j})}
{4(1+\delta_{f,j})(1+\delta_{v,j})},
\qquad
\delta_{c,j},\delta_{v,j}\geq\delta_{f,j}.
\tag{YM151}
$$

An explicit vertical field satisfying
$-\operatorname{div}_{\nu_{V,j}}u_{V,j,\xi}=s_{V,j,\xi}$
can prove this bound without estimating the pointwise score. No such field
or uniform estimate has been constructed for the exact interacting
Yang–Mills vacuum. The thermodynamic limit, weak-coupling refinement,
continuum measure and regulator-independent physical gap remain open.

### 9.22 Residual recovery and the score-penalty separation

The conditional-score operator in §9.21 acts on coarse tangent directions.
Approximate tensorization in §9.14 acts on physical functions. Their
Gramians have opposite proof roles and cannot be exchanged.

#### 9.22.1 Exact residual Gramian

Let

$$
\mathcal H_{\mathrm{phys}}
:=
\left\{
f\in L^2(\mu):
\mu(f)=0,\ f\ \hbox{is gauge invariant}
\right\}
\tag{YM152}
$$

be a nonzero closed subspace. Assume every conditional expectation below
preserves this sector and its common form domain. For the exterior
$\sigma$-algebra $\mathcal F_B$, define the restricted orthogonal
projections

$$
P_Bf:=\mathbb E_\mu(f\mid\mathcal F_B),
\qquad
R_B:=I-P_B.
\tag{YM153}
$$

For a finite block family, or a convergent nonnegative form sum, set

$$
\mathscr R
:=
\sum_Bw_BR_B^*R_B
=\sum_Bw_BR_B,
\qquad
\gamma_{\mathrm{rec}}
:=
\inf_{0\neq f\in\mathcal H_{\mathrm{phys}}}
\frac{\langle f,\mathscr Rf\rangle}{\|f\|_2^2}.
\tag{YM154}
$$

Conditional variance is exactly residual projection energy:

$$
\boxed{
\sum_Bw_B
\mathbb E_\mu
\left[
\operatorname{Var}(f\mid\mathcal F_B)
\right]
=
\sum_Bw_B\|R_Bf\|_2^2
=
\langle f,\mathscr Rf\rangle.
}
\tag{YM155}
$$

Since centered physical functions satisfy
$\operatorname{Var}_\mu f=\|f\|_2^2$, the optimal approximate-tensorization
constant is

$$
\boxed{
A_{\mathrm{AT}}^{\mathrm{opt}}
=\gamma_{\mathrm{rec}}^{-1},
\qquad
\ker\mathscr R
=
\bigcap_{B:w_B>0}\ker R_B
=
\bigcap_{B:w_B>0}\operatorname{Ran}P_B.
}
\tag{YM156}
$$

All operators, kernels and ranges in (YM152)–(YM156) are restricted to
$\mathcal H_{\mathrm{phys}}$. On the full $L^2(\mu)$ space, constants also
belong to the common kernel. When $\gamma_{\mathrm{rec}}=0$, the optimal
constant is $+\infty$.

#### 9.22.2 Recovery plus conditional coercivity

Suppose on the same physical form domain that

$$
\|R_Bf\|_2^2
\leq
\lambda_B^{-1}\mathcal E_B(f,f),
\qquad
\lambda_B\geq\lambda_{\mathrm{loc}}>0,
\qquad
\sum_Bw_B\mathcal E_B(f,f)
\leq\rho\,\mathcal E(f,f).
\tag{YM157}
$$

Combining (YM154), (YM155) and (YM157) yields

$$
\gamma_{\mathrm{rec}}\|f\|_2^2
\leq
\sum_Bw_B\|R_Bf\|_2^2
\leq
\frac{\rho}{\lambda_{\mathrm{loc}}}\mathcal E(f,f),
$$

and therefore

$$
\boxed{
\lambda_{\mathrm{gi}}(\mu)
\geq
\frac{\gamma_{\mathrm{rec}}\lambda_{\mathrm{loc}}}{\rho}.
}
\tag{YM158}
$$

This is (YM30) with
$A_{\mathrm{AT}}=\gamma_{\mathrm{rec}}^{-1}$. It identifies the missing
infrared quantity as the lower spectrum of a concrete residual operator.

For declared scale Hilbert spaces and isometries
$T_{j\to n}:\mathcal H_n\to\mathcal H_j$, define

$$
\mathscr R_n
:=
\sum_{j\leq n}
w_jT_{j\to n}^*R_jT_{j\to n}.
\tag{YM159}
$$

Let $\mathcal N_n$ be a closed nonphysical null subspace and require
$R_jT_{j\to n}\Pi_{\mathcal N_n}=0$. Quantitative recovery is

$$
\boxed{
\mathscr R_n
\succeq
\gamma_*(I-\Pi_{\mathcal N_n}),
\qquad
\gamma_*>0
}
\tag{YM160}
$$

uniformly in regulator and scale. Rigidity is the separate identity
$\ker\mathscr R_n=\mathcal N_n$. A correct kernel at every finite regulator
does not imply a uniform positive $\gamma_*$.

#### 9.22.3 Why the score Gramian cannot supply recovery

The score transport operator is

$$
\mathsf K_V:
\xi\longmapsto
\mathcal L_V^{-1/2}s_{V,\xi},
\qquad
\vartheta^2
=
\mathop{\mathrm{ess\,sup}}_V
\|\mathsf K_V\|_{\mathrm{op}}^2.
\tag{YM161}
$$

It maps coarse tangent directions to conditional $H^{-1}$ data, rather than
physical functions to conditional residuals. Its recurrence matrix is

$$
M(\vartheta)
=
\begin{pmatrix}
(2\lambda_c)^{-1}
&
\vartheta/\lambda_c\\
\vartheta/\lambda_c
&
2(\lambda_{\mathrm{fib}}^{-1}
+\vartheta^2/\lambda_c)
\end{pmatrix}.
\tag{YM162}
$$

For $\vartheta_2\geq\vartheta_1\geq0$, this nonnegative symmetric matrix
increases entrywise. A maximizing Rayleigh vector can be chosen
componentwise nonnegative, so
$\lambda_{\max}M(\vartheta)$ is nondecreasing and the certified rate
$[\lambda_{\max}M(\vartheta)]^{-1}$ is nonincreasing. Thus the score needs an
upper bound. A lower bound on
$\sum_jT_j^*\mathsf K_j^*\mathsf K_jT_j$ has the wrong sign and acts on the
wrong space for variance recovery.

The product Gaussian supplies an exact counterexample:

$$
d\mu(v,r)
\propto
e^{-v^2-2r^2}\,dv\,dr,
\qquad
s_v=0,
\qquad
\mathsf K=0,
\qquad
\lambda_{\mathrm{glob}}=2.
\tag{YM163}
$$

The nonconstant function $f(v,r)=v$ selects
$\xi=\partial_v\in\ker\mathsf K$ and attains the positive global rate because
$\operatorname{Var}v=1/2$ and $\mathcal E(v,v)=1$. A score-kernel direction
therefore need not be gauge or rigid. The fibre-only residual also obeys
$R_rv=0$, so an incomplete block family has
$\gamma_{\mathrm{rec}}=0$ despite a positive fibre conditional rate.

#### 9.22.4 Rigidity without a uniform floor

Let
$R_1=e_1e_1^T$ and
$R_2=r_\epsilon r_\epsilon^T$ on $\mathbb R^2$, where
$r_\epsilon=(\cos\epsilon,\sin\epsilon)^T$. Then

$$
\operatorname{spec}(R_1+R_2)
=
\left\{
1-|\cos\epsilon|,
1+|\cos\epsilon|
\right\}.
\tag{YM164}
$$

For $0<\epsilon<\pi/2$ the kernel is trivial, but
$\gamma_{\mathrm{rec}}=1-\cos\epsilon\to0$ as
$\epsilon\downarrow0$. Qualitative rigidity therefore carries no uniform
constant.

The quotient control

$$
\mathscr R
=
\operatorname{diag}(1,1,0),
\qquad
\mathcal N=\operatorname{span}\{e_3\}
\tag{YM165}
$$

has full-space floor zero and physical quotient floor one. The fixed
three-scale transported construction in the recovery protocol reproduces
this matrix and makes the null compatibility explicit.

#### 9.22.5 Gaussian recovery floor

For the Gaussian chain in (YM37), let
$d_i=Q_{ii}$ and $D=\operatorname{diag}(d_i)$. On first chaos the residual
Gramian is

$$
G_N(m)
=
D^{-1/2}Q_N(m)D^{-1/2},
\qquad
\gamma_{\mathrm{rec},N}(m)
=
\lambda_{\min}(G_N(m)).
\tag{YM166}
$$

If $p_i$ is the first-chaos conditional projection and $S_k$ the orthogonal
symmetrizer, then on $\operatorname{Sym}^k\mathcal H$,

$$
I-p_i^{\otimes_s k}
\succeq
S_k
\left[
(I-p_i)\otimes I^{\otimes(k-1)}
\right]
S_k.
\tag{YM167}
$$

Summing in $i$ transfers the first-chaos floor to every higher chaos, and a
linear function in the bottom eigendirection saturates it. Hence

$$
\boxed{
A_{\mathrm{AT},N}^{\mathrm{opt}}
=
\gamma_{\mathrm{rec},N}^{-1}.
}
\tag{YM168}
$$

For the massless open chain,

$$
\frac{\lambda_{\min}(Q_N)}{\max_i d_i}
\leq
\gamma_{\mathrm{rec},N}(0)
\leq
\frac{\lambda_{\min}(Q_N)}{\min_i d_i},
\qquad
\lambda_{\min}(Q_N)
=
2\sin\frac{\pi}{2(N+1)}.
\tag{YM169}
$$

Every finite chain has only the constant common kernel, while
$\gamma_{\mathrm{rec},N}(0)\to0$. This is an exact failure of uniform
recovery despite finite rigidity.

#### 9.22.6 Correct multiscale target

The recovery-or-rigidity program therefore requires two separate estimates:

$$
\boxed{
\mathscr R_n
\succeq
\gamma_*(I-\Pi_{\mathcal N_n})
\quad\hbox{on physical functions},
\qquad
\mathop{\mathrm{ess\,sup}}_V
\|\mathsf K_{V,n}\|_{\mathrm{op}}^2
\leq
\vartheta_*^2
\quad\hbox{on active coarse tangents}.
}
\tag{YM170}
$$

The first is a lower recovery bound; the second is an upper score-transport
bound that must fit the margin criterion (YM151). Neither follows from the
other. Proving only
$\ker\mathscr R_n=\mathcal N_n$ supplies no uniform recovery rate, and
proving a positive lower score Gramian supplies no gap. No such uniform pair
has been established for the exact interacting Yang–Mills vacuum. The
thermodynamic and continuum constructions remain open.

#### 9.22.7 Finite-level martingale transport criterion

A nested conditional construction can be combined into one estimate only after
its cross-level transport operator is defined on the joint form domain. Let

$$
\mathcal F_{-1}:=\{\varnothing,\Omega\}
\subset\mathcal F_0\subset\cdots\subset\mathcal F_L,
\qquad
P_{-1}f:=\mu(f),
\qquad
P_jf:=\mathbb E_\mu[f\mid\mathcal F_j]\quad(0\leq j\leq L),
\tag{YM171}
$$

and let $\mathcal D\subset L^2(\mathcal F_L,\mu)$ be the common dense form
domain, with $P_Lf=f$ for $f\in\mathcal D$. Set

$$
\Delta_j:=P_j-P_{j-1}.
$$

For centered $f\in\mathcal D$, martingale orthogonality gives
$\operatorname{Var}_\mu(f)=\sum_j\|\Delta_jf\|_2^2$. Assume that the
conditional shell at level $j$ has a rate $\lambda_j>0$ satisfying

$$
\|\Delta_jf\|_2^2
\leq
\lambda_j^{-1}\|h_j(f)\|_2^2,
\qquad
h_j(f):=\nabla_jP_jf.
\tag{YM172}
$$

Suppose differentiated disintegration supplies the joint identity

$$
h(f)=(A_L+K_L)G_Lf,
\qquad
G_Lf:=(\nabla_0f,\ldots,\nabla_Lf),
\tag{YM173}
$$

on $\mathcal D$. Here $A_L$ collects the direct conditional
gradient maps, while $K_L$ collects the centered Poisson transport fields
solving

$$
-\operatorname{div}_{\eta_j}u_{j,\xi}=s_{j,\xi}.
\tag{YM174}
$$

The level ordering makes $K_L$ strictly upper triangular: its $(j,k)$ block
vanishes for $k\leq j$. Let $\Lambda_L=\operatorname{diag}(\lambda_j)$ and
let $W_L$ be a positive direct-sum energy metric,

$$
\mathcal E_L(f):=\|W_L^{1/2}G_Lf\|_2^2.
\tag{YM175}
$$
For the Yang–Mills application, require the block metric to be energy
compatible with the gauge-invariant form domain:

$$
\mathcal E_L(f)
\leq
\chi_{a,L}\mathcal E_{\mathrm{YM},a,L}(f),
\qquad
\mathcal E_{\mathrm{YM},a,L}(f)
:=
\sum_{e,A}\|X_e^Af\|_{L^2(\mu_{a,L})}^2,
$$

for gauge-invariant $f\in\mathcal D$, with $\chi_{a,L}<\infty$. An exact
orthogonal block decomposition has $\chi_{a,L}=1$. The full-filtration
condition $P_Lf=f$ and this energy comparison are separate hypotheses from
the shell and transport estimates.

Then the finite-level estimate is

$$
\boxed{
\operatorname{Var}_\mu(f)
\leq
C_L^2\mathcal E_L(f),
\qquad
C_L:=
\left\|
\Lambda_L^{-1/2}(A_L+K_L)W_L^{-1/2}
\right\|_{\mathrm{op}}.
}
\tag{YM176}
$$

Indeed, (YM172) and martingale orthogonality bound the variance by
$\|\Lambda_L^{-1/2}h(f)\|_2^2$; (YM173) substitutes the joint gradient;
(YM175) and the operator norm give (YM176). Strict upper triangularity alone
does not bound $C_L$ uniformly as $L$ grows.

For a blockwise sufficient condition, write

$$
M_L:=\Lambda_L^{-1/2}(A_L+K_L)W_L^{-1/2},
\qquad
r_L:=\sup_j\sum_k\|M_{jk}\|,
\qquad
c_L:=\sup_k\sum_j\|M_{jk}\|.
\tag{YM177}
$$

The block Schur estimate gives

$$
\|M_L\|_{\mathrm{op}}^2\leq r_Lc_L.
\tag{YM178}
$$

Thus uniformly bounded weighted row and column sums are sufficient for a
scale-uniform conditional estimate. Exponential decay of the normalized
cross-level blocks in $k-j$ is one sufficient mechanism. This condition
controls the assembled transport operator directly; it does not follow by
summing the two-scale recurrences.

Combining (YM176) with the displayed energy comparison and the exact
ground-state transform (YM28) yields, for any family satisfying the displayed
hypotheses,

$$
\Delta_{\mathrm{phys}}(a,L)
\geq
\frac{g_L^2}{2a_L}\bigl(\chi_{a,L}C_L^2\bigr)^{-1}.
\tag{YM179}
$$

The criterion guarantees a fixed physical mass $m_*>0$ provided

$$
\inf_{a,L}
\frac{g_L^2}{2a_L}
\bigl(\chi_{a,L}C_L^2\bigr)^{-1}
\geq m_*.
\tag{YM180}
$$

The Gaussian family (YM37) supplies an exact infrared diagnostic for this
criterion. For the massless open chain,

$$
\lambda_{\mathrm{glob},N}
=2\lambda_{\min}(Q_N)
=4\sin\frac{\pi}{2(N+1)}
\sim\frac{2\pi}{N+1},
\qquad
C_N^2\geq\lambda_{\mathrm{glob},N}^{-1}.
\tag{YM181}
$$

Consequently, a scale-uniform $C_N$ is impossible in the massless chain,
even though every one-coordinate conditional rate remains bounded. With
$m>0$,

$$
\lambda_{\mathrm{glob},N}(m)
=2\sqrt{
m^2+4\sin^2\frac{\pi}{2(N+1)}
}
\longrightarrow 2m,
\tag{YM182}
$$

so a mass or an equivalent infrared-localization hypothesis changes the
global conclusion. These finite Gaussian formulas are algebraic diagnostics
and are separate from the 58-check primary and 30-check independent
receipts.

For the exact Yang–Mills measure, an instantiation would take $\mathcal F_j$
from a nested full-holonomy coarse filtration, use the exact conditional
shell rates for $\lambda_j$, and construct the fields in (YM174) from the
conditional vacuum scores. The required uniform shell, recovery and
transport estimates remain the obligations in (YM151) and (YM170). Equations
(YM171)–(YM182) provide a conditional finite-level target; they do not supply
the missing weak-coupling bound or a continuum mass gap.

### 9.23 Finite cutoff block study: exterior independence and the nodal Ritz obstruction

A seven-link two-plaquette calculation tests the conditional rate of (YM29)
on a graph small enough for exact representation contractions. Its frozen
protocol is `computations/yang-mills-exact-block-spectral-prereg.md`, its
source is `computations/verify_yang_mills_exact_block_spectrum.py`, and its
raw receipt is `runs/yang_mills_exact_block_spectrum/verification.json`. The
block is $B=\{0,1,2,3\}$, the exterior links are $\{4,5,6\}$, and the
scheduled boundary data are $U_4=e^{i\theta\sigma_3/2}$, $U_5=U_6=I$, with
$\theta$ running over the nine multiples of $\pi/8$ in $[0,\pi]$.

Two structural results come out of this calculation, and each one constrains
how the remaining obligations are stated.

The first is an orbit identity that holds for every block. Write $\eta$ for
the link data outside the block and $\eta^{\mathcal G}$ for its image under a
gauge transformation. The block Haar integral is unchanged by the
substitution $U_B\mapsto U_B^{\mathcal G}$, and exact gauge invariance
evaluates the regulated state at the transformed data, so

$$
\int dU_B\,\overline{\Psi(U_B^{\mathcal G};\eta^{\mathcal G})}\,
\Phi(U_B^{\mathcal G};\eta^{\mathcal G})\,
|\Omega(U_B^{\mathcal G};\eta^{\mathcal G})|^2
=
\int dU_B\,\overline{\Psi(U_B;\eta)}\,\Phi(U_B;\eta)\,
|\Omega(U_B;\eta)|^2
\tag{YM183}
$$

holds for every gauge transformation: each block-integrated conditional
moment is a function of the gauge orbit of the exterior data alone. Where the
exterior is a tree, that orbit is the whole exterior configuration space.
Here the exterior links $\{4,5,6\}$ form a tree, exterior gauge
transformations act freely on them, the only exterior invariant is the path
holonomy $W=U_6U_5^{-1}U_4$, and the block transformations at the attachment
vertices move $W$ by left multiplication, which reaches every element of
$SU(2)$. The partition, Gram and Dirichlet moments of the declared fibre
sector therefore coincide at every scheduled boundary angle, and the
Dirichlet sum inherits the invariance because its generator indices are
contracted. A direct seven-link contraction with explicit boundary matrices
reproduces the boundary-independent product algebra to $2.2\times10^{-16}$ in
the partition, $1.6\times10^{-15}$ in the Gram and $3.4\times10^{-15}$ in the
Dirichlet form, with a spread of $2.2\times10^{-16}$ across the nine angles;
three random exterior holonomies reproduce the same moments to
$3.7\times10^{-15}$.

Where the exterior carries loops, the orbit space is coordinatized by the
exterior loop holonomies, so the conditional moments become functions of
those holonomies alone. A finite surrogate for the boundary-uniform estimate
therefore needs an exterior with at least one independent loop. The coarse
plaquettes of the full lattice block decomposition supply them, and the
fibre-rate obligation is then stated over the compact exterior-holonomy
domain rather than over all exterior data.

The second result is a negative one at the smallest cutoff. At doubled
cutoff $J=1$ and $x=1$ the projected Ritz ground vector changes sign on the
block. In the four-state basis $(000),(011),(101),(110)$ the normalized
Hamiltonian is

$$
H_1=
\begin{pmatrix}
4&0&1&1\\
0&\tfrac{17}{2}&\tfrac12&\tfrac12\\
1&\tfrac12&7&0\\
1&\tfrac12&0&7
\end{pmatrix},
\tag{YM184}
$$

and the symmetric-loop sector has ground energy $4-s$, where $s$ is the
unique positive root of

$$
2s^3+15s^2+22s-18=0,
\qquad
\frac{23}{40}<s<\frac{72}{125}.
\tag{YM185}
$$

The exact eigenvector takes the value $2.094120531213694$ at the identity
configuration and $-0.03437408376157869$ at the configuration with the first
block link inverted, and the scaled ratio is bounded above by $-298/4669$.
The cutoff density $\rho\propto|\Omega|^2$ therefore vanishes on a nonempty
set, and a smooth approximation to $\operatorname{sign}(\Omega)$ has positive
limiting variance with Dirichlet energy tending to zero, so the unrestricted
conditional Poincaré gap of that cutoff measure is exactly zero. The
preregistered retained test space returns $0.864465200076$ for the same row.

The exact regulated vacuum measure is strictly positive by §9.13, so the nodal
degeneracy belongs to the projected Ritz density and not to the vacuum. The
retained rate keeps its one-sided meaning as an upper estimate for the cutoff
measure's conditional gap, and the exact-vacuum fibre rate
$\lambda_{\mathrm{fib}}$ remains an obligation in its own right: a projected
Ritz density is not a usable surrogate for it.

The schedule-wide extension of that obstruction is frozen in
`computations/yang-mills-nodal-family-prereg.md`, with source
`computations/verify_yang_mills_nodal_family.py` and receipt
`runs/yang_mills_nodal_family/verification.json`. The measured statistic is
the resolved sign-change count of the normalized Ritz wavefunction along two
block paths,

$$
N_{\mathrm{chg}}(J,x)=\#\Bigl\{k:\ \Omega_J\bigl(U_{(e^*)}(\varphi_k)\bigr)\,
\Omega_J\bigl(U_{(e^*)}(\varphi_{k+1})\bigr)<0,\ \
\bigl|\Omega_J\bigr|>10^{-10}\Bigr\},
\qquad
U_{(e^*)}(\varphi)=\exp\!\Bigl(i\frac{\varphi}{2}\sigma_3\Bigr),
\tag{YM186}
$$

evaluated at the twelve rows $J\in\{1,2,3\}$,
$x\in\{1/4,1,4,16\}$ with $\varphi_k=2\pi k/48$, the other block links and
the three exterior links at the identity, and path link $e^*\in\{0,1\}$. The
endpoint values at $J=1$, $x=1$ reproduce the sealed control to
$4.4\times10^{-16}$, and the path values are real to $8.5\times10^{-18}$
relative. Seven rows carry a resolved sign change, five of them with odd
parity, and the two rows at $J=2$, $x=4,16$ pass through two crossings with
negative excursions of resolved modulus $1.2\times10^{-2}$ and
$4.8\times10^{-3}$. The onset moves with the cutoff: at $J=1$ the
obstruction is present at $x=1$, while at $J=2$ and $J=3$ it appears only at
$x=4$. The $x=1/4$ rows are witness-free at every cutoff, with path minima
$0.675$, $0.706$ and $0.704$, three orders of magnitude above the
resolution, so their silence is not a resolution artifact. The frozen
decision tree returns `NODAL_CONFINED`.

Two consequences attach to this extension. The zero-gap region of the
projected Ritz density is not uniform in the cutoff; it occupies the
strong-coupling half of the schedule and recedes as the cutoff grows. A
one-parameter path can miss a codimension-one nodal set, so the five
witness-free rows bound nothing in the positive direction, and the whole
statement stays inside the surrogate: the exact regulated vacuum measure is
unaffected.

A second frozen protocol,
`computations/yang-mills-nodal-surface-prereg.md` with source
`computations/verify_yang_mills_nodal_surface.py` and receipt
`runs/yang_mills_nodal_surface/verification.json`, replaces the paths by a
two-parameter torus family that rotates block links $0$ and $1$ independently
over a $33\times33$ grid. Its 66 grid lines per row find the same boundary:
the same seven rows carry resolved sign changes, now on 12–62 lines each with
16–162 total changes, and the same five rows carry none on any line, with
grid minima $0.675$, $0.706$, $0.704$, $0.277$ and $0.201$ over 1089 points
per row. Both one-parameter lines reproduce the sealed path tables at the
seventeen common angles to $7.1\times10^{-15}$, and the frozen decision tree
returns `WITNESS_CONFINED`. The zero-gap region of the projected Ritz density
is therefore not an artifact of a single path family.

The frozen study classifies all 180 scheduled boundary rows
`INCONCLUSIVE`. The restriction rank grows with the cutoff at every coupling,
the embedded-minimizer and rate-stability rules fail under their literal
tolerances, and the endpoint full-space residual is $7.4\times10^{-2}$ at
$x=4$ and $3.12$ at $x=16$, above the $10^{-2}$ qualification bound. At the
two smallest couplings the retained rates have stabilized to
$1.1\times10^{-10}$ and $2.9\times10^{-6}$ between the last two cutoffs. No
row qualifies for `SUPPORTS_FINITE_BLOCK`, no conditional-collapse witness is
issued, and the study makes no score or margin claim because the transport
score is outside its first implementation target.

### 9.24 Loop-carrying exterior and finite fibre sensitivity

A finite exterior loop is the smallest graph change that leaves a genuine
holonomy after the block links are integrated. The frozen bowtie protocol
`computations/yang-mills-bowtie-fibre-prereg.md` uses eight links, with block
links $B=\{0,1,2,3\}$ and an exterior plaquette on links
$\{4,5,6,7\}$; the two plaquettes share one vertex and no link. The exterior
orbit space is therefore a conjugacy class of $SU(2)$, represented by
$U_4=U_5=U_6=I$ and $U_7=\exp(i\theta\sigma_3/2)$ for
$\theta=k\pi/8$.

The source-bound execution schedules the four couplings
$x\in\{1/4,1,4,16\}$ at doubled cutoffs $J=1,2,3$ and all nine boundary
angles, giving 108 rows. The seven analytic controls—state-space dimension,
kinetic labels, normalization, gauge-orbit invariance, Hermiticity,
positivity and exclusive receipt creation—pass. The partition responds to
the exterior loop; for example, at $J=1$, $x=1$ it ranges from
$0.9160251472$ to $2.3613249509$ over the angle slice. This selects the
boundary-sensitivity branch of the orbit decision tree and shows that the
tree-exterior collapse does not persist when an exterior loop is present.

The rate qualification remains unresolved at this finite level. Every one of
the 108 rows is `INCONCLUSIVE`: 36 rows fail only the full-space residual
bound, 27 fail only the nested restriction-rank rule, and 45 fail both; the
largest full-space residual is $15.2349853487$ against the preregistered
$10^{-2}$ bound. The retained-rate numbers are therefore diagnostic
measurements rather than a uniform fibre estimate. The exact-vacuum fibre
rate, transported score, conditional-rate cutoff removal, uniform interacting
recovery, thermodynamic limit and continuum construction remain open.

### 9.25 Fixed-finite-graph character-cutoff form lemma

Character truncation can be removed on any one finite connected graph without
a spectral-separation assumption. The required estimate comes from positivity
of the complete Wilson potential, so it remains valid when a low character
threshold lies below a Ritz energy.

Let $\Gamma=(V,E)$ be a finite connected oriented graph with at least one
chord, let $T$ be a rooted spanning tree, and let $N_p$ be the number of
plaquette terms. On the gauge-invariant Haar space set

$$
\mathcal H_{\mathrm{gi}}
=L^2\!\left(SU(2)^E,dU_E\right)^{SU(2)^V},
\qquad
H_\Gamma(x)=K+xV_\Gamma,
\qquad
0\leq V_\Gamma\leq V_*I,
\quad
V_*=4N_p,
\quad x\geq0.
\tag{YM187}
$$

Here $K$ is the sum of nonnegative link Casimirs and
$V_\Gamma=\sum_p(2-\chi_{1/2}(U_p))$. For every nonroot vertex, let $g_v$ be
the ordered tree transport from the root to $v$. For each chord
$c=(s(c),t(c))$, define $h_c=g_{s(c)}U_cg_{t(c)}^{-1}$. Successive Haar
translations and inversions give the exact disintegration

$$
dU_E=\prod_{v\neq o}dg_v\prod_{c\notin T}dh_c,
\qquad
\mathcal H_{\mathrm{gi}}
\cong
L^2\!\left(SU(2)^{|E|-|V|+1},dh\right)^{\operatorname{Ad}SU(2)}.
\tag{YM188}
$$

Thus tree gauge introduces no field-dependent Jacobian. To compare electric
forms, put

$$
r_{tc}
=\mathbf 1_{\{t\in P_T(o,s(c))\}}
+\mathbf 1_{\{t\in P_T(o,t(c))\}},
\qquad
M_t=\sum_c r_{tc},
\qquad
C_{\Gamma,T}
=1+\max_c\sum_{t\in T}M_tr_{tc}
\leq1+4(|E|-|V|+1)(|V|-1).
\tag{YM189}
$$

Varying a chord link produces exactly one left-invariant chord derivative.
Varying a tree link produces $M_t$ left- or right-invariant chord derivatives
with orthogonal adjoint coefficients. Pointwise Cauchy–Schwarz, followed by
the sum over Lie-algebra directions, therefore gives

$$
\mathcal E_{\mathrm{ch}}(F)
\leq
\mathcal E_K(F)
\leq
C_{\Gamma,T}\mathcal E_{\mathrm{ch}}(F).
\tag{YM190}
$$

The form domains are equal with equivalent norms. Compactness of the chord
group then gives compact resolvent for $K$ and, because $V_\Gamma$ is bounded,
for $H_\Gamma(x)$. A graph with no chords has a one-dimensional
gauge-invariant space and satisfies the same spectral conclusion directly.

Let $P_C$ project onto gauge-invariant spin networks with doubled link spins
$n_e=2j_e\leq C$ on every edge, and let $Q_C=I-P_C$. The Peter–Weyl
projectors commute with $K$, have finite rank and exhaust its form domain.
They consequently form a core for $H_\Gamma(x)$, and the min–max principle
gives

$$
E_{m,C}(x)\downarrow E_m(x)
\qquad(C\to\infty)
\tag{YM191}
$$

for every fixed graph, coupling and eigenvalue index. This convergence does
not require the Wilson multiplication operator to commute with $P_C$.

The quantitative bound begins with the first excluded link Casimir:

$$
Q_CKQ_C\succeq\kappa_CQ_C,
\qquad
\kappa_C=\frac{(C+1)(C+3)}4.
\tag{YM192}
$$

If $S_m$ is the span of eigenvectors through $E_m$, positivity
$K\preceq H_\Gamma(x)$ implies, for every $u\in S_m$,

$$
\boxed{
\|Q_Cu\|_2^2
\leq
\frac{E_m(x)}{\kappa_C}\|u\|_2^2.
}
\tag{YM193}
$$

For a computable Ritz upper bound $R_m\geq E_m$, define
$\eta_{m,C}=R_m/\kappa_C$. Whenever $\eta_{m,C}<1$, $P_C$ is injective on
$S_m$. The bounded-potential estimate

$$
\left|
\langle P_Cu,V_\Gamma P_Cu\rangle
-\langle u,V_\Gamma u\rangle
\right|
\leq
V_*\left(2\sqrt{\eta_{m,C}}+\eta_{m,C}\right)\|u\|_2^2
\tag{YM194}
$$

and min–max on $P_CS_m$ yield

$$
\boxed{
0\leq E_{m,C}-E_m
\leq
\frac{
R_m\eta_{m,C}
+xV_*\left(2\sqrt{\eta_{m,C}}+\eta_{m,C}\right)
}{
1-\eta_{m,C}
}.
}
\tag{YM195}
$$

This proves form-core convergence, discarded-mass decay and an explicit Ritz
error bound at fixed $(\Gamma,x,m)$. The bound retains the potential
correction required by $[P_C,V_\Gamma]\neq0$. The deterministic
noncommuting control
$K=\operatorname{diag}(0,4)$,
$V=\left(\begin{smallmatrix}1&-1\\-1&1\end{smallmatrix}\right)$ and $x=1$
violates the estimate obtained by deleting that correction and satisfies
(YM195).

For the isolated square with a three-edge tree and one chord,
$C_{\Gamma,T}=4$ and equality holds in (YM190) on class functions. Its
character matrices are
$K_{nn}=n(n+2)$ and
$V_{nm}=2\delta_{nm}-\delta_{n,m+1}-\delta_{n,m-1}$.
The primary verifier passes 22/22 checks, including 84/84 general tail
inequalities and 67/67 applicable Ritz inequalities. The independent dense
reconstruction passes 18/18 checks and agrees with the tridiagonal spectra to
machine precision. Both receipts set `continuum_hypotheses_present` to
`false` and `clay_verdict` to `NULL`.

The theorem is pointwise in the finite graph and coupling. Its constants grow
with graph size, and (YM195) supplies no weak-coupling-uniform rate. It gives
no thermodynamic limit, lattice-spacing-uniform estimate, reflection-positive
Euclidean construction, Osterwalder–Schrader reconstruction or
regulator-independent mass gap.



### 9.26 Volume-uniform local cutoff density and the global-norm obstruction

Local character observables admit a graph-size-independent cutoff estimate.
Electric-energy-density control alone does not make whole-wavefunction norm
approximation volume uniform.

Let $\Gamma_L$ be the periodic cubic lattice of side $L\geq3$, so
$|E_L|=N_{p,L}=3L^3$, and let $H_L(x)=K+xV_L$ be the dimensionless
Hamiltonian in (YM187). Write $\Pi_{0,L}$ for its ground-space projector and
use the normalized ground-space density
$\rho_{0,L}=\Pi_{0,L}/\operatorname{Tr}\Pi_{0,L}$. The lattice symmetry acts
transitively on links and commutes with $\Pi_{0,L}$, so every link has the
same electric expectation. The normalized constant function is
gauge-invariant, has zero electric energy, and has plaquette expectation
$\langle2-\chi_{1/2}(U_p)\rangle=2$ by normalized Haar orthogonality.
Consequently,

$$
E_{0,L}(x)
\leq 2xN_{p,L},
\qquad
\operatorname{Tr}(\rho_{0,L}K)
\leq E_{0,L}(x),
\qquad
\boxed{
\operatorname{Tr}(\rho_{0,L}K_e)\leq2x
}
\quad(e\in E_L).
\tag{YM196}
$$

For a finite link set $S\subset E_L$, let $P_{C,e}$ retain doubled spins
$n_e=2j_e\leq C$ on link $e$, put
$P_{C,S}=\prod_{e\in S}P_{C,e}$, and set
$Q_{C,S}=I-P_{C,S}$. These link-Casimir projectors commute. The union bound
for commuting projections and the first excluded Casimir in (YM192) give the
operator inequality

$$
\boxed{
Q_{C,S}
\preceq
\sum_{e\in S}(I-P_{C,e})
\preceq
\frac1{\kappa_C}\sum_{e\in S}K_e,
\qquad
\kappa_C=\frac{(C+1)(C+3)}4.
}
\tag{YM197}
$$

The discarded local mass of the symmetric ground-space density therefore
satisfies

$$
\boxed{
\delta_{C,S}(L,x)
:=\operatorname{Tr}(\rho_{0,L}Q_{C,S})
\leq
b_{C,S}(x)
:=\frac{2x|S|}{\kappa_C}
=\frac{8x|S|}{(C+1)(C+3)}.
}
\tag{YM198}
$$

Whenever $b_{C,S}(x)<1$, normalize the locally truncated density by

$$
\rho_{0,L}^{(C,S)}
:=
\frac{P_{C,S}\rho_{0,L}P_{C,S}}
{\operatorname{Tr}(P_{C,S}\rho_{0,L})}.
$$

The gentle-measurement estimate, followed by normalization, yields

$$
\left\|
\rho_{0,L}^{(C,S)}-\rho_{0,L}
\right\|_1
\leq
2\sqrt{\delta_{C,S}}+\delta_{C,S}
\leq
2\sqrt{b_{C,S}}+b_{C,S}.
\tag{YM199}
$$

Thus every bounded observable $A$ supported on $S$ obeys

$$
\boxed{
\left|
\operatorname{Tr}\!\left[
A\left(\rho_{0,L}^{(C,S)}-\rho_{0,L}\right)
\right]
\right|
\leq
\|A\|\left(2\sqrt{b_{C,S}}+b_{C,S}\right),
}
\tag{YM200}
$$

uniformly in $L$. At fixed $x$ and fixed $S$, the right-hand side tends to
zero as $C\to\infty$. Since $x=2/g^4$ grows on a weak-bare-coupling
trajectory, a joint auxiliary-cutoff schedule also has vanishing local error
whenever

$$
x_k\longrightarrow\infty,
\qquad
C_k\longrightarrow\infty,
\qquad
\boxed{
\frac{C_k^2}{x_k}\longrightarrow\infty.
}
\tag{YM201}
$$

This is a sufficient character-cutoff schedule for the local estimate. It is
not a weak-coupling field estimate and does not construct a limiting vacuum.

The corresponding whole-wavefunction statement fails under an energy-density
hypothesis. Let $P_C^{\mathrm{all}}$ retain doubled spins at most $C$ on every
link and put $Q_C^{\mathrm{all}}=I-P_C^{\mathrm{all}}$. Choose $N$
edge-disjoint elementary plaquettes, use the constant wavefunction on every
unused link and, for $0<q<1$, define the normalized class function and
gauge-invariant product state

$$
f_q(U)
=
\sqrt{1-q^2}
\sum_{n=0}^{\infty}q^n\chi_{n/2}(U),
\qquad
\Psi_{q,N}
=
\prod_{r=1}^{N}f_q(U_{p_r}).
\tag{YM202}
$$

Character orthogonality and edge disjointness give

$$
\boxed{
\frac1N
\langle\Psi_{q,N},K\Psi_{q,N}\rangle
=
\frac{q^2(3-q^2)}{(1-q^2)^2},
\qquad
\|P_C^{\mathrm{all}}\Psi_{q,N}\|_2^2
=
\left(1-q^{2(C+1)}\right)^N.
}
\tag{YM203}
$$

The loops occupy $4N$ distinct links, so the electric-energy density is at
most one quarter of the displayed finite energy per loop, independently of
$N$. Nevertheless, at every fixed $C$,

$$
\boxed{
\|Q_C^{\mathrm{all}}\Psi_{q,N}\|_2^2
=
1-\left(1-q^{2(C+1)}\right)^N
\longrightarrow1
\qquad(N\to\infty).
}
\tag{YM204}
$$

For fixed $0<q<1$ and $0<\varepsilon<1$, the exact least nonnegative cutoff
with retained squared norm at least $1-\varepsilon$ is

$$
\boxed{
C_{\min}(N,q,\varepsilon)
=
\max\!\left\{
0,\,
\left\lceil
\frac{
\log\!\left(1-(1-\varepsilon)^{1/N}\right)
}{
2\log q
}
-1
\right\rceil
\right\}
=\Theta(\log N).
}
\tag{YM205}
$$

The frozen protocol
`computations/yang-mills-local-cutoff-density-prereg.md` evaluates 1,536
local rows, seven auxiliary joint-cutoff rows and 180 product-family rows.
The primary verifier passes 16/16 checks; the source-independent JavaScript
reconstruction passes 17/17 and agrees on every row. Exactly 1,152 local rows
meet the declared $b_{C,S}<1$ applicability condition, the maximum
fixed-$(x,|S|,C)$ spread over all eight volumes is zero, and the firing row
$(q,C,N)=(1/2,2,512)$ has discarded norm
$0.9996850695596114>0.999$.

Equations (YM196)–(YM205) control fixed-support observables of the symmetric
finite-volume ground-space density and exclude global norm control from
energy density alone. Their volume-uniform local estimate is the tightness
input for the conditional fixed-regulator subsequence construction in
§9.27. They supply no clustering theorem, reflection-positive Euclidean
measure, Osterwalder–Schrader reconstruction, lattice-spacing limit or
physical mass gap.


### 9.27 Fixed-regulator thermodynamic ground-state subsequence

Fix $x\geq0$ and use periodic cubic lattices with $L\to\infty$. On every
finite lattice, $K$ is a sum of Laplace–Beltrami operators on the compact
configuration manifold $SU(2)^{E_L}$ and has compact resolvent. The Wilson
potential $xV_L$ is bounded. Restriction to the closed gauge-invariant
subspace therefore leaves a self-adjoint Hamiltonian with a finite-rank
ground-space projector. Let

$$
\rho_{0,L;S}
:=
\operatorname{Tr}_{E_L\setminus S}\rho_{0,L}
$$

be its reduction to a fixed finite link set $S$. The one-link Peter–Weyl
cutoff in §9.26 has

$$
\boxed{
d_C
:=
\operatorname{rank}P_{C,e}
=
\sum_{n=0}^{C}(n+1)^2
=
\frac{(C+1)(C+2)(2C+3)}6,
\qquad
\operatorname{rank}P_{C,S}=d_C^{|S|}<\infty.
}
\tag{YM206}
$$

The unnormalized gentle-measurement inequality and (YM198) give

$$
\boxed{
\left\|
\rho_{0,L;S}
-
P_{C,S}\rho_{0,L;S}P_{C,S}
\right\|_1
\leq
2\sqrt{\operatorname{Tr}(\rho_{0,L;S}Q_{C,S})}
\leq
2\sqrt{\frac{8x|S|}{(C+1)(C+3)}}.
}
\tag{YM207}
$$

The compressed positive trace-class ball

$$
\mathcal D_{C,S}
:=
\left\{
\tau\succeq0:
\tau=P_{C,S}\tau P_{C,S},\
\operatorname{Tr}\tau\leq1
\right\}
\tag{YM208}
$$

is compact in trace norm because it lies in the operator space on a Hilbert
space of dimension $d_C^{|S|}$. Given $\varepsilon>0$, first choose $C$ so
that the right-hand
side of (YM207) is at most $\varepsilon/2$, then cover
$\mathcal D_{C,S}$ by finitely many trace-norm balls of radius
$\varepsilon/2$. Thus

$$
\boxed{
\left\{
\rho_{0,L;S}:L\ \text{sufficiently large}
\right\}
\quad\text{is relatively compact in trace norm.}
}
\tag{YM209}
$$

Choose nested finite link sets
$S_1\subset S_2\subset\cdots$ exhausting the infinite cubic lattice. Repeated
subsequence extraction followed by the Cantor diagonal choice gives volumes
$L_k\to\infty$ and density matrices $\rho_{\infty,S_m}$ such that

$$
\boxed{
\rho_{0,L_k;S_m}
\longrightarrow
\rho_{\infty,S_m}
\quad\text{in trace norm for every fixed }m.
}
\tag{YM210}
$$

Finite-volume partial traces are compatible, and partial trace is
trace-norm contractive. Passing to the limit gives

$$
\boxed{
\operatorname{Tr}_{S_{m+1}\setminus S_m}
\rho_{\infty,S_{m+1}}
=
\rho_{\infty,S_m}.
}
\tag{YM211}
$$

For a bounded local observable $A$ supported in $S_m$, define

$$
\boxed{
\omega_x(A)
:=
\operatorname{Tr}(\rho_{\infty,S_m}A).
}
\tag{YM212}
$$

Equation (YM211) makes this independent of the chosen containing set. It is
a normalized positive state on the quasi-local algebra and is locally normal
by construction. Gauge, translation and cubic symmetries of the normalized
finite-volume ground-space densities pass to the local limits.

It remains to retain the ground-state property. Let $A$ belong to the
gauge-invariant finite-character local $*$-algebra. For all sufficiently
large $L$, locality makes $[H_L(x),A]$ independent of $L$ on one fixed
enlarged support; call the resulting bounded local commutator
$\mathcal G_x(A)$. Since $\rho_{0,L}$ is supported on the ground space,

$$
\operatorname{Tr}
\left(
\rho_{0,L}A^*[H_L(x),A]
\right)
=
\operatorname{Tr}
\left(
\rho_{0,L}A^*(H_L(x)-E_{0,L})A
\right)
\geq0.
$$

Trace-norm convergence on the enlarged support now gives

$$
\boxed{
\omega_x\!\left(A^*\mathcal G_x(A)\right)\geq0
\qquad
\text{for every gauge-invariant finite-character local }A.
}
\tag{YM213}
$$

This is the algebraic ground-state condition at fixed lattice regulator and
fixed $x$. The argument constructs at least one subsequential locally normal
ground state; it does not select a phase or show convergence of the complete
periodic-volume sequence. The alternating-state control in (YMT12) retains
two cluster points, the escaping Peter–Weyl sectors in (YMT13) show why the
energy bound is essential for trace-norm tightness, and the ferromagnetic
one-magnon bound in (YMT14) shows that thermodynamic ground-state existence
does not imply a positive uniform gap.

The frozen protocol
`computations/yang-mills-thermodynamic-ground-state-prereg.md` assigns a
narrower role to its executable evidence. The primary verifier passes 18/18
checks over 36 rank rows, 100 compactness rows, 12 synthetic finite-matrix
ground identities and all three firing controls. The largest selected cutoff
is $C=4095$; the nested partial-trace discrepancy is
$1.1102230246251565\times10^{-16}$, and the largest direct-versus-spectral
fixture discrepancy is $3.609612342034603\times10^{-15}$. The independent
JavaScript reconstruction passes 19/19 checks and agrees exactly on the rank,
compactness, escaping-sector and gap rows; its largest ground-fixture
difference from the primary calculation is
$1.7763568394002505\times10^{-15}$.

Both receipts classify this evidence as
`FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE`. They record
the interacting finite-volume ground densities and (YMT2) as analytic inputs
outside the executable proof surface, with
`thermodynamic_state_constructed_by_verifier=false`,
`uniform_mass_gap_established=false`,
`continuum_hypotheses_present=false` and `clay_verdict=NULL`. The executable
scope contains no interacting $SU(2)$ ground-state construction or spectral
mass-gap estimate.

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
| Continuous-$SU(2)$ isolated-square Feshbach pencil and bounds (YM57)–(YM77) | **Derived** for the regulated class-function operator | Exact energy-dependent self-energy retained; no many-plaquette or volume-uniform implication |
| Fixed-level weak-coupling square spectrum (YM78)–(YM81) | **Derived** | The physical $2\sqrt2/a$ leading spacing is an isolated ultraviolet plaquette normalization |
| Finite-scaled-cutoff form limits and fixed-window isolation (YM82)–(YM89) | **Derived** | Fixed $N/x^{1/4}=C$ isolates through the exact Feshbach self-energy but does not make the bare compression converge |
| Bare character-cutoff theorem (YM90) | **Derived** | For every fixed low level, bare spectral convergence and vanishing discarded mass hold iff $N/x^{1/4}\to\infty$, equivalently $gN\to\infty$ |
| Fixed fundamental-boundary internal Gauss fibre (YM91)–(YM96) | **Derived** within established $SU(2)$ representation theory | Exactly 14 states for $j_{\max}\geq1$; Wilson multiplication exits the fixed boundary sector |
| Poincaré/link-sphere geometry and exact two-scale recurrence (YM99)–(YM125) | **Derived** finite-regulator geometry and **Derived conditional** Poincaré theorem | Exact marginal interactions enter through \((\lambda_{\mathrm{fib}},\kappa,\lambda_c)\); (YM125) is the sufficient $L^2$-score target and its weak-coupling scale-uniform bounds remain open |
| Conditional $H^{-1}$ score recurrence and exact margin transfer (YM126)–(YM151) | **Derived conditional** finite-regulator theorem | The inverse-generator score norm retains vertical cancellations and is no weaker than the $L^2$ covariance estimate; its exact-vacuum uniform bound remains open |
| Residual recovery Gramian and score-penalty separation (YM152)–(YM170) | **Derived conditional** finite-regulator theorem | $A_{\mathrm{AT}}^{\mathrm{opt}}=\gamma_{\mathrm{rec}}^{-1}$ and $\lambda_{\mathrm{gi}}\geq\gamma_{\mathrm{rec}}\lambda_{\mathrm{loc}}/\rho$; the score operator is a separate upper penalty on coarse tangents, and uniform exact-vacuum recovery and score bounds remain open |
| Finite-level martingale transport criterion (YM171)–(YM182) | **Derived conditional** finite-regulator theorem | Full-filtration/gauge-domain identity, energy comparison, and uniformly controlled weighted transport operator are required; exact Yang–Mills shell, recovery and weak-coupling bounds remain open |
| Tree-exterior boundary independence and nodal Ritz obstruction (YM183)–(YM186) | **Derived** finite-regulator identity and **Derived** obstruction | A tree exterior collapses every scheduled boundary angle to one fibre; the projected Ritz density makes the cutoff measure's conditional gap vanish identically at the rows carrying a resolved path sign change, and the twelve-row path and two-parameter torus families confine that zero-gap region to the strong-coupling rows; the exact-vacuum fibre rate remains required |
| Fixed-graph character-cutoff form theorem (YM187)–(YM195) | **Derived** within every fixed finite regulated graph | Exact tree-gauge Haar disintegration, equivalent electric forms, form-core convergence, separation-free discarded-mass bound and noncommuting Ritz-error bound; constants are not uniform in graph size, coupling or lattice spacing |
| Volume-uniform local cutoff density and global-norm obstruction (YM196)–(YM205) | **Derived** local finite-volume theorem and **Derived** obstruction | On periodic cubic lattices, every fixed-support ground-density observable has a character-cutoff error uniform in volume; bounded electric energy density alone cannot control whole-wavefunction cutoff norm. Its executable receipt constructs no thermodynamic or continuum state; §9.27 uses the analytic bound as an input |
| Fixed-regulator thermodynamic ground-state subsequence (YM206)–(YM213) | **Derived conditional** operator theorem with finite-identity controls | Finite-volume ground densities and the volume-uniform local tail estimate are analytic inputs; a diagonal subsequence is locally normal and satisfies the finite-character algebraic ground condition, while full-sequence convergence, uniqueness, clustering, a uniform gap and every continuum limit remain open |
| Loop-carrying exterior bowtie fibre probe | **INCONCLUSIVE** finite-cutoff measurement | The eight-link exterior plaquette produces boundary-sensitive conditional partitions, but all 108 retained-rate rows fail a residual or nested-rank qualification rule; the exact-vacuum fibre rate, transport score, conditional-rate cutoff removal and continuum construction remain open |
| Finite open-cube SU(2) basis and oriented Wilson support | **Derived** finite-regulator construction | The open $2\times2\times2$ cube has 32 and 1013 gauge-invariant raw trivalent-$3j$ states at doubled cutoffs $C=1,2$; every six signed fundamental plaquette operators has 32 and 2388 nonzero candidate-supported directed entries, with finite Hermitian contractions; fixed-graph character-cutoff removal follows from (YM187)–(YM195), while a growing open-boundary family and continuum control remain open |
| Larger-volume/cutoff SU(2) Hamiltonian | **Derived** recovered finite-regulator construction and fixed-graph cutoff removal; **INCONCLUSIVE** frozen separation qualifications | The open $3\times2\times2$ graph has 868 and 955835 complete gauge-invariant states at doubled cutoffs $C=1,2$; the recovery enforces spectator-intertwiner orthogonality, all 226 finite-construction checks and 256 independent checks pass, every scheduled ground energy is nonnegative, and the separation-free theorem removes the character cutoff only after this graph and coupling are fixed |
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

The isolated-square radial Feshbach version-3 protocol in
`computations/yang-mills-radial-feshbach-v3-prereg.md` is implemented by
`computations/verify_yang_mills_radial_feshbach_v3.py` and the
source-independent JavaScript reconstruction
`computations/verify_yang_mills_radial_feshbach_v3_independent.mjs`. It
preserves all five declared cutoff schedules and uses the dimension-valid
finite-section rule
$
q(N)=\min\{3,N+1\}
$
for the requested Ritz values. The `grow` and `half` rows at $x=1/4$
therefore retain their scheduled cutoff $N=1$ and request only levels $0$ and
$1$.

The canonical `verification-final.json` passes **62 top-level checks** and records
8 symbolic rows, 24 determinant rows, 131 continued-fraction rows, 262
finite-tail rows, 15 resolvent rows, 18 reference-eigenvector rows, 12
continuous-angle spectrum rows, 30 cutoff rows containing 88 requested Ritz
values, and 6 Feshbach reconstructions. The canonical
`verification-independent-final.json` passes **20 independent checks**,
including source/snapshot binding, a continuous-angle Dirichlet spectrum,
direct tail solves, sign-preserving Sturm/bisection finite-section
reconstruction, doubled-reference convergence, Feshbach reconstruction and
weak-coupling landmarks.
The maximum independent continuous-angle discrepancy from the primary
spectrum is $7.37637628637\times10^{-11}$. All 88 independently reconstructed
finite-section eigenvalues are bit-identical to the primary serialized
binary64 values.
The largest normalized error across all independently reconstructed retained
masses, discarded masses and boundary residuals is
$1.11022302463\times10^{-15}$.

Across the five frozen cutoff schedules, the largest primary relative errors
against the doubled-terminal low spectrum are
$0.948000338655$ (fixed),
$0.478050400541$ ($C=2$),
$0.00395035778556$ (fixed-window isolation),
$0.0136990350912$ (growing), and
$0.0136990350912$ (square-root). These finite rows support numerical controls
only. The exact Feshbach transfer, operator bounds, fixed-level weak-coupling
asymptotics and character-cutoff limit are established separately by the
operator-domain and form arguments in §§9.18.1–9.18.7. The receipts leave
their analytical-reconciliation fields `REQUIRES_ANALYTICAL_RECONCILIATION`
or `UNRESOLVED`; they do not promote a finite calculation into a limiting
proof.

The required `v2-rejection-final.json` has status **FAIL** because the version-3
checker rejects the version-2 schema, manifest and source identities and
detects the two incompatible $N=1$ row shapes. The status is the prescribed
version-isolation outcome and carries no scientific classification. The
qualified artifacts, adjacent manifest, frozen source snapshots, receipt
audit, source-only analytical review and publication seal are in
`runs/yang_mills_radial_feshbach_v3/`. Interacting
refined fibres, volume-uniform weak-coupling resolvent control, the
thermodynamic limit, the four-dimensional continuum quantum field, a
regulator-independent mass gap and Cassi microscopic identification remain
**UNRESOLVED**.

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

The Poincaré-geometry recurrence protocol in
`computations/yang-mills-poincare-geometry-prereg.md` is implemented by
`computations/verify_yang_mills_poincare_geometry.py` and the independent
JavaScript reconstruction
`computations/verify_yang_mills_poincare_geometry_independent.mjs`.
The primary receipt passes **118 checks** over 12 spatial-sphere spectral
rows, 5 link-Casimir rows, 18 Wilson-Hessian rows, 8 blocking-geometry rows,
8 recurrence rows, 3 physical-scaling rows and 6 induction rows. Its largest
Wilson-Hessian, horizontal/vertical orthogonality, electric-energy
reconstruction and recurrence discrepancies are respectively
$5.29412608197\times10^{-9}$,
$4.44089209850\times10^{-15}$,
$1.42108547152\times10^{-14}$ and
$1.77635683940\times10^{-15}$.

The implementation-independent receipt passes **90 checks** and binds the
frozen protocol, both verifier sources and the primary receipt by SHA-256.
It uses the schedule vectors and measurements stored in the primary receipt,
then re-evaluates the sphere and character spectra, quaternion geodesics,
adjoint blocking geometry, connection term, generalized-eigenvalue
recurrence, physical rescaling and semidefinite induction decisions without
importing the Python implementation. It also asserts the frozen tolerances
and audits the primary per-check array, row summaries and reported maxima.
This is an independent implementation and receipt-integrity check, not
independent sample generation or a second scientific execution. The receipts
are `runs/yang_mills_poincare_geometry/verification.json` and
`runs/yang_mills_poincare_geometry/verification-independent.json`.
The finite controls classify **PASS**. Equations (YM99)–(YM124) are
analytical statements proved in §9.20; the checks guard their fixed formulas
and normalization. Equation (YM125) is the sufficient $L^2$-score target,
while (YM151) is its sharper conditional-transport alternative. Uniform
weak-coupling control of either route, the thermodynamic limit and the
continuum mass gap remain **UNRESOLVED**.

The conditional transport-score protocol
`computations/yang-mills-transport-score-prereg.md` is implemented by
`computations/verify_yang_mills_transport_score.py` and the independent
JavaScript reconstruction
`computations/verify_yang_mills_transport_score_independent.mjs`.
The primary receipt passes **86 checks** across 10 finite-chain rows, 2
Gaussian fixtures, 10 physical-margin rows and 2 alias-symbol rows. Its
largest normalized matrix and scalar discrepancies are respectively
$5.33638658877\times10^{-15}$ and
$2.13450577681\times10^{-16}$. Every chain and fixture recurrence check
reconstructs both the $H^{-1}$ and covariance-relaxed generalized
eigenvalues.

The independent receipt passes **32 checks**, constructs every chain square
root from the discrete-sine basis, uses separate Jacobi and pivoted-solve
algorithms, and binds the frozen protocol, both sources and primary receipt
by SHA-256. Its largest recorded row-level normalized discrepancy is
$6.08774906355\times10^{-14}$. The receipts are
`runs/yang_mills_transport_score/verification.json` and
`runs/yang_mills_transport_score/verification-independent.json`.

The read-only protocol audit
`runs/yang_mills_transport_score/analytical-review.json` and the
post-transcription theorem audit
`runs/yang_mills_transport_score/theorem-review.json` both classify
**VALID**. The latter recomputes (YM126)–(YM151), including the weak
divergence sign, zero-score branch, dual pairing, margin edge cases,
Gaussian factors, alias phase boundary, continuous-zone extrema and
massless infrared qualification.

The strict fixture has
$\vartheta^2=1/9$ and
$\kappa^2/\lambda_{\mathrm{fib}}=1$: the $H^{-1}$ lower bound is
$0.961295942106$, the covariance-relaxed bound is $0.737912651870$, and the
exact anisotropic Gaussian rate is $1$. In all 10 even/odd chain rows the two
score coefficients agree to
$7.77156117238\times10^{-16}$ and the recurrence reproduces the exact
anisotropic Gaussian rate to
$1.66533453694\times10^{-15}$. At $N=64$, the massless row has
$(\lambda_c,\lambda_{\mathrm{fib}},\vartheta)
=(0.188747776607,2.04774351863,0.952799273901)$, while the formal infinite
symbol retains $\lambda_{\mathrm{fib}}=2$, $\vartheta=1$ and zero coarse
symbol.

The finite controls classify **PASS**. They verify the fixed Gaussian,
matrix, margin and symbol calculations. Equations (YM126)–(YM151) carry the
analytical conditional theorem. No receipt supplies a transport field or a
volume- and weak-coupling-uniform bound for the exact Yang–Mills vacuum, so
the thermodynamic limit, continuum construction and physical mass gap remain
**UNRESOLVED**.

The residual-recovery protocol
`computations/yang-mills-recovery-gramian-prereg.md` is implemented by
`computations/verify_yang_mills_recovery_gramian.py` and the independent
JavaScript reconstruction
`computations/verify_yang_mills_recovery_gramian_independent.mjs`.
The source-bound primary receipt passes **58 checks** across four
near-parallel rows, orthogonal and gauge-quotient controls, four score rows,
the product counterexample, ten Gaussian chains and one transported
quotient-Gramian fixture. Its largest normalized matrix and scalar errors are
$5.33638658877\times10^{-15}$ and
$1.71390679427\times10^{-15}$.

The qualified independent receipt passes **30 checks**, reconstructs the
fixed matrices with a separate Jacobi eigensolver and sine basis, and binds
the frozen protocol, both sources and the primary receipt by SHA-256. Its
independently reconstructed matrix and scalar maxima are
$1.62353873949\times10^{-14}$ and
$7.77156117238\times10^{-16}$; its largest row comparison error is
$5.02862203952\times10^{-14}$. The receipts are
`runs/yang_mills_recovery_gramian/verification.json` and
`runs/yang_mills_recovery_gramian/verification-independent.json`.
The authoritative receipt pair binds the frozen protocol, both verifier
sources and the unchanged primary receipt. The read-only protocol audit
`analytical-review.json` and post-transcription audit `theorem-review.json`
both classify **VALID**.

The finite controls classify **PASS**. Equations (YM152)–(YM170) carry the
analytical conditional theorem. A lower recovery floor on physical functions
and an upper transported-score bound on coarse tangents are separate
requirements. No receipt supplies either estimate uniformly for the exact
interacting Yang–Mills vacuum, so the thermodynamic limit, continuum
construction and physical mass gap remain **UNRESOLVED**.

The finite-level martingale transport criterion in §9.22.7 is an analytical
conditional extension of the shell estimates. It has no separate preregistered
protocol or receipt: (YM171)–(YM180), including the displayed energy
comparison, are proved from their displayed form-domain and transport
hypotheses, while (YM181)–(YM182) are exact post-protocol Gaussian diagnostics.
These formulas do not extend the 58-check or 30-check recovery receipts. The
exact-vacuum shell, recovery and
weak-coupling transport bounds remain **UNRESOLVED**.

The exact-block first-target study in §9.23 is bound by SHA-256 to the frozen
protocol `computations/yang-mills-exact-block-spectral-prereg.md`, the source
`computations/verify_yang_mills_exact_block_spectrum.py` and the shared
representation helper `computations/yang_mills_conditional_algebra.py`. Its
receipt `runs/yang_mills_exact_block_spectrum/verification.json` holds 20
Ritz rows, 180 scheduled boundary rows and the analytic nodal control, with
partition, Gram, Dirichlet and boundary-spread deviations at the
$10^{-15}$–$10^{-16}$ level. All 180 boundary rows classify `INCONCLUSIVE`
under the literal preregistered rules, no row qualifies, and the study issues
no score or margin verdict because the transport score lies outside its
first implementation target. It extends neither the 58-check nor the
30-check recovery receipts, and the exact-vacuum fibre rate, transport score,
conditional-rate cutoff removal, uniform interacting recovery, thermodynamic
limit and continuum construction remain **UNRESOLVED**.

The schedule-wide nodal family of §9.23 is bound in the same way to the
frozen protocol `computations/yang-mills-nodal-family-prereg.md`, the source
`computations/verify_yang_mills_nodal_family.py` and the shared helper. Its
receipt `runs/yang_mills_nodal_family/verification.json` holds twelve rows
with two 49-point block paths each, reproduces the sealed nodal control to
$4.4\times10^{-16}$, keeps the path amplitudes real to $8.5\times10^{-18}$
relative, and returns `NODAL_CONFINED`: seven rows carry a resolved sign
change, five of them with odd parity, and the five witness-free rows sit at
$x=1/4$ plus $x=1$ for $J\geq2$. The decision tree of the frozen protocol,
not the raw count, supplies the classification. The probe makes no
conditional-rate cutoff-removal, exact-vacuum or continuum statement. Its
two-parameter torus
extension (`computations/yang-mills-nodal-surface-prereg.md`,
`computations/verify_yang_mills_nodal_surface.py`, receipt
`runs/yang_mills_nodal_surface/verification.json`) searches all 66 grid lines
of a $33\times33$ block grid per row, reproduces both one-parameter lines at
the seventeen common angles to $7.1\times10^{-15}$, and returns
`WITNESS_CONFINED`: the same seven rows carry resolved sign changes and the
same five rows carry none.

The loop-carrying bowtie study in §9.24 is bound by the frozen protocol
`computations/yang-mills-bowtie-fibre-prereg.md`, the source
`computations/verify_yang_mills_bowtie_fibre.py`, the seven-link reference
`computations/verify_yang_mills_exact_block_spectrum.py` and the shared helper
`computations/yang_mills_conditional_algebra.py`. Its receipt
`runs/yang_mills_bowtie_fibre/verification.json` contains 108 rows at
$J=1,2,3$, four couplings and nine boundary angles. The source and protocol
digests are
`19e3208831ce4af966cd6de8e0079e083ea55602e0d3fb1f132b71227bfb63ef` and
`b71f184c0c45c9eacb58e0756758baacca825bf18c951ffb651591dd76d714ae`;
the receipt also binds the shared algebra and reference-source hashes. All
seven analytic controls pass. The partition varies with the exterior loop,
while every retained-rate row is `INCONCLUSIVE`: 36 rows fail only the
full-space residual bound, 27 fail only the nested-rank rule and 45 fail
both. No exact-vacuum fibre, transport-score, conditional-rate cutoff-removal,
uniform recovery, thermodynamic or continuum conclusion follows.

The finite-volume Wilson Schwinger bridge is bound by the frozen protocol
`computations/yang-mills-su2-wilson-2d-prereg.md`, the primary
`computations/verify_yang_mills_su2_wilson_2d.py` and the independent
reconstruction `computations/verify_yang_mills_su2_wilson_2d_independent.mjs`.
The primary receipt
`runs/yang_mills_su2_wilson_2d/verification.json` passes 876/876 checks
across 108 coupling, spatial-length, temporal-length and character-cutoff
rows. It evaluates the gauge-projected character transfer spectrum, the
fundamental-character correlator at four temporal separations, the exact
effective-mass identity and the analytic character-tail bound. The independent
receipt `runs/yang_mills_su2_wilson_2d/verification-independent.json` passes
120/120 checks from the positive Bessel series and binds both verifier sources
and the primary receipt by SHA-256. This establishes a finite-volume
two-dimensional Wilson benchmark; four-dimensional spatial-volume growth,
thermodynamic construction, OS reconstruction and the physical mass gap remain
**UNRESOLVED**.

The finite open-cube SU(2) pilot is bound by the frozen protocol
`computations/yang-mills-su2-open-cube-prereg.md`, the primary
`computations/verify_yang_mills_su2_open_cube.py` and the shared exact
representation helper `computations/verify_yang_mills_exact_block_spectrum.py`.
Its receipt `runs/yang_mills_su2_open_cube/verification.json` passes 69/69
checks. The two cutoffs contain 32 and 1013 gauge-invariant raw trivalent
$3j$ states. Each of the six signed cyclic fundamental plaquette words has
32 nonzero candidate-supported directed entries at $C=1$ and 2388 at $C=2$.
The largest Hermiticity and dagger residual is
$5.55\times10^{-17}$, and the deterministic forbidden-pair samples vanish.
This supplies a finite three-dimensional operator layer. The form theorem in
§9.25 removes the character cutoff after this graph and coupling are fixed.
A volume-uniform estimate for this growing open-boundary family,
weak-coupling control, thermodynamic construction, OS reconstruction and a
physical mass gap remain **UNRESOLVED**.

The larger-volume construction is governed by the scientific protocol
`computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md` and the
spectator-channel recovery protocol
`computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`.
It uses a $3\times2\times2$ open graph with twenty links and eleven
plaquettes, a complete sequential binary-coupling basis at every vertex,
link cutoffs $C=1,2$, and
$x\in\{1/64,1/16,1/4,1\}$. The basis dimensions are 868 and 955835.

The recovered primary receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json`
passes all 226 finite-construction checks. Its 234/238 aggregate count
contains four non-gating failed tail-separation checks at $x=1/4$ and $x=1$
for both cutoffs. The independent receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification-independent.json`
passes 256/256 checks and reconstructs the basis hashes, plaquette matrix
hashes and counts, Wilson extrema, Ritz energies, shell norms and recovery
invariants.

The frozen $yz_{x0}$ firing control reduces the edge-only candidate column
from 80 states to five and its normalized squared norm from $16$ to $1$.
The lexicographically selected remote channel has zero intertwiner overlap
and zero recovered matrix element at spectator vertex 6. The largest
normalized squared plaquette-column norm is $1$ at $C=1$ and $2$ at $C=2$.
The Wilson-sum spectra lie in
$[-5.89211600962,5.89211600962]$ and
$[-11.1908496223,11.1908496223]$, respectively, inside the required
$[-22,22]$ interval. All eight scheduled ground energies are nonnegative;
the $C=2$ values range from $0.342854829715$ at $x=1/64$ to
$18.5248301195$ at $x=1$.

Every aggregate separation-based cutoff qualification is `INCONCLUSIVE`. The
sole useful individual row is the $C=1$, $x=1/64$ exact-shell bound; the
corresponding $C=2$ analytic ratio is $0.100890916829$, above the frozen $0.1$
threshold. The edge-only external receipts bound in
`runs/yang_mills_continuum_boundary_audit/verification.json` are excluded from
Hamiltonian and tail evidence because they omit the spectator-channel
Kronecker deltas.

The separation-free theorem in §9.25 independently establishes
character-cutoff removal on this fixed graph at each fixed coupling. Its
primary receipt
`runs/yang_mills_finite_graph_cutoff_form/verification.json` passes 22/22
checks, including 84/84 tail and 67/67 applicable Ritz inequalities. The
independent receipt
`runs/yang_mills_finite_graph_cutoff_form/verification-independent.json`
passes 18/18 checks and reconstructs all 84 spectral rows. Both receipts record
`continuum_hypotheses_present=false` and `clay_verdict=NULL`. These
fixed-graph receipts supply no growing-graph rate. Section 9.26 gives
fixed-support spatial-volume uniformity on periodic cubic lattices. Section
9.27 uses that estimate in a conditional fixed-regulator diagonal-subsequence
argument; weak-coupling field control, OS reconstruction and the physical
mass gap remain **UNRESOLVED**.

The local-density extension in §9.26 is bound by
`computations/yang-mills-local-cutoff-density-prereg.md`, the primary
`computations/verify_yang_mills_local_cutoff_density.py` and the independent
`computations/verify_yang_mills_local_cutoff_density_independent.mjs`. The
primary receipt passes 16/16 checks over 1,536 local rows, seven auxiliary
joint-cutoff rows and 180 product-family rows. The independent receipt passes
17/17 checks and reconstructs every primary value exactly. Of the local rows,
1,152 satisfy $b_{C,S}<1$; their fixed-parameter spread across
$L\in\{3,4,6,8,12,16,24,32\}$ is zero. The product-family firing control has
discarded global norm $0.9996850695596114$.

Both receipts bind protocol SHA-256
`69fe2a132dbccec4484bb6fc5f3d1b75dc95e88d5de7687774ab17e69c0e6789`.
The primary and independent source hashes are
`9584c4027c4be798c0a9687da78e1a977bba255ee1323bde76086022ddc4ec2c`
and
`f20a0e8c8e08b3081aa796ac827d3748561d7eac395b9374d9dc529e650933c1`;
the independent receipt binds primary-receipt SHA-256
`7c90eb75f7d50965eae5edad2183a7ae6074fbf82c72e2481d68197c5880aae1`.
Both local-cutoff receipts set `thermodynamic_limit_constructed=false`,
`continuum_hypotheses_present=false` and `clay_verdict=NULL`. Their executable
scope establishes the finite identities behind the graph-size-independent
fixed-support cutoff error. The thermodynamic operator argument in §9.27
retains the finite-volume ground densities and (YM198) as analytic inputs.

The thermodynamic evidence is bound by
`computations/yang-mills-thermodynamic-ground-state-prereg.md`, the primary
`computations/verify_yang_mills_thermodynamic_ground_state.py` and the
independent
`computations/verify_yang_mills_thermodynamic_ground_state_independent.mjs`.
The primary receipt passes 18/18 checks over 36 rank rows, 100 compactness
rows, 12 synthetic finite-matrix identities and three implication controls.
The independent receipt passes 19/19 checks, reconstructing all keyed
schedules with zero rank, compactness, escaping-sector and gap discrepancy.
Its maximum ground-fixture discrepancy is
$1.7763568394002505\times10^{-15}$.

Both thermodynamic receipts bind protocol SHA-256
`200217b92778d4d30551b7a655fa7e1af38ab9dbd7948f7395097ef08874bf87`.
The primary and independent source hashes are
`9ca6f3dabf8e1eb8acbb015e40c5b4fabcc9bd3f5cdfc201a5a98f23231f1adc`
and
`519bc5e8bdc0373b63b8d67e83647d88819ef5f5111378a86b79daa3b084cb07`;
the independent receipt binds primary-receipt SHA-256
`713849eb0863a5b3e69865388e64d46641d4fa41447cf8d4588e35bb58944e73`.
Both record
`operator_argument_scope=CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2`,
`thermodynamic_state_constructed_by_verifier=false`,
`uniform_mass_gap_established=false`,
`continuum_hypotheses_present=false` and `clay_verdict=NULL`.

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
- `computations/yang-mills-radial-feshbach-v3-prereg.md`—frozen
  operator-domain, weak-coupling, variable-Ritz and character-cutoff protocol
- `computations/verify_yang_mills_radial_feshbach_v3.py`—62-check source-bound
  radial Feshbach and cutoff controls
- `computations/verify_yang_mills_radial_feshbach_v3_independent.mjs`—20-check
  independent continuous-angle, continued-fraction, finite-section and
  cutoff-metric reconstruction
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
- `computations/yang-mills-poincare-geometry-prereg.md`—frozen spatial,
  link-curvature, horizontal-connection, recurrence and physical-induction
  obligations
- `computations/verify_yang_mills_poincare_geometry.py`—118-check
  source-bound geometry and recurrence verifier
- `computations/verify_yang_mills_poincare_geometry_independent.mjs`—90-check
  implementation-independent reconstruction and receipt-integrity audit
- `computations/yang-mills-transport-score-prereg.md`—frozen v4 conditional
  Poisson, transport-score, margin-transfer and Gaussian-control obligations
- `computations/verify_yang_mills_transport_score.py`—86-check source-bound
  transport-score and Gaussian verifier
- `computations/verify_yang_mills_transport_score_independent.mjs`—32-check
  discrete-sine, Jacobi, pivoted-solve and receipt reconstruction
- `computations/yang-mills-recovery-gramian-prereg.md`—frozen v5
  residual-recovery, score-separation, rigidity and Gaussian-chaos obligations
- `computations/verify_yang_mills_recovery_gramian.py`—58-check source-bound
  residual, score, quotient and Gaussian verifier
- `computations/verify_yang_mills_recovery_gramian_independent.mjs`—30-check
  independent Jacobi, sine-basis and receipt-integrity reconstruction
- `computations/yang-mills-exact-block-spectral-prereg.md`—frozen cutoff
  schedule, seven-link boundary fixtures, convergence and qualification rules
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact Ritz,
  conditional-moment and boundary verifier with a SHA-256 sealed receipt
- `computations/yang_mills_conditional_algebra.py`—shared representation,
  Haar-contraction and conditional-moment helper bound by receipt hash
- `computations/yang-mills-nodal-family-prereg.md`—frozen twelve-row
  block-path family, resolution rule and confinement decision tree
- `computations/verify_yang_mills_nodal_family.py`—schedule-wide nodal
  family verifier with a SHA-256 sealed receipt
- `computations/yang-mills-bowtie-fibre-prereg.md`—frozen eight-link
  loop-carrying exterior, boundary schedule and qualification rules
- `computations/verify_yang_mills_bowtie_fibre.py`—source-bound bowtie
  conditional-fibre verifier with analytic controls and sealed receipt
- `computations/yang-mills-su2-wilson-2d-prereg.md`—finite-volume
  two-dimensional Wilson transfer, character-fusion correlator and tail protocol
- `computations/verify_yang_mills_su2_wilson_2d.py`—876-check source-bound
  finite-volume Wilson bridge verifier
- `computations/verify_yang_mills_su2_wilson_2d_independent.mjs`—120-check
  independent Bessel-series and receipt reconstruction
- `computations/yang-mills-su2-open-cube-prereg.md`—frozen open-cube
  gauge-basis and oriented Wilson-support protocol
- `computations/verify_yang_mills_su2_open_cube.py`—69-check exact
  open-cube basis and Wilson-support verifier
- `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`—larger-volume/cutoff Hamiltonian, complete intertwiner basis and finite-volume character-tail protocol
- `computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`—spectator-channel recovery identity, firing control and finite-operator bounds
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—recovered 226-check finite Hamiltonian construction
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian_independent.py`—256-check independent basis, matrix and spectrum reconstruction
- `computations/yang-mills-finite-graph-cutoff-form-prereg.md`—fixed finite-graph Haar disintegration, form-core, tail and noncommuting Ritz theorem
- `computations/verify_yang_mills_finite_graph_cutoff_form.py`—22-check tridiagonal deterministic control
- `computations/verify_yang_mills_finite_graph_cutoff_form_independent.py`—18-check dense independent reconstruction and receipt audit
- `runs/yang_mills_finite_graph_cutoff_form/verification.json`—primary fixed-graph cutoff-form receipt with a `NULL` Clay verdict
- `runs/yang_mills_finite_graph_cutoff_form/verification-independent.json`—independent source- and receipt-bound reconstruction
- `computations/yang-mills-local-cutoff-density-prereg.md`—frozen
  multi-volume local cutoff, joint auxiliary schedule and global-obstruction
  protocol
- `computations/verify_yang_mills_local_cutoff_density.py`—16-check
  source-bound local-density and product-family verifier
- `computations/verify_yang_mills_local_cutoff_density_independent.mjs`—17-check
  independent reconstruction and receipt-binding audit
- `runs/yang_mills_local_cutoff_density/verification.json`—primary
  local-cutoff-density receipt with a `NULL` Clay verdict
- `runs/yang_mills_local_cutoff_density/verification-independent.json`—independent
  source- and receipt-bound reconstruction
- `computations/yang-mills-thermodynamic-ground-state-prereg.md`—frozen
  fixed-regulator compactness, compatibility, ground-identity and implication
  boundary protocol
- `computations/verify_yang_mills_thermodynamic_ground_state.py`—18-check
  source-bound finite-identity verifier for the conditional thermodynamic
  bridge
- `computations/verify_yang_mills_thermodynamic_ground_state_independent.mjs`—19-check
  independent rank, compactness, partial-trace, finite-matrix and
  receipt-binding reconstruction
- H. Grundling and G. Rudolph, [Dynamics for QCD on an infinite
  lattice](https://arxiv.org/abs/1512.06319)—infinite-lattice Hamiltonian
  gauge dynamics, physical observable algebra and gauge-invariant ground
  states
- H. Grundling and G. Rudolph, [QCD on an infinite
  lattice](https://arxiv.org/abs/1108.2129)—inductive local gauge algebra and
  Gauss-law construction
- `runs/yang_mills_continuum_boundary_audit/verification.json`—34-check v5 hash-bound audit receipt covering recovered finite evidence, fixed-graph cutoff removal, volume-uniform local cutoff control, conditional thermodynamic finite-identity evidence, excluded defect provenance and the unresolved continuum boundary
- `computations/verify_yang_mills_continuum_boundary_audit.py`—34-check source, receipt, recovery-snapshot and continuum-boundary audit
- D. Bakry, I. Gentil and M. Ledoux, *Analysis and Geometry of Markov
  Diffusion Operators*—Poincaré, Poisson and carré-du-champ framework
- C. Villani, *Optimal Transport: Old and New*—continuity equations and
  minimum-kinetic-energy tangent transport
- J. Milnor, [The Poincaré
  Conjecture](https://www.claymath.org/wp-content/uploads/2022/06/poincare.pdf)—official
  problem statement and three-sphere topology
- G. Perelman, [The entropy formula for the Ricci flow and its geometric
  applications](https://arxiv.org/abs/math/0211159)—entropy, rescaling and
  noncollapsing method
- A. Ikeda and Y. Taniguchi, [Spectra and eigenforms of the Laplacian on
  $S^n$ and $P^n(\mathbb C)$](https://ir.library.osaka-u.ac.jp/repo/ouka/all/6956/),
  Theorem 4.2—round-sphere differential-form spectra
- D. Bakry and M. Émery, [Diffusions
  hypercontractives](https://www.numdam.org/item/SPS_1985__19__177_0.pdf)—iterated
  carré-du-champ curvature criterion
- A. E. Moncrief, P. Marini and R. Maitra, [Orbit Space Curvature as a
  Source of Mass in Quantum Gauge
  Theory](https://arxiv.org/abs/2302.05721)—Bakry–Émery gauge-orbit gap
  program and continuum regularization boundary
