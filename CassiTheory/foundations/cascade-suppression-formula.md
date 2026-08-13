# The Cascade Suppression Formula: $\varphi^{-N}$ as the Universal Attenuation Law

## Status: Derived (coherence exponent); signal exponent definitionally calibrated (per-rung $\varphi^{-1}$ = attractor Yang fraction, §4)—August 2026

## Abstract

Every hierarchical phenomenon in the Cassi framework—proton stability, the
strong CP angle, the electroweak hierarchy, neutrino masses, quantum measurement
— obeys a single formula: the **cascade suppression factor**. A physical
quantity originating at cascade rung $m$ and observed at rung $n$ is attenuated
by a factor that depends only on the cascade span $N = n - m$ and the nature of
the propagation:

$$\boxed{\mathcal{D}_{m \to n} = \prod_{i=m}^{n-1} d_i}$$

where $d_i$ is the per-rung attenuation at rung $i$, determined by the
two-fluid PDE and the $\varphi$-attractor's de-resonance. Two regimes
cover all known applications:

- **Signal propagation** ($d_i \approx \varphi^{-1}$ uniform): $\mathcal{D} = \varphi^{-N}$—linear in span. Applies to CP violation, hierarchy, neutrino masses, and any phenomenon where a physical coupling propagates through the cascade medium.

- **Coherence maintenance** ($d_i \approx (1-q_i) \approx \varphi^{-i-\delta}$): $\mathcal{D} = \varphi^{-n(n+1)/2 - \delta(n+1)}$—quadratic in depth. Applies to proton stability and any phenomenon requiring simultaneous coherence across all supporting rungs.

The per-rung damping $d_i$ is fixed once in the cascade medium (Section 1), applied to
all five cases (Sections 2--4), establishing $\varphi^{-N}$ as the framework's
universal attenuation law—the single mathematical structure behind every
"hierarchy" or "stability" puzzle in physics. The signal-regime factor
$\varphi^{-1}$ is the definitional calibration of the formula (§4); the
coherence-regime factor $(1-q_i)$ is derived from the gate.

**Bidirectional extension:** The per-rung attenuation formulas in §1 are defined for $n \geq 0$ (Planck → observable scales). For the extension to sub-Planckian scales ($n < 0$), see `foundations/microcascade-mirror.md`.

---

## 1. Derivation from the two-fluid PDE

### 1.1 The per-rung attenuation $d_i$

At cascade rung $i$, the local field is described by the two-fluid PDE with
the conversion term coupling $E_Y$ and $E_I$:

$$\partial_t E_Y \supset -\lambda(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(E_Y - \varphi E_I)$$

Any departure from the $\varphi$-equilibrium ($E_Y \neq \varphi E_I$) is
**actively damped** by the conversion term. The damping rate at rung $i$
is set by the effective coupling strength at that scale.

Two distinct damping regimes emerge from the Qi coherence profile across
the cascade:

$$q_i = 1 - \varphi^{-i-\delta}, \qquad \delta = 3 \text{ (from } \sigma = \ell_{\text{Pl}}/\varphi^3\text{)}$$

### 1.2 Signal propagation: per-rung uniform damping

When a physical signal—a coupling constant, a CP-violating phase, a mass
scale—propagates through the cascade medium, it experiences the
**de-resonance damping** at each rung. The per-rung damping factor $d_i$
is the fraction of the signal that survives passage through rung $i$:

$$d_i^{\text{signal}} = 1 - q_i + \varphi^{-1} = \varphi^{-i-\delta} + \varphi^{-1}$$

For all rungs $i \ge 1$ (i.e., everywhere except the Planck core), the
$\varphi^{-1}$ term dominates, giving:

$$\boxed{d_i^{\text{signal}} \approx \varphi^{-1}, \qquad i \ge 1}$$

The $\varphi^{-1}$ term is the attractor Yang fraction
$\varphi/(1+\varphi) = \varphi^{-1}$—the fixed-point amplitude split
(§4)—and is the definitional per-rung step of the suppression formula;
the $(1-q_i)$ term is the per-rung coherence dephasing. The two are
independent: the first is the calibration, the second the noise.

The total damping over $N$ rungs is the product:

$$\mathcal{D}_{m \to n}^{\text{signal}} = \prod_{i=m}^{n-1} \varphi^{-1} = \varphi^{-(n-m)} = \varphi^{-N}$$

### 1.3 Coherence maintenance: position-dependent damping

When a condensed standing wave must maintain **simultaneous coherence**
across all its supporting rungs, the per-rung noise fraction $(1-q_i)$ sets
the probability that rung $i$ fails during one wave cycle:

$$d_i^{\text{coherence}} = (1-q_i) = \varphi^{-i-\delta}$$

This is **position-dependent**: rungs near Planck are far more coherent
($d_i \ll \varphi^{-1}$) than rungs near the QCD scale.

The total failure probability over $n$ rungs (from Planck, $i=0$, to the
particle, $i=n$) is:

$$\mathcal{D}_{0 \to n}^{\text{coherence}} = \prod_{i=0}^{n} (1-q_i) = \varphi^{-\sum_{i=0}^{n}(i+\delta)} = \varphi^{-n(n+1)/2 - \delta(n+1)}$$

The quadratic-in-$n$ exponent is why the proton lives $10^{910}$ years:
91.5 rungs of position-dependent coherence ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$), each contributing
$\varphi^{-i-\delta}$ with $\delta = 3$ (from $\sigma = \ell_{\text{Pl}}/\varphi^3$),
compound to $\varphi^{-4506}$ (see `foundations/proton-coherence-budget.md`).

