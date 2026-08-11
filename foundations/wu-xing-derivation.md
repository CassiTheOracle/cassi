# Wu Xing Number $w = 5$: Derivation from Cascade Dynamics

## Status: Derived (w = 5, gap, r₀)—single input: coherence postulate; verified 2026-08-11 / λ = 1/(2w) = 0.1 Derived conditional on the doublet conversion budget + one event per cycle (§7) / Calibrated (w₀ via the DESI-anchored coupling form—ledger)

## Abstract

The Wu Xing number $w = 5$—the number of elements in the primordial generation/control cycle that determines the cosmological initial conditions—is derived from two constraints. The cascade dynamics force an upper bound $w \leq 5$: a $w$-vertex cycle closes the golden rotation with accumulated phase error $E(w) = \min_p w|\varphi - p/w|$, and the coherence criterion (accumulated error $\leq$ cascade signal at rung $w$) is solvable **for all $w$ at once**. Continued-fraction optimality (Hurwitz) selects the Fibonacci denominators as the only candidates, the Fibonacci identity $|F_k\varphi - F_{k+1}| = \varphi^{-k}$ evaluates them exactly, and the criterion passes only for $w \in \{1, 2, 3, 5\}$—verified exhaustively for all $w \leq 2000$. $\varphi$-geometry forces a lower bound $w \geq 5$: the regular $n$-gon contains $\varphi$ among its chord ratios first at $n = 5$ (the pentagon's diagonal/side ratio), verified for $n = 3 \ldots 12$. The intersection is exactly $w = 5$. The primordial gap $g = 1 - \varphi^{-5}$ and the primordial Yang-Yin ratio $r_0 = \varphi^{-5}/(2-\varphi^{-5})$ follow directly. The single physical input is the coherence criterion; the Fibonacci restriction is a derived consequence, not an assumption. The derived cycle also fixes the PDE conversion rate, $\lambda = (1/2)(1/w) = 1/(2w) = 0.1$ (§7): the doublet factor $1/2$ (each of the two channels carries half a full oscillation's conversion budget) times the per-vertex share $1/w$ of the single conversion event per cycle.

---

## 1. The Problem

The Cassi framework's cosmological initial conditions depend on a single dimensionless number: the Wu Xing number $w$—the number of phase-advance vertices in the primordial generation/control cycle. This number determines:

- The primordial gap: $g = 1 - \varphi^{-w}$
- The primordial Yang-Yin ratio: $r_0 = (1-g)/(1+g) = \varphi^{-w}/(2 - \varphi^{-w})$
- The dark energy equation of state: $w_0 = -0.87$ (derived from $r_0$ via the PDE), $2\sigma$ from DESI $\approx -0.75 \pm 0.06$

Geometric candidates for $w = 5$ include (`computations/pinch_point_modes.py`):
1. Elliptical cavity mode bands (threshold-dependent, does not enforce exactly 5)
2. Fibonacci convergent hierarchy (derived in §2 from the coherence criterion + continued-fraction optimality)
3. Pentagon geometry (the minimal regular polygon containing $\varphi$)

The derivation follows from two constraints: the cascade dynamics force an upper bound of $w \leq 5$, and $\varphi$-geometry forces a lower bound of $w \geq 5$. The intersection is unique.

---

## 2. The Cascade Upper Bound: Why $w \geq 6$ Fails

### 2.1 Best Rational Closures of the Golden Rotation

Each vertex of a $w$-step cycle advances the phase of the golden rotation by $\varphi$ turns (the de-resonant rotation of `principles/de-resonance-principle.md`). After $w$ steps the phase advanced is $w\varphi$ turns; the cycle closes when this is nearly an integer number $p$ of turns, i.e. when the rational ratio $p/w$ approximates $\varphi$. The **accumulated phase error** after one full cycle is the distance from $w\varphi$ to the nearest integer:

$$E(w) \;=\; \min_{p \in \mathbb{Z}}\, w\left|\varphi - \frac{p}{w}\right| \;=\; \|w\varphi\|$$

where $\|x\|$ is the distance from $x$ to the nearest integer.

The golden ratio's continued fraction is $[1; 1, 1, 1, \ldots]$—the slowest-converging of all irrationals. Its best rational approximations are ratios of consecutive Fibonacci numbers:

$$F_1 = 1, \; F_2 = 1, \; F_3 = 2, \; F_4 = 3, \; F_5 = 5, \; F_6 = 8, \; F_7 = 13, \; \ldots$$

