# How the Infinite Bubble Lattice Enters DESI's Averaged Measurements

## Status: Hypothesized—July 2026

## Abstract

DESI averages galaxy clustering over roughly 20 (Gpc/h)$^3$ of the visible universe. The Cassi bubble lattice is infinite, periodic, and anisotropic—its cell structure at rungs $n \approx 283$–$291$ spans exactly the scales DESI measures. The question is which lattice structure survives the light-cone average and which is washed out. The answer, worked out quantitatively here:

1. **The distance channel washes out.** A fixed-scale lattice wiggle in $D_A(z)$/H$(z)$ is suppressed by the line-of-sight integral and by shell averaging (a redshift bin spanning $\gtrsim 3$ cells retains ≲ 10% of the amplitude). The physically realized distance wiggle is $\lesssim 0.1\%$; even a pathological 1% wiggle biases the CPL fit by ≲ 0.1 in $w_a$—sub-σ for DESI. Closing the $2.7\sigma$ $w_a$ gap would require $\delta D/D \gtrsim 20\%$. **The lattice cannot rescue the tension—the $w_0 = -0.87$/$w_a = +0.012$ verdict of `cosmology/observational_constraints.md` §6 stands.**
2. **The power-spectrum channel survives.** The angle-averaged lattice is a powder-diffraction comb: lines at zero-parameter positions $k/k_0 \in \{1, \sqrt{2}, \varphi, \sqrt{1+\varphi^2}, 2, \ldots\}$ with predicted multiplicities. Lattice nesting makes the inter-rung comb exactly log-periodic with period $\ln\varphi$—the established wake-wave prediction is the first pair of this comb, now with a fixed multiplicity structure attached.
3. **The anisotropy channel survives partially.** The cell is triaxial ($\ell_n, \ell_n/\varphi, \ell_n$), so line amplitudes are direction-dependent: the monopole ratio $A(\varphi k_0)/A(k_0) = 1/2$ (single-rung) and the $\mu$-dependence of the comb is predicted given the bubble axis ($l, b = 260°, +60°$, `cosmology/observational_constraints.md` §4).
4. **The variance channel inverts.** A deterministic lattice suppresses mean-density sample variance ~10× relative to Gaussian-random mocks and makes NGC–SGC large-scale modes *correlated* in a way mocks do not predict.

A first test on the DESI LRG monopole (`experiments/desi_pk_phi_search/desi_lrg_n_pk.txt`): the predicted first pair $(k_0, \varphi k_0)$ fits with amplitude $A = 2.6\%$ in $\ln P$ and a line width matching the FKP window ($\sigma_k \approx 0.0023$ h/Mpc $= 2\pi/L_{\rm survey}$)—but the improvement over the smooth broadband is not significant ($p = 0.08$, phase-shifted null) and a free-position fit does not select the predicted scale. **Consistent with the predicted 1–3% amplitude; not a detection.**

---

## 1. The Lattice at DESI Scales

The condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$ (`foundations/bubble-lattice-fabric.md`) organizes every cascade rung into a 3D staggered checkerboard with three orthogonal periods:

| Axis | Period at rung $n$ |
|---|---|
| $x$ (Yang, normal) | $\lambda_Y = \ell_n$ |
| $y$ (Yin, binormal) | $\lambda_I = \ell_n/\varphi$ |
| $z$ (string, tangent) | $P_\parallel \ell_n = \ell_n$ (cosmological $P_\parallel = 1$) |

At the cosmological rungs the cells span exactly the survey's scales (computed from $\ell_n = \ell_{\rm Pl}\varphi^n$):

| Rung | $\lambda_Y$ (Mpc) | $\lambda_I$ (Mpc) | Structure |
|---|---|---|---|
| 284 | 117.9 | 72.9 | Yin wake of rung 285; old "BAO ~120 Mpc" label |
| **285** | **190.8** | **117.9** | Cassi bubble |
| 286 | 308.8 | 190.8 |—|
| 287 | 499.6 | 308.8 |—|
| 288 | 808.4 | 499.6 | Supercluster scale |
| 290 | 2116 | 1308 | Horizon at recombination |
| 292 | 5541 | 3424 | Hubble radius |

