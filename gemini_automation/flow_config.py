"""Configuration for Google Flow image generation automation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _load_tier_accounts(base_dir: Path | None = None) -> dict[str, str]:
    """Load tier→account mapping from accounts.json.

    Each account entry can have an optional ``"tier"`` field (e.g. ``"ultra"``
    or ``"pro"``).  Falls back to empty mapping if file is missing.
    """
    base = base_dir or Path.cwd()
    accounts_file = base / "accounts.json"
    if not accounts_file.exists():
        return {}
    try:
        data = json.loads(accounts_file.read_text(encoding="utf-8"))
        mapping: dict[str, str] = {}
        for acct in data.get("accounts", []):
            tier = acct.get("tier")
            if tier:
                mapping[tier] = acct["name"]
        return mapping
    except Exception:
        return {}


# Lazy-loaded tier mapping (populated on first use)
TIER_ACCOUNTS: dict[str, str] = _load_tier_accounts()


@dataclass
class FlowConfig:
    """Configuration for Flow browser automation."""

    profile_dir: Path = field(default_factory=lambda: Path("./gemini_profile"))
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    flow_url: str = "https://labs.google/fx/tools/flow"
    account_name: str | None = None
    tier: str | None = None  # "ultra" or "pro"
    project_name: str | None = None  # named project for reuse
    images_per_prompt: int = 4
    min_delay: float = 3.0
    max_delay: float = 7.0
    generation_timeout: float = 120_000  # ms
    selectors: dict = field(
        default_factory=lambda: {
            # Navigation & mode (EN + KR)
            "cookie_agree": "button:has-text('Agree'), button:has-text('동의')",
            "promo_close": "button:has-text('close')",
            "new_project": "button:has-text('New project'), button:has-text('새 프로젝트')",
            "images_tab": "button:has-text('Images'), button:has-text('이미지')",
            # Project rename (EN + KR)
            "edit_project": "button:has-text('Edit project'), button:has-text('프로젝트 수정')",
            "save_edit": "button:has-text('Save edit'), button:has-text('수정사항 저장')",
            "cancel_edit": "button:has-text('Cancel edit'), button:has-text('수정 취소')",
            # Settings
            "settings_button": "button:has-text('Settings'), button:has-text('설정')",
            "outputs_per_prompt": "button:has-text('Outputs per prompt'), button:has-text('프롬프트당 출력')",
            # Prompt area
            "textarea": "textarea",
            # Create button (arrow_forward icon, not the dropdown) EN + KR
            "create_button": "button:has-text('arrow_forwardCreate'), button:has-text('arrow_forward만들기')",
            # Reference image upload
            "add_reference_button": "button:has-text('add')",
            "reference_file_input": "input[type='file']",
            "crop_and_save": "button:has-text('Crop and Save'), button:has-text('자르기 및 저장'), button:has-text('자르고 저장')",
            "reference_dismiss": "button:has-text('close'), button:has-text('닫기')",
            # Generated images from GCS
            "generated_image": "img[src*='storage.googleapis.com/ai-sandbox-videofx/image/']",
        }
    )
    browser_args: list[str] = field(
        default_factory=lambda: [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-session-crashed-bubble",
            "--no-first-run",
            "--no-default-browser-check",
        ]
    )

    @classmethod
    def for_tier(
        cls, tier: str, base_dir: Path | None = None, project_name: str | None = None
    ) -> "FlowConfig":
        """Create config for a specific tier (ultra/pro)."""
        account_name = TIER_ACCOUNTS.get(tier)
        if not account_name:
            raise ValueError(f"Unknown tier '{tier}'. Use 'ultra' or 'pro'.")
        base = base_dir or Path.cwd()
        return cls(
            profile_dir=base / "gemini_profiles" / account_name,
            output_dir=base / "output" / f"flow_{tier}",
            account_name=account_name,
            tier=tier,
            project_name=project_name,
        )

    @classmethod
    def for_account(
        cls, account_name: str, base_dir: Path | None = None
    ) -> "FlowConfig":
        """Create config with profile_dir pointing to account-specific Chrome profile."""
        base = base_dir or Path.cwd()
        tier = None
        for t, name in TIER_ACCOUNTS.items():
            if name == account_name:
                tier = t
                break
        output_subdir = f"flow_{tier}" if tier else "flow"
        return cls(
            profile_dir=base / "gemini_profiles" / account_name,
            output_dir=base / "output" / output_subdir,
            account_name=account_name,
            tier=tier,
        )

    @classmethod
    def from_defaults(cls, base_dir: Path | None = None) -> "FlowConfig":
        """Create config with default paths."""
        base = base_dir or Path.cwd()
        return cls(
            profile_dir=base / "gemini_profile",
            output_dir=base / "output" / "flow",
        )

    def ensure_dirs(self) -> None:
        """Create profile and output directories if they don't exist."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
