# Cassi Field Formalism — First Principles

## 1. The Field

A neural PDE over a paired real field `Ψ ∈ ℝ^{B×N×d×2}`, mapping `U(1) ≅ SO(2)`:

$$
\Psi\_{b,n,c,\alpha} = \begin{pmatrix}
\operatorname{Re}\psi\_{b,n,c} \\\\
\operatorname{Im}\psi\_{b,n,c}
\end{pmatrix}
$$

- `B`: batch dimension
- `N`: spatial positions (sequence length)
- `d`: field channels per position (sum of φ-scaled chakra widths)
- `α ∈ {0,1}`: the paired real axes (the "real" and "imaginary" components in U(1) form)

### 1.1 Chakra decomposition

The `d` channels are partitioned into 13 φ-scaled chakra bands. Each chakra `k` occupies a contiguous slice:

$$
\text{span}(k) = [s_k, e_k), \quad s_{k+1} - s_k = \big\lfloor \phi^{-k} d \big\rfloor
$$

where `φ = (1 + √5)/2 ≈ 1.618` and `φ⁻¹ ≈ 0.618`.

---

## 2. Field Operations in Real Form

### 2.1 Field magnitude (energy density)

$$
M_{b,n,c} = \Psi_{b,n,c,0}^2 + \Psi_{b,n,c,1}^2
$$

### 2.2 Phase gradient (current density)

The spatial gradient (spectral derivative):

$$
(\nabla\Psi)_{b,n,c,\alpha} = \mathcal{F}^{-1}\big[\,i k \cdot \mathcal{F}[\Psi]\,\big]_{b,n,c,\alpha}
$$

Current density measures how the phase winds through space:

$$
J_{b,n,c} = \Psi_{b,n,c,0} \cdot (\nabla\Psi)_{b,n,c,1} - \Psi_{b,n,c,1} \cdot (\nabla\Psi)_{b,n,c,0}
$$

### 2.3 Advection (self-consistent transport)

In complex form this is `ψ · ∇ψ`. In paired real form:

$$
\text{adv}_{\alpha} = -(\Psi_{(1-\alpha)} \cdot \nabla\Psi_{(1-\alpha)}) \cdot (\nabla\Psi)_\alpha
                + (\Psi_\alpha \cdot \nabla\Psi_{(1-\alpha)}) \cdot (\nabla\Psi)_{(1-\alpha)}
$$

More compactly, for each channel `c`:

$$
\text{adv}_0 = -(\Psi_1 \cdot \nabla\Psi_1) \cdot \nabla\Psi_0 + (\Psi_0 \cdot \nabla\Psi_1) \cdot \nabla\Psi_1
$$
$$
\text{adv}_1 = -(\Psi_0 \cdot \nabla\Psi_0) \cdot \nabla\Psi_1 + (\Psi_1 \cdot \nabla\Psi_0) \cdot \nabla\Psi_0
$$

### 2.4 Quantum potential

The Bohm quantum potential with φ-scaled exponent `β = φ⁻¹/2 ≈ 0.309`:

$$
Q_\alpha = -\frac{\hbar^2}{2m^2} \cdot \frac{\nabla^2 M^\beta}{M^\beta} \cdot \Psi_\alpha
$$

With stability clamp:

$$
M^\beta \leftarrow \max(M^\beta, 10^{-2})
$$

### 2.5 Rotation (dispersion)

The `SO(2)` rotation corresponding to `exp(i·χ·k·t)`:

$$
\Psi_0^{t+1} = \Psi_0^t \cos(\chi k \Delta t) - \Psi_1^t \sin(\chi k \Delta t)
$$
$$
\Psi_1^{t+1} = \Psi_0^t \sin(\chi k \Delta t) + \Psi_1^t \cos(\chi k \Delta t)
$$

### 2.6 Diffusion (linear damping)

$$
\Psi_\alpha^{t+1} = \Psi_\alpha^t \cdot \exp(- \nu k^2 \Delta t)
$$

Both 2.5 and 2.6 compose into the Fourier-space propagator:

$$
\hat\Psi_\alpha^{t+1} = e^{- \nu k^2 \Delta t} \cdot \mathbf{R}(\chi k \Delta t) \cdot \hat\Psi_\alpha^t
$$

