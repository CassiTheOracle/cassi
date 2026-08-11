# Exoplanet Orbital Spacing from the Wake-Wave Mechanism

## Status: Hypothesized—July 2026

## Abstract

The Titius-Bode "law" for solar system planetary spacing ($a \propto 1.7^n$) uses
a progression factor tantalizingly close to $\varphi \approx 1.618$. In the Cassi
framework, this is not a coincidence—it is the same wake-wave interference
mechanism that produces $\varphi$-periodic structure in the cosmic web
(`open-questions-cassi-answers.md`—C9) and log-periodic modulation in the
matter power spectrum (`predictions/falsifiable-predictions.md` §3). In a
protoplanetary disk, the Yang-Yin conversion produces $\varphi$-spaced density
nodes where planetesimals preferentially condense. This predicts a statistical
excess of adjacent-planet period ratios at $\varphi$ and its Fibonacci
convergents in the Kepler/TESS multi-planet catalog—a zero-parameter,
falsifiable test using existing data.

## Origin Status

**Verdict: catalog correspondence; mechanism open.** Recomputation
(`computations/verify_hypotheses_origin_audit.py`, 2026-08-11) confirms:

- **Mechanism.** The wake-wave $\to$ $\varphi$-spaced density nodes $\to$
  planetesimal condensation chain is asserted, not derived: no two-fluid-PDE
  calculation of a protoplanetary disk exists, and the cosmic-web wake-wave
  (open-questions C9) is itself a framework hypothesis. Mean-motion resonances
  are real, and 3:2 = 1.5, 5:3 = 1.667, 8:5 = 1.6 are Fibonacci convergents —
  but their ubiquity is standard celestial mechanics (resonance trapping
  during migration), which does not single out Fibonacci convergents over
  other low-order ratios such as 4:3.
- **The period-ratio prediction** $P_{\text{out}}/P_{\text{in}} =
  \varphi^{3/2} \approx 2.06$ (verified) is a legitimate zero-parameter
  statistical test on the Kepler/TESS catalog; it has not been run here.
- **Solar-system fit.** The geometric mean of the doc's own six adjacent-planet
  ratios is 1.66, not 1.73 (§1 corrected); the set is dominated by the 3.42
  Mars/Jupiter jump. The $\varphi$-fit's mean $|\ln a|$ deviation is 0.193 as
  slotted and 0.088 after a post-hoc remap, vs Titius-Bode's 0.084 — comparable
  at best, not better (§4 corrected).

Tier stays **Hypothesized**: the statistical prediction is pinned and
falsifiable; the mechanism step (disk wake-wave $\to$ $\varphi$-spacing) is
open.

---

## 1. The Titius-Bode "Law"

The empirical Titius-Bode relation for solar system semi-major axes:
$$a_n = 0.4 + 0.3 \times 2^n \quad \text{(AU, for $n = -\infty, 0, 1, 2, \ldots$)}$$

The progression factor is 2, but the actual mean spacing ratio of adjacent
planets in our solar system varies: Venus/Earth = 0.723, Earth/Mars = 1.52,
Mars/Jupiter = 3.42 (the asteroid belt occupies this gap), Jupiter/Saturn =
1.83, Saturn/Uranus = 1.97, Uranus/Neptune = 1.56. The geometric mean of these
six ratios is 1.66 (recomputed), within 3% of $\varphi$ — but the set is
dominated by the single 3.42 Mars/Jupiter jump, and the ratio convention
(inner/outer vs outer/inner, Mercury included or not) moves the mean between
1.66 and 1.75. One planetary system cannot select $\varphi$ over the
progression factor 2 that Titius-Bode already fits.

The standard interpretation is that orbital resonances (mean-motion resonances
at period ratios like 2:1, 3:2, 5:3) sculpt planetary spacing through
gravitational interactions. In Cassi, these resonances ARE the Fibonacci
convergents of $\varphi$—the de-resonance attractor in orbital frequency
space—and their ubiquity is a consequence of the disk's Qi field seeking
$\varphi$-equilibrium.

## 2. Wake-Wave in Protoplanetary Disks

The wake-wave mechanism (`open-questions-cassi-answers.md`—C9) produces
$\varphi$-spaced density nodes wherever the Yang and Yin fields interfere:
$$\rho_{\text{node}}(r) = \rho_0 \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{r}{r_0} + \phi_0\right)\right]$$

In a protoplanetary disk, the Yang field corresponds to the outward pressure
gradient and angular momentum transport; the Yin field corresponds to the inward
gravitational collapse. Their interference at the midplane produces radial
density enhancements at $\varphi$-spaced intervals in $\ln r$.

Planetesimal formation occurs preferentially at these nodes because (a) the
enhanced density promotes gravitational instability, and (b) the Qi coherence at
$\varphi$-resonant locations reduces disruptive tidal shear. The result: planets
form at $\varphi$-spaced orbital radii.

## 3. Key Prediction: Period Ratio Distribution

For multi-planet systems, the ratio of adjacent orbital periods should show a
statistical excess at $\varphi$ and its Fibonacci convergents:

$$\boxed{\frac{P_{\text{out}}}{P_{\text{in}}} = \left(\frac{a_{\text{out}}}{a_{\text{in}}}\right)^{3/2} \approx \varphi^{3/2} \approx 2.06}$$

The Fibonacci convergents of $\varphi$ correspond to mean-motion resonances:

| Convergent | Ratio | Resonance | Observed? |
|-----------|-------|-----------|-----------|
| $1/1$ | 1.000 | 1:1 (co-orbital) | Trojan asteroids, Janus-Epimetheus |
| $2/1$ | 2.000 | 2:1 | Common (e.g., TOI-216) |
| $3/2$ | 1.500 | 3:2 | Common (e.g., GJ 876) |
| $5/3$ | 1.667 | 5:3 | Observed in several systems |
| $8/5$ | 1.600 | 8:5 | Rare but present |
| $13/8$ | 1.625 |—| Near $\varphi$ |

The prediction is that these period ratios should be overrepresented in the
Kepler multi-planet catalog compared to random spacing, and the excess should
peak at period ratios corresponding to low-order Fibonacci convergents.

Mean-motion resonances are already known to be common. The Cassi
prediction is stronger: the specific resonances that are populated are exactly
the Fibonacci convergents of $\varphi$—not an arbitrary set of rational
ratios. Resonances like 4:3 (1.333), 5:2 (2.5), or 7:3 (2.333) that are NOT
Fibonacci convergents should be underrepresented relative to their Fibonacci
neighbors.

## 4. Solar System Fit

Our solar system's eight planets (treating the asteroid belt as a disrupted
planet at ~2.8 AU) should show a $\varphi$-spaced log-periodic fit:

$$\ln(a_n / \text{AU}) \approx \ln(a_0) + n \cdot \ln\varphi$$

With $a_0 = 0.4$ AU (Mercury): predicted $a_1 = 0.4 \times \varphi = 0.65$ AU
(Venus at 0.72), $a_2 = 0.4 \times \varphi^2 = 1.05$ AU (Earth at 1.00), $a_3
= 0.4 \times \varphi^3 = 1.70$ AU (Mars at 1.52), $a_4 = 0.4 \times \varphi^4 =
2.75$ AU (asteroid belt at 2.1–3.3), $a_5 = 0.4 \times \varphi^5 = 4.45$ AU
(Jupiter at 5.20—worst fit, 17% off), $a_6 = 0.4 \times \varphi^6 = 7.20$ AU
(Saturn at 9.54), $a_7 = 0.4 \times \varphi^7 = 11.6$ AU (Uranus at 19.2), $a_8
= 0.4 \times \varphi^8 \approx 18.8$ AU (Uranus fit here, Neptune at 30.1—worst
outer-planet fit).

The fit is rough—the solar system is one sample. Recomputed mean absolute
deviation in $\ln a$: 0.193 as slotted (Mercury→slot 0 through Neptune→slot 8,
with Saturn 34% off and slot 7 matching nothing), or 0.088 after a post-hoc
remap (Uranus→slot 8, Neptune→slot 9, slot 7 dropped). Titius-Bode's own mean
$|\ln a|$ deviation is 0.084 — so the $\varphi$-fit is comparable at best
after the remap and worse without it; it is not "better than" Titius-Bode,
and the remap is chosen after the fact.

## 5. Falsifiable Tests

1. **Kepler period ratio excess at $\varphi^{3/2}$:** The distribution of
   adjacent-planet period ratios from the Kepler multi-planet catalog should
   show a peak at $P_{\text{out}}/P_{\text{in}} \approx 2.06$. Testable with
   existing public data (NASA Exoplanet Archive).

2. **Resonance selectivity:** Fibonacci-convergent resonances (2:1, 3:2, 5:3,
   8:5) should be more common than non-Fibonacci resonances at similar period
   ratios. The 4:3 resonance (not a Fibonacci convergent) should be
   underrepresented after controlling for detection bias.

3. **Log-periodic $P(k)$ in disk structure:** If ALMA observations of
   protoplanetary disks can resolve radial substructure at sufficient dynamic
   range in radius, the ring/gap locations should show $\varphi$-periodicity in
   $\ln r$. The DSHARP survey of 20 bright disks already reveals concentric
   rings—re-analysis for $\varphi$-spacing is feasible.

4. **No period ratio at exactly $\varphi$ for single-disk systems:** The
   $\varphi$ spacing is an attractor, meaning any individual system may deviate
   due to migration and scattering. The prediction is statistical—an excess in
   a large sample, not an exact fit for each system.

## 6. Open Issues

- Planet migration (Type I and Type II) after formation smears the primordial
  $\varphi$-spacing. The observed period ratio distribution convolves formation
  spacing with migration and dynamical instability. Disentangling these requires
  a population synthesis model with $\varphi$-spaced initial conditions.
- The solar system's Jupiter (5.2 AU vs. predicted 4.45 AU) is the largest
  deviation. The Grand Tack hypothesis (Jupiter migrated inward to ~1.5 AU then
  back out) could explain this if the formation location was near the predicted
  node.
- The asteroid belt (2.1–3.3 AU) spans approximately one $\varphi$-factor in
  radius—consistent with a disrupted $\varphi$-node, but the disruption
  mechanism (Jupiter's resonance sweeping) must be shown to operate at the
  predicted location.

---

## References

- `open-questions-cassi-answers.md`—C9 (cosmic web from wake-wave), G5 (3+1 dimensions)
- `predictions/falsifiable-predictions.md`—$\varphi$-periodic $P(k)$ prediction
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `foundations/bubble-edge-geometry.md`—condensation field $C(x,y)$ structure (same wake-wave mechanism)
- `principles/de-resonance-principle.md`—why orbital resonances lock to $\varphi$
