# Filtered Stress Geometry in Periodic Incompressible Navier–Stokes

## Status: Derived conditional filtered identities; Hypothesized geometric closure—September 2026

## Abstract

The Gaussian-filtered form of the original three-dimensional incompressible Navier–Stokes equation retains a velocity covariance, third central moment, pressure covariance, and gradient covariance. This paper derives their exact contribution to stress, strain, and signed transfer $\Pi_\ell=-S_\ell:\tau_\ell$ on the periodic torus. The anisotropy ratio $R_\ell=\|\tau_{\ell,\mathrm{dev}}\|_F/\operatorname{tr}\tau_\ell$ bounds local transfer. Its all-scale representation gives a conditional Gronwall and Serrin continuation estimate when the spatial-and-scale supremum of $\|S_\ell\|_F R_\ell$ has a data-controlled time integral. Establishing that control from the original dynamics remains open.

An equal-weight, equal-speed phase average of two helical tangent dyads gives axisymmetric stress eigenvalues and
$$
R_\ell=\frac{|2-s^2|}{\sqrt 6(1+s^2)},\qquad s=ak,
$$
with isotropy at $s=\sqrt2$. The phase average, zero-mean interpretation, and identification with a Navier–Stokes filtered covariance are additional assumptions. A volume-preserving affine deformation gives the prescribed strain coefficient $\alpha(s)=\sigma(1-s^2/2)/(1+s^2)$ and the evolution $a=a_0e^{-\sigma t/2}$, $k=k_0e^{-\sigma t}$, $s=s_0e^{-3\sigma t/2}$, while a compactly supported curl-potential proves that any prescribed symmetric trace-free local strain can be changed while local vorticity is held fixed. Finally, the smooth admissible field $u=(\sin y,\sin z,\sin x)$ with initially constant pressure gives $\tau_\ell=T I$, $\Pi_\ell=0$ at the origin, but $\tau_{\ell,t}^{\mathrm{dev}}=-2T S_\ell$ and $\Pi_{\ell,t}=3Tg^2>0$. This is a local isotropy-preservation obstruction for an initial datum, while it does not decide every nonlocal or time-integrated condition. The equations retain nonclosure through $Q$, pressure, and dissipation, and no Cassi-to-Navier–Stokes constitutive map is established.

## 1. Scope, conventions, and the filtered momentum equation

The calculation concerns the original unforced equations and uses no additional Cassi field as a force. Let $u(x,t)$ be a smooth, mean-zero, periodic solution on $\mathbb T^3$, with
$$
\partial_tu_i+u_j\partial_j u_i=-\partial_i p+\nu\Delta u_i,
\qquad \partial_i u_i=0,
\qquad \nu>0.
$$
The pressure is defined up to a spatial constant. Angle brackets $\langle\cdot\rangle$ denote normalized spatial mean and repeated spatial indices are summed from $1$ to $3$.

For a fixed filter length $\ell>0$, define the Gaussian filter by its Fourier multiplier
$$
\widehat{\bar f_\ell}(k)=e^{-\ell^2|k|^2/2}\widehat f(k),
\qquad k\in\mathbb Z^3.
$$
It commutes with spatial derivatives, preserves the spatial mean, and preserves incompressibility. Write $U_i=\bar u_{\ell,i}$ and
$$
A_{ij}=\partial_jU_i,
\qquad S_{ij}=\frac12(A_{ij}+A_{ji}),
\qquad \Omega_{ij}=\frac12(A_{ij}-A_{ji}).
$$
Thus $\operatorname{tr}A=\operatorname{tr}S=0$. Define the covariance and the filtered material derivative by
$$
\tau_{ij}=\overline{u_i u_j}-U_iU_j,
\qquad
\bar D_t=\partial_t+U_j\partial_j.
$$
For every vector $a$ and output point $x$, $a_i\tau_{ij}(x)a_j=\overline{(a_i[u_i(y)-U_i(x)])^2}(x)\ge0$; hence $\tau$ is positive semidefinite and $\operatorname{tr}\tau\ge0$.

