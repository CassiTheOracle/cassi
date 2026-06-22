"""DreamBank — Episodic replay memory for Qi-state-balanced training.

Stores high-salience training experiences in five Qi-element sub-banks
(water/wood/fire/earth/metal) and replays from under-represented states
to maintain chakra balance and prevent catastrophic forgetting of rare patterns.

Adapted from the legacy DreamBank (dream_bank.py) for the MuonCord architecture.
Stores raw byte sequences rather than full field state — cheap and sufficient.
"""

import torch
import torch.nn as nn

from cassi.cord import PHI



class DreamBankMuon(nn.Module):
    """Episodic replay memory with 5 Qi-element sub-banks.

    Stores raw byte sequences from training. Before the optimizer step,
    replays 1 experience from the most under-represented bank to maintain
    balanced exposure across Qi states.

    Args:
        N: Sequence length stored per experience.
        capacity_per_bank: Max experiences per sub-bank (default 100).
        replay_every: Replay frequency in batches (default 4).
        replay_weight: Weight of replay loss in total loss (default 0.1).
    """

    ELEMENTS = ['water', 'wood', 'fire', 'earth', 'metal']
    ELEMENT_IDX = {e: i for i, e in enumerate(ELEMENTS)}

    def __init__(self, N: int = 128, capacity_per_bank: int = 100,
                 replay_every: int = 4, replay_weight: float = 0.1):
        super().__init__()
        self.N = N
        self.replay_every = replay_every
        self.replay_weight = replay_weight

        # Persistent buffers — stored in state_dict
        for i, elem in enumerate(self.ELEMENTS):
            self.register_buffer(f'keys_{elem}',
                torch.zeros(capacity_per_bank, N, dtype=torch.long))
            self.register_buffer(f'qi_mean_{elem}',
                torch.zeros(capacity_per_bank))
            self.register_buffer(f'quality_{elem}',
                torch.zeros(capacity_per_bank))
            self.register_buffer(f'count_{elem}',
                torch.zeros(1, dtype=torch.long))

        self._batch_count = 0

    @staticmethod
    def classify_qi_element(qi_mean: float, qi_quality_mean: float) -> str:
        """Map (qi_mean, quality) → 5-element phase.

        Uses qi relative to φ baseline and quality to determine element.
        """
        qi_norm = qi_mean / (2.0 * PHI)  # [0, ~1]
        q = qi_quality_mean

        if q < 0.33:
            return 'water'   # low quality, any energy → depletion
        elif qi_norm < 0.33:
            return 'wood'    # low energy, moderate+ quality → dormant clarity
        elif qi_norm > 0.67:
            return 'earth' if q > 0.5 else 'fire'  # high energy
        else:
            return 'metal'   # balanced energy, moderate+ quality → ideal

    @torch.no_grad()
    def store(self, x: torch.Tensor, qi_mean: float, qi_quality_mean: float,
              loss: float):
        """Store a training experience in the appropriate sub-bank.

        Args:
            x: [N] byte tensor from current batch.
            qi_mean, qi_quality_mean: scalar Qi diagnostics.
            loss: CE loss for this batch.
        """
        element = self.classify_qi_element(qi_mean, qi_quality_mean)
        idx = self.ELEMENT_IDX[element]
        count = getattr(self, f'count_{element}')

        slot = int(count.item()) % self._capacity(element)
        getattr(self, f'keys_{element}')[slot] = x[:self.N].detach()
        getattr(self, f'qi_mean_{element}')[slot] = qi_mean
        getattr(self, f'quality_{element}')[slot] = qi_quality_mean
        count.add_(1)

    def _capacity(self, element: str) -> int:
        return getattr(self, f'keys_{element}').shape[0]

    def should_replay(self) -> bool:
        """Check if it's time to replay."""
        self._batch_count += 1
        return self._batch_count % self.replay_every == 0

    def sample_replay(self) -> tuple:
        """Sample from the most under-represented bank.

        Returns:
            (replay_x, element_name) or (None, None) if all banks empty.
            replay_x: [1, N] byte tensor.
        """
        counts = [(e, getattr(self, f'count_{e}').item()) for e in self.ELEMENTS]
        # Pick bank with fewest entries (but at least 1)
        eligible = [(e, c) for e, c in counts if c > 0]
        if not eligible:
            return None, None

        # Pick the most under-represented
        element, _ = min(eligible, key=lambda x: x[1])
        count = getattr(self, f'count_{element}').item()
        n_available = min(count, self._capacity(element))
        slot = torch.randint(0, n_available, (1,)).item()

        keys = getattr(self, f'keys_{element}')
        return keys[slot:slot + 1].clone(), element
