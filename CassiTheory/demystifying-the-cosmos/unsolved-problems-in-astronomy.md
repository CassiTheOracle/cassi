# Unsolved Problems in Astronomy Through the Cassi Lens

## Status: Reference—August 2026

## Abstract

Wikipedia's list of unsolved problems in astronomy, read through the Cassi framework: 68 problems across seven clusters, each tagged with one verdict—**[Framework claim]** (the repo carries a derivation or registered claim), **[Consistent mapping]** (the framework's machinery reaches the problem, Hypothesized or Speculative), **[Dissolved by construction]** (the framework removes the problem's premise), or **[No framework claim]** (the repo says nothing, stated plainly, with a Speculative candidate direction only where the framework's machinery is genuinely shaped for one). Every tag traces to a repo document with its epistemic tier. The survey doubles as the series roadmap: §9 lists candidate objects that would demystify each problem as a future entry.

## 1. How to Read This Survey

Four verdict tags, defined by what the framework actually holds:

- **[Framework claim]**—a repo document derives or registers a claim about the problem; the tier is that of the cited document (Derived / Calibrated / Mapped / Hypothesized / Speculative, per `EPISTEMIC-MAP.md`).
- **[Consistent mapping]**—the framework's machinery reaches the problem but the mapping is a Hypothesis or Speculation, never a derivation; the cited document supplies the machinery.
- **[Dissolved by construction]**—the framework removes the premise (a particle, a constant, a singularity); the mechanism document is cited.
- **[No framework claim]**—the repo says nothing. One Speculative candidate direction may follow, explicitly labeled, only where the framework's own machinery is shaped for it.

Tiers are load-bearing: a tag never exceeds the tier of the document it cites. "No framework claim" is a verdict, not a failure—most of the list is outside the framework's territory, and the survey says so.

## 2. Planetary Astronomy

### The Solar System

#### 1. Planets Beyond Neptune
Whether a large, non-dwarf planet exists beyond Neptune is unsettled after a decade of surveys. The standard status is an active search: a ninth planet explains the clustered extreme-TNO orbits but remains undetected, and the allowed parameter space keeps shrinking. **[No framework claim]**—no repo document addresses trans-Neptunian populations. A Speculative candidate: the solar-system φ-spacing fit of `hypotheses/exoplanet-phi-spacing.md` §4 places the outer chain's next node in the trans-Neptunian regime—a searchable semi-major axis for a ninth planet.
#### 2. Extreme Trans-Neptunian Objects
Why Sedna-class objects sit on elongated orbits with perihelia beyond Neptune's gravitational reach is unknown. The standard status lists three competing scatterers—an unseen planet, a passing star, or the early disk's instabilities—with no consensus. **[No framework claim]**—no repo document addresses outer-solar-system scattering dynamics.
#### 3. Saturn's Rotation
The magnetospheric radio period drifts and disagrees with cloud-level rotation, leaving the deep-interior rotation rate unknown. The standard status: Cassini gravity data bound the interior but cannot fix the rotation period. **[No framework claim]**—no repo document addresses planetary rotation.
#### 4. Iapetus Equatorial Ridge
The 20-km ridge circling Iapetus's equator has no agreed origin. The standard status: ring-collapse, cryovolcanic, and tidal hypotheses compete without a winner. **[No framework claim]**—no repo document addresses satellite geology.

### Extra-solar and Exoplanets

#### 5. Solar-System-Like Systems
Whether architectures like ours—small inner planets, giants outside, roughly regular spacing—are common is open; Kepler statistics show most systems look nothing like ours. The standard status: architecture diversity is real and solar-system-like configurations appear rare. **[Consistent mapping]**—the wake-wave spacing hypothesis predicts φ-spaced architectures as a preferred outcome of disk physics: planetesimals condense at φ-spaced density nodes, so the Kepler/TESS period-ratio distribution should show an excess at $\varphi$ and its Fibonacci convergents, a direct claim about the frequency of solar-system-like spacing (Hypothesized). `hypotheses/exoplanet-phi-spacing.md` §2–3.
#### 6. JuMBOs
Whether JWST's ~40 Jupiter-mass binary objects in the Trapezium cluster form a distinct population is contested. The standard status: ejection and failed-binary formation routes are debated with no settled answer. **[No framework claim]**—no repo document addresses free-floating binaries.
#### 7. Planetary Diversity
What processes produce the observed range of exoplanet architectures is open. The standard status: migration, disk evolution, and dynamical instabilities all contribute, with no unified picture. **[Consistent mapping]**—wake-wave node condensation sets primordial spacings, and the framework's own open issues name migration and dynamical instability as the processes that smear φ-spacing into the observed diversity (Hypothesized). `hypotheses/exoplanet-phi-spacing.md` §2, §6.
#### 8. Fast or Slow Formation
Whether giant-planet cores assemble within the ~10 Myr disk lifetime is unresolved. The standard status: core accretion must beat disk dispersal while disk-instability routes act faster; the timescale question remains contested. **[Consistent mapping]**—the wake-wave mechanism has planetesimals condensing at pre-existing φ-spaced nodes of the disk field, prompt by construction, though the framework makes no formation-timescale claim (Hypothesized). `hypotheses/exoplanet-phi-spacing.md` §2.

