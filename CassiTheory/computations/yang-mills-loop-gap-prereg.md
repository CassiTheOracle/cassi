# Pure Yang–Mills Loop Closure: Fixed Analytical and Spectral Controls

## Status: Pre-registered—September 2026

## Abstract

This investigation tests a precise connection between strand closure and quantum excitation energy inside regulated pure $SU(2)$ Yang–Mills theory. It establishes the gauge-invariant electric-flux threshold, checks information lost by the projective bubble map, and resolves the interacting single-square control in two independent spectral representations. The quantum state, Haar measure, Gauss law and Hamiltonian are supplied by lattice gauge theory. Identification with the canonical Cassi carrier dynamics remains open. No four-dimensional continuum construction or mass-gap claim is an acceptance outcome.

## 1. Target and normalization

Use continuous time and a three-dimensional cubic spatial lattice, normalized link Haar measure, Hermitian generators $T^a=\sigma^a/2$, and dimensionless link Casimir $E_l^2$ with eigenvalues $j_l(j_l+1)$. Fix the explicit convention of Bauer et al., Eqs. (55)–(56):

$$
H=\frac{g^2}{2a}\sum_lE_l^2+
\frac{1}{2g^2a}\sum_p\operatorname{Tr}(2I-U_p-U_p^\dagger).
$$

Each unoriented elementary spatial square appears once; $g>0$, $a>0$. There are no external charges, matter fields, Higgs fields, damping terms or fitted coefficients. Impose Gauss invariance at every vertex, including boundary vertices. The analytical electric theorem concerns finite open cubic boxes with at least two sites in each direction. Its extension to periodic boxes requires graph girth four; short periodic cycles are excluded from that statement.

## 2. Fixed analytical targets

1. For paths with the same endpoints and holonomies $U_+,U_-$, derive the conjugation law of $W=U_+U_-^\dagger$ and gauge invariance of $\operatorname{Tr}W$.
2. Verify the exact group coordinate
   $$
   U(z)=\begin{pmatrix}z_Y&-z_I^*\\z_I&z_Y^*\end{pmatrix},
   \qquad |z_Y|^2+|z_I|^2=1.
   $$
   For $z=(e^{i\eta},0)$ at $\eta=0,\pi/2,\pi$, record $zz^\dagger$, trace and magnetic energy at $g=a=1$. Determine whether the Hamiltonian preserves the subspace of functions depending only on $zz^\dagger$. This tests autonomous projective closure; integration over discarded variables remains a distinct possible effective construction.
3. Prove using spin-network completeness and vertex singlets that the pure-electric operator has unique constant vacuum and exact excitation gap $3g^2/(2a)$ on the stated cubic graphs, independent of their size. Treat branching and integer representations; no assertion that every network is an unbranched loop is permitted.
4. For the full Hamiltonian, compute the action of the magnetic term on the electric vacuum. Explain why positivity of the magnetic term alone does not bound the excitation gap relative to the interacting vacuum. Derive the extensive second-order electric-vacuum energy shift in the scaled operator $K+2xN_p-x\sum_p\chi_{1/2}(U_p)$, with $K=\sum_lE_l^2$ and $x=2/g^4$.
5. For one isolated open square, derive the exact physical class-function reduction, its Dirichlet radial domain and the character-basis operator. Derive the scaled gap expansion $3+7x^2/15+O(x^4)$ and the weak-coupling oscillator limit. Neither asymptotic calculation supplies a many-plaquette result.

## 3. Fixed finite graph controls

Enumerate every edge labeling $2j\in\{0,1,2\}$ on: one square; two adjacent coplanar squares sharing one edge; the twelve-edge elementary cube. Each fixture has only degree-two or degree-three vertices. A bivalent singlet requires equal incident spins. A trivalent singlet requires the triangle inequalities and integer total spin. Record admissible counts, the complete electric-energy histogram, and the smallest positive eigenvalue in units $g^2/(2a)$. The finite enumeration checks representation and boundary accounting. The untruncated graph theorem requires the analytical argument in §2.

## 4. Fixed spectral schedule

Set $a=1$ and use exactly

$$
g\in\{1/8,1/4,1/2,1,2,4\},\qquad N\in\{32,64,128\}.
$$

