"""
Final attempt: load FP8 DiffusionGemma with correct device map.
Key fixes:
- Correct module paths (model.model.decoder.embed_tokens, not model.embed_tokens)
- Vision tower explicitly on CPU
- Fewer layers on GPU to stay under 24GB
- Tied encoder/decoder on same device
- Sequential loading (1 worker)
"""
import os
import gc
import torch
import transformers
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig

# Force sequential loading to avoid concurrent GPU memory spikes
transformers.core_model_loading.GLOBAL_WORKERS = 1
print(f"Loading with {transformers.core_model_loading.GLOBAL_WORKERS} worker(s)")

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers

print(f"Layers: {n_layers}, Hidden: {text_cfg.hidden_size}")

# Force float16 to halve memory
cfg.torch_dtype = torch.float16
cfg.dtype = "float16"
if hasattr(text_cfg, 'torch_dtype'):
    text_cfg.torch_dtype = torch.float16
if hasattr(text_cfg, 'dtype'):
    text_cfg.dtype = "float16"

tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

# Build device map
# In float16, experts per layer: gate_up ~0.95GB + down ~0.47GB = ~1.42GB
# Non-expert per layer: ~0.1GB
# 12 layers on GPU: 12 * 1.52 = ~18.2GB + embed ~1.5GB = ~19.7GB
LAYERS_ON_GPU = 12

device_map = {
    "": "cpu",  # default to CPU, not GPU
    "model": "cpu",
}

# Decoder on GPU for first N layers
for i in range(n_layers):
    dev = 0 if i < LAYERS_ON_GPU else "cpu"
    device_map[f"model.decoder.layers.{i}"] = dev
    device_map[f"model.encoder.language_model.layers.{i}"] = dev

# Embeddings and head on GPU
device_map["model.decoder.embed_tokens"] = 0
device_map["model.decoder.norm"] = 0
device_map["lm_head"] = 0

# Encoder on CPU (tied weights will be on GPU via decoder)
# Vision on CPU explicitly
device_map["model.encoder.vision_tower"] = "cpu"
device_map["model.encoder.embed_vision"] = "cpu"

print(f"Device map: {LAYERS_ON_GPU}/{n_layers} decoder layers on GPU")

print("\nLoading model...")
gc.collect()
torch.cuda.empty_cache()

try:
    model = DiffusionGemmaForBlockDiffusion.from_pretrained(
        LOCAL_DIR,
        config=cfg,
        torch_dtype=torch.float16,
        device_map=device_map,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
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
