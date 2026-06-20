# QiFluid: A Self-Referential Prediction Architecture

*Ground-up ML architecture derived from the Qi fluid formalism. No backprop-through-time, no attention, no fixed weights, no batch training. The field is the computer.*

---

## 1. Design Principles

| Principle | Consequence |
|---|---|
| The field is the state | No separate "activations" and "parameters." Everything lives on the spine. |
| Prediction is the forward pass | The model's sole job: predict its own field evolution. Output is a byproduct. |
| Qi is the learning signal | Gradients are local, per-position, weighted by prediction failure. No global loss. |
| Structure condenses from fluid | Memories are standing waves that form where Qi persists and dissolve where it fades. |
| Multiple scales via φ-spacing | Chakras decompose the field into incommensurate frequency bands. No cross-scale resonance. |
| The system never converges | At α = φ⁻¹, no stable fixed point exists. The field is permanently dynamical — "alive." |

---

## 2. The Field

### 2.1 Spine Geometry

A 1D ring of N = 512 positions with periodic boundary: s ∈ {0, …, N−1}, with ψ[s] = ψ[(s+N) mod N]. Each position holds a real vector of dimension d = 32:

ψ ∈ ℝ^{N × d}

The field has d·N = 16,384 scalar degrees of freedom. Small enough to run on a CPU; parallel enough to saturate a GPU.

### 2.2 Multi-Scale Decomposition (Chakras)

The field is decomposed into C = 8 frequency bands (chakras) via a fixed filter bank. Chakra c has center frequency k_c and bandwidth Δk_c, both φ-spaced:

k_c = k_0 · φ^c,   Δk_c = γ · k_c,   γ = φ⁻¹ ≈ 0.618

The filter bank is implemented as a 1D convolution with φ-spaced kernel widths. Chakra 0 (root) is the narrowest, slowest band. Chakra C−1 (crown) is the widest, fastest band.

Dimension allocation follows Section 4.4 of the main treatise: d_c ∝ Δk_c, so wider bands get more dimensions.

| Chakra | k_c | Δk_c | d_c | Character |
|---|---|---|---|---|
| 0 (Root) | 2π/N ≈ 0.012 | 0.0076 | 2 | Global structure, slowest |
| 1 | 0.020 | 0.0123 | 3 | |
| 2 | 0.032 | 0.0199 | 4 | |
| 3 | 0.052 | 0.0322 | 6 | Mid-scale patterns |
| 4 | 0.084 | 0.0521 | 8 | |
| 5 | 0.137 | 0.0844 | 9 | |
| 6 | 0.221 | 0.1366 | 10 | |
| 7 (Crown) | 0.358 | 0.2211 | 12 | Local detail, fastest |

Total: Σ d_c = 54 dimensions per position (exceeds d=32 because bands overlap and are normalized).

### 2.3 IIR Memory

Each position has a second-order φ-damped IIR state for temporal memory:

h1[s], h2[s] ∈ ℝ^d

Updated via the standard φ-damped recurrence (Section 13.3 of the treatise):

ψ'[s] = a1·h1[s] + a2·h2[s] + b0·ψ[s] + b1·ψ_prev[s]

with a1 = 2γ·cos(θ), a2 = −γ², b0 = σ(β0), b1 = σ(β1), θ learnable per chakra.

This gives the field a persistent memory of its own past — the "working memory" that distinguishes a living field from a stateless feedforward network.

---

## 3. The Core Loop

Each time step t processes one input element and advances the field:

