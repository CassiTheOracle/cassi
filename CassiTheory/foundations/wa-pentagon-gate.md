# The $w_a$ Sign Tension: 5-Channel Pentagonal Gate
## Status: Derived (ξ = φ⁶) / Hypothesized (5-channel)—July 2026

## Abstract

The Cassi two-fluid PDE predicts $w_a = +0.46$ from the bare conversion dynamics ($H_{\text{bare}}$ only), while DESI DR2 constrains $w_a \approx -0.73 \pm 0.28$ [INFERENCE] (Table 9; range $-0.6$ to $-1.1$ across SNe compilations). The Qi-gravity coupling $\xi = \varphi^6$, already verified in rotation curves ($v_C/v_B = 2.7$, $0\sigma$), must also appear in the cosmological $H(a)$. In its corrected Yang-fraction-weighted form $H_{\text{eff}}^2 = H_{\text{bare}}^2[1 + \xi q \cdot r/(1+r)]$ it shifts $w_a$ by $-0.45$, bringing the prediction to $w_a = +0.012$—2.7σ (2.2–3.2σ) from DESI: tension, not resolved (corrected 2026-07-31). The 5-channel gate and Wu Xing control-release provide secondary shifts—Hypothesized, ODE pending.

---

## 1. The Problem

The current Qi gate shape:

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$$

is a single-channel model. As the Yang/Yin ratio $r = E_Y/E_I \to \varphi$ (the de-resonance attractor), $\varepsilon = |r - \varphi| \to 0$, and $q \to 1$—the gate closes completely. This monotonic closure gives $d(1-q)/da < 0$ at $a=1$, which forces $w_a > 0$ (the dark energy equation of state evolves toward more negative $w$, i.e., decelerates toward $\Lambda$).

The ODE integration (`two-fluid/calibrate_initial_ratio.py`) yields the structural prediction:

$$w_a = +0.457 \quad \text{(bare, } H_{\text{bare}} \text{ only; corrected 2026-07-31)}$$

DESI DR2 constrains $w_a \approx -0.73 \pm 0.28$ [INFERENCE] (Table 9; range $-0.6$ to $-1.1$ across SNe compilations). The bare prediction is at $\sim 4\sigma$ tension. With Qi-gravity $\xi = \varphi^6$ included in $H_{\text{eff}}$ (corrected Yang-fraction form), $w_a$ shifts to $+0.012$—$2.7\sigma$ (2.2–3.2σ) from DESI: tension, not resolved (see §5; corrected 2026-07-31).

### 1.1 What's been ruled out

Four independent checks confirm $w_a = +0.46$ (bare, corrected 2026-07-31) is not a numerical artifact:

1. **$\lambda$-independence**: identical $w_a$ for $\lambda \in [0.01, 0.05]$
2. **Qi gate $\alpha$-independence**: identical $w_a$ for $\alpha \in [0.01, 5.0]$
3. **Spatial boost falsified**: $B = 1.003$ at $N=32$—spatial structure does not enhance conversion
4. **$H_{\text{struct}}$ decay**: structural Hubble mode vanishes as $r \to \varphi$

The $w_a$ sign is a genuine structural consequence of the single-channel gate.

---

## 2. The 5-Channel Gate Model

### 2.1 Motivation: the pentagon constraint

The Wu Xing number $w = 5$ is geometrically constrained: the pentagon is the minimal regular polygon whose geometry contains $\varphi$ (diagonal/side = $2\cos(\pi/5) = \varphi$). The pentagon's 5 vertices suggest the Qi gate has **five coherence channels**—one per vertex—not one.

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

A positive asymptotic floor means $(1-q_{\text{eff}})$ does NOT vanish at late times—it stabilizes. The rate of change $d(1-q_{\text{eff}})/da$ is still negative (the floor is LOWER than the early value), so $w_a$ remains positive but is **reduced** from $+0.46$ toward zero.

