# Finite-Graph Yang–Mills Character-Cutoff Form Lemma

## Status: Pre-registered analytic verification—September 2026

## Abstract

This protocol fixes an analytic finite-graph lemma for the regulated $SU(2)$ Kogut–Susskind Hamiltonian. It addresses the failure of a cutoff-tail estimate based on the separation $\kappa_C-E_C$: the separation can be negative even though the Hamiltonian is nonnegative and the character truncations converge. The replacement uses positivity of the complete Wilson potential, the electric-energy moment of the exact low-energy subspace, and a bounded-potential min–max estimate. It requires no commutation between the character projector and the Wilson operator.

The lemma also fixes the normalized-Haar spanning-tree coordinates needed to control the gauge quotient. The tree coordinates have unit Haar Jacobian, and the gauge-fixed electric form is equivalent to the product electric form on the chord variables with an explicit finite graph constant. The result proves character-cutoff removal for every fixed finite connected graph and gives an explicit tail bound and Ritz-error bound. It does not provide constants uniform in spatial volume or weak coupling and does not establish a continuum Yang–Mills theory or physical mass gap.

## 1. Finite connected graph and Hamiltonian

Let $\Gamma=(V,E)$ be a finite connected oriented graph, let $T\subset E$ be a rooted spanning tree, and let

$$
r=|E|-|V|+1
$$

be the number of chords. On

$$
\mathcal H_{\mathrm{gi}}=L^2\!\left(SU(2)^E,dU_E\right)^{SU(2)^V}
$$

use the nonnegative electric operator

$$
K=-\sum_{e\in E}\sum_{A=1}^3(X_e^A)^2
$$

and the Wilson multiplication operator

$$
V_\Gamma(U)=\sum_{p=1}^{N_p}\left(2-\chi_{1/2}(U_p)\right).
$$

For $x\geq0$ define the dimensionless Hamiltonian

$$
H_\Gamma(x)=K+xV_\Gamma.
\tag{YMCF1}
$$

The fundamental $SU(2)$ character is real and lies in $[-2,2]$. Therefore

$$
0\leq V_\Gamma\leq V_*I,
\qquad
V_*=4N_p.
\tag{YMCF2}
$$

No plaquette commutativity, magnetic perturbation expansion, or strong-coupling restriction is assumed.

## 2. Exact tree coordinates and Haar measure

Fix a root $o$. For every nonroot vertex $v$, let $g_v$ be the ordered tree transport from $o$ to $v$, with inversions when a tree edge is traversed against its declared orientation. For a chord $c=(s(c),t(c))$, define the root-based chord holonomy

$$
h_c=g_{s(c)}U_cg_{t(c)}^{-1}.
\tag{YMCF3}
$$

The inverse coordinate map reconstructs every tree link from the adjacent $g$ variables and every chord from $(g_{s(c)},h_c,g_{t(c)})$. Successive left multiplication, right multiplication and inversion preserve normalized Haar measure, so

$$
dU_E=
\prod_{v\neq o}dg_v
\prod_{c\in E\setminus T}dh_c.
\tag{YMCF4}
$$

The normalized-Haar Jacobian is exactly one. A gauge-invariant function is independent of the nonroot $g_v$ variables and is represented by a function $F(h_1,\ldots,h_r)$ invariant under simultaneous conjugation at the root. Thus

$$
\mathcal H_{\mathrm{gi}}
\cong
L^2\!\left(SU(2)^r,dh\right)^{\operatorname{Ad}SU(2)}.
\tag{YMCF5}
$$

No field-dependent Faddeev–Popov factor appears in this finite lattice tree gauge.

## 3. Explicit electric-form comparison
If $r=0$, the gauge-invariant Hilbert space is one-dimensional and the
spectral conclusion is immediate. The form comparison below assumes $r\geq1$.


For a tree edge $t$ and chord $c$, let

$$
r_{tc}=
\mathbf 1_{\{t\in P_T(o,s(c))\}}
+
\mathbf 1_{\{t\in P_T(o,t(c))\}}
\in\{0,1,2\},
\qquad
M_t=\sum_c r_{tc}.
\tag{YMCF6}
$$

Define

$$
C_{\Gamma,T}
=
1+\max_c\sum_{t\in T}M_t r_{tc}
\leq
1+4r(|V|-1).
\tag{YMCF7}
$$

Let

$$
\mathcal E_{\mathrm{ch}}(F)
=
\sum_{c=1}^{r}\sum_{A=1}^3
\|X_c^AF\|_2^2.
$$

A chord-link electric derivative contributes exactly its chord Casimir. A tree-link derivative becomes a sum of $M_t$ left- or right-invariant chord derivatives with adjoint coefficients. The adjoint matrices are orthogonal, and Cauchy–Schwarz gives

$$
\mathcal E_{\mathrm{ch}}(F)
\leq
\mathcal E_T(F)
\leq
C_{\Gamma,T}\mathcal E_{\mathrm{ch}}(F).
\tag{YMCF8}
$$

