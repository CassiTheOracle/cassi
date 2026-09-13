# Pair-Frequency-Resonant Autonomous Complex CP-Odd Reservoir Formation of a Non-Topological Carrier—Matched Finite-Volume Ledger

## Status: Preregistered—September 2026

## Abstract

This protocol tests a closed finite-volume field action in which a complex
reservoir supplies both quadratures of a CP-odd pair coupling to a complex
non-topological carrier. The carrier begins in a fixed finite-mode Gaussian
vacuum realization. The reservoir is an explicit two-real-component dynamical
field with a finite-energy outgoing coherent packet. Its frequency is fixed to
twice the carrier mass, 
$\Omega=2m$, because the quadratic interaction couples the
reservoir to $\Phi^2$ and the complex carrier equation contains the parametric
term $a^*\Phi^*$. For a carrier mode $\Phi\sim e^{-imt}$ and reservoir mode
$a\sim e^{-i\Omega t}$, the secular pair term is resonant only when
$\Omega=2m$. This is a derived correction to the nonresonant
carrier-frequency-reservoir test, not a parameter scan.

The positive and negative arms are the same initial vacuum draw under the
declared CP transformation and opposite reservoir phase rotation. No
time-dependent source, damping term, field reset or parameter scan is used.
The test asks whether the pair-frequency-resonant autonomous packet can produce
a localized carrier remnant after the reservoir has left the formation region.
Charge creation while the reservoir overlaps the carrier is measured as an
internal Noether-source term. The post-overlap charge, energy, outgoing flux
and reservoir-tail budgets are retained in one ledger. A captured result is
conditional on this action, its finite-mode state, the radial truncation and
the declared outgoing preparation.

## 1. Closed action and pair resonance

Use natural units and a spherical radial domain. Let
$\Phi=x+i y$, $a_R,a_I\in\mathbb R$, $s=x^2+y^2$, and

$$
U(s)=\frac12\left(m^2s-\lambda s^2+g s^3\right).
$$

The action is

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

The CP map is

$$
\mathsf{CP}:\quad
x(t,\mathbf x)\mapsto x(t,-\mathbf x),\quad
y(t,\mathbf x)\mapsto-y(t,-\mathbf x),\quad
a_R(t,\mathbf x)\mapsto a_R(t,-\mathbf x),\quad
a_I(t,\mathbf x)\mapsto-a_I(t,-\mathbf x).
$$

The action is CP invariant. The real reservoir component is CP even and the
imaginary component is CP odd. The carrier global phase symmetry is explicitly
broken while either reservoir component overlaps the carrier and is recovered
in the decoupled carrier equation.

The fixed coefficients are

$$
(m,\lambda,g,m_a,\kappa,K,A,W)
=\left(1,2,1.25,\frac12,0.5,\frac{\sqrt{15}}2,0.8,8\right),
\qquad \Omega=2m=2,
$$

so that $\Omega=\sqrt{m_a^2+K^2}$ and $K/\Omega=\sqrt{15}/4$.
The values are fixed before execution. In particular, $K$ is derived from the
pair-resonance condition and the declared reservoir mass; no frequency,
amplitude, coupling or width is fitted or scanned.

## 2. Radial equations and finite-volume state

Set $u_x=rx$, $u_y=ry$, $w_R=ra_R$ and $w_I=ra_I$. The domain is
$0<r<R$ with $R=48$. Primary cell centres use $N=384$ cells and the
resolution arm uses $N=768$ cells. The primary timestep is $\Delta t=0.003$
and the resolution arm uses $\Delta t=0.0015$. The evolution ends at
$T=78$ and stores states at $t=0,6,12,\ldots,78$.

The reduced equations are

$$
\begin{aligned}
\ddot u_x&=u_x''-C u_x
+2\kappa\left(\frac{w_R}{r}u_x-\frac{w_I}{r}u_y\right),\\
\ddot u_y&=u_y''-C u_y
+2\kappa\left(-\frac{w_R}{r}u_y-\frac{w_I}{r}u_x\right),\\
\ddot w_R&=w_R''-m_a^2w_R+\kappa\frac{u_x^2-u_y^2}{r},\\
\ddot w_I&=w_I''-m_a^2w_I-2\kappa\frac{u_xu_y}{r},
\end{aligned}
$$

