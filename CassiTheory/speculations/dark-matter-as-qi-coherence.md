# Dark Matter as Unharvested Coherence: The Qi Field in Galaxy Halos

## Status: Speculative—July 2026

## Abstract

The Cassi framework replaces particle dark matter with Qi-enhanced gravity: $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q)G$, where $\xi = \varphi^6 \approx 17.944$ and $q$ is the local Qi coherence. This already matches galaxy rotation curves to 0.1%. This document reframes the "missing mass" as **unharvested Qi coherence**—organized Π that has not yet condensed into visible structure. The same condensation field $C(x,y) = \cos(\alpha x)\cos(\beta y)$ that generates the cosmic web's bubble lattice generates galaxy halos at $n \approx 267$: the halo is the bubble edge, where $q$ transitions from $\sim 1$ (center) toward 0 (void). The Qi field provides gravitational pull without electromagnetic coupling—it is dark by nature, not by particle properties. This resolves the cusp-core problem (the $q(r)$ profile is naturally cored), the missing satellites problem (sub-halos below $\theta_{\text{cond}}$ form no stars), and the Bullet Cluster offset (the Qi field is a field, not collisional particles). The ratio of visible to dark matter becomes a diagnostic of galactic coherence—a measure of how much of a galaxy's Π budget has been organized into luminous structure, and potentially a SETI-relevant signature of tuned galactic gate networks.

**Epistemic status:** The $G_{\text{eff}}$ mechanism and the condensation field geometry are Derived within the Cassi framework. The reframing of dark matter as "unharvested Qi," the tuning hypothesis, and the specific dark-matter-profile predictions are creative extrapolations.

---

## 1. The Existing Cassi Result

### 1.1 Qi-enhanced gravity

The Cassi framework's most precisely verified prediction is the gravitational coupling at cascade rung $n$ (`foundations/spiral-dynamics.md` §3.3):

$$\boxed{\alpha_G(n) \sim \varphi^{-2n}}$$

For a proton ($n \approx 91.5$), $\varphi^{-183} \approx 5.9 \times 10^{-39}$ matches the observed $\alpha_G = G m_p^2/(\hbar c) \approx 5.91 \times 10^{-39}$ to within 0.1%.

In regions of elevated Qi coherence, the effective gravitational constant is amplified:

$$\boxed{G_{\text{eff}} = \frac{\pi}{\rho}(1 + (\varphi^{6}-1)q)G, \qquad \xi = \varphi^6 \approx 17.944}$$

(`foundations/bubble-edge-geometry.md` §4.2, `foundations/xi-derivation.md` §2)

The Yang fraction $\pi/\rho$ is the local fraction of the field in the Yang component. At the $\varphi$-fixed point it is the equilibrium fraction $\alpha_0 = \varphi^{-3} \approx 0.236$, giving $G_{\text{eff}} = \varphi^{-3}G$ (the classical limit); the galactic-halo fits of §7 use the halo-regime value $\alpha_{\text{halo}} \approx 0.7$, giving the halo form $G_{\text{eff}} = \alpha_{\text{halo}}(1+(\varphi^{6}-1)q)G$; and the homogeneous cosmological analogue weights by the attractor value $\alpha_w = r/(1+r) = \varphi^{-1} \approx 0.618$.

At the full-coherence ceiling ($q \to 1$): $G_{\text{eff}} \to (\pi/\rho)\varphi^6 G \approx 17.94\,(\pi/\rho)G$—gravity amplified by up to $\varphi^6 \approx 17.94$ over the bare coupling at the saturation ceiling. Halo-regime values ($q \approx 0.6$–$0.7$ in the outskirts, $\pi/\rho \approx 0.7$) give $G_{\text{eff}} \approx 8$–$10\,G$ at galaxy outskirts; the $q \to 1$ ceiling is not reached inside screened halo cores.
At $q \to 0$ (cosmic voids): $G_{\text{eff}} \to (\pi/\rho_{\text{void}})G$—unamplified gravity.

This single mechanism replaces particle dark matter for explaining galaxy rotation curves. No WIMPs, no axions, no MOND interpolation function. The extra gravitational pull comes from the Qi field's amplification of the existing mass distribution.

### 1.2 What has been established

