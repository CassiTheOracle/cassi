# Wu Xing Number $w = 5$: Conditional Cascade–Geometry Construction

## Status: Derived conditional ($w = 5$ arithmetic, gap, $r_0$) under the selected construction; the organizing cycle and coherence interpretation are Hypothesized coordinate/phenomenological inputs; verified 2026-08-11 / $\lambda = 0.1$—asserted solver normalization and hypothesized Wu Xing linkage; conditional consequences only (§7) / Calibrated ($w_0$ via the DESI-anchored coupling form—ledger)

## Abstract

The Wu Xing number $w = 5$ is a conditional organizing-cycle construction, not a quantity derived from the canonical two-fluid state. In the selected golden-rotation coordinate, the accumulated error $E(w) = \min_p w|\varphi - p/w|$ passes the stipulated coherence threshold only for $w \in \{1, 2, 3, 5\}$—verified exhaustively for all $w \leq 2000$—and the regular-polygon chord arithmetic first contains $\varphi$ at $n = 5$. Continued-fraction optimality (Hurwitz) and the Fibonacci identity $|F_k\varphi - F_{k+1}| = \varphi^{-k}$ are mathematical results; their use as a cycle-selection rule is conditional on the added coordinate and threshold construction. Within that construction, the intersection is $w = 5$, and $g = 1 - \varphi^{-5}$ and $r_0 = \varphi^{-5}/(2-\varphi^{-5})$ follow arithmetically.

The compact phase coordinate, the interpretation of one vertex as one phase advance and one cascade rung, the one-turn closure rule, the coherence threshold, and the physical five-channel gate are Hypothesized coordinate/phenomenological inputs. The predicted coherent-cycle set is therefore conditional and is not a measured PDE result. The solver retains $\lambda = 0.1$ as an asserted normalization and hypothesized Wu Xing linkage; §7 audits its arithmetic and consequences without treating it as derived.

---

## 1. The Problem

The Cassi framework's cosmological initial conditions use a single dimensionless label: the Wu Xing number $w$. Here $w$ labels the vertices of a hypothesized primordial generation/control cycle. Interpreting those vertices as phase advances in a compact golden-rotation coordinate is an additional coordinate/phenomenological input, not a consequence of the two real density fields. Under that stipulated construction, $w$ determines:

- The primordial gap: $g = 1 - \varphi^{-w}$
- The primordial Yang-Yin ratio: $r_0 = (1-g)/(1+g) = \varphi^{-w}/(2 - \varphi^{-w})$
- The dark energy equation of state: $w_0 = -0.87$ (derived from $r_0$ via the PDE), $2\sigma$ from DESI $\approx -0.75 \pm 0.06$

Geometric candidates for $w = 5$ include (`computations/pinch_point_modes.py`):
1. Elliptical cavity mode bands (threshold-dependent, does not enforce exactly 5)
2. Fibonacci convergent hierarchy (mathematical candidate arithmetic conditional on the selected coordinate and threshold construction)
3. Pentagon geometry (the minimal regular polygon containing $\varphi$)

Within the stipulated coordinate, threshold, and $\varphi$-geometry construction, the upper and lower arithmetic bounds intersect at $w = 5$. This is a conditional construction result; it is not a derivation of a physical cycle count from the canonical PDE.

---

## 2. Conditional Criterion: Why $w \geq 6$ Fails

### 2.1 Best Rational Closures of the Golden Rotation

For the selected construction, each vertex is assigned an advance of $\varphi$ turns in an added compact golden-rotation coordinate (the de-resonant rotation of `principles/de-resonance-principle.md`). After $w$ steps the assigned coordinate advances by $w\varphi$ turns; closure means that this added coordinate is near an integer number $p$ of turns, so the rational ratio $p/w$ approximates $\varphi$. This compact phase, one-turn closure, and vertex interpretation are Hypothesized coordinate inputs; the following error is mathematical arithmetic conditional on them. The **accumulated phase error** after the stipulated cycle is the distance from $w\varphi$ to the nearest integer:

