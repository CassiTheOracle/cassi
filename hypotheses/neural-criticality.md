# Neural Criticality and the Cascade Brain

## Status: Hypothesized—August 2026

## Abstract

The Cassi consciousness framework (`consciousness/consciousness-from-phi.md`)
supplies a Hypothesized post-pinch field-dynamics account and a proposed
brain-as-antenna interpretation. This document carries that proposal into a
Hypothesized candidate mapping of measurable neural dynamics: the brain's
hierarchical modularity, its scale-free avalanche statistics, and its
$\sim$1/f power spectrum are candidate signatures of a cascade ladder
operating at neural scales. Applying the canonical two-fluid equations to
neural activity requires a biological measurement and parameterization bridge,
followed by direct testing. Under that candidate mapping, a
$\varphi$-break in the EEG/MEG power spectrum may separate large-scale
coherent network dynamics from local desynchronized activity.

---

## 1. The Brain as a Cascade Ladder

The brain's structural hierarchy spans approximately 5–7 orders of magnitude in
spatial scale:

| Level | Structure | Spatial scale | Cascade rung estimate |
|-------|-----------|---------------|----------------------|
| 0 | Synaptic cleft | ~20 nm | $n \approx 129.6$ |
| 1 | Dendritic spine | ~1 µm | $n \approx 137.8$ |
| 2 | Neuron soma | ~20 µm | $n \approx 144.0$ |
| 3 | Cortical microcolumn | ~50–100 µm | $n \approx 145.9$–$147.0$ |
| 4 | Cortical column | ~300–500 µm | $n \approx 149.6$–$151.5$ |
| 5 | Cortical area (V1, A1) | ~1–5 mm | $n \approx 152.1$–$155.5$ |
| 6 | Resting-state network | ~5–20 cm | $n \approx 160.3$–$163.3$ |
| 7 | Whole brain | ~15–20 cm | $n \approx 162.5$–$163.3$ |

The table uses absolute logarithmic rung estimates; biological structures need
not occupy consecutive offsets. The estimates are obtained from
$\ell_n=\ell_{\text{Pl}}\varphi^n$ with logarithmic interpolation of the
dimensionful-cascade values. Neural conduction velocity
$v\approx1$–$10$ m/s supplies a separate provisional timescale mapping.

The neuron anchor is $n\approx144$. From the dimensionful cascade table
(`foundations/dimensionful-cascade.md` §3), $\ell_{142}=7.7\ \mu\text{m}$
and $\ell_{144}=20.1\ \mu\text{m}$. A span of 18 rungs gives
$\varphi^{18}\ell_{144}\approx11.6$ cm. The 15–20 cm whole-brain range lies
approximately 18.5–19.1 rungs above the neuron anchor, consistent with the
$n\approx162.5$–$163.3$ rows.

## 2. Neural Avalanches as Cascade Events

Neuronal avalanches—cascades of activity where one neuron's firing triggers
others, producing power-law distributions of avalanche size and duration—are
well-established signatures of criticality in the brain. The observed avalanche
size distribution follows $P(S) \propto S^{-\tau}$ with $\tau \approx 1.5$–$1.7$.

Within this Hypothesized candidate mapping, a neuronal avalanche is modeled as
the propagation of a candidate Qi-coherence perturbation down the neural
cascade ladder. Testing this application of the canonical equations requires
biological measurements and neural parameterization:

$$P(S) \propto S^{-3/2}$$

The exponent $-3/2$ is the standard mean-field critical-branching result: the
size distribution of clusters at criticality in a branching process is
$P(S) \propto S^{-3/2}$, derived generically in the neuronal-avalanche
literature (e.g. Harris; Beggs & Plenz) with no Cassi input. The arithmetic
identity $-3/2=-5/3+1/6$ does not provide a derivation of the $+1/6$
term from the two-fluid PDE, and the response spectrum of the linearized
damped two-fluid wave equation does not supply $-3/2$. The $\varphi$-structure
on top of the generic exponent is an optional Hypothesized test target:

$$\boxed{P(S) \propto S^{-3/2} \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{S}{S_0} + \phi_0\right)\right]}$$