Filtering the momentum equation and using incompressibility gives
$$
\boxed{\bar D_tU_i=-\partial_i\bar p+\nu\Delta U_i-\partial_j\tau_{ij}.}
$$
The last term is the exact subfilter momentum stress divergence. A scalar Cassi density, a Qi current, or a scale coefficient becomes a force in this equation only after a dimensionful, dynamical constitutive map has been supplied. The distinction between density/current quantities and spatial momentum stress is stated in `foundations/interscale-stress-attenuation-boundary.md` §1; this paper uses the Navier–Stokes $\tau$ without supplying that missing map.

## 2. Exact covariance equation

The covariance equation shows exactly which unresolved objects prevent a closed stress evolution. For each output point $x$, let the filter integration variable be $y$ and hold the center $U_i(x)$ fixed inside that integral:
$$
v_i(x;y)=u_i(y)-U_i(x),
\qquad
Q_{ijk}(x)=\overline{v_i(x;\cdot)v_j(x;\cdot)v_k(x;\cdot)}(x).
$$
Equivalently, this is the algebraic third cumulant
$$
\begin{aligned}
Q_{ijk}={}&\overline{u_i u_j u_k}
-U_i\overline{u_j u_k}
-U_j\overline{u_i u_k}
-U_k\overline{u_i u_j}\\
&+2U_iU_jU_k.
\end{aligned}
$$
This fixed-$x$ central moment convention is required because a Gaussian filter is not idempotent: replacing the center inside the integral by $U_i(y)$ would define a different object and would not give the displayed third-moment expansion.
Define also
$$
 c_{ij}=\tau(u_i,\partial_jp)+\tau(u_j,\partial_ip),
\qquad
 D_{ij}=\sum_{k=1}^3\tau(\partial_ku_i,\partial_ku_j),
$$
where $\tau(f,g)=\overline{fg}-\bar f\,\bar g$. In particular,
$$
 c_{ij}=\overline{u_i\partial_jp}+\overline{u_j\partial_ip}
-U_i\partial_j\bar p-U_j\partial_i\bar p.
$$

The filtered second moment obeys
$$
\partial_t\overline{u_i u_j}
=-\partial_k\overline{u_i u_j u_k}
-\overline{u_i\partial_jp+u_j\partial_ip}
+\nu\Delta\overline{u_i u_j}-2\nu\overline{\partial_ku_i\,\partial_ku_j}.
$$
Expand the third moment as
$$
\overline{u_i u_j u_k}
=U_iU_jU_k+U_i\tau_{jk}+U_j\tau_{ik}+U_k\tau_{ij}+Q_{ijk}.
$$
Subtract the equation for $U_iU_j$, use the filtered momentum equation, and collect the terms containing derivatives of $U$. The exact result is
$$
\boxed{
(\bar D_t-\nu\Delta)\tau_{ij}
=-A_{ik}\tau_{kj}-\tau_{ik}A_{jk}
-\partial_kQ_{ijk}-c_{ij}-2\nu D_{ij}.
}
$$
In matrix notation,
$$
\boxed{
(\bar D_t-\nu\Delta)\tau
=-A\tau-\tau A^{\mathsf T}-\operatorname{div}Q-c-2\nu D.
}
$$
Here $(\operatorname{div}Q)_{ij}=\partial_kQ_{ijk}$. The first two terms are production by the resolved velocity gradient, $Q$ is transport by the unresolved triple correlation, $c$ is pressure transport/strain covariance, and $D$ is the positive semidefinite gradient covariance. The $-2\nu D$ sign follows from
$$
\Delta(U_iU_j)=U_i\Delta U_j+U_j\Delta U_i+2\partial_kU_i\partial_kU_j
$$
and the corresponding identity for $\overline{u_i u_j}$. Dropping $D$, $c$, or $Q$ is a modeling choice rather than an identity.

The pressure covariance can be split into a transport part and a pressure-strain part. Since the filter commutes with derivatives,
$$
\tau(u_i,\partial_jp)
=\partial_j\tau(u_i,p)-\tau(\partial_ju_i,p),
$$
and therefore
$$
\boxed{
 c_{ij}=\partial_j\tau(u_i,p)+\partial_i\tau(u_j,p)
-\tau(\partial_ju_i,p)-\tau(\partial_iu_j,p).
}
$$
This rearrangement changes the bookkeeping only. It does not remove the unresolved pressure correlations.

## 3. Exact strain and signed-transfer equations

