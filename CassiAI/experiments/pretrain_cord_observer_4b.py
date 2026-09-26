#!/usr/bin/env python3
"""
Pre-train the CordObserver on frozen Qwen3.5-4B hidden states.

Same structure as pretrain_observer_4b.py but uses CordObserver
instead of the MLP ObserverHead.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import IterableDataset, DataLoader
from transformers import AutoConfig, AutoTokenizer
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from safetensors.torch import load_file
import os
import json
import time
import math
import random
import sys
sys.path.insert(0, ".")
from cassi.cord_observer import CordObserver

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
LOCAL_MODEL_DIR = "qwen_models/Qwen3.5-4B"
DEVICE = "cuda"


class TextChunkDataset(IterableDataset):
    def __init__(self, tokenizer, file_path, chunk_len=128, stride=64, data_limit=None,
                 shuffle_buffer=4096, seed=42):
        self.tokenizer = tokenizer
        self.file_path = file_path
        self.chunk_len = chunk_len
        self.stride = stride
        self.data_limit = data_limit
        self.shuffle_buffer = shuffle_buffer
        self.seed = seed
        self.epoch = 0

    def set_epoch(self, epoch):
        self.epoch = epoch

    def _raw_chunks(self, f, start_offset=0):
        buffer = ""
        read_so_far = 0
        chunk_size = 1_048_576

        if start_offset > 0:
            skipped = f.read(start_offset)
            read_so_far += len(skipped)

        while True:
            if self.data_limit and read_so_far >= self.data_limit:
                break
            to_read = chunk_size
            if self.data_limit:
                to_read = min(chunk_size, self.data_limit - read_so_far)
            piece = f.read(to_read)
            if not piece:
                break
            read_so_far += len(piece)
            buffer += piece
            tokens = self.tokenizer.encode(buffer, add_special_tokens=False)
            for i in range(0, len(tokens) - self.chunk_len, self.stride):
                chunk = tokens[i : i + self.chunk_len + 1]
                if len(chunk) < self.chunk_len + 1:
                    continue
                yield torch.tensor(chunk, dtype=torch.long)
            if len(tokens) > self.chunk_len:
                buffer = self.tokenizer.decode(tokens[-self.chunk_len:], skip_special_tokens=True)
            else:
                buffer = ""

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        start_offset = rng.randint(0, 1_048_576)

        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            buf = []
            for chunk in self._raw_chunks(f, start_offset=start_offset):
                buf.append(chunk)
                if len(buf) >= self.shuffle_buffer:
                    rng.shuffle(buf)
                    yield buf.pop(0)
            rng.shuffle(buf)
            for chunk in buf:
                yield chunk


def load_base_model():
    config = AutoConfig.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True)
    with torch.device("meta"):
        model = Qwen3_5ForConditionalGeneration(config)
    with open(os.path.join(LOCAL_MODEL_DIR, "model.safetensors.index.json")) as f:
        index = json.load(f)
    for shard in sorted(set(index["weight_map"].values())):
        sd = load_file(os.path.join(LOCAL_MODEL_DIR, shard), device="cuda:0")
        model.load_state_dict(sd, strict=False, assign=True)
        del sd
    for name, param in list(model.named_parameters()):
        if param.is_meta:
            path, p = name.rsplit(".", 1)
            m = model.get_submodule(path)
            setattr(m, p, nn.Parameter(torch.empty_like(param, device="cuda:0"), requires_grad=param.requires_grad))
    for name, buf in list(model.named_buffers()):
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
    model.eval()
    return model


def train_epoch(base_model, observer, loader, optimizer, grad_accum=4, grad_clip=1.0,
                steps_per_epoch=500, residual=False, hybrid=False, l2_weight=0.0,
                consistency_weight=0.0, noise_std=0.0):
    observer.train()
    total_loss = 0.0
    total_ce = 0.0
    total_l2 = 0.0
    total_cons = 0.0
    total_acc = 0.0
    steps = 0
    accum_steps = 0
    total_tokens = 0

    for batch_idx, batch in enumerate(loader):
        batch = batch.to(DEVICE)
        input_ids = batch[:, :-1]
        targets = batch[:, 1:]
        B, L = input_ids.shape

        with torch.no_grad():
            out = base_model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            hidden = out.hidden_states[-1]  # [B, L, D] bfloat16
            base_logits = out.logits if residual else None

        with torch.amp.autocast('cuda'):
            conf, imp, obs_logits = observer(hidden)  # [B, L, V]
            if residual:
                combined_logits = base_logits + obs_logits
                ce_loss = F.cross_entropy(
                    combined_logits.reshape(-1, combined_logits.size(-1)),
                    targets.reshape(-1),
                    reduction='none',
                )
                if hybrid:
                    with torch.no_grad():
                        base_ce = F.cross_entropy(
                            base_logits.reshape(-1, base_logits.size(-1)),
                            targets.reshape(-1),
                            reduction='none',
                        )
                    weight = torch.clamp(base_ce / base_ce.mean().clamp_min(1e-6), 0.1, 5.0)
                    ce_loss = (ce_loss * weight).mean()
                else:
                    ce_loss = ce_loss.mean()
                preds = combined_logits.argmax(dim=-1)
            else:
                ce_loss = F.cross_entropy(obs_logits.reshape(-1, obs_logits.size(-1)), targets.reshape(-1))
                preds = obs_logits.argmax(dim=-1)

            # L2 regularization on residual logits (anti-memorization)
            l2_loss = (obs_logits ** 2).mean() if l2_weight > 0 else torch.tensor(0.0, device=DEVICE)

            # Consistency: hidden-state noise should not change residual much
            cons_loss = torch.tensor(0.0, device=DEVICE)
            if consistency_weight > 0 and noise_std > 0:
                hidden_noisy = hidden + torch.randn_like(hidden) * noise_std
                _, _, obs_logits_noisy = observer(hidden_noisy)
                cons_loss = ((obs_logits - obs_logits_noisy) ** 2).mean()

            loss = ce_loss + l2_weight * l2_loss + consistency_weight * cons_loss
            loss = loss / grad_accum

            correct = (preds == targets).sum().item()
            total_acc += correct
            total_tokens += targets.numel()

        loss.backward()
        accum_steps += 1

        if accum_steps % grad_accum == 0:
            torch.nn.utils.clip_grad_norm_(observer.parameters(), grad_clip)
            optimizer.step()
            optimizer.zero_grad()

        total_loss += loss.item() * grad_accum
        total_ce += ce_loss.item()
        total_l2 += l2_loss.item()
        total_cons += cons_loss.item()
        steps += 1

        if batch_idx % 20 == 0:
            acc = 100.0 * correct / targets.numel()
            print(f"  step {batch_idx:4d}  loss={loss.item() * grad_accum:.4f}  ce={ce_loss.item():.4f}  acc={acc:.2f}%")

        if steps >= steps_per_epoch:
            break

    if accum_steps % grad_accum != 0:
        torch.nn.utils.clip_grad_norm_(observer.parameters(), grad_clip)
        optimizer.step()
        optimizer.zero_grad()

    return {
        "loss": total_loss / steps,
        "ce": total_ce / steps,
        "l2": total_l2 / steps,
        "cons": total_cons / steps,
        "acc": 100.0 * total_acc / total_tokens,
    }


def validate(base_model, observer, loader, val_steps=50, residual=False):
    observer.eval()
    total_loss = 0.0
    total_acc = 0.0
    total_tokens = 0
    steps = 0
    with torch.no_grad(), torch.amp.autocast('cuda'):
        for batch in loader:
            batch = batch.to(DEVICE)
            input_ids = batch[:, :-1]
            targets = batch[:, 1:]

            out = base_model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            hidden = out.hidden_states[-1]
            base_logits = out.logits if residual else None

            conf, imp, obs_logits = observer(hidden)
            if residual:
                combined_logits = base_logits + obs_logits
                loss = F.cross_entropy(combined_logits.reshape(-1, combined_logits.size(-1)), targets.reshape(-1))
                preds = combined_logits.argmax(dim=-1)
            else:
                loss = F.cross_entropy(obs_logits.reshape(-1, obs_logits.size(-1)), targets.reshape(-1))
                preds = obs_logits.argmax(dim=-1)

            correct = (preds == targets).sum().item()

            total_loss += loss.item()
            total_acc += correct
            total_tokens += targets.numel()
            steps += 1
            if steps >= val_steps:
                break

    return {
        "loss": total_loss / steps,
        "acc": 100.0 * total_acc / total_tokens,
    }


def generate_test(base_model, observer, tok, prompt, max_new=40, residual=False):
    observer.eval()
    input_ids = tok(prompt, return_tensors="pt").to(DEVICE)["input_ids"][0].tolist()
    past = None
    observer.reset_buffer()

    for _ in range(max_new):
        ids = torch.tensor([input_ids] if past is None else [[input_ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = base_model(input_ids=ids, past_key_values=past, use_cache=True, output_hidden_states=True)
            base_logits = out.logits[0, -1, :].float()
            hidden = out.hidden_states[-1][0, -1, :].to(torch.bfloat16)
            past = out.past_key_values

            conf, imp, obs_logits = observer(hidden)

        if residual:
            combined = base_logits + obs_logits.float()
        else:
            combined = 0.5 * base_logits + 0.5 * obs_logits.float()
        probs = F.softmax(combined / 0.8, dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()
        input_ids.append(token)
        if token == tok.eos_token_id:
            break

    return tok.decode(input_ids, skip_special_tokens=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="datasets/active/LightNovels.txt")
    parser.add_argument("--chunk-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--steps-per-epoch", type=int, default=500)
    parser.add_argument("--val-steps", type=int, default=50)
    parser.add_argument("--data-limit", type=int, default=None)
    parser.add_argument("--no-gen-test", action="store_true")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--D", type=int, default=1040, help="Cord field dimension")
    parser.add_argument("--residual", action="store_true", help="Train observer as residual over base model logits")
    parser.add_argument("--hybrid", action="store_true", help="Use hybrid objective: base-error weighting + L2 + consistency")
    parser.add_argument("--l2-weight", type=float, default=0.01, help="L2 penalty on observer residual logits")
    parser.add_argument("--consistency-weight", type=float, default=0.1, help="Consistency loss weight")
    parser.add_argument("--noise-std", type=float, default=0.05, help="Gaussian noise std for consistency loss")
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)
    base_model = load_base_model()

    d_model = base_model.config.text_config.hidden_size
    vocab_size = base_model.config.text_config.vocab_size

    observer = CordObserver(d_model, vocab_size, D=args.D).to(DEVICE).to(torch.bfloat16)

    # Freeze base
    for p in base_model.parameters():
        p.requires_grad = False
    base_model.eval()

    trainable = sum(p.numel() for p in observer.parameters() if p.requires_grad)
    print(f"CordObserver trainable params: {trainable:,}  (D={args.D})")

    if args.resume:
        print(f"Resuming observer from {args.resume}")
        observer.load_state_dict(torch.load(args.resume, weights_only=False))

    optimizer = torch.optim.AdamW(
        observer.parameters(), lr=args.lr, weight_decay=0.01, betas=(0.9, 0.95)
    )

    dataset = TextChunkDataset(tok, args.data, chunk_len=args.chunk_len, stride=args.chunk_len // 2, data_limit=args.data_limit)
    loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)

    best_val_loss = float("inf")

    save_prefix = f"experiments/cord_observer_D{args.D}"

    for epoch in range(args.epochs):
        print(f"\n=== Epoch {epoch + 1}/{args.epochs} ===")
        dataset.set_epoch(epoch)
        loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        t0 = time.time()
        metrics = train_epoch(base_model, observer, loader, optimizer,
                              grad_accum=args.grad_accum, steps_per_epoch=args.steps_per_epoch,
                              residual=args.residual, hybrid=args.hybrid,
                              l2_weight=args.l2_weight, consistency_weight=args.consistency_weight,
                              noise_std=args.noise_std)
        dt = time.time() - t0
        print(f"Epoch {epoch + 1} done in {dt:.1f}s  loss={metrics['loss']:.4f}  ce={metrics['ce']:.4f}  l2={metrics['l2']:.4f}  cons={metrics['cons']:.4f}  acc={metrics['acc']:.2f}%")

        # Validation on fixed-seed data for consistent comparison
        dataset.set_epoch(0)
        val_loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        val_metrics = validate(base_model, observer, val_loader, val_steps=args.val_steps,
                               residual=args.residual)
        print(f"Val  loss={val_metrics['loss']:.4f}  acc={val_metrics['acc']:.2f}%")

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            torch.save(observer.state_dict(), f"{save_prefix}_best.pt")
            print("Saved best CordObserver")

        torch.save(observer.state_dict(), f"{save_prefix}_epoch{epoch + 1}.pt")

        if not args.no_gen_test:
            print("\n--- Generation test (50/50 blend) ---")
            text = generate_test(base_model, observer, tok, "The golden ratio appears in nature", max_new=40,
                                 residual=args.residual)
            print(f"Generated: {text}\n")

        print(f"Peak VRAM: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")
        torch.cuda.reset_peak_memory_stats()

    print("CordObserver pre-training complete.")
    print(f"Best checkpoint: {save_prefix}_best.pt (val_loss={best_val_loss:.4f})")


if __name__ == "__main__":
    main()
