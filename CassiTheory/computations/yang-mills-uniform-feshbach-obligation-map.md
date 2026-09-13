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

### UF-A.1 Conditional boundary-fibre specification

An admissible block map requires a boundary representation construction before any averaging or coarse-variable identification. The following is a conditional specification; it asserts the data and tests required for a map, with no existence claim.

Fix $\nu$ and a finite block $B$ in the lattice graph $\Lambda_\nu$. Split the fine links into block links and exterior links, and let $V_{\partial B}$ be the vertices at which the two parts meet. With

$$
G_{\partial B}:=\prod_{v\in V_{\partial B}}SU(2)_v,
\tag{UFA1}
$$

define the relative fine block Hilbert space by leaving boundary gauge transformations unquotiented:

$$
\mathcal H_{\nu,B}^{\mathrm f}
:=
L^2\!\left(SU(2)^{E_B^{\mathrm f}},dU\right)^{
SU(2)^{V_B\setminus V_{\partial B}}}.
\tag{UFA2}
$$

The measure $dU$ is the product of normalized Haar measures on the block links, and the relative inner product is

$$
\langle F,G\rangle_{\nu,B}^{\mathrm f}
:=
\int_{SU(2)^{E_B^{\mathrm f}}}
\overline{F(U)}G(U)\,dU.
\tag{UFA15}
$$

For $g=(g_v)_{v\in V_{\partial B}}\in G_{\partial B}$, extend $g$ by the identity away from $V_{\partial B}$ and let

$$
(\pi_{\nu,B}^{\mathrm f}(g)F)(U)
:=
F(g^{-1}\!\cdot U),
\qquad
(g\!\cdot U)_e
:=
g_{s(e)}U_eg_{t(e)}^{-1}.
\tag{UFA16}
$$

The action is unitary for (UFA15). Interior Gauss generators annihilate the relative space, while the boundary generators remain as the infinitesimal representation $\pi_{\nu,B}^{\mathrm f}$. The exterior action uses the opposite boundary orientation.

For $\alpha\in\widehat{G_{\partial B}}$, define the isotypic projector and multiplicity space by

$$
\mathsf P_{\nu,B,\alpha}^{\mathrm f}
:=
d_\alpha
\int_{G_{\partial B}}
\overline{\chi_\alpha(g)}\,
\pi_{\nu,B}^{\mathrm f}(g)\,dg,
\qquad
\mathcal M_{\nu,B,\alpha}^{\mathrm f}
:=
\operatorname{Hom}_{G_{\partial B}}
\!\left(V_\alpha,\mathcal H_{\nu,B}^{\mathrm f}\right),
\tag{UFA17}
$$

with the Hilbert inner product inherited from (UFA15) and the standard inner product on $V_\alpha$. Fix a boundary half-edge identification $\iota_{\partial B}$, including orientations and any duplicated cut-link variables. Define the matched tensor space and its Haar/Peter–Weyl contraction by

$$
\begin{aligned}
\mathscr H_{\nu,B|\bar B}^{\mathrm f,\mathrm{match}}
:=
\operatorname{Inv}_{G_{\partial B}}
\left(
\mathcal H_{\nu,B}^{\mathrm f}
\widehat\otimes_{\iota_{\partial B}}
\mathcal H_{\nu,\bar B}^{\mathrm f}
\right),\\
\Gamma_{\nu,B}^{\mathrm f}:&
\mathscr H_{\nu,B|\bar B}^{\mathrm f,\mathrm{match}}
\longrightarrow
\mathcal H_{\nu,\Lambda}^{\mathrm{gi}}.
\end{aligned}
\tag{UFA18}
$$

