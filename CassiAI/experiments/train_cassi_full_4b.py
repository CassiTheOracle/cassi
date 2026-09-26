#!/usr/bin/env python3
"""
End-to-end training of the full Cassi stack on frozen Qwen3.5-4B.

Trains:
  - Observer head (confidence, importance, next-token)
  - Specialist ensemble (5 competitive sparse heads)
  - Harmony gate (Qi-modulated blending)
  - Berry head (memory-to-logits projection)

Frozen:
  - Base model
  - Berry memory keys/values (updated online, not backpropped)
  - Qi-fluid (neutral during training)
  - Neuroplasticizer (inference-only)

Loss:
  L = L_combined + 0.1 * L_observer + 0.05 * L_specialist_diversity
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
sys.path.insert(0, "experiments")
from pretrain_cord_observer_4b_multidata import TextSource, MultiSourceTextDataset
from cassi.cord_optimizer import CordOptimizer
from cassi.cord_observer import CordObserver

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
LOCAL_MODEL_DIR = "qwen_models/Qwen3.5-4B"
DEVICE = "cuda"


# ═══════════════════════════════════════════════════════════════════════════════
# Cassi Components (batch-compatible)
# ═══════════════════════════════════════════════════════════════════════════════

# ObserverHead replaced by CordObserver (imported from cassi.cord_observer)

class SpecialistEnsemble(nn.Module):
    def __init__(self, d_model, vocab_size, n_specialists=5, bottleneck=64):
        super().__init__()
        self.n_specialists = n_specialists
        self.specialists = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, bottleneck), nn.GELU(),
                nn.Linear(bottleneck, vocab_size, bias=False),
            )
            for _ in range(n_specialists)
        ])
        for spec in self.specialists:
            nn.init.xavier_uniform_(spec[0].weight, gain=0.05)
            nn.init.zeros_(spec[0].bias)
            nn.init.xavier_uniform_(spec[2].weight, gain=0.05)
        self.gate = nn.Linear(d_model, n_specialists)
        nn.init.xavier_uniform_(self.gate.weight, gain=0.1)
        nn.init.zeros_(self.gate.bias)

    def forward(self, hidden):
        """hidden: [..., D] → combined [..., V], gates [..., N]"""
        biases = torch.stack([spec(hidden) for spec in self.specialists], dim=0)  # [N, ..., V]
        gates = F.softmax(self.gate(hidden) / PHI, dim=-1)  # [..., N]
        # Weighted sum over specialists (works for single token or full sequence)
        combined = torch.einsum('...n,n...v->...v', gates, biases)
        return combined, gates

    def diversity_loss(self, hidden):
        """Encourage specialists to disagree. hidden: [B, D]"""
        biases = torch.stack([spec(hidden) for spec in self.specialists], dim=0)  # [N, B, V]
        # Normalize per specialist per sample
        norms = F.normalize(biases, dim=-1)  # [N, B, V]
        # Average pairwise cosine similarity
        sims = torch.einsum('nbv,mbv->nm', norms, norms) / norms.size(1)  # [N, N]
        mask = 1.0 - torch.eye(self.n_specialists, device=sims.device)
        loss = (sims * mask).sum() / mask.sum()
        return loss


class HarmonyGate(nn.Module):
    def __init__(self, d_model, vocab_size, residual=False):
        super().__init__()
        self.residual = residual
        self.qi_scale = nn.Parameter(torch.tensor(1.0))
        self.conf_scale = nn.Parameter(torch.tensor(1.0))
        self.berry_head = nn.Sequential(
            nn.Linear(d_model, 256), nn.GELU(),
            nn.Linear(256, vocab_size, bias=False),
        )
        nn.init.xavier_uniform_(self.berry_head[0].weight, gain=0.05)
        nn.init.xavier_uniform_(self.berry_head[2].weight, gain=0.05)

    def forward(self, base_logits, obs_logits, berry_bias, spec_bias, qi, conf):
        """
        All logits: [B, V] or [V].
        qi, conf: scalars or [B].
        Returns blended logits [B, V] or [V], and weight dict.

        In residual mode, Cassi components output logit-space residuals and
        are added to base_logits: combined = base + w_obs*obs + w_spec*spec + w_berry*berry.
        """
        # Normalize dtypes to match this module's parameters
        dtype = next(self.parameters()).dtype
        if base_logits is not None:
            base_logits = base_logits.to(dtype)
        if obs_logits is not None:
            obs_logits = obs_logits.to(dtype)
        if berry_bias is not None:
            berry_bias = berry_bias.to(dtype)
        if spec_bias is not None:
            spec_bias = spec_bias.to(dtype)
        if isinstance(qi, torch.Tensor):
            qi = qi.to(dtype)
        if isinstance(conf, torch.Tensor):
            conf = conf.to(dtype)

        if berry_bias is not None:
            berry_logits = self.berry_head(berry_bias)
        else:
            berry_logits = None

        w_base = 0.5 + 0.5 * qi * conf
        w_obs = (1 - conf) * 0.15
        w_berry = (1 - qi) * 0.05
        w_spec = 0.05

        total = w_base + w_obs + w_berry + w_spec
        w_base = w_base / total
        w_obs = w_obs / total
        w_berry = w_berry / total
        w_spec = w_spec / total

        # Broadcast if batched
        if isinstance(w_base, torch.Tensor) and w_base.dim() > 0:
            w_base = w_base.unsqueeze(-1)
            w_obs = w_obs.unsqueeze(-1)
            w_berry = w_berry.unsqueeze(-1)
            w_spec = w_spec.unsqueeze(-1)

        if self.residual:
            # Logit-space residual combination
            out = base_logits
            if obs_logits is not None:
                out = out + w_obs * obs_logits
            if spec_bias is not None:
                out = out + w_spec * spec_bias
            if berry_logits is not None:
                out = out + w_berry * berry_logits
            blended_logits = out
        else:
            # Probability-space blending (legacy)
            base_p = F.softmax(base_logits, dim=-1)
            obs_p = F.softmax(obs_logits, dim=-1) if obs_logits is not None else base_p
            berry_p = F.softmax(berry_logits, dim=-1) if berry_logits is not None else base_p
            spec_p = F.softmax(spec_bias, dim=-1) if spec_bias is not None else base_p

            blended_p = w_base * base_p + w_obs * obs_p + w_berry * berry_p + w_spec * spec_p
            blended_logits = torch.log(blended_p + 1e-10)

        if isinstance(w_base, torch.Tensor) and w_base.dim() > 0:
            weights = {
                "w_base": w_base.mean().item(), "w_obs": w_obs.mean().item(),
                "w_berry": w_berry.mean().item(), "w_spec": w_spec.mean().item(),
            }
        else:
            weights = {
                "w_base": float(w_base), "w_obs": float(w_obs),
                "w_berry": float(w_berry), "w_spec": float(w_spec),
            }
        return blended_logits, weights


class BerryMemory(nn.Module):
    def __init__(self, d_model, n_slots=512):
        super().__init__()
        self.n_slots = n_slots
        self.register_buffer("keys", torch.randn(n_slots, d_model) * 0.01)
        self.register_buffer("values", torch.randn(n_slots, d_model) * 0.01)
        self.register_buffer("counts", torch.zeros(n_slots))
        self.register_buffer("ages", torch.zeros(n_slots))

    def store(self, hidden):
        """hidden: [D] single vector"""
        sims = F.cosine_similarity(hidden.unsqueeze(0), self.keys, dim=-1)
        best_idx = sims.argmax()
        if sims[best_idx] > 0.92:
            self.keys[best_idx] = 0.9 * self.keys[best_idx] + 0.1 * hidden.detach()
            self.values[best_idx] = 0.9 * self.values[best_idx] + 0.1 * hidden.detach()
            self.counts[best_idx] += 1
        else:
            score = self.counts * 0.3 - self.ages * 0.7
            idx = score.argmin()
            self.keys[idx] = hidden.detach()
            self.values[idx] = hidden.detach()
            self.counts[idx] = 1
            self.ages[idx] = 0
        self.ages += 1

    def retrieve(self, hidden, k=5):
        """hidden: [D] → retrieved [D] or None, hit_quality scalar"""
        sims = F.cosine_similarity(hidden.unsqueeze(0), self.keys, dim=-1)
        topk = sims.topk(k)
        if topk.values.max() < 0.5:
            return None, 0.0
        weights = F.softmax(topk.values / 0.1, dim=-1)
        retrieved = (weights.unsqueeze(-1) * self.values[topk.indices]).sum(dim=0)
        return retrieved, topk.values.mean().item()

    def reset_stats(self):
        self.counts.zero_()
        self.ages.zero_()


# ═══════════════════════════════════════════════════════════════════════════════
# Trainable Cassi Model
# ═══════════════════════════════════════════════════════════════════════════════

class CassiTrainableModel(nn.Module):
    def __init__(self, base_model, residual=False, observer_bottleneck_dim=None, observer_low_rank=None):
        super().__init__()
        self.base = base_model
        self.residual = residual
        d_model = base_model.config.text_config.hidden_size
        vocab_size = base_model.config.text_config.vocab_size

        self.observer = CordObserver(d_model, vocab_size, D=1040,
                                     bottleneck_dim=observer_bottleneck_dim,
                                     low_rank=observer_low_rank).to(DEVICE).to(torch.bfloat16)
        self.specialists = SpecialistEnsemble(d_model, vocab_size).to(DEVICE).to(torch.bfloat16)
        self.harmony = HarmonyGate(d_model, vocab_size, residual=residual).to(DEVICE).to(torch.bfloat16)
        self.berry = BerryMemory(d_model, n_slots=512).to(DEVICE).to(torch.bfloat16)

        # Freeze base model
        for p in base_model.parameters():
            p.requires_grad = False
        base_model.eval()

    def forward(self, input_ids, targets, use_berry=True):
        """
        input_ids: [B, L]
        targets: [B, L]
        use_berry: bool — enable berry memory store/retrieve
        Returns loss scalar.
        """
        B, L = input_ids.shape
        V = self.base.config.text_config.vocab_size

        with torch.no_grad():
            out = self.base(input_ids=input_ids, use_cache=False, output_hidden_states=True)
            base_logits = out.logits.to(torch.bfloat16)  # [B, L, V]
            hidden = out.hidden_states[-1].to(torch.bfloat16)  # [B, L, D]

        # Vectorized observer over full sequence
        conf, imp, obs_logits = self.observer(hidden)  # [B,L], [B,L], [B,L,V]

        # Vectorized specialists over full sequence
        spec_bias, spec_gates = self.specialists(hidden)  # [B,L,V], [B,L,N]

        # Berry memory: loop over positions (stateful, can't vectorize)
        if use_berry:
            berry_biases = []
            for l in range(L):
                h = hidden[:, l, :]  # [B, D]
                berry_vals = []
                for b in range(B):
                    self.berry.store(h[b])
                    val, hit = self.berry.retrieve(h[b], k=5)
                    berry_vals.append(val if val is not None else torch.zeros_like(h[b]))
                berry_biases.append(torch.stack(berry_vals, dim=0))  # [B, D]
            berry_bias = torch.stack(berry_biases, dim=1)  # [B, L, D]
        else:
            berry_bias = None

        # Vectorized harmony gate over full sequence
        if berry_bias is not None:
            berry_bias = berry_bias.to(torch.bfloat16)
        qi = torch.tensor(0.9, device=DEVICE, dtype=torch.bfloat16)
        combined, _ = self.harmony(base_logits, obs_logits, berry_bias, spec_bias, qi, conf.mean())

        # Combined loss
        loss_combined = F.cross_entropy(
            combined.reshape(-1, V),
            targets.reshape(-1),
        )

        if self.residual:
            # In residual mode, the observer is already trained via the combined loss
            # (base + obs residual is what the harmony gate outputs). No auxiliary loss needed.
            loss = loss_combined
            return loss, {
                "combined": loss_combined.item(),
                "observer": loss_combined.item(),
                "diversity": 0.0,
            }

        # Observer auxiliary loss (legacy direct prediction mode)
        loss_observer = F.cross_entropy(
            obs_logits.reshape(-1, V),
            targets.reshape(-1),
        )

        # Specialist diversity loss
        loss_div = self.specialists.diversity_loss(hidden.reshape(-1, hidden.size(-1)))

        loss = loss_combined + 0.1 * loss_observer + 0.05 * loss_div
        return loss, {
            "combined": loss_combined.item(),
            "observer": loss_observer.item(),
            "diversity": loss_div.item(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Data & Training
# ═══════════════════════════════════════════════════════════════════════════════

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
        """Yield token chunks from file, optionally skipping a random prefix."""
        buffer = ""
        read_so_far = 0
        chunk_size = 1_048_576  # 1MB

        # Skip random prefix for epoch variety
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
        # Random start offset up to 1MB so each epoch begins at a different place
        start_offset = rng.randint(0, 1_048_576)

        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            buf = []
            for chunk in self._raw_chunks(f, start_offset=start_offset):
                buf.append(chunk)
                if len(buf) >= self.shuffle_buffer:
                    rng.shuffle(buf)
                    yield buf.pop(0)
            # Drain remaining buffer
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


def train_epoch(cassi, loader, optimizer, grad_accum=4, grad_clip=1.0, steps_per_epoch=500, use_berry=True):
    cassi.train()
    total_loss = 0.0
    total_combined = 0.0
    total_observer = 0.0
    total_div = 0.0
    steps = 0
    accum_steps = 0

    for batch_idx, batch in enumerate(loader):
        batch = batch.to(DEVICE)
        input_ids = batch[:, :-1]
        targets = batch[:, 1:]

        with torch.amp.autocast('cuda'):
            loss, metrics = cassi(input_ids, targets, use_berry=use_berry)
            loss = loss / grad_accum

        loss.backward()
        accum_steps += 1

        if accum_steps % grad_accum == 0:
            torch.nn.utils.clip_grad_norm_(cassi.parameters(), grad_clip)
            optimizer.step()
            optimizer.zero_grad()
            torch.cuda.empty_cache()

        total_loss += loss.item() * grad_accum
        total_combined += metrics["combined"]
        total_observer += metrics["observer"]
        total_div += metrics["diversity"]
        steps += 1

        if batch_idx % 20 == 0:
            print(f"  step {batch_idx:4d}  loss={loss.item() * grad_accum:.4f}  "
                  f"combined={metrics['combined']:.4f}  obs={metrics['observer']:.4f}  "
                  f"div={metrics['diversity']:.4f}")

        if steps >= steps_per_epoch:
            break

    if accum_steps % grad_accum != 0:
        torch.nn.utils.clip_grad_norm_(cassi.parameters(), grad_clip)
        optimizer.step()
        optimizer.zero_grad()

    return {
        "loss": total_loss / steps,
        "combined": total_combined / steps,
        "observer": total_observer / steps,
        "diversity": total_div / steps,
    }


def validate(cassi, loader, val_steps=50, use_berry=True):
    cassi.eval()
    total_loss = 0.0
    steps = 0
    with torch.no_grad(), torch.amp.autocast('cuda'):
        for batch in loader:
            batch = batch.to(DEVICE)
            input_ids = batch[:, :-1]
            targets = batch[:, 1:]
            loss, _ = cassi(input_ids, targets, use_berry=use_berry)
            total_loss += loss.item()
            steps += 1
            if steps >= val_steps:
                break
    return total_loss / steps


def generate_test(cassi, tok, prompt, max_new=40):
    """Quick generation test with trained components."""
    cassi.eval()
    input_ids = tok(prompt, return_tensors="pt").to(DEVICE)["input_ids"][0].tolist()
    past = None
    berry = cassi.berry
    berry.reset_stats()

    for _ in range(max_new):
        ids = torch.tensor([input_ids] if past is None else [[input_ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = cassi.base(input_ids=ids, past_key_values=past, use_cache=True, output_hidden_states=True)
            base_logits = out.logits[0, -1, :].float()
            hidden = out.hidden_states[-1][0, -1, :].to(torch.bfloat16)
            past = out.past_key_values

            conf, imp, obs_logits = cassi.observer(hidden)
            spec_bias, spec_gates = cassi.specialists(hidden)

            berry.store(hidden)
            val, hit = berry.retrieve(hidden, k=5)
            berry_bias = val.float() if val is not None else None

            qi = torch.tensor(0.9, device=DEVICE)
            combined, weights = cassi.harmony(base_logits, obs_logits, berry_bias, spec_bias, qi, conf.mean())

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
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--steps-per-epoch", type=int, default=500)
    parser.add_argument("--val-steps", type=int, default=50)
    parser.add_argument("--no-berry", action="store_true")
    parser.add_argument("--data-limit", type=int, default=None, help="Limit data read to N chars (for smoke tests)")
    parser.add_argument("--no-gen-test", action="store_true", help="Skip generation test at end of epoch")
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--residual", action="store_true", help="Use residual logit mode (Cassi components correct base model)")
    parser.add_argument("--save-prefix", type=str, default="experiments/cassi_full_4b",
                        help="Prefix for saved checkpoints")
    parser.add_argument("--data-list", type=str, default=None,
                        help='JSON list of sources, e.g. [{"path":"data.txt","weight":1.0}]')
    parser.add_argument("--observer-bottleneck-dim", type=int, default=None,
                        help="Bottleneck dim before CordObserver field projection")
    parser.add_argument("--observer-low-rank", type=int, default=None,
                        help="Rank for low-rank CordObserver logit projection")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)
    base_model = load_base_model()
    cassi = CassiTrainableModel(base_model, residual=args.residual,
                                observer_bottleneck_dim=args.observer_bottleneck_dim,
                                observer_low_rank=args.observer_low_rank).to(DEVICE)

    # Count trainable parameters
    trainable = sum(p.numel() for p in cassi.parameters() if p.requires_grad)
    total = sum(p.numel() for p in cassi.parameters())
    print(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    if args.resume:
        print(f"Resuming from {args.resume}")
        ckpt = torch.load(args.resume, weights_only=False)
        # Detect if this is an observer-only checkpoint (no 'observer.' prefix)
        if any(k.startswith("observer.") for k in ckpt.keys()):
            cassi.load_state_dict(ckpt, strict=False)
        else:
            # Pre-trained observer checkpoint — prepend 'observer.' to keys
            mapped = {f"observer.{k}": v for k, v in ckpt.items()}
            cassi.load_state_dict(mapped, strict=False)
            print("  Loaded observer-only checkpoint into cassi.observer")

    optimizer = CordOptimizer(
        (p for p in cassi.parameters() if p.requires_grad),
        lr=args.lr, weight_decay=0.01
    )
    # No GradScaler needed — bfloat16 has float32 range, no overflow issues

    if args.data_list:
        sources = json.loads(args.data_list)
        dataset = MultiSourceTextDataset(tok, sources, chunk_len=args.chunk_len,
                                         stride=args.chunk_len // 2, seed=args.seed)
    else:
        dataset = TextChunkDataset(tok, args.data, chunk_len=args.chunk_len, stride=args.chunk_len // 2, data_limit=args.data_limit)
    loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)

    best_val = float("inf")

    for epoch in range(args.epochs):
        print(f"\n=== Epoch {epoch + 1}/{args.epochs} ===")
        dataset.set_epoch(epoch)
        loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        cassi.berry.reset_stats()
        t0 = time.time()
        metrics = train_epoch(cassi, loader, optimizer,
                              grad_accum=args.grad_accum, steps_per_epoch=args.steps_per_epoch, use_berry=not args.no_berry)
        dt = time.time() - t0
        print(f"Epoch {epoch + 1} done in {dt:.1f}s  loss={metrics['loss']:.4f}  "
              f"combined={metrics['combined']:.4f}  obs={metrics['observer']:.4f}  "
              f"div={metrics['diversity']:.4f}")

        # Validation on a fixed-seed loader for consistent comparison across epochs
        dataset.set_epoch(0)
        val_loader = DataLoader(dataset, batch_size=args.batch_size, num_workers=0)
        val_loss = validate(cassi, val_loader, val_steps=args.val_steps, use_berry=not args.no_berry)
        print(f"Val loss: {val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            # Save only Cassi params (exclude frozen base model)
            trainable_sd = {k: v for k, v in cassi.state_dict().items() if not k.startswith("base.")}
            torch.save(trainable_sd, f"{args.save_prefix}_best.pt")
            print("Saved best")

        trainable_sd = {k: v for k, v in cassi.state_dict().items() if not k.startswith("base.")}
        torch.save(trainable_sd, f"{args.save_prefix}_epoch{epoch + 1}.pt")

        # Free memory to reduce fragmentation across epochs
        del val_loader
        torch.cuda.empty_cache()

        if not args.no_gen_test:
            print("\n--- Generation test ---")
            text = generate_test(cassi, tok, "The golden ratio appears in nature", max_new=40)
            print(f"Generated: {text}\n")

    print("Training complete.")


if __name__ == "__main__":
    main()
