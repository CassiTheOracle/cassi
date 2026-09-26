#!/usr/bin/env python3
"""
Lightweight GPQA-Main evaluator for Qwen3.5-4B + Cassi.

Scores multiple-choice questions by reading the A/B/C/D logit at the final
position. This avoids format-following issues with the chat-tuned model.

Usage:
    python experiments/eval_gpqa_cassi.py
    python experiments/eval_gpqa_cassi.py --checkpoint experiments/cassi_full_4b_best.pt --residual --limit 50
"""

import argparse
import csv
import json
import random
import sys
import time
import torch
import torch.nn.functional as F

sys.path.insert(0, ".")
sys.path.insert(0, "experiments")

from qwen_4b_cassi_full import load_base_model, CassiAugmentedModel, LOCAL_MODEL_DIR, DEVICE
from transformers import AutoTokenizer

LETTER_TOKENS = {"A": 32, "B": 33, "C": 34, "D": 35}


def parse_gpqa(path):
    """Return list of dicts with shuffled A-D choices and correct letter."""
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = row["Question"].strip()
            correct = row["Correct Answer"].strip()
            incorrects = [
                row["Incorrect Answer 1"].strip(),
                row["Incorrect Answer 2"].strip(),
                row["Incorrect Answer 3"].strip(),
            ]
            choices = [("A", correct)] + [("B", inc) for inc in incorrects]
            random.shuffle(choices)
            letter_map = {c: l for l, c in choices}
            questions.append({
                "question": q,
                "choices": choices,
                "correct_letter": letter_map[correct],
            })
    return questions


