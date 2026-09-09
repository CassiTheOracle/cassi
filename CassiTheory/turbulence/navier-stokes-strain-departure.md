# Quantitative Departure from Strain Self-Amplification

## Status: Derived conditional comparison / Open critical-work control—September 2026

## Abstract

The original unforced Navier–Stokes equation imposes a finite energy budget on persistent strain self-amplification. Retaining a standard interpolation inequality gives an explicit departure-or-breakdown deadline that is strictly earlier than the energy deadline in Miller's perturbative comparison. Known global regularity converts this alternative into a departure statement for axisymmetric, swirl-free data. A separate integrated identity quantifies the excess of the full-equation remainder over the perturbative condition. These are conditional comparison consequences of established Navier–Stokes identities. A bound on critical-scale production, control after departure, and arbitrary-data global regularity remain open.

## 1. Equation, data and source boundary

The comparison concerns the ordinary incompressible velocity equation. No Cassi force, modified dissipation, spectral truncation or constitutive identification is introduced. On $\mathbb R^3$,
$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad \nabla\cdot u=0,\qquad \nu>0.
$$
Use smooth, finite-energy data with enough Sobolev regularity for the quantities below; divergence-free Schwartz data suffice. All identities are applied on the smooth lifespan, and all spatial integrals use Lebesgue measure. Let
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

## 6. Critical-scale limitation

The regularity problem requires a different derivative weight and an upper production estimate. The velocity-critical quantities used in `turbulence/navier-stokes-transfer-boundary.md` are
$$
\mathcal C=\|u\|_{\dot H^{1/2}}^2
=2\|S\|_{\dot H^{-1/2}}^2,
\qquad
Y=\|u\|_{\dot H^{3/2}}^2
=2\|S\|_{\dot H^{1/2}}^2.
$$
The remainder contributes
$$
\left.\mathcal C'\right|_{\mathcal R}
=-4\langle\Lambda^{-1/2}S,\Lambda^{-1/2}\mathcal R\rangle.
$$
The unweighted cancellation $\langle S,\mathcal R\rangle=0$ leaves this pairing uncontrolled. Neither the sign of $f'$ nor a lower bound on $\int\delta_+$ estimates it. The complete budget remains
$$
\mathcal C'+2\nu Y=2F,
$$
with the production estimate identified in `turbulence/navier-stokes-depletion-dynamics.md` still open.

For general three-dimensional data, the argument permits breakdown before departure. Even for a smooth solution that leaves the perturbative condition, it supplies no bound on subsequent critical concentration, the number of renewed amplification episodes, or their cumulative production. It also provides no estimate uniform under symmetry-breaking perturbations of the axisymmetric class.

The Cassi-inspired research question concerns how a term with zero direct enstrophy work changes future amplification. The exact $f'$ identity and energy-coupled comparison quantify one aspect of that change inside ordinary Navier–Stokes. A geometry-resolved evolution estimate for the critical work remains the additional mathematical requirement. No Cassi current-to-momentum constitutive map follows from this argument.

## 7. Verification and evidence scope

The fixed analytical-verification schedule passes **71 checks**, with maximum normalized numerical discrepancy **$9.633333680505873\times10^{-15}$** against the threshold $10^{-10}$. It covers the projected completion of squares, variational derivative, comparison monotonicity, cumulative identity, Fourier scaling, exact Gaussian moments, independent cylindrical quadrature and comparison-deadline quadrature.

The cylindrical reconstruction uses Gaussian–Laguerre and Gaussian–Hermite orders 12 and 20, including the angular-basis derivative in the vorticity-gradient norm. The deadline checks compare Gaussian–Legendre orders 64 and 128 with independent 50-digit adaptive quadrature. The finite controls qualify their calculations. The continuum comparison and the strict inequality in §3 follow from the displayed analytical proof.

Independent analytical reviews reconcile the scalar comparison, endpoint alternative and cumulative excess-dose proof with the derivations above. `runs/navier_stokes_strain_departure/reconciliation.json` records the accepted statements and excludes ancillary reviewer claims that lack qualification. The critical-work estimate remains open; no universal no-go theorem for that estimate is adopted.

The accepted receipt is `runs/navier_stokes_strain_departure/qualified/verification.json`, schema `cassi.navier-stokes.strain-departure.verification.v1`, with adjacent `verification.inputs.json` and `verification.sources/`. The manifest, retained source snapshots and executable inputs agree on the following raw SHA-256 identities:

| Input | SHA-256 |
|---|---|
| Fixed protocol | `d783fe2f0b628bc4c97f010f540f65d871765e28973b4627a6f55df494c4d97c` |
| Departure verifier | `d784db3a6a61da213f2d15e1e38302c604c99e49b662e420ebd2115df26ba0b8` |
| Depletion helper | `f74633d488d974e8bb3c83d24448064f2badb89059a6938fcc8235db3e7426e5` |
| Fourier helper | `a7ca230b989f5713cb511b18971007d41cbdad20d9c8cf8e2af7d34f107755e0` |

The retained `runs/navier_stokes_strain_departure/verification.json` is a **FAIL** diagnostic: its two viscosity-normalization checks use a squared viscosity ratio. It is excluded from mathematical qualification and retains its own input manifest and source snapshots. The accepted comparison uses the $\nu^{-1}$ time similarity stated in §3.1. The frozen protocol has the same raw hash in both receipts.

No Navier–Stokes trajectory is run. No observed exit time, singularity, fitted constant or general regularity verdict is recorded. The critical-work and arbitrary-data regularity fields remain **UNRESOLVED**. No physical parameter, numbered open question or empirical prediction is introduced or reclassified by this comparison.

To reproduce from CassiTheory, supply a fresh path to `python computations/verify_navier_stokes_strain_departure.py --output runs/navier_stokes_strain_departure/reproduction/verification.json`. Existing receipt paths are immutable.

## References

- E. Miller, [Finite-time blowup for a Navier–Stokes model equation for the self-amplification of strain](https://arxiv.org/abs/1910.05415), §§5–6—strain model, perturbative comparison, explicit Gaussian datum, initial perturbative window and axisymmetric departure; [mathematical HTML](https://ar5iv.labs.arxiv.org/html/1910.05415).
- E. Miller, [A regularity criterion for the Navier–Stokes equation involving only the middle eigenvalue of the strain tensor](https://arxiv.org/abs/1710.05569)—strain enstrophy and conditional geometric regularity.
- `turbulence/navier-stokes-transfer-boundary.md`—critical transfer budget and heat-correction limitation.
- `turbulence/navier-stokes-stress-geometry.md`—full stress and strain dynamics.
- `turbulence/navier-stokes-depletion-dynamics.md`—fine-scale response, cumulative production requirement and matter-response boundary.
- `computations/navier-stokes-strain-departure-prereg.md`—fixed identities, controls, tolerance and stopping rule.
- `computations/verify_navier_stokes_strain_departure.py`—exact algebra and independent numerical reconstructions.
- `field-experience/probe-outcome-ledger.md`—qualified evidence and scope.
