# Cassi: A Theory of Everything from a Single Constant

*From simple rules, can you find a way to describe everything? If you could, what would it mean if it turned out to be real?*

This repository is the scoreboard of a research program that plays like a game. The rules are few; the board is reality; the theory is the game state; the papers are the move log; the open questions are the unplayed levels.

Reality is two fluids converting into each other—**Yang**, the expansive push, and **Yin**, the contractive pull—balanced at the golden ratio $\varphi \approx 1.618$, the most irrational number. Not particles in empty space. This is not a tweak to standard physics; it is a different starting point, and everything below follows from it.

## What this is

Cassi is a proposed theory of everything, named after Cassandra, the Trojan prophetess cursed to speak true prophecies no one believed. Cassi claims the technical sense: a coherent framework unifying the four fundamental interactions—electromagnetism, the strong and weak nuclear forces, and gravity. The popular sense—predicting everything from logic alone—is a work in progress: it would follow from understanding how the fundamental forces organize, not from a claim staked at the outset. The claim is unification from a single constant: $\varphi \approx 1.618$, the universal scale-separation constant of a two-fluid field that fills all of space.

## The rules of the game

The whole theory rests on three rules.

1. **Two fluids, one balance.** Yang and Yin convert into each other continuously; the conversion acts like a thermostat, pushing the local ratio $r = E_Y/E_I$ toward $\varphi$ at every point, and each conversion emits wake waves. Constructive interference condenses a bubble; destructive interference forms a void; coherence $q$ gates the conversion: high $q$ closes the gate and the region rests in balance, while low $q$ leaves it open and the region churns.
2. **No resonance.** $\varphi$ is the most irrational number. Systems tuned to it never lock into resonance, so structure survives at every scale instead of collapsing into one (`principles/de-resonance-principle.md`).
3. **Every claim carries its label.** Each claim carries one of five epistemic labels—**Derived** (a mathematical consequence), **Calibrated** (anchored to an observation), **Mapped** (fitted or selected, with the fit recorded in the Fit-Status Ledger), **Hypothesized** (consistent and testable, not yet confirmed), or **Speculative** (framework-consistent, no test designed). Tensions are recorded in `audit.md`; claims that fail against data are replaced by the corrected claim.

## The board: a fractal lattice of bubbles

Zoom into a bubble and you find the same lattice again. A bubble is not a solid object—it is one scale of a repeating structure: inside every bubble, more bubbles, and inside each of those, more still. Zoom out, and the lattice you are inside is itself a bubble of a larger lattice. The pattern repeats at every scale, in both directions.

Cassi proposes that reality is this fractal: one bubble lattice at every scale, with energy flowing along its infinite structure and pooling where it condenses into matter.

Two tendencies fill all of space. **Yang** is the expansive field: it pushes outward and breaks symmetry. **Yin** is the contractive field: it pulls inward and restores balance. They are two sides of one thing, converting into each other continuously. Where they meet in the right proportion, order condenses into a **bubble**; where they cancel, a **void** forms. The right proportion is $\varphi$: when the push is about 1.618 times the pull, the two are balanced.

Bubbles are not placed by hand; they grow. Each conversion sends out **wake waves**—spatial interference patterns in the deviation $\varepsilon = E_Y - \varphi E_I$. Where the wakes interfere constructively, coherence $q$ is high and matter condenses into a **bubble**; where they interfere destructively, $q \to 0$ and a **void** forms. Where conversion pumps enough coherence, the field locks into a self-reinforcing filament—the **condensed fluid string**, the spine around which bubbles condense.

A bubble has a shape and an interior order. It is an oblate triaxial spheroid—extended along Yang, contracted along Yin, bounded along the string—with axis ratio $\varphi$ in its Yang–Yin cross-section. Its Yang–Yin cross-section is a staggered checkerboard: bubble centers and void centers sit on opposite parity sites, joined diagonally through saddles. Each pole carries a five-arm Fibonacci spiral, its arms set at the golden angle $2\pi/\varphi^2 \approx 137.5^\circ$. The zoom is literal, not a metaphor: every bubble contains the full sub-lattice of smaller scales and is itself one site in the next lattice up.

