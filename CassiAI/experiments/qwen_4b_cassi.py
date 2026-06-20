#!/usr/bin/env python3
"""
Qwen3.5-4B + Cassi components via transformers.
Runs standard, breath-modulated, observer, and soft dual-stream generation.

VRAM notes:
- 4B model in bfloat16 ≈ 9 GB weights
- KV cache for 128 tokens ≈ 0.2 GB
- Cassi modules (observer, dual-stream nets) ≈ 0.05 GB
- Total ≈ 9.3 GB → fits comfortably in 24 GB

ROCm: temperature-only sampling (top-p crashes with HSA_STATUS_ERROR_EXCEPTION).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
from transformers import AutoTokenizer, AutoConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from safetensors.torch import load_file
import time
import json
import math
import gc

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
LOCAL_MODEL_DIR = "qwen_models/Qwen3.5-4B"
MODEL_ID = "Qwen/Qwen3.5-4B"
DEVICE = "cuda"
DTYPE = torch.bfloat16

# 32 layers total → 25% / 75% split
YANG_LAYER = 8
YIN_LAYER = 24


def vram_mb():
    return torch.cuda.memory_allocated() / 1024 / 1024


def load_model():
    print(f"Loading {MODEL_ID} from {LOCAL_MODEL_DIR} ...")
    config = AutoConfig.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True)

    print("Creating model on meta device...")
    with torch.device("meta"):
        model = Qwen3_5ForConditionalGeneration(config)

    with open(os.path.join(LOCAL_MODEL_DIR, "model.safetensors.index.json")) as f:
        index = json.load(f)

    shards = sorted(set(index["weight_map"].values()))
    print(f"Loading {len(shards)} shards directly to GPU...")
    torch.cuda.empty_cache()
    print(f"Free VRAM before: {torch.cuda.mem_get_info()[0]/1e9:.2f} GB")

    for shard_name in shards:
        shard_path = os.path.join(LOCAL_MODEL_DIR, shard_name)
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

    # Materialize ONLY remaining meta tensors
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

    # Mark all loaded weights as initialized
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
            hid = int(d / PHI)
            self.conf = nn.Sequential(
                nn.Linear(d, hid), nn.GELU(), nn.Linear(hid, 1), nn.Sigmoid()
            )
            self.imp = nn.Sequential(
                nn.Linear(d, hid), nn.GELU(), nn.Linear(hid, 1), nn.Sigmoid()
            )
            self.next_logits = nn.Linear(d, v, bias=False)

        def forward(self, hidden):
            return self.conf(hidden).squeeze(-1), self.imp(hidden).squeeze(-1), self.next_logits(hidden)

    d_model = model.config.text_config.hidden_size
    vocab_size = model.config.text_config.vocab_size
    observer = Observer(d_model, vocab_size).to(DEVICE).to(torch.float32).eval()

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


def dual_stream_generate(model, tok, prompt, max_new=64, K=4, yin_weight=0.15):
    """
    Soft dual-stream at the LOGIT level (no untrained hidden-state mixing).

    Yang = standard final logits (fast, local, every token).
    Yin  = running exponential average of final logits, updated every K tokens
           with PHI_INV decay (slow, global, integrated over time).

    Both streams produce valid logit distributions because they both use the
    model's trained final output. The Yin stream simply acts as a slow-moving
    bias that nudges generation toward longer-horizon coherence.
    """
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    yin_logits = None
    token_count = 0

    t0 = time.time()
    for _ in range(max_new):
        ids = torch.tensor(
            [input_ids] if past_key_values is None else [[input_ids[-1]]],
            device=DEVICE,
        )
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True)
        yang_logits = out.logits[0, -1, :].float()
        past_key_values = out.past_key_values

        # Update Yin stream every K tokens (slow integration)
        if token_count % K == 0:
            if yin_logits is None:
                yin_logits = yang_logits.clone()
            else:
                # Exponential moving average with PHI-scaled momentum
                yin_logits = PHI_INV * yin_logits + (1 - PHI_INV) * yang_logits
        else:
            # Decay Yin influence between updates
            if yin_logits is not None:
                yin_logits = yin_logits * PHI_INV + yang_logits * (1 - PHI_INV) * 0.3

        if yin_logits is None:
            blended = yang_logits
        else:
            # Blend: mostly Yang (fast) + small Yin bias (slow coherence)
            blended = (1 - yin_weight) * yang_logits + yin_weight * yin_logits

        probs = F.softmax(blended / 0.8, dim=-1)
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
    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)
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

    path = "experiments/qwen_4b_cassi_results.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {path}")


if __name__ == "__main__":
    main()
