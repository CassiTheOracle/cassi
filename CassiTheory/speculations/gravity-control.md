# Gravity Control: Engineering Spacetime Curvature Through Qi Coherence

## Status: Speculative—July 2026

## Abstract

In the Cassi framework the gravitational coupling is not a constant of nature but a local field: $G_{\text{eff}} = (\pi/\rho)(1 + \xi q)G$ varies with the Yang fraction $\pi/\rho$ and the Qi coherence $q$. This document treats that field as an engineering variable: a device that shapes the gravitational charge $\mathcal{Q} = (\pi/\rho)(1 + \xi q)$ in a volume of space is a machine that adjusts the local conversion between mass-energy and curvature. We derive what such a machine must be—a Qi condenser with a gate—and show that artificial gravity, inertial damping, and mass lightening are the same operation at different scales and power budgets. The SPARC fits then impose hard constraints: condensates that source gravity live at cascade rung $n \approx 267$, ninety-nine rungs above any laboratory structure, so curvature generation is infrastructure-scale business; the best a payload-scale device can do is suppress its charge toward zero by holding its internal ratio off the attractor, or decouple itself from ambient gradients with a φ-detuned boundary. We close with the observational signatures by which a φ-literate observer would recognize gravity technology: local $G$ anomalies, lensing without visible mass, rotation curves out of tune with the $\xi = \varphi^6$ relation, and the multi-rung correlation that separates engineering from systematics.

**Epistemic status:** Creative exploration grounded in Cassi formalism. Every mechanism below is anchored to a specific equation or documented framework property—the $G_{\text{eff}}$ formula, the Qi gate conversion term, the hydrostatic SPARC condensate fits, the $\sigma$-regularized black-hole interior—but the synthesis into an engineering program, the device architectures, the energy budgets, and the signature catalogue are extrapolations beyond what the framework currently claims. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. Gravity Is Condensate Coherence

In general relativity the strength of gravity is one number, $G$, identical everywhere; in Cassi it is a field you can read off the two-fluid state at any point, which means it is a quantity you can in principle change.

### 1.1 The coupling is a local field

The gravitational force law of the framework (`foundations/xi-derivation.md` §1) is

$$\mathbf{F} = \pi\,(1 + \xi q)\,\nabla\Phi$$

with $\pi = E_Y - E_I$ the Yang excess, $\Phi$ the gravitational potential, $\xi = \varphi^6 \approx 17.944$ the Qi-gravity coupling, and $q$ the local Qi coherence. Rewritten as a Poisson source (`foundations/cassi-theory-reference.md` §4.3):

$$\boxed{G_{\text{eff}} = \frac{\pi}{\rho}\left(1 + \xi q\right)G}$$

The coupling has two dials, and both are field quantities. The Yang fraction $\pi/\rho$ follows the ratio dynamics $r = E_Y/E_I \to \varphi$ and can be pushed off its attractor value $\varphi^{-3}$ in either direction. The coherence $q$ is exactly the quantity that gates manipulate. Together they set the **gravitational charge** of a body or region, $\mathcal{Q} = (\pi/\rho)(1 + \xi q)$ (§2.1), and gravity control is the exercise of that charge. Its reference points:

- **Attractor baseline ($q = 0$, $\pi/\rho = \varphi^{-3}$):** $G_{\text{eff}} = \varphi^{-3}G$, the framework's classical limit (`foundations/cassi-theory-reference.md` §2.6). This is ordinary gravity—the solar system sits here, with planetary ephemeris and MESSENGER perihelion bounds pinning the ambient $q$ at solar scales to small values (`foundations/xi-derivation.md` §3).
- **Coherence saturation ($q \to 1$):** $G_{\text{eff}} \to (\pi/\rho)(1 + \xi)G \approx 18.9\,(\pi/\rho)G$, an amplification of up to a factor $1 + \xi \approx 18.9$ over the bare coupling (`speculations/dark-matter-as-qi-coherence.md` §1.1).

