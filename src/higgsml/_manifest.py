from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


_RUNTIME_PACKAGES = (
    "awkward", "matplotlib", "mplhep", "numpy", "pandas", "PyYAML",
    "scikit-learn", "torch", "tqdm", "uproot", "vector",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: str | Path, value: Any) -> dict[str, Any]:
    payload = json_bytes(value)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {"path": destination.as_posix(), "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}


def write_canonical_json(path: str | Path, value: Any) -> dict[str, Any]:
    payload = canonical_json_bytes(value)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {
        "path": destination.as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def software_record() -> dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout)
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {
        "python": sys.version.split()[0],
        "packages": {
            name: importlib.metadata.version(name) for name in _RUNTIME_PACKAGES
        },
        "git_commit": commit, "git_dirty": dirty,
        "platform": {"os": platform.system(), "machine": platform.machine(), "processor": platform.processor()},
    }


def peak_memory_bytes() -> int:
    """Return the operating system's peak resident/working-set size for this process."""
    system = platform.system()
    if system == "Windows":
        import ctypes
        from ctypes import wintypes

        size_t = ctypes.c_size_t

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", size_t), ("WorkingSetSize", size_t),
                ("QuotaPeakPagedPoolUsage", size_t), ("QuotaPagedPoolUsage", size_t),
                ("QuotaPeakNonPagedPoolUsage", size_t), ("QuotaNonPagedPoolUsage", size_t),
                ("PagefileUsage", size_t), ("PeakPagefileUsage", size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_current_process.restype = wintypes.HANDLE
        get_process_memory_info.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD
        )
        get_process_memory_info.restype = wintypes.BOOL
        if not get_process_memory_info(
            get_current_process(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)

    if system in {"Darwin", "Linux"}:
        import resource

        maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return maximum if system == "Darwin" else maximum * 1024
    raise OSError(f"peak RSS measurement is unsupported on {system}")
