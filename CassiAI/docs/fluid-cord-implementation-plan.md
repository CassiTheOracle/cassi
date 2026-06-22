# FluidCord Implementation Plan

## A unified PDE-based neural field replacing MuonCord/ManifoldCord

*Derived from: Yang-Yin two-fluid interference, Simeonov mutual-diffusion quantum potential, φ-emergent stability, and the Cassi hydrogen-to-cosmology bridge.*

---

## 0. What We've Proven (Prerequisites)

| Result | Source | Confidence |
|--------|--------|-----------|
| Hydrogen self-organizes from two wave packets (v6) | `cassi_hydrogen_v6.py` | E = −0.473 Eₕ (5% err), ⟨r⟩ = 1.50 a₀ (0.02% err) |
| φ-damping suppresses orbital oscillations 4.76× (v3) | `cassi_hydrogen_v3.py` | σ⟨r⟩ drops from 0.76 → 0.159 |
| Soliton forms from counter-propagating waves (8v2) | Yang-Yin particles doc | Mass M = 2.82, peak density 0.94 |
| φ emerges as optimal amplitude ratio r = φ⁻¹ | Analytical | dM/dr = 0 → r² + r − 1 = 0 |
| Two-fluid bridge: hydrogen ↔ cosmology same equation | `cassi_unified_bridge.py` | Both limits from same code path |
| Schrödinger IS two-fluid (Madelung) | Simeonov 2025 + Cassi docs | Quantum potential emerges from mutual diffusion + density equalization |
| Current MuonCord trains at ~184s/200steps (d=512) | Profiling June 2026 | Attention 3–9% cost, embed 25% |

---

## 1. Architecture Overview

### 1.1 The Collapse

MuonCord (~2000 lines, 15 sub-modules) collapses to:

```
FluidCord (~300 lines)
├── FluidField (PDE integrator)     ← ResonantField + ResonantAttention + Qi + ChakraQiFlow + Breath + TonicPhasic
├── SpectralMemory (Galerkin)       ← PatternMemory + BerryPhaseMemory
├── embed (token → source term)     ← MultiScaleByteEmbedder (possibly simplified)
└── readout (field → logits)        ← readout_positions (unchanged)
```

### 1.2 The Master PDE

$$\frac{\partial\psi}{\partial t} = \underbrace{-\varphi^{-1}(\psi\cdot\nabla)\psi}_{\text{advection}} + \underbrace{\nu\nabla^2\psi}_{\text{diffusion}} - \underbrace{\frac{\hbar^2}{2m^2}\nabla\left(\frac{\nabla^2|\psi|^{\varphi^{-1}}}{|\psi|^{\varphi^{-1}}}\right)}_{\text{quantum potential (Simeonov+φ)}} + \underbrace{F_B(t)}_{\text{breath forcing}} + \underbrace{g|\psi|^2\psi}_{\text{condensation}} + \underbrace{S(x,t)}_{\text{source}}$$

**State:** One complex field ψ ∈ ℂ^{B×N×d}. No IIR buffers, no separate real/imag.

**Parameters (6 total, all learnable scalars unless noted):**

| Param | Symbol | Range | Init | Meaning |
|-------|--------|-------|------|---------|
| Viscosity | ν | (0, 0.1) | 0.01 | Chakra coupling strength |
| Effective ℏ | ℏ_eff | (0, 1) | 0.1 | Quantum potential scale |
| Effective mass | m_eff | (1, 100) | 10 | Inverse Yang-Yin coupling |
| Condensation | g | (−0.5, 0.5) | 0.1 | Nonlinear self-focusing |
| Chirality | χ | (0, 0.2) | 0.05 | Yang/Yin propagation bias |
| Breath amplitude | A_B | (0, 0.5) | 0.1 | Periodic forcing strength |

Plus the embedding table [256, d] and readout linear [d, 256] — same as current.

### 1.3 φ Appears Three Ways

