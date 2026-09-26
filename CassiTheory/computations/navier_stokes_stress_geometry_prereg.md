# Navier–Stokes Transfer and Stress-Geometry Verification

## Status: Pre-registered—September 2026

## Abstract

This protocol fixes reproducible checks of exact Navier–Stokes transfer identities and specific proposed geometric constraints. The calculations concern smooth, admissible initial fields and their full instantaneous Navier–Stokes derivatives. They include an unbounded level set of a cubic corrected energy, an initially isotropic filtered stress, deformation of a prescribed helix, and independently adjustable surrounding strain. The scope contains no numerical time integration, singularity search, or claim of unconditional regularity.

## 1. Question and mathematical scope

Can an instantaneous geometric constraint on velocity stress supply, and dynamically retain, the control required by a positive all-scale concentration norm?

Use original, unforced incompressible Navier–Stokes with positive viscosity:

$$
\partial_t u=\nu\Delta u+B(u,u),\qquad
B(u,u)=-\mathbb P[(u\cdot\nabla)u],\qquad \nabla\cdot u=0.
$$

Periodic fixtures live on $\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3$. Spatial averages are normalized by $(2\pi)^{-3}$; Fourier norms use the matching Parseval sum. The compact-support strain construction and continuum scaling statements concern $\mathbb R^3$. These domain statements must remain separate.

Every finite Fourier calculation uses the full quadratic convolution and Leray projection. Directional derivatives retain contributions through initially absent modes. No Galerkin time evolution is authorized by this protocol.

## 2. Frozen normalization and identities

Let $\Lambda=(-\Delta)^{1/2}$ and define

$$
\mathcal C=\|u\|_{\dot H^{1/2}}^2,\qquad
Y=\|u\|_{\dot H^{3/2}}^2,\qquad
F=\langle\Lambda u,B(u,u)\rangle.
$$

For the spectral curl polarizations $\omega_\pm=\nabla\times u_\pm$, put

$$
I=\langle u\cdot(\omega_-\times\omega_+)\rangle.
$$

The exact conventions are

$$
\mathcal C'+2\nu Y=2F=4I,
\qquad F=\int_0^\infty\Pi(K)\,dK.
$$

Here $\Pi(K)$ is the nonlinear energy-gain rate in modes $|k|>K$. It is a rate; the corresponding positive norm is

$$
\mathcal C=2\int_0^\infty E_{>K}\,dK,
\qquad E_{>K}=\frac12\sum_{|k|>K}|u_k|^2.
$$

Define the auxiliary heat functional and its full nonlinear derivative:

$$
\Phi(u)=\int_0^\infty F(e^{\nu s\Delta}u)\,ds,
\qquad R(u)=D\Phi(u)[B(u,u)].
$$

Each cubic Fourier term has sum divisor $\nu(|a|^2+|p|^2+|q|^2)$, where $a=p+q$. The required identities are

$$
D\Phi(u)[\nu\Delta u]=-F(u),\qquad
(\mathcal C+2\Phi)'+2\nu Y=2R.
$$

For the Gaussian filter with multiplier $e^{-\ell^2|k|^2/2}$, define $\tau_\ell=\overline{u\otimes u}_\ell-\bar u_\ell\otimes\bar u_\ell$, $\bar S_\ell=\operatorname{sym}\nabla\bar u_\ell$, and $\Pi_\ell=-\bar S_\ell:\tau_\ell$. The positive representation is

$$
\mathcal C=\frac1{\sqrt\pi}\int_0^\infty
\ell^{-2}\langle\operatorname{tr}\tau_\ell\rangle\,d\ell.
$$

## 3. Exact transfer controls

### 3.1 Three-coordinate phase-organized field

The positive wavevectors and coefficients are

| Wavevector | Fourier coefficient |
|---|---|
| $p=(1,0,0)$ | $i(0,1,1)$ |
| $q=(0,2,0)$ | $i(1,0,0)$ |
| $k=(1,2,0)$ | $i(-2,1,0)$ |
| $r=(0,0,3)$ | $i(1,0,0)$ |

Negative-wavevector coefficients are complex conjugates. Expected exact values are

$$
\mathcal C_0=14+10\sqrt5,\qquad
F_0=14-6\sqrt5>0,\qquad
\Phi_0=\frac{F_0}{10\nu}.
$$

