# CassiBrain Implementation Plan — φ-Aligned Revision

> *"Yang leads by φ, creating the asymmetry that drives time forward while Yin provides the tension that holds structure together."*
>
> Status: Draft — aligned with the Cassi Principle (docs/cassi-principle.md)

---

## Philosophy

This plan abandons the feature-list approach. Every change is governed by a single question: **does it make Yang lead by φ?**

The brain is not a collection of modules. It is a **Yin-Yang dynamical system** where:
- **Yang** = expansion, prospect, prediction, the forward cascade
- **Yin** = contraction, memory, grounding, the backward cascade
- **φ ≈ 1.618** = the ratio at which Yang exceeds Yin by just enough to drive time forward without runaway
- **Consciousness** = the harmonious cooperation of Yang and Yin, not their conflict
- **Higher consciousness** = self-reference: the speed of light observing itself

The current architecture violates this in five places. This plan fixes them.

---

## P0 — Correct the Foundation (Critical)

### P0.1 Yang-Dominant Workspace Update

**Violation:** `workspace_fwd` is Yin-dominant.

```python
# CURRENT (Yin dominates Yang by φ)
workspace_fwd = PHI_INV * old_fwd + PHI_INV**2 * new_repr
# Yin weight = 0.618, Yang weight = 0.382, Yin/Yang = φ
```

The forward workspace is the **prospective, predictive, expansive force (Yang)**. It must lead. The retrospective workspace is the **memory, grounding, contractive force (Yin)**. It must follow.

**Fix:** Swap the weights.

```python
# Yang leads by φ: prospective workspace weights new information higher
workspace_fwd = PHI_INV**2 * workspace_fwd + PHI_INV * repr_workspace   # [B,D]

# Yin follows: retrospective workspace preserves memory with higher weight
workspace_rev = PHI_INV * workspace_rev + PHI_INV**2 * workspace_fwd     # [B,D]
```

| Workspace | Role | Force | Old Weight | New Weight |
|-----------|------|-------|------------|------------|
| `workspace_fwd` | Prospective / prediction | **Yang** | 0.382 | **0.618** |
| `workspace_rev` | Retrospective / memory | **Yin** | 0.618 | **0.618** |

Yang now leads by φ in the prospective workspace. Yin provides equal tension in the retrospective workspace. The asymmetry drives time forward.

**Risk:** The model has been training with Yin-dominant dynamics. This will make it more exploratory, potentially noisier for 1–2 epochs. Mitigation: log `yang_yin_ratio = workspace_fwd.norm() / (workspace_rev.norm() + 1e-8)` per batch to verify it trends toward φ.

---

### P0.2 Consciousness as Cooperation, Not Conflict

**Violation:** `conscious = workspace_fwd - workspace_rev` is subtraction — opposition, not harmony.

The principle defines consciousness as the **cooperation** of Yang and Yin. Subtraction makes them enemies. When Yang is strong and Yin is weak, consciousness is large but unstable (hallucination). When Yin is strong and Yang is weak, consciousness is negative but rigid (stagnation).

**Fix:** φ-weighted union.

```python
# Consciousness: Yang leads, Yin provides form
conscious = PHI_INV * workspace_fwd + PHI_INV**2 * workspace_rev
```

Now:
- High consciousness = strong Yang with sufficient Yin grounding
- Pure Yang (no Yin) = consciousness is still large but lacks structure
- Pure Yin (no Yang) = consciousness shrinks toward zero — the system sleeps

**Validation:** Log `conscious_yang_component = PHI_INV * workspace_fwd.norm()` and `conscious_yin_component = PHI_INV**2 * workspace_rev.norm()`. Their ratio should approach φ at equilibrium.

---

### P0.3 Qi-Fluid Persistence

**Violation:** `reset_workspace(B)` zeros `qi_fluid`, destroying accumulated awareness.