where `\hat\Psi` is the spatial Fourier transform and `𝐑(θ)` is the 2×2 rotation matrix:

$$
\mathbf{R}(\theta) = \begin{pmatrix}
\cos\theta & -\sin\theta \\\\
\sin\theta & \cos\theta
\end{pmatrix}
$$

### 2.7 Nonlinear coupling

The self-interaction term `g · |ψ|² · ψ` in complex form:

$$
\text{nl}_\alpha = g \cdot M \cdot \Psi_\alpha
$$

### 2.8 Breath modulation

Harmonic modulation by the breath oscillator (dual-heart):

$$
\text{breathe}_\alpha = A_B \cdot \text{breath}(t) \cdot \Psi_\alpha
$$

where `breath(t)` is a dual-frequency oscillator (yang ≈ 1.0 Hz, yin = φ⁻¹·yang).

---

## 3. Qi — Coherent Energy

Qi is a **2-vector** at each field location:

$$
\mathbf{Q}_{b,n,c} = (E_{b,n,c},\; J_{b,n,c})
$$

### 3.1 Energy component

Coherent energy (self-consistency measure, independent of any external predictor):

$$
E_{b,n,c} = \frac{M_{b,n,c}^2}{M_{b,n,c} + \phi^{-2}}
$$

where `φ⁻² ≈ 0.382` is the minimum energy floor.

- When `M ≫ φ⁻²`: `E ≈ M` (calm, powerful)
- When `M ≪ φ⁻²`: `E ≈ M²/φ⁻²` (dormant, weak)
- Always `E ∈ [0, ∞)` and monotonic in `M`.

### 3.2 Flow component

Phase current density — directional flow of energy:

$$
J_{b,n,c} = \Psi_0 \cdot \nabla\Psi_1 - \Psi_1 \cdot \nabla\Psi_0
$$

- `J > 0`: Yang-biased — energy ripples **outward** (creative, expansive)
- `J < 0`: Yin-biased — energy ripples **inward** (consolidating, absorbing)
- `J ≈ 0`: balanced — energy is stationary (calm)

### 3.3 The five macro states of Qi

The `(E, J)` plane partitions into five φ-scaled sectors. Let `ε = φ⁻³ ≈ 0.236` be the flow threshold:

| # | State | E | J | Feel |
|---|-------|---|---|------|
| 1 | **太和** Calm Power | `> φ⁻²` | `\|J\| < ε·E` | High energy, balanced flow. The cultivated state. |
| 2 | **陽盛** Creative Yang | `> φ⁻²` | `J > ε·E` | Strong outward flow. Generating structure. |
| 3 | **陰盛** Consolidating Yin | `> φ⁻²` | `J < -ε·E` | Strong inward flow. Absorbing structure. |
| 4 | **靜明** Dormant Clarity | `≤ φ⁻²` | `\|J\| < ε·E` | Weak but coherent. Receptive. |
| 5 | **枯竭** Depletion | any | `\|J\| ≫ E` | Incoherent. Random drift. |

Macro state is determined by checking `(E, J)` at the focal point for each position, then averaging or voting over the sequence for an overall training signal. The five states form a periodic macro-cycle with φ-scaled transition boundaries.

---

## 4. Two-Hemisphere Architecture

Two fields `Ψ^L` and `Ψ^R` evolve simultaneously, each with its own dynamics and a cross-coupling term connecting them.

### 4.1 Directionality

**Left field**: integrates forward in position. Position `n` has received source context from positions `[0, n-1]`:

$$
\Psi^L \text{ uses source sequence } S_{0..N-1} \text{ (forward order)}
$$

**Right field**: integrates forward from the opposite end. Position `n` has received source context from positions `[n+1, N-1]`:

$$
\Psi^R \text{ uses source sequence } S_{N-1..0} \text{ (reversed order)}
$$

Both use identical forward-time PDE dynamics — the same propagator `exp(-νk²Δt)·R(χkΔt)` and the same nonlinear steps. There is **no backward-time integration**.

After integration, the right field is flipped back to align positions with the left field.

### 4.2 Cross-coupling

During each PDE substep, fields interact through a learnable coupling:

$$
\frac{\partial \Psi^L_n}{\partial t} =
F(\Psi^L_n, S_n) + \gamma \cdot \mathcal{C}(\Psi^R_n, \Psi^L_n)
$$
$$
\frac{\partial \Psi^R_n}{\partial t} =
F(\Psi^R_n, S_{N-1-n}) + \gamma \cdot \mathcal{C}(\Psi^L_n, \Psi^R_n)
$$

where `F` is the full PDE dynamics (advection + QP + nonlinear + breath + source), and `𝒞` is the cross-coupling operator:

$$
\mathcal{C}(\Psi^A, \Psi^B)_\alpha = \Xi_{\alpha\beta}(E^A, J^A) \cdot \Psi^B_\beta
$$

The coupling matrix `Ξ` is a 2×2 gating matrix determined by the sending field's Qi:

$$
\Xi = \begin{pmatrix}
\kappa_{11} & -\kappa_{12} \cdot J^A \\\\
\kappa_{21} \cdot J^A & \kappa_{22}
\end{pmatrix}
$$

where `κ_{ij}` are learnable scalars (possibly chakra-specific). When `J^A ≈ 0` (calm/balanced), the off-diagonals vanish — hemispheres decouple. Strong current (directional flow) gates the coupling.

### 4.3 Focal point coherence

At the focal point — the position `n` currently being read out — the two fields' Qi vectors combine:

$$
E^{\text{focal}} = \frac{E^L \cdot E^R}{E^L + E^R + \phi^{-2}}
$$
$$
J^{\text{focal}} = J^L - J^R
$$

- Focal `E` is high only when both hemispheres have high energy at the same position (agreement).
- Focal `J` is the difference — net outward (Yang, left-dominant) or inward (Yin, right-dominant) bias.

The overall `(E^{\text{focal}}, J^{\text{focal}})` determines the macro state of the system at the point of prediction.

---

## 5. Readout and Loss

### 5.1 Readout

The readout head receives the first component (real-part-like) of each hemisphere's field at the focal position, concatenated and layer-normalized:

$$
\Pi_{b,n} = \text{LayerNorm}\big( [\Psi^L_{b,n,:,0}, \Psi^R_{b,n,:,0}] \big) \quad \in \mathbb{R}^{2d}
$$

This vector feeds into a linear classification head → logits over the vocabulary:

$$
\text{logits}_{b,n,v} = \mathbf{W}_{\text{out}} \cdot \Pi_{b,n} + \mathbf{b}_{\text{out}}
$$

### 5.2 Training loss

The primary training signal is **field self-consistency**, with token prediction as a weak regularizer:

$$
\mathcal{L} = \alpha \underbrace{ \big\| \Psi^L_{1..N} - P_L(\Psi^L_{0..N-1}) \big\|^2 }_{\text{left self-prediction}}
           + \beta \underbrace{ \big\| \Psi^R_{0..N-1} - P_R(\Psi^R_{1..N}) \big\|^2 }_{\text{right self-prediction}}
           + \gamma \underbrace{ \big\| \Psi^L_{\text{focal}} - \Psi^R_{\text{focal}} \big\|^2 }_{\text{focal coherence}}
           + \delta \underbrace{ \text{CE}(\text{readout}, x) }_{\text{token anchor}}
$$

where `P_L` and `P_R` are per-hemisphere field predictors (Linear layers). Default weights:

- `α = β = 0.1` — self-consistency
- `γ = 0.05` — focal coherence
- `δ = 0.01` — token anchor

This loss simultaneously trains:
- The left field to be forward-predictable (smooth dynamics in the forward direction)
- The right field to be backward-predictable (smooth dynamics in the reverse direction)
- Both fields to agree at the focal point
- The field structure to be anchored to observable tokens (weak constraint)

---

## 6. Split-Step Integration Loop

Each PDE substep `Δt` follows this sequence:

### 6.1 Compute PDE coefficients
```
ν ← sigmoid(nu_logit) · 0.3
ℏ ← sigmoid(hbar_logit) · 0.8 + 0.2
m ← sigmoid(mass_logit) · 99 + 1
g ← tanh(g_logit) · 0.3 + 0.3
χ ← sigmoid(chi_logit) · 0.15 + 0.05
A_B ← sigmoid(A_B_logit) · 0.5
α ← sigmoid(alpha_logit)
```

### 6.2 Nonlinear half-step A (position space)

For each hemisphere:

1. Compute `M = Ψ₀² + Ψ₁²` (magnitude)
2. Compute `J = Ψ₀·∇Ψ₁ − Ψ₁·∇Ψ₀` (current)
3. Compute advection `adv_α` (equation 2.3)
4. Compute QP `Q_α` (equation 2.4) with `M^β` clamped at `10⁻²`
5. Compute nonlinear `nl_α = g · M · Ψ_α`
6. Compute breathe `b_α = A_B · breath(t) · Ψ_α`
7. Compute cross-coupling `𝒞` (equation 4.2)
8. Update:
   $$
   \Psi_\alpha \leftarrow \Psi_\alpha + \frac{\Delta t}{2} \big( \text{adv}_\alpha + Q_\alpha + \text{nl}_\alpha + \text{breathe}_\alpha + \mathcal{C}_\alpha + S_\alpha \big)
   $$

### 6.3 Clamp

$$
\Psi_\alpha \leftarrow \text{clamp}(\Psi_\alpha, -10^3, 10^3)
$$

### 6.4 Linear step (Fourier space)

For each hemisphere independently:

1. `\hat\Psi_\alpha ← FFT(\Psi_\alpha)` along the position dimension
2. Apply propagator:
   $$
   \hat\Psi_\alpha \leftarrow e^{- \nu k^2 \Delta t} \cdot \mathbf{R}(\chi k \Delta t) \cdot \hat\Psi_\alpha
   $$
3. `\Psi_\alpha ← IFFT(\hat\Psi_\alpha)` back to position space

### 6.5 Nonlinear half-step B (position space)

Repeat step 6.2 with the updated `Ψ`. This completes the split-step.

### 6.6 Normalize

Per position, normalize each channel group:

$$
\Psi_{\alpha,c} \leftarrow \frac{\Psi_{\alpha,c}}{\max_c(\sqrt{M_c}) + 10^{-8}}
$$

---

## 7. Breath Oscillator

Dual-heart breath provides the rhythmic carrier wave:

$$
\text{breath}(t) = \frac{1}{2} \big( \sin(2\pi \omega_{\text{yang}} t) + \sin(2\pi \omega_{\text{yin}} t) \big)
$$

where `ω_{\text{yang}} ≈ 1.0` Hz (yang heart) and `ω_{\text{yin}} = φ⁻¹ · ω_{\text{yang}}` (yin heart). The breath phase advances at each integration step. The breath's dual-frequency spectrum provides the φ-scaled modulation that couples all rhythmic processes in the field.

The breathing oscillation acts through the `A_B` coefficient — it modulates the field uniformly, creating a standing wave that "breathes" energy in and out of the field at the dual-heart rhythm.

---

## 8. Implemented Corrections from Prior Practice

The following corrections were discovered through implementation and are now part of the formal foundation:

### 8.1 Qi independent of prediction error

The original formula included `|ε|²` (prediction error) in the denominator:
$$
q = \frac{M}{M + \phi^{-2} + |\varepsilon|^2}
$$
This was incorrect — it made Qi collapse to zero whenever prediction error dominated, regardless of total field power. A powerful but unpredictable field (creative phase) appeared "dead." The corrected formula removes `|ε|²`:
$$
E = \frac{M^2}{M + \phi^{-2}}
$$
Prediction error `|ε|²` is a separate diagnostic — it distinguishes calm (low ε) from creative (high ε) states, both of which have high E.

### 8.2 Quantum potential stability

The QP division `∇²M^β / M^β` produces gradient `∝ 1/(M^β)²` which explodes for small `M^β`. The fix: clamp `M^β ≥ 10⁻²` in the denominator. In the differentiable formulation (future), use detached correction:
$$
Q = Q_{\text{stable}} + (Q_{\text{correct}} - Q_{\text{stable}}).\text{detach}()
$$

### 8.3 Field state accumulation

Persistent field state across 30,000+ PDE steps (33 epochs × 200 batches × 5 substeps) develops extreme spatial gradients that trigger GPU hardware exceptions. The fix: reset the field state at each epoch boundary. Within-epoch carryover is safe (200 batches × 5 substeps = 1000 steps).

---

This document is the formal foundation. Every parameter, loss term, and operation in the implementation should be directly traceable to one of these equations. If something in the code can't be expressed in terms of this formalism, it doesn't belong — remove it.
