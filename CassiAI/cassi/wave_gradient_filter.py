"""WaveGradientFilter — Cassi-native optimizer.

Full integration of IIR temporal filtering, chakra spectral decomposition,
and Muon-style Newton-Schulz orthogonalization. Designed specifically for
φ-scaled wave-dynamics architectures.

Pipeline per 2D parameter (where one dimension == D):
    1. IIR temporal filter:   m_t = b0·g_t + a1·m_{t-1} + a2·m_{t-2}
    2. Chakra split:          decompose m_t into 13 bands via spine.widths
    3. Resonant NS:           per-band Newton-Schulz with theta-adaptive steps
    4. Yang-weighted fusion:  φ-decaying weights, high-freq chakras lead
    5. Aspect-ratio scaling:  Muon compensation for non-square bands

For 1D parameters: standard IIR (no NS).
For non-D-shaped 2D matrices: full-matrix Muon (no chakra split).

Philosophy:
    IIR  → Yin: temporal memory, φ-damped recurrence
    NS   → Yang: spatial expansion, orthogonalized exploration
    Chakra split → the 13 spectral voices of the spine, each with its own
                   learned resonance frequency governing update dynamics.
"""

import math
import torch
from torch.optim.optimizer import Optimizer

from cassi.cord import PHI, PHI_INV


# ---------------------------------------------------------------------------
# Newton–Schulz quintic iteration (KellerJordan coefficients)
# ---------------------------------------------------------------------------
_NS_A, _NS_B, _NS_C = 3.4445, -4.7750, 2.0315


def _zeropower_via_newtonschulz5(G: torch.Tensor, steps: int):
    """Return nearest orthogonal matrix to G via NS-5 in bfloat16.
    Handles non-square matrices by transposing when m > n.
    """
    assert G.ndim >= 2
    if steps <= 0:
        return G
    X = G.to(torch.bfloat16)
    if G.size(-2) > G.size(-1):
        X = X.mT

    # Clamp spectral norm to ≤ 1
    X = X / (X.norm(dim=(-2, -1), keepdim=True) + 1e-7)

    for _ in range(steps):
        A = X @ X.mT
        B = _NS_B * A + _NS_C * A @ A
        X = _NS_A * X + B @ X

    if G.size(-2) > G.size(-1):
        X = X.mT
    return X.to(G.dtype)


# ---------------------------------------------------------------------------
# Full-matrix Muon (for non-D-shaped 2D params)
# ---------------------------------------------------------------------------

def _full_matrix_muon(G: torch.Tensor, steps: int = 5):
    """Apply Muon orthogonalization to the full matrix G."""
    update = _zeropower_via_newtonschulz5(G, steps)
    m, n = update.shape[-2], update.shape[-1]
    update *= max(1, m / n) ** 0.5
    return update


# ---------------------------------------------------------------------------
# Chakra geometry helpers
# ---------------------------------------------------------------------------

def _compute_chakra_offsets(widths):
    """Return list of (start, end) tuples for each chakra band."""
    offs = []
    cursor = 0
    for w in widths:
        offs.append((cursor, cursor + w))
        cursor += w
    return offs


def _theta_to_ns_steps(theta_sigmoid_pi, theta_max, ns_min, ns_max):
    """Map learned chakra frequency to Newton-Schulz step count.

    High-frequency chakras (theta near theta_max) are noisier and benefit
    from deeper orthogonalization. Low-frequency chakras converge faster
    with fewer steps.
    """
    ratio = theta_sigmoid_pi / (theta_max + 1e-8)
    ratio = ratio.clamp(0.0, 1.0)
    steps = ns_min + (ns_max - ns_min) * ratio
    return steps.round().long().tolist()


# ---------------------------------------------------------------------------
# Main optimizer
# ---------------------------------------------------------------------------

