"""Home dashboard screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static
from textual.containers import Container, Grid, Horizontal, Vertical


class CategoryCard(Button):
    """A benchmark category card button."""

    def __init__(self, title: str, subtitle: str, category: str, available: bool = True) -> None:
        label = f"[bold]{title}[/bold]\n[dim]{subtitle}[/dim]"
        super().__init__(label, id=f"cat-{category}", disabled=not available)
        self._category = category
        self._available = available


class HomeScreen(Screen):
    """Main dashboard — category selection + system status."""

    BINDINGS = [
        Binding("q", "app.quit", "Quit", show=True),
        Binding("s", "system_info", "System", show=True),
        Binding("?", "app.help", "Help", show=True),
    ]

    DEFAULT_CSS = """
    HomeScreen {
        padding: 1 2;
    }

    #header-bar {
        height: 3;
        margin-bottom: 1;
    }

    #app-title {
        color: #00A3FF;
        text-style: bold;
        width: 1fr;
    }

    #system-status {
        color: #8B949E;
        text-align: right;
        width: 1fr;
    }

    #category-grid {
        grid-size: 2;
        grid-gutter: 1 2;
        height: 12;
        margin-bottom: 1;
    }

    CategoryCard {
        height: 5;
        width: 1fr;
        border: round #1E2328;
        padding: 1 2;
        background: #171A1D;
        color: #00A3FF;
        text-align: left;
    }

    CategoryCard:hover {
        border: round #00A3FF;
        background: #1E2328;
    }

    CategoryCard:disabled {
        color: #3A3F45;
        border: round #1E2328;
    }

    #recent-panel {
        border: round #1E2328;
        padding: 1 2;
        height: auto;
        margin-top: 1;
    }

    #recent-title {
        color: #7C5CFF;
        text-style: bold;
        margin-bottom: 1;
    }

    #no-results {
        color: #8B949E;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)

        system_info = getattr(self.app, "_system_info", None)
        gpu_label = "No GPU detected"
        if system_info and system_info.primary_gpu:
            g = system_info.primary_gpu
            vram = f"{g.vram_gib:.0f}GB" if g.vram_gib else ""
            gpu_label = f"[#6DAA45]●[/#6DAA45] {g.name} {vram}"

        yield Horizontal(
            Static("[bold #00A3FF]arcbench[/bold #00A3FF]  [#8B949E]Intel Arc benchmark console[/#8B949E]",
                   id="app-title"),
            Static(gpu_label, id="system-status"),
            id="header-bar",
        )

        yield Grid(
            CategoryCard(
                "Machine Learning",
                "llama.cpp · SYCL inference",
                "ml",
                available=True,
            ),
            CategoryCard(
                "Rendering",
                "Blender — coming soon",
                "rendering",
                available=False,
            ),
            CategoryCard(
                "HPC / Compute",
                "GROMACS · oneAPI — coming soon",
                "hpc",
                available=False,
            ),
            CategoryCard(
                "System Info",
                "Hardware · software manifest",
                "sysinfo",
                available=True,
            ),
            id="category-grid",
        )

        yield Vertical(
            Static("[bold #7C5CFF]Recent results[/bold #7C5CFF]", id="recent-title"),
            Static(
                "[#8B949E]No results yet — run your first benchmark above.[/#8B949E]",
                id="no-results",
            ),
            id="recent-panel",
        )

        yield Footer()

    def on_mount(self) -> None:
        self._load_recent_results()

    def _load_recent_results(self) -> None:
        # TODO: load from results DB and update panel
        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "cat-ml":
            from arcbench.screens.category import CategoryScreen
            self.app.push_screen(CategoryScreen(category="ml"))
        elif btn_id == "cat-sysinfo":
            self.action_system_info()

    def action_system_info(self) -> None:
        self.notify("System info screen coming soon", title="arcbench")
