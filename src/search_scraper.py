"""Playwright-based scraper for extracting profile URLs from LinkedIn Recruiter search results."""

import asyncio
import logging
from typing import List, Optional
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class LinkedInSearchScraper:
    """Scrapes profile URLs from LinkedIn Recruiter search results."""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        session_storage_path: Optional[str] = None
    ):
        """
        Initialize the search scraper.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for operations in milliseconds
            session_storage_path: Path to LinkedIn session storage (cookies/local storage)
        """
        self.headless = headless
        self.timeout = timeout
        self.session_storage_path = session_storage_path
        self.browser: Optional[Browser] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Start the browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

        # Set default session path if not provided
        if self.session_storage_path is None:
            import os
            self.session_storage_path = os.path.expanduser("~/.linkedin-mcp/session.json")

        logger.info("Browser started")

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            logger.info("Browser closed")

    async def _load_session(self, page: Page):
        """Load LinkedIn session from storage if available."""
        if self.session_storage_path:
            try:
                # Load session cookies/storage from MCP server's session
                # This would need to be implemented based on how the MCP server stores sessions
                logger.info("Loading LinkedIn session from storage")
                # TODO: Implement session loading logic
            except Exception as e:
                logger.warning(f"Could not load session: {e}")

    async def _handle_security_prompts(self, page: Page):
        """
        Handle LinkedIn security prompts (suspicious behavior, account verification, etc.)
        """
        try:
            logger.info("Checking for security prompts...")
            await asyncio.sleep(2)

            # Common security prompt button texts
            security_button_texts = [
                "Continue",
                "Got it",
                "Dismiss",
                "Not now",
                "I understand",
                "Verify",
                "Confirm",
                "OK",
            ]

            for button_text in security_button_texts:
                try:
                    # Try various button selectors
                    selectors = [
                        f'button:has-text("{button_text}")',
                        f'[data-control-name*="verification"] button:has-text("{button_text}")',
                        f'[role="dialog"] button:has-text("{button_text}")',
                        f'.artdeco-modal button:has-text("{button_text}")',
                    ]

                    for selector in selectors:
                        button = await page.query_selector(selector)
                        if button:
                            # Check if button is visible
                            is_visible = await button.is_visible()
                            if is_visible:
                                logger.info(f"Found security prompt button: '{button_text}', clicking...")
                                await button.click()
                                await asyncio.sleep(3)
                                await page.wait_for_load_state("networkidle", timeout=10000)
                                logger.info("Clicked security prompt button")
                                return
                except Exception as e:
                    logger.debug(f"Error checking for '{button_text}' button: {e}")
                    continue

            logger.info("No security prompts found")

        except Exception as e:
            logger.debug(f"Error handling security prompts: {e}")

    async def _wait_for_authentication(self, page: Page) -> bool:
        """
        Wait for user to authenticate if not already logged in.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Check if we're on a login page
            if "login" in page.url or "checkpoint" in page.url:
                logger.warning("LinkedIn authentication required!")
                logger.warning("Please log in manually in the browser window.")
                logger.warning("Waiting up to 5 minutes for authentication...")

                # Wait for navigation away from login page (up to 5 minutes)
                await page.wait_for_url(
                    lambda url: "login" not in url and "checkpoint" not in url,
                    timeout=300000  # 5 minutes
                )
                logger.info("Authentication successful")
                return True

            # If we're on a LinkedIn page (not login), assume we're authenticated
            if "linkedin.com" in page.url and "login" not in page.url:
                logger.info("Already on LinkedIn - assuming authenticated")
                # Give the page a moment to load and stabilize
                await asyncio.sleep(5)

                # Check if there's a profile selection prompt
                try:
                    # Look for profile selection buttons/links
                    profile_selectors = [
                        'button:has-text("Picnic")',
                        'a:has-text("Picnic")',
                        '[data-test-account-switcher-item]:has-text("Picnic")'
                    ]

                    for selector in profile_selectors:
                        element = await page.query_selector(selector)
                        if element:
                            logger.info("Found Picnic profile selector, clicking...")
                            await element.click()
                            await page.wait_for_load_state("networkidle")
                            await asyncio.sleep(3)
                            break
                except Exception as e:
                    logger.debug(f"No profile selection needed or error: {e}")

                return True

            logger.warning("Unexpected page state")
            return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def _scroll_to_load_all_results(self, page: Page):
        """Scroll through the page to load all lazy-loaded results."""
        logger.info("Scrolling to load all results...")

        # Wait for initial content to load
        await asyncio.sleep(5)

        # Scroll slowly and incrementally to trigger lazy loading
        scroll_position = 0
        scroll_increment = 500  # Scroll 500px at a time
        no_change_count = 0
        max_no_change = 3

        for attempt in range(50):  # Max 50 scroll attempts
            try:
                # Get current page height
                page_height = await page.evaluate("document.body.scrollHeight")

                # Scroll down by increment
                scroll_position += scroll_increment
                await page.evaluate(f"window.scrollTo(0, {scroll_position})")

                # Wait for content to load after each scroll
                await asyncio.sleep(1.5)

                # Get new page height
                new_height = await page.evaluate("document.body.scrollHeight")

                # Check if we've reached the bottom
                current_scroll = await page.evaluate("window.pageYOffset")
                viewport_height = await page.evaluate("window.innerHeight")

                if current_scroll + viewport_height >= new_height - 100:
                    # Near the bottom
                    if new_height == page_height:
                        no_change_count += 1
                        if no_change_count >= max_no_change:
                            logger.info(f"Reached bottom of page after {attempt + 1} scrolls")
                            break
                    else:
                        no_change_count = 0
                else:
                    no_change_count = 0

            except Exception as e:
                logger.warning(f"Scroll error: {e}")
                break

        # Scroll back to top to ensure all content is in view
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(2)

        logger.info(f"Finished scrolling")

    async def _extract_profile_urls(self, page: Page) -> List[str]:
        """
        Extract all profile URLs from the current search results page.

        Returns:
            List of unique profile URLs
        """
        # LinkedIn Recruiter uses different selectors than regular LinkedIn
        # Common patterns:
        # - /talent/profile/[id]
        # - /in/[username]

        profile_urls = set()

        # Try to extract all links and filter for profile URLs
        try:
            all_links = await page.query_selector_all('a[href]')
            logger.info(f"Found {len(all_links)} total links on page")

            # Debug: print all URLs to understand what's on the page
            all_urls = []
            for link in all_links:
                try:
                    href = await link.get_attribute("href")
                    if href:
                        all_urls.append(href)
                except:
                    continue

            logger.info(f"Sample URLs on page: {all_urls[:20]}")  # Log first 20 URLs

            for link in all_links:
                try:
                    href = await link.get_attribute("href")
                    if not href:
                        continue

                    # Normalize URL
                    if href.startswith("/"):
                        href = f"https://www.linkedin.com{href}"

                    # Check if it looks like a profile URL (before cleaning query params)
                    is_profile = False

                    # LinkedIn Recruiter might use different URL patterns
                    if "/talent/profile/" in href:
                        is_profile = True
                        logger.info(f"Found recruiter profile (talent/profile): {href}")
                    elif "/talent/hire/" in href and "/profile/" in href:
                        is_profile = True
                        logger.info(f"Found recruiter profile (talent/hire/profile): {href}")
                    elif "/in/" in href and "linkedin.com" in href:
                        # Make sure it's not just ending with /in/
                        if not href.rstrip("/").endswith("/in"):
                            is_profile = True
                            logger.info(f"Found standard profile (/in/): {href}")

                    if is_profile:
                        # Clean up query parameters but keep the base URL
                        if "?" in href:
                            href = href.split("?")[0]

                        profile_urls.add(href)

                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting all links: {e}")

        logger.info(f"Extracted {len(profile_urls)} unique profile URLs")
        return list(profile_urls)

    async def _handle_pagination(self, page: Page) -> bool:
        """
        Navigate to next page if available.

        Returns:
            True if successfully navigated to next page, False if no more pages
        """
        try:
            # Look for "Next" button (various possible selectors)
            next_button_selectors = [
                'button[aria-label="Next"]',
                'button:has-text("Next")',
                'a[aria-label="Next"]',
                '.artdeco-pagination__button--next',
            ]

            for selector in next_button_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        is_disabled = await next_button.get_attribute("disabled")
                        if not is_disabled:
                            logger.info("Navigating to next page...")
                            await next_button.click()
                            await page.wait_for_load_state("networkidle", timeout=self.timeout)
                            await asyncio.sleep(2)  # Extra wait for content to load
                            return True
                except Exception:
                    continue

            logger.info("No more pages to navigate")
            return False

        except Exception as e:
            logger.warning(f"Pagination error: {e}")
            return False

    async def scrape_search_results(self, search_url: str, max_pages: Optional[int] = None) -> List[str]:
        """
        Scrape all profile URLs from LinkedIn Recruiter search results.

        Args:
            search_url: LinkedIn Recruiter search URL
            max_pages: Maximum number of pages to scrape (None for unlimited)

        Returns:
            List of unique profile URLs
        """
        if not self.browser:
            await self.start()

        # Create context with stored session if available
        import os
        context_options = {}
        if self.session_storage_path and os.path.exists(self.session_storage_path):
            logger.info(f"Loading session from {self.session_storage_path}")
            context_options["storage_state"] = self.session_storage_path

        context = await self.browser.new_context(**context_options)
        page = await context.new_page()

        all_profile_urls = set()
        page_count = 0

        try:
            logger.info(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, timeout=self.timeout, wait_until="networkidle")

            # Wait for authentication if needed (session should already be loaded)
            if not await self._wait_for_authentication(page):
                raise Exception("Failed to authenticate with LinkedIn")

            # Handle security prompts (suspicious behavior detection)
            await self._handle_security_prompts(page)

            # Wait for the search results to load (LinkedIn Recruiter is heavy JS)
            logger.info("Waiting for search results to load...")
            await asyncio.sleep(10)  # Give extra time for JavaScript to render

            # Process pages
            while True:
                page_count += 1
                logger.info(f"Processing page {page_count}...")

                # Scroll to load all results on current page
                await self._scroll_to_load_all_results(page)

                # Extract profile URLs from current page
                page_urls = await self._extract_profile_urls(page)
                logger.info(f"Found {len(page_urls)} profile URLs on page {page_count}")
                all_profile_urls.update(page_urls)

                # Check if we should stop
                if max_pages and page_count >= max_pages:
                    logger.info(f"Reached maximum page limit: {max_pages}")
                    break

                # Try to navigate to next page
                if not await self._handle_pagination(page):
                    break

            logger.info(f"Scraping complete. Found {len(all_profile_urls)} unique profile URLs across {page_count} pages")
            return list(all_profile_urls)

        except Exception as e:
            logger.error(f"Error scraping search results: {e}")
            raise
        finally:
            await context.close()


async def scrape_linkedin_search(
    search_url: str,
    headless: bool = True,
    max_pages: Optional[int] = None
) -> List[str]:
    """
    Convenience function to scrape LinkedIn search results.

    Args:
        search_url: LinkedIn Recruiter search URL
        headless: Run browser in headless mode
        max_pages: Maximum number of pages to scrape

    Returns:
        List of profile URLs
    """
    async with LinkedInSearchScraper(headless=headless) as scraper:
        return await scraper.scrape_search_results(search_url, max_pages=max_pages)


if __name__ == "__main__":
    # Example usage
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python search_scraper.py <search_url>")
        sys.exit(1)

    search_url = sys.argv[1]
    profile_urls = asyncio.run(scrape_linkedin_search(search_url, headless=False))

    print(f"\nFound {len(profile_urls)} profiles:")
    for url in profile_urls:
        print(url)
