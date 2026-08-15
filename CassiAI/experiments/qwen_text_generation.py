"""
Real text generation with Qwen3.5-0.8B + Cassi tokenizer.

Tests:
1. Basic text generation (greedy, sampling, breath-modulated)
2. Chat-formatted generation
3. Observer confidence tracking per token
"""

import json
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from qwen_minimal_forward import QwenMinimal, QwenCassiInference
from qwen_tokenizer import QwenTokenizer
from safetensors.torch import load_file


def generate_text(inference: QwenCassiInference, tokenizer: QwenTokenizer,
                  prompt: str, max_tokens: int = 50, temperature: float = 0.7,
                  use_breath: bool = False, use_observer: bool = False) -> dict:
    """Generate text from a prompt.

    Returns dict with generated text, tokens, confidence, timing.
    """
    input_ids = torch.tensor([tokenizer.encode(prompt)], device=inference.device)

    t0 = time.time()
    result = inference.generate(input_ids, max_new_tokens=max_tokens,
                                use_breath=use_breath, use_observer=use_observer)
    t1 = time.time()

    # Decode only the new tokens
    all_tokens = result['tokens']
    new_tokens = all_tokens[input_ids.shape[1]:]
    generated_text = tokenizer.decode(new_tokens)

    output = {
        'prompt': prompt,
        'generated': generated_text,
        'n_tokens': len(new_tokens),
        'time': t1 - t0,
        'tokens_per_sec': len(new_tokens) / (t1 - t0),
    }

    if use_observer and result.get('confidence'):
        output['confidence_mean'] = sum(result['confidence']) / len(result['confidence'])
        output['confidence_min'] = min(result['confidence'])
        output['confidence_max'] = max(result['confidence'])

    if use_breath and result.get('breath_log'):
        temps = [b['temperature'] for b in result['breath_log']]
        output['temp_mean'] = sum(temps) / len(temps)
        output['temp_range'] = (min(temps), max(temps))

    return output


def generate_chat(inference: QwenCassiInference, tokenizer: QwenTokenizer,
                  messages: list, max_tokens: int = 100,
                  use_breath: bool = False) -> dict:
    """Generate a chat response."""
    prompt = tokenizer.build_chat_prompt(messages)
    return generate_text(inference, tokenizer, prompt, max_tokens=max_tokens,
                         use_breath=use_breath, use_observer=True)


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}\n")

    # Load model
    model_path = Path('C:/Users/Carina/workspaces/Cassi/CassiAI/qwen_models/Qwen3.5-0.8B')
    print(f"Loading model from {model_path}...")

    state_dict = load_file(str(model_path / 'model.safetensors-00001-of-00001.safetensors'))
    with open(model_path / 'config.json') as f:
        config = json.load(f)

    model = QwenMinimal(config, state_dict).to(device)
    inference = QwenCassiInference(model, device)

    # Load tokenizer
    tokenizer = QwenTokenizer(str(model_path / 'tokenizer.json'))
    print(f"Tokenizer loaded: {len(tokenizer)} tokens\n")

    # ================================================================
    # Test 1: Basic text generation
    # ================================================================
    print("=" * 60)
    print("TEST 1: Basic Text Generation")
    print("=" * 60)

    prompts = [
        "The capital of France is",
        "In the beginning,",
        "The quick brown fox",
    ]

    for prompt in prompts:
        print(f"\nPrompt: {prompt!r}")

        # Greedy
        result = generate_text(inference, tokenizer, prompt, max_tokens=20,
                               temperature=0.01, use_breath=False)
        print(f"  Greedy:    {result['generated']!r}")

        # Standard sampling
        result = generate_text(inference, tokenizer, prompt, max_tokens=20,
                               temperature=0.7, use_breath=False)
        print(f"  Sampling:  {result['generated']!r}")

        # Breath-modulated
        result = generate_text(inference, tokenizer, prompt, max_tokens=20,
                               use_breath=True, use_observer=True)
        print(f"  Breath:    {result['generated']!r}")
        print(f"    Speed: {result['tokens_per_sec']:.1f} tok/s")
        print(f"    Confidence: {result.get('confidence_mean', 0):.3f}")

    # ================================================================
    # Test 2: Chat generation
    # ================================================================
    print("\n" + "=" * 60)
    print("TEST 2: Chat Generation")
    print("=" * 60)

    chat_prompts = [
        [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'What is 2+2?'},
        ],
        [
            {'role': 'system', 'content': 'You are a creative writer.'},
            {'role': 'user', 'content': 'Write a haiku about the moon.'},
        ],
    ]

    for messages in chat_prompts:
        print(f"\nUser: {messages[-1]['content']!r}")

        result = generate_chat(inference, tokenizer, messages, max_tokens=40,
                               use_breath=False)
        print(f"  Standard: {result['generated']!r}")

        result = generate_chat(inference, tokenizer, messages, max_tokens=40,
                               use_breath=True)
        print(f"  Breath:   {result['generated']!r}")
        print(f"    Speed: {result['tokens_per_sec']:.1f} tok/s")

    # ================================================================
    # Test 3: Observer confidence analysis
    # ================================================================
    print("\n" + "=" * 60)
    print("TEST 3: Observer Confidence Analysis")
    print("=" * 60)

    prompt = "The meaning of life is"
    result = generate_text(inference, tokenizer, prompt, max_tokens=30,
                           use_breath=False, use_observer=True)

    print(f"\nPrompt: {prompt!r}")
    print(f"Generated: {result['generated']!r}")
    print(f"Confidence: mean={result['confidence_mean']:.3f}, "
          f"range=[{result['confidence_min']:.3f}, {result['confidence_max']:.3f}]")

    # ================================================================
    # Test 4: Breath rhythm visualization
    # ================================================================
    print("\n" + "=" * 60)
    print("TEST 4: Breath Rhythm")
    print("=" * 60)

    prompt = "Once upon a time"
    result = generate_text(inference, tokenizer, prompt, max_tokens=20,
                           use_breath=True, use_observer=False)

    print(f"\nPrompt: {prompt!r}")
    print(f"Generated: {result['generated']!r}")
    if 'temp_mean' in result:
        print(f"Temperature: mean={result['temp_mean']:.3f}, "
              f"range=[{result['temp_range'][0]:.3f}, {result['temp_range'][1]:.3f}]")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
