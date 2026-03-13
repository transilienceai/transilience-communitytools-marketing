"""
Website screenshot capture using Playwright.

Crawls a website by scrolling through the page and clicking navigation links,
capturing viewport screenshots of every distinct view. All captures are
saved at the configured aspect ratio (default 16:9).
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# Map aspect ratio strings to viewport dimensions (width, height)
ASPECT_RATIO_VIEWPORTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:3": (1440, 1080),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
}


def _viewport_for_aspect_ratio(aspect_ratio: str) -> Tuple[int, int]:
    """Return (width, height) for a given aspect ratio string."""
    if aspect_ratio in ASPECT_RATIO_VIEWPORTS:
        return ASPECT_RATIO_VIEWPORTS[aspect_ratio]
    try:
        w, h = aspect_ratio.split(":")
        ratio = int(w) / int(h)
        width = 1920
        height = int(width / ratio)
        return (width, height)
    except Exception:
        return (1920, 1080)


@dataclass
class WebsiteCapture:
    """A single captured screenshot."""
    index: int
    label: str          # e.g. "homepage_scroll_0", "nav_pricing"
    path: Path
    source_url: str     # URL when captured
    capture_type: str   # "scroll" | "nav_click"


async def _ensure_browser_installed():
    """Install Chromium if not already present."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        except Exception:
            logger.info("Installing Playwright Chromium browser...")
            import subprocess
            subprocess.run(
                ["python", "-m", "playwright", "install", "chromium"],
                check=True, capture_output=True,
            )


async def _dismiss_overlays(page):
    """Try to dismiss cookie banners and modals."""
    for selector in [
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "button:has-text('OK')",
        "[class*='cookie'] button",
        "[class*='banner'] button",
        "[class*='modal'] button[class*='close']",
    ]:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=300):
                await btn.click()
                await page.wait_for_timeout(300)
        except Exception:
            pass


AUTH_STATE_FILE = Path.home() / ".cache" / "video_generator" / "auth_state.json"


BROWSER_PROFILE_DIR = Path.home() / ".cache" / "video_generator" / "chrome_profile"


async def _google_signin_direct(page, email: str, password: str) -> bool:
    """
    Sign into Google at accounts.google.com using a real-looking browser.
    """
    logger.info("Navigating to accounts.google.com...")
    await page.goto(
        "https://accounts.google.com/",
        wait_until="networkidle",
        timeout=30000,
    )
    await page.wait_for_timeout(2000)

    # ── Enter email ──
    try:
        email_input = page.locator('input[type="email"]')
        await email_input.wait_for(state="visible", timeout=10000)
        # Type slowly like a human instead of fill()
        await email_input.click()
        await page.keyboard.type(email, delay=50)
        logger.info("Entered email: %s", email)

        next_btn = page.locator('#identifierNext')
        await next_btn.click()
        await page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning("Email entry failed: %s", e)
        return False

    # ── Enter password ──
    try:
        password_input = page.locator('input[type="password"]')
        await password_input.wait_for(state="visible", timeout=10000)
        await password_input.click()
        await page.keyboard.type(password, delay=50)
        logger.info("Entered password")

        next_btn = page.locator('#passwordNext')
        await next_btn.click()
        await page.wait_for_timeout(5000)
    except Exception as e:
        logger.warning("Password entry failed: %s", e)
        return False

    # ── Handle 2FA / challenges — wait up to 60s for user ──
    for _ in range(60):
        await page.wait_for_timeout(1000)
        current = page.url.lower()
        if "myaccount.google" in current or not any(
            k in current for k in ["accounts.google", "signin", "challenge", "oauth"]
        ):
            logger.info("Google sign-in successful")
            return True

    logger.warning("Google sign-in may need manual 2FA — check the browser window")
    return True