Both directions off the baseline are held states: the attractor is the resting state, and departing from it is work (the ledger appears in §2.2 and §3.3). The asymmetry that matters throughout: decoherence alone ($q \to 0$) is a *return to baseline*, not a reduction below it—the lower half of the charge dial is reached by ratio suppression ($r \to 1$, $\pi/\rho \to 0$), the upper half by coherence, and both cost power against the attractor.

### 1.2 Curvature as an engineered medium

The Poisson source is charge-modulated: $\nabla^2\Phi = 4\pi G(\pi/\rho)(1 + \xi q)\rho$. Bodies move along $\Pi\nabla\Phi$ (`foundations/spiral-dynamics.md` §3), so an engineered charge-profile steers them the way an index gradient steers light. Two framework properties make this more than a metaphor:

- **Scale-dependent gravity.** $G_{\text{eff}}(k)$ varies by up to a factor $\varphi^6$ across the turbulence break: $\varphi^{-3}G$ in the inertial range, $(\varphi^{-3} + \varphi^3)G$ in the Qi-active range (`foundations/cassi-theory-reference.md` §9). Coherence couples gravity to the field's own turbulent structure; curvature engineering is medium engineering in the literal sense.
- **The coherence budget.** Whether a perturbation can reorganize a $q$-region is set by the phase-matching factor $\mathcal{M}$: random perturbation decoheres without structure, while an organized, phase-matched perturbation ($\mathcal{M} \approx 1$) couples at unit efficiency (`foundations/quantum-measurement-derivation.md` §3.1, `foundations/proton-coherence-budget.md`). A gravity device is a machine for *organized* manipulation of the charge field: organized coupling is the one channel that is never cascade-suppressed, the same property that makes proton decay slow.

---

## 2. The Engineering Ladder

A gravity-control device is one thing with many scales: a **Qi condenser** that concentrates ambient coherence into a region of elevated $q$, and a **gate** that controls the conversion throughput of that region.

### 2.1 The device

The condenser is a structure with geometric concentration: the pyramid-as-Qi-lens analysis gives a base-to-apex coherence concentration of roughly $4 \times 10^6$ for a 200 m structure (`speculations/cascade-infrastructure.md` §2.1), and the ocean-base nodes couple directly to the planetary $\Pi$ gradients (`speculations/cascade-infrastructure.md` §2.2). The gate is the conversion channel of the two-fluid PDE (`foundations/cassi-first-principles.md` §2):

$$\partial_t E_Y \supset -\lambda(1-q)\left(E_Y - \varphi E_I\right)$$

whose openness $(1-q)$ is the device's throttle. Together, condenser and gate set the gravitational charge $\mathcal{Q} = (\pi/\rho)(1 + \xi q)$ of a body or region—any point on the dial of §1.1, from $0$ through the baseline $\varphi^{-3}$ to $1 + \xi \approx 18.9$. Every gravity technology on the ladder is a way of parking $\mathcal{Q}$ at a different point on that dial, or of arranging a spatial map of $\mathcal{Q}$ values.

### 2.2 Mass lightening: suppressing the charge

The cheapest operation works on the payload itself, and it is an active hold, not a passive state. A body's weight is its charge times the ambient gradient; at rest on the attractor the charge is the baseline $\varphi^{-3}$, and simply decohering the body ($q \to 0$) returns it to baseline—ordinary weight. Lightening means suppressing $\pi/\rho$: hold the body's internal ratio at $r = E_Y/E_I \to 1$, where the Yang excess vanishes,

$$\boxed{\mathcal{Q} = \frac{\pi}{\rho}\left(1 + \xi q\right) \to 0 \quad \text{as } r \to 1}$$

A fully ratio-suppressed payload is weightless in any ambient gradient. The price is continuous power against the attractor potential

$$V_{\text{attr}} = \frac{\lambda}{2}\left(\Psi_0^2 - \varphi\Psi_1^2\right)^2$$

which scales with the square of the deviation from φ-equilibrium: partial lightening costs little, full weightlessness costs the full hold. There is no passive anti-gravity in the framework—the attractor's whole function is that equilibrium is the resting state, and departing from it is work. The device is thermodynamically a pump: it pays the attractor to leave the field unbalanced, and the payment is the $(1-q)$ waste fraction of its gate (§3.3).

