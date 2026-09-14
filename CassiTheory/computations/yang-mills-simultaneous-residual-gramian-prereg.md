# Simultaneous Translated-Block Residual Gramian

## Status: Frozen protocol v2—September 2026

## Abstract

This protocol measures the residual-recovery object on one common finite
SU(2) gauge-invariant Hilbert space. The graph is the recovered open
$3\times2\times2$ graph at doubled character cutoff $C=1$, with its complete
868-state spin-network basis and eleven source-order fundamental plaquettes.
At each fixed coupling, the exact finite Hamiltonian ground vector defines the
centered vacuum complement $Q$. The eleven centered one-plaquette vectors are
then placed in that same $Q$ space. For block $p$, the finite exterior source
space is the span of the other ten centered plaquette vectors; the residual is
the orthogonal complement of that exterior span inside the declared
one-operator source sector.

The calculation assembles all eleven local residual projections
simultaneously, uses equal bounded cover weights, reconstructs their source
coverage matrix, and probes spatially smooth coefficient patterns. It records
the positive floor on the declared source sector and the nullity of the
extension to the full 867-dimensional vacuum complement. The source-sector
floor is a finite measurement of the chosen conditional source space. A full
$Q$-sector recovery floor requires exterior sigma-algebras and residual
projections that cover the complete physical form domain; this protocol does
not supply that extension.

## 1. Frozen finite graph and Hilbert space

Use the exact recovered source and basis from
`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py` and the
current source-bound receipt
`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/current-verification.json`.
The original `verification.json` is excluded because it binds recovery
protocol hash
`8ca8b34e5250b798fdb2e196e68d731a2b14f6c4e2b7a0fcf89e0db29f9264e7`,
while the current recovery protocol and selected source artifact bind
`5647bfa524c25672c83d5daa2e515c33313fdf118c84afd29155e1e1e5cf1821`.
The selected source artifact is qualified finite evidence: it reports
`234/238` checks and four named `TAIL_UNRESOLVED` tail-separation obligations
(`C1/C2` at $x=0.25$ and $x=1$). This protocol carries those qualifications;
it does not treat the source artifact as a clean all-check verification.
The graph has 20 oriented links, 12 vertices, four four-valent intertwiner
sites, eleven signed fundamental plaquette words, and 868 complete
finite-cutoff gauge-invariant basis states. The basis overlap is diagonal,
with

$$
S_{ss}=\nu_s=\prod_{e=0}^{19}(n_e+1)^{-1}.
\tag{SRG1}
$$

For coupling

$$
x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\},
$$

form the normalized finite Hamiltonian

$$
\widehat H_x=S^{-1/2}(K+22xI-xW)S^{-1/2}.
\tag{SRG2}
$$

Let $(E_x,\Omega_x)$ be its normalized lowest eigenpair, with the sign of
$\Omega_x$ fixed by its largest-magnitude component. Define

$$
P_x=\Omega_x\Omega_x^*,
\qquad Q_x=I-P_x,
\qquad
\mathcal H_x^Q=\operatorname{ran}Q_x.
\tag{SRG3}
$$

The null subspace for this finite physical representation is
$\mathcal N_x=\operatorname{ran}P_x$. The compatibility condition is
$R_{x,p}\Omega_x=0$ for every positive-weight block.

## 2. Centered one-operator source sector

For plaquette $p$, let $W_{x,p}=S^{-1/2}W_pS^{-1/2}$ and define

$$
 m_{x,p}=\langle\Omega_x,W_{x,p}\Omega_x\rangle,
 \qquad
 v_{x,p}=(W_{x,p}-m_{x,p}I)\Omega_x.
\tag{SRG4}
$$

Every $v_{x,p}$ lies in $\mathcal H_x^Q$. The common finite source sector is

$$
\mathcal K_x^Q=\operatorname{span}\{v_{x,p}:p=0,\ldots,10\}
\subseteq\mathcal H_x^Q.
\tag{SRG5}
$$

Its source Gramian is

$$
G_x[p,q]=\langle v_{x,p},v_{x,q}\rangle.
\tag{SRG6}
$$

The source-sector construction requires rank eleven at every scheduled
coupling. This is a source-sector condition, not a statement about the full
local gauge-invariant algebra.

## 3. Simultaneous local residual projections

