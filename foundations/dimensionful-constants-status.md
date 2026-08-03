# Dimensionful Constants: Derivation Status of $c$, $\hbar$, and $G$

## Status: Hypothesized—July 2026

## Abstract

The Cassi framework derives all dimensionless parameters—couplings, mass ratios, mixing angles, and the PDE conversion rate $\lambda$—from the golden ratio $\varphi \approx 1.618$ and the two-fluid PDE. This document catalogues the constants that are **not yet derived**—the speed of light $c$, Planck's constant $\hbar$, and Newton's constant $G$—and clarifies the framework's parameter status.

**Bottom line:**

| Constant | Status | Why |
|----------|--------|-----|
| All dimensionless couplings ($\sin^2\theta_W$, $\alpha_{\text{GUT}}$, $\xi$, $r_0$, $w_0$, etc.) | **Derived** | $\varphi$-powers from cascade structure |
| $\lambda$ (PDE conversion rate) | **Derived** | $\lambda = 1/(2w) = 0.1$ with $w=5$ derived (`foundations/wu-xing-derivation.md`) |
| $v_0/M_{\text{Pl}}$ ratio | **Derived** | $\varphi^{-80}$ from cascade depth (5.3% residual) |
| **$c$**—geometric mechanism | **Closed** | $c = \lambda \cdot \ell_{\text{Pl}}$ (up to unit conversion); $\varphi^n$ cancellation exact, $\lambda=0.1$ derived |
| **$c$**—numerical value | **External** | Requires calibrating the sole dimensionful anchor $\ell_{\text{Pl}}$ in meters |
| **$\hbar$, $G$ individually** | **Not derivable** | Structurally inseparable from $\ell_{\text{Pl}}$ definition; one dimensionful anchor cannot determine three dimensionful constants independently |
| $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$ | **External** | One dimensionful scale governs all lengths via $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ |
| Current-epoch horizon rung $N \approx 292$ | **Empirical** | $N(t) = \log_\varphi(R_H(t) / \ell_{\text{Pl}}) = 291.54$ today; epoch-dependent state variable, uses empirical $H_0$, $\ell_{\text{Pl}}$ |

---

## 1. The Three Dimensionful Constants: $G$, $c$, $\hbar$

### 1.1 Why $\varphi$ alone cannot derive them

$\varphi \approx 1.618$ is a **dimensionless** number. Any theory that claims to derive dimensionful quantities from a dimensionless constant must either:

(a) Provide a second, independent dimensionful constant (a reference scale), or
(b) Show that a dimensionless ratio (e.g. $R_H / \ell_{\text{Pl}}$) is derivable from $\varphi$, which then anchors one dimensionful quantity in terms of another

Cassi takes path (a): $\ell_{\text{Pl}} = 1.616 \times 10^{-35}\,\text{m}$ is the sole dimensionful constant. The cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ distributes it across all scales. But $\ell_{\text{Pl}}$ itself is empirical—it enters through the $\sigma$-regularization of the two-fluid PDE (`gravity/quantum-gravity.md` §2) and is taken from standard physics:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}}$$

This is one equation with three unknowns. The framework does not (and mathematically cannot, from $\varphi$ alone) determine $c$, $\hbar$, and $G$ individually—only their combination $\ell_{\text{Pl}}$.

### 1.2 What is derivable vs. what is structural

The cascade framework has **one** dimensionful degree of freedom: the Planck length $\ell_{\text{Pl}}$. All length scales follow from $\ell_n = \ell_{\text{Pl}} \varphi^n$, and all dimensionless couplings are derived as $\varphi$-powers.

Within this structure, the three dimensionful constants $c$, $\hbar$, $G$ are **not independent**. They satisfy:

$$\ell_{\text{Pl}}^2 = \frac{\hbar G}{c^3}$$

The spiral dynamics mechanism provides an additional relation:

$$c = \lambda \cdot \ell_{\text{Pl}} \quad \text{(up to PDE-time-unit conversion)}$$

