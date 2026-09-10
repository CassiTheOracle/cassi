# Vorticity-Seeded Deformation Occupation and Active Cascade Dose

## Status: Derived conditional—September 2026

## Abstract

The Constantin–Iyer stochastic Cauchy field admits a second moment seeded by the actual initial vorticity. This matrix field obeys a closed deterministic advection–diffusion equation. Its trace dominates the Euclidean enstrophy and has an exact label-space representation as an exponential directional-strain occupation. A finite cumulative positive production dose therefore implies continuation of a smooth periodic three-dimensional Navier–Stokes solution.

The production sees only the anisotropic part of the stochastic orientation distribution and only its alignment with strain. It vanishes for embedded two-dimensional flows and for periodic shear even when the unseeded deformation covariance is anisotropic. The resulting quantity has zero formal Euclidean Navier–Stokes scaling exponent and retains the initial-vorticity distribution throughout the stochastic flow. It supplies a precise whole-cascade route: summability of the positive active dose across cascade levels is sufficient. A geometric scale ratio alone gives no such summability.

A reachable-direction Khasminskii condition bounds the occupation. Replacing the active direction by maximum positive strain gives a standard heat-kernel estimate in the range $2/p+3/q<2$. At equality, finite $1<p<\infty$, $3/2<q<\infty$ use a Lorentz refinement; $(1,\infty)$ is the direct maximum-strain integral and $(\infty,3/2)$ is excluded. The energy-class strain norm $L_t^2L_x^2$ lies outside that range, and a parabolically concentrated scalar-potential family excludes a uniform generic exponential-occupation bound from that norm alone. A uniform all-data bound on the active dose remains open, so the result does not settle the Navier–Stokes existence-and-smoothness problem.

## 1. Result

Consider the unforced incompressible Navier–Stokes equation on the normalized periodic torus:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\nu>0.
\tag{1}
$$

Let

$$
\omega=\nabla\times u,
\qquad
L=\nabla u,
\qquad
S=\frac12(L+L^{\mathsf T}),
\qquad
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta.
\tag{2}
$$

The vorticity equation and enstrophy law are

$$
\mathcal L_u\omega=L\omega,
\tag{3}
$$

$$
\frac12W'(t)+\nu D(t)=P(t),
\quad
W=\|\omega\|_2^2,
\quad
D=\|\nabla\omega\|_2^2,
\quad
P=\int\omega\cdot S\omega\,dx.
\tag{4}
$$

The construction below produces a nonnegative quantity $\mathcal E_M$ such that

$$
W(t)\le\mathcal E_M(t),
\qquad
\mathcal E_M(0)=W(0),
\tag{5}
$$

and

$$
\frac{\mathcal E_M(t)}{W(0)}
=
\exp\left(2\int_0^t\Gamma_M(s)\,ds\right).
\tag{6}
$$

All normalized identities, probability measures, and Rayleigh quotients below assume $W(0)>0$. The initial-vorticity-zero case is the trivial mean-zero solution; set $\Gamma_M=0$ for that separate case when reading (7).

**Proposition 1.** Fix $\nu>0$, finite $T>0$, and $R\ge0$. Suppose every smooth mean-zero divergence-free datum satisfying $\|u_0\|_{H^3}\le R$ generates, on its maximal smooth interval $[0,T_*)$, the uniform estimate

$$
\int_0^{\min(T,T_*)}(\Gamma_M(t))_+dt
\le B_M(\nu,T,R)<\infty.
\tag{7}
$$

Then every such solution continues through $T$.

Indeed, (5)–(7) bound $W$ uniformly. On a finite interval this also gives $\omega\in L_t^4L_x^2$, a standard vorticity continuation class, or equivalently a uniform periodic $H^1$ restart bound. Conversely, finite-time loss of regularity forces $\mathcal E_M$ and the cumulative positive dose in (7) to diverge along the endpoint.

The derivation of (5)–(6) is exact. The estimate (7) is the unresolved all-data step.

