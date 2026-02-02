"""Gemini web image generation automation."""

__version__ = "0.1.0"

from gemini_automation.config import Config
from gemini_automation.browser import BrowserManager
from gemini_automation.generator import ImageGenerator, GenerationResult
from gemini_automation.downloader import ImageDownloader, DownloadResult
from gemini_automation.accounts import Account, AccountManager

__all__ = [
    "Config",
    "BrowserManager",
    "ImageGenerator",
    "GenerationResult",
    "ImageDownloader",
    "DownloadResult",
    "Account",
    "AccountManager",
]
