"""Running screen — live benchmark execution + telemetry."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Log, ProgressBar, Static
from textual.containers import Container, Horizontal, Vertical

from arcbench.data.manifest import BenchmarkPreset


@dataclass
class BenchmarkRow:
    model: str
    size: str
    params: str
    backend: str
    ngl: int
    test: str
    tokens_per_sec: float
    stddev: float | None = None


@dataclass
class TelemetrySample:
    ts: float
    gpu_util: float | None = None
    vram_used_gib: float | None = None
    vram_total_gib: float | None = None
    cpu_percent: float = 0.0
    ram_used_gib: float = 0.0
    ram_total_gib: float = 0.0


class RunningScreen(Screen):
    """Live benchmark run screen with telemetry monitor."""

    BINDINGS = [
        Binding("ctrl+c", "stop_benchmark", "Stop", show=True),
        Binding("l", "toggle_log", "Logs", show=True),
        Binding("escape", "stop_benchmark", "Stop", show=False),
    ]

    DEFAULT_CSS = """
    RunningScreen {
        padding: 1 2;
    }

    #run-header {
        color: #00A3FF;
        text-style: bold;
        height: 2;
        margin-bottom: 1;
    }

    #telemetry-panel {
        border: round #1E2328;
        padding: 1 2;
        height: 9;
        margin-bottom: 1;
    }

    #telemetry-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
    }

    .metric-row {
        height: 1;
        margin-bottom: 0;
    }

    #results-panel {
        border: round #1E2328;
        padding: 1 2;
        height: 10;
        margin-bottom: 1;
    }

    #results-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
    }

    #log-panel {
        border: round #1E2328;
        padding: 0 1;
        height: 6;
    }

    #phase-label {
        color: #8B949E;
        height: 1;
        margin-bottom: 1;
    }

    #elapsed-label {
        color: #8B949E;
        text-align: right;
    }

    #stop-btn {
        background: #D163A7;
        border: tall #D163A7;
        color: #101214;
        width: 14;
        margin-top: 1;
    }
    """

    def __init__(self, preset: BenchmarkPreset) -> None:
        super().__init__()
        self._preset = preset
        self._results: list[BenchmarkRow] = []
        self._telemetry: list[TelemetrySample] = []
        self._start_time = 0.0
        self._phase = "initializing"
        self._running = True
        self._log_visible = True
        self._process: asyncio.subprocess.Process | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Horizontal(
            Static(
                f"[bold #00A3FF]Running: {self._preset.label}[/bold #00A3FF]",
                id="run-header",
            ),
            Static("elapsed: 0:00", id="elapsed-label"),
        )
        yield Static("Phase: initializing", id="phase-label")

        # Telemetry panel
        yield Vertical(
            Static("[bold #7C5CFF]Live system monitor[/bold #7C5CFF]", id="telemetry-title"),
            Static("GPU  ─────────────────────────────────────", id="metric-gpu-util"),
            Static("VRAM ─────────────────────────────────────", id="metric-vram"),
            Static("CPU  ─────────────────────────────────────", id="metric-cpu"),
            Static("RAM  ─────────────────────────────────────", id="metric-ram"),
            id="telemetry-panel",
        )

        # Results table
        yield Vertical(
            Static("[bold #7C5CFF]Results[/bold #7C5CFF]", id="results-title"),
            DataTable(id="results-table"),
            id="results-panel",
        )

        # Log tail
        yield Log(id="log-panel", highlight=True, markup=True)

        yield Button("■  Stop", id="stop-btn")
        yield Footer()

    def on_mount(self) -> None:
        # Set up results table columns
        table = self.query_one("#results-table", DataTable)
        table.add_columns("model", "size", "params", "backend", "ngl", "test", "t/s")

        self._start_time = time.time()
        self.set_interval(1.0, self._update_elapsed)
        self.run_worker(self._run_benchmark(), exclusive=True, name="benchmark")
        self.run_worker(self._poll_telemetry(), exclusive=False, name="telemetry")

    def _update_elapsed(self) -> None:
        elapsed = int(time.time() - self._start_time)
        m, s = divmod(elapsed, 60)
        self.query_one("#elapsed-label", Static).update(f"elapsed: {m}:{s:02d}")

    async def _run_benchmark(self) -> None:
        """Launch llama-bench and parse JSONL output."""
        log = self.query_one("#log-panel", Log)
        system_info = getattr(self.app, "_system_info", None)
        bench_path = "llama-bench"
        if system_info and system_info.software.llama_bench_path:
            bench_path = system_info.software.llama_bench_path

        model_path = self._preset.model.filename if self._preset.model else ""
        # Use full path from cache dir if available
        if system_info and self._preset.model:
            model_path = str(system_info.cache_dir / self._preset.model.filename)

        cmd = self._preset.build_command(model_path)
        cmd[0] = bench_path

        self._update_phase(f"launching {bench_path}")
        log.write_line(f"[#8B949E]$ {' '.join(cmd)}[/#8B949E]")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(),
            )

            self._update_phase("running")

            async def read_stderr() -> None:
                assert self._process and self._process.stderr
                async for line in self._process.stderr:
                    txt = line.decode(errors="replace").rstrip()
                    if txt:
                        log.write_line(f"[#8B949E]{txt}[/#8B949E]")

            async def read_stdout() -> None:
                assert self._process and self._process.stdout
                async for line in self._process.stdout:
                    txt = line.decode(errors="replace").rstrip()
                    if txt:
                        log.write_line(txt)
                        self._try_parse_jsonl(txt)

            await asyncio.gather(read_stdout(), read_stderr())
            await self._process.wait()

            self._running = False
            rc = self._process.returncode
            if rc == 0:
                self._update_phase("complete")
                self._on_complete()
            else:
                self._update_phase(f"failed (exit {rc})")

        except Exception as exc:
            self._running = False
            log.write_line(f"[#D163A7]Error: {exc}[/#D163A7]")
            self._update_phase("error")

    def _try_parse_jsonl(self, line: str) -> None:
        """Parse a JSONL line from llama-bench and update results table."""
        try:
            data = json.loads(line)
            if "t_s" not in data:
                return
            row = BenchmarkRow(
                model=data.get("model_type", "?"),
                size=data.get("model_size", "?"),
                params=data.get("n_params", "?"),
                backend=data.get("backend", "?"),
                ngl=int(data.get("n_gpu_layers", 0)),
                test=data.get("test", "?"),
                tokens_per_sec=float(data.get("t_s", 0)),
                stddev=data.get("t_s_dev"),
            )
            self._results.append(row)
            self._add_result_row(row)
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    def _add_result_row(self, row: BenchmarkRow) -> None:
        table = self.query_one("#results-table", DataTable)
        stddev = f" ± {row.stddev:.2f}" if row.stddev is not None else ""
        table.add_row(
            row.model[:20],
            row.size,
            row.params,
            row.backend,
            str(row.ngl),
            row.test,
            f"{row.tokens_per_sec:.2f}{stddev}",
        )

    async def _poll_telemetry(self) -> None:
        """Poll GPU/CPU/RAM metrics in background."""
        import psutil
        while self._running:
            sample = TelemetrySample(ts=time.time())
            # CPU / RAM via psutil
            sample.cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            sample.ram_used_gib = ram.used / (1024 ** 3)
            sample.ram_total_gib = ram.total / (1024 ** 3)

            # VRAM from sysfs
            try:
                from pathlib import Path
                for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_used"):
                    sample.vram_used_gib = int(p.read_text().strip()) / (1024 ** 3)
                for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
                    sample.vram_total_gib = int(p.read_text().strip()) / (1024 ** 3)
            except Exception:
                pass

            self._telemetry.append(sample)
            self._update_telemetry_display(sample)
            await asyncio.sleep(0.5)

    def _update_telemetry_display(self, sample: TelemetrySample) -> None:
        def bar(val: float, total: float, width: int = 20) -> str:
            if total <= 0:
                return "─" * width
            filled = int((val / total) * width)
            return "█" * filled + "░" * (width - filled)

        try:
            # GPU util (sysfs fallback — shows n/a if unavailable)
            gpu_bar = "n/a (install intel_gpu_top for GPU utilization)"
            vram_bar = "n/a"
            if sample.vram_used_gib is not None and sample.vram_total_gib:
                vram_bar = (
                    f"{bar(sample.vram_used_gib, sample.vram_total_gib)}  "
                    f"{sample.vram_used_gib:.1f}/{sample.vram_total_gib:.1f} GiB"
                )

            cpu_pct = sample.cpu_percent
            cpu_bar = f"{bar(cpu_pct, 100)}  {cpu_pct:.0f}%"
            ram_bar = (
                f"{bar(sample.ram_used_gib, sample.ram_total_gib)}  "
                f"{sample.ram_used_gib:.1f}/{sample.ram_total_gib:.1f} GiB"
            )

            self.query_one("#metric-gpu-util", Static).update(f"GPU  {gpu_bar}")
            self.query_one("#metric-vram", Static).update(f"VRAM {vram_bar}")
            self.query_one("#metric-cpu", Static).update(f"CPU  {cpu_bar}")
            self.query_one("#metric-ram", Static).update(f"RAM  {ram_bar}")
        except Exception:
            pass

    def _update_phase(self, phase: str) -> None:
        self._phase = phase
        try:
            self.query_one("#phase-label", Static).update(f"Phase: {phase}")
        except Exception:
            pass

    def _on_complete(self) -> None:
        from arcbench.screens.completion import CompletionScreen
        self.app.push_screen(CompletionScreen(
            preset=self._preset,
            results=self._results,
            telemetry=self._telemetry,
        ))

    def _build_env(self) -> dict:
        import os
        env = os.environ.copy()
        # Ensure oneAPI is sourced if SYCL_DEVICE_FILTER not set
        if "ONEAPI_ROOT" not in env:
            env["ONEAPI_ROOT"] = "/opt/intel/oneapi"
        return env

    def action_stop_benchmark(self) -> None:
        self._running = False
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        self.app.pop_screen()

    def action_toggle_log(self) -> None:
        log = self.query_one("#log-panel", Log)
        log.display = not log.display

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stop-btn":
            self.action_stop_benchmark()