Consequently the two closed forms have the same domain with equivalent form norms. Since $SU(2)^r$ is compact, the gauge-invariant electric operator has compact resolvent. Equations (YMCF2) and (YMCF8) imply that $H_\Gamma(x)$ is the self-adjoint bounded-form perturbation of $K$, has the same operator and form domains, is nonnegative, and has compact resolvent.

## 4. Character projectors and form core

Let $P_C$ be the orthogonal projector onto gauge-invariant spin networks for which every doubled edge spin obeys $n_e=2j_e\leq C$, and put $Q_C=I-P_C$. The projectors commute with $K$, increase strongly to the identity, preserve the gauge-invariant subspace, and have finite rank. Peter–Weyl spectral truncation gives

$$
\|(I-P_C)f\|_2^2
+
\mathcal E_K((I-P_C)f)
\longrightarrow0
\quad
(f\in\mathcal Q(K)).
\tag{YMCF9}
$$

Because $V_\Gamma$ is bounded, the same statement holds in the $H_\Gamma(x)$ form norm. The union of the ranges of $P_C$ is therefore a form core. If $E_m(x)$ is the $m$th eigenvalue of $H_\Gamma(x)$, counted from $m=0$ with multiplicity, and $E_{m,C}(x)$ is its Ritz value in $P_C\mathcal H_{\mathrm{gi}}$, then

$$
E_{m,C}(x)\downarrow E_m(x)
\qquad(C\to\infty).
\tag{YMCF10}
$$

## 5. Separation-free low-energy tail bound

Every state in $Q_C\mathcal H_{\mathrm{gi}}$ has at least one link with $j_e\geq(C+1)/2$. Hence

$$
Q_CKQ_C\succeq\kappa_CQ_C,
\qquad
\kappa_C=\frac{(C+1)(C+3)}4.
\tag{YMCF11}
$$

Let $S_m$ be the span of orthonormal eigenvectors associated with $E_0,\ldots,E_m$. Positivity of the Wilson potential gives $K\preceq H_\Gamma(x)$ in quadratic-form order. Therefore every $u\in S_m$ satisfies

$$
\boxed{
\|Q_Cu\|_2^2
\leq
\frac{E_m(x)}{\kappa_C}\|u\|_2^2.
}
\tag{YMCF12}
$$

This estimate does not use $\kappa_C-E_{m,C}>0$. In particular it remains valid in every recovered $3\times2\times2$ row where that separation is negative.

Any certified upper bound $R_m(x)\geq E_m(x)$ makes (YMCF12) computable. A finite Ritz value $R_m=E_{m,C_0}$ is one such bound. Set

$$
\eta_{m,C}=\frac{R_m}{\kappa_C}.
\tag{YMCF13}
$$

When $\eta_{m,C}<1$, $P_C$ is injective on $S_m$. For normalized $u\in S_m$, write $p=\|Q_Cu\|\leq\sqrt\eta$. Since $P_C$ commutes with $K$,

$$
\mathcal E_K(P_Cu)\leq\mathcal E_K(u).
$$

The noncommuting potential is controlled directly by

$$
\left|
\langle P_Cu,V_\Gamma P_Cu\rangle
-
\langle u,V_\Gamma u\rangle
\right|
\leq
V_*\left(2\sqrt\eta+\eta\right).
\tag{YMCF14}
$$

Applying the min–max principle to the $(m+1)$-dimensional space $P_CS_m$ yields the explicit bound

$$
\boxed{
0\leq E_{m,C}-E_m
\leq
\frac{R_m\eta_{m,C}
+xV_*\left(2\sqrt{\eta_{m,C}}+\eta_{m,C}\right)}
{1-\eta_{m,C}}.
}
\tag{YMCF15}
$$

Equations (YMCF12) and (YMCF15) prove tail removal and Ritz convergence at fixed $(\Gamma,x,m)$. Their displayed constants are not uniform in $N_p$, $|V|$, $r$, $x$, or the continuum regulator.

## 6. Frozen exact square control

Use the oriented square

$$
0\xrightarrow{e_0}1\xrightarrow{e_1}2
\xrightarrow{e_2}3\xrightarrow{e_3}0
$$

with root $0$, tree $T=\{e_0,e_1,e_2\}$ and chord $e_3$. The coordinate map is

$$
U_0=g_1,
\quad
U_1=g_1^{-1}g_2,
\quad
U_2=g_2^{-1}g_3,
\quad
U_3=g_3^{-1}h.
\tag{YMCF16}
$$

Here $r=1$, $r_{tc}=M_t=1$ for all three tree links, and $C_{\Gamma,T}=4$. On root-conjugation-invariant class functions, each of the four link Casimirs becomes the same chord Casimir, so equality holds in the upper side of (YMCF8):

$$
K_T=4(-\Delta_h).
\tag{YMCF17}
$$

In the orthonormal character basis $\chi_{n/2}$,

$$
K_{nn}=n(n+2),
\qquad
V_{nm}=2\delta_{nm}-\delta_{n,m+1}-\delta_{n,m-1}.
\tag{YMCF18}
$$

The finite compression of $V$ is positive and bounded by four, while $[K,V]\neq0$.

## 7. Frozen noncommuting firing control

