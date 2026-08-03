# Hypotheses—New Application Domains for the Cassi Framework

## Status: Exploratory catalog—July 2026

## Abstract

This directory catalogs new physical domains where the Cassi framework—the
two-fluid PDE, the $\varphi$ cascade ladder, the de-resonance principle, and the
coherence budget—may produce novel, testable predictions beyond the 41 open
questions already addressed in `../open-questions-cassi-answers.md`. Each document
identifies a specific Cassi mechanism, sketches a derivation path, and proposes
one or more falsifiable tests.

**Quality bar:** A hypothesis earns a place here only if (1) the proposed Cassi
mechanism extends existing derived machinery rather than inventing new structure,
and (2) it makes at least one zero-parameter or low-parameter prediction
distinguishable from the null hypothesis. $\varphi$ appearing somewhere in the
domain is not enough—the contribution must be what Cassi *uniquely* adds.

---

## Document Index

| # | Domain | Epistemic | Bridge | Document |
|---|--------|-----------|--------|----------|
| 1 | Nuclear magic numbers | Hypothesized | Fibonacci sub-channel closure in cascade steps 80–95 | `nuclear-magic-numbers.md` |
| 2 | Hoyle state / stellar nucleosynthesis | Hypothesized | Cascade rung resonance at $^3\alpha$ threshold | `hoyle-state-nucleosynthesis.md` |
| 3 | Quasicrystal stability | Hypothesized (near-Derived) | De-resonance + cascade suppression against crystallization | `quasicrystal-stability.md` |
| 4 | Exoplanet $\varphi$-spacing | Hypothesized | Wake-wave interference in protoplanetary disks | `exoplanet-phi-spacing.md` |
| 5 | Neural criticality / cascade brain | Hypothesized | Cascade PDE operating at neural scales | `neural-criticality.md` |
| 6 | Atomic shell structure / Madelung rule | Speculative | $n$ and $l$ as cascade coordinates | `periodic-table-madelung.md` |
| 7 | Atmospheric climate cascade | Speculative | $\varphi$-break in atmospheric energy spectrum | `atmospheric-climate-cascade.md` |
| 8 | Fatigue & fracture mechanics | Speculative | $\sigma$-regularized crack tip, $\varphi$-power Paris law | `fatigue-fracture-cascade.md` |
| 9 | Market cascade cycles | Speculative | Wake-wave in information propagation networks | `market-cascade-cycles.md` |
| 10 | Metabolic allometry | Speculative (open problem) | $\varphi$-derived fractal dimension for resource networks | `metabolic-scaling.md` |
| 11 | Muscle structural hierarchy | Hypothesized | Bubble-lattice ladder at biological rungs (142–168) maps the filament→belly ladder to consecutive cascade rungs | `muscle-cascade-lattice.md` |
| 12 | Riemann hypothesis | Speculative | De-resonance: RH as the absence of resonance in primes; φ-periodicity null test on ζ zeros | `riemann-hypothesis-de-resonance.md` |
| 13 | Two-fluid Hilbert–Pólya program | Speculative | Scale-operator candidate for the zeros; minimal-fluctuation probes (Selberg, Gram) | `riemann-two-fluid-spectral-program.md` |

---

## Document Summaries

Summaries follow the Document Index order (tier-grouped: Hypothesized first,
then Speculative, with the muscle hypothesis appended last).

### `nuclear-magic-numbers.md`—Nuclear Magic Numbers from the Cascade Ladder

Proposes that the shell-model magic numbers 2, 8, 20, 28, 50, 82, 126 are
Fibonacci sub-channel closures over the cascade span from QCD confinement
(step 95) down to nuclear binding (steps ~80–90): SO(2) doublet winding assigns
angular momentum to each sub-channel, giving capacity $\Omega_j = 2j + 1$, and
the cumulative closure count reproduces the magic sequence without a fitted
spin-orbit parameter. The pinned prediction is that level spacing within a
shell follows $\boxed{\Delta E_{j \to j+1} \propto \varphi^{-j} \cdot \Lambda_{\text{QCD}}}$,
a $\varphi$-power falloff in the sub-channel angular momentum $j$.
**Epistemic tier: Hypothesized.**

### `hoyle-state-nucleosynthesis.md`—The Hoyle State as a Cascade Rung Resonance

