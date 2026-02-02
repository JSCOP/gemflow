"""Interactive browser login screen."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from gemini_automation.accounts import AccountManager
from gemini_automation.browser import BrowserManager
from gemini_automation.config import Config


class LoginScreen(Screen):
    """Opens browser for manual Google login, waits for user confirmation."""

    BINDINGS = [
        Binding("enter", "confirm_login", "Confirm Login", show=True),
        Binding("escape", "cancel_login", "Cancel", show=True),
    ]

    def __init__(self, account_name: str) -> None:
        super().__init__()
        self.account_name = account_name
        self._bm: BrowserManager | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Login: {self.account_name}", id="login-message")
        yield Static(
            "Opening browser... Please log in to your Google account.",
            id="login-status",
        )
        yield Static(
            "Press ENTER here after you finish logging in.",
            id="login-instruction",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Launch browser when screen loads."""
        self._open_browser()

    @work(thread=False)
    async def _open_browser(self) -> None:
        """Open browser at Gemini URL in background."""
        config = Config.for_account(self.account_name)
        config.ensure_dirs()
        self._bm = BrowserManager(config)
        try:
            await self._bm.launch()
            await self._bm.wait_for_login_interactive()
            status = self.query_one("#login-status", Static)
            status.update("Browser opened. Log in with your Google account.")
        except Exception as e:
            status = self.query_one("#login-status", Static)
            status.update(f"Error opening browser: {e}")

    @work(thread=False)
    async def _check_and_close(self) -> None:
        """Check login status, close browser, return to previous screen."""
        status = self.query_one("#login-status", Static)
        if not self._bm:
            status.update("Browser not ready. Wait a moment and try again.")
            return

        try:
            page = await self._bm.get_page()
            logged_in = await self._bm.is_logged_in(page)
            if logged_in:
                status.update("Login successful! Closing browser...")
                AccountManager().update_last_used(self.account_name)
                await self._bm.close()
                self._bm = None
                self.notify(
                    f"Logged in as '{self.account_name}'", severity="information"
                )
                self.app.pop_screen()
            else:
                status.update(
                    "Login not detected. Complete login in browser, then press ENTER again."
                )
        except Exception as e:
            status.update(f"Error checking login: {e}")

    def action_confirm_login(self) -> None:
        """User confirms they finished logging in."""
        self._check_and_close()

    @work(thread=False)
    async def _close_browser(self) -> None:
        """Close browser without checking login."""
        if self._bm:
            await self._bm.close()
            self._bm = None

    def action_cancel_login(self) -> None:
        """Cancel login and return."""
        self._close_browser()
        self.app.pop_screen()
