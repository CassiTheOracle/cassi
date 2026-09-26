"""
Convert unfused FP8 expert weights to fused format expected by DiffusionGemma.
The checkpoint has experts.{i}.gate_proj/up_proj/down_proj (unfused)
The model expects experts.gate_up_proj and experts.down_proj (fused).
"""
import os
import re
import torch
from safetensors.torch import load_file, save_file

SRC_DIR = "checkpoints/diffusiongemma-fp8"
DST_DIR = "checkpoints/diffusiongemma-fp8-fused"
os.makedirs(DST_DIR, exist_ok=True)

print("Loading source checkpoint...")
state_dict = load_file(os.path.join(SRC_DIR, "model.safetensors"))
print(f"Loaded {len(state_dict)} tensors")

# Patterns for unfused expert weights
# e.g. model.decoder.layers.3.experts.12.gate_proj.weight
unfused_re = re.compile(
    r"^(model\.decoder\.layers\.\d+\.experits\.(\d+)\.(gate_proj|up_proj|down_proj)\.(weight|weight_scale))$"
)

# Actually, looking at the load report, the keys are:
# model.decoder.layers.{0...29}.experts.{0...127}.down_proj.weight
# Let me list a sample first
sample_keys = [k for k in state_dict.keys() if "experts.0.gate_proj.weight" in k][:5]
print("Sample expert keys:", sample_keys)

# Let's find all decoder expert keys
expert_keys = [k for k in state_dict.keys() if ".experts." in k and "model.decoder.layers." in k]
print(f"Found {len(expert_keys)} decoder expert tensors")

# Group by layer and expert index
from collections import defaultdict
layer_experts = defaultdict(lambda: defaultdict(dict))

for key in expert_keys:
    # Parse: model.decoder.layers.L.experts.E.COMPONENT.SUFFIX
    m = re.match(r"(model\.decoder\.layers\.\d+\.experts)\.(\d+)\.(gate_proj|up_proj|down_proj)\.(weight_scale|weight)$", key)
    if not m:
        continue
    prefix, expert_idx, component, suffix = m.groups()
    layer_experts[prefix][int(expert_idx)][f"{component}.{suffix}"] = key

print(f"Found {len(layer_experts)} layers with unfused experts")

# Fuse them
new_state_dict = {}
removed_keys = set()

for prefix, experts in layer_experts.items():
    num_experts = len(experts)
    # Get shapes from first expert
    e0 = experts[0]
    gate_w = state_dict[e0["gate_proj.weight"]]
    up_w = state_dict[e0["up_proj.weight"]]
    down_w = state_dict[e0["down_proj.weight"]]

    # gate_up_proj: [num_experts, 2*intermediate_dim, hidden_dim]
    # For nn.Linear, weight is [out_features, in_features]
    # gate_proj: [interm, hidden], up_proj: [interm, hidden]
    interm, hidden = gate_w.shape
    gate_up = torch.empty(num_experts, 2 * interm, hidden, dtype=gate_w.dtype, device="cpu")
    down = torch.empty(num_experts, hidden, interm, dtype=down_w.dtype, device="cpu")

    # Handle scales if present
    has_gate_scale = "gate_proj.weight_scale" in e0
    has_up_scale = "up_proj.weight_scale" in e0
    has_down_scale = "down_proj.weight_scale" in e0

    if has_gate_scale and has_up_scale:
        gate_s = state_dict[e0["gate_proj.weight_scale"]]
        # Scale shape depends on strategy; typically [out_features, 1] or [out_features]
        # For concatenation, we just cat along the first dim
        gate_up_scale = torch.empty(num_experts, 2 * interm, *gate_s.shape[1:], dtype=gate_s.dtype, device="cpu")
    else:
        gate_up_scale = None

    if has_down_scale:
        down_s = state_dict[e0["down_proj.weight_scale"]]
        down_scale = torch.empty(num_experts, *down_s.shape, dtype=down_s.dtype, device="cpu")
    else:
        down_scale = None

    for eidx in range(num_experts):
        e = experts[eidx]
        gate_up[eidx, :interm] = state_dict[e["gate_proj.weight"]]
        gate_up[eidx, interm:] = state_dict[e["up_proj.weight"]]
        down[eidx] = state_dict[e["down_proj.weight"]]

        if gate_up_scale is not None:
            gate_s = state_dict[e["gate_proj.weight_scale"]]
            up_s = state_dict[e["up_proj.weight_scale"]]
            gate_up_scale[eidx, :interm] = gate_s
            gate_up_scale[eidx, interm:] = up_s

        if down_scale is not None:
            down_scale[eidx] = state_dict[e["down_proj.weight_scale"]]

        # Mark old keys for removal
        for k in e.values():
            removed_keys.add(k)

    # Store fused weights
    new_state_dict[f"{prefix}.gate_up_proj"] = gate_up
    new_state_dict[f"{prefix}.down_proj"] = down
    if gate_up_scale is not None:
        new_state_dict[f"{prefix}.gate_up_proj.weight_scale"] = gate_up_scale
    if down_scale is not None:
        new_state_dict[f"{prefix}.down_proj.weight_scale"] = down_scale

    print(f"  {prefix}: fused {num_experts} experts -> gate_up {gate_up.shape}, down {down.shape}")

# Build final state dict: keep non-expert keys, add fused keys, remove unfused keys
final_state_dict = {}
for k, v in state_dict.items():
    if k not in removed_keys:
        final_state_dict[k] = v

for k, v in new_state_dict.items():
    final_state_dict[k] = v

print(f"\nFinal state dict: {len(final_state_dict)} tensors")
print(f"Removed {len(removed_keys)} unfused tensors, added {len(new_state_dict)} fused tensors")

# Save
print("Saving fused checkpoint...")
save_file(final_state_dict, os.path.join(DST_DIR, "model.safetensors"))

# Copy other files
import shutil
for fname in os.listdir(SRC_DIR):
    if fname == "model.safetensors":
        continue
    src = os.path.join(SRC_DIR, fname)
    dst = os.path.join(DST_DIR, fname)
    if os.path.isfile(src):
        shutil.copy2(src, dst)

print(f"Done. Fused checkpoint saved to {DST_DIR}")
print(f"Size: {os.path.getsize(os.path.join(DST_DIR, 'model.safetensors')) / 1e9:.2f} GB")
