# GWTC-4.0 and the Cascade Ladder: Black-Hole Masses as Rung Diagnostics

## Status: Speculative—August 2026

## Abstract

The fourth gravitational-wave transient catalog (GWTC-4.0) more than doubles
the census of compact-binary mergers, to 218 events with
$p_{\text{astro}}\ge 0.5$. This document applies the conditional
mass-to-rung map, $N_{\mathrm{BH}}=\log_\varphi(M/M_{\mathrm{Pl}})$, to the
population peaks, mass-gap edges, and selected events. In this document the
map is a **Hypothesized information-storage proxy**, not a Derived
black-hole observable or validated mass coordinate. The stellar-black-hole
zone ($n\approx182$–$194$) is unmapped territory between the rung-185 and
rung-200 anchors. The executable posterior search has no retained posterior
input, checksum, or result receipt in this repository, so its numerical
outputs are unresolved and are not treated as a reproduced full-catalog
result. GW230814_230901 shows a ringdown hint that the collaboration judges
statistically insignificant; a corroborated deviation would constrain the open
strong-field model.

---

## 1. The Catalog in One Paragraph

GWTC-4.0 covers observations through January 2024 (O4a) and brings the total to 218 confident events—more than double the first three runs combined [1, 2]. The new data strengthen the population findings: primary-mass peaks near 10 and 35 $M_\odot$ with a possible third near 20 $M_\odot$; broadly distributed neutron-star masses; a merger rate that increases with redshift; and a widening of the effective spin distribution with redshift [3]. Two events set records. GW231123_135430 is the most massive binary black hole with a low false-alarm rate—total mass $M = 236^{+29}_{-48}\,M_\odot$, with a component above the pair-instability gap at 94% credibility, high spins, and waveform-model systematics that complicate interpretation [4]. GW230814_230901 is the loudest gravitational-wave signal ever recorded (SNR 42.1, above GW170817's 32.4), a $33.6\,M_\odot$ merger seen by a single detector, with a potential statistically insignificant deviation from general relativity in the ringdown [5].

---


## 2. The Rung Map

The analysis uses the following conditional map, stated in `gravity/quantum-gravity.md` §7.5:

$$\boxed{N_{\mathrm{BH}} = \log_\varphi\!\left(\frac{M}{M_{\mathrm{Pl}}}\right)}$$

The source presents this capacity result within its Hypothesized
quantum-gravity programme as an **information-storage proxy**; it is not a
Derived black-hole observable or a validated mass coordinate. The solar-mass
value is $N_{\mathrm{BH}}\approx180$ rungs (the displayed calculation gives
181.6). Applying the map to GWTC-4.0 is therefore an exploratory conditional
comparison:

| Quantity | Mass | Rung $N_{\mathrm{BH}}$ |
|---|---|---|
| Chandrasekhar mass | $1.4\,M_\odot$ | 182.3 |
| Conditional toy NS output (no EOS baseline) | $\sim2.5\,M_\odot$ | 183.6 |
| Lower mass gap edge | $\sim5\,M_\odot$ | **185.0** |
| $m_1$ peak | $10\,M_\odot$ | 186.4 |
| $m_1$ peak | $\sim20\,M_\odot$ | 187.9 |
| $m_1$ peak | $35\,M_\odot$ | **189.0** |
| GW230814_230901 total | $61.8\,M_\odot$ | 190.2 |
| Pair-instability edge | $\sim130\,M_\odot$ | 191.8 |
| GW231123 total | $236\,M_\odot$ | **193.0** |

The zone $n\approx182$–$194$ sits between the two nearest ladder
anchors—rung 185 (Mt Everest, 8.8 km) and rung 200 (Earth diameter)—with no
framework claims of any kind. The mass-ladder interpretation developed below
is therefore a **new hypothesis**, not an application of an existing one. The
executable search is `experiments/gwtc4_mass_ladder/phi_mass_search.py`; no
posterior-input or result receipt is retained in this repository.

## 3. Test 1: Do the Mass Peaks Sit at Integer Rungs?—Posterior Search
The three catalog peak locations map to rungs 186.4, 187.9 and 189.0,
corresponding to spacings of 1.44 and 1.16 rungs (mass ratios 2.0 and 1.75).
The 10 $M_\odot$ peak is 0.43 rungs from the nearest integer. A
$\varphi$-grid anchored at the 35 $M_\odot$ peak maps to 21.6, 13.4 and
8.3 $M_\odot$; the observed $\sim20$ $M_\odot$ peak is near 21.6, while the
10 $M_\odot$ peak is not near the other mapped values. These are exploratory
catalog comparisons, not a statistical result.

The question this catalog makes answerable: if black-hole formation freezes
out at activated cascade rungs, the merger-rate peaks should cluster at
$\varphi$-spaced masses, i.e. at integer rung separations
$\Delta N_{\mathrm{BH}}=k$ (equivalently $\Delta\ln m=k\ln\varphi$).

An event-population density average over PE posterior draws is not identified
by these headline peak locations. It requires explicit
$p_{\mathrm{pop}}(m)/\pi_{\mathrm{PE}}(m)$ weights (or a validated equivalent),
support and Jacobian treatment, and the PE-prior metadata. None of those
inputs is retained here. Equal-weight posterior draws therefore cannot be
promoted to a population-density estimate or an evidentiary verdict.

### 3.1 Face value (peak positions)

The three peaks sit at rungs 186.4, 187.9 and 189.0: spacings of 1.44 and
1.16 rungs (mass ratios 2.0 and 1.75), neither 1 nor 2. The 10 $M_\odot$
peak is 0.43 rungs from the nearest integer. A $\varphi$-grid anchored at the
35 $M_\odot$ peak predicts further peaks at 21.6, 13.4 and 8.3 $M_\odot$; the
observed $\sim20$ $M_\odot$ peak is within about one sigma of 21.6, but the
10 $M_\odot$ peak matches neither 13.4 nor 8.3. These face-value
coincidences are descriptive only.

### 3.2 Data and provenance

The executable search (`experiments/gwtc4_mass_ladder/phi_mass_search.py`) is
present, but this checkout retains no v4 posterior samples, acquisition
manifest, checksum, mock catalogs, PE-prior metadata, or run-result receipt.
The stated event/sample inputs and all numerical search outputs therefore
remain unresolved. The executable's nominal support
$M\in[2,200]\,M_\odot$ may be retained only if it is aligned with the
retained v4 posterior support and documented PE prior; with the current files
that alignment is unresolved. No likelihood gain, information criterion, mock
exceedance, or rung-fraction significance is assigned here.

### 3.3 Results and verdict

No reproducible posterior-search result is available from the retained files.
The integer-rung mass ladder remains **Hypothesized**, and the face-value rung
map above is an exploratory catalog comparison rather than a detection. No
evidentiary verdict is assigned without a retained prior-weighted rerun and
receipt.


## 4. Test 2: Ringdown—Compact-Density Mapping Remains Open

The available phenomenological halo coordinate is an inverse-density proxy:

$$q_{\rm proxy}^{\rm halo}(\rho) =
\frac{1}{1+(\rho/\rho_{\rm ref})^2}.$$

This coordinate is assigned to decrease at nuclear and horizon densities. The
canonical, reference-normalized solver diagnostic is

$$q(\rho,\varepsilon) =
\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},$$

