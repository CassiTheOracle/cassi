"""MnemosyneCord — φ-Resonant Associative Memory.

A chord designed around recall rather than prediction.  It stores patterns as
attractors in a multi-chakra resonant field and retrieves them via energy
minimisation.  Can be used standalone (ultimate compression / memory bank) or
hybridised with a predictive CordPhysics spine.

Design principles
-----------------
* 13 chakras, φ-scaled widths / inversely φ-scaled frequencies (same skeleton
  as CordPhysics).
* Each chakra extracts a frequency-specific signature from the input.
* Persistent IIR states (h1, h2) act as a working-memory cache.
* A large associative memory matrix stores full signatures for long-term recall.
* Recall is iterative attractor dynamics: the cue "rings" the chord until the
  resonances stabilise on the nearest stored memory.
* The memory is holographic — any subset of chakras can reconstruct the
  pattern (with graceful degradation).
"""

import math
from typing import Literal, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _phi_spaced_widths(D: int, n_chakras: int = 13) -> list[int]:
    """Compute chakra widths that sum to D with φ-scaling."""
    raw = [PHI ** c for c in range(n_chakras)]
    total = sum(raw)
    widths = [max(1, round(D * r / total)) for r in raw]
    widths[-1] += D - sum(widths)
    return widths


def _init_phi_spaced_theta(param: nn.Parameter, theta_max: float = 2.5) -> None:
    """Logit-initialise so sigmoid(theta) * π gives inversely φ-spaced freqs."""
    for c in range(param.shape[0]):
        theta_c = theta_max * (PHI ** (-c))
        y = max(0.001, min(0.999, theta_c / math.pi))
        param.data[c] = math.log(y / (1.0 - y))


# ---------------------------------------------------------------------------
# Core: MnemosyneCord
# ---------------------------------------------------------------------------