async def login_and_save_auth(url: str, email: str = "", password: str = "") -> Path:
    """
    Sign in to Google using a persistent browser profile and save auth state.

    Uses a real Chrome profile directory so Google doesn't detect automation.
    Strategy: Sign into accounts.google.com first, then navigate to target URL.

    Returns:
        Path to the saved auth state file.
    """
    from playwright.async_api import async_playwright
    import os

    await _ensure_browser_installed()

    email = email or os.getenv("GOOGLE_EMAIL", "")
    password = password or os.getenv("GOOGLE_PASSWORD", "")

    AUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Launch with persistent context — looks like a real Chrome install
        # This avoids Google's "browser not secure" detection
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Remove webdriver flag that Google detects
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        signed_in = False
        if email and password:
            logger.info("Auto Google sign-in with %s...", email)
            signed_in = await _google_signin_direct(page, email, password)

        if signed_in:
            logger.info("Navigating to %s with Google session...", url)
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # If site still shows login, click its Google sign-in button
            current = page.url.lower()
            if any(k in current for k in ["login", "signin", "auth"]):
                for sel in [
                    "button:has-text('Sign in with Google')",
                    "button:has-text('Continue with Google')",
                    "a:has-text('Sign in with Google')",
                    "a:has-text('Continue with Google')",
                    "button:has-text('Google')",
                    "a:has-text('Google')",
                    "[data-provider='google']",
                    "[class*='google'] button",
                    "[class*='google'] a",
                    "button:has-text('Sign in')",
                    "button:has-text('Log in')",
                    "a:has-text('Sign in')",
                    "a:has-text('Log in')",
                ]:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=500):
                            await btn.click()
                            logger.info("Clicked: %s", sel)
                            await page.wait_for_timeout(5000)
                            break
                    except Exception:
                        continue
        else:
            logger.info("Opening %s for manual sign-in (up to 120s)...", url)
            await page.goto(url, wait_until="networkidle", timeout=60000)

        # Wait until we're past auth pages
        for _ in range(240):  # 120s max
            await page.wait_for_timeout(500)
            current = page.url.lower()
            if not any(k in current for k in [
                "accounts.google", "login", "signin", "oauth", "auth", "challenge"
            ]):
                await page.wait_for_timeout(2000)
                break

        await context.storage_state(path=str(AUTH_STATE_FILE))
        logger.info("Auth state saved to %s", AUTH_STATE_FILE)
        await context.close()

    return AUTH_STATE_FILE


def login_and_save_auth_sync(url: str, email: str = "", password: str = "") -> Path:
    """Synchronous wrapper around login_and_save_auth."""
    return asyncio.run(login_and_save_auth(url, email, password))


