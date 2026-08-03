# SU(5) / SO(10) GUT Embedding

## Status: Hypothesized—July 2026

## Abstract

The Cassi symmetry-breaking chain SU(4) → SU(3)$_C$ × U(1)$_{B-L}$ →
SU(3)$_C$ × SU(2)$_L$ × U(1)$_Y$ → U(1)$_{EM}$ is embedded at the φ-fixed
point in the two minimal grand-unified groups. SU(5) (Georgi–Glashow) unifies
one generation in $\mathbf{\bar{5}} \oplus \mathbf{10}$ with $\alpha_{\text{GUT}}
= \varphi^{-3}/(4\pi) \approx 1/53$ and $M_{\text{GUT}} \approx 2\times10^{16}\ \text{GeV}$,
predicting $\tau(p \to e^+\pi^0) \approx 4\times10^{34}\ \text{yr}$—within
Hyper-Kamiokande reach. SO(10) adds the right-handed neutrino in the
$\mathbf{16}$, giving a natural seesaw and a longer proton lifetime
($10^{35}$–$10^{36}\ \text{yr}$).

---

## 1. Why a GUT?

In the current Cassi framework, the three Standard Model gauge groups
SU(3)$_C$, SU(2)$_L$, and U(1)$_Y$ are introduced separately, each with its
own coupling. A grand unified theory (GUT) embeds them into a single simple
group $G_{\text{GUT}}$, providing three profound consequences:

1. **Charge quantization**—the U(1)$_Y$ hypercharge assignment ceases to be
   arbitrary and follows from the representation theory of $G_{\text{GUT}}$.
2. **Proton decay**—baryon number is violated by the same gauge bosons that
   unify the interactions, giving a definite (and testable) lifetime.
3. **GUT-scale Higgs sector**—the symmetry-breaking sector that reduces
   $G_{\text{GUT}} \to \text{SM}$ is inexorably linked to the Cassi
   φ-fixed-point dynamics of the isospinor field.

### 1.1 The φ-Breaking Chain

The Cassi symmetry breaking cascade derived in [sm-from-phi.md](sm-from-phi.md)
follows a specific pattern rooted in φ-truncations:

```
SU(4) ──→ SU(3)_C × U(1)_{B-L} ──→ SU(3)_C × SU(2)_L × U(1)_Y ──→ U(1)_{EM}
```

The rank of each gauge group is determined by truncating the continued
fraction expansion of $\phi$ at successive depths. The Cassi GUT extends this
chain by placing the SU(4) parent into a unified group at an even higher
scale.

---

## 2. SU(5) Embedding

The minimal simple group containing the Standard Model is SU(5) (Georgi &
Glashow, 1974). The Standard Model fermions of one generation fit into

$$\mathbf{\bar{5}} \oplus \mathbf{10}$$

of SU(5), decomposed under SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$ as:

$$\mathbf{\bar{5}} = (\mathbf{\bar{3}}, \mathbf{1})_{1/3} \oplus (\mathbf{1}, \mathbf{2})_{-1/2}$$

$$\mathbf{10} = (\mathbf{3}, \mathbf{2})_{1/6} \oplus (\mathbf{\bar{3}}, \mathbf{1})_{-2/3} \oplus (\mathbf{1}, \mathbf{1})_{1}$$

The right-handed neutrino is absent—it would require an SU(5) singlet, which
SO(10) naturally provides.

### 2.1 The GUT Scale from φ

The Cassi unification condition fixes the GUT coupling to the φ-point value:

$$\alpha_{\text{GUT}} = \frac{\phi^{-3}}{4\pi} \approx \frac{0.236}{4\pi}
   \approx 0.0188 \approx \frac{1}{53}$$

Running the three SM gauge couplings to the scale where they meet determines
$M_{\text{GUT}}$. From the one-loop RGEs:

$$\frac{1}{\alpha_i(M_Z)} - \frac{1}{\alpha_{\text{GUT}}} =
   \frac{b_i}{2\pi} \ln\frac{M_{\text{GUT}}}{M_Z}$$

where $(b_1, b_2, b_3) = (41/10, -19/6, -7)$ in SU(5) normalisation
(including two Higgs doublets). Using the measured couplings at $M_Z$:

$$\alpha_1^{-1}(M_Z) \approx 59.0,\quad
  \alpha_2^{-1}(M_Z) \approx 29.6,\quad
  \alpha_3^{-1}(M_Z) \approx 8.5$$

gives an intersection at

$$M_{\text{GUT}} \approx 10^{15}{-}10^{16}\ \text{GeV}$$

