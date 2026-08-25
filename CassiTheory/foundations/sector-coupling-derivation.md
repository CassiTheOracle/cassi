# Coefficient-Free Sector Scale: $\kappa_{s,\mathrm{scale}} = \varphi^{-6}/v_0^2$

## Status: Derived conditional on $\delta = 3$ (coefficient-free $\varphi$ scale and rung identity); optional Dirac↔two-fluid projection is a dimensionally incomplete Hypothesized ansatz (no physical $\kappa_s$ or $\chi$ value established; $v_0$ input Calibrated, $\mathcal{N}_{\mathrm{pde}}$ repair unresolved and not sourced/ledgered)—August 2026

## Abstract

The cascade supplies a coefficient-free arithmetic scale form $\kappa_{s,\mathrm{scale}} = \varphi^{-6}/v_0^2 = M_{\text{Pl}}^{-2}\varphi^{154}$ conditional on $\delta = 3$, with the formal mass scale $M_{s,\mathrm{scale}} = \kappa_{s,\mathrm{scale}}^{-1/2} = \varphi^3 v_0$ at rung $77 = 154/2$ (rung 77 ≈ 1.04 TeV). It does not establish a physical Dirac↔two-fluid coupling: the proposed projection below subtracts a spinor density of dimension $[M]^3$ from a condensate square of dimension $[M]^2$, and no sourced or ledgered normalization/mass scale repairs that mismatch. The values 1.04 TeV and 0.92 TeV$^{-2}$ are reported only as formal $C = 1$ arithmetic candidates; the full coupling and the bridge to $\chi$ remain unresolved.

## 1. The Optional Projection Ansatz and Its Symbol

The proposed Dirac↔two-fluid projection is presented only as an optional ansatz for identifying the unresolved dictionary:

$$
\boxed{\mathcal{L}_{D\to TF}^{\mathrm{optional}} = \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)^2}
$$

The displayed ansatz is not a dimensionally valid Lagrangian: the bracket subtracts quantities with different mass dimensions. It is therefore a dimensionally incomplete Hypothesized ansatz, not an established interaction from which a physical $\kappa_s$, equilibration timescale, or $\chi$ bridge can be inferred.

with $P_{\pm} = (1\pm\gamma^5)/2$ the chiral projectors. The plus term is intended to tie the right-handed density to the Yang condensate square $\Psi_0^2$, and the minus term the left-handed density to the Yin condensate square $\Psi_1^2$. No numerical coupling or timescale follows until a sourced and ledgered field/mass normalization makes the projection homogeneous.

### The symbol

The symbol $\kappa$ is shared with two other established constants. The Wu Xing pentagram transmission $\kappa = \varphi^{-1} = K_{fw}$ ("Water damps Fire", the control-cycle coefficient fixed by the pentagon side/diagonal ratio) is a different, derived constant documented in `foundations/wu-xing-cycle-structure.md` §1.3, and a charge-density constant appears as $\kappa$ in the Qi charge/current definitions of `predictions/cassi_definitions.md` ($\rho = -\kappa\nabla^2 q$, $J = \kappa\,\partial_t\nabla q$). This document uses $\kappa_s$ (s = sector) for a future repaired Dirac↔two-fluid coupling; no physical $\kappa_s$ value is established by the optional ansatz.

### Dimensions

The bracket in the optional ansatz attempts to subtract a $[M]^3$ spinor density from a $[M]^2$ condensate square, so it is undefined before any square is taken. No sourced or ledgered normalization/mass scale is specified. Consequently the intended mass dimension $-2$ and the interpretation of $\kappa_s$ as a stiffness or equilibration rate cannot be assigned from this expression; only the coefficient-free cascade arithmetic is reported below.

## 2. The scale: three rungs above electroweak

The cascade supplies a coefficient-free scale form, not a measured full coupling: conditional on $\delta = 3$, it places the formal $C = 1$ scale candidate at three rungs above the electroweak VEV. A physical $\kappa_s$ would require a dimensionally valid projection and a sourced normalization; neither is supplied here.

### The cascade tool