---

## 2. The two regimes, side by side

| Regime | $d_i$ | $\mathcal{D}_{m \to n}$ | Exponent | Physical meaning |
|---|---|---|---|---|
| **Signal propagation** | $\varphi^{-1}$ | $\varphi^{-N}$ | Linear in $N$ | A signal traversing $N$ rungs is attenuated by $\varphi^{-N}$—the cascade damps non-$\varphi$ structure at a fixed rate per rung. |
| **Coherence maintenance** | $\varphi^{-i-\delta}$ | $\varphi^{-n(n+1)/2}$ | Quadratic in $n$ | $n$ rungs must all stay coherent simultaneously; the probability compounds multiplicatively across all supporting depths. |

---

## 3. All applications in one table

| Phenomenon | Regime | Seed at cascade rung | Target rung | Span $N$ | $\mathcal{D}$ | Result | Status |
|---|---|---|---|---|---|---|---|
| **Hierarchy** ($v_0/M_{\text{Pl}}$) | Signal | $n_{\text{GUT}} \approx 13.3$ (corrected anchor) | $n_{\text{EW}} \approx 80$ | $66.7$ | $\varphi^{-66.7}$ | $10^{-14}$ (cf. $10^{-17}$; the $N \approx 80$ consistency check of `foundations/dimensionful-cascade.md` §2.1 uses the gap factor $g$) | Derived; exponent **Mapped** (ledger row 499) |
| **Strong CP** ($\bar{\theta}$) | Signal | $n_{\text{GUT}} \approx 13.3$ | $n_{\text{QCD}} = 94.7$ | $81.4$ | $\varphi^{-81.4}$ | $\bar{\theta} \approx 1.2\times10^{-17}$ | Derived |
| **Neutrino masses** | Signal | $n_{\text{GUT}} \approx 8$ | $n_{\text{seesaw}} \approx 20$ (or $n_\nu$) | $12$–$25$ | $\varphi^{-12}$ to $\varphi^{-25}$ | $m_\nu \sim 0.001$–$0.1$ eV | Hypothesized |
| **Proton stability** | Coherence | $n=0$ (Planck) | $n = 91.5$ (proton rung) | $91.5^2$ form | $\varphi^{-4506}$ | $\tau_p \approx 10^{910}$ yr | Derived |
| **Measurement collapse** | Single-rung |—| $n_{\text{target}}$ | $N=1$ | $\mathcal{M}$ (phase-matching) | $P \approx 1-q_n$ at target rung | Hypo w/ core |
| **Spin ($s = \Delta n/2$)** | Geometric |—|—| $\Delta n \in \{0,1,2,4\}$ | N/A (conserved winding) | $s \in \{0,\frac12,1,2\}$ | Hypothesized |

The hierarchy, strong CP, and neutrino masses are all **signal propagation**
from the GUT scale—different targets give different observed suppressions,
all following $\varphi^{-N}$ with zero free parameters.

Measurement and spin are the limiting cases: $N=1$ (single-rung coupling)
and $\Delta n$ (conserved doublet winding, $s = \Delta n/2$;
`foundations/spin-fibonacci-spiral.md` §2.1). The cascade suppression
formula smoothly interpolates between these limits.

---

## 4. Why $\varphi^{-1}$ per rung?

The per-rung factor is the definitional calibration of the suppression formula—one rung of signal propagation is, by definition, one $\varphi$-step of attenuation—and its in-framework expression is exact: it is the Yang fraction of the two-fluid doublet at the $\varphi$-attractor.

At the fixed point $E_Y = \varphi E_I$ the Yang channel carries

$$\frac{E_Y}{E_Y + E_I} = \frac{\varphi}{1+\varphi} = \frac{\varphi}{\varphi^2} = \varphi^{-1}$$

