"""
Robust FP8 DiffusionGemma loader for AMD RX 7900 XTX (24GB VRAM).
Tries multiple strategies to avoid OOM and tied-weight crashes.
"""
import os
import sys
import gc
import torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig
from huggingface_hub import snapshot_download

# Use local disk, not /tmp
LOCAL_DIR = "C:/Users/Carina/workspaces/Cassi/CassiAI/checkpoints/diffusiongemma-fp8"
MODEL_ID = "RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic"
DEVICE = "cuda:0"

def get_free_disk_gb(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / (1024**3)

def print_memory():
    if torch.cuda.is_available():
        alloc = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.memory_reserved() / 1e9
        print(f"  GPU: allocated={alloc:.2f}GB, reserved={reserved:.2f}GB")
    import psutil
    mem = psutil.virtual_memory()
    print(f"  RAM: used={mem.used/1e9:.2f}GB, available={mem.available/1e9:.2f}GB")

# ------------------------------------------------------------------
# 1. Download model files locally first (avoids streaming death)
# ------------------------------------------------------------------
print(f"Free disk at {LOCAL_DIR}: {get_free_disk_gb(LOCAL_DIR):.1f} GB")
print("Downloading model files (this may take a while)...")

try:
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=LOCAL_DIR,
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    print("Download complete.")
except Exception as e:
    print(f"Download failed: {e}")
    print("Trying to use cached files if any exist...")

print_memory()

# ------------------------------------------------------------------
# 2. Inspect config
# ------------------------------------------------------------------
print("\n--- Inspecting config ---")
cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
print(f"Model type: {cfg.model_type}")
print(f"Num hidden layers: {cfg.num_hidden_layers}")
print(f"Num experts: {cfg.num_experts}")
print(f"Vocab size: {cfg.vocab_size}")
if hasattr(cfg, 'quantization_config'):
    print(f"Quant config: {cfg.quantization_config}")
if hasattr(cfg, 'compressed_tensors_config'):
    print(f"Compressed tensors config: {cfg.compressed_tensors_config}")

# ------------------------------------------------------------------
# 3. Tokenizer
# ------------------------------------------------------------------
print("\n--- Loading tokenizer ---")
tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)
print("Tokenizer loaded.")

# ------------------------------------------------------------------
# 4. Strategy A: direct from_pretrained with low_cpu_mem_usage
# ------------------------------------------------------------------
print("\n--- Strategy A: from_pretrained with low_cpu_mem_usage ---")
print_memory()

try:
    model = DiffusionGemmaForBlockDiffusion.from_pretrained(
        LOCAL_DIR,
        torch_dtype="auto",           # keep FP8 format
        device_map="auto",
        max_memory={0: "22GiB", "cpu": "28GiB"},
        low_cpu_mem_usage=True,       # key: load directly to target device
        trust_remote_code=True,
    )
    print("Strategy A: SUCCESS")
    print_memory()
except Exception as e:
    print(f"Strategy A failed: {type(e).__name__}: {e}")
    model = None
    gc.collect()
    torch.cuda.empty_cache()

