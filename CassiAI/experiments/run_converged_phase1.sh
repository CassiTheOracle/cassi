#!/bin/bash
# Converged brain (MultimodalBrain = HarmonyBrain + Changepoint + Soul + memory read + neuroplasticizer)
# Phase 1: physics_equations — resume from phase 0 HoneybeeBrain checkpoint
python3 train_multimodal.py \
    --phase 1 \
    --epochs 30 \
    --bs 512 \
    --steps-per-epoch 1000 \
    --lr 2e-4 \
    --brain-type multimodal \
    --D 16384 \
    --optimizer wave \
    --unfreeze-spine \
    --iir-coupled \
    --save-every 5 \
    --patience 10 \
    --resume \
    --save cassi_multimodal.pt \
    2>&1 | tee -a train_converged_phase1.log
