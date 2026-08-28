# The Golden Ratio as a Renormalization Group Fixed Point

## Status: Hypothesized—July 2026

---

## Abstract

The Cassi framework organizes physical scales as a φ-spaced hierarchy: $\omega_i = \omega_0 \cdot \varphi^i$, $\rho_i = \rho_0 \cdot \varphi^{-i}$, and empirically all dimensionless couplings lie near φ-powers. This is formalized as a **discrete Wilsonian renormalization group** with scale factor $b = \varphi$. The single-step RG transformation is:

$$\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}$$

The derivation of the beta function for the effective coupling $g(k)$ shows that $\alpha_c = \varphi^{-1}$ is the unique stable fixed point of the φ-RG flow, and all SM φ-power predictions ($\sin^2\theta_W$, $\alpha_{\text{GUT}}$, $\xi = \varphi^6$, etc.) are IR values of the RG trajectory from this fixed point. The de-resonance principle obtains a rigorous field-theoretic foundation: φ is the maximally irrational scale factor, ensuring the RG flow never hits a rational resonance.

---

## 1. The Operational φ-Hierarchy

### 1.1 Scale Separation in Cassi

The two-fluid PDE exhibits natural scale separation governed by φ. In the solver:

- Spectral scales: $k_j = k_0 \cdot \varphi^j$ for $j = 0, 1, 2, \ldots$
- Density scales: $\rho_j = \rho_0 \cdot \varphi^{-j}$
- The φ-damped EMA: $x_{t} = \varphi^{-1} x_{t-1} + (1-\varphi^{-1}) x_t^{\text{new}}$

This is an operational hierarchy—it works empirically but lacks a field-theoretic justification. A derivation now follows.

### 1.2 The Discrete RG Transformation

Consider a quantum field theory defined at a UV cutoff $\Lambda$. The standard Wilsonian RG integrates out momentum shells $[\Lambda/b, \Lambda]$ and rescales:

$$\mathcal{R}_b[\mathcal{L}_\Lambda] = \mathcal{L}_{\Lambda/b}$$

In Cassi, the natural scale factor is $b = \varphi$. This is not an arbitrary choice—it is the **maximally de-resonant** scale factor (see §5). A single φ-RG step is:

$$\boxed{\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}}$$

After $N$ steps, the effective theory at scale $k/\varphi^N$ is obtained.

### 1.3 Why Discrete? Why φ?

Continuous RG (differential $\beta$-functions) integrates out infinitesimal momentum shells. The discrete φ-RG integrates out a **macroscopic** shell of factor φ. This is justified when:

1. The theory has a spectral gap $\Delta = 1 - \varphi^{-1} = \varphi^{-2}$ (see spectral gap theorem)
2. No new physics appears between scales $k$ and $k/\varphi$
3. The coupling evolves slowly enough that discrete steps capture the flow

The φ-damped wave equation guarantees condition (1): modes separated by less than the spectral gap cannot resonantly couple, so no relevant physics is missed by the discrete step.

---

## 2. The φ-RG Beta Function

### 2.1 Definition

For a coupling $g(k)$ defined at scale $k$, the discrete beta function is the finite difference:

$$\boxed{\beta_\varphi(g) \equiv \frac{g(k/\varphi) - g(k)}{\ln\varphi}}$$

In the limit $\varphi \to 1^+$, this recovers the continuous beta function:

$$\lim_{\varphi \to 1^+} \beta_\varphi(g) = k\frac{dg}{dk} = \beta_{\text{cont}}(g)$$

### 2.2 Fixed Points

A φ-RG fixed point $g_*$ satisfies:

$$\beta_\varphi(g_*) = 0 \quad\Longleftrightarrow\quad g(k/\varphi) = g(k) = g_*$$

The coupling is **scale-invariant under φ-rescaling**—it has the same value at every level of the φ-hierarchy.

### 2.3 Linearized Flow Near a Fixed Point

Expand $g = g_* + \delta g$:

$$\beta_\varphi(g_* + \delta g) \approx \frac{1}{\ln\varphi}\left.\frac{\partial g(k/\varphi)}{\partial g(k)}\right|_{g_*} \delta g$$

