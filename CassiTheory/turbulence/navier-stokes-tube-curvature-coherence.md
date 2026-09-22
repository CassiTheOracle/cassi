# Tube Curvature, Azimuthal Neutrality, and the Vorticity-Direction Coherence Modulus

## Status: Derived exact tube identities / Tested finite-grid curvature laws and resolution requirement / Conditional direction-coherence modulus—September 2026

## Abstract

A thin tube of vorticity is the empirically dominant structure of the high-vorticity region, and the Constantin–Fefferman continuation criterion asks for the spatial coherence of the vorticity direction there. This paper supplies the geometry of that coherence from an exactly relaxed cross-section. In adapted tube coordinates the curvature enters every cross-sectional functional through one metric factor $g=1+\kappa a\cos\phi$. A $\phi$-independent density is then **exactly** curvature-independent, because the curvature term is a $\cos\phi$ that integrates out, while a density carrying the axial derivative picks up the exact factor $1/\sqrt{1-(\kappa a)^2}$. Two consequences follow: the azimuthal (circulation) channel of a bent tube carries no curvature signature at any order, and the axial (twist) channel is **strictly enhanced** by curvature, never depleted, with a pole at $\kappa a\to1$ where the tube's outer edge reaches the axis of curvature. The coherence modulus of a tube-like high-vorticity region is therefore its bending radius, its failure is the pole, and its value is not free: the cross-section solve fixes the tube radius from the charge per unit length. This explains the positive signed production measured for coherent one-handed tube families in `turbulence/navier-stokes-helical-dynamic-depletion.md`: no cross-section-level curvature channel can deplete stretching. The time integrability of the coherence modulus remains open.

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

## 6. Boundary

The identities (3) and (5)–(7) are exact for the stated geometry: a circular axis and an axisymmetric cross-section. A non-circular axis or a non-axisymmetric core adds terms outside this derivation, and the pole condition of §3 is a statement about the support of the tube rather than a dynamical theorem.

The time integrability of the coherence modulus remains open. Equation (9) identifies $\rho$ with a geometric quantity of the vorticity field, but propagating that quantity from arbitrary smooth data is still the obligation that `turbulence/navier-stokes-stress-geometry.md` records, and no claim about arbitrary data or about global regularity follows here.

## 7. Evidence

The curvature laws are executed by `computations/matter_formation_tube_geometry.py` and independently reconstructed by `computations/verify_matter_formation_tube_geometry.py` from the retained profiles with their own quadrature and metric assembly.

| Check | Result |
|---|---|
| Cross-section energy equals the straight tube for $\kappa a_{\max}\le0.9836$ | $\max\lvert\Delta E\rvert=0$ exactly (C2.1, C2.2) |
| Winding energy equals the analytic metric integral (5) | max relative deviation $1.05\times10^{-13}$ over $R=32\ldots6.1$ (C4.1) |
| Enhancement equals the moment series (7) | $1.000899480$ versus $1.000899459$ (C4.4) |
| Enhancement grows with curvature | $1.000899\to1.027732$ (C4.3) |
| Tight-torus resolution requirement | coarse $\varphi$ grid deviates by $1.54\times10^{-10}$, fine grid by $1.89\times10^{-14}$ at $R=6.1$ (C4.5) |

The singular $\varphi$ integrand of (5) sets the resolution requirement of the tight rows; the coarse-grid deviation is reported as the measured requirement rather than absorbed into a tolerance.

## References

- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789, DOI `10.1512/iumj.1993.42.42034`—conditional direction-coherence continuation criterion
- H. Beirão da Veiga and L. C. Berselli, “On the regularizing effect of the vorticity direction in incompressible viscous flows,” *Differential and Integral Equations* **15** (2002), no. 3, 345–356—weaker Hölder coherence still suffices
- P. Constantin, I. Procaccia, and D. Segel, “Creation and dynamics of vortex tubes in three-dimensional turbulence,” *Physical Review E* **51** (1995), no. 4, 3207–3222, DOI `10.1103/PhysRevE.51.3207`—vortex-tube coherence length, alignment and the self-stretching rate of aligned tubes
- `foundations/core-trapped-charge-support.md` §8.4—the relaxed transverse tube, its exact bending neutrality and its winding energy
- `computations/matter_formation_tube_geometry.py`, `computations/verify_matter_formation_tube_geometry.py`—the curvature laws, the moment series and the independent reconstruction
- `turbulence/navier-stokes-stress-geometry.md`—filtered stress geometry, the Biot–Savart direction estimate and the critical coherence coefficient
- `turbulence/navier-stokes-helical-dynamic-depletion.md`—coherent helical tube families and their measured positive production
