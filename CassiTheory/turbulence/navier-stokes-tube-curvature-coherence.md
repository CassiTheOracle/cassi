# Tube Curvature, Azimuthal Neutrality, and the Vorticity-Direction Coherence Modulus

## Status: Derived exact tube identities and exact material transport of the cross-section scale and the curvature / Tested finite-grid curvature laws and resolution requirement / Measured flux-based width transport on the retained helical families at a converged patch quadrature, with its viscous profile spread and its span dependence / Conditional direction-coherence modulus—September 2026

## Abstract

A thin tube of vorticity is the empirically dominant structure of the high-vorticity region, and the Constantin–Fefferman continuation criterion asks for the spatial coherence of the vorticity direction there. This paper supplies the geometry of that coherence from an exactly relaxed cross-section. In adapted tube coordinates the curvature enters every cross-sectional functional through one metric factor $g=1+\kappa a\cos\phi$. A $\phi$-independent density is then **exactly** curvature-independent, because the curvature term is a $\cos\phi$ that integrates out, while a density carrying the axial derivative picks up the exact factor $1/\sqrt{1-(\kappa a)^2}$. Two consequences follow: the azimuthal (circulation) channel of a bent tube carries no curvature signature at any order, and the axial (twist) channel is **strictly enhanced** by curvature, never depleted, with a pole at $\kappa a\to1$ where the tube's outer edge reaches the axis of curvature. The coherence modulus of a tube-like high-vorticity region is therefore its bending radius, its failure is the pole, and its value is not free: the cross-section solve fixes the tube radius from the charge per unit length. This explains the positive signed production measured for coherent one-handed tube families in `turbulence/navier-stokes-helical-dynamic-depletion.md`: no cross-section-level curvature channel can deplete stretching. The material transport of the cross-section scale is exact: vorticity flux is conserved through a material element up to diffusion, and the enstrophy identity cancels that diffusion against the growth of the magnitude, leaving the cross-section scale falling at half the axial stretching and the coherence margin moving by a bending increment against an endpoint logarithm of the enstrophy. The bending channel is closed in the same way: the curvature of the vortex line transports by a bending gradient, the axial stretching and the viscous direction transport, so the margin's material rate is complete, every term of it is a critical norm weighted by the tube's own width, and a finite-time bound reduces to integrability of those weighted norms. The time integrability of the coherence modulus remains open.

## 1. Setting and conventions

Let a tube have an axis of curvature $\kappa=1/R$ with adapted coordinates $(s,a,\phi)$: $s$ along the axis, $a$ across it, $\phi$ around it. For a circular axis the volume element is

$$
dV=g\,a\,da\,d\phi\,ds,\qquad g=1+\kappa a\cos\phi,
\tag{1}
$$

and the axial derivative carries the inverse metric factor,

$$
\partial_s=\frac{1}{gR}\,\partial_\theta .
\tag{2}
$$

Every curvature effect on a cross-sectional functional therefore enters through the single factor $g$. Two vorticity channels are distinguished. The **azimuthal channel** carries the circulation: its density is $\phi$-independent for an axisymmetric core. The **axial channel** carries the twist or winding: its density contains the axial derivative of (2).

The curvature laws below are measured on the exactly relaxed Cassi carrier tube of `foundations/core-trapped-charge-support.md` §8.4, where the cross-section is obtained by a variational solve rather than imposed, and the same geometry applies to any tube-like structure through (1)–(2).

## 2. Exact neutrality of the azimuthal channel

For a $\phi$-independent density $F(a)$ the measure factor integrates out,

$$
\int_0^{2\pi} g\,d\phi\,F(a)=2\pi F(a),
\tag{3}
$$

because $\int_0^{2\pi}\cos\phi\,d\phi=0$. The azimuthal channel is therefore **exactly** curvature-independent, at every order in $\kappa a$, and not merely to leading order.

