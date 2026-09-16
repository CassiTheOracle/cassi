# CP-Odd Pair-to-Carrier Formation Protocol

## Status: Preregistered—September 2026

## Abstract

This protocol tests one explicit microscopic completion for localized matter
formation. A complex scalar carrier is coupled to a real pseudoscalar pulse
through a quadratic pair-production operator. The carrier begins in a finite-box
$s$-wave Gaussian vacuum state, not in a prepared nonzero-charge packet. The
pseudoscalar pulse is a CP-odd coherent state and supplies the declared branch
selection. After the pulse has crossed the carrier region, the carrier has the
standard global phase symmetry and its signed charge is measured on the retained
trajectory. A positive result requires a localized, energetically subthreshold
carrier remnant produced from vacuum fluctuations, post-pulse charge continuity,
energy accounting, and independent reconstruction.

This is a newly supplied effective action. It is not inferred from the
canonical real-density PDE or from the registered positive phase-current action.
The calculation can establish a conditional scalar matter mechanism only. It
cannot identify the scalar with a nucleon, derive QCD, or transfer a result to
the frozen degree-zero chiral or vacuum-bag schedules.

## 1. Action and transformations

Use natural units and a finite spherical domain $0<r<R$. The fields are a
complex carrier $\\Phi=x+iy$ and a real pseudoscalar $a$. The action is

$$
S=\int d^4x\left[
\partial_\mu\Phi^*\partial^\mu\Phi
+\frac12\partial_\mu a\partial^\mu a
-U(|\Phi|)-\frac12m_a^2a^2
+\kappa a\,\operatorname{Im}(\Phi^2)
\right],
$$

with

$$
U(|\Phi|)=m^2|\Phi|^2-\lambda|\Phi|^4+g|\Phi|^6.
$$

The frozen dimensionless coefficients are

$$
(m,\lambda,g,m_a,\kappa)=(1,2,1.25,2,0.8).
$$

The potential is bounded below and has a unique vacuum at $\Phi=0$ because
$\lambda^2<4gm^2$. For a stationary carrier $\Phi=f(r)e^{i\omega t}$,
$0<\omega<m$ and the radial equation are the standard non-topological
soliton conditions. The supplied coefficients admit the stationary localized
branch; its energy-to-charge ratio is tested independently rather than assumed.

The CP map is

$$
\mathsf{CP}:\quad \Phi(t,\mathbf x)\mapsto\Phi^*(t,-\mathbf x),
\qquad a(t,\mathbf x)\mapsto-a(t,-\mathbf x).
$$

The action is CP invariant. The sign of the initial $a$ coherent pulse is the
explicit CP-odd state datum. While $a\ne0$, the quadratic interaction permits
carrier-number violation and pair creation. Once the pulse has left the carrier
core, the carrier action has the global $U(1)$ symmetry and the ordinary signed
charge

$$
Q=\int i(\Phi^*\dot\Phi-\dot\Phi^*\Phi)\,d^3x
$$

is conserved up to boundary flux and the declared residual interaction tail.

## 2. Finite-box quantum state and radial equations

Use the radial reduced fields $u_x=rx$, $u_y=ry$, and $v=ra$ on
$R=32$, with $N=512$ cell centres $r_i=(i+1/2)\Delta r$ and
$\Delta r=R/N$. Dirichlet outer data are $u_x=u_y=v=0$; the cell-centred
second derivative supplies the regular origin condition. The evolved equations
are

$$
\begin{aligned}
\ddot u_x&=u_x''-\left[m^2-2\lambda s+3gs^2\right]u_x+\kappa(v/r)u_y,\\
\ddot u_y&=u_y''-\left[m^2-2\lambda s+3gs^2\right]u_y+\kappa(v/r)u_x,\\
\ddot v&=v''-m_a^2v+2\kappa u_xu_y/r,
\end{aligned}
\qquad
s=(u_x^2+u_y^2)/r^2.
$$

The pulse is the finite-energy coherent state

$$
 a(0,r)=A\exp[-(r-r_a)^2/(2w_a^2)],\quad \dot a(0,r)=0,
$$

with $(A,r_a,w_a)=(4,4,1.5)$. Its sign is positive in the primary arm and
negative in the CP-conjugate arm. No damping, absorber, clipping or source
reset is allowed. The coupled evolution runs to $T=48$ with $\Delta t=0.002$;
archives are retained at $t=0,4,8,\ldots,48$.

