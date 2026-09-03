# Particle Physical Hessian Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign computes the PA42 constrained energetic Hessian of the selected
Q2-qualified stationary background. The operator is the second variation of
the gauge-invariant physical energy at fixed carrier charge, restricted to the
registered finite Cartesian grid, fixed boundary values, $C_4$-equivariant
field class, and a discrete Coulomb representative of each gauge orbit. The
numerical gauge-fixing penalty is excluded from the operator.

The calculation uses exact reverse-over-reverse automatic-differentiation
Hessian-vector products, a separately implemented verifier, three finite-
difference step sizes, and two independently seeded sparse eigensolves. The
finite-grid energetic verdict and the spatial-resolution verdict are reported
separately. The available background has no Q2-qualified domain or finer-grid
counterpart, so every continuum and mesh-convergence claim remains
inconclusive under every outcome.

## 1. Frozen question

The primary question is:

> Does the selected `P:separated_core` background have a negative physical
> energetic mode in the complete registered $C_4$ finite-grid tangent space
> after imposing fixed charge, fixed boundary values, and a discrete Coulomb
> gauge slice?

The operator is

$$
\mathcal H_{\rm phys}
 = \left.
 \frac{1}{\Delta V}B^{\mathsf T}
 \nabla^2\!\left(\widehat E_{\rm phys}
                  -\widehat\omega_C Q_C\right)
 B\right|_{\bar\Phi},
\tag{PH1}
$$

where $B$ injects reduced physical coordinates into full real field arrays,
$\bar\Phi$ is the frozen background, and

$$
Q_C=\Delta V\sum_{\mathbf n}|\chi_{\mathbf n}|^2=4.
\tag{PH2}
$$

The $1/\Delta V$ factor makes (PH1) self-adjoint in the discrete physical
inner product

$$
\langle u,v\rangle_{L^2_h}
 =\Delta V\sum_{\mathbf n,A}u_{\mathbf n A}v_{\mathbf n A}.
\tag{PH3}
$$

The calculation addresses PA42 in
`foundations/particle-stationary-action-closure.md`. The mixed temporal PA43
pencil, decay channels, and lifetime lie outside this campaign.

## 2. Immutable background and authority graph

### 2.1 Selected artifact

The only admissible background is

- path:
  `runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`;
- SHA-256:
  `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550`;
- family and basin: `P:separated_core`;
- grid: $(R,N,\Delta x,\Delta V)=(4,17,0.5,0.125)$;
- charge: $Q_C=4$;
- physical energy:
  $\widehat E=3.8542001269281165$;
- physical first-variation RMS:
  $1.936974511462461\times10^{-4}$;
- cutoff virial:
  $1.8910101999779969\times10^{-3}$;
- carrier multiplier:
  $\widehat\omega_C=0.9619135625713447$.

The final recovery verdict is
`PASS—Q2-QUALIFIED PRIMARY BACKGROUND`. The independently verified values
above are immutable inputs. Their scalar comparison tolerance in preflight is

$$
|x_{\rm measured}-x_{\rm frozen}|
 \le 10^{-11}+10^{-9}|x_{\rm frozen}|.
\tag{PH4}
$$

The artifact must also have finite C-contiguous `float64` arrays with the
registered keys and shapes, charge relative error at most $10^{-12}$,
fixed-shell residual at most $10^{-12}$, and scalar/vector $C_4$ projection
residual at most $5\times10^{-12}$ in relative infinity norm.

### 2.2 Frozen authority hashes

The source manifest records these exact pre-execution SHA-256 values:

| Authority | SHA-256 |
|---|---|
| selected background NPZ | `99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550` |
| recovery `results.json` | `258ce9624c705b29af4f46b3b17500d93370a752859516129a73bc83cd6e1ea9` |
| recovery `verification.json` | `e25bf1aee5757c7a85e10c4013ffdfd0f13c0118beac64f442195c1f84964831` |
| recovery report | `7af4c59de3d9ee4cc10499f4f8218dbb501b0b3e436d8622a9cbe158ce2e7c94` |
| recovery preregistration | `e9c2bf8ab3c9001fdd40297eea2d0619e6388dd6d7786d1e0711102f6c4fe264` |
| recovery primary program | `10e269fd2a669f58fbec0c20f4076d9e07f4a693de4ca40221d5bd29cca3a2a9` |
| recovery independent verifier | `787520fcf3abb2ccbb66cc61a5ced29c39e1a9e75976468706ca58bae3de4707` |
| stationary BVP preregistration | `5ed7b77312ee28019d246f8a01420fc9b1ad4c6a015e27a4c04f7b04d3225e9e` |
| stationary BVP program | `3143682f8a1052c60243c906b029a5f291a5d767d17b4ebe622deb23d22c5ad1` |
| PA32/PA42 action authority | `87e005a5995b1dd36f013f416d1df6d493d863c90f946228bb601dcf867a3f82` |
| matter-completion boundary | `3ec218459045a613cbbed55a2ff095a68b677da8c234c0d8a95bdbd6c09c3701` |
| core-support boundary | `b18f94ab7cac17cfcac1dcbcb62e24970c3479dbbec2f62b24e331d711c6f01b` |
| magnetic-core boundary | `f23cfd51d261fb34e6742baace93c5a81f9fda7fcd5e17ca0cab048b352860a1` |

The implementation freeze adds the SHA-256 hashes of this preregistration,
the primary Hessian program, and the independent verifier to
`computations/particle_physical_hessian_manifest.json`. Preflight requires an
exact match for every listed byte stream. Any mismatch stops before an
operator or eigenvalue is evaluated.

## 3. Frozen functional and discretization

### 3.1 Fields and coefficient point

The full real field vector at each node contains eighteen components:

$$
(\operatorname{Re}\psi_1,\operatorname{Re}\psi_2,
 \operatorname{Im}\psi_1,\operatorname{Im}\psi_2,
 h_1,h_2,h_3,a_1^1,\ldots,a_3^3,
 \operatorname{Re}\chi,\operatorname{Im}\chi).
\tag{PH5}
$$

The coefficient point remains

$$
\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{Cx}=k_{C\mathfrak s}=u_C=1,
\quad
u_\rho=u_\varphi=u_H=4,
\quad
e_C=0.75,
\quad
h_C=1.50,
\quad
q_C=4,
\quad
L_{\mathfrak s}=1.
\tag{PH6}
$$

All fields are independent of $\mathfrak s$. The no-flux scale sector remains
active. The static slice sets temporal fields and velocities to zero.

### 3.2 Physical energy

The program evaluates the registered PA32 physical energy

$$
\begin{aligned}
\widehat E_{\rm phys}=\Delta V\sum_{\mathbf n}\bigg[&
\frac12|D_i\psi|^2
+\frac{u_\rho}{4}(\rho-1)^2
+\frac{u_\varphi}{2}(\Delta_\varphi)^2
&+\frac{\gamma_x}{4}F_{ij}^aF_{ij}^a\\
&+\frac{\gamma_x}{2}|D_i h|^2
&+\frac{u_H}{4}(|h|^2-1)^2
&+\frac{k_{Cx}}{2}|\partial_i\chi|^2\\
&+\bigl(e_C-h_C(1-\rho)\bigr)|\chi|^2
&+\frac{u_C}{2}|\chi|^4\bigg],
\end{aligned}
\tag{PH7}
$$

with the Pauli-matrix conventions, curvature sign, and composition field
specified by the stationary source. All first derivatives use
`torch.gradient`/`numpy.gradient` with spacing $0.5$, axes $(x,y,z)$, and
`edge_order=2`. Every energy sum includes the full $17^3$ grid exactly as in
the source program.

The numerical term