$$E(w) \;=\; \min_{p \in \mathbb{Z}}\, w\left|\varphi - \frac{p}{w}\right| \;=\; \|w\varphi\|$$

where $\|x\|$ is the distance from $x$ to the nearest integer.

The golden ratio's continued fraction is $[1; 1, 1, 1, \ldots]$—the slowest-converging of all irrationals. Its best rational approximations are ratios of consecutive Fibonacci numbers:

$$F_1 = 1, \; F_2 = 1, \; F_3 = 2, \; F_4 = 3, \; F_5 = 5, \; F_6 = 8, \; F_7 = 13, \; \ldots$$

**Best-approximation theorem (Hurwitz).** For every irrational $\alpha$, the integers $q$ with $\|q\alpha\|$ minimal among all $m \leq q$ are exactly the denominators of the convergents of $\alpha$ (best approximations of the second kind); the constant $1/\sqrt{5}$ in Hurwitz's bound $\|q\alpha\| < 1/(\sqrt{5}\,q)$ is optimal, and it is saturated by $\varphi$. For $\varphi$ the convergent denominators are the Fibonacci numbers, and every $w$ below the $(k{+}1)$-th convergent pays an error strictly larger than that convergent's:

$$\boxed{\|w\varphi\| > \|F_{k+1}\varphi\| = \varphi^{-(k+1)} \qquad \text{for all } 0 < w < F_{k+1}}$$

Cycle-size candidates for the stipulated coordinate closure are therefore the Fibonacci numbers themselves—**selected by mathematical optimality, conditional on the construction**. Any non-Fibonacci $w$ pays an error strictly larger than the next convergent's, and §2.5 shows that error fails the stipulated threshold.

### 2.2 The Fibonacci Identity (Number Theory)

A well-known identity follows from $\varphi^2 = \varphi + 1$ (Binet's formula):

$$\boxed{|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}}$$

This is **exact** for all $k \geq 1$. Proof by induction: base case $k=1$ gives $|1\cdot\varphi - 1| = \varphi^{-1}$; the recurrence $F_{k+1} = F_k + F_{k-1}$ combined with $\varphi^{k+1} = \varphi^k + \varphi^{k-1}$ propagates the identity.

For the selected coordinate, the convergent $p = F_{k+1}$ is the minimizer at $w = F_k$, so the accumulated error assigned to a Fibonacci cycle is exact:

$$E(F_k) = \|F_k \varphi\| = |F_k \varphi - F_{k+1}| = \varphi^{-k}$$

### 2.3 Cascade Attenuation (PDE Signal Regime)

The cascade suppression formula (`foundations/cascade-suppression-formula.md`)—derived from the two-fluid PDE—states that a signal propagating through $N$ cascade rungs is attenuated by:

$$\boxed{S(N) = S(0) \cdot \varphi^{-N}}$$

This is the per-rung damping in the signal-propagation regime: each rung damps non-$\varphi$ structure by $\varphi^{-1}$.

### 2.4 The Coherence Criterion

For the stipulated construction, each vertex is assigned one cascade-rung step, so the signal retained at the assigned rung $w$ is $\varphi^{-w}$. Treating that rung count as the closure point of the added coordinate and comparing it with one complete turn are Hypothesized coordinate/phenomenological inputs; the canonical two-fluid equations do not supply this identification.

**Coherence criterion (Hypothesized phenomenological rule, PDE-testable).** Under those inputs, a $w$-step cycle is assigned a coherent verdict if and only if

$$\boxed{E(w) \leq \varphi^{-w}}$$

i.e. the assigned phase slip $\|w\varphi\|$ does not exceed the stipulated cascade signal strength $\varphi^{-w}$ at the assigned rung. This is a chosen signal-detection threshold: it gives a conditional prediction that a cycle passes when the slip is below the threshold and fails when it is above. It is not derived from the canonical two-fluid state. A PDE test would need to implement the added coordinate and measure whether the proposed cycle observable is maintained; until then, the rule remains Hypothesized.

