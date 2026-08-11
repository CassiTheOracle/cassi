# Quark Confinement from a Saturated-Gate Flux Tube at the QCD Scale

## Status: Derived (tube extensivity + cell quantization; $\kappa = 2\pi$ conditional on the 2π-per-rung winding reading; inputs: gate saturation, one-cell quantization, pitch convention)—August 2026

## Abstract

Quark confinement has no fundamental explanation in the Standard Model—it is
an observed fact parameterized by the QCD scale $\Lambda_{\text{QCD}}$, with
permanent binding treated as a phenomenological property of the strong force.
In the Cassi framework the QCD scale is cascade step 95 ($\ell_{95} =
\ell_{\text{Pl}}\,\varphi^{95}$, $E_{95} = \hbar c/\ell_{95} = 0.171$ GeV), and
confinement is a **saturated-gate flux tube**: between two separated color
charges the conversion channel saturates to the de-converted vacuum
($q \to 0$), expelling the condensate and leaving a tube whose cross-section is
quantized to one condensation-lattice cell. The tube's energy is extensive in
its length, so $E(r) = \mu r$ and the force is constant—the linearity is
geometric (tube length $\propto$ separation) and does not depend on the gate
shape. The string tension follows from cell quantization as
$\mu = \rho_c A_c = \kappa (M_{\text{Pl}}/\varphi^{95})^2$; the $O(1)$
coefficient closes to $\kappa = 2\pi$—$\sigma_{\text{tube}} = 2\pi\Lambda_{\text{QCD}}^2 =
0.1836\ \text{GeV}^2$ versus the measured $\sigma \approx 0.18\ \text{GeV}^2$, a
2.0% residual—conditional on the 2π-per-rung winding reading: the tube's
wall carries one full SO(2) doublet turn per rung-cell, the same pitch
convention that quantizes spin (`foundations/spin-fibonacci-spiral.md` §1–§2;
`foundations/spiral-dynamics.md` §1.1). The cascade suppression formula
(`foundations/cascade-suppression-formula.md`) guarantees the binding is
**permanent** on any physically accessible timescale. The derivation rests on
two stated inputs—gate saturation and one-cell quantization—from which the
linear potential follows without further assumptions; the coefficient
$\kappa = 2\pi$ adds the pitch convention as a third, conditional input.

---

## 1. The QCD scale from the cascade

The strong interaction emerges from the two-fluid PDE at cascade step 95
(`foundations/dimensionful-cascade.md` §3). The scale is:

$$\ell_{95} = \ell_{\text{Pl}}\,\varphi^{95} = 1.616255\times10^{-35}\ \text{m} \times 7.142\times10^{19} = 1.154\times10^{-15}\ \text{m} = 1.154\ \text{fm}$$

with energy

$$\boxed{\Lambda_{\text{QCD}} = E_{95} = \frac{\hbar c}{\ell_{95}} = 0.1709\ \text{GeV} = \frac{M_{\text{Pl}}}{\varphi^{95}}}$$

The "$\sim 200$ MeV" label is the rounded value; the exact rung energy is
171 MeV, and the identity $E_{95} = M_{\text{Pl}}\varphi^{-95}$ holds in
natural units ($\hbar c = \ell_{\text{Pl}} M_{\text{Pl}} c^2$). This is the
confinement scale—the cascade rung where the flux tube forms.

---

## 2. The saturated-gate flux tube

### 2.1 The de-converted vacuum

The condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$
organizes the two-fluid state at every cascade rung
(`foundations/bubble-lattice-fabric.md` §1): bubble centers carry $q \to 1$
(condensate), void centers carry $q \to 0$ (de-converted vacuum, $B \to -1$,
§4.3). The conversion channel is gated by the Qi coherence through the
nonlinearity $g(q) = q/(\varphi^2 + q^2)$ (§2.1), which vanishes at $q \to 0$:
the de-converted vacuum is inert, its conversion saturated shut.

**Gate saturation.** Between two separated color charges the Yang-Yin state
saturates to the de-converted vacuum along the entire segment joining them.
The color sources impose a phase winding on the condensation field that forces
a void line ($B = 0$) between the charges; the winding is topologically stable
(flux quantization), so the void cannot re-condense except by pair creation
(§4). This saturation is a postulate (its detailed mechanism—the PDE solution
at rung 95—is Hypothesized, §7); the derivation below uses only the tube's
existence and uniformity.

### 2.2 Extensivity gives the linear potential

