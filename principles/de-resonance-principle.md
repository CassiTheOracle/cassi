# The De-Resonance Principle in Cassi

## Status: Derived—July 2026

## Why φ is the Attractor (and Why Most Things Are Near φ-Powers)

---

## 1. The Resonance Avoidance Principle

In a system of coupled oscillators, a **rational frequency ratio** (e.g., $2:1$, $3:2$)
leads to **resonance**—energy concentrates at a single scale, and the multi-scale
structure collapses. An **irrational frequency ratio** prevents this, allowing
multi-scale structure to persist.

The golden ratio $\varphi$ is the **most irrational** of all irrationals: its
continued fraction is $[1; 1, 1, 1, \ldots]$ forever, and the convergents
$1, 2, 3, 5, 8, 13, 21, 34, 55, 89$ are Fibonacci numbers. No other irrational
number resists rational approximation as well as $\varphi$.

**Consequence:** $\varphi$ is the *maximally de-resonant* value—the one that
most strongly forbids single-scale dominance and most strongly favors multi-scale
structure formation. In the two-fluid PDE, the Yang/Yin ratio $r = E_Y/E_I$
evolves toward $\varphi$ because that's the configuration that keeps the
system dynamically rich.

The $\varphi$-attractor is not an axiom—it is an **emergent consequence** of
the wave-physics principle that multi-scale structure requires de-resonance.

---


## 2. The Framework Posture

| Earlier framing | Revised framing |
|----------------|--------------|
| Every quantity is exactly a $\varphi$-power | Every quantity is **near** a $\varphi$-power, with deviations determined by dynamics |
| $v_0 = M_{\rm Pl} \cdot \varphi^{-80}$ (exact) | $v_0 = M_{\rm Pl} \cdot \varphi^{-80} \cdot (1 + \text{correction})$ |
| $m_e = v_0 \cdot \varphi^{-26}/\sqrt{2}$ (exact) | $m_e = v_0 \cdot \varphi^{-26}/\sqrt{2} \cdot (1 + \text{correction})$ |
| $\sin^2\theta_W = \varphi^{-3}$ (exact) | $\sin^2\theta_W = \varphi^{-3} \cdot (1 + \text{correction})$ |
## 3. The Empirical Pattern of Corrections

| Quantity | Nearest $\varphi$-power | Measured | Correction | Mechanism | Evidence |
|----------|------------------------|----------|------------|-----------|----------|
| $\sin^2\theta_W$ | $\varphi^{-3} = 0.236$ | $0.23129$ | $-2.0\%$ | MSSM RGE from GUT to $m_Z$ | **Computed** |
| $v_0/M_{\rm Pl}$ | $\varphi^{-80} = 1.91\times10^{-17}$ | $2.02\times10^{-17}$ | $+5.6\%$ | **Unidentified**—see `v0-hierarchy-problem.md` (v₀ is λ-independent at equilibrium; mechanism may be threshold corrections, exact φ-attractor value, or RGE) | **Hypothesized** |
| $m_e$ | $v_0\varphi^{-26}/\sqrt{2} = 0.64$ MeV | $0.511$ MeV | $-20\%$ | Flavor mixing from $\mu,\tau$ sector | **Speculative** |
| $\alpha_s(M_Z)$ | $0.058$ (SM RGE) | $0.118$ | $\times 2.0$ | Needs $\Delta b = 1.70$ from ~1 vector-like colored fermion pair + 2 colored scalars, or ~3 KK levels | **Speculative** |

**Evidence levels:**
- **Computed** = explicit calculation done in Cassi or SM RGE
- **Hypothesized** = plausible mechanism identified but not yet calculated in detail
- **Speculative** = a possible explanation with no specific calculation

