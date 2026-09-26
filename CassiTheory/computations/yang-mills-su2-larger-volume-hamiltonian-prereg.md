# Finite Larger-Volume SU(2) Hamiltonian and Character-Tail Study

## Status: Pre-registered—September 2026

## Abstract

This protocol defines the next finite three-dimensional SU(2) Hamiltonian target after the open-cube Wilson-support pilot. It uses a $3\times2\times2$ open rectangular box with twenty positively oriented links and eleven plaquettes. The gauge-invariant basis is completed at every vertex by a fixed sequential binary coupling tree, including every intertwiner multiplicity label. The regulated Kogut–Susskind Hamiltonian is assembled at doubled link cutoffs $C=1,2$ and at four fixed couplings.

The study has two finite outputs: a generalized Ritz spectrum and a character-cutoff tail bound for the exact ground state of the declared finite spatial graph. The $C=1$ tail coupling is computed from the complete $C=2$ operator shell; the $C=2$ row receives a separate analytic operator-norm bound. A positive separation between the omitted-sector electric lower bound and the Ritz energy is required before either tail bound is reported as informative. These estimates concern the exact finite-volume, untruncated character Hamiltonian on this graph. They do not supply spatial-volume uniformity, character-cutoff removal, a thermodynamic limit, OS reconstruction or a physical mass gap.

## 1. Question and scope

Does the first larger-than-cube finite spatial graph admit an exactly contracted, gauge-invariant SU(2) Hamiltonian whose nested cutoff Ritz energies and omitted-sector ground-state tail are numerically controlled by a declared electric-energy separation?

The target is deliberately finite:

- spatial graph: an open $3\times2\times2$ box;
- link cutoff: $C\in\{1,2\}$, where $n_e=2j_e\in\{0,\ldots,C\}$;
- coupling: $x\in\{1/64,1/16,1/4,1\}$;
- operator: the fundamental Wilson plaquette sum with the signed cyclic words below;
- state: the lowest generalized eigenvector in the full gauge-invariant truncated basis.

The existing open $2\times2\times2$ pilot is a separate finite operator receipt and is a regression reference only. It is not substituted for the rectangular graph and is not used to infer a volume limit.

## 2. Frozen larger-volume graph

Vertices are coordinates
\[
 V=\{0,1,2\}\times\{0,1\}\times\{0,1\}.
\]
Each link is positively oriented in the coordinate direction. The link IDs, tails and heads are fixed by this table:

| ID | tail | head |
|---:|:---:|:---:|
| 0 | $(0,0,0)$ | $(1,0,0)$ |
| 1 | $(0,0,1)$ | $(1,0,1)$ |
| 2 | $(0,1,0)$ | $(1,1,0)$ |
| 3 | $(0,1,1)$ | $(1,1,1)$ |
| 4 | $(1,0,0)$ | $(2,0,0)$ |
| 5 | $(1,0,1)$ | $(2,0,1)$ |
| 6 | $(1,1,0)$ | $(2,1,0)$ |
| 7 | $(1,1,1)$ | $(2,1,1)$ |
| 8 | $(0,0,0)$ | $(0,1,0)$ |
| 9 | $(0,0,1)$ | $(0,1,1)$ |
| 10 | $(1,0,0)$ | $(1,1,0)$ |
| 11 | $(1,0,1)$ | $(1,1,1)$ |
| 12 | $(2,0,0)$ | $(2,1,0)$ |
| 13 | $(2,0,1)$ | $(2,1,1)$ |
| 14 | $(0,0,0)$ | $(0,0,1)$ |
| 15 | $(0,1,0)$ | $(0,1,1)$ |
| 16 | $(1,0,0)$ | $(1,0,1)$ |
| 17 | $(1,1,0)$ | $(1,1,1)$ |
| 18 | $(2,0,0)$ | $(2,0,1)$ |
| 19 | $(2,1,0)$ | $(2,1,1)$ |

There are eleven plaquettes. Their signed cyclic words are frozen as follows; $+$ denotes the canonical link and $-$ its inverse:

| name | word |
|---|---|
| $xy_{z0,0}$ | $(0^+,10^+,2^-,8^-)$ |
| $xy_{z0,1}$ | $(4^+,12^+,6^-,10^-)$ |
| $xy_{z1,0}$ | $(1^+,11^+,3^-,9^-)$ |
| $xy_{z1,1}$ | $(5^+,13^+,7^-,11^-)$ |
| $xz_{y0,0}$ | $(0^+,16^+,1^-,14^-)$ |
| $xz_{y0,1}$ | $(4^+,18^+,5^-,16^-)$ |
| $xz_{y1,0}$ | $(2^+,17^+,3^-,15^-)$ |
| $xz_{y1,1}$ | $(6^+,19^+,7^-,17^-)$ |
| $yz_{x0}$ | $(8^+,15^+,9^-,14^-)$ |
| $yz_{x1}$ | $(10^+,17^+,11^-,16^-)$ |
| $yz_{x2}$ | $(12^+,19^+,13^-,18^-)$ |

The verifier must perform the endpoint walk for all eleven words before any contraction. The words are part of the operator definition and may not be replaced by unsigned incidence sets.

The selected graph has degree three at the eight vertices with $x\in\{0,2\}$ and degree four at the four vertices with $x=1$. The basis rule below fixes the complete invariant tensor at both valences; no vertex tensor or multiplicity space is left implicit.

## 3. Gauge-invariant basis and normalization

For a link assignment $n=(n_e)_{e=0}^{19}$, use $j_e=n_e/2$ with
\[
 n_e\in\{0,1,\ldots,C\}.
\]
The cutoff applies to link representations. Intermediate representations inside a vertex coupling tree are not independently clipped; every channel allowed by the incident link labels is retained. This makes the $C=1$ basis a literal subspace of the $C=2$ basis.

At each vertex $v$, sort incident half-edges by the tuple
\[
(\text{axis }x<y<z,\;\text{outgoing before incoming},\;\text{link ID}).
\]
Write the resulting incident spins as $(j_1,\ldots,j_d)$. Convert every incoming magnetic index with the SU(2) invariant metric
\[
 g^{(j)}_{mn}=(-1)^{j-m}\,\delta_{m,-n}.
\]
The local invariant basis is the normalized sequential binary tree. For $d=3$, fuse $j_1$ and $j_2$ directly to $j_3$ and contract the output with the final incident leg. For $d\ge4$:

1. fuse $j_1$ and $j_2$ to an intermediate $a_2$;
2. for $r=3,\ldots,d-2$, fuse $a_{r-1}$ and $j_r$ to $a_r$;
3. fuse $a_{d-2}$ and $j_{d-1}$ to the representation $j_d$ and contract that output with the final incident leg $j_d$ using $g^{(j_d)}$.

For the four degree-four vertices this is explicitly
$(j_1,j_2)\to a_2$, $(a_2,j_3)\to j_4$, followed by the invariant
pairing of the two $j_4$ representations. The same rule fixes a degree-six
tree, if a later graph contains one, as
$(j_1,j_2)\to a_2$, $(a_2,j_3)\to a_3$,
$(a_3,j_4)\to a_4$, $(a_4,j_5)\to j_6$, followed by the invariant pairing
of the two $j_6$ representations. Every sequence of intermediate channels
satisfying the SU(2) triangle and parity rules is retained as a separate
multiplicity label. The Clebsch–Gordan coefficients use the real
Condon–Shortley convention, and each tree tensor is normalized to unit
Euclidean norm. This fixes the degree-three and degree-four intertwiner
phases, multiplicities and norms for the selected graph.

A basis state is the complete edge-label assignment together with one admissible internal-channel sequence at every vertex. The primary must record the complete ordered state list and a hash of it. With the normalized local tensors, Haar orthogonality requires the diagonal overlap
\[
 G_{st}=\delta_{st}\,\nu_s,
 \qquad
 \nu_s=\prod_{e=0}^{19}(2j_e+1)^{-1}.
\]
The verifier must test this overlap directly on the first, last, lexicographically central and deterministic nontrivial multiplicity states at each cutoff, and must require positive diagonal entries and zero off-diagonal controls. The full overlap is then used in every generalized eigenproblem; no Euclidean-basis substitution is permitted.

## 4. Exact Wilson contractions and Hamiltonian

