# Pair-Frequency-Resonant Incoming-Shell Reservoir Formation of a Non-Topological Carrier—Matched Finite-Volume Ledger

## Status: Preregistered—September 2026

## Abstract

This protocol tests whether a finite-energy reservoir shell arriving from the
bubble interior can convert a finite-mode vacuum draw into a localized charged
carrier. It keeps the closed CP-odd action and the derived pair-frequency
condition from v10: the carrier interaction is quadratic in $\Phi$, so the
reservoir frequency is fixed to $\Omega=2m$ rather than fitted to a carrier
frequency. The new initial condition is an incoming, radially converging
reservoir shell centred at $r_0=16$, with width $W=6$. Its reduced radial
momentum is $+\partial_r f$, the incoming Sommerfeld sign; v10 used
$-\partial_r f$ for an outgoing packet launched at the origin.

The shell reaches the origin at the declared group-velocity estimate
$t_\mathrm{hit}=r_0/(K/\Omega)$ and then leaves through the outgoing boundary.
The formation window is fixed before execution at $0\le t\le78$, with the
source-tail checkpoint at $t=30$. No time-dependent source, damping term,
field reset, parameter scan or prepared carrier profile is used. The positive
and negative arms use the same Gaussian carrier vacuum draw and opposite
CP-odd reservoir quadrature. The question is whether the finite shell's
collision/focusing supplies the missing production impulse while leaving a
localized remnant after the shell has passed.

## 1. Closed action and pair resonance

Let $\Phi=x+i y$, $a_R,a_I\in\mathbb R$, $s=x^2+y^2$, and

$$
U(s)=\frac12\left(m^2s-\lambda s^2+g s^3\right).
$$

Use the closed action

$$
\begin{aligned}
S=\int d^4x\Big[&
\frac12\partial_\mu x\partial^\mu x
+\frac12\partial_\mu y\partial^\mu y
+\frac12\partial_\mu a_R\partial^\mu a_R
+\frac12\partial_\mu a_I\partial^\mu a_I
-U(s)-\frac12m_a^2(a_R^2+a_I^2)\\
&+\kappa a_R(x^2-y^2)-2\kappa a_Ixy\Big].
\end{aligned}
$$

The action is invariant under

$$
\mathsf{CP}:
(x,y,a_R,a_I)(t,\mathbf x)\mapsto
(x,-y,a_R,-a_I)(t,-\mathbf x).
$$

Writing the carrier equation in complex form exposes the interaction term
$a^*\Phi^*$. With $\Phi\sim e^{-imt}$ and $a\sim e^{-i\Omega t}$,
the secular term has phase $e^{-i(\Omega-m)t}$ in the conjugate carrier
channel and is resonant with $e^{-imt}$ only for $\Omega=2m$. Freeze

$$
(m,\lambda,g,m_a,\kappa,K,A,W,r_0)
=\left(1,2,1.25,\frac12,0.5,\frac{\sqrt{15}}2,0.8,6,16\right),
\qquad \Omega=2m=2.
$$

Thus $\Omega=\sqrt{m_a^2+K^2}$ and the packet group velocity is
$K/\Omega=\sqrt{15}/4$. All coefficients are fixed before execution and no
scan over shell centre, width, amplitude, frequency or coupling is permitted.

## 2. Radial equations and incoming shell

Set $u_x=rx$, $u_y=ry$, $w_R=ra_R$ and $w_I=ra_I$ on $0<r<R$ with
$R=48$. Use $N=384$, $\Delta t=0.003$ for the primary and
$N=768$, $\Delta t=0.0015$ for the doubled-grid arm. End at $T=78$ and
store $t=0,6,12,\ldots,78$. The reduced equations are

$$
\begin{aligned}
\ddot u_x&=u_x''-C u_x+2\kappa\left(\frac{w_R}{r}u_x-\frac{w_I}{r}u_y\right),\\
\ddot u_y&=u_y''-C u_y+2\kappa\left(-\frac{w_R}{r}u_y-\frac{w_I}{r}u_x\right),\\
\ddot w_R&=w_R''-m_a^2w_R+\kappa\frac{u_x^2-u_y^2}{r},\\
\ddot w_I&=w_I''-m_a^2w_I-2\kappa\frac{u_xu_y}{r},
\end{aligned}
$$

where

$$
C=m^2-2\lambda\frac{u_x^2+u_y^2}{r^2}
+3g\left(\frac{u_x^2+u_y^2}{r^2}\right)^2.
$$

Use the regular ghost $u_{-1}=-u_0$ at the origin and the outgoing
Sommerfeld ghost $u_N=u_{N-1}-\Delta r\,\dot u_{N-1}$ at the outer face.
The symmetric static outer ghost is used only in the energy quadratic.

The carrier begins in the first 64 free radial modes with PCG64 seed
$20260912$:

$$
q_{a,n}=\frac{\xi_{a,n}}{\sqrt{4\omega_n}},\qquad
p_{a,n}=\sqrt{\frac{\omega_n}{4}}\,\pi_{a,n},\qquad
\omega_n=\sqrt{m^2+(n\pi/R)^2}.
$$

The same draw is used in both CP arms; the negative arm maps $y,p_y$ to their
negatives. It contains no localized carrier profile or charge packet.

Define $\rho=r-r_0$, $g_0(r)=\exp[-\rho^2/(2W^2)]$ and
$h(r)=\cos(K\rho)$. The reduced incoming reservoir shell is

$$
 f(r)=A r g_0(r)h(r),\qquad
 f'(r)=A g_0(r)\left[h(r)-\frac{r\rho}{W^2}h(r)-rK\sin(K\rho)\right].