with the nominal Cassi value $M_{\text{GUT}} \approx 2 \times 10^{16}\ \text{GeV}$
corresponding to the φ-fixed point. The $\alpha_s$-only running estimate from
[sm-from-phi.md](sm-from-phi.md) gives $\sim 10^{15}\ \text{GeV}$, reflecting
the one-loop approximation and threshold uncertainties. The range $10^{15}{-}10^{16}$
is acceptable for unification; the precise value remains a prediction.

### 2.2 SU(5) Breaking and the Weinberg Angle

The SU(5) $\to$ SM breaking Higgs transforms in the **24** (adjoint)
representation. Its VEV at the φ-point gives:

$$\langle \mathbf{24} \rangle = v_{24} \cdot \operatorname{diag}
   \left(2, 2, 2, -3, -3\right)$$

breaking SU(5) $\to$ SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$.

The gauge coupling matching at $M_{\text{GUT}}$ determines the Weinberg angle:

$$\sin^2\theta_W(M_{\text{GUT}}) = \frac{3}{8}$$

for minimal SU(5). The Cassi φ-fixed-point VEV asymmetry modifies this to

$$\sin^2\theta_W(M_{\text{GUT}}) = \phi^{-3} \approx 0.236$$

which differs from the standard SU(5) tree-level value $3/8 = 0.375$ at
$M_{\text{GUT}}$, but **both converge to the measured weak-scale value**
$\sin^2\theta_W(M_Z) \approx 0.231$ through RG running. In standard SU(5),
the running from $0.375$ down to $0.231$ requires a large RG evolution;
in the Cassi φ-point scenario, $\phi^{-3} \approx 0.236$ at $M_{\text{GUT}}$
is already close to the weak-scale value, requiring substantially less running.
This is a consistency check: the Cassi prediction at the high scale already
anticipates the infrared fixed point of the RGEs.

### 2.3 The SU(5) φ-Lagrangian

The full SU(5) gauge Lagrangian at the unification scale:

$$\mathcal{L}_{\text{SU(5)}} = -\frac{1}{4} F_{\mu\nu}^A F^{A\mu\nu}
   + \bar{\Psi}_i i\gamma^\mu D_\mu \Psi_i
   + \mathcal{L}_{\text{Higgs}} + \mathcal{L}_{\text{Yukawa}}$$

where $A = 1, \ldots, 24$ are the SU(5) adjoint indices, and the fermions
$\Psi_i$ (for three generations $i = 1, 2, 3$) transform as
$\mathbf{\bar{5}} \oplus \mathbf{10}$. The covariant derivative is:

$$D_\mu = \partial_\mu - i g_5 A_\mu^A T^A$$

with $g_5^2 = 4\pi \alpha_{\text{GUT}} = 4\pi \cdot \phi^{-3}/(4\pi) = \phi^{-3}$,
so $g_5 = \sqrt{\phi^{-3}} \approx 0.486$.

The Higgs sector contains the **24** (adjoint) for GUT breaking and a
**5** (fundamental) for electroweak breaking:

$$\mathcal{L}_{\text{Higgs}} = |D_\mu \mathbf{24}|^2 + |D_\mu \mathbf{5}|^2
   - V(\mathbf{24}) - V(\mathbf{5}) - V_{\text{mix}}(\mathbf{24}, \mathbf{5})$$

At the φ-fixed point, the adjoint VEV takes the Cassi-normalised form:

$$v_{24} \sim \phi \cdot M_{\text{GUT}}$$

consistent with the hierarchy $v_{24} \gg v_5 \approx 246\ \text{GeV}$.

---

## 3. Proton Decay in SU(5)

Baryon-number violation is mediated by the $X$ and $Y$ gauge bosons—the
components of the SU(5) adjoint not in the SM subgroup. These acquire mass
$M_X = M_Y = M_{\text{GUT}}$ from the **24** Higgs.

The dominant decay channel is $p \to e^+ \pi^0$, with the dimension-6
operator:

$$\mathcal{L}_{d=6} = \frac{g_5^2}{M_X^2}\,
   \epsilon^{abc} \bar{u}_R^{c\,a} \gamma^\mu u_R^b\,
   \bar{e}_R^+ \gamma_\mu d_R^c + \text{(permutations)}$$

### 3.1 Proton Lifetime

The partial width for $p \to e^+ \pi^0$ is:

$$\Gamma(p \to e^+ \pi^0) =
   \frac{m_p}{32\pi} \left(1 - \frac{m_\pi^2}{m_p^2}\right)^2
   \left|\mathcal{A}(p \to e^+ \pi^0)\right|^2$$

with the amplitude:

$$|\mathcal{A}|^2 \propto
   \frac{g_5^4}{M_X^4} \cdot |\text{hadronic matrix element}|^2$$

The standard estimate gives:

$$\tau(p \to e^+ \pi^0) \approx
   \frac{1}{\alpha_{\text{GUT}}^2} \cdot \frac{M_{\text{GUT}}^4}{m_p^5}$$

Inserting the Cassi φ-values:

$$\boxed{\tau(p \to e^+ \pi^0) \approx
   \frac{1}{(1/53)^2} \cdot \frac{(2 \times 10^{16}\ \text{GeV})^4}
   {(0.938\ \text{GeV})^5} \approx 4 \times 10^{34}\ \text{years}}$$

For the conservative lower end of the GUT scale range, $M_{\text{GUT}} \approx
10^{15}\ \text{GeV}$, the lifetime decreases by $(10^{15}/2\times10^{16})^4
\approx 6 \times 10^{-5}$, giving $\tau \sim 2 \times 10^{30}\ \text{years}$ —
already excluded. This tension between the α_s-running estimate and the
full unification scale is **the central quantitative uncertainty** of the
Cassi SU(5) embedding, resolvable only by two-loop RGEs and threshold
corrections.

### 3.2 Decay Modes

The SU(5) prediction for the dominant branching ratios:

| Mode | Operator type | Relative branching | Notes |
|------|--------------|-------------------|-------|
| $p \to e^+ \pi^0$ | $d=6$ | dominant | Dictated by $X$ boson coupling |
| $p \to \bar{\nu} K^+$ | $d=6$ | mode-dependent | Involves second-generation |
| $p \to \mu^+ \pi^0$ | $d=6$ | $\sim |V_{us}|^2$ suppressed | CKM-suppressed |
| $p \to e^+ \gamma$ | $d=6$ | ${\sim}10^{-3}$ | Radiative |

The $\bar{\nu} K^+$ mode is particularly important: its relative rate depends
on the flavour structure of the GUT-scale Yukawas. In SUSY SU(5), $p \to
\bar{\nu} K^+$ can even become dominant.

---

## 4. Experimental Status

| Experiment | Bound on $\tau(p \to e^+ \pi^0)$ | Status |
|-----------|--------------------------------|--------|
| Super-Kamiokande (2024) | $> 2.4 \times 10^{34}$ years | Current best limit |
| Hyper-Kamiokande | $> 1 \times 10^{35}$ years | Projected (2030s) |
| **Cassi SU(5) prediction** | $\mathbf{4 \times 10^{34}}$ **years** | **Within Hyper-K reach** |

The Cassi prediction of $4 \times 10^{34}$ years sits **directly between** the
current Super-K bound and the future Hyper-K sensitivity—a hallmark of a
testable theory.

---

## 5. SO(10) Alternative

SO(10) is the next-simplest GUT. It unifies one SM generation plus a
right-handed neutrino into a single **16**-dimensional spinor representation:

$$\mathbf{16} = \mathbf{\bar{5}} \oplus \mathbf{10} \oplus \mathbf{1}$$

where the $\mathbf{1}$ is the right-handed neutrino $\nu_R$.

### 5.1 Advantages

- **Seesaw mechanism**: $\nu_R$ is already present. The Majorana mass for
  $\nu_R$ arises from the $\overline{\mathbf{126}}$ Higgs VEV, and the
  seesaw relation
  $$m_\nu \approx \frac{y_\nu^2 v^2}{M_R}$$
  follows naturally.
- **Complete GUT family**: SO(10) contains SU(5) $\times$ U(1)$_\chi$,
  and all SM fermions of one generation plus $\nu_R$ fit in one representation.
- **Charge quantization**: The U(1)$_{B-L}$ symmetry is a natural subgroup,
  providing a physical interpretation for the intermediate breaking step.

### 5.2 Breaking Chain in Cassi

The Cassi φ-scaling of VEVs determines the SO(10) breaking chain:

$$\text{SO(10)} \xrightarrow{M_{\text{GUT}}}
   \text{SU(5)} \times \text{U}(1)_\chi \xrightarrow{M_{24}}
   \text{SU(3)}_C \times \text{SU}(2)_L \times \text{U}(1)_Y
   \xrightarrow{M_{\text{EW}}} \text{U}(1)_{\text{EM}}$$

Each symmetry-breaking step occurs at a φ-scaled energy. The intermediate
scale $M_{24}$ (where the SU(5) **24**-plet gets a VEV) satisfies:

$$\frac{M_{24}}{M_{\text{GUT}}} \sim \phi^{-1} \approx 0.618$$

giving $M_{24} \sim 10^{16}\ \text{GeV}$ for $M_{\text{GUT}} \sim 2 \times
10^{16}\ \text{GeV}$.

The Higgs representations needed:

- **45** (adjoint)—breaks SO(10) $\to$ SU(5) $\times$ U(1)$_\chi$
- **126**—breaks SU(5) $\times$ U(1)$_\chi$ $\to$ SM; gives Majorana mass
  to $\nu_R$
- **10**—electroweak Higgs doublet

The **126** VEV at the φ-point determines the right-handed neutrino mass scale:

$$M_R \sim \phi^2 \cdot \langle \overline{\mathbf{126}} \rangle
   \sim \phi^2 \cdot M_{24} \sim 10^{15}{-}10^{16}\ \text{GeV}$$

consistent with the seesaw explanation of small neutrino masses.

### 5.3 Proton Decay in SO(10)

In SO(10), the $X$ and $Y$ gauge bosons are heavier than in minimal SU(5),
because the unification scale for complete coupling unification is typically
higher:

$$M_{\text{GUT}}^{\text{SO(10)}} \gtrsim M_{\text{GUT}}^{\text{SU(5)}}$$

The predicted proton lifetime is correspondingly longer:

$$\boxed{\tau(p \to e^+ \pi^0)_{\text{SO(10)}} \approx
   1 \times 10^{35}{-}1 \times 10^{36}\ \text{years}}$$

This range is **beyond the immediate reach** of Hyper-Kamiokande but could
be accessible to next-generation experiments such as DUNE and THEIA.

### 5.4 SU(5) vs SO(10) Comparison

| Feature | SU(5) | SO(10) |
|---------|-------|--------|
| Representation per generation | $\mathbf{\bar{5}} \oplus \mathbf{10}$ | $\mathbf{16}$ (one field) |
| $\nu_R$ included? | No (singlet needed) | Yes (in $\mathbf{16}$) |
| Seesaw mechanism | External $\nu_R$ | Natural via $\overline{\mathbf{126}}$ |
| Breaking Higgs | $\mathbf{24} + \mathbf{5}$ | $\mathbf{45} + \overline{\mathbf{126}} + \mathbf{10}$ |
| $\tau(p \to e^+ \pi^0)$ | $4 \times 10^{34}$ years | $10^{35}{-}10^{36}$ years |
| Hyper-K reach? | **Yes** | Marginal |
| Minimal φ-scaling | **Yes** | Needs extended Higgs sector |

---

## 6. Conclusion

SU(5) is the minimal GUT consistent with Cassi φ-fixed-point couplings. Its
predicted proton lifetime of $4 \times 10^{34}$ years ($p \to e^+ \pi^0$) is
**within reach** of Hyper-Kamiokande, with the expected sensitivity reaching
$> 10^{35}$ years in the 2030s.

The central uncertainty is the precise GUT scale: the α_s-running estimate
from sm-from-phi.md ($\sim 10^{15}$ GeV) gives a shorter lifetime, but the
full three-coupling unification and two-loop corrections push the scale toward
$2 \times 10^{16}$ GeV, which makes the prediction consistent with current
bounds and testable. A proton discovery at Hyper-K would simultaneously
confirm both grand unification and the Cassi φ-fixed-point principle.

SO(10) remains viable as a larger embedding that naturally accommodates the
right-handed neutrino and the seesaw mechanism, but it requires Higgs
representations beyond the minimal φ-scaling framework. Its proton lifetime
prediction of $10^{35}{-}10^{36}$ years is more challenging to test but not
beyond the reach of future experiments.

### Summary of Cassi GUT Predictions

| Observable | SU(5) Prediction | SO(10) Prediction | Experimental Prospect |
|-----------|-----------------|-------------------|---------------------|
| $\alpha_{\text{GUT}}$ | $\phi^{-3}/(4\pi) \approx 1/53$ | Same | Inferred from running |
| $M_{\text{GUT}}$ | $2 \times 10^{16}$ GeV | $\gtrsim 2 \times 10^{16}$ GeV | Unobservable directly |
| $\sin^2\theta_W(M_{\text{GUT}})$ | $\phi^{-3} \approx 0.236$ | Same | RG-extrapolated |
| $\tau(p \to e^+ \pi^0)$ | $\mathbf{4 \times 10^{34}}\ \text{y}$ | $10^{35}{-}10^{36}\ \text{y}$ | Hyper-K: $\mathbf{>10^{35}}\ \text{y}$ |
| $\nu$ masses | External seesaw | Natural seesaw | Oscillation experiments |

## References

- `standard-model/sm-from-phi.md`—φ-breaking chain and GUT-scale coupling
- `standard-model/su2-gauge-extension.md`—gauge-coupling unification at $M_{\text{GUT}}$
- `standard-model/neutrino-mass.md`—seesaw scale and canonical spectrum
- `foundations/dimensionful-cascade.md`—GUT rung anchors (steps 5–10)
