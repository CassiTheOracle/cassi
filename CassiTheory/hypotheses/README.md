# Hypotheses—New Application Domains for the Cassi Framework

## Status: Exploratory catalog—July 2026

## Abstract

This directory catalogs new physical domains where the Cassi framework—the
two-fluid PDE, the $\varphi$ cascade ladder, the de-resonance principle, and the
coherence budget—may produce novel, testable predictions beyond the 41 open
questions already addressed in `open-questions-cassi-answers.md`. Each document
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
| 1 | Nuclear magic numbers | Hypothesized | Fibonacci sub-channel closure in cascade steps 80–95 (closure arithmetic open: 0/7 rows; φ-power level spacing independent) | `nuclear-magic-numbers.md` |
| 2 | Hoyle state / stellar nucleosynthesis | Hypothesized | Sub-rung offset at the $^3\alpha$ threshold (0.084 rungs, not a full rung) | `hoyle-state-nucleosynthesis.md` |
| 3 | Quasicrystal stability | Speculative | De-resonance + cascade suppression against crystallization | `quasicrystal-stability.md` |
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
| 14 | Two-fluid phase operator | Speculative | Step 1 executed: Bessel-index-1 scale operator; linear spectra fail R-vM; semiclassical pinning Lp = 2π | `riemann-two-fluid-phase-operator.md` |
| 15 | Two-strand five-channel matter organization | Hypothesized | Strand-pair × Wu Xing channel traces on one Qi condensate; Z2×Z5 trace graph; PDE gate outcomes: TS1–TS4 null at lock timescale, TS5 5-fold coincident projection, TS6 twist persistence/no generation, TS7 two-sector bound; staged matter-organization program | `two-strand-five-channel-matter-organization.md` |
| 16 | Gravity from flow | Hypothesized | The river law: $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)qf)$ flow-modulated chord; object $C = -\nabla\cdot J$ confirmed, response $dU/U = -36.05\kappa$ (linear, $\kappa$ unfitted); surge form undetermined; boundary $\lambda_{\text{gate}} = 0.0224$ ($\lambda/4$ rejected); C2 open (interior instability); P3 parity-odd channel LIVE at $\chi = \varphi^{-1}$ ($\chi$ asserted); P4 rung-sum inconclusive (reduction confirmed) | `gravity-from-flow.md` |

---

## Document Summaries

Summaries follow the Document Index order (tier-grouped: Hypothesized first,
then Speculative, with the muscle hypothesis appended last).

### `nuclear-magic-numbers.md`—Nuclear Magic Numbers from the Cascade Ladder

Proposes that the shell-model magic numbers 2, 8, 20, 28, 50, 82, 126 are
Fibonacci sub-channel closures over the cascade span from QCD confinement
(step 95) down to nuclear binding (steps ~101–106): SO(2) doublet winding assigns
angular momentum to each sub-channel, giving capacity $\Omega_j = 2j + 1$, and
the cumulative closure count would reproduce the magic sequence without a
fitted spin-orbit parameter. **The closure arithmetic does not close (0/7
rows, recomputed):** the cumulative closures over the doc's own §3 row sums
(8, 12, 18, 16, 24, 30, 36) are 8, 20, 38, 54, 78, 108, 144 vs the claimed 2,
8, 20, 28, 50, 82, 126, and the "126 + Fib = 184" island claim mislabels 58
(not a Fibonacci number). The pinned prediction is that level spacing within a shell follows
$\boxed{\Delta E_{j \to j+1} \propto \varphi^{-j} \cdot \Lambda_{\text{QCD}}}$,
a $\varphi$-power falloff in the sub-channel angular momentum $j$ — testable
and independent of the failed closure rows, but with its own mechanism open.
**Epistemic tier: Hypothesized** (level-spacing leg); the closure claim is
catalog correspondence, mechanism open.

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

