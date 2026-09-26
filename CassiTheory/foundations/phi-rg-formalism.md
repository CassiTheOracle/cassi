# The Golden Ratio as a Renormalization Group Fixed Point

## Status: Hypothesized—September 2026

---

## Abstract

The Cassi framework organizes candidate physical scales as a
$\varphi$-spaced hierarchy. This document explores a discrete Wilsonian-RG
interpretation with scale factor $b=\varphi$:

$$\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}.$$

All discrete-step identities here use the IR-step convention: for a block
factor $b>1$, $\beta_b(g)=[g(k/b)-g(k)]/\ln b$, whose $b\to1^+$ limit equals
$-k\,dg/dk$, the negative of the standard continuous beta function
$\beta_{\text{cont}}=k\,dg/dk$. The proposed beta function, fixed-point
selection, Standard Model $\varphi$ charges, and de-resonance interpretation
are Hypothesized ansätze. A microscopic coarse-graining map and independently
derived running couplings are still required. Maximal irrationality is an
arithmetic property of $\varphi$; by itself it does not establish a
field-theoretic RG flow or exclude physical resonances.

---

## 1. The Operational φ-Hierarchy

### 1.1 Scale Separation in Cassi

The two-fluid PDE exhibits scale separation organized by φ. In the solver:

- Spectral scales: $k_j = k_0 \cdot \varphi^j$ for $j = 0, 1, 2, \ldots$
- Density scales: $\rho_j = \rho_0 \cdot \varphi^{-j}$
- The φ-damped EMA: $x_{t} = \varphi^{-1} x_{t-1} + (1-\varphi^{-1}) x_t^{\text{new}}$

This is an operational hierarchy—it works empirically but lacks a
field-theoretic justification. §1.2–§1.3 formulate the discrete-RG bookkeeping
such a justification would require; no coarse-graining map is constructed here.

### 1.2 The Discrete RG Transformation

Consider a quantum field theory defined at a UV cutoff $\Lambda$. The standard Wilsonian RG integrates out momentum shells $[\Lambda/b, \Lambda]$ and rescales:

$$\mathcal{R}_b[\mathcal{L}_\Lambda] = \mathcal{L}_{\Lambda/b}$$

Any $b>1$ defines a valid block step. Cassi proposes the scale factor
$b = \varphi$; §5 records exactly what the arithmetic of $\varphi$ does and
does not supply. A single φ-RG step is:

$$\boxed{\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}}$$

After $N$ steps, the effective theory at scale $k/\varphi^N$ is obtained,
conditional on the map $\mathcal{R}_\varphi$ being supplied.

### 1.3 Why Discrete? Why φ?

Continuous RG (differential $\beta$-functions) integrates out infinitesimal momentum shells. The discrete φ-RG integrates out a **macroscopic** shell of factor φ. A finite-step truncation is trustworthy only when:

1. No strongly coupled mode pair straddles the shell boundary. A commonly
   stated sufficient reading is a spectral gap, and the candidate value
   $\Delta = 1 - \varphi^{-1} = \varphi^{-2}$ is the feedback-gain bound of
   the φ-damped predictor (§3.1). The predictor bound is an inequality on a
   kernel; promoting it to a spectral gap of the field theory is a separate
   proposal, and nothing in this document closes that step.
2. No new physics appears between scales $k$ and $k/\varphi$
3. The coupling evolves slowly enough that discrete steps capture the flow

Condition (1) remains Hypothesized: a finite shell integration generally
generates every symmetry-allowed local operator, so bounding one kernel
does not by itself guarantee that no relevant physics is missed.

---

## 2. The φ-RG Beta Function

### 2.1 Definition and Continuum Limit

For a coupling $g(k)$ defined at scale $k$ and any block factor $b>1$, the
discrete beta function is the finite difference

$$\boxed{\beta_b(g) \equiv \frac{g(k/b) - g(k)}{\ln b}}$$

where $g(k/b) = \mathcal{R}_b[g(k)]$ is the coupling after one block step.
Writing $b = e^{\varepsilon}$ and Taylor-expanding,
$g(k/b) = g(k) - \varepsilon\, k\, dg/dk + O(\varepsilon^2)$, so

