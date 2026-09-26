# Local Yang–Mills Character-Cutoff Density Theorem

## Status: Pre-registered analytic verification—September 2026

## Abstract

The fixed-graph character-cutoff theorem controls the norm discarded from an entire finite-volume wavefunction. Its total-energy bound grows with volume and therefore does not supply a thermodynamic estimate. The appropriate finite-volume statement for a local quantum field theory is convergence on each fixed finite set of links.

This protocol fixes a local projector theorem for the regulated $SU(2)$ Kogut–Susskind ground state. On a periodic cubic lattice, a symmetry-invariant ground-state density matrix has a character-tail bound on any fixed link set that is independent of the total lattice volume. A separate gauge-invariant product family proves that global wavefunction-norm convergence cannot be uniform in volume at fixed character cutoff, even at bounded electric-energy density. The theorem leaves the existence of a thermodynamic state, clustering, weak-coupling field estimates, Osterwalder–Schrader reconstruction, and a regulator-independent mass gap unresolved.

## 1. Finite-volume Hamiltonian and local projectors

Let $\rho$ be a gauge-invariant density matrix on a finite connected graph $\Gamma=(V,E)$ with

$$
H_\Gamma(x)=K+xV_\Gamma,
\qquad
K=\sum_{e\in E}K_e,
\qquad
K_e\succeq0,
\qquad
V_\Gamma\succeq0,
\qquad
x\geq0.
\tag{YMLC1}
$$

Here $V_\Gamma=\sum_{p=1}^{N_p}(2-\chi_{1/2}(U_p))$ is the Wilson potential. Each plaquette term lies in $[0,4]$.

For an integer doubled-spin cutoff $C\geq0$, let $P_{C,e}$ be the spectral projector of the link Casimir $K_e$ onto $n_e=2j_e\leq C$. For a finite link set $S\subseteq E$, define

$$
P_{C,S}=\prod_{e\in S}P_{C,e},
\qquad
Q_{C,S}=I-P_{C,S},
\qquad
\kappa_C=\frac{(C+1)(C+3)}4.
\tag{YMLC2}
$$

The link Casimirs commute, and each first excluded link sector has energy at least $\kappa_C$. Hence

$$
Q_{C,S}
\preceq
\sum_{e\in S}(I-P_{C,e})
\preceq
\frac1{\kappa_C}\sum_{e\in S}K_e.
\tag{YMLC3}
$$

Writing

$$
\delta_{C,S}(\rho)
:=\operatorname{Tr}(\rho Q_{C,S}),
\tag{YMLC4}
$$

gives the local character-tail estimate

$$
\boxed{
\delta_{C,S}(\rho)
\leq
\frac1{\kappa_C}
\sum_{e\in S}\operatorname{Tr}(\rho K_e).
}
\tag{YMLC5}
$$

The projectors commute with gauge transformations, so the projected state remains in the physical Hilbert space.

## 2. Local observable control

When $\delta=\delta_{C,S}(\rho)<1$, define the normalized locally truncated state

$$
\rho_{C,S}
=
\frac{P_{C,S}\rho P_{C,S}}{1-\delta}.
\tag{YMLC6}
$$

The gentle-measurement inequality and normalization give

$$
\|\rho-\rho_{C,S}\|_1
\leq
2\sqrt\delta+\delta.
\tag{YMLC7}
$$

Every bounded observable $A$ therefore obeys

$$
\boxed{
\left|
\operatorname{Tr}(\rho A)
-
\operatorname{Tr}(\rho_{C,S}A)
\right|
\leq
\|A\|\left(2\sqrt\delta+\delta\right).
}
\tag{YMLC8}
$$

The application below uses observables supported on $S$. Equation (YMLC8) is stated for arbitrary bounded $A$ because trace distance controls the full state.

## 3. Edge-transitive energy-density bound

Suppose a finite symmetry group acts transitively on the links, commutes with $H_\Gamma$, and leaves $\rho$ invariant. Then

$$
\operatorname{Tr}(\rho K_e)
=
\frac{\operatorname{Tr}(\rho K)}{|E|}
\leq
\frac{\operatorname{Tr}(\rho H_\Gamma)}{|E|}.
\tag{YMLC9}
$$

Let $\Pi_0$ be the finite-volume ground-space projector and

$$
\rho_0=\frac{\Pi_0}{\operatorname{Tr}\Pi_0}.
\tag{YMLC10}
$$