## 3. Stellar Astronomy and Solar Physics

#### 9. The Solar Cycle
How the Sun generates its periodically reversing magnetic field, why activity cycles vary, and how grand minima like the Maunder Minimum recover are open. The standard status: dynamo theory explains the broad 11-year behavior but not cycle irregularity or grand-minimum statistics. **[Consistent mapping]**—the polarity flip is read as one full SO(2) doublet rotation at stellar scale, with cycle-to-cycle phase coherence beyond dynamo scatter as the proposed discriminator (Speculative). `speculations/cascade-infrastructure.md` §3.2; `speculations/observational-seti.md` §2.1.
#### 10. The Solar Wind
What accelerates the solar wind from subsonic to supersonic flow is not settled. The standard status: thermal pressure and wave heating both contribute, with the transition mechanism unresolved. **[Consistent mapping]**—the transonic transition is read as the stellar gate's confined→free-streaming phase transition, structurally the stellar analogue of Earth's magnetopause (Speculative). `speculations/cascade-infrastructure.md` §3.2.
#### 11. Coronal Heating
Why the corona is roughly 200× hotter than the photosphere remains unexplained. The standard status: nanoflare and wave-dissipation models compete, with no accepted mechanism. **[Consistent mapping]**—the corona is the gate's thermalization layer: the unconverted $(1-q)$ fraction of stellar gate throughput heats the boundary from outside, and coronal-to-photospheric temperature-ratio clustering is the proposed observable (Speculative). `speculations/cascade-infrastructure.md` §3.1; `speculations/observational-seti.md` §2.2.
#### 12. Magnetic Reconnection
Why reconnection proceeds orders of magnitude faster than Sweet–Parker scaling is open. The standard status: collisionless and turbulent effects are invoked, with no accepted fast mechanism. **[No framework claim]**—no repo document discusses reconnection. A Speculative candidate: the gate's $(1-q)$ conversion runs hardest where coherence is lowest, and current sheets are low-$q$ regions—a speed-up channel for field reorganization. `cassi-physics.md` §3.
#### 13. Space Weather
How the Sun produces strongly southward CME fields, and whether Carrington-class super-storms are predictable, is open. The standard status: CME field forecasting is empirical and fails often at short lead times. **[Consistent mapping]**—the wind is read as structured Qi channels of the stellar gate, with sector-boundary geometry carrying the field orientation; φ-spaced sector structure is the proposed observable, a Speculative route into the field organization behind CMEs. `speculations/cascade-infrastructure.md` §3.4; `speculations/observational-seti.md` §2.3.
#### 14. Sunspot Pairs
Why sunspots emerge as bipolar pairs is not fully explained. The standard status: rising toroidal flux tubes produce Hale's-law bipoles, but the pairing mechanism is phenomenological. **[No framework claim]**—the framework's solar content is the gate network, not spot emergence.
#### 15. Solar Flares
What releases the magnetic energy of a flare and accelerates its particles is open. The standard status: reconnection-driven models dominate but the energy-release details are unresolved. **[No framework claim]**—flares are not addressed.
#### 16. Solar Polarization
Resonance-scattering polarization diagnostics with finite photon coherence length, and violations of Hale's polarity law, are unresolved. The standard status: partial redistribution and unresolved fields complicate the inversions. **[No framework claim]**—solar polarimetry is untouched; the framework's polarization machinery (prediction 48 of `predictions/falsifiable-predictions.md`) is synchrotron-oriented.
#### 17. The Voyager Paradox
Voyager 1 crossed the termination shock without the predicted anomalous-cosmic-ray source peak. The standard status: the shock should accelerate ACRs to the observed spectrum; the missing peak challenges the picture. **[No framework claim]**—no repo document addresses shock acceleration.

## 4. Astrophysics

