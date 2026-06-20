# Qi-Native Cognition: Implementation Plan (Revised)

> Revised after critical review. Reduced from 9 phases to 7. Cut overcomplicated features.
> Added stability guards, inter-bank migration, and observability.

## Implementation Status

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| Phase 0: Stability Guard | ✅ COMPLETE | — | In `CassiBrain`: conscious clamp, sigmoid readout_scale, grad norm monitoring |
| Phase 1: QiCycle Conductor | ✅ COMPLETE | — | `QiCycle` class with hysteresis + broadcast |
| Phase 2: Qi-Aware Brainstem | ✅ COMPLETE | — | `Brainstem` with Qi state machine + neuroplasticizer |
| Phase 3: Five Sub-Banks | ✅ COMPLETE | — | `DreamBank` with Water/Wood/Fire/Earth/Metal sub-banks |
| Phase 4: Qi-Matched Replay | ✅ COMPLETE | — | `apply_replay_step` with Qi-state filtering |
| Phase 5: Berry Memory Qi-Keying | ✅ COMPLETE | 2026-06-07 | `qi_embed` + Qi state in Berry key. **But**: key is dynamic huge dim (~3384), not the planned 52. Value is `D_brain` (~3365), not 39. |
| Phase 6: Qi-Aware Subsystems | ✅ COMPLETE | 2026-06-07 | Changepoint, SoulVector, Breath all Qi-aware |
| Phase 7: Observability & Integration | ✅ COMPLETE | 2026-06-07 | `CassiMetrics` + `dashboard.py` integrated into training loop |

### Critical Gap: Architecture Branch Split

**All phases are implemented in `CassiBrain`/`DualCassi` (the active training architecture).** However, the φ-alignment features from `IMPLEMENTATION_PLAN.md` (P0–P2) were implemented in `HarmonyBrain`/`PhiGardenBrain` (legacy) and **never ported** to `CassiBrain`.

| Feature | HarmonyBrain (legacy) | CassiBrain (active) |
|---------|:---------------------:|:-------------------:|
| P0.1 Yang-dominant workspace | ✅ | ❌ |
| P0.2 Consciousness as cooperation | ✅ | ❌ |
| P0.3 Qi-fluid persistence | ✅ | N/A |
| P1.1 Meta-cord self-loop | ✅ | ❌ |
| P1.3 Conscious Berry keys | ✅ | ❌ |
| P2.1 φ-spaced LR groups | ❌ | ❌ |
| P2.2 Conscious spectral loss | ❌ | ❌ |

**Next priority:** Port P0–P2 into `CassiBrain` so the actively trained architecture is φ-aligned.

---

## Phase 0: Stability Guard

**Goal:** Fix the `conscious_norm` growth and NaN tendency before adding Qi complexity.

### Why this is Phase 0
The training run showed `conscious_norm` growing from 1.9 → 4.3 in 15 epochs. The previous run NaN'd at epoch 54 after similar growth. Adding 7 phases of Qi modulation on top of an unstable base is building on sand.

### What to build

#### 0.1 `conscious_norm` clamp in `CassiBrain.forward()`

```python
# After brain_state is computed:
brain_norm = brain_state.norm(dim=-1, keepdim=True)
if brain_norm.max() > 10.0:
    # Soft clamp: allow growth up to 10, then compress logarithmically
    scale = 10.0 / (brain_norm.clamp(min=10.0))
    brain_state = brain_state * scale
    info['conscious_clamped'] = True
```

This is a soft clamp, not a hard cutoff — it preserves gradients but prevents runaway growth.

#### 0.2 Gradient norm monitoring in training loop

```python
# After loss.backward() in train_multimodal.py:
total_grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
if total_grad_norm > 0.9:
    log_print(f"  WARNING: grad_norm={total_grad_norm:.2f} near clip threshold")
if not torch.isfinite(total_grad_norm):
    log_print("  WARNING: non-finite grad_norm, skipping step")
    opt.zero_grad()
    continue
```

#### 0.3 Brain readout normalization

```python
# In CassiBrain.__init__, replace readout:
self.readout = nn.Sequential(
    nn.LayerNorm(self.D_brain),
    nn.Linear(self.D_brain, 1024),
)
# Add a learned scale that starts small:
self.readout_scale = nn.Parameter(torch.zeros(1))
```