Differentiating filtered momentum gives the strain dynamics, including the stress-divergence Hessian. Let
$$
H_{ij}=\partial_i\partial_j\bar p,
\qquad
E_{ij}=\frac12\left(\partial_j\partial_k\tau_{ik}
+\partial_i\partial_k\tau_{jk}\right),
$$
so $E=\operatorname{sym}\nabla\operatorname{div}\tau$. Differentiating with respect to $x_j$ and commuting derivatives yields
$$
\bar D_tA_{ij}+A_{ik}A_{kj}
=-H_{ij}+\nu\Delta A_{ij}-\partial_j\partial_k\tau_{ik}.
$$
Taking the symmetric part gives
$$
\boxed{
(\bar D_t-\nu\Delta)S=-\operatorname{sym}(A^2)-H-E.
}
$$
Because $A=S+\Omega$, the symmetric part satisfies
$$
\operatorname{sym}(A^2)=S^2+\Omega^2,
$$
so an equivalent form is
$$
\boxed{
(\bar D_t-\nu\Delta)S=-(S^2+\Omega^2)-H-E.
}
$$
The pressure Hessian, the second derivatives of the stress divergence, and the antisymmetric-gradient contribution remain present even when $\operatorname{tr}S=0$.

Define the signed filtered transfer
$$
\Pi_\ell=-S_\ell:\tau_\ell=-S_{ij}\tau_{ij}.
$$
Since $\operatorname{tr}S=0$, $S:\tau=S:\tau_{\mathrm{dev}}$. Apply the product Laplacian rule to $S:\tau$:
$$
\Delta(S:\tau)=(\Delta S):\tau+S:(\Delta\tau)
+2\partial_kS_{ij}\,\partial_k\tau_{ij}.
$$
The exact transfer equation is consequently
$$
\boxed{
\begin{aligned}
(\bar D_t-\nu\Delta)\Pi_\ell={}&
\bigl(\operatorname{sym}(A^2)+H+E\bigr):\tau\\
&+S:\bigl(A\tau+\tau A^{\mathsf T}+\operatorname{div}Q+c+2\nu D\bigr)\\
&+2\nu\,\partial_kS_{ij}\,\partial_k\tau_{ij}.
\end{aligned}
}
$$
Equivalently, the material derivative itself is
$$
\boxed{
\bar D_t\Pi_\ell=\nu\Delta\Pi_\ell
+\bigl(\operatorname{sym}(A^2)+H+E\bigr):\tau
+S:\bigl(A\tau+\tau A^{\mathsf T}+\operatorname{div}Q+c+2\nu D\bigr)
+2\nu\,\partial_kS_{ij}\,\partial_k\tau_{ij}.
}
$$
The last displayed contraction is the cross-diffusion term. It has a plus sign in the equation for $\Pi=-S:\tau$ because the product rule contributes $-2\nu\,\partial_kS:\partial_k\tau$ to $(\bar D_t-\nu\Delta)(S:\tau)$ and $\Pi$ carries the additional minus sign. Any transfer evolution retaining only $\Delta S:\tau$ and $S:\Delta\tau$ is incomplete.

## 4. Stress anisotropy and a conditional all-scale estimate

The geometry gives an upper bound on signed transfer, while closure of $\mathcal C$ requires a separate all-scale estimate. Write
$$
\tau_{\mathrm{dev}}=\tau-\frac13(\operatorname{tr}\tau)I,
\qquad
R_\ell=
\begin{cases}
\|\tau_{\ell,\mathrm{dev}}\|_F/\operatorname{tr}\tau_\ell,&\operatorname{tr}\tau_\ell>0,\\
0,&\operatorname{tr}\tau_\ell=0.
\end{cases}
$$
The zero-trace case has $\tau_\ell=0$ because $\tau_\ell$ is positive semidefinite. Thus the convention $R_\ell=0$ is compatible with the covariance geometry. For the Frobenius and operator norms,
$$
\boxed{
|\Pi_\ell|\le \|S_\ell\|_{\mathrm{op}}\operatorname{tr}\tau_\ell,
}
$$
and
$$
\boxed{
|\Pi_\ell|
=|S_\ell:\tau_{\ell,\mathrm{dev}}|
\le \|S_\ell\|_F R_\ell\operatorname{tr}\tau_\ell.
}
$$
The first inequality uses $\tau\succeq0$; the second uses Cauchy–Schwarz and $\operatorname{tr}S=0$. The positive all-scale covariance identity below supplies the concentration norm, while these inequalities bound its production rate.