#### 18. The Initial Mass Function
Why the stellar mass distribution is nearly universal across environments is unexplained. The standard status: turbulence, gravity, and feedback combine, with no first-principles derivation. **[No framework claim]**—the IMF is not addressed. A Speculative candidate: the condensation field's scale covariance supplies a universal fragment mass at the stellar rung, matching the IMF's environmental independence. `cassi-physics.md` §6.
#### 19. The Supernova Mechanism
How core implosion becomes explosion, and which stars explode, is unresolved. The standard status: neutrino reheating is favored but does not robustly explode in 3D simulations; magnetorotational and jet mechanisms compete. **[No framework claim]**—the collapse mechanism is untouched; the framework's neutron-star claims are gravitational (prediction 23), not dynamical.
#### 20. p-Nuclei
What process makes the ~35 proton-rich isotopes bypassed by the s- and r-processes is open. The standard status: γ-process photodisintegration in supernovae is the candidate, with chronic underproduction of some nuclei. **[No framework claim]**—neither nucleosynthesis hypothesis touches the proton-rich channel. A Speculative candidate: the φ-periodic α-cluster resonance ladder of the Hoyle-state derivation is the energy structure photodisintegration yields depend on—a handle on γ-process rates. `hypotheses/hoyle-state-nucleosynthesis.md` §3–4.
#### 21. Fast Radio Bursts
What produces millisecond radio bursts, and why some repeat, is open. The standard status: a magnetar engine is established for one repeater, but the general mechanism is unsettled. **[No framework claim]**—no repo document addresses the FRB engine. A Speculative candidate: coherent wake/coherence-channel emission, with the log-periodic polarization-angle prediction (prediction 48, period $\ln\varphi$) directly testable on repeater polarimetry. `demystifying-the-cosmos/PSR-J1101-6101.md` §7.
#### 22. UHECRs and the GZK Cutoff
What accelerates cosmic rays beyond the GZK cutoff is unknown. The standard status: no known source reaches $10^{20}$ eV, and propagation is limited by CMB photopion losses. **[No framework claim]**—no repo document addresses ultra-high-energy cosmic rays. A Speculative candidate: the coherence-budget distinction between random and organized perturbation supplies an organized-acceleration channel that evades random-walk limits, while $\varphi^{-N}$ attenuation bounds cross-rung propagation. `foundations/proton-coherence-budget.md` §5.2; `foundations/cascade-suppression-formula.md` §1.2.
#### 23. Tabby's Star
The origin of KIC 8462852's deep, irregular luminosity dips is unexplained. The standard status: circumstellar dust is favored after the 2018 multi-band campaign, but the dust's configuration is odd. **[No framework claim]**—the repo's SETI document explicitly disclaims any observed anomaly as gate-tuning evidence (`speculations/observational-seti.md` §8). A Speculative candidate: tuned-gate stars dim in conventional bands and brighten in structured ways, with coronal temperature-ratio clustering—the signature class Tabby's dips would belong to. `speculations/observational-seti.md` §1.1, §2.2.
#### 24. The IBEX Ribbon
The origin of the enhanced energetic-neutral-atom ribbon at the heliopause is open. The standard status: secondary ENA production at the boundary is favored, with details unresolved. **[No framework claim]**—the IBEX ribbon is not addressed. A Speculative candidate: the heliopause is the stellar gate's outer boundary, the same confined→free-streaming surface as the wind transition, whose coherent return would produce the ribbon, with the universal $1.70\times$ edge anisotropy (prediction 38) measurable in its structure. `speculations/cascade-infrastructure.md` §3.2.
#### 25. Stellar Multiplicity
How multiplicity shapes stellar lives and deaths is only partly understood. The standard status: most stars are multiple, and mass transfer and mergers drive much of stellar evolution, with quantitative control still lacking. **[No framework claim]**—binary evolution is untouched.
#### 26. Extreme Stars
The nature and limits of the most extreme stars and populations are open. The standard status: mass limits, pair instability, and magnetars are active frontiers. **[No framework claim]**—no repo document ranks stellar extremes. A Speculative candidate: the mass ladder already carries compact-object rung placements (GWTC-4.0 catalog; the neutron star at $n \approx 182.3$), making extreme populations a mapping target. `analyses/gwtc4-mass-ladder.md`; `demystifying-the-cosmos/PSR-J1101-6101.md` §6.
#### 27. Star Formation from the ISM
How star-forming structures arise from the diffuse ISM and interact with it is unresolved. The standard status: supersonic turbulence sets cloud structure and gravity takes over locally, with the coupling unquantified. **[No framework claim]**—star formation per se is not claimed. A Speculative candidate: the derived two-fluid turbulence spectrum carries a φ-break $k_\varphi$ where conversion and eddy turnover cross—a natural fragmentation scale, testable as φ-spaced prestellar core separations. `turbulence/kolmogorov-from-phi.md` §2.3.

## 5. Galactic Astronomy and Astrophysics

