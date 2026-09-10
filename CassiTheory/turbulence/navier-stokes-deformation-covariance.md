# Deformation Covariance and Covariant Enstrophy in Navier–Stokes

## Status: Derived conditional—September 2026

## Abstract

The Constantin–Iyer stochastic Cauchy formula supplies a positive matrix adapted to the same deformation that transports vorticity. Let $F$ be the Eulerian forward-deformation matrix, let $C=\mathbb E[FF^{\mathsf T}]$, and set $G_C=C^{-1}$. Common translational noise closes the deterministic equation for $C$. The inverse equation for $G_C$ contains a quadratic spatial term which completes every viscous cross-term into a nonnegative covariant square. Consequently,

$$
\int\omega^{\mathsf T}G_C\omega\,dx
+2\nu\int_0^t\mathcal D_C(s)\,ds
=\|\omega_0\|_2^2
$$

through every smooth interval, with no scalar work projection.

The same law has an exact stochastic interpretation. At each point, the map $Tq=\mathbb E[Fq]$ sends the sampled initial vorticity to the current vorticity. The weighted density $\omega^{\mathsf T}G_C\omega$ is the squared norm of the orthogonal projection of that sampled datum onto $\operatorname{ran}T^*$. The accumulated covariant dissipation equals the endpoint regression residual. This identifies a data-conditioned Rayleigh quotient as the active distortion relevant to continuation.

A homogeneous extensional control keeps determinant one and weighted enstrophy constant while active distortion grows exponentially. An exact periodic shear develops covariance only in the plane orthogonal to its vorticity and has active distortion one. The covariance-inverse construction therefore removes the scalar normalization obstruction in the adaptive-metric analysis and retains the directional distinction. A uniform initial-$H^3$-controlled bound on its active Rayleigh quotient remains **UNRESOLVED**.

## 1. Scope and conventions

Work on the normalized three-torus with a sufficiently regular mean-zero solution of

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\nu>0.
\tag{1}
$$

Write

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
The gradient convention is $L_{ij}:=\partial_j u_i$, so
$L\omega=(\omega\cdot\nabla)u$.

The vorticity equation is

$$
\mathcal L_u\omega=L\omega.
\tag{3}
$$

Its Euclidean enstrophy balance is

$$
\frac12\frac d{dt}W+\nu D=P,
\qquad
W=\|\omega\|_2^2,
\quad
D=\|\nabla\omega\|_2^2,
\quad
P=\int\omega\cdot S\omega\,dx.
\tag{4}
$$

The argument below is an auxiliary reformulation of (3). Every identity is conditional on the existence of the smooth Navier–Stokes solution used to generate its coefficients. The continuation statement requires a uniform estimate over the prescribed initial-data class.

Throughout, every stochastic calculation is restricted to a compact smooth interval $[0,\tau]\subset[0,T_*)$ on which $u$, $p$, and the initial datum are smooth and periodic. On such an interval the stochastic flow is a smooth volume-preserving diffeomorphism almost surely, its required deformation moments are finite, and differentiation under expectation, Fubini, and removal of the mean-zero Itô integrals are justified. None of these conditional smooth-interval facts supplies a bound as $\tau\uparrow T_*$.

## 2. Stochastic forward deformation

Let $X_t(a)$ solve the Constantin–Iyer stochastic flow

$$
dX_t(a)=u(X_t(a),t)\,dt+\sqrt{2\nu}\,dB_t,
\qquad X_0(a)=a,
\tag{5}
$$

and let $\mathscr A_t=X_t^{-1}$ be its spatial inverse. Incompressibility gives

$$
\det\nabla_aX_t=1,
\qquad
\det\nabla_x\mathscr A_t=1
\tag{6}
$$

for every realization. Define the Eulerian forward deformation and sampled initial vorticity

$$
F_t(x)=\bigl(\nabla_aX_t\bigr)(\mathscr A_t(x)),
\qquad
V_t(x)=\omega_0(\mathscr A_t(x)).
\tag{7}
$$

The stochastic Cauchy formula is

$$
\boxed{\omega(x,t)=\mathbb E[F_t(x)V_t(x)].}
\tag{8}
$$

