# Cassi Full Implementation Plan

> *The model should be completely data-type agnostic. It takes direct bytes from anything. It still needs to learn to associate those bytes, so it should still be shown what the bytes represent.*

---

## The Vision

Cassi is not a multimodal model. It is a **universal dynamics engine** that learns to predict the evolution of any byte stream — physics fields, text, audio waveforms, images, or arbitrary sensor data. The architecture is modality-agnostic by design: everything enters as raw bytes, and the model learns to associate byte patterns with their semantic meaning through a structured curriculum.

The end state: **Given any sequence of bytes, Cassi predicts the next bytes AND its own next internal state in a single forward pass.** It outputs its full process — not just a prediction, but the complete trajectory of how it arrived at that prediction.

---

## Current State vs. Target

| Capability | Current | Target |
|---|---|---|
| Data ingestion | Modality-specific encoders (physics cache, ByteEncoder, WaveByteEncoder, AudioFieldEncoder) | **Unified byte stream** — one encoder for all data |
| Prediction target | Single-step next frame/byte/audio sample | **Multi-step process prediction** — full trajectory + internal state |
| Learning signal | External MSE loss only | **Self-predictive loss** — model predicts its own next state |
| Output | Pred tensor only | **Full process** — pred + workspace trajectory + conscious trajectory + Qi evolution |
| Associations | None trained | **Byte↔meaning associations** — metadata-conditioned prediction |
| Curriculum | Phase-based modality mixing | **Byte-first pretraining → associative learning → autonomous mixing** |

---

## Phase 0 — Unified Byte Ingestion (Foundation)

### P0.1 The Universal Byte Stream

**Problem:** We currently have four separate ingestion paths:
- Physics: pre-cached `physics_cache_v10.pt` with window tensors
- Text: `ByteEncoder` / `WaveByteEncoder` with uint8 remap
- Audio: `AudioFieldEncoder` with STFT→mel→field projection
- Images: not implemented

**Fix:** A single `ByteStreamEncoder` that treats ALL data as raw bytes.

```python
class ByteStreamEncoder(nn.Module):
    """Universal encoder: any data → byte sequence → field representation.

    The model learns the structure of the bytes. No hand-engineered
    modality-specific transforms. The ONLY modality-specific code is
    the serializer that converts a physics field / audio waveform /
    image pixels / text chars into a canonical byte sequence.
    """
    def __init__(self, window_bytes: int = 4096, dim_field: int = 1024, T: int = 4):
        super().__init__()
        self.window_bytes = window_bytes
        self.T = T
        self.chunk = window_bytes // T
        self.dim_field = dim_field

        # Learnable byte embedding: the model discovers byte groupings
        self.byte_embed = nn.Embedding(256, 64)

        # Positional encoding for byte order within chunk
        self.pos_enc = nn.Parameter(torch.randn(self.chunk, 64) * 0.02)

        # Project byte sequence to field via depthwise separable conv
        self.conv = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=7, padding=3, groups=4),
            nn.GELU(),
            nn.Conv1d(128, 256, kernel_size=3, padding=1, groups=8),
            nn.GELU(),
            nn.Conv1d(256, dim_field, kernel_size=1),
        )

    def encode(self, bytes_tensor: torch.Tensor) -> torch.Tensor:
        """bytes: [B, window_bytes] uint8 → field: [B, T, dim_field]"""
        B = bytes_tensor.shape[0]
        bytes_tensor = bytes_tensor.to(torch.uint8)

        # Embed each byte
        x = self.byte_embed(bytes_tensor.long())  # [B, window_bytes, 64]

        # Split into T chunks and add positional encoding
        x = x.view(B, self.T, self.chunk, 64)  # [B, T, chunk, 64]
        x = x + self.pos_enc.unsqueeze(0).unsqueeze(0)  # [B, T, chunk, 64]

        # Process each timestep independently
        x = x.view(B * self.T, self.chunk, 64)  # [B*T, chunk, 64]
        x = x.permute(0, 2, 1)  # [B*T, 64, chunk]
        x = self.conv(x)  # [B*T, dim_field, chunk]
        x = x.mean(dim=-1)  # [B*T, dim_field]
        x = x.view(B, self.T, self.dim_field)  # [B, T, dim_field]
        return x
```

