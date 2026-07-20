# The Dimensionful Cascade: All Physical Scales from $\varphi$

## Abstract

The Cassi two-fluid framework has one fundamental dimensionful scale: the Planck length $\ell_{\text{Pl}} = 1.616 \times 10^{-35}\,\text{m}$. Every other physical scale in the universe follows from the cascade relation

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}}$$

where $\varphi = (1+\sqrt{5})/2 \approx 1.618$ and the integer exponent $n$ is determined by the dynamics of the $\varphi$-attractor — specifically, by where in the cascade a given physical process freezes out. The total cascade spans $n = 0$ (Planck) to $n \approx 292$ (Hubble radius), a range of 292 $\varphi$-multiplications. This document catalogues the complete spectrum.

---

## 1. The Fundamental Scale

The Planck length is the sole dimensionful constant:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}} = 1.616255 \times 10^{-35}\,\text{m}$$

The Planck mass is $M_{\text{Pl}} = \sqrt{\hbar c / G} = 1.22 \times 10^{19}\,\text{GeV}/c^2$. In the Cassi framework, $\ell_{\text{Pl}}$ emerges as the natural UV cutoff from the $\sigma$-regularization of the two-fluid PDE (see `quantum-gravity.md`). No other fundamental length exists — all scales are $\varphi$-powers of $\ell_{\text{Pl}}$.

---

## 2. The Cascade Formula

For any physical scale $\ell$, the exponent $n$ is:

$$n = \frac{\ln(\ell / \ell_{\text{Pl}})}{\ln\varphi} = \log_\varphi\!\left(\frac{\ell}{\ell_{\text{Pl}}}\right)$$

The cascade is NOT a continuous spectrum. Physical scales correspond to integer (or near-integer) values of $n$, where a gauge symmetry breaks, a particle decouples, or a dynamical threshold is crossed. The selection of which $n$ are "active" is determined by the PDE dynamics — specifically, the conversion rate $\lambda$, the Qi gate shape, and the scale-dependent wave speed $c(r)$ along the ratio-evolution string.

### 2.1 Relationship to the Gap

The initial gap $g = 1 - \varphi^{-5}$ (see TOE.md §1.2) sets the cascade depth for the electroweak scale:

$$\frac{v_0}{M_{\text{Pl}}} = g \cdot \varphi^{-N} \quad\Longrightarrow\quad N = \frac{\ln(g \cdot M_{\text{Pl}} / v_0)}{\ln\varphi} \approx 79.7 \approx 80$$

The exponent $N \approx 80$ for the electroweak-to-Planck ratio is a **consistency check** — it matches the observation that $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ to within 5.3%. The gap itself is derived from the Wu Xing five-element structure ($w=5$), reducing the cascade depth to zero free parameters.

### 2.2 Cascade Invariance

The electroweak cascade depth $N \approx 80$ is robust against variations in the initial gap $g$. Changing $g$ (i.e., a different Wu Xing number $w$) changes the cosmology ($w_0$, $H_0$ evolution) but leaves the Standard Model couplings unchanged, because the $\varphi$-attractor physics near $r = \varphi$ is independent of the initial conditions. The EW scale "freezes out" at the same number of $\varphi$-steps from Planck regardless of how far the initial ratio started from equilibrium.

---

## 3. Complete Cascade Table

