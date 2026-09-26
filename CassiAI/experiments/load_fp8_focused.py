"""
Focused FP8 DiffusionGemma loader.
Single 26GB safetensors file. Strategy: custom layer-based device_map.
"""
import os
import gc
import torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

# --- Config ---
cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers
n_experts = text_cfg.num_experts
hidden_size = text_cfg.hidden_size
vocab_size = text_cfg.vocab_size

print(f"Layers: {n_layers}, Experts: {n_experts}, Hidden: {hidden_size}, Vocab: {vocab_size}")
print(f"Quantization: {cfg.quantization_config.get('format', 'none')}")

# --- Tokenizer ---
tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

# --- Build custom device map ---
# Put first N layers on GPU, rest on CPU.
# Estimate: 26GB total / 30 layers ≈ 0.87GB per layer in FP8.
# Target ~22GB on GPU to leave headroom.
LAYERS_ON_GPU = 22

device_map = {
    "": 0,
    "model": 0,
    "model.embed_tokens": 0,
}

# Decoder layers (the heavy ones with experts)
for i in range(n_layers):
    device_map[f"model.decoder.layers.{i}"] = 0 if i < LAYERS_ON_GPU else "cpu"

# Encoder layers (tied to decoder, mostly scalars + unquantized routers)
for i in range(n_layers):
    device_map[f"model.encoder.language_model.layers.{i}"] = "cpu"

# Final norm and head
device_map["model.decoder.norm"] = 0
device_map["lm_head"] = 0

gpu_layers = sum(1 for k, v in device_map.items() if isinstance(v, int) and "decoder.layers" in k)
print(f"Device map: {gpu_layers}/{n_layers} decoder layers on GPU")

# --- Load model ---
print("\nLoading model with custom device_map...")
gc.collect()
torch.cuda.empty_cache()

try:
    model = DiffusionGemmaForBlockDiffusion.from_pretrained(
        LOCAL_DIR,
        torch_dtype="auto",
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

# --- Verify placement ---
gpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cuda")
cpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cpu")
total_params = sum(p.numel() for p in model.parameters())
print(f"\nTotal params: {total_params / 1e9:.2f}B")
print(f"GPU params: {gpu_params / 1e9:.2f}B ({100*gpu_params/total_params:.1f}%)")
print(f"CPU params: {cpu_params / 1e9:.2f}B ({100*cpu_params/total_params:.1f}%)")

if torch.cuda.is_available():
    print(f"VRAM allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    print(f"VRAM reserved:  {torch.cuda.memory_reserved() / 1e9:.2f} GB")

# --- Test generation ---
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