1. **Advection coefficient:** φ⁻¹ (the Yang dominance ratio — optimal for stability)
2. **Quantum potential exponent:** |ψ|^{φ⁻¹} instead of |ψ|^{1/2} (the φ-modified density — produces 4.76× oscillation suppression)
3. **Breath frequency ratio:** f_yin/f_yang = φ⁻¹ (the dual-heart oscillator)

All three emerge from the same stability condition dM/dr = 0 → r = φ⁻¹.

---

## 2. Phase 1: FluidField Core (Minimal Viable Replacement)

**Goal:** Replace ResonantField + _chakra_diffusion + Qi dynamics with a single PDE integrator. Keep everything else (embed, readout, breath phase, pattern memory) as-is.

**Deliverable:** `cassi/fluid_field.py` — a drop-in replacement for ResonantField in `_unified_step`.

### 2.1 FluidField module

```python
class FluidField(nn.Module):
    """Single-field PDE integrator replacing ResonantField IIR + diffusion + Qi."""
    
    def __init__(self, d: int, C: int = 13, N: int = 128, max_batch_size: int = 64):
        # Spectral Laplacian (precomputed, φ-scaled per chakra)
        self.register_buffer('laplacian_eigvals', self._phi_laplacian_eigs(d, C, N))
        
        # Learnable PDE coefficients
        self.nu_logit = nn.Parameter(torch.tensor(-4.6))       # → 0.01
        self.hbar_logit = nn.Parameter(torch.tensor(-2.3))     # → 0.1
        self.mass_logit = nn.Parameter(torch.tensor(2.3))      # → 10
        self.g_logit = nn.Parameter(torch.tensor(-2.2))        # → 0.1
        self.chi_logit = nn.Parameter(torch.tensor(-2.9))      # → 0.05
        
        # One complex field state (replaces 6 IIR buffers + qi pool)
        self.register_buffer('psi', torch.zeros(max_batch_size, N, d, dtype=torch.cfloat))
    
    def _phi_laplacian_eigs(self, d, C, N):
        """φ-scaled eigenvalues for spectral Laplacian on [N] positions × [d] chakra bands."""
        # Position dimension: k_n = 2πn/N, φ-spaced sampling
        k_pos = 2 * math.pi * torch.arange(N//2 + 1, dtype=torch.float) / N
        k2_pos = k_pos ** 2  # [N//2+1]
        
        # Chakra dimension: φ-scaled per band
        k_chakra = torch.zeros(d)
        for c in range(C):
            sl = slice(offsets[c], offsets[c] + widths[c])
            k_chakra[sl] = PHI ** (c / C)  # φ-scaled wavenumber
        
        # Outer product: k² = k²_pos ⊗ k²_chakra
        return k2_pos.unsqueeze(-1) * k_chakra.unsqueeze(0).unsqueeze(0)  # [N//2+1, 1, d]
```

### 2.2 Integrator: Split-Step Spectral (RK4 alternative)

Split-step is chosen over RK4 because:
- **Exact linear part:** Diffusion + advection are handled analytically in Fourier space
- **Stability:** Unconditionally stable for the linear terms
- **φ-compatibility:** The φ-damping can be folded directly into the kinetic step