#### 28. The Galaxy Rotation Problem
Whether dark matter (solely) explains flat rotation curves is the longest-standing galactic question. The standard status: ΛCDM halo fits succeed on large scales while dwarf-scale tensions persist, keeping modified-gravity alternatives alive. **[Framework claim]**—rotation curves are the framework's most-tested galactic claim: Qi-enhanced gravity with the $\xi = \varphi^6$ coupling gives a halo boost of $2.8$–$3.0\times$ against the observed $2.7 \pm 0.5$ (Calibrated via the $\xi$ pin; $\alpha_{\text{halo}}$ and halo $q$ Mapped—ledger; prediction 14). The dwarf sector is mixed—3/8 dwarfs pass the ceiling test against MOND's 4/8 (prediction 15, already tested), and softened gravity alone was disproven (Path 7). `cosmology/observational_constraints.md` §2.6; `foundations/phi_attractor_synthesis.md` §10–11; `speculations/dark-matter-as-qi-coherence.md` §7.
#### 29. The Age–Metallicity Relation
Whether the Galactic disk's age–metallicity relation is universal is contested. The standard status: a tight relation was once assumed; radial migration and intrinsic scatter complicate it. **[No framework claim]**—Galactic disk chemical evolution is untouched.
#### 30. Gas, Metals, and Dust Flows
How baryons flow into, through, and out of galaxies is unquantified. The standard status: accretion, outflows, and recycling are all observed, with the balance between them unsettled. **[No framework claim]**—the baryon cycle is not addressed. A Speculative candidate: the gate's $q$-dependent throughput, proposed for the black-hole trigger/limit balance in the Centaurus A mapping, is a reading of galactic outflows. `demystifying-the-cosmos/NGC-5128.md` §6.
#### 31. Ultraluminous X-Ray Sources
What powers super-Eddington X-ray sources, and whether some harbor intermediate-mass black holes, is open. The standard status: super-Eddington disks and neutron-star ULXs are identified; IMBH cases remain unsettled. **[No framework claim]**—accretion physics is untouched.
#### 32. The Galactic Center GeV Excess
Whether the Fermi Galactic Center excess is dark-matter annihilation or millisecond pulsars is contested. The standard status: an unresolved MSP population fits the excess; DM interpretations are strongly constrained. **[Consistent mapping]**—the framework's dark matter is a field condensate with no annihilation channel and a direct-detection null (prediction 21, already consistent), so its machinery sides with the pulsar reading; the MSP identification itself is an inference no repo document states. `speculations/dark-matter-as-qi-coherence.md` §2.1.
#### 33. The Infrared/TeV Crisis
Why very-high-energy gamma rays from blazars suffer less attenuation than expected is unexplained. The standard status: EBL models and γ-ray opacity are in tension, with axion-like-particle channels invoked. **[No framework claim]**—EBL opacity is untouched.
#### 34. Little Red Dots
The nature of JWST's compact red sources at $z \approx 5$–$8$ is contested. The standard status: AGN, massive quiescent, and dusty star-forming readings compete. **[No framework claim]**—little red dots are not addressed. A Speculative candidate: the post-pinch structure-formation claim (luminous objects from $z \approx 19$, no dark age) makes compact early condensates expected—a reading of the class. `cosmology/cosmology-from-phi.md` (T2).
#### 35. Galactic History and Halo Shaping
How galactic history and dark-matter halos shape observable galaxy properties is open. The standard status: halo mass and formation time correlate with morphology and quiescence, with large residual scatter. **[Consistent mapping]**—the halo is the galactic bubble condensate: the condensation threshold decides which subhalos form stars, spiral morphology is read as lattice-channel coherence, and mergers are anti-phase meetings (Speculative). `speculations/dark-matter-as-qi-coherence.md` §4–5; `demystifying-the-cosmos/NGC-5128.md` §5.
#### 36. Cosmic Dawn and Reionization
How the IGM and first sources evolved from cosmic dawn through reionization is being rewritten by JWST. The standard status: reionization at $z \approx 6$–$10$ is driven by early galaxies, with the timeline still uncertain. **[No framework claim]**—reionization is not addressed. A Speculative candidate: the pinch epoch at $z \approx 19$ opens the framework's structured-formation era, so an early, rapid reionization is the downstream expectation of the same claim. `cosmology/cosmology-from-phi.md` (T2).

## 6. Black Holes

