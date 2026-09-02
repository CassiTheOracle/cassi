# The Cascade Suppression Formula: $\varphi^{-N}$ as a Conditional Attenuation Relation

## Status: Derived (coherence exponent; conditional product algebra); uniform $\varphi^{-1}$ attenuation is a declared cascade input, its Yang-fraction identity is exact, and signal-map and routed-port interpretations are Hypothesized—September 2026

## Abstract

For selected phenomena in the Cassi framework, the **cascade suppression
factor** supplies a conditional model. Documented examples include proton
stability, the strong CP angle, the electroweak hierarchy, neutrino masses, and
quantum measurement. For a declared cascade
family, a quantity assigned to source cascade step $m$ and target cascade step $n$ is attenuated
according to the cascade span $N = n - m$ and the selected per-step input:

$$\boxed{\mathcal{D}_{m \to n} = \prod_{i=m}^{n-1} d_i}$$

where $d_i$ is the declared per-step attenuation input at cascade step $i$. The canonical
two-density PDE evolves nonnegative real densities $E_Y,E_I$ under shared advection
and gated rank-one local conversion at each cascade step. Its shared advection gives a
common local velocity; a Yang-outward/Yin-inward direction or distinct carrier
velocities are a separate Hypothesized phenomenological/constitutive assignment.
Any propagation, carrier assignment, reabsorption, or interscale-transport
interpretation uses that separate map. The product algebra below is Derived
conditional on the selected attenuation input. The q-gated rank-one form is
the selected canonical/theory form. In code, `TwoFluid3DGPU.rhs` is ungated,
while `ExpandingTwoFluid3DGPU` defaults to `qi_gate=False` and applies the
gate only when explicitly enabled with `qi_gate=True`; record `lambda`,
`qi_gate`, `gate_model`, and `qi_memory` for an implementation receipt. Two
attenuation families cover the documented applications:

- **Uniform attenuation family (Hypothesized signal map)** ($d_i^{\text{signal}} \equiv \varphi^{-1}$ uniform): $\mathcal{D} = \varphi^{-N}$—linear in span. Under the separate map, it applies to CP violation, hierarchy, neutrino masses, and any phenomenon assigned a source-to-target coupling across the cascade.

- **Coherence maintenance (conditional cascade dephasing profile)** ($d_i^{\text{coherence}} = (1-q_i^{\mathrm{cascade}}) = \varphi^{-i-\delta}$): $\mathcal{D} = \varphi^{-n(n+1)/2 - \delta(n+1)}$—quadratic in depth. Applies to proton stability and any phenomenon requiring simultaneous coherence across all supporting scale layers.

The attenuation relation is specified by declared cascade families/inputs. The
coherence-regime factor $(1-q_i^{\mathrm{cascade}})$ is a conditional auxiliary
input; its product exponent is Derived conditional on the declared profile. The
uniform $\varphi^{-1}$ factor is a declared input whose Yang-fraction identity is
exact. Conditional on those inputs, the product establishes $\varphi^{-N}$ as the
conditional attenuation relation for the declared family and supplies a shared
algebraic form for modeled cases. Signal-map interpretations remain
Hypothesized.

`foundations/interscale-stress-attenuation-boundary.md` supplies one explicit
Hypothesized realization of the uniform family. Its time-completed quadratic
branch fixes the canonical boundary flux and a unitary endpoint family. Under
the Hypothesized Yang/Yin species-port identification, the frozen charged
endpoint background supplies a gauge-covariant Hermitian rail-rail Hessian.
A dressed quarter-turn phase and selected coupling ratio realize the golden
matrix at one design wave number. Requiring the same unbiased proton current
to remain below endpoint capacity with positive fixed-amplitude phase
stiffness gives the conditional bound $k_\star>0.0964640362$. The endpoint
background, trace normalization, dressed phase, and matching point remain
inputs. With complementary return ports separately routed away from coherent
re-entry, the branch yields $\varphi^{-N}$ for a quadratic forward flux.
Reciprocal stress transfer, self-adjoint endpoint matching, and closed coherent
propagation obey distinct composition laws.

**Index extension:** The per-step attenuation formulas in §1 are parameterized for
$n \geq 0$ (Planck → observable scales). Extending the index to sub-Planckian
scales ($n < 0$) uses `foundations/microcascade-mirror.md`.

---

## 1. Local two-fluid damping and cascade attenuation inputs

### 1.1 The per-step attenuation $d_i$

At cascade step $i$, the local field is described by the two-fluid PDE with
the conversion term coupling $E_Y$ and $E_I$:

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$

