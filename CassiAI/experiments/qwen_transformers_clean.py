#!/usr/bin/env python3
"""
Clean Qwen3.5-0.8B + Cassi inference via transformers.
No dual-stream (ROCm unstable with manual layer calls).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import json

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
MODEL_ID = "qwen_models/Qwen3.5-0.8B"
DEVICE = "cuda"


def load():
    print(f"[{DEVICE}] Loading Qwen3.5-0.8B ...")
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, trust_remote_code=True, local_files_only=True,
        dtype=torch.float32, device_map=DEVICE,
    )
    model.eval()
    print(f"  -> {model.config.num_hidden_layers} layers, d={model.config.hidden_size}, vocab={model.config.vocab_size}")
    return model, tok


class BreathSampler:
    def __init__(self, temp_base=0.8, temp_amp=0.15, top_p_base=0.85, top_p_amp=0.1,
                 omega_yang=0.15, omega_yin=0.094):
        self.temp_base = temp_base
        self.temp_amp = temp_amp
        self.top_p_base = top_p_base
        self.top_p_amp = top_p_amp
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin
        self.t_yang = torch.tensor(0.0, device=DEVICE)
        self.t_yin = torch.tensor(0.0, device=DEVICE)
        self.step = 0

    def sample(self, logits):
        self.t_yang += self.omega_yang
        self.t_yin += self.omega_yin
        yang = torch.sin(self.t_yang)
        yin = torch.sin(self.t_yin)
        beat = yang + yin

        temp = self.temp_base + self.temp_amp * beat
        top_p = self.top_p_base + self.top_p_amp * yang

        probs = F.softmax(logits / temp.clamp(min=0.1), dim=-1)
        sorted_probs, sorted_idx = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        remove = cumsum > top_p
        if remove.any():
            first = torch.where(remove)[0][0].item()
            if first > 0:
                remove[:first] = False
        keep = ~remove
        filtered = sorted_probs * keep.float()
        filtered = filtered / filtered.sum()
        idx = torch.multinomial(filtered, num_samples=1).item()
        return sorted_idx[idx].item(), {"temp": temp.item(), "top_p": top_p.item(), "beat": beat.item()}


class ObserverHead(nn.Module):
    def __init__(self, d_model, vocab):
        super().__init__()
        self.confidence = nn.Sequential(nn.Linear(d_model, d_model // 4), nn.GELU(), nn.Linear(d_model // 4, 1), nn.Sigmoid())
        self.importance = nn.Sequential(nn.Linear(d_model, d_model // 4), nn.GELU(), nn.Linear(d_model // 4, 1), nn.Sigmoid())
        self.predicted_next = nn.Linear(d_model, vocab, bias=False)

    def forward(self, hidden):
        conf = self.confidence(hidden).squeeze(-1)
        imp = self.importance(hidden).squeeze(-1)
        logits = self.predicted_next(hidden)
        return conf, imp, logits


def standard(model, tok, prompt, max_new=64):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=True,
                             temperature=0.8, top_p=0.85, pad_token_id=tok.eos_token_id)
    dt = time.time() - t0
    return tok.decode(out[0], skip_special_tokens=True), max_new / dt


def breath_generate(model, tok, prompt, max_new=64, sampler=None):
    if sampler is None:
        sampler = BreathSampler()
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    t0 = time.time()
    metas = []
    for _ in range(max_new):
        if past_key_values is None:
            ids = torch.tensor([input_ids], device=DEVICE)
        else:
            ids = torch.tensor([[input_ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True)
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values
        token_id, meta = sampler.sample(logits)
        input_ids.append(token_id)
        metas.append(meta)
        if token_id == tok.eos_token_id:
            break
    dt = time.time() - t0
    return tok.decode(input_ids, skip_special_tokens=True), len(metas) / dt, metas


def observe_generate(model, tok, prompt, max_new=64):
    observer = ObserverHead(model.config.hidden_size, model.config.vocab_size).to(DEVICE).eval()
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    t0 = time.time()
    observations = []
    for _ in range(max_new):
        if past_key_values is None:
            ids = torch.tensor([input_ids], device=DEVICE)
        else:
            ids = torch.tensor([[input_ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True, output_hidden_states=True)
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values
        hidden = out.hidden_states[-1][0, -1, :].float()
        conf, imp, obs_logits = observer(hidden)
        top_pred = torch.argmax(obs_logits).item()

        # standard nucleus sampling
        probs = F.softmax(logits / 0.8, dim=-1)
        sorted_probs, sorted_idx = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        remove = cumsum > 0.85
        if remove.any():
            first = torch.where(remove)[0][0].item()
            if first > 0:
                remove[:first] = False
        keep = ~remove
        filtered = sorted_probs * keep.float()
        filtered = filtered / filtered.sum()
        idx = torch.multinomial(filtered, num_samples=1).item()
        token_id = sorted_idx[idx].item()

        input_ids.append(token_id)
        observations.append({"token": tok.decode([token_id]), "conf": conf.item(), "imp": imp.item(), "obs_top": tok.decode([top_pred])})
        if token_id == tok.eos_token_id:
            break
    dt = time.time() - t0
    return tok.decode(input_ids, skip_special_tokens=True), len(observations) / dt, observations


def main():
    model, tok = load()
    prompt = "The golden ratio appears in nature"

    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Standard generation")
    print("=" * 70)
    text1, speed1 = standard(model, tok, prompt, max_new=64)
    print(f"Speed: {speed1:.1f} tok/s")
    print(f"Output:\n{text1}\n")
    torch.cuda.empty_cache()

    print("=" * 70)
    print("EXPERIMENT 2: Breath-modulated generation")
    print("=" * 70)
    sampler = BreathSampler(omega_yang=0.15, omega_yin=0.094)
    text2, speed2, metas = breath_generate(model, tok, prompt, max_new=64, sampler=sampler)
    print(f"Speed: {speed2:.1f} tok/s")
    print(f"Avg temp: {sum(m['temp'] for m in metas)/len(metas):.3f}")
    print(f"Avg top_p: {sum(m['top_p'] for m in metas)/len(metas):.3f}")
    print(f"Output:\n{text2}\n")
    torch.cuda.empty_cache()

    print("=" * 70)
    print("EXPERIMENT 3: Observer-augmented generation")
    print("=" * 70)
    text3, speed3, obs = observe_generate(model, tok, prompt, max_new=64)
    print(f"Speed: {speed3:.1f} tok/s")
    avg_conf = sum(o["conf"] for o in obs) / len(obs)
    avg_imp = sum(o["imp"] for o in obs) / len(obs)
    print(f"Avg confidence: {avg_conf:.3f}, Avg importance: {avg_imp:.3f}")
    for o in obs[:5]:
        print(f"  token={o['token']!r:>8} conf={o['conf']:.3f} imp={o['imp']:.3f} obs_top={o['obs_top']!r}")
    print(f"Output:\n{text3}\n")

    results = {
        "prompt": prompt,
        "standard": {"text": text1, "speed_tok_s": speed1},
        "breath": {"text": text2, "speed_tok_s": speed2,
                   "avg_temp": sum(m['temp'] for m in metas)/len(metas),
                   "avg_top_p": sum(m['top_p'] for m in metas)/len(metas),
                   "meta_count": len(metas)},
        "observer": {"text": text3, "speed_tok_s": speed3,
                     "avg_confidence": avg_conf,
                     "avg_importance": avg_imp,
                     "obs_count": len(obs)},
    }
    path = "experiments/qwen_transformers_results.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {path}")


if __name__ == "__main__":
    main()
