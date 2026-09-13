# 4x2x2 C=1 Sparse Feshbach Screen

## Status: Pre-registered—September 2026

## Abstract

The recovered open $3\times2\times2$ construction contains a finite-volume
Feshbach family at character cutoff $C=1$. This screen moves the spatial graph
to an open $4\times2\times2$ box while keeping the character cutoff fixed at
$C=1$. The gauge-invariant outer space is enumerated exactly, the sixteen
fundamental plaquette matrices are assembled as sparse Hermitian matrices, and
sixteen translated vacuum-plus-one-plaquette source families are tested at four
fixed couplings. The calculation tests whether the finite positive bridge
survives a larger spatial graph without using a dense complement basis.

## 1. Frozen graph and basis

Vertices are ordered lexicographically by $(x,y,z)$ with
$x\in\{0,1,2,3\}$ and $y,z\in\{0,1\}$. Edges are ordered by positive axis:
all $x$ edges, then all $y$ edges, then all $z$ edges. The open box has
$16$ vertices and $28$ oriented links. The eight vertices with $x\in\{1,2\}$
are four-valent; the remaining eight vertices are trivalent. At doubled
character cutoff $C=1$, the complete gauge-invariant spin-network basis is
formed by every admissible link-spin assignment and every allowed four-valent
intertwiner channel.

The fundamental plaquettes are ordered first by $xy$ planes, then $xz$, then
$yz$, with the lexicographic lower-left coordinate inside each orientation:

$$
(\texttt{xy\_z0\_0},\n\texttt{xy\_z0\_1},\n\texttt{xy\_z1\_0},\n\texttt{xy\_z1\_1},\n\texttt{xy\_z2\_0},\n\texttt{xy\_z2\_1},
$$
$$
\texttt{xz\_y0\_0},\n\texttt{xz\_y0\_1},\n\texttt{xz\_y1\_0},\n\texttt{xz\_y1\_1},\n\texttt{xz\_y2\_0},\n\texttt{xz\_y2\_1},
$$
$$
\texttt{yz\_x0},\n\texttt{yz\_x1},\n\texttt{yz\_x2},\n\texttt{yz\_x3}).
$$

All plaquette words use the positive boundary orientation. The source basis is
fixed before any spectrum is computed.

## 2. Sparse normalized Hamiltonian

Let $S$ be the diagonal overlap matrix of the spin-network basis,
$\nu_s=S_{ss}$, and let $M_j$ be the non-normalized matrix of the $j$th
fundamental plaquette multiplication operator. Define

$$
\widetilde W_j=S^{-1/2}M_jS^{-1/2},
\qquad
K_s=\sum_{e=1}^{28}j_e(j_e+1),
$$

and $n_p=16$. For $x\in\{1/64,1/16,1/4,1\}$ use the physical sparse matrix

$$
A_x=\operatorname{diag}(K_s+2n_p x)-x\sum_{j=0}^{15}\widetilde W_j.
\tag{G4C1}
$$

The lowest two eigenvalues are obtained by a symmetric sparse eigensolve. The
reported ground-vector residual must be at most $10^{-9}$ in the Euclidean
norm, and the reported gap $\Delta_x$ must be positive. No dense $25,676$ by
$25,676$ matrix is formed.

For each plaquette define the two source columns

$$
C_j=[e_0,\widetilde W_j e_0],
\tag{G4C2}
$$

where $e_0$ is the all-zero spin-network state. Singular values use a relative
threshold $10^{-10}$; every source family must have rank two.

## 3. Numerical complement screen

Let $(E_x,\Omega_x)$ be the normalized ground Ritz pair and set
$R_x=A_x-E_xI$. Project each source family into $\Omega_x^\perp$ and
orthonormalize it to $P_j$. The retained block is

$$
A_j=P_j^TR_xP_j,
\qquad \alpha_j=\lambda_{\min}(A_j).
$$

The calculation uses a finite-dimensional Ritz-resolution oracle for the
discarded edge. The oracle condition is that the reported Ritz vector resolves
the exact lowest eigenvector at the displayed residual and that the reported
full gap $\Delta_x$ is the lower edge on its exact ground-orthogonal
complement. The residual check is evidence for this numerical condition; it is
not a proof of an exact spectral enclosure. The receipt therefore labels the
result a conditional finite-dimensional numerical screen.

The exact retained-to-discarded coupling norm is computed without a complement
basis:

$$
\beta_j=\left\|(I-P_jP_j^T-\Omega_x\Omega_x^T)R_xP_j\right\|_2.
\tag{G4C3}
$$

Under the Ritz-resolution oracle, use $\delta_j=\Delta_x$ in the scalar Schur
screen

$$
\Phi_j(\lambda)=\alpha_j-\lambda-
\frac{\beta_j^2}{\delta_j-\lambda},
\qquad
\gamma_{j,\mathrm{Fesh}}=
\frac{\alpha_j+\delta_j-
\sqrt{(\alpha_j-\delta_j)^2+4\beta_j^2}}2.
\tag{G4C4}
$$

A row has a positive conditional certificate only when $\Phi_j(0)>0$ and
$\gamma_{j,\mathrm{Fesh}}>0$. The primary also checks
$\Phi_j(\lambda_*)>0$ at
$\lambda_* = \frac12\min(\Delta_x,\delta_j)=\Delta_x/2$ and verifies
$\gamma_{j,\mathrm{Fesh}}\le\Delta_x$ within $10^{-8}$ absolute tolerance.
The use of $\delta_j=\Delta_x$ is the declared finite-dimensional numerical
oracle assumption, not a volume-uniform or continuum estimate.

## 4. Statistic and decision tree

The primary statistic is the $64$-row inventory of basis dimensions, source
ranks, eigen residuals, gaps, $\alpha_j$, $\beta_j$, the scalar test values,
conditional roots and root-to-gap ratios, together with the per-plaquette
summary. Matrix support, Hermiticity, finite values, candidate uniqueness and
source-column hashes are recorded for every plaquette.

Any graph, basis, word, source, sparse-assembly, eigensolve, inequality or
summary failure gives `INCONCLUSIVE`. If all controls pass and all $64$ rows
have positive conditional roots, classify
`SUPPORTS_FINITE_4X2X2_C1_TRANSLATED_FAMILY`. If controls pass but at least one
root is absent, classify `NO_POSITIVE_4X2X2_C1_TRANSLATED_FAMILY`.

The independent checker reconstructs graph counts, the plaquette schedule,
source ranks, scalar conditional-certificate arithmetic and all summary values
from the primary receipt without importing the primary verifier or assembling
the sparse Hamiltonian.


A positive result establishes a finite $4\times2\times2$ and $C=1$ spatial
screen. It does not establish character-cutoff removal, uniform spatial-volume
or lattice-spacing bounds, continuum reconstruction or the Yang–Mills mass
gap.

## 5. Evidence and receipt

Write the primary receipt once to
`runs/yang_mills_4x2x2_c1_feshbach/verification.json` and the independent
receipt once to
`runs/yang_mills_4x2x2_c1_feshbach/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the exact SU(2) tensor primitive source and
the recovered larger-volume protocol and source used as the tensor reference.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.40—the translated finite-family boundary.
- `computations/verify_yang_mills_exact_block_spectrum.py`—SU(2) tensor primitives.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—recovered spin-network contraction pattern.
- `computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md`—finite-regulator recovery conventions.
