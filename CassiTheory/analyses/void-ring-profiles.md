# Void Radial Profiles and the Bubble-Shell Ring Ladder

## Status: Hypothesized—August 2026

## Abstract

Prediction 51 (`predictions/falsifiable-predictions.md`) forecasts that a
bubble shell of effective radius $R$ carries interior matter rings at
$r_k = R\,\varphi^{-k}$ with void troughs at $R\,\varphi^{-(k+\frac12)}$
(`foundations/bubble-edge-geometry.md` §3.5): successive matter rings are
separated by $\varphi^{-1} = 0.6180$, versus the interleaved-null ratio
$\varphi^{-1/2} = 0.7862$ (`predictions/falsifiable-predictions.md`
Prediction 51). This document runs the real-space cousin of that prediction
through a stacked void radial-profile test, using the public Nadathur &
Hotchkiss (2014) SDSS DR7 void catalog (VizieR `J/MNRAS/440/1248`,
hash-verified, per-sample Type1 counts reproduce the paper's Table 2
exactly: 808 Type1 voids).

The real-galaxy stacking step is **blocked at the data layer**: neither
preferred public catalog bundles per-void galaxy-member coordinates in a
downloadable form (Pan et al. 2012 is not on VizieR and its Drexel hosting
is defunct; the Nadathur CDS tables carry only per-void summaries, with
member-galaxy lists reachable only through the paywalled journal
supplementary). The void geometry exercised here is therefore real, while
the tracer galaxy field is the pre-registered synthetic φ-ladder pivot
built on the real centers and radii. The pipeline (stacking in units of each
void's effective radius, ridge detection in the shell interior, the
same-density masked-null, and the planted-signal detection-power
calibration) is the commit of this work and is ready to consume a real
per-void galaxy table unmodified.

The pre-registered decision tree runs on the synthetic field. At the
framework's expected 1% contrast floor the pipeline detects the ladder:
ridges at $r/R = \{0.377, 0.583, 0.994\}$ give successive ratios
$\{0.586, 0.647\}$—both inside the signal window
$[0.6180 \pm 0.08]$ and outside the null window $[0.7862 \pm 0.05]$—
verdict **SUPPORTS**, with a detection power of 62% at 1% (marginal), 100%
at 2–5%, and 0% at 0.3–0.5% against the same-density
null. Because no real galaxy data entered the stacking, this is a pipeline
calibration, **not** a detection in real void data: the tier is
**Hypothesized** until a per-void galaxy catalog is stacked.

---

## 1. The Prediction in Real Space

Prediction 51 is written for the two-fluid PDE realization of a single
bubble shell (`foundations/bubble-edge-geometry.md` §3.5; the honest
negative—the naive wake-sum is not the ladder—is documented there). The
real-space cousin is the identical ratio test read off **stacked void radial
galaxy-density profiles**: if a void's matter ring ladder survives
structure formation, the mean tracer density around many stacked voids
should show interior ridges at $r = R\,\varphi^{-k}$, i.e. at the successive
matter-ring ratio

$$\boxed{\frac{r_{k+1}}{r_k} = \varphi^{-1} = 0.6180}
\qquad\text{versus}\qquad
\frac{r^{\text{void}}_{k+1}}{r_k} = \varphi^{-1/2} = 0.7862.$$

In real void profiles only the first few interior ridges are resolvable
(the >100-Mpc void shells and the survey's tracer density allow at best a
handful of $\varphi$-spaced rungs before shot noise and the ~1% contrast
floor wash them out). The pre-registered question is deliberately narrow:
**does the stacked void radial profile show a matter ridge at
$r \approx 0.618\,R$ (and possibly $0.382\,R$), versus the $0.786$ null?**

## 2. Data: The Void Catalog (real) and the Galaxy Field (blocked/synthetic)

### 2.1 Void catalog

The void geometry is the public **Nadathur & Hotchkiss (2014)** SDSS DR7
catalog, VizieR `J/MNRAS/440/1248`
(`experiments/void_phi_rings/acquire_void_catalog.py` downloads all 16
tables over HTTPS from the CDS mirror as plain-text `asu-txt` responses and
records each raw blob's SHA-256 in
`experiments/void_phi_rings/data/raw/sha256.txt`).

**Authenticity and integrity**

