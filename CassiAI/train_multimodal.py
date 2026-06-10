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
from cassi.honeybee_brain import HoneybeeBrain
from cassi.cassi_brain import CassiBrain
from cassi.dual_cassi import DualCassi
from cassi.cord import PHI
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


def build_phi_spaced_groups(model, base_lr):
    """Split parameters into φ-spaced LR groups (P2.1).

    Yang (fast):    lr * φ      — readout, brain_field, brainstem
    Balance:        lr         — memory projections, unified_readout, corpus, arbitration
    Yin (slow):     lr / φ     — meta_cord, soul, changepoint
    """
    yang_names = {'readout', 'brain_field', 'brainstem', 'readout_scale'}
    yin_names = {'meta_cord', 'soul', 'changepoint', 'observer', 'dynamics'}

    yang_params, balance_params, yin_params = [], [], []

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        # Check if any yin keyword is in the parameter path
        is_yin = any(kw in name for kw in yin_names)
        is_yang = any(kw in name for kw in yang_names)

        if is_yin:
            yin_params.append(param)
        elif is_yang:
            yang_params.append(param)
        else:
            balance_params.append(param)

    groups = []
    if yang_params:
        groups.append({'params': yang_params, 'lr': base_lr * PHI, 'weight_decay': WD})
    if balance_params:
        groups.append({'params': balance_params, 'lr': base_lr, 'weight_decay': WD})
    if yin_params:
        groups.append({'params': yin_params, 'lr': base_lr / PHI, 'weight_decay': WD})

    if not groups:
        # Fallback: all parameters
        groups = [{'params': [p for p in model.parameters() if p.requires_grad], 'lr': base_lr, 'weight_decay': WD}]

    return groups


def spectral_slope_loss(pred, target, conscious_certainty=None, eps=1e-8):
    """Penalize deviation from Kolmogorov -5/3 spectral slope.

    Computes radially averaged power spectrum of pred and target,
    fits log-log slope, and returns MSE against target slope -5/3.

    Args:
        pred: [B, D] predicted field
        target: [B, D] target field
        conscious_certainty: [B, 1] or scalar. High certainty → stricter spectral match.
    """
    B, D = pred.shape
    pred_fft = torch.fft.rfft(pred, dim=-1)
    target_fft = torch.fft.rfft(target, dim=-1)
    pred_power = pred_fft.abs().pow(2).mean(dim=0)
    target_power = target_fft.abs().pow(2).mean(dim=0)

    k = torch.arange(1, pred_power.shape[0], device=pred.device).float()
    pred_power = pred_power[1:]
    target_power = target_power[1:]

    log_k = torch.log(k + eps)
    log_pred = torch.log(pred_power + eps)
    log_target = torch.log(target_power + eps)

    log_k_mean = log_k.mean()
    var_log_k = ((log_k - log_k_mean) ** 2).mean()
    if var_log_k < eps:
        return torch.tensor(0.0, device=pred.device)

    pred_slope = ((log_k - log_k_mean) * (log_pred - log_pred.mean())).mean() / var_log_k
    target_slope = ((log_k - log_k_mean) * (log_target - log_target.mean())).mean() / var_log_k

    KOLMOGOROV_SLOPE = -5.0 / 3.0
    loss = (pred_slope - KOLMOGOROV_SLOPE).pow(2) + 0.1 * (target_slope - KOLMOGOROV_SLOPE).pow(2)

    # P2.2: Weight by conscious certainty
    if conscious_certainty is not None:
        weight = torch.sigmoid(conscious_certainty - conscious_certainty.mean())
        loss = loss * weight.mean()

    return loss


def log_print(msg):
    line = f"[{RUN_ID}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')
        f.flush()


def save_checkpoint(path, model, val_mae, epoch, phase, optimizer=None, scaler=None, settings=None):
    """Atomic checkpoint save with optimizer, scaler, and training settings."""
    tmp = path + '.tmp'
    ckpt = {
        'model': model.state_dict(),
        'val_mae': val_mae,
        'epoch': epoch + 1,
        'phase': phase,
        'rng': torch.get_rng_state(),
    }
    if settings is not None:
        ckpt['settings'] = settings
    if optimizer is not None:
        ckpt['optimizer'] = optimizer.state_dict()
        ckpt['optimizer_type'] = optimizer.__class__.__name__
    if scaler is not None:
        ckpt['scaler'] = scaler.state_dict()
    torch.save(ckpt, tmp)
    os.replace(tmp, path)


