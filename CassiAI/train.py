#!/usr/bin/env python3
"""Unified Trainer — one script for physics, text, standard, and self-driven training.

Usage:
  # Physics standard
  python train.py --data physics --epochs 20

  # Text standard (loads datasets/active/ + optional --text fallback)
  python train.py --data text --epochs 10 --steps-per-epoch 2000

  # Self-driven consistency (physics or text)
  python train.py --data physics --self-driven --consistency-weight 0.1

  # Adaptive LR + curriculum + mixed precision
  python train.py --data text --adaptive --curriculum --mixed-precision
"""

import torch
import torch.nn.functional as F
import numpy as np
import time
import os
import argparse
import json

from cassi.harmony_brain import HarmonyBrain
from cassi.adaptive_trainer import AdaptiveTrainer
from cassi.streaming_text_sampler import StreamingTextSampler, MixedPrecisionTrainer
from cassi.cord import PHI

DEV = 'cuda'
SPINE_PHYSICS = 'checkpoints/spine_physics.pt'
SPINE_TEXT = 'checkpoints/spine_text.pt'
SAVE_PATH = 'cassi_latest.pt'
LOG_PATH = 'cassi_train.log'

RUN_ID = hex(int(time.time() * 1e6))[-6:]

WD = 0.01
COHERENCE_WEIGHT = 0.01


def log_print(msg):
    line = f"[{RUN_ID}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')
        f.flush()


def save_checkpoint(path, model, val_mae, epoch):
    torch.save({'model': model.state_dict(), 'val_mae': val_mae, 'epoch': epoch + 1}, path)


