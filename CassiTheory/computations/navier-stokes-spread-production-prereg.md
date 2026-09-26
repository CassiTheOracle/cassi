# Spectral Spread Production: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This fixed analytical check verifies a scale-resolved continuation reduction for the original unforced three-dimensional periodic Navier–Stokes equation. It checks exact radial-moment inequalities, the centered form of nonlinear spread production, the resulting Young estimates and the consequence of the existing exact mixing family. It evolves no trajectory, searches no parameter and makes no regularity classification beyond the proved conditional implication.

This is a separate analytical follow-up to the completed critical-recurrence
schedule. It does not add a fixture to, alter or rerun that frozen protocol.

## 1. Equation and conventions

Use a smooth mean-zero divergence-free velocity on the volume-normalized $2\pi$ torus while the solution exists:

$$
\nu>0,\qquad B=-\mathbb P[(u\cdot\nabla)u],\qquad u_t=B+\nu\Delta u.$$

Set

$$
K=\tfrac12\|u\|_2^2,\quad E=\tfrac12\|\Lambda u\|_2^2,
\quad G=\tfrac12\|\Lambda^2u\|_2^2,
$$

$$
\mathcal C=\|u\|_{\dot H^{1/2}}^2,\qquad
Y=\|u\|_{\dot H^{3/2}}^2,
$$

$$
A=\langle\Lambda^2u,B\rangle,\qquad
F=\langle\Lambda u,B\rangle,
$$

and

$$
\mathcal V=KE-\mathcal C^2/4,\qquad
\mathcal Q=2KG+2E^2-\mathcal C Y,
\qquad
\mathscr P_{\mathcal V}=KA-\mathcal C F.
$$

For nonzero data with $E>0$, put

$$
m=\frac{\mathcal C}{2K},\qquad
\eta=\frac{\mathcal V}{KE}.
$$

The radial spectral-energy measure $d\mu(r)$ has moments

$$
(M_0,M_1,M_2,M_3,M_4)=(2K,\mathcal C,2E,Y,2G).
$$

Normalize it to a probability measure and write

$$
a=\mathbb E R,\quad b=\mathbb E R^2,\quad c=\mathbb E R^3,
\quad d=\mathbb E R^4,
$$

$$
v=b-a^2,\qquad q=d+b^2-2ac.
$$

Then $m=a$, $\eta=v/b$ and $\mathcal Q=2K^2q$.

## 2. Fixed exact targets

The verifier checks the following symbolic identities and constants.

1. The pair expansion is
   $$
   q=\tfrac12\mathbb E_{R,S}\!
   \left[(R-S)^2(R^2+S^2)\right],
   $$
   hence
   $$
   \mathcal Q=\tfrac14\iint(r-s)^2(r^2+s^2)
   \,d\mu(r)d\mu(s)\ge0.
   $$
2. With $h=\mathbb E[R^2(R-a)^2]$,
   $$
   q=bv+h,
   \qquad
   \boxed{\mathcal Q\ge2\eta E^2}.
   $$
3. Let $L=a(3b-a^2)$ and $x=a/\sqrt b\in[0,1]$. Verify
   $$
   b(q-\eta ac)=bd+b^3-Lc,
   $$
   and its lower-bound decomposition using $bd\ge c^2$ and
   $$
   b^3-\frac{L^2}{4}
   =\frac{b^3}{4}(1-x^2)^2(4-x^2)\ge0.
   $$
   Therefore
   $$
   \boxed{\mathcal Q\ge\tfrac12\eta\mathcal C Y}.
   $$
4. For $k=\mathbb E[(R-a)^4]$ and
   $e=\mathbb E[R(R-a)^2]$, verify
   $$
   q-k=v^2+2ae\ge0,
   $$
   and consequently
   $$
   \boxed{\|(\Lambda-m)^2u\|_2^2\le\mathcal Q/K}.
   $$
5. Energy orthogonality $\langle u,B\rangle=0$ gives
   $$
   \boxed{
   \mathscr P_{\mathcal V}
   =K\langle(\Lambda-m)^2u,B\rangle}.
   $$
   Combined with the preceding target and
   $\|B\|_2\le c_{\rm S}\sqrt{2E}\sqrt Y$, this gives
   $$
   |\mathscr P_{\mathcal V}|
   \le c_{\rm S}\sqrt{2KEY\mathcal Q},
   $$
   and
   $$
   \mathcal V'+\frac\nu2\mathcal Q
   \le\frac{c_{\rm S}^2}{\nu}KEY.
   $$