Energy rungs follow the cascade ladder `foundations/dimensionful-cascade.md` §2,

$$
E_n = M_{\text{Pl}}\cdot\varphi^{-n},
$$

with $M_{\text{Pl}} = 1.2209\times10^{19}$ GeV. Each step down in $n$ multiplies the scale by $\varphi$.

### The electroweak anchor

The VEV $v_0 = 246$ GeV sits at $n = 79.89 \approx 80$: rung 80 is $E_{80} = M_{\text{Pl}}\varphi^{-80} = 233.2$ GeV, a $-5.22\%$ offset from $v_0$, the same discretization-residual class documented as the "5.3% gap" in `foundations/deriving-remaining-gaps.md` §3.3 ($\delta n = 0.11$ steps, a soft boundary between cascade regimes). The coefficient-free scale candidate inherits this placement.

### Three rungs up: rung 77

The coefficient-free scale candidate sits three rungs above the electroweak rung:

$$
E_{77} = M_{\text{Pl}}\cdot\varphi^{-77} = 987.7\ \text{GeV}.
$$

The round 1 TeV is $+1.24\%$ off this rung ($\log_\varphi(M_{\text{Pl}}/1\,\text{TeV}) = 76.97$).

### The rung identity: why 77

The placement is not an independent "three rungs up" assertion—it follows from the exponent arithmetic of the coefficient-free scale form $\kappa_{s,\mathrm{scale}} = \varphi^{-6}/v_0^2$. The VEV sits at rung 80,

$$
v_0 = M_{\text{Pl}}\,\varphi^{-80} \quad (\text{rung } 80),
$$

and squaring doubles the rung index ($80 \to 2\cdot 80 = 160$):

$$
v_0^2 = M_{\text{Pl}}^2\,\varphi^{-160}.
$$

Inserting into $\kappa_{s,\mathrm{scale}}$,

$$
\kappa_{s,\mathrm{scale}} = \frac{\varphi^{-6}}{v_0^2}
        = \varphi^{-6}\,M_{\text{Pl}}^{-2}\,\varphi^{160}
        = M_{\text{Pl}}^{-2}\,\varphi^{154}.
$$

The $\varphi$-exponent of $\kappa_{s,\mathrm{scale}}$ relative to the $M_{\text{Pl}}^{-2}$ base is $+154$—not the naive $-160 - 6 = -166$, because $v_0^2$ carries the dimensionful base $M_{\text{Pl}}^2$ and the $\varphi^{-6}$ stands in the numerator. The associated formal scale is

$$
M_{s,\mathrm{scale}} = \kappa_{s,\mathrm{scale}}^{-1/2} = M_{\text{Pl}}\,\varphi^{-154/2} = M_{\text{Pl}}\,\varphi^{-77}
$$

sits at rung $77 = 154/2$: halving the exponent inverts the squaring. Equivalently, $M_{s,\mathrm{scale}} = \varphi^3 v_0$: multiplying the VEV by $\varphi^3$ climbs three rungs ($E_{n-3} = E_n\,\varphi^3$), so $n(M_{s,\mathrm{scale}}) = n(v_0) - 3 = 80 - 3 = 77$.

**The offset is $\delta = 3$—the same $\delta$ as the gravity regulator.** Write the placement as

$$
\boxed{\delta = n_{v_0} - n_{s,\mathrm{scale}} = 80 - 77 = 3}
$$

with $n_{s,\mathrm{scale}}$ the rung of the formal $M_{s,\mathrm{scale}}$. This is the same 3-rung offset as $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`gravity/quantum-gravity.md` §2.1), where $\delta = 3 = d$ is derived conditional on the three-dimensional phase-resolution postulate. **The rung-77 placement is therefore derived conditional on $\delta = 3$**: with the shared offset $\delta$ the coefficient-free scale form is $\kappa_{s,\mathrm{scale}} = \varphi^{-2\delta}/v_0^2$ at rung $80 - \delta$; a future repaired coupling would be $C\,\kappa_{s,\mathrm{scale}}$. The reverse cross-check appears in `gravity/quantum-gravity.md` §2.1 (ii).