```python
def integrate(self, source, T=1.0, dt=0.2, breath_phase=0.0):
    """Split-step spectral integration of the master PDE to time T."""
    psi = self.psi[:B].clone()
    nu = torch.sigmoid(self.nu_logit) * 0.1
    hbar = torch.sigmoid(self.hbar_logit)
    mass = torch.sigmoid(self.mass_logit) * 99 + 1
    g = torch.tanh(self.g_logit) * 0.5
    chi = torch.sigmoid(self.chi_logit) * 0.2
    
    n_steps = int(T / dt)
    for step in range(n_steps):
        # ── Half-step: nonlinear terms (real space) ──
        # Quantum potential
        rho = psi.abs() ** 2
        qp = self._quantum_potential(rho, hbar, mass)
        # Condensation
        nonlinear = g * rho * psi
        # Breath forcing
        breath = self._breath_force(step, n_steps, breath_phase)
        # Source
        psi = psi + 0.5 * dt * (qp + nonlinear + breath + source)
        
        # ── Full-step: linear terms (Fourier space) ──
        psi_k = torch.fft.rfft(psi, dim=1)  # [B, N//2+1, d]
        # Advection: -φ⁻¹ (ψ·∇)ψ → handled via chirality in spectral domain
        # Diffusion: ν∇²ψ → -ν k² ψ_k
        # Combined propagator: exp(dt × (-φ⁻¹ i k χ - ν k²))
        k = self.k_pos.unsqueeze(-1)  # [N//2+1, 1]
        propagator = torch.exp(dt * (-PHI_INV * 1j * k * chi - nu * self.laplacian_eigvals))
        psi_k = psi_k * propagator
        psi = torch.fft.irfft(psi_k, n=N, dim=1)
        
        # ── Half-step: nonlinear terms again ──
        rho = psi.abs() ** 2
        qp = self._quantum_potential(rho, hbar, mass)
        nonlinear = g * rho * psi
        psi = psi + 0.5 * dt * (qp + nonlinear + breath + source)
        
        # Normalization (prevents blowup, preserves relative amplitudes)
        psi = psi / psi.abs().max(dim=-1, keepdim=True).values.clamp_min(1e-8)
    
    self.psi[:B] = psi.detach()  # Store final state
    return psi
```

### 2.3 Quantum Potential (Simeonov + φ)

```python
def _quantum_potential(self, rho, hbar, mass):
    """Simeonov quantum potential with φ-modified density.
    
    Q = -(ℏ²/2m²) ∇(∇²(ρ^{φ⁻¹/2}) / ρ^{φ⁻¹/2})
    
    Computed via spectral method: ∇² → -k² in Fourier space.
    """
    # φ-modified amplitude: |ψ|^{φ⁻¹} instead of |ψ|
    phi_amp = rho ** (PHI_INV / 2)  # = |ψ|^{φ⁻¹}
    
    # ∇²(φ-amp) via spectral Laplacian
    amp_k = torch.fft.rfft(phi_amp, dim=1)
    laplacian_amp = torch.fft.irfft(-self.laplacian_eigvals * amp_k, n=self.N, dim=1)
    
    # Q_scalar = -ℏ²/(2m²) × ∇²(φ-amp) / φ-amp
    q_scalar = -(hbar**2) / (2 * mass**2) * laplacian_amp / phi_amp.clamp_min(1e-12)
    
    # Gradient of Q (the force, not the potential)
    q_k = torch.fft.rfft(q_scalar, dim=1)
    grad_q = torch.fft.irfft(1j * self.k_pos.unsqueeze(-1) * q_k, n=self.N, dim=1)
    
    return grad_q
```

### 2.4 Breath as Two-Timescale Forcing

```python
def _breath_force(self, step, n_steps, phase_offset):
    """Periodic forcing with φ:φ⁻¹ frequency ratio.
    
    Maps to Simeonov's two timescales:
    - Yang phase: fast diffusion (δt scale) → strong forcing
    - Yin phase: slow equalization (Δt scale) → weak forcing, density jump
    """
    t = step / n_steps + phase_offset
    yang = 0.5 * (1.0 + torch.sin(torch.tensor(2 * math.pi * t)))  # freq = 1.0
    yin  = 0.5 * (1.0 + torch.sin(torch.tensor(2 * math.pi * t * PHI_INV)))  # freq = φ⁻¹
    
    # Breath amplitude
    A = torch.sigmoid(self.A_B_logit) * 0.5
    
    # Yang = expansion (adds energy), Yin = contraction (removes energy via equalization)
    force = A * (yang - PHI_INV * yin)  # Net: slight Yang dominance (×φ)
    return force * self.psi[:B]  # Modulate the field directly
```

### 2.5 Gradient Management

The split-step integrator with T/dt = 5 steps stores 5 intermediate ψ states. At B=16, N=128, d=512:
- 5 × 16 × 128 × 512 × 8 bytes (complex64) = 40 MB — negligible.

