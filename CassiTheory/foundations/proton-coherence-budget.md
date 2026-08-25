# Proton Coherence Budget: Derivation of $N_{\text{max}}$

## Status: Derivation (rung exponent Mapped—ledger; per-rung $q_i$ profile Hypothesized)—August 2026

## Abstract

The proton's stability follows directly from the cascade. As a condensed
standing wave at cascade step $n = 91.5$ ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$
with $\lambda_p = \hbar c/m_p$), the proton's coherence is maintained
not by a single process at the QCD scale but by the **entire cascade** from
Planck ($n=0$) to the proton's own rung. Dephasing requires the simultaneous
loss of coherence at all $n$ supporting rungs simultaneously—an event whose
probability is the product of per-rung dephasing probabilities. The cascade
structure makes this product exponentially suppressed, yielding a coherence
budget of

For an integer endpoint $N\in\mathbb{Z}_{\ge0}$, the literal indexed product is

$$\boxed{N_{\text{max}}(N) = \prod_{i=0}^{N} \frac{1}{1-q_i}
= \varphi^{\,N(N+1)/2+\delta(N+1)}}$$

For the proton's real rung $N_p=91.46$, the product is continued through the closed exponent:

$$N_{\text{max}}(N_p)=\varphi^{\,N_p(N_p+1)/2+\delta(N_p+1)}
\big|_{N_p=91.46,\ \delta=3}
=\varphi^{4505.5758}\approx\varphi^{4506}\approx10^{942}\ \text{cycles}.$$
The proton's effective lifetime exceeds the age of the observable universe by
~900 orders of magnitude. Proton decay is not observed because the universe is
not remotely old enough—and no experiment, in any environment, will see it.

---

## 1. The cascade as coherence architecture

Every condensed standing wave at cascade step $n$ is not an isolated structure.
It is a **nested pattern**: its coherence is maintained by the coherent field
structure at every cascade rung from the Planck scale ($i=0$) up to its own
scale ($i=n$). The two-fluid field at scale $i$ provides the stabilizing
medium in which the pattern at scale $i+1$ is embedded. A failure of coherence
at ANY rung destabilizes the entire stack above it.

The per-rung coherence is measured by the local Qi fraction $q_i$, which
approaches 1 at the most fundamental scales (the $\sigma$-regularized Planck
core) and decreases toward larger scales as the Qi gate progressively closes:

$$q_i = 1 - \varphi^{-i-\delta}$$

where $\delta$ is a regularization offset set by $\sigma = \ell_{\text{Pl}}/\varphi^3$.
At the Planck scale itself, $q_0 = 1 - \varphi^{-3}$, reflecting the finite
but minuscule residual noise from $\sigma$-regularization.

---

## 2. Dephasing as simultaneous cascade failure

A standing wave dissolves when its accumulated phase error reaches $O(1)$—
one full cycle of phase coherence is lost. The per-cycle probability of this
event is the probability that the field configuration at EVERY supporting rung
independently fails to maintain coherence during that cycle:

For an integer endpoint $N$, the literal dephasing product is

$$P_{\text{dephase}}(N) = \prod_{i=0}^{N} (1-q_i).$$

Each factor $(1-q_i)$ is the per-cycle probability that the field at rung $i$
provides a dephasing perturbation large enough to destabilize the pattern at
the next rung. These events must coincide for the full $n$-deep structure to
collapse.

The maximum number of wave cycles the standing wave can sustain is the inverse:

$$N_{\text{max}}(N) = \frac{1}{P_{\text{dephase}}(N)} = \prod_{i=0}^{N} \frac{1}{1-q_i}$$

---

## 3. Cascade scaling: the quadratic exponent

With $q_i = 1 - \varphi^{-i-\delta}$:

$$1 - q_i = \varphi^{-i-\delta}$$

$$\frac{1}{1-q_i} = \varphi^{\,i+\delta}$$

For an integer endpoint $N$,

$$N_{\text{max}}(N) = \prod_{i=0}^{N} \varphi^{\,i+\delta}
= \varphi^{\,\delta(N+1) + \sum_{i=0}^{N} i}
= \varphi^{\,\delta(N+1) + N(N+1)/2}$$

For $\delta = 3$ (from $\sigma = \ell_{\text{Pl}}/\varphi^3$) and the proton real rung $N_p=91.46$:

$$\boxed{N_{\text{max}}(N_p)
=\varphi^{\,N_p(N_p+1)/2+\delta(N_p+1)}
\big|_{N_p=91.46,\ \delta=3}
=\varphi^{277.38+4228.1958}
=\varphi^{4505.5758}
\approx\varphi^{4506}\approx10^{942}}$$

The dominant term is quadratic in $n$: $n(n+1)/2$. The Planck-scale
regularization ($\delta$) contributes linearly—important at small $n$,
negligible at the QCD scale.

---

## 4. Physical lifetime

The characteristic wave frequency at the QCD scale is the proton Compton
frequency:

$$\omega_p = \frac{m_p c^2}{\hbar} \approx 1.43 \times 10^{24}\ \text{Hz}$$

