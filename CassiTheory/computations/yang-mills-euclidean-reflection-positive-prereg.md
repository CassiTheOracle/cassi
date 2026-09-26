# Fixed-Regulator Euclidean Yang–Mills Reflection-Positive Subsequence

## Status: Pre-registered analytic verification—September 2026

## Abstract

This protocol fixes a four-dimensional Euclidean lattice step for pure $SU(2)$ Yang–Mills theory. At every fixed Wilson coupling $\beta>0$, the finite even periodic four-torus measure has positive character coefficients, Osterwalder–Schrader reflection positivity and a positive transfer matrix. Periodic finite-volume measures have weakly convergent subsequences on the compact infinite link-configuration space. Every such limit is translation invariant, gauge invariant, reflection positive and satisfies the Dobrushin–Lanford–Ruelle equations for the Wilson interaction.

The result supplies an infinite-volume Euclidean Gibbs state and an Osterwalder–Schrader Hilbert-space construction at fixed lattice regulator. It does not establish convergence of the full volume sequence, uniqueness, clustering, equivalence to the isotropic Kogut–Susskind Hamiltonian limit, a lattice-spacing limit, continuum regularity or nontriviality, the Wightman axioms, a volume- and regulator-uniform spectral gap, or the Clay Yang–Mills mass gap.

## 1. Finite Wilson measures

Let

$$
\mathbb T_L^4=(\mathbb Z/L\mathbb Z)^4,
\qquad L\in2\mathbb N,
\qquad L\geq4,
$$

with one positively oriented copy of every nearest-neighbour link. A configuration is

$$
U=(U_e)_{e\in E_L}\in X_L:=SU(2)^{E_L},
$$

with normalized Haar product measure $dU$. For every oriented plaquette $p$, let $U_p$ be its ordered holonomy. The Wilson weight and probability measure are

$$
w_\beta(V):=\exp\!\left(\frac\beta2\operatorname{Tr}V\right),
\qquad
 d\mu_{L,\beta}(U)
 :=Z_{L,\beta}^{-1}\prod_{p\subset\mathbb T_L^4}w_\beta(U_p)\,dU.
\tag{YME1}
$$

Compactness of $X_L$, continuity and strict positivity of $w_\beta$ give
$0<Z_{L,\beta}<\infty$ for every finite $L$ and $\beta>0$.

Index the irreducible $SU(2)$ characters by their dimension $n=1,2,\ldots$,
so $\chi_n(I)=n$. Normalized Haar orthogonality gives

$$
\boxed{
 w_\beta(V)
 =\sum_{n=1}^{\infty}C_n(\beta)\chi_n(V),
\qquad
 C_n(\beta)
 =I_{n-1}(\beta)-I_{n+1}(\beta)
 =\frac{2nI_n(\beta)}\beta>0.
}
\tag{YME2}
$$

The one-convolution eigenvalue is

$$
\boxed{
 r_n(\beta)=\frac{C_n(\beta)}n=\frac{2I_n(\beta)}\beta>0.
}
\tag{YME3}
$$

The character series is absolutely and uniformly convergent because
$|\chi_n(V)|\leq n$ and its positive majorant at the identity sums to
$w_\beta(I)=e^\beta$.

## 2. Reflection kernel and finite transfer operator

Let $D^{(n)}$ be a unitary matrix realization of the dimension-$n$
irreducible representation. For $A,B\in SU(2)$,

$$
\begin{aligned}
w_\beta(AB^{-1})
&=\sum_{n\geq1}C_n(\beta)\chi_n(AB^{-1})\\
&=\sum_{n\geq1}\sum_{a,b=1}^{n}
 C_n(\beta)D^{(n)}_{ab}(A)\overline{D^{(n)}_{ab}(B)}.
\end{aligned}
\tag{YME4}
$$

Thus every finite matrix $[w_\beta(A_iA_j^{-1})]_{i,j}$ is positive semidefinite. Products of crossing-plaquette kernels remain positive semidefinite by tensor-product factorization, equivalently by the Schur product theorem after evaluation on a finite set.

For a reflection $\vartheta$ through a plane between adjacent time slices, let $\mathcal A_+$ be the continuous cylinder functions supported strictly in the positive half and define the anti-linear reflection

$$
(\Theta F)(U):=\overline{F(\vartheta U)}.
$$

The Wilson reflection-positivity theorem, applied with (YME2), gives

$$
\boxed{
\int_{X_L}(\Theta F)(U)F(U)\,d\mu_{L,\beta}(U)\geq0
\qquad(F\in\mathcal A_+)
}
\tag{YME5}
$$

whenever the support lies inside one reflected half of the even torus. Site-plane reflection positivity supplies the corresponding translated time planes for gauge-invariant observables. The finite-spatial-volume Wilson transfer operator is self-adjoint and strictly positive on the physical gauge-invariant Hilbert space. After division by its spectral radius, spectral calculus gives a nonnegative fixed-regulator generator. None of these finite-volume statements supplies a lower spectral bound uniform in spatial volume or lattice spacing.

