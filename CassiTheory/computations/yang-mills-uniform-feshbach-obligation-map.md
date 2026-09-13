# Yang–Mills Uniform Feshbach Obligation Map

## Status: Hypothesized—September 2026

## Abstract

This document fixes the conditional statement that an interacting Feshbach construction would have to prove before it can support the uniform lower-form criterion for the Yang–Mills mass-gap problem. It uses an explicit weak-coupling and growing-volume trajectory, the physical overlap metric, the exact retained/discarded projections, a fixed resolvent domain, and fixed positive margins. Existing Feshbach receipts are classified against these obligations. A finite receipt receives a finite-regulator classification; the `YM262` conclusion requires every obligation in this map together with continuum recovery. This is an analytical roadmap, not an executable receipt protocol.

## 1. Target and frozen trajectory

The target is the centered local lower form bound in `foundations/loop-to-bubble-projection-theorem.md` §9.34. Let

$$
\mathfrak T=\{(a_\nu,L_\nu,g_\nu)\}_{\nu\ge1},
\qquad
F_\nu:=F_W(g_\nu),
$$

where $F_W$ is the two-loop Wilson scale fixed in (YM242). For a concrete screen, freeze

$$
 g_\nu^2=\frac1{\nu+8},
 \qquad
 a_\nu=F_\nu,
 \qquad
 L_\nu=2^{\left\lceil-2\log_2F_\nu\right\rceil},
 \qquad
 \Lambda_\nu=(\mathbb Z/L_\nu\mathbb Z)^3.
$$

The graph is the periodic cubic lattice with nearest-neighbour oriented links and the Kogut–Susskind Hamiltonian on the gauge-invariant Hilbert space. The schedule has $g_\nu\downarrow0$, $a_\nu\downarrow0$, and $L_\nu a_\nu\to\infty$. The choice $a_\nu=F_\nu$ fixes units for the normalized operator below; the general scale statement remains the separate requirement

$$
\frac{F_\nu}{a_\nu}\longrightarrow m_W\in(0,\infty).
$$

Write $H_\nu$ for the physical Hamiltonian, $E_{0,\nu}$ for its ground energy, and $\Omega_\nu$ for the normalized positive ground state. Define the scale-normalized shifted operator

$$
Y_\nu:=\frac{a_\nu}{F_\nu}(H_\nu-E_{0,\nu}).
$$

The finite-regulator target becomes

$$
\boxed{
\langle f\Omega_\nu,Y_\nu f\Omega_\nu\rangle_\nu
\ge c_-\|f\Omega_\nu\|_\nu^2,
\qquad
f\in\mathscr D_{\nu,\mathrm{loc}}^0,
\qquad
c_->0
}
\tag{UF1}
$$

with one $c_-$ independent of $\nu$, spatial volume, representation cutoff, and the selected weak-coupling trajectory. Multiplication by $F_\nu/a_\nu$ recovers (YM262).

## 2. Exact $S$-normalized Feshbach candidate

Use a gauge-invariant spin-network or Wilson-word basis $\{\Phi_{\nu,k}\}$ with raw overlap matrix

$$
(S_\nu)_{ij}=\langle\Phi_{\nu,i},\Phi_{\nu,j}\rangle,
$$

and raw shifted Hamiltonian matrix

$$
(M_\nu)_{ij}=\langle\Phi_{\nu,i},(H_\nu-E_{0,\nu})\Phi_{\nu,j}\rangle.
$$

On every positive-overlap subspace, the physical Euclidean representative is

$$
\widetilde Y_\nu
:=
\frac{a_\nu}{F_\nu}
S_\nu^{-1/2}M_\nu S_\nu^{-1/2}.
\tag{UF2}
$$

The inverse square root is taken on the positive support of $S_\nu$. A raw coefficient column $C$ for centered vectors is mapped to the physical Euclidean columns $U=S_\nu^{1/2}C$. The ground vector is removed first. With

