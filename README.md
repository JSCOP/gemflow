<div align="center">

# gemflow

### Automated Batch Image Generation for Google Gemini & Flow

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=for-the-badge)]()

**Real browser automation. Not an API wrapper.**

Generate hundreds of images across Google's Gemini and Flow (ImageFX) platforms using actual Chrome browsers with your logged-in Google accounts.

[Features](#-features) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [Usage](#-usage) · [AI Integration](#ai-coding-assistant-integration)

</div>

---

## Why gemflow?

Google's image generation tools (Gemini, Flow/ImageFX) don't have public APIs. **gemflow** bridges that gap by automating real Chrome browsers through Playwright — the same way a human would use them, but at scale.

- **No API keys needed** — uses your existing Google account sessions
- **No rate limit guessing** — built-in smart delays and anti-detection
- **Full feature access** — reference images, project management, tier selection
- **Batch processing** — feed it 100 prompts, walk away, come back to images

---

## Features

### Gemini Image Generation

| Feature | Details |
|---------|---------|
| Single account | Sequential prompt processing with smart delays |
| Multi-account parallel | Multiple Chrome instances across accounts simultaneously |
| Auto-detection | Handles promo dialogs, cookie consents, login checks |
| Image extraction | Detects generated images and downloads automatically |
| Output | 1 high-quality image per prompt |

### Flow (ImageFX) Image Generation

| Feature | Details |
|---------|---------|
| Tier system | Separate accounts for different quality tiers (ultra/pro) |
| Project management | Create, find, and reuse named projects |
| Batch generation | 4 images per prompt, sequential with delays |
| Reference images | Upload style reference, auto-reattach across batch via ingredient picker |
| Content detection | Copyright / policy rejection detection with clear error messages |
| Multi-language | English and Korean Google UI selectors |

### Side-by-Side Comparison

```
                    Gemini                    Flow (ImageFX)
                    ──────                    ──────────────
Images/prompt       1                         4 (configurable)
Projects            N/A (new chat each)       Named, reusable
Reference images    N/A                       Full support
Tier system         N/A                       Ultra / Pro
Output structure    Flat files                Per-prompt folders
Generation time     ~30s / prompt             ~20s / prompt
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Login to Google

```bash
python cli.py login
```

A Chrome browser opens. Log into your Google account manually. The session is saved to a local Chrome profile for future use.

### 3. Generate images

```bash
# Gemini - single prompt
python cli.py generate --prompts "a serene Japanese zen garden, watercolor style"

# Gemini - batch
python cli.py generate --prompts "prompt one" "prompt two" "prompt three"
```

### 4. Configure accounts (optional)

Create `accounts.json` in the project root:

```json
{
  "accounts": [
    {
      "name": "my-account",
      "tier": "ultra",
      "profile_dir": "./gemini_profiles/my-account"
    }
  ]
}
```

---

## Architecture

```
gemflow/
├── gemini_automation/          Core automation library
│   ├── config.py               Gemini configuration & selectors
│   ├── browser.py              BrowserManager — Playwright Chrome lifecycle
│   ├── generator.py            ImageGenerator — prompt → image URLs
│   ├── downloader.py           ImageDownloader — URLs → PNG files
│   ├── accounts.py             AccountManager — multi-account profiles
│   ├── parallel.py             Parallel multi-account orchestration
│   ├── flow_config.py          Flow configuration & dynamic tier loading
│   └── flow_generator.py       FlowImageGenerator + FlowImageDownloader
│
├── cli.py                      CLI entry point (login, generate, status)
├── requirements.txt            Python dependencies
├── accounts.json               Account config (gitignored)
└── gemini_profiles/            Chrome profiles with sessions (gitignored)
```

### How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Prompts    │────▶│ BrowserManager│────▶│   Chrome     │
│  (text list) │     │  (Playwright) │     │  (headful)   │
└─────────────┘     └──────┬───────┘     └──────┬──────┘
                           │                     │
                    ┌──────▼───────┐     ┌──────▼──────┐
                    │  Generator   │────▶│  Google UI   │
                    │ (enter prompt│     │ (Gemini or   │
                    │  click create│     │  Flow/ImageFX)│
                    │  poll images)│     │              │
                    └──────┬───────┘     └──────┬──────┘
                           │                     │
                    ┌──────▼───────┐     ┌──────▼──────┐
                    │  Downloader  │◀────│  GCS URLs    │
                    │ (fetch PNGs, │     │ (detected via│
                    │  save to disk│     │  DOM polling)│
                    └──────────────┘     └─────────────┘
```

### Generation Flow (Flow/ImageFX)

```
1. Launch Chrome with saved profile
2. Navigate to labs.google/fx/tools/flow
3. Find or create named project
4. Switch to Images mode, configure settings
5. [If reference] Upload image → Crop & Save → wait for thumbnail
6. Enter prompt text → Click Create
7. Poll DOM for new <img> elements with GCS URLs
8. Wait for naturalWidth >= 256 (fully loaded)
9. Download all images to per-prompt subfolder
10. [Next prompt] Re-attach reference from ingredient picker
11. Repeat 6-10 for remaining prompts
```

---

## Usage

### CLI

```bash
# Login (opens browser for manual Google login)
python cli.py login

# Check status
python cli.py status

# Generate with Gemini
python cli.py generate --prompts "a cat on the moon" "a dog in space"
```

### Flow Worker (Advanced)

```bash
# Single tier
python flow_worker.py --tier ultra --prompts "a landscape" "a portrait"

# With named project (reuses if exists)
python flow_worker.py --tier ultra --project-name "MyProject" --prompts "prompt 1"

# With reference image
python flow_worker.py --tier ultra \
  --reference-image "/path/to/reference.png" \
  --prompts "style transfer prompt 1" "style transfer prompt 2"

# Both tiers in parallel
python flow_worker.py --tier all --prompts "a sunset over mountains"
```

### Gemini Worker (Advanced)

```bash
# Single account
python gemini_worker.py --account my-account --prompts "a watercolor painting"

# Parallel across multiple accounts
python gemini_worker.py --accounts account1,account2 --prompts "p1" "p2" "p3" "p4"
```

---

## Reference Images

gemflow supports **reference/style images** for Flow generation. Upload an image once and it's automatically reused across all prompts in a batch.

### How it works

1. **First prompt**: Full upload flow — file picker → crop modal → save
2. **Subsequent prompts**: Opens ingredient picker → clicks most recent reference tile → instant reattach

This means batch generation with references is fast — only the first prompt has the ~10s upload overhead.

### Output Structure

```
output/
├── flow_ultra/                          Flow ultra-tier outputs
│   ├── A_serene_zen_garden/
│   │   ├── flow_0_20260203_032847.png
│   │   ├── flow_1_20260203_032848.png
│   │   ├── flow_2_20260203_032849.png
│   │   └── flow_3_20260203_032849.png
│   └── A_cute_cat_on_rainbow/
│       ├── flow_0_20260203_041217.png
│       └── ...
├── flow_pro/                            Flow pro-tier outputs
│   └── ...
└── gemini_{prompt}_{timestamp}.png      Gemini outputs (flat)
```

---

## Configuration

### accounts.json

```json
{
  "accounts": [
    {
      "name": "account-one",
      "tier": "ultra",
      "profile_dir": "./gemini_profiles/account-one",
      "created_at": "2026-01-01T00:00:00+00:00"
    },
    {
      "name": "account-two",
      "tier": "pro",
      "profile_dir": "./gemini_profiles/account-two",
      "created_at": "2026-01-01T00:00:00+00:00"
    }
  ]
}
```

### Tier System

| Tier | Use Case | Output Directory |
|------|----------|------------------|
| `ultra` | Highest quality generation | `output/flow_ultra/` |
| `pro` | Standard generation | `output/flow_pro/` |
| `all` | Both tiers in parallel | Both directories |

Tiers are mapped to accounts via the `"tier"` field in `accounts.json`.

---

## Anti-Detection

gemflow uses several strategies to avoid bot detection:

- **Headful Chrome** — real browser window, not headless
- **Persistent profiles** — reuses cookies/sessions like a real user
- **Random delays** — 3-10 second waits between actions
- **No automation flags** — disables `AutomationControlled` blink feature
- **Natural interaction** — types text, clicks buttons, waits for UI responses

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Browser automation | [Playwright](https://playwright.dev) for Python |
| Language | Python 3.11+ (async/await throughout) |
| Chrome management | Persistent Chromium contexts with saved profiles |
| Image detection | DOM polling with `naturalWidth` verification |
| TUI (optional) | [Textual](https://textual.textualize.io/) |
| Download | Direct GCS URL fetching via Playwright request context |

---

## Limitations

- **No public API** — relies on web UI automation, which can break if Google updates their interface
- **Requires Google account** — must be logged in with a real account
- **Generation speed** — limited by Google's actual generation time (~20-30s per prompt)
- **Content policy** — Google's content filters still apply; copyrighted characters will be refused

---

## AI Coding Assistant Integration

gemflow can be integrated with AI coding assistants like **OpenCode**, **Claude Code**, **Cline**, and similar tools that support custom tools/skills.

### Overview

The integration consists of three parts:

| Component | Purpose | Location |
|-----------|---------|----------|
| **Worker Scripts** | CLI wrappers that call the automation | `workers/` or project root |
| **Tool Definitions** | Schema + execution logic for AI tools | `~/.config/opencode/tools/` |
| **Skill Files** | Usage instructions for the AI | `~/.config/opencode/skills/` |

### 1. Worker Scripts

Create thin CLI wrappers that the AI tools can execute:

**`flow_worker.py`** — Flow image generation wrapper:

```python
#!/usr/bin/env python3
"""Flow image generation worker for AI tool integration."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_automation.flow_generator import FlowImageGenerator, FlowImageDownloader
from gemini_automation.flow_config import FlowConfig, TIER_ACCOUNTS


async def main():
    parser = argparse.ArgumentParser(description="Flow image generation worker")
    parser.add_argument("--tier", required=True, choices=["ultra", "pro", "all"])
    parser.add_argument("--prompts", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--project-name", type=str, default=None)
    parser.add_argument("--reference-image", type=str, default=None)
    args = parser.parse_args()

    tiers = ["ultra", "pro"] if args.tier == "all" else [args.tier]
    all_results = {}

    for tier in tiers:
        account = TIER_ACCOUNTS.get(tier)
        if not account:
            print(json.dumps({"error": f"No account configured for tier: {tier}"}))
            return 1

        config = FlowConfig.for_account(account)
        if args.output_dir:
            config.output_dir = args.output_dir / f"flow_{tier}"

        async with FlowImageGenerator(config) as generator:
            results = await generator.generate_batch(
                prompts=args.prompts,
                project_name=args.project_name,
                reference_image_path=args.reference_image,
            )
            downloader = FlowImageDownloader(generator.page, config)
            
            tier_results = []
            for result in results:
                entry = {"prompt": result.prompt, "success": result.success, "images": []}
                if result.success:
                    dl = await downloader.download_all(result)
                    entry["images"] = [str(p) for p in dl.saved_files]
                else:
                    entry["error"] = result.error
                tier_results.append(entry)
            all_results[tier] = tier_results

    print(json.dumps(all_results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

**`gemini_worker.py`** — Gemini image generation wrapper:

```python
#!/usr/bin/env python3
"""Gemini image generation worker for AI tool integration."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_automation.accounts import AccountManager
from gemini_automation.parallel import ParallelGenerator


async def main():
    parser = argparse.ArgumentParser(description="Gemini image generation worker")
    parser.add_argument("--prompts", nargs="+", required=True)
    parser.add_argument("--account", type=str, default=None)
    parser.add_argument("--accounts", type=str, default=None)  # comma-separated
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-concurrent", type=int, default=None)
    args = parser.parse_args()

    manager = AccountManager()
    
    if args.accounts:
        account_names = [a.strip() for a in args.accounts.split(",")]
    elif args.account:
        account_names = [args.account]
    else:
        account_names = [manager.list_accounts()[0]["name"]]

    generator = ParallelGenerator(
        account_names=account_names,
        output_dir=args.output_dir,
        max_concurrent=args.max_concurrent or len(account_names),
    )
    
    results = await generator.generate_batch(args.prompts)
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

### 2. Tool Definitions (OpenCode)

Create tool definitions that the AI can invoke. These go in `~/.config/opencode/tools/`:

**`flow-generate.ts`**:

```typescript
import { tool } from "@opencode-ai/plugin"

// Update this to your gemflow installation path
const GEMFLOW_ROOT = "/path/to/gemflow"
const WORKER_SCRIPT = `${GEMFLOW_ROOT}/flow_worker.py`

export default tool({
  description: "Generate images using Google Flow. Choose tier: ultra, pro, or all.",
  args: {
    prompts: tool.schema.array(tool.schema.string()).describe("Image prompts"),
    tier: tool.schema.enum(["ultra", "pro", "all"]).describe("Account tier"),
    outputDir: tool.schema.string().optional().describe("Output directory"),
    projectName: tool.schema.string().optional().describe("Flow project name"),
    referenceImage: tool.schema.string().optional().describe("Reference image path"),
  },
  async execute(args) {
    const cmdArgs = [WORKER_SCRIPT, "--tier", args.tier, "--prompts", ...args.prompts]
    if (args.outputDir) cmdArgs.push("--output-dir", args.outputDir)
    if (args.projectName) cmdArgs.push("--project-name", args.projectName)
    if (args.referenceImage) cmdArgs.push("--reference-image", args.referenceImage)

    const proc = Bun.spawn(["python", ...cmdArgs], { cwd: GEMFLOW_ROOT, stdout: "pipe", stderr: "pipe" })
    const stdout = await new Response(proc.stdout).text()
    const stderr = await new Response(proc.stderr).text()
    const exitCode = await proc.exited

    return exitCode === 0 ? stdout.trim() : `Error (exit ${exitCode}):\n${stderr || stdout}`
  },
})
```

**`gemini-generate.ts`**:

```typescript
import { tool } from "@opencode-ai/plugin"

const GEMFLOW_ROOT = "/path/to/gemflow"
const WORKER_SCRIPT = `${GEMFLOW_ROOT}/gemini_worker.py`

export default tool({
  description: "Generate images using Google Gemini web automation.",
  args: {
    prompts: tool.schema.array(tool.schema.string()).describe("Image prompts"),
    account: tool.schema.string().optional().describe("Account name"),
    accounts: tool.schema.array(tool.schema.string()).optional().describe("Accounts for parallel mode"),
    outputDir: tool.schema.string().optional().describe("Output directory"),
    maxConcurrent: tool.schema.number().optional().describe("Max parallel browsers"),
  },
  async execute(args) {
    const cmdArgs = [WORKER_SCRIPT, "--prompts", ...args.prompts]
    if (args.outputDir) cmdArgs.push("--output-dir", args.outputDir)
    if (args.accounts?.length) cmdArgs.push("--accounts", args.accounts.join(","))
    else if (args.account) cmdArgs.push("--account", args.account)
    if (args.maxConcurrent) cmdArgs.push("--max-concurrent", String(args.maxConcurrent))

    const proc = Bun.spawn(["python", ...cmdArgs], { cwd: GEMFLOW_ROOT, stdout: "pipe", stderr: "pipe" })
    const stdout = await new Response(proc.stdout).text()
    const stderr = await new Response(proc.stderr).text()
    const exitCode = await proc.exited

    return exitCode === 0 ? stdout.trim() : `Error (exit ${exitCode}):\n${stderr || stdout}`
  },
})
```

### 3. Skill Files (OpenCode)

Skills teach the AI **when and how** to use the tools. Create these in `~/.config/opencode/skills/`:

**`flow-image/SKILL.md`**:

```markdown
---
name: flow-image
description: Generate images using Google Flow. Use when user wants 4 images per prompt or tier-separated output.
---

## `flow-generate` tool

**Basic usage:**
\`\`\`json
{ "prompts": ["a serene landscape", "a futuristic city"], "tier": "ultra" }
\`\`\`

**With reference image:**
\`\`\`json
{
  "prompts": ["character in battle pose", "character menu screen"],
  "tier": "ultra",
  "referenceImage": "/path/to/style-reference.png"
}
\`\`\`

## Output
- 4 images per prompt
- Saved to: `output/flow_{tier}/{prompt_folder}/`

## When to use Flow vs Gemini
- Flow: 4 images/prompt, project organization, reference images, tier system
- Gemini: 1 image/prompt, simpler workflow
```

**`gemini-image/SKILL.md`**:

```markdown
---
name: gemini-image
description: Generate images using Google Gemini. Use when user wants single high-quality images.
---

## `gemini-generate` tool

**Single account:**
\`\`\`json
{ "prompts": ["a watercolor sunset", "abstract geometric art"] }
\`\`\`

**Parallel (multiple accounts):**
\`\`\`json
{
  "prompts": ["prompt1", "prompt2", "prompt3", "prompt4"],
  "accounts": ["account-one", "account-two"]
}
\`\`\`

## Output
- 1 image per prompt
- Saved to: `output/gemini_{prompt}_{timestamp}.png`
```

### 4. Directory Structure

After setup, your config should look like:

```
~/.config/opencode/
├── tools/
│   ├── flow-generate.ts
│   └── gemini-generate.ts
├── skills/
│   ├── flow-image/
│   │   └── SKILL.md
│   └── gemini-image/
│       └── SKILL.md
└── package.json          # Add @opencode-ai/plugin dependency
```

### 5. Installation

```bash
# In your opencode config directory
cd ~/.config/opencode
bun add @opencode-ai/plugin
```

### Usage with AI

Once configured, you can ask your AI assistant:

> "Generate 4 images of a cyberpunk cityscape using Flow"

The AI will:
1. Load the `flow-image` skill
2. Call the `flow-generate` tool with appropriate parameters
3. Return the generated image paths

### Other AI Assistants

For **Claude Code**, **Cline**, **Cursor**, or other MCP-compatible tools, adapt the tool definitions to their plugin format. The core pattern remains:

1. **Worker script** — Python CLI that wraps the automation
2. **Tool schema** — Defines parameters the AI can pass
3. **Skill/instruction** — Teaches the AI when/how to use it

---

## Disclaimer

> This tool automates interactions with Google's web interfaces. Usage may be subject to Google's Terms of Service. Use responsibly and at your own risk. This project is not affiliated with, endorsed by, or sponsored by Google.

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with Playwright and persistence.**

*Because sometimes the best API is no API at all.*

</div>
