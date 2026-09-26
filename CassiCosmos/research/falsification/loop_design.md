# Live Falsification Loop: w₀/wₐ from the Cassi Space-Sim

*Design for the live survey → estimate → display loop. Companion to
`falsify_wo.py` (the Python estimator, both synthetic and survey paths).
This document is DESIGN ONLY for the sim-side hookup — `sim_ui.gd` and
`cassi_survey.gd` are owned by other workers and are referenced, not edited.*

---

## 1. Goal

Take the live Cassi two-fluid sim's `_field_ey` / `_field_ei` grids, compute a
single scalar **volume-averaged field ratio**

```
r = <EY> / <EI>
```

feed it through the theory's own w₀/wₐ estimator (the identical estimator in
`falsify_wo.py`), and display w₀, wₐ, and the distance to DESI DR2's
`w₀ = −0.838` on an on-screen meter.

This is a **live falsification loop**, not a demo meter: if the sim reaches the
calibrated φ-attractor, the theory *must* report w₀ within the DESI 1σ band;
if it reaches a different equilibrium, that is evidence against the theory's
claim that the field ratio self-organizes at φ.

---

## 2. The estimator (already implemented, both paths verified)

All physics lives in `research/falsification/falsify_wo.py`. It reimplements
verbatim the DESI calibration ODE from
`~/workspaces/physics/two-fluid/calibrate_initial_ratio.py` (the parent repo's
`cassi` package exports no cosmology ODE — verified — so this is the
authoritative source). The theory formulas, from
`papers/theory-of-everything/cosmology/cosmology-from-phi.md` §1:

```
H_empty = (λ/3) φ⁻²
H_conv  = (λ/3) (φ − r)(1 + r) / r
w(a)    = −1 − (2/3) d ln H / d ln a
```

and a CPL fit `(w₀, w_a)` of `w(a)` over the DESI window `a ∈ [0.3, 1.0]`.

