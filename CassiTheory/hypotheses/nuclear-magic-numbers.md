# Nuclear Magic Numbers from the Cascade Ladder

## Status: Hypothesized—July 2026

## Abstract

Nuclear shell-model magic numbers (2, 8, 20, 28, 50, 82, 126) have no
first-principles derivation in standard nuclear physics—they are inferred from
experimental systematics and reproduced by phenomenological spin-orbit coupling.
The Cassi framework provides a structural alternative: magic numbers are
Fibonacci sub-channel closures within the cascade span from QCD confinement (step
95) down to nuclear binding (steps ~101–106). The SO(2) doublet winding at each
sub-rung produces angular momentum channels, and Fibonacci partitioning of the
cascade determines which channels close at each rung. The closure arithmetic as
written does not close (0/7 rows, §3): the cumulative channel sums are 8, 20, 38,
54, 78, 108, 144, not 2, 8, 20, 28, 50, 82, 126, so the sequence is not currently
generated from $\varphi$ without adjustment. The sub-channel pattern remains
**Hypothesized** with an open arithmetic gap; the $\varphi$-power level-spacing
prediction (§4) is independent of the closure rows and remains testable.

## Origin Status

**Verdict: catalog correspondence; mechanism open.** Recomputation
(`computations/verify_hypotheses_origin_audit.py`, 2026-08-11) confirms:

- **Closure arithmetic.** The doc's own rule $N_{\text{magic}} = \sum_i
  \Omega_{j_i}$ cumulated over the §3 sub-channel row sums (8, 12, 18, 16,
  24, 30, 36) gives 8, 20, 38, 54, 78, 108, 144 versus the claimed 2, 8, 20,
  28, 50, 82, 126 — **0 of 7 rows close** (the abstract already states this).
  The step "SO(2) winding
  $\Rightarrow s = \Delta n$" $\Rightarrow$ "sub-channel capacity
  $\Omega_j = 2j + 1$" is asserted; no dynamics selects the $j$ assignments.
- **Ladder placement.** The magic nuclei sit at
  $n = \log_\varphi(M_{\text{Pl}}/m)$: $^{208}$Pb 80.39, $^{90}$Zr 82.13,
  $^{56}$Ni 83.11, $^{48}$Ca 83.43, $^{16}$O 85.72 — scattered over steps
  80–86 with no special-point structure. These are the nuclei's masses read
  off the ladder; the ladder itself supplies no closure rule.
- **Island of stability.** The §6 claim "126 + Fib$(n_{\text{next}})$ = 126 +
  58 = 184" mislabels 58 as Fibonacci: the sequence near 184 runs $\ldots, 34,
  55, 89, 144$, and 126 + 55 = 181, 126 + 89 = 215 — neither equals 184.
  The $N = 184$ prediction is an independent nuclear-structure result that the
  Fibonacci closure rule does not reproduce (§6 corrected).
- **Level spacing (§4)** remains a zero-parameter, testable prediction
  independent of the failed closure rows; its mechanism (why the spacing
  should be $\varphi^{-j}$) is likewise open.

The magic sequence 2, 8, 20, 28, 50, 82, 126 is a real spectroscopic fact whose
standard explanation (harmonic-oscillator shells $2n^2$ plus a fitted
spin-orbit strength) contains no $\varphi$. Calling it a "Fibonacci
sub-channel closure" is therefore a correspondence chosen after the fact.
Tier stays **Hypothesized** for the §4 level-spacing prediction only; the
closure claim is open.

---

## 1. The Cascade at Sub-QCD Scales

The cascade ladder (`foundations/dimensionful-cascade.md`) anchors QCD
confinement at step 95 ($\Lambda_{\text{QCD}} \approx 200$ MeV). Nuclear binding
energies (1–10 MeV per nucleon) correspond to steps ~101–106—the energy scale
$\ell_n = \ell_{\text{Pl}} \times \varphi^n$ with $n \approx 101$–$106$ gives
$\sim$1–10 MeV.

Cascade step 0 (Planck) up to step 95 (QCD):
$$\ell_n = \ell_{\text{Pl}} \cdot \varphi^n$$

