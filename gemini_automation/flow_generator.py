"""Image generation logic for Google Flow (labs.google/fx/tools/flow).

Flow generates images via a project-based canvas UI:
1. Navigate to Flow → create new project
2. Switch to Images mode
3. Open Settings → set outputs per prompt to 4
4. Enter prompt → click Create
5. Wait for generated images (served from GCS)
6. Download via URL

All prompts in a batch are generated within the same project.

Key differences from Gemini:
- No "Tools → Create images" activation needed
- Configurable outputs per prompt (1-4, default 4)
- Images are on storage.googleapis.com, not googleusercontent.com
- Each generation creates entries in the project timeline
- Multiple prompts reuse the same project
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page

from gemini_automation.flow_config import FlowConfig


@dataclass
class FlowGenerationResult:
    """Result of a single Flow image generation attempt."""

    prompt: str
    image_urls: list[str] = field(default_factory=list)
    success: bool = False
    error: str | None = None


class FlowImageGenerator:
    """Generates images on Google Flow by controlling the browser."""

    def __init__(self, page: Page, config: FlowConfig) -> None:
        self.page = page
        self.config = config
        self._project_initialized = False

    async def _dismiss_consent_and_promos(self) -> None:
        """Handle cookie consent and promotional banners."""
        # Cookie consent
        try:
            agree = self.page.locator(self.config.selectors["cookie_agree"])
            if await agree.count() > 0 and await agree.first.is_visible():
                await agree.first.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Promo close button
        try:
            close_btn = self.page.locator(self.config.selectors["promo_close"]).first
            if await close_btn.count() > 0 and await close_btn.is_visible():
                await close_btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

    async def _go_to_dashboard(self) -> str | None:
        """Navigate to Flow dashboard. Returns error or None."""
        try:
            await self.page.goto(
                self.config.flow_url, wait_until="domcontentloaded", timeout=30_000
            )
        except Exception:
            pass
        await asyncio.sleep(3)

        await self._dismiss_consent_and_promos()

        # If on landing page, click "Create with Flow" to enter dashboard
        create_with_flow = self.page.locator("button:has-text('Create with Flow')")
        try:
            if (
                await create_with_flow.count() > 0
                and await create_with_flow.first.is_visible()
            ):
                await create_with_flow.first.click()
                await asyncio.sleep(5)
                await self._dismiss_consent_and_promos()
        except Exception:
            pass

        return None

    async def _find_project_by_name(self, name: str) -> bool:
        """On dashboard, look for a project with the given name and click it.

        Dashboard DOM structure:
        - Project names are <span> elements (NOT buttons)
        - Clickable card area is an <a href="/project/{uuid}"> (empty text)
        - Both are siblings inside a card container div

        Strategy: Find span with matching text → walk up to card container
        → find sibling <a> with project URL → click it.
        """
        href = await self.page.evaluate(
            """(name) => {
            const spans = document.querySelectorAll('span');
            for (const span of spans) {
                // Get only the direct text of this span (exclude nested button text
                // like "editEdit project" which is inside the same span)
                const firstTextNode = Array.from(span.childNodes).find(n => n.nodeType === 3);
                const spanText = firstTextNode ? firstTextNode.textContent.trim() : '';
                if (spanText === name) {
                    // Walk up to card container to find the sibling <a> link
                    let container = span.parentElement;
                    for (let i = 0; i < 5 && container; i++) {
                        const link = container.querySelector('a[href*="/project/"]');
                        if (link) return link.getAttribute('href');
                        container = container.parentElement;
                    }
                }
            }
            return null;
        }""",
            name,
        )

        if href:
            # Navigate directly to the project URL
            full_url = f"https://labs.google{href}" if href.startswith("/") else href
            await self.page.goto(
                full_url, wait_until="domcontentloaded", timeout=30_000
            )
            await asyncio.sleep(5)
            if "/project/" in self.page.url:
                return True
        return False

    async def _rename_project(self, name: str) -> str | None:
        """Rename the current project. Returns error or None."""
        edit_btn = self.page.locator(self.config.selectors["edit_project"])
        try:
            await edit_btn.first.wait_for(state="visible", timeout=5_000)
            await edit_btn.first.click()
            await asyncio.sleep(1)
        except Exception:
            return "Edit project button not found"

        # Find the project name input (first visible input that's not search/textarea)
        inputs = await self.page.locator("input").all()
        name_input = None
        for inp in inputs:
            try:
                if await inp.is_visible():
                    placeholder = await inp.get_attribute("placeholder") or ""
                    # Skip search inputs
                    if "search" in placeholder.lower() or "검색" in placeholder.lower():
                        continue
                    name_input = inp
                    break
            except Exception:
                continue

        if not name_input:
            # Cancel edit
            cancel = self.page.locator(self.config.selectors["cancel_edit"])
            try:
                await cancel.first.click()
            except Exception:
                pass
            return "Project name input not found"

        # Clear and type new name
        await name_input.click(click_count=3)  # select all
        await name_input.fill(name)
        await asyncio.sleep(0.5)

        # Save
        save_btn = self.page.locator(self.config.selectors["save_edit"])
        try:
            await save_btn.first.wait_for(state="visible", timeout=3_000)
            await save_btn.first.click()
            await asyncio.sleep(1)
        except Exception:
            return "Save edit button not found"

        return None

    async def _ensure_project(self) -> str | None:
        """Navigate to Flow, find or create a named project. Returns error or None."""
        if self._project_initialized:
            return None

        dash_error = await self._go_to_dashboard()
        if dash_error:
            return dash_error

        project_name = self.config.project_name

        # If project_name is set, try to find existing project
        if project_name:
            # Check dashboard for existing project
            new_proj = self.page.locator(self.config.selectors["new_project"])
            try:
                await new_proj.first.wait_for(state="visible", timeout=10_000)
            except Exception:
                return "Failed to reach dashboard — may not be logged in"

            found = await self._find_project_by_name(project_name)
            if found:
                print(f"  Found existing project: '{project_name}'")
            else:
                # Create new and rename
                await new_proj.first.click()
                await asyncio.sleep(5)
                if "/project/" not in self.page.url:
                    return f"Failed to create project. URL: {self.page.url}"
                rename_error = await self._rename_project(project_name)
                if rename_error:
                    print(f"  Warning: Could not rename project: {rename_error}")
                else:
                    print(f"  Created new project: '{project_name}'")
        else:
            # No name — just create new project
            new_proj = self.page.locator(self.config.selectors["new_project"])
            try:
                await new_proj.first.wait_for(state="visible", timeout=10_000)
                await new_proj.first.click()
                await asyncio.sleep(5)
            except Exception:
                return "Failed to find 'New project' button — may not be logged in"

        # Verify we're in a project
        if "/project/" not in self.page.url:
            return f"Failed to enter project. URL: {self.page.url}"

        # Switch to Images mode
        images_btn = self.page.locator(self.config.selectors["images_tab"])
        try:
            await images_btn.first.wait_for(state="visible", timeout=10_000)
            await images_btn.first.click()
            await asyncio.sleep(2)
        except Exception:
            return "Failed to switch to Images mode"

        # Set outputs per prompt (default: 4)
        count_error = await self._set_image_count(self.config.images_per_prompt)
        if count_error:
            print(f"  Warning: {count_error}")

        self._project_initialized = True
        return None

    async def _set_image_count(self, count: int) -> str | None:
        """Open Settings and set 'Outputs per prompt' to the desired count.

        Returns None on success, or an error message string.
        """
        # Open settings panel
        settings_btn = self.page.locator(self.config.selectors["settings_button"])
        try:
            await settings_btn.wait_for(state="visible", timeout=5_000)
            await settings_btn.click()
            await asyncio.sleep(1)
        except Exception:
            return "Settings button not found"

        # Click "Outputs per prompt" dropdown
        outputs_btn = self.page.locator(self.config.selectors["outputs_per_prompt"])
        try:
            await outputs_btn.wait_for(state="visible", timeout=5_000)
            await outputs_btn.click()
            await asyncio.sleep(1)
        except Exception:
            # Close settings if opened
            await self.page.keyboard.press("Escape")
            return "Outputs per prompt dropdown not found"

        # Select the desired count from dropdown options
        option = self.page.locator(f"[role='option']:has-text('{count}')").first
        try:
            await option.wait_for(state="visible", timeout=3_000)
            await option.click()
            await asyncio.sleep(1)
        except Exception:
            await self.page.keyboard.press("Escape")
            return f"Option '{count}' not found in outputs dropdown"

        # Close settings panel by clicking elsewhere
        await self.page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        return None

    async def _upload_reference_image(self, image_path: str) -> str | None:
        """Upload a reference image via the add button near the textarea.

        Flow:
        1. Click 'add' button → opens reference image picker modal
        2. Set file on the hidden input[type='file'] → triggers upload
        3. "Crop your ingredient" modal appears with crop tool
        4. Click "Crop and Save" to confirm → image attached as reference
        5. Wait for thumbnail to appear near textarea

        IMPORTANT: After crop & save, the reference is automatically attached.
        The uploaded image appears at picker index 1 (right after Upload button).
        For subsequent prompts, we simply click index 1 to reattach.

        Returns error message or None on success.
        """
        resolved = Path(image_path).resolve()
        if not resolved.exists():
            return f"Reference image not found: {resolved}"

        # Click the add button (last one matching, near textarea)
        add_btn = self.page.locator(self.config.selectors["add_reference_button"]).last
        try:
            await add_btn.wait_for(state="visible", timeout=5_000)
            await add_btn.click()
            await asyncio.sleep(2)
        except Exception:
            return "Add reference button not found"

        # Set file on the hidden input
        file_input = self.page.locator(self.config.selectors["reference_file_input"])
        try:
            await file_input.set_input_files(str(resolved))
            await asyncio.sleep(3)  # Wait for upload + crop modal to appear
        except Exception as e:
            await self.page.keyboard.press("Escape")
            return f"Failed to upload reference image: {e}"

        # Click "Crop and Save" on the crop modal (EN + KR)
        crop_save = self.page.locator(self.config.selectors["crop_and_save"])
        try:
            await crop_save.first.wait_for(state="visible", timeout=10_000)
            await crop_save.first.click()
        except Exception:
            # Try cancel / escape if crop modal didn't appear
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(1)
            await self.page.keyboard.press("Escape")
            return (
                "Crop and Save button not found — reference image may not have uploaded"
            )

        # Wait for the crop modal to close
        for _ in range(15):
            await asyncio.sleep(1)
            still_open = False
            try:
                still_open = (
                    await crop_save.first.is_visible()
                    if await crop_save.count() > 0
                    else False
                )
            except Exception:
                pass
            if not still_open:
                break

        # Poll for reference thumbnail to appear near textarea
        thumbnail_ready = False
        for _ in range(15):
            await asyncio.sleep(1)
            try:
                thumbnail_ready = await self.page.evaluate("""() => {
                    const els = document.querySelectorAll('button, div');
                    for (const el of els) {
                        if (el.offsetParent === null && el.offsetWidth === 0) continue;
                        if (el.offsetWidth > 100 || el.offsetHeight > 100) continue;
                        if (el.offsetWidth < 20) continue;
                        const bg = getComputedStyle(el).backgroundImage;
                        if (bg && bg !== 'none' &&
                            (bg.startsWith('url("data:image/') ||
                             bg.includes('storage.googleapis.com'))) {
                            return true;
                        }
                    }
                    return false;
                }""")
                if thumbnail_ready:
                    break
            except Exception:
                pass

        if thumbnail_ready:
            print(f"  Uploaded reference image: {resolved.name}")
        else:
            print(
                f"  Uploaded reference image: {resolved.name} (thumbnail not confirmed)"
            )

        return None

    async def _clear_reference_images(self) -> None:
        """Remove any attached reference images from the prompt area.

        Reference images appear as small thumbnails near the textarea.
        Click the 'x' / close button on each to remove them.
        """
        try:
            # Reference image thumbnails near the prompt area have close buttons
            close_btns = self.page.locator(
                "button[aria-label='Remove'], button[aria-label='삭제']"
            )
            count = await close_btns.count()
            for i in range(count):
                try:
                    await close_btns.first.click()
                    await asyncio.sleep(0.5)
                except Exception:
                    break
        except Exception:
            pass

    async def _reattach_reference_from_picker(self) -> str | None:
        """Re-attach a reference image from the ingredient picker.

        After each generation Flow removes the attached reference. This method
        opens the ingredient picker and clicks the uploaded reference tile.

        IMPORTANT DISCOVERY (via Chrome DevTools analysis):
        - Uploaded reference images appear at picker index 1 (right after Upload button)
        - Generated images do NOT get added to the picker
        - The uploaded reference stays at index 1 throughout the session
        - URL matching is unreliable because uploads initially have data:image URLs

        Therefore, we simply click index 1 (the tile right after Upload button).

        Returns error message or None on success.
        """
        # Open the ingredient picker
        add_btn = self.page.locator(self.config.selectors["add_reference_button"]).last
        try:
            await add_btn.wait_for(state="visible", timeout=5_000)
            await add_btn.click()
            await asyncio.sleep(2)
        except Exception:
            return "Add reference button not found for re-attach"

        # Click the tile at index 1 (right after Upload button)
        # This is where the uploaded reference image always appears
        clicked = await self.page.evaluate("""() => {
            const menu = document.querySelector('[role="menu"]');
            if (!menu) return { clicked: false, error: 'No menu found' };

            const btns = menu.querySelectorAll('button');
            let tileIndex = 0;

            for (const btn of btns) {
                const rect = btn.getBoundingClientRect();
                // Filter to only large tiles (100-200px)
                if (rect.width < 100 || rect.width > 200) continue;
                if (rect.height < 100 || rect.height > 200) continue;

                // Skip index 0 (Upload button), click index 1 (uploaded reference)
                if (tileIndex === 1) {
                    btn.click();
                    return { clicked: true, tileIndex: 1 };
                }
                tileIndex++;
            }
            return { clicked: false, error: 'Index 1 tile not found' };
        }""")

        if not clicked.get("clicked"):
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(1)
            return clicked.get("error", "No ingredient tile found in picker")

        # Wait for the picker to close and the thumbnail to appear
        thumbnail_ready = False
        for _ in range(10):
            await asyncio.sleep(1)
            thumbnail_ready = await self.page.evaluate("""() => {
                const els = document.querySelectorAll('button, div');
                for (const el of els) {
                    if (el.offsetParent === null && el.offsetWidth === 0) continue;
                    if (el.offsetWidth > 100 || el.offsetHeight > 100) continue;
                    if (el.offsetWidth < 20) continue;
                    const bg = getComputedStyle(el).backgroundImage;
                    if (bg && bg !== 'none' &&
                        (bg.startsWith('url("data:image/') ||
                         bg.includes('storage.googleapis.com'))) {
                        return true;
                    }
                }
                return false;
            }""")
            if thumbnail_ready:
                break

        if not thumbnail_ready:
            print("  Warning: Reference thumbnail did not appear after re-attach")
        else:
            print("  Re-attached reference from ingredient picker (index 1)")
        await asyncio.sleep(1)
        return None

    async def _detect_content_rejection(self) -> str | None:
        """Check the page for content policy / copyright rejection messages.

        Returns an error message if rejection detected, None otherwise.
        """
        # Common rejection phrases in EN and KR
        rejection_phrases = [
            "can't generate",
            "unable to generate",
            "content policy",
            "policy violation",
            "copyright",
            "not allowed",
            "couldn't create",
            "violates",
            "harmful content",
            "unsafe content",
            "생성할 수 없",
            "정책 위반",
            "저작권",
            "허용되지 않",
            "유해한 콘텐츠",
        ]
        try:
            # Check for error/warning banners or text on the page
            body_text = await self.page.evaluate(
                "() => document.body.innerText.substring(0, 5000)"
            )
            body_lower = body_text.lower()
            for phrase in rejection_phrases:
                if phrase.lower() in body_lower:
                    # Extract the relevant line for context
                    for line in body_text.split("\n"):
                        if phrase.lower() in line.lower():
                            return f"Content policy rejection: {line.strip()[:200]}"
                    return f"Content policy rejection (matched: '{phrase}')"
        except Exception:
            pass
        return None

    def _is_page_alive(self) -> bool:
        """Check if the page/browser is still open."""
        try:
            return not self.page.is_closed()
        except Exception:
            return False

    async def generate(
        self, prompt: str, reference_image: str | None = None
    ) -> FlowGenerationResult:
        """Generate images for a single prompt in the current project.

        Args:
            prompt: Text prompt for image generation.
            reference_image: Optional path to a local image file to use as
                style/content reference.
        """
        try:
            # Ensure we have a project and are in Images mode
            init_error = await self._ensure_project()
            if init_error:
                return FlowGenerationResult(
                    prompt=prompt, success=False, error=init_error
                )

            # Upload reference image if provided
            if reference_image:
                ref_error = await self._upload_reference_image(reference_image)
                if ref_error:
                    return FlowGenerationResult(
                        prompt=prompt, success=False, error=ref_error
                    )

            # Collect existing image URLs to distinguish new ones
            # Wait a moment to ensure all previous images have their final URLs
            await asyncio.sleep(1)
            existing_urls = set()
            existing_imgs = await self.page.locator(
                self.config.selectors["generated_image"]
            ).all()
            for img in existing_imgs:
                try:
                    src = await img.get_attribute("src") or ""
                    if src:
                        existing_urls.add(
                            src.split("?")[0]
                        )  # strip query params for comparison
                except Exception:
                    pass

            # Enter prompt
            textarea = self.page.locator(self.config.selectors["textarea"]).first
            try:
                await textarea.wait_for(state="visible", timeout=10_000)
            except Exception:
                return FlowGenerationResult(
                    prompt=prompt,
                    success=False,
                    error="Prompt textarea not found",
                )

            await textarea.click()
            # Clear existing text first
            await textarea.fill("")
            await asyncio.sleep(0.3)
            await textarea.fill(prompt)
            await asyncio.sleep(0.5)

            # Click Create
            create_btn = self.page.locator(self.config.selectors["create_button"]).first
            try:
                await create_btn.wait_for(state="visible", timeout=5_000)
                await create_btn.click()
            except Exception:
                return FlowGenerationResult(
                    prompt=prompt,
                    success=False,
                    error="Create button not found or not clickable",
                )

            # Wait for NEW images to appear
            timeout_s = self.config.generation_timeout / 1000
            poll_interval = 5.0
            elapsed = 0.0
            new_image_urls: list[str] = []

            while elapsed < timeout_s:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                if not self._is_page_alive():
                    return FlowGenerationResult(
                        prompt=prompt,
                        success=False,
                        error="Browser page was closed during generation",
                    )

                # Collect all GCS image URLs
                imgs = await self.page.locator(
                    self.config.selectors["generated_image"]
                ).all()
                for img in imgs:
                    try:
                        if not await img.is_visible():
                            continue
                        src = await img.get_attribute("src") or ""
                        if not src:
                            continue
                        base_url = src.split("?")[0]
                        if base_url not in existing_urls and src not in new_image_urls:
                            # Verify it's a real image (not a placeholder)
                            dims = await img.evaluate(
                                "el => ({w: el.naturalWidth, h: el.naturalHeight})"
                            )
                            if dims.get("w", 0) >= 256 and dims.get("h", 0) >= 256:
                                new_image_urls.append(src)
                    except Exception:
                        continue

                if new_image_urls:
                    # Wait for all expected images (config.images_per_prompt)
                    if len(new_image_urls) < self.config.images_per_prompt:
                        # Not all images ready yet, keep polling
                        continue
                    # All expected images found — final sweep for any late-arriving images
                    await asyncio.sleep(3)
                    # Re-check for any additional images
                    imgs = await self.page.locator(
                        self.config.selectors["generated_image"]
                    ).all()
                    for img in imgs:
                        try:
                            if not await img.is_visible():
                                continue
                            src = await img.get_attribute("src") or ""
                            if not src:
                                continue
                            base_url = src.split("?")[0]
                            if (
                                base_url not in existing_urls
                                and src not in new_image_urls
                            ):
                                dims = await img.evaluate(
                                    "el => ({w: el.naturalWidth, h: el.naturalHeight})"
                                )
                                if dims.get("w", 0) >= 256 and dims.get("h", 0) >= 256:
                                    new_image_urls.append(src)
                        except Exception:
                            continue
                    break

            if not new_image_urls:
                # Check for content policy / copyright rejection messages
                rejection_error = await self._detect_content_rejection()
                if rejection_error:
                    return FlowGenerationResult(
                        prompt=prompt,
                        success=False,
                        error=rejection_error,
                    )
                return FlowGenerationResult(
                    prompt=prompt,
                    success=False,
                    error=f"Image generation timed out after {timeout_s:.0f}s",
                )

            return FlowGenerationResult(
                prompt=prompt,
                image_urls=new_image_urls,
                success=True,
            )

        except Exception as e:
            return FlowGenerationResult(
                prompt=prompt,
                success=False,
                error=str(e),
            )

    async def generate_batch(
        self, prompts: list[str], reference_image: str | None = None
    ) -> list[FlowGenerationResult]:
        """Generate images for multiple prompts sequentially with delays.

        Args:
            prompts: List of text prompts.
            reference_image: Optional path to reference image.  The file is
                uploaded for the first prompt; subsequent prompts re-select
                the same reference from the ingredient picker (faster).
        """
        results = []
        total = len(prompts)
        ref_uploaded = False

        for i, prompt in enumerate(prompts, 1):
            print(
                f"[{i}/{total}] Generating: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            )

            if not self._is_page_alive():
                print("  ✗ Browser closed — skipping remaining prompts")
                for remaining in prompts[i - 1 :]:
                    results.append(
                        FlowGenerationResult(
                            prompt=remaining,
                            success=False,
                            error="Browser was closed before this prompt",
                        )
                    )
                break

            # Reference handling:
            #  - First prompt: full file upload (crop + attach)
            #  - Subsequent prompts: re-pick from ingredient picker (instant)
            if reference_image and ref_uploaded:
                reattach_err = await self._reattach_reference_from_picker()
                if reattach_err:
                    print(f"  Warning: {reattach_err}")

            ref_for_this = reference_image if not ref_uploaded else None
            result = await self.generate(prompt, reference_image=ref_for_this)
            if reference_image and not ref_uploaded and result.success:
                ref_uploaded = True
                # URL is now captured during upload via before/after diff
                # No fallback capture needed here

            if result.success:
                print(f"  ✓ Got {len(result.image_urls)} image(s)")
            else:
                print(f"  ✗ Failed: {result.error}")

            results.append(result)

            # Delay between prompts (skip after last)
            if i < total:
                delay = random.uniform(self.config.min_delay, self.config.max_delay)
                print(f"  Waiting {delay:.1f}s before next prompt...")
                await asyncio.sleep(delay)

        return results


class FlowImageDownloader:
    """Downloads Flow-generated images using the browser's authenticated session."""

    def __init__(self, page: Page, config: FlowConfig) -> None:
        self.page = page
        self.config = config

    async def download(self, url: str, prompt: str, index: int) -> Path | None:
        """Download a single image and save to prompt-named subfolder.

        Structure: output_dir/{sanitized_prompt}/flow_{index}_{timestamp}.png
        """
        try:
            sanitized = _sanitize_filename(prompt)
            prompt_dir = self.config.output_dir / sanitized
            prompt_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"flow_{index}_{timestamp}.png"
            filepath = prompt_dir / filename

            response = await self.page.request.get(url)
            if not response.ok:
                print(
                    f"  Warning: Download failed (HTTP {response.status}) for {url[:80]}"
                )
                return None

            body = await response.body()
            if not body:
                print(f"  Warning: Empty response for {url[:80]}")
                return None

            filepath.write_bytes(body)
            return filepath

        except Exception as e:
            print(f"  Warning: Download error: {e}")
            return None

    async def download_all(self, result: FlowGenerationResult) -> list[Path]:
        """Download all images from a generation result. Returns list of saved paths."""
        saved: list[Path] = []
        for i, url in enumerate(result.image_urls):
            path = await self.download(url, result.prompt, i)
            if path:
                saved.append(path)
        return saved


def _sanitize_filename(text: str, max_length: int = 50) -> str:
    """Sanitize text for use as a filename."""
    sanitized = re.sub(r"[^\w\-]", "_", text, flags=re.UNICODE)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")
    return sanitized or "image"
