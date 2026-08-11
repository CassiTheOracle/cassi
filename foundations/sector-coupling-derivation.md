# The Sector-Coupling Scale: $\kappa_s = \varphi^{-6}/v_0^2$

## Status: Derived conditional on δ = 3 (rung identity; coupling form as documented), coefficient Hypothesized (v₀ input Calibrated, N_pde normalization Mapped—ledger)—August 2026

## Abstract

The Dirac↔two-fluid sector coupling—the parameter behind the chemotactic mobility $\chi$, marked free in `parameter-inventory.md` §3.3—gets its scale derived from the cascade: the rung identity $\kappa_s = \varphi^{-6}/v_0^2 = M_{\text{Pl}}^{-2}\varphi^{154}$ places its mass scale $M_s = \kappa_s^{-1/2}$ at rung $77 = 154/2$, three $\varphi$-rungs above the electroweak VEV (rung 77 ≈ 1.04 TeV). The offset $\delta = 3$ is the same 3-rung offset as the gravity regulator $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`gravity/quantum-gravity.md` §2.1), so the placement is **derived conditional on $\delta = 3$**. The O(1) coefficient and the exact bridge to $\chi$ remain open, with candidate readings and a computable check identified.

## 1. The sector coupling and its symbol

The Dirac↔two-fluid sector coupling is the term that enforces the Yang/Yin dictionary between Dirac chiral densities and two-fluid condensate squares, and $\kappa_s$ sets its equilibration timescale; the term originates in `foundations/unified-lagrangian.md` §5.2.

$$
\boxed{\mathcal{L}_{D\to TF} = \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)^2}
$$

with $P_{\pm} = (1\pm\gamma^5)/2$ the chiral projectors: the plus term ties the right-handed density to the Yang condensate square $\Psi_0^2$, the minus term ties the left-handed density to the Yin condensate square $\Psi_1^2$. The coupling $\kappa_s$ sets the timescale for equilibration between the sectors.

### The symbol

The symbol $\kappa$ is shared with two other established constants. The Wu Xing pentagram transmission $\kappa = \varphi^{-1} = K_{fw}$ ("Water damps Fire", the control-cycle coefficient fixed by the pentagon side/diagonal ratio) is a different, derived constant documented in `foundations/wu-xing-cycle-structure.md` §1.3, and a charge-density constant appears as $\kappa$ in the Qi charge/current definitions of `predictions/cassi_definitions.md` ($\rho = -\kappa\nabla^2 q$, $J = \kappa\,\partial_t\nabla q$). This document uses $\kappa_s$ (s = sector) for the Dirac↔two-fluid coupling, and the rename is applied repo-wide.

### Dimensions

$\kappa_s$ has mass dimension $-2$—a soft constraint (an effective four-fermion-like coupling), not a renormalizable interaction. The term mixes a $[M]^3$ spinor density with a $[M]^2$ condensate square, so $\kappa_s$ is the stiffness of a dictionary, not a fundamental vertex: it measures how strongly the two sectors are pinned to a common Yang/Yin decomposition.

## 2. The scale: three rungs above electroweak

The sector-coupling scale is not free—it sits exactly three cascade rungs above the electroweak VEV, which fixes $\kappa_s$ to one part in $\xi = \varphi^6$ per $v_0^2$.

### The cascade tool

Energy rungs follow the cascade ladder `foundations/dimensionful-cascade.md` §2,

$$
E_n = M_{\text{Pl}}\cdot\varphi^{-n},
$$

with $M_{\text{Pl}} = 1.2209\times10^{19}$ GeV. Each step down in $n$ multiplies the scale by $\varphi$.

### The electroweak anchor

The VEV $v_0 = 246$ GeV sits at $n = 79.89 \approx 80$: rung 80 is $E_{80} = M_{\text{Pl}}\varphi^{-80} = 233.2$ GeV, a $-5.22\%$ offset from $v_0$, the same discretization-residual class documented as the "5.3% gap" in `foundations/deriving-remaining-gaps.md` §3.3 ($\delta n = 0.11$ steps, a soft boundary between cascade regimes). The sector coupling inherits this placement.

### Three rungs up: rung 77

The sector-coupling scale sits three rungs above the electroweak rung:

$$
E_{77} = M_{\text{Pl}}\cdot\varphi^{-77} = 987.7\ \text{GeV}.
$$

The round 1 TeV is $+1.24\%$ off this rung ($\log_\varphi(M_{\text{Pl}}/1\,\text{TeV}) = 76.97$).

### The rung identity: why 77

The placement is not an independent "three rungs up" assertion—it follows from the exponent arithmetic of $\kappa_s = \varphi^{-6}/v_0^2$ itself. The VEV sits at rung 80,