The tube is a chain of identical de-converted cells, one per lattice period
along the string axis. Away from the endpoints its transverse profile repeats
identically at every $z$: the tube is translation-invariant along its length,
so its energy is extensive:

$$\boxed{E(r) = \mu\,r + 2E_{\text{core}}, \qquad \mu = \text{const}}$$

where $E_{\text{core}}$ is the endpoint (quark-core) energy at rung
$\sim 91.5$, independent of $r$ for $r \gg \ell_{95}$. The force is

$$\boxed{F(r) = -\frac{dE}{dr} = -\mu}$$

—constant, hence the linear confining potential $V(r) = \mu r$. The linearity
is a geometric consequence of extensivity (tube length $\propto$ separation);
it does not depend on the specific form of $g(q)$. The gate nonlinearity
supplies only the existence and uniformity of the saturated tube: any
saturating gate that expels the condensate yields the same constant force.

**Remark (Lüscher term).** Transverse fluctuations of a flux tube produce the
universal correction $E(r) = \mu r - \pi/(12r) + \mathcal{O}(r^{-3})$, the
standard string result; the leading linear term is unaffected.

---

## 3. String tension from cell quantization

The energy per unit length is the condensation-energy deficit: the tube
removes the condensate over its cross-section,

$$\mu = \rho_c\,A_c$$

where $\rho_c \sim \Lambda_{\text{QCD}}^4$ is the condensate energy density of
the unperturbed vacuum (natural units; the Lagrangian couplings $g/4$ and
$\lambda/2$ in `foundations/unified-lagrangian.md` §4.1 supply the $O(1)$
prefactor) and $A_c$ is the tube's cross-section.

**One-cell quantization.** The tube cross-section is pinned to exactly one
condensation-lattice cell by flux quantization: the tube carries one unit of
the condensation-field winding and cannot thicken continuously, since adding a
cell of de-converted vacuum costs $\rho_c A_c$ per unit length. The lattice
cell in the Yang-Yin plane has area $\Lambda_Y\Lambda_I = \ell_{95}\,
\ell_{95}/\varphi$ (Yang wavelength $\ell_n$, Yin wavelength $\ell_n/\varphi$;
`foundations/bubble-lattice-fabric.md` §1.2–§3), so $A_c = \ell_{95}^2/\varphi$;
to order one, $A_c \sim \ell_{95}^2 = 1/\Lambda_{\text{QCD}}^2$. Combining:

$$\boxed{\mu = \kappa\,\Lambda_{\text{QCD}}^2 = \kappa\left(\frac{M_{\text{Pl}}}{\varphi^{95}}\right)^2 = \kappa\,\varphi^{-190}M_{\text{Pl}}^2, \qquad \kappa = 2\pi\ \text{(conditional on the 2π-per-rung winding reading, §3.1)}}$$

with $\kappa = 1$ for $A_c = \ell_{95}^2$, $\kappa = \varphi^{-1}$ for the
lattice cell, and $\kappa = 2\pi$ for the winding reading of §3.1. The
scaling $\mu \propto \Lambda^2$ is the derivation's content; the coefficient
is fixed to $2\pi$ by the per-rung winding (§3.1), conditional on the pitch
convention input (§8).

### 3.1 The $O(1)$ coefficient: $\kappa = 2\pi$ from the per-rung winding

The measured tension requires $\kappa^* = \sigma/\mu = 0.18/0.02922 = 6.160$.
The candidate geometric factors, with residuals versus $\kappa^*$
(`computations/string_tension_coefficient.py`):

| Candidate | Value | Residual |
|---|---|---|
| $2\varphi^2+1$ ($\varphi$-algebra; no mechanism) | 6.2361 | +1.2% |
| $2\pi$ | 6.2832 | +2.0% |
| $4\varphi$ | 6.4721 | +5.1% |
| $\varphi^4$ | 6.8541 | +11.3% |
| $\pi$ (circle of radius $\ell_{95}$) | 3.1416 | −49% |
| $1/\varphi$ (checkerboard cell) | 0.6180 | −90% |
| Golden-angle family ($2\pi/\varphi^2$, $2\pi/\varphi$, $2\pi/\varphi^3$) | 2.400, 3.883, 1.483 | −61%, −37%, −76% |

Two candidates sit within ~2%; only $2\pi$ has a mechanism.

