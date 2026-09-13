# Fixed-Graph Anisotropic $SU(2)$ Transfer-to-Hamiltonian Limit

## Status: Pre-registered analytic verification—September 2026

## Abstract

This protocol fixes an anisotropic positive-transfer family whose vanishing temporal step generates the $SU(2)$ Hamiltonian convention used in `foundations/loop-to-bubble-projection-theorem.md` (YM3). The temporal and spatial Wilson character-weight parameters are derived separately, including the factor of two between a coefficient multiplying the unnormalized plaquette trace in the Euclidean action and the parameter in $\exp[(B/2)\operatorname{Tr}U]$.

On every fixed finite spatial graph, normalized central convolution, bounded magnetic multiplication and a symmetric product give positive self-adjoint contractions that preserve the gauge-invariant Hilbert space. Their difference generators and logarithmic generators converge in the strong-resolvent sense to the fixed-graph Kogut–Susskind Hamiltonian, and their repeated products converge strongly to its heat semigroup. A finite isolated-square character calculation tests the normalization, generator convergence and failure controls.

The scope is a fixed finite spatial graph at fixed $a,g>0$. Volume-uniform estimates, a thermodynamic phase, the $a\to0$ limit, continuum Osterwalder–Schrader or Wightman reconstruction and a regulator-independent positive mass gap remain open. The Clay verdict is `NULL`.

## 1. Target Hamiltonian and normalized one-link kernel

Fix a finite spatial lattice graph $\Lambda$ with oriented link set $E$ and one positively oriented copy of each elementary plaquette in $P$. On

$$
\mathcal H_\Lambda=L^2\!\left(SU(2)^E,dU\right)
$$

use $T^a=\sigma^a/2$ and the Hamiltonian convention of Bauer et al., Eqs. (55)–(56):

$$
\boxed{
H_\Lambda=H_E+V,
\qquad
H_E=\frac{g^2}{2a}\sum_{e\in E}E_e^2,
\qquad
V=\frac{1}{g^2a}\sum_{p\in P}
\left(2-\operatorname{Tr}U_p\right).
}
\tag{YMA1}
$$

Here $a,g>0$, $E_e^2$ has eigenvalue $j(j+1)$ in spin $j$, and $0\leq V\leq4|P|/(g^2a)$. Equation (YMA1) is the $SU(2)$ reduction of
$\frac{1}{2g^2a}\operatorname{Tr}(2I-U_p-U_p^\dagger)$ with every unoriented square counted once.

For $B>0$, define

$$
w_B(W):=\exp\!\left(\frac{B}{2}\operatorname{Tr}W\right),
\qquad
C_n(B):=\frac{2nI_n(B)}{B},
\qquad
q_B(W):=\frac{w_B(W)}{C_1(B)}.
\tag{YMA2}
$$

Normalized Haar orthogonality gives $\int w_B\,dW=C_1(B)$, so $q_BdW$ is a central probability measure. Let $R_B$ be convolution by $q_B$. On a matrix coefficient of the dimension-$n=2j+1$ irrep,

$$
\boxed{
R_BD^{(j)}_{mn}
=\eta_j(B)D^{(j)}_{mn},
\qquad
\eta_j(B)
=\frac{C_{2j+1}(B)}{(2j+1)C_1(B)}
=\frac{I_{2j+1}(B)}{I_1(B)}.
}
\tag{YMA3}
$$

Thus $R_B$ is a positive self-adjoint contraction, $\eta_0=1$, and $0<\eta_j<1$ for $j>0$. The fixed-order modified-Bessel expansion gives

$$
-\log\eta_j(B)
=\frac{2j(j+1)}{B}+O(B^{-2})
\qquad(B\to\infty).
\tag{YMA4}
$$

## 2. Anisotropic weights and exact normalization map

Let $\epsilon>0$ be the target Hamiltonian time step and set

$$
\boxed{
B_\tau(\epsilon)=\frac{4a}{g^2\epsilon},
\qquad
B_\sigma(\epsilon)=\frac{2\epsilon}{g^2a}.
}
\tag{YMA5}
$$

The two coefficients are fixed independently by

$$
\frac{2}{B_\tau\epsilon}=\frac{g^2}{2a},
\qquad
\frac{B_\sigma}{2\epsilon}=\frac{1}{g^2a}.
\tag{YMA6}
$$

Write $\mathcal R_B:=\bigotimes_{e\in E}R_B$ and
$M_\epsilon:=M_{\exp(-\epsilon V/2)}$. The one-step operator is

$$
\boxed{
T_\epsilon
:=M_\epsilon\mathcal R_{B_\tau(\epsilon)}M_\epsilon.
}
\tag{YMA7}
$$