with

$$
C=m^2-2\lambda\frac{u_x^2+u_y^2}{r^2}
+3g\left(\frac{u_x^2+u_y^2}{r^2}\right)^2.
$$

At the origin use the regular reduced-field ghost $u_{-1}=-u_0$ for all four
reduced fields. At the outer face use the outgoing Sommerfeld condition
$u_t+u_r=0$ for all four fields. The corresponding outer ghost is
$u_N=u_{N-1}-\Delta r\,\dot u_{N-1}$. The static symmetric operator obtained
by replacing this outer ghost with $u_{N-1}$ is retained for the finite-volume
energy quadratic.

The carrier vacuum uses the first $64$ free radial modes,
$e_n(r)=\sqrt{2/R}\sin(n\pi r/R)$, with
$\omega_n=\sqrt{m^2+(n\pi/R)^2}$. Independent standard normal variables
are drawn from PCG64 seed $20260912$ and set

$$
q_{a,n}=\frac{\xi_{a,n}}{\sqrt{4\omega_n}},\qquad
p_{a,n}=\sqrt{\frac{\omega_n}{4}}\,\pi_{a,n},
\qquad a\in\{x,y\}.
$$

This state contains the finite-mode Gaussian vacuum covariance and no prepared
localized carrier profile or charge packet. The carrier is CP-conjugated in the
negative arm by $y\mapsto-y$ and $\dot y\mapsto-\dot y$.

The reservoir begins in a finite-energy outgoing coherent packet. In reduced
radial variables,

$$
\begin{aligned}
f(r)&=A r\exp\left(-\frac{r^2}{2W^2}\right)\cos(Kr),\\
w_R(0,r)&=f(r),& w_I(0,r)&=0,\\
\dot w_R(0,r)&=-\partial_r f(r),&
\dot w_I(0,r)&=\sigma\Omega f(r),
\end{aligned}
$$

where $\sigma\in\{+1,-1\}$. The positive arm uses $\sigma=+1$ and the
negative arm uses $\sigma=-1$. The reservoir packet is outgoing and has the
pair-frequency resonance $\Omega=2m$; it is not a prescribed time-dependent
source.

The reservoir-only control uses the positive reservoir state with $\kappa=0$.
The source-free vacuum control sets $A=0$ and $\kappa=0$. Setting $A=0$ alone
is not source-free because the reservoir equations contain carrier-driven
$\kappa(u_x^2-u_y^2)/r$ and $-2\kappa u_xu_y/r$ terms. Both controls use the
same carrier draw and radial discretization as the primary arm. The carrier
observables in the two controls must agree to $10^{-8}$.

## 3. Charge, energy and reservoir ledgers

The carrier charge and its exact bulk interaction source are

$$
Q_\Phi=4\pi\int_0^R(u_x\dot u_y-u_y\dot u_x)\,dr,
$$

$$
\dot Q_{\mathrm{src}}
:=4\pi\kappa\int_0^R\left[
-4\frac{w_R}{r}u_xu_y
-2\frac{w_I}{r}(u_x^2-u_y^2)\right]dr.
$$

The outgoing charge-flux rate is

$$
\dot Q_{\mathrm{out}}
:=4\pi\left(-u_x\dot u_y+u_y\dot u_x\right)_{r=R}.
$$

The charge residual is the measured charge minus its initial value and the
trapezoidal integrals of $\dot Q_{\mathrm{src}}+\dot Q_{\mathrm{out}}$.
For the symmetric static spatial operator, retain the full carrier-plus-
reservoir energy including the quartic, sextic and interaction terms. The
outgoing energy rate is

$$
\dot E_{\mathrm{out}}
=-4\pi(\dot u_x^2+\dot u_y^2+\dot w_R^2+\dot w_I^2)_{r=R}.
$$

