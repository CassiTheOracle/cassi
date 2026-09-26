# ManifoldCord v2 — Research Projects

## Status

| Project | Priority | Difficulty | Dependency |
|---|---|---|---|
| Parallel (block) generation | High | Medium | None |
| Self-supervised pretraining | High | High | Parallel generation |
| Anchor compression (M < W) | Medium | High | None |
| Absolute position encoding | Medium | Low | None |
| Episode memory (tier 3) | Medium | High | Anchor compression |
| Breath-gated resolution | Low | Medium | None |
| Interleaved forward/backward | Low | High | None |
| Online weight distillation | Low | Medium | None |

---

## 1. Parallel (Block) Generation

**Problem**: Current generation is autoregressive — one token at a time, with K_gen field steps per token. For 128 tokens, that's 128 K_gen calls (6,400 kernel groups at K_gen=50). Slow and kernel-launch heavy.

**Idea**: Generate all `max_new` tokens simultaneously in one field evolution.

### Mechanism

1. **Process seed through windows** as in `generate_from_stream` — accumulate full file context into IIR state + pattern memory.
2. **Extend the field**: Create an [1, N_ext] window where `N_ext = seed_suffix_len + max_new`. The first `seed_suffix_len` positions contain the last N tokens of the seed (providing local context). The remaining `max_new` positions are zero-filled (byte 0, i.e., NUL).
3. **Run K_gen field steps**: The field dynamics propagate information from the seed suffix into the empty positions via:
   - **SpatialCoupling**: φ-scaled lateral diffusion carries information across neighboring positions.
   - **ResonantAttention**: Zero-parameter attention retrieves relevant patterns from the seed region.
   - **IIR dynamics**: Temporal memory provides context from earlier windows.
   - **Pattern memory**: Long-term memory retrieves relevant patterns from training.
4. **Readout at all new positions**: `readout_positions(psi)[:, seed_suffix_len:, :]` gives logits at each new position.
5. **Sample all positions independently**: Multinomial sampling at each position, or use a CRF / beam search for coherent sequences.

### Why This Should Work

The field is a **continuous resonant medium**. When a source term (seed) is placed at one end of the medium, the wave equation propagates information spatially. The empty positions start at zero amplitude, and the field dynamics "fill them in" based on:
- Local continuity (adjacent positions should be similar)
- Global consistency (the seed constrains the field)
- Pattern completion (similar patterns in pattern memory)

This is analogous to **image inpainting** — the seed is the "known" region, and the field fills in the "missing" region.

### Implementation Sketch

```python
@torch.no_grad()
def generate_parallel_stream(self, seed, max_new=128, temp=0.8, K_init=None):
    # 1. Process seed through windows (same as generate_from_stream)
    self._process_seed_windows(seed, K_init)
    
    # 2. Build extended window
    suffix = seed[-self.N // 2:]  # last N/2 tokens as context prefix
    N_ext = suffix.numel() + max_new
    window = torch.zeros(N_ext, dtype=torch.long, device=device)
    window[:suffix.numel()] = suffix  # seed suffix + zeros
    
    # 3. Embed and run K_gen steps on extended field
    psi_real, psi_imag = self.embed(window.unsqueeze(0))
    for _ in range(K_init):
        (psi_real, psi_imag, h1n, h2n, ...) = self._unified_step(...)
        # ... persist state ...
    
    # 4. Readout all new positions
    logits = self.readout_positions(psi_real, psi_imag)[0, suffix.numel():, :] / temp
    samples = torch.multinomial(F.softmax(logits, dim=-1), 1).squeeze(-1)
    return samples
```

### Challenges

1. **Coherence**: Independently sampled positions may produce incoherent sequences (e.g., repeated tokens, broken patterns). Solutions: iterative refinement (multiple passes), or a lightweight autoregressive head on top of the parallel samples.
2. **Quality vs speed tradeoff**: More K_gen steps = better propagation but slower. Find the sweet spot.
3. **Position encoding on extended field**: The extended window has positions [suffix_len, N_ext). The position encoding should reflect absolute file positions.

