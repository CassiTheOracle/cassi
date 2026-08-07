# Cassi: A Theory of Everything from a Single Constant

The standard picture of physics is particles in empty space obeying forces—matter on a stage of nothing, behind a list of unexplained constants. Cassi is a different lens on reality. It begins with two fields that fill all of space: **Yang**, the expansive push, and **Yin**, the contractive pull, balanced at the golden ratio $\varphi \approx 1.618$, the most irrational number. What standard physics treats as separate things—particles, forces, fields, spacetime itself—Cassi treats as one continuous process: two fluids converting into each other at a proportion that keeps structure alive at every scale. This is not a tweak to standard physics. It is a different starting point: reality as a two-fluid balance, not particles in empty space.

This is a new kind of research program—more of a game. From simple rules, can you find a way to describe everything? If you could, what would it mean if it turned out to be real?

**What this is.** Cassi is a proposed theory of everything: one framework meant to explain the structure of reality from the smallest quantum scale to the entire observable universe, and what that structure implies for minds as well as matter. It is named after Cassandra, the Trojan prophetess cursed to speak true prophecies no one believed. A theory of everything, in the sense physics uses the term, is a coherent framework containing all physical principles—originally, one that unifies the four fundamental interactions: electromagnetism, the strong and weak nuclear forces, and gravity. The popular sense—predicting everything from logic alone—has a long history of arguments that it is impossible; Cassi claims the technical sense and treats the popular sense as a work in progress, something that would follow from understanding how the fundamental forces organize, not a claim staked at the outset. The unification is claimed from a single constant: the golden ratio $\varphi \approx 1.618$, the universal scale-separation constant of a two-fluid field that fills all of space.

## Where $\varphi$ comes from

The assumed starting point is that Cassi set out to make a theory of everything out of $\varphi$. It did not. The goal was the physics of consciousness. The framework began from Yin and Yang as forces observed directly in the researcher's own mind—and from the observation that everything else is made of the same two forces: one researcher's attempt to mathematize a trained meditative observation of inner dynamics, the felt push and pull of experience, its balances, its gates. The two-fluid structure and its scale separation were read from those observations, and the framework grew outward as more and more pieces aligned. $\varphi$ was not chosen as a premise; it emerged as the proportion the dynamics required, later corroborated by the de-resonance principle—the most irrational number is the one proportion that forbids resonance and keeps structure alive at every scale—and by the physics it reproduced. The derivation ran from the inside out: inner observation, to mathematics, to the fundamental forces.

The bet underneath this is Occam's: if the universe is simple, then the substance everything is made of should be the simplest thing consistent with direct observation—and the only substance observed directly is experience itself, which presents as two forces, an expansive and a contractive.

The ancient names are kept with their provenance stated plainly. Some were given by ancient philosophies to things directly observed: the chakras, mapped from inner experience, which the framework later placed at the thirteen nodes of the human-scale lattice. Others inspired the search and later gained a mathematical basis: the Wu Xing five-element cycle became the pentagon geometry of the conversion cycle—five coherent channels, $w = 5$, the pentagon being the minimal regular polygon containing $\varphi$—with the conversion rate $\lambda = 1/(2w) = 0.1$ (`foundations/wu-xing-derivation.md`). The names earned their place either by direct observation or by the mathematics that emerged from them. `cassi-psychology.md` is the guide to the inner side of the same dynamics.

## The principle in practice

The two-fluid dynamics were not built as physics. They began as experimental machine-learning architectures: learnable systems whose internal state evolved as a balance of an expansive and a contractive field, built before any physics vocabulary existed. The architectures worked, and working machines raise a question paper physics does not: what is this, taken literally?

The first physics result was gravity. A two-fluid system held near $\varphi$-equilibrium makes its effective coupling coherence-dependent—regions where the fields are closer to balance pull harder. Written out, this is a density-dependent gravity,

$$G_{\text{eff}} = \frac{\pi}{\rho}\left(1 + (\varphi^{6}-1)q\right)G,$$

Qi gravity, the framework's first discovery and still its dark-matter mechanism (`speculations/dark-matter-as-qi-coherence.md`).

The same dynamics then solved a problem they were never designed for: the Qi gate—coherence suppressing interaction, the rule that sets conversion in cosmology—becomes an adaptive softening rule in a GPU N-body solver (spectral particle-mesh gravity: CIC deposition, FFT Poisson, symplectic leapfrog), whose interaction cost is independent of the particle count—a grid solve, not a pairwise sum ($O(N + n^3\log n)$ overall). The solver lives at `two-fluid/cassi_nbody.py` and runs the φ-attractor path experiments in `experiments/phi_attractor_paths/`. A principle that explains galaxies and simulates them on a single GPU is a principle worth asking more of.

