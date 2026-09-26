# Yang–Mills Plaquette-Cyclic Coverage Screen: Degree Four

## Status: Frozen protocol—September 2026

## Scope

This protocol measures the finite centered-sector coverage supplied by ordered
products of the eleven fundamental plaquette characters on the recovered open
$3\times2\times2$ graph at doubled character cutoff $C=1$. The scheduled family
contains every plaquette word of degrees zero through four. It is a finite
operator-algebra coverage screen. A complete rank at these fixed controls would
establish coverage by this finite plaquette family on this finite graph only; it
does not establish coverage by every closed Wilson word, a conditional Poincare
inequality, a volume-uniform bound, a continuum limit or a mass gap.

Use the exact source
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py` and the
qualified source receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/current-verification.json`.
The source receipt has $234/238$ checks with four declared unresolved
tail-separation rows. The selected source binds recovery protocol hash
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`.

## 1. Finite operator family

Use the complete 868-state gauge-invariant basis and the eleven signed
fundamental plaquette words in source order. For each scheduled coupling

$$
 x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\},
$$

solve the normalized finite Hamiltonian for its normalized ground vector
$\Omega_x$. Let $M_{x,p}=S^{-1/2}W_pS^{-1/2}$ be the normalized multiplication
operator for plaquette $p$.

For a word $\alpha=(p_1,\ldots,p_d)$ define

$$
 u_{x,\alpha}=M_{x,p_d}\cdots M_{x,p_1}\Omega_x,
 \qquad
 v_{x,\alpha}=Q_xu_{x,\alpha},
 \qquad
 Q_x=I-\Omega_x\Omega_x^*.
$$

The degree-$d$ word schedule is the complete ordered set of all $11^d$ words.
Run exactly $d=0,1,2,3,4$ and retain every word count and source-order
index. The measured sector is

$$
\mathcal K_x^{\mathrm{cyc},4}
:=\operatorname{span}\{v_{x,\alpha}:0\le d\le4\}
\subseteq\operatorname{ran}Q_x.
$$

The degree-zero vector is the vacuum and projects to zero. This finite schedule
is not identified with the full local gauge-invariant algebra: the all-word
density statement and finite retained-family rank are separate claims.

## 2. Frozen rank and stopping rule

For each degree and cumulative schedule, compute the singular values of the
real projected word matrix in the common 868-dimensional Hilbert space. Use
rank tolerance $10^{-10}$ relative to the largest singular value. Record:

- word count $11^d$ for each degree;
- cumulative word count;
- cumulative rank;
- $Q$ dimension $867$;
- singular values and nullity of the cumulative projected matrix;
- the first degree at which rank $867$ is reached, if it occurs.

The schedule stops at degree four regardless of outcome. No degree or
singular-value threshold may be tuned after inspection. The finite degree-four
screen passes only when the cumulative degree-four rank is exactly $867$ for
every scheduled coupling. If rank is smaller, classify the result
`PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE` and report the finite deficiency. A
negative result supplies no asymptotic inference.

## 3. Controls and source binding

Check the common dimension, plaquette order, word counts, ground-state
normalization, vacuum orthogonality, finite singular values, monotone cumulative
rank, singular-value/nullity arithmetic, and source/protocol hashes. Preserve
the four unresolved source-tail names in every receipt. Refuse to overwrite
output receipts.

The primary receipt has exactly 32 checks: eight global source, schedule and
qualification checks, plus six row checks at each of four couplings:
word-count schedule, ground-state/Q decomposition, finite word matrix,
cumulative rank, singular-value/nullity consistency, and finite degree-four
boundary.

The independent receipt has exactly 20 arithmetic-audit checks: eight source,
schedule and primary-receipt checks plus three reconstructions at each coupling:
word-count/rank arithmetic, singular-value/nullity arithmetic, and finite
classification. It audits the serialized primary rank data without importing
the primary implementation or claiming a second Hamiltonian solve.

Primary receipt:

`runs/yang_mills_plaquette_cyclic_coverage/verification-v4.json`

Arithmetic-audit receipt:

`runs/yang_mills_plaquette_cyclic_coverage/verification-independent-v4.json`

## 4. Decision boundary

`PASS` is reserved for the declared finite degree-four coverage claim: all 32
primary checks must pass and every coupling must have cumulative degree-four
rank $867$. A primary classification of
`PLAQUETTE_CYCLIC_COVERAGE_COMPLETE` therefore has `status=PASS`. If the checks
pass but any cumulative rank is smaller than $867$, the primary receipt has
`status=FAIL` and classification `PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE`; the
receipt records `32/32` arithmetic checks and the measured finite deficiencies.

The arithmetic-audit classification is
`PRIMARY_RECEIPT_CYCLIC_RANK_AUDIT_PASS` when its 20 checks pass. That audit
PASS validates the serialized rank result and does not change the primary
coverage classification.

Either classification remains a finite-regulator statement. Complete rank
would not establish all-word completeness, a volume-uniform constant,
lattice-spacing control, a continuum construction or the Yang–Mills mass gap.
