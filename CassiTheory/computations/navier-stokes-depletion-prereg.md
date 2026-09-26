# Navier–Stokes Fine-Scale Transfer Dynamics: Fixed Verification

## Status: Pre-registered—September 2026

## Abstract

This calculation checks exact coarse/fine transfer identities and instantaneous responses under the original unforced three-dimensional incompressible Navier–Stokes equation. It tests whether zero signed fine-scale transfer necessarily begins to relax, while retaining the separate requirement for a cumulative estimate after viscous absorption. The fixed controls include a single-shell three-dimensional field, a planar two-shell field, a multiscale three-dimensional field and a shear. Algebra and finite Fourier quadrature can qualify these identities and refute a universal instantaneous sign rule. Arbitrary-data continuation requires an additional analytical estimate. This protocol specifies no time-integrated simulation or parameter search.

## 1. Equation and normalization

Use smooth mean-zero real velocities on $(\mathbb R/2\pi\mathbb Z)^3$, with normalized spatial mean and conjugate Fourier pairs. Set
$$
B(u,u)=-\mathbb P[(u\cdot\nabla)u],\qquad
\partial_tu=B(u,u)+\nu\Delta u,
$$
$$
\mathcal C=\sum_{k\ne0}|k||u_k|^2,\qquad
Y=\sum_{k\ne0}|k|^3|u_k|^2,\qquad
F=\langle\Lambda u,B(u,u)\rangle.
$$
Then $\mathcal C'+2\nu Y=2F$. The Gaussian filter has multiplier $g_\ell(k)=\exp(-\ell^2|k|^2/2)$ and positive covariance $\tau_\ell=G_\ell(u\otimes u)-\bar u_\ell\otimes\bar u_\ell$.

For fixed $L>0$, split only the strain: $u_c=G_Lu$, $u_f=u-u_c$, $S_{\ell,c}=\operatorname{sym}\nabla G_\ell u_c$, and $S_{\ell,f}=S_\ell-S_{\ell,c}$. Both contractions retain the full $\tau_\ell$. Define
$$
F_c=\frac1{\sqrt\pi}\int_0^\infty\ell^{-2}\langle-S_{\ell,c}:\tau_\ell\rangle\,d\ell,
\qquad F_f=F-F_c.
$$
The length $L$ is a decomposition parameter. Every velocity mode remains in the equation.

## 2. Identities and prospective estimates

For $a=p+q$, set
$$
z_{a,p,q}=\operatorname{Re}\left[u_a^*\cdot\{-i\mathbb P_a(q\cdot u_p)u_q\}\right],\qquad
s_{a,p,q}=\sqrt{(|a|^2+|p|^2+|q|^2)/2}.
$$
The candidate exact formula to verify is
$$
F_c=\sum_{a=p+q}e^{-L^2|a|^2/2}(|a|-s_{a,p,q})z_{a,p,q}.
$$
The resolved cubic-product term is retained. The $L=0$ sum must equal $F$. Differentiate every cubic slot to obtain $D F_f[B+\nu\Delta u]$; generated directional modes are retained even when absent from the base velocity.

The analytical comparison is
$$
|F_c|\le K_L\|u_0\|_2\mathcal C,
\qquad
K_L=\left(\sum_{k\ne0}|k|^2e^{-L^2|k|^2}\right)^{1/2}.
$$
An all-data sufficient estimate would additionally require $F_f\le\theta\nu Y+a_f(t)\mathcal C$, $0\le\theta<1$, with a time integral of $a_f$ controlled by initial data, viscosity and finite time. No such bound is assumed here. For descriptive absorption diagnostics only, fix $\theta=1/2$ and record $(F_f-\nu Y/2)/\mathcal C$ for nonzero fields. A positive value refutes viscous-only absorption for that field; it does not refute a data-controlled cumulative growth term.

The Gaussian gradient norm on $\mathbb R^3$ and its scaling may be checked symbolically:
$$
\|\nabla G_L\|_2^2=\frac{3}{16\pi^{3/2}L^5}.
$$
The Euclidean Navier–Stokes scaling gives invariant $\mathcal C$ and growth-rate scaling $\lambda^2$. Fixed-torus repeated cells use their actual Fourier normalization and are not identified with Euclidean volume rescaling.

## 3. Fixed fields and analytical responses

Use the following four fields without altering phases or polarizations:

1. **Cyclic field:** $u=(\sin y,\sin z,\sin x)$. Its initial pressure is constant, $F=F_c=F_f=0$, and $\|B\|_2^2=3/4$. Check
   $$
   D F[B]=\frac34(\sqrt2-1),\qquad
   D F_f[B]=(1-e^{-L^2/2})\frac34(\sqrt2-1),\qquad
   D F_f[\nu\Delta u]=0.
   $$
   Also check $\mathcal C(0)=Y(0)=3/2$ and the exact second-derivative budget $\mathcal C''(0)=2D F[B]+6\nu^2$. The resulting local-time expansion is an analytical consequence of smooth local existence; a Taylor polynomial is not a simulated trajectory.
2. **Planar field:** positive Fourier modes $p=(1,0,0)$, $u_p=i(0,1,0)$ and $q=(0,2,0)$, $u_q=i(1,0,0)$, with their conjugates. Check $F=F_f=0$ and
   $$
   D F[B]=\|B\|_2^2(\sqrt5-7/3),
   $$
   $$
   D F_f[B]=\frac{\|B\|_2^2}{3}\left[(1-e^{-L^2/2})(1-\sqrt5)-4(1-e^{-2L^2})(2-\sqrt5)\right].
   $$
