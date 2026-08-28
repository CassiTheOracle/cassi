"""Overnight training: TreeDiffusionCord + byte salience on 5.6GB text.

Usage:
    CUDA_VISIBLE_DEVICES=1 PYTORCH_HIP_ALLOC_CONF=expandable_segments:True \
    HSA_ENABLE_SDMA=0 PYTHONPATH=. python experiments/train_overnight.py
"""

import os, time, torch, argparse
from torch.optim.lr_scheduler import CosineAnnealingLR

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'

from cassi.tree_diffusion_cord import TreeDiffusionCord
from cassi.token_diffusion_cord import TokenDiffusionCord
from experiments.train_langevin_text import (
    build_text_loader, sample_train_batch, sample_val_batch
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=200)
    p.add_argument('--bs', type=int, default=32)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--steps-per-epoch', type=int, default=200)
    p.add_argument('--text-dir', default='datasets/active')
    p.add_argument('--save-dir', default='checkpoints')
    p.add_argument('--resume', default=None, help='Resume from checkpoint')
    p.add_argument('--gen-every', type=int, default=20, help='Generate samples every N epochs')
    args = p.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    D = 4096

    print(f"Device: {DEV}")
    print(f"D={D}, epochs={args.epochs}, bs={args.bs}, lr={args.lr}")
    print(f"Steps/epoch={args.steps_per_epoch}")

    # ── Models ──
    token_model = TokenDiffusionCord(
        vocab_size=256, emb_dim=4, seq_len=1024, num_timesteps=100
    ).to(DEV)
    spine = TreeDiffusionCord(D=D).to(DEV)

    n_tok = sum(p.numel() for p in token_model.parameters())
    n_spine = sum(p.numel() for p in spine.parameters())
    print(f"Token model: {n_tok:,} params")
    print(f"Tree spine:  {n_spine:,} params")
    print(f"Total:       {n_tok + n_spine:,} params")

    # ── Optimizer ──
    opt = torch.optim.AdamW(
        list(spine.parameters()) + list(token_model.parameters()),
        lr=args.lr, weight_decay=0.01
    )
    sched = CosineAnnealingLR(opt, T_max=args.epochs, eta_min=args.lr * 0.01)

    # ── Data ──
    sampler, total, n_train, n_val, val_off, tr_rng, val_rng = \
        build_text_loader(args.text_dir)
    print(f"Data: {total:,} bytes ({total/1e9:.1f} GB)")

    # ── Resume ──
    start_epoch = 0
    best_loss = float('inf')
    if args.resume:
        ckpt = torch.load(args.resume, map_location=DEV, weights_only=False)
        ms, cs = spine.state_dict(), ckpt['spine']
        for k in list(cs.keys()):
            if k in ms and cs[k].shape == ms[k].shape:
                ms[k] = cs[k]
        spine.load_state_dict(ms)
        ts, tc = token_model.state_dict(), ckpt['token']
        for k in list(tc.keys()):
            if k in ts and tc[k].shape == ts[k].shape:
                ts[k] = tc[k]
        token_model.load_state_dict(ts)
        start_epoch = ckpt.get('epoch', 0)
        best_loss = ckpt.get('best_loss', float('inf'))
        print(f"Resumed from epoch {start_epoch}, best_loss={best_loss:.4f}")

    # ── Training loop ──
    t_start = time.time()

    for ep in range(start_epoch, start_epoch + args.epochs):
        t_ep = time.time()
        spine.train()
        token_model.train()
        total_loss = 0.0

        for step in range(args.steps_per_epoch):
            x_bytes, _ = sample_train_batch(sampler, args.bs, tr_rng)
            field = token_model.bytes_to_field(x_bytes.to(DEV))

            t = torch.randint(0, spine.num_timesteps, (args.bs,), device=DEV)
            noise = torch.randn_like(field)
            x_t, _ = spine.q_sample(field, t, noise=noise)

            opt.zero_grad()
            x0_pred = spine(x_t, t)
            loss = torch.nn.functional.mse_loss(x0_pred, field)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(spine.parameters()) + list(token_model.parameters()), 1.0
            )
            opt.step()
            total_loss += loss.item()

        sched.step()
        avg_loss = total_loss / args.steps_per_epoch
        dt = time.time() - t_ep

        # Validation every 5 epochs
        val_loss = None
        if ep % 5 == 0:
            spine.eval()
            token_model.eval()
            val_total = 0.0
            with torch.no_grad():
                for _ in range(10):
                    xv, _ = sample_val_batch(sampler, args.bs, val_off, val_rng)
                    fv = token_model.bytes_to_field(xv.to(DEV))
                    tv = torch.randint(0, spine.num_timesteps, (args.bs,), device=DEV)
                    nv = torch.randn_like(fv)
                    xtv, _ = spine.q_sample(fv, tv, noise=nv)
                    val_total += torch.nn.functional.mse_loss(
                        spine(xtv, tv), fv
                    ).item()
            val_loss = val_total / 10

        status = f"Epoch {ep+1:4d}: loss={avg_loss:.4f}"
        if val_loss is not None:
            status += f" val={val_loss:.4f}"
        status += f" time={dt:.0f}s lr={sched.get_last_lr()[0]:.1e}"
        elapsed = time.time() - t_start
        eta = elapsed / (ep + 1 - start_epoch) * (args.epochs - (ep + 1 - start_epoch))
        status += f" elapsed={elapsed/3600:.1f}h eta={eta/3600:.1f}h"
        print(status)

        # Save best
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save({
                'spine': spine.state_dict(),
                'token': token_model.state_dict(),
                'epoch': ep + 1,
                'best_loss': best_loss,
            }, f"{args.save_dir}/overnight_best.pt")

        # Periodic checkpoint
        if (ep + 1) % 50 == 0:
            torch.save({
                'spine': spine.state_dict(),
                'token': token_model.state_dict(),
                'epoch': ep + 1,
                'best_loss': best_loss,
            }, f"{args.save_dir}/overnight_ep{ep+1}.pt")

        # Generate samples
        if (ep + 1) % args.gen_every == 0:
            spine.eval()
            token_model.eval()
            steps = spine._subsample_steps(100)
            x_t = torch.randn(1, D, device=DEV)
            for i, t_idx in enumerate(steps):
                t = torch.full((1,), t_idx, device=DEV, dtype=torch.long)
                t_pr = steps[i+1] if i+1 < len(steps) else -1
                x0 = spine(x_t, t)
                if t_pr >= 0:
                    ac = spine.alphas_cumprod[t_idx]
                    ap = spine.alphas_cumprod[t_pr]
                    eps = (x_t - torch.sqrt(ac) * x0) / torch.sqrt(1.0 - ac + 1e-8)
                    x_t = torch.sqrt(ap) * x0 + torch.sqrt(1.0 - ap + 1e-8) * eps
                else:
                    x_t = x0
            bt = token_model.field_to_bytes(x_t, temperature=0.8)
            raw = bt[0].cpu().numpy()
            text = bytes([x for x in raw if 32 <= x < 127]).decode('ascii', errors='replace')
            print(f"  sample: {text[:150]!r}")

    # ── Final save ──
    torch.save({
        'spine': spine.state_dict(),
        'token': token_model.state_dict(),
        'epoch': start_epoch + args.epochs,
        'best_loss': best_loss,
    }, f"{args.save_dir}/overnight_final.pt")

    total_time = time.time() - t_start
    print(f"\nDone! {args.epochs} epochs in {total_time/3600:.1f}h, best_loss={best_loss:.4f}")


if __name__ == '__main__':
    main()
