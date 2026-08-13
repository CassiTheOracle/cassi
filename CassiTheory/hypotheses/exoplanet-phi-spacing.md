# Exoplanet Orbital Spacing from the Wake-Wave Mechanism

## Status: Hypothesized—August 2026

## Abstract

The Titius-Bode "law" for solar system planetary spacing ($a \propto 1.7^n$) uses
a progression factor tantalizingly close to $\varphi \approx 1.618$. In the Cassi
framework, this is not a coincidence—it is the same $\varphi$-scaled structure
that organizes the condensation field at every cascade scale: the bubble-shell
ring ladder (`foundations/bubble-edge-geometry.md` §3.1) that produces
$\varphi$-spaced matter rings in the cosmic web
(`open-questions-cassi-answers.md`—C9) and log-periodic modulation in the
matter power spectrum (`predictions/falsifiable-predictions.md` §3). In a
protoplanetary disk, the condensation wake plays the bubble shell: the density
nodes (the future disk gaps) sit at $\varphi$-spaced radii, i.e. successive
gaps at the ratio $\varphi^{-1} = 0.6180$ against the interleaved null
$\varphi^{-1/2} = 0.7862$. This predicts (a) a statistical excess of
adjacent-planet period ratios at $\varphi$ and its Fibonacci convergents in the
Kepler/TESS multi-planet catalog—a zero-parameter, falsifiable test using
existing data—and (b) a $\varphi$-spacing of the annular gaps in resolved
protoplanetary disks. The disk-gap branch (b) is now a tested, registered
prediction: the pooled successive-gap ratio distribution of the ALMA DSHARP
survey shows the signal-window excess.

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
  is realized from microphysics is not established. Two honest no-ring nulls
  are on record: the canonical solver's four-arm dynamic probe
  (`two-fluid/run_bubble_ring_dynamic_probe.py`—**NO RINGS** on all arms to
  $t=40$) and the space-sim second-order wave-form readback
  (`diag_bubble_rings.gd`—**NO RIDGES**, transient shell with one interior
  ridge at ratio 0.545, dissipated by $t=40$). The ladder is kinematic; its
  dynamical realization in a disk is open, and the same caveat applies to the
  disk-gap reading.
- **The period-ratio prediction** $P_{\text{out}}/P_{\text{in}} =
  \varphi^{3/2} \approx 2.06$ (verified arithmetic) is unchanged and remains a
  legitimate zero-parameter statistical test on the Kepler/TESS catalog (§3).
- **Disk-gap branch now measured.** The ALMA DSHARP pooled successive-gap
  ratio test (Prediction 53) ran on real data (2026-08-13) and returned
  **SUPPORTS** at the pre-registered 2$\sigma$ threshold (§7): 10 of 22 pooled
  successive ratios land in the signal window $[0.6180 \pm 0.08]$ vs 3.5
  expected under the log-uniform null (3.86$\sigma$), with the null window
  $[0.7862 \pm 0.05]$ at baseline (4 vs 4.2). Detection power 100% at
  $\sigma_{\ln r} \le 0.15$, 93.5% at 0.2.
- **Solar-system fit (unchanged).** The geometric mean of the doc's own six
  adjacent-planet ratios is 1.66; the set is dominated by the 3.42 Mars/Jupiter
  jump. The $\varphi$-fit's mean $|\ln a|$ deviation is 0.193 as slotted and
  0.088 after a post-hoc remap, vs Titius-Bode's 0.084—comparable at best,
  not better.

Tier stays **Hypothesized**: the disk-gap prediction is statistically
supported in the pooled sample, but the mechanism step (ring-ladder $\to$
$\varphi$-spaced gaps in a real disk) remains open—the dynamical realization
is not established, planet-carving is the standard alternative, and the
pooled statistical excess is not a per-disk signature.

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
at period ratios like 2:1, 3:2, 5:3) sculpt planetary spacing through
gravitational interactions. In Cassi, these resonances ARE the Fibonacci
convergents of $\varphi$—the de-resonance attractor in orbital frequency
space—and their ubiquity is a consequence of the disk's Qi field seeking
$\varphi$-equilibrium.

## 2. The Ring Ladder in Protoplanetary Disks

The disk mechanism is the bubble-shell ring ladder (`foundations/bubble-edge-geometry.md`
§3.1). A condensation shell of effective radius $R$ carries interior matter
rings at

$$\boxed{r_k = R\,\varphi^{-k}, \qquad k = 0, 1, 2, \ldots}$$

and void troughs at $R\,\varphi^{-(k+\frac12)}$, so successive matter rings are
separated by the fixed ratio $\varphi^{-1} = 0.6180$ and each matter ring is
trailed inward by its void at $\varphi^{-1/2} = 0.7862$. The ladder is the
doublet's radial phase $\alpha = \pi u$, $u = \log_\varphi(r/\ell_n)$
(phase-quantized, *not* a beat); the honest negative—the naive one-dimensional
wake-sum $\cos(2\pi r/\ell_n) + \cos(2\pi\varphi r/\ell_n)$ has zeros at
$\{0.191, 0.573, 0.809, 0.955\}\,\ell_n$, not a $\varphi$-ladder—is documented
in `foundations/bubble-edge-geometry.md` §3.5.

