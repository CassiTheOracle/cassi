#!/usr/bin/env python3
"""Train TransceiverBrain atop frozen CordPhysics spine on physics data.

Architecture:
  Frozen spine → repr → transceiver field (φ² equilibrium)
  → Linear(1040→1024) → tanh → added to spine prediction

Persistent field design:
  - Field state persists across all training batches within an epoch.
  - Resets only at epoch boundaries, allowing the φ-damped IIR field to accumulate context.
  - ρ ≈ 0.618 ensures old state decays exponentially (~20 steps → negligible).
  - Spine processes each window independently (every window carries 4 input frames).

Optimizer:
  - Default: wave (Cassi-native IIR + chakra-aware NS iteration).
  - Alternatives: adamw, iir (resonant IIR).

Usage:
  python train_transceiver.py --epochs 20 --bs 16 --seq-len 64 --lr 1e-4
"""
import torch, time, argparse, numpy as np, os
from cassi.cord import CordPhysics
from cassi.transceiver_brain import TransceiverBrain, PHI, PHI_INV

p = argparse.ArgumentParser()
p.add_argument("--epochs", type=int, default=50)
p.add_argument("--bs", type=int, default=16)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--spine", default="checkpoints/spine_physics.pt")
p.add_argument("--save", default="transceiver_brain.pt")
p.add_argument("--steps-per-epoch", type=int, default=None)
p.add_argument("--seq-len", type=int, default=64)
p.add_argument("--field-clamp", type=float, default=50.0)
p.add_argument("--val-sequences", type=int, default=None)
p.add_argument("--device", default="auto")
p.add_argument("--optimizer", default="wave", choices=["adamw", "iir", "wave"])
p.add_argument("--wave-ns-min", type=int, default=3)
p.add_argument("--wave-ns-max", type=int, default=6)
p.add_argument("--iir-theta", type=float, default=None)
p.add_argument("--iir-phi-damp", type=float, default=None)
p.add_argument("--resume", action="store_true")
args = p.parse_args()

DEV = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")

# ── Spine ──
spine = CordPhysics(D=1040).to(DEV)
ck = torch.load(args.spine, map_location=DEV, weights_only=False)
state = ck.get("model", ck)
state = {k.replace("_orig_mod.", ""): v for k, v in state.items()}
spine_state = {}
for k, v in state.items():
    if k.startswith("spine."):
        spine_state[k[len("spine."):]] = v
if not spine_state:
    spine_state = {k: v for k, v in state.items()
                   if not k.startswith(("specialists.", "berry_", "memory_",
                       "readout.", "harmony_", "meta_cord.", "workspace_",
                       "field_history", "qi_fluid"))}
spine.load_state_dict(spine_state, strict=False)
spine.eval()
for p in spine.parameters():
    p.requires_grad = False
print(f"Spine: {sum(p.numel() for p in spine.parameters()):,} frozen")

# ── Data ──
cache = torch.load("datasets/physics_cache_v10.pt", map_location="cpu", weights_only=False)
wins = torch.stack(cache["windows"])          # [N, 5, 1024]
seqs = cache["seqs"]                          # list of (start, length)
rng = np.random.RandomState(42)
perm = rng.permutation(len(seqs))
split = int(len(seqs) * 0.8)
train_seqs = [seqs[i] for i in perm[:split]]
val_seqs   = [seqs[i] for i in perm[split:]]
min_len = args.seq_len
train_seqs = [(s, l) for s, l in train_seqs if l >= min_len]
val_seqs   = [(s, l) for s, l in val_seqs   if l >= min_len]
print(f"Data:  {len(train_seqs)} train seqs  {len(val_seqs)} val seqs  "
      f"seq_len={args.seq_len}  bs={args.bs}")

# ── Brain ──
brain = TransceiverBrain(D=1040, n_neurons=128, use_homeostasis=True).to(DEV)
brain.field_clamp = args.field_clamp