In forward:
```python
pred_brain = self.readout(brain_state)
scale = torch.nn.functional.sigmoid(self.readout_scale)  # bounded [0,1]
pred = pred_spine + scale * pred_brain
```

Replace `softplus(brain_scale) * 0.1` with `sigmoid(readout_scale)` — sigmoid is naturally bounded and avoids the tiny-brain-scale problem (currently ~1e-5).

### Testing
- Run 10-epoch mini-training, verify `conscious_norm` stays < 5.0
- Verify no NaN in any epoch
- Verify validation MAE is stable (no sudden spikes)

### Deliverable
- `conscious_norm` soft clamp in `CassiBrain.forward()`
- Gradient norm monitoring in `train_multimodal.py`
- Sigmoid-bounded `readout_scale` replacing `softplus(brain_scale)`

---

## Phase 1: QiCycle Conductor

**Goal:** Centralized Qi state with hysteresis, pulse integration, and broadcast to subscribers.

### 1.1 `QiCycle` class

```python
class QiCycle:
    STATES = ['water', 'wood', 'fire', 'earth', 'metal']
    
    def __init__(self, brainstem_qi, hysteresis=3):
        self.state = 'earth'
        self._pending_state = 'earth'
        self._pending_count = 0
        self._hysteresis = hysteresis
        self._history = deque(maxlen=100)
        self._subscribers = []
        self._brainstem_qi = brainstem_qi
        
    def subscribe(self, obj):
        if hasattr(obj, 'set_qi_profile'):
            self._subscribers.append(obj)
        
    def step(self, yang_norm, yin_norm, qi_energy, breath,
             dream_bank_pressure=None, changepoint_confidence=0.0):
        dream_bank_pressure = dream_bank_pressure or {}
        
        new_state = self._brainstem_qi.compute(yang_norm, yin_norm, qi_energy, breath)
        
        # System overrides
        if dream_bank_pressure.get('water', 0) > 0.5:
            new_state = 'water'
        elif changepoint_confidence > 0.8 and new_state == 'fire':
            new_state = 'metal'
        elif dream_bank_pressure.get('metal', 0) > 0.8:
            new_state = 'metal'
            
        # Hysteresis: require N consecutive diagnoses before transitioning
        if new_state == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = new_state
            self._pending_count = 1
            
        if self._pending_count >= self._hysteresis and new_state != self.state:
            self._transition(self.state, new_state)
            
        self._history.append(self.state)
        return self.state
        
    def _transition(self, old, new):
        self.state = new_state
        profile = self._brainstem_qi.get_profile(new)
        for sub in self._subscribers:
            sub.set_qi_profile(profile)
            
    @property
    def profile(self):
        return self._brainstem_qi.get_profile(self.state)
```

**Key changes from original plan:**
- **Hysteresis:** Requires 3 consecutive diagnoses before transitioning. Prevents state flicker.
- **`set_qi_profile()` instead of `on_qi_transition()`:** Simpler API — subscribers receive the full profile dict, not just state names.
- **Pulse integration:** `changepoint_confidence` replaces raw bool. Only forces Metal on high-confidence changepoints.

### 1.2 Integration into `CassiBrain`

```python
self.qi_cycle = QiCycle(brainstem_qi=self.brainstem.qi, hysteresis=3)
```

### Testing
- Vary inputs rapidly → verify state doesn't flicker (hysteresis holds)
- Hold input steady in one regime → verify transition happens after 3 steps
- Verify all subscribers receive `set_qi_profile()`

### Deliverable
- `cassi/qi_cycle.py` with `QiCycle`
- Hysteresis-based transitions
- Pulse detector integrated as confidence-weighted override

---

## Phase 2: Qi-Aware Brainstem and DreamBank

**Goal:** Brainstem receives state from QiCycle. DreamBank stores Qi-tagged experiences.

### 2.1 Brainstem refactoring

```python
def step(self, spine, qi_state=None):
    # ... breath, EMAs ...
    
    if qi_state is None:
        state_name = self.qi.compute(yang_norm, yin_norm, qi_energy, breath)
    else:
        state_name = qi_state
        
    profile = self.qi.get_profile(state_name)
    
    # ... modulation computation ...
    
    return {
        'compressed': compressed,
        'state': state_name,
        'profile': profile,
        # ... rest ...
    }
```

**No QiAware mixin for Brainstem.** It receives `qi_state` via argument, not callback. Simpler.

### 2.2 DreamBank Qi tagging