Reinterprets the 7.65 MeV Hoyle state as structural rather than anthropic: it
sits one cascade rung above the $^3\alpha$ threshold (7.27 MeV), with the
0.38 MeV gap identified as a Fibonacci sub-channel splitting at nuclear rungs
~82–88. The key prediction generalizes the Hoyle anchor to all $\alpha$-cluster
nuclei—excitation spacing
$\boxed{E_{\text{exc}}(N_\alpha + 1) - E_{\text{exc}}(N_\alpha) \propto \varphi^{-N_\alpha} \cdot \Lambda_{\text{QCD}}}$—
with concrete numbers for $^{16}$O (6.05 MeV), $^{20}$Ne (5.79 MeV), and
$^{24}$Mg (6.43 MeV), and consequences for the $^{16}$O$(\alpha,\gamma)^{20}$Ne
bottleneck in stellar helium burning. **Epistemic tier: Hypothesized.**

### `quasicrystal-stability.md`—Quasicrystal Stability from De-Resonance

Derives quasicrystal stability from the de-resonance principle: at
condensed-matter scales (cascade steps ~120–150) the Qi field forms
$\varphi$-spaced density waves, and crystallization requires detuning from that
attractor at a cascade-suppression cost—so aperiodic $\varphi$-modular order can
win. The 5D→3D projection of standard theory is read as the cascade dimension
count $D = 2 + 2 + 1 = 5$. Pinned predictions include the stabilization energy
$\boxed{\Delta E_{\text{QC} \to \text{crystal}} \propto N_{\text{unit}} \cdot \varphi^{-N_{\text{rungs}}}}$,
a critical cooling-rate ratio $\dot{T}_{\text{crit}}^{\text{QC}}/\dot{T}_{\text{crit}}^{\text{crystal}} = \varphi^{-N_{\text{rungs}}}$
with $N_{\text{rungs}} = 3$–$5$, and 1–3% $\varphi$-periodic modulation of
low-temperature heat capacity at period $\ln\varphi$—testable on existing
Al-Pd-Mn and Al-Cu-Fe data. **Epistemic tier: Hypothesized (near-Derived).**

### `exoplanet-phi-spacing.md`—Exoplanet Orbital Spacing from the Wake-Wave Mechanism

Applies the wake-wave mechanism of the cosmic web (open-questions entry C9) to
protoplanetary disks: Yang-Yin interference produces $\varphi$-spaced density
nodes at which planetesimals preferentially condense, making Titius-Bode's
~1.7 progression factor and the observed mean-motion resonances the de-resonance
attractor and its Fibonacci convergents. The pinned, zero-parameter prediction
is a statistical excess of adjacent-planet period ratios at
$\boxed{\frac{P_{\text{out}}}{P_{\text{in}}} \approx \varphi^{3/2} \approx 2.06}$
in the Kepler/TESS multi-planet catalog. **Epistemic tier: Hypothesized.**

### `neural-criticality.md`—Neural Criticality and the Cascade Brain

Extends the consciousness framework to measurable neural dynamics: the brain's
hierarchical modularity, avalanche statistics, and ~1/f spectrum are a cascade
ladder at neural scales, anchored at the neuron soma ($n \approx 144$) and
spanning 18 rungs to the whole brain ($n \approx 162$, $\varphi^{18} \approx 5.8
\times 10^3$), governed by the same PDE as cosmology. The pinned predictions are
the avalanche size distribution
$\boxed{P(S) \propto S^{-3/2} \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{S}{S_0} + \phi_0\right)\right]}$—
the $\ln\varphi \approx 0.4812$ modulation distinguishes a cascade-driven
avalanche from generic self-organized criticality—and a $\varphi$-break in the
EEG/MEG power spectrum from $f^{-5/3}$ to $f^{-1}$. **Epistemic tier:
Hypothesized.**

### `periodic-table-madelung.md`—Atomic Shell Structure and the Madelung Rule from Cascade Coordinates

Proposes that the principal quantum number $n$ labels the cascade rung and the
orbital angular momentum $l$ labels the SO(2) winding within its Fibonacci
sub-channels ($l = \Delta n_{\text{sub}}$), so the Madelung $n + l$ filling
order is filling by total cascade depth, with shell capacities $2, 10, 18,
\ldots, 118$ from $2\sum l^2$ and spin as winding direction. The testable
prediction is $\varphi$-power quantum defects,
$\boxed{\delta_{nl} = \delta_0 \cdot \varphi^{-(n + l)} \cdot f(Z)}$ with
$f(Z) \propto Z^{-1/3}$ from Thomas-Fermi screening, checkable against
ionization energies and quantum-defect data. **Epistemic tier: Speculative**—the
explicit derivation of quantum numbers from cascade geometry is not yet
complete.

