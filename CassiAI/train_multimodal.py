#!/usr/bin/env python3
"""Multimodal Trainer — physics + text + audio with curriculum and cognitive enhancements.

Usage:
  # Start with physics-only (phase 0)
  python train_multimodal.py --phase 0 --epochs 10

  # Advance to mixed modalities (phase 3 = speech_audio)
  python train_multimodal.py --phase 3 --epochs 10 --resume

Curriculum phases:
  0: physics_only
  1: physics_equations
  2: physics_descriptions
  3: speech_audio
  4: text_images
  5: all_modalities
"""

import torch
import torch.nn.functional as F
import numpy as np
import time
import os
import argparse

from cassi.multimodal_brain import MultimodalBrain
from cassi.multimodal_loader import MultimodalDataLoader
from cassi.adaptive_trainer import AdaptiveTrainer
from cassi.streaming_text_sampler import MixedPrecisionTrainer
from cassi.audio_encoder import AudioFieldEncoder
from cassi.observability import CassiMetrics

DEV = 'cuda'
SPINE_PHYSICS = 'checkpoints/spine_physics.pt'
SPINE_TEXT = 'checkpoints/spine_text.pt'
SAVE_PATH = 'cassi_multimodal.pt'
LOG_PATH = 'cassi_multimodal.log'

RUN_ID = hex(int(time.time() * 1e6))[-6:]
WD = 0.01
COHERENCE_WEIGHT = 0.01


def log_print(msg):
    line = f"[{RUN_ID}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')
        f.flush()


def save_checkpoint(path, model, val_mae, epoch, phase):
    torch.save({
        'model': model.state_dict(),
        'val_mae': val_mae,
        'epoch': epoch + 1,
        'phase': phase,
    }, path)


def train_epoch(model, loader, opt, mp_trainer, args, adaptive=None, audio_encoder=None, metrics=None):
    model.train()
    epoch_loss = epoch_pred = epoch_coherence = 0.0
    n_batches = 0
    modality_counts = {}

    for step in range(args.steps_per_epoch):
        x, y, tags = loader.sample_train_batch(args.bs, device=DEV)

        model.reset_workspace(len(x))

        # Store experience in berry memory if enabled
        store_exp = args.use_berry and (step % 10 == 0)

        # Determine if batch is audio
        is_audio = False
        if isinstance(tags, list):
            is_audio = any(t == 'audio' for t in tags)
            is_physics = tags[0] == 'physics'
            is_text = not is_physics and not is_audio
        else:
            is_audio = tags == 'audio'
            is_physics = tags == 'physics'
            is_text = not is_physics and not is_audio

        # Encode inputs based on modality
        if is_audio and audio_encoder is not None:
            # x is [B, 1024] float waveform → [B, dim_field]
            x_field = audio_encoder.encode_window(x)  # [B, dim_field]
            # Expand to [B, 4, dim_field] for spine
            x_input = x_field.unsqueeze(1).expand(-1, 4, -1)
            byte_mode = False
        else:
            x_input = x
            byte_mode = not is_physics

        pred, info = model(
            x_input, use_memory=True, return_workspace=True,
            byte_mode=byte_mode,
            store_experience=store_exp
        )

        if metrics is not None:
            metrics.record_batch(
                info=info,
                loss=loss.item() if torch.isfinite(loss) else None,
                pred=pred,
                target=y,
                model=model,
            )

        # Loss depends on modality
        if is_physics:
            loss_pred = F.mse_loss(pred, y)
        elif is_audio and audio_encoder is not None:
            # Target is also audio waveform → encode to field
            y_field = audio_encoder.encode_window(y)
            loss_pred = F.mse_loss(pred, y_field)
        else:
            # Text: encode target with wave encoder
            if hasattr(model.spine, 'byte_encoder') and hasattr(model.spine.byte_encoder, 'encode'):
                y_field = model.spine.byte_encoder.encode(y[:, :256])
            else:
                y_field = y.float()
            loss_pred = F.mse_loss(pred, y_field)

        coherence = info['conscious'].pow(2).mean()
        loss = loss_pred + COHERENCE_WEIGHT * coherence

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

        epoch_loss += loss.item() * len(x)
        epoch_pred += loss_pred.item() * len(x)
        epoch_coherence += coherence.item() * len(x)
        n_batches += 1

        # Track modality distribution (count each sample's tag individually)
        if isinstance(tags, list):
            for t in tags:
                modality_counts[t] = modality_counts.get(t, 0) + 1
        else:
            modality_counts[tags] = modality_counts.get(tags, 0) + len(x)

    n = n_batches * args.bs
    return epoch_loss / n, epoch_pred / n, epoch_coherence / n, modality_counts


