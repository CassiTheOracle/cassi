# The Dimensionful Cascade: External Planck Anchor and $\varphi$-Ladder

## Status: Derived dimensionless ladder identity; physical rung mappings mixed—August 2026

## Abstract

The Cassi framework takes the external Planck length $\ell_{\text{Pl}} = 1.616 \times 10^{-35}\,\text{m}$ as the reference anchor for a dimensionful cascade parameterization. Once that anchor and the dimensionless scale-separation constant are supplied, the ladder is

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}}$$

where $\varphi = (1+\sqrt{5})/2 \approx 1.618$. The integer or near-integer exponent $n$ is a coordinate assignment for a physical scale; its physical identification carries an individual **Mapped**, **Calibrated**, or **Hypothesized** status. The observable ladder spans $n = 0$ (Planck anchor) to $n \approx 292$ (today's horizon rung—epoch-dependent); the coordinate ladder is unbounded above and below. This document catalogues the present parameterization and its status-qualified scale assignments.

**Extension:** The cascade does not truncate at either boundary. Above $n \approx 292$ lies the **megacascade** (multiverse, bubble boundaries). Below $n = 0$ lies the **microcascade** (sub-Planckian infinite ladder). See `foundations/microcascade-mirror.md` for the bidirectional extension.

**Figure:** `visual-explainers/cascade_cosmos.png`—3-regime diagram: megacascade bubble chain, the 292-rung ladder, and the microcascade golden spiral, all computed from $\ell_n = \ell_{\text{Pl}}\,\varphi^{n}$ (`visual-explainers/cascade_cosmos.py`).
**Figure:** `visual-explainers/fractal_zoom.png`—three-panel fractal zoom demonstrating cascade self-similarity: overview with φ-spaced rings, deep zoom into a Qi bubble interior (elliptical φ:1 cross-section, five-arm spiral poles), and pole ultra-zoom with Fibonacci phyllotaxis. Zoom by φ → identical structure at every rung (`visual-explainers/fractal_zoom.py`).

---

## 1. The Fundamental Scale

The Planck length is the external dimensionful anchor used in this parameterization:

$$\ell_{\text{Pl}} = \sqrt{\frac{\hbar G}{c^3}} = 1.616255 \times 10^{-35}\,\text{m}$$

The Planck mass is $M_{\text{Pl}} = \sqrt{\hbar c / G} = 1.22 \times 10^{19}\,\text{GeV}/c^2$. The relation $\ell_n=\ell_{\text{Pl}}\varphi^n$ supplies dimensionful rung values once the external anchor is chosen. A UV cutoff interpretation for the anchor requires a separately stated regularization and physical closure; it is not fixed by the ladder identity alone.

---

## 2. The Cascade Formula

For any physical scale $\ell$ assigned within this parameterization, the exponent $n$ is:

$$n = \frac{\ln(\ell / \ell_{\text{Pl}})}{\ln\varphi} = \log_\varphi\!\left(\frac{\ell}{\ell_{\text{Pl}}}\right)$$

The cascade is a discrete coordinate ladder rather than a continuous spectrum. Physical scale assignments may use integer or near-integer values of $n$, where a gauge symmetry breaks, a particle decouples, or a dynamical threshold is crossed; each assignment requires its own status and supporting inputs. The selection of which $n$ are "active" is determined by the declared model dynamics—specifically, by the conversion rate $\lambda$, the Qi gate shape, and the dimensionless solver-unit wave-speed diagnostic $c(r)$ along the ratio-evolution string.

### 2.1 Relationship to the Gap

The initial gap $g = 1 - \varphi^{-5}$ (see `cassi-physics.md`) sets the cascade depth for the electroweak scale:

$$\frac{v_0}{M_{\text{Pl}}} = g \cdot \varphi^{-N} \quad\Longrightarrow\quad N = \frac{\ln(g \cdot M_{\text{Pl}} / v_0)}{\ln\varphi} \approx 79.7 \approx 80$$

The exponent $N \approx 80$ for the electroweak-to-Planck ratio is a **consistency check**—it matches the observation that $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ to within 5.3%. The gap relation itself is a **Hypothesized** Wu Xing five-element input ($w=5$); conditional on adopting that input, the cascade-depth expression has zero additional free parameters.

### 2.2 Cascade Invariance

The electroweak cascade depth $N \approx 80$ is robust as an algebraic ratio check against variations in the initial gap $g$ once the $\varphi$-attractor parameterization is adopted. Changing $g$ (i.e., a different Wu Xing number $w$) changes the cosmology ($w_0$, $H_0$ evolution) while leaving the listed Standard Model coupling inputs unchanged. The interpretation that the EW scale dynamically "freezes out" at the same number of $\varphi$-steps from Planck is **Hypothesized** and requires an independent dynamical closure.

---

## 3. Complete Cascade Table


| Step $n$ | Scale (meters) | Physical Meaning | Regime | Epistemic status |
|----------|---------------|-------------------|--------|------------------|
| 0 | $1.6 \times 10^{-35}$ | **Planck length**—external anchor; UV-cutoff reading | Quantum gravity | External; cutoff **Hypothesized** |
| 5 | $1.8 \times 10^{-34}$ | GUT-scale label ($M_{\text{GUT}} \approx 10^{16}$ GeV sits at $n \approx 13.3$–$14.8$, $\ell \approx 10^{-32}$ m; step 5 itself is $1.1\times10^{18}$ GeV) | GUT | Scale **Mapped**; GUT interpretation **Hypothesized** |
| 10 | $2.0 \times 10^{-33}$ | Compactification / string scale | GUT | **Hypothesized** |
| 20 | $2.4 \times 10^{-31}$ | Seesaw scale ($\sim 10^{14}$ GeV, neutrino masses) | GUT/neutrino | **Hypothesized** |
| 40 | $3.7 \times 10^{-27}$ | Inflationary energy scale | Inflation | **Hypothesized** |
| 60 | $5.6 \times 10^{-23}$ | SUSY-breaking / intermediate scale | Desert | **Hypothesized** |
| **80** | **$8.0 \times 10^{-19}$** | **Electroweak scale** ($v_0 \approx 246$ GeV) | Particle physics | **Mapped** ratio; threshold **Hypothesized** |
| 82 | $2.2 \times 10^{-18}$ | Weak boson Compton wavelength ($Z$: 91.2 GeV) | Particle physics | **Mapped** |
| 89 | $6.4 \times 10^{-17}$ | J/ψ charmonium ($m \approx 3.10$ GeV) | Particle physics | **Mapped** |
| **95** | **$1.1 \times 10^{-15}$** | **QCD confinement** ($\Lambda_{\text{QCD}} \sim 200$ MeV) | Nuclear | **Mapped** scale; confinement interpretation **Hypothesized** |
| 96 | $1.9 \times 10^{-15}$ | Muon Compton wavelength ($m_\mu \approx 105.7$ MeV) | Particle physics | **Mapped** |
| 107 | $3.7 \times 10^{-13}$ | Electron Compton wavelength (reduced; $m_e \approx 0.51$ MeV) | Particle physics | **Mapped** |
| **117** | **$5.3 \times 10^{-11}$** | **Bohr radius** (atomic scale, $a_0$) | Atomic | **Mapped** |
| 125 | $2.1 \times 10^{-9}$ | Typical molecular bond length | Molecular | **Mapped** |
| **136** | **$5.0 \times 10^{-7}$** | **Visible light** wavelength (500 nm) | Optical | **Mapped** |
| 142 | $7.7 \times 10^{-6}$ | Cellular scale ($\sim 8$ μm) | Biological | **Mapped** |
| **168** | **$1.7$** | **Human scale** ($\sim 1.7$ m) | Macroscopic | **Mapped** |
| 180 | $6.7 \times 10^{2}$ | Skyscraper scale | Macroscopic | **Mapped** |
| 185 | $8.8 \times 10^{3}$ | Mt Everest height | Planetary | **Mapped** |
| **200** | **$1.3 \times 10^{7}$** | **Earth diameter** | Planetary | **Mapped** |
| 208 | $3.8 \times 10^{8}$ | Earth-Moon distance | Planetary | **Mapped** |
| **220** | **$1.5 \times 10^{11}$** | **Astronomical Unit** (Earth-Sun) | Stellar system | **Mapped** |
| **228** | **$6.0 \times 10^{12}$** | **Solar System radius** ($\sim 40$ AU, Pluto) | Stellar system | **Mapped** |
| 235 | $2.1 \times 10^{14}$ | Inner Oort cloud ($\sim 1400$ AU) | Interstellar | **Mapped** |
| **243** | **$9.5 \times 10^{15}$** | **Light-year** | Interstellar | **Mapped** |
| 245 | $3.1 \times 10^{16}$ | Parsec ($\sim 3.26$ ly) | Interstellar | **Mapped** |
| 250 | $2.8 \times 10^{17}$ | Nearby stars ($\sim 9$ pc) | Interstellar | **Mapped** |
| 260 | $3.5 \times 10^{19}$ | Kiloparsec ($\sim 1.1$ kpc) | Galactic | **Mapped** |
| **267** | **$9.3 \times 10^{20}$** | **Milky Way diameter** ($\sim 30$ kpc) | Galactic | **Mapped** |
| 275 | $4.8 \times 10^{22}$ | Local Group ($\sim 1.6$ Mpc) | Extragalactic | **Mapped** |
| 280 | $5.3 \times 10^{23}$ | Cosmic void scale ($\sim 17$ Mpc) | Extragalactic | **Mapped** |
| **284** | **$3.6 \times 10^{24}$** | **Yin wake of rung 285** ($\Lambda_I = \ell_{285}/\varphi$; the observed BAO ruler lies near the 284.5 half-step, $\sim150$ Mpc) | Cosmological | **Hypothesized** wake mapping; BAO **Mapped** coincidence |
| **285** | **$5.9 \times 10^{24}$** | **Cassi bubble** ($\sim 191$ Mpc) | Multiverse | **Hypothesized** conditional model |
| 288 | $2.5 \times 10^{25}$ | Supercluster scale ($\sim 800$ Mpc) | Cosmological | **Mapped** |
| 290 | $6.5 \times 10^{25}$ | Horizon at recombination ($\sim 2.1$ Gpc) | Cosmological | **Mapped** |
| **292** | **$1.7 \times 10^{26}$** | **Horizon rung** (lattice length $\ell_{292} = 5.5$ Gpc; $R_H = 4.44$ Gpc $= 14.5$ Glyr, $\log_\varphi = 291.54$, c/H₀-consistent) | Observable universe | Horizon scale **Mapped/Calibrated** |

### Step Verification

Key steps are verified against known physical scales:

```
Step  80:  ℓ_Pl × φ^80  = 1.616255e-35 × 5.236e16 = 8.463e-19 m  → E = ħc/ℓ = 233.2 GeV  (EW scale 233.2 GeV ✓; the 246 GeV VEV claim is −5.2% off ✗)
Step  95:  ℓ_Pl × φ^95  = 1.616255e-35 × 7.142e19 = 1.154e-15 m  (QCD 1.0e-15 m: +15.4% ✗; proton λ_C = 2.103e-16 m sits at n = 91.46, not here; E₉₅ = 0.171 GeV ≠ 1 GeV ✗)
Step 117:  ℓ_Pl × φ^117 = 1.616255e-35 × 2.828e24 = 4.572e-11 m  (Bohr radius 5.29e-11 m: −13.6% ✗)
Step 220:  ℓ_Pl × φ^220 = 1.616255e-35 × 9.490e45 = 1.534e11 m   (1.02 AU ✓)
Step 267:  ℓ_Pl × φ^267 = 1.616255e-35 × 6.305e55 = 1.019e21 m   (33 kpc ✓)
Step 284:  ℓ_Pl × φ^284 = 1.616255e-35 × 2.252e59 = 3.639e24 m   (117.9 Mpc, Yin wake; observed BAO ruler ~150 Mpc lies near the 284.5 half-step)
Step 285:  ℓ_Pl × φ^285 = 1.616255e-35 × 3.643e59 = 5.888e24 m   (191 Mpc, bubble ✓)
```
---

## 4. Cascade Zones

The 292-step observable ladder (today) divides naturally into three regimes:

### Zone 1: Quantum ($n = 0$ to $n \approx 80$)
- Planck scale to electroweak scale
- Standard Model scales; an optional GUT extension supplies a conditional high-scale map
- The asserted boundary $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ belongs to that optional gauge extension; unification and running require particle-content and threshold inputs
- The electroweak scale is **Mapped** to $n \approx 80$; the interpretation as a dynamical threshold where the Qi gate begins to engage is **Hypothesized**

### Zone 2: Astrophysics ($n \approx 80$ to $n \approx 285$)
- Electroweak scale to the Cassi bubble
- Structure formation can be modeled with the Qi-gravity extension $\xi = \varphi^6$; its physical coupling is Calibrated/conditional and requires the declared constitutive and density maps
- Structure formation: galaxies, clusters, superclusters
- The wave-speed diagnostic $c(r)$ is dimensionless in solver units, and its physical interpretation requires a separate calibration
- The Qi gate engagement at $r = \varphi^{-1}$ ($a \sim 0.051$, $z \sim 19$) sets the bubble scale only under the declared conditional wake model

### Zone 3: Cosmology ($n \approx 285$ to $n \approx 292$)
- Cassi bubble to Hubble radius
- Only 7 $\varphi$-steps in the rung labels—the bubble sits at 97.8% of today's observable ladder; by volume it is $\sim 10^{-5}$ of the observable universe ($R_H/\ell_{285} = 23.3 \approx \varphi^{6.5}$, +2%)
- Adjacent lattice bubbles sit at $\varphi$-spaced intervals ($\ell_{286} = 309$ Mpc, $\ell_{287} = 500$ Mpc, …)—the nearest lie INSIDE the horizon; the horizon's rung coordinate (291.5 today) is an epoch-dependent cut through the lattice
- A **Hypothesized conditional mapping** associates CMB large-angle anomalies with bubble-boundary geometry at these scales (see `foundations/bubble-edge-geometry.md`)

---

## 5. Cascade Step Selection: Wake Wave Mechanism

Not every integer $n$ corresponds to an observable physical scale. The wake wave mechanism selects which steps "activate":

### 5.1 The String-Wake Feedback Loop

The global ratio $r(t) = \langle E_Y\rangle/\langle E_I\rangle$ evolves along the "ratio-space string" from $r_0 \approx 0.047$ to $r = \varphi$. As it moves, it generates wake waves—spatial density perturbations—through the conversion term. For a named solver run, $\lambda$ is a solver normalization (for example, $\lambda=0.1$ when explicitly passed), not a dimensional rate. The displayed local wave-speed diagnostic is:

$$c_{\mathrm{solver}}(r) = \sqrt{\frac{\lambda \cdot \text{gate}(r) \cdot |r-\varphi|}{(1+r)/2}}$$

This $c_{\mathrm{solver}}(r)$ is dimensionless and does not by itself represent the physical speed of light or a calibrated SI wave speed. In solver units, the wake spacing is $c_{\mathrm{solver}}(r)\times\tau_{\mathrm{solver}}(r)$, where $\tau_{\mathrm{solver}}(r)$ is the residence time at ratio $r$ (inverse of $dr/d\ln a$). A physical spacing requires an independently calibrated conversion from solver length and time units. The claim that successive wake spacings follow $\varphi$-powers is a Hypothesized conditional map requiring separately declared scaling for $c_{\mathrm{solver}}$ and $\tau_{\mathrm{solver}}$; it does not follow from the diagnostic alone.

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

---

## 6. The Wu Xing Bubble (Step 285; Hypothesized Conditional Model)

The following section is a **Hypothesized conditional bubble model**. Its coherence-length, gate-epoch, galaxy-count, and lattice-spacing assignments are model inputs or mapped targets.

Within this model, the bubble at step 285 is assigned as the coherence length of the Wu Xing number $w$—the scale over which the cosmological initial conditions remain constant. Its scale is tied to the comoving horizon at the epoch when the Qi gate is proposed to engage ($r = \varphi^{-1}$, $a \approx 0.051$, $z \approx 19$).

**Bubble properties:**
- Diameter: $\sim 191$ Mpc (comoving)
- Position in cascade: step 285 of today's observable ladder (97.8%; volume fraction $\sim 10^{-5}$)
- Model target: $\sim 10^6$ Milky-Way-sized galaxies
- Conditional lattice assignment: adjacent bubbles carry identical $w=5$ and are arranged at $\varphi$-spaced intervals in the chord lattice. They are separated by voids at $C=-1$ sites of the condensation field (`visual-explainers/chord_lattice.py`).

The bubble at step 285 has diameter $\sim191$ Mpc (comoving), while the measured sound horizon is $r_d=147.1$ Mpc (DESI/Planck). The ruler corresponds to $n=284.46$ in $\ell_n=\ell_{\text{Pl}}\varphi^n$, and $\ell_{284.5}=\sqrt{\ell_{284}\ell_{285}}=150.0$ Mpc (+1.98%—a **Mapped scale coincidence** within 2%). Step 284 (117.9 Mpc) is the Yin wake wavelength of the rung-285 lattice ($\Lambda_I^{(285)}=\ell_{285}/\varphi$); the wake wave modulation in $P(k)$ therefore sits adjacent to the BAO feature—entangled but separable through their different period structures (fixed scale vs. fixed ratio). See `cosmology/desi-lattice-averaging.md` §3.

---

## 7. Lattice Structure at Cascade Rungs

The optional condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$ supplies a conditional 3D checkerboard bubble-lattice construction at selected cascade rungs—see `foundations/bubble-lattice-fabric.md` for the full derivation. The cascade ladder ($\ell_n = \ell_{\text{Pl}}\,\varphi^n$) is the 1D slice along the string axis through this construction; each rung corresponds to a level set of $B$ at a specific scale factor.

The lattice structure varies with the condensation dimension $P_\parallel(n)$, which counts how many cascade rungs encode one structural repeat along the string axis. The following table catalogues key rungs:

| Step $n$ | Physical structure | Lattice structure |
|---|---|---|
| 0 | Planck length | $\sigma$-regularized crossover; discrete lattice dissolves into harmonic regime |
| 142–168 | Human body | 26-rung nested lattice; $P_\parallel = 2$ (13 chakra nodes at 2-rung spacing) |
| 144 | Neuron soma (~20 µm) | Neural hierarchy anchor; 8 φ-spaced lattice levels |
| 285 | Cassi bubble | $P_\parallel = 1$; staggered 2D checkerboard; foreground bubble in chord lattice |
| >292 | Megacascade | Chord lattice of $w=5$ bubbles; 5-arm Fibonacci spiral at gigacascade octave |

**Note:** $P_\parallel(n)$ varies with scale—1 rung at cosmological scales, 2 rungs at human scales. The $n$-dependence of $P_\parallel$ is not yet derived from first principles. The $P_\parallel = 1$ cosmological reading is the boundary-consistent one (tier Hypothesized): the Cassi bubble sits 6.5 rungs inside the horizon's nesting depth, the horizon cut is a half-rung, and the $P_\parallel = 1$ field reads $\approx$ void level there; the allowed set is $\{1, 2\}$ per `foundations/bubble-lattice-fabric.md` §8.1.

For the full derivation, the selected-level directional edge-slope proxy is
$R(\theta_{\mathrm{cond}})=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\mathrm{cond}}}{\theta_{\mathrm{cond}}}}$; at the phenomenologically selected $\theta_{\mathrm{cond}}=0.45$, $R=1.7072$. This ratio varies with the selected level and is a conditional geometric-proxy benchmark, not a universal or zero-parameter constant or canonical PDE output. The fixed-step PDE diagnostic retains no $C=0.45$ edge; any cosmological or biological test requires an independently identified boundary and proxy-to-observable map. See `foundations/bubble-lattice-fabric.md` for the epistemic boundaries.

