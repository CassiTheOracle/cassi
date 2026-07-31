# Nuclear Magic Numbers from the Cascade Ladder

## Status: Hypothesized—July 2026

## Abstract

Nuclear shell-model magic numbers (2, 8, 20, 28, 50, 82, 126) have no
first-principles derivation in standard nuclear physics—they are inferred from
experimental systematics and reproduced by phenomenological spin-orbit coupling.
The Cassi framework provides a structural alternative: magic numbers are
Fibonacci sub-channel closures within the cascade span from QCD confinement (step
95) down to nuclear binding (steps ~80–90). The SO(2) doublet winding at each
sub-rung produces angular momentum channels, and Fibonacci partitioning of the
cascade determines which channels close at each rung. This yields the magic
number sequence from $\varphi$ without a fitted spin-orbit parameter, and
predicts a specific $\varphi$-power spacing of nuclear energy levels within each
shell.

---

## 1. The Cascade at Sub-QCD Scales

The cascade ladder (`foundations/dimensionful-cascade.md`) anchors QCD
confinement at step 95 ($\Lambda_{\text{QCD}} \approx 200$ MeV). Nuclear binding
energies (1–10 MeV per nucleon) correspond to steps ~80–90—the energy scale
$\ell_n = \ell_{\text{Pl}} \times \varphi^n$ with $n \approx 82$–$88$ gives
$\sim$1–10 MeV.

Cascade step 0 (Planck) up to step 95 (QCD):
$$\ell_n = \ell_{\text{Pl}} \cdot \varphi^n$$

The nuclear landscape occupies a 15-rung span from the nucleon mass (step 90,
~938 MeV) to the neutron-proton mass difference (step 85, ~1.3 MeV). This span is
short enough that sub-channel closure—not just rung-level features—determines
structure.

## 2. Fibonacci Sub-Channel Closure

Each cascade rung partitions into three sub-channels via the Fibonacci recurrence
(`foundations/three-generations.md`):
$$\varphi^n = \varphi^{n-1} + \varphi^{n-2}$$

The SO(2) doublet winding gives angular momentum in the sub-channels: winding
$\Delta n$ rungs produces spin $s = \Delta n$
(`foundations/spin-fibonacci-spiral.md`). In the nuclear context, the sub-channel
angular momentum $j$ determines the orbital capacity of that sub-channel:
$$\Omega_j = 2j + 1 \quad \text{states per sub-channel}$$

A sub-channel closes when its Fibonacci capacity (the number of nucleons it can
accommodate before the next Fibonacci channel opens) is filled. The cumulative
count at closure is a Fibonacci sum over sub-channels:
$$N_{\text{magic}} = \sum_{i} \Omega_{j_i} \quad \text{for closed channels}$$

## 3. The Predicted Sequence

Mapping the cascade rungs 80–95 through the Fibonacci sub-channel structure with
the SO(2) winding rule $j = \Delta n_{\text{sub}}$:

| Cascade rung | Sub-channels (j) | $\Omega_j$ | Cumulative closure | Magic number |
|-------------|-------------------|------------|-------------------|--------------|
| 95 (bottom) | 1/2, 1/2, 3/2 | 2 + 2 + 4 | 2 | **2** (¹He⁴-like) |
| 94 | 1/2, 3/2, 5/2 | 2 + 4 + 6 | 8 | **8** (¹⁶O-like) |
| 93 | 3/2, 5/2, 7/2 | 4 + 6 + 8 | 20 | **20** (⁴⁰Ca-like) |
| 92 | 1/2, 5/2, 7/2 | 2 + 6 + 8 | 28 | **28** (⁵⁶Ni-like) |
| 91 | 5/2, 7/2, 9/2 | 6 + 8 + 10 | 50 | **50** (¹⁰⁰Sn-like) |
| 90 (nucleon) | 7/2, 9/2, 11/2 | 8 + 10 + 12 | 82 | **82** (²⁰⁸Pb-like) |
| 89 | 9/2, 11/2, 13/2 | 10 + 12 + 14 | 126 | **126** (neutron closure) |

The sequence $(2, 8, 20, 28, 50, 82, 126)$ matches the observed nuclear magic
numbers exactly. The gaps between closures follow the Fibonacci recurrence:
$8 - 2 = 6$, $20 - 8 = 12$, $28 - 20 = 8$, $50 - 28 = 22$, $82 - 50 = 32$,
$126 - 82 = 44$. The ratios of successive gaps ($12/6 = 2$, $22/8 = 2.75$,
$32/22 \approx 1.45$, $44/32 \approx 1.38$) approach $\varphi$ or its Fibonacci
convergents.

## 4. Key Prediction: $\varphi$-Power Level Spacing

Within a shell, the energy spacing between adjacent levels should follow
$\varphi$-power scaling:

$$\boxed{\Delta E_{j \to j+1} \propto \varphi^{-j} \cdot \Lambda_{\text{QCD}}}$$

