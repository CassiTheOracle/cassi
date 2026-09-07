#!/usr/bin/env python3
"""Qualify the frozen expanding-model density and composition budgets.

Run from the repository root with a fresh output directory:
    python computations/matter_formation_density_budget.py --output-dir runs/<fresh-name>

Uses actual CPU solver right-hand sides and time steps, independent NumPy
budget reconstruction, and a separable scalar endpoint. No solver edits.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import re
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import brentq
import sympy as sp
import torch

ROOT = Path(__file__).resolve().parents[1]
HEADING = "### 22.3 Nonlinear budget calculation: pre-execution criteria"
PROTOCOL_SHA = "c998f007510ede9845ca51c65c30c8af496477e83e377fa743bad0603c521497"
SOLVER_SHA = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
VERDICT = "SUPPORTS—nonlinear density and composition budgets of the specified expanding model"
PHI = (1 + np.sqrt(5.0)) / 2
CG = 0.382


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def protocol(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("Frozen budget heading must occur exactly once")
    rest = text.split(HEADING, 1)[1]
    end = re.search(r"\n#{1,3} ", rest)
    return (HEADING + (rest[:end.start()] if end else rest)).rstrip() + "\n"


def exact_identities() -> list[dict]:
    r, e, p, lam, c = sp.symbols("rho epsilon phi lambda c", positive=True)
    g = (e**2 + c) / (r**2 + e**2 + c)
    conv_y, conv_i = -lam*g*e, lam*g*e
    q = r**2 / (r**2 + e**2 + c)
    expected_qdot = 2*(1+p)*lam*r**2*e**2*(e**2+c)/(r**2+e**2+c)**3
    x = sp.Symbol("x", real=True)
    f, u = sp.Function("f")(x), sp.Function("u")(x)
    # The displayed one-coordinate product rules sum independently over axes.
    lap = sp.Function("laplacian_f")(x)
    implicit_primitive = (1+r**2/c)*sp.log(e) - r**2/(2*c)*sp.log(e**2+c)
    checks = {
        "total_conversion": conv_y + conv_i,
        "imbalance_conversion": conv_y-p*conv_i+(1+p)*lam*g*e,
        "advective_product_rule": f*u*sp.diff(f,x)-sp.diff(u*f**2/2,x)
        + sp.diff(u,x)*f**2/2,
        "diffusion_product_rule": f*sp.diff(f,x,2)-sp.diff(f*sp.diff(f,x),x)
        + sp.diff(f,x)**2,
        "biharmonic_flux_product_rule": f*sp.diff(lap,x,2)
        - sp.diff(f*sp.diff(lap,x)-lap*sp.diff(f,x),x)-lap*sp.diff(f,x,2),
        "material_coherence_derivative": sp.diff(q,e)*(conv_y-p*conv_i)-expected_qdot,
        "implicit_primitive_derivative": sp.diff(implicit_primitive,e)*(-(1+p)*lam*g*e)
        + (1+p)*lam,
    }
    return [{"name": name, "residual": str(sp.simplify(value)),
             "passed": bool(sp.simplify(value) == 0)} for name, value in checks.items()]


def make_solver(module, n: int, diffusion: float, hyper: float, viscosity: float = 0.02):
    solver = module.ExpandingTwoFluid3DGPU(
        N=n, L=2*np.pi, nu=viscosity, D=diffusion, lam=0.2,
        H0=0.0, a0=1.0, hubble_mode="friedmann", h_smooth=1.0,
        hyper_nu=hyper, cs2=0.7, qi_gate=True, phi_inv2=CG,
        qi_memory=False, wu_xing=False, chi=0.4, chi_yang=0.4/PHI,
        rho_ext=None, alpha_disp=None, device="cpu")
    solver.gate_model = "single"
    return solver


def initial_state(rho: np.ndarray, epsilon: np.ndarray, velocity: np.ndarray):
    ey = (PHI*rho+epsilon)/(1+PHI)
    ei = (rho-epsilon)/(1+PHI)
    fields = [torch.from_numpy(np.asarray(value, dtype=np.float64))
              for value in (*velocity, ey, ei)]
    return [torch.fft.fftn(value) for value in fields[:3]], torch.fft.fftn(fields[3]), torch.fft.fftn(fields[4])


def independent_symbols(n: int):
    frequencies = np.fft.fftfreq(n, d=2*np.pi/n).astype(np.float32)*np.float32(2*np.pi)
    kz, ky, kx = np.meshgrid(frequencies.astype(np.float64), frequencies.astype(np.float64),
                             frequencies.astype(np.float64), indexing="ij")
    return (kx, ky, kz), kx*kx+ky*ky+kz*kz


def spatial_budget(field: np.ndarray, waves, k2):
    spectrum = np.fft.fftn(field)
    gradients = [np.fft.ifftn(1j*k*spectrum).real for k in waves]
    laplacian = np.fft.ifftn(-k2*spectrum).real
    return float(sum(np.mean(v*v) for v in gradients)), float(np.mean(laplacian**2))


def save_arrays(out: Path, name: str, arrays: dict, files: dict):
    for key, value in arrays.items():
        if not np.isfinite(np.asarray(value)).all():
            raise FloatingPointError(f"Nonfinite array {name}:{key}")
    np.savez_compressed(out/name, **arrays)
    files[name] = digest((out/name).read_bytes())


def nonuniform_budgets(module, out: Path, files: dict) -> list[dict]:
    n = 16
    z, y, x = np.meshgrid(*(np.arange(n)*2*np.pi/n for _ in range(3)), indexing="ij")
    rho = 2+0.3*np.cos(x)+0.2*np.sin(y)
    epsilon = 0.4*np.sin(z)+0.1*np.cos(x+y)
    velocity = np.stack((0.2*np.sin(y), 0.3*np.sin(z), 0.1*np.sin(x)))
    waves, k2 = independent_symbols(n)
    grad_rho, lap_rho = spatial_budget(rho, waves, k2)
    grad_eps, lap_eps = spatial_budget(epsilon, waves, k2)
    gate = (epsilon**2+CG)/(rho**2+epsilon**2+CG)
    reaction = float((1+PHI)*0.2*np.mean(gate*epsilon**2))
    rows = []
    for index, (diffusion, hyper) in enumerate(((0.,0.),(.03,0.),(0.,.0004),(.03,.0004))):
        solver = make_solver(module, n, diffusion, hyper)
        wave_error = max(float(np.max(np.abs(w-k.detach().numpy())))
                         for w, k in zip(waves, (solver.kx, solver.ky, solver.kz)))
        state = initial_state(rho, epsilon, velocity)
        _, ey_rate_hat, ei_rate_hat = solver.rhs(*state)
        ey_rate = torch.fft.ifftn(ey_rate_hat).real.numpy()
        ei_rate = torch.fft.ifftn(ei_rate_hat).real.numpy()
        rho_rate = ey_rate+ei_rate
        eps_rate = ey_rate-PHI*ei_rate
        actual = [float(np.mean((rho-rho.mean())*rho_rate)), float(np.mean(epsilon*eps_rate))]
        expected = [-diffusion*grad_rho-hyper*lap_rho,
                    -diffusion*grad_eps-hyper*lap_eps-reaction]
        residuals = [abs(a-b)/max(1.,abs(b)) for a,b in zip(actual,expected)]
        mean_rate = abs(float(rho_rate.mean()))
        name = f"budget_{index:02d}.npz"
        save_arrays(out, name, {"rho":rho, "epsilon":epsilon, "velocity":velocity,
                    "ey_rate":ey_rate, "ei_rate":ei_rate, "actual":actual, "expected":expected,
                    "D":diffusion, "hyper_nu":hyper}, files)
        rows.append({"name":f"nonuniform_{index}", "array":name, "D":diffusion, "hyper_nu":hyper,
                     "half_quadratic_rates":actual, "expected":expected, "residuals":residuals,
                     "mean_rate":mean_rate, "wave_symbol_error":wave_error,
                     "passed": bool(max(residuals)<=1e-11 and mean_rate<=1e-12
                                    and max(actual)<=1e-11 and wave_error<=1e-12)})
    solver = make_solver(module,n,0.,0.)
    uniform_rho = np.full_like(rho,2.)
    _, ey_rate_hat, ei_rate_hat = solver.rhs(*initial_state(uniform_rho,epsilon,velocity))
    ey_rate = torch.fft.ifftn(ey_rate_hat).real.numpy()
    ei_rate = torch.fft.ifftn(ei_rate_hat).real.numpy()
    residual = float(np.max(np.abs(ey_rate+ei_rate)))
    save_arrays(out,"uniform_density.npz", {"rho":uniform_rho,"epsilon":epsilon,
                "velocity":velocity,"ey_rate":ey_rate,"ei_rate":ei_rate}, files)
    rows.append({"name":"uniform_density", "array":"uniform_density.npz",
                 "maximum_density_rate":residual,"passed":residual<=1e-12})
    return rows


def conversion_trajectories(module, out: Path, files: dict):
    rho0, eps0, final_time = 2., .8, 20.
    gamma = (1+PHI)*.2
    def implicit(e):
        return (1+rho0**2/CG)*np.log(eps0/e)-rho0**2/(2*CG)*np.log((eps0**2+CG)/(e*e+CG))-gamma*final_time
    reference = float(brentq(implicit,1e-15,eps0,xtol=1e-14))
    reference_q = rho0**2/(rho0**2+reference**2+CG)
    rows = []
    for index, dt in enumerate((.04,.02,.01)):
        solver = make_solver(module,4,0.,0.,viscosity=0.)
        state = initial_state(np.full((4,4,4),rho0),np.full((4,4,4),eps0),np.zeros((3,4,4,4)))
        steps = round(final_time/dt)
        # time, rho mean, epsilon mean, q mean, min EY, min EI, uniformity, a, H
        history = np.empty((steps+1,9),dtype=np.float64)
        for step in range(steps+1):
            ey, ei = [torch.fft.ifftn(h).real for h in state[1:]]
            rho, eps = ey+ei, ey-PHI*ei
            q, _ = solver.compute_q_field(ey,ei)
            uniformity = max(float(torch.max(torch.abs(v-v.mean()))) for v in (rho,eps,q))
            history[step] = (step*dt,float(rho.mean()),float(eps.mean()),float(q.mean()),
                             float(ey.min()),float(ei.min()),uniformity,float(solver.a),float(solver.H))
            if step < steps:
                state = solver.rk2_step(*state,dt)
        error = abs(float(history[-1,2])-reference)
        q_error = abs(float(history[-1,3])-reference_q)
        density_error = float(np.max(np.abs(history[:,1]-rho0)))
        uniformity_error = float(np.max(history[:,6]))
        scale_error = float(np.max(np.abs(history[:,7]-1)))
        hubble_error = float(np.max(np.abs(history[:,8])))
        q_decrease = float(min(0.,np.min(np.diff(history[:,3]))))
        minima = float(np.min(history[:,4:6]))
        name = f"conversion_{index:02d}.npz"
        save_arrays(out,name,{"history":history,"dt":dt,"reference_epsilon":reference,
                              "reference_q":reference_q},files)
        passed = (error<=1e-5 and q_error<=1e-6 and q_decrease>=-1e-13
                  and max(density_error,uniformity_error,scale_error,hubble_error)<=1e-12 and minima>.1)
        rows.append({"name":f"conversion_{index}","array":name,"dt":dt,
                     "epsilon_initial":eps0,"epsilon_final":float(history[-1,2]),
                     "epsilon_reference":reference,"epsilon_error":error,
                     "q_initial":float(history[0,3]),"q_final":float(history[-1,3]),
                     "q_reference":reference_q,"q_error":q_error,"maximum_q_decrease":q_decrease,
                     "density_error":density_error,"uniformity_error":uniformity_error,
                     "scale_error":scale_error,"hubble_error":hubble_error,"minimum_component":minima,
                     "passed":bool(passed)})
    errors = [row["epsilon_error"] for row in rows]
    ratios = [errors[i]/errors[i+1] if errors[i+1]>0 else None for i in range(2)]
    return rows,{"ratios":ratios,"passed":all(r is not None and 3.5<=r<=4.5 for r in ratios),
                 "reference_equation_residual":abs(float(implicit(reference)))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--note",type=Path,default=ROOT/"computations/matter-formation-continuum-report.md")
    parser.add_argument("--solver",type=Path,default=ROOT/"two-fluid/cassi_two_fluid_3d_gpu.py")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    result = {"schema":"matter-formation-density-budget-v1","verdict":"INCONCLUSIVE",
              "passed":False,"rows":[],"identities":[],"trajectories":[],"files":{},"provenance":{}}
    try:
        section = protocol(args.note)
        source = args.solver.read_bytes()
        if digest(section.encode())!=PROTOCOL_SHA:
            raise ValueError("Frozen budget section hash mismatch")
        if digest(canonical(source))!=SOLVER_SHA:
            raise ValueError("Canonical solver source hash mismatch")
        own_source = Path(__file__).read_bytes()
        result["provenance"] = {
            "protocol_sha256":PROTOCOL_SHA,"solver_canonical_sha256":SOLVER_SHA,
            "solver_raw_sha256":digest(source),"program_canonical_sha256":digest(canonical(own_source)),
            "program_raw_sha256":digest(own_source),"python":platform.python_version(),
            "numpy":np.__version__,"scipy":scipy.__version__,"sympy":sp.__version__,"torch":torch.__version__}
        for name,data in (("frozen_protocol.txt",section.encode()),("source_solver.py",source),("source_program.py",own_source)):
            (args.output_dir/name).write_bytes(data)
            result["files"][name] = digest(data)
        spec = importlib.util.spec_from_file_location("cassi_density_budget_source",args.solver)
        if spec is None or spec.loader is None:
            raise ValueError("Unable to load canonical source")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        torch.set_num_threads(1)
        result["identities"] = exact_identities()
        result["rows"] = nonuniform_budgets(module,args.output_dir,result["files"])
        result["trajectories"],result["convergence"] = conversion_trajectories(module,args.output_dir,result["files"])
        result["passed"] = (len(result["identities"])==7 and len(result["rows"])==5
                            and len(result["trajectories"])==3
                            and all(row["passed"] for group in ("identities","rows","trajectories") for row in result[group])
                            and result["convergence"]["passed"])
        if result["passed"]:
            result["verdict"] = VERDICT
    except (OSError,ValueError,RuntimeError,FloatingPointError,ImportError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (args.output_dir/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(result["verdict"])
    print(json.dumps({"identities":len(result["identities"]),"budget_rows":len(result["rows"]),
                      "trajectories":len(result["trajectories"]),"convergence":result.get("convergence"),
                      "error":result.get("error")},allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