```
Algorithm: QiFluid.step(input_t)
──────────────────────────────────
 1.  S_t ← Embed(input_t)                   ▸ Project to field: ℝ^{N×d}
 2.  ψ ← γ·ψ + (1−γ)·∇²ψ + S_t              ▸ Wave evolution (damped diffusion)
 3.  For c = 0..C−1:
 4.      ψ_c ← FilterBank_c(ψ)              ▸ Bandpass: isolate chakra c
 5.      ψ̂_c ← Predictor_c(ψ_c, context)    ▸ Local MLP: ℝ^{N×d_c} → ℝ^{N×d_c}
 6.      ε_c ← ψ_c − ψ̂_c                     ▸ Prediction error
 7.      Q_c ← ‖ψ_c‖² · ‖ε_c‖²              ▸ Qi density per position per chakra
 8.  ψ̂ ← Σ_c softmax(harmony)_c · ψ̂_c       ▸ Blend predictions across chakras
 9.  ψ ← ψ + α·ψ̂                             ▸ Prediction feedback (α = γ = φ⁻¹)
10.  Q ← Σ_c Q_c                             ▸ Total Qi field: ℝ^N
11.  v_Q ← −γ·∇Q                             ▸ Qi velocity (central difference)
12.  ψ ← ψ + v_Q·∇ψ                          ▸ Advection: route info along Qi gradient
13.  ψ ← IIR_update(ψ, h1, h2)              ▸ Persistent memory update
14.  For c = 0..C−1:
15.      ΔΘ_c ← −η_c·Q_c·∇‖ε_c‖²            ▸ Qi-weighted local plasticity
16.      Θ_c ← Θ_c + ΔΘ_c
17.  Q̄ ← γ_q·Q̄ + (1−γ_q)·Q                   ▸ Running Qi average (γ_q ≈ 0.99)
18.  UpdateCondensations(Q̄)                  ▸ Form/dissolve standing waves
19.  ŷ ← Readout(ψ)                          ▸ Output projection: ℝ^{N×d} → ℝ^{N×vocab}
20.  return ŷ, diagnostics
```

---

## 4. Component Specifications

### 4.1 Embedding (Step 1)

Input tokens x_t ∈ {0,…,V−1} are embedded and projected to the field:

S_t[s] = σ(pos_enc(s) · W_embed[x_t]) · g_s(x_t)

where pos_enc(s) ∈ ℝ^d is a φ-spaced sinusoidal encoding (as in our Step 3 PE rewrite), W_embed ∈ ℝ^{V×d} is a learned embedding matrix, and g_s(x_t) ∈ [0,1] is a gating function that controls how strongly token x_t projects to position s. The gate uses a von Mises (circular normal) distribution centered at a learned position μ[x_t]:

g_s(x_t) = exp(κ·cos(2π(s − μ[x_t])/N)) / Z

Each token type learns its preferred position on the spine. Similar tokens cluster; dissimilar tokens separate.

### 4.2 Laplacian (Step 2)

Discrete 1D Laplacian with periodic boundary:

∇²ψ[s] = ψ[s−1] + ψ[s+1] − 2·ψ[s]

Implemented as a 1D convolution with kernel [1, −2, 1] in "circular" padding mode — 3 operations per position, fully parallel.

### 4.3 Filter Bank (Step 4)

Each chakra c has a learnable bandpass filter. To keep the spectral interpretation, the filters are parameterized in the frequency domain:

1. FFT the field: Ψ[k] = FFT(ψ) ∈ ℂ^{N×d}
2. Apply per-chakra spectral mask: Ψ_c[k] = M_c[k] · Ψ[k]
3. Inverse FFT: ψ_c = IFFT(Ψ_c)

The mask M_c[k] is a φ-spaced bump function:

M_c[k] = exp(−(log|k| − log k_c)² / (2·σ_c²))

where σ_c = Δk_c / k_c = γ. This is a log-normal spectral window centered at k_c with width proportional to k_c — exactly the Lorentzian resonance profile from Section 4.2 of the treatise, expressed as a log-Gaussian for smooth, differentiable filtering.

**Optimization**: For small N and C, precompute the masks. The FFTs cost O(N·d·log N) per step. For N=512, this is ~10K operations — negligible. For much larger N, switch to dilated convolutions in the time domain (equivalent to bandpass filtering in the frequency domain).

