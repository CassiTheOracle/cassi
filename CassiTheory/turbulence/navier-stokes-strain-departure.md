# Strain Departure and Critical Spectral Concentration

## Status: Derived conditional estimates, helical reduction and cumulative mixing obstruction / Open arbitrary-data critical work—September 2026

## Abstract

The original unforced Navier–Stokes equation imposes a finite energy budget
on persistent strain self-amplification. Retaining a standard interpolation
inequality gives an explicit departure-or-breakdown deadline that is strictly
earlier than the energy deadline in Miller's perturbative comparison. Known
global regularity converts this alternative into a departure statement for
axisymmetric, swirl-free data. An integrated identity quantifies departure,
and spectral centering bounds both the critical remainder work and the
complete nonlinear transfer. The spectral spread has an exact nonnegative
viscous dissipation and a centered nonlinear production. Finite cumulative
positive spread production gives a Prodi–Serrin continuation criterion, while
the required initial-data-controlled bound remains open. A smooth
monochromatic periodic flow develops positive spread production immediately,
and a positive-moment scalar construction shows the insufficiency of the
listed energy and departure budgets for critical-norm control. With an
external force, exact source terms modify the budgets and the
strain-departure identity. Critical duality controls a smooth source within
the conditional spectral estimate. Parabolic rescaling makes that source
vanish locally, while obtaining a nontrivial unforced limit requires
additional compactness. Arbitrary-data regularity remains open.

An exact periodic mixing family supplies a cumulative obstruction. Its globally smooth solutions preserve odd Cartesian phase symmetry while accumulated excess critical transfer, spread dissipation and positive spread production become arbitrarily large relative to the initial squared critical norm $\mathcal C(0)$. The lower bounds follow from a continuum comparison with controlled parabolic error and the exact spread budget. A separate Fourier cancellation gives a finite nonlinear critical-transfer bound within the same invariant family.

The signed curl spectrum gives a complementary helical spread and the
$L^2$-optimal scalar Beltrami residual
$r_B=\omega-Hu/(2K)$. Finite
$\int\|r_B\|_3^2dt$ controls enstrophy and the cumulative radial-spread
production, but no arbitrary-data bound on that critical integral is known.
A smooth one-band positive-doublet family has bounded first-order phase
energy while its enstrophy and instantaneous $L^3$ residual diverge. Thus
the current phase action does not supply the missing coercivity; a
full-bubble dynamical restriction remains open.

## 1. Equation, data and source boundary

The analytical statements concern the ordinary incompressible velocity equation, with its complete nonlinearity and ordinary viscosity. The numerical approximations in §7 are identified separately. On $\mathbb R^3$,
$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad \nabla\cdot u=0,\qquad \nu>0.
$$
Sections 2–6 and 9 retain this unforced equation; §9 fixes the periodic domain. Section 8 treats the ordinary externally forced equation explicitly; its source terms remain part of every applicable budget.
For the Euclidean statements, use smooth, finite-energy data with enough Sobolev regularity for the displayed quantities; divergence-free Schwartz data suffice. All identities are applied on the smooth lifespan. Euclidean integrals use Lebesgue measure, and periodic statements use the normalized conventions of §6. Let
$$
S=\nabla_{\mathrm{sym}}u,
\quad \omega=\nabla\times u,
\quad \Lambda=(-\Delta)^{1/2},
$$
$$
K=\tfrac12\|u\|_2^2=\|S\|_{\dot H^{-1}}^2,
\qquad E=\|S\|_2^2=\tfrac12\|\omega\|_2^2,
\qquad G=\|S\|_{\dot H^1}^2,
$$
$$
f=-3\nu G-4\int_{\mathbb R^3}\det S\,dx.
$$
The initial comparison assumes $f_0>0$, which also requires $K_0,E_0>0$. Here $K$ is kinetic energy and $E$ is strain enstrophy.

Miller's strain self-amplification model and full-equation comparison supply the starting point. The relevant results are Theorem 6.1, Proposition 6.2, Theorem 6.3, Remark 6.5 and Corollary 6.6 of arXiv:1910.05415. In particular, the existence of axisymmetric, swirl-free solutions that enter and then leave the perturbative condition is established there. The results below sharpen the budget comparison and expose an integrated defect. No claim of literature-wide novelty is assigned to these elementary consequences.

## 2. Remainder and exact budgets

The full-equation remainder changes the strain configuration while doing zero direct work on total strain enstrophy. Let $P_{\mathrm{st}}$ be the $L^2$ orthogonal projection onto strains of divergence-free velocities, and define
$$
\mathcal R=P_{\mathrm{st}}\left((u\cdot\nabla)S+\tfrac13S^2+\tfrac14\omega\otimes\omega\right),
$$
$$
M=-\nu\Delta S+\tfrac23P_{\mathrm{st}}(S^2),
\qquad D=M+\tfrac12\mathcal R.
$$
The original strain equation is
$$
\partial_tS=-M-\mathcal R.
$$
The advection and Betchov identities give
$$
\langle S,\mathcal R\rangle=0,
\qquad
\boxed{E'=f+\nu G,\qquad K'=-2\nu E.}
$$
A Fourier Cauchy–Schwarz inequality supplies the additional coupling:
$$
E=\langle\Lambda^{-1}S,\Lambda S\rangle,
\qquad
\boxed{E^2\le KG.}
$$
These weights follow from the fact that strain already contains one velocity derivative.

The perturbative condition compares the remainder with the midpoint vector $D$. Use its squared defect to avoid dividing by a vanishing norm:
$$
\boxed{\delta=\|\mathcal R\|_2^2-4\|D\|_2^2.}
$$
The condition is $\delta\le0$, equivalently $\|\mathcal R\|_2\le2\|D\|_2$. When $D=0$, it holds only if $\mathcal R=0$. Departure is the well-defined event $\delta>0$.

The defect is exactly the negative derivative of the amplification functional. Since $\operatorname{tr}S=0$,
$$
\int\det S=\tfrac13\int\operatorname{tr}(S^3),
\qquad df[S](H)=-6\langle M,H\rangle
$$
for admissible strain directions $H$. Consequently,
$$
\begin{aligned}
f'&=6\langle M,M+\mathcal R\rangle\\
&=6\|M+\tfrac12\mathcal R\|_2^2-\tfrac32\|\mathcal R\|_2^2\\
&=\boxed{-\tfrac32\delta}.
\end{aligned}
$$
In particular, $\delta\le0$ preserves $f\ge f_0$ on any interval starting at the specified initial time. This identity concerns the complete projected remainder. It assigns no separate sign to its advection, quadratic-strain or vorticity components.

## 3. A coupled departure deadline

Persistent amplification spends kinetic energy faster than a linear enstrophy lower bound records. While $\delta\le0$, differentiate
$$
Z=KE^2+\frac{f_0}{2\nu}K^2.
$$
The exact budgets yield
$$
\begin{aligned}
Z'&=2KE(f-f_0)+2\nu E(KG-E^2)\\
&\ge0.
\end{aligned}
$$
Write
$$
A=K_0E_0^2+\frac{f_0}{2\nu}K_0^2.
$$
Then
$$
E^2\ge\frac{A}{K}-\frac{f_0}{2\nu}K,
\qquad
K'\le-2\nu\sqrt{\frac{A}{K}-\frac{f_0}{2\nu}K}.
$$
Integrating the scalar comparison until its kinetic energy reaches zero gives
$$
\boxed{
T_{\mathrm{cmp}}=
\frac{K_0}{2\nu E_0}\int_0^1
\frac{\sqrt{x}}{\sqrt{1+\chi(1-x^2)}}\,dx,
\qquad
\chi=\frac{f_0K_0}{2\nu E_0^2}>0.
}
$$
The integral is a comparison calculation, independent of a simulated flow.

**Conditional departure statement.** If the full Navier–Stokes solution is smooth through $T_{\mathrm{cmp}}$, there exists $s<T_{\mathrm{cmp}}$ with $\delta(s)>0$. Equivalently, general data face a departure-or-breakdown alternative: either the perturbative condition fails before this deadline or the smooth lifespan ends no later than the deadline.

To check the endpoint, suppose $\delta\le0$ throughout a smooth interval containing the deadline. The inequality for $Z$ prevents $K$ from reaching zero while $E$ stays finite, because $Z\ge A>0$. For positive $K$, the separated differential inequality makes the elapsed time strictly less than the full comparison integral. Neither possibility permits smooth persistence through $T_{\mathrm{cmp}}$ with $\delta\le0$. Continuity supplies an actual positive-defect time before the deadline.

### 3.1 Strict comparison with Miller's energy deadline

The refinement uses the gradient cost already present in the original equation. In the conventions above, Miller's stated energy deadline at general viscosity is
$$
T_*=
\frac{K_0}{\nu\left(E_0+\sqrt{E_0^2+f_0K_0/\nu}\right)},
\qquad
2\nu E_0T_*+\nu f_0T_*^2=K_0.
$$
The equality comparison underlying $T_{\mathrm{cmp}}$ satisfies
$$
\dot k=-2\nu e,
\qquad \dot e=f_0+\nu e^2/k,
\qquad (k(0),e(0))=(K_0,E_0).
$$
Until $k$ reaches zero, $e\ge E_0$ and $k\le K_0$. Thus
$$
\dot e\ge f_0+\nu E_0^2/K_0,
$$
which gives
$$
\boxed{
T_{\mathrm{cmp}}\le
\frac{K_0}{\nu\left(E_0+\sqrt{2E_0^2+f_0K_0/\nu}\right)}
<T_*.
}
$$
The strict inequality therefore holds throughout the positive-data class, beyond the finite quadrature controls. The comparison integral tends to $2/3$ as $\chi\to0^+$; $T_{\mathrm{cmp}}/T_*$ tends to $2/3$ in that limit.

Under the usual Navier–Stokes rescaling $u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t)$, the quantities transform as
$$
(K,E,G,f)\mapsto(\lambda^{-1}K,\lambda E,\lambda^3G,\lambda^3f).
$$
The parameter $\chi$ is invariant, and both deadlines scale as $\lambda^{-2}$. Changing viscosity while setting $u_0=\nu v_0$ is a different similarity: its time scale is $\nu^{-1}$.

## 4. Necessary cumulative departure

The budgets also quantify how much the amplification functional must decrease if the solution remains smooth. Integrating $f'=-3\delta/2$, then the enstrophy and kinetic-energy identities, gives
$$
\boxed{
\begin{aligned}
K(t)={}&K_0-2\nu E_0t-\nu f_0t^2\\
&+\frac{3\nu}{2}\int_0^t(t-s)^2\delta(s)\,ds\\
&-2\nu^2\int_0^t(t-s)G(s)\,ds.
\end{aligned}}
$$
For any smooth horizon $t$, this is an identity. At $t=T_*$, the initial-data polynomial vanishes, so
$$
\int_0^{T_*}(T_*-s)^2\delta(s)\,ds
=
\frac{2K(T_*)}{3\nu}
+\frac{4\nu}{3}\int_0^{T_*}(T_*-s)G(s)\,ds>0.
$$
Strict positivity follows because the nonzero initial datum has $G_0>0$ and the gradient norm is continuous. In particular, some positive defect is necessary by this horizon.

