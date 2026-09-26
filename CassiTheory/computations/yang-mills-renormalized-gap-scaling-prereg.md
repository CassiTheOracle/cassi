# Renormalized $SU(2)$ Gap and Volume Scaling Criterion

## Status: Pre-registered analytic diagnostic—September 2026

## Abstract

This protocol fixes the universal two-loop weak-coupling scale for four-dimensional pure $SU(2)$ Wilson lattice gauge theory and translates it into the Hamiltonian convention used in `foundations/loop-to-bubble-projection-theorem.md`. It separates three quantities that must be controlled on one trajectory: removal of the lattice spacing, divergence of the physical spatial volume, and convergence of a dimensionless lattice gap to a finite positive mass in renormalization-group units.

The executable work is an arithmetic and convention diagnostic. It can reject scale-incompatible volume or gap schedules, but it neither computes an interacting Yang–Mills gap nor constructs a continuum quantum field. The conditional bridge stated below additionally requires nontrivial convergent gauge-invariant Schwinger functions, the Osterwalder–Schrader hypotheses, restored Euclidean covariance and a uniform interacting spectral or correlation estimate. None of those hypotheses is established by this protocol. The Clay verdict is `NULL` under every executable outcome.

## 1. Wilson two-loop scale

Let $g_0=g_W$ denote the bare coupling of the standard isotropic $SU(2)$ Wilson action, with

$$
\beta_{\rm lat}=\frac{4}{g_0^2}.
\tag{YMR1}
$$

Use the beta-function convention

$$
\beta_L(g_0)
:=-a\frac{d g_0}{da}\bigg|_{g_R,\mu}
=-b_0g_0^3-b_1g_0^5+O(g_0^7).
\tag{YMR2}
$$

For pure $SU(N)$,

$$
b_0=\frac{11N}{48\pi^2},
\qquad
b_1=\frac{34N^2}{3(16\pi^2)^2}.
\tag{YMR3}
$$

Thus, for $SU(2)$,

$$
\boxed{
b_0=\frac{11}{24\pi^2},
\qquad
b_1=\frac{17}{96\pi^4},
\qquad
p:=\frac{b_1}{2b_0^2}=\frac{51}{121}.
}
\tag{YMR4}
$$

Integrating (YMR2) fixes the universal two-loop factor

$$
\boxed{
F_W(g_0)
:=\exp\!\left[-\frac{1}{2b_0g_0^2}\right]
(b_0g_0^2)^{-p}.
}
\tag{YMR5}
$$

A Wilson-scheme continuum trajectory has

$$
a\Lambda_L=F_W(g_0)\,[1+O(g_0^2)].
\tag{YMR6}
$$

Equivalently,

$$
\boxed{
F_W(\beta_{\rm lat})
=\exp\!\left[-\frac{3\pi^2}{11}\beta_{\rm lat}\right]
\left(\frac{6\pi^2}{11}\beta_{\rm lat}\right)^{51/121}.
}
\tag{YMR7}
$$

All executable evaluations use the log-stable forms

$$
\begin{aligned}
\ell_W(g_0^2)&:=\log F_W
=-\frac{1}{2b_0g_0^2}-p\log(b_0g_0^2),\\
\ell_W(\beta_{\rm lat})
&=-\frac{3\pi^2}{11}\beta_{\rm lat}
+p\log\!\left(\frac{6\pi^2}{11}\beta_{\rm lat}\right).
\end{aligned}
\tag{YMR8}
$$

The derivative of the two-loop factor gives

$$
\frac{d\ell_W}{dg_0}
=\frac{1}{b_0g_0^3}-\frac{2p}{g_0},
\qquad
-\left(\frac{d\ell_W}{dg_0}\right)^{-1}
=-\frac{b_0g_0^3}{1-(b_1/b_0)g_0^2}.
\tag{YMR9}
$$

Consequently the last expression equals
$-b_0g_0^3-b_1g_0^5+O(g_0^7)$. This derivative identity is a convention check, not evidence for nonperturbative spectral behavior. Higher-order and nonperturbative corrections to (YMR6) are outside the executable claim.

## 2. Hamiltonian convention map

The fixed-graph transfer result uses the Hamiltonian coupling $g_H$ and target time $\epsilon$. Its exact fixed-regulator map to the Wilson convention is

$$
\boxed{
g_W=2^{1/4}g_H,
\qquad
a_\tau=\frac{\epsilon}{\sqrt2},
\qquad
H_H(g_H)=\frac{1}{\sqrt2}H_W(2^{1/4}g_H).
}
\tag{YMR10}
$$

