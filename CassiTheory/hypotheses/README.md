# Hypotheses—New Application Domains for the Cassi Framework

## Status: Exploratory catalog—July 2026

## Abstract

This directory catalogs new physical domains where the Cassi framework—the
two-fluid PDE, the $\varphi$ cascade ladder, the de-resonance principle, and the
coherence budget—may produce novel, testable predictions beyond the 42 open
questions addressed in `open-questions-cassi-answers.md`. Each document
identifies a specific Cassi mechanism, sketches a derivation path, and proposes
one or more falsifiable tests.

**Quality bar:** A hypothesis earns a place here only if (1) the proposed Cassi
mechanism extends existing derived machinery rather than inventing new structure,
and (2) it makes at least one zero-parameter or low-parameter prediction
distinguishable from the null hypothesis. The contribution must identify what
Cassi uniquely adds; a standalone appearance of $\varphi$ does not satisfy
this bar.

---

## Document Index

| # | Domain | Epistemic | Bridge | Document |
|---|--------|-----------|--------|----------|
| 1 | Nuclear magic numbers | Hypothesized | Fibonacci sub-channel closure in cascade steps 80–95 (closure arithmetic open: 0/7 rows; φ-power level spacing independent) | `nuclear-magic-numbers.md` |
| 2 | Hoyle state / stellar nucleosynthesis | Hypothesized | Sub-rung offset at the $^3\alpha$ threshold (0.084 rungs, not a full rung) | `hoyle-state-nucleosynthesis.md` |
| 3 | Quasicrystal stability | Speculative | De-resonance + cascade suppression against crystallization | `quasicrystal-stability.md` |
| 4 | Exoplanet $\varphi$-spacing | Hypothesized | Supplied log-radius disk-gap template; tested Cassi dynamical realization REJECT; orbital transfer and observational tests open | `exoplanet-phi-spacing.md` |
| 5 | Neural criticality / cascade brain | Hypothesized | Candidate neural application of the canonical PDE; biological measurement and parameterization required | `neural-criticality.md` |
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
| 17 | Scalar time reparameterization | Derived conditional theorem / Hypothesized common-lapse application | Exact autonomous first-order time-change equivalence; canonical conversion age $d\tau_F=(1-q)dt$; spatial PDE, second-order, stochastic, memory, boundary, and split-operator limits; CT-2 cross-clock discriminator | `scalar-time-reparameterization-applications.md` |

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
a $\varphi$-power falloff in the sub-channel angular momentum $j$—testable
and independent of the failed closure rows, but with its own mechanism open.
**Epistemic tier: Hypothesized** (level-spacing leg); the closure claim is
catalog correspondence, mechanism open.

### `hoyle-state-nucleosynthesis.md`—The Hoyle State as a Cascade Rung Resonance

Reinterprets the 7.65 MeV Hoyle state as structural rather than anthropic: it
sits one cascade rung above the $^3\alpha$ threshold (7.27 MeV), with the
0.38 MeV gap identified as a Fibonacci sub-channel splitting at nuclear rungs
~82–88. The key prediction generalizes the Hoyle anchor to all $\alpha$-cluster
nuclei—excitation spacing
$\boxed{E_{\text{exc}}(N_\alpha + 1) - E_{\text{exc}}(N_\alpha) \propto \varphi^{-N_\alpha} \cdot \Lambda_{\text{QCD}}}$—with
concrete numbers for $^{16}$O (6.05 MeV), $^{20}$Ne (5.79 MeV), and
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

Applies the supplied log-radius bubble-shell template to protoplanetary disks.
The registered first-order and undriven second-order Cassi dynamics do not
generate its multiplicative ring ladder; the driven second-order control forms
additively spaced phase layers, and phase staggering alone remains gapless.
The coordinate template and its disk-to-orbit preservation map remain
Hypothesized. The conditional detached-orbit target is
$\boxed{P_{\text{out}}/P_{\text{in}}=\varphi^{3/2}
\approx2.058171}$ in a Kepler/TESS **multi-planet** catalog; the disk branch
tests successive **radial gap ratios** in resolved disks. The explicitly
confirmed primary Kepler sample contains 476 systems and 562 adjacent ratios
inside $[1,3]$. Its registered classifier result is **INDETERMINATE**
($z_{\rm win}=1.087$), and the scientific verdict is **INCONCLUSIVE** because
the target window overlaps the conventional excess immediately wide of the
2:1 resonance. The DSHARP branch remains pending an auditable data-and-results
receipt. **Epistemic tier: Hypothesized**; no mechanism-specific field signal
is established.

