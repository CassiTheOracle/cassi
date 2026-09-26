# Yang–Mills Repeated-Edge Closed-Wilson Coverage Screen

## Status: Frozen protocol—September 2026

## Scope

This protocol measures a declared finite extension of the closed-Wilson operator
family on the recovered open $3\times2\times2$ graph. The gauge-invariant basis
is the complete 868-state $C=1$ spin-network basis supplied by
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. The measured
sector is the centered $Q$ space of dimension $867$ at the four fixed couplings
used by the retained degree-four and simple-cycle screens.

The operator family contains every canonical cyclically reduced fundamental
Wilson trace of lengths $4$, $6$ and $8$, together with every simple cycle of
lengths $10$ and $12$. The degree-four ordered plaquette-product family is added
with its fixed source order. A rank result is evidence for this finite graph,
character cutoff, coupling schedule and declared word family. The continuum
construction, volume-uniform estimates, all closed-word local density and the
Yang–Mills mass gap remain separate analytical obligations.

## 1. Canonical word inventory

Use the fixed link graph and orientations in
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. Enumerate from
every graph vertex and every outgoing directed link by deterministic depth-first
search.

A reduced walk cannot contain adjacent inverse factors. At closure, its final
factor also cannot be the inverse of its first factor; this makes the cyclic word
reduced. Retain closed reduced walks of lengths $4$, $6$ and $8$. Canonicalize
each retained word by taking the lexicographically smallest tuple of
$(\text{edge},\text{orientation})$ pairs over all cyclic rotations of the word
and of its orientation-reversed word.

The fixed inventory controls are:

| length | rooted directed occurrences | canonical classes |
|---:|---:|---:|
| $4$ | $88$ | $11$ |
| $6$ | $432$ | $36$ |
| $8$ | $1944$ | $127$ |

The length-eight inventory contains $72$ simple-cycle classes and $55$ classes
with repeated edges or repeated vertices. The repeated-edge extension has $792$
rooted directed occurrences and $55$ canonical classes. The retained simple
cycles of lengths $10$ and $12$ contribute $84$ and $22$ canonical classes,
with $1680$ and $528$ rooted directed occurrences.

The declared Wilson family therefore has $280$ canonical representatives with
length distribution

$$
(11,36,127,84,22)\quad\text{for lengths }(4,6,8,10,12).
$$

Every representative must close, satisfy cyclic reduction, and have a unique
canonical key. The $225$ simple-cycle representatives are a subset of the
family. Proper powers and other algebraically dependent representatives remain
in the declared inventory; rank is measured on the resulting operator columns.

A word containing an adjacent inverse pair is represented by its exact shortened
word and is excluded from this inventory. The minimum closed length on the
bipartite graph is four.

## 2. Augmented finite family

For each scheduled coupling

$$
 x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\},
$$

solve the normalized finite Hamiltonian for its normalized ground vector
$\Omega_x$ and set $Q_x=I-\Omega_x\Omega_x^*$. Construct the normalized
multiplication matrix $M_{x,w}$ for each of the $280$ canonical Wilson words
$w$.

The projected columns are the union of:

1. the $280$ centered Wilson vectors
   $Q_xM_{x,w}\Omega_x$;
2. every ordered plaquette product through degree four, including degrees one
   through four and the $11^d$ source-order words at each degree.

The vacuum degree-zero column is omitted because its projection is zero. The
fixed plaquette block counts are $(11,121,1331,14641)$, so the projected matrix
shape is

$$
(868,\;280+11+121+1331+14641)=(868,16384).
$$

Duplicate columns remain in the matrix. Rank and singular values are the
measured invariants.

## 3. Exact repeated-edge operator construction

For each word, assemble its multiplication matrix by exact $SU(2)$ link Haar
contraction in the complete spin-network basis. The network must create one
fundamental loop factor for every word occurrence, including repeated uses of a
link. At each active link, the Haar integral must retain all bra, ket and loop
factors. At each active vertex, the contraction must retain every distinct active
link and every compatible spectator intertwiner channel.

