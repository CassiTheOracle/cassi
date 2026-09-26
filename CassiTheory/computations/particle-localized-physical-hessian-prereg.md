# Localized Particle Physical Hessian Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign evaluates the constrained energetic Hessian of the finest
qualified localized carrier field. The selected field is the `X2:separated_core`
artifact on the $(R,N)=(4,29)$ grid at the Mapped coupling
$h_C=2.9598260763447164$. The calculation keeps the fixed carrier charge,
strict outer-shell values, and $C_4$ field class of the stationary solve. It
then removes every local $SU(2)_Q$ gauge direction that preserves the same
finite-grid shell representative.

The physical tangent has 77,000 dimensions. A sparse orthogonal projector
avoids a dense $N=29$ quotient factorization. Exact automatic-differentiation
Hessian-vector products, centered
finite differences, independently constructed sparse projectors, and two
separately implemented eigensolvers determine the low-spectrum sign. The
numerical gauge-fixing energy is excluded from the Hessian.

This is one finite-grid energetic calculation on a localized field. It does not
supply a continuum spectrum, a non-$C_4$ spectrum, the mixed temporal pencil,
nonlinear persistence, formation, decay rates, or a physical particle
identification.

## 1. Frozen question

The primary question is:

> Does the finest qualified localized retained carrier field have a negative
> energetic mode in its complete registered $C_4$ finite-grid tangent after
> imposing fixed charge and fixed shell values and quotienting every
> boundary-preserving local $SU(2)_Q$ gauge direction?

Let $x$ denote coordinates in the fixed-shell, $C_4$, fixed-charge base tangent
and let $P$ be the Euclidean orthogonal projector away from the coupled gauge
image. The physical operator is

$$
\mathcal K_{\rm phys}
=\left.\frac{1}{\Delta V}
P\nabla_x^2\!\left(\widehat E_{\rm phys}
-\widehat\omega_C Q_C\right)P\right|_{\bar\Phi}
\quad\hbox{on }\operatorname{range}P.
\tag{LH1}
$$

The inner product is the finite-grid $L^2$ product. The common positive factor
$\Delta V$ is divided out in (LH1), so base coordinates use the ordinary
Euclidean metric:

$$
\langle u,v\rangle_{L^2_h}
=\Delta V\,u^{\mathsf T}v.
\tag{LH2}
$$

The calculation addresses the localized-background instance of PA42 in
`foundations/particle-stationary-action-closure.md`. PA43 and every real-time
claim remain outside this campaign.

## 2. Immutable background

### 2.1 Selected artifact

The only admissible background is:

- path:
  `runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz`;
- byte-exact SHA-256:
  `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0`;
- family and basin: `X2:separated_core`;
- grid:
  $(R,N,\Delta x,\Delta V)=(4,29,2/7,8/343)$;
- fixed carrier charge: $Q_C=4$;
- physical energy: $1.5251878559994063$;
- physical first-variation RMS:
  $3.090108443313949\times10^{-7}$;
- cutoff virial: $9.092469919592924\times10^{-8}$;
- carrier multiplier:
  $\widehat\omega_C=0.0034164531971490053$;
- carrier radius: $1.6314313026374387$;
- core length: $2.2977937729044924$;
- outer carrier fraction: $1.0708172350337447\times10^{-4}$;
- maximum density depletion: $0.9856286941942967$;
- negative carrier norm fraction: $0$.

The source campaign verdict is
`EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH`.
The source identities are:

| Authority | Canonical or byte-exact SHA-256 |
|---|---|
| resolution manifest | `8d1f18cb18d3635960ec7be1076688bcbd1f1fbc5fda1d86e851c46f8b3ff853` |
| resolution `results.json` | `b22a6e4b84aa68d099c2eb9930aa10213a28826b852a74f7e7b6a044a93c66ca` |
| resolution `verification.json` | `7a500585beb44430402987ef9b5cb990619462463161e42d03980ef9ba855b3c` |
| resolution preregistration | `9bdda6b3822a33c14c47528396860e148421eb2e1f05619f1ad7302e9d2ddb8c` |
| direct-coordinate amendment | `a8917f7c3afcba47a7f8405774b649b9a10cfd2111fd0f700df55387ace0ed48` |
| resolution-verification amendment | `7174362fea6759098929476893f4deb549566d337781fbdf96d6d26fdcc86e3c` |