These two equations link $c$, $\hbar$, $G$, and $\ell_{\text{Pl}}$ but leave one degree of freedom unfixed. The cascade framework can only determine the **combination** $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$. Individual values of $c$, $\hbar$, and $G$ require measuring $\ell_{\text{Pl}}$ (or any one cascade rung) in physical units.

This is not a failing of the framework. It is a **structural limitation** shared by any theory with a single dimensionful anchor. The Cassi framework correctly identifies $\ell_{\text{Pl}}$ as that anchor, derives all dimensionless parameters, and expresses $c$ in terms of $\ell_{\text{Pl}}$ and the derived $\lambda$.

### 1.3 Status of "zero free parameters" claims

All dimensionless parameters are derived from $\varphi$: couplings ($\xi$, $\sin^2\theta_W$, $\alpha_{\text{GUT}}$), cosmological initial conditions ($w_0$, $r_0$), and the PDE conversion rate ($\lambda = 1/(2w) = 0.1$). The claim "zero free parameters among dimensionless couplings" holds. Three dimensionful constants ($c$, $\hbar$, $G$) remain external—they cannot be derived from a dimensionless constant without a reference scale.

---

## 2. The Conversion Rate $\lambda$—Derived

### 2.1 Derivation

The PDE conversion rate couples the Yang and Yin fields:

$$\partial_t E_Y \supset -\lambda(E_Y - \varphi E_I)$$

The rate is set by the pentagon structure: one complete Wu Xing cycle traverses $w = 5$ vertices, with each full Yang→Yin→Yang oscillation requiring 2 conversion events. The per-event rate is therefore:

$$\boxed{\lambda = \frac{1}{2w} = \frac{1}{2 \times 5} = 0.1}$$

With $w = 5$ derived from cascade dynamics + $\varphi$-geometry (`foundations/wu-xing-derivation.md`), $\lambda = 0.1$ follows directly.

**Number-theoretic consistency:** No $\varphi$-power can equal exactly $0.1$ (proven: every $\varphi$-power combination has form $A + B\varphi$ with $A,B \in \mathbb{Z}$, which cannot equal $1/10$). This is a **feature**: if $\lambda$ were a $\varphi$-power, the conversion rate would phase-lock with specific cascade rungs, causing resonant overlap between the pentagon's 5 coherence channels. Because $\lambda = 1/10$ is rational and maximally non-resonant with the $\varphi$-spaced cascade, the 5 channels remain distinct and non-overlapping.

**Status: Derived.** $\lambda = 1/(2w)$ with $w = 5$ derived.

### 2.2 The Origin of $w = 5$: Derived from Cascade Dynamics

The Wu Xing number $w = 5$ that appears in the gap $g = 1 - \varphi^{-5}$ follows from a two-filter argument (`foundations/wu-xing-derivation.md`):

**Upper bound (cascade dynamics):** The Fibonacci identity $|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$ gives the accumulated phase error after one $w = F_k$ cycle. The cascade attenuates signals by $\varphi^{-N}$ over $N$ rungs (derived from the two-fluid PDE). Cycle coherence requires the phase error not to exceed the signal: $\varphi^{-k} \leq \varphi^{-F_k}$, i.e., $k \geq F_k$. This holds only for $k \in \{1, 2, 3, 4, 5\}$, giving coherent Fibonacci cycles $w \in \{1, 2, 3, 5\}$. For $k \geq 6$, $F_k > k$, and the cycle decoheres—all $w \geq 6$ fail.

**Lower bound (geometry):** $\varphi$ appears as a distance ratio ($\text{diagonal}/\text{side} = 2\cos(\pi/5) = \varphi$) only in $n$-gons with $n \geq 5$. Cycles with $w < 5$ are cascade-coherent but lack $\varphi$ in their vertex distance ratios.