$$
\mathcal K_\nu:=\Omega_\nu^\perp,
\qquad
P_{\nu,B,C}:=\operatorname{proj}_{\mathcal K_\nu}
\operatorname{ran}(U_{\nu,B,C}),
\qquad
Q_{\nu,B,C}:=I_{\mathcal K_\nu}-P_{\nu,B,C},
\tag{UF3}
$$

$\mathcal W_{B,C}$ denotes the complete centered gauge-invariant Wilson-word family supported in a block $B$ and with representation cutoff $C$. The centering is with the exact vacuum functional, so every retained vector lies in $\mathcal K_\nu$.

On the exact discarded form domain define

$$
A=P\widetilde YP,
\qquad
B=P\widetilde YQ,
\qquad
D=Q\widetilde YQ,
$$

and, for $z$ below the discarded spectrum,

$$
\mathfrak F_{\nu,B,C}(z)
:=A-zI_P-B(D-zI_Q)^{-1}B^*.
\tag{UF4}
$$

The fixed candidate constants are

$$
 c_*:=2^{-12},
 \qquad
 \rho_*:=2^{-12},
 \qquad
 \sigma_*:=2^{-12}.
\tag{UF5}
$$

The values in (UF5) are declared hypotheses for a future proof package. No
current receipt or theorem establishes that these margins are attainable.

The frozen resolvent domain and margins are

$$
0\le z\le c_*;
\qquad
D\succeq(c_*+\rho_*)I_Q;
\qquad
\mathfrak F_{\nu,B,C}(c_*)\succeq\sigma_*I_P.
\tag{UF6}
$$

The derivative

$$
\frac{d}{dz}\mathfrak F_{\nu,B,C}(z)
=-I_P-B(D-zI_Q)^{-2}B^*
\preceq0
$$

makes the endpoint $z=c_*$ sufficient once the uniform discarded margin in (UF6) is proved. The resulting lower bound on every retained source span is at least $c_*$. The word-core and transfer obligations below are required before this finite-span statement can be identified with (UF1).

## 3. Obligations with the missing quantifiers exposed

### UF-A. Exact gauge-compatible block or transfer map

Construct maps for every $\nu$, block position, and boundary sector that are isometric in the $S_\nu$ physical inner product and preserve the Gauss-law invariant domain. The map must retain the complete centered local Wilson-word family and place every fibre, boundary, plaquette-crossing, and generated interaction in the declared $P$ or $Q$ sector. The operator identity behind (UF4) must hold on the exact form domain.

A finite spin-network matrix with an asserted Ritz complement instantiates the algebraic part of UF-A. The full obligation additionally requires the block map, boundary fibres, and exact form-domain inclusion.

### UF-B. Uniform discarded-sector resolvent

The bound required for the whole trajectory is

$$
\inf_{\nu\ge1}\nobreak
\inf_{B,C}
\left[\inf\operatorname{spec}(D_{\nu,B,C})-c_*\right]
\ge\rho_*.
\tag{UF7}
$$

For unbounded $Q$ sectors, the equivalent form statement is

$$
\|(D_{\nu,B,C}-z)^{-1}\|\le
\frac1{c_*+\rho_*-z}
\quad(0\le z\le c_*),
\tag{UF8}
$$

with the bound uniform in lattice spacing, volume, coupling, block position, boundary fibre and representation cutoff. A finite full-volume gap used as a Ritz-resolution oracle is a row-wise assumption; it is not a proof of (UF7).

### UF-C. Uniform Schur lower bound

The interacting self-energy must obey the endpoint inequality on every retained local span:

$$
\inf_{\nu,B,C}
\inf\operatorname{spec}\!\left(
\mathfrak F_{\nu,B,C}(c_*)
\right)
\ge\sigma_*.
\tag{UF9}
$$

