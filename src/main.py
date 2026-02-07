"""Main CLI for LinkedIn Profile Scraper."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from search_scraper import LinkedInSearchScraper
from profile_processor import LinkedInProfileProcessor
from data_calculator import ProfileDataCalculator
from csv_exporter import CSVExporter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)

logger = logging.getLogger(__name__)


class LinkedInScraper:
    """Main orchestrator for LinkedIn profile scraping."""

    def __init__(
        self,
        config_dir: str = "config",
        output_dir: str = "output",
        min_delay: float = 3.0,
        max_delay: float = 5.0,
        headless: bool = True
    ):
        """
        Initialize the scraper.

        Args:
            config_dir: Configuration directory path
            output_dir: Output directory path
            min_delay: Minimum delay between profile fetches (seconds)
            max_delay: Maximum delay between profile fetches (seconds)
            headless: Run browser in headless mode
        """
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.headless = headless

        # Initialize components
        self.data_calculator = ProfileDataCalculator(config_dir=config_dir)
        self.csv_exporter = CSVExporter(output_dir=output_dir)

    async def scrape_profiles(
        self,
        search_url: str,
        output_file: str,
        max_pages: Optional[int] = None,
        batch_size: int = 50,
        resume: bool = False
    ):
        """
        Main scraping workflow.

        Args:
            search_url: LinkedIn Recruiter search URL
            output_file: Output CSV filename
            max_pages: Maximum search result pages to scrape
            batch_size: Save progress every N profiles
            resume: Resume from existing CSV file
        """
        logger.info("=" * 80)
        logger.info("LinkedIn Profile Scraper - Starting")
        logger.info("=" * 80)

        # Step 1: Extract profile URLs from search results
        logger.info("\n[STEP 1/4] Extracting profile URLs from search results...")

        already_processed = set()
        if resume:
            already_processed = self.csv_exporter.get_processed_urls(output_file)
            logger.info(f"Resume mode: Found {len(already_processed)} already processed profiles")

        async with LinkedInSearchScraper(headless=self.headless) as search_scraper:
            profile_urls = await search_scraper.scrape_search_results(
                search_url,
                max_pages=max_pages
            )

        # Filter out already processed URLs
        if already_processed:
            profile_urls = [url for url in profile_urls if url not in already_processed]
            logger.info(f"After filtering: {len(profile_urls)} profiles remaining to process")

        if not profile_urls:
            logger.warning("No profile URLs found!")
            return

        logger.info(f"Found {len(profile_urls)} profiles to process")

        # Step 2: Fetch profile data from LinkedIn using MCP
        logger.info(f"\n[STEP 2/4] Fetching profile data (with {self.min_delay}-{self.max_delay}s delays)...")

        processed_profiles = []

        def progress_callback(current, total, profile_data):
            """Progress callback for profile fetching."""
            logger.info(f"Progress: {current}/{total} profiles fetched")

            if profile_data and profile_data.get("success"):
                # Step 3: Extract and calculate fields for this profile
                try:
                    extracted_data = self.data_calculator.extract_profile_fields(profile_data)
                    processed_profiles.append(extracted_data)

                    # Save progress in batches
                    if len(processed_profiles) % batch_size == 0:
                        self._save_batch(processed_profiles, output_file, resume)
                        logger.info(f"Batch saved: {len(processed_profiles)} profiles")

                except Exception as e:
                    logger.error(f"Error extracting data for {profile_data.get('url')}: {e}")

            else:
                logger.warning(f"Failed to fetch: {profile_data.get('url')}")

        async with LinkedInProfileProcessor(
            min_delay=self.min_delay,
            max_delay=self.max_delay
        ) as processor:
            await processor.fetch_profiles_batch(profile_urls, on_progress=progress_callback)

        # Step 3: Data extraction already happens in progress callback
        logger.info(f"\n[STEP 3/4] Data extraction complete")
        logger.info(f"Successfully processed: {len(processed_profiles)} profiles")

        # Step 4: Export final results
        logger.info("\n[STEP 4/4] Exporting results to CSV...")

        if processed_profiles:
            # Save final batch
            output_path = self.csv_exporter.export_to_csv(
                processed_profiles,
                output_file=output_file,
                timestamp=False
            )

            # Also print as text block
            csv_text = self.csv_exporter.export_to_csv_text(processed_profiles)

            logger.info("=" * 80)
            logger.info("SCRAPING COMPLETE!")
            logger.info("=" * 80)
            logger.info(f"Total profiles processed: {len(processed_profiles)}")
            logger.info(f"Output file: {output_path}")
            logger.info("\nCSV Output:\n")
            print(csv_text)

        else:
            logger.warning("No profiles were successfully processed")

    def _save_batch(self, profiles, output_file, resume):
        """Save a batch of profiles to CSV."""
        try:
            if resume and Path(self.output_dir, output_file).exists():
                # Append to existing file
                for profile in profiles:
                    self.csv_exporter.append_to_csv(profile, output_file)
            else:
                # Create new file
                self.csv_exporter.export_to_csv(
                    profiles,
                    output_file=output_file,
                    timestamp=False
                )
        except Exception as e:
            logger.error(f"Error saving batch: {e}")


def parse_delay(delay_str: str) -> tuple:
    """
    Parse delay string into min and max values.

    Args:
        delay_str: Delay string like "3-5" or "3"

    Returns:
        Tuple of (min_delay, max_delay)
    """
    if '-' in delay_str:
        parts = delay_str.split('-')
        return float(parts[0]), float(parts[1])
    else:
        delay = float(delay_str)
        return delay, delay


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='LinkedIn Profile Scraper - Extract structured data from LinkedIn Recruiter search results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python main.py --search-url "https://www.linkedin.com/recruiter/..." --output results.csv

  # With custom delay and max pages
  python main.py --search-url "..." --output results.csv --delay 5-7 --max-pages 5

  # Resume interrupted scraping
  python main.py --search-url "..." --output results.csv --resume

  # Non-headless mode (show browser)
  python main.py --search-url "..." --output results.csv --no-headless
        """
    )

    parser.add_argument(
        '--search-url',
        required=True,
        help='LinkedIn Recruiter search URL'
    )

    parser.add_argument(
        '--output',
        default='profiles.csv',
        help='Output CSV filename (default: profiles.csv)'
    )

    parser.add_argument(
        '--config-dir',
        default='config',
        help='Configuration directory path (default: config)'
    )

    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory path (default: output)'
    )

    parser.add_argument(
        '--delay',
        default='3-5',
        help='Delay between profile fetches in seconds (e.g., "3-5" or "4") (default: 3-5)'
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum number of search result pages to scrape (default: unlimited)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Save progress every N profiles (default: 50)'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from existing output file'
    )

    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Show browser window (useful for debugging)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse delay
    min_delay, max_delay = parse_delay(args.delay)

    # Create scraper
    scraper = LinkedInScraper(
        config_dir=args.config_dir,
        output_dir=args.output_dir,
        min_delay=min_delay,
        max_delay=max_delay,
        headless=not args.no_headless
    )

    # Run scraping
    try:
        asyncio.run(scraper.scrape_profiles(
            search_url=args.search_url,
            output_file=args.output,
            max_pages=args.max_pages,
            batch_size=args.batch_size,
            resume=args.resume
        ))
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
