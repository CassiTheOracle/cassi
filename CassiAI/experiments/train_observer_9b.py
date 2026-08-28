#!/usr/bin/env python3
"""
Train an Observer head on top of frozen Qwen3.5-9B.

The observer learns to:
1. Predict the next token from the base model's hidden state (obs_logits)
2. Estimate its own confidence (sigmoid → [0,1])
3. Estimate token importance (sigmoid → [0,1])

Training is done with frozen base-model features (detached hidden states).
Generation blend:
    blended_logits = conf * base_logits + (1 - conf) * obs_logits

Where conf is the observer's confidence. High conf → trust base model.
Low conf → trust observer's own prediction.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import IterableDataset, DataLoader
from transformers import AutoConfig, AutoTokenizer
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from safetensors.torch import load_file
from huggingface_hub import snapshot_download
import os
import json
import time
import math

PHI = (1 + 5**0.5) / 2
MODEL_ID = "Qwen/Qwen3.5-9B"
DEVICE = "cuda"


class ObserverHead(nn.Module):
    def __init__(self, d_model: int, vocab_size: int, bottleneck: int = 1024):
        super().__init__()
        hid = int(d_model / PHI)
        self.confidence = nn.Sequential(
            nn.Linear(d_model, hid), nn.LayerNorm(hid), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hid, 1), nn.Sigmoid()
        )
        self.importance = nn.Sequential(
            nn.Linear(d_model, hid), nn.LayerNorm(hid), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hid, 1), nn.Sigmoid()
        )
        # Bottlenecked logits projection to save VRAM
        self.logits_proj = nn.Sequential(
            nn.Linear(d_model, bottleneck),
            nn.LayerNorm(bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, vocab_size, bias=False),
        )

    def forward(self, hidden):
        """
        hidden: [B, L, D] or [B, D]
        Returns: conf [B, L], imp [B, L], logits [B, L, V]
        """
        conf = self.confidence(hidden).squeeze(-1)
        imp = self.importance(hidden).squeeze(-1)
        logits = self.logits_proj(hidden)
        return conf, imp, logits


def load_base_model():
    print("Loading base model...")
    cache_dir = snapshot_download(MODEL_ID)
    config = AutoConfig.from_pretrained(cache_dir, trust_remote_code=True)
    with torch.device("meta"):
        model = Qwen3_5ForConditionalGeneration(config)

    with open(os.path.join(cache_dir, "model.safetensors.index.json")) as f:
        index = json.load(f)

    for shard in sorted(set(index["weight_map"].values())):
        sd = load_file(os.path.join(cache_dir, shard), device="cuda:0")
        model.load_state_dict(sd, strict=False, assign=True)
        del sd

    # Materialize only meta tensors (vision, rotary buffers)
    for name, param in model.named_parameters():
        if param.is_meta:
            path, p = name.rsplit(".", 1)
            m = model.get_submodule(path)
            setattr(m, p, nn.Parameter(torch.empty_like(param, device="cuda:0"), requires_grad=param.requires_grad))
    for name, buf in model.named_buffers():
        if buf.is_meta:
            path, b = name.rsplit(".", 1)
            m = model.get_submodule(path)
            setattr(m, b, torch.empty_like(buf, device="cuda:0"))

    for name, mod in model.named_modules():
        if hasattr(mod, "inv_freq") and hasattr(mod, "compute_default_rope_parameters"):
            inv, scale = mod.compute_default_rope_parameters(mod.config, device="cuda:0")
            mod.inv_freq = inv
            mod.original_inv_freq = inv.clone()
            mod.attention_scaling = scale

    model.tie_weights()
    for p in model.parameters():
        p._is_hf_initialized = True
    for b in model.buffers():
        b._is_hf_initialized = True

    # Freeze base model
    for p in model.parameters():
        p.requires_grad = False
    model.eval()
    print(f"Base model ready. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")
    return model


class TextChunkDataset(IterableDataset):
    """Stream text from a file, tokenize on the fly, yield chunks."""

    def __init__(self, tokenizer, file_path, chunk_len=256, stride=128):
        self.tokenizer = tokenizer
        self.file_path = file_path
        self.chunk_len = chunk_len
        self.stride = stride

    def __iter__(self):
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        for i in range(0, len(tokens) - self.chunk_len, self.stride):
            chunk = tokens[i : i + self.chunk_len + 1]
            if len(chunk) < self.chunk_len + 1:
                continue
            yield torch.tensor(chunk, dtype=torch.long)


def train_epoch(model, observer, loader, optimizer, scaler, grad_accum=4, grad_clip=1.0, steps_per_epoch=500):
    model.eval()
    observer.train()
    total_loss = 0.0
    total_obs = 0.0
    total_conf = 0.0
    total_imp = 0.0
    steps = 0
    accum_steps = 0

    for batch_idx, batch in enumerate(loader):
        batch = batch.to(DEVICE)
        input_ids = batch[:, :-1]
        targets = batch[:, 1:]

        # Forward base model, frozen
        with torch.no_grad(), torch.cuda.amp.autocast():
            out = model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            base_logits = out.logits  # [B, L, V]
            hidden = out.hidden_states[-1].detach()  # [B, L, D]

        # Forward observer
        with torch.cuda.amp.autocast():
            conf, imp, obs_logits = observer(hidden)

            # Observer next-token loss
            loss_obs = F.cross_entropy(
                obs_logits.reshape(-1, obs_logits.size(-1)),
                targets.reshape(-1),
            )

            # Confidence target: model's softmax probability on the TRUE token
            # High when base model is confident about the correct answer
            with torch.no_grad():
                base_probs = F.softmax(base_logits, dim=-1)  # [B, L, V]
                true_probs = base_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)  # [B, L]

            loss_conf = F.mse_loss(conf, true_probs)

            # Importance target: entropy of base model distribution
            # High entropy → model is uncertain → high importance
            with torch.no_grad():
                entropy = -(base_probs * torch.log(base_probs + 1e-9)).sum(dim=-1)  # [B, L]
                # Normalize to [0, 1] roughly
                imp_target = torch.tanh(entropy / 2.0)

            loss_imp = F.mse_loss(imp, imp_target)

            loss = (loss_obs + 0.5 * loss_conf + 0.1 * loss_imp) / grad_accum

        scaler.scale(loss).backward()
        accum_steps += 1

        if accum_steps % grad_accum == 0:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(observer.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
            torch.cuda.empty_cache()

        total_loss += loss.item() * grad_accum
        total_obs += loss_obs.item()
        total_conf += loss_conf.item()
        total_imp += loss_imp.item()
        steps += 1

        if batch_idx % 50 == 0:
            print(f"  step {batch_idx:4d}  loss={loss.item() * grad_accum:.4f}  obs={loss_obs.item():.4f}  "
                  f"conf={loss_conf.item():.4f}  imp={loss_imp.item():.4f}  "
                  f"avg_conf={conf.mean().item():.3f}")

        if steps >= steps_per_epoch:
            break

    # Final step if accumulation not complete
    if accum_steps % grad_accum != 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(observer.parameters(), grad_clip)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

    return {
        "loss": total_loss / steps,
        "obs": total_obs / steps,
        "conf": total_conf / steps,
        "imp": total_imp / steps,
    }


def validate(model, observer, loader):
    model.eval()
    observer.eval()
    total_loss = 0.0
    steps = 0
    with torch.no_grad(), torch.cuda.amp.autocast():
        for batch in loader:
            batch = batch.to(DEVICE)
            input_ids = batch[:, :-1]
            targets = batch[:, 1:]

            out = model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            hidden = out.hidden_states[-1].detach()
            base_logits = out.logits

            conf, imp, obs_logits = observer(hidden)
            loss_obs = F.cross_entropy(
                obs_logits.reshape(-1, obs_logits.size(-1)),
                targets.reshape(-1),
            )
            base_probs = F.softmax(base_logits, dim=-1)
            true_probs = base_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
            loss_conf = F.mse_loss(conf, true_probs)
            entropy = -(base_probs * torch.log(base_probs + 1e-9)).sum(dim=-1)
            imp_target = torch.tanh(entropy / 2.0)
            loss_imp = F.mse_loss(imp, imp_target)
            loss = loss_obs + 0.5 * loss_conf + 0.1 * loss_imp

            total_loss += loss.item()
            steps += 1
            if steps >= 100:
                break

    return total_loss / steps


def generate_with_observer(model, observer, tok, prompt, max_new=64, temperature=0.8):
    """Generate with observer blending."""
    model.eval()
    observer.eval()
    input_ids = tok(prompt, return_tensors="pt").to(DEVICE)["input_ids"][0].tolist()
    past = None
    metas = []

    for _ in range(max_new):
        ids = torch.tensor(
            [input_ids] if past is None else [[input_ids[-1]]],
            device=DEVICE,
        )
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past, use_cache=True, output_hidden_states=True)
            base_logits = out.logits[0, -1, :]
            hidden = out.hidden_states[-1][0, -1, :]
            past = out.past_key_values

            conf, imp, obs_logits = observer(hidden)
            # Blend: high conf → trust base, low conf → trust observer
            alpha = conf.item()
            blended = alpha * base_logits + (1 - alpha) * obs_logits[0]

        probs = F.softmax(blended / temperature, dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()

        input_ids.append(token)
        metas.append({"conf": alpha, "imp": imp.item(), "token": tok.decode([token])})
        if token == tok.eos_token_id:
            break

    return tok.decode(input_ids, skip_special_tokens=True), metas


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="datasets/active/LightNovels.txt")
    parser.add_argument("--chunk-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--steps-per-epoch", type=int, default=500)
    parser.add_argument("--save-every", type=int, default=250)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=True)
    base_model = load_base_model()
    d_model = base_model.config.text_config.hidden_size
    vocab_size = base_model.config.text_config.vocab_size

    observer = ObserverHead(d_model, vocab_size).to(DEVICE).to(torch.bfloat16)
    if args.resume:
        print(f"Resuming observer from {args.resume}")
        observer.load_state_dict(torch.load(args.resume, weights_only=False))

    optimizer = torch.optim.AdamW(observer.parameters(), lr=args.lr, weight_decay=0.01)
    scaler = torch.cuda.amp.GradScaler()

    dataset = TextChunkDataset(tok, args.data, chunk_len=args.chunk_len, stride=args.chunk_len // 2)
    loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)

    best_val = float("inf")
    global_step = 0

    for epoch in range(args.epochs):
        print(f"\n=== Epoch {epoch + 1}/{args.epochs} ===")
        t0 = time.time()
        metrics = train_epoch(base_model, observer, loader, optimizer, scaler,
                              grad_accum=args.grad_accum, steps_per_epoch=args.steps_per_epoch)
        dt = time.time() - t0
        print(f"Epoch {epoch + 1} done in {dt:.1f}s  loss={metrics['loss']:.4f}  "
              f"obs={metrics['obs']:.4f}  conf={metrics['conf']:.4f}  imp={metrics['imp']:.4f}")

        # Quick validation
        val_loss = validate(base_model, observer, loader)
        print(f"Val loss: {val_loss:.4f}")

        # Save
        if val_loss < best_val:
            best_val = val_loss
            torch.save(observer.state_dict(), "experiments/observer_9b_best.pt")
            print("Saved best observer")

        # Periodic save
        torch.save(observer.state_dict(), f"experiments/observer_9b_epoch{epoch + 1}.pt")

        # Test generation
        print("\n--- Generation test ---")
        text, metas = generate_with_observer(base_model, observer, tok, "The golden ratio appears in nature", max_new=40)
        print(f"Generated ({len(metas)} tokens, avg_conf={sum(m['conf'] for m in metas)/len(metas):.3f}):")
        print(text)
        print()

    print("Training complete.")


if __name__ == "__main__":
    main()
