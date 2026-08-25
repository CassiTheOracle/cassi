# Dimensionful Constants: Derivation Status of $c$, $\hbar$, and $G$

## Status: Hypothesized ($c$, $\hbar$, $G$ external) / Mapped (fitted dimensionless exponents—ledger)—August 2026

## Abstract

The Cassi framework expresses dimensionless parameters as combinations of $\varphi$ and the two-fluid PDE. Their epistemic origins differ: $\xi$ under its quadratic-coupling input and several cascade identities have closed derivations, while the declared framework/C-class value $\lambda=0.1$ is a normalization/timescale convention. The actual `TwoFluid3DGPU` constructor default is $\lambda=0.02$; $\lambda=0.1$ is used only when explicitly passed for a named C-class experiment. The linkage $\lambda=1/(2w)$ is Hypothesized as a Wu Xing relation and requires an independently defined cycle time or dynamical closure; the Weinberg value $\sin^2\theta_W=\varphi^{-3}$ remains an asserted coupling boundary with a Calibrated crossing at $\mu_*=233$ GeV. This document catalogues the external dimensionful constants and keeps the dimensionless status distinctions explicit.

**Bottom line:**

| Constant | Status | Why |
|----------|--------|-----|
| Dimensionless parameters (mixed status) |—| $\varphi$-powers with status set by the Fit-Status Ledger; $\sin^2\theta_W$ is an asserted boundary, the declared framework/C-class convention $\lambda=0.1$ is explicit while the `TwoFluid3DGPU` constructor default is $\lambda=0.02$, the $w=5$ coherence intersection is conditional, and other entries are Derived, Calibrated, or Mapped |
| $\lambda$ (PDE conversion rate) | **Framework/C-class convention** | Declared normalization/timescale $\lambda=0.1$; the `TwoFluid3DGPU` constructor defaults to $\lambda=0.02$ and uses $0.1$ only when explicitly passed. The relation $\lambda=1/(2w)$ with $w=5$ is a Hypothesized Wu Xing linkage requiring an independently defined cycle time and dynamical closure |
| $v_0/M_{\text{Pl}}$ ratio | **Mapped** | Closest-power comparison $\varphi^{-80}$ to the measured ratio (5.3% residual) |
| **$c$**—geometric mechanism | **Closed conditional on framework/C-class convention and attenuation map** | $c=\lambda\cdot\ell_{\text{Pl}}/\tau_{\text{PDE}}$ (with $\tau_{\text{PDE}}$ the calibrated PDE-to-physical-time conversion); the $\varphi^n$ cancellation is Derived conditional on the Hypothesized attenuation map, with declared $\lambda=0.1$ supplied as framework normalization; the implementation default remains $\lambda=0.02$ |
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

The cascade framework has one dimensionful degree of freedom: the Planck length $\ell_{\text{Pl}}$. All length scales follow from $\ell_n = \ell_{\text{Pl}}\varphi^n$. Dimensionless quantities are frequently expressed as $\varphi$-powers, with their derivation status recorded separately.

Within this structure, the three dimensionful constants $c$, $\hbar$, $G$ are **not independent**. They satisfy:

$$\ell_{\text{Pl}}^2 = \frac{\hbar G}{c^3}$$

The spiral dynamics mechanism provides an additional relation conditional on
the Hypothesized inter-rung attenuation map and the solver-time convention:

$$c = \lambda \cdot \frac{\ell_{\text{Pl}}}{\tau_{\text{PDE}}} \quad \text{(with $\tau_{\text{PDE}}$ the calibrated PDE-to-physical-time conversion)}$$

These two equations link $c$, $\hbar$, $G$, and $\ell_{\text{Pl}}$ but leave one degree of freedom unfixed. The cascade framework can only determine the **combination** $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$. Individual values of $c$, $\hbar$, and $G$ require measuring $\ell_{\text{Pl}}$ (or any one cascade rung) in physical units.

This is a structural limitation shared by any theory with a single dimensionful anchor. The Cassi framework identifies $\ell_{\text{Pl}}$ as that anchor and expresses $c$ in terms of $\ell_{\text{Pl}}$ and the convention-fixed $\lambda$, conditional on the Hypothesized attenuation map; the status of dimensionless couplings remains governed by their individual derivation chains.

