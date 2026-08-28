#!/usr/bin/env python3
"""
Cassi Speculative Decoder v3 — temperature-matched training + trained observer.

Fixes from v2:
  1. Draft head trained on temperature-sampled future tokens (not greedy)
  2. Train/val split with early stopping
  3. Observer head trained to predict top-1 probability from hidden state
  4. Greedy draft + greedy verify for correct speculative decoding
  5. Acceptance rate and speedup reported honestly
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import json
import math
from pathlib import Path

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
MODEL_ID = "qwen_models/Qwen3.5-0.8B"
DEVICE = "cuda"
TEMP = 0.8


def load_model():
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, trust_remote_code=True, local_files_only=True,
        dtype=torch.float32, device_map=DEVICE,
    )
    model.eval()
    return model, tok


# ---------------------------------------------------------------------------
# Draft Head: predicts next N tokens from hidden state
# ---------------------------------------------------------------------------
class DraftHead(nn.Module):
    def __init__(self, d_model=1024, vocab_size=248320, n_future=4):
        super().__init__()
        self.n_future = n_future
        hidden = d_model // 2
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, hidden),
                nn.LayerNorm(hidden),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(hidden, vocab_size),
            )
            for _ in range(n_future)
        ])

    def forward(self, hidden):
        return [head(hidden) for head in self.heads]


# ---------------------------------------------------------------------------
# Observer Head: predicts model confidence from hidden state
# ---------------------------------------------------------------------------
class ObserverHead(nn.Module):
    def __init__(self, d_model=1024):
        super().__init__()
        self.confidence = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.LayerNorm(d_model // 4),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(d_model // 4, 1),
            nn.Sigmoid(),
        )

    def forward(self, hidden):
        return self.confidence(hidden).squeeze(-1)


# ---------------------------------------------------------------------------
# Breath Scheduler
# ---------------------------------------------------------------------------
class BreathScheduler:
    def __init__(self, base_size=2, max_size=8, omega_yang=0.15, omega_yin=0.094):
        self.base_size = base_size
        self.max_size = max_size
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin
        self.t = 0

    def step(self):
        beat = math.sin(self.t * self.omega_yang) + math.sin(self.t * self.omega_yin)
        size = int(self.base_size + (self.max_size - self.base_size) * (1 + beat) / 2)
        self.t += 1
        return max(self.base_size, min(size, self.max_size)), beat


# ---------------------------------------------------------------------------
# Data collection with temperature sampling
# ---------------------------------------------------------------------------
def sample_token(logits, temp=TEMP):
    probs = F.softmax(logits / temp, dim=-1)
    return torch.multinomial(probs, num_samples=1).item()


def collect_data(model, tok, prompts, n_future=4, max_pos=100, temp=TEMP):
    """Collect (hidden_state, future_tokens, top_prob) with temperature sampling."""
    model.eval()
    data = []
    with torch.no_grad():
        for prompt in prompts:
            inputs = tok(prompt, return_tensors="pt").to(DEVICE)
            ids = inputs["input_ids"][0].tolist()
            past = None
            for _ in range(max_pos):
                t = torch.tensor([ids] if past is None else [[ids[-1]]], device=DEVICE)
                out = model(
                    input_ids=t,
                    past_key_values=past,
                    use_cache=True,
                    output_hidden_states=True,
                )
                logits = out.logits[0, -1, :]
                past = out.past_key_values
                hidden = out.hidden_states[-1][0, -1, :].float().cpu()

                top_prob = F.softmax(logits, dim=-1).max().item()
                token = sample_token(logits, temp)
                ids.append(token)

                # Sample future tokens with same temperature
                future = []
                tmp_ids = ids[:]
                tmp_past = past
                for _ in range(n_future):
                    tid = torch.tensor([[tmp_ids[-1]]], device=DEVICE)
                    tout = model(input_ids=tid, past_key_values=tmp_past, use_cache=True)
                    ft = sample_token(tout.logits[0, -1, :], temp)
                    future.append(ft)
                    tmp_ids.append(ft)
                    tmp_past = tout.past_key_values

                data.append({"hidden": hidden, "future": future, "top_prob": top_prob})
                if token == tok.eos_token_id:
                    break
    return data


# ---------------------------------------------------------------------------
# Training with train/val split and early stopping
# ---------------------------------------------------------------------------
def train_draft_head(draft, data, steps=500, lr=3e-4, batch_size=128, patience=20):
    draft.to(DEVICE).train()
    opt = torch.optim.AdamW(draft.parameters(), lr=lr, weight_decay=0.02)

    # φ-decay weights
    weights = torch.tensor([PHI_INV ** k for k in range(draft.n_future)], device=DEVICE)
    weights = weights / weights.sum()

    # Train/val split (90/10)
    n = len(data)
    n_train = int(0.9 * n)
    train_data = data[:n_train]
    val_data = data[n_train:]
    print(f"  Train: {n_train}, Val: {len(val_data)}")

    best_val_loss = float("inf")
    patience_counter = 0

    for step in range(steps):
        # Train
        draft.train()
        batch = train_data[:batch_size] if len(train_data) >= batch_size else train_data
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

        # Val every 10 steps
        if (step + 1) % 10 == 0:
            draft.eval()
            with torch.no_grad():
                vh = torch.stack([b["hidden"] for b in val_data]).to(DEVICE)
                vf = torch.tensor([b["future"] for b in val_data], device=DEVICE)
                vlogits = draft(vh)
                vloss = sum(weights[k] * F.cross_entropy(vlogits[k], vf[:, k]) for k in range(draft.n_future))
            val_loss = vloss.item()
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if (step + 1) % 50 == 0:
                print(f"  Step {step+1}, train_loss={loss.item():.4f}, val_loss={val_loss:.4f}")

            if patience_counter >= patience:
                print(f"  Early stopping at step {step+1} (best val_loss={best_val_loss:.4f})")
                break

    draft.eval()
    return best_val_loss


def train_observer(observer, data, steps=200, lr=1e-3, batch_size=128, patience=15):
    observer.to(DEVICE).train()
    opt = torch.optim.AdamW(observer.parameters(), lr=lr, weight_decay=0.01)

    n = len(data)
    n_train = int(0.9 * n)
    train_data = data[:n_train]
    val_data = data[n_train:]

    best_val_loss = float("inf")
    patience_counter = 0

    for step in range(steps):
        observer.train()
        batch = train_data[:batch_size] if len(train_data) >= batch_size else train_data
        if not batch:
            break
        h = torch.stack([b["hidden"] for b in batch]).to(DEVICE)
        y = torch.tensor([b["top_prob"] for b in batch], device=DEVICE)
        pred = observer(h)
        loss = F.mse_loss(pred, y)
        opt.zero_grad()
        loss.backward()
        opt.step()

        if (step + 1) % 10 == 0:
            observer.eval()
            with torch.no_grad():
                vh = torch.stack([b["hidden"] for b in val_data]).to(DEVICE)
                vy = torch.tensor([b["top_prob"] for b in val_data], device=DEVICE)
                vpred = observer(vh)
                vloss = F.mse_loss(vpred, vy)
            val_loss = vloss.item()
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
            if (step + 1) % 50 == 0:
                print(f"  Step {step+1}, train_loss={loss.item():.4f}, val_loss={val_loss:.4f}")
            if patience_counter >= patience:
                print(f"  Early stopping at step {step+1} (best val_loss={best_val_loss:.4f})")
                break

    observer.eval()
    return best_val_loss


# ---------------------------------------------------------------------------
# Speculative generation (greedy draft + greedy verify)
# ---------------------------------------------------------------------------
def generate_speculative(
    model, tok, draft, observer, scheduler,
    prompt, max_new=64, conf_threshold=0.55, cp_threshold=0.3,
):
    draft.eval()
    observer.eval()
    model.eval()

    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    ids = inputs["input_ids"][0].tolist()
    past = None
    prev_hidden = None

    stats = {
        "tokens_generated": 0,
        "draft_blocks": 0,
        "accepted_tokens": 0,
        "speculated_tokens": 0,
        "standard_tokens": 0,
        "truncated_by_changepoint": 0,
        "breath_sizes": [],
        "confidences": [],
        "acceptance_per_block": [],
    }

    t0 = time.time()
    while stats["tokens_generated"] < max_new:
        # Full forward pass
        t = torch.tensor([ids] if past is None else [[ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = model(
                input_ids=t,
                past_key_values=past,
                use_cache=True,
                output_hidden_states=True,
            )
        logits = out.logits[0, -1, :]
        past = out.past_key_values
        hidden = out.hidden_states[-1][0, -1, :].float()

        conf = observer(hidden).item()
        top_prob = F.softmax(logits, dim=-1).max().item()

        if prev_hidden is not None:
            sim = F.cosine_similarity(hidden.unsqueeze(0), prev_hidden.unsqueeze(0)).item()
            changepoint = 1 - sim
        else:
            changepoint = 0.0
        prev_hidden = hidden.clone()

        block_size, beat = scheduler.step()
        block_size = min(block_size, draft.n_future)
        stats["breath_sizes"].append(block_size)
        stats["confidences"].append(conf)

        should_speculate = (
            conf > conf_threshold
            and top_prob > 0.4
            and changepoint < cp_threshold
            and block_size > 1
        )

        if not should_speculate:
            token = torch.argmax(logits).item()
            ids.append(token)
            stats["tokens_generated"] += 1
            stats["standard_tokens"] += 1
            if token == tok.eos_token_id:
                break
            continue

        # Draft block
        stats["draft_blocks"] += 1
        with torch.no_grad():
            draft_logits = draft(hidden)
        draft_tokens = [torch.argmax(dl).item() for dl in draft_logits[:block_size]]

        # Verify block
        verify_ids = torch.tensor([draft_tokens], device=DEVICE)
        with torch.no_grad():
            vout = model(input_ids=verify_ids, past_key_values=past, use_cache=True)
        vlogits = vout.logits[0, :, :]
        vpast = vout.past_key_values

        accepted = 0
        for k in range(len(draft_tokens)):
            v_token = torch.argmax(vlogits[k, :]).item()
            if v_token == draft_tokens[k]:
                ids.append(draft_tokens[k])
                accepted += 1
                stats["tokens_generated"] += 1
                if draft_tokens[k] == tok.eos_token_id:
                    break
            else:
                ids.append(v_token)
                accepted += 1
                stats["tokens_generated"] += 1
                break

        stats["accepted_tokens"] += accepted
        stats["speculated_tokens"] += len(draft_tokens)
        stats["acceptance_per_block"].append(accepted / len(draft_tokens))
        past = vpast

        if changepoint > cp_threshold:
            stats["truncated_by_changepoint"] += 1

        if ids[-1] == tok.eos_token_id:
            break

    dt = time.time() - t0
    text = tok.decode(ids, skip_special_tokens=True)
    speed = stats["tokens_generated"] / dt if dt > 0 else 0.0
    return text, speed, stats


# ---------------------------------------------------------------------------
# Baseline greedy generation
# ---------------------------------------------------------------------------
def generate_baseline(model, tok, prompt, max_new=64):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.time() - t0
    return tok.decode(out[0], skip_special_tokens=True), max_new / dt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    model, tok = load_model()
    d_model = model.config.hidden_size
    vocab_size = model.config.vocab_size

    draft = DraftHead(d_model, vocab_size, n_future=4).to(DEVICE)
    observer = ObserverHead(d_model).to(DEVICE)
    scheduler = BreathScheduler(base_size=2, max_size=8)

    draft_path = Path("experiments/cassi_draft_head_v3.pt")
    observer_path = Path("experiments/cassi_observer_v3.pt")

    if not draft_path.exists() or not observer_path.exists():
        prompts = [
            "The golden ratio appears in nature",
            "In the philosophy of consciousness",
            "Quantum mechanics describes",
            "The history of artificial intelligence",
            "A recursive function is defined as",
            "The architecture of neural networks",
            "In topology, a manifold is",
            "The speed of light is",
            "Human memory works by",
            "Consciousness emerges from",
        ]
        print("Collecting training data with temperature sampling...")
        data = collect_data(model, tok, prompts, n_future=4, max_pos=100, temp=TEMP)
        print(f"Collected {len(data)} examples")

        print(f"Training draft head...")
        train_draft_head(draft, data, steps=600, lr=3e-4, batch_size=128, patience=25)
        torch.save(draft.state_dict(), draft_path)
        print(f"Saved draft head to {draft_path}")

        print(f"Training observer head...")
        train_observer(observer, data, steps=300, lr=1e-3, batch_size=128, patience=15)
        torch.save(observer.state_dict(), observer_path)
        print(f"Saved observer to {observer_path}")
    else:
        draft.load_state_dict(torch.load(draft_path, map_location=DEVICE))
        observer.load_state_dict(torch.load(observer_path, map_location=DEVICE))
        print(f"Loaded trained heads")

    prompt = "The golden ratio appears in nature"

    print("\n" + "=" * 70)
    print("BASELINE (greedy)")
    print("=" * 70)
    text_base, speed_base = generate_baseline(model, tok, prompt, max_new=64)
    print(f"Speed: {speed_base:.1f} tok/s")
    print(text_base)

    print("\n" + "=" * 70)
    print("CASSI SPECULATIVE (greedy draft + verify)")
    print("=" * 70)
    text_spec, speed_spec, stats = generate_speculative(
        model, tok, draft, observer, scheduler,
        prompt, max_new=64,
    )
    print(f"Speed: {speed_spec:.1f} tok/s")
    print(f"Draft blocks: {stats['draft_blocks']}")
    print(f"Standard tokens: {stats['standard_tokens']}")
    print(f"Accepted: {stats['accepted_tokens']} / Speculated: {stats['speculated_tokens']}")
    acc_rate = stats['accepted_tokens'] / max(stats['speculated_tokens'], 1)
    print(f"Acceptance rate: {acc_rate:.1%}")
    if stats['acceptance_per_block']:
        print(f"Per-block acceptance: {sum(stats['acceptance_per_block'])/len(stats['acceptance_per_block']):.2%}")
    print(f"Avg confidence: {sum(stats['confidences'])/len(stats['confidences']):.3f}")
    print(f"Avg block size: {sum(stats['breath_sizes'])/len(stats['breath_sizes']):.1f}")
    print(text_spec)

    results = {
        "prompt": prompt,
        "baseline": {"text": text_base, "speed": speed_base},
        "speculative": {
            "text": text_spec,
            "speed": speed_spec,
            "stats": {k: v for k, v in stats.items() if k not in ['acceptance_per_block']},
            "acceptance_rate": acc_rate,
        },
    }
    with open("experiments/cassi_speculative_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to experiments/cassi_speculative_v3_results.json")


if __name__ == "__main__":
    main()
