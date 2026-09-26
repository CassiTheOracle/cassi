# Translated Block-Local Feshbach Sweep

## Status: Pre-registered—September 2026

## Abstract

The anchored block-local screen retained one first plaquette. This sweep tests
translation and orientation coverage on the recovered open $3\times2\times2$
source without increasing the retained rank. Each of the eleven frozen
fundamental plaquettes is tested separately with the vacuum, producing eleven
rank-two local families at four fixed couplings. The sweep asks whether the
positive finite Feshbach bridge survives across all source-order plaquettes,
including the boundary orientations, rather than only at one anchor.

## 1. Frozen translated family

Use the exact recovered large-volume source and normalized Hamiltonian from
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py` and
`computations/verify_yang_mills_volume_feshbach_bridge.py`. The outer source
dimension is $868$. For each ordinal $j\in\{0,\ldots,10\}$, let

$$
 u_j=S^{-1/2}W_jS^{-1/2}e_0,
 \qquad
 L_{R,j}=\operatorname{span}\{e_0,u_j\}.
 \tag{VTB1}
$$

The source ordering and names are frozen as

$$
(\texttt{xy\_z0\_0},\n\texttt{xy\_z0\_1},\n\texttt{xy\_z1\_0},\n\texttt{xy\_z1\_1},
\texttt{xz\_y0\_0},\n\texttt{xz\_y0\_1},\n\texttt{xz\_y1\_0},\n\texttt{xz\_y1\_1},
\texttt{yz\_x0},\n\texttt{yz\_x1},\n\texttt{yz\_x2}).
$$

Each family contains exactly two arithmetic source columns, vacuum plus one
unit-weight plaquette vector. Orthonormalization uses singular-value threshold
$10^{-10}$ relative to the largest singular value. Every family must have
source rank $2$; otherwise the run is `INCONCLUSIVE`.

## 2. Feshbach rows

For each $(j,x)$ with
$x\in\{1/64,1/16,1/4,1\}$, form the normalized large-volume Hamiltonian,
its lowest eigenpair $(E_0,\Omega)$ and measured outer gap $\Delta_x$. Project
$L_{R,j}$ into $\Omega^\perp$ and orthonormalize it to $V_{P,j}$. Define
$V_{Q,j}$ as the orthonormal complement of
$\{\Omega\}\cup\operatorname{ran}V_{P,j}$. For the shifted matrix
$\widehat H_x-E_0$, define

$$
 A_j=V_{P,j}^*(\widehat H_x-E_0)V_{P,j},
 \quad B_j=V_{P,j}^*(\widehat H_x-E_0)V_{Q,j},
 \quad D_j=V_{Q,j}^*(\widehat H_x-E_0)V_{Q,j}.
$$

Record

$$
 \alpha_j=\lambda_{\min}(A_j),
 \quad \delta_{Q,j}=\lambda_{\min}(D_j),
 \quad \beta_j=\|B_j\|_2,
$$

and at $\lambda_{\rm test}=\frac12\min(\Delta_x,\delta_{Q,j})$ verify

$$
 \|(D_j-\lambda I)^{-1}\|_2\le(\delta_{Q,j}-\lambda)^{-1},
 \qquad
 \|B_j(D_j-\lambda I)^{-1}B_j^*\|_2
 \le\beta_j^2/(\delta_{Q,j}-\lambda).
 \tag{VTB2}
$$

Use

$$
 \Phi_j(\lambda)=\alpha_j-\lambda-
 \frac{\beta_j^2}{\delta_{Q,j}-\lambda}
 \tag{VTB3}
$$

and, when $\Phi_j(0)>0$,

$$
 \gamma_{j,\rm Fesh}=\frac{\alpha_j+\delta_{Q,j}-
 \sqrt{(\alpha_j-\delta_{Q,j})^2+4\beta_j^2}}2.
 \tag{VTB4}
$$

Require a positive direct Schur matrix at the test energy and a measured gap
at least (VTB4) within $10^{-10}$ absolute tolerance. Record the tail-floor
domain as undefined when the smallest discarded eigenvalue is the floor.

## 3. Statistic and decision tree

The primary statistic is the $44$-row inventory of source and projected ranks,
$\alpha_j$, $\delta_{Q,j}$, $\beta_j$, resolvent and self-energy norms,
positive-root count, root-to-gap ratios, $\beta_j^2/(\alpha_j\delta_{Q,j})$
and the per-plaquette minima/maxima of $\gamma_{j,\rm Fesh}$ and $\beta_j$.

Any source, name, rank, finite-matrix, residual, inequality, Schur, root,
domain or summary failure is `INCONCLUSIVE`. If all controls pass and all
$44$ rows have a positive (VTB4) root, classify
`SUPPORTS_FINITE_TRANSLATED_BLOCK_SWEEP`. If controls pass but one or more
roots are absent, classify `NO_POSITIVE_TRANSLATED_BLOCK_SWEEP`.

No ordinal, coupling, tolerance, source vector or matrix is added after
inspection. The independent checker reconstructs the scalar bounds, roots,
ranks, fixed 44-row schedule, per-plaquette summaries and source bindings
without assembling the graph matrix.

A positive sweep establishes only one finite-volume, finite-cutoff translation
and orientation result. It does not establish uniformity in spatial volume or
lattice spacing, transfer to larger blocks, continuum recovery or the
Yang–Mills mass gap.

## 4. Evidence boundary and receipt

Write the primary receipt once to
`runs/yang_mills_volume_translated_block_feshbach/verification.json` and the
independent receipt once to
`runs/yang_mills_volume_translated_block_feshbach/verification-independent.json`.
Refuse to overwrite either receipt. Bind both receipts to this protocol, the
primary and independent sources, the anchored block-local protocol, sources
and receipts, the adapted-family source and receipts, the constant-sector
volume-bridge source, the exact seven-link source, the large-volume source,
both large-volume protocols and the recovered large-volume receipt.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.39—the anchored block-local finite-family boundary.
- `computations/yang-mills-volume-block-local-feshbach-prereg.md`—the one-plaquette anchored family.
- `computations/verify_yang_mills_volume_feshbach_bridge.py`—exact finite-volume matrix helpers.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—open $3\times2\times2$ source and frozen plaquette ordering.
