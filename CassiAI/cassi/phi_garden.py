"""φ-Garden Brain: Conscious Harmonic Workspace Architecture.

A unified physics-cognition system combining:
  - Twin-Cord structure: External Cord A (spine) + 5 internal specialists
  - GWT broadcasting: φ-temperature softmax competition for workspace access
  - Berry + boundary memory: 39-dim topological keys for associative retrieval
  - Dual workspace FWD/REV: conscious content = workspace_fwd - workspace_rev
  - Meta-cord: inner voice observing workspace history
  - Fatigue: per-specialist energy buffer for natural attention oscillation

Usage:
    garden = PhiGardenBrain(spine_checkpoint='cord_phi_chakras.pt')
    pred = garden(x)  # x: [B, 4, 1024]
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from cassi.cord import CordPhysics, PHI, PHI_INV
from cassi.berry_brain import BerryMemory, compute_berry_phases


class SlimSpecialist(nn.Module):
    """A specialist with only IIR parameters.

    Shares widths, chakra_gain, and fusion with the spine.
    Owns only: fwd_theta, rev_theta, fwd_b0/b1, rev_b0/b1.
    Parameter count: 78 scalars.
    """

    def __init__(self, widths, frequency_offset=0.0):
        super().__init__()
        self.C = len(widths)
        self.widths = widths
        self.register_buffer('freq_offset', torch.tensor(frequency_offset))

        # Only IIR params — everything else is borrowed from spine
        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.rev_theta = nn.Parameter(torch.randn(self.C))
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))

    def init_from_spine(self, spine: CordPhysics):
        """Copy IIR params from spine, then apply frequency offset."""
        with torch.no_grad():
            self.fwd_theta.copy_(spine.fwd_theta.data + self.freq_offset.item())
            self.rev_theta.copy_(spine.rev_theta.data + self.freq_offset.item())
            self.fwd_b0.copy_(spine.fwd_b0.data)
            self.fwd_b1.copy_(spine.fwd_b1.data)
            self.rev_b0.copy_(spine.rev_b0.data)
            self.rev_b1.copy_(spine.rev_b1.data)

    def compute_all_f(self, psi, chakra_gain):
        """Compute IIR outputs (all_f) for a field history.

        psi: [B, 4, D] — field history already in D-space
        chakra_gain: [C] — from spine
        Returns: all_f [B, D]
        """
        B = psi.shape[0]

        # Split into chakras with gains
        psi_c = []
        offset = 0
        for c in range(self.C):
            w = self.widths[c]
            g = torch.sigmoid(chakra_gain[c]) * 2.0
            psi_c.append(psi[:, :, offset:offset + w] * g)
            offset += w

        outs = []
        for c in range(self.C):
            ch = psi_c[c]  # [B, 4, W_c]

            # Forward IIR
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf

            h0 = ch[:, 0] * b0
            h1 = ch[:, 1] * b0 + ch[:, 0] * b1 + a1 * h0
            h  = ch[:, 2] * b0 + ch[:, 1] * b1 + a1 * h1 + a2 * h0
            h_fwd = ch[:, 3] * b0 + ch[:, 2] * b1 + a1 * h + a2 * h1

            # Reverse IIR
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            b0r, b1r = b0r / sr, b1r / sr

            ch_rev = torch.flip(ch, [1])
            h0r = ch_rev[:, 0] * b0r
            h1r = ch_rev[:, 1] * b0r + ch_rev[:, 0] * b1r + a1r * h0r
            hr  = ch_rev[:, 2] * b0r + ch_rev[:, 1] * b1r + a1r * h1r + a2r * h0r
            h_rev = ch_rev[:, 3] * b0r + ch_rev[:, 2] * b1r + a1r * hr + a2r * h1r

            outs.append(h_fwd - h_rev)

        return torch.cat(outs, -1)  # [B, D]


class PhiGardenBrain(nn.Module):
    """Conscious harmonic workspace brain.

    Components:
      - spine (CordPhysics): external physics cord, frozen in phase 1
      - specialists (list[SlimSpecialist]): 5 competing internal cords
      - meta_cord (SlimSpecialist): observes workspace history
      - workspace_fwd, workspace_rev: dual persistent workspace
      - berry_memory: topological associative memory
      - readout: D → 1024 residual predictor
    """

    def __init__(self, D=1040, n_specialists=5, n_slots=512,
                 memory_value_dim=26, readout_hidden=520, byte_mode=False):
        super().__init__()
        self.D = D
        self.n_specialists = n_specialists
        self.byte_mode = byte_mode

        # Spine — loaded from checkpoint, typically frozen
        self.spine = CordPhysics(D=D, byte_mode=byte_mode)

        # Specialists on φ-spiral frequency offsets
        # Offsets: (i - N//2) * φ^{-1/3}
        offset_scale = PHI ** (-1.0 / 3.0)
        self.specialists = nn.ModuleList([
            SlimSpecialist(self.spine.widths,
                          frequency_offset=(i - n_specialists // 2) * offset_scale)
            for i in range(n_specialists)
        ])

        # Meta-cord: observes workspace history
        self.meta_cord = SlimSpecialist(self.spine.widths, frequency_offset=0.0)

        # Dual workspace (persistent state, not parameters)
        self.register_buffer('workspace_fwd', torch.zeros(1, D))
        self.register_buffer('workspace_rev', torch.zeros(1, D))
        self.register_buffer('field_history', torch.zeros(1, 4, D))

        # Fatigue energy per specialist
        self.register_buffer('specialist_energy', torch.ones(n_specialists))

        # Berry memory: 39-dim key (26 Berry + 13 boundary residual)
        self.berry_memory = BerryMemory(
            D=D, n_slots=n_slots, key_dim=39, value_dim=memory_value_dim,
        )

        # Memory decompressor: 26 → 128 → D
        self.memory_decompressor = nn.Sequential(
            nn.Linear(memory_value_dim, 128),
            nn.ReLU(),
            nn.Linear(128, D),
        )

        # Readout: conscious workspace → residual prediction
        self.readout = nn.Sequential(
            nn.Linear(D, readout_hidden),
            nn.ReLU(),
            nn.Linear(readout_hidden, 1024),
        )

    def load_spine(self, checkpoint_path: str):
        """Load spine from checkpoint and initialize specialists from it."""
        state = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        # Checkpoint may be wrapped in dict with 'model' key
        if isinstance(state, dict) and 'model' in state:
            state = state['model']
        # Strip _orig_mod. prefix from torch.compile wrapped models
        if any(k.startswith('_orig_mod.') for k in state.keys()):
            state = {k.replace('_orig_mod.', ''): v for k, v in state.items()}
        # If checkpoint is a full model (keys prefixed with 'spine.'), extract spine weights
        spine_keys = [k for k in state.keys() if k.startswith('spine.')]
        if spine_keys:
            state = {k.replace('spine.', ''): v for k, v in state.items() if k.startswith('spine.')}
        # Load with strict=False to handle byte_encoder mismatch
        # (old checkpoints lack byte_encoder; new ones may have it)
        missing, unexpected = self.spine.load_state_dict(state, strict=False)
        if missing and not all(k.startswith('byte_encoder') for k in missing):
            print(f"[load_spine] Warning: unexpected missing keys: {missing}")
        if unexpected:
            print(f"[load_spine] Warning: unexpected keys: {unexpected}")

        # Init specialists as copies of spine with frequency offsets
        for spec in self.specialists:
            spec.init_from_spine(self.spine)
        self.meta_cord.init_from_spine(self.spine)

    def freeze_spine(self):
        """Freeze spine parameters."""
        for p in self.spine.parameters():
            p.requires_grad = False
        self._spine_frozen = True

    def unfreeze_spine(self):
        """Unfreeze spine parameters."""
        for p in self.spine.parameters():
            p.requires_grad = True
        self._spine_frozen = False

    def reset_workspace(self, batch_size=1, reset_energy=False):
        """Reset workspace state for a new episode.

        By default preserves specialist_energy so fatigue accumulates across
        training batches. Pass reset_energy=True to also reset fatigue.
        """
        self.workspace_fwd = torch.zeros(batch_size, self.D, device=self.workspace_fwd.device)
        self.workspace_rev = torch.zeros(batch_size, self.D, device=self.workspace_rev.device)
        self.field_history = torch.zeros(batch_size, 4, self.D, device=self.field_history.device)
        if reset_energy:
            self.specialist_energy = torch.ones(self.n_specialists, device=self.specialist_energy.device)

    def _compute_all_f_specialist_chunk(self, specialists_chunk, psi, chakra_gain):
        """Compute IIR outputs for a chunk of specialists in parallel.

        specialists_chunk: list of SlimSpecialist (length M ≤ N)
        psi: [B, 4, D] — field history in D-space
        chakra_gain: [C] — from spine
        Returns: all_f_chunk [M, B, D]
        """
        M = len(specialists_chunk)
        if M == 0:
            return torch.empty(0, psi.shape[0], self.D, device=psi.device)

        # Stack specialist parameters: [M, C]
        fwd_theta = torch.stack([s.fwd_theta for s in specialists_chunk], dim=0)
        rev_theta = torch.stack([s.rev_theta for s in specialists_chunk], dim=0)
        fwd_b0 = torch.stack([s.fwd_b0 for s in specialists_chunk], dim=0)
        fwd_b1 = torch.stack([s.fwd_b1 for s in specialists_chunk], dim=0)
        rev_b0 = torch.stack([s.rev_b0 for s in specialists_chunk], dim=0)
        rev_b1 = torch.stack([s.rev_b1 for s in specialists_chunk], dim=0)

        outs = []
        offset = 0
        for c in range(self.spine.C):
            w = self.spine.widths[c]
            g = torch.sigmoid(chakra_gain[c]) * 2.0
            ch = psi[:, :, offset:offset + w] * g  # [B, 4, w]
            offset += w

            # Forward IIR params for chunk: [M]
            theta = torch.sigmoid(fwd_theta[:, c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0_raw = torch.sigmoid(fwd_b0[:, c])
            b1_raw = torch.sigmoid(fwd_b1[:, c])
            sf = b0_raw + b1_raw + 1e-8
            b0 = b0_raw / sf
            b1 = b1_raw / sf

            # Batched IIR: [M, B, w]
            h0 = ch[:, 0, :].unsqueeze(0) * b0.view(M, 1, 1)
            h1 = (ch[:, 1, :].unsqueeze(0) * b0.view(M, 1, 1) +
                  ch[:, 0, :].unsqueeze(0) * b1.view(M, 1, 1) +
                  a1.view(M, 1, 1) * h0)
            h = (ch[:, 2, :].unsqueeze(0) * b0.view(M, 1, 1) +
                 ch[:, 1, :].unsqueeze(0) * b1.view(M, 1, 1) +
                 a1.view(M, 1, 1) * h1 +
                 a2 * h0)
            h_fwd = (ch[:, 3, :].unsqueeze(0) * b0.view(M, 1, 1) +
                     ch[:, 2, :].unsqueeze(0) * b1.view(M, 1, 1) +
                     a1.view(M, 1, 1) * h +
                     a2 * h1)

            # Reverse IIR params: [M]
            theta_r = torch.sigmoid(rev_theta[:, c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r_raw = torch.sigmoid(rev_b0[:, c])
            b1r_raw = torch.sigmoid(rev_b1[:, c])
            sfr = b0r_raw + b1r_raw + 1e-8
            b0r = b0r_raw / sfr
            b1r = b1r_raw / sfr

            ch_rev = torch.flip(ch, [1])  # [B, 4, w]
            h0r = ch_rev[:, 0, :].unsqueeze(0) * b0r.view(M, 1, 1)
            h1r = (ch_rev[:, 1, :].unsqueeze(0) * b0r.view(M, 1, 1) +
                   ch_rev[:, 0, :].unsqueeze(0) * b1r.view(M, 1, 1) +
                   a1r.view(M, 1, 1) * h0r)
            hr = (ch_rev[:, 2, :].unsqueeze(0) * b0r.view(M, 1, 1) +
                  ch_rev[:, 1, :].unsqueeze(0) * b1r.view(M, 1, 1) +
                  a1r.view(M, 1, 1) * h1r +
                  a2r * h0r)
            h_rev = (ch_rev[:, 3, :].unsqueeze(0) * b0r.view(M, 1, 1) +
                     ch_rev[:, 2, :].unsqueeze(0) * b1r.view(M, 1, 1) +
                     a1r.view(M, 1, 1) * hr +
                     a2r * h1r)

            outs.append(h_fwd - h_rev)  # [M, B, w]

        return torch.cat(outs, dim=-1)  # [M, B, D]

    def _compute_all_f_specialists_batched(self, psi, chakra_gain, chunk_size=4):
        """Compute IIR outputs for ALL specialists in parallel chunks.

        Processes specialists in chunks of `chunk_size` to bound memory usage
        while still vectorizing within each chunk. Default chunk_size=4 gives
        ~3× memory reduction vs full batching with most of the speedup.

        psi: [B, 4, D] — field history in D-space
        chakra_gain: [C] — from spine
        Returns: all_f_stack [N, B, D]
        """
        chunks = []
        for i in range(0, self.n_specialists, chunk_size):
            chunk = self.specialists[i:i + chunk_size]
            chunks.append(self._compute_all_f_specialist_chunk(chunk, psi, chakra_gain))
        return torch.cat(chunks, dim=0)  # [N, B, D]

    def compute_boundary_residual(self, all_f_stack):
        """Compute per-chakra disagreement between specialists.

        all_f_stack: [N, B, D] — each specialist's IIR output
        Returns: [B, 13] boundary residuals
        """
        N, B, D = all_f_stack.shape
        residuals = []
        offset = 0
        for c in range(self.spine.C):
            w = self.spine.widths[c]
            # Views of chakra c from all specialists
            views = all_f_stack[:, :, offset:offset + w]  # [N, B, w]
            # Disagreement = variance across specialists, mean over width
            if N > 1:
                disagreement = views.var(dim=0).mean(dim=-1)  # [B]
            else:
                disagreement = torch.zeros(B, device=views.device)
            residuals.append(disagreement)
            offset += w
        return torch.stack(residuals, dim=1)  # [B, 13]

    def compute_berry_key(self, trajectories, boundary_residual):
        """Compute 39-dim Berry key for memory.

        trajectories: dict with 'fwd' and 'rev', each list of 13 tensors [4, B, w]
        boundary_residual: [B, 13]
        Returns: [B, 39]
        """
        # Berry phases from trajectories
        # Each trajectory element is [4, B, w] from the spine
        berry_phases = []
        for hemisphere in ['fwd', 'rev']:
            traj_list = trajectories[hemisphere]  # list of 13
            for c in range(self.spine.C):
                t = traj_list[c]  # [4, B, w]
                w = t.shape[-1]
                if w >= 2:
                    x = t[:, :, 0]  # [4, B]
                    y = t[:, :, 1]  # [4, B]
                else:
                    x = t[:, :, 0]
                    y = torch.cat([
                        torch.zeros(1, t.shape[1], device=t.device),
                        x[:-1]
                    ], dim=0)
                area = 0.5 * torch.sum(x[:-1] * y[1:] - x[1:] * y[:-1], dim=0)
                berry_phases.append(area)

        berry_fp = torch.stack(berry_phases, dim=1)  # [B, 26]
        return torch.cat([berry_fp, boundary_residual], dim=1)  # [B, 39]

    def forward(self, x, use_memory=True, return_workspace=False, byte_mode=None):
        """Process physics input through the conscious workspace.

        x: [B, 4, 1024] (field) or [B, 1024] uint8 (bytes)
        byte_mode: override default byte_mode
        Returns:
          pred: [B, 1024] — enhanced prediction
          (optionally: workspace info dict)
        """
        if byte_mode is None:
            byte_mode = self.byte_mode

        # Encode bytes to field if needed
        if byte_mode:
            field = self.spine.byte_encoder.encode_sequence(x, T=4)  # [B, 4, 1024]
        else:
            field = x

        B = field.shape[0]
        device = field.device

        # Ensure workspace state matches batch
        if self.workspace_fwd.shape[0] != B:
            self.reset_workspace(B)
        if self.workspace_fwd.device != device:
            self.workspace_fwd = self.workspace_fwd.to(device)
            self.workspace_rev = self.workspace_rev.to(device)
            self.field_history = self.field_history.to(device)

        # --- Spine prediction (external cord) ---
        # If spine is frozen, compute without gradients for speed
        spine_frozen = not any(p.requires_grad for p in self.spine.parameters())
        if spine_frozen:
            with torch.no_grad():
                pred_spine, trajectories = self.spine(
                    field, return_trajectories=True, byte_mode=False
                )
                repr_external = trajectories['repr']
            pred_spine = pred_spine.detach()
            repr_external = repr_external.detach()
        else:
            pred_spine, trajectories = self.spine(
                field, return_trajectories=True, byte_mode=False
            )
            repr_external = trajectories['repr']  # [B, D]

        # --- Berry memory retrieval ---
        if use_memory and self.berry_memory.n_filled.item() > 0:
            # Compute boundary residual from external prediction
            # (single specialist view = spine itself as baseline)
            all_f_spine = self.spine.compute_all_f(trajectories['psi'])
            boundary_res = self.compute_boundary_residual(
                all_f_spine.unsqueeze(0)  # [1, B, D]
            )
            berry_key = self.compute_berry_key(trajectories, boundary_res)

            retrieved, attn = self.berry_memory.query(berry_key, temperature=0.1)
            workspace_bias = self.memory_decompressor(retrieved)  # [B, D]
        else:
            workspace_bias = torch.zeros(B, self.D, device=device)
            attn = torch.zeros(B, self.berry_memory.n_slots, device=device)

        # --- Field history update with external repr + memory bias ---
        field_current = repr_external + PHI_INV * workspace_bias
        self.field_history = torch.cat([
            self.field_history[:, 1:, :],
            field_current.unsqueeze(1)
        ], dim=1)  # [B, 4, D]

        # --- Specialist competition (batched across N specialists) ---
        all_f_stack = self._compute_all_f_specialists_batched(
            self.field_history, self.spine.chakra_gain
        )  # [N, B, D]

        # Amplitudes with fatigue modulation
        amplitudes = all_f_stack.norm(dim=-1)  # [N, B]
        # Detach specialist_energy to prevent cross-batch gradient accumulation
        specialist_energy_old = self.specialist_energy.detach()
        effective_energy = torch.tanh(specialist_energy_old.unsqueeze(1))  # [N, 1]
        effective_amp = amplitudes * effective_energy  # [N, B]

        # φ-temperature softmax competition
        weights = F.softmax(effective_amp * PHI, dim=0)  # [N, B]

        # Update fatigue: specialists that won get tired
        contributions = weights.mean(dim=1)  # [N]
        self.specialist_energy = PHI_INV * specialist_energy_old + (1 - PHI_INV) * (1.0 - contributions)
        self.specialist_energy = torch.clamp(self.specialist_energy, 0.1, 2.0)

        # Aggregate IIRs before shared fusion (linear property)
        all_f_workspace = torch.einsum('nb,nbd->bd', weights, all_f_stack)  # [B, D]

        # Shared fusion
        field_last = self.field_history[:, -1, :]  # [B, D]
        repr_workspace = self.spine.fusion(
            torch.cat([field_last, all_f_workspace * 0.5], -1)
        ) + field_last  # [B, D]

        # --- Dual workspace update ---
        # Forward: prospective / prediction
        self.workspace_fwd = PHI_INV * self.workspace_fwd + PHI_INV ** 2 * repr_workspace
        # Reverse: retrospective / memory
        self.workspace_rev = PHI_INV * self.workspace_rev + PHI_INV ** 2 * self.workspace_fwd

        # --- Conscious content ---
        conscious = self.workspace_fwd - self.workspace_rev  # [B, D]

        # --- Meta-cord (inner voice) ---
        # Observes workspace history
        workspace_history = torch.stack([
            self.workspace_fwd,
            self.workspace_rev,
            conscious,
            field_last,
        ], dim=1)  # [B, 4, D]
        meta_repr = self.meta_cord.compute_all_f(workspace_history, self.spine.chakra_gain)
        meta_fused = self.spine.fusion(
            torch.cat([workspace_history[:, -1, :], meta_repr * 0.5], -1)
        ) + workspace_history[:, -1, :]

        # Meta-cord gently nudges forward workspace
        self.workspace_fwd = self.workspace_fwd + PHI_INV ** 3 * meta_fused

        # --- Readout: conscious → residual prediction ---
        residual = self.readout(conscious)
        pred_enhanced = pred_spine + residual

        # --- Memory encoding (when calm = low surprise) ---
        surprise = conscious.norm(dim=-1).mean().item()
        # Adaptive threshold: encode when surprise is below running average
        if not hasattr(self, '_surprise_ema'):
            self._surprise_ema = surprise
        self._surprise_ema = 0.95 * self._surprise_ema + 0.05 * surprise
        if use_memory and surprise < self._surprise_ema * 1.3 and self.training:
            with torch.no_grad():
                # Recompute boundary residual with all specialists
                boundary_res = self.compute_boundary_residual(all_f_stack)
                berry_key = self.compute_berry_key(trajectories, boundary_res)
                workspace_summary = self.workspace_fwd.view(B, self.spine.C, -1).mean(dim=-1)  # [B, 13]
                value = torch.cat([workspace_summary, boundary_res], dim=1)  # [B, 26]
                self.berry_memory.write(berry_key.detach(), value.detach(), mode='ema')

        if return_workspace:
            return pred_enhanced, {
                'pred_spine': pred_spine,
                'workspace_fwd': self.workspace_fwd,
                'workspace_rev': self.workspace_rev,
                'conscious': conscious,
                'weights': weights,
                'energy': self.specialist_energy.clone(),
                'memory_attn': attn,
                'surprise': surprise,
            }
        return pred_enhanced

    def get_specialist_freqs(self):
        """Report current specialist frequencies."""
        info = []
        for i, spec in enumerate(self.specialists):
            fwd_freqs = [torch.sigmoid(spec.fwd_theta[c]).item() * math.pi / (2 * math.pi)
                        for c in range(spec.C)]
            info.append({
                'specialist': i,
                'offset': spec.freq_offset.item(),
                'mean_freq': sum(fwd_freqs) / len(fwd_freqs),
                'freq_range': (min(fwd_freqs), max(fwd_freqs)),
            })
        return info

    def get_memory_stats(self):
        return self.berry_memory.get_stats()


# ---------------------------------------------------------------------------
# Quick test / sanity check
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("Building φ-Garden brain...")
    garden = PhiGardenBrain(D=1040, n_specialists=5)

    # Count parameters
    spine_params = sum(p.numel() for p in garden.spine.parameters())
    specialist_params = sum(p.numel() for p in garden.specialists.parameters())
    meta_params = sum(p.numel() for p in garden.meta_cord.parameters())
    readout_params = sum(p.numel() for p in garden.readout.parameters())
    decompressor_params = sum(p.numel() for p in garden.memory_decompressor.parameters())
    memory_params = garden.berry_memory.keys.numel() + garden.berry_memory.values.numel()

    total = specialist_params + meta_params + readout_params + decompressor_params + memory_params
    # Fusion is shared (part of spine)

    print(f"  Spine params:          {spine_params:,}")
    print(f"  5 specialists:         {specialist_params:,}  ({specialist_params//5:,} each)")
    print(f"  Meta-cord:             {meta_params:,}")
    print(f"  Readout:               {readout_params:,}")
    print(f"  Memory decompressor:   {decompressor_params:,}")
    print(f"  Memory banks (512):    {memory_params:,}")
    print(f"  Brain total (excl spine): {total:,}")
    print(f"  Full system:           {spine_params + total:,}")

    # Test forward pass
    x = torch.randn(2, 4, 1024)
    pred, info = garden(x, return_workspace=True)
    print(f"\nTest forward:")
    print(f"  Input:    {x.shape}")
    print(f"  Output:   {pred.shape}")
    print(f"  Weights:  {info['weights'].shape}  (specialist competition)")
    print(f"  Conscious: {info['conscious'].shape}")
    print(f"  Surprise: {info['surprise']:.4f}")
    print(f"  Specialist energy: {info['energy'].tolist()}")

    # Test specialist frequencies
    freqs = garden.get_specialist_freqs()
    print(f"\nSpecialist frequency offsets:")
    for f in freqs:
        print(f"  Spec {f['specialist']}: offset={f['offset']:.3f}, mean_freq={f['mean_freq']:.4f}")