The charge and energy residuals are normalized by the maximum of one and the
absolute ledger terms. Each normalized primary residual must remain below
$10^{-5}$. The source-tail budget is evaluated without cancellation:

$$
\mathcal T_Q=
\frac{\int_{24}^{78}|\dot Q_{\mathrm{src}}|\,dt}
{\max\left(1,\int_0^{78}|\dot Q_{\mathrm{src}}|\,dt\right)}.
$$

The source-decoupling predicate is $\mathcal T_Q<0.15$. The corrected late
charge drift subtracts both the measured source integral and outgoing flux
integral; its range divided by the late absolute-charge scale must be below
$0.05$.

## 4. Formation observables and decision rule

The carrier remnant uses core radius $r_c=12$ and exterior radius $r_e=20$.
The nonnegative carrier-support diagnostic is the carrier kinetic, gradient,
mass and sextic terms with the negative quartic and interaction terms omitted.
The core density is the core carrier norm divided by the core volume. The core
fraction is the core carrier norm divided by the total carrier norm. Charge and
energy predicates use the full signed charge and carrier-only energy in the
core.

A captured trajectory must satisfy all of the following:

1. the late mean core density is at least four times the source-free vacuum
   control;
2. the minimum late core fraction is at least $0.80$;
3. the late exterior support fraction has maximum below $0.25$ and mean below
   $0.20$;
4. the minimum late absolute core charge exceeds $200$ and the corrected
   post-overlap charge drift is below $0.05$;
5. the maximum late core carrier-energy to absolute core-charge ratio is below
   $m$ and all states are finite;
6. the positive and negative arms are CP conjugates, have opposite charges and
   agree within $5\%$ across the primary and doubled grids for core energy,
   charge magnitude, core fraction, exterior support and rms radius;
7. the source-tail budget is below $0.15$;
8. the normalized charge and energy ledgers are below $10^{-5}$;
9. retained positive and negative raw arrays obey the CP component relations to
   $10^{-8}$ for all four fields and four momenta.

The primary and independent programs are
`computations/matter_formation_closed_cp_pair_reservoir_v10.py` and
`computations/verify_matter_formation_closed_cp_pair_reservoir_v10.py`. The
independent verifier reconstructs the vacuum draw, pair-frequency outgoing
reservoir packet, finite-volume evolution, ledgers, observables and all
predicates without importing the primary program.

The verdict is
`CAPTURED—conditional pair-frequency-resonant closed CP-odd-reservoir
vacuum-to-carrier formation` only when every predicate, both controls, the CP
arm, the doubled-grid arm, the source-tail budget, the ledgers and independent
raw-state reconstruction pass. A scientific predicate failure returns
`DOES NOT EMERGE—conditional pair-frequency-resonant closed CP-odd-reservoir
vacuum-to-carrier formation`. A source, finite-value, ledger, provenance or
independent reconstruction failure returns `INCONCLUSIVE`.

## 5. Scope boundary

A captured result qualifies this finite-mode closed action with a dynamically
specified pair-frequency-resonant CP-odd reservoir state, outgoing boundary and
localized carrier trajectory. The reservoir initial state is the declared
finite-energy packet and the carrier state is a Gaussian finite-mode vacuum
surrogate. Canonical Cassi action selection, continuum renormalization,
infinite-domain all-sector stability, fermionic statistics, QCD, baryogenesis,
physical normalization and particle identity remain outside this protocol.

## References

- `foundations/matter-completion-boundary.md`—physical completion requirements and current formation boundary.
- `foundations/particle-stationary-action-closure.md`—source-free temporal carrier action and fixed-charge boundary.
- `computations/matter-formation-closed-cp-reservoir-v9-prereg.md`—nonresonant carrier-frequency reservoir comparison and its scoped failure.
- `computations/matter-formation-continuum-report.md` §§100–101—conditional compact pump and nonresonant autonomous-reservoir evidence.