Because the rule is stipulated for **all** integers $w$, it screens non-Fibonacci cycles as arithmetic: §2.5 evaluates $E(w)$ exactly on the Fibonacci candidates (via §2.1–§2.2) and bounds it away from the threshold on every other $w$.

### 2.5 Solving the Conditional Criterion

**Fibonacci cycles.** For $w = F_k$, the criterion is $\varphi^{-k} \leq \varphi^{-F_k}$, equivalent (since $\varphi > 1$) to:

$$\boxed{k \geq F_k}$$

| $k$ | $F_k$ | $k \geq F_k$? | Cycle $w$ | Conditional criterion verdict |
|-----|-------|:---:|:---:|---------|
| 1 | 1 | ✓ | 1 | Coherent (trivial) |
| 2 | 1 | ✓ | 1 | Coherent |
| 3 | 2 | ✓ | 2 | Coherent |
| 4 | 3 | ✓ | 3 | Coherent |
| **5** | **5** | **✓** | **5** | **Coherent (at equality)** |
| 6 | 8 | ✗ | 8 | **Decoheres** |
| 7 | 13 | ✗ | 13 | **Decoheres** |
| 8 | 21 | ✗ | 21 | **Decoheres** |

The inequality $k \geq F_k$ holds for $k \in \{1, 2, 3, 4, 5\}$ and fails for all $k \geq 6$ ($F_k > k$ thereafter, with the gap growing exponentially: $F_{10} = 55$ vs. $k = 10$). The distinct cycle sizes that pass the stipulated arithmetic criterion are $w \in \{1, 2, 3, 5\}$; interpreting these passes as physically coherent cycles is the Hypothesized phenomenological reading. The $k = 5$ case is marginal, satisfying the assigned threshold at exact equality $E(5) = \varphi^{-5} = \text{signal}$.

**Non-Fibonacci cycles.** Every non-Fibonacci $w \geq 6$ fails the stipulated criterion. Write $F_k \leq w < F_{k+1}$ with $k \geq 5$. The best-approximation theorem gives $E(w) > \varphi^{-(k+1)}$. Since $w \geq 6$ implies $\varphi^{-(k+1)} \geq \varphi^{-w}$ (for $w \in \{6, 7\}$ with $k = 5$ this is $\varphi^{-6} \geq \varphi^{-w}$; for $k \geq 6$, $w \geq F_k \geq k+1$), the error strictly exceeds the threshold:

$$E(w) > \varphi^{-(k+1)} \geq \varphi^{-w} \qquad \text{for all non-Fibonacci } w \geq 6$$

The remaining non-Fibonacci value below the geometric bound, $w = 4$, fails by direct computation: $E(4) = 6 - 4\varphi \approx 0.472 > \varphi^{-4} \approx 0.146$. Combined with the Fibonacci table:

$$\boxed{\{w \in \mathbb{Z}^{+} : E(w) \leq \varphi^{-w}\} = \{1, 2, 3, 5\}}$$

**Numeric verification.** `computations/wu_xing_coherence_check.py` (run from repo root) checks the stipulated arithmetic for all $w \in [1, 2000]$: $\|w\varphi\| \leq \varphi^{-w}$ holds **only** for $w \in \{1, 2, 3, 5\}$ ($w = 5$ passes at equality, exact to the identity; the check uses a $10^{-12}$ float tolerance). These are conditional criterion results, not direct observations of physical phase coherence. Explicit values: $E(4) = 0.4721 > 0.1459$, $E(6) = 0.2918 > 0.0557$, $E(7) = 0.3262 > 0.0344$.

**Explicit $w = 10$ criterion counterexample:** Ten assigned steps with rational approximation $16/10 = 1.6$ accumulate error $10 \cdot |\varphi - 1.6| = 0.180$. The stipulated attenuation at assigned rung 10 is $\varphi^{-10} = 0.0081$. The error exceeds the threshold by a factor of **22×**; this is a counterexample within the conditional construction, not a direct physical falsification.

---