$$\lim_{b \to 1^+} \beta_b(g) = -\,k\frac{dg}{dk} = -\beta_{\text{cont}}(g),
\qquad \beta_{\text{cont}} \equiv k\frac{dg}{dk}.$$

$\beta_b$ measures the step toward the IR, so in the continuum limit it is
the negative of the standard continuous beta function. Signs in this
document always refer to the IR-step convention. Specializing to the
proposed scale factor $b=\varphi$ defines $\beta_\varphi$.

### 2.2 Fixed Points

A φ-RG fixed point $g_*$ satisfies:

$$\beta_\varphi(g_*) = 0 \quad\Longleftrightarrow\quad \mathcal{R}_\varphi(g_*) = g_* \quad\Longleftrightarrow\quad g(k/\varphi) = g(k) = g_*$$

The coupling is **scale-invariant under φ-rescaling**—it has the same value
at every level of the φ-hierarchy. A fixed-point value is an input to the
discrete flow unless some independent calculation selects it.

### 2.3 Linearized Flow Near a Fixed Point

For any block factor $b>1$, let $\lambda$ be the eigenvalue of the
linearized blocking map at an assumed fixed point $g_*$:

$$\lambda \equiv \mathcal{R}_b'(g_*).$$

Expanding $g(k) = g_* + \delta g$ and using the definition of §2.1:

$$\beta_b(g_* + \delta g) \approx \frac{\lambda - 1}{\ln b}\, \delta g,
\qquad
\delta g_N \approx \lambda^N\, \delta g_0,$$

where $\delta g_N$ is the deviation at $k/b^N$, after $N$ IR steps. Specialized
to the proposed factor $b=\varphi$ one has $\mathcal{R}_b=\mathcal{R}_\varphi$
and $\ln b = \ln\varphi$. Where $g_* \neq 0$

one may equivalently write the **scaling dimension** as the
logarithmic-derivative form
$\Delta_g \equiv \partial \ln g(k/b)/\partial \ln g(k)\big|_{g_*} = \lambda$.
Attraction is governed by the modulus of $\lambda$:

- **IR-attractive** if $|\lambda| < 1$ (equivalently $|\Delta_g| < 1$ for
  $g_* \neq 0$): monotone decay for $0 < \lambda < 1$, sign-alternating damped
  decay for $-1 < \lambda < 0$.
- **UV-attractive** (IR-repulsive) if $\lambda > 1$.
- **Repulsive at both ends** if $\lambda < -1$ (alternating divergence).
- **Marginal** if $|\lambda| = 1$: the linear term decides nothing. At
  $\lambda = 1$ the leading motion comes from nonlinear terms (logarithmic
  running, Kosterlitz–Thouless-type behavior); at $\lambda = -1$ the
  alternation must be resolved through the two-step map.

---

## 3. The Candidate Coupling Threshold $\alpha_c = \varphi^{-1}$ (Hypothesized)

### 3.1 The Self-Predictive Wave Equation Input

The master wave equation with self-prediction:

$$\mathcal{D}[\psi] = S + \alpha \cdot \mathcal{P}[\psi]$$

In the overdamped limit ($\gamma \gg \partial_t$), the effective dynamics for mode $k$:

$$\gamma \partial_t \hat{\psi}_k = -v^2 k^2 \hat{\psi}_k + \hat{S}_k + \alpha \cdot \hat{H}(\omega_k) \hat{\psi}_k$$

where $\hat{H}(\omega)$ is the transfer function of the φ-damped predictor.
Marginal balance of prediction feedback against damping at scale $k$ reads

$$\alpha \cdot \hat{H}(\omega_k) = v^2 k^2.$$

If the feedback branch obeys the gain bound $|\hat{H}(\omega)| \leq
1 - \varphi^{-1} = \varphi^{-2}$, the feedback stays subcritical when

$$\alpha \cdot \varphi^{-2} \lesssim v^2 k^2.$$

Two inputs are needed before that inequality selects a coupling value. First,
the bound itself: the EMA kernel of §1.1 has unit gain at zero frequency, so
$|\hat{H}| \leq \varphi^{-2}$ presumes a feedback branch that excludes the DC
part, and the branch is defined by the archive formalism, not here. Second,
the balance fixes a relation among $\alpha$, $\hat{H}$, and $k_c$ at one
scale; extracting a $k$-independent critical value requires additional input
fixing $k_c$ (or an argument that the balance is scale-invariant). With those
inputs declared, the framework registers the candidate threshold

