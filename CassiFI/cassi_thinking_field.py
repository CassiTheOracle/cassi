"""A circulating Yang/Yin field whose cells are thinking neurons.

Every cell is a site of one field, and every idea the organism holds is a mode
of that field: each (idea, cell) site carries the canonical density pair
``(E_Y, E_I)``.  Three processes run on it:

* **Conversion** at each site follows the canonical law: the imbalance
  ``eps = E_Y - phi E_I`` relaxes at rate ``lambda (1 - q)(1 + phi)`` with the
  density ``rho = E_Y + E_I`` conserved, gated by the Qi diagnostic
  ``q = [1 + (eps/rho)^2 + phi^-2 / rho^2]^-1``.  The step is exact for a
  frozen ``q``, so densities stay non-negative.
* **Circulation** along the directed synapses: Yang travels forward along
  every synapse and Yin travels backward, each cell passing exactly what the
  next one receives.  A ring of cells gives the counter-current loop; any
  directed graph of cells gives a larger brain with the same law.
* **Fading** removes a small uniform fraction per unit time, so an idea that
  no cell keeps feeding dims away; ``forget`` then removes its mode.

Readouts are measurements of that state: ``churn`` is the local conversion
power (where the field is still working something out), ``resonance`` is the
geometric mean of an idea's Qi over every cell (high only when every cell
holds it densely and in golden balance), and the field is at rest when no site
churns.  Cells change the field only by depositing Yang or Yin at their own
site or by draining it; the field never reads the records that justify a
deposit.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

SCHEMA = "cassifi.thinking-field.v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV2 = PHI ** -2


def qi(ey: np.ndarray, ei: np.ndarray) -> np.ndarray:
    """The canonical Qi diagnostic of density pairs (0 where the site is empty)."""

    rho = ey + ei
    safe = np.where(rho > 0.0, rho, 1.0)
    value = 1.0 / (1.0 + ((ey - PHI * ei) / safe) ** 2 + PHI_INV2 / safe ** 2)
    return np.where(rho > 0.0, value, 0.0)


class ThinkingField:
    """Ideas x cells two-fluid state circulating along directed synapses."""

    def __init__(
        self,
        cells: Sequence[str],
        synapses: Iterable[tuple[str, str]] | None = None,
        *,
        conversion: float = 0.5,
        circulation: float = 0.8,
        fade: float = 0.03,
        dt: float = 0.05,
    ) -> None:
        cells = tuple(str(cell) for cell in cells)
        if len(cells) < 2 or len(set(cells)) != len(cells):
            raise ValueError("a thinking field needs two or more distinct cells")
        if synapses is None:
            synapses = zip(cells, cells[1:] + cells[:1])
        index = {cell: i for i, cell in enumerate(cells)}
        edges = []
        for source, target in synapses:
            if source not in index or target not in index or source == target:
                raise ValueError(f"invalid synapse {source}->{target}")
            edges.append((index[source], index[target]))
        if len(set(edges)) != len(edges):
            raise ValueError("duplicate synapse")
        outs = [sum(1 for s, _ in edges if s == i) for i in range(len(cells))]
        ins = [sum(1 for _, t in edges if t == i) for i in range(len(cells))]
        if 0 in outs or 0 in ins:
            raise ValueError("every cell needs at least one incoming and one outgoing synapse")
        for name, value in (("conversion", conversion), ("circulation", circulation),
                            ("fade", fade), ("dt", dt)):
            if not math.isfinite(value) or value < 0.0 or (name == "dt" and value == 0.0):
                raise ValueError(f"{name} must be finite and non-negative")
        self.cells = cells
        self.edges = tuple(edges)
        self.params = {"conversion": float(conversion), "circulation": float(circulation),
                       "fade": float(fade), "dt": float(dt)}
        self.ideas: list[str] = []
        self.ey = np.zeros((0, len(cells)))
        self.ei = np.zeros((0, len(cells)))
        self.time = 0.0
        self._outs = np.asarray(outs, dtype=np.float64)
        self._ins = np.asarray(ins, dtype=np.float64)

    # ── ideas and cell actions ────────────────────────────────────────────

    def add_idea(self, idea: str) -> int:
        if idea in self.ideas:
            raise ValueError(f"idea {idea} already exists")
        self.ideas.append(idea)
        zero = np.zeros((1, len(self.cells)))
        self.ey = np.vstack([self.ey, zero])
        self.ei = np.vstack([self.ei, zero])
        return len(self.ideas) - 1

    def _site(self, idea: str, cell: str) -> tuple[int, int]:
        return self.ideas.index(idea), self.cells.index(cell)

    def deposit(self, idea: str, cell: str, *, yang: float = 0.0, yin: float = 0.0) -> None:
        if yang < 0.0 or yin < 0.0 or not math.isfinite(yang + yin):
            raise ValueError("deposits are non-negative")
        k, c = self._site(idea, cell)
        self.ey[k, c] += yang
        self.ei[k, c] += yin

    def drain(self, idea: str, cell: str, fraction: float) -> None:
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("drain fraction must lie in [0, 1]")
        k, c = self._site(idea, cell)
        self.ey[k, c] *= 1.0 - fraction
        self.ei[k, c] *= 1.0 - fraction

    def forget(self, idea: str) -> float:
        """Remove an idea's mode from the field and return the density it still carried."""

        k = self.ideas.index(idea)
        carried = float(self.ey[k].sum() + self.ei[k].sum())
        del self.ideas[k]
        self.ey = np.delete(self.ey, k, axis=0)
        self.ei = np.delete(self.ei, k, axis=0)
        return carried

    # ── dynamics ──────────────────────────────────────────────────────────

    def step(self, count: int = 1) -> None:
        p = self.params
        dt = p["dt"]
        keep = math.exp(-p["circulation"] * dt)
        fade = math.exp(-p["fade"] * dt)
        sources = np.asarray([s for s, _ in self.edges], dtype=np.intp)
        targets = np.asarray([t for _, t in self.edges], dtype=np.intp)
        for _ in range(int(count)):
            if not self.ideas:
                self.time += dt
                continue
            rate = p["conversion"] * (1.0 - qi(self.ey, self.ei)) * (1.0 + PHI)
            eps = self.ey - PHI * self.ei
            shift = eps * (np.exp(-rate * dt) - 1.0) / (1.0 + PHI)
            self.ey += shift
            self.ei -= shift
            yang_out = self.ey * (1.0 - keep)
            yin_out = self.ei * (1.0 - keep)
            ey = self.ey - yang_out
            ei = self.ei - yin_out
            yang_share = yang_out / self._outs
            yin_share = yin_out / self._ins
            np.add.at(ey.T, targets, yang_share.T[sources])
            np.add.at(ei.T, sources, yin_share.T[targets])
            self.ey = np.maximum(ey, 0.0) * fade
            self.ei = np.maximum(ei, 0.0) * fade
            self.time += dt

    def breathe(self, duration: float = 1.0) -> None:
        self.step(max(1, round(duration / self.params["dt"])))

    # ── readouts ──────────────────────────────────────────────────────────

    def qi(self) -> np.ndarray:
        return qi(self.ey, self.ei)

    def churn(self) -> np.ndarray:
        """Local conversion power ``lambda (1-q) |eps|`` at every site."""

        return self.params["conversion"] * (1.0 - self.qi()) * np.abs(self.ey - PHI * self.ei)

    def resonance(self) -> np.ndarray:
        """Geometric-mean Qi of each idea over all cells."""

        if not self.ideas:
            return np.zeros(0)
        return np.exp(np.mean(np.log(np.maximum(self.qi(), 1e-12)), axis=1))

    def site(self, idea: str, cell: str) -> dict[str, float]:
        k, c = self._site(idea, cell)
        ey, ei = float(self.ey[k, c]), float(self.ei[k, c])
        return {"yang": ey, "yin": ei, "rho": ey + ei, "qi": float(self.qi()[k, c]),
                "churn": float(self.churn()[k, c])}

    def readout(self) -> dict[str, Any]:
        churn = self.churn()
        resonance = self.resonance()
        return {
            "time": self.time,
            "cell_churn": {cell: float(churn[:, c].sum()) for c, cell in enumerate(self.cells)},
            "resonance": {idea: float(resonance[k]) for k, idea in enumerate(self.ideas)},
            "density": {idea: float((self.ey[k] + self.ei[k]).sum()) for k, idea in enumerate(self.ideas)},
            "max_churn": float(churn.max()) if churn.size else 0.0,
        }

    # ── persistence ───────────────────────────────────────────────────────

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA, "cells": list(self.cells),
            "synapses": [[self.cells[s], self.cells[t]] for s, t in self.edges],
            "params": dict(self.params), "time": self.time, "ideas": list(self.ideas),
            "ey": self.ey.tolist(), "ei": self.ei.tolist(),
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "ThinkingField":
        if payload.get("schema") != SCHEMA:
            raise ValueError("not a thinking field")
        field = cls(payload["cells"], [tuple(edge) for edge in payload["synapses"]], **payload["params"])
        field.ideas = list(payload["ideas"])
        shape = (len(field.ideas), len(field.cells))
        field.ey = np.asarray(payload["ey"], dtype=np.float64).reshape(shape)
        field.ei = np.asarray(payload["ei"], dtype=np.float64).reshape(shape)
        field.time = float(payload["time"])
        return field

    def save(self, path: str | os.PathLike[str]) -> None:
        path = Path(path)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_json()), encoding="utf-8")
        os.replace(temporary, path)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "ThinkingField":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