The random Eulerian matrix $F$ satisfies the common-noise transport-stretching equation. Its Stratonovich form is

$$
dF+\bigl(u\cdot\nabla F-LF\bigr)dt
+\sqrt{2\nu}\sum_k\partial_kF\circ dB_t^k=0.
\tag{9a}
$$

Equivalently, the Itô form used for the covariance calculation is

$$
dF+\bigl(u\cdot\nabla F-LF\bigr)dt
-\nu\Delta F\,dt
+\sqrt{2\nu}\sum_k\partial_kF\,dB_t^k=0.
\tag{9b}
$$

The regularity assumptions on the smooth interval make the Itô integrals martingales and justify the pointwise expectations. The same common Brownian translation drives every column.

## 3. Closed deformation covariance

Define

$$
C(x,t)=\mathbb E[F_t(x)F_t(x)^{\mathsf T}].
\tag{10}
$$

The Itô product rule for $FF^{\mathsf T}$ has the quadratic-variation term

$$
2\nu\sum_k(\partial_kF)(\partial_kF)^{\mathsf T}dt.
\tag{11}
$$

Together with the two Laplacian terms, this is exactly $\nu\Delta(FF^{\mathsf T})dt$. Taking expectation in (9b) therefore gives the closed equation

$$
\boxed{
\mathcal L_uC=LC+CL^{\mathsf T},
\qquad C(x,0)=I.}
\tag{12}
$$

No higher stochastic moment appears in (12). This common-noise closure is parallel to the exact deformation and Weber covariance calculus developed in the recent mean–covariance analysis cited below.

For every nonzero $q\in\mathbb R^3$,

$$
q^{\mathsf T}Cq=\mathbb E|F^{\mathsf T}q|^2>0,
\tag{13}
$$

so $C$ is symmetric positive definite. Put

$$
G_C=C^{-1}.
\tag{14}
$$

Differentiating $CG_C=I$ gives

$$
\partial_kG_C=-G_C(\partial_kC)G_C.
\tag{15}
$$

For any invertible matrix field $C$,

$$
\mathcal L_u(C^{-1})
=-C^{-1}(\mathcal L_uC)C^{-1}
-2\nu\sum_k
(\partial_kC^{-1})C(\partial_kC^{-1}).
\tag{16}
$$

Substitution of (12) into (16) yields

$$
\boxed{
\mathcal L_uG_C
+G_CL+L^{\mathsf T}G_C
+2\nu\sum_k
(\partial_kG_C)C(\partial_kG_C)=0.}
\tag{17}
$$

The final term in (17) is negative when $\mathcal L_uG_C$ is isolated. It is the term that completes the weighted viscous expression below.

## 4. Covariant completion of viscosity

For a symmetric matrix field $G$ and vector field $w$, the diffusion product rule is

$$
\begin{aligned}
\mathcal L_u(w^{\mathsf T}Gw)
={}&2(\mathcal L_uw)^{\mathsf T}Gw
+w^{\mathsf T}(\mathcal L_uG)w\\
&-2\nu\sum_k(\partial_kw)^{\mathsf T}G(\partial_kw)
-4\nu\sum_k(\partial_kw)^{\mathsf T}(\partial_kG)w.
\end{aligned}
\tag{18}
$$

Set

$$
\nabla_k^C\omega
:=\partial_k\omega+C(\partial_kG_C)\omega.
\tag{19}
$$

Equation (15) gives the equivalent form

$$
\nabla_k^C\omega
=\partial_k\omega-(\partial_kC)G_C\omega.
\tag{20}
$$

The square expands as

$$
\begin{aligned}
(\nabla_k^C\omega)^{\mathsf T}G_C(\nabla_k^C\omega)
={}&(\partial_k\omega)^{\mathsf T}G_C(\partial_k\omega)
+2(\partial_k\omega)^{\mathsf T}(\partial_kG_C)\omega\\
&+\omega^{\mathsf T}(\partial_kG_C)C(\partial_kG_C)\omega.
\end{aligned}
\tag{21}
$$

Apply (18) with $w=\omega$, then use (3) and (17). The two reaction terms cancel:

$$
2(L\omega)^{\mathsf T}G_C\omega
-\omega^{\mathsf T}(G_CL+L^{\mathsf T}G_C)\omega=0.
\tag{22}
$$

The three remaining spatial terms are exactly (21). Hence

$$
\boxed{
\mathcal L_u(\omega^{\mathsf T}G_C\omega)
=-2\nu\sum_k
(\nabla_k^C\omega)^{\mathsf T}
G_C(\nabla_k^C\omega).}
\tag{23}
$$

Define

$$
Z_C(t)=\int_{\mathbb T^3}\omega^{\mathsf T}G_C\omega\,dx,
\tag{24}
$$

$$
\mathcal D_C(t)=
\sum_k\int_{\mathbb T^3}
(\nabla_k^C\omega)^{\mathsf T}
G_C(\nabla_k^C\omega)\,dx\ge0.
\tag{25}
$$

Periodicity and incompressibility remove the transport and Laplacian integrals in (23). Since $G_C(0)=I$,

$$
\boxed{
Z_C(t)+2\nu\int_0^t\mathcal D_C(s)\,ds=W(0).}
\tag{26}
$$

Equation (26) is an exact weighted-enstrophy law generated by a forward parabolic covariance equation. The matrix remains positive and every viscous term belongs to one covariant square. No global scalar factor or vorticity-weighted curvature cancellation enters its definition.

## 5. Orthogonal projection identity

The stochastic representation gives (26) a second, independent interpretation. Fix $(x,t)$ and set

$$
\mathscr H=L^2(\Xi;\mathbb R^3),
\qquad
T_x:\mathscr H\to\mathbb R^3,
\qquad
T_xq=\mathbb E[Fq].
\tag{27}
$$

Its adjoint is

$$
T_x^*y=F^{\mathsf T}y,
\tag{28}
$$

and therefore

$$
T_xT_x^*=C,
\qquad
G_C=(T_xT_x^*)^{-1}.
\tag{29}
$$

Define

$$
P_x=T_x^*G_CT_x.
\tag{30}
$$

Then $P_x^*=P_x$ and

$$
P_x^2
=T_x^*G_C(T_xT_x^*)G_CT_x
=P_x.
\tag{31}
$$

Thus $P_x$ is the orthogonal projection onto $\operatorname{ran}T_x^*$. Since $\omega=T_xV$,

$$
P_xV=F^{\mathsf T}G_C\omega,
\qquad
T_xP_xV=\omega.
\tag{32}
$$

Moreover,

$$
\|P_xV\|_{\mathscr H}^2
=\omega^{\mathsf T}G_C(T_xT_x^*)G_C\omega
=\omega^{\mathsf T}G_C\omega.
\tag{33}
$$

The orthogonal residual is

$$
R_xV=(I-P_x)V
=V-F^{\mathsf T}G_C\omega.
\tag{34}
$$

Pythagoras gives the pointwise Schur-complement identity

$$
\boxed{
\mathbb E|V|^2
-\omega^{\mathsf T}G_C\omega
=\mathbb E|R_xV|^2\ge0.}
\tag{35}
$$

For every realization, $\mathscr A_t$ preserves volume. Consequently,

$$
\int_{\mathbb T^3}\mathbb E|V_t(x)|^2dx
=\mathbb E\int_{\mathbb T^3}
|\omega_0(\mathscr A_t(x))|^2dx
=W(0).
\tag{36}
$$

Integrating (35) and comparing with (26) yields

$$
\boxed{
\int_{\mathbb T^3}\mathbb E
\left|V-F^{\mathsf T}G_C\omega\right|^2dx
=2\nu\int_0^t\mathcal D_C(s)\,ds.}
\tag{37}
$$

The covariant viscous loss is exactly the component of sampled initial vorticity which the endpoint deformation regression fails to retain.

## 6. Active Rayleigh quotient

For $W(t)>0$, define

$$
\mathfrak A_C(t)=\frac{W(t)}{Z_C(t)},
\tag{38}
$$

with $\mathfrak A_C=1$ for the zero solution. Equations (32)–(33) give

