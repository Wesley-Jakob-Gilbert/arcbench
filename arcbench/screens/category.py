"""Category / benchmark selection screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static
from textual.containers import Container, Horizontal, Vertical

from arcbench.data.manifest import BenchmarkPreset, load_manifests


CATEGORY_TITLES = {
    "ml": "Machine Learning",
    "rendering": "Rendering",
    "hpc": "HPC / Compute",
}


class BenchmarkListItem(ListItem):
    """A single benchmark in the list."""

    def __init__(self, preset: BenchmarkPreset) -> None:
        super().__init__()
        self.preset = preset

    def compose(self) -> ComposeResult:
        system_info = None
        vram_gib = 32.0  # default assumption
        fits = (self.preset.model is None or
                self.preset.expected_vram_gib == 0 or
                self.preset.expected_vram_gib < vram_gib)
        fit_badge = "[#6DAA45]fits VRAM[/#6DAA45]" if fits else "[#D19900]hybrid[/#D19900]"
        size_str = ""
        if self.preset.model:
            size_str = f"  [#8B949E]{self.preset.model.size_gib:.1f} GiB[/#8B949E]"
        yield Label(
            f"[bold]{self.preset.label}[/bold]{size_str}  {fit_badge}"
        )


class CategoryScreen(Screen):
    """Benchmark selection for a given category."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("b", "go_back", "Back", show=False),
        Binding("r", "run_selected", "Run", show=True),
        Binding("?", "app.help", "Help", show=True),
    ]

    DEFAULT_CSS = """
    CategoryScreen {
        padding: 1 2;
    }

    #breadcrumb {
        color: #8B949E;
        height: 1;
        margin-bottom: 1;
    }

    #main-layout {
        height: 1fr;
    }

    #list-panel {
        width: 50%;
        border: round #1E2328;
        padding: 1;
    }

    #list-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
        padding: 0 1;
    }

    BenchmarkListItem {
        padding: 0 1;
    }

    BenchmarkListItem:hover {
        background: #1E2328;
    }

    #detail-panel {
        width: 1fr;
        border: round #1E2328;
        padding: 1 2;
        margin-left: 1;
    }

    #detail-title {
        color: #00A3FF;
        text-style: bold;
        margin-bottom: 1;
    }

    #detail-description {
        color: #C9D1D9;
        margin-bottom: 1;
    }

    #detail-meta {
        color: #8B949E;
        margin-bottom: 1;
    }

    #detail-command {
        background: #0D1117;
        border: round #1E2328;
        padding: 1;
        color: #6DAA45;
        margin-bottom: 1;
    }

    #detail-actions {
        margin-top: 1;
    }

    #btn-run {
        width: 18;
        background: #00A3FF;
        color: #101214;
        border: tall #00A3FF;
    }

    #btn-run:hover {
        background: #7C5CFF;
        border: tall #7C5CFF;
    }
    """

    def __init__(self, category: str = "ml") -> None:
        super().__init__()
        self._category = category
        self._presets = load_manifests(category)
        self._selected: BenchmarkPreset | None = (
            self._presets[0] if self._presets else None
        )

    def compose(self) -> ComposeResult:
        cat_title = CATEGORY_TITLES.get(self._category, self._category)
        yield Header(show_clock=False)
        yield Static(
            f"[#8B949E]Home / {cat_title}[/#8B949E]",
            id="breadcrumb",
        )
        yield Horizontal(
            Vertical(
                Static(f"[bold #7C5CFF]{cat_title}[/bold #7C5CFF]", id="list-title"),
                ListView(
                    *[BenchmarkListItem(p) for p in self._presets],
                    id="benchmark-list",
                ),
                Button("← Back", id="btn-back", variant="default"),
                id="list-panel",
            ),
            Vertical(
                *self._build_detail_widgets(),
                id="detail-panel",
            ),
            id="main-layout",
        )
        yield Footer()

    def _build_detail_widgets(self) -> list:
        if not self._selected:
            return [Static("[#8B949E]Select a benchmark to see details.[/#8B949E]")]

        p = self._selected
        model_info = ""
        cmd_preview = ""
        if p.model:
            fits_str = "fits in VRAM" if p.expected_vram_gib < 32.0 else "exceeds 32GB VRAM — hybrid mode"
            model_info = (
                f"Model: {p.model.filename}\n"
                f"Size:  {p.model.size_gib:.2f} GiB\n"
                f"VRAM:  {fits_str}\n"
                f"License: {p.model.license}"
            )
            cmd_args = " ".join(p.args).replace("{model}", p.model.filename)
            cmd_preview = f"{p.executable} {cmd_args}"

        repo_badge = (
            "[#6DAA45]repo-compatible[/#6DAA45]" if p.repo_compatible
            else "[#D19900]custom[/#D19900]"
        )

        return [
            Static(f"[bold #00A3FF]{p.label}[/bold #00A3FF]  {repo_badge}", id="detail-title"),
            Static(p.description.strip(), id="detail-description"),
            Static(model_info, id="detail-meta"),
            Static(f"[#8B949E]Command:[/#8B949E]\n[#6DAA45]{cmd_preview}[/#6DAA45]", id="detail-command"),
            Container(
                Button("▶  Run benchmark", id="btn-run"),
                id="detail-actions",
            ),
        ]

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, BenchmarkListItem):
            self._selected = item.preset
            # Refresh detail panel
            detail = self.query_one("#detail-panel", Vertical)
            detail.remove_children()
            for widget in self._build_detail_widgets():
                detail.mount(widget)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run" and self._selected:
            self.action_run_selected()
        elif event.button.id == "btn-back":
            self.action_go_back()

    def action_run_selected(self) -> None:
        if not self._selected:
            return
        from arcbench.screens.running import RunningScreen
        self.app.push_screen(RunningScreen(preset=self._selected))

    def action_go_back(self) -> None:
        self.app.pop_screen()
