"""RecurrentDiffusionBrain — proper brainstem feedback loop around DiffusionCord.

Uses the REAL Brainstem and BrainField with full stateful mechanics:
Breath, Qi cycle, chakra attention, homeostasis, focus/regulation EMAs,
pulse detection — all active. At each DDIM step, the brainstem reads 
the spine's state and feeds modulatory signals back to the next step.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV
from cassi.diffusion_cord import DiffusionCord
from cassi.brainstem import Brainstem
from cassi.brain_field import BrainField


class SpineDiffusionCord(DiffusionCord):
    """DiffusionCord with Brainstem-compatible persistent state.

    Adds field_state, yang, yin, qi_fluid, field_energy buffers
    and exposes _offsets as contiguous (start, end) tuples for
    brainstem.step() compatibility. Internal chakra processing
    uses _strided_indices for the strided allocation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Persist strided indices internally
        self._strided_indices = self._offsets  # list of index lists

        # Expose contiguous offsets for brainstem compatibility
        # (brainstem.step() does for c: start,end = spine._offsets[c])
        self._offsets = []
        offset = 0
        for w in self.widths:
            self._offsets.append((offset, offset + w))
            offset += w

        # Brainstem-readable state
        self.register_buffer('field_state', torch.zeros(1, self.D))
        self.register_buffer('yang', torch.zeros(1, self.D))
        self.register_buffer('yin', torch.zeros(1, self.D))
        self.register_buffer('qi_fluid', torch.zeros(1, self.D))
        self.register_buffer('field_energy', torch.zeros(1, self.C))

        # Modulation accumulators
        self._mod_theta_shift = 0.0
        self._mod_damp_scale = 1.0
        self._mod_yang_gain = 1.0
        self._mod_yin_gain = 1.0

    def _split_chakras(self, x):
        """Override: use strided indices for chakra processing."""
        parts = []
        for c in range(self.C):
            indices = self._strided_indices[c]
            g = torch.sigmoid(self.chakra_gain[c]) * 2.0
            parts.append(x[:, indices] * g)
        return parts

    def reset_state(self, batch_size):
        def _ensure(buf, shape):
            if buf.shape[0] != shape[0]:
                return torch.zeros(*shape, device=buf.device, dtype=buf.dtype)
            buf.zero_()
            return buf
        self.field_state = _ensure(self.field_state, (batch_size, self.D))
        self.yang = _ensure(self.yang, (batch_size, self.D))
        self.yin = _ensure(self.yin, (batch_size, self.D))
        self.qi_fluid = _ensure(self.qi_fluid, (batch_size, self.D))
        self.field_energy = _ensure(self.field_energy, (batch_size, self.C))
        self._mod_theta_shift = 0.0
        self._mod_damp_scale = 1.0
        self._mod_yang_gain = 1.0
        self._mod_yin_gain = 1.0

    def apply_brainstem_modulation(self, stem_info):
        self._mod_theta_shift = stem_info.get('theta_shift', 0.0)
        self._mod_damp_scale = stem_info.get('damp_scale', 1.0)
        self._mod_yang_gain = stem_info.get('yang_gain', 1.0)
        self._mod_yin_gain = stem_info.get('yin_gain', 1.0)

    def forward(self, x_t, t):
        """Denoise with brainstem modulation injected into chakras."""
        t_emb = self.time_emb(t)
        t_mod = self.time_modulation(t_emb)

        x_parts = self._split_chakras(x_t)

        chakra_outs = []
        for c in range(self.C):
            field_c = self._chakra_transform_modulated(
                x_parts[c], t_mod, c,
                self._mod_theta_shift,
                self._mod_damp_scale,
                self._mod_yang_gain,
                self._mod_yin_gain,
            )
            chakra_outs.append(field_c)

        # Scatter back using strided indices
        all_f = torch.zeros_like(x_t)
        for c in range(self.C):
            all_f[:, self._strided_indices[c]] = chakra_outs[c]

        x0_pred = self.fusion(torch.cat([x_t, all_f * 0.5], dim=-1)) + x_t

        # Update brainstem-readable state
        self.field_state = x0_pred.detach()
        for c in range(self.C):
            self.field_energy[:, c] = chakra_outs[c].norm(dim=-1).detach()

        return x0_pred

    def _chakra_transform_modulated(self, x_c, t_mod, c,
                                     theta_shift, damp_scale,
                                     yang_gain, yin_gain):
        """Chakra transform with brainstem modulation on top of timestep."""
        gain_scale = t_mod[:, c * 3 + 0].unsqueeze(-1)
        t_theta = t_mod[:, c * 3 + 1].unsqueeze(-1)
        t_damp = t_mod[:, c * 3 + 2].unsqueeze(-1)

        theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
        theta = theta + 0.5 * torch.tanh(t_theta) * math.pi
        theta = theta + 0.3 * theta_shift * math.pi
        theta = theta.clamp(0.001, math.pi - 0.001)

        d = PHI_INV * torch.sigmoid(t_damp) * damp_scale
        d = d.clamp(0.05, 1.0)

        b0 = torch.sigmoid(self.fwd_b0[c]) * yang_gain
        b1 = torch.sigmoid(self.fwd_b1[c]) * yin_gain
        sf = b0 + b1 + 1e-8
        b0, b1 = b0 / sf, b1 / sf
        gm = torch.sigmoid(gain_scale) * 2.0
        b0, b1 = b0 * gm, b1 * gm

        denom = 1.0 - 2.0 * d * torch.cos(theta) + d ** 2
        ng = torch.rsqrt(denom + 1e-8)
        sg = (b0 + b1) * ng
        sg = torch.tanh(sg) * 2.0

        resonant = x_c * sg
        refined = self.chakra_proj_down[c](x_c)
        refined = F.gelu(refined)
        refined = self.chakra_proj_up[c](refined)
        return resonant + refined


