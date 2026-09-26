"""Fresh whole-machine telemetry for ordinary physically admitted work.

The observer reports only measurements it can obtain from the host or the
shared resource manager. Missing OS/device counters stay unavailable; this
module does not estimate an unregistered GPU, infer physical core topology,
or run synthetic performance campaigns.
"""
from __future__ import annotations

import ctypes
import math
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Mapping


try:
    import psutil
except Exception as _psutil_exc:  # pragma: no cover - optional on minimal installs
    psutil = None
    _PSUTIL_ERROR = f"{type(_psutil_exc).__name__}: {str(_psutil_exc)[:160]}"
else:
    _PSUTIL_ERROR = None



class _PdhValueUnion(ctypes.Union):
    _fields_ = [
        ("long_value", ctypes.c_long),
        ("double_value", ctypes.c_double),
        ("large_value", ctypes.c_longlong),
        ("ansi_string_value", ctypes.c_void_p),
        ("wide_string_value", ctypes.c_void_p),
    ]


class _PdhFormattedValue(ctypes.Structure):
    _fields_ = [("status", ctypes.c_ulong), ("value", _PdhValueUnion)]


class _WindowsMachineTelemetry:
    """Bounded Windows disk, page-fault, PDH GPU-engine, and adapter-memory sampler."""

    _MAX_DISK_DEVICES = 64
    _MAX_GPU_ENGINES = 64
    _MAX_GPU_ADAPTERS = 32
    _GPU_REFRESH_SAMPLES = 4
    _MAX_PDH_LIST_CHARS = 65536
    _PDH_MORE_DATA = 0x800007D2
    _PDH_DETAIL_WIZARD = 400
    _PDH_FMT_DOUBLE = 0x00000200
    _PDH_VALID_STATUSES = (0, 1)  # PDH_CSTATUS_VALID_DATA / NEW_DATA

    def __init__(self) -> None:
        self._process: Any = None
        self._process_error = _PSUTIL_ERROR or "psutil process counters unavailable"
        if psutil is not None:
            try:
                self._process = psutil.Process(os.getpid())
                self._process_error = ""
            except Exception as exc:
                self._process_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        self._previous_faults: int | None = None
        self._previous_fault_ns: int | None = None
        self._previous_disk: dict[str, tuple[int, int, int, int, int, int]] | None = None
        self._previous_disk_ns: int | None = None
        self._sample_index = 0
        self._pdh: Any = None
        self._query: ctypes.c_void_p | None = None
        self._page_fault_counter: ctypes.c_void_p | None = None
        self._gpu_counters: dict[str, ctypes.c_void_p] = {}
        self._gpu_memory_counters: dict[str, dict[str, ctypes.c_void_p]] = {}
        self._pdh_error: str | None = None
        self._page_fault_error: str | None = None
        self._gpu_error: str | None = None
        self._gpu_details: str | None = None
        self._gpu_memory_error: str | None = None
        self._gpu_memory_details: str | None = None
        self._last_gpu_refresh = -self._GPU_REFRESH_SAMPLES
        self._last_gpu_memory_refresh = -self._GPU_REFRESH_SAMPLES
        self._closed = False
        self._open_pdh()

    @staticmethod
    def _capability(
        provider: str, reason: str | None = None, details: str | None = None,
    ) -> dict[str, Any]:
        return {
            "available": reason is None,
            "provider": provider,
            "reason": reason,
            "details": details,
        }

    @staticmethod
    def _error_code(code: int) -> str:
        return f"0x{int(code) & 0xFFFFFFFF:08x}"

    def _open_pdh(self) -> None:
        try:
            pdh = ctypes.WinDLL("pdh", use_last_error=True)
            pdh.PdhOpenQueryW.argtypes = [
                ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p),
            ]
            pdh.PdhOpenQueryW.restype = ctypes.c_ulong
            pdh.PdhAddEnglishCounterW.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            pdh.PdhAddEnglishCounterW.restype = ctypes.c_ulong
            pdh.PdhEnumObjectItemsW.argtypes = [
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_wchar), ctypes.POINTER(ctypes.c_ulong),
                ctypes.c_ulong, ctypes.c_ulong,
            ]
            pdh.PdhEnumObjectItemsW.restype = ctypes.c_ulong
            pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
            pdh.PdhCollectQueryData.restype = ctypes.c_ulong
            pdh.PdhGetFormattedCounterValue.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(_PdhFormattedValue),
            ]
            pdh.PdhGetFormattedCounterValue.restype = ctypes.c_ulong
            pdh.PdhRemoveCounter.argtypes = [ctypes.c_void_p]
            pdh.PdhRemoveCounter.restype = ctypes.c_ulong
            pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
            pdh.PdhCloseQuery.restype = ctypes.c_ulong
            self._pdh = pdh
        except Exception as exc:
            self._pdh_error = f"Windows PDH provider unavailable: {type(exc).__name__}: {str(exc)[:160]}"
            self._page_fault_error = self._pdh_error
            self._gpu_error = self._pdh_error
            return

        query = ctypes.c_void_p()
        status = int(self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) or 0) & 0xFFFFFFFF
        if status:
            self._pdh_error = f"PdhOpenQueryW failed with {self._error_code(status)}"
            self._page_fault_error = self._pdh_error
            self._gpu_error = self._pdh_error
            return
        self._query = query
        self._page_fault_counter, self._page_fault_error = self._add_counter(
            r"\Memory\Page Faults/sec",
        )

    def _add_counter(
        self, path: str,
    ) -> tuple[ctypes.c_void_p | None, str | None]:
        if self._pdh is None or self._query is None:
            return None, self._pdh_error or "PDH query is unavailable"
        counter = ctypes.c_void_p()
        status = int(self._pdh.PdhAddEnglishCounterW(
            self._query, path, 0, ctypes.byref(counter),
        ) or 0) & 0xFFFFFFFF
        if status:
            return None, f"PdhAddEnglishCounterW({path}) failed with {self._error_code(status)}"
        return counter, None

    def _enum_instances(self, object_name: str) -> list[str]:
        size_counters = ctypes.c_ulong(0)
        size_instances = ctypes.c_ulong(0)
        status = int(self._pdh.PdhEnumObjectItemsW(
            None, None, object_name, None, ctypes.byref(size_counters),
            None, ctypes.byref(size_instances), self._PDH_DETAIL_WIZARD, 0,
        ) or 0) & 0xFFFFFFFF
        if status not in (0, self._PDH_MORE_DATA):
            raise OSError(
                f"PdhEnumObjectItemsW({object_name}) failed with {self._error_code(status)}",
            )
        if size_instances.value <= 1:
            return []
        if (
            size_counters.value > self._MAX_PDH_LIST_CHARS
            or size_instances.value > self._MAX_PDH_LIST_CHARS
        ):
            raise OSError(
                f"PdhEnumObjectItemsW({object_name}) exceeded the "
                f"{self._MAX_PDH_LIST_CHARS}-character buffer cap",
            )
        counter_list = ctypes.create_unicode_buffer(max(1, size_counters.value))
        instance_list = ctypes.create_unicode_buffer(max(1, size_instances.value))
        status = int(self._pdh.PdhEnumObjectItemsW(
            None, None, object_name, counter_list, ctypes.byref(size_counters),
            instance_list, ctypes.byref(size_instances), self._PDH_DETAIL_WIZARD, 0,
        ) or 0) & 0xFFFFFFFF
        if status:
            raise OSError(
                f"PdhEnumObjectItemsW({object_name}) failed with {self._error_code(status)}",
            )
        return sorted({
            item for item in instance_list[:size_instances.value].split("\0") if item
        })

    def _refresh_gpu_counters(self) -> None:
        self._last_gpu_refresh = self._sample_index
        if self._pdh_error is not None:
            self._gpu_error = self._pdh_error
            return
        try:
            instances = self._enum_instances("GPU Engine")
        except Exception as exc:
            self._gpu_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            return
        selected = instances[:self._MAX_GPU_ENGINES]
        self._gpu_details = (
            f"sampled {len(selected)} of {len(instances)} GPU Engine instances "
            f"(limit {self._MAX_GPU_ENGINES})"
            if len(instances) > len(selected) else None
        )
        if selected == list(self._gpu_counters):
            if not selected:
                self._gpu_error = "PDH GPU Engine object returned no counter instances"
            return
        for counter in self._gpu_counters.values():
            self._pdh.PdhRemoveCounter(counter)
        self._gpu_counters.clear()
        failures: list[str] = []
        for instance in selected:
            path = f"\\GPU Engine({instance})\\Utilization Percentage"
            counter, reason = self._add_counter(path)
            if counter is not None:
                self._gpu_counters[instance] = counter
            elif reason is not None and len(failures) < 3:
                failures.append(reason)
        self._gpu_error = (
            "; ".join(failures)
            if failures else
            None if self._gpu_counters else
            "PDH GPU Engine object returned no counter instances"
        )

    def _refresh_gpu_memory_counters(self) -> None:
        self._last_gpu_memory_refresh = self._sample_index
        if self._pdh_error is not None:
            self._gpu_memory_error = self._pdh_error
            return
        try:
            instances = self._enum_instances("GPU Adapter Memory")
        except Exception as exc:
            self._gpu_memory_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            return
        selected = instances[:self._MAX_GPU_ADAPTERS]
        self._gpu_memory_details = (
            f"sampled {len(selected)} of {len(instances)} GPU Adapter Memory instances "
            f"(limit {self._MAX_GPU_ADAPTERS})"
            if len(instances) > len(selected) else None
        )
        if selected == list(self._gpu_memory_counters):
            if not selected:
                self._gpu_memory_error = (
                    "PDH GPU Adapter Memory object returned no adapter instances"
                )
            return
        for row in self._gpu_memory_counters.values():
            for counter in row.values():
                self._pdh.PdhRemoveCounter(counter)
        self._gpu_memory_counters.clear()
        failures: list[str] = []
        for instance in selected:
            counters: dict[str, ctypes.c_void_p] = {}
            for label, counter_name in (
                ("dedicated", "Dedicated Usage"),
                ("shared", "Shared Usage"),
            ):
                path = f"\\GPU Adapter Memory({instance})\\{counter_name}"
                counter, reason = self._add_counter(path)
                if counter is not None:
                    counters[label] = counter
                elif reason is not None and len(failures) < 3:
                    failures.append(reason)
            if counters:
                self._gpu_memory_counters[instance] = counters
        self._gpu_memory_error = (
            "; ".join(failures)
            if failures else
            None if self._gpu_memory_counters else
            "PDH GPU Adapter Memory object returned no counter instances"
        )

    def _formatted_value(
        self, counter: ctypes.c_void_p,
    ) -> tuple[float | None, str | None]:
        value = _PdhFormattedValue()
        counter_type = ctypes.c_ulong()
        status = int(self._pdh.PdhGetFormattedCounterValue(
            counter, self._PDH_FMT_DOUBLE, ctypes.byref(counter_type), ctypes.byref(value),
        ) or 0) & 0xFFFFFFFF
        if status:
            return None, f"PdhGetFormattedCounterValue failed with {self._error_code(status)}"
        counter_status = int(value.status) & 0xFFFFFFFF
        if counter_status not in self._PDH_VALID_STATUSES:
            return None, f"PDH counter has no valid sample ({self._error_code(counter_status)})"
        number = float(value.value.double_value)
        if not math.isfinite(number):
            return None, "PDH returned a non-finite counter value"
        return number, None

    def _pdh_sample(
        self,
    ) -> tuple[float | None, dict[str, float], dict[str, dict[str, int]], dict[str, Any]]:
        page_fault_provider = "Windows PDH Memory\\Page Faults/sec"
        engine_provider = "Windows PDH GPU Engine\\Utilization Percentage"
        gpu_memory_provider = (
            "Windows PDH GPU Adapter Memory Dedicated Usage and Shared Usage"
        )
        if self._pdh_error is not None:
            return None, {}, {}, {
                "system_page_faults_per_second": self._capability(
                    page_fault_provider, self._pdh_error,
                ),
                "gpu_engine_utilization_percent": self._capability(
                    engine_provider, self._gpu_error or self._pdh_error,
                ),
                "gpu_adapter_memory_bytes": self._capability(
                    gpu_memory_provider, self._gpu_memory_error or self._pdh_error,
                ),
            }
        self._sample_index += 1
        if self._sample_index - self._last_gpu_refresh >= self._GPU_REFRESH_SAMPLES:
            self._refresh_gpu_counters()
        if (
            self._sample_index - self._last_gpu_memory_refresh
            >= self._GPU_REFRESH_SAMPLES
        ):
            self._refresh_gpu_memory_counters()
        status = int(self._pdh.PdhCollectQueryData(self._query) or 0) & 0xFFFFFFFF
        if status:
            reason = f"PdhCollectQueryData failed with {self._error_code(status)}"
            return None, {}, {}, {
                "system_page_faults_per_second": self._capability(
                    page_fault_provider, reason,
                ),
                "gpu_engine_utilization_percent": self._capability(
                    engine_provider, reason,
                ),
                "gpu_adapter_memory_bytes": self._capability(
                    gpu_memory_provider, reason,
                ),
            }

        page_faults = None
        page_fault_reason = self._page_fault_error
        if self._page_fault_counter is not None:
            page_faults, page_fault_reason = self._formatted_value(self._page_fault_counter)
            if page_faults is not None:
                page_faults = round(max(0.0, page_faults), 3)

        engines: dict[str, float] = {}
        engine_read_errors: list[str] = []
        for instance, counter in self._gpu_counters.items():
            value, reason = self._formatted_value(counter)
            if value is not None:
                engines[instance] = round(max(0.0, value), 3)
            elif reason is not None and len(engine_read_errors) < 3:
                engine_read_errors.append(reason)
        engine_reason = self._gpu_error if not engines else None
        if not engines and engine_reason is None:
            engine_reason = (
                "; ".join(engine_read_errors)
                or "PDH GPU Engine counters have not produced a valid sample yet"
            )
        engine_details = (
            self._gpu_error if self._gpu_error is not None and engines
            else self._gpu_details
        )
        if engine_read_errors:
            error_details = "; ".join(engine_read_errors)
            engine_details = (
                f"{engine_details}; counter read failures: {error_details}"
                if engine_details else f"counter read failures: {error_details}"
            )

        adapter_memory: dict[str, dict[str, int]] = {}
        memory_read_errors: list[str] = []
        for instance, counters in self._gpu_memory_counters.items():
            values: dict[str, int] = {}
            for label, counter in counters.items():
                value, reason = self._formatted_value(counter)
                if value is not None:
                    values[label] = int(round(max(0.0, value)))
                elif reason is not None and len(memory_read_errors) < 3:
                    memory_read_errors.append(reason)
            if values:
                adapter_memory[instance] = values
        memory_reason = self._gpu_memory_error if not adapter_memory else None
        if not adapter_memory and memory_reason is None:
            memory_reason = (
                "; ".join(memory_read_errors)
                or "PDH GPU Adapter Memory counters have not produced a valid sample yet"
            )
        memory_details = (
            self._gpu_memory_error
            if self._gpu_memory_error is not None and adapter_memory
            else self._gpu_memory_details
        )
        if memory_read_errors:
            error_details = "; ".join(memory_read_errors)
            memory_details = (
                f"{memory_details}; counter read failures: {error_details}"
                if memory_details else f"counter read failures: {error_details}"
            )
        return page_faults, engines, adapter_memory, {
            "system_page_faults_per_second": self._capability(
                page_fault_provider, page_fault_reason,
            ),
            "gpu_engine_utilization_percent": self._capability(
                engine_provider, engine_reason, engine_details,
            ),
            "gpu_adapter_memory_bytes": self._capability(
                gpu_memory_provider, memory_reason, memory_details,
            ),
        }

    def _process_fault_sample(
        self, sampled_ns: int,
    ) -> tuple[int | None, float | None, dict[str, Any]]:
        provider = "psutil.Process.memory_info().num_page_faults"
        if self._process is None:
            return None, None, {
                "process_page_faults_per_second": self._capability(
                    provider, self._process_error,
                ),
            }
        try:
            value = getattr(self._process.memory_info(), "num_page_faults", None)
        except Exception as exc:
            return None, None, {
                "process_page_faults_per_second": self._capability(
                    provider, f"{type(exc).__name__}: {str(exc)[:160]}",
                ),
            }
        if not isinstance(value, int) or isinstance(value, bool):
            return None, None, {
                "process_page_faults_per_second": self._capability(
                    provider, "psutil memory_info() does not expose num_page_faults",
                ),
            }
        rate = None
        if self._previous_faults is not None and self._previous_fault_ns is not None:
            elapsed_ns = max(1, sampled_ns - self._previous_fault_ns)
            rate = round(max(0, value - self._previous_faults) * 1_000_000_000 / elapsed_ns, 3)
        self._previous_faults = value
        self._previous_fault_ns = sampled_ns
        reason = None if rate is not None else "waiting for a second process page-fault sample"
        return value, rate, {
            "process_page_faults_per_second": self._capability(provider, reason),
        }

    def _disk_sample(
        self, sampled_ns: int,
    ) -> tuple[dict[str, dict[str, int | float | None]], dict[str, Any]]:
        provider = "psutil.disk_io_counters(perdisk=True)"
        latency_provider = "psutil disk read_time/write_time per completed operation"
        if psutil is None:
            reason = _PSUTIL_ERROR or "psutil unavailable"
            return {}, {
                "drive_io": self._capability(provider, reason),
                "drive_latency_ms": self._capability(latency_provider, reason),
            }
        try:
            counters = psutil.disk_io_counters(perdisk=True)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {str(exc)[:160]}"
            return {}, {
                "drive_io": self._capability(provider, reason),
                "drive_latency_ms": self._capability(latency_provider, reason),
            }
        if not isinstance(counters, Mapping) or not counters:
            reason = "Windows reported no per-device disk I/O counters"
            return {}, {
                "drive_io": self._capability(provider, reason),
                "drive_latency_ms": self._capability(latency_provider, reason),
            }

        current: dict[str, tuple[int, int, int, int, int, int]] = {}
        for device in sorted(counters)[:self._MAX_DISK_DEVICES]:
            row = counters[device]
            try:
                values = tuple(
                    int(getattr(row, field))
                    for field in (
                        "read_bytes", "write_bytes", "read_count", "write_count",
                        "read_time", "write_time",
                    )
                )
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
            if any(value < 0 for value in values):
                continue
            current[str(device)] = values  # type: ignore[assignment]

        disk_rates: dict[str, dict[str, int | float | None]] = {}
        reason = "waiting for a second per-device disk counter sample"
        if self._previous_disk is not None and self._previous_disk_ns is not None:
            elapsed_ns = max(1, sampled_ns - self._previous_disk_ns)
            reason = "no per-device disk counters could be read"
            for device, values in current.items():
                previous = self._previous_disk.get(device)
                if previous is None:
                    continue
                read_delta = max(0, values[0] - previous[0])
                write_delta = max(0, values[1] - previous[1])
                read_ops = max(0, values[2] - previous[2])
                write_ops = max(0, values[3] - previous[3])
                read_ms = max(0, values[4] - previous[4])
                write_ms = max(0, values[5] - previous[5])
                operation_count = read_ops + write_ops
                disk_rates[device] = {
                    "read_bytes_per_second": read_delta * 1_000_000_000 // elapsed_ns,
                    "write_bytes_per_second": write_delta * 1_000_000_000 // elapsed_ns,
                    "read_operations_per_second": round(read_ops * 1_000_000_000 / elapsed_ns, 3),
                    "write_operations_per_second": round(write_ops * 1_000_000_000 / elapsed_ns, 3),
                    "average_latency_ms": (
                        round((read_ms + write_ms) / operation_count, 4)
                        if operation_count else None
                    ),
                }
            reason = None if disk_rates else "no matched device counters between consecutive samples"
        self._previous_disk = current
        self._previous_disk_ns = sampled_ns
        details = (
            f"sampled first {self._MAX_DISK_DEVICES} of {len(counters)} disk instances; "
            f"{len(current)} returned usable counters"
            if len(counters) > self._MAX_DISK_DEVICES or len(current) < len(counters) else None
        )
        latency_available = any(
            values["average_latency_ms"] is not None for values in disk_rates.values()
        )
        latency_reason = (
            None if latency_available else
            "no completed disk I/O between consecutive samples"
            if disk_rates else reason
        )
        return disk_rates, {
            "drive_io": self._capability(provider, reason, details),
            "drive_latency_ms": self._capability(
                latency_provider, latency_reason, details,
            ),
        }

    def sample(self, sampled_ns: int) -> dict[str, Any]:
        page_faults, engines, adapter_memory, pdh_availability = self._pdh_sample()
        process_faults, process_fault_rate, process_availability = self._process_fault_sample(
            sampled_ns,
        )
        disk_rates, disk_availability = self._disk_sample(sampled_ns)
        availability = {
            **pdh_availability,
            **process_availability,
            **disk_availability,
            "gpu_temperature_celsius": self._capability(
                "Windows in-process GPU thermal provider",
                "No supported in-process temperature provider is configured; AMD ADLX is not C-callable",
            ),
            "gpu_clock_mhz": self._capability(
                "Windows in-process GPU clock provider",
                "No supported in-process clock provider is configured; AMD ADLX is not C-callable",
            ),
        }
        return {
            "system_page_faults_per_second": page_faults,
            "process_page_faults": process_faults,
            "process_page_faults_per_second": process_fault_rate,
            "disk_io_bytes_per_second": {
                device: {
                    "read_bytes_per_second": int(values["read_bytes_per_second"]),
                    "write_bytes_per_second": int(values["write_bytes_per_second"]),
                }
                for device, values in disk_rates.items()
            },
            "disk_operations_per_second_by_device": {
                device: {
                    "read": values["read_operations_per_second"],
                    "write": values["write_operations_per_second"],
                }
                for device, values in disk_rates.items()
            },
            "disk_latency_ms_by_device": {
                device: values["average_latency_ms"]
                for device, values in disk_rates.items()
                if values["average_latency_ms"] is not None
            },
            "gpu_engine_utilization_percent": engines,
            "gpu_adapter_memory_bytes_by_instance": adapter_memory,
            "telemetry_availability": availability,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._query is not None and self._pdh is not None:
            self._pdh.PdhCloseQuery(self._query)
        self._query = None
        self._gpu_counters.clear()
        self._gpu_memory_counters.clear()
        self._page_fault_counter = None


OBSERVER_SCHEMA = "cassifi.machine-observation.v1"
CONCURRENCY_LEVELS = (1, 2, 4, 8)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_bytes() -> tuple[int | None, int | None]:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("available_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        try:
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None, None
        except (AttributeError, OSError):
            return None, None
        return int(status.total_physical), int(status.available_physical)
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total = int(os.sysconf("SC_PHYS_PAGES")) * page_size
        available = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
    except (AttributeError, OSError, ValueError):
        return None, None
    return total, available


def _cpu_counters() -> tuple[int, int] | None:
    """Return cumulative busy and total system CPU counters, when available."""
    if os.name == "nt":
        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

        idle, kernel, user = FileTime(), FileTime(), FileTime()
        try:
            ok = ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user),
            )
        except (AttributeError, OSError):
            return None
        if not ok:
            return None

        def value(item: FileTime) -> int:
            return (int(item.high) << 32) | int(item.low)

        idle_ticks = value(idle)
        total_ticks = value(kernel) + value(user)
        return max(0, total_ticks - idle_ticks), total_ticks
    if not sys.platform.startswith("linux"):
        return None
    try:
        with open("/proc/stat", "r", encoding="ascii") as stream:
            fields = stream.readline().split()
        if not fields or fields[0] != "cpu":
            return None
        counters = [int(value) for value in fields[1:]]
    except (OSError, ValueError):
        return None
    if len(counters) < 4:
        return None
    total_ticks = sum(counters)
    idle_ticks = counters[3] + (counters[4] if len(counters) > 4 else 0)
    return max(0, total_ticks - idle_ticks), total_ticks