The corresponding two-loop spatial scale is therefore

$$
\boxed{
F_H(g_H)
:=F_W(2^{1/4}g_H)
=\exp\!\left[-\frac{6\sqrt2\pi^2}{11g_H^2}\right]
\left(\frac{12\sqrt2\pi^2}{11g_H^2}\right)^{51/121}.
}
\tag{YMR11}
$$

For a physical spectral gap write

$$
\delta_W:=a\Delta_W,
\qquad
\delta_H:=a\Delta_H=\frac{\delta_W}{\sqrt2}.
\tag{YMR12}
$$

If the dimensionless gauge-invariant eigen-gap is defined after extracting the respective electric prefactor,

$$
\delta_W=\frac{g_W^2}{2}\widehat\Delta_W,
\qquad
\delta_H=\frac{g_H^2}{2}\widehat\Delta_H,
\tag{YMR13}
$$

then (YMR10)–(YMR12) imply the exact convention identity

$$
\boxed{\widehat\Delta_H(g_H)=\widehat\Delta_W(2^{1/4}g_H).}
\tag{YMR14}
$$

No spectrum is equated across different regulators or volumes by this identity.

## 3. Simultaneous continuum and thermodynamic scaling

Let $N(g_0)$ be the linear spatial site count, so the physical linear size is $R=N a$. Along (YMR6),

$$
R\Lambda_L=N(g_0)F_W(g_0)\,[1+O(g_0^2)].
\tag{YMR15}
$$

The simultaneous infinite-volume continuum requirement is

$$
\boxed{
g_0\longrightarrow0,
\qquad
N(g_0)F_W(g_0)\longrightarrow\infty.
}
\tag{YMR16}
$$

A fixed $N$, or any $N$ growing only as a power of $1/g_0$, makes $R\Lambda_L\to0$. A schedule $N\asymp F_W^{-1}$ retains only a fixed physical box. The following two schedules do reach infinite volume:

$$
N_{\rm th,1}\asymp\frac{1}{g_0^2F_W(g_0)},
\qquad
N_{\rm th,2}\asymp\frac{\log(1/F_W(g_0))}{F_W(g_0)}.
\tag{YMR17}
$$

Ceilings to integer site counts do not change these limits. For a Euclidean lattice, every extent used to define the infinite-volume theory must separately satisfy $N_\mu F_W\to\infty$. The fixed-$\beta$ thermodynamic subsequence and the fixed-graph anisotropic transfer limit established earlier do not supply (YMR16).

## 4. Renormalized gap criterion

For a finite-volume lattice gap $\delta_W(g_0,N)=a\Delta_W(g_0,N)$, its value in lattice-$\Lambda$ units is

$$
\boxed{
\frac{\Delta_W}{\Lambda_L}
=\frac{\delta_W}{a\Lambda_L}
=\frac{\delta_W}{F_W(g_0)}[1+O(g_0^2)].
}
\tag{YMR18}
$$

A finite positive continuum excitation scale therefore requires, on the same trajectory as (YMR16),

$$
\boxed{
0<c_-
\leq\liminf_{g_0\to0}\frac{\delta_W(g_0,N(g_0))}{F_W(g_0)}
\leq\limsup_{g_0\to0}\frac{\delta_W(g_0,N(g_0))}{F_W(g_0)}
\leq c_+<\infty.
}
\tag{YMR19}
$$

The positive lower bound is the gap-scale requirement. The finite upper witness must come from at least one nonzero centered local gauge-invariant channel; it prevents a putative limit with no finite-energy local excitation from being mislabeled as a nontrivial massive theory. If a single mass limit exists, (YMR19) sharpens to $\delta_W/F_W\to m_*/\Lambda_L\in(0,\infty)$.

In the Hamiltonian factorization (YMR13), the same condition reads

$$
\widehat\Delta_W(g_0,N(g_0))
\asymp\frac{2F_W(g_0)}{g_0^2},
\tag{YMR20}
$$

with the proportionality bounded above and below by positive constants. A nonzero constant lattice gap, any power-law lattice gap, and the isolated-square asymptotic $a\Delta_H\to2\sqrt2$ all give $\delta/F\to\infty$; they are ultraviolet-scale gaps rather than finite continuum masses. A schedule $\delta=F_Wg_0^2$ gives $\delta/F_W\to0$ and cannot supply a positive mass gap.

## 5. Conditional continuum bridge