### 1.3 Status of "zero free parameters" claims

The closed subset of dimensionless parameters is fixed by $\varphi$ and the cascade after the declared framework/C-class convention $\lambda=0.1$ is supplied; the `TwoFluid3DGPU` constructor default $\lambda=0.02$ is a separate implementation choice. Other $\varphi$-power quantities retain their ledger status: $\sin^2\theta_W$ is an asserted boundary, $\mu_*$ is Calibrated, and fitted exponents are Mapped. The Wu Xing signal criterion and its $w=5$ intersection are conditional on the declared/Hypothesized per-rung signal map; the linkage $\lambda=1/(2w)$ remains Hypothesized because $w=5$ does not independently define a cycle time or rate. Three dimensionful constants ($c$, $\hbar$, $G$) remain external because a dimensionless constant cannot determine a reference scale.

---

## 2. The Conversion Rate $\lambda$—Solver Convention and Hypothesized Linkage

### 2.1 Convention and linkage

The PDE conversion rate couples the Yang and Yin fields:

$$\left.\partial_t E_Y\right|_{\mathrm{conv}} = -\lambda(1-q)(E_Y - \varphi E_I)$$

The pentagon geometry supplies the exact $\varphi$-structured candidate $w=5$, but it does not by itself select the physical coherence criterion or set a rate or its units. For the framework/C-class PDE convention, $\lambda=0.1$ is the declared normalization/timescale value; the `TwoFluid3DGPU` constructor default is $\lambda=0.02$, and $0.1$ is used only when explicitly passed. The proposed event-count relation is the Hypothesized linkage:

$$\boxed{\lambda = \frac{1}{2w} = \frac{1}{2 \times 5} = 0.1}$$

If an independently supplied cycle time and dynamical closure support this linkage, $w=5$ gives the declared framework value $\lambda=0.1$; the equality is therefore a hypothesis compatible with, not a derivation of, that convention and does not describe the `TwoFluid3DGPU` constructor default.

**Number-theoretic consistency:** The canonical convention uses rational $\lambda = 1/10$, not a $\varphi$-power (every $\varphi$-power combination has form $A + B\varphi$ with $A,B \in \mathbb{Z}$, which cannot equal $1/10$). Under the Hypothesized linkage, this rational choice can be read as non-resonant with the $\varphi$-spaced cascade, so the 5 channels remain distinct and non-overlapping; that mechanism reading is conditional on the linkage.

**Status: Framework/C-class convention / Hypothesized linkage.** $\lambda=0.1$ is fixed by the declared framework normalization, while `TwoFluid3DGPU` defaults to $\lambda=0.02$. The relation $\lambda=1/(2w)$ with $w=5$ is a Hypothesized Wu Xing linkage; it requires an independently defined cycle time and dynamical closure (factor interpretation: `foundations/wu-xing-derivation.md` §7).

### 2.2 The Origin of $w = 5$: Conditional Cascade-Signal Criterion

The Wu Xing number $w = 5$ that appears in the gap $g = 1 - \varphi^{-5}$ is selected by a two-filter argument (`foundations/wu-xing-derivation.md`). The argument combines exact mathematical identities with a conditional physical signal criterion.

**Upper bound (cascade signal criterion):** The Fibonacci identity $|F_k \cdot \varphi - F_{k+1}| = \varphi^{-k}$ gives the accumulated phase error after one $w = F_k$ cycle. The framework declares $d_i \approx \varphi^{-1}$ as a Hypothesized physical signal map for rung $i$; this per-rung profile is not derived from the canonical two-density PDE. Conditional on that map, the cumulative signal profile is the algebraic product $D_N = \prod_{i=1}^{N} d_i \approx \varphi^{-N}$. Cycle coherence then requires the phase error not to exceed the conditional signal: $\varphi^{-k} \leq \varphi^{-F_k}$, i.e., $k \geq F_k$. This holds only for $k \in \{1, 2, 3, 4, 5\}$, giving coherent Fibonacci candidates $w \in \{1, 2, 3, 5\}$ under the stated map. For $k \geq 6$, $F_k > k$, and the corresponding Fibonacci candidates fail this conditional criterion.