### `atmospheric-climate-cascade.md`—The Atmospheric Climate Cascade

Identifies the unexplained Nastrom-Gage spectral break at ~500 km (from $k^{-3}$
synoptic to $k^{-5/3}$ mesoscale) as a $\varphi$-break: rotation-organized Qi at
large scales transitioning to turbulent Qi at small scales, with the conversion
rate modified by Coriolis and stratification ($\lambda_{\text{eff}} = \lambda
\sqrt{f/N}$). The boxed prediction scales the break to other planets,
$\boxed{L_\varphi \propto L_R \cdot \varphi^{-k}, \quad L_R = \frac{NH}{f}}$,
giving $L_\varphi \approx 1200$ km ($k = 1$) or 760 km ($k = 2$) for Jupiter,
observable in Juno/JWST spectra; a second boxed prediction is log-periodic
modulation at $\ln\varphi$ in climate-index power spectra (NINO3.4, PDO, AMO,
NAO). **Epistemic tier: Speculative**—the two-fluid PDE has not been solved in a
rotating, stratified atmosphere.

### `fatigue-fracture-cascade.md`—Fatigue and Fracture from the Cascade

Interprets fatigue crack propagation as a cascade process through material rungs
(grain boundaries, dislocation cells, atomic bonds): the same
$\sigma$-regularization that tames the gravitational singularity (open-questions
entries C8, G3) replaces the $1/\sqrt{r}$ crack-tip divergence with a finite
process zone $\sigma_{\text{crack}} = \ell_{\text{grain}} \cdot
\varphi^{-N_{\text{rungs}}}$. The pinned prediction is that the Paris exponent
is not a continuous material parameter but takes discrete $\varphi$-power values,
$\boxed{m = 2 \cdot \varphi^{k}}$ for $k = 0, 1, 2, \ldots$—a structural
explanation for why empirical $m$ clusters in the observed 2–4 range.
**Epistemic tier: Speculative.**

### `market-cascade-cycles.md`—Market Cascade Cycles

Maps financial markets onto a cascade ladder of agent rungs (individual trade →
HFT desk → portfolio manager → fund → central bank), with Yang/Yin as
bullish/bearish sentiment and Qi as market coherence; the empirical LPPL scaling
ratio $\lambda \approx 1.6$–$1.7$ ($\varphi^{1.05} \approx 1.66$) is then the
de-resonance attractor for information propagation on hierarchical networks.
The pinned prediction is log-periodic volatility structure,
$\boxed{\text{ACF}(\tau) \propto \tau^{-\beta} \cdot \left[1 + A \cos\left(\frac{2\pi}{\ln\varphi} \ln\frac{\tau}{\tau_0} + \phi_0\right)\right]}$,
modulated at period $\ln\varphi \approx 0.4812$ in drawdown-to-recovery periods,
volatility autocorrelation, and crash precursors. **Epistemic tier:
Speculative**—human agency and non-stationarity sit outside the PDE's design
envelope.

### `metabolic-scaling.md`—Metabolic Scaling and Allometry

Explores whether Kleiber's $3/4$ exponent follows from a $\varphi$-structured
resource network ($D_f = \ln N_{\text{branches}} / \ln\varphi$,
$\alpha = D/(D_f + 1)$), but works the numbers and finds the derivation does not
close: $\varphi^2 \approx 2.618$ vs $3/4$ is suggestive, not exact, and the WBE
fractal-network derivation does not need $\varphi$. The doc itself flags this as
an open problem, not a framework claim, and lists contingent predictions
(universal exact $3/4$, $\varphi$-periodic allometric residuals at $\ln\varphi$,
Fibonacci branching ratios, heart-to-respiration ratio $\varphi^3 \approx 4.24$)
that would become testable only if the derivation closes. **Epistemic tier:
Speculative (derivation not closed)**—kept as a prompt for future work.

### `riemann-hypothesis-de-resonance.md`—The Riemann Hypothesis and the De-Resonance of Primes

