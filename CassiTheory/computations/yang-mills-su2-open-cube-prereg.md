# Finite Open-Cube SU(2) Gauge-Basis and Wilson-Sparsity Pilot

## Status: Pre-registered—September 2026

## Abstract

This protocol defines a bounded exact representation-theoretic pilot for the
pure SU(2) Kogut–Susskind Hamiltonian on one open $2\times2\times2$ cube.
The calculation enumerates gauge-invariant trivalent spin-network labels at
two doubled-spin cutoffs and evaluates the fundamental Wilson plaquette
matrix elements using Clebsch–Gordan products and Haar integration. The six
plaquette words are oriented cyclically before any noncommutative matrix
mapping is applied.

The pilot measures the finite-regulator kinematic basis and the support of the
oriented plaquette operator. It does not establish character-cutoff removal,
spatial-volume growth, a thermodynamic limit, an Osterwalder–Schrader
reconstruction, or a continuum Yang–Mills mass gap.

## 1. Question and scope

Can the first nontrivial three-dimensional gauge-invariant basis and the
fundamental Wilson operator be constructed exactly on a bounded open cube,
with the signed cyclic plaquette words retained in the matrix calculation?

The graph has vertices
\[
v=(x,y,z)\in\{0,1\}^3
\]
and twelve links, each canonically oriented in the positive coordinate
direction. The link IDs are
\[
\begin{array}{c|cccccccccccc}
e&0&1&2&3&4&5&6&7&8&9&10&11\\\hline
\text{tail}&000&000&000&100&100&010&010&110&001&001&101&011\\
\text{head}&100&010&001&110&101&110&011&111&101&011&111&111.
\end{array}
\]

The frozen plaquette words, written as `(link, sign)` with sign $+1$ for the
canonical link and $-1$ for its inverse, are
\[
\begin{aligned}
P_{xy,0}&=(0^+,3^+,5^-,1^-),&P_{xy,1}&=(8^+,10^+,11^-,9^-),\\
P_{zx,0}&=(2^+,8^+,4^-,0^-),&P_{zx,1}&=(6^+,11^+,7^-,5^-),\\
P_{yz,0}&=(1^+,6^+,9^-,2^-),&P_{yz,1}&=(3^+,7^+,10^-,4^-).
\end{aligned}
\]
Each word must close by an endpoint walk. The signs are part of the operator
and must not be replaced by an unsigned incidence set.

## 2. Gauge-invariant basis

For doubled cutoff $C\in\{1,2\}$, assign an edge label
$n_e\in\{0,1,\ldots,C\}$, corresponding to spin $j_e=n_e/2$. At every
trivalent vertex, the three incident labels must obey
\[
n_a+n_b+n_c\equiv0\pmod 2,
\qquad |n_a-n_b|\le n_c\le n_a+n_b.
\]
The basis contains one fixed trivalent intertwiner whenever these rules hold
and no state otherwise. The implementation uses the raw real Wigner $3j$
tensors in a deterministic incident-edge order and the SU(2) invariant metric
on incoming link indices. The resulting spin-network functions are
unnormalized; this convention changes matrix magnitudes but not the
selection-rule support being measured.

The frozen basis dimensions are
\[
\dim\mathcal H_{C=1}=32,
\qquad
\dim\mathcal H_{C=2}=1013.
\]
These dimensions are gauge-invariant label counts, not a claim about an
infinite-volume Hilbert space.

## 3. Oriented Wilson operator

For each frozen word $P$, define the fundamental Wilson multiplication
operator
\[
W_P(U)=\chi_{1/2}\!\left(U_{e_1}^{s_1}U_{e_2}^{s_2}
U_{e_3}^{s_3}U_{e_4}^{s_4}\right).
\]
The matrix element between unnormalized spin-network functions is evaluated
by multiplying the link representation matrices with the fundamental factors,
recoupling each link with the SU(2) Clebsch–Gordan series, and integrating all
links by Haar orthogonality. No Monte Carlo samples or Cartesian group grids
are used.

