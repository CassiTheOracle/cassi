#!/usr/bin/env python3
"""ManifoldCord streaming trainer with file-extension tagged data.

Files are enclosed in [FILE:ext]...[/FILE] byte markers so the model learns
file-type-specific patterns. Any file extension is supported — tags are
generated dynamically from the actual file extension.

Usage:
    python3 train_manifold.py --N 128 --d 256 --epochs 50 --num-windows 4
    python3 train_manifold.py --N 256 --d 1024 --num-windows 4 \
        --checkpoint checkpoints/N256_d1024_muon/muon_latest.pt
    python3 train_manifold.py --no-tag-files  # disable file tags
"""

import argparse
import json
import os
import sys
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ.setdefault('ABSL_MIN_LOG_LEVEL', '2')
os.environ.setdefault('PYTORCH_HIP_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('HSA_ENABLE_SDMA', '0')

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from manifold_cord import ManifoldCord
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from cassi.qi_gated_sgd import QiGatedSGD
from cassi.streaming_text_sampler import StreamingTextSampler
from experiments.train_langevin_text import (
    sample_train_batch, sample_val_batch,
)


# ════════════════════════════════════════════════
#  File-Extension Tagged Data Loader
# ════════════════════════════════════════════════

def _file_tag(ext: str) -> bytes:
    """Return opening file-type tag bytes — dynamic, any extension."""
    ext_clean = ext.lstrip('.').lower()
    return f'[FILE:{ext_clean}]\n'.encode('utf-8')

_END_TAG = b'\n[/FILE]\n'


def build_tagged_loader(active_dir='datasets/active', val_frac=0.02,
                        window_bytes=1024, stride=256,
                        tag_files: bool = True):
    """Build a tagged byte-stream data loader.

    Iterates all files in active_dir.  Each file's content is wrapped in
    [FILE:ext]...[/FILE] byte markers.  Extension tags are generated
    dynamically from the actual file extension — any file type works.

    Structured formats (.parquet, .json/.jsonl) have their text fields
    extracted.  Everything else is ingested as raw bytes.
    """
    sampler = StreamingTextSampler(
        None, window_bytes=window_bytes, stride=stride, device='cpu')

    if not (active_dir and os.path.exists(active_dir)):
        total_size = sampler.size
        n_val = int(total_size * val_frac)
        n_train = total_size - n_val
        val_offset = n_train
        return sampler, total_size, n_train, n_val, val_offset, \
            np.random.RandomState(42), np.random.RandomState(43)

    for fname in sorted(os.listdir(active_dir)):
        path = os.path.join(active_dir, fname)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(fname)[1].lower()

        try:
            # ── Read file content ──
            if ext == '.parquet':
                try:
                    import pyarrow.parquet as pq
                    df = pq.read_table(path).to_pandas()
                except ImportError:
                    continue
                content = None
                for col in df.columns:
                    if df[col].dtype == object:
                        texts = df[col].dropna().astype(str).tolist()
                        if texts:
                            content = '\n\n'.join(texts).encode('utf-8')
                            break
                if content is None:
                    continue

            elif ext in ('.json', '.jsonl'):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw = f.read()
                texts = []
                try:
                    obj = json.loads(raw)
                    if isinstance(obj, list):
                        texts = [x for x in obj if isinstance(x, str)]
                except json.JSONDecodeError:
                    for line in raw.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                for k in ('text', 'content', 'instruction',
                                          'response'):
                                    if k in obj and isinstance(obj[k], str):
                                        texts.append(obj[k])
                                        break
                        except json.JSONDecodeError:
                            pass
                if texts:
                    content = '\n\n'.join(texts).encode('utf-8')
                else:
                    content = raw.encode('utf-8')

            else:
                # Generic: any extension — read as raw bytes
                with open(path, 'rb') as f:
                    content = f.read()

            if not content:
                continue

            # ── Inject file-type tags (dynamic, any extension) ──
            if tag_files and ext:
                sampler.append(_file_tag(ext))
                sampler.append(content)
                sampler.append(_END_TAG)
            else:
                sampler.append(content)

        except Exception as e:
            print(f"  Warning: could not load {fname}: {e}")
            continue

    total_size = sampler.size
    n_val = int(total_size * val_frac)
    n_train = total_size - n_val
    val_offset = n_train

    return sampler, total_size, n_train, n_val, val_offset, \
        np.random.RandomState(42), np.random.RandomState(43)


# ════════════════════════════════════════════════
#  GPU Selection
# ════════════════════════════════════════════════

def _select_gpu():
    if not torch.cuda.is_available():
        return 'cuda:0'
    count = torch.cuda.device_count()
    if count > 1:
        if 'CUDA_VISIBLE_DEVICES' in os.environ:
            return 'cuda:0'
        return 'cuda:1'
    return 'cuda:0'


def _select_device():
    if not torch.cuda.is_available():
        return 'cpu'
    return _select_gpu()


def _display_tokens(tokens, max_width=None):
    if max_width is None:
        import shutil
        max_width = shutil.get_terminal_size((80, 20)).columns - 4
    s = ''
    for t in tokens:
        b = bytes([t])
        try:
            ch = b.decode('utf-8')
        except UnicodeDecodeError:
            if 32 <= t <= 126:
                ch = chr(t)
            else:
                ch = f'\\x{t:02x}'
        if ch == '\n':
            s += '⏎'
        elif ch == '\t':
            s += '⇥'
        elif ch == '\r':
            s += '↵'
        elif ch == ' ':
            s += '·'
        else:
            s += ch
        if len(s) >= max_width:
            s += '…'
            break
    return s


# ════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Train ManifoldCord (streaming resonant field) on text.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Core model
    parser.add_argument('--N', type=int, default=128,
                        help='window size (working-memory bandwidth)')
    parser.add_argument('--d', type=int, default=128,
                        help='field dimension per position')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--patience', type=int, default=50)
    parser.add_argument('--bs', type=int, default=32)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--optimizer', type=str, default='qi_gated',
                        choices=['qi_gated', 'qifluid', 'adamw'])
    parser.add_argument('--K-train', type=int, default=3)
    parser.add_argument('--K-gen', type=int, default=50)
    parser.add_argument('--K-ar', type=int, default=3,
                        help='field AR loss evolution steps (training only)')
    # Brain
    parser.add_argument('--brain-shells', type=int, default=7)
    parser.add_argument('--no-attention', action='store_true',
                        help='disable ResonantAttention (IIR-only contextual mixing)')
    parser.add_argument('--brain-D', type=int, default=588)
    # Constraint forces
    parser.add_argument('--stiffness-Q', type=float, default=1.0)
    parser.add_argument('--stiffness-E', type=float, default=1.0)
    parser.add_argument('--stiffness-B', type=float, default=0.1)
    parser.add_argument('--noise-scale', type=float, default=0.01)
    # Pattern memory
    parser.add_argument('--max-neurons', type=int, default=512)
    parser.add_argument('--span-len', type=int, default=16)
    parser.add_argument('--lambda-pattern-div', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-commit', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-util', type=float, default=0.01)
    # Streaming
    parser.add_argument('--num-windows', type=int, default=4,
                        help='streaming windows per training example')
    # Masked prediction
    parser.add_argument('--mask-ratio', type=float, default=0.35,
                        help='span mask ratio for masked prediction (0=disabled)')
    parser.add_argument('--mask-prob', type=float, default=0.5,
                        help='probability of any given step using masked prediction')
    # File tagging
    parser.add_argument('--no-tag-files', action='store_true',
                        help='disable file-extension tagging')
    # Generation
    parser.add_argument('--gen-every', type=int, default=1,
                        help='generate every N epochs (0=disabled)')
    parser.add_argument('--gen-len', type=int, default=128)
    parser.add_argument('--gen-temp', type=float, default=0.8)
    parser.add_argument('--gen-seeds', type=int, default=2)
    parser.add_argument('--repetition-penalty', type=float, default=1.2)
    parser.add_argument('--gen-top-k', type=int, default=0)
    parser.add_argument('--gen-ngram-block', type=int, default=0)
    parser.add_argument('--gen-file-seed', type=str, default=None,
                        help='file path to use as generation seed')
    parser.add_argument('--gen-mode', type=str, default='autoregressive',
                        choices=['autoregressive', 'parallel'],
                        help='generation strategy')
    parser.add_argument('--gen-context-frac', type=float, default=0.5,
                        help='parallel: fraction of window used as context suffix')
    parser.add_argument('--gen-refine-passes', type=int, default=0,
                        help='parallel: refinement passes per block')
    # I/O
    parser.add_argument('--no-tb', action='store_true')
    parser.add_argument('--logdir', type=str, default=None)
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--checkpoint', type=str, default=None)
    parser.add_argument('--no-multi-scale-bytes', action='store_true',
                        help='disable multi-scale byte embedding')
    parser.add_argument('--no-bidirectional', action='store_true',
                        help='disable bidirectional training')
    parser.add_argument('--strict-ckpt', action='store_true',
                        help='strict checkpoint loading (fail on key mismatch)')
    parser.add_argument('--no-resume', action='store_true',
                        help='force training from scratch, ignore checkpoint')
    args = parser.parse_args()

    if args.save_dir is None:
        args.save_dir = f'checkpoints/N{args.N}_d{args.d}_manifold'
    if args.logdir is None:
        args.logdir = 'logs/tensorboard_manifold'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print('GPU: CPU-only')
    else:
        print(f'GPU: {DEV} ({torch.cuda.get_device_name(DEV)})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # ── Build model ──
    model = ManifoldCord(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen, K_ar=args.K_ar,
        brain_shells=args.brain_shells, brain_D=args.brain_D,
        use_attention=not args.no_attention,
        stiffness_B=args.stiffness_B, noise_scale=args.noise_scale,
        max_neurons=args.max_neurons, span_len=args.span_len,
        lambda_pattern_div=args.lambda_pattern_div,
        lambda_pattern_commit=args.lambda_pattern_commit,
        lambda_pattern_util=args.lambda_pattern_util,
        bidirectional=not args.no_bidirectional,
        multi_scale_bytes=not args.no_multi_scale_bytes,
        lambda_word=0.0,
        max_batch_size=args.bs,
    ).to(DEV)

    n_p = sum(p.numel() for p in model.parameters())
    print(f'Model: ManifoldCord N={args.N} d={args.d} '
          f'({model.C} chakras, {args.brain_shells} brain shells)')
    print(f'Params: {n_p:,} total')
    print(f'Chakra dims: {model.chakra_widths} (sum={sum(model.chakra_widths)})')
    print(f'Streaming: {args.num_windows} windows x {args.N} = '
          f'{args.num_windows * args.N} tokens/example')

    # ── Optimizer ──
    if args.optimizer == 'qi_gated':
        opt = QiGatedSGD(model.parameters(), lr=args.lr)
    elif args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    else:
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    # ── Checkpoint handling ──
    ckpt_latest = os.path.join(args.save_dir, 'manifold_latest.pt')
    ckpt_best = os.path.join(args.save_dir, 'manifold_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0
    ckpt_path = args.checkpoint or ckpt_latest
    loaded_ok = False
    if args.no_resume:
        print('--no-resume: training from scratch')
    elif os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        if args.strict_ckpt:
            model.load_state_dict(ckpt_model, strict=True)
            print(f'Loaded checkpoint from {ckpt_path} (strict mode)')
            loaded_ok = True
        else:
            missing, unexpected = model.load_state_dict(ckpt_model, strict=False)
            loaded_keys = len(ckpt_model) - len(missing) - len(unexpected)
            total_keys = len(dict(model.state_dict()))
            print(f'Loaded checkpoint from {ckpt_path}: '
                  f'{loaded_keys}/{total_keys} tensors restored')
            if missing:
                print(f'  {len(missing)} tensors reinitialized from defaults')
            if unexpected:
                print(f'  {len(unexpected)} tensors dropped')
            loaded_ok = loaded_keys > 0
        if loaded_ok and 'optimizer' in ckpt:
            try:
                opt.load_state_dict(ckpt['optimizer'])
                print('Loaded optimizer state')
            except (RuntimeError, ValueError):
                print('Using fresh optimizer (incompatible state)')
        if loaded_ok and 'epoch' in ckpt:
            start_ep = ckpt.get('epoch', 0) + 1
            best_val_loss = ckpt.get('best_val_loss', float('inf'))
            patience_counter = 0
    else:
        print(f'No checkpoint found at {ckpt_path}, training from scratch')

    # ── TensorBoard ──
    tb_writer = None
    run_id = time.strftime('%Y%m%d-%H%M%S')
    if not args.no_tb:
        tb_writer = SummaryWriter(log_dir=f'{args.logdir}/{run_id}')

    # ── Data ──
    sampler, total_size, n_train, n_val, val_offset, train_rng, val_rng = \
        build_tagged_loader('datasets/active', tag_files=not args.no_tag_files)
    tag_str = ' (file-extension tagged)' if not args.no_tag_files else ' (untagged)'
    print(f'Data: {total_size:,} bytes{tag_str}')

    # ════════════════════════════════════════════════
    #  Training loop
    # ════════════════════════════════════════════════

    for ep in range(start_ep, start_ep + args.epochs):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_ce = 0.0
        ep_Q_mean = 0.0
        ep_lambda_Q = 0.0
        ep_lambda_E = 0.0
        ep_lambda_B = 0.0
        ep_breath_yang = 0.0
        ep_breath_yin = 0.0
        ep_breath_beat = 0.0
        ep_pm_active = 0.0
        ep_pm_born_ratio = 0.0
        ep_pm_new_neurons = 0.0
        ep_pm_dissolved = 0.0

        for step in range(args.steps_per_epoch):
            # Sample [B, window_bytes] from the sampler
            x, _ = sample_train_batch(sampler, args.bs, train_rng)

            # Slice into num_windows windows of N tokens each
            L = args.num_windows * args.N
            x = x[:, :L].to(DEV).long()  # [B, L]

            opt.zero_grad()
            mask_ratio = args.mask_ratio if torch.rand(1).item() < args.mask_prob else 0.0
            loss_info = {}

            for window_idx in range(args.num_windows):
                start = window_idx * args.N
                x_window = x[:, start:start + args.N]  # [B, N]
                no_reset = (window_idx > 0)

                loss, info = model.training_loss(x_window, no_reset=no_reset,
                                                 mask_ratio=mask_ratio)
                # Backward per-window: frees computation graph immediately,
                # avoids holding 4 windows' graphs in memory simultaneously.
                (loss / args.num_windows).backward()

                # Collect diagnostics from all windows
                for k in ('ce_loss', 'loss', 'Q_mean', 'lambda_Q',
                          'lambda_E', 'lambda_B', 'breath_yang',
                          'breath_yin', 'breath_beat', 'pm_active',
                          'pm_born_ratio', 'pm_new_neurons',
                          'pm_dissolved', 'ce_masked', 'mask_count'):
                    if k in info:
                        loss_info[k] = loss_info.get(k, 0.0) + info.get(k, 0.0)

                # NaN guard per-window
                if torch.isnan(loss) or torch.isinf(loss):
                    print(f'  !! NaN in window {window_idx} at step {step} — skipping batch')
                    opt.zero_grad()
                    model.reset_iir_state()
                    break

            else:
                # Only reached if no break (all windows clean)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
                if args.optimizer == 'qi_gated':
                    opt.step(model=model)
                else:
                    opt.step()
            model.reset_iir_state()
            for k in list(loss_info.keys()):
                if isinstance(loss_info[k], torch.Tensor) and loss_info[k].numel() == 1:
                    loss_info[k] = loss_info[k].item()
            ep_loss += loss_info.get('loss', 0.0) / args.num_windows
            ep_ce += loss_info.get('ce_loss', 0.0) / args.num_windows
            ep_Q_mean += loss_info.get('Q_mean', 0.0) / args.num_windows
            ep_lambda_Q += loss_info.get('lambda_Q', 0.0) / args.num_windows
            ep_lambda_E += loss_info.get('lambda_E', 0.0) / args.num_windows
            ep_lambda_B += loss_info.get('lambda_B', 0.0) / args.num_windows
            ep_breath_yang += loss_info.get('breath_yang', 0.0) / args.num_windows
            ep_breath_yin += loss_info.get('breath_yin', 0.0) / args.num_windows
            ep_breath_beat += loss_info.get('breath_beat', 0.0) / args.num_windows
            ep_pm_active += loss_info.get('pm_active', 0.0) / args.num_windows
            ep_pm_born_ratio += loss_info.get('pm_born_ratio', 0.0) / args.num_windows
            ep_pm_new_neurons += loss_info.get('pm_new_neurons', 0.0) / args.num_windows
            ep_pm_dissolved += loss_info.get('pm_dissolved', 0.0) / args.num_windows

        n_steps = args.steps_per_epoch
        ep_loss /= n_steps
        ep_ce /= n_steps
        ep_Q_mean /= n_steps
        ep_lambda_Q /= n_steps
        ep_lambda_E /= n_steps
        ep_lambda_B /= n_steps
        ep_breath_yang /= n_steps
        ep_breath_yin /= n_steps
        ep_breath_beat /= n_steps
        ep_pm_active /= n_steps
        ep_pm_born_ratio /= n_steps
        ep_pm_new_neurons /= n_steps
        ep_pm_dissolved /= n_steps

        # ════════════════════════════════════════
        #  Validation
        # ════════════════════════════════════════
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for _ in range(20):
                x, _ = sample_val_batch(sampler, args.bs, val_offset, val_rng)
                L_val = args.num_windows * args.N
                x = x[:, :L_val].to(DEV).long()

                model.reset_iir_state()
                for window_idx in range(args.num_windows):
                    start = window_idx * args.N
                    x_window = x[:, start:start + args.N]
                    no_reset = (window_idx > 0)
                    loss_v, _ = model.training_loss(x_window, no_reset=no_reset)
                    val_loss += loss_v.item()
        val_loss /= (20 * args.num_windows)

        # ════════════════════════════════════════
        #  Generation
        # ════════════════════════════════════════
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            model.reset_iir_state()
            try:
                print(f'--- generation @ epoch {ep} ---', flush=True)
                for seed_idx in range(args.gen_seeds):
                    if args.gen_file_seed and os.path.exists(args.gen_file_seed):
                        with open(args.gen_file_seed, 'rb') as f:
                            seed_bytes = f.read()
                        seed = torch.tensor(list(seed_bytes), dtype=torch.long,
                                            device=DEV)
                        if seed.numel() > 8192:
                            seed = seed[:8192]
                        label = f'file seed ({seed.numel()} bytes)'
                    else:
                        torch.manual_seed(42 + ep * 1000 + seed_idx)
                        x_bytes, _ = sample_val_batch(sampler, 1, val_offset, val_rng)
                        seed = x_bytes[0, :8].to(DEV).long()
                        label = 'random seed'

                    if args.gen_mode == 'parallel':
                        sample = model.generate_parallel_stream(
                            seed, max_new=args.gen_len, temp=args.gen_temp,
                            top_k=args.gen_top_k if args.gen_top_k > 0 else None,
                            repetition_penalty=args.repetition_penalty,
                            ngram_block_size=args.gen_ngram_block,
                            context_frac=args.gen_context_frac,
                            refine_passes=args.gen_refine_passes)
                    else:
                        sample = model.generate_from_stream(
                            seed, max_new=args.gen_len, temp=args.gen_temp,
                            top_k=args.gen_top_k if args.gen_top_k > 0 else None,
                            repetition_penalty=args.repetition_penalty,
                            ngram_block_size=args.gen_ngram_block)
                    print(f'  [{label}] {_display_tokens(sample.cpu().tolist())}',
                          flush=True)
            except Exception as e:
                print(f'  !! generation failed (skipping): {e}', flush=True)
            model.train()

        dt = time.time() - t0
        constraint_str = (f'λ_Q={ep_lambda_Q:.3f} λ_E={ep_lambda_E:.3f} '
                          f'λ_B={ep_lambda_B:.3f}')
        win_info = f'wins={args.num_windows}'
        print(f'ep={ep} train={ep_loss:.4f} ce={ep_ce:.4f} val={val_loss:.4f} '
              f'Q={ep_Q_mean:.4f} {constraint_str} '
              f'yang={ep_breath_yang:.3f} yin={ep_breath_yin:.3f} '
              f'pm_active={ep_pm_active:.1f} {win_info} dt={dt:.1f}s')

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/train_loss', ep_loss, ep)
            tb_writer.add_scalar('epoch/train_ce', ep_ce, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/lambda_Q', ep_lambda_Q, ep)

        # ── Save checkpoint ──
        ckpt = {
            'epoch': ep,
            'model': model.state_dict(),
            'optimizer': opt.state_dict(),
            'best_val_loss': best_val_loss,
            'patience_counter': patience_counter,
        }
        torch.save(ckpt, ckpt_latest)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(ckpt, ckpt_best)
            patience_counter = 0
            print(f'  ✓ new best: {best_val_loss:.4f}')
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f'Early stop after {ep} epochs (best={best_val_loss:.4f})')
                break

    if tb_writer is not None:
        tb_writer.close()
    print('Done.')


if __name__ == '__main__':
    main()
