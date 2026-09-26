# Helical Spread and Phase-Current Coercivity: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This fixed analytical check refines the spectral-spread continuation problem for the original unforced three-dimensional incompressible Navier–Stokes equation. It resolves velocity into signed curl modes, derives the optimal scalar Beltrami residual, verifies a critical continuation criterion and uses that residual to bound the positive radial-spread production left open by the preceding analysis. It then checks whether the first-order phase geometry of a positive Yang/Yin doublet controls the residual. A fixed smooth concentrating family supplies the obstruction: bounded doublet gradient energy can coexist with unbounded enstrophy and Beltrami residual.

The calculation evolves no candidate singular trajectory, searches no parameter and assigns no literature priority to the continuation criterion. It does not alter or rerun any earlier frozen schedule.

## 1. Equation and conventions

Use a smooth mean-zero divergence-free velocity on the volume-normalized $2\pi$ torus, or a smooth decaying velocity on $\mathbb R^3$, while the solution exists:

$$
\nu>0,\qquad
B=-\mathbb P[(u\cdot\nabla)u]=\mathbb P(u\times\omega),
\qquad
u_t:=\partial_tu=B+\nu\Delta u,
$$

where $\omega=\nabla\times u$, $S=(\nabla u+\nabla u^\mathsf T)/2$ and $\Lambda=(-\Delta)^{1/2}$. Set

$$
K=\tfrac12\|u\|_2^2,\qquad
E=\tfrac12\|\omega\|_2^2=\|S\|_2^2,\qquad
G=\tfrac12\|\nabla\omega\|_2^2=\|S\|_{\dot H^1}^2,
$$

$$
\mathcal C=\langle u,\Lambda u\rangle,
\qquad
Y=\langle u,\Lambda^3u\rangle,
$$

$$
H=\langle u,\omega\rangle,
\qquad
J=\langle\omega,\nabla\times\omega\rangle,
$$

and

$$
\mathcal A=\langle\Lambda^2u,B\rangle
=\int\omega\cdot S\omega\,dx,
\qquad
F=\langle\Lambda u,B\rangle.
$$

The exact budgets used below are

$$
K'=-2\nu E,\qquad
E'=\mathcal A-2\nu G,\qquad
\mathcal C'=2F-2\nu Y,\qquad
H'=-2\nu J.
$$

For each nonzero Fourier mode choose curl eigenvectors $h_\sigma(k)$ with

$$
i k\times h_\sigma(k)=\sigma|k|h_\sigma(k),
\qquad \sigma\in\{-1,+1\}.
$$

The signed helical spectral-energy measure $d\mu(x)$ puts the energy of $u_\sigma(k)$ at $x=\sigma|k|$. Its first five moments are

$$
(M_0,M_1,M_2,M_3,M_4)=(2K,H,2E,J,2G).
$$

The radial measure is the pushforward under $x\mapsto|x|$ and has odd moments $\mathcal C$ and $Y$ in place of $H$ and $J$.

## 2. Fixed exact targets

The verifier checks the following identities, coefficients and fixtures.

1. For $K>0$, define the canonical Beltrami coefficient and residual
   $$
   \lambda_B=\frac{H}{2K},\qquad r_B=\omega-\lambda_Bu.
   $$
   The exact square completion is
   $$
   \|\omega-\lambda u\|_2^2
   =2E-2\lambda H+2K\lambda^2
   =D_B+2K(\lambda-\lambda_B)^2,
   $$
   where
   $$
   D_B=\|r_B\|_2^2
   =2E-\frac{H^2}{2K}.
   $$
   Set
   $$
   \mathcal V_B=KE-H^2/4=\frac K2D_B.
   $$
   Then
   $$
   \boxed{
   \mathcal V_B=\frac18\iint(x-y)^2\,d\mu(x)d\mu(y)\ge0.}
   $$

2. With
   $$
   D_{B,1}=\|\nabla r_B\|_2^2
   =2G-2\lambda_BJ+2E\lambda_B^2,
   $$
   verify
   $$
   \boxed{
   \mathcal Q_B:=2KG+2E^2-HJ
   =E D_B+K D_{B,1}
   =\frac14\iint(x-y)^2(x^2+y^2)\,d\mu(x)d\mu(y)\ge0.}
   $$