The quantifier includes every translated block and every boundary sector. Source-dependent positive roots, a positive root at each sampled coupling, and a root-to-gap ratio bounded away from zero on one graph are finite observations. UF-C requires one declared constant over the complete trajectory and an extension from cutoff spans to the local core.

### UF-D. Cutoff removal and local correlation transport

For every centered local gauge-invariant word $A$, construct source vectors $v_{\nu,A}=f_{\nu,A}\Omega_\nu$ and an exhaustion $(B_k,C_k)$ such that

$$
\lim_{k\to\infty}\sup_\nu
\left\|
(I-P_{\nu,B_k,C_k})v_{\nu,A}
\right\|_\nu=0
$$

in the declared order of limits, with a matching uniform form-tail estimate. The block map must transport local correlations and boundary fibres so that the limiting source span is the full centered local core from (YM260). Finite-word density at each fixed graph is recorded separately from uniform transported density.

### UF-E. Continuum recovery and scale matching

Construct a locally normal continuum representation and a continuum local form core $\mathscr D_{\mathrm{loc},*}$. For every $v$ in that core, provide $v_\nu=f_\nu\Omega_\nu$ with

$$
\|v_\nu\|_\nu\to\|v\|_*;
\qquad
\limsup_{\nu\to\infty}
\langle v_\nu,(H_\nu-E_{0,\nu})v_\nu\rangle_\nu
\le\mathfrak q_*(v,v),
\tag{UF10}
$$

and establish $F_\nu/a_\nu\to m_W\in(0,\infty)$. The form-core closure then gives the conditional continuum lower bound in (YM267), with spectral threshold at least $c_-m_W$.

## 4. Current Feshbach evidence tested against UF-A–UF-E

The following receipts are the current finite evidence inventory. Their classifications are retained exactly; the quantifier column records the obligation coverage required by (UF1).

| Receipt | Observed result | Quantifier coverage |
|---|---|---|
| `runs/yang_mills_4x2x2_c1_feshbach/verification-fresh.json` | `FAIL`, `INCONCLUSIVE`; 407/423 checks, 64/64 positive conditional roots | The 16 failed checks are `row_test_inequality_*_x1`, with $\phi_{\mathrm{test}}$ from $-2.0146598632$ to $-0.7508664577$ (the $xy/xz$ rows also take $-1.3481260325$ and $-1.6769411083$). The receipt scope marks cutoff removal, volume uniformity, lattice-spacing uniformity, continuum recovery and the mass gap `UNRESOLVED`. UF-A–UF-E are open. |
| `runs/yang_mills_interacting_feshbach/verification.json` | `PASS`, `SUPPORTS_FINITE_FESHBACH`; 38/38 checks, 4/4 positive rows | Seven-link two-plaquette graph, finite cutoffs $C_P=1$ to $C_Q=3$, finite $Q$ sector. UF-B and UF-C hold only for the declared matrix rows; UF-A, UF-D and UF-E remain open. |
| `runs/yang_mills_interacting_feshbach_cutoff/verification.json` | `PASS`, `NO_POSITIVE_FAMILY_CERTIFICATE`; 403/403 checks, 36/40 positive rows | Four zero-root rows occur at $x=16$. The finite cutoff family supplies no uniform $C$-exhaustion or trajectory bound. UF-A–UF-E remain open. |
| `runs/yang_mills_interacting_feshbach_cutoff6/verification.json` | `PASS`, `SUPPORTS_FINITE_ADJACENT_FAMILY`; 603/603 checks, 52/60 positive rows and 20/20 adjacent rows | The seven-link graph and finite cutoff family remain fixed. The adjacent-family result supplies finite row arithmetic; UF-A, UF-B, UF-C, UF-D and UF-E remain open at the theorem quantifiers. |
| `runs/yang_mills_volume_translated_block_feshbach/verification.json` | `PASS`, `SUPPORTS_FINITE_TRANSLATED_BLOCK_SWEEP`; 455/455 checks, 44/44 positive rows | All 11 recovered plaquettes are covered at four finite couplings in a finite $C=1$ outer family. Translation coverage is finite; volume, cutoff, spacing and continuum quantifiers remain open. |
| `runs/yang_mills_volume_block_local_feshbach/verification.json` | `PASS`, `SUPPORTS_FINITE_VOLUME_ANCHORED_BLOCK_FAMILY`; 83/83 checks, 8/8 positive rows | Two finite graphs and four couplings are covered. The receipt marks translation uniformity `UNRESOLVED`; UF-B–UF-E remain open. |
| `runs/yang_mills_volume_collective_feshbach/verification.json` | `PASS`, `SUPPORTS_FINITE_VOLUME_COLLECTIVE_PLAQUETTE_FAMILY`; 83/83 checks, 8/8 positive rows | The collective source is a finite arithmetic mode. The receipt marks the local volume-uniform bound `UNRESOLVED`; UF-A–UF-E remain open. |
| `runs/yang_mills_volume_adapted_feshbach_v2/verification.json` | `PASS`, `SUPPORTS_FINITE_VOLUME_RESERVED_PLAQUETTE_FAMILY`; 84/84 checks, 8/8 positive rows | The reserved source family is finite and the volume-uniform bound is `UNRESOLVED`; UF-A–UF-E remain open. |
| `runs/yang_mills_volume_feshbach_bridge/verification.json` | `PASS`, `SUPPORTS_FINITE_VOLUME_FESHBACH_BRIDGE`; 84/84 checks, 8/8 positive rows | The constant-sector bridge is finite and the receipt marks volume uniformity `UNRESOLVED`; UF-A–UF-E remain open. |
| `computations/yang-mills-transport-score-prereg.md` | Gaussian and conditional-transport control protocol | The protocol explicitly limits a finite row to Gaussian controls and states that no finite row proves a volume-uniform Yang–Mills estimate. It supplies an analytic template for recurrence constants, not UF-A–UF-E. |