Any departure from the $\varphi$-equilibrium ($E_Y \neq \varphi E_I$) is
**locally damped** by the conversion term. The damping rate at cascade step $i$
is set by the effective coupling strength at that scale.

The conditional cascade dephasing profile $q_i^{\mathrm{cascade}}$ is an auxiliary
scale-indexed quantity, distinct from the canonical local scalar coherence $q$.
It supplies the position-dependent family below. The uniform family used when a
separate map assigns source-to-target signal amplitudes is a declared input
(§1.2):

$$q_i^{\mathrm{cascade}} = 1 - \varphi^{-i-\delta}, \qquad \delta = 3 \text{ (from } \sigma = \ell_{\text{Pl}}/\varphi^3\text{)}$$

### 1.2 Uniform attenuation family (Hypothesized signal map)

For an application with a separate Hypothesized phenomenological/constitutive
map assigning a physical signal—a coupling constant, a CP-violating phase, a mass
scale—between cascade steps, the map uses a uniform attenuation family. Its
per-step factor $d_i^{\text{signal}}$ is the fraction of the signal that survives passage
through cascade step $i$ under that map:

An auxiliary source-plus-floor profile is:

$$d_i^{\text{source+floor}} \equiv 1 - q_i^{\mathrm{cascade}} + \varphi^{-1} = \varphi^{-i-\delta} + \varphi^{-1}$$

For all cascade steps $i \ge 1$ (everywhere except the Planck core), this auxiliary
profile is dominated by its $\varphi^{-1}$ term. The exact uniform signal family
used in source-to-target products is:

$$\boxed{d_i^{\text{signal}} \equiv \varphi^{-1}}$$

The $\varphi^{-1}$ term is the attractor Yang fraction
$\varphi/(1+\varphi) = \varphi^{-1}$—the fixed-point density split
(§4)—and fixes the exact uniform input. The auxiliary source-plus-floor profile
records the $(1-q_i^{\mathrm{cascade}})$ coherence contribution alongside that
calibration. Only $d_i^{\text{signal}}$ enters the source-to-target product,
which is Derived conditional on this input and on the Hypothesized map. Any
directional interscale propagation, Yang-outward/Yin-inward direction, or
distinct carrier velocities are supplied by that map; the canonical PDE's shared
advection and conversion terms describe the local two-density dynamics. Any
reabsorption or re-locking reading is likewise part of the Hypothesized
constitutive map.

Conditional on that declared input and map, the total attenuation over $N$ indexed cascade steps is the product:

$$\mathcal{D}_{m \to n}^{\text{signal}} = \prod_{i=m}^{n-1} \varphi^{-1} = \varphi^{-(n-m)} = \varphi^{-N}$$

### 1.3 Coherence maintenance: position-dependent damping

When a condensed standing wave must maintain **simultaneous coherence**
across all its supporting scale layers, the per-step noise fraction
$(1-q_i^{\mathrm{cascade}})$ sets the probability that scale step $i$ fails during one wave cycle:

$$d_i^{\text{coherence}} = (1-q_i^{\mathrm{cascade}}) = \varphi^{-i-\delta}$$

This is **position-dependent**: scale steps near Planck are far more coherent
($d_i^{\text{coherence}} \ll \varphi^{-1}$) than the uniform-family attenuation input.

For an integer endpoint $N\in\mathbb{Z}_{\ge0}$, the total failure
probability over the indexed range from Planck, $i=0$, to the particle,
$i=N$, is:

$$\mathcal{D}_{0 \to N}^{\text{coherence}} = \prod_{i=0}^{N}
(1-q_i^{\mathrm{cascade}}) = \varphi^{-\sum_{i=0}^{N}(i+\delta)}
= \varphi^{-N(N+1)/2 - \delta(N+1)}$$

This discrete product and finite sum are literal only for integer endpoints.
For the registered two-decimal proton coordinate
$N_p^{\mathrm{budget}}=91.46$, no discrete product with a noninteger upper
bound is implied. The coherence-budget model continues the closed quadratic
exponent:

$$
\mathcal{D}_{0\to N_p}^{\mathrm{coherence}}
:=\varphi^{-N_p(N_p+1)/2-\delta(N_p+1)}
\big|_{N_p=91.46}
=\varphi^{-4505.5758}
\approx\varphi^{-4506}.
$$