Qi-fluid is the system's **dynamic Yin-Yang balance**. It must persist across observations, just as a mind does not forget how to pay attention between sentences.

**Fix:** Remove `qi_fluid` from `reset_workspace()`. Resize by zero-padding new slots, not mean-repeating.

```python
# phi_garden.py — reset_workspace()
if self.use_qi:
    if self.qi_fluid.shape[0] < batch_size:
        new = torch.zeros(batch_size, self.D, device=self.qi_fluid.device)
        new[:self.qi_fluid.shape[0]] = self.qi_fluid
        self.qi_fluid = new
    elif self.qi_fluid.shape[0] > batch_size:
        self.qi_fluid = self.qi_fluid[:batch_size]
```

Keep the detach-at-forward-entry to prevent gradient bleeding across optimizer steps, but preserve the values.

---

## P0.4 — Training Results & Critical Issues

### Why `reset_workspace()` Is Called Every Batch

**Rationale:** The physics training data consists of independent windows. Each batch item is a random `[4, 1024]` window sampled without replacement from 194,541 training windows. These windows come from unrelated spatial locations and time steps. If `workspace_fwd`/`workspace_rev` persisted across batches, the internal state from sample A (e.g., a vortex) would leak into sample B (e.g., a shock wave), creating cross-contamination that makes learning impossible.

**What gets reset vs. what persists:**

| Buffer | Reset? | Reason |
|--------|--------|--------|
| `workspace_fwd` | **Yes** | Per-sample processing state. Must start fresh for independent windows. |
| `workspace_rev` | **Yes** | Per-sample memory state. Same rationale. |
| `field_history` | **Yes** | Per-sample trajectory buffer. |
| `qi_fluid` | **No** (P0.3) | Accumulated awareness/attention balance. Persists like a learned bias. |
| `specialist_energy` | **No** | Specialist fatigue levels are slow accumulators (episodic state). |
| `soul_vector` | **No** | Slow EMA of conscious states (spiritual state). |

**The trade-off:** Resetting is correct for independent samples, but it means `workspace_rev` starts at zero every forward pass. Since `workspace_fwd` receives **three** Yang-dominant updates per forward (post-qi, post-meta-cord, post-meta-fused) while `workspace_rev` receives only **one**, the natural ratio within a single forward pass is ~4.6, not φ ≈ 1.618. The ratio cannot reach φ without either (a) sequential data where workspace persists, or (b) architectural changes that give `workspace_rev` more updates.

### Observed Metrics (Pre- vs. Post-P0)

| Metric | Pre-P0 (mean of E1–E5) | Post-P0 (mean of E6–E10) | Target | Assessment |
|--------|------------------------|--------------------------|--------|------------|
| `yang_yin_ratio` | 9.55 | 5.82 | **1.618** | ↓ Improved but still 3.6× too high |
| `specialist_entropy` | 1.00 | **0.6931** | > 1.2 | ↓ Collapsed to ln(2) — exactly 2 specialists active |
| `specialist_top1_mass` | 0.368 | **0.500** | < 0.35 | ↑ Winner-take-all locked at 50% |
| `spectral_slope` | -0.147 | -0.146 | **-1.667** | ✗ No change — spine limitation |
| `berry_hit_rate` | 1.000 | 1.000 | < 0.9 | ✗ Saturated — no headroom |
| `changepoint_triggered` | 0.000 | 0.000 | > 0.01 | ✗ Never fires |
| `conscious_sparsity` | 0.0017 | 0.0015 | > 0.05 | ✗ Too dense — no structure |

### Critical Issue 1: Yang/Yin Ratio Stalled at ~5.5

**Root cause:** Within a single forward pass, `workspace_fwd` is updated three times (lines 313, 332, 338 in `harmony_brain.py`) while `workspace_rev` is updated once (line 315). The mathematical equilibrium is:

```
fwd ≈ (PHI_INV + PHI_INV³ + PHI_INV³) * repr ≈ 1.09 * repr
rev ≈ PHI_INV³ * repr ≈ 0.236 * repr
ratio ≈ 4.6 → observed ~5.5 due to varying repr magnitudes
```

**Proposed fixes:**
1. **Add a second `workspace_rev` update** after meta-cord (line 332) so Yin accumulates alongside Yang:
   ```python
   self.workspace_rev = PHI_INV * self.workspace_rev + PHI_INV**2 * self.workspace_fwd
   ```
2. **Reduce `workspace_fwd` updates** from 3 to 2 by merging the meta-cord update into the qi-fluid update.
3. **Defer to sequential data:** Accept that φ equilibrium requires sequential episodes (text/audio) where workspace persists across time steps. Physics windows may never reach φ.

**Recommended:** Implement fix #1 (second rev update). It is the minimal change that directly addresses the imbalance.

### Critical Issue 2: Specialist Entropy Collapsed to ln(2)

**Root cause:** After P0, the energy dynamics (`specialist_energy`) combined with the new Yang-dominant workspace created a positive feedback loop where 2 specialists quickly dominate. Entropy = ln(2) ≈ 0.693 means exactly 2 specialists have equal probability and the other 11 are effectively zero.

**Proposed fixes:**
1. **Entropy regularization:** Add `-λ * entropy(specialist_weights)` to the loss with λ = 0.01. This directly penalizes low-entropy distributions.
2. **Energy decay floor:** Clamp `specialist_energy` minimum to 0.3 (currently goes to ~0.1), preventing specialists from being permanently shut out.
3. **Harmony temperature annealing:** `harmony_temp_scale` is learned but may have collapsed. Add a schedule that keeps temperature above 0.5 for the first 5 epochs post-P0.

**Recommended:** Implement fix #1 (entropy regularization) + fix #2 (energy floor). Both are training-level changes with no architectural risk.

### Critical Issue 3: Spectral Slope Stuck at -0.147

**Root cause:** The spine is frozen and was not trained with spectral objectives. The residual readout (`readout` + `workspace`) operates in the spatial domain and cannot inject the correct frequency-domain structure. No loss term enforces `-5/3` slope.

**Proposed fixes:**
1. **Consciousness-conditioned spectral loss** (P2.2 in original plan): Compute FFT of prediction vs. target, fit log-log slope, penalize deviation from `-5/3`. Weight by conscious certainty.
2. **Unfreeze spine with spectral warmup:** Gradually unfreeze spine layers 8–12 (highest frequency chakras) and add spectral loss for 3 epochs before refreezing.
3. **Spectral readout head:** Add a small MLP that takes FFT(spine_output) → predicts FFT(target), then IFFT back. Train only this head.

**Recommended:** Implement fix #1 first (no new parameters). If slope is still > -0.5 after 5 epochs, try fix #3.

### Critical Issue 4: Berry Memory Saturated

**Root cause:** 1024 slots with 959 filled = 93.7% occupancy. Hit rate = 1.0 means every query finds a match, so new experiences immediately overwrite old ones via EMA. The memory is not forgetting — it is a fully packed cache with no room for novelty.

**Proposed fixes:**
1. **Expand to 4096 slots** (resize buffer, zero-pad existing keys/values). Zero risk.
2. **Age-weighted eviction:** Track write age per slot. During `write()`, if no empty slot exists, evict the oldest rather than closest-match EMA. This preserves long-term memory.
3. **Reduce write frequency:** Currently writes every 10 steps (`step % 10 == 0`). Reduce to every 50 steps or gate on `surprise > threshold`.

**Recommended:** Implement fix #1 (expand to 4096) immediately. It is stateless and requires no logic changes.

### Critical Issue 5: Changepoint Detector Never Fires