The rung identity is exact in the exponent arithmetic ($154/2 = 77$). The *formal $C = 1$ scale* $M_{s,\mathrm{scale}} = \varphi^3 v_0 = 1042.07$ GeV inherits the VEV's discretization residual, sitting $\delta n = 0.11$ steps below rung 77 ($+5.50\%$ above $E_{77}$)—the same residual class as the EW anchor itself. All values are verified as arithmetic for this formal candidate in `computations/kappa_s_rung_identity.py`.

### The VEV-anchored form

Equivalently, the scale is $\varphi^3$ times the electroweak VEV:

$$
\boxed{M_{s,\mathrm{scale}} = \kappa_{s,\mathrm{scale}}^{-1/2} \approx \varphi^3 v_0 \approx 1.04\ \text{TeV}}
$$

with $\varphi^3 = 4.23607$, giving $\varphi^3 v_0 = 1042.07$ GeV—$+5.50\%$ off rung 77, the same discretization-residual class as the EW anchor itself. Inverting the coefficient-free scale form,

$$
\boxed{\kappa_{s,\mathrm{scale}} = \frac{\varphi^{-6}}{v_0^2} = \frac{1}{\xi\, v_0^2} = 9.21\times10^{-7}\ \text{GeV}^{-2} = 0.92\ \text{TeV}^{-2}}
$$
The displayed inversion is a formal $C = 1$ scale evaluation; without a dimensionally valid projection and sourced normalization, it is not a physical $\kappa_s$ value.

where $\xi = \varphi^6 = 17.94427191$ is the Qi-gravity coupling.

### Observation, not mechanism

The suppression $\kappa_{s,\mathrm{scale}} \propto \varphi^{-6}$ is the reciprocal of the Qi-gravity enhancement $\xi = \varphi^6$ at the electroweak anchor (`foundations/unified-lagrangian.md` §5.1). This reciprocity is an observation about the arithmetic, not a claimed mechanism; a physical coefficient remains blocked by the optional projection's dimensional defect.

### A dark step answered

Rung 77 is a "dark step"—a rung the activated set $\{1,2,3,5,6,26,80,292\}$ leaves unlabeled. `foundations/dimensionful-cascade.md` §9 Q2 asks whether dark steps carry physical meaning (sterile neutrino masses, dark sector couplings). This document supplies a conditional formal $C = 1$ scale-form candidate at rung 77; interpreting it as the Dirac↔two-fluid equilibration scale remains a plausible hypothesis blocked by the dimensionally incomplete projection.

### Consistency with the inventory

`parameter-inventory.md` §3.3's slogan "$\kappa \sim 1/\text{TeV}^2$" is not pinned to a unique physical coupling. The exact scale form gives the formal $C = 1$ candidate $\kappa_{s,\mathrm{scale}} = 0.92$ TeV$^{-2}$—the same order of magnitude as the inventory's estimate—while the alternatives in §3 and the dimensional repair remain open.

## 3. Optional Coefficient Fork: Projection Remains Dimensionally Incomplete

The coefficient-free scale form is derived conditional on $\delta = 3$, but assigning it to a physical $\kappa_s$ requires a dimensionally valid projection. The optional ansatz in §1 supplies no homogeneous bracket and no sourced or ledgered normalization.

If a future repair supplies that missing normalization, one could write $\kappa_s = C\,\kappa_{s,\mathrm{scale}}$ with $C$ an O(1) coefficient. The following are formal candidate readings only:

| $C$ | Reading | Formal $\kappa_s$ candidate | Formal $M_s$ candidate |
|-----|---------|----------------------------|-------------------------|
| $1$ | Pure $\xi^{-1}$ | 0.921 TeV$^{-2}$ | 1.042 TeV |
| $\varphi^{-1} = K_{fw}$ | One pentagram transmission | 0.569 TeV$^{-2}$ | 1.326 TeV |
| $\varphi^{-2}$ | Two transmissions | 0.352 TeV$^{-2}$ | 1.686 TeV |

All three are formal values inside the "$\sim 1/\text{TeV}^2$" band; the inventory's order-of-magnitude slogan cannot discriminate between them, and none is an established physical coupling.