def format_prompt(q, tokenizer=None):
    """Multiple-choice prompt; the next token should be the answer letter."""
    lines = [f"Question: {q['question']}"]
    for letter, text in q["choices"]:
        lines.append(f"{letter}. {text}")
    lines.append("\nAnswer:")
    prompt = "\n".join(lines)
    if tokenizer and tokenizer.chat_template:
        messages = [
            {"role": "system", "content": "You are taking a multiple-choice exam. Answer with a single letter."},
            {"role": "user", "content": prompt},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    return prompt


def score_base_logits(model, tokenizer, prompt, max_length=2048):
    """Return dict {letter: logit} for A-D at the final position."""
    inputs = tokenizer(prompt, return_tensors="pt", max_length=max_length, truncation=True).to(DEVICE)
    with torch.no_grad():
        out = model(**inputs)
    logits = out.logits[0, -1, :].float()
    return {letter: logits[token_id].item() for letter, token_id in LETTER_TOKENS.items()}


def score_cassi_logits(cassi, tokenizer, prompt, max_length=2048, obs_boost=1.0, spec_boost=1.0):
    """Return dict {letter: logit} for A-D after the Cassi harmony gate."""
    cassi.reset_state()
    input_ids = tokenizer(prompt, return_tensors="pt", max_length=max_length, truncation=True).to(DEVICE)["input_ids"]
    with torch.no_grad():
        out = cassi.base(
            input_ids=input_ids,
            output_hidden_states=True,
        )
    base_logits = out.logits[0, -1, :].float()
    hidden = out.hidden_states[-1][0, -1, :].float()

    conf, imp, obs_logits = cassi.observer(hidden)
    conf_val = conf.item() if conf.numel() == 1 else conf.mean().item()
    imp_val = imp.item() if imp.numel() == 1 else imp.mean().item()
    qi_coherence = cassi.qi.update(hidden)
    qi_val = qi_coherence.item() if isinstance(qi_coherence, torch.Tensor) else qi_coherence
    berry_bias, _ = cassi.berry.retrieve(hidden, k=5)
    if berry_bias is not None:
        berry_bias = berry_bias.float()
    spec_bias, _ = cassi.specialists(hidden)
    spec_bias = spec_bias.float()
    cassi.chakra.track(out.hidden_states)
    entropy = -(F.softmax(base_logits, dim=-1) * F.log_softmax(base_logits, dim=-1)).sum().item()
    cassi.neuro.update(input_ids[0, -1].item(), entropy)

    # Diagnostic boost of residual components
    if obs_logits is not None:
        obs_logits = obs_logits.float() * obs_boost
    if spec_bias is not None:
        spec_bias = spec_bias * spec_boost

    blended_logits, _ = cassi.harmony(
        base_logits, obs_logits, berry_bias, spec_bias, qi_val, conf_val
    )
    return {letter: blended_logits[token_id].item() for letter, token_id in LETTER_TOKENS.items()}


def predict_from_scores(scores):
    """Pick the letter with highest logit."""
    return max(scores, key=scores.get)


def evaluate(score_fn, questions, tokenizer):
    """score_fn(prompt) -> {A:logit, B:logit, C:logit, D:logit}."""
    correct = 0
    details = []
    t0 = time.time()
    for i, q in enumerate(questions):
        prompt = format_prompt(q, tokenizer)
        scores = score_fn(prompt)
        pred = predict_from_scores(scores)
        is_correct = pred == q["correct_letter"]
        if is_correct:
            correct += 1
        details.append({
            "question_idx": i,
            "predicted": pred,
            "correct": q["correct_letter"],
            "is_correct": is_correct,
            "scores": scores,
        })
        if (i + 1) % 10 == 0:
            dt = time.time() - t0
            print(f"  {i+1}/{len(questions)}  acc={correct/(i+1):.3f}  {dt:.1f}s")
        if (i + 1) % 50 == 0:
            torch.cuda.empty_cache()
    return correct, len(questions), details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Cassi checkpoint to evaluate (omit for base-only)")
    parser.add_argument("--residual", action="store_true",
                        help="Use residual logit mode")
    parser.add_argument("--observer-bottleneck-dim", type=int, default=None,
                        help="Bottleneck dim before CordObserver field projection")
    parser.add_argument("--observer-low-rank", type=int, default=None,
                        help="Rank for low-rank CordObserver logit projection")
    parser.add_argument("--data", type=str, default="datasets/gpqa_main.csv")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N questions")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=1536,
                        help="Max token length per prompt (truncate from the left)")
    parser.add_argument("--base-results", type=str, default=None,
                        help="Load existing base results JSON instead of re-running base")
    parser.add_argument("--cassi-only", action="store_true",
                        help="Only run Cassi evaluation (requires --base-results)")
    parser.add_argument("--obs-boost", type=float, default=1.0,
                        help="Scale observer residual logits (diagnostic)")
    parser.add_argument("--spec-boost", type=float, default=1.0,
                        help="Scale specialist residual logits (diagnostic)")
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    questions = parse_gpqa(args.data)
    if args.limit:
        questions = questions[:args.limit]
    print(f"Loaded {len(questions)} GPQA questions from {args.data}")

    print("\nLoading base model...")
    base_model = load_base_model()
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)

    if args.cassi_only:
        if not args.base_results:
            raise ValueError("--cassi-only requires --base-results")
        with open(args.base_results) as f:
            base_data = json.load(f)
        c_base = int(round(base_data["base_accuracy"] * base_data["n_questions"]))
        n_base = base_data["n_questions"]
        acc_base = base_data["base_accuracy"]
        det_base = base_data.get("base_details", [])
        print(f"Loaded base results: {acc_base:.4f} ({c_base}/{n_base})")
    else:
        print("\n" + "=" * 70)
        print("BASE MODEL")
        print("=" * 70)
        c_base, n_base, det_base = evaluate(lambda p: score_base_logits(base_model, tokenizer, p, args.max_length), questions, tokenizer)
        acc_base = c_base / n_base
        print(f"Base accuracy: {c_base}/{n_base} = {acc_base:.4f}")
        out_path = "experiments/gpqa_eval_base_only.json"
        with open(out_path, "w") as f:
            json.dump({
                "n_questions": n_base,
                "base_accuracy": acc_base,
                "base_details": det_base,
            }, f, indent=2, default=str)
        print(f"Saved base-only results to {out_path}")

    if args.checkpoint:
        print("\n" + "=" * 70)
        print("CASSI AUGMENTED")
        print("=" * 70)
        torch.cuda.empty_cache()
        cassi = CassiAugmentedModel(base_model, residual=args.residual,
                                    observer_bottleneck_dim=args.observer_bottleneck_dim,
                                    observer_low_rank=args.observer_low_rank)
        print(f"Loading checkpoint: {args.checkpoint}")
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        if not any(k.startswith("observer.") for k in ckpt.keys()):
            ckpt = {f"observer.{k}": v for k, v in ckpt.items()}
        ckpt = {k: v for k, v in ckpt.items() if not k.startswith("base.")}
        missing, unexpected = cassi.load_state_dict(ckpt, strict=False)
        print(f"  Missing keys: {len(missing)}, Unexpected keys: {len(unexpected)}")
        cassi.eval()

        c_cassi, n_cassi, det_cassi = evaluate(
            lambda p: score_cassi_logits(cassi, tokenizer, p, args.max_length, args.obs_boost, args.spec_boost),
            questions, tokenizer
        )
        acc_cassi = c_cassi / n_cassi
        print(f"Cassi accuracy: {c_cassi}/{n_cassi} = {acc_cassi:.4f}")

        delta = (acc_cassi - acc_base) * 100
        print(f"\nDelta: {delta:+.2f} percentage points")

        out_path = "experiments/gpqa_eval_results.json"
        with open(out_path, "w") as f:
            json.dump({
                "checkpoint": args.checkpoint,
                "residual": args.residual,
                "n_questions": n_base,
                "base_accuracy": acc_base,
                "cassi_accuracy": acc_cassi,
                "delta_pp": delta,
                "base_details": det_base,
                "cassi_details": det_cassi,
            }, f, indent=2, default=str)
        print(f"Saved detailed results to {out_path}")


if __name__ == "__main__":
    main()
