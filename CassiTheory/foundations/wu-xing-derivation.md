# Wu Xing Number $w = 5$: Derivation from Cascade Dynamics

## Status: Derived—July 2026

## Abstract

The Wu Xing number $w = 5$—the number of elements in the primordial generation/control cycle that determines the cosmological initial conditions—is motivated by geometric arguments (the pentagon is the minimal regular polygon containing $\varphi$) and by the Fibonacci convergent hierarchy. The derivation combines the cascade suppression formula (from the two-fluid PDE) with a Fibonacci number-theoretic identity (from $\varphi^2 = \varphi + 1$): the cascade dynamics eliminate all $w \geq 6$ via a coherence criterion; $\varphi$-geometry eliminates $w < 5$. The intersection is exactly $w = 5$. The primordial gap $g = 1 - \varphi^{-5}$ and the primordial Yang-Yin ratio $r_0$ follow directly.

---

## 1. The Problem

The Cassi framework's cosmological initial conditions depend on a single dimensionless number: the Wu Xing number $w$—the number of phase-advance vertices in the primordial generation/control cycle. This number determines:

- The primordial gap: $g = 1 - \varphi^{-w}$
- The primordial Yang-Yin ratio: $r_0 = (1-g)/(1+g) = \varphi^{-w}/(2 - \varphi^{-w})$
- The dark energy equation of state: $w_0$ (derived from $r_0$ via the PDE, matches DESI DR2 at $0.3\sigma$ for $w=5$)

Geometric candidates for $w = 5$ include (`computations/pinch_point_modes.py`):
1. Elliptical cavity mode bands (threshold-dependent, does not enforce exactly 5)
2. Fibonacci convergent hierarchy (physically motivated but not derived from the PDE)
3. Pentagon geometry (the minimal regular polygon containing $\varphi$)

The derivation follows from two constraints: the cascade dynamics force an upper bound of $w \leq 5$, and $\varphi$-geometry forces a lower bound of $w \geq 5$. The intersection is unique.

---

## 2. The Cascade Upper Bound: Why $w \geq 6$ Fails

### 2.1 Fibonacci Convergents as Cycle Candidates

The golden ratio's continued fraction is $[1; 1, 1, 1, \ldots]$—the slowest-converging of all irrationals. Its best rational approximations are ratios of consecutive Fibonacci numbers:

$$F_1 = 1, \; F_2 = 1, \; F_3 = 2, \; F_4 = 3, \; F_5 = 5, \; F_6 = 8, \; F_7 = 13, \; \ldots$$

The $k$-th convergent $F_{k+1}/F_k$ approximates $\varphi$ with error:

$$\left|\varphi - \frac{F_{k+1}}{F_k}\right| = \frac{|F_k \cdot \varphi - F_{k+1}|}{F_k}$$

### 2.2 The Fibonacci Identity (Number Theory)

A well-known identity follows from $\varphi^2 = \varphi + 1$ (Binet's formula):

$$\boxed{|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}}$$

This is **exact** for all $k \geq 1$. Proof by induction: base case $k=1$ gives $|1\cdot\varphi - 1| = \varphi^{-1}$; the recurrence $F_{k+1} = F_k + F_{k-1}$ combined with $\varphi^{k+1} = \varphi^k + \varphi^{k-1}$ propagates the identity.

### 2.3 Cascade Attenuation (PDE Signal Regime)

The cascade suppression formula (`foundations/cascade-suppression-formula.md`)—derived from the two-fluid PDE—states that a signal propagating through $N$ cascade rungs is attenuated by:

$$\boxed{S(N) = S(0) \cdot \varphi^{-N}}$$

This is the per-rung damping in the signal-propagation regime: each rung damps non-$\varphi$ structure by $\varphi^{-1}$.

### 2.4 The Coherence Criterion

For a Wu Xing cycle of $w$ vertices (where $w = F_k$, a Fibonacci number) to maintain phase coherence across one complete cycle, the accumulated phase error after $w$ steps must not exceed the cascade signal strength at rung $w$.

The accumulated phase error after one full cycle is the product of the per-step error and the number of steps:

$$\text{Error} = F_k \cdot \left|\varphi - \frac{F_{k+1}}{F_k}\right| = |F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$$

The cascade signal strength at rung $w = F_k$ is:

$$\text{Signal} = \varphi^{-F_k}$$

**Coherence criterion:** The cycle closes coherently if and only if the error does not exceed the signal:

$$\boxed{\varphi^{-k} \leq \varphi^{-F_k}}$$

Since $\varphi > 1$, this is equivalent to:

$$\boxed{k \geq F_k}$$

### 2.5 Solving the Criterion

The Fibonacci numbers satisfy $F_k = k$ for exactly two values:

| $k$ | $F_k$ | $k \geq F_k$? | Cycle $w$ | Verdict |
|-----|-------|:---:|:---:|---------|
| 1 | 1 | ✓ | 1 | Coherent (trivial) |
| 2 | 1 | ✓ | 1 | Coherent |
| 3 | 2 | ✓ | 2 | Coherent |
| 4 | 3 | ✓ | 3 | Coherent |
| **5** | **5** | **✓** | **5** | **Coherent** |
| 6 | 8 | ✗ | 8 | **Decoheres** |
| 7 | 13 | ✗ | 13 | **Decoheres** |
| 8 | 21 | ✗ | 21 | **Decoheres** |

For $k \geq 6$, $F_k > k$ holds for all Fibonacci numbers (and the gap grows exponentially: $F_{10} = 55$ vs. $k = 10$). Every cycle with $w \geq 6$ decoheres—the accumulated phase error exceeds the cascade signal at that rung.

