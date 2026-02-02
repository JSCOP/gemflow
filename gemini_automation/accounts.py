"""Multi-account manager with JSON persistence."""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class Account:
    """A Google account used for Gemini automation."""

    name: str
    profile_dir: str  # stored as string in JSON, converted to Path when needed
    created_at: str
    last_used: str | None = None


class AccountManager:
    """Manages multiple Google accounts with separate Chrome profiles."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        base = Path(base_dir) if base_dir else Path.cwd()
        self.profiles_dir = base / "gemini_profiles"
        self.accounts_file = base / "accounts.json"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Account]:
        """Load accounts from JSON file."""
        if not self.accounts_file.exists():
            return []
        with open(self.accounts_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Account(**a) for a in data.get("accounts", [])]

    def save(self, accounts: list[Account]) -> None:
        """Save accounts to JSON file."""
        data = {"accounts": [asdict(a) for a in accounts]}
        with open(self.accounts_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create(self, name: str) -> Account:
        """Create a new account. Raises ValueError on invalid/duplicate name."""
        if not name or not _NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid account name '{name}'. Use alphanumeric, hyphens, underscores only."
            )
        accounts = self.load()
        if any(a.name == name for a in accounts):
            raise ValueError(f"Account '{name}' already exists.")

        profile_dir = self.profiles_dir / name
        profile_dir.mkdir(parents=True, exist_ok=True)

        account = Account(
            name=name,
            profile_dir=str(profile_dir),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        accounts.append(account)
        self.save(accounts)
        return account

    def remove(self, name: str) -> None:
        """Remove account and delete its profile directory."""
        accounts = self.load()
        accounts = [a for a in accounts if a.name != name]
        self.save(accounts)

        profile_dir = self.profiles_dir / name
        if profile_dir.exists():
            for attempt in range(3):
                try:
                    shutil.rmtree(profile_dir)
                    break
                except PermissionError:
                    if attempt < 2:
                        time.sleep(1)
                    else:
                        raise

    def get(self, name: str) -> Account | None:
        """Look up account by name."""
        for a in self.load():
            if a.name == name:
                return a
        return None

    def list_accounts(self) -> list[Account]:
        """Return all accounts."""
        return self.load()

    def update_last_used(self, name: str) -> None:
        """Update last_used timestamp for an account."""
        accounts = self.load()
        for a in accounts:
            if a.name == name:
                a.last_used = datetime.now(timezone.utc).isoformat()
                break
        self.save(accounts)

    def get_profile_dir(self, name: str) -> Path:
        """Return profile directory path for an account."""
        return self.profiles_dir / name