$$\boxed{\alpha_c = \varphi^{-1} \quad \text{(Hypothesized selector)}}$$

interpreted as: below it the system is overdamped (returns to equilibrium),
above it underdamped (self-amplifies), and at it marginally stable (the Qi
fluid circulates without growing or decaying). The interpretation is
Hypothesized; the inequality above supplies no selection on its own.

### 3.2 Stability Reading (Hypothesized, Not a Proof)

**Claim (Hypothesized):** For the φ-RG flow of the self-predictive wave
equation, $\alpha_* = \varphi^{-1}$ is the unique IR-stable fixed point for
$\alpha > 0$.

The argument one would need runs as follows. Consider the effective coupling
$\alpha(k)$ at scale $k$, and assume the damping dichotomy of §3.1 controls
the block step:

1. **Above the selector** ($\alpha > \varphi^{-1}$): prediction feedback
   overpowers damping, the field is underdamped, energy leaves through
   growing oscillation, and therefore $\alpha(k/\varphi) < \alpha(k)$, i.e.
   $\beta_\varphi(\alpha) < 0$.
2. **Below the selector** ($\alpha < \varphi^{-1}$): damping overpowers
   feedback, the field is overdamped, and coherence decay drives
   $\alpha(k/\varphi) > \alpha(k)$, i.e. $\beta_\varphi(\alpha) > 0$ for
   $0 < \alpha < \varphi^{-1}$.
3. By continuity, $\beta_\varphi(\varphi^{-1}) = 0$.

If items 1–2 held and $\beta_\varphi$ were differentiable at
$\varphi^{-1}$, the sign pattern together with
$\beta_\varphi \approx (\lambda-1)\delta g/\ln\varphi$ would at most bound
the linearized eigenvalue by $\lambda \le 1$: it excludes $\lambda > 1$ but
not $\lambda < -1$. IR-attractive behavior in the sense of §2.3 requires
$|\lambda| < 1$, which the sign pattern alone does not establish. Taking
$|\lambda| < 1$ as an additional assumption, the claimed global statement
would be

$$\forall \alpha > 0: \lim_{N \to \infty} \mathcal{R}_\varphi^N[\alpha] = \varphi^{-1}.$$

Nothing here is proven. The argument assumes what §2.2 declares missing: a
supplied map $\mathcal{R}_\varphi$ whose monotonicity follows from the
damping dichotomy, the exclusion of other zeros of $\beta_\varphi$ for
$\alpha>0$, and a basin reaching all $\alpha>0$. No step of §3.1 computes a
block step of the wave equation, and the physical spectral gap of §1.3
condition (1) is not established by the predictor bound. The selector and
the limit statement above keep the document's Hypothesized tier.

### 3.3 The No-Fixed-Point Theorem Connection

The no-fixed-point theorem in `(external—see archive/theory/qi-fluid-formalism.md in physics repo)` (archive-only provenance, registered in `BROKEN_REFS.md`) states that for $\alpha \geq \varphi^{-1}$ and $S \neq 0$, the map $F(\psi) = \mathcal{D}^{-1}[S + \alpha \cdot \mathcal{P}[\psi]]$ has no stable fixed point in field space. Conditional on the selector of §3.2, the φ-RG would supply the complementary perspective: $\alpha$ itself flows to $\varphi^{-1}$ in coupling space, while at that value the field dynamics are permanently non-stationary (the Qi fluid circulates forever).

---

## 4. SM Couplings as φ-RG Trajectories

### 4.1 The General Flow Equation

Inverting the definition of §2.1 gives the exact one-step recurrence for any
$b>1$:

$$g(k/b) = g(k) + \beta_b(g(k)) \cdot \ln b$$

Telescope it. Start from $g_0 = g(\Lambda)$ at the UV cutoff and define the
step lattice $k_j = \Lambda/b^j$, $g_j \equiv g(k_j)$, so
$\mu_N = k_N = \Lambda/b^N$. Applying the recurrence at $j = 0, 1, \ldots,
N-1$:

$$g(\mu_N) = g_N = g_0 + \ln b \sum_{j=0}^{N-1} \beta_b(g_j),
\qquad g_0 = g(\Lambda), \qquad \mu_N = \Lambda/b^{N}.$$

For the proposed factor $b=\varphi$ the step count spanning a range
$\Lambda \to \mu$ is $N = \ln(\Lambda/\mu)/\ln\varphi$ (rounded per §7.2).
Near an assumed fixed point the linearized recurrence of §2.3 gives

$$g(\mu_N) - g_* \approx \lambda^N \left[ g_0 - g_* \right],$$

so the **deviation** decays (or grows) geometrically with the eigenvalue
$\lambda$; the coupling value itself acquires no $\varphi$-power of its own
accord. Any $\varphi^{n}$ placement of a value is an assignment to the
trajectory's endpoint or to the model family of §6.1, not a consequence of
this recurrence.

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

The identity $\xi=\varphi^6$ is conditionally derived for the optional
Qi-gravity constitutive factor in `foundations/xi-derivation.md`. It does not
by itself define a momentum-space renormalization-group trajectory. The
state-space coupling-magnitude diagnostic is

$$
\mathcal G_C(E_Y,E_I)
:=
\frac{\pi}{\rho}\left[1+(\varphi^6-1)q\right].
$$

On the composition line $\varepsilon=0$, $\pi/\rho=\varphi^{-3}$ while $q$
continues to vary with density. The dilute endpoint gives
$\mathcal G_C\to\varphi^{-3}$; the registered reference-density point gives
$q=\varphi^2/3$ and $\mathcal G_C=5\sqrt5/3$; the high-density
same-composition endpoint gives $\mathcal G_C\to\varphi^3$. The ratio of the
two formal density endpoints is $\varphi^6$.

Calling these endpoints ultraviolet and infrared fixed points requires a
separate, frozen map $k\mapsto(E_Y,E_I,\rho_\star)$ and a physical gravity
completion. Neither follows from the local definition of $q$. Until that map
exists, $\mathcal G_C$ is a state-space diagnostic rather than a running
Newton coupling (`foundations/quantum-free-fall-correspondence.md` §7).

### 4.4 CP Violation Phase

The Jarlskog invariant rescaling

$$J(\mu/\varphi) = J(\mu) \cdot \varphi^{-2}$$

is an ad hoc multiplicative rule. The recurrences of §2–§4.1 constrain
deviations from fixed points additively or geometrically through
$\lambda$; no result here implies a per-step factor $\varphi^{-2}$ acting on
$J$ itself. The physical picture offered with it—that each φ-step halves the
number of effectively mixing generations (third, then second, decoupling)—is
an asserted mechanism. Under that assumption the CKM phase accumulates
geometrically:

$$\delta_{\text{CP}} = \pi \cdot \prod_{j=1}^3 \varphi^{-1} = \pi\varphi^{-3}$$

with an additional factor of $\varphi^{+1}$ from the top quark threshold,
giving $\pi\varphi^{-2}$. The product arithmetic is correct conditional on
the rule; the rule itself is a Hypothesized candidate reading, consistent
with the Mapped-conditional CKM-phase status of
$\delta_{\text{CP}} = \pi\varphi^{-2}$ recorded in
`parameter-inventory.md`, and is not a derivation of it from RG flow.

### 4.5 General Pattern

Any dimensionless SM coupling $g$ at scale $\mu$ is parameterized as:

$$g(\mu) = \varphi^{n_g} \cdot (1 + \delta_g)$$

where:
- $n_g$ is the **φ-RG charge**—the rung placement assigned to the value by
  comparison with the cascade ladder (`parameter-inventory.md`); the
  identification "$\varphi$-steps × scaling dimension" belongs to the model
  family of §6.1, and no general consequence of §4.1 ties a placement
  exponent to the linearized exponent $\Delta_g$
- $\delta_g$ is the **dynamical correction**—from threshold effects, RGE
  running, and flavor mixing