which approaches $1$ as $\rho$ grows at fixed relative imbalance
$\varepsilon$. A separately supplied and measured constitutive map
$q=\mathcal{M}(q_{\rm proxy}^{\rm halo},\rho,\varepsilon)$ is required before
the halo proxy can enter
$G_{\text{eff}} = (\pi/\rho)(1+(\varphi^{6}-1)q)G$. The compact-density branch
therefore leaves compact-density ringdown frequencies as an open Hypothesized
prediction. The updated quantum-gravity probe supplies
Gaussian UV suppression, a low-$k$ slope
$c_{\text{eff}}\to\sqrt{1+\varphi^{-6}}\approx1.0275$, and a finite
$\mathcal{O}(11\%)$ running correction at the $\sigma$ scale; it leaves
high-$k$ mode energies uncapped and has no curved-spacetime ringdown
calculation (`gravity/quantum-gravity.md` §§4.2, 5.3, 6).

GW230814_230901—the loudest event ever recorded, SNR 42.1—is the available
high-leverage observation for this open question. Its single-detector analysis
found a potential ringdown deviation that the collaboration explicitly could
not separate from statistical noise and could not corroborate with a second
facility [5]. The catalog therefore leaves the compact-density constitutive
map and the curved-spacetime ringdown calculation open; a corroborated
deviation would constrain that map and the corresponding strong-field model.

