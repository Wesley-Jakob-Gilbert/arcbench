"""Completion / result review screen."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static
from textual.containers import Container, Horizontal, Vertical

from arcbench.data.manifest import BenchmarkPreset
from arcbench.screens.running import BenchmarkRow, TelemetrySample


class CompletionScreen(Screen):
    """Show final results, validation badge, and export actions."""

    BINDINGS = [
        Binding("c", "copy_result", "Copy row", show=True),
        Binding("e", "export_markdown", "Export", show=True),
        Binding("h", "go_home", "Home", show=True),
        Binding("escape", "go_back", "Back", show=True),
    ]

    DEFAULT_CSS = """
    CompletionScreen {
        padding: 1 2;
    }

    #completion-header {
        color: #6DAA45;
        text-style: bold;
        height: 2;
        margin-bottom: 1;
    }

    #summary-panel {
        border: round #1E2328;
        padding: 1 2;
        height: auto;
        margin-bottom: 1;
    }

    #validation-panel {
        border: round #1E2328;
        padding: 1 2;
        height: auto;
        margin-bottom: 1;
    }

    #validation-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
    }

    #summary-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
    }

    #actions-panel {
        height: auto;
        margin-top: 1;
    }

    .action-btn {
        margin: 0 1;
        width: 22;
    }
    """

    def __init__(
        self,
        preset: BenchmarkPreset,
        results: list[BenchmarkRow],
        telemetry: list[TelemetrySample],
    ) -> None:
        super().__init__()
        self._preset = preset
        self._results = results
        self._telemetry = telemetry

    def compose(self) -> ComposeResult:
        valid, reason = self._validate()
        valid_str = (
            "[bold #6DAA45]✓ Benchmark complete — valid result[/bold #6DAA45]"
            if valid else
            f"[bold #D19900]⚠ Benchmark complete — {reason}[/bold #D19900]"
        )

        yield Header(show_clock=False)
        yield Static(valid_str, id="completion-header")

        # Summary
        pp_row = next((r for r in self._results if r.test.startswith("pp")), None)
        tg_row = next((r for r in self._results if r.test.startswith("tg")), None)
        pp_str = f"{pp_row.tokens_per_sec:.2f} t/s" if pp_row else "—"
        tg_str = f"{tg_row.tokens_per_sec:.2f} t/s" if tg_row else "—"

        avg_vram = None
        if self._telemetry:
            vram_samples = [s.vram_used_gib for s in self._telemetry if s.vram_used_gib is not None]
            if vram_samples:
                avg_vram = max(vram_samples)

        vram_str = f"{avg_vram:.1f} GiB peak" if avg_vram else "n/a"

        yield Vertical(
            Static("[bold #7C5CFF]Summary[/bold #7C5CFF]", id="summary-title"),
            Static(
                f"Model:               {self._preset.label}\n"
                f"Prompt processing:   {pp_str}\n"
                f"Token generation:    {tg_str}\n"
                f"Peak VRAM:           {vram_str}\n"
                f"Repo-compatible:     {'yes' if self._preset.repo_compatible else 'custom'}"
            ),
            id="summary-panel",
        )

        # Validation checks
        pp_ok = pp_row is not None
        tg_ok = tg_row is not None
        sycl_ok = bool(self._results and "SYCL" in (self._results[0].backend or ""))
        yield Vertical(
            Static("[bold #7C5CFF]Validation[/bold #7C5CFF]", id="validation-title"),
            Static(
                f"{'[#6DAA45]✓[/#6DAA45]' if pp_ok else '[#D163A7]✗[/#D163A7]'} pp512 row captured\n"
                f"{'[#6DAA45]✓[/#6DAA45]' if tg_ok else '[#D163A7]✗[/#D163A7]'} tg128 row captured\n"
                f"{'[#6DAA45]✓[/#6DAA45]' if sycl_ok else '[#D19900]![/#D19900]'} Backend: "
                f"{'SYCL' if sycl_ok else 'not SYCL — check GPU acceleration'}"
            ),
            id="validation-panel",
        )

        # Actions
        yield Horizontal(
            Button("Copy table row", id="btn-copy", classes="action-btn"),
            Button("Export Markdown", id="btn-export", classes="action-btn"),
            Button("Run another", id="btn-back", classes="action-btn"),
            Button("Home", id="btn-home", classes="action-btn"),
            id="actions-panel",
        )
        yield Footer()

    def _validate(self) -> tuple[bool, str]:
        if not self._results:
            return False, "no results captured"
        has_pp = any(r.test.startswith("pp") for r in self._results)
        has_tg = any(r.test.startswith("tg") for r in self._results)
        has_sycl = any("SYCL" in (r.backend or "") for r in self._results)
        if not has_pp or not has_tg:
            return False, "incomplete — missing pp or tg row"
        if not has_sycl:
            return False, "backend not SYCL — GPU may not be active"
        return True, "valid"

    def _build_markdown_row(self) -> str:
        pp_row = next((r for r in self._results if r.test.startswith("pp")), None)
        tg_row = next((r for r in self._results if r.test.startswith("tg")), None)
        pp_str = f"{pp_row.tokens_per_sec:.2f}" if pp_row else "—"
        tg_str = f"{tg_row.tokens_per_sec:.2f}" if tg_row else "—"
        model_name = self._preset.label.split("—")[0].strip()
        quant = self._preset.label.split("—")[-1].strip() if "—" in self._preset.label else ""
        size_str = f"{self._preset.model.size_gib:.2f} GiB" if self._preset.model else "?"
        ngl_str = "999 (all GPU)" if "999" in " ".join(self._preset.args) else "hybrid"
        today = date.today().isoformat()
        return f"| {model_name} | {quant} | {size_str} | {ngl_str} | {pp_str} | {tg_str} | {today} |"

    def action_copy_result(self) -> None:
        row = self._build_markdown_row()
        try:
            import subprocess
            subprocess.run(["xclip", "-selection", "clipboard"], input=row.encode(), check=True)
            self.notify("Copied to clipboard", title="arcbench")
        except Exception:
            # Fallback: show in notification
            self.notify(f"Copy manually:\n{row}", title="arcbench", timeout=10)

    def action_export_markdown(self) -> None:
        system_info = getattr(self.app, "_system_info", None)
        results_dir = (
            system_info.results_dir if system_info
            else Path.home() / ".local" / "share" / "arcbench"
        )
        results_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        fname = f"{today}_{self._preset.id}.md"
        out = results_dir / fname

        gpu_str = "Unknown GPU"
        if system_info and system_info.primary_gpu:
            g = system_info.primary_gpu
            gpu_str = f"{g.name} {g.vram_gib:.0f}GB"

        sw_str = ""
        if system_info:
            sw = system_info.software
            sw_str = (
                f"- llama.cpp build: {sw.llama_bench_build or 'unknown'}\n"
                f"- oneAPI: {sw.oneapi_version or 'unknown'}\n"
            )

        raw_rows = "\n".join(
            f"| {r.model} | {r.size} | {r.params} | {r.backend} | {r.ngl} | {r.test} | {r.tokens_per_sec:.2f} ± {r.stddev or 0:.2f} |"
            for r in self._results
        )

        md = f"""## {gpu_str} — {self._preset.label} — {today}

| Model | Quant | Size | ngl | Prompt (t/s) | Generation (t/s) | Date |
|---|---|---|---|---|---|---|
{self._build_markdown_row()}

**Hardware**
- GPU: {gpu_str}

**Software**
{sw_str}
**Command**
```bash
{self._preset.executable} {" ".join(self._preset.args)}
```

<details>
<summary>Raw llama-bench output</summary>

| model | size | params | backend | ngl | test | t/s |
|---|---|---|---|---|---|---|
{raw_rows}

</details>
"""
        out.write_text(md)
        self.notify(f"Exported to {out}", title="arcbench")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-copy":
                self.action_copy_result()
            case "btn-export":
                self.action_export_markdown()
            case "btn-back":
                # Pop back to category screen
                self.app.pop_screen()
                self.app.pop_screen()
            case "btn-home":
                self.action_go_home()

    def action_go_home(self) -> None:
        # Pop all screens back to home
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
