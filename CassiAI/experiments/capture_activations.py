#!/usr/bin/env python3
"""Capture per-layer residual activations from a LARQL vindex model.

Runs inference on prompts from wikitext (or random) via
WalkModel.forward_with_capture() and saves per-layer residual streams to
a memory-mapped float16 numpy file for function-space distillation training.

Usage:
    ~/.venv/bin/python3 experiments/capture_activations.py \\
      --vindex-dir /home/valerie/.cassicore/models/gemma4-e2b-full.vindex \\
      --n-prompts 500 --min-tokens 64 --max-tokens 200 \\
      --output-dir datasets/activations/gemma4-e2b

Requires: larql Python package (maturin develop from cassicore/packages/larql).
Run this script with ~/.venv/bin/python3 — it will NOT work with system python.
"""

import argparse
import json
import os
import sys
import time

import numpy as np


# ── Prompt sources ──────────────────────────────────────────


def _load_wikitext_prompts(n_target, rng):
    """Load paragraphs from wikitext-103 (HuggingFace) for diversity.

    Returns a list of text paragraphs to sample prompts from.
    """
    from datasets import load_dataset

    print("Loading wikitext via HuggingFace datasets...")
    ds = load_dataset("Salesforce/wikitext", "wikitext-103-raw-v1",
                       split="train", streaming=True)
    # Collect only non-empty paragraphs with reasonable length.
    paragraphs = []
    for ex in ds:
        text = ex["text"].strip()
        if 50 <= len(text) <= 500:
            paragraphs.append(text)
        if len(paragraphs) >= n_target * 10:  # ~10x oversample for diversity
            break
    print(f"Loaded {len(paragraphs)} candidate paragraphs from wikitext")
    return paragraphs


def _wikitext_prompt(paragraphs, min_chars, max_chars, rng):
    """Sample one prompt from the wikitext paragraph pool."""
    para = paragraphs[rng.randint(0, len(paragraphs))]
    if len(para) < min_chars:
        return para  # will be filtered length-check later
    start = rng.randint(0, max(1, len(para) - min_chars))
    end = min(start + rng.randint(min_chars, max_chars + 1), len(para))
    prompt = para[start:end]
    # Try not to cut mid-word.
    last_space = prompt.rfind(" ")
    if last_space > min_chars // 2:
        prompt = prompt[:last_space]
    return prompt.strip()


def _random_prompt(min_chars, max_chars, rng):
    """Generate a random ASCII character sequence as a prompt."""
    length = rng.randint(min_chars, max_chars + 1)
    # Printable ASCII (letters, digits, spaces, basic punctuation).
    chars = []
    for _ in range(length):
        # 60% letters, 20% space/punctuation, 20% other common chars.
        r = rng.random()
        if r < 0.60:
            chars.append(chr(rng.randint(97, 122)))  # lowercase
        elif r < 0.80:
            chars.append(" ")
        else:
            chars.append(chr(rng.randint(33, 47)))  # punctuation
    return "".join(chars)


