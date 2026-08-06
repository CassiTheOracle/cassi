# GWTC-4.0 and the Cascade Ladder: Black-Hole Masses as Rung Diagnostics

## Status: Speculative—August 2026

## Abstract

The fourth gravitational-wave transient catalog (GWTC-4.0) more than doubles the census of compact-binary mergers, to 218 events with $p_{\text{astro}} \ge 0.5$. This document runs the new catalog through the framework's only derived mass-to-rung relation—the black-hole coherence-capacity rung $N_{\text{BH}} = \log_\varphi(M/M_{\text{Pl}})$ from `gravity/quantum-gravity.md` §7.5—and maps the population peaks, the mass-gap edges, and the headline events onto the cascade ladder. The stellar-black-hole zone ($n \approx 182$–$194$) is unmapped territory: the ladder has no claims there between the rung-185 and rung-200 anchors. The observed primary-mass peaks (10, $\sim$20, 35 M$_\odot$ at rungs 186.4, 187.9, 189.0) do **not** form an integer-rung grid—the spacings are 1.44 and 1.16 rungs—and a full-posterior search over all 173 catalog events with proper measurement uncertainties confirms this: no significant comb at the predicted period ln $\varphi$ ($\Delta\ln L = +1.9$ vs a null median of +12.8, p ≈ 1.0), a marginal rung-fraction excess (p ≈ 0.02) worth tracking with GWTC-5, and no periodicity at any other period. The catalog also supplies the first high-loudness test of the framework's GR-exact ringdown prediction The catalog also supplies the first high-loudness test of the framework's GR-exact ringdown prediction: the loudest event ever recorded, GW230814_230901, shows a ringdown hint that the collaboration judges statistically insignificant—consistent with the framework so far, and a falsifier if it survives corroboration.

---

## 1. The Catalog in One Paragraph