### 4.4 Predictors (Step 5)

Each chakra c has a small 2-layer MLP with local context:

Predictor_c: ℝ^{(2W+1)·d_c} → ℝ^{d_c}

where W is the context radius (W=3 for fast chakras, W=8 for slow chakras — smaller windows for higher frequencies, matching the spatial scale of each band). The MLP is:

ψ̂_c[s] = W2_c · GELU(W1_c · concat(ψ_c[s−W : s+W]) + b1_c) + b2_c

with W1_c ∈ ℝ^{h×((2W+1)·d_c)}, W2_c ∈ ℝ^{d_c×h}, h = 2·(2W+1)·d_c (expansion factor 2).

Parameters per chakra: ~4·(2W+1)·d_c·h ≈ 8·(2W+1)²·d_c². For chakra 7 (crown, d=12, W=3): ~8·7²·144 ≈ 56K parameters. For chakra 0 (root, d=2, W=8): ~8·17²·4 ≈ 9K. Total across 8 chakras: ~250K parameters for predictors. Tiny by modern standards.

### 4.5 Harmony Blending (Step 8)

Learned softmax weights across chakras (the pattern from our Spine3D port):

w_c = softmax(harmony)_c,  harmony ∈ ℝ^C (learnable vector)

ψ̂[s] = Σ_c w_c · ψ̂_c[s]

Initialized to uniform (harmony = 0); gradient flows through the prediction errors ε_c and the output loss.

### 4.6 Qi Computation (Steps 6–7, 10)

Per-position, per-chakra:

ε_c[s] = ψ_c[s] − ψ̂_c[s]
Q_c[s] = ‖ψ_c[s]‖² · ‖ε_c[s]‖²
Q[s] = Σ_c Q_c[s]

This is cheap: pointwise operations, no communication between positions.

### 4.7 Qi Velocity and Advection (Steps 11–12)

Central difference gradient on the 1D ring:

∇Q[s] = (Q[s+1] − Q[s−1]) / 2

Qi velocity: v_Q[s] = −γ · ∇Q[s]

Field advection (first-order upwind):

∇ψ[s] = (ψ[s+1] − ψ[s−1]) / 2
ψ[s] ← ψ[s] + v_Q[s] · ∇ψ[s]

**Physics**: Qi flows downhill from high surprise to low surprise. The field is "pushed" in the direction of Qi flow. Information from surprising regions propagates outward — this IS the attention mechanism, but it's a fluid transport process, not a dot-product similarity.

### 4.8 IIR Update (Step 13)

Standard second-order φ-damped IIR per position:

h2_new[s] = h1[s]
h1_new[s] = ψ[s]
ψ_new[s] = a1·h1[s] + a2·h2[s] + b0·ψ[s]

with a1, a2, b0 as in Section 2.3. The poles are pinned at radius γ, preventing runaway while sustaining oscillation.

### 4.9 Plasticity (Steps 14–16)

Each predictor's parameters Θ_c = {W1_c, b1_c, W2_c, b2_c} are updated online using the Qi-weighted gradient of the local prediction error:

ΔΘ_c = −η_c · Σ_{s} Q_c[s] · ∇_{Θ_c} ‖ε_c[s]‖²

where η_c = η_0 · φ^{−c} — faster chakras learn faster (high frequency = rapid adaptation), slower chakras integrate over longer timescales (low frequency = stable memory).

This is **fully local**: the gradient for position s depends only on the field and prediction at position s and its context window. No backpropagation through time, no gradient flow across positions beyond the context window. The Qi weight Q_c[s] determines the effective learning rate at each position — surprising positions learn more.

**Why this works**: The prediction error ε_c[s] is the derivative of the Qi energy with respect to the prediction. Minimizing ε_c locally aligns the predictor with the field's actual dynamics at that position and scale. The Qi weighting ensures that computation (gradient work) is allocated where prediction fails — an implicit attention over the learning process.