For a vortex tube with an axisymmetric core the azimuthal vorticity and the azimuthal velocity have $\phi$-independent densities, $\omega_\theta^2(a)$ and $u_\theta^2(a)=\Gamma^2/(4\pi^2a^2)$. Their cross-sectional integrals are neutral by (3), so the core enstrophy and the local core kinetic energy of a bent tube equal those of the straight tube with the same circulation and core profile.

The identity is measured on the relaxed profile over an eightfold-deep metric excursion: the cross-section energy difference from the straight tube is **exactly zero** for $\kappa a_{\max}$ up to $0.9836$, where the metric factor falls to $g_{\min}=0.016$. A bending tube's core carries no curvature signature.

## 3. The axial channel: exact enhancement, strict sign, and the pole

A density carrying the axial derivative acquires the inverse square of (1) per coordinate cell, and the measure supplies one power back, so the product is $1/g$:

$$
\int g\,a\,da\,d\phi\,\frac{\rho(a)}{g^2}
=\int a\,da\,\rho(a)\int_0^{2\pi}\frac{d\phi}{1+\kappa a\cos\phi}.
\tag{4}
$$

The azimuthal integral is elementary,

$$
\int_0^{2\pi}\frac{d\phi}{1+\kappa a\cos\phi}
=\frac{2\pi}{\sqrt{1-(\kappa a)^2}},
\tag{5}
$$

so the axial channel of a bent tube is

$$
E_{\rm ax}=\mathcal K\int_0^{a_{\rm out}}
\frac{a\,da\,\rho(a)}{\sqrt{1-(\kappa a)^2}} .
\tag{6}
$$

Two properties of (5)–(6) carry the consequences.

**Strict enhancement.** The factor exceeds one for every $\kappa a>0$. Curvature raises the axial channel's energy, and no arrangement of the cross-section reverses that sign.

**The pole.** The factor diverges as $\kappa a_{\rm out}\to1$, where the tube's outer edge reaches the axis of curvature. A tube in a bend must keep its support strictly inside its bending radius; at the pole the axial channel carries unbounded energy and the tube ceases to be a tube.

At weak curvature (5) expands term by term inside the charge average,

$$
\left\langle\frac{1}{\sqrt{1-(\kappa a)^2}}\right\rangle
=1+\frac{\kappa^2}{2}\langle a^2\rangle
+\frac{3\kappa^4}{8}\langle a^4\rangle+\cdots,
\tag{7}
$$

which is measured against the profile's own moments: at $R=32$ the measured enhancement is $1.000899480$ and the two-term series of (7) gives $1.000899459$ from the profile's charge-weighted moments alone.

| $R$ | 32 | 16 | 12 | 8 | 6.5 | 6.1 |
|---|---|---|---|---|---|---|
| $\kappa a_{\max}$ | 0.188 | 0.375 | 0.500 | 0.750 | 0.923 | 0.984 |
| enhancement | 1.000899 | 1.003636 | 1.006536 | 1.015227 | 1.023962 | 1.027732 |

## 4. The coherence modulus of a tube-like region

Constantin and Fefferman require, on the high-vorticity region,

$$
|\sin\angle(\omega(x,t),\omega(y,t))|\le\frac{|x-y|}{\rho}
\tag{8}
$$

for a coherence length $\rho$. For a tube, the direction varies across a cross-section only through the axial channel of §3: the azimuthal channel is exactly coherent by (3), while the axial variation is $O(\kappa a)$ by (2). The Lipschitz modulus of (8) is therefore

$$
\rho=R=\frac1\kappa
\tag{9}
$$

for a tube-like region, with failure at the pole $\kappa a_{\rm out}\to1$ of §3. The geometric identification (9) is treated as an interpretation in the vortex-tube literature; what the present calculation supplies is the exact variational structure behind it, the strict sign of §3, and the failure condition.

**The modulus is not a free field.** The cross-section solve fixes the tube radius from its charge per unit length, so the aspect ratio $\kappa a$ is a function of the tube's charge and its curvature rather than an independent field. The measured flat-tube radii are $a_{\rm rms}=1.26,\ 1.77,\ 2.37$ at $n=8,\ 24,\ 48$ charge per unit length, which give