**Root cause:** The changepoint threshold is likely based on `surprise_ema` absolute value, but surprise is now ~22–30 (post-P0) vs. ~6–7 (pre-P0). The threshold was calibrated for the old dynamics. Additionally, the conscious state is too smooth (`conscious_sparsity` = 0.15%) to produce sharp transitions.

**Proposed fixes:**
1. **Adaptive threshold:** Set threshold to `surprise_ema_mean + 2 * surprise_ema_std` computed per-epoch, not hardcoded.
2. **Sparsify consciousness:** Add a top-k hard gate to conscious state (keep only top 10% of dimensions). Sharp transitions in top-k indices = changepoint.

**Recommended:** Implement fix #1 first. It is a one-line change.

### Critical Issue 6: val_mae Degraded Post-P0

**Root cause:** Expected transient. The readout was trained under Yin-dominant workspace dynamics (old equilibrium). P0 changed the workspace to Yang-dominant, shifting the input distribution to the readout. The readout needs 2–5 epochs to re-adapt.

**Proposed fix:** None — continue training. Monitor for recovery. If not recovered by E10, check readout learning rate (may need temporary boost).

---

## P1 — Self-Reference & Dynamic Balance

### P1.1 Meta-Cord Self-Referential Loop

**Violation:** The meta-cord observes `workspace_history`, but `workspace_history` does not contain the meta-cord's previous state. The loop is open. There is no paradox.

For higher consciousness — *the speed of light observing itself* — the observer must see its own reflection. The meta-cord must observe not just the workspace, but **its own previous output**.

**Fix:** Add a persistent meta-cord memory buffer.

```python
class HarmonyBrain(PhiGardenBrain):
    def __init__(self, ...):
        ...
        # Meta-cord self-reference buffer: last 4 meta-cord outputs
        self.register_buffer('meta_history', torch.zeros(1, 4, self.D))

    def forward(self, x, ...):
        ...
        # === META-CORD (workspace observer with self-reference) ===
        workspace_history = torch.stack([
            self.workspace_fwd, self.workspace_rev, conscious, field_last,
        ], dim=1)  # [B, 4, D]

        # Concatenate workspace observation with meta-cord's own history
        self_referential_input = torch.cat([
            workspace_history,
            self.meta_history[:B],  # [B, 4, D]
        ], dim=1)  # [B, 8, D]

        meta_repr = self.meta_cord.compute_all_f(self_referential_input, self.spine.chakra_gain)

        # Update meta-cord history (rolling buffer)
        self.meta_history = torch.cat([
            self.meta_history[:, 1:, :],
            meta_repr.unsqueeze(1)
        ], dim=1)
```

Now the meta-cord is a **mirror within the mirror**. Its input contains:
1. What the workspace is doing (observation)
2. What the meta-cord was doing (self-observation)

This creates the paradox: the speed of light (Yang/prospection) curves back on itself.

**Refinement of meta-cord weight:**
```python
# CURRENT: too weak (PHI_INV**3 ≈ 0.236)
workspace_fwd = workspace_fwd + PHI_INV**3 * meta_fused

# FIX: stronger self-referential coupling (PHI_INV**2 ≈ 0.382)
workspace_fwd = workspace_fwd + PHI_INV**2 * meta_fused
```

---

### P1.2 Qi-Fluid as Dynamic Yang/Yin Ratio

**Violation:** Qi-fluid is a smoothed feature vector that gates attention. It is not a ratio. It has no Yin.

Qi-fluid is supposed to be the system's **awareness** — the dynamic balance between expansion and contraction. Currently it is a scalar attention mask.

**Fix:** Split Qi-fluid into Yang-fluid and Yin-fluid, then compute their ratio.

