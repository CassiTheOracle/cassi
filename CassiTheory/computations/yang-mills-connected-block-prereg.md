# Pure Yang–Mills Connected Blocks and the Strong-Coupling Gap

## Status: Pre-registered—September 2026

## Abstract

This investigation checks a volume-uniform strong-coupling gap inside the supplied quantum $SU(2)$ lattice theory and constructs a local unitary step that removes first-order electric-vacuum loop creation. Full link holonomies are retained. The gap argument uses an established stability theorem for finite-range perturbations of a product vacuum; the unitary step separates a relatively bounded interaction from a quadratic remainder. The numerical controls test exact local identities and periodic geometry. They do not determine a continuum mass, a numerical strong-coupling threshold, or a microscopic Cassi identification.

## 1. Hamiltonian and theorem convention

Use the Hamiltonian and normalized Haar measure in `computations/yang-mills-loop-gap-prereg.md`. Work on periodic three-dimensional cubic lattices with even side length at least four and Gauss invariance at every vertex. Write

$$
h=\frac{2a}{g^2}H=K+2xN_p-x\sum_p\chi_{1/2}(U_p),\qquad
x=2/g^4,\qquad K=\sum_l E_l^2.
$$

Each site groups its three positively oriented outgoing link Hilbert spaces, $\mathcal H_{\mathbf r}=L^2(SU(2)^3)$. Let $K_{\mathbf r}$ sum their Casimirs. Its unique constant vacuum has excitation threshold $3/4$. Fix the interaction support

$$
\mathcal S=\{0,e_1,e_2,e_3\},\qquad
h^0_{\mathbf r}=\frac43\sum_{\mathbf y\in\mathbf r+\mathcal S}K_{\mathbf y},\qquad
v_{\mathbf r}=-\frac{16x}{3}\sum_{i<j}\chi_{1/2}(U_{\mathbf r,ij}).
$$

Check that the local classical gap is one, that each site appears in four supports, and that

$$
\sum_{\mathbf r}(h^0_{\mathbf r}+v_{\mathbf r})
=\frac{16}{3}(h-2xN_p),\qquad
\|v_{\mathbf r}\|\le32|x|=64/g^4.
$$

Independently audit all hypotheses of Yarotsky, arXiv:math-ph/0412040, Theorem 1: infinite-dimensional site Hilbert spaces, diagonal local partition, common finite interaction support, periodic boundaries, and volume-independent small local perturbations. Trace the physical gap normalization and the gauge restriction. The theorem's smallness constant and gap constant remain symbolic; no finite-control coupling is declared to satisfy an unevaluated theorem threshold.

## 2. Exact local unitary target

On the four links of a square let $|0_p\rangle$ be their constant vacuum and $|p\rangle=\chi_{1/2}(U_p)|0_p\rangle$, with unit norm and electric energy three. Define

$$
P_p=|0_p\rangle\langle0_p|,\quad Q_p=I-P_p,\quad
A_p=|p\rangle\langle0_p|-|0_p\rangle\langle p|,\quad
S_p=-A_p/3,
$$
$$
T_p=|p\rangle\langle0_p|+|0_p\rangle\langle p|,\qquad
W_p=Q_p\chi_{1/2}(U_p)Q_p.
$$

Derive $[S_p,K]=T_p$, $\chi_{1/2}(U_p)=T_p+W_p$, and invariance under vertex gauge transformations. Bound the local vacuum-complement projector by the electric energy. Each link belongs to four plaquettes, giving the candidate global form bound

$$
\left|x\sum_{p\in\mathcal I}\langle\psi,W_p\psi\rangle\right|
\le\frac{32|x|}{3}\langle\psi,K\psi\rangle
$$

for every subset $\mathcal I$ of plaquettes. This estimate must use the local unreduced threshold $3/4$, including when the global state is gauge invariant.

Color a plaquette by its coordinate plane and the three parities of its anchor. The 24 colors form disjoint-link layers on the declared even tori. Order planes lexicographically, then anchor parity lexicographically. Apply the corresponding layers of $\exp(xS_p)$ in that fixed order. Establish whether their product $D(x)$ is an exact gauge-invariant finite-depth unitary satisfying

$$
D(x)(h-2xN_p)D(x)^\dagger
=K-x\sum_pW_p+R(x),
$$