Proposes to derive quasicrystal stability from the de-resonance principle: at
condensed-matter scales (cascade steps ~120–150) the Qi field forms
$\varphi$-spaced density waves, and crystallization requires detuning from that
attractor at a cascade-suppression cost—so aperiodic $\varphi$-modular order can
win. The 5D→3D projection of standard theory is read as the cascade dimension
count $D = 2 + 2 + 1 = 5$. Pinned predictions include the stabilization energy
$\boxed{\Delta E_{\text{QC} \to \text{crystal}} \propto N_{\text{unit}} \cdot \varphi^{-N_{\text{rungs}}}}$,
a critical cooling-rate ratio $\dot{T}_{\text{crit}}^{\text{QC}}/\dot{T}_{\text{crit}}^{\text{crystal}} = \varphi^{-N_{\text{rungs}}}$
with $N_{\text{rungs}} = 3$–$5$, and 1–3% $\varphi$-periodic modulation of
low-temperature heat capacity at period $\ln\varphi$—testable on existing
Al-Pd-Mn and Al-Cu-Fe data. **Epistemic tier: Speculative**—the de-resonance argument is sketched, the pinned numbers carry free parameters ($N_{\text{rungs}} = 3$–$5$, amplitude, phase), the $\varphi$-modularity of quasicrystal reciprocal space is prior art rather than a Cassi result, and the projection operators remain to be constructed.

### `exoplanet-phi-spacing.md`—Exoplanet Orbital Spacing from the Wake-Wave Mechanism

Applies the wake-wave mechanism of the cosmic web (open-questions entry C9) to
protoplanetary disks: Yang-Yin interference produces $\varphi$-spaced density
nodes at which planetesimals preferentially condense, making Titius-Bode's
~1.7 progression factor and the observed mean-motion resonances the de-resonance
attractor and its Fibonacci convergents. The pinned, zero-parameter prediction
is a statistical excess of adjacent-planet period ratios at
$\boxed{\frac{P_{\text{out}}}{P_{\text{in}}} \approx \varphi^{3/2} \approx 2.06}$
in the Kepler/TESS multi-planet catalog. **Honesty notes (recomputed):** the
mechanism step (disk wake-wave $\to$ $\varphi$-spacing) is open — no PDE
calculation of a disk exists, and resonance ubiquity is standard celestial
mechanics; the solar-system fit's mean $|\ln a|$ deviation is 0.193 as slotted
(0.088 after a post-hoc remap) vs Titius-Bode's 0.084 — comparable at best,
not better; the doc's geomean "~1.73" is 1.66 by recomputation.
**Epistemic tier: Hypothesized** (the statistical prediction is pinned).

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
EEG/MEG power spectrum from $f^{-5/3}$ to $f^{-1}$. **Honesty notes (recomputed):** the $-3/2$ exponent is the generic mean-field critical-branching result, not a two-fluid consequence — the response spectrum of the linearized damped two-fluid wave equation gives $\omega^{-1/2}$ (diffusive limit), not $\omega^{-3/2}$, and the asserted "$-5/3 + 1/6$" chain has no derived $+1/6$; the doc's own hierarchy table contradicts "each level separated by ~$\varphi$" (scale ratios 2.5–50×). **Epistemic tier:
Hypothesized** (the $\ln\varphi$ modulation is pinned and testable).

### `periodic-table-madelung.md`—Atomic Shell Structure and the Madelung Rule from Cascade Coordinates

