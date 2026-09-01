# Particle Stationary Fixed-Charge Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign performs the first numerical minimization of the conditional
particle functional in `foundations/particle-stationary-action-closure.md` at
one frozen normalization-invariant coefficient point and fixed carrier charge.
It compares six deterministic initialization basins on the same finite-domain
functional, repeats every basin on a larger domain, and applies one finer-grid
control selected by a frozen rule.

The experiment asks whether a localized fixed-$Q_C$ stationary basin emerges
inside the declared discretized class. It does not identify a physical
particle, select Cassi's coefficients, establish an unrestricted global
minimum, compute a fluctuation spectrum, or test real-time stability. No
coefficient, seed, optimizer, threshold, arm, or stopping rule may change after
the primary program begins execution.

---

## 1. Source functional and numerical sector

The source authority is the dimensionless static energy (PA32), charge (PA34),
and variational boundary (PA38)--(PA41) in
`foundations/particle-stationary-action-closure.md`. The program minimizes

$$
\widehat E[\psi,h,a_i,c]
$$

at fixed $q_C=\int|c|^2d^3\widehat x$.

The first computation uses the lowest no-flux scale mode:

$$
\partial_{\mathfrak s}\psi
=\partial_{\mathfrak s}h
=\partial_{\mathfrak s}c=0,
\qquad
a_{\mathfrak s}=0,
\qquad
L_{\mathfrak s}=1.
$$

The $\alpha_{\mathfrak s}$, $\gamma_{\mathfrak s}$, and
$k_{C\mathfrak s}$ terms consequently vanish. The temporal fields are fixed to
the Gauss-compatible stationary sector $a_0=0$. The carrier phase is constant,
and its nodeless representative is real and nonnegative. The optimized fields
are otherwise the full complex fundamental doublet $\psi$, real adjoint
triplet $h^a$, and nine real spatial connection components $a_i^a$.

The Cartesian representation is projected onto fourfold rotations around the
$z$ axis. Scalar and color-scalar fields are averaged over the four rotations;
the spatial index of $a_i^a$ is rotated with the grid. This is a $C_4$
approximation to the axisymmetric class. Removed degrees of freedom are:

- nonzero scale modes and $a_{\mathfrak s}$;
- carrier phase gradients, sign changes, and exact interior carrier zeros;
- non-$C_4$ spatial deformations;
- temporal fields and fluctuation modes;
- arbitrary knots and topology-changing paths outside the represented seeds.

Every conclusion is restricted to this finite-dimensional class.

---

## 2. Frozen coefficient point

The sole static point is

| group | value |
|---|---:|
| $\varphi$ | $(1+\sqrt5)/2$ |
| $\alpha_{\mathfrak s}$ | `1.0` (inactive in the lowest scale mode) |
| $u_\rho$ | `4.0` |
| $u_\varphi$ | `4.0` |
| $\gamma_x$ | `1.0` |
| $\gamma_{\mathfrak s}$ | `1.0` (inactive) |
| $u_H$ | `4.0` |
| $k_{Cx}$ | `1.0` |
| $k_{C\mathfrak s}$ | `1.0` (inactive) |
| $e_C$ | `0.75` |
| $h_C$ | `1.50` |
| $u_C$ | `1.0` |
| $q_C$ | `4.0` |
| $L_{\mathfrak s}$ | `1.0` |

The gauge-fixing coefficient is $\xi_{\rm gf}=1.0$. These order-unity values
define a mathematical benchmark and have no fitted interpretation. They set
the vacuum carrier threshold to $e_C=0.75$ and the fully depleted-core linear
coefficient to $e_C-h_C=-0.75$. No scan or post-run replacement point is
permitted.

The only potentially negative pointwise contribution is the combined
doublet-carrier potential. With $x=|\psi|^2$ and $y=c^2$ it is

$$
V_{C\rho}=(x-1)^2+(-0.75+1.5x)y+\frac12y^2.
$$

For $x\geq1/2$, every term is nonnegative. For $0\leq x<1/2$, minimization over
$y\geq0$ gives

$$
\min_yV_{C\rho}
=(x-1)^2-\frac12(0.75-1.5x)^2\geq\frac14.
$$