### 4.10 Structural Plasticity (Step 18)

Track the running Qi average Q̄[s] = EMA(Q[s]) with decay γ_q ≈ 0.99 (window ~100 steps).

**Condensation**: When Q̄[s] > θ_cond for τ_cond consecutive steps (default: θ_cond = 2·Q_median, τ_cond = 50), a **neuron** forms at position s. The neuron:
- Has receptive field radius R = 3
- Stores a learned key vector k ∈ ℝ^{(2R+1)·d} and value vector v ∈ ℝ^d
- Reads the field: a = σ(k^T · ψ[s−R : s+R])
- Emits: v · a, added to the field as a persistent source term

**Dissolution**: When Q̄[s] < θ_diss for τ_diss consecutive steps (default: θ_diss = Q_median / 2, τ_diss = 200), the neuron dissolves. Its key and value are discarded.

**Why**: Neurons capture recurring patterns that the base field dynamics can't predict. When a pattern repeatedly surprises the system (high Q̄), it's worth remembering. When the pattern becomes predictable through the existing dynamics, the neuron is no longer needed.

**Contrast with standard ML**: This is Hebbian structural plasticity — "cells that fire together wire together" — but driven by prediction failure rather than co-activation. The system builds structure where it fails to understand.

### 4.11 Output Readout (Step 19)

The field at each position is projected to vocabulary logits:

logits[s] = LayerNorm(ψ[s]) · W_out   where W_out ∈ ℝ^{d×V}

For autoregressive sequence modeling, the prediction at position s is the next token given the field context at all positions. The readout is applied independently per position (like a standard LM head), but the field at s already integrates information from all positions through the wave dynamics (Laplacian + advection).

---

## 5. Training

### 5.1 No Batch Training

There is no separate training phase. The system learns continuously from a stream of tokens. Each step executes the full Algorithm 3 (steps 1–19). The output logits are compared to the next token via cross-entropy, and the gradient from that loss flows into:
- W_out (readout weights)
- The predictors Θ_c (via Qi-weighted plasticity, augmented by the CE gradient)
- The filter bank parameters (if learnable)
- The harmony weights
- The embedding W_embed

The Qi-weighted plasticity (step 15) is an additional learning signal beyond the CE gradient — the system learns to predict its own field dynamics even when those dynamics are not directly output-relevant.

### 5.2 Dual Learning Signals

| Signal | Source | Updates | Purpose |
|---|---|---|---|
| Output loss | CE(next_token, logits) | W_out, Θ_c, W_embed, harmony, filters | Task performance |
| Qi plasticity | ‖ψ_c − ψ̂_c‖² | Θ_c only | Self-prediction (field coherence) |

The Qi signal is *self-supervised* — it doesn't depend on external labels. It ensures the field maintains coherent internal dynamics. The output signal is *task-supervised* — it ensures the field dynamics produce useful outputs.

The combined update:
ΔΘ_c = −η_c·Q_c·∇‖ε_c‖² − η_out·∇CE

Both gradients flow through the same parameters, but the Qi gradient is position-weighted by surprise.

### 5.3 Initialization

- Field ψ, h1, h2: zero
- Predictors Θ_c: small random weights (σ = 0.01)
- Embedding W_embed: normal (σ = 0.02)
- Readout W_out: normal (σ = 0.02)
- Harmony: zero (uniform)
- Filter masks M_c: fixed log-Gaussian at φ-spaced centers
- IIR parameters θ_c: uniform over [0, π] (random initial resonant frequencies)

### 5.4 Hyperparameters