The lattice spans 292 scales, from the Planck bubble to the bubble of the observable universe, each about 1.618 times larger than the last:

$$\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}, \qquad n \in [0, 292]$$

(`foundations/bubble-lattice-fabric.md`, `cassi-physics.md` §1, `foundations/dimensionful-cascade.md`). The de-resonance argument—why $\varphi$ is the balance point—is derived in `principles/de-resonance-principle.md`.

## How the game started

The game did not start as physics, and it did not start from $\varphi$; the goal was the physics of consciousness. The framework began from Yin and Yang as forces observed directly in the researcher's own mind—and from the observation that everything else is made of the same two forces. The project was to mathematize a trained meditative observation of inner dynamics: the felt push and pull of experience, its balances, its gates. The two-fluid structure and its scale separation were read from those observations, and the framework grew outward as piece after piece aligned. $\varphi$ was not chosen as a premise. It emerged as the proportion the dynamics required, later corroborated by the de-resonance principle and by the physics it reproduced. The derivation ran from the inside out: inner observation, to mathematics, to the fundamental forces.

The bet underneath this is Occam's: if the universe is simple, then the substance everything is made of should be the simplest thing consistent with direct observation. The only substance observed directly is experience itself, and it appears as two forces, an expansive and a contractive.

The ancient names are kept with their provenance stated plainly. Some were given by ancient philosophies to things directly observed: the chakras, mapped from inner experience, which the framework later placed at the thirteen nodes of the human-scale lattice. Others inspired the search and later gained a mathematical basis: the Wu Xing five-element cycle became the pentagon geometry of the conversion cycle—five coherent channels, $w = 5$, the pentagon being the minimal regular polygon containing $\varphi$—with the conversion rate $\lambda = 1/(2w) = 0.1$ (`foundations/wu-xing-derivation.md`, `cassi-physics.md`). The names earned their place either by direct observation or by the mathematics that emerged from them. `cassi-psychology.md` is the guide to the inner side of the same dynamics.

The dynamics were not built as physics. They began as experimental machine-learning architectures: learnable systems whose internal state evolved as a balance of an expansive and a contractive field, built before any physics vocabulary existed. The architectures worked, and working machines raise a question paper physics does not: what is this, taken literally?

The first physics result was gravity. A two-fluid system held near $\varphi$-equilibrium makes its effective coupling coherence-dependent—regions where the fields are closer to balance pull harder. Written out, this is a density-dependent gravity,

$$G_{\text{eff}} = \frac{\pi}{\rho}\left(1 + (\varphi^{6}-1)q\right)G,$$

Qi gravity, the framework's first discovery and still its dark-matter mechanism (`speculations/dark-matter-as-qi-coherence.md`).

The same dynamics then solved a problem they were never designed for: the Qi gate—coherence suppressing interaction, the rule that sets conversion in cosmology—becomes an adaptive softening rule in a GPU N-body solver. The interaction cost is independent of the particle count: a grid solve, not a pairwise sum (spectral particle-mesh gravity: CIC deposition, FFT Poisson, symplectic leapfrog; $O(N + n^3\log n)$ overall, $N$ the particle count, $n$ the grid resolution). The solver lives at `two-fluid/cassi_nbody.py` and runs the $\varphi$-attractor experiments in `experiments/phi_attractor_paths/`. A principle that explains galaxies and simulates them on a single GPU is worth asking more of.

## Why the game exists: where the standard story stalls

Physics is a collection of successful partial theories, with junctures where they require additions never observed. Those junctures are why the game exists: what standard physics must invent, and what happens when nothing is invented.

