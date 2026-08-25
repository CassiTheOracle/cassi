# Exoplanet Orbital Spacing from the Wake-Wave Mechanism

## Status: Hypothesized—August 2026

## Abstract

The Titius-Bode "law" for solar system planetary spacing ($a \propto 1.7^n$)
uses a progression factor close to $\varphi \approx 1.618$. The observed
spacing is a catalog correspondence; standard orbital dynamics does not select
$\varphi$ from this one system. A conditional Cassi reading identifies the
disk condensation wake with the bubble-shell ring ladder
(`foundations/bubble-edge-geometry.md` §3.1), which would place density nodes
(future disk gaps) at $\varphi$-spaced radii and successive gaps at
$\varphi^{-1}=0.6180$, against the interleaved null
$\varphi^{-1/2}=0.7862$. Under that model, the corresponding tests are
(a) a statistical excess of **adjacent-planet period ratios in the Kepler/TESS
multi-planet catalog** at $\varphi^{3/2}=2.058171\approx2.058\approx2.06$ and
its Fibonacci convergents, and (b) a statistical test of **successive radial
gap ratios in resolved protoplanetary disks**. The disk-gap branch (b) is
registered, but its reported analysis cannot be reproduced from this
checkout: the parsed gap table, raw source files, hashes, and run JSON are
absent. The disk-gap result therefore remains pending an auditable receipt
rather than an established observation. The planet-period branch is likewise
retained as a registered model test only; no current numerical verdict is
accepted.

## Origin Status

**Verdict: mechanism Derived conditional; tier stays Hypothesized.** The
disk mechanism is the bubble-shell ring ladder of
`foundations/bubble-edge-geometry.md` §3.1 (the ring law, **Derived
conditional** on the pitch convention, the doublet's $\pi$-per-rung internal
advance, the pool-cell parities, and the nesting depth). In a protoplanetary
disk the condensation wake plays the bubble shell: the density nodes—the
annular gaps resolved by ALMA—sit at $\varphi$-spaced radii
($r_k = R\,\varphi^{-k}$, successive ratio $\varphi^{-1} = 0.6180$, null
interleaved ratio $\varphi^{-1/2} = 0.7862$). The mechanism is the
phase-quantized radial ladder of the doublet phase ($\alpha = \pi u$), the
product of the SO(2) doublet advance and the pool-cell parities—not a
one-dimensional wake-sum beat. Pending status:

- **Radial-reading inference flag.** The reading of the doublet
  phase radially, $\alpha = \pi u$, is an inference resting on the nested
  sub-lattice structure (`foundations/bubble-lattice-fabric.md` §3.2), not an
  established identity; it is flagged throughout `foundations/bubble-edge-geometry.md`
  §3.1 and inherited by the disk application.
- **Dynamical realization open.** Whether the full ~10-ring ladder
  is realized from microphysics is not established. Two no-ring nulls are on
  record: the canonical solver's four-arm dynamic probe
  (`two-fluid/run_bubble_ring_dynamic_probe.py`—**NO RINGS** on all arms to
  $t=40$) and an unretained external space-sim second-order wave-form readback
  (**NO RIDGES**, transient shell with one interior ridge at ratio 0.545,
  dissipated by $t=40$). The ladder is kinematic; its dynamical realization in
  a disk is open, and the same caveat applies to the disk-gap reading.
- **The period-ratio prediction is registered, not currently tested.** Prediction
  54 specifies adjacent-planet period ratios in a Kepler/TESS **multi-planet**
  catalog. Receipt-style claims of a Kepler result, a folded-window
  significance, a K2/TESS cross-check, or an INDETERMINATE verdict are
  **invalid/pending**: the retained implementation has unresolved null-support
  and signal/control overlap defects described in §8, and its raw catalog,
  archive-confirmation evidence, hash receipt, and run JSON are not retained.
  No rerun or replacement verdict is claimed.
- **Disk-gap branch pending provenance.** Prediction 53 specifies successive
  radial gap ratios within each resolved disk, pooled only after the per-disk
  radial ratios are formed. This checkout retains neither the parsed gap table
  nor the raw source files, SHA-256 receipt, or run JSON. Pooled counts, null
  comparisons, significances, and detection-power claims are **invalid/pending**;
  no DSHARP verdict is assigned.
