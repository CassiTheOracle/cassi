"""DreamBank — Episodic memory for surprise & disappointment replay.

Stores salient moments (high surprise or disappointment) from training
for later replay. Inspired by:
  - Hippocampal replay during sleep (consolidation of surprising events)
  - Meditation / processing of disappointment (restoration and learning)

Modes:
  dream     — replay high-surprise moments (consolidate unexpected events)
  meditate  — replay high-disappointment moments (process, find resolution)
  rest      — replay low-salience moments (generalize, prevent overfitting)

Each experience is a snapshot of the full cognitive state at a salient moment.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class DreamExperience:
    """A single salient moment captured during training.

    Attributes:
        x: input tensor [B, 4, 1024] or [B, 1024]
        y: target tensor [B, 1024]
        surprise: scalar surprise signal
        disappointment: scalar disappointment signal
        qi_state: str, Qi state name
        brain_state: [B, D_brain] brain field state snapshot
        compressed: [B, D_stem] brainstem compressed state
        pred: [B, 1024] prediction at the moment
        loss: scalar prediction loss
        modality: str ('physics', 'text', 'audio')
    """

    __slots__ = ['x', 'y', 'surprise', 'disappointment', 'qi_state',
                 'brain_state', 'compressed', 'pred', 'loss', 'modality',
                 '_timestamp']

    def __init__(self, x, y, surprise, disappointment, qi_state,
                 brain_state, compressed, pred, loss, modality='physics'):
        self.x = x.detach().cpu()
        self.y = y.detach().cpu()
        self.surprise = float(surprise)
        self.disappointment = float(disappointment)
        self.qi_state = qi_state
        self.brain_state = brain_state.detach().cpu() if brain_state is not None else None
        self.compressed = compressed.detach().cpu() if compressed is not None else None
        self.pred = pred.detach().cpu()
        self.loss = float(loss)
        self.modality = modality
        self._timestamp = 0  # set by DreamBank

    @property
    def salience(self):
        """Overall salience = max of surprise and disappointment."""
        return max(self.surprise, self.disappointment)


class DreamBank(nn.Module):
    """Episodic memory bank for salient training moments.

    Args:
        capacity: max number of experiences to store
        dream_ratio: fraction of replay steps dedicated to dreams
        meditate_ratio: fraction dedicated to meditation
        replay_batch_size: number of experiences per replay step
        replay_lr_scale: learning rate multiplier during replay (usually lower)
    """

    def __init__(self, capacity=1024, dream_ratio=0.5, meditate_ratio=0.3,
                 replay_batch_size=32, replay_lr_scale=0.3):
        super().__init__()
        self.capacity = capacity
        self.dream_ratio = dream_ratio
        self.meditate_ratio = meditate_ratio
        self.replay_batch_size = replay_batch_size
        self.replay_lr_scale = replay_lr_scale

        # Experience storage (not parameters, so we manage manually)
        self.experiences = []
        self._timestamp = 0
        self._replay_counter = 0

        # EMAs for adaptive sampling thresholds
        self.register_buffer('_surprise_ema', torch.tensor(0.0))
        self.register_buffer('_disappointment_ema', torch.tensor(0.0))
        self.register_buffer('_loss_ema', torch.tensor(0.0))

    def store(self, x, y, info, pred, loss, modality='physics'):
        """Potentially store a training moment if it's salient enough.

        Returns True if stored, False otherwise.
        """
        surprise = info.get('surprise', 0.0)
        disappointment = info.get('disappointment', 0.0)

        # Handle tensor values
        if isinstance(surprise, torch.Tensor):
            surprise = surprise.item()
        if isinstance(disappointment, torch.Tensor):
            disappointment = disappointment.item()

        # Update EMAs
        with torch.no_grad():
            self._surprise_ema = 0.95 * self._surprise_ema + 0.05 * abs(surprise)
            self._disappointment_ema = 0.95 * self._disappointment_ema + 0.05 * abs(disappointment)
            self._loss_ema = 0.95 * self._loss_ema + 0.05 * float(loss)

        # Adaptive thresholds: store if significantly above recent average
        surprise_thresh = self._surprise_ema.item() * 1.2 + 0.05
        disappointment_thresh = self._disappointment_ema.item() * 1.2 + 0.05
        loss_thresh = self._loss_ema.item() * 1.5

        is_surprising = abs(surprise) > surprise_thresh
        is_disappointing = abs(disappointment) > disappointment_thresh
        is_high_loss = float(loss) > loss_thresh

        if not (is_surprising or is_disappointing or is_high_loss):
            return False

        exp = DreamExperience(
            x=x, y=y,
            surprise=surprise,
            disappointment=disappointment,
            qi_state=info.get('qi_state', 'earth'),
            brain_state=info.get('conscious', pred),  # fallback to pred if no conscious
            compressed=info.get('compressed', None),
            pred=pred,
            loss=float(loss),
            modality=modality,
        )
        exp._timestamp = self._timestamp
        self._timestamp += 1

        # Insert maintaining sort by salience (highest first)
        salience = exp.salience
        inserted = False
        for i, existing in enumerate(self.experiences):
            if salience > existing.salience:
                self.experiences.insert(i, exp)
                inserted = True
                break
        if not inserted:
            self.experiences.append(exp)

        # Trim to capacity
        if len(self.experiences) > self.capacity:
            self.experiences = self.experiences[:self.capacity]

        return True

    def sample(self, mode='dream', n=None):
        """Sample experiences for replay.

        Args:
            mode: 'dream' (high surprise), 'meditate' (high disappointment),
                  'rest' (low salience), or 'mixed'
            n: number of experiences to sample (default replay_batch_size)

        Returns:
            list of DreamExperience objects
        """
        if n is None:
            n = self.replay_batch_size
        if len(self.experiences) == 0:
            return []

        if mode == 'dream':
            # Weight by surprise
            weights = torch.tensor([e.surprise for e in self.experiences])
        elif mode == 'meditate':
            # Weight by disappointment
            weights = torch.tensor([e.disappointment for e in self.experiences])
        elif mode == 'rest':
            # Weight by inverse salience (practice on easy moments)
            weights = torch.tensor([1.0 / (1.0 + e.salience) for e in self.experiences])
        else:  # mixed
            weights = torch.ones(len(self.experiences))

        weights = weights.clamp(min=1e-8)
        probs = weights / weights.sum()

        n = min(n, len(self.experiences))
        indices = torch.multinomial(probs, n, replacement=False)
        return [self.experiences[i] for i in indices.tolist()]

    def replay_step(self, model, optimizer, mode='dream'):
        """Perform one replay step on sampled experiences.

        Returns:
            dict with 'loss', 'mode', 'n_samples'
        """
        samples = self.sample(mode)
        if len(samples) == 0:
            return {'loss': 0.0, 'mode': mode, 'n_samples': 0}

        device = next(model.parameters()).device

        # Batch the samples
        xs = torch.cat([s.x.to(device) for s in samples], dim=0)
        ys = torch.cat([s.y.to(device) for s in samples], dim=0)

        # Forward pass
        model.train()
        pred, info = model(xs, return_workspace=True, byte_mode=False)

        # Reconstruction loss: match original prediction + target
        loss_pred = F.mse_loss(pred, ys)

        # Consolidation loss: encourage similar brain state to stored snapshot
        # (helps stabilize representations for salient moments)
        loss_consolidation = 0.0
        if 'conscious' in info:
            stored_brain = torch.cat([s.brain_state.to(device) for s in samples], dim=0)
            current_brain = info['conscious']
            if stored_brain.shape == current_brain.shape:
                loss_consolidation = 0.01 * F.mse_loss(current_brain, stored_brain)

        loss = loss_pred + loss_consolidation

        # Scale LR for replay (gentler learning)
        for param_group in optimizer.param_groups:
            original_lr = param_group.get('_original_lr', param_group['lr'])
            if '_original_lr' not in param_group:
                param_group['_original_lr'] = original_lr
            param_group['lr'] = original_lr * self.replay_lr_scale

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # Restore LR
        for param_group in optimizer.param_groups:
            if '_original_lr' in param_group:
                param_group['lr'] = param_group['_original_lr']

        self._replay_counter += 1

        return {
            'loss': loss.item(),
            'mode': mode,
            'n_samples': len(samples),
        }

    def choose_mode(self):
        """Auto-select replay mode based on bank composition."""
        if len(self.experiences) == 0:
            return 'mixed'

        total_surprise = sum(e.surprise for e in self.experiences)
        total_disappointment = sum(e.disappointment for e in self.experiences)

        # Cycle through modes based on ratios
        cycle_pos = (self._replay_counter % 100) / 100.0
        if cycle_pos < self.dream_ratio:
            return 'dream'
        elif cycle_pos < self.dream_ratio + self.meditate_ratio:
            return 'meditate'
        else:
            return 'rest'

    def summary(self):
        """Return a text summary of the DreamBank contents."""
        if len(self.experiences) == 0:
            return "DreamBank: empty"

        n_dream = sum(1 for e in self.experiences if e.surprise > e.disappointment)
        n_meditate = sum(1 for e in self.experiences if e.disappointment >= e.surprise)
        avg_surprise = sum(e.surprise for e in self.experiences) / len(self.experiences)
        avg_disappointment = sum(e.disappointment for e in self.experiences) / len(self.experiences)
        avg_loss = sum(e.loss for e in self.experiences) / len(self.experiences)

        return (
            f"DreamBank: {len(self.experiences)}/{self.capacity} | "
            f"dreams={n_dream} meditate={n_meditate} | "
            f"avg_surprise={avg_surprise:.3f} "
            f"avg_disappointment={avg_disappointment:.3f} "
            f"avg_loss={avg_loss:.4f}"
        )