## 5. Test 3: Halo Strain—No New Evidence, a Doubled Sample

The framework's halo-strain expression is a Hypothesized constitutive ansatz:

$$h_{\mathrm{Cassi}} =
\frac{\pi}{\rho}\Bigl(1+(\varphi^{6}-1)q\Bigr)h_{\mathrm{GR}},\qquad
q=\mathcal{M}(q_{\mathrm{proxy}}^{\mathrm{halo}},\rho,\varepsilon).$$

The proxy-to-canonical-$q$ map $\mathcal{M}$ and its calibration are open.
The quoted $\sim10\times$ cluster-halo enhancement (prediction 17,
`predictions/falsifiable-predictions.md` §4;
`experiments/cassi_physics/cassi_gravitational_waves.py`) and the
$q_{\mathrm{proxy}}^{\mathrm{halo}}<0.1$–$0.3$ figures are unverified
script/model outputs. No LVK/LIGO source or retained GWTC posterior/selection
receipt supports them as an observational bound, and they must not be
reported as a LIGO cluster non-detection. GWTC-4.0 supplies no retained
cluster-localized PE rerun here, so no evidentiary verdict is assigned.
Also untested by this catalog is the breathing-mode polarization prediction
(prediction 29), since the loudest events were single-detector.

## 6. What the Framework Cannot Say (Yet)

Three strengthened population results have no framework counterpart and must
not be retrofitted casually:

- **Merger rate increasing with redshift**—the framework's cosmology has gate
  engagement at $z\sim19$ and wake-wave structure formation, but no merger-rate
  prediction; the rate-redshift relation is a test for the future, not a
  consistency check.
- **Spin-distribution width increasing with redshift**—spin would use the
  optional SO(2) doublet-winding extension
  (`foundations/spin-fibonacci-spiral.md`, **Hypothesized**); that extension
  supplies no population-evolution prediction.
- **Broad neutron-star mass distribution**—the Cassi NS script
  (`experiments/cassi_physics/cassi_neutron_stars.py`) provides a conditional
  toy mass-radius output with no EOS baseline and no population-distribution
  calculation. Its one sharp, testable statement—a lower maximum NS mass than
  GR for the same EOS, attributed to $G_{\mathrm{eff}}$ enhancement in the
  outer layers—remains unquantified and requires the proxy-to-canonical-$q$
  constitutive map before any comparison with the catalog's NS-BH events
  (GW230529_181500, GW230518_125908).

## 7. Epistemic Summary

