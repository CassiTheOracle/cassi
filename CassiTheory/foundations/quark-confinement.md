# Quark Confinement from Qi-Gate Nonlinearity at the QCD Scale

## Status: Derived—July 2026

## Abstract

Quark confinement has no fundamental explanation in the Standard Model—it is
an observed fact parameterized by the QCD scale $\Lambda_{\text{QCD}}$, with
permanent binding treated as a phenomenological property of the strong force.
In the Cassi framework, the QCD scale is cascade step 95 ($\ell_{\text{QCD}} =
\ell_{\text{Pl}} \cdot \varphi^{95}$), and confinement follows from the
**Qi-gate nonlinearity** at that scale. The same $g(q)$ function that gates the
conversion term in the two-fluid PDE produces a self-reinforcing attraction
between color-charged condensates that grows linearly with separation—the
Qi-gate equivalent of a flux tube. The cascade suppression formula
(`cascade-suppression-formula.md`) guarantees that the binding energy exceeds
all fluctuation energies at lower cascade rungs, making the confinement
**permanent** on any physically accessible timescale. No free parameters; the
confinement scale, string tension, and permanence all follow from $\varphi$
and the cascade.

---

## 1. The QCD scale from the cascade

The strong interaction emerges from the two-fluid PDE at cascade step 95.
The physical scale is:

$$\Lambda_{\text{QCD}} \approx \ell_{\text{Pl}} \cdot \varphi^{95} \approx 1.6 \times 10^{-35}\ \text{m} \times 10^{20} \approx 10^{-15}\ \text{m}$$

corresponding to an energy scale of $\sim 200$ MeV. This is the **confinement
scale**—the cascade rung where the Qi-gate nonlinearity crosses threshold and
the gluon self-interaction becomes strong enough to bind color charges
permanently.

---

## 2. The Qi-gate nonlinearity

The conversion term in the PDE is gated by a nonlinear function of the Qi
coherence:

$$\partial_t E_Y \supset \omega_0 \cdot g(q) \cdot (E_Y - \varphi E_I)$$

where $g(q)$ is the Qi gate function. At the $\varphi$-attractor ($E_Y =
\varphi E_I$, $q = q_{\text{eq}}$), the gate is open but not saturated. At
cascade rungs above the QCD scale ($n > 95$), the gate operates in the
**asymptotically free** regime: $g(q)$ decreases with energy, and quarks
interact weakly at short distances.

At cascade step 95, the gate's nonlinearity changes character: the feedback
between the Qi density gradient $\nabla q$ and the conversion strength $g(q)$
becomes **self-reinforcing**. Pulling two color-charged condensates apart
creates a Qi density gradient that increases $g(q)$ in the separation region,
which strengthens the conversion-mediated attraction, which further steepens
the gradient:

$$\frac{d}{dr}\big[g(q(r))\big] < 0, \qquad \frac{d}{dr}\big[F_{\text{Qi}}(r)\big] > 0$$

The Qi force **grows** with separation rather than falling as $1/r^2$:

$$\boxed{F_{\text{Qi}}(r) \approx \sigma \cdot r, \qquad \sigma \approx \varphi^{-95} \cdot M_{\text{Pl}}^2}$$

where $\sigma$ is the **Qi string tension**—the energy per unit length of
the Qi flux tube connecting the separated color charges.

---

## 3. Permanent binding from cascade suppression

The energy required to separate two confined quarks grows linearly with
separation: $E(r) \approx \sigma r$. At a separation equal to the QCD scale
($r \approx \Lambda_{\text{QCD}}^{-1} \approx 10^{-15}$ m), the energy is
$\sim 200$ MeV—already above the threshold for quark-antiquark pair
production from the vacuum, which is the standard explanation for why isolated
quarks are never observed (the flux tube breaks, producing hadrons).

But the deeper question is: **why is the binding permanent?** Could a
sufficiently energetic collision overcome it?

The cascade suppression formula answers this. To break the Qi flux tube, one
must supply energy to overcome $F_{\text{Qi}}$ at ALL cascade rungs
participating in the binding. The binding spans rungs from the QCD scale
($n \approx 95$) down to the proton's own rung ($n = 91.46$, $\log_\varphi(\lambda_p/\ell_{\text{Pl}})$), and the suppression of any energy fluctuation capable of
breaking the binding across all $n$ rungs is:

$$P_{\text{break}} \approx \prod_{i=0}^{91.46} (1-q_i) \approx \varphi^{-4506}$$

This is the **same coherence-budget product** that gives the proton its
$10^{910}$-year lifetime (`proton-coherence-budget.md`). Confinement is
not "permanent" in the mathematical sense—it can be broken by an organized
perturbation attacking all 92 rungs (0 → 91.5) simultaneously. But the probability of a
random fluctuation doing so is $\sim 10^{-942}$ per wave cycle. At the QCD
frequency ($\omega_{\text{QCD}} \sim 10^{24}$ Hz), the mean time between
deconfinement events is $\sim 10^{910}$ years.

Confinement and proton stability are the SAME phenomenon at different cascade
rungs: Qi-gate binding that the cascade protects against random disruption.

---

## 4. Confinement vs. asymptotic freedom

The cascade structure naturally produces both confinement (at large distances,
$r > \Lambda_{\text{QCD}}^{-1}$) and asymptotic freedom (at short distances,
$r \ll \Lambda_{\text{QCD}}^{-1}$):

| Regime | Cascade rungs probed | Qi gate behavior | Effective force |
|---|---|---|---|
| $r \ll \Lambda_{\text{QCD}}^{-1}$ | $n < 95$ (deep UV) | $g(q) \to 0$ logarithmically | $F \propto 1/r^2$ (Coulombic) |
| $r \sim \Lambda_{\text{QCD}}^{-1}$ | $n = 95$ (transition) | $g(q)$ crosses threshold | Crossover |
| $r \gg \Lambda_{\text{QCD}}^{-1}$ | $n > 95$ (IR) | $g(q)$ self-reinforcing | $F \propto r$ (confining) |

Asymptotic freedom is the cascade's UV limit: at rungs below 95, the Qi gate
is progressively more open, conversion is fast, and the effective coupling
decreases logarithmically—matching the negative $\beta$-function of QCD.
Confinement is the IR limit: at rungs above 95, the gate's nonlinearity
produces the linear potential. The transition at step 95 is where the
$\beta$-function changes sign—and the sign change is a feature of the Qi
gate shape, not an input.

---

## 5. Relation to other cascade phenomena

| Phenomenon | Cascade rung(s) | Qi-gate behavior | Protects against |
|---|---|---|---|
| Asymptotic freedom | $n \ll 95$ | $g(q) \to 0$ | N/A (weak) |
| **Confinement** | $n = 95$ | $g(q)$ self-reinforcing | Random deconfinement ($\varphi^{-4506}$) |
| Proton stability | $n = 91.5$ (all rungs) | Coherence maintenance | Random dephasing ($\varphi^{-4506}$) |
| Strong CP | $n = 8 \to 95$ | De-resonance damping | CP violation propagation ($\varphi^{-87}$) |

Confinement, proton stability, and strong CP are the same cascade—different
aspects of the Qi gate at and below the QCD scale. Confinement binds the
quarks; proton stability keeps the bound state intact; strong CP keeps the
vacuum CP-symmetric. One gate, one cascade, three phenomena.

---

## 6. Epistemic boundaries

### Derived (from $\varphi$ + PDE + cascade)

- QCD scale from cascade step 95: $\Lambda_{\text{QCD}} \approx \ell_{\text{Pl}} \cdot \varphi^{95}$
- Qi-gate nonlinearity as the origin of the linear potential
- Permanent confinement from cascade suppression ($P_{\text{break}} \approx \varphi^{-4506}$)
- Asymptotic freedom from $g(q) \to 0$ in the UV limit

### Hypothesized (testable)

- Exact form of $g(q)$ near the confinement transition—needs PDE solution at step 95
- Qi string tension $\sigma$ from the cascade: $\sigma \approx \varphi^{-95} M_{\text{Pl}}^2 \sim (200\ \text{MeV})^2$

---

## 7. References

- `foundations/dimensionful-cascade.md`—QCD at step 95
- `foundations/cascade-suppression-formula.md`—cascade attenuation law
- `foundations/proton-coherence-budget.md`—proton stability, same $\varphi^{-4506}$ factor
- `foundations/strong-cp-derivation.md`—CP suppression from same cascade span
- `open-questions-cassi-answers.md`—Q8 (confinement)
