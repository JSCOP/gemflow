"""Configuration for Gemini automation."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Configuration for Gemini browser automation."""

    profile_dir: Path = field(default_factory=lambda: Path("./gemini_profile"))
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    gemini_url: str = "https://gemini.google.com/app"
    account_name: str | None = None
    min_delay: float = 5.0
    max_delay: float = 10.0
    generation_timeout: float = 120_000  # ms
    selectors: dict = field(
        default_factory=lambda: {
            "textarea": "div.ql-editor.textarea",
            "send_button": 'button[aria-label="Send message"]',
            "generated_image": 'img[src*="googleusercontent.com"]',
            # Multi-language: EN + KR
            "tools_button": "button:has-text('Tools'), button:has-text('도구')",
            "create_images_option": ".cdk-overlay-container button:has-text('Create images'), .cdk-overlay-container button:has-text('이미지 생성하기'), .cdk-overlay-container button:has-text('이미지 만들기')",
            "deselect_tool": 'button[aria-label*="Deselect"], button[aria-label*="선택 해제"]',
            "response_complete": 'button[aria-label="Good response"], button[aria-label="대답이 마음에 들어요"]',
            "still_generating": 'button[aria-label="Stop response"], button[aria-label="대답 생성 중지"]',
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
    def from_defaults(cls, base_dir: Path | None = None) -> "Config":
        """Create config with paths relative to base_dir (defaults to cwd)."""
        base = base_dir or Path.cwd()
        return cls(
            profile_dir=base / "gemini_profile",
            output_dir=base / "output",
        )

    @classmethod
    def for_account(cls, account_name: str, base_dir: Path | None = None) -> "Config":
        """Create config with profile_dir pointing to account-specific Chrome profile."""
        base = base_dir or Path.cwd()
        return cls(
            profile_dir=base / "gemini_profiles" / account_name,
            output_dir=base / "output",
            account_name=account_name,
        )

    def ensure_dirs(self) -> None:
        """Create profile and output directories if they don't exist."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
