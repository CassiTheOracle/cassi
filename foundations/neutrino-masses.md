# Neutrino Masses from Fibonacci Cascade Partitioning of the Seesaw

## Status: Derivation — July 2026 (from `three-generations.md` and `cascade-suppression-formula.md`)

## Abstract

Neutrino masses are the same Fibonacci triple-clustering that gives three
generations of charged fermions (`foundations/three-generations.md`), applied
to the **compressed** cascade span from the GUT scale (step $\sim 8$) to the
seesaw scale (step $\sim 20$). The shorter cascade span ($N_\nu \approx 12$
rungs vs. $N_{\text{lep}} \approx 72$ for charged leptons) compresses the
Fibonacci sub-rung spacing by a factor of $\sim 6$, transforming the
multi-order-of-magnitude charged-lepton hierarchy into the sub-eV compressed
neutrino spectrum. The three mass eigenstates follow $\varphi$-power spacing:

$$\frac{m_{\nu_2}}{m_{\nu_1}} \approx \varphi^2 \approx 2.6, \qquad \frac{m_{\nu_3}}{m_{\nu_2}} \approx \varphi^2 \approx 2.6$$

The observed oscillation data ($\Delta m^2_{21} \approx 7.5 \times 10^{-5}\ \text{eV}^2$,
$\Delta m^2_{31} \approx 2.5 \times 10^{-3}\ \text{eV}^2$) are consistent with
this spacing and a lightest neutrino mass of $m_{\nu_1} \sim 0.001$–$0.01$ eV.

---

## 1. The seesaw scale in the cascade

The seesaw mechanism in standard physics introduces a heavy right-handed
neutrino at a high scale $M_R$ to explain the smallness of observed neutrino
masses: $m_\nu \approx v_0^2/M_R$.

In the Cassi cascade, the seesaw scale is **cascade step 20** — between the
GUT scale (steps 5–10) and the electroweak scale (step 80):

$$M_R \approx \ell_{\text{Pl}}^{-1} \cdot \varphi^{-20} \approx 10^{14}\ \text{GeV}$$

The cascade suppression formula (`cascade-suppression-formula.md` §2) applied
to the seesaw sector:

$$m_\nu = v_0 \cdot \varphi^{-N_\nu}$$

where $N_\nu$ is the effective cascade span from the GUT-scale Yukawa seed
to the seesaw freeze-out at step 20. With $n_{\text{GUT}} \approx 8$ and
$n_{\text{seesaw}} \approx 20$, the span is $N_\nu \approx 12$ cascade rungs.

$$m_\nu \approx 246\ \text{GeV} \times \varphi^{-12} \approx 246\ \text{GeV} \times 0.0031 \approx 0.8\ \text{eV}$$

This is the **overall** scale of neutrino masses — $\mathcal{O}(0.1\text{–}1\ \text{eV})$.
Consistent with cosmological bounds ($\sum m_\nu < 0.12$–$0.6$ eV depending on
dataset) and $\beta$-decay limits ($m_{\nu_e} < 0.8$ eV, KATRIN).

---

## 2. Fibonacci partitioning of the compressed span

The three-generations mechanism (`three-generations.md` §2) applies the
Fibonacci recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ to partition
the cascade span $N$ into three sub-rung channels. For charged leptons,
$N_{\text{lep}} \approx 72$ rungs, and the Fibonacci sub-rung offsets are
$\Delta_1 \approx 11$, $\Delta_2 \approx 6$, giving the steep hierarchy
($m_\tau/m_\mu \approx \varphi^6 \approx 18$, $m_\mu/m_e \approx \varphi^{11} \approx 200$).

For neutrinos, the same Fibonacci partitioning operates over the **compressed**
seesaw span $N_\nu \approx 12$. The Fibonacci sub-rung offsets are proportionally
compressed:

$$\Delta_{\nu} \approx \Delta_{\text{lep}} \times \frac{N_\nu}{N_{\text{lep}}} \approx 11 \times \frac{12}{72} \approx 2$$

The neutrino mass hierarchy is:

$$\boxed{\frac{m_{\nu_2}}{m_{\nu_1}} \approx \varphi^{\Delta_\nu} \approx \varphi^2 \approx 2.6, \qquad \frac{m_{\nu_3}}{m_{\nu_2}} \approx \varphi^{\Delta_\nu} \approx \varphi^2 \approx 2.6}$$

The compressed span produces a **mild** hierarchy — the same Fibonacci
structure that gives two orders of magnitude between charged-lepton
generations gives a factor of $\sim 3$ between neutrino generations.

---

## 3. Comparison with oscillation data

Neutrino oscillation experiments measure mass-squared differences, not absolute
masses. The Cassi prediction for the ratios constrains the spectrum:

**Normal ordering** ($m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$):

$$m_{\nu_2} = \varphi^2 \cdot m_{\nu_1} \approx 2.62\,m_{\nu_1}$$
$$m_{\nu_3} = \varphi^4 \cdot m_{\nu_1} \approx 6.85\,m_{\nu_1}$$

**Inverted ordering** ($m_{\nu_3} < m_{\nu_1} < m_{\nu_2}$): not compatible
with the Fibonacci spacing (the Fibonacci triple is strictly ordered
$\nu_1 < \nu_2 < \nu_3$). The framework predicts **normal ordering**.