Proposes that the principal quantum number $n$ labels the cascade rung and the
orbital angular momentum $l$ labels the SO(2) winding within its Fibonacci
sub-channels ($l = \Delta n_{\text{sub}}$), so the Madelung $n + l$ filling
order is filling by total cascade depth, with shell capacities $2, 10, 18,
\ldots, 118$ from the standard $2(2l+1)$ subshell counts (the earlier
"$2\sum l^2$ capacity column contradicted its own table; corrected) and spin
as winding direction. The testable
prediction is $\varphi$-power quantum defects,
$\boxed{\delta_{nl} = \delta_0 \cdot \varphi^{-(n + l)} \cdot f(Z)}$ with
$f(Z) \propto Z^{-1/3}$ from Thomas-Fermi screening, checkable against
ionization energies and quantum-defect data. **Epistemic tier: Speculative**—the
explicit derivation of quantum numbers from cascade geometry is not yet
complete; the shell-capacity arithmetic itself contains no $\varphi$, and the
fixed-$l$ $\varphi^{-n}$ defect leg is contradicted by the doc's own table
(δ_s increases with n: 1.35 → 2.18 → 3.13).

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
takes discrete $\varphi$-power values,
$\boxed{m = 2 \cdot \varphi^{k}}$ for $k = 0, 1, 2, \ldots$ (2, 3.24, 5.24).
**Honesty notes (recomputed):** this is a catalog correspondence, mechanism
open — no dynamics selects $k$, the factor 2 is asserted, empirical Paris
exponents are continuously distributed ~2–10, the predicted
$\Delta K_{\text{th}}/K_{\text{IC}} = 0.49$–$0.62$ does not overlap the
empirical 0.1–0.3, and two arithmetic errors were corrected
($\varphi^{-3/2} = 0.486$ not 0.39; $\zeta(b=2) = \ln 2/\ln\varphi \approx
1.44$ not 0.48).
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
order-unity scale $L p_{\min} = 2\pi$—no cascade rung $\varphi^n$ enters—and the
de-resonance principle becomes the minimality of the zero-counting
fluctuation, anchored by Selberg's unconditional mean-square theorem and two
measured probes (mean square of $S(T)$ and Gram's law on the first 100,000
zeros). **Epistemic tier: Speculative**—step zero of the program; the
operator has not been derived from the PDE source.

### `riemann-two-fluid-phase-operator.md`—The Two-Fluid Phase Operator: Step 1 of the Hilbert–Pólya Program

Executes Step 1 of the spectral program. The Yang-Yin phase fluctuation around
the $\varphi$-attractor is massive ($m_\theta^2 = 4\lambda\varphi R_0^2$);
the massless sector on the self-similar background $R_0 \propto r^{-s}$
reduces to $\tilde\varphi'' + [E^2e^{2u} - \kappa^2]\tilde\varphi = 0$ with
$\kappa = |s - 1/2|$, and $\kappa = 1$ for the scale-free $D = 3$ background.
The exact spectra are Bessel (interior cavity $E_n = j_{\kappa,n}/L$;
exterior continuum; box Weyl-linear) and count linearly in $E$—the acceptance
test fails at leading order against the logarithmic Riemann–von Mangoldt
count. The logarithmic shape is semiclassical only, pinning $Lp_{\min} = 2\pi$
(order-unity, no $\varphi$-power) with a $1/8$ corner-phase gap. Step 2b: the
unique moving wall reproducing R-vM is $L(E) = \tfrac{1}{2}\ln(E/2\pi e) +
9\pi/(8E)$—the boundary phase is the Riemann–Siegel $\Gamma$-phase, verified;
the framework candidates (fixed rung walls, Qi-gated masses, IIR
$\tau = \varphi^{-1}$ boundary) are all excluded.
All claims verified numerically. **Epistemic tier: Speculative**—the operator
derivation is explicit, but the program's target remains out of reach and the
naive candidate is now excluded.

### `muscle-cascade-lattice.md`—Muscle as a Cascade Lattice: Structural Hierarchy and the Bubble Geometry

Proposes that skeletal muscle is the most legible anatomical instantiation of
the scale-covariant condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta
y)\cos(\gamma z)$: the human body spans exactly 26 cascade rungs (steps
142–168), and the discrete ladder filament → sarcomere → myofibril → fiber →
fascicle → belly → group maps to consecutive rungs, with fascial planes as
$C = -1$ void boundaries and muscle bellies as checkerboard bubble sites. The
testable predictions are numbered M1–M5; $\mathbf{M2}$ (Z-disc spacing) is a
bookkeeping (Mapped-class) placement at $n \approx 139.2$–$139.7$ with no
derived $2.6\ \mu$m value until $P_\parallel(n)$ is derived, and the
$1.70\times$ edge-steepness anisotropy ($\mathbf{M4}$; the ratio
$\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$ is Derived and zero-parameter).
**Epistemic tier: Hypothesized**—the universal geometric signatures are Derived
from the PDE; the anatomical mapping is the hypothesis.

