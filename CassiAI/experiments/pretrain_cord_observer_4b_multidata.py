#!/usr/bin/env python3
"""
Pre-train CordObserver on a broad mix of datasets.

Same structure as pretrain_cord_observer_4b.py, but samples from multiple
sources (narrative, factual, math, science) to avoid QA specialization.
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
import csv
sys.path.insert(0, ".")
from cassi.cord_observer import CordObserver

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
LOCAL_MODEL_DIR = "qwen_models/Qwen3.5-4B"
DEVICE = "cuda"


# ═══════════════════════════════════════════════════════════════════════════════
# Text extraction helpers
# ═══════════════════════════════════════════════════════════════════════════════

def decode_tokenized_json(path):
    """Decode {chars, sequences} tokenized instruct files to strings."""
    with open(path) as f:
        data = json.load(f)
    chars = data["chars"]
    sequences = data["sequences"]
    texts = []
    for seq in sequences:
        text = "".join(chars[t] for t in seq)
        texts.append(text)
    return texts


def load_jsonl_text(path, field="self_contained_problem"):
    texts = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if field in obj:
                    texts.append(obj[field])
            except Exception:
                pass
    return texts


def load_json_text(path, field=None):
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        if field:
            return [str(item.get(field, "")) for item in data if field in item]
        return [str(item) for item in data]
    if "sequences" in data and "chars" in data:
        return decode_tokenized_json(path)
    return [str(data)]


def load_csv_text(path, columns=None):
    texts = []
    with open(path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if columns:
                parts = [row.get(c, "") for c in columns]
                texts.append("\n".join(p for p in parts if p))
            else:
                texts.append("\n".join(row.values()))
    return texts


def load_parquet_text(path, columns):
    import pandas as pd
    df = pd.read_parquet(path)
    texts = []
    for _, row in df.iterrows():
        parts = [str(row.get(c, "")) for c in columns if c in df.columns]
        texts.append("\n".join(p for p in parts if p))
    return texts


def load_source_text(path, extractor=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == ".jsonl":
        field = extractor or "text"
        return "\n\n".join(load_jsonl_text(path, field))
    if ext == ".json":
        field = extractor
        return "\n\n".join(load_json_text(path, field))
    if ext == ".csv":
        columns = extractor.split(",") if extractor else None
        return "\n\n".join(load_csv_text(path, columns))
    if ext == ".parquet":
        columns = extractor.split(",") if extractor else None
        return "\n\n".join(load_parquet_text(path, columns))
    raise ValueError(f"Unsupported file type: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-source dataset (memory-efficient chunked reading)
# ═══════════════════════════════════════════════════════════════════════════════

class TextSource:
    """Yields tokenized chunks from a single file, reading lazily."""

    def __init__(self, tokenizer, path, chunk_len=128, stride=64,
                 read_chunk_size=1_048_576, extractor=None):
        self.tokenizer = tokenizer
        self.path = path
        self.chunk_len = chunk_len
        self.stride = stride
        self.read_chunk_size = read_chunk_size
        self.extractor = extractor
        self.ext = os.path.splitext(path)[1].lower()

    def _text_stream(self):
        """Yield text fragments from the source file."""
        if self.ext == ".txt":
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                while True:
                    piece = f.read(self.read_chunk_size)
                    if not piece:
                        break
                    yield piece
        elif self.ext == ".jsonl":
            field = self.extractor or "text"
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if field in obj:
                            yield obj[field] + "\n\n"
                    except Exception:
                        pass
        elif self.ext == ".json":
            # Heuristic: if it has chars+sequences, decode tokenized; else treat as list of objects
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            if isinstance(data, dict) and "chars" in data and "sequences" in data:
                chars = data["chars"]
                for seq in data["sequences"]:
                    yield "".join(chars[t] for t in seq) + "\n\n"
            elif isinstance(data, list):
                field = self.extractor
                for item in data:
                    if field and isinstance(item, dict) and field in item:
                        yield item[field] + "\n\n"
                    else:
                        yield str(item) + "\n\n"
        elif self.ext == ".csv":
            columns = self.extractor.split(",") if self.extractor else None
            with open(self.path, newline="", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if columns:
                        yield "\n".join(row.get(c, "") for c in columns if row.get(c)) + "\n\n"
                    else:
                        yield "\n".join(row.values()) + "\n\n"
        elif self.ext == ".parquet":
            import pandas as pd
            columns = self.extractor.split(",") if self.extractor else None
            df = pd.read_parquet(self.path)
            for _, row in df.iterrows():
                if columns:
                    yield "\n".join(str(row.get(c, "")) for c in columns if c in df.columns and row.get(c)) + "\n\n"
                else:
                    yield "\n".join(str(v) for v in row.values if v) + "\n\n"
        else:
            raise ValueError(f"Unsupported file type: {self.path}")

    def chunks(self, rng):
        """Yield tokenized chunks with a random starting offset."""
        buffer = ""
        for fragment in self._text_stream():
            buffer += fragment
            if len(buffer) < self.read_chunk_size:
                continue
            tokens = self.tokenizer.encode(buffer, add_special_tokens=False)
            start = rng.randint(0, self.chunk_len)
            for i in range(start, len(tokens) - self.chunk_len, self.stride):
                chunk = tokens[i:i + self.chunk_len + 1]
                if len(chunk) < self.chunk_len + 1:
                    continue
                yield torch.tensor(chunk, dtype=torch.long)
            # Keep tail for overlap
            if len(tokens) > self.chunk_len:
                buffer = self.tokenizer.decode(tokens[-self.chunk_len:], skip_special_tokens=True)
            else:
                buffer = ""
        # Drain remaining buffer
        if buffer:
            tokens = self.tokenizer.encode(buffer, add_special_tokens=False)
            start = rng.randint(0, self.chunk_len)
            for i in range(start, len(tokens) - self.chunk_len, self.stride):
                chunk = tokens[i:i + self.chunk_len + 1]
                if len(chunk) < self.chunk_len + 1:
                    continue
                yield torch.tensor(chunk, dtype=torch.long)


class MultiSourceTextDataset(IterableDataset):
    def __init__(self, tokenizer, sources, chunk_len=128, stride=64,
                 shuffle_buffer=4096, seed=42):
        """
        sources: list of dicts with keys:
            path, weight, extractor (optional)
        """
        self.tokenizer = tokenizer
        self.sources = sources
        self.chunk_len = chunk_len
        self.stride = stride
        self.shuffle_buffer = shuffle_buffer
        self.seed = seed
        self.epoch = 0
        self._source_objs = []
        self._weights = []
        for src in sources:
            print(f"Registering source: {src['path']} (weight={src.get('weight', 1.0)}, extractor={src.get('extractor')})")
            self._source_objs.append(TextSource(
                tokenizer, src["path"], chunk_len=chunk_len, stride=stride,
                extractor=src.get("extractor")
            ))
            self._weights.append(src.get("weight", 1.0))
        total = sum(self._weights)
        self._probs = [w / total for w in self._weights]
        print(f"Registered {len(self._source_objs)} sources; sampling probs: {self._probs}")

    def set_epoch(self, epoch):
        self.epoch = epoch

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        source_iters = [iter(src.chunks(rng)) for src in self._source_objs]
        buf = []
        while True:
            idx = rng.choices(range(len(source_iters)), weights=self._probs, k=1)[0]
            try:
                chunk = next(source_iters[idx])
            except StopIteration:
                source_iters[idx] = iter(self._source_objs[idx].chunks(rng))
                try:
                    chunk = next(source_iters[idx])
                except StopIteration:
                    continue
            buf.append(chunk)
            if len(buf) >= self.shuffle_buffer:
                rng.shuffle(buf)
                yield buf.pop(0)
        rng.shuffle(buf)
        for chunk in buf:
            yield chunk


# ═══════════════════════════════════════════════════════════════════════════════
# Model loading and training (reused from pretrain_cord_observer_4b.py)
# ═══════════════════════════════════════════════════════════════════════════════

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


def compute_hard_weights(base_logits, targets, mode="ce", alpha=1.0):
    """Compute per-token loss weights from base-model difficulty.

    mode='ce': weight by base cross-entropy relative to median (clamp 0.5..3.0).
    mode='wrong': up-weight tokens where base top-1 != target by factor (1+alpha).
    """
    flat_logits = base_logits.reshape(-1, base_logits.size(-1))
    flat_targets = targets.reshape(-1)
    if mode == "ce":
        ce = F.cross_entropy(flat_logits, flat_targets, reduction='none')
        median = ce.median()
        weights = torch.clamp(ce / (median + 1e-8), 0.5, 3.0) ** alpha
    elif mode == "wrong":
        pred = flat_logits.argmax(dim=-1)
        hard = (pred != flat_targets).float()
        weights = 1.0 + alpha * hard
    else:
        weights = torch.ones_like(flat_targets, dtype=torch.float32)
    return weights


def train_epoch(base_model, observer, loader, optimizer, grad_accum=4, grad_clip=1.0,
                steps_per_epoch=500, residual=False, hard_example_mode="none",
                hard_example_alpha=1.0):
    observer.train()
    total_loss = 0.0
    total_acc = 0.0
    steps = 0
    accum_steps = 0
    total_tokens = 0

    for batch_idx, batch in enumerate(loader):
        batch = batch.to(DEVICE)
        input_ids = batch[:, :-1]
        targets = batch[:, 1:]

        with torch.no_grad():
            out = base_model(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            hidden = out.hidden_states[-1]
            base_logits = out.logits
            # Hard-example weights always use the base model, independent of residual mode
            weights = None
            if hard_example_mode != "none":
                weights = compute_hard_weights(base_logits, targets,
                                               mode=hard_example_mode,
                                               alpha=hard_example_alpha)

        with torch.amp.autocast('cuda'):
            conf, imp, obs_logits = observer(hidden)
            if residual:
                combined_logits = base_logits + obs_logits
                logits_for_loss = combined_logits
            else:
                logits_for_loss = obs_logits

            flat_logits = logits_for_loss.reshape(-1, logits_for_loss.size(-1))
            flat_targets = targets.reshape(-1)
            ce = F.cross_entropy(flat_logits, flat_targets, reduction='none')
            if weights is not None:
                ce = ce * weights.to(ce.dtype)
                loss = ce.sum() / weights.sum()
            else:
                loss = ce.mean()

            preds = logits_for_loss.argmax(dim=-1)
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
        steps += 1

        if batch_idx % 20 == 0:
            acc = 100.0 * correct / targets.numel()
            print(f"  step {batch_idx:4d}  loss={loss.item() * grad_accum:.4f}  acc={acc:.2f}%")

        if steps >= steps_per_epoch:
            break

    if accum_steps % grad_accum != 0:
        torch.nn.utils.clip_grad_norm_(observer.parameters(), grad_clip)
        optimizer.step()
        optimizer.zero_grad()

    return {
        "loss": total_loss / steps,
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


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-len", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--steps-per-epoch", type=int, default=500)
    parser.add_argument("--val-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-gen-test", action="store_true")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--D", type=int, default=1040)
    parser.add_argument("--bottleneck-dim", type=int, default=None,
                        help="Bottleneck hidden dim before field projection (default: d_model)")
    parser.add_argument("--low-rank", type=int, default=None,
                        help="Rank for low-rank logit projection (default: full-rank)")
    parser.add_argument("--residual", action="store_true")
    parser.add_argument("--hard-example-mode", type=str, default="none",
                        choices=["none", "ce", "wrong"],
                        help="Weight training loss by base-model difficulty")
    parser.add_argument("--hard-example-alpha", type=float, default=1.0,
                        help="Scaling for hard-example weighting")
    parser.add_argument("--save-prefix", type=str, default="experiments/cord_observer_D1040_multidata")
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)
    base_model = load_base_model()

    d_model = base_model.config.text_config.hidden_size
    vocab_size = base_model.config.text_config.vocab_size

    observer = CordObserver(d_model, vocab_size, D=args.D,
                            bottleneck_dim=args.bottleneck_dim,
                            low_rank=args.low_rank).to(DEVICE).to(torch.bfloat16)

    for p in base_model.parameters():
        p.requires_grad = False
    base_model.eval()

    trainable = sum(p.numel() for p in observer.parameters() if p.requires_grad)
    bn = args.bottleneck_dim or d_model
    lr = args.low_rank or "full"
    print(f"CordObserver trainable params: {trainable:,}  (D={args.D}, bottleneck={bn}, logit_rank={lr})")

    if args.resume:
        print(f"Resuming observer from {args.resume}")
        observer.load_state_dict(torch.load(args.resume, weights_only=False))

    optimizer = torch.optim.AdamW(
        observer.parameters(), lr=args.lr, weight_decay=0.01, betas=(0.9, 0.95)
    )

    # Broad data mix: narrative, factual, educational, math, science
    sources = [
        {"path": "datasets/LightNovels.txt", "weight": 1.0},
        {"path": "datasets/TinyStories-Instruct-train.txt", "weight": 1.5},
        {"path": "datasets/wikitext103_train.txt", "weight": 1.0},
        {"path": "datasets/textbook_spelled_full.txt", "weight": 1.0},
        {"path": "datasets/research-math.jsonl.txt", "weight": 0.5, "extractor": "self_contained_problem"},
        {"path": "datasets/gsm8k_train.txt", "weight": 0.5},
        {"path": "datasets/physics_real_instruct.json", "weight": 0.3},
        {"path": "datasets/sciq_instruct.json", "weight": 0.3},
        {"path": "datasets/active/1M-GPT4-Augmented.parquet", "weight": 0.3, "extractor": "system_prompt,question,response"},
    ]

    dataset = MultiSourceTextDataset(tok, sources, chunk_len=args.chunk_len,
                                     stride=args.chunk_len // 2, seed=args.seed)
    loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)

    best_val_loss = float("inf")

    for epoch in range(args.epochs):
        print(f"\n=== Epoch {epoch + 1}/{args.epochs} ===")
        dataset.set_epoch(epoch)
        loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        t0 = time.time()
        metrics = train_epoch(base_model, observer, loader, optimizer,
                              grad_accum=args.grad_accum, steps_per_epoch=args.steps_per_epoch,
                              residual=args.residual,
                              hard_example_mode=args.hard_example_mode,
                              hard_example_alpha=args.hard_example_alpha)
        dt = time.time() - t0
        print(f"Epoch {epoch + 1} done in {dt:.1f}s  loss={metrics['loss']:.4f}  acc={metrics['acc']:.2f}%")

        dataset.set_epoch(0)
        val_loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        val_metrics = validate(base_model, observer, val_loader, val_steps=args.val_steps,
                               residual=args.residual)
        print(f"Val  loss={val_metrics['loss']:.4f}  acc={val_metrics['acc']:.2f}%")

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            torch.save(observer.state_dict(), f"{args.save_prefix}_best.pt")
            print("Saved best CordObserver")

        torch.save(observer.state_dict(), f"{args.save_prefix}_epoch{epoch + 1}.pt")

        if not args.no_gen_test:
            print("\n--- Generation test (50/50 blend) ---")
            text = generate_test(base_model, observer, tok, "The golden ratio appears in nature", max_new=40,
                                 residual=args.residual)
            print(f"Generated: {text}\n")

        print(f"Peak VRAM: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")
        torch.cuda.reset_peak_memory_stats()

    print("CordObserver pre-training complete.")
    print(f"Best checkpoint: {args.save_prefix}_best.pt (val_loss={best_val_loss:.4f})")


if __name__ == "__main__":
    main()