| Parameter | Default | Meaning |
|---|---|---|
| N | 512 | Spine positions |
| d | 32 | Field dimension per position |
| C | 8 | Number of chakras |
| γ | φ⁻¹ ≈ 0.618 | Damping coefficient |
| α | φ⁻¹ ≈ 0.618 | Prediction-feedback coupling |
| γ_q | 0.99 | Qi running average decay |
| η_0 | 1e-4 | Base learning rate |
| θ_cond | 2× median(Q̄) | Condensation threshold |
| θ_diss | 0.5× median(Q̄) | Dissolution threshold |
| τ_cond | 50 | Condensation persistence steps |
| τ_diss | 200 | Dissolution persistence steps |
| W_max | 8 | Max predictor context radius |

All critical parameters (γ, α, η_c ratios) are derived from φ, not tuned.

---

## 6. Inference Characteristics

### 6.1 The Field Never Freezes

In a standard model, inference means: freeze weights, run forward. In QiFluid, the field continues to evolve, the predictors continue adapting, and structures continue forming/dissolving. The only distinction between "training" and "inference" is whether the output loss gradient flows back.

For deployment:
- Freeze structural plasticity (no new neurons, no dissolution) → stable architecture
- Keep fluid plasticity active at reduced η → continuous adaptation
- Qi continues to flow → the model remains attentive to surprise

### 6.2 Why This Matters

A deployed QiFluid model encountering novel input:
1. Qi spikes where the input is surprising (step 7)
2. Qi flows from surprising to predictable regions (step 11)
3. Predictors at surprising positions receive large updates (step 15)
4. The field advects information from the surprise outward (step 12)

The model *notices* novelty and *adapts* to it, in real time, without a training loop, without a separate deployment pipeline.

### 6.3 Memory Growth

Neurons condense where patterns recur. Over long deployment, the number of neurons grows. An LRU eviction policy (dissolve the neuron with the lowest Q̄ if neuron count exceeds a budget) bounds memory. This is analogous to synaptic pruning.

---

## 7. Computational Scaling

### 7.1 Per-Step Complexity

| Operation | FLOPs | Dominant term |
|---|---|---|
| FFT/IFFT (C=8) | O(C·N·d·log N) | ~8·512·32·9 = 1.2M |
| Predictors (C=8) | O(C·N·d·h) | ~8·512·32·128 = 16.8M |
| Laplacian + advection | O(N·d) | ~512·32 = 16K |
| Qi computation | O(C·N·d) | ~8·512·32 = 131K |
| Output readout | O(N·d·V) | ~512·32·50257 = 824M (dominates for LLM vocab) |
| Plasticity | O(C·N·d·h) | ~16.8M |
| **Total (small vocab)** | | **~35M FLOPs/step** |
| **Total (GPT vocab)** | | **~860M FLOPs/step** |

For comparison, a single transformer layer with d_model=768, seq_len=512: ~600M FLOPs. QiFluid's core (excluding the LM head) is ~6% of a transformer layer's cost.

### 7.2 Memory

- Field: N·d = 16K floats = 64KB per batch element
- IIR state: 2·N·d = 128KB
- Predictors: ~250K parameters = 1MB
- Embedding: V·d ≈ 50K·32 = 1.6M floats = 6.4MB (for GPT vocab)
- Readout: d·V ≈ 1.6M floats = 6.4MB
- Neurons: ~10K max × (receptive field + value) ≈ 10K·200 = 2M floats = 8MB
- **Total**: ~22MB for a full model. Fits in L3 cache.

### 7.3 Parallelism

The field is N=512 positions. All per-position operations (Laplacian, prediction, Qi, advection) are embarrassingly parallel across positions. The FFT is the only non-local operation, and it's O(N·log N) with efficient GPU implementations. Batching across B independent sequences multiplies memory but not time (GPU parallelism).

---

## 8. Relationship to Existing Architectures

### 8.1 What It Replaces