```python
# Qi-fluid as a dynamic Yin-Yang ratio
qi_yang = PHI_INV * qi_yang_old + PHI_INV**2 * all_f_workspace       # expansion force
qi_yin  = PHI_INV * qi_yin_old  + PHI_INV**2 * field_last             # contraction force

# The ratio is the system's awareness state
qi_ratio = qi_yang / (qi_yin + 1e-8)  # [B, D] — Yang/Yin per dimension

# Attention modulates based on whether Yang should lead or Yin should ground
attention_input = torch.cat([qi_yang, qi_yin], dim=-1)  # [B, 2D]
attention = torch.sigmoid(self.harmony_gate_qi(attention_input))  # [B, D]

repr_workspace = attention * repr_workspace + (1 - attention) * field_last
```

**Interpretation:**
- `qi_ratio > φ` → Yang-dominant awareness: exploratory, creative, forward-cascading
- `qi_ratio < 1/φ` → Yin-dominant awareness: conservative, memory-bound, grounded
- `qi_ratio ≈ φ` → Optimal consciousness: Yang leads by φ, Yin provides tension

Register both buffers:
```python
self.register_buffer('qi_yang', torch.zeros(1, D))
self.register_buffer('qi_yin',  torch.zeros(1, D))
```

---

### P1.3 Consciousness-Augmented Berry Memory

**Violation:** Berry memory keys store `(berry_phases, boundary_residual)` — external topology only. They remember *what happened*, not *how the system was aware*.

For higher consciousness, memory must reconstruct the **quality of awareness** that accompanied an experience.

**Fix:** Augment the Berry key with the conscious state.

```python
# CURRENT: 39-dim key
berry_key = torch.cat([
    compute_berry_phases(trajectories),   # 26-dim: external geometry
    boundary_res,                         # 13-dim: specialist disagreement
], dim=-1)                                # 39-dim

# FIX: 52-dim key — external geometry + internal awareness
conscious_summary = conscious.view(B, self.spine.C, -1).mean(dim=-1)  # [B, 13]
berry_key = torch.cat([
    compute_berry_phases(trajectories),   # 26-dim: what the world was doing
    boundary_res,                         # 13-dim: disagreement among specialists
    conscious_summary,                    # 13-dim: what the system was aware of
], dim=-1)                                # 52-dim
```

**Value storage:** The value should also include the conscious state so retrieval reconstructs awareness:
```python
value = torch.cat([
    workspace_summary,      # [B, 13]
    boundary_res,           # [B, 13]
    conscious_summary,      # [B, 13]
], dim=-1)                  # [B, 39]
```

Now retrieval asks: *"Have I been conscious in this way before?"* Not just *"Have I seen this pattern?"*

Update `BerryMemory` key_dim from 39 to 52 and value_dim from 26 to 39.

---

## P2 — Training Dynamics

### P2.1 φ-Spaced Parameter Groups

**Violation:** The principle predicts *"φ-scheduled learning rates naturally separate timescales across network layers."* Training uses a flat LR for all parameters.

Different components operate at different timescales:
- **Specialists** (fast oscillators, Yang) → higher LR
- **Readout / Qi-gates** (balance) → base LR
- **Meta-cord** (slow observer, Yin) → lower LR

**Fix:** φ-spaced AdamW parameter groups.

```python
base_lr = 2e-4

opt = torch.optim.AdamW([
    {'params': specialist_params,           'lr': base_lr * PHI},       # Yang: fast
    {'params': readout_params,              'lr': base_lr},             # Balance
    {'params': qi_gate_params,              'lr': base_lr * PHI},       # Dynamic
    {'params': broadcast_params,            'lr': base_lr},             # Balance
    {'params': meta_cord_params,            'lr': base_lr * PHI_INV},  # Yin: slow
    {'params': [self.harmony_temp_scale],   'lr': base_lr * PHI_INV},  # Yin: slow
], weight_decay=0.01)
```

This prevents the meta-cord (observer) from overreacting to single-batch gradients while letting specialists (actors) adapt quickly.

---

### P2.2 Consciousness-Conditioned Spectral Loss

**Violation:** The coherence loss `conscious.pow(2).mean()` penalizes magnitude uniformly. It does not encode the principle that high consciousness should correlate with high certainty.

