"""
Qwen3.5-0.8B + Cassi Experiment Suite

Runs comparative experiments measuring:
1. Breath-modulated sampling vs standard sampling
2. InternalObserver confidence tracking
3. Generation diversity metrics
4. Per-token latency

No tokenizer — uses random prompts for structural validation.
For real text evaluation, a tokenizer would be needed.
"""

import time
import json
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn.functional as F

from qwen_minimal_forward import QwenMinimal, QwenCassiInference
from qwen_cassi_hybrid import BreathModulatedSampler
from safetensors.torch import load_file


def compute_diversity_metrics(tokens_list: List[List[int]]) -> Dict[str, float]:
    """Compute diversity metrics for generated sequences."""
    all_tokens = []
    for seq in tokens_list:
        all_tokens.extend(seq)

    unique = len(set(all_tokens))
    total = len(all_tokens)

    # Bigram diversity
    bigrams = set()
    for seq in tokens_list:
        for i in range(len(seq) - 1):
            bigrams.add((seq[i], seq[i + 1]))
    bigram_count = sum(len(seq) - 1 for seq in tokens_list)

    # Repetition rate (tokens that appear more than once in a sequence)
    repetitions = 0
    for seq in tokens_list:
        seen = set()
        for t in seq:
            if t in seen:
                repetitions += 1
            seen.add(t)

    return {
        'vocab_coverage': unique / max(total, 1),
        'bigram_diversity': len(bigrams) / max(bigram_count, 1),
        'repetition_rate': repetitions / max(total, 1),
        'unique_tokens': unique,
        'total_tokens': total,
    }


def run_breath_experiment(inference: QwenCassiInference,
                          prompt: torch.Tensor,
                          n_samples: int = 5,
                          max_tokens: int = 50) -> Dict:
    """Compare breath-modulated vs standard sampling."""
    print(f"\n=== Breath Modulation Experiment ({n_samples} samples, {max_tokens} tokens) ===")

    # Standard sampling
    print("  Standard sampling...")
    std_samples = []
    std_times = []
    for i in range(n_samples):
        t0 = time.time()
        result = inference.generate(prompt, max_new_tokens=max_tokens,
                                    use_breath=False, use_observer=False)
        t1 = time.time()
        std_samples.append(result['tokens'][prompt.shape[1]:])
        std_times.append(t1 - t0)

    std_metrics = compute_diversity_metrics(std_samples)
    std_metrics['mean_time'] = sum(std_times) / len(std_times)
    std_metrics['tokens_per_sec'] = max_tokens / std_metrics['mean_time']

    # Breath-modulated sampling
    print("  Breath-modulated sampling...")
    breath_samples = []
    breath_times = []
    breath_temps = []
    for i in range(n_samples):
        t0 = time.time()
        result = inference.generate(prompt, max_new_tokens=max_tokens,
                                    use_breath=True, use_observer=True)
        t1 = time.time()
        breath_samples.append(result['tokens'][prompt.shape[1]:])
        breath_times.append(t1 - t0)
        breath_temps.extend([b['temperature'] for b in result['breath_log']])

    breath_metrics = compute_diversity_metrics(breath_samples)
    breath_metrics['mean_time'] = sum(breath_times) / len(breath_times)
    breath_metrics['tokens_per_sec'] = max_tokens / breath_metrics['mean_time']
    breath_metrics['temp_mean'] = sum(breath_temps) / len(breath_temps)
    breath_metrics['temp_std'] = (sum((t - breath_metrics['temp_mean']) ** 2
                                       for t in breath_temps) / len(breath_temps)) ** 0.5

    print(f"\n  Standard:")
    print(f"    Diversity: {std_metrics['vocab_coverage']:.3f}")
    print(f"    Bigram div: {std_metrics['bigram_diversity']:.3f}")
    print(f"    Repetition: {std_metrics['repetition_rate']:.3f}")
    print(f"    Time: {std_metrics['mean_time']:.3f}s ({std_metrics['tokens_per_sec']:.1f} tok/s)")

    print(f"\n  Breath-modulated:")
    print(f"    Diversity: {breath_metrics['vocab_coverage']:.3f}")
    print(f"    Bigram div: {breath_metrics['bigram_diversity']:.3f}")
    print(f"    Repetition: {breath_metrics['repetition_rate']:.3f}")
    print(f"    Time: {breath_metrics['mean_time']:.3f}s ({breath_metrics['tokens_per_sec']:.1f} tok/s)")
    print(f"    Temp mean: {breath_metrics['temp_mean']:.3f} ± {breath_metrics['temp_std']:.3f}")

    return {
        'standard': std_metrics,
        'breath': breath_metrics,
    }