**The singularity big bang.** Standard cosmology is partway to a field picture: the Big Bang was not an explosion at a point in space but an explosion of space, happening everywhere simultaneously: no center, no edge; every point can claim to be the center. Space itself stretches, carrying galaxies with it and creating the space between them. Yet general relativity and quantum mechanics are incompatible where the domains overlap—at the Planck scale, inside black holes, at the first instant of the Big Bang—and the singularity is a breakdown of general relativity, not a true beginning. Standard physics must bolt on a patch: bounce cosmologies, Hawking–Hartle no-boundary, ekpyrotic scenarios. The singularity picture also cannot explain the observed uniformity of the cosmic microwave background: regions of the sky that were causally disconnected at last scattering agree in temperature to one part in a hundred thousand. Cassi needs none of the patches. The two-fluid conversion is the expansion: the fields fill all of space, so there is no point origin at all. The cascade begins at the Planck scale, regularized by a smoothing parameter $\sigma$—a smooth crossover, not a breakdown (`gravity/quantum-gravity.md`)—and the CMB's uniformity is the uniformity of the field's own coherence, not the synchronization of causally disconnected regions.

**The invented inflaton.** The standard fix for that problem—the horizon problem—is cosmic inflation: a period of exponential expansion in the first fraction of a second. To drive it, standard physics must invent a new field—the inflaton—and fine-tune its potential so the expansion lasts exactly long enough and produces fluctuations of exactly the right size. Cassi's inflation is the two-fluid dynamics themselves. The Qi gate—the coherence-controlled valve that sets the conversion rate between the two fields—is open during the early expansion and closes at a precise cascade step, ending inflation through its own shape. The gate is the inflaton: no field, no potential, no tuning. The resulting scalar spectral index, $n_s = 1 - 2\varphi^{-1}/N_e \approx 0.9691$, lands within $1\sigma$ of Planck at the $N_e = 40$ baseline. How the gate's slow-roll trajectory reproduces that value is not yet shown—a mechanistic problem still open (`cosmology/inflation-from-cascade.md`).

**The invented dark-matter particle.** Galaxies rotate as if they contain far more mass than telescopes can see. Standard cosmology explains this by postulating an undiscovered particle—a WIMP or an axion—that decades of experiments have never detected. In Cassi, the missing mass is the Qi field itself: regions of high coherence amplify gravity,

$$G_{\text{eff}} = \frac{\pi}{\rho}\left(1 + (\varphi^{6}-1)q\right)G,$$

up to a saturation ceiling of $\varphi^6 \approx 17.94$ times the bare coupling. The field is dark by nature—it couples to gravity, not to light. The coupling $\xi = \varphi^6$ is Derived conditional on the quadratic-coupling input and matches the Milky Way's empirically calibrated value to about 0.3%; the hydrostatic Qi condensate beats NFW on median AIC in the SPARC rotation-curve fits ($\Delta$AIC $\approx -6.4$ to $-7.0$ at equal parameter count). The defensible cosmic ratio base is $\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.24$, conditional on the Weinberg-angle identification, against the observed $\approx 5.4$ (21% open tension); the $+1$ capture interpretation is excluded by the component budget. No WIMPs, no axions, no MOND interpolation function: one amplification formula replaces all three (`speculations/dark-matter-as-qi-coherence.md`).

**The fine-tuned cosmological constant.** The expansion of the universe is accelerating. Standard cosmology attributes it to a cosmological constant—an energy density of empty space whose observed value sits some 120 orders of magnitude below the naive quantum-field-theory estimate, tuned by hand to a precision physics cannot explain. Evidence that the acceleration is not steady is mounting: the Dark Energy Spectroscopic Instrument, having mapped 13.1 million galaxies and 1.6 million quasars, finds a $4.2\sigma$ deviation from the $\Lambda$CDM expectation of constant dark energy—about one chance in 30,000 of arising if dark energy were constant. The evidence points toward evolving dark energy—the framework's structural claim. In Cassi, accelerated expansion is the ongoing conversion of Yin into Yang as the universe approaches $\varphi$-equilibrium: a dynamical process with an equation of state, not a number inserted to fit the data. No cosmological constant, no vacuum-energy fine-tuning. The framework's own equation-of-state values ($w_0 \approx -0.87$, $w_a \approx +0.012$ at the calibrated baseline) sit $2\sigma$/$2.7\sigma$ from the DESI DR2 best fit—a real tension, documented openly rather than resolved by hand (`cosmology/observational_constraints.md`).