3. **Three-coordinate field:** use the exact `three_dimensional_fixture()` from `computations/verify_navier_stokes_transfer.py`, including all conjugates and its independent axial mode. Record its $\mathcal C,Y,F,F_c,F_f$ and differentiated nonlinear and viscous contributions. This is the fixed multiscale nonzero-transfer control.
4. **Shear:** $u=(\sin y,0,0)$. Its nonlinear acceleration and all nonlinear transfer contributions vanish exactly.

Use only $L\in\{1/2,1,2\}$ and $\nu\in\{1/100,1\}$. At amplitude one verify the exact identities, velocity reversal ($F_f$ is odd, $D F_f[B]$ is even, and the viscous derivative is odd), and amplitude degrees two for $\mathcal C,Y$, three for $F,F_c,F_f$ and the viscous derivative, and four for $D F_f[B]$. The absorption table uses only amplitudes $m\in\{1,8\}$ of the four fixed fields, both viscosities and the three lengths. It is a fixed diagnostic schedule, with no fitted coefficient or optimization.

## 4. Independent numerical reconstruction

Use spatial grids $N\in\{16,24,32\}$ for the four amplitude-one fields. Construct their real velocities independently from their prescribed Fourier coefficients; differentiate with FFTs, form the physical advective product, and apply the full Fourier Leray projector, including generated modes. Check the nonlinear direction against the exact sparse result. At $\ell\in\{1/2,1,2\}$ and each fixed $L$, reconstruct the covariance and coarse/fine strain contractions directly in physical space and compare their spatial means with the ordered-triad expression. Reconstruct the instantaneous derivative from velocity and full nonlinear direction; no finite time step is used for these comparisons.

For all-scale integration, independently integrate the ordered exponential difference before taking its square-root closed form. Use Gauss–Legendre orders 128 and 192 on $s\in(0,1)$ with $\ell=s/(1-s)$ and its Jacobian. Evaluate differences with `expm1` to avoid cancellation near zero. Compare the numerical integrals of both the cubic functional and all differentiated slots against the exact expressions for every field and fixed $L$.

Every compared value must be finite. Use normalized discrepancy $|x-y|/\max(1,|x|,|y|)$ and require every comparison to be below $10^{-10}$. A sign used for a numerical classification must have magnitude above $10^{-10}$; exact symbolic zero is handled separately. Check every stated exact identity symbolically. Retain all grid, quadrature, fixture and decomposition rows.

## 5. Decision tree and stopping rule

1. A failed exact identity, nonfinite value or discrepancy at or above $10^{-10}$ gives **INCONCLUSIVE** for the affected scientific classification. Preserve the failure and stop adoption of that inference.
2. If the cyclic identities qualify and $D F_f[B]>0$ at zero $F_f$, the universal claim that zero fine-scale transfer necessarily has nonpositive instantaneous nonlinear response receives **CONTRADICTS**.
3. If qualified rows have both positive and negative $D F_f[B]$, record the measured two-sided response. This excludes a universal sign assignment to the instantaneous response in the supplied class.
4. A qualified positive absorption residual receives **CONTRADICTS** for viscous-only absorption with the specified $\theta=1/2$. A nonpositive schedule does not prove universal absorption and is **INCONCLUSIVE** about that universal claim.
5. The time-integrated depletion estimate and arbitrary-data global regularity remain **UNRESOLVED** unless an independently checked analytical proof closes them. Fixed-mode boundedness and finite quadrature accuracy are insufficient.

Execute the fixed schedule once after protocol and source freeze. A reproducible implementation defect may be repaired while preserving every failed receipt and keeping the mathematical fixtures and thresholds unchanged; use a fresh output path. Do not add fields, resolutions, amplitudes, viscosities, phase scans, time-evolved simulations or tuned growth coefficients. Stop after the fixed controls and independent analytical review are reconciled.

## 6. Execution and evidence

From the CassiTheory directory, run `python computations/verify_navier_stokes_depletion.py`. The default receipt is `runs/navier_stokes_depletion/verification.json`, anchored to the script's CassiTheory root. An existing output is refused; `--output` selects a fresh path. Record raw SHA-256 identities of this protocol, the verifier and its imported transfer-verifier source. Print the quantities and finish `ALL CHECKS PASSED` only when all verification checks pass.

The mathematical record is `turbulence/navier-stokes-depletion-dynamics.md`; its matter-formation comparison is sourced to `computations/matter-formation-continuum-report.md` §§44–50. Register the generated receipt in `BROKEN_REFS.md` and the scoped scientific classifications in `field-experience/probe-outcome-ledger.md`. The earlier transfer/stress protocol and its receipts remain unchanged.

## References

- `turbulence/navier-stokes-transfer-boundary.md`—critical budget, heat-correction obstruction and helical transfer identity.
- `turbulence/navier-stokes-stress-geometry.md`—complete filtered dynamics and geometric counterexamples.
- `computations/verify_navier_stokes_transfer.py`—retained exact Fourier vocabulary and multiscale fixture.
- `computations/matter-formation-continuum-report.md` §§44–50—self-consistent stress, longitudinal response, fixed-population binding and charge-neutral packet scope.
- T. Tao, [Finite time blowup for an averaged three-dimensional Navier–Stokes equation](https://arxiv.org/abs/1402.0290)—obstruction to relying only on generic energy cancellation and scaling estimates.