Here $\widehat\otimes_{\iota_{\partial B}}$ is the Hilbert tensor product after identifying duplicated cut-link variables with the declared orientations, and $\operatorname{Inv}_{G_{\partial B}}$ denotes fixed vectors under the diagonal boundary action. The map $\Gamma_{\nu,B}^{\mathrm f}$ is the Haar/Peter–Weyl contraction of matching $V_\alpha\otimes V_\alpha^*$ factors. UF-A requires proving that this map is a unitary bijection onto $\mathcal H_{\nu,\Lambda}^{\mathrm{gi}}$; that property is not assumed by the specification. On the finite Peter–Weyl core, the boundary condition is equivalently $(G_{\nu,B,v}^A+G_{\nu,\bar B,v}^A)\Psi=0$ for every boundary vertex and Lie-algebra direction. In the remaining equations, $\operatorname{Glue}_{\mathrm f}$ denotes this $\Gamma_{\nu,B}^{\mathrm f}$; the coarse $\operatorname{Glue}_{\mathrm c}$ has the analogous definition.


Peter–Weyl decomposition for the compact boundary group gives

$$
\mathcal H_{\nu,B}^{\mathrm f}
\cong
\widehat{\bigoplus}_{\alpha\in\widehat{G_{\partial B}}}
\mathcal M_{\nu,B,\alpha}^{\mathrm f}\otimes V_\alpha,
\tag{UFA3}
$$

where $\alpha$ contains the boundary representation labels and the multiplicity spaces contain the interior spin-network and intertwiner data. The exterior relative space has the dual boundary factor,

$$
\mathcal H_{\nu,\bar B}^{\mathrm f}
\cong
\widehat{\bigoplus}_{\alpha\in\widehat{G_{\partial B}}}
\mathcal M_{\nu,\bar B,\bar\alpha}^{\mathrm f}\otimes V_\alpha^*.
\tag{UFA4}
$$

The fine physical Hilbert space is obtained by the invariant contraction of $V_\alpha\otimes V_\alpha^*$:

$$
\mathcal H_{\nu,\Lambda}^{\mathrm{gi}}
\cong
\widehat{\bigoplus}_{\alpha}
\mathcal M_{\nu,B,\alpha}^{\mathrm f}
\otimes
\mathcal M_{\nu,\bar B,\bar\alpha}^{\mathrm f}.
\tag{UFA5}
$$

The same construction is required for a proposed coarse block graph, with a declared identification of its boundary gauge group with $G_{\partial B}$. If the coarse and fine boundary groups have different vertex identifications, an explicit intertwiner between the two boundary representations must be supplied before a block map can be defined.

For every $\nu$, block position and boundary sector, the candidate map consists of multiplicity-space maps

$$
J_{\nu,B,\alpha}:
\mathcal M_{\nu,B,\alpha}^{\mathrm c}
\longrightarrow
\mathcal M_{\nu,B,\alpha}^{\mathrm f},
\qquad
J_{\nu,B,\alpha}^*J_{\nu,B,\alpha}=I,
\tag{UFA6}
$$

extended as $J_{\nu,B,\alpha}\otimes I_{V_\alpha}$ on the boundary factor and assembled as a direct sum $J_{\nu,B}$. Boundary covariance requires

$$
(J_{\nu,B,\alpha}\otimes I_{V_\alpha})
\pi_{\nu,B,\alpha}^{\mathrm c}(g)
=
\pi_{\nu,B,\alpha}^{\mathrm f}(g)
(J_{\nu,B,\alpha}\otimes I_{V_\alpha})
\qquad
(g\in G_{\partial B}).
\tag{UFA7}
$$

The exterior map and the block map must preserve the Gauss-law contraction:

$$
\operatorname{Glue}_{\mathrm f}
\circ
\bigl(J_{\nu,B}\otimes J_{\nu,\bar B}\bigr)
=
J_{\nu,\Lambda}
\circ
\operatorname{Glue}_{\mathrm c}
\tag{UFA8}
$$

on every matched boundary sector. Equation (UFA8) is the decisive boundary test. A map obtained by averaging link variables has no UF-A status until it satisfies (UFA7)–(UFA8), including all boundary intertwiners and orientation conventions.

The forms in (UFA9)–(UFA13) are the dimensionless forms of $h_\nu=K_\nu+x_\nu V_\nu$. Their physical forms carry the common factor $g_\nu^2/(2a_\nu)$, so the coupling normalization is applied after the block and boundary tests rather than absorbed into the map.

