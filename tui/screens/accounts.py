"""Account management screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static, Button

from gemini_automation.accounts import AccountManager


class AccountScreen(Screen):
    """Account selection and management."""

    BINDINGS = [
        Binding("a", "add_account", "Add", show=True),
        Binding("r", "remove_account", "Remove", show=True),
        Binding("l", "login_account", "Login", show=True),
        Binding("enter", "select_and_continue", "Select & Continue", show=True),
        Binding("o", "logout_account", "Logout", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.account_mgr = AccountManager()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Account Manager", id="title-bar")
        yield DataTable(id="account-table", cursor_type="row")
        with Horizontal(classes="btn-row"):
            yield Input(placeholder="New account name...", id="add-input")
            yield Button("Add", id="add-btn", variant="primary")
            yield Button("Remove", id="remove-btn", variant="error")
            yield Button("Login", id="login-btn", variant="warning")
            yield Button("Logout", id="logout-btn")
            yield Button("Continue →", id="continue-btn", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        """Populate the account table."""
        table = self.query_one("#account-table", DataTable)
        table.add_column("Name", key="name", width=20)
        table.add_column("Created", key="created", width=22)
        table.add_column("Last Used", key="last_used", width=22)
        table.zebra_stripes = True
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Reload accounts into the table."""
        table = self.query_one("#account-table", DataTable)
        table.clear()
        for acc in self.account_mgr.list_accounts():
            created = acc.created_at[:19].replace("T", " ") if acc.created_at else "-"
            last_used = (
                acc.last_used[:19].replace("T", " ") if acc.last_used else "Never"
            )
            table.add_row(acc.name, created, last_used, key=acc.name)

    def _get_selected_name(self) -> str | None:
        """Get the account name of the selected row."""
        table = self.query_one("#account-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            return str(row_key.value)
        except Exception:
            return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        actions = {
            "add-btn": self.action_add_account,
            "remove-btn": self.action_remove_account,
            "login-btn": self.action_login_account,
            "logout-btn": self.action_logout_account,
            "continue-btn": self.action_select_and_continue,
        }
        action = actions.get(event.button.id)
        if action:
            action()

    def action_add_account(self) -> None:
        """Create a new account."""
        name_input = self.query_one("#add-input", Input)
        name = name_input.value.strip()
        if not name:
            self.notify("Enter an account name first", severity="warning")
            return
        try:
            self.account_mgr.create(name)
            self.notify(f"Account '{name}' created", severity="information")
            name_input.clear()
            self._refresh_table()
        except ValueError as e:
            self.notify(str(e), severity="error")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the add-input field."""
        if event.input.id == "add-input":
            self.action_add_account()

    def action_remove_account(self) -> None:
        """Remove the selected account."""
        name = self._get_selected_name()
        if not name:
            self.notify("Select an account first", severity="warning")
            return
        try:
            self.account_mgr.remove(name)
            self.notify(f"Account '{name}' removed", severity="information")
            if self.app.current_account == name:
                self.app.current_account = None
            self._refresh_table()
        except Exception as e:
            self.notify(f"Remove failed: {e}", severity="error")

    def action_login_account(self) -> None:
        """Open LoginScreen for selected account."""
        name = self._get_selected_name()
        if not name:
            self.notify("Select an account first", severity="warning")
            return
        from tui.screens.login import LoginScreen

        self.app.push_screen(LoginScreen(account_name=name))

    def action_logout_account(self) -> None:
        """Clear login state for selected account."""
        name = self._get_selected_name()
        if not name:
            self.notify("Select an account first", severity="warning")
            return
        import shutil

        profile_dir = self.account_mgr.get_profile_dir(name)
        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir)
                profile_dir.mkdir(parents=True, exist_ok=True)
                self.notify(f"Logged out '{name}'", severity="information")
            except Exception as e:
                self.notify(f"Logout failed: {e}", severity="error")
        else:
            self.notify(f"Account '{name}' has no profile data", severity="warning")

    def action_select_and_continue(self) -> None:
        """Select account and go to MainScreen."""
        name = self._get_selected_name()
        if not name:
            self.notify("Select an account first", severity="warning")
            return
        self.app.current_account = name
        self.app.switch_to_main()
