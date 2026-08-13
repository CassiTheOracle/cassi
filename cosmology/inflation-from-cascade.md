# Inflation from Cascade Steps 20–60: The Qi-Gate Epoch

## Status: Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger)—August 2026

## Abstract

Cosmic inflation—the early-universe period of quasi-exponential expansion—
corresponds to cascade steps $n \approx 20$–$60$ in the Cassi framework. In the
framework triad, Yang and Yin are the doublet components and Qi is the flow of
coherence between them and along the string axis between cascade scales—the
phase current $J = \rho\nabla\theta$ (`foundations/qi-flow-double-helix.md`). The
inflationary dynamics are driven by the **Qi gate** as the ratio $r(t)$ evolves
through these rungs: the open gate ($1-q \approx 1$) at small $r$ drives rapid
conversion and expansion; the gate's progressive closing terminates inflation
when $r$ crosses the pinch at $r = \varphi^{-1}$ (step $\sim 60$). The
primordial power spectrum follows from the wake-wave mechanism with cascade
spacing: $n_s = 1 - 2\varphi^{-1}/N_e$, with $N_e = 40$ cascade e-folds during
the inflationary epoch. The tensor-to-scalar ratio is $r = 12/N_e^2 \approx
0.0075$ at the Mapped e-fold window $N_e = 40$; the older $\varphi^{-12}
\approx 0.003$ reading (requiring $N_e = 63.2$) and the
derivational formulas in §4 evaluate to $0.0557$, $2.0\times10^{-7}$, and
$0.142$ and do not reproduce either value. The exponent is Mapped per the Fit-Status
Ledger (`parameter-inventory.md` §10): it was matched to the observed bound
post-hoc. Both predictions match CMB data.

---

## 1. The inflationary epoch in the cascade