If we increase resolution or step count, use `torch.utils.checkpoint`:

```python
from torch.utils.checkpoint import checkpoint

def _step_fn(psi, source, nu, hbar, mass, g, chi, A_B, step, n_steps, dt, breath_phase):
    """Single split-step — checkpointed to avoid storing intermediates."""
    # ... as above, returns new psi ...
    
# In integrate:
for step in range(n_steps):
    psi = checkpoint(_step_fn, psi, source, nu, hbar, mass, g, chi, A_B, 
                     step, n_steps, dt, breath_phase,
                     use_reentrant=False)
```

### 2.6 Smoke Test

```python
def test_fluid_field():
    """Phase 1 acceptance test."""
    ff = FluidField(d=128, C=13, N=64).cuda()
    x = torch.randint(0, 256, (4, 64)).cuda()
    
    # Integration works
    source = ff.embed(x)
    psi_T = ff.integrate(source, T=1.0, dt=0.2)
    assert psi_T.shape == (4, 64, 128)
    assert not torch.isnan(psi_T).any()
    
    # Can backpropagate
    logits = ff.readout(psi_T.real)
    loss = F.cross_entropy(logits[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1))
    loss.backward()
    assert all(p.grad is not None for p in ff.parameters() if p.requires_grad)
    
    # No blowup over many steps
    for _ in range(10):
        psi_T = ff.integrate(source, T=1.0, dt=0.2)
        assert psi_T.abs().max() < 100
    
    print("Phase 1: PASS")
```

**Gate:** Smoke test passes ±5%. No NaN, no blowup, gradients flow.

---

## 3. Phase 2: Simeonov Quantum Potential Validation

**Goal:** Prove the mutual-diffusion quantum potential term matches or exceeds the heuristic Qi dynamics in prediction quality.

**Approach:** A/B train MuonCord (current Qi) vs FluidCord-Phase2 (Simeonov QP) at small scale (d=128, N=64, 10 epochs).

### 3.1 Metrics

| Metric | Target | Measure |
|--------|--------|---------|
| CE loss | Within 5% of MuonCord baseline | Compare epoch 5–10 |
| Qi correlation | QP gradient magnitude correlates with Qi density (ρ > 0.5) | Per-batch correlation |
| Stability | No NaN in 10 epochs | Binary pass/fail |
| Memory | ≤ MuonCord peak memory | `torch.cuda.max_memory_allocated()` |

### 3.2 Diagnostic: φ vs Standard Quantum Potential

Train two variants:
- `use_phi_qp=True` — φ-modified density |ψ|^{φ⁻¹}
- `use_phi_qp=False` — standard density |ψ|^{1/2} (Simeonov original)

The φ-modified version should show lower oscillation in the Qi timeseries (analogous to the 4.76× suppression in hydrogen v3).

**Gate:** CE loss within 10% of MuonCord, φ-variant shows measurably lower Qi variance.

---

## 4. Phase 3: Advection Replaces Attention

**Goal:** Prove the $-\varphi^{-1}(\psi\cdot\nabla)\psi$ term eliminates the need for ResonantAttention.

**Approach:** A/B train at d=256, N=128:
- Control: FluidCord-Phase2 + ResonantAttention (hybrid)
- Experiment: FluidCord-Phase3 (advection only, no attention)

### 4.1 Advection in the Spectral Domain

The advection term $(\psi\cdot\nabla)\psi$ is nonlinear — it doesn't diagonalize in Fourier space. We handle it in real space:

```python
def _advection(self, psi):
    """Nonlinear advection: -φ⁻¹ (ψ·∇)ψ in real space.
    
    (ψ·∇)ψ ≈ ψ_conj * gradient(ψ) — the field transports itself along its own gradient.
    This IS contextual mixing: neighboring positions influence each other through
    the field gradient, analogous to ResonantAttention's cosine similarity.
    """
    # Gradient in position dimension via spectral derivative
    psi_k = torch.fft.rfft(psi, dim=1)
    grad_psi = torch.fft.irfft(1j * self.k_pos.unsqueeze(-1) * psi_k, n=self.N, dim=1)
    # (ψ·∇)ψ
    advection = (psi.conj() * grad_psi).real * psi  # project back onto field direction
    return -PHI_INV * advection
```