The selection rule for a possible matrix entry is that each of the four word
links changes by exactly one doubled-spin unit and all spectator labels remain
unchanged; the target labels must remain gauge-admissible. The frozen
structural support counts are:

| doubled cutoff | basis dimension | candidate entries per plaquette | all six candidate entries |
|---:|---:|---:|---:|
| $C=1$ | 32 | 32 | 192 |
| $C=2$ | 1013 | 2388 | 14328 |

These are directed matrix-entry counts before numerical evaluation. The
calculation records the exact nonzero count separately, so cancellations are
visible rather than folded into the selection rule.

## 4. Frozen checks and decision rule

For each cutoff and each of the six oriented plaquettes, the receipt must
record:

1. endpoint closure of all six cyclic words;
2. the frozen basis dimension;
3. the frozen candidate-entry count;
4. finite matrix entries for every candidate and no omitted candidate;
5. the maximum Hermiticity residual for $W_P-W_P^\dagger$;
6. the number of entries with $|M_{ts}|>10^{-12}$ and the smallest retained magnitude;
7. a deterministic forbidden-pair zero control;
8. agreement of the oriented word and its reversed/dagger support.

The forbidden-pair control evaluates the lexicographically first
$\min(128,N^2-N_{\mathrm{candidate}})$ state pairs that are not in the
selection-rule candidate set. It requires every sampled matrix element to
have magnitude at most $10^{-12}$. The full forbidden count is retained as a
structural number, but it does not satisfy the zero control by itself. The
selection rule supplies the analytic reason that the remaining forbidden
pairs vanish.

The dagger control evaluates the lexicographically first
$\min(64,N_{\mathrm{candidate}})$ candidate pairs with the reversed
fundamental word and requires agreement with the forward matrix element to
the matrix tolerance. The support comparison covers every candidate pair.

The pilot is `PASS` for the declared finite construction when all graph,
basis, selection-rule, matrix-finiteness, Hermiticity, dagger-support, and
forbidden-sample checks pass. The result is classified
`SUPPORTS_FINITE_OPEN_CUBE_OPERATOR` if every structurally allowed entry is
numerically nonzero at the frozen threshold. If structurally allowed entries
vanish, the finite construction can still pass, but the operator
classification is `CANCELLATION_PRESENT` and the receipt must list those
entries. Any graph, basis, or forbidden-support failure is `FAIL`.

The fixed threshold $10^{-12}$ is a reporting threshold only; no entry is
rescaled or fitted. The cutoff schedule, forbidden-pair sample rule, and word
orientation cannot change after execution.

## 5. Implementation and output

The primary implementation is:

`computations/verify_yang_mills_su2_open_cube.py`

The source-bound receipt is:

`runs/yang_mills_su2_open_cube/verification.json`

The receipt binds this protocol, the implementation source, and the exact
representation helper by SHA-256. Existing finite one-plaquette and
finite-volume two-dimensional receipts remain separate evidence; this pilot
adds a bounded three-dimensional gauge-invariant operator layer.

## 6. Boundary after this pilot

A passing pilot supplies the first exact three-dimensional kinematic block and
its oriented plaquette sparsity. The next mathematical boundary is a sequence
of increasing spatial cubes with a controlled character truncation and a
positive vacuum measure, followed by uniform estimates sufficient for a
thermodynamic and continuum Schwinger-function construction. None of those
bounds is inferred from this finite pilot.

## References

- `computations/yang-mills-exact-block-spectral-prereg.md`—finite SU(2) spin-network and Haar-contraction conventions.
- `computations/verify_yang_mills_exact_block_spectrum.py`—shared exact representation helper.
- `computations/yang-mills-su2-schwinger-prereg-v2.md`—finite one-plaquette Schwinger-function bridge.
- `computations/yang-mills-su2-wilson-2d-prereg.md`—finite-volume two-dimensional Wilson bridge.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—continuum target.