**Lower bound (geometry):** $\varphi$ appears as a distance ratio ($\text{diagonal}/\text{side} = 2\cos(\pi/5) = \varphi$) only in $n$-gons with $n \geq 5$. Cycles with $w < 5$ satisfy the conditional cascade criterion but lack $\varphi$ in their vertex distance ratios.

**Intersection:** Under the declared/Hypothesized signal map and the physical coherence criterion, $w = 5$ is the unique intersection. The pentagon is the only cycle that is both conditionally cascade-coherent and $\varphi$-structured. This is a conditional physical selection, not an unconditional derivation from the canonical PDE.

Once that conditional selection is made, the gap $g = 1 - \varphi^{-5}$ and the primordial ratio $r_0 = \varphi^{-5}/(2 - \varphi^{-5})$ follow by exact algebra.

**Status: Mixed—Derived identities / Hypothesized signal map / conditional intersection.** The Fibonacci identity and the pentagon distance-ratio identity are Derived mathematical identities. The per-rung profile $d_i \approx \varphi^{-1}$ is a declared/Hypothesized physical signal map, and $D_N \approx \varphi^{-N}$ is Derived algebra conditional on that map. The coherence criterion and the resulting $w = 5$ intersection are conditional on this map and the physical bridging postulate; the canonical two-density PDE does not by itself establish uniform attenuation or the $w = 5$ selection.

### 2.3 Parameter Count

With the conditional $w=5$ intersection and $\lambda = 0.1$ fixed by solver convention, the parameter catalog contains a mixture of closed, conditional, calibrated, mapped, asserted, and conventional dimensionless entries:

| Category | Status | Examples |
|----------|--------|----------|
| **Solver conventions and conditional $\varphi$-relations** | Convention / Derived conditional / Hypothesized | $\lambda = 0.1$ (solver normalization), $w=5$ (conditional signal/coherence intersection), $\xi = \varphi^6$ conditional on the quadratic-coupling input, $\alpha_0 = \varphi^{-3}$ |
| **Boundary assignments and anchors** | Asserted / Calibrated | $\sin^2\theta_W = \varphi^{-3}$; $\mu_* = 233$ GeV |
| **Cascade-span or fitted quantities** | Mapped / Calibrated | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$, $m_e/v_0$, $\eta$, $w_0$ |
| **External dimensionful constants** | External | $G$, $c$, $\hbar$ |

The phrase “zero additional physical dimensionless parameters” applies only to the closed subset after its named inputs and the one solver-normalization input $\lambda=0.1$ are supplied; it does not mean that the Wu Xing signal map or the $w=5$ intersection is derived from the canonical PDE, nor does it change the status of asserted boundaries and calibrated anchors.

---

## 3. The Horizon Rung and the Dimensionful Bridge

### 3.1 What it is

The horizon rung $N(t)$ is the exponent relating the Hubble radius at epoch $t$ to the Planck length:

$$N(t) = \log_\varphi\left(\frac{R_H(t)}{\ell_{\text{Pl}}}\right) \approx 291.54 \text{ today}$$

This is the **only** dimensionless constraint linking the cascade structure to the dimensionful constants. It says: today's observable universe spans 292 $\varphi$-multiplications of the Planck length. The cascade itself is unbounded ($n \in \mathbb{Z}$—megacascade above, microcascade below, `foundations/dimensionful-cascade.md` §1), so there is no "cascade depth" constant; $N$ is a **state variable**—the horizon's rung coordinate, which evolves as $H(r)$ runs toward $\varphi$ (`two-fluid/run_hubble_pipeline.py`). Today $N = 291.54 \approx 291.5$, a half-step; 292 is the nearest-rung label. The number 292 is an empirical input—it depends on the measured $H_0$ and the measured $G$, $c$, $\hbar$.

### 3.2 What it constrains

