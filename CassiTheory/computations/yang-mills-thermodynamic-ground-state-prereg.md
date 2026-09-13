# Thermodynamic Yang–Mills Ground-State Subsequence

## Status: Pre-registered analytic verification—September 2026

## Abstract

The volume-uniform fixed-support cutoff theorem makes the periodic finite-volume ground densities locally tight. This protocol fixes the resulting compactness argument: at every fixed dimensionless coupling $x$, a subsequence of periodic cubic ground-space densities converges in trace norm on every finite link set to a compatible, translation-invariant, gauge-invariant and locally normal lattice state. The limit satisfies the algebraic ground-state condition on the finite-character gauge-invariant local core.

The result constructs a thermodynamic lattice ground state at fixed regulator and fixed coupling. It does not establish convergence of the full volume sequence, uniqueness, clustering, a uniform spectral gap, the weak-coupling lattice-spacing limit, Osterwalder–Schrader reconstruction or the Clay Yang–Mills mass gap.

## 1. Finite-link reductions and Peter–Weyl tightness

Let $\rho_{0,L}$ be the normalized physical ground-space density of the periodic cubic $SU(2)$ Kogut–Susskind Hamiltonian $H_L(x)=K+xV_L$ on side $L\geq3$. For a fixed finite oriented link set $S\subset\mathbb Z^3$, identify $S$ with its non-wrapping image in every sufficiently large torus and define the kinematical reduced density

$$
\rho_{L,S}
:=
\operatorname{Tr}_{E_L\setminus S}\rho_{0,L}.
$$

The Peter–Weyl decomposition on one link is

$$
L^2(SU(2))
=
\bigoplus_{n=0}^{\infty}
V_{n/2}\otimes V_{n/2}^{*}.
$$

If $P_{C,e}$ retains doubled spins $n\leq C$, then

$$
\boxed{
d_C
:=
\operatorname{rank}P_{C,e}
=
\sum_{n=0}^{C}(n+1)^2
=
\frac{(C+1)(C+2)(2C+3)}6,
\qquad
\operatorname{rank}P_{C,S}=d_C^{|S|}.
}
\tag{YMT1}
$$

Let $P_{C,S}=\prod_{e\in S}P_{C,e}$, $Q_{C,S}=I-P_{C,S}$ and

$$
\kappa_C=\frac{(C+1)(C+3)}4.
$$

The local-density theorem gives

$$
\boxed{
\operatorname{Tr}(\rho_{L,S}Q_{C,S})
\leq
b_{C,S}(x)
:=
\frac{2x|S|}{\kappa_C}
=
\frac{8x|S|}{(C+1)(C+3)},
}
\tag{YMT2}
$$

uniformly in every sufficiently large $L$. The gentle-measurement estimate for the unnormalized compression gives


$$
\boxed{
\left\|
\rho_{L,S}-P_{C,S}\rho_{L,S}P_{C,S}
\right\|_1
\leq
2\sqrt{\operatorname{Tr}(\rho_{L,S}Q_{C,S})}
\leq2\sqrt{b_{C,S}(x)}.
}
\tag{YMT3}
$$

For the executable evidence, the existence of the finite-volume ground-space
density matrices and the operator estimate (YMT2) are analytic inputs. The
implementations do not construct the interacting $SU(2)$ ground states and do
not prove the volume-uniform tail estimate. Their scope begins with these
inputs and checks the finite-dimensional consequences, compatibility
identities and implication controls used below.

## 2. Trace-norm precompactness

For fixed $(C,S)$, the set

$$
\mathcal K_{C,S}
:=
\left\{
P_{C,S}\sigma P_{C,S}:
\sigma\succeq0,
\operatorname{Tr}\sigma=1
\right\}
$$

is bounded in the finite-dimensional real vector space of Hermitian matrices on a space of rank $d_C^{|S|}$. Its closure is compact in trace norm. Given $\varepsilon>0$, choose $C$ so that $2\sqrt{b_{C,S}(x)}<\varepsilon/2$, and choose a finite $\varepsilon/2$-net for $\mathcal K_{C,S}$. Equation (YMT3) turns it into a finite $\varepsilon$-net for the complete family of reduced densities. Hence

$$
\boxed{
\left\{\rho_{L,S}:L\geq L(S)\right\}
\text{ is relatively compact in }\mathfrak S_1(\mathcal H_S).
}
\tag{YMT4}
$$

The argument uses local electric-energy tightness. Pointwise weak compactness alone would permit singular local limits on the infinite-dimensional link Hilbert space; (YMT2) excludes that escape.

## 3. Compatible diagonal limit

Choose a nested exhaustion $S_1\subset S_2\subset\cdots$ of the oriented links of $\mathbb Z^3$. Repeated subsequence extraction followed by the Cantor diagonal choice gives increasing sides $L_k\to\infty$ and density matrices $\rho_{\infty,S_m}$ such that, for every fixed $m$,

$$
\boxed{
\lim_{k\to\infty}
\left\|\rho_{L_k,S_m}-\rho_{\infty,S_m}\right\|_1
=0.
}
\tag{YMT5}
$$