Text authorities are hashed after CRLF-to-LF canonicalization. Binary artifacts
are hashed byte for byte.

### 2.2 Background preflight

Both implementations must independently require the exact artifact key set
`x`, `psi_real`, `psi_imag`, `h`, `a`, and `c`; finite C-contiguous `float64`
arrays; and shapes

$$
(29),\quad(29^3,2),\quad(29^3,2),\quad(29^3,3),
\quad(29^3,3,3),\quad(29^3).
\tag{LH3}
$$

Here compact notation suppresses the three explicit spatial axes. Coordinates
must equal `linspace(-4,4,29)` to $10^{-14}$ in maximum norm. Charge relative
error must be at most $10^{-12}$, shell residual at most $10^{-12}$, and scalar
or vector $C_4$ projection residual at most $5\times10^{-12}$. Each frozen
scalar must satisfy

$$
|x_{\rm measured}-x_{\rm frozen}|
\le10^{-11}+10^{-9}|x_{\rm frozen}|.
\tag{LH4}
$$

The source coefficient vector, artifact digest, source receipt digests, and
source verdict must match before the operator is built.

## 3. Frozen action and coefficient point

### 3.1 Fields and coefficients

Each grid node carries eighteen real fluctuation components:

$$
(\operatorname{Re}\psi_1,\operatorname{Re}\psi_2,
 \operatorname{Im}\psi_1,\operatorname{Im}\psi_2,
 h_1,h_2,h_3,a_1^1,\ldots,a_3^3,
 \operatorname{Re}\chi,\operatorname{Im}\chi).
\tag{LH5}
$$

The frozen dimensionless coefficients are

$$
\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{Cx}=k_{C\mathfrak s}=u_C=1,
\qquad
u_\rho=u_\varphi=u_H=4,
\tag{LH6}
$$

$$
e_C=0.75,
\qquad
h_C=2.9598260763447164,
\qquad
q_C=4,
\qquad
L_{\mathfrak s}=1,
\qquad
\xi_{\rm gf}=1.
\tag{LH7}
$$

The $h_C$ value is the Mapped coupling selected by the completed direct-carrier
campaign. This campaign does not vary or refit it. All fields are independent
of $\mathfrak s$, the no-flux scale sector stays active, and the static slice
sets temporal fields and velocities to zero.

### 3.2 Physical energy

The operator differentiates

$$
\begin{aligned}
\widehat E_{\rm phys}=\Delta V\sum_{\mathbf n}\bigg[&
\frac12|D_i\psi|^2
+\frac{u_\rho}{4}(\rho-1)^2
+\frac{u_\varphi}{2}(\Delta_\varphi)^2
+\frac{\gamma_x}{4}F_{ij}^aF_{ij}^a\\
&+\frac{\gamma_x}{2}|D_i h|^2
+\frac{u_H}{4}(|h|^2-1)^2
+\frac{k_{Cx}}{2}|\partial_i\chi|^2\\
&+\bigl(e_C-h_C(1-\rho)\bigr)|\chi|^2
+\frac{u_C}{2}|\chi|^4\bigg].
\end{aligned}
\tag{LH8}
$$

The Pauli matrices, curvature sign, covariant derivatives, and composition
field are those of the stationary action. Every first derivative uses the
registered `edge_order=2` stencil with spacing $2/7$, and every energy sum
includes all $29^3$ nodes.

The optimizer diagnostic

$$
\widehat E_{\rm gf}
=\frac{\xi_{\rm gf}}2\Delta V
 \sum_{\mathbf n,a}(\partial_i a_i^a)^2
\tag{LH9}
$$

is excluded from the augmented functional, every Hessian-vector product, every
directional curvature, and every eigenvalue. Its background value is reported
only as an identity diagnostic.

### 3.3 Static constraints

The fixed-charge condition removes the one real carrier normal. The complex
carrier phase remains. On the static PA42 slice, the linearized Gauss momentum
constraint has rank zero because temporal gauge fields and velocities vanish.
The nontrivial temporal Gauss system belongs to PA43.

## 4. Exact finite-grid tangent

### 4.1 Fixed shell and $C_4$ bases

Every perturbation vanishes on the outer shell. Scalar fields use the
orthonormal orbit basis $U_S$ on the $27^3$ interior. Lexicographically selected
orbits under quarter turns about $z$ give

$$
n_S=27+\frac{27^3-27}{4}=4941.
\tag{LH10}
$$