Under the Euclidean Navier–Stokes rescaling,
$\mathcal E_M/W(0)$ and $\int\Gamma_Mdt$ have zero scaling exponent. The
rescaling changes the period of a fixed torus. This records scale-critical
dimensional behavior; the normalized torus has no corresponding continuous
rescaling symmetry.

## 2. Stochastic Cauchy field

On a compact interval inside $[0,T_*)$, let $X_t(a)$ be the smooth Constantin–Iyer stochastic flow and let $\mathscr A_t=X_t^{-1}$. Smoothness on this interval supplies finite deformation moments, differentiation under expectation, Fubini, and mean-zero Itô integrals:

$$
dX_t(a)=u(X_t(a),t)\,dt+\sqrt{2\nu}\,dB_t,
\qquad
X_0(a)=a.
\tag{8}
$$

The Brownian translation is common to every label in a realization. Since $u$ is divergence free, each random map preserves volume. Define the Eulerian deformation, sampled initial vorticity, and Cauchy field

$$
F_t(x)=\bigl(\nabla_aX_t\bigr)(\mathscr A_t(x)),
\qquad
V_t(x)=\omega_0(\mathscr A_t(x)),
\qquad
Y_t(x)=F_t(x)V_t(x).
\tag{9}
$$

The stochastic Cauchy formula reads

$$
\boxed{\omega(x,t)=\mathbb E Y_t(x).}
\tag{10}
$$

In Eulerian variables, $Y$ satisfies

$$
dY+\bigl(u\cdot\nabla Y-LY\bigr)dt
-\nu\Delta Y\,dt
+\sqrt{2\nu}\sum_k\partial_kY\,dB_t^k=0.
\tag{11}
$$

The same spatial Brownian increment appears in every component. This common-noise structure is what closes the second moment.

## 3. Seeded covariance closure

Define

$$
M(x,t)=\mathbb E\bigl[Y_t(x)Y_t(x)^{\mathsf T}\bigr].
\tag{12}
$$

When Itô's product rule is applied to $YY^{\mathsf T}$, the two individual Laplacians and the quadratic variation combine into the full product Laplacian:

$$
\nu\bigl[(\Delta Y)Y^{\mathsf T}
+Y(\Delta Y)^{\mathsf T}\bigr]
+2\nu\sum_k(\partial_kY)(\partial_kY)^{\mathsf T}
=
\nu\Delta(YY^{\mathsf T}).
\tag{13}
$$

Taking expectations gives the closed deterministic equation

$$
\boxed{
\mathcal L_uM=LM+ML^{\mathsf T},
\qquad
M(x,0)=\omega_0(x)\omega_0(x)^{\mathsf T}.}
\tag{14}
$$

The initial matrix is rank one where $\omega_0\ne0$, but positive definiteness is unnecessary. Positivity is preserved by the stochastic representation.

The centred covariance

$$
R=M-\omega\omega^{\mathsf T}
\tag{15}
$$

has the pointwise representation

$$
R=\mathbb E\bigl[(Y-\mathbb EY)(Y-\mathbb EY)^{\mathsf T}\bigr]\succeq0.
\tag{16}
$$

The diffusion product rule for the deterministic mean field has the opposite gradient term:

$$
\mathcal L_u(\omega\omega^{\mathsf T})
=L\omega\omega^{\mathsf T}
+\omega\omega^{\mathsf T}L^{\mathsf T}
-2\nu\sum_k(\partial_k\omega)(\partial_k\omega)^{\mathsf T}.
\tag{17}
$$

Subtracting (17) from (14) yields

$$
\boxed{
\mathcal L_uR=LR+RL^{\mathsf T}
+2\nu\sum_k(\partial_k\omega)(\partial_k\omega)^{\mathsf T},
\qquad R(x,0)=0.}
\tag{18}
$$

Viscous averaging reduces the squared mean field in (4) while feeding stochastic spread in (18). Equation (18) identifies that transfer without imposing an isotropy model on the spread.

## 4. Enstrophy envelope

Set

$$
\mathcal E_M(t)=\int_{\mathbb T^3}\operatorname{tr}M(x,t)\,dx.
\tag{19}
$$