The floor convention for an integer comparison is
$\lfloor N_p\rfloor=91$. The declared profile assigns
$\varphi^{-i-\delta}$ to each scale step, with $\delta=3$ from
$\sigma=\ell_{\mathrm{Pl}}/\varphi^3$. Interpreting the product as a failure
probability requires independent simultaneous step failures. Converting the
result to $10^{910}$ years further requires one transition trial per Compton
cycle. These stochastic inputs are Hypothesized; see
`foundations/proton-coherence-budget.md`.

---

## 2. The two regimes, side by side

| Regime | $d_i$ | $\mathcal{D}_{m \to n}$ | Exponent | Physical meaning |
|---|---|---|---|---|
| **Signal propagation (Hypothesized map)** | $\varphi^{-1}$ | $\varphi^{-N}$ | Linear in $N$ | Under the separate map, a signal assigned across $N$ cascade steps receives $\varphi^{-N}$; the product parameterizes damping of non-$\varphi$ structure at a fixed rate per indexed step. |
| **Coherence budget** | $\varphi^{-i-\delta}$ | $\varphi^{-n(n+1)/2-\delta(n+1)}$ | Quadratic in $n$ | Under the Hypothesized independent-step failure model, every included scale layer participates in one simultaneous trial. |

---

## 3. All applications in one table

| Phenomenon | Regime | Seed cascade step | Target cascade step | Span $N$ | $\mathcal{D}$ | Result | Status |
|---|---|---|---|---|---|---|---|
| **Hierarchy** ($v_0/M_{\text{Pl}}$) | Signal (Hypothesized map) | $n_{\text{GUT}} \approx 13.3$ (GUT anchor) | $n_{\text{EW}} \approx 80$ | $66.7$ | $\varphi^{-66.7}$ | $10^{-14}$ (cf. $10^{-17}$; the $N \approx 80$ consistency check of `foundations/dimensionful-cascade.md` §2.1 uses the gap factor $g$) | Derived conditional on declared input; exponent **Mapped** (ledger row 499) |
| **Strong CP** ($\bar{\theta}$) | Signal (Hypothesized map) | $n_{\text{GUT}} \approx 13.3$ with Mapped seed $\delta_{\text{CP}}=\pi\varphi^{-2}$ | $n_{\text{QCD}} = 94.7$ | $81.4$ | $\pi\varphi^{-2}\times\varphi^{-81.4}=\pi\varphi^{-83.4}$ | $\bar{\theta} \approx 1.2\times10^{-17}$ | Derived conditional on declared input and Mapped seed |
| **Neutrino masses** | Signal (Hypothesized map) | $n_{\text{GUT}} \approx 13.3$ (GUT-scale Yukawa seed) | $n_{\text{seesaw}} \approx 20$ | $N_\nu = 20 - 13.3 \approx 6.7 \approx 7$ | $\varphi^{-N_\nu}\approx\varphi^{-6.7}$ (flavor exponents $\varphi^{-12}$ to $\varphi^{-25}$) | $m_\nu \sim 0.001$–$0.1$ eV | Hypothesized (signal map and scale-step assignment; flavor offsets Mapped) |
| **Proton conditional cycle budget** | Coherence | $n=0$ (Planck) | $N_p^{\mathrm{budget}}=91.46$ | $91.46$ | $\varphi^{-4505.5758}\approx\varphi^{-4506}$ | $\sim10^{942}$ modeled cycles; physical rate open | Derived conditional arithmetic under the declared $q_i^{\mathrm{cascade}}$ profile; stochastic and trial-frequency maps Hypothesized |
| **Spin ($s = \Delta n/2$)** | Geometric |—|—| $\Delta n \in \{0,1,2,4\}$ | N/A (conserved winding) | $s \in \{0,\frac12,1,2\}$ | Hypothesized |

The hierarchy, strong CP, and neutrino masses use the **Hypothesized
phenomenological/constitutive signal map** from the GUT scale. Under that
declared map, different targets give different observed suppressions, and the
conditional products follow $\varphi^{-N}$ with zero additional free parameters.

Spin supplies a geometric limiting label through $\Delta n$ (conserved
doublet winding, $s=\Delta n/2$;
`foundations/spin-fibonacci-spiral.md` §2.1). Quantum measurement follows the
regulated configuration-space construction in
`foundations/quantum-measurement-derivation.md`.

---

## 4. Why $\varphi^{-1}$ per cascade step? Declared calibration and phenomenological reading

The per-step factor is the declared calibration input of the attenuation
family. Its in-framework algebraic identity is exact: at the
$\varphi$-attractor, the Yang component has an energy-density fraction
$\varphi^{-1}$. Interpreting this density fraction as transport attenuation
between cascade steps requires a separate Hypothesized phenomenological/constitutive map.