All remaining potential and gradient terms are nonnegative, so the frozen
functional is bounded below.

The point does not pre-satisfy the carrier-retention or reduced-support
conditions: $\widehat\omega_C$ is measured, while the thin-tube quantities
$\Lambda_C$, $C_Q$, $\sigma_Q$, and $\varepsilon_b$ are outside this
coefficient point. The preregistration commit freezes the table and every
execution choice before the primary program runs.

The outer vacuum is

$$
h_\infty=(0,0,1),
\qquad
a_{i,\infty}=0,
$$

The fixed real boundary doublet is

$$
\psi_\infty
:=\begin{pmatrix}\varphi^{-1/2}\\ \varphi^{-1}\end{pmatrix},
$$

with both components positive. It satisfies
$|\psi_\infty|^2=1$ and
$\psi_\infty^\dagger\sigma^3\psi_\infty
=(\varphi-1)/(\varphi+1)$, so $\delta_\varphi=0$ at the boundary.

---

## 3. Discretization, gauge condition, and constrained gradient

The primary run uses PyTorch float64 on the installed ROCm device exposed as
`cuda:0`, launched with `CUDA_VISIBLE_DEVICES=1`. Absence of that device is a
preflight failure; there is no CPU fallback. The receipt records the PyTorch,
HIP, and device versions. The program calls
`torch.use_deterministic_algorithms(True)`.

The spatial domain is a cube $[-R,R]^3$ with uniform nodes. Spatial derivatives
use

```python
torch.gradient(field, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2)
```

with $\Delta x=2R/(N-1)$. Every integral is the uniform node sum with
$\Delta V=(\Delta x)^3$. The outermost node layer is fixed exactly to
$\psi_\infty$, $h_\infty$, $a_i=0$, and $c=0$.

The covariant quantities are evaluated directly from PA30--PA32:

$$
D_i\psi=\partial_i\psi-ia_i^aT^a\psi,
\qquad
(D_ih)^a=\partial_ih^a+(a_i\times h)^a,
$$

$$
f_{ij}=\partial_i a_j-\partial_j a_i+a_i\times a_j.
$$

The optimizer objective is

$$
\widehat E_{\rm obj}
:=\widehat E
+\frac{\xi_{\rm gf}}{2}
\int(\partial_i a_i^a)^2d^3\widehat x.
$$

The second term selects a numerical Coulomb representative. It is excluded
from every reported physical energy. Its norm and energy fraction are quality
diagnostics.

The carrier is constructed from an unconstrained interior field $w$ by

$$
c=\sqrt{q_C}\,
\frac{m\,\operatorname{softplus}(w)}
{\left[\int m^2\operatorname{softplus}(w)^2d^3\widehat x\right]^{1/2}},
$$

where $m$ is zero on the fixed boundary and one elsewhere. Charge is therefore
fixed during every optimizer evaluation. This realizes the
$\widehat E-\widehat\omega_Cq_C$ sign convention of PA34.
For G1 only, $q_C=0$ directly sets $c\equiv0$; the normalized
positive-charge map above is used only for $q_C>0$.

For a scalar or component-valued field $u$, and for the four quarter-turns
$R_k$ around $z$, the exact lattice projector is

$$
(P_4u)(x)=\frac14\sum_{k=0}^3u(R_k^{-1}x).
$$

For the connection its spatial index is rotated:

$$
(P_4a)_i^a(x)
=\frac14\sum_{k=0}^3(R_k)_{ij}a_j^a(R_k^{-1}x).
$$

The color index is unchanged. Each rotation is an exact `torch.rot90`; no
interpolation is used. The raw optimizer arrays pass through these projectors
and then the fixed-boundary map on every objective evaluation. The softplus
map restricts this campaign to strictly positive carrier interiors; exact
interior zeros, sign changes, and phase winding remain outside the class.

The stationarity gate uses the physical PA32 energy, independent of the raw
parameterization and gauge-fixing penalty. Let $\partial E/\partial u_r$ be
the autograd derivative with respect to each real component of the final
physical arrays, and define its discrete functional derivative by
$g_r=(\partial E/\partial u_r)/\Delta V$. Zero the fixed shell and apply $P_4$
to the $\psi$, $h$, and $a_i$ gradients. For the carrier additionally apply
the fixed-charge tangent projection

