# Dimensionful Constants: Derivation Status of $c$, $\hbar$, $G$, and $\lambda$

## Status: Hypothesized — July 2026

## Abstract

The Cassi framework derives ~20 dimensionless parameters (couplings, mass ratios, mixing angles) from the golden ratio $\varphi \approx 1.618$ and the two-fluid PDE. This document catalogues the constants that are **not yet derived** — the speed of light $c$, Planck's constant $\hbar$, Newton's constant $G$, and the PDE conversion rate $\lambda$ — and clarifies which "zero free parameters" claims in the existing literature are accurate and which overstate the case. There are no new derivations here; this is a status inventory and a reconciliation of inconsistencies between existing documents.

**Bottom line:**

| Constant | Status | Why |
|----------|--------|-----|
| All dimensionless couplings ($\sin^2\theta_W$, $\alpha_{\text{GUT}}$, $\xi$, etc.) | **Derived** | $\varphi$-powers from cascade structure |
| $v_0/M_{\text{Pl}}$ ratio | **Derived** | $\varphi^{-80}$ from cascade depth (5.3% residual) |
| $m_e/v_0$, $m_\nu/v_0$, $\eta$ (baryon asymmetry) | **Derived** | $\varphi$-powers (1–6% residuals) |
| $\lambda$ (PDE conversion rate) | **Empirical** | 0.1 in natural units — not derived from $\varphi$ |
| $c$, $\hbar$, $G$ individually | **External** | Dimensionful; $\varphi$ is dimensionless |
| $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$ | **External** | One dimensionful scale governs all lengths via $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ |
| $\sigma = \ell_{\text{Pl}}$ | **External** | Same as $\ell_{\text{Pl}}$ — not independently derived |
| The 292-step cascade depth | **Empirical** | $292 = \log_\varphi(R_H / \ell_{\text{Pl}})$ uses empirical $R_H$, $\ell_{\text{Pl}}$ |

---

## 1. The Three Dimensionful Constants: $G$, $c$, $\hbar$

### 1.1 Why $\varphi$ alone cannot derive them

$\varphi \approx 1.618$ is a **dimensionless** number. Any theory that claims to derive dimensionful quantities from a dimensionless constant must either:

(a) Provide a second, independent dimensionful constant (a reference scale), or
(b) Show that a dimensionless ratio (e.g. $R_H / \ell_{\text{Pl}}$) is derivable from $\varphi$, which then anchors one dimensionful quantity in terms of another

Cassi takes path (a): $\ell_{\text{Pl}} = 1.616 \times 10^{-35}\,\text{m}$ is the sole dimensionful constant. The cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ distributes it across all scales. But $\ell_{\text{Pl}}$ itself is empirical — it enters through the $\sigma$-regularization of the two-fluid PDE (`gravity/quantum-gravity.md` §2) and is taken from standard physics:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}}$$

This is one equation with three unknowns. The framework does not (and mathematically cannot, from $\varphi$ alone) determine $c$, $\hbar$, and $G$ individually — only their combination $\ell_{\text{Pl}}$.

### 1.2 The consistent position

This is acknowledged in the repository's most careful documents:

- **`parameter-inventory.md` §4** (§4.1): "$G$, $c$, $\hbar$ — The Unit System. … $\varphi$ is dimensionless. It cannot determine a dimensionful scale without a reference. The Cassi framework does not provide such a reference."
- **`foundations/deriving-remaining-gaps.md` §5** (lines 303–307): "$G$, $c$, $\hbar$ are dimensionful and cannot be derived from a dimensionless constant — this is a feature of any theory, not a bug."

These documents correctly classify $G, c, \hbar$ as **External (E)** in the parameter classification scheme.

### 1.3 The overstatement

Other documents make stronger claims that conflict with the above:

- **`gravity/quantum-gravity.md`** (line 243): "$\sigma = 1/M_{\text{Pl}}$ is already determined by the Planck scale, which itself is a derived quantity in the Cassi framework. … The **Theory of Everything is complete**." — **No derivation of $M_{\text{Pl}}$ from $\varphi$ exists anywhere in the repository.**
- **`foundations/xi-derivation.md` §5**: "With $\xi = \varphi^6$ derived, the Cassi Theory of Everything has **zero free parameters**." — This claim omits $\lambda$ (see §2) and the dimensionful constants.

These overstatements should be corrected. The framework's genuine achievement — deriving ~20 dimensionless couplings and ratios from $\varphi$ — does not need exaggeration.

