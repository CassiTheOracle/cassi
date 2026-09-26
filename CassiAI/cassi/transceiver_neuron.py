"""Complex transceiver neuron for QiField.

A single transceiver maintains a persistent complex-valued IIR resonator.
Because ROCm/HIP complex dtype support is uncertain, the complex state is
stored as separate real/imag buffers and all arithmetic is implemented on
real/imag pairs.
"""

from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV


class ComplexTransceiverNeuron(nn.Module):
    """Complex-valued transceiver neuron with a φ-damped IIR resonator.

    Args:
        width: feature dimension of the neuron (a single transceiver row).
        theta_init: initial resonant angle in radians (default 0.5).
    """

    def __init__(self, width: int, theta_init: float = 0.5):
        super().__init__()
        self.width = width

        # Damping set to the golden inverse for stability.
        self.register_buffer('rho', torch.tensor(PHI_INV, dtype=torch.float32))

        # Learned resonant frequency.
        self.theta = nn.Parameter(torch.tensor(theta_init, dtype=torch.float32))

        # Feed-forward and feedback coefficients are learned, then sigmoided.
        self.b0 = nn.Parameter(torch.zeros(width))
        self.b1 = nn.Parameter(torch.zeros(width))

        # Output gain.
        self.emit_gain = nn.Parameter(torch.zeros(width))

        # Persistent IIR state: h[n] and h[n-1], stored as real/imag pairs.
        self.register_buffer('h_real', torch.zeros(1, width))
        self.register_buffer('h_imag', torch.zeros(1, width))
        self.register_buffer('h_prev_real', torch.zeros(1, width))
        self.register_buffer('h_prev_imag', torch.zeros(1, width))
        self.register_buffer('x_prev_real', torch.zeros(1, width))
        self.register_buffer('x_prev_imag', torch.zeros(1, width))

    @staticmethod
    def complex_mul(a_real: torch.Tensor, a_imag: torch.Tensor,
                    b_real: torch.Tensor, b_imag: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Multiply two complex tensors represented as real/imag pairs."""
        real = a_real * b_real - a_imag * b_imag
        imag = a_real * b_imag + a_imag * b_real
        return real, imag

    def reset_state(self, batch_size: int, device: torch.device) -> None:
        """Zero the persistent IIR state for the given batch size."""
        self.h_real = torch.zeros(batch_size, self.width, device=device)
        self.h_imag = torch.zeros(batch_size, self.width, device=device)
        self.h_prev_real = torch.zeros(batch_size, self.width, device=device)
        self.h_prev_imag = torch.zeros(batch_size, self.width, device=device)
        self.x_prev_real = torch.zeros(batch_size, self.width, device=device)
        self.x_prev_imag = torch.zeros(batch_size, self.width, device=device)

    def forward(self, received_real: torch.Tensor,
                received_imag: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute one transceiver step.

        Args:
            received_real/received_imag: [B, width]

        Returns:
            tx_real, tx_imag: [B, width]
        """
        # Complex pole: z = rho * exp(i * theta)
        cos_theta = torch.cos(self.theta)
        # Standard complex-conjugate-pole IIR coefficients.
        a1 = 2.0 * self.rho * cos_theta            # scalar
        a2 = -(self.rho ** 2)                      # scalar

        # Learnable feed coefficients via sigmoid (b0 + b1 acts as effective gain).
        b0 = torch.sigmoid(self.b0)
        b1 = torch.sigmoid(self.b1)

        # Clone reads that are multiplied by differentiable params (they are
        # saved for backward); use detached views for reads multiplied by the
        # non-differentiable a2 coefficient.
        h_real = self.h_real.detach().clone()
        h_imag = self.h_imag.detach().clone()
        h_prev_real = self.h_prev_real.detach()
        h_prev_imag = self.h_prev_imag.detach()
        x_prev_real = self.x_prev_real.detach().clone()
        x_prev_imag = self.x_prev_imag.detach().clone()

        # h_new = a1*h + a2*h_prev + b0*received + b1*x_prev
        h_new_real = (a1 * h_real + a2 * h_prev_real
                      + b0 * received_real + b1 * x_prev_real)
        h_new_imag = (a1 * h_imag + a2 * h_prev_imag
                      + b0 * received_imag + b1 * x_prev_imag)
        # Update persistent state without gradient flow through the buffer.
        with torch.no_grad():
            self.x_prev_real.copy_(received_real.detach())
            self.x_prev_imag.copy_(received_imag.detach())
            self.h_prev_real.copy_(self.h_real)
            self.h_prev_imag.copy_(self.h_imag)
            self.h_real.copy_(h_new_real.detach())
            self.h_imag.copy_(h_new_imag.detach())
        # Transmission: scaled sigmoid gain * PHI_INV * tanh(state)
        gain = torch.sigmoid(self.emit_gain)
        tx_real = gain * PHI_INV * torch.tanh(h_new_real)
        tx_imag = gain * PHI_INV * torch.tanh(h_new_imag)

        return tx_real, tx_imag
