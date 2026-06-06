"""Audio utilities — FLAC decoding via ffmpeg, waveform preprocessing."""

import subprocess
import numpy as np
import torch


def decode_flac_bytes(flac_bytes: bytes, target_sr: int = 16000) -> np.ndarray:
    """Decode FLAC bytes to float32 waveform [-1, 1] using ffmpeg.

    flac_bytes: raw FLAC file bytes
    target_sr: target sample rate (ffmpeg will resample)
    Returns: float32 numpy array [n_samples]
    """
    proc = subprocess.run(
        ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-acodec', 'pcm_s16le',
         '-ar', str(target_sr), '-ac', '1', 'pipe:1'],
        input=flac_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode('utf-8', errors='replace')[:200]}")

    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def load_audio_from_parquet_row(row_dict: dict, target_sr: int = 16000) -> tuple:
    """Load audio and transcript from a parquet row dict.

    row_dict: dict with 'audio' (dict with 'bytes') and 'text'
    Returns: (waveform_np, transcript_str)
    """
    audio_bytes = row_dict['audio']['bytes']
    transcript = row_dict.get('text', '')
    waveform = decode_flac_bytes(audio_bytes, target_sr)
    return waveform, transcript


def waveform_to_tensor(waveform: np.ndarray, target_samples: int = 1024) -> torch.Tensor:
    """Pad/trim waveform to exact sample count.

    waveform: [n_samples] float32
    target_samples: desired length
    Returns: [target_samples] float32 tensor
    """
    n = len(waveform)
    if n < target_samples:
        padded = np.zeros(target_samples, dtype=np.float32)
        padded[:n] = waveform
        waveform = padded
    elif n > target_samples:
        waveform = waveform[:target_samples]
    return torch.from_numpy(waveform).float()
