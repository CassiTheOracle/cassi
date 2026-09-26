"""Emergent two-fluid field memory: a large vocabulary of chords and sequences.

The field holds the memory; the brain is a mathematical machine that encodes
into the field and decodes out of it.

Field.  The canonical Yang/Yin pair runs on a medium whose density ``rho``
belongs to the field itself:

    rho (Y'' + gamma Y') = lap Y - w^2 (Y - phi I) + drive
    rho (I'' + gamma I') = lap I + w^2 (Y - phi I)

Where Qi intensity gathers the medium thickens, and it relaxes without it:

    rho' = eta * <S^2> / (<S^2> + I_half) * (rho_max - rho) - mu * (rho - 1),   S = Y + I

On a blank medium the field's standing waves (its notes) are exact and never
mix: psi_k = prod_axis cos(pi k_axis (x_axis + 1/2) / n).  Nothing else is coded.

Brain.  An idea is a chord: a blend of every note below the shared pitch with
random phases, shaped so its brightness |S(x)|^2 is nearly even across the
field.  Two chords A and B played together at one pitch leave
|A|^2 + |B|^2 + 2 Re(A conj B) in the medium; the even self terms only retune
each note in place, so the imprint that couples notes is the link itself.
The medium couples notes through K_km = integral (rho - 1) psi_k psi_m, and K
is the memory.

To read, the brain bows a chord (a smooth swell, so the field does not ring),
listens to both fluids note by note, and inverts the known physics exactly:
it subtracts the blank response and undoes each note's own 2x2 Yang/Yin
transfer, both measured once on a blank field like tuning an instrument.
What remains is K applied to the chord, which carries |A|^2 B = B for a
stored link.  Random chords are nearly orthogonal, so decoding is a
correlation against the chords the brain can name, and capacity grows with
the number of notes, i.e. with the field's volume.

Sequences.  Each idea owns two chords, one it sends with and one it receives
with.  A step a -> b is stored by playing a's sending chord with b's receiving
chord.  The medium's coupling is symmetric, yet the pairing gives direction:
playing a's sending chord answers with b, and playing b's receiving chord
answers with a, so a train of thought runs forward and can be traced back.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import torch

PHI = (1.0 + math.sqrt(5.0)) / 2.0
STATE = ("Y", "I", "vY", "vI", "rho", "S2")


@dataclass(frozen=True)
class EmergentProfile:
    dims: int = 3
    size: int = 64
    dt: float = 0.25
    omega2: float = 1.0
    gamma: float = 0.01
    pitch: float = 2.0
    eta: float = 0.0002
    intensity_tau: float = 100.0
    intensity_half: float = 1000.0
    rho_max: float = 3.0
    mu: float = 0.000001
    onset: float = 50.0
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


class EmergentField:
    """One continuing field; its entire adaptive state is the tensors in ``STATE``."""

    def __init__(self, profile: EmergentProfile = EmergentProfile()) -> None:
        self.p = profile
        shape, dev = (profile.size,) * profile.dims, torch.device(profile.device)
        for name in STATE:
            setattr(self, name, torch.zeros(shape, dtype=torch.float64, device=dev))
        self.rho += 1.0
        self.t = 0.0

    def step(self, steps: int, drive: torch.Tensor | None = None, plastic: bool = True) -> None:
        """Advance the live field under a complex phasor drive ``D`` (physical drive Re(D e^{i w t}))."""
        p, dt, w, d = self.p, self.p.dt, self.p.pitch, self.p.dims
        Y, I, vY, vI = (x.unsqueeze(0) for x in (self.Y, self.I, self.vY, self.vI))
        for i in range(steps):
            eps = Y - PHI * I
            force = _lap(Y, d) - p.omega2 * eps
            if drive is not None:
                env = _envelope(i * dt, p.onset)
                force = force + env * (drive.real * math.cos(w * self.t) - drive.imag * math.sin(w * self.t))
            vY += dt * (force / self.rho - p.gamma * vY)
            vI += dt * ((_lap(I, d) + p.omega2 * eps) / self.rho - p.gamma * vI)
            Y += dt * vY
            I += dt * vI
            self.t += dt
            if plastic:
                S = (Y + I)[0]
                self.S2 += (dt / p.intensity_tau) * (S * S - self.S2)
                self.rho += dt * (p.eta * self.S2 / (self.S2 + p.intensity_half) * (p.rho_max - self.rho)
                                  - p.mu * (self.rho - 1.0))

    def listen(self, drive_Y: torch.Tensor, drive_I: torch.Tensor | None, steps: int,
               rho: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        """Play a batch of phasor drives on a quiet copy of the fast field and demodulate.

        The medium is only read.  Every play starts from rest at local time 0,
        so identical drives give identical answers.  Returns the complex
        Yang and Yin amplitudes heard over the second half of the play.
        """
        p, dt, w, d = self.p, self.p.dt, self.p.pitch, self.p.dims
        rho = self.rho if rho is None else rho
        Y = torch.zeros(drive_Y.shape, dtype=torch.float64, device=drive_Y.device)
        I, vY, vI = torch.zeros_like(Y), torch.zeros_like(Y), torch.zeros_like(Y)
        hY = torch.zeros_like(drive_Y, dtype=torch.complex128)
        hI = torch.zeros_like(hY)
        start, t = steps // 2, 0.0
        for i in range(steps):
            c, s = (_envelope(t, p.onset) * x for x in (math.cos(w * t), math.sin(w * t)))
            eps = Y - PHI * I
            fY = _lap(Y, d) - p.omega2 * eps + drive_Y.real * c - drive_Y.imag * s
            fI = _lap(I, d) + p.omega2 * eps
            if drive_I is not None:
                fI = fI + drive_I.real * c - drive_I.imag * s
            vY += dt * (fY / rho - p.gamma * vY)
            vI += dt * (fI / rho - p.gamma * vI)
            Y += dt * vY
            I += dt * vI
            t += dt
            if i >= start:
                phase = complex(math.cos(w * t), -math.sin(w * t))
                hY += Y * phase
                hI += I * phase
        scale = 2.0 / (steps - start)
        return hY * scale, hI * scale

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
    """The brain's instrument: notes below the pitch, chords over them, exact decoding."""

    def __init__(self, field: EmergentField, top: int, read_steps: int = 800,
                 batch_cells: int = 24_000_000) -> None:
        p = field.p
        n, dev = p.size, field.Y.device
        if 3 * top >= n:
            raise ValueError("notes up to `top` would alias on this grid")
        self.field, self.read_steps = field, read_steps
        self.batch = max(1, batch_cells // n ** p.dims)
        tone = lambda k: 2.0 - 2.0 * math.cos(math.pi * k / n)
        w2, g = p.pitch ** 2, p.gamma * p.pitch
        notes = []
        for k in itertools.product(range(1, top + 1), repeat=p.dims):
            lam = sum(tone(x) for x in k)
            det = complex(-w2 + lam + p.omega2, g) * complex(-w2 + lam + p.omega2 * PHI, g) - p.omega2 ** 2 * PHI
            # Keep notes below the pitch and away from the Yin-branch resonance.
            if lam < 0.8 * w2 and abs(complex(-w2 + lam + p.omega2 * PHI, g) / det) < 1.5:
                notes.append(k)
        self.notes = notes
        self.index = torch.tensor(notes, dtype=torch.long, device=dev) - 1
        coord = (torch.arange(n, dtype=torch.float64, device=dev) + 0.5) / n
        basis = torch.stack([torch.cos(math.pi * k * coord) for k in range(1, top + 1)], dim=1)
        self.basis = (basis / basis.norm(dim=0, keepdim=True)).to(torch.complex128)   # (n, top)
        self.volume = float(n ** p.dims) ** 0.5
        self._calibrate()

    # -- spectral transforms -------------------------------------------------
    def to_grid(self, amps: torch.Tensor) -> torch.Tensor:
        """Note amplitudes (B, notes) -> field pattern (B, *grid)."""
        top = self.basis.shape[1]
        spec = torch.zeros((amps.shape[0],) + (top,) * self.field.p.dims, dtype=torch.complex128,
                           device=amps.device)
        spec[(slice(None),) + tuple(self.index.T)] = amps
        for axis in range(self.field.p.dims):
            spec = torch.tensordot(spec, self.basis, dims=([1], [1]))    # rolls the axis to the end
        return spec

    def to_notes(self, grid: torch.Tensor) -> torch.Tensor:
        """Field pattern (B, *grid) -> note amplitudes (B, notes)."""
        spec = grid
        for axis in range(self.field.p.dims):
            spec = torch.tensordot(spec, self.basis, dims=([1], [0]))
        return spec[(slice(None),) + tuple(self.index.T)]

    # -- tuning --------------------------------------------------------------
    def _calibrate(self) -> None:
        """Tune the instrument on a blank medium: every note at once, at two phases.

        ``T`` is each note's 2x2 Yang/Yin transfer.  ``quad`` is the blank
        answer to the quadrature phase; together with the in-phase answer it
        gives the blank response to any drive exactly, leftover ringing included.
        """
        ones = torch.ones((1, len(self.notes)), dtype=torch.complex128, device=self.index.device)
        pattern = self.to_grid(ones) * self.volume
        blank = torch.ones_like(self.field.rho)
        zero = torch.zeros_like(pattern)
        heard = [self.field.listen(pattern, None, self.read_steps, rho=blank),
                 self.field.listen(zero, pattern, self.read_steps, rho=blank),
                 self.field.listen(1j * pattern, None, self.read_steps, rho=blank)]
        (hYy, hIy), (hYi, hIi), (hYq, hIq) = [[self.to_notes(h)[0] / self.volume for h in pair] for pair in heard]
        T = torch.stack([torch.stack([hYy, hYi], -1), torch.stack([hIy, hIi], -1)], -2)
        # The medium records S = Y + I.  Keep notes whose S answers the Yang drive well.
        G = T[:, 0, 0] + T[:, 1, 0]
        keep = G.abs() >= 0.25 * G.abs().median()
        self.notes = [k for k, ok in zip(self.notes, keep.tolist()) if ok]
        self.index = self.index[keep]
        self.T, self.G = T[keep], G[keep]
        self.Tinv = torch.linalg.inv(self.T)                                  # (notes, 2, 2)
        self.quad = torch.stack([hYq, hIq], -1)[keep]                        # (notes, 2)

    def blank(self, drive_notes: torch.Tensor) -> torch.Tensor:
        """Exact blank-medium answer (B, notes, 2) to Yang drives given per note."""
        x, y = drive_notes.real[..., None], drive_notes.imag[..., None]
        return x * self.T[:, :, 0] + y * self.quad

    # -- chords --------------------------------------------------------------
    def chord(self, generator: torch.Generator, rounds: int = 40) -> torch.Tensor:
        """A random chord whose brightness |S(x)|^2 is as even as the notes allow.

        An even chord's own imprint on the medium is uniform, and a uniform
        imprint only retunes every note in place.  So what the medium records
        from two chords played together is their link and nothing else.  The
        shape is found by alternating between the note band and flat modulus.
        """
        phase = torch.rand(len(self.notes), generator=generator, dtype=torch.float64) * (2.0 * math.pi)
        amps = torch.polar(torch.ones_like(phase), phase).to(self.index.device)[None]
        for _ in range(rounds):
            grid = self.to_grid(amps)
            amps = self.to_notes(grid / grid.abs().clamp_min(1e-12))
        return (amps / amps.norm())[0]

    def unevenness(self, chord: torch.Tensor) -> float:
        """Relative spread of the chord's brightness across the field (speckle is 1)."""
        bright = self.to_grid(chord[None]).abs() ** 2
        return float(bright.std() / bright.mean())

    def drive(self, chords: torch.Tensor) -> torch.Tensor:
        """Phasor drive that makes the coherent amplitude S of every note equal the chord."""
        return self.to_grid(chords / self.G) * self.volume

    def write(self, a: torch.Tensor, b: torch.Tensor, steps: int) -> None:
        """Play two chords together; the medium keeps the product of their shapes."""
        self.field.step(steps, self.drive((a + b)[None])[0])
        self.field.calm()

    def trace(self, chords: torch.Tensor) -> torch.Tensor:
        """K applied to each chord (rows), with the chord's own direction removed."""
        out = []
        for part in chords.split(self.batch):
            D = self.drive(part)
            hY, hI = self.field.listen(D, None, self.read_steps)
            heard = torch.stack([self.to_notes(hY), self.to_notes(hI)], -1) / self.volume   # (B, notes, 2)
            residual = heard - self.blank(part / self.G)
            # The medium's source enters both fluids; together they carry K applied to S.
            source = torch.einsum("nij,bnj->bni", self.Tinv, residual).sum(-1)
            own = (source * part.conj()).sum(-1, keepdim=True) / (part.abs() ** 2).sum(-1, keepdim=True)
            out.append(source - own * part)
        return torch.cat(out)

    @staticmethod
    def similarity(traces: torch.Tensor, chords: torch.Tensor) -> torch.Tensor:
        a = traces / traces.norm(dim=-1, keepdim=True).clamp_min(1e-300)
        b = chords / chords.norm(dim=-1, keepdim=True)
        return (a @ b.conj().T).abs()


class SequenceMemory:
    """Ideas with a sending and a receiving chord; steps between them live in the medium."""

    def __init__(self, codec: NoteCodec, ideas: int, seed: int = 7, write_steps: int = 1000,
                 z_heard: float = 5.0) -> None:
        g = torch.Generator().manual_seed(seed)
        self.codec, self.write_steps, self.z_heard = codec, write_steps, z_heard
        self.send = torch.stack([codec.chord(g) for _ in range(ideas)])
        self.receive = torch.stack([codec.chord(g) for _ in range(ideas)])
        self.forward: torch.Tensor | None = None
        self.backward: torch.Tensor | None = None

    def link(self, a: int, b: int) -> None:
        self.codec.write(self.send[a], self.receive[b], self.write_steps)
        self.forward = self.backward = None

    def read(self) -> None:
        """Listen to every idea once in each direction; the medium is unchanged by listening."""
        self.forward = NoteCodec.similarity(self.codec.trace(self.send), self.receive)
        self.backward = NoteCodec.similarity(self.codec.trace(self.receive), self.send)

    def heard(self, scores: torch.Tensor) -> list[int]:
        """Ideas that stand clearly above the row's murmur.

        Unlinked chords murmur with a Rayleigh spread; exceeding ``z_heard``
        times the median happens by chance with probability 2^-(z_heard^2).
        """
        floor = scores.median().clamp_min(1e-300)
        loud = torch.nonzero(scores / floor > self.z_heard).flatten().tolist()
        return sorted(loud, key=lambda i: -float(scores[i]))

    def follow(self, start: int, depth: int, backward: bool = False) -> dict:
        """Play the train of thought from ``start``; forks branch, loops stop."""
        if self.forward is None:
            self.read()
        table = self.backward if backward else self.forward
        root = {"idea": start, "next": []}
        frontier, seen = [root], {start}
        for _ in range(depth):
            nxt = []
            for node in frontier:
                for idea in self.heard(table[node["idea"]]):
                    child = {"idea": idea, "next": []}
                    node["next"].append(child)
                    if idea not in seen:
                        seen.add(idea)
                        nxt.append(child)
            frontier = nxt
        return root


def _paths(tree: dict) -> list[list[int]]:
    if not tree["next"]:
        return [[tree["idea"]]]
    return [[tree["idea"], *rest] for child in tree["next"] for rest in _paths(child)]


def episode(out: Path, sequences: int, length: int, rest_steps: int,
            profile: EmergentProfile = EmergentProfile(), top: int = 20, seed: int = 7) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    field = EmergentField(profile)
    codec = NoteCodec(field, top)
    # Disjoint sequences, plus a branch that leaves the first one halfway.
    seqs = [list(range(i * length, (i + 1) * length)) for i in range(sequences)]
    fork_at = seqs[0][length // 2]
    branch = [fork_at, *range(sequences * length, sequences * length + length // 2)]
    ideas = sequences * length + length // 2
    memory = SequenceMemory(codec, ideas, seed)
    links = [(s[i], s[i + 1]) for s in [*seqs, branch] for i in range(len(s) - 1)]
    order = torch.randperm(len(links), generator=torch.Generator().manual_seed(seed)).tolist()
    for j in order:
        memory.link(*links[j])
    field.step(rest_steps)
    field.calm()
    t_write = time.perf_counter()

    memory.read()
    table = memory.forward
    truth = torch.zeros_like(table, dtype=torch.bool)
    for a, b in links:
        truth[a, b] = True
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
        "profile": asdict(profile), "notes": len(codec.notes), "ideas": ideas, "links": len(links),
        "links_detected": int((detected & truth).sum()), "false_links": int((detected & ~truth).sum()),
        "silent_endings": sum(int(not detected[s[-1]].any()) for s in [*seqs[1:], branch]),
        "endings": len(seqs) - 1 + 1,
        "score": {"stored_min": round(float(true_scores.min()), 4), "stored_mean": round(float(true_scores.mean()), 4),
                  "murmur_max": round(float(murmur.max()), 4), "murmur_median": round(float(murmur.median()), 4)},
        "trains_forward_exact": sum(t["forward_exact"] for t in trains),
        "trains_backward_exact": sum(t["backward_exact"] for t in trains),
        "trains": trains,
        "medium": {"mean": round(float(field.rho.mean()), 4), "max": round(float(field.rho.max()), 4)},
        "seconds": {"write": round(t_write - t0, 1), "read": round(time.perf_counter() - t_write, 1)},
    }
    field.save(out / "emergent_field.pt")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
        rho = field.rho.cpu()
        axes[0].imshow((rho if profile.dims == 2 else rho[profile.size // 2]).numpy(), cmap="magma")
        axes[0].set_title("medium (middle slice)")
        axes[0].axis("off")
        axes[1].imshow(table.cpu().numpy(), cmap="viridis")
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
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    profile = replace(EmergentProfile(), dims=a.dims, size=a.size, device=a.device)
    r = episode(a.out, a.sequences, a.length, a.rest_steps, profile, top=a.top)
    print(json.dumps({k: v for k, v in r.items() if k not in ("profile", "trains")}, indent=1))


if __name__ == "__main__":
    main()