$$
\boxed{
\mathfrak A_C(t)=
\frac{\displaystyle
\int_{\mathbb T^3}\|T_xP_xV\|_{\mathbb R^3}^2dx}
{\displaystyle
\int_{\mathbb T^3}\|P_xV\|_{\mathscr H}^2dx}.}
\tag{39}
$$

This is a Rayleigh quotient of the stochastic deformation operator on the projected component selected by the actual initial vorticity. A bound on $\sup_x\|T_x\|^2=\sup_x\lambda_{\max}(C)$ is sufficient for (39), while (39) permits large covariance in components absent from $P_xV$.

Equation (26) gives

$$
W(t)\le\mathfrak A_C(t)W(0).
\tag{40}
$$

On every interval on which $W$ and $Z_C$ are positive, smoothness makes them and $\mathfrak A_C$ locally continuously differentiable. Equations (4) and (26) then give

$$
\boxed{
\frac d{dt}\log\mathfrak A_C
=
\frac{2P}{W}
+2\nu\left(
\frac{\mathcal D_C}{Z_C}-\frac D W
\right)
=:\Gamma_C.}
\tag{40a}
$$

A sufficient differential target is

$$
\Gamma_C(t)
\le b_C(t)\left(1+\log_+\mathfrak A_C(t)\right),
\qquad b_C(t)\ge0\ \text{a.e.},
\qquad
\int_0^{\min(T,T_*)}b_C(t)\,dt
\le B_C(\nu,T,R)<\infty.
\tag{40b}
$$

Set $Y_C=1+\log_+\mathfrak A_C$. On the active branch, $Y_C'=\Gamma_C\le b_CY_C$; on the inactive branch, $Y_C'=0\le b_CY_C$. Hence

$$
\mathfrak A_C(t)
\le\exp\left[
Y_C(0)\exp\left(\int_0^t b_C(s)\,ds\right)-1
\right].
\tag{40c}
$$

Here $\mathfrak A_C(0)=1$ and $Y_C(0)=1$. This logarithmic Gronwall estimate supplies the uniform bound required below. The coefficient $b_C$ must be built from independently controlled quantities; defining it from $\Gamma_C$ would restate the target.

This produces the continuation statement.

**Proposition 1.** Fix $\nu>0$, finite $T>0$, and $R\ge0$. Suppose every
$u_0\in C^\infty(\mathbb T^3;\mathbb R^3)$ satisfying

$$
\int_{\mathbb T^3}u_0\,dx=0,
\qquad
\nabla\cdot u_0=0,
\qquad
\|u_0\|_{H^3}\le R
\tag{41}
$$

For each corresponding smooth solution, define $F$, $C$, $G_C$, and $\mathfrak A_C$ by (5)–(39), and suppose the resulting active quotient satisfies

$$
\boxed{
\sup_{0\le t<\min(T,T_*)}
\mathfrak A_C(t)
\le C_C(\nu,T,R)<\infty.}
\tag{42}
$$

Then every such solution continues through $T$.

**Proof.** Equations (40) and (42) give a uniform enstrophy bound through the smooth interval. On the mean-zero periodic divergence-free subspace, the Fourier curl identity and Poincaré inequality control the $H^1$ velocity norm by enstrophy. The standard local $H^1$ restart extends the solution at a finite endpoint. $\square$

Conversely, a finite maximal time forces enstrophy to become unbounded. Since (26) gives $Z_C\le W(0)$, finite-time loss of regularity forces $\mathfrak A_C$ to diverge along a sequence approaching that endpoint.

## 7. Determinant and the deformation-spread gap

Apply the matrix log-determinant chain rule to (12). Incompressibility removes the reaction trace:

$$
\begin{aligned}
\mathcal L_u\log\det C
&=\operatorname{tr}(G_C\mathcal L_uC)
+\nu\sum_k\operatorname{tr}
\left[(G_C\partial_kC)^2\right]\\
&=\nu\sum_k\operatorname{tr}
\left[(G_C\partial_kC)^2\right]\ge0.
\end{aligned}
\tag{43}
$$

Each matrix $G_C\partial_kC$ is similar to the symmetric matrix
$G_C^{1/2}(\partial_kC)G_C^{1/2}$, so the final traces are nonnegative. The periodic minimum principle and $C(0)=I$ give