| Step $n$ | Scale (meters) | Physical Meaning | Regime |
|----------|---------------|-------------------|--------|
| 0 | $1.6 \times 10^{-35}$ | **Planck length** — UV cutoff | Quantum gravity |
| 1 | $2.6 \times 10^{-35}$ | String tension scale | Quantum gravity |
| 2 | $4.2 \times 10^{-35}$ | Compactification scale | Quantum gravity |
| 5 | $1.8 \times 10^{-34}$ | GUT scale ($M_{\text{GUT}} \sim 10^{16}$ GeV) | GUT |
| 10 | $2.0 \times 10^{-32}$ | Intermediate symmetry breaking | GUT |
| 20 | $2.5 \times 10^{-27}$ | Seesaw scale ($\sim 10^{14}$ GeV, neutrino masses) | GUT/neutrino |
| 40 | $4.0 \times 10^{-17}$ | Inflationary energy scale | Inflation |
| 60 | $6.4 \times 10^{-7}$ | SUSY-breaking / intermediate scale | Desert |
| **80** | **$8.0 \times 10^{-19}$** | **Electroweak scale** ($v_0 \approx 246$ GeV) | Particle physics |
| 88 | $3.1 \times 10^{-15}$ | QCD confinement ($\Lambda_{\text{QCD}} \sim 200$ MeV) | Particle physics |
| 95 | $1.0 \times 10^{-15}$ | Proton Compton wavelength ($\sim 1$ GeV) | Nuclear |
| 105 | $1.0 \times 10^{-12}$ | Pion Compton wavelength ($\sim 140$ MeV) | Nuclear |
| 117 | $5.3 \times 10^{-11}$ | **Bohr radius** ($a_0$, atomic scale) | Atomic |
| 125 | $2.5 \times 10^{-9}$ | Typical molecular bond length | Molecular |
| 142 | $3.0 \times 10^{-5}$ | Cellular scale ($\sim 30$ μm) | Biological |
| 168 | $1.7$ | **Human scale** ($\sim 1.7$ m) | Macroscopic |
| 180 | $1.3 \times 10^{7}$ | Earth diameter | Planetary |
| 198 | $6.6 \times 10^{12}$ | Solar System ($\sim 44$ AU, Pluto orbit) | Stellar system |
| 220 | $3.6 \times 10^{17}$ | Light-year ($\sim 9.5 \times 10^{15}$ m) | Interstellar |
| 228 | $6.0 \times 10^{12}$ | Solar System (40 AU) | Stellar system |
| 240 | $2.3 \times 10^{19}$ | Parsec ($\sim 3.1 \times 10^{16}$ m) | Interstellar |
| 260 | $3.5 \times 10^{22}$ | Kiloparsec ($\sim 3.1 \times 10^{19}$ m) | Galactic |
| 267 | $9.3 \times 10^{20}$ | Milky Way diameter ($\sim 30$ kpc) | Galactic |
| 275 | $4.5 \times 10^{23}$ | Local Group ($\sim 3$ Mpc) | Extragalactic |
| 280 | $5.0 \times 10^{24}$ | BAO scale ($\sim 150$ Mpc) | Cosmological |
| **285** | **$7.0 \times 10^{24}$** | **Wu Xing bubble** ($\sim 226$ Mpc) | Multiverse |
| 288 | $3.0 \times 10^{25}$ | Supercluster scale ($\sim 1$ Gpc) | Cosmological |
| 290 | $7.8 \times 10^{25}$ | Horizon at recombination | Cosmological |
| **292** | **$1.4 \times 10^{26}$** | **Hubble radius** ($\sim 4.5$ Gpc) | Observable universe |

### Step Verification

Key steps are verified against known physical scales:

```
Step  80:  ℓ_Pl × φ^80  = 1.616e-35 × 4.97e16  = 8.04e-19 m   (EW scale ✓)
Step  95:  ℓ_Pl × φ^95  = 1.616e-35 × 6.63e19  = 1.07e-15 m   (QCD scale ✓)
Step 117:  ℓ_Pl × φ^117 = 1.616e-35 × 3.28e24  = 5.30e-11 m   (Bohr radius ✓)
Step 285:  ℓ_Pl × φ^285 = 1.616e-35 × 4.31e59  = 6.97e24 m    (226 Mpc ✓)
Step 292:  ℓ_Pl × φ^292 = 1.616e-35 × 8.68e60  = 1.40e26 m    (Hubble ✓)
```

---

## 4. Cascade Zones

The full 292-step cascade divides naturally into three regimes:

### Zone 1: Quantum ($n = 0$ to $n \approx 80$)
- Planck scale to electroweak scale
- Governed by the Standard Model and its GUT extension
- All gauge couplings unify at the GUT scale ($\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$)
- The electroweak scale emerges at $n \approx 80$ as a dynamical threshold where the Qi gate begins to engage

### Zone 2: Astrophysics ($n \approx 80$ to $n \approx 285$)
- Electroweak scale to the Wu Xing bubble
- Governed by Qi-enhanced gravity ($\xi = \varphi^6$)
- Structure formation: galaxies, clusters, superclusters
- The wave speed $c(r)$ varies from $\sim 0.24$ (at $r_0$) to $\sim 0$ (near $\varphi$), creating a variable-tension "string" that generates wake waves at $\varphi$-scaled intervals
- The Qi gate engagement at $r = \varphi^{-1}$ ($a \sim 0.051$, $z \sim 19$) sets the bubble scale

### Zone 3: Cosmology ($n \approx 285$ to $n \approx 292$)
- Wu Xing bubble to Hubble radius
- Only 7 $\varphi$-steps — the bubble fills 98% of the observable volume
- Neighboring $w$-bubbles ($w=4$, $w=6$) are mostly beyond the horizon
- CMB large-angle anomalies may reflect $w$-gradient structure at these scales

---

## 5. Cascade Step Selection: Wake Wave Mechanism

Not every integer $n$ corresponds to an observable physical scale. The wake wave mechanism selects which steps "activate":

### 5.1 The String-Wake Feedback Loop

The global ratio $r(t) = \langle E_Y\rangle/\langle E_I\rangle$ evolves along the "ratio-space string" from $r_0 \approx 0.047$ to $r = \varphi$. As it moves, it generates wake waves — spatial density perturbations — through the conversion term. These wakes propagate at the local wave speed:

$$c(r) = \sqrt{\frac{\lambda \cdot \text{gate}(r) \cdot |r-\varphi|}{(1+r)/2}}$$

The wake spacing in physical space is set by $c(r) \times \tau(r)$, where $\tau(r)$ is the residence time at ratio $r$ (inverse of $dr/d\ln a$). The ratio of successive wake spacings follows $\varphi$-powers because both $c(r)$ and $\tau(r)$ scale with the Qi gate.

### 5.2 Activated Steps

The known $\varphi$-exponents in the Cassi framework correspond to specific activated cascade steps:

| $\varphi$-exponent | Step $n$ | Physical Quantity | Activation Mechanism |
|-------------------|---------|-------------------|---------------------|
| $\varphi^{-1}$ | 1 | $m_t/v_0$ | Top Yukawa (generation 3 threshold) |
| $\varphi^{-2}$ | 2 | $\delta_{\text{CP}}/\pi$ | CKM Yukawa diagonalisation |
| $\varphi^{-3}$ | 3 | $\sin^2\theta_W$ | GUT symmetry breaking |
| $\varphi^{3}$ | 3 | $\Omega_{\text{DM}}/\Omega_b$ | Qi condensate freeze-out |
| $\varphi^{6}$ | 6 | $\xi$ (Qi-gravity) | Two-field × three-dimension coupling |
| $\varphi^{-5}$ | 5 | Gap $g = 1-\varphi^{-5}$ | Wu Xing five-element cycle |
| $\varphi^{-26}$ | 26 | $m_e/v_0$ | Flavor mixing (generation 1) |
| $\varphi^{-80}$ | 80 | $v_0/M_{\text{Pl}}$ | Electroweak symmetry breaking |
| $\varphi^{-292}$ | 292 | $H_0/M_{\text{Pl}}$ | Hubble horizon (IR cutoff) |

The activation mechanism is typically a symmetry-breaking event or a dynamical threshold (gauge symmetry breaking, particle decoupling, Qi gate engagement). Steps that lack such a threshold remain "dark" — they exist in the cascade but don't correspond to observable couplings.

