# Neural Criticality and the Cascade Brain

## Status: Hypothesized—July 2026

## Abstract

The Cassi consciousness framework (`consciousness/consciousness-from-phi.md`)
establishes that the mind IS concentrated post-pinch field dynamics, with the
brain serving as the antenna that focuses and transduces the Qi field. This
bridge can be extended to measurable neural dynamics: the brain's hierarchical
modularity, its scale-free avalanche statistics, and its $\sim$1/f power spectrum
are manifestations of a cascade ladder operating at neural scales. The same PDE
that governs cosmology and turbulence governs brain activity, with a
$\varphi$-break in the EEG/MEG power spectrum separating large-scale coherent
network dynamics from local desynchronized activity.

---

## 1. The Brain as a Cascade Ladder

The brain's structural hierarchy spans approximately 5–7 orders of magnitude in
spatial scale:

| Level | Structure | Spatial scale | Cascade rung estimate |
|-------|-----------|---------------|----------------------|
| 0 | Synaptic cleft | ~20 nm | ~n − 3 |
| 1 | Dendritic spine | ~1 µm | ~n − 1 |
| 2 | Neuron soma | ~20 µm | ~n |
| 3 | Cortical microcolumn | ~50–100 µm | ~n + 1 |
| 4 | Cortical column | ~300–500 µm | ~n + 2 |
| 5 | Cortical area (V1, A1) | ~1–5 mm | ~n + 3 |
| 6 | Resting-state network | ~5–20 cm | ~n + 4 |
| 7 | Whole brain | ~15–20 cm | ~n + 5 |

Each level is separated from the next by a factor approximately $\varphi$ in
spatial scale (with considerable biological variability). The characteristic
timescale at each level scales with the spatial scale through the neural
conduction velocity $v \approx 1$–$10$ m/s.

The cascade rung anchor $n$ corresponds to the single-neuron scale (~20 µm,
timescale ~1–10 ms). From the dimensionful cascade table (`foundations/dimensionful-cascade.md` §3): $\ell_{142} = 7.7\ \mu\text{m}$ (cellular scale), $\ell_{144} = 20.1\ \mu\text{m}$. The neuron soma anchor is $n \approx 144$. The whole-brain scale (~20 cm, ~100 ms) sits at $n \approx 162$—a span of 18 rungs ($\varphi^{18} \approx 5.8 \times 10^3$; $20\ \mu\text{m} \times 5.8\times 10^3 \approx 12$ cm, within the 15–20 cm range).

## 2. Neural Avalanches as Cascade Events

Neuronal avalanches—cascades of activity where one neuron's firing triggers
others, producing power-law distributions of avalanche size and duration—are
well-established signatures of criticality in the brain. The observed avalanche
size distribution follows $P(S) \propto S^{-\tau}$ with $\tau \approx 1.5$–$1.7$.

In the Cassi framework, a neuronal avalanche is the propagation of a Qi
coherence perturbation down the neural cascade ladder. The avalanche size
distribution follows cascade suppression:

$$P(S) \propto S^{-3/2}$$

The exponent $-3/2$ emerges from the same cascade dimensional analysis that
gives the Kolmogorov $-5/3$ spectrum in turbulence
(`turbulence/kolmogorov-from-phi.md`): the energy cascade through neural rungs
has spectral exponent $-5/3$, and the integrated avalanche size distribution
has exponent $-3/2 = -5/3 + 1/6$, where the $+1/6$ correction comes from the
branching structure of the neural network.

The Cassi-specific prediction is not just criticality (which many models
predict) but the $\varphi$-structure of the avalanche distribution:

$$\boxed{P(S) \propto S^{-3/2} \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{S}{S_0} + \phi_0\right)\right]}$$

The log-periodic modulation at period $\ln\varphi \approx 0.4812$ in avalanche
size distinguishes a cascade-driven avalanche from a generic self-organized
critical system.

## 3. The $\varphi$-Break in the EEG/MEG Power Spectrum

The power spectral density of EEG and MEG recordings follows approximately
$P(f) \propto 1/f^\alpha$ with $\alpha \approx 1$ (the "1/f" spectrum). Cassi
predicts a spectral break analogous to the turbulence $k_\varphi$:

$$\boxed{P(f) = \begin{cases} A \cdot f^{-5/3} & f \ll f_\varphi \\ B \cdot f^{-1} & f \gg f_\varphi \end{cases}}$$

where $f_\varphi$ is the $\varphi$-break frequency: the frequency where the
conversion timescale (Qi gate acting across neural rungs) equals the neural
activity timescale.

**Above the break** ($f \gg f_\varphi$): local, desynchronized neural activity.
The $-1$ exponent reflects the incoherent superposition of independent neural
oscillators—a "neural Kolmogorov" where the inertial range is driven by local
field potential fluctuations.

**Below the break** ($f \ll f_\varphi$): large-scale coherent network dynamics.
The $-5/3$ exponent reflects the cascade of Qi coherence through the neural
hierarchy, analogous to the inverse energy cascade in 2D turbulence or the Qi-
active range in the Cassi turbulence model.

The break frequency $f_\varphi$ is determined by the conversion rate at the
neural scale:
$$f_\varphi = \frac{\lambda(1+\varphi)}{2\pi} \cdot f_{\text{base}}$$