---

## 2. The Hidden Free Parameter: $\lambda$

### 2.1 Current status

The PDE conversion rate $\lambda$ couples the Yang and Yin fields:

$$\partial_t E_Y \supset -\lambda(E_Y - \varphi E_I)$$

In the unified Lagrangian (`foundations/unified-lagrangian.md` §0), $\lambda$ is listed as:

> `λ = 0.1 — PDE conversion rate (empirical; not derived from φ)`

The word **"free"** is explicit. This is a dimensionless number that is not derived from $\varphi$. It is calibrated empirically and used consistently across all sectors.

**Number-theoretic proof that no integer $\varphi$-power combination can equal exactly $0.1$:** Every $\varphi$-power can be written as $\varphi^{-n} = (-1)^n F_{n+1} + (-1)^{n+1}F_n\varphi$ where $F_n$ are Fibonacci numbers. Any finite integer-coefficient linear combination therefore takes the form $A + B\varphi$ with $A, B \in \mathbb{Z}$. For this to equal $1/10$, we would need $B = 0$ and $A = 1/10$, impossible since $A$ is integer. **No finite sum of integer-weighted $\varphi$-powers can produce exactly $0.1$.** The search is definitively closed.

**De-resonance interpretation:** The fact that no $\varphi$-power equals $0.1$ is a **feature**, not a gap. If $\lambda$ were a $\varphi$-power, the conversion rate would phase-lock with specific cascade rungs, creating resonant overlap between the pentagon's 5 coherence channels — they would blur into a quasi-continuous spectrum. Because $\lambda = 1/10$ is rational and maximally non-resonant with the $\varphi$-spaced cascade, the 5 channels remain **distinct and non-overlapping**. This is the de-resonance principle applied to the gate itself: the gate's operating frequency is chosen to minimize interference between channels, just as $\varphi$-spacing minimizes resonant coupling between cascade rungs.

**Status: Hypothesized.** $\lambda = 1/(2 \times 5)$ is the simplest, most geometric candidate. It connects $\lambda$ to the same pentagon structure that determines $w = 5$ and the gap $g = 1 - \varphi^{-5}$. The number-theoretic proof above shows it cannot be a $\varphi$-power — and the de-resonance principle shows it *should not* be one.

### 2.2 History of attempted derivation

- **`foundations/cassi-first-principles.md`** (line 262) lists $\lambda = 3\varphi^2 H_0$ as **Derived**.
### 2.3 The Origin of $w = 5$: Geometric Constraint

The Wu Xing number $w = 5$ that appears in the gap $g = 1 - \varphi^{-5}$ is not arbitrary. The golden ratio $\varphi$ appears geometrically in the regular pentagon as the ratio of diagonal to side:

$$\frac{\text{diagonal}}{\text{side}} = 2\cos\left(\frac{\pi}{5}\right) = \varphi$$

This is a geometric identity — the pentagon is the **minimal** regular polygon whose geometry contains $\varphi$. The triangle ($n=3$) and square ($n=4$) do not contain $\varphi$ in any distance ratio. The decagon ($n=10$) also contains $\varphi$ ($R/s = \varphi$), but the decagon decomposes into two pentagons — $n=5$ is the irreducible cycle.

In the two-fluid PDE, the Wu Xing represents a closed cycle of phase relations between Yang and Yin modes. For the cycle to be $\varphi$-structured (i.e., for phase advances to be $\varphi$-commensurate), the minimal geometric cycle that supports $\varphi$ is the pentagon. Hence $w = 5$ by geometric necessity — the smallest $n$ such that a regular $n$-gon's distance ratios include $\varphi$.

The gap $g = 1 - \varphi^{-5}$ then follows: one complete pentagonal cycle advances the conversion phase by a factor of $\varphi^5$, leaving an unconverted residual of $\varphi^{-5} \approx 0.090$. The converted fraction is $\varphi^{-5}$, the resisted fraction is $g = 1 - \varphi^{-5} \approx 0.910$.

**Status: Hypothesized.** The geometric constraint on $w=5$ is mathematically rigorous (the pentagon is indeed the minimal $\varphi$-containing polygon). The step from "$w=5$ by geometry" to "$g = 1 - \varphi^{-5}$ by cycle closure" is reasoned but not derived from the PDE equations of motion. The computational investigation `foundations/pinch_point_modes.py` shows that an elliptical cavity with aspect ratio $\varphi$ does not independently enforce exactly 5 bands — the pentagon constraint is geometric, not spectral.