In a protoplanetary disk the condensation wake plays the bubble shell: the
radial substructure—the annular gaps resolved by ALMA at millimeter
wavelengths—sits at $\varphi$-spaced radii, with successive gap ratios
$\varphi^{-1} = 0.6180$ against the interleaved-null ratio $\varphi^{-1/2} =
0.7862$. (The disk is not a static bubble shell: a gap is a deep radial
intensity minimum carved into the disk, and the Cassi ladder supplies a
$\varphi$-spaced template for where the substructure sits, not the 
depletion mechanics itself.) Planetesimal and planet formation proceeds
preferentially at/around these radial loci: the enhanced local density promotes
gravitational instability, and the $\varphi$-resonant locations reduce
disruptive tidal shear. The result: planets form at $\varphi$-spaced orbital
radii, and the gaps they carve in the disk carry the same ladder.

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
$\ln a$: 0.193 as slotted (Mercury→slot 0 through Neptune→slot 8, with Saturn
34% off and slot 7 matching nothing), or 0.088 after a post-hoc remap
(Uranus→slot 8, Neptune→slot 9, slot 7 dropped). Titius-Bode's own mean
$|\ln a|$ deviation is 0.084 — so the $\varphi$-fit is comparable at best
after the remap and worse without it; it is not "better than" Titius-Bode,
and the remap is chosen after the fact.

## 5. Falsifiable Tests

1. **Kepler period ratio excess at $\varphi^{3/2}$:** The distribution of
   adjacent-planet period ratios from the Kepler multi-planet catalog should
   show a peak at $P_{\text{out}}/P_{\text{in}} \approx 2.06$. Testable with
   existing public data (NASA Exoplanet Archive). Untested here.

2. **Resonance selectivity:** Fibonacci-convergent resonances (2:1, 3:2, 5:3,
   8:5) should be more common than non-Fibonacci resonances at similar period
   ratios. The 4:3 resonance (not a Fibonacci convergent) should be
   underrepresented after controlling for detection bias. Untested here.

3. **Log-periodic $\varphi$-spacing in disk gaps (tested).** The ring/gap
   locations of ALMA-resolved protoplanetary disks should show
   $\varphi$-spacing in $\ln r$: successive gap ratios $\varphi^{-1} =
   0.618$ vs the null $\varphi^{-1/2} = 0.786$. The DSHARP survey of 18
   single-disk systems is tested in §7 (Prediction 53). Verdict on the real
   data: **SUPPORTS** at the pooled level (signal-window excess 3.86$\sigma$
   vs the log-uniform null), with the caveats in §6.

4. **No period ratio at exactly $\varphi$ for single-disk systems:** The
   $\varphi$ spacing is an attractor, meaning any individual system may
   deviate due to migration and scattering. The prediction is statistical—an
   excess in a large sample, not an exact fit for each system.

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
  positions from the survey's annular-substructure table
  (`tab:ringpositions`, Huang et al. 2018, arXiv:1812.04041; the survey is
  Andrews et al. 2018, arXiv:1812.04040). Data acquisition, provenance and
  hashes in `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py` and
  `data/raw/sha256.txt`.
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
  single-disk systems). Annular substructure table:
  Huang et al. 2018 (arXiv:1812.04041), Table `tab:ringpositions`.
- **Acquisition:** the two e-print sources downloaded over HTTPS; SHA-256
  recorded (`data/raw/sha256.txt`). The gap table was machine-parsed from the
  paper's LaTeX source, so every value is extracted rather than re-typed.
  Only the **DARK ("D")** substructures—the gaps—enter the test.
- **Sample:** 40 gaps across the 18 single-disk systems (the appended
  comparison disks TW Hya and HL Tau are excluded from the primary pool and
  reported separately). 11 disks have $\ge 2$ gaps, giving **22 pooled
  successive ratios**. Gap positions carry the published uncertainties; about
  a third are low-precision visual (`~`) estimates, many in the inner disk
  near the resolution limit.

Per-disk gap counts and positions are in
`experiments/dsharp_phi_gaps/data/parsed/dsharp_gaps.csv` (gitignored).

### 7.3 Results

Pooled successive-gap ratios (22): 0.208, 0.267, 0.365, 0.431, 0.432, 0.556,
0.576, 0.596, 0.638, 0.641, 0.667, 0.673, 0.676, 0.680, 0.693, 0.721, 0.722,
0.755, 0.760, 0.770, 0.784, 0.852.