Spatial vectors use the orthonormal equivariant basis $U_V$. Each four-site
orbit carries three rotated Cartesian seeds, while each of the 27 axial sites
carries its invariant $z$ component:

$$
n_V=3\frac{27^3-27}{4}+27=14769.
\tag{LH11}
$$

Sparse Gram checks must give identity to $10^{-12}$ in maximum norm.

### 4.2 Fixed-charge carrier tangent

Let $\bar c_S=U_S^{\mathsf T}\bar c$. A deterministic Householder reflector
maps $\bar c_S/\|\bar c_S\|_2$ to the first coordinate. The remaining 4,940
coordinates span the real-carrier tangent. The implementation applies the
reflector matrix-free and requires orthogonality and charge-normal residuals at
most $10^{-11}$. All 4,941 imaginary-carrier coordinates remain.

The normalized global phase generator is

$$
v_{U(1)}:\qquad
\delta\operatorname{Re}\chi=0,
\qquad
\delta\operatorname{Im}\chi=\bar c.
\tag{LH12}
$$

Its Rayleigh quotient must have magnitude at most $10^{-10}$. Its Hessian
residual is reported.

The pre-gauge base dimension is

$$
n_{\rm base}=7n_S+3n_V+(n_S-1)+n_S=88775.
\tag{LH13}
$$

### 4.3 Boundary-preserving gauge parameters

A permitted infinitesimal gauge parameter is zero on the outer shell and has
zero source-stencil gradient there. The complete allowed space is constructed
without a dense null-space decomposition.

Let $\beta$ be a scalar $C_4$ field on indices $2,\ldots,26$ in each axis. For
one coordinate define

$$
s(i)=\begin{cases}
2,&i=1,\\
i,&2\le i\le26,\\
26,&i=27,
\end{cases}
\qquad
w(i)=\begin{cases}
\tfrac14,&i\in\{1,27\},\\
1,&2\le i\le26.
\end{cases}
\tag{LH14}
$$

The extension is zero if any coordinate is 0 or 28 and otherwise is

$$
\alpha_{ijk}=w(i)w(j)w(k)\,
\beta_{s(i)s(j)s(k)}.
\tag{LH15}
$$

Equation (LH15) enforces the one-sided `edge_order=2` conditions
$4\alpha_1-\alpha_2=0$ and
$4\alpha_{27}-\alpha_{26}=0$ on every face, including their compatible edge
and corner products. The central $25^3$ orbit basis has

$$
n_\alpha=25+\frac{25^3-25}{4}=3925
\tag{LH16}
$$

columns per gauge color. Extended columns are normalized individually; their
supports remain disjoint, so the resulting basis is orthonormal. Preflight must
verify shell values and all three shell derivatives to $10^{-12}$.

### 4.4 Coupled gauge image and sparse orthogonal projector

For each allowed $\alpha=\alpha^aT^a$, both implementations independently
construct

$$
\delta_\alpha\psi=i\alpha^aT^a\bar\psi,
\qquad
\delta_\alpha h=\bar h\times\alpha,
\qquad
(\delta_\alpha a)_i=\partial_i\alpha+\bar a_i\times\alpha,
\qquad
\delta_\alpha\chi=0.
\tag{LH17}
$$

Projection into $U_S$ and $U_V$ gives a sparse coupled map
$G\in\mathbb R^{88775\times11775}$. Its carrier rows vanish and may remain
implicit. The represented physical dimension is

$$
n_{\rm phys}=88775-3(3925)=77000.
\tag{LH18}
$$

The numerical construction must establish full column rank through successful
factorization of $G^{\mathsf T}G$, three deterministic linear-solve relative
residuals at most $10^{-10}$, a smallest Gram eigenvalue greater than
$10^{-8}$, and an estimated spectral condition number below $10^8$.

The physical projector is

$$
P=I-G(G^{\mathsf T}G)^{-1}G^{\mathsf T}.
\tag{LH19}
$$

`scipy.sparse.linalg.splu` factors the sparse Gram matrix in each
implementation. The factor is only an implementation of (LH19); it does not
change the inner product or add an energy. Three deterministic probes must
satisfy all of:

$$
\frac{\|P^2v-Pv\|_2}{\max(\|Pv\|_2,1)}\le10^{-10},
\qquad
\frac{\|G^{\mathsf T}Pv\|_2}{\max(\|Pv\|_2,1)}\le10^{-10},
\tag{LH20}
$$