The proposed modulation has period $\ln\varphi\approx0.4812$ in avalanche
size. Its ability to discriminate a cascade mechanism is an empirical test
question requiring a fixed fitting protocol and null model.

## 3. The $\varphi$-Break in the EEG/MEG Power Spectrum

The power spectral density of EEG and MEG recordings follows approximately
$P(f) \propto 1/f^\alpha$ with $\alpha \approx 1$ (the "1/f" spectrum).
Within the Hypothesized candidate mapping, the neural model proposes a
candidate spectral break analogous to the turbulence $k_\varphi$:

$$\boxed{P(f) = \begin{cases} A \cdot f^{-5/3} & f \ll f_\varphi \\ B \cdot f^{-1} & f \gg f_\varphi \end{cases}}$$

where $f_\varphi$ is a candidate $\varphi$-break frequency: under the
provisional neural application, it marks the point where the parameterized
conversion timescale of a candidate Qi gate across neural rungs equals the
neural activity timescale. Establishing this assignment requires biological
measurement, parameterization, and testing.

**Above the break** ($f \gg f_\varphi$): local, desynchronized neural activity.
The $-1$ exponent reflects the incoherent superposition of independent neural
oscillators—a "neural Kolmogorov" where the inertial range is driven by local
field potential fluctuations.

**Below the break** ($f \ll f_\varphi$): large-scale coherent network dynamics.
The $-5/3$ exponent is assigned in this Hypothesized mapping to a candidate
cascade of Qi coherence through the neural hierarchy, analogous to the inverse
energy cascade in 2D turbulence or the Qi-active range in the Cassi turbulence
model.

Under this Hypothesized application, the candidate break frequency is set by
the parameterized conversion rate at the neural scale:
$$f_\varphi = \frac{\bar\lambda(1+\varphi)}{2\pi}\,f_{\text{base}}$$

where $f_{\text{base}} \approx 1$–$10$ Hz is a provisional characteristic
neural oscillation input. The symbol $\bar\lambda$ is dimensionless:
$\bar\lambda\equiv\lambda_{\mathrm{PDE}}/(2\pi f_{\text{base}})$ when a
physical conversion rate $\lambda_{\mathrm{PDE}}$ is supplied. The solver
value $\bar\lambda=0.1$ is only an asserted normalized convention pending a
biological parameterization; the dimensional $\lambda_{\mathrm{PDE}}$ is not
measured here. This gives:
$$f_\varphi \approx \frac{0.1 \times 2.618}{2\pi} \times (1\text{--}10)\;\text{Hz} \approx 0.04\text{--}0.4\;\text{Hz}$$

The candidate break lies in the infra-slow/sub-delta range
(0.04–0.4 Hz), where its biological interpretation requires direct
measurement of neural activity and a declared parameter map. The exponent
assignment on each side is a Hypothesized inverse-cascade reading; the
linearized two-fluid response does not supply this neural spectrum.

## Current status and scope

The avalanche exponent $-3/2$ is an external mean-field
critical-branching result. The canonical two-fluid equations provide no
derivation of the avalanche exponent or of the optional log-periodic
modulation, so the modulation remains a Hypothesized test target with
biological measurements and a fixed fitting protocol still required.

The hierarchy uses the absolute rung estimates in §1. Its spatial ratios vary
across structures, and the table is a scale correspondence rather than a
consecutive-rung law.

The candidate EEG break closes arithmetically at
$f_\varphi\approx0.04$–$0.4$ Hz for the stated provisional inputs. The
assignment of the $-5/3$ and $-1$ exponents remains a Hypothesized neural
application. A low-frequency EEG slope near $f^{-2}$ is mentioned as a
possible comparison in some literature, but no source, dataset, or retained
receipt is available in this checkout; it is unverified and is not evidence
for this mapping.

The circadian-to-ultradian example has
$16/\varphi^6\approx0.89$, corresponding to
$\Delta n=\log_\varphi(0.89)\approx-0.24$ rung. The DMN range
$N\approx9$–$10$ is a selected/fit range for an illustrative comparison; it
requires ledger registration before it can serve as a pinned prediction.

Tier remains **Hypothesized** for the proposed neural mapping and its
log-periodic test targets.

