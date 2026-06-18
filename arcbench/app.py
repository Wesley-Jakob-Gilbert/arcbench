"""arcbench — Intel Arc GPU benchmark console for Linux."""

from textual.app import App, ComposeResult
from textual.binding import Binding

from arcbench.screens.welcome import WelcomeScreen
from arcbench.screens.home import HomeScreen
from arcbench.screens.category import CategoryScreen
from arcbench.screens.running import RunningScreen
from arcbench.screens.completion import CompletionScreen


class ArcBenchApp(App):
    """Main arcbench TUI application."""

    TITLE = "arcbench"
    CSS_PATH = None

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
    ]

    CSS = """
    Screen {
        background: #101214;
    }

    .title {
        color: #00A3FF;
        text-style: bold;
    }

    .subtitle {
        color: #8B949E;
    }

    .accent {
        color: #7C5CFF;
    }

    .success {
        color: #6DAA45;
    }

    .warning {
        color: #D19900;
    }

    .error {
        color: #D163A7;
    }

    .muted {
        color: #8B949E;
    }

    Button {
        background: #171A1D;
        border: tall #00A3FF;
        color: #00A3FF;
        margin: 1 2;
    }

    Button:hover {
        background: #00A3FF;
        color: #101214;
    }

    Button:focus {
        background: #00A3FF;
        color: #101214;
        border: tall #7C5CFF;
    }

    DataTable {
        background: #171A1D;
        border: round #1E2328;
    }

    DataTable > .datatable--header {
        background: #1E2328;
        color: #00A3FF;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #7C5CFF 30%;
    }

    Footer {
        background: #171A1D;
        color: #8B949E;
    }

    Header {
        background: #171A1D;
        color: #00A3FF;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

    def action_help(self) -> None:
        # TODO: push help overlay
        self.notify("Help coming soon — press ? on any screen", title="arcbench")


def main() -> None:
    app = ArcBenchApp()
    app.run()


if __name__ == "__main__":
    main()