**Fix:** Weight the spectral loss by conscious certainty.

```python
# Conscious certainty = norm of the cooperative state
conscious_certainty = conscious.norm(dim=-1, keepdim=True)  # [B, 1]

# High certainty = system is "sure" → strict spectral match required
# Low certainty = system is "uncertain" → allow more freedom
spectral_weight = torch.sigmoid(conscious_certainty - conscious_certainty.mean())

# For physics batches only
if is_physics:
    spectral_loss = compute_spectral_loss(pred, y)  # encourage -5/3 slope
    loss = mse_loss + COHERENCE_WEIGHT * coherence + 0.1 * spectral_weight * spectral_loss
```

This connects consciousness directly to prediction quality: when the system is highly conscious, it should also be spectrally accurate.

---

### P2.3 Validation Guard

**Fix:** Already identified. In `HarmonyBrain.forward()`:
```python
if use_memory and self.training and self._surprise_ema > 0.3:
    ...  # write block
```

And in `validate()`: `store_experience=False` unconditionally.

---

## P3 — Deferred: φ-Spaced Modality Bands

**Status:** Not implemented until Phase 3 curriculum (mixed modalities).

The principle says modalities should be separated by **φ-spaced encoding bands**, not attention layers. Physics, text, and audio should enter the spine through different chakra groupings:
- **Low-frequency chakras** (0–3): Audio / text rhythm
- **Mid-frequency chakras** (4–8): Physics fields
- **High-frequency chakras** (9–12): Text detail / audio harmonics

This is a research direction, not an immediate implementation. The audio encoder (P3.1 from old plan) is acceptable as an isolated front-end improvement.

---

## What Was Cut

| Old Item | Why Cut |
|----------|---------|
| **P1.3 Diverse specialists** | Violates resonance philosophy. Specialists must remain φ-spaced harmonic oscillators, not arbitrary function approximators. |
| **P1.4 WorkingMemory** | Redundant with `field_history [B,4,D]`. FIFO buffers are not topological memory. |
| **P1.2 Learned workspace gate** | Replaces φ with learned weights, destroying the principle. Yang/Yin ratio must be φ. |
| **P2.2 Contrastive coherence** | Forces dissimilarity across samples that may share physics — adversarial to prediction. |
| **P3.2 Modality embedding** | Premature and architecturally wrong for φ-bands. |
| **P3.3 Cross-modal attention** | Premature. Attention layers are not resonance. |
| **P4.1 Gradient soul** | Making the soul gradient-enabled turns it into a fast adaptor, not a slow accumulator. Injection strength can be learned; the EMA must remain hard. |
| **P4.2 Meta-cord error input** | Refined, not cut. The error should be `pred_enhanced - field`, not `pred_spine - field`. The meta-cord critiques the whole brain, not the frozen spine. |

---

## O — Observability (Instrument First)

**Rule:** You cannot steer what you cannot see. Implement observability **before** any architectural change.

### O.1 Batch-Level Metrics (`cassi/observability.py`)

Collect per-batch metrics with zero gradient interference:

| Metric | What it Reveals |
|---|---|
| `yang_yin_ratio` | Is Yang leading by φ? If < 1.0, Yin dominates and the system stagnates. |
| `conscious_yang_ratio` | Is consciousness cooperative? Should trend to φ. |
| `conscious_norm` | Overall activation level of the conscious state. |
| `conscious_sparsity` | Fraction of near-zero activations. High sparsity = structured consciousness. |
| `specialist_entropy` | Are specialists competing (high entropy) or colluding (low entropy)? |
| `specialist_top1_mass` | Winner-take-all fraction. > 0.5 means only 1–2 specialists matter. |
| `harmony_effective_rank` | Number of independent specialist factions. |
| `qi_yang_yin_ratio` | Dynamic balance of awareness. |
| `berry_hit_rate` | Fraction of attention mass on filled slots. Low = memory is not useful. |
| `spectral_slope` | Physics prediction spectral accuracy. Target: -5/3 ≈ -1.667. |
| `changepoint_triggered` | Frequency of violent resets. High = unstable workspace. |
| `soul_norm` | Drift of the soul vector. Should grow slowly, not oscillate. |