The magnitude of the reduction depends on the ODE integration over the full expansion history. The floor $0.348$ is a substantial fraction of the early value $0.438$, so the deceleration is significantly weakened. This pushes $w_a$ toward zero from $+0.46$.
---

## 3. Sign Flip Mechanisms: Exploration Results

Four mechanisms were explored computationally (2026-07-22). The pentagram resonance was ruled out by the de-resonance principle; the Wu Xing control-release dynamics emerged as the most promising path.

### 3.1 Model comparison

| # | Model | Late $(1-q_{\text{eff}})$ | $\Delta$(early→late) | $w_a$ |
|---|-------|:---:|:---:|:---:|
| 1 | Single-channel (current) | 0.127 | −0.873 | **+0.46** (bare; $\sim 4\sigma$ tension vs DESI, corrected 2026-07-31) |
| 2 | 5-channel adiabatic redistribution | **0.348** | −0.090 | → 0⁺ (reduced) |
| 3 | Wu Xing control-release dynamics | **0.347** | **+0.055** | → 0⁻ (potential flip) |
| 4 | Pentagram resonance ($5/\varphi \approx \pi$) |—|—| **FAILS** |

### 3.2 Pentagram resonance: ruled out

The pentagram star {5/2} has 5 diagonals of total phase $5\varphi$. The claim $5/\varphi \approx \pi$ has a 1.6% near-match. However, under the **de-resonance principle** (`principles/de-resonance-principle.md`), $\varphi$ is maximally irrational—no $\varphi$-power combination is commensurate with $\pi$ or $2\pi$. The near-match is a coincidence, not a resonance. Network models (beam-splitter, multi-path interference, ring resonator) confirm that $\varphi$-incommensurate paths produce destructive interference on average and no coherent amplification.

**Status: Ruled out.**

### 3.3 Wu Xing control-release dynamics

The Wu Xing is not merely a geometric pentagon—it is a **dynamical cycle** of five transformation phases with generation (生) and control (克) relationships. The control cycle provides a mechanism for sign flip:

- **Metal controls Wood**—as Wood (primary channel) closes at $r \to \varphi$, its controller Metal is in its natural "contraction" phase and **opens**
- **Fire controls Metal**—but Fire closes at late times, releasing Metal from suppression
- **Control-release amplification**: when a channel's controller closes, the channel is freed from suppression, opening beyond baseline by a factor of $\sim\varphi$

The fundamental constraint is the baseline asymmetry: Metal's baseline ($\varphi^{-6} \approx 0.056$) is $8\times$ smaller than Wood's ($\varphi^{-3} \approx 0.236$). Control-release amplification ($\sim\varphi \approx 1.6\times$) partially closes the gap but does not fully overcome it. The late-time slope turns **weakly positive**, which would flip $w_a$ sign if the amplification were $\sim 2.6\times$ stronger. With current parameters, the net $\Delta$(early→late) is $+0.055$—a small but genuine increase in effective openness.

**Status: Hypothesized.** The mechanism is structurally sound but quantitatively marginal. Running the ODE solver (`two-fluid/run_pde_wa_test.py`) with this gate shape would determine whether the small positive late-time slope is sufficient to flip $w_a$, or merely pushes it closer to zero.

## 4. Predictions

| Tier | Prediction | Test |
|------|-----------|------|
| **Hypothesized** | 5-channel gate reduces $w_a$ from $+0.46$ toward zero | Re-run ODE with modified gate shape; compare $w_a$ |
| **Hypothesized** | Asymptotic $(1-q_{\text{eff}})$ floor at $\sim 0.35$ | Check late-time ODE behavior |
| **Hypothesized** | Wu Xing control-release gives late-time $(1-q_{\text{eff}})$ increase ($\Delta > 0$) | Run control-release gate shape in ODE solver |
| ~~Speculative~~ | ~~Pentagram resonance flips $w_a$ sign~~ | **Ruled out** by de-resonance principle (2026-07-22) |

