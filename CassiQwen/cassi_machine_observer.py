"""Bounded, observational machine telemetry for authorized Cassi requests.

The observer never schedules and never holds a physical lease.  It records
request timing samples around the entity's own brain calls and runs one
low-frequency background thread that samples OS counters (CPU, RAM, disk,
page faults, and GPU process memory when Windows exposes them) at a fixed
interval.  Sampling stays off the per-token path: one background thread per
process, no shell invocation per token, no device synchronization.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from collections import deque
from typing import Any, Mapping

try:
    import psutil
except Exception as _psutil_exc:  # pragma: no cover - exercised only without psutil
    psutil = None
    _PSUTIL_ERROR = f"{type(_psutil_exc).__name__}: {str(_psutil_exc)[:160]}"
else:
    _PSUTIL_ERROR = None


_PROCESS_DELTA_KEYS = (
    "process_rss_bytes",
    "process_cpu_seconds",
    "process_read_bytes",
    "process_write_bytes",
    "process_page_faults",
)


def _ceil(value: float) -> int:
    whole = int(value)
    return whole if whole == value else whole + 1


def _percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile on sorted values (ceil(p*n)-1)."""

    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, _ceil(p * len(ordered)) - 1))
    return float(ordered[index])


class _GpuProcessMemorySampler:
    """Optional Windows PDH reader for this process's GPU memory usage.

    Pure OS counter API: no shell, no driver calls, no device sync.  The
    counter set reports the GPU shared/dedicated bytes attributed to our
    process; absence is reported as an explicit unavailable marker.
    """

    _RECHECK_EVERY = 16

    def __init__(self, pid: int) -> None:
        self._pid = int(pid)
        self._pdh = ctypes.windll.pdh if os.name == "nt" else None
        self._query = None
        self._counter = None
        self._installed = False
        self._checks = 0
        self._failed = False
        self._error: str | None = None

    @property
    def error(self) -> str | None:
        return self._error

    def _close_query(self) -> None:
        if self._query is not None:
            try:
                self._pdh.PdhCloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._counter = None
        self._installed = False

    def _fail(self, reason: str) -> None:
        self._close_query()
        self._failed = True
        if self._error is None:
            self._error = reason

    def _enum_instances(self) -> list[str]:
        counter_list = ctypes.create_unicode_buffer(65536)
        counter_size = ctypes.c_ulong(65536)
        instance_list = ctypes.create_unicode_buffer(65536)
        instance_size = ctypes.c_ulong(65536)
        result = self._pdh.PdhEnumObjectItemsW(
            None, None, "GPU Process Memory",
            counter_list, ctypes.byref(counter_size),
            instance_list, ctypes.byref(instance_size),
            None, None, 0,
        )
        if (result & 0xFFFFFFFF) != 0:
            raise OSError(f"PdhEnumObjectItemsW failed: 0x{result & 0xFFFFFFFF:08x}")
        raw = instance_list.value
        return [item for item in raw.split("\0") if item] if raw else []

    def _install(self, instances: list[str]) -> bool:
        wanted = f"pid_{self._pid}_"
        matches = [item for item in instances if item.startswith(wanted)]
        if not matches:
            return False
        query = ctypes.c_void_p()
        if (self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) & 0xFFFFFFFF) != 0:
            self._fail("PDH GPU query could not be opened")
            return False
        installed: list[Any] = []
        for instance in matches:
            path = f"\\GPU Process Memory({instance})\\Shared Usage"
            counter = ctypes.c_void_p()
            result = self._pdh.PdhAddEnglishCounterW(query, path, None, ctypes.byref(counter))
            if (result & 0xFFFFFFFF) == 0:
                installed.append(counter)
        if not installed:
            self._pdh.PdhCloseQuery(query)
            self._fail("PDH GPU counter could not be opened for this process")
            return False
        self._query = query
        self._counter = installed
        self._installed = True
        return True

    def sample(self) -> int | None:
        """Return total GPU bytes attributed to this process, or None."""

        if self._failed:
            return None
        if self._installed and self._checks >= self._RECHECK_EVERY:
            # A device attach or driver restart may add instances; re-check
            # occasionally and rebuild if the installed handle disappears.
            self._checks = 0
            try:
                instances = self._enum_instances()
                installed = any(f"pid_{self._pid}_" in item for item in instances)
                if not installed:
                    self._close_query()
                elif self._query is None:
                    self._install(instances)
            except Exception as exc:
                if self._query is None:
                    self._fail(f"{type(exc).__name__}: {str(exc)[:120]}")
        if not self._installed:
            self._checks += 1
            try:
                instances = self._enum_instances()
            except Exception as exc:
                self._fail(f"{type(exc).__name__}: {str(exc)[:120]}")
                return None
            if not self._install(instances):
                self._checks += 1
                return None
        if self._query is None or self._counter is None:
            return None
        if (self._pdh.PdhCollectQueryData(self._query) & 0xFFFFFFFF) != 0:
            self._close_query()
            self._fail("PDH GPU counter collection failed")
            return None
        total = 0
        for counter in self._counter:
            value = _PdhRawCounter()
            status = ctypes.c_ulong()
            result = self._pdh.PdhGetRawCounterValue(counter, ctypes.byref(status), ctypes.byref(value))
            if (result & 0xFFFFFFFF) != 0 or (value.CStatus & 0xFFFFFFFF) != 0:
                self._close_query()
                self._fail("PDH GPU counter read failed")
                return None
            total += max(0, int(value.FirstValue))
        return total