### Relation to Existing Code

MuonCord already has `generate_parallel` (muon_cord.py:1130) which seeds N positions and generates in parallel. `generate_parallel_stream` extends this to: (a) process arbitrarily long seeds before parallel generation, and (b) generate more than N-new tokens by using a larger extended window (or iterative parallel blocks).

---

## 2. Self-Supervised Pretraining

**Problem**: Current training uses next-token prediction (autoregressive CE). This is effective but slow to learn global structure — the model only gets a training signal from predicting the next byte, not from understanding the whole file.

**Idea**: Add self-supervised objectives that operate on the full field state, not just the readout at target positions.

### 2a. Masked Token Prediction (Field Inpainting)

Operates within a single window (compatible with current architecture):

1. **Mask**: Randomly replace 15% of input tokens with a [MASK] token (byte 0, or a special value).
2. **Process**: Run K_train field steps on the masked input.
3. **Predict**: Read out at masked positions. CE loss on masked positions only.
4. **Field dynamics fill gaps**: Spatial coupling + attention propagate information from unmasked positions into masked ones.

This is BERT-style training adapted to the continuous field. The field's spatial dynamics naturally perform "inpainting" — masked positions are predicted from neighboring unmasked positions through lateral diffusion.

### 2b. Field Consistency (Contrastive)

Encourages the field state to be invariant under perturbations:

1. **Two views**: Process the SAME window with two different perturbations:
   - Different subsets of masked tokens
   - Different noise levels (vary `noise_scale`)
   - Different starting breath phases
2. **Consistency loss**: MSE between the resulting field states (psi_real, psi_imag) at unmasked positions.
3. **Separation**: Also push apart field states from DIFFERENT windows (negative pairs).

This is SimCLR-style contrastive learning on the field state. The field learns to represent the underlying structure (which is shared between views) rather than surface perturbations.

### 2c. Next-Window Prediction (Streaming)

Operates across windows — trains the model to predict the field state of the next window:

1. **Process**: Window k → field state ψ_k (IIR state + pattern memory).
2. **Predict**: From ψ_k, predict properties of window k+1:
   - Mean field amplitude (MSE)
   - Chakra activation distribution (KL divergence)
   - Qi density (MSE)
3. **Loss**: Difference between predicted and actual window k+1 properties.

This trains the IIR state to encode predictive information about future windows — making the streaming context more useful.

### 2d. File-Level Objectives

1. **File boundary detection**: Binary classifier on field state → "is this the end of a file?" Trains the field to recognize structural boundaries.
2. **Language identification**: Multi-class classifier on field state. Trains the field to distinguish language-level patterns (Python vs. English vs. JSON).
3. **File size prediction**: Regress file length from early-window field state. Trains the field to estimate scope.

### Implementation Strategy

Add a `SelfSupervisedHead` module that attaches to the field state at various points:
```python
class SelfSupervisedHead(nn.Module):
    def __init__(self, d):
        # Masked token prediction head
        self.mask_predictor = nn.Linear(d, 256)
        # File boundary classifier
        self.boundary_classifier = nn.Linear(d, 2)
        # Window predictor (field state → next-window properties)
        self.window_predictor = nn.Sequential(
            nn.Linear(d, d // 4), nn.GELU(), nn.Linear(d // 4, 13))

    def forward(self, psi_real, psi_imag, mask, ...):
        return {
            'mask_logits': self.mask_predictor(psi_real + psi_imag),  # [B,N,256]
            'boundary_logits': self.boundary_classifier(
                (psi_real + psi_imag).mean(dim=1)),  # [B,2]
            'window_pred': self.window_predictor(
                (psi_real + psi_imag).mean(dim=(1,2))),  # [B,13]
        }
```