$$
g_c^\perp
=P_4\left[
m\left(g_c-c\frac{\langle c,g_c\rangle_h}
{\langle c,c\rangle_h}\right)\right],
\qquad
\langle u,v\rangle_h:=\Delta V\sum_xuv.
$$

Counting the real and imaginary doublet entries separately, the reported
physical first-variation norm is

$$
\|\delta\widehat E\|
:=\left(\frac1M\sum_{r=1}^{M}|g_r^\perp|^2\right)^{1/2},
$$

where $M$ is the number of non-boundary real field entries. The raw
$\widehat E_{\rm obj}$ gradient is recorded only as an optimizer diagnostic.

---

## 4. Frozen grid arms

| family | $R$ | $N$ | $\Delta x$ | basins |
|---|---:|---:|---:|---|
| `P` primary | `4.0` | `17` | `0.5` | all six |
| `D` larger domain | `5.0` | `21` | `0.5` | all six |
| `H` finer grid | `4.0` | `21` | `0.4` | one basin selected below |

The structural set is
`separated_core`, `merged_core`, `closed_loop`, `carrier_lump`, and
`split_multicore`. The `H` basin is the lowest-physical-energy structural `P`
basin that passes Q1--Q4. Ties within `1e-10` are resolved by the basin order
in Section 5. If no structural primary basin passes Q1--Q4, `H` is not run and
the campaign returns `INCONCLUSIVE—NUMERICAL QUALITY`. This rule is frozen
before any field result.

---

## 5. Frozen initialization basins

Every seed is analytic and passes through the same boundary and $P_4$ maps.
Widths and positions are in units of $\ell_Q$. Define

$$
G_{p,w}(x):=\exp\left[-\frac{|x-p|^2}{2w^2}\right],
\qquad
r_\perp:=\sqrt{x^2+y^2},
$$

and use $\eta=10^{-4}$. A declared positive carrier profile $p_C$ initializes
the unconstrained carrier variable as

$$
w_0=\log\left[\exp(p_C+\eta)-1\right].
$$

The fixed-charge map in Section 3 then supplies the physical carrier.

1. **`separated_core`**—set $d=1.50$, $w=0.70$,
   $G_\pm=G_{(0,0,\pm d),w}$, and

   $$
   G_I=\exp\left[
   -\frac{r_\perp^2+(|z|-d)_+^2}{2w^2}\right].
   $$

   This is a smooth planar color texture with two adjoint-magnitude zeros.
   With $A_h=(1-G_+)(1-G_-)$,
   $\theta=0.80(G_+-G_-)$, and
   $n=(\sin\theta,0,\cos\theta)$, initialize
   $h=A_hn$, $a_i=-n\times\partial_i n$,
   $\psi=(1-G_I)\psi_\infty$, and $p_C=G_I$.
2. **`merged_core`**—with $G=G_{(0,0,0),0.85}$, initialize
   $h=(0,0,1-G)$, $\psi=(1-G)\psi_\infty$, and $a_i=0$.
   Set $p_C=G_{(0,0,0),0.80}$.
3. **`closed_loop`**—define

   $$
   G_T=\exp\left[
   -\frac{(r_\perp-1.50)^2+z^2}{2(0.55)^2}\right],
   \qquad
   e_\phi=\frac{(-y,x,0)}{\sqrt{r_\perp^2+\eta^2}}.
   $$

   Initialize $h=(0,0,1-G_T)$,
   $\psi=(1-G_T)\psi_\infty$,
   $a_i^a=0.80\,G_T(e_\phi)_i\delta^{a3}$, and $p_C=G_T$.
4. **`carrier_lump`**—use the exact vacuum $\psi,h,a_i$ and
   $p_C=G_{(0,0,0),0.90}$.
5. **`delocalized`**—use the exact vacuum $\psi,h,a_i$ and $p_C=1$ on every
   interior node.
6. **`split_multicore`**—let
   $\mathcal P=\{(\pm1.35,0,0),(0,\pm1.35,0)\}$,
   $G_p=G_{p,0.60}$, and $A_\psi=\prod_{p\in\mathcal P}(1-G_p)$.
   Initialize $\psi=A_\psi\psi_\infty$, $h=h_\infty$, $a_i=0$, and
   $p_C=\sum_{p\in\mathcal P}G_p$.

