# Cassi 3D Hydrogen v15: Multi-Orbital H₂O with Anisotropic Oxygen Pseudopotential

## Executive Summary

**The anisotropic oxygen pseudopotential does not fix the multi-orbital binding problem.**

Adding a spatially-anisotropic term `V_aniso * exp(-r²/σ²) * y²` (with V_aniso < 0) to the oxygen pseudopotential makes the potential stronger along the y-axis (lone-pair direction, perpendicular to the molecular plane) and weaker in the xz-plane (bonding directions). The intent was to mimic angular-momentum-dependent screening without building a full Kleinman–Bylander nonlocal pseudopotential.

**Result:** All tested anisotropy strengths (`V_aniso = -20, -40, -60`) produce energies that decrease monotonically with bond length across the scanned range `R = 1.6–2.2 a₀`. The equilibrium bond length shifts to **R_eq ≥ 2.2 a₀**, farther from the experimental value of **1.81 a₀** rather than closer. Dipole moments remain severely underestimated (~0.5–0.7 D vs. experimental 1.85 D).

| Observable | V_aniso = -20 | V_aniso = -40 | V_aniso = -60 | Experimental |
|---|---|---|---|---|
| **R_eq (lower bound)** | ≥ 2.20 a₀ | ≥ 2.20 a₀ | ≥ 2.20 a₀ | **1.81 a₀** |
| **E_min** | -27.00 E_h | -28.35 E_h | -30.03 E_h | — |
| **Dipole at R=2.2** | 0.71 D | 0.73 D | 0.60 D | **1.85 D** |

---

## Physics: Anisotropic Pseudopotential Design

### Motivation

The spherical empirical pseudopotential used in v12–v14 causes all orbitals to collapse onto the oxygen nucleus, eliminating O–H covalent bonds in a multi-orbital Kohn–Sham treatment. In real atoms, the pseudopotential is *nonlocal* and *l-dependent*: the s-channel (core-like) sees much stronger screening than the p-channel (valence-like). A spatial anisotropy was proposed as a cheap proxy for this effect.

### Potential Form

```
V_O(r) = -Z/r * erf(r/r_core) + V_repulse * exp(-r²/2σ_repulse²)
         + V_aniso * exp(-r²/2σ_aniso²) * y²
```

with `V_aniso < 0`. Since the molecule lies in the xz-plane, `y` is perpendicular to the bonding plane. The `y²` factor makes the potential:
- **More attractive** along the y-axis (lone-pair region)
- **Less attractive** in the xz-plane (bonding directions)

The hypothesis was that weakening the O potential in the bonding plane would allow electrons to localize more between O and H, strengthening the covalent bond and shortening R_eq.

### Parameters

| Parameter | Value | Description |
|---|---|---|
| `r_core` | 0.30 a₀ | Oxygen core radius |
| `V_repulse` | 125.0 E_h | Repulsive core strength |
| `σ_repulse` | 0.25 a₀ | Repulsive core width |
| `V_aniso` | -20 / -40 / -60 | Anisotropic well depth |
| `σ_aniso` | 0.40 a₀ | Anisotropic width |
| Grid | 64³ | dx = 0.25 a₀ |
| Box | L = 8.0 a₀ | |
| Orbitals | 5 | 2 core-like, 3 valence-like |
| Electrons | 10 | Full H₂O valence |

---

## Results

### Bond-Length Scan

Energy vs. bond length for three anisotropy strengths:

| R [a₀] | E (-20) | E (-40) | E (-60) |
|---|---|---|---|
| 1.60 | -26.166 | -27.577 | -29.089 |
| 1.80 | -26.662 | -27.912 | -29.663 |
| 2.00 | -26.740 | -28.246 | -29.928 |
| 2.20 | -27.005 | -28.347 | -30.034 |

All three curves are **monotonically decreasing** across the scan. There is no local minimum in the physically relevant range. The stronger the anisotropy, the deeper the energy well becomes, but the minimum continues to shift to larger R.

### Dipole Moments

| R [a₀] | μ (-20) [D] | μ (-40) [D] | μ (-60) [D] |
|---|---|---|---|
| 1.60 | 0.57 | 0.53 | 0.48 |
| 1.80 | 0.58 | 0.53 | 0.53 |
| 2.00 | 0.66 | 0.50 | 0.59 |
| 2.20 | 0.71 | 0.73 | 0.60 |