# Learned parameters only; runtime buffers (field, h, h_prev) excluded.
trainable = sum(p.numel() for p in brain.parameters() if p.requires_grad)
total = sum(p.numel() for p in brain.parameters())

wave_kwargs = {"lr": args.lr, "weight_decay": 0.0}
if args.iir_theta is not None:
    wave_kwargs["theta"] = args.iir_theta
if args.iir_phi_damp is not None:
    wave_kwargs["phi_damp"] = args.iir_phi_damp
if args.optimizer == "wave":
    wave_kwargs["ns_min_steps"] = args.wave_ns_min
    wave_kwargs["ns_max_steps"] = args.wave_ns_max

brain_params = [p for p in brain.parameters() if p.requires_grad]
param_groups = [{"params": brain_params, "lr": args.lr, "weight_decay": 0.0}]

if args.optimizer == "adamw":
    opt = torch.optim.AdamW(param_groups)
elif args.optimizer == "iir":
    from cassi.iir_optimizer import ResonantIIR
    opt = ResonantIIR(param_groups, **wave_kwargs)
else:  # wave
    from cassi.wave_gradient_filter import WaveGradientFilter
    opt = WaveGradientFilter(param_groups, spine=spine, **wave_kwargs)
    opt.bind_spine(spine)

print(f"Brain: {trainable:,}/{total:,} trainable  lr={args.lr}  "
      f"ρ={PHI_INV:.4f}  φ²={PHI**2:.4f}")

# Exclude runtime state from checkpoints (reset per epoch/sequence)
runtime_keys = {"field"}
for i in range(brain.n_neurons):
    runtime_keys.add(f"neurons.{i}.h")
    runtime_keys.add(f"neurons.{i}.h_prev")
runtime_keys.add("meta_plasticity.h")
runtime_keys.add("meta_plasticity.h_prev")


def sample_train_batch(seq_list, batch_size, seq_len, rng):
    idx = rng.choice(len(seq_list), size=batch_size)
    xs, ys = [], []
    for i in idx:
        s, l = seq_list[i]
        off = rng.randint(0, l - seq_len + 1)
        chunk = wins[s + off:s + off + seq_len]
        xs.append(chunk[:, :4])
        ys.append(chunk[:, 4])
    return torch.stack(xs).to(DEV), torch.stack(ys).to(DEV)


# ── Training ──
best_val = float("inf")
start_ep = 0
rg = np.random.RandomState(42)
t0 = time.perf_counter()

if args.resume and os.path.exists(args.save):
    ck2 = torch.load(args.save, map_location=DEV, weights_only=False)
    brain_state = {k: v for k, v in ck2["brain"].items() if k not in runtime_keys}
    brain.load_state_dict(brain_state, strict=False)
    best_val = ck2.get("val_mae", float("inf"))
    start_ep = ck2.get("epoch", 0)
    print(f"Resumed epoch={start_ep}  val_mae={best_val:.4f}")

