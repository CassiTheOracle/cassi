# Atomic Shell Structure and the Madelung Rule from Cascade Coordinates

## Status: Speculative—July 2026

## Abstract

The periodic table's electron shell filling order follows the Madelung rule
($n+l$ ordering): 1s, 2s, 2p, 3s, 3p, 4s, 3d, 4p, 5s, 4d, 5p, 6s, 4f, 5d, 6p,
7s, 5f, 6d, 7p. The principal quantum number $n$ and orbital angular momentum
$l$ are treated as independent quantum numbers in standard quantum mechanics. The
Cassi framework suggests they are not independent—$n$ labels the cascade rung
and $l$ labels the Fibonacci sub-channel within that rung, with the Madelung rule
emerging from the cascade ordering. This is Speculative because the explicit
derivation of quantum numbers from cascade geometry is not yet complete, but the
pattern is highly suggestive and makes testable predictions for ionization
energies and quantum defects.

---

## 1. $n$ and $l$ as Cascade Coordinates

The cascade ladder has two structural dimensions:
- The **rung index** $n$—the primary scale separation, counting steps from the
  Planck scale (`foundations/dimensionful-cascade.md`).
- The **sub-channel index**—the Fibonacci partition within each rung
  (`foundations/three-generations.md`).

In the atomic context, the principal quantum number $n$ corresponds to the
cascade rung (the radial scale of the electron orbit), and the orbital angular
momentum $l$ corresponds to the SO(2) winding within the sub-channel
(`foundations/spin-fibonacci-spiral.md`):
$$l = \Delta n_{\text{sub}}$$

where $\Delta n_{\text{sub}}$ is the number of Fibonacci sub-rungs within the
primary rung $n$.

The Madelung rule says orbitals fill in order of increasing $n + l$, with lower
$n$ breaking ties. In cascade coordinates:
$$n + l = n_{\text{rung}} + \Delta n_{\text{sub}}$$

This combination is the total cascade depth of the orbital—the primary rung
plus the sub-rung offset. The filling order by $n + l$ is filling order by total
cascade depth.

## 2. The Filling Sequence

The observed shell capacities (cumulative electron counts at noble gases):
$$2, 10, 18, 36, 54, 86, 118$$

These are twice the sum of squares:
$$2 \times (1^2),\; 2 \times (1^2 + 2^2),\; 2 \times (1^2 + 2^2 + 2^2),\; 2 \times (1^2 + 2^2 + 3^2),\; \ldots$$

The factor of 2 comes from spin degeneracy (up/down), which in Cassi corresponds
to the two directions of SO(2) winding (clockwise/counterclockwise).

The sum-of-squares pattern $1^2, 1^2+2^2, 1^2+2^2+2^2, 1^2+2^2+3^2, \ldots$
maps to the Fibonacci partitioning of each cascade rung:

| Period | Rung $n$ | Sub-channels | Capacity $2\sum l^2$ | Cumulative |
|--------|---------|-------------|---------------------|------------|
| 1 | 1 | $l=0$ | $2(0+1)^2 = 2$ | **2** (He) |
| 2 | 2 | $l=0,1$ | $2(1^2+2^2) = 10$ | $2+8$ = **10** (Ne) |
| 3 | 3 | $l=0,1$ (3d delayed) | $2(1^2+2^2) = 10$ | $10+8$ = **18** (Ar) |
| 4 | 4 | $l=0,1,2$ | $2(1^2+2^2+3^2) = 28$ | $18+18$ = **36** (Kr) |
| 5 | 5 | $l=0,1,2$ (4f delayed) | $2(1^2+2^2+3^2) = 28$ | $36+18$ = **54** (Xe) |
| 6 | 6 | $l=0,1,2,3$ | $2(1^2+2^2+3^2+4^2) = 60$ | $54+32$ = **86** (Rn) |
| 7 | 7 | $l=0,1,2,3$ (5f, 5g delayed) | up to $2(4^2) = 32$ | $86+32$ = **118** (Og) |

The delays (3d filling after 4s, 4f after 6s, 5f after 7s) correspond to
Fibonacci sub-channel reordering: sub-channels with higher SO(2) winding (higher
$l$) are energetically penalized by the cascade geometry and fill only when the
next rung's lower-$l$ sub-channels are occupied.

## 3. Key Prediction: $\varphi$-Power Quantum Defects

The quantum defect $\delta_{nl}$—the deviation of the atomic energy level from
the hydrogenic value $E_n = -R_y / n^2$—arises from core penetration and
screening. In the cascade picture, the defect comes from the sub-channel
coupling to the cascade ladder above it:

$$\boxed{\delta_{nl} = \delta_0 \cdot \varphi^{-(n + l)} \cdot f(Z)}$$

where $f(Z)$ accounts for the nuclear charge scaling (approximately
$\propto Z^{-1/3}$ from Thomas-Fermi screening) and $\delta_0$ is a
normalization constant.