At the fixed point $E_Y = \varphi E_I$ the Yang component has

$$\frac{E_Y}{E_Y + E_I} = \frac{\varphi}{1+\varphi} = \frac{\varphi}{\varphi^2} = \varphi^{-1}$$

of the total density (ledger rows 500/453: the fixed-point Yang density fraction is $\varphi^{-1}$, and $\alpha_w = r/(1+r)$ at $r = \varphi$). This identity characterizes the local fixed-point density split. A separate Hypothesized phenomenological/constitutive map assigns any expansive, structure-carrying, or propagating role to Yang and any restorative or reabsorption role to Yin. That map may also specify a re-locking event at each cascade step. Under this constitutive reading, one indexed step applies the declared factor $\varphi^{-1}$, and over $N$ steps

$$\boxed{\mathcal{D}^{\text{signal}}_{m \to n} = \prod_{i=m}^{n-1} \varphi^{-1} = \varphi^{-(n-m)} = \varphi^{-N}}$$

The alternative constitutive crossing models yield calibration values distinct
from $\varphi^{-1}$, and the numbers are reported so the calibration is
explicit (all computed in
`computations/wake_anchor_and_suppression.py` §B):

- **Impedance transmission in an alternative constitutive crossing model at a scale boundary** with impedance ratio $Z_2/Z_1 = \varphi$: amplitude $T = 2\sqrt{Z_1Z_2}/(Z_1+Z_2) = 2\varphi^{-3/2} \approx 0.972$ (power $4\varphi^{-3} \approx 0.944$; amplitude reflection $(\varphi-1)/(1+\varphi) = \varphi^{-3} \approx 0.236$). A $\varphi$ impedance step has ~97% transmission; the declared attenuation input is $\varphi^{-1}\approx62\%$.
- **Kinetic vs conversion at the modeled wavelength scale in an alternative constitutive model**: the wave (kinetic) term $c^2k^2 = 4\pi^2$ at scale $\ell_n$ ($c = 1$, $k = 2\pi/\ell_n$) dominates the conversion term $\lambda(1-q) \le 0.1$ by a factor $\sim 4\pi^2/\lambda \approx 395$; the ratio $\lambda(1-q)/c^2k^2 \approx 2.5\times10^{-3}$ is two and a half orders below $\varphi^{-1}$. This scale-separated model is kinetic-dominated at wavelength $\ell_n$.
- **Gate openness at the attractor**: $(1-q_{\mathrm{eq}}) = \varphi^{-2}/3 \approx 0.127$ (`foundations/spiral-dynamics.md` §2.2), the gate value used for this calibration.

$$\boxed{\text{Inputs: (i) the }\varphi\text{-attractor fixed point } E_Y = \varphi E_I \text{ (the defining structure of the conversion term); (ii) the declared uniform per-step attenuation input } \varphi^{-1}; \text{ (iii) a separate Hypothesized phenomenological/constitutive map for any propagating-channel assignment, directional interscale coupling, re-locking, reabsorption, or interscale-transport reading. Tier: the identity } \varphi/(1+\varphi) = \varphi^{-1} \text{ is exact; the product algebra is Derived conditional on the declared input; the map-dependent propagation, carrier, re-locking, and reabsorption interpretation is Hypothesized.}}$$

### 4.1 Conservative stress and routed-flux boundary

The mixed-stress identity in
`foundations/interscale-stress-attenuation-boundary.md` separates four uses of
the same scalar coefficient. In a reciprocal ladder,
$\kappa_a=\kappa_{\star,a}d_a$ makes $d_a$ an interface stiffness. It gives the
exact frozen-state traction ratio
$\Pi_{a+1/2}(d_a)/\Pi_{a+1/2}(1)=d_a$, while normal modes remain conservative
and static interfaces combine through series compliance.

The time-completed quadratic scale action supplies the canonical boundary
flux. At an equal-impedance two-lead vertex, Hermitian Robin data
$K_{\mathfrak s}\Phi'=\Lambda_v\Phi$ give the unitary family

$$
S_\Lambda(k)
=
(ikK_{\mathfrak s}I-\Lambda_v)^{-1}
(ikK_{\mathfrak s}I+\Lambda_v).
$$

The registered two-rail phase gluing is a perfect-transfer endpoint. The
declared golden matrix is realized at one design wave number by