def train_epoch(model, loader, opt, mp_trainer, args, adaptive=None, audio_encoder=None, metrics=None, dream_bank=None):
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
        info['is_physics'] = is_physics

        # Loss depends on modality
        if is_physics:
            if pred.dim() == 3 and y.dim() == 3:
                # Multi-horizon: [B, H, 1024]
                loss_pred = F.mse_loss(pred, y)
            else:
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

        # Entropy regularization: encourage diverse specialist participation
        weights = info.get('weights')
        entropy_loss = 0.0
        if weights is not None:
            p = weights.clamp(min=1e-8)
            p = p / p.sum(dim=0, keepdim=True)
            entropy = -(p * p.log()).sum(dim=0).mean()
            entropy_loss = -0.01 * entropy  # maximize entropy → minimize negative entropy

        # Spectral loss for physics: encourage Kolmogorov -5/3 slope
        # P2.2: Weight by conscious certainty (high consciousness → strict spectral match)
        spectral_loss = 0.0
        if is_physics and pred.shape[-1] >= 64:
            conscious = info.get('conscious')
            if conscious is not None:
                conscious_certainty = conscious.norm(dim=-1, keepdim=True)  # [B, 1]
            else:
                conscious_certainty = None
            if pred.dim() == 3:
                spectral_loss = 0.01 * spectral_slope_loss(pred[:, 0], y[:, 0], conscious_certainty)
            else:
                spectral_loss = 0.01 * spectral_slope_loss(pred, y, conscious_certainty)

        # φ-balance regularization and Qi energy bonus (HarmonyBrain only)
        dev = pred.device
        phi_balance_loss = info.get('phi_balance_loss', torch.tensor(0.0, device=dev))
        qi_energy_bonus = info.get('qi_energy_bonus', torch.tensor(0.0, device=dev))

        # Workspace sparsity regularization + meta-cord loss
        sparsity_loss = 0.0
        meta_loss = 0.0
        if 'sparsity_loss' in info and info['sparsity_loss'] is not None:
            sparsity_loss = info['sparsity_loss']
        elif 'workspace' in info:
            workspace = info['workspace']
            sparsity_target = 0.10
            actual_sparsity = (workspace.abs() > 1e-6).float().mean()
            sparsity_loss = 0.1 * (actual_sparsity - sparsity_target).pow(2)
        if 'meta_loss' in info:
            meta_loss = 0.01 * info['meta_loss']

        # ── Internal Observer self-predictive loss (autoencoder) ──
        observer_loss = torch.tensor(0.0, device=pred.device)
        if 'observer_embedding' in info and 'observer_predicted_emb' in info:
            emb = info['observer_embedding']
            pred_emb = info['observer_predicted_emb']
            observer_loss = 0.01 * F.mse_loss(pred_emb, emb)

        # ── Conscious Dynamics temporal prediction loss ──
        # Predicted next conscious from the PREVIOUS batch, when read out,
        # should match the ACTUAL prediction made by the model in THIS batch.
        # This trains the imagination engine to genuinely simulate the future.
        dynamics_loss = torch.tensor(0.0, device=pred.device)
        if info.get('prev_predicted_next_conscious') is not None:
            pred_next_prev = info['prev_predicted_next_conscious']
            # Only compute if batch sizes match (last batch may be smaller)
            if pred_next_prev.shape[0] == pred.shape[0]:
                if hasattr(model, 'yang') and hasattr(model.yang.brain, 'readout'):
                    pred_from_dynamics, _ = model.yang.brain.readout(pred_next_prev)
                    dynamics_loss = 0.001 * F.mse_loss(pred_from_dynamics, pred.detach())
                elif hasattr(model, 'readout'):
                    pred_from_dynamics, _ = model.readout(pred_next_prev)
                    dynamics_loss = 0.001 * F.mse_loss(pred_from_dynamics, pred.detach())

        loss = (loss_pred + COHERENCE_WEIGHT * coherence + entropy_loss + spectral_loss +
                phi_balance_loss + qi_energy_bonus + sparsity_loss + meta_loss +
                observer_loss + dynamics_loss)

        # Temporal resonance regularization: keep learned band spacing near φ
        temporal_reg = 0.0
        if hasattr(model, 'temporal_regularization_loss'):
            temporal_reg = model.temporal_regularization_loss()
            if torch.isfinite(temporal_reg):
                loss = loss + temporal_reg

        # DualCassi: disagreement regularization — encourage hemispheres to specialize
        # We want them to disagree on HOW to predict, not on WHAT to predict
        # So we penalize small disagreements (encourage them to find different strategies)
        # but only after they've learned the basics
        disagreement_loss = 0.0
        if args.brain_type == 'dual' and 'disagreement' in info:
            disagreement = info['disagreement']
            # Target: moderate disagreement (not zero, not huge)
            # Too little = hemispheres collapsed to same solution
            # Too much = they disagree on basic facts
            disagreement_target = 15.0  # empirical: ~28 at init, want >10
            if disagreement < disagreement_target:
                disagreement_loss = 0.01 * (disagreement_target - disagreement)
            loss = loss + disagreement_loss

        if metrics is not None:
            metrics.record_batch(
                info=info,
                loss=loss.item() if torch.isfinite(loss) else None,
                pred=pred,
                target=y,
                model=model,
            )

        # Store salient moments in DreamBank for later replay
        if dream_bank is not None and torch.isfinite(loss):
            stored = dream_bank.store(
                x=x_input, y=y, info=info, pred=pred,
                loss=loss_pred.item(), modality='physics' if is_physics else ('audio' if is_audio else 'text')
            )

        if not torch.isfinite(loss):
            continue

        # Get neuroplasticizer modulation if available
        neuro_mod = info.get('neuro_modulation') if args.optimizer in ('iir', 'wave') else None

        if mp_trainer and mp_trainer.enabled:
            mp_trainer.scaler.scale(loss).backward()
            if neuro_mod is not None:
                mp_trainer.optimizer_step(clip_grad=1.0, neuro_modulation=neuro_mod)
            else:
                mp_trainer.optimizer_step(clip_grad=1.0)
        else:
            loss.backward()
            total_grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            if total_grad_norm > 0.9:
                if step % 50 == 0:
                    print(f"  [step {step}] grad_norm={total_grad_norm:.2f} near clip threshold")
            if not torch.isfinite(total_grad_norm):
                print(f"  [step {step}] WARNING: non-finite grad_norm={total_grad_norm}, skipping step")
                opt.zero_grad()
                continue
            if neuro_mod is not None:
                opt.step(neuro_modulation=neuro_mod)
            else:
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

    n_samples = n_batches * args.bs  # batches are fixed-size in this loader
    if n_samples == 0:
        return float('nan'), float('nan'), float('nan'), modality_counts
    return epoch_loss / n_samples, epoch_pred / n_samples, epoch_coherence / n_samples, modality_counts


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
            info['is_physics'] = is_physics

            batch_mae = batch_mse = None
            if is_physics:
                if pred.dim() == 3 and y.dim() == 3:
                    # Multi-horizon: report MAE averaged over all horizons
                    batch_mae = F.l1_loss(pred, y)
                    batch_mse = F.mse_loss(pred, y)
                else:
                    batch_mae = F.l1_loss(pred, y)
                    batch_mse = F.mse_loss(pred, y)
            elif is_audio and audio_encoder is not None:
                y_field = audio_encoder.encode_window(y)
                batch_mae = F.l1_loss(pred, y_field)
                batch_mse = F.mse_loss(pred, y_field)
            else:
                if hasattr(model.spine, 'byte_encoder') and hasattr(model.spine.byte_encoder, 'encode'):
                    y_field = model.spine.byte_encoder.encode(y[:, :256])
                else:
                    y_field = y.float()
                batch_mae = F.l1_loss(pred, y_field)
                batch_mse = F.mse_loss(pred, y_field)

            if batch_mae is not None and torch.isfinite(batch_mae) and torch.isfinite(batch_mse):
                val_mae += batch_mae.item() * len(x)
                val_mse += batch_mse.item() * len(x)
                val_surprise += info.get('surprise', 0.0) * len(x)
                mean_harmony = info.get('mean_harmony')
                qi_arousal = info.get('qi_arousal')
                if mean_harmony is not None:
                    val_harmony += mean_harmony.mean().item() * len(x)
                elif qi_arousal is not None:
                    val_harmony += qi_arousal.item() * len(x)
                val_n += len(x)

    if val_n == 0:
        return {'mae': float('nan'), 'mse': float('nan'), 'surprise': float('nan'), 'harmony': float('nan')}

    def _as_float(x):
        return x.item() if isinstance(x, torch.Tensor) else float(x)

    return {
        'mae': _as_float(val_mae / val_n),
        'mse': _as_float(val_mse / val_n),
        'surprise': _as_float(val_surprise / val_n),
        'harmony': _as_float(val_harmony / val_n),
    }