## 3. Conditional Geometry Selection: Why $w < 5$ Fails

As mathematical geometry, a regular $n$-gon first contains $\varphi$ in its chord ratios at $n = 5$ (verified numerically for $n = 3 \ldots 12$; `computations/wu_xing_coherence_check.py`), because

$$\frac{\text{diagonal}}{\text{side}} = 2\cos\left(\frac{\pi}{5}\right) = \varphi$$

| $n$ | Polygon | $\varphi$ in chord ratios? |
|-----|---------|:---:|
| 3 | Triangle | No—only ratio $1$ |
| 4 | Square | No—ratios $1$, $\sqrt{2}$, $2$ |
| **5** | **Pentagon** | **Yes**—$\text{diag}/\text{side} = \varphi$, $R/r = 2/\varphi$, $R/s = 1/(2\sin 36°) \approx 0.8507$ |
| 6 | Hexagon | No—ratios $1$, $\sqrt{3}/2$, $\sqrt{3}$, $2$ |
| 7–9, 11–12 | Heptagon … dodecagon | No—no chord ratio equals $\varphi$ |
| 10 | Decagon | Yes, $R/s = \varphi$ (but fails the stipulated criterion—see §2; decomposes into two pentagons) |

Cycles with $w \in \{1, 2, 3\}$ pass the stipulated arithmetic threshold but are not $\varphi$-structured: they cannot encode the golden ratio in their vertex distance ratios. Selecting the pentagon as the organizing cycle, and interpreting it as a physical five-channel gate, are additional Hypothesized phenomenological inputs; the chord-ratio result alone does not establish either claim. Within this construction, the lower candidate bound is $w \geq 5$.

---

## 4. The Intersection: $w = 5$

Within the stipulated criterion and $\varphi$-geometry construction, values $w \geq 6$ fail the arithmetic threshold and values $w < 5$ lack the selected chord ratio. The only surviving candidate is:

$$\boxed{w = 5}$$

The pentagon is the unique non-trivial candidate that passes the stipulated threshold while carrying the selected $\varphi$ chord ratio. Calling it physically coherent or identifying it as the organizing five-channel gate remains Hypothesized, rather than a consequence of the canonical PDE.

---

## 5. Consequences: The Gap and $r_0$

### 5.1 The Primordial Gap

Under the conditional pentagonal construction, one complete cycle is assigned a conversion factor of $\varphi^5$, leaving an unconverted residual of $\varphi^{-5}$:

$$\boxed{g = 1 - \varphi^{-5} \approx 0.9098}$$