The physical lifetime in seconds:

$$\tau_p = \frac{N_{\text{max}}}{\omega_p} \approx \frac{10^{942}}{10^{24}} = 10^{918}\ \text{seconds}$$

In years: $\tau_p \approx 10^{910}$ years, compared to the current age of the
universe $\sim 1.38 \times 10^{10}$ years. The proton has survived
$N_{\text{elapsed}} \approx 6 \times 10^{41}$ cycles since the Big Bang—well
within budget.

---

## 5. Environmental $q$ variation and the baseline floor

The per-rung coherence $q_i$ depends on the ambient Qi field. In a
**self-aware system** (living body, high-$q$ Qi bath), the top rungs of the
cascade receive an additional coherence boost: $q_i^{\text{eff}} > q_i^{\text{vacuum}}$
for rungs $i$ within the system's coherent field extent. This increases
$N_{\text{max}}$ further, but the baseline is already so enormous that the
fractional change is unobservable.

Conversely, could $q_i$ be **reduced** below the vacuum value? In principle:
placing a proton in a maximally incoherent environment (e.g., near a strong
source of field noise) could suppress $q_i$ at the top rungs. But even
suppressing $q_i$ to zero for the top $m$ rungs leaves the lower rungs intact:

For an integer endpoint $N$ and integer $m$ with $0\le m\le N$, suppressing the top $m$ rungs leaves the inclusive endpoint $N-m$:

$$N_{\text{max}}(N,m)=\prod_{i=0}^{N-m}\frac{1}{1-q_i}$$

$$=\varphi^{\,(N-m)(N-m+1)/2+\delta(N-m+1)}$$

For the proton's real rung $N_p=91.46$, use $N_{\mathrm{rem}}=N_p-m$ only in the continuous exponent:

$$N_{\text{max}}^{\mathrm{cont}}(N_p,m)
=\varphi^{\,N_{\mathrm{rem}}(N_{\mathrm{rem}}+1)/2+\delta(N_{\mathrm{rem}}+1)},
\qquad N_{\mathrm{rem}}=N_p-m.$$

