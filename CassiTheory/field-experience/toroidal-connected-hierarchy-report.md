# Toroidal Connected-Hierarchy Campaign Report

## Status: Tested—August 2026

## 1. Scope and receipts

This campaign evolves three labeled scale components simultaneously in one periodic multicomponent Schrödinger–Poisson system:

- a compact Yang/Yin core;
- the V5 toroidal Yang/Yin loop;
- a broad Yang/Yin outer envelope.

Each scale density generates a Poisson potential. A frozen symmetric graph selects which potentials act on each scale. Full, decoupled, nearest-neighbor, and loop-disconnected graphs use identical initial fields. The protocol is `field-experience/toroidal-connected-hierarchy-pre-registration.md`.

Canonical receipts:

- `runs/20260831T233830Z_toroidal_connected_hierarchy/results.json`, SHA-256 `4c11270d6775d02ffe24552c2f8fe61ae2867a491dc83ad2542f89c8252e19ab`;
- `runs/20260831T233830Z_toroidal_connected_hierarchy/verification.json`, SHA-256 `42d95392e4e38134871996792ea8b74ed33555de983682ab68785587fe1959e2`;
- `fields_A.npz` through `fields_F.npz` in the same run directory, each hash-bound by `results.json`.

The independently verified terminal result is

```text
EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION
```

Secondary labels are

```text
CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY
INCONCLUSIVE—MIXED LOOP RESPONSE
```

## 2. Frozen initialization

The reference `N=64` unit profiles give

\[
K_1=0.6611932884066583,
\qquad
W_1=-0.00315613483199668,
\]

and the frozen full-state virial mass is

\[
M_*=-\frac{2K_1}{W_1}=418.98925337632966.
\]

The scale masses are `104.74731334408243`, `209.49462668816477`, and `104.7473133440824` for core, loop, and envelope. Their fractions are `(0.25,0.50,0.25)`. The reference virial residual is `1.0259327051677939e-16`.

Initial mean radii are `1.2764851638639432`, `4.399549463055625`, and `6.206932646839309`. The loop has fitted radius `4.269998986912656`, helical order `0.8273853869634591`, and windings `(+2,-3)`. G1–G4 all pass.

## 3. Numerical quality

All six arms complete with finite complex128 fields. Q1–Q5 all pass.

| gate | result | decisive maximum or comparison |
|---|---|---|
| Q1 completion and mass | pass | maximum scale-mass drift `2.3697123237429215e-12` |
| Q2 Hamiltonian | pass | maximum total-energy drift `3.363306786394955e-7`, against `5e-3` |
| Q3 half step | pass | energy-transfer differences at most `7.038140403814452e-8`; helical-retention difference `2.532478063366206e-8`; radius-retention difference `8.807050755343937e-9` |
| Q4 resolution | pass | energy-transfer differences at most `0.0007804023271607008`; helical-retention difference `0.0010879089709605883`; radius-retention difference `0.00003906890491961468` |
| Q5 loop isolation | pass | final loop-field relative infinity errors are exactly `0.0`; metric errors are at most `8.593141142517172e-14` |

The primary full arm has total-energy drift `1.3346265550468783e-7`. Its half-step arm reduces that drift to `8.352393307922538e-9`. The `N=80` arm reproduces the endpoint energy redistribution and loop response well inside every frozen tolerance.

## 4. Connected scale-energy redistribution

The frozen endpoint scale-energy changes are normalized by the magnitude of each arm's initial total Hamiltonian. The exchange amplitude is one half of their absolute sum.

| arm | graph | core $\delta_C$ | loop $\delta_L$ | envelope $\delta_E$ | exchange $X$ |
|---|---|---:|---:|---:|---:|
| A | full | `-1.2025553072773119` | `0.3959890921783316` | `0.8065662207254375` | `1.2025553100905404` |
| B | decoupled | `2.370882370012646e-9` | `-1.5514742008166367e-12` | `2.3697213872567323e-13` | `1.1863354081760941e-9` |
| C | nearest-neighbor chain | `-0.7876327550594342` | `0.29637875590985713` | `0.4912540192208079` | `0.7876327650950496` |
| D | loop disconnected | `-0.7293861565933927` | `-1.465542789391465e-12` | `0.7293862213970144` | `0.7293861889959363` |
| E | full, `N=80` | `-1.2017749049501512` | `0.3957399022981655` | `0.8060350083170724` | `1.2017749077826945` |
| F | full, half step | `-1.2025552368959078` | `0.39598904224945913` | `0.8065661949841203` | `1.2025552370647437` |

