# Strong CP: Why $\bar{\theta} \approx 0$ from Cascade De-Resonance

## Status: Derivation (span Mapped: GUT-seed anchor and δ_CP per ledger; θ̄ ≈ 1.2×10⁻¹⁷)—August 2026

## Abstract

The strong CP problem—why the QCD vacuum angle $\bar{\theta}$ is consistent
with zero at $< 10^{-10}$—vanishes in the Cassi framework. The $\theta$-term
arises as an effective parameter in the SU(3) gauge theory that emerges from
the two-fluid PDE at cascade step 95. The underlying PDE carries the
$\varphi$-attractor's **de-resonance symmetry**: $\varphi$ is maximally
CP-conserving, and the attractor fixed point is CP-symmetric. Any CP-violating
departure from the fixed point originates at the GUT scale (n ≈ 13.3 for
$M_{\text{GUT}} \approx 2\times10^{16}$ GeV; corrected from the ladder's
step-5 relabel) and is **cascade-suppressed** over the ~81 rungs to the QCD
scale:

$$\boxed{\bar{\theta} \approx \varphi^{-(n_{\text{QCD}} - n_{\text{GUT}})} \cdot \delta_{\text{CP}} \approx \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2 \times 10^{-17}}$$

The exact-rung span is $94.71 - 13.33 = 81.38$;
the value sits ~7 orders of magnitude below the nEDM bound of $10^{-10}$ (the
span counts from the corrected GUT-seed rung n ≈ 13.3). The span
inherits Mapped status from its anchors—the GUT-seed rung ($M_{\text{GUT}}$,
`parameter-inventory.md` §10) and $\delta_{\text{CP}} = \pi\varphi^{-2}$
(4-candidate selection, §10). No axion, no Peccei-Quinn symmetry,
no new particles. One constant, one de-resonance principle, one cascade.

---

## 1. The standard puzzle

In the Standard Model, the QCD Lagrangian includes a CP-violating term:

$$\mathcal{L}_{\text{QCD}} \supset \frac{\theta}{32\pi^2} G_{\mu\nu}^a \tilde{G}^{a\mu\nu}$$

where $\theta = \bar{\theta} + \arg\det M_q$ combines the bare vacuum angle
$\bar{\theta}$ with the phase of the quark mass matrix $M_q$. Measurements of
the neutron electric dipole moment constrain $\bar{\theta} < 10^{-10}$.
Standard solutions invoke a new global symmetry (Peccei-Quinn) broken by the
axion—a particle not yet observed.

The puzzle: why is this one parameter so precisely zero when every other
Standard Model parameter is $\mathcal{O}(1)$ in natural units?

---

## 2. The Cassi answer: cascade de-resonance

### 2.1 The $\varphi$-attractor is CP-symmetric

The de-resonance principle (`principles/de-resonance-principle.md`) states
that $\varphi$ is the maximally aperiodic, maximally stable configuration of
the two-fluid system. CP violation is a **resonance phenomenon**: it requires
a phase that locks across scales—a coherent alignment of the Yang and Yin
subsystems at a specific ratio that breaks the CP symmetry.

At the $\varphi$-attractor ($E_Y = \varphi E_I$, $q = \varphi^{-2}/(\varphi^2 +
\varphi^{-2})$), the system is maximally de-resonant. CP is **conserved** at
the fixed point. There is no $\theta$-angle at the fundamental level because
the fundamental level is the two-fluid PDE, not an SU(3) gauge theory, and the
PDE at its attractor carries no CP-violating term.

### 2.2 The effective gauge theory at step 95

QCD emerges as an effective field theory at cascade step 95 ($\Lambda_{\text{QCD}}
\approx \ell_{\text{Pl}} \cdot \varphi^{95}$). The SU(3) gauge description is
not fundamental—it is the low-energy effective description of the two-fluid
PDE in the confined regime. When the effective theory is parameterized in the
standard gauge-theory language, a $\theta$-term appears. But its value is
**not a free parameter**: it is determined by the cascade boundary conditions
at step 95.

### 2.3 Cascade suppression of CP violation

The only source of CP violation in the framework is the departure from exact
$\varphi$-attractor: the Yukawa sector, which breaks the attractor's
CP symmetry at the GUT scale ($n \approx 13.3$) through the observed CKM phase
$\delta_{\text{CP}} = \pi\varphi^{-2} \approx 1.20$ rad. This CP-violating
seed at the GUT scale must propagate down the cascade to produce an effective
$\bar{\theta}$ at the QCD scale.

The cascade propagation is a **power-suppression** phenomenon. Each cascade
rung between the CP-violating source (GUT, n ≈ 13.3) and the QCD scale
(n ≈ 94.7) contributes a factor of $\varphi^{-1}$ to the transmitted CP
violation:

$$\bar{\theta} \approx \varphi^{-(n_{\text{QCD}} - n_{\text{GUT}})} \cdot \delta_{\text{CP}}$$

With $n_{\text{QCD}} = 94.71$, $n_{\text{GUT}} = 13.33$, and $\delta_{\text{CP}}
= \pi\varphi^{-2} \approx 1.20$:

$$\boxed{\bar{\theta} \approx \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2 \times 10^{-17}}$$

