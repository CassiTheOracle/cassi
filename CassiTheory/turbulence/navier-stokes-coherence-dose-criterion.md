# A Coherence-Dose Continuation Criterion for Periodic Navier–Stokes

## Status: Derived conditional—September 2026

## Abstract

This note extracts a continuation criterion from the positive-minus-positive replica identity in `turbulence/navier-stokes-replica-coherence.md` §5. The identity separates deformation-amplified seeded occupation from the retarded covariance spread created by viscosity. A uniform bound on the accumulated positive active seeded rate gives a uniform enstrophy bound and therefore continuation through every finite time. An independently proved lower bound on the retarded spread gives a second, compensated route to the same conclusion. Periodic shear, the rank-two Beltrami control, the full-rank ABC heat flow, and a homogeneous extensional control separate the finite-horizon criterion from the unresolved initial-data estimate.

## 1. Setup

Let $u$ be a smooth mean-zero divergence-free solution of the unforced periodic three-dimensional Navier–Stokes equation on the interval before its first possible singular time $T_*$. Use the vorticity, enstrophy, seeded occupation, and replica disagreement from `turbulence/navier-stokes-replica-coherence.md`:

$$
W(t)=\int_{\mathbb T^3}|\omega|^2dx,
\qquad
\mathcal E_M(t)=\int_{\mathbb T^3}\operatorname{tr}M\,dx,
\qquad
\mathcal V(t)=\int_{\mathbb T^3}\operatorname{tr}R\,dx.
$$

The covariance is positive semidefinite, so $\mathcal V(t)\ge0$, and the exact decomposition is

$$
\mathcal E_M(t)=W(t)+\mathcal V(t).
$$

Write

$$
\Gamma_M(t)=
\frac{\int_{\mathbb T^3}S:M\,dx}{\mathcal E_M(t)},
\qquad
G(t)=\int_0^t\Gamma_M(s)\,ds,
\qquad
G_+(t)=\int_0^t(\Gamma_M(s))_+\,ds.
$$

For nonzero data, $\mathcal E_M(0)=W(0)>0$ and the occupation equation gives

$$
\mathcal E_M(t)=W(0)e^{2G(t)}.
$$

The zero datum is the stationary zero solution and is handled separately.

## 2. Active-dose continuation criterion

The positive-minus-positive identity gives an immediate conditional continuation route.

**Proposition 1.** Suppose that, for a fixed $T>0$ and $R_0<\infty$, there is a constant $C_\Gamma(\nu,T,R_0)$ such that every smooth periodic datum with $\|u_0\|_{H^3}\le R_0$ satisfies

$$
\sup_{0\le t<\min(T,T_*)}G_+(t)
\le C_\Gamma(\nu,T,R_0).
\tag{CC1}
$$

Then every such solution continues through time $T$.

**Proof.** The retarded occupation formula is

$$
\mathcal V(t)=2\nu\int_0^tD(s)
\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}\,dr\right)ds\ge0.
\tag{CC2}
$$

Combining it with the exact seeded-occupation identity gives

$$
\begin{aligned}
W(t)
&=W(0)e^{2G(t)}-\mathcal V(t)\\
&\le W(0)e^{2G(t)}\\
&\le W(0)e^{2G_+(t)}.
\end{aligned}
\tag{CC3}
$$

On the normalized torus, $W(0)=\|\nabla\times u_0\|_2^2\le\|u_0\|_{H^3}^2\le R_0^2$. Thus (CC1) and (CC3) give

$$
\sup_{0\le t<\min(T,T_*)}W(t)
\le R_0^2e^{2C_\Gamma(\nu,T,R_0)}<\infty.
\tag{CC4}
$$

The periodic Fourier curl identity and the kinetic-energy estimate then place $u$ in $L^4_tL^6_x$ with a finite norm. The periodic Prodi–Serrin continuation bridge extends the solution through $T$. $\square$

An absolute-dose hypothesis

$$
\sup_{\|u_0\|_{H^3}\le R_0}
\int_0^{\min(T,T_*)}|\Gamma_M(t)|\,dt<\infty
\tag{CC5}
$$

implies (CC1). A summable positive-dose bound on any finite partition of the time interval is the same sufficient control: the sum of the window doses is $G_+(T)$.

## 3. Retarded-spread compensation route

The same identity isolates the exact cancellation needed when the seeded occupation grows. Define

$$
A_M(t)=W(0)e^{2G(t)}.
$$

An independently proved uniform bound of the form

$$
\mathcal V(t)\ge A_M(t)-C_{\mathrm{ret}}(\nu,T,R_0)
\quad\text{for every }t<\min(T,T_*)
\tag{CC6}
$$

implies

$$
W(t)=A_M(t)-\mathcal V(t)\le C_{\mathrm{ret}}(\nu,T,R_0).
\tag{CC7}
$$

Proposition 1 again gives continuation. Condition (CC6) is a lower bound on a positive retarded integral relative to the entire seeded occupation. It is a precise formulation of the required compensation; its uniform derivation from initial-data control remains open.

There is a general pointwise rate bound. Since $M\succeq0$ and $S$ is symmetric,

$$
\Gamma_M(t)
=\frac{\int S:M\,dx}{\mathcal E_M(t)}
\le\|S(t)\|_{L^\infty(\mathbb T^3;\operatorname{op})}.
\tag{CC8}
$$

Consequently,

$$
G_+(t)\le\int_0^t\|S(s)\|_{L^\infty(\mathbb T^3;\operatorname{op})}\,ds.
\tag{CC9}
$$