The ODE `dr/dlna = λ · gate · (φ−r)(1+r) / H` is autonomous in `ln a` (only `r`),
so a **single survey snapshot** (one `r` at the sim's current state) is enough
to reconstruct the whole `r(a)` trajectory over the DESI window: anchor the
trajectory at the survey's `r` seen at `a = 1.0` (today), back-integrate to
`a = 0.3`. `falsify_wo.py._integrate_r` does exactly this (descending `t_span`
for the below-anchor segment, ascending for the above-anchor segment — no RHS
negation, since the ODE is genuinely autonomous in `ln a`).

### Gate status (from `falsify_wo.py`, both green)

- **G36 (synthetic, no sim):** forward-integrate from `a₀ = 0.01` over a grid of
  initial ratios `r₀ = <EY>/<EI>`; at the calibrated `r₀ = 0.0431934` (the
  bisection root from `calibrate_initial_ratio.py`), the estimator reports
  `w₀ = −0.8377`, i.e. **|w₀ − (−0.838)| = 0.0003 ≤ 5e-3** → PASS. Also prints
  `w_a = +0.4378` (within DESI's `−0.06 ± 0.68`).
- **G37 (survey path):** loads a synthetic dump in `survey_read.py` format
  (`field_ey.raw` / `field_ei.raw` float32 LE `grid_N³` grids + `meta.json`
  extents), volume-averages `r`, anchors and reconstructs the trajectory, and
  reports a finite `w₀` with a meaningful distance to DESI → PASS. **The gate is
  *pipeline correctness*, not "matches DESI".** Seeded at the calibrated
  today-value `r(a=1) = 1.5892`, it reconstructs `w₀ = −0.8391` (within 0.001 of
  −0.838), which is the honesty check that the survey path has correct physics,
  not merely "prints a number".

---

## 3. Live loop architecture

### 3.1 Cadence

The sim-side exporter already exists: `scripts/cassi_survey.gd` writes a
`survey_<timestamp>/` directory with `field_ey.raw`, `field_ei.raw`,
`meta.json` at a **default 10 s wall-clock cadence** (`survey_interval_seconds`).
It reads the RD buffers directly, and **every dump is a full-grid readback that
stalls the global RenderingDevice** — documented in that file's header. So the
live loop must NOT lower the cadence into the sub-second range in a live/render
loop. The falsification pipeline only needs ~1 dump per 10 s.

**Loop (design):**
1. `cassi_survey.gd` (already present, unchanged) writes `survey_<ts>/` every 10 s.
2. A small Python watcher (or a polled step) calls
   `falsify_wo.py --survey <latest>` for each new dump → `(w₀, w_a, r, |Δw₀|)`.
3. A meter on screen shows the latest estimate.

Because the Python estimator is a pure function of the dump's `r`, the meter
only needs `(r, w₀, w_a, |Δw₀|)` — a handful of floats over IPC (file or
watcher), re-computed every 10 s. The heavy numpy work is ~0.4 s per dump
(measured), well inside the cadence.

### 3.2 On-screen meter (DESIGN ONLY — `sim_ui.gd` is another worker's)

`sim_ui.gd` already has an `_info_label` / `_diag_label` pattern and updates
status strings at ~2 Hz (`_process` guards on `_update_info()`). The meter is a
small addition in that style: a plain `Label` (or a `PanelContainer` + `Label`)
reading, refreshed each survey tick when a new dump lands:

```
w₀ = -0.838   w_a = +0.438
r  = <EY>/<EI> = 1.589   (φ = 1.618)
Δw₀ vs DESI = +0.000   [WITHIN 1σ]
```

The verdict shown is the same honesty rule as `falsify_wo.py`: until the sim
sits at the calibrated attractor, the meter should read a state like
`r ≠ 1.59 — still relaxing to φ-attractor; estimate not yet meaningful` rather
than a false "PASS". The exact widget ownership stays with the `sim_ui.gd`
worker; the falsification contract the meter must honor is:
- show the raw `r`, `w₀`, `w_a`, `|Δw₀|`;
- never claim agreement until the relax-to-attractor test (below) passes.

### 3.3 Hookup location (later, out of scope for this wave)

The sim-side hookup lives in the intersection of `cassi_survey.gd` (dump writer,
already present) and `sim_ui.gd` (meter). For THIS Python-only wave, the
deliverable is the estimator + this design; the actual GDScript meter wiring is
left to the owner workers, consuming the interface specified above (a file per
dump + a floats-only IPC for the meter). No GDScript is touched here.

---

## 4. Honest statistics: how many dumps / how much sim time

The estimator is not the hard part — the **statistical question is how long
`r` must be measured until the w₀ estimate is meaningful.** Two distinct
requirements:

### 4.1 The r-attractor must be reached (qualitatively)

The whole falsification claim is that the two-fluid *self-organizes to the
φ-attractor*, and the DESI calibration is the point on that attractor
`r(a=1) ≈ 1.5892` (from the calibrated trajectory). The ODE shows the flow near
the attractor is fast in e-folds: `dr/dlna ≈ 0.09–0.2` at `r ∈ [1.5, 1.6]`,
`|r − φ| ≈ 0.03` at `a = 1`. But that is the homogeneous-ODE rate, **not** the
sim's PDE relaxation (the sim has gradients, diffusion, gravity, structure —
`cassi_sim.gd` is a full 3-D PDE with `grid_N = 64`, not a single ODE). The
honest statement: *how many wall-clock sim seconds it takes for the volume-mean
r to stop drifting and sit near 1.589 cannot be derived from the ODE alone — it
must be measured live.* The loop treats "attractor reached" as an **empirical
trigger**: `r` stable (drift over several consecutive dumps below the resolution
threshold) AND `|r − 1.589|` small. Until then the estimate is not falsifiable.

### 4.2 Sensitivity sets the r-measurement precision

Numerically (recomputed here for the doc, same estimator):
```
dw₀/dr ≈ −6.1   (at the calibrated today-r)
⇒ to resolve w₀ to the DESI 1σ half-width (Δw₀ = 0.068), the
  volume-averaged r must be measured to  Δr ≈ 0.068/6.1 ≈ 0.011.
```
So the requirement is: **measure the volume-mean `r` to ±0.011.** Each dump is
a full-`grid_N³` readback (64³ = 262k cells of `ey` and `ei`), so a single dump
gives a very well-sampled spatial mean — but the sim is not homogeneous; real
structure makes the per-dump `r` fluctuate about the true mean. The per-dump
standard deviation `σ_r` is unknown until the live sim runs. Averaging `N`
independent dumps (10 s apart) reduces the mean's error to `σ_r/√N`, so:

```
N ≥ (σ_r / 0.011)²  dumps
sim time ≳ N × 10 s   (at the default cadence)
```

A concrete worked example: if a live run's per-dump `r` scatter is `σ_r = 0.05`
(plausible for a structured 64³ box), then `N ≈ (0.05/0.011)² ≈ 21` dumps
≈ **210 s ≈ 3.5 min of sim time** just for the r-mean to settle to the 1σ
precision — *after* the attractor itself is reached. That is the honest
ballpark; it is deliberately stated as a function of the unknown `σ_r`, because
fabricating a fixed number would be dishonest. The loop measures `σ_r` from the
first ~20 dumps and then computes the actual `N`.

---

## 5. Falsification logic (a real falsifier, not a demo meter)

The claim under test is **parameter-free**: `w₀ = −0.838` is not fitted in the
sim; it is the DESI DR2 measurement, and the theory's *prediction* is that the
sim's φ-attractor reproduces it. So the decision rule is:

| Observation (after attractor reached, N dumps) | Verdict |
|---|---|
| `|w₀ − (−0.838)| ≤ 0.068` (DESI 1σ) | **AGREEMENT** — theory self-validates; report `w₀`, `w_a`, band. |
| `0.068 < |w₀ − (−0.838)| ≤ 0.136` (2σ) | **MARGINAL/INCONCLUSIVE** — keep sampling; not yet falsified. |
| `|w₀ − (−0.838)| > 0.136` (2σ) | **FALSIFIED (at 2σ)** — the sim reached a field equilibrium whose cosmic expansion disagrees with DESI. |
| `r` never settles / drifts (no attractor) | **FALSIFIED** — the theory's core claim (φ-attractor reached) fails. |

**What a "wrong" w₀ would MEAN for the theory** — this is what makes it a real
falsifier, not a demo:

1. **`w₀` —DESI⇒ while `r` sits near φ (1.62):** the φ-attractor is reached but
   the CPL intercept disagrees. That would falsify the *specific* claim that
   `r(a=1) ≈ 1.589` (the assignment of today to the calibrated trajectory point).
   Either the calibration's `H_conv` formula is wrong, or the sim's field-mean
   maps to a different cosmic time than the ODE's `a`.
2. **`r` —>φ (relaxes to 1.618, the attractor) but `w₀ → −1`:** a sim sitting
   exactly on the φ-attractor with minimal conversion would show near-`ΛCDM`
   w₀ = −1 — *not* −0.838. That would falsify the claim that the observed
   dark-energy deviation (−0.838) is *caused by* the still-active conversion
   channel at today's `r = 1.589 ≠ φ`. This is the sharpest falsifier: it
   requires the sim to stop *at* the calibrated point, not relax all the way
   to φ — the theory needs `r` frozen at 1.589 at today, with the residual
   conversion producing the −0.838 deviation.
3. **`w_a` wildly outside DESI's `−0.06 ± 0.68`** while `w₀` matches: would
   indicate the trajectory's *shape* (the `dr/dlna` flow toward φ) disagrees
   with data even if the intercept is right — a subtler but real falsification
   of the `H_conv(r)` form.

**Honest caveat (must be explicit):** the current gates verify the *pipeline*,
not the theory. Until the live sim demonstrably reaches the calibrated attractor
(§4.1), a non-DESI `w₀` from a live dump is **not** a falsification — it simply
means the sim has not yet relaxed. The meter and the loop design must therefore
*gate* the verdict on the attractor-reached test; only then does a 2σ miss carry
falsification weight.

---

## 6. File layout (this wave, Python-only)

```
research/falsification/
  falsify_wo.py        # the estimator (synthetic G36 + survey G37), verified
  loop_design.md       # this document (live-loop design, statistics, falsifier)
  _synthetic_survey/   # git-ignored synthetic dump for the G37 pipeline test
```

The `_synthetic_survey/` directory is generated by `falsify_wo.py
--make-synthetic` and is test data, not committed. GDScript wiring
(`sim_ui.gd` meter, `cassi_survey.gd` cadence) is future work owned by the
respective workers, per §3.3.
