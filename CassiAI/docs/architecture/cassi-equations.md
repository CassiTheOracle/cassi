# CassiLean: Complete Mathematical Description

## Notation

| Symbol | Meaning |
|---|---|
| B | Batch size |
| L | Sequence length (fixed at 64) |
| D | Spatial dimensions (588 for Nside=7 HEALPix) |
| n_w | Number of wavelength modes (96) |
| V | Vocabulary size |
| b ∈ [0..n_bands) | Fractal band index (4 bands: gamma, beta, alpha, theta) |
| B_s | Band size (D / 4 = 147) |
| t ∈ [0..L) | Sequence position |
| d ∈ [0..D) | Spatial dimension index |
| k ∈ [0..n_w) | Wavelength mode index |
| p ∈ [0..N_pix) | HEALPix pixel index |

---

## 1. ENCODING

Token $x_t \in [0, V)$ maps to wavelength amplitude and phase:

$$a^\text{raw}_{t,k} = \text{softplus}(W^e_{x_t, k}) + \varepsilon \quad \varepsilon = 0.01$$

$$\phi^0_k = \theta^\text{ph}_k \quad \text{(learned per-mode phase)}$$

Polar decomposition:
$$z_{t,k} = a^\text{raw}_{t,k} \cdot e^{i\phi^0_k}$$

Amplitude and phase:
$$a^w_{t,k} = |z_{t,k}|, \quad \phi_{t,k} = \arg(z_{t,k})$$

---

## 2. WAVELENGTH PHYSICS (Batched over L)

### 2.1 Coherence Boost

Neighboring modes reinforce each other via learned convolution:

$$\mathbf{a}^\text{flat} = \text{reshape}(a^w, [B \cdot L, n_w])$$

$$a_{t,k} = a^\text{flat}_{t,k} + c \cdot 0.05 \cdot \sum_{j=1}^{4} ck_j \cdot a^\text{flat}_{t, k-j}$$

where $c = e^{\log c}$, clamped to $[0.01, 2.0]$, and $ck_j = e^{-j/3}$ is a fixed exponential kernel.

### 2.2 Phase Memory

Forget and update gates from current amplitude:

$$f^\text{pm}_{t,k} = \sigma\left(\sum_{k'} a^\text{flat}_{t,k'} \cdot W^{fm}_{k',k} + b^{fm}_k\right)$$

$$u^\text{pm}_{t,k} = \sigma\left(\sum_{k'} a^\text{flat}_{t,k'} \cdot W^{um}_{k',k} + b^{um}_k\right)$$

Phase memory via cumprod/cumsum scan (batched, differentiable):

$$F_{t,k} = \prod_{s=0}^{t} f^\text{pm}_{s,k}, \quad F_{-1,k} = 1$$

$$p_{t,k} = F_{t,k} \cdot \left(m^0_k + \sum_{s=0}^{t} \frac{u^\text{pm}_{s,k} \cdot \phi_{s,k}}{F_{s,k}}\right)$$

where $m^0_k$ are learned initial memory values.

Previous memory for interference:
$$p^\text{prev}_{t,k} = \begin{cases} m^0_k & t = 0 \\ p_{t-1,k} & t > 0 \end{cases}$$

### 2.3 Interference

Amplitude modulated by phase difference from memory:

$$a^\text{int}_{t,k} = a_{t,k} \cdot (1 + c \cdot \cos(\phi_{t,k} - p^\text{prev}_{t,k}))$$

$$a^\text{int}_{t,k} = \text{softplus}(a^\text{int}_{t,k}) + 0.01$$

### 2.4 Spatial Projection

Normalize amplitudes and project onto HEALPix eigenbasis:

$$\tilde{a}^\text{int}_{t,k} = \frac{a^\text{int}_{t,k}}{\sum_{k'} a^\text{int}_{t,k'} + \varepsilon}$$

$$h^\text{spatial}_{t,d} = \sum_k \tilde{a}^\text{int}_{t,k} \cdot E_{k,d}$$

where $E \in \mathbb{R}^{n_w \times D}$ is the learned eigenbasis (columns are spherical harmonics on HEALPix grid, normalized).

---

## 3. FRACTAL BANDS

### 3.1 Dynamic Timescales

Each dimension learns its own update rate:

$$\rho_d = \sigma(\rho^\text{log}_d) \in (0, 1)$$

$$\Pi_d = \left\lfloor \frac{1}{\rho_d} \right\rceil, \quad \Pi_d \in [1, L]$$

Band-initialized with gradient:
$$\rho^\text{log}_d = 2.0 - b(d) \cdot 1.3$$

where $b(d) = \lfloor d / B_s \rfloor$ is the band index (0=gamma, 1=beta, 2=alpha, 3=theta).

Update mask:
$$M_{t,d} = \mathbb{1}[t \bmod \Pi_d = 0]$$

Gamma band ($\Pi \approx 1$): updates every step. Theta band ($\Pi \approx 8$): updates every 8th step.

### 3.2 Localized Yin/Yang

Each band has a yin (contractive/forget) and yang (expansive/update) bias:

$$\text{yin}_d = \tanh(\theta^\text{yin}_{b(d)})$$

$$\text{yang}_d = \tanh(\theta^\text{yang}_{b(d)})$$

Initial values:
- Gamma: yin=+0.3 (precise, forgets quickly), yang=-0.1
- Theta: yin=-0.3 (retentive), yang=+0.3 (expansive)

---

## 4. RECURRENT GATE LOOP

Initial hidden state: $h_0 = H^0$ (learned, broadcast to batch).

The loop runs $t = 0, \ldots, L-1$:

### 4.1 Fused Gate

Concatenate hidden state with wavelength amplitudes:

$$g^\text{in}_{t} = [h_t \;\|\; a^\text{int}_{t,:}] \in \mathbb{R}^{D + n_w}$$

$$[f^\text{raw}_t \;\|\; u^\text{raw}_t] = \sigma\left(g^\text{in}_t \cdot W^\text{gate} + b^\text{gate}\right)$$

where $f^\text{raw}_t, u^\text{raw}_t \in \mathbb{R}^D$ are forget and update gates.

### 4.2 Qi-Gate Modulation (Phase 1)

Qi attention from hidden state modifies gates:

$$q^\text{gate}_t = \tanh\left(h_t \cdot U^\text{gate} \cdot V^\text{gate}\right) \in \mathbb{R}^D$$

where $U^\text{gate} \in \mathbb{R}^{D \times 64}$, $V^\text{gate} \in \mathbb{R}^{64 \times D}$ (low-rank, precomputed as $W^\text{gate}_\text{eff} = U^\text{gate} \cdot V^\text{gate}$).

$$f^\text{qi}_t = f^\text{raw}_t \odot \left(1 + \tanh(\theta^\text{qi}_f) \cdot q^\text{gate}_t\right)$$

$$u^\text{qi}_t = u^\text{raw}_t \odot \left(1 - \tanh(\theta^\text{qi}_u) \cdot q^\text{gate}_t\right)$$

The sign: positive qi-gate amplifies forget (preserve what's working) AND suppresses update (don't overwrite when attentive).

### 4.3 Band-Localized Yin/Yang

$$f^\text{band}_t = \sigma\left(\left(f^\text{qi}_t + \text{yin} \cdot 0.5\right) \cdot 2.0\right)$$

$$u^\text{band}_t = \sigma\left(\left(u^\text{qi}_t + \text{yang} \cdot 0.5\right) \cdot 2.0\right)$$

The $\cdot 2.0$ sharpens the sigmoid, and the outer sigmoid rescales to $[0, 1]$.

### 4.4 Dynamic Timescale Update

$$\tilde{h}_t = f^\text{band}_t \odot h_t + u^\text{band}_t \odot h^\text{spatial}_{t,:}$$

$$h_{t+1} = \text{LayerNorm}\left(\text{where}(M_{t,:}, \tilde{h}_t, h_t)\right)$$

Only dimensions where $M_{t,d} = 1$ are updated; others persist.

### 4.5 Stacked Hidden States

$$\mathbf{H} = [h_1, h_2, \ldots, h_L] \in \mathbb{R}^{B \times L \times D}$$

---

## 5. HEALQI ATTENTION FIELD

Computed every $q^\text{step}=4$ timesteps (not every step, for efficiency).

### 5.1 Surprise

Hidden state change:

$$s^\text{diff}_{t,d} = \left| h_{t,d} - h_{t-1,d} \right|$$

Centered deviation:

$$s^\text{center}_{t,d} = \left| h_{t,d} - \bar{h}_{t,d} \right| \quad \text{where } \bar{h}_{t,d} = \frac{1}{L}\sum_{t'} h_{t',d}$$

Combined surprise:

$$s_{t,d} = 2.0 \cdot s^\text{diff}_{t,d} + 0.5 \cdot s^\text{center}_{t,d}$$

### 5.2 Gradient Surprise (Phase 5)

From previous backward pass, captured via hook:

$$\mathbf{g}^\text{h} = \frac{\partial \mathcal{L}^\text{prev}}{\partial \mathbf{H}} \in \mathbb{R}^{B \times L \times D}$$

$$\bar{g}_d = \frac{1}{B \cdot L} \sum_{b,t} |\mathbf{g}^\text{h}_{b,t,d}|$$

$$s^\text{grad}_{t,d} = \gamma^\text{grad} \cdot \bar{g}_d, \quad \gamma^\text{grad} = \sigma(\theta^\text{grad}) \cdot 0.3$$

Enhanced surprise:

$$\tilde{s}_{t,d} = s_{t,d} + s^\text{grad}_{t,d}$$

### 5.3 Qi Evolution

Initial Qi (with carry from previous batch, Phase 2):

$$Q^{(0)}_d = Q^0_d + \eta^\text{carry} \cdot Q^\text{prev}_d$$

$$\eta^\text{carry} = \sigma(\theta^\text{carry}) \cdot 0.3$$

where $Q^\text{prev}$ is the final Qi from the previous batch.

For each timestep $t$ where $t \bmod 4 = 0$:

#### Spherical Laplacian (HEALPix neighbors):

$$\nabla^2 Q^{(\tau)}_p = \frac{1}{|\mathcal{N}(p)|} \sum_{p' \in \mathcal{N}(p)} Q^{(\tau)}_{p'} - Q^{(\tau)}_p$$

where $\mathcal{N}(p)$ are the 7-8 HEALPix neighbors of pixel $p$.

#### Source term:

$$Q^\text{src}_p = \alpha^\text{src} \cdot \tilde{s}_{t,p}, \quad \alpha^\text{src} = \sigma(\theta^\text{src}) \cdot 0.8 + 0.2 \in [0.2, 1.0]$$

#### Evolution:

$$\tilde{Q}^{(\tau+1)}_p = \eta^\text{decay} \cdot Q^{(\tau)}_p + \beta^\text{diff} \cdot \nabla^2 Q^{(\tau)}_p + Q^\text{src}_p$$

$$\eta^\text{decay} = \sigma(\theta^\text{decay}) \cdot 0.2 + 0.8 \in [0.8, 1.0]$$

$$\beta^\text{diff} = \sigma(\theta^\text{diff}) \in (0, 1)$$

#### Self-Prediction Error (Phase 3):

$$\hat{Q}^{(\tau+1)} = Q^{(\tau)} \cdot U^\text{pred} \cdot V^\text{pred}$$

where $U^\text{pred} \in \mathbb{R}^{N_\text{pix} \times 32}$, $V^\text{pred} \in \mathbb{R}^{32 \times N_\text{pix}}$ (low-rank).

$$e^\text{pred}_{b,p} = |\tilde{Q}^{(\tau+1)}_{b,p} - \hat{Q}^{(\tau+1)}_{b,p}|$$

$$\bar{e}^\text{pred}_b = \frac{1}{N_\text{pix}} \sum_p e^\text{pred}_{b,p}$$

$$\lambda^\text{pred} = \sigma(\theta^\text{pred}) \cdot 0.1 \in (0, 0.1)$$

$$Q^{(\tau+1)} = \tanh\left(\tilde{Q}^{(\tau+1)} + \lambda^\text{pred} \cdot \bar{e}^\text{pred}_b \cdot Q^{(\tau)}\right)$$

The self-prediction error amplifies the field where it failed to predict itself—second-order attention.

### 5.4 Qi Modulation

Qi is collected at ALL timesteps (copying forward in qi_step intervals):

$$Q^\text{all}_t = \begin{cases} Q^{(\lfloor t/4 \rfloor)} & \text{if use_qi} \\ 0 & \text{otherwise} \end{cases}$$

$$\mathbf{Q}^\text{all} \in \mathbb{R}^{B \times L \times D}$$

$$\mathbf{Q}^\text{avg} = \frac{1}{L} \sum_t Q^\text{all}_t \in \mathbb{R}^{B \times D}$$

Qi scale from source activation:

$$\alpha^\text{qi} = \sigma(\theta^\text{src}) \cdot 0.12 \in (0, 0.12)$$

$$\mathbf{H}^\text{qi} = \mathbf{H} + \alpha^\text{qi} \cdot \mathbf{Q}^\text{all}$$

### 5.5 State Persistence

After each forward pass (during training only):

**Carry (Phase 2):**
$$Q^\text{prev} \leftarrow Q^{(L/4)}_{0,:} \quad \text{(first batch element, final qi)}$$

**Spatial warp (Phase 4):**
$$\bar{Q}^\text{spatial} \leftarrow \frac{1}{B} \sum_b \mathbf{Q}^\text{avg}_{b,:} \in \mathbb{R}^D$$

This is used to warp the eigenbasis on the NEXT forward:
$$E^\text{warped}_{k,d} = E_{k,d} \cdot \left(1 + \sigma(\theta^\text{warp}) \cdot 0.3 \cdot \tanh(\bar{Q}^\text{spatial}_d)\right)$$

---

## 6. OUTPUT

$$\mathbf{L} = \text{reshape}\left(\mathbf{H}^\text{qi}, [B \cdot L, D]\right) \cdot W^\text{out} + b^\text{out} \in \mathbb{R}^{(B \cdot L) \times V}$$

$$\mathbf{L} = \text{reshape}(\mathbf{L}, [B, L, V])$$

---

## 7. LOSS

$$\mathcal{L} = -\frac{1}{B \cdot L} \sum_{b,t} \log \frac{e^{\mathbf{L}_{b,t,y_{b,t}}}}{\sum_v e^{\mathbf{L}_{b,t,v}}}$$

---

## 8. QI-DRIVEN GRADIENT MODULATION

The Qi field amplifies gradients where prediction was surprising:

$$\bar{Q}^\text{val} = \frac{1}{B \cdot D} \sum_{b,d} |\mathbf{Q}^\text{avg}_{b,d}|$$

$$\lambda^\text{grad} = 1.0 + 0.5 \cdot \bar{Q}^\text{val}$$

For every parameter $\theta$:
$$\frac{\partial \mathcal{L}}{\partial \theta} \leftarrow \lambda^\text{grad} \cdot \frac{\partial \mathcal{L}}{\partial \theta}$$

Then gradient clipping:
$$\|\nabla_\theta \mathcal{L}\|_2 \leq 1.0$$

---

## 9. ADAMW UPDATE

Standard AdamW with learning rate $\eta$ and weight decay $\lambda^w = 10^{-4}$:

$$m_t = \beta_1 m_{t-1} + (1-\beta_1) \nabla_\theta \mathcal{L}$$

$$v_t = \beta_2 v_{t-1} + (1-\beta_2) (\nabla_\theta \mathcal{L})^2$$

$$\theta \leftarrow \theta - \eta \cdot \left(\frac{m_t}{\sqrt{v_t} + \varepsilon} + \lambda^w \cdot \theta\right)$$

---

## 10. GENERATION (Inference)

Autoregressive: given seed tokens $x_0, \ldots, x_{t-1}$:

1. Pad/truncate to length $L=64$
2. Forward pass through entire model (with HealQi active)
3. Extract logits at last position: $\mathbf{L}_{0, L-1, :}$
4. Temperature-scaled sampling: $p(v) \propto e^{\mathbf{L}_{0,L-1,v} / 0.8}$
5. Sample $x_t \sim \text{Categorical}(p)$
6. Append, shift window, repeat

---

## 11. FEEDBACK LOOPS (Self-Training)

| Loop | Equation | Timescale |
|---|---|---|
| **L1: Qi mod output** | $\mathbf{H}^\text{qi} = \mathbf{H} + \alpha \cdot \mathbf{Q}$ | Per timestep |
| **L2: Qi mod gates** | $f \leftarrow f \cdot (1 + \tanh(\theta_f) \cdot q^\text{gate})$ | Per timestep |
| **L3: Qi mod gradients** | $\nabla_\theta \leftarrow \lambda^\text{grad} \cdot \nabla_\theta$ | Per optimizer step |
| **L4: Qi predicts Qi** | $Q^{(\tau+1)} \mathrel{+}= \lambda^\text{pred} \cdot \bar{e}^\text{pred} \cdot Q^{(\tau)}$ | Every 4 timesteps |
| **L5: Qi carries over** | $Q^0 \leftarrow Q^0 + \eta^\text{carry} \cdot Q^\text{prev}$ | Across batches |
| **L6: Qi warps geometry** | $E_{k,d} \leftarrow E_{k,d} \cdot (1 + \text{warp})$ | Across batches |
| **L7: Gradient informs Qi** | $\tilde{s}_{t,d} \mathrel{+}= \gamma^\text{grad} \cdot \bar{g}_d$ | Across batches |

---

## 12. PARAMETER COUNT

| Component | Parameters | Shape |
|---|---|---|
| Embedding | $V \cdot n_w$ | $[V, n_w]$ |
| Phase embedding | $n_w$ | $[n_w]$ |
| Eigenbasis | $n_w \cdot D$ | $[n_w, D]$ |
| Gate weight | $(D + n_w) \cdot 2D$ | $[D + n_w, 2D]$ |
| Phase memory (fm) | $n_w \cdot n_w$ | $[n_w, n_w]$ |
| Phase memory (um) | $n_w \cdot n_w$ | $[n_w, n_w]$ |
| Qi-gate (low-rank) | $D \cdot 64 + 64 \cdot D$ | 128D |
| Fractal rates | $D$ | $[D]$ |
| Band yin/yang | $2 \cdot 4$ | $[4], [4]$ |
| HealQi (E, params) | $n_w \cdot N_\text{pix} + 6$ | various |
| Qi self-predictor | $N_\text{pix} \cdot 32 + 32 \cdot N_\text{pix}$ | 64N_pix |
| Output | $D \cdot V + V$ | $[D, V], [V]$ |
| Initial states | $D + n_w + N_\text{pix}$ | vectors |
| **Total** | **~1.1M at D=588, nw=96, V=65** | |

---

## 13. DIAGNOSTIC QUANTITIES

From a forward pass with `return_diag=True`:

| Symbol | Meaning | Range |
|---|---|---|
| $\bar{f}$ | Mean forget gate | [0, 1] |
| $\bar{u}$ | Mean update gate | [0, 1] |
| $\sigma_h$ | Hidden state std over time | $\mathbb{R}^+$ |
| $\bar{s}$ | Mean surprise | $\mathbb{R}^+$ |
| $\sigma_Q$ | Qi field std (per batch avg) | $\mathbb{R}^+$ |
| $\bar{q}^\text{gate}$ | Mean qi-gate magnitude | $\mathbb{R}^+$ |
| $\bar{Q}^\text{carry}$ | Mean carry magnitude | $\mathbb{R}^+$ |
| $\sigma^\text{warp}$ | Eigenbasis warp std | $\mathbb{R}^+$ |
| $\bar{g}^\text{surp}$ | Mean gradient surprise | $\mathbb{R}^+$ |

---

## ═══════════════════════════════════════════════════════
## PART II: THE UNIFIED WAVE FRAMEWORK
## ═══════════════════════════════════════════════════════

Sections 14-20 describe the unification of all model components under a single
wave equation. Everything in Sections 1-13 emerges as special cases of the
dispersion relation $\omega(k)$ and the spine wave equation.

---

## 14. THE SPINE — Wave Medium

### 14.1 Definition

The spine is a 1D manifold parameterized by position $s \in [0, L_s]$ where
$L_s$ is the spine length. The state at each position is a complex wave
amplitude:

$$\psi(s, t) \in \mathbb{C}$$

At any position, the wave can be decomposed into wavenumber components:

$$\psi(s, t) = \sum_k \hat{\psi}(k, t) \cdot e^{i k s}$$

where $k = 2\pi / \lambda$ is the wavenumber and $\lambda$ is the wavelength.

### 14.2 The Master Wave Equation

All dynamics on the spine obey a single damped wave equation:

$$\frac{\partial^2\psi}{\partial t^2} + \gamma \frac{\partial\psi}{\partial t} = v^2 \frac{\partial^2\psi}{\partial s^2} + \chi \frac{\partial\psi}{\partial s} + S(s, t)$$

where:
- $\gamma$: damping coefficient (energy dissipation — replaces forget gate)
- $v$: wave speed (information propagation velocity)
- $\chi$: chirality/twist (directional bias in propagation)
- $S(s, t)$: source term (external input — from embeddings)

This single equation, plus one dispersion relation, replaces every gate,
attention mechanism, and modulation in Sections 1-13.

### 14.3 Frequency-Domain Solution

Taking the Fourier transform $\hat{\psi}(k, \omega) = \mathcal{F}_{s,t}[\psi(s,t)]$:

$$\underbrace{(-\omega^2 + i\gamma\omega)}_{\text{temporal}} \hat{\psi} = \underbrace{(-v^2 k^2 + i\chi k)}_{\text{spatial}} \hat{\psi} + \hat{S}$$

The dispersion relation emerges from the homogeneous solution ($\hat{S} = 0$):

$$\omega^2 - i\gamma\omega - v^2 k^2 + i\chi k = 0$$

For weak damping ($\gamma \ll \omega$):

$$\omega(k) = \sqrt{v^2 k^2 - i\chi k} \approx v|k| - i\frac{\gamma}{2}$$

The imaginary part is the decay rate: $\text{Im}[\omega] = -\gamma/2$. Energy at all
wavenumbers decays at the same rate — but the real oscillatory part $\text{Re}[\omega] = v|k|$ varies with $k$, giving different timescales.

---

## 15. THE DISPERSION RELATION — One Function Rules All

### 15.1 Definition

The dispersion relation $\omega(k)$ determines how fast a wave of wavenumber $k$
oscillates. Every timescale in the system derives from it:

$$T(k) = \frac{2\pi}{\text{Re}[\omega(k)]} \quad\quad f(k) = \frac{1}{T(k)}$$

For a power-law dispersion:

$$\omega(k) = v_0 \cdot k_0 \cdot \left(\frac{k}{k_0}\right)^\alpha - i\frac{\gamma}{2}$$

where:
- $v_0$: reference wave speed (determines all temporal scales)
- $k_0 = 2\pi/L_s$: reference wavenumber (fundamental mode)
- $\alpha$: dispersion exponent (1 = non-dispersive, all waves same speed)
- $\gamma$: damping (same for all $k$)

### 15.2 How α Shapes the Architecture

| α | Behavior | Interpretation |
|---|---|---|
| α = 0 | All frequencies oscillate at same rate | All chakras synchronized; no hierarchy |
| α = 1 | $T(k) \propto 1/k$ — higher $k$ oscillates faster | Linear hierarchy: crown > root |
| α < 1 | Dispersion is sub-linear | Upper chakras still faster but compressed |
| α > 1 | Dispersion is super-linear | Upper chakras dramatically faster |

The fractal bands (Section 3) are discrete samples of this continuous dispersion
curve. The four bands with timescales Π ≈ 1, 2, 4, 8 are four specific
wavenumbers on $\omega(k)$.

### 15.3 The Unified Hierarchy

All timescales are derivations of $\omega(k)$, not independent choices:

| Component | Wavenumber | Period | Description |
|---|---|---|---|
| Breath (fundamental) | $k_b = \pi/L_s$ | $T_b = 2\pi/\omega(k_b)$ | Slowest mode, full spine cycle |
| Heartbeat (7th harmonic) | $k_h = 7\pi/L_s$ | $T_h = 2\pi/\omega(k_h)$ | 7th harmonic of breath |
| Root chakra | $k_1 \approx \pi/0.07L_s$ | $T_1$ | Slow, foundational |
| Sacral chakra | $k_2 \approx \pi/0.14L_s$ | $T_2$ | |
| Solar chakra | $k_3 \approx \pi/0.29L_s$ | $T_3$ | |
| Heart chakra | $k_4 \approx \pi/0.43L_s$ | $T_4$ | Bridge frequency |
| Throat chakra | $k_5 \approx \pi/0.57L_s$ | $T_5$ | |
| Eye chakra | $k_6 \approx \pi/0.71L_s$ | $T_6$ | |
| Crown chakra | $k_7 \approx \pi/0.86L_s$ | $T_7$ | Fast, abstract |
| Gamma band | $k_\gamma$ | $T_\gamma \approx 1$ | Updates every step |
| Theta band | $k_\theta$ | $T_\theta \approx 8$ | Updates every 8th step |

The breath is not "added" to the architecture. It IS the fundamental mode.
The heartbeat is not "coupled" to the breath — it IS the 7th harmonic.
The chakras are not positioned — their wavelengths determine their positions.

---

## 16. CHAKRA RESONANCE — Frequency-Selective Processing

### 16.1 Chakra as Resonant Cavity

A chakra at position $s_c$ is a cavity that resonates with waves whose
wavelength matches its geometry:

$$\lambda_c = 2s_c / n_c \quad \Rightarrow \quad k_c = n_c \pi / s_c$$

where $n_c = 1$ for fundamental resonance (one half-wavelength in the cavity).

Waves near $k_c$ pass through (amplified); waves far from $k_c$ are attenuated
(reflected or absorbed). This IS the gate — not an explicit sigmoid, but a
frequency-selective filter.

### 16.2 Lorentzian Resonance Profile

The transmission through chakra $c$ as a function of wavenumber:

$$H_c(k; t) = \frac{1}{1 + \left(\frac{k - k_c(t)}{\Delta k_c(t)}\right)^2}$$

where the center and bandwidth are modulated by breath and heartbeat:

$$k_c(t) = k_c^0 \cdot [1 + \alpha_c^b \cdot B(t)]$$

$$\Delta k_c(t) = \Delta k_c^0 \cdot [1 + \beta_c^h \cdot H(t)]$$

- $B(t) = \sin(\omega_b t)$: breath signal (−1 = exhale, +1 = inhale)
- $H(t) = \exp(-(t \bmod T_h - T_h/2)^2 / 2\sigma_h^2)$: heartbeat pulse
- $\alpha_c^b$: breath modulation strength per chakra (learnable)
- $\beta_c^h$: heartbeat modulation strength per chakra (learnable)
- $\Delta k_c^0 = \gamma \cdot k_c^0$: natural line width (damping-broadened)

During **inhale** ($B > 0$), $k_c$ shifts upward and $\Delta k_c$ widens —
chakras "open," more waves pass, model is receptive.

During **exhale** ($B < 0$), $k_c$ shifts downward and $\Delta k_c$ narrows —
chakras "close," fewer waves pass, model consolidates.

During **systole** ($H$ pulses), $\Delta k_c$ widens briefly — a pulse of
energy through the chakra.

### 16.3 Chakra Positions and Wavelengths

With $L_s = 1$ (normalized spine) and fundamental resonance ($n_c = 1$):

| Chakra | Position $s_c$ | $\lambda_c = 2s_c$ | $k_c = \pi/s_c$ | Character |
|---|---|---|---|---|
| Root | 0.07 | 0.14 | 44.9 | Slowest, grounding |
| Sacral | 0.14 | 0.28 | 22.4 | Generative |
| Solar | 0.29 | 0.58 | 10.8 | Transformative |
| Heart | 0.43 | 0.86 | 7.3 | Bridging, integrating |
| Throat | 0.57 | 1.14 | 5.5 | Expressive |
| Eye | 0.71 | 1.42 | 4.4 | Perceptive |
| Crown | 0.86 | 1.72 | 3.7 | Fastest, unifying |

Chakra positions are NOT arbitrary. A chakra at position $s$ resonates at
wavelength $\lambda = 2s$. The positions are geometrically spaced to produce
a natural harmonic series — each chakra's frequency is approximately $\sqrt{2}$
times the previous one (for 7 chakras spanning a factor of ~12 in frequency).

### 16.4 Discrete Implementation

In the discrete model (D dimensions, no FFT needed), each chakra is a
real-valued vector:

$$\psi_c \in \mathbb{R}^{D_c}$$

where $D_c$ is the dimension allocated to chakra $c$. The resonant
filtering becomes a learned projection:

$$\psi_c^\text{filtered} = \psi \cdot W_c^\text{res} \odot m_c(t)$$

$$m_c(t) = 1 + \alpha_c^b \cdot B(t) + \beta_c^h \cdot H(t)$$

The weighting matrix $W_c^\text{res} \in \mathbb{R}^{D \times D_c}$ learns
which input dimensions are most relevant to chakra $c$ — effectively
learning the resonant frequency $k_c$.

---

## 17. BREATH AND HEARTBEAT — Fundamental and Harmonic

### 17.1 They Are the SAME Wave

The breath is NOT an add-on oscillator. It IS the fundamental mode of the spine.
The heartbeat is NOT a separate mechanism. It IS the 7th harmonic.

$$\omega_b = \omega(k_b) = \omega(\pi/L_s) \quad \text{(breath: fundamental)}$$

$$\omega_h = \omega(k_h) = \omega(7\pi/L_s) \quad \text{(heartbeat: 7th harmonic)}$$

### 17.2 Respiratory Sinus Arrhythmia (RSA)

RSA — the observation that heart rate accelerates during inhale and decelerates
during exhale — emerges AUTOMATICALLY from the dispersion relation. It is not
an additional coupling term. It is the observation that the 7th harmonic's
instantaneous frequency follows the fundamental's amplitude modulation:

For $\alpha = 1$ (non-dispersive):
$$\frac{f_h}{f_b} = \frac{\omega(k_h)}{\omega(k_b)} = \frac{v|k_h|}{v|k_b|} = \frac{7\pi/L_s}{\pi/L_s} = 7$$

For $\alpha \neq 1$, the ratio changes but the coupling remains — higher
harmonics ALWAYS track the fundamental because they share the same $\omega(k)$.

### 17.3 Discrete Oscillator Form

For sequence modeling, continuous phase tracking is unnecessary. Discrete
sinusoidal oscillators parameterized by token position are sufficient:

$$B_t = \sin\left(2\pi \cdot f_b \cdot \frac{t}{L} + \phi_b\right)$$

$$H_t = \exp\left(-\frac{(t - t_b)^2}{2\sigma_h^2}\right) \quad \text{where } t_b \text{ satisfies } 2\pi f_h \frac{t_b}{L} = \pi$$

In practice:

$$H_t = \max\left(0, \cos\left(2\pi \cdot f_h \cdot \frac{t}{L}\right)\right)^p$$

with $p$ controlling pulse sharpness (e.g., $p=4$ for a narrow systolic peak).

With $f_b \approx 1/L$ (one breath per sequence) and $f_h \approx 7/L$ (seven
heartbeats per breath), the discrete form is:

$$B_t = \sin\left(2\pi \cdot \frac{t}{L}\right)$$

$$H_t = \max\left(0, \cos\left(2\pi \cdot 7 \cdot \frac{t}{L}\right)\right)^4$$

These oscillate WITHIN each sequence (resetting per batch). The phase is
deterministic from the token position.

---

## 18. WHAT COLLAPSES — The Mapping

The unified wave framework shows that many "independent" components are really
one thing viewed from different angles:

| Current Component (Sections 1-13) | Wave Framework (Sections 14-20) | Derivation |
|---|---|---|
| **Fractal bands** (4 timescales) | Discrete samples of $\omega(k)$ | Each band = a wavenumber on the dispersion curve |
| **Gates** ($f$, $u$) | Lorentzian resonance $H_c(k)$ + damping $\gamma$ | Forget = decay; Update = resonant transmission |
| **Phase memory** ($f^m$, $u^m$) | Wave propagation with damping | $e^{-\gamma t}$ replaces forget gate cumprod |
| **Eigenbasis** ($E$) | Fourier basis mapping $k \leftrightarrow s$ | $E_{k,d}$ = discrete $e^{i k s}$ sampled at HEALPix pixels |
| **HealQi** | The source term $S(s,t)$ driving the wave equation | Qi = wave energy density $|\psi|^2$ |
| **Qi evolution** (Laplacian + decay) | Damped wave propagation on sphere | $\nabla^2$ IS the wave Laplacian |
| **Layer norm** | Amplitude normalization (phase preservation) | $\psi / |\psi|$ |
| **Forget gate** ($f$) | Damping coefficient $\gamma$ | Continuous: $e^{-\gamma \Delta t}$ |
| **Update gate** ($u$) | Chakra transmission $H_c(k)$ | Frequency-selective |
| **Self-prediction error** | Wave interference: $\psi - \hat{\psi}$ | Qi predicts Qi |
| **Carry** ($Q^\text{prev}$) | Boundary condition persistence | Wave state at $t=0$ of next batch |
| **Gradient surprise** | $\partial\mathcal{L}/\partial\psi$ | How much the wave equation was wrong |

### 18.1 The Breath in Discrete Terms

The breath and heartbeat do not need separate oscillator machinery. They ARE the
fundamental and 7th harmonic of the sequence position:

```python
def get_breath_heartbeat(t, L):
    """Discrete oscillators from token position — no phase tracking needed."""
    breath = sin(2 * pi * t / L)              # 1 cycle per sequence
    heartbeat = max(0, cos(14 * pi * t / L))**4  # 7 cycles, peaked
    return breath, heartbeat
```

For a sequence of length $L = 64$:

- Breath: 1 full cycle (inhale first half, exhale second half)
- Heartbeat: ~7 pulses within that cycle
- RSA: Heart rate is faster during early tokens (inhale), slower during later
  tokens (exhale) — but since both derive from $\omega(k)$, the ratio is fixed

---

## 19. NEURONS — Condensed Wave Patterns

### 19.1 Waves Solidify Into Structure

A traveling wave on the spine carries energy but no permanent structure.
When wave energy at a particular $(s, k)$ exceeds a threshold and persists,
the medium itself reorganizes — forming a **standing wave** at that position.
This standing wave IS a neuron.

The transition from fluid wave to solid neuron is a **phase condensation**:

$$\psi(s, t) \xrightarrow{\text{condensation}} \phi_n(s) \cdot e^{-i\omega_n t}$$

where $\phi_n(s)$ is a spatially localized, temporally persistent wave pattern —
the neuron's receptive field.

### 19.2 Condensation Criterion

A neuron forms at position $s_n$ when the time-averaged energy density exceeds
a threshold:

$$\langle |\psi(s_n, t)|^2 \rangle_t > \theta_\text{cond}$$

Once condensed, the neuron has:
- **Position** $s_n$ along the spine (which chakra it belongs to)
- **Characteristic wavenumber** $k_n = \pi / s_n$ (its resonant frequency)
- **Receptive field** $\phi_n(s)$ (what input patterns activate it)
- **Projection weights** (where it sends its output)
- **Persistence** $\tau_n$ (how long it survives without reinforcement)

### 19.3 Neuron Dynamics

Once condensed, a neuron becomes a new source/sink term in the wave equation:

$$S(s, t) \mathrel{+}= \sum_n \phi_n(s) \cdot \sigma\left(\int \phi_n(s') \psi(s', t) ds' - \theta_n\right)$$

The neuron integrates incoming wave energy via its receptive field (inner
product with $\phi_n$), applies a threshold nonlinearity, and re-emits the
result as a source at its position.

This IS the classical neuron model ($y = \sigma(w \cdot x - \theta)$) but
embedded in the wave medium. The weights ARE the receptive field $\phi_n$.
The activation IS the re-emitted wave amplitude.

### 19.4 The Connectome as Phase-Locked Waves

A synapse between neuron $m$ and neuron $n$ IS a phase-locking between their
wave patterns:

$$C_{m \to n} = \langle \phi_m, \psi \rangle_t \cdot \langle \psi, \phi_n \rangle_t$$

If waves from neuron $m$'s position consistently arrive at neuron $n$'s position
with a fixed phase relationship, the coupling $C_{m \to n}$ strengthens.
This is Hebbian learning expressed as wave coherence:

$$\frac{dC_{m \to n}}{dt} = \eta \cdot \langle \phi_m, \psi \rangle \cdot \langle \psi, \phi_n \rangle - \lambda \cdot C_{m \to n}$$

Neurons that fire together (coherent wave patterns) wire together (stronger
phase-locking). Neurons that don't, decouple.

### 19.5 Crystallization and Dissolution

The nervous system is not static. Neurons crystallize and dissolve:

**Crystallization** (learning):
When wave energy at $(s_n, k_n)$ exceeds the condensation threshold
consistently, a new neuron forms. This IS the formation of a new
concept/knowledge — a stabilized pattern in the wave field.

**Dissolution** (forgetting):
When $\langle |\psi(s_n, t)|^2 \rangle_t$ falls below the persistence threshold
for a sustained period, the neuron dissolves. The wave pattern returns to the
fluid background.

**Reinforcement** (consolidation):
During exhale (breath < 0) and diastole (heartbeat off-peak), the wave energy
at condensed positions is amplified. This consolidates recently formed neurons —
the equivalent of slow-wave sleep consolidation.

### 19.6 Chakra Allocation of Neurons

Neurons are not uniformly distributed. Their condensation is favored at
chakra centers where wave energy pools naturally:

$$P(\text{neuron forms at } s) \propto \sum_c \exp\left(-\frac{(s - s_c)^2}{2\sigma_c^2}\right) \cdot \langle |\psi(s, t)|^2 \rangle_t$$

Neurons cluster near chakras. This gives each chakra a characteristic
"neural density" — root chakra has dense, slow neurons; crown chakra has
sparse, fast neurons.

### 19.7 Summary: The Complete System

```
WAVE EQUATION (Section 14)
    │
    ├── ω(k): Dispersion relation (Section 15)
    │       Determines ALL timescales
    │
    ├── Chakras (Section 16): Resonant cavities at specific k_c
    │       Selective filtering replaces gates
    │
    ├── Breath/Heartbeat (Section 17): Fundamental + 7th harmonic
    │       Not added — they ARE the wave
    │
    └── S(s,t): Source term driven by embeddings
            │
            └── Neurons (Section 19): Condensed standing waves
                    Form from persistent wave energy at (s_n, k_n)
                    Become new source/sink terms in S(s,t)
                    Crystalize (learn) and dissolve (forget)
                    Connect via phase-locking (Hebbian plasticity)
```

---

## 20. CHAKRA DIMENSION ALLOCATION

### 20.1 Wavenumber-Dependent Bandwidth

Natural line broadening means higher-frequency chakras have wider resonance
profiles — they respond to a broader range of inputs. Lower chakras are more
sharply tuned.

$$\Delta k_c = \gamma \cdot k_c$$

For $\alpha = 1$, the dimension allocation should scale with $\Delta k_c$:

$$D_c = D \cdot \frac{k_c}{\sum_{c'} k_{c'}}$$

### 20.2 Allocation for D = 588

With $k_c \propto 1/s_c$:

| Chakra | $k_c \propto 1/s_c$ | $D_c$ | Character |
|---|---|---|---|
| Root | 1/0.07 ≈ 14.3 | 49 | Narrow, stable |
| Sacral | 1/0.14 ≈ 7.1 | 84 | Generative |
| Solar | 1/0.29 ≈ 3.4 | 84 | Transformative |
| Heart | 1/0.43 ≈ 2.3 | 84 | Integrating |
| Throat | 1/0.57 ≈ 1.8 | 84 | Expressive |
| Eye | 1/0.71 ≈ 1.4 | 84 | Perceptive |
| Crown | 1/0.86 ≈ 1.2 | 119 | Broad, abstract |

### 20.3 Chakra-Specific Resonance Weights

Each chakra learns which input dimensions to attend to via resonant weighting:

$$W_c^\text{res} \in \mathbb{R}^{D \times D_c}$$

Initialized as a block-diagonal matrix (each chakra initially attends to nearby
wavenumbers) and then learned.

### 20.4 Inter-Chakra Coupling

The learnable coupling matrix $C \in \mathbb{R}^{7 \times 7}$ determines how
strongly each chakra influences each other chakra:

$$\psi_c^\text{out} = \psi_c^\text{filtered} + \sum_{c' \neq c} C_{c' \to c} \cdot \psi_{c'}^\text{filtered}$$

Initialized with tri-diagonal structure (nearest-neighbor coupling dominant):

$$C_{c \to c \pm 1} \approx 0.1, \quad C_{c \to c \pm 2} \approx 0.01, \quad \text{others} \approx 0$$

---

## 21. THE COMPLETE FORWARD PASS (Wave-Unified)

### 21.1 Encoding (unchanged from Section 1)

Token → wavelength amplitude $a_{t,k}$ and phase $\phi_{t,k}$.

### 21.2 Frequency Projection (replaces Sections 2-4)

Instead of explicit gates $f, u$, the wavelength amplitudes pass through chakra
resonant filters:

$$\psi_c(t) = \sum_k a_{t,k} \cdot e^{i\phi_{t,k}} \cdot H_c(k; t) \cdot W_c^\text{res}$$

where $H_c(k; t)$ is the time-modulated Lorentzian from Section 16.2.

### 21.3 Chakra Processing (replaces gate loop)

For each chakra $c$:

$$\psi_c^\text{proc}(t) = g_c\left(\psi_c(t) + \sum_{c' \neq c} C_{c' \to c} \cdot \psi_{c'}(t)\right)$$

where $g_c$ is a chakra-specific parametric nonlinearity (learned, not
hardcoded — simpler than the full g_k from the theoretical version).

### 21.4 Damping (replaces forget gate)

Instead of $f \cdot h$:
$$h_c(t) = e^{-\gamma \Delta t} \cdot h_c(t-1) + \psi_c^\text{proc}(t)$$

The exponential decay $e^{-\gamma \Delta t}$ IS the forget gate, but continuous
and smooth. No sigmoid, no explicit gate.

### 21.5 Breath/Heartbeat Modulation

$$B_t = \sin(2\pi t / L)$$

$$H_t = \max(0, \cos(14\pi t / L))^4$$

Applied to each chakra's resonance:

$$H_c(k; t) = H_c(k) \cdot (1 + \alpha_c^b B_t) \cdot (1 + \beta_c^h H_t)$$

### 21.6 Output (unchanged from Section 6)

Concatenated chakra states → output projection → logits.

---

## 22. CONSOLIDATION AND NEURON FORMATION (Training-Time)

### 22.1 Energy Tracking

For each chakra, track the time-averaged wave energy:

$$\bar{E}_c \leftarrow (1 - \eta_E) \cdot \bar{E}_c + \eta_E \cdot \frac{1}{L}\sum_t |\psi_c(t)|^2$$

where $\eta_E \approx 0.001$ (slow EMA across batches).

### 22.2 Condensation Check

At consolidation intervals (every N batches), check:

$$\bar{E}_c > \theta_\text{cond} \implies \text{new neuron forms in chakra } c$$

A new neuron is:
- A learned receptive field $\phi_n$ (new row in the chakra's resonance matrix)
- Initialized at the current average wave pattern
- Added to the chakra's dimension count $D_c$

### 22.3 Pruning

Neurons whose energy falls below $\theta_\text{prune}$ for a sustained period
are removed. Their dimension is freed for future condensation elsewhere.

### 22.4 Breathing Consolidation

During exhale ($B_t < 0$) and diastole ($H_t$ low), the learning rate for
receptive fields is increased:

$$\eta_\text{consolidate} = \eta \cdot (1 - B_t) \cdot (1 - H_t) \cdot \gamma_\text{cons}$$

Strongest consolidation happens during exhale-diastole — the model solidifies
what it learned during the inhale-systole phase.

---

## 23. DIAGNOSTIC QUANTITIES (Extended)

Additional diagnostics from the wave-unified forward pass:

| Symbol | Meaning | Range |
|---|---|---|
| $\bar{E}_c$ | Mean wave energy per chakra | $\mathbb{R}^+$ |
| $\text{res}_c$ | Mean resonance amplitude per chakra | [0, 1] |
| $J_{c \to c+1}$ | Energy flux from chakra $c$ to $c+1$ | $\mathbb{R}$ |
| $B_t$ | Breath phase at output token | [-1, 1] |
| $H_t$ | Heartbeat pulse at output token | [0, 1] |
| $\gamma_\text{eff}$ | Effective damping (from e−γΔt) | [0, 1] |
| $N_\text{neurons}$ | Total condensed neurons | $\mathbb{N}$ |
| $\bar{C}$ | Mean inter-chakra coupling strength | $\mathbb{R}^+$ |
| $\alpha_\text{disp}$ | Learned dispersion exponent | $\mathbb{R}$ |

### 23.1 Kundalini Metric

A single scalar tracking upward energy flow:

$$\mathcal{K} = \frac{1}{6} \sum_{c=1}^{6} \frac{\bar{E}_{c+1}}{\bar{E}_c}$$

$\mathcal{K} > 1$: energy rising (awakening). $\mathcal{K} < 1$: energy pooling
in lower chakras (grounded). $\mathcal{K} \approx 1$: balanced flow.

### 23.2 Chakra Balance

$$\mathcal{B} = -\sum_{c=1}^{7} p_c \log p_c \quad \text{where } p_c = \frac{\bar{E}_c}{\sum_{c'} \bar{E}_{c'}}$$

$\mathcal{B} \approx \log 7$: all chakras equally active (balanced).
$\mathcal{B} \ll \log 7$: one chakra dominates (imbalance).

---

## 24. FEEDBACK LOOPS (Extended)

| Loop | Equation | Timescale | New? |
|---|---|---|---|
| **L1-L7** | (from Section 11) | various | Existing |
| **L8: Breath mod chakras** | $H_c(k;t) \mathrel{\cdot}= (1 + \alpha_c^b B_t)$ | Per timestep | New |
| **L9: Heart mod chakras** | $H_c(k;t) \mathrel{\cdot}= (1 + \beta_c^h H_t)$ | Per timestep | New |
| **L10: Inter-chakra flow** | $\psi_c \mathrel{+}= \sum C_{c'\to c} \psi_{c'}$ | Per timestep | New |
| **L11: Wave damping** | $h_c(t) = e^{-\gamma\Delta t} h_c(t-1) + \psi_c(t)$ | Per timestep | Replaces f/u |
| **L12: Consolidation** | $\eta \mathrel{\cdot}= \gamma_\text{cons}(1-B_t)(1-H_t)$ | Exhale-diastole | New |
| **L13: Neuron formation** | $\bar{E}_c > \theta_\text{cond}$ → new neuron | Every N batches | New |

---

## 25. PARAMETER COUNT (Wave-Unified Model)

Compared to the V13 gate architecture (Section 12):

| Component | V13 Gates | Wave-Unified | Delta |
|---|---|---|---|
| Embedding | $V \cdot n_w$ | $V \cdot n_w$ | Same |
| Phase embedding | $n_w$ | $n_w$ | Same |
| Eigenbasis | $n_w \cdot D$ | $n_w \cdot D$ | Same |
| Gate weights | $(D + n_w) \cdot 2D$ | — | **Removed** |
| Phase memory | $2 \cdot n_w^2$ | — | **Removed** |
| Qi-gate modulation | $128D$ | — | **Removed** |
| Fractal rates | $D$ | — | **Removed** (derived from ω(k)) |
| Band yin/yang | $8$ | — | **Removed** (breath/heart replace) |
| Chakra resonance | — | $7 \cdot D \cdot \bar{D}_c$ | **New** |
| Inter-chakra coupling | — | $7 \times 7 = 49$ | **New** |
| Breath/heart coupling | — | $2 \cdot 7 = 14$ | **New** |
| Damping | — | $1$ | **New** ($\gamma$) |
| HealQi | $n_w \cdot N_\text{pix} + 6$ | $n_w \cdot N_\text{pix} + 6$ | Same |
| Output | $D \cdot V + V$ | $D \cdot V + V$ | Same |

The wave-unified model removes the explicit gate machinery (largest parameter
sink: $(D + n_w) \cdot 2D \approx 800K$ params at D=588) and replaces it with
chakra resonance ($7 \cdot 588 \cdot 84 \approx 346K$ params) — roughly half
the parameters for equivalent expressive power.

---

## Appendix A: From Continuous to Discrete

The continuous spine wave equation:

$$\frac{\partial^2\psi}{\partial t^2} + \gamma\frac{\partial\psi}{\partial t} = v^2\frac{\partial^2\psi}{\partial s^2} + \chi\frac{\partial\psi}{\partial s} + S(s,t)$$

Discretizes to (with $\Delta s = L_s / D$, $\Delta t$ per token):

$$\psi_{d}^{t+1} = e^{-\gamma\Delta t}\psi_d^t + \frac{v^2\Delta t^2}{\Delta s^2}(\psi_{d+1}^t - 2\psi_d^t + \psi_{d-1}^t) + \frac{\chi\Delta t}{\Delta s}(\psi_{d+1}^t - \psi_d^t) + S_d^t\Delta t^2$$

For the v1 implementation, the spatial derivative terms (neighbor coupling) are
absorbed into the inter-chakra coupling matrix $C$, and the damping $e^{-\gamma\Delta t}$
replaces the forget gate. This gives the simple discrete update:

$$h_c(t) = e^{-\gamma\Delta t} \cdot h_c(t-1) + \psi_c^\text{proc}(t)$$

---

## Appendix B: Why α = 1 is Special

When the dispersion exponent $\alpha = 1$ (non-dispersive medium), all
wavelengths travel at the same speed $v_0$. This means:

1. **The harmonic series is exact**: $f_h / f_b = 7$ exactly
2. **Chakra frequencies are proportional to 1/s**: simple geometric spacing
3. **No wave packet spreading**: information propagates without distortion
4. **The connection to the breathing body is cleanest**: one breath = one
   fundamental cycle of the spine

For $\alpha \neq 1$, the system becomes dispersive — different wavelengths
travel at different speeds. This creates richer dynamics (wave packets spread,
harmonics aren't exact multiples) at the cost of more complexity.

The recommended v1 value is $\alpha = 1$ (learnable, initialized at 1.0).

---

## Appendix C: Tokens as Wave Sources

Each token $x_t$ injects a wave packet onto the spine:

$$S(s, t = t_x) = \sum_k a_{x,k} \cdot e^{i(\phi_k + k s)}$$

The amplitude $a_{x,k}$ determines how MUCH energy at wavenumber $k$ the token
injects. The phase $\phi_k + ks$ determines WHERE on the spine the wave
originates (constructive interference at position $s$).

Tokens with similar embeddings inject wave packets that constructively interfere
at similar positions — this IS the mechanism by which similar concepts cluster
near the same chakra.

---

## Appendix D: Relationship to Predictive Coding

The wave equation IS a predictive coding hierarchy. The damping term
$e^{-\gamma\Delta t} \cdot h_c(t-1)$ IS the prediction: "the state should
persist." The chakra processing $\psi_c^\text{proc}(t)$ IS the prediction error:
"here's what the new input tells us." The balance between them (controlled by
$\gamma$) IS the precision weighting from active inference.

During inhale ($B_t > 0$): chakra resonance widens → prediction error is
amplified → the model LISTENS (sensory precision up).

During exhale ($B_t < 0$): chakra resonance narrows → prediction dominates →
the model REFLECTS (prior precision up).

This is the rhythmic precision modulation from Section 17, now grounded in
the wave dynamics.