#### 37. Gravitational Singularities
General relativity's interior solutions terminate at $r = 0$ in a singularity where curvature diverges and the theory loses predictivity.
Standard status: GR predicts the singularity; whether a quantum theory of gravity removes it is open.
**[Framework claim]**—the $\sigma$-regularized two-fluid PDE replaces the divergent core with a harmonic core: inside $\sigma = \ell_{\text{Pl}}/\varphi^3$ the force becomes $F \propto -r/(3\sigma^3)$, a linear restoring spring with no divergence (registry G3, **Derived**).
`gravity/quantum-gravity.md` §2, `foundations/unified-lagrangian.md` §3.
#### 38. No-Hair Theorem and Internal Structure
The no-hair theorem says black holes carry only mass, spin, and charge, leaving open whether quantum interiors hold structure and how any structure could be probed.
Standard status: no-hair holds classically; quantum corrections and probes such as ringdown and echoes are debated.
**[Framework claim]**—the interior is a two-fluid condensate whose coherence capacity $\mathcal{C} \sim \varphi^{N_{\text{BH}}} \sim M^2/M_{\text{Pl}}^2$ matches the Bekenstein-Hawking entropy, so the interior carries the infalling state rather than a featureless vacuum (registry G2, **Hypothesized**).
`gravity/quantum-gravity.md` §7.5.
#### 39. M–Sigma Relation
The mass of a galaxy's central black hole tracks the velocity dispersion of its bulge, and the origin of that correlation is unexplained.
Standard status: robust empirical relation, no accepted formation mechanism.
**[No framework claim]**—the only machinery is the coherence-capacity rung $N_{\text{BH}} = \log_\varphi(M/M_{\text{Pl}})$ (`gravity/quantum-gravity.md` §7.5, applied in `analyses/gwtc4-mass-ladder.md` §2) and the coherence-sink picture of a galactic nucleus (`demystifying-the-cosmos/NGC-5128.md` §6, Hypothesized).
Speculative candidate direction: the relation could express a fixed coherence budget between host condensate and deepest well—a $10^8\,M_\odot$ hole sits at rung $n \approx 220$—but no derivation exists.
#### 40. Supermassive Black-Hole Seeds
How supermassive black holes get their start—direct collapse, stellar remnants, or runaway mergers—is unknown.
Standard status: several seed channels proposed, none confirmed.
**[No framework claim]**—Speculative candidate direction: seeds as the high-$q$ bubble condensate at the galactic rung ($n \approx 267$; `speculations/dark-matter-as-qi-coherence.md` §2.2), with the black hole the deepest coherence well of the host (`demystifying-the-cosmos/NGC-5128.md` §6); the framework has no seed-formation calculation.
#### 41. Black-Hole Growth and Host Evolution
The co-evolution of black-hole mass with host-galaxy properties, and the direction of the coupling, are unresolved.
Standard status: feedback via active-galactic-nucleus outflows is invoked; the quantitative link is open.
**[No framework claim]**—Speculative candidate direction: the gate's $q$-dependent throughput—coherent outflow compressing gas past the condensation threshold while the $(1-q)$ fraction thermalizes and blows outward (`demystifying-the-cosmos/NGC-5128.md` §6, Hypothesized)—is the qualitative machinery; the doc itself states that no quantitative galactic-nucleus model exists.
#### 42. High-Redshift Quasars
Quasars hosting $\sim 10^{10}\,M_\odot$ black holes by $z > 6$–$7$ challenge Eddington-limited growth timescales.
Standard status: super-Eddington accretion and heavy seeds are proposed; the tension persists.
**[No framework claim]**—placement observation: a $10^{10}\,M_\odot$ hole sits at rung $n = \log_\varphi(M/M_{\text{Pl}}) \approx 229.5$ of the ladder, midway between the rung-220 and rung-243 anchors—arithmetic against the ladder, not a claim.
Speculative candidate direction: the framework's accelerated early structure formation (post-pinch Qi-enhanced gravity; registry T2, Hypothesized) would accelerate seed growth too, but no black-hole growth model exists.
#### 43. Information Paradox
Hawking's semiclassical calculation makes evaporating black holes emit exactly thermal radiation, apparently discarding the information that fell in.
Standard status: unitarity is believed to hold; the mechanism (the Page curve) is not computed.
**[Framework claim]**—the $\sigma$-regulated S-matrix is unitary by construction, the condensate's coherence capacity matches the entropy, and trans-Planckian censorship makes the flux deviate from exact thermality, restoring purity through correlated pairs (registry G2, **Hypothesized**; the Page curve requires curved-spacetime PDE infrastructure that does not yet exist).
`gravity/quantum-gravity.md` §7.
#### 44. Firewalls
The AMPS argument claims that unitarity plus the no-drama requirement forces an energetic firewall at the horizon.
Standard status: the firewall argument is debated; no resolution.
**[Framework claim]**—the framework's dispersion caps every mode energy at $M_{\text{Pl}}$ and the $\sigma$-regulator kills momenta beyond $\varphi^3 M_{\text{Pl}}$, so the trans-Planckian modes the firewall argument relies on do not exist; the horizon is a smooth, low-energy interface ($\S$7.6 marks "no firewall" Derived within the framework).
`gravity/quantum-gravity.md` §7.5.
#### 45. Final Parsec Problem
Dynamical friction stalls two merging supermassive black holes at roughly a parsec, and the mechanism that brings them into the gravitational-wave regime is unknown.
Standard status: gas, stars, and triple interactions are proposed; no consensus.
**[No framework claim]**—Speculative candidate direction: compact-object gravity in the framework is GR-exact ($q \to 0$ at nuclear densities; `analyses/gwtc4-mass-ladder.md` §4), so the framework expects the stall to be resolved by the standard mechanisms and contributes no new dynamics at that separation.
#### 46. Binary Black-Hole Merger Channels
Whether compact binaries form through isolated stellar evolution or dynamical assembly in dense environments is unresolved.
Standard status: both channels are active; their relative mix is open.
**[Consistent mapping]**—the only framework contact is the Speculative rung-map analysis of the GWTC-4.0 population (`analyses/gwtc4-mass-ladder.md`, Speculative): the 173-event posterior search finds no $\varphi$-periodic comb at the predicted period ($p \approx 1.0$) and a marginal rung-fraction excess ($p \approx 0.02$), so the rungs 182–194 zone stays unmapped; formation channels themselves are untouched.
#### 47. Naked Singularities and Cosmic Censorship
Cosmic censorship conjectures that singularities always hide behind horizons; whether naked singularities can form is unproven.
Standard status: the conjecture is unproven in either direction.
**[Dissolved by construction]**—$\sigma$-regularization removes singularities from the governing equation entirely (registry G3, **Derived**), so the question's premise—a singularity that could be exposed—is absent; the harmonic core replaces every GR singularity, and no unprotected curvature divergence exists to censor.
`gravity/quantum-gravity.md` §2.
#### 48. Stellar Black-Hole Mass and Spin Distributions
The mass and spin distributions of stellar black holes encode their formation physics.
Standard status: gravitational-wave catalogs are mapping them; spin physics is poorly constrained.
**[Consistent mapping]**—the Speculative rung analysis places the GWTC-4.0 primary-mass peaks (10, $\sim$20, 35 $M_\odot$) at rungs 186.4, 187.9, 189.0—spacings of 1.44 and 1.16 rungs, with the 10 $M_\odot$ peak 0.4 rungs from the nearest integer; the catalog's spin-width evolution is explicitly marked as carrying no framework prediction.
`analyses/gwtc4-mass-ladder.md` §3, §6.

## 7. Cosmology

