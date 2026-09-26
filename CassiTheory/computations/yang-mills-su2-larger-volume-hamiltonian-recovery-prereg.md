# Finite Larger-Volume SU(2) Hamiltonian Spectator-Channel Recovery

## Status: Pre-registered recovery—September 2026

## Abstract

This protocol governs the matrix-support recovery for the finite $3\times2\times2$ SU(2) Hamiltonian defined in `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`. A Wilson plaquette acts only at its four incident vertices. Every four-valent vertex outside that set contributes the intertwiner overlap $\delta_{a_v^{\mathrm L},a_v^{\mathrm R}}$. The current candidate construction groups states by link labels alone and therefore admits matrix entries between orthogonal spectator channels. The resulting regulated Hamiltonian violates the exact lower bound $H_C(x)\succeq0$ at doubled cutoff $C=2$.

The recovery enforces spectator-channel compatibility in the primary and independent constructions, verifies a fixed forbidden-transition witness, checks every normalized plaquette column against the character-multiplication Parseval bound, checks the extremal spectrum of the assembled Wilson sum, and requires nonnegative Ritz ground energies. New receipts use a non-overwriting recovery directory. The calculation remains a finite spatial-volume and finite-character construction.

## 1. Fixed scientific target

The graph, orientation, basis, Hamiltonian, cutoff schedule and coupling schedule remain those of `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`:

$$
V=\{0,1,2\}\times\{0,1\}\times\{0,1\},
\qquad
C\in\{1,2\},
\qquad
x\in\left\{\frac1{64},\frac1{16},\frac14,1\right\},
$$

with twenty links, eleven signed plaquette words and

$$
H_C(x)=K_C+22xI-xW_C.
\tag{YMLVR1}
$$

The basis state consists of the twenty doubled link spins followed by the four sequential-coupling labels at vertices $4,5,6,7$. The overlap is

$$
G_{st}=\delta_{st}\nu_s,
\qquad
\nu_s=\prod_{e=0}^{19}(n_e+1)^{-1}.
\tag{YMLVR2}
$$

No coupling, cutoff, graph, plaquette word or basis convention may be changed by the recovery.

## 2. Spectator-channel identity

For plaquette $p$, let $V_p$ be the set of its four incident vertices and let $a_v(s)$ denote the intertwiner channel of state $s$ at a four-valent vertex. Link Haar orthogonality requires identical spectator link labels. Vertex orthogonality additionally requires

$$
a_v(s)=a_v(t)
\qquad
\text{for every }v\in\{4,5,6,7\}\setminus V_p
\tag{YMLVR3}
$$

before $(s,t)$ can be a matrix candidate for $W_p$.

Equivalently, the exact matrix element contains

$$
\prod_{v\in\{4,5,6,7\}\setminus V_p}
\left\langle I_{a_v(s)},I_{a_v(t)}\right\rangle
=
\prod_{v\in\{4,5,6,7\}\setminus V_p}
\delta_{a_v(s),a_v(t)}.
\tag{YMLVR4}
$$

The primary must enforce (YMLVR3) when constructing candidate target indices. Its scalar matrix-element oracle must return exact zero when (YMLVR3) fails. The independent source must implement the same identity from its own active-vertex construction rather than import the primary predicate.

## 3. Frozen forbidden-transition witness

The recovery includes the following doubled-spin and channel state as the ket:

$$
\begin{aligned}
t={}&(1,1,2,2,1,1,1,1,1,1,1,1,0,2,0,1,1,2,1,1;\\
&0,0,3,1).
\end{aligned}
\tag{YMLVR5}
$$

Use plaquette $yz_{x0}$, whose active vertices are $\{0,1,2,3\}$. At spectator vertex $6$, the incident doubled spins are $(1,2,1,2)$. A candidate with channel $1$ at vertex $6$ against channel $3$ in (YMLVR5) has

$$
\left\langle I_1,I_3\right\rangle=0.
\tag{YMLVR6}
$$

The recovered candidate set must exclude every such state, and the scalar matrix-element function must return zero for the fixed mismatched pair selected lexicographically from the admissible link-label targets. The receipt records the local overlap, the scalar matrix element and whether the unfiltered edge-only construction would admit the pair.

The firing control deliberately evaluates the edge-only candidate set without using it to assemble the production matrix. It must find the fixed mismatched pair and a normalized $yz_{x0}$ column norm squared greater than $4$. Failure to fire means the recovery no longer demonstrates sensitivity to the defect it is designed to exclude.

## 4. Character-multiplication bounds