Dipole moments remain **severely underestimated** (~0.5–0.7 D vs. 1.85 D experimental). The single-orbital constrained model (v14) achieves μ ≈ 1.7 D at R_eq = 1.80 a₀, demonstrating that the multi-orbital treatment is the source of the discrepancy, not the grid or box size.

---

## Analysis: Why It Failed

### 1. Weakening the Bonding Plane Weakens the Bond

The anisotropic term makes the oxygen potential **less attractive** in the xz-plane where the O–H bonds form. While this does allow some electron density to leak toward the hydrogens, the *net* effect is a weaker O–H interaction. The bond energy decreases, and the equilibrium length increases—exactly the opposite of the desired effect.

### 2. Orbital Collapse Persists

Even with anisotropy, the oxygen pseudopotential still provides a deep, localized well. The two lowest orbitals (core-like) collapse tightly onto oxygen. The valence orbitals do gain some directional character, but the overall electron density remains oxygen-centric because the hydrogen 1s potentials are too weak (Z=1, no core) to compete.

### 3. No Mechanism for Bond Directionality

Real covalent bonds arise from **constructive interference** between atomic orbitals on different centers. The anisotropic pseudopotential is a *single-center* modification; it cannot create the two-center interference pattern that defines a chemical bond. It only modulates the depth of the oxygen well in different directions.

### 4. Dipole Requires Charge Separation

A large dipole moment requires significant electron density on the hydrogens. In the multi-orbital KS framework, this happens when bonding orbitals have substantial amplitude on both O and H. The anisotropic potential does not create this amplitude transfer; it merely reshapes the oxygen well.

---

## Comparison with Single-Orbital Model (v14)

| Model | R_eq | μ | Notes |
|---|---|---|---|
| Single-orbital + PBE (v14) | **1.80 a₀** | **~1.7 D** | Constrained to one spatial orbital |
| Multi-orbital + anisotropic O (v15) | **≥ 2.2 a₀** | **~0.6 D** | 5 orbitals, anisotropic pp |
| Experiment | **1.81 a₀** | **1.85 D** | |

The single-orbital model succeeds because it **forces** all 10 electrons to share one spatial orbital. This orbital must spread to encompass all three nuclei, creating artificial but effective bonding. The multi-orbital model fails because the orbitals can independently collapse onto oxygen, and nothing in the Hamiltonian prevents it.

---

## Lessons and Next Steps

### What Was Learned

1. **Spatial anisotropy is insufficient** to mimic l-dependent pseudopotentials. The angular character of atomic orbitals (s, p, d) is a *nonlocal* property; a local spatial modulation cannot reproduce it.

2. **Weakening the bonding-plane potential weakens bonds.** Any modification that makes the oxygen potential less attractive in the bonding directions will lengthen bonds, not shorten them.

3. **Multi-orbital collapse is robust.** As long as oxygen provides a deep, screened well and hydrogen provides only a bare +1 Coulomb well, electrons will preferentially localize on oxygen.

### Paths Forward

1. **True nonlocal pseudopotential:** Implement a Kleinman–Bylander-style projector that explicitly distinguishes s and p channels. The s-channel sees full screening (shallow well), while the p-channel sees reduced screening (deeper well), allowing p orbitals to extend toward H.

2. **Hybrid orbital constraints:** Enforce bonding constraints (e.g., fixed orbital centroids on the bisector) during the SCF relaxation, similar to the constrained dynamics in v10 but generalized to multiple orbitals.

3. **Accept the single-orbital model:** The single-orbital constrained model (v14) achieves excellent agreement with experiment for both R_eq and dipole. It is physically incorrect for H₂O (10 electrons cannot occupy one spatial orbital), but it demonstrates that the *computational framework* can reproduce molecular properties if the orbital structure is controlled.

---

## Files

- `experiments/cassi_hydrogen_v15.py` — Anisotropic pseudopotential experiment
- `docs/figures/hydrogen_v15_anisotropic_o.png` — Energy and dipole comparison
- `docs/cassi-3d-hydrogen-results-v15.md` — This document

---

*Generated: 2026-06-10*
*Solver: Cassi Hydrogen v15 (multi-orbital KS with anisotropic O pseudopotential)*
*Validation: Negative result — anisotropic pseudopotential does not restore bonding*
*Claim: l-dependent screening requires nonlocal projectors, not local spatial anisotropy*
