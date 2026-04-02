# Website Screenshotter — `src/pipeline/website_screenshotter.py`

## Description

Playwright-based website crawling and viewport screenshot capture.

## Data Classes

| Class | Description |
|-------|-------------|
| `WebsiteCapture` | Single capture: `index`, `label` (e.g. "homepage_scroll_0"), `path`, `source_url`, `capture_type` ("scroll" or "nav_click"). |

## Functions

| Function | Description |
|----------|-------------|
| `crawl_and_capture()` | Async. Crawls a website: load homepage, scroll-capture every viewport-height (max 10 per page), find same-domain nav links, visit and scroll-capture each. Supports saved auth state. Auto-installs Chromium if needed. |
| `crawl_and_capture_sync()` | Synchronous wrapper via `asyncio.run()`. |
| `login_and_save_auth()` | Async. Signs into Google using a persistent Chrome profile. Supports auto sign-in via env vars or manual browser login (120s timeout). Saves auth state to `~/.cache/video_generator/auth_state.json`. |
| `login_and_save_auth_sync()` | Synchronous wrapper. |

## Internal Functions
- `_scroll_and_capture()` — Scroll through page, capture per viewport
- `_find_nav_links()` — Find same-domain nav links from nav/header/menu elements
- `_dismiss_overlays()` — Close cookie banners and modals
- `_google_signin_direct()` — Automated Google sign-in with human-like typing
- `_slugify()` — Text to filesystem-safe slug

## Constants
- `ASPECT_RATIO_VIEWPORTS` — Maps ratio strings to (width, height)
- `AUTH_STATE_FILE` — `~/.cache/video_generator/auth_state.json`
- `BROWSER_PROFILE_DIR` — `~/.cache/video_generator/chrome_profile`

## Dependencies
- `playwright` (async API, Chromium)

## Usage
```python
from src.pipeline.website_screenshotter import crawl_and_capture_sync, login_and_save_auth_sync

# Basic crawl
captures = crawl_and_capture_sync("https://example.com", Path("screenshots/"))

# With auth
auth = login_and_save_auth_sync("https://app.example.com")
captures = crawl_and_capture_sync("https://app.example.com", Path("screenshots/"), auth_state=auth)
```