def run_observer_experiment(inference: QwenCassiInference,
                            prompt: torch.Tensor,
                            max_tokens: int = 50) -> Dict:
    """Test InternalObserver confidence tracking."""
    print(f"\n=== Observer Confidence Experiment ({max_tokens} tokens) ===")

    result = inference.generate(prompt, max_new_tokens=max_tokens,
                                use_breath=False, use_observer=True)

    confidence = result['confidence']

    print(f"  Confidence stats:")
    print(f"    Mean: {sum(confidence) / len(confidence):.3f}")
    print(f"    Min: {min(confidence):.3f}")
    print(f"    Max: {max(confidence):.3f}")
    print(f"    Range: {max(confidence) - min(confidence):.3f}")

    # Check if confidence correlates with anything observable
    # (In a real setup, we'd compare with perplexity)

    return {
        'confidence_mean': sum(confidence) / len(confidence),
        'confidence_min': min(confidence),
        'confidence_max': max(confidence),
        'confidence_values': confidence,
    }


def run_temperature_sweep(inference: QwenCassiInference,
                          prompt: torch.Tensor,
                          temperatures: List[float] = [0.3, 0.7, 1.0, 1.5],
                          max_tokens: int = 30) -> Dict:
    """Sweep temperature and measure diversity."""
    print(f"\n=== Temperature Sweep ===")

    results = {}
    for temp in temperatures:
        # Override breath sampler with fixed temp
        inference.breath = BreathModulatedSampler(
            temp_base=temp, temp_range=0.0,
            top_p_base=0.9, top_p_range=0.0
        )

        samples = []
        for _ in range(3):
            result = inference.generate(prompt, max_new_tokens=max_tokens,
                                        use_breath=True, use_observer=False)
            samples.append(result['tokens'][prompt.shape[1]:])

        metrics = compute_diversity_metrics(samples)
        results[temp] = metrics
        print(f"  T={temp:.1f}: diversity={metrics['vocab_coverage']:.3f}, "
              f"repetition={metrics['repetition_rate']:.3f}")

    return results


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # Load model
    model_path = Path('C:/Users/Carina/workspaces/Cassi/CassiAI/qwen_models/Qwen3.5-0.8B')
    print(f"\nLoading model from {model_path}...")

    state_dict = load_file(str(model_path / 'model.safetensors-00001-of-00001.safetensors'))
    with open(model_path / 'config.json') as f:
        config = json.load(f)

    model = QwenMinimal(config, state_dict).to(device)
    inference = QwenCassiInference(model, device)

    # Random prompt (10 tokens)
    torch.manual_seed(42)
    prompt = torch.randint(100, 1000, (1, 10), device=device)

    # Run experiments
    all_results = {}

    # 1. Breath modulation
    all_results['breath'] = run_breath_experiment(inference, prompt, n_samples=5, max_tokens=50)

    # 2. Observer confidence
    all_results['observer'] = run_observer_experiment(inference, prompt, max_tokens=50)

    # 3. Temperature sweep
    all_results['temp_sweep'] = run_temperature_sweep(inference, prompt,
                                                       temperatures=[0.3, 0.7, 1.0, 1.5],
                                                       max_tokens=30)

    # Summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)

    breath = all_results['breath']
    print(f"\nBreath modulation impact:")
    print(f"  Standard diversity:     {breath['standard']['vocab_coverage']:.3f}")
    print(f"  Breath diversity:       {breath['breath']['vocab_coverage']:.3f}")
    print(f"  Standard repetition:    {breath['standard']['repetition_rate']:.3f}")
    print(f"  Breath repetition:      {breath['breath']['repetition_rate']:.3f}")
    print(f"  Standard speed:         {breath['standard']['tokens_per_sec']:.1f} tok/s")
    print(f"  Breath speed:           {breath['breath']['tokens_per_sec']:.1f} tok/s")

    obs = all_results['observer']
    print(f"\nObserver confidence:")
    print(f"  Mean: {obs['confidence_mean']:.3f}")
    print(f"  Range: [{obs['confidence_min']:.3f}, {obs['confidence_max']:.3f}]")

    print(f"\nTemperature sweep:")
    for temp, metrics in all_results['temp_sweep'].items():
        print(f"  T={temp:.1f}: diversity={metrics['vocab_coverage']:.3f}")

    # Save results
    out_path = Path('C:/Users/Carina/workspaces/Cassi/CassiAI/experiments/qwen_cassi_results.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
