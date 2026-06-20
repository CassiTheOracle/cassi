"""
Dual-Stream Qwen3.5 — Yang/Yin Architecture with Cassi Arbitration

Implements a dual-process transformer where:
  - YANG stream: fast, local, processes every token (linear attention layers)
  - YIN stream: slow, global, processes every K tokens (full attention layers)
  - ARBITRATION: per-dimension gate learns which stream to trust per output

This is applied as a wrapper around the base QwenMinimal model.
The dual stream runs in parallel and blends at the output.
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from safetensors.torch import load_file
from qwen_minimal_forward import QwenMinimal, RMSNorm, get_rope_embeddings


PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1.0 / PHI


class CorpusCallosum(nn.Module):
    """Learned bottleneck communication between Yang and Yin streams.

    Each stream sends a compressed representation to the other.
    """

    def __init__(self, d_model: int, bottleneck_dim: Optional[int] = None):
        super().__init__()
        self.d_model = d_model
        self.bottleneck = bottleneck_dim or d_model // 4

        # Yang → compressed → Yin
        self.yang_compress = nn.Sequential(
            nn.Linear(d_model, self.bottleneck),
            nn.LayerNorm(self.bottleneck),
        )
        # Yin → compressed → Yang
        self.yin_compress = nn.Sequential(
            nn.Linear(d_model, self.bottleneck),
            nn.LayerNorm(self.bottleneck),
        )
        # Shared → Yang input
        self.yang_expand = nn.Sequential(
            nn.Linear(self.bottleneck, d_model),
            nn.LayerNorm(d_model),
        )
        # Shared → Yin input
        self.yin_expand = nn.Sequential(
            nn.Linear(self.bottleneck, d_model),
            nn.LayerNorm(d_model),
        )

    def forward(self, yang_state: torch.Tensor, yin_state: torch.Tensor):
        """Exchange compressed states.

        Returns:
            yang_input: what Yang receives from Yin
            yin_input: what Yin receives from Yang
        """
        yang_shared = self.yang_compress(yang_state)
        yin_shared = self.yin_compress(yin_state)

        # Cross: Yang hears Yin's perspective, Yin hears Yang's
        yang_input = self.yin_expand(yin_shared)
        yin_input = self.yang_expand(yang_shared)

        return yang_input, yin_input


class StreamArbitration(nn.Module):
    """Per-dimension gate: how much to trust Yang vs Yin.

    Uses four signals: yang, yin, |diff|, dot_product.
    Output: [0, 1] per dimension — 1 = full Yang, 0 = full Yin.
    """

    def __init__(self, d_model: int):
        super().__init__()
        self.d_model = d_model

        self.gate = nn.Sequential(
            nn.Linear(d_model * 4, d_model),
            nn.LayerNorm(d_model),
            nn.Sigmoid(),
        )

    def forward(self, yang_state: torch.Tensor, yin_state: torch.Tensor):
        """Compute Yang weight per dimension.

        Args:
            yang_state: [B, T, D]
            yin_state: [B, T, D]
        Returns:
            yang_weight: [B, T, D] in [0, 1]
        """
        abs_diff = (yang_state - yin_state).abs()
        dot_prod = (yang_state * yin_state).sum(dim=-1, keepdim=True)
        dot_prod = dot_prod.expand_as(yang_state)

        features = torch.cat([
            yang_state,
            yin_state,
            abs_diff,
            dot_prod,
        ], dim=-1)

        return self.gate(features)


class DualStreamQwen(nn.Module):
    """Dual-stream wrapper for QwenMinimal.

    Architecture:
      - Yang stream: processes ALL layers every token (fast, local)
      - Yin stream: processes only FULL ATTENTION layers every K tokens (slow, global)
      - Between Yin updates: state decays by PHI_INV
      - Corpus Callosum: cross-stream communication every layer
      - Arbitration: per-dimension blending at output

    The base model weights are shared between streams — this is not
    two separate models, but two processing paths through shared weights.
    """

    def __init__(self, base_model: QwenMinimal, yin_update_every: int = 4,
                 use_corpus: bool = True, use_arbitration: bool = True):
        super().__init__()
        self.base = base_model
        self.d_model = base_model.d_model
        self.n_layers = base_model.n_layers
        self.layer_types = base_model.layer_types
        self.yin_update_every = yin_update_every

        # Identify layer types
        self.yang_layer_indices = [i for i, t in enumerate(self.layer_types)
                                    if t == 'linear_attention']
        self.yin_layer_indices = [i for i, t in enumerate(self.layer_types)
                                   if t == 'full_attention']

        # Communication and arbitration
        self.use_corpus = use_corpus
        self.use_arbitration = use_arbitration

        # Get dtype from base model
        dtype = next(base_model.parameters()).dtype

        if use_corpus:
            self.corpus = CorpusCallosum(self.d_model).to(dtype=dtype)
        if use_arbitration:
            self.arbitration = StreamArbitration(self.d_model).to(dtype=dtype)

        # Yin persistent state (decays between updates)
        self.register_buffer('yin_state', torch.zeros(1, 1, self.d_model, dtype=dtype))
        self.register_buffer('yin_step_counter', torch.zeros(1, dtype=torch.long))

        # Output fusion
        self.output_norm = RMSNorm(self.d_model).to(dtype=dtype)

        # Disagreement tracking
        self.register_buffer('_disagreement_ema', torch.zeros(1, dtype=dtype))

    def _run_yang_layer(self, x: torch.Tensor, layer_idx: int,
                        corpus_input: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Run a single layer through the Yang (fast) path."""
        layer = self.base.layers[layer_idx]

        # Pre-norm
        h = layer['input_norm'](x)

        # Add corpus input if available
        if corpus_input is not None:
            h = h + corpus_input * PHI_INV

        # Attention
        attn = layer['attn']
        if hasattr(attn, 'forward'):
            # Linear attention: just run it
            attn_out = attn(h)
        else:
            attn_out = attn(h)

        x = x + attn_out

        # MLP
        h = layer['post_norm'](x)
        x = x + layer['mlp'](h)

        return x

    def _run_yin_layer(self, x: torch.Tensor, layer_idx: int,
                       cos=None, sin=None, mask=None,
                       corpus_input: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Run a single layer through the Yin (slow) path."""
        layer = self.base.layers[layer_idx]

        # Pre-norm
        h = layer['input_norm'](x)

        # Add corpus input if available
        if corpus_input is not None:
            h = h + corpus_input * PHI_INV

        # Attention (full attention with RoPE)
        attn = layer['attn']
        if hasattr(attn, 'forward'):
            attn_out = attn(h, cos=cos, sin=sin, mask=mask)
        else:
            attn_out = attn(h)

        x = x + attn_out

        # MLP
        h = layer['post_norm'](x)
        x = x + layer['mlp'](h)

        return x

    def forward(self, input_ids: torch.Tensor, return_both: bool = False):
        """Dual-stream forward pass.

        Args:
            input_ids: [B, T] token indices
            return_both: if True, return both streams' outputs
        Returns:
            blended: [B, T, D] or (blended, yang_out, yin_out)
        """
        B, T = input_ids.shape
        device = input_ids.device
        dtype = next(self.base.parameters()).dtype

        # Embed
        yang_x = self.base.embed_tokens(input_ids)
        yin_x = yang_x.clone()

        # RoPE for Yin full attention
        cos, sin = get_rope_embeddings(T, 256, device=device, dtype=dtype)
        causal_mask = torch.triu(torch.ones(T, T, device=device, dtype=torch.bool), diagonal=1)

        # Ensure yin_state is on correct device/dtype
        if self.yin_state.device != device or self.yin_state.dtype != dtype:
            self.yin_state = self.yin_state.to(device=device, dtype=dtype)

        # Process layers
        for layer_idx in range(self.n_layers):
            layer_type = self.layer_types[layer_idx]

            # Corpus Callosum communication
            yang_corpus = None
            yin_corpus = None
            if self.use_corpus:
                yang_corpus, yin_corpus = self.corpus(yang_x, yin_x)

            if layer_type == 'linear_attention':
                # Yang processes every layer
                yang_x = self._run_yang_layer(yang_x, layer_idx,
                                              corpus_input=yin_corpus)

                # Yin: decay state (no computation for linear layers)
                yin_x = yin_x * PHI_INV

            else:
                # Full attention layer: both streams process
                yang_x = self._run_yang_layer(yang_x, layer_idx,
                                              corpus_input=yin_corpus)

                # Yin updates every K steps
                self.yin_step_counter += 1
                if self.yin_step_counter.item() % self.yin_update_every == 0:
                    yin_x = self._run_yin_layer(yin_x, layer_idx,
                                                cos=cos, sin=sin, mask=causal_mask,
                                                corpus_input=yang_corpus)
                else:
                    # Decay between Yin updates
                    yin_x = yin_x * PHI_INV

        # Final norms
        yang_x = self.base.norm(yang_x)
        yin_x = self.base.norm(yin_x)

        # Arbitration
        if self.use_arbitration:
            yang_weight = self.arbitration(yang_x, yin_x)
            blended = yang_weight * yang_x + (1 - yang_weight) * yin_x
        else:
            # Simple φ-weighted blend
            blended = PHI_INV * yang_x + PHI_INV ** 2 * yin_x

        # Track disagreement
        with torch.no_grad():
            disagreement = (yang_x - yin_x).norm(dim=-1).mean()
            self._disagreement_ema = 0.95 * self._disagreement_ema + 0.05 * disagreement

        # Output projection
        logits = self.base.lm_head(blended)

        if return_both:
            return logits, yang_x, yin_x
        return logits

    def reset_yin_state(self):
        """Reset Yin persistent state (call on new sequence)."""
        self.yin_state.zero_()
        self.yin_step_counter.zero_()
        self._disagreement_ema.zero_()


class DualStreamInference:
    """Inference wrapper for DualStreamQwen with Cassi components."""

    def __init__(self, dual_model: DualStreamQwen, tokenizer,
                 device: str = 'cuda'):
        self.model = dual_model
        self.tokenizer = tokenizer
        self.device = device
        self.model.to(device)
        self.model.eval()

        # Import Cassi components
        from qwen_cassi_hybrid import BreathModulatedSampler, InternalObserverHead

        self.breath = BreathModulatedSampler(temp_base=0.7, temp_range=0.3)
        self.observer = InternalObserverHead(
            d_model=dual_model.d_model,
            hidden_dim=256,
            observe_every_n_layers=4,
        ).to(device)

    @torch.no_grad()
    def generate(self, prompt_text: str, max_new_tokens: int = 50,
                 use_breath: bool = True, use_observer: bool = True,
                 return_both_streams: bool = False) -> Dict:
        """Generate text with dual-stream model.

        Args:
            prompt_text: input prompt string
            max_new_tokens: number of tokens to generate
            use_breath: enable breath-modulated sampling
            use_observer: enable confidence tracking
            return_both_streams: return Yang and Yin outputs separately
        Returns:
            dict with generated text and metadata
        """
        self.model.reset_yin_state()
        self.breath.reset()

        # Encode prompt
        input_ids = torch.tensor([self.tokenizer.encode(prompt_text)],
                                 device=self.device)

        generated_ids = input_ids.clone()
        confidence_log = []
        breath_log = []

        for step in range(max_new_tokens):
            # Forward pass
            if return_both_streams and step == max_new_tokens - 1:
                logits, yang_h, yin_h = self.model(generated_ids, return_both=True)
            else:
                logits = self.model(generated_ids)

            # Get logits for last token
            next_logits = logits[:, -1, :]

            # Observer confidence
            if use_observer:
                # Use blended hidden state
                last_hidden = logits[:, -1:, :].detach()  # proxy for hidden state
                # Actually we need the hidden state, not logits
                # For now, skip observer in dual-stream mode
                pass

            # Sample
            if use_breath:
                breath = self.breath.step()
                temp = breath['temperature']
                breath_log.append(breath)
            else:
                temp = 0.7

            probs = F.softmax(next_logits / temp, dim=-1)

            # Top-p
            sorted_probs, sorted_indices = torch.sort(probs, descending=True)
            cumsum = torch.cumsum(sorted_probs, dim=-1)
            cutoff = (cumsum > 0.9).nonzero(as_tuple=True)[1]
            if len(cutoff) > 0:
                keep = cutoff[0].item() + 1
                mask = torch.zeros_like(probs)
                mask[0, sorted_indices[0, :keep]] = 1.0
                probs = probs * mask
                probs = probs / probs.sum()

            next_token = torch.multinomial(probs, 1)
            generated_ids = torch.cat([generated_ids, next_token], dim=1)

        # Decode
        all_tokens = generated_ids[0].tolist()
        new_tokens = all_tokens[input_ids.shape[1]:]

        result = {
            'prompt': prompt_text,
            'generated': self.tokenizer.decode(new_tokens),
            'tokens': new_tokens,
            'n_tokens': len(new_tokens),
        }

        if use_breath:
            result['breath_log'] = breath_log

        if return_both_streams:
            result['yang_text'] = self.tokenizer.decode(
                torch.argmax(yang_h[0], dim=-1).tolist()
            )
            result['yin_text'] = self.tokenizer.decode(
                torch.argmax(yin_h[0], dim=-1).tolist()
            )

        return result


def demo():
    """Demo dual-stream generation."""
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}\n")

    # Load base model
    model_path = Path('/home/valerie/workspaces/cassi/qwen_models/Qwen3.5-0.8B')
    print(f"Loading model from {model_path}...")

    state_dict = load_file(str(model_path / 'model.safetensors-00001-of-00001.safetensors'))
    with open(model_path / 'config.json') as f:
        config = json.load(f)

    base_model = QwenMinimal(config, state_dict).to(device)

    # Wrap in dual stream
    print("Building dual-stream architecture...")
    dual_model = DualStreamQwen(
        base_model,
        yin_update_every=4,
        use_corpus=True,
        use_arbitration=True,
    ).to(device)

    # Load tokenizer
    from qwen_tokenizer import QwenTokenizer
    tokenizer = QwenTokenizer(str(model_path / 'tokenizer.json'))

    # Create inference wrapper
    inference = DualStreamInference(dual_model, tokenizer, device)

    # Test prompts
    prompts = [
        "The capital of France is",
        "In the future,",
        "Once upon a time",
    ]

    print("\n" + "=" * 60)
    print("DUAL-STREAM GENERATION")
    print("=" * 60)

    for prompt in prompts:
        print(f"\nPrompt: {prompt!r}")

        # Standard dual-stream
        result = inference.generate(prompt, max_new_tokens=15,
                                    use_breath=False, use_observer=False)
        print(f"  Standard: {result['generated']!r}")

        # Breath-modulated
        result = inference.generate(prompt, max_new_tokens=15,
                                    use_breath=True, use_observer=False)
        print(f"  Breath:   {result['generated']!r}")

    print("\n" + "=" * 60)
    print("Architecture summary:")
    print(f"  Yang layers: {len(dual_model.yang_layer_indices)} (linear attention)")
    print(f"  Yin layers:  {len(dual_model.yin_layer_indices)} (full attention)")
    print(f"  Yin update every: {dual_model.yin_update_every} tokens")
    print(f"  Corpus Callosum: {dual_model.use_corpus}")
    print(f"  Arbitration: {dual_model.use_arbitration}")
    print(f"  Total params: {sum(p.numel() for p in dual_model.parameters()):,}")
    print("=" * 60)


if __name__ == '__main__':
    demo()