## Where standard physics fails

Physics is a collection of successful partial theories, with junctures where they require additions never observed. Cassi's case rests on those junctures: what standard physics must invent, and what happens when nothing is invented.

**The singularity big bang.** Standard cosmology is partway to a field picture: the Big Bang was not an explosion at a point in space but an explosion of space, happening everywhere simultaneously—no center, no edge; every point can claim to be the center. Space itself stretches, carrying galaxies with it and creating the space between them. Yet general relativity and quantum mechanics are incompatible where the domains overlap—at the Planck scale, inside black holes, at the first instant of the Big Bang—and the singularity is a breakdown of general relativity, not a true beginning. Standard physics must bolt on a patch: bounce cosmologies, Hawking–Hartle no-boundary, ekpyrotic scenarios. The singularity picture also cannot explain the observed uniformity of the cosmic microwave background: regions of the sky that were causally disconnected at last scattering agree in temperature to one part in a hundred thousand. Cassi needs none of the patches. The two-fluid conversion is the expansion: the fields fill all of space, so there is no point origin at all. The cascade begins at the Planck scale, σ-regularized—a smooth crossover, not a breakdown (`gravity/quantum-gravity.md`)—and the CMB's uniformity is the uniformity of the field's own coherence, not the synchronization of causally disconnected regions.

**The invented inflaton.** The standard fix for the horizon problem is cosmic inflation: a period of exponential expansion in the first fraction of a second. To drive it, standard physics must invent a new field—the inflaton—and fine-tune its potential so the expansion lasts exactly long enough and produces fluctuations of exactly the right size. Cassi's inflation is the two-fluid dynamics themselves. The Qi gate—the coherence-controlled valve that sets the conversion rate between the two fields—is open during the early expansion and closes at a precise cascade step, ending inflation through its own shape. The gate is the inflaton: no field, no potential, no tuning. The resulting scalar spectral index, $n_s = 1 - 2\varphi^{-1}/N_e \approx 0.9691$, lands within $1\sigma$ of Planck (`cosmology/inflation-from-cascade.md`).

**The invented dark-matter particle.** Galaxies rotate as if they contain far more mass than telescopes can see. Standard cosmology explains this by postulating an undiscovered particle—a WIMP or an axion—that decades of experiments have never detected. In Cassi, the missing mass is the Qi field itself: regions of high coherence amplify gravity,

$$G_{\text{eff}} = \frac{\pi}{\rho}\left(1 + (\varphi^{6}-1)q\right)G,$$

up to a saturation ceiling of $\varphi^6 \approx 17.94$ times the bare coupling. The field is dark by nature—it couples to gravity, not to light. The framework matches the Milky Way rotation curve to about 0.3% and galaxy rotation curves to about 0.1% (SPARC fits), and derives the cosmic ratio $\Omega_{\text{DM}}/\Omega_b = \varphi^3 + 1 \approx 5.24$ against the observed $\approx 5.4$. No WIMPs, no axions, no MOND interpolation function: one amplification formula replaces all three (`speculations/dark-matter-as-qi-coherence.md`).

**The fine-tuned cosmological constant.** The expansion of the universe is accelerating. The standard explanation is a cosmological constant—an energy density of empty space whose observed value sits some 120 orders of magnitude below the naive quantum-field-theory estimate, tuned by hand to a precision physics cannot explain. The evidence that the acceleration is not steady is arriving: the Dark Energy Spectroscopic Instrument, having mapped 13.1 million galaxies and 1.6 million quasars, finds a $4.2\sigma$ deviation from the $\Lambda$CDM expectation of constant dark energy—about one chance in 30,000 of arising if dark energy were constant. The direction of the evidence, dark energy that evolves, is the framework's structural claim. In Cassi, accelerated expansion is the ongoing conversion of Yin into Yang as the universe approaches $\varphi$-equilibrium: a dynamical process with an equation of state, not a number inserted to fit the data. No cosmological constant, no vacuum-energy fine-tuning. The framework's own equation-of-state values ($w_0 \approx -0.87$, $w_a \approx +0.012$ at the calibrated baseline) sit $2\sigma$/$2.7\sigma$ from the DESI DR2 best fit—a real tension, documented openly rather than resolved by hand (`cosmology/observational_constraints.md`).