The carrier state is the finite-box $s$-wave Wigner vacuum of the free massive
carrier at $t=0$. Let
$e_n(r)=\sqrt{2/R}\sin(n\pi r/R)$ and
$\omega_n=\sqrt{m^2+(n\pi/R)^2}$. For $n=1,\ldots,32$, draw independent
standard normal variables $\xi_{x,n},\xi_{y,n},\pi_{x,n},\pi_{y,n}$ from the frozen
PCG64 generator with seed $20260912$, and set

$$
q_{a,n}=\frac{\xi_{a,n}}{\sqrt{4\omega_n}},\qquad
p_{a,n}=\sqrt{\frac{\omega_n}{4}}\,\pi_{a,n},
$$

$$
 u_a(0,r)=\sum_n q_{a,n}e_n(r),\qquad
\dot u_a(0,r)=\sum_n p_{a,n}e_n(r),\qquad a\in\{x,y\}.
$$

This fixes the finite-mode Gaussian vacuum covariance and contains no prepared
classical carrier profile or nonzero-charge input. The source-free vacuum
control uses the same draw with $A=0$.

## 3. Observables and frozen decisions

The carrier energy after the pulse is

$$
E_\Phi=4\pi\int_0^Rdr\left[
\frac12(\dot u_x^2+\dot u_y^2+u_x'^2+u_y'^2)
+\frac12m^2(u_x^2+u_y^2)
-\frac{\lambda}{r^2}(u_x^2+u_y^2)^2
+\frac{g}{r^4}(u_x^2+u_y^2)^3
\right].
$$

The signed charge, core charge, rms radius and exterior fraction use

$$
Q=8\pi\int_0^R(u_x\dot u_y-u_y\dot u_x)\,dr,
$$

with the core $r\le6$ and exterior $r\ge12$. A retained carrier remnant must
satisfy all of:

1. late core density exceeds the source-free vacuum control by at least a
   factor of four;
2. the core retains at least $80\%$ of the late carrier number;
3. the late exterior energy fraction is below $0.20$;
4. $|Q|\ge0.5$ and the post-pulse charge drift over $t\in[24,48]$ is below
   $5\%$ after subtracting the measured outer flux;
5. $E_\Phi/|Q|<m$ and the late core rms radius is finite and grid-stable;
6. the positive and negative pulse arms are CP conjugates within the raw-state
   tolerance and have opposite signed charge.

The numerical calculation is `computations/matter_formation_cp_odd_pair_qball.py`.
The independent reconstruction is
`computations/verify_matter_formation_cp_odd_pair_qball.py`. The verifier must
rebuild the vacuum draw, finite-volume evolution, energy, charge, radial
observables and decision predicates without importing the primary source.

Controls are mandatory: (i) source-free vacuum, (ii) positive-pulse primary,
(iii) negative-pulse CP conjugate, and (iv) doubled spatial resolution
$N=1024$ for the positive-pulse arm. The doubled-grid arm uses the same physical
parameters and the same vacuum modes interpolated through their analytic basis;
it is a resolution check, not a parameter scan.

The result is `CAPTURED—conditional CP-odd vacuum-to-carrier formation` only if
all six predicates, both controls and the independent receipt pass. If all
numerical and provenance checks pass but a predicate fails, the verdict is
`DOES NOT EMERGE—conditional CP-odd vacuum-to-carrier formation`. Any source,
finite-value, raw-state or independent-reconstruction failure is
`INCONCLUSIVE`.

## 4. Scope boundary

A captured result establishes one explicitly supplied scalar effective action
and a finite-mode Gaussian vacuum-to-localized-carrier trajectory. It does not
establish a canonical Cassi derivation, a fermionic particle, QCD, a physical
proton mass or radius, all angular sectors, continuum renormalization, gravity,
or a universal matter-formation law. The source-free vacuum and negative-pulse
controls are required to distinguish formation from prepared carrier data and
from a sign convention.

## References

- `foundations/matter-completion-boundary.md`—six physical completion requirements and current formation boundary.
- `foundations/interscale-current-soliton.md`—registered phase-bearing action and its empty-sector invariant.
- `computations/matter-formation-continuum-report.md` §§84–86, 98–99—CP-selection and vacuum-formation boundaries.
