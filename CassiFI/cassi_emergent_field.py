"""Emergent two-fluid field memory: chords over every note the lattice owns.

The field holds the memory; the brain is a mathematical machine that encodes
into the field and decodes out of it.

Field.  The canonical Yang/Yin pair runs on a medium whose density ``rho``
belongs to the field itself:

    rho (Y'' + gamma Y') = lap Y - omega^2 (Y - phi I) + drive_Y
    rho (I'' + gamma I') = lap I + omega^2 (Y - phi I) + drive_I

The pair splits exactly into two waves.  Their sum, the Qi wave S = Y + I,
feels no coupling at all:

    rho (S'' + gamma S') = lap S + drive_Y + drive_I

Their imbalance eps = Y - phi I is the counterflow, a wave with mass
omega phi: rho (eps'' + gamma eps') = lap eps - omega^2 phi^2 eps + drive_Y - phi drive_I.
The brain drives Yang and Yin in golden proportion, drive_Y = phi drive_I, so
the counterflow is never excited: eps stays exactly zero, the pair moves as
one Qi wave with Y = S / phi and I = S / phi^2, and the field steps S alone.

Where Qi intensity gathers the medium thickens, and it relaxes without it:

    rho' = eta * <S^2> / (<S^2> + I_half) * (rho_max - rho) - mu * (rho - 1)

Many chords may sound at once, each on its own Qi wave over the one medium;
the medium hears the sum of their intensities, and far below its saturation
that is exactly what playing them one after another would leave.

On a blank medium the field's standing waves (its notes) are exact and never
mix: psi_k = prod_axis cos(pi k_axis (x_axis + 1/2) / n), one note per cell.
Driven at the pitch w, a note of stiffness lambda resonates at lambda = w^2.
Every other note answers cleanly, so the brain plays all of them.  Nothing
else is coded.

Brain.  An idea is a chord: a blend of every clean note with random phases,
shaped so its brightness |S(x)|^2 is nearly even across the field.  Two
chords A and B played together at one pitch leave
|A|^2 + |B|^2 + 2 Re(A conj B) in the medium; the even self terms only retune
each note in place, so the imprint that couples notes is the link itself.
The medium couples notes through K_km = sum_x (rho - 1) psi_k psi_m, and K
is the memory.

To read, the brain bows a chord (a smooth swell, so the field does not ring),
listens to the Qi wave note by note, and inverts the known physics exactly:
it subtracts the response of an even medium and divides by each note's own
answer to the drive, like tuning an instrument.  As links accumulate the
medium thickens on average, and an even thickening slows every wave alike.
The brain follows it: it plays at w / sqrt(1 + level), where level is the
mean imprint, and tunes against an even medium at that same level, so what
it subtracts is everything held evenly and what remains is the uneven imprint.
What remains is K applied to the chord, which carries |A|^2 B = B for a
stored link.  Random chords over N notes overlap by about 1/sqrt(N), so a
link's clarity falls as sqrt(N / links) and the number of links a field
holds grows with its number of cells.

Sequences.  Each idea owns two chords, one it sends with and one it receives
with.  A step a -> b is stored by playing a's sending chord with b's receiving
chord.  The medium's coupling is symmetric, yet the pairing gives direction:
playing a's sending chord answers with b, and playing b's receiving chord
answers with a, so a train of thought runs forward and can be traced back.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import torch


@dataclass(frozen=True)
class EmergentProfile:
    dims: int = 3
    size: int = 64
    dt: float = 0.25
    gamma: float = 0.01
    pitch: float = 2.0
    eta: float = 0.0002
    intensity_tau: float = 100.0
    intensity_half: float = 1000.0
    rho_max: float = 3.0
    mu: float = 0.000001
    onset: float = 50.0
    # A note is clean when its Qi answer to the drive stays within this gain of resonance.
    clean_gain: float = 4.0
    dtype: str = "float32"
    device: str = "cpu"


def _lap(S: torch.Tensor, dims: int) -> torch.Tensor:
    """Flux-free (Neumann) lattice Laplacian over the trailing ``dims`` axes of a batch."""
    out = torch.zeros_like(S)
    for axis in range(S.dim() - dims, S.dim()):
        flux = torch.diff(S, dim=axis)
        n = S.shape[axis]
        out.narrow(axis, 0, n - 1).add_(flux)
        out.narrow(axis, 1, n - 1).sub_(flux)
    return out


def _envelope(t: float, onset: float) -> float:
    """Bowed onset: the drive swells smoothly so the field is not struck into ringing."""
    return 1.0 if t >= onset else math.sin(0.5 * math.pi * t / onset) ** 2


def _complex(real: torch.dtype) -> torch.dtype:
    return torch.complex64 if real == torch.float32 else torch.complex128


_WAVE_SOURCE = r"""
extern "C" __global__ void wave_step(const float* __restrict__ S, float* __restrict__ Sn, float* __restrict__ V,
    const float* __restrict__ rho, const float* __restrict__ Dr, const float* __restrict__ Di,
    float* __restrict__ re, float* __restrict__ im, int n,
    float c, float s, float keep, float dt, float ca, float sa, int acc)
{
    int n2 = n * n, cells = n2 * n;
    int cell = blockIdx.x * blockDim.x + threadIdx.x;
    if (cell >= cells) return;
    size_t i = (size_t)blockIdx.y * cells + cell;
    int x = cell / n2, rem = cell - x * n2, y = rem / n, z = rem - y * n;
    float s0 = S[i], lap = 0.f;
    if (x > 0) lap += S[i - n2] - s0;
    if (x < n - 1) lap += S[i + n2] - s0;
    if (y > 0) lap += S[i - n] - s0;
    if (y < n - 1) lap += S[i + n] - s0;
    if (z > 0) lap += S[i - 1] - s0;
    if (z < n - 1) lap += S[i + 1] - s0;
    float v = keep * V[i] + dt * ((lap + c * Dr[i] + s * Di[i]) / rho[cell]);
    V[i] = v;
    float sn = s0 + dt * v;
    Sn[i] = sn;
    if (acc) { re[i] += ca * sn; im[i] += sa * sn; }
}