$$
v_0 = M_{\text{Pl}}\,\varphi^{-80} \quad (\text{rung } 80),
$$

and squaring doubles the rung index ($80 \to 2\cdot 80 = 160$):

$$
v_0^2 = M_{\text{Pl}}^2\,\varphi^{-160}.
$$

Inserting into $\kappa_s$,

$$
\kappa_s = \frac{\varphi^{-6}}{v_0^2}
        = \varphi^{-6}\,M_{\text{Pl}}^{-2}\,\varphi^{160}
        = M_{\text{Pl}}^{-2}\,\varphi^{154}.
$$

The $\varphi$-exponent of $\kappa_s$ relative to the $M_{\text{Pl}}^{-2}$ base is $+154$—not the naive $-160 - 6 = -166$, because $v_0^2$ carries the dimensionful base $M_{\text{Pl}}^2$ and the $\varphi^{-6}$ stands in the numerator. The associated mass scale

$$
M_s = \kappa_s^{-1/2} = M_{\text{Pl}}\,\varphi^{-154/2} = M_{\text{Pl}}\,\varphi^{-77}
$$

sits at rung $77 = 154/2$: halving the exponent inverts the squaring. Equivalently, $M_s = \varphi^3 v_0$: multiplying the VEV by $\varphi^3$ climbs three rungs ($E_{n-3} = E_n\,\varphi^3$), so $n(M_s) = n(v_0) - 3 = 80 - 3 = 77$.

**The offset is $\delta = 3$—the same $\delta$ as the gravity regulator.** Write the placement as

$$
\boxed{\delta = n_{v_0} - n_{\kappa_s} = 80 - 77 = 3}
$$

with $n_{\kappa_s}$ the rung of $M_s = \kappa_s^{-1/2}$. This is the same 3-rung offset as $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`gravity/quantum-gravity.md` §2.1), where $\delta = 3 = d$ is derived conditional on the three-dimensional phase-resolution postulate. **The rung-77 placement is therefore derived conditional on $\delta = 3$**: with the shared offset $\delta$ the coupling takes the form $\kappa_s = \varphi^{-2\delta}/v_0^2$ at rung $80 - \delta$, and $\delta = 3$ is inherited from the $\sigma$-derivation, not derived here. The reverse cross-check appears in `gravity/quantum-gravity.md` §2.1 (ii).

The rung identity is exact in the exponent arithmetic ($154/2 = 77$). The *physical* scale $M_s = \varphi^3 v_0 = 1042.07$ GeV inherits the VEV's discretization residual, sitting $\delta n = 0.11$ steps below rung 77 ($+5.50\%$ above $E_{77}$)—the same residual class as the EW anchor itself. All values verified in `computations/kappa_s_rung_identity.py`.

### The VEV-anchored form

Equivalently, the scale is $\varphi^3$ times the electroweak VEV:

$$
\boxed{M_s = \kappa_s^{-1/2} \approx \varphi^3 v_0 \approx 1.04\ \text{TeV}}
$$

with $\varphi^3 = 4.23607$, giving $\varphi^3 v_0 = 1042.07$ GeV—$+5.50\%$ off rung 77, the same discretization-residual class as the EW anchor itself. Inverting,

$$
\boxed{\kappa_s = \frac{\varphi^{-6}}{v_0^2} = \frac{1}{\xi\, v_0^2} = 9.21\times10^{-7}\ \text{GeV}^{-2} = 0.92\ \text{TeV}^{-2}}
$$

where $\xi = \varphi^6 = 17.94427191$ is the Qi-gravity coupling.

### Observation, not mechanism

The suppression $\kappa_s \propto \varphi^{-6}$ is the reciprocal of the Qi-gravity enhancement $\xi = \varphi^6$ at the electroweak anchor (`foundations/unified-lagrangian.md` §5.1). This reciprocity is an observation about the arithmetic, not a claimed mechanism; the mechanism that sets the coefficient is the open fork of §3.

### A dark step answered

Rung 77 is a "dark step"—a rung the activated set $\{1,2,3,5,6,26,80,292\}$ leaves unlabeled. `foundations/dimensionful-cascade.md` §9 Q2 asks whether dark steps carry physical meaning (sterile neutrino masses, dark sector couplings). This derivation answers Q2 for rung 77: it is the Dirac↔two-fluid equilibration scale.

### Consistency with the inventory

`parameter-inventory.md` §3.3's slogan "$\kappa \sim 1/\text{TeV}^2$" is now pinned to a specific value, $\kappa_s = 0.92$ TeV$^{-2}$—same order of magnitude as the inventory's estimate, derived rather than assumed.

## 3. The O(1) coefficient: candidate readings