def main():
    parser = argparse.ArgumentParser(description='Multimodal Cassi Trainer')
    parser.add_argument('--phase', type=int, default=0, choices=range(6),
                        help='Curriculum phase (0=physics, 3=speech, 5=all)')
    parser.add_argument('--epochs', type=int, default=60,
                        help='Total training epochs (default: 60)')
    parser.add_argument('--bs', type=int, default=32,
                        help='Batch size (default: 32)')
    parser.add_argument('--steps-per-epoch', type=int, default=1000)
    parser.add_argument('--lr', type=float, default=2e-4)
    parser.add_argument('--save', default=SAVE_PATH)
    parser.add_argument('--no-resume', action='store_true', help='Start fresh instead of auto-resuming from checkpoint')
    parser.add_argument('--save-every', type=int, default=5)
    parser.add_argument('--patience', type=int, default=50)

    # Brain features (default True; use --no-* to disable)
    parser.add_argument('--use-berry', action='store_true', default=True, dest='use_berry')
    parser.add_argument('--no-berry', action='store_false', dest='use_berry')
    parser.add_argument('--use-changepoint', action='store_true', default=True, dest='use_changepoint')
    parser.add_argument('--no-changepoint', action='store_false', dest='use_changepoint')
    parser.add_argument('--use-soul', action='store_true', default=True, dest='use_soul')
    parser.add_argument('--no-soul', action='store_false', dest='use_soul')
    parser.add_argument('--berry-slots', type=int, default=4096)

    # Training features
    parser.add_argument('--mixed-precision', action='store_true')
    parser.add_argument('--adaptive', action='store_true')
    parser.add_argument('--unfreeze-spine', action='store_true',
                        help='Unfreeze spine parameters with reduced LR')
    parser.add_argument('--optimizer', type=str, default='wave',
                        choices=['adamw', 'iir', 'wave'],
                        help='Optimizer: adamw, iir (resonant IIR), or wave (Cassi-native IIR+chakra+Muon)')
    parser.add_argument('--iir-theta', type=float, default=None,
                        help='IIR resonance angle in radians (default: π/4)')
    parser.add_argument('--iir-phi-damp', type=float, default=None,
                        help='IIR damping factor (default: PHI_INV ≈ 0.618)')
    parser.add_argument('--iir-b0', type=float, default=None,
                        help='IIR feedforward gain (default: 1 - phi_damp)')
    parser.add_argument('--iir-coupled', action='store_true',
                        help='Couple IIR coefficients to spine IIR params after load_spine()')
    parser.add_argument('--iir-adaptive', action='store_true',
                        help='Add per-parameter variance scaling to IIR (AdamW-like adaptivity)')
    parser.add_argument('--iir-order', type=int, default=2, choices=[1, 2],
                        help='IIR filter order (default 2); use 1 with --iir-adaptive to keep 2 states total')
    parser.add_argument('--wave-ns-min', type=int, default=3,
                        help='WaveGradientFilter min NS steps per chakra band (default 3)')
    parser.add_argument('--wave-ns-max', type=int, default=6,
                        help='WaveGradientFilter max NS steps per chakra band (default 6)')
    parser.add_argument('--wave-ns-skip', type=int, default=4096,
                        help='Skip NS for chakra bands wider than this (default 4096)')
    parser.add_argument('--wave-no-resonant', action='store_true',
                        help='Disable resonant NS (use fixed max steps for all bands)')
    parser.add_argument('--brain-type', type=str, default='dual',
                        choices=['multimodal', 'honeybee', 'cassi', 'dual'],
                        help='Brain architecture: multimodal, honeybee, cassi, or dual (two hemispheres)')
    parser.add_argument('--D', type=int, default=None,
                        help='Conscious dimension (default: 1040 for multimodal, 16384 for honeybee)')
    parser.add_argument('--W', type=int, default=256,
                        help='Workspace dimension (honeybee only, default 256)')
    parser.add_argument('--horizons', type=int, nargs='+', default=[1, 4, 16],
                        help='Multi-horizon prediction targets for physics (default: [1, 4, 16])')

    # DreamBank
    parser.add_argument('--use-dream', action='store_true', default=True, dest='use_dream')
    parser.add_argument('--no-dream', action='store_false', dest='use_dream')
    parser.add_argument('--dream-capacity', type=int, default=1024)
    parser.add_argument('--dream-replay', type=int, default=50,
                        help='Number of replay steps per epoch')
    parser.add_argument('--dream-batch', type=int, default=32)

    args = parser.parse_args()
    args.epoch = 0

    from datetime import datetime
    log_print(f"{'='*60}")
    log_print(f"Cassi Multimodal Trainer  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print(f"Phase: {args.phase}  Epochs: {args.epochs}")
    log_print(f"Berry: {args.use_berry}  Changepoint: {args.use_changepoint}  Soul: {args.use_soul}")
    log_print(f"DreamBank: {args.use_dream}  capacity={args.dream_capacity}  replay={args.dream_replay}")
    log_print(f"Horizons: {args.horizons}")
    log_print(f"{'='*60}")

    # Data loader
    physics_cache = 'datasets/physics_cache_v10.pt'
    if len(args.horizons) > 1 or max(args.horizons) > 1:
        physics_cache = 'datasets/physics_cache_multihz_v1.pt'
    loader = MultimodalDataLoader(phase=args.phase, physics_cache=physics_cache)
    log_print(f"Phase: {loader.get_phase_name()}")
    log_print(f"Physics cache: {physics_cache}")
    log_print(f"Physics train: {loader.nt:,}  val: {loader.nv:,}")
    log_print(f"Text bytes: {loader.text_total:,}")
    log_print(f"Audio transcripts: {len(loader.audio_transcripts):,}")
    log_print(f"Descriptions: {len(loader.descriptions):,}")

    # Model
    D = args.D if args.D is not None else (16384 if args.brain_type == 'honeybee' else 1040)
    if args.brain_type == 'honeybee':
        readout_hidden = max(520, D // 32)
        model = HoneybeeBrain(
            D=D, W=args.W, n_specialists=13, n_slots=512,
            memory_value_dim=39, readout_hidden=readout_hidden,
            byte_mode=True, sparsity=0.10,
        ).to(DEV)
    elif args.brain_type == 'cassi':
        # Scaled-up architecture: D_stem=D for 2:1 compression, D_brain=2*D*φ for 2x capacity
        model = CassiBrain(
            D=D, D_stem=D, D_brain=int(D * PHI * 2),
            use_changepoint=args.use_changepoint,
            use_soul=args.use_soul,
            use_memory=args.use_berry,
            K=2,
            byte_mode=True,
            horizons=tuple(args.horizons),
        ).to(DEV)
        log_print(f"CassiBrain: D={D}, D_stem={model.D_stem}, D_brain={model.D_brain}")
    elif args.brain_type == 'dual':
        # Dual-hemisphere: two Cassi instances with corpus callosum + arbitration
        model = DualCassi(
            D=D, D_stem=D, D_brain=int(D * PHI * 2),
            use_changepoint=args.use_changepoint,
            use_soul=args.use_soul,
            use_memory=args.use_berry,
            byte_mode=True,
            horizons=tuple(args.horizons),
        ).to(DEV)
        summary = model.summary()
        log_print(f"DualCassi: Yang={summary['yang_params']:,} + Yin={summary['yin_params']:,} "
                  f"+ Corpus={summary['corpus_callosum_params']:,} + Arb={summary['arbitration_params']:,} "
                  f"= Total={summary['total_trainable']:,}")
    else:
        model = MultimodalBrain(
            D=D, n_specialists=13, n_slots=512,
            memory_value_dim=39, readout_hidden=520,
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

    # Unfreeze brain + berry + soul params (leave spine frozen)
    for name, p in model.named_parameters():
        if 'spine' in name and 'byte_encoder.gain' not in name:
            continue
        p.requires_grad = True

    # Build optimizer
    if args.optimizer in ('iir', 'wave'):
        wave_kwargs = {'lr': args.lr, 'weight_decay': WD}
        if args.iir_theta is not None:
            wave_kwargs['theta'] = args.iir_theta
        if args.iir_phi_damp is not None:
            wave_kwargs['phi_damp'] = args.iir_phi_damp
        if args.iir_b0 is not None:
            wave_kwargs['b0'] = args.iir_b0
        wave_kwargs['order'] = args.iir_order
        if args.optimizer == 'wave':
            wave_kwargs['ns_min_steps'] = args.wave_ns_min
            wave_kwargs['ns_max_steps'] = args.wave_ns_max
            wave_kwargs['ns_skip_width'] = args.wave_ns_skip
            wave_kwargs['use_resonant_ns'] = not args.wave_no_resonant
    else:
        wave_kwargs = None

    # Optionally unfreeze spine with reduced LR
    if args.unfreeze_spine:
        model.unfreeze_spine()
        log_print("Spine UNFROZEN — fine-tuning with reduced LR")
        spine_lr = args.lr * 0.1
        brain_params = [p for n, p in model.named_parameters() if 'spine' not in n or 'byte_encoder.gain' in n]
        spine_params = [p for n, p in model.named_parameters() if 'spine' in n and 'byte_encoder.gain' not in n]
        if args.optimizer == 'iir':
            from cassi.iir_optimizer import ResonantIIR
            opt = ResonantIIR([
                {'params': brain_params, 'lr': args.lr, 'weight_decay': WD},
                {'params': spine_params, 'lr': spine_lr, 'weight_decay': WD},
            ], **wave_kwargs)
        elif args.optimizer == 'wave':
            from cassi.wave_gradient_filter import WaveGradientFilter
            opt = WaveGradientFilter([
                {'params': brain_params, 'lr': args.lr, 'weight_decay': WD},
                {'params': spine_params, 'lr': spine_lr, 'weight_decay': WD},
            ], spine=model.spine, **wave_kwargs)
            opt.bind_spine(model.spine)
            if args.iir_coupled and hasattr(model.spine, 'fwd_theta'):
                opt.load_spine_coeffs(model.spine)
        else:
            opt = torch.optim.AdamW([
                {'params': brain_params, 'lr': args.lr, 'weight_decay': WD},
                {'params': spine_params, 'lr': spine_lr, 'weight_decay': WD},
            ])
    else:
        # P2.1: φ-spaced parameter groups for CassiBrain / DualCassi
        use_phi_groups = args.brain_type in ('cassi', 'dual')
        if use_phi_groups:
            param_groups = build_phi_spaced_groups(model, args.lr)
        else:
            param_groups = [{'params': [p for p in model.parameters() if p.requires_grad], 'lr': args.lr, 'weight_decay': WD}]

        if args.optimizer == 'iir':
            from cassi.iir_optimizer import ResonantIIR
            opt = ResonantIIR(param_groups, **wave_kwargs)
            if args.iir_coupled and hasattr(model, 'spine') and hasattr(model.spine, 'fwd_theta'):
                opt.load_spine_coeffs(model.spine)
        elif args.optimizer == 'wave':
            from cassi.wave_gradient_filter import WaveGradientFilter
            opt = WaveGradientFilter(param_groups, spine=model.spine, **wave_kwargs)
            opt.bind_spine(model.spine)
            if args.iir_coupled and hasattr(model, 'spine') and hasattr(model.spine, 'fwd_theta'):
                opt.load_spine_coeffs(model.spine)
        else:
            opt = torch.optim.AdamW(param_groups)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log_print(f"Trainable params: {n_params:,}")
    log_print(f"Optimizer: {args.optimizer}")
    mp_trainer = MixedPrecisionTrainer(model, opt, enabled=args.mixed_precision)
    adaptive = AdaptiveTrainer(model, opt, lr_base=args.lr) if args.adaptive else None
    metrics = CassiMetrics(log_dir='logs/metrics')

    # DreamBank for episodic replay of surprise & disappointment
    dream_bank = None
    if args.use_dream:
        from cassi.dream_bank import DreamBank
        dream_bank = DreamBank(
            capacity=args.dream_capacity,
            replay_batch_size=args.dream_batch,
        )
        qi_cycle = getattr(model, 'qi_cycle', None)
        if qi_cycle is not None:
            qi_cycle.subscribe(dream_bank)

    best_val = float('inf')
    best_path = args.save + '.best'
    start_ep = 0
    no_improve = 0

    # Build serialisable settings dict for checkpoint metadata
    settings = {
        'brain_type': args.brain_type,
        'bs': args.bs,
        'epochs': args.epochs,
        'lr': args.lr,
        'optimizer': args.optimizer,
        'horizons': args.horizons,
        'use_berry': args.use_berry,
        'use_changepoint': args.use_changepoint,
        'use_soul': args.use_soul,
        'use_dream': args.use_dream,
        'phase': args.phase,
    }

    if not args.no_resume and os.path.exists(args.save):
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

        # Validate settings from checkpoint
        ck_settings = ck.get('settings')
        if ck_settings is not None:
            mismatches = []
            for key, val in ck_settings.items():
                current = getattr(args, key, None)
                if current is not None and current != val:
                    mismatches.append(f"{key}: {val} → {current}")
            if mismatches:
                log_print(f"Settings mismatch vs checkpoint: {', '.join(mismatches)}")
            else:
                log_print("Settings validated against checkpoint")
        else:
            log_print("Checkpoint lacks settings metadata (legacy checkpoint)")

        ck_phase = ck.get('phase', args.phase)
        ck_epoch = ck.get('epoch', 0)
        if ck_phase != args.phase:
            # Phase transition: reset epoch counter and best val
            log_print(f"Phase transition detected: checkpoint phase {ck_phase} → target phase {args.phase}")
            start_ep = 0
            best_val = float('inf')
            no_improve = 0
            log_print(f"Starting fresh at epoch 0 of phase {args.phase}")
        else:
            start_ep = ck_epoch
            best_val = ck.get('val_mae', float('inf'))
            log_print(f"Resumed phase {args.phase} epoch {start_ep} val_mae={best_val:.4f}")
        # Restore optimizer and scaler state for continuity
        # Only restore if optimizer type matches (Wave/ResonantIIR have incompatible
        # param_groups with AdamW, so loading AdamW state into Wave crashes on step)
        ck_opt_type = ck.get('optimizer_type')
        current_opt_type = opt.__class__.__name__ if opt is not None else None
        if 'optimizer' in ck and opt is not None:
            if ck_opt_type is not None and ck_opt_type != current_opt_type:
                log_print(f"Optimizer type mismatch: checkpoint {ck_opt_type} vs current {current_opt_type}, starting fresh optimizer state")
            elif args.optimizer in ('wave', 'iir') and ck_opt_type is None:
                log_print(f"Checkpoint lacks optimizer type; skipping state restore for {args.optimizer} optimizer safety")
            else:
                try:
                    opt.load_state_dict(ck['optimizer'])
                    log_print("Optimizer state restored")
                except Exception as e:
                    log_print(f"Optimizer state load failed (param mismatch expected if architecture changed): {e}")
        if 'scaler' in ck and mp_trainer.scaler is not None:
            try:
                mp_trainer.scaler.load_state_dict(ck['scaler'])
                log_print("Scaler state restored")
            except Exception as e:
                log_print(f"Scaler state load failed: {e}")
        if 'rng' in ck:
            rng_state = ck['rng']
            if rng_state.device.type != 'cpu':
                rng_state = rng_state.cpu()
            torch.set_rng_state(rng_state)

    t_start = time.perf_counter()
    last_epoch = start_ep

    for ep in range(start_ep, args.epochs):
        last_epoch = ep
        args.epoch = ep
        train_loss, train_pred, train_coherence, mod_counts = \
            train_epoch(model, loader, opt, mp_trainer, args, adaptive, audio_encoder, metrics=metrics, dream_bank=dream_bank)

        mod_str = ' '.join(f"{k}={v}" for k, v in mod_counts.items())

        do_val = (ep + 1) % 2 == 0 or ep == start_ep or ep == args.epochs - 1

        if do_val:
            v = validate(model, loader, args, audio_encoder)
            improved = v['mae'] < best_val
            if improved:
                best_val = v['mae']
                save_checkpoint(best_path, model, best_val, ep, args.phase, opt, mp_trainer.scaler if mp_trainer else None, settings=settings)
                no_improve = 0
            else:
                no_improve += 1

            metrics.flush_epoch(epoch=ep, val_metrics=v)
            elapsed = time.perf_counter() - t_start
            # Optional: log learned temporal resonance α
            alpha_val = None
            try:
                if hasattr(model, 'readout') and hasattr(model.readout, 'log_alpha'):
                    alpha_val = model.readout.log_alpha.detach().exp().item()
                elif hasattr(model, 'yang') and hasattr(model.yang, 'brain') and \
                        hasattr(model.yang.brain, 'readout') and \
                        hasattr(model.yang.brain.readout, 'log_alpha'):
                    alpha_val = model.yang.brain.readout.log_alpha.detach().exp().item()
            except Exception:
                alpha_val = None
            alpha_str = f" α={alpha_val:.3f}" if alpha_val is not None else ""
            log_print(
                f"  ep {ep+1:4d}  train={train_pred:.4f}  val_mae={v['mae']:.4f}  "
                f"best={best_val:.4f}  surprise={v['surprise']:.2f}  "
                f"harmony={v['harmony']:.2f}{alpha_str}  "
                f"[{int(elapsed//60)}m{int(elapsed%60):02d}s]  mods={mod_str}"
            )
            log_print(metrics.summary_table(epoch=-1).replace('\n', ' | '))

            if (ep + 1) % args.save_every == 0:
                save_checkpoint(args.save, model, v['mae'], ep, args.phase, opt, mp_trainer.scaler if mp_trainer else None, settings=settings)
                metrics.plot_dashboard(save_path=f'logs/dashboard_epoch_{ep+1:03d}.png')

            if no_improve >= args.patience:
                log_print(f"  Early stop at epoch {ep+1}")
                break
        else:
            metrics.flush_epoch(epoch=ep)
            elapsed = time.perf_counter() - t_start
            log_print(f"  ep {ep+1:4d}  train={train_pred:.4f}  [{int(elapsed//60)}m{int(elapsed%60):02d}s]")
            log_print(metrics.summary_table(epoch=-1).replace('\n', ' | '))

        # DreamBank replay: consolidate salient moments
        if dream_bank is not None and sum(len(b) for b in dream_bank.banks.values()) > 0:
            replay_results = []
            for _ in range(args.dream_replay):
                mode = dream_bank.choose_mode()
                samples, replay_state = dream_bank.sample_for_replay(mode)
                if samples is None:
                    continue
                loss, state = dream_bank.replay_forward(model, samples, replay_state)
                dream_bank.apply_replay_step(opt, loss, state, mp_trainer=mp_trainer)
                for exp in samples:
                    exp._replay_losses.append(loss.item())
                replay_results.append({'loss': loss.item(), 'state': state})
            if replay_results:
                losses = [r['loss'] for r in replay_results]
                states = {}
                for r in replay_results:
                    states[r['state']] = states.get(r['state'], 0) + 1
                state_str = ' '.join(f"{k}={v}" for k, v in states.items())
                log_print(f"  DreamBank replay: {len(losses)} steps, "
                          f"loss={sum(losses)/len(losses):.4f}  "
                          f"states=[{state_str}]  {dream_bank.summary()}")

            # Migration and rebalancing (in Metal state or every 5 epochs)
            qi_cycle = getattr(model, 'qi_cycle', None)
            if (qi_cycle is not None and qi_cycle.state == 'metal') or ep % 5 == 0:
                dream_bank.run_migration()
                dream_bank.rebalance_capacity()

    # Load best and save final
    if os.path.exists(best_path):
        ck_best = torch.load(best_path, map_location=DEV, weights_only=False)
        best_state = ck_best['model']
        model_state = model.state_dict()
        filtered_best = {}
        skipped_best = []
        for k, v in best_state.items():
            if k in model_state:
                if v.shape == model_state[k].shape:
                    filtered_best[k] = v
                else:
                    skipped_best.append(k)
            else:
                skipped_best.append(k)
        if skipped_best:
            log_print(f"Final load skipped mismatched keys: {skipped_best}")
        model.load_state_dict(filtered_best, strict=False)
    model.eval()

    # Save final
    save_checkpoint(args.save, model, best_val, last_epoch, args.phase, opt, mp_trainer.scaler if mp_trainer else None, settings=settings)
    log_print(f"\nSaved {args.save}  phase={args.phase}  val_mae={best_val:.4f}")


if __name__ == '__main__':
    main()
