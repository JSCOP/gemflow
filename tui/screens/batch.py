"""Batch prompt entry modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class BatchScreen(ModalScreen[list[str] | None]):
    """Modal dialog for entering multiple prompts."""

    def compose(self) -> ComposeResult:
        with Vertical(id="batch-container"):
            yield Static("Batch Generation — Enter one prompt per line")
            yield TextArea(id="batch-input")
            with Horizontal(classes="btn-row"):
                yield Button("Start Batch", variant="primary", id="start-batch")
                yield Button("Cancel", id="cancel-batch")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-batch":
            text = self.query_one("#batch-input", TextArea).text
            prompts = [line.strip() for line in text.splitlines() if line.strip()]
            if prompts:
                self.dismiss(prompts)
            else:
                self.notify("Enter at least one prompt", severity="warning")
        elif event.button.id == "cancel-batch":
            self.dismiss(None)