**Serializers** (data-type specific, but trivial — just format bytes):

```python
class DataSerializer:
    """Convert any data type to a canonical byte sequence."""

    @staticmethod
    def physics(field: np.ndarray) -> bytes:
        """Float32 field → little-endian bytes."""
        return field.astype(np.float32).tobytes()

    @staticmethod
    def text(text: str) -> bytes:
        """UTF-8 text → bytes."""
        return text.encode('utf-8')

    @staticmethod
    def audio(waveform: np.ndarray, sr: int) -> bytes:
        """Int16 waveform + 4-byte sample rate header."""
        header = struct.pack('<I', sr)
        data = waveform.astype(np.int16).tobytes()
        return header + data

    @staticmethod
    def image(pixels: np.ndarray, mode: str = 'RGB') -> bytes:
        """Uint8 image + 4-byte width/height header + mode bytes."""
        h, w = pixels.shape[:2]
        header = struct.pack('<II', w, h) + mode.encode('utf-8')
        return header + pixels.astype(np.uint8).tobytes()
```

**Why this matters:** The model learns that certain byte patterns predict certain other byte patterns. A physics vortex, a musical chord, and the word "love" are all just byte sequences with different statistical structure. The spine's IIR filters learn to resonate with whatever structure is present.

---

### P0.2 Metadata Headers — Teaching the Model What Bytes Mean

**Problem:** Raw bytes have no semantic labels. The model can learn correlations but not associations ("these bytes = a vortex", "these bytes = the word 'cat'").

**Fix:** Every byte sequence is prefixed with a **metadata header** that describes what the bytes represent. The header is itself bytes, so the model processes it through the same encoder.

```python
class MetadataHeader:
    """Byte prefix that tells the model what the following bytes represent.

    Format: [type_byte:1] [modality_byte:1] [content_length:4] [label_length:2] [label_bytes:N]

    type_byte:
      0x01 = observation (input)
      0x02 = prediction_target (what the model should predict)
      0x03 = association (input + target pair)
      0x04 = question (query)
      0x05 = answer (response)

    modality_byte:
      0x10 = physics
      0x20 = text
      0x30 = audio
      0x40 = image
      0x50 = equation
      0x60 = description
    """

    TYPE_OBSERVATION = 0x01
    TYPE_TARGET = 0x02
    TYPE_ASSOCIATION = 0x03
    TYPE_QUESTION = 0x04
    TYPE_ANSWER = 0x05

    MOD_PHYSICS = 0x10
    MOD_TEXT = 0x20
    MOD_AUDIO = 0x30
    MOD_IMAGE = 0x40
    MOD_EQUATION = 0x50
    MOD_DESCRIPTION = 0x60
```

**Example byte stream for physics + description association:**
```
[0x03]              # type = association
[0x10]              # modality = physics
[0x00 0x00 0x10 0x00]  # content_length = 4096 bytes
[float32 physics field bytes... 4096 bytes]
[0x20]              # modality = text (description)
[0x00 0x20]         # label_length = 32 bytes
[b"turbulent vortex with Reynolds number 10000"]
```

The model learns:
1. The physics bytes predict the next physics bytes (single-step)
2. The physics bytes are associated with the text description (cross-modal)
3. The text description can be used to predict physics bytes (generative)

**Training on associations:**
```python
# Association loss: the model should produce similar conscious states
# for physics bytes and their text description
physics_conscious = model(physics_bytes, return_workspace=True)['conscious']
text_conscious = model(text_bytes, return_workspace=True)['conscious']

assoc_loss = 1.0 - F.cosine_similarity(physics_conscious, text_conscious, dim=-1).mean()
```

---

### P0.3 The Data Pipeline