For each plaquette $p$, define
\[
 W_p(U)=\chi_{1/2}\!\left(\prod_{(e,s)\in p}U_e^s\right),
 \qquad
 W=\sum_{p=1}^{11}W_p.
\]
The matrix entries are
\[
 (M_{p,C})_{st}=\langle\psi_s,W_p\psi_t\rangle.
\]
The primary uses exact SU(2) representation contraction, normalized Clebsch–Gordan products and Haar orthogonality. Monte Carlo quadrature, a Cartesian group grid and fitted matrix entries are disallowed. The reversed word supplies the dagger control.

A structurally possible entry changes each of the four plaquette link labels by one doubled-spin unit, subject to the cutoff and local intertwiner admissibility, and leaves all spectator link labels unchanged. Internal tree channels may change within their admissible ranges. This rule defines the candidate support; numerical cancellation is recorded rather than removed from the candidate set.

Use the dimensionless finite-lattice Hamiltonian
\[
 H_{C}(x)=K_C+2xN_p I-xW_C,
 \qquad N_p=11,
\]
where
\[
 K_C\psi_s=k_s\psi_s,
 \qquad
 k_s=\sum_{e=0}^{19}j_e(j_e+1),
 \qquad
 W_C=\sum_{p=1}^{11}M_{p,C}.
\]
In the unnormalized basis its covariant matrix is
\[
 \mathsf H_C(x)=\operatorname{diag}\!\big((k_s+22x)\nu_s\big)-xW_C.
\]
The Ritz pair solves
\[
 \mathsf H_C(x)v_C=E_C(x)G_Cv_C,
 \qquad v_C^*G_Cv_C=1,
\]
with the lowest eigenvalue selected. The primary records the lowest two eigenvalues, the generalized residual, the phase convention, all matrix hashes and the normalized coefficient vector. The independent verifier reconstructs the basis, overlap and Hamiltonian without importing primary functions or trusting primary summaries.

## 5. Frozen schedule and finite controls

The complete schedule is the Cartesian product
\[
 C\in\{1,2\},
 \qquad
 x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\}.
\]
No coupling, cutoff, state or tolerance may be added after the first scientific receipt is created.

Every row records and checks:

1. closure of all eleven signed plaquette words;
2. the complete ordered basis and all local multiplicity labels;
3. positive diagonal Haar overlap and the declared normalization formula;
4. finite exact contractions for every candidate entry;
5. Hermiticity of every $M_{p,C}$ and of $H_C(x)$;
6. agreement of each forward matrix with the reversed-word dagger matrix;
7. deterministic forbidden-pair zeros and the full candidate/nonzero counts;
8. generalized eigensolver residual at most $10^{-10}$ after conversion to orthonormal coordinates;
9. finite first excitation energy and nonnegative Ritz gap;
10. nested-state embedding and nonincreasing cutoff energy $E_2(x)\le E_1(x)$ within $10^{-10}$ absolute tolerance.

The finite construction is `PASS` only when all structural, contraction, overlap, Hermiticity, eigenvalue and nested-energy controls pass. A `PASS` is a finite-regulator construction result. It is not a continuum or infinite-volume claim.

## 6. Exact finite-volume character-tail bound

The tail certificate concerns the exact ground state of the untruncated character Hamiltonian on this fixed finite graph. Let $P_C$ project onto all gauge-invariant states whose link labels obey $n_e\le C$, and let $Q_C=I-P_C$. Every state in $Q_C$ has at least one link with
\[
 j_e\ge\frac{C+1}{2},
\]
so
\[
 Q_CKQ_C\succeq \kappa_CQ_C,
 \qquad
 \kappa_C=\frac{(C+1)(C+3)}4.
\]
For SU(2), $|\chi_{1/2}(U_p)|\le2$, hence
\[
 2N_pI-W\succeq0
 \quad\text{and therefore}\quad
 H(x)\succeq K.
\]
For a cutoff Ritz energy $E_C(x)$ define the declared separation
\[
 \Delta_C(x)=\kappa_C-E_C(x).
\]

The coupling from $P_1$ to its full complement is exactly represented by the $C=2$ shell: a fundamental plaquette changes no link label by more than one, and all $C=1$ states therefore couple only to states in $P_2$. Let $H_{21}^{\rm shell}(x)$ be the covariant cross block from $P_1$ to $P_2\setminus P_1$. The primary computes its physical operator norm
\[
 b_1(x)=\left\|
 G_{2,\rm shell}^{-1/2}
 H_{21}^{\rm shell}(x)
 G_1^{-1/2}
 \right\|_2.
\]
The independent verifier recomputes this norm from the cross block and the two independently reconstructed overlap matrices. The $C=2$ row also records the analytic bound
\[
 b_2(x)\le x\,\|W\|\le2N_px=22x,
\]
which does not require an uncomputed $C=3$ matrix.