$$
\Lambda_\varphi(k_\star)
:=
iK_{\mathfrak s}k_\star
\frac{r_\varphi}{1+t_\varphi}
\begin{pmatrix}0&1\\-1&0\end{pmatrix}.
$$

Under the Hypothesized Yang/Yin species-port identification, freezing the
charged endpoint background gives the gauge-covariant rail-rail Hessian

$$
\Lambda_{\mathrm{link},v}
:=2\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix}.
$$

A dressed quarter-turn phase and the matching condition
$2\kappa_vu_v/(K_{\mathfrak s}k_\star)
=r_\varphi/(1+t_\varphi)$ realize $\Lambda_\varphi$. Requiring the same link
to carry the unbiased proton circuit current below capacity with positive
fixed-amplitude phase stiffness gives the conditional lower bound
$k_\star>0.0964640362$. The endpoint background, coupling amplitude, dressed
phase, port normalization, and matching point remain physical inputs, and a
fixed frozen link gives a wave-number-dependent split.

With the separate constitutive identification
$T_\varphi=\varphi^{-1}$ and $R_\varphi=\varphi^{-2}$ as forward and return
powers, a closed coherent chain produces interference. Routing every return
port away from later forward inputs gives

$$
P_N^{\mathrm{fwd}}=\varphi^{-N}P_0,
\qquad
P_N^{\mathrm{return,tot}}=(1-\varphi^{-N})P_0.
$$

The amplitude in that routed branch scales as $\varphi^{-N/2}$. This
realization applies directly to a conserved quadratic flux, power, energy, or
stress. Coupling constants, phases, and other amplitude-like observables retain
their separate Hypothesized signal maps. The endpoint selection, port
identification, return routing, and map from density or gauge current to
spatial-momentum stress remain open constitutive physics.

---

## 5. Predictive power

The cascade suppression formula makes a specific, falsifiable prediction
for any phenomenon with identified source and target cascade steps, conditional on
the declared attenuation family and any required Hypothesized
phenomenological/constitutive source-to-target map:

$$\text{Prediction} = \text{Seed value} \times \varphi^{-(n_{\text{target}} - n_{\text{source}})}$$

Under the Hypothesized signal map, with the Mapped CKM seed
$\delta_{\text{CP}}=\pi\varphi^{-2}$, strong CP gives
$\bar{\theta} \approx \pi\varphi^{-83.4}\approx1.2\times10^{-17}$—testable if
future neutron EDM probes improve by several orders of magnitude.

For neutrino masses, the same conditional formula applied to the seesaw scale gives the
order-of-magnitude mass scale. The individual flavor masses require the
specific $\varphi$-power chain through the cascade, which is the three-
generation structure (Q5).

For a future "why is this number so small?" question in particle physics with a
declared source-to-target assignment, the first algebraic test is: does the
ratio match $\varphi^{-N}$ for some integer cascade span $N$ under the
corresponding attenuation input? If yes, the cascade family supplies the
conditional answer under its Hypothesized map. If no, the framework does not
assign a $\varphi^{-N}$ explanation at that span.

---

## 6. Relation to the cascade table

For each modeled hierarchical coupling assigned to the declared attenuation
family, the parameterization is $g_n = g_m \cdot \varphi^{-(n-m)}$; the relation
is Derived conditional on that input. The two are dual: the first governs
**lengths**; the second parameterizes **strengths**. Together they provide the
scaling parameterization for those declared cases.

---

## 7. References

- `foundations/dimensionful-cascade.md`—complete cascade table, $\ell_n = \ell_{\text{Pl}}\varphi^n$ (292 = today's horizon step)
- `foundations/proton-coherence-budget.md`—coherence maintenance, quadratic exponent
- `foundations/strong-cp-derivation.md`—Hypothesized signal-map use, $\bar{\theta} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as a cascade suppression factor
- `principles/de-resonance-principle.md`—why $\varphi^{-1}$ is the per-step attenuation input
- `computations/wake_anchor_and_suppression.py`—§B: impedance, kinetic-vs-conversion, and Yang-fraction readings of the per-step factor
- `foundations/interscale-stress-attenuation-boundary.md`—reciprocal stress ledger, coherent two-port boundary, and routed quadratic-flux realization
- `foundations/endpoint-link-and-localization-boundary.md`—gauge-covariant charged-link realization and conditional current-capacity boundary
- `computations/endpoint_robin_link_prereg.md`—frozen endpoint–Robin receipt
- `computations/interscale_stress_attenuation_check.py`—conservation and transfer-algebra receipt