6. The exact critical budget and Target 3 imply, for
   $0<\varepsilon\le2\nu$,
   $$
   \mathcal C'+(2\nu-\varepsilon)Y
   \le\frac{2c_{\rm S}^2}{\varepsilon}\mathcal Q.
   $$
   In particular,
   $$
   \mathcal C'+\nu Y\le\frac{2c_{\rm S}^2}{\nu}\mathcal Q.
   $$
7. From
   $\mathcal V'+\nu\mathcal Q=\mathscr P_{\mathcal V}$,
   verify the integrated implication
   $$
   \mathcal C(t)+\nu\int_0^tY\,ds
   \le\mathcal C(0)
   +\frac{2c_{\rm S}^2}{\nu^2}
   \left(\mathcal V(0)
   +\int_0^t(\mathscr P_{\mathcal V})_+\,ds\right).
   $$
   Finiteness of the positive-production integral at a finite smooth endpoint therefore bounds $\sup\mathcal C$ and $\int Y$. Together with $4E^2\le\mathcal C Y$ and $\dot H^1\hookrightarrow L^6$, this gives $u\in L_t^4L_x^6$ and the standard Prodi–Serrin continuation implication. The verifier checks only the algebraic coefficients; the functional-analytic continuation step is proved in the accompanying paper.
8. For the two-atom probability measure
   $(1-p)\delta_0+p\delta_r$, check
   $$
   \frac q{\eta ac}=\frac1p,\qquad
   \frac{\mathcal Q}{\eta E^2}=\frac2p,
   $$
   and the limits $1$ and $2$ as $p\uparrow1$. These show that the coefficients in Targets 2 and 3 are optimal. Check also that the ratio between $k$ and $q$ tends to one.
9. The existing exact mixing family at viscosity one has
   $\mathcal C(0)=N^6$ and
   $\mathcal C(t_N)\ge N^7/64$ for $N\ge2$. The verifier checks the consequence
   $$
   \int_0^{t_N}\mathcal Q\,dt
   \ge\frac{N^7/64-N^6}{c_{\rm S}^2},
   $$
   and, because $\mathcal V(0)=0$,
   $$
   \int_0^{t_N}(\mathscr P_{\mathcal V})_+\,dt
   \ge\frac{N^7/64-N^6}{c_{\rm S}^2}.
   $$
   Thus neither cumulative quantity admits a datum-independent bound linear in $\mathcal C(0)$. The family is globally smooth and supplies no singularity.

The degenerate cases are stated separately in the paper: $K=0$ gives the zero field; $E=0$ on the mean-zero torus also gives the zero field; and $\mathcal V=0$ gives a single radial shell with $\eta=\mathcal Q=0$.

## 3. Fixed symbolic controls

Use exact SymPy expressions only. Check the moment expansions directly and again after substituting a finite positive atomic measure with fixed rational supports $0,1,2,5$ and fixed rational weights $1/10,1/5,3/10,2/5$. Check the two-atom sharpness formulas symbolically for $0<p<1$ and $r>0$. Check each Young remainder by expanding it as a square.

Every named check is unique. Empty results, a failed exact equality, a failed fixed-atom inequality or a nonfinite serialized expression fail the run. No floating-point tolerance is used.

## 4. Decision and stopping rule

The fixed analytical classification is **PASS** only if every exact and fixed-atom check passes. Any failure is **FAIL**. The scientific conclusion is limited to the displayed identities, sharp constants, conditional continuation reduction and exact-family obstruction to linear cumulative bounds. A data-controlled bound on cumulative positive spread production remains **UNRESOLVED**.

Run the frozen verifier once after its source is complete. An implementation defect may be repaired with the failed receipt retained, no target changed and a fresh output path. Do not add trajectories, parameter searches or fitted inequalities.

## 5. Evidence paths

From the CassiTheory root, run:

```
python computations/verify_navier_stokes_spread_production.py \
  --output runs/navier_stokes_spread_production/verification.json
```

The verifier writes an immutable JSON receipt, an adjacent input manifest and source snapshots. Generated evidence remains local and is indexed in `BROKEN_REFS.md`.

- `turbulence/navier-stokes-strain-departure.md`—analytical proof and exact mixing family.
- `computations/verify_navier_stokes_spread_production.py`—fixed exact verification.
- `computations/verify_navier_stokes_critical_recurrence.py`—retained spread dynamics and cyclic zero-spread departure fixture.
- `computations/verify_navier_stokes_mixing_budget.py`—retained exact mixing-family verification.
- E. Miller, [Global regularity for solutions of the Navier–Stokes equation sufficiently close to being eigenfunctions of the Laplacian](https://arxiv.org/abs/2005.14152)—established spectral-concentration context.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—problem alternatives.