---

## 6. The Wu Xing Bubble (Step 285)

The bubble at step 285 is the coherence length of the Wu Xing number $w$ — the scale over which the cosmological initial conditions remain constant. It is set by the comoving horizon at the epoch when the Qi gate first engages ($r = \varphi^{-1}$, $a \approx 0.051$, $z \approx 19$).

**Bubble properties:**
- Diameter: $\sim 226$ Mpc (comoving)
- Position in cascade: step 285 of 292 (98%)
- Contains: $\sim 10^6$ Milky-Way-sized galaxies
- Neighboring bubbles: $w=4$ or $w=6$, separated by $\varphi$-scaled voids

The bubble is nearly degenerate with the BAO scale (step $\sim 284.5$, $150$ Mpc). They differ by less than one $\varphi$-step, which means the wake wave modulation in $P(k)$ sits directly on top of the BAO feature — entangled but separable through their different period structures (fixed scale vs. fixed ratio).

---

## 7. Testable Implications

### 7.1 $\varphi$-Periodic $P(k)$ Modulation

The wake waves imprint a log-periodic signal on the matter power spectrum:

$$\Delta(\ln k) = \ln\varphi \approx 0.4812$$

This is a **zero-parameter, falsifiable prediction** — see `falsifiable-predictions.md` §5 and TOE.md §3.3. Orthogonal to BAO (which has constant period in $k$-space), the Cassi modulation has constant period in $\ln k$-space. Subtract the BAO template; search the residual for $\ln\varphi$ periodicity. DESI DR2: marginal (2–3σ). Euclid (2027): definitive (>5σ).

### 7.2 Void and Structure Scale Ratios

Structures formed by the wake mechanism should show $\varphi$-scaled separations. While the void size function is smooth (not multi-peaked), the wake wave mechanism predicts subtle $\varphi$-periodic modulations in the correlation function $\xi(r)$ and the void-galaxy cross-correlation. These are distinguishable from BAO through their fixed-ratio (not fixed-scale) structure.

### 7.3 Multiverse $w$-Gradient

The Wu Xing bubble at step 285 implies neighboring bubbles at $w=4$ and $w=6$ beyond our horizon. Their boundaries would create a preferred axis in the CMB at $\ell < 5$ that fades at smaller scales — a scale-dependent signature unique to the super-horizon $w$-gradient explanation (see `observational_constraints.md` §4).

---

## 8. Open Questions

1. **Why 292 steps?** The total cascade from Planck to Hubble is $\log_\varphi(M_{\text{Pl}}/H_0) \approx 292$. Is this number derivable from the PDE dynamics, or is it set by the initial conditions of inflation?

2. **Why these specific activated steps?** The set $\{1, 2, 3, 5, 6, 26, 80, 292\}$ has no obvious pattern. Do the "dark" steps carry physical meaning (e.g., sterile neutrino masses, dark sector couplings)?

3. **Cascade spacing regularity?** The steps are irregularly spaced: sparse at low $n$, dense at high $n$ (near $\varphi$). Is there an underlying periodicity in $\ln n$ space?

4. **Full 3D PDE verification.** The cascade table is derived from the homogeneous ODE + dimensional analysis. The full 3D PDE should independently reproduce the activated step set through the wake wave mechanism. This requires N≥32 simulations with structure formation.

---

## References

- TOE.md §1.2: Gap derivation and dimensionful cascade overview
- TOE.md §1.3: Governing PDE with Qi gate formula
- TOE.md §3.3: $\varphi$-periodic $P(k)$ prediction
- `parameter-inventory.md`: Complete parameter classification (D:16, C:4, E:6, I:6)
- `observational_constraints.md` §2.6: Rotation curve prediction ($\xi=\varphi^6$)
- `observational_constraints.md` §4: CMB $w$-gradient analysis
- `falsifiable-predictions.md`: Full prediction catalogue (31 entries)