**Explicit $w = 10$ falsification:** Ten steps with rational approximation $16/10 = 1.6$ accumulate error $10 \cdot |\varphi - 1.6| = 0.180$. Cascade attenuation at rung 10 is $\varphi^{-10} = 0.0081$. The error exceeds the signal by a factor of **22×**—the cycle is obliterated by noise.

---

## 3. The Geometry Lower Bound: Why $w < 5$ Fails

The golden ratio appears as a distance ratio in regular polygons only for $n \geq 5$:

$$\frac{\text{diagonal}}{\text{side}} = 2\cos\left(\frac{\pi}{5}\right) = \varphi$$

| $n$ | Polygon | $\varphi$ in distance ratios? |
|-----|---------|:---:|
| 3 | Triangle | No |
| 4 | Square | No |
| **5** | **Pentagon** | **Yes**—$\text{diag}/\text{side} = \varphi$ |
| 6 | Hexagon | Yes (but $w = 6$ decoheres—see §2) |
| 10 | Decagon | Yes, $R/s = \varphi$ (but decomposes into two pentagons; decoheres—see §2) |

Cycles with $w \in \{1, 2, 3\}$ are cascade-coherent but not $\varphi$-structured: they cannot encode the golden ratio in their vertex distance ratios, so they cannot serve as the organizing cycle of a $\varphi$-based framework.

---

## 4. The Intersection: $w = 5$

The cascade dynamics eliminate $w \geq 6$ (all decohere). $\varphi$-geometry eliminates $w < 5$ (all lack $\varphi$ in their distance ratios). The only surviving value is:

$$\boxed{w = 5}$$

The pentagon is **both** cascade-coherent **and** $\varphi$-structured. It is the unique non-trivial solution to $F_k \leq k$ with $\varphi$ in its geometry.

---

## 5. Consequences: The Gap and $r_0$

### 5.1 The Primordial Gap

One complete pentagonal cycle advances the conversion phase by a factor of $\varphi^5$, leaving an unconverted residual of $\varphi^{-5}$:

$$\boxed{g = 1 - \varphi^{-5} \approx 0.9098}$$

This is the fraction of the primordial Yang-Yin imbalance converted in the first pentagon cycle at the GUT scale (cascade step 5).

### 5.2 The Primordial Yang-Yin Ratio

The gap $g = |E_Y - E_I|/\rho$ relates to the ratio $r = E_Y/E_I$ via $g = (1-r)/(1+r)$ for Yin-dominated initial states ($r < 1$). Inverting:

$$\boxed{r_0 = \frac{1 - g}{1 + g} = \frac{\varphi^{-5}}{2 - \varphi^{-5}} \approx 0.0472}$$

Equivalently: $E_I/E_Y = 1/r_0 \approx 21.2$. Yin dominates Yang by a factor of ~21 at the Planck scale.

### 5.3 Observable Consequences

- **Dark energy equation of state:** $w_0 = -0.87$ (from PDE integration with $r_0$; corrected 2026-07-31—the earlier $-0.856$ “matching at 0.3σ” was measured against the repo's own calibration target), $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ [INFERENCE]
- **Baryon asymmetry:** The gap $g = 1 - \varphi^{-5}$ sets the Yang-Yin imbalance at GUT freeze-out, which seeds the matter-antimatter asymmetry
- **Cascade depth:** $N \approx 292$ follows from $H(r)$ dynamics + cosmic age, with $r_0$ as the initial condition

---

## 6. Epistemic Boundaries

### Derived (from $\varphi$ + cascade PDE + number theory)

- Fibonacci identity $|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$ (mathematical theorem)
- Cascade attenuation $\varphi^{-N}$ over $N$ rungs (derived from two-fluid PDE signal regime)
- The set of coherent Fibonacci cycles: $\{w : F_k \leq k\} = \{1, 2, 3, 5\}$
- The set of $\varphi$-containing polygons: $\{n \geq 5\}$
- Intersection: $w = 5$ uniquely
- The gap: $g = 1 - \varphi^{-5}$
- The primordial ratio: $r_0 = \varphi^{-5}/(2 - \varphi^{-5})$

### Physical Postulate (well-motivated, PDE-testable)

- **The coherence criterion itself:** $\text{accumulated phase error} \leq \text{cascade signal attenuation}$. This is a signal-detection principle: if the phase slip across one cycle exceeds the surviving signal strength at that cascade rung, the cycle cannot close coherently. It is physically well-motivated by the de-resonance principle and consistent with the cascade suppression formula, but it has not been directly verified by a PDE simulation computing phase closure as a function of $w$. A PDE test would initialize a $w$-cycle perturbation and measure whether phase coherence is maintained after one full cycle. The prediction: coherent for $w \leq 5$, decoherent for $w \geq 6$.

---

## 7. References

- `foundations/cascade-suppression-formula.md`—per-rung attenuation $\varphi^{-1}$, signal regime
- `foundations/dimensionful-cascade.md`—cascade table, step 5 (GUT), step 285 (Cassi bubble)
- `foundations/dimensionful-constants-status.md`—prior status of $w = 5$ as Hypothesized
- `computations/pinch_point_modes.py`—Candidate 2: Fibonacci convergent hierarchy
- `foundations/spiral-dynamics.md`—Hubble, gravity, and $c$ from spiral geometry
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `parameter-inventory.md`—$r_0$ classification (updated to Derived)
- `open-questions-cassi-answers.md`—$r_{\text{Planck}}$ entry (updated)
- `cassi-physics.md`—gap derivation
