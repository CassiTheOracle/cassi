# Void Radial Profiles and the Bubble-Shell Ring Ladder

## Status: Hypothesized—August 2026

## Abstract

Prediction 51 (`predictions/falsifiable-predictions.md`) forecasts that a
bubble shell of effective radius $R$ carries interior matter rings at
$r_k = R\,\varphi^{-k}$ with void troughs at
$R\,\varphi^{-(k+\frac12)}$ (`foundations/bubble-edge-geometry.md` §3.1):
successive matter rings are separated by $\varphi^{-1}=0.6180$, versus the
interleaved-null ratio $\varphi^{-1/2}=0.7862$
(`predictions/falsifiable-predictions.md` Prediction 51). This document
specifies a real-space extension using the Nadathur & Hotchkiss (2014) SDSS
DR7 void catalog (VizieR `J/MNRAS/440/1248`), but the real-data stack is
currently blocked.

No raw catalog blobs, SHA-256 manifest, parsed Type1-count receipt, or tracked
run JSON is retained in this checkout. The current
`experiments/void_phi_rings/stack_void_rings.py` is a synthetic detector and
power-calibration script: at most a catalog count sets the number of
independent profiles. It does not consume real void centers, effective radii,
survey masks, member-galaxy positions, random sky centers, or a real
same-density null. The profiles are count-only independent Poisson shells.

The real-galaxy stacking pre-registration therefore remains **pending**. No
measured ridge positions, significance values, power result, or real-data
verdict is assigned. The ratio windows and decision tree below are retained
as a protocol for a future receipt, not as an analysis outcome.

---

## 1. The Prediction in Real Space

Prediction 51 specifies a simulated bubble-shell ring ladder
(`foundations/bubble-edge-geometry.md` §3.1). This analysis defines a
real-space extension: stacked tracer-density profiles are tested for the same
matter-ring ratios under an explicitly Hypothesized galaxy-to-shell mapping.
The extension is conditional on the void selection, tracer catalogue, and
null construction described below.

For matter rings $r_k=R\,\varphi^{-k}$ and interleaved troughs
$r^{\mathrm{void}}_{k+1/2}=R\,\varphi^{-(k+1/2)}$, the comparison is

$$
\boxed{\frac{r_{k+1}}{r_k}=\varphi^{-1}=0.6180}
\qquad\text{versus}\qquad
\frac{r^{\mathrm{void}}_{k+1/2}}{r_k}=\varphi^{-1/2}=0.7862.
$$

In real void profiles only the first few interior ridges are resolvable:
void shells of at least $100$ Mpc and the survey's tracer density allow at
most a handful of $\varphi$-spaced rungs before shot noise and the
approximately $1\%$ contrast floor wash them out. The pre-registered question
is whether the stacked void radial profile shows a matter ridge near
$r=0.618R$ (and possibly $0.382R$) under this conditional mapping.

## 2. Data: The Void Catalog (real) and the Galaxy Field (blocked/synthetic)

### 2.1 Void catalog

The intended void-geometry source is the public **Nadathur & Hotchkiss
(2014)** SDSS DR7 catalog, VizieR `J/MNRAS/440/1248`. The acquisition script
(`experiments/void_phi_rings/acquire_void_catalog.py`) is the planned source
path, but this checkout retains no fetched raw tables, SHA-256 manifest, or
parsed count receipt. The citation and source description are therefore not a
currently verified catalog-integrity record.

The source table reports effective radii in comoving Mpc/h. The pending
pre-registration keeps those source units and normalizes each void by its own
$R$, so the planned comparison uses dimensionless $u=r/R$. No converted radius,
center, or catalog count enters the current synthetic claim.

### 2.2 The real-galaxy step is blocked—exact failures

The pre-registered stacking needs per-void galaxy positions. For the two
preferred public catalogs, that is not downloadable:

* **Pan et al. (2012)**, arXiv:1103.4156 (the product that bundles the
  8,046 void galaxies with membership): not published to VizieR (CDS
  returns "VizieR not found" for `J/MNRAS/421/926`, HTTP 404); the
  paper-linked institutional hosting at `www.physics.drexel.edu` is
  defunct (no void-catalog page reachable; the paper's own
  `www.physics.drexel.edu` anchor 404s).