class RecurrentDiffusionBrain(nn.Module):
    """Three-tier diffusion with real Brainstem feedback loop.

    At each DDIM step:
      1. Spine denoises with modulation from previous brainstem step
      2. Brainstem reads spine state, computes new modulation
      3. Brainfield updates (throttled) from compressed representation
      4. Modulation feeds back to next step
    """

    def __init__(self, D=1040, D_stem=None, D_brain=None, K=2):
        super().__init__()
        self.D = D
        self.D_stem = D_stem if D_stem is not None else int(D / PHI)
        self.D_brain = D_brain if D_brain is not None else int(self.D_stem * PHI)
        self.K = K
        self._step_counter = 0

        self.spine = SpineDiffusionCord(D=D)
        self.brainstem = Brainstem(D=D, D_stem=self.D_stem)
        self.brain_field = BrainField(D_stem=self.D_stem, D_brain=self.D_brain, K=K)

    def reset_state(self, B):
        self.spine.reset_state(B)
        self.brainstem.reset_state(B)
        self.brain_field.reset_state(B)
        self._step_counter = 0

    def forward(self, x_t, t, step_idx=0):
        B = x_t.shape[0]

        # 1. Spine denoises with brainstem modulation from previous step
        x0_pred = self.spine(x_t, t)

        # 2. Brainstem reads spine state, computes modulation for NEXT step
        stem_info = self.brainstem.step(self.spine)
        self.spine.apply_brainstem_modulation(stem_info)

        # 3. BrainField update (throttled)
        brain_state = self.brain_field.maybe_step(stem_info['compressed'])

        # 4. Integrate brainfield into spine's qi_fluid (slow cognitive bias)
        if brain_state is not None and self._step_counter % (self.K * 2) == 0:
            brain_energy = brain_state.norm(dim=-1, keepdim=True)
            self.spine.qi_fluid = (
                PHI_INV * self.spine.qi_fluid +
                PHI_INV ** 2 * brain_energy * 0.01
            ).detach()

        self._step_counter += 1
        return x0_pred

    def training_loss(self, x_0, t=None):
        B = x_0.shape[0]
        if t is None:
            t = torch.randint(0, self.spine.num_timesteps, (B,), device=x_0.device)
        noise = torch.randn_like(x_0)
        x_t, _ = self.spine.q_sample(x_0, t, noise=noise)
        x0_pred = self.forward(x_t, t, step_idx=0)
        return F.mse_loss(x0_pred, x_0)


def demo():
    print("=" * 60)
    print("RecurrentDiffusionBrain — active brainstem feedback")
    print("=" * 60)
    D = 1040
    model = RecurrentDiffusionBrain(D=D, K=2)
    print(f"D={model.D}, D_stem={model.D_stem}, D_brain={model.D_brain}")
    print(f"Params: {sum(p.numel() for p in model.parameters()):,}")

    B = 4
    model.reset_state(B)
    x_t = torch.randn(B, D)
    steps = model.spine._subsample_steps(50)

    norms = []
    for i, t_idx in enumerate(steps):
        t = torch.full((B,), t_idx, dtype=torch.long)
        t_prev = steps[i + 1] if i + 1 < len(steps) else -1

        x0 = model(x_t, t, step_idx=i)

        if t_prev >= 0:
            ac = model.spine.alphas_cumprod[t_idx]
            ap = model.spine.alphas_cumprod[t_prev]
            eps = (x_t - torch.sqrt(ac) * x0) / torch.sqrt(1.0 - ac + 1e-8)
            x_t = torch.sqrt(ap) * x0 + torch.sqrt(1.0 - ap + 1e-8) * eps
        else:
            x_t = x0
        norms.append(x_t.norm(dim=-1).mean().item())

    print(f"DDIM: start={norms[0]:.1f} end={norms[-1]:.1f} min={min(norms):.1f}")
    assert not torch.isnan(x_t).any(), "NaN!"
    print("No NaN ✓")

    loss = model.training_loss(torch.randn(4, D))
    loss.backward()
    print(f"Loss={loss.item():.4f}, gradients OK ✓")
    print("Ready for training.")


if __name__ == '__main__':
    demo()
