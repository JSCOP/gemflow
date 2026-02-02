"""Parallel multi-account image generation.

Distributes prompts across multiple Google accounts using a shared
asyncio.Queue. Each account runs its own Chrome browser and processes
prompts from the queue until it's empty.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import async_playwright, Playwright

from gemini_automation.accounts import AccountManager
from gemini_automation.config import Config
from gemini_automation.downloader import ImageDownloader
from gemini_automation.generator import ImageGenerator, GenerationResult


@dataclass
class ParallelResult:
    """Result of a single prompt including which account processed it."""

    prompt: str
    account: str
    image_urls: list[str] = field(default_factory=list)
    saved_files: list[str] = field(default_factory=list)
    success: bool = False
    error: str | None = None


async def _account_worker(
    pw: Playwright,
    account_name: str,
    config: Config,
    queue: asyncio.Queue[tuple[int, str]],
    results: dict[int, ParallelResult],
    min_delay: float,
    max_delay: float,
) -> None:
    """Worker coroutine: one Chrome browser per account, pulls prompts from queue."""
    context = None
    try:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(config.profile_dir.resolve()),
            channel="chrome",
            headless=False,
            args=config.browser_args,
            viewport={"width": 1920, "height": 1080},
            no_viewport=False,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        generator = ImageGenerator(page, config)
        downloader = ImageDownloader(page, config)

        first_prompt = True
        while True:
            try:
                idx, prompt = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            # Stagger: small delay before first prompt per account (avoid launch spike)
            if first_prompt:
                await asyncio.sleep(random.uniform(0.5, 2.0))
                first_prompt = False
            else:
                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)

            print(
                f"  [{account_name}] Generating: {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
            )

            gen_result = await generator.generate(prompt)

            pr = ParallelResult(
                prompt=prompt,
                account=account_name,
                success=gen_result.success,
                image_urls=gen_result.image_urls,
                error=gen_result.error,
            )

            if gen_result.success:
                dl_result = await downloader.download_all(gen_result)
                pr.saved_files = [str(p) for p in dl_result.saved_files]
                print(f"  [{account_name}] ✓ {len(pr.saved_files)} image(s)")
            else:
                print(f"  [{account_name}] ✗ {gen_result.error}")

            results[idx] = pr
            queue.task_done()

    except Exception as e:
        # Account-level failure: drain remaining items back to queue? No — just log.
        print(f"  [{account_name}] Worker crashed: {e}")
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass


async def run_parallel(
    prompts: list[str],
    account_names: list[str],
    base_dir: Path,
    output_dir: Path | None = None,
    max_concurrent: int | None = None,
) -> dict:
    """Run image generation across multiple accounts in parallel.

    Args:
        prompts: List of text prompts.
        account_names: Account names to use. Use ["all"] to use all accounts.
        base_dir: Project root directory.
        output_dir: Override output directory.
        max_concurrent: Max simultaneous browsers (default: len(accounts)).

    Returns:
        JSON-serializable result dict.
    """
    mgr = AccountManager(base_dir=base_dir)

    # Resolve account names
    if len(account_names) == 1 and account_names[0].lower() == "all":
        all_accounts = mgr.list_accounts()
        if not all_accounts:
            return {
                "error": "No accounts registered.",
                "results": [],
                "total_prompts": len(prompts),
                "successful": 0,
                "failed": len(prompts),
            }
        account_names = [a.name for a in all_accounts]

    # Validate accounts exist
    for name in account_names:
        if not mgr.get(name):
            available = [a.name for a in mgr.list_accounts()]
            return {
                "error": f"Account '{name}' not found. Available: {available}",
                "results": [],
                "total_prompts": len(prompts),
                "successful": 0,
                "failed": len(prompts),
            }

    # Limit concurrency
    effective_concurrent = min(
        max_concurrent or len(account_names),
        len(account_names),
        len(prompts),  # No point running more workers than prompts
    )
    active_accounts = account_names[:effective_concurrent]

    print(
        f"Parallel generation: {len(prompts)} prompts across {len(active_accounts)} account(s)"
    )
    print(f"  Accounts: {', '.join(active_accounts)}")

    # Build configs
    configs: dict[str, Config] = {}
    for name in active_accounts:
        cfg = Config.for_account(name, base_dir=base_dir)
        if output_dir:
            cfg.output_dir = output_dir
        cfg.ensure_dirs()
        configs[name] = cfg
        mgr.update_last_used(name)

    # Fill queue with (index, prompt) tuples
    queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
    for i, prompt in enumerate(prompts):
        queue.put_nowait((i, prompt))

    # Results indexed by prompt order
    results: dict[int, ParallelResult] = {}

    # Run workers
    async with async_playwright() as pw:
        tasks = [
            asyncio.create_task(
                _account_worker(
                    pw=pw,
                    account_name=name,
                    config=configs[name],
                    queue=queue,
                    results=results,
                    min_delay=configs[name].min_delay,
                    max_delay=configs[name].max_delay,
                )
            )
            for name in active_accounts
        ]

        # Wait for all workers to finish
        await asyncio.gather(*tasks, return_exceptions=True)

    # Build ordered result list
    all_results = []
    for i, prompt in enumerate(prompts):
        if i in results:
            pr = results[i]
            all_results.append(
                {
                    "prompt": pr.prompt,
                    "account": pr.account,
                    "success": pr.success,
                    "images": pr.saved_files,
                    "error": pr.error,
                }
            )
        else:
            all_results.append(
                {
                    "prompt": prompt,
                    "account": None,
                    "success": False,
                    "images": [],
                    "error": "Prompt was not processed (all workers failed)",
                }
            )

    successful = sum(1 for r in all_results if r["success"])
    return {
        "results": all_results,
        "total_prompts": len(prompts),
        "successful": successful,
        "failed": len(all_results) - successful,
        "accounts_used": active_accounts,
    }
