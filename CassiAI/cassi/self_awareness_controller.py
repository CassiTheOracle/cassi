"""Self-awareness controller for QiField.

A shallow, breath-carrier-modulated homeostatic regulator that reads Qi,
breath, and field-state signals and outputs actuators to keep Qi circulating
healthily.  This version supports the rebuilt QiField actuator set
(alpha/gamma/rho/perturb/m_self) while preserving backward-compatible imports
and a legacy call path for older QiField variants.
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV


@dataclass(init=False)
class CtrlOutputs:
    """Actuator values after clamping and breath modulation.

    New actuator set for the rebuilt QiField.  Old field names passed as
    keyword arguments to the constructor are silently ignored, and legacy
    attributes (beta, delta_mem, mu_c, zeta_c) are available through
    __getattr__ with harmless defaults.
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
                 **legacy_kwargs):
        """Construct CtrlOutputs, ignoring legacy kwargs (beta, mu_c, etc.)."""
        self.alpha = alpha
        self.gamma = gamma
        self.rho = rho if rho is not None else torch.ones_like(alpha)
        self.perturb = perturb if perturb is not None else torch.zeros_like(alpha)
        self.m_self = m_self if m_self is not None else torch.ones_like(alpha)
        self.diagnostics = diagnostics if diagnostics is not None else {}

    def __getattr__(self, name: str) -> Any:
        """Provide harmless defaults for legacy fields."""
        if name == 'beta':
            return torch.zeros_like(self.alpha)
        if name == 'delta_mem':
            return torch.zeros_like(self.alpha)
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

        # ── Legacy actuator heads (old QiField variants) ──
        # Kept for backward-compatible call path.
        legacy_input_dim = 3 * C + 5 + 6 + 3 + 1 + 1 + hidden_dim
        self.legacy_input_proj = nn.Sequential(
            nn.Linear(legacy_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.legacy_hidden_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.head_alpha_legacy = nn.Linear(hidden_dim, 1)
        self.head_mu_legacy    = nn.Linear(hidden_dim, C)
        self.head_zeta_legacy  = nn.Linear(hidden_dim, C)
        self.head_gamma_legacy = nn.Linear(hidden_dim, 1)

        # Persistent controller state.
        self.register_buffer('h_ctrl', torch.zeros(hidden_dim))
        self.register_buffer('qi_ema_c', torch.zeros(C))
        self.register_buffer('prev_outputs', torch.zeros(2 * C + 2))

        self._init_weights()

    def _init_weights(self):
        """Zero-initialize all actuator heads so the controller starts as a no-op.

        Projection layers use small Xavier for healthy gradient flow.
        """
        for module in [self.input_proj, self.hidden_proj,
                       self.legacy_input_proj, self.legacy_hidden_proj]:
            for p in module.parameters():
                if p.dim() >= 2:
                    nn.init.xavier_uniform_(p, gain=0.5)
                else:
                    nn.init.zeros_(p)

        for head in [self.head_alpha, self.head_gamma, self.head_rho,
                     self.head_perturb, self.head_m_self]:
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

        for head in [self.head_alpha_legacy, self.head_mu_legacy,
                     self.head_zeta_legacy, self.head_gamma_legacy]:
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

    # ═══════════════════ Public forward (dispatch) ═══════════════════

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

        Supports two call conventions:
          * New: controller(qi_per_chakra, q_trend, y_over_z_ratio,
                           field_energy, breath, ...)
          * Legacy: controller(qi_per_chakra, breath, Q_mean, Q_max, ...)
        """
        legacy_keys = {
            'Q_mean', 'Q_max', 'Q_var', 'Q_high_frac', 'Q_low_frac', 'Q_sat_frac',
            'Q_transport_mean', 'Q_transport_max', 'Q_transport_clip',
            'harmony_weights', 'psi_sat_frac', 'field_ratio',
        }
        is_legacy_kwargs = bool(kwargs.keys() & legacy_keys)

        # Start from any explicitly provided keyword values.
        new_q_trend = q_trend
        new_yz = y_over_z_ratio
        new_energy = field_energy
        new_breath = breath

        def _call_legacy():
            if 'breath' not in kwargs and breath is not None:
                kwargs['breath'] = breath
            if 'reset' not in kwargs:
                kwargs['reset'] = reset
            return self._forward_legacy(qi_per_chakra, *args, **kwargs)

        if not is_legacy_kwargs and args:
            if (len(args) >= 4 and isinstance(args[0], torch.Tensor)
                    and isinstance(args[3], dict)):
                # New-style positional: (q_trend, y_over_z_ratio, field_energy, breath)
                new_q_trend, new_yz, new_energy, new_breath = args[0], args[1], args[2], args[3]
            elif len(args) == 1 and isinstance(args[0], dict):
                d = args[0]
                if set(d.keys()) == {'yang', 'yin'}:
                    new_breath = d
                else:
                    return _call_legacy()
            else:
                return _call_legacy()

        if is_legacy_kwargs:
            return _call_legacy()

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

        # Forward pass with residual recurrent connection.
        h = self.input_proj(x)
        h = self.hidden_proj(h) + h_ctrl

        # Update shared recurrent state when using the internal buffer.
        if prev_hidden is None:
            with torch.no_grad():
                h_next = h.detach().mean(dim=0)
                self.h_ctrl.copy_(
                    self.ctrl_ema_decay * self.h_ctrl.to(device) +
                    (1.0 - self.ctrl_ema_decay) * h_next
                )

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
        )

    # ═══════════════════ Legacy forward (old QiField variants) ═══════════════════

    def _forward_legacy(self,
                        qi_per_chakra: torch.Tensor,      # [C]
                        breath: Dict[str, torch.Tensor],
                        Q_mean: torch.Tensor,              # scalar
                        Q_max: torch.Tensor,               # scalar
                        Q_var: torch.Tensor,               # scalar
                        Q_high_frac: torch.Tensor,         # scalar
                        Q_low_frac: torch.Tensor,          # scalar
                        Q_sat_frac: torch.Tensor,          # scalar
                        Q_transport_mean: torch.Tensor,    # scalar
                        Q_transport_max: torch.Tensor,     # scalar
                        Q_transport_clip: torch.Tensor,    # scalar
                        harmony_weights: torch.Tensor,     # [C]
                        psi_sat_frac: torch.Tensor,        # scalar
                        field_ratio: torch.Tensor,         # scalar
                        reset: bool = False,
                        ) -> CtrlOutputs:
        """Original controller interface kept for backward compatibility."""
        if reset:
            self.reset_state()

        device = qi_per_chakra.device

        h_ctrl = self.h_ctrl.to(device)
        qi_ema_c = self.qi_ema_c.to(device)

        qi_trend = qi_per_chakra - qi_ema_c

        breath_vec = torch.stack([
            breath['yang'].flatten(),
            breath['yin'].flatten(),
            breath['beat'].flatten(),
            breath['flow'].flatten(),
            breath['phase_diff'].flatten() / (2.0 * math.pi),
        ]).view(-1).to(device)

        Q_global = torch.stack([
            Q_mean, Q_max, Q_var,
            Q_high_frac, Q_low_frac, Q_sat_frac,
        ]).to(device)

        Q_transport = torch.stack([
            Q_transport_mean, Q_transport_max, Q_transport_clip,
        ]).to(device)

        x = torch.cat([
            qi_per_chakra,
            qi_trend,
            breath_vec,
            Q_global,
            Q_transport,
            harmony_weights,
            psi_sat_frac.unsqueeze(0),
            field_ratio.unsqueeze(0),
            h_ctrl,
        ], dim=0)

        h = self.legacy_input_proj(x)
        h = self.legacy_hidden_proj(h) + h_ctrl

        intero = 0.005 * torch.tanh((field_ratio - PHI_INV**2) / PHI_INV)
        h = h + intero.detach()

        with torch.no_grad():
            self.h_ctrl.copy_(
                self.ctrl_ema_decay * h_ctrl +
                (1.0 - self.ctrl_ema_decay) * h.detach()
            )

        yang = breath['yang'].flatten()[0]
        carrier = 1.0 + 0.5 * yang

        raw_alpha = torch.tanh(self.head_alpha_legacy(h)) * 0.6
        raw_mu    = torch.tanh(self.head_mu_legacy(h))
        raw_zeta  = torch.tanh(self.head_zeta_legacy(h)) * 0.75
        raw_gamma = torch.tanh(self.head_gamma_legacy(h)) * 0.99

        alpha_val = 1.0 + raw_alpha * carrier
        mu_c      = raw_mu * carrier
        zeta_c    = 1.0 + raw_zeta * carrier
        gamma_val = 1.0 + raw_gamma * carrier

        alpha_val = alpha_val.clamp(0.15, 2.5).squeeze(0)
        mu_c      = mu_c.clamp(-1.0, 1.0)
        zeta_c    = zeta_c.clamp(0.5, 2.0)
        gamma_val = gamma_val.clamp(0.8, 1.2).squeeze(0)

        with torch.no_grad():
            self.qi_ema_c.copy_(0.9 * qi_ema_c + 0.1 * qi_per_chakra)
            self.prev_outputs.copy_(torch.cat([
                alpha_val.detach().flatten(),
                mu_c.detach(),
                zeta_c.detach(),
                gamma_val.detach().flatten(),
            ]))

        diagnostics = {
            'ctrl_alpha': alpha_val.item(),
            'ctrl_mu_mean': mu_c.mean().item(),
            'ctrl_mu_std': mu_c.std().item(),
            'ctrl_zeta_mean': zeta_c.mean().item(),
            'ctrl_gamma': gamma_val.item(),
            'ctrl_carrier': carrier.item(),
            'ctrl_h_norm': h.norm().item(),
        }

        # Return new CtrlOutputs; legacy fields are available as properties.
        return CtrlOutputs(
            alpha=alpha_val,
            gamma=gamma_val,
            rho=torch.ones_like(alpha_val),
            perturb=torch.zeros_like(alpha_val),
            m_self=torch.ones_like(alpha_val),
            diagnostics=diagnostics,
        )

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

    # ═══════════════════ Legacy loss helpers ═══════════════════

    def _homeostasis_loss(self, Q_mean: torch.Tensor) -> torch.Tensor:
        """Prevent Qi from vanishing (< qi_target_low) or exploding (> qi_target_high)."""
        low_violation = F.relu(self.qi_target_low - Q_mean)
        high_violation = F.relu(Q_mean - self.qi_target_high)
        return low_violation.pow(2) + high_violation.pow(2)

    def _chakra_balance_loss(self, qi_per_chakra: torch.Tensor) -> torch.Tensor:
        """Prevent any single chakra from dominating Qi."""
        q = qi_per_chakra + 1e-8
        q_norm = q / q.sum()
        target = 1.0 / self.C
        return (q_norm - target).pow(2).mean()

    def _step_smoothness(self, ctrl: CtrlOutputs, prev_ctrl: CtrlOutputs) -> torch.Tensor:
        """Per-step smoothness loss — keep as tensor for gradient flow."""
        return (
            (ctrl.alpha - prev_ctrl.alpha).pow(2) +
            (ctrl.gamma - prev_ctrl.gamma).pow(2) +
            (ctrl.rho - prev_ctrl.rho).pow(2) +
            (ctrl.m_self - prev_ctrl.m_self).pow(2) +
            (ctrl.perturb - prev_ctrl.perturb).pow(2)
        ) / 5.0

    def _breath_gating_loss(self, ctrl: CtrlOutputs, yang: torch.Tensor) -> torch.Tensor:
        """Penalize global actuators when they deviate from center while breath is neutral."""
        breath_weight = 1.0 - yang.abs()  # [B] or scalar
        return (
            (ctrl.alpha - 1.0).pow(2).mean() * breath_weight.mean() +
            (ctrl.gamma - 1.0).pow(2).mean() * breath_weight.mean() +
            (ctrl.m_self - 1.0).pow(2).mean() * breath_weight.mean()
        ) / 3.0

    def _center_loss(self, ctrl: CtrlOutputs) -> torch.Tensor:
        """Very weak L2 anchor: actuators should stay near natural centers."""
        return (
            (ctrl.alpha - 1.0).pow(2).mean() +
            (ctrl.gamma - 1.0).pow(2).mean() +
            (ctrl.rho - 1.0).pow(2).mean() +
            (ctrl.m_self - 1.0).pow(2).mean() +
            ctrl.perturb.pow(2).mean()
        ) / 5.0

    def aux_loss(self,
                 Q_mean: torch.Tensor,
                 qi_per_chakra: torch.Tensor,
                 smoothness_acc: torch.Tensor = 0.0,
                 yang_mag: torch.Tensor = 0.0,
                 latest_ctrl: CtrlOutputs = None,
                 weights: Dict[str, float] = None) -> torch.Tensor:
        """Combined auxiliary loss with configurable weights."""
        if weights is None:
            weights = {}
        device = Q_mean.device
        smoothness_acc_t = torch.as_tensor(smoothness_acc, device=device)
        L = torch.tensor(0.0, device=device)
        L = L + weights.get('homeo', 0.0) * self._homeostasis_loss(Q_mean)
        L = L + weights.get('balance', 0.0) * self._chakra_balance_loss(qi_per_chakra)
        L = L + weights.get('smooth', 0.0) * smoothness_acc_t
        if latest_ctrl is not None:
            yang_t = torch.as_tensor(yang_mag, device=device)
            L = L + weights.get('breath_gating', 0.0) * self._breath_gating_loss(latest_ctrl, yang_t)
            L = L + weights.get('center', 0.0) * self._center_loss(latest_ctrl)
        return L

    def reset_state(self):
        """Clear all persistent controller state."""
        with torch.no_grad():
            self.h_ctrl.zero_()
            self.qi_ema_c.zero_()
            self.prev_outputs.zero_()
