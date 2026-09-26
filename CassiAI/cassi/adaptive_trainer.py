"""AdaptiveTrainer — self-aware training driven by model signals.

The model's own internal state (surprise, harmony, consistency) drives:
  - Curriculum: high-surprise samples are "hard", sampled more often
  - LR scheduling: high surprise → explore (higher LR), low harmony → stabilize (lower LR)
  - Stopping: when surprise AND harmony plateau, training is done
  - Memory writing: only write to Berry memory when surprise is above threshold
"""

import torch
import torch.nn.functional as F
import numpy as np
from collections import deque


class AdaptiveTrainer:
    """Trainer that uses model internal signals to guide training."""

    def __init__(self, model, optimizer,
                 lr_base=2e-4, lr_min=1e-6, lr_max=1e-3,
                 curriculum_alpha=0.3,
                 stop_patience=10,
                 signal_window=20):
        self.model = model
        self.optimizer = optimizer
        self.lr_base = lr_base
        self.lr_min = lr_min
        self.lr_max = lr_max
        self.curriculum_alpha = curriculum_alpha
        self.stop_patience = stop_patience
        self.signal_window = signal_window

        # Signal history
        self.surprise_history = deque(maxlen=signal_window)
        self.harmony_history = deque(maxlen=signal_window)
        self.loss_history = deque(maxlen=signal_window)
        self.consistency_history = deque(maxlen=signal_window)

        # Curriculum: per-sample surprise scores for resampling
        from collections import OrderedDict
        self.sample_surprises = OrderedDict()  # idx -> surprise, bounded LRU

        # Adaptive LR state
        self.lr_current = lr_base
        self.lr_plateau_count = 0

        # Stopping state
        self.best_signal = None
        self.no_improve_count = 0

    def update_signals(self, info, loss):
        """Record model signals from a forward pass."""
        self.loss_history.append(loss)
        if 'surprise' in info:
            self.surprise_history.append(info['surprise'])
        if 'mean_harmony' in info:
            h = info['mean_harmony']
            if hasattr(h, 'item'):
                h = h.item() if h.numel() == 1 else h.mean().item()
            self.harmony_history.append(h)
        if 'consistency' in info:
            self.consistency_history.append(info['consistency'])

    def curriculum_weights(self, indices):
        """Compute sampling weights: higher surprise = more frequent."""
        if not self.sample_surprises or len(self.sample_surprises) < 100:
            return None  # Not enough data, uniform sampling

        weights = []
        for idx in indices:
            s = self.sample_surprises.get(int(idx), 1.0)
            weights.append(1.0 + self.curriculum_alpha * s)
        return np.array(weights, dtype=np.float64)

    def record_sample_surprise(self, indices, surprises, max_samples=50000):
        """Store per-sample surprise for curriculum."""
        for idx, s in zip(indices, surprises):
            self.sample_surprises[int(idx)] = float(s)
        # Trim oldest if too large
        while len(self.sample_surprises) > max_samples:
            self.sample_surprises.popitem(last=False)

    def adapt_lr(self):
        """Adjust learning rate based on surprise and harmony trends.

        High surprise + rising → model is learning, maintain or increase LR
        Low surprise + flat → model is stagnating, reduce LR
        Low harmony → specialists disagreeing, reduce LR to stabilize
        """
        if len(self.surprise_history) < 5 or len(self.harmony_history) < 5:
            return self.lr_current

        surprise_recent = np.mean(list(self.surprise_history)[-5:])
        surprise_old = np.mean(list(self.surprise_history)[:5]) if len(self.surprise_history) >= 10 else surprise_recent
        surprise_trend = surprise_recent - surprise_old

        harmony_recent = np.mean(list(self.harmony_history)[-5:])
        harmony_old = np.mean(list(self.harmony_history)[:5]) if len(self.harmony_history) >= 10 else harmony_recent
        harmony_trend = harmony_recent - harmony_old

        # Logic: want surprise to be moderate (not too low = bored, not too high = chaos)
        # Want harmony to be rising (specialists converging)
        if surprise_trend < -0.1 and harmony_trend < 0:
            # Both dropping: stagnation
            self.lr_current *= 0.7
            self.lr_plateau_count += 1
        elif surprise_trend > 0.1 and harmony_trend > 0:
            # Both rising: learning well
            self.lr_current *= 1.1
            self.lr_plateau_count = 0
        elif surprise_trend > 0.5:
            # Surprise spiking: chaos, reduce LR
            self.lr_current *= 0.5
            self.lr_plateau_count = 0
        else:
            self.lr_plateau_count += 1

        self.lr_current = np.clip(self.lr_current, self.lr_min, self.lr_max)

        # Apply to optimizer
        for g in self.optimizer.param_groups:
            g['lr'] = self.lr_current

        return self.lr_current

    def should_stop(self):
        """Dynamic stopping based on signal plateau.

        Stop when:
          - Loss hasn't improved for stop_patience evaluations
          - AND surprise has been flat (not changing much)
          - AND harmony has been flat or declining
        """
        if len(self.loss_history) < self.stop_patience:
            return False

        recent_losses = list(self.loss_history)[-self.stop_patience:]
        best_recent = min(recent_losses)
        worst_recent = max(recent_losses)

        # If loss is still improving significantly, don't stop
        if worst_recent - best_recent > 0.01 * best_recent:
            self.no_improve_count = 0
            return False

        self.no_improve_count += 1

        if self.no_improve_count < self.stop_patience:
            return False

        # Additional checks: require signal plateau too
        if len(self.surprise_history) >= 10:
            surprise_std = np.std(list(self.surprise_history)[-10:])
            if surprise_std > 0.5:
                return False  # Surprise still fluctuating, keep going

        if len(self.harmony_history) >= 10:
            harmony_trend = np.mean(list(self.harmony_history)[-5:]) - np.mean(list(self.harmony_history)[:5])
            if harmony_trend > 0.01:
                return False  # Harmony still rising, keep going

        return True

    def get_status(self):
        """Return current adaptive state for logging."""
        return {
            'lr': self.lr_current,
            'lr_plateau': self.lr_plateau_count,
            'surprise_mean': np.mean(self.surprise_history) if self.surprise_history else 0,
            'harmony_mean': np.mean(self.harmony_history) if self.harmony_history else 0,
            'no_improve': self.no_improve_count,
            'n_curriculum': len(self.sample_surprises),
        }