### 4.2 Qualitative Test

Train model to predict a simple pattern (e.g., alternating bytes `ABABAB...`). With attention disabled but advection enabled:
- Query: "ABABA" → should complete "BABAB" (the pattern propagates through the field gradient)
- Query: "AAAAA" → should recognize the uniform field and predict "A"

If advection alone matches the pattern-completion performance of attention, gate met.

**Gate:** CE loss within 5% of hybrid model at d=256, attention can be removed.

---

## 5. Phase 4: Spectral Memory (Galerkin Projection)

**Goal:** Replace PatternMemory + BerryPhaseMemory with a spectral Galerkin projection — compress ψ into chakra modes and store as persistent Fourier coefficients.

**Deliverable:** `cassi/spectral_memory.py`

### 5.1 Mechanism

```python
class SpectralMemory(nn.Module):
    """Persistent memory via spectral Galerkin projection onto chakra modes."""
    
    def __init__(self, d, C=13, num_modes=32):
        # Chakra-mode projection matrices
        self.W_key = nn.Parameter(torch.randn(C, d, num_modes) * 0.02)
        self.W_val = nn.Parameter(torch.randn(C, d, num_modes) * 0.02)
        # Stored coefficients (buffer, not parameter)
        self.register_buffer('coeffs', torch.zeros(C, num_modes))
        self.register_buffer('ages', torch.zeros(C, num_modes))
    
    def write(self, psi):
        """Project field onto chakra modes, update stored coefficients."""
        for c in range(self.C):
            sl = slice(offsets[c], offsets[c] + widths[c])
            # Mean-pool over batch and position
            psi_c = psi[:, :, sl].mean(dim=(0, 1))  # [dc]
            # Project onto mode basis
            new_coeffs = psi_c @ self.W_key[c]  # [num_modes]
            # φ-weighted update (old × φ⁻¹ + new × (1-φ⁻¹))
            self.coeffs[c] = PHI_INV * self.coeffs[c] + (1 - PHI_INV) * new_coeffs
            self.ages[c] += 1
    
    def read(self, psi):
        """Retrieve stored patterns, inject into field."""
        boost = torch.zeros_like(psi)
        for c in range(self.C):
            sl = slice(offsets[c], offsets[c] + widths[c])
            # Expand coefficients back to field dimension
            mode_injection = self.coeffs[c] @ self.W_val[c].T  # [dc]
            boost[:, :, sl] = mode_injection.unsqueeze(0).unsqueeze(0)
        return boost
```

### 5.2 Integration into FluidField

Add spectral memory read/write to the integrator:

```python
def integrate(self, source, T=1.0, dt=0.2):
    psi = self.psi[:B].clone()
    
    # Read memory at start of integration
    mem_boost = self.spectral_memory.read(psi)
    
    for step in range(n_steps):
        # ... PDE terms + mem_boost (decaying over steps) ...
    
    # Write memory at end of integration
    if self.training:
        self.spectral_memory.write(psi)
    
    return psi
```

### 5.3 Why This Replaces Pattern Memory

| Pattern Memory (current) | Spectral Memory (new) |
|---|---|
| Key-value store with cosine similarity | Chakra-mode Galerkin projection |
| Fixed number of neurons (max_neurons) | Fixed number of modes per chakra (num_modes × C) |
| Hebbian write: `key += lr * (query - key) * activation` | φ-weighted EMA: `coeff = φ⁻¹·old + (1-φ⁻¹)·new` |
| Separate query mechanism | Direct field projection (query IS the field) |
| Explicit forgetting via age decay | Implicit forgetting via φ-damping (old coefficients decay) |