The canonical solver's rational normalization $\lambda = 0.1$ and the Hypothesized Wu Xing linkage do not select $C$. The de-resonance posture (`principles/de-resonance-principle.md` §6) likewise leaves the leading coefficient to dynamics that have not been specified.

Conclusion: the coefficient-free scale arithmetic is Derived conditional on $\delta = 3$; the projection and all physical coefficient readings are dimensionally incomplete optional Hypotheses. The $\chi$ bridge remains blocked.

## 4. The $\chi$ Bridge: Blocked Pending Dimensional Repair

The inventory's bridge from a sector coupling to the chemotactic mobility $\chi$ cannot be closed while the projection in §1 is dimensionally incomplete.

### Dimensional failure of the as-written bridge

`parameter-inventory.md` §3.3 writes

$$
\chi = \frac{\kappa\,\varphi^{-1}}{m_e(1+\varphi)}.
$$

The expression is dimensionally inconsistent: a putative $\kappa_s$ has intended $[M]^{-2}$ while $m_e$ has $[M]$, so the right-hand side carries $[M]^{-3}$, not dimensionless $\chi$. A formal substitution of the $C = 1$ scale number yields $4.25\times10^{-4}$ in mixed units; it is not a $\chi$ value and cannot be compared with the calibrated band.

### Conditional bridge if a sourced repair is supplied

A dimensionful field/mass normalization would be required before the bridge can be evaluated. No such normalization is sourced or ledgered here, and an $\mathcal{N}_{\mathrm{pde}}$ factor cannot by itself repair the undefined bracket. If a future repair supplies both, the formal bridge would be

$$
\boxed{\chi = \mathcal{N}_{\mathrm{pde}}\cdot\frac{\kappa_s\,\varphi^{-1}}{m_e(1+\varphi)}}
$$

where $\mathcal{N}_{\mathrm{pde}}$ would be the solver normalization factor. Its value and the resulting $\chi$ remain unresolved.

### The computational follow-up

Computing $\mathcal{N}_{\mathrm{pde}}$ is downstream of the missing dimensional repair: it is not enough to read constants from `two-fluid/cassi_two_fluid_3d_gpu.py` while the Lagrangian bracket remains undefined. Until the repair is sourced and ledgered, $\chi$ remains a C-class solver parameter and the bridge is open.

### The falsifiable check after repair

Only after the normalization and projection are made dimensionally valid can the chain be tested against $\chi \in [0.5, 1.0]$.

## 5. Conditional Arithmetic and Blocked Predictions

| # | Prediction | Status |
|---|------------|--------|
| K1 | The formal coefficient-free scale is $M_{s,\mathrm{scale}} = \varphi^3 v_0 \approx 1.04$ TeV (rung 77 = 987.7 GeV; formal $\kappa_{s,\mathrm{scale}} = 0.92$ TeV$^{-2}$). | Derived arithmetic conditional on $\delta = 3$; not a physical coupling; no K2 closure |
| K2 | A repaired bridge could test $\chi = \mathcal{N}_{\mathrm{pde}}\cdot\kappa_s\varphi^{-1}/[m_e(1+\varphi)] \in [0.5, 1.0]$ after a sourced dimensional normalization exists. | Blocked Hypothesis; concrete computation remains downstream |
| K3 | Rung 77 is a formal coefficient-free candidate for a Dirac↔two-fluid equilibration scale. | Plausible Hypothesis only; physical interpretation blocked |

The K-numbers (letter K for the formal scale notation) do not collide with the numbered prediction catalog or the consciousness-doc prediction ranges.

## 6. Epistemic Boundaries

