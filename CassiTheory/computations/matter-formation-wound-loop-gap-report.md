# Wound Carrier Loop and the Yang–Mills Mass-Gap Boundary

## Status: Tested—September 2026

## Abstract

The corrected matter-formation tube functional has now been carried into a closed, temporally charged and spatially wound loop calculation. The straight tube binds above a finite line-density threshold. Temporal charge and phase winding together produce a positive reduced mass and a formal finite-radius minimum. On the frozen charge schedule, the reduced minima at $Q=64,128,256$ lie below their dilute charged continua, and the transported $Q=256$, $w=1$, $R=8$ trial remains bound by $72.12081046$ energy units. Its transverse spectrum is positive apart from the expected soft translation mode.

The loop does not yet supply a stationary thin-loop gap mechanism. Every unconstrained reduced minimum lies at $R<1.85$, outside the validated $R\ge8$ transported-tube domain. At the admissible boundary $R=8$, the bound $Q=256$ trial has $dM/dR=+8.69217885$, so its energy falls toward smaller radii. The frozen classification is

$$
\boxed{\texttt{BOUND\_THIN\_TRIAL\_NO\_THIN\_STATIONARY\_RADIUS}.}
$$

This result identifies the live part of the mechanism and the precise missing part. The corrected scalar tube supplies binding, width selection, longitudinal winding pressure and a positive transverse gap. A Yang–Mills application still needs a gauge-owned, quantized loop sector and a controlled small-radius completion that stops contraction before the thin-tube description fails.

## 1. Reduced loop mechanism

For fixed carrier line density $n$, the corrected transverse functional defines

$$
E_\perp(n)=\inf_{\int c^2d^2x_\perp=n}
\int d^2x_\perp\left[
\frac12|\nabla f|^2+\frac{k_{Cx}}2|\nabla c|^2
+\frac{u_\rho}{4}(f^2-1)^2
+(B-h_C+h_Cf^2)c^2+\frac{u_C}{2}c^4
\right].
$$

Write $e(n)=E_\perp(n)/n$. Bending this profile into a loop of length $L=2\pi R$, integrated carrier norm $N=Ln$, temporal Noether charge $Q$ and spatial phase winding $w$ gives the thin-loop mass

$$
M_{Q,w}(L,n)
=L E_\perp(n)
+\frac{2\pi^2k_{Cx}w^2n}{L}
+\frac{Q^2}{4aLn}.
\tag{1}
$$

Equivalently,

$$
M_{Q,w}(N,n)=Ne(n)+\frac{A_{Q,w}(n)}{N},
\qquad
A_{Q,w}(n)=\frac{Q^2}{4a}+2\pi^2k_{Cx}w^2n^2.
\tag{2}
$$

At fixed $n$, the two terms balance exactly:

$$
N_*(n)=\sqrt{\frac{A_{Q,w}(n)}{e(n)}},
\qquad
L_*(n)=\frac{N_*(n)}{n},
\qquad
M_*(n)=2\sqrt{e(n)A_{Q,w}(n)}.
\tag{3}
$$

This isolates the mechanism. The transverse tube energy acts as tension, while temporal charge and longitudinal winding provide inverse-length pressure. Both conserved structures are required by the controls: with $Q=0$, the mass infimum tends to zero as $n\to0$; with $w=0$, temporal charge can bind a carrier distribution but selects no finite loop radius.

Relative to the dilute charged threshold $\Omega_\infty|Q|$, where $\Omega_\infty=\sqrt{B/a}$, a wound loop is bound exactly when

$$
\left|\frac{Q}{w}\right|^2>
\frac{8\pi^2ak_{Cx}e(n)n^2}{B-e(n)}.
\tag{4}
$$

The corrected tube profiles therefore turn the mass question into a directly measured competition between $e(n)$, charge and winding.

## 2. Frozen calculation

The calculation uses

$$
a=\frac1{16},\quad c_\Psi=\frac18,\quad k_{Cx}=u_C=1,
\quad u_\rho=4,\quad B=\frac{19}{4},\quad
h_C=2.9598260763447164.
$$

The primary program solves 19 radial profiles on $(M,R_{\max})=(200,8)$ for

$$
n\in\{1.75,1.875,2,2.25,2.5,2.75,3,\pi,3.25,3.5,3.75,4,
4.5,5,6,8,12,24,48\}.
$$