# ------------------------------------------------------------------
# 5. Strategy B: manual device map (if A fails on tied weights)
# ------------------------------------------------------------------
if model is None:
    print("\n--- Strategy B: custom device map ---")
    print_memory()

    # Load on meta to inspect structure
    print("Loading model on meta device...")
    try:
        model_meta = DiffusionGemmaForBlockDiffusion.from_pretrained(
            LOCAL_DIR,
            torch_dtype="auto",
            device_map="meta",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
    except Exception as e:
        print(f"Even meta loading failed: {e}")
        sys.exit(1)

    # Build device map: put as many layers on GPU as possible
    # Estimate: ~0.9GB per layer in FP8, embeddings ~0.5GB
    # Target: keep ~23GB on GPU, rest on CPU
    GPU_BUDGET_BYTES = 23 * 1024**3
    gpu_used = 0
    device_map = {}

    for name, param in model_meta.named_parameters():
        size = param.numel() * param.element_size()
        if gpu_used + size < GPU_BUDGET_BYTES:
            device_map[name] = 0
            gpu_used += size
        else:
            device_map[name] = "cpu"

    # Also map buffers
    for name, buf in model_meta.named_buffers():
        if name not in device_map:
            # Buffers are small, put on GPU
            device_map[name] = 0

    # Map modules (needed for dispatch_model)
    for name, module in model_meta.named_modules():
        if name not in device_map:
            # Default to GPU for empty modules
            device_map[name] = 0

    gpu_params = sum(1 for d in device_map.values() if d == 0)
    cpu_params = sum(1 for d in device_map.values() if d == "cpu")
    print(f"Device map: {gpu_params} tensors on GPU, {cpu_params} on CPU")
    print(f"GPU budget used: {gpu_used / 1e9:.2f} GB")

    del model_meta
    gc.collect()
    torch.cuda.empty_cache()

    # Now load with custom device map
    print("Loading with custom device map...")
    try:
        model = DiffusionGemmaForBlockDiffusion.from_pretrained(
            LOCAL_DIR,
            torch_dtype="auto",
            device_map=device_map,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        print("Strategy B: SUCCESS")
        print_memory()
    except Exception as e:
        print(f"Strategy B failed: {type(e).__name__}: {e}")
        model = None
        gc.collect()
        torch.cuda.empty_cache()

# ------------------------------------------------------------------
# 6. Strategy C: manual state_dict loading with map_location
# ------------------------------------------------------------------
if model is None:
    print("\n--- Strategy C: manual state_dict + map_location ---")
    print_memory()

    from accelerate import load_checkpoint_and_dispatch
    from accelerate.utils import get_balanced_memory, infer_auto_device_map

    # Load empty model on meta
    print("Loading empty model on meta...")
    model = DiffusionGemmaForBlockDiffusion.from_pretrained(
        LOCAL_DIR,
        torch_dtype="auto",
        device_map="meta",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )

    # Try to infer device map manually, skipping tied weight issues
    # by mapping all decoder keys to GPU and encoder-only keys to CPU
    print("Building device map from checkpoint keys...")
    from safetensors.torch import load_file

    # List all keys in the first shard
    shard_files = sorted([f for f in os.listdir(LOCAL_DIR) if f.endswith('.safetensors')])
    if shard_files:
        first_shard = os.path.join(LOCAL_DIR, shard_files[0])
        keys = list(load_file(first_shard, device="cpu").keys())
        print(f"First shard has {len(keys)} keys. Sample: {keys[:5]}")

    # Build a simple layer-based device map
    n_layers = cfg.num_hidden_layers
    # Put first 24 layers on GPU, rest on CPU (adjust based on memory)
    # Embeddings and lm_head on GPU
    manual_map = {
        "": 0,
        "model": 0,
        "model.embed_tokens": 0,
    }

    # Decoder layers
    for i in range(n_layers):
        dev = 0 if i < 24 else "cpu"
        manual_map[f"model.decoder.layers.{i}"] = dev

    # Encoder layers (tied, mostly scalars)
    for i in range(n_layers):
        manual_map[f"model.encoder.language_model.layers.{i}"] = "cpu"

    manual_map["lm_head"] = 0
    manual_map["model.decoder.norm"] = 0

    print(f"Manual device map has {len(manual_map)} entries")

    try:
        model = load_checkpoint_and_dispatch(
            model,
            LOCAL_DIR,
            device_map=manual_map,
            offload_folder=None,  # no disk offload to avoid bus error
            dtype="auto",
            offload_state_dict=False,
        )
        print("Strategy C: SUCCESS")
        print_memory()
    except Exception as e:
        print(f"Strategy C failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# ------------------------------------------------------------------
# 7. Verify model placement
# ------------------------------------------------------------------
print("\n--- Model placement ---")
gpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cuda")
cpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cpu")
total_params = sum(p.numel() for p in model.parameters())
print(f"Total params: {total_params / 1e9:.2f}B")
print(f"GPU params: {gpu_params / 1e9:.2f}B ({100*gpu_params/total_params:.1f}%)")
print(f"CPU params: {cpu_params / 1e9:.2f}B ({100*cpu_params/total_params:.1f}%)")
print_memory()

# ------------------------------------------------------------------
# 8. Test generation
# ------------------------------------------------------------------
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
# Move inputs to GPU since first layer is there
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

print_memory()
print("\nDone.")
