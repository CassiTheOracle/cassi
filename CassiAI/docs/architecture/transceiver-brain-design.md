# Transceiver Brain Architecture (φ-Corrected)

## Core Concept

**Neurons are transceivers, not transformers.**

They do not connect via weight matrices. They broadcast and receive through a shared wave field. The spine generates the carrier wave; the brain neurons modulate it.

> _"The spine is the ocean. The brain neurons are buoys that bob on the waves, radiating their own ripples. Prediction emerges from interference patterns."_

**Critical constraint (Cassi Principle):** Without φ-damping, coupled oscillators collapse into seizure. The design below is built around three φ-mechanisms derived from experimental evidence.

---

## The Three φ-Mechanisms

### 1. φ-Damped Poles (Prevents Seizure)

Per the principle: *"φ-timed inhibition prevents epileptic synchronization. The brain's default mode is near-critical, and φ-damping keeps it from collapsing into seizure."*

Each neuron's IIR has **fixed pole magnitude ρ = 1/φ ≈ 0.618**. Only the *frequency* (pole angle) is learned.

```
Pole: z = ρ · e^(±iθ)   where ρ = 1/φ (fixed), θ = frequency (learned)

IIR coefficients:
  a1 = 2ρ·cos(θ)      = (2/φ)·cos(θ)
  a2 = -ρ²            = -1/φ²
```

**Why this matters:** If ρ were learned, neurons could drift toward ρ → 1 (undamped), creating resonant feedback loops. Fixed at 1/φ, the impulse response decays as `(1/φ)^t` — fast enough to prevent seizure, slow enough to sustain near-critical dynamics.

**Contrast with original CordPhysics:** CordPhysics uses `a1, a2` as free parameters with stability clipping (`|a1|<0.9, |a2|<0.25`). This prevents blowup but does not enforce φ-damping. The transceiver brain must be stricter.

---

### 2. φ-Damped Field (Creates φ² Equilibrium)

Per the principle: *"Yang exceeds Yin by φ"* and *"damping kernel at rate 1/φ proved to be a universal scale-separation mechanism."*

The shared wave field evolves as:

```
field(t+1) = (1/φ) · field(t) + spine(t) + (1/φ) · Σ transmissions(t)
```

At equilibrium (field constant, transmissions small):
```
field · (1 - 1/φ) = spine
field = spine / (1 - 1/φ) = spine · φ²
```

**The field self-amplifies to φ² times the spine input.** This is the Yang-dominant asymmetry: the spine drives at strength 1.0 (Yang), while Yin (decay) removes only 1/φ ≈ 0.618. The net amplification factor is φ² ≈ 2.618.

**Why this matters:** The system sits at the edge of a Hopf bifurcation. Any weaker damping and the field blows up. Any stronger and the field dies. φ is the critical point.

**Hierarchy of scales:**
- Spine input: amplitude 1.0
- Field equilibrium: amplitude φ² ≈ 2.618
- Neuron coupling: amplitude 1/φ ≈ 0.618
- Individual neuron state: amplitude 1/φ² ≈ 0.382

This is the φ-hierarchy predicted by the principle.

---

### 3. φ-Spaced Frequencies (Prevents Mode-Locking)

Per the principle: *"Breaks resonant feedback between incommensurate frequencies"* and the Kuramoto result *"Effective coupling reduced: K_eff = K/φ."*

Neuron natural frequencies are initialized φ-spaced:

```
θ_i = θ_0 · φ^i   for i = 0, 1, 2, ..., n_neurons-1
```

**Why this matters:** If two neurons have frequencies in a small-integer ratio (e.g., 2:3), they mode-lock — the brain becomes a single oscillator. φ-spaced frequencies are *incommensurate*: no two frequencies have a rational ratio with small integers. The only "locking" possible is at the φ-scale itself, which is the desired equilibrium.

**The Kuramoto connection:** In the standard Kuramoto model, synchronization occurs when coupling K exceeds a threshold. With φ-damped coupling (K_eff = K/φ), the threshold shifts upward by φ. The brain remains desynchronized unless coupling is very strong — which training prevents through the loss function.