For block $p$, define the finite exterior source space

$$
\mathcal E_{x,p}=\operatorname{span}\{v_{x,q}:q\ne p\}
\subseteq\mathcal K_x^Q.
\tag{SRG7}
$$

Let $\Pi_{x,p}^{\mathrm{ext}}$ be the orthogonal projection onto
$\mathcal E_{x,p}$ in the common Euclidean Hilbert space
$\mathbb R^{868}$. The local residual vector is

$$
 r_{x,p}=(I-\Pi_{x,p}^{\mathrm{ext}})v_{x,p},
 \qquad
 \widehat r_{x,p}=r_{x,p}/\|r_{x,p}\|.
\tag{SRG8}
$$

The declared source-sector residual projection and the simultaneous Gramian
are

$$
R_{x,p}^{\mathrm{src}}=\widehat r_{x,p}\widehat r_{x,p}^*,
\qquad
\mathscr R_x^{\mathrm{src}}
 =\sum_{p=0}^{10}w_pR_{x,p}^{\mathrm{src}}.
\tag{SRG9}
$$

Use equal weights

$$
 w_p=\frac1{11},
 \qquad \sum_pw_p=1,
 \qquad 0<w_p\le\frac1{11}.
\tag{SRG10}
$$

All eleven projections are formed in the same $\mathbb R^{868}$ space before
their sum is diagonalized. The source coverage matrix is

$$
C_x[p,q]=\langle\widehat r_{x,p},\widehat r_{x,q}\rangle.
\tag{SRG11}
$$

For a positive source Gramian, the inverse-Gramian identity gives

$$
C_x[p,q]
 =\frac{(G_x^{-1})_{pq}}
 {\sqrt{(G_x^{-1})_{pp}(G_x^{-1})_{qq}}}.
\tag{SRG12}
$$

The primary computes both sides independently. The independent verifier
reconstructs (SRG12) from the serialized source Gramian.

## 4. Source-sector floor and full-$Q$ boundary

The measured source-sector recovery floor is

$$
\gamma_{x}^{Q,\mathrm{src}}
 =\lambda_{\min}\left(
 \mathscr R_x^{\mathrm{src}}\big|_{\mathcal K_x^Q}
 \right)
 =\lambda_{\min}\left(\frac{C_x}{11}\right),
\qquad
A_{Q,x}^{\mathrm{src}}=1/\gamma_{x}^{Q,\mathrm{src}}.
\tag{SRG13}
$$

The extension of the eleven rank-one residuals by zero on
$(\mathcal K_x^Q)^\perp\cap\mathcal H_x^Q$ has rank eleven. Therefore its
full-$Q$ spectral boundary is recorded explicitly:

$$
\dim\mathcal H_x^Q=867,
\qquad
\operatorname{rank}\mathscr R_x^{Q,\mathrm{src}}=11,
\qquad
\gamma_x^{Q,\mathrm{full}}=0,
\qquad
\dim\ker\mathscr R_x^{Q,\mathrm{src}}=856.
\tag{SRG14}
$$

Equation (SRG14) is a coverage diagnostic. It prevents the positive
source-sector number in (SRG13) from being read as a full physical recovery
floor. A full UF-B floor requires additional local conditional residuals whose
ranges cover the remaining physical directions.

## 5. Long-wavelength probes

Use the frozen plaquette centers, in source order,

$$
\begin{aligned}
&(\tfrac12,\tfrac12,0),(\tfrac32,\tfrac12,0),
 (\tfrac12,\tfrac12,1),(\tfrac32,\tfrac12,1),\\
&(\tfrac12,0,\tfrac12),(\tfrac32,0,\tfrac12),
 (\tfrac12,1,\tfrac12),(\tfrac32,1,\tfrac12),\\
&(0,\tfrac12,\tfrac12),(1,\tfrac12,\tfrac12),(2,\tfrac12,\tfrac12).
\end{aligned}
\tag{SRG15}
$$

For coefficient vectors on these centers, use the four fixed probes

$$
 c^{(0)}_p=1,
\quad
 c^{(x)}_p=\cos\!\left(\frac{\pi(x_p+1/2)}3\right),
\quad
 c^{(y)}_p=\cos\!\left(\frac{\pi(y_p+1/2)}2\right),
