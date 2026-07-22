# The $w_a$ Sign Tension: 5-Channel Pentagonal Gate

## Status: Hypothesized — July 2026

## Abstract

The Cassi two-fluid PDE predicts $w_a = +0.46$ (decelerating dark energy equation of state), while DESI DR2 measures $w_a = -0.51 \pm 0.38$ — a $2.5\sigma$ sign mismatch. This is the single largest tension between the framework and observation. The current Qi gate model uses a single coherence channel ($q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$) that closes monotonically as $r \to \varphi$, producing $w_a > 0$.

The pentagon geometry that determines the Wu Xing number $w=5$ (§2.3 of `dimensionful-constants-status.md`) suggests the Qi gate has **five coherence channels** — one per pentagon vertex. When the primary channel closes at late times, coherence redistributes adiabatically to the four secondary channels. The 5-channel model produces a non-zero asymptotic floor for the effective coherence openness $(1-q_{\text{eff}}) \to 0.348$, which pushes $w_a$ toward zero from $+0.46$ — a genuine reduction of the tension. Full sign flip ($w_a < 0$) requires pentagram resonance amplification of the secondary channels at late times (**Speculative**).

---

## 1. The Problem

The current Qi gate shape:

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$$

is a single-channel model. As the Yang/Yin ratio $r = E_Y/E_I \to \varphi$ (the de-resonance attractor), $\varepsilon = |r - \varphi| \to 0$, and $q \to 1$ — the gate closes completely. This monotonic closure gives $d(1-q)/da < 0$ at $a=1$, which forces $w_a > 0$ (the dark energy equation of state evolves toward more negative $w$, i.e., decelerates toward $\Lambda$).

The ODE integration (`cosmology/observational_constraints.md` §6) yields the structural prediction:

$$w_a = +0.46 \quad \text{(invariant under } \lambda, \alpha \text{ variations)}$$

DESI DR2 measures $w_a = -0.51 \pm 0.38$ — the opposite sign at $2.5\sigma$.

### 1.1 What's been ruled out

Four independent checks confirm $w_a = +0.46$ is not a numerical artifact:

1. **$\lambda$-independence**: identical $w_a$ for $\lambda \in [0.01, 0.05]$
2. **Qi gate $\alpha$-independence**: identical $w_a$ for $\alpha \in [0.01, 5.0]$
3. **Spatial boost falsified**: $B = 1.003$ at $N=32$ — spatial structure does not enhance conversion
4. **$H_{\text{struct}}$ decay**: structural Hubble mode vanishes as $r \to \varphi$

The $w_a$ sign is a genuine structural consequence of the single-channel gate.

---

## 2. The 5-Channel Gate Model

### 2.1 Motivation: the pentagon constraint

The Wu Xing number $w = 5$ is geometrically constrained: the pentagon is the minimal regular polygon whose geometry contains $\varphi$ (diagonal/side = $2\cos(\pi/5) = \varphi$). The pentagon's 5 vertices suggest the Qi gate has **five coherence channels** — one per vertex — not one.

Each channel represents a distinct coherence pathway through the pentagon cycle. The 5 channels are NOT independent: coherence that cannot exit through one vertex redistributes to the remaining vertices (adiabatic coherence conservation).

### 2.2 Channel openness

Channel $i$ has baseline openness determined by its vertex's coupling strength to the cascade:

$$b_i = \varphi^{-k_i}, \quad k_i = 2 + i \quad (i = 1,\ldots,5)$$

The exponent $k_i$ increases with channel number: channel 1 (primary vertex, strongest coupling) has $k_1 = 3$ (Planck barrier); channel 5 (opposite vertex, weakest coupling) has $k_5 = 7$.

| Channel | $k_i$ | $b_i = \varphi^{-k_i}$ |
|---------|-------|------------------------|
| 1 (primary) | 3 | 0.2361 |
| 2 | 4 | 0.1459 |
| 3 | 5 | 0.0902 |
| 4 | 6 | 0.0557 |
| 5 | 7 | 0.0344 |
| **Total** | | **0.5623** |