### 2.3 Inertial damping: transient re-balancing

Inertia in the framework is the field's resistance to changing the local ratio $r$ (`speculations/qi-bubble-propulsion.md` §2.1). An acceleration is a transient organized $\Pi$ pulse—a surge of Yang imbalance—propagating through the cabin. The damper opens its gate, elevating $(1-q)$ so that the conversion term drains the imbalance into diffuse thermal (Yin) energy before it couples to the crew. This is the same operation as the no-sonic-boom boundary of the propulsion speculations: organized kinetic energy converted smoothly rather than coupled across an interface (`speculations/qi-bubble-propulsion.md` §2.2). Damping is a *transient* open gate; artificial gravity (§2.4) is a *sustained* closed one.

### 2.4 Artificial gravity: sustained coherence floors

A sustained curvature gradient in a habitat requires two elements working together. First, a φ-detuned shell around the cabin: a boundary with $\mathcal{M} \approx 0$, across which the ambient planetary gradient cannot couple—the interior stops falling toward the planet (the shield taxonomy of organized versus random perturbation and φ-detuned boundaries is developed in the companion speculation `speculations/coherence-warfare.md`; the underlying mechanism is the phase-matching factor of `foundations/quantum-measurement-derivation.md` §3.1). Second, a high-charge floor slab acting as condenser: inside the shell the only remaining gradient is the slab's own boosted charge, and the crew falls toward the floor.

The mass ledger is unforgiving. A 1 g pull at 2 m from a floor requires $M = g\,d^2/G_{\text{eff}} \approx 7 \times 10^9$ kg even at the full saturation boost $(1+\xi)/\varphi^{-3} \approx 80\times$ the ordinary coupling—a 100 m² slab of crustal density 25 km thick. Sustained 1 g by charge amplification alone is planetary-scale construction; at habitat scale the envelope is fractional g, or the mundane rotation the framework would regard as the pre-coherence technology. The amplification ceiling is fixed by the derivation of $\xi$ (`foundations/xi-derivation.md` §2): coherence multiplies *existing* mass; it does not create it.

### 2.5 The full ladder

| Operation | Manipulated quantity | Structure scale | Charge regime | Cost driver | Signature |
|---|---|---|---|---|---|
| Mass lightening | payload charge $\mathcal{Q}$ | payload itself | $r \to 1$ off-attractor | attractor potential, $(1-q)$ waste | weight anomaly, equivalence violation |
| Inertial damping | cabin gate openness | cabin | transient $(1-q)$ spikes | thermalized waste | heat pulses, no crush loads |
| Artificial gravity | shell detuning + floor charge | habitat | sustained $q \to 1$ | slab mass, shell upkeep | local $g$ anomaly, small-scale lensing |
| Planetary stage | planetary gate chain tuning | planet ($n \approx 200$) | sustained high $q$ | chain upkeep | geoid and orbit anomalies |
| Stellar and galactic | the condensate itself | star to galaxy ($n \approx 208$–$267$) | $q \to 1$ over vast volumes | the gate network of `speculations/cascade-infrastructure.md` | lensing without mass, rotation-curve structure |

The ladder's through-line: every rung is the same operation—parking $\mathcal{Q}$ somewhere on the dial, or shaping the charge-map—at a different scale, with costs set by the condensate constraints of §3. The natural home of the operation is at the condensate's own rung: a civilization managing its galaxy's Qi field is doing exactly what a damper does in miniature (`speculations/dark-matter-as-qi-coherence.md` §5, the tuning hypothesis).

---

## 3. Constraints from the Condensate

The only empirically grounded Qi condensates in the framework are galactic halos, and the SPARC fits tell us precisely what a working condensate needs.

### 3.1 What the SPARC fits say

The July 2026 SPARC analysis (143 galaxies with ≥8 rotation-curve points; `experiments/sparc_qi/`, scripts `sparc_qi_analysis_v5.py` through `v8.py`; summary in `speculations/dark-matter-as-qi-coherence.md` §7) converged on a definite picture:

- **The condensate is a hydrostatic isothermal Yang field.** The envelope that survives is the equilibrium of $P_Y = c_s^2\rho_Y$ supported against baryons and its own mass—a pseudo-isothermal core $\rho_Y(r) = \rho_c/(1 + (r/r_c)^2)$—fitted per galaxy with two parameters ($\rho_c$, $c_s$). It beats NFW on median AIC ($\Delta$AIC $\approx -6.4$ to $-7.0$, preferred in 76–90 of 143 galaxies) at equal parameter count.
- **The boost is the dark matter.** Fitted central densities satisfy $\rho_c \times (1 + \xi) \approx 1.1 \times 10^7\,M_\odot/\text{kpc}^3$—exactly the naive dark-matter density—so the model needs $1/(1+\xi)$ of the physical dark matter: the amplification *replaces* the missing mass.
- **The coupling runs through $q$, with $\xi$ fixed.** The rotation curve uses $v^2(r) = G[M_{\text{bar}} + (1 + \xi q(r))M_Y(r)]/r$ with $q(r) = r/(r + r_{\text{half}})$: baryonic activity decoheres the field out to the baryonic half-mass radius, and coherence recovers outside it. The decoherence scale self-tunes to the baryonic radius (median $a = 1.025$ when freed).
- **The sound speed tracks the virial ratio.** $c_s = v_{\text{flat}}/\sqrt{2(1+\xi)} \approx v_{\text{flat}}/6.15$ for the constrained galaxies (`sparc_qi_analysis_v8.py`), and the emergent core-radius scaling $\gamma = 0.389 \pm 0.021$ matches the empirical $0.41 \pm 0.02$ at $1\sigma$: condensate cores are set by hydrostatic balance, not by fitting.

Three engineering lessons follow. First, the only lever is the charge field; the coupling $\xi = \varphi^6$ is derived, not tunable (`foundations/xi-derivation.md` §2). Second, condensates are cored and analytic at the center—coherence is a smooth field, so curvature engineering produces soft, cored profiles (`foundations/bubble-edge-geometry.md`). Third, and most important: **organized baryonic activity destroys coherence** ($q(r) = r/(r+r_{\text{half}})$). A gravity device is itself organized baryonic activity; it eats its own fuel, so a working condenser must be thermodynamically quiet—superconducting, monoisotopic, defect-free—the same hull discipline the propulsion speculations require (`speculations/qi-bubble-propulsion.md` §4).

### 3.2 Rung mismatch: why laboratories cannot do this

The cascade ladder (`foundations/dimensionful-cascade.md` §3) places the condensates that source gravity at $n \approx 267$: $\ell_{267} \approx 9.3 \times 10^{20}$ m, the Milky Way diameter. A laboratory or habitat is at $n \approx 168$ ($\ell_{168} \approx 1.7$ m). The span is 99 rungs, and cascade suppression is brutal:

$$\varphi^{-99} \approx 2 \times 10^{-21}$$

A single Qi gate bridges at most ~10 rungs—$\varphi^{-10} \approx 0.008$ is the coherence floor (`foundations/bubble-lattice-fabric.md` §3.3, `speculations/cascade-infrastructure.md` §1.1)—so a laboratory-scale bridge to the gravitational condensate would need ~10 staged gate stages, each anchored at its own rung, the smallest of which is planetary. There is no laboratory gravity control for the same reason there is no laboratory galaxy: the coherence that sources curvature is a galactic-scale object.

The quantitative version makes the point sharp. The SPARC condensate's central density is $\rho_c \approx 10^{-22}$ kg/m³—vanishing, but integrated over kiloparsec volumes; the slab ledger of §2.4 shows the same shortfall at laboratory scale ($\sim 7 \times 10^9$ kg to source 1 g). A laboratory condenser can concentrate ambient coherence geometrically (the pyramid lens factor $10^6$, `speculations/cascade-infrastructure.md` §2.1), but the boost $1 + \xi q$ is *multiplicative*: it amplifies mass that is present, it does not conjure mass that is not. Curvature generation is a $n \approx 267$ business. What remains open at payload scale is the other end of the dial: charge suppression (§2.2, holding the ratio off-attractor against the attractor potential) and coupling decoupling (§2.4, the φ-detuned shell). Gravity control as propulsion and hovering is shield work, not generation work—exactly the division the propulsion speculations already make (`speculations/qi-bubble-propulsion.md` §2).