This predicts:
- For fixed $n$, $\delta_{nl}$ decreases with increasing $l$ as
  $\varphi^{-l}$. Observed trend: $\delta_{ns} > \delta_{np} > \delta_{nd} >
  \delta_{nf}$ for each $n$. The ratios $\delta_{np}/\delta_{ns}$,
  $\delta_{nd}/\delta_{np}$, etc., should approximately equal
  $\varphi^{-1} \approx 0.618$.
- For fixed $l$, $\delta_{nl}$ decreases with increasing $n$ as
  $\varphi^{-n}$. The defects for Rydberg states ($n \gg 1$) should vanish
  exponentially as $\varphi^{-n}$.

**Test with alkali metals (single valence electron, cleanest quantum defects):**

| Atom | $n$ | $l$ | $\delta_{nl}$ (obs.) | Ratio $\delta_{n,l+1}/\delta_{nl}$ |
|------|-----|-----|---------------------|-----------------------------------|
| Na | 3 | $s$ | 1.35 |—|
| Na | 3 | $p$ | 0.85 | 0.63 |
| Na | 3 | $d$ | 0.010 | 0.012 |
| K | 4 | $s$ | 2.18 |—|
| K | 4 | $p$ | 1.71 | 0.78 |
| K | 4 | $d$ | 0.25 | 0.15 |
| Rb | 5 | $s$ | 3.13 |—|
| Rb | 5 | $p$ | 2.64 | 0.84 |
| Rb | 5 | $d$ | 1.35 | 0.51 |

The $p/s$ ratios (0.63, 0.78, 0.84) are in the neighborhood of
$\varphi^{-1} \approx 0.618$ but with significant scatter. The $d/p$ ratios
(0.012, 0.15, 0.51) deviate strongly—the $nd$ states are nearly hydrogenic
for low $n$, suggesting the cascade suppression breaks down when the orbital
angular momentum exceeds the sub-channel capacity.

## 4. Ionization Energy Ratios

Successive ionization energies of a multi-electron atom should show
$\varphi$-periodic structure: the ratio of the $k$th to the $(k+1)$th
ionization energy, for electrons in the same shell, should approach
$\varphi$. More precisely:

$$\frac{I_k}{I_{k+1}} \xrightarrow[\text{same shell}]{} \varphi$$

**Test with oxygen (8 electrons):**
Ionization energies: 13.6, 35.1, 54.9, 77.4, 113.9, 138.1, 739.3, 871.4 eV.
Within the $n=2$ shell (first 6 electrons, $n=1$ core excluded): ratios are
35.1/13.6 = 2.58, 54.9/35.1 = 1.56, 77.4/54.9 = 1.41, 113.9/77.4 = 1.47,
138.1/113.9 = 1.21. The geometric mean of within-shell ratios is ~1.56—close
to $\varphi \approx 1.618$ but the individual ratios vary substantially,
reflecting electron correlation effects that the simple cascade model does not
capture.

## 5. Falsifiable Tests

1. **Quantum defect $\varphi$-scaling for Rydberg states:** For $n \gtrsim 10$,
   the quantum defect should follow $\delta_{nl} \propto \varphi^{-n}$.
   High-precision spectroscopy of Rydberg atoms can test this.

2. **Ionization energy ratio convergence:** For heavy atoms ($Z > 50$), the
   ratio of successive ionization energies for electrons in the same subshell
   should converge toward $\varphi$ as $Z \to \infty$ (where the central field
   approximation improves).

3. **No $\varphi$-structure in $l > 3$:** The cascade predicts sub-channels up
   to $l = 3$ (from three Fibonacci sub-channels). $l = 4$ ($g$-orbitals)
   should exist only at rungs where a fourth Fibonacci sub-channel opens—this
   would be nuclei with $Z > 120$, beyond the current periodic table.

## 6. Open Issues

- The derivation of atomic quantum numbers from cascade geometry is not yet
  complete. The mapping $n \leftrightarrow$ rung index and $l \leftrightarrow$
  sub-channel winding is structurally motivated but lacks a formal PDE
  derivation.
- Quantum defects in multi-electron atoms involve electron-electron
  interactions that the simple cascade model does not address. The prediction
  is clearest for alkali atoms (single valence electron) and highly ionized
  species.
- The status is **Speculative** because while the pattern is suggestive, the
  mechanism is not yet derived from the two-fluid PDE. It is included here as a
  prompt for future work rather than a falsifiable claim at the existing
  framework's epistemic standard.

---

## References

- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `foundations/three-generations.md`—Fibonacci partitioning
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding and angular momentum
- `foundations/why-three-dimensions.md`—spiral's Frenet-Serret frame
- `open-questions-cassi-answers.md`—Q5 (three generations), Q10 (spin)