Training combines next-token CE with weighted self-supervised losses:
```python
loss = ce_loss + lambda_mask * mask_loss + lambda_boundary * boundary_loss + ...
```

---

## 3. Anchor Compression (M < W)

**Problem**: Currently M = W = N — each window position has one anchor. This means the field resolution is tied to window size. For larger windows (e.g., W=512) or more anchors for detail (e.g., M=256 for W=128), the computational cost scales with M × d.

**Idea**: Decouple field resolution M from window size W. Use M anchors (M < W) with interpolation to map tokens to anchors.

### Mechanism

1. **M anchors at positions** {x₁, ..., x_M} in [0, 1]. Initially uniform; later adaptive.
2. **Token injection**: Each token at position `t` distributes its embedding to nearby anchors via an interpolation kernel:
   ```python
   weights = phi_kernel(t/W, anchor_positions)  # [M]
   psi_real += weights.unsqueeze(0).unsqueeze(-1) * token_emb  # [B, M, d]
   ```
3. **Field dynamics**: ResonantField, IIR, etc. operate on [B, M, d].
4. **Readout interpolation**: To predict token at position `t`, interpolate field state at that position:
   ```python
   weights = phi_kernel(t/W, anchor_positions)  # [M]
   psi_at_t = (weights.unsqueeze(0).unsqueeze(-1) * psi).sum(dim=1)  # [B, d]
   logit = readout_y(psi_at_t)
   ```

### Interpolation Kernel

Use the φ-scaled kernel from SpatialCoupling, generalized to continuous positions:
```python
def phi_kernel(x, anchors, decay_length=None):
    # x: [K] query positions
    # anchors: [M] anchor positions
    dist = (x.unsqueeze(1) - anchors.unsqueeze(0)).abs()  # [K, M]
    if decay_length is None:
        decay_length = PHI * (anchors.max() - anchors.min())
    weights = PHI ** (-dist / decay_length)
    return weights / weights.sum(dim=-1, keepdim=True).clamp_min(1e-12)
```

### Submodule Changes Required

- **SpatialCoupling**: Replace [M,M] precomputed kernel with the kernel function evaluated at anchor positions.
- **ResonantAttention**: Replace [M,M] structural kernel similarly.
- **QiFlow**: Replace discrete Laplacian (neighbor indexing) with anchor-aware derivatives: `∇²Q(x_i) ≈ Σ_j kernel(x_i, x_j) · (Q(x_j) - Q(x_i))`.
- **Position encoding**: Already a continuous function in ManifoldCord.
- **ResonantField, MultiScaleCord, TonicPhasic, etc.**: No changes — operate on [B, M, d].

### Adaptive Anchors (v2.5)

Once M < W works: make anchor positions learnable.
- Anchor positions as `nn.Parameter(torch.linspace(0, 1, M))`.
- Qi-driven anchor growth: when Qi is high in a region, add an anchor there.
- Low-Qi pruning: when an anchor is consistently below threshold, remove it.
- Anchor movement: gradients flow through the interpolation kernel to optimize anchor positions.

---

## 4. Absolute Position Encoding

**Problem**: Current position encoding is relative to the window (positions [0, N-1]). The model can't distinguish "position 5 in window 3" from "position 5 in window 7" except through the IIR state. For very long files, this may cause aliasing.

**Idea**: Replace the static `pos_enc_real/imag` buffers with a function of absolute file position.

### Mechanism

```python
def position_encode(self, absolute_pos, context_span=65536):
    # absolute_pos: [B, W] — positions in bytes from file start
    i = torch.arange(self.d, dtype=torch.float32, device=absolute_pos.device)
    freqs = (2 * math.pi / context_span) * PHI ** (i / self.d)
    angle = absolute_pos.unsqueeze(-1) * freqs
    return torch.sin(angle), torch.cos(angle)

def embed(self, x, absolute_pos=None):
    emb = self.token_embed(x)
    if absolute_pos is None:
        absolute_pos = torch.arange(x.shape[1], device=x.device).unsqueeze(0)
    pe_re, pe_im = self.position_encode(absolute_pos)
    return emb + pe_re, self.imag_proj(emb) + pe_im
```

