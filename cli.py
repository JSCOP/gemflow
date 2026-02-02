"""CLI entry point for Gemini image generation automation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from gemini_automation.config import Config
from gemini_automation.browser import BrowserManager
from gemini_automation.generator import ImageGenerator
from gemini_automation.downloader import ImageDownloader


async def cmd_login(config: Config) -> int:
    """Open browser for manual Google login."""
    async with BrowserManager(config) as bm:
        success = await bm.wait_for_login(timeout_seconds=300)
        if success:
            print(f"Login successful! Session saved to {config.profile_dir}")
            return 0
        else:
            print("Login timed out after 5 minutes.")
            return 1


async def cmd_status(config: Config) -> int:
    """Check login state and show project info."""
    profile_exists = config.profile_dir.exists() and any(config.profile_dir.iterdir())
    print(f"Profile dir: {config.profile_dir}")
    print(f"Output dir:  {config.output_dir}")

    if not profile_exists:
        print("Profile: empty (run 'python cli.py login' first)")
        print("Logged in: NO")
        return 0

    print("Profile: exists")

    async with BrowserManager(config) as bm:
        page = await bm.get_page()
        logged_in = await bm.is_logged_in(page)
        print(f"Logged in: {'YES' if logged_in else 'NO'}")

    # Count images in output
    image_count = len(list(config.output_dir.glob("*.png"))) + len(
        list(config.output_dir.glob("*.jpg"))
    )
    print(f"Images in output: {image_count}")
    return 0


async def cmd_generate(
    config: Config, prompts: list[str], output_dir: Path | None
) -> int:
    """Generate images for given prompts."""
    if output_dir:
        config.output_dir = output_dir
    config.ensure_dirs()

    async with BrowserManager(config) as bm:
        page = await bm.get_page()

        # Check login
        if not await bm.is_logged_in(page):
            print("Error: Not logged in. Run 'python cli.py login' first.")
            return 1

        generator = ImageGenerator(page, config)
        downloader = ImageDownloader(page, config)

        # Generate images
        gen_results = await generator.generate_batch(prompts)

        # Download images
        all_results = []
        for gen_result in gen_results:
            entry = {
                "prompt": gen_result.prompt,
                "success": gen_result.success,
                "images": [],
                "error": gen_result.error,
            }
            if gen_result.success:
                dl_result = await downloader.download_all(gen_result)
                entry["images"] = [str(p) for p in dl_result.saved_files]
                if dl_result.failed_urls:
                    entry["download_failures"] = len(dl_result.failed_urls)
            all_results.append(entry)

    # Summary
    successful = sum(1 for r in all_results if r["success"])
    failed = len(all_results) - successful

    output = {
        "results": all_results,
        "total_prompts": len(prompts),
        "successful": successful,
        "failed": failed,
    }

    print(json.dumps(output, indent=2, default=str, ensure_ascii=False))
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gemini web image generation automation"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # login
    subparsers.add_parser("login", help="Open browser for manual Google login")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate images from prompts")
    gen_parser.add_argument(
        "--prompts", nargs="+", required=True, help="List of text prompts"
    )
    gen_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: ./output)",
    )

    # status
    subparsers.add_parser("status", help="Check login state and project info")

    # tui
    subparsers.add_parser("tui", help="Launch interactive TUI")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    config = Config.from_defaults()
    config.ensure_dirs()

    if args.command == "tui":
        return cmd_tui()
    elif args.command == "login":
        return asyncio.run(cmd_login(config))
    elif args.command == "generate":
        return asyncio.run(cmd_generate(config, args.prompts, args.output_dir))
    elif args.command == "status":
        return asyncio.run(cmd_status(config))
    else:
        parser.print_help()
        return 1


def cmd_tui() -> int:
    """Launch the interactive TUI."""
    from tui.app import GeminiApp

    app = GeminiApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