def validate(model, loader, args, audio_encoder=None):
    model.eval()
    val_mae = val_mse = val_surprise = val_harmony = 0.0
    val_n = 0
    steps = loader.val_steps(args.bs)

    with torch.no_grad():
        for _ in range(steps):
            x, y, tags = loader.sample_val_batch(args.bs, device=DEV)
            model.reset_workspace(len(x))

            is_audio = (tags == 'audio') if isinstance(tags, str) else (tags[0] == 'audio' if isinstance(tags, list) else False)
            is_physics = (tags == 'physics') if isinstance(tags, str) else (tags[0] == 'physics' if isinstance(tags, list) else False)

            if is_audio and audio_encoder is not None:
                x_input = audio_encoder.encode_window(x).unsqueeze(1).expand(-1, 4, -1)
                byte_mode = False
            else:
                x_input = x
                byte_mode = not is_physics

            pred, info = model(x_input, use_memory=True, return_workspace=True, byte_mode=byte_mode)

            if is_physics:
                val_mae += F.l1_loss(pred, y).item() * len(x)
                val_mse += F.mse_loss(pred, y).item() * len(x)
            elif is_audio and audio_encoder is not None:
                y_field = audio_encoder.encode_window(y)
                val_mae += F.l1_loss(pred, y_field).item() * len(x)
                val_mse += F.mse_loss(pred, y_field).item() * len(x)
            else:
                if hasattr(model.spine, 'byte_encoder') and hasattr(model.spine.byte_encoder, 'encode'):
                    y_field = model.spine.byte_encoder.encode(y[:, :256])
                else:
                    y_field = y.float()
                val_mae += F.l1_loss(pred, y_field).item() * len(x)
                val_mse += F.mse_loss(pred, y_field).item() * len(x)

            val_surprise += info['surprise'] * len(x)
            val_harmony += info['mean_harmony'].mean().item() * len(x)
            val_n += len(x)

    return {
        'mae': val_mae / val_n,
        'mse': val_mse / val_n,
        'surprise': val_surprise / val_n,
        'harmony': val_harmony / val_n,
    }