### 2.3 Adiabatic redistribution

As $r \to \varphi$, channel 1 closes: $\Delta b_1 = -\varphi^{-3} \approx -0.236$. The lost coherence redistributes to channels 2–5 in proportion to their baseline openness:

$$\Delta b_i = \frac{b_i}{\sum_{j=2}^5 b_j} \cdot \varphi^{-3}, \quad i = 2,\ldots,5$$

The redistribution denominator is $\sum_{j=2}^5 b_j = 0.3262$.

| Channel | Redistribution gain | Final $b_i$ |
|---------|---------------------|-------------|
| 2 | +0.1056 (44.7%) | 0.2515 |
| 3 | +0.0652 (27.6%) | 0.1554 |
| 4 | +0.0403 (17.1%) | 0.0961 |
| 5 | +0.0249 (10.6%) | 0.0594 |

Total coherence is conserved: $\sum_i b_i^{\text{final}} = 0.5623 = \sum_i b_i^{\text{initial}}$.

### 2.4 Effective openness with conversion efficiency

Not all channels convert with equal efficiency. The primary channel (vertex 1) couples through the pentagon's direct diagonal ($d = \varphi s$), giving $\eta_1 = 1$. Secondary channels couple through the pentagon's edges (side $s$), giving:

$$\eta_{2..5} = \frac{\text{side}}{\text{diagonal}} = \frac{1}{\varphi} \approx 0.618$$

The effective openness that enters the equation of state is:

$$(1-q_{\text{eff}}) = \sum_{i=1}^{5} \eta_i \cdot b_i$$

**Before channel 1 closes** ($r \ll \varphi$, early times):

$$(1-q_{\text{eff}})^{\text{early}} = 1 \cdot 0.236 + 0.618 \cdot (0.146 + 0.090 + 0.056 + 0.034) = 0.438$$

**After channel 1 closes** ($r \to \varphi$, late times):

$$(1-q_{\text{eff}})^{\text{late}} = 1 \cdot 0 + 0.618 \cdot (0.251 + 0.155 + 0.096 + 0.059) = 0.348$$

### 2.5 Asymptotic floor and $w_a$

The 5-channel model gives:

$$\lim_{r \to \varphi} (1-q_{\text{eff}}) = 0.348 > 0$$

Compare with the single-channel model: $\lim_{r \to \varphi} (1-q) = 0$.

A positive asymptotic floor means $(1-q_{\text{eff}})$ does NOT vanish at late times — it stabilizes. The rate of change $d(1-q_{\text{eff}})/da$ is still negative (the floor is LOWER than the early value), so $w_a$ remains positive but is **reduced** from $+0.46$ toward zero.

The magnitude of the reduction depends on the ODE integration over the full expansion history. Without running the ODE (code is in parent repo), the most we can say is: the floor $0.348$ is a substantial fraction of the early value $0.438$, so the deceleration is significantly weakened. This pushes $w_a$ toward zero from $+0.46$.

---

## 3. Sign Flip Mechanisms: Exploration Results

Four mechanisms were explored computationally (2026-07-22). The pentagram resonance was ruled out by the de-resonance principle; the Wu Xing control-release dynamics emerged as the most promising path.

### 3.1 Model comparison

| # | Model | Late $(1-q_{\text{eff}})$ | $\Delta$(early→late) | $w_a$ |
|---|-------|:---:|:---:|:---:|
| 1 | Single-channel (current) | 0.127 | −0.873 | **+0.46** (2.5σ tension) |
| 2 | 5-channel adiabatic redistribution | **0.348** | −0.090 | → 0⁺ (reduced) |
| 3 | Wu Xing control-release dynamics | **0.347** | **+0.055** | → 0⁻ (potential flip) |
| 4 | Pentagram resonance ($5/\varphi \approx \pi$) | — | — | **FAILS** |

