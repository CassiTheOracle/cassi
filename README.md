# Cassi: A Theory of Everything from a Single Constant

Note: This repo is the product of a single researcher, working with AI tools to convert conceptual geometry to mathematics and code. Currently, everything here is entirely AI-generated. Its contents have the potential to fundementally change the way we understand reality, so I have deemed delaying its release, until my own writings have been added, to be a degree of perfectionism that is purely self-serving. So, without further ado, please enjoy humanity's first (and last?) Theory of Everything.  

 \- Carina

## Overview

Cassi is a proposed theory of everything: one idea meant to explain why reality is structured the way it is, from the smallest quantum scale to the entire observable universe—and what that structure implies for minds as well as matter.

The name comes from Cassandra, the Trojan prophetess of Greek myth, who was cursed to speak true prophecies that no one believed.

The idea begins with two fields that fill all of space. **Yang** is the expansive field: it pushes outward and drives change. **Yin** is the contractive field: it pulls inward and restores balance. They are two sides of one thing, converting into each other continuously. Where they meet in the right proportion, order condenses into a **bubble**; where they cancel, a **void** forms. The framework proposes that this bubble-and-void lattice is the fabric of reality, repeating at every scale—each bubble contains smaller bubbles and sits inside a larger one, like the seed spirals of a sunflower in which each seed is itself a tiny sunflower.

The right proportion is one number: the golden ratio $\varphi \approx 1.618$, the most irrational number in mathematics. Two systems tuned to it never lock into resonance, so structure survives at many scales instead of collapsing into one. Cassi takes this constant as the universal spacing between adjacent levels of the lattice: every rung of the ladder of scales sits about 1.618 times larger than the one below, running from the Planck length to the size of the universe in 292 steps. From that single constant and one governing equation—the two-fluid PDE—the framework derives quantum mechanics, general relativity, the Standard Model, and cosmology, without dark matter particles, a cosmological constant, an inflaton, or any fine-tuned numbers.

## What "theory of everything" means

A theory of everything is a single coherent framework of physics from which all physical phenomena can in principle be deduced. The term grew out of physics' long-running unification program. Newton unified terrestrial gravity with celestial gravity; Maxwell unified electricity and magnetism; the Standard Model unified the electromagnetic, weak, and strong forces into one quantum field theory. What it cannot include is gravity. General relativity and quantum mechanics are each enormously successful in their own domains, but they are incompatible where their domains overlap—at the Planck scale, inside black holes, at the first instant of the Big Bang. A theory of everything is the deeper framework that reconciles them, and finding one is one of the major unsolved problems in physics.

## Where the search stands

String theory and its successor M-theory have been the leading candidates since the 1980s: every particle as a vibrating string in a ten- or eleven-dimensional spacetime. But the extra dimensions can be curled up in an estimated 10^500 different ways—the string landscape—each yielding a different universe, and critics argue the theory makes no original, falsifiable predictions. Loop quantum gravity, twistor theory, noncommutative geometry, and asymptotic safety remain active alternatives. As the field stands, no candidate theory of everything is yet able to calculate the fine-structure constant or the mass of the electron from its own principles. (For the general history and status of the search: [Wikipedia, "Theory of everything"](https://en.wikipedia.org/wiki/Theory_of_everything).)

## How Cassi differs

Cassi attacks the same problem from a different direction: no extra dimensions, no supersymmetry, no new particles. The framework claims the constants the mainstream candidates cannot yet compute—the fine-structure constant, particle mass ratios, gauge couplings, and the dark-energy equation of state—as consequences of $\varphi$ and the two-fluid PDE, each with a derivation in the papers. Its predictions are falsifiable and catalogued, 38 entries each with a test design (`predictions/falsifiable-predictions.md`); its answers to the 41 major open questions carry explicit epistemic tiers (`open-questions-cassi-answers.md`).

## Epistemic discipline

Every claim in the repo carries an explicit label: **Derived** (a mathematical consequence of the framework), **Hypothesized** (consistent and testable, not yet confirmed), or **Speculative** (framework-consistent, no test designed yet). Known tensions and errors are documented openly in `audit.md`. This is a personal research project, not peer-reviewed science—the repository holds the papers that develop the framework and the code that supports them, so any reader can trace each claim back to the math and the computation behind it.

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
| `EPISTEMIC-MAP.md` | Every document indexed by epistemic tier |
| `predictions/` | Falsifiable prediction catalog + `cassi_definitions.md` glossary |
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