**Best-approximation theorem (Hurwitz).** For every irrational $\alpha$, the integers $q$ with $\|q\alpha\|$ minimal among all $m \leq q$ are exactly the denominators of the convergents of $\alpha$ (best approximations of the second kind); the constant $1/\sqrt{5}$ in Hurwitz's bound $\|q\alpha\| < 1/(\sqrt{5}\,q)$ is optimal, and it is saturated by $\varphi$. For $\varphi$ the convergent denominators are the Fibonacci numbers, and every $w$ below the $(k{+}1)$-th convergent pays an error strictly larger than that convergent's:

$$\boxed{\|w\varphi\| > \|F_{k+1}\varphi\| = \varphi^{-(k+1)} \qquad \text{for all } 0 < w < F_{k+1}}$$

Cycle-size candidates for coherent closure are therefore the Fibonacci numbers themselves—**selected by optimality, not by assumption**. Any non-Fibonacci $w$ pays an error strictly larger than the next convergent's, and §2.5 shows that error already fails the coherence criterion.

### 2.2 The Fibonacci Identity (Number Theory)

A well-known identity follows from $\varphi^2 = \varphi + 1$ (Binet's formula):

$$\boxed{|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}}$$

This is **exact** for all $k \geq 1$. Proof by induction: base case $k=1$ gives $|1\cdot\varphi - 1| = \varphi^{-1}$; the recurrence $F_{k+1} = F_k + F_{k-1}$ combined with $\varphi^{k+1} = \varphi^k + \varphi^{k-1}$ propagates the identity.

By the best-approximation theorem the convergent $p = F_{k+1}$ is the minimizer at $w = F_k$, so the accumulated error of a Fibonacci cycle is exact:

$$E(F_k) = \|F_k \varphi\| = |F_k \varphi - F_{k+1}| = \varphi^{-k}$$

### 2.3 Cascade Attenuation (PDE Signal Regime)

The cascade suppression formula (`foundations/cascade-suppression-formula.md`)—derived from the two-fluid PDE—states that a signal propagating through $N$ cascade rungs is attenuated by:

$$\boxed{S(N) = S(0) \cdot \varphi^{-N}}$$

This is the per-rung damping in the signal-propagation regime: each rung damps non-$\varphi$ structure by $\varphi^{-1}$.

### 2.4 The Coherence Criterion

A Wu Xing cycle of $w$ vertices advances one cascade rung per vertex, so at cycle closure the cascade signal surviving to rung $w$ is $\varphi^{-w}$. The cycle maintains phase coherence across one complete turn only if its accumulated phase error does not exceed that surviving signal.

**Coherence criterion (physical postulate).** A $w$-step cycle closes coherently if and only if

$$\boxed{E(w) \leq \varphi^{-w}}$$

i.e. the accumulated phase slip $\|w\varphi\|$ across one full cycle does not exceed the cascade signal strength $\varphi^{-w}$ at the cycle's rung. This is a signal-detection threshold: if the phase slip exceeds the surviving signal, the cycle's phase structure is obliterated by the cascade noise floor and cannot lock. It is the single physical input of the derivation (§6); it is motivated by the de-resonance principle and consistent with the cascade suppression formula, and it is PDE-testable.

Because the criterion is stated for **all** integers $w$, it screens non-Fibonacci cycles as well: §2.5 evaluates $E(w)$ exactly on the Fibonacci candidates (via §2.1–§2.2) and bounds it away from the threshold on every other $w$.

### 2.5 Solving the Criterion

**Fibonacci cycles.** For $w = F_k$, the criterion is $\varphi^{-k} \leq \varphi^{-F_k}$, equivalent (since $\varphi > 1$) to:

$$\boxed{k \geq F_k}$$

| $k$ | $F_k$ | $k \geq F_k$? | Cycle $w$ | Verdict |
|-----|-------|:---:|:---:|---------|
| 1 | 1 | ✓ | 1 | Coherent (trivial) |
| 2 | 1 | ✓ | 1 | Coherent |
| 3 | 2 | ✓ | 2 | Coherent |
| 4 | 3 | ✓ | 3 | Coherent |
| **5** | **5** | **✓** | **5** | **Coherent (at equality)** |
| 6 | 8 | ✗ | 8 | **Decoheres** |
| 7 | 13 | ✗ | 13 | **Decoheres** |
| 8 | 21 | ✗ | 21 | **Decoheres** |