* **Nadathur & Hotchkiss (2014)**: the downloadable CDS tables are described
  as carrying each void's *summary* (center, radius, densities), not the
  galaxy-member positions. The member lists are produced only by the
  auxiliary `postproc.py` in the full `cat_v11.11.13` package, which CDS does
  not mirror and which lives on the paywalled journal site.

Accordingly, the current synthetic stack does not consume real sky positions,
effective radii, survey-mask geometry, member coordinates, or random sky
centers. It has no real-data same-density null. The geometry and Type1 count
must remain unverified until raw/hash/count receipts are retained.

### 2.3 The synthetic $\varphi$-ladder field (the pivot)

The current `experiments/void_phi_rings/stack_void_rings.py` implements a
synthetic $\varphi$-ladder detector, not a real-catalog stack. Its planted
field is sampled as independent Poisson shell counts:

$$\ln n(u) \supset c\cos\!\bigl(2\pi\log_\varphi u\bigr), \qquad u=r/R,$$

whose ridges sit at $u=\varphi^{-k}$ and troughs at
$u=\varphi^{-(k+\frac12)}$. The synthetic null sets $c=0$ with the same
profile count, binning, and mean count. It has no catalog centers, catalog
radii, survey mask, member galaxies, or random-sky null; a count, if available,
only sets the number of independent profiles. The nominal script scale
$N_{\mathrm{mean}}=50{,}000$ is a toy Poisson parameter, not an observed
galaxy density. No synthetic output is a measurement of void data.

## 3. Stacking, Ridges, and the Pre-Registered Decision Tree

`experiments/void_phi_rings/stack_void_rings.py` is the current synthetic
detector and power-calibration implementation. The **pending real-data
pre-registration** specifies:

* bins galaxies in void-centric shells in units of each void's $R$,
  $u\in(0.12,3.0)$ in approximately $0.1$-wide $u$ bins;
* **ridge detection** in the shell interior $u\in(0.2,1.0]$—a bin is
  significant at $2\sigma$ against a future same-density masked-null band at
  that bin, and a ridge is the maximum of a contiguous run of significant
  bins (robust to a noisy deep-interior neighbour);
* **same-density masked null**: random centers drawn uniformly in the same
  masked footprint volume with the real $R$-distribution, stacked the same
  number of times and with the same binning, with no ladder; this is a planned
  real-data null, not the current synthetic null;
* a retained run JSON must record each outcome, including source hashes,
  source units, count, bin edges, ridge positions, null bands, ratios, and
  the decision-tree branch.

The pending decision tree is:

1. **Ridge selection**: local maxima in the shell interior
   $u\in(0.2,1.0]$ clearing the $2\sigma$ null band.
2. **Count**: $\ge3$ candidate ridges required to run the ratio test.
3. **Ratio test**: from the $\ge3$ ridges (innermost first), the two
   successive ratios $q_1=r_{(2)}/r_{(3)}$ and $q_2=r_{(1)}/r_{(2)}$
   (outer-normalized, equal to $\varphi^{-1}$ if the ladder holds):
   * **SUPPORTS**: every $q_i\in[0.6180\pm0.08]$ and outside
     $[0.7862\pm0.05]$;
   * **SUPPORTS NULL**: every $q_i\in[0.7862\pm0.05]$ and outside
     $[0.6180\pm0.08]$;
   * **INDETERMINATE**: otherwise.
4. **Verdict**: if fewer than three significant ridges are present, **NO
   RIDGES** (the null result, not null support); otherwise use Step 3.

No branch above has been measured on real void data. A pre-registration
refinement documented in the script docstring tightens the nominal core cut
from $r/R>0.1$ to $u>0.2$ because the resolvable rungs $(0.618,0.382)$ sit
above $0.2R$ and the deep interior has the smallest shell volume and worst
signal-to-noise.

### 4.1 Receipt status