class PhysicsDataLoader:
    """Load physics_cache_v10.pt and serve batches."""

    def __init__(self, cache_path='datasets/physics_cache_v10.pt', val_frac=0.2, seed=42):
        cache = torch.load(cache_path, map_location='cpu', weights_only=False)
        self.wins = torch.stack(cache['windows']).to(DEV)
        self.n = len(self.wins)

        rng = np.random.RandomState(seed)
        perm = rng.permutation(self.n)
        split = int(self.n * (1 - val_frac))
        self.train_idx = perm[:split]
        self.val_idx = perm[split:]
        self.nt, self.nv = len(self.train_idx), len(self.val_idx)

    def sample_train_batch(self, batch_size, rng):
        idx = rng.choice(self.train_idx, size=batch_size, replace=False)
        x = self.wins[idx][:, :4]
        y = self.wins[idx][:, 4]
        return x, y

    def sample_val_batch(self, batch_size, rng):
        idx = rng.choice(self.val_idx, size=min(batch_size, self.nv), replace=False)
        x = self.wins[idx][:, :4]
        y = self.wins[idx][:, 4]
        return x, y

    def val_steps(self, batch_size):
        return max(1, self.nv // batch_size)


class TextDataLoader:
    """Streaming text loader with optional active-directory loading."""

    def __init__(self, text_path=None, active_dir='datasets/active', val_frac=0.02,
                 window_bytes=1024, stride=256, seed=42):
        self.window_bytes = window_bytes
        self.stride = stride
        self.sampler = StreamingTextSampler(None, window_bytes=window_bytes,
                                            stride=stride, device=DEV)

        # Load active directory
        if active_dir and os.path.exists(active_dir):
            for fname in sorted(os.listdir(active_dir)):
                path = os.path.join(active_dir, fname)
                if os.path.isfile(path):
                    self._append_file(path)

        # Fallback to single file
        if self.sampler.size == 0 and text_path and os.path.exists(text_path):
            with open(text_path, 'rb') as f:
                self.sampler.append(f.read())

        self.total_size = self.sampler.size
        self.n_val = int(self.total_size * val_frac)
        self.n_train = self.total_size - self.n_val
        self.val_offset = self.n_train

        self.train_rng = np.random.RandomState(seed)
        self.val_rng = np.random.RandomState(seed + 1)

    def _append_file(self, path):
        fname = os.path.basename(path)
        ext = os.path.splitext(fname)[1].lower()
        try:
            if ext == '.txt':
                with open(path, 'rb') as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        self.sampler.append(chunk)
            elif ext in ('.json', '.jsonl'):
                self._append_json(path)
            elif ext == '.parquet':
                self._append_parquet(path)
        except Exception as e:
            log_print(f"  Error loading {fname}: {e}")

    def _append_json(self, path):
        texts = []
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        try:
            obj = json.loads(content)
            if isinstance(obj, dict) and 'chars' in obj and 'sequences' in obj:
                chars = obj['chars']
                for seq in obj['sequences']:
                    decoded = ''.join(chars[t] for t in seq if 0 <= t < len(chars))
                    decoded = decoded.replace(obj.get('user_tag', ''), '\n[User] ')
                    decoded = decoded.replace(obj.get('asst_tag', ''), '\n[Asst] ')
                    decoded = decoded.replace(obj.get('end_tag', ''), '')
                    texts.append(decoded.strip())
            elif isinstance(obj, list):
                texts = [x for x in obj if isinstance(x, str)]
        except json.JSONDecodeError:
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        for key in ('text', 'content', 'instruction', 'response'):
                            if key in obj and isinstance(obj[key], str):
                                texts.append(obj[key])
                                break
                except json.JSONDecodeError:
                    pass
        if texts:
            self.sampler.append('\n\n'.join(texts).encode('utf-8'))

    def _append_parquet(self, path):
        try:
            import pyarrow.parquet as pq
            df = pq.read_table(path).to_pandas()
            for col in df.columns:
                if df[col].dtype == object:
                    sample = df[col].dropna().iloc[:5].tolist()
                    if any(isinstance(x, str) and len(x) > 20 for x in sample):
                        texts = df[col].dropna().astype(str).tolist()
                        self.sampler.append('\n\n'.join(texts).encode('utf-8'))
                        break
        except ImportError:
            pass

    def sample_train_batch(self, batch_size, rng=None, curriculum_weights=None):
        if rng is None:
            rng = self.train_rng
        return self.sampler.sample_batch(batch_size, rng, curriculum_weights)

    def sample_val_batch(self, batch_size, rng=None):
        if rng is None:
            rng = self.val_rng
        max_start = self.sampler.size - self.val_offset - self.window_bytes - self.stride
        if max_start > 0:
            starts = rng.randint(self.val_offset, self.val_offset + max_start, size=batch_size)
        else:
            max_start = self.sampler.size - self.window_bytes - self.stride
            max_start = max(1, max_start)
            starts = rng.randint(0, max_start, size=batch_size)

        idx = np.arange(self.window_bytes)
        x_idx = starts[:, None] + idx[None, :]
        y_idx = (starts + self.stride)[:, None] + idx[None, :]
        data = self.sampler._ring[:self.sampler._ring_size]
        x = torch.from_numpy(data[x_idx]).to(DEV, non_blocking=True)
        y = torch.from_numpy(data[y_idx]).to(DEV, non_blocking=True)
        return x, y

    def val_steps(self, batch_size):
        return max(1, self.n_val // (batch_size * self.stride) // 10)


def build_optimizer(model, lr_spine, lr_brain):
    spine_params = []
    brain_params = []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if 'spine.' in name:
            spine_params.append(p)
        else:
            brain_params.append(p)
    param_groups = [
        {'params': brain_params, 'lr': lr_brain, 'name': 'brain'},
        {'params': spine_params, 'lr': lr_spine, 'name': 'spine'},
    ]
    return torch.optim.AdamW(param_groups, weight_decay=WD), param_groups


def train_epoch(model, loader, opt, mp_trainer, args, adaptive=None):
    """Unified training epoch with optional self-driven consistency loss."""
    model.train()
    epoch_loss = epoch_pred = epoch_coherence = epoch_cons = 0.0
    n_batches = n_cons = 0
    rng = np.random.RandomState(42 + args.epoch)
    cons_weight = getattr(args, 'consistency_weight', 0)
    use_cons = cons_weight > 0

    for step in range(args.steps_per_epoch):
        if args.data == 'physics':
            x, y = loader.sample_train_batch(args.bs, rng)
            y_field = None
        else:
            x, y, _ = loader.sample_train_batch(args.bs, rng,
                adaptive.sample_surprises if (adaptive and args.curriculum) else None)
            y_field = model.spine.byte_encoder.encode_sequence(y, T=1).squeeze(1)

        model.reset_workspace(len(x))
        pred, info = model(x, use_memory=True, return_workspace=True,
                           byte_mode=(args.data == 'text'))

        loss_pred = F.mse_loss(pred, y_field if y_field is not None else y)
        coherence = info['conscious'].pow(2).mean()
        loss = loss_pred + COHERENCE_WEIGHT * coherence

        # Consistency: predict with one frame replaced by prediction
        if use_cons and n_batches % 4 == 0 and len(x) == args.bs:
            with torch.no_grad():
                pred_detach = pred.detach()
            x_self = x.clone()
            x_self[:, 2, :] = pred_detach
            model.reset_workspace(len(x))
            pred_self = model(x_self, use_memory=True, return_workspace=False,
                              byte_mode=(args.data == 'text'))
            loss_cons = F.mse_loss(pred_self, pred_detach)
            loss = loss + cons_weight * loss_cons
            epoch_cons += loss_cons.item() * len(x)
            n_cons += 1

        if not torch.isfinite(loss):
            continue

        if mp_trainer and mp_trainer.enabled:
            mp_trainer.scaler.scale(loss).backward()
            mp_trainer.optimizer_step(clip_grad=1.0)
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            opt.zero_grad()

        if adaptive:
            adaptive.update_signals(info, loss_pred.item())
            if 'conscious' in info:
                per_sample = info['conscious'].norm(dim=-1).detach().cpu().numpy()
                adaptive.record_sample_surprise(
                    np.arange(step * args.bs, (step + 1) * args.bs) % loader.n_train,
                    per_sample)

        epoch_loss += loss.item() * len(x)
        epoch_pred += loss_pred.item() * len(x)
        epoch_coherence += coherence.item() * len(x)
        n_batches += 1

    n = n_batches * args.bs
    if use_cons:
        cons_avg = epoch_cons / max(1, n_cons * args.bs)
        return epoch_loss / n, epoch_pred / n, epoch_coherence / n, cons_avg
    return epoch_loss / n, epoch_pred / n, epoch_coherence / n


def validate(model, loader, args):
    model.eval()
    val_mae = val_mse = val_surprise = val_harmony = val_k = 0.0
    val_n = 0
    steps = loader.val_steps(args.bs)

    with torch.no_grad():
        for _ in range(steps):
            if args.data == 'physics':
                x, y = loader.sample_val_batch(args.bs, np.random.RandomState(43))
            else:
                x, y = loader.sample_val_batch(args.bs)

            model.reset_workspace(len(x))
            pred, info = model(x, use_memory=True, return_workspace=True,
                               byte_mode=(args.data == 'text'))

            if args.data == 'text':
                y_field = model.spine.byte_encoder.encode_sequence(y, T=1).squeeze(1)
                val_mae += F.l1_loss(pred, y_field).item() * len(x)
                val_mse += F.mse_loss(pred, y_field).item() * len(x)
            else:
                val_mae += F.l1_loss(pred, y).item() * len(x)
                val_mse += F.mse_loss(pred, y).item() * len(x)

            val_surprise += info['surprise'] * len(x)
            val_harmony += info['mean_harmony'].mean().item() * len(x)
            if 'k_eff' in info:
                val_k += info['k_eff'].float().mean().item() * len(x)
            val_n += len(x)

    return {
        'mae': val_mae / val_n,
        'mse': val_mse / val_n,
        'surprise': val_surprise / val_n,
        'harmony': val_harmony / val_n,
        'k': val_k / val_n,
    }


def generate_text_samples(model, loader, args, n_samples=3):
    """Generate text samples during validation."""
    if not hasattr(model.spine, 'byte_encoder'):
        log_print("  GEN: spine has no byte_encoder — skipping generation")
        return

    model.eval()
    window_bytes = loader.window_bytes
    seeds = []

    # Parse fixed seeds
    if args.seed:
        seeds = [s.strip().encode('utf-8') for s in args.seed.split(',') if s.strip()]

    # Fill remaining with random dataset windows
    if len(seeds) < n_samples:
        rng = np.random.RandomState(42 + args.epoch)
        data = loader.sampler._ring[:loader.sampler._ring_size]
        max_start = max(1, loader.sampler.size - window_bytes)
        for _ in range(n_samples - len(seeds)):
            start = rng.randint(0, max_start)
            seeds.append(bytearray(data[start:start + window_bytes]))

    with torch.no_grad():
        for i, seed_bytes in enumerate(seeds[:n_samples]):
            # Pad/truncate to exact window size
            seed_bytes = bytes(seed_bytes)[:window_bytes]
            seed_bytes = seed_bytes + b'\x00' * (window_bytes - len(seed_bytes))

            x = torch.tensor(list(seed_bytes), dtype=torch.uint8).unsqueeze(0).to(DEV)
            model.reset_workspace(1)
            pred = model(x, use_memory=True, return_workspace=False, byte_mode=True)

            # Decode prediction back to bytes
            try:
                pred_bytes = model.spine.byte_encoder.decode_field_greedy(pred[0])
                pred_text = pred_bytes.decode('utf-8', errors='replace')
            except Exception as e:
                pred_text = f"<decode error: {e}>"

            seed_text = seed_bytes.decode('utf-8', errors='replace')
            log_print(f"  GEN[{i+1}] seed: {seed_text[:100]!r}")
            log_print(f"  GEN[{i+1}] pred: {pred_text[:100]!r}")


def main():
    parser = argparse.ArgumentParser(description='Unified Cassi Trainer')
    parser.add_argument('--data', choices=['physics', 'text'], default='physics')
    parser.add_argument('--text', default='datasets/TinyStories-Instruct-train.txt')
    parser.add_argument('--active-dir', default='datasets/active')
    parser.add_argument('--cache', default='datasets/physics_cache_v10.pt')
    parser.add_argument('--spine', default=None, help='Spine checkpoint (auto-selected by --data if omitted)')
    parser.add_argument('--save', default=SAVE_PATH)
    parser.add_argument('--resume', action='store_true')

    # Model config
    parser.add_argument('--D', type=int, default=1040)
    parser.add_argument('--specialists', type=int, default=13)
    parser.add_argument('--mode', default='sparse', choices=['qi', 'gated', 'combined', 'sparse'])
    parser.add_argument('--min-k', type=int, default=2)
    parser.add_argument('--byte-mode', action='store_true', help='Force byte mode')

    # Training config
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--bs', type=int, default=1024)
    parser.add_argument('--steps-per-epoch', type=int, default=None)
    parser.add_argument('--lr-spine', type=float, default=5e-6)
    parser.add_argument('--lr-brain', type=float, default=2e-4)
    parser.add_argument('--save-every', type=int, default=10)
    parser.add_argument('--patience', type=int, default=15)
    parser.add_argument('--val-frac', type=float, default=0.02)

    # Features
    parser.add_argument('--mixed-precision', action='store_true')
    parser.add_argument('--adaptive', action='store_true', help='Adaptive LR via surprise/harmony')
    parser.add_argument('--curriculum', action='store_true', help='High-surprise sample resampling')
    parser.add_argument('--self-driven', action='store_true', help='Consistency self-driving')
    parser.add_argument('--consistency-weight', type=float, default=0.1)
    parser.add_argument('--seed', default=None, help='Comma-separated seed strings for text generation (random from dataset if omitted)')
    parser.add_argument('--gen-samples', type=int, default=3, help='Number of text samples to generate per eval')
    parser.add_argument('--wave-encoder', action='store_true', default=False, help='Use sinusoidal wave encoder')

    # Spine control
    parser.add_argument('--freeze-spine', action='store_true')
    parser.add_argument('--unfreeze-spine', action='store_true')

    args = parser.parse_args()
    args.epoch = 0  # set during loop

    # Auto-select spine based on data mode
    if args.spine is None:
        args.spine = SPINE_TEXT if args.data == 'text' else SPINE_PHYSICS

    # Default wave encoder for text
    if args.data == 'text' and not args.wave_encoder:
        args.wave_encoder = True

    from datetime import datetime
    log_print(f"{'='*60}")
    log_print(f"Cassi Unified Trainer  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print(f"Data: {args.data}  Mode: {args.mode}  Specialists: {args.specialists}")
    log_print(f"Epochs: {args.epochs}  Patience: {args.patience}")
    log_print(f"Wave encoder: {args.wave_encoder}")
    log_print(f"Self-driven: {args.self_driven}  Adaptive: {args.adaptive}  Curriculum: {args.curriculum}")
    log_print(f"Mixed precision: {args.mixed_precision}")
    log_print(f"{'='*60}")

    # Data loader
    if args.data == 'physics':
        loader = PhysicsDataLoader(args.cache, val_frac=args.val_frac)
        args.steps_per_epoch = args.steps_per_epoch or (loader.nt // args.bs)
        byte_mode = args.byte_mode
    else:
        loader = TextDataLoader(args.text, args.active_dir, val_frac=args.val_frac)
        args.steps_per_epoch = args.steps_per_epoch or 2000
        byte_mode = True

    log_print(f"Train samples: {loader.nt if hasattr(loader, 'nt') else loader.n_train:,}")
    log_print(f"Val samples:   {loader.nv if hasattr(loader, 'nv') else loader.n_val:,}")
    log_print(f"Steps/epoch:   {args.steps_per_epoch:,}")

    # Model
    model = HarmonyBrain(
        D=args.D, n_specialists=args.specialists, n_slots=512,
        memory_value_dim=26, readout_hidden=520,
        byte_mode=byte_mode, mode=args.mode, min_k=args.min_k
    ).to(DEV)

    model.load_spine(args.spine)
    log_print("Spine loaded")

    # Replace byte_encoder with wave encoder for text mode
    if args.wave_encoder and args.data == 'text':
        from cassi.text_codec import WaveByteEncoder
        wave_enc = WaveByteEncoder(window_bytes=1024, dim_field=1024, T=4).to(DEV)
        model.spine.byte_encoder = wave_enc
        log_print("Wave encoder installed")

    if args.freeze_spine or args.data == 'text':
        model.freeze_spine()
        # But keep wave encoder gain trainable
        if args.wave_encoder and hasattr(model.spine.byte_encoder, 'gain'):
            model.spine.byte_encoder.gain.requires_grad = True
        log_print("Spine FROZEN (wave gain trainable)")
    elif args.unfreeze_spine:
        model.unfreeze_spine()
        log_print("Spine UNFROZEN")

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log_print(f"Trainable params: {n_params:,}")

    # Optimizer
    if args.unfreeze_spine or (args.data == 'physics' and not args.freeze_spine):
        opt, param_groups = build_optimizer(model, args.lr_spine, args.lr_brain)
        for g in param_groups:
            log_print(f"  {g['name']}: {len(g['params'])} tensors, lr={g['lr']}")
    else:
        opt = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=args.lr_brain, weight_decay=WD
        )

    # Mixed precision
    mp_trainer = MixedPrecisionTrainer(model, opt, enabled=args.mixed_precision)

    # Adaptive trainer
    adaptive = AdaptiveTrainer(model, opt, lr_base=args.lr_brain) if args.adaptive else None

    best_val = float('inf')
    best_state = None
    best_ep = 0
    start_ep = 0
    no_improve = 0

    if args.resume and os.path.exists(args.save):
        ck = torch.load(args.save, map_location=DEV, weights_only=False)
        skip = ['workspace_fwd', 'workspace_rev', 'field_history', 'qi_fluid',
                'harmony_state', 'specialist_energy']
        state = {k: v for k, v in ck['model'].items() if k not in skip}
        model.load_state_dict(state, strict=False)
        best_val = ck.get('val_mae', float('inf'))
        start_ep = ck.get('epoch', 0)
        log_print(f"Resumed from {args.save}  epoch={start_ep}  val_mae={best_val:.4f}")

    t_start = time.perf_counter()

    for ep in range(start_ep, args.epochs):
        args.epoch = ep

        result = train_epoch(model, loader, opt, mp_trainer, args, adaptive)
        if args.self_driven:
            train_loss, train_pred, train_coherence, train_cons = result
        else:
            train_loss, train_pred, train_coherence = result
            train_cons = 0.0

        if adaptive:
            new_lr = adaptive.adapt_lr()
            log_print(f"  Adaptive LR: {new_lr:.2e}")

        # Validation every 2 epochs (or first/last)
        do_val = (ep + 1) % 2 == 0 or ep == start_ep or ep == args.epochs - 1

        if do_val:
            v = validate(model, loader, args)

            if args.data == 'text':
                generate_text_samples(model, loader, args, n_samples=args.gen_samples)

            improved = v['mae'] < best_val
            if improved:
                best_val = v['mae']
                best_state = {k: v.clone().cpu() for k, v in model.state_dict().items()}
                best_ep = ep
                no_improve = 0
            else:
                no_improve += 1

            elapsed = time.perf_counter() - t_start
            status = adaptive.get_status() if adaptive else {}
            parts = [
                f"ep {ep+1:4d}",
                f"train={train_pred:.4f}",
                f"val_mae={v['mae']:.4f}",
                f"best={best_val:.4f}",
                f"surprise={v['surprise']:.2f}",
                f"harmony={v['harmony']:.2f}",
                f"k={v['k']:.2f}",
                f"lr={status.get('lr', args.lr_brain):.2e}",
            ]
            if args.self_driven:
                parts.insert(2, f"cons={train_cons:.4f}")
            log_print(f"  {'  '.join(parts)}  [{int(elapsed//60)}m{int(elapsed%60):02d}s]")

            if (ep + 1) % args.save_every == 0 or (improved and ep > 0):
                save_checkpoint(args.save.replace('.pt', '_latest.pt'), model, v['mae'], ep)

            if adaptive and adaptive.should_stop():
                log_print(f"  Adaptive stop at epoch {ep+1}")
                break
            if no_improve >= args.patience:
                log_print(f"  Early stop at epoch {ep+1}")
                break
        else:
            elapsed = time.perf_counter() - t_start
            log_print(f"  ep {ep+1:4d}  train={train_pred:.4f}  "
                      f"[{int(elapsed//60)}m{int(elapsed%60):02d}s]")

        torch.cuda.empty_cache()

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    elapsed = time.perf_counter() - t_start
    log_print(f"\n  Best: epoch {best_ep+1}  val_mae={best_val:.4f}  "
              f"[{int(elapsed//60)}m{int(elapsed%60):02d}s]")

    torch.save({'model': best_state, 'val_mae': best_val, 'epoch': best_ep + 1}, args.save)
    log_print(f"\nSaved {args.save}  val_mae={best_val:.4f}")


if __name__ == '__main__':
    main()
