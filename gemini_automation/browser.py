"""Persistent Chrome browser manager for Gemini automation."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

from gemini_automation.config import Config


class BrowserManager:
    """Manages a persistent Chrome browser context with anti-detection."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserManager":
        await self.launch()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def launch(self) -> None:
        """Launch persistent Chrome browser context."""
        self.config.ensure_dirs()
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.profile_dir.resolve()),
            channel="chrome",
            headless=False,
            args=self.config.browser_args,
            viewport={"width": 1920, "height": 1080},
            no_viewport=False,
        )

    async def get_page(self) -> Page:
        """Return first existing page or create a new one."""
        if not self._context:
            raise RuntimeError("Browser not launched. Call launch() first.")
        pages = self._context.pages
        if pages:
            return pages[0]
        return await self._context.new_page()

    async def close(self) -> None:
        """Gracefully shut down browser context and playwright."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def is_logged_in(self, page: Page | None = None) -> bool:
        """Check if user is logged in to Gemini by looking for the textarea."""
        if page is None:
            page = await self.get_page()
        try:
            await page.goto(self.config.gemini_url, wait_until="domcontentloaded")
            textarea = page.locator(self.config.selectors["textarea"])
            await textarea.wait_for(state="visible", timeout=15_000)
            return True
        except Exception:
            return False

    async def wait_for_login(self, timeout_seconds: float = 300) -> bool:
        """Navigate to Gemini and poll until user logs in manually.

        Returns True if login detected, False on timeout.
        """
        page = await self.get_page()
        await page.goto(self.config.gemini_url, wait_until="domcontentloaded")
        print("Please log in to your Google account in the browser window...")
        print(f"Waiting up to {int(timeout_seconds)}s for login...")

        elapsed = 0.0
        poll_interval = 3.0
        while elapsed < timeout_seconds:
            try:
                textarea = page.locator(self.config.selectors["textarea"])
                await textarea.wait_for(state="visible", timeout=5_000)
                return True
            except Exception:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
        return False

    async def wait_for_login_interactive(self) -> bool:
        """Navigate to Gemini and keep browser open for manual login.

        The caller (TUI) should wait for user confirmation, then call
        is_logged_in() to verify.
        Returns True when browser is ready for user interaction.
        """
        page = await self.get_page()
        await page.goto(self.config.gemini_url, wait_until="domcontentloaded")
        return True

    async def logout(self) -> None:
        """Close browser and delete profile directory to clear login state."""
        await self.close()
        if self.config.profile_dir.exists():
            for attempt in range(3):
                try:
                    shutil.rmtree(self.config.profile_dir)
                    break
                except PermissionError:
                    if attempt < 2:
                        await asyncio.sleep(1)
                    else:
                        raise