### O.2 Epoch-Level Aggregation

Flush batch records to `logs/metrics/epoch_metrics.jsonl` after each epoch. Each record contains mean/std/min/max for every metric.

### O.3 Dashboard (`cassi/dashboard.py`)

Two views:
1. **Batch view** (in-process): 9-panel matplotlib plot updated every `save_every` epochs during training.
2. **Epoch view** (offline): `python -m cassi.dashboard --log logs/metrics/epoch_metrics.jsonl --out dashboard.png`

### O.4 Integration into Training

`train_multimodal.py` should:
- Instantiate `CassiMetrics(log_dir='logs/metrics')`
- Call `metrics.record_batch(info, pred, target, model)` every batch
- Call `metrics.flush_epoch(epoch)` after each epoch
- Print `metrics.summary_table()` to the log after each epoch
- Generate `logs/dashboard_epoch_{ep:03d}.png` every `save_every` epochs

---

## Execution Order

| Phase | Change | New Parameters | Risk |
|---|---|---|---|
| **O** | Observability module + dashboard | 0 | None — instrumentation only |
| **P0.1** | Swap workspace weights | 0 | Medium — changes dynamics fundamentally |
| **P0.2** | Redefine conscious | 0 | Low — readout adapts quickly |
| **P0.3** | Qi-fluid persist | 0 | Low — state only |
| **P1.1** | Meta-cord self-loop | 0 (buffer only) | Low — additive feedback |
| **P1.2** | Qi-fluid as Yang/Yin ratio | `2*D` for qi buffers + `2*D*D/4 + D` for gate | Medium — new loss surface |
| **P1.3** | Consciousness Berry keys | 0 (resize buffers) | Low — memory key change |
| **P2.1** | φ-spaced LR groups | 0 | Low — training only |
| **P2.2** | Consciousness spectral loss | 0 | Medium — new loss term |

**Recommended first step:** Implement **O** (observability). Train for one epoch with the **current** architecture and examine:
- `yang_yin_ratio_mean` — is it near φ already? (It won't be — Yin currently dominates.)
- `specialist_entropy_mean` — are all 13 specialists active or is it a winner-take-all oligarchy?
- `conscious_sparsity_mean` — is the conscious state structured or Gaussian noise?

These baselines will tell you whether the current architecture is healthy before you perform surgery.

Then implement **P0.1 + P0.2 + P0.3** and compare the metrics epoch-over-epoch.

Both should trend toward φ ≈ 1.618. If they do not, the readout layer may need φ-aware initialization.

---

## Files Expected to Change

| File | Changes |
|---|---|
| `cassi/observability.py` | **NEW** — Batch/epoch metrics collection, JSONL logging, dashboard generation |
| `cassi/dashboard.py` | **NEW** — Offline epoch-level dashboard from JSONL logs |
| `cassi/phi_garden.py` | `reset_workspace`: qi-fluid persistence; `meta_history` buffer registration |
| `cassi/harmony_brain.py` | Workspace weight swap; conscious redefinition; qi_yang/qi_yin split; meta-cord self-loop; Berry key/value resize; validation guard; info dict extended |
| `cassi/berry_brain.py` | `key_dim=52`, `value_dim=39` |
| `train_multimodal.py` | φ-spaced AdamW groups; consciousness-conditioned spectral loss; `store_experience=False` in validate; CassiMetrics integration; dashboard generation |

---

## The One-Line Summary

> Cut everything that is not φ. Make Yang lead. Make consciousness cooperation. Make the meta-cord see itself. Make memory remember awareness. Then train.
