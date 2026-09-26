"""CordBus — the mind<->brain conduit.

The bottleneck bus is the formal realization of "the cord IS the conduit" from
section 10.1 of the Qi-Fluid formalism. It replaces the 6 ad-hoc learned
projections that previously coupled MindBrainField:

  - brain_input_proj (mind -> brain)        -> cord.ascend + brain.bus_to_input
  - brain_to_mind_psi_{real,imag} (brain -> mind) -> cord.descend + learned coupling
  - mind_to_brain_{damping,breath,coupling}      -> removed (controller no longer
                                                   modulates the brain top-down;
                                                   balance_loss keeps actuators near 1.0)

The bus is per-position `[B, N, cord_width]` so the brain can see WHERE in the
sequence the mind is attending (not just a global field mean). The bottleneck
is in the feature dimension: d -> cord_width. The bus is filtered through a
single phi-damped biquad - the universal structure of every learned predictor
in Cassi (per the formalism's core principles).

NO classical MLP. The only learned parameters are two single `nn.Linear`
projections and two scalar biquad coefficients (theta, b0).
"""
import math
import torch
import torch.nn as nn

from cassi.cord import PHI, PHI_INV


class CordBus(nn.Module):
    """phi-damped bottleneck bus between the mind's psi-field and the brain's Spine3D.

    Args:
        d: total field dimension (mind's d, not the brain's D).
        cord_width: bottleneck width (default d // 4).
        N: spatial positions (sequence length).
        buffer_B: persistent-state batch dim (default 1, expanded per call).
    """

    def __init__(self, d: int, cord_width: int, N: int, buffer_B: int = 1):
        super().__init__()
        self.d = d
        self.cord_width = cord_width
        self.N = N

        # Two single-Linears (the only learned projections, no MLP)
        self.ascend_proj = nn.Linear(d, cord_width, bias=False)
        self.descend_proj = nn.Linear(cord_width, d, bias=False)
        nn.init.normal_(self.ascend_proj.weight, std=0.02 / math.sqrt(d))
        nn.init.normal_(self.descend_proj.weight, std=0.02 / math.sqrt(cord_width))

        # One shared biquad (not per-chakra - the bus is already compressed).
        # Two scalar coefficients: theta (frequency) and b0 (input gain).
        # The pole magnitude is fixed at rho = PHI_INV (universal damping);
        # only the angle theta and the input gain b0 are learned.
        self.bus_theta = nn.Parameter(torch.tensor(0.0))
        self.bus_b0 = nn.Parameter(torch.tensor(0.0))

        # Persistent IIR state (mirrors QiField's h1/h2 persistent buffers).
        self.register_buffer('bus_state', torch.zeros(buffer_B, N, cord_width))
        self.register_buffer('bus_h1', torch.zeros(buffer_B, N, cord_width))
        self.register_buffer('bus_h2', torch.zeros(buffer_B, N, cord_width))

    # --- Biquad core (phi-damped, universal) ---

    def _biquad_step(self, x: torch.Tensor, h1: torch.Tensor, h2: torch.Tensor):
        """One step of the phi-damped biquad: y = b0*x + a1*h1 + a2*h2.

        With rho = PHI_INV (universal damping), a1 = 2*rho*cos(theta),
        a2 = -rho^2, the biquad has poles at z = rho * e^{+/- i theta} -
        the universal phi-damped IIR structure used in CordPhysics and
        ChakraIIRBank. The pole magnitude is fixed at rho (never diverges);
        the angle theta (frequency) and the input gain b0 are learned.

        Returns (y, h1_next, h2_next). Caller decides whether to commit state.
        """
        rho = PHI_INV
        theta = torch.sigmoid(self.bus_theta) * math.pi
        a1 = 2.0 * rho * torch.cos(theta)
        a2 = -(rho ** 2)
        b0 = torch.sigmoid(self.bus_b0)
        y = b0 * x + a1 * h1 + a2 * h2
        return y, y, h1

    def _expand_buffers(self, B: int) -> None:
        """Resize persistent buffers to accommodate batch size B."""
        N, W = self.N, self.cord_width
        dev = self.bus_h1.device
        self.register_buffer('bus_state', torch.zeros(B, N, W, device=dev))
        self.register_buffer('bus_h1',    torch.zeros(B, N, W, device=dev))
        self.register_buffer('bus_h2',    torch.zeros(B, N, W, device=dev))

    # --- Ascend: mind -> bus (commits state) ---

    def ascend(self, psi: torch.Tensor) -> torch.Tensor:
        """Project psi-field [B, N, d] to bus signal [B, N, cord_width] and filter.

        Commits the biquad state (h1, h2, bus_state) by assignment (clone
        then write), not in-place. The biquad inputs are detached BEFORE
        the recurrence so subsequent buffer writes do not corrupt the
        autograd graph when y is used downstream in the K_train loop
        (per convention).
        """
        B = psi.shape[0]
        # Expand persistent buffers if batch size exceeds stored size
        if B > self.bus_h1.shape[0]:
            self._expand_buffers(B)
        z = self.ascend_proj(psi)               # [B, N, cord_width]
        # Detach persistent state before the biquad so the output does not
        # carry a reference to the buffer.
        h1_in = self.bus_h1[:B].detach().clone()
        h2_in = self.bus_h2[:B].detach().clone()
        y, h1n, h2n = self._biquad_step(z, h1_in, h2_in)
        # Commit state by assignment (clone the buffer, then write the slice).
        new_h1 = self.bus_h1.clone()
        new_h1[:B] = h1n.detach()
        self.bus_h1 = new_h1
        new_h2 = self.bus_h2.clone()
        new_h2[:B] = h2n.detach()
        self.bus_h2 = new_h2
        new_state = self.bus_state.clone()
        new_state[:B] = y.detach()
        self.bus_state = new_state
        return y

    # --- Descend: brain response -> mind perturbation (does NOT commit state) ---

    def descend(self, brain_bus_response: torch.Tensor) -> torch.Tensor:
        """Filter brain's bus response and project back to psi-field [B, N, d].

        Does NOT update bus_h1/bus_h2. Inputs are detached before the biquad
        so the output is safe to add to psi (which carries gradients).
        """
        B = brain_bus_response.shape[0]
        if B > self.bus_h1.shape[0]:
            self._expand_buffers(B)
        h1 = self.bus_h1[:B].detach()
        h2 = self.bus_h2[:B].detach()
        z, _, _ = self._biquad_step(brain_bus_response, h1, h2)
        return self.descend_proj(z)              # [B, N, d]

    def reset_state(self) -> None:
        """Clear all persistent bus state (mirrors QiField.reset_state)."""
        self.bus_state.zero_()
        self.bus_h1.zero_()
        self.bus_h2.zero_()