---

## 8. Testable Implications

### 8.1 $\varphi$-Periodic $P(k)$ Modulation

The wake waves imprint a log-periodic signal on the matter power spectrum:

$$\Delta(\ln k) = \ln\varphi \approx 0.4812$$

This is a **zero-parameter, falsifiable prediction**—see `predictions/falsifiable-predictions.md` §5 and `cassi-physics.md`. The lattice origin is now explicit (`cosmology/desi-lattice-averaging.md` §2): the comb follows from the triaxial cell ($\ell_n, \ell_n/\varphi, \ell_n$) and lattice nesting, so the modulation period $\ln\varphi$ is the inter-rung spacing and the first pair $(k_0, \varphi k_0)$ carries predicted multiplicities 4:2. Orthogonal to BAO (which has constant period in $k$-space), the Cassi modulation has constant period in $\ln k$-space. Subtract the BAO template; search the residual for $\ln\varphi$ periodicity. DESI DR2: marginal (2–3σ). Euclid (2027): definitive (>5σ).

### 8.2 Void and Structure Scale Ratios

Structures formed by the wake mechanism should show $\varphi$-scaled separations. While the void size function is smooth (not multi-peaked), the wake wave mechanism predicts subtle $\varphi$-periodic modulations in the correlation function $\xi(r)$ and the void-galaxy cross-correlation. These are distinguishable from BAO through their fixed-ratio (not fixed-scale) structure.

