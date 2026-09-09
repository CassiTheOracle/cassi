# Navier–Stokes Strain Departure: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule checks a quantitative comparison argument for departure from the strain self-amplification condition in the original unforced Navier–Stokes equation. It covers exact budget algebra, a smooth axisymmetric datum, and one-dimensional quadratures of a comparison deadline. It contains no time-evolved Navier–Stokes calculation, singularity search, fitted coefficient, or parameter optimization. The analytical theorem and its limitations are recorded in `turbulence/navier-stokes-strain-departure.md`.

## 1. Equation, data and conventions

Work on $\mathbb R^3$ with smooth, finite-energy, divergence-free velocity, viscosity $\nu>0$, strain $S=\nabla_{\mathrm{sym}}u$, and vorticity $\omega=\nabla\times u$. All spatial integrals use ordinary Lebesgue measure. Retain the full orthogonal projection $P_{\mathrm{st}}$ onto strains of solenoidal velocities. Define
$$
K=\tfrac12\|u\|_2^2=\|S\|_{\dot H^{-1}}^2,
\quad E=\|S\|_2^2,
\quad G=\|S\|_{\dot H^1}^2,
\quad f=-3\nu G-4\int\det S,
$$
$$
\mathcal R=P_{\mathrm{st}}\left((u\cdot\nabla)S+\tfrac13S^2+\tfrac14\omega\otimes\omega\right),
\quad M=-\nu\Delta S+\tfrac23P_{\mathrm{st}}(S^2),
\quad D=M+\tfrac12\mathcal R.
$$
The perturbative condition is $\|\mathcal R\|_2\le2\|D\|_2$. Use its squared defect
$$
\delta=\|\mathcal R\|_2^2-4\|D\|_2^2
$$
to handle a zero denominator. The source is Miller, arXiv:1910.05415, Theorem 6.1 and Corollary 6.6. The comparison requires $K_0,E_0,f_0>0$.

## 2. Exact identities and candidate comparison

Check the Hilbert-space completion of squares, the variational derivative of $f$ on the strain space, and
$$
f'=-\tfrac32\delta,\qquad E'=f+\nu G,\qquad K'=-2\nu E,
\qquad E^2\le KG.
$$
On an interval with $\delta\le0$, the candidate integrated inequality is
$$
K E^2+\frac{f_0}{2\nu}K^2
\ge K_0E_0^2+\frac{f_0}{2\nu}K_0^2.
$$
Its proposed exit-or-breakdown deadline is
$$
T_{\mathrm{cmp}}=
\frac{K_0}{2\nu E_0}\int_0^1
\frac{\sqrt{x}\,dx}{\sqrt{1+\chi(1-x^2)}},
\qquad \chi=\frac{f_0K_0}{2\nu E_0^2}.
$$
Compare it with Miller's energy deadline at general viscosity,
$$
T_*=
\frac{K_0}{\nu\left(E_0+\sqrt{E_0^2+f_0K_0/\nu}\right)}.
$$
Verify the $\chi\to0^+$ comparison integral $2/3$ and the scaling $K\mapsto\lambda^{-1}K$, $E\mapsto\lambda E$, $f\mapsto\lambda^3f$, $T\mapsto\lambda^{-2}T$.

Check the exact cumulative defect identity
$$
K(t)=K_0-2\nu E_0t-\nu f_0t^2
+\frac{3\nu}{2}\int_0^t(t-s)^2\delta(s)\,ds
-2\nu^2\int_0^t(t-s)G(s)\,ds.
$$
Differentiation and the three initial values must recover the budget system. A lower bound on an integrated excess is separate from an upper regularity bound. The critical work $\langle\Lambda^{-1/2}S,\Lambda^{-1/2}\mathcal R\rangle$ has its own derivative weights; no norm-ratio implication or favorable sign is assumed.

## 3. Fixed axisymmetric datum

Use Miller's Proposition 5.4 datum
$$
v(x,y,z)=e^{-(x^2+y^2+z^2)}
\left(x(1-2z^2),y(1-2z^2),2z(x^2+y^2-1)\right).
$$
Derive its Cartesian strain, vorticity, divergence, and the four exact Gaussian moments
$$
K_v=\tfrac12\int|v|^2,\quad E_v=\int|S_v|^2,
\quad G_v=\int|\nabla S_v|^2,\quad I_v=-\int\det S_v.
$$
Qualify $I_v=8\pi^{3/2}/(81\sqrt3)$ against the primary paper. Cross-check $E_v=\tfrac12\int|\omega_v|^2$ and $G_v=\tfrac12\int|\nabla\omega_v|^2$.