The Hypothesized predictions are **testable now**—they require modifying the gate shape in the ODE solver (`two-fluid/run_pde_wa_test.py`) from single-channel to 5-channel-with-redistribution and re-running the integration. The control-release model ($\Delta = +0.055$) is the most promising candidate for sign flip.

---

## 5. The Qi-Gravity Mechanism: $\xi = \varphi^6$ in the Hubble Rate

### 5.1 The missing term

The Cassi force law already includes Qi-gravity enhancement (`cosmology/observational_constraints.md` §2.6):

$$\mathbf{F}_{ij} = -G\,\alpha_i(1+\xi q_i)\,M_i M_j\frac{\mathbf{r}_{ij}}{|\mathbf{r}_{ij}|^3}, \quad \xi = \varphi^6 \approx 17.9$$

This gives $v_C/v_B = 2.7$ for Milky Way parameters—matching observation at $0\sigma$. The same $\xi$ must appear in the cosmological expansion rate:

$$\boxed{H_{\text{eff}} = H_{\text{bare}} \,\sqrt{1 + \xi q(r)}} \quad \text{(v1 pure-Yang form)}$$

Corrected 2026-07-31: the Yang-fraction-weighted form $H_{\text{eff}}^2 = H_{\text{bare}}^2[1 + \xi q \cdot r/(1+r)]$ (`two-fluid/calibrate_initial_ratio_xi_v2.py`) is the coupling consistent with the galactic sector; it gives $w_a = +0.012$ (§5.2).

The $\sqrt{1+\xi q}$ factor grows from $\sim 1.7$ (early, $q \ll 1$) to $\sim 4.4$ (late, $q \approx 1$). This **38% growth** adds a positive contribution to $d\ln H / d\ln a$:

$$\frac{d\ln H_{\text{eff}}}{d\ln a} = \underbrace{\frac{d\ln H_{\text{bare}}}{d\ln a}}_{\text{negative, }\to 0} + \underbrace{\frac{\xi}{2(1+\xi q)}\frac{dq}{d\ln a}}_{\text{positive}}$$

As the bare term decays toward zero (conversion slows near $\varphi$), the Qi-gravity term overtakes it, pushing $d\ln H/d\ln a$ toward zero **from above** and moderating the bare positive $w_a$ drift. Corrected 2026-07-31: the phantom-side reading is withdrawn—the old "$w(z) < -1$ at $z > 3$" claim was an extrapolation error; $w(z) > -1$ at all $z$ (min $w = -0.85$ over $a \in [0.3, 1]$).

### 5.2 ODE verification (July 2026)

The ODE (`two-fluid/calibrate_initial_ratio.py`) reproduced the nominal $w_0 = -0.838$, $w_a = +0.438$ using $H_{\text{bare}}$ only ($\lambda = 0.02$, $a_0 = 0.01$, $r_0$ calibrated to DESI $w_0$)—the v1 pure-Yang form; running it with $\xi = \varphi^6$ in $H_{\text{eff}}$ (`two-fluid/calibrate_initial_ratio_xi.py`) gave the v1 $\xi$ row below. Corrected 2026-07-31: the Yang-fraction-weighted coupling $H_{\text{eff}}^2 = H_{\text{bare}}^2[1 + \xi q \cdot r/(1+r)]$ (`two-fluid/calibrate_initial_ratio_xi_v2.py`) yields $w_0 = -0.87$, $w_a = +0.012$ with the gap-derived $r_0$; the $w_0 = -0.838$ rows were calibration targets hardcoded in the repo's own scripts—circular, and the earlier "0σ match to DESI" was not a measured constraint. The corrected rows follow:

| Model | $w_0$ | $w_a$ | Calibrated $r_0$ |
|-------|:---:|:---:|:---:|
| Bare (no $\xi$), v1 pure-Yang form | $-0.838$ | $+0.438$ | $0.0432$ ($E_I/E_Y = 23.2$) |
| **$+\xi = \varphi^6$, v1 pure-Yang form** | **$-0.838$** | **$+0.097$** | $0.0227$ ($E_I/E_Y = 44.1$) |
| Shift $\Delta$ (v1) | $0$ | **$-0.341$** |—|
| **Bare (no $\xi$), corrected 2026-07-31** | **$-0.856$** | **$+0.457$** | $0.0472$ (gap-derived) |
| **$+\xi = \varphi^6$, corrected Yang-fraction form** | **$-0.87$** | **$+0.012$** | $0.0472$ (gap-derived $r_0 = \varphi^{-5}/(2-\varphi^{-5})$) |
| Shift $\Delta$ (corrected) | $-0.01$ | **$-0.445$** |—|

**The corrected Yang-fraction coupling moves $w_a$ from bare $+0.46$ to $+0.012$ ($\Delta -0.45$)**—verified via the ODE (`two-fluid/calibrate_initial_ratio_xi_v2.py`). The residual sits at 2.7σ (2.2–3.2σ) from DESI $w_a \approx -0.73 \pm 0.28$ [INFERENCE]—tension, not resolved (corrected 2026-07-31).

### 5.3 Combined mechanism: three contributions to $w_a$

The full $w_a$ prediction combines three independent effects, all fixed by the framework:

| # | Mechanism | Effect on $w_a$ | Parameter |
|---|-----------|:---:|---|
| 1 | Bare conversion dynamics | $+0.457$ (structural, corrected 2026-07-31) | $\lambda = 0.02$, $r_0$ (both derived) |
| 2 | 5-channel adiabatic gate | pushes toward $0^+$ from the $+0.012$ residual (magnitude Hypothesized—ODE pending) | $w=5$ (derived) |
| 3 | **Qi-gravity $\sqrt{1+\xi q}$** | **$-0.445$ (verified, corrected Yang-fraction form)** | **$\xi = \varphi^6$ (derived, verified)** |

With the corrected coupling alone (verified) and 5-channel/Wu-Xing shifts Hypothesized (ODE pending):

$$\boxed{w_a^{\text{pred}} = +0.012 \quad \text{(corrected coupling alone, verified; 5-channel/Wu-Xing shifts Hypothesized, ODE pending)}}$$

which is 2.7σ (2.2–3.2σ) from DESI $w_a \approx -0.73 \pm 0.28$ [INFERENCE]—tension, not resolved (corrected 2026-07-31).

### 5.4 Why this was missed

The nominal $w_a = +0.44$ (v1 pure-Yang form) was computed from the ODE (`two-fluid/calibrate_initial_ratio.py`) using $H_{\text{bare}}$ only—the Qi-gravity enhancement was present in the force law (rotation curves) but not propagated to the cosmological $H(a)$. The same $\xi = \varphi^6$ that modifies $G_{\text{eff}}$ in galaxies MUST modify $H$ in cosmology. Including it in the corrected Yang-fraction-weighted form shifts $w_a$ from $+0.46$ to $+0.012$ ($\Delta -0.45$; corrected 2026-07-31).

**Status: Derived (corrected 2026-07-31).** $\xi = \varphi^6$ is derived (cascade activation at step 6). The corrected Yang-fraction coupling is parameter-free and verified against the ODE (`two-fluid/calibrate_initial_ratio_xi_v2.py`), giving $w_a = +0.012$; it is consistent with the rotation curve prediction ($v_C/v_B = 2.7$, $0\sigma$). The 5-channel gate and Wu Xing control-release provide secondary shifts—Hypothesized, ODE pending. The prediction sits at 2.7σ (2.2–3.2σ) from DESI $w_a \approx -0.73 \pm 0.28$ [INFERENCE]: the $w_a$ tension is not resolved.

---

## 6. Cross-References