**Intersection:** $w = 5$ uniquely. The pentagon is the only cycle that is both cascade-coherent ($k \geq F_k$) and $\varphi$-structured.

The gap $g = 1 - \varphi^{-5}$ and the primordial ratio $r_0 = \varphi^{-5}/(2 - \varphi^{-5})$ follow directly.

**Status: Derived.** The cascade attenuation formula is derived from the two-fluid PDE. The Fibonacci identity is a proven number-theoretic theorem. The coherence criterion ($\text{error} \leq \text{signal}$) is a physical bridging postulate—well-motivated by the de-resonance principle, PDE-testable. The geometric lower bound is a mathematical identity. The unique intersection $w = 5$ follows from these two independent constraints.

### 2.3 Parameter Count

With $w=5$ and $\lambda = 1/(2w)$ both derived, all dimensionless parameters are fixed by $\varphi$ and the cascade:

| Category | Count | Examples |
|----------|-------|----------|
| **$\varphi$-powers (Derived)** | ~18 dimensionless | $\xi = \varphi^6$, $\sin^2\theta_W = \varphi^{-3}$, $\lambda = 1/10$, $r_0$, $w_0$ |
| **Cascade-span derived** | ~3 dimensionless | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$, $m_e/v_0$, $\eta$ |
| **External (Dimensionful)** | 3 | $G$, $c$, $\hbar$ |

**Zero free parameters among dimensionless couplings.** The three dimensionful constants ($c$, $\hbar$, $G$) remain external.

---

## 3. The Horizon Rung and the Dimensionful Bridge

### 3.1 What it is

The horizon rung $N(t)$ is the exponent relating the Hubble radius at epoch $t$ to the Planck length:

$$N(t) = \log_\varphi\left(\frac{R_H(t)}{\ell_{\text{Pl}}}\right) \approx 291.54 \text{ today}$$

This is the **only** dimensionless constraint linking the cascade structure to the dimensionful constants. It says: today's observable universe spans 292 $\varphi$-multiplications of the Planck length. The cascade itself is unbounded ($n \in \mathbb{Z}$—megacascade above, microcascade below, `foundations/dimensionful-cascade.md` §1), so there is no "cascade depth" constant; $N$ is a **state variable**—the horizon's rung coordinate, which evolves as $H(r)$ runs toward $\varphi$ (`two-fluid/run_hubble_pipeline.py`). Today $N = 291.54 \approx 291.5$, a half-step; 292 is the nearest-rung label. The number 292 is an empirical input—it depends on the measured $H_0$ and the measured $G$, $c$, $\hbar$.

### 3.2 What it constrains