### `neural-criticality.md`—Neural Criticality and the Cascade Brain

Extends the consciousness framework to a Hypothesized candidate mapping of
neural dynamics: hierarchical modularity, avalanche statistics, and scale-free
spectra are proposed signatures requiring biological measurement and a
parameterization bridge before any canonical two-fluid interpretation. The
avalanche exponent $-3/2$ is an external mean-field critical-branching result,
not a two-fluid derivation. The candidate EEG/MEG break uses
$f_\varphi=\bar\lambda(1+\varphi)f_{\text{base}}/(2\pi)$ with dimensionless
$\bar\lambda$ normalization; the $f^{-5/3}$ and $f^{-1}$ sides remain a
Hypothesized application, not a measured law. A low-frequency $f^{-2}$ slope
is mentioned only as an unverified comparison because no source, dataset, or
retained receipt is present. The candidate $D=2+1/\varphi\approx2.62$ is an
unregistered geometric correspondence requiring a mechanism and independent
fractal-dimension measurement, not a derived dimension or current prediction.
**Epistemic tier: Hypothesized** (candidate tests remain open).

### `periodic-table-madelung.md`—Atomic Shell Structure and the Madelung Rule from Cascade Coordinates

Proposes that the principal quantum number $n$ labels the cascade rung and the
orbital angular momentum $l$ labels the SO(2) winding within its Fibonacci
sub-channels ($l = \Delta n_{\text{sub}}$), so the Madelung $n + l$ filling
order is filling by total cascade depth, with shell capacities $2, 10, 18,
\ldots, 118 from the standard $2(2l+1)$ subshell counts and spin
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
**Epistemic qualification (recomputed):** this is a catalog correspondence, mechanism
open—no dynamics selects $k$, the factor 2 is asserted, empirical Paris
exponents are continuously distributed ~2–10, the predicted
$\Delta K_{\text{th}}/K_{\text{IC}} = 0.49$–$0.62$ does not overlap the
empirical 0.1–0.3, and the current arithmetic gives
$\varphi^{-3/2} = 0.486$ and $\zeta(b=2) = \ln 2/\ln\varphi \approx
1.44$).
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

Examines whether Kleiber's $3/4$ exponent can acquire a $\varphi$-based
first-principles origin. The WBE dimensional law is
$\alpha_{\mathrm{WBE}}(D)=D/(D+1)$, giving $3/4$ for a three-dimensional
space-filling network and $2/3$ for $D=2$. A distinct diagnostic insertion,
$\alpha_{\mathrm{trial}}=3/(D_f+1)$, exposes the consequence of substituting
an illustrative $\varphi$-based branch dimension $D_f$; it is not the WBE law.
The branch counts and $D_f$ values are candidate parameterizations, not
universal measurements, and the $\varphi$ derivation remains open. **Epistemic
tier: Speculative (derivation not closed)**—no metabolic evidence beyond the
source WBE result is claimed.

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

The document treats skeletal muscle as a Hypothesized anatomical comparison
with the scale-covariant condensation field
$B(x,y,z)=\cos(\alpha x)\cos(\beta y)\cos(\gamma z)$, not as a cross-rung
identity. In this document the Derived content is limited to the transverse
algebra, including the level-dependent directional edge-slope proxy
$R(\theta_{\mathrm{cond}})=\frac{\sqrt{1+\varphi^2}}{2}
\sqrt{\frac{1+\theta_{\mathrm{cond}}}{\theta_{\mathrm{cond}}}}$; at the
phenomenologically selected $\theta_{\mathrm{cond}}=0.45$, $R=1.7072$ is a
conditional geometric-proxy benchmark, and no $C=0.45$ edge survives the
fixed-step PDE endpoint. The anatomical mapping remains conditional. $B=-1$
is the void-center extremum, while a fascial boundary is
$B=\theta_{\mathrm{cond}}$. Axial/radial assignments, Fibonacci relations
across rungs, and $\varphi$-rescaling or parameter/unit renormalization are
conditional Hypothesized claims requiring an explicit convention. The
staggered-checkerboard axial-diagonal neighbor count is a 2D transverse
cross-section count, not a full 3D neighbor count. M4 is a normalized
$(\alpha,\beta)$ direction with slope $\varphi$ (about $58.3^\circ$ from Yang),
not a literal $45^\circ$ angle; Q5 is a speculative ventricular imaging
target, not a Fibonacci/octave or Torrent–Guasp derivation.
**Epistemic tier: Hypothesized**—the anatomical mapping is the hypothesis.


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
labels only, no master prediction numbers. **Epistemic tier: Hypothesized**—the
trace-graph algebra is Derived, the PDE gate outcomes are Tested
(TS1–TS4 null, TS5 5-fold coincident projection, TS6 twist
persistence/no generation, TS7 two-sector bound), and the spatial binding
sector is Open.