Covariance positivity gives

$$
|\omega(x,t)|^2\le\operatorname{tr}M(x,t),
\qquad
W(t)\le\mathcal E_M(t).
\tag{20}
$$

Taking the trace of (14) and integrating over the torus eliminates transport and diffusion. Since $M$ is symmetric, the skew part of $L$ also disappears:

$$
\boxed{
\mathcal E_M'(t)=2\int_{\mathbb T^3}S:M\,dx.}
\tag{21}
$$

Define

$$
\Gamma_M(t)=
\frac{\displaystyle\int S:M\,dx}
{\displaystyle\int\operatorname{tr}M\,dx}.
\tag{22}
$$

Equations (6) and (7) now follow from scalar integration of (21). The ratio $\mathcal E_M/W(0)$ is invariant under the Navier–Stokes scaling, and $\Gamma_Mdt$ is dimensionless. The reduction retains the scale-critical character of the original obstruction.

The seeded envelope differs from the Euclidean enstrophy. Diffusion can make (20) strict by reducing the mean while preserving variance in the stochastic ensemble. The periodic shear control in §10 displays this separation exactly.

## 5. Orientation anisotropy

Put

$$
m=\operatorname{tr}M.
\tag{23}
$$

Where $m>0$, introduce the normalized orientation matrix and its traceless part:

$$
N=\frac M m,
\qquad
Q=N-\frac13I.
\tag{24}
$$

The eigenvalues $p_i$ of $N$ are nonnegative and sum to one. Therefore

$$
\|Q\|_{\mathrm F}^2
=\sum_ip_i^2-\frac13
\le\frac23.
\tag{25}
$$

Define the normalized anisotropy

$$
\theta=\sqrt{\frac32}\,\|Q\|_{\mathrm F}\in[0,1].
\tag{26}
$$

Because $\operatorname{tr}S=0$,

$$
S:M=mS:Q.
\tag{27}
$$

Here and below, $|S|=\|S\|_{\mathrm F}$ and
$|Q|=\|Q\|_{\mathrm F}$.

Where $|S|\theta>0$, define the Frobenius alignment

$$
\chi=\frac{S:Q}{|S|\,|Q|}\in[-1,1],
\tag{28}
$$

and set $\chi=0$ elsewhere. The active production becomes

$$
\boxed{
\Gamma_M(t)=
\sqrt{\frac23}\,
\frac{\displaystyle\int m|S|\theta\chi\,dx}
{\displaystyle\int m\,dx}.}
\tag{29}
$$

This formula isolates three factors: ensemble mass, orientation anisotropy, and signed strain alignment. Large strain in an orientation-isotropic ensemble contributes zero. Large anisotropy in a strain-orthogonal direction also contributes zero. Any Cassi coherence argument aimed at (7) must control the positive time accumulation of their product.

## 6. Exact occupation identity

For each stochastic realization, change variables from $x$ to the volume-preserved label $a$ in (19):

$$
\mathcal E_M(t)
=
\int_{\mathbb T^3}
\mathbb E\left|
\nabla_aX_t(a)\omega_0(a)
\right|^2da.
\tag{30}
$$

For $\omega_0(a)\ne0$, set

$$
J_t(a)=\nabla_aX_t(a)\omega_0(a),
\qquad
n_t(a)=\frac{J_t(a)}{|J_t(a)|}.
\tag{31}
$$

Differentiating the flow in its label gives

$$
\frac d{dt}J_t=L(X_t,t)J_t,
\tag{32}
$$

and hence

$$
\frac d{dt}n_t
=(I-n_tn_t^{\mathsf T})L(X_t,t)n_t,
\tag{33}
$$

$$
\frac d{dt}\log|J_t|
=n_t^{\mathsf T}S(X_t,t)n_t
=: \sigma_t.
\tag{34}
$$

Use the initial-vorticity probability measure

$$
n_0(a)=:\widehat\omega_0(a)=\frac{\omega_0(a)}{|\omega_0(a)|},
\qquad
d\mu_0(a)=\frac{|\omega_0(a)|^2}{W(0)}da.
\tag{35}
$$

Then (30)–(35) give the exact representation

$$
\boxed{
\frac{\mathcal E_M(t)}{W(0)}
=
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t\sigma_sds\right).}
\tag{36}
$$