The nuclear landscape occupies a 13.7-rung span from the nucleon mass (step
91.5, ~938 MeV; $n = \log_\varphi(M_{\text{Pl}}/m_p) = 91.46$) to the
neutron-proton mass difference (step 105.2, ~1.3 MeV; $n = 105.15$). This span is
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

| Cascade rung | Sub-channels (j) | $\Omega_j = 2j+1$ | Row sum | Cumulative closure (computed) | Claimed magic number | Verdict |
|-------------|-------------------|------------|---------|---------------------------|---------------------|---------|
| 95 (bottom) | 1/2, 1/2, 3/2 | 2 + 2 + 4 | 8 | 8 | 2 | does not close—nearest sum 8 |
| 94 | 1/2, 3/2, 5/2 | 2 + 4 + 6 | 12 | 20 | 8 | does not close—nearest sum 20 |
| 93 | 3/2, 5/2, 7/2 | 4 + 6 + 8 | 18 | 38 | 20 | does not close—nearest sum 38 |
| 92 | 1/2, 5/2, 7/2 | 2 + 6 + 8 | 16 | 54 | 28 | does not close—nearest sum 54 |
| 91 | 5/2, 7/2, 9/2 | 6 + 8 + 10 | 24 | 78 | 50 | does not close—nearest sum 78 |
| 91.5 (nucleon) | 7/2, 9/2, 11/2 | 8 + 10 + 12 | 30 | 108 | 82 | does not close—nearest sum 108 |
| 89 | 9/2, 11/2, 13/2 | 10 + 12 + 14 | 36 | 144 | 126 | does not close—nearest sum 144 |

Recomputed with the doc's own rule ($N_{\text{magic}} = \sum_i \Omega_{j_i}$,
cumulative over closed sub-channels), **0 of 7 rows close at the claimed magic
number**. The cumulative sums (8, 20, 38, 54, 78, 108, 144) reproduce the
claimed closures at rows 95 and 94 only by coincidence of one-rung offsets
(8 = row 95's sum; 20 = rows 95+94); the remaining rows fail by factors of
1.4–1.9. The sub-channel $j$ assignments are a hypothesized pattern
(§7) and do not, as written, generate the sequence.

The gaps of the *claimed* sequence are arithmetic facts ($8 - 2 = 6$, $20 - 8 = 12$, $28 - 20 = 8$, $50 - 28 = 22$, $82 - 50 = 32$, $126 - 82 = 44$), but the successive ratios ($12/6 = 2$, $22/8 = 2.75$, $32/22 \approx 1.45$, $44/32 \approx 1.38$) do not approach $\varphi \approx 1.618$ or its Fibonacci convergents (nearest convergents: 2, 3/2, 5/3, 8/5, 13/8).

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

2. **No new magic numbers:** The cascade was intended to predict exactly the
   observed sequence; with the closure arithmetic open (0/7 rows, §3), this
   test is not yet well-posed. Any new magic number (e.g., 34, 40, 58)
   discovered in exotic nuclei far from stability would falsify the Fibonacci
   closure pattern once the sub-channel assignments are fixed.

3. **Island of stability:** The next doubly-magic nucleus beyond $^{208}$Pb is
   a candidate test for the closure rule — but the Fibonacci closure as
   written does not work: $184 - 126 = 58$, and 58 is not a Fibonacci number
   (the sequence near 184 runs $\ldots, 34, 55, 89, 144$; $126 + 55 = 181$,
   $126 + 89 = 215$, neither equals 184). The $N = 184$ island-of-stability
   prediction is an independent nuclear-structure result; it cannot be cited
   as a cascade closure until the §3 arithmetic closes.

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

- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `foundations/three-generations.md`—Fibonacci sub-channel partitioning
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding and angular momentum
- `foundations/wu-xing-derivation.md`—five-phase cycle structure
- `foundations/quark-confinement.md`—QCD at cascade step 95
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation
- `open-questions-cassi-answers.md`—Q8 (quark confinement), Q10 (spin)