```python
class DreamExperience:
    __slots__ = ['x', 'y', 'surprise', 'disappointment', 'qi_state',
                 'capture_qi_state', 'brain_state', 'compressed', 'pred',
                 'loss', 'modality', '_timestamp']
    
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
```

### 2.3 DreamBank `pressure` metric

```python
@property
def pressure(self):
    """Return dict of per-bank fill ratios."""
    if len(self.experiences) == 0:
        return {}
    counts = {}
    for e in self.experiences:
        counts[e.capture_qi_state] = counts.get(e.capture_qi_state, 0) + 1
    fair_share = self.capacity / 5.0
    return {state: min(1.0, counts.get(state, 0) / fair_share)
            for state in ['water', 'wood', 'fire', 'earth', 'metal']}
```

### Testing
- Brainstem receives `qi_state='fire'` → verify `stem_info['profile']['lr_fast'] == 1.0`
- DreamBank stores experience in Fire state → verify `capture_qi_state == 'fire'`
- Verify `pressure` returns accurate fill ratios

### Deliverable
- `Brainstem.step()` accepts `qi_state` argument
- `DreamExperience` has `capture_qi_state`
- `DreamBank.pressure` property

---

## Phase 3: Five Sub-Banks with Migration

**Goal:** Split DreamBank into five sub-banks with automatic inter-bank migration.

### 3.1 `QiSubBank` — parameterized, not five separate classes

```python
class QiSubBank:
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
        key = self._sort_key(exp)
        for i, existing in enumerate(self.experiences):
            if key > self._sort_key(existing):
                self.experiences.insert(i, exp)
                break
        else:
            self.experiences.append(exp)
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
        indices = torch.randperm(len(self.experiences))[:n]
        return [self.experiences[i] for i in indices.tolist()]
```

### 3.2 Sub-bank structure with dynamic capacity rebalancing

```python
def __init__(self, capacity=1024, ...):
    per_bank = max(1, capacity // 5)
    self.banks = {state: QiSubBank(state, per_bank)
                  for state in ['water', 'wood', 'fire', 'earth', 'metal']}
    self.capacity = per_bank * 5
    self._rebalance_counter = 0
```

### 3.3 Inter-bank migration

Add `migrate()` method called during Metal-state replay:

```python
MIGRATION_RULES = {
    # After N replays in a bank, promote/demote
    'water': {'replays_to_promote': 3, 'target': 'wood',
              'condition': lambda exp, losses: losses[-1] < losses[0] * 0.8},
    'wood': {'replays_to_promote': 2, 'target': 'fire',
             'condition': lambda exp, losses: max(losses) < exp.loss * 1.2},
    'fire': {'replays_to_promote': 2, 'target': 'earth',
             'condition': lambda exp, losses: np.std(losses) < 0.1},
    'earth': {'replays_to_promote': 2, 'target': 'metal',
              'condition': lambda exp, losses: True},
    'metal': {'replays_to_promote': 1, 'target': None,  # purified
              'condition': lambda exp, losses: True},
}

def migrate(self, exp, source_bank, replay_losses):
    """Move experience between banks based on replay history."""
    rule = self.MIGRATION_RULES.get(source_bank)
    if rule is None:
        return
        
    if (len(replay_losses) >= rule['replays_to_promote'] and
        rule['condition'](exp, replay_losses)):
        
        target = rule['target']
        if target is None:
            # Purified: move to Berry Memory or delete
            self._on_purified(exp)
        else:
            self.banks[source_bank].experiences.remove(exp)
            exp._timestamp = self._timestamp
            self._timestamp += 1
            self.banks[target].insert(exp)
```

### 3.4 Dynamic capacity rebalancing

```python
def rebalance_capacity(self):
    """Redistribute capacity based on actual fill rates."""
    total_filled = sum(len(b) for b in self.banks.values())
    if total_filled == 0:
        return
        
    # Give more capacity to heavily used banks
    fill_rates = {s: len(b) / max(1, total_filled) for s, b in self.banks.items()}
    for state, bank in self.banks.items():
        # Target: proportional to fill rate, minimum 10% of total
        target = max(self.capacity * 0.1, self.capacity * fill_rates[state])
        bank.capacity = int(target)
        if len(bank.experiences) > bank.capacity:
            bank.experiences = bank.experiences[:bank.capacity]
```

Called once per epoch during Metal state.