of the amplitude (ledger rows 500/453: the fixed-point Yang fraction is $\varphi^{-1}$, and $\alpha_w = r/(1+r)$ at $r = \varphi$). The reading: at each rung the field re-locks to the $\varphi$-attractor, and the Yang (expansive, structure-carrying) channel—the one a propagating signal rides—carries fraction $\varphi^{-1}$ of the doublet; the Yin (restorative) fraction is re-absorbed by conversion. One rung of propagation is one re-locking event, so the signal survives with factor $\varphi^{-1}$ per rung, and over $N$ rungs

$$\boxed{\mathcal{D}^{\text{signal}}_{m \to n} = \prod_{i=m}^{n-1} \varphi^{-1} = \varphi^{-(n-m)} = \varphi^{-N}}$$

The alternative crossing models do not produce $\varphi^{-1}$, and the numbers are reported so the calibration is explicit (all computed in `computations/wake_anchor_and_suppression.py` §B):

- **Impedance transmission at a rung boundary** with impedance ratio $Z_2/Z_1 = \varphi$: amplitude $T = 2\sqrt{Z_1Z_2}/(Z_1+Z_2) = 2\varphi^{-3/2} \approx 0.972$ (power $4\varphi^{-3} \approx 0.944$; amplitude reflection $(\varphi-1)/(1+\varphi) = \varphi^{-3} \approx 0.236$). A $\varphi$ impedance step transmits ~97%, not 62%.
- **Kinetic vs conversion at the rung-wave scale**: the wave (kinetic) term $c^2k^2 = 4\pi^2$ at rung $\ell_n$ ($c = 1$, $k = 2\pi/\ell_n$) dominates the conversion term $\lambda(1-q) \le 0.1$ by a factor $\sim 4\pi^2/\lambda \approx 395$; the ratio $\lambda(1-q)/c^2k^2 \approx 2.5\times10^{-3}$ is two and a half orders below $\varphi^{-1}$. The "kinetic term is $\mathcal{O}(\varphi)$ relative to the conversion term" statement does not hold at the rung-wave scale.
- **Gate openness at the attractor**: $(1-q_0) = \varphi^{-2}/3 \approx 0.127$ (`foundations/spiral-dynamics.md` §2.2)—not $\varphi^{-1}$.

$$\boxed{\text{Inputs: (i) the }\varphi\text{-attractor fixed point } E_Y = \varphi E_I \text{ (the defining structure of the conversion term); (ii) the identification of the propagating channel with the Yang fraction (the framework's characterization of Yang as expansive, structure-carrying); (iii) the re-locking-per-rung reading. Tier: the identity } \varphi/(1+\varphi) = \varphi^{-1} \text{ is exact; the per-rung factor itself remains the definitional calibration of the suppression formula (postulate-level, like } \ell_n \text{); the re-locking reading is the framework's characterization—Hypothesized.}}$$

---

## 5. Predictive power

The cascade suppression formula makes a specific, falsifiable prediction
for any phenomenon with an identified source and target rung:

$$\text{Prediction} = \text{Seed value} \times \varphi^{-(n_{\text{target}} - n_{\text{source}})}$$

For strong CP, this gives $\bar{\theta} \approx 1.2\times10^{-17}$—testable if
future neutron EDM probes improve by several orders of magnitude.

For neutrino masses, the same formula applied to the seesaw rung gives the
order-of-magnitude mass scale. The individual flavor masses require the
specific $\varphi$-power chain through the cascade, which is the three-
generation structure (Q5).

For every future "why is this number so small?" question in particle physics,
the first test is: does the ratio match $\varphi^{-N}$ for some integer
cascade span $N$? If yes, the answer is the cascade. If no, the framework
predicts new physics at that span's source rung.

---

## 6. Relation to the cascade table

Every hierarchical coupling follows $g_n = g_m \cdot \varphi^{-(n-m)}$. The two are
dual: the first governs **lengths**; the second governs **strengths**.
Together they constitute the complete scaling laws of the framework.

---

## 7. References

- `foundations/dimensionful-cascade.md`—complete cascade table, $\ell_n = \ell_{\text{Pl}}\varphi^n$ (292 = today's horizon rung)
- `foundations/proton-coherence-budget.md`—coherence maintenance, quadratic exponent
- `foundations/strong-cp-derivation.md`—signal propagation, $\bar{\theta} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as a cascade suppression factor
- `principles/de-resonance-principle.md`—why $\varphi^{-1}$ is the per-rung damping
- `computations/wake_anchor_and_suppression.py`—§B: impedance, kinetic-vs-conversion, and Yang-fraction readings of the per-rung factor