The initial datum selects both the label distribution and the initial orientation. Differentiating the logarithm of (36) gives

$$
\boxed{
\Gamma_M(t)=
\frac{
\mathbb E_{\mu_0,B}
\left[\sigma_t
\exp\left(2\int_0^t\sigma_sds\right)\right]}
{
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t\sigma_sds\right)}.}
\tag{37}
$$

The weighting in (37) progressively selects paths with a history of positive stretching. This supplies the Lagrangian form of the Eulerian alignment average (29). It also states the role of formation history precisely: the whole later occupation is seeded by $|\omega_0|^2$ and its direction; the unconditioned deformation ensemble is absent.

## 7. Bridge to the covariance-inverse result

The unseeded deformation covariance from `turbulence/navier-stokes-deformation-covariance.md` is

$$
C=\mathbb E[FF^{\mathsf T}],
\qquad
G_C=C^{-1}.
\tag{38}
$$

Its weighted enstrophy and active quotient are

$$
Z_C=\int\omega^{\mathsf T}G_C\omega\,dx,
\qquad
\mathfrak A_C=\frac W{Z_C}.
\tag{39}
$$

A direct-metric quotient sharpens the full operator comparison:

$$
\mathfrak B_C=
\frac{\displaystyle\int\omega^{\mathsf T}C\omega\,dx}{W}.
\tag{40}
$$

For every positive definite $C$ and vector $v$,

$$
(v^{\mathsf T}v)^2
\le(v^{\mathsf T}Cv)(v^{\mathsf T}C^{-1}v).
\tag{41}
$$

Applying (41) pointwise and then using Cauchy–Schwarz in space yields

$$
\boxed{
\mathfrak A_C
\le\mathfrak B_C
\le\|\lambda_{\max}(C)\|_{L^\infty}.}
\tag{42}
$$

In an eigenbasis of $C$, the gap in (41) has the manifestly nonnegative form

$$
(v^{\mathsf T}Cv)(v^{\mathsf T}C^{-1}v)
-(v^{\mathsf T}v)^2
=
\sum_{i<j}v_i^2v_j^2
\frac{(c_i-c_j)^2}{c_ic_j}.
\tag{43}
$$

The quotient $\mathfrak B_C$ observes current vorticity directions and can be much smaller than the full deformation norm. The seeded field $M$ goes further by placing the actual initial-vorticity matrix in the covariance evolution. This yields the closed envelope (20) and occupation identity (36) without selecting the current vorticity as an input to a new metric.

## 8. Reachable-direction Khasminskii bound

The exact occupation immediately gives

$$
\frac{\mathcal E_M(t)}{W(0)}
\le
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t(\sigma_s)_+ds\right).
\tag{44}
$$

The pair $(X_t,n_t)$ is a Markov process on $\mathbb T^3\times\mathbb S^2$. Let $\mathscr R_s$ be the support reachable at time $s$ from the seeded states $(a,\widehat\omega_0(a))$. On a time interval $I_j=[t_{j-1},t_j]$, define

$$
\kappa_j=
\sup_{\substack{s\in I_j\\(x,n)\in\mathscr R_s}}
\mathbb E_{s,x,n}
\int_s^{t_j}
2\bigl(n_r^{\mathsf T}S(X_r,r)n_r\bigr)_+dr.
\tag{45}
$$

Khasminskii's moment expansion and the Markov property imply

$$
\boxed{
\kappa_j<1\ \text{for every }j
\quad\Longrightarrow\quad
\sup_{t\le t_N}\frac{\mathcal E_M(t)}{W(0)}
\le\prod_{j=1}^N(1-\kappa_j)^{-1}.}
\tag{46}
$$

This form retains the reachable orientation set. It is exact enough to recognize the inactive direction of a shear. A coarser estimate replaces the directional potential by

