"""System detection and preflight checks."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GPUInfo:
    name: str = "Unknown"
    pci_id: str = ""
    vram_gib: float = 0.0
    driver: str = "unknown"          # "xe", "i915", or "unknown"
    render_node: str = ""            # e.g. /dev/dri/renderD128


@dataclass
class SoftwareStack:
    oneapi_version: str = ""
    llama_bench_path: str = ""
    llama_bench_build: str = ""
    intel_gpu_top: bool = False
    nvtop: bool = False
    level_zero: bool = False


@dataclass
class SystemInfo:
    gpus: list[GPUInfo] = field(default_factory=list)
    software: SoftwareStack = field(default_factory=SoftwareStack)
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "arcbench" / "models")
    results_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "arcbench")
    os_name: str = ""
    kernel: str = ""

    @property
    def primary_gpu(self) -> GPUInfo | None:
        return self.gpus[0] if self.gpus else None

    @property
    def cache_free_gib(self) -> float:
        try:
            import shutil as sh
            usage = sh.disk_usage(self.cache_dir.parent)
            return usage.free / (1024 ** 3)
        except Exception:
            return 0.0


def detect_system() -> SystemInfo:
    """Run hardware and software detection. Returns SystemInfo."""
    info = SystemInfo()

    # OS / kernel
    try:
        import platform
        info.os_name = platform.freedesktop_os_release().get("PRETTY_NAME", platform.system())
        info.kernel = platform.release()
    except Exception:
        pass

    # GPU detection via lspci
    info.gpus = _detect_gpus()

    # Software stack
    info.software = _detect_software()

    # Ensure cache dir exists
    info.cache_dir.mkdir(parents=True, exist_ok=True)
    info.results_dir.mkdir(parents=True, exist_ok=True)

    return info


def _detect_gpus() -> list[GPUInfo]:
    gpus: list[GPUInfo] = []
    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Intel" in line and any(x in line.lower() for x in ["arc", "display", "vga", "3d"]):
                gpu = GPUInfo()
                # Extract PCI ID e.g. [8086:e223]
                if "[8086:" in line:
                    gpu.pci_id = line.split("[8086:")[-1].split("]")[0]
                    gpu.pci_id = f"8086:{gpu.pci_id}"
                # Name: everything before the brackets
                gpu.name = line.split("[")[0].split(":")[-1].strip()
                # Check driver
                gpu.driver = _detect_driver(gpu.pci_id)
                # Render node
                gpu.render_node = _find_render_node()
                # VRAM from sysfs
                gpu.vram_gib = _detect_vram()
                gpus.append(gpu)
    except Exception:
        pass
    return gpus


def _detect_driver(pci_id: str) -> str:
    try:
        result = subprocess.run(
            ["lspci", "-k"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if pci_id.split(":")[-1].lower() in line.lower():
                for j in range(i, min(i + 5, len(lines))):
                    if "Kernel driver in use" in lines[j]:
                        drv = lines[j].split(":")[-1].strip()
                        return drv
    except Exception:
        pass
    return "unknown"


def _find_render_node() -> str:
    try:
        render_nodes = list(Path("/dev/dri").glob("renderD*"))
        if render_nodes:
            return str(sorted(render_nodes)[0])
    except Exception:
        pass
    return ""


def _detect_vram() -> float:
    """Try to read VRAM from sysfs."""
    try:
        for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
            val = int(p.read_text().strip())
            return val / (1024 ** 3)
    except Exception:
        pass
    return 0.0


def _detect_software() -> SoftwareStack:
    sw = SoftwareStack()

    # llama-bench
    bench = shutil.which("llama-bench")
    if bench:
        sw.llama_bench_path = bench
    else:
        # Common build locations
        for candidate in [
            Path.home() / "llama.cpp/build/bin/llama-bench",
            Path("/usr/local/bin/llama-bench"),
        ]:
            if candidate.exists():
                sw.llama_bench_path = str(candidate)
                break

    # oneAPI version
    setvars = Path("/opt/intel/oneapi/setvars.sh")
    if setvars.exists():
        try:
            result = subprocess.run(
                ["find", "/opt/intel/oneapi", "-name", "version.txt", "-maxdepth", "3"],
                capture_output=True, text=True, timeout=5
            )
            for vfile in result.stdout.splitlines()[:1]:
                sw.oneapi_version = Path(vfile).read_text().strip().splitlines()[0]
        except Exception:
            sw.oneapi_version = "found"

    # Tool availability
    sw.intel_gpu_top = bool(shutil.which("intel_gpu_top"))
    sw.nvtop = bool(shutil.which("nvtop"))

    # Level Zero
    try:
        result = subprocess.run(
            ["dpkg", "-l", "libze-intel-gpu1"],
            capture_output=True, text=True, timeout=5
        )
        sw.level_zero = "ii" in result.stdout
    except Exception:
        pass

    return sw