Let $E_0(x)$ and $\Psi_0(x)$ denote the exact lowest eigenpair of the finite-volume untruncated Hamiltonian. If $\Delta_C(x)>0$, the block equation and the min–max bound $E_0(x)\le E_C(x)$ give
\[
 \|Q_C\Psi_0(x)\|
 \le
 \frac{b_C(x)}{\kappa_C-E_C(x)}\,\|P_C\Psi_0(x)\|
 \le
 \frac{b_C(x)}{\Delta_C(x)}.
\]
The receipt reports
\[
 T_C(x)=\min\!\left(1,\frac{b_C(x)}{\Delta_C(x)}\right)
\]
only when $\Delta_C(x)>0$. This is a finite-volume exact-ground-state character-tail bound under the declared self-adjoint Hamiltonian; it is not a bound on a continuum vacuum or on a thermodynamic sequence.

The $C=1$ bound is `TAIL_CERTIFIED_EXACT_SHELL` when $\Delta_1>0$ and the computed cross block passes all norm and residual controls. It is `TAIL_UNRESOLVED` when the separation is nonpositive or the shell construction fails. The $C=2$ analytic bound is `TAIL_CERTIFIED_ANALYTIC` when $\Delta_2>0$; it is marked `COARSE` whenever $22x/\Delta_2\ge0.1$ and is not promoted to a useful small-tail result. A useful tail row additionally requires $T_C\le0.1$, fixed before execution. No row may use a sampled high-cutoff amplitude in place of this operator estimate.

## 7. Decision tree and boundary

The receipt has separate fields for `finite_construction`, `cutoff_energy_comparison`, `tail_status_C1` and `tail_status_C2`.

- Any failed graph, basis, exact-contraction, overlap, Hermiticity or eigensolver control is `FAIL` for the finite construction.
- A passing finite construction with a positive separation receives the corresponding analytic tail status above.
- A useful tail bound at both scheduled cutoffs is classified `SUPPORTS_FINITE_VOLUME_CUTOFF_TAIL_CONTROL` for that coupling row. A nonpositive separation, a coarse bound or a failed nested comparison is `INCONCLUSIVE` for cutoff qualification, not a failure of the finite matrix construction.
- No aggregate `PASS` or `SUPPORTS` label may be issued for character-cutoff removal, spatial-volume uniformity, the thermodynamic limit, OS reconstruction or a physical gauge-invariant mass gap.

The primary source is

`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`

and the independent reconstruction is

`computations/verify_yang_mills_su2_larger_volume_hamiltonian_independent.py`.

A future execution must create new, non-overwriting receipts at

`runs/yang_mills_su2_larger_volume_hamiltonian/verification.json`

and

`runs/yang_mills_su2_larger_volume_hamiltonian/verification-independent.json`.

The future receipts must bind this protocol, both source files, the exact representation helper versions and the complete ordered basis by SHA-256. The existing receipt `runs/yang_mills_su2_open_cube/verification.json` has SHA-256 `69a0fe9156fe815aefe427b3d7d99780ebd62320a2e780d4e7fce66d89ba0c54`; it may be retained as an implementation regression reference and must not be overwritten or treated as data from the larger graph.

This protocol supplies a concrete finite larger-volume Hamiltonian target with a complete high-valence intertwiner convention and a declared omitted-sector estimate. It does not close the spatial-volume or continuum boundary.

## References

- `computations/yang-mills-su2-open-cube-prereg.md`—finite open-cube basis and oriented Wilson-support pilot.
- `computations/verify_yang_mills_su2_open_cube.py`—bounded trivalent contraction implementation used as a regression reference.
- `computations/yang-mills-exact-block-spectral-prereg.md`—finite SU(2) Hamiltonian, generalized Ritz and cutoff-qualification conventions.
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact representation and Haar-contraction primitives.
- `computations/yang-mills-su2-wilson-2d-prereg.md`—finite-volume Wilson transfer and character-tail certificate.
- `foundations/loop-to-bubble-projection-theorem.md`—regulated Yang–Mills boundary and continuum scope.