### 3.5 Qi-routed storage

```python
def store(self, x, y, info, pred, loss, modality='physics'):
    # ... EMA updates ...
    capture_qi = info.get('qi_state', 'earth')
    
    # Routing overrides
    if disappointment > self._disappointment_ema.item() * 2.0:
        target_bank = 'water'
    elif salience > self._surprise_ema.item() * 3.0:
        target_bank = 'fire'
    else:
        target_bank = capture_qi
        
    exp = DreamExperience(..., capture_qi_state=capture_qi)
    exp._timestamp = self._timestamp
    self._timestamp += 1
    self.banks[target_bank].insert(exp)
    return True
```

### Testing
- Store 50 experiences → verify correct bank routing
- Simulate 3 Water replays with improving loss → verify migration to Wood
- Verify dynamic rebalancing increases capacity for heavily used banks
- Verify purified experiences trigger `_on_purified()` callback

### Deliverable
- `QiSubBank` parameterized class
- 5 sub-banks with dynamic capacity
- Inter-bank migration rules
- `_on_purified()` hook for Berry Memory handoff

---

## Phase 4: Qi-Matched Replay

**Goal:** Replay experiences through the generating cycle with Qi-profiled modulation. Generating cycle only.

### 4.1 Generating cycle only

```python
GENERATING_CYCLE = {
    'water': 'wood',
    'wood': 'fire',
    'fire': 'earth',
    'earth': 'metal',
    'metal': 'water',
}
```

**Controlling cycle removed.** One cycle reduces cognitive load.

### 4.2 Split `replay_step()` into focused functions

```python
def sample_for_replay(self, mode='dream'):
    """Sample experiences and determine target replay Qi state."""
    if mode == 'dream':
        primary, secondary = 'wood', 'fire'
    elif mode == 'meditate':
        primary, secondary = 'water', 'earth'
    elif mode == 'rest':
        primary, secondary = 'earth', 'metal'
    else:
        primary = self._active_qi_state
        secondary = 'earth'
        
    samples = self.banks[primary].sample(self.replay_batch_size)
    if len(samples) < self.replay_batch_size:
        samples += self.banks[secondary].sample(
            self.replay_batch_size - len(samples))
            
    if len(samples) == 0:
        return None, None
        
    # Determine replay Qi state
    if len(set(s.capture_qi_state for s in samples)) == 1:
        replay_state = self.GENERATING_CYCLE.get(samples[0].capture_qi_state, 'earth')
    else:
        replay_state = self._active_qi_state
        
    return samples, replay_state

def replay_forward(self, model, samples, replay_state):
    """Forward pass with forced Qi state. Returns loss."""
    device = next(model.parameters()).device
    xs = torch.cat([s.x.to(device) for s in samples], dim=0)
    ys = torch.cat([s.y.to(device) for s in samples], dim=0)
    
    # Handle mixed modality
    modalities = set(s.modality for s in samples)
    if len(modalities) > 1:
        # Group by modality, replay each group separately
        losses = []
        for mod in modalities:
            mod_samples = [s for s in samples if s.modality == mod]
            mod_xs = torch.cat([s.x.to(device) for s in mod_samples], dim=0)
            mod_ys = torch.cat([s.y.to(device) for s in mod_samples], dim=0)
            byte_mode = (mod != 'physics')
            pred, _ = model(mod_xs, return_workspace=True, byte_mode=byte_mode,
                           force_qi_state=replay_state)
            losses.append(F.mse_loss(pred, mod_ys))
        loss_pred = sum(losses) / len(losses)
    else:
        mod = samples[0].modality
        byte_mode = (mod != 'physics')
        pred, _ = model(xs, return_workspace=True, byte_mode=byte_mode,
                       force_qi_state=replay_state)
        loss_pred = F.mse_loss(pred, ys)
        
    return loss_pred, replay_state

def apply_replay_step(self, optimizer, loss, replay_state):
    """Backward pass with Qi-profiled LR."""
    profile = self._get_profile(replay_state)
    lr_multiplier = profile['lr_fast'] / 0.6
    
    for param_group in optimizer.param_groups:
        original = param_group.get('_original_lr', param_group['lr'])
        if '_original_lr' not in param_group:
            param_group['_original_lr'] = original
        param_group['lr'] = original * lr_multiplier * self.replay_lr_scale
        
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(self._model_params(), 1.0)
    optimizer.step()
    
    for param_group in optimizer.param_groups:
        if '_original_lr' in param_group:
            param_group['lr'] = param_group['_original_lr']
```