* Catalog: SDSS DR7 voids and superclusters, Nadathur S., Hotchkiss S.,
  MNRAS 440, 1248 (2014), cite
  `2014MNRAS.440.1248N`.
* Raw-table hashes recorded (one per table, e.g. the `samples` table and
  the 15 void/cluster tables; run-to-run byte hashes differ because the
  CDS `asu-txt` response embeds a query-time stamp header, so the manifest
  is of the specific fetched bytes).
* Cross-check against the paper: per-sample **Type1** void counts from the
  parsed tables reproduce Table 2 of Nadathur & Hotchkiss (2014) exactly:
  bright1 = 262, bright2 = 112, dim1 = 80, dim2 = 271, lrgdim = 70,
  lrgbright = 13 (total **808 Type1 voids**). The stack uses Type1 voids
  only: the robust interior voids (not touching the survey boundary),
  which is the physically meaningful set for stacking interior rings.

Effective radii are the catalog's comoving Mpc/h values converted to
physical Mpc with $h = 0.6736$ so radii and comoving distances share one
unit system; the stacking normalizes every void by its own $R$, so the
cosmology enters only through the radial-shell volume and angular scale
(flat ΛCDM, Planck 2018; $D_C(z=0.1) = 434$ Mpc physical).

### 2.2 The real-galaxy step is blocked—exact failures

The pre-registered stacking needs per-void galaxy positions. For the two
preferred public catalogs, that is not downloadable:

* **Pan et al. (2012)**, arXiv:1103.4156 (the product that bundles the
  8,046 void galaxies with membership): not published to VizieR (CDS
  returns "VizieR not found" for `J/MNRAS/421/926`, HTTP 404); the
  paper-linked institutional hosting at `www.physics.drexel.edu` is
  defunct (no void-catalog page reachable; the paper's own
  `www.physics.drexel.edu` anchor 404s).
* **Nadathur & Hotchkiss (2014)**: the downloadable CDS tables carry each
  void's *summary* (center, radius, densities), **not** the galaxy-member
  positions. The member lists are produced only by the auxiliary
  `postproc.py` in the full `cat_v11.11.13` package, which CDS does not
  mirror (its `cat_files/*` entries are absent) and which lives on the
  paywalled journal site.

The void geometry is therefore real and verified; the tracer galaxy field
is the pre-registered synthetic φ-ladder pivot.

### 2.3 The synthetic φ-ladder field (the pivot)

