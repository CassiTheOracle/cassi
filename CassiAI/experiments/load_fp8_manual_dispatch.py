"""
Manual dispatch: load on meta, fix encoder weight_scales from decoder, then dispatch.
"""
import os
import gc
import torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig
from accelerate import dispatch_model

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers

print(f"Layers: {n_layers}, Hidden: {text_cfg.hidden_size}")

# Force float16
torch.set_default_dtype(torch.float16)
cfg.torch_dtype = torch.float16
cfg.dtype = "float16"
if hasattr(text_cfg, 'torch_dtype'):
    text_cfg.torch_dtype = torch.float16
if hasattr(text_cfg, 'dtype'):
    text_cfg.dtype = "float16"

tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

# Build device map
LAYERS_ON_GPU = 12

device_map = {
    "": "cpu",
    "model": "cpu",
}

for i in range(n_layers):
    dev = 0 if i < LAYERS_ON_GPU else "cpu"
    device_map[f"model.decoder.layers.{i}"] = dev
    device_map[f"model.encoder.language_model.layers.{i}"] = dev

device_map["model.decoder.embed_tokens"] = 0
device_map["model.decoder.norm"] = 0
device_map["lm_head"] = 0
device_map["model.encoder.vision_tower"] = "cpu"
device_map["model.encoder.embed_vision"] = "cpu"

print(f"Device map: {LAYERS_ON_GPU}/{n_layers} layers on GPU")

# Step 1: Load on meta
print("\nStep 1: Loading model on meta...")
model = DiffusionGemmaForBlockDiffusion.from_pretrained(
    LOCAL_DIR,
    config=cfg,
    torch_dtype=torch.float16,
    device_map="meta",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
print("Model loaded on meta.")

# Step 2: Fix encoder weight_scales by copying from decoder
print("Step 2: Fixing encoder weight_scales...")
for i in range(n_layers):
    dec_layer = model.model.decoder.layers[i]
    enc_layer = model.model.encoder.language_model.layers[i]
    
    # Copy weight_scale from decoder to encoder for each quantized submodule
    for dec_name, dec_mod in dec_layer.named_modules():
        if hasattr(dec_mod, 'weight_scale'):
            # Find corresponding encoder module
            enc_mod = enc_layer
            for part in dec_name.split('.'):
                if part:
                    enc_mod = getattr(enc_mod, part)
            
            if hasattr(enc_mod, 'weight_scale') and enc_mod.weight_scale.device.type == 'meta':
                enc_mod.weight_scale = dec_mod.weight_scale
                # print(f"  Layer {i}: copied {dec_name}.weight_scale")

print("Encoder weight_scales fixed.")

# Step 3: Manual dispatch
print("Step 3: Dispatching model...")
gc.collect()
torch.cuda.empty_cache()

try:
    model = dispatch_model(model, device_map=device_map)
    print("Dispatch successful!")
except Exception as e:
    print(f"Dispatch failed: {type(e).__name__}: {e}")
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