If today's $N = 291.5$ could be **derived** from the Wu Xing gap $g = 1 - \varphi^{-5}$ or from the PDE's attractor dynamics, then the dimensionless ratio $R_H / \ell_{\text{Pl}} = \varphi^{291.5}$ would be predicted. What would be derived is the **epoch** (the initial condition $r_0$ that places today's horizon at this rung), not a constant—$N$ is a state variable that evolves with $H(r)$. Combined with the measured $R_H$ (or equivalently $H_0$), this would determine $\ell_{\text{Pl}}$—and thereby constrain the combination $\hbar G / c^3$.

No such derivation exists. Under the conditional Wu Xing selection, $w = 5$ determines the gap $g$ and the ratio $r_0$ but does not independently fix the current horizon rung $N$. The cascade table in `foundations/dimensionful-cascade.md` assigns physical meanings to each rung by matching to observed scales—this is a **catalog**, not a derivation of $N$.

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

The primordial Yang-Yin ratio $r_{\text{Planck}}$ is **Derived conditional on the Wu Xing selection** (`foundations/wu-xing-derivation.md`). The canonical $\lambda = 0.1$ is a solver normalization/timescale convention; the relation $\lambda = 1/(2w)$ is Hypothesized (§2.1). The Fibonacci and geometric identities remain Derived, while the signal map and $w=5$ intersection remain conditional. $N$ (current-epoch horizon rung), $c$, $\hbar$, $G$ remain external.

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

**Conclusion:** atomic unit anchors do not survive decomposition. The external list remains $\{ \ell_{\text{Pl}},\, \text{current-epoch horizon rung},\, \text{human-unit calibration} \}$. One observation survives: the EM coupling's RG running from the φ-boundary to zero momentum spans $\alpha_{\text{em}}^{-1}$: $225$ at $M_{\text{GUT}}$ (rung $11.26$, with $\sin^2\theta_W = \varphi^{-3}$) $\to$ $128.95$ at $m_Z$ $\to$ $137.04$ at zero momentum (rung $10.22$)—about one $\varphi$-rung overall; structural, but not a derivation of a unit (`standard-model/sm-radiative-corrections.md` §3–4).

### 3.6 The seed units: the closest thing to a derived unit

The seed arm width (`foundations/wake-geometry.md` §3b) is the framework's
origin-unit: the coefficient is derived from the phyllotaxis (five arms tile
the azimuth), while the dimensionful core is the single external anchor. The
seed pentagon at rung 0 defines a consistent natural-unit trio
(`computations/seed_arm_width.py`):

$$w_{\text{seed}} = \frac{2\pi}{5}\,\ell_{\text{Pl}} \approx 2.03\times10^{-35}\ \text{m}, \qquad t_{\text{seed}} = \frac{2\pi}{5}\,t_{\text{Pl}} \approx 6.77\times10^{-44}\ \text{s}, \qquad m_{\text{seed}} = \frac{5}{2\pi}\,M_{\text{Pl}} \approx 1.73\times10^{-8}\ \text{kg}$$

with $w_{\text{seed}} = c\,t_{\text{seed}}$ and $m_{\text{seed}} w_{\text{seed}} c = \hbar$ exactly—a closed unit system at the cascade's origin. This is as close as a dimensionless constant can come: $\varphi$ fixes the coefficients ($2\pi/5$ from the pentagon, $5/2\pi$ from its inverse), while the dimensionful content remains the sole external anchor $\ell_{\text{Pl}}$ (§1.1). The SI units reduce to the same anchors and fail the rung test: the second through cesium (§3.5, decomposition fails); the meter and kilogram are definitions over $c$, $h$, $\Delta\nu_{\text{Cs}}$ (no independent content); and the human-unit placements—the meter at rung 166.47 (1.5% from the half-rung 166.5, an Earth-scale coincidence), the second at 206.9, the kilogram at −36.7—are formation and definitional observations without mechanism, the epoch-observation class. The external list stands at $\{ \ell_{\text{Pl}},\, \text{current-epoch horizon rung},\, \text{human-unit calibration} \}$; what the seed units add is the geometric content of the anchor itself.

---

## 4. Derivation Pathways

### 4.1 Formal structural path for $c$—physical closure open

The mechanism supplies a **formal structural cancellation conditional on the
solver convention and the Hypothesized attenuation map**. It does not close
the physical value of $c$: converting the PDE-time expression to m/s requires
an independently justified time calibration in addition to the empirical
anchor $\ell_{\text{Pl}}$.

#### Formal scale-invariant form

The spiral-dynamics mechanism (`foundations/spiral-dynamics.md` §4) gives a
conditional expression for $c$ as the product of the effective conversion rate
and coherence length at any cascade rung, after adopting its Hypothesized
inter-rung attenuation map:

$$c \sim \lambda_{\text{eff}}(n) \cdot \ell_n$$

where $\lambda_{\text{eff}}(n) = \lambda \cdot \varphi^{-n}$ is the
Hypothesized constitutive attenuation map and
$\ell_n = \ell_{\text{Pl}} \cdot \varphi^n$ is the coherence length. The
$\varphi^n$ factors cancel exactly:

$$c \sim (\lambda \cdot \varphi^{-n}) \cdot (\ell_{\text{Pl}} \cdot \varphi^n) = \lambda \cdot \ell_{\text{Pl}}$$

This cancellation is **Derived conditional on the Hypothesized constitutive
map**: the product is independent of $n$ for all cascade rungs once that map is
adopted. The algebra is verified analytically
(`foundations/spiral-dynamics.md` §6.3); the attenuation map itself is not
derived by this cancellation.

Using the canonical solver convention $\lambda = 0.1$ (with the linkage $\lambda = 1/(2w)$ only Hypothesized), the formal expression becomes:

$$\boxed{c_{\mathrm{formal}} \propto \lambda \cdot \ell_{\text{Pl}}}$$

where the proportionality constant is the PDE-time-to-physical-time conversion
(see §4.1.2 below). This expression has no fitted dimensionless parameter once
the solver convention and attenuation map are declared, but it is not a
physical closure for $c$.

#### What remains: PDE-time calibration

The conversion rate $\lambda = 0.1$ is expressed in PDE inverse-time units. To obtain $c$ in m/s requires calibrating $\tau_{\text{PDE}}$, the mapping between PDE time units and physical seconds.

This calibration is provided by the Hubble formula:

$$H_{\text{PDE}} = \frac{\lambda}{3}\frac{(\varphi - r)(1+r)}{r} + \frac{\lambda}{3}\varphi^{-2}$$

(The 1/3 is **Derived conditional on the assumed spatial dimension $d = 3$** as the isotropic dimension factor $1/d$—`cosmology/cosmology-from-phi.md` §1, `computations/verify_h_form_one_third.py`; the dimensional identification remains Hypothesized in `foundations/why-three-dimensions.md`; the $\lambda\varphi^{-2}$ rate stays **Asserted**; the Lagrangian's T₀₀ at equilibrium gives 0 or (g/4)φ², never λφ⁻²/3.)

At the current epoch ($r \to \varphi$), the imbalance parameter $\epsilon$ tends to zero. At finite density the gate remains $q=q_{\mathrm{eq}}(\rho)<1$; reaching $q \to 1$ additionally requires the high-density limit $\rho \gg \varphi^{-1}$:

$$H_{\text{PDE}} = \frac{\lambda \varphi^{-2}}{3} \approx 0.0127 \text{ [PDE time units]}^{-1}$$

Equating with the observed $H_0 \approx 2.2 \times 10^{-18}$ s$^{-1}$ gives:

$$\tau_{\text{PDE}} = \frac{H_{\text{PDE}}}{H_0} \approx 5.8 \times 10^{15} \text{ s/PDE time unit}$$

This calibration uses the observed $H_0$ as dimensional input, which depends on the same distant-scale measurements that underpin $c$. The calibration is **consistent** but not a derivation from $\varphi$ alone.

#### Summary

The formal conversion is expressed using the convention-fixed $\lambda$, the
empirical anchor $\ell_{\text{Pl}}$, and an empirical time-scale input:

$$c_{\mathrm{formal}} = \frac{\lambda \cdot \ell_{\text{Pl}}}{\tau_{\text{PDE}}}$$

with $\tau_{\text{PDE}}$ calibrated from $H_0$ as an empirical time-scale input. Using $H_{\text{PDE}}\approx0.0127$ and $H_0\approx2.2\times10^{-18}\ {\rm s}^{-1}$ gives $\tau_{\text{PDE}}\approx5.8\times10^{15}$ s per PDE time unit. Combined with $\ell_{\text{Pl}}=1.616\times10^{-35}$ m and the convention $\lambda=0.1$, the displayed conversion yields only $c_{\mathrm{formal}}\approx2.8\times10^{-52}$ m/s, not the measured speed of light. The relation is therefore a formal structural cancellation, not a physical closure. A physical $c$ requires an independently justified PDE-to-physical-time calibration or an equivalent measured velocity; both $H_0$ and $\ell_{\text{Pl}}$ are empirical inputs.

**Status: Formal structural relation; physical $c$ closure open.** The
spiral-dynamics pathway reduces the scale dependence to
$\lambda_{\mathrm{eff}}(n)\ell_n=\lambda\ell_{\text{Pl}}$ conditional on the
Hypothesized constitutive attenuation map. The value $\lambda=0.1$ is supplied
by solver convention, while the implementation default is $\lambda=0.02$.
Neither this cancellation nor the Hubble calibration derives the measured
$c$; no claim of a closed physical $c$ pathway is made.

### 4.2 Path for $\hbar$—Structural Gap

$\hbar$ cannot be derived from $\varphi$ alone, and this is not a temporary gap but a **structural limitation** of any theory with one dimensionful anchor.

#### What the canonical state provides—and the optional spin extension adds

The canonical Cassi state is the real density pair $(E_Y,E_I)$. Its derived
density-plane angle is a coordinate representation of those two real fields; it
does not provide an independent compact phase, a fixed winding per cascade rung,
a half-angle lift, or spin quantization.

`foundations/spin-fibonacci-spiral.md` defines a separate **Hypothesized**
conditional extension. It adds a compact coordinate $\chi$, chooses the
one-turn convention $\Delta\chi=2\pi\Delta n$, and introduces the half-angle
$\vartheta=\chi/2$. If that added representation is accepted, its proposed
dimensionless spin label is

$$
\boxed{
s=\frac{\Delta\vartheta}{2\pi}
=\frac{\Delta\chi}{4\pi}
=\frac{\Delta n}{2}.}
$$

The algebra of this formula is exact conditional on those added postulates.
The compact phase, its winding span $\Delta n$, the half-angle representation,
and the proposed values $s\in\{0,\frac12,1,2\}$ all carry
**Hypothesized conditional extension** status. None is supplied by the
canonical conversion.

The proposed spin label is dimensionless. The physical angular momentum is:

$$L = \hbar s$$

The dimensionful constant $\hbar$ converts this conditional dimensionless label
into units of angular momentum
($\text{kg}\cdot\text{m}^2/\text{s}$). This conversion factor is not derivable
from the cascade geometry alone—it requires calibrating the energy-momentum
scale of the field excitations in physical units.

#### The structural issue

$\hbar$ appears in the fundamental definition of the cascade's dimensionful anchor:

$$
\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}}
$$