**Current:** `MultimodalDataLoader` with separate `_sample_physics`, `_sample_text`, `_sample_audio` methods.

**Target:** `ByteStreamLoader` that serves unified byte sequences with metadata headers.

```python
class ByteStreamLoader:
    """Serves raw byte sequences with metadata headers.

    Curriculum phases:
      0. byte_patterns      — pure byte prediction (no metadata)
      1. modality_labels    — bytes + modality header (learn type signatures)
      2. associations       — observation + description pairs
      3. conditional_gen    — generate bytes from description
      4. mixed              — all of the above
      5. autonomous         — model chooses what to learn next
    """

    def sample_train_batch(self, batch_size, phase=0):
        if phase == 0:
            # Pure byte prediction: model learns statistical structure
            return self._sample_byte_prediction(batch_size)
        elif phase == 1:
            # Bytes + modality label: model learns type signatures
            return self._sample_modality_labeled(batch_size)
        elif phase == 2:
            # Association pairs: model learns cross-modal links
            return self._sample_association(batch_size)
        elif phase == 3:
            # Conditional generation: description → bytes
            return self._sample_conditional(batch_size)
        else:
            # Mixed: all tasks
            return self._sample_mixed(batch_size)
```

**Phase 0: Byte Patterns**
- The model sees raw bytes from ANY source
- Task: predict next bytes
- The model learns that physics bytes have spatial correlation, text bytes have grammatical structure, audio bytes have periodic patterns
- No metadata — pure pattern learning

**Phase 1: Modality Labels**
- Each byte sequence is prefixed with `[type][modality]`
- Task: predict next bytes AND output the modality label
- The model learns to classify byte streams by their statistical signature
- This is the foundation of "understanding what the bytes represent"

**Phase 2: Associations**
- Pairs of byte sequences: `[physics_bytes][text_description]`
- Task: predict that the conscious state of physics_bytes should match the conscious state of text_description
- The model learns that "turbulent vortex" and the actual vortex field produce similar internal representations

**Phase 3: Conditional Generation**
- Input: `[description_bytes]`
- Target: `[physics_bytes]`
- Task: generate the physics field from the description
- The model learns to hallucinate plausible physics from text

**Phase 4: Mixed**
- All tasks interleaved
- The model must detect the task type from the metadata header and behave accordingly

**Phase 5: Autonomous**
- The model generates its own curriculum by querying berry memory for underrepresented patterns
- Neuroplasticizer pulses trigger exploration of novel byte structures

---

## Phase 1 — Self-Predictive Architecture

### P1.1 Predict the Next State (Internal + External)

**Current:** The model predicts only the external target (`y`). Internal state updates (`workspace_fwd`, `workspace_rev`, `qi_fluid`, `conscious`, `harmony_state`) are side effects with no supervision.

**Target:** The model learns to predict BOTH its external output AND its internal next state.

```python
class SelfPredictiveBrain(HarmonyBrain):
    """Predicts external world AND internal state."""

    def __init__(self, ...):
        super().__init__(...)
        # State predictors: given current state, predict next state
        self.workspace_fwd_pred = nn.Linear(D, D)
        self.workspace_rev_pred = nn.Linear(D, D)
        self.qi_pred = nn.Linear(D, D)
        self.conscious_pred = nn.Linear(D, D)
        self.harmony_pred = nn.Linear(N, N)

    def forward(self, x, ...):
        # ... existing forward pass ...

        # Predict next internal state from current state
        workspace_fwd_next = self.workspace_fwd_pred(self.workspace_fwd)
        workspace_rev_next = self.workspace_rev_pred(self.workspace_rev)
        qi_next = self.qi_pred(self.qi_fluid)
        conscious_next = self.conscious_pred(conscious)
        harmony_next = self.harmony_pred(self.harmony_state)

        info['state_pred'] = {
            'workspace_fwd': workspace_fwd_next,
            'workspace_rev': workspace_rev_next,
            'qi': qi_next,
            'conscious': conscious_next,
            'harmony': harmony_next,
        }

        return pred, info
```