$$
\det C(x,t)\ge1,
\qquad
\det G_C(x,t)\le1.
\tag{44}
$$

The determinant inequality records volume spreading among stochastic deformations. It permits one eigenvalue of $C$ to grow while another shrinks, so it supplies no uniform lower bound on $G_C$.

There is an exact comparison with the inverse-deformation metric in `turbulence/navier-stokes-adaptive-metric.md`. Set

$$
X=FF^{\mathsf T},
\qquad
H=\mathbb E[X^{-1}]
=\mathbb E[F^{-\mathsf T}F^{-1}].
\tag{45}
$$

The covariance-inverse metric is

$$
G_C=(\mathbb E X)^{-1}.
\tag{46}
$$

Direct expansion gives

$$
\boxed{
H-G_C
=\mathbb E\left[
(X^{-1}-G_C)X(X^{-1}-G_C)
\right]\succeq0.}
\tag{47}
$$

Equation (47) is the inverse-Jensen gap. Equivalently, it is the arithmetic-minus-harmonic gap for the random inverse-deformation metric $X^{-1}$: $\mathbb E[X^{-1}]$ is its arithmetic mean, while $(\mathbb E X)^{-1}$ is its matrix harmonic mean. Equality requires $X=\mathbb E X$ almost surely. The gap vanishes for a deterministic deformation and records stochastic deformation spread otherwise.

The two metric constructions make different trades. The unscaled $H$ lies above $G_C$ and has the determinant floor $\det H\ge1$, while its weighted-enstrophy balance contains a spatial-curvature cross-term. A scalar projection removes that cross-term. The metric $G_C$ is defined directly by (10) and (14); its nonlinear inverse equation builds the cross-term into the square (23), yielding (26) with no scalar projection. Its determinant has the opposite inequality in (44), and its active lower bound remains the theorem obligation.
This comparison is conditional on the smooth stochastic deformation and the
inverse-metric derivation cited there. The executable H1–H3 checks cover the
fixed matrix inverse-Jensen gap; they do not execute the evolution, weighted
balance, or determinant bound for $H$.

## 8. Exact controls

### 8.1 Homogeneous extension

Take the trace-free constant matrix

$$
L_a=\operatorname{diag}(a,-a,0),
\qquad a>0.
\tag{48}
$$

The deformation, covariance, and inverse metric are

$$
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1),
\tag{49}
$$

$$
C_a(t)=\operatorname{diag}(e^{2at},e^{-2at},1),
\qquad
G_a(t)=\operatorname{diag}(e^{-2at},e^{2at},1).
\tag{50}
$$

For the expanding state $\omega_a=e^{at}e_1$,

$$
\omega_a^{\mathsf T}G_a\omega_a=1,
\qquad
\mathfrak A_C^{\mathrm{loc}}=e^{2at},
\qquad
\det C_a=1.
\tag{51}
$$


This control is a local matrix specialization. It is curl-free, nonperiodic, and has infinite Euclidean energy as an affine velocity field. It classifies coercivity inferred from positivity, determinant, exact weighted cancellation, or unrestricted matrix algebra. A periodic Navier–Stokes estimate can use additional self-consistency absent from this control.

### 8.2 Periodic shear heat flow

Let

$$
u_s(y,t)=b e^{-\lambda t}\sin(ny)e_1,
\qquad
\lambda=\nu n^2,
\qquad n\in\mathbb N.
\tag{52}
$$

This is an exact unforced periodic solution because its advective term vanishes and it satisfies the heat equation. Put

$$
a_s(y,t)=bn e^{-\lambda t}\cos(ny).
\tag{53}
$$

The velocity gradient has only $(L_s)_{12}=a_s$. Equation (12) has the exact solution

$$
C_s=
\begin{pmatrix}
1+q_0(t)+q_2(t)\cos(2ny)&t a_s&0\\
t a_s&1&0\\
0&0&1
\end{pmatrix},
\tag{54}
$$

where

$$
q_0(t)=\frac{b^2n^2}{4\lambda^2}
\left[1-(1+2\lambda t)e^{-2\lambda t}\right],
\tag{55}
$$