### 8.3 Bubble Edge Imprint

The bubble at step 285 is bounded by adjacent bubbles at identical $w=5$ in the chord lattice. The boundary—the level set of the condensation field $C(x,y) = \theta_{\text{cond}}$—imprints a preferred axis on the CMB at $\ell < 5$. The axis is set by the bubble's triaxial geometry (Yang axis vs. boundary normal), not by a $w$-gradient. The $12.2^\circ$ alignment angle is predicted from the geometry. See `cosmology/observational_constraints.md` §4 and `foundations/bubble-edge-geometry.md`.

---

## 9. Open Questions

1. **Why 292 steps?** $\log_\varphi(M_{\text{Pl}}/H_0) \approx 291.54$ today; is this number derivable from the PDE dynamics, or is it set by the initial conditions of inflation? 292 is not a constant of the cascade—the cascade is unbounded ($n \in \mathbb{Z}$, megacascade above, microcascade below), and 292 is today's horizon rung (epoch-dependent; $N(t) = \log_\varphi(R_H(t)/\ell_{\text{Pl}})$ evolves as $H(r) \to \varphi$). The derivable targets are the asymptotic horizon $N_\infty \approx 294.2$ under the verified Yang-fraction-weighted coupling (292–296 across documented forms—`foundations/wake-geometry.md` §4) and the epoch selection via the initial condition $r_0$.