$$
\lambda_+(S)=\max\{\lambda_{\max}(S),0\}.
\tag{47}
$$

The transition semigroup for the spatial process has divergence-free drift. The Nash energy argument gives the torus estimate

$$
\|P_{s,t}f\|_\infty
\le c_{q,\mathbb T}
\left[1+\bigl(\nu(t-s)\bigr)^{-3/(2q)}\right]
\|f\|_q.
\tag{48}
$$

Let $\alpha=3/(2q)$. Hölder's inequality in time then gives, for $1<p\le\infty$ and $3/2<q\le\infty$,

$$
\overline\kappa_j
\le C_{p,q,\mathbb T}
\left[
\Delta_j^{1-1/p}
+\nu^{-\alpha}
\Delta_j^{1-1/p-\alpha}
\right]
\|\lambda_+(S)\|_{L^p(I_j;L^q)},
\tag{49}
$$

provided

$$
\frac1p+\frac{3}{2q}<1,
\quad\text{equivalently}\quad
\frac2p+\frac3q<2.
\tag{50}
$$

Here $\kappa_j\le\overline\kappa_j$. At equality, direct Lorentz control applies for finite $1<p<\infty$ and $3/2<q<\infty$ through $L_t^{p,1}L_x^q$. The endpoint $(p,q)=(\infty,3/2)$ is excluded because its $\tau^{-1}$ kernel is nonintegrable and has no nontrivial $L_t^{\infty,1}$ refinement. The separate endpoint $(p,q)=(1,\infty)$ is the direct integral of maximum strain.

This comparison supplies an established analytic route to (7) under stronger strain hypotheses. It leaves the all-data problem at the energy level.

## 9. Why kinetic energy does not close the occupation

The kinetic-energy law controls

$$
S\in L_t^2L_x^2.
\tag{51}
$$

For $(p,q)=(2,2)$, the exponent in (50) is

$$
\frac2p+\frac3q=\frac52>2.
\tag{52}
$$

Thus (48)–(50) do not turn the energy-class norm into a uniform exponential occupation estimate. A scalar pulse shows that this failure is structural for generic parabolic potentials.

Choose nonnegative smooth bumps $\chi$ and $\psi$ that are positive on smaller cores, and in a local torus chart let

$$
s_r(t,x)=r^{-5/2}\chi(t/r^2)\psi(x/r).
\tag{53}
$$

Its space-time $L^2$ norm is scale independent:

$$
\|s_r\|_{L_{t,x}^2}^2
\asymp r^{-5}r^2r^3\asymp1.
\tag{54}
$$

A Brownian path started in the spatial core has, by Brownian scaling, an $r$-independent positive probability of remaining in the core for a time comparable to $r^2$. On that event,

$$
\int s_rdt\gtrsim r^{-5/2}r^2=r^{-1/2}.
\tag{55}
$$

Consequently, the family of exponential occupations is bounded below by $c\exp(c'r^{-1/2})$ and is unbounded as $r\downarrow0$ while (54) stays bounded. Each fixed smooth $s_r$ has a finite exponential moment.

This pulse is a scalar heat-kernel control. It is not a Navier–Stokes strain field and makes no claim that the coupled equation realizes such a history. It proves that energy-class integrability alone cannot establish the required exponential estimate through generic semigroup and Hölder bounds. Any successful all-data argument must use additional self-consistent structure: reachable-orientation depletion, pressure coupling, incompressibility, interscale correlation, or another property of the original equation.

## 10. Exact controls

### 10.1 Local algebraic homogeneous extension

Consider the trace-free local matrix model

$$
L_a=S_a=\operatorname{diag}(a,-a,0),
\qquad
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1),
\qquad a>0,
\tag{56}
$$

with the prescribed vector seed $e_1$. Per unit label volume,

$$
M_a(t)=e^{2at}e_1e_1^{\mathsf T},
\qquad
\frac{\mathcal E_M(t)}{W(0)}=e^{2at},
\qquad
\Gamma_M=a.
\tag{57}
$$