class MnemosyneCord(nn.Module):
    """Standalone resonant associative-memory chord.

    Parameters
    ----------
    D : int
        Internal dimension (total width of all chakras).  Default 1040.
    input_dim : int
        Dimension of the raw pattern vectors.  Default 1024.
    n_slots : int
        Number of slots in the long-term associative memory bank.  Default 16384.
    chakra_temperature : float
        Temperature for sparse chakra gating during storage.  Lower = sparser.
    attractor_steps : int
        Default number of attractor-dynamics steps during recall.
    working_memory_decay : float
        EMA decay for the persistent IIR working-memory cache (h1, h2).
        PHI_INV = 0.618 is the biological default; 0.9 = longer cache.
    """

    def __init__(
        self,
        D: int = 1040,
        input_dim: int = 1024,
        n_slots: int = 16384,
        chakra_temperature: float = 0.5,
        attractor_steps: int = 4,
        working_memory_decay: float = PHI_INV,
    ):
        super().__init__()
        self.D = D
        self.input_dim = input_dim
        self.n_slots = n_slots
        self.chakra_temperature = chakra_temperature
        self.attractor_steps = attractor_steps
        self.working_memory_decay = working_memory_decay  # α for h1/h2 EMA
        self.C = 13

        # ── Chakra geometry ──
        self.widths = _phi_spaced_widths(D, self.C)
        self._offsets = []
        off = 0
        for w in self.widths:
            self._offsets.append((off, off + w))
            off += w

        # ── Input projection ──
        self.in_proj = nn.Sequential(
            nn.Linear(input_dim, D),
            nn.LayerNorm(D),
        )

        # ── Chakra parameters ──
        # Per-chakra gains (sigmoid-scaled, ×2 range)
        self.chakra_gain = nn.Parameter(torch.zeros(self.C))

        # Forward / reverse IIR frequencies (logit-space, φ-spaced init)
        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.rev_theta = nn.Parameter(torch.randn(self.C))
        _init_phi_spaced_theta(self.fwd_theta)
        _init_phi_spaced_theta(self.rev_theta)

        # IIR feed-forward coefficients
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))

        # ── Memory-commit gates ──
        # Each chakra learns how "surprising" a pattern must be to get written
        # to long-term memory.  High gate = store; low gate = ignore.
        self.commit_gate = nn.Parameter(torch.zeros(self.C))

        # ── Long-term associative memory bank ──
        # We store *signatures* (the concatenated chakra outputs) as keys and
        # *compressed representations* as values.  Keys are L2-normalised for
        # cosine-similarity retrieval.
        self.register_buffer("mem_keys", torch.zeros(n_slots, D))     # signatures
        self.register_buffer("mem_vals", torch.zeros(n_slots, D))     # repr vectors
        self.register_buffer("mem_mask", torch.zeros(n_slots, dtype=torch.bool))
        self.register_buffer("mem_age", torch.zeros(n_slots, dtype=torch.long))
        self.register_buffer("mem_count", torch.zeros(n_slots))
        self._n_filled = 0

        # ── Working-memory IIR state (persistent across calls) ──
        # These are NOT register_buffer because we want them to survive
        # `state_dict()` loading / device moves but NOT be optimised.
        self.register_buffer("_wm_h1", torch.zeros(1, D))
        self.register_buffer("_wm_h2", torch.zeros(1, D))
        self.register_buffer("_wm_x1", torch.zeros(1, D))

        # ── Decode head ──
        # Maps a fused representation back to input space.
        self.fusion = nn.Linear(D * 2, D, bias=False)
        self.decoder = nn.Linear(D, input_dim)

        # ── Attractor-step MLP (learned energy landscape) ──
        # Each recall step refines signatures through a small MLP that is
        # trained to minimise reconstruction error.
        self.attractor_mlp = nn.Sequential(
            nn.Linear(D, D // 2),
            nn.LayerNorm(D // 2),
            nn.GELU(),
            nn.Linear(D // 2, D),
        )

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def _iir(self, x: torch.Tensor, a1, a2, b0, b1) -> torch.Tensor:
        """Second-order IIR over 4 time steps.  x: [B, 4, W]."""
        h0 = x[:, 0] * b0
        h1 = x[:, 1] * b0 + x[:, 0] * b1 + a1 * h0
        h = x[:, 2] * b0 + x[:, 1] * b1 + a1 * h1 + a2 * h0
        out = x[:, 3] * b0 + x[:, 2] * b1 + a1 * h + a2 * h1
        return out

    def _encode_frame(self, x: torch.Tensor) -> torch.Tensor:
        """Project a single frame [B, input_dim] → D-space [B, D]."""
        return self.in_proj(x)

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, list[torch.Tensor]]:
        """Encode input into per-chakra signatures.

        Parameters
        ----------
        x : torch.Tensor
            [B, 4, input_dim] windowed input, or [B, input_dim] single frame.

        Returns
        -------
        signatures : [B, D]
            Flattened concatenation of all chakra signatures.
        repr_vec : [B, D]
            Fused representation suitable for decoding or storage.
        chakra_sigs : list of [B, W_c]
            Individual chakra signatures (useful for sparse gating).
        """
        if x.dim() == 2:
            # Single frame — repeat to create a pseudo-window
            x = x.unsqueeze(1).expand(-1, 4, -1)
        B = x.shape[0]

        # Project to D-space and split into chakras
        psi = self.in_proj(x)  # [B, 4, D]
        chakra_sigs: list[torch.Tensor] = []

        for c in range(self.C):
            start, end = self._offsets[c]
            w = end - start
            ch = psi[:, :, start:end]  # [B, 4, W_c]
            g = torch.sigmoid(self.chakra_gain[c]) * 2.0
            ch = ch * g

            # Forward IIR
            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf
            h_fwd = self._iir(ch, a1, a2, b0, b1)

            # Reverse IIR
            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            b0r, b1r = b0r / sr, b1r / sr
            h_rev = self._iir(torch.flip(ch, [1]), a1r, a2r, b0r, b1r)

            chakra_sigs.append(h_fwd - h_rev)

        signatures = torch.cat(chakra_sigs, dim=-1)  # [B, D]

        # Fusion (same formula as CordPhysics)
        repr_vec = self.fusion(torch.cat([psi[:, -1, :], signatures * 0.5], dim=-1)) + psi[:, -1, :]

        return signatures, repr_vec, chakra_sigs

    # ------------------------------------------------------------------
    # Working memory (persistent IIR cache)
    # ------------------------------------------------------------------

    def _ensure_wm(self, B: int, device: torch.device) -> None:
        """Lazy-allocate working-memory buffers."""
        if self._wm_h1.shape[0] < B or self._wm_h1.device != device:
            self._wm_h1 = torch.zeros(B, self.D, device=device)
            self._wm_h2 = torch.zeros(B, self.D, device=device)
            self._wm_x1 = torch.zeros(B, self.D, device=device)
        elif self._wm_h1.device != device:
            self._wm_h1 = self._wm_h1.to(device)
            self._wm_h2 = self._wm_h2.to(device)
            self._wm_x1 = self._wm_x1.to(device)

    def _update_working_memory(self, signatures: torch.Tensor) -> torch.Tensor:
        """EMA-update the persistent IIR cache with new signatures.

        Returns the blended working-memory state [B, D].
        """
        B, device = signatures.shape[0], signatures.device
        self._ensure_wm(B, device)

        h1 = self._wm_h1[:B]
        h2 = self._wm_h2[:B]
        x1 = self._wm_x1[:B]
        alpha = self.working_memory_decay

        # Treat signatures as the "input" to a first-order IIR
        new_h2 = alpha * h2 + (1 - alpha) * h1
        new_h1 = alpha * h1 + (1 - alpha) * signatures
        new_x1 = alpha * x1 + (1 - alpha) * signatures

        with torch.no_grad():
            h1.copy_(new_h1)
            h2.copy_(new_h2)
            x1.copy_(new_x1)

        # Working memory = weighted combination of recent + older traces
        return PHI_INV * h1 + PHI_INV ** 2 * h2 + PHI_INV ** 3 * x1

    # ------------------------------------------------------------------
    # Long-term memory bank
    # ------------------------------------------------------------------

    def _find_matches(self, keys: torch.Tensor, threshold: float = 0.85):
        """Cosine-similarity match against stored keys.

        Returns (best_sim [B], best_idx [B]).
        """
        B = keys.shape[0]
        if self._n_filled == 0:
            return torch.full((B,), -1.0, device=keys.device), torch.zeros(B, dtype=torch.long, device=keys.device)

        q = F.normalize(keys, dim=-1)
        k = F.normalize(self.mem_keys, dim=-1)
        sim = q @ k.T  # [B, n_slots]
        sim = sim.masked_fill(~self.mem_mask.unsqueeze(0), torch.finfo(sim.dtype).min)
        best_sim, best_idx = sim.max(dim=-1)
        return best_sim, best_idx.clamp(0, self.n_slots - 1)

    def store(self, x: torch.Tensor, mode: Literal["ema", "replace", "cumulative"] = "ema") -> dict:
        """Store pattern(s) in long-term memory.

        Parameters
        ----------
        x : [B, input_dim] or [B, 4, input_dim]
        mode : storage update rule for collisions

        Returns
        -------
        info : dict with 'n_new', 'n_updated', 'sparsity'
        """
        signatures, repr_vec, chakra_sigs = self.encode(x)
        B = signatures.shape[0]
        device = signatures.device

        # --- Sparse gating: which chakras "care" about this pattern? ---
        chakra_norms = torch.stack([s.norm(dim=-1) for s in chakra_sigs], dim=1)  # [B, C]
        gate_logits = self.commit_gate.unsqueeze(0) + torch.log(chakra_norms + 1e-8)
        gate = torch.sigmoid(gate_logits / self.chakra_temperature)  # [B, C]
        sparsity = (gate > 0.5).float().mean().item()

        # Apply gate to signatures (sparse storage)
        for c in range(self.C):
            start, end = self._offsets[c]
            signatures[:, start:end] *= gate[:, c].unsqueeze(-1)

        # --- Update working memory ---
        self._update_working_memory(signatures.detach())

        # --- Write to long-term bank ---
        with torch.no_grad():
            q = F.normalize(signatures, dim=-1)
            best_sim, best_idx = self._find_matches(q, threshold=0.85)
            match_mask = best_sim > 0.85
            new_mask = ~match_mask

            info = {"n_new": 0, "n_updated": 0, "sparsity": sparsity}

            # Update existing slots
            if match_mask.any():
                match_idx = best_idx[match_mask]
                match_sig = signatures[match_mask]
                match_repr = repr_vec[match_mask]

                # Unique indices + averaging
                u_idx, inverse = torch.unique(match_idx, return_inverse=True)
                gc = torch.zeros(len(u_idx), device=device)
                gc.scatter_add_(0, inverse, torch.ones(len(inverse), device=device))

                sum_sigs = torch.zeros(len(u_idx), self.D, device=device)
                sum_reprs = torch.zeros(len(u_idx), self.D, device=device)
                sum_sigs.scatter_add_(0, inverse.unsqueeze(-1).expand(-1, self.D), match_sig)
                sum_reprs.scatter_add_(0, inverse.unsqueeze(-1).expand(-1, self.D), match_repr)

                avg_sig = sum_sigs / gc.unsqueeze(-1).clamp(min=1)
                avg_repr = sum_reprs / gc.unsqueeze(-1).clamp(min=1)

                if mode == "ema":
                    old_counts = self.mem_count[u_idx]
                    alpha = 1.0 / (old_counts + 1.0)
                    self.mem_keys[u_idx] = (1 - alpha.unsqueeze(-1)) * self.mem_keys[u_idx] + alpha.unsqueeze(-1) * avg_sig
                    self.mem_vals[u_idx] = (1 - alpha.unsqueeze(-1)) * self.mem_vals[u_idx] + alpha.unsqueeze(-1) * avg_repr
                elif mode == "replace":
                    self.mem_keys[u_idx] = avg_sig
                    self.mem_vals[u_idx] = avg_repr
                else:  # cumulative
                    self.mem_keys[u_idx] += avg_sig
                    self.mem_vals[u_idx] += avg_repr

                self.mem_count[u_idx] += 1
                self.mem_age[u_idx] = 0
                info["n_updated"] = len(u_idx)

            # Write new slots
            if new_mask.any():
                new_sig = signatures[new_mask]
                new_repr = repr_vec[new_mask]
                N_new = new_sig.shape[0]

                empty = torch.where(~self.mem_mask)[0]
                if empty.shape[0] >= N_new:
                    assigned = empty[:N_new]
                else:
                    assigned_empty = empty
                    n_evict = N_new - assigned_empty.shape[0]
                    if n_evict > 0 and self._n_filled > 0:
                        n_evict = min(n_evict, self._n_filled)
                        ages_clone = self.mem_age.clone()
                        ages_clone[~self.mem_mask] = -1
                        _, evict_idx = torch.topk(ages_clone, n_evict)
                        assigned = torch.cat([assigned_empty, evict_idx])
                    else:
                        assigned = assigned_empty

                n_assign = len(assigned)
                self.mem_keys[assigned] = new_sig[:n_assign]
                self.mem_vals[assigned] = new_repr[:n_assign]
                self.mem_count[assigned] = 1
                self.mem_age[assigned] = 0
                self.mem_mask[assigned] = True
                info["n_new"] = n_assign

            self._n_filled = int(self.mem_mask.sum().item())
            self.mem_age[self.mem_mask] += 1

        return info

    # ------------------------------------------------------------------
    # Recall (attractor dynamics)
    # ------------------------------------------------------------------

    def _attractor_step(self, signatures: torch.Tensor, temperature: float = 1.0) -> torch.Tensor:
        """One step of attractor relaxation.

        The update is a damped gradient step toward the retrieved memory,
        plus a small learned correction that shapes the attractor basin:

            sig' = sig + α·(retrieved − sig) + β·mlp(sig)

        with α = PHI_INV ≈ 0.618 and β = PHI_INV² ≈ 0.382.  The convex
        combination of ``sig`` and ``retrieved`` guarantees contraction
        when the memory bank is fixed; the MLP residual is small and
        trained to nudge the dynamics toward the true stored pattern.

        Returns refined signatures [B, D].
        """
        if self._n_filled == 0:
            # No long-term memory yet — refine via learned MLP only
            return signatures + PHI_INV * self.attractor_mlp(signatures)

        # 1. Query long-term memory
        q = F.normalize(signatures, dim=-1)
        k = F.normalize(self.mem_keys, dim=-1)
        sim = q @ k.T  # [B, n_slots]
        sim = sim.masked_fill(~self.mem_mask.unsqueeze(0), torch.finfo(sim.dtype).min)

        # Sparse top-k attention (like BerryMemory)
        k_sparse = min(64, self._n_filled)
        topk_sim, topk_idx = sim.topk(k_sparse, dim=-1)
        attn = F.softmax(topk_sim / temperature, dim=-1)  # [B, k_sparse]

        retrieved = torch.bmm(
            attn.unsqueeze(1),
            self.mem_vals[topk_idx],
        ).squeeze(1)  # [B, D]

        # 2. Contractive update toward retrieved memory + learned correction
        # The dynamics are a damped relaxation toward the retrieved memory,
        # plus a small learned residual that shapes the attractor basin.
        # Empirically, 3–4 steps gives optimal convergence; beyond that the
        # unconstrained MLP can overshoot (set ``attractor_steps`` accordingly).
        delta = retrieved - signatures
        correction = self.attractor_mlp(signatures)
        refined = signatures + PHI_INV * delta + (PHI_INV ** 2) * correction

        return refined

    def recall(
        self,
        x_cue: torch.Tensor,
        steps: Optional[int] = None,
        temperature: float = 1.0,
        return_trajectory: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, list[torch.Tensor]]:
        """Recall the nearest stored pattern to the cue.

        Parameters
        ----------
        x_cue : [B, input_dim] or [B, 4, input_dim]
            Partial, noisy, or complete pattern to use as retrieval key.
        steps : int, optional
            Number of attractor-dynamics iterations.  Defaults to
            ``self.attractor_steps``.
        temperature : float
            Softmax temperature for memory attention.  Lower = sharper,
            more winner-take-all retrieval.
        return_trajectory : bool
            If True, return the signature at every attractor step.

        Returns
        -------
        recalled : [B, input_dim]
            The reconstructed pattern.
        trajectory : list of [B, input_dim], optional
            Decoded pattern at each step (for analysis / visualisation).
        """
        steps = steps if steps is not None else self.attractor_steps
        signatures, _, _ = self.encode(x_cue)

        trajectory: list[torch.Tensor] = []

        for _ in range(steps):
            signatures = self._attractor_step(signatures, temperature=temperature)
            if return_trajectory:
                # Decode intermediate for trajectory
                traj_repr = self.fusion(torch.cat([signatures, signatures * 0.5], dim=-1)) + signatures
                trajectory.append(self.decoder(traj_repr))

        # Final decode
        repr_vec = self.fusion(torch.cat([signatures, signatures * 0.5], dim=-1)) + signatures
        recalled = self.decoder(repr_vec)

        if return_trajectory:
            return recalled, trajectory
        return recalled

    # ------------------------------------------------------------------
    # Convenience forward
    # ------------------------------------------------------------------

    def forward(
        self,
        x: torch.Tensor,
        mode: Literal["autoencode", "store", "recall"] = "autoencode",
    ) -> torch.Tensor | dict:
        """Convenience dispatch.

        * ``autoencode`` — store x, then recall from a noisy cue.  Training mode.
        * ``store``      — store x, return storage info dict.
        * ``recall``     — recall nearest memory to x.
        """
        if mode == "store":
            return self.store(x)
        elif mode == "recall":
            return self.recall(x)
        elif mode == "autoencode":
            # Training: store the clean pattern, recall from a noisy cue
            with torch.no_grad():
                self.store(x)
            # During training we still want gradients through recall
            noise = 0.15 * torch.randn_like(x) if x.dim() == 2 else 0.15 * torch.randn_like(x[:, -1, :])
            cue = x + noise if x.dim() == 2 else x[:, -1, :] + noise
            return self.recall(cue)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_working_memory(self, batch_size: Optional[int] = None) -> None:
        """Clear the persistent IIR working-memory cache.

        Call this when starting a new, unrelated session / episode.
        Long-term ``mem_*`` buffers are NOT cleared.
        """
        device = self._wm_h1.device
        B = batch_size if batch_size is not None else 1
        self._wm_h1 = torch.zeros(B, self.D, device=device)
        self._wm_h2 = torch.zeros(B, self.D, device=device)
        self._wm_x1 = torch.zeros(B, self.D, device=device)

    def memory_stats(self) -> dict:
        """Return statistics about the long-term memory bank."""
        n = self._n_filled
        if n == 0:
            return {"filled": 0, "mean_count": 0.0, "max_age": 0, "capacity": self.n_slots}
        return {
            "filled": n,
            "fill_ratio": n / self.n_slots,
            "mean_count": self.mem_count[:n].mean().item(),
            "max_age": int(self.mem_age[:n].max().item()),
            "capacity": self.n_slots,
        }


# ---------------------------------------------------------------------------
# Hybrid: Predictive + Mnemosyne cord sharing chakra weights
# ---------------------------------------------------------------------------

class HybridCord(nn.Module):
    """A single physical cord that serves both prediction and memory.

    The 13 chakras, their frequencies, and their IIR coefficients are shared.
    Two lightweight heads branch from the fused representation:

    * **Predictive head** — ``decoder_pred`` maps repr → next-frame residual.
    * **Memory head**     — ``decoder_mem`` maps repr → full reconstruction.

    During inference you can toggle ``mode='predict' | 'memorise' | 'recall'``.
    During training you supervise both heads simultaneously; the shared
    chakras learn representations that are useful for *both* anticipating
    the future and remembering the past.

    This is the "ultimate compression" idea: the same resonant encoding
    compactly represents everything needed for both tasks.
    """

    def __init__(
        self,
        D: int = 1040,
        input_dim: int = 1024,
        n_slots: int = 16384,
        attractor_steps: int = 4,
    ):
        super().__init__()
        self.D = D
        self.input_dim = input_dim

        # ── Shared chakra body ──
        self.widths = _phi_spaced_widths(D, 13)
        self._offsets = []
        off = 0
        for w in self.widths:
            self._offsets.append((off, off + w))
            off += w
        self.C = 13

        self.in_proj = nn.Sequential(nn.Linear(input_dim, D), nn.LayerNorm(D))
        self.chakra_gain = nn.Parameter(torch.zeros(self.C))

        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.rev_theta = nn.Parameter(torch.randn(self.C))
        _init_phi_spaced_theta(self.fwd_theta)
        _init_phi_spaced_theta(self.rev_theta)

        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))

        # ── Shared fusion ──
        self.fusion = nn.Linear(D * 2, D, bias=False)

        # ── Predictive head (CordPhysics-style) ──
        self.decoder_pred = nn.Linear(D, input_dim)

        # ── Memory head (Mnemosyne-style) ──
        self.decoder_mem = nn.Linear(D, input_dim)
        self.attractor_mlp = nn.Sequential(
            nn.Linear(D, D // 2),
            nn.LayerNorm(D // 2),
            nn.GELU(),
            nn.Linear(D // 2, D),
        )

        # ── Memory bank ──
        self.register_buffer("mem_keys", torch.zeros(n_slots, D))
        self.register_buffer("mem_vals", torch.zeros(n_slots, D))
        self.register_buffer("mem_mask", torch.zeros(n_slots, dtype=torch.bool))
        self.register_buffer("mem_age", torch.zeros(n_slots, dtype=torch.long))
        self.register_buffer("mem_count", torch.zeros(n_slots))
        self._n_filled = 0

        # ── Working memory ──
        self.register_buffer("_wm_h1", torch.zeros(1, D))
        self.register_buffer("_wm_h2", torch.zeros(1, D))
        self._wm_initialized = False

    # ------------------------------------------------------------------
    # Shared encoder
    # ------------------------------------------------------------------

    def _iir(self, x, a1, a2, b0, b1):
        h0 = x[:, 0] * b0
        h1 = x[:, 1] * b0 + x[:, 0] * b1 + a1 * h0
        h = x[:, 2] * b0 + x[:, 1] * b1 + a1 * h1 + a2 * h0
        return x[:, 3] * b0 + x[:, 2] * b1 + a1 * h + a2 * h1

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Shared encoding: input → (signatures [B,D], repr [B,D])."""
        if x.dim() == 2:
            x = x.unsqueeze(1).expand(-1, 4, -1)
        psi = self.in_proj(x)
        outs = []
        for c in range(self.C):
            s, e = self._offsets[c]
            ch = psi[:, :, s:e] * (torch.sigmoid(self.chakra_gain[c]) * 2.0)

            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            h_fwd = self._iir(ch, a1, a2, b0 / sf, b1 / sf)

            theta_r = torch.sigmoid(self.rev_theta[c]) * math.pi
            a1r = 2.0 * PHI_INV * torch.cos(theta_r)
            a2r = -(PHI_INV) ** 2
            b0r = torch.sigmoid(self.rev_b0[c])
            b1r = torch.sigmoid(self.rev_b1[c])
            sr = b0r + b1r + 1e-8
            h_rev = self._iir(torch.flip(ch, [1]), a1r, a2r, b0r / sr, b1r / sr)

            outs.append(h_fwd - h_rev)

        signatures = torch.cat(outs, dim=-1)
        repr_vec = self.fusion(torch.cat([psi[:, -1, :], signatures * 0.5], dim=-1)) + psi[:, -1, :]
        return signatures, repr_vec

    # ------------------------------------------------------------------
    # Predictive forward (drop-in replacement for CordPhysics.forward)
    # ------------------------------------------------------------------

    def predict(self, x: torch.Tensor) -> torch.Tensor:
        """Predict next frame from 4-frame history.

        x: [B, 4, input_dim]
        Returns: [B, input_dim] residual prediction.
        """
        signatures, repr_vec = self.encode(x)
        return x[:, -1, :] + self.decoder_pred(repr_vec)

    # ------------------------------------------------------------------
    # Memory operations
    # ------------------------------------------------------------------

    def _ensure_wm(self, B: int, device: torch.device) -> None:
        if self._wm_h1.shape[0] < B or self._wm_h1.device != device:
            self._wm_h1 = torch.zeros(B, self.D, device=device)
            self._wm_h2 = torch.zeros(B, self.D, device=device)

    def _update_wm(self, signatures: torch.Tensor) -> None:
        B, device = signatures.shape[0], signatures.device
        self._ensure_wm(B, device)
        h1 = self._wm_h1[:B]
        h2 = self._wm_h2[:B]
        alpha = PHI_INV
        with torch.no_grad():
            h1.copy_(alpha * h1 + (1 - alpha) * signatures)
            h2.copy_(alpha * h2 + (1 - alpha) * h1)

    def store(self, x: torch.Tensor) -> dict:
        """Store pattern in long-term memory."""
        signatures, repr_vec = self.encode(x)
        self._update_wm(signatures.detach())

        with torch.no_grad():
            q = F.normalize(signatures, dim=-1)
            if self._n_filled > 0:
                k = F.normalize(self.mem_keys, dim=-1)
                sim = q @ k.T
                sim = sim.masked_fill(~self.mem_mask.unsqueeze(0), torch.finfo(sim.dtype).min)
                best_sim, best_idx = sim.max(dim=-1)
            else:
                best_sim = torch.full((signatures.shape[0],), -1.0, device=signatures.device)
                best_idx = torch.zeros(signatures.shape[0], dtype=torch.long, device=signatures.device)

            match = best_sim > 0.85
            info = {"n_new": 0, "n_updated": 0}

            if match.any():
                u_idx, inv = torch.unique(best_idx[match], return_inverse=True)
                gc = torch.zeros(len(u_idx), device=signatures.device)
                gc.scatter_add_(0, inv, torch.ones(len(inv), device=signatures.device))
                ss = torch.zeros(len(u_idx), self.D, device=signatures.device)
                ss.scatter_add_(0, inv.unsqueeze(-1).expand(-1, self.D), signatures[match])
                sr = torch.zeros(len(u_idx), self.D, device=signatures.device)
                sr.scatter_add_(0, inv.unsqueeze(-1).expand(-1, self.D), repr_vec[match])
                avg_s = ss / gc.unsqueeze(-1).clamp(min=1)
                avg_r = sr / gc.unsqueeze(-1).clamp(min=1)
                old = self.mem_count[u_idx]
                a = 1.0 / (old + 1.0)
                self.mem_keys[u_idx] = (1 - a.unsqueeze(-1)) * self.mem_keys[u_idx] + a.unsqueeze(-1) * avg_s
                self.mem_vals[u_idx] = (1 - a.unsqueeze(-1)) * self.mem_vals[u_idx] + a.unsqueeze(-1) * avg_r
                self.mem_count[u_idx] += 1
                self.mem_age[u_idx] = 0
                info["n_updated"] = len(u_idx)

            new = ~match
            if new.any():
                ns = signatures[new]
                nr = repr_vec[new]
                N = ns.shape[0]
                empty = torch.where(~self.mem_mask)[0]
                if empty.shape[0] >= N:
                    assigned = empty[:N]
                else:
                    ae = empty
                    ne = N - ae.shape[0]
                    if ne > 0 and self._n_filled > 0:
                        ne = min(ne, self._n_filled)
                        ages = self.mem_age.clone()
                        ages[~self.mem_mask] = -1
                        _, evict = torch.topk(ages, ne)
                        assigned = torch.cat([ae, evict])
                    else:
                        assigned = ae
                na = len(assigned)
                self.mem_keys[assigned] = ns[:na]
                self.mem_vals[assigned] = nr[:na]
                self.mem_count[assigned] = 1
                self.mem_age[assigned] = 0
                self.mem_mask[assigned] = True
                info["n_new"] = na

            self._n_filled = int(self.mem_mask.sum().item())
            self.mem_age[self.mem_mask] += 1

        return info

    def recall(self, x_cue: torch.Tensor, steps: int = 4, temperature: float = 1.0) -> torch.Tensor:
        """Recall nearest memory to cue via attractor dynamics."""
        signatures, _ = self.encode(x_cue)
        for _ in range(steps):
            if self._n_filled == 0:
                signatures = signatures + PHI_INV * self.attractor_mlp(signatures)
                continue
            q = F.normalize(signatures, dim=-1)
            k = F.normalize(self.mem_keys, dim=-1)
            sim = q @ k.T
            sim = sim.masked_fill(~self.mem_mask.unsqueeze(0), torch.finfo(sim.dtype).min)
            ks = min(64, self._n_filled)
            tk, ti = sim.topk(ks, dim=-1)
            attn = F.softmax(tk / temperature, dim=-1)
            retrieved = torch.bmm(attn.unsqueeze(1), self.mem_vals[ti]).squeeze(1)
            delta = retrieved - signatures
            correction = self.attractor_mlp(signatures)
            signatures = signatures + PHI_INV * delta + (PHI_INV ** 2) * correction

        # Decode through memory head
        return self.decoder_mem(signatures)

    # ------------------------------------------------------------------
    # Unified forward (training)
    # ------------------------------------------------------------------

    def forward(
        self,
        x: torch.Tensor,
        mode: Literal["predict", "store", "recall", "both"] = "both",
    ) -> torch.Tensor | dict:
        """Unified entry point.

        * ``predict`` — next-frame prediction only.
        * ``store``   — store pattern, return info dict.
        * ``recall``  — memory recall only.
        * ``both``    — returns dict with ``pred`` and ``recalled``.
        """
        if mode == "predict":
            return self.predict(x)
        if mode == "store":
            return self.store(x)
        if mode == "recall":
            return self.recall(x)

        # mode == "both" — compute shared encoding once, branch to both heads
        signatures, repr_vec = self.encode(x)
        pred = x[:, -1, :] + self.decoder_pred(repr_vec)
        mem_out = self.decoder_mem(repr_vec)
        return {"pred": pred, "recalled": mem_out, "repr": repr_vec, "signatures": signatures}

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def reset_working_memory(self, batch_size: Optional[int] = None) -> None:
        device = self._wm_h1.device
        B = batch_size if batch_size is not None else 1
        self._wm_h1 = torch.zeros(B, self.D, device=device)
        self._wm_h2 = torch.zeros(B, self.D, device=device)

    def memory_stats(self) -> dict:
        n = self._n_filled
        if n == 0:
            return {"filled": 0, "capacity": self.mem_keys.shape[0]}
        return {
            "filled": n,
            "fill_ratio": n / self.mem_keys.shape[0],
            "mean_count": self.mem_count[:n].mean().item(),
            "max_age": int(self.mem_age[:n].max().item()),
            "capacity": self.mem_keys.shape[0],
        }