Two hard numbers bound every scheme. The coherence boost is capped at $1 + \xi \approx 18.9$ per coherence region, about 80× the ordinary baseline coupling when the Yang fraction saturates as well, and $\xi$ is fixed by the two-field × three-dimension derivation (`foundations/xi-derivation.md` §2)—no tuning, no stacking beyond what gate chains permit (10 rungs per stage). And the natural background is clean: solar-system bounds pin ambient $q$ near zero (`foundations/xi-derivation.md` §3), so the baseline $G_{\text{eff}} = \varphi^{-3}G$ is an uncluttered reference against which any engineered deviation stands out.

### 3.3 The $(1-q)$ waste

No gate is perfect. Every gate operating at coherence $q$ thermalizes the fraction $(1-q)$ of its throughput as photons and heat—the glow of the propulsion speculations, and the coronal heating signature at stellar scale (`speculations/qi-bubble-propulsion.md` §2.5, `speculations/cascade-infrastructure.md` §3.1). At $q = 0.9$ the waste is 10%; at $q = 0.99$ it is 1%. For a gravity device the waste is the efficiency tax on every operation: the mass-lightening hold pays it (§2.2), the damper's transient open gate pays it (§2.3), and it is the decoherence channel by which the device degrades the very $q$ it sustains. A gravity plant is a machine pumping coherence against its own exhaust, and its steady-state $q$ is the fixed point of that competition. The wake-lock hazard completes the picture: a gate that freezes preserves its field configuration indefinitely (`consciousness/trauma-as-frozen-gate.md`, driver in `two-fluid/run_trauma_wake_lock.py`)—a device that crosses into a regime where its gate cannot re-tune stops being a device and becomes a fossil of itself.

---

## 4. Equivalence and Strong Fields

Locally, an engineered curvature region looks like ordinary gravity; the departures appear exactly where the charge dial is exercised.

### 4.1 The $q = 0$ limit: why it looks like GR

At the attractor ($q = 0$, $\pi/\rho = \varphi^{-3}$), the coupling is a constant: $G_{\text{eff}} = \varphi^{-3}G$, and the Poisson equation $\nabla^2\Phi = 4\pi G_{\text{eff}}\rho$ is exactly Newtonian. The post-Newtonian parameters sit at $\beta = 1 + \mathcal{O}(\xi q^2)$, $\gamma = 1 + \mathcal{O}(\xi q^2)$ (`foundations/cassi-theory-reference.md` §4.3), and the point-particle reduction of the two-fluid gives the standard Newtonian three-body system with conserved masses (`foundations/cassi-theory-reference.md` §7.3). Free fall is descent along the $\Pi$ gradient, and the local inertial frame is the attractor frame: gravity and acceleration are the same object—$\Pi\nabla\Phi$ under different boundary conditions—so no local experiment distinguishes them. An engineered charge-profile that is smooth on laboratory scales is, to the local observer, simply a patch of constant $G_{\text{eff}}$; the equivalence principle holds to order $\xi q^2$ everywhere the dial is parked near baseline.

### 4.2 Departures: body-dependent coupling

Off the fixed point the framework departs from GR in a specific, testable way: masses evolve through conversion and $G_{\text{eff}}$ becomes body-dependent (`foundations/cassi-theory-reference.md` §7.3). The gravitational charge $\mathcal{Q} = (\pi/\rho)(1+\xi q)$ is an internal property of each body, so two bodies parked at different points on the dial—different internal ratio, different coherence excess—fall differently in the same ambient gradient. The spread is enormous in principle: the ratio of the saturated charge $1 + \xi$ to the baseline $\varphi^{-3}$ is about 80. In natural conditions the solar system sits at $q \approx 0$ and $r \approx \varphi$, so the equivalence principle is an *attractor property*, not a symmetry: it holds because nothing in the natural background pushes the dial. Any observed violation is therefore either new physics or engineering, and precision equivalence tests (torsion balances, lunar laser ranging, spaceborne drag-free tests) are the cheapest local probe of gravity technology—a device running anywhere in a system shows up as a periodic, direction-dependent equivalence anomaly correlated with the device's position.