The form test must include the plaquettes that cross the block boundary. Let $\mathscr D_{\nu,B}^{\mathrm f}\odot\mathscr D_{\nu,\bar B}^{\mathrm f}$ be the finite Peter–Weyl tensor core with matched boundary sectors. The electric terms of links assigned to $B$ and the plaquettes wholly owned by $B$ induce a sesquilinear form $\mathfrak k_{\nu,B}^{\mathrm f,\mathrm{int}}$ on the glued core; the exterior terms induce $\mathfrak k_{\nu,\bar B}^{\mathrm f,\mathrm{int}}$. Their restrictions to the relative block and exterior spaces are denoted by the same symbols with arguments in the corresponding relative spaces. For matched tensors $u\otimes\bar u$ and $v\otimes\bar v$, define

$$
\begin{aligned}
\mathfrak h_{\nu,\Lambda}^{\mathrm f}
\bigl[
\operatorname{Glue}_{\mathrm f}(u\otimes\bar u),
\operatorname{Glue}_{\mathrm f}(v\otimes\bar v)
\bigr]
&=
\mathfrak k_{\nu,B}^{\mathrm f,\mathrm{int}}
[u\otimes\bar u,v\otimes\bar v]\\
&\quad+
\mathfrak k_{\nu,\bar B}^{\mathrm f,\mathrm{int}}
[u\otimes\bar u,v\otimes\bar v]\\
&\quad+
\mathfrak i_{\nu,\partial B}^{\mathrm f}
[u\otimes\bar u,v\otimes\bar v].
\end{aligned}
\tag{UFA9}
$$

The interaction form $\mathfrak i_{\nu,\partial B}^{\mathrm f}$ contains every plaquette multiplication term with support on both sides of the cut. Each link Casimir is assigned to exactly one side by the declared link-ownership convention. A boundary electric or Gauss-law operator generated by the relative construction is included in $\mathfrak i_{\nu,\partial B}^{\mathrm f}$; it is absent only after that absence has been proved. The coarse form has the analogous decomposition with $\mathfrak i_{\nu,\partial B}^{\mathrm c}$.

Equivalently, after fixing an exterior boundary datum $\eta$ in a declared representation sector, the relative form is

$$
\mathfrak h_{\nu,B}^{\mathrm f,\eta}[u,v]
:=
\mathfrak k_{\nu,B}^{\mathrm f,\mathrm{int}}[u,v]
+
\mathfrak i_{\nu,\partial B}^{\mathrm f,\eta}[u,v].
\tag{UFA10}
$$

The datum $\eta$ is an exterior holonomy or boundary operator, rather than a scalar boundary value. A coarse datum $\eta_{\mathrm c}$ and its fine image $\eta_{\mathrm f}$ must be specified by an intertwining rule. The coarse relative form uses the corresponding expression $\mathfrak h_{\nu,B}^{\mathrm c,\eta_{\mathrm c}}[u,v]=\mathfrak k_{\nu,B}^{\mathrm c,\mathrm{int}}[u,v]+\mathfrak i_{\nu,\partial B}^{\mathrm c,\eta_{\mathrm c}}[u,v]$, and (UFA10) must agree with the glued form for every admissible boundary datum.


Let $\mathscr D_{\nu,\Lambda}^{\mathrm c}$ denote the matched coarse finite Peter–Weyl core. The exact-map alternative requires the glued image to lie in the fine form domain and to preserve the full form:

$$
\operatorname{Glue}_{\mathrm f}
\bigl(J_{\nu,B}\otimes J_{\nu,\bar B}\bigr)
\mathscr D_{\nu,\Lambda}^{\mathrm c}
\subseteq
\operatorname{Dom}\mathfrak h_{\nu,\Lambda}^{\mathrm f},
\tag{UFA11}
$$

$$
\mathfrak h_{\nu,\Lambda}^{\mathrm f}
\left[
\operatorname{Glue}_{\mathrm f}(J_{\nu,B}u\otimes J_{\nu,\bar B}\bar u),
\operatorname{Glue}_{\mathrm f}(J_{\nu,B}v\otimes J_{\nu,\bar B}\bar v)
\right]
=
\mathfrak h_{\nu,\Lambda}^{\mathrm c}
\left[
\operatorname{Glue}_{\mathrm c}(u\otimes\bar u),
\operatorname{Glue}_{\mathrm c}(v\otimes\bar v)
\right]
\tag{UFA12}
$$

