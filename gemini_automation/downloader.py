"""Image download and save logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page

from gemini_automation.config import Config
from gemini_automation.generator import GenerationResult
from gemini_automation.metadata import embed_png_metadata


def sanitize_filename(text: str, max_length: int = 50) -> str:
    """Sanitize text for use as a filename."""
    # Replace non-alphanumeric (keeping unicode letters) with underscore
    sanitized = re.sub(r"[^\w\-]", "_", text, flags=re.UNICODE)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Strip leading/trailing underscores
    sanitized = sanitized.strip("_")
    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip("_")
    return sanitized or "image"


@dataclass
class DownloadResult:
    """Result of downloading images for a single prompt."""

    prompt: str
    saved_files: list[Path] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)


class ImageDownloader:
    """Downloads generated images using the browser's authenticated session."""

    def __init__(self, page: Page, config: Config) -> None:
        self.page = page
        self.config = config

    async def download(self, url: str, prompt: str, index: int) -> Path | None:
        """Download a single image and save to output directory."""
        try:
            sanitized = sanitize_filename(prompt)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{sanitized}_{index}_{timestamp}.png"
            filepath = self.config.output_dir / filename

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

            filepath.write_bytes(embed_png_metadata(body, prompt))
            return filepath

        except Exception as e:
            print(f"  Warning: Download error: {e}")
            return None

    async def download_all(self, result: GenerationResult) -> DownloadResult:
        """Download all images from a generation result."""
        download_result = DownloadResult(prompt=result.prompt)

        for i, url in enumerate(result.image_urls):
            path = await self.download(url, result.prompt, i)
            if path:
                download_result.saved_files.append(path)
            else:
                download_result.failed_urls.append(url)

        return download_result