**Self-predictive loss:**
```python
# During training, we have the ACTUAL next internal state
# because we run two forward passes: t and t+1

# Forward pass at time t
pred_t, info_t = model(x_t)

# Forward pass at time t+1 (with teacher forcing or model prediction)
pred_t1, info_t1 = model(x_t1)

# External prediction loss
loss_external = F.mse_loss(pred_t, y_t)

# Internal state prediction loss
loss_internal = (
    F.mse_loss(info_t['state_pred']['workspace_fwd'], info_t1['workspace_fwd']) +
    F.mse_loss(info_t['state_pred']['workspace_rev'], info_t1['workspace_rev']) +
    F.mse_loss(info_t['state_pred']['qi'], info_t1['qi_fluid']) +
    F.mse_loss(info_t['state_pred']['conscious'], info_t1['conscious']) +
    F.mse_loss(info_t['state_pred']['harmony'], info_t1['harmony_state'])
)

loss = loss_external + 0.1 * loss_internal
```

**Why this matters:** When the model can predict its own next state, it becomes a **genuine dynamical system**. You can give it one frame, let it predict its own next state, and it autonomously generates trajectories without teacher forcing. The current model is a frame interpolator; this makes it a simulator.

---

### P1.2 Multi-Step Process Prediction

**Current:** Single-step. Given frames `[t-3, t-2, t-1, t]`, predict `t+1`.

**Target:** Given frames `[t-3, t-2, t-1, t]`, predict the full trajectory `[t+1, t+2, ..., t+H]` AND the full internal process trajectory.

```python
class ProcessPredictor(nn.Module):
    """Outputs the full prediction process, not just the final answer."""

    def __init__(self, brain: SelfPredictiveBrain, horizon: int = 8):
        super().__init__()
        self.brain = brain
        self.horizon = horizon

    def forward(self, x, return_process=True):
        """x: [B, 4, D] initial state
        Returns:
          preds: [B, H, D] predictions for t+1...t+H
          process: dict with full internal trajectories
        """
        B = x.shape[0]
        history = x.clone()

        preds = []
        process = {
            'workspace_fwd': [],
            'workspace_rev': [],
            'conscious': [],
            'qi': [],
            'harmony': [],
            'specialist_weights': [],
        }

        for h in range(self.horizon):
            pred, info = self.brain(history)
            preds.append(pred)

            if return_process:
                process['workspace_fwd'].append(info['workspace_fwd'].detach())
                process['workspace_rev'].append(info['workspace_rev'].detach())
                process['conscious'].append(info['conscious'].detach())
                process['qi'].append(info.get('qi_fluid', torch.zeros_like(info['conscious'])).detach())
                process['harmony'].append(info.get('harmony_state', torch.zeros(self.brain.N)).detach())
                process['specialist_weights'].append(info.get('weights', torch.zeros(self.brain.N, B)).detach())

            # Roll history forward
            history = torch.cat([history[:, 1:, :], pred.unsqueeze(1)], dim=1)

        preds = torch.stack(preds, dim=1)  # [B, H, D]
        return preds, process
```

**Training with multi-step loss:**
```python
# Teacher-forced multi-step
preds, process = process_predictor(x)  # [B, H, D]
loss = 0
for h in range(H):
    loss += F.mse_loss(preds[:, h, :], y_true[:, h, :])
loss = loss / H

# Process consistency loss: predicted internal states should be smooth
for key in ['workspace_fwd', 'conscious']:
    traj = torch.stack(process[key], dim=1)  # [B, H, D]
    # Penalize high-frequency oscillation (encourage coherent trajectories)
    diff = traj[:, 1:, :] - traj[:, :-1, :]
    loss += 0.01 * diff.pow(2).mean()
```

**The full process output:**
```python
# At inference time, the model returns EVERYTHING
preds, process = model.process_predict(x, horizon=64)

# process contains:
# - workspace_fwd trajectory: how prospective memory evolved
# - workspace_rev trajectory: how retrospective memory accumulated
# - conscious trajectory: how awareness shifted
# - qi trajectory: how the resonant field pulsed
# - specialist weights: which chakras were active at each step
# - harmony state: how specialist cooperation evolved
```