Here $N$ retains the characters $\chi_{n/2}$ for $n=0,\ldots,N-1$. In normalized Haar measure they are orthonormal, and the square matrix is

$$
H_{nm}=\left[\frac{g^2}{2}n(n+2)+\frac{2}{g^2}\right]\delta_{nm}
-\frac{1}{g^2}(\delta_{n,m+1}+\delta_{n,m-1}).
$$

Record the lowest three energies, first excitation gap and both adjacent-cutoff discrepancies for all six couplings. Require normalized discrepancy $|v-w|/\max(1,|v|,|w|)<10^{-8}$ between $N=64$ and $N=128$. The $N=32$ rows are a resolution diagnostic with no acceptance threshold.

Independently reconstruct the first eight basis matrix elements from the Dirichlet quadratic form on $0<\theta<\pi$, using $u_n=\sin((n+1)\theta)$ and midpoint grids of 96 and 192 points. At every fixed coupling compare the Gram matrix and Hamiltonian matrix to the character representation with normalized discrepancy below $10^{-10}$.

A separate implementation derives and evaluates the Mathieu characteristic-value representation for the lowest three physical states:

$$
E_r=\frac{g^2}{8}\left[b_{2(r+1)}(-8/g^4)-4\right]+\frac{2}{g^2},
\qquad r=0,1,2.
$$

Compare all three energies and the first gap to the $N=128$ character calculation with normalized discrepancy below $10^{-8}$. The independent implementation must not import the primary verifier or use its tridiagonal matrix. It checks receipt completeness and source bindings before scientific classification. Numerical agreement is a finite-square control, not a proof of spectral truncation bounds on the full lattice.

## 5. Qualification and stopping rule

- Algebraic failure, missing or duplicate rows, nonfinite data, source-binding failure, or a discrepancy at or above its threshold makes the affected result **INCONCLUSIVE** and blocks adoption.
- Qualified group and electric controls receive **SUPPORTS** for the specified finite-regulator loop identities, subject to independent analytical review.
- Equal projectors with distinct Wilson energy receive **CONTRADICTS** for an exact autonomous Hamiltonian closure using only that projective variable. This does not exclude an exact effective marginal with additional nonlocal or memory structure.
- Qualified interacting square spectra receive **SUPPORTS** for the exact finite-square reduction only.
- The interacting infinite-volume gap, four-dimensional continuum construction, Cassi microscopic identification and extension to every compact simple gauge group remain **UNRESOLVED**.

Run the fixed schedule once after both implementations settle. Retain every failed receipt. An implementation defect may be repaired without changing this schedule and rerun to a fresh path; no new couplings, cutoffs, fixtures, fitting, adaptive sweep or four-dimensional simulation is allowed. Stop after independent analytical and numerical reconciliation.

## 6. Evidence

Run from CassiTheory:

```
python computations/verify_yang_mills_loop_gap.py --output runs/yang_mills_loop_gap/primary.json
python computations/verify_yang_mills_loop_gap_independent.py --input runs/yang_mills_loop_gap/primary.json --output runs/yang_mills_loop_gap/independent.json
```

Use immutable fresh outputs. The primary receipt retains all checks, graph histograms, matrix comparisons and spectral rows. Its adjacent input manifest and source directory freeze the protocol and both implementations with SHA-256 identities; reject source mutation during execution. The independent receipt preserves its own values, row-wise comparisons and the hash of the consumed primary receipt. Generated receipts remain local and are indexed in `BROKEN_REFS.md`.

## References

- J. Kogut and L. Susskind, [Hamiltonian formulation of Wilson's lattice gauge theories](https://doi.org/10.1103/PhysRevD.11.395)—established Hamiltonian framework.
- C. W. Bauer, I. D'Andrea, M. Freytsis and D. M. Grabowska, [A new basis for Hamiltonian SU(2) simulations](https://arxiv.org/abs/2307.11829), §§II–IV and Appendix B—explicit normalization, gauge reduction and physical Mathieu spectrum.
- A. Jaffe and E. Witten, [Quantum Yang–Mills Theory](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), §4—continuum existence and mass-gap obligations.
- `foundations/loop-to-bubble-projection-theorem.md` §9—carrier projection and quantum-identification boundary.