$$
\kappa a_{\rm rms}=0.16,\ 0.22,\ 0.30\ \ (R=8);
\qquad
0.21,\ 0.29,\ 0.40\ \ (R=6).
\tag{10}
$$

A denser tube has a smaller coherence margin in a given bend, and the margin is computable from the charge.

**Region level.** The high-vorticity set is a union of tubes, so the coherence length of the region is the smaller of the bending radius (9) and the separation between neighbouring tubes. The second branch is the classical Kolmogorov-scale estimate for the coherence length along vortex lines; the first is the bending branch supplied by the geometry of (1).

## 5. The sign of geometric depletion

`turbulence/navier-stokes-helical-dynamic-depletion.md` measures coherent one-handed tube families in a finite Fourier–Galerkin matrix and reports positive signed production at every checkpoint, a **CONTRADICTS** verdict for the claim that handedness or coherence alone depletes stretching.

Sections 2 and 3 state why. The core carries no curvature signature at all by (3), and the only curvature dependence of the axial channel is the strictly enhancing factor of (5). No cross-section-level curvature channel can deplete the stretching term. Depletion has to come from the axis, that is from the nonlocal Biot–Savart geometry that `turbulence/navier-stokes-stress-geometry.md` already uses for its direction estimate, and the present result fixes the geometric content that estimate must respect: the core is inert, the curvature sign is fixed, and the coherence length is the bending radius until the pole.

## 6. Material transport of the cross-section scale and the curvature

The modulus of §4 is static geometry. Its evolution along the flow is fixed by one conservation law and one identity, both exact.

**Flux conservation.** The vorticity flux through a material surface element $S$ with unit normal $N$ obeys

$$
\frac{d}{d\tau}\int_S\omega\!\cdot\!N\,dA=\nu\int_S\Delta\omega\!\cdot\!N\,dA ,
\tag{11}
$$

the inviscid part being Helmholtz's transport of vortex lines and the viscous part the diffusion of vorticity across the element. Read locally on a flux tube, whose element normal is the direction $\xi$,

$$
\frac{d}{d\tau}\log\Gamma=\nu\,\frac{\omega\!\cdot\!\Delta\omega}{|\omega|^2},
\tag{12}
$$

with $\Gamma$ the flux through the element.

**Cross-section scale.** Let $a$ be the tube's cross-section scale, $\pi a^2$ the area the tube cuts perpendicular to $\xi$; equivalently $a^2=\Gamma/(\pi|\omega|)$. The enstrophy identity (KC3) of `turbulence/navier-stokes-curvature-clock.md` §6,

$$
D_\tau\log|\omega|=\ell+\nu\,\frac{\omega\!\cdot\!\Delta\omega}{|\omega|^2},
\qquad \ell=\xi\!\cdot\!S\xi ,
\tag{13}
$$

cancels the viscous term of (12) exactly:

$$
D_\tau\log a=-\frac{\ell}{2}.
\tag{14}
$$

The transverse rate is the frame closure (KF) of the same note, $n\!\cdot\!Sn+b\!\cdot\!Sb=-\ell$: the cross-section falls at the rate carried by the two directions across it.

**Integrated form.** With $e=\frac12|\omega|^2$ and $\Delta$ the increment along the trajectory,

$$
\log(\kappa a)(T)=\log(\kappa a)(0)+\Delta\log\kappa-\frac14\Delta\log e
+\frac12\nu\int_0^T\frac{\omega\!\cdot\!\Delta\omega}{|\omega|^2}\,d\tau .
\tag{15}
$$

**A mixed criterion.** In (15) the enstrophy enters through an endpoint logarithm while the viscous term enters through an integral; at a point where $|\omega|$ is locally maximal along $n$, $\Delta|\omega|\le0$ caps that integral by $\frac12\nu\int\Delta|\omega|/|\omega|\,d\tau$. Inviscidly the margin is $\kappa a\propto\kappa/\sqrt{|\omega|}$: a tube reaches the pole of §3 only when its bending outruns the decay of the square root of its vorticity magnitude. No cumulative enstrophy appears.