This is one equation linking $\hbar$, $G$, and $c$. Even with
$c = \lambda \cdot \ell_{\text{Pl}}/\tau_{\text{PDE}}$ (closed conditional on
solver convention and attenuation map, §4.1, with $\tau_{\text{PDE}}$ the
calibrated PDE-to-physical-time conversion), the equation becomes:

$$
\ell_{\text{Pl}}^2
=\frac{\hbar G}{\left(\lambda \cdot \ell_{\text{Pl}}/\tau_{\text{PDE}}\right)^3}
=\frac{\hbar G\,\tau_{\text{PDE}}^3}{\lambda^3\ell_{\text{Pl}}^3}
\quad\Longrightarrow\quad
\ell_{\text{Pl}}^5=\frac{\hbar G\,\tau_{\text{PDE}}^3}{\lambda^3}.
$$

This still involves both $\hbar$ and $G$. The cascade framework provides only
one dimensional equation ($\ell_{\text{Pl}}^2 = \hbar G / c^3$) and one
structural relation ($c = \lambda \cdot \ell_{\text{Pl}}/\tau_{\text{PDE}}$).
With the calibrated $\tau_{\text{PDE}}$ treated as the PDE-to-physical-time
conversion, two equations in three unknowns ($\ell_{\text{Pl}}$, $\hbar$, $G$)
leave one free degree. Or, equivalently: given $\ell_{\text{Pl}}$ as the sole
dimensionful input, $c$ is determined in structure once the solver convention
for $\lambda$ and the time conversion are supplied, but $\hbar$ and $G$ are not
individually determined.