DESI's comoving range (z ∈ [0.1, 2.1], out to ~3.4 Gpc) crosses ~18 rung-285 cells along the line of sight and contains ~$10^3$ of them in volume; the survey side length (≈ 2.7 Gpc) spans 1–3 rung-288 cells. The lattice is *nested*: every rung-$n$ cell contains the full sub-lattice of rungs $n-1, n-2, \ldots$ (`foundations/bubble-lattice-fabric.md` §3.2), so DESI's power spectrum carries the superposition of rungs ~283–291.

---

## 2. The Angle-Averaged Spectrum: Powder Lines

The density field of a single-rung lattice is a sum of plane waves at reciprocal-lattice vectors $G = 2\pi(h/\ell_n, j\varphi/\ell_n, m/\ell_n)$. A survey that averages over many cells and all sky directions measures the *powder pattern*: the angle average is a comb of lines at $k = |G|$ with multiplicities. For the rung-285 lattice ($k_0 = 2\pi/190.8$ Mpc $= 0.03293$ h/Mpc):

$$\boxed{\begin{array}{c|c|c} k/k_0 & |G| & \text{multiplicity} \\ \hline 1.000 & (1,0,0),(0,0,1) & 4 \\ 1.414 & (1,0,\pm1) & 4 \\ 1.618 & (0,1,0) & 2 \\ 1.902 & (1,\pm1,0) & 8 \\ 2.000 & (2,0,0) \ldots & 4 \\ 2.149 & (1,\pm1,1) & 8 \\ 2.236 & (2,0,\pm1) & 8 \\ \ldots \end{array}}$$

Two structural identities follow:

**Intra-rung pair.** The first two lines sit at $k_0$ and $\varphi k_0$—a pair separated by exactly $\ln\varphi$ in $\ln k$. The established wake-wave prediction $\Delta(\ln k) = \ln\varphi$ (`predictions/falsifiable-predictions.md` §3) is the *first pair of this comb*, with the zero-parameter amplitude ratio $A(\varphi k_0)/A(k_0) = 2/4 = 1/2$ in the single-rung limit.

**Inter-rung comb.** Nesting makes the Yin line of rung $n$ land on the fundamental of rung $n-1$ ($\lambda_I^{(n)} = \ell_n/\varphi = \ell_{n-1}$). The fully nested lattice is therefore a log-periodic comb of period $\ln\varphi$ with *equal* effective multiplicity per line (6 per line when adjacent rungs contribute equally). The wake-wave prediction is thus *derived from nesting*, and the single-rung 4:2 asymmetry is the discriminating test between one dominant rung and a fully nested lattice. The higher lines ($\sqrt{2}$, $\sqrt{1+\varphi^2}$, 2, $\sqrt{5}$, …) are new, testable content beyond the existing single-period search.

The line width is set by the survey window, $\sigma_k \sim 2\pi/L_{\rm survey} \approx 0.0023$ h/Mpc for DESI's ~2.7 Gpc extent—narrow compared to the inter-line spacing ($\Delta k/k = \varphi - 1 = 0.618$), so the comb survives window smearing.

---

## 3. The BAO Ruler at the Half-Step

The measured sound horizon sits between the two cells, not on either:

$$\boxed{n(r_d) = \frac{\ln(r_d/\ell_{\rm Pl})}{\ln\varphi} = 284.46 \approx 284.5, \qquad r_d \approx \sqrt{\ell_{284}\,\ell_{285}} = \ell_{\rm Pl}\,\varphi^{284.5} = 150.0\ \text{Mpc}}$$

