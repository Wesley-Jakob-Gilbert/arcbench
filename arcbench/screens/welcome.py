"""Welcome / system scan screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static
from textual.containers import Container, Vertical


LOGO = """\
  █████╗ ██████╗  ██████╗    ██████╗ ███████╗███╗   ██╗ ██████╗██╗  ██╗
 ██╔══██╗██╔══██╗██╔════╝    ██╔══██╗██╔════╝████╗  ██║██╔════╝██║  ██║
 ███████║██████╔╝██║         ██████╔╝█████╗  ██╔██╗ ██║██║     ███████║
 ██╔══██║██╔══██╗██║         ██╔══██╗██╔══╝  ██║╚██╗██║██║     ██╔══██║
 ██║  ██║██║  ██║╚██████╗    ██████╔╝███████╗██║ ╚████║╚██████╗██║  ██║
 ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝    ╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝"""


class CheckRow(Static):
    """A single preflight check row with status."""

    DEFAULT_CSS = """
    CheckRow {
        height: 1;
        padding: 0 2;
    }
    """

    def __init__(self, label: str, status: str = "pending", detail: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._status = status
        self._detail = detail

    def compose(self) -> ComposeResult:
        icon, color = self._status_icon()
        yield Label(f"[{color}]{icon}[/{color}]  {self._label:<40}  [{color}]{self._detail}[/{color}]")

    def _status_icon(self) -> tuple[str, str]:
        return {
            "ok": ("✓", "#6DAA45"),
            "warn": ("!", "#D19900"),
            "error": ("✗", "#D163A7"),
            "pending": ("·", "#8B949E"),
            "running": ("…", "#00A3FF"),
        }.get(self._status, ("?", "#8B949E"))

    def update_status(self, status: str, detail: str = "") -> None:
        self._status = status
        self._detail = detail
        self.refresh(recompose=True)


class WelcomeScreen(Screen):
    """First-launch system scan screen."""

    BINDINGS = [
        Binding("enter", "continue_to_home", "Continue", show=True),
        Binding("q", "app.quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Container(
            Static(f"[#00A3FF]{LOGO}[/#00A3FF]", id="logo"),
            Static(
                "[#8B949E]Intel Arc GPU benchmark console for Linux[/#8B949E]",
                id="subtitle"
            ),
            Vertical(
                Static("[bold #00A3FF]Scanning system...[/bold #00A3FF]", id="scan-title"),
                CheckRow("Intel Arc GPU", "pending", "", id="check-gpu"),
                CheckRow("Intel oneAPI / SYCL runtime", "pending", "", id="check-oneapi"),
                CheckRow("llama-bench", "pending", "", id="check-llamabench"),
                CheckRow("GPU telemetry (intel_gpu_top)", "pending", "", id="check-telemetry"),
                CheckRow("Model cache directory", "pending", "", id="check-cache"),
                id="checks",
            ),
            Container(
                Button("Continue →", id="btn-continue", variant="primary"),
                id="actions",
            ),
            id="welcome-container",
        )
        yield Footer()

    DEFAULT_CSS = """
    #welcome-container {
        align: center middle;
        width: 100%;
        height: 100%;
        padding: 2 4;
    }

    #logo {
        text-align: center;
        margin-bottom: 1;
        color: #00A3FF;
    }

    #subtitle {
        text-align: center;
        margin-bottom: 2;
    }

    #checks {
        border: round #1E2328;
        padding: 1 2;
        margin-bottom: 2;
        width: 80;
    }

    #scan-title {
        margin-bottom: 1;
    }

    #actions {
        align: center middle;
    }

    #btn-continue {
        width: 20;
    }
    """

    def on_mount(self) -> None:
        self.run_worker(self._run_scan(), exclusive=True)

    async def _run_scan(self) -> None:
        """Run system detection asynchronously and update check rows."""
        import asyncio
        from arcbench.data.system import detect_system

        await asyncio.sleep(0.3)  # Let UI render first

        self._update_check("check-gpu", "running", "detecting...")
        await asyncio.sleep(0.1)

        info = await asyncio.get_event_loop().run_in_executor(None, detect_system)

        # GPU check
        if info.primary_gpu:
            g = info.primary_gpu
            vram_str = f"{g.vram_gib:.0f} GiB" if g.vram_gib else "VRAM unknown"
            self._update_check("check-gpu", "ok", f"{g.name}  {vram_str}  driver: {g.driver}")
        else:
            self._update_check("check-gpu", "warn", "No Intel Arc GPU detected via lspci")

        # oneAPI
        self._update_check("check-oneapi", "running", "checking...")
        await asyncio.sleep(0.05)
        if info.software.oneapi_version:
            self._update_check("check-oneapi", "ok", info.software.oneapi_version)
        else:
            self._update_check("check-oneapi", "warn", "Not found — source /opt/intel/oneapi/setvars.sh")

        # llama-bench
        self._update_check("check-llamabench", "running", "checking...")
        await asyncio.sleep(0.05)
        if info.software.llama_bench_path:
            self._update_check("check-llamabench", "ok", info.software.llama_bench_path)
        else:
            self._update_check("check-llamabench", "error", "Not found — build llama.cpp with SYCL")

        # Telemetry
        self._update_check("check-telemetry", "running", "checking...")
        await asyncio.sleep(0.05)
        if info.software.intel_gpu_top:
            self._update_check("check-telemetry", "ok", "intel_gpu_top found")
        elif info.software.nvtop:
            self._update_check("check-telemetry", "warn", "intel_gpu_top missing — nvtop fallback")
        else:
            self._update_check("check-telemetry", "warn", "No GPU monitor — CPU/RAM only")

        # Cache
        self._update_check("check-cache", "running", "checking...")
        await asyncio.sleep(0.05)
        free = info.cache_free_gib
        self._update_check(
            "check-cache", "ok",
            f"{info.cache_dir}  ({free:.0f} GiB free)"
        )

        # Store system info on app for other screens
        self.app._system_info = info  # type: ignore[attr-defined]

    def _update_check(self, check_id: str, status: str, detail: str) -> None:
        try:
            row = self.query_one(f"#{check_id}", CheckRow)
            row.update_status(status, detail)
        except Exception:
            pass

    def action_continue_to_home(self) -> None:
        from arcbench.screens.home import HomeScreen
        self.app.switch_screen(HomeScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-continue":
            self.action_continue_to_home()