$$
\widehat E_{\rm gf}=\frac{\xi_{\rm gf}}2\Delta V
 \sum_{\mathbf n,a}(\partial_i a_i^a)^2
\tag{PH8}
$$

is excluded from (PH1), every Hessian-vector product, and every directional
curvature. It is retained only as a background diagnostic.

### 3.3 Static Gauss constraint

PA42 varies configuration fields on the static slice. With
$\delta a_0=0$, zero field velocities, and the neutral carrier sector,
the linearized Gauss momentum constraint vanishes identically. The nontrivial
linearized Gauss constraint enters PA43 when temporal canonical variables are
added. Preflight records this zero-rank static constraint explicitly.

## 4. Exact finite-grid physical quotient

### 4.1 Fixed boundary and $C_4$ symmetry

Every perturbation vanishes on the outer shell. Scalar fields use the
orthonormal $C_4$ orbit basis $U_S$ on the $15^3$ interior sites. Orbit
representatives are selected in lexicographic order; each orbit column has
value $1/\sqrt{|\mathcal O|}$. There are

$$
\dim U_S=15+\frac{15^3-15}{4}=855
\tag{PH9}
$$

scalar columns.

Spatial vectors use the orthonormal equivariant basis $U_V$. For each
four-site orbit and Cartesian seed $e_i$, the value at the $k$th rotated site
is $R^{-k}e_i/2$, where

$$
R=\begin{pmatrix}0&-1&0\\1&0&0\\0&0&1\end{pmatrix}.
\tag{PH10}
$$

Each of the fifteen sites on the rotation axis contributes only its invariant
$z$ component. Therefore

$$
\dim U_V=3\frac{15^3-15}{4}+15=2535.
\tag{PH11}
$$

The all-grid scalar orbit basis $U_S^{\rm all}$ has 1241 columns and includes
boundary orbits for representing the divergence constraint.

### 4.2 Discrete Coulomb slice

Let $D$ be the source `edge_order=2` divergence from boundary-zero interior
vector values to all $17^3$ scalar grid values. The reduced one-color
constraint matrix is

$$
C_A=(U_S^{\rm all})^{\mathsf T}DU_V.
\tag{PH12}
$$

Its frozen structural rank is 1188 at the relative singular-value cutoff
$10^{-11}\sigma_{\max}$. The rank must remain 1188 at cutoffs
$10^{-10}\sigma_{\max}$ and $10^{-12}\sigma_{\max}$. The design calculation
gives

$$
\sigma_{\max}=4.56558164970823,
\qquad
\sigma_{1188}=0.37222442008723217,
\qquad
\sigma_{1189}\le3.24\times10^{-15}.
\tag{PH13}
$$

A full right-null basis $Z_A$ must satisfy

$$
Z_A^{\mathsf T}Z_A=I_{1347},
\qquad
\|C_AZ_A\|_2\le10^{-11}.
\tag{PH14}
$$

The same spatial null basis is applied independently to the three gauge
colors. The Coulomb slice removes $3\times1188=3564$ coordinates.

### 4.3 Fixed carrier charge and global phase

Write the frozen carrier as
$\bar\chi=\bar c+i0$ and let
$\bar c_S=U_S^{\mathsf T}\bar c$. A deterministic Householder reflector
maps $\bar c_S/\|\bar c_S\|_2$ to the first coordinate. Its remaining 854
columns form $Z_C$ and must satisfy

$$
Z_C^{\mathsf T}Z_C=I_{854},
\qquad
|\bar c_S^{\mathsf T}Z_C|\le10^{-11}.
\tag{PH15}
$$

This removes the one normal direction in $\delta\operatorname{Re}\chi$ to
the fixed-charge sphere. Every one of the 855
$\delta\operatorname{Im}\chi$ scalar coordinates is charge-tangent at the
real background and remains in PA42. The normalized global-$U(1)_C$ generator