against the DESI/Planck value $r_d = 147.1 \pm 0.26$ Mpc—a +1.98% offset (11σ, so a near-miss rather than a match, but a structural anchor within 2%). The older ladder label "step 284 ≈ BAO ~120 Mpc" (`foundations/dimensionful-cascade.md` §3) is actually the Yin wavelength $\lambda_I^{(285)} = 117.9$ Mpc; the measured ruler sits at the geometric-mean cell of the (284, 285) pair. Note $r_d/\lambda_I^{(285)} = 1.248 \approx \varphi^{1/2}$ to within 2%: the half-step is the natural reading of the ladder at the BAO scale.

---

## 4. The Distance Channel: the Average Washes the Lattice Out

DESI's expansion-history measurements ($D_A(z)$, H$(z)$ via BAO and RSD) average along the line of sight and over redshift shells. A coherent lattice wiggle in the distance field, $\delta D/D = A\cos(2\pi D/\ell + \phi)$, is suppressed twice:

1. **LOS integral.** The cumulative distance to a shell is an integral of $1 + \delta$ over the path; a periodic wiggle cancels to $O(\ell/D)$: $\delta D/D \sim (f/3)\,A_\delta\,\ell/(2\pi D) \sim 0.07\%$ for the rung-285 lattice at $D \sim 1.4$ Gpc with $A_\delta = 6.3\%$ (the ΛCDM rms at 190.8 Mpc, $\sigma = 0.8\,(8/190.8)^{0.8}$).
2. **Shell average.** A redshift bin of width $\Delta D$ retains the fraction $|\operatorname{sinc}(\pi\,\Delta D/\ell)|$ of the wiggle. For DESI's $\Delta z = 0.1$ bins: retention is 5–20% at $\ell \lesssim 310$ Mpc and up to 74–85% only at $\ell = 808$ Mpc (rung 288)—but the rung-288 lattice's own density amplitude is ~2%, and its LOS-integral suppression applies the same way.

The full CPL-fit simulation (fit $w(a) = w_0 + w_a(1-a)$ at fixed $\Omega_m = 0.31$, DESI-like bins z ∈ [0.1, 2.1], $\sigma_{D_A} = 0.5\%$) gives, for a 1% amplitude wiggle:

| $\ell$ (Mpc) | max $\lvert\Delta w_0\rvert$ | max $\lvert\Delta w_a\rvert$ |
|---|---|---|
| 117.9 | 0.003 | 0.002 |
| 190.8 | 0.021 | 0.114 |
| 308.8 | 0.001 | 0.005 |
| 499.6 | 0.021 | 0.121 |
| 808.4 | 0.060 | 0.316 |

(max over phase; the physically realized $\delta D/D$ is ~0.07%, fifteen times smaller, so all entries drop to ≲ 0.01.) A log-periodic wiggle of any fixed amplitude behaves similarly: $A = 1\%$ biases $w_a$ by ≲ 0.16. The amplitude needed to shift $w_a$ by the full DESI offset of −0.74 is $\delta D/D \gtrsim 20\%$—ruled out by DESI's own smooth $D_A(z)$ measurements to well below 1%.

$$\boxed{\text{The bubble lattice cannot bias the CPL fit into the DESI region. The } 2\sigma\ (w_0) \text{ / } 2.7\sigma\ (w_a) \text{ tension is not a lattice-averaging artifact.}}$$

---

## 5. The Power-Spectrum Channel: the Comb Survives

The monopole $P(k)$ keeps the lattice: lines sit at fixed comoving wavenumbers (the lattice is comoving), so the comb is coherent across redshift bins, and window smearing (~0.002 h/Mpc) is narrower than the line spacing. The zero-parameter statement is the §2 comb; the amplitude is set by the condensation threshold at these rungs (calibrated phenomenologically, `foundations/bubble-lattice-fabric.md` §8.2) and by the wake mechanism, whose prediction is 1–3% (`predictions/falsifiable-predictions.md` §3).