extern "C" __global__ void imprint_step(const float* __restrict__ S, float* __restrict__ S2,
    float* __restrict__ imprint, float* __restrict__ rho, int batch, int cells,
    float blend, float eta, float half, float rho_max, float mu, float dt)
{
    int cell = blockIdx.x * blockDim.x + threadIdx.x;
    if (cell >= cells) return;
    float q = 0.f;
    for (int b = 0; b < batch; ++b) { float x = S[(size_t)b * cells + cell]; q += x * x; }
    float s2 = S2[cell] + blend * (q - S2[cell]);
    S2[cell] = s2;
    float m = imprint[cell];
    m += dt * (eta * s2 / (s2 + half) * (rho_max - rho[cell]) - mu * m);
    imprint[cell] = m;
    rho[cell] = m + 1.f;
}
"""


class _FusedWave:
    """The same field law as ``EmergentField._sound``, one GPU kernel per step (3D, float32, ROCm).

    Compiled once per process with hiprtc from the ROCm runtime torch ships
    with.  Where that is unavailable the field steps with torch operations.
    """

    _instance: "_FusedWave | None | bool" = None
    BLOCK = 256

    def __init__(self) -> None:
        import ctypes
        import _rocm_sdk_core
        self.ct = ctypes
        bin_dir = Path(_rocm_sdk_core.__file__).parent / "bin"
        rtc = ctypes.CDLL(str(next(bin_dir.glob("hiprtc0*.dll"))))
        self.hip = ctypes.CDLL(str(next(bin_dir.glob("amdhip64_*.dll"))))
        prog = ctypes.c_void_p()
        if rtc.hiprtcCreateProgram(ctypes.byref(prog), _WAVE_SOURCE.encode(), b"cassi_wave.hip", 0, None, None):
            raise RuntimeError("hiprtcCreateProgram failed")
        arch = torch.cuda.get_device_properties(torch.cuda.current_device()).gcnArchName.split(":")[0]
        options = (ctypes.c_char_p * 2)(f"--gpu-architecture={arch}".encode(), b"-O3")
        if rtc.hiprtcCompileProgram(prog, 2, options):
            size = ctypes.c_size_t()
            rtc.hiprtcGetProgramLogSize(prog, ctypes.byref(size))
            log = ctypes.create_string_buffer(size.value)
            rtc.hiprtcGetProgramLog(prog, log)
            raise RuntimeError(log.value.decode(errors="replace"))
        size = ctypes.c_size_t()
        rtc.hiprtcGetCodeSize(prog, ctypes.byref(size))
        self._code = ctypes.create_string_buffer(size.value)
        rtc.hiprtcGetCode(prog, self._code)
        rtc.hiprtcDestroyProgram(ctypes.byref(prog))
        self._module = ctypes.c_void_p()
        if self.hip.hipModuleLoadData(ctypes.byref(self._module), self._code):
            raise RuntimeError("hipModuleLoadData failed")
        self.fn = {}
        for name in ("wave_step", "imprint_step"):
            handle = ctypes.c_void_p()
            if self.hip.hipModuleGetFunction(ctypes.byref(handle), self._module, name.encode()):
                raise RuntimeError(f"hipModuleGetFunction {name} failed")
            self.fn[name] = handle

    @classmethod
    def get(cls, like: torch.Tensor) -> "_FusedWave | None":
        if like.dim() != 3 or like.dtype != torch.float32 or not like.is_cuda or torch.version.hip is None:
            return None
        if cls._instance is None:
            try:
                cls._instance = cls()
            except (ImportError, OSError, RuntimeError, StopIteration):
                cls._instance = False
        return cls._instance or None

    def _launch(self, name: str, grid: tuple[int, int], args: Sequence[tuple[type, Any]]) -> None:
        ct = self.ct
        held = [kind(value) for kind, value in args]
        params = (ct.c_void_p * len(held))(*[ct.cast(ct.byref(h), ct.c_void_p) for h in held])
        stream = ct.c_void_p(torch.cuda.current_stream().cuda_stream)
        if self.hip.hipModuleLaunchKernel(self.fn[name], grid[0], grid[1], 1, self.BLOCK, 1, 1, 0,
                                          stream, params, None):
            raise RuntimeError(f"{name} launch failed")

    def run(self, p: EmergentProfile, drive: torch.Tensor, steps: int, rho: torch.Tensor, w: float,
            listen_from: int | None, imprint: torch.Tensor | None) -> tuple[torch.Tensor, torch.Tensor] | None:
        """Sound ``drive`` for ``steps``; demodulate from step ``listen_from`` and/or let ``imprint`` keep it."""
        ct, dt, n = self.ct, p.dt, p.size
        P, I, F = ct.c_void_p, ct.c_int, ct.c_float
        B, cells = drive.shape[0], n ** 3
        S = torch.zeros(drive.shape, dtype=torch.float32, device=drive.device)
        Sn, V = torch.empty_like(S), torch.zeros_like(S)
        Dr, Di = drive.real.contiguous(), drive.imag.contiguous()
        re = im = S
        if listen_from is not None:
            re, im = torch.zeros_like(S), torch.zeros_like(S)
        if imprint is not None:
            S2 = torch.zeros_like(imprint)
        rho = rho.contiguous()
        blocks = (cells + self.BLOCK - 1) // self.BLOCK
        keep, t = 1.0 - dt * p.gamma, 0.0
        for i in range(steps):
            env = _envelope(t, p.onset)
            c, s = env * math.cos(w * t), env * math.sin(w * t)
            t += dt
            acc = listen_from is not None and i >= listen_from
            self._launch("wave_step", (blocks, B), [
                (P, S.data_ptr()), (P, Sn.data_ptr()), (P, V.data_ptr()), (P, rho.data_ptr()),
                (P, Dr.data_ptr()), (P, Di.data_ptr()), (P, re.data_ptr()), (P, im.data_ptr()), (I, n),
                (F, c), (F, -s), (F, keep), (F, dt), (F, math.cos(w * t)), (F, -math.sin(w * t)), (I, int(acc))])
            S, Sn = Sn, S
            if imprint is not None:
                self._launch("imprint_step", (blocks, 1), [
                    (P, S.data_ptr()), (P, S2.data_ptr()), (P, imprint.data_ptr()), (P, rho.data_ptr()),
                    (I, B), (I, cells), (F, dt / p.intensity_tau), (F, p.eta), (F, p.intensity_half),
                    (F, p.rho_max), (F, p.mu), (F, dt)])
        return (re, im) if listen_from is not None else None


class EmergentField:
    """One continuing medium; its entire adaptive state is ``imprint``.  The Qi wave is silent between plays.

    ``imprint`` is the medium's thickening rho - 1: what it holds.  Keeping it
    apart from the blank density leaves every digit of the float to the memory.
    """

    def __init__(self, profile: EmergentProfile = EmergentProfile()) -> None:
        self.p = profile
        self.imprint = torch.zeros((profile.size,) * profile.dims, dtype=getattr(torch, profile.dtype),
                                   device=torch.device(profile.device))
        self.t = 0.0

    @property
    def rho(self) -> torch.Tensor:
        return self.imprint + 1.0

    @property
    def level(self) -> float:
        """The medium's mean thickening: the part of the imprint that is the same everywhere."""
        return float(self.imprint.mean())

    def pitch(self, level: float) -> float:
        """The pitch that keeps every note in tune over a medium thickened evenly by ``level``.

        An even thickening slows every wave alike, so the brain plays lower by
        sqrt(1 + level), the way a musician retunes to a warm room, and every
        note keeps its place relative to resonance.
        """
        return self.p.pitch / math.sqrt(1.0 + level)

    def _sound(self, drive: torch.Tensor, steps: int, rho: torch.Tensor,
               w: float) -> Iterator[tuple[torch.Tensor, float]]:
        """Play a batch of Qi drives (B, *grid) at pitch ``w``, each on its own quiet wave, from rest.

        The physical drive is Re(D e^{i w t}) under a bowed envelope, given to
        Yang and Yin in golden proportion.  Yields the Qi wave S and the local
        time after every step; ``rho`` is read live, so a player that thickens
        it as it goes is heard.
        """
        p, dt, d = self.p, self.p.dt, self.p.dims
        S = torch.zeros(drive.shape, dtype=rho.dtype, device=drive.device)
        vS = torch.zeros_like(S)
        Dr, Di = drive.real.contiguous(), drive.imag.contiguous()
        keep, t = 1.0 - dt * p.gamma, 0.0
        for _ in range(steps):
            c, s = (_envelope(t, p.onset) * x for x in (math.cos(w * t), math.sin(w * t)))
            force = _lap(S, d).add_(Dr, alpha=c).add_(Di, alpha=-s)
            vS.mul_(keep).addcdiv_(force, rho, value=dt)
            S.add_(vS, alpha=dt)
            t += dt
            yield S, t

    def listen(self, drive: torch.Tensor, steps: int, level: float | None = None) -> torch.Tensor:
        """Hear a batch of Qi drives over the medium, which is only read.

        With ``level`` the drives sound over an even medium thickened by that
        level instead: the reference the brain tunes against.  Either way the
        pitch is the one in tune with the medium's mean.  Identical drives give
        identical answers.  Returns the complex Qi amplitude heard over the
        second half of the play.
        """
        if level is None:
            rho, w = self.rho, self.pitch(self.level)
        else:
            rho, w = torch.full_like(self.imprint, 1.0 + level), self.pitch(level)
        start = steps // 2
        fused = _FusedWave.get(self.imprint)
        if fused is not None:
            re, im = fused.run(self.p, drive, steps, rho, w, start, None)
            return torch.complex(re, im) * (2.0 / (steps - start))
        re = torch.zeros(drive.shape, dtype=rho.dtype, device=drive.device)
        im = torch.zeros_like(re)
        for i, (S, t) in enumerate(self._sound(drive, steps, rho, w)):
            if i >= start:
                re.add_(S, alpha=math.cos(w * t))
                im.add_(S, alpha=-math.sin(w * t))
        return torch.complex(re, im) * (2.0 / (steps - start))

    def play(self, drive: torch.Tensor, steps: int) -> None:
        """Sound a batch of Qi drives together and let the medium keep what it hears.

        The medium thickens where the plays' intensities gather.  Its gate
        stays far below saturation (S^2 << I_half), so B plays sounding
        together imprint the sum of what each would alone.
        """
        p, dt, imprint = self.p, self.p.dt, self.imprint
        rho, w = self.rho, self.pitch(self.level)
        fused = _FusedWave.get(imprint) if imprint.is_contiguous() else None
        if fused is not None:
            fused.run(p, drive, steps, rho, w, None, imprint)
            self.t += steps * dt
            return
        S2 = torch.zeros_like(imprint)
        for S, _ in self._sound(drive, steps, rho, w):
            S2 += (dt / p.intensity_tau) * (S.square().sum(0) - S2)
            imprint += dt * (p.eta * S2 / (S2 + p.intensity_half) * (p.rho_max - rho) - p.mu * imprint)
            torch.add(imprint, 1.0, out=rho)
        self.t += steps * dt

    def rest(self, duration: float) -> None:
        """Silence for ``duration``: the exact solution of the medium law with no Qi present.

        With nothing sounding, rho' = -mu (rho - 1), so every imprint fades by
        the same factor exp(-mu * duration).  No stepping is needed.
        """
        self.imprint *= math.exp(-self.p.mu * duration)
        self.t += duration


