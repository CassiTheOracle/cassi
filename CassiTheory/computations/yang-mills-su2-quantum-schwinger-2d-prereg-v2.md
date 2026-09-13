# Normalization-Corrected SU(2) Quantum Schwinger-Function Generator in Two Dimensions

## Status: Pre-registered analytic verification—September 2026

## Abstract

This protocol fixes the finite two-dimensional quantum transfer generator after deriving the Wilson character normalization from normalized Haar orthogonality. The coefficient multiplying the dimension-$n$ character is $C_n=2nI_n(\beta)/\beta$, while the gluing eigenvalue is $r_n=C_n/n=2I_n(\beta)/\beta$. The primary and independent implementations reconstruct the corrected transfer Hamiltonian, gauge-invariant fusion observables, vacuum correlators and effective masses.

The model is a finite two-dimensional transfer benchmark. It does not establish a four-dimensional thermodynamic limit, Osterwalder–Schrader reconstruction, a continuum quantum field or a physical Yang–Mills mass gap.

## 1. Corrected finite transfer matrix

Use normalized Haar measure and the dimension-indexed SU(2) characters

$$
n=2j+1=1,2,3,\ldots,
\qquad
\chi_n(\theta)=\frac{\sin(n\theta)}{\sin\theta}.
$$

The corrected Wilson expansion and convolution quotient are

$$
e^{\beta\cos\theta}
=
\sum_{n\geq1}C_n(\beta)\chi_n(\theta),
\qquad
C_n(\beta)=\frac{2nI_n(\beta)}\beta,
\tag{YMQ2-1}
$$

$$
r_n(\beta)
:=
\frac{C_n(\beta)}n
=
\frac{2I_n(\beta)}\beta.
\tag{YMQ2-2}
$$

Equations (YMW2-1)–(YMW2-4) of `computations/yang-mills-su2-wilson-2d-prereg-v2.md` give the independent Haar and gluing derivation.

For spatial circle length $L_s$ and character cutoff $N$, define

$$
T_{N,L_s,\beta}
:=
\operatorname{diag}\bigl(r_1(\beta)^{L_s},\ldots,r_N(\beta)^{L_s}\bigr),
\tag{YMQ2-3}
$$

and normalize its largest eigenvalue to one:

$$
H_{N,L_s,\beta}
:=
-\log\!\left(\frac{T_{N,L_s,\beta}}{r_1(\beta)^{L_s}}\right),
\qquad
E_n=L_s\log\frac{r_1(\beta)}{r_n(\beta)}.
\tag{YMQ2-4}
$$

For every declared $\beta$, $r_n>0$ and is strictly decreasing in $n$. Hence $E_1=0$ and $E_n>0$ for $n>1$ in every retained finite model.

## 2. Fusion observables and vacuum correlators

For doubled-spin channel $k\in\{1,2,3\}$, let $O_k$ be multiplication by $\chi_{k+1}$ projected to the retained character space. Its matrix entries implement SU(2) fusion:

$$
(O_k)_{mn}=1
\quad\Longleftrightarrow\quad
m-1\in
\{|k-(n-1)|,|k-(n-1)|+2,\ldots,k+n-1\},
\tag{YMQ2-5}
$$

with $1\leq m,n\leq N$, and vanish otherwise. For the vacuum vector $|0\rangle=e_1$,

$$
O_k|0\rangle=e_{k+1},
\qquad
\langle0|O_k|0\rangle=0.
\tag{YMQ2-6}
$$

The connected transfer-vacuum correlator is

$$
C_{k,N,L_s,\beta}(t)
:=
\langle0|O_ke^{-tH}O_k|0\rangle
-
\langle0|O_k|0\rangle^2
=
e^{-tE_{k+1}}.
\tag{YMQ2-7}
$$

At the declared increment $\delta t=1/2$,

$$
-\frac1{\delta t}\log\frac{C_k(t+\delta t)}{C_k(t)}
=E_{k+1},
\qquad
C_k(t+\delta t)=C_k(t)e^{-\delta tE_{k+1}}.
\tag{YMQ2-8}
$$