For the Gaussian filter, Parseval and the normalized spatial mean give the exact identity
$$
\mathcal C(t):=\|u(t)\|_{\dot H^{1/2}}^2
=\sum_{k\ne0}|k|\,|u_k(t)|^2
=\frac1{\sqrt\pi}\int_0^\infty
\ell^{-2}\langle\operatorname{tr}\tau_\ell\rangle\,d\ell.
$$
The associated higher quantity is $Y=\sum_{k\ne0}|k|^3|u_k|^2$. The transfer convention used in the Navier–Stokes audit is
$$
\mathcal C'+2\nu Y=2F,
\qquad F=\langle\Lambda u,B(u,u)\rangle,
$$
with the equivalent cascade notation $F=\int_0^\infty\Pi(K)\,dK$ when a transfer density $\Pi(K)$ has been defined.

For the Gaussian transfer convention used here, the all-scale signed transfer has the exact representation
$$
F(t)=\frac1{\sqrt\pi}\int_0^\infty
\ell^{-2}\langle\Pi_\ell(t)\rangle\,d\ell,
$$
For the smooth fields considered here, this integral converges in the stated Gaussian convention. The data-controlled geometric envelope
$$
G(t):=\operatorname*{ess\,sup}_{x\in\mathbb T^3,\,\ell>0}
\|S_\ell(x,t)\|_F R_\ell(x,t)
$$
is assumed to belong to $L^1(0,T)$.

Then
$$
|F(t)|
\le \frac1{\sqrt\pi}\int_0^\infty\ell^{-2}
\langle|\Pi_\ell|\rangle\,d\ell
\le G(t)\mathcal C(t),
$$
where the first inequality is the exact all-scale representation and the second uses the boxed geometric estimate. Retaining the dissipative term in the balance gives
$$
\mathcal C'(t)+2\nu Y(t)\le2G(t)\mathcal C(t).
$$
Gronwall therefore yields
$$
\boxed{
\mathcal C(t)\le \mathcal C(0)\exp\!\left(2\int_0^tG(s)\,ds\right)
}
$$
and, by integrating the differential inequality with this bound,
$$
\mathcal C(t)+2\nu\int_0^tY(s)\,ds
\le \mathcal C(0)\exp\!\left(2\int_0^tG(s)\,ds\right).
$$
More directly, the integrating-factor form is
$$
e^{-2\int_0^tG(s)\,ds}\mathcal C(t)
+2\nu\int_0^t e^{-2\int_0^sG(r)\,dr}Y(s)\,ds\le \mathcal C(0).
$$
On the mean-zero torus, Sobolev and Fourier interpolation give
$$
\|u(t)\|_{L^6}^4\le C_{\mathbb T^3}\,\mathcal C(t)Y(t).
$$
Thus the estimate supplies $u\in L^4(0,T;L^6)$ whenever the right-hand side is finite, the standard Serrin continuation class. The integrability of $G$ is a stronger conditional bound imposed on the filtered data; it is not proved by these identities and introduces no independent dynamics or new regularity theorem. The unresolved $Q$, pressure covariance, and dissipative gradient covariance remain in the exact transfer dynamics.

A less restrictive sufficient target would allow viscosity to absorb part of the signed transfer:
$$
\boxed{F(t)\le\theta\nu Y(t)+a(t)\mathcal C(t),
\qquad 0\le\theta<1,\qquad a\ge0,\quad a\in L^1(0,T).}
$$
Here $\theta$ is a specified mathematical absorption fraction, and the time integral of $a$ must be bounded in terms of the initial datum, viscosity, and $T$. This gives the same continuation argument with $2(1-\theta)\nu Y$ in the dissipative budget. The anisotropy envelope supplies the special conditional case $\theta=0$, $a=G$. Deriving either bound from the original stress, strain, and pressure dynamics for arbitrary data is the unresolved estimate.

## 5. Helical tangent dyads and affine straightening