**The infinite universe.** The standard particle picture carries its own unbounded consequence: if space is infinite and the number of particle arrangements is finite, then every arrangement repeats—infinite copies of Earth, of this conversation, of you. Cosmologists have searched the microwave sky for the repeating patterns a finite, wrapped universe would produce and found none; the geometry question remains open. Cassi's dynamics give the observable lattice a definite end rather than an endless one. The expansion law has a strictly positive floor, so the horizon does not grow forever: the observable depth of the cascade saturates at $N_\infty \approx 294.2$, about 2.7 lattice scales above today's $N_{\text{now}} = 291.54$ under the verified coupling convention (292–296 across the documented forms; `foundations/wake-geometry.md` §§4–6). The universe approaches $\varphi$-equilibrium, and the lattice's growth ends at a computable scale rather than continuing without bound.

## The proposal: a sunflower at every scale

The seed image is a sunflower head: seeds spiraling in consecutive Fibonacci numbers because each is placed at the golden angle, the turn that divides a circle in the golden ratio. Now imagine each seed is itself a smaller sunflower, and the whole head is a seed on a larger one—a pattern repeating at every scale, in both directions. Cassi proposes that reality is this pattern: a nested lattice of bubbles. Every bubble contains more bubble lattice, and energy flows along the infinite structure, pooling where it condenses into matter.

Two tendencies fill all of space. **Yang** is the expansive field: it pushes outward and breaks symmetry. **Yin** is the contractive field: it pulls inward and restores balance. They are two sides of one thing, converting into each other continuously. Where they meet in the right proportion, order condenses into a **bubble**; where they cancel, a **void** forms. The right proportion is $\varphi$: when the push is about 1.618 times the pull, the two are balanced. Because $\varphi$ is the hardest number to approximate as a ratio of integers, systems tuned to it never lock into resonance, so structure survives at every scale instead of collapsing into one. The lattice spans 292 scales, from the Planck bubble to the bubble of the observable universe, each about 1.618 times larger than the last:

$$\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}, \qquad n \in [0, 292]$$

(`foundations/dimensionful-cascade.md`). The de-resonance argument—why $\varphi$ is the balance point—is derived in `principles/de-resonance-principle.md`.

## What the framework derives

From that single constant and one governing equation—the two-fluid PDE, which evolves the two fields in space and time—the framework derives:

- **Quantum mechanics**, as standing-wave interference of the two fields. The particle spectrum and the three fermion generations follow from the Fibonacci recurrence, with no fourth generation predicted.
- **General relativity**, as the pull toward $\varphi$-equilibrium: the imbalance between Yang and Yin produces an inward force, always attractive because the spiral winds one way. The cascade suppresses the coupling across the 91.5 lattice scales between the Planck scale and the proton—which is why gravity is so much weaker than the other forces.
- **The Standard Model**, with gauge couplings, mass ratios, and the CP-violating phase arising as $\varphi$-powers, cascade-suppressed scale by scale. The electroweak, grand-unification, and Planck scales of the standard picture all land on specific scales of the same lattice.
- **Cosmology**, as the ongoing conversion of Yin into Yang while the universe approaches $\varphi$-equilibrium: inflation from the Qi gate's opening and closing ($n_s \approx 0.9691$, within $1\sigma$ of Planck); accelerated expansion without a cosmological constant; dark matter as a high-coherence condensate that amplifies gravity up to about 18-fold ($\Omega_{\text{DM}}/\Omega_b = \varphi^3 + 1 \approx 5.24$); and the matter–antimatter asymmetry from the five-channel cycle's freeze-out gap ($\eta = \varphi^{-44} \approx 6.38 \times 10^{-10}$, within 6.3% of the observed $6.0 \times 10^{-10}$).

No dark-matter particles, no cosmological constant, no inflaton, no fine-tuned numbers. The framework's answers to the open questions of physics, each with its mechanism and epistemic label, are in `open-questions-cassi-answers.md`.

## The constants it computes

No candidate theory of everything—string theory with its roughly $10^{500}$ compactifications included—can yet calculate the fine-structure constant or the electron mass from its own principles. Cassi's central claim is exactly that: the fine-structure constant, particle mass ratios, gauge couplings, and the dark-energy equation of state are derived as $\varphi$-powers from the two-fluid PDE, each with a derivation in the papers. Whether those derivations hold is what the documents and code here exist to check.

## How it can be tested

