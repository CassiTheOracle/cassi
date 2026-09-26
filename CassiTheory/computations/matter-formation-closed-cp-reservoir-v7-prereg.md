# Finite-Mode Autonomous CP-Odd Pulse Formation of a Non-Topological Carrier—Matched Finite-Volume Ledger

## Status: Preregistered—September 2026

## Abstract

This protocol tests a closed finite-volume field action in which a complex
reservoir supplies both quadratures of a CP-odd pair coupling to a complex
non-topological carrier. The carrier begins in a fixed finite-mode Gaussian
vacuum realization. The reservoir is an explicit two-real-component
dynamical field prepared as a frozen finite-mode superposition whose free
evolution approximates the registered two-quadrature pulse over
$0\le t\le24$ and is suppressed after the pulse window. No time-dependent
source, damping term, field reset or parameter scan is used. The positive
and negative arms are the same initial draw under the declared CP
transformation.

The test asks whether this autonomous finite-mode packet can produce a
localized carrier remnant after the reservoir pulse has passed. Charge
creation while the reservoir overlaps the carrier is measured as an internal
Noether-source term. The post-overlap charge, energy, outgoing flux and
reservoir-tail budgets are retained in one ledger. A captured result is
conditional on this action, its finite-mode state, the radial truncation and
the frozen pulse-preparation objective.

## 1. Closed action and CP symmetry

Use natural units and a spherical radial domain. Let $\Phi=x+i y$,
$a_R,a_I\in\mathbb R$, $s=x^2+y^2$, and

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

The corresponding interaction energy is

$$
V_{\mathrm{int}}
=-\kappa a_R(x^2-y^2)+2\kappa a_Ixy.
$$

The fixed dimensionless action coefficients and pulse target are

$$
(m,\lambda,g,m_a,\kappa,A,W,\Omega,T_p)
=(1,2,1.25,1,0.5,0.8,8,1,24).
$$

The reservoir superposition uses $N_a=64$ radial sine modes,
$N_r^{\mathrm{fit}}=96$ radial samples, $\Delta t_{\mathrm{fit}}=0.25$,
and the same $R=48$. Its free mode frequencies are
$\omega_n=\sqrt{m_a^2+(n\pi/R)^2}$. The target reduced complex reservoir is

$$
W_{\mathrm{target}}(t,r)
:=A r e^{-r^2/(2W^2)}
\;\sin^2\left(\frac{\pi t}{T_p}\right)e^{i\Omega t}
\quad(0\le t<T_p),
$$

and is zero for $T_p\le t\le T$. The frozen fit samples are
$r_j=(j+\tfrac12)R/96$ for $j=0,\ldots,95$ and
$t_\ell=0.25\ell$ for $\ell=0,\ldots,312$. The coefficient vector $c_n$
uses the convention $W=\sum_{n=1}^{64}c_ne_n(r)e^{i\omega_nt}$ and is
the unique least-squares solution with NumPy `lstsq` and `rcond=10^{-10}`
of the complex residual on every $(t_\ell,r_j)$ pair, with uniform
sample weights. The normalized residual
$\|\mathbf A c-\mathbf b\|_2/\|\mathbf b\|_2$ is retained in the primary
and independent receipts. The initial state is the fitted field at $t=0$
and its free time derivative:
$W(0,r)=\sum_n c_ne_n(r)$ and
$\dot W(0,r)=\sum_n i\omega_nc_ne_n(r)$. The verifier recomputes these
coefficients from this objective; it does not read them from the primary
receipt.

The CP map is

$$
\mathsf{CP}:\quad
x(t,\mathbf x)\mapsto x(t,-\mathbf x),\quad
y(t,\mathbf x)\mapsto-y(t,-\mathbf x),\quad
a_R(t,\mathbf x)\mapsto a_R(t,-\mathbf x),\quad
a_I(t,\mathbf x)\mapsto-a_I(t,-\mathbf x).
$$

The action is CP invariant. The real reservoir component is CP even and the
imaginary component is CP odd. The carrier global phase symmetry is
explicitly broken while either reservoir component overlaps the carrier and
is recovered in the decoupled carrier equation.

