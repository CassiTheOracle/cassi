"""
Load FP8 DiffusionGemma to CPU first, then manually dispatch.
Avoids meta-device complexity.
"""
import os
import gc
import torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer, AutoConfig

LOCAL_DIR = "checkpoints/diffusiongemma-fp8-fused"
DEVICE = "cuda:0"

cfg = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
text_cfg = cfg.text_config
n_layers = text_cfg.num_hidden_layers

print(f"Layers: {n_layers}, Hidden: {text_cfg.hidden_size}")

tok = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

# Monkey-patch expert forward for FP8 dequantization
print("Monkey-patching expert forward...")
from transformers.models.diffusion_gemma.modeling_diffusion_gemma import DiffusionGemmaTextExperts

def fp8_forward(self, hidden_states, top_k_index, top_k_weights):
    final_hidden_states = torch.zeros_like(hidden_states)
    for expert_idx in range(self.num_experts):
        expert_mask = (top_k_index == expert_idx).any(dim=-1)
        if not expert_mask.any():
            continue
        expert_tokens = hidden_states[expert_mask]
        gate_up_weight = self.gate_up_proj[expert_idx].to(torch.bfloat16)
        down_weight = self.down_proj[expert_idx].to(torch.bfloat16)
        gate, up = torch.nn.functional.linear(expert_tokens, gate_up_weight).chunk(2, dim=-1)
        expert_output = torch.nn.functional.linear(self.act_fn(gate) * up, down_weight)
        weights = top_k_weights[expert_mask][top_k_index[expert_mask] == expert_idx]
        final_hidden_states[expert_mask] += expert_output * weights.unsqueeze(-1)
    return final_hidden_states

DiffusionGemmaTextExperts.forward = fp8_forward

# Step 1: Load to CPU
print("\nStep 1: Loading model to CPU...")
gc.collect()
torch.cuda.empty_cache()

try:
    model = DiffusionGemmaForBlockDiffusion.from_pretrained(
        LOCAL_DIR,
        config=cfg,
        torch_dtype="auto",
        device_map=None,  # CPU
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    print("Model loaded to CPU.")
except Exception as e:
    print(f"Load failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    raise

# Step 2: Manually move layers to GPU
print("Step 2: Moving layers to GPU...")
LAYERS_ON_GPU = 12

for i in range(n_layers):
    if i < LAYERS_ON_GPU:
        model.model.decoder.layers[i] = model.model.decoder.layers[i].to(DEVICE)
        model.model.encoder.language_model.layers[i] = model.model.encoder.language_model.layers[i].to(DEVICE)

model.model.decoder.embed_tokens = model.model.decoder.embed_tokens.to(DEVICE)
model.model.decoder.norm = model.model.decoder.norm.to(DEVICE)
model.lm_head = model.lm_head.to(DEVICE)

print(f"Moved {LAYERS_ON_GPU} layers to GPU.")

# Check memory
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
