"""PredictionOperator — composite prediction from transceivers and cross-chakra mixing.

Owns:
- transceivers (one ComplexTransceiverNeuron per chakra — the only learned
  per-chakra predictor)
- cross_chakra mixing Linear(C, C) — a single linear projection, not an MLP
- chakra decomposition/composition helpers

No classical MLP is allowed in the model architecture.

This is the exact computation from QiField.predict(), decomposed into a
standalone module. No imports from cassi.qi_field.
"""

from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from cassi._chakra_utils import phi_chakra_widths
from cassi.cord import PHI, PHI_INV
from cassi.transceiver_neuron import ComplexTransceiverNeuron



class PredictionOperator(nn.Module):
    """Prediction operator: transceiver neurons + cross-chakra mixing.

    Given the current complex field ψ = (psi_real, psi_imag), computes a
    self-prediction P[ψ] that is fed into the Qi dynamics as the source of
    prediction error.

    Each chakra independently runs its transceiver neuron on the chakra mean,
    then cross-chakra mixing exchanges information between chakras. The only
    learned parameters are the IIR transceivers and a single Linear(C, C)
    cross-chakra mixer — no classical MLP.
    """

    def __init__(
        self,
        d: int,
        C: int = 13,
        widths: Optional[List[int]] = None,
        N: int = 64,
    ):
        super().__init__()
        self.C = C
        self.N = N
        self.d = d

        # φ-scaled chakra widths — caller may pass custom widths, else compute canonically
        if widths is not None:
            assert len(widths) == C, f"widths length {len(widths)} != C={C}"
            assert sum(widths) == d, f"widths sum {sum(widths)} != d={d}"
            self.chakra_widths = widths
        else:
            self.chakra_widths = phi_chakra_widths(d, C)

        self.transceivers = nn.ModuleList([
            ComplexTransceiverNeuron(
                width=self.chakra_widths[c],
                theta_init=0.1 * (PHI ** (c % 8)),
            )
            for c in range(C)
        ])


        # Cross-chakra mixing: per-chakra means pass through a small Linear
        self.cross_chakra = nn.Linear(self.C, self.C, bias=True)
        nn.init.zeros_(self.cross_chakra.weight)
        nn.init.zeros_(self.cross_chakra.bias)


    # ── Chakra decomposition / composition ──

    def _decompose_chakras(
        self, psi_real: torch.Tensor, psi_imag: torch.Tensor
    ) -> Tuple[List[torch.Tensor], List[torch.Tensor]]:
        """Split psi into C per-chakra real/imag lists.

        Args:
            psi_real: [B, N, d]
            psi_imag: [B, N, d]

        Returns:
            re_parts, im_parts: each a list of C tensors [B, N, dc].
        """
        re_parts, im_parts = [], []
        off = 0
        for c in range(self.C):
            dc = self.chakra_widths[c]
            re_parts.append(psi_real[:, :, off:off + dc])
            im_parts.append(psi_imag[:, :, off:off + dc])
            off += dc
        return re_parts, im_parts

    @staticmethod
    def _compose_chakras(
        re_parts: List[torch.Tensor], im_parts: List[torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Concatenate per-chakra lists back into full tensors.

        Args:
            re_parts, im_parts: each a list of C tensors [B, N, dc].

        Returns:
            psi_real, psi_imag: [B, N, d].
        """
        return torch.cat(re_parts, dim=-1), torch.cat(im_parts, dim=-1)

    @staticmethod
    def _complex_norm2(
        a_real: torch.Tensor, a_imag: torch.Tensor
    ) -> torch.Tensor:
        """Squared magnitude of a complex tensor."""
        return a_real ** 2 + a_imag ** 2

    # ── Forward ──

    def forward(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        use_residual: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """Compute one prediction step.

        Args:
            psi_real: [B, N, d] real part of the field.
            psi_imag: [B, N, d] imaginary part of the field.
            use_residual: DEPRECATED — accepted for backward compatibility but
                ignored. The residual MLP has been removed (classical ML is
                not allowed in the model architecture).

        Returns:
            P_re, P_im: [B, N, d] predictions.
            eps2: [B, N, d] prediction error squared magnitude.
            diag: dict of diagnostic tensors (per-chakra means).
        """
        # ── 13-chakra path: transceivers only + cross-chakra mix ──
        re_parts, im_parts = self._decompose_chakras(psi_real, psi_imag)
        pred_re, pred_im = [], []

        for c in range(self.C):
            psi_c_re = re_parts[c]
            psi_c_im = im_parts[c]
            B, N, dc = psi_c_re.shape

            mean_re = psi_c_re.mean(dim=1, keepdim=True)
            mean_im = psi_c_im.mean(dim=1, keepdim=True)

            tx_re, tx_im = self.transceivers[c](mean_re.squeeze(1), mean_im.squeeze(1))
            tx_re = tx_re.unsqueeze(1).expand(-1, N, -1)
            tx_im = tx_im.unsqueeze(1).expand(-1, N, -1)

            pred_re.append(psi_c_re + tx_re)
            pred_im.append(psi_c_im + tx_im)

        # Cross-chakra mixing: per-chakra scalar means -> Linear(C, C) -> broadcast back
        chakra_means_re = torch.stack([p.mean(dim=(1, 2)) for p in pred_re], dim=1)  # [B, C]
        chakra_means_im = torch.stack([p.mean(dim=(1, 2)) for p in pred_im], dim=1)  # [B, C]
        mix_re = self.cross_chakra(chakra_means_re)  # [B, C]
        mix_im = self.cross_chakra(chakra_means_im)  # [B, C]

        for c in range(self.C):
            dc = self.chakra_widths[c]
            pred_re[c] = pred_re[c] + mix_re[:, c].view(-1, 1, 1).expand(-1, N, dc)
            pred_im[c] = pred_im[c] + mix_im[:, c].view(-1, 1, 1).expand(-1, N, dc)

        P_re, P_im = self._compose_chakras(pred_re, pred_im)
        eps2 = self._complex_norm2(psi_real - P_re, psi_imag - P_im)

        diag = {
            'chakra_means_re': chakra_means_re.detach(),
            'chakra_means_im': chakra_means_im.detach(),
        }
        return P_re, P_im, eps2, diag

    def reset_transceiver_states(self, batch_size: int, device: torch.device) -> None:
        """Reset all transceiver IIR states for a new batch."""
        for c in range(self.C):
            self.transceivers[c].reset_state(batch_size, device)
