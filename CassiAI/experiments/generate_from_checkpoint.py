import argparse
import os
import sys
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cassi.qi_field import QiField


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=str, required=True)
    parser.add_argument('--N', type=int, default=128)
    parser.add_argument('--d', type=int, default=128)
    parser.add_argument('--K-gen', type=int, default=50)
    parser.add_argument('--gen-len', type=int, default=256)
    parser.add_argument('--gen-temp', type=float, default=0.8)
    parser.add_argument('--gen-seeds', type=int, default=1)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        print('CUDA not available')
        return
    dev = 'cuda:0'  # with CUDA_VISIBLE_DEVICES=1, this maps to the dGPU

    model = QiField(N=args.N, d=args.d, C=13, V=256,
                    K_train=10, K_gen=args.K_gen,
                    self_aware=True, ctrl_hidden_dim=64).to(dev)

    ckpt = torch.load(args.checkpoint, map_location=dev, weights_only=True)
    model.load_state_dict(ckpt['model'])
    print(f'Loaded checkpoint from epoch {ckpt.get("epoch", "?")}')

    model.eval()
    for seed in range(args.gen_seeds):
        torch.manual_seed(42 + seed)
        tokens = model.generate(seq_len=args.gen_len, temp=args.gen_temp)
        text = ''.join(chr(t) if 32 <= t < 127 else '.' for t in tokens)
        print(f'--- sample {seed + 1} ---')
        print(text)
        print()


if __name__ == '__main__':
    main()