This is the "full process" the user asked about. The model doesn't just say "the answer is 42" — it shows its work: the entire dynamical trajectory from input to output.

---

### P1.3 State Persistence for Sequential Data

**Problem:** `reset_workspace()` zeros all state every batch. This is correct for independent physics windows but destroys sequential coherence for text/audio.

**Fix:** State persistence for sequential episodes.

```python
class EpisodeBuffer:
    """Maintains state across sequential timesteps within an episode."""

    def __init__(self, brain):
        self.brain = brain
        self.episode_state = None
        self.episode_id = None

    def begin_episode(self, episode_id):
        """Start a new episode. State is reset."""
        self.episode_id = episode_id
        self.brain.reset_workspace(batch_size=1)
        self.episode_state = {
            'workspace_fwd': self.brain.workspace_fwd.clone(),
            'workspace_rev': self.brain.workspace_rev.clone(),
            'qi_fluid': self.brain.qi_fluid.clone() if hasattr(self.brain, 'qi_fluid') else None,
            'harmony_state': self.brain.harmony_state.clone(),
            'specialist_energy': self.brain.specialist_energy.clone(),
        }

    def step(self, x):
        """Process one timestep within the episode. State persists."""
        pred, info = self.brain(x, use_memory=True, return_workspace=True)
        # State is NOT reset — it accumulates across the episode
        return pred, info

    def end_episode(self):
        """Episode ends. Write episode summary to berry memory."""
        # The final conscious state is the episode's "soul"
        # Write it to long-term memory with the episode ID
        pass
```

**Why this matters:** Text and audio are sequential. The meaning of word 100 depends on words 1–99. With state persistence, `workspace_rev` accumulates context across the sequence. The model becomes a true recurrent processor, not a window-based interpolator.

---

## Phase 2 — Full Process Output

### P2.1 Process Serialization

**Target:** The model outputs its full process in a human/ machine-readable format.

```python
class ProcessSerializer:
    """Serialize the model's internal process to JSON/dict."""

    @staticmethod
    def serialize(process: dict, metadata: dict) -> dict:
        """Convert process tensors to structured dict."""
        return {
            'metadata': metadata,
            'trajectory': {
                'workspace_fwd': ProcessSerializer._tensor_to_stats(process['workspace_fwd']),
                'workspace_rev': ProcessSerializer._tensor_to_stats(process['workspace_rev']),
                'conscious': ProcessSerializer._tensor_to_stats(process['conscious']),
                'qi': ProcessSerializer._tensor_to_stats(process['qi']),
                'harmony': ProcessSerializer._tensor_to_stats(process['harmony']),
                'specialist_weights': ProcessSerializer._tensor_to_list(process['specialist_weights']),
            },
            'summary': {
                'yang_yin_ratio': process['workspace_fwd'][-1].norm() / (process['workspace_rev'][-1].norm() + 1e-8),
                'conscious_sparsity': (process['conscious'][-1].abs() < 0.01).float().mean(),
                'dominant_specialist': process['specialist_weights'][-1].argmax(dim=0).mode().item(),
                'spectral_slope': compute_spectral_slope(process['conscious'][-1]),
            }
        }

    @staticmethod
    def _tensor_to_stats(tensors):
        """Compute mean/std/norm statistics for a list of tensors."""
        stacked = torch.stack(tensors, dim=0)
        return {
            'mean': stacked.mean(dim=-1).tolist(),
            'std': stacked.std(dim=-1).tolist(),
            'norm': stacked.norm(dim=-1).tolist(),
        }
```