In temporal gauge its integral kernel contains one factor
$q_{B_\tau}(U_{t+1,e}U_{t,e}^{-1})$ per spatial link. In a periodic product of steps, the two half-potentials on each time slice combine. Up to configuration-independent normalization factors, the product weight is

$$
\boxed{
\prod_{t,e}
\exp\!\left[\frac{B_\tau}{2}
\operatorname{Tr}U_{0e}(t)\right]
\prod_{t,p}
\exp\!\left[\frac{B_\sigma}{2}
\operatorname{Tr}U_p(t)\right].
}
\tag{YMA8}
$$

Carena et al. write the anisotropic Euclidean action with coefficients
$\widehat\beta_\sigma,\widehat\beta_\tau$ multiplying
$\operatorname{ReTr}(I-U_p)$ and use the Boltzmann weight $e^{-S}$. Their Eq. (3), with $z=2$ for $SU(N)$, gives

$$
\widehat\beta_\sigma=\frac{2}{g_\sigma^2\xi},
\qquad
\widehat\beta_\tau=\frac{2\xi}{g_\tau^2},
\qquad
\xi=\frac{a}{a_\tau}.
\tag{YMA9}
$$

Because (YMA8) uses $\exp[(B/2)\operatorname{Tr}U]$, its character-weight parameter is
$B_\mu=2\widehat\beta_\mu$. The exact bare-convention map

$$
\boxed{
g_\sigma=g_\tau=g_W=2^{1/4}g,
\qquad
a_\tau=\frac{\epsilon}{\sqrt2},
\qquad
\xi=\frac{\sqrt2a}{\epsilon}
}
\tag{YMA10}
$$

gives $B_\tau=4\xi/g_W^2$ and $B_\sigma=4/(g_W^2\xi)$, exactly reproducing (YMA5). Equivalently,

$$
H_\Lambda^{\mathrm{(YMA1)}}(g)
=2^{-1/2}H_{W,\Lambda}(2^{1/4}g)
\tag{YMA11}
$$

when Wilson time $a_\tau$ is converted to target time
$\epsilon=\sqrt2a_\tau$. This is a coupling-and-time convention identity at fixed regulator. It supplies no physical scale or gap estimate. The fixed-$\beta$ isotropic Gibbs subsequence of the Euclidean reflection protocol is a separate result: along (YMA5), $B_\tau\to\infty$ and $B_\sigma\to0$.

## 3. Fixed-graph operator limit

The centrality of $q_B$ makes $\mathcal R_B$ commute with every endpoint gauge action. The potential is gauge invariant. Hence $T_\epsilon$ preserves the physical gauge-invariant subspace. Since $M_\epsilon$ is a strictly positive self-adjoint contraction and $\mathcal R_B$ is a positive self-adjoint contraction with trivial kernel, $T_\epsilon$ is a positive self-adjoint contraction with trivial kernel.

Let $\mathcal D_{\mathrm{PW}}$ be the finite Peter–Weyl span on $SU(2)^E$. It is a core for $\sum_eE_e^2$ and for $H_\Lambda$, because $V$ is bounded. Equations (YMA3)–(YMA6), followed by the norm expansion of the bounded multiplier $M_\epsilon$, give

$$
\boxed{
\lim_{\epsilon\downarrow0}
\frac{I-T_\epsilon}{\epsilon}f
=H_\Lambda f
\qquad(f\in\mathcal D_{\mathrm{PW}}).
}
\tag{YMA12}
$$

Set

$$
A_\epsilon:=\frac{I-T_\epsilon}{\epsilon},
\qquad
H_\epsilon:=-\frac{1}{\epsilon}\log T_\epsilon.
\tag{YMA13}
$$

The $A_\epsilon$ are nonnegative self-adjoint operators. Core convergence with a common lower bound gives

$$
\boxed{A_\epsilon\xrightarrow[\epsilon\downarrow0]{\mathrm{sr}}H_\Lambda.}
\tag{YMA14}
$$

The logarithmic generator follows without a spectral lower bound on $T_\epsilon$. For $0<t\leq1$, $s=1-t$ and $\lambda>0$,

$$
0\leq
\frac{1}{(1-t)/\epsilon+\lambda}
-
\frac{1}{-\log(t)/\epsilon+\lambda}
\leq\epsilon,
\tag{YMA15}
$$

because $-(1-s)\log(1-s)\leq s$. Spectral calculus therefore yields

$$
\left\|(A_\epsilon+\lambda)^{-1}
-(H_\epsilon+\lambda)^{-1}\right\|\leq\epsilon,
$$

and hence

$$
\boxed{H_\epsilon\xrightarrow[\epsilon\downarrow0]{\mathrm{sr}}H_\Lambda.}
\tag{YMA16}
$$

Strong continuity at zero, contraction, and the derivative (YMA12) give the Chernoff product limit