**The bending channel.** The curvature of the vortex line transports with the direction field. With $t=\xi$ and $D_\tau\xi=(\nabla u)\xi-\ell\xi+V$, where

$$
V=\nu\,\frac{\Delta\omega-\xi\,(\omega\!\cdot\!\Delta\omega)/|\omega|}{|\omega|}
\tag{16}
$$

is the viscous direction transport that the vorticity equation adds to the frozen-field reading, the field $\kappa n=(\xi\!\cdot\!\nabla)\xi$ transports as

$$
D_\tau\kappa=n\!\cdot\!\big[((\nabla u)\xi\!\cdot\!\nabla)\xi+(\xi\!\cdot\!\nabla)((\nabla u)\xi)
-((\nabla u)^{\!\top}\xi\!\cdot\!\nabla)\xi\big]-2\ell\kappa
+n\!\cdot\!\big[(V\!\cdot\!\nabla)\xi+(\xi\!\cdot\!\nabla)V\big].
\tag{17}
$$

The first and third entries of the bracket cancel identically, because

$$
((\nabla u)-(\nabla u)^{\!\top})\xi=\omega\times\xi=0
\tag{18}
$$

— the vortex line is an eigenvector of the rotation, so the rotation part of the velocity gradient drops out. The field commutator that distinguishes a curvature field from a material curve's curvature is cancelled by exactly that term. What remains is the strain and the bending,

$$
D_\tau\log\kappa=\frac{n\!\cdot\!(\xi\!\cdot\!\nabla\nabla u)\xi}{\kappa}+n\!\cdot\!Sn-2\ell
+\frac{n\!\cdot\!\big[(V\!\cdot\!\nabla)\xi+(\xi\!\cdot\!\nabla)V\big]}{\kappa}.
\tag{19}
$$

With (14) the margin's material rate is complete,

$$
D_\tau(\kappa a)=a\,n\!\cdot\!(\xi\!\cdot\!\nabla\nabla u)\xi+\kappa a\,n\!\cdot\!Sn
-\tfrac52\kappa a\,\ell+a\,n\!\cdot\!\big[(V\!\cdot\!\nabla)\xi+(\xi\!\cdot\!\nabla)V\big],
\tag{20}
$$

with no cumulative enstrophy and no unresolved channel.

**The criterion this gives.** Every term of (20) is bounded by the critical norms, each weighted by the tube's own width:

$$
\big|D_\tau(\kappa a)\big|\le a\,\|\nabla^2u\|+\tfrac72\,\kappa a\,\|\nabla u\|
+a\,\big\|(V\!\cdot\!\nabla)\xi+(\xi\!\cdot\!\nabla)V\big\| .
\tag{21}
$$

Inside the tube regime $\kappa a<1$, so both weights are bounded and a finite-time bound on the coherence margin follows from $\int_0^T a\,\|\nabla^2u\|_\infty\,d\tau$ and $\int_0^T\kappa a\,\|\nabla u\|_\infty\,d\tau$ being finite — strictly less than an unweighted critical-norm bound, and the second-derivative channel enters only through the width that the margin divides by.

**Which width.** The clock's width channel uses the local scale $a_n=|\omega|^{1/2}(n\!\cdot\!\nabla^2|\omega|\,n)^{-1/2}$, read from the curvature of the magnitude profile; the scale $a$ of (14) is the tube's own cross-section radius, read from its flux. They are different objects, and (14) is the transport that closes: a Gaussian core gives $a=\sqrt2\,a_n$, and $a_n$'s material rate carries the additional rate of $\lambda=n\!\cdot\!\nabla^2|\omega|\,n$ that the clock's measured fiftyfold width gap sits in.

**The measured form.** A flux read over a patch of finite size, rather than at the tube's core, carries the profile spread of the viscous term:

$$
D_\tau\log a=-\tfrac12\ell+S,\qquad
S=\tfrac12\nu\left(\frac{\int_P\Delta\omega\!\cdot\!N\,dA}{\Gamma}
-\frac{\omega\!\cdot\!\Delta\omega}{|\omega|^2}\right),
\tag{22}
$$

the difference between the patch-mean and the core reading of $\nu\,\Delta\omega\!\cdot\!\omega/|\omega|^2$. On the retained helical families this spread is what the deviation from (14) consists of: the deviation of $\log a$ from the ideal $-\tfrac12\int\ell$ is $2.16\times10^{-1}$, $5.06\times10^{-1}$ and $8.85\times10^{-1}$ over one carried window, and the measured spread integral is $2.16\times10^{-1}$, $5.06\times10^{-1}$ and $8.80\times10^{-1}$ — $100.00\%$, $99.94\%$ and $99.44\%$ of it. The flux width therefore widens because viscosity acts differently across the tube's profile than at its centre, not because the inviscid law fails.

**The declared patch.** The width's value is a property of the patch that reads it: at span $4$ the same family's deviation is $1.67\times10^{-1}$ against $2.16\times10^{-1}$ at span $6$, while the spread accounts for $99.88\%$ of it at that span too. The transport (22) holds at every declared patch; the width itself is the flux through the declared patch, so a patch below the tube reads its area and a patch far above it reads the surroundings.

## 7. Boundary

The identities (3) and (5)–(7) are exact for the stated geometry: a circular axis and an axisymmetric cross-section. A non-circular axis or a non-axisymmetric core adds terms outside this derivation, and the pole condition of §3 is a statement about the support of the tube rather than a dynamical theorem. The transport (11)–(15) holds for a flux tube in a viscous incompressible flow; it is a statement about the cross-section scale of the tube-like region, and no claim about arbitrary data or about global regularity follows from it.

The time evolution of the coherence modulus is `turbulence/navier-stokes-curvature-clock.md`: its rate splits exactly into a bending-gradient term, a transverse-strain term and an axial-stretching term, the closed-form controls realize a finite-time pole, exponential growth and exact conservation, and the retained tube families grow the margin through transverse strain as their cores widen, arresting below the pole. A bound on the modulus for finite time from general smooth data is the obligation that `turbulence/navier-stokes-stress-geometry.md` records, and no claim about arbitrary data or about global regularity follows here.

## 8. Evidence

The curvature laws are executed by `computations/matter_formation_tube_geometry.py` and independently reconstructed by `computations/verify_matter_formation_tube_geometry.py` from the retained profiles with their own quadrature and metric assembly.

| Check | Result |
|---|---|
| Cross-section energy equals the straight tube for $\kappa a_{\max}\le0.9836$ | $\max\lvert\Delta E\rvert=0$ exactly (C2.1, C2.2) |
| Winding energy equals the analytic metric integral (5) | max relative deviation $1.05\times10^{-13}$ over $R=32\ldots6.1$ (C4.1) |
| Enhancement equals the moment series (7) | $1.000899480$ versus $1.000899459$ (C4.4) |
| Enhancement grows with curvature | $1.000899\to1.027732$ (C4.3) |
| Tight-torus resolution requirement | coarse $\varphi$ grid deviates by $1.54\times10^{-10}$, fine grid by $1.89\times10^{-14}$ at $R=6.1$ (C4.5) |

The singular $\varphi$ integrand of (5) sets the resolution requirement of the tight rows; the coarse-grid deviation is reported as the measured requirement rather than absorbed into a tolerance.

The transport (11)–(15) is executed by `computations/verify_navier_stokes_tube_modulus_transport.py` on the exact Arnold–Beltrami–Childress flow $\omega=u=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x)$, an unsteady viscous Navier–Stokes solution with curved vortex lines, a time-independent vorticity direction and $\Delta\omega=-\omega$, at $\nu=0.05$ over one time unit from the tracer $(1.1,0.7,0.4)$.