Check reality, incompressibility, zero nonlinear energy and signed-helicity derivatives, $F=2I$, the heat derivative, and positive full $\mathcal C'$ at amplitude $400$ and $\nu=1$. Record the quartic remainder and the contribution lost by restricting its directional derivative to initially populated modes.

The second, planar fixture retains only $p=i(0,1,0)$ and $q=i(1,0,0)$ with their conjugates. Its exact quartic remainder is a sign control. Both remainders must be reported, including a failed expected sign if the calculation disagrees.

### 3.2 Corrected-energy level set

Multiply the $k$ coefficient by $a+ib$, with $a^2+b^2=1$. Verify algebraically that the modal energies remain unchanged and that $F=aF_0$, $\Phi=a\Phi_0$. For amplitude $A$, set

$$
a=-\frac{5\nu\mathcal C_0}{AF_0},\qquad
A\ge(155+70\sqrt5)\nu.
$$

The decision quantities are $\mathcal C(Au)=A^2\mathcal C_0$ and $\mathcal C(Au)+2\Phi(Au)=0$. This is a family of initial data; it supplies no singular trajectory.

Check also the exact derivative of the positive completion $\mathcal C+2\Phi+\alpha\mathcal C^2/\nu^2$, including its quintic $4\alpha\mathcal C F/\nu^2$ term. For $p\cdot q=0$, explicitly distinguish the heat sum divisor $10\nu$ from the zero difference divisor in a quadratic interaction representation.

## 4. Stress-geometry controls

### 4.1 Pointwise isotropy under the original dynamics

Use

$$
u_0(x,y,z)=(\sin y,\sin z,\sin x).
$$

The variable in this display is $u_0$, the velocity field. Its nonlinear acceleration has zero divergence, so the initial periodic pressure is constant. Evaluate the full instantaneous derivative

$$
\partial_t u\big|_0=
-(\sin z\cos y,\sin x\cos z,\sin y\cos x)-\nu u_0.
$$

At the origin, for each fixed $\ell>0$, let

$$
g=e^{-\ell^2/2},\qquad T=\frac{1-e^{-2\ell^2}}2.
$$

The expected identities are

$$
\bar u=0,\qquad \tau=T\mathbf1,\qquad \Pi_\ell=0,
$$

$$
\partial_t\tau^{\mathrm{dev}}=-2T\bar S,
\qquad
\partial_t\Pi_\ell=2T\bar S:\bar S=3Tg^2>0.
$$

The material and partial derivatives agree at this point because $\bar u=0$. Independently evaluate the filtered quantities by Fourier quadrature on grids $N\in\{16,32,64\}$, at widths $\ell\in\{1/2,1,2\}$ and viscosity $\nu=1$.

Statistics: maximal absolute or scale-normalized discrepancy in $\tau$, $\bar S$, $\partial_t\tau$, $\Pi_\ell$, and $\partial_t\Pi_\ell$; the smallest measured $\partial_t\Pi_\ell$ across the fixed widths; and the generated deviatoric stress. Numerical quality requires discrepancy at most $10^{-10}$ on every grid. The sign decision requires $\partial_t\Pi_\ell>10^{-10}$ on every grid and width.

This challenges preservation of pointwise isotropy at a resolved material point. The initial stress is not assumed isotropic throughout space. No conclusion about every nonlocal or time-integrated geometric constraint follows from this local control.

### 4.2 Double-helix deformation

For equal-speed, equally weighted, zero-mean tangent fluctuations with uniform phase sampling, the axisymmetric covariance model has eigenvalues

$$
U^2\left(\frac{s^2}{2(1+s^2)},\frac{s^2}{2(1+s^2)},
\frac1{1+s^2}\right),\qquad s=ak.
$$

Check its trace, positive semidefiniteness and normalized deviatoric magnitude

$$
\frac{\|\tau^{\mathrm{dev}}\|_F}{\operatorname{tr}\tau}
=\frac{|2-s^2|}{\sqrt6(1+s^2)}.
$$

The sampling and velocity-fluctuation interpretation are supplied assumptions. They do not identify Cassi currents with Navier–Stokes stress.

Under the prescribed incompressible affine strain $\operatorname{diag}(-\sigma/2,-\sigma/2,\sigma)$, each half-turn strand has

