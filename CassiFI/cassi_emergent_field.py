"""Emergent two-fluid field memory, written and read as the field's own notes.

The field holds the memory; the brain is a mathematical machine that encodes
into the field and decodes out of it.

Field.  The canonical Yang/Yin pair runs on a medium whose density ``rho``
belongs to the field itself:

    rho Y'' = lap Y - w^2 (Y - phi I) - rho gamma Y' + drive
    rho I'' = lap I + w^2 (Y - phi I) - rho gamma I'

Where Qi intensity gathers the medium thickens, and it relaxes without it:

    rho' = eta * <S^2> / (<S^2> + I_half) * (rho_max - rho) - mu * (rho - 1),   S = Y + I

The two fluids split exactly into a coherent part ``S = Y + I`` (a pure wave,
where Yang and Yin move together) and an incoherent part ``eps = Y - phi I``
(a wave with a mass gap).  On a blank medium the coherent part has natural
standing patterns, the field's notes: psi_kl = cos(pi k (y+1/2)/n) cos(pi l (x+1/2)/n).
Notes never mix on their own.  Nothing else is coded.

Brain.  An idea is a note.  To store a link, the brain plays two notes
together at one shared pitch, so their overlap stays in step and the medium
keeps it as a lasting imprint shaped like psi_a * psi_b.  To recall, the brain
plays one note alone, subtracts what blank physics returns for it (the brain
knows the laws, so this is exact), and listens for which other note now
sounds: the medium has made the two strings sympathetic.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import torch

PHI = (1.0 + math.sqrt(5.0)) / 2.0
STATE = ("Y", "I", "vY", "vI", "rho", "S2")


@dataclass(frozen=True)
class EmergentProfile:
    size: int = 64
    dt: float = 0.25
    omega2: float = 1.0
    gamma: float = 0.01
    pitch: float = 2.0
    eta: float = 0.005
    intensity_tau: float = 100.0
    intensity_half: float = 1000.0
    rho_max: float = 3.0
    mu: float = 0.00001
    device: str = "cpu"


class EmergentField:
    """One continuing field; its entire adaptive state is the tensors in ``STATE``."""

    def __init__(self, profile: EmergentProfile = EmergentProfile()) -> None:
        self.p = profile
        n, dev = profile.size, torch.device(profile.device)
        for name in STATE:
            setattr(self, name, torch.zeros((n, n), dtype=torch.float64, device=dev))
        self.rho += 1.0
        self.t = 0.0

    @staticmethod
    def _lap(S: torch.Tensor) -> torch.Tensor:
        out = torch.zeros_like(S)
        fx = S[:, 1:] - S[:, :-1]
        fy = S[1:, :] - S[:-1, :]
        out[:, :-1] += fx
        out[:, 1:] -= fx
        out[:-1, :] += fy
        out[1:, :] -= fy
        return out

    def step(self, steps: int, drive: torch.Tensor | None = None, plastic: bool = True,
             listen_from: int | None = None) -> torch.Tensor | None:
        """Advance the field under a drive pattern played at the shared pitch.

        ``drive`` is a real spatial pattern.  With ``listen_from`` set, returns
        the complex coherent field ``<S e^{-i pitch t}>`` heard over steps
        ``>= listen_from``.  With ``plastic=False`` the medium is read without
        being imprinted.
        """
        p, dt, w = self.p, self.p.dt, self.p.pitch
        heard = torch.zeros_like(self.Y, dtype=torch.complex128) if listen_from is not None else None
        for i in range(steps):
            eps = self.Y - PHI * self.I
            force = self._lap(self.Y) - p.omega2 * eps
            if drive is not None:
                force = force + drive * math.sin(w * self.t)
            self.vY += dt * (force / self.rho - p.gamma * self.vY)
            self.vI += dt * ((self._lap(self.I) + p.omega2 * eps) / self.rho - p.gamma * self.vI)
            self.Y += dt * self.vY
            self.I += dt * self.vI
            self.t += dt
            if plastic:
                self.S2 += (dt / p.intensity_tau) * ((self.Y + self.I) ** 2 - self.S2)
                self.rho += dt * (p.eta * self.S2 / (self.S2 + p.intensity_half) * (p.rho_max - self.rho)
                                  - p.mu * (self.rho - 1.0))
            if heard is not None and i >= listen_from:
                heard += (self.Y + self.I) * complex(math.cos(w * self.t), -math.sin(w * self.t))
        if heard is None:
            return None
        return heard * (2.0 / max(1, steps - listen_from))

    def calm(self) -> None:
        """Let the fast field fall silent; the medium keeps what it holds."""
        for name in ("Y", "I", "vY", "vI", "S2"):
            getattr(self, name).zero_()

    def save(self, path: Path) -> None:
        torch.save({"profile": asdict(self.p), "t": self.t,
                    **{k: getattr(self, k).cpu() for k in STATE}}, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> "EmergentField":
        raw = torch.load(path, map_location=device)
        field = cls(EmergentProfile(**{**raw["profile"], "device": device}))
        field.t = raw["t"]
        for k in STATE:
            setattr(field, k, raw[k].to(device))
        return field


class NoteCodec:
    """The brain's side: ideas are the field's notes; links live in the medium."""

    def __init__(self, field: EmergentField, notes: list[tuple[int, int]], read_steps: int = 2400) -> None:
        p = field.p
        n = p.size
        coord = (torch.arange(n, dtype=torch.float64, device=field.Y.device) + 0.5) / n
        self.field, self.notes, self.read_steps = field, notes, read_steps
        self.shapes = torch.stack([torch.outer(torch.cos(math.pi * k * coord), torch.cos(math.pi * l * coord))
                                   for k, l in notes])
        self.shapes /= self.shapes.pow(2).sum(dim=(1, 2), keepdim=True).sqrt()
        tone = lambda k: 2.0 - 2.0 * math.cos(math.pi * k / n)
        self.stiffness = torch.tensor([tone(k) + tone(l) for k, l in notes], dtype=torch.float64,
                                      device=field.Y.device)
        if float(self.stiffness.max()) >= p.pitch ** 2:
            raise ValueError("every note must sit below the shared pitch")
        # Pre-compensation: each note, played alone, answers with amplitude ``n``.
        self.detune = torch.abs(p.pitch ** 2 - self.stiffness)
        self.gain = self.detune * n
        self._physics: dict[int, torch.Tensor] = {}

    def pattern(self, *index: int) -> torch.Tensor:
        return sum(self.gain[i] * self.shapes[i] for i in index)

    def write(self, a: int, b: int, steps: int) -> None:
        """Play notes ``a`` and ``b`` together; the medium keeps their overlap."""
        self.field.step(steps, self.pattern(a, b))
        self.field.calm()

    def _hear(self, field: EmergentField, a: int) -> torch.Tensor:
        field.calm()
        heard = field.step(self.read_steps, self.pattern(a), plastic=False, listen_from=self.read_steps // 2)
        field.calm()
        # Undo each note's own response factor: what remains is the coupling into it.
        return torch.einsum("kyx,yx->k", self.shapes.to(heard.dtype), heard) * self.detune / field.p.size

    def recall(self, a: int) -> torch.Tensor:
        """How strongly every note sounds when ``a`` is played, beyond blank physics."""
        if a not in self._physics:
            self._physics[a] = self._hear(EmergentField(self.field.p), a)
        return (self._hear(self.field, a) - self._physics[a]).abs()


def _plus_minus(a: int, b: int) -> tuple[int, int]:
    return abs(a + b), abs(a - b)


def _crosstalk_free(notes: list[tuple[int, int]]) -> bool:
    """True when no imprint can make a note sound another note except its own link.

    An imprint left by notes c and d has wavenumbers (k_c +- k_d, l_c +- l_d);
    it scatters a played note a to (k_a +- those, l_a +- those).  Allowed hits
    are only the link partner (a = c gives d).
    """
    known = set(notes)
    for a in notes:
        for c, d in itertools.combinations_with_replacement(notes, 2):
            for wk in _plus_minus(c[0], d[0]):
                for wl in _plus_minus(c[1], d[1]):
                    for mk in _plus_minus(a[0], wk):
                        for ml in _plus_minus(a[1], wl):
                            m = (mk, ml)
                            if m == a or m not in known:
                                continue
                            if (a == c and m == d) or (a == d and m == c):
                                continue
                            return False
    return True


def note_codebook(size: int, pitch: float, top: int, tries: int = 60) -> list[tuple[int, int]]:
    """The largest crosstalk-free set of notes the brain can find below the pitch."""
    tone = lambda k: 2.0 - 2.0 * math.cos(math.pi * k / size)
    if 3 * top >= size:
        raise ValueError("notes up to `top` would alias on this grid")
    pool = [(k, l) for k in range(1, top + 1) for l in range(1, top + 1) if tone(k) + tone(l) < 0.8 * pitch ** 2]
    best: list[tuple[int, int]] = []
    for seed in range(tries):
        order = pool[:]
        random.Random(seed).shuffle(order)
        chosen: list[tuple[int, int]] = []
        for note in order:
            if _crosstalk_free(chosen + [note]):
                chosen.append(note)
        if len(chosen) > len(best):
            best = chosen
    return sorted(best)


def episode(out: Path, pairs: int, learn_steps: int, rest_steps: int,
            profile: EmergentProfile = EmergentProfile(), top: int = 20, seed: int = 7) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    field = EmergentField(profile)
    notes = note_codebook(profile.size, profile.pitch, top)
    if 2 * pairs + 2 > len(notes):
        raise ValueError("not enough notes for the requested pairs")
    codec = NoteCodec(field, notes)
    g = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(notes), generator=g).tolist()
    links = [(order[2 * i], order[2 * i + 1]) for i in range(pairs)]
    strangers = order[2 * pairs:2 * pairs + 2]
    t0 = time.perf_counter()
    for a, b in links:
        codec.write(a, b, learn_steps)
    field.step(rest_steps)
    field.calm()
    trials = []
    for cue, answer in [*links, *[(b, a) for a, b in links], *[(s, None) for s in strangers]]:
        heard = codec.recall(cue)
        heard[cue] = 0.0
        ranked = torch.argsort(heard, descending=True).tolist()
        others = torch.cat([heard[:ranked[0]], heard[ranked[0] + 1:]])
        others = others[others > 0]
        trials.append({
            "cue": notes[cue], "stored_answer": None if answer is None else notes[answer],
            "heard": notes[ranked[0]],
            "clarity": round(float(heard[ranked[0]] / others.mean().clamp_min(1e-30)), 2),
            "strength": float(f"{float(heard[ranked[0]]):.3g}"),
        })
    stored = [t for t in trials if t["stored_answer"] is not None]
    report = {
        "profile": asdict(profile), "notes": len(notes), "links": [(notes[a], notes[b]) for a, b in links],
        "recalled": sum(t["heard"] == t["stored_answer"] for t in stored), "of": len(stored),
        "chance": round(1.0 / (len(notes) - 1), 3),
        "trials": trials,
        "medium": {"mean": round(float(field.rho.mean()), 4), "max": round(float(field.rho.max()), 4)},
        "seconds": round(time.perf_counter() - t0, 1),
    }
    field.save(out / "emergent_field.pt")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(4.6, 4.6))
        ax.imshow(field.rho.cpu().numpy(), cmap="magma")
        ax.set_title(f"medium holding {pairs} linked note pairs")
        ax.axis("off")
        fig.savefig(out / "emergent_medium.png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        report["image"] = str(out / "emergent_medium.png")
    except ImportError:
        pass
    (out / "emergent_episode.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("_diag") / "emergent")
    ap.add_argument("--pairs", type=int, default=4)
    ap.add_argument("--learn-steps", type=int, default=6000)
    ap.add_argument("--rest-steps", type=int, default=3000)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    r = episode(a.out, a.pairs, a.learn_steps, a.rest_steps, replace(EmergentProfile(), size=a.size, device=a.device), top=a.top)
    print(json.dumps({k: r[k] for k in ("notes", "recalled", "of", "chance", "trials", "medium", "seconds")},
                     indent=1))


if __name__ == "__main__":
    main()
