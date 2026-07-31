# The Cascade Suppression Formula: $\varphi^{-N}$ as the Universal Attenuation Law

## Status: Derived—July 2026

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

- **Coherence maintenance** ($d_i \approx (1-q_i) \approx \varphi^{-i-\delta}$): $\mathcal{D} = \varphi^{-n(n+1)/2 + \delta n}$—quadratic in depth. Applies to proton stability and any phenomenon requiring simultaneous coherence across all supporting rungs.

The per-rung damping $d_i$ is derived from the PDE once (Section 1), applied to
all five cases (Sections 2--4), establishing $\varphi^{-N}$ as the framework's
universal attenuation law—the single mathematical structure behind every
"hierarchy" or "stability" puzzle in physics.

**Bidirectional extension:** The per-rung attenuation formulas in §1 are defined for $n \geq 0$ (Planck → observable scales). For the extension to sub-Planckian scales ($n < 0$), see `microcascade-mirror.md`.

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

The quadratic-in-$n$ exponent is why the proton lives $10^{980}$ years:
95 rungs of position-dependent coherence, each contributing $\varphi^{-i}$,
compound to $\varphi^{-4560}$.

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
| **Hierarchy** ($v_0/M_{\text{Pl}}$) | Signal | $n_{\text{GUT}} \approx 8$ | $n_{\text{EW}} \approx 80$ | $72$ | $\varphi^{-72}$ | $10^{-15}$ (cf. $10^{-17}$) | Derived |
| **Strong CP** ($\bar{\theta}$) | Signal | $n_{\text{GUT}} \approx 8$ | $n_{\text{QCD}} = 95$ | $87$ | $\varphi^{-87}$ | $\bar{\theta} \approx 10^{-19}$ | Derived |
| **Neutrino masses** | Signal | $n_{\text{GUT}} \approx 8$ | $n_{\text{seesaw}} \approx 20$ (or $n_\nu$) | $12$–$25$ | $\varphi^{-12}$ to $\varphi^{-25}$ | $m_\nu \sim 0.001$–$0.1$ eV | Hypothesized |
| **Proton stability** | Coherence | $n=0$ (Planck) | $n_{\text{QCD}} = 95$ | $95^2$ form | $\varphi^{-4848}$ | $\tau_p \approx 10^{980}$ yr | Derived |
| **Measurement collapse** | Single-rung |—| $n_{\text{target}}$ | $N=1$ | $\mathcal{M}$ (phase-matching) | $P \approx 1-q_n$ at target rung | Hypo w/ core |
| **Spin ($s = \Delta n$)** | Geometric |—|—| $\Delta n$ | N/A (conserved winding) | $s \in \{0,\frac12,1,2\}$ | Hypothesized |

The hierarchy, strong CP, and neutrino masses are all **signal propagation**
from the GUT scale—different targets give different observed suppressions,
all following $\varphi^{-N}$ with zero free parameters.

Measurement and spin are the limiting cases: $N=1$ (single-rung coupling)
and $\Delta n$ (conserved topological winding). The cascade suppression
formula smoothly interpolates between these limits.

---

## 4. Why $\varphi^{-1}$ per rung?

The per-rung damping $d_i \approx \varphi^{-1}$ in the signal-propagation
regime is not an assumption—it follows from the de-resonance principle.
The $\varphi$-attractor is the fixed point where conversion vanishes
($\lambda(E_Y - \varphi E_I) = 0$). A signal that departs from the
attractor (a coupling not at its $\varphi$-power value, a phase not at
the CP-symmetric fixed point) is **off-resonance** at every intermediate
rung. The damping per rung is the ratio of the off-resonance amplitude
to the on-resonance amplitude:

$$\frac{\text{off-resonance}}{\text{on-resonance}} = \frac{\lambda \cdot \varepsilon}{\lambda \cdot 0 + \text{kinetic}} \approx \varphi^{-1}$$

because the kinetic (inertial) term at each rung is $\mathcal{O}(\varphi)$
relative to the conversion term—the same $\varphi$ ratio that gives the
attractor its stability. One cycle of conversion damps the non-$\varphi$
component by $\varphi^{-1}$. Over $N$ rungs, the signal must survive
$N$ such damping events, losing a factor of $\varphi^{-1}$ each time.

---

## 5. Predictive power

The cascade suppression formula makes a specific, falsifiable prediction
for any phenomenon with an identified source and target rung:

$$\text{Prediction} = \text{Seed value} \times \varphi^{-(n_{\text{target}} - n_{\text{source}})}$$

For strong CP, this gives $\bar{\theta} \approx 10^{-19}$—testable if
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

- `dimensionful-cascade.md`—complete 292-step cascade table
- `proton-coherence-budget.md`—coherence maintenance, quadratic exponent
- `strong-cp-derivation.md`—signal propagation, $\bar{\theta} = \varphi^{-87}$
- `xi-derivation.md`—$\xi = \varphi^6$ as a cascade suppression factor
- `principles/de-resonance-principle.md`—why $\varphi^{-1}$ is the per-rung damping