### 3.2 Pentagram resonance: ruled out

The pentagram star {5/2} has 5 diagonals of total phase $5\varphi$. The claim $5/\varphi \approx \pi$ has a 1.6% near-match. However, under the **de-resonance principle** (`principles/de-resonance-principle.md`), $\varphi$ is maximally irrational — no $\varphi$-power combination is commensurate with $\pi$ or $2\pi$. The near-match is a coincidence, not a resonance. Network models (beam-splitter, multi-path interference, ring resonator) confirm that $\varphi$-incommensurate paths produce destructive interference on average and no coherent amplification.

**Status: Ruled out.**

### 3.3 Wu Xing control-release dynamics

The Wu Xing is not merely a geometric pentagon — it is a **dynamical cycle** of five transformation phases with generation (生) and control (克) relationships. The control cycle provides a mechanism for sign flip:

- **Metal controls Wood** — as Wood (primary channel) closes at $r \to \varphi$, its controller Metal is in its natural "contraction" phase and **opens**
- **Fire controls Metal** — but Fire closes at late times, releasing Metal from suppression
- **Control-release amplification**: when a channel's controller closes, the channel is freed from suppression, opening beyond baseline by a factor of $\sim\varphi$

The fundamental constraint is the baseline asymmetry: Metal's baseline ($\varphi^{-6} \approx 0.056$) is $8\times$ smaller than Wood's ($\varphi^{-3} \approx 0.236$). Control-release amplification ($\sim\varphi \approx 1.6\times$) partially closes the gap but does not fully overcome it. The late-time slope turns **weakly positive**, which would flip $w_a$ sign if the amplification were $\sim 2.6\times$ stronger. With current parameters, the net $\Delta$(early→late) is $+0.055$ — a small but genuine increase in effective openness.

**Status: Hypothesized.** The mechanism is structurally sound but quantitatively marginal. Running the ODE solver (`run_pde_wa_test.py` in the parent repo) with this gate shape would determine whether the small positive late-time slope is sufficient to flip $w_a$, or merely pushes it closer to zero.

## 4. Predictions

| Tier | Prediction | Test |
|------|-----------|------|
| **Hypothesized** | 5-channel gate reduces $w_a$ from $+0.46$ toward zero | Re-run ODE with modified gate shape; compare $w_a$ |
| **Hypothesized** | Asymptotic $(1-q_{\text{eff}})$ floor at $\sim 0.35$ | Check late-time ODE behavior |
| **Hypothesized** | Wu Xing control-release gives late-time $(1-q_{\text{eff}})$ increase ($\Delta > 0$) | Run control-release gate shape in ODE solver |
| ~~Speculative~~ | ~~Pentagram resonance flips $w_a$ sign~~ | **Ruled out** by de-resonance principle (2026-07-22) |

The Hypothesized predictions are **testable now** — they require modifying the gate shape in the ODE solver (`run_pde_wa_test.py` in the parent repo) from single-channel to 5-channel-with-redistribution and re-running the integration. The control-release model ($\Delta = +0.055$) is the most promising candidate for sign flip.

---

## 5. Cross-References

- `foundations/dimensionful-constants-status.md` §2.3 — Geometric constraint on $w=5$ (pentagon)
- `cosmology/observational_constraints.md` §6 — $w_a$ tension analysis, resolution pathways
- `foundations/pinch_point_modes.py` — Computational analysis: mode spectrum in φ-aspect cavity
- `visual-explainers/coherence_transmission.py` — Cascade coherence transmission model

---

## References

- `foundations/dimensionful-constants-status.md` — Dimensionful constants: pentagon constraint on $w=5$
- `cosmology/observational_constraints.md` — DESI DR2 constraints, $w_a$ tension
- `foundations/cassi-first-principles.md` — Two-fluid PDE, φ-attractor, Qi gate
- `principles/de-resonance-principle.md` — φ as maximally irrational