### Challenges

- **context_span tradeoff**: Small span = fast-varying encoding (good for within-window distinction) but aliases over long files. Large span = slow-varying (aliases less) but positions within a window are nearly identical.
- **Solution**: φ-scaled frequencies already provide this — low chakras (i/d ≈ 0) have slow variation (long wavelength), high chakras (i/d ≈ 1) have fast variation (short wavelength). The model uses different chakras for different spatial scales.
- **Training**: The trainer must pass `absolute_pos` to `training_loss` for each window. Position = `window_idx * N + local_pos`.

### When to Use

Not needed for v1 (relative encoding + IIR state is sufficient). Use for v2 when processing files > 100K tokens, or when the IIR state alone isn't providing enough positional awareness.

---

## 5. Episode Memory (Tier 3)

**Problem**: Pattern memory (tier 2) stores compressed representations with a limited capacity (max_neurons). IIR state (tier 1) is the working memory for the current file. There's no mechanism to recall specific earlier sections of a very long file.

**Idea**: Add a third memory tier — "episode memory" — that stores field state snapshots at regular intervals and retrieves them by similarity.

### Mechanism

1. **Write**: Every K windows, snapshot the field state (psi at M anchors, mean-pooled to a vector) and store it with a position tag.
2. **Read**: At each window, compute similarity between current field state and episode memory. Retrieve top-K episodes.
3. **Inject**: Add the retrieved episode representations to the current field state (like pattern memory read).

```python
class EpisodeMemory(nn.Module):
    def __init__(self, d, max_episodes=256):
        self.keys = nn.Parameter(torch.randn(max_episodes, d))    # episode keys
        self.values_re = nn.Parameter(torch.randn(max_episodes, d))  # compressed states
        self.values_im = nn.Parameter(torch.randn(max_episodes, d))
        self.positions = nn.Parameter(torch.zeros(max_episodes))    # file positions
        self.ptr = 0
    
    def write(self, psi_re, psi_im, position):
        key = psi_re.mean(dim=(0, 1))  # compress to [d]
        self.keys[self.ptr] = key
        self.values_re[self.ptr] = psi_re.mean(dim=(0, 1))
        self.values_im[self.ptr] = psi_im.mean(dim=(0, 1))
        self.positions[self.ptr] = position
        self.ptr = (self.ptr + 1) % self.max_episodes
    
    def read(self, psi_re, psi_im, top_k=4):
        query = psi_re.mean(dim=(0, 1))
        sim = F.cosine_similarity(query, self.keys, dim=-1)
        top_idx = sim.topk(top_k).indices
        return self.values_re[top_idx].mean(dim=0), self.values_im[top_idx].mean(dim=0)
```

### When to Use

For files > 10K tokens where the IIR state's PHI_INV dampening has caused near-complete forgetting of early sections (after ~10 windows, state is at 0.618^10 ≈ 0.8% of original).

---

## 6. Breath-Gated Resolution

**Problem**: Not all parts of a file are equally important. Comments, boilerplate, and repetitive patterns don't need full field resolution.

**Idea**: Use the breath oscillator to modulate processing depth:
- **Yang phase** (active, ~1.0 rate): Full K_train steps, full d dimension. "Reading closely."
- **Yin phase** (passive, ~0.618 rate): Reduced K_train // 2 steps, truncated d // φ dimension. "Skimming."

### Mechanism

```python
breath_yang = torch.sin(self.breath_t_yang)
if breath_yang > 0.3:  # yang: full processing
    K = self.K_train
    d_eff = self.d
else:  # yin: reduced processing
    K = max(1, self.K_train // 2)
    d_eff = int(self.d * PHI_INV)
    psi_real = psi_real[..., :d_eff]
    psi_imag = psi_imag[..., :d_eff]
```

