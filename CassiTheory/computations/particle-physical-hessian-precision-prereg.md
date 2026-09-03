# Particle Physical Hessian Campaign on the Precision Background

## Status: Preregistered—September 2026

## Abstract

This campaign computes the PA42 constrained energetic Hessian of the selected
higher-precision stationary background. The operator is the second variation of
the gauge-invariant physical energy at fixed carrier charge, restricted to the
registered finite Cartesian grid, fixed boundary values, and
$C_4$-equivariant field class, followed by the orthogonal quotient of every
boundary-preserving local $SU(2)_Q$ gauge direction. The numerical
gauge-fixing penalty is excluded from the operator.

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
> after imposing fixed charge and fixed boundary values and quotienting every
> boundary-preserving local gauge direction?

The reduced symmetric-definite pencil is

$$
\begin{aligned}
\mathcal K_{\rm phys}
&=\left.
\frac{1}{\Delta V}B^{\mathsf T}
\nabla^2\!\left(\widehat E_{\rm phys}
                 -\widehat\omega_C Q_C\right)
B\right|_{\bar\Phi},\\
\mathcal M_{\rm phys}&=B^{\mathsf T}B,\\
\mathcal K_{\rm phys}v&=\lambda\mathcal M_{\rm phys}v.
\end{aligned}
\tag{PH1}
$$

Here $B$ injects quotient coordinates into the fixed-boundary, fixed-charge
base tangent, $\bar\Phi$ is the frozen background, and

$$
Q_C=\Delta V\sum_{\mathbf n}|\chi_{\mathbf n}|^2=4.
\tag{PH2}
$$

The $1/\Delta V$ factor and the positive metric
$\mathcal M_{\rm phys}$ make (PH1) self-adjoint in the discrete physical
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
  `runs/20260902_particle_stationary_precision_v5/fields_block01.npz`;
- SHA-256:
  `ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e`;
- family and basin: `P:separated_core`;
- grid: $(R,N,\Delta x,\Delta V)=(4,17,0.5,0.125)$;
- charge: $Q_C=4$;
- physical energy:
  $\widehat E=3.854183410304054$;
- physical first-variation RMS:
  $5.471248126403579\times10^{-5}$;
- cutoff virial:
  $1.348199173228824\times10^{-4}$;
- carrier multiplier:
  $\widehat\omega_C=0.9619139451720476$.

The precision-continuation verdict is
`PASS—HIGHER-PRECISION BACKGROUND`. The independently verified values
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

The source manifest records these pre-execution SHA-256 values. Text
authorities (`.md`, `.py`, and `.json`) are hashed after canonicalizing CRLF
line endings to LF; the binary NPZ is hashed byte for byte. This preserves the
same authority identity across Git checkout line-ending policies.

| Authority | SHA-256 |
|---|---|
| selected precision background NPZ | `ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e` |
| precision `results.json` | `9decc9a751d7c833f92754eb3e5187da9056bc5ddda0c9bd125e188f4e90cfa5` |
| precision `verification.json` | `7667c9617c3e4bd237e77e84226c78805d224002a18a192f25cce24cd2ce4b32` |
| precision source manifest | `1307cc689272eb0100655299232719079ca34697e6e6f74451efb50270d6fc33` |
| precision preregistration | `b95d9f1bbf361161fcc2b1647e1ee707c1ded004be683a791748c1508b6dc0e1` |
| precision primary program | `ca0f824261612e007689d1be1028a33faa9edb4e55c3b6a6372731cc904749dc` |
| precision independent verifier | `e970991cd4947bf6bc4259dec8cb5b5f1ae38546c949d68616639f733b18e87f` |
| stationary BVP preregistration | `5ed7b77312ee28019d246f8a01420fc9b1ad4c6a015e27a4c04f7b04d3225e9e` |
| stationary BVP program | `3143682f8a1052c60243c906b029a5f291a5d767d17b4ebe622deb23d22c5ad1` |
| frozen PA42 operator engine | `4a0e324142ba937388498890cb73089b677f7c3c1e9d8f6c3e3c54295b702b35` |
| PA32/PA42 action authority | `87e005a5995b1dd36f013f416d1df6d493d863c90f946228bb601dcf867a3f82` |
| matter-completion boundary | `3ec218459045a613cbbed55a2ff095a68b677da8c234c0d8a95bdbd6c09c3701` |
| core-support boundary | `b18f94ab7cac17cfcac1dcbcb62e24970c3479dbbec2f62b24e331d711c6f01b` |
| magnetic-core boundary | `f23cfd51d261fb34e6742baace93c5a81f9fda7fcd5e17ca0cab048b352860a1` |

