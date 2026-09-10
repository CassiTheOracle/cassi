# Replica Coherence and Viscous Compensation in Navier–Stokes

## Status: Derived conditional—September 2026

## Abstract

The Constantin–Iyer representation writes the vorticity of a smooth incompressible Navier–Stokes solution as the mean of a stochastic Cauchy vector. Two independent Brownian replicas give an exact overlap representation of physical enstrophy, while their mean squared disagreement gives the centred same-noise covariance. That covariance obeys a forced positive matrix equation. Its source is twice viscosity times the vorticity-gradient Gram matrix, so replica disagreement is generated directly by palinstrophy and subsequently transported by the same deformation that stretches vorticity.

Variation of constants converts the covariance source into a retarded occupation over every earlier time, spatial label, gradient direction, and Brownian history. Volume preservation yields the sharp instantaneous-source inequality

$$
\operatorname{tr}(FQF^{\mathsf T})\ge3(\det Q)^{1/3},
\qquad F\in SL(3).
$$

Applying the concave determinant root after source times and stochastic paths have accumulated gives a stronger rank-recovery functional

$$
\mathcal K(t)=3\int_{\mathbb T^3}(\det R)^{1/3}dx.
$$

It obeys

$$
6\nu\int_0^t\int_{\mathbb T^3}
|\det\nabla\omega(x,s)|^{2/3}\,dx\,ds
\le\mathcal K(t)\le\mathcal V(t).
$$

The sharpened occupation $\mathcal H=\mathcal E_M-\mathcal K$ bounds ordinary enstrophy from above. Its cumulative budget is total seeded stretching minus recovered covariance volume. An exact periodic rank-two Beltrami heat flow has $\det\nabla\omega=0$ at every point and time while $\det R>0$ on an open set at positive time, establishing temporal rank recovery inside the original equation. Periodic shear remains rank one and shows why recovery cannot have a uniform positive lower bound over every datum. A relative rank-recovery estimate would bound $\mathcal H$, while a signed cross-scale estimate would bound $W$ directly; either would imply continuation. Both uniform all-data estimates remain open.

## 1. Main result

Consider a smooth mean-zero divergence-free solution of the unforced periodic three-dimensional Navier–Stokes equation on a compact interval inside its smooth lifespan:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\nu>0.
\tag{1}
$$

Set

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

The enstrophy, palinstrophy, and vortex-stretching production are

$$
W(t)=\int_{\mathbb T^3}|\omega|^2dx,
\qquad
D(t)=\int_{\mathbb T^3}|\nabla\omega|^2dx,
\qquad
P(t)=\int_{\mathbb T^3}\omega\cdot S\omega\,dx.
\tag{3}
$$

They satisfy

$$
W'=2P-2\nu D.
\tag{4}
$$

Let $Y$ be the vorticity-seeded stochastic Cauchy field and define

$$
M=\mathbb E[YY^{\mathsf T}],
\qquad
R=M-\omega\omega^{\mathsf T}\succeq0.
\tag{5}
$$

The integrated seeded occupation and replica disagreement are

$$
\mathcal E_M(t)=\int_{\mathbb T^3}\operatorname{tr}M\,dx,
\qquad
\mathcal V(t)=\int_{\mathbb T^3}\operatorname{tr}R\,dx.
\tag{6}
$$

The first identity is the exact coherent–spread decomposition

$$
\boxed{\mathcal E_M(t)=W(t)+\mathcal V(t).}
\tag{7}
$$

The covariance has the forced evolution

$$
\boxed{
\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad
R(0)=0,}
\tag{8}
$$

where

$$
Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T}
=\sum_{k=1}^3(\partial_k\omega)(\partial_k\omega)^{\mathsf T}.
\tag{9}
$$

For the stochastic deformation $F_{s,t}$ from source time $s$ to observation time $t$, variation of constants gives the retarded occupation

$$
\boxed{
\mathcal V(t)=2\nu\int_0^t\int_{\mathbb T^3}
\mathbb E\operatorname{tr}
\left[F_{s,t}(a)Q_\omega(a,s)F_{s,t}(a)^{\mathsf T}\right]
\,da\,ds.}
\tag{10}
$$

Every realization is volume preserving. The arithmetic-geometric mean inequality therefore gives

$$
\boxed{
\mathcal V(t)\ge6\nu\int_0^tJ(s)ds,}
\qquad
J(s)=\int_{\mathbb T^3}|\det\nabla\omega(x,s)|^{2/3}dx.
\tag{11}
$$

Define the compensated occupation

$$
\mathcal G(t)=
\mathcal E_M(t)-6\nu\int_0^tJ(s)ds.
\tag{12}
$$

Then

$$
\boxed{0\le W(t)\le\mathcal G(t)\le\mathcal E_M(t).}
\tag{13}
$$

The estimate retains the positive occupation structure of $\mathcal E_M$ and subtracts a rigorously certified part of the stochastic spread. It uses no force, regularizer, hyperdiffusion, Cassi scalar, or added constitutive law.

Applying the determinant after covariance contributions have accumulated gives the sharper upper envelope $\mathcal H=\mathcal E_M-\mathcal K$ derived in §12. It can detect temporal completion of rank-one or rank-two source frames that the instantaneous functional $J$ does not see.

## 2. Stochastic Cauchy field and two replicas

On a compact interval inside the smooth lifespan, let $X_t(a)$ be the smooth Constantin–Iyer stochastic flow and let $\mathscr A_t=X_t^{-1}$:

$$
dX_t(a)=u(X_t(a),t)dt+\sqrt{2\nu}\,dB_t,
\qquad
X_0(a)=a.
\tag{14}
$$

The Brownian translation is common to all labels in one realization. Since $u$ is divergence free,