The breath naturally alternates between phases, so the model gets both detailed and coarse processing of the file. The chakra structure already handles multi-scale processing within each phase.

### Benefits

- **Compute savings**: ~30% reduction in total operations during yin phases.
- **Longer effective context**: Yin-phase processing has lower IIR dampening (fewer steps), allowing information to persist longer.
- **Hierarchical processing**: Yang = local detail, Yin = global structure. Both contribute to the final field state.

---

## 7. Interleaved Forward/Backward Windows

**Problem**: Forward-only streaming can only use context from earlier windows. True bidirectionality requires a second backward pass over the file.

**Idea**: Instead of two full passes, interleave forward and backward windows:
- Window 0: forward (tokens 0→W)
- Window 1: backward (tokens 2W→W, reversed)
- Window 2: forward (tokens W→2W)
- Window 3: backward (tokens 3W→2W, reversed)

Each window uses the IIR state from the previous window, regardless of direction. The model learns to use forward context (from forward windows) and backward context (from backward windows) together.

### Challenges

- **IIR state semantics**: The IIR state carries "what came before" — but when alternating directions, "before" means alternating forward and backward. The state becomes direction-agnostic.
- **Position encoding**: Reverse windows need reversed position encoding. A new flag in embed() handles this: `embed(x, direction='backward')` reverses the position encoding order.
- **Training complexity**: The interleaving pattern must be consistent — the model needs to learn which windows are forward and which are backward.

### When to Use

When forward-only context is insufficient (e.g., code completion needs to know what follows a function call). For text generation, forward-only is usually sufficient.

---

## 8. Online Weight Distillation

**Problem**: `soft_condense` distills IIR state into weight deltas (fast weights). This is a simple form of online learning, but the scale `PHI_INV / (1 + |h1|)` is fixed.

**Idea**: Make the condensation learnable:
- A small network predicts the condensation scale per chakra based on Qi, breath phase, and field statistics.
- The condenser's deltas are gated by Qi — high-Qi (surprising) states get larger weight updates.
- An EMA of condensation effectiveness (did the update reduce future Qi?) modulates the scale.

### Mechanism

Replace the fixed-scale condensation:
```python
scale = PHI_INV / (1.0 + h1_norm.item())
```
with:
```python
scale_per_chakra = self.condense_controller(Q_per_chakra, breath_yang, breath_yin)
# scale_per_chakra: [C] — learnable, per-chakra condensation scale
```

### Benefits

- **Adaptive learning rate**: The model learns when to solidify patterns based on their predictive value.
- **Catastrophic forgetting protection**: Low-Qi periods get smaller updates, preserving existing knowledge.
- **Chakra-specific**: Each chakra gets its own condensation rate, reflecting its role (root = slow/solid, crown = fast/plastic).

---

## 9. Research Infrastructure Needed

To support these projects, the following infrastructure should be built:

1. **Checkpoint comparison tool**: Compare two checkpoints (before/after training) — which weights changed most? Which chakras learned? Used to validate that self-supervised objectives have the intended effect.
2. **Field visualization**: Project the field state at each chakra into 2D (PCA/UMAP) and visualize evolution over streaming windows. Shows whether the field develops meaningful structure or collapses.
3. **Qi-per-position tracking**: Track Qi at each position across streaming windows. Identifies which parts of a file are "surprising" to the model — useful for debugging and for adaptive anchor placement.
4. **Memory utilization metrics**: Track pattern memory hit rate, episode memory hit rate, IIR decay rate — provides quantitative measures of how well each memory tier is working.
5. **Synthetic benchmarks**: Small, generated datasets that test specific capabilities:
   - **Long-range copy**: Token at position 0 must be predicted at position 10K. Tests streaming context retention.
   - **Hierarchical structure**: Nested brackets/parens. Tests chakra multi-scale processing.
   - **Pattern completion**: Partial pattern → full pattern. Tests field inpainting for parallel generation.