Spacing and domain checks repeat $n=2,4,8$ on $(400,8)$ and $(400,16)$. Shape-preserving interpolation is confined to the measured density intervals. The loop schedule is $Q\in\{16,64,128,256\}$ with $w=1$. Transported profiles are geometrically qualified only for $R\ge8$ with carrier tail fraction beyond transverse radius six below $10^{-4}$.

All 19 primary profiles converge. The worst stationarity residual is $1.3691\times10^{-8}$ against the $10^{-7}$ gate. The worst relative spacing and domain discrepancies in $e(n)$ are $1.6997\times10^{-5}$ and $2.1146\times10^{-4}$ against the $5\times10^{-4}$ gates.

## 3. Binding threshold

The infinite-plane weak-field onset is

$$
n_T=1.7307557357.
$$

The finite $R_{\max}=8$ tube becomes bound relative to $B=4.75$ between $n=1.875$ and $1.90625$. Across the complete measured profile family, the least charge-to-winding ratio required by (4) is

$$
\left|\frac{Q}{w}\right|_{\rm bind}=41.1173021501
$$

at

$$
n=4.3260504663,
\qquad e(n)=4.5039640307,
$$

inside the measured bracket $4<n<4.5$. Thus $Q=16$ lies below the loop-binding threshold for $w=1$, while $Q=64,128,256$ can bind in the reduced family.

## 4. Formal reduced minima

The density-minimized leading thin-loop rows are:

| $Q$ | $n_*$ | $M_*$ | $\Omega_\infty Q-M_*$ | $R_*$ | Bound | Geometry qualified |
|---:|---:|---:|---:|---:|:---:|:---:|
| 16 | 2.000000 | 144.681047 | $-5.196280$ | 1.213297 | no | no |
| 64 | 7.147844 | 544.349165 | 13.589900 | 1.422852 | yes | no |
| 128 | 12.637748 | 1049.101646 | 66.776483 | 1.649102 | yes | no |
| 256 | 23.103097 | 2032.835937 | 198.920322 | 1.848122 | yes | no |

The bound rows are interior minima of the measured density interpolation, with positive density and population curvature. Their radii are all far below the validated transported-profile condition $R\ge8$. They establish a real energetic tendency in the reduced formula, while the thin geometry cannot resolve their cores.

## 5. Admissible-radius trial

The exact transported-profile mass at radius $R$ uses the torus metric factor

$$
\eta(n,R)=
\frac{\int_0^6 2\pi r c_n(r)^2[1-(r/R)^2]^{-1/2}dr}
{\int_0^6 2\pi r c_n(r)^2dr},
$$

$$
M^{\rm tor}_{Q,w}(n,R)=2\pi R E_\perp(n)
+\frac{\pi k_{Cx}w^2n}{R}\eta(n,R)
+\frac{Q^2}{8\pi aRn}.
\tag{5}
$$

At the smallest qualified radius, $Q=256$, $w=1$, $R=8$, the density minimization selects $n=5$. A fresh profile solve at that density gives

$$
\begin{aligned}
E_\perp &=22.1744771884,\\
\eta(5,8)&=1.0118788464,\\
M^{\rm tor}_{256,1}(5,8)&=2159.6354486318,\\
\Omega_\infty Q&=2231.7562590928,\\
\Omega_\infty Q-M^{\rm tor}&=72.1208104610.
\end{aligned}
$$

The profile is well inside the transverse support gate: its tail fraction beyond radius six is $2.8574\times10^{-6}$. The energy decomposition is

$$
M_{\rm static}=1114.6107941159,
\qquad
M_Q=1043.0378350470,
\qquad
M_w=1.9868194689.
$$

The decisive radius measurement is

$$
\left.\frac{dM^{\rm tor}}{dR}\right|_{n=5,R=8}
=+8.6921788545.
$$

Increasing $R$ raises the mass, so decreasing $R$ lowers it. The admissible boundary is bound, but it is not a stationary loop: the configuration contracts toward the unresolved thick-loop regime.

## 6. Transverse spectrum

The exact discrete Hessian of $E_\perp-\mu n$ was evaluated on the recomputed $n=5$ profile with kinetic mass density $W=\operatorname{diag}(c_\Psi,2a)$. The $m=0$ carrier-amplitude block is projected onto the fixed-$n$ tangent space. The lowest generalized eigenvalues are

| Angular mode | Lowest $\omega^2$ | Interpretation |
|---:|---:|---|
| $m=0$ | 12.7661775631 | positive fixed-population radial mode |
| $m=1$ | 0.00256718381 | soft rigid-translation mode |
| $m=2$ | 12.7261387878 | positive first shape mode |
| $m=3$ | 17.7075102178 | positive |
| $m=4$ | 19.9381383240 | positive |

