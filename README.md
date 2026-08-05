# Cassi: A Theory of Everything from a Single Constant

Note: This repo is the product of a single researcher, working with AI tools to convert lived experience and conceptual geometry to mathematics and code. Currently, everything here is entirely AI-generated. Its contents have the potential to fundamentally change the way we understand reality, so I have deemed delaying its release, until my own writings have been added, to be a degree of perfectionism that impedes progress. So, without further ado, please enjoy humanity's first (and last?) Theory of Everything.  

 \- Carina

## What this is

Cassi is a proposed theory of everything: one framework meant to explain the structure of reality from the smallest quantum scale to the entire observable universe, and what that structure implies for minds as well as matter. It is named after Cassandra, the Trojan prophetess of Greek myth, who was cursed to speak true prophecies that no one believed.

A theory of everything, in the sense physics uses the term, is a coherent framework containing all physical principles—originally, one that unifies the four fundamental interactions: electromagnetism, the strong and weak nuclear forces, and gravity. The popular sense of the phrase—predicting everything in the universe from logic alone—comes with a long history of arguments that it is not possible; Cassi claims the technical sense. It claims the unification from a single constant: the golden ratio $\varphi \approx 1.618$, the most irrational number in mathematics, used as the universal scale-separation constant of a two-fluid field that fills all of space.

## The search Cassi enters

Physics has climbed most of the way up the unification ladder. Newton unified terrestrial with celestial gravity; Maxwell unified electricity and magnetism; the electroweak theory unified the electromagnetic and weak forces; the Standard Model brought in the strong force. One step remains: gravity. General relativity and quantum mechanics are each enormously successful in their own domains, but they are incompatible where the domains overlap—at the Planck scale, inside black holes, at the first instant of the Big Bang. Finding the deeper framework that reconciles them is one of the major unsolved problems in physics.

The leading candidate, string theory, proposes vibrating strings in ten or eleven dimensions, but its extra dimensions can be curled up in an estimated 10^500 different ways, and critics argue it makes no original, falsifiable predictions. No candidate theory of everything to date that includes the Standard Model and general relativity can calculate the fine-structure constant or the mass of the electron from its own principles. Cassi enters this search from a different direction: no extra dimensions, no supersymmetry, no new particles—just two fields and one number.

## The proposal: a sunflower at every scale

The seed image is a sunflower head: seeds spiraling in consecutive Fibonacci numbers because each is placed at the golden angle, the turn that divides a circle in the golden ratio. Now imagine each seed is itself a smaller sunflower, and the whole head is a seed on a larger one—a pattern repeating at every scale, in both directions. Cassi proposes that reality is this pattern: a nested lattice of bubbles.

Two tendencies fill all of space. **Yang** is the expansive field: it pushes outward and breaks symmetry. **Yin** is the contractive field: it pulls inward and restores balance. They are two sides of one thing, converting into each other continuously. Where they meet in the right proportion, order condenses into a **bubble**; where they cancel, a **void** forms. The right proportion is $\varphi$: when the push is about 1.618 times the pull, the two are balanced. Because $\varphi$ is the hardest number to approximate as a ratio of integers, systems tuned to it never lock into resonance, so structure survives at every scale instead of collapsing into one. The resulting ladder of scales runs from the Planck length to the size of the observable universe in 292 steps, each about 1.618 times larger than the last.

## What the framework derives

From that single constant and one governing equation—the two-fluid PDE, which evolves the two fields in space and time—the framework derives:

- **Quantum mechanics**, as standing-wave interference of the two fields. The particle spectrum and the three fermion generations follow from the Fibonacci recurrence, with no fourth generation predicted.
- **General relativity**, as the pull toward $\varphi$-equilibrium: the imbalance between Yang and Yin produces an inward force, always attractive because the spiral winds one way. The cascade suppresses the coupling over the 92 rungs between the Planck scale and the proton—which is why gravity is so much weaker than the other forces.
- **The Standard Model**, with gauge couplings, mass ratios, and the CP-violating phase arising as $\varphi$-powers, cascade-suppressed across the rungs. The electroweak, grand-unification, and Planck scales of the standard unification picture all land on specific rungs of the same ladder.
- **Cosmology**, as the ongoing conversion of Yin into Yang while the universe approaches $\varphi$-equilibrium: accelerated expansion without a cosmological constant, dark matter as high-coherence condensate that amplifies gravity by up to about 18 times where coherence is high, and the matter-antimatter asymmetry from the freeze-out gap of the five-channel cycle.