**Example output:**
```json
{
  "metadata": {
    "input_modality": "physics",
    "input_description": "turbulent vortex",
    "horizon": 64,
    "task": "process_prediction"
  },
  "summary": {
    "yang_yin_ratio": 1.62,
    "conscious_sparsity": 0.15,
    "dominant_specialist": 7,
    "spectral_slope": -1.67
  },
  "trajectory": {
    "conscious": {
      "mean": [0.12, 0.13, 0.15, ...],
      "std": [0.04, 0.05, 0.06, ...],
      "norm": [7.2, 7.5, 8.1, ...]
    },
    "specialist_weights": [
      [0.02, 0.01, 0.15, 0.60, ...],
      [0.03, 0.02, 0.14, 0.58, ...],
      ...
    ]
  }
}
```

---

### P2.2 Process Visualization

**Target:** Visualize the model's internal process as it runs.

```python
class ProcessVisualizer:
    """Generate visualizations of the model's internal process."""

    def visualize_trajectory(self, process: dict, save_path: str):
        """Create a multi-panel figure showing the process."""
        fig, axes = plt.subplots(3, 2, figsize=(14, 18))

        # Panel 1: Workspace evolution (fwd vs rev)
        ax = axes[0, 0]
        fwd_norms = [w.norm().item() for w in process['workspace_fwd']]
        rev_norms = [w.norm().item() for w in process['workspace_rev']]
        ax.plot(fwd_norms, label='Yang (fwd)', color='red')
        ax.plot(rev_norms, label='Yin (rev)', color='blue')
        ax.set_ylabel('Norm')
        ax.set_title('Workspace Evolution')
        ax.legend()

        # Panel 2: Yang/Yin ratio
        ax = axes[0, 1]
        ratios = [f / (r + 1e-8) for f, r in zip(fwd_norms, rev_norms)]
        ax.plot(ratios, color='purple')
        ax.axhline(y=PHI, color='green', linestyle='--', label='φ')
        ax.set_ylabel('Yang/Yin Ratio')
        ax.set_title('Yin-Yang Balance')
        ax.legend()

        # Panel 3: Conscious state heatmap
        ax = axes[1, 0]
        conscious_stack = torch.stack(process['conscious'], dim=0).cpu().numpy()
        ax.imshow(conscious_stack.T, aspect='auto', cmap='RdBu_r')
        ax.set_ylabel('Dimension')
        ax.set_xlabel('Timestep')
        ax.set_title('Conscious State Trajectory')

        # Panel 4: Specialist activation
        ax = axes[1, 1]
        weights = torch.stack(process['specialist_weights'], dim=0).cpu().numpy()
        ax.imshow(weights.T, aspect='auto', cmap='viridis')
        ax.set_ylabel('Specialist')
        ax.set_xlabel('Timestep')
        ax.set_title('Specialist Activation')

        # Panel 5: Qi energy
        ax = axes[2, 0]
        qi_norms = [q.norm().item() for q in process['qi']]
        ax.plot(qi_norms, color='orange')
        ax.set_ylabel('Qi Energy')
        ax.set_xlabel('Timestep')
        ax.set_title('Qi Fluid Evolution')

        # Panel 6: Harmony effective rank
        ax = axes[2, 1]
        # Compute effective rank of harmony matrix over time
        ax.set_title('Harmony Structure')

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close()
```

---

## Phase 3 — Associative Curriculum

### P3.1 Byte-First Pretraining

**Week 1–2:** Train on raw bytes from ALL sources mixed together. No metadata. Task: predict next bytes.

- Physics bytes + text bytes + audio bytes all in one bucket
- The model learns universal byte-level patterns
- Specialist chakras self-organize: some resonate with spatial correlations (physics), some with grammatical structure (text), some with periodic patterns (audio)
- Curriculum: start with short sequences (256 bytes), gradually increase to 4096 bytes

### P3.2 Modality Signature Learning

**Week 3–4:** Add modality headers. Task: predict next bytes AND identify modality.

- Each sequence prefixed with `[type][modality]`
- Auxiliary classification head predicts modality from conscious state
- Loss: `MSE(pred, target) + 0.1 * CrossEntropy(modality_pred, modality_label)`
- The model learns that "physics bytes feel different from text bytes"

### P3.3 Association Learning