$$
\boxed{
\operatorname*{s-lim}_{N\to\infty}
T_{t/N}^{\,N}=e^{-tH_\Lambda}
\qquad(t\geq0).
}
\tag{YMA17}
$$

All statements restrict to the closed physical Hilbert space because the operators and the Peter–Weyl core are gauge equivariant.

## 4. Isolated-square finite-character fixture

The executable calculation uses the physical class-function basis
$\{\chi_{n/2}:0\leq n\leq C\}$ of one isolated square. Set $a=1$, $\delta=\epsilon/a$, and

$$
g^2\in\left\{\frac12,1,2\right\},
\qquad
C\in\{2,4,6\},
\qquad
\delta\in
\left\{\frac1{256},\frac1{512},\frac1{1024},\frac1{2048}\right\}.
\tag{YMA18}
$$

There are 36 matrix rows. Four links carry the same spin in the gauge-invariant square character, so

$$
R_C(\epsilon)
=\operatorname{diag}_{0\leq n\leq C}
\eta_{n/2}(B_\tau)^4.
\tag{YMA19}
$$

For $\zeta=\epsilon/(g^2a)$, compression of the exact half-potential multiplier has entries

$$
\begin{aligned}
(M_C)_{nm}
&=\int_{SU(2)}
\chi_{n/2}(U)e^{-\epsilon V(U)/2}\chi_{m/2}(U)\,dU\\
&=e^{-\zeta}
\sum_{\substack{r=|n-m|\\r\equiv n+m\ (2)}}^{n+m}
\frac{2(r+1)I_{r+1}(\zeta)}{\zeta}.
\end{aligned}
\tag{YMA20}
$$

The primary implementation evaluates (YMA20) from SciPy Bessel functions and checks it against normalized-Haar Gauss–Chebyshev quadrature. The independent implementation constructs the same matrix directly from a fixed midpoint Haar rule.

Define

$$
T_C=M_CR_CM_C,
\qquad
A_C=\frac{I-T_C}{\epsilon},
\qquad
G_C=-\frac{1}{\epsilon}\log T_C,
\tag{YMA21}
$$

and compare them with the compressed target Hamiltonian

$$
\boxed{
(H_C)_{nm}
=\left[\frac{g^2}{2a}n(n+2)+\frac{2}{g^2a}\right]\delta_{nm}
-\frac{1}{g^2a}
(\delta_{n,m+1}+\delta_{n,m-1}).
}
\tag{YMA22}
$$

The reported errors are

$$
e_A=\frac{\|A_C-H_C\|_2}{\max(1,\|H_C\|_2)},
\qquad
e_G=\frac{\|G_C-H_C\|_2}{\max(1,\|H_C\|_2)}.
\tag{YMA23}
$$

Each matrix row has exactly ten checks:

1. every normalized Bessel multiplier is finite and lies in $(0,1]$;
2. the vacuum multiplier equals one and the retained nontrivial multipliers are strictly ordered;
3. the temporal coefficient in (YMA6) matches $g^2/(2a)$;
4. the spatial coefficient in (YMA6) matches $1/(g^2a)$;
5. $M_C$ is symmetric, positive definite and contractive;
6. $T_C$ is symmetric, positive definite and contractive;
7. $H_C$ is symmetric and nonnegative;
8. $A_C$ is symmetric and nonnegative;
9. $G_C$ is symmetric and nonnegative;
10. the matrix resolvents obey the bound in (YMA15) at $\lambda\in\{1/4,1,4\}$.

For each of the nine $(g^2,C)$ families, four convergence checks require: strict decrease of all $e_A$ values; strict decrease of all $e_G$ values; final-to-first error ratios at most $0.20$ for both generators; and final halving ratios at most $0.70$ for both generators. These are finite-dimensional checks of the frozen schedule, rather than substitutes for the analytic fixed-graph proof.

## 5. Semigroup fixture and firing controls

At $g^2=1$, $C=6$, $a=1$ and $t=1/2$, form

$$
S_N:=T_{t/N}^{\,N},
\qquad
N\in\{64,128,256,512\},
\tag{YMA24}
$$

and compare it with $e^{-tH_C}$. The spectral-norm errors must decrease strictly, and the final-to-first ratio must be at most $0.20$.

The following mutations must fire:

1. replacing $B_\tau$ by $B_\tau/2$ doubles the induced electric coefficient;
2. replacing $B_\sigma$ by $2B_\sigma$ doubles the induced magnetic coefficient;
3. omitting division by $C_1(B)$ at $B=4$ moves the constant-sector convolution eigenvalue away from one;
4. replacing the symmetric product $M_CR_CM_C$ by the ordered product $M_C^2R_C$ at $g^2=a=1$, $C=6$, $\delta=1/16$ produces a nonzero antisymmetric part;
5. the strictly positive controls
   $T_L^{\mathrm{gap}}=\operatorname{diag}(1,e^{-\Delta_L})$ with
   $\Delta_L=2-2\cos(2\pi/L)$ and
   $L\in\{8,16,32,64,128,256\}$ have gaps tending to zero.