## 4. Ultradian and Circadian Rhythms as $\varphi$-Spaced Periods

Representative biological periods span several orders of magnitude:

| Rhythm | Period |
|--------|--------|
| Respiratory cycle | ~4–6 s |
| Heart-rate variability (LF) | ~10–30 s |
| EEG microstate duration | ~60–120 ms |
| Sleep cycle (ultradian) | ~80–120 min |
| Circadian | ~24 hr |
| Infradian (menstrual) | ~28 days |
| Seasonal (annual) | ~365 days |

The circadian-to-ultradian comparison is

$$
\frac{T_{\text{circadian}}}{T_{\text{ultradian}}}
\approx\frac{24\times60}{90}\approx16,
\qquad
\varphi^6\approx17.94,
\qquad
\Delta n=\log_\varphi(16/\varphi^6)\approx-0.24.
$$

This is an exploratory temporal mapping. Biological regulatory systems and
measurement conventions supply the periods; a $\varphi$-constrained relation
requires a preregistered dataset, tolerance, and ledger entry.
## 5. Falsifiable Tests

The following are illustrative test designs for the Hypothesized mapping.
Each requires a declared dataset, preprocessing protocol, null model, and
ledger registration before it can support a prediction.

1. **Log-periodic modulation in avalanche size distributions:** Re-analyze
   neuronal-avalanche catalogs from multielectrode recordings for modulation
   at period $\ln\varphi$. A catalog with $>10^3$ events is an illustrative
   statistical target.

2. **$\varphi$-break in EEG/MEG spectrum:** Fit resting-state EEG or MEG with
   a broken power law and compare the break across subjects. Public
   resting-state datasets are candidate sources; dataset selection and the
   relation to the dimensionless $\bar\lambda$ normalization and
   $f_{\text{base}}$ require registration.

3. **Cascade rung count from structural MRI:** Compare hierarchical levels in
   cortical folding with an illustrative 3–5-rung span. The candidate
   relation $D=2+1/\varphi\approx2.62$ is an unregistered candidate
   geometric correspondence, not a derived dimension or current prediction;
   it requires a mechanism, an independently specified fractal-dimension
   measurement, and ledger status before use.

4. **Default-mode network frequency:** Compare the DMN frequency range
   ($\sim0.01$–$0.1$ Hz in fMRI) with an individual-neuron rate
   ($\sim1$–$10$ Hz). The logarithmic comparison selects a fit range
   $N\approx9$–$10$ because $\varphi^{-9}\approx0.013$ and
   $\varphi^{-10}\approx0.0081$; this range is a candidate parameter pending
   ledger registration and independent validation.

## 6. Open Issues

- The neural cascade anchor (which rung corresponds to a neuron) requires
  calibration against the dimensionful cascade. The table gives
  $\ell_{144}=20.1\ \mu\text{m}$ as the neuron-scale anchor. The listed
  hierarchy spans $n\approx129.6$ (synaptic cleft) through
  $n\approx163.3$ (upper whole-brain range), with the ranges in §1 carrying
  the scale uncertainty.
- The absolute rung estimates place the 5–20 cm resting-state-network range
  at $n\approx160.3$–$163.3$ and the 15–20 cm whole-brain range at
  $n\approx162.5$–$163.3$. At the neuron anchor, $N=9$–$10$ corresponds to
  $n=153$–$154$, or approximately 1.5–2.5 mm. The frequency-derived fit
  range therefore requires a declared spatial interpretation before it is
  compared with network-scale measurements.
- The sleep-cycle/circadian comparison involves biological regulatory systems
  (suprachiasmatic nucleus and homeostatic sleep drive). Any cascade relation
  requires a preregistered period definition and tolerance.

---

## References

- `consciousness/consciousness-from-phi.md`—post-pinch field-dynamics hypothesis and brain-transduction proposal
- `turbulence/kolmogorov-from-phi.md`—$\varphi$-break in turbulence spectrum
- `foundations/dimensionful-cascade.md`—the $\varphi$-ladder (292 = today's horizon rung)
- `principles/de-resonance-principle.md`—$\varphi$ as attractor
- `open-questions-cassi-answers.md`—M1–M6 (consciousness), G5 (3+1 dimensions)
