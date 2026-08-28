"""MultimodalDataLoader — serves physics, text, and audio with curriculum scheduling.

Curriculum phases:
  0. physics_only         — physics windows only
  1. physics_equations    — physics + equation overlays (future)
  2. physics_descriptions — physics + English descriptions
  3. speech_audio         — audio + transcripts
  4. text_images          — text rendered as images (future)
  5. all_modalities       — mixed sampling from all
"""

import torch
import numpy as np
import os
import json
import warnings

from cassi.streaming_text_sampler import StreamingTextSampler


class MultimodalDataLoader:
    """Unified loader for physics, text, and audio data."""

    PHASE_NAMES = [
        'physics_only',
        'physics_equations',
        'physics_descriptions',
        'speech_audio',
        'text_images',
        'all_modalities',
    ]

    def __init__(self,
                 physics_cache='datasets/physics_cache_v10.pt',
                 active_dir='datasets/active',
                 audio_source='datasets/active/MLCommons-peoples_speech.parquet',
                 phase=0,
                 val_frac=0.02,
                 seed=42):
        self.phase = phase
        self.val_frac = val_frac
        self.rng = np.random.RandomState(seed)
        self.val_rng = np.random.RandomState(seed + 1)

        # ── Physics ──
        self.physics_cache = physics_cache
        self._physics_loaded = False
        self.physics_nt = 0
        self.physics_nv = 0

        # ── Text ──
        self.text_sampler = StreamingTextSampler(None, window_bytes=1024, stride=256, device='cpu')
        self.text_total = 0
        self.text_n_val = 0
        self._load_text_data(active_dir)

        # ── Audio ──
        self.audio_source = audio_source
        self.audio_available = os.path.exists(audio_source)
        self.audio_transcripts = []
        self._load_audio_metadata()

        # ── Physics descriptions ──
        self.descriptions = []
        self._load_descriptions(active_dir)

        # ── Phase 8 curiosity-driven curriculum ──
        # Optional external weights override phase-based ratios.
        self.curiosity_weights = None

    def _load_physics(self):
        if self._physics_loaded:
            return
        cache = torch.load(self.physics_cache, map_location='cpu', weights_only=False)
        wins = cache['windows']
        if isinstance(wins, list):
            wins = torch.stack(wins)
        # Filter out any windows with NaN, Inf, or extreme outliers as a safety measure.
        valid_mask = torch.isfinite(wins).all(dim=(1, 2)) & (wins.abs().amax(dim=(1, 2)) <= 100.0)
        if not valid_mask.all():
            wins = wins[valid_mask]
        self.wins = wins
        self.n = len(self.wins)
        # Multi-horizon support
        self.physics_input_frames = cache.get('input_frames', 4)
        self.physics_horizons = cache.get('horizons', [1])
        perm = self.rng.permutation(self.n)
        split = int(self.n * (1 - self.val_frac))
        self.physics_train_idx = perm[:split]
        self.physics_val_idx = perm[split:]
        self.physics_nt = len(self.physics_train_idx)
        self.physics_nv = len(self.physics_val_idx)
        self._physics_loaded = True

    def _load_text_data(self, active_dir):
        if not os.path.exists(active_dir):
            return
        for fname in sorted(os.listdir(active_dir)):
            path = os.path.join(active_dir, fname)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(fname)[1].lower()
            try:
                if ext == '.txt':
                    with open(path, 'rb') as f:
                        self.text_sampler.append(f.read())
                elif ext in ('.json', '.jsonl'):
                    self._append_json(path)
                elif ext == '.parquet' and 'peoples_speech' not in fname:
                    self._append_parquet(path)
            except Exception as e:
                warnings.warn(f"Failed to load {path}: {e}")
        self.text_total = self.text_sampler.size
        self.text_n_val = int(self.text_total * self.val_frac)
        self.text_n_train = self.text_total - self.text_n_val

    def _append_json(self, path):
        import json
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        try:
            obj = json.loads(content)
            if isinstance(obj, dict) and 'chars' in obj:
                return  # skip tokenized
            elif isinstance(obj, list):
                texts = [x for x in obj if isinstance(x, str)]
                if texts:
                    self.text_sampler.append('\n\n'.join(texts).encode('utf-8'))
        except json.JSONDecodeError:
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        for key in ('text', 'content', 'instruction', 'response'):
                            if key in obj and isinstance(obj[key], str):
                                self.text_sampler.append(obj[key].encode('utf-8'))
                                break
                except json.JSONDecodeError:
                    pass

    def _append_parquet(self, path):
        try:
            import pyarrow.parquet as pq
            df = pq.read_table(path).to_pandas()
            for col in df.columns:
                if df[col].dtype == object:
                    sample = df[col].dropna().iloc[:5].tolist()
                    if any(isinstance(x, str) and len(x) > 20 for x in sample):
                        texts = df[col].dropna().astype(str).tolist()
                        self.text_sampler.append('\n\n'.join(texts).encode('utf-8'))
                        break
        except ImportError:
            pass

    def _load_audio_metadata(self):
        """Load audio transcript metadata."""
        if not self.audio_available:
            return
        try:
            import pyarrow.parquet as pq
            df = pq.read_table(self.audio_source).to_pandas()
            if 'text' in df.columns:
                self.audio_transcripts = df['text'].dropna().astype(str).tolist()[:50000]
            elif 'transcript' in df.columns:
                self.audio_transcripts = df['transcript'].dropna().astype(str).tolist()[:50000]
            # Also store full rows for audio decoding
            self.audio_rows = df.to_dict('records')
        except Exception as e:
            warnings.warn(f"Failed to load audio metadata from {self.audio_source}: {e}")
            self.audio_available = False

    def _load_descriptions(self, active_dir):
        """Load physics description files."""
        desc_path = os.path.join(active_dir, 'physics_descriptions.txt')
        if os.path.exists(desc_path):
            with open(desc_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.descriptions = f.read().split('\n\n')
        else:
            # Try jsonl
            desc_path_jsonl = os.path.join(active_dir, 'physics_descriptions.jsonl')
            if os.path.exists(desc_path_jsonl):
                with open(desc_path_jsonl, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                obj = json.loads(line)
                                if 'text' in obj:
                                    self.descriptions.append(obj['text'])
                            except json.JSONDecodeError:
                                self.descriptions.append(line)

    def get_phase_name(self):
        return self.PHASE_NAMES[min(self.phase, len(self.PHASE_NAMES) - 1)]

    def advance_phase(self):
        """Move to next curriculum phase."""
        if self.phase < len(self.PHASE_NAMES) - 1:
            self.phase += 1
        return self.get_phase_name()

    def set_curiosity_weights(self, weights):
        """Set Phase 8 curiosity-driven sampling weights.

        weights: dict {'physics': float, 'text': float, 'audio': float}
                 or None to disable.
        """
        self.curiosity_weights = weights

    def sample_train_batch(self, batch_size, device='cuda', return_indices=False):
        """Sample a batch according to current curriculum phase.

        Returns: (x, y, modality_tag) by default.
        If return_indices=True, returns (x, y, indices, modality_tag).
        indices are window indices for physics, None otherwise.
        """
        phase_name = self.get_phase_name()

        if phase_name == 'physics_only':
            return self._sample_physics(batch_size, device, return_indices=return_indices)

        # Phase 8: curiosity-driven weights override phase-based ratios
        if self.curiosity_weights is not None:
            physics_w = self.curiosity_weights.get('physics', 1.0 / 3)
            audio_w = self.curiosity_weights.get('audio', 1.0 / 3)
            text_w = self.curiosity_weights.get('text', 1.0 / 3)
            total = physics_w + audio_w + text_w
            return self._sample_mixed(
                batch_size, device,
                physics_ratio=physics_w / total,
                audio_ratio=audio_w / total,
                return_indices=return_indices,
            )

        if phase_name == 'physics_descriptions':
            return self._sample_mixed(batch_size, device, physics_ratio=0.5,
                                      return_indices=return_indices)
        elif phase_name == 'speech_audio':
            return self._sample_mixed(batch_size, device, audio_ratio=0.5,
                                      return_indices=return_indices)
        elif phase_name == 'all_modalities':
            return self._sample_mixed(batch_size, device, physics_ratio=0.25,
                                      audio_ratio=0.25,
                                      return_indices=return_indices)
        else:
            # Default: physics + text mix
            return self._sample_mixed(batch_size, device, physics_ratio=0.5,
                                      return_indices=return_indices)

    def _sample_physics(self, batch_size, device, return_indices=False):
        self._load_physics()
        idx = self.rng.choice(self.physics_train_idx, size=batch_size, replace=False)
        n_in = self.physics_input_frames
        x = self.wins[idx][:, :n_in].to(device)
        if len(self.physics_horizons) > 1:
            # Multi-horizon: gather target frames
            target_indices = [n_in + h - 1 for h in self.physics_horizons]
            y = self.wins[idx][:, target_indices].to(device)  # [B, H, 1024]
        else:
            y = self.wins[idx][:, n_in:n_in+1].to(device)  # [B, 1, 1024]
        if return_indices:
            return x, y, idx, 'physics'
        return x, y, 'physics'

    def _sample_text(self, batch_size, device):
        max_start = self.text_sampler.size - 1024 - 256
        if max_start <= 0:
            max_start = max(1, self.text_sampler.size - 1280)
        starts = self.rng.randint(0, max_start, size=batch_size)
        idx = np.arange(1024)
        x_idx = starts[:, None] + idx[None, :]
        y_idx = (starts + 256)[:, None] + idx[None, :]
        data = self.text_sampler._ring[:self.text_sampler._ring_size]
        x = torch.from_numpy(data[x_idx]).to(device, dtype=torch.uint8)
        y = torch.from_numpy(data[y_idx]).to(device, dtype=torch.uint8)
        return x, y, 'text'

    def _sample_audio(self, batch_size, device):
        """Sample audio waveforms + transcripts."""
        if not self.audio_available or len(self.audio_rows) == 0:
            return self._sample_text(batch_size, device)

        from cassi.audio_utils import decode_flac_bytes, waveform_to_tensor
        from cassi.audio_encoder import AudioFieldEncoder

        x_list = []
        y_list = []
        texts = []

        for _ in range(batch_size):
            idx = self.rng.randint(0, len(self.audio_rows))
            row = self.audio_rows[idx]

            # Decode audio
            try:
                waveform = decode_flac_bytes(row['audio']['bytes'], target_sr=16000)
                # Take first 1024 samples as input, next 1024 as target
                if len(waveform) < 2048:
                    waveform = np.pad(waveform, (0, 2048 - len(waveform)))
                w_in = waveform[:1024]
                w_out = waveform[1024:2048]
                x_list.append(torch.from_numpy(w_in).float())
                y_list.append(torch.from_numpy(w_out).float())
                texts.append(row.get('text', ''))
            except Exception as e:
                warnings.warn(f"Audio decode failed, falling back to text: {e}")
                text = row.get('text', '')
                b = text.encode('utf-8') if text else b'\x00' * 1280
                if len(b) < 1280:
                    b = b + b'\\x00' * (1280 - len(b))
                b = b[:1280]
                x_list.append(torch.tensor(list(b[:1024]), dtype=torch.uint8).float())
                y_list.append(torch.tensor(list(b[256:1280]), dtype=torch.uint8).float())

        x = torch.stack(x_list).to(device)
        y = torch.stack(y_list).to(device)
        return x, y, 'audio'
    def _sample_mixed(self, batch_size, device, physics_ratio=0.5, audio_ratio=0.0,
                      return_indices=False):
        """Sample a mixed batch from multiple modalities.

        If return_indices=True, returns (x, y, indices, tag); otherwise
        the default (x, y, tag) tuple is returned.
        """
        n_physics = int(batch_size * physics_ratio)
        n_audio = int(batch_size * audio_ratio)
        n_text = batch_size - n_physics - n_audio

        parts = []
        if n_physics > 0:
            parts.append(('physics', n_physics))
        if n_text > 0:
            parts.append(('text', n_text))
        if n_audio > 0:
            parts.append(('audio', n_audio))

        if not parts:
            parts = [('text', batch_size)]

        tag, n = self.rng.choice(parts)
        if tag == 'physics':
            return self._sample_physics(n, device, return_indices=return_indices)
        elif tag == 'text':
            out = self._sample_text(n, device)
            if return_indices:
                x, y, t = out
                return x, y, None, t
            return out
        else:
            out = self._sample_audio(n, device)
            if return_indices:
                x, y, t = out
                return x, y, None, t
            return out


    def sample_val_batch(self, batch_size, device='cuda', return_indices=False):
        """Sample validation batch respecting curriculum phase."""
        self._load_physics()
        n_in = self.physics_input_frames
        if len(self.physics_horizons) > 1:
            target_indices = [n_in + h - 1 for h in self.physics_horizons]
        else:
            target_indices = [n_in]

        if self.phase == 0:
            idx = self.val_rng.choice(self.physics_val_idx, size=min(batch_size, self.physics_nv), replace=False)
            x = self.wins[idx][:, :n_in].to(device)
            y = self.wins[idx][:, target_indices].to(device)  # [B, n_horizons, 1024]
            if return_indices:
                return x, y, idx, 'physics'
            return x, y, 'physics'
        elif self.phase in (2, 3, 5):
            # Mixed validation: sample from all active modalities
            return self.sample_train_batch(batch_size, self.val_rng, device=device, return_indices=return_indices)
        else:
            # Default to physics
            idx = self.val_rng.choice(self.physics_val_idx, size=min(batch_size, self.physics_nv), replace=False)
            x = self.wins[idx][:, :n_in].to(device)
            y = self.wins[idx][:, target_indices].to(device)  # [B, n_horizons, 1024]
            if return_indices:
                return x, y, idx, 'physics'
            return x, y, 'physics'

    def val_steps(self, batch_size):
        self._load_physics()
        if self.phase == 0:
            return max(1, self.physics_nv // batch_size)
        # For mixed phases, use a reasonable fixed number of val steps
        return max(1, 100)

    @property
    def nt(self):
        self._load_physics()
        return self.physics_nt

    @property
    def nv(self):
        self._load_physics()
        return self.physics_nv