The helical calculation is an axisymmetric covariance model whose relation to an actual filter must be declared separately. Let an axial coordinate be $z$, transverse basis vectors be $e_1,e_2$, and let a helix have radius $a$ and wave number $k$. Its dimensionless tangent at phase $\theta$ has the form
$$
q_\pm(\theta)=\pm s\bigl(-\sin\theta\,e_1+\cos\theta\,e_2\bigr)+e_3,
\qquad s=ak.
$$
Both strands have the same handedness, with a half-turn phase separation:
$$
q_+(\theta)=s\bigl(-\sin\theta\,e_1+\cos\theta\,e_2\bigr)+e_3,
\qquad
q_-(\theta)=q_+(\theta+\pi)
=-s\bigl(-\sin\theta\,e_1+\cos\theta\,e_2\bigr)+e_3.
$$
Equal speed means normalization by the common factor $(1+s^2)^{-1/2}$. Uniform phase sampling gives
$$
\left\langle\frac{q_\pm\otimes q_\pm}{1+s^2}\right\rangle_\theta
=\operatorname{diag}\!\left(\frac{s^2}{2(1+s^2)},
\frac{s^2}{2(1+s^2)},\frac1{1+s^2}\right).
$$
The stress interpretation requires zero-mean counterflow/signed fluctuations in addition to uniform phase sampling: use equal populations of $\xi=\pm q_\pm/\sqrt{1+s^2}$, so $\langle\xi\rangle=0$ while the dyad above is unchanged. A coflow ensemble with both axial components positive has a nonzero axial mean; centering that coflow subtracts the axial dyad and removes the displayed axial covariance eigenvalue. Gaussian filtering of a deterministic Navier–Stokes field supplies neither this signed ensemble nor its uniform phase sampling automatically.

With unit trace, the transverse and axial eigenvalues are
$$
\lambda_\perp=\frac{s^2}{2(1+s^2)},
\qquad
\lambda_\parallel=\frac1{1+s^2}.
$$
The deviatoric eigenvalues are
$$
\lambda_\perp-\frac13=\frac{s^2-2}{6(1+s^2)},
\qquad
\lambda_\parallel-\frac13=\frac{2-s^2}{3(1+s^2)}.
$$
Therefore
$$
\boxed{
R_\ell=\|\tau_{\mathrm{dev}}\|_F
=\frac{|2-s^2|}{\sqrt6(1+s^2)}.
}
$$
At $s=\sqrt2$, all three eigenvalues equal $1/3$ and the modeled stress is isotropic. The ratio tends to $\sqrt{2/3}$ as $s\to0$ and to $1/\sqrt6$ as $s\to\infty$.

A volume-preserving affine deformation supplies the relevant local strain coefficient and its straightening scale. Take
$$
X(t)=e^{-\sigma t/2}X_0,\qquad
Y(t)=e^{-\sigma t/2}Y_0,\qquad
Z(t)=e^{\sigma t}Z_0,
$$
so the affine velocity and strain are
$$
U_{\mathrm{aff}}=(-\tfrac{\sigma}{2}X,-\tfrac{\sigma}{2}Y,\sigma Z),
\qquad
S_{\mathrm{aff}}=\operatorname{diag}(-\tfrac{\sigma}{2},-\tfrac{\sigma}{2},\sigma),
\qquad \operatorname{tr}S_{\mathrm{aff}}=0.
$$
Applied to a helix parametrized by $(a\cos kz,a\sin kz,z)$, this deformation gives
$$
a(t)=a_0e^{-\sigma t/2},\qquad
k(t)=k_0e^{-\sigma t},\qquad
s(t)=a(t)k(t)=s_0e^{-3\sigma t/2}.
$$
Contracting the unit-trace axisymmetric tangent-dyad stress $M(s)$ with the affine strain gives
$$
\boxed{
\alpha(s):=S_{\mathrm{aff}}:M(s)
=\sigma\,\frac{1-s^2/2}{1+s^2}.
}
$$
For the supplied zero-mean tangent covariance with trace $U^2$, the modeled transfer is $\Pi_{\mathrm{model}}=-U^2\alpha$. Thus compression along a tangent ($\alpha<0$) and positive modeled stress transfer occur together. Vortex-stretching suppression and critical-energy-transfer suppression are distinct conditions in this construction. Both signs reverse at $s=\sqrt2$, which the prescribed deformation reaches at
$$
t_{\mathrm{cross}}=\frac{2}{3\sigma}\log\left(\frac{s_0}{\sqrt2}\right);
\qquad
s_0=2,\ \sigma=1\Longrightarrow t_{\mathrm{cross}}=\frac{\log2}{3}.
$$
This is an affine kinematic control and local tangent-dyad calculation. The globally affine velocity lies outside the periodic and finite-energy Euclidean data classes. The supplied tangent ensemble is a separate covariance assumption; it is not the Gaussian covariance generated by that affine velocity.