Tier stays **Hypothesized**: the disk-gap mechanism remains open, the DSHARP
analysis awaits a retained data-and-results receipt, and planet-carving is the
standard alternative. The registered tests are scoped to radial gap ratios
within resolved disks and adjacent-planet period ratios in a multi-planet
catalog; neither current receipt-style numerical claims nor a cross-channel
verdict is retained.

- **Solar-system fit.** The geometric mean of the document's six adjacent
  planet ratios is 1.66, with the 3.42 Mars/Jupiter jump dominating the set.
  The $\varphi$ fit has mean $|\ln a|$ deviation 0.193 for the fixed
  Mercury-to-slot-8 assignment; an assignment that maps Uranus to slot 8,
  Neptune to slot 9, and drops slot 7 gives 0.088. Titius-Bode gives 0.084
  under its stated assignment. These values compare bookkeeping choices and
  do not establish a mechanism.

The channel reading (`foundations/qi-as-spatial-spacing-signal.md` §4) remains
conditional: a coherence-coupled disk tracer could carry a spatial-spacing
signal, while detached orbital dynamics may not preserve that signal in
period-ratio statistics. With the current receipt defects, no Kepler result
or cross-channel verdict is assigned.

---

## 1. The Titius-Bode "Law"

The empirical Titius-Bode relation for solar system semi-major axes:
$$a_n = 0.4 + 0.3 \times 2^n \quad \text{(AU, for $n = -\infty, 0, 1, 2, \ldots$)}$$

The progression factor is 2, but the actual mean spacing ratio of adjacent
planets in our solar system varies: Venus/Earth = 0.723, Earth/Mars = 1.52,
Mars/Jupiter = 3.42 (the asteroid belt occupies this gap), Jupiter/Saturn =
1.83, Saturn/Uranus = 1.97, Uranus/Neptune = 1.56. The geometric mean of these
six ratios is 1.66, within 3% of $\varphi$ — but the set is dominated by the
single 3.42 Mars/Jupiter jump, and the ratio convention (inner/outer vs
outer/inner, Mercury included or not) moves the mean between 1.66 and 1.75.
One planetary system cannot select $\varphi$ over the progression factor 2
that Titius-Bode already fits.

The standard interpretation is that orbital resonances (mean-motion resonances
at period ratios like 2:1, 3:2, and 5:3) sculpt planetary spacing through
gravitational interactions. In the Cassi interpretation, these ratios can be
compared with Fibonacci convergents of $\varphi$ as a conditional
de-resonance mapping. Whether their ubiquity follows from a disk Qi field
seeking $\varphi$-equilibrium remains an open dynamical question.

## 2. The Ring Ladder in Protoplanetary Disks

The disk mechanism is the bubble-shell ring ladder (`foundations/bubble-edge-geometry.md`
§3.1). A condensation shell of effective radius $R$ carries interior matter
rings at

$$\boxed{r_k = R\,\varphi^{-k}, \qquad k = 0, 1, 2, \ldots}$$

and void troughs at $R\,\varphi^{-(k+\frac12)}$, so successive matter rings are
separated by the fixed ratio $\varphi^{-1} = 0.6180$ and each matter ring is
trailed inward by its void at $\varphi^{-1/2} = 0.7862$. The ladder is the
doublet's radial phase $\alpha = \pi u$, $u = \log_\varphi(r/\ell_n)$
(phase-quantized, *not* a beat); the negative result—the naive one-dimensional
wake-sum $\cos(2\pi r/\ell_n) + \cos(2\pi\varphi r/\ell_n)$ has zeros at
$\{0.191, 0.573, 0.809, 0.955\}\,\ell_n$, not a $\varphi$-ladder—is documented
in `foundations/bubble-edge-geometry.md` §3.5.

For a conditional disk application, the condensation wake can be compared with
the bubble shell: annular gaps in millimeter observations can be tested against
the $\varphi$-spaced template, with successive gap ratios
$\varphi^{-1}=0.6180$ and interleaved-null ratio $\varphi^{-1/2}=0.7862$. A
disk is not a static bubble shell; a gap is a radial intensity minimum whose
depletion mechanics are set by disk dynamics. The ladder supplies a testable
location template, not a demonstrated gap generator. Whether local density,
planet formation, or another process selects these loci remains open.