$$
\det\nabla_aX_t(a)=1
\tag{15}
$$

for every realization. Define

$$
F_t(x)=\bigl(\nabla_aX_t\bigr)(\mathscr A_t(x)),
\qquad
Y_t(x)=F_t(x)\omega_0(\mathscr A_t(x)).
\tag{16}
$$

The stochastic Cauchy formula is

$$
\boxed{\omega(x,t)=\mathbb E Y_t(x).}
\tag{17}
$$

Take two conditionally independent copies $Y^{(1)}$ and $Y^{(2)}$ driven by independent Brownian translations through the same deterministic velocity $u$. These are samples of the exact mean-field representation in (14)–(17). The finite-$N$ interacting system of Iyer and Mattingly replaces $u$ by an empirical velocity and is a separate construction.

Independence gives

$$
\mathbb E_{1,2}
\left[Y^{(1)}Y^{(2)\mathsf T}\right]
=\mathbb EY^{(1)}\,\mathbb EY^{(2)\mathsf T}
=\omega\omega^{\mathsf T}.
\tag{18}
$$

Taking the trace yields the overlap formula

$$
\boxed{
\mathbb E_{1,2}
\left[Y^{(1)}(x,t)\cdot Y^{(2)}(x,t)\right]
=|\omega(x,t)|^2.}
\tag{19}
$$

The squared difference yields the covariance formula

$$
\begin{aligned}
\frac12\mathbb E_{1,2}|Y^{(1)}-Y^{(2)}|^2
&=\mathbb E|Y|^2-|\mathbb EY|^2\\
&=\operatorname{tr}R.
\end{aligned}
\tag{20}
$$

After spatial integration,

$$
\boxed{
W(t)=\int_{\mathbb T^3}
\mathbb E_{1,2}[Y^{(1)}\cdot Y^{(2)}]dx,}
\tag{21}
$$

$$
\boxed{
\mathcal V(t)=\frac12\int_{\mathbb T^3}
\mathbb E_{1,2}|Y^{(1)}-Y^{(2)}|^2dx.}
\tag{22}
$$

Equations (21)–(22) make coherence operational. Physical enstrophy is the mean overlap of two stochastic formation histories. Viscous cancellation appears as the disagreement between them.

## 3. How viscosity creates stochastic spread

In Eulerian variables, $Y$ satisfies

$$
dY+\bigl(u\cdot\nabla Y-LY\bigr)dt
-\nu\Delta Y\,dt
+\sqrt{2\nu}\sum_k\partial_kY\,dB_t^k=0.
\tag{23}
$$

The same Brownian increment acts on every component. Itô's product rule gives

$$
\nu\left[(\Delta Y)Y^{\mathsf T}
+Y(\Delta Y)^{\mathsf T}\right]
+2\nu\sum_k(\partial_kY)(\partial_kY)^{\mathsf T}
=\nu\Delta(YY^{\mathsf T}).
\tag{24}
$$

This is the common-noise closure. Taking expectation gives

$$
\boxed{
\mathcal L_uM=LM+ML^{\mathsf T},
\qquad
M(0)=\omega_0\omega_0^{\mathsf T}.}
\tag{25}
$$

The deterministic vorticity satisfies

$$
\mathcal L_u\omega=L\omega.
\tag{26}
$$

Applying the diffusion product rule to its dyadic square gives

$$
\mathcal L_u(\omega\omega^{\mathsf T})
=L\omega\omega^{\mathsf T}
+\omega\omega^{\mathsf T}L^{\mathsf T}
-2\nu Q_\omega.
\tag{27}
$$

Subtracting (27) from (25) proves (8). The sign is decisive: $2\nu Q_\omega$ is positive semidefinite. Viscosity reduces the squared mean through cancellation while creating spread in the stochastic ensemble.

Taking the trace of (8) and integrating over the torus gives

$$
\boxed{
\mathcal V'(t)=2\int_{\mathbb T^3}S:R\,dx+2\nu D(t).}
\tag{28}
$$

Thus

$$
\mathcal V(0)=0,
\qquad
\mathcal V'(0)=2\nu D(0).
\tag{29}
$$

The immediate decoherence rate is exactly twice viscous palinstrophy. Later evolution includes strain acting on the covariance already created.

## 4. Retarded palinstrophy occupation

The local source in (8) can be propagated from every earlier time. Let $X_{s,t}(a)$ solve the stochastic flow beginning at $a$ at time $s$, let $\mathscr A_{s,t}=X_{s,t}^{-1}$, and set

$$
F_{s,t}(a)=\nabla_aX_{s,t}(a).
\tag{30}
$$

The homogeneous matrix equation associated with (8) preserves positive semidefiniteness. Duhamel's formula therefore gives

$$
R(x,t)=2\nu\int_0^t
\mathbb E
\left[
\left(
F_{s,t}Q_\omega(\,\cdot\,,s)F_{s,t}^{\mathsf T}
\right)\circ\mathscr A_{s,t}(x)
\right]ds.
\tag{31}
$$

Changing variables from endpoint $x$ to source label $a$ uses (15) and yields (10).

Write

$$
g_k(a,s)=\partial_k\omega(a,s),
\qquad
Q_\omega=\sum_kg_kg_k^{\mathsf T}.
\tag{32}
$$

For $D(s)>0$, the vorticity-gradient source defines the probability measure

$$
d\eta_s(a,k)=
\frac{|g_k(a,s)|^2}{D(s)}da,
\qquad
\sum_k\int_{\mathbb T^3}d\eta_s(a,k)=1.
\tag{33}
$$

For a nonzero transported source vector, let

$$
n_r^{s,a,k}=
\frac{F_{s,r}(a)g_k(a,s)}{|F_{s,r}(a)g_k(a,s)|}
\tag{34}
$$

and define its directional strain

$$
\sigma_r^{s,a,k}=
(n_r^{s,a,k})^{\mathsf T}
S(X_{s,r}(a),r)n_r^{s,a,k}.
\tag{35}
$$

Differentiating the transported norm gives

$$
\frac d{dr}\log|F_{s,r}(a)g_k(a,s)|
=\sigma_r^{s,a,k}.
\tag{36}
$$

Hence

$$
|F_{s,t}(a)g_k(a,s)|^2
=|g_k(a,s)|^2
\exp\left(2\int_s^t\sigma_r^{s,a,k}dr\right).
\tag{37}
$$

Substitution into (10) gives the scalar retarded representation

$$
\boxed{
\mathcal V(t)=2\nu\int_0^tD(s)
\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}dr\right)ds.}
\tag{38}
$$