The two-dimensional control is

$$
K_f=
\begin{pmatrix}0&0\\0&4\end{pmatrix},
\qquad
V_f=
\begin{pmatrix}1&-1\\-1&1\end{pmatrix},
\qquad
x=1,
\qquad
P_f=
\begin{pmatrix}1&0\\0&0\end{pmatrix}.
\tag{YMCF19}
$$

It has $V_f\succeq0$, $\|V_f\|=2$, $[K_f,V_f]\neq0$ and exact ground energy

$$
E_f=3-\sqrt5.
$$

The Ritz value is one. With $\eta_f=E_f/4$, the deliberately incomplete commuting-style estimate

$$
1-E_f\leq\frac{E_f\eta_f}{1-\eta_f}
\tag{YMCF20}
$$

is false, while (YMCF15) is true. The verifier must show a positive violation margin for (YMCF20). If this control does not fire, the numerical checks do not demonstrate sensitivity to the omitted noncommuting-potential term.

## 8. Deterministic verification schedule

The primary source is

`computations/verify_yang_mills_finite_graph_cutoff_form.py`.

The independent source is

`computations/verify_yang_mills_finite_graph_cutoff_form_independent.py`.

Both sources independently implement:

1. quaternion $SU(2)$ multiplication, inversion, exponential and logarithm;
2. reconstruction and tree gauge fixing for (YMCF16);
3. the left-trivialized $12\times12$ differential of (YMCF16), whose determinant has absolute value one;
4. a centered finite-difference check of that differential at the fixed coordinate vectors
   $$
   (0.23,-0.17,0.31),\ (-0.29,0.37,0.11),\ (0.19,0.41,-0.27),\ (-0.33,0.14,0.26),
   $$
   with step $10^{-6}$;
5. 64-node Gauss–Chebyshev quadrature of the second kind for the $SU(2)$ class-Haar Gram matrix of characters $n=0,\ldots,15$;
6. the square matrices (YMCF18) at reference cutoff $C_R=64$, couplings
   $$
   x\in\{1/64,1/16,1/4,1,4,16\},
   $$
   low levels $m\in\{0,1\}$, computable upper bounds $R_m=E_{m,C_0}$ at $C_0=2$, and Ritz cutoffs
   $$
   C\in\{1,2,4,8,16,32,48\};
   $$
7. every applicable inequality (YMCF12) and (YMCF15), with an explicit attempted/applicable count;
8. monotone Ritz energies and the exact noncommuting firing control (YMCF19)–(YMCF20).

The primary uses a symmetric-tridiagonal eigensolver. The independent source uses dense Hermitian diagonalization and does not import primary functions. Spectra reconstructed by the two sources must agree within $10^{-10}$. Algebraic identities use tolerance $10^{-12}$, eigensystem residuals use $10^{-10}$, the finite-difference Jacobian uses $10^{-6}$, and every inequality allows additive tolerance $10^{-11}$.

The primary creates

`runs/yang_mills_finite_graph_cutoff_form/verification.json`

and the independent source creates

`runs/yang_mills_finite_graph_cutoff_form/verification-independent.json`.

Neither source overwrites an existing receipt without an explicit `--replace` option. Both receipts bind this protocol and their source files by SHA-256; the independent receipt also binds the primary source and receipt.

## 9. Decision tree and scope

The analytic lemma is accepted as internally verified only when every exact-coordinate, Haar, form-matrix, tail, Ritz, monotonicity, residual, source-binding and firing check passes in both sources. Each receipt must separate:

- `finite_graph_status`, which is `PASS` or `FAIL` for the declared fixed-graph checks;
- `continuum_hypotheses_present`, which is `false` unless spatial-volume-uniform and lattice-spacing-uniform estimates plus a continuum construction have actually been supplied; and
- `clay_verdict`, which must be `NULL` whenever `continuum_hypotheses_present` is `false`.

A finite-graph `PASS` verifies the algebra and deterministic finite controls supporting (YMCF1)–(YMCF20). The proof is the analytic argument in §§1–7, not the numerical receipt. Failure of a numerical identity rejects the implementation or stated constant until resolved. A finite-graph `PASS` is prohibited from being reported as progress on the Clay conclusion unless the missing uniform estimates and continuum construction are independently established.

Character-cutoff removal is established only for each fixed finite graph, fixed coupling and fixed low-energy index. The result supplies no spatial-volume-uniform $C_{\Gamma,T}$, no weak-coupling-uniform Ritz rate, no thermodynamic limit, no reflection-positive Euclidean construction, no Osterwalder–Schrader reconstruction, and no regulator-independent physical mass gap. Those hypotheses are absent in this protocol, so its frozen `continuum_hypotheses_present` value is `false` and its frozen `clay_verdict` is `NULL`.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.18,9.21–9.24,11—isolated-square cutoff theorem, interacting finite-block boundary and continuum obligations.
- `computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`—recovered finite $3\times2\times2$ Hamiltonian and inconclusive separation-based tail schedule.
- `runs/yang_mills_continuum_boundary_audit/verification.json`—hash-bound finite evidence and unresolved continuum boundary.