**First test on DESI LRG data** (`experiments/desi_pk_phi_search/desi_lrg_n_pk.txt`, real DESI LRG_N FKP monopole, 41 bins over $k \in [0.008, 0.25]$ h/Mpc): residuals around a degree-5 broadband in $\ln P$ were fit with the predicted first pair at fixed positions $(k_0, \varphi k_0)$ with fixed 4:2 multiplicities:

- Best-fit amplitude $A = 2.6\%$ in $\ln P$; best-fit line width $\sigma_k = 0.0023$ h/Mpc—*matching the FKP window scale* $2\pi/L_{\rm survey}$;
- $\Delta$SSE = +0.009 vs the smooth broadband, $p = 0.08$ against a phase-shifted null (500 draws, spectrum-preserving)—**not significant**;
- A free-position fit runs to a single-bin spike at $k_0 = 0.042$ h/Mpc (27% off the prediction): the data do not select the predicted scale.

The bound is $A \lesssim 2.6\%$ (1σ-ish) at the predicted positions—consistent with the wake-mechanism forecast of 1–3%, and with a lattice whose lines are smeared by nonlinearity and the window, but not a detection. The discriminating upgrade is the multiplicity ratio: a *fully nested* comb (equal lines, period $\ln\varphi$) versus a *single-rung* comb (4:2 ratios) can be separated with Euclid-class precision, where the predicted amplitude is >5σ reachable.

---

## 6. The Anisotropy Channel: Footprint and Multipoles

The cell is triaxial ($\ell_n, \ell_n/\varphi, \ell_n$), so the comb is anisotropic: the $k_0$ line lives on the $x$/$z$ axes, the $\varphi k_0$ line only on $y$. Under a global lattice orientation the angle-averaged multiplicities 4:2 become direction-dependent:

- **$P(k, \mu)$ sees a $\mu$-dependent comb amplitude.** Along the string axis the fundamental line dominates; transverse, the Yin line does. Given the bubble axis ($l, b) = (260°, +60°)$ (`cosmology/observational_constraints.md` §4.2, itself ~1σ suggestive), the ratio of comb amplitudes along and across the axis is fully predicted—zero additional parameters.
- **NGC vs SGC.** Two disjoint footprints on the same lattice see the *same* lines with different effective multiplicities (the axis is not centered on either footprint), producing a measurable NGC–SGC difference in the residual comb that a Gaussian random field would not show.
- **Bulk flows.** The anisotropic lattice drags coherent velocity structure along the axis—the §4.2 bulk-flow prediction (500–2000 km/s at Gpc scales) is the kinematic face of the same geometry.
- **Void edges.** The same triaxiality is the 1.70× boundary-steepness anisotropy (`foundations/bubble-lattice-fabric.md` §4.2): void boundary profiles should show the axial:diagonal slope ratio, already in the catalog (`predictions/falsifiable-predictions.md` §3, §8).

If bubble orientations instead decohere into domains below the survey scale, the anisotropy washes out and only the monopole comb (§5) survives—itself a testable fork.

---

## 7. The Variance Channel: Deterministic Instead of Random

Standard analyses treat the large-scale field as a Gaussian random realization; the lattice is a *deterministic* field. The consequences for the survey average:

- **Mean-density bias.** A periodic lattice sampled by a box of $M$ cells per side has a mean-density error bounded by $A_\delta/(2\pi M)$ (worst phase remainder): ≤ 0.13% at DESI survey scale ($M = 14.4$ for $\ell = 190.8$ Mpc), versus a Gaussian σ of 0.75–1.3%. The lattice suppresses the k → 0 sample variance by **~10×**.
- **Deterministic scatter.** The measured mean is biased by a *fixed* phase remainder, not scattered: repeated patches (NGC vs SGC, independent redshift shells) trace the same lattice, so their large-scale modes are more correlated than mock ensembles (which draw independent Gaussian initial conditions) predict. This is testable directly against DESI's mock catalogs (EZmocks, AbacusSummit): the scatter of $P(k)$ across the four lowest-$k$ bins, and the NGC–SGC mode correlation, are predicted to be smaller than the mock ensemble spread.
- **Error bars become conservative.** Under the lattice, DESI's large-scale ($k \lesssim 0.03$ h/Mpc) error budget from mocks overestimates the true variance—the reverse of the usual worry.

