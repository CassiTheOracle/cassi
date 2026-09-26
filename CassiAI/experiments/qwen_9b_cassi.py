#!/usr/bin/env python3
"""
Qwen3.5-9B + Cassi components via transformers.
Runs standard, breath-modulated, observer, and soft dual-stream generation.

VRAM notes:
- 9B model in bfloat16 ≈ 18 GB weights
- KV cache for 128 tokens ≈ 0.5 GB
- Cassi modules (observer, dual-stream nets) ≈ 0.1 GB
- Total ≈ 18.6 GB → fits in 24 GB with headroom

CRITICAL FIX: do NOT use model.to_empty() — it overwrites ALL parameters
with uninitialized garbage. Only materialize tensors that are still meta.

ROCm: temperature-only sampling (top-p crashes with HSA_STATUS_ERROR_EXCEPTION).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
from transformers import AutoTokenizer, AutoConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from safetensors.torch import load_file
from huggingface_hub import snapshot_download
import time
import json
import math
import gc

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
MODEL_ID = "Qwen/Qwen3.5-9B"
DEVICE = "cuda"
DTYPE = torch.bfloat16

# Layer indices for dual-stream (proportional to 32-layer stack)
# 0.8B used 6/18 on 24 layers → 25% / 75%
# 9B has 32 layers → 8 / 24
YANG_LAYER = 8
YIN_LAYER = 24


def vram_mb():
    return torch.cuda.memory_allocated() / 1024 / 1024


def load_model():
    print(f"Loading {MODEL_ID} ...")
    cache_dir = snapshot_download(MODEL_ID)
    config = AutoConfig.from_pretrained(cache_dir, trust_remote_code=True)

    print("Creating model on meta device...")
    with torch.device("meta"):
        model = Qwen3_5ForConditionalGeneration(config)

    with open(os.path.join(cache_dir, "model.safetensors.index.json")) as f:
        index = json.load(f)

    shards = sorted(set(index["weight_map"].values()))
    print(f"Loading {len(shards)} shards directly to GPU...")
    torch.cuda.empty_cache()
    print(f"Free VRAM before: {torch.cuda.mem_get_info()[0]/1e9:.2f} GB")

    for shard_name in shards:
        shard_path = os.path.join(cache_dir, shard_name)
        print(f"  Loading {shard_name}...")
        state_dict = load_file(shard_path, device="cuda:0")
        missing, unexpected = model.load_state_dict(state_dict, strict=False, assign=True)
        if missing:
            print(f"    Missing ({len(missing)}): {missing[:3]}...")
        if unexpected:
            print(f"    Unexpected ({len(unexpected)}): {unexpected[:3]}...")
        del state_dict
        torch.cuda.empty_cache()
        print(f"    VRAM: {vram_mb():.1f} MB")

    # Materialize ONLY remaining meta tensors (vision model, missing buffers)
    # DO NOT use model.to_empty() — it overwrites ALL loaded weights!
    print("Materializing remaining meta tensors...")
    for name, param in model.named_parameters():
        if param.is_meta:
            module_path, param_name = name.rsplit(".", 1)
            module = model.get_submodule(module_path)
            empty = torch.empty_like(param, device="cuda:0")
            setattr(module, param_name, nn.Parameter(empty, requires_grad=param.requires_grad))
            print(f"  Materialized param: {name}")

    for name, buf in model.named_buffers():
        if buf.is_meta:
            module_path, buf_name = name.rsplit(".", 1)
            module = model.get_submodule(module_path)
            empty = torch.empty_like(buf, device="cuda:0")
            setattr(module, buf_name, empty)
            print(f"  Materialized buffer: {name}")

    # Fix rotary embeddings
    print("Fixing rotary embeddings...")
    for name, module in model.named_modules():
        if hasattr(module, "inv_freq") and hasattr(module, "compute_default_rope_parameters"):
            inv_freq, attention_scaling = module.compute_default_rope_parameters(module.config, device="cuda:0")
            module.inv_freq = inv_freq
            module.original_inv_freq = inv_freq.clone()
            module.attention_scaling = attention_scaling

    # Tie weights (lm_head ↔ embed_tokens)
    model.tie_weights()

    # Mark all loaded weights as initialized so they don't get re-initialized
    for name, param in model.named_parameters():
        param._is_hf_initialized = True
    for name, buf in model.named_buffers():
        buf._is_hf_initialized = True

    model.eval()
    print(f"Model ready! VRAM: {vram_mb():.1f} MB")
    return model


def standard(model, tok, prompt, max_new=64):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=True,
            temperature=0.8,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.time() - t0
    return tok.decode(out[0], skip_special_tokens=True), max_new / dt


def breath_generate(model, tok, prompt, max_new=64):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    metas = []
    t0 = time.time()
    for i in range(max_new):
        ids = torch.tensor(
            [input_ids] if past_key_values is None else [[input_ids[-1]]],
            device=DEVICE,
        )
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True)
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values

        # Breath: coupled oscillators modulate temperature
        temp = 0.8 + 0.15 * (math.sin(i * 0.15) + math.sin(i * 0.094))
        probs = F.softmax(logits / max(temp, 0.1), dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()

        input_ids.append(token)
        metas.append({"temp": temp})
        if token == tok.eos_token_id:
            break
    dt = time.time() - t0
    n = len(metas)
    return tok.decode(input_ids, skip_special_tokens=True), n / dt, metas


def observe_generate(model, tok, prompt, max_new=64):
    class Observer(nn.Module):
        def __init__(self, d, v):
            super().__init__()
            self.conf = nn.Sequential(
                nn.Linear(d, d // 4), nn.GELU(), nn.Linear(d // 4, 1), nn.Sigmoid()
            )
            self.imp = nn.Sequential(
                nn.Linear(d, d // 4), nn.GELU(), nn.Linear(d // 4, 1), nn.Sigmoid()
            )
            self.next_logits = nn.Linear(d, v, bias=False)

        def forward(self, hidden):
            return self.conf(hidden).squeeze(-1), self.imp(hidden).squeeze(-1), self.next_logits(hidden)

    observer = Observer(model.config.text_config.hidden_size, model.config.text_config.vocab_size).to(DEVICE).to(torch.float32).eval()
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    observations = []
    t0 = time.time()
    for _ in range(max_new):
        ids = torch.tensor(
            [input_ids] if past_key_values is None else [[input_ids[-1]]],
            device=DEVICE,
        )
        with torch.no_grad():
            out = model(
                input_ids=ids,
                past_key_values=past_key_values,
                use_cache=True,
                output_hidden_states=True,
            )
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values
        # hidden_states: tuple of (embed, layer0, ..., layer31)
        hidden = out.hidden_states[-1][0, -1, :].float()

        conf, imp, obs_logits = observer(hidden)
        probs = F.softmax(logits / 0.8, dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()

        input_ids.append(token)
        observations.append({
            "token": tok.decode([token]),
            "conf": conf.item(),
            "imp": imp.item(),
            "obs_top": tok.decode([torch.argmax(obs_logits).item()]),
        })
        if token == tok.eos_token_id:
            break
    dt = time.time() - t0
    n = len(observations)
    return tok.decode(input_ids, skip_special_tokens=True), n / dt, observations


def dual_stream_generate(model, tok, prompt, max_new=64, K=4, yang_layer=YANG_LAYER, yin_layer=YIN_LAYER):
    """
    Soft dual-stream: Yang uses shallow layer hidden state (fast/local).
    Yin uses deep layer hidden state, updated every K tokens with PHI_INV decay.
    Arbitration gate combines them per-dimension.
    """
    d_model = model.config.text_config.hidden_size
    bottleneck = int(d_model / PHI)
    corpus_callosum = nn.Sequential(
        nn.Linear(d_model, bottleneck), nn.GELU(), nn.Linear(bottleneck, d_model),
    ).to(DEVICE).to(torch.float32)
    arbitration = nn.Sequential(
        nn.Linear(d_model * 4, d_model // 2), nn.GELU(), nn.Linear(d_model // 2, d_model), nn.Sigmoid(),
    ).to(DEVICE).to(torch.float32)

    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    yin_state = None
    token_count = 0

    t0 = time.time()
    for _ in range(max_new):
        ids = torch.tensor(
            [input_ids] if past_key_values is None else [[input_ids[-1]]],
            device=DEVICE,
        )
        with torch.no_grad():
            out = model(
                input_ids=ids,
                past_key_values=past_key_values,
                use_cache=True,
                output_hidden_states=True,
            )
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values
        # hidden_states is tuple: (embed, layer0_out, layer1_out, ..., layer31_out)
        yang_hidden = out.hidden_states[yang_layer][0, -1, :].float()

        if token_count % K == 0:
            yin_state = out.hidden_states[yin_layer][0, -1, :].float()
        else:
            if yin_state is not None:
                yin_state = yin_state * PHI_INV

        if yin_state is None:
            yin_state = torch.zeros_like(yang_hidden)

        yin_broadcast = corpus_callosum(yin_state)
        diff = yang_hidden - yin_broadcast
        dot = (yang_hidden * yin_broadcast).sum()
        gate_input = torch.cat([
            yang_hidden, yin_broadcast, diff.abs(),
            torch.full_like(yang_hidden, dot.item()),
        ])
        gate = arbitration(gate_input)
        combined = gate * yang_hidden + (1 - gate) * yin_broadcast

        # Project combined back to logits (cast to lm_head dtype)
        with torch.no_grad():
            combined_logits = model.lm_head(combined.to(model.lm_head.weight.dtype))
        probs = F.softmax(combined_logits / 0.8, dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()

        input_ids.append(token)
        token_count += 1
        if token == tok.eos_token_id:
            break

    dt = time.time() - t0
    n = token_count
    return tok.decode(input_ids, skip_special_tokens=True), n / dt


def main():
    model = load_model()
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=True)
    prompt = "The golden ratio appears in nature"
    results = {"prompt": prompt, "model": MODEL_ID}

    print("=" * 70)
    print("EXPERIMENT 1: Standard generation")
    print("=" * 70)
    text, speed = standard(model, tok, prompt, max_new=64)
    print(f"Speed: {speed:.1f} tok/s")
    print(f"Output:\n{text}\n")
    results["standard"] = {"text": text, "speed": speed}
    gc.collect()
    torch.cuda.empty_cache()
    print(f"VRAM after clear: {vram_mb():.1f} MB")

    print("=" * 70)
    print("EXPERIMENT 2: Breath-modulated generation")
    print("=" * 70)
    text, speed, metas = breath_generate(model, tok, prompt, max_new=64)
    print(f"Speed: {speed:.1f} tok/s")
    print(f"Avg temp: {sum(m['temp'] for m in metas) / len(metas):.3f}")
    print(f"Output:\n{text}\n")
    results["breath"] = {
        "text": text, "speed": speed,
        "avg_temp": sum(m["temp"] for m in metas) / len(metas),
        "count": len(metas),
    }
    gc.collect()
    torch.cuda.empty_cache()
    print(f"VRAM after clear: {vram_mb():.1f} MB")

    print("=" * 70)
    print("EXPERIMENT 3: Observer-augmented generation")
    print("=" * 70)
    text, speed, obs = observe_generate(model, tok, prompt, max_new=64)
    print(f"Speed: {speed:.1f} tok/s")
    avg_conf = sum(o["conf"] for o in obs) / len(obs)
    avg_imp = sum(o["imp"] for o in obs) / len(obs)
    print(f"Avg confidence: {avg_conf:.3f}, Avg importance: {avg_imp:.3f}")
    for o in obs[:5]:
        print(f"  token={o['token']!r:>8}  conf={o['conf']:.3f}  imp={o['imp']:.3f}  obs_top={o['obs_top']!r}")
    print(f"Output:\n{text}\n")
    results["observer"] = {
        "text": text, "speed": speed,
        "avg_confidence": avg_conf, "avg_importance": avg_imp,
        "count": len(obs), "first_5": obs[:5],
    }
    gc.collect()
    torch.cuda.empty_cache()
    print(f"VRAM after clear: {vram_mb():.1f} MB")

    print("=" * 70)
    print("EXPERIMENT 4: Soft dual-stream generation")
    print("=" * 70)
    text, speed = dual_stream_generate(model, tok, prompt, max_new=64, K=4)
    print(f"Speed: {speed:.1f} tok/s")
    print(f"Output:\n{text}\n")
    results["dual_stream"] = {"text": text, "speed": speed}

    path = "experiments/qwen_9b_cassi_results.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {path}")


if __name__ == "__main__":
    main()