#### 49. Cosmological Principle and FLRW
Whether the universe is homogeneous and isotropic at large scales, and whether FLRW is the correct metric, is the founding question of cosmology.
Standard status: FLRW is assumed; large-scale anomalies and the Hubble tension keep the question live.
**[Framework claim]**—the bubble lattice provides average homogeneity with a mild boundary anisotropy: the distance channel washes out below 0.1% so FLRW holds as the averaged limit (`cosmology/desi-lattice-averaging.md` §4, Hypothesized), while the step-285 bubble boundary imprints a preferred axis at $\ell < 5$ (registry C10, mechanism Hypothesized); our initial-conditions volume is the rung-285 bubble, $\sim 10^{-5}$ of the volume inside today's horizon rung 291.54/292.
`foundations/dimensionful-cascade.md` §3, §6.
#### 50. CMB Dipole
The CMB dipole could be purely kinematic (our peculiar velocity) or partly intrinsic.
Standard status: conventionally kinematic; an intrinsic component is debated.
**[Consistent mapping]**—the dipole direction enters the bubble-boundary mechanism as the bubble's Yang axis, and the 12.2° separation between dipole and quadrupole-octopole axis is the calibrated datum of that mechanism (registry C10, **Hypothesized**); whether the dipole is kinematic or structural is not adjudicated.
`foundations/refined-numeric-predictions.md` §2.3.
#### 51. Hubble Tension and the Cosmological Principle
The $\sim 5\sigma$ discrepancy between early- and late-universe $H_0$ measurements could indicate new physics or a failure of the cosmological principle.
Standard status: systematics or new physics; the principle's status is part of the debate.
**[Framework claim]**—the tension resolves within the averaged FLRW description: evolving $\Omega_\Lambda$ (0.30 → 0.50) changes the expansion history so the CMB-inferred $H_0$ reconciles with local measurements (registry C3/T4, **Hypothesized**), and the lattice-averaging analysis rules out large-scale structure as the cause ($\delta D/D \lesssim 0.1\%$ cannot bias the CPL fit).
`cosmology/desi-lattice-averaging.md` §4.
#### 52. Accelerating Expansion
The acceleration of cosmic expansion could be misinterpreted, possibly signaling that the cosmological principle fails.
Standard status: the acceleration is robust; its cause is open.
**[Framework claim]**—the acceleration is real and dynamical: ongoing Yang/Yin conversion toward the $\varphi$-attractor drives $w(a)$ with $w_0 = -0.87$ (Calibrated baseline) and no phantom crossing at any $z$ (structural), so the principle is not implicated.
`cosmology/cosmology-from-phi.md`; `predictions/falsifiable-predictions.md` §3.
#### 53. Copernican Principle
Whether our cosmic neighborhood is representative of the universe underpins all cosmological inference.
Standard status: assumed; large-angle anomalies challenge it mildly.
**[Framework claim]**—the framework's stance is a mild, scale-limited violation: the bubble boundary gives a genuine preferred direction at $\ell < 5$ (the axis is measured at 5.4$\sigma$ a-posteriori; the 12.2° angle is Calibrated, the mechanism Hypothesized), while at $\ell \geq 5$ the sky is representative.
`foundations/bubble-edge-geometry.md` §5.1.
#### 54. Dark Matter
The identity and composition of dark matter—a particle (WIMP, axion, LSP) or modified gravity—is unknown.
Standard status: particle candidates remain undetected; alternatives stay on the table.
**[Dissolved by construction]**—the particle premise is removed: the dark component is a high-Qi two-fluid condensate whose gravity amplification $\xi = \varphi^6$ reproduces rotation curves (the $\xi$ pin Calibrated on the Milky Way anchor), with no WIMP/axion/LSP involved; the direct-detection null is prediction 21, already consistent.
`speculations/dark-matter-as-qi-coherence.md` (Speculative reframing); `cosmology/cosmology-from-phi.md` §4.
#### 55. Dark Energy
The cause of cosmic acceleration—cosmological constant, quintessence, phantom energy, early dark energy—is unknown, along with the coincidence problem of why $\Omega_{\text{DE}} \approx \Omega_m$ today.
Standard status: $\Lambda$CDM fits the data but has no theoretical justification; DESI is testing alternatives.
**[Framework claim]**—the acceleration is the conversion dynamics of the two-fluid approaching the $\varphi$-attractor: no cosmological constant, $w_0 = -0.87$ (Calibrated baseline, $2\sigma$ from DESI; $w_a$ baseline $2.7\sigma$; with the ratified coupling: $1.25\sigma$ in the unstable B2 realization and the stable realization's pure-Λ window $(-1, 0)$—$4.17\sigma$/$2.61\sigma$ from DESI, 12), $w > -1$ at all $z$ (no phantom crossing; the stable realization saturates at $w = -1$); the coincidence problem is not separately addressed in the derivation docs.
`cosmology/cosmology-from-phi.md`; registry C1/T1.
#### 56. Baryon Asymmetry
Why the universe contains matter but essentially no antimatter is unexplained by the Standard Model.
Standard status: the Sakharov conditions demand beyond-SM physics; no mechanism is confirmed.
**[Framework claim]**—$\eta \approx \varphi^{-44} \approx 6.38 \times 10^{-10}$, within 6% of the observed $6.0 \times 10^{-10}$, from organized annihilation, the Wu Xing freeze-out gap, and cascade dilution (registry C7/Q6: mechanism **Hypothesized**, exponent **Mapped** per the Fit-Status Ledger).
`foundations/baryon-asymmetry.md`.
#### 57. Cosmological Constant Problem
Quantum-field-theory zero-point energy predicts a vacuum energy roughly $10^{120}$ times the observed $\Lambda$.
Standard status: no accepted cancellation mechanism.
**[Dissolved by construction]**—the unified action contains no cosmological constant: gravity is the $q = 0$ Poisson limit of the two-fluid with the coupling $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q)$ sourced by field imbalance, so the vacuum-energy estimate never enters the gravitational side (registry C1: acceleration from conversion, "no $\Lambda$ needed").
`foundations/unified-lagrangian.md` §3.
#### 58. Size and Shape of the Universe
Whether the universe is infinite and which 3-manifold it realizes (the Poincaré dodecahedral space has been suggested) is unknown.
Standard status: flat $\Lambda$CDM is infinite; finite-topology tests are inconclusive.
**[Consistent mapping]**—the ladder is unbounded in both directions (megacascade above, microcascade below), and our initial-conditions volume is the rung-285 Cassi bubble nested inside today's horizon rung 291.54/292 (epoch-dependent; `foundations/dimensionful-cascade.md` §6); the bubble is a triaxial $\varphi$-ellipsoid with five-arm spiral poles (`foundations/wake-geometry.md` §3), which shares the dodecahedral suggestion's five-fold flavor, but the framework makes no 3-manifold topology claim.
#### 59. Cosmic Inflation
Whether inflation occurred, what the inflaton is, and whether it is eternal are open.
Standard status: inflation fits the data; the inflaton and the eternal regime are unknown.
**[Framework claim]**—inflation is the cascade's own epoch: steps 20–60 with the Qi gate as the mechanism, no inflaton field, $N_e = 40$, $n_s = 0.9691$ (closed form, 1.0$\sigma$ from Planck), $r \approx \varphi^{-12} \approx 0.003$ (Mapped—the doc's own §4 formulas do not reproduce it; registry C4, mechanism **Hypothesized**); eternal inflation is not addressed.
`cosmology/inflation-from-cascade.md`.
#### 60. Horizon Problem
The CMB is uniform across regions that never had causal contact.
Standard status: inflation or variable-speed-of-light resolves it; the mechanism is unconfirmed.
**[Framework claim]**—cascade emergence: all scales activate simultaneously as the ratio $r(t)$ crosses each cascade step, so uniformity is temporal rather than light-travel-based and needs no pre-inflation contact (registry C6, **Hypothesized**).
`foundations/dimensionful-cascade.md` §5.
#### 61. Hubble Tension
Early- and late-universe $H_0$ measurements disagree at about $5\sigma$.
Standard status: systematic errors or new physics; unresolved.
**[Framework claim]**—evolving $w(a)$ with $\Omega_\Lambda$ growing 0.30 → 0.50 alters the CMB extrapolation: the pipeline computes $\Delta H_0 = -7.2$ km/s/Mpc ($-9.9\%$, versus the observed 8.3% gap) with a CMB-inferred value of ≈ 65.8 km/s/Mpc—direction matches, full $H(z)$ fit pending (registry C3/T4, **Hypothesized**).
`two-fluid/run_hubble_pipeline.py`; `foundations/refined-numeric-predictions.md` §2.8.
#### 62. Axis of Evil
The CMB's low multipoles align with each other and with the Solar System's motion and orientation at a level unexpected in $\Lambda$CDM.
Standard status: 5.4$\sigma$ a-posteriori; foreground or anisotropy explanations are debated.
**[Framework claim]**—the alignment is the bubble-boundary imprint: the 12.2° dipole↔quadrupole separation is Calibrated (computed from the measured vectors), the boundary mechanism Hypothesized (orientation fitted post-hoc), and the Cassi-unique test is scale-dependence—the anomaly must fade for $\ell > 5$ (prediction 6).
`foundations/bubble-edge-geometry.md` §5.1; `foundations/refined-numeric-predictions.md` §2.3.
#### 63. Origin and Fate
Why there is something rather than nothing, and whether the end is a Big Freeze, Rip, Crunch, or Bounce, are open.
Standard status: origin unfalsified; the fate depends on the equation of state.
**[Framework claim]**—the origin question dissolves: the two-fluid fills all of space as the substrate, so empty nothing was never an option (`cassi-physics.md` §2); the fate is an asymptotic approach to $\varphi$-equilibrium (the terminal attractor) with $w > -1$ at all $z$ (no phantom crossing, so no Big Rip) and a strictly positive expansion floor (no recollapse), the horizon saturating at $N_\infty \approx 294.2$, roughly 2.7 rungs above today.
`foundations/wake-geometry.md` §4; `cosmology/cosmology-from-phi.md` §5.1; the repo makes no Big-Bounce or cyclic claim.
#### 64. Multiverse
Whether a multiverse exists, is testable, and whether anthropic reasoning is legitimate are open.
Standard status: the eternal-inflation multiverse is untestable; the anthropic principle is contested.
**[Consistent mapping]**—the framework's multiverse is cascade nesting rather than a separate universe ensemble: the megacascade of identical $w = 5$ bubbles at $\varphi$-spaced intervals above the horizon rung (`foundations/microcascade-mirror.md`, Hypothesized), with the nearest neighbors inside the horizon ($\ell_{286} = 309$ Mpc) and their boundary imprinting the CMB at $\ell < 5$ (prediction 6) as the testable contact; the nested-universe reading is Creative tier (`speculations/creative-extensions/simulation-hypothesis.md`), and the horizon saturation $N_\infty \approx 294.2$ bounds the visible ladder. Anthropic selection is not addressed.