The inequality $k \geq F_k$ holds for $k \in \{1, 2, 3, 4, 5\}$ and fails for all $k \geq 6$ ($F_k > k$ thereafter, with the gap growing exponentially: $F_{10} = 55$ vs. $k = 10$). The distinct coherent Fibonacci cycle sizes are $w \in \{1, 2, 3, 5\}$; $k = 5$ is the marginal case, closing at exact equality $E(5) = \varphi^{-5} = \text{signal}$.

**Non-Fibonacci cycles.** Every non-Fibonacci $w \geq 6$ fails the criterion. Write $F_k \leq w < F_{k+1}$ with $k \geq 5$. The best-approximation theorem gives $E(w) > \varphi^{-(k+1)}$. Since $w \geq 6$ implies $\varphi^{-(k+1)} \geq \varphi^{-w}$ (for $w \in \{6, 7\}$ with $k = 5$ this is $\varphi^{-6} \geq \varphi^{-w}$; for $k \geq 6$, $w \geq F_k \geq k+1$), the error strictly exceeds the threshold:

$$E(w) > \varphi^{-(k+1)} \geq \varphi^{-w} \qquad \text{for all non-Fibonacci } w \geq 6$$

The remaining non-Fibonacci value below the geometric bound, $w = 4$, fails by direct computation: $E(4) = 6 - 4\varphi \approx 0.472 > \varphi^{-4} \approx 0.146$. Combined with the Fibonacci table:

$$\boxed{\{w \in \mathbb{Z}^{+} : E(w) \leq \varphi^{-w}\} = \{1, 2, 3, 5\}}$$

**Numeric verification.** `computations/wu_xing_coherence_check.py` (run from repo root) checks all $w \in [1, 2000]$: $\|w\varphi\| \leq \varphi^{-w}$ holds **only** for $w \in \{1, 2, 3, 5\}$ ($w = 5$ passes at equality, exact to the identity; the check uses a $10^{-12}$ float tolerance). Explicit values: $E(4) = 0.4721 > 0.1459$, $E(6) = 0.2918 > 0.0557$, $E(7) = 0.3262 > 0.0344$.

**Explicit $w = 10$ falsification:** Ten steps with rational approximation $16/10 = 1.6$ accumulate error $10 \cdot |\varphi - 1.6| = 0.180$. Cascade attenuation at rung 10 is $\varphi^{-10} = 0.0081$. The error exceeds the signal by a factor of **22×**—the cycle is obliterated by noise.

---

## 3. The Geometry Lower Bound: Why $w < 5$ Fails

A cycle that organizes a $\varphi$-based framework must encode $\varphi$ in its vertex geometry. Among the chord ratios of the regular $n$-gon, $\varphi$ appears **first** at $n = 5$ (verified numerically for $n = 3 \ldots 12$; `computations/wu_xing_coherence_check.py`):

$$\frac{\text{diagonal}}{\text{side}} = 2\cos\left(\frac{\pi}{5}\right) = \varphi$$

| $n$ | Polygon | $\varphi$ in chord ratios? |
|-----|---------|:---:|
| 3 | Triangle | No—only ratio $1$ |
| 4 | Square | No—ratios $1$, $\sqrt{2}$, $2$ |
| **5** | **Pentagon** | **Yes**—$\text{diag}/\text{side} = \varphi$, $R/r = 2/\varphi$, $R/s = 1/(2\sin 36°) \approx 0.8507$ |
| 6 | Hexagon | No—ratios $1$, $\sqrt{3}/2$, $\sqrt{3}$, $2$ |
| 7–9, 11–12 | Heptagon … dodecagon | No—no chord ratio equals $\varphi$ |
| 10 | Decagon | Yes, $R/s = \varphi$ (but decoheres—see §2; decomposes into two pentagons) |

Cycles with $w \in \{1, 2, 3\}$ are cascade-coherent but not $\varphi$-structured: they cannot encode the golden ratio in their vertex distance ratios, so they cannot serve as the organizing cycle of a $\varphi$-based framework. The lower bound is $w \geq 5$.

---

## 4. The Intersection: $w = 5$

The cascade dynamics eliminate $w \geq 6$ (all decohere—§2). $\varphi$-geometry eliminates $w < 5$ (all lack $\varphi$ in their chord ratios—§3). The only surviving value is:

$$\boxed{w = 5}$$

The pentagon is **both** cascade-coherent **and** $\varphi$-structured. It is the unique non-trivial cycle satisfying the coherence criterion $E(w) \leq \varphi^{-w}$ with $\varphi$ in its geometry.