If today's $N = 291.5$ could be **derived** from the Wu Xing gap $g = 1 - \varphi^{-5}$ or from the PDE's attractor dynamics, then the dimensionless ratio $R_H / \ell_{\text{Pl}} = \varphi^{291.5}$ would be predicted. What would be derived is the **epoch** (the initial condition $r_0$ that places today's horizon at this rung), not a constant—$N$ is a state variable that evolves with $H(r)$. Combined with the measured $R_H$ (or equivalently $H_0$), this would determine $\ell_{\text{Pl}}$—and thereby constrain the combination $\hbar G / c^3$.

No such derivation exists. The Wu Xing number $w = 5$ determines the gap $g$ and the ratio $r_0$ but does not independently fix the current horizon rung $N$. The cascade table in `foundations/dimensionful-cascade.md` assigns physical meanings to each rung by matching to observed scales—this is a **catalog**, not a derivation of $N$.

### 3.3 Vacuum energy consistency check

While $N$ cannot be derived from $\varphi$ alone, a non-trivial consistency exists. The observed vacuum energy density $\rho_\Lambda \approx 10^{-123}\,\rho_{\text{Pl}}$ is within an order of magnitude of:

$$\rho_\Lambda \approx \rho_{\text{Pl}} \times \varphi^{-2N}$$

With $N = 292$, $\varphi^{-2N} = \varphi^{-584} \approx 10^{-122.1}$, matching the observed $10^{-123}$ to within a factor of $\sim 8$—remarkable for a 123-order-of-magnitude quantity. Equivalently, inverting: if $\rho_\Lambda$ is determined by the cascade structure (specifically by the cumulative Wu Xing gap integrated over the cascade), then $N$ is constrained within a few rungs of 292. This is a consistency, not a derivation—it requires the empirical $\rho_\Lambda$—but it is the closest the framework comes to an independent prediction for $N$.

### 3.4 Pathways to deriving $N$—structurally blocked

Three candidate pathways for independently deriving $N$ from $\varphi$ are structurally blocked:

| Candidate | Status | Evidence |
|-----------|--------|----------|
| **Qi-gate closure**—Cascade ends when $(1-q_n)$ drops below a formation threshold | **Structurally blocked** | Bubble PDE test: $(1-q)$ has an irreducible floor $\approx 0.23$, never closes. Gate modulates spatial pattern, not convergence rate. |
| **Conversion-rate cascade termination**—$N$ emerges from the homogeneous ODE's $H(r)/\dot r$ integral | **Structurally blocked** | Homogeneous ODE gives $N \approx 9$, not ~292 (`computations/cascade_depth_integral.py`). $\lambda$ couples conversion and expansion at the same scale; the $10^{60}$ hierarchy requires a dimensionful input. |
| **De-resonance bandwidth**—Cascade spans the frequency range over which $\varphi$-spacing is stable against rational resonance | **Structurally blocked** | The rational approximation error drops as $\varphi^{-2N}$, always faster than the cascade resolution $\varphi^{-N}$. No $N$ yields distinguishable rational approximations. |

**Conclusion:** $N$ cannot be derived from $\varphi$ alone. It is a **state variable**—the horizon's rung coordinate, epoch-dependent as $H(r)$ evolves toward $\varphi$—not a derivable constant of the cascade. The three pathways are structurally blocked because each set out to derive a boundary the cascade does not have. The current-epoch horizon rung is the single empirical calibration that maps $\varphi^N$ to physical scales; the cascade framework requires exactly one dimensionful anchor, and the number of $\varphi$-multiplications between the Planck length (dimensionful, defined by $c, \hbar, G$) and the Hubble radius (observational) is an observation, not a theorem.

The primordial Yang-Yin ratio $r_{\text{Planck}}$ is **derived** (`foundations/wu-xing-derivation.md`). $\lambda = 1/(2w) = 0.1$ is derived (§2.1). $N$ (current-epoch horizon rung), $c$, $\hbar$, $G$ remain external.

### 3.5 Unit Anchors: the SI Second Fails the Rung Test

A candidate for anchoring the unit system without a human-scale measurement is the SI second itself: if the cesium hyperfine transition sat on a cascade rung, $\Delta\nu_{\text{Cs}}\,t_{\text{Pl}} = \varphi^{-n}$ would turn the defined unit of time into a prediction. The bare ratio is tantalizing:

$$\Delta\nu_{\text{Cs}}\,t_{\text{Pl}} = 4.956\times10^{-34} \;\Rightarrow\; n = -159.36 \approx -159.5 \quad (6.8\%)$$

Same residual class as the electroweak placement, same half-step pattern as $m_e/v_0$. But $\Delta\nu_{\text{Cs}}$ is a **compound** observable (Fermi contact, hydrogenic $Z=55$, $n=6$):

$$\Delta\nu_{\text{Cs}} = \frac{8}{3}\alpha^2\,\frac{m_e}{m_p}\,\frac{g_I}{2}\,\frac{Z^3}{n^3}\,F_{\text{rel}}(Z\alpha)\,(1-\delta)(1-\epsilon)\,cR_\infty$$

The per-factor rung ledger closes exactly on the observed $-159.36$:

| Factor | Rung $n$ | Nearest structure | Residual |
|--------|----------|-------------------|----------|
| $cR_\infty\,t_{\text{Pl}}$ (Rydberg) | $-132.79$ | $-133$ | 10.7% |
| $8/3$ | $+2.04$ | $+2$ | 1.9% |
| $\alpha^2$ | $-20.45$ | $-20.5$ | 2.5% |
| $m_e/m_p$ | $-15.62$ | $-15.5$ | 5.8% |
| $g_I/2$ (Cs-133) | $-2.07$ | $-2$ | 3.6% |
| $Z^3 = 55^3$ | $+24.98$ | $+25$ | 0.8% |
| $1/n^3$ | $-11.17$ | $-11$ | 8.5% |
| $F_{\text{rel}}(Z\alpha)$ | $-0.69$ |—| no claim |
| $(1-\delta)(1-\epsilon)$ (many-body) | $-3.60$ |—| no claim (factor 0.177) |
| **Sum** | **$-159.36$** |—| = observed exactly |

The $-159.5$ hit is a **cancellation**, not a claim: two factors have no rung structure at all ($F_{\text{rel}}$, and the 0.177 many-body factor carrying shielding, correlation, and nuclear-size corrections), and the structured factors carry residuals of 2–11%. Two further cautions: the $Z^3 \approx \varphi^{25}$ hit is a number-theory identity ($55 = F_{10}$, so $\log_\varphi(55^3) = 30 - 3\log_\varphi\sqrt5 = 24.98$), not a physical selection; and even the purest anchor, the Rydberg frequency, sits at $-132.79$—10.7% off $-133$, not the ~2% one might hope for. A derived second would require per-factor derivations ($\alpha$ at low energy, $m_e/m_p$, nuclear $g$-factors, many-electron corrections) the framework does not have.

**Conclusion:** atomic unit anchors do not survive decomposition. The external list remains $\{ \ell_{\text{Pl}},\, \text{current-epoch horizon rung},\, \text{human-unit calibration} \}$. One observation survives: $\alpha^{-1}$ runs from the GUT value $4\pi\varphi^3 = 53.2$ (rung 8.26) to $137.04$ (rung 10.22)—a $1.97 \approx 2$-rung traversal ($1.6\%$)—so the EM coupling's RG running spans two $\varphi$-rungs; structural, but not a derivation of a unit.

---

## 4. Derivation Pathways

### 4.1 Path for $c$—Closed in Structure

The mechanism for $c$ is **closed in structure**, though its numerical value in m/s still requires calibrating the framework's sole dimensionful anchor $\ell_{\text{Pl}}$ in physical units.

#### The closed form

The spiral-dynamics mechanism (`foundations/spiral-dynamics.md` §4) derives $c$ as the product of the effective conversion rate and coherence length at any cascade rung:

$$c \sim \lambda_{\text{eff}}(n) \cdot \ell_n$$

where $\lambda_{\text{eff}}(n) = \lambda \cdot \varphi^{-n}$ is the cascade-suppressed conversion rate and $\ell_n = \ell_{\text{Pl}} \cdot \varphi^n$ is the coherence length. The $\varphi^n$ factors cancel exactly:

$$c \sim (\lambda \cdot \varphi^{-n}) \cdot (\ell_{\text{Pl}} \cdot \varphi^n) = \lambda \cdot \ell_{\text{Pl}}$$

This cancellation is a **theorem**: the product is independent of $n$ for all cascade rungs, proving that $c$ is scale-invariant. The cancellation is verified analytically (`foundations/spiral-dynamics.md` §6.3).

With $\lambda = 1/(2w) = 0.1$ **derived** from $w=5$ (`foundations/wu-xing-derivation.md`), the expression becomes:

$$\boxed{c \propto \lambda \cdot \ell_{\text{Pl}}}$$

where the proportionality constant is the PDE-time-to-physical-time conversion (see §4.1.2 below). The expression involves no free dimensionless parameters—$\lambda$ is derived, and $\ell_{\text{Pl}}$ is the framework's sole dimensionful anchor.

#### What remains: PDE-time calibration

The conversion rate $\lambda = 0.1$ is expressed in PDE inverse-time units. To obtain $c$ in m/s requires calibrating $\tau_{\text{PDE}}$, the mapping between PDE time units and physical seconds.

This calibration is provided by the Hubble formula:

$$H_{\text{PDE}} = \frac{\lambda}{3}\frac{(\varphi - r)(1+r)}{r} + \frac{\lambda}{3}\varphi^{-2}$$

At the current epoch ($r \to \varphi$, $q \to 1$):

$$H_{\text{PDE}} = \frac{\lambda \varphi^{-2}}{3} \approx 0.0127 \text{ [PDE time units]}^{-1}$$

Equating with the observed $H_0 \approx 2.2 \times 10^{-18}$ s$^{-1}$ gives:

$$\tau_{\text{PDE}} = \frac{H_{\text{PDE}}}{H_0} \approx 5.8 \times 10^{15} \text{ s/PDE time unit}$$

This calibration uses the observed $H_0$ as dimensional input, which depends on the same distant-scale measurements that underpin $c$. The calibration is **consistent** but not a derivation from $\varphi$ alone.

#### Summary

$c$ is expressed in terms of $\lambda$ (derived) and $\ell_{\text{Pl}}$ (sole dimensionful anchor):

$$c = \frac{\lambda \cdot \ell_{\text{Pl}}}{\tau_{\text{PDE}}}$$

with $\tau_{\text{PDE}}$ calibrated from $H_0$. The $c$ mechanism is **closed in structure**: the scale-invariant product $\lambda_{\text{eff}} \cdot \ell_n$ is proven constant, $\lambda$ is derived, and the expression for $c$ has zero free dimensionless parameters.

**Status: Mechanism Closed.** The spiral-dynamics derivation reduces $c$ to $\lambda \cdot \ell_{\text{Pl}}$ with $\lambda$ derived. Numerical value in m/s requires calibrating $\ell_{\text{Pl}}$ in physical units—the framework's single dimensionful anchor. No additional degrees of freedom remain; the pathway from first principles to $c$ is fully specified.

### 4.2 Path for $\hbar$—Structural Gap

$\hbar$ cannot be derived from $\varphi$ alone, and this is not a temporary gap but a **structural limitation** of any theory with one dimensionful anchor.

#### What the SO(2) doublet winding provides

The spin derivation (`foundations/spin-fibonacci-spiral.md`) is **complete** for the dimensionless spin quantum number:

$$s = \Delta n = \frac{\Delta\Theta}{2\pi}$$

where $\Delta\Theta$ is the accumulated SO(2) doublet winding along a radial Fibonacci spiral. Boundary conditions quantize $s$ to $\{0, \frac12, 1, 2\}$. This derivation is at the **Derived** epistemic tier: it follows from the conversion term, the $\varphi$-scaled cascade, and single-valued boundary conditions.

However, spin quantization $s \in \{0, \frac12, 1, 2\}$ is **dimensionless**. The physical angular momentum is:

$$L = \hbar s$$

The dimensionful constant $\hbar$ converts the dimensionless winding number into units of angular momentum ($\text{kg}\cdot\text{m}^2/\text{s}$). This conversion factor is not derivable from the cascade geometry alone—it requires calibrating the energy-momentum scale of the field excitations in physical units.

#### The structural issue

$\hbar$ appears in the fundamental definition of the cascade's dimensionful anchor:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}}$$

This is one equation linking $\hbar$, $G$, and $c$. Even with $c = \lambda \cdot \ell_{\text{Pl}}$ (closed in structure, §4.1), the equation becomes:

$$\ell_{\text{Pl}}^2 = \frac{\hbar G}{(\lambda \cdot \ell_{\text{Pl}})^3} \quad \Longrightarrow \quad \ell_{\text{Pl}}^5 = \frac{\hbar G}{\lambda^3}$$

This still involves both $\hbar$ and $G$. The cascade framework provides only one dimensional equation ($\ell_{\text{Pl}}^2 = \hbar G / c^3$) and one derived relation ($c = \lambda \cdot \ell_{\text{Pl}}$). Two equations in three unknowns ($\ell_{\text{Pl}}$, $\hbar$, $G$) leaves one free degree. Or, equivalently: given $\ell_{\text{Pl}}$ as the sole dimensionful input, $c$ is determined in structure, but $\hbar$ and $G$ are not individually determined.

#### Blocked pathway

The minimum cascade action $S_{\text{min}}^{(n)} = E_n \cdot \tau_n$ whose scale-invariant limit would define $\hbar$ requires an independent energy scale (e.g., $M_{\text{Pl}}c^2$). This is circular: $M_{\text{Pl}} = \sqrt{\hbar c/G}$ already contains $\hbar$.

No alternative pathway is available. $\hbar$ is structurally inseparable from the definition of $\ell_{\text{Pl}}$ in a cascade framework with one dimensionful anchor.

**Status: Not derivable—structural limitation.** $\hbar$ is not separable from $\ell_{\text{Pl}}$ without independent measurements of $G$ and $c$. The SO(2) doublet winding quantizes the dimensionless spin $s$, but the conversion $L = \hbar s$ requires an external dimensionful reference. The framework correctly classifies $\hbar$ as External.

### 4.3 Path for $G$—Structural Gap

$G$ faces the same structural limitation as $\hbar$. It cannot be derived from $\varphi$ alone.

#### What $\xi = \varphi^6$ provides

The Qi-gravity coupling $\xi = \varphi^6$ is fully **derived** (`foundations/xi-derivation.md`). It modifies the effective gravitational constant:

$$G_{\text{eff}} = G \cdot \alpha\,(1 + \xi q)$$

with $\alpha$ the local Yang fraction ($\alpha_0 = \pi/\rho = \varphi^{-3}$ at the $\varphi$-fixed point; $\alpha_{\text{halo}} \approx 0.7$ in the galactic halo regime). This is a **dimensionless modification**—it tells us how $G$ is enhanced by local Qi coherence, but it does not determine the bare $G$ itself.

#### The structural issue

$G$ enters the cascade through $\ell_{\text{Pl}}$:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}}$$