GWTC-4.0 covers observations through January 2024 (O4a) and brings the total to 218 confident events—more than double the first three runs combined [1, 2]. The new data strengthen the population findings: primary-mass peaks near 10 and 35 M$_\odot$ with a possible third near 20 M$_\odot$; broadly distributed neutron-star masses; a merger rate that increases with redshift; and a widening of the effective spin distribution with redshift [3]. Two events set records. GW231123_135430 is the most massive binary black hole with a low false-alarm rate—total mass $M = 236^{+29}_{-48}$ M$_\odot$, with a component above the pair-instability gap at 94% credibility, high spins, and waveform-model systematics that complicate interpretation [4]. GW230814_230901 is the loudest gravitational-wave signal ever recorded (SNR 42.1, above GW170817's 32.4), a modest 33.6 + 28.3 M$_\odot$ merger seen by a single detector, with a potential—statistically insignificant—deviation from general relativity in the ringdown [5].

## 2. The Rung Map

Every claim in this document uses one derived relation: the number of accessible cascade rungs of a black hole of mass $M$ is

$$\boxed{N_{\text{BH}} = \log_\varphi\!\left(\frac{M}{M_{\text{Pl}}}\right)}$$

derived in `gravity/quantum-gravity.md` §7.5 as the coherence capacity of the interior two-fluid condensate ($M_\odot \to N_{\text{BH}} \approx 180$ rungs; exact value 181.6). Applying it to GWTC-4.0 places the entire stellar-black-hole population in an unmapped band of the ladder:

| Quantity | Mass | Rung $N_{\text{BH}}$ |
|---|---|---|
| Chandrasekhar mass | 1.4 M$_\odot$ | 182.3 |
| Max NS mass (EOS limit) | $\sim$2.5 M$_\odot$ | 183.6 |
| Lower mass gap edge | $\sim$5 M$_\odot$ | **185.0** |
| m$_1$ peak | 10 M$_\odot$ | 186.4 |
| m$_1$ peak | $\sim$20 M$_\odot$ | 187.9 |
| m$_1$ peak | 35 M$_\odot$ | **189.0** |
| GW230814_230901 total | 61.8 M$_\odot$ | 190.2 |
| Pair-instability edge | $\sim$130 M$_\odot$ | 191.8 |
| GW231123 total | 236 M$_\odot$ | **193.0** |

The zone $n \approx 182$–$194$ sits between the two nearest ladder anchors—rung 185 (Mt Everest, 8.8 km) and rung 200 (Earth diameter)—with no framework claims of any kind. The mass-ladder interpretation developed below is therefore a **new hypothesis**, not an application of an existing one. (Script: `experiments/gwtc4_mass_ladder/gwtc4_mass_ladder.py`—rung mapping, verification block, figure.)

## 3. Test 1: Do the Mass Peaks Sit at Integer Rungs?—Posterior Search

The question this catalog makes answerable: if black-hole formation freezes out at activated cascade rungs, the merger-rate peaks should cluster at $\varphi$-spaced masses, i.e. at integer rung separations $\Delta N_{\text{BH}} = k$ (equivalently $\Delta\ln m = k\ln\varphi$).

### 3.1 Face value (peak positions)

The three peaks sit at rungs 186.4, 187.9 and 189.0: spacings of 1.44 and 1.16 rungs (mass ratios 2.0 and 1.75), neither 1 nor 2. The 10 M$_\odot$ peak is 0.43 rungs from the nearest integer. A $\varphi$-grid anchored at the 35 M$_\odot$ peak predicts further peaks at 21.6, 13.4 and 8.3 M$_\odot$; the observed $\sim$20 M$_\odot$ peak is within about one sigma of 21.6, but the 10 M$_\odot$ peak matches neither 13.4 nor 8.3. Three coincidences are worth recording anyway: the 35 M$_\odot$ peak lands at rung 189.03 (0.03 off), the GW231123 total mass at rung 193.00 exactly (90% CI 188–265 M$_\odot$ spanning rungs 192.5–193.2), and the lower mass-gap edge $\sim$5 M$_\odot$ at rung 185.0.

### 3.2 The posterior search (this analysis)

To test the comb hypothesis against the full measurement uncertainties, all high-purity posteriors in the catalog were downloaded and analyzed: **173 events** (84 from O4a, 54 from the GWTC-2.1 v2 release covering O1+O2+O3a, 36 from GWTC-3; 5.06M posterior samples of source-frame $m_1$ from the equal-weight waveform mixtures; md5-verified against the LVK release checksums). The three NS/BNS events without a Mixed group (GW230518, GW230529, GW190425) are excluded—all below the 2 M$_\odot$ analysis floor.

The search (`experiments/gwtc4_mass_ladder/phi_mass_search.py`):

- **Models** on $m_1 \in [2, 200]$ M$_\odot$: M0 = power law + three linear-mass Gaussians (the FullPop-4.0-style structure at 10/20/35); M1 = M0 × (1 + $A\cos 2\pi n$) with the period **fixed at ln $\varphi$** (ψ=0); M1ψ = same with free phase; M2 = free period $T$.
- **Likelihood**: $L_i(\Lambda) = \langle p(m_1|\Lambda)\rangle$ over each event's posterior samples—an unbiased importance estimator for $\int p(d_i|m_1)p(m_1|\Lambda)\,dm_1$ for any positive reference prior, so no PE-prior reconstruction is needed. All densities are properly normalized on the analysis range (log-grid Jacobian included).
- **Significance**: 60 fully synthetic mock catalogs drawn from the fitted M0 (true masses from M0×VT, $VT \propto m^{1.5}$, with real posterior shapes transplanted) are refit with the same machinery, giving null distributions for every statistic. Selection enters through smooth $VT(m)$ only; the comb is nearly orthogonal to any smooth envelope (bracket quoted below).

### 3.3 Results

| model | $k$ | $\Delta\ln L$ vs M0 | $\Delta$BIC |
|---|---|---|---|
| M0 smooth (3 bumps) | 10 | 0 | 0 |
| M1 comb @ ln $\varphi$ (ψ=0) | 11 | +1.93 | +1.3 |
| M1ψ comb @ ln $\varphi$ (ψ free) | 12 | +1.93 | +6.4 |
| M2 comb (free period) | 13 | +9.36 | −3.3 |

M1's best fit is $A = +0.77$ at the predicted phase (ψ → 0 when freed), and the M0 baseline finds the LVK's 10 M$_\odot$ peak at 10.8 M$_\odot$—but the comb gain is **small compared with what M0 fluctuations produce**: under the null, $\Delta\ln L$(M1−M0) has median +12.8 (95% +17.8), so the observed +1.93 gives $p \approx 1.0$. The free-period M2 gain (+9.36 at $T \approx 1.4$ rungs, mass ratio 1.93—the 10→20→35 spacing) is also *below* the M2 null median (+14.8), $p = 0.82$: the apparent $T \approx 1.4$ preference is exactly what smooth-model fluctuations produce, not a new periodicity. The selection bracket is ±(0.3–0.5) on $\Delta\ln L$ at the fitted amplitude, far below the null widths.

The one marginal result is the rung-fraction statistic: the event-weighted excess of posterior mass within $|n \bmod 1| < 0.15$ of integer rungs is $S(1) = +0.156$, against an M0 null median of +0.140, $p \approx 0.02$ (0/60 mocks exceeded it). Interpreted alone, a 15.6% excess of posterior weight near integer rungs is a weak hint; with the other statistics null (p = 0.5–1.0) and the multiple-testing caveat, it is **not** a detection. It is the one number from this analysis worth rechecking with GWTC-5's larger catalog [8].

### 3.4 Verdict

**No significant comb at the predicted period ln $\varphi$ in the full-catalog posteriors.** The face-value rung positions (186.4/187.9/189.0) survive the full measurement-uncertainty treatment: the 10 M$_\odot$ peak is 0.4 rungs off the integer grid at high significance, and the 10→20→35 spacing is not an integer number of rungs. The integer-rung mass ladder is **Hypothesized, disfavored at current sensitivity**; the marginal rung-fraction excess (p ≈ 0.02) is the only feature worth carrying forward, and the GWTC-5 posterior set (released Spring 2026 [8]) is the decisive dataset.

## 4. Test 2: Ringdown—The Framework Predicts GR, and the Loudest Event Agrees

The framework's effective gravity at compact-object densities is unmodified: the halo parameterization $q = 1/(1 + (\rho/\rho_{\text{ref}})^2)$ drives $q \to 0$ at nuclear and horizon densities, so $G_{\text{eff}} = (\pi/\rho)(1+(\varphi^{6}-1)q)G \to (\pi/\rho)G$, unamplified (GR-like) (`cosmology/observational_constraints.md` §2.6), and the σ-regularized running of $G$ is below 1% even at the Planck scale (`gravity/quantum-gravity.md` §5.3). The prediction is therefore **GR-exact ringdown frequencies** for a given remnant mass and spin: no mass-shift, no frequency-shift, no anomalous damping.

GW230814_230901—the loudest event ever recorded, SNR 42.1—is precisely the event that could break this. Its single-detector analysis found a potential ringdown deviation that the collaboration explicitly could not separate from statistical noise and could not corroborate with a second facility [5]. Consistent with the framework so far; **if the deviation survives with corroborated detections, it falsifies the current $q$-density dependence** (the branch $q \to 1$ at high density, or a nonzero compact-density enhancement, would be required instead). This is a clean, binary falsifier and the most valuable contact point between GWTC-4.0 and the framework.

## 5. Test 3: Halo Strain—No New Evidence, a Doubled Sample

The framework's unique gravitational-wave signature is enhanced strain from mergers inside Qi halos: $h_{\text{Cassi}} = (\pi/\rho)(1+(\varphi^{6}-1)q)\,h_{\text{GR}}$, up to $\sim$10$\times$ in cluster halos (prediction 17, `predictions/falsifiable-predictions.md` §4; `experiments/cassi_physics/cassi_gravitational_waves.py`). LIGO cluster non-detections already bound $q < 0.1$–$0.3$ at cluster scales. GWTC-4.0 reports no cluster-localized O4a merger with anomalous loudness, so the bound stands—now over a doubled event sample, which tightens the sensitivity of the next dedicated cluster search. Also untested by this catalog: the breathing-mode polarization prediction (prediction 29), since the loudest events were single-detector.

## 6. What the Framework Cannot Say (Yet)

Three strengthened population results have no framework counterpart and must not be retrofitted casually:

- **Merger rate increasing with redshift**—the framework's cosmology has gate engagement at $z \sim 19$ and wake-wave structure formation, but no merger-rate prediction; the rate-redshift relation is a test for the future, not a consistency check.
- **Spin-distribution width increasing with redshift**—spin in the framework is SO(2) doublet winding (`foundations/spin-fibonacci-spiral.md`); nothing predicts its population evolution.
- **Broad neutron-star mass distribution**—the Cassi NS model (`experiments/cassi_physics/cassi_neutron_stars.py`) predicts a modified TOV mass-radius relation, not a population distribution. Its one sharp, testable statement—a lower maximum NS mass than GR for the same EOS, from the $G_{\text{eff}}$ enhancement in the outer layers—is unquantified in the docs and should be quantified before being compared to the catalog's NS-BH events (GW230529_181500, GW230518_125908).

## 7. Epistemic Summary

| Claim | Tier | Status after GWTC-4.0 |
|---|---|---|
| $N_{\text{BH}} = \log_\varphi(M/M_{\text{Pl}})$ | Derived | Unaffected (used as mapping) |
| Stellar-BH zone rungs 182–194 | Hypothesized (new) | Unmapped territory; first data map |
| Integer-rung mass peaks | Speculative (new) | **Tested on full posteriors (173 events): no comb at ln $\varphi$ (p ≈ 1.0); marginal rung-fraction excess (p ≈ 0.02) to track with GWTC-5** |
| GR-exact ringdown | Derived (from $q\to0$ at compact density) | Consistent; GW230814_230901 hint insignificant; binary falsifier if confirmed |
| Halo strain $\le$10$\times$ (pred. 17) | Hypothesized | No new cluster mergers; bound stands over doubled sample |
| Breathing-mode polarization (pred. 29) | Hypothesized | Untested (single-detector loud events) |
| Rate-$z$, spin-width-$z$, NS mass spread |—| No framework prediction; do not retrofit |

---

## 8. GWTC-5 Recheck (Blocked on Data, 2026-08-06)

The integer-rung peak test is to be re-run on GWTC-5 (O4b). The recheck is
blocked on data acquisition, not on code: the existing
`experiments/gwtc4_mass_ladder/extract_samples.py` and
`experiments/gwtc4_mass_ladder/phi_mass_search.py` run unchanged once the
posterior samples are available.

Acquisition path: IGWN GWTC-5.0 PE data release—DOI
10.5281/zenodo.20348005 (part 1, ~46.4 GB; part 2 = 10.5281/zenodo.20348006),
one `IGWN-GWTC5p0-29ebe06b7_25-GW*-combined_PEDataRelease.hdf5` per O4b
event (FAR < 1/yr).

---

## References

- `gravity/quantum-gravity.md` §7.5—coherence-capacity rungs $N_{\text{BH}}$
- `foundations/dimensionful-cascade.md`—the 292-step ladder and its anchors
- `predictions/falsifiable-predictions.md` §4—GW predictions 17 and 29
- `cosmology/observational_constraints.md` §2.6—halo $q$ parameterization
- `experiments/cassi_physics/cassi_gravitational_waves.py`—strain-enhancement model
- `experiments/cassi_physics/cassi_neutron_stars.py`—modified TOV
- `experiments/phi_periodic_pk_search/phi_periodic_pk_search.py`—log-periodic search pipeline to reuse
- `experiments/gwtc4_mass_ladder/gwtc4_mass_ladder.py`—rung mapping, verification block, figure
- `experiments/gwtc4_mass_ladder/extract_samples.py`—posterior extraction from the LVK releases
- `experiments/gwtc4_mass_ladder/phi_mass_search.py`—the φ-periodic mass search (models, bootstrap null)
- `experiments/gwtc4_mass_ladder/phi_mass_figure.py`—result figure (PNG gitignored)
- Data: GWTC-4.0 PE release (zenodo 17602505), GWTC-2.1 v2 (zenodo 6513631), GWTC-3 (zenodo 8177023); posteriors via [9]
- [1] AAS Nova roundup, 2026-07-29: https://aasnova.org/2026/07/29/monthly-roundup-the-fourth-catalog-of-gravitational-wave-events-from-ligo-virgo-and-kagra/
- [2] GWTC-4.0 catalog paper, arXiv:2508.18082, doi:10.3847/2041-8213/ae2c74
- [3] GWTC-4.0 population properties, doi:10.3847/2041-8213/ae771e
- [4] GW231123, doi:10.3847/2041-8213/ae0c9c
- [5] GW230814, doi:10.3847/2041-8213/ae2ad3
- [8] GWTC-5.0 release, 2026-05-26: https://www.ligo.caltech.edu/news/ligo20260526
- [9] Gravitational Wave Open Science Center: https://gwosc.org/