$$
v_{U(1)}:\qquad
\delta\operatorname{Re}\chi=0,
\qquad
\delta\operatorname{Im}\chi=\bar c
\tag{PH16}
$$

is retained as an exact symmetry direction. Its straight-line Hessian
Rayleigh quotient must have magnitude at most $10^{-10}$, and its full
Hessian residual is reported against the finite stationarity residual.

The complete reduced dimension is

$$
7(855)+3(1347)+854+855=11735.
\tag{PH17}
$$

The total nontrivial linear constraint rank is $3565$: 3564 Coulomb
conditions plus one fixed-charge condition. The static Gauss rank is zero.

### 4.4 Gauge-slice completeness

Preflight independently constructs the infinitesimal $C_4$ gauge map

$$
(\delta_\alpha a)_i^a
=-\partial_i\alpha^a-\epsilon^{abc}\bar a_i^b\alpha^c
\tag{PH18}
$$

for three boundary-zero scalar gauge parameters. The combined map reports the
fixed-boundary values of $\delta_\alpha a$ and the all-grid divergence
$D\delta_\alpha a$. It must have full column rank $3\times855=2565$ at the
same $10^{-11}\sigma_{\max}$ cutoff, retain that rank at $10^{-10}$ and
$10^{-12}$, and have smallest singular value above $10^{-6}$. These tests
exclude a residual $C_4$ gauge orbit from the Coulomb representative.

The global carrier phase in (PH16) is the only declared continuous physical
symmetry direction in the represented class. Exact spatial translations are
broken by the fixed cube, axial translation remains only an approximate
diagnostic, and the background is invariant under the represented discrete
quarter turns. Every near-zero eigenmode must therefore be assigned to the
one-dimensional global-$U(1)_C$ symmetry subspace or remain unresolved after
its charge, boundary, Coulomb, gauge-orbit, and numerical residual diagnostics
are reported.

## 5. Primary operator and eigensolve

### 5.1 Hessian-vector products

The primary program imports the frozen stationary grid and noncarrier energy
implementation. It evaluates the complex carrier terms in (PH7) directly,
builds the reduced injection implicitly, and never materializes the full
$88434\times11735$ matrix $B$.

For each requested reduced vector $v$, PyTorch `float64`
reverse-over-reverse automatic differentiation evaluates

$$
\mathcal H_{\rm phys}v
=\frac1{\Delta V}\nabla_y
 \left[v^{\mathsf T}\nabla_y
 \left(\widehat E_{\rm phys}(\bar\Phi+B y)
       -\widehat\omega_C Q_C(\bar\chi+B_\chi y)
 \right)\right]_{y=0}.
\tag{PH19}
$$

The projected augmented-gradient RMS at $y=0$ must be at most
$3\times10^{-4}$. The operator symmetry probe uses four deterministic pairs
$(u,v)$ and requires

$$
\frac{|u^{\mathsf T}\mathcal Hv-v^{\mathsf T}\mathcal Hu|}
 {\max(|u^{\mathsf T}\mathcal Hv|,|v^{\mathsf T}\mathcal Hu|,1)}
\le10^{-9}.
\tag{PH20}
$$

### 5.2 Sparse spectrum

The primary SciPy `eigsh` call is frozen as follows:

| Setting | Value |
|---|---:|
| reduced dimension | 11735 |
| requested eigenpairs | 12 |
| selector | `which="SA"` |
| Krylov dimension | `ncv=48` |
| tolerance | `1e-9` |
| maximum iterations | 2000 |
| initial-vector seed | 424242 |

Eigenvalues are sorted algebraically. Each normalized eigenvector must have
relative residual

$$
r_j=\frac{\|\mathcal Hv_j-\lambda_jv_j\|_2}
          {\max(|\lambda_j|,1)}\le10^{-6},
\tag{PH21}
$$

and the maximum orthogonality residual must satisfy
$\|V^{\mathsf T}V-I\|_{\max}\le10^{-8}$. A nonconverged ARPACK return is an
execution failure even if it contains partial eigenpairs.

