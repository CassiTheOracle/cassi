#!/usr/bin/env python3
"""Evolve the conditional constant-density Cassi reacting capillary fluid.

Run from CassiTheory:
    python computations/cassi_fluid_thermodynamics.py --n 21 --dt 0.002 --time 0.2

This research model supplies rotational velocity and constitutive thermal
coefficients. It is separate from the native density/Poisson solver. State
channels are (u_x, u_y, u_z, c, T); Y=rho_ref*c, I=rho_ref*(1-c).
Odd-grid periodic Fourier collocation, skew velocity convection and classical
RK4 are used. No mode, density or temperature is reset after a step. Continuum
energy/entropy laws require spatial convergence; RK4 is not positivity preserving.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0
C_STAR = PHI / (1.0 + PHI)
AXES = (-3, -2, -1)


@dataclass(frozen=True)
class Parameters:
    inertia: float = 1.0
    rho_ref: float = 1.0
    a: float = 1.0
    gamma: float = 0.02
    heat_capacity: float = 2.0
    mixing_entropy: float = 0.2
    viscosity: float = 0.03  # Dynamic viscosity eta, not kinematic nu.
    conductivity: float = 0.02
    conversion: float = 0.4

    def __post_init__(self):
        values = asdict(self)
        if not all(np.isfinite(value) for value in values.values()):
            raise ValueError("All constitutive coefficients must be finite")
        for name in ("inertia", "rho_ref", "a", "heat_capacity", "mixing_entropy"):
            if values[name] <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("gamma", "viscosity", "conductivity", "conversion"):
            if values[name] < 0:
                raise ValueError(f"{name} must be nonnegative")


def mixing(c):
    """Relative mixing entropy, its derivative and continuous secant slope."""
    delta = c - C_STAR
    log_y = np.log1p(delta / C_STAR)
    log_i = np.log1p(-delta / (1.0 - C_STAR))
    h = c * log_y + (1.0 - c) * log_i
    hp = log_y - log_i
    slope = np.full_like(c, 1.0 / (C_STAR * (1.0 - C_STAR)))
    np.divide(hp, delta, out=slope, where=delta != 0)
    return h, hp, slope


class SpectralFluid:
    def __init__(self, n: int, parameters: Parameters = Parameters()):
        if n < 5 or n % 2 != 1:
            raise ValueError("Use an odd grid of at least five points per axis")
        self.n = n
        self.p = parameters
        coordinates = np.arange(n, dtype=np.float64) * (2.0 * np.pi / n)
        self.xyz = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        frequencies = np.fft.fftfreq(n, d=1.0 / n)
        self.k = np.asarray(np.meshgrid(frequencies, frequencies, frequencies, indexing="ij"))
        self.k2 = np.sum(self.k * self.k, axis=0)
        self.inverse_k2 = np.zeros_like(self.k2)
        np.divide(1.0, self.k2, out=self.inverse_k2, where=self.k2 != 0)

    @staticmethod
    def fft(value):
        return np.fft.fftn(value, axes=AXES)

    @staticmethod
    def ifft(value):
        return np.fft.ifftn(value, axes=AXES).real

    def gradient(self, value):
        return self.ifft(1j * self.k * self.fft(value)[..., None, :, :, :])

    def divergence(self, vector):
        return self.ifft(np.sum(1j * self.k * self.fft(vector), axis=-4))

    def laplacian(self, value):
        return self.ifft(-self.k2 * self.fft(value))

    def project(self, vector):
        spectrum = self.fft(vector)
        longitudinal = np.sum(self.k * spectrum, axis=0) * self.inverse_k2
        # At k=0 the subtracted longitudinal part is exactly zero.
        return self.ifft(spectrum - self.k * longitudinal)

    def check_state(self, state):
        if state.shape != (5, self.n, self.n, self.n):
            raise ValueError("Expected five channels on the configured cubic grid")
        if not np.isfinite(state).all():
            raise FloatingPointError("Non-finite fluid state")
        if np.min(state[3]) <= 0 or np.max(state[3]) >= 1 or np.min(state[4]) <= 0:
            raise FloatingPointError("Fluid state left 0<c<1 or T>0; no floor is applied")

    def terms(self, state):
        self.check_state(state)
        p = self.p
        u, c, temperature = state[:3], state[3], state[4]
        gradients = self.gradient(state)
        du, dc, dtemperature = gradients[:3], gradients[3], gradients[4]
        lap = self.laplacian(state)
        grad_c2 = np.sum(dc * dc, axis=0)
        g = p.gamma / (c * (1.0 - c))
        gp = -p.gamma * (1.0 - 2.0 * c) / (c * (1.0 - c)) ** 2
        # This variational form is also the exact derivative of the collocation
        # energy under the skew-adjoint discrete Fourier derivative.
        mu = p.a * (c - C_STAR) + 0.5 * gp * grad_c2 - self.divergence(g * dc)
        h, hp, slope = mixing(c)
        epsilon = p.rho_ref * (1.0 + PHI) * (c - C_STAR)
        gap = PHI ** -2 + epsilon * epsilon
        kappa = p.conversion * gap / (p.rho_ref ** 2 + gap)
        mobility = (1.0 + PHI) * kappa / (p.a + p.mixing_entropy * temperature * slope)
        affinity = mu + p.mixing_entropy * temperature * hp
        reaction = -mobility * affinity
        capillary = g * dc[:, None] * dc[None, :]
        force = -self.divergence(capillary)
        strain = 0.5 * (du + np.swapaxes(du, 0, 1))
        viscous_heat = 2.0 * p.viscosity * np.sum(strain * strain, axis=(0, 1))
        production = (viscous_heat + mobility * affinity * affinity) / temperature
        production += p.conductivity * np.sum(dtemperature * dtemperature, axis=0) / temperature ** 2
        return dict(gradients=gradients, lap=lap, mu=mu, h=h, hp=hp,
                    g=g, grad_c2=grad_c2, force=force, reaction=reaction,
                    affinity=affinity, mobility=mobility, viscous_heat=viscous_heat,
                    production=production)

    def rhs(self, state):
        fields = self.terms(state)
        p, u = self.p, state[:3]
        advection = np.sum(u * fields["gradients"], axis=1)
        velocity_flux = u[:, None] * u[None, :]
        velocity_advection = 0.5 * (advection[:3] + self.divergence(velocity_flux))
        result = np.empty_like(state)
        result[:3] = self.project(-velocity_advection + fields["force"] / p.inertia)
        result[:3] += (p.viscosity / p.inertia) * fields["lap"][:3]
        result[3] = -advection[3] + fields["reaction"]
        result[4] = -advection[4] + (p.conductivity * fields["lap"][4]
                    + fields["viscous_heat"] - fields["mu"] * fields["reaction"]) / p.heat_capacity
        return result

    def step(self, state, dt):
        k1 = self.rhs(state)
        k2 = self.rhs(state + 0.5 * dt * k1)
        k3 = self.rhs(state + 0.5 * dt * k2)
        k4 = self.rhs(state + dt * k3)
        result = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        self.check_state(result)
        return result

    def diagnostics(self, state):
        f, p = self.terms(state), self.p
        u, c, temperature = state[:3], state[3], state[4]
        kinetic = float(np.mean(0.5 * p.inertia * np.sum(u * u, axis=0)))
        composition = float(np.mean(0.5 * p.a * (c - C_STAR) ** 2 + 0.5 * f["g"] * f["grad_c2"]))
        thermal = float(p.heat_capacity * np.mean(temperature))
        return dict(kinetic=kinetic, composition=composition, thermal=thermal,
                    total_energy=kinetic + composition + thermal,
                    entropy=float(np.mean(p.heat_capacity * np.log(temperature) - p.mixing_entropy * f["h"])),
                    entropy_production=float(np.mean(f["production"])),
                    c_min=float(np.min(c)), c_max=float(np.max(c)), temperature_min=float(np.min(temperature)),
                    divergence_max=float(np.max(np.abs(self.divergence(u)))),
                    momentum_x=float(p.inertia * np.mean(u[0])),
                    momentum_y=float(p.inertia * np.mean(u[1])),
                    momentum_z=float(p.inertia * np.mean(u[2])))

    def evolve(self, initial, duration, dt):
        if not np.isfinite(duration) or not np.isfinite(dt) or duration <= 0 or dt <= 0:
            raise ValueError("Duration and step must be finite and positive")
        count = round(duration / dt)
        if count < 1 or abs(count * dt - duration) > 1e-12 * max(1.0, duration):
            raise ValueError("Duration must be an integer number of steps")
        state = initial.copy()
        self.check_state(state)
        first = self.diagnostics(state)
        columns = ["time", *first]
        history = [[0.0, *first.values()]]
        entropy_integral = 0.0
        previous_production = first["entropy_production"]
        for index in range(count):
            state = self.step(state, dt)
            row = self.diagnostics(state)
            entropy_integral += 0.5 * dt * (previous_production + row["entropy_production"])
            previous_production = row["entropy_production"]
            history.append([(index + 1) * dt, *row.values()])
        return state, np.asarray(history), columns, entropy_integral


def coupled_initial(model, at_rest=False):
    x, y, z = model.xyz
    state = np.zeros((5, model.n, model.n, model.n), dtype=np.float64)
    if not at_rest:
        state[0] = 0.2 * np.sin(x) * np.cos(y) * np.cos(z)
        state[1] = -0.2 * np.cos(x) * np.sin(y) * np.cos(z)
    state[3] = C_STAR + 0.06 * (np.cos(x) + 0.5 * np.cos(2.0 * y) + 0.25 * np.sin(z))
    state[4] = 1.0 + 0.05 * np.sin(x + y) + 0.03 * np.cos(z)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=21)
    parser.add_argument("--dt", type=float, default=0.002)
    parser.add_argument("--time", type=float, default=0.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError(args.output)
    model = SpectralFluid(args.n)
    initial = coupled_initial(model)
    final, history, columns, entropy_integral = model.evolve(initial, args.time, args.dt)
    before, after = model.diagnostics(initial), model.diagnostics(final)
    report = dict(scope="Conditional constitutive model; no physical calibration or global regularity claim",
                  n=args.n, dt=args.dt, duration=args.time, parameters=asdict(model.p),
                  initial=before, final=after, energy_drift=after["total_energy"]-before["total_energy"],
                  entropy_integral=entropy_integral,
                  entropy_balance_error=after["entropy"]-before["entropy"]-entropy_integral)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            np.savez_compressed(stream, initial=initial, final=final, history=history,
                                columns=np.asarray(columns), report=np.asarray(json.dumps(report)))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