def main():
    parser = argparse.ArgumentParser(description='Multimodal Cassi Trainer')
    parser.add_argument('--phase', type=int, default=0, choices=range(6),
                        help='Curriculum phase (0=physics, 3=speech, 5=all)')
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--bs', type=int, default=512)
    parser.add_argument('--steps-per-epoch', type=int, default=1000)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--save', default=SAVE_PATH)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--save-every', type=int, default=5)
    parser.add_argument('--patience', type=int, default=10)

    # Brain features
    parser.add_argument('--use-berry', action='store_true', default=True)
    parser.add_argument('--use-changepoint', action='store_true', default=True)
    parser.add_argument('--use-soul', action='store_true', default=True)
    parser.add_argument('--berry-slots', type=int, default=1024)

    # Training features
    parser.add_argument('--mixed-precision', action='store_true')
    parser.add_argument('--adaptive', action='store_true')

    args = parser.parse_args()
    args.epoch = 0

    from datetime import datetime
    log_print(f"{'='*60}")
    log_print(f"Cassi Multimodal Trainer  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print(f"Phase: {args.phase}  Epochs: {args.epochs}")
    log_print(f"Berry: {args.use_berry}  Changepoint: {args.use_changepoint}  Soul: {args.use_soul}")
    log_print(f"{'='*60}")

    # Data loader
    loader = MultimodalDataLoader(phase=args.phase)
    log_print(f"Phase: {loader.get_phase_name()}")
    log_print(f"Physics train: {loader.nt:,}  val: {loader.nv:,}")
    log_print(f"Text bytes: {loader.text_total:,}")
    log_print(f"Audio transcripts: {len(loader.audio_transcripts):,}")
    log_print(f"Descriptions: {len(loader.descriptions):,}")

    # Model
    model = MultimodalBrain(
        D=1040, n_specialists=13, n_slots=512,
        memory_value_dim=26, readout_hidden=520,
        byte_mode=True, mode='sparse', min_k=2,
        use_berry=args.use_berry,
        use_changepoint=args.use_changepoint,
        use_soul=args.use_soul,
        berry_slots=args.berry_slots,
    ).to(DEV)

    # Load spine
    spine_path = SPINE_PHYSICS if args.phase <= 2 else SPINE_TEXT
    if os.path.exists(spine_path):
        model.load_spine(spine_path)
        log_print(f"Spine loaded: {spine_path}")

    # Install wave encoder for text/audio phases
    if args.phase >= 2:
        from cassi.text_codec import WaveByteEncoder
        wave_enc = WaveByteEncoder(window_bytes=1024, dim_field=1024, T=4).to(DEV)
        model.spine.byte_encoder = wave_enc
        log_print("Wave encoder installed")

    # Audio encoder for speech phases
    audio_encoder = None
    if args.phase >= 3:
        audio_encoder = AudioFieldEncoder(dim_field=1024).to(DEV)
        log_print("Audio encoder installed")

    model.freeze_spine()
    if hasattr(model.spine, 'byte_encoder') and hasattr(model.spine.byte_encoder, 'gain'):
        model.spine.byte_encoder.gain.requires_grad = True

    # Unfreeze brain + berry + soul params
    for p in model.parameters():
        p.requires_grad = True

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log_print(f"Trainable params: {n_params:,}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=WD)
    mp_trainer = MixedPrecisionTrainer(model, opt, enabled=args.mixed_precision)
    adaptive = AdaptiveTrainer(model, opt, lr_base=args.lr) if args.adaptive else None
    metrics = CassiMetrics(log_dir='logs/metrics')

    best_val = float('inf')
    best_path = args.save + '.best'
    start_ep = 0
    no_improve = 0

    if args.resume and os.path.exists(args.save):
        ck = torch.load(args.save, map_location=DEV, weights_only=False)
        state = ck['model']
        model_state = model.state_dict()
        filtered = {}
        skipped = []
        for k, v in state.items():
            if k in model_state:
                if v.shape == model_state[k].shape:
                    filtered[k] = v
                else:
                    skipped.append(k)
            else:
                skipped.append(k)
        model.load_state_dict(filtered, strict=False)
        if skipped:
            log_print(f"Resume skipped mismatched keys: {skipped}")
        best_val = ck.get('val_mae', float('inf'))
        start_ep = ck.get('epoch', 0)
        args.phase = ck.get('phase', args.phase)
        log_print(f"Resumed phase {args.phase} epoch {start_ep} val_mae={best_val:.4f}")

    t_start = time.perf_counter()

    for ep in range(start_ep, args.epochs):
        args.epoch = ep
        train_loss, train_pred, train_coherence, mod_counts = \
            train_epoch(model, loader, opt, mp_trainer, args, adaptive, audio_encoder, metrics=metrics)

        mod_str = ' '.join(f"{k}={v}" for k, v in mod_counts.items())

        do_val = (ep + 1) % 2 == 0 or ep == start_ep or ep == args.epochs - 1

        if do_val:
            v = validate(model, loader, args, audio_encoder)
            improved = v['mae'] < best_val
            if improved:
                best_val = v['mae']
                save_checkpoint(best_path, model, best_val, ep, args.phase)
                no_improve = 0
            else:
                no_improve += 1

            metrics.flush_epoch(epoch=ep, val_metrics=v)
            elapsed = time.perf_counter() - t_start
            log_print(
                f"  ep {ep+1:4d}  train={train_pred:.4f}  val_mae={v['mae']:.4f}  "
                f"best={best_val:.4f}  surprise={v['surprise']:.2f}  "
                f"harmony={v['harmony']:.2f}  [{int(elapsed//60)}m{int(elapsed%60):02d}s]  "
                f"mods={mod_str}"
            )
            log_print(metrics.summary_table(epoch=-1).replace('\n', ' | '))

            if (ep + 1) % args.save_every == 0:
                save_checkpoint(args.save, model, v['mae'], ep, args.phase)
                metrics.plot_dashboard(save_path=f'logs/dashboard_epoch_{ep+1:03d}.png')

            if no_improve >= args.patience:
                log_print(f"  Early stop at epoch {ep+1}")
                break
        else:
            metrics.flush_epoch(epoch=ep)
            elapsed = time.perf_counter() - t_start
            log_print(f"  ep {ep+1:4d}  train={train_pred:.4f}  [{int(elapsed//60)}m{int(elapsed%60):02d}s]")
            log_print(metrics.summary_table(epoch=-1).replace('\n', ' | '))

        torch.cuda.empty_cache()

    # Load best and save final
    if os.path.exists(best_path):
        ck_best = torch.load(best_path, map_location=DEV, weights_only=False)
        model.load_state_dict(ck_best['model'], strict=False)
    model.eval()

    # Save final
    torch.save({'model': model.state_dict(), 'val_mae': best_val, 'epoch': args.epochs, 'phase': args.phase}, args.save)
    log_print(f"\nSaved {args.save}  phase={args.phase}  val_mae={best_val:.4f}")


if __name__ == '__main__':
    main()