A survey tracer field is built on the **real** Type1 void centers and radii
(footprint = the sample's RA/Dec/z slab with the $|b|>20°$ Galactic cut),
with a uniform mean density $n_0$ and, for each void, a log-periodic matter
modulation of amplitude $c$ (in ln-density, so $c = 0.01$ is a ~1%
contrast):

$$\ln n(u) \supset c\cos\!\bigl(2\pi \log_\varphi u\bigr), \qquad u = r/R,$$

whose ridges sit at $u = \varphi^{-k}$ (matter at $R$, $0.618\,R$,
$0.382\,R$, …) and troughs at $u = \varphi^{-(k+\frac12)}$. The no-ladder
($c=0$) field is the pre-registered uniform radial-density null on the
identical position grid. `stack_void_rings.py` stacks $n_0 = 50{,}000$
galaxies per void ($\approx 4\times10^7$ per stack), giving an
interior-rung stacked Poisson floor of ~0.4%, so the 1% expected floor
lands at the marginal threshold.

## 3. Stacking, Ridges, and the Pre-Registered Decision Tree

`experiments/void_phi_rings/stack_void_rings.py`:
* bins galaxies in void-centric shells in units of each void's $R$,
  $u \in (0.12, 3.0)$ in ~0.1-$\varphi$ bins;
* **ridge detection** in the shell interior $u \in (0.2, 1.0]$—a bin is
  significant at $2\sigma$ against the same-density null band at that bin,
  and a ridge is the maximum of a contiguous run of significant bins
  (robust to a noisy deep-interior neighbour);
* **same-density null**: random centers drawn uniformly in the same masked
  footprint volume with the real $R$-distribution, stacked the same number
  of times, same binning, no ladder; reported as a per-bin band and a
  distribution of profile-maxima ratios, never a single number.

The decision tree is pre-registered in the script docstring (written
before any analysis run) and reported in the run JSON:

1. **Ridge selection**: local maxima in the shell interior
   $u \in (0.2, 1.0]$ clearing the $2\sigma$ null band.
2. **Count**: $\ge 3$ candidate ridges required to run the ratio test.
3. **Ratio test**: from the $\ge 3$ ridges (innermost first) the two
   successive ratios $q_1 = r_{(2)}/r_{(3)}$ and $q_2 = r_{(1)}/r_{(2)}$
   (outer-normalized, equal to $\varphi^{-1}$ if the ladder holds):
   * **SUPPORTS**: every $q_i \in [0.6180 \pm 0.08]$ **and** outside
     $[0.7862 \pm 0.05]$;
   * **SUPPORTS NULL**: every $q_i \in [0.7862 \pm 0.05]$ **and** outside
     $[0.6180 \pm 0.08]$;
   * **INDETERMINATE**: otherwise.
4. **Verdict**: if $<3$ significant ridges, **NO RIDGES** (the honest
   outcome, not a null-support); else Step 3's verdict. Every outcome is
   reported.

A pre-registration refinement documented in the docstring: the nominal
core cut "$r/R > 0.1$" is tightened to $u > 0.2$ because the ring ladder's
resolvable rungs (0.618, 0.382) sit well above $0.2\,R$ and the deep
interior below $0.2\,R$ has the smallest shell volume and worst
signal-to-noise.

## 4. Results

### 4.1 The stacked profile table (run `runs/20260813_142511_rings.json`)

Fiducial run at the expected 1% contrast floor, 808 Type1 voids,
$n_0 = 50{,}000$ galaxies/void. Interior bins (density in arbitrary units
of stacked number density; null band = 16–84 percentile of the
same-density null):

| $r/R$ | density | null band (16–84%) | $r/R$ | density | null band (16–84%) |
|---:|---:|---|---:|---:|---:|
| 0.274 | 438.3 | [440.5, 444.8] | 0.789 | 437.6 | [441.5, 443.0] |
| 0.377 | **448.9** | [440.6, 443.0] | 0.891 | 442.3 | [441.5, 443.0] |
| 0.480 | 437.9 | [441.1, 442.8] | 0.994 | **445.6** | [441.5, 443.0] |
| 0.583 | **445.4** | [441.2, 443.0] | 1.097 | 443.9 | [441.9, 442.6] |
| 0.686 | 442.9 | [441.2, 442.9] | 1.200 | 439.1 | [441.6, 442.4] |

The three interior maxima at $0.377$, $0.583$, $0.994$ rise $3$–$4\sigma$
above their null bands; the troughs at $0.480$ and $0.789$ sit below the
null. Full per-bin profiles and null bands are in the run JSON.

### 4.2 Ridge ratios and the verdict

* Significant interior ridges (shell interior, $2\sigma$): $r/R =
  \{0.377,\,0.583,\,0.994\}$—the $k=2$ ($\varphi^{-2}$), $k=1$
  ($\varphi^{-1}$) and $k=0$ (wall, $\varphi^0$) matter rings within
  bin-centering bias.
* Successive ratios (outer-normalized, so equal to $\varphi^{-1}$ if the
  ladder holds): $q_1 = 0.583/0.994 = 0.586$, $q_2 = 0.377/0.583 = 0.647$.
  Both lie in the signal window $[0.538, 0.698]$ and outside the null
  window $[0.736, 0.836]$.
* **Verdict by the pre-registered tree: SUPPORTS** (for the planted
  ladder at 1%—a pipeline-calibration statement, see §5).

### 4.3 Same-density null and its maxima-ratio distribution

The null (random masked centers, no ladder, 40 realizations) yields a
median of **1** significant interior ridge per stack (range 0–3); it
essentially never produces the $\ge 3$ interior ridges the ratio test needs
(only 2 realizations reached $\ge 3$). Those few null successive-ratios
form a thin, broad distribution (observed ratios 0.55 and 0.69), and the
median-1 ridge count means the background-only field does **not** fabricate
the ladder's 3-ridge pattern. The comparison is a distribution, not a
single threshold.

### 4.4 Planted-signal detection power

Fractions of realizations (8 per contrast) in which the decision tree
returns SUPPORTS, at each planted contrast:

| contrast | detection power | reading |
|---:|---:|---|
| 0.3% | 0/8 (0%) | not detectable |
| 0.5% | 0/8 (0%) | not detectable |
| **1.0%** | **5/8 (62%)** | **hinted—marginal at the expected floor** |
| 2.0% | 8/8 (100%) | confirmed |
| 5.0% | 8/8 (100%) | confirmed |

At the framework's expected ~1% contrast floor the pipeline has ~60%
detection power (marginal): a real interior ring ladder at that amplitude
would be found only part of the time at the stacked shot-noise floor of
this analysis. At $\ge 2$% it is found with confidence; below 1% it is not.

## 5. Verdict and Honest Tier

**Pipeline verdict: SUPPORTS at the 1% floor, i.e. the pre-registered
pipeline recovers a φ-ladder interior ring pattern (ridges at
$\approx\varphi^{-2}, \varphi^{-1}, \varphi^0$ R with successive ratios at
$0.586$/$0.647$, both inside the signal window and outside the null) when a
1%-contrast φ-ladder is present.**

This is a **positive calibration of the detection pipeline**, not a
detection of rings in real void data. The real-galaxy stacking step is
blocked because no downloadable public catalog supplies per-void galaxy
positions for the preferred sources (Pan et al. 2012: not on VizieR and
Drexel hosting defunct; Nadathur & Hotchkiss CDS tables: per-void
summaries only). No real galaxy distribution was fitted, so nothing is
**Mapped** and the Fit-Status Ledger is untouched.

**Tier: Hypothesized.** The pipeline exists, is pre-registered, and is
calibrated against the synthetic pivot; the real-data verdict is pending
acquisition of a per-void galaxy catalog (the pipeline consumes one
unmodified). The prediction it implements is new in real space (the
k-space / PDE versions are Prediction 51's family) and is registered as
Prediction 52.

The pre-registered decision tree, written before any analysis run, is the
pipeline's contract: the fiducial verdict (SUPPORTS), the marginal power at
the 1% floor, and the NO RIDGES outcomes at subm-percent contrast are all
outputs of that fixed rule.

## 6. Reproducibility

```bash
# 1. Download + hash-verify the Nadathur & Hotchkiss (2014) DR7 void catalog
python experiments/void_phi_rings/acquire_void_catalog.py
# 2. Stack, detect ridges, run the null + detection-power calibration
python experiments/void_phi_rings/stack_void_rings.py
```

Both scripts run from the repo root, require only NumPy, and write outputs
to `experiments/void_phi_rings/data/` (data files gitignored; scripts
tracked). The run JSON is `experiments/void_phi_rings/data/runs/<id>_rings.json`.

## 7. What Would Make This a Real-Data Detection

A genuine stacking of per-void galaxy coordinates. The exact acquisition
paths: obtain Pan et al. (2012) void-galaxy tables from the authors or an
archive mirror, or reconstruct the DR7 galaxy field (SDSS DR7 main-sample
spectroscopy over the NGC footprint) and match it to the verified Nadathur
centers/radii downloaded here. Whichever source, the existing
`stack_void_rings.py` consumes per-void $(r_{\text{3d}}, R)$ lists
unchanged and re-runs the identical pre-registered tree. Publishing that
result would move this analysis from Hypothesized to Mapped (a fitted
real-data locus with its null band).

---

## References

- `predictions/falsifiable-predictions.md`—Prediction 51 (bubble-shell
  ring ladder, PDE/simulated) and the catalog that Prediction 52 extends
- `foundations/bubble-edge-geometry.md` §3.5—the ring law
  $r_k = \ell_n\,\varphi^{-k}$ and the honest negative (the naive
  wake-sum is not the ladder)
- `foundations/bubble-lattice-fabric.md` §3.2–3.3—nested sub-lattice,
  the ~1% nesting floor
- `experiments/void_phi_rings/acquire_void_catalog.py`—download +
  hash + Table-2 cross-check of `J/MNRAS/440/1248`
- `experiments/void_phi_rings/stack_void_rings.py`—stacking, ridge
  detection, pre-registered decision tree, same-density null,
  detection-power calibration
- `experiments/phi_periodic_pk_search/run_phi_periodic_pk_test.py`—the
  k-space φ-periodic P(k) cousin and its null/power discipline
- Data: Nadathur & Hotchkiss (2014), SDSS DR7 voids and superclusters,
  VizieR `J/MNRAS/440/1248` (cite `2014MNRAS.440.1248N`); Pan et al.
  (2012) blocked as described in §2.2 (arXiv:1103.4156)
