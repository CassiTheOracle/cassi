# Particles—Yang-Yin Interference and DFT Benchmarks

## Status: Index—July 2026

## Abstract

This directory pairs the Cassi account of how particles emerge from field interference with a computational benchmark of the framework's density-functional engine. `cassi-yang-yin-particles.md` derives particle formation from counter-propagating Yang and Yin waves condensing into solitons at a $\varphi$-determined amplitude ratio; `dft-benchmarks.md` validates the real-space DFT solver in CassiBridgeV2 against exact atomic ground-state energies for the first row of the periodic table. Read in alphabetical order: the mechanism doc first, then the benchmarks as evidence that the computational core reproduces chemistry.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `cassi-yang-yin-particles.md` | Particle emergence | Derived |
| 2 | `dft-benchmarks.md` | Computational chemistry | Derived |

## Document Summaries

### `cassi-yang-yin-particles.md`—Yang-Yin Field Interference and Particle Formation

Derives particle emergence from two complex scalar fields with opposite chiral bias—Yang right-moving (expansive), Yin left-moving (contractive)—each obeying a damped wave equation with a $\pm\chi$ advection term and mutually coupled sources. Their superposition creates a standing-wave intensity pattern with contrast $\rho_{\text{max}}/\rho_{\text{min}} = \varphi^6 \approx 17.94$, and adding the attractive nonlinear Schrödinger self-interaction nucleates bright solitons above the condensation threshold $\rho_{\text{peak}} = A_Y^2\varphi^2 > \theta_{\text{cond}}$. Minimizing the soliton mass $M(r) = M_0\,(1+r)^2/\sqrt{r}$ pins the Yin/Yang amplitude ratio at $A_I/A_Y = \varphi^{-1} \approx 0.618$—the golden ratio emerges as the stability condition for particle formation rather than an input. The framework maps onto the Dirac equation (a massive fermion is the superposition of right- and left-moving Weyl chiralities) and is confirmed numerically by Experiment 8v2: soliton formation from interference, elastic soliton scattering, and an amplitude-ratio scan peaking at $\varphi^{-1}$. Epistemic tier: Derived—analytic derivation plus numerical validation.

### `dft-benchmarks.md`—DFT Benchmarks: CassiBridgeV2 Real-Space Performance

Benchmarks the real-space pseudospectral DFT engine in CassiBridgeV2 against exact atomic ground-state energies for Z = 1–10. LDA is accurate for light atoms (He at 0.8% error, 64³ grid), but the uniform Cartesian grid cannot resolve compact 1s cores for Z ≥ 4; pseudopotentials remove that bottleneck (Ne 4.8% vs 47.6% all-electron at 64³), and the PBE functional's correctness is verified by systematic grid refinement (He 3.2% → 1.4% from 64³ to 96³). The Dirac-Kohn-Sham extension is also validated: the Foldy-Wouthuysen propagator converges without variational collapse, giving He binding −2.996 $E_h$ (3.2% error) and a correctly resolved Ne 1s² core. The recommendation is N=96 + pseudopotentials for Z > 2, with the direct conclusion that the uniform grid demonstrates functional equivalence but is not competitive with specialized quantum-chemistry codes for heavy atoms. Epistemic tier: Derived—measured results against known exact energies.

## Cross-References

- `../foundations/cassi-first-principles.md`—first-principles foundation for the two-fluid fields whose interference builds particles
- `../foundations/dimensionful-cascade.md`—the cascade ladder that sets the scales of the quantized standing waves
- `../foundations/cascade-suppression-formula.md`—the coherence budget behind the soliton stability condition
- `../predictions/falsifiable-predictions.md`—the 46-entry prediction catalog (particle predictions inherit the framework's falsifiability)