No raw catalog blobs, SHA-256 manifest, parsed Type1-count receipt, or
tracked run JSON is present for a fiducial stack, a real-data null ensemble,
or a synthetic calibration. Any numerical table, significance statement, or
decision-tree branch would therefore be outside the current evidence record.
A future receipt must include fetched-table hashes, source units, void count,
bin edges, ridge positions, null bands, successive ratios, and the branch
label.

### 4.2 Current real-data state

The real-galaxy stacking step requires per-void galaxy coordinates and a
retained catalog receipt. Neither is available in the tracked inputs.
Consequently, the current record contains no real centers/radii receipt,
galaxy positions, survey mask, random-sky null, ridge positions, significance
values, ratio estimates, or real-data verdict.

### 4.3 Synthetic calibration state

The synthetic script is a count-only calibration arm made of independent
Poisson profiles. Its toy outputs, if generated, describe detector behavior
under the planted model and a same-count synthetic null; they are not measured
void profiles and do not provide a real-data verdict. No retained receipt
currently supports any reported synthetic frequency or power value. The
real-data pre-registration remains pending.


## 5. Verdict and Epistemic Tier

**Current analysis state:** the real-space extension remains **Hypothesized
and pending**. No raw/hash/count receipt establishes catalog integrity in this
checkout, and the synthetic stack is a count-only calibration of independent
profiles with no real centers, radii, masks, member coordinates, random-sky
null, or measured ridge. The galaxy-to-shell correspondence and null
comparison remain conditional model components.

The pipeline contract is the pre-registered decision tree: interior ridge
selection, a minimum of three candidate ridges, successive-ratio windows
around $\varphi^{-1}$ and $\varphi^{-1/2}$, and explicit outcomes for each
branch. A future receipt can support a ledger review; no measured verdict and
no quantity is assigned **Mapped** status at this stage.

## 6. Reproducibility

```bash
# 1. Download + hash-verify the Nadathur & Hotchkiss (2014) DR7 void catalog
python experiments/void_phi_rings/acquire_void_catalog.py
# 2. Stack, detect ridges, run the null + detection-power calibration
python experiments/void_phi_rings/stack_void_rings.py
```

Both scripts run from the repo root, require only NumPy, and write outputs
to `experiments/void_phi_rings/data/` (data files gitignored; scripts
tracked). A retained run JSON should be stored under
`experiments/void_phi_rings/data/runs/`.

## 7. What Would Make This a Real-Data Detection

A genuine stacking requires per-void galaxy coordinates and retained
raw/hash/count receipts. Acquisition paths include obtaining the Pan et al.
(2012) void-galaxy tables from the authors or an archive mirror, or
reconstructing the DR7 galaxy field (SDSS DR7 main-sample spectroscopy over the
NGC footprint) and matching it to a future verified center/radius table.
Whichever source is used, the full root-relative
`experiments/void_phi_rings/stack_void_rings.py` path consumes per-void
$(r_{\text{3d}},R)$ lists and reruns the registered tree. The resulting fit,
null band, and provenance would then receive a Fit-Status Ledger review before
any epistemic label changes.


## References

- `predictions/falsifiable-predictions.md`—Prediction 51 (bubble-shell
  ring ladder, PDE/simulated) and the catalog that Prediction 52 extends
- `foundations/bubble-edge-geometry.md` §3.1—the ring law
  $r_k = \ell_n\,\varphi^{-k}$; §3.5—the naive wake-sum comparison
- `foundations/bubble-lattice-fabric.md` §3.2–3.3—the nested sub-lattice
  and the approximately 1% nesting floor
- `experiments/void_phi_rings/acquire_void_catalog.py`—planned download,
  hash, and Table-2 cross-check of `J/MNRAS/440/1248`; no receipt is retained
- `experiments/void_phi_rings/stack_void_rings.py`—count-only synthetic
  calibration and the pending real-data decision tree
- `experiments/phi_periodic_pk_search/run_phi_periodic_pk_test.py`—the
  k-space φ-periodic P(k) cousin and its null/power discipline
- Data: Nadathur & Hotchkiss (2014), SDSS DR7 voids and superclusters,
  VizieR `J/MNRAS/440/1248` (cite `2014MNRAS.440.1248N`); Pan et al.
  (2012) blocked as described in §2.2 (arXiv:1103.4156)
