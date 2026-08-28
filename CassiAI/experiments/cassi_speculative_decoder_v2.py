#!/usr/bin/env python3
"""
Cassi Speculative Decoder v2 — corrected temperature handling and better training.
"""
import torch, torch.nn as nn, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time, json, math
from pathlib import Path

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
MODEL_ID = "qwen_models/Qwen3.5-0.8B"
DEVICE = "cuda"

def load():
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, trust_remote_code=True, local_files_only=True, dtype=torch.float32, device_map=DEVICE)
    model.eval()
    return model, tok

class DraftHead(nn.Module):
    def __init__(self, d_model, vocab_size, n_future=4):
        super().__init__()
        self.n_future = n_future
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.Dropout(0.1),
                nn.GELU(),
                nn.Linear(d_model // 2, vocab_size),
            )
            for _ in range(n_future)
        ])
    def forward(self, hidden):
        return [head(hidden) for head in self.heads]

class ObserverHead(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.conf = nn.Sequential(nn.Linear(d_model, d_model // 4), nn.GELU(), nn.Linear(d_model // 4, 1), nn.Sigmoid())
    def forward(self, hidden):
        return self.conf(hidden).squeeze(-1)

class BreathScheduler:
    def __init__(self, base=2, max_size=8, oy=0.15, oi=0.094):
        self.base = base
        self.max_size = max_size
        self.oy = oy
        self.oi = oi
        self.t = 0
    def step(self):
        beat = math.sin(self.t * self.oy) + math.sin(self.t * self.oi)
        size = int(self.base + (self.max_size - self.base) * (1 + beat) / 2)
        self.t += 1
        return max(self.base, min(size, self.max_size)), beat

def collect_data(model, tok, prompts, n_future=4, max_pos=80):
    data = []
    with torch.no_grad():
        for prompt in prompts:
            inputs = tok(prompt, return_tensors="pt").to(DEVICE)
            ids = inputs["input_ids"][0].tolist()
            past = None
            for _ in range(max_pos):
                t = torch.tensor([ids] if past is None else [[ids[-1]]], device=DEVICE)
                out = model(input_ids=t, past_key_values=past, use_cache=True, output_hidden_states=True)
                logits = out.logits[0, -1, :]
                past = out.past_key_values
                hidden = out.hidden_states[-1][0, -1, :].float().cpu()
                tok_id = torch.argmax(logits).item()
                ids.append(tok_id)
                # collect future greedy tokens
                future = []
                tmp_ids = ids[:]
                tmp_past = past
                for _ in range(n_future):
                    tid = torch.tensor([[tmp_ids[-1]]], device=DEVICE)
                    tout = model(input_ids=tid, past_key_values=tmp_past, use_cache=True)
                    ft = torch.argmax(tout.logits[0, -1, :]).item()
                    future.append(ft)
                    tmp_ids.append(ft)
                    tmp_past = tout.past_key_values
                data.append({"hidden": hidden, "future": future})
                if tok_id == tok.eos_token_id:
                    break
    return data

def train(draft, data, steps=300, lr=5e-4, bs=64):
    draft.to(DEVICE).train()
    opt = torch.optim.AdamW(draft.parameters(), lr=lr, weight_decay=0.01)
    weights = torch.tensor([PHI_INV ** k for k in range(draft.n_future)], device=DEVICE)
    weights = weights / weights.sum()
    losses = []
    for step in range(steps):
        batch = data[:bs] if len(data) >= bs else data
        if not batch:
            break
        h = torch.stack([b["hidden"] for b in batch]).to(DEVICE)
        f = torch.tensor([b["future"] for b in batch], device=DEVICE)
        logits = draft(h)
        loss = sum(weights[k] * F.cross_entropy(logits[k], f[:, k]) for k in range(draft.n_future))
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(draft.parameters(), 1.0)
        opt.step()
        losses.append(loss.item())
        if (step + 1) % 50 == 0:
            print(f"  step {step+1}, loss={loss.item():.4f}")
    draft.eval()
    return losses

def generate_spec(model, tok, draft, obs, sched, prompt, max_new=64, temp=0.8, conf_thr=0.35, cp_thr=0.25):
    draft.eval(); obs.eval(); model.eval()
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    ids = inputs["input_ids"][0].tolist()
    past = None
    prev_h = None
    stats = {"blocks": 0, "accepted": 0, "speculated": 0, "total": 0, "standard": 0}
    t0 = time.time()
    while stats["total"] < max_new:
        t = torch.tensor([ids] if past is None else [[ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = model(input_ids=t, past_key_values=past, use_cache=True, output_hidden_states=True)
        logits = out.logits[0, -1, :]
        past = out.past_key_values
        hidden = out.hidden_states[-1][0, -1, :].float()
        conf = obs(hidden).item()
        probs = F.softmax(logits, dim=-1)
        top_p = probs.max().item()
        if prev_h is not None:
            sim = F.cosine_similarity(hidden.unsqueeze(0), prev_h.unsqueeze(0)).item()
            cp = 1 - sim
        else:
            cp = 0.0
        prev_h = hidden.clone()
        block_size, beat = sched.step()
        speculate = (conf > conf_thr and top_p > 0.35 and cp < cp_thr and block_size > 1)
        if not speculate:
            # standard sample
            token = torch.multinomial(F.softmax(logits / temp, dim=-1), num_samples=1).item()
            ids.append(token)
            stats["total"] += 1
            stats["standard"] += 1
            if token == tok.eos_token_id:
                break
            continue
        # draft
        stats["blocks"] += 1
        with torch.no_grad():
            dlogits = draft(hidden)
        dprobs = [F.softmax(dl / temp, dim=-1) for dl in dlogits[:block_size]]
        draft_tokens = [torch.multinomial(dp, num_samples=1).item() for dp in dprobs]
        # verify
        vt = torch.tensor([draft_tokens], device=DEVICE)
        with torch.no_grad():
            vout = model(input_ids=vt, past_key_values=past, use_cache=True)
        vlogits = vout.logits[0, :, :]
        vpast = vout.past_key_values
        vprobs = [F.softmax(vlogits[k, :] / temp, dim=-1) for k in range(block_size)]
        accepted = 0
        for k in range(block_size):
            v_token = torch.multinomial(vprobs[k], num_samples=1).item()
            if v_token == draft_tokens[k]:
                ids.append(draft_tokens[k])
                accepted += 1
                stats["total"] += 1
                if draft_tokens[k] == tok.eos_token_id:
                    break
            else:
                ids.append(v_token)
                accepted += 1
                stats["total"] += 1
                break
        stats["accepted"] += accepted
        stats["speculated"] += block_size
        past = vpast
        if ids[-1] == tok.eos_token_id:
            break
    dt = time.time() - t0
    text = tok.decode(ids, skip_special_tokens=True)
    return text, stats["total"] / dt, stats

def generate_base(model, tok, prompt, max_new=64, temp=0.8):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=True, temperature=temp, top_p=0.85, pad_token_id=tok.eos_token_id)
    dt = time.time() - t0
    return tok.decode(out[0], skip_special_tokens=True), max_new / dt

def main():
    model, tok = load()
    d_model = model.config.hidden_size
    vocab = model.config.vocab_size
    draft = DraftHead(d_model, vocab, n_future=4).to(DEVICE)
    obs = ObserverHead(d_model).to(DEVICE)
    sched = BreathScheduler(base=2, max_size=8)
    draft_path = Path("experiments/cassi_draft_head_v2.pt")
    if not draft_path.exists():
        prompts = [
            "The golden ratio appears in nature",
            "In the philosophy of consciousness",
            "Quantum mechanics describes",
            "The history of artificial intelligence",
            "A recursive function is defined as",
            "The architecture of neural networks",
            "In topology, a manifold is",
            "The speed of light is",
        ]
        data = collect_data(model, tok, prompts, n_future=4, max_pos=80)
        print(f"Collected {len(data)} examples")
        losses = train(draft, data, steps=400, lr=5e-4, bs=128)
        torch.save(draft.state_dict(), draft_path)
        print(f"Saved to {draft_path}")
    else:
        draft.load_state_dict(torch.load(draft_path, map_location=DEVICE))
        print(f"Loaded from {draft_path}")

    prompt = "The golden ratio appears in nature"
    print("\n" + "=" * 70)
    print("BASELINE")
    print("=" * 70)
    t1, s1 = generate_base(model, tok, prompt, max_new=64, temp=0.8)
    print(f"Speed: {s1:.1f} tok/s")
    print(t1)

    print("\n" + "=" * 70)
    print("CASSI SPECULATIVE")
    print("=" * 70)
    t2, s2, stats = generate_spec(model, tok, draft, obs, sched, prompt, max_new=64, temp=0.8)
    print(f"Speed: {s2:.1f} tok/s")
    print(f"Blocks: {stats['blocks']}, Accepted: {stats['accepted']}, Speculated: {stats['speculated']}, Standard: {stats['standard']}")
    acc_rate = stats['accepted'] / max(stats['speculated'], 1)
    print(f"Acceptance rate: {acc_rate:.1%}")
    print(t2)

    with open("experiments/cassi_speculative_v2_results.json", "w") as f:
        json.dump({"baseline": {"text": t1, "speed": s1}, "speculative": {"text": t2, "speed": s2, "stats": stats, "acceptance_rate": acc_rate}}, f, indent=2)

if __name__ == "__main__":
    main()
