from transformers import DiffusionGemmaForBlockDiffusion, AutoTokenizer
import torch

print("Loading tokenizer...")
tok = AutoTokenizer.from_pretrained(
    "RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic",
    trust_remote_code=True,
)

print("Loading FP8 model...")
model = DiffusionGemmaForBlockDiffusion.from_pretrained(
    "RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic",
    torch_dtype=torch.bfloat16,
    device_map="auto",
    max_memory={0: "20GiB", "cpu": "30GiB"},
    trust_remote_code=True,
)
model.eval()

print(f"VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

gpu = sum(p.numel() for p in model.parameters() if p.device.type == "cuda")
cpu = sum(p.numel() for p in model.parameters() if p.device.type == "cpu")
print(f"GPU: {gpu / 1e9:.2f}B params, CPU: {cpu / 1e9:.2f}B params")

print("Testing generation...")
msgs = [{"role": "user", "content": "What is the golden ratio?"}]
inp = tok.apply_chat_template(
    msgs,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
)
inp = {k: v.to("cuda:0") for k, v in inp.items()}

import time
t0 = time.time()
with torch.no_grad():
    out = model.generate(**inp, max_new_tokens=64)
dt = time.time() - t0
text = tok.decode(out[0], skip_special_tokens=True)
print(f"Time: {dt:.2f}s, {64 / dt:.1f} tok/s")
print(f"Output: {text}")
