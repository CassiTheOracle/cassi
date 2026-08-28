#!/usr/bin/env python3
"""Compare QiField generation with/without state reset between chunks."""
import math
import os
import sys

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cassi.qi_field import QiField


def tokens_to_text(tokens):
    """Best-effort decode: printable ASCII, else '.'."""
    chars = []
    for t in tokens:
        if 32 <= t < 127:
            chars.append(chr(t))
        elif t in (10, 13):
            chars.append(chr(t))
        else:
            chars.append('.')
    return ''.join(chars)


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'Device: {device}')

    model = QiField(N=128, d=128, K_train=10, K_gen=50).to(device)
    ckpt_path = 'checkpoints/N128_d128/qi_field_latest.pt'
    checkpoint_found = os.path.exists(ckpt_path)

    if checkpoint_found:
        print(f'Loading checkpoint: {ckpt_path}')
        state = torch.load(ckpt_path, map_location=device, weights_only=False)
        if isinstance(state, dict):
            if 'model_state_dict' in state:
                state = state['model_state_dict']
            elif 'model' in state:
                state = state['model']
        missing, unexpected = model.load_state_dict(state, strict=False)
        if missing:
            print(f'Missing keys: {missing}')
        if unexpected:
            print(f'Unexpected keys: {unexpected}')
    else:
        print('No trained checkpoint found; using fresh model.')

    model.eval()
    temp = 0.8
    seq_len = 512

    # Generate with state reset between chunks (default behavior).
    print('\n' + '=' * 60)
    print(f'Generating {seq_len} tokens with reset_between_chunks=True, temp={temp}')
    print('=' * 60)
    model.reset_state()
    with torch.no_grad():
        tokens_reset = model.generate(seq_len=seq_len, temp=temp, reset_between_chunks=True)
    text_reset = tokens_to_text(tokens_reset)
    print(text_reset)

    # Generate without state reset between chunks (persistent state).
    print('\n' + '=' * 60)
    print(f'Generating {seq_len} tokens with reset_between_chunks=False, temp={temp}')
    print('=' * 60)
    model.reset_state()
    with torch.no_grad():
        tokens_persist = model.generate(seq_len=seq_len, temp=temp, reset_between_chunks=False)
    text_persist = tokens_to_text(tokens_persist)
    print(text_persist)

    # Perplexity via held-out synthetic sequence (must match model.N).
    held_out = torch.randint(0, 256, (1, model.N), device=device)
    model.reset_state()
    with torch.no_grad():
        loss, info = model.training_loss(held_out)
    val_loss = loss.item()
    ppl = math.exp(val_loss)

    print('\n' + '=' * 60)
    print('Comparison')
    print('=' * 60)
    print(f'Checkpoint used       : {ckpt_path if checkpoint_found else "none (fresh model)"}')
    print(f'Held-out val loss     : {val_loss:.4f}')
    print(f'Held-out perplexity   : {ppl:.2f}')
    print(f'Reset sample length   : {len(tokens_reset)}')
    print(f'Persist sample length : {len(tokens_persist)}')
    print(f'Reset printable ratio : {sum(1 for c in text_reset if c.isprintable()) / len(text_reset):.3f}')
    print(f'Persist printable ratio: {sum(1 for c in text_persist if c.isprintable()) / len(text_persist):.3f}')
    print(f'Reset unique tokens   : {len(set(tokens_reset))}')
    print(f'Persist unique tokens : {len(set(tokens_persist))}')


if __name__ == '__main__':
    main()
