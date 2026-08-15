#!/bin/bash
set -e

cd C:/Users/Carina/workspaces/Cassi/CassiAI

# Experiment 1: Standard generation
python -c "
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import time, json

model_id = 'qwen_models/Qwen3.5-0.8B'
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, local_files_only=True, dtype=torch.float32, device_map='cuda')
model.eval()

prompt = 'The golden ratio appears in nature'
inputs = tok(prompt, return_tensors='pt').to('cuda')
t0 = time.time()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=64, do_sample=True, temperature=0.8, top_p=0.85, pad_token_id=tok.eos_token_id)
dt = time.time() - t0

result = {'text': tok.decode(out[0], skip_special_tokens=True), 'speed': 64/dt}
with open('experiments/qwen_result_standard.json', 'w') as f:
    json.dump(result, f)
print(f'Standard: {64/dt:.1f} tok/s')
print(result['text'])
"

# Experiment 2: Breath-modulated generation
python -c "
import torch, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time, json

model_id = 'qwen_models/Qwen3.5-0.8B'
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, local_files_only=True, dtype=torch.float32, device_map='cuda')
model.eval()

prompt = 'The golden ratio appears in nature'
inputs = tok(prompt, return_tensors='pt').to('cuda')
input_ids = inputs['input_ids'][0].tolist()
past_key_values = None
t_yang = torch.tensor(0.0, device='cuda')
t_yin = torch.tensor(0.0, device='cuda')
metas = []

t0 = time.time()
for i in range(64):
    ids = torch.tensor([input_ids] if past_key_values is None else [[input_ids[-1]]], device='cuda')
    with torch.no_grad():
        out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True)
    logits = out.logits[0, -1, :]
    past_key_values = out.past_key_values
    t_yang += 0.15
    t_yin += 0.094
    temp = 0.8 + 0.15 * (torch.sin(t_yang) + torch.sin(t_yin))
    top_p = 0.85 + 0.1 * torch.sin(t_yang)
    probs = F.softmax(logits / temp.clamp(min=0.1), dim=-1)
    sorted_p, sorted_i = torch.sort(probs, descending=True)
    cumsum = torch.cumsum(sorted_p, dim=-1)
    remove = cumsum > top_p
    if remove.any():
        first = torch.where(remove)[0][0].item()
        if first > 0:
            remove[:first] = False
    keep = ~remove
    filtered = sorted_p * keep.float()
    filtered = filtered / filtered.sum()
    idx = torch.multinomial(filtered, num_samples=1).item()
    input_ids.append(sorted_i[idx].item())
    metas.append({'temp': temp.item(), 'top_p': top_p.item()})
    if input_ids[-1] == tok.eos_token_id:
        break
dt = time.time() - t0
n = len(metas)

result = {
    'text': tok.decode(input_ids, skip_special_tokens=True),
    'speed': n/dt,
    'avg_temp': sum(m['temp'] for m in metas)/n,
    'avg_top_p': sum(m['top_p'] for m in metas)/n,
    'count': n,
}
with open('experiments/qwen_result_breath.json', 'w') as f:
    json.dump(result, f)
print(f'Breath: {n/dt:.1f} tok/s, avg_temp={result[\"avg_temp\"]:.3f}')
print(result['text'])
"

# Experiment 3: Observer-augmented generation
python -c "
import torch, torch.nn as nn, torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time, json

model_id = 'qwen_models/Qwen3.5-0.8B'
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, local_files_only=True, dtype=torch.float32, device_map='cuda')
model.eval()

class Obs(nn.Module):
    def __init__(self, d, v):
        super().__init__()
        self.c = nn.Sequential(nn.Linear(d, d//4), nn.GELU(), nn.Linear(d//4, 1), nn.Sigmoid())
        self.i = nn.Sequential(nn.Linear(d, d//4), nn.GELU(), nn.Linear(d//4, 1), nn.Sigmoid())
        self.n = nn.Linear(d, v, bias=False)
    def forward(self, h):
        return self.c(h).squeeze(-1), self.i(h).squeeze(-1), self.n(h)

obs = Obs(model.config.hidden_size, model.config.vocab_size).to('cuda').eval()

prompt = 'The golden ratio appears in nature'
inputs = tok(prompt, return_tensors='pt').to('cuda')
input_ids = inputs['input_ids'][0].tolist()
past_key_values = None
observations = []

t0 = time.time()
for i in range(64):
    ids = torch.tensor([input_ids] if past_key_values is None else [[input_ids[-1]]], device='cuda')
    with torch.no_grad():
        out = model(input_ids=ids, past_key_values=past_key_values, use_cache=True, output_hidden_states=True)
    logits = out.logits[0, -1, :]
    past_key_values = out.past_key_values
    hidden = out.hidden_states[-1][0, -1, :].float()
    conf, imp, obs_logits = obs(hidden)
    probs = F.softmax(logits / 0.8, dim=-1)
    token = torch.multinomial(probs, num_samples=1).item()
    input_ids.append(token)
    observations.append({'token': tok.decode([token]), 'conf': conf.item(), 'imp': imp.item(), 'obs_top': tok.decode([torch.argmax(obs_logits).item()])})
    if token == tok.eos_token_id:
        break
dt = time.time() - t0
n = len(observations)

result = {
    'text': tok.decode(input_ids, skip_special_tokens=True),
    'speed': n/dt,
    'avg_conf': sum(o['conf'] for o in observations)/n,
    'avg_imp': sum(o['imp'] for o in observations)/n,
    'count': n,
    'first_5': observations[:5],
}
with open('experiments/qwen_result_observer.json', 'w') as f:
    json.dump(result, f)
print(f'Observer: {n/dt:.1f} tok/s, conf={result[\"avg_conf\"]:.3f}, imp={result[\"avg_imp\"]:.3f}')
print(result['text'])
"

# Combine results
python -c "
import json
results = {}
for name in ['standard', 'breath', 'observer']:
    with open(f'experiments/qwen_result_{name}.json') as f:
        results[name] = json.load(f)
with open('experiments/qwen_transformers_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Combined results saved to experiments/qwen_transformers_results.json')
"