Consider a full sequence of four-dimensional $SU(2)$ Wilson lattices satisfying (YMR6) and (YMR16). Assume all of the following, none of which follows from the scale arithmetic:

1. renormalized gauge-invariant local Schwinger functions converge along the full sequence and define a nontrivial limit;
2. the limiting functions satisfy the Osterwalder–Schrader axioms, restore Euclidean covariance and have the required short-distance asymptotically free behavior;
3. centered local gauge-invariant transfer correlations obey a volume- and regulator-uniform exponential bound at rate at least $c_-\Lambda_L$;
4. at least one nonzero centered local gauge-invariant channel has spectral support at or below $c_+\Lambda_L$.

Osterwalder–Schrader reconstruction then gives a nontrivial relativistic quantum field whose vacuum-sector spectrum has a finite positive mass gap in $[c_-,c_+]\Lambda_L$. This is a conditional implication organizing the remaining proof obligations. Establishing its hypotheses for interacting four-dimensional Yang–Mills theory is the unsolved work.

## 6. Frozen executable schedule

The primary and independent implementations use exactly

$$
g_0^2\in\{0.8,0.5,0.3,0.2,0.1,0.05\}.
\tag{YMR21}
$$

For each of the six rows they independently compute $\ell_W$ from both forms in (YMR8), $F_W=\exp(\ell_W)$, the exact Hamiltonian-map value in (YMR11), the derivative beta value in (YMR9), and the following idealized log-domain schedules:

| Schedule | Definition | Required classification |
|---|---|---|
| fixed volume count | $N=64$ | $NF_W\to0$ |
| polynomial volume count | $N=g_0^{-8}$ | $NF_W\to0$ |
| fixed physical box | $N=8F_W^{-1}$ | $NF_W=8$ |
| thermodynamic 1 | $N=(g_0^2F_W)^{-1}$ | $NF_W=g_0^{-2}\to\infty$ |
| thermodynamic 2 | $N=\log(1/F_W)F_W^{-1}$ | $NF_W=\log(1/F_W)\to\infty$ |
| constant gap | $\delta=1/4$ | $\delta/F_W\to\infty$ |
| polynomial gap | $\delta=g_0^6$ | $\delta/F_W\to\infty$ |
| subscale gap | $\delta=F_Wg_0^2$ | $\delta/F_W\to0$ |
| matched gap | $\delta=(7/4)F_W$ | $\delta/F_W=7/4$ |
| isolated-square control | $\delta_H=2\sqrt2$ | $\delta_H/F_H\to\infty$ |

Each row has exactly ten checks:

1. the two Wilson log-scale formulas agree within $2\times10^{-13}$;
2. $F_W$ is finite and strictly between zero and one on the frozen grid;
3. the direct and Hamiltonian-mapped log scales agree within $2\times10^{-13}$;
4. the exact derivative expression in (YMR9) agrees with its rational form within $2\times10^{-13}$ relative error;
5. the fixed-box product equals $8$ in the log domain within $2\times10^{-13}$;
6. the first thermodynamic product equals $g_0^{-2}$ within $2\times10^{-13}$ in logarithms;
7. the second thermodynamic product equals $\log(1/F_W)$ within $2\times10^{-13}$ in logarithms;
8. the matched gap ratio equals $7/4$ within $2\times10^{-13}$;
9. (YMR12)–(YMR14) agree for the synthetic value $\widehat\Delta=13/10$ within $2\times10^{-13}$;
10. all row values are finite.

Exactly twenty top-level checks cover: the three $SU(2)$ coefficients in (YMR4); the Wilson-$\beta_{\rm lat}$ exponent and power; strict decrease of $F_W$ along the ordered schedule; the derivative remainder being $O(g_0^7)$ with its exact coefficient; both collapsing-volume classifications; the fixed-box classification; both thermodynamic classifications; the constant, polynomial, subscale, matched and isolated-square gap classifications; full Hamiltonian-map agreement; firing controls; exact row and check counts; finite numeric payloads; source bindings; and the declared claim boundary. The primary total is therefore exactly $6\times10+20=80$ checks.

Trend decisions use the ordered schedule as printed in (YMR21), from larger to smaller $g_0^2$. They require strict monotonicity with no numerical floor. Limit classifications are justified analytically by (YMR5), not inferred from six samples; the sample trends only verify that the implementation realizes the frozen formulas.

## 7. Firing controls

All six mutations must activate their intended rejection:

1. omitting the power $(b_0g_0^2)^{-p}$ fails the two-loop power-coefficient check;
2. inserting the pure-$SU(3)$ value of $b_0$ fails the frozen $SU(2)$ coefficient check;
3. labeling $N=8F_W^{-1}$ as thermodynamic fails the required divergence of $NF_W$;
4. labeling the constant lattice gap $\delta=1/4$ as a finite continuum mass fails the finite upper bound in (YMR19);
5. replacing $g_W=2^{1/4}g_H$ by $g_W=2^{-1/4}g_H$ fails the Hamiltonian/Wilson scale identity;
6. replacing $\delta_H=\delta_W/\sqrt2$ by $\delta_H=\delta_W$ fails the gap-normalization identity.

The receipt records an attempted comparison count for every family whose passing result is a zero residual. A firing control passes only when the corresponding unmutated check passes and the mutation makes that same check fail.

## 8. Frozen implementations and decision contract

The primary implementation is
`computations/verify_yang_mills_renormalized_gap_scaling.py`.
It uses only the Python standard library and writes
`runs/yang-mills-renormalized-gap-scaling/verification.json`.

The independent implementation is
`computations/verify_yang_mills_renormalized_gap_scaling_independent.mjs`.
It uses only Node built-ins, imports no primary code, derives the coefficient and schedule formulas separately, and writes
`runs/yang-mills-renormalized-gap-scaling/verification-independent.json`.
It reconstructs all six primary rows and contains exactly 20 decision checks covering the primary schema and counts, protocol and source bindings, coefficient reconstruction, row reconstruction, every volume and gap classification, the Hamiltonian map, derivative residual, all six firing controls, finite payloads and the claim boundary.
Independent numeric reconstruction tolerance is $5\times10^{-13}$ in absolute or scale-normalized relative error.

Both receipts bind the protocol and current source files by SHA-256. The independent receipt additionally binds the primary receipt. Neither implementation overwrites an existing receipt without `--replace`. A primary `PASS` requires all 80 checks; an independent `PASS` requires all 20 independent checks. Any failed arithmetic, trend, count, source-binding, mutation or claim-boundary check gives `FAIL`.

Every receipt records:

- `two_loop_scaling_arithmetic=PASS` only when its executable checks pass;
- `double_scaling_necessity_diagnostic=PASS` only when its executable checks pass;
- `conditional_continuum_bridge_analytic=true`;
- `analytic_theorem_outside_executable=true`;
- `interacting_gap_computed=false`;
- `continuum_trajectory_constructed=false`;
- `thermodynamic_limit_constructed=false`;
- `os_axioms_established=false`;
- `euclidean_covariance_restored=false`;
- `nontrivial_continuum_limit_established=false`;
- `volume_uniform_mass_gap_established=false`;
- `continuum_mass_gap_established=false`;
- `clay_verdict=NULL`.

The first two values become `FAIL` if an executable fails; all remaining negative scope fields and the Clay verdict are invariant. Execution stops after one primary and one independent run. A failed run is diagnosed before a replacement receipt is produced.

## 9. Sources

- B. Allés, A. Feo and H. Panagopoulos, [*The three-loop beta function in $SU(N)$ lattice gauge theories*](https://arxiv.org/abs/hep-lat/9609025), Eqs. (1.1), (2.11) and (3.5)—lattice beta-function convention, universal coefficients and integrated lattice scale.
- W. E. Caswell, [*Asymptotic Behavior of Nonabelian Gauge Theories to Two-Loop Order*](https://doi.org/10.1103/PhysRevLett.33.244), *Physical Review Letters* **33** (1974), 244–246—the two-loop non-Abelian beta function.
- D. R. T. Jones, [*Two-loop diagrams in Yang–Mills theory*](https://doi.org/10.1016/0550-3213(74)90093-5), *Nuclear Physics B* **75** (1974), 531–538—independent two-loop Yang–Mills calculation.
- A. Hasenfratz and P. Hasenfratz, [*The connection between the lambda parameters of lattice and continuum QCD*](https://doi.org/10.1016/0370-2693(80)90118-5), *Physics Letters B* **93** (1980), 165–168—lattice/continuum scheme-scale relation.
- A. Jaffe and E. Witten, [*Quantum Yang–Mills Theory*](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), §4—continuum existence, axiomatic and mass-gap obligations.
- `computations/yang-mills-anisotropic-hamiltonian-limit-prereg.md`—fixed-regulator Wilson/Hamiltonian coupling-and-time convention map.