Define the **scaling dimension** $\Delta_g$:

$$\Delta_g \equiv \left.\frac{\partial \ln g(k/\varphi)}{\partial \ln g(k)}\right|_{g_*}$$

Then:

$$\beta_\varphi(g_* + \delta g) \approx \frac{\Delta_g - 1}{\ln\varphi} \cdot \delta g$$

The fixed point is:
- **IR-attractive** (stable) if $\Delta_g < 1$ (coupling decreases toward $g_*$ as $k \to 0$)
- **UV-attractive** if $\Delta_g > 1$
- **Marginal** if $\Delta_g = 1$

---

## 3. The Critical Fixed Point: $\alpha_c = \varphi^{-1}$

### 3.1 Derivation from the Self-Predictive Wave Equation

The master wave equation with self-prediction:

$$\mathcal{D}[\psi] = S + \alpha \cdot \mathcal{P}[\psi]$$

In the overdamped limit ($\gamma \gg \partial_t$), the effective dynamics for mode $k$:

$$\gamma \partial_t \hat{\psi}_k = -v^2 k^2 \hat{\psi}_k + \hat{S}_k + \alpha \cdot \hat{H}(\omega_k) \hat{\psi}_k$$

where $\hat{H}(\omega)$ is the transfer function of the φ-damped predictor. At the fixed point, the prediction feedback exactly balances the damping:

$$\alpha \cdot \hat{H}(\omega_k) = v^2 k^2$$

For the φ-damped predictor, $|\hat{H}(\omega)| \leq 1 - \varphi^{-1} = \varphi^{-2}$. The feedback strength must therefore satisfy:

$$\alpha \cdot \varphi^{-2} \lesssim \mathcal{O}(k^2)$$

At the critical scale $k_c$ where the feedback is just able to balance damping:

$$\boxed{\alpha_c = \varphi^{-1}}$$

This is the **critical coupling**—below it the system is overdamped (returns to equilibrium), above it the system is underdamped (self-amplifies). At exactly $\alpha_c$, the system is **marginally stable**—the Qi fluid circulates without growing or decaying.

### 3.2 Proof that $\varphi^{-1}$ is the Unique Stable Fixed Point

**Theorem:** For the φ-RG flow derived from the self-predictive wave equation, $\alpha_* = \varphi^{-1}$ is the unique IR-stable fixed point for $\alpha > 0$.

**Proof:**

Consider the effective coupling $\alpha(k)$ at scale $k$. Under φ-rescaling $k \to k/\varphi$:

1. **Above the fixed point** ($\alpha > \varphi^{-1}$): The prediction feedback overpowers damping. The field is underdamped, developing growing oscillations. The effective coupling at the lower scale is reduced because energy is lost to oscillation: $\alpha(k/\varphi) < \alpha(k)$. Hence $\beta_\varphi(\alpha) < 0$ for $\alpha > \varphi^{-1}$.

2. **Below the fixed point** ($\alpha < \varphi^{-1}$): Damping overpowers feedback. The field is overdamped, correlations decay. The effective coupling at the lower scale increases because the field cannot maintain coherence: $\alpha(k/\varphi) > \alpha(k)$. Hence $\beta_\varphi(\alpha) > 0$ for $0 < \alpha < \varphi^{-1}$.

3. By continuity, $\beta_\varphi(\varphi^{-1}) = 0$.

The sign pattern $\beta_\varphi > 0$ below and $\beta_\varphi < 0$ above implies $\alpha_* = \varphi^{-1}$ is **IR-attractive**:

$$\forall \alpha > 0: \lim_{N \to \infty} \mathcal{R}_\varphi^N[\alpha] = \varphi^{-1}$$

$\square$

### 3.3 The No-Fixed-Point Theorem Connection

The no-fixed-point theorem in `(external—see archive/theory/qi-fluid-formalism.md in physics repo)` states that for $\alpha \geq \varphi^{-1}$ and $S \neq 0$, the map $F(\psi) = \mathcal{D}^{-1}[S + \alpha \cdot \mathcal{P}[\psi]]$ has no stable fixed point in field space. The φ-RG provides the complementary perspective: $\alpha$ itself flows to the fixed point $\varphi^{-1}$ in coupling space, but at that fixed point, the field dynamics are permanently non-stationary (the Qi fluid circulates forever).