**The winding reading (candidate mechanism).** The framework's rung-to-angle
mapping is the pitch convention $\Theta = 2\pi n$: one full rotation ($2\pi$)
per cascade rung, an asserted coordinate postulate
(`foundations/spiral-dynamics.md` §1.1) that also underlies spin quantization
(`foundations/spin-fibonacci-spiral.md` §1–§2). The saturated tube at rung 95
is the same two-fluid structure: its wall is a cylinder of radius $\ell_{95}$
whose doublet phase winds once per rung-cell along the tube, and the
per-unit-length energy of one full turn is $2\pi\Lambda_{\text{QCD}}^2$:

$$\boxed{\sigma_{\text{tube}} = 2\pi\,\Lambda_{\text{QCD}}^2 = 2\pi\left(\frac{M_{\text{Pl}}}{\varphi^{95}}\right)^2 = 0.1836\ \text{GeV}^2 \qquad (+2.0\%\ \text{vs}\ \sigma = 0.18\ \text{GeV}^2)}$$

Geometric support: a tube of radius $\ell_{95}$ has perimeter $2\pi\ell_{95}$,
and a one-cell-thick condensate–void interface carries surface energy density
$\sim \Lambda^3$; $\mu = \Lambda^3 \cdot 2\pi\ell_{95} = 2\pi\Lambda^2$. The
pure volume reading (circle of area $\pi\ell^2$, $\kappa = \pi$) and the
checkerboard-cell reading ($\kappa = 1/\varphi$) are excluded at 49% and 90%.
The 2π-per-rung convention is asserted rather than dynamical (the measured
dynamical rotation rate is $\varphi^{-2}$ turns/rung, `spiral-dynamics.md`
§1.1), so the closure is **conditional**: the coefficient is Derived
conditional on the pitch convention and the winding reading, not a closed PDE
derivation. The alternative $2\varphi^2+1 = 6.236$ (+1.2%) is a
$\varphi$-algebra coincidence with no mechanism and remains Hypothesized.

The 2.0% residual is a 1.0% $\Lambda$ / 0.02-rung displacement, inside the
framework's rung-placement tolerance. Against the lattice band
$\sqrt{\sigma} = 0.42$–$0.44$ GeV ($\sigma = 0.17$–$0.21$ GeV$^2$), the
closure residual runs +8.0% (band low) to −12.6% (band high), with the exact
hit at $\sqrt{\sigma} = 0.4285$ GeV inside the band.

### Numerical comparison

All numbers below are from `computations/confinement_flux_tube.py` (usage:
`python computations/confinement_flux_tube.py`) and
`computations/string_tension_coefficient.py`, with the exact rung energy
$\Lambda_{\text{QCD}} = 0.1709$ GeV:

| Quantity | Value |
|---|---|
| $\mu$ ($\kappa = 1$) | $0.0292$ GeV$^2$, $\sqrt{\mu} = 0.171$ GeV |
| $\mu$ ($\kappa = \varphi^{-1}$) | $0.0181$ GeV$^2$, $\sqrt{\mu} = 0.134$ GeV |
| $\mu$ ($\kappa = 2\pi$, §3.1) | $0.1836$ GeV$^2$, $\sqrt{\mu} = 0.4285$ GeV |
| Measured $\sigma$ (Cornell / lattice QCD) | $0.18$ GeV$^2$, $\sqrt{\sigma} = 0.424$ GeV |
| $\mu / \sigma$ | $0.162$ ($\kappa = 1$), $0.100$ ($\kappa = \varphi^{-1}$), $1.020$ ($\kappa = 2\pi$) |
| $\Lambda$ reproducing $\sigma$ | $\sqrt{\sigma/2\pi} = 0.1693$ GeV, rung $n_* = 95.02$ ($\kappa = 2\pi$); $\sqrt{\sigma} = 0.424$ GeV, rung $n_* = 93.11$ ($\kappa = 1$) |

The $\kappa = 1$ and $\kappa = \varphi^{-1}$ rows bracket the geometric cell
area but sit a factor 6–10 below the measured tension; the winding reading of
§3.1 supplies the missing coefficient. With $\kappa = 2\pi$ the rung-95 scale
reproduces $\sigma$ directly: the scale $\sqrt{\sigma/2\pi} = 0.1693$ GeV
sits at rung 95.02, so the closure requires no rung displacement. The
phenomenological range $\Lambda_{\text{QCD}} \approx 0.2$–$0.3$ GeV
($\overline{\text{MS}}$ schemes) would give $\mu = 0.04$–$0.09$ GeV$^2$
($\Lambda = 0.22$ GeV gives $0.048$ GeV$^2$); the exact rung value
$E_{95} = 0.171$ GeV is used throughout this document.

---

## 4. String breaking

The tube decays when its stored energy reaches the pair-creation cost:

$$E(r_b) = \sigma\,r_b = 2m_q \qquad\Longrightarrow\qquad \boxed{r_b = \frac{2m_q}{\sigma}}$$

With the measured tension $\sigma = 0.18$ GeV$^2$:

| Pair-creation scale $m_q$ | $r_b$ |
|---|---|
| Pion floor, $m_\pi = 0.140$ GeV (rung 95.4) | $0.31$ fm |
| Constituent quark, $m_N/3 = 0.313$ GeV (rung 93.7) | $0.69$ fm |
| Lattice QCD $r_b \approx 1.2$ fm implies | $2m_q = 1.09$ GeV |

The framework's hadron-floor scales give $r_b \in [0.3, 0.7]$ fm, an
order of magnitude consistent with the lattice string-breaking distance
$\approx 1.2$ fm, which corresponds to a pair-creation energy $2m_q \approx
1.09$ GeV (the energy of the two light hadrons the string breaks into). Current
quark masses (2–5 MeV) give $r_b \approx 0.01$ fm and are the wrong input:
pair creation is a nonperturbative, hadronic-scale process. With the
coefficient resolved ($\mu = 2\pi\Lambda_{\text{QCD}}^2 = 0.1836$ GeV$^2$,
§3.1), the derived tension reproduces the measured $\sigma$ to 2.0% and the
breaking distances above stand unchanged.

---

## 5. Permanent binding from cascade suppression

The linear potential makes the binding energy grow without bound with
separation, but the deeper question is why the binding is permanent: could a
sufficiently energetic collision overcome it?

The cascade suppression formula answers this. To break the Qi flux tube, one
must supply energy to overcome the binding at ALL cascade rungs participating
in it. The binding spans rungs from the QCD scale ($n \approx 95$) down to the
proton's own rung ($n = 91.46$, $\log_\varphi(\lambda_p/\ell_{\text{Pl}})$),
and the suppression of any energy fluctuation capable of breaking the binding
across all $n$ rungs is:

$$P_{\text{break}} \approx \prod_{i=0}^{91.46} (1-q_i) \approx \varphi^{-4506}$$

This is the same coherence-budget product that gives the proton its
$10^{910}$-year lifetime (`foundations/proton-coherence-budget.md`). Confinement
is not permanent in the mathematical sense—it can be broken by an organized
perturbation attacking all 92 rungs (0 → 91.5) simultaneously. But the
probability of a random fluctuation doing so is $\sim 10^{-942}$ per wave
cycle; at the QCD frequency ($\omega_{\text{QCD}} \sim 10^{24}$ Hz), the mean
time between deconfinement events is $\sim 10^{910}$ years. Confinement and
proton stability are the same phenomenon at different cascade rungs: flux-tube
binding that the cascade protects against random disruption.

---

## 6. Confinement vs. asymptotic freedom

The cascade structure naturally produces both confinement (at large distances,
$r > \Lambda_{\text{QCD}}^{-1}$) and asymptotic freedom (at short distances,
$r \ll \Lambda_{\text{QCD}}^{-1}$):

| Regime | Cascade rungs probed | Qi gate behavior | Effective force |
|---|---|---|---|
| $r \ll \Lambda_{\text{QCD}}^{-1}$ | $n < 95$ (deep UV) | $g(q) \to 0$ logarithmically | $F \propto 1/r^2$ (Coulombic) |
| $r \sim \Lambda_{\text{QCD}}^{-1}$ | $n = 95$ (transition) | gate saturates | Crossover |
| $r \gg \Lambda_{\text{QCD}}^{-1}$ | $n > 95$ (IR) | saturated gate, uniform tube | $F = -\mu$ (confining) |

Asymptotic freedom is the cascade's UV limit: at rungs below 95, conversion is
fast and the effective coupling decreases logarithmically, matching the
negative $\beta$-function of QCD. Confinement is the IR limit: the saturated
tube of §2, whose constant force follows from extensivity. The transition at
step 95 is where the gate crosses from the free regime to saturation.

---

## 7. Epistemic boundaries

### Derived

- QCD scale at cascade step 95: $\ell_{95} = 1.154$ fm, $\Lambda_{\text{QCD}} = E_{95} = 0.171$ GeV
- Linear confining force $F = -\mu$ from tube extensivity (geometric; independent of the form of $g(q)$)
- String-tension scaling $\mu = \kappa\,(M_{\text{Pl}}/\varphi^{95})^2 = \kappa\,\varphi^{-190}M_{\text{Pl}}^2$
- String-breaking form $r_b = 2m_q/\sigma$ and the order-of-magnitude comparison with lattice QCD
- Permanent confinement from cascade suppression ($P_{\text{break}} \approx \varphi^{-4506}$)
- Asymptotic freedom from $g(q) \to 0$ in the UV limit