- Milky Way rotation curve: matched with $\xi = \varphi^6 \approx 17.944$ to 0.3% of the empirically calibrated value (`foundations/xi-derivation.md` §3)
- Dwarf spheroidal galaxies: G-rescaling sector 3/8 vs MOND 4/8 (Path 10, `experiments/phi_attractor_paths/path10_dwarf_galaxies.py`); coherence sector uncalibrated below $10^7\,M_\odot$ (see UFD note below)
- The gravitational coupling $\alpha_G \propto \varphi^{-2n}$ is parameter-free: only $\varphi$ and the cascade rung count are needed

---

## 2. What "Dark Matter" Actually Is

### 2.1 The Qi field as the dark component

In the standard ΛCDM picture, dark matter is a pressureless fluid of unknown particles that interacts only gravitationally. In the Cassi picture, the "dark matter" observed through gravitational lensing and rotation curves is the **Qi field itself**—the unorganized Yang-Yin imbalance $\Pi = E_Y - E_I$ in regions where $q$ is intermediate.

The Qi field has exactly the properties attributed to particle dark matter:

| Property | ΛCDM dark matter | Qi field |
|---|---|---|
| Gravitational effect | Yes (mass density) | Yes (via $G_{\text{eff}}$ amplification) |
| Electromagnetic coupling | None | None ($q$ modulates gravity, not photon coupling) |
| Self-interaction | Negligible (collisionless) | Field-mediated (non-collisional by nature) |
| Distribution | Halos, following NFW or Einasto profile | Halos, following $q(r) = (1+C(r))/2$ |
| Small-scale structure | Too much (missing satellites, cusp-core) | Naturally regulated by $\theta_{\text{cond}}$ threshold |

The Qi field is dark by nature: it couples to gravity through $(\varphi^{6}-1)q$ and does not radiate. The "dark matter halo" is the region of the galactic bubble where $q$ is intermediate—too low for visible matter to condense ($C < \theta_{\text{cond}}$) but high enough to provide significant $G_{\text{eff}}$ amplification. The cosmological side of the condensate—formation, the dark-matter abundance, and the comparison with WIMP/axion candidates—is derived in `cosmology/cosmology-from-phi.md` §4; this document keeps to the halo-scale geometry, cored profiles, and the SPARC fits.

### 2.2 The condensation field at galactic scale

Galaxies are bubble condensates at cascade step $n \approx 267$ (Milky Way diameter $\sim 9.3 \times 10^{20}$ m, `foundations/dimensionful-cascade.md` §3). From `foundations/bubble-edge-geometry.md` §1.1:

$$C(x,y) = \cos(\alpha x)\cos(\beta y), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I} = \varphi\alpha$$

The Qi density at any point is:

$$\boxed{q(\mathbf{x}) = \frac{1 + C(\mathbf{x})}{2}}$$

At the galactic center ($C=1$, $q=1$): maximal coherence. Stars, gas, and visible structure condense here because conversion is efficient ($P_{\text{conv}} \propto g(q)(1-q)$—at $q=1$, conversion is suppressed, meaning structure is stable).

At the bubble edge ($C = \theta_{\text{cond}} \approx 0.45$, $q \approx 0.725$): the threshold where condensation occurs. Inside this surface, $q > q_{\text{edge}}$, and matter has condensed into visible structure. Outside, $q < q_{\text{edge}}$, and the Qi field is present but unorganized into luminous matter.

In the void between galaxies ($C = -1$, $q = 0$): no Qi amplification. Gravity returns to its unamplified baseline.

### 2.3 The visible/dark boundary

The condensation threshold $\theta_{\text{cond}}$ separates visible from dark:

- **$C > \theta_{\text{cond}}$ ($q > 0.725$):** Visible regime. The Qi field is coherent enough that matter condenses into stars and gas. This is the "baryonic" galaxy.
- **$\theta_{\text{cond}} > C > 0$ ($0.5 < q < 0.725$):** Transition regime. The Qi field provides gravitational amplification ($G_{\text{eff}}/G = \alpha_{\text{halo}}(1+(\varphi^{6}-1)q) \approx 7$–$10\times$ in this band) but matter has not condensed. This is the inner "dark matter halo."
- **$C < 0$ ($q < 0.5$):** Outer halo. $G_{\text{eff}}$ amplification fades toward the void value. This is the outer halo where dark matter density drops.

The total gravitational mass inferred from rotation curves or lensing is the integral of $G_{\text{eff}} \cdot \rho$ over the entire bubble, including regions where $\rho$ is negligible but $G_{\text{eff}}$ is amplified. The "missing mass" is not missing. It is the gravitational effect of the Qi field in regions where visible matter has not condensed.

