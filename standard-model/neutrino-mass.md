# Neutrino Mass from $\varphi$

## Status: Hypothesized—July 2026

## Abstract

Neutrinos are the lightest fermions by far: masses of $\sim 0.001\!-\!0.1\ \text{eV}$ against $0.511\ \text{MeV}$ for the electron. This primer derives the seesaw scale from the Cassi cascade—the right-handed neutrino sits at cascade step 20, $M_R \approx 10^{14}\ \text{GeV}$—and presents the canonical mass spectrum from the Fibonacci cascade partition of the compressed seesaw span: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019\ \text{eV}$ ($\sum m_\nu = 0.0631\ \text{eV}$, normal ordering, no sterile neutrino). The full derivation lives in `foundations/neutrino-masses.md`; this document is the pedagogical entry point.

## 1. The Problem

Neutrinos have mass $\sim 0.001\!-\!0.1\ \text{eV}$, far below charged fermions.
The ratio to the electron mass $m_\nu/m_e \sim 10^{-5}$ is six orders of
magnitude below the next-lightest charged fermion. A natural suppression
mechanism is required.

## 2. The Seesaw Mechanism

Introduce a right-handed neutrino $\nu_R$ with Majorana mass $M_R$. After
electroweak symmetry breaking, the light neutrino mass is:

$$
\boxed{m_\nu \approx \frac{y_\nu^2\,v_0^2}{M_R}}
$$

where $v_0 = 246\ \text{GeV}$ is the Higgs VEV and $y_\nu$ is the neutrino
Yukawa coupling. The seesaw scale is fixed by the cascade: the right-handed
neutrino sits at **cascade step 20**, between the GUT scale (n ≈ 13.3 for
$M_{\text{GUT}} \approx 2\times10^{16}$ GeV) and
the electroweak scale (step 80) (`foundations/dimensionful-cascade.md`):

$$
M_R \approx \ell_{\text{Pl}}^{-1}\,\varphi^{-20} \approx 10^{14}\ \text{GeV}
$$

—the intermediate scale familiar from $B\!-\!L$ breaking chains. For
$y_\nu \sim \mathcal{O}(1)$:

$$
m_\nu \sim \frac{(246\ \text{GeV})^2}{10^{14}\ \text{GeV}} \sim 0.6\ \text{eV}.
$$

The observed spectrum sits below this naive scale; its structure comes from the
cascade partition of the seesaw span (Section 4).

## 3. A First Candidate: $M_R = \varphi^{-3} M_{\text{GUT}}$

The simplest Cassi ansatz fixes $M_R$ by a single $\varphi$-power: three
generations of right-handed neutrinos, each contributing one factor of
$\varphi^{-1}$, give

$$
M_R = \varphi^{-3}\,M_{\text{GUT}} \approx 0.236 \times 2\times10^{16}\ \text{GeV}
    \approx 4.7 \times 10^{15}\ \text{GeV},
$$

and through the seesaw, $m_\nu \approx \varphi^{-3}\,v_0^2/M_{\text{GUT}}$
with $\varphi$-suppressed lighter generations ($m_2 \approx 0.0050$,
$m_1 \approx 0.0019\ \text{eV}$).

## 4. The Canonical Derivation: Fibonacci Cascade Partition

The canonical derivation (`foundations/neutrino-masses.md`) applies the
three-generations Fibonacci mechanism (`foundations/three-generations.md`) to
the **compressed** cascade span from the GUT-scale Yukawa seed (n
$\approx 13.3$) to seesaw freeze-out (step 20): $N_\nu \approx 7$ rungs.
The sector is Mapped per the Fit-Status Ledger (`parameter-inventory.md` §10). The
seesaw's $y_\nu^2$ structure doubles the $\varphi$-exponent, so mass ratios
between Fibonacci sub-rungs are

$$
\frac{m_{\nu_2}}{m_{\nu_1}} = \varphi^{2\Delta_1}, \qquad
\frac{m_{\nu_3}}{m_{\nu_2}} = \varphi^{2\Delta_2}.
$$

The cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`) pins
the offsets against the observed $\Delta m^2_{31}/\Delta m^2_{21} \approx
33.89$:

$$
\Delta_1 = 1.00\ \text{rungs},\qquad \Delta_2 = 1.75\ \text{rungs},\qquad
\frac{\Delta m^2_{31}}{\Delta m^2_{21}}
= \frac{\varphi^{11}-1}{\varphi^{4}-1} \approx 33.82
$$

—a 0.2% residual to observation. The resulting spectrum is the boxed result
of this document:

$$
\boxed{m_1 = 0.00356\ \text{eV},\qquad m_2 = 0.00931\ \text{eV},\qquad
m_3 = 0.05019\ \text{eV},\qquad \sum m_\nu = 0.0631\ \text{eV}}
$$

**Normal ordering** ($m_3 > m_2 > m_1$) follows from the Fibonacci triple
ordering; **no sterile neutrino** exists at cascade-accessible scales.

## 5. Predictions

| Observable | Cassi | Experiment |
|:---|:---:|:---|
| Mass ordering | Normal ($m_1 < m_2 < m_3$) | JUNO / DUNE |
| Lightest mass | $m_1 = 0.00356\ \text{eV}$ | KATRIN, cosmological |
| $0\nu\beta\beta$ | $\lvert m_{\beta\beta}\rvert = 0.0043\!-\!0.0052\ \text{eV}$ | nEXO, LEGEND-1000 |
| KATRIN endpoint | $m_\beta = 0.0092\ \text{eV}$ | KATRIN |
| Mass sum | $\sum m_\nu = 0.0631\ \text{eV}$ | CMB + BAO bounds |

## 6. References

- `foundations/neutrino-masses.md`—canonical Fibonacci cascade-partition derivation
- `foundations/three-generations.md`—Fibonacci triple-clustering, $N_{\text{gen}} = 3$
- `foundations/dimensionful-cascade.md`—seesaw at cascade step 20
- `foundations/cascade-suppression-formula.md`—cascade attenuation law
- `computations/cascade_rge_pmns.py`—pinned offsets and mass spectrum
- `standard-model/sm-from-phi.md`—Yukawa hierarchy and seesaw context