Full arm A satisfies every frozen discriminator:

1. `X_A=1.2025553100905404 >= 0.02`;
2. `X_B=1.1863354081760941e-9 <= 0.005`;
3. the disconnected loop has `|delta_L|=1.465542789391465e-12 <= 0.005`;
4. the full energy-change vector has both signs.

The core becomes more bound while the loop and envelope receive positive assigned energy. The total Hamiltonian remains conserved. The full interaction energy changes from `-165.9637944169088` to `-1174.198935635297` as the three distributions contract and overlap more strongly.

Mean radii in arm A change from `(1.2764851638639432, 4.399549463055625, 6.206932646839309)` to `(1.0270352401375347, 2.400080725173167, 3.3475503885053968)` for core, loop, and envelope. Fine modal-mass fractions at final time are `0.13781243739126056`, `0.35926810697987616`, and `0.35399185106142333`.

## 5. Graph attribution

The loop-disconnected control reproduces the decoupled loop fields exactly while its core and envelope exchange an amplitude of `0.7293861889959363`. This separates scale-graph energy redistribution from self-evolution and validates the declared coupling boundary.

The nearest-neighbor chain does not reproduce the full graph. Its differences from full A are:

- core energy change: `0.41492255221787766`;
- loop energy change: `0.09961033626847449`;
- envelope energy change: `0.3153122015046296`;
- exchange amplitude: `0.41492254499549075`.

Every value exceeds the frozen `0.03` sufficiency limit. The chain's loop finishes with windings `(+1,-2)`, while full A retains `(+2,-3)`. Within this three-component proxy, the direct core–envelope edge materially changes the redistribution and loop topology. The registered secondary label is `CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY`.

## 6. Loop response

Full and decoupled arms start from the same loop. Their endpoint retentions are:

| arm | helical retention | radius retention | final winding | fine modal-mass change |
|---|---:|---:|---|---:|
| A full | `0.19627664091756078` | `0.4935297934492889` | `(+2,-3)` | `0.3568613237250503` |
| B decoupled | `0.258506476588151` | `0.8769341668482781` | `(+2,-3)` | `-0.0019700104353792425` |

The connected differences are

\[
\Delta\mathcal H=-0.06222983567059023,
\qquad
\Delta\mathcal R=-0.3834043733989892.
\]

The full graph drives much stronger loop contraction and fine-mode generation. Its helical-retention decrement does not cross the frozen `-0.10` paired threshold, while its radius decrement does. The protocol therefore returns `INCONCLUSIVE—MIXED LOOP RESPONSE`. The connected hierarchy establishes energy redistribution; it does not establish support for toroidal survival.

## 7. Independent verification

The verifier reconstructs the analytic scale profiles, recalibrates the frozen mass, re-evolves all six arms, recomputes every scalar series and gate, and compares all six final complex fields without importing the primary program.

It returns:

- `pass: true`;
- no errors;
- maximum normalized scalar discrepancy `0.00011368683772032354`;
- maximum normalized final-field discrepancy `0.000026928140623745657`;
- the same Q1–Q5 directions;
- the same terminal and secondary labels.

## 8. Interpretation boundary

This campaign establishes a resolved, conservative transfer of assigned energy among three labeled field components through a shared gravitational coupling graph. It also shows that graph topology changes both the transfer vector and the loop's winding outcome.

The result does not establish an endogenous hierarchy, conversion of one scale species into another, nested-domain boundary exchange, an open environmental coupling, a preferred scale spacing, or a canonical Cassi cascade. The components and their graph are supplied intervention variables. The next hierarchy campaign can test robustness across mass shares and scale separations, followed by a single-field construction in which scale membership is diagnosed rather than assigned.