$$
\alpha=\sigma\frac{1-s^2/2}{1+s^2},\qquad
s(t)=s_0e^{-3\sigma t/2}.
$$

Use $a_0=2$, $k_0=1$, $\sigma=1$. Record the stretching signs at $t=0$ and $t=1$, and the crossing time $\log2/3$. This is a kinematic deformation control; the globally affine velocity is excluded as a finite-energy Clay datum.

### 4.3 Adjustable admissible surrounding strain

For a trace-free symmetric matrix $M$, use the vector potential $A(x)=-(x\times Mx)/3$. Verify $\nabla\times A=Mx$. A smooth cutoff equal to one in the unit ball and zero outside the ball of radius two gives $v=\nabla\times(\eta A)$, a smooth compactly supported divergence-free velocity. In the inner ball $\nabla v=M$ and $\nabla\times v=0$.

Use $M=\operatorname{diag}(-1/2,-1/2,1)$ for the executable polynomial check. Adding this perturbation preserves local vorticity while changing strain. Its surrounding vorticity supplies the change self-consistently at the initial instant.

### 4.4 Scale and resolution

Check the $\mathbb R^3$ Navier–Stokes rescaling $u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t)$ at matching filter width:

$$
\tau_\ell[u_\lambda](x)=\lambda^2\tau_{\lambda\ell}[u](\lambda x),\quad
\bar S_\ell[u_\lambda](x)=\lambda^2\bar S_{\lambda\ell}[u](\lambda x),\quad
\Pi_\ell[u_\lambda](x)=\lambda^4\Pi_{\lambda\ell}[u](\lambda x).
$$

The all-scale $\mathcal C$ is invariant. The finite quadrature comparison in §4.1 checks normalization and resolved-mode accuracy; it is not a continuum regularity experiment.

## 5. Decision tree and stopping rule

1. An exact identity discrepancy or numerical-quality failure gives **INCONCLUSIVE** for the affected measured inference. Retain its failure; do not change a fixture or threshold to obtain a favorable classification.
2. When §4.1 passes quality and has the specified positive derivative, the assertion that pointwise isotropy alone persists and suppresses subsequent local transfer receives **CONTRADICTS** for this explicit control.
3. When §4.2 reproduces the sign crossing, protection from the supplied helix shape alone receives **CONTRADICTS** under that prescribed deformation.
4. The compact-support construction excludes any universal inference from local vorticity geometry alone to a uniquely determined local strain.
5. Algebraic-verifier **PASS** means identities and counterexamples are reproduced. It does not promote a geometric regulation hypothesis or establish a global solution.
6. Arbitrary-data global regularity remains unresolved unless a separate full analytical estimate controls the all-scale transfer from the original dynamics and initial data.

Execute only the fixed controls above. No parameter search, fitted constant, seed selection, long-time simulation, or higher-resolution extension is part of this run. A verifier implementation defect may be repaired with the discrepancy disclosed; the mathematical fixtures and decision thresholds remain fixed. Stop after all fixed checks and the independent analytical review are reconciled.

## 6. Execution and evidence

From the CassiTheory directory:

```
python computations/verify_navier_stokes_transfer.py
python computations/verify_navier_stokes_stress_geometry.py
```

Each script prints its quantities and finishes `ALL CHECKS PASSED` only when its verification checks succeed. Raw JSON receipts are written to `runs/navier_stokes_transfer/verification.json` and `runs/navier_stokes_stress_geometry/verification.json`. They include script and protocol hashes. These are generated, ignored artifacts. The mathematical records are `turbulence/navier-stokes-transfer-boundary.md` and `turbulence/navier-stokes-stress-geometry.md`; the measured control classifications are indexed in `field-experience/probe-outcome-ledger.md`.

## References

- `turbulence/navier-stokes-transfer-boundary.md`—transfer identities, corrected-energy level sets and analytical estimates.
- `turbulence/navier-stokes-stress-geometry.md`—filtered stress evolution and geometric assumptions.
- `foundations/qi-flow-double-helix.md`—conditional spatial helix and phase-current constructions.
- `foundations/interscale-stress-attenuation-boundary.md`—scale-current and spatial momentum-stress distinctions.
- Eyink and Aluie, [Localness of energy cascade in hydrodynamic turbulence. I. Smooth coarse-graining](https://arxiv.org/abs/0909.2386)—filtering conventions and scale-locality assumptions.