| Check | Result |
|---|---|
| Frame closure $n\!\cdot\!Sn+b\!\cdot\!Sb=-\ell$ | worst $7.2\times10^{-16}$ over 1001 samples (V1) |
| Enstrophy identity against analytic rates | worst $3.8\times10^{-16}$ (V2) |
| Flux transport on a material element, $\Delta\log\Gamma$ against $\nu\int\Delta\omega\!\cdot\!N\,dA/\Gamma$ | worst $8.0\times10^{-4}$ at step $10^{-3}$, $1.6\times10^{-3}$ at $2\times10^{-3}$ (V3) |
| Cross-section scale, $\Delta\log a$ against $-\frac12\int\ell$ | worst $4.0\times10^{-4}$ against $7.9\times10^{-4}$ under refinement (V4) |
| Integrated modulus identity (15) | worst $4.0\times10^{-4}$ against $7.9\times10^{-4}$; the margin moves $+2.407190$, bending $+2.122684$, the enstrophy endpoint $+0.309107$, the viscous integral $-0.025000$ (V5) |
| Viscous term capped where $\lvert\omega\rvert$ is locally maximal along $n$ | 1001 of 1001 samples, worst excess $-1.3\times10^{-2}$ (V6) |
| Curvature transport (19) against finite differences of the curvature field | worst $3.1\times10^{-10}$ over 1001 samples (V7) |
| The rotation part of the velocity gradient drops out, (18) | worst $4.6\times10^{-16}$ (V8) |
| Margin's rate against the width-weighted critical norms, (21) | ratio $0.309$ worst, $0.165$ mean; the terms of (20) sum to the rate to $2.7\times10^{-20}$; bending, strain and axial carry $0.037$, $0.027$ and $0.102$ of the bound (V9) |

The residual is a finite-difference floor: every transport reading halves when the step halves, and the exact identities of V1 and V2 close at round-off. This flow is Beltrami, $\Delta\omega=-\omega$, so the direction transport (16) vanishes identically and V7 exercises the kinematic and inviscid part of (17) exactly; the viscous bracket is derived and named rather than measured here.

The flux width (22) is measured on the retained helical families `helix_wide`, `helix_narrow` and `helix_tight_pitch` by `computations/navier_stokes_flux_width.py`, pre-registered in `computations/navier-stokes-flux-width-prereg.md` and independently re-derived by `computations/verify_navier_stokes_flux_width.py`. A tracer is released at the vorticity core of each family's initial state, carried with a material parallelogram in the budget's stage convention, over $1024$ steps at $\nu=0.1$ to horizon $0.5$ on a $97^3$ lattice at cutoff $16$; the patch is released perpendicular to $\xi$ with side $6\times$ the core's own Hessian width, so it spans the tube rather than sampling a point inside it, and the flux is a three-point Gauss quadrature per patch direction sampled every four steps.

| Check | Result |
|---|---|
| Derivative blocks against the spectral grid derivatives | $2.4\times10^{-16}$ first, $4.4\times10^{-16}$ second (D0) |
| Point evaluator against the grid velocity | $2.2\times10^{-16}$ (D1) |
| Curvature transport (19) with the viscous bracket | $2.1\times10^{-4}$, $7.7\times10^{-4}$, $2.6\times10^{-3}$; without the bracket $2.4\times10^{-3}$, $5.7\times10^{-3}$, $1.2\times10^{-3}$ (D3) |
| Flux lemma (11) on the carried patch | $1.7\times10^{-3}$, $6.3\times10^{-4}$, $6.6\times10^{-3}$ (D4) |
| Enstrophy identity (13) | $1.1\times10^{-4}$, $2.2\times10^{-4}$, $1.2\times10^{-3}$ (D5) |
| Width law (22) after removing the measured spread | $7.8\times10^{-4}$, $2.1\times10^{-4}$, $2.7\times10^{-3}$ (D6) |
| Weighted critical-norm bound (21) | worst ratio $0.078$, $0.157$, $0.245$ (D7) |
| Spread-removed residual across sampling spacings $4,2,1$ | $4.68\times10^{-5}$ at every spacing, spread $3.4\times10^{-9}$ (D9) |