The disk reading inherits the radial-reading inference flag of
`foundations/bubble-edge-geometry.md` §3.1, and the ladder's dynamical
realization in a disk is open (the two no-ring nulls in Origin Status). The
prediction is a statistical, pooled statement, not a per-disk scaffolding.

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
peak at period ratios corresponding to low-order Fibonacci convergents (this
branch is untested here).

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

The fit is rough—the solar system is one sample. Mean absolute deviation in
$\ln a$ is 0.193 for the fixed Mercury-to-slot-8 assignment (with Saturn 34%
off and slot 7 matching nothing). An assignment that maps Uranus to slot 8,
Neptune to slot 9, and drops slot 7 gives 0.088. Titius-Bode's own mean
$|\ln a|$ deviation is 0.084 under its stated assignment. These values compare
bookkeeping choices and do not establish a mechanism.

## 5. Falsifiable Tests

1. **Kepler period-ratio excess (registered; current receipt invalid/pending).**
   The registered target is a statistical excess of adjacent-planet ratios
   $P_{\text{out}}/P_{\text{in}}$ in a Kepler/TESS **multi-planet catalog** at
   $\varphi^{3/2}=2.058171\approx2.058\approx2.06$. Receipt-style
   claims of a run, significance, cross-check, or INDETERMINATE verdict are
   invalid/pending: the retained analysis has unresolved null-support and
   signal/control overlap defects (§8), and its raw catalog, archive-
   confirmation evidence, hash receipt, and run JSON are absent. No rerun or
   replacement verdict is claimed.

2. **Resonance selectivity (registered design only).** The design compares
   Fibonacci-convergent resonance windows with non-Fibonacci controls in the
   same adjacent-ratio multi-planet sample. No numerical control counts,
   significance, or selectivity verdict is retained from the invalid receipt.

3. **Log-periodic $\varphi$-spacing in disk gaps (registered; evidence
   pending).** The ring/gap locations of ALMA-resolved protoplanetary disks
   should show $\varphi$-spacing in $\ln r$: successive **radial gap ratios**
   $\varphi^{-1}=0.618$ versus the null $\varphi^{-1/2}=0.786$. The DSHARP
   design is specified in §7, but the parsed input, source hashes, and run
   output are absent from this checkout; no data verdict, significance, or
   detection-power value is assigned.

4. **No per-system exact-ratio claim.** The $\varphi$ spacing is a pooled
   catalog or radial-gap-ratio hypothesis, not an exact fit for any individual
   planetary system or disk. Migration, scattering, and disk dynamics may move
   individual ratios away from the registered windows.

## 6. Open Issues

- Planet migration (Type I and Type II) after formation smears the primordial
  $\varphi$-spacing. The observed period ratio distribution convolves
  formation spacing with migration and dynamical instability. Disentangling
  these requires a population synthesis model with $\varphi$-spaced initial
  conditions.
- The solar system's Jupiter (5.2 AU vs. predicted 4.45 AU) is the largest
  deviation. The Grand Tack hypothesis (Jupiter migrated inward to ~1.5 AU then
  back out) could explain this if the formation location was near the predicted
  node.