The scale is derived, but the O(1) coefficient in front of $\varphi^{-6}/v_0^2$ is set by the equilibration mechanism, which is not yet specified.

Write $\kappa_s = C\cdot\varphi^{-6}/v_0^2$ with $C$ an O(1) coefficient. The candidate readings:

| $C$ | Reading | $\kappa_s$ | $M_s = \kappa_s^{-1/2}$ |
|-----|---------|------------|--------------------------|
| $1$ | Pure $\xi^{-1}$ | 0.921 TeV$^{-2}$ | 1.042 TeV |
| $\varphi^{-1} = K_{fw}$ | One pentagram transmission | 0.569 TeV$^{-2}$ | 1.326 TeV |
| $\varphi^{-2}$ | Two transmissions | 0.352 TeV$^{-2}$ | 1.686 TeV |

All three sit inside the "$\sim 1/\text{TeV}^2$" band, so the inventory's order-of-magnitude slogan cannot discriminate between them.

The framework provides two precedents for how such a coefficient should be read. First, the conversion rate $\lambda = 1/(2w) = 1/10$ is deliberately rational, *not* a $\varphi$-power, precisely to avoid phase-locking with cascade rungs (`foundations/dimensionful-constants-status.md` §2.1)—so $C = 1$ is not required to be a $\varphi$-power, and the mechanism may well produce a rational coefficient. Second, the de-resonance posture (`principles/de-resonance-principle.md` §6): the $\varphi$-attractor sets leading-order baselines and dynamics supply subleading corrections, so the coefficient is exactly the kind of quantity the attractor leaves free.

Conclusion: the scale is derived (conditional on $\delta = 3$; §2); the coefficient is an open fork with identifiable readings. Tier of the scale: **Derived conditional on $\delta = 3$ (rung identity; coupling form as documented)**; tier of the coefficient: **Hypothesized**.

## 4. The bridge to $\chi$: repaired

The inventory's bridge from $\kappa_s$ to the chemotactic mobility $\chi$ is dimensionally broken as written; the repaired bridge introduces one computable normalization factor.

### The as-written bridge fails

`parameter-inventory.md` §3.3 writes

$$
\chi = \frac{\kappa\,\varphi^{-1}}{m_e(1+\varphi)}.
$$

This is dimensionally inconsistent: $\kappa_s$ has $[M]^{-2}$ and $m_e$ has $[M]$, so the right-hand side carries $[M]^{-3}$, not dimensionless $\chi$. It also fails numerically: with $\kappa_s = 0.92$ TeV$^{-2}$ and $m_e = 5.11\times10^{-4}$ GeV,

$$
\chi = \frac{\kappa_s\,\varphi^{-1}}{m_e(1+\varphi)} \approx 4.25\times10^{-4},
$$

three orders of magnitude below the calibrated band $\chi \approx 0.5$–$1.0$.

### The repaired bridge

The missing factor is the PDE normalization: the Lagrangian's mass-dimensionful densities are reduced to the solver's normalized fields, and that reduction carries a dimensionful prefactor. The repaired bridge is

$$
\boxed{\chi = \mathcal{N}_{\text{pde}}\cdot\frac{\kappa_s\,\varphi^{-1}}{m_e(1+\varphi)}}
$$

where $\mathcal{N}_{\text{pde}}$ is the PDE normalization factor from the solver conventions (grid $L=40$, $N=48$, $\Delta t = 0.002$, $\rho_{\text{crit}} = \varphi$; `two-fluid/cassi_two_fluid_3d_gpu.py`). Matching the calibrated band requires $\mathcal{N}_{\text{pde}} \approx 2.35\times10^{3}$.

### The computational follow-up

Computing $\mathcal{N}_{\text{pde}}$ from the solver's reduction is a concrete calculation—it is the unit conversion between the Lagrangian densities and the solver fields, read off the normalization constants in `two-fluid/cassi_two_fluid_3d_gpu.py`. Until it is done, $\chi$ remains a C-class solver parameter in the inventory's classification; the bridge is repaired in form but not yet closed in value.

### The falsifiable check

Once $\mathcal{N}_{\text{pde}}$ is computed, the whole chain stands or falls on one number: $\chi$ must land in $[0.5, 1.0]$.

## 5. Predictions