Under this conditional construction, this is the fraction of the primordial Yang-Yin imbalance assigned to the first pentagon cycle at the GUT scale (n ≈ 13.3 for $M_{\text{GUT}} \approx 2\times10^{16}$ GeV; the cascade table's step-5 rung is the 1.1×10¹⁸ GeV scale).

### 5.2 The Primordial Yang-Yin Ratio

The gap $g = |E_Y - E_I|/\rho$ relates to the ratio $r = E_Y/E_I$ via $g = (1-r)/(1+r)$ for Yin-dominated initial states ($r < 1$). Inverting:

$$\boxed{r_0 = \frac{1 - g}{1 + g} = \frac{\varphi^{-5}}{2 - \varphi^{-5}} \approx 0.0472}$$

Equivalently: $E_I/E_Y = 1/r_0 \approx 21.2$. Yin dominates Yang by a factor of ~21 at the Planck scale.

### 5.3 Observable Consequences

- **Conditional dark energy equation of state:** $w_0 = -0.87$ (from PDE integration with $r_0$), $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ [INFERENCE]
- **Conditional baryon-asymmetry hypothesis:** the gap $g = 1 - \varphi^{-5}$ is mapped to the Yang-Yin imbalance at GUT freeze-out, which is hypothesized to seed the matter-antimatter asymmetry
- **Conditional cascade-depth mapping:** $N \approx 292$ follows from $H(r)$ dynamics + cosmic age, with $r_0$ as the initial condition

---

## 6. Epistemic Boundaries

### Derived conditional mathematics

The following are mathematical or arithmetic results after selecting the coordinate, cycle, and threshold construction. They do not establish that construction as a physical feature of the canonical two-fluid equations:

- Fibonacci identity $|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$ (mathematical theorem)
- Best-approximation optimality of the Fibonacci denominators for $\varphi$ (Hurwitz; mathematical theorem)
- Cascade attenuation $\varphi^{-N}$ over $N$ rungs (derived from the two-fluid PDE signal regime)
- For the stipulated $E(w)$ definition and threshold, the conditional criterion set $\{w : E(w) \leq \varphi^{-w}\} = \{1, 2, 3, 5\}$ (continued-fraction optimality + Fibonacci identity; exhaustive numeric check $w \leq 2000$)
- $\varphi$ first appears in regular $n$-gon chord ratios at $n = 5$ (verified $n = 3 \ldots 12$)
- Within the selected construction, the intersection candidate is $w = 5$
- Under that selected candidate, the gap is $g = 1 - \varphi^{-5}$
- Under that selected candidate, the primordial ratio is $r_0 = \varphi^{-5}/(2 - \varphi^{-5})$

### Hypothesized coordinate and phenomenological inputs

The canonical state is two real density fields. The following additions are not supplied by those equations:

- **Compact golden-rotation coordinate:** treating a density-plane diagnostic as a compact phase with a one-turn clock, and assigning a phase advance to each vertex
- **Cycle/rung identification:** assigning one vertex step to one cascade rung and treating the end of $w$ steps as one-turn closure
- **Coherence rule:** using $E(w) \leq \varphi^{-w}$ as a signal-detection threshold
- **Physical five-channel gate:** selecting the pentagon as the primordial organizing gate and reading a criterion pass as physical coherence
- **Predicted coherent cycles:** interpreting the conditional set $w \in \{1, 2, 3, 5\}$ and the $w \geq 6$ failures as phenomenological predictions; these are not measured PDE outcomes

These hypotheses are PDE-testable only after the additional coordinate and cycle observable are explicitly implemented. Until then, the coherence labels and the $w = 5$ organizing interpretation remain Hypothesized.

**Conditional construction inputs.**

1. **Added coordinate.** The $w$-vertex golden-rotation coordinate, its phase/turn language, and $E(w) = \|w\varphi\|$ are stipulated definitions.
2. **Phenomenological threshold.** The rule $E(w) \leq \varphi^{-w}$ and the one-rung-per-vertex assignment are Hypothesized inputs.
3. **$\varphi$-geometry selection.** The chord-ratio fact is mathematical; requiring the pentagon as the physical organizing five-channel gate is an additional hypothesis.

The tier for the cycle interpretation is **Hypothesized coordinate/phenomenological construction**. The Fibonacci identities, continued-fraction arithmetic, pentagon chord ratio, and the conditional evaluations of $g$ and $r_0$ are **Derived conditional on selecting that construction**. No compact phase clock, physical five-channel gate, or direct PDE coherence result is claimed here.

### Asserted solver/model choice

- $\lambda = 0.1$—asserted solver normalization and hypothesized Wu Xing linkage (§7); all rate, relaxation, and downstream numerical claims are conditional on this fixed choice

---

## 7. The Solver Conversion Normalization $\lambda = 0.1$

The PDE conversion coefficient—the coefficient of the linearized conversion term

$$\partial_t E_Y \supset -\lambda(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(E_Y - \varphi E_I)$$

(the code form in `two-fluid/cassi_two_fluid_3d_gpu.py`, gated by $(1-q)$)—is an inverse-time coefficient in the solver's chosen time units. The coherence result $w = 5$ and the numerical choice $\lambda = 0.1$ are separate statements. The solver retains $\lambda = 0.1$ as an asserted normalization and hypothesized Wu Xing linkage; the factor-by-factor reading below is conditional bookkeeping, not a derivation of a dynamical rate.

### 7.1 Why the factors do not derive a rate

**Equal-and-opposite doublet flux is a conservation statement, not a rate calibration.** Let

$$G = (1-q)(E_Y - \varphi E_I).$$

The conversion contribution has the form

$$\left.\partial_t E_Y\right|_{\mathrm{conv}} = -\lambda G, \qquad \left.\partial_t E_I\right|_{\mathrm{conv}} = +\lambda G.$$

Therefore $\partial_t(E_Y + E_I)|_{\mathrm{conv}} = 0$ for every value of $\lambda$. Equal-and-opposite flux fixes the sign pattern and the internal redistribution of the two real density fields; it does not fix the magnitude or the timescale. In particular, it does not mean that each channel carries half of a rate. The mass-conservation check in the companion script tests this symmetry for the chosen coefficient—it cannot determine that coefficient.

**The $1/2$ in the potential is a conventional normalization, not a dynamical rate.** The $\varphi$-attractor potential is written in the two-field form

$$V_{\text{attr}} = \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

(`foundations/unified-lagrangian.md` §1.2). The prefactor $1/2$ is a choice of potential normalization; when the equations are formed, $\lambda$ remains the free coefficient setting the strength in the selected time units. It neither assigns half a conversion budget to each channel nor supplies the missing inverse-time scale. A conventional prefactor can be changed together with the parameter or field normalization without changing the equal-and-opposite structure.

**One event per $w$-cycle leaves the timescale unspecified.** A statement that one conversion event occurs in one cycle supplies an event count and, at most, a dimensionless share such as $1/w$. If the cycle duration is $T_{\mathrm{cycle}}$, its frequency is set by $1/T_{\mathrm{cycle}}$; with a separately imposed half-share, a bookkeeping coefficient would be proportional to $1/(2T_{\mathrm{cycle}})$. Writing $T_{\mathrm{cycle}} = w\,\Delta t_{\mathrm{vertex}}$ makes the missing dependence explicit:

$$\lambda_{\mathrm{bookkeeping}} = \frac{1}{2w\,\Delta t_{\mathrm{vertex}}}.$$

Neither the coherence argument nor the event count specifies $\Delta t_{\mathrm{vertex}}$, the mapping from a vertex step to solver time, or the amount of density converted by an event. Setting $\Delta t_{\mathrm{vertex}} = 1$ in solver units and retaining the half-share gives the historical arithmetic $1/(2 \times 5) = 0.1$, but that assignment is an asserted timescale convention and hypothesized Wu Xing linkage—not a mathematical consequence of the cycle result.

The fixed value is rational, and the finite non-resonance searches below verify that $0.1$ does not coincide with the tested $\varphi$ powers or integer combinations. This is a property of the selected normalization, not a mechanism that selects its magnitude.

### 7.2 Conditional numeric audit

`computations/lambda_half_w_derivation.py` (run from the repository root) is a conditional arithmetic and solver-consequence audit. It keeps the historical $1/(2w)$ bookkeeping calculation for continuity, but it does not present that calculation as a derivation:

1. **Arithmetic bookkeeping:** $1/(2 \cdot 5) = 0.1$ exactly, and the $(1/2)(1/w)$ split multiplies to the fixed audit value. This is a numerical consistency check, not a rate derivation.
2. **Primordial ratio:** $r_0 = \varphi^{-5}/(2 - \varphi^{-5}) = 0.0472$ (§5.2), the $w$-conditioned initial ratio used in runs with the fixed $\lambda = 0.1$.
3. **Conditional attractor relaxation:** with $\lambda = 0.1$ held fixed and the attractor gate $(1-q_0) = \varphi^{-2}/3$, the two-field conversion ODE relaxes $\delta = E_Y - \varphi E_I$ as $e^{-\gamma t}$ with $\gamma = \lambda(1-q_0)(1+\varphi) = \lambda/3 = 1/30$ and $\tau = 30$. The integrated ODE reproduces the analytic decay to $1.1\times10^{-6}$ relative error (Euler truncation); this verifies a consequence of the chosen coefficient.
4. **Exact $\varphi$-algebra:** $(1-q_0)(1+\varphi) = (\varphi^{-2}/3)\cdot\varphi^2 = 1/3$ because $1 + \varphi = \varphi^2$.
5. **Chosen-value non-resonance:** no $\varphi^k$ ($-20 \le k \le 20$) and no $A + B\varphi$ ($|A|, |B| \le 1000$) equals the selected value $0.1$.
6. **Doublet symmetry:** the conversion term is equal-and-opposite in the two channels and conserves total mass exactly. This holds for any $\lambda$ and does not support a $1/2$ rate assignment.
7. **Conditional downstream consequences:** at $\lambda = 0.1$, the wake ratio $\Lambda_\varepsilon/\Lambda_Y = 1/\sqrt{1 - 2\lambda(1-q)/\omega^2} = 1.0025$—a 0.25% correction (`foundations/wake-geometry.md`)—and the kinetic/conversion ratio $\lambda/(c^2k^2) = 2.53\times10^{-3}$ (`foundations/cascade-suppression-formula.md`) reproduce the quoted values.

**Conditional audit inputs and tier.**

1. **Fixed solver normalization:** $\lambda = 0.1$ is supplied as the numerical input in solver time units; it is asserted, not independently measured or derived here.
2. **Conditional Wu Xing bookkeeping:** $w = 5$ comes from §4. The historical $1/(2w)$ arithmetic is retained only as a hypothesized linkage under the explicit unit and half-share conventions above; the cycle's coherence does not set the rate.
3. **Conditional ODE and gate:** the code-form conversion term, its gate, and the time unit are held fixed while consequences are checked.

The tier for $\lambda = 0.1$ is **Asserted solver normalization / hypothesized Wu Xing linkage**. The $w = 5$ coherence result, $g$, and $r_0$ retain their §2–§5 classification; the script's arithmetic, relaxation, non-resonance, conservation, and downstream checks are conditional on selecting $\lambda = 0.1$. No independent measurement or dimensional argument in this document fixes the coefficient.

## 8. References

- `foundations/cascade-suppression-formula.md`—per-rung attenuation $\varphi^{-1}$, signal regime; kinetic/conversion ratio at $\lambda = 0.1$
- `foundations/dimensionful-cascade.md`—cascade table, n ≈ 13.3 (GUT), step 285 (Cassi bubble)
- `foundations/dimensionful-constants-status.md`—status of $w = 5$; §2.1 conversion-rate reading ("2 conversion events per full oscillation")
- `computations/pinch_point_modes.py`—Candidate 2: Fibonacci convergent hierarchy
- `computations/wu_xing_coherence_check.py`—numeric verification: Fibonacci identity, criterion over $w \leq 2000$, chord-ratio check for $n = 3 \ldots 12$
- `computations/lambda_half_w_derivation.py`—conditional numeric audit of the retained $1/(2w)$ bookkeeping at $\lambda = 0.1$: $r_0$, the $\gamma = \lambda/3$ attractor time constant, non-resonance, doublet symmetry, and downstream consequences
- `foundations/spiral-dynamics.md`—Hubble, gravity, and $c$ from spiral geometry; §2.3 radial relaxation rate $\gamma = \lambda/3$
- `foundations/unified-lagrangian.md`—the $\varphi$-attractor potential $(\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$
- `foundations/xi-derivation.md`—$\xi = \varphi^6$, the quadratic degree 2
- `foundations/wa-pentagon-gate.md`—5-channel gate openness $b_i = \varphi^{-k_i}$, $k_i = 2 + i$
- `foundations/wake-geometry.md`—wake correction $2\lambda(1-q)/\omega^2 \approx 0.25\%$ at $\lambda = 0.1$
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `parameter-inventory.md`—$r_0$ classification (Derived); §3.1 $\lambda$ electroweak consistency check
- `open-questions-cassi-answers.md`—$r_{\text{Planck}}$ entry
- `cassi-physics.md`—gap derivation