To determine $G$ individually, one needs:
- The combination $\ell_{\text{Pl}}$ (requires deriving $N$ from $\varphi$, which is structurally blocked—see §3.4; $N$ is epoch-dependent, not a derivable constant), OR
- Independent measurements of $\hbar$ and $c$ combined with $\ell_{\text{Pl}}$

Neither pathway is available within the framework. The cascade structure determines the combination $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ (the sole dimensionful anchor) but cannot separate $G$ from $\hbar$.

#### The blocked pathway

Deriving $N$ from $\varphi$—thereby $\ell_{\text{Pl}} = R_H / \varphi^N$, then $G = \ell_{\text{Pl}}^2 c^3 / \hbar$—is structurally blocked by §3.4: $N$ is an epoch-dependent state variable, not a derivable constant. Even with $N$ in hand, $G$ would still depend on $\hbar$ through the Planck length formula.

**Status: Not derivable—structural limitation.** $G$ shares the same inseparability from $\ell_{\text{Pl}}$ as $\hbar$. The Qi-gravity coupling $\xi = \varphi^6$ is fully derived and modifies $G_{\text{eff}}$, but the bare $G$ remains an external anchor. The pathway is blocked, and no alternative exists.

### 4.4 Path for $\lambda$—Closed

$\lambda = 1/(2w) = 0.1$ is **derived** (§2.1). The Wu Xing number $w = 5$ follows from cascade dynamics + $\varphi$-geometry (`foundations/wu-xing-derivation.md`). This path is closed.