### 4.3 Optional consolidation loss

```python
def replay_forward(self, model, samples, replay_state, use_consolidation=False):
    # ... existing forward ...
    
    loss = loss_pred
    if use_consolidation and 'conscious' in info:
        stored_brain = torch.cat([s.brain_state.to(device) for s in samples], dim=0)
        current_brain = info['conscious']
        if stored_brain.shape == current_brain.shape:
            loss = loss + 0.01 * F.mse_loss(current_brain, stored_brain)
            
    return loss, replay_state
```

Default `use_consolidation=False`. Enable only after A/B testing shows benefit.

### 4.4 Private forward with forced Qi

```python
class CassiBrain:
    def forward(self, x, byte_mode=None, return_info=False, return_workspace=False, **kwargs):
        return self._forward_impl(x, byte_mode, return_info, return_workspace, **kwargs)
        
    def _forward_impl(self, x, byte_mode=None, return_info=False, return_workspace=False,
                      force_qi_state=None, **kwargs):
        # ... existing implementation ...
        if force_qi_state is not None:
            qi_state = force_qi_state
        else:
            qi_state = self.qi_cycle.step(...)
        # ... rest unchanged ...
```

Public API unchanged. `force_qi_state` is internal-only.

### 4.5 Breath-synchronized replay scheduling

```python
class DreamBank:
    def choose_mode(self):
        cycle_pos = (self._replay_counter % 100) / 100.0
        if cycle_pos < self.dream_ratio:
            return 'dream'
        elif cycle_pos < self.dream_ratio + self.meditate_ratio:
            return 'meditate'
        else:
            return 'rest'
            
    def should_replay_now(self, breath):
        """Gate replay by breath phase.
        
        Yang inhale → surprise replay (dream)
        Yin exhale → disappointment replay (meditate)
        """
        if breath.get('phase', 'yang') == 'yang':
            return 'dream' if self.banks['wood'].experiences else 'rest'
        else:
            return 'meditate' if self.banks['water'].experiences else 'rest'
```

### Testing
- Fire-captured experience → verify replay_state='earth' (generating cycle)
- Mixed-modality batch → verify separate forward passes per modality
- Verify `use_consolidation=False` by default
- Verify public `forward()` signature unchanged

### Deliverable
- `sample_for_replay()`, `replay_forward()`, `apply_replay_step()`
- Mixed-modality handling
- Optional consolidation loss (default off)
- Private `_forward_impl()` with forced Qi
- Breath-synchronized mode selection

---

## Phase 5: Berry Memory Qi-Keying

**Goal:** Add Qi context to Berry Memory keys. Cut per-slot tracking.

### 5.1 Learned Qi embedding

```python
class CassiBrain:
    def __init__(self, ...):
        # ... existing init ...
        self.qi_embed = nn.Embedding(5, 4)
        nn.init.xavier_uniform_(self.qi_embed.weight)
        # Warm-start: Water(0) and Metal(4) closer, Fire(2) and Wood(1) closer
        with torch.no_grad():
            self.qi_embed.weight[0] = torch.tensor([0.5, 0.5, -0.5, -0.5])   # water
            self.qi_embed.weight[1] = torch.tensor([0.5, -0.5, 0.5, -0.5])   # wood
            self.qi_embed.weight[2] = torch.tensor([-0.5, 0.5, 0.5, -0.5])  # fire
            self.qi_embed.weight[3] = torch.tensor([0.0, 0.0, 0.0, 0.0])    # earth
            self.qi_embed.weight[4] = torch.tensor([0.5, 0.5, 0.5, 0.5])    # metal

        key_dim = 13 + self.D_stem + self.D_brain + 2 + 4
        self.berry_memory = BerryMemory(key_dim=key_dim, value_dim=self.D_brain, n_slots=4096)
```

### 5.2 Key construction

```python
qi_idx = torch.tensor([self.qi_index.get(stem_info['state'], 3)], device=device)
qi_vec = self.qi_embed(qi_idx).expand(B, -1)

key = torch.cat([
    self.spine.field_energy,
    compressed,
    brain_state,
    breath_vec,
    qi_vec,
], dim=-1)
```

### 5.3 Qi-gated writes

