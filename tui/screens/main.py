"""Main generation screen with queue and DataTable progress."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static
from textual.worker import get_current_worker

from gemini_automation.accounts import AccountManager
from gemini_automation.browser import BrowserManager
from gemini_automation.config import Config
from gemini_automation.downloader import ImageDownloader
from gemini_automation.generator import GenerationResult, ImageGenerator


@dataclass
class QueueItem:
    """A single generation task in the queue."""

    id: str
    prompt: str
    account_name: str
    status: str = "Pending"
    error: str | None = None
    image_count: int = 0


class MainScreen(Screen):
    """Image generation with prompt input, queue, and progress tracking."""

    BINDINGS = [
        Binding("ctrl+n", "new_prompt", "New Prompt", show=True),
        Binding("ctrl+b", "open_batch", "Batch", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("c", "cancel_task", "Cancel", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._queue: list[QueueItem] = []
        self._is_processing = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="prompt-container"):
            yield Input(placeholder="Enter image prompt...", id="prompt-input")
            yield Button("Generate", variant="primary", id="gen-btn")
            yield Button("Batch", id="batch-btn")
        yield DataTable(id="queue-table", cursor_type="row")
        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the queue table."""
        table = self.query_one("#queue-table", DataTable)
        table.add_column("ID", key="id", width=10)
        table.add_column("Prompt", key="prompt", width=45)
        table.add_column("Account", key="account", width=15)
        table.add_column("Status", key="status", width=20)
        table.add_column("Images", key="images", width=8)
        table.zebra_stripes = True
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Refresh the status bar."""
        account = self.app.current_account or "None"
        pending = sum(1 for q in self._queue if q.status == "Pending")
        total = len(self._queue)
        bar = self.query_one("#status-bar", Static)
        bar.update(f"Account: {account} | Queue: {pending} pending / {total} total")

    def _add_to_queue(self, prompt: str) -> None:
        """Add a prompt to the generation queue."""
        account = self.app.current_account
        if not account:
            self.notify("No account selected. Press Ctrl+A.", severity="error")
            return

        task_id = uuid.uuid4().hex[:8]
        item = QueueItem(id=task_id, prompt=prompt, account_name=account)
        self._queue.append(item)

        table = self.query_one("#queue-table", DataTable)
        display_prompt = prompt[:45] + "..." if len(prompt) > 45 else prompt
        table.add_row(task_id, display_prompt, account, "Pending", "0", key=task_id)
        self._update_status_bar()

        # Start processing if idle
        if not self._is_processing:
            self._process_next()

    def _get_next_pending(self) -> QueueItem | None:
        """Get the next pending item from the queue."""
        for item in self._queue:
            if item.status == "Pending":
                return item
        return None

    def _update_task(self, task_id: str, status: str, images: int = 0) -> None:
        """Update a task's status in the DataTable."""
        table = self.query_one("#queue-table", DataTable)
        try:
            table.update_cell(task_id, "status", status)
            table.update_cell(task_id, "images", str(images))
        except Exception:
            pass
        # Update queue item
        for item in self._queue:
            if item.id == task_id:
                item.status = status
                item.image_count = images
                break
        self._update_status_bar()

    def _process_next(self) -> None:
        """Start processing the next pending item."""
        item = self._get_next_pending()
        if item:
            self._is_processing = True
            self._run_generation(item)
        else:
            self._is_processing = False

    @work(thread=False, exclusive=False)
    async def _run_generation(self, item: QueueItem) -> str:
        """Run image generation for a single queue item."""
        worker = get_current_worker()
        task_id = item.id

        config = Config.for_account(item.account_name)
        config.min_delay = self.app.min_delay
        config.max_delay = self.app.max_delay
        config.generation_timeout = self.app.generation_timeout
        config.output_dir = self.app.output_dir
        config.ensure_dirs()

        bm = BrowserManager(config)
        try:
            # Launch browser
            self._update_task(task_id, "Launching...")
            await bm.launch()

            if worker.is_cancelled:
                self._update_task(task_id, "Cancelled")
                await bm.close()
                return "Cancelled"

            # Check login
            self._update_task(task_id, "Checking login...")
            page = await bm.get_page()
            if not await bm.is_logged_in(page):
                self._update_task(task_id, "Not logged in!")
                await bm.close()
                self._is_processing = False
                self._process_next()
                return "Not logged in"

            if worker.is_cancelled:
                self._update_task(task_id, "Cancelled")
                await bm.close()
                return "Cancelled"

            # Generate image
            self._update_task(task_id, "Generating...")
            generator = ImageGenerator(page, config)
            result = await generator.generate(item.prompt)

            if worker.is_cancelled:
                self._update_task(task_id, "Cancelled")
                await bm.close()
                return "Cancelled"

            if not result.success:
                self._update_task(task_id, f"Failed: {result.error}")
                await bm.close()
                self._is_processing = False
                self._process_next()
                return f"Failed: {result.error}"

            # Download images
            self._update_task(task_id, "Downloading...")
            downloader = ImageDownloader(page, config)
            dl_result = await downloader.download_all(result)

            image_count = len(dl_result.saved_files)
            self._update_task(task_id, "Done ✓", image_count)

            # Update last used
            AccountManager().update_last_used(item.account_name)

            await bm.close()

            self.notify(
                f"Generated {image_count} image(s) for: {item.prompt[:30]}",
                severity="information",
            )

            # Process next in queue
            self._is_processing = False
            self._process_next()
            return "Success"

        except Exception as e:
            self._update_task(task_id, f"Error: {e}")
            try:
                await bm.close()
            except Exception:
                pass
            self._is_processing = False
            self._process_next()
            return f"Error: {e}"

    # --- Actions ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gen-btn":
            self.action_new_prompt()
        elif event.button.id == "batch-btn":
            self.action_open_batch()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt-input":
            self.action_new_prompt()

    def action_new_prompt(self) -> None:
        """Submit the current prompt."""
        prompt_input = self.query_one("#prompt-input", Input)
        prompt = prompt_input.value.strip()
        if not prompt:
            self.notify("Enter a prompt first", severity="warning")
            return
        self._add_to_queue(prompt)
        prompt_input.clear()
        prompt_input.focus()

    def action_open_batch(self) -> None:
        """Open batch prompt dialog."""
        from tui.screens.batch import BatchScreen

        def on_batch_result(prompts: list[str] | None) -> None:
            if prompts:
                for p in prompts:
                    self._add_to_queue(p)
                self.notify(f"Added {len(prompts)} prompts to queue")

        self.app.push_screen(BatchScreen(), callback=on_batch_result)

    def action_delete_task(self) -> None:
        """Delete selected task if pending."""
        table = self.query_one("#queue-table", DataTable)
        if table.row_count == 0:
            return
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            task_id = str(row_key.value)
        except Exception:
            return

        # Only delete if pending
        for item in self._queue:
            if item.id == task_id and item.status == "Pending":
                self._queue.remove(item)
                table.remove_row(row_key)
                self._update_status_bar()
                self.notify(f"Deleted task {task_id}")
                return
        self.notify("Can only delete pending tasks", severity="warning")

    def action_cancel_task(self) -> None:
        """Cancel running task."""
        self.workers.cancel_all()
        for item in self._queue:
            if item.status in (
                "Launching...",
                "Checking login...",
                "Generating...",
                "Downloading...",
            ):
                item.status = "Cancelled"
                self._update_task(item.id, "Cancelled")
        self._is_processing = False
        self.notify("Cancelled running tasks")