There is also a data-only lower bound on the unweighted positive defect. Define
$$
\delta_+=\max(\delta,0),
\qquad T_0=\frac{K_0}{3\nu E_0}.
$$
If the solution is smooth through $T_0$, then
$$
\boxed{\int_0^{T_0}\delta_+(s)\,ds>\frac23f_0.}
$$
To prove it, suppose $f\ge0$ throughout $[0,T_0]$. The argument in §3 with the constant lower bound zero gives $(KE^2)'\ge0$ and hence
$$
\frac{d}{dt}K^{3/2}\le-3\nu E_0\sqrt{K_0}.
$$
At $T_0$, this forces $K=0$, contradicting $KE^2\ge K_0E_0^2>0$ and smoothness. Therefore some $s<T_0$ has $f(s)<0$. The exact derivative identity then yields
$$
\int_0^{T_0}\delta_+(r)\,dr
\ge\int_0^s\delta(r)\,dr
=\frac23(f_0-f(s))>\frac23f_0.
$$
These are necessary lower bounds on departure, conditional on survival to the stated horizon. They provide no upper bound on concentration or on the magnitude of the remainder.

## 5. Axisymmetric, swirl-free application

Known global regularity removes the breakdown alternative in the axisymmetric, swirl-free class. Every datum in this class satisfying the stated regularity and $f_0>0$ therefore has a positive-defect time before $T_{\mathrm{cmp}}$, and its solution satisfies the cumulative bounds in §4. Miller's Proposition 6.2 and Remark 6.5 supply a nonempty subset with a strict initial perturbative window. Such solutions genuinely depart from a condition that initially holds.

An explicit Gaussian datum verifies the signs and initial-data normalizations:
$$
v=e^{-(x^2+y^2+z^2)}
\left(x(1-2z^2),y(1-2z^2),2z(x^2+y^2-1)\right).
$$
This is the velocity in Miller's Proposition 5.4. It is divergence-free, axisymmetric and swirl-free. Exact Gaussian integration gives
$$
\begin{aligned}
K_v&=\frac{7\sqrt2\,\pi^{3/2}}{64},&
E_v&=\frac{63\sqrt2\,\pi^{3/2}}{64},\\
G_v&=\frac{693\sqrt2\,\pi^{3/2}}{64},&
I_v=-\int\det S_v&=\frac{8\pi^{3/2}}{81\sqrt3}.
\end{aligned}
$$
For $u_0=av$, the amplification functional is
$$
f_0=a^2(4aI_v-3\nu G_v),
\qquad a_{\mathrm{crit}}=\frac{3\nu G_v}{4I_v}.
$$
Thus $a>a_{\mathrm{crit}}$ has $f_0>0$. The fixed controls use $a=ma_{\mathrm{crit}}$ with $m=2,4$. Their dimensionless parameter simplifies to $\chi=11(m-1)/6$.

| Viscosity $\nu$ | Multiplier $m$ | $T_*$ | $T_{\mathrm{cmp}}$ | $T_{\mathrm{cmp}}/T_*$ |
|---|---|---|---|---|
| $0.01$ | $2$ | $3.51589969536$ | $2.67029613364$ | $0.759491556930$ |
| $0.01$ | $4$ | $2.48899153044$ | $1.97733010100$ | $0.794430224779$ |
| $1$ | $2$ | $0.0351589969536$ | $0.0267029613364$ | $0.759491556930$ |
| $1$ | $4$ | $0.0248899153044$ | $0.0197733010100$ | $0.794430224779$ |

The table evaluates guaranteed upper deadlines in these units. It contains no measured departure time. The Gaussian controls' initial perturbative condition is **NOT_EVALUATED**; the nonempty initial-window statement uses Miller's separate construction. No universal favorable sign of the critical work is inferred from these controls.

## 6. Critical work and spectral spread

The critical budget measures concentration at a different derivative order from strain enstrophy. Its cancellation can be quantified through the spread of the velocity spectrum. The estimates below hold on $\mathbb R^3$ under the smoothness and integrability assumptions in §1, and on the mean-zero $2\pi$ torus with volume-normalized integrals. The explicit Fourier controls use the torus.
$$
\mathcal C=\|u\|_{\dot H^{1/2}}^2
=2\|S\|_{\dot H^{-1/2}}^2,
\qquad
Y=\|u\|_{\dot H^{3/2}}^2
=2\|S\|_{\dot H^{1/2}}^2.
$$
With $B=-\mathbb P[(u\cdot\nabla)u]$ and $F=\langle\Lambda u,B\rangle$, the complete budget is
$$
\mathcal C'+2\nu Y=2F.
$$

### 6.1 Optimal scalar centering of the remainder

The zero enstrophy work removes the part of the critical multiplier parallel to the strain. Define
$$
\mathcal V=KE-\mathcal C^2/4\ge0,\qquad
W=\langle\Lambda^{-1/2}S,\Lambda^{-1/2}\mathcal R\rangle.
$$
For real $b$,
$$
\|(\Lambda^{-1}-b)S\|_2^2=K-b\mathcal C+b^2E.
$$
The minimum occurs at $b=\mathcal C/(2E)$. Since $\langle S,\mathcal R\rangle=0$, Cauchy–Schwarz gives
$$
\boxed{|W|^2\le\frac{\mathcal V}{E}\|\mathcal R\|_2^2.}
$$
This is the optimal scalar centering in the displayed Hilbert-space estimate. It gives zero remainder work at a single frequency radius. The complete critical budget also contains the strain-model term:
$$
J=\langle\Lambda^{-1}S,P_{\mathrm{st}}(S^2)\rangle,
\qquad
2F=-\frac83J-4W.
$$
Neither $\|\mathcal R\|_2$ nor $J$ has a data-controlled cumulative bound from the departure comparison alone.

### 6.2 A bound on the complete nonlinear transfer

Energy orthogonality supplies a spectral-spread factor directly for the full nonlinearity. For nonzero data, put
$$
\eta=\frac{\mathcal V}{KE}
=1-\frac{\mathcal C^2}{4KE},\qquad 0\le\eta\le1.
$$
Since $\langle u,B\rangle=0$,
$$
\begin{aligned}
|F|
&=\left|\left\langle
\left(\Lambda-\frac{\mathcal C}{2K}\right)u,B
\right\rangle\right|\\
&\le\sqrt{2E\eta}\,\|B\|_2.
\end{aligned}
$$
Let $c_{\rm S}$ be the product of the constants in the vector-valued embeddings $\dot H^1\hookrightarrow L^6$ and $\dot H^{1/2}\hookrightarrow L^3$, with the corresponding fixed-domain constants on the mean-zero torus. Hölder's inequality and the $L^2$ contraction of the Leray projection give
$$
\|B\|_2
\le\|u\|_6\|\nabla u\|_3
\le c_{\rm S}\sqrt{2E}\sqrt{Y}.
$$
The derivative on $\nabla u$ is included: $\|\nabla u\|_{\dot H^{1/2}}^2=Y$. Interpolation gives $2E\le\sqrt{\mathcal C Y}$, so
$$
\boxed{
|F|\le c_{\rm S}\sqrt{\eta\mathcal C}\,Y.
}
$$
Every derivative on the right belongs to the critical dissipation $Y$; this argument requires no absorption of the higher-order quantity $G$.

For any fixed $0<\theta<1$, the hypothesis
$$
c_{\rm S}\sqrt{\eta(t)\mathcal C(t)}\le\theta\nu
$$
throughout a smooth time interval implies
$$
\mathcal C'+2(1-\theta)\nu Y\le0.
$$
Thus $\sup\mathcal C$ and $\int Y\,dt$ are bounded on that interval. Since $4E^2\le\mathcal C Y$, the Sobolev inequality gives $u\in L^4_tL^6_x$, sufficient for Serrin continuation at a finite endpoint. This is a conditional estimate with a spectral-spread factor. A bound on its evolving coefficient from arbitrary initial data is still required.

### 6.3 Exact spread dissipation and nonlinear production

