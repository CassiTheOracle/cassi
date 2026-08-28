"""
Load fused FP8 DiffusionGemma using accelerate.
Fix: tied encoder/decoder layers must be on SAME device.
"""
import os
import gc
import torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig
from accelerate import load_checkpoint_and_dispatch

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers

print(f"Layers: {n_layers}, Hidden: {text_cfg.hidden_size}")

tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

# Build device map: encoder and decoder layers MUST be on same device
# because weights are tied between them.
LAYERS_ON_GPU = 12

device_map = {
    "": 0,
    "model": 0,
    "model.embed_tokens": 0,
}

for i in range(n_layers):
    dev = 0 if i < LAYERS_ON_GPU else "cpu"
    device_map[f"model.decoder.layers.{i}"] = dev
    device_map[f"model.encoder.language_model.layers.{i}"] = dev

device_map["model.decoder.norm"] = 0
device_map["lm_head"] = 0

print(f"Device map: {LAYERS_ON_GPU}/{n_layers} layers on GPU (encoder+decoder tied)")

# Load empty model on meta
print("\nLoading empty model on meta...")
model = DiffusionGemmaForBlockDiffusion.from_pretrained(
    LOCAL_DIR,
    torch_dtype="auto",
    device_map="meta",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
print("Empty model loaded.")

# Use accelerate to load with custom device map
print("Loading weights with accelerate...")
gc.collect()
torch.cuda.empty_cache()

try:
    model = load_checkpoint_and_dispatch(
        model,
        LOCAL_DIR,
        device_map=device_map,
        offload_folder=None,
        dtype=None,
        offload_state_dict=False,
    )
    print("Load successful!")
except Exception as e:
    print(f"Load failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    raise

gpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cuda")
cpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cpu")
total_params = sum(p.numel() for p in model.parameters())
print(f"\nTotal params: {total_params / 1e9:.2f}B")
print(f"GPU params: {gpu_params / 1e9:.2f}B ({100*gpu_params/total_params:.1f}%)")
print(f"CPU params: {cpu_params / 1e9:.2f}B ({100*cpu_params/total_params:.1f}%)")

if torch.cuda.is_available():
    print(f"VRAM allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    print(f"VRAM reserved:  {torch.cuda.memory_reserved() / 1e9:.2f} GB")

# Test generation
print("\n--- Testing generation ---")
model.eval()

msgs = [{"role": "user", "content": "What is the golden ratio?"}]
inp = tok.apply_chat_template(
    msgs,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
)
inp = {k: v.to(DEVICE) for k, v in inp.items()}

import time
t0 = time.time()
try:
    with torch.no_grad():
        out = model.generate(**inp, max_new_tokens=32)
    dt = time.time() - t0
    text = tok.decode(out[0], skip_special_tokens=True)
    print(f"Time: {dt:.2f}s")
    print(f"Output: {text}")
except Exception as e:
    print(f"Generation failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

if torch.cuda.is_available():
    print(f"VRAM after gen: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

print("\nDone.")
