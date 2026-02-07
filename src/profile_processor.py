"""MCP integration for fetching LinkedIn profile data."""

import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class LinkedInProfileProcessor:
    """Fetches LinkedIn profile data using the linkedin-mcp-server."""

    def __init__(
        self,
        min_delay: float = 3.0,
        max_delay: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize the profile processor.

        Args:
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Connect to the MCP server."""
        try:
            logger.info("Connecting to linkedin-mcp-server...")

            # Configure the MCP server parameters
            server_params = StdioServerParameters(
                command="uvx",
                args=["linkedin-scraper-mcp"],
                env=None
            )

            # Create stdio client connection
            self.stdio_transport = await stdio_client(server_params)
            self.stdio, self.write = self.stdio_transport

            # Create session
            self.session = ClientSession(self.stdio, self.write)
            await self.session.__aenter__()

            # Initialize the session
            await self.session.initialize()

            logger.info("Successfully connected to MCP server")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
                logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.warning(f"Error disconnecting from MCP server: {e}")

    async def _rate_limit_delay(self):
        """Apply rate limiting delay between requests."""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"Rate limiting: waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    async def _exponential_backoff(self, attempt: int):
        """Apply exponential backoff for retries."""
        if attempt > 0:
            wait_time = min(30 * (2 ** attempt), 120)  # Cap at 120 seconds
            logger.warning(f"Retry attempt {attempt}: waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)

    async def fetch_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single profile from LinkedIn using the MCP server.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Profile data dictionary, or None if fetch failed
        """
        if not self.session:
            raise Exception("Not connected to MCP server. Call connect() first.")

        for attempt in range(self.max_retries):
            try:
                # Apply exponential backoff for retries
                await self._exponential_backoff(attempt)

                logger.info(f"Fetching profile: {profile_url}")

                # Call the get_person_profile tool via MCP
                result = await self.session.call_tool(
                    "get_person_profile",
                    arguments={"url": profile_url}
                )

                # Extract profile data from result
                if result and len(result.content) > 0:
                    # The MCP server returns content as a list
                    profile_data = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])

                    logger.info(f"Successfully fetched profile: {profile_url}")

                    # Apply rate limiting delay before next request
                    await self._rate_limit_delay()

                    # Return the profile data
                    # Note: The actual structure depends on what the MCP server returns
                    # We'll store the raw data and parse it in data_calculator.py
                    return {
                        "url": profile_url,
                        "raw_data": profile_data,
                        "success": True
                    }
                else:
                    logger.warning(f"Empty response for profile: {profile_url}")
                    return None

            except Exception as e:
                logger.error(f"Error fetching profile {profile_url} (attempt {attempt + 1}/{self.max_retries}): {e}")

                # If this was the last attempt, return None
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to fetch profile after {self.max_retries} attempts: {profile_url}")
                    return {
                        "url": profile_url,
                        "raw_data": None,
                        "success": False,
                        "error": str(e)
                    }

        return None

    async def fetch_profiles_batch(
        self,
        profile_urls: List[str],
        on_progress: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple profiles with progress tracking.

        Args:
            profile_urls: List of LinkedIn profile URLs
            on_progress: Optional callback function(current, total, profile_data)

        Returns:
            List of profile data dictionaries
        """
        results = []
        total = len(profile_urls)

        for i, url in enumerate(profile_urls, 1):
            logger.info(f"Processing profile {i}/{total}")

            profile_data = await self.fetch_profile(url)
            results.append(profile_data)

            # Call progress callback if provided
            if on_progress:
                on_progress(i, total, profile_data)

        return results


async def fetch_linkedin_profiles(
    profile_urls: List[str],
    min_delay: float = 3.0,
    max_delay: float = 5.0,
    on_progress: Optional[callable] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch multiple LinkedIn profiles.

    Args:
        profile_urls: List of LinkedIn profile URLs
        min_delay: Minimum delay between requests in seconds
        max_delay: Maximum delay between requests in seconds
        on_progress: Optional progress callback

    Returns:
        List of profile data dictionaries
    """
    async with LinkedInProfileProcessor(min_delay=min_delay, max_delay=max_delay) as processor:
        return await processor.fetch_profiles_batch(profile_urls, on_progress=on_progress)


if __name__ == "__main__":
    # Example usage
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python profile_processor.py <profile_url> [profile_url...]")
        sys.exit(1)

    profile_urls = sys.argv[1:]

    def progress_callback(current, total, profile_data):
        print(f"\nProgress: {current}/{total}")
        if profile_data and profile_data.get("success"):
            print(f"Successfully fetched: {profile_data['url']}")
        else:
            print(f"Failed to fetch: {profile_data['url']}")

    results = asyncio.run(fetch_linkedin_profiles(
        profile_urls,
        on_progress=progress_callback
    ))

    print(f"\nFetched {len(results)} profiles")
    print(f"Successful: {sum(1 for r in results if r and r.get('success'))}")
    print(f"Failed: {sum(1 for r in results if r and not r.get('success'))}")