A zero value of $D(s)$ contributes zero to (38). Equation (38) retains the full causal order:

$$
\text{vorticity gradient at }s
\longrightarrow
\text{viscous stochastic spread}
\longrightarrow
\text{directional deformation from }s\text{ to }t.
\tag{39}
$$

Initial formation data determine the vorticity and the first source distribution. The subsequent cascade enters through the time-indexed family $\eta_s$ and every deformation history $F_{s,t}$. This is a precise realization of whole-history dependence within the original Navier–Stokes dynamics.

## 5. Coherence-share dynamics

For positive denominators, define the coherent and spread production rates

$$
\alpha(t)=\frac{P(t)}{W(t)},
\qquad
\beta(t)=
\frac{\int_{
\mathbb T^3}S:R\,dx}{\mathcal V(t)}.
\tag{40}
$$

The global replica coherence is

$$
\boxed{
c(t)=\frac{W(t)}{\mathcal E_M(t)}
=1-\frac{\mathcal V(t)}{\mathcal E_M(t)},
\qquad 0\le c\le1.}
\tag{41}
$$

The active seeded production rate is

$$
\Gamma_M(t)=
\frac{\int_{
\mathbb T^3}S:M\,dx}{\mathcal E_M(t)}.
\tag{42}
$$

Since $M=\omega\omega^{\mathsf T}+R$,

$$
\boxed{\Gamma_M=c\alpha+(1-c)\beta.}
\tag{43}
$$

The three scalar balances are

$$
W'=2\alpha W-2\nu D,
\tag{44}
$$

$$
\mathcal V'=2\beta\mathcal V+2\nu D,
\tag{45}
$$

$$
\mathcal E_M'=2\Gamma_M\mathcal E_M.
\tag{46}
$$

Differentiating (41) and using (43)–(46) gives

$$
\boxed{
c'=2c(1-c)(\alpha-\beta)
-\frac{2\nu D}{\mathcal E_M}.}
\tag{47}
$$

On any interval where $W>0$ and $\mathcal E_M>0$, equivalently where $c>0$, the logarithmic coherence budget is

$$
\boxed{
\frac d{dt}\log c
=2(1-c)(\alpha-\beta)-\frac{2\nu D}{W}.}
$$

The first term is a replicator term: it compares strain production on the coherent mean with strain production on stochastic spread. The second term is the direct viscous transfer into disagreement. At the initial endpoint,

$$
c(0)=1,
\qquad
c'(0)=-\frac{2\nu D(0)}{W(0)}
\quad\text{when }W(0)>0.
\tag{48}
$$

Once both populations are positive, their odds satisfy

$$
\boxed{
\frac12\frac d{dt}\log\frac{W}{\mathcal V}
=\alpha-\beta
-\nu D\left(\frac1W+\frac1{\mathcal V}\right).}
\tag{49}
$$

The seeded occupation has the exact exponential form from `turbulence/navier-stokes-active-deformation-occupation.md`:

$$
\mathcal E_M(t)=W(0)
\exp\left(2\int_0^t\Gamma_M(s)ds\right).
\tag{50}
$$

Combining (38) and (50) in (7) gives

$$
\boxed{
\begin{aligned}
W(t)
={}&W(0)\exp\left(2\int_0^t\Gamma_M(s)ds\right)\\
&-2\nu\int_0^tD(s)
\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}dr\right)ds.
\end{aligned}}
\tag{51}
$$

The first positive term counts deformation-amplified seeded occupation. The second positive term is the amount lost from the coherent mean into stochastic disagreement. A useful regularity estimate may therefore control their compensation even when the first term alone is large.

## 6. A sharp volume-preserving lower bound

The stochastic deformation obeys

$$
F_{s,t}(a)\in SL(3)
\tag{52}
$$

for every realization. This constraint gives a pointwise optimization theorem.

**Lemma 1.** For every $F\in SL(3)$ and every symmetric positive semidefinite $Q$,

$$
\operatorname{tr}(FQF^{\mathsf T})
\ge3(\det Q)^{1/3}.
\tag{53}
$$

For positive definite $Q$, equality is attained by

$$
F_*(Q)=(\det Q)^{1/6}Q^{-1/2}.
\tag{54}
$$

**Proof.** First assume $Q$ is positive definite. The matrix

$$
A=FQF^{\mathsf T}
\tag{55}
$$

is positive definite and satisfies

$$
\det A=(\det F)^2\det Q=\det Q.
\tag{56}
$$

If $a_1,a_2,a_3$ are its eigenvalues, arithmetic-geometric mean gives

$$
\operatorname{tr}A=a_1+a_2+a_3
\ge3(a_1a_2a_3)^{1/3}
=3(\det Q)^{1/3}.
\tag{57}
$$

For (54),

$$
\det F_*=(\det Q)^{1/2}(\det Q)^{-1/2}=1
\tag{58}
$$

and