$$
q_2(t)=\frac{b^2n^2}{4\lambda^2}e^{-4\lambda t}
\left[e^{2\lambda t}(2\lambda t-1)+1\right].
\tag{56}
$$

Indeed,

$$
q_0'=tb^2n^2e^{-2\lambda t},
\qquad
q_2'+4\lambda q_2=tb^2n^2e^{-2\lambda t},
\qquad
\mathcal L_u(ta_s)=a_s.
\tag{57}
$$

These are exactly the component equations in (12), with $C_s(\cdot,0)=I$. Uniqueness for that linear parabolic initial-value problem identifies $C_s$ with the covariance (10); its positive definiteness then follows from the stochastic representation. The upper-left block is the second moment of a random shear matrix.

The vorticity is

$$
\omega_s=-a_s e_3.
\tag{58}
$$

The third direction of $C_s$ and $G_s=C_s^{-1}$ is unchanged, so

$$
(G_s)_{33}=1,
\qquad
Z_C=W,
\qquad
\mathfrak A_C=1.
\tag{59}
$$

The covariance may be highly anisotropic in the first two directions while the vorticity-weighted metric remains Euclidean. This is the active-direction distinction required by (39).

## 9. Remaining estimate

The covariance-inverse law strengthens the adaptive-metric formulation in two ways:

1. the scalar work projection and its cumulative normalization disappear;
2. the stochastic deformation and sampled initial vorticity remain coupled through the exact projection $P_x$.

The remaining estimate is still substantial. From (39), a generic operator bound gives

$$
\mathfrak A_C(t)
\le\operatorname*{ess\,sup}_{x}
\lambda_{\max}(C(x,t)).
\tag{60}
$$

The direct maximum-principle estimate for the right-hand side depends on
$\int_0^t\|S(s)\|_\infty ds$, which is already a continuation-level quantity. The Navier–Stokes energy law only gives

$$
L=\nabla u\in L_t^2L_x^2.
\tag{61}
$$

As a coefficient of a matrix parabolic equation, this lies beyond the local parabolic scaling line $2/p+3/q=2$. Generic matrix-PDE estimates therefore do not close (42).

Equation (39) is weaker than (60). A useful proof may allow large singular
values of $T_x$ wherever $P_xV$ has no component in the corresponding
stochastic direction. The direct endpoint target is (42), while (40b) gives
a precise differential route to it.

The normalized covariant-dissipation term in (40a) also has an exact
regression meaning. Define

$$
\mathcal R_C(t)
:=\int\mathbb E
\left|V-F^{\mathsf T}G_C\omega\right|^2dx
=W(0)-Z_C(t).
$$

Then

The following identities hold at smooth times for which $Z_C(t)>0$; they make no assertion that the quotient has a finite limit at $T_*$:

$$
\boxed{
2\nu\frac{\mathcal D_C}{Z_C}
=\frac d{dt}\bigl[-\log Z_C\bigr]
=\frac{\mathcal R_C'}{W(0)-\mathcal R_C}.}
\tag{62}
$$

Thus the positive metric term in (40a) is the fractional rate at which
projected initial-vorticity energy is lost into the regression residual.
Equation (37) controls the unnormalized accumulated loss, while closing
(40b) requires control relative to the surviving denominator.

Two pieces of self-consistency remain available for such an estimate:

- $V=\omega_0\circ\mathscr A_t$ is generated from one fixed initial field and preserves its realization-wise spatial $L^2$ norm;
- $F$, $V$, $T_x$, and $P_x$ use the same stochastic flow rather than independent deformation and data samples.

Replacing these objects by an arbitrary matrix potential or factoring their correlated expectations discards the information introduced by the stochastic representation. The homogeneous extension tests that weakened problem and exhibits exponential active distortion. The periodic shear shows that the full coupled geometry can instead place all covariance in inactive directions.

A proof of (42), or a signed evolution inequality for (39) whose coefficients are controlled by the initial data, would advance the original regularity problem. Equations (26), (37), and (39) provide the exact objects for that attempt. The required uniform estimate remains **UNRESOLVED**.

## 10. Relation to Cassi

The construction uses the part of Cassi's field-intelligence viewpoint that survives mathematical translation: adaptive positive geometry must be generated by the dynamics, and only its action on the occupied state matters. Here that statement is exact. The covariance is produced by the same stochastic deformation that transports vorticity, and the active metric is evaluated on the projected initial-vorticity component.

No two-fluid constitutive term, golden-ratio coefficient, finite mode cutoff, or added damping enters (1)–(62). Such additions define modified equations. The result concerns the original unforced incompressible Navier–Stokes equation and derives its auxiliary objects from that equation alone.

The recent Weber mean–covariance work establishes that common-noise deformation covariances can obey closed deterministic equations and records the limits of mean-only deformation control. The present covariance uses the forward deformation in the stochastic Cauchy vorticity formula and then inverts its arithmetic mean. The projection and covariant-dissipation identities identify the data-conditioned quantity which a continuation proof must control.

## 11. Verification evidence

The audit-rechecked protocol is
`computations/navier-stokes-deformation-covariance-prereg.md`. Its verifier,
`computations/verify_navier_stokes_deformation_covariance.py`, executes 40
exact symbolic and fixed-control checks covering the stochastic-calculus
conversion, covariance and inverse equations, covariant square, active-growth
identity, finite-ensemble projection, inverse-Jensen gap, homogeneous
extension, and periodic shear. P7 and P8 are synthetic scalar prototypes for
the integrated-loss and positive-denominator rate algebra; they do not
independently verify (37) or (62) for a stochastic flow. Those endpoint
identities follow analytically from the projection theorem, volume
preservation, and the covariant weighted law. Stochastic-flow and
Navier–Stokes trajectory integration lie outside the executable schedule.
C7 and C8 exercise only the one-coordinate chain-rule and diagonal-SPD
sum-of-squares components of the analytic determinant argument. They do not
execute the covariance PDE evolution, incompressibility trace removal, or
torus minimum-principle step.

The source-bound final audit receipt is
`runs/navier_stokes_deformation_covariance/verification.audit-qualified-final.json`.
It reports the result after execution.

## 12. Conclusion

The forward-deformation covariance supplies a canonical positive metric for vorticity. Its inverse cancels stretching and turns the complete viscous contribution into one nonnegative covariant square. The same identity is an orthogonal-regression theorem: weighted enstrophy is retained projected initial-vorticity energy, and accumulated dissipation is the endpoint residual.

This removes the scalar normalization term from the adaptive-metric route and replaces a generic coercivity request with the active Rayleigh quotient (39). The exact controls show why this distinction matters. Homogeneous extension has exponentially growing active distortion despite determinant one; periodic shear can have anisotropic covariance and active distortion one.

The all-data obligation is (42). Its proof must use the shared stochastic origin of deformation and sampled initial vorticity strongly enough to control the data-conditioned quotient without assuming accumulated maximum strain. That estimate and arbitrary-data global regularity remain **UNRESOLVED**.

## References

- `turbulence/navier-stokes-adaptive-metric.md`—positive cancellation metrics, scalar work projection, determinant boundary, and active-distortion continuation criterion.
- `turbulence/navier-stokes-strain-departure.md`—initial-$H^3$ all-data target, cumulative critical production, and exact smooth controls.
- `turbulence/navier-stokes-stress-geometry.md`—strain freedom, filtered geometry, and conditional depletion estimates.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—official domains, data, and regularity problem.
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the 3-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic flow and Cauchy vorticity representation.
- T. Mahithitarmmatorn, [Exact mean–covariance dynamics of the Weber field in the stochastic Lagrangian representation of the 3D Navier–Stokes equations](https://arxiv.org/abs/2608.16915)—closed common-noise covariance equations, deformation-second-moment analysis, and mean-only obstructions.
- E. Miller, [A regularity criterion for the Navier–Stokes equation involving only the middle eigenvalue of the strain tensor](https://arxiv.org/abs/1710.05569)—strain-eigenvalue continuation criterion.
- E. Miller, [On the interaction of strain and vorticity for solutions of the Navier–Stokes equation](https://arxiv.org/abs/2407.02691)—strain–vorticity orthogonality and conditional regularity criteria.