### 2.4 Impact on "zero free parameters"

The claim "zero free parameters" cannot be sustained while $\lambda = 0.1$ is empirically set. The framework's parameter count should be stated as:

| Category | Count | Examples |
|----------|-------|----------|
| **$\varphi$-powers (Derived)** | ~17 dimensionless | $\xi = \varphi^6$, $\sin^2\theta_W = \varphi^{-3}$, $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ |
| **Cascade-span derived** | ~3 dimensionless | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$, $m_e/v_0$, $\eta$ |
| **Calibrated (Empirical)** | 1 dimensionless | $\lambda = 0.1$ |
| **External (Dimensionful)** | 3 | $G$, $c$, $\hbar$ (or equivalently $\ell_{\text{Pl}}$, $t_{\text{Pl}}$, $M_{\text{Pl}}$) |

The claim in `open-questions-cassi-answers.md` (line 646) that "the single calibrated constant $\lambda$ is fixed by the measured Hubble" should be revised — $\lambda$ is not uniquely fixed by $H_0$ (see `cosmology/observational_constraints.md` lines 219–222: $w_a$ unchanged across $\lambda \in [0.01, 0.05]$).

---

## 3. The 292-Step Bridge

### 3.1 What it is

The cascade depth $N \approx 292$ is the exponent relating the Hubble radius to the Planck length:

$$N = \log_\varphi\left(\frac{R_H}{\ell_{\text{Pl}}}\right) \approx 292$$

This is the **only** dimensionless constraint linking the cascade structure to the dimensionful constants. It says: the observable universe spans 292 $\varphi$-multiplications of the Planck length. The number 292 is an empirical input — it depends on the measured $H_0$ and the measured $G$, $c$, $\hbar$.

### 3.2 What it constrains

If $N = 292$ could be **derived** from the Wu Xing gap $g = 1 - \varphi^{-5}$ or from the PDE's attractor dynamics, then the dimensionless ratio $R_H / \ell_{\text{Pl}} = \varphi^{292}$ would be predicted. Combined with the measured $R_H$ (or equivalently $H_0$), this would determine $\ell_{\text{Pl}}$ — and thereby constrain the combination $\hbar G / c^3$.

Currently, no such derivation exists. The Wu Xing number $w = 5$ determines the gap $g$ and the ratio $r_0$ but does not independently fix the total cascade depth $N$. The cascade table in `foundations/dimensionful-cascade.md` assigns physical meanings to each rung by matching to observed scales — this is a **catalog**, not a derivation of $N$.

### 3.3 Vacuum energy consistency check

While $N$ cannot be derived from $\varphi$ alone, a non-trivial consistency exists. The observed vacuum energy density $\rho_\Lambda \approx 10^{-123}\,\rho_{\text{Pl}}$ is within an order of magnitude of:

$$\rho_\Lambda \approx \rho_{\text{Pl}} \times \varphi^{-2N}$$

With $N = 292$, $\varphi^{-2N} = \varphi^{-584} \approx 10^{-122.1}$, matching the observed $10^{-123}$ to within a factor of $\sim 8$ — remarkable for a 123-order-of-magnitude quantity. Equivalently, inverting: if $\rho_\Lambda$ is determined by the cascade structure (specifically by the cumulative Wu Xing gap integrated over the cascade), then $N$ is constrained within a few rungs of 292. This is a consistency, not a derivation — it requires the empirical $\rho_\Lambda$ — but it is the closest the framework currently comes to an independent prediction for $N$.

### 3.4 The path to a derivation

Deriving $N$ from $\varphi$ requires a termination condition that does not reintroduce the circularity $N = \log_\varphi(R_H/\ell_{\text{Pl}})$ where $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$. The following candidate paths skirt the circularity by fixing $N$ from the PDE dynamics or the Wu Xing structure alone:

- **Qi-gate closure condition**: the cascade ends when $(1-q_n)$ falls below a threshold where coherent structure can no longer form. This would give $N$ from the Qi profile $q_n = 1 - \varphi^{-n-\delta}$ — but the threshold itself would need to be derived.
- **De-resonance bandwidth**: the cascade spans the frequency range over which φ-spacing is stable against resonance. If the total bandwidth (ratio of highest to lowest stable frequency) is fixed by the de-resonance principle, it may equal $\varphi^N$.