- **Supported by Verified Arithmetic**: the coefficient-free rung-77 placement ($E_n = M_{\text{Pl}}\varphi^{-n}$; $v_0^2 = M_{\text{Pl}}^2\varphi^{-160}$; $\kappa_{s,\mathrm{scale}} = M_{\text{Pl}}^{-2}\varphi^{154}$; $77 = 154/2$); the formal $C = 1$ scale's order-of-magnitude consistency; the dimensional failure of the optional projection and as-written $\chi$ bridge.
- **Derived conditional on $\delta = 3$**: the coefficient-free scale form $\kappa_{s,\mathrm{scale}} = \varphi^{-6}/v_0^2$ and its placement at rung 77, inherited from $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`gravity/quantum-gravity.md` §2.1, itself conditional on $d = 3$). With $\delta \neq 3$ the scale form would be $\varphi^{-2\delta}/v_0^2$ at rung $80 - \delta$.
- **Hypothesized but dimensionally incomplete**: the optional Dirac↔two-fluid projection, any physical $\kappa_s=C\,\kappa_{s,\mathrm{scale}}$ assignment, and the associated equilibration interpretation. No sourced normalization repairs the bracket.
- **Blocked Hypothesis (test exists after repair)**: the $\mathcal{N}_{\mathrm{pde}}$ computation and any $\chi \in [0.5, 1.0]$ result.
- **Speculative**: TeV-scale phenomenology of the sector-coupling enforcement dynamics.
- **Not Supported**: any claim that the O(1) coefficient or physical coupling is determined without a dimensionally valid mechanism (no discriminator between $C = 1$, $\varphi^{-1}$, $\varphi^{-2}$).

**Inputs.**

$$
\boxed{
\begin{aligned}
&\text{(a) cascade ladder } E_n = M_{\text{Pl}}\,\varphi^{-n} && \text{framework-derived (foundations/dimensionful-cascade.md §2)}\\
&\text{(b) } v_0 = 246\ \text{GeV at rung 80} && \text{calibrated anchor } (n(v_0) = 79.89 \approx 80;\ E_{80} = 233.2\ \text{GeV})\\
&\text{(c) coefficient-free scale form } \kappa_{s,\mathrm{scale}} = \varphi^{-6}/v_0^2 && \text{exact conditional arithmetic (reciprocal of } \xi = \varphi^6 \text{ at the anchor)}\\
&\text{(d) } \delta = 3 && \text{inherited from } \sigma = \ell_{\text{Pl}}/\varphi^3 \text{ (gravity/quantum-gravity.md §2.1, conditional on } d = 3)
\end{aligned}
}
$$

Output of the exact conditional $\varphi$ arithmetic: $M_{s,\mathrm{scale}} = M_{\text{Pl}}\,\varphi^{-77}$ (rung $77 = 154/2$) and $\kappa_{s,\mathrm{scale}} = 9.21\times10^{-7}\ \text{GeV}^{-2} = 0.92\ \text{TeV}^{-2}$. These are formal scale values, not a physical $\kappa_s$, $\chi$, or repaired Lagrangian coupling.

## References

- `foundations/unified-lagrangian.md`—§5.2/§5.5/§6/§7.2: optional Dirac→two-fluid projection ansatz (dimensionally incomplete), full mixing Lagrangian, complete action, Dirac equation of motion
- `foundations/dimensionful-cascade.md`—§2–§3: rung ladder $E_n = M_{\text{Pl}}\varphi^{-n}$; §9: dark-step open questions
- `gravity/quantum-gravity.md`—§2.1: $\sigma = \ell_{\text{Pl}}/\varphi^3$ with $\delta = 3 = d$ (the shared offset; cross-check (ii) points here)
- `computations/kappa_s_rung_identity.py`—numerical verification of the rung identity and every value in §2
- `foundations/deriving-remaining-gaps.md`—§3.3: EW discretization residual class ($n = 79.89$, 5.3% gap)
- `foundations/dimensionful-constants-status.md`—§2.1: canonical $\lambda = 0.1$ solver normalization and Hypothesized $\lambda = 1/(2w)$ linkage (rational, not a $\varphi$-power)
- `foundations/wu-xing-cycle-structure.md`—§1.3: the other $\kappa$ (pentagram transmission $K_{fw} = \varphi^{-1}$)
- `principles/de-resonance-principle.md`—$\varphi$-baseline posture: attractor sets leading order, dynamics supply corrections
- `parameter-inventory.md`—§3.3: status of $\chi$ and $\kappa$ (free, $\sim 1/\text{TeV}^2$)