#### Blocked pathway

The minimum cascade action $S_{\text{min}}^{(n)} = E_n \cdot \tau_n$ whose scale-invariant limit would define $\hbar$ requires an independent energy scale (e.g., $M_{\text{Pl}}c^2$). This is circular: $M_{\text{Pl}} = \sqrt{\hbar c/G}$ already contains $\hbar$.

No alternative pathway is available. $\hbar$ is structurally inseparable from the definition of $\ell_{\text{Pl}}$ in a cascade framework with one dimensionful anchor.

**Status: Not derivable—structural limitation.** $\hbar$ is not separable from $\ell_{\text{Pl}}$ without independent measurements of $G$ and $c$. The optional compact-phase extension supplies only a conditional dimensionless spin label; it does not determine the conversion $L=\hbar s$ or the value of $\hbar$. The framework therefore classifies $\hbar$ as External.

### 4.3 Path for $G$—Structural Gap

$G$ faces the same structural limitation as $\hbar$. It cannot be derived from $\varphi$ alone.

#### What $\xi = \varphi^6$ provides

The Qi-gravity coupling $\xi = \varphi^6$ is **Derived conditional on the
quadratic-coupling input** (`foundations/xi-derivation.md`). It modifies the
effective gravitational constant:

$$G_{\text{eff}} = G \cdot \alpha\,(1 + (\varphi^{6}-1)q)$$

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