The occupation identity is exact, and the normalized orientation anisotropy is $\theta=1$. This control shows local algebraic sharpness: trace-free deformation and volume preservation do not bound the active envelope. The affine velocity $u=L_ax$ has zero curl, so the prescribed seed is not its vorticity. On $\mathbb R^3$ the constant seed gives infinite global $W(0)$ and $\mathcal E_M$. The control is neither periodic nor a Navier–Stokes solution.

### 10.2 Periodic shear heat flow

Consider

$$
u_s(y,t)=b e^{-\lambda t}\sin(ny)e_1,
\qquad
\lambda=\nu n^2.
\tag{58}
$$

Its nonlinear term vanishes and its vorticity is

$$
\omega_s=-bn e^{-\lambda t}\cos(ny)e_3.
\tag{59}
$$

The deformation acts in the $e_1$–$e_2$ plane and fixes $e_3$ pathwise. Therefore

$$
\sigma_t=0,
\qquad
\mathcal E_M(t)=W(0),
\qquad
\Gamma_M=0,
\tag{60}
$$

while

$$
W(t)=e^{-2\lambda t}W(0).
\tag{61}
$$

The active seeded envelope remains one even though the unseeded covariance can become strongly anisotropic in the shear plane. Diffusion appears as cancellation in the stochastic mean, making (20) strict for $t>0$.

### 10.3 Embedded two-dimensional flow

For a two-dimensional incompressible flow embedded in three dimensions,

$$
\omega_0=\zeta_0e_3,
\qquad
\nabla_aX_te_3=e_3.
\tag{62}
$$

Hence

$$
\mathcal E_M(t)=W(0),
\qquad
\Gamma_M=0,
\qquad
W(t)\le W(0).
\tag{63}
$$

The construction therefore recovers the absence of vortex stretching in two dimensions without an operator-norm estimate on the in-plane deformation.

## 11. Whole-cascade requirement

Partition a possible concentration history into disjoint cascade-level intervals $I_j$ and define

$$
\delta_j=\int_{I_j}(\Gamma_M(t))_+dt.
\tag{64}
$$

Equation (6) shows that the sufficient condition is

$$
\sum_{j=0}^\infty\delta_j<\infty.
\tag{65}
$$

A geometric sequence of spatial scales does not enforce (65). Each scale-critical event can carry a dimensionless dose bounded below by the same positive constant, in which case the sum diverges. A quantitative decay law such as

$$
\delta_j\le C\varphi^{-\varepsilon j},
\qquad \varepsilon>0,
\tag{66}
$$

would instead give

$$
\sum_{j=0}^\infty\delta_j
\le\frac C{1-\varphi^{-\varepsilon}}<\infty.
\tag{67}
$$

This identifies the mathematical role available to a whole-bubble Cassi cascade. Formation data enter through $\mu_0$ in (35), the stochastic history enters through (36), and interscale selection enters through the sequence $\delta_j$. A theorem using this active-dose route must produce summability, diminishing orientation anisotropy, adverse strain alignment, or an equivalent cancellation. The fixed golden scale ratio supplies the index geometry while leaving the required decay unproved.

A theorem covering physically selected Cassi bubbles would apply to that restricted class. The Clay global-regularity alternative requires the bound for every smooth divergence-free datum in the stated class. The distinction remains part of the target.

## 12. Relation to Cassi

The construction uses a Cassi principle without changing the governing equation: deformation is measured only on the state distribution that the dynamics actually occupies. The unseeded covariance $C$ treats every vector direction equally. The seeded moment $M$ begins with $\omega_0\omega_0^{\mathsf T}$, propagates that occupied direction through the original stochastic Navier–Stokes flow, and records both its mean and its spread.

Equation (29) gives a concrete coherence quantity. The tensor $Q$ is the anisotropic part of the transported orientation ensemble, and $\chi$ measures its alignment with strain. Equation (37) gives the complementary history-dependent description: stretching exponentially reweights the active trajectory ensemble. These are mathematical observables of the original equation. No Cassi scalar $q$, two-fluid constitutive law, or additional damping term is inserted into Navier–Stokes.