## 6. Strain freedom at fixed local vorticity

Vorticity at a point fixes the antisymmetric part of the velocity gradient, while incompressibility fixes only the trace of its symmetric part. This leaves arbitrary symmetric trace-free strain directions available in the local jet. Let $x_0$ be a point and let $B=B^{\mathsf T}$ be any symmetric trace-free $3\times3$ matrix. Put $r=x-x_0$ and choose a smooth compactly supported cutoff $\chi$ that equals one on a neighborhood of $x_0$. Define the vector potential
$$
 a(x)=\frac13\chi(x)\,(Br)\times r,
\qquad
 w=\nabla\times a.
$$
Then $w$ is smooth, compactly supported, and divergence-free. In the neighborhood where $\chi=1$, the linear identity
$$
\nabla\times\left[\frac13(Br)\times r\right]=Br
$$
holds because $\operatorname{tr}B=0$. Consequently,
$$
 w(x_0)=0,
\qquad
\nabla w(x_0)=B,
\qquad
\operatorname{sym}\nabla w(x_0)=B.
$$
Moreover, the vorticity perturbation at $x_0$ vanishes:
$$
(\nabla\times w)(x_0)=0,
$$
because the curl of the linear field $Br$ is zero for symmetric $B$. Thus $u$ and $u+w$ have the same velocity and vorticity at $x_0$, while their symmetric velocity gradients differ by the arbitrary prescribed $B$. On a periodic domain the same construction fits inside a coordinate ball and extends periodically.

This jet-level freedom is an obstruction to any pointwise rule that infers arbitrary strain geometry from local vorticity alone. It also clarifies the scope of the helical stress ansatz: a local vorticity direction or a local helical label cannot select the full symmetric strain tensor without additional nonlocal information. A compact perturbation generally changes filtered fields at nearby points, so the construction does not assert invariance of $\tau_\ell$ under filtering.

## 7. An admissible initial field and the isotropy-preservation test

A concrete smooth periodic datum tests local isotropy without invoking a turbulence ensemble. Take
$$
 u(x,y,z)=(\sin y,\sin z,\sin x),
 \qquad p(0,x)=\text{constant}.
$$
It is mean-zero and divergence-free. Its gradient at the origin is
$$
A^{(0)}(0)=
\begin{pmatrix}
0&1&0\\
0&0&1\\
1&0&0
\end{pmatrix},
$$
while the filtered gradient is $A_\ell(0)=gA^{(0)}(0)$ with
$$
 g=e^{-\ell^2/2}.
$$
The constant pressure is compatible with the pressure Poisson equation for this datum because $\operatorname{tr}((A^{(0)})^2)=0$ pointwise. At the origin, the filtered velocity vanishes. Since each squared sine has Fourier wave number $2$,
$$
T=\frac{1-e^{-2\ell^2}}2,
\qquad
\tau_\ell(0)=T I.
$$
Therefore
$$
\boxed{\Pi_\ell(0,0)=-S_\ell(0):\tau_\ell(0)=0.}
$$