A scalar grid with $s\in\{0,2^{-16},2^{-12},2^{-8},2^{-4},1/2,3/4,1-2^{-8}\}$ and $\lambda\in\{1/4,1,4\}$ checks (YMA15). A four-link identity check verifies that (YMA19) produces electric coefficient $2g^2j(j+1)/a$, matching the square reduction of (YMA1).

## 6. Frozen implementation and decision contract

The primary implementation is
`computations/verify_yang_mills_anisotropic_hamiltonian_limit.py`.
The independent implementation is
`computations/verify_yang_mills_anisotropic_hamiltonian_limit_independent.mjs`.

The primary receipt is written to
`runs/yang-mills-anisotropic-hamiltonian-limit/verification.json`.
It contains 36 matrix rows with ten checks each, nine convergence families with four checks each, and exactly 18 top-level checks, for 414 checks total. The top-level checks cover normalized-Haar Bessel coefficients, half-potential fusion versus quadrature, both coefficient maps, the five firing controls, the scalar resolvent grid, the four-link identity, the semigroup schedule, aggregate row and convergence decisions, finite numeric payloads and the declared claim boundary.

The independent implementation uses no SciPy or primary helper code. It computes scaled Bessel ratios with a 65,536-point midpoint integral, constructs half-potential matrices with an independent 16,384-point normalized-Haar midpoint rule, diagonalizes symmetric matrices with a Jacobi eigensolver, rebuilds every row and convergence family, reconstructs every firing control and the semigroup fixture, and compares the primary receipt. Its receipt is written to
`runs/yang-mills-anisotropic-hamiltonian-limit/verification-independent.json` and contains exactly 24 decision checks.

Primary algebra tolerance is $2\times10^{-12}$, positive-spectrum tolerance is $2\times10^{-11}$ relative to spectral scale, quadrature comparison tolerance is $2\times10^{-10}$, and independent reconstruction tolerance is $5\times10^{-8}$. Strict decrease comparisons allow an additive $10^{-13}$ numerical floor while still requiring the frozen ratio bounds.

A primary `PASS` requires all 414 checks. An independent `PASS` requires all 24 decision checks and reconstruction of every primary row. Both receipts bind the protocol and current sources by SHA-256; the independent receipt also binds the primary receipt. Both refuse to overwrite an existing receipt without `--replace`.

A passing receipt records:

- `fixed_graph_anisotropic_hamiltonian_limit=PASS`;
- `analytic_fixed_graph_core_limit=true`;
- `analytic_fixed_graph_strong_resolvent_limit=true`;
- `analytic_fixed_graph_log_generator_limit=true`;
- `analytic_fixed_graph_chernoff_limit=true`;
- `analytic_theorem_outside_executable=true`;
- `finite_isolated_square_fixture=PASS`;
- `fixed_beta_gibbs_identified_with_anisotropic_limit=false`;
- `spatial_volume_uniformity_established=false`;
- `thermodynamic_limit_established=false`;
- `lattice_spacing_limit_established=false`;
- `continuum_limit_established=false`;
- `wightman_reconstruction_established=false`;
- `uniform_mass_gap_established=false`;
- `clay_verdict=NULL`.

Any failed numerical, schedule, source-binding or firing check gives `FAIL`. The Clay verdict remains `NULL` under either executable outcome. Execution stops after one primary and one independent run. A failed run is diagnosed before any replacement receipt is produced.

## 7. Sources

- C. W. Bauer, I. D'Andrea, M. Freytsis and D. M. Grabowska, [A new basis for Hamiltonian $SU(2)$ simulations](https://arxiv.org/abs/2307.11829), Eqs. (55)–(56)—target Hamiltonian, trace and positively oriented plaquette convention.
- M. Carena, E. J. Gustafson, H. Lamm, Y.-Y. Li and W. Liu, [Gauge Theory Couplings on Anisotropic Lattices](https://arxiv.org/abs/2208.10417), Eqs. (1)–(3)—anisotropic Wilson action coefficients and bare anisotropy convention.
- M. Lüscher, [Construction of a selfadjoint, strictly positive transfer matrix for Euclidean lattice gauge theories](https://doi.org/10.1007/BF01614090), *Communications in Mathematical Physics* **54** (1977), 283–292—positive finite-lattice transfer operator.
- P. R. Chernoff, [Note on product formulas for operator semigroups](https://doi.org/10.1016/0022-1236(68)90020-7), *Journal of Functional Analysis* **2** (1968), 238–242—contraction product limit.
- NIST Digital Library of Mathematical Functions, [§10.40](https://dlmf.nist.gov/10.40)—large-argument modified-Bessel asymptotics.
