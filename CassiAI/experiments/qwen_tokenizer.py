"""
Minimal Qwen3.5 tokenizer — loads from tokenizer.json without transformers.

Implements BPE tokenization with pretokenization regex matching Qwen2Tokenizer.
"""

import json
import regex as re
from typing import List, Union


class QwenTokenizer:
    """Minimal BPE tokenizer for Qwen3.5.

    Loads vocab and merge rules from tokenizer.json.
    """

    def __init__(self, tokenizer_path: str):
        with open(tokenizer_path) as f:
            data = json.load(f)

        self.model = data['model']
        self.vocab = self.model['vocab']
        self.merges = self.model.get('merges', [])

        # Build reverse vocab
        self.id_to_token = {v: k for k, v in self.vocab.items()}

        # Added special tokens
        self.added_tokens = {t['id']: t for t in data.get('added_tokens', [])}
        self.special_tokens = {t['content']: t['id'] for t in data.get('added_tokens', [])}

        # Pretokenization regex (from tokenizer_config.json)
        self.pretokenize_pattern = re.compile(
            r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|"
            r"[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|"
            r"\p{N}|"
            r" ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|"
            r"\s*[\r\n]+|"
            r"\s+(?!\S)|"
            r"\s+"
        )

        # For encode: build merge rank lookup
        self.merge_ranks = {}
        for i, merge in enumerate(self.merges):
            pair = tuple(merge.split())
            self.merge_ranks[pair] = i

        # Chat template tokens
        self.im_start = self.special_tokens.get('<|im_start|>', 248045)
        self.im_end = self.special_tokens.get('<|im_end|>', 248046)
        self.eos = self.special_tokens.get('<|endoftext|>', 248044)

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        """Encode text to token IDs using BPE with pretokenization.

        Args:
            text: input string
            add_special_tokens: if True, wrap with im_start/im_end
        Returns:
            list of token IDs
        """
        tokens = []

        # Split on special tokens first
        parts = self._split_special_tokens(text)

        for part_text, is_special in parts:
            if is_special:
                tokens.append(self.special_tokens.get(part_text, self.eos))
                continue

            # Pretokenize with regex
            words = self.pretokenize_pattern.findall(part_text)

            for word in words:
                word_tokens = self._bpe_encode_word(word)
                tokens.extend(word_tokens)

        if add_special_tokens:
            tokens = [self.im_start] + tokens + [self.im_end]

        return tokens

    def _split_special_tokens(self, text: str) -> List[tuple]:
        """Split text into (text, is_special) segments."""
        # Build pattern from special token contents
        special_contents = sorted(
            [re.escape(t['content']) for t in self.added_tokens.values()],
            key=len, reverse=True
        )
        if not special_contents:
            return [(text, False)]

        pattern = re.compile('(' + '|'.join(special_contents) + ')')
        parts = []
        last_end = 0
        for m in pattern.finditer(text):
            if m.start() > last_end:
                parts.append((text[last_end:m.start()], False))
            parts.append((m.group(1), True))
            last_end = m.end()
        if last_end < len(text):
            parts.append((text[last_end:], False))
        return parts

    def _bpe_encode_word(self, word: str) -> List[int]:
        """BPE encode a single pretokenized word.

        Qwen uses 'Ġ' (U+0120) to represent leading spaces in BPE.
        We convert leading spaces to Ġ before vocab lookup.
        """
        # Convert leading space to Ġ for BPE vocab lookup
        if word.startswith(' '):
            word = 'Ġ' + word[1:]

        word_tokens = []
        i = 0
        while i < len(word):
            # Greedy longest match
            best_id = None
            best_len = 0
            for length in range(min(32, len(word) - i), 0, -1):
                substr = word[i:i + length]
                if substr in self.vocab:
                    best_id = self.vocab[substr]
                    best_len = length
                    break
            if best_id is not None:
                word_tokens.append(best_id)
                i += best_len
            else:
                # Byte fallback
                b = word[i].encode('utf-8')[0]
                byte_token = f'<|byte_{b:02x}|>'
                word_tokens.append(self.vocab.get(byte_token, self.eos))
                i += 1
        return word_tokens

    def decode(self, token_ids: Union[List[int], 'torch.Tensor']) -> str:
        """Decode token IDs to text.

        Args:
            token_ids: list or tensor of token IDs
        Returns:
            decoded string
        """
        import torch
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()

        tokens = []
        for tid in token_ids:
            if tid in self.id_to_token:
                token = self.id_to_token[tid]
                # Handle byte fallback
                if token.startswith('<|byte_') and token.endswith('|>'):
                    hex_val = token[7:-2]
                    tokens.append(bytes.fromhex(hex_val).decode('utf-8', errors='replace'))
                else:
                    tokens.append(token)
            elif tid in self.added_tokens:
                tokens.append(self.added_tokens[tid]['content'])
            else:
                tokens.append(f'<|unk_{tid}|>')

        text = ''.join(tokens)
        # Convert Ġ back to space for readability
        text = text.replace('Ġ', ' ')
        return text

    def build_chat_prompt(self, messages: List[dict]) -> str:
        """Build a chat prompt from messages.

        Args:
            messages: list of {'role': 'user'|'assistant'|'system', 'content': str}
        Returns:
            formatted prompt string
        """
        parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            parts.append(f'<|im_start|>{role}\n{content}<|im_end|>')
        parts.append('<|im_start|>assistant\n')
        return '\n'.join(parts)

    def __len__(self):
        return len(self.vocab) + len(self.added_tokens)


def test_tokenizer():
    """Quick test of the tokenizer."""
    import torch

    tok = QwenTokenizer('C:/Users/Carina/workspaces/Cassi/CassiAI/qwen_models/Qwen3.5-0.8B/tokenizer.json')
    print(f"Vocab size: {len(tok)}")
    print(f"Special tokens: {list(tok.special_tokens.keys())[:5]}")

    # Test encode/decode roundtrip
    test_strings = [
        "Hello world",
        "The quick brown fox",
        "123 + 456 = 579",
        "Hello, world! How are you?",
    ]

    for text in test_strings:
        ids = tok.encode(text)
        decoded = tok.decode(ids)
        match = "✓" if decoded.strip() == text.strip() else "✗"
        print(f"\n{text!r}")
        print(f"  IDs: {ids[:10]}...")
        print(f"  Decoded: {decoded!r}")
        print(f"  Match: {match}")

    # Test chat prompt
    messages = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'What is the capital of France?'},
    ]
    prompt = tok.build_chat_prompt(messages)
    print(f"\nChat prompt:\n{prompt}")
    prompt_ids = tok.encode(prompt)
    print(f"Prompt IDs: {prompt_ids[:20]}...")


if __name__ == '__main__':
    test_tokenizer()