| # | Prediction | Status |
|---|------------|--------|
| K1 | The sector-coupling scale is $\kappa_s^{-1/2} = \varphi^3 v_0 \approx 1.04$ TeV (rung 77 = 987.7 GeV; $\kappa_s = 0.92$ TeV$^{-2}$). | Derived scale (conditional on $\delta = 3$), testable via K2 |
| K2 | The repaired bridge closes: $\chi = \mathcal{N}_{\text{pde}}\cdot\kappa_s\varphi^{-1}/[m_e(1+\varphi)] \in [0.5, 1.0]$ once $\mathcal{N}_{\text{pde}}$ is computed from the solver conventions. | Plausible hypothesis, concrete computation |
| K3 | Rung 77 is the Dirac↔two-fluid equilibration scale—an answer to `foundations/dimensionful-cascade.md` §9 Q2 (dark steps). | Plausible hypothesis |

The K-numbers (letter K for kappa) do not collide with the numbered prediction catalog or the consciousness-doc prediction ranges.

## 6. Epistemic Boundaries

- **Supported by Verified Physics**: the rung-77 placement as arithmetic ($E_n = M_{\text{Pl}}\varphi^{-n}$; the rung identity $v_0^2 = M_{\text{Pl}}^2\varphi^{-160}$, $\kappa_s = M_{\text{Pl}}^{-2}\varphi^{154}$, $77 = 154/2$); consistency of $\kappa_s = 0.92$ TeV$^{-2}$ with the inventory's order of magnitude; the dimensional failure of the as-written $\chi$ bridge.
- **Derived conditional on $\delta = 3$**: the placement's *value* (rung 77, $\kappa_s = \varphi^{-6}/v_0^2$) inherits the shared 3-rung offset from $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`gravity/quantum-gravity.md` §2.1, itself conditional on $d = 3$). With $\delta \neq 3$ the coupling would be $\varphi^{-2\delta}/v_0^2$ at rung $80 - \delta$.
- **Plausible Hypothesis (test exists)**: $\kappa_s = \varphi^{-6}/v_0^2$ with $C = 1$; the $\mathcal{N}_{\text{pde}}$ computation is a concrete calculation with a falsifiable target ($\chi \in [0.5, 1.0]$).
- **Speculative**: TeV-scale phenomenology of the sector-coupling enforcement dynamics.
- **Not Supported**: any claim that the O(1) coefficient is determined without the mechanism (no discriminator between $C = 1$, $\varphi^{-1}$, $\varphi^{-2}$ yet).

**Inputs.**

$$
\boxed{
\begin{aligned}
&\text{(a) cascade ladder } E_n = M_{\text{Pl}}\,\varphi^{-n} && \text{framework-derived (foundations/dimensionful-cascade.md §2)}\\
&\text{(b) } v_0 = 246\ \text{GeV at rung 80} && \text{calibrated anchor } (n(v_0) = 79.89 \approx 80;\ E_{80} = 233.2\ \text{GeV})\\
&\text{(c) coupling form } \kappa_s = \varphi^{-6}/v_0^2 && \text{as documented (reciprocal of } \xi = \varphi^6 \text{ at the anchor)}\\
&\text{(d) } \delta = 3 && \text{inherited from } \sigma = \ell_{\text{Pl}}/\varphi^3 \text{ (gravity/quantum-gravity.md §2.1, conditional on } d = 3)
\end{aligned}
}
$$

Output: the rung identity $M_s = \kappa_s^{-1/2} = M_{\text{Pl}}\,\varphi^{-77}$ (rung $77 = 154/2$), $\kappa_s = 9.21\times10^{-7}\ \text{GeV}^{-2} = 0.92\ \text{TeV}^{-2}$.

## References

- `foundations/unified-lagrangian.md`—§5.2/§5.5/§6/§7.2: sector-coupling definition (Dirac→two-fluid projection, full mixing Lagrangian, complete action, Dirac equation of motion)
- `foundations/dimensionful-cascade.md`—§2–§3: rung ladder $E_n = M_{\text{Pl}}\varphi^{-n}$; §9: dark-step open questions
- `gravity/quantum-gravity.md`—§2.1: $\sigma = \ell_{\text{Pl}}/\varphi^3$ with $\delta = 3 = d$ (the shared offset; cross-check (ii) points here)
- `computations/kappa_s_rung_identity.py`—numerical verification of the rung identity and every value in §2
- `foundations/deriving-remaining-gaps.md`—§3.3: EW discretization residual class ($n = 79.89$, 5.3% gap)
- `foundations/dimensionful-constants-status.md`—§2.1: $\lambda = 1/(2w)$ rate precedent (rational, not a $\varphi$-power)
- `foundations/wu-xing-cycle-structure.md`—§1.3: the other $\kappa$ (pentagram transmission $K_{fw} = \varphi^{-1}$)
- `principles/de-resonance-principle.md`—$\varphi$-baseline posture: attractor sets leading order, dynamics supply corrections
- `parameter-inventory.md`—§3.3: status of $\chi$ and $\kappa$ (free, $\sim 1/\text{TeV}^2$)
