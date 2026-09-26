#!/usr/bin/env python3
"""
Cassi-inspired speculative decoding for Qwen3.5-0.8B.

Combines:
  1. Breath-guided dynamic block size (Yang = small/conservative, Yin = large/exploratory)
  2. Small draft head distilled from target model hidden states
  3. φ-decay loss weighting during draft training (earlier positions matter more)
  4. Observer confidence gating (only speculate when confident)
  5. Changepoint proxy (hidden-state cosine similarity) to truncate blocks early

Usage:
  python experiments/cassi_speculative_decoder.py --train-draft  --train-steps 200
  python experiments/cassi_speculative_decoder.py --generate --prompt "The golden ratio"
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import json
import math
import argparse
from pathlib import Path

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
MODEL_ID = "qwen_models/Qwen3.5-0.8B"
DEVICE = "cuda"


def load_model():
    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, trust_remote_code=True, local_files_only=True,
        dtype=torch.float32, device_map=DEVICE,
    )
    model.eval()
    return model, tok


# ---------------------------------------------------------------------------
# 1. Draft Head: maps hidden state -> next N token distributions
# ---------------------------------------------------------------------------
class CassiDraftHead(nn.Module):
    def __init__(self, d_model=1024, vocab_size=248320, n_future=4):
        super().__init__()
        self.n_future = n_future
        # One small head per future position
        self.heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Linear(d_model // 2, vocab_size),
            )
            for _ in range(n_future)
        ])

    def forward(self, hidden):
        """hidden: [d_model] -> list of [vocab_size] logits"""
        return [head(hidden) for head in self.heads]


# ---------------------------------------------------------------------------
# 2. Observer Head (reused from prior script)
# ---------------------------------------------------------------------------
class ObserverHead(nn.Module):
    def __init__(self, d_model=1024, vocab_size=248320):
        super().__init__()
        self.confidence = nn.Sequential(
            nn.Linear(d_model, d_model // 4), nn.GELU(), nn.Linear(d_model // 4, 1), nn.Sigmoid()
        )
        self.importance = nn.Sequential(
            nn.Linear(d_model, d_model // 4), nn.GELU(), nn.Linear(d_model // 4, 1), nn.Sigmoid()
        )

    def forward(self, hidden):
        return self.confidence(hidden).squeeze(-1), self.importance(hidden).squeeze(-1)


# ---------------------------------------------------------------------------
# 3. Breath-guided block scheduler
# ---------------------------------------------------------------------------
class BreathBlockScheduler:
    """Coupled oscillators control speculation depth."""

    def __init__(self, base_size=4, max_size=12, omega_yang=0.15, omega_yin=0.094):
        self.base_size = base_size
        self.max_size = max_size
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin
        self.t = 0

    def step(self):
        yang = math.sin(self.t * self.omega_yang)
        yin = math.sin(self.t * self.omega_yin)
        beat = yang + yin
        # Map beat to block size: Yang dominance -> small, Yin dominance -> large
        size = int(self.base_size + (self.max_size - self.base_size) * (1 + beat) / 2)
        self.t += 1
        return size, beat, yang, yin


# ---------------------------------------------------------------------------
# 4. Collect training data for draft head
# ---------------------------------------------------------------------------
def collect_training_data(model, tok, prompts, n_future=4, max_per_prompt=128):
    """For each prompt, run model and collect (hidden_state, future_tokens) pairs."""
    model.eval()
    data = []
    with torch.no_grad():
        for prompt in prompts:
            inputs = tok(prompt, return_tensors="pt").to(DEVICE)
            input_ids = inputs["input_ids"][0].tolist()
            past_key_values = None

            for pos in range(max_per_prompt):
                ids = torch.tensor(
                    [input_ids] if past_key_values is None else [[input_ids[-1]]],
                    device=DEVICE,
                )
                out = model(
                    input_ids=ids,
                    past_key_values=past_key_values,
                    use_cache=True,
                    output_hidden_states=True,
                )
                logits = out.logits[0, -1, :]
                past_key_values = out.past_key_values
                hidden = out.hidden_states[-1][0, -1, :].float().cpu()

                # Sample next token
                token = torch.argmax(logits).item()
                input_ids.append(token)

                # Collect future tokens (greedy for training stability)
                future = []
                temp_ids = input_ids[:]
                temp_past = past_key_values
                for _ in range(n_future):
                    tid = torch.tensor([[temp_ids[-1]]], device=DEVICE)
                    t_out = model(input_ids=tid, past_key_values=temp_past, use_cache=True)
                    t_tok = torch.argmax(t_out.logits[0, -1, :]).item()
                    future.append(t_tok)
                    temp_ids.append(t_tok)
                    temp_past = t_out.past_key_values

                data.append({"hidden": hidden, "future": future})

                if token == tok.eos_token_id:
                    break
    return data


# ---------------------------------------------------------------------------
# 5. Train draft head with φ-decay loss weighting
# ---------------------------------------------------------------------------
def train_draft_head(draft_head, data, n_steps=200, lr=1e-3):
    """Train draft head with φ-decay: earlier future positions matter more."""
    draft_head.to(DEVICE).train()
    opt = torch.optim.Adam(draft_head.parameters(), lr=lr)

    # φ-decay weights: w_k = PHI_INV^(k)
    weights = torch.tensor([PHI_INV ** k for k in range(draft_head.n_future)], device=DEVICE)
    weights = weights / weights.sum()

    losses = []
    for step in range(n_steps):
        # Sample a batch
        batch = data[:64] if len(data) >= 64 else data
        if not batch:
            break

        hiddens = torch.stack([b["hidden"] for b in batch]).to(DEVICE)
        futures = torch.tensor([b["future"] for b in batch], device=DEVICE)  # [B, n_future]

        logits_list = draft_head(hiddens)  # list of [B, vocab]
        loss = 0.0
        for k in range(draft_head.n_future):
            loss += weights[k] * F.cross_entropy(logits_list[k], futures[:, k])

        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())

        if (step + 1) % 50 == 0:
            print(f"  Step {step+1}/{n_steps}, loss={loss.item():.4f}")

    draft_head.eval()
    return losses


# ---------------------------------------------------------------------------
# 6. Speculative generation loop
# ---------------------------------------------------------------------------
def generate_speculative(
    model, tok, draft_head, observer, scheduler,
    prompt, max_new=64, temp=0.8, conf_threshold=0.6, changepoint_threshold=0.3
):
    """
    Speculative decoding with Cassi-inspired control signals.
    """
    draft_head.eval()
    observer.eval()
    model.eval()

    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None
    prev_hidden = None

    stats = {
        "tokens_generated": 0,
        "draft_blocks": 0,
        "accepted_tokens": 0,
        "full_verifications": 0,
        "truncated_by_changepoint": 0,
        "breath_sizes": [],
        "confidences": [],
    }

    t0 = time.time()
    while stats["tokens_generated"] < max_new:
        # --- Full forward pass for current position ---
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

        # --- Observer signals ---
        conf, imp = observer(hidden)
        top_prob = F.softmax(logits, dim=-1).max().item()

        # --- Changepoint proxy ---
        if prev_hidden is not None:
            sim = F.cosine_similarity(hidden.unsqueeze(0), prev_hidden.unsqueeze(0)).item()
            changepoint = 1 - sim  # high = topic shift
        else:
            changepoint = 0.0
        prev_hidden = hidden.clone()

        # --- Breath-guided block size ---
        block_size, beat, yang, yin = scheduler.step()
        stats["breath_sizes"].append(block_size)
        stats["confidences"].append(conf.item())

        # --- Decide whether to speculate ---
        should_speculate = (
            conf.item() > conf_threshold
            and top_prob > 0.5
            and changepoint < changepoint_threshold
            and block_size > 1
        )

        if not should_speculate:
            # Standard sampling
            probs = F.softmax(logits / temp, dim=-1)
            token = torch.multinomial(probs, num_samples=1).item()
            input_ids.append(token)
            stats["tokens_generated"] += 1
            stats["full_verifications"] += 1
            if token == tok.eos_token_id:
                break
            continue

        # --- Speculate: draft next `block_size` tokens ---
        stats["draft_blocks"] += 1
        with torch.no_grad():
            draft_logits = draft_head(hidden)  # list of [vocab]
        draft_tokens = [torch.argmax(dl).item() for dl in draft_logits[:block_size]]

        # --- Verify draft block ---
        # Feed draft tokens through model in one go
        verify_ids = torch.tensor([draft_tokens], device=DEVICE)
        with torch.no_grad():
            verify_out = model(
                input_ids=verify_ids,
                past_key_values=past_key_values,
                use_cache=True,
            )
        verify_logits = verify_out.logits[0, :, :]  # [block_size, vocab]
        verify_past = verify_out.past_key_values

        # Accept tokens up to first mismatch (greedy verification)
        accepted = 0
        for k in range(block_size):
            verify_token = torch.argmax(verify_logits[k, :]).item()
            if verify_token == draft_tokens[k]:
                input_ids.append(draft_tokens[k])
                accepted += 1
                stats["tokens_generated"] += 1
                if draft_tokens[k] == tok.eos_token_id:
                    break
            else:
                # Mismatch: accept verify token instead
                input_ids.append(verify_token)
                accepted += 1
                stats["tokens_generated"] += 1
                break

        stats["accepted_tokens"] += accepted
        stats["full_verifications"] += 1
        past_key_values = verify_past

        # Check changepoint within accepted tokens
        if changepoint > changepoint_threshold:
            stats["truncated_by_changepoint"] += 1

        if input_ids[-1] == tok.eos_token_id:
            break

    dt = time.time() - t0
    text = tok.decode(input_ids, skip_special_tokens=True)
    speed = stats["tokens_generated"] / dt if dt > 0 else 0.0
    return text, speed, stats


# ---------------------------------------------------------------------------
# 7. Baseline generation for comparison
# ---------------------------------------------------------------------------
def generate_baseline(model, tok, prompt, max_new=64, temp=0.8):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=True,
            temperature=temp,
            top_p=0.85,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.time() - t0
    return tok.decode(out[0], skip_special_tokens=True), max_new / dt


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-draft", action="store_true")
    parser.add_argument("--train-steps", type=int, default=200)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--prompt", type=str, default="The golden ratio appears in nature")
    parser.add_argument("--max-new", type=int, default=64)
    args = parser.parse_args()

    model, tok = load_model()
    d_model = model.config.hidden_size
    vocab_size = model.config.vocab_size

    draft_head = CassiDraftHead(d_model, vocab_size, n_future=4).to(DEVICE)
    observer = ObserverHead(d_model, vocab_size).to(DEVICE)
    scheduler = BreathBlockScheduler(base_size=2, max_size=8)

    draft_path = Path("experiments/cassi_draft_head.pt")

    if args.train_draft or not draft_path.exists():
        print("Collecting training data...")
        prompts = [
            "The golden ratio appears in nature",
            "In the philosophy of consciousness",
            "Quantum mechanics describes",
            "The history of artificial intelligence",
            "A recursive function is defined as",
        ]
        data = collect_training_data(model, tok, prompts, n_future=4, max_per_prompt=64)
        print(f"Collected {len(data)} training examples")

        print(f"Training draft head for {args.train_steps} steps...")
        losses = train_draft_head(draft_head, data, n_steps=args.train_steps)
        torch.save(draft_head.state_dict(), draft_path)
        print(f"Saved draft head to {draft_path}")
    else:
        print(f"Loading draft head from {draft_path}")
        draft_head.load_state_dict(torch.load(draft_path, map_location=DEVICE))

    if args.generate:
        print("\n" + "=" * 70)
        print("BASELINE GENERATION")
        print("=" * 70)
        text_base, speed_base = generate_baseline(model, tok, args.prompt, max_new=args.max_new)
        print(f"Speed: {speed_base:.1f} tok/s")
        print(f"Output:\n{text_base}\n")

        print("=" * 70)
        print("CASSI SPECULATIVE GENERATION")
        print("=" * 70)
        text_spec, speed_spec, stats = generate_speculative(
            model, tok, draft_head, observer, scheduler,
            args.prompt, max_new=args.max_new,
        )
        print(f"Speed: {speed_spec:.1f} tok/s")
        print(f"Draft blocks: {stats['draft_blocks']}")
        print(f"Accepted tokens: {stats['accepted_tokens']}")
        print(f"Avg block size: {sum(stats['breath_sizes'])/max(len(stats['breath_sizes']),1):.1f}")
        print(f"Avg confidence: {sum(stats['confidences'])/max(len(stats['confidences']),1):.3f}")
        print(f"Output:\n{text_spec}\n")

        results = {
            "prompt": args.prompt,
            "baseline": {"text": text_base, "speed": speed_base},
            "speculative": {
                "text": text_spec,
                "speed": speed_spec,
                "stats": stats,
            },
        }
        with open("experiments/cassi_speculative_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Saved results to experiments/cassi_speculative_results.json")


if __name__ == "__main__":
    main()
