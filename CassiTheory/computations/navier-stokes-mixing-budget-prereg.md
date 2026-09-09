# Unforced Navier–Stokes Mixing: Cumulative Critical Budget

## Status: Pre-registered—September 2026

## Abstract

This fixed investigation tests cumulative critical transfer along a globally smooth invariant family of the original unforced periodic Navier–Stokes equation. A decaying shear transports a third velocity component. A comparison-profile error estimate supplies a continuum lower bound; an exact Fourier cancellation supplies a finite upper bound within this family. Numerical trajectories check the reduction and finite-time budget independently. The candidate under examination is a universal budget linear in the initial critical norm. A general nonlinear initial-data bound and arbitrary-data regularity remain open.

## 1. Equation and candidate

Use the $2\pi$ torus, volume-normalized integrals, $\Lambda=(-\Delta)^{1/2}$ and
$$
\mathcal C=\langle u,\Lambda u\rangle,\qquad
Y=\langle u,\Lambda^3u\rangle,\qquad
F=\langle\Lambda u,-\mathbb P[(u\cdot\nabla)u]\rangle.
$$
The viscosity margin is fixed:
$$
\mathcal W_{1/2}(T)=\int_0^T(F-\nu Y/2)_+\,dt.
$$
The candidate is $\mathcal W_{1/2}(T)\le K(\nu,T)\mathcal C(0)$ with finite $K$ independent of the initial datum. The broader objective allows nonlinear dependence on prescribed initial data. All velocities in this investigation are real, smooth, mean-zero and divergence-free. The finite numerical system approximates the infinite Fourier evolution; the analytical argument concerns the exact parabolic solution.

## 2. Exact invariant family

The full velocity is
$$
u(x,y,z,t)=(A e^{-\nu t}\sin y,0,bv(x,y,t)),\qquad p=0,
$$
where
$$
v_t+A e^{-\nu t}\sin y\,v_x=\nu(v_{xx}+v_{yy}),\qquad v(x,y,0)=\sin x.
$$
There is no external force. The two independent variables and the absence of a second velocity component are exact invariant-class assumptions. The passive component has the infinite expansion
$$
v=\sum_{j\in\mathbb Z}c_j(t)\sin(x+jy),\qquad
c_j'=-\nu(1+j^2)c_j-\frac{A e^{-\nu t}}2(c_{j-1}-c_{j+1}).
$$
Only $c_0(0)=1$ is nonzero. Both signs of $j$ and every generated mode belong to the continuum equation. The complete velocity remains odd under spatial inversion.

For the lower-bound family fix $\nu=1$, $A=b=N^3$, and $t_N=1/(2N^2)$, with $N\ge2$. Initial $\mathcal C=N^6$ and all initial nonzero modes have frequency radius one. The analytical targets are
$$
\mathcal C(t_N)\ge N^7/64,\qquad
\mathcal W_{1/2}(t_N)\ge N^7/128-N^6/2.
$$
A separate exact cancellation is to bound
$$
\mathcal W_{1/2}(T)\le\frac{|A|b^2}{12\nu}(1-e^{-3\nu T})
$$
within this invariant family. All three statements require the analytical derivations; numerical agreement alone supplies no continuum proof.

## 3. Analytical controls

Use $a=A(1-e^{-t})$ and the transport comparison $v_{\rm app}=\sin(x-a\sin y)$ for $\nu=1$. Differentiate its full residual in the parabolic equation. Compute its normalized $L^2$, gradient, Laplacian, $x$-Laplacian-derivative and $y$-Laplacian-derivative moments exactly. Verify the interpolation lower bound $\mathcal C[v_{\rm app}]\ge a/4$ and all nonnegative-polynomial estimates used in the error bounds
$$
B_0=\frac{t+A^2t^3/3}{\sqrt2},\qquad
B_y=At^2\left(\frac12+\frac1{2\sqrt2}\right)
+A^3t^4\left(\frac14+\frac1{12\sqrt2}\right).
$$
The exact error $e=v-v_{\rm app}$ must satisfy $\|e\|_2,\|e_x\|_2\le B_0$ and $\|e_y\|_2\le B_y$. Check the derivative commutator, the critical interpolation bound $\|e\|_{\dot H^{1/2}}^2\le B_0\sqrt{B_0^2+B_y^2}$, the uniform constant $23/9+\sqrt2<4$, and the reverse-triangle conversion. Independent analytical review must check the global smoothness and all quantifiers.