For each normalized basis function $e_t=\psi_t/\sqrt{\nu_t}$ and each plaquette,

$$
\sum_s
\left|\left\langle e_s,\chi_{1/2}(U_p)e_t\right\rangle\right|^2
=
\|P_C\chi_{1/2}(U_p)e_t\|^2
\le4.
\tag{YMLVR7}
$$

The primary computes all column sums of every assembled plaquette matrix in orthonormal coordinates and records the maximum. Every maximum must be at most $4+10^{-10}$. The independent construction recomputes these maxima from its separately assembled matrices.

The complete Wilson compression satisfies

$$
-22I\preceq
G_C^{-1/2}W_CG_C^{-1/2}
\preceq22I.
\tag{YMLVR8}
$$

At each cutoff, both sources compute the smallest and largest algebraic eigenvalues of this Hermitian sparse operator. The lower endpoint must be at least $-22-10^{-8}$ and the upper endpoint at most $22+10^{-8}$. The eigensolver residual for each extremal vector must be at most $10^{-8}$.

Since $K_C\succeq0$, equations (YMLVR1) and (YMLVR8) imply

$$
H_C(x)\succeq0.
\tag{YMLVR9}
$$

Every scheduled Ritz ground energy must be at least $-10^{-8}$. This check is part of finite-construction qualification rather than a tail diagnostic.

## 5. Matrix and basis controls

The recovery retains every structural control in the original protocol and adds:

1. all eleven plaquette words contain four distinct links and close under endpoint walking;
2. every production candidate pair satisfies spectator-link and spectator-channel compatibility;
3. candidate target indices are unique within each source column;
4. the fixed forbidden-transition witness satisfies (YMLVR6) and has zero recovered matrix element;
5. the edge-only firing construction violates (YMLVR7) on the fixed witness column;
6. every recovered plaquette column satisfies (YMLVR7);
7. the assembled Wilson spectrum satisfies (YMLVR8);
8. every scheduled Hamiltonian row satisfies (YMLVR9);
9. the primary and independent ordered basis hashes, plaquette matrix hashes, spectra, shell norms and new invariant maxima agree within their declared tolerances.

The original generalized-eigenvalue residual tolerance remains $10^{-10}$. Matrix Hermiticity, reversed-word dagger checks, deterministic forbidden-edge samples, nested energy monotonicity and the declared character-tail decision tree remain unchanged.

## 6. Receipt paths and bindings

The recovered primary source is

`computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`.

The recovered independent source is

`computations/verify_yang_mills_su2_larger_volume_hamiltonian_independent.py`.

They create new receipts at

`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json`

and

`runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification-independent.json`.

Neither source may overwrite an existing receipt. Both receipts bind this recovery protocol, the original scientific protocol, both source files, `computations/verify_yang_mills_exact_block_spectrum.py`, the complete ordered basis and every finalized plaquette matrix by SHA-256.

The excluded finite-construction receipts have source identities recorded in `runs/yang_mills_continuum_boundary_audit/verification.json`. They remain provenance inputs and supply no Hamiltonian spectrum or cutoff-tail evidence after the firing control in §3 is established.

## 7. Decision tree and scope

The recovered finite construction is `PASS` only when every graph, basis, overlap, contraction, spectator-channel, uniqueness, firing, Parseval, Wilson-spectrum, Hamiltonian-positivity, Hermiticity and Ritz-residual check passes.

A passing finite construction receives `PASS_RECOVERED_FINITE_CONSTRUCTION`. Character-tail rows retain the original statuses `TAIL_CERTIFIED_EXACT_SHELL`, `TAIL_CERTIFIED_ANALYTIC`, `COARSE` and `TAIL_UNRESOLVED`. The aggregate label `SUPPORTS_FINITE_VOLUME_CUTOFF_TAIL_CONTROL` requires useful tail bounds at both cutoffs under the original threshold $T_C\le0.1$.

No outcome establishes character-cutoff removal, spatial-volume uniformity, a thermodynamic limit, Osterwalder–Schrader reconstruction or a regulator-independent mass gap. The continuum claim remains `false` in both receipts.

## References

- `computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md`—finite graph, Hamiltonian, basis and character-tail protocol.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`—recovered primary implementation.
- `computations/verify_yang_mills_su2_larger_volume_hamiltonian_independent.py`—independent reconstruction.
- `computations/verify_yang_mills_exact_block_spectrum.py`—SU(2) representation and Haar-contraction primitives.
- `foundations/loop-to-bubble-projection-theorem.md`—finite-regulator and continuum Yang–Mills boundary.