Finite-volume partial traces are compatible and the partial trace is trace-norm contractive. Therefore, whenever $m<n$,

$$
\boxed{
\operatorname{Tr}_{S_n\setminus S_m}\rho_{\infty,S_n}
=
\rho_{\infty,S_m}.
}
\tag{YMT6}
$$

For every bounded local operator $A\in\mathcal B(\mathcal H_{S_m})$, define

$$
\boxed{
\omega_x(A)
:=
\operatorname{Tr}(\rho_{\infty,S_m}A).
}
\tag{YMT7}
$$

Equation (YMT6) makes this definition independent of the chosen containing set. Positivity, normalization and norm continuity extend it to a state on the quasi-local link algebra. Periodic translations and cubic rotations pass through (YMT5). A reduced density on an arbitrary $S$ need not be invariant under a gauge action cut off at the boundary of $S$. For a compactly supported lattice gauge transformation and a local observable, choose $S_m$ to contain the observable and every incident transformed link. Finite-volume gauge invariance then passes to $\omega_x$, so the state is invariant under the quasi-local gauge automorphism. The local tail estimate also passes to the limit:

$$
\boxed{
\operatorname{Tr}(\rho_{\infty,S}Q_{C,S})
\leq
\frac{2x|S|}{\kappa_C}.
}
\tag{YMT8}
$$

Thus $\omega_x$ is locally normal, and every fixed finite-link restriction retains the same quantitative character-tail control as the periodic states.

## 4. Algebraic ground-state condition

Let $\mathfrak A_{\mathrm{gi,fin}}$ be the local gauge-invariant star algebra whose operators have finite Peter–Weyl matrix support. Such an operator preserves the physical finite-volume space, and its electric commutator is bounded. For $A\in\mathfrak A_{\mathrm{gi,fin}}$, locality makes

$$
\mathscr D_x(A)
:=
[H_L(x),A]
$$

independent of $L$ once the torus contains the one-plaquette neighbourhood of $\operatorname{supp}A$ without wrapping:

