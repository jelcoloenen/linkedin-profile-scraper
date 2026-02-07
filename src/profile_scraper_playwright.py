"""Playwright-based scraper for extracting detailed profile data from LinkedIn."""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from playwright_stealth.stealth import Stealth

logger = logging.getLogger(__name__)
stealth = Stealth()


class LinkedInProfileScraperPlaywright:
    """Scrapes detailed profile data from LinkedIn using Playwright."""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        session_storage_path: Optional[str] = None
    ):
        """
        Initialize the profile scraper.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for operations in milliseconds
            session_storage_path: Path to LinkedIn session storage (cookies/local storage)
        """
        self.headless = headless
        self.timeout = timeout
        self.session_storage_path = session_storage_path or os.path.expanduser("~/.linkedin-mcp/session.json")
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

    async def _check_authentication(self, page: Page) -> bool:
        """Check if we're logged in to LinkedIn."""
        try:
            # Check if we're on a login page
            current_url = page.url
            if "login" in current_url or "checkpoint" in current_url:
                return False

            # Check for sign-in button (indicates not logged in)
            sign_in_button = await page.query_selector('a[href*="login"], button:has-text("Sign in")')
            if sign_in_button:
                is_visible = await sign_in_button.is_visible()
                if is_visible:
                    return False

            return True
        except Exception as e:
            logger.warning(f"Error checking authentication: {e}")
            return True  # Assume authenticated to continue

    async def _wait_for_authentication(self, page: Page):
        """Wait for user to authenticate if not already logged in."""
        try:
            if not await self._check_authentication(page):
                logger.warning("=" * 80)
                logger.warning("NOT LOGGED IN TO LINKEDIN!")
                logger.warning("Please log in manually in the browser window")
                logger.warning("Waiting up to 5 minutes for authentication...")
                logger.warning("=" * 80)

                # Wait for authentication (check every 5 seconds)
                for _ in range(60):  # 60 * 5 seconds = 5 minutes
                    await asyncio.sleep(5)
                    if await self._check_authentication(page):
                        logger.info("Authentication successful!")
                        return True

                logger.error("Authentication timeout - please try again")
                return False

            logger.info("Already authenticated")
            return True

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def _wait_for_page_load(self, page: Page):
        """Wait for the profile page to fully load."""
        try:
            # Wait for key profile sections to load
            await page.wait_for_selector('main', timeout=self.timeout)
            # Wait a bit more for dynamic content
            await asyncio.sleep(5)

            # Debug: save screenshot and HTML
            try:
                await page.screenshot(path='/tmp/linkedin_page_debug.png', full_page=True)
                logger.info("Saved page screenshot to /tmp/linkedin_page_debug.png")

                html_content = await page.content()
                with open('/tmp/linkedin_page_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info("Saved page HTML to /tmp/linkedin_page_debug.html")

                title = await page.title()
                logger.info(f"Page title: {title}")
            except Exception as e:
                logger.warning(f"Could not save debug files: {e}")

        except Exception as e:
            logger.warning(f"Page load wait error: {e}")

    async def _scroll_page(self, page: Page):
        """Scroll through the page to load all lazy-loaded content."""
        try:
            # Get initial height
            previous_height = await page.evaluate("document.body.scrollHeight")

            for _ in range(5):  # Scroll up to 5 times
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break
                previous_height = new_height

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Scrolling error: {e}")

    async def _extract_profile_data(self, page: Page, url: str) -> Dict[str, Any]:
        """
        Extract all profile data from the current page.

        Returns:
            Dictionary with profile fields
        """
        data = {
            "url": url,
            "name": "",
            "headline": "",
            "location": "",
            "about": "",
            "experience": [],
            "education": [],
            "skills": [],
            "languages": []
        }

        try:
            # Extract name
            try:
                name_element = await page.query_selector('h1.text-heading-xlarge, h1.top-card-layout__title')
                if name_element:
                    data["name"] = (await name_element.inner_text()).strip()
                    logger.info(f"Extracted name: {data['name']}")
            except Exception as e:
                logger.warning(f"Error extracting name: {e}")

            # Extract headline
            try:
                headline_element = await page.query_selector('.text-body-medium.break-words, .top-card-layout__headline')
                if headline_element:
                    data["headline"] = (await headline_element.inner_text()).strip()
            except Exception as e:
                logger.warning(f"Error extracting headline: {e}")

            # Extract location
            try:
                location_element = await page.query_selector('.text-body-small.inline.t-black--light.break-words, .top-card__subline-item')
                if location_element:
                    data["location"] = (await location_element.inner_text()).strip()
            except Exception as e:
                logger.warning(f"Error extracting location: {e}")

            # Extract about section
            try:
                about_element = await page.query_selector('#about ~ * .inline-show-more-text')
                if about_element:
                    data["about"] = (await about_element.inner_text()).strip()
            except Exception as e:
                logger.warning(f"Error extracting about: {e}")

            # Extract experience
            try:
                experience_section = await page.query_selector('#experience')
                if experience_section:
                    # Get the parent section
                    parent = await experience_section.evaluate_handle('el => el.closest("section")')
                    experience_items = await parent.query_selector_all('ul > li.artdeco-list__item')

                    logger.info(f"Found {len(experience_items)} experience items")

                    for item in experience_items:
                        try:
                            exp_data = {}

                            # Title
                            title_elem = await item.query_selector('.mr1.t-bold span[aria-hidden="true"]')
                            if title_elem:
                                exp_data["title"] = (await title_elem.inner_text()).strip()

                            # Company
                            company_elem = await item.query_selector('.t-14.t-normal span[aria-hidden="true"]')
                            if company_elem:
                                exp_data["company"] = (await company_elem.inner_text()).strip()

                            # Date range
                            date_elem = await item.query_selector('.t-14.t-normal.t-black--light span[aria-hidden="true"]')
                            if date_elem:
                                exp_data["date_range"] = (await date_elem.inner_text()).strip()

                            # Location
                            loc_elem = await item.query_selector('.t-14.t-normal.t-black--light:nth-of-type(2) span[aria-hidden="true"]')
                            if loc_elem:
                                exp_data["location"] = (await loc_elem.inner_text()).strip()

                            if exp_data:
                                data["experience"].append(exp_data)
                                logger.debug(f"Extracted experience: {exp_data.get('title')} at {exp_data.get('company')}")
                        except Exception as e:
                            logger.warning(f"Error extracting individual experience item: {e}")
            except Exception as e:
                logger.warning(f"Error extracting experience section: {e}")

            # Extract education
            try:
                education_section = await page.query_selector('#education')
                if education_section:
                    parent = await education_section.evaluate_handle('el => el.closest("section")')
                    education_items = await parent.query_selector_all('ul > li.artdeco-list__item')

                    logger.info(f"Found {len(education_items)} education items")

                    for item in education_items:
                        try:
                            edu_data = {}

                            # School name
                            school_elem = await item.query_selector('.mr1.t-bold span[aria-hidden="true"]')
                            if school_elem:
                                edu_data["school"] = (await school_elem.inner_text()).strip()

                            # Degree
                            degree_elem = await item.query_selector('.t-14.t-normal span[aria-hidden="true"]')
                            if degree_elem:
                                edu_data["degree"] = (await degree_elem.inner_text()).strip()

                            # Date range
                            date_elem = await item.query_selector('.t-14.t-normal.t-black--light span[aria-hidden="true"]')
                            if date_elem:
                                edu_data["date_range"] = (await date_elem.inner_text()).strip()

                            if edu_data:
                                data["education"].append(edu_data)
                                logger.debug(f"Extracted education: {edu_data.get('school')}")
                        except Exception as e:
                            logger.warning(f"Error extracting individual education item: {e}")
            except Exception as e:
                logger.warning(f"Error extracting education section: {e}")

            # Extract skills
            try:
                skills_section = await page.query_selector('#skills')
                if skills_section:
                    parent = await skills_section.evaluate_handle('el => el.closest("section")')
                    skill_items = await parent.query_selector_all('ul > li span[aria-hidden="true"]')

                    for skill_elem in skill_items[:20]:  # Limit to first 20 skills
                        skill_text = (await skill_elem.inner_text()).strip()
                        if skill_text and skill_text not in data["skills"]:
                            data["skills"].append(skill_text)
            except Exception as e:
                logger.warning(f"Error extracting skills: {e}")

            # Extract languages
            try:
                languages_section = await page.query_selector('#languages')
                if languages_section:
                    parent = await languages_section.evaluate_handle('el => el.closest("section")')
                    lang_items = await parent.query_selector_all('ul > li .mr1.t-bold span[aria-hidden="true"]')

                    for lang_elem in lang_items:
                        lang_text = (await lang_elem.inner_text()).strip()
                        if lang_text:
                            data["languages"].append(lang_text)
            except Exception as e:
                logger.warning(f"Error extracting languages: {e}")

            logger.info(f"Profile extraction complete: {len(data['experience'])} jobs, {len(data['education'])} schools, {len(data['languages'])} languages")

        except Exception as e:
            logger.error(f"Error during profile data extraction: {e}")

        return data

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape a single LinkedIn profile.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Dictionary with profile data
        """
        if not self.browser:
            await self.start()

        # Create context with stored session
        context_options = {}

        # Prefer Playwright-specific session if it exists
        session_dir = os.path.dirname(self.session_storage_path)
        playwright_session = os.path.join(session_dir, "playwright_session.json")

        if os.path.exists(playwright_session):
            logger.info(f"Loading Playwright session from {playwright_session}")
            context_options["storage_state"] = playwright_session
        elif self.session_storage_path and os.path.exists(self.session_storage_path):
            logger.info(f"Loading MCP session from {self.session_storage_path}")
            context_options["storage_state"] = self.session_storage_path

        context = await self.browser.new_context(**context_options)
        page = await context.new_page()

        # Apply stealth mode to avoid detection
        await stealth.apply_stealth_async(page)
        logger.info("Stealth mode enabled")

        try:
            logger.info(f"Navigating to profile: {profile_url}")
            await page.goto(profile_url, timeout=self.timeout, wait_until="networkidle")

            # Check authentication and wait if needed
            if not await self._wait_for_authentication(page):
                raise Exception("Authentication failed or timed out")

            # After authentication, we might have been redirected - navigate back to profile
            if page.url != profile_url and not page.url.startswith(profile_url.split('?')[0]):
                logger.info(f"Redirected to {page.url}, navigating back to profile...")
                await page.goto(profile_url, timeout=self.timeout, wait_until="networkidle")

            # Wait for page to load
            await self._wait_for_page_load(page)

            # Scroll to load all content
            await self._scroll_page(page)

            # Extract profile data
            profile_data = await self._extract_profile_data(page, profile_url)

            # Save session for future use
            try:
                session_dir = os.path.dirname(self.session_storage_path)
                playwright_session_path = os.path.join(session_dir, "playwright_session.json")
                await context.storage_state(path=playwright_session_path)
                logger.info(f"Saved Playwright session to {playwright_session_path}")
            except Exception as e:
                logger.warning(f"Could not save session: {e}")

            return {
                "url": profile_url,
                "raw_data": profile_data,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {e}")
            return {
                "url": profile_url,
                "raw_data": None,
                "success": False,
                "error": str(e)
            }
        finally:
            await context.close()

    async def scrape_profiles_batch(
        self,
        profile_urls: List[str],
        on_progress: Optional[callable] = None,
        delay: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple profiles with progress tracking.

        Args:
            profile_urls: List of LinkedIn profile URLs
            on_progress: Optional callback function(current, total, profile_data)
            delay: Delay between requests in seconds

        Returns:
            List of profile data dictionaries
        """
        results = []
        total = len(profile_urls)

        for i, url in enumerate(profile_urls, 1):
            logger.info(f"Processing profile {i}/{total}")

            profile_data = await self.scrape_profile(url)
            results.append(profile_data)

            # Call progress callback if provided
            if on_progress:
                on_progress(i, total, profile_data)

            # Apply delay between requests (except for last one)
            if i < total:
                logger.info(f"Waiting {delay} seconds before next request...")
                await asyncio.sleep(delay)

        return results


async def scrape_linkedin_profiles_playwright(
    profile_urls: List[str],
    headless: bool = True,
    on_progress: Optional[callable] = None,
    delay: float = 3.0
) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape multiple LinkedIn profiles.

    Args:
        profile_urls: List of LinkedIn profile URLs
        headless: Run browser in headless mode
        on_progress: Optional progress callback
        delay: Delay between requests in seconds

    Returns:
        List of profile data dictionaries
    """
    async with LinkedInProfileScraperPlaywright(headless=headless) as scraper:
        return await scraper.scrape_profiles_batch(profile_urls, on_progress=on_progress, delay=delay)
