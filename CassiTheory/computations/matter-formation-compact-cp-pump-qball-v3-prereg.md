# Compact CP-Pump Formation of a Non-Topological Carrier

## Status: Preregistered—September 2026

## Abstract

This protocol tests one explicitly supplied vacuum-to-carrier mechanism with a
finite-duration CP-odd pump. The carrier is a complex scalar with a bounded
sextic potential. A prescribed complex background $J$ couples to $\\Phi^2$
through a quadratic pair-production operator. The carrier begins in a finite
mode Wigner vacuum, not in a prepared localized packet. The pump has compact
temporal support and is exactly zero after its declared duration. Its transient
number-violating work is measured; after the pump, the carrier charge is
conserved apart from the measured outgoing boundary flux.

The calculation targets a localized, non-topological degree-zero carrier. A
positive and a CP-conjugate pump must produce opposite signed carrier charges,
while matching energy, localization, charge-balance and grid-resolution
criteria. A positive result is conditional on this effective action, supplied
pump state, finite-mode vacuum and radiative boundary. It does not identify the
carrier with a Standard Model particle or derive the action from the canonical
Cassi density pair.

## 1. Action and CP transformation

Use natural units and the radial reduced fields
$u_x=r x$, $u_y=r y$ on $0<r<R$, where $\\Phi=x+i y$. The carrier action is

$$
S_\\Phi=\\int d^4x\\left[
\\frac12\\partial_\\mu x\\partial^\\mu x
+\\frac12\\partial_\\mu y\\partial^\\mu y
-U(s)-V_J(t,r,x,y)\\right],
$$

with

$$
 s=x^2+y^2,
\\qquad
U(s)=\\frac12\\left(m^2s-\\lambda s^2+g s^3\\right),
$$

and the compact external pump interaction

$$
V_J=-\\kappa\\left[J_R(t,r)(x^2-y^2)-2J_I(t,r)xy\\right].
$$

The fixed coefficients are

$$
(m,\\lambda,g,\\kappa)=(1,2,1.25,0.5).
$$

The sextic term makes the carrier potential bounded below. The prescribed
positive-pump background is

$$
J_+(t,r)=A f(t)\\exp\\left(-\\frac{r^2}{2W^2}\\right)e^{+i\\Omega t},
$$

where

$$
 f(t)=\\begin{cases}
\\sin^2(\\pi t/T_p),&0\\le t\\le T_p,\\\\
0,&t>T_p,
\\end{cases}
$$

and

$$
(A,W,\\Omega,T_p)=(0.8,8,1,24).
$$

The negative arm uses $J_-=J_+^*$ and the conjugate carrier data
$y\\mapsto-y$, $\\dot y\\mapsto-\\dot y$. The radial profile is parity even,
so the CP map is

$$
\\mathsf{CP}:\\quad \\Phi(t,\\mathbf x)\\mapsto\\Phi^*(t,-\\mathbf x),
\\qquad J(t,\\mathbf x)\\mapsto J^*(t,-\\mathbf x).
$$

The pump is an external effective background. Carrier charge is not asserted
to be conserved while $J\\ne0$; the measured pump source and boundary flux are
part of the receipt. Since $J=0$ exactly for $t>T_p$, the post-pump carrier
action has its ordinary global $U(1)$ symmetry.

## 2. Finite-volume evolution and vacuum state

Use $R=48$ with cell centres
$r_i=(i+1/2)\\Delta r$. The primary grid has $N=384$ and
$\\Delta t=0.003$; the resolution arm has $N=768$ and
$\\Delta t=0.0015$. The evolution ends at $T=78$ and stores states at
$t=0,6,12,\\ldots,78$. The source-free, positive-pump and negative-pump arms
use the primary grid; a positive-pump doubled-grid arm supplies the resolution
control.

The reduced equations are

$$
\\begin{aligned}
\\ddot u_x&=u_x''-C u_x+2\\kappa(J_Ru_x-J_Iu_y),\\\\
\\ddot u_y&=u_y''-C u_y+2\\kappa(-J_Ru_y-J_Iu_x),
\\end{aligned}
$$

where

$$
 C=m^2-2\\lambda\\frac{u_x^2+u_y^2}{r^2}
 +3g\\left(\\frac{u_x^2+u_y^2}{r^2}\\right)^2.
$$

At the origin use the regular reduced-field condition $u(0)=0$. At the outer
face use the outgoing Sommerfeld condition $u_t+u_r=0$. Its discrete charge and
energy fluxes are retained instead of treating the boundary as reflecting.