3. Let
   $$
   \mathcal C_+=\int_{x>0}|x|\,d\mu,
   \qquad
   \mathcal C_-=\int_{x<0}|x|\,d\mu,
   $$
   and define $Y_\pm$ analogously with $|x|^3$. Thus
   $$
   \mathcal C=\mathcal C_++\mathcal C_-,\quad
   H=\mathcal C_+-\mathcal C_-,\quad
   Y=Y_++Y_-,\quad
   J=Y_+-Y_-.
   $$
   For the radial spread quantities
   $$
   \mathcal V=KE-\mathcal C^2/4,
   \qquad
   \mathcal Q=2KG+2E^2-\mathcal C Y,
   $$
   check
   $$
   \boxed{\mathcal V_B=\mathcal V+\mathcal C_+\mathcal C_-},
   $$
   $$
   \boxed{
   \mathcal Q_B=\mathcal Q
   +2(\mathcal C_+Y_-+\mathcal C_-Y_+).}
   $$
   The additional terms are the exact opposite-helicity mixing penalties. They vanish on one curl sign. A single radial shell can have $\mathcal V=0$ and $\mathcal V_B>0$ when both signs are present.

4. Differentiate the moments using the budgets in §1. Verify
   $$
   \boxed{\mathcal V_B'+\nu\mathcal Q_B=K\mathcal A,}
   $$
   and
   $$
   \boxed{
   (\mathcal C_+\mathcal C_-)'
   =\mathcal C F
   -\nu\left(\mathcal C Y-HJ\right).}
   $$
   Helicity conservation removes nonlinear work from $H$ but does not sign the transfer $F$ that creates opposite-sign mixing.

5. For any scalar $\lambda(t)$, integration by parts and incompressibility give
   $$
   \langle u,S\omega\rangle=0,
   \qquad
   \mathcal A
   =\langle\omega,S\omega\rangle
   =\langle\omega-\lambda u,S\omega\rangle.
   $$
   Fix $\lambda=\lambda_B$ and let $c_B$ dominate the fixed-domain Sobolev constants in
   $$
   \|S\|_6\le c_B\sqrt G,
   \qquad
   \|u\|_6\le c_B\sqrt{2E}.
   $$
   With $R_B=\|r_B\|_3$, verify the coefficients in
   $$
   |\mathcal A|\le c_B\sqrt{2EG}\,R_B
   \le\nu G+\frac{c_B^2}{2\nu}ER_B^2,
   $$
   and hence
   $$
   \boxed{
   E'+\nu G\le\frac{c_B^2}{2\nu}R_B^2E.}
   $$
   Therefore
   $$
   \boxed{
   I_B(T):=\int_0^T\|\omega-\lambda_Bu\|_3^2\,dt<\infty}
   $$
   is a conditional continuation criterion at a finite smooth endpoint. The verifier checks the exact cancellation and Young square; the standard enstrophy continuation step is supplied analytically.

6. Under the Euclidean Navier–Stokes scaling
   $$
   u_\rho(x,t)=\rho u(\rho x,\rho^2t),
   $$
   check
   $$
   \lambda_{B,\rho}=\rho\lambda_B,
   \qquad
   r_{B,\rho}(x,t)=\rho^2r_B(\rho x,\rho^2t),
   $$
   and the invariance of $I_B$. The criterion is scale-critical rather than a subcritical reformulation.

7. The radial-spread production from the preceding analysis has the centered form
   $$
   \mathscr P_{\mathcal V}
   =K\langle(\Lambda-m)^2u,B\rangle,
   \qquad
   m=\frac{\mathcal C}{2K},
   $$
   with
   $$
   \|(\Lambda-m)^2u\|_2^2\le\mathcal Q/K.
   $$
   Since $B=\mathbb P(u\times r_B)$, verify
   $$
   \boxed{
   |\mathscr P_{\mathcal V}|
   \le c_B\sqrt{2KE\mathcal Q}\,R_B
   \le\frac\nu2\mathcal Q
   +\frac{c_B^2}{\nu}KER_B^2.}
   $$
   If $I=I_B(t)$, the enstrophy estimate from Target 5, $K(t)\le K_0$, and
   $\mathcal V'+\nu\mathcal Q=\mathscr P_{\mathcal V}$ give
   $$
   \boxed{
   \int_0^t(\mathscr P_{\mathcal V})_+\,ds
   \le\mathcal V(0)
   +\frac{2c_B^2K_0E_0}{\nu}
   I\exp\!\left(\frac{c_B^2I}{2\nu}\right).}
   $$
   Thus $I_B(T)<\infty$ supplies the unresolved cumulative positive-production condition. An arbitrary-data estimate for $I_B$ is not assumed.

8. Check three fixed velocity controls with volume-normalized integrals.

   - The exact Beltrami heat flow
     $$
     u=a e^{-\nu n^2t}(\sin nz,\cos nz,0)
     $$
     has $\omega=nu$, $\mathcal V=\mathcal V_B=\mathcal Q=\mathcal Q_B=0$.
   - The exact shear heat flow
     $$
     u=a e^{-\nu n^2t}(\sin ny,0,0)
     $$
     has $H=J=\mathcal V=\mathcal Q=0$ but
     $$
     \mathcal V_B=\frac{a^4n^2e^{-4\nu n^2t}}{16},
     \qquad
     \mathcal Q_B=4n^2\mathcal V_B.
     $$
     A nonzero Beltrami defect is therefore not itself evidence of singular behavior.
   - The smooth divergence-free periodic datum
     $$
     u=(0,1,1)\cos x+(1,0,1)\cos y+(1,-1,1)\sin(x+y)
     $$
     has
     $$
     K=\frac74,\quad E=\frac52,\quad G=4,
     \quad H=J=0,
     $$
     $$
     \mathcal C=2+\frac{3\sqrt2}{2},
     \quad Y=2+3\sqrt2,
     \quad \mathcal A=\frac12.
     $$
     It checks the cancellation
     $\langle\omega-\lambda u,S\omega\rangle=\mathcal A$
     at fixed nonzero values of $\lambda$ and shows that zero total helicity does not cancel vortex stretching.

9. For a positive normalized doublet
   $$
   Z=(\sqrt c\,e^{i\theta_Y},\sqrt{1-c}\,e^{i\theta_I}),
   \qquad
   \alpha=\theta_Y-\theta_I,
   $$
   define
   $$
   A=-iZ^\dagger dZ=d\theta_I+c\,d\alpha,
   \qquad
   n=Z^\dagger\sigma Z.
   $$
   Check the exact identities
   $$
   |\nabla Z|^2=|A|^2+\frac14|\nabla n|^2,
   $$
   $$
   \omega_i=\frac{\kappa}{4}\epsilon_{ijk}
   n\cdot(\partial_jn\times\partial_kn),
   \qquad u=\kappa A,
   $$
   and the pointwise singular-value bound
   $$
   \boxed{|\omega|\le\frac\kappa4|\nabla n|^2.}
   $$
   This gives an $L^1$ vorticity bound from first-order projective energy, not an $L^2$ enstrophy bound.

10. Fix $\delta=1/4$ and Schwartz functions on $\mathbb R^3$,
    $$
    a(y)=\delta e^{-|y|^2},
    \qquad b(y)=y_1e^{-|y|^2}.
    $$
    For $0<\varepsilon\le1$, set
    $$
    c_\varepsilon(x)=\frac12+a(x/\varepsilon),
    \qquad
    \alpha_\varepsilon(x)=\varepsilon^{-1/2}b(x/\varepsilon),
    $$
    $$
    A_\varepsilon=\mathbb P(c_\varepsilon\nabla\alpha_\varepsilon),
    \qquad u_\varepsilon=\kappa A_\varepsilon.
    $$
    Choose the decaying potential
    $$
    \theta_{I,\varepsilon}
    =-\frac12\alpha_\varepsilon
    -\Delta^{-1}\nabla\cdot
    \bigl(a(x/\varepsilon)\nabla\alpha_\varepsilon\bigr),
    \qquad
    \theta_{Y,\varepsilon}=\theta_{I,\varepsilon}+\alpha_\varepsilon.
    $$
    This realizes the displayed $A_\varepsilon$ in a single positive chart. Verify
    $$
    \int_{\mathbb R^3}|\nabla a\times\nabla b|^2dy
    =\frac{\delta^2\pi^{3/2}}8,
    $$
    and consequently
    $$
    \boxed{
    \|\omega_\varepsilon\|_2^2
    =\frac{\kappa^2\delta^2\pi^{3/2}}{8\varepsilon^2}.}
    $$
    Meanwhile
    $$
    \int|\nabla Z_\varepsilon|^2dx
    =P_0+\varepsilon P_1,
    \qquad 0<P_0,P_1<\infty,
    $$
    with
    $$
    P_0=\|\mathbb P(a\nabla b)\|_2^2
    +\int c(1-c)|\nabla b|^2dy,
    $$
    $$
    P_1=\int\frac{|\nabla a|^2}{4c(1-c)}dy,
    \qquad c=\frac12+a.
    $$
    The global positive chart has $H=0$, so $\lambda_B=0$ and $r_B=\omega$. The verifier checks the additional scaling
    $$
    \|r_{B,\varepsilon}\|_3^2
    =\varepsilon^{-3}\|r_{B,1}\|_3^2.
    $$
    Hence a bounded sublevel of the first-order doublet gradient energy contains smooth fields with unbounded enstrophy and unbounded instantaneous $L^3$ Beltrami residual. This contradicts a static coercive closure of Target 5 by that energy alone. It does not rule out a dynamical restriction selected by the full bubble state, a higher-order curvature energy or an initial-$H^3$-dependent estimate.

The $K=0$ case is stated separately: then $u=\omega=0$ and the residual identities are trivial. The concentrating family is one-band and kinematic; no Cassi or Navier–Stokes trajectory is assigned to it.

## 3. Fixed symbolic controls

Use exact SymPy expressions only. Check the signed-moment identities symbolically and again on the fixed positive atomic measure with supports $-3,-1,2,5$ and weights $1/10,1/5,3/10,2/5$. Check the radial/helical split from independently accumulated positive and negative moments. Check every Young remainder by expanding it as a square.

Evaluate the three periodic controls by direct symbolic differentiation and volume-normalized trigonometric integration, not by substituting the target values. Check the Gaussian cross-gradient before evaluating its exact integral by Gaussian moments. Check all dilation exponents symbolically. Every named check is unique. Empty results, a failed exact equality, a failed sign assertion or a nonfinite serialized expression fail the run. No floating-point tolerance is used.

## 4. Decision and stopping rule

The fixed analytical classification is **PASS** only if every exact, atomic, periodic and Gaussian check passes. Any failure is **FAIL**. On **PASS**, the scientific classification is limited to:

- **DERIVED CONDITIONAL REDUCTION** for the helical-spread identities, the critical $L_t^2L_x^3$ Beltrami-residual criterion and its implication for cumulative radial-spread production;
- **CONTRADICTS** for control of enstrophy or the instantaneous $L^3$ Beltrami residual by a bounded first-order positive-doublet gradient-energy sublevel;
- **UNRESOLVED** for an arbitrary-data bound on $I_B$, a full-bubble dynamical exclusion of the concentrating family, and global regularity.

Run the frozen verifier once after its source is complete. An implementation defect may be repaired with the failed receipt retained, no target changed and a fresh output path. Do not add trajectories, fit exponents, vary the Gaussian profile or search helical mixtures after observing the result.

## 5. Evidence paths

From the CassiTheory root, run:

```
python computations/verify_navier_stokes_helical_spread.py \
  --output runs/navier_stokes_helical_spread/verification.json
```

The verifier writes an immutable JSON receipt, an adjacent input manifest and source snapshots. Generated evidence remains local and is indexed in `BROKEN_REFS.md`.

- `turbulence/navier-stokes-strain-departure.md`—analytical proof, scope and prior radial-spread criterion.
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—positive-doublet phase-current and topology identities.
- `computations/verify_navier_stokes_helical_spread.py`—fixed exact verification.
- E. Miller, [Global regularity for solutions of the Navier–Stokes equation sufficiently close to being eigenfunctions of the Laplacian](https://arxiv.org/abs/2005.14152)—established near-eigenfunction criterion.
- Z. Grujić and L. Xu, [Time-averaging of the 3D Navier–Stokes equations and near-Beltrami dynamics](https://arxiv.org/abs/1608.05658)—near-Beltrami context.
- L. C. Berselli and D. Córdoba, [On the regularity of the solutions to the 3D Navier–Stokes equations: a remark on the role of the helicity](https://doi.org/10.1016/j.crma.2009.03.003)—velocity–vorticity alignment context.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—original problem alternatives.