## 6. Independent verification and finite differences

### 6.1 Independent implementation

`computations/verify_particle_physical_hessian.py` must not import the primary
Hessian program, the stationary BVP program, either recovery program, or any
recovery verifier. It independently implements:

- NPZ schema and authority checks;
- grid, Pauli matrices, coefficients, and physical energy;
- scalar and vector $C_4$ orbit bases;
- boundary, charge, divergence, and gauge-slice matrices;
- augmented-gradient and exact Hessian-vector products;
- eigenpair residual, constraint, Fourier, and participation diagnostics.

Its separate SciPy `eigsh` call requests six smallest-algebraic eigenpairs
with `ncv=32`, tolerance `1e-9`, maximum iterations 2000, and seed 314159.
For $j=1,\ldots,6$, the independent and primary values must agree under

$$
|\lambda_j^{\rm ind}-\lambda_j^{\rm pri}|
 \le5\times10^{-6}+5\times10^{-4}|\lambda_j^{\rm ind}|.
\tag{PH22}
$$

### 6.2 Frozen directional probes

Both implementations use three deterministic normalized Gaussian directions;
the primary seed is 271828 and the verifier seed is 161803. For each direction
they compare the exact automatic-differentiation product with the centered
gradient difference

$$
\mathcal H_hv
=\frac{g(hv)-g(-hv)}{2h\Delta V},
\qquad
h\in\{2\times10^{-4},10^{-4},5\times10^{-5}\}.
\tag{PH23}
$$

The smallest-step vector relative error must satisfy

$$
\frac{\|\mathcal H_hv-\mathcal Hv\|_2}
 {\max(\|\mathcal Hv\|_2,1)}\le5\times10^{-5}.
\tag{PH24}
$$

The same ladder evaluates the energy directional curvature

$$
\kappa_h=
\frac{\mathcal L(hv)-2\mathcal L(0)+\mathcal L(-hv)}
     {h^2\Delta V}.
\tag{PH25}
$$

At $h=5\times10^{-5}$ it must agree with
$v^{\mathsf T}\mathcal Hv$ under

$$
|\kappa_h-v^{\mathsf T}\mathcal Hv|
\le5\times10^{-5}+5\times10^{-4}|v^{\mathsf T}\mathcal Hv|.
\tag{PH26}
$$

The two smallest steps must agree under the same bound. The verifier also
applies (PH23)–(PH26) to the primary lowest eigenvector. These checks expose
sign, normalization, projection, and differentiation errors without sharing
primary code.

## 7. Mode classification

### 7.1 Numerical uncertainty

The classification buffer is fixed after all checks as

$$
\epsilon_\lambda=\max\left(
10r_{\rm pri},
10r_{\rm ind},
10\Delta_{\rm eig},
10\Delta_{\rm FD},
10g_{\rm aug,RMS},
10^{-6}
\right),
\tag{PH27}
$$

where $r_{\rm pri}$ and $r_{\rm ind}$ are the largest absolute eigen-equation
residual norms among the compared modes, $\Delta_{\rm eig}$ is the largest
absolute paired eigenvalue difference, $\Delta_{\rm FD}$ is the largest
small-step directional-curvature disagreement, and $g_{\rm aug,RMS}$ is the
reduced augmented-gradient RMS. Including $g_{\rm aug,RMS}$ prevents the
finite Q2 stationarity residual from being interpreted as a resolved zero or
a weak instability.

For each independently matched mode:

- negative: $\lambda_j+\epsilon_\lambda<0$ and both implementations' smallest-step directional curvatures plus $\epsilon_\lambda$ are negative;
- positive: $\lambda_j-\epsilon_\lambda>0$ and both smallest-step directional curvatures minus $\epsilon_\lambda$ are positive;
- near-zero: neither condition holds.