Because $\Pi_0$ is a spectral projector of the symmetric Hamiltonian, $\rho_0$ is symmetry invariant without a ground-state uniqueness assumption. The normalized constant wavefunction is gauge invariant, has zero electric energy, and has zero expectation of every nondegenerate elementary plaquette character. The variational principle gives

$$
E_0(\Gamma,x)
\leq
2xN_p.
\tag{YMLC11}
$$

For the three-dimensional periodic cubic lattice with side $L\geq3$,

$$
|E_L|=3L^3,
\qquad
N_{p,L}=3L^3.
\tag{YMLC12}
$$

Equations (YMLC5), (YMLC9), and (YMLC11) therefore give

$$
\boxed{
\delta_{C,S}(\rho_{0,L})
\leq
b_{C,S}(x)
:=
\frac{2x|S|}{\kappa_C},
\qquad
L\geq3.
}
\tag{YMLC13}
$$

Whenever $b_{C,S}(x)<1$,

$$
\sup_{L\geq3}
\left|
\operatorname{Tr}(\rho_{0,L}A)
-
\operatorname{Tr}((\rho_{0,L})_{C,S}A)
\right|
\leq
\|A\|\left(2\sqrt{b_{C,S}(x)}+b_{C,S}(x)\right).
\tag{YMLC14}
$$

For fixed $x$ and finite $S$, the right side tends to zero as $C\to\infty$, uniformly in $L$. Along a joint auxiliary-cutoff schedule $x\to\infty$, this bound tends to zero when

$$
\frac{C(x)^2}{x}\longrightarrow\infty.
\tag{YMLC15}
$$

The estimate $E_0/|E|\leq2x$ is variational and volume uniform. A sharper weak-coupling schedule requires a volume-uniform electric-energy-density estimate below order $x$.

## 4. Global wavefunction-norm obstruction

Let $\Gamma_N$ be a connected flower of $N$ edge-disjoint oriented squares sharing one root vertex. Tree gauge leaves $N$ independent plaquette holonomies $h_1,\ldots,h_N$. The same state embeds in any lattice containing $N$ edge-disjoint squares by taking the constant wavefunction on every unused link. For $0<q<1$, define the normalized central function

$$
f_q(h)
=\sqrt{1-q^2}
\sum_{n=0}^{\infty}q^n\chi_{n/2}(h)
\tag{YMLC16}
$$

and the gauge-invariant state

$$
\Psi_{N,q}(h_1,\ldots,h_N)
=\prod_{r=1}^{N}f_q(h_r).
\tag{YMLC17}
$$

Character orthogonality gives finite electric energy per square,

$$
\frac{\langle\Psi_{N,q},K\Psi_{N,q}\rangle}{N}
=(1-q^2)\sum_{n=0}^{\infty}n(n+2)q^{2n}
=
\frac{q^2(3-q^2)}{(1-q^2)^2}.
\tag{YMLC18}
$$

Let $P_C^{(N)}$ impose the doubled-spin cutoff on every link. Since the square loops are edge disjoint,

$$
\|P_C^{(N)}\Psi_{N,q}\|_2^2
=
\left(1-q^{2(C+1)}\right)^N
\tag{YMLC19}
$$

and therefore

$$
\boxed{
\|(I-P_C^{(N)})\Psi_{N,q}\|_2^2
=1-\left(1-q^{2(C+1)}\right)^N
\longrightarrow1
\quad(N\to\infty).
}
\tag{YMLC20}
$$

Thus bounded electric-energy density does not yield volume-uniform convergence of whole normalized wavefunctions at fixed $C$. To retain squared norm at least $1-\varepsilon$, the smallest integer cutoff is

$$
C_{\min}(N,q,\varepsilon)
=
\max\left\{0,
\left\lceil
\frac{\log\!\left(1-(1-\varepsilon)^{1/N}\right)}{2\log q}-1
\right\rceil
\right\}.
\tag{YMLC21}
$$

This grows logarithmically with $N$ at fixed $q$ and $\varepsilon$.

## 5. Frozen deterministic schedule

The primary implementation is

`computations/verify_yang_mills_local_cutoff_density.py`.

The independent implementation is

`computations/verify_yang_mills_local_cutoff_density_independent.mjs`.

The local cubic schedule is

$$
L\in\{3,4,6,8,12,16,24,32\},
\qquad
x\in\{1/64,1/16,1/4,1,4,16\},
$$