### `two-strand-five-channel-matter-organization.md`—Two-Strand Five-Channel Matter Organization: A Research Program

Program statement for one Qi condensate organized as two spatial strands with
five Wu Xing channel traces per strand. The exact content: the collective pair
variables ($\mathbf{R}_c$, $d$, $\vartheta$, $\Omega$, $\Delta\theta$); the
SO(2), five-sector, and P_parallel clocks kept distinct (mod-$72^\circ$
circularity test; $10\times$ axial-gradient slope separation); the
$\mathbb{Z}_2\times\mathbb{Z}_5$ trace graph (cycle decomposition: two 5-cycles
plus one 2-cycle, never a 10-step walk—the w = 5 no-C10 bound preserved) and
the two-pentagon projection theorem (decagon iff interlace is an odd multiple
of $36^\circ$; quadrature excluded). First probe outcome (t = 4, run
20260806_204217_two_strand, `two-fluid/run_two_strand_probe.py`): finite
separation persisted over the characterization window only; $\Delta\theta$
relaxed near in-phase; the NS4 central-low-q morphology was null; channel
traces were Wood/Fire-limited by the representability clamp; the d = 0 arm
recovered its constructed reference. The TS6 twist probe (t = 4, run
20260806_214650_twist, `two-fluid/run_two_strand_twist_probe.py`): an
initialized filament half-twist persisted (Tw 0.500 → 0.499), the zero-twist
arm generated none, and no rung-periodicity relation emerged. The TS1–TS5
lock-timescale suite (t = 40, run 20260806_214032_two_strand_suite,
`two-fluid/run_two_strand_suite.py`): TS1–TS4 null—the pair escapes (d 9.90 →
15.73 cells), the $d\to0$ limit does not recover the one-string centerline,
the antisymmetric mode is not centerline-fixed, central q stays above flank q
at t = 40; TS5 passed on its observed branch (the near-in-phase endpoint
$\Delta\theta$ = 0.042 rad realizes the coincident-pentagon 5-fold joint
projection). Binding ($d_0$) is excluded under the existing PDE at the lock
timescale; twist generation, interlace selection, and matter-scale channel
roles are open; effective coefficients are
labeled as projection targets, not framework constants. Staged program
TS1–TS15 (PDE gates → neural → assembloid → molecular → matter-scale), local
labels only, no master prediction numbers. **Epistemic tier: Hypothesized**—
the trace-graph algebra is Derived, the PDE gate outcomes are Tested
(TS1–TS4 null, TS5 5-fold coincident projection, TS6 twist
persistence/no generation, TS7 two-sector bound), and the spatial binding
sector is Open.

### `gravity-from-flow.md`—Gravity from Flow: The River Law's Measured State