$$
\frac{|u^{\mathsf T}Pv-v^{\mathsf T}Pu|}
{\max(|u^{\mathsf T}Pv|,|v^{\mathsf T}Pu|,1)}\le10^{-10}.
\tag{LH21}
$$

The coupled gauge image is the sole local-gauge quotient. No Coulomb condition
or numerical gauge-fixing curvature is added.

## 5. Operator implementation and preflight

### 5.1 Matrix-free Hessian

The primary program imports the stationary action authority for (LH8) and
independently constructs the sparse tangent geometry. For a base direction
$v$, PyTorch `float64` reverse-over-reverse automatic differentiation computes

$$
Kv=\frac1{\Delta V}
\nabla_x^2\!\left(\widehat E_{\rm phys}
-\widehat\omega_CQ_C\right)_{x=0}v.
\tag{LH22}
$$

The physical action is $PKP$. To keep gauge vectors away from the requested
smallest-algebraic spectrum while retaining an ordinary symmetric eigenproblem,
the eigensolver receives

$$
K_\mu=PKP+\mu(I-P),
\qquad \mu=8.
\tag{LH23}
$$

On $\operatorname{range}P$, (LH23) equals the physical Hessian. On the gauge
image it is the fixed positive scalar 8. Every accepted eigenmode must have
$\|G^{\mathsf T}v\|/\max(\|v\|,1)\le10^{-10}$ and eigenvalue below
$\mu/2=4$, so a lifted gauge mode cannot enter the scientific set. The lift is
excluded from all physical Rayleigh and directional-curvature values.

The primary augmented-gradient RMS is

$$
g_{\rm aug,RMS}=\frac{\|P\nabla_x
(\widehat E_{\rm phys}-\widehat\omega_CQ_C)/\Delta V\|_2}
{\sqrt{77000}}
\tag{LH24}
$$

and must not exceed $5\times10^{-6}$. Four deterministic physical pairs must
satisfy the bilinear symmetry residual bound $10^{-9}$.

### 5.2 Directional finite differences

Each implementation uses three independently seeded Gaussian directions,
projects and normalizes each one, and compares the exact physical HVP with

$$
K_hv=\frac{P[g(hv)-g(-hv)]}{2h\Delta V},
\qquad
h\in\{2\times10^{-4},10^{-4},5\times10^{-5}\}.
\tag{LH25}
$$

The smallest-step vector relative error must be at most $5\times10^{-5}$. The
energy curvature

$$
\kappa_h=
\frac{\mathcal L(hv)-2\mathcal L(0)+\mathcal L(-hv)}{h^2\Delta V}
\tag{LH26}
$$

must agree with $v^{\mathsf T}PKPv$ under

$$
|\kappa_h-v^{\mathsf T}PKPv|
\le5\times10^{-5}+5\times10^{-4}|v^{\mathsf T}PKPv|.
\tag{LH27}
$$

The two smallest steps must agree under the same bound. Primary direction seed
is 271828; verifier direction seed is 161803. The verifier also applies
(LH25)–(LH27) to the primary lowest eigenvector.

## 6. Frozen eigensolves

The primary sparse solve is:

| Setting | Value |
|---|---:|
| operator dimension | 88775 |
| physical dimension | 77000 |
| requested eigenpairs | 8 |
| selector | `which="SA"` |
| Krylov dimension | `ncv=40` |
| tolerance | `1e-9` |
| maximum iterations | 2000 |
| initial-vector seed | 424242 |

The initial vector is projected and normalized. Eigenvalues are sorted
algebraically. Every eigenpair must satisfy

$$
r_j=\frac{\|K_\mu v_j-\lambda_jv_j\|_2}
{\max(|\lambda_j|,1)}\le10^{-6},
\tag{LH28}
$$

Euclidean orthogonality residual at most $10^{-8}$, physical-projector residual
at most $10^{-10}$, fixed-shell residual at most $10^{-12}$, and
fixed-charge-tangent residual at most $10^{-11}$. A partial ARPACK result is an
execution failure.

The independent verifier is a separate implementation. It must not import the
primary Hessian program, stationary optimizer, recovery programs, or their
verifiers. It separately implements the physical energy, grid, $C_4$ bases,
charge tangent, allowed gauge extension, coupled sparse gauge map, Gram solve,
orthogonal projector, automatic-differentiation HVP, diagnostics, and
`eigsh` call. Constants may only be duplicated as literal frozen data.