All fields on the outermost layer are replaced by the exact boundary values
after seed construction. The labels record initialization provenance; no
topological label is inferred from a converged field.

---

## 6. Frozen optimizer and preflight

Each arm uses exactly:

1. Adam for `800` steps with learning rate `0.020` for steps `0–399` and
   `0.005` for steps `400–799`;
2. L-BFGS with `max_iter=120`, `max_eval=150`, `history_size=20`,
   `tolerance_grad=1e-10`, `tolerance_change=1e-12`, and
   `line_search_fn="strong_wolfe"`. It terminates only at either declared
   tolerance, `max_iter`, or `max_eval`.

The boundary, $C_4$, carrier-positivity, and charge maps are part of the
objective construction. Adam completes all `800` steps unless an objective,
field, or gradient becomes nonfinite. No restart, learning-rate change, seed
change, clipping, coefficient adjustment, or extra iteration is permitted
after execution begins.

Before the campaign arms, the program must pass:

- **G1:** the $q_C=0$ exact outer vacuum has physical energy magnitude below
  `1e-12`;
- **G2:** twelve frozen directional derivatives of the raw projected objective
  on an `N=7`, `R=2` test state have central-difference relative error at most
  `5e-5`;
- **G3:** fixed-charge construction has relative charge error below `5e-12`;
- **G4:** SHA-256 hashes of
  `foundations/particle-stationary-action-closure.md`,
  `foundations/core-trapped-charge-support.md`,
  `foundations/nonabelian-magnetic-core-boundary.md`, this preregistration,
  the primary program, and the independent verifier are recorded before the
  first arm.

For each G2 row, start from a fresh `merged_core` seed, add `0.03 d_r` only
to the listed raw block, and compare the derivative along that same $d_r$;
all other raw blocks remain at the seed. On lattice indices
$i,j,k\in\{0,\ldots,6\}$,

$$
d_r(i,j,k)
:=m\,\cos\left[(r+1)(i+1)+2(j+1)+3(k+1)\right],
$$

normalized to Euclidean norm one. The twelve $(r,\text{block})$ pairs are

| $r$ | raw block |
|---:|---|
| 0 | $\Re\psi_0$ |
| 1 | $\Re\psi_1$ |
| 2 | $\Im\psi_0$ |
| 3 | $\Im\psi_1$ |
| 4 | $h_0$ |
| 5 | $h_1$ |
| 6 | $h_2$ |
| 7 | $a_0^0$ |
| 8 | $a_1^1$ |
| 9 | $a_2^2$ |
| 10 | $a_0^2$ |
| 11 | $w$ |

Use central step `1e-5` and relative error

$$
\frac{|D_{\rm AD}-D_{\rm FD}|}
{\max(10^{-8},|D_{\rm AD}|,|D_{\rm FD}|)}.
$$

Any preflight failure stops the campaign with
`INCONCLUSIVE—IMPLEMENTATION PREFLIGHT` and preserves the receipt.

---

## 7. Frozen diagnostics

For every completed arm $b$, record the PA39 tuple

$$
\mathcal R_b=
(\widehat E_b,q_{C,b},\widehat\omega_{C,b},L_b,R_{C,b},
\|\delta\widehat E\|,\mathcal V_b,\Phi_{\partial\Omega,b}).
$$

The energy components retain their PA32 coefficients. In particular,
$E_{c\nabla}=(k_{Cx}/2)\int|\nabla c|^2dV$,
$E_{c2}=\int[e_C-h_C(1-|\psi|^2)]c^2dV$, and
$E_{c4}=(u_C/2)\int c^4dV$. The diagnostics are

$$
\widehat\omega_C
=\frac{E_{c\nabla}+E_{c2}+2E_{c4}}{q_C},
$$

$$
L_b
=2\sqrt{\frac{\int z^2(1-|\psi|^2)_+dV}
{\int(1-|\psi|^2)_+dV}},
\qquad
R_{C,b}=\sqrt{\frac{\int r^2c^2dV}{q_C}}.
$$