**The infinite universe.** The standard particle picture carries its own unbounded consequence: if space is infinite and the number of particle arrangements is finite, then every arrangement repeats—infinite copies of Earth, of this conversation, of you. Cosmologists have searched the microwave sky for the repeating patterns a finite, wrapped universe would produce and found none; the geometry question remains open. Cassi's dynamics give the observable lattice a definite end rather than an endless one. The expansion law has a strictly positive floor, so the horizon does not grow forever: the observable depth of the cascade saturates at $N_\infty \approx 294.2$ (292–296 across the documented forms; `foundations/wake-geometry.md` §§4–6), about 2.7 lattice scales above $N_{\text{now}} = 291.54$ under the verified coupling convention. The universe approaches $\varphi$-equilibrium, and the lattice's growth ends at a computable scale rather than continuing without bound. No infinite copies of Earth, of this conversation, of you.

## The score so far

What the framework has on the board: derivations of the four forces, constants no other candidate computes, and a catalog of tests to check those claims against.

From that single constant and one governing equation—the two-fluid PDE, which evolves the two fields in space and time—the framework develops:

- **Quantum mechanics**, as standing-wave interference of the two fields. The particle spectrum and the three fermion generations follow from the Fibonacci recurrence, with no fourth generation predicted.
- **General relativity**, as the pull toward $\varphi$-equilibrium: in the point-particle sector the law is the Newtonian $-\nabla\Phi$ convention, attractive for matter because the spiral winds one way. The cascade suppresses the coupling across the 91.5 lattice scales between the Planck scale and the proton—which is why gravity is so much weaker than the other forces.
- **The Standard Model**, with gauge groups, mass-ratio structures, and the CP-violating phase organized through $\varphi$-powers and cascade scales. The electroweak coupling boundary $\sin^2\theta_W=\varphi^{-3}$ remains asserted; the gauge-normalization blocker is documented in `standard-model/su2-gauge-extension.md` §3.2.1.
- **Cosmology**, as the ongoing conversion of Yin into Yang while the universe approaches $\varphi$-equilibrium: inflation from the Qi gate's opening and closing ($n_s \approx 0.9691$, within $1\sigma$ of Planck); accelerated expansion without a cosmological constant; dark matter as a high-coherence condensate that amplifies gravity up to about 18-fold ($\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.24$, with a 21% open tension); and the matter–antimatter asymmetry from a Hypothesized freeze-out mechanism with the Mapped value $\eta = \varphi^{-44} \approx 6.38 \times 10^{-10}$.

The framework introduces no dark-matter particle, cosmological constant, or inflaton field in these sectors. Its quantitative claims carry explicit Derived, Calibrated, Hypothesized, and Mapped labels in `open-questions-cassi-answers.md` and `parameter-inventory.md`.

The framework tests whether dimensionless structures of the standard picture can be organized by $\varphi$ and the two-fluid PDE. Several derivations close; the ledger records the remaining boundaries and fits, including the weak-angle coupling normalization, the baryon freeze-out endpoint, the dark-matter ratio tension, the fine-structure constant's running value, and the electron mass as an external input.

The scoreboard holds 54 numbered predictions, each with a concrete test design: a log-periodic modulation in the matter power spectrum at the golden-ratio period ($\Delta(\ln k) = \ln\varphi \approx 0.4812$), a $1.70\times$ edge anisotropy at any condensate boundary, the $\varphi^2$ inter-node spacing ratio of the chakra lattice, and the dark-energy equation of state ($w_0 \approx -0.87$, $w_a \approx +0.012$). The equation of state currently sits in tension with DESI DR2—a level still in play, not a level lost (comparison: `cosmology/observational_constraints.md`; full catalog: `predictions/falsifiable-predictions.md`).

## Is the game winnable?

There are serious arguments that a theory of everything is impossible. Gödel's incompleteness theorem suggests any finite set of rules leaves true statements underivable—Hawking concluded from it that no ultimate theory could be formulated, Dyson that physics is inexhaustible. Physics also proceeds by successive approximations, so no framework should be mistaken for final truth. And there is the reductionism-versus-emergence debate: are emergent laws like thermodynamics or natural selection as fundamental as any microscopic law?