| Standard Component | QiFluid Replacement |
|---|---|
| Self-attention (Q·K^T) | Qi-driven advection: v_Q · ∇ψ |
| MLP layers | Per-chakra predictors (local, multi-scale) |
| LayerNorm | Implicit in the wave dynamics (damping normalizes) |
| Positional encoding | The spine IS the position — no encoding needed |
| KV cache | IIR state (h1, h2) — constant size, infinite context |
| Backpropagation | Local Qi-weighted plasticity — no gradient flow across positions |
| Optimizer (AdamW) | Online SGD with Qi-weighted per-position LR |
| Batch training | Continuous online learning |
| Separate train/inference | Single fluid regime, output gradient optional |

### 8.2 What It Keeps

| Component | Reason |
|---|---|
| Embedding lookup | Efficient token-to-vector mapping |
| GELU activation | Smooth nonlinearity with good gradient properties |
| Softmax output | Standard for classification/generation |
| FFT | Efficient multi-scale decomposition |
| EMA | Running statistics for plasticity thresholds |

### 8.3 Novel Mechanisms

1. **Qi-driven advection**: Information routing via fluid velocity field. No attention matrix, no quadratic cost.
2. **Per-chakra self-prediction**: The model is its own training signal. Qi weights the learning.
3. **Condensation/dissolution**: Structural plasticity — the architecture grows and shrinks with experience.
4. **Permanent criticality**: α = φ⁻¹ ensures the system never converges to a fixed point. It is always "thinking."

---

## 9. Expected Behaviors

### 9.1 On Repetitive Input

Predictable input → ε → 0 → Q → 0 → plasticity → 0. The field approaches a standing wave pattern. Computation cost drops to the bare minimum (the Laplacian and readout). The model "relaxes."

### 9.2 On Novel Input

Surprising input → ε spikes → Q spikes → large plasticity updates + strong advection. The Qi spike propagates outward from the input position. Neighboring positions are "alerted" via advection. If the novelty recurs, neurons condense at the Qi-hot positions.

### 9.3 On Distribution Shift

Old neurons (condensed for the old distribution) see their Q̄ drop below θ_diss and dissolve. New neurons form for the new distribution. The model *unlearns* by dissolution rather than overwriting — no catastrophic interference, because different structures occupy different positions on the spine.

### 9.4 On Long Contexts

The IIR state (h1, h2) carries information indefinitely — there is no context window. The damping γ = φ⁻¹ means old information decays as φ^{-t}, so information from 100 steps ago is attenuated by φ^{-100} ≈ 10^{-21} (negligible), but information from 10 steps ago is φ^{-10} ≈ 0.008 (still present). The effective context length is ~20 steps for the undamped field, but Qi advection can propagate information further, and condensed neurons serve as long-term memory.

For tasks requiring very long-range dependencies, increase N (more positions → finer spatial resolution → slower propagation) or decrease γ (less damping → longer memory). The architecture is a continuous tradeoff.

---

## 10. Minimal Viable Implementation