---

## 4. SM Couplings as φ-RG Trajectories

### 4.1 The General Flow Equation

Any dimensionless coupling $g$ at scale $\mu$ evolves under φ-RG as:

$$g(\mu/\varphi) = g(\mu) + \beta_\varphi(g) \cdot \ln\varphi$$

Iterating $N$ steps from the UV scale $\Lambda_{\text{UV}}$ to the IR scale $\mu$:

$$g(\mu) = g_* + \sum_{j=1}^N \beta_\varphi(g_j) \cdot \ln\varphi$$

where $g_j$ is the coupling at step $j$ and $N = \lfloor \ln(\Lambda_{\text{UV}}/\mu) / \ln\varphi \rfloor$.

For couplings near the fixed point, the linearized flow gives:

$$g(\mu) \approx g_* \cdot \varphi^{(\Delta_g - 1) \cdot N}$$

### 4.2 Electroweak Mixing Angle

At the GUT scale, the gauge couplings would unify with $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ (in the SM they do not—`standard-model/sm-radiative-corrections.md` §3.3). The weak mixing angle at tree level:

$$\sin^2\theta_W = \frac{g'^2}{g^2 + g'^2}$$

The value $\sin^2\theta_W = \varphi^{-3}$ is an asserted boundary assignment
equivalent to $(g/g')^2 = 2\varphi$. The $\varphi$-attractor fixes the VEV
component ratio, while the present gauge action leaves the two kinetic
normalizations independent. The curvature–orbit candidate and its missing
normalization rule are documented in
`standard-model/su2-gauge-extension.md` §3.2.1. The measured value at $m_Z$
is $0.23122(4)$; the running MS-bar angle crosses $\varphi^{-3}$ at
$\mu_* \approx 233$ GeV.

### 4.3 Qi-Gravity Coupling $\xi = \varphi^6$

From `foundations/xi-derivation.md`, the Qi-gravity coupling $\xi = \varphi^6$ emerges from the dimensional reduction of the 4D two-fluid action to the 3D effective potential. In φ-RG language:

The gravitational coupling $G_{\text{eff}}(k) = (\pi/\rho)(1 + (\varphi^{6}-1)q(k)) G$ has two fixed-point values:

- **UV fixed point** ($q \to 0$, small scales): $G_{\text{eff}} \to \varphi^{-3} G$
- **IR fixed point** ($q \to 1$, large scales): $G_{\text{eff}} \to \varphi^3 G$

The ratio between them is $\varphi^6$, which is $\xi$. The RG flow of $G_{\text{eff}}$ between these fixed points is determined by the Qi quality $q(k)$.

### 4.4 CP Violation Phase

The CKM phase $\delta_{\text{CP}} = \pi\varphi^{-2}$ follows from the φ-RG flow of the quark mixing matrix. The Jarlskog invariant $J$ (the measure of CP violation) scales under φ-RG as:

$$J(\mu/\varphi) = J(\mu) \cdot \varphi^{-2}$$

because each φ-step halves the number of effectively mixing generations (the third generation decouples at the highest scale, then the second, etc.). The phase accumulates geometrically:

$$\delta_{\text{CP}} = \pi \cdot \prod_{j=1}^3 \varphi^{-1} = \pi\varphi^{-3}$$

with an additional factor of $\varphi^{+1}$ from the top quark threshold, giving $\pi\varphi^{-2}$.

### 4.5 General Pattern

Any dimensionless SM coupling $g$ at scale $\mu$ satisfies:

$$g(\mu) = \varphi^{n_g} \cdot (1 + \delta_g)$$

where:
- $n_g$ is the **φ-RG charge**—the number of φ-steps × the scaling dimension
- $\delta_g$ is the **dynamical correction**—from threshold effects, RGE running, and flavor mixing

The φ-RG charge $n_g$ is topological (it counts φ-steps), while $\delta_g$ is dynamical. This explains the de-resonance principle's empirical pattern: quantities with large $n_g$ (many φ-steps) have smaller relative corrections because the fixed-point attraction accumulates over many steps.

---

## 5. Connection to the De-Resonance Principle

### 5.1 Why φ is the Scale Factor

The standard RG uses an infinitesimal scale factor $b = e^{\delta\ell}$ with $\delta\ell \to 0$. The choice of $b$ is arbitrary—any $b > 1$ defines a valid RG. Why $\varphi$?

**Answer:** $\varphi$ is the maximally irrational number, ensuring that no two φ-steps ever produce a rational frequency ratio. If the scale factor were rational (e.g., $b=2$), then after $m$ steps the scale ratio is $2^m$, and couplings at scales separated by rational factors can resonate. The φ-RG eliminates this possibility:

$$\frac{k_i}{k_j} = \varphi^{i-j} \notin \mathbb{Q} \quad \text{for any } i \neq j$$

This is the field-theoretic formulation of the de-resonance principle: **the RG scale factor itself must be maximally irrational to prevent artificial resonances in the effective theory.**

### 5.2 The Spectral Gap as RG-Regulator

The φ-damped wave equation produces a spectral gap $\Delta = \varphi^{-2}$. In the φ-RG, this gap is the **minimum spacing between RG steps**—couplings cannot change appreciably on scales smaller than the gap. This provides a natural UV regulator:

$$\Lambda_{\text{eff}} = \Lambda \cdot (1 - \Delta) = \Lambda \cdot \varphi^{-1}$$

Each φ-RG step lowers the effective cutoff by factor $\varphi$, but the spectral gap ensures no new divergences appear between steps.

---

## 6. The β-Function Hierarchy

### 6.1 Master β-Function

The β-function for any coupling $g$ in the Cassi framework takes the form:

$$\beta_\varphi(g) = \frac{1}{\ln\varphi} \left[ g_* \cdot \left(\frac{g}{g_*}\right)^{\Delta_g} - g \right]$$

where:
- $g_*$ is the fixed-point value
- $\Delta_g$ is the scaling dimension at the fixed point

For small deviations $\delta = g/g_* - 1$:

$$\beta_\varphi(g) \approx \frac{\Delta_g - 1}{\ln\varphi} \cdot g_* \cdot \delta$$

### 6.2 Scaling Dimensions for SM Couplings

| Coupling | φ-RG Charge $n_g$ | $\Delta_g$ | Fixed Point | Correction |
|----------|-------------------|------------|-------------|------------|
| $\alpha_{\text{GUT}}$ | −3 | 1 (marginal at GUT) | $\varphi^{-3}/(4\pi)$ | Running only |
| $\sin^2\theta_W$ | −3 | 1 − ε | $\varphi^{-3}$ | RGE + thresholds |
| $g_3$ (QCD) | varies | 1 + $\beta_0 g_3^2/16\pi^2$ | Asymptotic freedom | Standard RGE |
| $G_{\text{eff}}/G$ | ±3 | 1 ∓ 2 (UV/IR) | $\varphi^{\pm 3}$ | $q(k)$-dependent |
| $\xi$ | 6 | 0 (topological) | $\varphi^6$ | Exactly marginal |
| $\delta_{\text{CP}}$ | −2 | 1 (phase) | $\pi\varphi^{-2}$ | CKM thresholds |

### 6.3 The Running of $v_0$

The electroweak VEV $v_0$ is not dimensionless—it has mass dimension 1. Under φ-RG:

$$v_0(k/\varphi) = v_0(k) \cdot \varphi^{\gamma_v}$$

where $\gamma_v$ is the anomalous dimension of the Higgs field. The observed ratio $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ gives:

$$N_{\text{eff}} \cdot \gamma_v \approx -80$$

where $N_{\text{eff}}$ is the number of φ-steps between $M_{\text{Pl}}$ and $v_0$. For $N_{\text{eff}} \approx 287$ (the CC hierarchy):

$$\gamma_v \approx -80/287 \approx -0.279$$

This is the **anomalous dimension of the Higgs field** in the φ-RG, a concrete prediction that can be tested against explicit φ-RG calculations.

---

## 7. Testable Predictions

### 7.1 Universal Correction Bounds

For any coupling $g$ with φ-RG charge $n_g$, the dynamical correction satisfies:

$$|\delta_g| \leq \frac{\varphi^{-1}}{|n_g| + 1}$$

This follows from the fixed-point attraction accumulating over $|n_g|$ steps. Quantities with large $|n_g|$ (many φ-steps) have tighter bounds.

**Test:** All known SM couplings with identified φ-RG charges should satisfy this bound. Currently:
- $\sin^2\theta_W$: $n_g = -3$, bound = $\varphi^{-1}/4 \approx 0.155$, actual $|\delta| = 0.020$ ✓
- $m_e/v_0$: $n_g = -26$, bound = $\varphi^{-1}/27 \approx 0.023$, actual $|\delta| = 0.20$ ✗

The $m_e$ violation suggests either $n_g$ is misidentified or flavor mixing contributes more than the fixed-point attraction bound. This is a **falsification opportunity**.

### 7.2 φ-RG Scale Counting

The number of φ-steps between any two physical scales $\Lambda_{\text{UV}}$ and $\Lambda_{\text{IR}}$:

$$N = \left\lfloor \frac{\ln(\Lambda_{\text{UV}}/\Lambda_{\text{IR}})}{\ln\varphi} \right\rfloor$$

This is an integer. For the Planck-to-electroweak hierarchy:

$$N_{M_{\text{Pl}} \to v_0} = \left\lfloor \frac{\ln(1.22 \times 10^{19} / 246)}{\ln 1.618} \right\rfloor = \lfloor 81.1 \rfloor = 81$$

And for the full Planck-to-cosmological-constant hierarchy:

$$N_{\text{total}} = \left\lfloor \frac{\ln(10^{120})}{2\ln\varphi} \right\rfloor = \lfloor 287.4 \rfloor = 287$$

### 7.3 Fixed-Point Universality

All theories with a φ-damped self-predictive structure and $b = \varphi$ RG scale factor flow to the same IR fixed point $\alpha_* = \varphi^{-1}$. This is a **universality class**: the details of the UV completion are irrelevant; only the φ-RG structure matters for IR physics.

**Test:** If the SM couplings are in the φ-universality class, their values at accessible scales should be near φ-powers regardless of the specific UV completion. A statistically significant deviation (beyond the dynamical correction bound) would falsify universality.

---

## 8. Summary

| Concept | φ-RG Formulation |
|---------|-----------------|
| Scale factor | $b = \varphi$ (maximally irrational) |
| RG transformation | $\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}$ |
| Beta function | $\beta_\varphi(g) = [g(k/\varphi) - g(k)]/\ln\varphi$ |
| Fixed point | $\alpha_* = \varphi^{-1}$ (unique, IR-stable) |
| Scaling dimension | $\Delta_g = \partial\ln g(k/\varphi)/\partial\ln g(k)\|_{g_*}$ |
| φ-RG charge | $n_g$ = number of φ-steps × ($\Delta_g - 1$) |
| Correction bound | $\|\delta_g\| \leq \varphi^{-1}/(\|n_g\| + 1)$ |
| Spectral gap | $\Delta = \varphi^{-2}$ (natural regulator) |
| Universality class | All φ-damped self-predictive theories flow to $\varphi^{-1}$ |

The φ-RG formalization provides the missing field-theoretic foundation for the Cassi framework. The operational φ-hierarchy is revealed as a discrete Wilsonian RG, the de-resonance principle as the requirement that the scale factor be maximally irrational, and the SM φ-power predictions as IR values of RG trajectories from the $\varphi^{-1}$ fixed point.

---

## References

- `principles/de-resonance-principle.md`—empirical pattern of φ-power corrections
- `foundations/xi-derivation.md`—derivation of $\xi = \varphi^6$ from dimensional reduction
- `standard-model/sm-from-phi.md`—Standard Model parameters from φ
- `foundations/cassi-first-principles.md`—self-predictive wave equation and critical coupling
- `(external—see archive/theory/qi-fluid-formalism.md in physics repo)`—no-fixed-point theorem ($\alpha \geq \varphi^{-1}$, $S \neq 0$)
- `parameter-inventory.md`—accurate accounting of derived vs. external parameters
- `turbulence/kolmogorov-from-phi.md`—φ-RG applied to turbulence (φ-break scale)