---

## 8. Synthesis

| Channel | Survives the average? | Prediction | Status |
|---|---|---|---|
| $D_A(z)$, H$(z)$ (CPL fit) | No—washed out | $\delta D/D \lesssim 0.1\%$; no $w_0/w_a$ bias | Consistent; lattice cannot explain the 2.7σ tension |
| $P(k)$ monopole | Yes | Comb at $k/k_0 \in \{1, \sqrt{2}, \varphi, \ldots\}$, period $\ln\varphi$, 1–3% amplitude | DESI LRG: $A \lesssim 2.6\%$, $p = 0.08$—consistent, undetected |
| Anisotropy (multipoles, NGC–SGC) | Partially | $\mu$-dependent comb given the axis; NGC–SGC line mismatch; 1.70× void edges | Untested; Simons Obs./DESI void catalogs |
| Sample variance | Inverted | ~10× suppression; NGC–SGC correlation | Testable with DESI mocks |

---

## 9. Epistemic Boundaries

**Derived (formal consequences of the PDE + ladder).** The powder line positions and multiplicities (§2); the half-step BAO identity $r_d \leftrightarrow \ell_{284.5}$ (§3); the LOS-integral and shell-average washout and the CPL-bias bounds (§4); the variance-suppression arithmetic (§7). These follow from the condensation field, scale covariance, and $\ell_n = \ell_{\rm Pl}\varphi^n$ without new parameters.

**Hypothesized (structural identifications, verification pending).** That the observed cosmic web *is* the bubble lattice at rungs 283–291 (rather than Gaussian-random structure); the 1–3% comb amplitude (wake mechanism, $\theta_{\rm cond}$ calibrated); a global lattice orientation tied to the CMB axis; the NGC–SGC correlation claim.

**Data.** The DESI LRG monopole bound $A \lesssim 2.6\%$ at the predicted positions ($p = 0.08$; no detection).

---

## 10. Open Questions

1. **What sets the comb amplitude per rung?** The condensation threshold $\theta_{\rm cond}$ at cosmological rungs is calibrated, not derived; a derivation would turn the 1–3% forecast into a prediction with an error bar.
2. **Single-rung vs nested comb?** The 4:2 multiplicity ratio discriminates; the nested (equal-multiplicity) version is the scale-covariant default.
3. **Is the lattice orientation global?** The CMB axis is ~1σ suggestive; a global orientation makes §6's anisotropy predictions live, a domain structure kills them.
4. **Does the lattice survive nonlinearity?** Structure formation at $\sigma(190.8\ \text{Mpc}) = 6\%$ is quasi-linear; the line widths and harmonics after nonlinear evolution need N-body-scale verification.

---

## References

- `foundations/bubble-lattice-fabric.md`—condensation field, triaxial periods, nesting, edge anisotropy
- `foundations/dimensionful-cascade.md`—rung table, wake-wave mechanism, §6 Cassi bubble
- `cosmology/observational_constraints.md`—DESI DR2 comparison (§1, §6) and CMB axis (§4)
- `predictions/falsifiable-predictions.md`—φ-periodic $P(k)$ row and catalog entries
- `experiments/desi_pk_phi_search/desi_lrg_n_pk.txt`—DESI LRG_N FKP monopole used in §5
- `experiments/desi_pk_phi_search/desi_lrg_pk_fft.py`—monopole pipeline
- `foundations/bubble-edge-geometry.md`—condensation field derivation, $P_\parallel = 1$ at cosmological scale
- `predictions/cassi_definitions.md`—glossary