The full geometric factorization and transfer-operator theorem in this section are analytic inputs from the cited lattice-gauge results. The executable checks below test the coefficient normalization, finite reflection Gram matrices, products, weighted transfer matrices and firing controls; they do not replace the analytic reflection-positivity proof.

## 3. Infinite-volume subsequence

Let

$$
X:=SU(2)^{E(\mathbb Z^4)}
$$

with the product topology. This is a compact metrizable space because the link
set is countable and $SU(2)$ is compact metrizable. Choose a nested exhaustion
$B_1\subset B_2\subset\cdots$ of the oriented links of $\mathbb Z^4$ by
centred boxes. Identify each $B_m$ with its non-wrapping image in every
sufficiently large torus, and let $\mu_{L,\beta}^{(m)}$ be the corresponding
local marginal.

For fixed $m$, the probability measures on the compact space
$SU(2)^{B_m}$ are weakly compact. Repeated extraction followed by the Cantor
diagonal choice gives even sides $L_k\to\infty$ and local probability measures
$\nu_{\beta}^{(m)}$ such that

$$
\boxed{
\mu_{L_k,\beta}^{(m)}\Longrightarrow\nu_{\beta}^{(m)}
\quad\text{for every fixed }m.
}
\tag{YME6}
$$

Finite-volume marginalization identities pass to the limit, so the
$\nu_{\beta}^{(m)}$ are projectively compatible. The compact-space
Kolmogorov extension theorem gives a unique probability measure
$\mu_{\infty,\beta}$ on $X$ with these local marginals.

Every finite-volume periodic measure is invariant under lattice translations.
A compactly supported gauge transformation can be periodized once $L$
contains its incident links without wrapping. Apply (YME6) in a box containing
the observable, its translate and every transformed incident link. Translation
and compactly supported gauge invariance then pass to
$\mu_{\infty,\beta}$.

For any fixed $F\in\mathcal A_+$, all links in $F$ and $\Theta F$ fit away
from the second periodic reflection plane for sufficiently large $L_k$.
Equation (YME5) and local weak convergence give

$$
\boxed{
\int_X(\Theta F)F\,d\mu_{\infty,\beta}\geq0.
}
\tag{YME7}
$$

For a finite link set $\Delta$, let $\gamma_{\Delta,\beta}$ be the Wilson
Gibbs specification obtained by integrating the links in $\Delta$ with the
plaquette factors meeting $\Delta$, conditional on the exterior links. The
interaction has finite range, and its density is continuous and strictly
positive on a compact group. Hence $\gamma_{\Delta,\beta}f$ is a bounded
continuous cylinder function whenever $f$ is. Once the torus contains a box
holding the supports of $f$, $\gamma_{\Delta,\beta}f$ and the plaquette
neighbourhood of $\Delta$ without wrapping,

$$
\int f\,d\mu_{L,\beta}
=
\int\gamma_{\Delta,\beta}f\,d\mu_{L,\beta}.
\tag{YME8}
$$

Local convergence in a box containing both cylinder functions yields

$$
\boxed{
\int f\,d\mu_{\infty,\beta}
=
\int\gamma_{\Delta,\beta}f\,d\mu_{\infty,\beta}.
}
\tag{YME9}
$$

for every finite $\Delta$ and continuous cylinder $f$. Thus every selected
limit is a translation-invariant, gauge-invariant, reflection-positive Wilson
DLR state at fixed $\beta$.

## 4. Fixed-regulator Osterwalder–Schrader space

On $\mathcal A_+$ define

$$
(F,G)_{\mathrm{OS}}
:=
\int_X(\Theta F)G\,d\mu_{\infty,\beta}.
\tag{YME10}
$$

Equation (YME7) makes this a positive semidefinite sesquilinear form. Quotienting its null space and completing gives a Hilbert space $\mathcal H_{\mathrm{OS},\beta}$. Lattice-time translations act through the standard reflection-positive reconstruction, and the normalized positive transfer operator has a nonnegative spectral generator on its support.

This construction is entirely at fixed lattice regulator. Continuum Osterwalder–Schrader regularity, Euclidean covariance restoration, nontrivial Schwinger functions, Wightman reconstruction and a positive physical mass gap require estimates uniform as the lattice spacing tends to zero.

## 5. Firing controls and implication boundaries

Positive finite transfer operators do not imply a uniform gap. For

$$
\delta_L:=2-2\cos(2\pi/L),
\qquad
T_L^{\mathrm{ctl}}:=\operatorname{diag}(1,e^{-\delta_L}),
\tag{YME11}
$$

every $T_L^{\mathrm{ctl}}$ is strictly positive while $\delta_L\to0$.

Compactness does not imply convergence of the full sequence. The probability measures

$$
\nu_L=
\begin{cases}
\delta_0,&L\text{ even},\\
\delta_1,&L\text{ odd}
\end{cases}
\tag{YME12}
$$

have two constant subsequences and no full-sequence limit.

Reflection positivity depends on nonnegative character coefficients. In each scheduled firing fixture, the highest retained coefficient is replaced by

$$
C_N^{\mathrm{bad}}
:=-\frac{1+\sum_{n<N}nC_n}{N}.
\tag{YME13}
$$