async def crawl_and_capture(
    url: str,
    output_dir: Path,
    aspect_ratio: str = "16:9",
    wait_seconds: float = 3.0,
    auth_state: Optional[Path] = None,
) -> List[WebsiteCapture]:
    """
    Crawl a website and capture all visible views.

    Strategy:
    1. Load homepage, scroll through capturing every viewport-height
    2. Find all navigation links (same domain)
    3. Click each nav link, scroll through that page too
    4. All captures are viewport-sized at the configured aspect ratio

    Args:
        url: Website URL to crawl.
        output_dir: Directory to save all captures.
        aspect_ratio: Viewport aspect ratio (default "16:9").
        wait_seconds: Wait time after page loads.
        auth_state: Path to saved auth state JSON (cookies/localStorage).

    Returns:
        List of WebsiteCapture objects for all screenshots taken.
    """
    from playwright.async_api import async_playwright

    await _ensure_browser_installed()

    viewport_width, viewport_height = _viewport_for_aspect_ratio(aspect_ratio)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_domain = urlparse(url).netloc
    captures = []
    capture_index = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {
            "viewport": {"width": viewport_width, "height": viewport_height},
            "device_scale_factor": 2,
        }
        if auth_state and Path(auth_state).exists():
            context_kwargs["storage_state"] = str(auth_state)
            logger.info("Using saved auth state from %s", auth_state)
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        # ── Load homepage ──
        logger.info("Loading %s (%dx%d viewport)...", url, viewport_width, viewport_height)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(int(wait_seconds * 1000))
        await _dismiss_overlays(page)

        # ── Scroll through homepage ──
        homepage_captures = await _scroll_and_capture(
            page, output_dir, "homepage", url, viewport_height, capture_index
        )
        captures.extend(homepage_captures)
        capture_index += len(homepage_captures)
        logger.info("Homepage: captured %d screenshots", len(homepage_captures))

        # ── Find nav links ──
        nav_links = await _find_nav_links(page, base_domain, url)
        logger.info("Found %d navigation links to explore", len(nav_links))

        # ── Visit each nav link ──
        visited_urls = {url.rstrip("/")}
        for link_text, link_href in nav_links:
            normalized = link_href.rstrip("/")
            if normalized in visited_urls:
                continue
            visited_urls.add(normalized)

            slug = _slugify(link_text) or _slugify(urlparse(link_href).path)
            label = f"nav_{slug}"

            try:
                await page.goto(link_href, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(1500)
                await _dismiss_overlays(page)

                page_captures = await _scroll_and_capture(
                    page, output_dir, label, link_href, viewport_height, capture_index
                )
                captures.extend(page_captures)
                capture_index += len(page_captures)
                logger.info("  %s (%s): captured %d screenshots", link_text, link_href, len(page_captures))

            except Exception as e:
                logger.warning("  Failed to load %s: %s", link_href, e)
                continue

        await browser.close()

    logger.info("Total: %d screenshots captured across %d pages", len(captures), len(visited_urls))
    return captures


async def _scroll_and_capture(
    page,
    output_dir: Path,
    label: str,
    source_url: str,
    viewport_height: int,
    start_index: int,
) -> List[WebsiteCapture]:
    """Scroll through a page and capture a screenshot every viewport height."""
    captures = []
    page_height = await page.evaluate("document.body.scrollHeight")
    num_scrolls = max(1, (page_height + viewport_height - 1) // viewport_height)
    # Cap at 10 scrolls per page to avoid extremely long pages
    num_scrolls = min(num_scrolls, 10)

    for i in range(num_scrolls):
        scroll_y = i * viewport_height
        await page.evaluate(f"window.scrollTo(0, {scroll_y})")
        await page.wait_for_timeout(600)

        idx = start_index + len(captures)
        filename = f"{idx:03d}_{label}_scroll_{i}.png"
        filepath = output_dir / filename

        await page.screenshot(path=str(filepath), full_page=False)

        captures.append(WebsiteCapture(
            index=idx,
            label=f"{label}_scroll_{i}",
            path=filepath,
            source_url=source_url,
            capture_type="scroll" if i > 0 else "nav_click",
        ))

    # Scroll back to top for next navigation
    await page.evaluate("window.scrollTo(0, 0)")
    return captures


async def _find_nav_links(page, base_domain: str, base_url: str) -> List[Tuple[str, str]]:
    """
    Find all navigation links on the page (same domain, unique paths).
    Looks in <nav>, <header>, and top-level link elements.
    """
    links = []
    seen_paths = set()
    base_path = urlparse(base_url).path.rstrip("/")
    seen_paths.add(base_path or "/")

    # Selectors for common navigation patterns
    selectors = [
        "nav a[href]",
        "header a[href]",
        "[role='navigation'] a[href]",
        "[class*='nav'] a[href]",
        "[class*='menu'] a[href]",
    ]

    for selector in selectors:
        try:
            elements = await page.locator(selector).all()
            for el in elements:
                try:
                    href = await el.get_attribute("href")
                    text = (await el.inner_text()).strip()
                    if not href or not text:
                        continue

                    # Skip anchors, javascript, mailto, tel
                    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    parsed = urlparse(full_url)

                    # Same domain only
                    if parsed.netloc and parsed.netloc != base_domain:
                        continue

                    # Deduplicate by path
                    path = parsed.path.rstrip("/") or "/"
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)

                    # Clean up text
                    text = re.sub(r'\s+', ' ', text)[:50]
                    if text:
                        links.append((text, full_url))

                except Exception:
                    continue
        except Exception:
            continue

    return links


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text)
    return text[:40].strip('_')


def crawl_and_capture_sync(url: str, output_dir: Path, **kwargs) -> List[WebsiteCapture]:
    """Synchronous wrapper around crawl_and_capture."""
    return asyncio.run(crawl_and_capture(url, output_dir, **kwargs))