def _disk_counters() -> dict[str, tuple[int, int]] | None:
    """Return raw whole-device Linux byte counters without merging devices."""
    if not sys.platform.startswith("linux"):
        return None
    rows: dict[str, tuple[int, int]] = {}
    try:
        with open("/proc/diskstats", "r", encoding="ascii") as stream:
            for line in stream:
                values = line.split()
                if len(values) < 10:
                    continue
                name = values[2]
                # Linux reports completed sectors in fixed 512-byte units.
                rows[name] = (int(values[5]) * 512, int(values[9]) * 512)
    except (OSError, ValueError):
        return None
    return rows


def _distribution(values: list[int | float]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    def percentile(fraction: float) -> int | float:
        index = max(0, math.ceil(fraction * len(ordered)) - 1)
        return ordered[index]

    return {
        "count": len(ordered),
        "mean": sum(ordered) / len(ordered),
        "p50": percentile(0.50),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "max": ordered[-1],
    }


def _peak_concurrency(target: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> int:
    start = int(target["admitted_at_ns"])
    end = int(target["ended_at_ns"])
    events: list[tuple[int, int]] = []
    for row in rows:
        other_start = int(row["admitted_at_ns"])
        other_end = int(row["ended_at_ns"])
        if other_end <= start or other_start >= end:
            continue
        events.append((max(start, other_start), 1))
        events.append((min(end, other_end), -1))
    active = peak = 0
    for _timestamp, delta in sorted(events, key=lambda event: (event[0], event[1])):
        active += delta
        peak = max(peak, active)
    return max(1, peak)


def _workload_evidence(admission: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        row for row in admission.get("recent_work", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("admitted_at_ns"), int)
        and isinstance(row.get("ended_at_ns"), int)
        and isinstance(row.get("queued_at_ns"), int)
        and int(row["ended_at_ns"]) >= int(row["admitted_at_ns"])
    ]
    scaled: dict[str, list[tuple[Mapping[str, Any], int]]] = {
        str(level): [] for level in CONCURRENCY_LEVELS
    }
    other: dict[str, list[tuple[Mapping[str, Any], int]]] = {}
    for row in rows:
        concurrency = _peak_concurrency(row, rows)
        group = scaled.get(str(concurrency))
        if group is None:
            group = other.setdefault(str(concurrency), [])
        group.append((row, concurrency))

    def summarize(group: list[tuple[Mapping[str, Any], int]]) -> dict[str, Any]:
        end_to_end = [
            max(0, int(row["ended_at_ns"]) - int(row["queued_at_ns"]))
            for row, _concurrency in group
        ]
        admission_wait = [
            max(0, int(row["admitted_at_ns"]) - int(row["queued_at_ns"]))
            for row, _concurrency in group
        ]
        active = [
            max(0, int(row["ended_at_ns"]) - int(row["admitted_at_ns"]))
            for row, _concurrency in group
        ]
        stage_durations: dict[str, list[int]] = {}
        for row, _concurrency in group:
            stages = row.get("stages")
            if not isinstance(stages, Mapping):
                continue
            for name, bounds in stages.items():
                if not isinstance(bounds, Mapping):
                    continue
                duration = bounds.get("wall_ns")
                if isinstance(duration, int) and not isinstance(duration, bool):
                    stage_durations.setdefault(str(name), []).append(duration)
        return {
            "count": len(group),
            "request_to_retirement_ns": _distribution(end_to_end),
            "admission_wait_ns": _distribution(admission_wait),
            "active_work_ns": _distribution(active),
            "stage_wall_ns": {
                name: _distribution(values)
                for name, values in sorted(stage_durations.items())
            },
            "statuses": {
                status: sum(row.get("status") == status for row, _ in group)
                for status in sorted({str(row.get("status")) for row, _ in group})
            },
            "completed_count": sum(
                row.get("status") == "completed" for row, _ in group
            ),
        }

    levels = {level: summarize(scaled[level]) for level in scaled}
    other_levels = {level: summarize(group) for level, group in sorted(other.items())}
    return {
        "latency_definition": (
            "request queue entry through lease retirement; includes admission wait "
            "and ends at physical retirement, not first useful response"
        ),
        "concurrency_definition": (
            "maximum number of overlapping admitted physical-work leases during "
            "each lease's admitted-to-retired interval"
        ),
        "concurrency_1_2_4_8": levels,
        "other_exact_concurrency": other_levels,
        "window_size": len(rows),
        "source_window_size": int(admission.get("telemetry", {}).get("window_size", len(rows))),
        "foreground_wait_ns": admission.get("telemetry", {}).get("foreground_wait_ns"),
    }


class PhysicalObserver:
    """Sample host pressure alongside the actual shared admission executor.

    Call ``start`` around ordinary owner work and ``stop`` after it drains.
    Work latency distributions are derived from the executor's real bounded
    lease journal, grouped by observed (not requested) simultaneous activity
    count. The observer never generates synthetic workload.
    """

    def __init__(
        self,
        admission: Any,
        *,
        sample_interval_seconds: float = 0.25,
        max_samples: int = 4096,
    ) -> None:
        if not callable(getattr(admission, "report", None)):
            raise TypeError("physical observer requires physical admission reporting")
        if (
            isinstance(sample_interval_seconds, bool)
            or not isinstance(sample_interval_seconds, (int, float))
            or not math.isfinite(sample_interval_seconds)
            or not 0.01 <= sample_interval_seconds <= 10.0
        ):
            raise ValueError("sample interval must be finite and between 0.01 and 10 seconds")
        if isinstance(max_samples, bool) or not isinstance(max_samples, int) or max_samples < 1:
            raise ValueError("max_samples must be a positive integer")
        self.admission = admission
        self.sample_interval_seconds = float(sample_interval_seconds)
        self._samples: deque[dict[str, Any]] = deque(maxlen=max_samples)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at_ns: int | None = None
        self._started_at_utc: str | None = None
        self._stopped_at_ns: int | None = None
        self._stopped_at_utc: str | None = None
        self._last_cpu_counters: tuple[int, int] | None = None
        self._last_disk_counters: dict[str, tuple[int, int]] | None = None
        self._last_counter_ns: int | None = None
        self._dropped_samples = 0
        self._windows_telemetry_lock = threading.Lock()
        self._windows_telemetry: _WindowsMachineTelemetry | None = None

    def start(self) -> "PhysicalObserver":
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("physical observer is already running")
            self._samples.clear()
            self._stop_event.clear()
            self._started_at_ns = time.monotonic_ns()
            self._started_at_utc = _utc_now()
            self._stopped_at_ns = None
            self._stopped_at_utc = None
            self._last_cpu_counters = None
            self._last_disk_counters = None
            self._last_counter_ns = None
            self._dropped_samples = 0
        with self._windows_telemetry_lock:
            if self._windows_telemetry is not None:
                self._windows_telemetry.close()
                self._windows_telemetry = None
        if os.name != "nt":
            self.sample()
        thread = threading.Thread(
            target=self._run,
            name="cassifi-machine-observer",
            daemon=True,
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return self

    def _run(self) -> None:
        if os.name == "nt":
            self.sample()
        while not self._stop_event.wait(self.sample_interval_seconds):
            self.sample()

    def sample(self) -> dict[str, Any]:
        """Capture a host/admission snapshot without changing admission state."""
        sampled_ns = time.monotonic_ns()
        total_ram, available_ram = _memory_bytes()
        cpu_counters = _cpu_counters()
        disk_counters = _disk_counters()
        cpu_percent: float | None = None
        disk_rates: dict[str, dict[str, int]] | None = None
        with self._lock:
            previous_cpu = self._last_cpu_counters
            previous_disk = self._last_disk_counters
            previous_ns = self._last_counter_ns
            if cpu_counters is not None and previous_cpu is not None:
                total_delta = cpu_counters[1] - previous_cpu[1]
                busy_delta = cpu_counters[0] - previous_cpu[0]
                if total_delta > 0:
                    cpu_percent = min(100.0, max(0.0, 100.0 * busy_delta / total_delta))
            if disk_counters is not None and previous_disk is not None and previous_ns is not None:
                elapsed_ns = max(1, sampled_ns - previous_ns)
                disk_rates = {}
                for device, (read_bytes, write_bytes) in disk_counters.items():
                    old = previous_disk.get(device)
                    if old is None:
                        continue
                    disk_rates[device] = {
                        "read_bytes_per_second": max(0, read_bytes - old[0]) * 1_000_000_000 // elapsed_ns,
                        "write_bytes_per_second": max(0, write_bytes - old[1]) * 1_000_000_000 // elapsed_ns,
                    }
            self._last_cpu_counters = cpu_counters
            self._last_disk_counters = disk_counters
            self._last_counter_ns = sampled_ns

        windows_metrics: dict[str, Any] = {}
        if os.name == "nt":
            try:
                with self._windows_telemetry_lock:
                    if self._windows_telemetry is None:
                        self._windows_telemetry = _WindowsMachineTelemetry()
                    windows_metrics = self._windows_telemetry.sample(sampled_ns)
            except Exception as exc:
                reason = f"{type(exc).__name__}: {str(exc)[:160]}"
                windows_metrics = {
                    "telemetry_availability": {
                        name: _WindowsMachineTelemetry._capability(provider, reason)
                        for name, provider in (
                            ("drive_io", "psutil.disk_io_counters(perdisk=True)"),
                            ("drive_latency_ms", "psutil disk read_time/write_time"),
                            ("system_page_faults_per_second", "Windows PDH Memory\\Page Faults/sec"),
                            ("process_page_faults_per_second", "psutil process num_page_faults"),
                            ("gpu_engine_utilization_percent", "Windows PDH GPU Engine\\Utilization Percentage"),
                            ("gpu_temperature_celsius", "Windows in-process GPU thermal provider"),
                            ("gpu_clock_mhz", "Windows in-process GPU clock provider"),
                        )
                    },
                }
            disk_rates = windows_metrics.get("disk_io_bytes_per_second")

        cpu_provider = "kernel32.GetSystemTimes" if os.name == "nt" else "Linux /proc/stat"
        if cpu_percent is not None:
            cpu_reason = None
        elif cpu_counters is None:
            cpu_reason = f"{cpu_provider} returned no cumulative CPU counters"
        elif previous_cpu is None:
            cpu_reason = f"waiting for a second {cpu_provider} sample"
        else:
            cpu_reason = f"{cpu_provider} counters did not advance between samples"
        telemetry_availability = {
            "system_cpu_busy_percent": _WindowsMachineTelemetry._capability(
                cpu_provider, cpu_reason,
            ),
            "system_memory": _WindowsMachineTelemetry._capability(
                "GlobalMemoryStatusEx" if os.name == "nt" else "os.sysconf",
                None if total_ram is not None and available_ram is not None else
                "OS total/available physical-memory counters unavailable",
            ),
        }
        if os.name == "nt":
            telemetry_availability.update(windows_metrics.get("telemetry_availability", {}))
        else:
            disk_reason = (
                None if disk_rates is not None else
                "waiting for a second /proc/diskstats sample"
                if disk_counters is not None else
                "Linux /proc/diskstats unavailable"
            )
            telemetry_availability.update({
                "drive_io": _WindowsMachineTelemetry._capability(
                    "Linux /proc/diskstats", disk_reason,
                ),
                "drive_latency_ms": _WindowsMachineTelemetry._capability(
                    "Linux /proc/diskstats latency fields",
                    "current Linux sampler reads byte counters only",
                ),
                "system_page_faults_per_second": _WindowsMachineTelemetry._capability(
                    "Windows PDH Memory\\Page Faults/sec",
                    "Windows PDH counter is unavailable outside Windows",
                ),
                "process_page_faults_per_second": _WindowsMachineTelemetry._capability(
                    "psutil.Process.memory_info().num_page_faults",
                    "Windows process page-fault sampler is unavailable outside Windows",
                ),
                "gpu_engine_utilization_percent": _WindowsMachineTelemetry._capability(
                    "Windows PDH GPU Engine\\Utilization Percentage",
                    "Windows PDH GPU Engine counters are unavailable outside Windows",
                ),
                "gpu_adapter_memory_bytes": _WindowsMachineTelemetry._capability(
                    "Windows PDH GPU Adapter Memory Dedicated Usage and Shared Usage",
                    "Windows PDH GPU Adapter Memory counters are unavailable outside Windows",
                ),
                "gpu_temperature_celsius": _WindowsMachineTelemetry._capability(
                    "Windows in-process GPU thermal provider",
                    "No supported in-process GPU temperature provider is configured",
                ),
                "gpu_clock_mhz": _WindowsMachineTelemetry._capability(
                    "Windows in-process GPU clock provider",
                    "No supported in-process GPU clock provider is configured",
                ),
            })

        try:
            admission = self.admission.report()
            resources = admission.get("residency")
            admission_error = None
        except Exception as exc:
            admission = {}
            resources = None
            admission_error = f"{type(exc).__name__}: {exc}"
        sample = {
            "sampled_at_ns": sampled_ns,
            "sampled_at_utc": _utc_now(),
            "logical_cpu_count": os.cpu_count(),
            "system_cpu_busy_percent": cpu_percent,
            "total_ram_bytes": total_ram,
            "available_ram_bytes": available_ram,
            "vram_devices": (
                dict(resources.get("vram_devices", {}))
                if isinstance(resources, Mapping) else {}
            ),
            "resident_used_bytes": (
                dict(resources.get("used_bytes", {}))
                if isinstance(resources, Mapping) else {}
            ),
            "physical_cores_active": admission.get("active_physical_cores"),
            "background_cores_active": admission.get("active_background_cores"),
            "queued_activities": admission.get("queued"),
            "disk_io_bytes_per_second": disk_rates,
            "disk_operations_per_second_by_device": windows_metrics.get(
                "disk_operations_per_second_by_device",
            ),
            "disk_latency_ms_by_device": windows_metrics.get("disk_latency_ms_by_device"),
            "system_page_faults_per_second": windows_metrics.get(
                "system_page_faults_per_second",
            ),
            "process_page_faults": windows_metrics.get("process_page_faults"),
            "process_page_faults_per_second": windows_metrics.get(
                "process_page_faults_per_second",
            ),
            "gpu_engine_utilization_percent": windows_metrics.get(
                "gpu_engine_utilization_percent",
            ),
            "gpu_adapter_memory_bytes_by_instance": windows_metrics.get(
                "gpu_adapter_memory_bytes_by_instance",
            ),
            "gpu_temperature_celsius": None,
            "gpu_clock_mhz": None,
            "telemetry_availability": telemetry_availability,
            "admission_error": admission_error,
        }
        with self._lock:
            if len(self._samples) == self._samples.maxlen:
                self._dropped_samples += 1
            self._samples.append(sample)
        return dict(sample)

    def stop(self) -> dict[str, Any]:
        """Stop fresh sampling and return measurements collected so far."""
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            self._stop_event.set()
            if thread is not threading.current_thread():
                thread.join()
            if os.name != "nt":
                self.sample()
        with self._lock:
            if self._started_at_ns is not None and self._stopped_at_ns is None:
                self._stopped_at_ns = time.monotonic_ns()
                self._stopped_at_utc = _utc_now()
        with self._windows_telemetry_lock:
            if self._windows_telemetry is not None:
                self._windows_telemetry.close()
                self._windows_telemetry = None
        return self.report()

    def report(self) -> dict[str, Any]:
        """Return fresh samples and actual work-tail evidence, without estimates."""
        with self._lock:
            samples = [dict(row) for row in self._samples]
            started_at_ns = self._started_at_ns
            started_at_utc = self._started_at_utc
            stopped_at_ns = self._stopped_at_ns
            stopped_at_utc = self._stopped_at_utc
            dropped_samples = self._dropped_samples
        try:
            admission = self.admission.report()
            admission_error = None
        except Exception as exc:
            admission = {}
            admission_error = f"{type(exc).__name__}: {exc}"
        completed = _workload_evidence(admission)
        elapsed_ns = (
            None if started_at_ns is None else
            max(0, (stopped_at_ns or time.monotonic_ns()) - started_at_ns)
        )
        disk_samples: dict[str, dict[str, list[int]]] = {}
        disk_operation_samples: dict[str, dict[str, list[int | float]]] = {}
        disk_latency_samples: dict[str, list[int | float]] = {}
        system_page_fault_samples: list[int | float] = []
        process_page_fault_samples: list[int | float] = []
        gpu_engine_samples: dict[str, list[int | float]] = {}
        vram_samples: dict[str, dict[str, list[int]]] = {}
        gpu_adapter_memory_samples: dict[str, dict[str, list[int]]] = {}
        for row in samples:
            disk_rates = row.get("disk_io_bytes_per_second")
            if isinstance(disk_rates, Mapping):
                for device, rates in disk_rates.items():
                    if not isinstance(rates, Mapping):
                        continue
                    bucket = disk_samples.setdefault(
                        str(device), {"read": [], "write": []},
                    )
                    for label, field in (
                        ("read", "read_bytes_per_second"),
                        ("write", "write_bytes_per_second"),
                    ):
                        value = rates.get(field)
                        if isinstance(value, int) and not isinstance(value, bool):
                            bucket[label].append(value)
            operations = row.get("disk_operations_per_second_by_device")
            if isinstance(operations, Mapping):
                for device, rates in operations.items():
                    if not isinstance(rates, Mapping):
                        continue
                    bucket = disk_operation_samples.setdefault(
                        str(device), {"read": [], "write": []},
                    )
                    for label in ("read", "write"):
                        value = rates.get(label)
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            bucket[label].append(value)
            latencies = row.get("disk_latency_ms_by_device")
            if isinstance(latencies, Mapping):
                for device, value in latencies.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        disk_latency_samples.setdefault(str(device), []).append(value)
            for field, target in (
                ("system_page_faults_per_second", system_page_fault_samples),
                ("process_page_faults_per_second", process_page_fault_samples),
            ):
                value = row.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    target.append(value)
            engines = row.get("gpu_engine_utilization_percent")
            if isinstance(engines, Mapping):
                for instance, value in engines.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        gpu_engine_samples.setdefault(str(instance), []).append(value)
            adapter_memory = row.get("gpu_adapter_memory_bytes_by_instance")
            if isinstance(adapter_memory, Mapping):
                for instance, values in adapter_memory.items():
                    if not isinstance(values, Mapping):
                        continue
                    bucket = gpu_adapter_memory_samples.setdefault(
                        str(instance), {"dedicated": [], "shared": []},
                    )
                    for label in ("dedicated", "shared"):
                        value = values.get(label)
                        if isinstance(value, int) and not isinstance(value, bool):
                            bucket[label].append(value)
            devices = row.get("vram_devices")
            if isinstance(devices, Mapping):
                for device, device_row in devices.items():
                    if not isinstance(device_row, Mapping):
                        continue
                    bucket = vram_samples.setdefault(
                        str(device), {"used": [], "available": []},
                    )
                    used = device_row.get("used_bytes")
                    if isinstance(used, Mapping):
                        used_total = sum(
                            value for value in used.values()
                            if isinstance(value, int) and not isinstance(value, bool)
                        )
                        bucket["used"].append(used_total)
                    available = device_row.get("available_bytes")
                    if isinstance(available, int) and not isinstance(available, bool):
                        bucket["available"].append(available)
        return {
            "schema": OBSERVER_SCHEMA,
            "status": "observing" if stopped_at_ns is None and started_at_ns is not None else "snapshot",
            "started_at_utc": started_at_utc,
            "stopped_at_utc": stopped_at_utc,
            "elapsed_ns": elapsed_ns,
            "logical_cpu_count": os.cpu_count(),
            "sample_count": len(samples),
            "dropped_samples": dropped_samples,
            "samples": samples,
            "telemetry_availability": (
                samples[-1].get("telemetry_availability") if samples else None
            ),
            "machine_distributions": {
                "system_cpu_busy_percent": _distribution([
                    float(row["system_cpu_busy_percent"])
                    for row in samples
                    if isinstance(row.get("system_cpu_busy_percent"), (int, float))
                ]),
                "available_ram_bytes": _distribution([
                    int(row["available_ram_bytes"])
                    for row in samples
                    if isinstance(row.get("available_ram_bytes"), int)
                    and not isinstance(row.get("available_ram_bytes"), bool)
                ]),
                "physical_cores_active": _distribution([
                    int(row["physical_cores_active"])
                    for row in samples
                    if isinstance(row.get("physical_cores_active"), int)
                    and not isinstance(row.get("physical_cores_active"), bool)
                ]),
                "queued_activities": _distribution([
                    int(row["queued_activities"])
                    for row in samples
                    if isinstance(row.get("queued_activities"), int)
                    and not isinstance(row.get("queued_activities"), bool)
                ]),
                "system_page_faults_per_second": _distribution(system_page_fault_samples),
                "process_page_faults_per_second": _distribution(process_page_fault_samples),
                "disk_io_bytes_per_second_by_device": {
                    device: {
                        "read": _distribution(values["read"]),
                        "write": _distribution(values["write"]),
                    }
                    for device, values in sorted(disk_samples.items())
                },
                "disk_operations_per_second_by_device": {
                    device: {
                        "read": _distribution(values["read"]),
                        "write": _distribution(values["write"]),
                    }
                    for device, values in sorted(disk_operation_samples.items())
                },
                "disk_latency_ms_by_device": {
                    device: _distribution(values)
                    for device, values in sorted(disk_latency_samples.items())
                },
                "gpu_engine_utilization_percent_by_instance": {
                    instance: _distribution(values)
                    for instance, values in sorted(gpu_engine_samples.items())
                },
                "gpu_temperature_celsius": _distribution([
                    float(row["gpu_temperature_celsius"])
                    for row in samples
                    if isinstance(row.get("gpu_temperature_celsius"), (int, float))
                ]),
                "gpu_clock_mhz": _distribution([
                    float(row["gpu_clock_mhz"])
                    for row in samples
                    if isinstance(row.get("gpu_clock_mhz"), (int, float))
                ]),
                "gpu_adapter_memory_bytes_by_instance": {
                    instance: {
                        "dedicated": _distribution(values["dedicated"]),
                        "shared": _distribution(values["shared"]),
                    }
                    for instance, values in sorted(gpu_adapter_memory_samples.items())
                },
                "vram_bytes_by_device": {
                    device: {
                        "used": _distribution(values["used"]),
                        "available": _distribution(values["available"]),
                    }
                    for device, values in sorted(vram_samples.items())
                },
            },
            "workload": completed,
            "admission_error": admission_error,
        }

    def status(self) -> dict[str, Any]:
        """Return bounded current evidence without the full sample history."""
        report = self.report()
        samples = report.pop("samples")
        report["latest_sample"] = None if not samples else samples[-1]
        return report


    def __enter__(self) -> "PhysicalObserver":
        return self.start()

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.stop()
