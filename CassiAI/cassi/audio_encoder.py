"""Audio field encoder using the wave basis.

Audio is naturally wave-like — the sinusoidal basis is a perfect match.
We encode audio frames as amplitudes of frequency components.
"""

import torch
import torch.nn as nn
import numpy as np


class AudioFieldEncoder(nn.Module):
    """Encode audio waveforms as Cord-compatible field representations.

    Uses STFT-like frequency decomposition, then maps frequency bins
    to the wave encoder's sinusoidal basis.
    """

    def __init__(self, sample_rate=16000, n_fft=512, hop_length=256,
                 n_mels=128, dim_field=1024, window_size=1024):
        super().__init__()
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.dim_field = dim_field
        self.window_size = window_size  # samples per frame

        # Mel filterbank (learnable or fixed)
        # Fixed mel bins for stability
        mel_basis = self._create_mel_filterbank(sample_rate, n_fft, n_mels)
        self.register_buffer('mel_basis', mel_basis)  # [n_mels, n_fft//2+1]

        # Project mel spectrogram to field dimensions
        self.mel_to_field = nn.Linear(n_mels, dim_field)

        # Phase encoder: learn to encode phase information
        self.phase_proj = nn.Linear(n_mels, dim_field)

    def _create_mel_filterbank(self, sr, n_fft, n_mels, f_min=0, f_max=None):
        """Create a mel filterbank matrix."""
        if f_max is None:
            f_max = sr // 2

        # Mel scale conversion
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)

        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595) - 1)

        mel_min = hz_to_mel(f_min)
        mel_max = hz_to_mel(f_max)
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = mel_to_hz(mel_points)
        bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

        # Vectorized mel filterbank construction
        n_freqs = n_fft // 2 + 1
        filterbank = np.zeros((n_mels, n_freqs))
        for i in range(n_mels):
            # Left ramp: bin_points[i] -> bin_points[i+1]
            left_start, left_peak = bin_points[i], bin_points[i + 1]
            if left_peak > left_start:
                left_idx = np.arange(left_start, left_peak)
                filterbank[i, left_idx] = (left_idx - left_start) / (left_peak - left_start)
            # Right ramp: bin_points[i+1] -> bin_points[i+2]
            right_peak, right_end = bin_points[i + 1], bin_points[i + 2]
            if right_end > right_peak:
                right_idx = np.arange(right_peak, right_end)
                filterbank[i, right_idx] = (right_end - right_idx) / (right_end - right_peak)

        return torch.from_numpy(filterbank).float()

    def stft(self, waveform):
        """Simple differentiable STFT.

        waveform: [B, T] or [T]
        Returns: magnitude [B, n_freqs, n_frames], phase [B, n_freqs, n_frames]
        """
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        B, T = waveform.shape
        n_freqs = self.n_fft // 2 + 1

        # Pad to multiple of hop_length
        pad_len = (self.hop_length - T % self.hop_length) % self.hop_length
        if pad_len > 0:
            waveform = torch.nn.functional.pad(waveform, (0, pad_len))

        # Unfold into frames
        n_frames = (waveform.shape[1] - self.n_fft) // self.hop_length + 1
        frames = waveform.unfold(1, self.n_fft, self.hop_length)  # [B, n_frames, n_fft]

        # Hann window (registered as buffer for reuse)
        if not hasattr(self, '_hann_window') or self._hann_window.device != waveform.device:
            self.register_buffer('_hann_window', torch.hann_window(self.n_fft, device=waveform.device))
        frames = frames * self._hann_window.unsqueeze(0).unsqueeze(0)

        # FFT
        fft = torch.fft.rfft(frames, dim=-1)  # [B, n_frames, n_freqs]
        magnitude = fft.abs()  # [B, n_frames, n_freqs]
        phase = fft.angle()  # [B, n_frames, n_freqs]

        return magnitude, phase

    def encode(self, waveform):
        """Encode audio waveform → field representation.

        waveform: [B, n_samples] float in [-1, 1]
        Returns: [B, dim_field] field vector
        """
        magnitude, phase = self.stft(waveform)
        # magnitude: [B, n_frames, n_freqs]

        # Average across time frames
        mag_mean = magnitude.mean(dim=1)  # [B, n_freqs]
        # Circular mean for phase (not linear mean)
        sin_mean = torch.sin(phase).mean(dim=1)  # [B, n_freqs]
        cos_mean = torch.cos(phase).mean(dim=1)  # [B, n_freqs]
        phase_mean = torch.atan2(sin_mean, cos_mean)  # [B, n_freqs]

        # Apply mel filterbank
        mel_mag = mag_mean @ self.mel_basis.T  # [B, n_mels]
        mel_phase = phase_mean @ self.mel_basis.T  # [B, n_mels]

        # Log compression for dynamic range
        mel_mag = torch.log1p(mel_mag.clamp(min=0))

        # Encode to field
        field_mag = self.mel_to_field(mel_mag)  # [B, dim_field]
        field_phase = self.phase_proj(torch.sin(mel_phase))  # [B, dim_field]

        field = field_mag + 0.1 * field_phase
        return field

    def encode_window(self, waveform, target_samples=1024):
        """Encode a window of audio to match byte window size.

        waveform: [B, n_samples] — will be resampled/trimmed to target_samples
        Returns: [B, dim_field]
        """
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        B, n = waveform.shape
        if n < target_samples:
            waveform = torch.nn.functional.pad(waveform, (0, target_samples - n))
        elif n > target_samples:
            waveform = waveform[:, :target_samples]

        return self.encode(waveform)