The remaining terms in the covariance equation can be evaluated by parity and the displayed Fourier modes. At the origin, $c=0$ because $p$ is constant; the gradient covariance and Laplacian covariance are
$$
D_\ell(0)=\left(\frac{1+g^4}{2}-g^2\right)I,
\qquad
\Delta\tau_\ell(0)=-2(g^2-g^4)I.
$$
The same parity calculation gives $\operatorname{div}Q_\ell(0)=0$. With $T=(1-g^4)/2$, the isotropic viscous contribution is
$$
\nu\Delta\tau_\ell-2\nu D_\ell=-2\nu T I.
$$
Therefore the full covariance derivative at the origin is
$$
\boxed{\tau_{\ell,t}(0,0)=-2T S_\ell(0)-2\nu T I,}
$$
and its anisotropic part is
$$
\boxed{\tau_{\ell,t}^{\mathrm{dev}}(0,0)=-2T S_\ell(0).}
$$
Since $\tau_\ell=T I$ initially, the contraction with $S_{\ell,t}$ vanishes by $\operatorname{tr}S_{\ell,t}=0$. Consequently,
$$
\Pi_{\ell,t}(0,0)
=-S_\ell(0):\tau_{\ell,t}(0,0)
=2T\,S_\ell(0):S_\ell(0).
$$
The matrix $S^{(0)}$ has six off-diagonal entries equal to $1/2$, hence $S^{(0)}:S^{(0)}=3/2$. It follows that
$$
\boxed{\Pi_{\ell,t}(0,0)=3Tg^2>0\qquad(\ell>0).}
$$
The covariance is isotropic at the origin at the initial instant, and this one-point isotropy is immediately lost under the Navier–Stokes evolution for this datum. The assertion that pointwise isotropy alone persists and suppresses subsequent local transfer receives **CONTRADICTS** for this control. Conditions involving spatial averaging, nonlocal Biot–Savart geometry, a time integral, or a separately imposed phase ensemble require separate analysis.

### 7.1 Fixed numerical controls

Independent Fourier quadrature of the raw velocity and its full instantaneous Navier–Stokes derivative reproduces the covariance calculation on all nine combinations of $N\in\{16,32,64\}$ and $\ell\in\{1/2,1,2\}$ at $\nu=1$. The largest checked discrepancy is $1.721\times10^{-15}$, below the frozen $10^{-10}$ tolerance.

| Filter width $\ell$ | $\partial_t\Pi_\ell(0,0)$ at $N=64$ |
|---|---|
| $1/2$ | $0.4596513454955868$ |
| $1$ | $0.4771385592053693$ |
| $2$ | $0.0274642420145713$ |

The smallest derivative over all nine combinations is $0.02746424201457126$. All 37 symbolic and numerical checks pass. Under the prescribed affine deformation in §5, $s_0=2$ and $\sigma=1$ give $\alpha(0)=-1/5$, $\alpha(1)=(e^3-2)/(e^3+4)>0$, and crossing time $\log2/3$. Protection from the supplied helix shape alone receives **CONTRADICTS** under this deformation.

The Euclidean rescaling $u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t)$ gives $\tau_\ell[u_\lambda](x)=\lambda^2\tau_{\lambda\ell}[u](\lambda x)$, $S_\ell[u_\lambda](x)=\lambda^2S_{\lambda\ell}[u](\lambda x)$, and $\Pi_\ell[u_\lambda](x)=\lambda^4\Pi_{\lambda\ell}[u](\lambda x)$. Spatial integration and the change of filter variable leave $\mathcal C$ invariant. These scaling identities and the finite quadrature comparisons establish normalization and resolved-mode accuracy. No flow-time integration or continuum regularity experiment is included.

Run `python computations/verify_navier_stokes_stress_geometry.py` from the CassiTheory directory. Its raw receipt is `runs/navier_stokes_stress_geometry/verification.json`; use `--output` with a fresh path to retain an additional receipt. The accepted script SHA-256 is `01685b5c68bf72e7db752536f179abbfb390d9b3d5309500cdd4683552649d84`; the frozen protocol SHA-256 is `0c56f063a75a13b1b9e497963f694b1138ea1a3641f1a854c167ce8c472eaf62`. The receipt retains the matrices, term splits, residuals, and control classifications.

## 8. Relation to Cassi foundations and primary literature

The Cassi foundations distinguish density-plane diagnostics and optional helical lifts from a physical spatial momentum flux. `foundations/qi-flow-double-helix.md` §3 labels compact phase, pitch, and double-helix embedding as additional Hypothesized structure; its canonical real-density equations do not contain the tangent ensemble used in §5. `foundations/interscale-stress-attenuation-boundary.md` §1 likewise requires a dimensionally explicit map from an interscale current to a mixed spatial stress. That current-to-$T_{i\mathfrak s}$ map, and hence any Cassi-to-Navier–Stokes constitutive map, remains unselected here.

The parent audit is `turbulence/navier-stokes-transfer-boundary.md`; the governing protocol is `computations/navier_stokes_stress_geometry_prereg.md`, with the transfer and stress-geometry checks specified in `computations/verify_navier_stokes_transfer.py` and `computations/verify_navier_stokes_stress_geometry.py`.