$$

For arm sign $\sigma\in\{+1,-1\}$ set

$$
 w_R(0,r)=f(r),\quad w_I(0,r)=0,\quad
 \dot w_R(0,r)=+f'(r),\quad
 \dot w_I(0,r)=\sigma\Omega f(r).
$$

The plus sign on $\dot w_R$ is the incoming radial Sommerfeld sign. The
reservoir-only control uses the positive shell with $\kappa=0$. The source-free
control sets both $A=0$ and $\kappa=0$; $A=0$ alone is not source-free because
carrier-driven reservoir equations would remain. Controls share the carrier
draw and grid and must agree in carrier observables to $10^{-8}$.

## 3. Ledgers and fixed windows

Use

$$
Q_\Phi=4\pi\int_0^R(u_x\dot u_y-u_y\dot u_x)\,dr,
$$

$$
\dot Q_{\mathrm{src}}=4\pi\kappa\int_0^R
\left[-4\frac{w_R}{r}u_xu_y-2\frac{w_I}{r}(u_x^2-u_y^2)\right]dr,
$$

and

$$
\dot Q_{\mathrm{out}}=4\pi(-u_x\dot u_y+u_y\dot u_x)_{r=R}.
$$

The energy is the symmetric finite-volume carrier-plus-reservoir Hamiltonian
with the quartic, sextic and interaction terms. Its outer flux is

$$
\dot E_{\mathrm{out}}=-4\pi(\dot u_x^2+\dot u_y^2+\dot w_R^2+\dot w_I^2)_{r=R}.
$$

Integrate source and boundary rates by the trapezoidal rule. Every normalized
primary charge and energy residual must be below $10^{-5}$. The absolute source
tail is

$$
\mathcal T_Q=
\frac{\int_{30}^{78}|\dot Q_{\mathrm{src}}|dt}
{\max\left(1,\int_0^{78}|\dot Q_{\mathrm{src}}|dt\right)},
\qquad \mathcal T_Q<0.15.

To falsify a momentum-sign mistake, store the reduced-reservoir energy density

$$
e_R(r,t)=\frac12\left(\dot w_R^2+\dot w_I^2+
(\partial_r w_R)^2+(\partial_r w_I)^2+
m_a^2(w_R^2+w_I^2)\right)
$$

and its centroid

$$
C_R(t)=\frac{\int_0^R r e_R(r,t)\,dr}{\int_0^R e_R(r,t)\,dr}.
$$

The initial shell centroid must lie in $14\le C_R(0)\le18$. The incoming
characteristic must reach the core before the source-tail checkpoint:
$\min_{0\le t\le30}C_R(t)\le8$. This diagnostic is measured from every
stored checkpoint and is a required scientific predicate; an outgoing or
static shell fails it even if the other ledgers are finite.

The corrected late charge drift removes both source and outgoing-flux
integrals and must be below $0.05$ after normalization by the late absolute
charge scale. The late formation window is $60\le t\le78$.

## 4. Formation predicates and decision rule

Use core radius $r_c=12$ and exterior radius $r_e=20$. Core density is the
carrier norm divided by the core volume. Core fraction is core carrier norm
over total carrier norm. Exterior support uses nonnegative carrier kinetic,
gradient, mass and sextic terms, omitting negative quartic and interaction
terms. A captured trajectory must satisfy every predicate:

1. late mean core density is at least four times the source-free vacuum control;
2. minimum late core fraction is at least $0.80$;
3. maximum and mean late exterior support are below $0.25$ and $0.20$;
4. minimum late absolute core charge exceeds $200$ and corrected drift is below
   $0.05$;
5. maximum late core carrier-energy / absolute core-charge is below $m=1$;
6. positive and negative arms are CP conjugates, have opposite charge, and
   agree within $5\%$ for core energy, charge magnitude, fraction, support and
   rms radius across primary and doubled grids;
7. $\mathcal T_Q<0.15$;
8. normalized charge and energy ledgers are below $10^{-5}$;
9. the incoming-shell centroid starts in $[14,18]$ and reaches $C_R\le8$
   before $t=30$;
10. every retained raw field and momentum array obeys the CP relation to
   $10^{-8}$.

The primary and independent programs are
`computations/matter_formation_closed_cp_incoming_reservoir_v11.py` and
`computations/verify_matter_formation_closed_cp_incoming_reservoir_v11.py`.
The verifier reconstructs the finite-mode draw, incoming shell, evolution,
ledgers, raw arrays and predicates without importing the primary program.

The verdict is
`CAPTURED—conditional pair-frequency-resonant incoming-shell formation` only
when all controls and all ten predicates pass. Any scientific predicate
failure returns
`DOES NOT EMERGE—conditional pair-frequency-resonant incoming-shell formation`.
A finite-value, provenance, ledger, source or independent-reconstruction
failure returns `INCONCLUSIVE`.

## 5. Scope boundary

A captured result qualifies this finite-mode closed action, incoming shell,
finite-mode vacuum surrogate and radial outgoing boundary. It would still not
select the canonical Cassi action, a continuum-renormalized quantum state,
infinite-domain all-sector stability, physical normalization, fermionic
statistics, QCD, baryogenesis or particle identity.

## References

- `computations/matter-formation-closed-cp-pair-reservoir-v10-prereg.md`—pair-frequency outgoing-reservoir comparison and scoped failure.
- `computations/matter-formation-continuum-report.md` §§100–102—retained pump, outgoing-reservoir and pair-resonant evidence.
- `foundations/matter-completion-boundary.md`—physical completion requirements and current formation boundary.