The next theorem obligation is now specific:

$$
\sup_{\substack{u_0\in C^\infty,\ \nabla\cdot u_0=0,\ \int u_0=0\\
\|u_0\|_{H^3}\le R}}
\int_0^{\min(T,T_*)}(\Gamma_M(t))_+dt
<\infty.
\tag{68}
$$

Possible routes include a regression-observability estimate for the seeded covariance, a depletion theorem for reachable orientations, or a cross-scale decorrelation estimate that proves (65). Positivity, geometric scale placement, kinetic energy, and the generic maximum-strain semigroup bound do not establish (68).

The independent-replica refinement in
`turbulence/navier-stokes-replica-coherence.md` resolves the same seeded
second moment into deterministic overlap and stochastic disagreement. Its
full-rank determinant term supplies a rigorous part of the desired
compensation, while rank-deficient collapse leaves the uniform all-data bound
open.

## 13. Verification and evidence scope

The fixed schedule in `computations/navier-stokes-active-deformation-occupation-prereg.md` specifies 40 general polynomial components, explicitly labelled finite fixtures, local algebraic controls, and exponent checks. The executable is `computations/verify_navier_stokes_active_deformation_occupation.py`. Its source-bound selected receipt is `runs/navier_stokes_active_deformation_occupation/verification.json`, with an adjacent input manifest and source snapshots.

The executable inventory covers the common-noise product correction, seeded and centred covariance algebra, covariance positivity on a fixed ensemble, fixed active-Rayleigh quadrature, label conversion, orientation and occupation components, anisotropy algebra, formal Euclidean scaling exponents, local homogeneous and exact shear controls, embedded two-dimensional block algebra, Khasminskii-series arithmetic, heat-kernel exponents, pulse scaling, and cascade sums.

The stochastic-flow representation, analytical continuation step, Khasminskii implication, drift-independent Nash estimate, Lorentz endpoint statement, Brownian core-event lower bound, and periodic $H^1$ restart criterion are conditional analytical arguments under the stated smoothness and standard theorems, outside the 40-check receipt. The verifier runs no Navier–Stokes trajectory, stochastic simulation, matrix-PDE integration, singularity search, or Cassi whole-cascade dynamics.

The qualified classifications are:

- seeded common-noise closure and active occupation reduction: **SUPPORTS**;
- generic energy-class-strain-only control of the exponential occupation: **CONTRADICTS**;
- geometric cascade spacing as a sufficient source of summable active dose: **CONTRADICTS**;
- the uniform all-data bound (68) and arbitrary-data Navier–Stokes regularity: **UNRESOLVED**.

## Sources

1. C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—official problem statement and periodic formulation.
2. P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://web.math.princeton.edu/~const/ci.pdf)—stochastic flow, volume preservation, and Cauchy formula.
3. P. Constantin and G. Iyer, [A stochastic-Lagrangian approach to the Navier–Stokes equations in domains with boundary](https://web.math.princeton.edu/~const/gic31110.pdf)—random-characteristic formulation and vorticity transport context.
4. J. Nash, *Continuity of solutions of parabolic and elliptic equations*, American Journal of Mathematics **80** (1958), 931–954—heat-kernel scale behind (48).
5. G. Seregin, L. Silvestre, V. Šverák, and A. Zlatoš, [On divergence-free drifts](https://arxiv.org/abs/1010.6025)—parabolic estimates and critical drift boundaries.
6. T. Mahithitarmmatorn, [Exact mean–covariance dynamics of the Weber field in the stochastic Lagrangian representation of the 3D Navier–Stokes equations](https://arxiv.org/abs/2608.16915)—closed common-noise covariance calculus and stochastic-flow regularity boundary.
7. `turbulence/navier-stokes-deformation-covariance.md`—covariance-inverse weighted law and active deformation quotient.
8. `turbulence/navier-stokes-strain-departure.md`—critical continuation reductions and cascade-recurrence obstructions.
9. `turbulence/navier-stokes-replica-coherence.md`—independent-replica overlap, viscous disagreement, and full-rank compensation.
