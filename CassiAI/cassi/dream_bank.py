"""DreamBank — Episodic memory for surprise & disappointment replay.

Stores salient moments in five Qi-state sub-banks for later replay.
Inspired by hippocampal replay and meditation processing.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class DreamExperience:
    __slots__ = ['x', 'y', 'surprise', 'disappointment', 'qi_state',
                 'capture_qi_state', 'brain_state', 'compressed', 'pred',
                 'loss', 'modality', '_timestamp', '_replay_losses']

    def __init__(self, x, y, surprise, disappointment, qi_state,
                 capture_qi_state, brain_state, compressed, pred, loss,
                 modality='physics'):
        self.x = x.detach().cpu()
        self.y = y.detach().cpu()
        self.surprise = float(surprise)
        self.disappointment = float(disappointment)
        self.qi_state = qi_state
        self.capture_qi_state = capture_qi_state
        self.brain_state = brain_state.detach().cpu() if brain_state is not None else None
        self.compressed = compressed.detach().cpu() if compressed is not None else None
        self.pred = pred.detach().cpu()
        self.loss = float(loss)
        self.modality = modality
        self._timestamp = 0
        self._replay_losses = []

    @property
    def salience(self):
        return max(self.surprise, self.disappointment)


class QiSubBank:
    """A specialized bank for one Qi state."""

    SORT_KEYS = {
        'water': lambda e: e.disappointment,
        'wood': lambda e: e.surprise,
        'fire': lambda e: e.salience,
        'earth': lambda e: e.loss,
        'metal': lambda e: e._timestamp,
    }

    def __init__(self, state_name, capacity):
        self.state_name = state_name
        self.capacity = capacity
        self.experiences = []
        self._sort_key = self.SORT_KEYS[state_name]

    def insert(self, exp):
        import bisect
        key = self._sort_key(exp)
        # Insert in descending order (highest priority first).
        # bisect only supports ascending, so we negate keys.
        neg_keys = [-self._sort_key(e) for e in self.experiences]
        idx = bisect.bisect_left(neg_keys, -key, lo=0, hi=len(neg_keys))
        self.experiences.insert(idx, exp)
        if len(self.experiences) > self.capacity:
            self.experiences = self.experiences[:self.capacity]

    def sample(self, n, weights=None):
        if len(self.experiences) == 0:
            return []
        n = min(n, len(self.experiences))
        if weights is not None:
            probs = weights / weights.sum()
            indices = torch.multinomial(probs, n, replacement=False)
            return [self.experiences[i] for i in indices.tolist()]
        else:
            indices = torch.randperm(len(self.experiences))[:n]
            return [self.experiences[i] for i in indices.tolist()]

    def __len__(self):
        return len(self.experiences)


class DreamBank(nn.Module):
    """Episodic memory bank with Qi-native sub-banks and migration."""

    GENERATING_CYCLE = {
        'water': 'wood', 'wood': 'fire', 'fire': 'earth',
        'earth': 'metal', 'metal': 'water',
    }

    MIGRATION_RULES = {
        'water': {'replays_to_promote': 3, 'target': 'wood',
                  'condition': lambda exp, losses: len(losses) >= 3 and losses[-1] < losses[0] * 0.8},
        'wood': {'replays_to_promote': 2, 'target': 'fire',
                 'condition': lambda exp, losses: len(losses) >= 2 and max(losses) < exp.loss * 1.2},
        'fire': {'replays_to_promote': 2, 'target': 'earth',
                 'condition': lambda exp, losses: len(losses) >= 2 and (max(losses) - min(losses)) < 0.1},
        'earth': {'replays_to_promote': 2, 'target': 'metal',
                  'condition': lambda exp, losses: len(losses) >= 2},
        'metal': {'replays_to_promote': 1, 'target': None,
                  'condition': lambda exp, losses: len(losses) >= 1},
    }

    def __init__(self, capacity=1024, dream_ratio=0.5, meditate_ratio=0.3,
                 replay_batch_size=32, replay_lr_scale=0.3,
                 use_consolidation=False):
        super().__init__()
        self.capacity = capacity
        self.dream_ratio = dream_ratio
        self.meditate_ratio = meditate_ratio
        self.replay_batch_size = replay_batch_size
        self.replay_lr_scale = replay_lr_scale
        self.use_consolidation = use_consolidation

        per_bank = max(1, capacity // 5)
        self.banks = {
            state: QiSubBank(state, per_bank)
            for state in ['water', 'wood', 'fire', 'earth', 'metal']
        }
        self.capacity = per_bank * 5

        self._timestamp = 0
        self._replay_counter = 0
        self._active_qi_state = 'earth'

        self.register_buffer('_surprise_ema', torch.tensor(0.0))
        self.register_buffer('_disappointment_ema', torch.tensor(0.0))
        self.register_buffer('_loss_ema', torch.tensor(0.0))

    def set_qi_profile(self, profile):
        self._active_qi_state = profile.get('state', 'earth')

    def store(self, x, y, info, pred, loss, modality='physics'):
        surprise = info.get('surprise', 0.0)
        disappointment = info.get('disappointment', 0.0)
        if isinstance(surprise, torch.Tensor):
            surprise = surprise.item()
        if isinstance(disappointment, torch.Tensor):
            disappointment = disappointment.item()

        with torch.no_grad():
            self._surprise_ema = 0.95 * self._surprise_ema + 0.05 * abs(surprise)
            self._disappointment_ema = 0.95 * self._disappointment_ema + 0.05 * abs(disappointment)
            self._loss_ema = 0.95 * self._loss_ema + 0.05 * float(loss)

        surprise_thresh = self._surprise_ema.item() * 1.2 + 0.05
        disappointment_thresh = self._disappointment_ema.item() * 1.2 + 0.05
        loss_thresh = self._loss_ema.item() * 1.5

        if not (abs(surprise) > surprise_thresh or abs(disappointment) > disappointment_thresh or float(loss) > loss_thresh):
            return False

        capture_qi = info.get('qi_state', self._active_qi_state)
        if disappointment > self._disappointment_ema.item() * 2.0:
            target_bank = 'water'
        elif max(surprise, disappointment) > self._surprise_ema.item() * 3.0:
            target_bank = 'fire'
        else:
            target_bank = capture_qi

        exp = DreamExperience(
            x=x, y=y, surprise=surprise, disappointment=disappointment,
            qi_state=info.get('qi_state', 'earth'), capture_qi_state=capture_qi,
            brain_state=info.get('conscious', pred),
            compressed=info.get('compressed', None),
            pred=pred, loss=float(loss), modality=modality,
        )
        exp._timestamp = self._timestamp
        self._timestamp += 1
        self.banks[target_bank].insert(exp)
        return True

    @property
    def pressure(self):
        return {state: len(bank) / max(1, bank.capacity)
                for state, bank in self.banks.items()}

    def sample_for_replay(self, mode='dream'):
        if mode == 'dream':
            primary, secondary = 'wood', 'fire'
        elif mode == 'meditate':
            primary, secondary = 'water', 'earth'
        elif mode == 'rest':
            primary, secondary = 'earth', 'metal'
        else:
            primary, secondary = self._active_qi_state, 'earth'

        samples = self.banks[primary].sample(self.replay_batch_size)
        if len(samples) < self.replay_batch_size and len(self.banks[secondary]) > 0:
            samples += self.banks[secondary].sample(self.replay_batch_size - len(samples))

        if len(samples) == 0:
            return None, None

        if len(set(s.capture_qi_state for s in samples)) == 1:
            replay_state = self.GENERATING_CYCLE.get(samples[0].capture_qi_state, 'earth')
        else:
            replay_state = self._active_qi_state

        return samples, replay_state

    def replay_forward(self, model, samples, replay_state):
        device = next(model.parameters()).device
        modalities = set(s.modality for s in samples)

        if len(modalities) > 1:
            losses = []
            for mod in modalities:
                mod_samples = [s for s in samples if s.modality == mod]
                mod_xs = torch.cat([s.x.to(device) for s in mod_samples], dim=0)
                mod_ys = torch.cat([s.y.to(device) for s in mod_samples], dim=0)
                byte_mode = (mod != 'physics')
                model.reset_state(mod_xs.shape[0])
                pred, info = model(mod_xs, return_workspace=True, byte_mode=byte_mode,
                                   force_qi_state=replay_state)
                losses.append(F.mse_loss(pred, mod_ys))
            loss_pred = sum(losses) / len(losses)
        else:
            mod = samples[0].modality
            byte_mode = (mod != 'physics')
            xs = torch.cat([s.x.to(device) for s in samples], dim=0)
            ys = torch.cat([s.y.to(device) for s in samples], dim=0)
            model.reset_state(xs.shape[0])
            pred, info = model(xs, return_workspace=True, byte_mode=byte_mode,
                               force_qi_state=replay_state)
            loss_pred = F.mse_loss(pred, ys)

        loss = loss_pred
        if self.use_consolidation and 'conscious' in info:
            stored_brain = torch.cat([s.brain_state.to(device) for s in samples if s.brain_state is not None], dim=0)
            current_brain = info['conscious']
            if stored_brain.shape == current_brain.shape:
                loss = loss + 0.01 * F.mse_loss(current_brain, stored_brain)

        return loss, replay_state

    def apply_replay_step(self, optimizer, loss, replay_state, mp_trainer=None):
        from cassi.brainstem import Brainstem
        # Qi-aware LR scaling
        LR_FAST = {'water': 0.05, 'wood': 0.4, 'fire': 1.0, 'earth': 0.6, 'metal': 0.2}
        lr_multiplier = LR_FAST.get(replay_state, 0.6) / 0.6

        for param_group in optimizer.param_groups:
            original = param_group.get('_original_lr', param_group['lr'])
            if '_original_lr' not in param_group:
                param_group['_original_lr'] = original
            param_group['lr'] = original * lr_multiplier * self.replay_lr_scale

        if mp_trainer is not None and mp_trainer.enabled:
            mp_trainer.zero_grad()
            mp_trainer.backward(loss)
            mp_trainer.unscale()
            mp_trainer.step_optimizer(clip_grad=1.0)
            mp_trainer.update_scaler()
        else:
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(optimizer.param_groups[0]['params'], 1.0)
            optimizer.step()

        for param_group in optimizer.param_groups:
            if '_original_lr' in param_group:
                param_group['lr'] = param_group['_original_lr']

    def run_migration(self):
        """Move experiences between banks based on replay history."""
        for state, bank in list(self.banks.items()):
            rule = self.MIGRATION_RULES.get(state)
            if rule is None:
                continue
            to_move = []
            for exp in list(bank.experiences):
                if rule['condition'](exp, exp._replay_losses):
                    to_move.append((exp, rule['target']))
            for exp, target in to_move:
                bank.experiences.remove(exp)
                if target is not None:
                    exp._timestamp = self._timestamp
                    self._timestamp += 1
                    self.banks[target].insert(exp)
                exp._replay_losses = []

    def rebalance_capacity(self):
        total_filled = sum(len(b) for b in self.banks.values())
        if total_filled == 0:
            return
        fill_rates = {s: len(b) / max(1, total_filled) for s, b in self.banks.items()}
        for state, bank in self.banks.items():
            target = max(self.capacity * 0.1, self.capacity * fill_rates[state])
            bank.capacity = int(target)
            if len(bank.experiences) > bank.capacity:
                bank.experiences = bank.experiences[:bank.capacity]

    def choose_mode(self):
        cycle_pos = (self._replay_counter % 100) / 100.0
        if cycle_pos < self.dream_ratio:
            return 'dream'
        elif cycle_pos < self.dream_ratio + self.meditate_ratio:
            return 'meditate'
        else:
            return 'rest'

    def summary(self):
        totals = {state: len(bank) for state, bank in self.banks.items()}
        total = sum(totals.values())
        if total == 0:
            return "DreamBank: empty"
        parts = [f"{s}={totals[s]}" for s in ['water', 'wood', 'fire', 'earth', 'metal']]
        return f"DreamBank: {total}/{self.capacity} | {' '.join(parts)}"