### `gravity-from-flow.md`—Gravity from Flow: The River Law's Measured State

Candidate law for the multiscale-coherence-flow synthesis: the scalar
coefficient
$\boxed{G_{\text{eff}}(x)=G(\pi/\rho)(1+(\varphi^{6}-1)q(x)f(x))}$ belongs
to a separate gravitational acceleration/potential law; it is not itself an
acceleration, gradient, or force. A Poisson/lensing forward model and
dimensional normalization are still required before that candidate law can be
used as gravity.

The canonical tested density-plane diagnostic is
$C_d=-\nabla\cdot J_d$, with $J_d$ distinct from the optional complex-amplitude
extension
$J_\Psi=\rho\nabla\theta_\Psi/f_\Psi$ and
$C_\Psi=-\nabla\cdot J_\Psi$. The latter amplitude-current object is
conditional and is not the receipt-level measured density-plane object. The
probe waves (briefs 68–71) establish the sign and response for $C_d/J_d$:
the closure has $\bar f=0.884<1$, $dU/U=-22.22$ with the predicted sign, and
the measured response is linear in $\kappa$ with
$dU/U=-36.05\,\kappa$ over $[\varphi^{-2},\varphi]$; the sign-definiteness
bound fails on the tested density-plane object. The boundary is measured at
$\lambda_{\text{gate}}=0.0224$, while the surge form and C2 leg remain open.
The parity-odd P3 channel is LIVE at $\chi=\varphi^{-1}$ and the rung-sum P4
post-process is inconclusive. **Epistemic tier: Hypothesized**—a candidate
skeleton and tested density-plane response, not a completed gravity law.

### `scalar-time-reparameterization-applications.md`—Scalar Time Reparameterization in Cassi Applications

States and proves the exact equivalence between an autonomous first-order
generator and its positive scalar time change. The paper distinguishes a
global clock from spatially varying local ages, and derives the required
transformations for second-order systems, Itô noise, memory kernels, boundary
data, and noncommuting operator splits. The canonical conversion age
$d\tau_F=(1-q)dt$ and the relative candidate $N_q=(1-q)/(1-q_{\mathrm{ref}})$
are **Derived conditional**; assigning $N_q$ as a universal lapse across
independent sectors is **Hypothesized** and is tested by CT-2. Cross-repository
$q/Q$ symbols remain definition-separated.

---

## Epistemic Tier Definitions

| Tier | Criterion |
|------|-----------|
| **Derived** | Mathematical consequence under the stated equations, inputs, and postulates; empirical anchors and fitted or selected quantities retain their own tier |
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
anchored claim without its ledger entry is a house-style violation. Use the
epistemic tiers listed above.

---

## Cross-References

- `open-questions-cassi-answers.md`—the 42-entry epistemic registry (Q/C/G/M/F/T)
- `predictions/falsifiable-predictions.md`—the 56-entry prediction catalog
- `foundations/cascade-suppression-formula.md`—universal $\varphi^{-N}$ tool
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `principles/de-resonance-principle.md`—why $\varphi$ is the attractor
- `turbulence/kolmogorov-from-phi.md`—$\varphi$-break and spectral cascade machinery
- `foundations/bubble-lattice-fabric.md`—condensation field and conditional geometric lattice signatures
- `foundations/why-three-dimensions.md`—$\mathbb{R}^3$ Frenet consistency analysis and the open dimension-selection problem
- `foundations/three-generations.md`—Fibonacci sub-channel partition
- `foundations/spin-fibonacci-spiral.md`—optional compact-phase, half-angle, and spin mapping
- `consciousness/chakras-as-cascade-bubbles.md`—human-scale bubble lattice along the string axis
- `experiments/riemann_phi_search/`—the ζ-zero periodicity test, phase-operator checks, and fluctuation probes that execute the riemann documents' numerical claims