These are finite transfer-matrix identities.

## 3. Frozen schedules and checks

Use

$$
\beta\in\{1,2,4\},
\quad
L_s\in\{1,2,4\},
\quad
N\in\{8,16,24,32\},
$$

$$
k\in\{1,2,3\},
\quad
t\in\{0,\tfrac12,1,2,4\},
\quad
\delta t=\tfrac12.
\tag{YMQ2-9}
$$

The independent Haar schedule is $n\in\{1,2,\ldots,8\}$. There are 36 parameter rows. Each row has exactly thirteen checks:

1. every retained $C_n$, $r_n$ and transfer eigenvalue is finite and positive;
2. numerical Haar quadrature agrees with $C_n=2nI_n/\beta$ on the eight-order Haar schedule;
3. $C_n/n=r_n$ for every retained representation;
4. the rejected transfer value $r_n/n$ differs from $r_n$ by at least one half at $n=2$;
5. the finite diagonal transfer matrix is symmetric;
6. $r_n$ is strictly decreasing;
7. the normalized ground energy is zero and every retained excited energy is positive;
8. every declared fusion observable is finite and symmetric;
9. every vacuum orbit obeys (YMQ2-6);
10. every scheduled connected correlator is finite and nonnegative;
11. every effective mass and semigroup ratio obeys (YMQ2-8);
12. every fusion operator obeys $\|O_k\|\leq k+1$;
13. the complete row payload contains no non-finite value.

The primary therefore has 468 row checks and eight top-level checks, for exactly 476 checks. The independent receipt has ten top-level checks and independently reconstructs all 36 rows.

## 4. Independent construction and bindings

The primary implementation is

`computations/verify_yang_mills_su2_quantum_schwinger_2d.py`.

The independent implementation is

`computations/verify_yang_mills_su2_quantum_schwinger_2d_independent.mjs`.

The corrected receipts are

- `runs/yang_mills_su2_quantum_schwinger_2d/verification-v2.json`;
- `runs/yang_mills_su2_quantum_schwinger_2d/verification-independent-v2.json`.

The corrected Wilson prerequisite is

`runs/yang_mills_su2_wilson_2d/verification-v2.json`.

Both sources bind this protocol and the Wilson v2 protocol. The primary binds and requires a passing current Wilson v2 receipt. The independent source also binds the primary source, both primary receipts and its own source. It evaluates $I_n$ with a positive series and evaluates the Haar integral by deterministic midpoint quadrature rather than importing primary arrays.

Both outputs refuse overwrite without an explicit replacement flag. The primary scalar tolerance is $10^{-11}$, its Haar relative tolerance is $10^{-9}$, and the independent comparison tolerance is $10^{-9}$.

## 5. Decision contract

`PASS` requires exactly 476 passing primary checks, ten passing independent top-level checks, complete independent agreement on all 36 rows, current source and protocol hashes, a passing current Wilson v2 prerequisite, and a firing double-division control in every row.

`FAIL` records any normalization, transfer, fusion, vacuum-orbit, correlator, effective-mass, semigroup, finiteness, source-identity or count failure.

`INCONCLUSIVE` records missing execution or missing finite-value evidence.

A `PASS` establishes the normalization-corrected finite two-dimensional quantum Schwinger generator. Character-cutoff convergence of this correlator, four-dimensional spatial-volume control, the lattice-spacing limit and a regulator-independent mass gap remain open.

The v1 protocol and v1 receipts use the rejected double-division normalization and carry no active evidence claim.

## References

- `computations/yang-mills-su2-wilson-2d-prereg-v2.md`—normalized-Haar coefficient, gluing quotient and corrected tail.
- `computations/yang-mills-su2-quantum-schwinger-2d-prereg-v1.md`—invalidated normalization retained as defect provenance.
- `computations/yang-mills-su2-schwinger-prereg-v2.md`—finite one-plaquette Hamiltonian correlator bridge.
- `computations/yang-mills-finite-graph-cutoff-form-prereg.md`—fixed-graph character-cutoff form convergence.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—continuum target.