---

## 5. Status of Individual Claims

### 5.1 Claim-level status

| Document | Claim | Current status |
|----------|-------|-------------------|
| `gravity/quantum-gravity.md` §3 | $\sigma = \ell_{\text{Pl}}/\varphi^3$ is the regularization scale | $M_{\text{Pl}}$ remains external (dimensionful); the ratio $\sigma = \ell_{\text{Pl}}/\varphi^3$ is derived |
| `gravity/quantum-gravity.md` | "The Theory of Everything is complete" | All dimensionless parameters are derived; $c$, $\hbar$, $G$ remain external |
| `foundations/xi-derivation.md` §5 | "zero free parameters" | Zero free parameters among dimensionless couplings (λ derived via w=5) |
| `open-questions-cassi-answers.md` F5 | $\lambda$ is fixed by the measured Hubble | $\lambda = 1/(2w) = 0.1$, derived from $w=5$ |

### 5.2 Registry status

In `open-questions-cassi-answers.md`, the F5 entry lists $\lambda = 0.1$ as **Derived** (via $w=5$). $c$, $\hbar$, $G$ remain under the Hypothesized tier (pathways identified, not closed). The epistemic summary reflects these classifications.

### 5.3 Derivation pathway summary

| Constant | Status | Key result |
|----------|----------------|---------------|
| $\lambda$ | **Derived** | $\lambda = 1/(2w)$, $w=5$ derivation closed |
| $c$ | **Mechanism Closed** | $c = \lambda \cdot \ell_{\text{Pl}}$ from spiral dynamics; $\lambda$ derived; $\varphi^n$ cancellation exact |
| $\hbar$ | **Not derivable** | Structural: inseparable from $\ell_{\text{Pl}}$ definition; SO(2) winding quantizes $s$ but not $\hbar$ |
| $G$ | **Not derivable** | Structural: same inseparability; $\xi=\varphi^6$ modifies $G_{\text{eff}}$ but not bare $G$ |

