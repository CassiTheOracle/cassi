#!/usr/bin/env python3
"""Conditional massive chiral evolution on a periodic bubble-shaped cell.

Run from the theory root; see matter-formation-continuum-report.md section 32
for the frozen experiment. This comparison field is an additional model input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from scipy.integrate import solve_bvp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations/matter-formation-continuum-report.md"
MU = 0.5266577616452649
PHI = (1.0 + math.sqrt(5.0)) / 2.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_sha256() -> str:
    text = REPORT.read_text(encoding="utf-8")
    protocol = text.split("<!-- chiral-lattice-protocol:start -->", 1)[1].split(
        "<!-- chiral-lattice-protocol:end -->", 1
    )[0]
    return hashlib.sha256(protocol.encode("utf-8")).hexdigest()


def radial_profile() -> tuple[np.ndarray, np.ndarray]:
    r = np.linspace(1.0e-5, 64.0, 1201)
    radius = 1.0 / math.sqrt(2.0)
    guess = 2.0 * np.arctan(r / radius)
    guess_p = 2.0 * radius / (r * r + radius * radius)

    def rhs(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        theta, theta_p = y
        sine = np.sin(theta)
        theta_pp = (-2.0*x*theta_p
                    - np.sin(2.0*theta)*(theta_p*theta_p-1.0-sine*sine/(x*x))
                    - MU*MU*x*x*sine) / (x*x+2.0*sine*sine)
        return np.vstack((theta_p, theta_pp))

    def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.array([left[0]-r[0]*left[1], right[0]-math.pi])

    solution = solve_bvp(rhs, boundary, r, np.vstack((guess, guess_p)),
                         tol=1.0e-8, max_nodes=100000)
    if not solution.success:
        raise RuntimeError(f"Massive radial profile failed: {solution.message}")
    sample = np.linspace(0.0, 64.0, 64001)
    f = math.pi - solution.sol(np.maximum(sample, r[0]))[0]
    f[0], f[-1] = math.pi, 0.0
    return sample, f


class ChiralLattice:
    def __init__(self, nsites: int, length: float, device: str):
        self.N = nsites
        self.L = length
        self.device = torch.device(device)
        self.dtype = torch.float64
        basis0 = np.array([[0.5, 0.5, 0.0],
                           [0.5/PHI, 0.0, 0.5/PHI],
                           [0.0, 1.0, 1.0]])
        self.basis_np = (length/nsites)*basis0
        self.basis = self.tensor(self.basis_np)
        self.inverse = torch.linalg.inv(self.basis)
        self.volume = abs(float(torch.linalg.det(self.basis)))
        self.identity = torch.eye(4, device=self.device, dtype=self.dtype)
        index = torch.arange(nsites, dtype=self.dtype, device=self.device)
        index = index - nsites/2.0 + 0.5
        self.index = torch.stack(torch.meshgrid(index, index, index, indexing="ij"))
        self.coordinates = torch.einsum("ai,ixyz->axyz", self.basis, self.index)

    def tensor(self, value: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(value, dtype=self.dtype, device=self.device)

    def gradient(self, field: torch.Tensor, kind: str) -> torch.Tensor:
        differences = []
        for i in range(3):
            if kind == "forward":
                difference = torch.roll(field, -1, i+1)-field
            elif kind == "backward":
                difference = field-torch.roll(field, 1, i+1)
            else:
                difference = 0.5*(torch.roll(field, -1, i+1)-torch.roll(field, 1, i+1))
            differences.append(difference)
        return torch.einsum("ia,icxyz->acxyz", self.inverse, torch.stack(differences))

    def pieces(self, n: torch.Tensor, p: torch.Tensor):
        central = self.gradient(n, "central")
        d = central-n[None]*(central*n[None]).sum(1, keepdim=True)
        dlocal = d.permute(2, 3, 4, 0, 1)
        scalar = (d*d).sum((0, 1))
        matrix = (1.0+scalar)[..., None, None]*self.identity
        matrix = matrix-torch.einsum("...ai,...aj->...ij", dlocal, dlocal)
        velocity = torch.linalg.solve(matrix, p.permute(1, 2, 3, 0)[..., None])
        velocity = velocity[..., 0].permute(3, 0, 1, 2)
        kinetic = 0.5*(p*velocity).sum(0)
        forward = self.gradient(n, "forward")
        backward = self.gradient(n, "backward")
        e2 = 0.25*((forward*forward).sum((0, 1))+(backward*backward).sum((0, 1)))
        e4 = torch.zeros_like(e2)
        for a in range(3):
            for b in range(a+1, 3):
                e4 = e4+0.5*((d[a]*d[a]).sum(0)*(d[b]*d[b]).sum(0)
                             -(d[a]*d[b]).sum(0).square())
        potential = MU*MU*(1.0-n[0])
        return velocity, kinetic, e2, e4, potential, d

    def rhs(self, n: torch.Tensor, p: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        with torch.enable_grad():
            variable = n.detach().requires_grad_(True)
            velocity, kinetic, e2, e4, potential, _ = self.pieces(variable, p)
            gradient, = torch.autograd.grad((kinetic+e2+e4+potential).sum(), variable)
            tangent_gradient = gradient-variable*(variable*gradient).sum(0, keepdim=True)
            dp = -tangent_gradient-variable*(p*velocity).sum(0, keepdim=True)
        return velocity.detach(), dp.detach()

    @staticmethod
    def project(n: torch.Tensor, p: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        n = n/torch.linalg.vector_norm(n, dim=0, keepdim=True)
        p = p-n*(n*p).sum(0, keepdim=True)
        return n, p

    def step(self, n: torch.Tensor, p: torch.Tensor, dt: float):
        a, b = self.rhs(n, p)
        c, d = self.rhs(*self.project(n+0.5*dt*a, p+0.5*dt*b))
        e, f = self.rhs(*self.project(n+0.5*dt*c, p+0.5*dt*d))
        g, h = self.rhs(*self.project(n+dt*e, p+dt*f))
        return self.project(n+(dt/6.0)*(a+2*c+2*e+g), p+(dt/6.0)*(b+2*d+2*f+h))

    def observables(self, n: torch.Tensor, p: torch.Tensor, t: float) -> dict:
        with torch.no_grad():
            _, kinetic, e2, e4, potential, d = self.pieces(n, p)
            local = torch.stack((n, d[0], d[1], d[2]), dim=-1).permute(1, 2, 3, 0, 4)
            b = torch.linalg.det(local)/(2.0*math.pi**2)
            positive, negative = torch.clamp(b, min=0.0), torch.clamp(-b, min=0.0)
            edge_angle = torch.zeros((), dtype=self.dtype, device=self.device)
            for i in range(3):
                dot = (n*torch.roll(n, -1, i+1)).sum(0).clamp(-1.0, 1.0)
                edge_angle = torch.maximum(edge_angle, torch.acos(dot).max())
            torque = self.volume*torch.linalg.cross(n[1:], p[1:], dim=0).sum((1, 2, 3))
            centres, fractions = [], []
            for density in (positive, negative):
                total = float(density.sum())
                if total <= 1.0e-30:
                    centres.append([0.0, 0.0, 0.0])
                    fractions.append(0.0)
                    continue
                # Circular means and minimum-image primitive coordinates make the
                # diagnostic invariant under translations across periodic faces.
                angles = 2.0*math.pi*self.index/self.N
                zreal = (torch.cos(angles)*density[None]).sum((1, 2, 3))
                zimag = (torch.sin(angles)*density[None]).sum((1, 2, 3))
                centre_index = torch.atan2(zimag, zreal)*self.N/(2.0*math.pi)
                delta = self.index-centre_index[:, None, None, None]
                delta = delta-self.N*torch.round(delta/self.N)
                physical = torch.einsum("ai,ixyz->axyz", self.basis, delta)
                radius = torch.linalg.vector_norm(physical, dim=0)
                fractions.append(float(density[radius <= 2.0].sum())/total)
                centres.append((self.basis@centre_index).cpu().tolist())
            delta_centres = self.inverse@self.tensor(np.array(centres[0])-np.array(centres[1]))
            delta_centres = delta_centres-self.N*torch.round(delta_centres/self.N)
            separation = float(torch.linalg.vector_norm(self.basis@delta_centres))
            energy_parts = [self.volume*float(piece.sum()) for piece in (kinetic, e2, e4, potential)]
            return {"t": t, "energy": sum(energy_parts), "kinetic": energy_parts[0],
                    "e2": energy_parts[1], "e4": energy_parts[2], "potential": energy_parts[3],
                    "B": self.volume*float(b.sum()), "Bpos": self.volume*float(positive.sum()),
                    "Bneg": self.volume*float(negative.sum()),
                    "unit_error": float(((n*n).sum(0)-1.0).abs().max()),
                    "tangent_error": float((n*p).sum(0).abs().max()),
                    "edge_angle_max": float(edge_angle), "torque": torque.cpu().tolist(),
                    "centres": centres, "separation": separation, "local_fractions": fractions}

    def hedgehog(self, x: torch.Tensor, radial: tuple[np.ndarray, np.ndarray], scale: float):
        r = torch.linalg.vector_norm(x, dim=0)
        knots, values = radial
        f = np.interp((r/scale).cpu().numpy(), knots, values)
        f = self.tensor(f)
        unit = x/r.clamp_min(1.0e-30)[None]
        return torch.cat((torch.cos(f)[None], torch.sin(f)[None]*unit), dim=0)

    @staticmethod
    def multiply(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        scalar = a[:1]*b[:1]-(a[1:]*b[1:]).sum(0, keepdim=True)
        vector = a[:1]*b[1:]+b[:1]*a[1:]-torch.linalg.cross(a[1:], b[1:], dim=0)
        return torch.cat((scalar, vector))

    def initial(self, mode: str, speed: float, radial):
        n = torch.zeros((4, self.N, self.N, self.N), dtype=self.dtype, device=self.device)
        n[0] = 1.0
        p = torch.zeros_like(n)
        if mode == "prepared":
            n = self.hedgehog(self.coordinates, radial, 1.0)
        elif mode == "impulse":
            displacement = torch.zeros((3, 1, 1, 1), dtype=self.dtype, device=self.device)
            displacement[0] = 1.0e-3
            u = self.hedgehog(self.coordinates, radial, 1.5)
            conjugate = torch.cat((u[:1], -u[1:]))
            derivative = (self.hedgehog(self.coordinates+displacement, radial, 1.5)
                          -self.hedgehog(self.coordinates-displacement, radial, 1.5))/0.002
            p = 2.0*speed*self.multiply(derivative, conjugate)
            n, p = self.project(n, p)
        elif mode == "controls":
            phase = 2.0*math.pi*self.index/self.N
            n[1] = 0.08*torch.sin(phase[0])+0.03*torch.cos(phase[1]+phase[2])
            n[2] = 0.07*torch.cos(phase[1])+0.02*torch.sin(phase[0]-phase[2])
            n[3] = 0.06*torch.sin(phase[2])+0.02*torch.cos(phase[0]+phase[1])
            p[1] = 0.04*torch.cos(phase[0]-phase[1])
            p[2] = 0.03*torch.sin(phase[1]+phase[2])
            p[3] = 0.02*torch.cos(phase[0]+phase[2])
            n, p = self.project(n, p)
        return n.detach(), p.detach()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("controls", "impulse", "prepared", "vacuum"), required=True)
    parser.add_argument("--N", type=int, default=32)
    parser.add_argument("--L", type=float, default=18.0)
    parser.add_argument("--dt", type=float, default=0.002)
    parser.add_argument("--T", type=float, default=4.0)
    parser.add_argument("--speed", type=float, default=2.0)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if args.N < 4 or args.N % 2 or args.L <= 0 or args.dt <= 0 or args.T <= 0:
        raise ValueError("Positive lengths/times and an even N >= 4 are required")
    steps = round(args.T/args.dt)
    if abs(steps*args.dt-args.T) > 1.0e-12:
        raise ValueError("T must be an integer multiple of dt")
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(4)
    start = time.perf_counter()
    model = ChiralLattice(args.N, args.L, args.device)
    radial = radial_profile() if args.mode in ("impulse", "prepared") else None
    if args.resume is None:
        n, p = model.initial(args.mode, args.speed, radial)
    else:
        with np.load(args.resume, allow_pickle=False) as data:
            if data["n"].shape != (4, args.N, args.N, args.N):
                raise ValueError("Resume field shape does not match the selected lattice")
            if not np.array_equal(data["basis"], model.basis_np):
                raise ValueError("Resume basis differs from the selected lattice")
            n, p = model.tensor(data["n"]), model.tensor(data["p"])
    source_file = Path(__file__).relative_to(ROOT).as_posix()
    sources = {source_file: sha256(Path(__file__))}
    for name in ("verify_matter_formation_chiral_lattice.py", "matter_formation_chiral_lattice_structure.py"):
        path = ROOT/"computations"/name
        if path.is_file():
            sources[path.relative_to(ROOT).as_posix()] = sha256(path)
    result = {"schema": "matter-formation-chiral-lattice-v1", "source_file": source_file,
              "primary_source": source_file, "source_sha256": sources[source_file], "sources": sources,
              "protocol_file": REPORT.relative_to(ROOT).as_posix(), "protocol_sha256": protocol_sha256(),
              "mode": args.mode, "device": str(model.device),
              "parameters": {"N": args.N, "L": args.L, "dt": args.dt, "T": args.T,
                             "speed": args.speed, "mu": MU, "kappa": 1.0, "p_parallel": 2.0},
              "snapshots": [], "records": [], "scientific_execution_started": args.mode != "controls"}
    if args.resume:
        result["resume"] = {"file": str(args.resume.resolve()), "sha256": sha256(args.resume)}

    def save_arrays(name: str, **arrays) -> dict:
        path = args.output/name
        plain = {key: value.detach().cpu().numpy() if isinstance(value, torch.Tensor) else value
                 for key, value in arrays.items()}
        np.savez(path, **plain)
        return {"file": name, "sha256": sha256(path)}

    def record(step: int):
        row = model.observables(n, p, step*args.dt)
        if not all(math.isfinite(row[key]) for key in ("energy", "B", "Bpos", "Bneg", "unit_error", "tangent_error")):
            raise FloatingPointError("Nonfinite trajectory diagnostic")
        artifact = save_arrays(f"state_{step:06d}.npz", n=n, p=p, basis=model.basis_np)
        artifact.update(t=row["t"], metrics=row)
        result["snapshots"].append(artifact)
        result["records"].append(row)
        result["wall_s"] = time.perf_counter()-start
        (args.output/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        print(json.dumps(row, allow_nan=False), flush=True)

    if args.mode == "controls":
        dn, dp = model.rhs(n, p)
        result["rhs_probe"] = save_arrays("rhs_probe.npz", n=n, p=p, dn=dn, dp=dp, basis=model.basis_np)
        parity = torch.where(torch.arange(args.N, device=model.device) % 2 == 0, 1.0, -1.0)
        checker = torch.zeros_like(n)
        checker[0] = math.cos(0.4)
        checker[1] = math.sin(0.4)*parity[:, None, None]
        old = 0.5*model.volume*float(model.gradient(checker, "central").square().sum())
        checker_pieces = model.pieces(checker, torch.zeros_like(checker))
        new = model.volume*float(checker_pieces[2].sum())
        result["checkerboard"] = {"central_e2": old, "edge_e2": new, "angle": 0.4}
        initial_n, initial_p = n.clone(), p.clone()
    if radial:
        result["radial_profile"] = save_arrays("radial_profile.npz", r=radial[0], F=radial[1])
    record(0)
    sample_every = max(1, round(0.5/args.dt))
    for step in range(1, steps+1):
        n, p = model.step(n, p, args.dt)
        if step % sample_every == 0 or step == steps:
            record(step)
    if args.mode == "controls":
        result["replay"] = save_arrays("replay.npz", n0=initial_n, p0=initial_p, n1=n, p1=p, basis=model.basis_np)
        result["replay"].update(dt=args.dt, steps=steps)
    energy0 = result["records"][0]["energy"]
    result["max_relative_energy_drift"] = max(abs(row["energy"]-energy0) for row in result["records"])/max(1.0, abs(energy0))
    result["wall_s"] = time.perf_counter()-start
    result["completed"] = True
    (args.output/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"completed": True, "output": str(args.output), "wall_s": result["wall_s"],
                      "max_relative_energy_drift": result["max_relative_energy_drift"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