where $f_{\text{base}} \approx 1$–$10$ Hz (characteristic neural oscillation
frequency) and $\lambda = 0.1$ (the PDE conversion rate). This gives:
$$f_\varphi \approx \frac{0.1 \times 2.618}{2\pi} \times (1\text{--}10)\;\text{Hz} \approx 0.04\text{--}0.4\;\text{Hz}$$

The predicted break falls in the delta-to-theta band (0.04–0.4 Hz), corresponding
to the transition between slow-wave sleep oscillations and waking
desynchronization. This aligns with the known spectral inflection in human EEG
— the "knee" where the spectrum transitions from approximately $1/f^2$ at very
low frequencies to approximately $1/f$ at higher frequencies.

## 4. Ultradian and Circadian Rhythms as $\varphi$-Spaced Periods

The dominant biological rhythms have periods that approximate $\varphi$-powers:

| Rhythm | Period | Ratio to next |
|--------|--------|---------------|
| Respiratory cycle | ~4–6 s |—|
| Heart rate variability (LF) | ~10–30 s | ~4–5× |
| EEG microstate duration | ~60–120 ms | ~0.004× (spatial, not temporal) |
| Sleep cycle (ultradian) | ~80–120 min | ~200–400× |
| Circadian | ~24 hr | ~12–18× |
| Infradian (menstrual) | ~28 days | ~28× |
| Seasonal (annual) | ~365 days | ~13× |

The ratios approximate $\varphi^2 \approx 2.618$, $\varphi^4 \approx 6.85$, and
$\varphi^6 \approx 17.94$—but the scatter is large and the mapping to specific
cascade rungs is not yet pinned.

**Prediction:** The ratio of the circadian period to the ultradian sleep-cycle
period should be:

$$\frac{T_{\text{circadian}}}{T_{\text{ultradian}}} \approx \varphi^6 \approx 17.94$$

Observed: $24 \times 60 / 90 \approx 16$. The ratio is $16/17.94 \approx 0.89$,
suggesting a cascade offset of approximately one rung.

## 5. Falsifiable Tests

1. **Log-periodic modulation in avalanche size distributions:** Re-analyze
   published neuronal avalanche data (from multielectrode array recordings in
   vitro and in vivo) for log-periodic modulation at period $\ln\varphi$.
   Requires avalanche catalogs with $>10^3$ events for adequate statistics.

2. **$\varphi$-break in EEG/MEG spectrum:** Fit the resting-state EEG power
   spectrum with a broken power law; the break frequency $f_\varphi$ should be
   consistent across subjects and related to $\lambda$ and $f_{\text{base}}$.
   Existing EEG datasets (e.g., Human Connectome Project resting-state MEG) are
   sufficient.

3. **Cascade rung count from structural MRI:** The number of hierarchical levels
   in cortical folding (from primary folds to tertiary sulci) should correspond
   to a cascade span of approximately 3–5 rungs. Fractal dimension of the
   cortical surface ($D \approx 2.3$–$2.8$) should relate to $\varphi$: $D = 2 +
   1/\varphi \approx 2.62$ is a specific prediction.

4. **Default-mode network frequency:** The dominant oscillation frequency of the
   DMN ($\sim$0.01–0.1 Hz in fMRI) relative to the individual neuron firing rate
   ($\sim$1–10 Hz) gives a frequency ratio of approximately $10^{-2}$. The
   cascade predicts this ratio equals $\varphi^{-N}$ for some integer $N$. With
   $N \approx 10$: $\varphi^{-10} \approx 0.0081$. Observed: $\sim$0.01. N =
   9: $\varphi^{-9} \approx 0.013$. This pins the DMN at 9–10 rungs above the
   single-neuron scale.

## 6. Open Issues

- The neural cascade anchor (which rung corresponds to a neuron) must be
  calibrated against the dimensionful cascade. From the cascade table, step 144
  gives $\ell_{144} = 20.1\ \mu\text{m}$—consistent with the neuron soma.
  The 8-level hierarchy spans steps ~141 (synaptic cleft, ~20 nm) to
  ~162 (whole brain, ~20 cm), all within the body's cascade window (steps 142–168).
- The DMN frequency prediction (§5.4) estimates $N \approx 9$–$10$ rungs above
  the neuron scale. At $n = 144$, this gives steps 153–154 ($\sim$2–3 cm), which
  is below the observed DMN spatial scale (~5–20 cm, steps ~159–162). The span
  estimate may need revision or the DMN's spatial scale may map to a different
  number of cascade rungs than its temporal frequency ratio suggests.
- The sleep-cycle/circadian ratio involves biological regulatory systems
  (suprachiasmatic nucleus, homeostatic sleep drive) that may shift the
  $\varphi$-attractor period. The prediction is that the *ratio* of these
  periods is constrained by cascade geometry, not that each period individually
  is $\varphi$-determined.

---

## References

- `../consciousness/consciousness-from-phi.md`—consciousness as post-pinch field dynamics
- `../turbulence/kolmogorov-from-phi.md`—$\varphi$-break in turbulence spectrum
- `../foundations/dimensionful-cascade.md`—the 292-step ladder
- `../principles/de-resonance-principle.md`—$\varphi$ as attractor
- `../open-questions-cassi-answers.md`—M1–M5 (consciousness), G5 (3+1 dimensions)