# ── Main ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Capture per-layer residuals from LARQL vindex model"
    )
    parser.add_argument(
        "--vindex-dir",
        type=str,
        default="/home/valerie/.cassicore/models/gemma4-e2b-full.vindex",
        help="Path to vindex directory (default: gemma4-e2b-full.vindex)",
    )
    parser.add_argument(
        "--prompt-source",
        type=str,
        default="wikitext",
        choices=["wikitext", "random"],
        help="Source of text prompts (default: wikitext)",
    )
    parser.add_argument(
        "--n-prompts", type=int, default=500, help="Number of prompts to process"
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=64,
        help="Minimum prompt length in tokens",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=200,
        help="Maximum prompt length in tokens",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/activations/gemma4-e2b",
        help="Output directory for residuals",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    args = parser.parse_args()

    # ── Venv guard ──
    try:
        import larql
    except ImportError:
        print(
            "ERROR: 'larql' package not found in current Python interpreter.\n"
            "This script requires LARQL (Rust Python bindings) which is only\n"
            "installed in the project venv at ~/.venv.\n\n"
            "Run it with:\n"
            "    ~/.venv/bin/python3 experiments/capture_activations.py ...\n"
            "NOT with /usr/bin/python3.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Load model ──
    print(f"Loading WalkModel from {args.vindex_dir}...")
    t_start = time.time()
    wm = larql.WalkModel(args.vindex_dir, top_k=8192)
    n_layers = wm.num_layers
    hidden_size = wm.hidden_size
    print(f"  num_layers={n_layers}, hidden_size={hidden_size} "
          f"({time.time() - t_start:.1f}s)")

    # ── RNG ──
    rng = np.random.RandomState(args.seed)

    # ── Prompt source setup ──
    # Character-estimate: ~1 token ≈ 4 chars for English text; be generous.
    min_chars = args.min_tokens * 3
    max_chars = args.max_tokens * 5

    if args.prompt_source == "wikitext":
        paragraphs = _load_wikitext_prompts(args.n_prompts, rng)
        if len(paragraphs) == 0:
            print("ERROR: No paragraphs loaded from wikitext.", file=sys.stderr)
            sys.exit(1)
    else:
        paragraphs = None  # random source does not use a pool

    # ── Output directory ──
    os.makedirs(args.output_dir, exist_ok=True)

    # Estimate total tokens for pre-allocation: n_prompts * avg_tokens.
    # We over-allocate slightly and will trim at the end.
    avg_est_tokens = (args.min_tokens + args.max_tokens) // 2
    est_total = args.n_prompts * avg_est_tokens
    shape = (est_total, n_layers, hidden_size)
    out_path = os.path.join(args.output_dir, "residuals.f16")

    print(f"Pre-allocating memmap ({shape[0]} estimated tokens, "
          f"{shape[1]} layers × {shape[2]} dim) ...")
    mmap = np.memmap(out_path, dtype=np.float16, mode="w+", shape=shape)
    write_pos = 0  # first unused row index in dim-0

    # ── Capture loop ──
    total_tokens = 0
    prompts_captured = 0
    prompt_token_counts = []
    layer_keys = list(range(n_layers))
    t_start_capture = time.time()

    while prompts_captured < args.n_prompts:
        # Get prompt text.
        if args.prompt_source == "wikitext":
            prompt = _wikitext_prompt(paragraphs, min_chars, max_chars, rng)
        else:
            prompt = _random_prompt(min_chars, max_chars, rng)

        if not prompt or len(prompt) < 10:
            continue

        # Run forward and capture.
        try:
            result = wm.forward_with_capture(prompt, layers=layer_keys)
        except Exception as e:
            print(f"  WARNING: prompt {prompts_captured + 1} failed: {e}")
            continue

        # Validate result and assemble layer stack.
        seq_len = None
        layer_arrays = []
        ok = True
        for L in layer_keys:
            if L not in result:
                print(f"  WARNING: layer {L} missing from result")
                ok = False
                break
            arr = result[L]
            if seq_len is None:
                seq_len = arr.shape[0]
            elif arr.shape[0] != seq_len:
                print(f"  WARNING: seq_len mismatch at layer {L}: "
                      f"{arr.shape[0]} != {seq_len}")
                ok = False
                break
            layer_arrays.append(arr)

        if not ok:
            continue

        # Stack: [seq_len, n_layers, hidden_size]
        # Clip to f16 range before cast to prevent overflow → inf/NaN.
        F16_MAX = 64000.0  # half of f16 max (65504), leaving margin
        stacked = np.stack(layer_arrays, axis=1)
        stacked = np.clip(stacked, -F16_MAX, F16_MAX).astype(np.float16)

        # Check we don't overflow the pre-allocated memmap.
        new_pos = write_pos + seq_len
        if new_pos > est_total:
            # Grow memmap: allocate a new larger one and copy.
            print(f"  Reached est_total ({est_total}), growing by 50%...")
            new_est = int(est_total * 1.5)
            new_shape = (new_est, n_layers, hidden_size)
            new_path = out_path + ".tmp"
            new_mmap = np.memmap(new_path, dtype=np.float16,
                                 mode="w+", shape=new_shape)
            new_mmap[:write_pos] = mmap[:write_pos]
            mmap.flush()
            del mmap
            os.replace(new_path, out_path)
            mmap = new_mmap
            est_total = new_est

        # Write into memmap.
        mmap[write_pos:new_pos] = stacked
        write_pos = new_pos
        total_tokens = write_pos
        prompt_token_counts.append(seq_len)
        prompts_captured += 1

        if prompts_captured % 50 == 0 or prompts_captured == args.n_prompts:
            mmap.flush()  # persist to disk with each progress interval
            elapsed = time.time() - t_start_capture
            print(f"  [{prompts_captured}/{args.n_prompts}] tokens={total_tokens}, "
                  f"{elapsed:.1f}s")

    # ── Finalize output ──
    if total_tokens == 0:
        print("ERROR: No prompts captured successfully.", file=sys.stderr)
        mmap.flush()
        del mmap
        os.remove(out_path)
        sys.exit(1)

    # Trim memmap to actual size by copying to a file of the real shape.
    print(f"Trimming memmap to actual size {total_tokens} tokens...")
    final_shape = (total_tokens, n_layers, hidden_size)
    trimmed_path = out_path + ".trimmed"
    trimmed = np.memmap(trimmed_path, dtype=np.float16, mode="w+",
                        shape=final_shape)
    trimmed[:] = mmap[:total_tokens]
    trimmed.flush()
    del mmap, trimmed
    os.replace(trimmed_path, out_path)

    # Write metadata.
    meta = {
        "n_layers": n_layers,
        "hidden_size": hidden_size,
        "total_tokens": total_tokens,
        "n_prompts_processed": prompts_captured,
        "prompt_token_counts": prompt_token_counts,
        "model": os.path.basename(args.vindex_dir),
        "prompt_source": args.prompt_source,
    }
    meta_path = os.path.join(args.output_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # ── Final stats ──
    t_total = time.time() - t_start
    size_gb = os.path.getsize(out_path) / (1024 ** 3)
    print(f"\nDone.")
    print(f"  Total tokens:    {total_tokens}")
    print(f"  Layers × dim:    {n_layers} × {hidden_size}")
    print(f"  Storage size:    {size_gb:.2f} GB")
    print(f"  Output file:     {out_path}")
    print(f"  Metadata file:   {meta_path}")
    print(f"  Total time:      {t_total:.1f}s")


if __name__ == "__main__":
    main()