Viscosity decreases the unnormalized spread, while convection can replenish it.
Set
$$
\mathcal A:=\langle\Lambda^2u,B\rangle
=\int\omega\cdot S\omega\,dx,
\qquad
\mathcal Q:=2KG+2E^2-\mathcal C Y,
\qquad
\mathscr P_{\mathcal V}:=K\mathcal A-\mathcal C F.
$$
Differentiating $\mathcal V$ using $K'=-2\nu E$,
$E'=\mathcal A-2\nu G$ and the critical budget gives
$$
\boxed{\mathcal V'+\nu\mathcal Q=\mathscr P_{\mathcal V}.}
$$
For the radial spectral energy measure $d\mu(r)$, whose moments of orders
$0,1,2,3,4$ are $2K,\mathcal C,2E,Y,2G$,
$$
\mathcal V=\frac18\iint(r-s)^2\,d\mu(r)d\mu(s),
$$
$$
\boxed{
\mathcal Q
=\frac14\iint(r-s)^2(r^2+s^2)\,d\mu(r)d\mu(s)\ge0.
}
$$

At any time with $K=0$, the velocity vanishes and the unnormalized identities
are trivial. In the nontrivial case $K>0$, the normalized radial measure is
well-defined.

The spread dissipation controls the coefficient in the complete critical
transfer estimate. Normalize $d\mu/(2K)$ to a probability measure and write
$$
a=\mathbb E R=\frac{\mathcal C}{2K},\quad
b=\mathbb E R^2=\frac EK,\quad
c=\mathbb E R^3=\frac Y{2K},\quad
d=\mathbb E R^4=\frac GK,
$$
$$
v=b-a^2,\qquad
q=d+b^2-2ac.
$$
Then $\eta=v/b$ and $\mathcal Q=2K^2q$. With
$$
h=\mathbb E\!\left[R^2(R-a)^2\right],
$$
direct expansion gives
$$
q=bv+h.
$$
Consequently
$$
\boxed{\mathcal Q\ge2\eta E^2.}
$$
A second sharp moment inequality retains the critical dissipation $Y$. Put
$L=a(3b-a^2)$. Then
$$
b(q-\eta ac)=bd+b^3-Lc.
$$
Cauchy–Schwarz gives $bd\ge c^2$. Since
$x=a/\sqrt b\in[0,1]$,
$$
L=b^{3/2}x(3-x^2)\le2b^{3/2},
$$
and hence
$$
\begin{aligned}
b(q-\eta ac)
&\ge c^2-Lc+b^3\\
&=\left(c-\frac L2\right)^2+b^3-\frac{L^2}{4}\ge0,
\end{aligned}
$$
where
$$
b^3-\frac{L^2}{4}
=\frac{b^3}{4}(1-x^2)^2(4-x^2).
$$
It follows that
$$
\boxed{\mathcal Q\ge\frac12\eta\mathcal C Y.}
$$
Both constants are optimal among nonnegative radial measures. For
$(1-p)\delta_0+p\delta_r$,
$$
\frac{\mathcal Q}{\eta E^2}=\frac2p,\qquad
\frac{\mathcal Q}{\eta\mathcal C Y}=\frac1{2p},
$$
and the limits as $p\uparrow1$ are $2$ and $1/2$.

The same quantity centers the nonlinear spread production. Define
$$
m=\frac{\mathcal C}{2K}=a,\qquad
k=\mathbb E[(R-a)^4],\qquad
e=\mathbb E[R(R-a)^2].
$$
Expansion gives
$$
q-k=v^2+2ae\ge0,
$$
so
$$
\boxed{
\|(\Lambda-m)^2u\|_2^2
=2Kk\le\frac{\mathcal Q}{K}.
}
$$
A further expansion compares this radial spread with Miller's
squared-frequency deficit:
$$
q-\frac{d-b^2}{2}=\frac{k+3v^2}{2}\ge0,
$$
and therefore
$$
\boxed{
G-\frac{E^2}{K}\le\frac{\mathcal Q}{K}.
}
$$
The coefficient one is optimal in this centered fourth-moment bound. Energy
orthogonality now yields
$$
\begin{aligned}
\mathscr P_{\mathcal V}
&=K\left\langle(\Lambda-m)^2u,B\right\rangle\\
&=K\mathcal A-2KmF+Km^2\langle u,B\rangle
:=K\mathcal A-\mathcal C F.
\end{aligned}
$$
Together with the bound on $B$ in §6.2,
$$
\boxed{
|\mathscr P_{\mathcal V}|
\le c_{\rm S}\sqrt{2KEY\mathcal Q}.
}
$$
Young's inequality therefore gives
$$
\boxed{
\mathcal V'+\frac\nu2\mathcal Q
\le\frac{c_{\rm S}^2}{\nu}KEY.
}
$$
The right-hand side remains uncontrolled for arbitrary data. A radial measure
supported on one radius has $\mathcal Q=0$ even when its spectral center and
$G$ are arbitrarily large, so $\mathcal Q$ supplies spread rather than a raw
high-frequency bound.

There is also a direct continuation reduction. The complete transfer estimate
in §6.2 and $\eta\mathcal C Y\le2\mathcal Q$ imply, for
$0<\varepsilon\le2\nu$,
$$
\boxed{
\mathcal C'+(2\nu-\varepsilon)Y
\le\frac{2c_{\rm S}^2}{\varepsilon}\mathcal Q.
}
$$
Indeed,
$$
2|F|\le2c_{\rm S}\sqrt{2\mathcal QY}
\le\varepsilon Y+\frac{2c_{\rm S}^2}{\varepsilon}\mathcal Q.
$$
Taking $\varepsilon=\nu$, integrating, and using the exact spread budget gives
$$
\begin{aligned}
\mathcal C(t)+\nu\int_0^tY\,ds
&\le\mathcal C(0)+\frac{2c_{\rm S}^2}{\nu}
\int_0^t\mathcal Q\,ds\\
&=\mathcal C(0)+\frac{2c_{\rm S}^2}{\nu^2}
\left(\mathcal V(0)-\mathcal V(t)
+\int_0^t\mathscr P_{\mathcal V}\,ds\right)\\
&\le
\boxed{
\mathcal C(0)+\frac{2c_{\rm S}^2}{\nu^2}
\left(\mathcal V(0)
+\int_0^t(\mathscr P_{\mathcal V})_+\,ds\right).
}
\end{aligned}
$$
Thus
$$
\int_0^T(\mathscr P_{\mathcal V})_+\,dt<\infty
$$
is a continuation criterion at a finite smooth endpoint. The displayed bound
controls $\sup_{t<T}\mathcal C(t)$ and $\int_0^T Y\,dt$. Since
$4E^2\le\mathcal C Y$,
$$
\int_0^T\|u\|_6^4\,dt
\le C_{\mathbb T^3}\sup_{t<T}\mathcal C(t)\int_0^T Y\,dt<\infty.
$$
The Prodi–Serrin criterion with time exponent four and space exponent six
then continues the solution. A constant periodic mean is removed by the
Galilean transformation in §9.5.

This gives a concrete sufficient all-data target. With $R_0$ as in §9.1,
seek
$$
\boxed{
\sup_{0\le t<\min(T,T_*)}
\int_0^t(\mathscr P_{\mathcal V})_+\,ds
\le M_{\mathcal V}(\nu,T,R)<\infty
\quad\text{whenever }R_0\le R.
}
$$
The initial quantities $\mathcal C(0)$ and $\mathcal V(0)$ are bounded in
terms of $R$, and orthogonal Fourier truncations preserve the same initial
$H^3$ bound. This estimate would therefore give global regularity for smooth
periodic data. No such arbitrary-data estimate is established here.

Two admissible flows delimit possible shortcuts. The periodic datum
$$
u_0=a(\sin y,\sin z,\sin x),\qquad a\ne0,
$$
has one frequency radius. Its full Navier–Stokes derivatives satisfy
$$
\mathcal V(0)=\mathcal V'(0)=0,\qquad
\boxed{\mathcal V''(0)=\frac{9a^6}{16}(3-2\sqrt2)>0.}
$$
The nonlinear derivative lies on radius $\sqrt2$, and its spectral energy is
of order $t^2$. Hence $\mathcal Q(0)=\mathcal Q'(0)=0$ and
$$
\boxed{
\mathscr P_{\mathcal V}(0)=0,\qquad
\mathscr P_{\mathcal V}'(0)
=\frac{9a^6}{16}(3-2\sqrt2)>0.
}
$$
Positive spread production therefore begins immediately from a
monochromatic datum.

The exact globally smooth family in §9 also excludes a linear cumulative
bound for the new quantities. At viscosity one, the choice
$\varepsilon=2\nu$ above gives $\mathcal C'\le c_{\rm S}^2\mathcal Q$.
Since $\mathcal C(0)=N^6$,
$\mathcal C(t_N)\ge N^7/64$ and $\mathcal V(0)=0$,
$$
\int_0^{t_N}\mathcal Q\,dt
\ge\frac{N^7/64-N^6}{c_{\rm S}^2},
$$
$$
\int_0^{t_N}(\mathscr P_{\mathcal V})_+\,dt
\ge\int_0^{t_N}\mathscr P_{\mathcal V}\,dt
=\mathcal V(t_N)+\int_0^{t_N}\mathcal Q\,dt
\ge\frac{N^7/64-N^6}{c_{\rm S}^2}.
$$
For $N\ge65$ these lower bounds are positive, and division by
$\mathcal C(0)$ gives $(N/64-1)/c_{\rm S}^2\to\infty$. The family permits
finite datum-dependent bounds, while excluding a universal coefficient
linear in the initial squared critical norm.

### 6.4 Instantaneous amplification and critical growth

A negative amplification functional and declining spectral spread can coexist with critical growth in an admissible smooth velocity field. The three-coordinate Fourier fixture in `computations/navier-stokes-critical-recurrence-prereg.md` at $a=4$, $\nu=1/100$ gives
$$
f=-107.52,\qquad
\mathcal C'=\frac{44208}{25}-784\sqrt5
=15.2427056401649\ldots>0,
$$
$$
\mathcal V'=-22947.8011094927\ldots<0.
$$
These are full-equation derivatives at the initial datum. The strict signs persist for a sufficiently short smooth interval. The remainder itself contributes $-4W=74.6997932801615\ldots$ to $\mathcal C'$ at that instant; the strain-model contribution and viscosity must also be retained.

The functional sign $f<0$ is distinct from departure, which is $\delta>0$ and hence $f'<0$. This fixture has $\delta=-53287.808$. None of the 24 frozen velocity rows has positive $\delta$, so the protocol classifies the implication $\delta>0\Rightarrow\mathcal C'\le0$ as **INCONCLUSIVE**. These controls provide no instantaneous counterexample to that particular implication.

### 6.5 A scalar-budget obstruction to cumulative control

The energy and departure identities alone permit divergent critical moments even with positive departure throughout. This limitation can be demonstrated with positive spectral moments, without asserting a Navier–Stokes trajectory. Set $\tau=1-t$, $0\le t<1$, $\nu=1$, and
$$
K=8\tau^{1/4},\quad
E=\tau^{-3/4},\quad
G=\frac32\tau^{-7/4},\quad
f=-\frac34\tau^{-7/4},\quad
\delta=\frac78\tau^{-11/4}.
$$
These functions satisfy
$$
K'=-2E,\qquad E'=f+G,\qquad f'=-\frac32\delta,
\qquad E^2\le KG.
$$
They also have $\int_0^1E\,dt=4$, $f<0$, $\delta>0$ and $KE=8\tau^{-1/2}\to\infty$.

A positive two-atom measure of mass $2K$, weights $44/45,1/45$ and frequency radii
$$
r_1=\frac{\tau^{-1/2}}4,\qquad
r_2=\frac{\sqrt{46}\,\tau^{-1/2}}4
$$
has moments $m_0=2K$, $m_2=2E$, $m_4=2G$. Its critical moments are
$$
\mathcal C=m_1=\frac{4(44+\sqrt{46})}{45}\tau^{-1/4}\to\infty,
\qquad
Y=m_3=\frac{22+23\sqrt{46}}{90}\tau^{-5/4}.
$$
Taking $F=(\mathcal C'+2Y)/2$ satisfies the scalar critical budget. This assignment supplies no nonlinear velocity realizing $F$ or the strain remainder. Atomic radial measures also do not supply finite-energy velocities on $\mathbb R^3$ or a fixed periodic frequency lattice. The result is a counterexample to closure from the listed scalar relations; full PDE compatibility remains an additional constraint. Its $f_0<0$ lies outside the initial positive-amplification hypothesis in §3.

### 6.6 Established criterion and remaining proof requirement

Spectral concentration already enters the regularity literature. Miller's Corollary 1.3 in [the Laplacian-eigenfunction paper](https://arxiv.org/abs/2005.14152) gives a continuation criterion on $\mathbb R^3$ through finiteness of
$$
\int_0^T\left(G-\frac{E^2}{K}\right)^{2/3}dt
$$
at fixed $\nu>0$. The underlying centered residual is
$$
\inf_\lambda\|-\Delta u-\lambda u\|_2^2
=2\left(G-\frac{E^2}{K}\right).
$$
This is a spread in squared frequency and differs from $\mathcal V$. The
pointwise comparison in §6.3 gives
$$
G-\frac{E^2}{K}\le\frac{\mathcal Q}{K},
$$
while the time weights and energy factor in the two continuation criteria
remain different. For the scalar construction in §6.5,
$$
\left(G-\frac{E^2}{K}\right)^{2/3}
:=\frac{11^{2/3}}4\tau^{-7/6},
$$
whose time integral diverges. The construction is consistent with Miller's
criterion.

Section 6.3 supplies an exact continuation reduction through cumulative
positive spread production. The remaining all-data lemma is the finite
$M_{\mathcal V}(\nu,T,R)$ bound displayed there. The direct production
estimate leaves $\int KEY\,dt$ uncontrolled; kinetic-energy dissipation
controls $\int E\,dt$ but supplies no bound on this product. The exact mixing
family excludes dependence linear in $\mathcal C(0)$ without excluding the
prescribed initial-$H^3$ dependence of $M_{\mathcal V}$.

For general three-dimensional data, breakdown before departure, recurrent
amplification and symmetry-breaking disturbances remain possible within the
present estimates. No arbitrary-data bound on positive spread production or
Cassi current-to-momentum constitutive law is established. No priority or
stronger-than-Miller theorem is asserted.

## 7. Verification and evidence scope

### 7.1 Departure comparison

The fixed analytical-verification schedule passes **71 checks**, with maximum normalized numerical discrepancy **$9.633333680505873\times10^{-15}$** against the threshold $10^{-10}$. It covers the projected completion of squares, variational derivative, comparison monotonicity, cumulative identity, Fourier scaling, exact Gaussian moments, independent cylindrical quadrature and comparison-deadline quadrature.

The cylindrical reconstruction uses Gaussian–Laguerre and Gaussian–Hermite orders 12 and 20, including the angular-basis derivative in the vorticity-gradient norm. The deadline checks compare Gaussian–Legendre orders 64 and 128 with independent 50-digit adaptive quadrature. The finite controls qualify their calculations. The continuum comparison and the strict inequality in §3 follow from the displayed analytical proof.

Independent analytical reviews reconcile the scalar comparison, endpoint alternative and cumulative excess-dose proof with the derivations above. `runs/navier_stokes_strain_departure/reconciliation.json` records the accepted statements and excludes ancillary reviewer claims that lack qualification. Data-controlled critical-work closure remains open.

The accepted receipt is `runs/navier_stokes_strain_departure/qualified/verification.json`, schema `cassi.navier-stokes.strain-departure.verification.v1`, with adjacent `verification.inputs.json` and `verification.sources/`. The manifest, retained source snapshots and executable inputs agree on the following raw SHA-256 identities:

| Input | SHA-256 |
|---|---|
| Fixed protocol | `d783fe2f0b628bc4c97f010f540f65d871765e28973b4627a6f55df494c4d97c` |
| Departure verifier | `d784db3a6a61da213f2d15e1e38302c604c99e49b662e420ebd2115df26ba0b8` |
| Depletion helper | `f74633d488d974e8bb3c83d24448064f2badb89059a6938fcc8235db3e7426e5` |
| Fourier helper | `a7ca230b989f5713cb511b18971007d41cbdad20d9c8cf8e2af7d34f107755e0` |

The retained `runs/navier_stokes_strain_departure/verification.json` is a **FAIL** diagnostic: its two viscosity-normalization checks use a squared viscosity ratio. It is excluded from mathematical qualification and retains its own input manifest and source snapshots. The accepted comparison uses the $\nu^{-1}$ time similarity stated in §3.1. The frozen protocol has the same raw hash in both receipts.

The departure schedule runs no Navier–Stokes trajectory. No observed exit time, singularity, fitted constant or general regularity verdict is recorded by that schedule. Arbitrary-data critical work and regularity remain **UNRESOLVED**. No physical parameter, numbered open question or empirical prediction is introduced or reclassified.

To reproduce from CassiTheory, supply a fresh path to `python computations/verify_navier_stokes_strain_departure.py --output runs/navier_stokes_strain_departure/reproduction/verification.json`. Existing receipt paths are immutable.

### 7.2 Critical recurrence controls

The separate fixed schedule in `computations/navier-stokes-critical-recurrence-prereg.md` passes **134 checks**, including **24 exact velocity rows** and **48 independent FFT rows** at grids $24^3$ and $32^3$. The maximum normalized numerical discrepancy is **$1.0766942892814768\times10^{-12}$**, below $10^{-10}$. Every generated Fourier mode needed by the contractions is retained. The spatial reconstruction evaluates the complete projected remainder independently of the exact convolution and tensor helpers.

The accepted receipt is `runs/navier_stokes_critical_recurrence/verification.json`, schema `cassi.navier-stokes.critical-recurrence.verification.v1`, with adjacent `verification.inputs.json` and `verification.sources/`. Current executable inputs, the manifest and retained source snapshots have matching raw SHA-256 identities:

| Input | SHA-256 |
|---|---|
| Fixed recurrence protocol | `7d93b9a6821edf4ace662f97e1712cf823fa2178a9c4c5244d2165178e846da9` |
| Recurrence verifier | `61295a26a09506d6e336a541dd684fc690d800a524cab84899742b4454a800ce` |
| Depletion helper | `f74633d488d974e8bb3c83d24448064f2badb89059a6938fcc8235db3e7426e5` |
| Fourier helper | `a7ca230b989f5713cb511b18971007d41cbdad20d9c8cf8e2af7d34f107755e0` |

The frozen classifications are **CONTRADICTS** universal zero-spread preservation in the periodic control, **INCONCLUSIVE** for departure implying a nonincreasing critical norm, and **CONTRADICTS** closure from the listed scalar budgets. The last classification concerns scalar consistency only. Data-controlled critical production, recurrence control and arbitrary-data regularity remain **UNRESOLVED**.

The Sobolev estimates and continuation arguments in §§6.2–6.3 are analytical derivations; the 134-check receipt does not constitute their continuum proof. No Navier–Stokes time trajectory is integrated. To reproduce the fixed controls, use `python computations/verify_navier_stokes_critical_recurrence.py --output runs/navier_stokes_critical_recurrence/reproduction/verification.json` with a fresh output path.

Independent analytical reviews confirm the centered remainder estimate, the full-transfer derivative weights and the fixed scalar identities. The accepted continuation argument uses $L^4_tL^6_x$. `runs/navier_stokes_critical_recurrence/reconciliation.json` records the accepted proof statements, their scope and the excluded auxiliary claims; it is retained locally with the generated evidence.

### 7.3 Forced concentration controls

The post-run qualification in `computations/navier-stokes-forced-concentration-prereg.md` passes **215 checks**, including **20 exact forced velocity rows**, **40 independent FFT rows** on $24^3$ and $32^3$ grids, a forcing-from-rest control and exact Gaussian moments with independent 60-digit quadrature. The maximum normalized numerical discrepancy is **$7.275957614183426\times10^{-12}$**, below $10^{-10}$. The sign controls cover all three source pairings $I_0,I_1,I_2$; the maximum-speed scaling is evaluated from the scaled Gaussian field. Pressure-gradient removal, the complete forced strain identity and the critical forcing duality are included.

The selected post-run qualification receipt is `runs/navier_stokes_forced_concentration/qualified_v3/verification.json`, schema `cassi.navier-stokes.forced-concentration.verification.v1`, with adjacent `verification.inputs.json` and `verification.sources/`. Its exact and spatial rows equal those of the preregistered run. All five qualification input identities match the current raw source bytes and qualification snapshots:

| Input | SHA-256 |
|---|---|
| Qualification specification | `3cd568c5c5540cfe039ca07f6c736b9158f5c420e09ecd9570d13fc93c4b7065` |
| Forced verifier | `6349f3c3f2dd97c804f8f2bae0a313467fd6f5e06b3ade7d415283e343cb7c74` |
| Recurrence helper | `61295a26a09506d6e336a541dd684fc690d800a524cab84899742b4454a800ce` |
| Depletion helper | `f74633d488d974e8bb3c83d24448064f2badb89059a6938fcc8235db3e7426e5` |
| Fourier helper | `a7ca230b989f5713cb511b18971007d41cbdad20d9c8cf8e2af7d34f107755e0` |

The preregistered evidence remains `runs/navier_stokes_forced_concentration/verification.json`, its adjacent manifest and snapshots, and `runs/navier_stokes_forced_concentration/reconciliation.json`. That frozen run has 215 passing checks and binds protocol SHA-256 `2aa31e17c796fff7d438024154f468570e34e1a7ab3c4abc64270ee1c0ab2b2f` and verifier SHA-256 `7ddcb369a804580b3b1e1c520a02862ab7229648689f2cb4fef1abf5948ba40e`. Its input comparisons concern the retained source snapshots. The qualification is separate post-run evidence and carries its own hashes. The records `runs/navier_stokes_forced_concentration/qualified/verification.json` and `runs/navier_stokes_forced_concentration/qualified_v2/verification.json`, with their adjacent manifests and snapshots, are retained qualification diagnostics.

The Gaussian family's classification is **CONTRADICTS** for the purely kinematic implication from bounded energy and unbounded maximum velocity to divergent critical norm. Its scope is a family of solenoidal fields. No Navier–Stokes trajectory or singularity is computed. The continuum inequalities below have a separate analytical derivation. The announced construction's proof is **NOT_AUDITED**, and unforced blow-up, arbitrary-data regularity and a nontrivial blow-up limit remain **UNRESOLVED**.

The post-run analytical reconciliation is retained in `runs/navier_stokes_forced_concentration/qualified_v3/reconciliation.json`. It records the qualified continuum estimates, endpoint force assumptions, finite direct source work, cumulative excess-transfer condition and source-qualified leading growth asymptotic. Independent reviews are restricted to those statements. The numerical checks verify the budgets and fixed controls; they do not establish the continuum continuation argument or the announced construction.

To reproduce the qualification, use `python computations/verify_navier_stokes_forced_concentration.py --output runs/navier_stokes_forced_concentration/qualified_reproduction/verification.json` with a fresh output path. Each receipt's input manifest and source snapshots identify its computation.

### 7.4 Unforced cumulative mixing controls

The fixed schedule in `computations/navier-stokes-mixing-budget-prereg.md`
passes **601 checks**. Its eight physical cases use
$N=2,4,8,16,32,64,128,256$, with two Fourier cutoffs per case and one
zero-shear heat control: **17 numerical evolutions** in total.
Each evolution retains 1,001 sampled states. Forty independent spatial
reconstructions check the critical and kinetic quantities, full convection,
pressure projection, momentum equation, incompressibility and odd phase.
The maximum normalized discrepancy is
$2.2384929847241164\times10^{-11}$ against the fixed tolerance $10^{-8}$.

The finer trajectories give the following endpoint values. The viscosity is
one, the initial amplitude is $N^3$, and $t_N=1/(2N^2)$.

| $N$ | $\mathcal C(t_N)/\mathcal C(0)$ | $\mathcal W_{1/2}(t_N)/\mathcal C(0)$ |
|---|---|---|
| 2 | 0.823147906 | 0 |
| 4 | 1.202513994 | 0.126714769 |
| 8 | 1.791807097 | 0.415134761 |
| 16 | 2.970060320 | 1.013096106 |
| 32 | 5.356797844 | 2.230579389 |
| 64 | 10.160722058 | 4.683033991 |
| 128 | 19.789812829 | 9.599474730 |
| 256 | 39.061232232 | 19.439379455 |

The finite unit-initial-budget control is **CONTRADICTS**: at $N=256$,
the continuum proof in §9 gives a ratio at least $3/2$, and the numerical
ratio exceeds one. The exclusion of every finite amplitude-independent
coefficient $K(\nu,T)$ follows from the unbounded continuum family in §9.5.
The numerical approximations supply finite-resolution checks of the
invariant evolution and its budgets.

The receipt is `runs/navier_stokes_mixing_budget/verification.json`,
schema `cassi.navier-stokes.mixing-budget.verification.v1`, with adjacent
`verification.inputs.json`, `verification.sources/` and
`verification.trajectories.npz`. All four raw input identities match the
live sources, manifest, receipt and snapshots. The trajectory archive hash
also matches its receipt.

The separate `runs/navier_stokes_mixing_budget/reconciliation.json` records
the accepted analytical reviews and an independent raw-array reconstruction.
The latter checks all 51 archive arrays and 17,017 sampled states, rebuilds
the eight fine endpoints by direct sine quadrature, and compares stored
critical and kinetic balances. Its 113 comparisons have maximum normalized
discrepancy $5.920390225714912\times10^{-14}$. It imports no verifier helpers
and performs no additional trajectory integration. These comparisons remain
separate from the 601-check preregistered receipt.

The reconciliation retains the audit's `python_source` and `source_sha256`
under `independent_array_reconstruction`. From CassiTheory, execute its
stored source without starting a flow:

```
python -c "import hashlib, json; from pathlib import Path; a=json.loads(Path('runs/navier_stokes_mixing_budget/reconciliation.json').read_text(encoding='utf-8'))['independent_array_reconstruction']; s=a['python_source']; assert hashlib.sha256(s.encode('utf-8')).hexdigest()==a['source_sha256']; exec(compile(s, '<retained-array-audit>', 'exec'))"
```

To reproduce the separate 601-check investigation, use
`python computations/verify_navier_stokes_mixing_budget.py --output runs/navier_stokes_mixing_budget/reproduction/verification.json`
from CassiTheory with a fresh output path. Existing receipts are immutable.
The continuum lower bound, the class-specific finite upper bound and
arbitrary-data regularity have the distinct scopes stated in §9.

## 8. External forcing and concentration limits

### 8.1 Exact source terms

An external force can inject energy and alter the strain comparison even when it remains smooth. Denote it by $f_{\rm ext}$ to distinguish it from the amplification functional $f$ in §1, and put
$$
g=\mathbb P f_{\rm ext},\qquad
\partial_tu=B-\nu\Lambda^2u+g,\qquad
I_j=\langle\Lambda^j u,g\rangle,\quad j=0,1,2.
$$
The definitions of $K,E,G,\mathcal C,Y,A,F,\mathcal V$ are unchanged. Integration by parts and the Leray projection give
$$
\boxed{
\begin{aligned}
K'&=-2\nu E+I_0,\\
E'&=A-2\nu G+I_2,\\
\mathcal C'&=-2\nu Y+2F+2I_1.
\end{aligned}}
$$
Differentiating $\mathcal V=KE-\mathcal C^2/4$ consequently yields
$$
\boxed{
\mathcal V'+\nu(2KG+2E^2-\mathcal C Y)
=KA-\mathcal C F+EI_0+KI_2-\mathcal C I_1.
}
$$
A gradient part of $f_{\rm ext}$ is absorbed into pressure. On the torus these statements use mean-zero velocity and mean-zero forcing. On $\mathbb R^3$ the displayed norms must be finite.

The amplification derivative also has a source term. With $T=\nabla_{\rm sym}g$, the strain equation becomes $S_t=-M-\mathcal R+T$. For an admissible strain variation $H$,
$$
Df[S](H)=-6\langle M,H\rangle.
$$
Indeed, differentiating $-3\nu\|\nabla S\|_2^2$ gives $-6\nu\langle\Lambda^2S,H\rangle$. The trace-free variation of the determinant gives $\langle S^2,H\rangle$; orthogonal projection onto admissible strains supplies the remaining term in $M$. Therefore
$$
\boxed{f'=-\frac32\delta-6\langle M,T\rangle.}
$$
This extra work has no universal sign. The monotonicity and deadlines in §§3–5 require the unforced identities specified there.

### 8.2 Smooth forcing in the critical estimate

The critical source work can be bounded using a norm of the prescribed force. Let
$$
H_g(t)=\|g(t)\|_{\dot H^{-1/2}}.
$$
The exact pairing and Cauchy–Schwarz give
$$
I_1=\langle\Lambda^{3/2}u,\Lambda^{-1/2}g\rangle,
\qquad |I_1|\le\sqrt{Y}\,H_g.
$$
The estimate for $F$ in §6.2 is an instantaneous property of the velocity nonlinearity, so it still applies. Suppose, throughout a smooth interval $[t_0,T_*)$,
$$
c_{\rm S}\sqrt{\eta(t)\mathcal C(t)}\le\theta\nu,
\qquad 0<\theta<1,\qquad d=(1-\theta)\nu.
$$
Set $\eta=0$ at the zero field; all nonlinear work then vanishes. Young's inequality gives
$$
2|I_1|\le dY+\frac{H_g^2}{d},
$$
and hence
$$
\boxed{
\mathcal C(t)+d\int_{t_0}^tY(s)\,ds
\le\mathcal C(t_0)+\frac1d\int_{t_0}^tH_g(s)^2\,ds.
}
$$
If $g\in L^2((t_0,T_*);\dot H^{-1/2})$, both quantities on the left stay bounded. The interpolation $4E^2\le\mathcal C Y$ supplies $\int E^2<\infty$ and thus $u\in L^4_tL^6_x$. For continuation, also require $g\in L^2((t_0,T_*);L^2)$ and a force smooth through the endpoint in the strong-solution class. The usual $H^1$ energy estimate then has an integrable coefficient proportional to $\|u\|_6^4$ and an integrable forcing term, so strong-solution continuation applies. Smooth compactly supported space-time forces on $\mathbb R^3$, and smooth mean-zero periodic forces on $\mathbb T^3$ through $T_*$, satisfy these endpoint requirements.

A smooth compactly supported space-time force satisfies the required force condition on every finite interval. At low Fourier frequencies, bounded $\widehat f_{\rm ext}$ makes the weight $|k|^{-1}$ integrable in three dimensions; at high frequencies the $L^2$ bound suffices. The Leray projection is a contraction for this weighted norm. This gives a conditional continuation estimate for such forcing. Controlling $\eta\mathcal C$ from arbitrary initial data remains an additional requirement.

Any finite-time breakdown under these force assumptions must therefore violate every uniform subcritical margin near its endpoint:
$$
\limsup_{t\uparrow T_*}c_{\rm S}\sqrt{\eta(t)\mathcal C(t)}\ge\nu.
$$
This necessary condition bounds a product. It supplies no lower bound on $\eta$ alone.

There is also a useful consequence without the spectral hypothesis. Taking $d=\nu$ in Young's inequality and using $F\le F_+:=\max(F,0)$ before integration gives
$$
\boxed{
\mathcal C(t)+\nu\int_{t_0}^tY
\le\mathcal C(t_0)+2\int_{t_0}^tF_+
+\nu^{-1}\int_{t_0}^tH_g^2.
}
$$
Thus finite $\int_{t_0}^{T_*}F_+\,dt$, where $F_+=\max(F,0)$, is sufficient for continuation under the same force assumptions. A singular solution would require divergent accumulated positive nonlinear critical transfer. The present estimates provide no upper bound on that accumulation.

The same argument gives an excess-transfer condition. For any fixed $0\le\kappa<1$, define
$$
\mathcal W_\kappa(t)=\int_{t_0}^t(F-\kappa\nu Y)_+\,ds,
\qquad d_\kappa=(1-\kappa)\nu.
$$
Using $F\le\kappa\nu Y+(F-\kappa\nu Y)_+$ before the source estimate yields
$$
\boxed{
\mathcal C(t)+d_\kappa\int_{t_0}^tY
\le\mathcal C(t_0)+2\mathcal W_\kappa(t)
+d_\kappa^{-1}\int_{t_0}^tH_g^2.
}
$$
Finite $\mathcal W_\kappa(T_*)$ therefore suffices for continuation. Conversely, any finite-time singularity under the stated force assumptions must have $\mathcal W_\kappa(T_*)=\infty$ for every fixed $\kappa<1$. The endpoint $\kappa=1$ supplies no positive dissipation coefficient and is excluded. This cumulative condition permits temporary large positive transfer; it requires control of its accumulated excess over a fixed fraction of viscosity.

For smooth compactly supported forcing there is also a direct bound on total source work that uses only prescribed force norms and initial energy. The regularized kinetic inequality gives
$$
\|u(t)\|_2\le U_*(T_*):=
\|u(t_0)\|_2+\int_{t_0}^{T_*}\|g(s)\|_2\,ds.
$$
Since $I_1=\langle u,\Lambda g\rangle$,
$$
\boxed{
\int_{t_0}^{T_*}|I_1(s)|\,ds
\le U_*(T_*)\int_{t_0}^{T_*}\|\Lambda g(s)\|_2\,ds<\infty.
}
$$
Regularizing $\sqrt{\|u\|_2^2+\varepsilon}$ justifies the energy bound at zero velocity. This stronger spatial regularity of the prescribed force is automatic in the smooth compactly supported case. The directly injected critical work is then finite even if the nonlinear transfer has unbounded accumulation. These are analytical corollaries; the fixed finite controls in §7.3 verify the underlying budgets and normalization.

### 8.3 Vanishing source under parabolic magnification

A smooth external force becomes small when space and time are magnified around a proposed singular point. On $\mathbb R^3$, define
$$
u_\lambda(y,s)=\lambda u(x_*+\lambda y,T_*+\lambda^2s),
\quad p_\lambda(y,s)=\lambda^2p(x_*+\lambda y,T_*+\lambda^2s),
$$
$$
(f_{\rm ext})_\lambda(y,s)
=\lambda^3 f_{\rm ext}(x_*+\lambda y,T_*+\lambda^2s),
\qquad \lambda\downarrow0.
$$
Every term in the momentum equation has the same factor $\lambda^3$. For multi-indices $\alpha$ and time-derivative order $j$,
$$
\partial_y^\alpha\partial_s^j(f_{\rm ext})_\lambda
=\lambda^{3+|\alpha|+2j}
(\partial_x^\alpha\partial_t^j f_{\rm ext})(x_*+\lambda y,T_*+\lambda^2s).
$$
Consequently the source tends to zero with all derivatives on compact rescaled sets when the physical force is smooth through $T_*$. The projected source also obeys the exact Euclidean identity
$$
\int_{-L}^0\|g_\lambda(s)\|_{\dot H^{-1/2}}^2\,ds
=\int_{T_*-L\lambda^2}^{T_*}\|g(t)\|_{\dot H^{-1/2}}^2\,dt
\longrightarrow0
$$
for every fixed $L>0$, by absolute continuity of the force integral.

These statements concern the source. Constructing a limiting velocity requires uniform local velocity, pressure and local-energy bounds, compactness sufficient to pass $u_\lambda\otimes u_\lambda$, and a nondegeneracy argument preventing the limit from vanishing. The limit domain and solution class must also be specified. In particular,
$$
K[u_\lambda]=\lambda^{-1}K[u],
\qquad \mathcal C[u_\lambda]=\mathcal C[u],
$$
so bounded physical kinetic energy supplies no uniform global energy bound after magnification. A resulting unforced limit would generally be ancient or local. Turning it into finite-time blow-up from admissible smooth unforced initial data requires a further argument.

### 8.4 Scope of the announced forced construction

Theorem 1.1 of OpenAI's *Finite time blowup for Navier–Stokes* states a forced solution starting from rest, with a smooth compactly supported space-time force, uniformly bounded kinetic energy and unbounded maximum velocity as $t\uparrow1$. The source identifies Clay alternatives C and D. The theorem statement alone supplies no unforced counterexample or compactness theorem for the rescalings in §8.3.

The mechanism described in §§2.2 and 3 uses oscillatory velocity pulses whose mean momentum flux cancels a singular residual of the collapsing background. Their amplification draws on background shear. Such internal momentum flux belongs to the nonlinear velocity dynamics $B$; the smooth external source is the final residual. A source that becomes small under magnification can therefore coexist with substantial nonlinear transfer. No universal damping sign for the pulse feedback follows from its small external seed.

Theorem 3.1(iv), together with the localization in §3.5, gives a full-flow leading asymptotic along the growth path:
$$
u_\theta(\sqrt{2X_{\rm in}\tau},0,0,1-\tau)
=\tau^{-1/2-h}\bigl(e_0+o(1)\bigr),
\qquad e_0>0,
$$
where the position is cylindrical. Conditional on that source estimate, the magnification in §8.3 centered at $(0,1)$ gives the fixed-point value
$$
(u_\lambda)_\theta(\sqrt{2X_{\rm in}},0,0,-1)
=\lambda^{-2h}\bigl(e_0+o(1)\bigr)
\longrightarrow\infty.
$$
Thus this parabolic magnification has no locally uniformly bounded velocity subsequence on a neighborhood containing that point, despite the vanishing smooth source. This rules out local $C^0$ compactness for the specified magnification. Other normalizations or weaker limits require separate estimates; the growth-path statement gives no classification of them.

The quoted leading core scales are
$$
\ell_r\asymp\tau^{1/2},\quad
\ell_z\asymp\tau^{1/2-h},\quad
|u_{\theta,z}^{(0)}|\asymp\tau^{-1/2-h},
\qquad \tau=1-t,\quad 0<h<1/100.
$$
Their exponent arithmetic gives core volume $\tau^{3/2-h}$ and characteristic core energy $\tau^{1/2-3h}$, which tends to zero. If the complete velocity has this speed as a lower bound on a fixed positive fraction of that core volume, then
$$
\int|u|^3\,dx\gtrsim\tau^{-4h},
\qquad
\mathcal C\gtrsim\|u\|_3^2\gtrsim\tau^{-8h/3}.
$$
The last inequality uses $\dot H^{1/2}\hookrightarrow L^3$. It is a conditional bulk-volume estimate: an $L^\infty$ lower bound on a single circle or a leading-profile statement alone does not establish its premise for the completed flow. The fixed calculation checks the exponents; it does not verify the correction estimates or the construction.

### 8.5 Kinematic concentration control and remaining requirement

Energy and maximum speed alone leave the critical norm undetermined. Consider the solenoidal Schwartz field
$$
U(x,y,z)=(-2y,2x,0)e^{-(x^2+y^2+z^2)},\qquad
U_\ell(x)=\ell^{-1}U(x/\ell).
$$
With the unitary Fourier transform,
$$
|\widehat U(k)|^2=\frac{k_x^2+k_y^2}{8}e^{-|k|^2/2}.
$$
The exact moments give
$$
K[U_\ell]=\ell\,\frac{\sqrt2\,\pi^{3/2}}4\longrightarrow0,
\qquad
\mathcal C[U_\ell]=\frac{8\pi}{3},
\qquad
\|U_\ell\|_\infty=\ell^{-1}\sqrt{2/e}\longrightarrow\infty.
$$
This family is a kinematic control. No evolution law or admissible smooth forcing for this concentration is asserted.

For original unforced Navier–Stokes dynamics, §6.3 isolates cumulative
positive spectral-spread production as a sufficient continuation quantity;
the finite $M_{\mathcal V}(\nu,T,R)$ bound remains the explicit all-data
target. Cumulative critical production and control of the evolving coefficient
$\eta\mathcal C$ remain alternative routes. The source estimate isolates the
additional terms for smooth forcing, and the force-scaling calculation
specifies the compactness needed to compare a proposed singularity with an
unforced limiting equation. These steps establish neither arbitrary-data
regularity nor an unforced smooth-data singularity.

## 9. Cumulative mixing in an exact periodic family

Smooth unforced solutions can accumulate critical transfer, spread dissipation and positive spread production arbitrarily larger than their initial squared critical norm $\mathcal C(0)$. This constrains the initial-data dependence of the corresponding cumulative bounds. The same family also has a finite critical-transfer upper bound for every datum.

### 9.1 Fixed margin and the candidate

Use the volume-normalized $2\pi$ torus and the definitions of $\mathcal C,Y,F$ in §6. For zero forcing, set
$$
\mathcal W_{1/2}(T)=\int_0^T(F-\nu Y/2)_+\,dt.
$$
The exact critical budget gives
$$
\boxed{
\mathcal C(T)+\nu\int_0^TY\,dt
\le\mathcal C(0)+2\mathcal W_{1/2}(T).
}
$$
The candidate examined here is
$$
\mathcal W_{1/2}(T)\le K(\nu,T)\mathcal C(0),
$$
with finite $K$ independent of the initial datum. The construction below excludes this form, linear in $\mathcal C(0)$, for every fixed $\nu,T>0$.

A concrete sufficient all-data target permits dependence on $\nu$, $T$
and a prescribed bound $R$ on the single initial norm
$$
R_0=\|u_0-\langle u_0\rangle\|_{H^3(\mathbb T^3)}.
$$
Writing $T_*$ for the maximal smooth existence time, one sufficient estimate
is
$$
\sup_{0\le t<\min(T,T_*)}\mathcal W_{1/2}(t)
\le M_{\mathcal W}(\nu,T,R)<\infty
\qquad\text{whenever }R_0\le R.
$$
The spread-production reduction in §6.3 gives the alternative sufficient
estimate
$$
\sup_{0\le t<\min(T,T_*)}
\int_0^t(\mathscr P_{\mathcal V})_+\,ds
\le M_{\mathcal V}(\nu,T,R)<\infty
\qquad\text{whenever }R_0\le R.
$$
Either function must be finite for every $\nu>0$, finite $T>0$ and finite
$R\ge0$, uniformly over all smooth solenoidal periodic data with $R_0\le R$.
Smoothness on the compact torus makes $R_0$ finite for every admissible
datum. For a Fourier-cutoff proof, the same bound must hold at every cutoff:
orthogonal Fourier projection contracts $H^3$, so all projected initial data
obey the same prescribed bound $R$. Evolving norm suprema and cutoff-dependent
quantities are excluded from the right-hand side. Both all-data estimates
remain **UNRESOLVED**.

### 9.2 Full-equation admissibility

A one-way coupling between shear and a third velocity component gives an exact invariant class. For real $A,b$, define
$$
u(x,y,z,t)=(U(y,t),0,bv(x,y,t)),\qquad
U=Ae^{-\nu t}\sin y,\qquad p=0,
$$
where
$$
v_t+Uv_x=\nu(v_{xx}+v_{yy}),\qquad v(x,y,0)=\sin x.
$$
Then $\nabla\cdot u=0$ and
$$
(u\cdot\nabla)u=(0,0,bUv_x).
$$
This convection is itself divergence-free. The horizontal momentum equation is the heat equation for $U$, and the vertical momentum equation is the displayed parabolic equation for $v$. Thus the full three-dimensional Navier–Stokes equation holds with zero pressure gradient.

Every fixed $A,b,\nu$ gives a global smooth solution. In a differentiated $H^m$ energy estimate, the principal transport term integrates to zero; the commutators involve bounded derivatives of $U$ and derivatives of $v$ of order at most $m$. Gronwall bounds these norms by a finite factor of the form $\exp(C_m|A|/\nu)$ times their initial values. These estimates are uniform in Fourier cutoff and give global existence through the linear parabolic problem. No bound uniform in $A$ is assumed.

The infinite sine expansion is
$$
v=\sum_{j\in\mathbb Z}c_j(t)\sin(x+jy),\qquad
c_j'=-\nu(1+j^2)c_j-\frac{Ae^{-\nu t}}2(c_{j-1}-c_{j+1}),
$$
with $c_0(0)=1$ and all other coefficients zero. Both signs of $j$ are included. Since the basis has normalized squared norm $1/2$,
$$
\frac{d}{dt}\sum_jc_j^2=-2\nu\sum_j(1+j^2)c_j^2,\qquad
\sum_jc_j^2\le e^{-2\nu t}.
$$
The coefficients stay real. Consequently $u(-x,-y,-z,t)=-u(x,y,z,t)$, and its nonzero Cartesian Fourier coefficients stay purely imaginary.

### 9.3 A finite data-controlled upper bound

The critical multiplier has a bounded difference between neighboring members of this sine sequence. Write $r_j=\sqrt{1+j^2}$. The complete quantities, including the horizontal shear contribution, are
$$
\mathcal C=\frac12\left(A^2e^{-2\nu t}+b^2\sum_jr_jc_j^2\right),\qquad
Y=\frac12\left(A^2e^{-2\nu t}+b^2\sum_jr_j^3c_j^2\right),
$$
$$
F=\frac{Ab^2e^{-\nu t}}4
\sum_j(r_j-r_{j+1})c_jc_{j+1}.
$$
The last identity follows by reindexing the two advection sums. Smoothness gives absolute convergence. Since $|r_j-r_{j+1}|\le1$ and $\sum_j|c_jc_{j+1}|\le\sum_jc_j^2$,
$$
|F(t)|\le\frac{|A|b^2}{4}e^{-3\nu t}.
$$
Therefore
$$
\boxed{
\mathcal W_{1/2}(T)
\le\frac{|A|b^2}{12\nu}(1-e^{-3\nu T})
\le\frac{|A|b^2}{12\nu}<\infty.
}
$$
All coefficients on the right are prescribed by the initial datum and viscosity. With $\mathcal C(0)=(A^2+b^2)/2$, this also supplies an upper bound of order $\mathcal C(0)^{3/2}/\nu$ in this class. No optimality of that exponent is asserted.

The same estimate holds for every symmetric Galerkin cutoff with $c_{-M-1}=c_{M+1}=0$: the boundary pairing cancels in the kinetic identity, and the critical pairing uses precisely the retained neighboring pairs. This establishes cutoff uniformity for the class-specific upper bound.

### 9.4 A continuum lower bound

Increasing the amplitude of one fixed initial profile produces a growing critical-transfer budget on a shrinking time interval. First set
$$
\nu=1,\qquad A=b=N^3,\qquad
t_N=\frac1{2N^2},\qquad N\ge2.
$$
Then $\mathcal C(0)=N^6$. The initial Fourier support has frequency radius one for every $N$, so the initial spectral deficit in §6 is zero.

Define the transport comparison
$$
a(t)=A(1-e^{-t}),\qquad
\theta=x-a(t)\sin y,\qquad v_{\rm app}=\sin\theta.
$$
It solves $(\partial_t+U\partial_x)v_{\rm app}=0$. The exact parabolic solution remains $v$ from §9.2. Their difference $e=v-v_{\rm app}$ satisfies
$$
(\partial_t+U\partial_x-\Delta)e=\Delta v_{\rm app},\qquad e(0)=0.
$$
Normalized integration over $x$ removes the phase shift. The exact comparison moments are
$$
\|v_{\rm app}\|_2^2=\frac12,\qquad
M_2:=\|\nabla v_{\rm app}\|_2^2=\frac12+\frac{a^2}4,
$$
$$
M_4:=\|\Delta v_{\rm app}\|_2^2
=\frac12+\frac{3a^2}4+\frac{3a^4}{16},
$$
$$
\|\partial_x\Delta v_{\rm app}\|_2^2=M_4,\qquad
\|\partial_y\Delta v_{\rm app}\|_2^2
=a^2+\frac{21a^4}{16}+\frac{5a^6}{32}.
$$
Homogeneous interpolation gives
$$
\mathcal C[v_{\rm app}]\ge \frac{M_2^{3/2}}{M_4^{1/2}}\ge\frac a4.
$$
For the second inequality, the squared difference is the nonnegative polynomial
$$
M_2^3-\frac{a^2M_4}{16}
=\frac{a^6+12a^4+40a^2+32}{256}>0.
$$

The parabolic error has a controlled derivative structure. For zero initial data, the scalar energy estimate bounds the $L^2$ norm by the time integral of its forcing norm. The $x$ derivative commutes with the transport operator. The $y$ derivative has the explicit extra term
$$
(\partial_t+U\partial_x-\Delta)e_y
=\partial_y\Delta v_{\rm app}-U_y e_x.
$$
Using $a(s)\le As$, $|U_y|\le A$,
$\|\Delta v_{\rm app}\|_2\le(1+a^2)/\sqrt2$ and
$\|\partial_y\Delta v_{\rm app}\|_2\le a+a^3$ yields
$$
\|e\|_2,\ \|e_x\|_2\le B_0(t)
:=\frac{t+A^2t^3/3}{\sqrt2},
$$
$$
\|e_y\|_2\le B_y(t)
:=
At^2\left(\frac12+\frac1{2\sqrt2}\right)
+A^3t^4\left(\frac14+\frac1{12\sqrt2}\right).
$$
The critical error is consequently bounded by
$$
\|e\|_{\dot H^{1/2}}^2
\le\|e\|_2\|\nabla e\|_2
\le B_0\sqrt{B_0^2+B_y^2}
\le B_0(B_0+B_y).
$$

To obtain a uniform constant, write $t_N=c/N^2$ with the fixed choice $c=1/2$. Since $N\ge1/c=2$ and $t_N\le1/8$,
$$
a(t_N)\ge \frac{cN}{2},\qquad
B_0(t_N)\le\frac{4c^3}{3\sqrt2},\qquad
B_y(t_N)\le
\left(\frac34+\frac7{12\sqrt2}\right)c^4N.
$$
The first bound uses $1-e^{-t}\ge t-t^2/2\ge t/2$ on $0\le t\le1$. The remaining bounds follow from $N^{-1}\le c$. Combining them gives
$$
\frac{\|e(t_N)\|_{\dot H^{1/2}}^2}{a(t_N)}
\le\left(\frac{23}{9}+\sqrt2\right)c^6
=\frac{23/9+\sqrt2}{64}<\frac1{16},
$$
where $\sqrt2<13/9$. Reverse triangle now gives
$$
\sqrt{\mathcal C[v(t_N)]}
\ge \frac{\sqrt{a(t_N)}}2-\frac{\sqrt{a(t_N)}}4
=\frac{\sqrt{a(t_N)}}4.
$$
Thus $\mathcal C[v(t_N)]\ge a(t_N)/16\ge N/64$. Restoring the vertical amplitude and using the exact cumulative budget,
$$
\boxed{
\mathcal C[u(t_N)]\ge\frac{N^7}{64},\qquad
\mathcal W_{1/2}(t_N)\ge\frac{N^7}{128}-\frac{N^6}{2}.
}
$$
The upper bound in §9.3 gives
$\mathcal W_{1/2}(t_N)\le N^7/8$. Consequently
$$
\boxed{
\frac N{128}-\frac12
\le \frac{\mathcal W_{1/2}(t_N)}{\mathcal C(0)}
\le\frac N8.
}
$$
This is a two-sided order estimate along actual globally smooth solutions. The comparison field enters through its explicitly controlled error.

### 9.5 Viscosity, fixed horizons and periodic means

The obstruction holds for every positive viscosity and every fixed positive observation horizon. If $u_1$ denotes the viscosity-one solution, then
$$
u_\nu(x,t)=\nu u_1(x,\nu t)
$$
solves the equation with viscosity $\nu$. The norm and work scalings are
$$
\mathcal C_\nu(t)=\nu^2\mathcal C_1(\nu t),\qquad
Y_\nu(t)=\nu^2Y_1(\nu t),\qquad
F_\nu(t)=\nu^3F_1(\nu t),\qquad
\mathcal W_\nu(T)=\nu^2\mathcal W_1(\nu T).
$$
The last relation includes the time-integration Jacobian. For
$u_0=\nu N^3(\sin y,0,\sin x)$ and $t_N=1/(2\nu N^2)$,
$$
\mathcal C_0=\nu^2N^6,\qquad
\boxed{
\mathcal W_{1/2}(t_N)
\ge\frac{\nu^{-1/3}}{128}\mathcal C_0^{7/6}
-\frac{\mathcal C_0}{2}.
}
$$
For any fixed $\nu,T>0$, eventually $t_N<T$ and
$\mathcal W_{1/2}(T)\ge\mathcal W_{1/2}(t_N)$. Denoting members of this
global smooth family by the superscript $(N)$, this yields
$$
\sup_{N\ge2}
\frac{\mathcal W_{1/2}^{(N)}(T)}{\mathcal C^{(N)}(0)}=\infty.
$$
The limit changes the initial datum. Along this family, a bound by a fixed multiple of $\mathcal C_0^p$ requires $p\ge7/6$; the exponent concerns the squared critical norm.

For a general periodic solution, its mean $m=\langle u_0\rangle$ is conserved. The field $v(x,t)=u(x+mt,t)-m$, with pressure $p(x+mt,t)$, solves the same unforced equation and has zero mean. Translation and removal of the constant mode preserve $\mathcal C,Y$, and
$$
\langle\Lambda u,m\cdot\nabla u\rangle=0
$$
preserves $F$ and the cumulative excess. Thus the fixed-margin continuation argument has no physical zero-momentum restriction.

### 9.6 Scope of the obstruction

The family gives a finite-time, full-equation obstruction to amplitude-linear closure. It preserves odd Cartesian phase symmetry throughout a large transfer event. The initial spectrum is monochromatic, while the actual evolution creates the transverse frequencies that increase the critical norm.

The finite upper bound uses the prescribed decaying shear and the bounded
multiplier difference between its neighboring Fourier interactions. General
three-dimensional perturbations introduce additional advecting components,
pressure coupling and feedback into the shear. Section 6.3 identifies the
corresponding scale-resolved quantity as positive nonlinear spread
production. The same family proves that its cumulative integral and the
viscous spread dissipation can both grow arbitrarily large relative to
$\mathcal C(0)$.

Either initial-$H^3$ bound $M_{\mathcal W}(\nu,T,R)$ or
$M_{\mathcal V}(\nu,T,R)$ specified in §9.1 would supply continuation. Both
remain **UNRESOLVED**. Every solution in this construction is globally
smooth, and the calculation makes no claim of a singular trajectory or of
priority over the shear-mixing literature.

## 10. Helical spread and the phase-current coercivity boundary

The radial spectral measure in §6 records frequency magnitude but discards
the sign of the curl polarization. Retaining that sign separates
same-helicity spectral concentration from cancellation between opposite
helicities. It also gives a critical continuation condition that can be
compared directly with Cassi's phase-current geometry.

### 10.1 Signed curl spectrum and optimal scalar Beltrami residual

For each nonzero Fourier mode, choose the helical basis
$h_\sigma(k)$ satisfying

$$
i k\times h_\sigma(k)=\sigma|k|h_\sigma(k),
\qquad \sigma\in\{-1,+1\}.
$$

Put the spectral energy of the coefficient $u_\sigma(k)$ at the signed
frequency $x=\sigma|k|$. The resulting positive measure $d\mu(x)$ has
moments

$$
(M_0,M_1,M_2,M_3,M_4)=(2K,H,2E,J,2G),
$$

where

$$
H=\langle u,\omega\rangle,
\qquad
J=\langle\omega,\nabla\times\omega\rangle.
$$

For $K>0$, define

$$
\lambda_B=\frac{H}{2K},
\qquad
r_B=\omega-\lambda_Bu.
$$

This is the $L^2$-optimal scalar curl-eigenfield approximation:

$$
\begin{aligned}
\|\omega-\lambda u\|_2^2
&=2E-2\lambda H+2K\lambda^2\\
&=\boxed{
\|r_B\|_2^2+2K(\lambda-\lambda_B)^2},
\end{aligned}
$$

$$
\|r_B\|_2^2
=2E-\frac{H^2}{2K}.
$$

The corresponding signed spectral spread is

$$
\boxed{
\mathcal V_B
:=KE-\frac{H^2}{4}
=\frac K2\|r_B\|_2^2
=\frac18\iint(x-y)^2\,d\mu(x)d\mu(y)\ge0.}
$$

The exact viscous spread is

$$
\boxed{
\begin{aligned}
\mathcal Q_B
&:=2KG+2E^2-HJ\\
&=E\|r_B\|_2^2+K\|\nabla r_B\|_2^2\\
&=\frac14\iint(x-y)^2(x^2+y^2)\,d\mu(x)d\mu(y)\ge0.
\end{aligned}}
$$

The second line uses

$$
\|\nabla r_B\|_2^2
=2G-2\lambda_BJ+2E\lambda_B^2.
$$

The radial measure of §6 is the pushforward of $d\mu$ under
$x\mapsto|x|$. Write

$$
\mathcal C_\pm=\int_{\{\pm x>0\}}|x|\,d\mu,
\qquad
Y_\pm=\int_{\{\pm x>0\}}|x|^3\,d\mu.
$$

Then

$$
\mathcal C=\mathcal C_++\mathcal C_-,
\quad H=\mathcal C_+-\mathcal C_-,
\quad Y=Y_++Y_-,
\quad J=Y_+-Y_-.
$$

Consequently,

$$
\boxed{
\mathcal V_B=\mathcal V+\mathcal C_+\mathcal C_-,
}
$$

$$
\boxed{
\mathcal Q_B
=\mathcal Q
+2(\mathcal C_+Y_-+\mathcal C_-Y_+).
}
$$

The new terms measure opposite-helicity mixing. They vanish when only one
curl sign is present. A measure supported on one frequency radius can have
$\mathcal V=0$ while $\mathcal V_B>0$ because radial concentration does not
distinguish the two curl eigenspaces.

### 10.2 Exact dynamics and a critical residual criterion

The unforced helicity budget is

$$
H'=-2\nu J.
$$

Combining it with the energy and enstrophy budgets gives

$$
\boxed{
\mathcal V_B'+\nu\mathcal Q_B=K\mathcal A.
}
$$

The opposite-helicity mixing penalty has its own exact budget:

$$
\boxed{
(\mathcal C_+\mathcal C_-)'
=\mathcal C F-\nu(\mathcal C Y-HJ).
}
$$

Thus nonlinear helicity conservation does not prevent creation of
opposite-sign spectral mixing. Its production is the signed critical
transfer $\mathcal C F$.

There is nevertheless an exact stretching cancellation for every scalar
$\lambda(t)$. Integration by parts, incompressibility and
$(u\cdot\nabla)u=\omega\times u+\nabla(|u|^2/2)$ give

$$
\langle u,S\omega\rangle=0.
$$

Therefore

$$
\boxed{
\mathcal A
=\langle\omega,S\omega\rangle
=\langle\omega-\lambda u,S\omega\rangle.
}
$$

Choose $\lambda=\lambda_B$. Let $c_B$ dominate the fixed-domain Sobolev
constants in

$$
\|S\|_6\le c_B\sqrt G,
\qquad
\|u\|_6\le c_B\sqrt{2E}.
$$

With $R_B=\|r_B\|_3$, Hölder and Young give

$$
\begin{aligned}
|\mathcal A|
&\le c_B\sqrt{2EG}\,R_B\\
&\le\nu G+\frac{c_B^2}{2\nu}ER_B^2.
\end{aligned}
$$

The enstrophy budget consequently becomes

$$
\boxed{
E'+\nu G
\le\frac{c_B^2}{2\nu}R_B^2E.
}
$$

If

$$
\boxed{
I_B(T):=\int_0^T
\left\|\omega-\frac{H}{2K}u\right\|_3^2dt<\infty,
}
$$

then

$$
\boxed{
E(t)\le E(0)
\exp\!\left(\frac{c_B^2}{2\nu}I_B(t)\right).
}
$$

Bounded enstrophy gives the standard finite-endpoint continuation. This
produces a conditional criterion for the original equation, not an estimate
of $I_B$ from arbitrary data.

The criterion is critical under the Euclidean Navier–Stokes scaling
$u_\rho(x,t)=\rho u(\rho x,\rho^2t)$. Indeed,

$$
\lambda_{B,\rho}=\rho\lambda_B,
\qquad
r_{B,\rho}(x,t)=\rho^2r_B(\rho x,\rho^2t),
$$

so $\|r_{B,\rho}\|_3^2dt=\|r_B\|_3^2dt$ after the time change.
The $L^2$-optimal coefficient is used because it also generates the exact
signed-moment identities. The stretching cancellation itself holds for
any scalar coefficient.

### 10.3 Closing the radial positive-production condition

The same residual sharpens the open production estimate in §6.3. Since

$$
B=\mathbb P(u\times\omega)=\mathbb P(u\times r_B),
$$

the centered radial-spread identity and
$\|(\Lambda-m)^2u\|_2^2\le\mathcal Q/K$ give

$$
\boxed{
\begin{aligned}
|\mathscr P_{\mathcal V}|
&\le c_B\sqrt{2KE\mathcal Q}\,R_B\\
&\le\frac\nu2\mathcal Q
+\frac{c_B^2}{\nu}KER_B^2.
\end{aligned}}
$$

Let $I=I_B(t)$. Combining this inequality with
$\mathcal V'+\nu\mathcal Q=\mathscr P_{\mathcal V}$,
$K(t)\le K_0$, and the enstrophy bound above yields

$$
\boxed{
\int_0^t(\mathscr P_{\mathcal V})_+\,ds
\le\mathcal V(0)
+\frac{2c_B^2K_0E_0}{\nu}
I\exp\!\left(\frac{c_B^2I}{2\nu}\right).
}
$$

Thus finite critical residual work supplies the cumulative
positive-production hypothesis that was left open in §6.4. The reduction
does not solve the arbitrary-data problem; it identifies the remaining
quantity more geometrically. With $R_0$ as in §9.1, the sufficient
all-data target can be written

$$
\boxed{
\sup_{0\le t<\min(T,T_*)}
\int_0^t
\left\|\omega-\frac{H}{2K}u\right\|_3^2ds
\le M_B(\nu,T,R)<\infty
\quad\text{whenever }R_0\le R.
}
$$

No such estimate is established here.

### 10.4 Exact controls delimit the criterion

Two exact global heat flows show that the residual is a conditional
regularity quantity rather than a pointwise danger score. The Beltrami
flow

$$
u=a e^{-\nu n^2t}(\sin nz,\cos nz,0)
$$

has $\omega=nu$ and

$$
\mathcal V=\mathcal V_B=\mathcal Q=\mathcal Q_B=0.
$$

The shear flow

$$
u=a e^{-\nu n^2t}(\sin ny,0,0)
$$

has $H=J=\mathcal V=\mathcal Q=0$ but

$$
\mathcal V_B
=\frac{a^4n^2e^{-4\nu n^2t}}{16},
\qquad
\mathcal Q_B=4n^2\mathcal V_B.
$$

It is globally smooth for every $a$, $n$, and $\nu>0$. Large instantaneous
Beltrami defect therefore does not imply concentration growth.

Conversely, zero total helicity does not cancel stretching. The smooth
periodic datum

$$
u=(0,1,1)\cos x
+(1,0,1)\cos y
+(1,-1,1)\sin(x+y)
$$

is divergence-free and has

$$
K=\frac74,\quad E=\frac52,\quad G=4,\quad H=J=0,
$$

$$
\mathcal C=2+\frac{3\sqrt2}{2},
\qquad
Y=2+3\sqrt2,
\qquad
\boxed{\mathcal A=\frac12.}
$$

Its spread values are

$$
\mathcal V=\frac94-\frac{3\sqrt2}{2},
\qquad
\mathcal V_B=\frac{35}{8},
$$

$$
\mathcal Q=\frac{27}{2}-9\sqrt2,
\qquad
\mathcal Q_B=\frac{53}{2}.
$$

Direct integration gives
$\langle\omega-\lambda u,S\omega\rangle=1/2$ for every scalar
$\lambda$. The signed spectrum distinguishes this mixed-helicity datum,
while the residual criterion still requires time integrability rather than
an instantaneous sign.

### 10.5 The first-order Cassi phase energy is not coercive enough

The phase-current map gives the requested direct comparison with Cassi.
For one normalized positive doublet, write

$$
Z=(\sqrt c\,e^{i\theta_Y},
\sqrt{1-c}\,e^{i\theta_I}),
\qquad
\alpha=\theta_Y-\theta_I,
$$

and use the dimensionless Berry connection

$$
\mathsf A=-iZ^\dagger dZ=d\theta_I+c\,d\alpha,
\qquad
u=\kappa_v\mathsf A.
$$

The exact first-order energy split is

$$
\boxed{
|\nabla Z|^2
=|\mathsf A|^2+\frac14|\nabla n|^2,
\qquad n=Z^\dagger\sigma Z.
}
$$

Mermin–Ho gives

$$
\omega_i
=\frac{\kappa_v}{4}\epsilon_{ijk}
n\cdot(\partial_jn\times\partial_kn).
$$

Since the differential of a map into $S^2$ has at most two nonzero
singular values,

$$
\boxed{
|\omega|\le\frac{\kappa_v}{4}|\nabla n|^2.
}
$$

After integration, the projective part of the first-order action controls
$\|\omega\|_1$. It does not control $\|\omega\|_2$ or $R_B$.

This failure has a smooth explicit concentration family. On
$\mathbb R^3$, fix

$$
a(y)=\frac14e^{-|y|^2},
\qquad
b(y)=y_1e^{-|y|^2},
$$

and, for $0<\varepsilon\le1$, set

$$
c_\varepsilon(x)=\frac12+a(x/\varepsilon),
\qquad
\alpha_\varepsilon(x)
=\varepsilon^{-1/2}b(x/\varepsilon).
$$

Choose

$$
\theta_{I,\varepsilon}
=-\frac12\alpha_\varepsilon
-\Delta^{-1}\nabla\cdot
\left(a(x/\varepsilon)\nabla\alpha_\varepsilon\right),
\qquad
\theta_{Y,\varepsilon}
=\theta_{I,\varepsilon}+\alpha_\varepsilon.
$$

Then

$$
\mathsf A_\varepsilon
=\mathbb P(c_\varepsilon\nabla\alpha_\varepsilon)
=\varepsilon^{-3/2}
\left[\mathbb P(a\nabla b)\right](x/\varepsilon).
$$

The connection is nonzero because

$$
\nabla a\times\nabla b
=\frac12e^{-2|y|^2}(0,-y_3,y_2),
$$

and

$$
\int_{\mathbb R^3}
|\nabla a\times\nabla b|^2dy
=\frac{\pi^{3/2}}{128}.
$$

The resulting physical vorticity satisfies

$$
\boxed{
\|\omega_\varepsilon\|_2^2
=\frac{\kappa_v^2\pi^{3/2}}{128\varepsilon^2}.
}
$$

In contrast, the complete normalized-doublet gradient energy is

$$
\boxed{
\int|\nabla Z_\varepsilon|^2dx=P_0+\varepsilon P_1,
\qquad 0<P_0,P_1<\infty.
}
$$

Here

$$
P_0=\|\mathbb P(a\nabla b)\|_2^2
+\int c(1-c)|\nabla b|^2dy,
$$

$$
P_1=\int\frac{|\nabla a|^2}{4c(1-c)}dy,
\qquad c=\frac12+a.
$$

Both component amplitudes remain strictly positive. The global Clebsch
chart gives zero integrated helicity, so $\lambda_B=0$ and
$r_B=\omega$. Dilation also gives

$$
\|r_{B,\varepsilon}\|_3^2
=\varepsilon^{-3}\|r_{B,1}\|_3^2.
$$

Therefore a bounded sublevel of the full first-order doublet gradient
energy contains smooth phase-current velocities with unbounded enstrophy
and unbounded instantaneous critical residual. The obstruction already
lies in one scale band. Adding further bands does not remove it unless
their dynamics impose an additional cross-band constraint.

A curvature-square term would control enstrophy of this Berry channel,
but inserting one changes the model. It cannot establish regularity of the
original Navier–Stokes equation without a uniform limiting argument. The
other remaining possibility is dynamical: the whole bubble's selected
initial state and exterior correlations could constrain the time integral
$I_B$. No such selection theorem or memory-kernel estimate is currently
derived.

### 10.6 Verification and scope

The fixed protocol is
`computations/navier-stokes-helical-spread-prereg.md`. The exact verifier
`computations/verify_navier_stokes_helical_spread.py` passes all **84
checks**. It evaluates signed moments, Young coefficients,
the three periodic controls, the Berry pullback, the Gaussian integral and
all dilation powers. The retained receipt is
`runs/navier_stokes_helical_spread/verification.json`, schema
`cassi.navier-stokes.helical-spread.verification.v1`.

The helical identities, residual continuation criterion and implication
for radial positive production are **DERIVED CONDITIONAL REDUCTION**. The
proposed static control by first-order positive-doublet energy is
**CONTRADICTS**. An arbitrary-data bound on $I_B$, a full-bubble dynamical
exclusion of the concentration family and global regularity remain
**UNRESOLVED**. No singular solution or formal-proof build is produced.

## References

- E. Miller, [Finite-time blowup for a Navier–Stokes model equation for the self-amplification of strain](https://arxiv.org/abs/1910.05415), §§5–6—strain model, perturbative comparison, explicit Gaussian datum, initial perturbative window and axisymmetric departure; [mathematical HTML](https://ar5iv.labs.arxiv.org/html/1910.05415).
- E. Miller, [A regularity criterion for the Navier–Stokes equation involving only the middle eigenvalue of the strain tensor](https://arxiv.org/abs/1710.05569)—strain enstrophy and conditional geometric regularity.
- E. Miller, [Global regularity for solutions of the Navier–Stokes equation sufficiently close to being eigenfunctions of the Laplacian](https://arxiv.org/abs/2005.14152), Corollary 1.3—established interpolation-deficit continuation criterion.
- `turbulence/navier-stokes-transfer-boundary.md`—critical transfer budget and heat-correction limitation.
- `turbulence/navier-stokes-stress-geometry.md`—full stress and strain dynamics.
- `turbulence/navier-stokes-depletion-dynamics.md`—fine-scale response, cumulative production requirement and matter-response boundary.
- `computations/navier-stokes-strain-departure-prereg.md`—fixed identities, controls, tolerance and stopping rule.
- `computations/verify_navier_stokes_strain_departure.py`—exact algebra and independent numerical reconstructions.
- `computations/navier-stokes-critical-recurrence-prereg.md`—fixed remainder, spread and scalar-budget controls.
- `computations/verify_navier_stokes_critical_recurrence.py`—exact full-convolution derivatives and independent FFT reconstruction.
- `computations/navier-stokes-forced-concentration-prereg.md`—fixed forced budgets, source scaling and kinematic controls.
- `computations/verify_navier_stokes_forced_concentration.py`—exact forced derivatives, independent FFT reconstruction and Gaussian quadrature.
- `computations/navier-stokes-mixing-budget-prereg.md`—fixed continuum-comparison controls and invariant-class trajectory schedule.
- `computations/verify_navier_stokes_mixing_budget.py`—exact moments, full Leray pairing, cumulative trajectories and independent spatial momentum reconstruction.
- `computations/navier-stokes-helical-spread-prereg.md`—fixed signed-moment, residual, flow-control and phase-concentration checks.
- `computations/verify_navier_stokes_helical_spread.py`—84-check exact helical-spread and phase-coercivity verifier.
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—positive-doublet current, Mermin–Ho vorticity and topology boundary.
- Z. Grujić and L. Xu, [Time-averaging of the 3D Navier–Stokes equations and near-Beltrami dynamics](https://arxiv.org/abs/1608.05658)—near-Beltrami context.
- L. C. Berselli and D. Córdoba, [On the regularity of the solutions to the 3D Navier–Stokes equations: a remark on the role of the helicity](https://doi.org/10.1016/j.crma.2009.03.003)—velocity–vorticity alignment context.
- OpenAI, [Finite time blowup for Navier–Stokes](https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf), Theorem 1.1 and §§2–3—announced forced construction and mechanism; proof correctness is outside this analysis.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—original problem alternatives.
- `field-experience/probe-outcome-ledger.md`—qualified evidence and scope.