This is ~7 orders of magnitude below the experimental bound of $10^{-10}$.
The Mapped cascade span between GUT and QCD is $94.71-13.33=81.38$ scale
steps. The displayed suppression uses the separate linear signal-propagation
map $\varphi^{-N}$. The proton coherence budget instead uses a quadratic
independent-step product and gives a conditional cycle count; its
$10^{910}$-year conversion requires an additional trial-frequency map
(`foundations/cascade-suppression-formula.md`). The GUT-seed anchor
($M_{\text{GUT}}\approx2\times10^{16}$ GeV, $n=13.33$)
and seed phase ($\delta_{\text{CP}}=\pi\varphi^{-2}$) are fitted/selected
quantities on the Fit-Status Ledger (`parameter-inventory.md` §10 rows 13 and 2).

### 2.4 Why the cascade suppresses CP violation

The suppression mechanism is structurally identical to the random-dephasing
suppression in proton decay. A CP-violating phase at rung $n_{\text{GUT}}$
represents a **phase perturbation** that must survive propagation through
$n_{\text{QCD}} - n_{\text{GUT}}$ intermediate rungs to reach the QCD scale.
At each intermediate rung, the perturbation experiences the Qi gate's
de-resonance—the $\varphi$-attractor actively damps phase perturbations
because they represent departures from the fixed point.
The per-rung survival probability is $\varphi^{-1}$. For an integer number
of indexed rungs, the cumulative suppression is the literal product. For the
real-valued anchors here, use the uniform signal-family continuation prescribed
in `foundations/cascade-suppression-formula.md` §1.2:

$$
P_{\text{survival}}(\Delta n)
:= \varphi^{-\Delta n},\qquad
\Delta n = n_{\text{QCD}} - n_{\text{GUT}} = 81.38.
$$

At integer $\Delta n$, this continuation equals
$\prod_{i=0}^{\Delta n-1}\varphi^{-1}$.

Applied to the CP-violating seed: $\bar{\theta} = \delta_{\text{CP}} \cdot
P_{\text{survival}}$. The cascade protection works the same way for CP as it
does for proton decay—just with a different seed (CKM phase vs. random
ambient noise) and a different cascade span (~81 rungs vs. 92 rungs).

---

## 3. No axion required

The Peccei-Quinn solution to the strong CP problem introduces a new global
U(1) symmetry and a new particle (the axion) to dynamically relax $\bar{\theta}$
to zero. In Cassi, $\bar{\theta}$ is **already zero** at the $\varphi$-attractor,
and the residual CP-violating contribution from CKM mixing is cascade-suppressed
to $\pi\varphi^{-83.4} \approx 1.2\times10^{-17}$. No new symmetry, no new particle, no new energy scale. The
cascade does what the axion was invented to do—and does it with zero
additional parameters.

---

## 4. Relation to other cascade phenomena

| Phenomenon | Seed | Cascade span | Suppression | Result |
|---|---|---|---|---|
| **Strong CP** ($\bar{\theta}$) | CKM phase $\delta_{\text{CP}}$ (Mapped) | GUT→QCD (~81 rungs) | $\varphi^{-81.4}$ | $\bar{\theta} \approx 1.2 \times 10^{-17}$ |
| Proton coherence budget | Hypothesized independent-step profile | Planck→proton ($N_p^{\mathrm{budget}}=91.46$) | $\varphi^{-4505.5758}$ | $\sim10^{942}$ modeled cycles; physical rate open |
| Hierarchy ($v_0/M_{\text{Pl}}$) | Gauge structure | Planck→EW (80 rungs) | $\varphi^{-80}$ (exact count) | $10^{-17}$ |
| Neutrino masses | Seesaw scale | GUT→ν (20 rungs) | $\varphi^{-20}$ | $m_\nu \sim 0.1$ eV |

The table contains two declared cascade maps. Strong CP, the hierarchy, and
neutrino examples use a linear $\varphi^{-N}$ signal-propagation map. The
proton coherence budget uses a quadratic product over included scale steps.
Every physical identification and any cycle-to-time conversion retain their
source-specific epistemic labels.

---

## 5. How this closes the strong CP problem

The strong CP problem exists because the Standard Model treats $\bar{\theta}$
as a free parameter—an angle that could have any value between $0$ and $2\pi$,
yet is observed to be $< 10^{-10}$. The Cassi framework treats $\bar{\theta}$
as a **derived** quantity: its value is fixed by the cascade position of the
CP-violating source (GUT scale) and the cascade depth to the QCD scale. The
angle is not free—it is as determined as the proton's mass or the weak
scale, and its smallness is the same $\varphi^{-N}$ scaling that explains all
other hierarchy problems in the framework.

**Epistemic status: Mapped** (span from Mapped anchors). $\bar{\theta}$ follows from cascade architecture
+ $\delta_{\text{CP}}$ + de-resonance damping, but both anchors are ledgered
fits: the GUT-seed rung (n = 13.33 for $M_{\text{GUT}} \approx 2\times10^{16}$
GeV, `parameter-inventory.md` §10 row 13) and $\delta_{\text{CP}} =
\pi\varphi^{-2}$ (§10 row 2). The predicted value ($1.2\times10^{-17}$)
sits ~7 orders below the bound and
is falsifiable if future neutron EDM probes measure below $10^{-10}$ and
find a nonzero $\bar{\theta}$ significantly larger than $10^{-17}$.

---

## 6. References

- `principles/de-resonance-principle.md`—$\varphi$ as maximally CP-conserving
- `foundations/proton-coherence-budget.md`—cascade suppression mechanism
- `standard-model/cp-violation.md`—$\delta_{\text{CP}} = \pi\varphi^{-2}$
- `open-questions-cassi-answers.md`—Q2 (strong CP, now Mapped)