Both are **Hypothesized** — reasoned from the framework but not yet derived. The circularity $G \leftrightarrow N$ remains the fundamental blocker: $\ell_{\text{Pl}}$ is both the cascade's anchor ($\ell_0$) and a function of $G$. Until an independent determination of either $\ell_{\text{Pl}}$ or $N$ exists within the framework, $G$ will remain external.

---

## 4. Derivation Pathways

### 4.1 Path for $c$

$c$ enters the framework through the kinetic term $\frac{1}{2}(\partial_\mu\Psi)(\partial^\mu\Psi)$ of the two-fluid Lagrangian. In natural units $c = 1$, this is the invariant speed of the Lorentz metric $\eta_{\mu\nu}$.

**Cannot be derived from $\varphi$ while the metric is an input.** A derivation of $c$ would require the metric itself to emerge from the two-fluid dynamics — specifically, from the Qi field's role in defining the effective geometry (the $G_{\text{eff}} = G_N(1 + \xi q)$ modification of `gravity/quantum-gravity.md` points in this direction but does not go far enough).

**If** the two-fluid PDE, in its dimensionless form (as solved in the parent repo's code), has a *natural* ratio of spatial to temporal discretization steps that is set by the $\varphi$-attractor dynamics (not by numerical convenience), then restoring physical units would give $c$ in terms of $\varphi$ and the conversion rate $\lambda$. This is testable with the relativistic PDE solver — it cannot be tested with the parabolic reaction-diffusion solvers in `visual-explainers/`.

**Spiral-dynamics perspective** (`foundations/spiral-dynamics.md` §4): $c$ may emerge as the scale-invariant product $c \sim \lambda_{\text{eff}} \cdot \ell_n = \lambda \cdot \ell_{\text{Pl}}$, where the $\varphi^n$ factors cancel between the cascade-suppressed conversion rate and the cascade-expanded coherence length. This is a dimensional consistency check (both $\lambda$ and $\ell_{\text{Pl}}$ remain empirical inputs) but provides a geometric mechanism for why $c$ is constant across scales — it is the invariant speed of the Fibonacci spiral.

**Status: Hypothesized.** The spiral-dynamics mechanism is specified and PDE-testable; a full derivation still requires calibrating $\lambda$'s PDE units against physical time.

### 4.2 Path for $\hbar$

$\hbar$ enters through canonical quantization: $[\hat\Psi, \hat\Pi] = i\hbar$. The quantum-gravity document ($\S4.1$) quantizes the two-fluid field but takes $\hbar = 1$ in natural units.

A Cassi-native derivation of $\hbar$ would require identifying the *minimum cascade action* — the smallest quantum of coherent energy transfer across one cascade rung. The cascade-suppression formula gives per-rung damping factors, but these are dimensionless probability ratios, not actions.

If the minimum action at cascade rung $n$ is:

$$S_{\text{min}}^{(n)} = E_n \cdot \tau_n$$

where $E_n$ is the energy density of a coherent excitation at rung $n$ and $\tau_n$ is the conversion period, then $\hbar$ would be the scale-invariant limit of $S_{\text{min}}^{(n)}$ as $n$ varies — the cascade's *common* quantum of action. This would require an independent energy scale (e.g. the Planck energy $M_{\text{Pl}}c^2$), making it dependent on the $c$ and $G$ derivations.

**Status: Speculative.** Depends on deriving at least one other dimensionful constant first.
### 4.3 Path for $G$

$G$ (or equivalently $\ell_{\text{Pl}}$) is the sole dimensionful constant of the cascade. The Qi-gravity coupling $\xi = \varphi^6$ is derived — it modifies the *effective* $G$ via $G_{\text{eff}} = G_N(1 + \xi q)$ — but the bare $G_N$ is not.

The path: if $N = 292$ can be derived from $\varphi$ (§3.4), and the Hubble scale $R_H$ is measured, then $\ell_{\text{Pl}} = R_H / \varphi^{292}$ is determined — and $G = \ell_{\text{Pl}}^2 c^3 / \hbar$ follows, assuming $c$ and $\hbar$ are already fixed.

**Status: Hypothesized pathway.** The 292-step bridge is structurally promising; the derivation of $N$ from $\varphi$ is the missing piece.

### 4.4 Path for $\lambda$

The conversion rate $\lambda$ is the most tractable target: it is dimensionless, so $\varphi$ *could* determine it directly. Candidates:

- **De-resonance condition**: $\lambda$ is the rate at which off-resonance perturbations are damped. The per-rung damping is $\varphi^{-1}$; summed over the cascade, the effective $\lambda$ may be $\varphi$-related. But the damping is a *probability per rung*, not a rate — dimensionally different.
- **Qi-gate timescale**: the conversion rate at rung $n$ is $\lambda_n = \lambda_0 \cdot (1 - q_n)$, varying with cascade position. The uniform $\lambda = 0.1$ would be an effective average over the cascade. If $\lambda_0$ at the Planck scale is set by $\varphi$ (e.g. $\lambda_0 = \varphi^{-2}$), integration over the cascade would give a specific number.

**Status: Hypothesized.** The value 0.1 has no obvious $\varphi$-power match. The shallowest gap to close — a single dimensionless number — and deserves priority.

---

## 5. Inconsistencies to Resolve

### 5.1 "Zero free parameters" claims

The following documents contain claims that should be qualified:

| Document | Claim | Correction needed |
|----------|-------|-------------------|
| `gravity/quantum-gravity.md` line 243 | "$\sigma = 1/M_{\text{Pl}}$ … is a derived quantity" | $M_{\text{Pl}}$ is external; change "derived" to "determined by the Planck scale, which is the cascade's dimensionful anchor" |
| `gravity/quantum-gravity.md` line 245 | "The Theory of Everything is complete" | Remove or qualify: "…with one free dimensionless parameter ($\lambda$) and three external dimensionful constants" |
| `foundations/xi-derivation.md` §5 | "zero free parameters" | Add: "zero free parameters among dimensionless couplings; $\lambda$, $c$, $\hbar$, $G$ remain external" |
| `open-questions-cassi-answers.md` line 646 | "the single calibrated constant $\lambda$ is fixed by the measured Hubble" | $\lambda$ is empirically set to 0.1, not uniquely fixed by $H_0$ |

### 5.2 The hybrid ℏ in the Lagrangian

`foundations/unified-lagrangian.md` declares $\hbar = c = 1$ (natural units) in §0, but §1.3 retains explicit $\hbar^2$ in the Bohm quantum potential:

$$\mathcal{L}_{\text{QP}} = -\frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha$$

In natural units $\hbar = 1$, this term should carry coefficient $1/(2m^2)$ without $\hbar^2$. The hybrid notation is confusing but not incorrect (it reminds the reader that the term is quantum in origin). A consistent normalization pass across the unified Lagrangian is recommended.

### 5.3 Q-registry cross-reference

In `open-questions-cassi-answers.md`, the epistemic summary classifies 16 questions as **Derived** and 23 as Hypothesized/Speculative. The F-questions (Fundamental) previously covered fine-tuning (F1), arrow of time (F2), unification (F3), and TOE completeness (F4). An F5 entry ("Derivation of dimensionful constants") has been added, adding $c$, $\hbar$, $G$, $\lambda$ to the registry under the Hypothesized tier.
---

## 6. Cross-Doc Update Checklist

When this document's findings are accepted:

- [x] **`parameter-inventory.md`**: Already correct. No change needed.
- [x] **`gravity/quantum-gravity.md`** line 243: Done (2026-07-22).
- [x] **`foundations/xi-derivation.md`** §5: Done (2026-07-22).
- [x] **`foundations/unified-lagrangian.md`** §0: Done (2026-07-22).
- [x] **`open-questions-cassi-answers.md`**: Done — F5 added, λ claim fixed, summary updated to 40 (2026-07-22).
- [x] **`TOE.md`**: Done — five instances qualified (2026-07-22).

---

## 7. References

- `parameter-inventory.md` §4 — External constant classification
- `foundations/deriving-remaining-gaps.md` §5 — Updated parameter counts
- `gravity/quantum-gravity.md` — $\sigma$-regularization, claims "derived" Planck scale
- `foundations/xi-derivation.md` — $\xi = \varphi^6$, claims "zero free parameters"
- `foundations/unified-lagrangian.md` — Full Lagrangian, declares $\hbar = c = 1$, $\lambda = 0.1$
- `foundations/cassi-first-principles.md` — Retracted $\lambda = 3\varphi^2 H_0$ derivation
- `foundations/dimensionful-cascade.md` — 292-step cascade table with empirical $N$
- `open-questions-cassi-answers.md` — Epistemic registry (Q1–Q10, C1–C10, G1–G6, M1–M5, F1–F5, T1–T4)
- `cosmology/observational_constraints.md` §4 — $\lambda$-independence of $w_a$