**Week 5–6:** Pair observations with descriptions. Task: match conscious states.

- Input: `[physics_bytes][text_description]`
- The model processes both through the same encoder
- Association loss: `1.0 - cosine_similarity(physics_conscious, text_conscious)`
- The model learns that "turbulent vortex" and the actual vortex field produce similar internal representations
- Berry memory stores these associations: key = physics bytes, value = text description

### P3.4 Conditional Generation

**Week 7–8:** Generate bytes from descriptions. Task: description → observation.

- Input: `[TYPE_QUESTION][MOD_TEXT][description]`
- Target: `[TYPE_ANSWER][MOD_PHYSICS][field_bytes]`
- The model learns to hallucinate plausible physics from text
- This is the inverse of association: instead of matching representations, the model generates the representation that would match

### P3.5 Autonomous Mixing

**Week 9+:** All tasks interleaved. The model detects task type from metadata and behaves accordingly.

- Neuroplasticizer pulses trigger exploration of underrepresented byte structures
- Berry memory queries guide curriculum: "I don't have enough audio examples — sample more audio"
- The model becomes self-directing in its learning

---

## Phase 4 — Architecture Changes Summary

### Files to Create

| File | Purpose |
|---|---|
| `cassi/byte_stream.py` | `ByteStreamEncoder` — universal byte→field encoder |
| `cassi/serializer.py` | `DataSerializer` — modality-specific byte formatters |
| `cassi/metadata.py` | `MetadataHeader` — byte prefix definitions |
| `cassi/byte_loader.py` | `ByteStreamLoader` — unified data loader |
| `cassi/self_predictive.py` | `SelfPredictiveBrain` — internal state prediction |
| `cassi/process_predictor.py` | `ProcessPredictor` — multi-step full process output |
| `cassi/episode_buffer.py` | `EpisodeBuffer` — state persistence for sequential data |
| `cassi/process_serializer.py` | `ProcessSerializer` — process→JSON/dict |
| `cassi/process_viz.py` | `ProcessVisualizer` — process visualization |

### Files to Modify

| File | Changes |
|---|---|
| `cassi/harmony_brain.py` | Add state predictors; expose state_pred in info dict |
| `cassi/multimodal_brain.py` | Add association loss; conditional generation mode |
| `cassi/berry_brain.py` | Store associations (observation + description pairs) |
| `train_multimodal.py` | Multi-step loss; process consistency loss; episode-aware training; byte-stream loader |
| `cassi/observability.py` | Add process trajectory metrics |

---

## Phase 5 — Execution Order

| Step | Task | Duration | Risk |
|---|---|---|---|
| 0 | Implement `ByteStreamEncoder` + `DataSerializer` | 1 day | Low — replaces existing encoders |
| 1 | Implement `MetadataHeader` + `ByteStreamLoader` Phase 0 | 1 day | Low — data pipeline only |
| 2 | Train baseline: bytes-only, single-step | 3 days | Low — validate encoder works |
| 3 | Implement `SelfPredictiveBrain` + internal state loss | 2 days | Medium — new loss terms |
| 4 | Implement `ProcessPredictor` + multi-step loss | 2 days | Medium — unrolling changes dynamics |
| 5 | Implement `EpisodeBuffer` for sequential data | 1 day | Low — state management |
| 6 | Add `ByteStreamLoader` Phase 1–2 (modality labels + associations) | 2 days | Low — curriculum changes |
| 7 | Train full curriculum (Phase 0–3) | 2 weeks | Medium — convergence uncertain |
| 8 | Implement `ProcessSerializer` + `ProcessVisualizer` | 1 day | None — inference only |
| 9 | Add autonomous mixing (Phase 5) | 3 days | High — self-directed learning untested |

**Total: ~4 weeks to full autonomous system.**

---

## The One-Line Summary

> Everything is bytes. The model learns byte patterns first, then learns what they mean through metadata-conditioned associations, then learns to predict its own next state, then outputs its full process. The result is a dynamical system that understands any data type because it understands bytes.