The carrier starts in the same finite-mode Wigner vacuum in every arm. Let
$e_n(r)=\\sqrt{2/R}\\sin(n\\pi r/R)$ and
$\\omega_n=\\sqrt{m^2+(n\\pi/R)^2}$. For $n=1,\\ldots,64$, draw independent
standard normal variables from PCG64 seed $20260912$ and set

$$
q_{a,n}=\\frac{\\xi_{a,n}}{\\sqrt{4\\omega_n}},
\\qquad
p_{a,n}=\\sqrt{\\frac{\\omega_n}{4}}\\,\\pi_{a,n},
\\qquad a\\in\\{x,y\\}.
$$

The source-free arm uses $J=0$. No classical carrier profile, nonzero-charge
packet, damping term, clipping, field reset or parameter scan is permitted.

## 3. Observables and frozen predicates

The carrier energy excludes the pump interaction and is

$$
E_\\Phi=4\\pi\\int_0^Rdr\\left[
\\frac12(\\dot u_x^2+\\dot u_y^2+u_x'^2+u_y'^2)
+\\frac12m^2(u_x^2+u_y^2)
-\\frac{\\lambda}{2r^2}(u_x^2+u_y^2)^2
+\\frac{g}{2r^4}(u_x^2+u_y^2)^3
\\right].
$$

The signed carrier charge is

$$
Q_\\Phi=4\\pi\\int_0^R(u_x\\dot u_y-u_y\\dot u_x)\\,dr.
$$

The pump source term and outer boundary flux are reconstructed from the
finite-volume equations. In particular,

$$
\\dot Q_{\\rm pump}=4\\pi\\int_0^Rdr\\left[
-4\\kappa J_Rxy-2\\kappa J_I(x^2-y^2)\\right],
$$

and the full energy includes $V_J$, with explicit pump work
$\int\partial_tV_J$ and outgoing energy flux. The post-pump charge test uses
$Q_\Phi$ corrected by the measured outer charge flux; the pump source must be
zero after $T_p$.

The remnant core is $r\\le12$. This radius is fixed before the execution as the
finite-radius support scale of the supplied non-topological branch. The
exterior support fraction uses the nonnegative carrier-support diagnostic over
$r\\ge20$. The late window is $60\\le t\\le78$.

The primary scientific predicates are:

1. the late-window mean core density is at least four times the source-free
   late-window mean;
2. the minimum late-window core number fraction is at least $0.80$;
3. the maximum late-window exterior support fraction is below $0.25$ and its
   mean is below $0.20$;
4. the minimum late-window absolute core charge exceeds $200$, and the
   corrected post-pump charge range divided by the late charge scale is below
   $0.05$;
5. the maximum late-window $E_{\\Phi,\\mathrm{core}}/|Q_{\\Phi,\\mathrm{core}}|$
   is below $m$, the core radius and all state values are finite;
6. the positive and negative arms are CP conjugates, with opposite signed
   charge, and the late-window means of core energy, core charge magnitude,
   core fraction, exterior fraction and rms radius differ by less than $5\\%$
   between the primary and doubled grids.

The primary and independent programs are
`computations/matter_formation_compact_cp_pump_qball_v3.py` and
`computations/verify_matter_formation_compact_cp_pump_qball_v3.py`. The
verifier must rebuild the vacuum draw, source, finite-volume evolution, flux
ledger, observables and all predicates without importing the primary program.

The verdict is
`CAPTURED—conditional compact CP-pump vacuum-to-carrier formation` only when
all six predicates, the source-free control, the CP arm, the flux/energy ledger,
and the independent raw-state reconstruction pass. A numerical receipt with a
failed scientific predicate returns
`DOES NOT EMERGE—conditional compact CP-pump vacuum-to-carrier formation`.
A source, finite-value, ledger, provenance or independent-reconstruction failure
returns `INCONCLUSIVE`.

## 4. Scope boundary

A captured result establishes a finite-mode vacuum-to-localized trajectory for
one supplied effective action with a compact external CP-odd pump and outgoing
boundary. The carrier is a non-topological degree-zero scalar remnant in this
model. The result does not establish a canonical Cassi action, a dynamical pump
reservoir, a fermionic statistic, QCD, a physical proton mass or radius, all
angular sectors, continuum renormalization, gravity, chemistry or a universal
matter-formation law. Those are separate physical completion requirements.

## References

- `foundations/matter-completion-boundary.md`—physical completion requirements and current formation boundary.
- `foundations/interscale-current-soliton.md`—registered phase-bearing action and its empty-sector invariant.
- `computations/matter-formation-continuum-report.md` §§84–86, 98–99—CP selection and vacuum-formation boundaries.
