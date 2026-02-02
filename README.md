<div align="center">

# gemflow

### Automated Batch Image Generation for Google Gemini & Flow

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=for-the-badge)]()

**Real browser automation. Not an API wrapper.**

Generate hundreds of images across Google's Gemini and Flow (ImageFX) platforms using actual Chrome browsers with your logged-in Google accounts.

[Features](#-features) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [Usage](#-usage) · [Reference Images](#-reference-images)

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
