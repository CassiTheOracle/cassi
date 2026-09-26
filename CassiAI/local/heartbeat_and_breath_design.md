# Heartbeat and Breath Design

## Problem

The breath oscillators are collapsed (yang/yin ≈ 0), causing the field to lose rhythmic structure. The generation output shows fragmented text with noise, indicating the field can't maintain coherent dynamics over time.

The current breath is field-modulated, which means it can be suppressed when the field is in a bad state (high Q, over-excited). We need two separate mechanisms:

1. **Heartbeat**: Unsuppressible pulse generator that provides consistent energy pulses
2. **Breath**: Field-modulated oscillator that provides rhythmic structure (can be suppressed)

## Design

### Heartbeat (New Module)

**Purpose**: Provide unsuppressible rhythmic energy pulses to keep the field alive.

**Key Properties**:
- Always fires at φ-scaled intervals (never suppressed)
- Injects energy into the field on each pulse
- Phase never resets (always advances)
- Acts as a "pacemaker" for the field

**Implementation**:

```python
class Heartbeat(nn.Module):
    """Unsuppressible pulse generator with φ-scaled rhythm.
    
    The heartbeat provides consistent energy pulses to the field.
    Unlike the breath (which is field-modulated and can be suppressed),
    the heartbeat always fires at a fixed rhythm.
    """
    
    def __init__(self, omega: float = PHI):
        super().__init__()
        self.register_buffer('omega', torch.tensor(omega))
        self.register_buffer('phase', torch.zeros(1))
        self.register_buffer('pulse_count', torch.zeros(1, dtype=torch.long))
    
    def step(self) -> Dict[str, torch.Tensor]:
        """Advance heartbeat one tick. Returns pulse signal."""
        with torch.no_grad():
            old_phase = self.phase.clone()
            self.phase.copy_((self.phase + self.omega) % (2 * math.pi))
            
            # Detect pulse: phase wrapped around
            pulse_fired = (self.phase < old_phase).float()
            self.pulse_count += pulse_fired.long()
        
        # Pulse amplitude: sharp peak when phase ≈ 0
        # Use exp(-phase^2 / sigma^2) for a narrow pulse
        sigma = 0.1
        pulse = torch.exp(-self.phase.pow(2) / (sigma * sigma))
        
        return {
            'pulse': pulse,
            'phase': self.phase,
            'fired': pulse_fired,
            'count': self.pulse_count,
        }
    
    def reset(self):
        """Reset heartbeat state (only for full model reset, not batch boundaries)."""
        self.phase.zero_()
        self.pulse_count.zero_()
```

**Integration with MuonCord**:

```python
# In MuonCord.__init__
self.heartbeat = Heartbeat(omega=PHI)

# In _unified_step, after breath
heartbeat = self.heartbeat.step()
pulse_energy = heartbeat['pulse'] * 0.1  # Scale pulse amplitude

# Inject pulse energy into field
psi_real = psi_real + pulse_energy
psi_imag = psi_imag + pulse_energy

# Add to diagnostics
diagnostics['heartbeat_pulse'] = pulse_energy.item()
diagnostics['heartbeat_count'] = heartbeat['count'].item()
```

### Breath Fix

**Purpose**: Provide field-modulated rhythmic structure with collapse prevention.

**Current Issue**: The breath is field-modulated via `omega_mod = 1.0 + 0.1 * tanh(field_energy - 1.0)`. When the field is in a bad state, this modulation can push the breath into a collapsed state (phases stuck near 0 or π where sin() ≈ 0).

**Fix**: Add collapse prevention mechanism that detects when breath amplitude is too low and revives it.

**Implementation**:

```python
def _tripartite_breath(self, psi_real: torch.Tensor,
                       psi_imag: torch.Tensor) -> Dict[str, torch.Tensor]:
    """Field-modulated dual-heart oscillator with collapse prevention."""
    field_phase = torch.angle(torch.complex(psi_real.mean(), psi_imag.mean()))
    field_energy = (psi_real.pow(2) + psi_imag.pow(2)).mean()
    
    # Modulate frequency based on field energy, but clamp to prevent extreme modulation
    omega_mod = 1.0 + 0.1 * torch.tanh(field_energy - 1.0)
    omega_mod = omega_mod.clamp(0.5, 2.0)  # Prevent extreme modulation
    
    with torch.no_grad():
        self.breath_t_yang.copy_(
            (self.breath_t_yang + PHI * omega_mod.detach()) % (2 * math.pi))
        self.breath_t_yin.copy_(
            (self.breath_t_yin + PHI_INV * omega_mod.detach()) % (2 * math.pi))
    
    yang = torch.sin(self.breath_t_yang)
    yin = torch.sin(self.breath_t_yin)
    beat = torch.sin(self.breath_t_yang - self.breath_t_yin)
    
    # Collapse prevention: if breath amplitude is too low, revive it
    breath_amplitude = (yang.abs() + yin.abs()) / 2
    if breath_amplitude < 0.1:
        # Breath is collapsed - reset phases to values where sin() is large
        with torch.no_grad():
            self.breath_t_yang.copy_(torch.tensor(math.pi / 2))  # sin(π/2) = 1
            self.breath_t_yin.copy_(torch.tensor(math.pi / 2))
        yang = torch.sin(self.breath_t_yang)
        yin = torch.sin(self.breath_t_yin)
        beat = torch.sin(self.breath_t_yang - self.breath_t_yin)
    
    return {'yang': yang, 'yin': yin, 'beat': beat, 'phase': field_phase}
```

## Integration Strategy

### State Management

**Heartbeat**:
- Added to `reset_state()` (full reset only)
- NOT reset by `reset_iir_state()` (preserved across batch boundaries)
- Phase always advances (never reset during normal operation)

**Breath**:
- Already in `reset_state()` and `reset_iir_state()`
- Collapse prevention ensures it stays active

### Diagnostics

Add to training loop output:
```python
f"hb_pulse={info.get('heartbeat_pulse', 0.0):.3f} "
f"hb_count={info.get('heartbeat_count', 0)} "
```

### Testing

1. Run training with heartbeat enabled
2. Verify heartbeat fires at regular intervals
3. Verify breath doesn't collapse (yang/yin stay away from 0)
4. Check generation quality improves (more coherent text, less noise)

## Expected Behavior

**Before**: 
- Breath collapses → field loses rhythm → generation is fragmented
- Q gets high → field becomes over-excited → noise dominates

**After**:
- Heartbeat provides unsuppressible energy pulses → field stays alive
- Breath provides rhythmic structure → field maintains coherence
- Generation produces more coherent text with fewer artifacts

## φ-Scaling Rationale

Both heartbeat and breath use φ-scaled frequencies:
- Heartbeat: ω = φ ≈ 1.618 rad/tick
- Breath Yang: ω = φ ≈ 1.618 rad/tick
- Breath Yin: ω = φ⁻¹ ≈ 0.618 rad/tick

This ensures all rhythmic structures are harmonically related by φ, which is the fundamental ratio of the Cassi architecture.