class NoteCodec:
    """The brain's instrument: every clean note of the lattice, chords over them, exact decoding."""

    def __init__(self, field: EmergentField, read_steps: int = 800, batch_cells: int = 24_000_000) -> None:
        p = field.p
        n, d, dev = p.size, p.dims, field.imprint.device
        self.field, self.read_steps = field, read_steps
        self.cplx = _complex(field.imprint.dtype)
        self.batch = max(1, batch_cells // n ** d)
        k = torch.arange(n, dtype=torch.float64, device=dev)
        tone = 2.0 - 2.0 * torch.cos(math.pi * k / n)
        lam = torch.zeros((n,) * d, dtype=torch.float64, device=dev)
        for axis in range(d):
            shape = [1] * d
            shape[axis] = n
            lam = lam + tone.view(shape)
        # Continuous-time Qi answer of each note at the pitch; keep the clean ones.
        gain = 1.0 / torch.complex(lam - p.pitch ** 2, torch.full_like(lam, p.gamma * p.pitch)).abs()
        clean = gain <= p.clean_gain
        clean[(0,) * d] = False                      # the uniform note is where even imprints land
        self.index = torch.nonzero(clean)            # (notes, dims)
        coord = (torch.arange(n, dtype=torch.float64, device=dev) + 0.5) / n
        basis = torch.cos(math.pi * coord[:, None] * k[None, :])
        self.basis = (basis / basis.norm(dim=0, keepdim=True)).to(self.cplx)     # (n, n)
        self.volume = float(n ** d) ** 0.5
        self._calibrate()

    @property
    def count(self) -> int:
        return int(self.index.shape[0])

    # -- spectral transforms -------------------------------------------------
    def to_grid(self, amps: torch.Tensor) -> torch.Tensor:
        """Note amplitudes (B, notes) -> field pattern (B, *grid)."""
        n, d = self.field.p.size, self.field.p.dims
        spec = torch.zeros((amps.shape[0],) + (n,) * d, dtype=self.cplx, device=amps.device)
        spec[(slice(None),) + tuple(self.index.T)] = amps.to(self.cplx)
        for _ in range(d):
            spec = torch.tensordot(spec, self.basis, dims=([1], [1]))    # rolls the axis to the end
        return spec

    def to_notes(self, grid: torch.Tensor) -> torch.Tensor:
        """Field pattern (B, *grid) -> note amplitudes (B, notes)."""
        spec = grid.to(self.cplx)
        for _ in range(self.field.p.dims):
            spec = torch.tensordot(spec, self.basis, dims=([1], [0]))
        return spec[(slice(None),) + tuple(self.index.T)]

    # -- tuning --------------------------------------------------------------
    def _measure(self, level: float) -> tuple[torch.Tensor, torch.Tensor]:
        """Every note's Qi answer over an even medium at ``level``, in phase and in quadrature.

        Together the two answers give the even medium's response to any
        drive exactly, leftover ringing included.
        """
        ones = torch.ones((1, self.count), dtype=self.cplx, device=self.index.device)
        pattern = self.to_grid(ones) * self.volume
        heard = self.to_notes(self.field.listen(torch.cat([pattern, 1j * pattern]), self.read_steps, level=level))
        G, quad = heard / self.volume
        return G, quad

    def _calibrate(self) -> None:
        """Tune the instrument on a blank medium and keep the notes that answer cleanly."""
        G, quad = self._measure(0.0)
        keep = (G.abs() >= 0.1 * G.abs().median()) & (G.abs() <= 2.0 * self.field.p.clean_gain)
        self.index = self.index[keep]
        self._tuning = (0.0, G[keep], quad[keep])

    def tune(self) -> tuple[torch.Tensor, torch.Tensor]:
        """(G, quad) in tune with the medium as it is now.

        Everything the medium holds evenly only shifts every note alike; the
        brain retunes to it and measures its answers over an even medium at
        the same level.  What then differs from that reference is exactly the
        uneven imprint, which is where the links are.
        """
        level = self.field.level
        if abs(level - self._tuning[0]) > 1e-7:
            self._tuning = (level, *self._measure(level))
        return self._tuning[1], self._tuning[2]

    def blank(self, drive_notes: torch.Tensor) -> torch.Tensor:
        """Exact Qi answer (B, notes) of the even reference medium to drives given per note."""
        G, quad = self.tune()
        return drive_notes.real * G + drive_notes.imag * quad

    # -- chords --------------------------------------------------------------
    def chords(self, generators: list[torch.Generator], rounds: int = 30) -> torch.Tensor:
        """Random chords (one per generator) whose brightness |S(x)|^2 is as even as the notes allow.

        An even chord's own imprint on the medium is uniform, and a uniform
        imprint only retunes every note in place.  So what the medium records
        from two chords played together is their link and nothing else.  The
        shape is found by alternating between the note band and flat modulus.
        """
        out = []
        for start in range(0, len(generators), self.batch):
            phase = torch.stack([torch.rand(self.count, generator=g, dtype=torch.float64)
                                 for g in generators[start:start + self.batch]]) * (2.0 * math.pi)
            amps = torch.polar(torch.ones_like(phase), phase).to(self.index.device, self.cplx)
            for _ in range(rounds):
                grid = self.to_grid(amps)
                amps = self.to_notes(grid / grid.abs().clamp_min(1e-12))
            out.append(amps / amps.norm(dim=-1, keepdim=True))
        return torch.cat(out)

    def unevenness(self, chord: torch.Tensor) -> float:
        """Relative spread of the chord's brightness across the field (speckle is 1)."""
        bright = self.to_grid(chord[None]).abs() ** 2
        return float(bright.std() / bright.mean())

    def drive(self, chords: torch.Tensor) -> torch.Tensor:
        """Qi drive that makes the amplitude of every note equal the chord."""
        return self.to_grid(chords / self.tune()[0]) * self.volume

    def write(self, a: torch.Tensor, b: torch.Tensor, steps: int) -> None:
        """Play chord pairs together, row by row; the medium keeps the product of each pair's shapes."""
        for part in (a + b).to(self.cplx).split(self.batch):
            self.field.play(self.drive(part), steps)

    def trace(self, chords: torch.Tensor) -> torch.Tensor:
        """K applied to each chord (rows), with the chord's own direction removed."""
        out = []
        for part in chords.to(self.cplx).split(self.batch):
            heard = self.to_notes(self.field.listen(self.drive(part), self.read_steps)) / self.volume
            # What the medium scattered, as the drive that would have produced it.
            G = self.tune()[0]
            source = (heard - self.blank(part / G)) / G
            own = (source * part.conj()).sum(-1, keepdim=True) / (part.abs() ** 2).sum(-1, keepdim=True)
            out.append(source - own * part)
        return torch.cat(out)

    @staticmethod
    def similarity(traces: torch.Tensor, chords: torch.Tensor) -> torch.Tensor:
        a = traces / traces.norm(dim=-1, keepdim=True).clamp_min(1e-30)
        b = chords / chords.norm(dim=-1, keepdim=True)
        return (a @ b.conj().T).abs()


class SequenceMemory:
    """Named ideas, each with a sending and a receiving chord; the links live only in the medium.

    An idea's chords are computed from its name, so the brain can name any idea
    without keeping a table of meanings.  The list of names is the vocabulary
    the brain listens for; everything relational is the medium.  Chords are
    recomposed on demand and only a bounded working set is kept at hand.

    * ``link(a, b)`` plays a's sending chord with b's receiving chord.
    * ``forget(a, b)`` replays them in anti-phase: the cross imprint cancels.
    * ``predict`` / ``follow`` listen forward (or backward) through stored steps.
    * ``sleep`` rehearses the steps recalled since the last sleep, then rests.
      Rehearsed links grow; the rest fades every imprint equally, so what was
      used stands out over what was not.
    """

    SCHEMA = "cassifi.emergent-sequence-memory.v3"

    def __init__(self, codec: NoteCodec, *, salt: str = "cassi", write_steps: int = 1000,
                 alarm: float = 1e-3, working_bytes: int = 2 ** 31) -> None:
        self.codec, self.salt, self.write_steps, self.alarm = codec, salt, write_steps, alarm
        self.names: list[str] = []
        self.index: dict[str, int] = {}
        self.used: dict[tuple[str, str], int] = {}
        self._working: OrderedDict[tuple[str, str], torch.Tensor] = OrderedDict()
        row_bytes = codec.count * torch.empty((), dtype=codec.cplx).element_size()
        self._working_rows = max(64, working_bytes // row_bytes)
        # Steps the brain links in one play: two chords each, well within the working set.
        self.hand = self._working_rows // 4
        # The noise floor of an unlinked chord: |<trace, chord>| for a random unit chord.
        self.floor = math.sqrt(math.log(2.0) / codec.count)

    def _generator(self, name: str, role: str) -> torch.Generator:
        seed = int.from_bytes(hashlib.sha256(f"{self.salt}\x1f{role}\x1f{name}".encode()).digest()[:8], "little")
        return torch.Generator().manual_seed(seed & (2 ** 63 - 1))

    def ideas(self, names: Sequence[str]) -> list[int]:
        """Indices of ``names`` in the vocabulary, adding any the brain has not named before."""
        for n in names:
            if n not in self.index:
                self.index[n] = len(self.names)
                self.names.append(n)
        return [self.index[n] for n in names]

    def chords(self, role: str, names: Sequence[str]) -> torch.Tensor:
        """The ``role`` chords of ``names`` (rows), composing any not at hand in bounded slices."""
        self.ideas(names)
        rows = []
        for start in range(0, len(names), self._working_rows // 2):
            part = names[start:start + self._working_rows // 2]
            missing = [n for n in dict.fromkeys(part) if (role, n) not in self._working]
            if missing:
                made = self.codec.chords([self._generator(n, role) for n in missing])
                for n, chord in zip(missing, made):
                    self._working[(role, n)] = chord.clone()
            for n in part:
                self._working.move_to_end((role, n))
                rows.append(self._working[(role, n)])
            while len(self._working) > self._working_rows:
                self._working.popitem(last=False)
        return torch.stack(rows)

    def link(self, steps: Sequence[tuple[str, str]], sign: float = 1.0) -> None:
        """Play each step's sending chord with its receiving chord, every step at once."""
        for start in range(0, len(steps), self.hand):
            part = steps[start:start + self.hand]
            self.codec.write(self.chords("send", [a for a, _ in part]),
                             sign * self.chords("receive", [b for _, b in part]), self.write_steps)

    def forget(self, steps: Sequence[tuple[str, str]]) -> None:
        """Replay steps in anti-phase: their cross imprints cancel."""
        self.link(steps, -1.0)
        for step in steps:
            self.used.pop(step, None)

    def strength(self, trace: torch.Tensor, role: str, names: Sequence[str]) -> torch.Tensor:
        """|<trace, chord>| of every named chord, composed in bounded slices."""
        step = max(1, self._working_rows // 2)
        return torch.cat([(trace @ self.chords(role, names[i:i + step]).conj().T).abs()
                          for i in range(0, len(names), step)], dim=-1)

    def scores(self, cues: Sequence[str], backward: bool = False) -> tuple[torch.Tensor, torch.Tensor]:
        """(similarity, strength) of every known idea answering each cue."""
        played, heard = ("receive", "send") if backward else ("send", "receive")
        trace = self.codec.trace(self.chords(played, cues))
        strength = self.strength(trace, heard, list(self.names))
        return strength / trace.norm(dim=-1, keepdim=True).clamp_min(1e-30), strength

    def threshold(self, candidates: int) -> float:
        """Clarity an idea needs to be heard among ``candidates``.

        An unlinked chord's similarity has a Rayleigh spread with median
        ``floor``; exceeding z times it by chance has probability 2^-(z^2).  The
        threshold keeps the chance that any murmur is heard at ``alarm``.
        """
        return math.sqrt(math.log2(max(candidates, 1) / self.alarm))

    def heard(self, similarity: torch.Tensor) -> list[int]:
        """Ideas that stand clearly above the murmur."""
        loud = torch.nonzero(similarity > self.threshold(similarity.shape[-1]) * self.floor).flatten().tolist()
        return sorted(loud, key=lambda i: -float(similarity[i]))

    def predict(self, cues: list[str], backward: bool = False, top: int = 5) -> list[list[dict]]:
        """For each cue, the ideas the field answers with, loudest first."""
        sim, strength = self.scores(cues, backward)
        out = []
        for cue, s_row, k_row in zip(cues, sim, strength):
            row = []
            for i in self.heard(s_row)[:top]:
                name = self.names[i]
                row.append({"idea": name, "clarity": round(float(s_row[i]) / self.floor, 2),
                            "strength": float(k_row[i])})
                step = (name, cue) if backward else (cue, name)
                self.used[step] = self.used.get(step, 0) + 1
            out.append(row)
        return out

    def follow(self, start: str, depth: int, backward: bool = False) -> dict:
        """Play the train of thought from ``start``; forks branch, loops stop.  One listen per level."""
        root = {"idea": start, "next": []}
        frontier, seen = [root], {start}
        for _ in range(depth):
            if not frontier:
                break
            nxt = []
            answers = self.predict([node["idea"] for node in frontier], backward, top=8)
            for node, row in zip(frontier, answers):
                for hit in row:
                    child = {"idea": hit["idea"], "next": []}
                    node["next"].append(child)
                    if hit["idea"] not in seen:
                        seen.add(hit["idea"])
                        nxt.append(child)
            frontier = nxt
        return root

    def sleep(self, duration: float) -> dict:
        """Rehearse every step recalled since the last sleep, then rest for ``duration``."""
        rehearsed = sorted(self.used)
        self.link(rehearsed)
        self.used.clear()
        self.codec.field.rest(duration)
        return {"rehearsed": [list(s) for s in rehearsed],
                "faded_by": round(1.0 - math.exp(-self.codec.field.p.mu * duration), 6)}

    def state(self) -> dict[str, Any]:
        field = self.codec.field
        return {"schema": self.SCHEMA, "profile": asdict(field.p), "t": field.t, "imprint": field.imprint.cpu(),
                "read_steps": self.codec.read_steps, "salt": self.salt,
                "write_steps": self.write_steps, "alarm": self.alarm, "names": list(self.names),
                "used": [[a, b, n] for (a, b), n in self.used.items()]}

    @classmethod
    def from_state(cls, raw: Mapping[str, Any], device: str = "cpu") -> "SequenceMemory":
        if raw.get("schema") != cls.SCHEMA:
            raise ValueError("not an emergent sequence memory")
        field = EmergentField(EmergentProfile(**{**raw["profile"], "device": device}))
        field.t = raw["t"]
        field.imprint = raw["imprint"].to(device)
        memory = cls(NoteCodec(field, read_steps=raw["read_steps"]), salt=raw["salt"],
                     write_steps=raw["write_steps"], alarm=raw["alarm"])
        memory.ideas(list(raw["names"]))
        memory.used = {(a, b): n for a, b, n in raw["used"]}
        return memory

    def save(self, path: Path) -> None:
        _atomic_save(self.state(), path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> "SequenceMemory":
        return cls.from_state(torch.load(path, map_location=device), device)

    @classmethod
    def create(cls, profile: EmergentProfile, **kwargs: Any) -> "SequenceMemory":
        return cls(NoteCodec(EmergentField(profile)), **kwargs)


def _atomic_save(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".partial")
    torch.save(dict(payload), scratch)
    os.replace(scratch, path)


class TemporalMedium:
    """An owner temporal memory's experience, held in the emergent medium.

    Every step of every admitted episode becomes one link: the context in which
    an action was taken points to the observation that followed.  The context
    is one chord made of nested voices, equally loud: the action alone, the
    action after the last step, after the last two steps, and so on to
    ``depth``.  Two contexts share exactly the voices of the history they have
    in common.

    To recall, the brain plays one voice at a time, the most specific first,
    and trusts the most specific voice the medium answers.  An exact repeat
    answers through its deepest voice; a new situation falls back to the
    experiences that share the most recent history with it.  Playing a voice
    alone hears every link that contains it at full strength, so even the
    faint general memories come back clearly.

    ``sync`` makes the medium's imprints match the admitted evidence exactly:
    new steps are linked, and steps whose evidence was revoked are replayed in
    anti-phase, which erases them from the medium, rehearsals included.

    ``sleep`` is rest with replay.  Every experience the medium recognised
    while predicting since the last sleep is played once more, and then the
    medium rests in silence, which fades every imprint by the same factor.
    Experiences that were used grow relative to those that were not.

    ``choose`` plays every candidate action at once, lets the medium imagine
    the outcomes, plays the imagined futures again, and acts on the action
    whose futures carry the goal loudest.  When no goal is heard, it takes the
    action the medium knows least about: the one answered only by its most
    general memories, or not at all.
    """

    SCHEMA = "cassifi.emergent-temporal-medium.v3"
    START = ("^", "^")

    def __init__(self, memory: SequenceMemory, *, depth: int = 4) -> None:
        self.memory, self.depth = memory, depth
        self.absorbed: Counter[str] = Counter()
        self.recognised: Counter[str] = Counter()
        self.rehearsed: Counter[str] = Counter()
        # What each voice was last heard to answer, valid until the medium or its outcomes change.
        self._answers: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
        self._answer_outcomes: list[str] = []
        self._spoken: set[str] = set()

    def _voices(self, history: Sequence[Mapping[str, str]], action: str) -> list[str]:
        steps = [self.START] * self.depth + [(s["action"], s["observation"]) for s in history]
        recent = steps[len(steps) - self.depth:]
        return [f"do:{action}|" + "|".join(f"{a}>{o}" for a, o in recent[self.depth - k:])
                for k in range(self.depth + 1)]

    def _cue(self, voices: Sequence[str]) -> torch.Tensor:
        cue = self.memory.chords("send", voices).sum(0)
        return cue / cue.norm()

    def transitions(self, episode: Sequence[Mapping[str, str]]) -> list[str]:
        return [json.dumps([self._voices(episode[:t], step["action"]), step["observation"]])
                for t, step in enumerate(episode)]

    def _write(self, keys: Sequence[str], sign: float) -> None:
        """Play every key's context cue with its observation's receiving chord, all keys at once."""
        if not keys:
            return
        self._answers.clear()
        hand = self.memory.hand
        for start in range(0, len(keys), hand):
            part = [json.loads(key) for key in keys[start:start + hand]]
            cues = torch.stack([self._cue(voices) for voices, _ in part])
            answers = self.memory.chords("receive", [f"see:{observation}" for _, observation in part])
            self.memory.codec.write(cues, sign * answers, self.memory.write_steps)

    def _hear(self, voices: Sequence[str], outcomes: list[str]) -> tuple[torch.Tensor, torch.Tensor]:
        """(strength, clarity) of every outcome answering each voice; voices already heard are not replayed."""
        if outcomes != self._answer_outcomes:
            self._answers.clear()
            self._answer_outcomes = list(outcomes)
        new = [v for v in dict.fromkeys(voices) if v not in self._answers]
        if new:
            trace = self.memory.codec.trace(self.memory.chords("send", new))
            strength = self.memory.strength(trace, "receive", outcomes)
            clarity = strength / trace.norm(dim=-1, keepdim=True).clamp_min(1e-30) / self.memory.floor
            self._answers.update(zip(new, zip(strength, clarity)))
        rows = [self._answers[v] for v in voices]
        return torch.stack([r[0] for r in rows]), torch.stack([r[1] for r in rows])

    def sync(self, episodes: Sequence[Sequence[Mapping[str, str]]]) -> dict[str, int]:
        """Link every admitted step not yet in the medium; erase every step no longer admitted."""
        want = Counter(key for episode in episodes for key in self.transitions(episode))
        add, drop = want - self.absorbed, self.absorbed - want
        gone = {key: self.rehearsed.pop(key) for key in list(self.rehearsed) if not want[key]}
        for key in gone:
            self.recognised.pop(key, None)
        self._write([key for key, count in sorted((drop + Counter(gone)).items()) for _ in range(count)], -1.0)
        self._write([key for key, count in sorted(add.items()) for _ in range(count)], 1.0)
        self.absorbed = want
        self._spoken = {voice for key in want for voice in json.loads(key)[0]}
        return {"linked": sum(add.values()), "erased": sum(drop.values()) + sum(gone.values()),
                "steps": sum(want.values())}

    def predict_batch(self, queries: Sequence[tuple[Sequence[Mapping[str, str]], str]],
                      record: bool = True) -> list[dict[str, Any]]:
        """What the medium expects each (history, action) to produce, and how well it knows.

        Every voice of every query is played, one listen per depth.  A voice
        that answers adds its outcomes with weight 4^k, so each step of shared
        history counts four times more than the one before it.  A voice that
        stays silent adds the same weight to not knowing.  ``confidence`` is
        the known share; ``distribution`` spreads it over the outcomes.  A
        voice the brain never played into the medium cannot answer and is not
        played; voices heard since the medium last changed are not replayed.
        """
        out: list[dict[str, Any]] = [{"action": a, "supported": False, "observation": None, "depth": -1,
                                      "confidence": 0.0, "clarity": 0.0, "distribution": {}} for _, a in queries]
        outcomes = sorted(n for n in self.memory.names if n.startswith("see:"))
        if not outcomes:
            return out
        voice_sets = [self._voices(h, a) for h, a in queries]
        bar = self.memory.threshold(len(outcomes) * (self.depth + 1))
        weights = [4.0 ** k for k in range(self.depth + 1)]
        blend = torch.zeros(len(queries), len(outcomes), dtype=torch.float64)
        clarity_at = torch.zeros(len(queries), len(outcomes), dtype=torch.float64)
        deepest = [-1] * len(queries)
        for k in range(self.depth + 1):
            playable = [q for q in range(len(queries)) if voice_sets[q][k] in self._spoken]
            if not playable:
                continue
            strength, clarity = self._hear([voice_sets[q][k] for q in playable], outcomes)
            loud = clarity > bar
            share = torch.where(loud, strength, torch.zeros_like(strength)).double().cpu()
            answered = loud.any(dim=-1).cpu()
            rows = torch.tensor(playable)[answered]
            blend[rows] += weights[k] * share[answered] / share[answered].sum(-1, keepdim=True)
            clarity_at[rows] = clarity.double().cpu()[answered]
            for q in rows.tolist():
                deepest[q] = k
        total = sum(weights)
        for q, (history, action) in enumerate(queries):
            if deepest[q] < 0:
                continue
            known = float(blend[q].sum())
            best = int(torch.argmax(blend[q]))
            observation = outcomes[best][4:]
            if record and deepest[q] == self.depth:
                key = json.dumps([voice_sets[q], observation])
                if self.absorbed[key]:
                    self.recognised[key] += 1
            out[q].update({
                "supported": True, "observation": observation, "depth": deepest[q],
                "confidence": round(known / total, 4), "clarity": round(float(clarity_at[q, best]), 2),
                "distribution": {outcomes[i][4:]: round(float(blend[q, i]) / known, 4)
                                 for i in torch.nonzero(blend[q]).flatten().tolist()},
            })
        return out

    def predict(self, history: Sequence[Mapping[str, str]], actions: Sequence[str]) -> list[dict[str, Any]]:
        return self.predict_batch([(history, a) for a in actions])

    def _imagine(self, histories: list[list[Mapping[str, str]]], reach: list[float], actions: Sequence[str],
                 goals: set[str], avoid: set[str], depth: int, discount: float, beam: int,
                 record: bool) -> list[list[dict[str, Any]]]:
        """Value of every action after every history: goal loudness now plus imagined futures.

        What the medium does not know is worth nothing, so a future counts in
        proportion to the confidence it is imagined with.  Only the ``beam``
        futures most likely to be reached are imagined further.
        """
        preds = self.predict_batch([(h, a) for h in histories for a in actions], record=record)
        rows = [preds[i * len(actions):(i + 1) * len(actions)] for i in range(len(histories))]
        futures: list[tuple[int, int, float, float, list[Mapping[str, str]]]] = []
        for hi, row in enumerate(rows):
            for ai, pred in enumerate(row):
                chance = {obs: pred["confidence"] * share for obs, share in pred["distribution"].items()}
                pred["value"] = sum(p * ((obs in goals) - (obs in avoid)) for obs, p in chance.items())
                if depth > 1:
                    for obs, p in chance.items():
                        if obs not in goals and obs not in avoid:
                            futures.append((hi, ai, p, reach[hi] * p,
                                            [*histories[hi], {"action": pred["action"], "observation": obs}]))
        futures = sorted(futures, key=lambda f: -f[3])[:beam]
        if futures:
            later = self._imagine([f[4] for f in futures], [f[3] for f in futures], actions, goals, avoid,
                                  depth - 1, discount, beam, False)
            for (hi, ai, share, _, _), options in zip(futures, later):
                rows[hi][ai]["value"] += discount * share * max(o["value"] for o in options)
        return rows

    def choose(self, history: Sequence[Mapping[str, str]], actions: Sequence[str], *,
               goals: Sequence[str] = (), avoid: Sequence[str] = (), depth: int = 5,
               discount: float = 0.7, beam: int = 16) -> dict[str, Any]:
        """Act on the action whose imagined futures carry the goal loudest (see class notes)."""
        if not actions:
            raise ValueError("choose needs at least one action")
        rows = self._imagine([list(history)], [1.0], actions, set(goals), set(avoid), depth, discount, beam, True)[0]
        best = max(rows, key=lambda r: r["value"])
        if best["value"] > 0.0:
            reason = "goal"
        else:
            safe = [r for r in rows if r["value"] >= 0.0] or rows
            best, reason = min(safe, key=lambda r: r["confidence"]), "curiosity"
        return {"action": best["action"], "reason": reason,
                "candidates": [{k: r[k] for k in ("action", "value", "observation", "depth", "confidence",
                                                  "distribution")} for r in rows]}

    def sleep(self, duration: float) -> dict[str, Any]:
        """Replay each recognised experience once, then rest in silence for ``duration``."""
        replayed = sorted(self.recognised)
        self._write(replayed, 1.0)
        for key in replayed:
            self.rehearsed[key] += 1
        self.recognised.clear()
        self.memory.codec.field.rest(duration)
        self._answers.clear()
        return {"replayed": len(replayed),
                "faded_by": round(1.0 - math.exp(-self.memory.codec.field.p.mu * duration), 6)}

    def save(self, path: Path) -> None:
        _atomic_save({**self.memory.state(), "medium_schema": self.SCHEMA, "depth": self.depth,
                      "absorbed": dict(self.absorbed), "recognised": dict(self.recognised),
                      "rehearsed": dict(self.rehearsed)}, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> "TemporalMedium":
        raw = torch.load(path, map_location=device)
        if raw.get("medium_schema") != cls.SCHEMA:
            raise ValueError(f"{path} is not an emergent temporal medium")
        medium = cls(SequenceMemory.from_state(raw, device), depth=raw["depth"])
        medium.absorbed = Counter(raw["absorbed"])
        medium.recognised = Counter(raw["recognised"])
        medium.rehearsed = Counter(raw["rehearsed"])
        medium._spoken = {voice for key in medium.absorbed for voice in json.loads(key)[0]}
        return medium


def _paths(tree: dict) -> list[list[str]]:
    if not tree["next"]:
        return [[tree["idea"]]]
    return [[tree["idea"], *rest] for child in tree["next"] for rest in _paths(child)]


def episode(out: Path, sequences: int, length: int, rest_steps: int,
            profile: EmergentProfile = EmergentProfile(), seed: int = 7) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    memory = SequenceMemory.create(profile, salt=f"episode-{seed}")
    field, codec = memory.codec.field, memory.codec
    # Disjoint sequences, plus a branch that leaves the first one halfway.
    seqs = [[str(i) for i in range(k * length, (k + 1) * length)] for k in range(sequences)]
    fork_at = seqs[0][length // 2]
    branch = [fork_at, *(str(i) for i in range(sequences * length, sequences * length + length // 2))]
    ideas = sequences * length + length // 2
    memory.ideas([str(i) for i in range(ideas)])
    links = [(s[i], s[i + 1]) for s in [*seqs, branch] for i in range(len(s) - 1)]
    memory.link(links)
    field.rest(rest_steps * profile.dt)
    t_write = time.perf_counter()

    table, _ = memory.scores(memory.names)
    truth = torch.zeros_like(table, dtype=torch.bool)
    for a, b in links:
        truth[memory.index[a], memory.index[b]] = True
    detected = torch.zeros_like(truth)
    for a in range(ideas):
        detected[a, memory.heard(table[a])] = True
    true_scores, murmur = table[truth], table[~truth]

    trains = []
    for s in seqs:
        forward = _paths(memory.follow(s[0], length + 2))
        expected = [s] if s[0] != seqs[0][0] else [s, seqs[0][:length // 2] + branch]
        back = _paths(memory.follow(s[-1], length + 2, backward=True))
        trains.append({"start": s[0], "forward_paths": forward,
                       "forward_exact": sorted(forward) == sorted(expected),
                       "backward_paths": back, "backward_exact": back == [s[::-1]]})
    report = {
        "profile": asdict(profile), "notes": codec.count, "ideas": ideas, "links": len(links),
        "links_detected": int((detected & truth).sum()), "false_links": int((detected & ~truth).sum()),
        "silent_endings": sum(int(not detected[memory.index[s[-1]]].any()) for s in [*seqs[1:], branch]),
        "endings": len(seqs),
        "score": {"stored_min": round(float(true_scores.min()), 4), "stored_mean": round(float(true_scores.mean()), 4),
                  "murmur_max": round(float(murmur.max()), 4), "murmur_median": round(float(murmur.median()), 4)},
        "trains_forward_exact": sum(t["forward_exact"] for t in trains),
        "trains_backward_exact": sum(t["backward_exact"] for t in trains),
        "trains": trains,
        "medium": {"mean": round(float(field.rho.mean()), 4), "max": round(float(field.rho.max()), 4)},
        "seconds": {"write": round(t_write - t0, 1), "read": round(time.perf_counter() - t_write, 1)},
    }
    memory.save(out / "emergent_memory.pt")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
        rho = field.rho.float().cpu()
        axes[0].imshow((rho if profile.dims == 2 else rho[profile.size // 2]).numpy(), cmap="magma")
        axes[0].set_title("medium (middle slice)")
        axes[0].axis("off")
        axes[1].imshow(table.float().cpu().numpy(), cmap="viridis")
        axes[1].set_xlabel("idea heard")
        axes[1].set_ylabel("idea played")
        axes[1].set_title(f"{len(links)} stored steps among {ideas} ideas")
        fig.savefig(out / "emergent_memory.png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        report["image"] = str(out / "emergent_memory.png")
    except ImportError:
        pass
    (out / "emergent_episode.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("_diag") / "emergent")
    ap.add_argument("--sequences", type=int, default=6)
    ap.add_argument("--length", type=int, default=10)
    ap.add_argument("--rest-steps", type=int, default=3000)
    ap.add_argument("--dims", type=int, default=3)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--dtype", default="float32", choices=("float32", "float64"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    profile = replace(EmergentProfile(), dims=a.dims, size=a.size, dtype=a.dtype, device=a.device)
    r = episode(a.out, a.sequences, a.length, a.rest_steps, profile)
    print(json.dumps({k: v for k, v in r.items() if k not in ("profile", "trains")}, indent=1))


if __name__ == "__main__":
    main()