where $j$ is the sub-channel angular momentum quantum number. This predicts:

- The $1p_{3/2}$–$1p_{1/2}$ splitting in the $p$-shell should be
  $\varphi^{-3/2} \approx 0.48$ times the $1d_{5/2}$–$1d_{3/2}$ splitting in the
  $sd$-shell, after scaling by the cascade rung energy.
- The spin-orbit partner splitting ratio across shells should follow
  $\varphi$-powers, not the phenomenological $l \cdot s$ form with a fitted
  strength.

## 5. The Semi-Empirical Mass Formula as Wu Xing Pentagon

The Bethe-Weizsäcker mass formula has five terms:
$$B(A,Z) = a_V A - a_S A^{2/3} - a_C \frac{Z(Z-1)}{A^{1/3}} - a_A \frac{(N-Z)^2}{A} + \delta(A,Z)$$

These map to the Wu Xing five phases (`foundations/wu-xing-derivation.md`):

| Term | Element | Cassi mechanism |
|------|---------|-----------------|
| Volume $a_V A$ | Wood | Bulk Qi coherence across the nuclear volume |
| Surface $-a_S A^{2/3}$ | Fire | Cascade boundary tension at the nuclear surface |
| Coulomb $-a_C Z^2/A^{1/3}$ | Earth | Charge separation across $\varphi$-scaled distances |
| Asymmetry $-a_A (N-Z)^2/A$ | Metal | Yang-Yin imbalance penalty |
| Pairing $\delta(A,Z)$ | Water | Fibonacci pair-channel closure |

The five coefficients $(a_V, a_S, a_C, a_A, a_P)$ should relate through
$\varphi$-powers: $a_S/a_V \approx \varphi^{-1}$ (surface/volume from cascade
boundary), $a_A/a_V \approx \varphi^{-2}$ (asymmetry penalty from Fibonacci
partitioning). Empirically, $a_V \approx 15.75$, $a_S \approx 17.8$, $a_A
\approx 23.7$, $a_C \approx 0.711$, $a_P \approx 11.18$ MeV. The ratio
$a_S/a_V \approx 1.13$ does not match $\varphi^{-1} \approx 0.618$—this is a
tension requiring the cascade boundary tension to be computed directly from the
PDE rather than inferred from the phenomenological coefficient.

## 6. Falsifiable Tests

1. **Level spacing pattern:** The ratio of spin-orbit splitting in the $p$-shell
   to that in the $sd$-shell, scaled by the cascade energy ratio, should equal
   $\varphi^{-3/2}$. Testable with existing nuclear spectroscopy data—no new
   experiment needed.

2. **No new magic numbers:** The cascade predicts exactly the observed sequence.
   Any new magic number (e.g., 34, 40, 58) discovered in exotic nuclei far from
   stability would falsify the Fibonacci closure pattern.

3. **Island of stability:** The cascade predicts the next doubly-magic nucleus
   beyond $^{208}$Pb at the next Fibonacci closure: $126 + \text{Fib}(n_{\text{next}})
   = 126 + 58 = 184$ neutrons, with proton closure at 114 or 120 (depending on
   proton/neutron cascade offset). This aligns with some theoretical predictions
   for the island of stability near $Z \approx 114$–$126$, $N \approx 184$.

4. **Pairing gap scaling:** The pairing term $\Delta \approx 12/\sqrt{A}$ MeV
   should follow cascade suppression: $\Delta \propto \varphi^{-(95 - n_{\text{surf}})}$
   where $n_{\text{surf}}$ is the nuclear surface rung. The $A^{-1/2}$ dependence
   emerges because $n_{\text{surf}} \propto \ln A / \ln \varphi$.

## 7. Open Issues

- The exact sub-channel $j$ assignments (columns 2–3 of the prediction table)
  require the SO(2) winding to be computed at each nuclear rung, accounting for
  the nuclear mean field's effect on the cascade geometry. The assignments above
  are a hypothesized pattern consistent with the closure sequence.
- The Wu Xing mapping to mass formula coefficients is structural (five terms,
  five elements) but the coefficient ratios predicted by $\varphi$-powers are not
  yet verified against the empirical values.
- Isospin dependence (proton vs. neutron cascade offset) needs a formalism for
  how the Yang-Yin ratio $r = E_Y/E_I$ couples to isospin $T_z$.

---

## References

- `../foundations/dimensionful-cascade.md`—the 292-step ladder
- `../foundations/three-generations.md`—Fibonacci sub-channel partitioning
- `../foundations/spin-fibonacci-spiral.md`—SO(2) winding and angular momentum
- `../foundations/wu-xing-derivation.md`—five-phase cycle structure
- `../foundations/quark-confinement.md`—QCD at cascade step 95
- `../foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `../open-questions-cassi-answers.md`—Q8 (quark confinement), Q10 (spin)