\quad
 c^{(z)}_p=\cos\!\left(\frac{\pi(z_p+1/2)}2\right).
\tag{SRG16}
$$

The physical probe is $f=\sum_pc_pv_{x,p}$. Record its source-sector Rayleigh
quotient

$$
\mathcal Q_x(c)=
\frac{\langle f,\mathscr R_x^{\mathrm{src}}f\rangle}
 {\langle f,f\rangle}
$$

and independently evaluate the equivalent coefficient formula

$$
\mathcal Q_x(c)=
\frac{\sum_pw_p c_p^2/(G_x^{-1})_{pp}}
 {c^*G_xc}.
\tag{SRG17}
$$

These probes test whether smooth spatial patterns are represented by the
same simultaneous local family. The finite graph supplies no volume sequence;
no asymptotic conclusion is assigned to these four rows.

## 6. Frozen schedule and checks

The primary schedule is the four couplings in (SRG2), all eleven translated
plaquettes at every coupling, and the four probes in (SRG16). It must record
one common state dimension, source Gramian, local exterior ranks, residual
vectors, source coverage matrix, source-sector floor, full-$Q$ rank boundary,
and probe quotients at every coupling.

The primary receipt has exactly 50 checks:

- ten global protocol, graph, source-order, weight, binding and receipt-integrity checks;
- ten row checks at each of the four couplings: finite spectrum; $P/Q$
  decomposition; source Gramian; all exterior ranks; all residual projection
  identities; null compatibility; direct/inverse source coverage; positive
  source-sector floor; probe reconstruction; and the full-$Q$ coverage
  boundary.

The independent receipt has exactly 30 checks:

- ten protocol, source, schedule and primary-receipt checks;
- five reconstructions at each of the four coupling rows: source Gramian,
  inverse-Gramian coverage, source-sector spectrum, soft probes, and the
  full-$Q$ boundary.

Use primary tolerance $10^{-10}$ for matrix and projector identities and
comparison tolerance $10^{-8}$ for the independent receipt. Both programs
refuse to overwrite an existing receipt and bind protocol, primary source,
independent source, exact larger-volume source, its scientific and recovery
protocols, and its qualified finite source receipt by SHA-256.

Primary receipt:

`runs/yang_mills_simultaneous_residual_gramian/verification-v4.json`

Independent receipt:

`runs/yang_mills_simultaneous_residual_gramian/verification-independent-v4.json`

## 7. Decision rule and claim boundary

`PASS` means that the source-bound finite construction, all simultaneous
projection identities, the source-sector floor, the soft-probe arithmetic and
the full-$Q$ rank boundary pass their declared checks. With the selected
source receipt, the primary classification is
`QUALIFIED_FINITE_SOURCE_SECTOR_RECOVERY` because the prerequisite finite
source artifact has `234/238` checks and four `TAIL_UNRESOLVED` obligations.
`SUPPORTS_FINITE_SOURCE_SECTOR_RECOVERY` is reserved for a future receipt
whose prerequisite source checks are complete; it is not the classification
of this run.
The independent receipt classification
`PRIMARY_RECEIPT_ARITHMETIC_AUDIT_PASS` means that its arithmetic, coverage,
probe and binding checks reconstruct the serialized primary result without
importing the primary implementation. It is a primary-receipt arithmetic
audit, not an independent physical Hamiltonian solve.

The result supplies a common finite Hilbert-space construction and a
quantitative source-coverage diagnostic. It does not supply a positive
volume-uniform $\gamma_{Q,*}$ for the full physical space, a conditional
Poincare estimate for the exact interacting vacuum, a thermodynamic limit, a
continuum construction or a Yang–Mills mass gap. The explicit zero in
(SRG14) is part of the result and keeps the UF-B claim at its current
conditional boundary.

## References

- `computations/yang-mills-recovery-gramian-prereg.md`—finite residual and score-penalty separation.
- `computations/yang-mills-volume-translated-block-feshbach-prereg.md`—all-plaquette finite translation coverage.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—recovered common finite graph and plaquette operators.
- `computations/yang-mills-uniform-feshbach-obligation-map.md` §§UF-B.5–UF-B.6—the full-$Q$ recovery and residual Schur obligations.
- `foundations/loop-to-bubble-projection-theorem.md` §9.22—the analytical residual-recovery theorem.