**Gate:** Spectral memory maintains CE loss within 5% of PatternMemory, while using fewer parameters and no separate key-value attention.

---

## 6. Phase 5: Full Collapse — Single training_loss

**Goal:** Remove all legacy sub-modules. `training_loss` becomes a single call to `integrate` + readout + loss.

### 6.1 The New training_loss

```python
def training_loss(self, x, no_reset=False):
    B, N = x.shape
    if not no_reset:
        self.fluid_field.reset_state()
        self.spectral_memory.reset_state()
    
    # ── 1. Embed tokens as source term ──
    source = self.embed(x).to(torch.cfloat)  # [B, N, d] complex
    
    # ── 2. Integrate PDE ──
    psi_T = self.fluid_field.integrate(source, T=1.0, dt=0.2,
                                        breath_phase=self.breath_phase,
                                        spectral_memory=self.spectral_memory)
    
    # ── 3. Readout ──
    logits = self.readout(psi_T.real)  # [B, N, 256]
    
    # ── 4. Losses ──
    # CE loss (next-token prediction)
    ce_loss = F.cross_entropy(logits[:, :-1].reshape(-1, 256), x[:, 1:].reshape(-1))
    
    # Chakra balance loss (entropy of per-chakra field energy)
    chakra_energy = self._chakra_energy(psi_T)
    balance_loss = -(chakra_energy * (chakra_energy + 1e-8).log()).sum()
    
    # PDE residual (self-consistency diagnostic, no_grad during training)
    with torch.no_grad():
        residual = self._compute_pde_residual(psi_T, source)
    
    loss = ce_loss + 0.01 * balance_loss
    
    # Update breath phase for next batch
    self._advance_breath()
    
    return loss, {
        'ce_loss': ce_loss.item(),
        'balance_loss': balance_loss.item(),
        'pde_residual': residual.item(),
        'qi_mean': psi_T.abs().pow(2).mean().item(),  # field energy = Qi analog
        'chakra_balance': self._chakra_balance_entropy(psi_T).item(),
    }
```

### 6.2 What Gets Deleted