Here $r:=\sqrt{x^2+y^2+z^2}$ about the box center.

Set $L_b=0$ when its denominator is below `1e-12`.
$\|\delta\widehat E\|$ is the physical constrained norm in Section 3.

The virial residual uses one admissible cutoff dilation. Define the
cube-symmetric, $C_4$-invariant cutoff

$$
\chi(x):=\prod_{i=1}^3\left[1-(x_i/R)^2\right]^2,
\qquad
v_i(x):=\chi(x)x_i,
$$

and the tangent fields

$$
\dot\psi=-v_j\partial_j\psi,
\qquad
\dot h=-v_j\partial_jh,
\qquad
\dot a_i=-v_j\partial_ja_i-a_j\partial_iv_j.
$$

For the positive carrier set

$$
s_c=-v\cdot\nabla\log(c+10^{-12})-\frac12\nabla\cdot v.
$$

The `1e-12` logarithm regularizer is frozen. It defines a positive
charge-preserving tangent and approaches the carrier half-density dilation
where $c\gg10^{-12}$.

At $t_\pm=\pm10^{-4}$, form

$$
\psi_\pm=P_4(\psi+t_\pm\dot\psi),\quad
h_\pm=P_4(h+t_\pm\dot h),\quad
(a_i)_\pm=P_4(a_i+t_\pm\dot a_i),
$$

reset the fixed shell, and use the exactly normalized positive carrier

$$
c_\pm
=\sqrt{q_C}\,
\frac{mce^{t_\pm s_c}}
{\left[\int m^2c^2e^{2t_\pm s_c}dV\right]^{1/2}}.
$$

For every PA32 energy component $\alpha$, let

$$
W_\alpha
:=\frac{E_\alpha(+10^{-4})-E_\alpha(-10^{-4})}{2\times10^{-4}},
\qquad
\mathcal V_b
:=\frac{|\sum_\alpha W_\alpha|}
{\max(10^{-12},\sum_\alpha|W_\alpha|)}.
$$

This path preserves the fixed shell, $C_4$, carrier positivity, and charge.
For $\chi=1$ and without the logarithm regularizer, it is the derivative at
$t=0$ of

$$
\psi_t(x)=\psi(e^{-t}x),\quad
h_t(x)=h(e^{-t}x),\quad
(a_i)_t(x)=e^{-t}a_i(e^{-t}x),\quad
c_t(x)=e^{-3t/2}c(e^{-t}x).
$$

The matching formal whole-space derivative is recorded:

$$
\mathcal W_\infty
=E_{\psi\nabla}+E_{h\nabla}-E_f
+3(E_\rho+E_\varphi+E_H)
-2E_{c\nabla}-3E_{c4}.
$$

The carrier quadratic terms have zero whole-space fixed-charge scaling weight.
Gauge fixing is excluded from both virial quantities.

The first outer shell $S_1$ contains nodes with any index `0` or `N-1`; the
outer-two-shell set $S_2$ contains nodes with any index at most `1` or at least
`N-2`. Define $\Phi_{\partial\Omega}$ as the unweighted arithmetic RMS of the
nine $f_{ij}^a$ entries with $i<j$ over the node union $S_1$, counting each
corner once. Gauge-divergence RMS is the same node RMS of the three color
components $\sum_i\partial_i a_i^a$ over the full grid. The outer carrier
fraction is $\sum_{S_2}c^2/\sum_\Omega c^2$.

For the gauge-invariant outer charge, set

$$
\mathscr g_{ij}
:=\widehat h^af_{ij}^a
-\epsilon^{abc}\widehat h^a(D_i\widehat h)^b(D_j\widehat h)^c,
\qquad
\widehat h:=\frac{h}{|h|},
\qquad
\mathscr B_i:=\frac12\epsilon_{ijk}\mathscr g_{jk}.
$$

The face flux uses node-centered arrays and the same derivative stencil as the
energy. Evaluate $\widehat h$ only on $S_1$, where the fixed representative has
$|h|=1$. On each face use trapezoid weights `1` in the face interior, `1/2` on
its edges, and `1/4` at its corners. Then