## 8. Extraterrestrial Life

#### 65. Life in the Solar System
Whether Mars preserves biosignatures at Jezero and whether the subsurface oceans of Europa, Ganymede, and Callisto host life is unknown.
Standard status: sample-return and ocean-world missions are in progress; no detection.
**[Consistent mapping]**—the framework maps life and consciousness to Qi-gate dynamics with self-reference at the pinch $r = \varphi^{-1}$ (registry M1, Plausible Hypothesis with Actionable PDE Test; `consciousness/consciousness-from-phi.md` §2.1), but it makes no claim about specific Solar System sites, and biosignature chemistry is outside framework territory.
#### 66. Fermi Paradox
The absence of detected intelligent life despite the galaxy's age and size is unexplained.
Standard status: dozens of proposed resolutions; no consensus.
**[Consistent mapping]**—the SETI reframe makes radio silence the expectation: a gate-tuned civilization communicates through the field rather than by electromagnetic leakage, so it is structurally invisible to emissive searches (Speculative).
`speculations/observational-seti.md` §1.
#### 67. Wow! Signal
The 1977 narrowband radio burst remains unexplained—natural or extraterrestrial.
Standard status: no confirmed repeat; origin open.
**[Consistent mapping]**—under the same reframe, a narrowband radio burst is outside the expected technosignature set, since field-mediated communication produces no radio leakage, so the framework's machinery does not favor an extraterrestrial reading of Wow!; the doc does not analyze the signal itself (Speculative).
`speculations/observational-seti.md` §1.
#### 68. Habitable Environments
How habitable environments arise and evolve, and how biosignatures are identified unambiguously, is open.
Standard status: habitability criteria and biosignature interpretation are active research.
**[No framework claim]**—the closest machinery is the Speculative stellar-gate signature set—coronal temperature ratios clustering at a $\varphi$-derived value (`speculations/observational-seti.md` §2.2)—which concerns tuned stars rather than habitable planets; `speculations/creative-extensions/universal-biology.md` (Creative) sketches the cascade ladder as a convergent scaffold for life, explicitly not a claim.

