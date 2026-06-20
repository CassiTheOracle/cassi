#!/usr/bin/env python3
"""QiField trainer for physics field regression.

Usage:
    python3 experiments/train_qi_field_physics.py --N 4 --d 512 --bs 64 --epochs 200
    python3 experiments/train_qi_field_physics.py --N 4 --d 128 --bs 4 --steps-per-epoch 2 --no-tb
"""

import argparse
import os
import sys
import time

import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.qi_field import QiField
from cassi.qi_fluid_optimizer import QiFluidOptimizer
from cassi.multimodal_loader import MultimodalDataLoader


MODELS = {
    'qifield': QiField,
}


def _select_gpu():
    if not torch.cuda.is_available():
        return 'cpu'
    n = torch.cuda.device_count()
    if n == 1:
        return 'cuda:0'
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        props = torch.cuda.get_device_properties(i)
        total = props.total_memory / (1024 ** 3)
        if '7900' in name or total > 20:
            return f'cuda:{i}'
    return 'cuda:0'


def _select_device():
    if not torch.cuda.is_available():
        return 'cpu'
    return _select_gpu()


def _target_frame(y):
    """Extract the first-horizon target frame from a multi-horizon batch.

    Args:
        y: [B, H, D] or [B, D]
    Returns:
        [B, D]
    """
    if y.dim() == 3:
        return y[:, 0, :]
    return y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='qifield', choices=list(MODELS.keys()))
    parser.add_argument('--N', type=int, default=4, help='Number of input frames')
    parser.add_argument('--d', type=int, default=512, help='Field dimension')
    parser.add_argument('--epochs', type=int, default=200)
    parser.add_argument('--patience', type=int, default=50)
    parser.add_argument('--bs', type=int, default=64)
    parser.add_argument('--steps-per-epoch', type=int, default=200)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--optimizer', type=str, default='qifluid', choices=['qifluid', 'adamw'])
    parser.add_argument('--K-train', type=int, default=10)
    parser.add_argument('--K-gen', type=int, default=50)
    parser.add_argument('--no-self-aware', action='store_true',
                        help='Disable self-awareness controller (default: enabled)')
    parser.add_argument('--ctrl-hidden-dim', type=int, default=64)
    parser.add_argument('--ctrl-loss-weight', type=float, default=0.01)
    parser.add_argument('--ctrl-lr-scale', type=float, default=0.1)
    parser.add_argument('--lambda-homeo', type=float, default=0.1)
    parser.add_argument('--lambda-breath-gating', type=float, default=0.01)
    parser.add_argument('--lambda-smooth', type=float, default=0.01)
    parser.add_argument('--lambda-balance', type=float, default=0.01)
    parser.add_argument('--lambda-center', type=float, default=1e-4)
    parser.add_argument('--no-tb', action='store_true')
    parser.add_argument('--logdir', type=str, default=None)
    parser.add_argument('--save-dir', type=str, default=None)
    parser.add_argument('--gen-every', type=int, default=10,
                        help='Generate rollout every N epochs; 0 disables generation')
    parser.add_argument('--gen-horizon', type=int, default=16,
                        help='Number of frames to rollout during generation')
    parser.add_argument('--gen-seeds', type=int, default=2,
                        help='Number of independent rollouts per epoch')
    parser.add_argument('--max-neurons', type=int, default=512)
    parser.add_argument('--span-len', type=int, default=16)
    parser.add_argument('--lambda-pattern-div', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-commit', type=float, default=0.001)
    parser.add_argument('--lambda-pattern-util', type=float, default=0.01)
    parser.add_argument('--cache', type=str, default='datasets/physics_cache_multihz_v1.pt')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--reset', action='store_true',
                        help='Reset field state every batch (default: accumulate)')
    parser.add_argument('--reset-every', type=int, default=1,
                        help='Reset field state every N training steps (default 1)')
    args = parser.parse_args()
    args.self_aware = not args.no_self_aware

    if args.save_dir is None:
        args.save_dir = f'checkpoints/N{args.N}_d{args.d}_{args.model}_physics_v1'
    if args.logdir is None:
        args.logdir = f'logs/tensorboard_{args.model}_physics'
    os.makedirs(args.save_dir, exist_ok=True)

    DEV = _select_device()
    if DEV == 'cpu':
        print(f'GPU: CPU-only mode')
    else:
        print(f'GPU: device {DEV.split(":")[-1]} ({torch.cuda.get_device_name(int(DEV.split(":")[-1]))})')
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    # ── Data ──
    loader = MultimodalDataLoader(physics_cache=args.cache, phase=0)
    print(f'Data: {loader.nt:,} train windows, {loader.nv:,} val windows from {args.cache}')

    # ── Model ──
    ModelCls = MODELS[args.model]
    model_kwargs = dict(
        N=args.N, d=args.d, C=13, V=256,
        K_train=args.K_train, K_gen=args.K_gen,
        self_aware=args.self_aware,
        ctrl_hidden_dim=args.ctrl_hidden_dim,
        ctrl_loss_weight=args.ctrl_loss_weight,
        max_neurons=args.max_neurons,
        span_len=args.span_len,
        lambda_pattern_div=args.lambda_pattern_div,
        lambda_pattern_commit=args.lambda_pattern_commit,
        lambda_pattern_util=args.lambda_pattern_util,
        input_dim=1024,
        output_dim=1024,
        continuous_mode=True,
        max_batch_size=args.bs,
        state_bank_size=loader.wins.shape[0],
    )
    if args.self_aware:
        model_kwargs.update(
            lambda_homeo=args.lambda_homeo,
            lambda_breath_gating=args.lambda_breath_gating,
            lambda_smooth=args.lambda_smooth,
            lambda_balance=args.lambda_balance,
            lambda_center=args.lambda_center,
        )
    model = ModelCls(**model_kwargs).to(DEV)

    use_state_bank = getattr(model, 'state_bank_size', 0) > 0

    n_p = sum(p.numel() for p in model.parameters())
    print(f'Model: {ModelCls.__name__} N={args.N} d={args.d} ({model.C} chakras), params: {n_p:,}')

    if args.optimizer == 'qifluid':
        opt = QiFluidOptimizer(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    else:
        raise ValueError(f'Unsupported optimizer: {args.optimizer}')

    ckpt_latest = os.path.join(args.save_dir, f'{args.model}_latest.pt')
    ckpt_best = os.path.join(args.save_dir, f'{args.model}_best.pt')
    start_ep = 0
    best_val_loss = float('inf')
    patience_counter = 0

    loaded_model = False
    if args.resume and os.path.exists(ckpt_latest):
        ckpt = torch.load(ckpt_latest, map_location=DEV, weights_only=True)
        ckpt_model = ckpt.get('model', ckpt)
        try:
            missing, unexpected = model.load_state_dict(ckpt_model)
            print(f'Loaded checkpoint from {ckpt_latest}')
            loaded_model = True
        except RuntimeError as e:
            print(f'Checkpoint conversion failed: {e}')
            print('Starting training from scratch.')
            start_ep = 0
            best_val_loss = float('inf')
            patience_counter = 0

        if loaded_model:
            if 'optimizer' in ckpt:
                try:
                    opt.load_state_dict(ckpt['optimizer'])
                    print('Loaded optimizer state.')
                except (RuntimeError, ValueError) as e:
                    print(f'Optimizer state incompatible: {e}')
                    print('Using freshly initialized optimizer.')

            if 'epoch' in ckpt:
                start_ep = ckpt.get('epoch', 0) + 1
                best_val_loss = ckpt.get('best_val_loss', float('inf'))
                patience_counter = ckpt.get('patience_counter', 0)
                print(f'Resuming from epoch {start_ep}')

    tb_writer = None
    run_id = time.strftime('%Y%m%d-%H%M%S')
    if not args.no_tb:
        tb_writer = SummaryWriter(log_dir=f'{args.logdir}/{run_id}')

    prev_val_loss = float('inf')
    end_epoch = args.epochs + (start_ep if args.resume else 0)
    for ep in range(start_ep, end_epoch):
        t0 = time.time()
        model.train()
        ep_loss = 0.0
        ep_mse = 0.0
        ep_mae = 0.0
        ep_Q_mean = 0.0
        ep_pm_active = 0.0
        ep_pm_born_ratio = 0.0
        ep_pm_new_neurons = 0.0
        ep_pm_dissolved = 0.0
        ep_ctrl_aux = 0.0
        ep_ctrl_alpha = 0.0
        ep_ctrl_beta = 0.0
        ep_ctrl_delta = 0.0
        nan_steps = 0

        for step in range(args.steps_per_epoch):
            if use_state_bank:
                pass  # keyed IIR persistence active; do not reset between batches
            elif not args.reset:
                pass
            elif args.reset_every <= 1 or step % args.reset_every == 0:
                model.reset_state()
            x, y, indices, _ = loader.sample_train_batch(args.bs, device=DEV, return_indices=True)
            if indices is not None:
                indices = torch.from_numpy(indices).long().to(DEV)
            y = _target_frame(y)

            opt.zero_grad()
            loss, info = model.training_loss(x, y, state_indices=indices)

            if torch.isnan(loss) or torch.isinf(loss):
                print(f'  !! NaN/inf loss at step {step} — skipping', flush=True)
                nan_steps += 1
                continue

            loss.backward()

            grad_nan = any(
                torch.isnan(p.grad).any() or torch.isinf(p.grad).any()
                for p in model.parameters() if p.grad is not None
            )
            if grad_nan:
                opt.zero_grad()
                nan_steps += 1
                continue

            if args.self_aware and model.controller is not None:
                for p in model.controller.parameters():
                    if p.grad is not None:
                        p.grad.mul_(args.ctrl_lr_scale)

            opt.step()

            ep_loss += info['loss']
            ep_mse += info['mse_loss']
            ep_mae += info['mae_loss']
            ep_Q_mean += info['Q_mean']
            ep_pm_active += info.get('pm_active', 0.0)
            ep_pm_born_ratio += info.get('pm_born_ratio', 0.0)
            ep_pm_new_neurons += info.get('pm_new_neurons', 0.0)
            ep_pm_dissolved += info.get('pm_dissolved', 0.0)
            if args.self_aware:
                ep_ctrl_aux += info.get('ctrl_aux_loss', 0.0)
                ep_ctrl_alpha += info.get('ctrl_alpha', 0.0)
                ep_ctrl_beta += info.get('ctrl_beta', 0.0)
                ep_ctrl_delta += info.get('ctrl_delta', 0.0)

        eff_steps = max(1, args.steps_per_epoch - nan_steps)
        ep_loss /= eff_steps
        ep_mse /= eff_steps
        ep_mae /= eff_steps
        ep_Q_mean /= eff_steps
        ep_pm_active /= eff_steps
        ep_pm_born_ratio /= eff_steps
        if args.self_aware:
            ep_ctrl_aux /= eff_steps
            ep_ctrl_alpha /= eff_steps
            ep_ctrl_beta /= eff_steps
            ep_ctrl_delta /= eff_steps

        # ── Validation ──
        model.eval()
        if not use_state_bank:
            model.reset_state()
        val_loss = 0.0
        val_mae = 0.0
        with torch.no_grad():
            for _ in range(20):
                x, y, indices, _ = loader.sample_val_batch(args.bs, device=DEV, return_indices=True)
                if indices is not None:
                    indices = torch.from_numpy(indices).long().to(DEV)
                y = _target_frame(y)
                loss, info = model.training_loss(x, y, state_indices=indices)
                pred = model(x, state_indices=indices)[0]
                val_loss += loss.item()
                val_mae += F.l1_loss(pred, y).item()
        val_loss /= 20
        val_mae /= 20

        # ── Rollout generation ──
        rollout_texts = []
        if args.gen_every > 0 and ep % args.gen_every == 0:
            model.eval()
            rollout_texts.append(f'--- rollout @ epoch {ep} ---')
            for seed_idx in range(args.gen_seeds):
                model.reset_state()
                torch.manual_seed(42 + ep * 1000 + seed_idx)
                x, y_gt, _ = loader.sample_val_batch(1, device=DEV)
                seed = x[0]  # [N, 1024]
                y_gt = _target_frame(y_gt)[0]  # [1024]
                pred = model.generate_rollout(seed, max_new=1, K_init=args.K_gen)
                pred = pred[0, 0]  # [1024]
                mae = F.l1_loss(pred, y_gt).item()
                rollout_texts.append(f'  seed {seed_idx}: horizon-1 MAE = {mae:.4f}')
            model.train()
        extra = ''
        if args.self_aware:
            extra = (f' ctrl_aux={ep_ctrl_aux:.4f} alpha={ep_ctrl_alpha:.3f} '
                     f'beta={ep_ctrl_beta:.3f} delta={ep_ctrl_delta:.3f}')
        dt = time.time() - t0
        print(f'ep={ep} train={ep_loss:.4f} mse={ep_mse:.4f} mae={ep_mae:.4f} '
              f'val={val_loss:.4f} val_mae={val_mae:.4f} Q={ep_Q_mean:.4f} '
              f'pm_active={ep_pm_active:.1f} pm_born_ratio={ep_pm_born_ratio:.3f} '
              f'pm_new={ep_pm_new_neurons:.1f} pm_dissolved={ep_pm_dissolved:.1f}{extra} '
              f'lr={opt.param_groups[0]["lr"]:.6f} dt={dt:.1f}s')
        for txt in rollout_texts:
            print(txt, flush=True)

        if tb_writer is not None:
            tb_writer.add_scalar('epoch/val_loss', val_loss, ep)
            tb_writer.add_scalar('epoch/val_mae', val_mae, ep)
            tb_writer.add_scalar('epoch/train_mse', ep_mse, ep)
            tb_writer.add_scalar('epoch/train_mae', ep_mae, ep)
            tb_writer.add_scalar('epoch/train_loss', ep_loss, ep)
            tb_writer.add_scalar('epoch/Q_mean', ep_Q_mean, ep)
            tb_writer.add_scalar('epoch/pm_active', ep_pm_active, ep)
            tb_writer.add_scalar('epoch/pm_born_ratio', ep_pm_born_ratio, ep)
            tb_writer.add_scalar('epoch/pm_new_neurons', ep_pm_new_neurons, ep)
            tb_writer.add_scalar('epoch/pm_dissolved', ep_pm_dissolved, ep)
            tb_writer.add_scalar('epoch/lr', opt.param_groups[0]['lr'], ep)
            if args.self_aware:
                tb_writer.add_scalar('epoch/ctrl_aux', ep_ctrl_aux, ep)
                tb_writer.add_scalar('epoch/ctrl_alpha', ep_ctrl_alpha, ep)
                tb_writer.add_scalar('epoch/ctrl_beta', ep_ctrl_beta, ep)
                tb_writer.add_scalar('epoch/ctrl_delta', ep_ctrl_delta, ep)

        ckpt = {
            'epoch': ep,
            'model': model.state_dict(),
            'optimizer': opt.state_dict(),
            'best_val_loss': best_val_loss,
            'patience_counter': patience_counter,
            'args': vars(args),
        }
        torch.save(ckpt, ckpt_latest)

        delta = prev_val_loss - val_loss
        prev_val_loss = val_loss
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(ckpt, ckpt_best)
        else:
            patience_counter += 1

        if patience_counter >= args.patience:
            print(f'Early stop at epoch {ep}')
            break

    if tb_writer is not None:
        tb_writer.close()
    print('Done!')

    if torch.cuda.is_available():
        try:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        except Exception:
            pass


if __name__ == '__main__':
    main()
