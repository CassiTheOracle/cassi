"""Heartbeat — Unsuppressible pulse generator with φ-scaled rhythm.

The heartbeat provides consistent energy pulses to the field, acting as a
pacemaker that keeps the field alive. Unlike the breath (which is field-modulated
and can be suppressed), the heartbeat always fires at a fixed rhythm.

The heartbeat fires a sharp pulse every time its phase wraps around (every 2π/ω steps),
injecting energy into the field to maintain coherent dynamics.
"""

import torch
import torch.nn as nn
import math
from typing import Dict

from cassi._chakra_utils import PHI


class Heartbeat(nn.Module):
    """Unsuppressible pulse generator with φ-scaled rhythm.
    
    The heartbeat provides consistent energy pulses to the field.
    Unlike the breath (which is field-modulated and can be suppressed),
    the heartbeat always fires at a fixed rhythm.
    
    Attributes:
        omega: Angular frequency (default: φ ≈ 1.618 rad/tick)
        phase: Current phase in [0, 2π)
        pulse_count: Number of pulses fired since last reset
    """
    
    def __init__(self, omega: float = PHI):
        super().__init__()
        self.register_buffer('omega', torch.tensor(omega))
        self.register_buffer('phase', torch.zeros(1))
        self.register_buffer('pulse_count', torch.zeros(1, dtype=torch.long))
    
    def step(self) -> Dict[str, torch.Tensor]:
        """Advance heartbeat one tick. Returns pulse signal.
        
        Returns:
            {
                'pulse': Pulse amplitude (sharp peak when phase ≈ 0),
                'phase': Current phase in [0, 2π),
                'fired': 1.0 if pulse fired this step, 0.0 otherwise,
                'count': Total number of pulses fired,
            }
        """
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