$$
\boxed{
[H_{L'}(x),A]=[H_L(x),A]=\mathscr D_x(A)
\qquad(L',L\geq L_A).
}
\tag{YMT9}
$$

Let $E_{0,L}$ be the physical ground energy. Since $A$ preserves the physical Hilbert space and $H_L-E_{0,L}\succeq0$ there,

$$
\boxed{
\operatorname{Tr}
\left(\rho_{0,L}A^*[H_L,A]\right)
=
\operatorname{Tr}
\left(\rho_{0,L}A^*(H_L-E_{0,L})A\right)
\geq0.
}
\tag{YMT10}
$$

The operator $A^*\mathscr D_x(A)$ has fixed finite support and is bounded. Equations (YMT5), (YMT7), (YMT9), and (YMT10) therefore give

$$
\boxed{
\omega_x\left(A^*\mathscr D_x(A)\right)\geq0
\qquad
(A\in\mathfrak A_{\mathrm{gi,fin}}).
}
\tag{YMT11}
$$

This is the algebraic infinite-volume ground-state condition for the local Hamiltonian derivation. The construction selects at least one subsequential state for each fixed $x$; it does not select a unique phase or establish convergence without subsequences.

## 5. Firing controls and implication boundaries

Compactness does not imply convergence of the full sequence. On a two-level local space, define

$$
\sigma_L
=
\begin{cases}
|0\rangle\langle0|,&L\text{ even},\\
|1\rangle\langle1|,&L\text{ odd}.
\end{cases}
\qquad
\|\sigma_{2k}-\sigma_{2k+1}\|_1=2.
\tag{YMT12}
$$

The sequence is precompact and has two constant subsequences, while the full sequence does not converge. Any verifier that promotes diagonal extraction to full-sequence convergence fails this control.

The energy bound is essential for local trace-norm compactness. For one $SU(2)$ link, let $\tau_n$ be a normalized vector state in a doubled-spin-$n$ Peter–Weyl sector. Then, for every fixed $C$,

$$
\operatorname{Tr}(\tau_nQ_{C,e})=1
\quad(n>C),
\qquad
\|\tau_n-\tau_m\|_1=2
\quad(n\ne m),
\tag{YMT13}
$$

while $\operatorname{Tr}(\tau_nK_e)=n(n+2)/4\to\infty$. This escaping family has no trace-norm convergent subsequence.

Existence of a thermodynamic ground state also does not imply a positive uniform gap. On a periodic spin-$1/2$ chain, let

$$
H_L^{\mathrm{FM}}
=
\sum_{r=1}^{L}(I-P_{r,r+1}),
$$

where $P_{r,r+1}$ swaps neighbouring spins. The all-up product state is a ground state for every $L$, while a one-magnon state of momentum $2\pi/L$ gives

$$
\boxed{
0\leq\Delta_L^{\mathrm{FM}}
\leq
2-2\cos\left(\frac{2\pi}{L}\right)
\longrightarrow0.
}
\tag{YMT14}
$$

This control must fire: the finite-identity checks may pass while the receipt continues to record the conditional analytic inputs, absence of an executable state construction, and null results for uniqueness, clustering, uniform gap, continuum construction and Clay resolution.

## 6. Frozen deterministic schedule

The primary implementation is `computations/verify_yang_mills_thermodynamic_ground_state.py`. The independent implementation is `computations/verify_yang_mills_thermodynamic_ground_state_independent.mjs`.

The prerequisite evidence is the local-cutoff protocol, primary source and current primary receipt:

- `computations/yang-mills-local-cutoff-density-prereg.md`;
- `computations/verify_yang_mills_local_cutoff_density.py`;
- `runs/yang_mills_local_cutoff_density/verification.json`.

The rank schedule uses

$$
C\in\{0,1,2,4,8,16,32,64,128\},
\qquad
|S|\in\{1,2,4,8\},
$$

for 36 rows. Every row records the direct sum, closed rank $d_C$, total support rank as a decimal string and its decimal digit count.

The compactness schedule uses

$$
x\in\{1/64,1/4,1,4,16\},
\qquad
|S|\in\{1,2,4,8\},
$$

$$
\varepsilon\in\{1/2,1/4,1/8,1/16,1/32\},
$$

for 100 rows. Each row finds the least nonnegative $C$ with $2\sqrt{b_{C,S}(x)}\leq\varepsilon/2$, proves that $C-1$ fails whenever $C>0$, and records the finite compressed rank. The halved target leaves an $\varepsilon/2$ radius for a finite net in the compressed matrix ball.

Twelve ground-identity fixtures use dimensions $4,5,6$, ground multiplicities $1,2$ and two deterministic complex operator seeds. Each fixture compares the direct matrix trace in (YMT10) with the nonnegative spectral sum over excited rows. A separate tensor-product fixture checks that a spectator Hamiltonian commuting with $A$ leaves $[H,A]$ unchanged. A normalized complex three-qubit state checks nested partial-trace compatibility.

The firing schedules are:

- the alternating states in (YMT12);
- escaping Peter–Weyl sectors $n\in\{1,2,4,8,16,32,64\}$ against fixed cutoffs;
- the ferromagnetic upper-gap rows $L\in\{4,8,16,32,64,128,256\}$.

The primary and independent receipts are written to `runs/yang_mills_thermodynamic_ground_state/verification.json` and `runs/yang_mills_thermodynamic_ground_state/verification-independent.json`. Both implementations refuse to overwrite an existing receipt without `--replace` and bind their protocol and sources by SHA-256. The independent receipt also binds the prerequisite local receipt and the thermodynamic primary receipt.

## 7. Frozen decision contract

A primary `PASS` requires exactly 18 checks. An independent `PASS` requires exactly 19 checks. Both require complete schedules, exact Peter–Weyl ranks, minimal compactness cutoffs, finite-rank compression, partial-trace compatibility, nonnegative finite-matrix ground identities, commutator stabilization, all three firing controls and current source bindings. The prerequisite check must record that the finite-volume ground-state setup and (YMT2) remain analytic inputs outside the executable proof surface.

A passing receipt records

- `conditional_thermodynamic_bridge_status=PASS`;
- `operator_argument_scope=CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2`;
- `finite_volume_setup_proved_by_verifier=false`;
- `uniform_tail_bound_proved_by_verifier=false`;
- `thermodynamic_state_constructed_by_verifier=false`;
- `full_sequence_convergence_established=false`;
- `uniqueness_established=false`;
- `clustering_established=false`;
- `uniform_mass_gap_established=false`;
- `continuum_hypotheses_present=false`;
- `clay_verdict=NULL`.

A failed source identity, missing row, stale binding, nonminimal cutoff, negative finite-matrix ground quadratic form, failed partial trace or nonfiring boundary control makes the corresponding receipt `FAIL`. The calculation stops at the frozen schedules.

A `PASS` verifies the finite identities and falsification controls supporting (YMT1)–(YMT14). It does not certify the interacting finite-volume ground states or the uniform operator estimate (YMT2). Conditional on those analytic inputs, the operator argument in §§1–4 constructs a subsequential locally normal thermodynamic lattice ground state at each fixed regulator and coupling. Full-sequence convergence, phase selection, clustering, a regulator-uniform positive gap, weak-coupling continuum construction, Osterwalder–Schrader reconstruction and the Clay mass gap remain open.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §9.26—volume-uniform local character-tail estimate and global-norm obstruction.
- `computations/yang-mills-local-cutoff-density-prereg.md`—fixed-support cutoff theorem and generated evidence contract.
- H. Grundling and G. Rudolph, [Dynamics for QCD on an infinite lattice](https://arxiv.org/abs/1512.06319)—infinite-lattice Hamiltonian gauge dynamics, physical observable algebra and gauge-invariant ground-state existence.
- H. Grundling and G. Rudolph, [QCD on an infinite lattice](https://arxiv.org/abs/1108.2129)—inductive local gauge algebra and Gauss-law construction.
- M. Cha, P. Naaijkens and B. Nachtergaele, [The complete set of infinite volume ground states for Kitaev's abelian quantum double models](https://arxiv.org/abs/1608.04449)—weak-star limits of finite-volume ground states and boundary-sector dependence.