The translation ratio is $2.0173\times10^{-4}$ relative to the first positive non-symmetry mode. Every tested non-symmetry transverse mode is positive. The obstruction is therefore the loop-radius direction, not a transverse breakup mode in the measured sector.

## 7. Verification and retained recovery

The primary receipt passes 12 checks. The source-independent verifier passes 17 checks and reconstructs every profile functional, the Townes onset, the charge-to-winding threshold, all four reduced minima, the exact torus metric and mass, the fixed-radius trial and the full $m=0,\ldots,4$ generalized spectrum. Its worst spectral normalized error is $4.03\times10^{-12}$.

Two can-fail controls fire. Adding $10^{-3}$ to one stored energy produces normalized mass error $2.3274\times10^{-5}$, above the comparison tolerance. Flipping the sign of the positive $m=0$ eigenvalue changes the stability minimum from $+12.7662$ to $-12.7662$ and fails the classifier.

The evidence set preserves an initial receipt whose scientific calculation completed but whose final manifest-path conversion followed the repository's `runs` junction. The protocol-authorized recovery uses a fresh directory, records the defect and the failed receipt, and changes no density, charge, grid, threshold or stopping rule.

| Artifact | SHA-256 |
|---|---|
| `runs/20260921_matter_formation_wound_loop_gap/primary.json` | `fbe2ec4ca9a39be31ebb0c4574c9ff12536d6ba6e8d2a4feaf0ef996d11125bd` |
| `runs/20260921_matter_formation_wound_loop_gap_recovery/primary.json` | `a58a7532bb4364faabb6739bed22aa7e462e4a361be5fdead5fe14d5ff49288f` |
| `runs/20260921_matter_formation_wound_loop_gap_recovery/independent.json` | `aad299784a97f95624ef029fdbe2e6b0e7ecbc385df1c03d5f033fff71fe5648` |

The primary content digest is `59dd68a62e45ed2b9ab2f1eb499d140847cf2478ed88471e59f2b724932c2e20`; the independent verifier reproduces it exactly. The independent receipt content digest is `3053faf678e9a36c870fbec5ca2617627e7e1e03ab160e2fac57bcfbd6d0c3cd`.

## 8. Yang–Mills consequence

The calculation adds a concrete scale-generation mechanism to the Yang–Mills program:

1. the corrected nonlinear transverse sector forms a bound tube above a measured density threshold;
2. the tube selects its own width and has positive non-symmetry transverse modes;
3. temporal charge and spatial winding create a finite formal loop scale;
4. the resulting loop can lie below its dilute charged continuum.

The same calculation locates the break in the chain. The registered carrier is neutral under the conditional $SU(2)_Q$ field. Its conserved $Q$ is a global $U(1)$ Noether charge, its integer $w$ is a scalar phase winding, and neither has a derived identification with a Wilson representation, electric flux sector or pure-gauge excitation. The formal radius occurs after the thin tube has entered core overlap. Consequently

$$
\texttt{yang\_mills\_identification}=\texttt{UNRESOLVED},
$$

$$
\texttt{continuum\_gauge\_construction}=\texttt{UNRESOLVED},
\qquad
\texttt{charge\_quantization}=\texttt{UNRESOLVED},
\qquad
\texttt{clay\_verdict}=\texttt{NULL}.
$$

The next mathematical target is now sharp: construct the conserved inverse-length term from gauge-invariant Yang–Mills data and continue the loop through the thick-core regime. A full toroidal solve can test whether core overlap, curvature-induced profile relaxation or gauge flux supplies the missing positive small-radius energy. A successful mechanism must produce an interior radius before importing any scalar charge as a Yang–Mills quantum number, and it must then connect that excitation to a regulator-independent continuum spectral bound.

## References

- `computations/matter-formation-wound-loop-gap-prereg.md`—frozen functional, schedules, controls and decision tree.
- `computations/matter_formation_wound_loop_gap.py`—primary profile, loop and generalized-spectrum calculation.
- `computations/verify_matter_formation_wound_loop_gap.py`—source-independent reconstruction and mutation controls.
- `computations/matter_formation_tube_geometry.py`—corrected transverse tube solver.
- `computations/verify_matter_formation_tube_geometry.py`—independent tube-geometry reconstruction.
- `foundations/core-trapped-charge-support.md` §8.4—registered straight-tube geometry and winding law.
- `foundations/loop-to-bubble-projection-theorem.md` §9—Yang–Mills spectral target and current bridge boundary.