**Status: Not derivable—structural limitation.** $G$ shares the same inseparability from $\ell_{\text{Pl}}$ as $\hbar$. The Qi-gravity coupling $\xi = \varphi^6$ is **Derived conditional on the quadratic-coupling input** and modifies $G_{\text{eff}}$, but the bare $G$ remains an external anchor. The pathway is blocked, and no alternative exists.

### 4.4 Status of $\lambda$

$\lambda = 0.1$ is the solver's normalization/timescale convention. The equality $\lambda = 1/(2w)$ with $w = 5$ is a Hypothesized Wu Xing linkage; closing it requires an independently defined cycle time and dynamical closure. This path is therefore not a derivation of $\lambda$.

---

## 5. Status of Individual Claims

### 5.1 Claim-level status

| Document | Claim | Current status |
|----------|-------|-------------------|
| `gravity/quantum-gravity.md` §3 | $\sigma = \ell_{\text{Pl}}/\varphi^3$ is the regularization scale | $M_{\text{Pl}}$ remains external (dimensionful); $\sigma = \ell_{\text{Pl}}/\varphi^3$ is **Derived conditional** on the noise–signal identification, the Hypothesized cascade-dephasing family ($d_i=\varphi^{-i-\delta}$), and the selected $d=3$ domain; only the $\varphi^{-3}$ arithmetic follows once $\delta=3$ is selected. Not a derived gravity prediction |
| `gravity/quantum-gravity.md` | "The Theory of Everything is complete" | The closed dimensionless subset has derived origins; $\sin^2\theta_W$ remains an asserted boundary, while $c$, $\hbar$, $G$ remain external |
| `foundations/xi-derivation.md` §5 | "zero free parameters" | Zero free inputs within the closed subset after the quadratic-coupling condition; asserted boundaries and mapped entries retain their ledger statuses |
| `open-questions-cassi-answers.md` F5 | $\lambda$ is fixed by the measured Hubble | $\lambda = 0.1$ is the solver normalization/timescale convention; $\lambda = 1/(2w)$ is a Hypothesized Wu Xing linkage requiring independent cycle-time/dynamical closure |