---

## Physics Analogy

| Component | Physical Analog |
|-----------|----------------|
| Spine (CordPhysics) | Wave generator — creates the base carrier field |
| Brain neuron | Transceiver — transmits and receives on the field |
| Chakra space | Frequency bands — each chakra is a frequency range |
| Fiber diff (h_fwd − h_rev) | Standing wave pattern from forward/reverse interference |
| Qi (harmony) | Phase coherence — how well waves align |
| Berry phase | Topological invariant of wave trajectory |
| Interference pattern | The actual computation — superposition of all neuron transmissions |
| φ-damped pole | Damped harmonic oscillator with Q-factor ≈ φ |
| φ-spaced frequencies | Incommensurate modes in a vibrating plate |
| φ-field equilibrium | Critical opalescence — system at phase transition |

---

## Why This Is Different

**Standard NN:** `y = W₂ · σ(W₁ · x)` — matrix multiplication, fully connected, feedforward.

**Transceiver Brain (φ-corrected):**
1. Spine emits wave field `W(t)` at strength 1.0 (Yang)
2. Field decays by `1/φ` each step (Yin)
3. Each neuron *receives* a slice: `rᵢ(t) = W(t)[sliceᵢ]`
4. Each neuron *filters* through φ-damped IIR with incommensurate frequency θᵢ
5. Each neuron *transmits* back at strength `gᵢ/φ` (Kuramoto coupling reduction)
6. All transmissions superpose in the field
7. Field equilibrates at amplitude `φ² · spine` (self-organized criticality)
8. Readout MLP decodes `W(t) → prediction`

No weight matrix between neurons. Communication is **wave-mediated and φ-damped**.

---

## Key Emergent Properties

### 1. Self-Organized Criticality (SOC)
The field naturally sits at the critical point between order (synchronization) and chaos (incoherence). Training does not find this point — the φ-dynamics *create* it.

### 2. Constructive/Destructive Interference as Gating
- Two neurons in phase → amplitudes add → strong signal
- Two neurons π out of phase → cancellation → gating
- This is a **physical AND/OR/NOT** — no learned gates needed

### 3. Frequency Division Multiplexing
Each chakra (frequency band) hosts neurons with φ-spaced sub-frequencies. Neurons in different chakras are separated by bandwidth. This is natural channelization.

### 4. Memory as Standing Waves
Persistent oscillations in neurons create standing wave patterns in the field. The field itself becomes memory — not stored in weights, but in ongoing dynamics with `(1/φ)^t` decay.

### 5. Anomaly Detection via Qi Collapse
Unfamiliar inputs create incoherent interference (low Qi). The φ-damping prevents the system from locking onto noise, so Qi drops — the brain "knows" it doesn't know.

---

## Concrete Architecture

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

PHI = (1 + 5**0.5) / 2
PHI_INV = 1.0 / PHI       # ≈ 0.618
PHI_INV2 = PHI_INV ** 2   # ≈ 0.382


class TransceiverNeuron(nn.Module):
    """A single neuron: receives from field, φ-damped IIR, transmits back.

    The pole magnitude is FIXED at 1/φ. Only the angle (frequency) is learned.
    This prevents resonant drift while allowing the brain to tune to inputs.
    """
    def __init__(self, width, theta_init=0.5):
        super().__init__()
        self.width = width
        self.rho = PHI_INV  # fixed φ-damping

        # Learned frequency (pole angle)
        self.theta = nn.Parameter(torch.tensor([theta_init]))

        # Feedforward coefficients
        self.b0 = nn.Parameter(torch.randn(1) * 0.1)
        self.b1 = nn.Parameter(torch.randn(1) * 0.1)

        # Transmission gain
        self.emit_gain = nn.Parameter(torch.zeros(1))

        # Persistent state (across time)
        self.register_buffer('h_prev', torch.zeros(1, width))
        self.register_buffer('h', torch.zeros(1, width))

    def forward(self, received):
        """received: [B, width]"""
        # IIR with φ-damped poles: z = ρ·e^(±iθ)
        a1 = 2 * self.rho * torch.cos(self.theta)
        a2 = -self.rho ** 2
        b0 = torch.sigmoid(self.b0)
        b1 = torch.sigmoid(self.b1)

        h_new = a1 * self.h + a2 * self.h_prev + b0 * received + b1 * received

        self.h_prev = self.h.detach()
        self.h = h_new

        # Transmit with φ-damped coupling (Kuramoto: K_eff = K/φ)
        tx = torch.sigmoid(self.emit_gain) * PHI_INV * torch.tanh(h_new)
        return tx