$$
|S|\in\{1,4,6,12\},
\qquad
C\in\{1,2,4,8,16,32,64,128\}.
\tag{YMLC22}
$$

It contains exactly $8\times6\times4\times8=1536$ rows. Every row records $|E_L|$, $N_{p,L}$, $\kappa_C$, $b_{C,S}(x)$, whether $b<1$, and the applicable unit-norm observable bound from (YMLC14). The attempted and applicable counts are explicit. At fixed $(x,|S|)$ the bound must be identical across all eight volumes and strictly decrease with $C$.

The joint weak-coupling diagnostic uses

$$
k\in\{2,4,8,16,32,64,128\},
\qquad
x_k=k^4,
\qquad
C_k=k^3,
\qquad
|S|=1.
\tag{YMLC23}
$$

It checks $C_k^2/x_k=k^2$, strict decrease of $b_k$, and convergence of the observable envelope. This deterministic diagnostic covers only the sufficient auxiliary-cutoff schedule in (YMLC15); no weak-coupling field estimate is supplied.

The global-obstruction schedule is

$$
q\in\{1/4,1/2,3/4\},
\qquad
C\in\{0,1,2,4,8\},
$$

$$
N\in\{1,2,4,8,16,32,64,128,256,512,1024,4096\}.
\tag{YMLC24}
$$

It contains 180 rows. Every row records the one-loop tail, retained global norm, discarded global norm, electric energy per loop, and $C_{\min}$ for $\varepsilon=0.1$. Closed forms are compared with direct character sums, iterative retained-mass multiplication, and direct minimal-cutoff search.

The firing control is $(q,C,N)=(1/2,2,512)$. It must satisfy

$$
1-(1-2^{-6})^{512}>0.999.
\tag{YMLC25}
$$

A check suite that does not reject a volume-independent global-norm interpretation at this row fails the protocol.

## 6. Tolerances, receipts, and decision tree

Algebraic, probability and schedule comparisons use tolerance $10^{-12}$; the primary absolute comparisons are at least as strict as the declared combined absolute and relative tolerance. Direct character sums run through $n=4096$. Stable global probabilities use `log1p` and `expm1`; iterative multiplication supplies a separate reconstruction on the frozen finite schedule.

The primary creates

`runs/yang_mills_local_cutoff_density/verification.json`.

The independent source creates

`runs/yang_mills_local_cutoff_density/verification-independent.json`.

Neither source overwrites an existing receipt without an explicit `--replace` option. Both receipts bind this protocol and their source files by SHA-256. The independent receipt also binds the primary source and receipt.

The analytic result is internally verified only when both implementations pass every formula, coverage, applicability, volume-invariance, monotonicity, series, minimal-cutoff, firing, source-binding, and receipt-comparison check. The receipts must expose:

- `local_cutoff_status`, equal to `PASS` or `FAIL`;
- `global_norm_uniformity`, fixed to `EXCLUDED_BY_PRODUCT_FAMILY` when the firing control passes;
- `thermodynamic_limit_constructed`, fixed to `false`;
- `continuum_hypotheses_present`, fixed to `false`;
- `clay_verdict`, fixed to `NULL`.

A `PASS` verifies (YMLC1)–(YMLC25), volume-uniform local projection control at fixed coupling and the global-norm obstruction under electric-energy-density control alone. The proof is the operator argument in §§1–4. The result supplies no convergence of $\rho_{0,L}$ as $L\to\infty$, no uniqueness or clustering estimate, no uniform weak-coupling electric-energy-density bound, no continuum measure, no Osterwalder–Schrader reconstruction, and no regulator-independent positive mass gap.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.20–9.25—finite regulated gap identities, conditional multiscale criteria, and the fixed-graph cutoff theorem.
- `computations/yang-mills-finite-graph-cutoff-form-prereg.md`—global fixed-finite-graph form-core and Ritz theorem.
- `computations/verify_yang_mills_continuum_boundary_audit.py`—hash-bound separation between finite evidence and the continuum target.
- A. Winter, [Coding theorem and strong converse for quantum channels](https://doi.org/10.1109/18.651037), Lemma 9—gentle measurement estimate.
- J. A. Zapata, [Local gauge theory and coarse graining](https://arxiv.org/abs/1203.2306)—local holonomy data and finite graph refinement.
- A. Jaffe and E. Witten, [Quantum Yang–Mills Theory](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), §4—continuum existence and mass-gap requirements.