- The asteroid belt (2.1–3.3 AU) spans approximately one $\varphi$-factor in
  radius—consistent with a disrupted $\varphi$-node, but the disruption
  mechanism (Jupiter's resonance sweeping) must be shown to operate at the
  predicted location.
- **The dynamical realization of the ladder in a disk is open.** The two
  no-ring nulls (Origin Status) apply: the canonical first-order solver does
  not spontaneously form standing rings, and the space-sim wave form shows no
  persistent ridge ladder. A real disk gap is carved by planet-disk
  interaction or other mechanisms; the Cassi ladder is a kinematic template,
  not an established generator of disk substructure.
- **Planet-carving is the standard alternative.** Many of the same
  $\varphi$-spaced gaps are naturally attributed to planets (low-order
  mean-motion resonances, 2:1, 3:2, 5:3, are Fibonacci convergents). The
  Cassi hypothesis predicts the *specific* Fibonacci set is overrepresented;
  distinguishing it from generic resonance-locking requires the selectivity
  test (§5, item 2), not yet run.

## 7. The DSHARP Disk-Gap Test (Prediction 53)

### 7.1 Pre-registered design

The ring ladder predicts, in a protoplanetary disk, annular gaps at
$\varphi$-spaced radii with successive (inner/outer) ratio $\varphi^{-1} =
0.6180$ against the interleaved-null ratio $\varphi^{-1/2} = 0.7862$. The
decision tree is pre-registered in the script docstring
(`experiments/dsharp_phi_gaps/stack_phi_gaps.py`, written before any analysis
run):

- **Data:** the 18 single-disk systems of the ALMA DSHARP survey; gap radial
  positions are specified by the survey's annular-substructure table
  (`tab:ringpositions`, Huang et al. 2018, arXiv:1812.04041; the survey is
  Andrews et al. 2018, arXiv:1812.04040).
- **Acquisition specification:** `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`
  records the intended download and hash procedure. The raw files and SHA-256 receipt are not
  retained in this checkout.
- **Ratios:** each disk's detected gaps sorted by radius, successive
  (inner/outer) ratios pooled across disks.
- **Windows (fixed):** signal $W_1 = [0.6180 \pm 0.08] = [0.538, 0.698]$;
  null $W_2 = [0.7862 \pm 0.05] = [0.736, 0.836]$.
- **Null:** for each disk, draw the same number of gaps from a log-uniform
  distribution over that disk's observed gap radial span; 1000 realizations.
  $E_1, E_2$ = null mean counts in $W_1, W_2$; $s_1, s_2$ = std.
- **Verdict:** counting $N_1$ pooled ratios in $W_1$ and $N_2$ in $W_2$:
  **SUPPORTS** if $N_1 \ge E_1 + 2s_1$ and $N_2 < E_2 + 2s_2$;
  **SUPPORTS NULL** if $N_2 \ge E_2 + 2s_2$ and $N_1 < E_1 + 2s_1$;
  else **INDETERMINATE**.

### 7.2 Data and provenance

- **Survey:** DSHARP (Andrews et al. 2018, arXiv:1812.04040, 20 targets; 18
  single-disk systems), with annular substructure positions cited from Huang
  et al. 2018 (arXiv:1812.04041), Table `tab:ringpositions`.
- **Repository state:** only `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`
  and `experiments/dsharp_phi_gaps/stack_phi_gaps.py` are present. The parsed
  gap table, raw e-print files, SHA-256 receipt, and run JSON are not retained.
  The reported sample counts and numerical results therefore cannot be
  independently reproduced from this checkout.
- **Evidence status:** the DSHARP design remains a registered test. No
  observation-level verdict is assigned until the input and output receipt is
  retained.

### 7.3 Results

No reproducible DSHARP result is available in this checkout. Exact pooled
ratios, window counts, null moments, significances, per-disk classifications,
and detection-power values are not evidence here without the missing input and
run receipts. No detection-power or sensitivity value is assigned. These
quantities require the missing parsed gap input and retained run output.

### 7.4 Verdict and statistical reading

Prediction 53 remains registered and **pending an auditable data-and-results
receipt**. The ring-ladder mechanism remains Hypothesized and conditional on
its dynamical realization in a disk; planet-carving remains the standard
alternative explanation.
---

## 8. The Kepler Period-Ratio Test (Prediction 54)

### 8.1 Registered design (not a retained result)

The period-ratio branch is registered for adjacent-planet
$P_{\text{out}}/P_{\text{in}}$ ratios in a Kepler/TESS **multi-planet**
catalog. The decision tree is recorded in the script docstring
(`experiments/kepler_phi_ratios/run_phi_ratios.py`), but the input and output
receipts needed to claim a completed run are not retained in this checkout.
The intended source is the NASA Exoplanet Archive `ps` table, with an explicit
archive-confirmation predicate required for each included planet; a parser
that merely treats a row label as confirmed is not sufficient evidence.

The registered signal is
$\varphi^{3/2}=2.058171\approx2.058\approx2.06$, with a fixed half-width
$0.05$ window. The associated signal interval is therefore approximately
$[2.008,2.108]$. The planned comparison includes Fibonacci-convergent
resonance windows and non-Fibonacci controls, but the $\varphi^{3/2}$ window
overlaps the stated 2:1 control interval $[1.95,2.05]$. Until that overlap is
resolved in the registered analysis, the control cannot serve as an
independent discriminator and no verdict transfers from this design.

The planned folded-window null uses equal-width windows across a declared
ratio support. The prior receipt used folded-null centers on $[1,3]$ while
other parts of the receipt used a ratio support extending to $[1,4]$; this
support/center mismatch is an unresolved design defect. A future run must
freeze one support and center domain before computing counts or significance.
The intended decision tree is retained as a registered design only:
SUPPORTS, SUPPORTS NULL, or INDETERMINATE would be assigned only after the
support, controls, catalog predicate, and complete receipts pass audit.

### 8.2 Data and provenance

The claimed acquisition is not auditable here. The raw catalog, archive-
confirmation evidence, source/hash receipt, and run JSON are absent. The sample
sizes, ratios, null moments, and any cross-check lack auditable receipts and are not retained as observations. The script paths below document
the intended acquisition and analysis locations; they do not prove that a run
was completed:

- `experiments/kepler_phi_ratios/acquire_kepler_catalog.py` — intended
  download, archive-confirmation filtering, parsing, and hashing;
- `experiments/kepler_phi_ratios/run_phi_ratios.py` — intended registered
  decision tree and folded-window null;
- **Required run receipt:** no JSON receipt is retained in this checkout.

### 8.3 Results

No Kepler, K2, or TESS numerical result is currently valid. The table of
counts and sigma values, the INDETERMINATE label, and any receipt-style
cross-check claim are **invalid/pending** because the raw/hash/run receipts
are missing and the retained implementation has the null-support mismatch and
overlapping signal/control windows described above. No rerun or replacement
verdict is claimed.

### 8.4 Detection power and selection effects

The detection-power statement is not retained. Its injection analysis
reused a null calibrated for $N$ observations when evaluating $N+K$
injections, so the reported percentages cannot support a power claim. A
future power calculation must recalibrate the null for each injected sample
size (or otherwise use a pre-specified size-matched procedure), while retaining
the raw injection seeds, null draws, and run receipt.

Selection effects remain an open design consideration rather than an
observed correction: transit geometry and compact multi-planet architectures
can shape the marginal period-ratio distribution. The registered test must
freeze the catalog inclusion predicate and null support before interpreting
any excess.

### 8.5 Verdict and statistical reading

Prediction 54 remains **registered and pending/invalid at the receipt level**,
not confirmed, rejected, or INDETERMINATE. The document retains the
multi-planet period-ratio design only. No matter-channel result or
cross-channel comparison is assigned. Tier stays **Hypothesized** until a
fresh, independently auditable run resolves the parser predicate, null
support, signal/control overlap, size-matched power calibration, and missing
raw/hash/run receipts.

---

## References

- `open-questions-cassi-answers.md`—C9 (cosmic web from wake-wave), G5 (3+1 dimensions)
- `predictions/falsifiable-predictions.md`—$\varphi$-periodic $P(k)$ prediction; Prediction 51/52; **Prediction 53** (disk-gap $\varphi$-ladder); **Prediction 54** (Kepler period-ratio)
- `foundations/bubble-edge-geometry.md` §3.1—the ring law (Derived conditional); §3.5—the negative result; §3.6—the two no-ring nulls
- `foundations/bubble-lattice-fabric.md` §3.2–3.3—nested sub-lattice, the ~1% nesting floor
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `principles/de-resonance-principle.md`—why orbital resonances lock to $\varphi$
- `foundations/qi-as-spatial-spacing-signal.md`—the channel principle: Qi is the spatial-spacing signal; disk gas is a coherence-coupled channel, detached orbital dynamics are not
- `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`—intended download and
  hash procedure for the DSHARP gap table; raw and parsed receipts are absent
- `experiments/dsharp_phi_gaps/stack_phi_gaps.py`—the pre-registered decision
  tree and null; its data and run output are absent
- Data: Andrews et al. 2018 (arXiv:1812.04040, DSHARP survey); Huang et al. 2018 (arXiv:1812.04041, annular substructures, Table `tab:ringpositions`)
- `experiments/kepler_phi_ratios/acquire_kepler_catalog.py`—intended download,
  archive-confirmation filtering, parse, and hash procedure; the raw receipt
  is absent
- `experiments/kepler_phi_ratios/run_phi_ratios.py`—registered decision tree
  and folded-window null; the run receipt and any power receipt are absent
- Data source intended: NASA Exoplanet Archive `ps` multi-planet catalog;
  no completed Kepler/K2/TESS result is retained