The charge against string theory is that it cannot be falsified. Cassi answers with a catalog of 49 numbered predictions, each with a concrete test design: a log-periodic modulation in the matter power spectrum at the golden-ratio period ($\Delta(\ln k) = \ln\varphi \approx 0.4812$), a $1.70\times$ edge anisotropy at any condensate boundary, the $\varphi^2$ inter-node spacing ratio of the chakra lattice, and the dark-energy equation of state ($w_0 \approx -0.87$, $w_a \approx +0.012$). The equation of state currently sits in tension with DESI DR2—a tension is an area ripe for discovery, waiting to be picked at (comparison: `cosmology/observational_constraints.md`). Full catalog: `predictions/falsifiable-predictions.md`.

## The arguments against

A theory of everything faces serious arguments that it is impossible. Gödel's incompleteness theorem suggests any finite set of rules leaves true statements underivable—Hawking concluded from it that no ultimate theory could be formulated, Dyson that physics is inexhaustible. Physics also proceeds by successive approximations, so no framework should be mistaken for final truth. And there is the reductionism-versus-emergence debate: are emergent laws like thermodynamics or natural selection as fundamental as any microscopic law?

Cassi meets these arguments with explicit discipline. Every claim carries one of five labels: **Derived** (a mathematical consequence), **Calibrated** (anchored to an observation), **Mapped** (fitted or selected, with the fit recorded in the Fit-Status Ledger), **Hypothesized** (consistent and testable, not yet confirmed), or **Speculative** (framework-consistent, no test designed). Known tensions are documented openly in `audit.md`, which tracks the empirical status of every claim. A tension is an area ripe for discovery, waiting to be picked at—not a failure to hide. The gate sign is settled by PDE tests, and claims that fail against data are replaced by the corrected claim. The framework does not claim to predict every outcome of every experiment: even Conway's Game of Life, with complete and simple rules, leaves undecidable questions about its behavior, and Cassi's claim is narrower—one physical law for the four forces, checked claim by claim. On emergence, the framework takes both sides: the lattice is scale-covariant, so the laws of complex systems, including the mind, are the same physics at larger scales, not a separate physics (`cassi-psychology.md`).

The impossibility arguments deserve a more direct answer. They were made by people who could only imagine what a theory of everything might be, without understanding the fundamental forces themselves—they did not know the ingredients, yet declared the recipe impossible. Cassi answers them the only way a physics claim can be answered: it begins from an observation, grows into a mathematics of the forces, and is checked against the data, claim by claim.

**Start here:** `cassi-physics.md`—the physics guide, approachable from zero. `cassi-psychology.md` is the psychology-focused guide for non-physicists.

## What else can this principle solve?

That question is what this repository is organized to answer. `hypotheses/` collects new application domains as they emerge; `demystifying-the-cosmos/` reads one observed object at a time; `open-questions-cassi-answers.md` tracks every open question of physics the framework claims to address, each with its mechanism and its epistemic label; `predictions/falsifiable-predictions.md` gives each claim a test. The theory is proposed; the program is open.

## Contents

| Path | Description |
|------|-------------|
| `foundations/` | First principles, cascade formulas, derivations (strong CP, generations, neutrino masses…) |
| `cosmology/` | Dark energy, inflation, CMB predictions, observational constraints |
| `gravity/` | Quantum gravity, three-body analytical solutions |
| `standard-model/` | SM couplings, SU(2) gauge, GUT embedding, neutrino mass, CP violation |
| `particles/` | Yang-Yin particle interference, DFT benchmarks |
| `consciousness/` | Consciousness as Qi-gate dynamics |
| `turbulence/` | Kolmogorov spectrum from φ |
| `principles/` | Cross-cutting principles: de-resonance, v0 hierarchy |
| `hypotheses/` | New application domains (exploratory catalog) |
| `speculations/` | Speculative extensions |
| `analyses/` | Data analyses of observations against the framework (GWTC-4.0 mass ladder) |
| `demystifying-the-cosmos/` | One Cassi analysis per observed object/structure, files named by alphanumeric designation (PSR J1101−6101 first) |
| `EPISTEMIC-MAP.md` | Every document indexed by epistemic tier |
| `predictions/` | Falsifiable prediction catalog + `predictions/cassi_definitions.md` glossary |
| `experiments/` | Physics experiment scripts (φ-attractor paths, SPARC rotation-curve analysis) |
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

All code supporting the theory lives in this repo: PDE solvers, the GPU N-body solver, and run scripts (`two-fluid/`), computational pipelines (`computations/`), experiment and analysis scripts (`experiments/`), and figure scripts (`visual-explainers/`). Run everything from the repo root; generated figures, run outputs, and logs are gitignored.