```python
if stem_info['state'] in {'earth', 'metal'} and self.training:
    with torch.no_grad():
        value = brain_state.mean(dim=0, keepdim=True)
        self.berry_memory.write(key[0:1], value, mode='ema')
```

### 5.4 Per-slot Qi tracking — CUT

**Removed from plan.** The learned embedding achieves 90% of the benefit. Per-slot tracking adds O(n_slots) overhead for marginal gain. Revisit only if A/B testing shows embedding underperforms.

### 5.5 Checkpoint migration strategy

Old checkpoints have `berry_memory.keys` with shape `[4096, 2339]`. New shape is `[4096, 2343]`.

```python
def load_state_dict(self, state_dict, strict=True):
    # ... existing filtering ...
    # Handle BerryMemory key dimension mismatch
    if 'berry_memory.keys' in state_dict:
        old_keys = state_dict['berry_memory.keys']
        new_keys = self.state_dict()['berry_memory.keys']
        if old_keys.shape != new_keys.shape:
            print(f"[CassiBrain] BerryMemory key dim changed: {old_keys.shape} -> {new_keys.shape}")
            print("[CassiBrain] BerryMemory will be reinitialized. Old memories lost.")
            del state_dict['berry_memory.keys']
            del state_dict['berry_memory.values']
            del state_dict['berry_memory.n_filled']
    return super().load_state_dict(state_dict, strict=False)
```

Explicit warning, not silent data loss.

### Testing
- Verify `qi_embed` produces different vectors for different states
- Verify memories written in Earth are retrievable
- Verify Fire-written memories are NOT written (gated)
- Load old checkpoint → verify explicit warning about BerryMemory reinit
- Verify `berry_hit_rate` changes with Qi state

### Deliverable
- `qi_embed` with warm-start initialization
- Qi-gated writes (Earth/Metal only)
- Explicit checkpoint migration warning
- No per-slot Qi tracking

---

## Phase 6: Qi-Aware Subsystems

**Goal:** Make BrainField, Changepoint, Soul, Spine, Fast Weights, and Loss Weights all Qi-responsive. Merged into one phase because each is a small parameter lookup.

### 6.1 BrainField K-modulation

```python
class BrainField(nn.Module):
    K_TABLE = {'water': 0, 'wood': 2, 'fire': 1, 'earth': 3, 'metal': 4}
    
    def set_qi_profile(self, profile):
        state = profile.get('state', 'earth')
        self.K = self.K_TABLE.get(state, 2)
        
    def maybe_step(self, compressed):
        if self.K == 0:
            return self.field_state
        self._step_counter += 1
        if self._step_counter % self.K != 0:
            return self.field_state
        # ... update logic ...
```

**No QiAware mixin.** Direct `set_qi_profile()` call from `CassiBrain` after `qi_cycle.step()`.

### 6.2 Changepoint Qi-sensitization

```python
class ChangepointDetector:
    QI_SENSITIVITY = {
        'fire': (0.8, 10), 'wood': (0.6, 6), 'earth': (0.5, 5),
        'metal': (0.3, 3), 'water': (0.7, 8),
    }
    
    def update(self, x, qi_state='earth'):
        thresh, win = self.QI_SENSITIVITY.get(qi_state, (0.5, 5))
        # ... resize buffer, compute drift ...
        confidence = min(1.0, drift / thresh)
        triggered = drift > thresh
        return triggered, confidence
```

In `CassiBrain.forward()`:
```python
triggered, confidence = self.changepoint.update(cp_input, qi_state=stem_info['state'])
if triggered and confidence > 0.8:
    info['changepoint'] = True
    info['changepoint_confidence'] = confidence
```

No direct state mutation. QiCycle handles the transition signal.

### 6.3 Soul Qi-adaptation

```python
class SoulVector(nn.Module):
    SOUL_DYNAMICS = {
        'fire': (0.90, 0.3), 'wood': (0.95, 0.5), 'earth': (0.99, 1.0),
        'metal': (0.995, 1.5), 'water': (1.00, 0.1),
    }
    
    def set_qi_profile(self, profile):
        state = profile.get('state', 'earth')
        decay, scale = self.SOUL_DYNAMICS.get(state, (0.99, 1.0))
        self.decay = decay
        self.injection_scale = scale
        
    def update(self, brain_state_mean):
        if self.decay >= 1.0:
            return
        self.vector = self.decay * self.vector + (1 - self.decay) * brain_state_mean.detach()
        
    def inject(self, brain_state):
        if self.injection_scale <= 0:
            return brain_state
        soul = self.vector.unsqueeze(0).expand(brain_state.shape[0], -1)
        return brain_state + self.injection_scale * 0.05 * soul
```

