"""Settings screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static


class SettingsScreen(Screen):
    """Configure generation settings."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Settings", id="title-bar")
        with Vertical():
            with Horizontal(classes="setting-row"):
                yield Label("Min Delay (s):")
                yield Input(
                    value=str(self.app.min_delay),
                    id="min_delay",
                    type="number",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Max Delay (s):")
                yield Input(
                    value=str(self.app.max_delay),
                    id="max_delay",
                    type="number",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Timeout (ms):")
                yield Input(
                    value=str(self.app.generation_timeout),
                    id="generation_timeout",
                    type="number",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Output Dir:")
                yield Input(
                    value=str(self.app.output_dir),
                    id="output_dir",
                )
            with Horizontal(classes="btn-row"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Back", id="back-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_settings()
        elif event.button.id == "back-btn":
            self.action_go_back()

    def _save_settings(self) -> None:
        """Save settings to app state."""
        from pathlib import Path

        try:
            self.app.min_delay = float(self.query_one("#min_delay", Input).value)
            self.app.max_delay = float(self.query_one("#max_delay", Input).value)
            self.app.generation_timeout = float(
                self.query_one("#generation_timeout", Input).value
            )
            self.app.output_dir = Path(self.query_one("#output_dir", Input).value)
            self.notify("Settings saved", severity="information")
            self.app.pop_screen()
        except ValueError as e:
            self.notify(f"Invalid value: {e}", severity="error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