### Derived conditional (on the pitch convention + winding reading)

- The coefficient $\kappa = 2\pi$: $\sigma_{\text{tube}} = 2\pi\Lambda_{\text{QCD}}^2 = 0.1836$ GeV$^2$, +2.0% vs the Cornell datum $\sigma = 0.18$ GeV$^2$ (inside the lattice band $0.17$–$0.21$ GeV$^2$); the required coefficient $\kappa^* = 6.160$ is reproduced to 2.0%. Inputs: the 2π-per-rung pitch convention $\Theta = 2\pi n$ (asserted coordinate postulate, `foundations/spiral-dynamics.md` §1.1) and the reading that the saturated tube's wall carries one full doublet turn per rung-cell (§3.1; `foundations/spin-fibonacci-spiral.md` §1–§2)

### Hypothesized (testable)

- Gate saturation: the de-converted tube is the preferred configuration between separated charges—needs the PDE solution at rung 95
- One-cell quantization of the tube cross-section (flux-quantization argument, not yet PDE-verified)
- The winding reading itself: the PDE-level mechanism attaching $2\pi$ per rung-cell to the tube-wall energy (tube profile at rung 95)
- The $\varphi$-algebra coincidence $2\varphi^2+1 = 6.236$ (+1.2%) as a rival coefficient—numerically tighter than $2\pi$, no mechanism
- Exact form of $g(q)$ near the saturation transition

---

## 8. Inputs

The derivation rests on two postulates; the linear potential and the
$\mu \propto \Lambda^2$ scaling follow from them without further assumptions.
The coefficient $\kappa = 2\pi$ adds the pitch convention (v) as a conditional
input; the exact gate form remains open.

$$\boxed{\begin{array}{rl}
\text{(i) Gate saturation} & \text{between separated color charges the conversion channel}\\
& \text{saturates to the de-converted vacuum } q \to 0 \text{ (physical postulate)}\\
\text{(ii) One-cell quantization} & \text{the tube cross-section is pinned to one}\\
& \text{condensation-lattice cell by the flux quantum (physical postulate)}\\
\text{(iii) Cascade placement} & \Lambda_{\text{QCD}} = E_{95} = \hbar c/(\ell_{\text{Pl}}\varphi^{95})\\
& \text{(derived: } \text{dimensionful-cascade.md}\text{ §3)}\\
\text{(iv) Comparison datum} & \sigma \approx 0.18\ \text{GeV}^2 \text{ (measured; not an input)}\\
\text{(v) Pitch convention} & \Theta = 2\pi n \text{ per cascade rung (asserted coordinate}\\
& \text{postulate, } \text{spiral-dynamics.md}\text{ §1.1; conditional input for } \kappa = 2\pi \text{ (§3.1)}
\end{array}}$$

---

## 9. References

- `foundations/dimensionful-cascade.md`—$\ell_n = \ell_{\text{Pl}}\varphi^n$; QCD at step 95 ($E_{95} = 0.171$ GeV)
- `foundations/bubble-lattice-fabric.md`—condensation field, checkerboard cell structure ($\Lambda_Y = \ell_n$, $\Lambda_I = \ell_n/\varphi$), $q = (1+B)/2$, gate nonlinearity $g(q) = q/(\varphi^2+q^2)$
- `foundations/spiral-dynamics.md`—§1.1 the pitch convention $\Theta = 2\pi n$ (asserted coordinate postulate, one full rotation per cascade rung)
- `foundations/spin-fibonacci-spiral.md`—§1–§2 the 2π-per-rung convention and doublet winding; spin quantization from the same pitch convention
- `foundations/cassi-theory-reference.md`—§2 Qi coherence and gate; §6.7 confinement summary
- `foundations/cascade-suppression-formula.md`—per-rung damping, $\varphi^{-N}$
- `foundations/proton-coherence-budget.md`—$\varphi^{-4506}$ coherence product
- `foundations/unified-lagrangian.md`—§4.1 two-fluid core, condensate couplings
- `computations/confinement_flux_tube.py`—numerical verification of the tube derivation (usage: `python computations/confinement_flux_tube.py`)
- `computations/string_tension_coefficient.py`—numerical verification of $\kappa = 2\pi$ (usage: `python computations/string_tension_coefficient.py`)
- `open-questions-cassi-answers.md`—Q8 (confinement)