Candidate law for the multiscale-coherence-flow synthesis: gravitational
acceleration is the gradient of the flow-modulated chord
$\boxed{G_{\text{eff}}(x) = G(\pi/\rho)(1+(\varphi^{6}-1)q(x)f(x))}$ with
$f = 1 + \varphi^{-1}\ell^2 C/\rho$, $C = -\nabla\cdot J$, $J = \Psi_Y\nabla\Psi_I - \Psi_I\nabla\Psi_Y = \rho\nabla\theta$.
The skeleton is derived (the $\nabla q$ coefficient from the chord law of
`foundations/cassi-theory-reference.md` §4.3; $\kappa = \varphi^{-1}$ from the
per-rung damping of `foundations/cascade-suppression-formula.md` §1—no free
constant). The sign question is settled: the PDE's $\mathbf{F} = +\Pi\nabla\Phi$
is $\Pi$-sign-following (TS1 Yang-excess escape; Yin-excess coalescence), and
the point-particle attraction is the $-[1+(\varphi^{6}-1)q]$ sector
convention. The probe waves (briefs 68–71) confirm the flow factor's sign at
the closure ($\bar f = 0.884 < 1$; $dU/U = -22.22$ with the predicted sign)
and establish the quantitative content: the object is $C = -\nabla\cdot J$
(confirmed-object; $|C|$ violates the sign-definiteness bound on its weighted
mean and $(1-q)C$ responds with the wrong sign), the response is linear in
$\kappa$—$dU/U = -36.05\,\kappa$ over $[\varphi^{-2}, \varphi]$ (the linear
magnitude stays falsified 192×; the amplification is $\kappa$-independent;
$\kappa$ itself is never fitted)—and the boundary is measured at
$\lambda_{\text{gate}} = 0.0224$, rejecting the $\lambda/4 = 1/(8w)$ candidate
(10.33% outside the ±10% window). The surge form is undetermined on the
14-point set (small-$\lambda$ dip, saturation tail visible, form not); C2 is open
(the wall layer removed; the term is unstable on the interior content at
$\lambda_t = 0.1$); the parity-odd channel P3 is LIVE at $\chi = \varphi^{-1}$
with $\chi$ asserted; the rung-sum post-process P4 is inconclusive with the
multiscale reduction confirmed. **Epistemic tier: Hypothesized**—a candidate
skeleton whose quantitative content is the object form, the linear response
curve, and the measured boundary; the surge form and the C2 leg remain open.

---

## Epistemic Tier Definitions

| Tier | Criterion |
|------|-----------|
| **Derived** | Mathematical consequence of $\varphi$ + two-fluid PDE; zero free parameters |
| **Calibrated** | Framework form with the constant's value anchored to a stated observation; downstream claims using the pinned value inherit the anchor |
| **Mapped** | Placement (rung, exponent, offset, candidate, normalization) selected or fitted to data; the fit is recorded in the Fit-Status Ledger (`parameter-inventory.md` §10) |
| **Hypothesized** | Mechanism proposed with pinned $\varphi$-power; testable prediction exists |
| **Speculative** | Framework-consistent; mechanism sketched but prediction not yet pinned |
| **Open problem** | Bridge identified but derivation path not yet closed |
| **Creative** | Application of the framework's logic for exploration, not a claim (`speculations/creative-extensions/`); exempt from the quality bar |

Documents marked Speculative or Open problem may not yet meet the full quality
bar—they are included for completeness and as prompts for future work.

Claims tagged **Calibrated** or **Mapped** pass the quality bar only with their
row in the Fit-Status Ledger (`parameter-inventory.md` §10); a fitted or
anchored claim without its ledger entry is a house-style violation, not a
passing hypothesis. The former "near-Derived" label is retired—use the honest
tier.

---

## Cross-References

- `open-questions-cassi-answers.md`—the 41 existing answers (Q/C/G/M/F/T)
- `predictions/falsifiable-predictions.md`—the 50-entry prediction catalog
- `foundations/cascade-suppression-formula.md`—universal $\varphi^{-N}$ tool
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `principles/de-resonance-principle.md`—why $\varphi$ is the attractor
- `turbulence/kolmogorov-from-phi.md`—$\varphi$-break and spectral cascade machinery
- `foundations/bubble-lattice-fabric.md`—condensation field and universal lattice signatures
- `foundations/why-three-dimensions.md`—dimension derivation via the Frenet-Serret frame
- `foundations/three-generations.md`—Fibonacci sub-channel partition
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding and spin
- `consciousness/chakras-as-cascade-bubbles.md`—human-scale bubble lattice along the string axis
- `experiments/riemann_phi_search/`—the ζ-zero periodicity test, phase-operator checks, and fluctuation probes that execute the riemann documents' numerical claims