$$
F_*QF_*^{\mathsf T}=(\det Q)^{1/3}I,
\tag{59}
$$

which attains equality. Positive semidefinite $Q$ follows by continuity. $\square$

For $Q=Q_\omega$,

$$
\det Q_\omega
=\det\bigl[(\nabla\omega)(\nabla\omega)^{\mathsf T}\bigr]
=|\det\nabla\omega|^2.
\tag{60}
$$

Therefore

$$
(\det Q_\omega)^{1/3}
=|\det\nabla\omega|^{2/3}.
\tag{61}
$$

Apply Lemma 1 inside (10), then integrate in source time. This proves (11).

The bound is optimal among estimates using only $Q$ and $\det F=1$. For a rank-two source,

$$
Q_2=\operatorname{diag}(q_1,q_2,0),
\qquad
F_\varepsilon^{(2)}=
\operatorname{diag}(\varepsilon,\varepsilon,\varepsilon^{-2}),
\tag{62}
$$

so

$$
\det F_\varepsilon^{(2)}=1,
\qquad
\operatorname{tr}
(F_\varepsilon^{(2)}Q_2F_\varepsilon^{(2)\mathsf T})
=\varepsilon^2(q_1+q_2)\to0.
\tag{63}
$$

For a rank-one source,

$$
Q_1=\operatorname{diag}(q_1,0,0),
\qquad
F_\varepsilon^{(1)}=
\operatorname{diag}(\varepsilon,\varepsilon^{-1/2},\varepsilon^{-1/2}),
\tag{64}
$$

and

$$
\det F_\varepsilon^{(1)}=1,
\qquad
\operatorname{tr}
(F_\varepsilon^{(1)}Q_1F_\varepsilon^{(1)\mathsf T})
=q_1\varepsilon^2\to0.
\tag{65}
$$

Volume preservation controls the product of three transported singular values. It supplies no positive lower trace bound when the source occupies fewer than three independent directions. Any estimate covering those source frames must use orientation dynamics, time persistence, incompressibility beyond the determinant constraint, or relations among neighboring source times.

## 7. Conditional continuation theorem

The compensation in (12) gives a direct all-data target.

**Proposition 1.** Fix $\nu>0$, finite $T>0$, and finite $R_0\ge0$. Suppose every smooth mean-zero divergence-free periodic datum satisfying

$$
\|u_0\|_{H^3}\le R_0
\tag{66}
$$

has a smooth solution on $[0,T_*)$ for which

$$
\boxed{
\sup_{0\le t<\min(T,T_*)}
\mathcal G(t)
\le C_G(\nu,T,R_0)<\infty.}
\tag{67}
$$

Then each such solution continues through time $T$.

**Proof.** Equation (13) gives

$$
\sup_{0\le t<\min(T,T_*)}W(t)
\le C_G(\nu,T,R_0).
\tag{68}
$$

For mean-zero periodic divergence-free velocity, the Fourier curl identity and Poincaré inequality control the velocity $H^1$ norm by enstrophy. The standard local $H^1$ restart criterion extends the solution at any finite endpoint with a uniform lifespan depending on the bound in (68). Therefore $T_*\le T$ is impossible. $\square$

Conversely, finite-time loss of regularity would force $W$ and hence $\mathcal G$ to become unbounded along an endpoint sequence. The criterion is scale critical in the same formal Euclidean sense as enstrophy. Under

$$
u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t),
\qquad
\omega_\lambda(x,t)=\lambda^2\omega(\lambda x,\lambda^2t),
\tag{69}
$$

$W$, $\mathcal E_M$, $\mathcal V$, and $\nu\int Jdt$ all have scaling exponent one. Their ratios have exponent zero. The rescaling changes the period of a fixed torus.

The open obligation is the uniform estimate (67). Positivity and volume preservation prove the subtracted lower bound in (12); they do not bound the remaining compensation gap

$$
\mathcal G-W
=\mathcal V-6\nu\int_0^tJ(s)ds.
\tag{70}
$$

## 8. Exact controls

### 8.1 Periodic shear

Consider

$$
u_n(y,t)=e^{-\nu n^2t}\sin(ny)e_1,
\qquad
\omega_n(y,t)=-n e^{-\nu n^2t}\cos(ny)e_3.
\tag{71}
$$

This is an exact periodic Navier–Stokes heat flow. Its vorticity-gradient Gram matrix has rank one wherever nonzero, so

$$
J(t)=0.
\tag{72}
$$

For the stochastic flow, $F_te_3=e_3$ and the sampled label has

$$
\mathscr A_{t,y}(y)=y-\sqrt{2\nu}B_t^y.
\tag{73}
$$

The stochastic Cauchy vector is therefore

$$
Y_t(y)=-n\cos
\left[n\left(y-\sqrt{2\nu}B_t^y\right)\right]e_3.
\tag{74}
$$

Spatial translation leaves its integrated square unchanged. Brownian averaging supplies the heat factor in the mean, so

$$
\boxed{
\mathcal E_M(t)=W(0),
\qquad
W(t)=W(0)e^{-2\nu n^2t},
\qquad
\mathcal V(t)=W(0)(1-e^{-2\nu n^2t}).}
\tag{75}
$$

The exact disagreement accounts for all enstrophy decay in this control, while the determinant lower bound captures none of it. This is the principal rank-deficient limitation of (11).

### 8.2 Homogeneous extension

The local trace-free deformation

$$
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1)
\tag{76}
$$

with deterministic seed $Y_0=e_1$ gives

$$
R=0,
\qquad
c=1,
\qquad
\mathcal E_M(t)=W(t)=e^{2at}W(0).
\tag{77}
$$

A volume-preserving deformation can amplify every occupied replica identically and create no disagreement. This curl-free affine control is nonperiodic and has infinite Euclidean energy. It isolates the deformation-algebra boundary and supplies no Navier–Stokes counterexample.

