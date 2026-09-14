# Yang–Mills Closed-Wilson Simple-Cycle Coverage Screen

## Status: Frozen protocol—September 2026

## Scope

This protocol measures whether the complete unoriented simple-cycle family of
the recovered open $3\times2\times2$ graph closes the finite centered $Q$
sector when added to the degree-four plaquette-product family. It is a finite
operator-coverage screen at doubled character cutoff $C=1$. A complete rank
would establish the declared finite simple-cycle family at the four fixed
couplings only. It would not establish completeness of all closed walks, an
RG image, a volume-uniform estimate, a continuum limit or a Yang–Mills mass
gap.

The graph has twelve vertices and twenty links. The gauge-invariant basis is
the complete 868-state $C=1$ basis supplied by
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`. The selected
larger-volume receipt remains the qualified finite construction with four
unresolved tail-separation qualifications. Those qualifications are retained
in every receipt.

## 1. Canonical simple-cycle inventory

Enumerate directed walks by deterministic depth-first search from every graph
vertex. A walk is retained when it has length at least four, returns to its
starting vertex, and has no repeated vertex before that return. The search is
bounded by the twelve graph vertices, so the possible simple-cycle lengths on
this bipartite graph are $4,6,8,10,12$.

The raw directed enumeration must contain exactly $3880$ rooted oriented
occurrences. Quotient each occurrence by every cyclic rotation and by reversal
with orientation signs negated. The lexicographically smallest tuple of
$(\text{edge},\text{orientation})$ pairs is the canonical representative. The
unoriented canonical inventory must contain exactly $225$ classes with this
length distribution:

| length | canonical classes |
|---:|---:|
| $4$ | $11$ |
| $6$ | $36$ |
| $8$ | $72$ |
| $10$ | $84$ |
| $12$ | $22$ |

Each representative must close, contain distinct active edges and visit each
active vertex as a simple cycle. Cyclic rotation leaves a Wilson trace
unchanged. For the fundamental $SU(2)$ character, reversal also leaves the
trace unchanged because $\chi_{1/2}(U^{-1})=\chi_{1/2}(U)$. The canonical inventory
therefore supplies one real multiplication operator per class. This finite
simple-cycle inventory is not the set of all closed Wilson words.

## 2. Augmented finite family

For each scheduled coupling

$$
 x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\},
$$

solve the normalized finite Hamiltonian for its normalized ground vector
$\Omega_x$ and let $Q_x=I-\Omega_x\Omega_x^*$. Construct the normalized
multiplication matrix $M_{x,c}$ for every one of the $225$ canonical simple
cycles $c$.

The measured columns are the union of:

1. the $225$ centered simple-cycle vectors
   $Q_xM_{x,c}\Omega_x$;
2. every ordered plaquette product through degree four, including degrees
   one through four and the $11^d$ source-order words at each degree.

The vacuum degree-zero column is omitted because it projects exactly to zero.
The total declared projected-column count is therefore

$$
225+11+121+1331+14641=16329.
$$

The plaquette products retain the source order and multiplication order from
the degree-four screen. Duplicate columns are retained; rank is the invariant
being measured.

## 3. Exact variable-length operator construction

For each simple cycle, assemble its finite multiplication matrix by exact
$SU(2)$ link Haar contraction in the complete spin-network basis. The
variable-length transfer contraction must use one transfer factor per cycle
edge and a dynamically generated cyclic Einstein summation. It must not use
the four-factor plaquette contraction or its four-sign candidate shortcut.
At $C=1$, each distinct active edge has the unique admissible spin change
that remains in $\{0,1\}$; the candidate target construction must retain all
compatible spectator intertwiner channels.

The primary controls must include:

- the $3880$ raw occurrence count, the $225$ canonical count and the five
  length counts above;
- closure, distinct-active-edge and simple-vertex checks for every class;
- exact length-four agreement between the variable-length assembler and the
  existing plaquette assembler for all eleven source plaquettes;
- a fixed sampled length-eight agreement with a direct link-Haar network
  contraction at state pairs $(0,0),(10,17),(100,200),(867,866)$;
- finite, Hermitian simple-cycle matrices and normalized ground-state
  decompositions at all four couplings;
- projected-column shape $(868,16329)$ and finite values;
- cumulative rank arithmetic and source/protocol hash bindings.

## 4. Rank and decision rule

Compute singular values of the real projected augmented matrix with rank
threshold $10^{-10}$ relative to its largest singular value. Record the
singular values, rank, nullity, cumulative rank for the simple-cycle and each
plaquette-degree block, and the first family block at which rank $867$ is
reached if present. Record the finite deficiency $867-rank$.

The primary receipt has exactly $40$ checks: sixteen global inventory,
assembler, source and schedule checks, plus six row checks at each coupling:
finite ground/Q decomposition, simple-cycle matrix controls, degree-four
plaquette schedule, augmented-column shape, singular-value/nullity
consistency and full-$Q$ boundary.

The screen has classification
`CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE` only when all primary checks
pass and every coupling has augmented rank $867$. Otherwise, when the checks
pass, use `CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE` and report the
finite deficiencies. A negative result has no asymptotic inference.

The independent receipt has exactly $24$ arithmetic-audit checks. It reads the
primary receipt without importing the primary implementation, reconstructs the
inventory counts, column counts, singular-value ranks, nullities and finite
classification, and does not claim a second Hamiltonian solve.

Primary receipt:

`runs/yang_mills_closed_wilson_simple_cycle_coverage/verification.json`

Arithmetic-audit receipt:

`runs/yang_mills_closed_wilson_simple_cycle_coverage/verification-independent.json`

## 5. Boundary

This screen tests a complete finite simple-cycle inventory plus the declared
finite plaquette-product family. It does not test self-intersecting or
repeated-edge single-trace words beyond those represented by the retained
plaquette products. The all-word local density result, uniform transfer
constants, lattice-spacing control, continuum construction and mass gap remain
separate obligations.