**Pattern:** the correction magnitude correlates with how "de-resonant" the
quantity's natural scale is. Strongly-attractor quantities (couplings set at
the $\varphi$-equilibrium) have small corrections ($\sim 2{-}5\%$). Weakly-attractor
quantities (masses that require mixing to set their scale) have larger
corrections ($\sim 20{-}30\%$). Non-attractor quantities (those determined by
The $\varphi$-attractor gives $\sin^2\theta_W = \varphi^{-3}$ at the scale
where the two-fluid gauge structure is set (the GUT scale). The MSSM
$\beta$-function from $M_{\rm GUT}$ to $m_Z$ shifts this by $-1.7\%$.
GUT-scale threshold corrections of $\sim 2\%$ close the remaining gap.

**Mechanism:** running of the gauge couplings between the matching scale
and the $Z$-pole, plus heavy-particle thresholds at the matching scale.

### 4.2 $v_0/M_{\rm Pl}$ ($5.6\%$ correction)—**Hypothesized, mechanism unidentified**

The equilibrium $v_0$ from the Cassi potential is **independent of $\lambda$** at
the $\varphi$-fixed point ($v_0^2 = -\mu^2/g$). The original hypothesis that
the $5.6\%$ correction came from $g/\lambda$ mixing is therefore **wrong**.
The actual mechanism remains unidentified; plausible candidates are:

- **Threshold corrections at the matching scale** (heavy-particle finite shifts)
- **The exact $\varphi$-attractor value** vs. the nearest integer power
  $\varphi^{-80}$ (true exponent is $79.89$, introducing $\sim 0.5\%$ baseline)
- **RGE running of $v_0$** in the Cassi SU(2) framework (sign analysis needed)

See `v0-hierarchy-problem.md` for the full analysis. None of the candidates
has been computed in the Cassi framework; this is the framework hierarchy
problem in disguise.

### 4.3 $m_e$ ($20{-}25\%$ correction)—**Speculative**

The electron Yukawa coupling is set by the $\varphi$-power hierarchy, but the
*actual* coupling is renormalized by mixing with the $\mu$ and $\tau$ Yukawa
sectors. In the CKM-like structure, the off-diagonal mixing terms contribute
$\sim 25\%$ corrections to the diagonal electron coupling.

**Mechanism:** flavor-mixing among the three lepton families. The
$\varphi$-attractor prediction is the "no-mixing" limit.

### 4.4 $\alpha_s(M_Z)$ ($\times 2.0$ correction)—**Speculative**
The $\alpha_s$ running from $\alpha_{\rm GUT} = \varphi^{-3}/(4\pi)$ depends on
the **number and content of particles** between $M_{\rm GUT}$ and $m_Z$. The
Standard Model $\beta$-function coefficient $b_0 = 7$ (for $n_f = 6$) gives
$\alpha_s(M_Z) \approx 0.058$—a factor of $2.0\times$ below the measured
$0.118$. The gap reported as $11\times$ came from a sign error
in the RGE calculation; the corrected SM running is $0.058$.

Closing this gap requires $\Delta b = 1.70$ in the QCD $\beta$-function,
achievable through:
- **~1 vector-like colored fermion pair** (e.g., a $\mathbf{3} + \bar{\mathbf{3}}$ pair)
- **+ 2 colored scalars** (e.g., squark-like states)
- **Or ~3 KK levels** of a gluon in an extra-dimensional scenario

**Mechanism:** the $\alpha_s$ RGE depends on the full particle spectrum, not
just on $\varphi$.

---

## 5. Forward-Looking Testable Predictions

The de-resonance principle makes *prospective* claims—predictions about
future measurements, not descriptions of the existing pattern.

### 5.1 Precision electroweak

The next generation of electroweak measurements (FCC-ee, ILC, CEPC) will
measure $\sin^2\theta_W$ to $\pm 10^{-6}$ precision. The de-resonance principle
predicts the residual shift from $\varphi^{-3}$ should be **stable under RGE
running**—the Z-pole value should equal the LEP-2 value plus a calculable
logarithmic correction, with no additional threshold shifts. If a new
threshold appears in the Z-pole $\sin^2\theta_W$, the de-resonance framework
is stressed.

### 5.2 New scalar discoveries

If a new scalar is discovered at mass $M_X$ with coupling $y_X$ to the
Standard Model Higgs, the de-resonance principle predicts:

$$y_X \approx \varphi^{-n} \cdot (1 + \delta), \quad |\delta| < 0.3$$

for some integer $n$ determined by the field's role. A scalar with $y_X$
deviating from the nearest $\varphi$-power by more than $30\%$ would
indicate a non-$\varphi$-attractor sector.

### 5.3 Future lepton mass measurements

Currently $m_e$ deviates from $v_0\varphi^{-26}/\sqrt{2}$ by $-20\%$. If
flavor-mixing is the source, the deviation should be **calculable** from
the CKM-like lepton mixing matrix once the full flavor structure is
specified. A measured $m_e$ shift of more than $30\%$ from this prediction
would rule out flavor-mixing as the dominant correction.

### 5.4 GUT-scale $\alpha_s$

If a new GUT-scale measurement of $\alpha_s$ (e.g., from proton decay bounds
or collider GUT signals) gives a value within $10\%$ of $\varphi^{-3}/(4\pi)$,
the SUSY/KK-explanation for the $\alpha_s$ RGE would be confirmed. A
significantly different GUT-scale $\alpha_s$ would force re-evaluation of
the $\varphi$-attractor scale.

---

## 6. Implications for the TOE

The Cassi framework is not a "everything is $\varphi$" theory. It is a
**de-resonance principle** theory: the $\varphi$-attractor sets the
**leading-order baseline** for all couplings, and the dynamics provide
**subleading corrections**.

This is the same conceptual structure as the Standard Model, where the
electroweak VEV sets the leading-order scale for all masses, and the Yukawa
couplings (with their non-trivial flavor structure) provide the corrections.
The Cassi framework's innovation is to identify $\varphi$ as the relevant
leading-order baseline—the *most irrational*, *most de-resonant* value
that nature could pick.

The framework's predictive power is:

1. **All dimensionless couplings are near $\varphi$-powers** (within a factor
   of $\sim 2$, set by the dynamics).
2. **The deviation pattern is monotonic in the natural scale** (smallest
   at the $\varphi$-attractor scale, largest at far-IR scales).
3. **The mechanism for each correction is identifiable** (RGE running,
   threshold effects, flavor mixing, particle content).

This is a weaker but more honest framework than "every quantity is exactly a
$\varphi$-power"—and a much stronger framework than "we have a thousand free
parameters."