for every matched finite-core tensor. The same equality may be stated fibrewise using (UFA10), provided it holds for every admissible exterior datum and every boundary sector.

In (UFA13), $\|(u,\bar u)\|_{\mathfrak h_\nu^{\mathrm c}}$ denotes the form norm of the glued vector, namely $\|w\|_{\mathfrak h_\nu^{\mathrm c}}^2=\|w\|^2+\mathfrak h_{\nu,\Lambda}^{\mathrm c}[w,w]$ with $w=\operatorname{Glue}_{\mathrm c}(u\otimes\bar u)$; the fine norm is defined analogously.

If only an approximate transport estimate is available, it must include the glued interaction:

$$
\left|
\mathfrak h_{\nu,\Lambda}^{\mathrm f}
\left[
\operatorname{Glue}_{\mathrm f}(J_{\nu,B}u\otimes J_{\nu,\bar B}\bar u),
\operatorname{Glue}_{\mathrm f}(J_{\nu,B}v\otimes J_{\nu,\bar B}\bar v)
\right]
-
\mathfrak h_{\nu,\Lambda}^{\mathrm c}
\left[
\operatorname{Glue}_{\mathrm c}(u\otimes\bar u),
\operatorname{Glue}_{\mathrm c}(v\otimes\bar v)
\right]
\right|
\leq
\varepsilon_{\nu,B,\alpha}
\|(u,\bar u)\|_{\mathfrak h_{\nu}^{\mathrm c}}
\|(v,\bar v)\|_{\mathfrak h_{\nu}^{\mathrm c}}.
\tag{UFA13}
$$

The limit or summability required of $\varepsilon_{\nu,B,\alpha}$ belongs to the continuum transport obligation. It cannot be silently substituted for the exact fine-space identity in (UF4), (UF7) or (UF9).


For a finite representation cutoff $C$, retain only the declared internal and boundary sectors and form the centered Wilson-word columns in each $\alpha$. Their raw Gram matrix $S_{\nu,B,C,\alpha}$ must be positive on the retained quotient, and the physical columns are $U=S_{\nu,B,C,\alpha}^{1/2}C$. After removing the declared ground subspace, set

$$
P_{\nu,B,C,\alpha}
:=
\operatorname{proj}_{\mathcal K_\nu}
\operatorname{ran}(U_{\nu,B,C,\alpha}),
\qquad
Q_{\nu,B,C,\alpha}
:=
I_{\mathcal K_\nu}-P_{\nu,B,C,\alpha}.
\tag{UFA14}
$$

If the finite-volume ground state is degenerate, centering and ground removal use the declared ground-space density and the entire ground subspace. A single positive vector is sufficient only under a separately established uniqueness statement. The conditional specification is satisfied only after (UFA1)–(UFA18), including the Haar inner product, boundary Gauss constraint, form-domain inclusion and boundary contraction, are proved for the chosen block family. It supplies a testable UF-A target; it supplies no UF-A–UF-E theorem by itself.

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

### UF-B.1 The elementary Casimir bound is non-uniform

The one-link character estimate gives an exact finite-volume form inequality, but its shifted version cannot supply the trajectory-uniform discarded resolvent. Write the dimensionless Hamiltonian and its physical normalization as

$$
h_\nu=K_\nu+x_\nu V_\nu,
\qquad
H_\nu=\frac{g_\nu^2}{2a_\nu}h_\nu,
\qquad
x_\nu=\frac{2}{g_\nu^4},
\qquad
0\leq V_\nu\leq4N_{p,\nu}I.
\tag{UF-B.1a}
$$

For a finite link set $S$, let $P_{C,S}$ and $Q_{C,S}$ be the character projectors in (UF2)–(UF3), and let

$$
\kappa_C=\frac{(C+1)(C+3)}4.
$$

Commutativity of the link Casimirs gives the exact operator inequality

$$
Q_{C,S}K_\nu Q_{C,S}\succeq\kappa_CQ_{C,S}.
\tag{UF-B.2a}
$$