A verified negative mode among the six independently matched lowest modes is
sufficient to fail finite-grid energetic stability. With no negative mode,
the near-zero eigenspace must contain exactly one mode, that mode must have
absolute overlap at least $0.90$ with the normalized generator $v_{U(1)}$,
and the other five matched modes must be positive. Any additional near-zero
direction or an unassigned near-zero mode keeps the result inconclusive.

### 7.2 Constraint and symmetry diagnostics

Every reported mode must satisfy:

- fixed-shell maximum residual $\le10^{-12}$;
- relative carrier-tangent residual $\le10^{-11}$;
- relative all-grid Coulomb residual $\le10^{-10}$;
- reduced-coordinate normalization residual $\le10^{-10}$;
- gauge-orbit overlap bound $\le10^{-8}$ after projection to the frozen slice.

Every near-zero mode additionally reports component energy fractions,
overlap with the exact global-$U(1)_C$ generator, overlap with discrete $x$,
$y$, and $z$ translation probes, overlap with the axial-rotation probe,
overlap with the carrier charge normal, and overlap with the gauge-image
singular vectors. The symmetry assignment requires a one-dimensional
near-zero eigenspace and $|\langle v_j,v_{U(1)}\rangle|\ge0.90$; the remaining
labels are diagnostics and cannot change a positive or negative
classification.

### 7.3 Spatial-resolution diagnostic

For each full-grid eigenvector, define node power by summing the squares of all
eighteen components. Its participation number is

$$
P=\frac{(\sum_{\mathbf n}p_{\mathbf n})^2}
        {\sum_{\mathbf n}p_{\mathbf n}^2}.
\tag{PH28}
$$

The Fourier high-frequency fraction is the fraction of componentwise FFT
power at wavevectors for which any Cartesian component has magnitude at least
$0.75$ of the Nyquist frequency. A mode is spatially resolved on `P` only if

$$
P\ge16,
\qquad
f_{\rm high}\le0.20.
\tag{PH29}
$$

A verified negative finite matrix mode retains its algebraic classification
when (PH29) fails, while its spatial interpretation becomes
`INCONCLUSIVE—GRID-SCALE NEGATIVE MODE`.

The `D` and `H` stationary backgrounds fail Q2. A mesh-convergence Hessian
comparison is therefore inadmissible. The campaign always reports
`INCONCLUSIVE—NO Q2 DOMAIN/RESOLUTION BACKGROUNDS` for domain, resolution,
continuum, and infinite-volume scope.

## 8. Frozen gates and verdict tree

Evaluate these gates in order:

| Gate | Pass condition |
|---|---|
| H1 | Manifest, selected NPZ, background values, schema, $C_4$, boundary, charge, and coefficient checks all pass |
| H2 | Scalar/vector dimensions, Coulomb rank 1188, rank stability, null residuals, total reduced dimension 11735, and full-rank gauge-slice checks pass |
| H3 | Augmented-gradient, global-$U(1)_C$ Rayleigh, operator symmetry, directional HVP, and energy-curvature preflights pass in both implementations |
| H4 | Both eigensolves converge; residual, orthogonality, constraint, finiteness, and six-value comparison checks pass |
| H5 | The six matched lowest modes contain no verified negative mode |
| H6 | Exactly one matched near-zero mode is assigned to global $U(1)_C$ and the other five matched modes are verified positive |
| H7 | Every verified negative or near-zero mode passes the spatial-resolution diagnostic |

The scientific verdict follows the first applicable branch:

1. H1 failure: `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`.
2. H1 passes and H2 fails: `INCONCLUSIVE—GAUGE SLICE`.
3. H1–H2 pass and H3 fails: `INCONCLUSIVE—HESSIAN PREFLIGHT`.
4. H1–H3 pass and H4 fails:
   `INCONCLUSIVE—EIGENSOLVER OR VERIFICATION`.