class WaveGradientFilter(Optimizer):
    """Cassi-native optimizer: IIR → Chakra → Resonant NS → φ-fusion.

    Args:
        params: iterable of parameters
        spine:  a CordPhysics (or compatible) instance providing
                `widths`, `fwd_theta`, `C`, and `D`
        lr:     base learning rate (default 2e-4)
        weight_decay: decoupled L2 (default 0.01)
        theta:  IIR resonance angle, radians (default π/4)
        phi_damp: IIR damping (default PHI_INV ≈ 0.618)
        b0:     IIR feedforward gain. None → auto (1 - a1 - a2)
        order:  1 or 2 (default 2)
        ns_min_steps: minimum NS iterations per band (default 3)
        ns_max_steps: maximum NS iterations per band (default 6)
        ns_skip_width: skip NS for bands wider than this, use IIR only (default 4096)
        use_resonant_ns: if True, step count follows spine.fwd_theta;
                         if False, uses fixed ns_max_steps for all bands.
    """

    def __init__(self, params, spine, lr=2e-4, weight_decay=0.01,
                 theta=math.pi / 4.0, phi_damp=PHI_INV, b0=None,
                 order=2, ns_min_steps=3, ns_max_steps=6,
                 ns_skip_width=4096, use_resonant_ns=True):
        if lr < 0.0:
            raise ValueError(f"Invalid lr: {lr}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay: {weight_decay}")
        if not (0.0 < phi_damp < 1.0):
            raise ValueError(f"phi_damp must be in (0,1), got {phi_damp}")
        if order not in (1, 2):
            raise ValueError(f"order must be 1 or 2, got {order}")
        theta = float(theta)
        theta = max(0.05, min(math.pi - 0.05, theta))

        # IIR coefficient pre-computation (same logic as ResonantIIR)
        if order == 2:
            a1_tmp = 2.0 * phi_damp * math.cos(theta)
            a2_tmp = -(phi_damp ** 2)
            if b0 is None:
                b0 = max(1.0 - a1_tmp - a2_tmp, 1e-3)
            else:
                b0 = float(b0)
                if b0 <= 0:
                    raise ValueError(f"b0 must be positive, got {b0}")
        else:
            a1_tmp = phi_damp
            a2_tmp = 0.0
            if b0 is None:
                b0 = 1.0 - phi_damp
            else:
                b0 = float(b0)
                if b0 <= 0:
                    raise ValueError(f"b0 must be positive, got {b0}")

        defaults = dict(
            lr=lr, weight_decay=weight_decay,
            theta=theta, phi_damp=phi_damp, b0=b0,
            order=int(order),
            ns_min_steps=int(ns_min_steps),
            ns_max_steps=int(ns_max_steps),
            ns_skip_width=int(ns_skip_width),
            use_resonant_ns=bool(use_resonant_ns),
        )
        super().__init__(params, defaults)

        # Cache spine geometry (static for a given model)
        self._spine_D = int(spine.D)
        self._widths = list(spine.widths)
        self._offsets = _compute_chakra_offsets(self._widths)
        self._C = int(spine.C)
        self._theta_max = 2.5

        # Pre-compute Yang-weighted fusion coefficients.
        # High-frequency chakras (small c) lead by φ, but we cap the
        # ratio to avoid starving low-frequency bands.
        raw = [PHI ** (self._C - 1 - c) for c in range(self._C)]
        total = sum(raw)
        self._yang_weights = torch.tensor([r / total for r in raw])
        self._yang_weights_dev = None  # lazily cached on first use

        # Caches for dynamic theta reads
        self._cached_theta = None
        self._cached_ns_steps = None
        self._step_counter = 0
        self._spine_ref = None

    # -------------------------------------------------------------------
    # Dynamic spine-frequency cache
    # -------------------------------------------------------------------
    def _refresh_theta_cache(self, spine):
        """Re-read learned fwd_theta from spine (cheap: 13 scalars)."""
        with torch.no_grad():
            theta_vals = torch.sigmoid(spine.fwd_theta) * math.pi
        self._cached_theta = theta_vals.detach().cpu()
        self._cached_ns_steps = _theta_to_ns_steps(
            self._cached_theta, self._theta_max,
            self.defaults['ns_min_steps'],
            self.defaults['ns_max_steps'],
        )

    # -------------------------------------------------------------------
    # Core step
    # -------------------------------------------------------------------
    @torch.no_grad()
    def step(self, closure=None, neuro_modulation=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        neuro = neuro_modulation or {}
        lr_scale = float(neuro.get('lr_scale', 1.0))
        theta_shift = float(neuro.get('theta_shift', 0.0))
        reset_state = bool(neuro.get('reset_state', False))

        spine = self._spine_ref
        if spine is not None:
            if self._step_counter % 100 == 0 or self._cached_ns_steps is None:
                self._refresh_theta_cache(spine)
        self._step_counter += 1

        ns_steps_list = self._cached_ns_steps
        if ns_steps_list is None:
            ns_steps_list = [self.defaults['ns_max_steps']] * self._C

        for group in self.param_groups:
            lr = group['lr'] * lr_scale
            wd = group['weight_decay']
            theta = group['theta'] + theta_shift
            theta = max(0.05, min(math.pi - 0.05, theta))
            order = group['order']
            use_res_ns = group['use_resonant_ns']
            ns_min = group['ns_min_steps']
            ns_max = group['ns_max_steps']
            ns_skip = group['ns_skip_width']

            a1, a2, b0 = self._compute_coeffs({**group, 'theta': theta})

            for p in group['params']:
                if p.grad is None:
                    continue
                grad = p.grad
                if grad.is_sparse:
                    raise RuntimeError("WaveGradientFilter does not support sparse gradients")

                state = self.state[p]
                if len(state) == 0:
                    state['m_prev'] = torch.zeros_like(p)
                    if order == 2:
                        state['m_prev2'] = torch.zeros_like(p)

                m_prev = state['m_prev']
                m_prev2 = state.get('m_prev2', None)

                if reset_state:
                    m_prev.zero_()
                    if m_prev2 is not None:
                        m_prev2.zero_()

                # 1. Decoupled weight decay
                if wd != 0:
                    p.mul_(1.0 - lr * wd)

                # 2. IIR temporal filter
                if order == 2:
                    saved_m2 = m_prev2.clone(memory_format=torch.preserve_format)
                    m_filtered = m_prev2
                    m_filtered.copy_(m_prev).mul_(a1).add_(grad, alpha=b0).add_(saved_m2, alpha=a2)
                    del saved_m2
                else:
                    m_filtered = m_prev
                    m_filtered.mul_(a1).add_(grad, alpha=b0)

                # 3. Spatial orthogonalization
                if p.ndim >= 2:
                    if p.shape[0] == self._spine_D or p.shape[1] == self._spine_D:
                        update = self._chakra_orthogonalize(
                            m_filtered, ns_steps_list, use_res_ns, ns_min, ns_max, ns_skip
                        )
                    else:
                        # Non-D 2D matrix: full-matrix Muon with skip guard
                        m, n = p.shape[-2], p.shape[-1]
                        if min(m, n) >= ns_skip:
                            update = m_filtered
                            update = update * max(1, m / n) ** 0.5
                        else:
                            update = _full_matrix_muon(m_filtered, steps=ns_max)
                else:
                    update = m_filtered

                # 4. Parameter update
                p.add_(update, alpha=-lr)

                # 5. Advance IIR history
                if order == 2:
                    state['m_prev'] = m_filtered
                    state['m_prev2'] = m_prev

        return loss

    # -------------------------------------------------------------------
    # Chakra orthogonalization kernel
    # -------------------------------------------------------------------
    def _chakra_orthogonalize(self, m_filtered, ns_steps_list, use_res_ns, ns_min, ns_max, ns_skip):
        """Split m_filtered into chakra bands, NS each band, φ-fuse back.

        Reuses m_filtered as the output buffer to avoid allocating a separate
        zero tensor every step. Bands are disjoint and cover all D elements,
        so overwriting each slice in-place is equivalent to zero+accumulate.
        """
        shape = m_filtered.shape
        D = self._spine_D

        if shape[0] == D:
            split_dim = 0
        elif shape[1] == D:
            split_dim = 1
        else:
            return m_filtered

        device = m_filtered.device
        # Lazily cache Yang weights on the target device
        if self._yang_weights_dev is None or self._yang_weights_dev.device != device:
            self._yang_weights_dev = self._yang_weights.to(device, non_blocking=True)
        weights = self._yang_weights_dev

        # Overwrite m_filtered in-place band by band
        fused = m_filtered

        for c, (start, end) in enumerate(self._offsets):
            width = end - start
            w = weights[c]

            # Extract band (from original data; fused hasn't touched this slice yet)
            if split_dim == 0:
                band = m_filtered[start:end, :]
            else:
                band = m_filtered[:, start:end]

            if band.ndim > 2:
                band = band.view(band.shape[0], -1)

            # Skip NS for very wide bands (too expensive, diminishing returns)
            if width > ns_skip:
                ns_update = band
            else:
                nsteps = ns_steps_list[c] if use_res_ns else ns_max
                ns_update = _zeropower_via_newtonschulz5(band, nsteps)

            # Apply aspect-ratio scaling (Muon compensation) consistently
            m, n = ns_update.shape[-2], ns_update.shape[-1]
            ns_update = ns_update * max(1, m / n) ** 0.5

            # Restore shape if conv
            if split_dim == 0:
                ns_update = ns_update.view(width, *shape[1:])
            else:
                ns_update = ns_update.view(shape[0], width, *shape[2:])

            # Overwrite slice with weighted update (bands are disjoint)
            if split_dim == 0:
                fused[start:end].copy_(ns_update).mul_(w)
            else:
                fused[:, start:end].copy_(ns_update).mul_(w)

        return fused

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------
    def _compute_coeffs(self, group):
        phi = group['phi_damp']
        theta = group['theta']
        if group['order'] == 2:
            a1 = 2.0 * phi * math.cos(theta)
            a2 = -(phi ** 2)
        else:
            a1 = phi
            a2 = 0.0
        b0 = group['b0']
        return a1, a2, b0

    def bind_spine(self, spine):
        """Attach a live spine reference for dynamic theta reads."""
        self._spine_ref = spine
        self._refresh_theta_cache(spine)

    def load_spine_coeffs(self, spine):
        """Couple IIR theta/b0 to spine's learned IIR params."""
        with torch.no_grad():
            theta = torch.sigmoid(spine.fwd_theta).mean().item() * math.pi
            b0 = torch.sigmoid(spine.fwd_b0).mean().item()
        for group in self.param_groups:
            group['theta'] = theta
            if group['b0'] is not None:
                group['b0'] = b0

    def reset_iir_state(self):
        """Reset all gradient IIR buffers (m_prev, m_prev2) to zero.

        Called when the brainstem triggers a pulse / neuroplasticizer reset.
        Synchronizes optimizer state with spine state reset.
        """
        for group in self.param_groups:
            order = group['order']
            for p in group['params']:
                state = self.state.get(p)
                if state is None:
                    continue
                if 'm_prev' in state:
                    state['m_prev'].zero_()
                if order == 2 and 'm_prev2' in state:
                    state['m_prev2'].zero_()