The resulting kernel has diagonal $-1$ and therefore a negative eigenvalue. A separate asymmetric matrix perturbation must be rejected before any spectral positivity test.

These controls force a receipt to preserve the subsequence qualifier and to keep the uniform-gap and continuum conclusions null.

## 6. Frozen deterministic schedule

The primary implementation is
`computations/verify_yang_mills_euclidean_reflection_positive.py`. The independent implementation is
`computations/verify_yang_mills_euclidean_reflection_positive_independent.mjs`.

The coefficient and finite-kernel schedule is

$$
\beta\in\{1/4,1,4,16\},
\qquad
N\in\{4,8,16\},
\qquad
M\in\{8,12,16\},
\tag{YME14}
$$

for 36 rows. Each row uses $M$ deterministic unit quaternions, evaluates

$$
G_{ij}^{(N)}
:=
\sum_{n=1}^{N}C_n(\beta)
\chi_n(q_iq_j^{-1}),
\tag{YME15}
$$

and checks eight conditions: finite positive coefficients, the character bound $|\chi_n|\leq n$, Gram symmetry, Gram positive semidefiniteness, three deterministic reflection quadratic forms, Schur-product positivity, positivity of $DGD$ for a fixed positive diagonal spatial weight $D$, and a normalized transfer spectrum in $[0,1]$ with nonnegative effective energies. Eigenvalue tolerances are relative to the matrix spectral scale.

Adaptive normalized-Haar quadrature checks $C_n$ for $n=1,\ldots,6$ at every scheduled $\beta$. The primary weak-limit closure fixture uses $G_m=G+I/m$ for $m\in\{1,2,4,8,16,32\}$ and checks positivity plus entrywise convergence to $G$. A finite-simplex fixture forms the normalized diagonal of even powers of a positive transfer matrix at temporal lengths $2,4,8,16,32$ and checks positivity and unit mass. These finite fixtures test the closure operations only; the compactness and DLR conclusions are the analytic argument in §3.

The firing schedule evaluates (YME11) at $L\in\{8,16,32,64,128,256\}$, evaluates (YME12), applies (YME13) to the scheduled $\beta=1$, $N=8$, $M=16$ Gram fixture, and applies an asymmetric perturbation to the same matrix.

The primary receipt is written to
`runs/yang_mills_euclidean_reflection_positive/verification.json`. It contains 36 rows with eight checks each and exactly 20 top-level checks, for 308 checks total. The independent implementation rebuilds every row with a positive Bessel series, a 65,536-point normalized-Haar midpoint rule and an independent symmetric Jacobi eigensolver. Its receipt is written to
`runs/yang_mills_euclidean_reflection_positive/verification-independent.json` and contains exactly 22 decision checks. Both implementations refuse to overwrite an existing receipt without `--replace` and bind the protocol and current sources by SHA-256. The independent receipt also binds the primary receipt.

## 7. Frozen decision contract

A primary `PASS` requires all 308 checks. An independent `PASS` requires all 22 decision checks and reconstruction of all 36 primary rows. Both require the complete schedules, corrected normalized-Haar coefficients, positive finite Gram and transfer matrices within the declared scaled tolerances, all closure fixtures, every firing control and current source bindings.

A passing receipt records

- `fixed_regulator_euclidean_support=PASS`;
- `finite_torus_measure_exists=true`;
- `finite_volume_reflection_positivity_analytic_input=true`;
- `finite_volume_positive_transfer_analytic_input=true`;
- `infinite_volume_subsequence_argument=ANALYTIC`;
- `infinite_volume_measure_constructed_by_verifier=false`;
- `full_sequence_convergence_established=false`;
- `uniqueness_established=false`;
- `clustering_established=false`;
- `anisotropic_hamiltonian_equivalence_established=false`;
- `continuum_limit_established=false`;
- `wightman_reconstruction_established=false`;
- `uniform_mass_gap_established=false`;
- `clay_verdict=NULL`.

Any failed numerical, schedule, source-binding or firing check gives `FAIL`. The Clay verdict remains `NULL` under either outcome. A protocol or schedule change requires a new protocol version. Execution stops after one primary and one independent run; a failed run is diagnosed before any replacement receipt is produced.

## 8. Sources

- K. Osterwalder and E. Seiler, [Gauge field theories on a lattice](https://doi.org/10.1016/0003-4916(78)90039-8), *Annals of Physics* **110** (1978), 440–471.
- M. Lüscher, [Construction of a selfadjoint, strictly positive transfer matrix for Euclidean lattice gauge theories](https://doi.org/10.1007/BF01614090), *Communications in Mathematical Physics* **54** (1977), 283–292.
- P. Menotti and A. Pelissetto, [General proof of Osterwalder–Schrader positivity for the Wilson action](https://doi.org/10.1007/BF01221251), *Communications in Mathematical Physics* **113** (1987), 369–373.
- H.-O. Georgii, *Gibbs Measures and Phase Transitions*, 2nd ed., de Gruyter (2011), compact-spin finite-range Gibbs specifications and thermodynamic limits.