---

## 5. Consequences: The Gap and $r_0$

### 5.1 The Primordial Gap

One complete pentagonal cycle advances the conversion phase by a factor of $\varphi^5$, leaving an unconverted residual of $\varphi^{-5}$:

$$\boxed{g = 1 - \varphi^{-5} \approx 0.9098}$$

This is the fraction of the primordial Yang-Yin imbalance converted in the first pentagon cycle at the GUT scale (n ≈ 13.3 for $M_{\text{GUT}} \approx 2\times10^{16}$ GeV; the cascade table's step-5 rung is the 1.1×10¹⁸ GeV scale).

### 5.2 The Primordial Yang-Yin Ratio

The gap $g = |E_Y - E_I|/\rho$ relates to the ratio $r = E_Y/E_I$ via $g = (1-r)/(1+r)$ for Yin-dominated initial states ($r < 1$). Inverting:

$$\boxed{r_0 = \frac{1 - g}{1 + g} = \frac{\varphi^{-5}}{2 - \varphi^{-5}} \approx 0.0472}$$

Equivalently: $E_I/E_Y = 1/r_0 \approx 21.2$. Yin dominates Yang by a factor of ~21 at the Planck scale.

### 5.3 Observable Consequences

- **Dark energy equation of state:** $w_0 = -0.87$ (from PDE integration with $r_0$), $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ [INFERENCE]
- **Baryon asymmetry:** The gap $g = 1 - \varphi^{-5}$ sets the Yang-Yin imbalance at GUT freeze-out, which seeds the matter-antimatter asymmetry
- **Cascade depth:** $N \approx 292$ follows from $H(r)$ dynamics + cosmic age, with $r_0$ as the initial condition

---

## 6. Epistemic Boundaries

### Derived (from the coherence postulate + mathematical theorems)

- Fibonacci identity $|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$ (mathematical theorem)
- Best-approximation optimality of the Fibonacci denominators for $\varphi$ (Hurwitz; mathematical theorem)
- Cascade attenuation $\varphi^{-N}$ over $N$ rungs (derived from two-fluid PDE signal regime)
- The coherent cycle set $\{w : E(w) \leq \varphi^{-w}\} = \{1, 2, 3, 5\}$ (continued-fraction optimality + Fibonacci identity + coherence criterion; exhaustive numeric check $w \leq 2000$)
- $\varphi$ first appears in regular $n$-gon chord ratios at $n = 5$ (verified $n = 3 \ldots 12$)
- Intersection: $w = 5$ uniquely
- The gap: $g = 1 - \varphi^{-5}$
- The primordial ratio: $r_0 = \varphi^{-5}/(2 - \varphi^{-5})$
- The conversion rate: $\lambda = 1/(2w) = 0.1$ (§7)—**Derived conditional on** the doublet conversion budget ($1/2$: each of the two channels carries half a full oscillation's budget) and one conversion event per $w$-cycle ($1/w$: the gap is the fraction converted in one cycle, shared over $w$ vertices)

### Physical Postulate (the single input, PDE-testable)

- **The coherence criterion:** accumulated phase error $\leq$ cascade signal attenuation, $E(w) \leq \varphi^{-w}$. This is a signal-detection principle: if the phase slip across one cycle exceeds the surviving signal strength at that cascade rung, the cycle cannot close coherently. It is physically motivated by the de-resonance principle and consistent with the cascade suppression formula, but it has not been directly verified by a PDE simulation computing phase closure as a function of $w$. A PDE test would initialize a $w$-cycle perturbation and measure whether phase coherence is maintained after one full cycle. The prediction: coherent for $w \leq 5$, decoherent for $w \geq 6$.

**Inputs.** The derivation rests on:

1. **Coherence criterion (physical postulate—the single input of the cascade bound).** A $w$-step cycle closes coherently iff $E(w) \leq \varphi^{-w}$, with one cascade rung advanced per vertex so the closing signal is $\varphi^{-w}$. The $1/\sqrt{5}$-class optimality of $\varphi$'s convergents then supplies the Fibonacci restriction as a theorem, not an assumption.
2. **Cycle setup.** The $w$-vertex cycle closes the golden rotation with best integer ratio $p/w \approx \varphi$; $E(w) = \|w\varphi\|$ measures the phase slip in turns.
3. **$\varphi$-structure requirement (framework principle, not a fitted number).** The organizing cycle of a $\varphi$-based framework must contain $\varphi$ among its vertex chord ratios, which first happens at the pentagon ($w = 5$).

Everything else in §2–§5 is a mathematical theorem or a PDE-derived formula evaluated on these inputs. The tier is **Derived** conditional on input 1 (and the framework principle 3); no exponent is fitted—$w$, $g$, and $r_0$ are computed, and the Fibonacci restriction is derived.

---

## 7. The Conversion Rate $\lambda = 1/(2w) = 0.1$

The PDE conversion rate—the coefficient of the linearized conversion term
$\partial_t E_Y \supset -\lambda(E_Y - \varphi E_I)$, $\partial_t E_I \supset +\lambda(E_Y - \varphi E_I)$
(the code form in `two-fluid/cassi_two_fluid_3d_gpu.py`, gated by $(1-q)$)—factors into two
structural inputs, both already present in the derived material above:

**The doublet factor $1/2$.** The conversion term acts on the two-field SO(2) doublet
$(\Psi_0, \Psi_1) = (E_Y, E_I)$. The $\varphi$-attractor potential is the two-field symmetric form

$$V_{\text{attr}} = \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

(`foundations/unified-lagrangian.md` §1.2): the $1/2$ is the standard normalization in which each
of the two channels carries half the conversion budget. A full Yang→Yin→Yang oscillation is **two
conversion events—one per channel leg**—so the per-channel share of one oscillation's budget is
$1/2$. The same $2$ recurs as $\xi$'s quadratic degree ($\xi = \varphi^6 = (\pi/\rho)^{-2}$, exponent
$6 = 3 \times 2$; `foundations/xi-derivation.md` §2.2), as the pentagonal gate's base offset
$k_i = 2 + i$ (`foundations/wa-pentagon-gate.md`), and as the doublet's full SO(2) cycle of 2 rungs
(`foundations/spin-fibonacci-spiral.md` §2.1).

**The per-cycle event share $1/w$.** The gap $g = 1 - \varphi^{-5}$ (§5.1) is defined as the fraction
of the primordial Yang-Yin imbalance converted in **one** pentagon cycle—each cycle completes exactly
one conversion event. The cycle has $w = 5$ vertices, with one cascade rung advanced per vertex
(§2.4), so the event's rate is shared across the $w$ vertex steps: the per-vertex rate is $1/w$.
In PDE time units (the vertex step, one rung per step), the per-vertex, per-channel conversion rate is

$$\boxed{\lambda = \frac{1}{2}\cdot\frac{1}{w} = \frac{1}{2w} = \frac{1}{2 \times 5} = 0.1}$$

With $w = 5$ derived (§4), $\lambda = 0.1$ follows. The value is rational: no $\varphi$-power equals
$1/10$ (every $\varphi$-power combination has the form $A + B\varphi$, $A, B \in \mathbb{Z}$, and none
equals $1/10$—verified numerically, §7.1), so the conversion rate never phase-locks with the
$\varphi$-spaced cascade rungs and the pentagon's five channels remain non-overlapping (the
de-resonance posture, `principles/de-resonance-principle.md`). This rational, non-resonant character
was already documented as the reason $\lambda = 1/10$ is a *feature*
(`foundations/dimensionful-constants-status.md` §2.1); §7 supplies the factor-by-factor origin of the
value.