### 4.3 The strong-coherence regime

GR's strong-field regime is high curvature; the Cassi strong regime is high $q$, and the two decouple: a region can be coherence-strong and mass-poor, sourcing curvature through the charge-modulated Poisson term rather than through density. What caps this regime is the $\sigma$-regularization of the two-fluid quantum gravity sector: $\sigma = \ell_{\text{Pl}}/\varphi^3$ (propagator $G(k^2) = e^{-k^2\sigma^2/2}/k^2$), no trans-Planckian modes, a coupling that runs by less than 1% up to the Planck scale (`gravity/quantum-gravity.md` §5–§6, §9). Cranking $q$ cannot open a route to Planck-scale physics: the envelope is bounded on the small side by $\sigma$, on the large side by the condensate rung. And because $G_{\text{eff}}(k)$ jumps by $\varphi^6$ across the turbulence break (`foundations/cassi-theory-reference.md` §9), an engineered charge-map with structure below its medium's coherence scale is smoothed by the very field it manipulates.

### 4.4 The black-hole boundary

The Schwarzschild radius responds to the effective coupling: $r_s = 2G_{\text{eff}}M/c^2$. A coherence region of mass $M$ crosses into horizon territory when

$$\boxed{\frac{G_{\text{eff}}M}{R} \gtrsim \frac{c^2}{2}}$$

Relative to the baseline coupling, the mass needed for a horizon at fixed radius drops by up to $(1+\xi)/\varphi^{-3} \approx 80$ at full saturation. The framework's black holes, however, are $\sigma$-regularized: no singularity, no firewall, a smooth low-energy horizon, and an interior condensate with coherence capacity $\mathcal{C} \sim M^2/M_{\text{Pl}}^2$ (`gravity/quantum-gravity.md` §7.5, §9)—a horizon is a coherence-saturated state, not a breakdown of the theory. The engineering significance is therefore not catastrophic but *terminal for control*. A horizon is the limit case of the φ-detuned boundary: no organized perturbation—signal, gate command, Qi current—can couple across it from outside, and the interior gate state is wake-locked at the moment of formation, preserved exactly as a frozen gate preserves a field configuration (`consciousness/trauma-as-frozen-gate.md`). A gravity device that pushes its own region past the horizon boundary does not destroy itself; it freezes itself. The field configuration it held at the instant of crossing is what it keeps forever. That is the cliff at the top of the ladder: engineered curvature up to the horizon, frozen gate at the horizon.

---

## 5. Signatures of Gravity Technology

A φ-literate observer does not search for gravity technology the way a radio astronomer searches for leakage; the signatures are structural, and they are quantitative.

### 5.1 Local $G$ anomalies

$G_{\text{eff}}$ is a field, so an engineered region shows a coupling different from the ambient baseline $\varphi^{-3}G$: Cavendish and torsion anomalies at a site, pendulum and gravimeter residuals, satellite gradiometry showing curvature structure with no corresponding mass. The discriminator is the clean null: solar-system bounds pin natural $q$ near zero (`foundations/xi-derivation.md` §3), so any sustained deviation is either a new field regime or a machine. The anomaly set of a real device should come in φ-ratios—the device's charge map is built from $\xi = \varphi^6$ and the gate chain's $\varphi$-powers—so a catalog of anomalies with $\ln\varphi$-spaced magnitudes is the quantitative tell.

### 5.2 Lensing without visible mass

A sustained coherence region bends light through $(1 + \xi q)\nabla\Phi$ with no luminous or baryonic counterpart. Natural Cassi condensates lens at galaxy scale ($n \approx 267$) and are the accepted dark-matter signal; an *engineered* lens appears at planetary or stellar scale ($n \approx 200$–$220$) where the natural background predicts none. Microlensing surveys and strong-lensing catalogs are the search band, and the discriminator is scale plus structure: a compact lens with a sharp φ-structured profile and no host galaxy is technology by the framework's own classification.