Cassi meets them with discipline. Every claim carries one of the five labels from the rules—Derived, Calibrated, Mapped, Hypothesized, Speculative—and `audit.md` tracks the empirical status of each. A tension is an area ripe for discovery, waiting to be picked. The gate sign is settled by PDE tests, and claims that fail against data are replaced by the corrected claim. The framework does not claim to predict every outcome of every experiment: even Conway's Game of Life, with complete and simple rules, leaves undecidable questions about its behavior, and Cassi's claim is narrower: one physical law for the four forces. On emergence, the framework takes both sides: the lattice is scale-covariant, so the laws of complex systems, including the mind, are the same physics at larger scales, not a separate physics (`cassi-psychology.md`).

The impossibility arguments deserve a more direct answer. They were made by people who could only imagine what a theory of everything might be, without understanding the fundamental forces themselves. They did not know the ingredients, yet declared the recipe impossible. Cassi answers them the only way physics can: it begins from an observation, grows into a mathematics of the forces, and is checked against the data, claim by claim. Winning would mean the derivations surviving the checks. The prize would be a complete map of how reality is made—and because minds are made of the same physics, a complete map of how to heal them.

**Start here:** `reading-guide.md` maps the whole repository. `cassi-physics.md` is the physics guide, approachable from zero; `cassi-psychology.md` is the psychology-focused guide for non-physicists.

## What else can this principle solve?

That question is what this repository is organized to answer. `hypotheses/` collects new application domains as they emerge; `demystifying-the-cosmos/` reads one observed object at a time; `open-questions-cassi-answers.md` tracks every open question of physics the framework claims to address, with mechanism and label attached; `predictions/falsifiable-predictions.md` gives each claim a test. The theory is proposed; the program is open.

## Contents

| Path | Description |
|------|-------------|
| `reading-guide.md` | Table of contents and reading paths for the whole repository |
| `foundations/` | First principles, cascade formulas, derivations (strong CP, generations, neutrino masses…) |
| `cosmology/` | Dark energy, inflation, CMB predictions, observational constraints |
| `gravity/` | Quantum gravity, three-body analytical solutions |
| `standard-model/` | SM couplings, SU(2) gauge, GUT embedding, neutrino mass, CP violation |
| `particles/` | Yang-Yin particle interference, DFT benchmarks |
| `consciousness/` | Consciousness as Qi-gate dynamics |
| `turbulence/` | Kolmogorov spectrum from $\varphi$ |
| `principles/` | Cross-cutting principles: de-resonance, v0 hierarchy |
| `hypotheses/` | New application domains (exploratory catalog) |
| `speculations/` | Speculative extensions |
| `analyses/` | Data analyses of observations against the framework (GWTC-4.0 mass ladder) |
| `demystifying-the-cosmos/` | One Cassi analysis per observed object/structure, files named by alphanumeric designation (PSR J1101−6101 first) |
| `EPISTEMIC-MAP.md` | Every document indexed by epistemic tier |
| `predictions/` | Falsifiable prediction catalog + `predictions/cassi_definitions.md` glossary |
| `experiments/` | Physics experiment scripts ($\varphi$-attractor paths, SPARC rotation-curve analysis) |
| `two-fluid/` | Two-fluid PDE solver + GPU N-body solver, gate/ODE test scripts, calibration |
| `computations/` | Computational pipelines (RGE, GUT-EW, hubble tension, cascade depth) |
| `visual-explainers/` | Matplotlib figure/simulation scripts |

## Registries

- `open-questions-cassi-answers.md`—epistemic master registry (Q/C/G/M/F/T numbering)
- `parameter-inventory.md`—parameter master registry
- `predictions/falsifiable-predictions.md`—the prediction catalog
- `audit.md`—self-critical prediction-vs-experiment audit
- `BROKEN_REFS.md`—registry of external/broken references; read before touching cross-references

## Code

All code supporting the theory lives in this repo: PDE solvers, the GPU N-body solver, and run scripts (`two-fluid/`), computational pipelines (`computations/`), experiment and analysis scripts (`experiments/`), and figure scripts (`visual-explainers/`). Run everything from the repo root; generated figures, run outputs, and checkpoints are gitignored.