The independent solve requests six smallest-algebraic eigenpairs with
`ncv=32`, tolerance $10^{-9}$, maximum 2000 iterations, and seed 314159. Its
six values must match the six lowest primary values under

$$
|\lambda_j^{\rm ind}-\lambda_j^{\rm pri}|
\le5\times10^{-6}+5\times10^{-4}|\lambda_j^{\rm ind}|.
\tag{LH29}
$$

The verifier reconstructs every saved primary field mode from the base vector,
recomputes its physical HVP and lifted residual, checks the NPZ schema and
hash, and compares the archived arrays at $10^{-11}$ relative tolerance.

## 7. Mode classification

The classification buffer is fixed after all numerical checks as

$$
\epsilon_\lambda=\max\!\left(
10r_{\rm pri},
10r_{\rm ind},
10\Delta_{\rm eig},
10\Delta_{\rm FD},
10g_{\rm aug,RMS},
10^{-7}
\right),
\tag{LH30}
$$

where the residuals are absolute eigen-equation residual norms over the six
matched modes, $\Delta_{\rm eig}$ is the largest paired eigenvalue difference,
$\Delta_{\rm FD}$ is the largest accepted smallest-step directional-curvature
disagreement, and $g_{\rm aug,RMS}$ is the larger value from the two
implementations.

For each matched mode:

- **negative:** $\lambda+\epsilon_\lambda<0$ and both implementations'
  smallest-step directional curvatures plus $\epsilon_\lambda$ are negative;
- **positive:** $\lambda-\epsilon_\lambda>0$ and both curvatures minus
  $\epsilon_\lambda$ are positive;
- **near-zero:** neither inequality holds.

A verified negative mode among the six independently matched lowest modes is
sufficient to reject energetic stability at the frozen scope. If no negative
mode occurs, the near-zero eigenspace must be exactly one-dimensional, have
absolute overlap at least 0.90 with (LH12) in both implementations, and leave
the other five matched modes positive. Any additional or unassigned near-zero
mode is inconclusive.

For every negative or near-zero mode, node power sums all eighteen real
components. Report

$$
P_{\rm part}=\frac{(\sum_{\mathbf n}p_{\mathbf n})^2}
{\sum_{\mathbf n}p_{\mathbf n}^2}
\tag{LH31}
$$

and the componentwise FFT power fraction for which any Cartesian frequency has
magnitude at least 0.75 of Nyquist. A mode is spatially resolved only if

$$
P_{\rm part}\ge16,
\qquad
f_{\rm high}\le0.20.
\tag{LH32}
$$

Failure of (LH32) does not change an exact finite-matrix sign. It changes the
separate spatial interpretation to
`INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE`.

## 8. Frozen gates and verdict tree

Evaluate these gates in order:

| Gate | Pass condition |
|---|---|
| LH1 | Manifest, source receipts, selected NPZ, coefficient point, background scalars, schema, boundary, $C_4$, localization, retention, and charge checks pass |
| LH2 | Scalar/vector dimensions, allowed gauge extension, coupled gauge rank, sparse Gram factorization, physical dimension, and projector probes pass independently |
| LH3 | Augmented gradient, global phase, operator symmetry, exact HVP, and finite-difference checks pass independently |
| LH4 | Both eigensolves converge; residual, orthogonality, physicality, finiteness, lift-separation, archive, and six-value comparison checks pass |
| LH5 | The six matched lowest physical modes contain no verified negative mode |
| LH6 | Exactly one matched near-zero mode is assigned to global $U(1)_C$ and the other five are verified positive |
| LH7 | Every verified negative or near-zero mode passes the spatial diagnostic |

The first applicable scientific branch is:

1. LH1 fails: `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`.
2. LH1 passes and LH2 fails: `INCONCLUSIVE—GAUGE QUOTIENT`.
3. LH1–LH2 pass and LH3 fails: `INCONCLUSIVE—HESSIAN PREFLIGHT`.
4. LH1–LH3 pass and LH4 fails:
   `INCONCLUSIVE—EIGENSOLVER OR VERIFICATION`.
5. LH1–LH4 pass and LH5 fails:
   `FAIL—NEGATIVE PHYSICAL MODE ON LOCALIZED BRANCH`.
