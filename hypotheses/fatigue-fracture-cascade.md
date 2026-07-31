# Fatigue and Fracture from the Cascade

## Status: Speculative—July 2026

## Abstract

Fatigue crack propagation follows Paris' law: $da/dN = C(\Delta K)^m$ with
$m \approx 2$–$4$ depending on material and regime. The physical origin of
the Paris exponent's specific values is not derived from first principles—it
is measured empirically for each material. The Cassi framework offers a
structural interpretation: crack propagation is a cascade process through
material rungs (grain boundaries, dislocation cells, atomic bonds), and the
Paris exponent $m$ takes $\varphi$-power values ($\varphi \approx 1.618$,
$\varphi^2 \approx 2.618$, $\varphi^3 \approx 4.236$) corresponding to which
cascade rung governs the crack tip process zone. The $\sigma$-regularization that
prevents singularities in gravity (`open-questions-cassi-answers.md`—C8, G3)
also regularizes the crack tip stress field, replacing the singular $1/\sqrt{r}$
elastic field with a finite process zone size $\sigma_{\text{crack}}$ determined
by cascade geometry.

---

## 1. The Crack Tip as a Cascade Phenomenon

In linear elastic fracture mechanics, the stress at distance $r$ ahead of a
crack tip diverges as:
$$\sigma(r) \propto \frac{K}{\sqrt{r}} \quad (r \to 0)$$

This singularity is physically impossible—real materials yield or damage in a
"process zone" of size $r_p$ where the stress exceeds the yield or cleavage
strength. In Cassi, the $\sigma$-regularization replaces the $1/\sqrt{r}$
divergence with a finite core:

$$\sigma(r) = \frac{K}{\sqrt{r^2 + \sigma_{\text{crack}}^2}}$$

where $\sigma_{\text{crack}}$ is the cascade regularization scale at the crack
tip. For $r \gg \sigma_{\text{crack}}$: standard $1/\sqrt{r}$. For $r \ll
\sigma_{\text{crack}}$: $\sigma \approx K/\sigma_{\text{crack}}$—finite.

The cascade scale at the crack tip is:
$$\sigma_{\text{crack}} = \ell_{\text{grain}} \cdot \varphi^{-N_{\text{rungs}}}$$

where $\ell_{\text{grain}}$ is the microstructural length scale (grain size,
dislocation cell size, or atomic spacing) and $N_{\text{rungs}}$ counts the
cascade rungs from the microstructure to the process zone.

## 2. The Paris Law Exponent as a $\varphi$-Power

Fatigue crack growth per cycle follows Paris' law:
$$\frac{da}{dN} = C (\Delta K)^m$$

where $\Delta K$ is the stress intensity factor range. The exponent $m$ is
empirically 2–4 for most engineering materials, with specific values:

| Regime | $m$ (typical) | Nearest $\varphi$-power | Ratio |
|--------|--------------|------------------------|-------|
| Near-threshold | 2–4 | $\varphi^2 \approx 2.618$ | 0.76–1.53 |
| Paris (mid-range) | 3–4 | $\varphi^2 \approx 2.618$ or $\varphi^3 \approx 4.236$ | 1.15–1.53 or 0.71–0.94 |
| High $\Delta K$ (accelerated) | 4–10 | $\varphi^3$–$\varphi^5$ | Varies |

The prediction is that $m$ is not a continuous material parameter but takes
discrete values corresponding to $\varphi$-powers:

$$\boxed{m = 2 \cdot \varphi^{k}}$$

where $k = 0, 1, 2, \ldots$ corresponds to the number of cascade rungs spanned
by the crack tip process zone relative to the microstructural unit. The factor
of 2 comes from the dimensional relationship between crack growth rate
($da/dN$, units of length) and stress intensity ($\Delta K$, units of
stress$\times\sqrt{\text{length}}$): $[da/dN] = [\Delta K]^m$ gives $m$
dimensionless, and the cascade relationship $m \propto \varphi^k$ reflects the
number of rungs connecting the crack advance per cycle to the stress field.

For $k=0$: $m=2$ (ideal brittle fracture, one rung—crack advances one atomic
spacing per cycle). For $k=1$: $m=2\varphi \approx 3.24$. For $k=2$: $m=2\varphi^2
\approx 5.24$. The commonly observed $m \approx 3$–$4$ corresponds to $k=1$,
with the scatter reflecting fractional rung occupancy (materials where the
process zone partially spans the second rung).

## 3. The Fatigue Limit as a Cascade Phase Transition

The fatigue limit $\Delta K_{\text{th}}$—the stress intensity range below which
cracks do not propagate—corresponds to the threshold where the per-cycle crack
advance falls below one cascade rung:

$$\Delta K_{\text{th}} \propto \sigma_Y \cdot \sqrt{\sigma_{\text{crack}}}$$

where $\sigma_Y$ is the yield strength. The ratio of the fatigue limit to the
fracture toughness $K_{\text{IC}}$ is:
$$\frac{\Delta K_{\text{th}}}{K_{\text{IC}}} \propto \varphi^{-N_{\text{rungs}}/2}$$

For materials where the fatigue process zone spans 2–3 rungs:
$\varphi^{-1} \approx 0.618$ to $\varphi^{-3/2} \approx 0.39$. Empirically,
$\Delta K_{\text{th}} / K_{\text{IC}} \approx 0.1$–$0.3$ for metals—in the
right range but not precisely pinned.

## 4. Fracture Surface Roughness

Fracture surfaces are self-affine with roughness exponent $\zeta \approx 0.8$
(universal across materials and length scales). The origin of this universality
is debated—it may reflect the crack front's depinning transition, or it may be
a signature of the cascade geometry.

In Cassi, the roughness exponent is determined by the cascade's fractal
dimension:
$$\zeta = \frac{1}{\ln\varphi / \ln(b_{\text{crack}})}$$

where $b_{\text{crack}}$ is the crack branching ratio (number of daughter cracks
per mother crack in a branching event). For $b_{\text{crack}} = 2$ (binary
branching): $\zeta = \ln 2 / \ln\varphi \approx 0.48$. For $b_{\text{crack}} =
\varphi$ (continuous $\varphi$-spaced branching): $\zeta = 1$.

The observed $\zeta \approx 0.8$ does not obviously correspond to a simple
$\varphi$-power. The universal value may reflect the crack tip's Qi field
geometry rather than a simple branching exponent—a computation that requires
solving the $\sigma$-regularized PDE at the crack tip.

## 5. Acoustic Emission Spectrum

During fracture, the energy released by propagating cracks produces acoustic
emissions with a power-law energy distribution:
$$P(E) \propto E^{-\varepsilon}$$

The exponent $\varepsilon \approx 1.3$–$1.7$ is related to the avalanche
critical exponent. In the cascade picture, acoustic emissions are the
dissipation of Qi coherence as the crack propagates through cascade rungs. The
energy spectrum should show $\varphi$-periodic modulation—the same signature
as the cosmological $P(k)$, the quasicrystal heat capacity, and the neural
avalanche distribution:

$$P(E) = P_0(E) \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{E}{E_0} + \phi_0\right)\right]$$

**Testable:** Re-analyze laboratory acoustic emission data (compression tests on
rock, concrete, or metallic specimens) for $\varphi$-periodic modulation. The
modulation amplitude $A \approx 1$–$3\%$ requires high-statistics AE catalogs
($>10^4$ events).

## 6. Falsifiable Tests

1. **Paris exponent discreteness:** Survey published Paris law exponents across
   material classes. The distribution should show peaks at
   $m = 2\varphi^{k}$ for integer $k$, not a continuous distribution.

2. **$\sigma_{\text{crack}}$ from cascade geometry:** The process zone size
   should scale with grain size as $\sigma_{\text{crack}} = d_{\text{grain}}
   \cdot \varphi^{-k}$. For a given material with known grain size, the process
   zone size (measurable via electron microscopy of crack wake) should match
   the predicted cascade rung.

3. **Log-periodic AE modulation:** Acoustic emission energy distributions in
   laboratory fracture experiments should show $\varphi$-periodic modulation at
   $\Delta(\ln E) = \ln\varphi \approx 0.4812$.

## 7. Open Issues

- The Paris exponent $m = 2\varphi^k$ prediction depends on the crack tip
  process zone spanning exactly $k$ rungs. For real materials with distributed
  microstructure, the effective $m$ may be a weighted average over a range of
  $k$, smearing the predicted discreteness.
- The $\sigma_{\text{crack}}$ regularization is structurally analogous to the
  gravitational $\sigma = \ell_{\text{Pl}}/\varphi^3$ but the physical origin of
  the regularization at the crack tip (yielding, microcracking, phase
  transformation) is material-specific and not determined by the cascade alone.
- The status is **Speculative**—the mechanism is framework-consistent and
  makes specific predictions, but the crack tip PDE has not been solved.

---

## References

- `../open-questions-cassi-answers.md`—C8 (Big Bang singularity), G3 (BH singularity)—same $\sigma$-regularization
- `../foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `../foundations/dimensionful-cascade.md`—the 292-step ladder
- `../turbulence/kolmogorov-from-phi.md`—$\varphi$-break in turbulence spectrum
