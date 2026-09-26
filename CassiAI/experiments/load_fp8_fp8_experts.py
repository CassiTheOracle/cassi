"""
Load FP8 DiffusionGemma while keeping expert weights in FP8 format.
Corrected device map paths.
"""
import os
import gc
import torch
from safetensors import safe_open
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig
from accelerate import dispatch_model

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers

print(f"Layers: {n_layers}, Hidden: {text_cfg.hidden_size}")

torch.set_default_dtype(torch.bfloat16)
cfg.torch_dtype = torch.bfloat16
cfg.dtype = "bfloat16"
if hasattr(text_cfg, 'torch_dtype'):
    text_cfg.torch_dtype = torch.bfloat16
if hasattr(text_cfg, 'dtype'):
    text_cfg.dtype = "bfloat16"

tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

LAYERS_ON_GPU = 22

# Correct device map paths: model.model.decoder..., model.model.encoder...
device_map = {
    "": "cpu",
    "model": "cpu",
    "model.model": "cpu",
}

for i in range(n_layers):
    dev = 0 if i < LAYERS_ON_GPU else "cpu"
    device_map[f"model.model.decoder.layers.{i}"] = dev
    device_map[f"model.model.encoder.language_model.layers.{i}"] = dev

device_map["model.model.decoder.embed_tokens"] = 0
device_map["model.model.decoder.norm"] = 0
device_map["lm_head"] = 0
device_map["model.model.encoder.vision_tower"] = "cpu"
device_map["model.model.encoder.embed_vision"] = "cpu"

print(f"Device map: {LAYERS_ON_GPU}/{n_layers} layers on GPU")

# Monkey-patch expert forward for FP8 dequantization
print("Monkey-patching expert forward...")
from transformers.models.diffusion_gemma.modeling_diffusion_gemma import DiffusionGemmaTextExperts

original_forward = DiffusionGemmaTextExperts.forward

def fp8_forward(self, hidden_states, top_k_index, top_k_weights):
    batch_size = hidden_states.shape[0]
    current_state = hidden_states
    final_hidden_states = torch.zeros_like(hidden_states)
    
    for expert_idx in range(self.num_experts):
        expert_mask = (top_k_index == expert_idx).any(dim=-1)
        if not expert_mask.any():
            continue
        
        expert_tokens = current_state[expert_mask]
        
        gate_up_weight = self.gate_up_proj[expert_idx].to(torch.bfloat16)
        down_weight = self.down_proj[expert_idx].to(torch.bfloat16)
        
        gate, up = torch.nn.functional.linear(expert_tokens, gate_up_weight).chunk(2, dim=-1)
        expert_output = torch.nn.functional.linear(self.act_fn(gate) * up, down_weight)
        
        weights = top_k_weights[expert_mask][top_k_index[expert_mask] == expert_idx]
        final_hidden_states[expert_mask] += expert_output * weights.unsqueeze(-1)
    
    return final_hidden_states

DiffusionGemmaTextExperts.forward = fp8_forward

# Step 1: Load on meta
print("\nStep 1: Loading model on meta...")
model = DiffusionGemmaForBlockDiffusion.from_pretrained(
    LOCAL_DIR,
    config=cfg,
    torch_dtype="auto",
    device_map="meta",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
print("Model loaded on meta.")

# Step 2: Manually load expert weights in FP8 format
print("Step 2: Loading expert weights manually...")
with safe_open(os.path.join(LOCAL_DIR, "model.safetensors"), framework="pt") as f:
    for i in range(n_layers):
        dec_layer = model.model.decoder.layers[i]
        enc_layer = model.model.encoder.language_model.layers[i]
        
        for proj_name in ["gate_up_proj", "down_proj"]:
            key = f"model.decoder.layers.{i}.experts.{proj_name}"
            if key in f.keys():
                tensor = f.get_tensor(key)  # Keep as FP8
                setattr(dec_layer.experts, proj_name, torch.nn.Parameter(tensor))
                setattr(enc_layer.experts, proj_name, getattr(dec_layer.experts, proj_name))

print("Expert weights loaded in FP8.")

# Step 3: Copy ALL decoder params/buffers to encoder (tied weights)
print("Step 3: Copying tied decoder weights to encoder...")
for i in range(n_layers):
    dec_layer = model.model.decoder.layers[i]
    enc_layer = model.model.encoder.language_model.layers[i]
    
    for dec_name, dec_param in dec_layer.named_parameters():
        enc_mod = enc_layer
        parts = dec_name.split(".")
        for part in parts[:-1]:
            enc_mod = getattr(enc_mod, part)
        enc_param_name = parts[-1]
        if hasattr(enc_mod, enc_param_name):
            enc_param = getattr(enc_mod, enc_param_name)
            if enc_param.device.type == "meta" and dec_param.device.type != "meta":
                setattr(enc_mod, enc_param_name, dec_param)
    
    for dec_name, dec_buf in dec_layer.named_buffers():
        enc_mod = enc_layer
        parts = dec_name.split(".")
        for part in parts[:-1]:
            enc_mod = getattr(enc_mod, part)
        enc_buf_name = parts[-1]
        if hasattr(enc_mod, enc_buf_name):
            enc_buf = getattr(enc_mod, enc_buf_name)
            if enc_buf.device.type == "meta" and dec_buf.device.type != "meta":
                enc_mod.register_buffer(enc_buf_name, dec_buf)

model.model.encoder.language_model.embed_tokens = model.model.decoder.embed_tokens
model.model.encoder.language_model.norm = model.model.decoder.norm

print("Tied weights copied.")

# Step 4: Initialize any remaining meta tensors
print("Step 4: Initializing remaining meta tensors...")
for name, param in list(model.named_parameters()):
    if param.device.type == "meta":
        parts = name.split(".")
        module = model
        for part in parts[:-1]:
            module = getattr(module, part)
        new_param = torch.nn.Parameter(torch.empty_like(param, device="cpu"))
        setattr(module, parts[-1], new_param)

for name, buf in list(model.named_buffers()):
    if buf.device.type == "meta":
        parts = name.split(".")
        module = model
        for part in parts[:-1]:
            module = getattr(module, part)
        new_buf = torch.zeros_like(buf, device="cpu")
        module.register_buffer(parts[-1], new_buf)

print("Meta tensors initialized.")

# Step 5: Dispatch
print("Step 5: Dispatching model...")
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