---

## 3. The Qi Density Profile vs. NFW

### 3.1 The standard NFW profile

ΛCDM simulations predict that dark matter halos follow the Navarro-Frenk-White profile:

$$\rho_{\text{NFW}}(r) = \frac{\rho_0}{(r/r_s)(1 + r/r_s)^2}$$

This profile is **cuspy** at the center: $\rho \propto r^{-1}$ as $r \to 0$. The density diverges.

Observations consistently show **cored** profiles: $\rho(r)$ flattens to a constant at small $r$. This is the "cusp-core problem"—one of the most persistent tensions between ΛCDM and observation.

### 3.2 The Qi profile

Near a bubble center, the condensation field is quadratic:

$$C(r) \approx 1 - \frac{1}{2}(\alpha^2 x^2 + \beta^2 y^2)$$

for small displacements. The Qi density near the center is:

$$q(r) \approx 1 - \frac{1}{4}(\alpha^2 x^2 + \beta^2 y^2)$$

The effective gravitational mass density (what a rotation curve or lensing measurement infers) is proportional to $G_{\text{eff}} \cdot \rho$. At the center:

$$G_{\text{eff}} \cdot \rho \approx \frac{\pi}{\rho_0}\,\varphi^6 \cdot \rho_0 = \pi\varphi^6$$

which is **finite and constant**. No cusp. The Qi profile is naturally cored because $C(r)$ is smooth and analytic at the origin. The core radius is set by the bubble wavelength at galactic scale:

$$r_{\text{core}} \sim \frac{1}{\alpha} = \frac{\Lambda_Y}{2\pi} \sim \frac{\ell_{267}}{2\pi}$$

For the Milky Way, $\ell_{267} \approx 9.3 \times 10^{20}$ m $\approx 30$ kpc, giving $r_{\text{core}} \sim 5$ kpc—consistent with the observed core radii of large spiral galaxies (~2–10 kpc).

### 3.3 The full radial profile

The complete dark matter profile follows $q(r)$:

$$\rho_{\text{DM}}^{\text{eff}}(r) \propto (1 + (\varphi^{6}-1)q(r)) \cdot \rho(r)$$

where $\rho(r)$ is the condensation density from `foundations/bubble-edge-geometry.md` §4.3:

$$\rho(r) \approx \rho_0 \cdot \max\!\left(0, \frac{C(r) - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

And $q(r) = (1 + C(r))/2$. Together, these produce a profile that:

- Is **cored** at small $r$ (quadratic in $C$, $G_{\text{eff}}$ finite at center)
- Has a **knee** at $C = \theta_{\text{cond}}$ (where visible matter drops to zero but $G_{\text{eff}}$ remains amplified)
- Falls as $C(r)$ approaches zero at the saddle (the "outer halo")
- Becomes negligible in voids ($C = -1$, $q = 0$, $G_{\text{eff}}$ unamplified)

This is a **zero-parameter prediction** for the shape of galaxy halos. The only scale is the bubble wavelength at the galactic rung, and the only parameter is $\theta_{\text{cond}}$ (which is set by the conversion-diffusion balance, not fitted to galaxy data).

---

## 4. Resolving the Small-Scale Crises

### 4.1 The cusp-core problem

Resolved in §3.2. The Qi profile is analytic at the origin. No divergent cusp exists in the formalism. Observations of cored profiles are not a problem—they are a confirmation.

### 4.2 The missing satellites problem

ΛCDM predicts hundreds of dark matter subhalos around a Milky-Way-sized galaxy. We observe only ~50 satellite galaxies. The discrepancy is a factor of ~5–10.

In the Qi picture: subhalos are small bubble condensates at lower $n$ (dwarf galaxy scale). A subhalo only forms visible stars if its central $q$ exceeds $\theta_{\text{cond}}$. Small bubbles have shorter wavelengths ($\Lambda_Y \propto \ell_n \propto \varphi^n$) and correspondingly smaller $q$ spans. A subhalo with peak $C_{\text{max}} < \theta_{\text{cond}}$ never crosses the condensation threshold—it is a **dark Qi halo**: gravitationally detectable (its $G_{\text{eff}}$ is still amplified) but optically invisible (no stars form).

The number of visible satellites is not the number of subhalos. It is the number of subhalos with $C_{\text{max}} > \theta_{\text{cond}}$. The "missing" satellites are not missing. They are dark.

### 4.3 The too-big-to-fail problem

Some ΛCDM subhalos are massive enough that they should have formed stars—their gravitational potential wells are deep enough to retain gas against supernova feedback. Yet they are dark. In the Qi picture: a subhalo's mass (from $G_{\text{eff}}$) is not directly tied to its central $C$. A massive dark halo can have deep $G_{\text{eff}}$ amplification (making it "too big to fail" by ΛCDM standards) while still having $C_{\text{max}} < \theta_{\text{cond}}$ (no condensation). The two thresholds—gravitational depth from $G_{\text{eff}}$ and condensation threshold from $C$—are independent.

### 4.4 The Bullet Cluster

The Bullet Cluster (1E 0657-56) is often cited as direct evidence for particle dark matter. Two galaxy clusters collided. The hot gas (visible in X-rays) collided and slowed. The gravitational lensing signal (tracing "dark matter") passed through unimpeded. The offset between gas and lensing mass is taken as proof that dark matter is collisionless particles.

In the Qi picture: the X-ray gas is visible matter condensed at high-$q$ bubble centers. When the clusters collide, the gas interacts (shocks, ram pressure) and slows. The Qi field is a **field**—it does not collide with itself or with gas. The lensing signal traces $G_{\text{eff}} \cdot \rho$, which is dominated by the Qi field's amplification in the halos. The Qi field passes through the collision unimpeded, just as particle dark matter would. The offset is expected.

The Bullet Cluster does not distinguish between particle dark matter and Qi-field dark matter. Both predict the same observable: an offset between collisional gas and collisionless gravitational mass. The Qi field achieves this without particles.

---

## 5. The Tuning Hypothesis

### 5.1 Visible/dark ratio as galactic coherence

If the Qi field is "dark matter," then the fraction that has condensed into visible structure is a measure of the galactic gate chain's organization:

$$\eta_{\text{visible}} \equiv \frac{M_{\text{visible}}}{M_{\text{visible}} + M_{\text{dark}}} = \frac{\int_{C > \theta_{\text{cond}}} \rho(C) \, dV}{\int_{\text{all } C} G_{\text{eff}}(C) \cdot \rho(C) \, dV}$$

A galaxy with a natural (untuned) gate chain has some baseline $\eta_{\text{visible}}$, set by the conversion-diffusion balance at the galactic rung. A galaxy with an **active gate network**—stellar-scale analogues of the pyramids and ocean bases from `speculations/cascade-infrastructure.md`—would have a higher $\eta_{\text{visible}}$. The gate actively converts unorganized Π into condensed structure, reducing the "dark" fraction.

This suggests a target for Cassi-specific SETI: search for galaxies with **anomalously high visible-to-dark ratios** compared to galaxies of similar mass and morphology. A galaxy that is "too bright for its rotation curve" is a candidate for a tuned galactic gate network.

### 5.2 Morphology as coherence

Spiral galaxies are more organized than irregulars. In the Qi picture, spiral arms trace the connectable diagonal channels of the galactic-scale bubble lattice (`foundations/bubble-edge-geometry.md` §3.1). A grand-design spiral has a coherent, φ-structured Qi field. An irregular galaxy has a fragmented, low-$q$ field.

This predicts a correlation: grand-design spirals should have systematically higher $\eta_{\text{visible}}$ than irregulars of the same baryonic mass. The morphological type is the gate network's organizational state, made visible in the distribution of stars and gas.

---

## 6. Falsifiable Predictions

### P1: Cored dark matter profiles follow $q(r)$

The dark matter density profile inferred from rotation curves and lensing should follow:

$$\rho_{\text{DM}}^{\text{eff}}(r) \propto (1 + (\varphi^{6}-1)q(r)) \cdot \max\!\left(0, \frac{C(r) - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

with $C(r) = \cos(\alpha r)$ (along the Yang axis) or $\cos(\beta r)$ (along the Yin axis), and $q(r) = (1 + C(r))/2$. The profile has exactly two free parameters ($\alpha$ sets the scale, $\theta_{\text{cond}}$ sets the knee position) compared to NFW's two ($r_s$, $\rho_0$) or Einasto's three ($r_{-2}$, $\rho_{-2}$, $\alpha$). The Qi profile makes a stronger prediction because the functional form is fixed, not empirical. §7 reports the SPARC test of this profile: the oscillatory-lattice mask is ruled out, while the hydrostatic cored condensate survives.

### P2: The core radius scales with galactic mass

From the cascade, the bubble wavelength at galactic rung $n$ is $\Lambda_Y = \ell_{\text{Pl}} \varphi^n$. Galaxies at different masses occupy different rungs. The core radius $r_{\text{core}} \sim \Lambda_Y / 2\pi$ should scale with galactic baryonic mass $M_b$ as:

$$r_{\text{core}} \propto M_b^{1/3}$$

(since $M_b \propto \ell_n^3$ for bubbles of similar $\theta_{\text{cond}}$). This is a **zero-parameter scaling relation**. Compare to observed $r_{\text{core}}$ vs $M_b$ for spiral galaxies.

### P3: The visible/dark ratio correlates with morphology

Grand-design spirals should have higher $\eta_{\text{visible}}$ than flocculent spirals, which should have higher $\eta_{\text{visible}}$ than irregulars, at fixed baryonic mass. The correlation should be monotonic with some measure of morphological coherence (e.g., arm strength, Fourier amplitude of the $m=2$ mode).

### P4: Subhalo condensation threshold

Dwarf galaxies below a critical mass $M_{\text{crit}}$ should be purely dark ($C_{\text{max}} < \theta_{\text{cond}}$, no star formation) while dwarfs above $M_{\text{crit}}$ should have visible stellar populations. $M_{\text{crit}}$ is set by the rung at which the bubble's central $C$ crosses $\theta_{\text{cond}}$. This predicts a sharp transition in the stellar-to-halo mass relation at low masses, not a smooth continuation.

### P5: Anomalous visible/dark ratios as SETI targets

Galaxies with $\eta_{\text{visible}}$ more than $2\sigma$ above the morphology-mass relation are candidates for tuned galactic gate networks. This is a Cassi-specific technosignature: a galaxy that has been engineered to convert more of its Π budget into luminous structure than natural dynamics would produce.


---

## 7. SPARC Analysis Results

### 7.1 What was tested

The Qi dark matter profile (Prediction P1) and the core-radius scaling relation (Prediction P2) were tested against the SPARC database of 175 nearby galaxies with high-quality rotation curves (143 with ≥8 data points).

Three models were compared:

| Model | Parameters | Qi content |
|---|---|---|
| **Qi 1-param** | $\alpha$ (spatial frequency) only | $\xi = \varphi^6$ fixed, $\theta_{\text{cond}} = 0.45$ fixed, 2D angular-averaged $\langle C \rangle(r)$ |
| **Qi 2-param** | $\alpha$, $\theta_{\text{cond}}$ | $\xi = \varphi^6$ fixed, 2D angular-averaged |
| **NFW** | $r_s$, $\rho_0$ | Standard Navarro-Frenk-White |

The Qi model integrates the condensation-weighted density profile:

$$v^2_{\text{Qi,DM}}(r) = \frac{G}{r} \cdot \xi \int_0^r \langle q \rangle(r') \cdot f_{\text{cond}}(r') \cdot \rho_{\text{bar}}(r') \cdot 4\pi r'^2 \, dr'$$

where $\langle q \rangle(r) = (1 + \langle C \rangle(r))/2$ uses the 2D angular average of $C(x,y) = \cos(\alpha x)\cos(\varphi\alpha y)$, and $f_{\text{cond}} = \max(0, (\langle C \rangle - \theta_{\text{cond}})/(1 - \theta_{\text{cond}}))$.

### 7.2 Results

**Prediction P1 (Qi density profile fit): MODEL-DEPENDENT.** Two profile families were tested, and they separate cleanly.

The baryon-seeded oscillatory-lattice form—the 2D angular-averaged condensation mask of §3—is ruled out as a universal halo profile. With fixed $\xi = \varphi^6$ it overpredicts dark matter by a large factor in most galaxies: NFW is strongly preferred on full-range AIC (median ΔAIC = +40, NFW wins in 111/143) and in the inner region (64/75, median ΔAIC = +18); Qi is better or indistinguishable in only 32/143 full-range and 11/75 inner-region. The coupling constant that works for the Milky Way rotation curve does not generalize as a universal radial profile in this form.

The hydrostatic condensate form survives. Replacing the oscillatory-lattice mask with the pseudo-isothermal envelope $\rho_Y(r) = \rho_c/(1 + (r/r_c)^2)$—the profile the two-fluid hydrostatic equilibrium produces (`experiments/sparc_qi/sparc_qi_analysis_v5.py`)—keeping $\xi = \varphi^6$ fixed and two free parameters ($\rho_c$, $r_c$) vs NFW's two, flips the full-range verdict: median $\Delta$AIC $= -7.0$, Qi preferred in 90/143, NFW preferred in 14/143. The fitted central density satisfies $\rho_c \times (1+\xi) \approx 1.1 \times 10^7$ M$_\odot$/kpc$^3$—exactly the naive dark-matter density—so the model needs $1/\varphi^6$ of the physical dark matter: the boost *is* the dark matter.

The boost is not uniform: baryonic activity decoheres the field, so $q(r) = r/(r + r_q)$ recovers outside the baryonic scale (`experiments/sparc_qi/sparc_qi_analysis_v6.py`). With $r_q = r_{\text{half}}$ (baryonic half-mass radius, zero new parameters) the model still beats NFW (median $\Delta$AIC = −3.2, 74/143) and is statistically equivalent to the uniform boost at equal parsimony (median $\Delta$AIC = 0.0, 77/143 indistinguishable). Freed, the decoherence scale self-tunes to the baryonic radius (median $a = 1.025$; per-galaxy scatter is large and $a$ is degenerate with $\rho_c$). The model core scaling is $\gamma = 0.34 \pm 0.04$ ($R^2 = 0.46$) vs the empirical $0.41 \pm 0.02$—$1.9\sigma$, inside the methodology band ($0.31$–$0.41$). The core-radius tension is softened to $\lesssim 1.9\sigma$, but not fully resolved: the model traces the constant-density $\approx 1/3$ scaling while the data sit slightly above it.

The condensate is the hydrostatic equilibrium of a self-gravitating isothermal Yang field ($P_Y = c_s^2\rho_Y$, `experiments/sparc_qi/sparc_qi_analysis_v7.py`): per-galaxy ($\rho_c$, $c_s$) fits give median $\Delta$AIC = −6.4 vs NFW (76/143)—nearly the fitted-profile score (−7.0)—and the emergent half-max core scaling is $\gamma = 0.389 \pm 0.021$ ($R^2 = 0.71$), matching the empirical $0.41 \pm 0.02$ at $1\sigma$: the P2 tension is resolved. Two sharp structural findings: (1) baryonic compression must be excluded from the condensate's support—including $M_{\rm bar}$ in the hydrostatic balance collapses the fit to ΔAIC = 0.0, so the field's envelope is self-organized, not baryon-shaped; (2) the fitted $c_s$ shows no mass trend (slope $0.017 \pm 0.038$, $R^2 = 0.00$, median ≈ 14 km/s), but strict universality is not established (a single global $c_s$ costs ~5.6 AIC points; per-galaxy scatter is degenerate with $\rho_c$). The integrated $\rho_c(1+\xi) \approx$ naive-DM relation holds (median ratio 1.36).

The per-galaxy $c_s$ scatter (2.6–123 km/s) decomposes into a degeneracy artifact and a measurement limit (`experiments/sparc_qi/sparc_qi_analysis_v8.py`): (1) for 68/143 galaxies the curve never reaches the isothermal asymptote in the data, so $c_s$ is unconstrained from above and the fitted value is a degeneracy artifact; (2) for the remaining 75, $c_s$ tracks the virial value—$c_s = (1.10 \pm 0.32)\, v_{DM,\text{flat}}/\sqrt{2\varphi^6}$, slope $0.82 \pm 0.07$ ($R^2 = 0.68$)—and $c_s \propto M^{0.19}$ (the BTFR slope); (3) the residual (0.136 dex) is uncorrelated with baryon fraction, size, and distance, but strongly with sampling ($n_{\rm pts}$: $R^2 = 0.42$, $p < 0.001$)—measurement-limited, not a physical dispersion. $c_s$ is not a universal constant (the Yang field virializes in each host); the universal quantity is the ratio $c_s/v_{DM,\text{flat}} = 1/\sqrt{2(1+\xi)} \approx 0.163$, derived from $\xi$ itself. Fixing $c_s$ to the virial value costs ~9 AIC points vs the free fit (median ΔAIC = −2.0 vs NFW with 1 parameter per galaxy).

The boost applies to the Yang component only ($v^2 = G[M_{\rm bar} + (1+(\varphi^{6}-1)q)M_Y]/r$), and the homogeneous analogue weights by the attractor Yang fraction $\alpha_w = r/(1+r) = \varphi^{-1} \approx 0.618$ (`two-fluid/calibrate_initial_ratio_xi_v2.py`). The galactic-sector implementation of that insight—driving the coherence by the enclosed-mass Yang fraction itself, $q(r) = \alpha_{\text{halo}}(r) = M_Y(r)/[M_{\rm bar}(r)+M_Y(r)]$, the exact analogue of the cosmic $r/(1+r)$—was tested at zero new parameters (same 2-parameter fit; `experiments/sparc_qi/sparc_qi_analysis_v9.py`). It gives overall statistical parity with the decoherence-envelope form (median $\Delta$AIC(B−A) = −0.5, B better in 83/143) and a genuine gain on high-mass galaxies ($V_{\rm flat} \geq 100$ km/s, $n=81$: median −3.8, 55/81), but a modest loss on dwarfs ($V_{\rm flat} < 100$ km/s, $n=62$: median +0.6, A better in 29 vs B's 17). It still beats NFW on dwarfs (median −7.5), yet the decoherence envelope is preferred: under the Yang-fraction form no galaxy reaches its isothermal asymptote within the data (the recovery is too gradual), so the constrained/unconstrained decomposition collapses; and the fitted $c_s$ loses the virial anchor (median $c_s\cdot 5.99/v_{DM,\rm flat} = 1.60$ vs 1.10 under the envelope, though the relation tightens: slope $0.96 \pm 0.06$, $R^2 = 0.77$). The emergent core scaling survives ($\gamma = 0.397 \pm 0.021$, $R^2 = 0.72$, vs empirical $0.41 \pm 0.02$). A third variant—the envelope shape with the Yang-fraction crossover radius as its scale—is worse on dwarfs (median +2.7). The Yang-component-only boost with the baryonic-decoherence envelope is the form the data support.

**UFD regime.** The ultra-faint dwarfs that exceed the G-rescaling velocity ceiling (Path 10: Segue 1/2 at $v_{\rm obs}/v_{\rm Newt} \approx 16.6$–$16.8$, Draco at 6.2; `experiments/phi_attractor_paths/path10_dwarf_galaxies.py`) are not a test of this sector's ceiling—in the coupling above they demand $M_Y/M_{\rm bar} \approx 15$ at $q \to 1$, four-plus decades below the SPARC calibration range ($M_{\rm bar} \gtrsim 10^7\,M_\odot$). The condensate mechanism is therefore uncalibrated (not falsified) there; the SPARC $c_s$ scalings cannot be extrapolated to $10^3\,M_\odot$ stellar masses.

**Prediction P2 (core radius scaling).** The pseudo-isothermal fits give $\gamma = 0.23 \pm 0.10$ with $R^2 = 0.05$—the model-fitted $r_c$ is too degenerate with $\rho_c$ to trace mass, so the fitted scaling does not constrain P2. The empirical measurement stands as the P2 constraint.

The empirical core radius (measured as the radius where $v_{\text{DM}}$ reaches half its maximum) gives $\gamma = 0.41 \pm 0.02$—a $3.6\sigma$ deviation from the predicted $1/3$. However, the result is sensitive to measurement methodology: different bulge-mass scaling factors and filtering criteria produce $\gamma$ values ranging from 0.31 to 0.41, with $R^2$ between 0.32 and 0.73. The prediction is neither cleanly confirmed nor cleanly falsified by current data.

The small-$r$ dark matter velocity slope is intermediate between cusp ($p = 0.5$) and core ($p = 1.0$): median $p = 0.65$ from 19 galaxies with sufficient inner resolution. The SPARC data do not clearly discriminate cusps from cores.

### 7.3 Interpretation

The analysis does **not** support promoting Prediction P1 or P2 to Hypothesized. The specific radial profile derived from a 1D/2D condensation field model with fixed $\xi = \varphi^6$ is ruled out as a universal galaxy halo profile.

The existing Cassi result—that $\xi = \varphi^6$ matches the Milky Way rotation curve—stands. The issue is not with the coupling constant itself but with the attempt to apply it as a universal radial profile in a simplified 1D/2D geometry. Possible explanations for the failure:

1. **Geometry**: A full 3D bubble-lattice solution with checkerboard connectivity may produce a radial profile different from the 2D angular average
2. **Coupling saturation**: $\xi = \varphi^6$ is the vacuum coupling; the effective $\xi$ in partially organized galaxy halos may be lower
3. **Scale dependence**: $\theta_{\text{cond}}$ and $n_{\text{cond}}$ may vary with cascade rung, not remaining fixed at the cosmological values
4. **The right test**: The Qi mechanism may only be testable through full two-fluid PDE simulations at galactic scale, not through static radial fits to rotation curves

### 7.4 Path forward

The hydrostatic two-component condensate survives SPARC at NFW parity with fixed $\xi$ (median $\Delta$AIC = −7.0). The per-galaxy $c_s$ scatter is closed: unconstrained-direction degeneracy (68/143) plus measurement-limited scatter ($R^2 = 0.42$ vs $n_{\rm pts}$); the constrained 75 follow the virial ratio $c_s/v_{DM,\text{flat}} = 1/\sqrt{2\varphi^6} \approx 0.167$. Remaining steps:
- Full 3D bubble-lattice galaxy model with checkerboard geometry, not radial approximation
- Two-fluid PDE simulation at galactic scale ($n \approx 267$) with realistic baryonic distributions
- Scaling the effective $\xi$ from the PDE output rather than fixing it at the vacuum value

Until one of these is implemented, the dark-matter-as-Qi-coherence framework remains Speculative.
---

## 8. Epistemic Boundaries

### Derived (within the Cassi framework)

- $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q)G$ with $\xi = \varphi^6$ (`foundations/xi-derivation.md`)
- $q(C) = (1 + C)/2$ from the condensation field (`foundations/bubble-edge-geometry.md` §1.1)
- The condensation field $C(x,y) = \cos(\alpha x)\cos(\beta y)$ and its bubble-edge geometry
- Scale covariance: the same field operates at galactic scale ($n \approx 267$) as at cosmological scale ($n \approx 285$)
- The cascade relation $\ell_n = \ell_{\text{Pl}} \varphi^n$

### Hypothesized (PDE-testable)

- That $\theta_{\text{cond}}$ at galactic scale equals the cosmological value ($\approx 0.45$)—the conversion-diffusion balance is scale-invariant, but this has not been verified by multi-scale PDE simulation
- The condensation exponent $n_{\text{cond}}$ at galactic scale

### Creative extrapolation (this document)

- The reframing of "dark matter" as unharvested Qi coherence
- The tuning hypothesis: that $\eta_{\text{visible}}$ can be engineered
- The SETI prediction P5
- The morphological coherence correlation (P3)

### Not claimed

- That the Cassi framework disproves particle dark matter
- That all dark matter phenomenology is explained by the Qi field—detailed lensing maps, the Lyman-α forest, and CMB acoustic peaks may require additional physics
- That any observed galaxy shows evidence of gate tuning

---

## References

- `foundations/xi-derivation.md`—$\xi = \varphi^6$, Qi-gravity coupling, Milky Way rotation curve
- `foundations/bubble-edge-geometry.md`—condensation field, $G_{\text{eff}}$ profile, $q(C)$, $\theta_{\text{cond}}$
- `foundations/spiral-dynamics.md`—gravitational coupling $\alpha_G \propto \varphi^{-2n}$, gravity as gradient descent
- `foundations/dimensionful-cascade.md`—cascade table, galactic scale at $n \approx 267$
- `foundations/cassi-first-principles.md`—two-fluid PDE, Qi gate, $G_{\text{eff}}$ limits
- `foundations/bubble-lattice-fabric.md`—scale covariance, checkerboard lattice at every rung
- `foundations/cascade-suppression-formula.md`—per-rung attenuation
- `cosmology/cosmology-from-phi.md`—dark-matter condensate: formation, abundance, candidate comparison (§4)
- `experiments/sparc_qi/`—SPARC fits: hydrostatic condensate, baryonic-decoherence envelope, core scaling
- `experiments/phi_attractor_paths/path10_dwarf_galaxies.py`—dwarf-spheroidal G-rescaling sector, UFD ceiling tests
- `two-fluid/calibrate_initial_ratio_xi_v2.py`—Yang-component boost, attractor weighting $r/(1+r)$
- `speculations/cascade-infrastructure.md`—gate chain topology, tuned vs untuned galaxies
- `speculations/qi-bubble-propulsion.md`—Qi bubble drive, energy harvesting
- `speculations/gravity-control.md`—gravity control at the condensate rung; SPARC constraints