| Claim | Tier | Status after GWTC-4.0 |
|---|---|---|
| $N_{\mathrm{BH}} = \log_\varphi(M/M_{\mathrm{Pl}})$ | Hypothesized information-storage proxy | Exploratory mapping only; not Derived and no evidentiary verdict |
| Stellar-BH zone rungs 182–194 | Hypothesized (new) | Unmapped territory; face-value placements only |
| Integer-rung mass peaks | Speculative (new) | No retained v4 posterior, prior-weighted rerun, or receipt; unresolved |
| Compact-density ringdown response | Hypothesized (constitutive map and curved-spacetime calculation required) | $q_{\mathrm{proxy}}^{\mathrm{halo}}\to q$ is uncalibrated; the updated flat-space dispersion has a 1.0275 low-$k$ slope and $\mathcal{O}(11\%)$ $\sigma$-scale running correction; GW230814_230901 hint remains uncorroborated |
| Halo strain $\le10\times$ (pred. 17) | Hypothesized (constitutive ansatz) | Unverified script/model bound with no LVK source or retained prior-weighted rerun; no evidentiary verdict |
| Breathing-mode polarization (pred. 29) | Hypothesized | Untested (single-detector loud events) |
| Rate-$z$, spin-width-$z$, NS mass spread |—| No framework prediction; NS output is conditional toy with no EOS baseline; do not retrofit |

---

## 8. GWTC-4 Recheck (Blocked on Data, 2026-08-24)

The integer-rung peak test is blocked on GWTC-4.0 O4a PE acquisition, not on
the comparison question. This document is v4-only: the expected release
contains one `*-combined_PEDataRelease.hdf5` file per O4a event (Zenodo
17602505). The extraction/file contract must use that `.hdf5` pattern, not a
generic `.h5` glob, and must not silently mix GWTC-2.1, GWTC-3, or GWTC-5
files. A rerun also requires PE-prior metadata, support/Jacobian handling,
and a retained manifest, checksum, and result receipt before any evidentiary
verdict can be assigned.

No v4 posterior samples or such receipt are available in this checkout, so
the numerical search and the nominal $[2,200]\,M_\odot$ support remain
unresolved.

---

## References

- `gravity/quantum-gravity.md` §7.5—coherence-capacity rungs $N_{\text{BH}}$
- `foundations/dimensionful-cascade.md`—the 292-step ladder and its anchors
- `predictions/falsifiable-predictions.md` §4—GW predictions 17 and 29
- `cosmology/observational_constraints.md` §2.6—halo $q_{\rm proxy}^{\rm halo}$
  parameterization and SPARC comparison
- `experiments/cassi_physics/cassi_gravitational_waves.py`—strain-enhancement model
- `experiments/cassi_physics/cassi_neutron_stars.py`—modified TOV
- `experiments/phi_periodic_pk_search/phi_periodic_pk_search.py`—log-periodic search pipeline to reuse
- `experiments/gwtc4_mass_ladder/gwtc4_mass_ladder.py`—rung mapping, verification block, figure
- `experiments/gwtc4_mass_ladder/extract_samples.py`—v4-only posterior
  extraction; input files must match
  `*-combined_PEDataRelease.hdf5` from the GWTC-4.0 O4a release
- `experiments/gwtc4_mass_ladder/phi_mass_search.py`—the φ-periodic mass
  search (models, bootstrap null), pending a prior-weighted v4 rerun
- `experiments/gwtc4_mass_ladder/phi_mass_figure.py`—result figure (PNG gitignored)
- Data: GWTC-4.0 O4a PE release (Zenodo 17602505); no posterior receipt is
  retained here
- [1] AAS Nova roundup, 2026-07-29: https://aasnova.org/2026/07/29/monthly-roundup-the-fourth-catalog-of-gravitational-wave-events-from-ligo-virgo-and-kagra/
- [2] GWTC-4.0 catalog paper, arXiv:2508.18082, doi:10.3847/2041-8213/ae2c74
- [3] GWTC-4.0 population properties, doi:10.3847/2041-8213/ae771e
- [4] GW231123, doi:10.3847/2041-8213/ae0c9c
- [5] GW230814, doi:10.3847/2041-8213/ae2ad3
- [9] Gravitational Wave Open Science Center: https://gwosc.org/