where $R(x)$ has finite interaction range and bounded local terms of order $x^2$ with volume-independent constants. Treat the unbounded electric operator through bounded commutators, not a global bound on $\|K\|$. Any application of Yarotsky Theorem 2 must handle the circuit's two-site translation period by grouping $2\times2\times2$ cells and must retain the exact remainder. A truncated transformed Hamiltonian is outside the claim.

## 3. Fixed finite controls

### Periodic geometry

Use exactly $L\in\{4,6,8\}$. Enumerate sites, positive links, unoriented plaquettes and the four-site supports. Record the counts, every link's plaquette incidence, every site's support multiplicity and the sizes of all 24 color classes. Require no repeated link within a color class and containment of each anchored plaquette's link groups in its declared support. These finite controls accompany the all-even-size analytical argument.

### Local operator identities

In the normalized square-character basis $|n\rangle=\chi_{n/2}$, use $K_{nn}=n(n+2)$ and $V_{n,n+1}=V_{n+1,n}=1$. The generator $S$ acts only on $|0\rangle,|1\rangle$. Derive the support of the commutators and the exact remainder before numerical evaluation. Use basis sizes $N\in\{3,5,8\}$ and exactly

$$
x\in\{-1/4,-1/8,-1/16,0,1/16,1/8,1/4\}.
$$

Compare a numerical matrix exponential to the independently derived sine/cosine rotation. Require maximum absolute discrepancy below $10^{-11}$ for the unitary, transformed operator, first-order cancellation and zero matrix tail outside the analytically derived three-character remainder support. Require invariant spectra under exact unitary conjugation at the same tolerance. Negative $x$ values are algebraic controls, with no physical bare-coupling identification.

Compute exact symbolic commutators and their operator norms. The single-square remainder bound must follow from those norms and the integral remainder formula, with no fitted coefficient. Check that bound at all fixed nonzero $x$, allowing numerical slack $10^{-11}$. Record the leading vacuum energy and vacuum-to-second-character coefficients; compare the transformed vacuum expectation to the original expectation in the rotated state. Matrix truncations test the finite-rank identities and supply no many-plaquette spectral estimate.

## 4. Qualification and stopping

- Missing/duplicate rows, nonfinite numerical data, source mutation, or a discrepancy at or above tolerance gives **INCONCLUSIVE** for the affected control and blocks adoption of its numerical support.
- Qualified exact geometry and operator identities receive **SUPPORTS** for the stated regulated construction, subject to independent analytical review.
- A complete verified hypothesis map to Yarotsky's theorem permits **ADOPT** for the sufficiently-strong-coupling, volume-uniform gap. A failed hypothesis map gives **INCONCLUSIVE**; no theorem constant may be invented.
- A complete verified finite-depth/unitarity/remainder argument permits **ADOPT** for the exact first-order vacuum-dressing step. Its numerical controls cannot establish the infinite-volume assertion by themselves.
- The weak-bare-coupling scaling trajectory, nontrivial continuum quantum-field construction, continuum mass and Cassi microscopic identification remain **UNRESOLVED**.

Run once after source and independent analytical reviews settle. Preserve failed receipts. Implementation repairs retain the full schedule and use fresh output paths. No parameter scan, fitted remainder coefficient, four-dimensional simulation, representation-based many-plaquette spectrum, or change to the first loop-gap campaign is allowed. Stop after the two analytical targets and fixed controls are reconciled.

## 5. Evidence

Run from CassiTheory:

```
python computations/verify_yang_mills_connected_blocks.py --output runs/yang_mills_connected_blocks/verification.json
```

The program freezes this protocol, its own raw source bytes and the reused check-record helper source in an adjacent manifest and source directory, checks source stability during execution, and writes a fresh immutable receipt with every fixed row, symbolic expression, comparison and source identity. The director independently inspects the receipt and the external theorem statements before scientific classification. Raw analytical reviews and the final reconciliation accompany the receipt. Generated evidence remains local and is indexed in `BROKEN_REFS.md`.

## References

- D. A. Yarotsky, [Ground states in relatively bounded quantum perturbations of classical lattice systems](https://arxiv.org/abs/math-ph/0412040), Theorems 1–2 and Eqs. (1)–(6)—local hypotheses, thermodynamic limit and gap stability.
- `foundations/loop-to-bubble-projection-theorem.md` §§9.4–9.9—Hamiltonian, full-holonomy requirement, electric gap and vacuum subtraction.
- `computations/yang-mills-loop-gap-prereg.md`—retained first-campaign normalization and scope.
