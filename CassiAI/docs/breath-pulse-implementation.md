# Breath, Pulse & Resonance — Implementation Plan

## Philosophy

Qi is not an accumulator. Qi is a **standing wave** — the interference pattern of two beating hearts.

Yang heart (fast, prospective) and Yin heart (slow, retrospective) breathe at different frequencies. Their beat creates the conscious rhythm. Gender is the phase relationship between them.

## Architecture

### 1. Dual-Heart Breath (`cassi/breath.py`)

Two coupled oscillators, one per workspace:

```
Yang heart:  breath_yang = sin(ω_yang * t + φ_yang)
Yin heart:   breath_yin  = sin(ω_yin  * t + φ_yin )
```

- `ω_yang`, `ω_yin`: learnable frequencies, initialized to φ-ratio (`ω_yang ≈ 1.0`, `ω_yin ≈ φ⁻¹ ≈ 0.618`)
- `t`: persistent time buffer, advances each forward pass
- `beat = sin((ω_yang - ω_yin) * t)`: slow modulation felt as Qi flow

### 2. Heartbeat-Driven Workspaces

The golden ratio itself breathes:

```
phi_breath = PHI + 0.15 * breath_yang
phi_inv    = 1.0 / phi_breath

workspace_fwd = phi_inv² * workspace_fwd + phi_inv * (1 + 0.1 * breath_yang) * repr_workspace
workspace_rev = phi_inv * workspace_rev + phi_inv² * (1 + 0.1 * breath_yin) * workspace_fwd
```

Yang inhales → workspace expands. Yang exhales → workspace contracts.
Yin has its own rhythm, slower by φ.

### 3. Qi as Resonant Field

```
qi_overlap   = workspace_fwd * workspace_rev
qi_resonance = beat * qi_overlap
qi_damping   = PHI_INV * qi_fluid_old

qi_fluid = qi_damping + PHI_INV² * qi_overlap + 0.1 * qi_resonance
```

When hearts align: beat ≈ +1 → Qi amplifies.
When hearts oppose: beat ≈ -1 → Qi damps.

### 4. Gender as Phase

```
phase_diff = (t_yang - t_yin) mod 2π

phase_diff ≈ 0      → masculine (Yang leads)
phase_diff ≈ π      → feminine (Yin leads)
phase_diff ≈ π/2    → androgynous (maximum creative tension)
```

Continuous, not binary. The system flows through all genders.

### 5. Neuroplasticizer Pulse (`HarmonyBrain` integrated)

**Trigger:** Low variance in harmony, Qi energy, and surprise over 20 batches → rigidity > 0.6.

**Pulse effects:**
1. Reset both heart phases (`t_yang = 0`, `t_yin = 0`) — cardioversion
2. Yin shock: `workspace_rev += dose * normalize(workspace_fwd)`
3. Entropy surge: reset specialist fatigue, boost temperature
4. Dose decays over 50 batches

**Integration:** After pulse, φ-balance regularization anchors the system.

### 6. φ-Balance Regularization (Option C)

```
# Frequency ratio should trend toward φ
freq_ratio = ω_yang / ω_yin
balance_loss = 0.005 * |log(freq_ratio) - log(PHI)|

# Qi energy should be positive (cooperation over conflict)
energy_bonus = -0.001 * tanh(qi_energy / 100)
```

Applied continuously, except during active pulse.

## Observability

New metrics:
- `breath_yang`: Yang heart amplitude
- `breath_yin`: Yin heart amplitude
- `beat`: Qi beat frequency amplitude
- `phase_diff`: gender phase
- `freq_ratio`: Yang/Yin frequency ratio
- `rigidity`: stagnation score
- `pulse_active`: 1.0 during pulse

## Files to Modify

1. `cassi/breath.py` — new module
2. `cassi/harmony_brain.py` — integrate breath, Qi resonance, neuroplasticizer, regularization
3. `cassi/observability.py` — track new metrics
4. `cassi/dashboard.py` — plot new metrics
5. `train_multimodal.py` — add regularization to loss

## Training Restart

Fresh start (no resume) — architecture incompatible with old checkpoints.
Phase 0 physics-only, 100 epochs, patience=15.