### 6.4 Spine resonance Qi-modulation

```python
# In Brainstem.step():
baseline_phi = self.qi.PROFILES['earth']['phi_fast']  # explicit baseline
phi_fast = profile.get('phi_fast', baseline_phi)
phi_fast_scale = phi_fast / baseline_phi
phi_fast_scale = max(0.5, min(2.0, phi_fast_scale))

# In returned modulation dict:
'modulation': {
    'theta_shift': theta_shift,
    'damp_scale': damp_scale,
    'yang_gain': yang_gain,
    'yin_gain': yin_gain,
    'phi_fast_scale': phi_fast_scale,
}
```

In `CordPhysics.step()`:
```python
def step(self, x_new, ..., phi_fast_scale=1.0):
    for c in range(self.C):
        effective_phi = self.phi_damp[c] * phi_fast_scale * damp_scale
        effective_phi = max(0.1, min(1.0, effective_phi))
        # ... IIR computation with effective_phi ...
```

### 6.5 Fast-weight Qi-modulation

```python
# In CordPhysics.step(), when brainstem_gate=True:
if brainstem_gate and hasattr(self, 'theta_fast_fwd'):
    # Qi profile modulates fast-weight learning rate
    lr_scale = profile.get('lr_fast', 0.6) / 0.6
    self.theta_fast_fwd[c] += lr_scale * 0.01 * grad_theta
    self.gain_fast[c] += lr_scale * 0.01 * grad_gain
```

### 6.6 Qi-conditioned loss weights

```python
# In train_multimodal.py:
QI_LOSS_WEIGHTS = {
    'fire':   {'pred': 1.5, 'coherence': 0.3, 'spectral': 1.0},
    'wood':   {'pred': 1.2, 'coherence': 0.7, 'spectral': 0.8},
    'earth':  {'pred': 1.0, 'coherence': 1.0, 'spectral': 1.0},
    'metal':  {'pred': 0.8, 'coherence': 1.2, 'spectral': 1.5},
    'water':  {'pred': 0.5, 'coherence': 1.5, 'spectral': 0.3},
}

qi_state = info.get('qi_state', 'earth')
weights = QI_LOSS_WEIGHTS.get(qi_state, QI_LOSS_WEIGHTS['earth'])

loss = (weights['pred'] * loss_pred +
        weights['coherence'] * COHERENCE_WEIGHT * coherence +
        weights['spectral'] * spectral_loss +
        ...)
```

### Testing
- Fire state → verify BrainField K=1, Soul decay=0.90, loss pred weight=1.5
- Water state → verify BrainField K=0 (frozen), Soul decay=1.00 (frozen), loss pred weight=0.5
- Metal state → verify Changepoint threshold=0.3, Soul injection=1.5, spectral weight=1.5
- Verify `effective_phi` stays in [0.1, 1.0] across all states
- Verify fast-weight LR scales with Qi profile

### Deliverable
- BrainField K-table via `set_qi_profile()`
- Changepoint sensitivity table
- Soul dynamics table
- Spine `phi_fast_scale` via brainstem modulation
- Fast-weight LR scaling
- Qi-conditioned loss weights

---

## Phase 7: Observability & Integration

**Goal:** Dashboard panels, metrics, and training loop integration for the full Qi-native system.

### 7.1 New metrics

```python
# In CassiMetrics:
self.batch_buffer.update({
    'qi_state': deque(maxlen=window_size),
    'phi_fast_scale': deque(maxlen=window_size),
    'soul_strength': deque(maxlen=window_size),
    'brainfield_k': deque(maxlen=window_size),
})

def record_batch(self, info, ...):
    # ... existing metrics ...
    record['qi_state'] = info.get('qi_state', 'earth')
    record['phi_fast_scale'] = info.get('phi_fast_scale', 1.0)
    record['soul_strength'] = info.get('soul_strength', 1.0)
    record['brainfield_k'] = info.get('brainfield_k', 2)
```

### 7.2 Dashboard panels