The retained full Leray-convolution helper independently checks the Fourier pairing and its factors on a fixed finite signed coefficient sequence. Add a constant mean to that same field to check invariance of $\mathcal C,Y,F$ under constant advection; the time-dependent Galilean transformation is justified analytically. The zero-shear control is the exact viscous decay of $\sin x$, with zero nonlinear work and zero excess budget.

## 4. Fixed numerical schedule

The only trajectory parameters are $N=2,4,8,16,32,64,128,256$. Evolve scaled time $s=N^2t\in[0,1/2]$, normalized velocity $u/N^3$, and $c_j$. This retains the viscosity coefficient $N^{-2}$ and shear coefficient $N e^{-s/N^2}$.

For every $N$, integrate two symmetric Fourier cutoffs:

- $|j|\le\max(32,2N)$ with DOP853, relative tolerance $10^{-11}$ and absolute tolerance $10^{-13}$;
- $|j|\le\max(48,3N)$ with DOP853, relative tolerance $10^{-13}$ and absolute tolerance $10^{-15}$.

Both use maximum scaled step $1/(8N)$ and 1,001 equally spaced output times. Integrate signed critical work, critical dissipation, kinetic dissipation and the positive-part excess alongside the Fourier coefficients. Retain all sampled coefficients and budgets in an adjacent NPZ artifact.

At scaled times $0,1/8,1/4,3/8,1/2$, reconstruct the finer solution on an independent $8\times(4M+8)$ periodic grid, where $M$ is its Fourier cutoff. Compute the three-component velocity, spatial derivatives, complete convection and Leray projection, critical work, critical norm, dissipation and kinetic energy from those fields. Compare the full momentum equation with the integrator's coefficient derivative. The suppressed spatial coordinate has zero derivative. Resolve all convolution products; record the generated endpoint residual, incompressibility and odd-phase discrepancies.

Record for every physical case: $\mathcal C(t_N)/\mathcal C(0)$, $\mathcal W_{1/2}(t_N)/\mathcal C(0)$, the exact uniform lower bound, the sharper comparison-profile lower bound, the finite-family upper bound, signed-work and dissipation integrals, and the maximum error in every cross-resolution or independent-spatial comparison.

## 5. Decision tree and stopping rule

Every symbolic identity must agree exactly. Each numerical comparison uses absolute error divided by $\max(1,|\text{left}|,|\text{right}|)$ and must be below $10^{-8}$. This includes coefficient convergence, integrated kinetic and critical balances, the independent spatial quantities and the exact no-shear control. All states and outputs must be finite; the normalized passive $L^2$ energy must satisfy its Poincare decay bound to the same tolerance.

The numerical-reduction classification is **PASS** only when all checks pass; otherwise it is **FAIL**. The finite control $\mathcal W_{1/2}(t_{256})\le\mathcal C(0)$ is **CONTRADICTS** only when the continuum lower bound exceeds one and the qualified numerical trajectory also exceeds one; otherwise its classification is **INCONCLUSIVE**. The impossibility of every finite amplitude-independent coefficient $K(\nu,T)$ is a separate analytical consequence of the unbounded $N$ family. General data-controlled closure and arbitrary-data regularity remain **UNRESOLVED**.

Execute this fixed schedule once after the protocol and source freeze. Implementation errors may be repaired with all failed artifacts retained and a fresh output path. Do not change the parameters, tolerances, cutoff rule or classifications in response to a result. No fitting, arbitrary three-dimensional perturbation campaign, singularity search, forced construction, or formal-proof build belongs to this investigation.

## 6. Evidence and references

Run `python computations/verify_navier_stokes_mixing_budget.py` from CassiTheory. The default output is `runs/navier_stokes_mixing_budget/verification.json`; reproductions must use a fresh `--output` path. Preserve raw source snapshots and SHA-256 identities for the protocol, verifier and both local imported helpers. Record library versions, the raw trajectory artifact hash and every control outcome. Generated evidence remains local and is indexed in `BROKEN_REFS.md`. Publication remains outside this task.

- `turbulence/navier-stokes-strain-departure.md`—critical budget, continuation conventions and cumulative-transfer analysis.
- `computations/verify_navier_stokes_mixing_budget.py`—fixed analytical controls, invariant-class trajectories and independent spatial reconstruction.
- `computations/verify_navier_stokes_depletion.py`—duplicate-safe receipt handling and finite JSON serialization.
- `computations/verify_navier_stokes_transfer.py`—full ordered Leray convolution and normalized Fourier pairings.