### 5.2 Registry status

In `open-questions-cassi-answers.md`, the F5 entry records $\lambda = 0.1$ as the solver normalization/timescale convention and $\lambda = 1/(2w)$ as a Hypothesized Wu Xing linkage requiring independent cycle-time/dynamical closure. $c$, $\hbar$, $G$ remain under the Hypothesized tier (pathways identified, not closed). The epistemic summary reflects these classifications.

### 5.3 Derivation pathway summary

| Constant | Status | Key result |
|----------|----------------|---------------|
| $\lambda$ | **Solver convention / Hypothesized linkage** | $\lambda = 0.1$ by canonical normalization; $\lambda = 1/(2w)$ with $w=5$ requires independent cycle-time/dynamical closure |
| $w=5$ | **Conditional physical selection** | Fibonacci and pentagon identities are Derived; the signal map $d_i \approx \varphi^{-1}$ is declared/Hypothesized, and the $w=5$ intersection is conditional on that map and the coherence criterion |
| $c$ | **Mechanism Closed conditional on solver convention and attenuation map** | $c = \lambda \cdot \ell_{\text{Pl}}/\tau_{\text{PDE}}$ from the spiral-dynamics pathway, with $\tau_{\text{PDE}}$ the calibrated PDE-to-physical-time conversion; $\lambda$ is convention-fixed, while the $\varphi^n$ cancellation is Derived conditional on the Hypothesized attenuation map |
| $\hbar$ | **Not derivable** | Structural: inseparable from $\ell_{\text{Pl}}$ definition; the optional compact-phase construction supplies only a conditional dimensionless spin label and does not determine $\hbar$ |
| $G$ | **Not derivable** | Structural: same inseparability; $\xi=\varphi^6$ modifies $G_{\text{eff}}$ but not bare $G$ |

### 5.4 Registry synchronization

- `parameter-inventory.md` §4 classifies $c$, $\hbar$, $G$ as External.
- `gravity/quantum-gravity.md` uses $\sigma = \ell_{\text{Pl}}/\varphi^3$ as the regularization scale; $M_{\text{Pl}}$ external.
- `foundations/xi-derivation.md` §5 and the compact references carry the closed-subset zero-free-input claim; the Weinberg boundary is recorded as asserted.
- `open-questions-cassi-answers.md` F5 records $\lambda = 0.1$ as the solver normalization/timescale convention and $\lambda = 1/(2w)$ as a Hypothesized linkage requiring independent cycle-time/dynamical closure.
- `foundations/spiral-dynamics.md` §4 carries the $c$ pathway, closed conditional on solver normalization and the Hypothesized attenuation map.
- `foundations/dimensionful-constants-status.md` (this document) records the derivation status above.

---

## 6. References

- `parameter-inventory.md` §4—External constant classification
- `foundations/deriving-remaining-gaps.md` §5—parameter assessment status
- `gravity/quantum-gravity.md`—$\sigma$-regularization, Planck-scale status
- `foundations/xi-derivation.md`—$\xi = \varphi^6$, zero-free-parameter claims
- `foundations/unified-lagrangian.md`—Full Lagrangian, declares $\hbar = c = 1$, $\lambda = 0.1$
- `foundations/cassi-first-principles.md`—two-fluid PDE, canonical solver normalization $\lambda=0.1$; $\lambda = 1/(2w)$ is a Hypothesized linkage
- `foundations/dimensionful-cascade.md`—cascade table (292 = today's horizon rung), empirical $N$
- `open-questions-cassi-answers.md`—Epistemic registry (Q1–Q10, C1–C10, G1–G6, M1–M6, F1–F6, T1–T4)
- `foundations/spiral-dynamics.md`—Hubble, gravity, and c from spiral geometry
- `foundations/spin-fibonacci-spiral.md`—optional compact-phase extension; conditional half-angle spin map
- `foundations/wu-xing-derivation.md`—$w=5$ argument; Fibonacci and geometric identities are Derived, while the signal map and intersection remain conditional
- `cosmology/observational_constraints.md` §4—$\lambda$-independence of $w_a$