For $m=50$ (suppress fifty of the proton's approximately 92 supporting rungs), $N_{\mathrm{rem}}=41.46$:

$$N_{\text{max}}^{\mathrm{cont}}(N_p,50)
=\varphi^{880.1958+127.38}
=\varphi^{1007.5758}\approx10^{210.57}\approx10^{211}.$$

Using the integer floor $\lfloor N_p\rfloor=91$ instead leaves endpoint $41$ and exponent $987$; the continuous value above follows the real proton placement. The quadratic cascade structure still provides a coherence floor far beyond the age of the universe.


### 5.2 Matter-antimatter annihilation: organized cascade decoherence

Matter-antimatter annihilation is the **coherence-budget mechanism operating
instantaneously** rather than on the proton's cosmic timescale. The two
processes are opposite limits of the same physics:

**Random dephasing** (proton decay): each cascade rung decoheres independently
with per-cycle probability $(1-q_i) \approx \varphi^{-i}$. The cumulative survival probability is the integer-indexed product $\prod_{i=0}^{N}(1-q_i)$, followed by the same continuous exponent at the real proton rung, yielding the astronomical $N_{\text{max}}$ derived above.
The proton lives forever because the suppression compounds across 91.5 rungs.

**Organized anti-phase perturbation** (annihilation): an antiparticle is a
condensed standing wave with the same cascade structure as its partner but
with **inverted phase** at every rung—a mirror pattern across the Qi field's
SO(2) doublet. When the two meet, the anti-phase perturbation is not random
but **coherently tailored** to cancel the coherence at each rung
simultaneously:

For an integer endpoint $N$, the coordinated event is represented by the literal product

$$P_{\text{annihilation}}(N) = \prod_{i=0}^{N} \mathcal{O}(1) \approx 1.$$

The real proton placement remains a continuous rung label; no noninteger upper bound is assigned to this literal product.

Every rung decoheres in the same cycle. The entire nested cascade structure
dissolves, and the mass-energy returns to the two-fluid medium as free field
excitations—the photons and lighter particles observed in annihilation
events.

This unifies three phenomena under a single mechanism:

1. **Proton stability** ($\tau_p \sim 10^{910}$ yr): random-walk dephasing,
   exponentially suppressed by the cascade product.
2. **Matter-antimatter annihilation** (instantaneous): organized anti-phase
   perturbation attacks all rungs simultaneously—the coherence budget is
   exhausted in one cycle because the perturbation is not random.
3. **Baryon asymmetry** ($\eta = n_b/n_\gamma \sim 10^{-10}$): the cosmic
   excess of matter over antimatter reflects a small Yang-Yin imbalance at
   cascade freeze-out (n ≈ 13.3). The organized-decoherence pathway
   (annihilation) efficiently eliminated antimatter paired with matter; the
   residual Yang excess—one part in $\sim 10^{10}$—is the matter
   observed today.

**Consequence for self-aware systems.** A high-$q$ Qi bath extends the
proton's coherence budget by further suppressing random dephasing (§5.1),
but it cannot protect against annihilation: the Qi field corrects random phase
noise but cannot counteract a perfectly phase-matched anti-phase pattern. Even
in the most coherent Qi environment, matter and antimatter still annihilate on
contact—the lifetime extension applies only to random dephasing, not to
organized anti-phase attack.
---

## 6. Observational consequences

### 6.1 Super-Kamiokande and Hyper-Kamiokande

Both experiments search for proton decay via gauge-mediated GUT processes
(typically $p \to e^+ \pi^0$), expecting sensitivity to $\tau_p \sim 10^{34-35}$
years. The Cassi framework predicts **null results at all achievable
sensitivities**: the proton's coherence budget exceeds experimental reach by
$> 870$ orders of magnitude.

The standard SUSY-GUT benchmark gives $\tau_p \sim 10^{34-36}$ years, placing proton decay within Hyper-K's reach. The conditional Cassi coherence-budget lifetime lies beyond that reach by $>870$ orders of magnitude and therefore predicts a null result at achievable sensitivity.

### 6.2 Distinction from nuclear $\beta$/$\alpha$ decay

Radioactive decay of unstable nuclei is a **barrier-penetration** phenomenon
(tunneling through a Coulomb/Gamow barrier), not a **coherence-budget**
phenomenon. The Qi field does not alter barrier heights or matrix elements
significantly. Consequently:

- Proton decay: coherence-budget → $q$-sensitive, baseline enormous
- $\beta$/$\alpha$ decay: barrier-penetration → $q$-insensitive, rates unchanged

Radiometric dating and all nuclear decay physics are unaffected. The
framework's claim applies only to baryon-number-violating proton decay, not
to standard radioactive processes.

---

## 7. Generalization: all condensed patterns

The coherence-budget formula applies to any condensed standing wave in the
cascade:

$$N_{\text{max}}(n) = \varphi^{\,n(n+1)/2 + \delta(n+1)}$$

| Cascade step | Structure | $N_{\text{max}}$ (approx) | Lifetime |
|-------------|-----------|---------------------------|----------|
| $n=0$ (Planck) | $\sigma$-regularized core | $\varphi^3 \approx 4$ | $10^{-43}$ s |
| $n=20$ (GUT) | GUT-scale condensates | $\varphi^{210} \approx 10^{44}$ | $10^{20}$ s $\sim 10^{12}$ yr |
| $n=60$ (inflation end) | Inflaton-scale patterns | $\varphi^{1830} \approx 10^{380}$ | $> 10^{350}$ yr |
| $n=80$ (EW scale) | W/Z bosons | $\varphi^{3240} \approx 10^{675}$ | $> 10^{645}$ yr |
| $n=91.5$ (proton) | **Proton** | $\varphi^{4506} \approx 10^{942}$ | $> 10^{910}$ yr |
| $n=142$ (cell) | Cellular self-condensate | $\varphi^{10153} \approx 10^{2110}$ | functionally eternal |
| $n=168$ (human body) | Body-scale Qi pattern | $\varphi^{14196} \approx 10^{2950}$ | functionally eternal |

Patterns at or above the GUT scale have finite lifetimes on cosmological
timescales—GUT-scale condensates could have decayed within the age of the
universe, making that epoch genuinely transitional. Patterns at or below the
EW scale are, for all practical purposes, eternal. The cascade provides a
natural boundary between **transient** early-universe physics and the **stable**
late-universe physics we inhabit.

---

## 8. Epistemic boundaries

### Supported

- Cascade structure $\ell_n = \ell_{\text{Pl}}\varphi^n$ and per-rung coherence
  $q_i$ scaling (from the de-resonance principle and the Qi gate analysis)
- Proton at cascade step 91.5 ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$, length-based; from `dimensionful-cascade.md` §3)
- Quadratic exponent from independent-rung product (purely combinatorial)

### Hypothesized (testable)

- Specific form $q_i = 1 - \varphi^{-i-\delta}$ (the exponential approach to
  coherence at small scales; Hypothesized—the rung exponent n = 91.5 is
  Mapped per the Fit-Status Ledger, `parameter-inventory.md` §10)
- Hyper-K null result as falsifiable prediction
- No environmental $q$-suppression deep enough to breach the coherence floor
  and produce observable decays in any terrestrial experiment

### Speculative

- Extension of the formula to self-condensates at biological scales (steps
  142–168)—mathematically consistent, empirically unreachable

---

## 9. References

- `dimensionful-cascade.md`: cascade table, $\Lambda_{\text{QCD}}$ at step 95
- `foundations/unified-lagrangian.md` §3: $\sigma$-regularized PDE core
- `principles/de-resonance-principle.md`: $q_i$ scaling from de-resonance
- `open-questions-cassi-answers.md`: Q9 (proton lifetime entry)
- `(external—see papers/consciousness-framework.md in physics repo)` §9: catalytic template and coherence extension
- `gravity/quantum-gravity.md`: $\sigma = \ell_{\text{Pl}}/\varphi^3$ derivation