No dark matter particles, no cosmological constant, no inflaton, no fine-tuned numbers. The framework's answers to the open questions of physics, each with its mechanism and epistemic label, are in `open-questions-cassi-answers.md`.

## The constants it computes

The present status of the field sets the bar Cassi aims at: no candidate theory of everything that includes the Standard Model and general relativity can yet calculate the fine-structure constant or the mass of the electron from its own principles. Cassi's central claim is exactly that—the fine-structure constant, particle mass ratios, gauge couplings, and the dark-energy equation of state are derived as $\varphi$-powers from the two-fluid PDE, each with a derivation in the papers. Whether those derivations hold is what the documents and the code in this repository exist to check.

## How it can be tested

The charge against string theory is that it cannot be falsified. Cassi answers with a catalog of 47 numbered predictions, each with a concrete test design: a log-periodic modulation in the matter power spectrum at the golden-ratio period, a 1.70× edge anisotropy at any condensate boundary, the $\varphi^2$ inter-node spacing ratio of the chakra lattice, the dark-energy equation of state. Full catalog: `predictions/falsifiable-predictions.md`.

## The arguments against

A theory of everything faces serious arguments that it is impossible. Gödel's incompleteness theorem suggests any finite set of rules leaves true statements underivable—Hawking concluded from it that no ultimate theory could be formulated, Dyson that physics is inexhaustible. Others note that physics proceeds by successive approximations, so no framework should be mistaken for final truth. And there is the reductionism-versus-emergence debate: whether emergent laws like thermodynamics or natural selection are as fundamental as any microscopic law.

Cassi meets these arguments with explicit discipline. Every claim carries one of three labels: **Derived** (a mathematical consequence of the framework), **Hypothesized** (consistent and testable, not yet confirmed), or **Speculative** (framework-consistent, no test designed yet). Known tensions and errors are documented openly in `audit.md`—the gate sign is PDE-tested, and falsified claims are replaced by the corrected claim. The framework does not claim to predict every outcome of every experiment: even Conway's Game of Life, with complete and simple rules, leaves undecidable questions about its behavior, and Cassi's claim is narrower—one physical law for the four forces, checked claim by claim. On emergence, the framework takes both sides: the lattice is scale-covariant, so the laws of complex systems, including the mind, are the same physics at higher rungs rather than a separate physics (`cassi-psychology.md`).

**Start here:** `cassi-physics.md`—the physics guide, approachable from zero. `cassi-psychology.md` is the psychology-focused guide for non-physicists.

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
| `EPISTEMIC-MAP.md` | Every document indexed by epistemic tier |
| `predictions/` | Falsifiable prediction catalog + `predictions/cassi_definitions.md` glossary |
| `experiments/` | Physics experiment scripts (φ-attractor paths, SPARC rotation-curve analysis) |
| `two-fluid/` | Two-fluid PDE solver + gate/ODE test scripts, calibration |
| `computations/` | Computational pipelines (RGE, GUT-EW, hubble tension, cascade depth) |
| `visual-explainers/` | Matplotlib figure/simulation scripts |

## Registries

- `open-questions-cassi-answers.md`—epistemic master registry (Q/C/G/M/F/T numbering)
- `parameter-inventory.md`—parameter master registry
- `predictions/falsifiable-predictions.md`—the prediction catalog
- `audit.md`—self-critical prediction-vs-experiment audit
- `BROKEN_REFS.md`—registry of external/broken references; read before touching cross-references

## Code

All code supporting the theory lives in this repo: PDE solvers and run scripts (`two-fluid/`), computational pipelines (`computations/`), experiment and analysis scripts (`experiments/`), and figure scripts (`visual-explainers/`). Run everything from the repo root; generated figures, run outputs, and logs are gitignored.