5. H1–H4 pass and H5 fails: `FAIL—NEGATIVE PHYSICAL MODE`.
6. H1–H5 pass and H6 fails:
   `INCONCLUSIVE—UNRESOLVED PHYSICAL ZERO MODE`.
7. H1–H6 pass:
   `PASS—NONNEGATIVE C4 FINITE-GRID PA42 HESSIAN`.

H7 supplies the separate spatial verdict and never changes the exact
finite-matrix branch. The domain/resolution verdict is always
`INCONCLUSIVE—NO Q2 DOMAIN/RESOLUTION BACKGROUNDS`.

The campaign stops after this tree. Eigenpair count, Krylov settings, step
sizes, thresholds, background, quotient, coefficient point, and verdict
rules remain fixed after preflight begins. A failed, negative, or inconclusive
result receives no enlarged eigensolve, altered tolerance, shifted
background, or alternative quotient in this campaign.

## 9. Programs, execution order, and receipts

Primary program:

- `computations/particle_physical_hessian.py`

Independent verifier:

- `computations/verify_particle_physical_hessian.py`

Frozen source manifest:

- `computations/particle_physical_hessian_manifest.json`

Frozen run directory:

- `runs/20260902_particle_physical_hessian/`

Required artifacts:

- `preflight_verification.json`—independent manifest, background, quotient,
  gauge-slice, HVP, and finite-difference receipt;
- `results.json`—primary operator, spectrum, mode diagnostics, gates, and
  verdict receipt;
- `eigenmodes.npz`—twelve eigenvalues, reduced eigenvectors, and full-grid
  physical mode arrays;
- `verification.json`—independent eigensolve, comparison, directional checks,
  gates, and final verdict.

Execution order:

```text
python computations/verify_particle_physical_hessian.py --preflight
python computations/particle_physical_hessian.py
python computations/verify_particle_physical_hessian.py
```

The environment is Python 3.12 with NumPy, SciPy, and the installed ROCm
PyTorch build. The device selectors are `CUDA_VISIBLE_DEVICES=0`,
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, and `HSA_ENABLE_SDMA=0`.
Both programs require `torch.float64`; TensorFloat-32 is disabled and
deterministic algorithms are enabled.

## 10. Scope after any verdict

This campaign supplies one exact constrained spectrum of one registered
finite matrix. It cannot establish:

- a stationary solution outside the $C_4$ variational class;
- stability under non-$C_4$ perturbations;
- domain, resolution, or continuum convergence;
- carrier localization or the registered retention inequality;
- an unrestricted global minimum;
- nonzero scale modes or scale-direction dynamics;
- the PA43 temporal pencil or real-time spectral stability;
- nonlinear orbital stability, tunnelling, decay rate, or lifetime;
- physical calibration, particle identity, mass, radius, electric charge,
  spin, or statistics.

A finite-grid `PASS` closes PA42 only at the declared `P`, $C_4$, fixed-charge
scope, including the full complex carrier fluctuation and its assigned global
$U(1)_C$ symmetry zero mode. A verified negative mode rejects that finite-grid
stationary candidate within the same scope. An unassigned near-zero result
requires a Q2-qualified refined background or a stronger stationary solve
before a physical interpretation.

## References

- `computations/particle_stationary_q2_recovery_v2_prereg.md`—frozen background-recovery protocol.
- `computations/particle-stationary-q2-recovery-report.md`—selected Q2-qualified background and scope.
- `computations/particle-stationary-bvp-pre-registration.md`—coefficient point, grids, field class, and PA32 diagnostics.
- `computations/particle_stationary_bvp.py`—source finite-difference energy implementation.
- `foundations/particle-stationary-action-closure.md`—PA32 action and PA42–PA43 qualification authority.
- `foundations/matter-completion-boundary.md`—matter-completion scope boundary.
- `foundations/core-trapped-charge-support.md`—carrier support and retention conditions.
- `foundations/nonabelian-magnetic-core-boundary.md`—non-Abelian core and confinement boundary.