### 7.1 Numeric verification

`computations/lambda_half_w_derivation.py` (run from repo root) verifies:

1. **$\lambda = 1/(2 \cdot 5) = 0.1$ exact**, and the $(1/2)(1/w)$ split multiplies to it.
2. **$r_0 = \varphi^{-5}/(2 - \varphi^{-5}) = 0.0472$** (§5.2)—the derived primordial ratio, the
   initial condition this $\lambda$ drives toward the attractor.
3. **The attractor-approach time constant.** The two-field conversion ODE in the code form, gated at
   the attractor gate value $(1-q_0) = \varphi^{-2}/3$, relaxes the imbalance
   $\delta = E_Y - \varphi E_I$ as $e^{-\gamma t}$ with
   $\gamma = \lambda(1-q_0)(1+\varphi) = \lambda/3 = 1/30$, $\tau = 30$—matching the radial relaxation
   rate $\gamma = \lambda/3$ quoted in `foundations/spiral-dynamics.md` §2.3. The integrated ODE
   reproduces the analytic decay to $1.1\times10^{-6}$ relative error (Euler truncation).
4. **The $1/3$ is exact $\varphi$-algebra:** $(1-q_0)(1+\varphi) = (\varphi^{-2}/3)\cdot\varphi^2 = 1/3$
   since $1 + \varphi = \varphi^2$.