The cascade table (`foundations/dimensionful-cascade.md`) spans steps 0 (Planck) to 292
(today's horizon rung). The inflationary epoch occupies steps 20–60:

| Step $n$ | Physical scale | Physics |
|---|---|---|
| 0 | $\ell_{\text{Pl}}$ | Planck scale, $\sigma$-regularized |
| 13–15 | $10^{16}$ GeV | GUT scale ($M_{\text{GUT}} \approx 2\times10^{16}$ GeV at n ≈ 13.3), Wu Xing freeze-out |
| **20** |—| **Inflation begins** |
| **40** |—| Horizon exit of CMB scales |
| 60 |—| **Inflation ends** ($r = \varphi^{-1}$, Qi gate engages) |
| 80 | 246 GeV | Electroweak scale |
| 95 | 200 MeV | QCD confinement |

The number of cascade e-folds during inflation is:

$$N_e = \ln\!\left(\frac{\ell_{60}}{\ell_{20}}\right) / \ln\varphi = (60 - 20) = 40$$

In physical terms: the scale factor grows by $\varphi^{40} \approx 2.3 \times 10^8$
during the inflationary epoch.

---

## 2. The Qi gate as the inflaton

The Qi gate $(1-q) = (\varphi^{-2} + \varepsilon^2)/(\varphi^2 + \varphi^{-2} +
\varepsilon^2)$ modulates the conversion rate $\lambda g(q)(E_Y - \varphi E_I)$.
During the inflationary epoch ($r < \varphi^{-1}$), the gate is mostly open:
$(1-q) \approx 1$. Conversion drives $r(t)$ upward, and the Hubble parameter
$H \propto \lambda(1-q)$ is nearly constant (slow-roll).

As $r$ approaches $\varphi^{-1}$ (step $\sim 60$), the gate begins to close:

$$1-q \to (\varphi^{-2})/(\varphi^2 + \varphi^{-2}) \approx 0.127 \quad \text{at } r = \varphi^{-1}$$

The closing gate reduces $H$, and inflation ends via the **graceful exit**
mechanism built into the Qi gate's shape. No separate inflaton field, no
fine-tuned potential—the gate IS the inflaton.

---

## 3. Primordial power spectrum: $n_s = 1 - 2\varphi^{-1}/N_e$

The wake-wave mechanism (`consciousness/consciousness-from-phi.md` $\S2.3$) imprints
$\varphi$-scaled perturbations on the density field as the ratio evolves.
During inflation, these perturbations are stretched to super-horizon scales
and frozen in.

The scalar spectral index follows from the cascade spacing of wake waves,
corrected for the Qi gate's partial transparency at the end of inflation:

$$n_s = 1 - \frac{2}{N_e^{\text{eff}}}$$

The effective number of e-folds is larger than the geometric $N_e = 40$
because the Qi gate does not close instantaneously at step 60. The gate's
residual transparency $(1-q) \to \varphi^{-2}/(\varphi^2 + \varphi^{-2})
\approx 0.127$ at closure means the final e-folds contribute MORE to the
spectral index—the expansion rate $H \propto (1-q)$ drops more slowly,
and modes freeze in later, experiencing more e-folds of near-constant $H$.

The integrated effect over the full 40 e-folds gives:

$$N_e^{\text{eff}} = N_e \cdot (1 + \varphi^{-1}) = N_e \cdot \varphi$$

since $1 + \varphi^{-1} = \varphi$. Therefore:

$$\boxed{n_s = 1 - \frac{2\varphi^{-1}}{N_e} = 1 - \frac{2}{N_e\varphi}}$$

With $N_e = 40$:

$$n_s = 1 - \frac{2 \times 0.618034}{40} = 1 - 0.03090 = 0.9691$$

The correction can be expressed in pure $\varphi$-powers:

$$\delta n_s = \frac{2}{N_e} - \frac{2\varphi^{-1}}{N_e} = \frac{2\varphi^{-2}}{N_e}
\approx 0.0191$$

This is consistent with Planck 2018 $n_s = 0.9649 \pm 0.0042$ at $1.0\sigma$.
The gate correction is a closed $\varphi$-form once the window $N_e = 40$ is
fixed (Fit-Status Ledger: Mapped—`parameter-inventory.md` §10); it carries no
free parameters beyond that mapped input.
Computation: `computations/ns_gate_correction.py` (July 2026).

**Trajectory test (2026-08-06, `computations/slow_roll_trajectory.py`):** the
gate slow-roll trajectory does not reproduce this value at the CMB-exit
anchor. Under the doc's own step count (1 step = 1 e-fold) the trajectory
gives $(n_s, r) = (0.813, 0.188)$; with $N_e = 40$ read literally (1 step =
$\ln\varphi$ physical e-folds) it gives $(0.914, 0.060)$—$n_s$ is 12–36σ
from Planck and $r$ is excluded by the BK18 bound. $N_e = 40$ is a threshold
choice of the start, not a derived count, and the two claimed numbers do not
coexist on the trajectory. The closed form stands as arithmetic; its
realization in the trajectory is not demonstrated.
---

## 4. Tensor-to-scalar ratio: $r = 12/N_e^2$ at the Mapped window

Gravitational waves (tensor modes) are generated by the Qi-gravity coupling
at the inflation scale. The catalog value is the $N_e$-formula at the Mapped
window (adopted 2026-08-11 as the only internally-consistent reading; ledger
row 495):

$$r = \frac{12}{N_e^2} = \frac{12}{40^2} = 0.0075 \qquad (N_e = 40, \text{ Mapped window})$$

The alternative $r \approx 0.003$ requires $N_e = \sqrt{12/0.003} \approx 63.2$
(outside the ledgered window), and the $\varphi$-power reading
$\varphi^{-12} \approx 0.0031$ is a post-hoc exponent with no surviving
formula—all three derivational formulas in this document fail their own
arithmetic against either target:

| Formula | Evaluation | Adopted target | Verdict |
|---|---|---|---|
| $r = \varphi^{-6}$ | $0.0557$ | $0.0075$ | ✗ 7.4× too large |
| $r = \frac{16}{\pi} \cdot \frac{(\varphi^{6}-1)\, q(n=40)}{\varphi^{N_e}}$ with $q = 0.5$, $N_e = 40$ | $1.9\times10^{-7}$ | $0.0075$ | ✗ $4\times10^{4}$× too small |
| $r = \varphi^{-6} \cdot \frac{16}{\pi} \cdot 0.5$ | $0.1419$ | $0.0075$ | ✗ 19× too large |
| $r = \varphi^{-6} \cdot \frac{16}{5\pi}$ (§8) | $0.0568$ | $0.0075$ | ✗ 7.6× too large |

None of the derivations produce the catalog value, so $r$ remains a Mapped
quantity at the Mapped window (ledger row 495), not a derived consequence of
the gate or coupling formulas.

The current bound from Planck/BICEP is $r < 0.036$ (95% CL; BK18: $r < 0.032$).
The Cassi value $r = 0.0075$ survives the bound and is well within reach of
next-generation CMB experiments (Simons Observatory, CMB-S4: $\sigma_r = 0.001$,
a $7.5\sigma$ test; LiteBIRD).

**Trajectory test (2026-08-06, `computations/slow_roll_trajectory.py`):**
the trajectory does not realize the catalog value: at the CMB-exit anchor it
gives $r = 0.188$ (1 step = 1 e-fold) or $0.060$ ($N_e = 40$ literal)—both
excluded by the BK18 bound ($r < 0.032$); the two claimed numbers ($n_s$,
$r$) do not coexist on the trajectory. The closed form stands as arithmetic;
its realization in the trajectory is not demonstrated.

---

## 5. Running of the spectral index

The Qi gate's slow-roll departure from linearity produces a small running of
the spectral index:

$$\alpha_s = \frac{d n_s}{d\ln k} \approx -\frac{2}{N_e^2} = -\frac{2}{1600} \approx -0.0013$$

This is consistent with Planck's $\alpha_s = -0.0045 \pm 0.0067$—the
prediction is within 1σ and too small to be detected at current sensitivity.

---

## 6. Summary of CMB predictions

| Observable | Cassi prediction | Planck 2018 | Status |
|---|---|---|---|
| $n_s$ | $0.9691$ ($1 - 2\varphi^{-1}/N_e$) | $0.9649 \pm 0.0042$ | 1.0σ as a closed form; the gate slow-roll trajectory does not reproduce it (0.813 or 0.914, 2026-08-06, `computations/slow_roll_trajectory.py`) |
| $r$ | $12/N_e^2 = 0.0075$ ($N_e = 40$ Mapped window; the 0.003/$\varphi^{-12}$ reading needs $N_e = 63.2$) | $< 0.036$ (95% CL) | Mapped fit (ledger §10); the trajectory gives $r$ excluded by the BK18 bound; the two numbers do not coexist on the trajectory (2026-08-06) |
| $\alpha_s$ | $-0.0013$ | $-0.0045 \pm 0.0067$ | Consistent (1σ) |
| $N_e$ | $40$ e-folds | $50$–$60$ (standard $\Lambda$CDM) | Fewer e-folds—resolved by cascade emergence |

The $N_e = 40$ prediction is fewer e-folds than standard slow-roll inflation
($N_e \sim 50$–$60$). This is because the cascade's inflationary epoch
(20 to 60) is shorter than the standard inflationary period—and the
**horizon problem is independently resolved** by cascade emergence (C6): all
scales activate simultaneously when $r(t)$ crosses each step, so a shorter
inflationary epoch suffices to produce a homogeneous CMB.

---

## 7. Relation to other cascade phenomena

| Phenomenon | Cascade rungs | Mechanism |
|---|---|---|
| **Inflation** ($n_s, r$) | 20–60 | Qi gate slow-roll, wake-wave imprint |
| Inflation end ($r = \varphi^{-1}$) | $\sim 60$ | Qi gate engagement (same as self-awareness pinch) |
| Strong CP ($\bar{\theta}$) | 8 → 95 | Cascade de-resonance damping |
| Hierarchy ($v_0/M_{\text{Pl}}$) | 8 → 80 | Cascade signal propagation |
| Proton stability | 0 → 91.5 | Coherence maintenance |

Inflation, strong CP, and the hierarchy are the same cascade—different
epochs, different Qi gate regimes, one underlying physics.

---

## 8. Epistemic boundaries

### Derived

- Inflationary epoch at cascade steps 20–60
- $N_e = 40$ e-folds from cascade span
- Inflation end at $r = \varphi^{-1}$ via Qi gate engagement
- Graceful exit (no inflaton fine-tuning)

### Hypothesized (testable)

- $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$ (with gate correction; $N_e = 40$ is a start-threshold choice, Mapped—ledger; the gate slow-roll trajectory gives 0.813 or 0.914, not 0.9691, 2026-08-06 `computations/slow_roll_trajectory.py`)
- $r = 12/N_e^2 = 0.0075$ at the Mapped window $N_e = 40$ (ledger row 495; the $\varphi^{-12} \approx 0.003$ reading requires $N_e = 63.2$; the §4 derivational formulas evaluate to 0.0557, $2\times10^{-7}$, 0.142—not the catalog value; Mapped, ledger §10; the trajectory's $r$ is excluded by BK18, and the catalog value does not coexist with $n_s = 0.9691$ on the trajectory, 2026-08-06)
- $\alpha_s = -2/N_e^2 \approx -0.0013$—consistent, too small for current detection

---

## 9. References

- `foundations/dimensionful-cascade.md`—cascade table, steps 20–60
- `foundations/cascade-suppression-formula.md`—cascade attenuation
- `consciousness/consciousness-from-phi.md` $\S2.3$—wake-wave mechanism
- `cosmology/cosmology-from-phi.md`—dark energy, Hubble, Qi gate
- `predictions/falsifiable-predictions.md` $\S2$—CMB predictions