If $e_{0,\nu}$ is the lowest eigenvalue of $h_\nu$, then positivity of $V_\nu$ yields

$$
Q_{C,S}(h_\nu-e_{0,\nu})Q_{C,S}
\succeq
(\kappa_C-e_{0,\nu})Q_{C,S}.
\tag{UF-B.3a}
$$

The constant gauge-invariant wavefunction is a variational state with zero electric energy and plaquette expectation $2$, so

$$
e_{0,\nu}\leq2x_\nu N_{p,\nu}.
\tag{UF-B.4a}
$$

Consequently the elementary estimate certifies only

$$
Q_{C,S}Y_\nu Q_{C,S}
\succeq
\frac{g_\nu^2}{2F_\nu}
\left(\kappa_C-2x_\nu N_{p,\nu}\right)Q_{C,S},
\qquad
Y_\nu=\frac{a_\nu}{F_\nu}(H_\nu-E_{0,\nu}).
\tag{UF-B.5a}
$$

It gives a positive discarded-sector margin only when $\kappa_C>2x_\nu N_{p,\nu}$. On the frozen trajectory in §1, $N_{p,\nu}=3L_\nu^3$ and $L_\nu=\Theta(F_\nu^{-2})$. Since

$$
x_\nu N_{p,\nu}
=\Theta\!\left(g_\nu^{-4}F_\nu^{-6}\right)
=\Theta\!\left(\nu^{\,2-6p}e^{3\nu/b_0}\right),
\qquad
b_0=\frac{11}{24\pi^2},
\qquad
p=\frac{51}{121}.
$$

while every polynomial cutoff $C_\nu=O(\nu^r)$ has $\kappa_{C_\nu}=O(\nu^{2r})$, the ratio

$$
\frac{\kappa_{C_\nu}}{2x_\nu N_{p,\nu}}
\longrightarrow0.
\tag{UF-B.6a}
$$

A log-domain evaluation of (UF-B.5) with the illustrative polynomial schedule $C_\nu=\nu^3$ gives:

| $\nu$ | $C_\nu$ | $\log_2L_\nu$ | $\log_{10}\!\left[\kappa_{C_\nu}/(2x_\nu N_{p,\nu})\right]$ | certified sign |
|---:|---:|---:|---:|:---|
| 1 | 1 | 274 | $-250.133$ | negative |
| 2 | 8 | 305 | $-277.128$ | negative |
| 4 | 64 | 367 | $-331.635$ | negative |
| 8 | 512 | 490 | $-441.182$ | negative |
| 16 | 4096 | 738 | $-663.697$ | negative |
| 32 | 32768 | 1235 | $-1111.171$ | negative |

This is a counter-obstruction to the elementary Casimir-plus-extensive-ground-energy proof route, not a counterexample to UF-B itself. The true discarded resolvent estimate must control $h_\nu-e_{0,\nu}$ directly on the $Q$ sector, including the vacuum-energy cancellation and every block-boundary and fibre interaction. The fixed-support local cutoff theorem supplies neither this cancellation nor that boundary and fibre control; it therefore cannot discharge UF-B or UF-C along the continuum trajectory.

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

- `foundations/loop-to-bubble-projection-theorem.md` §§9.13, 9.20, 9.25–9.26, 9.30, 9.33–9.34—vacuum form, finite character bounds, scale matching, local completeness and the uniform lower-form criterion.
- `computations/yang-mills-4x2x2-c1-feshbach-prereg.md`—finite translated $4\times2\times2$ screen and its declared evidence boundary.
- `computations/yang-mills-interacting-feshbach-prereg.md`—fixed-graph interacting resolvent and Schur inequalities.
- `computations/yang-mills-transport-score-prereg.md`—conditional $H^{-1}$ transport recurrence and Gaussian controls.
- `computations/verify_yang_mills_continuum_boundary_audit.py` and `runs/yang_mills_continuum_boundary_audit/verification.json`—the hash-bound audit source and its recorded `status: PASS`, `verdict: UNRESOLVED_CONTINUUM_PROBLEM` and `clay_verdict: NULL`; the receipt is source-snapshot-bound and its recorded result is not a current-theorem validation.