The φ-RG charge $n_g$ is a placement label (fixed once the rung is chosen),
while $\delta_g$ is dynamical. Whether large $|n_g|$ suppresses relative
corrections depends on IR attraction along the trajectory, which §3 leaves
Hypothesized; `principles/de-resonance-principle.md` records the empirical
pattern of small corrections near deep rungs as observation.

---

## 5. Connection to the De-Resonance Principle

### 5.1 Why φ is the Proposed Scale Factor

The standard RG uses an infinitesimal scale factor $b = e^{\delta\ell}$ with $\delta\ell \to 0$. The choice of $b$ is arbitrary—any $b > 1$ defines a valid RG. Why $\varphi$?

The framework's proposal is arithmetic: $\varphi$ is the maximally irrational
number, with continued fraction $[1;1,1,1,\ldots]$ and the slowest rational
approximation (Lagrange/Hurwitz sense), so that

$$\frac{k_i}{k_j} = \varphi^{i-j} \notin \mathbb{Q} \quad \text{for any } i \neq j,$$

and no two φ-steps produce a rational scale ratio. If the scale factor were
rational (e.g. $b=2$), scales separated by rational factors would repeat the
same shell bookkeeping at commensurate positions.

The boundary must be stated plainly. A Wilsonian shell integration is
well-defined for every $b>1$, and nothing in the standard construction makes
a rational step factor resonant or pathological: the continuum flow is the
$b\to1^+$ limit computed in §2.1, and step-size choices are scheme data.
That rational scale ratios could mediate physical resonances in an effective
theory is an assertion this document does not establish. The requirement
"the RG scale factor itself must be maximally irrational to prevent artificial
resonances" is therefore the field-theoretic formulation *proposed* by the
de-resonance principle (`principles/de-resonance-principle.md`), Hypothesized:
arithmetic extremality supplies a selection among valid $b$-values only if a
resonance mechanism independent of scheme is first constructed.

### 5.2 The Predictor Gain Bound and the RG Step

The φ-damped predictor of §3.1 has feedback-gain bound $\varphi^{-2}$
(the identity $1-\varphi^{-1}=\varphi^{-2}$). The cutoff update written as

$$\Lambda_{\text{eff}} = \Lambda \cdot (1 - \Delta) = \Lambda \cdot \varphi^{-1}, \qquad \Delta = \varphi^{-2},$$

restates the defining φ-step of §1.2 with $b=\varphi$; the arithmetic is an
identity, and the factor $(1-\Delta)$ attributes to the bound nothing the
step did not already contain. Reading the same $\Delta$ as a spectral gap
that spaces the RG steps and ensures no new divergences appear between steps
is the gap interpretation of §1.3 condition (1), which remains unestablished:
a finite shell integration generically induces all symmetry-allowed local
operators, and regulating that requires the full local action space, not a
gap between steps.

---

## 6. The β-Function Hierarchy

### 6.1 Master β-Function (Model Family)

A one-parameter family of blocking maps consistent with the fixed-point and
linearization identities of §2 (for $g, g_* > 0$) is the power-law map
$\mathcal{R}_b(g) = g_* (g/g_*)^{\Delta_g}$, whose linearization at $g_*$ has
$\lambda = \Delta_g$. Inserting it into §2.1:

$$\beta_\varphi(g) = \frac{1}{\ln\varphi} \left[ g_* \cdot \left(\frac{g}{g_*}\right)^{\Delta_g} - g \right]$$

where:
- $g_*$ is the fixed-point value (an input here)
- $\Delta_g$ is the scaling dimension at the fixed point

For small deviations $\delta = g/g_* - 1$ this reduces to the §2.3 linear
form with $\delta g = g_*\delta$ and $\lambda = \Delta_g$:

$$\beta_\varphi(g) \approx \frac{\Delta_g - 1}{\ln\varphi} \cdot g_* \cdot \delta$$

Attraction of this family requires $|\Delta_g| < 1$. The family is a
conditional construction: choosing $\Delta_g$ and $g_*$ builds a map, and
separate physics must say whether any member is the actual coarse-graining
step.

### 6.2 Scaling Dimensions for SM Couplings (Candidate Assignments)

The table records proposed placements under the §6.1 model family. None of
the entries is derived, and under the §2.3 criterion an entry is attractive
at the stated end only when its $|\lambda| < 1$.