## 2. Radial equations and finite-volume state

Set $u_x=rx$, $u_y=ry$, $w_R=ra_R$ and $w_I=ra_I$. The domain is $0<r<R$
with $R=48$. Primary cell centres use $N=384$ cells and the resolution arm
uses $N=768$ cells. The primary timestep is $\Delta t=0.003$ and the
resolution arm uses $\Delta t=0.0015$. The evolution ends at $T=78$ and
stores states at $t=0,6,12,\ldots,78$.

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
$u_t+u_r=0$ for all four fields. The corresponding outer ghost for each
reduced field is $u_N=u_{N-1}-\Delta r\,\dot u_{N-1}$. The static symmetric
operator obtained by replacing this outer ghost with $u_{N-1}$ is retained
for the finite-volume energy quadratic.

The carrier vacuum uses the first $64$ free radial modes,
$e_n(r)=\sqrt{2/R}\sin(n\pi r/R)$, with
$\omega_n=\sqrt{m^2+(n\pi/R)^2}$. Draw independent standard normal variables
from PCG64 seed $20260912$ and set

$$
q_{a,n}=\frac{\xi_{a,n}}{\sqrt{4\omega_n}},\qquad
p_{a,n}=\sqrt{\frac{\omega_n}{4}}\,\pi_{a,n},
\qquad a\in\{x,y\}.
$$
The carrier fields are the corresponding mode sums. This state contains the
finite-mode Gaussian vacuum covariance and no prepared localized carrier
profile or charge packet.

The reservoir begins in the finite-energy fitted packet. In the reduced
complex variable $W=w_R+i w_I$, its initial data are

$$
W(0,r)=\sum_{n=1}^{64}c_ne_n(r),\qquad
\dot W(0,r)=\sum_{n=1}^{64}i\omega_nc_ne_n(r),
$$

with $e_n(r)=\sqrt{2/R}\sin(n\pi r/R)$. For the positive arm,
$w_R=\operatorname{Re}W$, $w_I=\operatorname{Im}W$ and the same split is
used for the momenta. The negative arm applies the declared CP map by
reversing $u_y,p_y,w_I,p_{w_I}$ while leaving $u_x,p_x,w_R,p_{w_R}$
unchanged.

The positive and negative arms use the same fitted coefficient vector. The
reservoir-only control uses this positive packet with $\kappa=0$. The
source-free vacuum control sets the packet amplitude to zero and
$\kappa=0$. Both controls use the same carrier draw and radial
discretization as the primary arm. The carrier observables in the two
controls must agree to $10^{-8}$.

## 3. Charge, energy and reservoir ledgers

The carrier charge and its exact bulk interaction source are

$$
Q_\Phi=4\pi\int_0^R
(u_x\dot u_y-u_y\dot u_x)\,dr,
$$

$$
\dot Q_{\mathrm{src}}
=4\pi\kappa\int_0^R\left[
-4\frac{w_R}{r}u_xu_y
-2\frac{w_I}{r}(u_x^2-u_y^2)\right]\,dr.
$$

The outgoing charge-flux rate at the outer face is

$$
\dot Q_{\mathrm{out}}
:=4\pi\left(-u_x\dot u_y+u_y\dot u_x\right)_{r=R}.
$$

The primary charge residual is the difference between the measured charge and
its initial value plus the trapezoidal integrals of
$\dot Q_{\mathrm{src}}+\dot Q_{\mathrm{out}}$.

For each real reduced field, let $A_h$ be the symmetric second-difference
operator with the regular inner ghost and the static outer ghost. Define

$$
E_{\mathrm{grad},h}
=-\frac12\Delta r\left(
u_x^TA_hu_x+u_y^TA_hu_y+w_R^TA_hw_R+w_I^TA_hw_I\right).
$$

Writing $\rho_i=u_{x,i}^2+u_{y,i}^2$, the full radial energy is

