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

            # Check if we see recruiter content
            await page.wait_for_selector(
                'a[href*="/talent/profile/"], a[href*="/in/"]',
                timeout=10000
            )
            logger.info("Already authenticated")
            return True

        except PlaywrightTimeoutError:
            logger.error("Authentication timeout")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def _scroll_to_load_all_results(self, page: Page):
        """Scroll through the page to load all lazy-loaded results."""
        logger.info("Scrolling to load all results...")

        previous_height = 0
        scroll_attempts = 0
        max_scroll_attempts = 50  # Prevent infinite loops

        while scroll_attempts < max_scroll_attempts:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)  # Wait for content to load

            # Get new scroll height
            current_height = await page.evaluate("document.body.scrollHeight")

            if current_height == previous_height:
                # No new content loaded, try one more time
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0  # Reset counter if we found new content

            previous_height = current_height

        logger.info(f"Finished scrolling after {scroll_attempts} attempts")

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

        selectors = [
            'a[href*="/talent/profile/"]',  # Recruiter-specific URLs
            'a[href*="/in/"][href*="linkedin.com/in/"]',  # Standard profile URLs
            'a.app-aware-link[href*="/in/"]',  # Alternative selector
        ]

        profile_urls = set()

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                logger.info(f"Found {len(elements)} elements with selector: {selector}")

                for element in elements:
                    href = await element.get_attribute("href")
                    if href:
                        # Normalize URL
                        if href.startswith("/"):
                            href = f"https://www.linkedin.com{href}"

                        # Clean up query parameters
                        if "?" in href:
                            href = href.split("?")[0]

                        # Only add if it looks like a profile URL
                        if "/in/" in href or "/talent/profile/" in href:
                            profile_urls.add(href)

            except Exception as e:
                logger.warning(f"Error extracting URLs with selector {selector}: {e}")

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

        context = await self.browser.new_context()
        page = await context.new_page()

        all_profile_urls = set()
        page_count = 0

        try:
            logger.info(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, timeout=self.timeout, wait_until="networkidle")

            # Load session if available
            await self._load_session(page)

            # Wait for authentication if needed
            if not await self._wait_for_authentication(page):
                raise Exception("Failed to authenticate with LinkedIn")

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
