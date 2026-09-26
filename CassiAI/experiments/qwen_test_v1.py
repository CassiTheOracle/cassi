import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = 'qwen_models/Qwen3.5-0.8B'
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=True)
print("Tokenizer loaded")
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, local_files_only=True, dtype=torch.float32, device_map='cuda')
print("Model loaded")

prompt = 'The golden ratio appears in nature'
inputs = tok(prompt, return_tensors='pt').to('cuda')
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=64, do_sample=True, temperature=0.8, top_p=0.85, pad_token_id=tok.eos_token_id)
print("Generated:", tok.decode(out[0], skip_special_tokens=True))