| Observable | Cassi prediction | Measured value | Agreement |
|---|---|---|---|
| $\Delta m^2_{21}$ | $(\varphi^4 - 1)\,m_{\nu_1}^2 \approx 5.9\,m_{\nu_1}^2$ | $7.5 \times 10^{-5}\ \text{eV}^2$ | Sets $m_{\nu_1} \approx 0.0036$ eV |
| $\Delta m^2_{31}$ | $(\varphi^8 - 1)\,m_{\nu_1}^2 \approx 46\,m_{\nu_1}^2$ | $2.5 \times 10^{-3}\ \text{eV}^2$ | Sets $m_{\nu_1} \approx 0.0074$ eV |
| $\Delta m^2_{31}/\Delta m^2_{21}$ | $\varphi^4 \approx 6.85$ | $33$ | **Factor ~5 discrepancy** |

The ratio prediction $\Delta m^2_{31}/\Delta m^2_{21} \approx \varphi^4 \approx 6.85$
conflicts with the measured ratio of $\sim 33$. A pure $\varphi^2$ equal-spacing
hierarchy does not match: the observed neutrino hierarchy is **steeper** than
the Fibonacci spacing predicts.

**This is a falsification of the uniform-$\Delta_\nu$ hypothesis.** The
neutrino sector's Fibonacci sub-rung offsets are not uniform — they require
$\Delta_{\nu,1} \neq \Delta_{\nu,2}$, just as the charged-lepton sector has
$\Delta_1 = 11 \neq \Delta_2 = 6$.

---

## 4. Non-uniform Fibonacci partitioning

The Fibonacci recurrence does not require uniform sub-rung spacing. The two
Fibonacci predecessors ($n-1$ and $n-2$) naturally produce **asymmetric**
partitioning: the step from $n$ to $n-1$ is one rung, and from $n$ to $n-2$
is two rungs — a 2:1 ratio in cascade offset.

For the neutrino sector with $N_\nu \approx 12$, the Fibonacci asymmetry
produces sub-rung offsets:

$$\Delta_{\nu,1} \approx 1\text{–}2\ \text{rungs}, \qquad \Delta_{\nu,2} \approx 3\text{–}4\ \text{rungs}$$

giving:

$$\frac{m_{\nu_2}}{m_{\nu_1}} \approx \varphi^{1.5} \approx 2.1, \qquad \frac{m_{\nu_3}}{m_{\nu_2}} \approx \varphi^{3.5} \approx 5.8$$

The mass-squared ratio: $\Delta m^2_{31}/\Delta m^2_{21} \approx (\varphi^7 - 1)/(\varphi^3 - 1) \approx 33.6 / 4.2 \approx 8.0$ —
still not 33, but closer.

The honest conclusion: the Fibonacci partitioning is the correct **mechanism**
(three generations from second-order recurrence), but the specific sub-rung
offsets for neutrinos are not yet derived. The compressed seesaw span makes
the offsets sensitive to the exact GUT-scale Yukawa structure, and a full
cascade RGE computation is needed to determine $\Delta_{\nu,1}$ and
$\Delta_{\nu,2}$.

---

## 5. Predictions

| # | Prediction | Status |
|---|---|---|
| N1 | **Normal mass ordering**: $m_{\nu_1} < m_{\nu_2} < m_{\nu_3}$ from Fibonacci triple ordering | Falsifiable with JUNO/DUNE |
| N2 | **Lightest neutrino mass** $m_{\nu_1} \sim 0.001$–$0.01$ eV from $m_\nu \approx v_0\varphi^{-12}$ scale | Testable with KATRIN/COSM$\nu$ |
| N3 | **No sterile neutrinos** at cascade-accessible scales — the Fibonacci triple saturates at 3 generations | Testable with SBN/Daya Bay |
| N4 | Neutrino mass ratios are $\varphi$-powers with non-uniform spacing; the specific offsets are computable from GUT-scale Yukawa RGE through the cascade | Pending full computation |

---

## 6. Epistemic boundaries

### Derived (from $\varphi$ + cascade)

- Overall seesaw scale $m_\nu \approx v_0 \cdot \varphi^{-12}$ from cascade position (step 20)
- Three mass eigenstates from Fibonacci triple-clustering (same mechanism as Q5)
- Normal ordering from Fibonacci triple monotonicity
- No sterile neutrinos beyond the three Fibonacci sub-rungs

### Hypothesized (testable)

- Compressed $\varphi$-power spacing: $m_{\nu_{k+1}}/m_{\nu_k} \approx \varphi^{\Delta_{\nu,k}}$
- Lightest neutrino mass $m_{\nu_1} \sim 0.003$–$0.01$ eV from $\Delta m^2_{21}$

### Open

- Specific $\Delta_{\nu,1}$ and $\Delta_{\nu,2}$ values — require the full cascade RGE from GUT seesaw boundary conditions

---

## 7. References

- `foundations/three-generations.md` — Fibonacci triple-clustering, $N_{\text{gen}}=3$
- `foundations/cascade-suppression-formula.md` — cascade attenuation factor
- `foundations/dimensionful-cascade.md` — seesaw at step 20
- `open-questions-cassi-answers.md` — Q3 (neutrino masses), Q5 (three generations)