The exact filtered identities sit in the established large-eddy-simulation literature. Germano's primary paper derives averaging-invariant filtered Navier–Stokes equations in generalized central moments and the algebraic relation between stresses at filter levels, the basis of the Germano identity. Eyink and Aluie, arXiv:0909.2386, derive smooth coarse-grained space/scale budgets and rigorous locality bounds under inertial-range scaling assumptions. Their results support exact scale decompositions and locality estimates for the declared turbulent setting; they do not turn a pointwise geometric envelope into an arbitrary-data regularity theorem.

Constantin and Fefferman's primary conditional criterion states that spatial coherence of the vorticity direction on the high-vorticity region, in a Lipschitz-type form such as
$$
|\sin\angle(\omega(x,t),\omega(y,t))|
\le \frac{|x-y|}{\rho},
$$
precludes a singularity while the condition holds. This is a vorticity-direction condition controlling vortex stretching. It is distinct from the stress-anisotropy envelope $\|S_\ell\|_F R_\ell\in L^1_tL^\infty_{x,\ell}$ proposed here. Both are conditional geometric regularity statements; neither supplies an unconditional proof for every smooth datum.

Buaria, Pumir, and Bodenschatz (Nature Communications 11, article 5852, 2020, DOI `10.1038/s41467-020-19530-1`) use highly resolved turbulent data and a Biot–Savart decomposition to report local strain self-attenuation at extreme vorticity, connected to local Beltramization. This is a measured turbulence-statistics mechanism in a specified numerical regime. It is valuable motivation for adversarial stress geometry, while the present paper treats arbitrary smooth initial data algebraically and makes no statistical extrapolation.

## 9. Present boundary and conclusions

The exact filtered equations retain the third moment, pressure correlations, gradient covariance, pressure Hessian, stress derivatives, and product cross-diffusion. They supply an exact all-scale concentration budget and a conditional anisotropy estimate. A data-controlled bound on its time integral remains open. The helical covariance model requires uniform phase sampling and zero-mean signed tangent fluctuations, and its deformation depends on the surrounding strain.

The field $u_0=(\sin y,\sin z,\sin x)$ has isotropic filtered covariance and zero instantaneous transfer at the origin, with a strictly positive transfer derivative there. The compact curl-potential construction independently shows that local vorticity does not determine symmetric strain. Together these facts require any proposed geometric condition to state its nonlocal, ensemble, time, and filtering assumptions explicitly.

No Millennium-problem solution, unconditional global regularity theorem, or physical Cassi-to-Navier–Stokes stress identification follows from these derivations.

## References

- `foundations/qi-flow-double-helix.md` §3—canonical density-plane mathematics and conditional compact-phase/double-helix structure
- `foundations/interscale-stress-attenuation-boundary.md` §1—spatial momentum stress boundary and missing current-to-stress map
- `turbulence/navier-stokes-transfer-boundary.md`—parent transfer and heat-corrector audit
- `computations/navier_stokes_stress_geometry_prereg.md`—stress-geometry protocol
- `computations/verify_navier_stokes_transfer.py`—transfer checks
- `computations/verify_navier_stokes_stress_geometry.py`—stress-geometry checks
- M. Germano, “Turbulence: the filtering approach,” *Journal of Fluid Mechanics* **238** (1992), 325–336, DOI `10.1017/S0022112092001733`; primary record: https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/abs/turbulence-the-filtering-approach/1B92D8CFAEEB0D6B4ADA6BB31282D378
- G. L. Eyink and H. Aluie, [Localness of energy cascade in hydrodynamic turbulence. I. Smooth coarse-graining](https://arxiv.org/abs/0909.2386), *Physics of Fluids* **21**, 115107 (2009)—filtered energy budgets and conditional scale locality.
- D. Buaria, A. Pumir, and E. Bodenschatz, “Self-attenuation of extreme events in Navier–Stokes turbulence,” *Nature Communications* **11** (2020), article 5852, DOI `10.1038/s41467-020-19530-1`, https://www.nature.com/articles/s41467-020-19530-1
- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789, DOI `10.1512/iumj.1993.42.42034`
- P. Constantin, [Near identity transformations for the Navier–Stokes equations](https://web.math.princeton.edu/~const/niD.pdf), §§4–5—conditional continuation estimates and geometric depletion.