### 8.3 Exact periodic ABC heat flow

On the $2\pi$-periodic torus, define

$$
u_{\mathrm{ABC}}(x,y,z)=
(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x).
\tag{78}
$$

Direct differentiation gives

$$
\nabla\cdot u_{\mathrm{ABC}}=0,
\qquad
\nabla\times u_{\mathrm{ABC}}=u_{\mathrm{ABC}},
\qquad
\Delta u_{\mathrm{ABC}}=-u_{\mathrm{ABC}}.
\tag{79}
$$

Since $u\times\omega=0$, the nonlinear term is a Bernoulli gradient. Thus

$$
u(x,t)=e^{-\nu t}u_{\mathrm{ABC}}(x)
\tag{80}
$$

Together with the corresponding Bernoulli pressure $p(x,t)=-e^{-2\nu t}|u_{\mathrm{ABC}}(x)|^2/2$, equation (80) is an exact unforced Navier–Stokes solution. Its vorticity-gradient determinant is

$$
\det\nabla\omega(x,y,z,t)
=e^{-3\nu t}
\left(
\cos x\cos y\cos z-
\sin x\sin y\sin z
\right).
\tag{81}
$$

The expression in parentheses equals one at the origin, so it is nonzero on a set of positive measure. Consequently,

$$
\boxed{J(t)=e^{-2\nu t}J(0),
\qquad J(0)>0.}
\tag{82}
$$

The full-rank compensation term is therefore active in a genuine smooth periodic three-dimensional flow.

## 9. What the reduction establishes

The exact statements are:

1. Independent stochastic Cauchy replicas recover enstrophy through overlap and covariance through disagreement.
2. The centred covariance is forced by $2\nu Q_\omega$ and starts at zero.
3. Replica disagreement is a retarded palinstrophy occupation weighted by subsequent directional deformation.
4. Global coherence obeys the replicator-diffusion equation (47).
5. Volume preservation forces the sharp instantaneous-source lower bound (11).
6. The accumulated determinant root $\mathcal K$ is nondecreasing, dominates the instantaneous-source determinant integral, and is bounded above by replica disagreement.
7. A rank-two periodic Beltrami heat flow has $J=0$ while its accumulated covariance becomes full rank on an open set.
8. The sharpened occupation $\mathcal H=\mathcal E_M-\mathcal K$ bounds enstrophy from above.
9. A uniform initial-$H^3$-controlled bound on $\mathcal H$ implies continuation over every finite horizon.

The unresolved statements are:

1. a uniform bound on $\mathcal H$ over every bounded initial-data ball;
2. a production-relative recovery or rigidity estimate for rank-one and rank-two source histories;
3. a signed cross-scale stretching estimate with data-controlled time integrals;
4. a Navier–Stokes estimate connecting the active strain rates $\alpha$ and $\beta$;
5. any implication from the canonical Cassi scalar $q$ or from geometric scale spacing alone;
6. arbitrary-data global regularity.

No singular solution, regularity proof, numerical near-singularity, or physical field-to-vorticity identification is claimed.

## 10. Cassi interpretation

The derivation was prompted by Cassi's distinction between a coherent signal and the spread of its available histories. The mathematical construction now has a precise Navier–Stokes meaning:

$$
\text{coherent state}
\longleftrightarrow
\mathbb EY=\omega,
\tag{83}
$$

$$
\text{history spread}
\longleftrightarrow
R=\operatorname{Cov}(Y),
\tag{84}
$$

$$
\text{coherence fraction}
\longleftrightarrow
c=\frac{|\mathbb EY|_{L^2}^2}{\mathbb E|Y|_{L^2}^2}.
\tag{85}
$$

The field dynamics in this paper are entirely Navier–Stokes dynamics. Cassi contributes the question that selects the observable: how much of the transported formation history survives as common overlap, and how much becomes mutually cancelling spread? The resulting answer is sharper than the canonical scalar $q$ for this problem because it is constructed from the actual stochastic vorticity histories and their deformation.

Equation (38) also sharpens the role of initial conditions. Initial vorticity seeds the stochastic Cauchy field, while new viscous disagreement is seeded at every later time by $\nabla\omega$. The entire formation cascade appears as an ordered family of source measures and deformation propagators. A local slow-field state cannot replace that information without a proved closure.

The dimensionless quantity

$$
\mathfrak C(t)=
\frac{6\nu\int_0^tJ(s)ds}{\mathcal E_M(t)}
\tag{86}
$$

is the fraction of total seeded occupation whose conversion into disagreement is certified solely by full-rank mixing and volume preservation. Equations (11) and (41) imply

$$
0\le\mathfrak C(t)
\le1-c(t).
\tag{87}
$$

This quantity is a derived diagnostic. It introduces no golden-ratio coefficient and no additional fluid law.

## 11. Next analytical targets

The reduction isolates three routes toward a uniform bound on the sharpened envelope in §12.

### 11.1 Production-relative rank recovery

The instantaneous full-rank region is handled by $J$, while $\mathcal K$ also detects singular source frames whose transported ranges complete one another over source time and stochastic paths. An all-data estimate cannot demand a fixed positive recovery rate because zero data and periodic shear are admissible. The required bound must instead compare recovered covariance-volume production with the seeded stretching that needs compensation.

With the accumulated quantities defined in §12, the exact uncompensated production is

$$
\mathcal H(t)-W(0)
=
2\int_0^t\int_{\mathbb T^3}S:M\,dx\,dr
-\mathcal K(t).
\tag{88}
$$

### 11.2 Recovery-or-rigidity alternative

