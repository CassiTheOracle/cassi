"""
Convert fused FP8 checkpoint to float16.
This avoids dtype issues during loading.
"""
import os
import torch
from safetensors.torch import load_file, save_file

SRC = "checkpoints/diffusiongemma-fp8-fused/model.safetensors"
DST = "checkpoints/diffusiongemma-fp8-fused/model.float16.safetensors"

print("Loading checkpoint...")
state_dict = load_file(SRC)
print(f"Loaded {len(state_dict)} tensors")

print("Converting float8_e4m3fn to float16...")
converted = 0
for key, tensor in state_dict.items():
    if tensor.dtype == torch.float8_e4m3fn:
        state_dict[key] = tensor.to(torch.float16)
        converted += 1

print(f"Converted {converted} tensors")

print("Saving float16 checkpoint...")
save_file(state_dict, DST)

size_gb = os.path.getsize(DST) / 1e9
print(f"Done. Saved to {DST} ({size_gb:.2f} GB)")