This recovers a standard continuation-level estimate. It supplies a finite bound on every already-smooth compact interval, while a bound uniform over an arbitrary initial-data ball is the unresolved step.

## 4. Exact controls

The controls test the two terms in (CC3) separately.

### 4.1 Periodic shear

For

$$
u_n(y,t)=e^{-\nu n^2t}\sin(ny)e_1,
\qquad
\omega_n(y,t)=-n e^{-\nu n^2t}\cos(ny)e_3,
$$

rank-one source geometry gives $J=0$ and the exact replica budget is

$$
\mathcal E_M(t)=W(0),
\qquad
\mathcal V(t)=W(0)(1-e^{-2\nu n^2t}),
\qquad
W(t)=W(0)e^{-2\nu n^2t}.
$$

Thus $\Gamma_M=0$, $G_+=0$, and the active-dose criterion gives the exact bound $W(t)\le W(0)$. The retarded spread accounts for the entire decay even though the full-rank determinant functional vanishes.

### 4.2 Periodic rank-two Beltrami control

For the exact periodic field

$$
v=(\cos y,\ \sin x,\ \sin y+\cos x),
\qquad
u=e^{-\nu t}v,
$$

one has $\nabla\cdot v=0$, $\nabla\times v=v$, $\Delta v=-v$, and

$$
(v\cdot\nabla)v=\nabla\frac{|v|^2}{2}.
$$

It is a smooth unforced Navier–Stokes solution. The source Gram in the
replica identity is built from
$J=\nabla\omega=\nabla(\nabla\times v)$, with rows indexed by vorticity
components and columns by coordinate derivatives. Because this control has
$\nabla\times v=v$, the source gradient equals $\nabla v$. Therefore

$$
\nabla\omega(0)=\nabla(\nabla\times v)(0)=
\begin{pmatrix}
0&0&0\\
1&0&0\\
0&1&0
\end{pmatrix},
\qquad
Q_0=(\nabla\omega(0))(\nabla\omega(0))^{\mathsf T}
=\operatorname{diag}(0,1,1).
$$

The verifier computes this same $J=\nabla\omega$ and $Q=JJ^{\mathsf T}$
row/column convention. The source has rank at most two and $J=0$ at every
time, while the accumulated covariance becomes positive definite on an open
set for sufficiently small positive time. The rate bound (CC8) gives a finite
active dose on every compact smooth interval, so Proposition 1 applies to
this exact control without relying on a positive instantaneous determinant
source.

### 4.3 Full-rank ABC heat flow

For

$$
u_{\mathrm{ABC}}(x,y,z,t)=e^{-\nu t}
(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x),
$$

one has $\nabla\times u_{\rm ABC}=u_{\rm ABC}$ and $\Delta u_{\rm ABC}=-u_{\rm ABC}$. The flow is globally smooth and

$$
J(t)=e^{-2\nu t}J(0),
\qquad J(0)>0.
$$

Because $S(t)=e^{-\nu t}S(0)$, (CC8) gives the explicit finite dose estimate

$$
G_+(T)\le
\|S(0)\|_{L^\infty(\operatorname{op})}
\frac{1-e^{-\nu T}}{\nu}.
$$

The active-dose route therefore passes a full-rank three-dimensional periodic control. It remains a control-specific estimate and supplies no uniform bound over arbitrary data.

### 4.4 Homogeneous extensional control

For the volume-preserving deformation

$$
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1),
\qquad Y_0=e_1,
$$

all replicas coincide:

$$
\mathcal V(t)=0,
\qquad
\mathcal E_M(t)=W(t)=e^{2at}W(0),
\qquad
\Gamma_M=a.
$$

For a finite horizon, $G_+(T)=aT$ when $a\ge0$, and (CC3) is exact. Over an unbounded horizon the dose is not summable for $a>0$. This affine control is outside the periodic finite-energy Navier–Stokes class and marks the boundary of the algebraic criterion.

## 5. Evidence boundary

The criterion in Proposition 1 is an exact conditional consequence of the replica occupation identity and the periodic Prodi–Serrin bridge. The retarded-spread route records the compensation estimate required to replace active-dose control. The operator-norm estimate (CC8) shows why the criterion alone does not yield arbitrary-data regularity: it reduces the rate to the time integral of the spatial strain norm, whose uniform initial-data-ball bound is unavailable.

The exact controls support the scope of the criterion. Periodic shear shows that rank-deficient data can satisfy the criterion through viscous spread alone. The rank-two Beltrami flow shows that accumulated covariance recovery can coexist with $J=0$. ABC shows the criterion alongside nonzero full-rank recovery. The affine control shows finite-horizon validity with no retarded spread and the absence of an infinite-horizon summability conclusion.

A uniform bound on $G_+$, a uniform estimate of the form (CC6), and arbitrary-data global regularity remain open.

## References

- `turbulence/navier-stokes-replica-coherence.md`—independent replicas, retarded covariance occupation, and the periodic continuation bridge
- `computations/navier-stokes-coherence-dose-continuation-prereg.md`—fixed scope and verification schedule for this criterion
- `computations/verify_navier_stokes_coherence_dose.py`—exact symbolic and control verifier
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic Cauchy representation
- J. Serrin, [On the interior regularity of weak solutions of Navier–Stokes equations](https://link.springer.com/article/10.1007/BF00253344)—velocity Prodi–Serrin continuation criterion