class _PdhRawCounterUnion(ctypes.Union):
    _fields_ = [
        ("longValue", ctypes.c_long),
        ("doubleValue", ctypes.c_double),
        ("largeValue", ctypes.c_longlong),
        ("AnsiStringValue", ctypes.c_void_p),
        ("WideStringValue", ctypes.c_void_p),
    ]


class _PdhRawCounter(ctypes.Structure):
    _fields_ = [
        ("CStatus", ctypes.c_ulong),
        ("TimeStamp", ctypes.c_ulong * 4),
        ("FirstValue", ctypes.c_longlong),
        ("SecondValue", ctypes.c_longlong),
        ("MultiCount", ctypes.c_ulong),
    ]


class CassiMachineObserver:
    """Collect bounded request timings and best-effort process resource deltas."""

    _LIMIT = 256
    _WINDOW_SECONDS = 300.0
    _SAMPLE_LEVELS = (1, 2, 4, 8)
    _SYSTEM_SAMPLE_INTERVAL_SECONDS = 2.0
    _SYSTEM_SAMPLE_LIMIT = 512
    _PAUSE_LIMIT = 512
    # A recommendation never hikes past the host reserve it measured: below
    # the floor no concurrency beyond one is proposed; above it, one slot per
    # 2 GiB of available RAM, capped at 8.
    _RESERVE_FLOOR_BYTES = 2 * 1024**3
    _RESERVE_CHUNK_BYTES = 2 * 1024**3
    _PAGE_FAULT_RATE_BUDGET = 2000.0
    _DISK_LATENCY_BUDGET_MS_PER_IO = 25.0
    _PAUSE_TAIL_BUDGET_MS = 5000.0

    def __init__(self, *, sample_interval_seconds: float | None = None) -> None:
        self._lock = threading.Lock()
        self._samples: deque[dict[str, Any]] = deque(maxlen=self._LIMIT)
        self._pending: dict[int, dict[str, Any]] = {}
        self._next_id = 0
        self._process = None
        self._process_error: str | None = _PSUTIL_ERROR
        if psutil is not None:
            try:
                self._process = psutil.Process(os.getpid())
            except Exception as exc:
                self._process_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        self._system_samples: deque[dict[str, Any]] = deque(maxlen=self._SYSTEM_SAMPLE_LIMIT)
        self._pauses: deque[dict[str, Any]] = deque(maxlen=self._PAUSE_LIMIT)
        self._sample_interval = (
            float(sample_interval_seconds)
            if sample_interval_seconds is not None
            else self._SYSTEM_SAMPLE_INTERVAL_SECONDS
        )
        self._sampler_thread: threading.Thread | None = None
        self._sampler_stop = threading.Event()
        self._sampler_overhead_ns = 0
        self._sampler_cycles = 0
        self._request_capture_overhead_ns = 0
        self._request_capture_count = 0
        self._previous_system: dict[str, Any] | None = None
        self._gpu = _GpuProcessMemorySampler(os.getpid()) if os.name == "nt" else None
        self._gpu_error: str | None = None if os.name == "nt" else "Windows PDH provider is unavailable on this platform"

    # ------------------------------------------------------------------
    # Process snapshot helpers
    # ------------------------------------------------------------------
    def _process_snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "process_rss_bytes": None,
            "process_cpu_seconds": None,
            "process_read_bytes": None,
            "process_write_bytes": None,
            "process_page_faults": None,
        }
        if self._process is None:
            for key in result:
                result["unavailable_" + key] = self._process_error or "psutil unavailable"
            return result
        try:
            memory = self._process.memory_info()
            result["process_rss_bytes"] = int(memory.rss)
        except Exception as exc:
            result["unavailable_process_rss_bytes"] = type(exc).__name__
        try:
            times = self._process.cpu_times()
            result["process_cpu_seconds"] = float(times.user + times.system)
        except Exception as exc:
            result["unavailable_process_cpu_seconds"] = type(exc).__name__
        try:
            io = self._process.io_counters()
            result["process_read_bytes"] = int(io.read_bytes)
            result["process_write_bytes"] = int(io.write_bytes)
        except Exception as exc:
            result["unavailable_process_io_bytes"] = type(exc).__name__
        try:
            faults = getattr(self._process.memory_info(), "num_page_faults", None)
            if faults is None:
                result["unavailable_process_page_faults"] = "platform does not expose process page faults"
            else:
                result["process_page_faults"] = int(faults)
        except Exception as exc:
            result["unavailable_process_page_faults"] = type(exc).__name__
        return result

    def _system_memory_snapshot(self) -> dict[str, Any]:
        if psutil is None:
            return {"unavailable_system_available_ram_bytes": self._process_error or "psutil unavailable"}
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                "system_total_ram_bytes": int(memory.total),
                "system_available_ram_bytes": int(memory.available),
                "system_ram_used_percent": float(memory.percent),
                "system_swap_used_bytes": int(swap.used),
            }
        except Exception as exc:
            return {"unavailable_system_available_ram_bytes": type(exc).__name__}

    # ------------------------------------------------------------------
    # Background system sampler
    # ------------------------------------------------------------------
    def _ensure_sampler(self) -> None:
        with self._lock:
            if self._sampler_thread is not None or self._sampler_stop.is_set():
                return
            thread = threading.Thread(
                target=self._sampler_loop,
                name="cassi-machine-observer-sampler",
                daemon=True,
            )
            self._sampler_thread = thread
        thread.start()

    def close(self) -> None:
        with self._lock:
            self._sampler_stop.set()
            self._sampler_thread = None
        self._sampler_stop.set()

    def _sampler_loop(self) -> None:
        interval = self._sample_interval
        while True:
            started = time.perf_counter()
            try:
                self._system_tick()
            except Exception:
                pass
            with self._lock:
                self._sampler_overhead_ns += int((time.perf_counter() - started) * 1_000_000_000)
                self._sampler_cycles += 1
            if self._sampler_stop.wait(max(0.05, interval)):
                return

    def _system_tick(self) -> None:
        now = time.monotonic_ns()
        previous = self._previous_system
        sample: dict[str, Any] = {
            "sampled_at_monotonic_ns": now,
            "wall_interval_ns": None if previous is None else now - int(previous["sampled_at_monotonic_ns"]),
            "provenance": "monotonic sampler clock; psutil system/current-process counters; Windows PDH GPU Process Memory counter",
            "system": {},
            "process": {},
            "derived": {},
            "unavailable": {},
        }
        system = sample["system"]
        process = sample["process"]
        derived = sample["derived"]
        unavailable = sample["unavailable"]

        memory_snapshot = self._system_memory_snapshot()
        for key, value in memory_snapshot.items():
            if key.startswith("unavailable_"):
                unavailable[key[len("unavailable_"):]] = value
            else:
                system[key] = value

        if self._process is not None:
            process_snapshot = self._process_snapshot()
            for key, value in process_snapshot.items():
                if key.startswith("unavailable_"):
                    unavailable[key[len("unavailable_"):]] = value
                else:
                    process[key] = value
            try:
                process["process_cpu_utilization_percent"] = self._process.cpu_percent(None)
            except Exception as exc:
                unavailable["process_cpu_utilization_percent"] = type(exc).__name__

        if psutil is not None:
            try:
                disk = psutil.disk_io_counters()
                if disk is None:
                    unavailable["disk"] = "no physical disk counters reported by the OS"
                else:
                    system["disk_read_bytes"] = int(disk.read_bytes)
                    system["disk_write_bytes"] = int(disk.write_bytes)
                    system["disk_read_count"] = int(disk.read_count)
                    system["disk_write_count"] = int(disk.write_count)
                    system["disk_read_time_ms"] = int(disk.read_time)
                    system["disk_write_time_ms"] = int(disk.write_time)
            except Exception as exc:
                unavailable["disk"] = type(exc).__name__
            try:
                system["system_cpu_utilization_percent"] = float(psutil.cpu_percent(None))
            except Exception as exc:
                unavailable["system_cpu_utilization_percent"] = type(exc).__name__
        else:
            unavailable["disk"] = self._process_error or "psutil unavailable"

        if self._gpu is not None:
            try:
                gpu_bytes = self._gpu.sample()
                if gpu_bytes is None:
                    unavailable["gpu_memory_bytes"] = self._gpu.error or (
                        "Windows exposes no GPU Process Memory counter instance for this process yet"
                    )
                else:
                    system["gpu_process_memory_bytes"] = gpu_bytes
                    self._gpu_error = None
            except Exception as exc:
                self._gpu._fail(f"{type(exc).__name__}: {str(exc)[:120]}")
                unavailable["gpu_memory_bytes"] = self._gpu.error or type(exc).__name__
        elif self._gpu_error:
            unavailable["gpu_memory_bytes"] = self._gpu_error

        with self._lock:
            previous_sample = self._system_samples[-1] if self._system_samples else None
            self._system_samples.append(sample)
            self._previous_system = sample

        # Derive interval rates from the stored counter deltas.
        if previous_sample is not None and sample["wall_interval_ns"]:
            seconds = sample["wall_interval_ns"] / 1_000_000_000
            previous_system = previous_sample.get("system", {})
            previous_process = previous_sample.get("process", {})
            if (
                isinstance(system.get("disk_read_bytes"), int)
                and isinstance(previous_system.get("disk_read_bytes"), int)
            ):
                read_delta = max(0, system["disk_read_bytes"] - previous_system["disk_read_bytes"])
                write_delta = max(0, system["disk_write_bytes"] - previous_system["disk_write_bytes"])
                count_delta = max(
                    0,
                    (system["disk_read_count"] - previous_system["disk_read_count"])
                    + (system["disk_write_count"] - previous_system["disk_write_count"]),
                )
                time_delta_ms = max(
                    0,
                    (system["disk_read_time_ms"] - previous_system["disk_read_time_ms"])
                    + (system["disk_write_time_ms"] - previous_system["disk_write_time_ms"]),
                )
                derived["disk_read_bytes_per_second"] = round(read_delta / seconds, 3)
                derived["disk_write_bytes_per_second"] = round(write_delta / seconds, 3)
                derived["disk_iops"] = round(count_delta / seconds, 3)
                derived["disk_avg_io_latency_ms"] = (
                    round(time_delta_ms / count_delta, 4) if count_delta > 0 else None
                )
            if (
                isinstance(process.get("process_page_faults"), int)
                and isinstance(previous_process.get("process_page_faults"), int)
            ):
                derived["process_page_faults_per_second"] = round(
                    max(0, process["process_page_faults"] - previous_process["process_page_faults"]) / seconds,
                    3,
                )

    # ------------------------------------------------------------------
    # Request-scoped sampling
    # ------------------------------------------------------------------
    def begin(self, *, foreground: bool, queued: Mapping[str, int]) -> int:
        started = time.perf_counter()
        before = self._process_snapshot()
        self._ensure_sampler()
        now = time.monotonic_ns()
        with self._lock:
            sample_id = self._next_id
            self._next_id += 1
            self._pending[sample_id] = {
                "started": now,
                "foreground": bool(foreground),
                "before": before,
                "first_useful_ns": None,
            }
            self._request_capture_overhead_ns += int((time.perf_counter() - started) * 1_000_000_000)
            self._request_capture_count += 1
            return sample_id

    def record_pause_event(
        self, *, foreground: bool, pause_ns: int, first_useful: bool
    ) -> None:
        """Scheduler hook: one segment pause (and possibly a first useful segment)."""

        now = time.monotonic_ns()
        try:
            with self._lock:
                target = None
                for pending in self._pending.values():
                    if bool(pending.get("foreground")) == bool(foreground):
                        target = pending
                        break
                if target is not None and first_useful and target.get("first_useful_ns") is None:
                    target["first_useful_ns"] = now
                self._pauses.append(
                    {
                        "observed_at_monotonic_ns": now,
                        "priority": "foreground" if foreground else "background",
                        "pause_ms": round(max(0, int(pause_ns)) / 1_000_000, 3),
                        "first_useful_segment": bool(first_useful),
                        "provenance": "scheduler segment-yield pause, monotonic clock",
                    }
                )
        except Exception:
            pass

    def finish(
        self,
        sample_id: int,
        *,
        foreground: bool,
        queue_wait_ns: int | None,
        response: Any,
        error: BaseException | None,
        batch_size: Any = None,
        segment_pause_ns: int | None = None,
        segment_pause_count: int | None = None,
    ) -> None:
        started_capture = time.perf_counter()
        after = self._process_snapshot()
        with self._lock:
            pending = self._pending.pop(sample_id, None)
            if pending is None:
                self._request_capture_overhead_ns += int((time.perf_counter() - started_capture) * 1_000_000_000)
                self._request_capture_count += 1
                return
            started, _was_foreground, before = (
                pending["started"],
                pending["foreground"],
                pending["before"],
            )
            first_useful_ns = pending.get("first_useful_ns")
            usage = response.get("usage") if isinstance(response, Mapping) else None
            timings = response.get("timings") if isinstance(response, Mapping) else None
            output_tokens = usage.get("completion_tokens") if isinstance(usage, Mapping) else None
            prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, Mapping) else None
            predicted_n = timings.get("predicted_n") if isinstance(timings, Mapping) else None
            prompt_n = timings.get("prompt_n") if isinstance(timings, Mapping) else None
            cache_reused_tokens = (
                prompt_tokens - prompt_n
                if isinstance(prompt_tokens, int)
                and isinstance(prompt_n, int)
                and prompt_tokens >= prompt_n >= 0
                else None
            )
            ended = time.monotonic_ns()
            sample = {
                "observed_at_monotonic_ns": ended,
                "priority": "foreground" if foreground else "background",
                "queue_wait_ms": round(queue_wait_ns / 1_000_000, 3) if queue_wait_ns is not None else None,
                "arrival_to_useful_response_ms": (
                    round((first_useful_ns - started) / 1_000_000, 3)
                    if error is None and first_useful_ns is not None
                    else None
                ),
                "arrival_to_completion_ms": round((ended - started) / 1_000_000, 3),
                "full_completion_ms": round((ended - started) / 1_000_000, 3),
                "status": "completed" if error is None else "failed",
                "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
                "batch_size": batch_size if isinstance(batch_size, int) and not isinstance(batch_size, bool) else None,
                "segment_pause_ms": (
                    round(segment_pause_ns / 1_000_000, 3)
                    if isinstance(segment_pause_ns, (int, float)) and not isinstance(segment_pause_ns, bool)
                    else None
                ),
                "segment_pause_count": (
                    segment_pause_count
                    if isinstance(segment_pause_count, int) and not isinstance(segment_pause_count, bool)
                    else None
                ),
                "resources_before": before,
                "resources_after": after,
                "resource_deltas": {
                    key: after.get(key) - before.get(key)
                    for key in _PROCESS_DELTA_KEYS
                    if isinstance(before.get(key), (int, float)) and isinstance(after.get(key), (int, float))
                },
                "bytes_moved": (
                    max(0, int(after.get("process_read_bytes") - before["process_read_bytes"]))
                    + max(0, int(after.get("process_write_bytes") - before["process_write_bytes"]))
                    if isinstance(before.get("process_read_bytes"), int)
                    and isinstance(after.get("process_read_bytes"), int)
                    and isinstance(before.get("process_write_bytes"), int)
                    and isinstance(after.get("process_write_bytes"), int)
                    else None
                ),
                "work_counters": {
                    "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else None,
                    "completion_tokens": output_tokens if isinstance(output_tokens, int) else None,
                    "backend_prompt_n": prompt_n if isinstance(prompt_n, int) else None,
                    "backend_predicted_n": predicted_n if isinstance(predicted_n, int) else None,
                    "cache_reused_tokens": cache_reused_tokens,
                },
                "expert_hits": None,
                "activity_state": "running" if error is None else "failed",
                "provenance": "monotonic request clock; psutil current-process counters; brain response usage/timings when supplied",
                "unavailable": {
                    "expert_hits": "brain backend exposes no expert-hit counter",
                    "batch_size": "brain backend exposes no executed batch-size counter" if not isinstance(batch_size, int) or isinstance(batch_size, bool) else None,
                    "arrival_to_useful_response_ms": (
                        None
                        if error is None and first_useful_ns is not None
                        else "no segment-yield boundary reached before completion; backend exposes no earlier first-token callback"
                    ),
                    "cache_reused_tokens": (
                        None
                        if cache_reused_tokens is not None
                        else "brain timings expose no prompt_n counter to separate reused-prefix tokens"
                    ),
                },
            }
            self._samples.append(sample)
            self._request_capture_overhead_ns += int((time.perf_counter() - started_capture) * 1_000_000_000)
            self._request_capture_count += 1

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def _windowed_system(self, now: int, horizon: int) -> dict[str, Any]:
        system = self._system_samples
        recent = [s for s in system if now - int(s["sampled_at_monotonic_ns"]) <= horizon]
        latest = system[-1] if system else None
        derived_values: dict[str, list[float]] = {}
        unavailable: dict[str, str] = {}
        for sample in recent:
            for key, value in sample.get("derived", {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    derived_values.setdefault(key, []).append(float(value))
            for key, value in sample.get("unavailable", {}).items():
                unavailable.setdefault(key, str(value))
        rates = {
            key: round(sum(values) / len(values), 4)
            for key, values in derived_values.items()
        }
        latest_system = latest.get("system", {}) if latest else {}
        latest_process = latest.get("process", {}) if latest else {}
        return {
            "sampling_interval_seconds": self._sample_interval,
            "sample_count": len(recent),
            "latest": {
                key: value
                for key, value in {**latest_system, **latest_process}.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            },
            "rates_window_average": rates,
            "provenance": "monotonic sampler clock; psutil current-process/system counters; Windows PDH GPU Process Memory counter",
            "unavailable": unavailable,
        }

    def status(
        self, *, queues: Mapping[str, int], available_capacity: bool | None = None
    ) -> dict[str, Any]:
        self._ensure_sampler()
        now = time.monotonic_ns()
        horizon = int(self._WINDOW_SECONDS * 1_000_000_000)
        with self._lock:
            samples = [s for s in self._samples if now - int(s["observed_at_monotonic_ns"]) <= horizon]
            pauses = [p for p in self._pauses if now - int(p["observed_at_monotonic_ns"]) <= horizon]
            latest_samples = [dict(s) for s in list(self._samples)[-16:]]
            sampler_overhead_ns = self._sampler_overhead_ns
            sampler_cycles = self._sampler_cycles
            request_overhead_ns = self._request_capture_overhead_ns
            request_capture_count = self._request_capture_count
        completed = [s for s in samples if s["status"] == "completed"]
        def series(selector, items=completed):
            values = []
            for item in items:
                value = selector(item)
                if value is not None:
                    values.append(float(value))
            return values

        latency = series(lambda s: s["arrival_to_completion_ms"])
        useful = series(lambda s: s["arrival_to_useful_response_ms"])
        foreground = [s for s in completed if s["priority"] == "foreground"]
        background = [s for s in completed if s["priority"] == "background"]
        foreground_full = series(lambda s: s["full_completion_ms"], foreground)
        foreground_useful = [s for s in foreground if s["arrival_to_useful_response_ms"] is not None]
        foreground_useful_series = series(lambda s: s["arrival_to_useful_response_ms"], foreground_useful)
        queue_wait = series(lambda s: s["queue_wait_ms"])
        active = [float(s["full_completion_ms"]) - float(s["queue_wait_ms"])
                  for s in completed
                  if s["queue_wait_ms"] is not None
                  and float(s["full_completion_ms"]) - float(s["queue_wait_ms"]) >= 0]
        pause_values = [float(p["pause_ms"]) for p in pauses]

        def pct(values, p):
            return _percentile(values, p)

        window_first = min((int(s["observed_at_monotonic_ns"]) for s in completed), default=now)
        window_last = max((int(s["observed_at_monotonic_ns"]) for s in completed), default=now)
        span_seconds = max(1e-9, (window_last - window_first) / 1_000_000_000)

        if available_capacity is None:
            with self._lock:
                system = list(self._system_samples)
            latest_system = system[-1].get("system", {}) if system else {}
            latest_ram = latest_system.get("system_available_ram_bytes")
            available_capacity = isinstance(latest_ram, int) and latest_ram > 0

        full_p95 = pct(foreground_full, 0.95)
        useful_p95 = pct(foreground_useful_series, 0.95)
        recommendation = self._recommendation(
            completed=completed,
            foreground_count=len(foreground),
            useful_p95=useful_p95,
            full_p95=full_p95,
            pause_values=pause_values,
            queues=queues,
            now=now,
            horizon=horizon,
        )

        return {
            "schema": "cassi.machine-observer.v2",
            "window_seconds": self._WINDOW_SECONDS,
            "sample_limit": self._LIMIT,
            "sample_count": len(samples),
            "request_count": len(completed),
            "throughput_requests_per_second": (
                round(len(completed) / span_seconds, 6) if len(completed) >= 2 else
                (0.0 if len(completed) == 0 else None)
            ),
            "throughput_window_seconds": round(span_seconds, 6) if len(completed) >= 2 else None,
            "latency_ms": {"p50": pct(latency, 0.50), "p95": pct(latency, 0.95), "p99": pct(latency, 0.99)},
            "useful_response_ms": {
                "p50": pct(useful, 0.50),
                "p95": pct(useful, 0.95),
                "p99": pct(useful, 0.99),
                "sample_count": len(useful),
            },
            "foreground_latency_ms": {
                "p50": pct(foreground_full, 0.50), "p95": full_p95, "p99": pct(foreground_full, 0.99)
            },
            "foreground_useful_response_ms": {
                "p50": pct(foreground_useful_series, 0.50),
                "p95": useful_p95,
                "p99": pct(foreground_useful_series, 0.99),
                "sample_count": len(foreground_useful_series),
            },
            "queue_wait_ms": {"p50": pct(queue_wait, 0.50), "p95": pct(queue_wait, 0.95), "p99": pct(queue_wait, 0.99), "sample_count": len(queue_wait)},
            "active_ms": {"p50": pct(active, 0.50), "p95": pct(active, 0.95), "p99": pct(active, 0.99), "sample_count": len(active)},
            "pause_control_ms": {
                "p50": pct(pause_values, 0.50),
                "p95": pct(pause_values, 0.95),
                "p99": pct(pause_values, 0.99),
                "count": len(pause_values),
                "total_ms": round(sum(pause_values), 3) if pause_values else 0.0,
            },
            "queues": dict(queues),
            "sampling": {
                "compatible_activity_levels": list(self._SAMPLE_LEVELS),
                "recommended_level": recommendation["level"],
                "recommendation": recommendation,
                "capacity_available": available_capacity,
                "automatic_cost_increase": False,
                "policy": (
                    "recommendation from the measured foreground arrival-to-useful/completion tail within the "
                    "measured host reserve (available RAM, page-fault rate, disk latency, pause tail); applied by "
                    "the entity scheduler only for the resident segment-yielding brain, never automatically"
                ),
            },
            "system": self._windowed_system(now, horizon),
            "overhead": {
                "sampler_interval_seconds": self._sample_interval,
                "sampler_cycles": sampler_cycles,
                "sampler_cpu_overhead_seconds_total": round(sampler_overhead_ns / 1_000_000_000, 6),
                "sampler_cpu_overhead_seconds_per_sample": (
                    round(sampler_overhead_ns / sampler_cycles / 1_000_000_000, 6) if sampler_cycles else None
                ),
                "per_request_capture_overhead_seconds_average": (
                    round(request_overhead_ns / request_capture_count / 1_000_000_000, 9)
                    if request_capture_count
                    else None
                ),
                "provenance": "perf_counter deltas around observer-only capture work; excludes brain and scheduler time",
            },
            "latest_samples": latest_samples,
            "unavailable": {
                "device_startup_seconds": "brain startup predates observer attachment",
                "expert_hits": "brain backend exposes no expert-hit counter",
                "batch_size": "backend execution batch size not reported",
                "gpu_thermal_celsius": "no in-process thermal provider for this host; ADLX interface is not C-callable and per-token command probes are forbidden",
                **(
                    {"gpu_memory_bytes": self._gpu_error or "Windows exposes no GPU Process Memory counter instance for this process yet"}
                    if os.name == "nt" and self._gpu_error
                    else {}
                ),
            },
        }

    def _recommendation(
        self,
        *,
        completed: list[dict[str, Any]],
        foreground_count: int,
        useful_p95: float | None,
        full_p95: float | None,
        pause_values: list[float],
        queues: Mapping[str, int],
        now: int,
        horizon: int,
    ) -> dict[str, Any]:
        foreground_count = max(0, foreground_count)
        if not completed:
            return {
                "level": 1,
                "basis": "no completed observations in the 300 s window; idle hosts receive no concurrency hike",
                "confidence": "none",
                "fairness": "single-slot default preserved while no observations exist",
                "reserve": {},
            }
        tail = useful_p95 if useful_p95 is not None else full_p95
        if foreground_count < 8:
            confidence = "low"
        elif foreground_count < 24:
            confidence = "medium"
        else:
            confidence = "high"
        level = 1
        if tail is not None and confidence != "low":
            if foreground_count >= 24 and tail < 250:
                level = 8
            elif foreground_count >= 12 and tail < 500:
                level = 4
            elif tail < 1000:
                level = 2
        reserve_cap = self._SAMPLE_LEVELS[-1]
        reserve: dict[str, Any] = {}
        reasons: list[str] = []
        with self._lock:
            system = list(self._system_samples)
        recent = [s for s in system if now - int(s["sampled_at_monotonic_ns"]) <= horizon]
        latest = system[-1] if system else None
        available = latest.get("system", {}).get("system_available_ram_bytes") if latest else None
        if isinstance(available, int):
            raw_cap = (
                1
                if available < self._RESERVE_FLOOR_BYTES
                else 1 + int((available - self._RESERVE_FLOOR_BYTES) // self._RESERVE_CHUNK_BYTES)
            )
            cap = max(level for level in self._SAMPLE_LEVELS if level <= raw_cap)
            reserve_cap = min(reserve_cap, cap)
            reserve["available_ram_bytes"] = available
            reserve["ram_reserve_cap"] = cap
        else:
            reserve["available_ram_bytes"] = None
            reserve["ram_reserve_cap"] = None
        fault_rates = [
            float(s["derived"]["process_page_faults_per_second"])
            for s in recent
            if isinstance(s.get("derived", {}).get("process_page_faults_per_second"), (int, float))
        ]
        if fault_rates:
            reserve["page_faults_per_second"] = round(max(fault_rates), 3)
        disk_latencies = [
            float(s["derived"]["disk_avg_io_latency_ms"])
            for s in recent
            if isinstance(s.get("derived", {}).get("disk_avg_io_latency_ms"), (int, float))
        ]
        if disk_latencies:
            reserve["disk_avg_io_latency_ms"] = round(max(disk_latencies), 3)
        if fault_rates and max(fault_rates) > self._PAGE_FAULT_RATE_BUDGET:
            reserve_cap = 1
            reasons.append("process page-fault rate exceeded the memory-pressure budget")
        if disk_latencies and max(disk_latencies) > self._DISK_LATENCY_BUDGET_MS_PER_IO:
            reserve_cap = min(reserve_cap, 2)
            reasons.append("disk latency exceeded the IO-pressure budget")
        if pause_values:
            pause_p95 = _percentile(pause_values, 0.95)
            reserve["pause_control_ms_p95"] = pause_p95
            if pause_p95 > self._PAUSE_TAIL_BUDGET_MS:
                reserve_cap = min(reserve_cap, 2)
                reasons.append("segment pause/control tail exceeded the pause budget")
        level = min(level, reserve_cap)
        basis_parts = [
            f"foreground arrival-to-useful p95 {round(useful_p95, 1) if useful_p95 is not None else None} ms / arrival-to-completion p95 {round(full_p95, 1) if full_p95 is not None else None} ms over {foreground_count} foreground completions"
        ]
        basis_parts.append(f"measured reserve caps the level at {reserve_cap}")
        if reasons:
            basis_parts.append("; ".join(reasons))
        return {
            "level": level,
            "basis": " | ".join(basis_parts),
            "confidence": confidence,
            "fairness": {
                "foreground_waiting": int(queues.get("foreground_waiting", 0)),
                "background_waiting": int(queues.get("background_waiting", 0)),
                "policy": "one foreground slot and the foreground burst are scheduler-owned; the recommendation only bounds background concurrency",
            },
            "reserve": reserve,
        }