The repeated-edge assembler must support active vertices with two or three
distinct incident links and active links with multiple loop factors. It must not
reuse the four-factor plaquette contraction or the simple-cycle candidate-target
shortcut. A matrix assembled from a word and its orientation reversal must agree
with the corresponding trace identity, and every retained multiplication matrix
must be finite and Hermitian within the fixed matrix tolerance.

The primary controls must include:

- independent raw and canonical inventory counts;
- closure, cyclic-reduction and canonical-key uniqueness for every representative;
- subset identity for the $225$ simple-cycle representatives;
- exact length-four agreement with the retained plaquette assembler;
- direct link-Haar network agreement at fixed state pairs for sampled length-eight
  repeated-edge words;
- finite and Hermitian matrix controls for all $55$ repeated-edge representatives;
- normalized ground-state decomposition at all four couplings;
- projected-column shape $(868,16384)$ and finite values;
- cumulative rank, nullity, singular-value and deficiency arithmetic;
- protocol, primary-source, independent-source and reused-helper SHA-256
  bindings.

The direct network controls use state pairs
$(0,0),(10,17),(100,200),(867,866)$ and a deterministic sample containing
representatives from each repeated-edge orbit class. The full family remains
assembled by the exact primary path; sampling is a control, not a substitute for
full matrix construction.

## 4. Rank and decision rule

Compute singular values of the real projected augmented matrix with rank
threshold $10^{-10}$ relative to its largest singular value. Record the singular
values, rank, nullity, cumulative rank for the Wilson and four plaquette-degree
blocks, the first family block at which rank $867$ is reached when present, and
the finite deficiency $867-rank$.

The primary classification is
`REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE` when every primary check passes
and all four couplings have rank $867$. When the checks pass and at least one
coupling has a positive deficiency, classify the result as
`REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE` and retain every coupling row.
A failed construction or source control is `INCONCLUSIVE`.

The independent receipt reads the primary receipt without importing the primary
implementation. It independently reconstructs the graph walk inventory, raw and
canonical counts, word and plaquette column counts, cumulative ranks, nullities,
finite classification and source bindings. It does not claim a second
Hamiltonian solve or a continuum result.

## 5. Fixed stopping rule

Run the complete fixed schedule once after the protocol and both verifier sources
are settled. Preserve every receipt and its adjacent source manifest. An
implementation repair uses a fresh output path and retains the complete schedule.
Do not extend the word length, tune the rank threshold, remove dependent words,
select couplings, or add a new family in response to the measured rank.

A complete classification establishes the declared $280$-word family plus the
degree-four plaquette products at $C=1$ on this graph and coupling schedule. An
incomplete classification records the remaining finite deficiency and ends the
screen. The all-word local algebra, volume-uniform transfer estimates,
continuum construction and mass gap require separate protocols and proofs.

## 6. Evidence

Run from the CassiTheory root:

```bash
python computations/verify_yang_mills_closed_wilson_repeated_edge_coverage.py \
  --output runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json
python computations/verify_yang_mills_closed_wilson_repeated_edge_coverage_independent.py \
  --primary runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json \
  --output runs/yang_mills_closed_wilson_repeated_edge_coverage/verification-independent.json
```

Primary receipt:

`runs/yang_mills_closed_wilson_repeated_edge_coverage/verification.json`

Arithmetic-audit receipt:

`runs/yang_mills_closed_wilson_repeated_edge_coverage/verification-independent.json`

Generated receipts and frozen source snapshots remain local under `runs/` and
are indexed through `BROKEN_REFS.md` when the finite result is published.

## References

- `computations/yang-mills-closed-wilson-simple-cycle-coverage-prereg.md`—finite simple-cycle inventory and degree-four augmentation.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—fixed graph, $C=1$ basis and exact link-Haar primitives.
- `computations/yang-mills-plaquette-cyclic-coverage-prereg-v4.md`—ordered degree-four plaquette-product schedule.
- `foundations/loop-to-bubble-projection-theorem.md` §9.43—finite closed-Wilson coverage boundary.
