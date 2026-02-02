"""Main Textual TUI application for Gemini image generation."""

from __future__ import annotations

from pathlib import Path
from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive


class GeminiApp(App):
    """Gemini Image Generator TUI."""

    TITLE = "Gemini Image Generator"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+a", "switch_accounts", "Accounts"),
        Binding("ctrl+s", "switch_settings", "Settings"),
    ]

    # Reactive state
    current_account: reactive[str | None] = reactive(None)
    is_logged_in: reactive[bool] = reactive(False)

    # Settings (in-memory, modified by SettingsScreen)
    min_delay: float = 5.0
    max_delay: float = 10.0
    generation_timeout: float = 120_000
    output_dir: Path = Path("./output")

    def on_mount(self) -> None:
        """Start on AccountScreen."""
        from tui.screens.accounts import AccountScreen

        self.install_screen(AccountScreen(), name="accounts")
        self.push_screen("accounts")

    def action_switch_accounts(self) -> None:
        """Switch to account management screen."""
        from tui.screens.accounts import AccountScreen

        self.push_screen(AccountScreen())

    def action_switch_settings(self) -> None:
        """Switch to settings screen."""
        from tui.screens.settings import SettingsScreen

        self.push_screen(SettingsScreen())

    def switch_to_main(self) -> None:
        """Navigate to main generation screen."""
        from tui.screens.main import MainScreen

        self.switch_screen(MainScreen())
