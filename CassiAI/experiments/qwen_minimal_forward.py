"""
Minimal Qwen3.5-0.8B forward pass — no transformers dependency.

Implements just the text model:
  - Token embedding
  - 24 layers: linear_attention (Mamba-like) or full_attention (GQA)
  - RMSNorm
  - SwiGLU MLP
  - Output projection (tied with embedding)

Then integrates Cassi inference components:
  - BreathModulatedSampler for temperature/top-p
  - InternalObserverHead for confidence per token
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from safetensors.torch import load_file

# Import Cassi components
from qwen_cassi_hybrid import BreathModulatedSampler, InternalObserverHead


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps) * self.weight


def rotate_half(x):
    """Rotary embedding: rotate half the dimensions."""
    x1, x2 = x.chunk(2, dim=-1)
    return torch.cat([-x2, x1], dim=-1)


def apply_rotary_pos_emb(q, k, cos, sin):
    """Apply rotary positional embeddings to q and k."""
    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)
    return q_embed, k_embed


def get_rope_embeddings(seq_len, head_dim, theta=10000.0, device='cuda', dtype=torch.bfloat16):
    """Generate RoPE cos/sin for a sequence."""
    inv_freq = 1.0 / (theta ** (torch.arange(0, head_dim, 2, device=device).float() / head_dim))
    t = torch.arange(seq_len, device=device)
    freqs = torch.outer(t, inv_freq)
    emb = torch.cat([freqs, freqs], dim=-1)
    cos = emb.cos()[None, None, :, :].to(dtype)
    sin = emb.sin()[None, None, :, :].to(dtype)
    return cos, sin


# ---------------------------------------------------------------------------
# Attention Modules
# ---------------------------------------------------------------------------

class LinearAttention(nn.Module):
    """Mamba-like linear attention / SSM layer.

    Simplified implementation based on Qwen3.5's linear_attn structure:
      - in_proj_qkv: projects input to Q, K, V
      - in_proj_a, in_proj_b: SSM parameters
      - in_proj_z: gating
      - conv1d: short temporal convolution
      - A_log, dt_bias: SSM state transition
      - out_proj: output projection
    """

    def __init__(self, config, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.d_model = config['hidden_size']
        self.d_conv = config.get('linear_conv_kernel_dim', 4)
        self.d_inner = 2048  # from in_proj_z weight shape [2048, 1024]
        self.n_heads = config.get('linear_num_key_heads', 16)
        self.d_head = config.get('linear_key_head_dim', 128)
        self.d_state = 16  # from A_log shape

        # Projections
        self.in_proj_qkv = nn.Linear(self.d_model, 6144, bias=False)
        self.in_proj_a = nn.Linear(self.d_model, 16, bias=False)
        self.in_proj_b = nn.Linear(self.d_model, 16, bias=False)
        self.in_proj_z = nn.Linear(self.d_model, 2048, bias=False)

        # Conv1d for short-range dependencies
        self.conv1d = nn.Conv1d(6144, 6144, kernel_size=self.d_conv,
                                groups=6144, padding=self.d_conv - 1)

        # SSM parameters
        self.A_log = nn.Parameter(torch.zeros(self.n_heads))
        self.dt_bias = nn.Parameter(torch.zeros(self.n_heads))

        # Norm
        self.norm = RMSNorm(128)  # operates on a subset

        # Output
        self.out_proj = nn.Linear(2048, self.d_model, bias=False)

    def forward(self, x):
        """x: [batch, seq, d_model]"""
        B, T, D = x.shape

        # Projections
        qkv = self.in_proj_qkv(x)  # [B, T, 6144]
        z = self.in_proj_z(x)  # [B, T, 2048]

        # Conv1d
        qkv = qkv.transpose(1, 2)  # [B, 6144, T]
        qkv = self.conv1d(qkv)[:, :, :T]  # [B, 6144, T]
        qkv = qkv.transpose(1, 2)  # [B, T, 6144]

        # Split into Q, K, V
        # 6144 = 3 * 2048, but we need to map to heads
        # Simplified: treat as combined and project
        # In reality this is more complex; we'll do a simplified pass
        q, k, v = qkv.chunk(3, dim=-1)  # each [B, T, 2048]

        # Simplified linear attention: causal aggregation
        # For a proper Mamba implementation we'd use selective scan
        # Here we do a simplified causal linear attention
        k_cumsum = torch.cumsum(k, dim=1)
        v_cumsum = torch.cumsum(v, dim=1)

        # Gating
        z_gate = F.silu(z)

        # Combine
        out = self.out_proj(z_gate * v_cumsum[:, :, :self.out_proj.in_features])

        return out


class FullAttention(nn.Module):
    """Grouped Query Attention with RoPE.

    Qwen3.5 uses:
      - 8 attention heads
      - 2 KV heads (GQA)
      - head_dim = 256
      - q/k_norm for stability
    """

    def __init__(self, config, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx
        self.d_model = config['hidden_size']
        self.n_heads = config['num_attention_heads']
        self.n_kv_heads = config['num_key_value_heads']
        self.head_dim = config['head_dim']
        self.n_rep = self.n_heads // self.n_kv_heads

        self.q_proj = nn.Linear(self.d_model, self.n_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(self.d_model, self.n_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(self.d_model, self.n_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(self.n_heads * self.head_dim, self.d_model, bias=False)

        self.q_norm = RMSNorm(self.head_dim)
        self.k_norm = RMSNorm(self.head_dim)

    def forward(self, x, cos=None, sin=None, mask=None):
        """x: [batch, seq, d_model]

        Qwen3.5 uses attn_output_gate=True:
        q_proj outputs [Q, gate] concatenated (4096 = 2048 + 2048).
        The gate is applied to the attention output before o_proj.
        """
        B, T, D = x.shape

        q_all = self.q_proj(x)  # [B, T, 4096] = [Q, gate]
        q = q_all[:, :, :self.n_heads * self.head_dim]  # [B, T, 2048]
        q_gate = q_all[:, :, self.n_heads * self.head_dim:]  # [B, T, 2048]

        k = self.k_proj(x)  # [B, T, 512]
        v = self.v_proj(x)  # [B, T, 512]

        # Reshape to heads
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)  # [B, 8, T, 256]
        k = k.view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)  # [B, 2, T, 256]
        v = v.view(B, T, self.n_kv_heads, self.head_dim).transpose(1, 2)  # [B, 2, T, 256]

        # Apply norm
        q = self.q_norm(q)
        k = self.k_norm(k)

        # Apply RoPE
        if cos is not None and sin is not None:
            q, k = apply_rotary_pos_emb(q, k, cos, sin)

        # Repeat KV heads (2 -> 8)
        if self.n_rep > 1:
            k = k.repeat_interleave(self.n_rep, dim=1)
            v = v.repeat_interleave(self.n_rep, dim=1)

        # Attention: Q @ K^T / sqrt(d)
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)

        # Causal mask
        if mask is None:
            mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1)
        scores = scores.masked_fill(mask[None, None, :, :], float('-inf'))

        attn = F.softmax(scores, dim=-1)
        out = torch.matmul(attn, v)  # [B, 8, T, 256]

        # Reshape
        out = out.transpose(1, 2).contiguous().view(B, T, -1)  # [B, T, 2048]

        # Apply output gate
        gate = torch.sigmoid(q_gate)
        out = out * gate

        # Project
        out = self.o_proj(out)

        return out


class SwiGLU(nn.Module):
    """SwiGLU MLP: gate_proj + up_proj + down_proj."""

    def __init__(self, config):
        super().__init__()
        self.d_model = config['hidden_size']
        self.d_intermediate = config['intermediate_size']

        self.gate_proj = nn.Linear(self.d_model, self.d_intermediate, bias=False)
        self.up_proj = nn.Linear(self.d_model, self.d_intermediate, bias=False)
        self.down_proj = nn.Linear(self.d_intermediate, self.d_model, bias=False)

    def forward(self, x):
        gate = F.silu(self.gate_proj(x))
        up = self.up_proj(x)
        return self.down_proj(gate * up)


# ---------------------------------------------------------------------------
# Full Model
# ---------------------------------------------------------------------------

class QwenMinimal(nn.Module):
    """Minimal Qwen3.5-0.8B text model."""

    def __init__(self, config: dict, state_dict: dict):
        super().__init__()
        self.config = config
        self.text_config = config['text_config']
        self.d_model = self.text_config['hidden_size']
        self.n_layers = self.text_config['num_hidden_layers']
        self.vocab_size = self.text_config['vocab_size']
        self.layer_types = self.text_config['layer_types']

        # Embedding
        self.embed_tokens = nn.Embedding(self.vocab_size, self.d_model)

        # Layers
        self.layers = nn.ModuleList()
        for i in range(self.n_layers):
            layer_type = self.layer_types[i]
            if layer_type == 'linear_attention':
                attn = LinearAttention(self.text_config, i)
            else:
                attn = FullAttention(self.text_config, i)

            mlp = SwiGLU(self.text_config)
            input_layernorm = RMSNorm(self.d_model)
            post_attention_layernorm = RMSNorm(self.d_model)

            self.layers.append(nn.ModuleDict({
                'attn': attn,
                'mlp': mlp,
                'input_norm': input_layernorm,
                'post_norm': post_attention_layernorm,
            }))

        # Final norm
        self.norm = RMSNorm(self.d_model)

        # Output projection (tied with embedding)
        self.lm_head = nn.Linear(self.d_model, self.vocab_size, bias=False)

        # Load weights
        self._load_weights(state_dict)

    def _load_weights(self, state_dict):
        """Load weights from safetensors state dict."""
        # Build a mapping from stripped keys to original keys
        text_keys = {}
        for key in list(state_dict.keys()):
            if key.startswith('model.language_model.'):
                stripped = key.replace('model.language_model.', '')
                text_keys[stripped] = key

        # Determine dtype — most weights are bfloat16, some params are float32
        # Use bfloat16 as the primary dtype
        weight_dtype = torch.bfloat16
        print(f"  Weight dtype: {weight_dtype}")

        # Cast all modules to weight dtype
        self = self.to(weight_dtype)

        # Load embedding
        embed_key = text_keys.get('embed_tokens.weight')
        if embed_key is None:
            raise KeyError("embed_tokens.weight not found. Available: " + str(list(text_keys.keys())[:10]))
        self.embed_tokens.weight.data = state_dict[embed_key].to(weight_dtype)

        # Tie lm_head
        self.lm_head.weight = self.embed_tokens.weight

        # Load layers
        for i in range(self.n_layers):
            layer = self.layers[i]
            prefix = f'layers.{i}.'

            def get(key):
                full_key = text_keys.get(key)
                if full_key is None:
                    raise KeyError(f"Key not found: {key}")
                return state_dict[full_key]

            # Norms
            layer['input_norm'].weight.data = get(f'{prefix}input_layernorm.weight')
            layer['post_norm'].weight.data = get(f'{prefix}post_attention_layernorm.weight')

            # Attention
            attn = layer['attn']
            if isinstance(attn, LinearAttention):
                attn.in_proj_qkv.weight.data = get(f'{prefix}linear_attn.in_proj_qkv.weight')
                attn.in_proj_a.weight.data = get(f'{prefix}linear_attn.in_proj_a.weight')
                attn.in_proj_b.weight.data = get(f'{prefix}linear_attn.in_proj_b.weight')
                attn.in_proj_z.weight.data = get(f'{prefix}linear_attn.in_proj_z.weight')
                attn.conv1d.weight.data = get(f'{prefix}linear_attn.conv1d.weight')
                attn.A_log.data = get(f'{prefix}linear_attn.A_log')
                attn.dt_bias.data = get(f'{prefix}linear_attn.dt_bias')
                attn.norm.weight.data = get(f'{prefix}linear_attn.norm.weight')
                attn.out_proj.weight.data = get(f'{prefix}linear_attn.out_proj.weight')
            else:
                attn.q_proj.weight.data = get(f'{prefix}self_attn.q_proj.weight')
                attn.k_proj.weight.data = get(f'{prefix}self_attn.k_proj.weight')
                attn.v_proj.weight.data = get(f'{prefix}self_attn.v_proj.weight')
                attn.o_proj.weight.data = get(f'{prefix}self_attn.o_proj.weight')
                attn.q_norm.weight.data = get(f'{prefix}self_attn.q_norm.weight')
                attn.k_norm.weight.data = get(f'{prefix}self_attn.k_norm.weight')

            # MLP
            mlp = layer['mlp']
            mlp.gate_proj.weight.data = get(f'{prefix}mlp.gate_proj.weight')
            mlp.up_proj.weight.data = get(f'{prefix}mlp.up_proj.weight')
            mlp.down_proj.weight.data = get(f'{prefix}mlp.down_proj.weight')

        # Final norm
        self.norm.weight.data = get('norm.weight')

        print(f"[QwenMinimal] Loaded {self.n_layers} layers")
        print(f"  Total params: {sum(p.numel() for p in self.parameters()):,}")

    def forward(self, input_ids: torch.Tensor, return_hidden: bool = False):
        """Forward pass.

        Args:
            input_ids: [batch, seq] token indices
            return_hidden: if True, return all hidden states for observer
        Returns:
            logits: [batch, seq, vocab_size]
            hidden_states: list of [batch, seq, d_model] if return_hidden
        """
        B, T = input_ids.shape
        device = input_ids.device

        # Embed
        x = self.embed_tokens(input_ids)  # [B, T, D]

        # RoPE for full attention layers
        cos, sin = get_rope_embeddings(T, 256, device=device, dtype=x.dtype)
        causal_mask = torch.triu(torch.ones(T, T, device=device, dtype=torch.bool), diagonal=1)

        hidden_states = []

        # Layers
        for i, layer in enumerate(self.layers):
            # Pre-norm
            h = layer['input_norm'](x)

            # Attention
            attn = layer['attn']
            if isinstance(attn, FullAttention):
                attn_out = attn(h, cos=cos, sin=sin, mask=causal_mask)
            else:
                attn_out = attn(h)

            x = x + attn_out

            # MLP
            h = layer['post_norm'](x)
            x = x + layer['mlp'](h)

            if return_hidden:
                hidden_states.append(x.clone())

        # Final norm
        x = self.norm(x)

        # Output
        logits = self.lm_head(x)

        if return_hidden:
            return logits, hidden_states
        return logits


# ---------------------------------------------------------------------------
# Cassi-Enhanced Inference
# ---------------------------------------------------------------------------

class QwenCassiInference:
    """Wraps QwenMinimal with Cassi inference enhancements."""

    def __init__(self, model: QwenMinimal, device: str = 'cuda'):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()

        # Cassi components
        self.breath = BreathModulatedSampler(
            temp_base=0.7,
            temp_range=0.3,
            top_p_base=0.9,
            top_p_range=0.1,
        )
        self.observer = InternalObserverHead(
            d_model=model.d_model,
            hidden_dim=256,
            observe_every_n_layers=4,
        ).to(device)

    @torch.no_grad()
    def generate(self, input_ids: torch.Tensor, max_new_tokens: int = 50,
                 use_breath: bool = True, use_observer: bool = True) -> Dict:
        """Generate tokens with Cassi enhancements.

        Args:
            input_ids: [batch, seq] prompt tokens
            max_new_tokens: number of tokens to generate
            use_breath: enable breath-modulated sampling
            use_observer: enable confidence tracking
        Returns:
            dict with 'tokens', 'text', 'confidence', 'breath_log'
        """
        self.breath.reset()
        generated = input_ids.clone()
        confidence_log = []
        breath_log = []

        for step in range(max_new_tokens):
            # Forward pass
            logits, hidden_states = self.model(generated, return_hidden=True)

            # Get logits for last token
            next_logits = logits[:, -1, :]  # [batch, vocab]

            # Observer: confidence on last token's hidden state
            if use_observer:
                # Observe last layer's hidden state at last position
                last_hidden = hidden_states[-1][:, -1:, :]  # [batch, 1, D]
                obs = self.observer.observe(last_hidden)
                confidence_log.append(obs['confidence'].mean().item())

            # Sample with breath modulation
            if use_breath:
                next_token, breath_info = self._sample_with_breath(next_logits[0])
                breath_log.append(breath_info)
            else:
                probs = F.softmax(next_logits[0] / 0.7, dim=-1)
                next_token = torch.multinomial(probs, 1).item()

            # Append
            next_token_tensor = torch.tensor([[next_token]], device=self.device)
            generated = torch.cat([generated, next_token_tensor], dim=1)

        return {
            'tokens': generated[0].tolist(),
            'confidence': confidence_log,
            'breath_log': breath_log,
        }

    def _sample_with_breath(self, logits: torch.Tensor) -> Tuple[int, Dict]:
        """Sample using breath-modulated temperature."""
        breath = self.breath.step()
        temp = breath['temperature']
        top_p = breath['top_p']

        # Temperature
        probs = F.softmax(logits / temp, dim=-1)

        # Top-p
        sorted_probs, sorted_indices = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        cutoff = (cumsum > top_p).nonzero(as_tuple=True)[0]
        if len(cutoff) > 0:
            keep = cutoff[0].item() + 1
            mask = torch.zeros_like(probs)
            mask[sorted_indices[:keep]] = 1.0
            probs = probs * mask
            probs = probs / probs.sum()

        token = torch.multinomial(probs, 1).item()
        return token, breath


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # Load model
    model_path = Path('C:/Users/Carina/workspaces/Cassi/CassiAI/qwen_models/Qwen3.5-0.8B')
    print(f"\nLoading model from {model_path}...")

    state_dict = load_file(str(model_path / 'model.safetensors-00001-of-00001.safetensors'))
    with open(model_path / 'config.json') as f:
        config = json.load(f)

    model = QwenMinimal(config, state_dict).to(device)

    # Create inference wrapper
    inference = QwenCassiInference(model, device)

    # Simple prompt (we don't have tokenizer, so use random tokens for structure test)
    print("\n=== Structure Test ===")
    prompt = torch.randint(0, 1000, (1, 10), device=device)

    # Standard generation
    print("\nStandard sampling:")
    result_std = inference.generate(prompt, max_new_tokens=10,
                                    use_breath=False, use_observer=False)
    print(f"  Generated {len(result_std['tokens'])} tokens")

    # Breath-modulated generation
    print("\nBreath-modulated sampling:")
    result_breath = inference.generate(prompt, max_new_tokens=10,
                                       use_breath=True, use_observer=True)
    print(f"  Generated {len(result_breath['tokens'])} tokens")
    print(f"  Confidence range: [{min(result_breath['confidence']):.3f}, "
          f"{max(result_breath['confidence']):.3f}]")
    print(f"  Temperature range: [{min(b['temperature'] for b in result_breath['breath_log']):.3f}, "
          f"{max(b['temperature'] for b in result_breath['breath_log']):.3f}]")

    print("\n=== Demo complete ===")


if __name__ == '__main__':
    demo()