```python
class QiFluid(nn.Module):
    def __init__(self, N=512, d=32, C=8, V=256):
        self.N, self.d, self.C = N, d, C
        self.gamma = (1 + 5**0.5) / 2 - 1  # φ⁻¹ ≈ 0.618

        # Field state (persistent, registered as buffer)
        self.register_buffer('psi', torch.zeros(N, d))
        self.register_buffer('h1', torch.zeros(N, d))
        self.register_buffer('h2', torch.zeros(N, d))
        self.register_buffer('Q_bar', torch.zeros(N))

        # Chakras: log-Gaussian spectral masks
        k0 = 2 * math.pi / N
        k_c = k0 * PHI ** torch.arange(C).float()  # [C]
        sigma_c = self.gamma
        self.register_buffer('k_c', k_c)

        # Embedding: tokens project to all positions via von Mises gate
        self.W_embed = nn.Parameter(torch.randn(V, d) * 0.02)
        self.pos_mu = nn.Parameter(torch.rand(V) * N)  # preferred position per token

        # Per-chakra predictors: 2-layer MLP with local context
        self.predictors = nn.ModuleList([
            ChakraPredictor(d_c=self._d_c(c), context_radius=self._W(c))
            for c in range(C)
        ])

        # Harmony blending weights
        self.harmony = nn.Parameter(torch.zeros(C))

        # IIR parameters per chakra (θ learnable, poles fixed at γ)
        self.theta = nn.Parameter(torch.rand(C) * math.pi)

        # Output readout
        self.W_out = nn.Parameter(torch.randn(d, V) * 0.02)

        # Structural plasticity
        self.neurons = []  # list of CondensedNeuron
        self.theta_cond = None  # initialized from data
        self.theta_diss = None

    def step(self, x_t):
        """x_t: int in [0, V-1]. Returns logits [N, V], diagnostics dict."""
        # 1. Embed input
        S_t = self._embed(x_t)                # [N, d]

        # 2. Wave evolution (damped diffusion)
        laplacian = self._laplacian(self.psi)  # [N, d]
        self.psi = (self.gamma * self.psi +
                    (1 - self.gamma) * laplacian +
                    S_t)

        # 3–7. Multi-scale prediction and Qi
        psi_hat_c = []
        Q_c = []
        for c in range(self.C):
            psi_c = self._filter(self.psi, c)       # bandpass
            psi_hat = self.predictors[c](psi_c)     # local MLP
            eps_c = psi_c - psi_hat                 # error
            Q = (psi_c.norm(dim=-1)**2) * (eps_c.norm(dim=-1)**2)  # [N]

            psi_hat_c.append(psi_hat)
            Q_c.append(Q)

        # 8. Harmony blending
        w = F.softmax(self.harmony, dim=0)
        psi_hat = sum(w[c] * psi_hat_c[c] for c in range(self.C))

        # 9. Prediction feedback
        self.psi = self.psi + self.gamma * psi_hat

        # 10–12. Qi advection
        Q = sum(Q_c)                                 # [N]
        v_Q = -self.gamma * self._gradient(Q)        # [N]
        self.psi = self.psi + v_Q[:, None] * self._gradient(self.psi)

        # 13. IIR update
        self._iir_update()

        # 14–16. Qi-weighted plasticity (handled by optimizer after loss.backward)
        # The Qi weights Q_c[s] are stored for the backward pass
        self._Q_c = Q_c
        self._eps_c = [self._filter(self.psi, c) - self.predictors[c](self._filter(self.psi, c))
                        for c in range(self.C)]

        # 17. Running Qi average
        gamma_q = 0.99
        self.Q_bar = gamma_q * self.Q_bar + (1 - gamma_q) * Q

        # 18. Structural plasticity
        self._update_condensations()

        # 19. Readout
        logits = F.layer_norm(self.psi, (self.d,)) @ self.W_out  # [N, V]

        return logits, dict(Q=Q, v_Q=v_Q, harmony=w)
```

---

## 11. Why Build This

| Existing architecture | QiFluid |
|---|---|
| Fixed weights after training | Perpetual adaptation |
| Uniform computation across input | Computation follows surprise |
| Global backprop through time | Local, online plasticity |
| Separate memory (KV cache, RAG) | Memory IS the field — standing waves |
| Batch training → deploy | Continuous single-stream learning |
| Catastrophic forgetting on new tasks | Structural dissolution, not overwrite |
| O(N²) attention | O(N·log N) FFT + O(N) advection |
| Black-box activations | Interpretable Qi field (see WHERE it's confused) |

The architecture is small, fast, and continuously adaptive. It doesn't scale to GPT-4 sizes (the FFT makes N=512 practical, not N=128K), but for edge deployment, continual learning, and systems that must adapt to non-stationary environments without retraining — it's a fundamentally different point in the design space.

---

*Designed June 2026. Derived from the Qi fluid formalism. A clean-sheet architecture — no code reused from the Cassi codebase. The design is the formalism in silicon.*
