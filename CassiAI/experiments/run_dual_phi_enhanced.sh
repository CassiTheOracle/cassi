#!/bin/bash
# DualCassi with all Phase 1-8 enhancements:
#   - Breath-driven workspace update
#   - φ-balance regularization (workspace + conscious + breath freq)
#   - Metacognitive monitor (curiosity / confusion / confidence)
#   - Multi-step imagination consistency
#   - BerryMemory trajectory store
#   - Qi-state seasonal nudge fix
#   - Curiosity-driven curriculum (active in mixed-modality phases)
#   - Optional multi-scale byte encoder
#   - Optional ModelEMA
#
# ROCm workarounds:
#   PYTORCH_HIP_ALLOC_CONF=expandable_segments:True  # reduce memory fragmentation
#   HSA_ENABLE_SDMA=0                                # avoid SDMA hangs on RDNA3

set -e

PHASE=0
EPOCHS=90
BS=32
LR=2e-4
SAVE="dual_cassi_phi_enhanced.pt"
LOG="logs/dual_cassi_phi_enhanced.log"

mkdir -p logs/metrics logs/test_metrics

env PYTORCH_HIP_ALLOC_CONF=expandable_segments:True HSA_ENABLE_SDMA=0 \
python3 -u train_multimodal.py \
    --brain-type dual \
    --phase ${PHASE} \
    --epochs ${EPOCHS} \
    --bs ${BS} \
    --steps-per-epoch 1000 \
    --lr ${LR} \
    --optimizer wave \
    --horizons 1 4 16 \
    --use-berry \
    --use-changepoint \
    --use-soul \
    --use-dream \
    --multi-scale-bytes \
    --use-ema \
    --ema-decay 0.999 \
    --save ${SAVE} \
    --save-every 5 \
    --patience 50 \
    2>&1 | tee ${LOG}