The independent Feshbach receipts in this inventory are audit artifacts. Their declared scopes do not add UF-A–UF-E or the missing uniform operator estimates.

## 5. Decision rule and stopping rule

A finite implementation may report one of the following:

- `FINITE_ONLY`: all declared matrix, source, resolvent and Schur controls pass for the frozen finite schedule;
- `FINITE_FAIL`: a declared finite inequality or source control fails;
- `INCONCLUSIVE`: an input, identity, residual, source binding or required evidence is absent.

The label `SUPPORTS_YM262` is reserved for a proof package containing UF-A, UF-B, UF-C, UF-D and UF-E with constants and quantifiers stated before execution. A positive finite receipt, including one with translated blocks or many couplings, cannot receive that label by itself.

No new Feshbach receipt is scheduled until an exact block/transfer construction has been written with its boundary fibres, $S$-metric, $P/Q$ domains, the fixed $z$-domain in (UF6), and a proof strategy for the uniform constants in (UF7) and (UF9). If a proposed construction changes the graph trajectory, source family, cutoff order, constants or stopping rule, it requires a new protocol version.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.13, 9.20, 9.33–9.34—vacuum form, conditional recurrence, local completeness and the uniform lower-form criterion.
- `computations/yang-mills-4x2x2-c1-feshbach-prereg.md`—finite translated $4\times2\times2$ screen and its declared evidence boundary.
- `computations/yang-mills-interacting-feshbach-prereg.md`—fixed-graph interacting resolvent and Schur inequalities.
- `computations/yang-mills-transport-score-prereg.md`—conditional $H^{-1}$ transport recurrence and Gaussian controls.
- `computations/verify_yang_mills_continuum_boundary_audit.py` and `runs/yang_mills_continuum_boundary_audit/verification.json`—the hash-bound audit source and its recorded `status: PASS`, `verdict: UNRESOLVED_CONTINUUM_PROBLEM` and `clay_verdict: NULL`; the receipt is source-snapshot-bound and its recorded result is not a current-theorem validation.