### 5.4 Registry synchronization

- `parameter-inventory.md` §4 classifies $c$, $\hbar$, $G$ as External.
- `gravity/quantum-gravity.md` uses $\sigma = \ell_{\text{Pl}}/\varphi^3$ as the regularization scale; $M_{\text{Pl}}$ external.
- `foundations/xi-derivation.md` §5 asserts zero free parameters among dimensionless couplings.
- `open-questions-cassi-answers.md` F5 lists $\lambda = 0.1$ as Derived.
- `foundations/spiral-dynamics.md` §4 carries the $c$ mechanism (closed in structure).
- `foundations/dimensionful-constants-status.md` (this document) records the derivation status above.

---

## 6. References

- `parameter-inventory.md` §4—External constant classification
- `foundations/deriving-remaining-gaps.md` §5—parameter assessment status
- `gravity/quantum-gravity.md`—$\sigma$-regularization, Planck-scale status
- `foundations/xi-derivation.md`—$\xi = \varphi^6$, zero-free-parameter claims
- `foundations/unified-lagrangian.md`—Full Lagrangian, declares $\hbar = c = 1$, $\lambda = 0.1$
- `foundations/cassi-first-principles.md`—two-fluid PDE, conversion rate $\lambda = 1/(2w)$
- `foundations/dimensionful-cascade.md`—cascade table (292 = today's horizon rung), empirical $N$
- `open-questions-cassi-answers.md`—Epistemic registry (Q1–Q10, C1–C10, G1–G6, M1–M5, F1–F6, T1–T4)
- `foundations/spiral-dynamics.md`—Hubble, gravity, and c from spiral geometry
- `foundations/spin-fibonacci-spiral.md`—SO(2) doublet winding, spin quantization
- `foundations/wu-xing-derivation.md`—$w=5$ derivation, $\lambda = 1/(2w)$
- `cosmology/observational_constraints.md` §4—$\lambda$-independence of $w_a$