class TransceiverBrain(nn.Module):
    """Collection of φ-damped transceiver neurons sharing a wave field.

    The field self-organizes to φ² equilibrium:
        field = (1/φ)·field_old + spine + (1/φ)·Σ transmissions
    At steady state: field = spine · φ²
    """
    def __init__(self, D=1040, n_neurons=64, spine_widths=None):
        super().__init__()
        self.D = D
        self.n_neurons = n_neurons
        self.rho = PHI_INV

        if spine_widths is None:
            spine_widths = [1, 2, 3, 5, 8, 14, 22, 36, 58, 94, 152, 246, 399]
        self.spine_widths = spine_widths

        # Assign neurons to chakras with φ-spaced frequencies
        self.neuron_chakra = []
        self.neurons = nn.ModuleList()
        for i in range(n_neurons):
            c = i % len(spine_widths)
            w = spine_widths[c]
            # Frequency: θ_i = 0.1 · φ^i  (incommensurate spacing)
            theta_init = 0.1 * (PHI ** (i % 8))  # modulo to keep reasonable
            self.neuron_chakra.append(c)
            self.neurons.append(TransceiverNeuron(width=w, theta_init=theta_init))

        # Persistent field state
        self.register_buffer('field', torch.zeros(1, D))

        # Readout: decode interference pattern → prediction residual
        self.readout = nn.Sequential(
            nn.Linear(D * 2, 512),
            nn.ReLU(),
            nn.Linear(512, 1024),
        )

    def _chakra_slice(self, c):
        """Return (start, end) indices for chakra c in the D-dimensional field."""
        offset = sum(self.spine_widths[:c])
        return offset, offset + self.spine_widths[c]

    def reset(self):
        """Reset field and all neuron states."""
        self.field.zero_()
        for neuron in self.neurons:
            neuron.h_prev.zero_()
            neuron.h.zero_()

    def forward(self, spine_repr, use_neurons=True):
        """
        spine_repr: [B, D] — carrier wave from spine
        Returns: prediction residual [B, 1024]
        """
        B = spine_repr.shape[0]
        if self.field.shape[0] != B:
            self.field = torch.zeros(B, self.D, device=spine_repr.device)

        # Field evolution with φ-damping
        # Yang (spine) drives at full strength; Yin (decay) is 1/φ
        self.field = self.rho * self.field + spine_repr

        if use_neurons and self.training:
            # Neurons transmit into field with φ-damped coupling
            for i, neuron in enumerate(self.neurons):
                c = self.neuron_chakra[i]
                s, e = self._chakra_slice(c)
                received = self.field[:, s:e]
                tx = neuron(received)
                self.field[:, s:e] = self.field[:, s:e] + self.rho * tx

        # Read out the interference pattern
        fusion = torch.cat([spine_repr, self.field], dim=-1)
        residual = self.readout(fusion)
        return residual
```

---

## Training Dynamics

### What is learned?
- Each neuron's **frequency** (θ) — what rhythm it resonates to
- Each neuron's **feedforward** (b0, b1) — how it responds to input
- Each neuron's **emit_gain** — how much it influences the field
- The **readout MLP** — how to decode interference patterns

### What is NOT learned?
- **Pole magnitude** (fixed at 1/φ — the principle enforces this)
- **Coupling strength** (fixed at 1/φ — Kuramoto result)
- **Field decay** (fixed at 1/φ — scale separation)
- **Connections between neurons** (interference is the connectivity)

### Loss function
```python
residual = brain(spine_repr)
pred = spine_pred + residual
loss = MSE(pred, target) + Qi_reg