for ep in range(start_ep, args.epochs):
    brain.train()
    brain.reset_state(batch_size=args.bs)
    ep_loss = ep_base = 0.0
    n_train = 0

    n_steps = args.steps_per_epoch if args.steps_per_epoch is not None else len(train_seqs)
    for step_i in range(n_steps):
        x, y = sample_train_batch(train_seqs, args.bs, args.seq_len, rg)
        B, T = x.shape[:2]

        x_flat = x.reshape(B * T, 4, 1024)
        spine_pred, trajs = spine(x_flat, return_trajectories=True)
        sp_max = spine_pred.abs().max().item()
        if sp_max != sp_max or sp_max > 1e6:
            continue

        spine_pred = spine_pred.reshape(B, T, 1024)
        spine_repr = trajs["repr"].clamp(-10.0, 10.0).reshape(B, T, 1040)
        base_pred = spine_pred.detach().clamp(-10.0, 10.0)
        residual = brain(spine_repr, use_neurons=True, target=y)
        enhanced = base_pred + residual

        emax = enhanced.abs().max().item()
        if emax != emax or emax > 1e6:
            continue

        loss = (enhanced - y).pow(2).mean()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(brain.parameters(), 1.0)

        # Meta-plasticity: let the brain modulate its own learning rate
        lr_mod = brain.lr_modulation
        for g in opt.param_groups:
            g['lr'] = args.lr * lr_mod

        opt.step()
        with torch.no_grad():
            w = brain.readout[0].weight
            w *= (PHI ** 2) / (w.norm() + 1e-8)

        ep_loss += loss.item() * B
        ep_base += (base_pred - y).pow(2).mean().item() * B
        n_train += B

    # ── Validation ──
    brain.eval()
    val_enh = val_base = 0.0
    n_val = 0

    with torch.no_grad():
        for seq_idx, (s, l) in enumerate(val_seqs):
            if args.val_sequences is not None and seq_idx >= args.val_sequences:
                break
            for start in range(s, s + l, args.seq_len):
                if start + args.seq_len > s + l:
                    continue
                chunk = wins[start:start + args.seq_len]
                x = chunk[:, :4].unsqueeze(0).to(DEV)   # [1, T, 4, 1024]
                y = chunk[:, 4].unsqueeze(0).to(DEV)    # [1, T, 1024]
                B, T = x.shape[:2]

                x_flat = x.reshape(B * T, 4, 1024)
                spine_pred, trajs = spine(x_flat, return_trajectories=True)
                sp_max = spine_pred.abs().max().item()
                if sp_max != sp_max or sp_max > 1e6:
                    continue

                spine_pred = spine_pred.reshape(B, T, 1024)
                spine_repr = trajs["repr"].clamp(-10.0, 10.0).reshape(B, T, 1040)

                brain.reset_state(batch_size=B)
                residual = brain(spine_repr, use_neurons=True)
                enhanced = spine_pred.clamp(-10.0, 10.0) + residual

                emax = enhanced.abs().max().item()
                if emax != emax:
                    continue

                vh = (enhanced - y).abs().mean().item()
                vb = (spine_pred.clamp(-10.0, 10.0) - y).abs().mean().item()
                if vh != vh or vb != vb:
                    continue

                val_enh += vh * B
    wnorm = brain.readout[0].weight.norm().item()
    train_avg = ep_loss / max(1, n_train)
    val_enh_avg = val_enh / max(1, n_val) if n_val else float("nan")
    val_base_avg = val_base / max(1, n_val) if n_val else float("nan")
    dt = time.perf_counter() - t0

    stats = brain.get_field_stats()
    freqs = brain.get_neuron_freqs()
    freq_spread = np.std(freqs) if len(freqs) > 1 else 0.0
    qi_energy_val = brain._qi_energy.item()
    lr_mod_val = brain.lr_modulation
    qi_st = brain.qi_state
    print(f"ep {ep+1:3d}  train={train_avg:.4f}  "
          f"val_enh={val_enh_avg:.4f}  val_base={val_base_avg:.4f}  "
          f"wnorm={wnorm:.2f}  field_energy={stats['energy']:.3f}  "
          f"freq_spread={freq_spread:.3f}  "
          f"qi={qi_st}  qi_e={qi_energy_val:.4f}  lr_mod={lr_mod_val:.3f}  "
          f"[{int(dt//60)}m{int(dt%60):02d}s]")

    if val_enh_avg < best_val and n_val > 0:
        best_val = val_enh_avg
        brain_ckpt = {k: v for k, v in brain.state_dict().items() if k not in runtime_keys}
        torch.save({"brain": brain_ckpt, "val_mae": best_val, "epoch": ep + 1}, args.save)

elapsed = time.perf_counter() - t0
print(f"\nBest: {best_val:.4f}  [{int(elapsed//60)}m{int(dt%60):02d}s]  {args.save}")
