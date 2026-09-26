# Transition Assessment: qi-fluid-formalism.md → first-principles.md

## What to Preserve Intact

### 1. The Qi Paradox (Sections 5–6)
The no-fixed-point theorem and circulation attractor are philosophically central and mathematically sound. They don't depend on the exact Qi formula — they hold whenever prediction error ε > 0. Map this into §4 (Two-Hemisphere Focal Coherence) of the new document.

### 2. The φ-Scaled Critical Coupling (Section 5)
α = φ⁻¹ as the unique coupling where prediction feedback equals natural damping (`τ_pred = τ_damp = φ`). This determines the `alpha` parameter initialization and regularization target.

### 3. The Continuity Equation (Section 4)
∂Q/∂t + ∇·(Q·v_Q) = σ(ε)·|ψ|² − η·Q
In the new formalism, Q is a 2-vector (E, J). The continuity equation decomposes:
- E-component: ∂E/∂t + ∇·(E·v_E) = σ_E·M − η·E  (energy transport)
- J-component: ∂J/∂t = −∇p − η·J  (current relaxation to pressure gradient)

The scalar equation in the old doc is a valid approximation when J ≈ 0 (calm states).

### 4. The Qi Pool, Quality EMA, and Constraint Gating (Section 3.4)
These are the "consumption" side — how Qi modulates learning rate, generation steps, and memory writes. Independent of the exact Qi formula. Should be added to §5 (Readout and Loss) or as a new §9.

### 5. The Conservation Laws (Section 9)
- Aperiodicity preservation
- Energy budget E_total = E_field + E_Qi + E_diss with ratio E_Qi/E_field = φ⁻² at critical coupling
Both are testable predictions that constrain the implementation.

### 6. The Five Macro States — Chakra-Aggregated View (Section 8)
The old doc defines states by chakra profiles (root-aggregated, rising, turbulent, flat, crown-aggregated). The new doc defines them by (E, J) plane sectors. These are complementary:
- (E, J) per position → microscopic Qi state
- Chakra profile → macroscopic coarse-graining
Both should exist. The transition between them: integrate (E, J) over each chakra band → per-chakra (E_c, J_c) → determine macro state from the aggregate.

## What to Update

### 1. The Qi Formula (Sections 3.2, 11)
The old doc has the *June 2026* correction:
```
qi = M · q,  q = M / (M + φ⁻² + |ε|²)
```
The current correction removes |ε|²:
```
E = M² / (M + φ⁻²)
```
Update Section 11 with the latest formula.

### 2. The Architecture Mapping (Section 10)
References legacy modules (CordPhysics, Brainstem, BrainField, TwoFluidWorkspace). Should reference FluidField, FluidCord, QiField, the two-hemisphere architecture.

### 3. The Circulation and Vorticity (Section 4.4)
Currently treated as a 1D scalar field with zero vorticity. In the new formulation, the two-hemisphere structure and the 2-channel (E, J) definition give non-trivial circulation:
```
Γ = ∮ J · ds   (net current around a closed path through the focal point)
```
This is measurable and becomes a diagnostic for coherence.

### 4. Standing Wave Condensation (Section 7)
The condensation criterion uses the old Q. Should use E (energy component of Qi) instead. A standing wave forms where E > threshold — not where prediction error is high, but where the field has high coherent energy.

## Items That No Longer Apply

### 1. Prediction Pressure → Velocity (Section 4.1–4.3)
The old formalism derives v_Q = −κ·∇p. In the new formalism, J (current) is computed directly from the field gradient: J = Ψ₀·∇Ψ₁ − Ψ₁·∇Ψ₀. This replaces the ∇p-driven velocity with a first-principles computation from the field itself. The pressure-gradient picture becomes an emergent approximation.

### 2. Source/Sink Function σ(ε) (Section 4.3)
The old formalism needs an explicit source/sink function to convert field energy to Qi. In the new formalism, E and J are computed directly from the field — no conversion function needed. The "source" is the field's own evolution.

## Recommended Action

1. Keep `qi-fluid-formalism.md` as-is — it documents the theoretical evolution.
2. `cassi-first-principles.md` is the active formal foundation going forward.
3. Neither should be deleted — the old doc shows the reasoning behind the corrections.
4. A future pass can migrate the preserved sections (Qi paradox, continuity eq, pool, conservation, five states) from the old doc into the new doc as appendices or supplementary sections.