$$
\begin{aligned}
E=4\pi\Bigg\{E_{\mathrm{grad},h}
+\Delta r\sum_i\Bigg[&
\frac12(\dot u_{x,i}^2+\dot u_{y,i}^2+\dot w_{R,i}^2+\dot w_{I,i}^2)
+\frac12m^2\rho_i
-\frac{\lambda}{2}\frac{\rho_i^2}{r_i^2}\\
&+\frac{g}{2}\frac{\rho_i^3}{r_i^4}
+\frac12m_a^2(w_{R,i}^2+w_{I,i}^2)
-\kappa\frac{w_{R,i}}{r_i}(u_{x,i}^2-u_{y,i}^2)
+2\kappa\frac{w_{I,i}}{r_i}u_{x,i}u_{y,i}
\Bigg]\Bigg\}.
\end{aligned}
$$

The energy boundary rate supplied by the outgoing operator is

$$
\dot E_{\mathrm{out}}
=-4\pi(\dot u_x^2+\dot u_y^2+\dot w_R^2+\dot w_I^2)_{r=R}.
$$

The energy residual is the measured full energy minus its initial value and
minus the trapezoidal integral of $\dot E_{\mathrm{out}}$. The charge and
energy residuals are normalized by the maximum of one and the absolute ledger
terms. Each primary residual must remain below $10^{-5}$.

The source-tail budget is evaluated without cancellation:


$$
\mathcal T_Q=
\frac{\int_{24}^{78}|\dot Q_{\mathrm{src}}|\,dt}
{\max\left(1,\int_0^{78}|\dot Q_{\mathrm{src}}|\,dt\right)}.
$$

The source-decoupling predicate is $\mathcal T_Q<0.15$. The corrected late
charge drift subtracts both the measured source integral and the outgoing flux
integral; its range divided by the late absolute-charge scale must be below
$0.05$. The window $60\le t\le78$ is fixed before execution.

## 4. Formation observables and decision rule

The carrier remnant uses core radius $r_c=12$ and exterior radius $r_e=20$. The
nonnegative carrier-support diagnostic is the carrier kinetic, gradient, mass
and sextic terms with the negative quartic and interaction terms omitted. The
core density is the core carrier norm divided by the core volume. The core
fraction is the core carrier norm divided by the total carrier norm. The charge
and energy predicates use the full signed charge and the carrier-only energy in
the core.

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
9. the retained positive and negative raw arrays obey
   $u_x^+=u_x^-$, $u_y^+=-u_y^-$, $w_R^+=w_R^-$,
   $w_I^+=-w_I^-$ and the same relations for the four momenta to $10^{-8}$.

The primary and independent programs are
`computations/matter_formation_closed_cp_reservoir_v7.py` and
`computations/verify_matter_formation_closed_cp_reservoir_v7.py`. The verifier
rebuilds the vacuum draw, least-squares reservoir packet, finite-volume
evolution, ledgers, observables and all predicates without importing the
primary program.

The verdict is
`CAPTURED—conditional closed CP-odd-reservoir vacuum-to-carrier formation` only
when every predicate, both controls, the CP arm, the doubled-grid arm, the
source-tail budget, the ledgers and the independent raw-state reconstruction
pass. A scientific predicate failure returns
`DOES NOT EMERGE—conditional closed CP-odd-reservoir vacuum-to-carrier
formation`. A source, finite-value, ledger, provenance or independent
reconstruction failure returns `INCONCLUSIVE`.

## 5. Scope boundary

A captured result qualifies a finite-mode closed action with a dynamically
specified CP-odd reservoir state, outgoing boundary and localized carrier
trajectory. The reservoir initial state is the declared least-squares
projection of the target two-quadrature pulse; the carrier state is a
Gaussian finite-mode vacuum surrogate. Canonical Cassi action selection,
continuum renormalization, infinite-domain all-sector stability, fermionic
statistics, QCD, baryogenesis, physical normalization and particle identity
remain outside this protocol.

## References

- `foundations/matter-completion-boundary.md`—physical completion requirements and current formation boundary.
- `foundations/particle-stationary-action-closure.md`—source-free temporal carrier action and fixed-charge boundary.
- `computations/matter-formation-cp-odd-pair-qball-v2-prereg.md`—dynamic pseudoscalar source-tail diagnostics.
- `computations/matter-formation-continuum-report.md` §100—conditional prescribed-pump trajectory.