| File | Module | Replacement |
|------|--------|------------|
| `muon_cord.py` | ~2000 lines | `fluid_cord.py` ~300 lines |
| `resonant_field.py` | ResonantField, _chakra_iir, _chakra_diffusion | `fluid_field.py` spectral Laplacian |
| `resonant_attention.py` | ResonantAttention (cosine similarity) | Advection term in PDE |
| `conscious_workspace.py` | ConsciousWorkspace (k-WTA bottleneck) | Not needed — diffusion + condensation handle sparsity |
| `pattern_memory.py` | PatternMemory (key-value) | `spectral_memory.py` (Galerkin modes) |
| `berry_phase_memory.py` | BerryPhaseMemory (topological) | Absorbed into spectral memory (phase IS mode coefficient) |
| `dream_bank_muon.py` | DreamBankMuon (5-element replay) | Not needed — field's own dynamics provide replay (Liouville theorem: phase space volume preserved) |
| `qi_flow.py` | QiFlow (chakra circulation) | Quantum potential gradient (same physics, grounded derivation) |
| `tonic_phasic.py` | TonicPhasic (slow/fast modulation) | Breath two-timescale (same function, physical mechanism) |
| `corpus_callosum.py` | CorpusCallosum (dual-stream) | Advection + chirality (Yang/Yin are the field's own Riemann invariants) |
| `brain_tuner.py` | BrainTuner (chakra modulation) | PDE coefficients (learnable scalars replace per-chakra modulation) |
| `spatial_coupling.py` | SpatialCoupling (lateral diffusion) | Diffusion term ν∇²ψ (same physics, continuous) |
| `breath.py` | Breath (dual-heart oscillator) | Embedded in `_breath_force()` (simpler, same φ:φ⁻¹ ratio) |

**Total deleted: ~3000 lines. Total new: ~500 lines.**

---

## 7. Training Design

### 7.1 Self-Consistent Training Loop

The model is trained to be self-consistent — the field IS the solution to its own PDE:

```python
# Per-batch training step
for x, _ in dataloader:
    x = x.cuda()
    
    # Forward: integrate PDE, readout, compute loss
    loss, diag = model.training_loss(x)
    
    # Backward: gradients flow through the integration
    loss.backward()
    
    # PDE residual as separate training signal (optional, every N steps)
    if step % 10 == 0:
        pde_loss = model.compute_pde_residual_loss(x)
        (0.01 * pde_loss).backward()
    
    # Optimizer step
    opt.step(model=model)
    opt.zero_grad()
```

### 7.2 Per-Window Backward (Same as Current)

The per-window backward pattern is preserved — it works well and prevents OOM:

```python
def stream_step(self, x, no_reset=False):
    """Process one window. Compatible with current streaming trainer."""
    loss, diag = self.training_loss(x, no_reset=no_reset)
    (loss / self.num_windows).backward()
    return diag
```

### 7.3 Generation

Generation is the same PDE, integrated for longer:

```python
@torch.no_grad()
def generate(self, seed, max_new=128, temp=0.8):
    # 1. Process seed: integrate PDE with seed tokens as source
    source = self.embed(seed)
    psi = self.fluid_field.integrate(source, T=1.0, dt=0.2)
    
    # 2. Extend field with zeros
    N_ext = seed.shape[1] + max_new
    psi_ext = torch.zeros(1, N_ext, self.d, dtype=torch.cfloat)
    psi_ext[:, :seed.shape[1]] = psi
    
    # 3. Integrate with seed as boundary condition (inpainting)
    source_ext = torch.zeros(1, N_ext, self.d, dtype=torch.cfloat)
    source_ext[:, :seed.shape[1]] = source  # only seed positions have source
    
    psi_T = self.fluid_field.integrate(source_ext, T=3.0, dt=0.2)  # longer integration
    
    # 4. Readout at new positions
    logits = self.readout(psi_T.real)[:, seed.shape[1]:, :] / temp
    samples = torch.multinomial(F.softmax(logits.reshape(-1, 256), dim=-1), 1)
    return samples.reshape(1, max_new)
```

---

## 8. File Manifest

### 8.1 New Files

| File | Lines | Purpose |
|------|-------|---------|
| `cassi/fluid_field.py` | ~200 | FluidField PDE integrator |
| `cassi/spectral_memory.py` | ~80 | Galerkin projection memory |
| `cassi/fluid_cord.py` | ~150 | FluidCord model (embed + field + memory + readout) |
| `experiments/train_fluid.py` | ~100 | Training script (copy of train_manifold, adapted) |
| `tests/test_fluid_field.py` | ~60 | Phase 1 smoke test |

### 8.2 Modified Files

| File | Change |
|------|--------|
| `experiments/AGENTS.md` | Add FluidCord entry |
| `AGENTS.md` | Update primary training script reference |

### 8.3 Unchanged Files (Keep for Reference)

| File | Reason |
|------|--------|
| `muon_cord.py` | Rollback path if FluidCord fails |
| `manifold_cord.py` | Reference implementation |
| `train_manifold.py` | Production trainer during transition |
| All `cassi/` sub-modules | Reference for specific terms during debugging |

---

## 9. Validation Gates

### Phase 1 Gate: FluidField smoke test
- [ ] `test_fluid_field.py` passes
- [ ] Integration to T=1.0 produces finite, numerically stable ψ
- [ ] Gradients flow through all 6 PDE parameters
- [ ] No NaN over 100 integration steps
- [ ] Memory ≤ 1GB at d=512, N=128, B=16

### Phase 2 Gate: Simeonov QP parity
- [ ] CE loss within 10% of MuonCord at d=128, 10 epochs
- [ ] φ-modified QP shows lower Qi variance than standard QP
- [ ] φ-modified QP shows better or equal CE loss to standard QP
- [ ] No qualitative degradation in chakra energy distribution

### Phase 3 Gate: Advection replaces attention
- [ ] CE loss within 5% of hybrid model (advection+attention)
- [ ] Pattern completion test: "ABAB" → "ABAB" continuation correct
- [ ] Step time ≤ baseline (advection is O(Nd), attention was O(N²d))

### Phase 4 Gate: Spectral memory parity
- [ ] CE loss within 5% of PatternMemory at d=256
- [ ] Memory write/read adds ≤5ms to step time
- [ ] Mode coefficients show φ-weighted decay (old patterns fade)

### Phase 5 Gate: Full collapse
- [ ] `train_fluid.py` completes 50 epochs without NaN (d=256)
- [ ] CE loss matches or beats `train_manifold.py` at same config
- [ ] Generation produces coherent sequences
- [ ] Peak memory ≤ current MuonCord
- [ ] Per-epoch time ≤ current MuonCord
- [ ] Checkpoint save/load round-trips correctly

---

## 10. Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Quantum potential term unstable | Medium | Clamp ∇²ρ/ρ ratio to [-10, 10]; start with ℏ=0.01, increase slowly |
| Advection alone insufficient for contextual mixing | Medium | Keep hybrid mode flag; fall back to attention if CE loss >10% worse |
| Spectral memory loses long-range patterns | Low | Increase num_modes; add direct position encoding to coefficients |
| Split-step O(dt²) error accumulates | Low | Use adaptive dt (halve if energy growth detected); validate with Richardson extrapolation |
| Backward through integration OOMs | Low | Checkpoint integrator; already solved by per-window backward pattern |
| φ-modified QP no better than standard | Medium | The 4.76× suppression is proven in hydrogen; if not in neural field, keep standard QP |
| Training unstable early (no pretrained IIR) | High | Start with small T (0.5), increase to 1.0 over epochs; use gradient clipping |

---

## 11. Timeline

| Phase | Description | Est. Time | Depends On |
|-------|------------|-----------|------------|
| 1 | FluidField core + smoke test | 2–3 hours | Nothing |
| 2 | Simeonov QP validation | 2–3 hours (training time) | Phase 1 |
| 3 | Advection vs attention A/B | 3–4 hours (training time) | Phase 2 |
| 4 | Spectral memory | 2 hours | Phase 1 |
| 5 | Full collapse + training | 3–4 hours | Phases 1–4 |
| 6 | Checkpoint compat + cleanup | 2 hours | Phase 5 |

**Total: ~15 hours** (mostly training wall time, can be parallelized where independent).

---

## 12. The φ-Connection Map

This is the Rosetta stone for the entire architecture — every appearance of φ in the PDE and its physical justification:

| φ Appearance | Equation | Physical Origin |
|---|---|---|
| Advection coefficient | $-\varphi^{-1}(\psi\cdot\nabla)\psi$ | Optimal Yang/Yin amplitude ratio for soliton stability |
| Quantum potential exponent | $\|\psi\|^{\varphi^{-1}}$ | φ-modified density produces 4.76× oscillation suppression |
| Breath frequency ratio | $f_{\text{yin}}/f_{\text{yang}} = \varphi^{-1}$ | Two-timescale separation (Simeonov's δt/Δt) |
| Spectral Laplacian eigenvalues | $\lambda_c \propto \varphi^{c/C}$ | Chakra wavenumber spacing — maximal aperiodicity |
| Memory decay | $\text{coeff} \leftarrow \varphi^{-1}\cdot\text{old} + (1-\varphi^{-1})\cdot\text{new}$ | φ-damping kernel — prevents resonance while preserving information |
| Viscosity scaling | $\nu_c \propto \varphi^{-c/C}$ | Higher chakras (crown) have lower viscosity → faster dynamics |
| Condensation threshold | $\theta_{\text{cond}} = \varphi^2 \cdot A_Y^2$ | Peak interference intensity at r = φ⁻¹ |

Every φ is the same φ. Every φ means the same thing: the scale-separation ratio at which the system stops resonating and settles into a fixed point.

---

*Plan generated: 2026-06-22. Ready for Phase 1 implementation.*