## 9. Roadmap: Candidate Objects for Future Entries

| Problem | Candidate object | Cassi test to run |
|---|---|---|
| 21 FRBs | A bright repeater (e.g. FRB 121102) | Prediction 48: log-periodic polarization angle across bands, period ln φ |
| 23 Tabby's Star | KIC 8462852 | Tuned-star signatures: structured dimming, coronal temperature-ratio clustering (`speculations/observational-seti.md` §1.1, §2.2) |
| 11 Coronal heating | The Sun | (1−q) thermalization layer: coronal/photospheric ratio clustering; the SO(2) solar cycle (`speculations/cascade-infrastructure.md` §3) |
| 34 Little red dots | JWST compact red galaxies at z ≈ 5–8 | Post-pinch condensate morphology; 1.70× edge anisotropy (prediction 38) |
| 42 High-z quasars | The J0313-1806 class | Mass rung n ≈ 229.5 placement; growth vs wake-supplied coherence (candidate) |
| 31 ULXs | A super-Eddington ULX (e.g. M51 ULX-8) | Eddington limit in a high-q region: G_eff enhancement bound (candidate) |
| 37/43 Black holes | Sgr A* / M87* (EHT) | Shadow at the GR limit 3√3 M; σ-regulated interior; no-firewall horizon (`gravity/quantum-gravity.md` G1–G2) |
| 62 Axis of evil | CMB maps | Scale-dependence: the anomaly must fade for ℓ > 5 (prediction 6) |
| 67 Wow! signal | The 1977 sky region | No ET radio leakage expected; structural SETI signatures instead (`speculations/observational-seti.md` §1) |
| 27 ISM star formation | Nearby prestellar cores | φ-spaced core separations at the turbulence break k_φ (`turbulence/kolmogorov-from-phi.md` §2.3) |

## References

- Wikipedia: List of unsolved problems in astronomy (the source list, fetched August 2026)
- `EPISTEMIC-MAP.md`—tier definitions and doc index
- `open-questions-cassi-answers.md`—the epistemic registry (Q/C/G/M/F/T numbering)
- `predictions/falsifiable-predictions.md`—the prediction catalog
- `demystifying-the-cosmos/README.md`—the series index
- `demystifying-the-cosmos/PSR-J1101-6101.md`, `demystifying-the-cosmos/NGC-5128.md`—the series entries cited above