$$
\Phi_G^{\rm disc}
=\Delta x^2\sum_{i=1}^3
\left[
\sum_{F_i^+}w\mathscr B_i-\sum_{F_i^-}w\mathscr B_i
\right],
\qquad
N_G^{\rm outer,disc}:=\frac{\Phi_G^{\rm disc}}{4\pi}.
$$

All derivatives in this section use the Section 3 operator. The fixed outer
representative makes every tangential term in the charge sum zero; direct
evaluation remains an implementation check.

Also record every energy component, boundary residual, objective-gradient
diagnostic, gauge-divergence RMS, gauge-fixing energy fraction,
$N_G^{\rm outer,disc}$, outer carrier fraction, maximum doublet-density
depletion, Adam and L-BFGS histories, wall time, field-artifact hash, and
program hashes.

---

## 8. Numerical-quality gates

For positive $u,v$, every relative difference below means

$$
\operatorname{reldiff}(u,v)
:=\frac{|u-v|}{\max(|u|,|v|,10^{-12})}.
$$

### Q1—Completion, charge, and boundary

Every required arm is finite, completes the frozen schedule, and satisfies:

- relative charge error $\le5\times10^{-12}$;
- maximum fixed-boundary field residual $\le10^{-12}$.

### Q2—Physical stationarity

Every scored arm must satisfy

$$
\|\delta\widehat E\|\le3\times10^{-4},
\qquad
\mathcal V_b\le0.08.
$$

### Q3—Gauge representative

Every scored arm must satisfy

$$
\|\partial_i a_i\|_{\rm RMS}\le0.02,
\qquad
\frac{E_{\rm gf}}{\max(|\widehat E|,10^{-12})}\le0.01.
$$

### Q4—Outer gauge boundary

Every scored arm must satisfy

$$
\Phi_{\partial\Omega,b}\le0.05,
\qquad
|N_G^{\rm outer,disc}|\le10^{-10}.
$$

The outer carrier fraction serves only as a localization diagnostic.

### Q5—Domain convergence and dilution control

For each of the five structural basins, the `P` and `D` arms must pass Q1--Q4
and satisfy:

- $\operatorname{reldiff}(\widehat E_D,\widehat E_P)\le0.05$;
- $|L_D-L_P|\le0.75$;
- $|\widehat\omega_{C,D}-\widehat\omega_{C,P}|\le0.10$;
- $\operatorname{reldiff}(R_{C,D},R_{C,P})\le0.10$ when both outer carrier
  fractions are at most `0.01`;
- otherwise,
  $\operatorname{reldiff}(R_{C,D}/R_D,R_{C,P}/R_P)\le0.10$.

Classify localization separately on `P` and `D` by Section 9. If the
`delocalized` control is localized on both domains, it uses the standard Q5
comparisons above. If it is nonlocalized on both, its dilution control
passes only when

$$
\operatorname{reldiff}(R_{C,D}/R_D,R_{C,P}/R_P)\le0.10,
$$

$$
E_{c4,D}\le E_{c4,P}+10^{-6},
\qquad
\frac{|\widehat E_D-e_Cq_C|}{e_Cq_C}\le0.25.
$$

A localization mismatch between its two domains fails the control.

### Q6—Resolution convergence

The frozen `H` basin must pass Q1--Q4 and agree with its `P` counterpart under
the same energy, length, multiplier, and applicable radius tolerances in Q5.

Any applicable Q1--Q6 or dilution-control failure returns
`INCONCLUSIVE—NUMERICAL QUALITY` before the physical classifier.

---

## 9. Localization and basin-ordering classifier

A quality-passing basin is localized only when all conditions hold:

1. outer carrier charge fraction $\le10^{-3}$;
2. $R_C<R/2$;
3. $\widehat\omega_C<e_C-0.02=0.73$;
4. maximum doublet-density depletion is at least `0.10`.

For each basin define its domain uncertainty

$$
\Delta_b^{\rm num}=|\widehat E_b^{(D)}-\widehat E_b^{(P)}|,
$$

and include $|\widehat E^{(H)}-\widehat E^{(P)}|$ in the selected basin's
uncertainty by taking the maximum. Basin $x$ is robustly below basin $y$ only
when

$$
\widehat E_y^{(P)}-\widehat E_x^{(P)}
>0.01+2(\Delta_x^{\rm num}+\Delta_y^{\rm num}).
$$