Weak recent-Gramian coercivity means that one direction remains nearly orthogonal to most transported source ranges. A quantitative inverse theorem could turn this near-common kernel into approximate dimensional reduction, vorticity-direction coherence, or depleted stretching. The complementary case would charge substantial spanning directly to $\mathcal K$. Establishing either implication from the original Navier–Stokes dynamics remains open.

The quantitative recovery observable is

$$
\lambda_{\min}(\mathscr R_{s,t}(x))
=
\inf_{|v|=1}
\int_s^t
\mathbb E
\left|
Q_\omega^{1/2}F_{r,t}^{\mathsf T}v
\right|^2
\circ\mathscr A_{r,t}(x)\,dr.
\tag{89}
$$

### 11.3 Signed cross-scale compensation

Advective shell transfer has an exact telescoping flux because it conserves total enstrophy. Vortex stretching is a genuine source and must be retained separately. The sufficient shell estimate in §12.6 permits signed backscatter and requires data-controlled time integrals; geometric spacing or triadic locality alone supplies neither the needed sign nor the bound.

These routes preserve the original Navier–Stokes equation and target continuation through $\mathcal H$ or $W$.

## 12. Accumulated rank recovery and sharpened compensation

### 12.1 Determinant recovery after accumulation

For a positive semidefinite $3\times3$ matrix define

$$
\Phi(A)=(\det A)^{1/3},
\qquad
\mathcal K(t)=3\int_{\mathbb T^3}\Phi(R(x,t))dx.
\tag{90}
$$

The determinant root is continuous, concave, and homogeneous of degree one on the positive-semidefinite cone. Concavity and homogeneity imply superadditivity:

$$
\Phi(A+B)\ge\Phi(A)+\Phi(B),
\qquad A,B\succeq0.
\tag{91}
$$

**Theorem 2.** On every compact interval inside the smooth lifespan,

$$
\boxed{
\mathcal K(t)\ge
\mathcal K(s)+6\nu\int_s^tJ(r)dr,
\qquad
0\le s\le t,}
\tag{92}
$$

and

$$
\boxed{0\le\mathcal K(t)\le\mathcal V(t).}
\tag{93}
$$

**Proof.** Let the positive homogeneous matrix propagator be

$$
\mathscr U_{s,t}A(x)=
\mathbb E\!\left[
\left(F_{s,t}AF_{s,t}^{\mathsf T}\right)
\circ\mathscr A_{s,t}(x)
\right].
\tag{94}
$$

The covariance Duhamel formula from any intermediate time is

$$
R(t)=\mathscr U_{s,t}R(s)
+2\nu\int_s^t\mathscr U_{r,t}Q_\omega(r)dr.
\tag{95}
$$

Jensen's inequality for the concave function $\Phi$, followed pathwise by the volume-preserving change of variables $x=X_{s,t}(a)$, gives

$$
\int_{\mathbb T^3}\Phi(\mathscr U_{s,t}A)dx
\ge
\int_{\mathbb T^3}\Phi(A)dx.
\tag{96}
$$

Apply superadditivity and homogeneity to (95), use (96) on every source contribution, and integrate in source time. This proves (92). Pointwise arithmetic-geometric mean gives $3\Phi(R)\le\operatorname{tr}R$, proving (93). The argument works directly for singular matrices by continuity on the positive-semidefinite cone. $\square$

The recent source Gramian

$$
\mathscr R_{s,t}(x)=
\int_s^t\mathscr U_{r,t}Q_\omega(r)(x)dr
\tag{97}
$$

retains more than the separate determinants of its source matrices. The same proof gives

$$
\boxed{
\mathcal K(t)\ge
\mathcal K(s)
+6\nu\int_{\mathbb T^3}\Phi(\mathscr R_{s,t})dx
\ge
\mathcal K(s)+6\nu\int_s^tJ(r)dr.}
\tag{98}
$$

At $s=0$, the first inequality is an equality because $R(0)=0$ and $R(t)=2\nu\mathscr R_{0,t}$.

Define the recovered-rank envelope

$$
\mathcal H(t)=\mathcal E_M(t)-\mathcal K(t)
=W(t)+\mathcal V(t)-\mathcal K(t).
\tag{99}
$$

Equations (12), (92), and (93) yield

$$
\boxed{
0\le W(t)\le\mathcal H(t)\le\mathcal G(t)\le\mathcal E_M(t).}
\tag{100}
$$

### 12.2 Local production law

At a time for which $R$ is positive definite throughout the torus, put $\rho_R=\Phi(R)$. Its first two matrix derivatives are

$$
D\Phi_R[A]=\frac{\rho_R}{3}\operatorname{tr}(R^{-1}A),
\tag{101}
$$

$$
D^2\Phi_R[A,A]
=\rho_R\left[
\frac19\bigl[\operatorname{tr}(R^{-1}A)\bigr]^2
-\frac13\operatorname{tr}(R^{-1}AR^{-1}A)
\right].
\tag{102}
$$

For

$$
B_k=R^{-1/2}(\partial_kR)R^{-1/2},
\tag{103}
$$

the chain rule, $\operatorname{tr}L=0$, and periodic integration give, under the same positive-definite hypothesis,

$$
\boxed{
\begin{aligned}
\mathcal K'(t)
={}&2\nu\int_{\mathbb T^3}
\rho_R\operatorname{tr}(R^{-1}Q_\omega)dx\\
&+\nu\sum_{k=1}^3\int_{\mathbb T^3}
\rho_R\left[
\operatorname{tr}(B_k^2)
-\frac13\bigl[\operatorname{tr}(B_k)\bigr]^2
\right]dx.
\end{aligned}}
\tag{104}
$$

Both displayed terms are nonnegative. The matrix stretching drops out because