Add to `CassiMetrics.plot_dashboard()`:
```python
panels = [
    # ... existing panels ...
    ('qi_state', 'Qi State', 'tab:purple'),  # encoded as 0-4
    ('phi_fast_scale', 'Phi Fast Scale', 'tab:orange'),
    ('soul_strength', 'Soul Strength', 'tab:pink'),
    ('brainfield_k', 'BrainField K', 'tab:cyan'),
]
```

### 7.3 DreamBank summary in training logs

```python
if dream_bank is not None:
    log_print(f"  {dream_bank.summary()}")
    log_print(f"  Qi transitions this epoch: {model.qi_cycle._transition_count}")
```

### 7.4 Qi state time distribution

```python
@property
def qi_distribution(self):
    """Fraction of time spent in each Qi state over the epoch."""
    if not self.epoch_records:
        return {}
    states = [r.get('qi_state', 'earth') for r in self.epoch_records[-1].get('batches', [])]
    total = len(states)
    return {s: states.count(s) / total for s in set(states)} if total > 0 else {}
```

### 7.5 Training loop integration

```python
for ep in range(start_ep, args.epochs):
    train_loss, train_pred, train_coherence, mod_counts = \
        train_epoch(model, loader, opt, mp_trainer, args, 
                   adaptive, audio_encoder, metrics=metrics, dream_bank=dream_bank)
    
    # Reset transition counter after epoch
    model.qi_cycle._transition_count = 0
    
    # DreamBank replay
    if dream_bank is not None:
        replay_results = []
        for _ in range(args.dream_replay):
            mode = dream_bank.choose_mode()
            samples, replay_state = dream_bank.sample_for_replay(mode)
            if samples is None:
                continue
            loss, state = dream_bank.replay_forward(model, samples, replay_state)
            dream_bank.apply_replay_step(opt, loss, state)
            
            # Track per-experience replay losses for migration
            for exp in samples:
                exp._replay_losses = getattr(exp, '_replay_losses', []) + [loss.item()]
                
            replay_results.append({'loss': loss.item(), 'state': state})
            
        # Migration pass (in Metal state or every 10 replays)
        if model.qi_cycle.state == 'metal' or ep % 5 == 0:
            dream_bank.run_migration()
            dream_bank.rebalance_capacity()
```

### Testing
- Verify all new metrics appear in `epoch_metrics.jsonl`
- Verify dashboard renders new panels without error
- Verify `qi_distribution` sums to 1.0
- Verify DreamBank replay results are logged
- Verify migration runs during Metal state

### Deliverable
- Qi-state metrics in CassiMetrics
- Dashboard panels for Qi dynamics
- DreamBank replay + migration in training loop
- Qi state distribution tracking

---

## Appendix: Dependency Graph

```
Phase 0: Stability Guard
    └── Phase 1: QiCycle Conductor
            └── Phase 2: Qi-Aware Brainstem + DreamBank
                    └── Phase 3: Five Sub-Banks
                            └── Phase 4: Qi-Matched Replay
                                    └── Phase 5: Berry Memory Qi-Keying
                                            └── Phase 6: Qi-Aware Subsystems
                                                    └── Phase 7: Observability
```

**Parallelizable after Phase 4:** Phases 5 and 6 are independent. Phase 7 depends on both.

## Appendix: Rollback Strategy

| Phase | Rollback | How |
|-------|----------|-----|
| 0 | Disable clamp | Set `conscious_norm` threshold to `float('inf')` |
| 1 | Disable conductor | Pass `qi_state=None` to brainstem (fallback to self-diagnosis) |
| 2 | Disable Qi tagging | `capture_qi_state='earth'` for all experiences |
| 3 | Merge banks back | Concatenate all sub-banks into single list |
| 4 | Flat replay | Set `GENERATING_CYCLE[state] = state` (identity mapping) |
| 5 | Drop Qi embedding | Set `qi_vec = zeros` (neutral effect on similarity) |
| 6 | Neutral profiles | Override all profile values to Earth's baseline |
| 7 | Skip metrics | Omit new keys from dashboard (graceful degradation) |

## Appendix: Cut Features (Revisit Later)

- **Per-slot Qi tracking in BerryMemory** — learned embedding achieves 90% of benefit
- **Controlling cycle** — generating cycle alone is sufficient for first implementation
- **Five soul sub-vectors** — single vector with Qi-adaptive dynamics is enough
- **DreamBank-to-Berry direct write** — use `_on_purified()` hook when needed
- **Asynchronous Qi callbacks** — `set_qi_profile()` is simpler and sufficient