That invocation's instrument does not pass its own checks: the patch quadrature is not converged at order $3$ on the live states, the frame reader's residual of $6.9\times10^{-10}$ is round-off in a ratio that the declared tolerance was tighter than, and a patch at span $9$ measures a different object from one at span $6$. The receipt at `runs/20260922_flux_width` records those failures, and its closure rules stand as measured rather than promoted.

A second protocol, `computations/navier-stokes-flux-width-convergence-prereg.md`, repeats the identities at a six-point quadrature and a span-$4$ control, and writes `runs/20260922_flux_width_converged`.

| Check | Result |
|---|---|
| Patch quadrature at order $6$ against order $8$ | $1.9\times10^{-2}$ relative on the release state (D2) |
| Curvature transport (19) with the viscous bracket | $2.1\times10^{-4}$, $7.7\times10^{-4}$, $2.6\times10^{-3}$ (D3) |
| Flux lemma (11) on the carried patch | $1.0\times10^{-4}$, $3.9\times10^{-4}$, $1.1\times10^{-2}$ (D4) |
| Enstrophy identity (13) | $1.1\times10^{-4}$, $2.2\times10^{-4}$, $1.2\times10^{-3}$ (D5) |
| Width law (22) after removing the measured spread | $2.8\times10^{-6}$, $3.1\times10^{-4}$, $4.9\times10^{-3}$ (D6) |
| Weighted critical-norm bound (21) | worst ratio $0.194$, $0.221$, $0.437$ (D7) |
| Spread-removed residual across sampling spacings $4,2,1$ | $2.57\times10^{-6}$ to $2.59\times10^{-6}$, spread $2.0\times10^{-8}$ (D9) |
| Width deviation at span $4$ against span $6$ | $1.67\times10^{-1}$ against $2.16\times10^{-1}$, gap $4.9\times10^{-2}$ (D8, fails) |

The instrument passes at this quadrature and the closure rules hold: the spread-removed width law closes to $2.8\times10^{-6}$ on the widest family, against $7.8\times10^{-4}$ at the uncorrected order, so the quadrature was the larger part of that residual. The span control fails by its own declared rule, and the receipt's D3 record fails because the producer's curvature tolerance at run time carried the frame reader's value; re-derived against this protocol's declared $10^{-2}$, D3 holds. The independent verifier reads the receipt against the protocol's tolerances and returns **H2**: the closure is measured and the span dependence is a separate finding. The residual floor of D6 and D9 is a property of the identity, not of the sampling spacing.

## References

- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789, DOI `10.1512/iumj.1993.42.42034`—conditional direction-coherence continuation criterion
- H. Beirão da Veiga and L. C. Berselli, “On the regularizing effect of the vorticity direction in incompressible viscous flows,” *Differential and Integral Equations* **15** (2002), no. 3, 345–356—weaker Hölder coherence still suffices
- P. Constantin, I. Procaccia, and D. Segel, “Creation and dynamics of vortex tubes in three-dimensional turbulence,” *Physical Review E* **51** (1995), no. 4, 3207–3222, DOI `10.1103/PhysRevE.51.3207`—vortex-tube coherence length, alignment and the self-stretching rate of aligned tubes
- `foundations/core-trapped-charge-support.md` §8.4—the relaxed transverse tube, its exact bending neutrality and its winding energy
- `computations/matter_formation_tube_geometry.py`, `computations/verify_matter_formation_tube_geometry.py`—the curvature laws, the moment series and the independent reconstruction
- `computations/verify_navier_stokes_tube_modulus_transport.py`—the flux conservation, the cross-section scale transport and the integrated modulus identity on the exact Arnold–Beltrami–Childress flow
- `turbulence/navier-stokes-stress-geometry.md`—filtered stress geometry, the Biot–Savart direction estimate and the critical coherence coefficient
- `turbulence/navier-stokes-helical-dynamic-depletion.md`—coherent helical tube families and their measured positive production