| Coupling | φ-RG Charge $n_g$ | $\Delta_g$ | Fixed Point | Correction |
|----------|-------------------|------------|-------------|------------|
| $\alpha_{\text{GUT}}$ | −3 | 1 (marginal at GUT; linear test inconclusive) | $\varphi^{-3}/(4\pi)$ | Running only |
| $\sin^2\theta_W$ | −3 | 1 − ε (attractive if $-1<1-\varepsilon<1$) | $\varphi^{-3}$ | RGE + thresholds |
| $g_3$ (QCD) | varies | 1 + $\beta_0 g_3^2/16\pi^2$ | Asymptotic freedom | Standard RGE |
| $G_{\text{eff}}/G$ | ±3 | 1 ∓ 2 (UV/IR) | $\varphi^{\pm 3}$ | $q(k)$-dependent |
| $\xi$ | 6 | 1 (declared constant; no flow) | $\varphi^6$ | Exactly marginal |
| $\delta_{\text{CP}}$ | −2 | 1 (phase) | $\pi\varphi^{-2}$ | CKM thresholds |

The $G_{\text{eff}}/G$ values $\lambda=-1$ and $\lambda=3$ sit on the
flip-marginal and IR-repulsive boundaries of §2.3 and are listed as candidate
endpoints only; §4.3 keeps their state-space reading conditional on the
frozen scale map.

### 6.3 The Running of $v_0$

The electroweak VEV $v_0$ is not dimensionless—it has mass dimension 1. Its
per-step behavior is summarized by the net (canonical plus anomalous)
exponent $\gamma_v$:

$$v_0(k/\varphi) = v_0(k) \cdot \varphi^{\gamma_v}$$

The registered placement $v_0/M_{\text{Pl}} \approx \varphi^{-80}$
(`parameter-inventory.md`) spans about 80 φ-steps between $M_{\text{Pl}}$ and
$v_0$ (§7.2), so the recurrence of §4.1 applied to this ratio gives:

$$N_{\text{eff}} \cdot \gamma_v \approx -80, \qquad N_{\text{eff}} \approx 80
\;\Rightarrow\; \gamma_v \approx -1.$$

That is the canonical mass dimension of $v_0$: a relation between a
dimensionful parameter and the running cutoff reproduces the hierarchy by
construction. No anomalous part is extracted, and the Planck-to-cosmological-constant
step count ($\approx 287$, §7.2) does not apply to the Planck-to-electroweak
interval. The $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ comparison stays
Mapped, as the registries record; this section is a restatement of it under
the §4.1 recurrence.

---

## 7. Testable Predictions

### 7.1 Universal Correction Bounds (Proposed)

For any coupling $g$ with φ-RG charge $n_g$, the proposed candidate bound on
the dynamical correction is:

$$|\delta_g| \leq \frac{\varphi^{-1}}{|n_g| + 1}$$

This form is an empirical bookkeeping proposal: no derivation from §2–§6
exists, geometric attraction of §2.3 would give decay in the step count $N$
traveled, not a $1/(|n_g|+1)$ ceiling on endpoint residuals. Quantities with
large $|n_g|$ (deep rungs) are expected by the proposal to sit closer to
their φ-power.

**Test:** All known SM couplings with identified φ-RG charges should satisfy this bound. Currently:
- $\sin^2\theta_W$: $n_g = -3$, bound = $\varphi^{-1}/4 \approx 0.155$, actual $|\delta| = 0.020$ ✓
- $m_e/v_0$: $n_g = -26$, bound = $\varphi^{-1}/27 \approx 0.023$, actual $|\delta| = 0.20$ ✗

The $m_e$ violation falsifies the candidate bound as stated for that
placement; it does not touch the §4.1 identities. This is a
**falsification opportunity**.

### 7.2 φ-RG Scale Counting

The number of φ-steps between any two physical scales $\Lambda_{\text{UV}}$ and $\Lambda_{\text{IR}}$:

$$N = \left\lfloor \frac{\ln(\Lambda_{\text{UV}}/\Lambda_{\text{IR}})}{\ln\varphi} \right\rfloor$$

This is an integer. For the Planck-to-electroweak hierarchy:

$$N_{M_{\text{Pl}} \to v_0} = \left\lfloor \frac{\ln(1.22 \times 10^{19} / 246)}{\ln 1.618} \right\rfloor = \lfloor 79.9 \rfloor = 79$$

The raw exponent is $79.9$; the cascade ladder places $v_0$ at the nearest
integer rung, step 80, which is the convention behind the registered
$v_0/M_{\text{Pl}} \approx \varphi^{-80}$ (`parameter-inventory.md`,
`open-questions-cassi-answers.md`). Floor counting here and nearest-rung
placement there are different rounding conventions of the same raw ratio.

And for the full Planck-to-cosmological-constant hierarchy:

$$N_{\text{total}} = \left\lfloor \frac{\ln(10^{120})}{2\ln\varphi} \right\rfloor = \lfloor 287.1 \rfloor = 287$$

### 7.3 Fixed-Point Universality (Conditional)

All theories with a φ-damped self-predictive structure and $b = \varphi$ RG
scale factor would flow to the same IR fixed point $\alpha_* = \varphi^{-1}$
provided the selector and stability reading of §3.2 obtain. Under that
condition this defines a **universality class**: details of the UV completion
are irrelevant; only the φ-RG structure matters for IR physics. The condition
is exactly the piece this document does not derive.

**Test:** If the SM couplings are in the φ-universality class, their values at accessible scales should be near φ-powers regardless of the specific UV completion. A statistically significant deviation (beyond the dynamical correction bound) would falsify universality.

---

## 8. Summary

| Concept | φ-RG Formulation |
|---------|-----------------|
| Scale factor | $b = \varphi$ proposed among all valid $b>1$; arithmetic extremality alone selects nothing (§5.1) |
| RG transformation | $\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}$ (ansatz; no map constructed) |
| Beta function | $\beta_b(g) = [g(k/b) - g(k)]/\ln b$; IR-step convention; $b\to1^+$ limit $= -k\,dg/dk$ |
| Fixed point | $\alpha_* = \varphi^{-1}$ (Hypothesized selector; input unless independently derived) |
| Linearized flow | $\beta_b = (\lambda - 1)\delta g/\ln b$ with $\lambda = \mathcal{R}_b'(g_*)$; attraction $\lvert\lambda\rvert < 1$ |
| Scaling dimension | $\Delta_g = \partial\ln g(k/\varphi)/\partial\ln g(k)\|_{g_*} = \lambda$ (for $g_* \neq 0$) |
| φ-RG charge | $n_g$ = registered rung placement (Mapped comparison) |
| Correction bound | $\|\delta_g\| \leq \varphi^{-1}/(\|n_g\| + 1)$ (proposed; falsified for $m_e$ as stated) |
| Predictor gain bound | $\Delta = \varphi^{-2}$; physical spectral-gap reading open |
| Universality class | Conditional on the §3.2 selector |

This document fixes the discrete-step identities—the IR-step beta function
and its continuum limit, linearization at an assumed fixed point, and the
telescoped recurrence from $g(\Lambda)$—that any candidate φ-spaced blocking
map must satisfy. It supplies a coarse-graining map for no theory: the
$\varphi^{-1}$ selection, the spectral-gap reading, and the SM trajectory
placements remain Hypothesized, and the mapped comparisons and state-space
diagnostics keep the boundaries the registries record. Nothing here
constructs a blocking map for a lattice gauge theory.

---

## References

- `principles/de-resonance-principle.md`—empirical pattern of φ-power corrections
- `foundations/xi-derivation.md`—derivation of $\xi = \varphi^6$ from dimensional reduction
- `standard-model/sm-from-phi.md`—Standard Model parameters from φ
- `foundations/cassi-first-principles.md`—self-predictive wave equation and critical coupling
- `(external—see archive/theory/qi-fluid-formalism.md in physics repo)`—no-fixed-point theorem ($\alpha \geq \varphi^{-1}$, $S \neq 0$); archive-only, registered in `BROKEN_REFS.md`
- `parameter-inventory.md`—accurate accounting of derived vs. external parameters
- `turbulence/kolmogorov-from-phi.md`—φ-RG applied to turbulence (φ-break scale)