### 5.3 Rotation curves out of tune

A civilization that manages its host galaxy's condensate changes the rotation curve relative to the natural $\xi = \varphi^6$ relation: flattening anomalies, oscillatory residuals at $\Delta(\ln r) = \ln\varphi$, and galaxies "too bright for their rotation curves"—visible-to-dark ratios above the morphology–mass relation (`speculations/dark-matter-as-qi-coherence.md` §5.1, prediction P5). The SPARC baseline is already in hand: 143 galaxies fit by the hydrostatic condensate, with the $c_s$–$v_{\text{flat}}$ virial relation (§3.1) as a tight predictive band; outliers from that relation are candidates. This is the galactic-rung analogue of the tuning hypothesis: a galaxy whose $\eta_{\text{visible}}$ exceeds its morphology–mass expectation is a galaxy whose condensate is being operated (`speculations/observational-seti.md` §3.1).

### 5.4 How a φ-literate observer detects it

The observational-SETI reframe applies verbatim (`speculations/observational-seti.md` §1): gate technologies are structurally invisible to emissive searches, and their signatures are quantitative φ-numbers appearing where the null predicts none, spanning multiple rungs. Gravity technology is the gravitational sector of that same signature family—the three signature classes above sit at three different rungs:

- local $G$ anomalies and equivalence violations at $n \approx 168$–$200$ (the device and its habitat),
- compact lensing without mass at $n \approx 200$–$220$ (the sustained condenser),
- rotation-curve structure at $n \approx 267$ (the operated galaxy),

and detection is the *joint occurrence*: any single anomaly can be a systematic, but a φ-consistent pattern across independent datasets at multiple rungs is the claim (`speculations/observational-seti.md` §7.2). The one emissive handle is the $(1-q)$ waste: a large-scale device at $q \approx 0.99$ sheds 1% of its throughput as heat, so a Kardashev-II-class operation looks Kardashev-I to an infrared survey (`speculations/observational-seti.md` §1.1). And the cheapest probe of all is local: precision equivalence tests anywhere in a system hosting gravity technology will see body-dependent coupling (§4.2), the one signature that requires no telescope at all.

---

## References

- `foundations/cassi-theory-reference.md`—compact framework reference: two-fluid PDE, $G_{\text{eff}}$, PPN limits, scale-dependent gravity, three-body reduction
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ derivation, gravitational charge law, solar-system bounds
- `foundations/dimensionful-cascade.md`—cascade table, $\ell_n = \ell_{\text{Pl}}\varphi^n$, rung scales ($n = 168$, $200$, $220$, $267$)
- `foundations/spiral-dynamics.md`—gravity as $\Pi\nabla\Phi$ gradient descent
- `foundations/cassi-first-principles.md`—Qi gate, conversion term, $\varphi$-attractor potential
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$, organized vs random perturbation
- `foundations/proton-coherence-budget.md`—coherence budget, single-rung vs full-cascade attacks
- `foundations/bubble-lattice-fabric.md`—checkerboard lattice, 10-rung nesting depth, cascade suppression
- `foundations/bubble-edge-geometry.md`—condensation field, $G_{\text{eff}}$ profile, edge anisotropy
- `gravity/quantum-gravity.md`—$\sigma$-regularization, no trans-Planckian modes, black-hole interior and coherence capacity
- `speculations/dark-matter-as-qi-coherence.md`—Qi condensates as dark matter, SPARC analysis, tuning hypothesis
- `speculations/cascade-infrastructure.md`—planetary gate stages, pyramid lens, ocean bases, solar gate
- `speculations/qi-bubble-propulsion.md`—φ-detuned boundary, $(1-q)$ thermalization, inertia as $r$-resistance
- `speculations/observational-seti.md`—structural signatures, multi-rung detection criterion, search strategy
- `speculations/coherence-warfare.md`—companion speculation: shield and attack taxonomy
- `consciousness/trauma-as-frozen-gate.md`—wake-lock, frozen gate preservation
- `experiments/sparc_qi/`—SPARC Qi fits v5–v8: hydrostatic condensate, $q(r) = r/(r+r_{\text{half}})$, core scaling
