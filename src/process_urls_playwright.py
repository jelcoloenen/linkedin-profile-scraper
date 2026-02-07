"""Process LinkedIn profile URLs using Playwright direct scraping."""

import asyncio
import logging
import sys
import csv
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from profile_scraper_playwright import LinkedInProfileScraperPlaywright
from data_calculator import ProfileDataCalculator
from csv_exporter import CSVExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('profile_processing_playwright.log')
    ]
)

logger = logging.getLogger(__name__)


async def process_profiles_from_csv(
    input_csv: str,
    output_csv: str,
    config_dir: str = "config",
    output_dir: str = "output",
    delay: float = 3.0,
    headless: bool = True
):
    """
    Process LinkedIn profiles from a CSV file using Playwright.

    Args:
        input_csv: Path to input CSV with Profile_Name and Profile_Link columns
        output_csv: Output CSV filename
        config_dir: Configuration directory
        output_dir: Output directory
        delay: Delay between requests in seconds
        headless: Run browser in headless mode
    """
    logger.info("=" * 80)
    logger.info("LinkedIn Profile Processor (Playwright) - Starting")
    logger.info("=" * 80)

    # Read profile URLs from CSV
    logger.info(f"\nReading profile URLs from {input_csv}...")
    profile_urls = []

    try:
        with open(input_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('Profile_Link', '').strip()
                if url:
                    profile_urls.append(url)
    except Exception as e:
        logger.error(f"Error reading input CSV: {e}")
        return

    if not profile_urls:
        logger.error("No profile URLs found in input CSV!")
        return

    logger.info(f"Found {len(profile_urls)} profile URLs to process\n")

    # Initialize components
    data_calculator = ProfileDataCalculator(config_dir=config_dir)
    csv_exporter = CSVExporter(output_dir=output_dir)

    # Process profiles
    processed_profiles = []

    def progress_callback(current, total, profile_data):
        """Progress callback for profile fetching."""
        logger.info(f"\n[{current}/{total}] Processing profile...")

        if profile_data and profile_data.get("success"):
            try:
                # Debug: save first profile's raw data
                if current == 1:
                    import json
                    with open('/tmp/profile_playwright_debug.txt', 'w', encoding='utf-8') as f:
                        f.write(f"URL: {profile_data.get('url')}\n")
                        f.write(f"Raw data keys: {list(profile_data.get('raw_data', {}).keys())}\n")
                        f.write(f"\n========== RAW DATA ==========\n")
                        f.write(json.dumps(profile_data.get('raw_data'), indent=2, ensure_ascii=False))
                    logger.info("DEBUG: Saved first profile's raw data to /tmp/profile_playwright_debug.txt")

                # Extract and calculate fields
                extracted_data = data_calculator.extract_profile_fields(profile_data)
                processed_profiles.append(extracted_data)

                logger.info(f"✓ Successfully processed: {extracted_data.get('name', 'Unknown')}")
                logger.info(f"  Current company: {extracted_data.get('current_company', 'N/A')}")
                logger.info(f"  Total experience: {extracted_data.get('total_years_experience', 0)} years")

            except Exception as e:
                logger.error(f"✗ Error extracting data: {e}")
        else:
            logger.warning(f"✗ Failed to fetch profile")

    # Fetch profiles using Playwright
    logger.info("\n[STEP 1/2] Fetching profile data from LinkedIn...\n")

    async with LinkedInProfileScraperPlaywright(headless=headless) as scraper:
        await scraper.scrape_profiles_batch(profile_urls, on_progress=progress_callback, delay=delay)

    # Export results
    logger.info(f"\n[STEP 2/2] Exporting results...\n")

    if processed_profiles:
        output_path = csv_exporter.export_to_csv(
            processed_profiles,
            output_file=output_csv,
            timestamp=False
        )

        # Also print as text
        csv_text = csv_exporter.export_to_csv_text(processed_profiles)

        logger.info("=" * 80)
        logger.info("PROCESSING COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Total profiles processed: {len(processed_profiles)}/{len(profile_urls)}")
        logger.info(f"Output file: {output_path}")
        logger.info(f"\nCSV Output:\n")
        print(csv_text)

    else:
        logger.warning("No profiles were successfully processed")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Process LinkedIn profile URLs from CSV using Playwright'
    )

    parser.add_argument(
        '--input',
        default='input_profiles.csv',
        help='Input CSV file with Profile_Link column (default: input_profiles.csv)'
    )

    parser.add_argument(
        '--output',
        default='processed_profiles.csv',
        help='Output CSV filename (default: processed_profiles.csv)'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=3.0,
        help='Delay between requests in seconds (default: 3.0)'
    )

    parser.add_argument(
        '--config-dir',
        default='config',
        help='Configuration directory (default: config)'
    )

    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory (default: output)'
    )

    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Show browser window (default: headless mode)'
    )

    args = parser.parse_args()

    # Process profiles
    try:
        await process_profiles_from_csv(
            input_csv=args.input,
            output_csv=args.output,
            config_dir=args.config_dir,
            output_dir=args.output_dir,
            delay=args.delay,
            headless=not args.no_headless
        )
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