All five structural basins and the delocalized control are eligible only after
their applicable Q1--Q5 checks pass. Fewer than two eligible basins is a
numerical-quality failure.

The frozen verdict tree is evaluated in this order:

1. **`INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`** when G1--G4 fail.
2. **`INCONCLUSIVE—NUMERICAL QUALITY`** when any required Q1--Q6 or control
   gate fails.
3. **`EMERGES—LOCALIZED FIXED-CHARGE STATIONARY BASIN`** when one localized
   structural basin is robustly below every other eligible basin.
4. **`DOES NOT EMERGE—LOCALIZED FIXED-CHARGE STATIONARY BASIN`** when no
   structural basin is localized, or when the delocalized control is robustly
   below every localized structural basin.
5. **`INCONCLUSIVE—BASIN ORDERING`** for every remaining overlap involving a
   localized structural basin.

A positive result establishes one conditional discretized stationary basin at
the frozen point. A negative result rejects localization only at this point and
inside this represented class.

---

## 10. Artifacts and independent verification

Primary program:

- `computations/particle_stationary_bvp.py`

Independent verifier:

- `computations/verify_particle_stationary_bvp.py`

Report:

- `computations/particle-stationary-bvp-report.md`

Frozen receipt directory:

```text
runs/20260901_particle_stationary_bvp/
  results.json
  fields_P_<basin>.npz
  fields_D_<basin>.npz
  fields_H_<selected>.npz
  verification.json
```

Each NPZ has these float64 C-order arrays:

| key | shape |
|---|---|
| `x` | `(N,)` |
| `psi_real`, `psi_imag` | `(N,N,N,2)` |
| `h` | `(N,N,N,3)` |
| `a` | `(N,N,N,3,3)` with final indices `(spatial,color)` |
| `c` | `(N,N,N)` |

`results.json` contains `schema_version`, the coefficient point including the
exact value of $\varphi$, environment, source/program SHA-256 inventory,
preflight results, frozen arm inventory, per-arm optimizer receipt including
the actual L-BFGS iteration, closure-call, and function-evaluation counts,
diagnostics, `H` selection, gate booleans, pairwise ordering margins, terminal
verdict, and every NPZ SHA-256. Its `hashes` object uses the exact keys
`authority_action`, `authority_core_support`, `authority_magnetic_boundary`,
`preregistration`, `primary_program`, `independent_verifier`, and `artifacts`.
Before the first arm, the first six keys contain hashes of the files named by
G4; `artifacts` is a filename-to-hash object populated after each arm.

The verifier must not import or execute the primary program. It independently
reconstructs the PA32 discretization and projected physical first variation,
loads the final arrays, recomputes every final diagnostic and gate, checks the
source/program and artifact hashes, and reproduces the verdict tree. Optimizer
histories and wall times are receipt data; the verifier checks their schema and
finiteness without claiming to reproduce them.

Strings, booleans, arm inventory, hashes, gate directions, and the terminal
verdict must match exactly. Floating diagnostics must satisfy

$$
|x_{\rm verify}-x_{\rm primary}|
\le10^{-8}+10^{-6}|x_{\rm primary}|.
$$

A verifier mismatch returns `pass: false` and does not rewrite the primary
receipt.

---

## 11. Stopping and interpretation boundary

- Stop before basin minimization if G1--G4 fail.
- Stop an arm immediately on a nonfinite objective, field, or gradient and
  preserve its partial history.
- Run every required arm once under the frozen schedule.
- Do not rerun, tune, extend, or replace a completed arm after observing its
  result.
- Do not promote finite-grid basin ordering to an unrestricted global minimum.
- Do not infer a proton, particle mass, radius, spin, statistics, spectrum,
  lifetime, or physical coefficient from either verdict.
- Retain the unresolved sectors in PA38 §8.4, together with the scale-mode,
  carrier-phase, and non-$C_4$ exclusions introduced here.

## References

- `foundations/particle-stationary-action-closure.md`
- `foundations/core-trapped-charge-support.md`
- `foundations/nonabelian-magnetic-core-boundary.md`
- `computations/particle_action_closure_check.py`