Independently reconstruct these integrals in cylindrical coordinates using $v_r=r(1-2z^2)e^{-r^2-z^2}$ and $v_z=2z(r^2-1)e^{-r^2-z^2}$. Use Gaussian–Laguerre quadrature in $r^2$ and Gaussian–Hermite quadrature in $z$, with orders **12 and 20**. Include the cylindrical vector-gradient contribution $\omega_\theta^2/r^2$ in $G_v$.

The amplitude threshold is $a_{\mathrm{crit}}=3\nu G_v/(4I_v)$. For each $\nu\in\{1/100,1\}$ and multiplier $m\in\{2,4\}$, use $u_0=m a_{\mathrm{crit}}v$. Record $K_0,E_0,G_0,f_0,\chi,T_*,T_{\mathrm{cmp}}$. These fixtures qualify the determinant sign and comparison input; no claim is made that their initial perturbative condition holds. The nonempty class with an initial perturbative window is supplied by Miller's Proposition 6.2 and Remark 6.5.

## 4. Fixed deadline quadratures

For $\chi\in\{1/16,1/4,1,4,16\}$ and the four amplitude/viscosity rows above, evaluate the comparison integral in two independent ways:

1. Gaussian–Legendre quadrature of the smooth substitution $x=s^2$, with orders **64 and 128**.
2. Independent high-precision adaptive quadrature of the original $x$ integral, using **50 decimal digits**.

Record all values, normalized discrepancies, and $T_{\mathrm{cmp}}/T_*$. Check $T_{\mathrm{cmp}}<T_*$ on the fixed rows; the infinite-class inequality requires the analytical proof. Check viscosity and Navier–Stokes scaling at $\lambda\in\{1/2,1,2\}$ without interpreting the rescaling as an additional flow simulation.

## 5. Qualification and stopping rule

- Exact equalities require zero symbolic residual. Numerical comparisons require finite values and $|a-b|/(1+|a|+|b|)<10^{-10}$.
- Every named comparison is unique. The comparison sets must be nonempty. Missing evidence, a nonfinite value, or an exact/numerical failure gives **FAIL** to the affected check and forbids adopting its inference.
- Algebraic/numerical qualification is **PASS/FAIL**. A qualified set verifies the stated computations, rather than continuum dynamics. No simulated departure or blow-up verdict is assigned.
- The analytical review separately resolves proof assumptions, sign conventions, strictness, the squared-defect zero-denominator case, and the distinction between general-data exit-or-breakdown and axisymmetric swirl-free exit.
- No numerical continuation, extra amplitudes, graded Sobolev sweep, spatial grid, or stopping-time fit may be added. Stop after this fixed schedule and the independent analytical reviews are reconciled. An unresolved critical-work estimate remains an explicit proof limitation.

## 6. Evidence and reproduction

Run `python computations/verify_navier_stokes_strain_departure.py --output runs/navier_stokes_strain_departure/verification.json` from CassiTheory. Require a fresh output, adjacent input manifest, and frozen source snapshots. Record raw SHA-256 identities for this protocol, the verifier, and any imported local helpers. Preserve source bytes throughout execution and retain failed receipts. Generated receipts are indexed in `BROKEN_REFS.md`; the scoped record belongs in `field-experience/probe-outcome-ledger.md`. Existing Navier–Stokes protocols and their receipts remain immutable.

## References

- E. Miller, [Finite-time blowup for a Navier–Stokes model equation for the self-amplification of strain](https://arxiv.org/abs/1910.05415), §§5–6; [mathematical HTML](https://ar5iv.labs.arxiv.org/html/1910.05415).
- `turbulence/navier-stokes-strain-departure.md`—analytical comparison and limits.
- `turbulence/navier-stokes-transfer-boundary.md`—velocity-critical concentration budget.
- `computations/verify_navier_stokes_depletion.py`—existing immutable receipt conventions.
