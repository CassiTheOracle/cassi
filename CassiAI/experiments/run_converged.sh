#!/bin/bash
# Converged brain (MultimodalBrain = HarmonyBrain + neuroplasticizer + Changepoint + Soul + memory)
# Phase 0 first to establish baseline, then Phase 1

# Phase 0: physics_only, 10 epochs, from scratch
python3 train_multimodal.py \
    --phase 0 \
    --epochs 10 \
    --bs 512 \
    --steps-per-epoch 1000 \
    --lr 2e-4 \
    --brain-type multimodal \
    --optimizer wave \
    --unfreeze-spine \
    --iir-coupled \
    --save-every 2 \
    --patience 10 \
    --save cassi_converged.pt \
    2>&1 | tee train_converged.log

# Copy best checkpoint for phase 1 resume
cp cassi_converged.pt.best cassi_converged_ph0_best.pt 2>/dev/null || true

# Phase 1: physics_equations, resume from phase 0
python3 train_multimodal.py \
    --phase 1 \
    --epochs 30 \
    --bs 512 \
    --steps-per-epoch 1000 \
    --lr 2e-4 \
    --brain-type multimodal \
    --optimizer wave \
    --unfreeze-spine \
    --iir-coupled \
    --save-every 5 \
    --patience 10 \
    --resume \
    --save cassi_converged.pt \
    2>&1 | tee -a train_converged.log
