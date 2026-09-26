"""Self-awareness controller for QiField.

A shallow, breath-carrier-modulated homeostatic regulator that reads Qi,
breath, and field-state signals and outputs actuators (alpha/gamma/rho/
perturb/m_self) to keep Qi circulating healthily.
 """

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV


@dataclass(init=False)
class CtrlOutputs:
    """Actuator values after clamping and breath modulation.

    New actuator set for the rebuilt QiField.  Old field names passed as
    keyword arguments to the constructor are silently ignored, and legacy
    attributes (mu_c, zeta_c) are available through __getattr__ with
    harmless defaults.
    """
    alpha: torch.Tensor          # [B], range [0.5, 2.0], centered 1.0
    gamma: torch.Tensor          # [B], range [0.5, 2.0], centered 1.0
    rho: torch.Tensor            # [B], range [0.5, 2.0], centered 1.0
    perturb: torch.Tensor        # [B], range [0.0, 0.1], centered 0.0
    m_self: torch.Tensor         # [B], range [0.5, 2.0], centered 1.0
    diagnostics: Dict[str, Any]

    C: ClassVar[int] = 13

    def __init__(self, *, alpha: torch.Tensor, gamma: torch.Tensor,
                 rho: Optional[torch.Tensor] = None,
                 perturb: Optional[torch.Tensor] = None,
                 m_self: Optional[torch.Tensor] = None,
                 diagnostics: Optional[Dict[str, Any]] = None,
                 h_next: Optional[torch.Tensor] = None,
                 **legacy_kwargs):
        """Construct CtrlOutputs, ignoring legacy kwargs (beta, mu_c, etc.)."""
        self.alpha = alpha
        self.gamma = gamma
        self.rho = rho if rho is not None else torch.ones_like(alpha)
        self.perturb = perturb if perturb is not None else torch.zeros_like(alpha)
        self.m_self = m_self if m_self is not None else torch.ones_like(alpha)
        self.diagnostics = diagnostics if diagnostics is not None else {}
        self.h_next = h_next

    def __getattr__(self, name: str) -> Any:
        """Provide harmless defaults for legacy fields."""
        if name == 'mu_c':
            return torch.zeros(self.C, device=self.alpha.device, dtype=self.alpha.dtype)
        if name == 'zeta_c':
            return torch.ones(self.C, device=self.alpha.device, dtype=self.alpha.dtype)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class SelfAwarenessController(nn.Module):
    """Self-regulating controller that reads Qi/breath/state signals.

    Args:
        C: number of chakras (fixed at 13).
        hidden_dim: controller MLP hidden dimension (default 64).
        qi_target_low: lower bound for legacy homeostasis band (default 0.01).
        qi_target_high: upper bound for legacy homeostasis band (default 10.0).
        ctrl_ema_decay: decay for controller hidden-state EMA (default PHI_INV).
    """

    def __init__(self, C: int = 13, hidden_dim: int = 64,
                 qi_target_low: float = 0.01, qi_target_high: float = 10.0,
                 ctrl_ema_decay: float = PHI_INV):
        super().__init__()
        self.C = C
        self.hidden_dim = hidden_dim
        self.qi_target_low = qi_target_low
        self.qi_target_high = qi_target_high
        self.ctrl_ema_decay = ctrl_ema_decay

        # ── New actuator heads (rebuilt QiField) ──
        # Input dim: C (qi_per_chakra) + 5 (q_trend, y/z ratio, field_energy,
        #             breath yang/yin) + hidden_dim.
        self.new_input_dim = C + 5 + hidden_dim

        self.input_proj = nn.Sequential(
            nn.Linear(self.new_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.hidden_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        # All heads are zero-initialized so the controller starts as a no-op.
        self.head_alpha   = nn.Linear(hidden_dim, 1)
        self.head_gamma   = nn.Linear(hidden_dim, 1)
        self.head_rho     = nn.Linear(hidden_dim, 1)
        self.head_perturb = nn.Linear(hidden_dim, 1)
        self.head_m_self  = nn.Linear(hidden_dim, 1)
        # Persistent controller state.
        self.register_buffer('h_ctrl', torch.zeros(hidden_dim))

        self._init_weights()

    def _init_weights(self):
        """Initialize weights for healthy gradient flow.

        Actuator heads are initialized with small Xavier weights (gain=0.1)
        so the controller starts near the no-op center but the heads can
        actually receive gradient signal from the very first step. Pure
        zero-init makes the heads gradient-dead (the no-op is an exact
        fixed point of the balance_loss). With small nonzero init, the
        balance_loss anchor is a soft pull, not a hard floor.

        Projection layers use small Xavier; LayerNorm uses PyTorch defaults
        (weight=1, bias=0) — a zero LayerNorm weight would force the
        output to zero regardless of input, so it must NOT be zero-initialized.
        """
        for module in [self.input_proj, self.hidden_proj]:
            for p in module.parameters():
                if p.dim() >= 2:
                    nn.init.xavier_uniform_(p, gain=0.5)

        for head in [self.head_alpha, self.head_gamma, self.head_rho,
                     self.head_m_self]:
            # Small Xavier init → outputs are near zero, in the linear
            # regime of tanh, so (1+tanh(...))*0.75 ≈ 1.0 + small_jitter.
            # The balance_loss pulls the small jitter back toward zero.
            nn.init.xavier_uniform_(head.weight, gain=0.1)
            nn.init.zeros_(head.bias)
        # Perturb head: bias = 0.0 (no perturbation at init).
        nn.init.xavier_uniform_(self.head_perturb.weight, gain=0.1)
        nn.init.zeros_(self.head_perturb.bias)

    # ═══════════════════ Public forward ═══════════════════

    def forward(self,
                qi_per_chakra: torch.Tensor,
                *args,
                q_trend: Optional[torch.Tensor] = None,
                y_over_z_ratio: Optional[torch.Tensor] = None,
                field_energy: Optional[torch.Tensor] = None,
                breath: Optional[Dict[str, torch.Tensor]] = None,
                prev_hidden: Optional[torch.Tensor] = None,
                reset: bool = False,
                **kwargs) -> CtrlOutputs:
        """Compute actuator values from Qi/breath/state signals.

        New-style call:
            controller(qi_per_chakra, q_trend=..., y_over_z_ratio=...,
                       field_energy=..., breath=..., ...)

        Legacy keyword arguments are silently ignored.
        """
        # New-style positional: (q_trend, y_over_z_ratio, field_energy, breath)
        new_q_trend = q_trend
        new_yz = y_over_z_ratio
        new_energy = field_energy
        new_breath = breath
        if not args:
            pass
        elif len(args) >= 4 and isinstance(args[0], torch.Tensor):
            new_q_trend, new_yz, new_energy, new_breath = args[0], args[1], args[2], args[3]
        elif len(args) == 1 and isinstance(args[0], dict):
            d = args[0]
            if set(d.keys()) == {'yang', 'yin'}:
                new_breath = d

        return self._forward_new(
            qi_per_chakra,
            q_trend=new_q_trend,
            y_over_z_ratio=new_yz,
            field_energy=new_energy,
            breath=new_breath,
            prev_hidden=prev_hidden,
            reset=reset,
        )

    # ═══════════════════ New forward (rebuilt QiField) ═══════════════════

    def _forward_new(self,
                     qi_per_chakra: torch.Tensor,       # [B, C]
                     q_trend: Optional[torch.Tensor] = None,      # [B]
                     y_over_z_ratio: Optional[torch.Tensor] = None,  # [B]
                     field_energy: Optional[torch.Tensor] = None,    # [B]
                     breath: Optional[Dict[str, torch.Tensor]] = None,
                     prev_hidden: Optional[torch.Tensor] = None,
                     reset: bool = False,
                     ) -> CtrlOutputs:
        """New controller interface aligned with the complex-wave QiField."""
        if reset:
            self.reset_state()

        device = qi_per_chakra.device
        B = qi_per_chakra.shape[0]

        # Default missing inputs to zeros on the correct device.
        def _vec(value: Optional[torch.Tensor]) -> torch.Tensor:
            if value is None:
                return torch.zeros(B, device=device, dtype=qi_per_chakra.dtype)
            v = value.to(device).flatten()
            if v.numel() == 1:
                return v.expand(B)
            return v[:B]

        q_trend_v      = _vec(q_trend)
        y_over_z_v     = _vec(y_over_z_ratio)
        field_energy_v = _vec(field_energy)

        if breath is None:
            yang = torch.zeros(B, device=device, dtype=qi_per_chakra.dtype)
            yin  = torch.zeros(B, device=device, dtype=qi_per_chakra.dtype)
        else:
            yang = breath.get('yang', torch.zeros(1, device=device)).to(device).flatten()
            yin  = breath.get('yin',  torch.zeros(1, device=device)).to(device).flatten()
            if yang.numel() == 1:
                yang = yang.expand(B)
            if yin.numel() == 1:
                yin = yin.expand(B)
            yang = yang[:B]
            yin  = yin[:B]

        # Recurrent hidden state.
        h_ctrl = self.h_ctrl.to(device)
        if prev_hidden is not None:
            h_ctrl = prev_hidden.to(device)
        else:
            h_ctrl = h_ctrl.unsqueeze(0).expand(B, -1)

        # Concatenate all inputs.
        x = torch.cat([
            qi_per_chakra.view(B, self.C),
            q_trend_v.unsqueeze(-1),
            y_over_z_v.unsqueeze(-1),
            field_energy_v.unsqueeze(-1),
            yang.unsqueeze(-1),
            yin.unsqueeze(-1),
            h_ctrl,
        ], dim=-1)

        h = self.input_proj(x)
        h = self.hidden_proj(h) + h_ctrl
        # Forward pass with residual recurrent connection.
        # Note: h_ctrl buffer update is deferred to the caller (must happen
        # outside any gradient-checkpointed region). The caller calls
        # self._compute_h_next(h) to get the new value, then
        # self._update_h_ctrl(h_next) after the checkpoint boundary.
        h_next = self._compute_h_next(h, base=prev_hidden)

        # Actuator heads: raw tanh -> scale -> bias -> clamp.
        raw_alpha   = torch.tanh(self.head_alpha(h))   * 0.75   # [-0.75, 0.75]
        raw_gamma   = torch.tanh(self.head_gamma(h))   * 0.75
        raw_rho     = torch.tanh(self.head_rho(h))     * 0.75
        raw_perturb = torch.tanh(self.head_perturb(h)) * 0.10   # [-0.10, 0.10]
        raw_m_self  = torch.tanh(self.head_m_self(h))  * 0.75

        alpha_val   = (1.0 + raw_alpha).clamp(0.5, 2.0).squeeze(-1)
        gamma_val   = (1.0 + raw_gamma).clamp(0.5, 2.0).squeeze(-1)
        rho_val     = (1.0 + raw_rho).clamp(0.5, 2.0).squeeze(-1)
        perturb_val = raw_perturb.clamp(0.0, 0.1).squeeze(-1)
        m_self_val  = (1.0 + raw_m_self).clamp(0.5, 2.0).squeeze(-1)

        diagnostics = {
            'ctrl_alpha':   alpha_val.mean().item(),
            'ctrl_gamma':   gamma_val.mean().item(),
            'ctrl_rho':     rho_val.mean().item(),
            'ctrl_perturb': perturb_val.mean().item(),
            'ctrl_m_self':  m_self_val.mean().item(),
            'ctrl_h_norm':  h.norm().item(),
        }

        return CtrlOutputs(
            alpha=alpha_val,
            gamma=gamma_val,
            rho=rho_val,
            perturb=perturb_val,
            m_self=m_self_val,
            diagnostics=diagnostics,
            h_next=h_next,
        )

    def _compute_h_next(self, h: torch.Tensor,
                         base: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Compute the EMA-updated hidden state without mutating the buffer.

        Returns the new h_ctrl value. The caller is responsible for the
        in-place copy_ to self.h_ctrl (which must happen outside any
        gradient-checkpointed region).

        Args:
            h: the new MLP output (per-sample, [B, hidden_dim])
            base: the hidden state to EMA from. If None, uses self.h_ctrl.
                Pass the snapshot when calling inside a gradient-checkpointed
                region so the EMA uses a frozen copy, not the mutable buffer.
                If base has a batch dimension, it is reduced to [hidden_dim]
                by taking the mean — the EMA is always per-hidden-dim.
        """
        h_next = h.detach().mean(dim=0)
        if base is None:
            base = self.h_ctrl.to(h_next.device)
        elif base.dim() == 2:
            base = base.mean(dim=0)
        return self.ctrl_ema_decay * base + (1.0 - self.ctrl_ema_decay) * h_next

    def _update_h_ctrl(self, h_next: torch.Tensor) -> None:
        """In-place update of self.h_ctrl. Must be called OUTSIDE gradient
        checkpointing (the buffer mutation breaks gradient flow through
        the checkpoint boundary)."""
        self.h_ctrl.copy_(h_next.to(self.h_ctrl.device))


    # ═══════════════════ Homeostasis regularizer ═══════════════════

    def compute_homeo_loss(self,
                           q_mean: torch.Tensor,
                           weight: float = 0.001) -> torch.Tensor:
        """Tiny regularizer keeping per-batch Q near the healthy [PHI_INV/2, PHI] band.

        Args:
            q_mean: [B] or scalar tensor of mean Qi values.
            weight: multiplier; default 0.001.  When weight == 0.0 the loss is
                exactly zero and no computation is performed.
        """
        if weight == 0.0:
            return torch.tensor(0.0, device=q_mean.device, dtype=q_mean.dtype)
        low = PHI_INV / 2.0
        high = PHI
        low_violation  = F.relu(low - q_mean)
        high_violation = F.relu(q_mean - high)
        loss = (low_violation.pow(2) + high_violation.pow(2)).mean()
        return weight * loss
    def compute_balance_loss(self,
                             ctrl_outputs: 'CtrlOutputs',
                             weight: float = 0.01) -> torch.Tensor:
        """Balance regularizer: keep controller actuators near their natural centers.

        Per convention (chakra balance), "chakra balance is the ideal". This loss anchors
        alpha/gamma/rho/m_self to 1.0 (the value that means "no modulation")
        and perturb to 0, preventing the controller from learning to suppress
        any single actuator. The most common failure mode is alpha->0
        (silencing the brain->mind modulation), which collapses brain energy
        and breaks the 13-chakra balance.

        Args:
            ctrl_outputs: CtrlOutputs from the controller's forward pass.
                Must be the non-detached output so the gradient flows back
                to the controller's head_* parameters.
            weight: multiplier; default 0.01. When weight == 0.0, returns 0.
        """
        if weight == 0.0:
            return torch.tensor(0.0, device=ctrl_outputs.alpha.device)
        # .sum() (not .mean()) so the weight is batch-size-independent.
        # Gradient per element: weight * (1/5) * 2*(actuator - 1.0),
        # regardless of batch size. .mean() would scale the gradient as 1/B.
        loss = (
            (ctrl_outputs.alpha - 1.0).pow(2).sum() +
            (ctrl_outputs.gamma - 1.0).pow(2).sum() +
            (ctrl_outputs.rho - 1.0).pow(2).sum() +
            (ctrl_outputs.m_self - 1.0).pow(2).sum() +
            ctrl_outputs.perturb.pow(2).sum()
        ) / 5.0
        return weight * loss


    def reset_state(self):
        """Clear all persistent controller state."""
        with torch.no_grad():
            self.h_ctrl.zero_()