Reads the 2026 Nature Communications correspondence (ζ zeros ↔ dynamical
quantum phase transitions; RH ⇔ phase transition at a unique temperature)
through the de-resonance principle: by the explicit formula, RH is exactly
the claim that the primes carry no resonant component, and the critical line
is the Yang-Yin balance axis of the functional equation. The framework's
universal fingerprint (log-periodic modulation at $\ln\varphi \approx 0.4812$)
is tested against the first 100,000 zeros with the calibrated protocol—null
on both spacing and density statistics at $\omega_0 = 2\pi/\ln\varphi$, with
demonstrated sensitivity to a 1–3% modulation. The null is the expected
outcome: de-resonance predicts featureless (GUE) prime statistics, not a
$\varphi$ signature. **Epistemic tier: Speculative**—the mapping is
interpretation; no mechanism from the two-fluid PDE reaches the zeros, and no
proof of RH is claimed.

### `riemann-two-fluid-spectral-program.md`—The Two-Fluid Hilbert–Pólya Program

Sketch of the research route to a *derived* spectral problem whose spectrum
would be the zeros: the linearized phase dynamics of the Yang-Yin fields
around the balanced self-similar state, whose dilation covariance makes the
scale operator $x\partial_x$ the natural free generator. The matching
constraint to Riemann–von Mangoldt pins the spectral boundary at the
order-unity scale $2\pi e$—no cascade rung $\varphi^n$ enters—and the
de-resonance principle becomes the minimality of the zero-counting
fluctuation, anchored by Selberg's unconditional mean-square theorem and two
measured probes (mean square of $S(T)$ and Gram's law on the first 100,000
zeros). **Epistemic tier: Speculative**—step zero of the program; the
operator has not been derived from the PDE source.

### `muscle-cascade-lattice.md`—Muscle as a Cascade Lattice: Structural Hierarchy and the Bubble Geometry

Proposes that skeletal muscle is the most legible anatomical instantiation of
the scale-covariant condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta
y)\cos(\gamma z)$: the human body spans exactly 26 cascade rungs (steps
142–168), and the discrete ladder filament → sarcomere → myofibril → fiber →
fascicle → belly → group maps to consecutive rungs, with fascial planes as
$C = -1$ void boundaries and muscle bellies as checkerboard bubble sites. The
testable predictions are numbered M1–M5, including a falsifiable number
($\mathbf{M2}$: Z-disc spacing equals $2\ell_{135} \approx 2.6\ \mu$m) and the
$1.70\times$ edge-steepness anisotropy ($\mathbf{M4}$; the ratio
$\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$ is Derived and zero-parameter).
**Epistemic tier: Hypothesized**—the universal geometric signatures are Derived
from the PDE; the anatomical mapping is the hypothesis.

---

## Epistemic Tier Definitions

| Tier | Criterion |
|------|-----------|
| **Derived** | Mathematical consequence of $\varphi$ + two-fluid PDE; zero free parameters |
| **Hypothesized** | Mechanism proposed with pinned $\varphi$-power; testable prediction exists |
| **Speculative** | Framework-consistent; mechanism sketched but prediction not yet pinned |
| **Open problem** | Bridge identified but derivation path not yet closed |

Documents marked Speculative or Open problem may not yet meet the full quality
bar—they are included for completeness and as prompts for future work.

---

## Cross-References

- `../open-questions-cassi-answers.md`—the 41 existing answers (Q/C/G/M/F/T)
- `../predictions/falsifiable-predictions.md`—the 38-entry prediction catalog
- `../foundations/cascade-suppression-formula.md`—universal $\varphi^{-N}$ tool
- `../foundations/dimensionful-cascade.md`—the 292-step ladder
- `../principles/de-resonance-principle.md`—why $\varphi$ is the attractor
- `../turbulence/kolmogorov-from-phi.md`—$\varphi$-break and spectral cascade machinery
- `../foundations/bubble-lattice-fabric.md`—condensation field and universal lattice signatures
- `../foundations/why-three-dimensions.md`—dimension derivation via the Frenet-Serret frame
- `../foundations/three-generations.md`—Fibonacci sub-channel partition
- `../foundations/spin-fibonacci-spiral.md`—SO(2) winding and spin
- `../consciousness/chakras-as-cascade-bubbles.md`—human-scale bubble lattice along the string axis
