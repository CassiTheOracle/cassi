#!/usr/bin/env python3
"""MindBrainField -- Bidirectional QiField (mind) + Spine3D (brain) loop, coupled
through a CordBus bottleneck (the cord IS the conduit, per formalism section 10.1).

Architecture:
    1. Mind runs K_train cycles of: field_step -> CordBus.ascend ->
       Spine3D.receive_bus -> CordBus.descend -> coupling * descend added to psi.
    2. Qi Q = |psi|^2 * |eps|^2 emerges from the prediction gap -- never injected.
    3. Controller runs internally (K_train times in field_step) and externally
       once after the loop (for balance_loss + final field regulation).
    4. One settling field_step -> readout.

Signals:
    Mind -> Brain: bus = cord.ascend(psi_real) [per-position, [B, N, cord_width]]
    Brain -> Mind: psi += sigmoid(coupling_strength) * cord.descend(brain_out['bus_response'])

No ad-hoc projections: the bus IS the conduit.
"""
import math
from contextlib import nullcontext
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.qi_field import QiField
from cassi.spine3d import Spine3D
from cassi.cord import PHI, PHI_INV
from cassi._field_modules.cord_bus import CordBus


class MindBrainField(nn.Module):
    """QiField (mind) + Spine3D (brain) with bidirectional coupling.

    Args:
        N: spatial positions (sequence length).
        d: field dimension per position (mind).
        C: chakras (fixed at 13).
        V: vocabulary size (256 for bytes).
        K_train: refinement steps during training.
        K_gen: refinement steps during generation.
        n_shells: number of brain shells (default 7).
        D_spine: total brain dimensions across shells (default 588).
        lambda_recon: reconstruction auxiliary loss weight (default 0.1).
        use_bf16: cast mind field to bf16 with autocast for ~1.5x speedup (default True).
        cord_width: bottleneck width between mind and brain (default d // 4).
        ctrl_hidden_dim: controller MLP hidden dimension (default 64).
        ctrl_loss_weight: controller loss weight (default 0.01).
        lambda_homeo: homeostasis regularizer weight (default 0.001).
        lambda_balance: balance regularizer weight for controller actuators
            (default 0.01). Anchors alpha/gamma/rho near 1.0 to prevent the
            controller from collapsing brain energy. Set 0 to disable.
        lambda_be: brain energy regularizer weight (default 0.1). Prevents
            the optimizer from collapsing brain weights to zero when the
            gate is mostly closed (low absolute energy).
        target_be: target mean brain energy for the regularizer (default 0.05).
            Calibrated to epoch-0 shell-0 energy of 0.058.
        max_batch_size: maximum batch size for persistent buffers (default 256).
        **qi_kwargs: additional kwargs passed to QiField.
    """

    def __init__(self, N: int = 128, d: int = 128, C: int = 13, V: int = 256,
                 K_train: int = 10, K_gen: int = 50,
                 n_shells: int = 7, D_spine: int = 588, nw: int = 96,
                 lambda_recon: float = 0.1,
                use_bf16: bool = True,
                cord_width: Optional[int] = None,
                 ctrl_hidden_dim: int = 64, ctrl_loss_weight: float = 0.01,
                 lambda_homeo: float = 0.001, lambda_balance: float = 0.01,
                 lambda_be: float = 0.1, target_be: float = 0.05,
                 max_batch_size: int = 256,
                 **qi_kwargs):
        super().__init__()

        # Remove kwargs that would conflict
        qi_kwargs.pop('lambda_recon', None)

        # ── Cord conduit ──
        self.cord_width = cord_width if cord_width is not None else d // 4
        self.cord = CordBus(d=d, cord_width=self.cord_width, N=N)
        self.coupling_strength = nn.Parameter(torch.tensor(-2.2))  # sigmoid -> 0.1

        # ── Components ──
        self.mind = QiField(
            N=N, d=d, C=C, V=V,
            K_train=K_train, K_gen=K_gen,
            ctrl_hidden_dim=ctrl_hidden_dim,
            ctrl_loss_weight=ctrl_loss_weight,
            lambda_homeo=lambda_homeo,
            max_batch_size=max_batch_size,
            **qi_kwargs,
        )
        self.brain = Spine3D(n_shells=n_shells, input_dim=nw, D=D_spine, cord_width=self.cord_width)
        # Off for text: cos-based interference needs 3D spatial data.
        self.brain.use_interference = False

        # --- Expose constants for training-script compatibility ---
        self.C = C
        self.use_bf16 = use_bf16
        self.d = d
        self.V = V
        self.K_train = K_train
        self.K_gen = K_gen
        self.lambda_recon = lambda_recon
        self.lambda_balance = lambda_balance
        self.lambda_be = lambda_be
        self.target_be = target_be

    @property
    def transceivers(self):
        return self.mind.transceivers

    @property
    def residuals(self):
        return self.mind.residuals

    @property
    def controller(self):
        return self.mind.controller

    @property
    def breath(self):
        return self.mind.breath

    @property
    def pattern_memory(self):
        return self.mind.pattern_memory

    # ═══════════════════ Stage methods (training_loss decomposition) ═══════════════════

    def _setup_state(self, x: torch.Tensor, state_indices, no_reset: bool) -> None:
        """Set up transceiver state for the current batch."""
        B, N = x.shape
        dev = x.device
        if state_indices is not None:
            if self.mind.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            for t in self.mind.transceivers:
                if t.h_real.shape[0] != B:
                    t.reset_state(B, dev)
        elif not no_reset:
            self.reset_state()
            for t in self.mind.transceivers:
                t.reset_state(B, dev)
        else:
            for t in self.mind.transceivers:
                if t.h_real.shape[0] != B:
                    t.h_real = t.h_real[:1].expand(B, -1).clone()
                    t.h_imag = t.h_imag[:1].expand(B, -1).clone()
                    t.h_prev_real = t.h_prev_real[:1].expand(B, -1).clone()
                    t.h_prev_imag = t.h_prev_imag[:1].expand(B, -1).clone()
                    t.x_prev_real = t.x_prev_real[:1].expand(B, -1).clone()
                    t.x_prev_imag = t.x_prev_imag[:1].expand(B, -1).clone()


    def reset_state(self) -> None:
        """Reset persistent state between sequences.

        Resets mind ψ/transceivers/controller/breath/pattern memory via
        QiField.reset_state. The Brain (Spine3D) has no IIR state to reset.
        The Breath oscillator IS reset (phase → 0); the next forward call
        re-derives breath/heartbeat_seq from the fresh phase via
        `breath_module=self.mind.breath`. The shared breath module is what
        keeps the brain's heart in sync with the mind's across the loop.
        The CordBus persistent biquad state is also reset.
        """
        self.mind.reset_state()
        self.cord.reset_state()

    def load_state_dict(self, state_dict, strict=False, assign=False):
        """Load state dict, normalizing mind sub-module transceiver buffer shapes.

        Transceiver buffers (h_real, h_imag, etc.) have batch-dependent shapes.
        Delegates to QiField._normalize_state_dict for the `mind.*` keys before
        calling the default loader with strict=False.
        """
        # Normalize mind sub-module keys for transceiver buffer shapes.
        if any(k.startswith('mind.') for k in state_dict):
            mind_keys = {k[len('mind.'):]: v for k, v in state_dict.items() if k.startswith('mind.')}
            mind_keys = self.mind._normalize_state_dict(mind_keys)
            for k, v in mind_keys.items():
                state_dict['mind.' + k] = v
        return super().load_state_dict(state_dict, strict=strict, assign=assign)

    def training_loss(self, x: torch.Tensor,
                      state_indices=None,
                      no_reset: bool = True):
        B, N = x.shape
        dev = x.device

        # --- 1. State setup ---
        self._setup_state(x, state_indices, no_reset)

        # --- 2. Context/target split ---
        context_len = max(1, N - self.mind.span_len)
        if self.mind.span_len >= N:
            context_len = N // 2
        context = x[:, :context_len]
        target = x[:, context_len:]
        if context.shape[1] < N:
            pad = torch.zeros(B, N - context_len, dtype=torch.long, device=dev)
            context = torch.cat([context, pad], dim=1)

        # --- 3. Embed ---
        psi_real, psi_imag = self.mind.embed(context)  # [B, N, d]

        # --- 4. Coupled mind<->brain loop (K_train cycles) ---
        if self.use_bf16 and dev.type == 'cuda':
            psi_real = psi_real.bfloat16()
            psi_imag = psi_imag.bfloat16()
            Q_field = self.mind.Q_field.expand(B, -1, -1).clone().bfloat16()
        else:
            Q_field = self.mind.Q_field.expand(B, -1, -1).clone()

        amp_ctx = (torch.autocast('cuda', dtype=torch.bfloat16)
                   if self.use_bf16 and dev.type == 'cuda' else nullcontext())

        all_diag: Dict = {}
        ctrl_losses: list = []
        last_pm_diag: Dict = {}
        last_bus = None
        last_brain_out = None

        with amp_ctx:
            for k in range(self.mind.K_train):
                breath = self.mind.breath.step()
                psi_real, psi_imag, Q_field, diag = self.mind.field_step(
                    psi_real, psi_imag, Q_field, breath,
                    state_indices=state_indices)

                # Mind -> bus (ascend commits state)
                bus = self.cord.ascend(psi_real.float())  # ascend in fp32 for stability
                last_bus = bus
                # Bus -> brain (one forward per cycle -- this is the conduit)
                brain_out = self.brain.receive_bus(bus, breath_module=self.mind.breath)
                last_brain_out = brain_out
                # Brain -> mind perturbation (descend does NOT commit state)
                descend_signal = self.cord.descend(brain_out['bus_response'])
                # Learned additive coupling (sigmoid -> [0, 1])
                coupling = torch.sigmoid(self.coupling_strength)
                psi_real = psi_real + coupling * descend_signal.to(psi_real.dtype)
                psi_imag = psi_imag + coupling * descend_signal.to(psi_imag.dtype)

                for key, val in diag.items():
                    if isinstance(val, torch.Tensor) and val.numel() > 1:
                        all_diag[key] = val
                    else:
                        all_diag[key] = all_diag.get(key, 0.0) + val
                last_pm_diag = {k: v for k, v in diag.items() if k.startswith('pm_')}
                if self.mind.controller is not None and self.mind.lambda_homeo > 0:
                    ctrl_losses.append(self.mind.controller.compute_homeo_loss(
                        diag['Q_mean'], weight=self.mind.lambda_homeo))

        psi_real = psi_real.float()
        psi_imag = psi_imag.float()
        Q_field = Q_field.float()

        # --- 5. External controller call (for balance_loss + final field regulation) ---
        if self.mind.controller is not None:
            with torch.set_grad_enabled(self.training):
                qi_per_chakra = self.mind._qi_per_chakra(Q_field)
                q_trend = self.mind.Q_trend.expand(B).to(dev)
                yz_ratio = self.mind._yang_yin_ratio(psi_real, psi_imag)
                field_energy = self.mind._complex_norm2(psi_real, psi_imag).mean(dim=(1, 2))
                ctrl_breath = self.mind.breath.step()
                ctrl_out = self.mind.controller(
                    qi_per_chakra,
                    q_trend=q_trend,
                    y_over_z_ratio=yz_ratio,
                    field_energy=field_energy,
                    breath=ctrl_breath,
                )
                ctrl_alpha_t = ctrl_out.alpha.mean().detach()
                ctrl_gamma_t = ctrl_out.gamma.mean().detach()
                ctrl_rho_t = ctrl_out.rho.mean().detach()
                ctrl_alpha = ctrl_alpha_t.item()
                ctrl_gamma = ctrl_gamma_t.item()
                ctrl_rho = ctrl_rho_t.item()
                balance_loss_t = self.mind.controller.compute_balance_loss(
                    ctrl_out, weight=self.lambda_balance) if self.lambda_balance > 0 \
                    else torch.tensor(0.0, device=dev)
        else:
            ctrl_alpha_t = torch.tensor(1.0, device=dev)
            ctrl_gamma_t = torch.tensor(1.0, device=dev)
            ctrl_rho_t = torch.tensor(1.0, device=dev)
            ctrl_alpha = 1.0
            ctrl_gamma = 1.0
            ctrl_rho = 1.0
            balance_loss_t = torch.tensor(0.0, device=dev)

        all_diag['balance_loss'] = balance_loss_t.item()
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if (isinstance(val, (int, float))
                    or (isinstance(val, torch.Tensor) and val.numel() == 1)):
                all_diag[key] = val / self.mind.K_train
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        # --- 6. Settling field_step + readout ---
        with amp_ctx:
            breath = self.mind.breath.step()
            psi_real, psi_imag, Q_field, settle_diag = self.mind.field_step(
                psi_real.bfloat16(), psi_imag.bfloat16(), Q_field.bfloat16(), breath,
                state_indices=state_indices)
            logits = self.mind.readout_positions(psi_real, psi_imag)

        logits = logits.float()

        # --- 7. CE loss ---
        ce_loss = F.cross_entropy(
            logits[:, context_len:, :].reshape(-1, self.V),
            target.reshape(-1))

        # --- 8. Reconstruction auxiliary loss (bus signal as recon target) ---
        # The brain tries to reconstruct the bus signal it received. This is the
        # "P[psi] compressed to the conduit" from section 10.1 of the formalism.
        bus_input_proj = self.brain.bus_to_input(last_bus)  # [B, N, input_dim]
        recon_loss = F.mse_loss(
            last_brain_out['psi_recon'], bus_input_proj.reshape(B * N, -1))

        # --- 9. Composite loss (CE + recon + pattern + balance + be_reg + homeo) ---
        pattern_div_loss = torch.tensor(0.0, device=dev)
        pattern_commit_loss = torch.tensor(0.0, device=dev)
        pattern_util_loss = torch.tensor(0.0, device=dev)
        if last_pm_diag:
            entropy = last_pm_diag.get('pm_usage_entropy', 0.0)
            if isinstance(entropy, (int, float)):
                entropy = torch.tensor(float(entropy), device=dev)
            pattern_div_loss = -entropy
            commit = last_pm_diag.get('pm_commit_loss', 0.0)
            if isinstance(commit, (int, float)):
                commit = torch.tensor(float(commit), device=dev)
            pattern_commit_loss = commit
            born_ratio = last_pm_diag.get('pm_born_ratio', 0.0)
            if isinstance(born_ratio, (int, float)):
                born_ratio = torch.tensor(float(born_ratio), device=dev)
            pattern_util_loss = (born_ratio - 0.5).pow(2)

        loss = ce_loss \
            + self.lambda_recon * recon_loss \
            + self.mind.lambda_pattern_div * pattern_div_loss \
            + self.mind.lambda_pattern_commit * pattern_commit_loss \
            + self.mind.lambda_pattern_util * pattern_util_loss \
            + balance_loss_t

        # Brain energy regularizer (keeps brain weights from collapsing)
        be_mean = last_brain_out['qi_energy'].mean()
        be_reg = (self.target_be - be_mean).clamp(min=0) ** 2 * self.lambda_be
        loss = loss + be_reg
        all_diag['be_reg'] = be_reg.item()

        if ctrl_losses:
            homeo_loss = torch.stack(ctrl_losses).mean()
            loss = loss + homeo_loss
            all_diag['homeo_loss'] = homeo_loss.item()

        all_diag['ce_loss'] = ce_loss.item()
        all_diag['recon_loss'] = recon_loss.item()
        all_diag['loss'] = loss.item()

        # --- 10. Diagnostics ---
        q_mean_val = all_diag.get('Q_mean', Q_field.mean().item())
        if isinstance(q_mean_val, torch.Tensor):
            q_mean_val = q_mean_val.mean().item()

        brain_energy_shell = last_brain_out['qi_energy'].mean(dim=(0, 1))
        qi_per_chakra = self.mind._qi_per_chakra(Q_field)

        all_diag['Q_mean'] = q_mean_val
        all_diag['Q_max'] = all_diag.get('Q_max', Q_field.max().item())
        all_diag['brain_energy'] = brain_energy_shell.detach().cpu()
        all_diag['brain_energy_mean'] = last_brain_out['qi_energy'].mean().item()
        all_diag['cord_coupling'] = coupling.item()
        all_diag['qi_per_chakra'] = qi_per_chakra.mean(dim=0)
        all_diag['ctrl_alpha'] = ctrl_alpha
        all_diag['ctrl_gamma'] = ctrl_gamma
        all_diag['ctrl_rho'] = ctrl_rho
        all_diag['ctrl_aux_loss'] = all_diag.get('homeo_loss', 0.0) + all_diag['balance_loss']

        return loss, all_diag

    def forward(self, x: torch.Tensor,
                state_indices: Optional[torch.Tensor] = None,
                no_reset: bool = True) -> torch.Tensor:
        """Inference forward: brain-perturbed mind field -> pooled logits."""
        B = x.shape[0]
        dev = x.device

        self._setup_state(x, state_indices, no_reset)

        psi_real, psi_imag = self.mind.embed(x)
        Q_field = self.mind.Q_field.expand(B, -1, -1).clone()

        for _ in range(self.mind.K_train):
            breath = self.mind.breath.step()
            psi_real, psi_imag, Q_field, _diag = self.mind.field_step(
                psi_real, psi_imag, Q_field, breath,
                state_indices=state_indices)
            bus = self.cord.ascend(psi_real)
            brain_out = self.brain.receive_bus(bus, breath_module=self.mind.breath)
            descend_signal = self.cord.descend(brain_out['bus_response'])
            coupling = torch.sigmoid(self.coupling_strength)
            psi_real = psi_real + coupling * descend_signal
            psi_imag = psi_imag + coupling * descend_signal

        logits = self.mind.readout(psi_real, psi_imag)
        return logits

    @torch.no_grad()
    def generate(self, seq_len: int = 128, temp: float = 0.8,
                 K: Optional[int] = None,
                 device: Optional[torch.device] = None) -> torch.Tensor:
        """Generate a byte sequence from the mind's learned dynamics.

        The brain is not involved in standalone generation (per prototype).
        Delegates to QiField.generate().
        """
        return self.mind.generate(seq_len=seq_len, temp=temp, K=K, device=device)

    @staticmethod
    def qi_state(qi_per_chakra: Optional[torch.Tensor] = None) -> str:
        """Diagnostic: mean Qi and balanced chakra count."""
        C = qi_per_chakra.shape[-1] if qi_per_chakra is not None else 13
        if qi_per_chakra is not None:
            mean_q = qi_per_chakra.mean().item()
            balanced = int((qi_per_chakra > 0.01).sum().item())
        else:
            mean_q = 0.0
            balanced = 0
        return f"Q_mean={mean_q:.3f} balanced={balanced}/{C}"


# ═══════════════════ Smoke test ═══════════════════

if __name__ == '__main__':
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    torch.manual_seed(42)

    m = MindBrainField(N=8, d=64, K_train=3, n_shells=7, D_spine=128, nw=32)
    x = torch.randint(0, 256, (2, 8))
    loss, info = m.training_loss(x)
    assert torch.isfinite(loss), f'non-finite loss: {loss}'
    loss.backward()
    for name, p in m.named_parameters():
        if p.grad is not None:
            assert torch.isfinite(p.grad).all(), f'non-finite grad in {name}'

    # Generation smoke test
    tokens = m.generate(seq_len=16, temp=0.8)
    assert tokens.shape[0] == 16

    print('MindBrainField smoke tests passed.')
    print(f'  loss={loss.item():.4f}  ce={info["ce_loss"]:.4f}  recon={info["recon_loss"]:.4f}')
    print(f'  Q_mean={info["Q_mean"]:.4f}  coupling={info["cord_coupling"]:.4f}')
    print(f'  brain_energy={info["brain_energy"]}')
    print(f'  ctrl: alpha={info["ctrl_alpha"]:.3f} gamma={info["ctrl_gamma"]:.3f} rho={info["ctrl_rho"]:.3f}')