The implementation freeze adds the canonical SHA-256 hashes of this
preregistration, the primary Hessian program, and the independent verifier to
`computations/particle_physical_hessian_precision_manifest.json`. Preflight
applies the same text canonicalization and requires every listed digest to
match. Any mismatch stops before an operator or eigenvalue is evaluated.

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

### 4.2 Boundary-preserving gauge domain

The frozen stationary source calls
`torch.gradient(..., edge_order=2)` for every spatial first derivative.
Both Hessian implementations use that exact one-sided shell stencil and
centered interior stencil.

The continuum boundary authority permits gauge-equivalent pure-gauge
representatives and requires quotient transformations to approach the
identity. The finite registered source selects the strict representative
$a_i^a=0$ on every shell node, and §4.1 fixes every perturbation there.
This campaign therefore quotients only infinitesimal transformations whose
complete $\delta a_i^a$ also vanishes on the numerical shell. Induced
pure-gauge shell values define a different finite-boundary class and are
excluded.

Start from one boundary-zero scalar $C_4$ gauge parameter
$\alpha=U_Sz$. Because $\bar a=0$ on the shell, boundary preservation requires
the source-stencil gradient of $\alpha$ to vanish there. Let
$B_{\partial}$ extract the three shell components of that gradient:

$$
B_{\partial}z
=\left.(\partial_x,\partial_y,\partial_z)U_Sz\right|_{\partial\Omega}.
\tag{PH12}
$$

Its frozen structural rank is 296 at
$10^{-11}\sigma_{\max}$ and remains 296 at the relative cutoffs $10^{-10}$
and $10^{-12}$. The design singular values are

$$
\sigma_{\max}(B_{\partial})=7.141428428542849,
\quad
\sigma_{296}=4.123105625617637,
\quad
\sigma_{297}\le6.35\times10^{-15}.
\tag{PH13}
$$

The orthonormal right-null basis $Z_{\alpha}$ has 559 columns and must satisfy

$$
\|Z_{\alpha}^{\mathsf T}Z_{\alpha}-I\|_{\max}\le10^{-11},
\qquad
\|B_{\partial}Z_{\alpha}\|_2\le10^{-11}.
\tag{PH14}
$$

Each gauge color uses this same boundary-preserving parameter domain.

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

Before the local gauge quotient, the base tangent has

$$
n_{\rm base}=7(855)+3(2535)+854+855=15299
\tag{PH17}
$$

coordinates. The fixed-charge condition has rank one. The static Gauss rank
is zero.

### 4.4 Coupled orthogonal gauge quotient

For $\alpha=U_SZ_{\alpha}\beta$, the full infinitesimal transformation in
source conventions is

$$
\begin{aligned}
\delta_\alpha\psi&=i\alpha^aT^a\bar\psi,\\
\delta_\alpha h&=\bar h\times\alpha,\\
(\delta_\alpha a)_i&=\partial_i\alpha+\bar a_i\times\alpha,\\
\delta_\alpha\chi&=0.
\end{aligned}
\tag{PH18}
$$

The coupled gauge matrix has 13,590 nonzero target rows,
$7(855)+3(2535)$, and $3\times559=1677$ parameter columns. Embedding its zero
carrier rows gives $G\in\mathbb R^{15299\times1677}$. The design calculation
includes every $\delta\psi$, $\delta h$, and $\delta a$ component. It gives
full rank 1677 at all three relative cutoffs $10^{-10}$, $10^{-11}$, and
$10^{-12}$, with

$$
\sigma_{\min}(G)=0.8176573203083152,
\qquad
\sigma_{\max}(G)=3.5702938387634995.
$$

For the first normalized allowed parameter column, the design norms
$(\|\delta\psi\|_2,\|\delta h\|_2,\|\delta a\|_2)$ are
$(0.4997025943382308,1.0000001146783537,2.460424947556975)$ and the maximum
shell residual is $5.10\times10^{-16}$. Preflight reconstructs this coupled
map independently and requires rank 1677, smallest singular value above
$10^{-6}$, rank stability at the three frozen cutoffs, and shell residual at
most $10^{-12}$.

The physical finite-grid tangent is the orthogonal complement

$$
\mathcal V_{\rm phys}=\ker C,
\qquad
C=G^{\mathsf T}.
$$

The noncarrier complement has dimension $13590-1677=11913$. Adding the 854
real-carrier tangent coordinates and all 855 imaginary-carrier coordinates
gives

$$
\dim\mathcal V_{\rm phys}=11913+854+855=13622.
$$

The orthogonal complement of the complete coupled gauge image is the sole
local-gauge quotient. Coulomb constraints are absent from this construction.