$$
\operatorname{tr}\!\left[
R^{-1}(LR+RL^{\mathsf T})
\right]
=2\operatorname{tr}L=0.
\tag{105}
$$

Arithmetic-geometric mean applied to $R^{-1/2}Q_\omega R^{-1/2}$ gives $\mathcal K'\ge6\nu J$ on this positive-definite region. The integral theorem supplies the corresponding statement through singular strata.

Under the same positive-definite hypothesis, $\mathcal E_M'=2\int S:M\,dx$ gives

$$
\boxed{
\mathcal H'
=2\int_{\mathbb T^3}S:M\,dx-\mathcal K'.}
\tag{106}
$$

### 12.3 Exact Gramian criterion

For every $v\in\mathbb R^3$,

$$
\boxed{
v^{\mathsf T}\mathscr R_{s,t}(x)v
=
\int_s^t
\mathbb E
\left|
Q_\omega^{1/2}
F_{r,t}^{\mathsf T}v
\right|^2
\circ\mathscr A_{r,t}(x)\,dr.}
\tag{107}
$$

Consequently,

$$
\boxed{
\mathscr R_{s,t}(x)\succ0
\iff
\operatorname*{ess\,span}_{r,B}
F_{r,t}\operatorname{Ran}Q_\omega(r)
=\mathbb R^3.}
\tag{108}
$$

The essential qualifier is necessary: independent directions encountered only on source-time or path sets of measure zero do not contribute. Quantitative recovery requires a lower bound on the quadratic form in (107); matrix rank records only its positivity.

### 12.4 Exact rank-two recovery control

On the $2\pi$-periodic torus let

$$
v(x,y,z)=
\left(\cos y,\ \sin x,\ \sin y+\cos x\right),
\qquad
u(x,t)=e^{-\nu t}v(x),
\qquad
p(x,t)=-\frac12|u(x,t)|^2.
\tag{109}
$$

Direct differentiation gives

$$
\nabla\cdot v=0,
\qquad
\nabla\times v=v,
\qquad
\Delta v=-v,
\qquad
(v\cdot\nabla)v=\nabla\frac{|v|^2}{2}.
\tag{110}
$$

Thus (109) is an exact smooth unforced Navier–Stokes solution. It is independent of $z$, so

$$
\operatorname{rank}Q_\omega\le2,
\qquad
\det Q_\omega=0,
\qquad
J(t)=0
\tag{111}
$$

at every point and time. Writing $L_0=\nabla v(0,0,z)$ gives

$$
L_0=
\begin{pmatrix}
0&0&0\\
1&0&0\\
0&1&0
\end{pmatrix},
\qquad
Q_0=L_0L_0^{\mathsf T}
=\operatorname{diag}(0,1,1).
\tag{112}
$$

Differentiating the covariance equation at $t=0$ gives

$$
R'(0)=2\nu Q_0,
\qquad
R''(0)=
\begin{pmatrix}
4\nu^2&0&0\\
0&-8\nu^2&4\nu\\
0&4\nu&-4\nu^2
\end{pmatrix}.
\tag{113}
$$

Therefore

$$
\boxed{
\det R(0,0,z,t)
=8\nu^4t^4+O(t^5)>0}
\tag{114}
$$

The verifier checks the exact flow identities, the two covariance derivatives, and the $8\nu^4$ coefficient obtained from the truncated time jet. Smooth covariance evolution supplies the remainder in (114). Positivity of $R$ and spatial continuity then imply $R\succ0$ on an open set for sufficiently small positive time, so $\mathcal K(t)>0$ while $J(t)=0$. Source-time accumulation, spatial sampling, and deformation complete the missing covariance direction.

### 12.5 Relative compensation criterion

**Proposition 2.** Fix $\nu>0$, finite $T>0$, and $R_0<\infty$. Suppose there are $0\le\theta<1$ and nonnegative functions $a,b$ such that every smooth solution with $\|u_0\|_{H^3}\le R_0$ satisfies, for every $t<\min(T,T_*)$,

$$
\boxed{
2\int_0^t\int_{\mathbb T^3}S:M\,dx\,ds
\le
\theta\mathcal K(t)
+2\int_0^ta(s)\mathcal H(s)ds
+2\int_0^tb(s)ds,}
\tag{115}
$$

and

$$
\sup_{u_0}\int_0^{\min(T,T_*)}a(t)dt<\infty,
\qquad
\sup_{u_0}\int_0^{\min(T,T_*)}b(t)dt<\infty.
\tag{116}
$$

Then every such solution continues through $T$.

Indeed, $\mathcal H(t)+\mathcal K(t)=\mathcal E_M(t)=W(0)+2\int_0^t\int_{\mathbb T^3}S:M\,dx\,ds$ on every smooth interval. Applying (115) gives

$$
\mathcal H(t)+(1-\theta)\mathcal K(t)
\le
W(0)
+2\int_0^ta(s)\mathcal H(s)ds
+2\int_0^tb(s)ds.
\tag{117}
$$

Writing $A(t)=\int_0^ta(s)ds$, Gronwall yields

$$
\boxed{
\mathcal H(t)
\le
e^{2A(t)}
\left[
W(0)+2\int_0^te^{-2A(s)}b(s)ds
\right].}
\tag{118}
$$

The uniform bound on $\mathcal H$ controls enstrophy by (100), and the periodic $H^1$ restart completes the continuation argument. Deriving (115)–(116) from initial-data control is unresolved. Full rank alone cannot provide it: periodic shear has $\mathcal K=0$, and nearly rank-deficient data can have arbitrarily small recovered eigenvalues. Even isotropic $R$ leaves $\mathcal H=W$.

### 12.6 Canonical signed shell target

On the $2\pi$ torus, let $\Pi_j$ be the orthogonal Fourier projection onto

$$
\mathscr S_j=
\{k\in\mathbb Z^3:2^j\le|k|<2^{j+1}\},
\qquad
\omega_j=\Pi_j\omega,
\qquad
W_j=\|\omega_j\|_2^2,
\qquad
D_j=\|\nabla\omega_j\|_2^2.
\tag{119}
$$

Split nonlinear shell transfer into advection and stretching:

$$
A_j=-\langle\omega_j,\Pi_j(u\cdot\nabla\omega)\rangle,
\qquad
S_j=\langle\omega_j,\Pi_j(\omega\cdot\nabla u)\rangle.
\tag{120}
$$

Orthogonality and periodic incompressibility give

$$
\frac12W_j'=A_j+S_j-\nu D_j,
\qquad
\sum_jA_j=0,
\qquad
\sum_jS_j=P.
\tag{121}
$$

The canonical advective boundary flux

$$
\mathscr F_N=-\sum_{j=0}^NA_j
\tag{122}
$$

satisfies $A_j=\mathscr F_{j-1}-\mathscr F_j$, with $\mathscr F_{-1}=0$ and $\mathscr F_N\to0$ on compact smooth intervals. The substantive sufficient estimate is therefore a stretching bound

$$
\boxed{
S_j\le
\theta\nu D_j+a_{\mathrm{sh}}(t)W_j+b_j(t),
\qquad
0\le\theta<1,}
\tag{123}
$$

where $a_{\mathrm{sh}},b_j\ge0$, $b_{\mathrm{sh}}=\sum_jb_j$, and the time integrals of $a_{\mathrm{sh}}$ and $b_{\mathrm{sh}}$ are bounded uniformly over the initial-data ball. With $A_{\mathrm{sh}}(t)=\int_0^ta_{\mathrm{sh}}(s)ds$, summation and an integrating factor give

$$
\boxed{
\begin{aligned}
W'+2(1-\theta)\nu D
&\le2a_{\mathrm{sh}}W+2b_{\mathrm{sh}},\\
W(t)&\le
e^{2A_{\mathrm{sh}}(t)}
\left[
W(0)+2\int_0^te^{-2A_{\mathrm{sh}}(s)}b_{\mathrm{sh}}(s)ds
\right].
\end{aligned}}
\tag{124}
$$

The shell identities and conditional implication are exact. The uniform estimate (123) is unresolved. The standard bound $|P|\lesssim W^{3/4}D^{3/4}$ leaves a cubic enstrophy remainder after viscous absorption, while interaction locality alone supplies no sign for three-dimensional stretching or backscatter.

## 13. Verification evidence

The source-bound verifier is

```text
python computations/verify_navier_stokes_replica_coherence.py
```

It executes the 60 checks frozen in `computations/navier-stokes-replica-coherence-prereg.md`. The checked components cover:

- finite independent-replica factorization and disagreement algebra;
- common-noise and independent-noise product corrections;
- the centred covariance source and initial value;
- constant-matrix Duhamel and directional occupation identities;
- coherence-share, logarithmic, and odds balances;
- determinant transport, the sharp equality case, and singular-rank collapse;
- determinant-root differential components and trace-free stretching cancellation under positive-definite covariance;
- matrix-trace derivations of the sharpened-envelope decomposition and production identity;
- the recent-Gramian quadratic form and a fixed spanning control;
- Navier–Stokes scaling exponents;
- exact periodic shear, homogeneous extension, and ABC controls;
- exact rank-two flow identities, covariance time-jet components, and recovered determinant coefficient;
- fixed three-shell chain-rule, telescoping, boundary, and integrating-factor components.

The stochastic-flow representation, positive matrix propagator, general Duhamel step, determinant-root concavity, singular-stratum extension, Gramian spanning criterion, covariance-jet remainder and open-set implication, orthogonal shell-projection derivation, infinite-shell convergence, ultraviolet flux limit, assumed shell-bound signs, Gronwall step, and continuation implications remain analytical arguments under the stated smoothness hypotheses. The verifier does not integrate a generic Navier–Stokes trajectory or simulate Brownian paths.

The selected local evidence bundle is

```text
runs/navier_stokes_replica_coherence_rank_recovery_20260910_final_qualified/verification.json
runs/navier_stokes_replica_coherence_rank_recovery_20260910_final_qualified/verification.inputs.json
runs/navier_stokes_replica_coherence_rank_recovery_20260910_final_qualified/verification.sources/
```

The bundle records raw source hashes for this paper, the frozen protocol, and the verifier.

## 14. Sources

- `turbulence/navier-stokes-active-deformation-occupation.md`—vorticity-seeded common-noise moment and active deformation occupation
- `turbulence/navier-stokes-deformation-covariance.md`—forward-deformation covariance, inverse metric, and endpoint regression
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—uniform-noise stochastic flow and vorticity Cauchy formula
- G. Iyer and J. Mattingly, [A stochastic-Lagrangian particle system for the Navier–Stokes equations](https://arxiv.org/abs/0803.1222)—independent stochastic-flow replicas and finite-ensemble approximation
- T. D. Drivas and G. L. Eyink, [A Lagrangian fluctuation-dissipation relation for scalar turbulence, I](https://arxiv.org/abs/1606.00729)—scalar fluctuation-dissipation identity
- G. L. Eyink, A. Gupta, and T. Zaki, [Stochastic Lagrangian Dynamics of Vorticity. I. General Theory](https://arxiv.org/abs/1912.06677)—stochastic Cauchy invariants, cancellation, and ensemble variance
- G. L. Eyink and H. Aluie, [Localness of energy cascade in hydrodynamic turbulence, I. Smooth coarse-graining](https://arxiv.org/abs/0909.2386)—scale-locality estimates under declared inertial-range scaling assumptions