| quantity | value |
|---|---|
| Pooled successive ratios | 22 (11 disks) |
| $N_1$ in $W_1 = [0.538, 0.698]$ | **10** |
| Null mean $E_1$, std $s_1$ | 3.51, 1.68 |
| Signal-window significance | **3.86$\sigma$** |
| $N_2$ in $W_2 = [0.736, 0.836]$ | 4 |
| Null mean $E_2$, std $s_2$ | 4.19, 1.83 |
| Null-window significance | −0.10$\sigma$ (baseline) |
| **Verdict (pre-registered)** | **SUPPORTS** |

### 7.4 Per-disk verdicts (statistical, not per-disk)

| disk | successive ratios | windows |
|---|---|---|
| AS 209 | 0.365, 0.680, 0.576, 0.676, 0.852, 0.770 | 3 in $W_1$, 1 in $W_2$—INDETERMINATE |
| DoAr 25 | 0.755, 0.784 | 0, 2—NULL |
| Elias 20 | 0.760 | 0, 1—NULL |
| Elias 24 | 0.638 | 1, 0—SUPPORTED |
| GW Lup | 0.721 | 0, 0—INDETERMINATE |
| HD 142666 | 0.432, 0.673 | 1, 0—SUPPORTED |
| HD 143006 | 0.431 | 0, 0—INDETERMINATE |
| HD 163296 | 0.208, 0.556, 0.596 | 2, 0—SUPPORTED |
| MY Lup | 0.267 | 0, 0—INDETERMINATE |
| RU Lup | 0.667, 0.722, 0.693 | 2, 0—SUPPORTED |
| Sz 129 | 0.641 | 1, 0—SUPPORTED |

### 7.5 Detection power and sensitivity

- **Detection power:** a planted synthetic $\varphi$-ladder of gaps (successive
  ratio $\varphi^{-1}$, anchored at each disk's outermost observed gap) is
  recovered by the decision tree in 100% of realizations at log-normal scatter
  $\sigma_{\ln r} \le 0.15$ and 93.5% at 0.2 (200 realizations per step). The
  pipeline would detect a genuine $\varphi$-ladder at this sample size.
- **Sensitivity (exclude visual `~` gaps):** 17 pooled ratios, $N_1 = 7$ vs
  null $E_1 = 2.62$ (2.93$\sigma$), $N_2 = 3$ vs $E_2 = 3.06$ (baseline).
  Verdict SUPPORTS is robust but weaker on the high-precision subset.

### 7.6 Verdict and honest reading

The pre-registered decision tree on the real ALMA data returns **SUPPORTS**:
the pooled successive-gap ratios are concentrated in the signal window
$[0.6180 \pm 0.08]$ (10/22 vs 3.5 expected, 3.86$\sigma$) and separated from
the null window $[0.7862 \pm 0.05]$ (4/22 vs 4.2 expected, baseline).
Detection power is high, and the result survives on the high-precision
subset.

The honest reading is a **statistical, population-level SUPPORTS**, not a
per-disk or mechanism-level detection:

- The pooled ratios span 0.208–0.852; the signal is an excess near the
  signal window, not a tight ladder in any single disk (per-disk verdicts are
  mixed: 5 SUPPORTED, 2 NULL, 4 INDETERMINATE among the 11 multi-gap disks).
- The disk is not a static bubble shell: gap radii carry uncertainties, gaps
  have widths, and several published positions are low-precision visual
  estimates near the resolution limit (some inner gaps below ~20 au).
- Planet-carving is the standard alternative explanation: single planets in
  low-viscosity disks can open several gaps whose spacing is set by disk-planet
  dynamics, not the ring ladder.
- The ladder's dynamical realization in a disk is open (the two no-ring
  nulls in Origin Status).

Tier stays **Hypothesized**. The test is registered as
**Prediction 53** (`predictions/falsifiable-predictions.md`), alongside
Prediction 51 (the bubble-shell ladder) and Prediction 52 (the void radial
profiles).

---

## References

- `open-questions-cassi-answers.md`—C9 (cosmic web from wake-wave), G5 (3+1 dimensions)
- `predictions/falsifiable-predictions.md`—$\varphi$-periodic $P(k)$ prediction; Prediction 51/52; **Prediction 53** (disk-gap $\varphi$-ladder)
- `foundations/bubble-edge-geometry.md` §3.1—the ring law (Derived conditional); §3.5—the honest negative; §3.6—the two no-ring nulls
- `foundations/bubble-lattice-fabric.md` §3.2–3.3—nested sub-lattice, the ~1% nesting floor
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `principles/de-resonance-principle.md`—why orbital resonances lock to $\varphi$
- `experiments/dsharp_phi_gaps/acquire_dsharp_gaps.py`—download + hash + parse of the DSHARP gap table
- `experiments/dsharp_phi_gaps/stack_phi_gaps.py`—the pre-registered decision tree, null, detection power (run JSON `experiments/dsharp_phi_gaps/data/runs/<id>_gaps.json`)
- Data: Andrews et al. 2018 (arXiv:1812.04040, DSHARP survey); Huang et al. 2018 (arXiv:1812.04041, annular substructures, Table `tab:ringpositions`)