A column-pivoted QR factorization of $C$ selects 1677 pivot coordinates $P$
and 13622 free coordinates $F$. With

$$
T=-C_P^{-1}C_F,
\qquad
x_P=Ty,
\qquad
x_F=y,
$$

$B$ is the resulting implicit injection $y\mapsto x$. The frozen design
values are

$$
\kappa_2(C_P)=105.7581581240739,
\qquad
\|T\|_2=64.48593292493692,
\qquad
\|C_P T+C_F\|_{\max}\le5.20\times10^{-15}.
$$

Preflight requires $\kappa_2(C_P)\le10^3$ and a relative constraint residual
at most $10^{-10}$. The reduced metric and its inverse are applied as

$$
\mathcal M_{\rm phys}=I+T^{\mathsf T}T,
\qquad
\mathcal M_{\rm phys}^{-1}
=I-T^{\mathsf T}(I+TT^{\mathsf T})^{-1}T.
$$

This construction removes exactly the coupled gauge image and leaves every
orthogonal physical direction. The total quotient rank relative to the
unconstrained complex-carrier base is 1678: one fixed-charge normal plus 1677
local gauge directions.

The global carrier phase in (PH16) is the only declared continuous physical
symmetry direction in the represented class. Exact spatial translations are
broken by the fixed cube, axial translation remains only an approximate
diagnostic, and the background is invariant under the represented discrete
quarter turns. Every near-zero eigenmode must therefore be assigned to the
one-dimensional global-$U(1)_C$ symmetry subspace or remain unresolved after
its charge, boundary, gauge-orthogonality, and numerical residual diagnostics
are reported.

## 5. Primary operator and eigensolve

### 5.1 Hessian-vector products

The primary driver parameterizes the hash-bound operator engine in
`computations/particle_physical_hessian.py`. The engine imports the frozen
stationary grid and noncarrier energy implementation. It evaluates the complex
carrier terms in (PH7) directly,
builds the base injection and quotient map implicitly, and never materializes
the full $88434\times13622$ matrix $B$.

For each requested quotient vector $v$, PyTorch `float64`
reverse-over-reverse automatic differentiation evaluates

$$
\mathcal K_{\rm phys}v
=\frac1{\Delta V}B^{\mathsf T}
\nabla_x^2
\left(\widehat E_{\rm phys}(\bar\Phi+x)
      -\widehat\omega_C Q_C(\bar\chi+x_\chi)\right)_{x=0}
Bv.
\tag{PH19}
$$

The quotient augmented-gradient RMS is
$\sqrt{g_y^{\mathsf T}\mathcal M_{\rm phys}^{-1}g_y/13622}$ and must be at
most $3\times10^{-4}$. The operator symmetry probe uses four deterministic
$(u,v)$ and requires

$$
\frac{|u^{\mathsf T}\mathcal Kv-v^{\mathsf T}\mathcal Ku|}
 {\max(|u^{\mathsf T}\mathcal Kv|,|v^{\mathsf T}\mathcal Ku|,1)}
\le10^{-9}.
\tag{PH20}
$$

### 5.2 Sparse spectrum

The primary SciPy `eigsh` call is frozen as follows:

| Setting | Value |
|---|---:|
| reduced dimension | 13622 |
| requested eigenpairs | 12 |
| selector | `which="SA"` |
| Krylov dimension | `ncv=48` |
| tolerance | `1e-9` |
| maximum iterations | 2000 |
| initial-vector seed | 424242 |

Eigenvalues are sorted algebraically. SciPy `eigsh` receives
$\mathcal K_{\rm phys}$, $\mathcal M_{\rm phys}$, and the frozen Woodbury
inverse of $\mathcal M_{\rm phys}$. Each eigenvector must have relative
generalized residual

$$
r_j=\frac{\|\mathcal K v_j-\lambda_j\mathcal M v_j\|_2}
{\max(|\lambda_j|\|\mathcal Mv_j\|_2,1)}\le10^{-6},
\tag{PH21}
$$

and the maximum metric-orthogonality residual must satisfy
$\|V^{\mathsf T}\mathcal M V-I\|_{\max}\le10^{-8}$. A nonconverged ARPACK
return is an execution failure even if it contains partial eigenpairs.

## 6. Independent verification and finite differences

### 6.1 Independent implementation

`computations/verify_particle_physical_hessian_precision.py` must not import the primary
Hessian program, the stationary BVP program, either recovery program, or any
recovery verifier. It independently implements:

- NPZ schema and authority checks;
- grid, Pauli matrices, coefficients, and physical energy;
- scalar and vector $C_4$ orbit bases;
- boundary, charge, boundary-preserving gauge, and orthogonal-quotient matrices;
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

Both implementations use three deterministic Gaussian directions normalized
by $v^{\mathsf T}\mathcal M_{\rm phys}v=1$; the primary seed is 271828 and
the verifier seed is 161803. For each direction they compare the exact
automatic-differentiation product with the centered gradient difference

$$
\mathcal K_hv
=\frac{g(hv)-g(-hv)}{2h\Delta V},
\qquad
h\in\{2\times10^{-4},10^{-4},5\times10^{-5}\}.
\tag{PH23}
$$

The smallest-step vector relative error must satisfy

$$
\frac{\|\mathcal K_hv-\mathcal Kv\|_2}
 {\max(\|\mathcal Kv\|_2,1)}\le5\times10^{-5}.
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
$v^{\mathsf T}\mathcal Kv$ under

$$
|\kappa_h-v^{\mathsf T}\mathcal Kv|
\le5\times10^{-5}+5\times10^{-4}|v^{\mathsf T}\mathcal Kv|.
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
- relative gauge-orthogonality residual
  $\|G^{\mathsf T}x\|_2/\max(\|x\|_2,1)\le10^{-10}$;
- metric-normalization residual
  $|v^{\mathsf T}\mathcal Mv-1|\le10^{-10}$.

Every near-zero mode additionally reports component norm fractions,
overlap with the exact global-$U(1)_C$ generator, overlap with discrete $x$,
$y$, and $z$ translation probes, overlap with the axial-rotation probe, and
overlap with the carrier charge normal. The symmetry assignment requires a
one-dimensional near-zero eigenspace and
$|\langle v_j,v_{U(1)}\rangle_{L^2_h}|\ge0.90$; the remaining labels cannot
change a positive or negative classification.

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
| H2 | Scalar/vector dimensions, boundary-gradient rank 296, allowed gauge-parameter dimension 1677, coupled gauge rank 1677, quotient dimension 13622, pivot conditioning, metric inversion, and constraint residuals all pass |
| H3 | Augmented-gradient, global-$U(1)_C$ Rayleigh, operator symmetry, directional HVP, and energy-curvature preflights pass in both implementations |
| H4 | Both eigensolves converge; residual, orthogonality, constraint, finiteness, and six-value comparison checks pass |
| H5 | The six matched lowest modes contain no verified negative mode |
| H6 | Exactly one matched near-zero mode is assigned to global $U(1)_C$ and the other five matched modes are verified positive |
| H7 | Every verified negative or near-zero mode passes the spatial-resolution diagnostic |

The scientific verdict follows the first applicable branch:

1. H1 failure: `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`.
2. H1 passes and H2 fails: `INCONCLUSIVE—GAUGE QUOTIENT`.
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

- `computations/particle_physical_hessian_precision.py`

Independent verifier:

- `computations/verify_particle_physical_hessian_precision.py`

Frozen source manifest:

- `computations/particle_physical_hessian_precision_manifest.json`

Frozen run directory:

- `runs/20260902_particle_physical_hessian_precision/`

Required artifacts:

- `preflight_verification.json`—independent manifest, background, quotient,
  gauge-quotient, HVP, and finite-difference receipt;
- `results.json`—primary operator, spectrum, mode diagnostics, gates, and
  verdict receipt;
- `eigenmodes.npz`—twelve eigenvalues, reduced eigenvectors, and full-grid
  physical mode arrays;
- `verification.json`—independent eigensolve, comparison, directional checks,
  gates, and final verdict.

Execution order:

```text
python computations/verify_particle_physical_hessian_precision.py --preflight
python computations/particle_physical_hessian_precision.py
python computations/verify_particle_physical_hessian_precision.py
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

- `computations/particle-stationary-precision-v5-prereg.md`—higher-precision background acquisition protocol.
- `computations/particle_stationary_precision_v5_manifest.json`—hash-bound precision source and implementation graph.
- `computations/particle-stationary-bvp-pre-registration.md`—coefficient point, grid, field class, and PA32 diagnostics.
- `computations/particle_stationary_bvp.py`—source finite-difference energy implementation.
- `computations/particle_physical_hessian.py`—frozen PA42 operator and eigensolver engine.
- `foundations/particle-stationary-action-closure.md`—PA32 action and PA42–PA43 qualification authority.
- `foundations/matter-completion-boundary.md`—matter-completion scope boundary.
- `foundations/core-trapped-charge-support.md`—carrier support and retention conditions.
- `foundations/nonabelian-magnetic-core-boundary.md`—non-Abelian core and confinement boundary.