5. **Non-resonance:** no $\varphi^k$ ($-20 \le k \le 20$) and no $A + B\varphi$
   ($|A|, |B| \le 1000$) equals $1/10$.
6. **Doublet symmetry:** the conversion term is equal-and-opposite in the two channels
   ($\partial_t E_Y = -\partial_t E_I$), conserving total mass exactly—the $1/2$-per-channel reading
   of the budget.
7. **$\lambda = 0.1$ consequences quoted in the docs reproduce:** the wake ratio
   $\Lambda_\varepsilon/\Lambda_Y = 1/\sqrt{1 - 2\lambda(1-q)/\omega^2} = 1.0025$—a 0.25% correction
   (the argument $2\lambda/\omega^2 = 0.51\%$ with $(1-q) = 1$), not a factor $\varphi$
   (`foundations/wake-geometry.md`)—and the kinetic/conversion ratio
   $\lambda/(c^2k^2) = 2.53\times10^{-3}$ (`foundations/cascade-suppression-formula.md`).

**Inputs.** The derivation rests on:

1. **The doublet conversion budget ($1/2$).** A full Yang→Yin→Yang oscillation is two conversion
   events (one per channel leg); the two-field symmetric potential $(\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$
   carries the same $1/2$ per-channel normalization. Structural—the same $2$ as $\xi$'s quadratic
   degree and the $b_i = \varphi^{-(2+i)}$ gate base.
2. **One conversion event per $w$-vertex cycle ($1/w$).** The gap $g = 1 - \varphi^{-5}$ is the
   fraction converted in one cycle (§5.1); the event's rate is shared across the $w$ vertices (one
   cascade rung per vertex, §2.4). Structural reading of the derived gap.
3. **$w = 5$** (§4), the PDE's linear conversion form, and its time unit (the vertex step). Derived.

The tier is **Derived conditional on inputs 1–2**: with the doublet budget and the one-event-per-cycle
reading, $\lambda = 1/(2w) = 0.1$ is computed, not fitted. Both inputs are structural—input 1 is the
established doublet normalization (and reproduces the existing "2 conversion events per full
oscillation" reading of `foundations/dimensionful-constants-status.md` §2.1), and input 2 is the
per-cycle reading of the already-derived gap—but neither is separately pinned by an independent
measurement of $\lambda$; the numeric checks in §7.1 confirm the value's consequences, not the
inputs' necessity.

---

## 8. References

- `foundations/cascade-suppression-formula.md`—per-rung attenuation $\varphi^{-1}$, signal regime; kinetic/conversion ratio at $\lambda = 0.1$
- `foundations/dimensionful-cascade.md`—cascade table, n ≈ 13.3 (GUT), step 285 (Cassi bubble)
- `foundations/dimensionful-constants-status.md`—status of $w = 5$; §2.1 conversion-rate reading ("2 conversion events per full oscillation")
- `computations/pinch_point_modes.py`—Candidate 2: Fibonacci convergent hierarchy
- `computations/wu_xing_coherence_check.py`—numeric verification: Fibonacci identity, criterion over $w \leq 2000$, chord-ratio check for $n = 3 \ldots 12$
- `computations/lambda_half_w_derivation.py`—numeric verification of §7: $\lambda = 1/(2w)$, $r_0$, the $\gamma = \lambda/3$ attractor time constant, non-resonance, doublet symmetry, $\lambda = 0.1$ doc consequences
- `foundations/spiral-dynamics.md`—Hubble, gravity, and $c$ from spiral geometry; §2.3 radial relaxation rate $\gamma = \lambda/3$
- `foundations/unified-lagrangian.md`—the $\varphi$-attractor potential $(\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$
- `foundations/xi-derivation.md`—$\xi = \varphi^6$, the quadratic degree 2
- `foundations/wa-pentagon-gate.md`—5-channel gate openness $b_i = \varphi^{-k_i}$, $k_i = 2 + i$
- `foundations/wake-geometry.md`—wake correction $2\lambda(1-q)/\omega^2 \approx 0.25\%$ at $\lambda = 0.1$
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `parameter-inventory.md`—$r_0$ classification (Derived); §3.1 $\lambda$ electroweak consistency check
- `open-questions-cassi-answers.md`—$r_{\text{Planck}}$ entry
- `cassi-physics.md`—gap derivation