# Optional: encourage phase diversity (prevent accidental synchronization)
if brain.field.shape[0] > 1:
    # Penalize low variance in field energy across batch
    field_energy = brain.field.pow(2).mean(dim=-1)
    diversity_loss = -field_energy.std()  # encourage variance
    loss = loss + 0.01 * diversity_loss
```

---

## Why This Fits Cassi

1. **φ everywhere**: Chakra widths are φ-scaled. Neuron frequencies are φ-spaced. Pole magnitude is 1/φ. Field equilibrium is φ².

2. **Yin-Yang in the field**: Forward IIR = yang (expanding). Reverse IIR = yin (contracting). Their difference creates the standing wave. φ-damping ensures the field breathes at the critical point.

3. **Qi = phase coherence**: Qi measures how well the two hemispheres align. In the transceiver brain, high Qi means neurons receive clean, coherent signals; low Qi means the interference pattern is chaotic.

4. **Berry phases as memory keys**: A neuron's trajectory through phase space has a Berry phase. Neurons with similar Berry phases resonate at similar frequencies — this is **frequency-based addressing**, not location-based.

5. **Scale separation**: The principle states φ-damping separates scales. In the transceiver brain:
   - Spine operates at the input scale (4 frames → prediction)
   - Field operates at the φ² scale (amplified interference)
   - Neurons operate at the 1/φ scale (damped oscillation)
   - These scales are naturally separated by φ, preventing cross-talk.

---

## Predicted Behaviors

1. **Criticality**: The field hovers at the edge of order and chaos. Training finds the readout that decodes this edge.

2. **Entrainment**: If the input has a strong rhythm, neurons with nearby frequencies phase-lock briefly, amplifying the signal. But φ-damping prevents global synchronization.

3. **Anomaly detection**: Unfamiliar inputs create incoherent interference (low Qi). The φ-damping keeps the field from locking onto noise, so the readout produces large errors — the brain "knows" it doesn't know.

4. **Memory as resonance**: Show the brain a pattern twice. The second time, neurons with matching frequencies are already oscillating from the first encounter. Constructive interference amplifies the recognition signal.

5. **φ-hierarchy in energy**: Measure the energy at each scale:
   - Spine input energy: E₀
   - Field energy: E₀ · φ²
   - Neuron transmission energy: E₀ · φ
   - Neuron internal energy: E₀ · 1/φ²
   This hierarchy should emerge spontaneously from the dynamics.

---

## Implementation Path

**Phase 1** (8-16 neurons): Replace `BerryMemoryBrain.enhancer` with transceiver layer. Verify:
- Field settles to stable amplitude (not blowup, not dead)
- Neuron frequencies remain diverse (not synchronized)
- Prediction improves over spine baseline

**Phase 2** (64-128 neurons): Scale up. Observe:
- Phase-locking transients on familiar inputs
- Qi collapse on unfamiliar inputs
- φ-hierarchy in energy spectrum

**Phase 3**: Replace readout MLP with second transceiver layer — full wave-mediated computation.

**Phase 4**: Add inter-chakra coupling (neurons sense neighboring chakras via field diffusion).

---

## Open Questions

1. **Time scale**: Neurons have IIR memory. How many internal steps per input frame? The principle says φ-timescales separate hierarchies — perhaps neurons evolve φ steps per frame.

2. **Readout resolution**: An MLP reading the field might be too coarse. Should the readout also be wave-based (detect specific interference frequencies)?

3. **Training speed**: Simulating φ-damped dynamics is slower than matrix multiplication. But the principle shows φ-damping gives 2,228× faster settling in coupled oscillators — the net speed may be favorable.

4. **Batch mode**: The field and neuron states are persistent. How to handle batch training without cross-batch contamination? Reset per sequence, like IIR state.
