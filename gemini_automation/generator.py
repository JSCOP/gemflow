"""Image generation logic for Gemini web automation."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from playwright.async_api import Page

from gemini_automation.config import Config
from gemini_automation.overlay import BrowserOverlay


@dataclass
class GenerationResult:
    """Result of a single image generation attempt."""

    prompt: str
    image_urls: list[str] = field(default_factory=list)
    success: bool = False
    error: str | None = None


class ImageGenerator:
    """Generates images on Gemini by controlling the browser."""

    def __init__(
        self, page: Page, config: Config, overlay: BrowserOverlay | None = None
    ) -> None:
        self.page = page
        self.config = config
        self.overlay = overlay

    async def _activate_create_images_tool(self) -> str | None:
        """Click Tools → Create images to activate image generation mode.

        The toolbar only appears after focusing the textarea, so we click
        the textarea first to reveal it.

        Returns None on success, or an error message string on failure.
        """
        # Focus textarea to reveal the toolbar buttons
        textarea = self.page.locator(self.config.selectors["textarea"])
        await textarea.click()
        await asyncio.sleep(1)

        # Click the "Tools" button
        tools_btn = self.page.locator(self.config.selectors["tools_button"]).first
        try:
            await tools_btn.wait_for(state="visible", timeout=10_000)
        except Exception:
            return "Tools button not found on page"
        await tools_btn.click()
        await asyncio.sleep(1)

        # Click "Create images" from the dropdown
        create_images = self.page.locator(
            self.config.selectors["create_images_option"]
        ).first
        try:
            await create_images.wait_for(state="visible", timeout=5_000)
        except Exception:
            # Close dropdown if it opened but option not found
            await self.page.keyboard.press("Escape")
            return "Create images option not found in Tools menu"
        await create_images.click()
        await asyncio.sleep(1)
        return None

    def _is_page_alive(self) -> bool:
        """Check if the page/browser is still open."""
        try:
            return not self.page.is_closed()
        except Exception:
            return False

    async def _dismiss_promo_dialogs(self) -> None:
        """Dismiss any promotional overlay dialogs (Deep Research, etc.).

        These dialogs appear in the cdk-overlay-container and block clicks
        on the textarea and toolbar buttons.
        """
        dismiss_selectors = [
            # EN: "No, thanks" / KR: various dismiss buttons
            'button:has-text("No, thanks")',
            'button:has-text("아니요")',
            'button:has-text("괜찮습니다")',
            'button:has-text("닫기")',
            # Generic close/dismiss in overlay
            '.cdk-overlay-container button:has-text("No")',
            '.cdk-overlay-container button:has-text("아니")',
        ]
        for sel in dismiss_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

        # Fallback: press Escape to close any overlay
        try:
            overlay = self.page.locator(".cdk-overlay-container .cdk-overlay-backdrop")
            if await overlay.count() > 0 and await overlay.is_visible():
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(1)
        except Exception:
            pass

    async def generate(self, prompt: str) -> GenerationResult:
        """Generate images for a single prompt in a new chat."""
        try:
            # Navigate to new chat
            await self.page.goto(self.config.gemini_url, wait_until="domcontentloaded")

            if self.overlay:
                await self.overlay.update(
                    status="Loading page...",
                    skip_enabled=True,
                    next_enabled=False,
                )

            # Wait for textarea
            textarea = self.page.locator(self.config.selectors["textarea"])
            try:
                await textarea.wait_for(state="visible", timeout=30_000)
            except Exception:
                return GenerationResult(
                    prompt=prompt,
                    success=False,
                    error="Textarea not found - may not be logged in",
                )

            # Dismiss any promo dialogs that may block interaction
            await self._dismiss_promo_dialogs()

            if self.overlay:
                await self.overlay.update(status="Activating image tool...")

            # Activate "Create images" tool BEFORE entering prompt.
            # Without this, Gemini generates text instead of images.
            tool_error = await self._activate_create_images_tool()
            if tool_error:
                return GenerationResult(
                    prompt=prompt,
                    success=False,
                    error=f"Failed to activate image tool: {tool_error}",
                )

            if self.overlay:
                await self.overlay.update(
                    status=f"Sending: {prompt[:60]}{'…' if len(prompt) > 60 else ''}",
                )

            # Enter prompt and send
            await textarea.click()
            await textarea.fill(prompt)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")

            # Wait for REAL generated images (not UI thumbnails/avatars).
            min_dim = 256
            poll_interval = 5.0
            timeout_s = self.config.generation_timeout / 1000
            elapsed = 0.0
            image_urls: list[str] = []

            while elapsed < timeout_s:
                # Check skip before sleeping
                if self.overlay and self.overlay.check_skip():
                    return GenerationResult(
                        prompt=prompt,
                        success=False,
                        error="Skipped by user",
                    )

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                if self.overlay:
                    await self.overlay.update(
                        status="Waiting for images...",
                        sub=f"⏳ {elapsed:.0f}s / {timeout_s:.0f}s",
                    )

                # Guard: check page is still alive
                if not self._is_page_alive():
                    return GenerationResult(
                        prompt=prompt,
                        success=False,
                        error="Browser page was closed during generation",
                    )

                # Check if Gemini finished responding (feedback buttons appear)
                response_complete = False
                try:
                    good_btn = self.page.locator(
                        self.config.selectors["response_complete"]
                    )
                    if await good_btn.count() > 0 and await good_btn.first.is_visible():
                        response_complete = True
                except Exception:
                    pass

                # Collect real images
                image_locator = self.page.locator(
                    self.config.selectors["generated_image"]
                )
                try:
                    elements = await image_locator.all()
                except Exception:
                    return GenerationResult(
                        prompt=prompt,
                        success=False,
                        error="Lost connection to browser during generation",
                    )

                for el in elements:
                    try:
                        visible = await el.is_visible()
                        if not visible:
                            continue
                        dims = await el.evaluate(
                            "el => ({w: el.naturalWidth, h: el.naturalHeight})"
                        )
                        if dims.get("w", 0) >= min_dim and dims.get("h", 0) >= min_dim:
                            src = await el.get_attribute("src")
                            if src and src not in image_urls:
                                image_urls.append(src)
                    except Exception:
                        continue

                if image_urls:
                    # Found images — wait a bit for more, then collect
                    await asyncio.sleep(3)
                    try:
                        elements = await image_locator.all()
                    except Exception:
                        break
                    for el in elements:
                        try:
                            visible = await el.is_visible()
                            if not visible:
                                continue
                            dims = await el.evaluate(
                                "el => ({w: el.naturalWidth, h: el.naturalHeight})"
                            )
                            if (
                                dims.get("w", 0) >= min_dim
                                and dims.get("h", 0) >= min_dim
                            ):
                                src = await el.get_attribute("src")
                                if src and src not in image_urls:
                                    image_urls.append(src)
                        except Exception:
                            continue
                    break

                # Response finished but NO images → text-only (refusal/error)
                if response_complete and not image_urls:
                    return GenerationResult(
                        prompt=prompt,
                        success=False,
                        error="Gemini responded with text only (likely refused due to content policy)",
                    )

            if not image_urls:
                return GenerationResult(
                    prompt=prompt,
                    success=False,
                    error=f"Image generation timed out after {timeout_s:.0f}s",
                )

            return GenerationResult(
                prompt=prompt,
                image_urls=image_urls,
                success=True,
            )

        except Exception as e:
            return GenerationResult(
                prompt=prompt,
                success=False,
                error=str(e),
            )

    async def generate_batch(self, prompts: list[str]) -> list[GenerationResult]:
        """Generate images for multiple prompts sequentially with delays."""
        results = []
        total = len(prompts)

        for i, prompt in enumerate(prompts, 1):
            print(
                f"[{i}/{total}] Generating: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            )

            if self.overlay:
                await self.overlay.update(
                    progress=f"{i} / {total}",
                    status=f"Starting: {prompt[:50]}{'…' if len(prompt) > 50 else ''}",
                    sub="",
                    skip_enabled=True,
                    next_enabled=False,
                )

            # Guard: abort remaining prompts if browser died
            if not self._is_page_alive():
                print("  ✗ Browser closed — skipping remaining prompts")
                for remaining in prompts[i - 1 :]:
                    results.append(
                        GenerationResult(
                            prompt=remaining,
                            success=False,
                            error="Browser was closed before this prompt",
                        )
                    )
                break

            result = await self.generate(prompt)

            if result.success:
                print(f"  ✓ Got {len(result.image_urls)} image(s)")
            else:
                print(f"  ✗ Failed: {result.error}")

            results.append(result)

            # Random delay between prompts (skip after last)
            if i < total:
                delay = random.uniform(self.config.min_delay, self.config.max_delay)
                print(f"  Waiting {delay:.1f}s before next prompt...")

                if self.overlay:
                    await self.overlay.update(
                        status=f"✓ Done — waiting {delay:.0f}s",
                        sub="Click Next to skip wait",
                        skip_enabled=False,
                        next_enabled=True,
                    )
                    await self.overlay.wait_for_next_or_timeout(delay)
                else:
                    await asyncio.sleep(delay)

        if self.overlay:
            await self.overlay.update(
                status="✅ Batch complete",
                sub=f"{total} prompts processed",
                skip_enabled=False,
                next_enabled=False,
            )

        return results