2. **Why these specific activated steps?** The set $\{1, 2, 3, 5, 6, 26, 80, 292\}$ has no obvious pattern. Do the "dark" steps carry physical meaning (e.g., sterile neutrino masses, dark sector couplings)? Two dark steps host wake-anchored particles (`foundations/wake-geometry.md` §3): rung 89 hosts the J/ψ ($n = 88.98$, 1.0%—a golden-angle closure level) and rung 96 the muon ($n = 96.000$, 0.01%—wake-anchored).

3. **Cascade spacing regularity?** The steps are irregularly spaced: sparse at low $n$, dense at high $n$ (near $\varphi$). Is there an underlying periodicity in $\ln n$ space?

4. **Full 3D PDE verification.** The cascade table is derived from the homogeneous ODE + dimensional analysis. The full 3D PDE should independently reproduce the activated step set through the wake wave mechanism. This requires N≥32 simulations with structure formation.

---

## References

- `foundations/bubble-lattice-fabric.md`—Conditional 3D checkerboard lattice; φ-elliptical bubble shape, level-dependent edge-slope proxy, and condensation field derivation
- `cassi-physics.md`—Gap derivation, governing PDE, and $\varphi$-periodic $P(k)$ prediction
- `parameter-inventory.md`—Complete parameter classification (46 parameters: F1/D24/C0/E7/I6/N8)
- `cosmology/observational_constraints.md` §2.6—Rotation curve prediction ($\xi=\varphi^6$)
- `cosmology/observational_constraints.md` §4—CMB bubble-boundary axis analysis
- `predictions/falsifiable-predictions.md`—Full prediction catalogue (47 entries)
- `visual-explainers/fractal_zoom.py`—fractal zoom: cascade self-similarity, φ-spaced rings