6. LH1–LH5 pass and LH6 fails:
   `INCONCLUSIVE—UNRESOLVED PHYSICAL ZERO MODE`.
7. LH1–LH6 pass:
   `PASS—NONNEGATIVE LOCALIZED C4 FINITE-GRID PA42 HESSIAN`.

LH7 supplies a separate spatial verdict. The separate mesh verdict is always
`INCONCLUSIVE—NO LOCALIZED HESSIAN RESOLUTION SEQUENCE`, because this campaign
computes the Hessian only on `X2`.
The final receipt's `pass` field and successful process exit require LH1–LH6.
Its separate `infrastructure_pass` field records LH1–LH4, allowing a verified
negative spectrum to remain distinguishable from an implementation failure.


The campaign stops after this tree. No failed or unfavorable result receives a
larger eigensolve, changed projector, changed lift, altered tolerance, shifted
background, changed coefficient, or alternative classification rule.

## 9. Programs and immutable receipts

Primary program:

- `computations/particle_localized_physical_hessian.py`

Independent verifier:

- `computations/verify_particle_localized_physical_hessian.py`

Frozen source manifest:

- `computations/particle_localized_physical_hessian_manifest.json`

Run directory:

- `runs/20260903_particle_localized_physical_hessian/`

Required receipts:

- `preflight_verification.json`—independent source, background, tangent,
  projector, HVP, phase, symmetry, and finite-difference receipt;
- `results.json`—primary preflight, eight-mode spectrum, diagnostics, and
  pending-verification status;
- `eigenmodes.npz`—eigenvalues, base vectors, full-grid fields, and global
  phase vector;
- `verification.json`—independent six-mode solve, primary reconstruction,
  comparisons, gates, classification, and final verdict.

Execution order is:

```text
python computations/verify_particle_localized_physical_hessian.py --preflight
python computations/particle_localized_physical_hessian.py
python computations/verify_particle_localized_physical_hessian.py
```

Python 3.12, NumPy, SciPy, and the installed ROCm PyTorch build are used with
`CUDA_VISIBLE_DEVICES=0`,
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, and `HSA_ENABLE_SDMA=0`.
Both implementations require `torch.float64`, disable TensorFloat-32, and
enable deterministic algorithms.

The manifest is created after both programs are complete and before preflight.
It binds this preregistration, both implementations, the stationary action
authority used by the primary, all source recovery authorities, source
receipts, and the selected NPZ. Any source mismatch stops execution.

Before the canonical preflight, controlled copies must demonstrate independent
rejection of at least two corruptions: changing the frozen $h_C$ coefficient
and changing the frozen diagnostic physical energy. These tests must not alter
the canonical manifest or receipts.

## 10. Scope after any verdict

A passing result establishes the low-sign classification of one explicit
77,000-dimensional physical finite-grid matrix in the registered $C_4$ class.
A failing result identifies a verified negative direction of that same matrix.
Neither outcome establishes:

- perturbative stability outside the represented $C_4$ class;
- a Hessian resolution sequence or continuum spectrum;
- infinite-domain existence or unrestricted basin ordering;
- nonzero scale modes or scale-direction dynamics;
- the PA43 temporal pencil or a real-time mode frequency;
- nonlinear orbital stability, tunnelling, decay, or lifetime;
- spontaneous formation from generic initial data;
- physical mass, radius, electric charge, spin, statistics, or particle
  identity.

## References

- `computations/particle-carrier-resolution-recovery-prereg.md`—frozen source-branch refinement protocol.
- `computations/particle-carrier-resolution-recovery-report.md`—qualified four-grid localized retained branch.
- `computations/particle_carrier_resolution_recovery_manifest.json`—source implementation and receipt graph.
- `computations/particle-physical-hessian-precision-v2-prereg.md`—diffuse-background finite-grid quotient definitions and checks.
- `computations/particle-physical-hessian-precision-v2-report.md`—distinct diffuse-background spectrum.
- `computations/particle_stationary_bvp.py`—stationary physical-energy authority used by the primary implementation.
- `foundations/particle-stationary-action-closure.md`—PA32 action and PA42–PA43 qualification boundary.
- `foundations/matter-completion-boundary.md`—matter-completion scope boundary.
- `foundations/core-trapped-charge-support.md`—carrier localization and retention boundary.
- `foundations/nonabelian-magnetic-core-boundary.md`—coupled core and confinement boundary.
