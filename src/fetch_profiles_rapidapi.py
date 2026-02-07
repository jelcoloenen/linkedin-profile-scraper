"""Fetch LinkedIn profiles using RapidAPI Fresh LinkedIn Profile Data API."""

import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from data_calculator import ProfileDataCalculator
from csv_exporter import CSVExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rapidapi_processing.log')
    ]
)

logger = logging.getLogger(__name__)


class RapidAPILinkedInFetcher:
    """Fetches LinkedIn profiles using RapidAPI."""

    def __init__(self, api_key: str):
        """
        Initialize the RapidAPI fetcher.

        Args:
            api_key: Your RapidAPI key
        """
        self.api_key = api_key
        self.base_url = "https://fresh-linkedin-profile-data.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "fresh-linkedin-profile-data.p.rapidapi.com"
        }

    def fetch_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Fetch a single LinkedIn profile.

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Profile data dictionary
        """
        endpoint = f"{self.base_url}/enrich-lead"

        params = {
            "linkedin_url": profile_url,
            "include_skills": "true",
            "include_certifications": "false",
            "include_publications": "false",
            "include_honors": "false",
            "include_volunteers": "false",
            "include_projects": "false",
            "include_patents": "false",
            "include_courses": "false",
            "include_organizations": "false",
            "include_profile_status": "false",
            "include_company_public_url": "false"
        }

        try:
            logger.info(f"Fetching profile: {profile_url}")

            response = requests.get(endpoint, headers=self.headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ Successfully fetched: {profile_url}")

                return {
                    "url": profile_url,
                    "raw_data": data,
                    "success": True
                }
            elif response.status_code == 429:
                error_msg = "Rate limit exceeded"
                logger.error(f"✗ {error_msg}: {profile_url}")
                return {
                    "url": profile_url,
                    "raw_data": None,
                    "success": False,
                    "error": error_msg
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                error_body = response.text
                logger.error(f"✗ {error_msg}: {profile_url} - {error_body[:200]}")
                return {
                    "url": profile_url,
                    "raw_data": None,
                    "success": False,
                    "error": error_msg
                }

        except Exception as e:
            logger.error(f"✗ Error fetching {profile_url}: {e}")
            return {
                "url": profile_url,
                "raw_data": None,
                "success": False,
                "error": str(e)
            }

    def fetch_profiles_batch(
        self,
        profile_urls: List[str],
        delay: float = 1.0,
        on_progress: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple profiles with rate limiting.

        Args:
            profile_urls: List of LinkedIn profile URLs
            delay: Delay between requests in seconds
            on_progress: Optional progress callback

        Returns:
            List of profile data dictionaries
        """
        results = []
        total = len(profile_urls)

        for i, url in enumerate(profile_urls, 1):
            logger.info(f"Processing profile {i}/{total}")

            profile_data = self.fetch_profile(url)
            results.append(profile_data)

            # Call progress callback
            if on_progress:
                on_progress(i, total, profile_data)

            # Rate limiting delay
            if i < total:
                logger.info(f"Waiting {delay} seconds before next request...")
                time.sleep(delay)

        return results


def process_profiles_from_csv(
    input_csv: str,
    output_csv: str,
    api_key: str,
    config_dir: str = "config",
    output_dir: str = "output",
    delay: float = 1.0,
    save_raw_data: bool = True
):
    """
    Process LinkedIn profiles from CSV using RapidAPI.

    Args:
        input_csv: Input CSV with Profile_Link column
        output_csv: Output CSV filename
        api_key: RapidAPI key
        config_dir: Configuration directory
        output_dir: Output directory
        delay: Delay between requests in seconds
        save_raw_data: Save all raw API responses for future reprocessing
    """
    logger.info("=" * 80)
    logger.info("LinkedIn Profile Processor (RapidAPI) - Starting")
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

    # Create raw data directory if saving
    raw_data_dir = None
    if save_raw_data:
        raw_data_dir = Path(output_dir) / "raw_data"
        raw_data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Raw API responses will be saved to: {raw_data_dir}\n")

    # Initialize components
    fetcher = RapidAPILinkedInFetcher(api_key)
    data_calculator = ProfileDataCalculator(config_dir=config_dir)
    csv_exporter = CSVExporter(output_dir=output_dir)

    # Process profiles
    processed_profiles = []
    all_raw_data = []

    def progress_callback(current, total, profile_data):
        """Progress callback for profile fetching."""
        logger.info(f"\n[{current}/{total}] Processing profile...")

        if profile_data and profile_data.get("success"):
            try:
                # Save raw data if enabled
                if save_raw_data and raw_data_dir:
                    profile_filename = f"profile_{current:03d}.json"
                    profile_path = raw_data_dir / profile_filename
                    with open(profile_path, 'w', encoding='utf-8') as f:
                        json.dump(profile_data, f, indent=2, ensure_ascii=False)
                    logger.debug(f"Saved raw data to: {profile_path}")

                    # Also collect for combined file
                    all_raw_data.append(profile_data)

                # Extract and calculate fields
                extracted_data = data_calculator.extract_profile_fields(profile_data)
                processed_profiles.append(extracted_data)

                logger.info(f"✓ Successfully processed: {extracted_data.get('name', 'Unknown')}")
                logger.info(f"  Current company: {extracted_data.get('current_company', 'N/A')}")
                logger.info(f"  Total experience: {extracted_data.get('total_years_experience', 0)} years")

            except Exception as e:
                logger.error(f"✗ Error extracting data: {e}", exc_info=True)
        else:
            error = profile_data.get('error', 'Unknown error') if profile_data else 'Unknown error'
            logger.warning(f"✗ Failed to fetch profile: {error}")

            # Save failed attempts too
            if save_raw_data and raw_data_dir:
                profile_filename = f"profile_{current:03d}_FAILED.json"
                profile_path = raw_data_dir / profile_filename
                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(profile_data, f, indent=2, ensure_ascii=False)
                all_raw_data.append(profile_data)

    # Fetch profiles using RapidAPI
    logger.info("\n[STEP 1/2] Fetching profile data from RapidAPI...\n")
    fetcher.fetch_profiles_batch(profile_urls, delay=delay, on_progress=progress_callback)

    # Save combined raw data file
    if save_raw_data and raw_data_dir and all_raw_data:
        combined_path = raw_data_dir / "all_profiles_raw.json"
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(all_raw_data, f, indent=2, ensure_ascii=False)
        logger.info(f"\n✓ Saved combined raw data to: {combined_path}")

    # Export results
    logger.info(f"\n[STEP 2/2] Exporting results...\n")

    if processed_profiles:
        output_path = csv_exporter.export_to_csv(
            processed_profiles,
            output_file=output_csv,
            timestamp=False
        )

        csv_text = csv_exporter.export_to_csv_text(processed_profiles)

        logger.info("=" * 80)
        logger.info("PROCESSING COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Total profiles processed: {len(processed_profiles)}/{len(profile_urls)}")
        logger.info(f"Success rate: {len(processed_profiles)/len(profile_urls)*100:.1f}%")
        logger.info(f"Output file: {output_path}")
        if save_raw_data:
            logger.info(f"Raw data directory: {raw_data_dir}")
            logger.info(f"  - Individual files: profile_001.json, profile_002.json, ...")
            logger.info(f"  - Combined file: all_profiles_raw.json")
        logger.info(f"\nCSV Output:\n")
        print(csv_text)

    else:
        logger.warning("No profiles were successfully processed")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch LinkedIn profiles from CSV using RapidAPI'
    )

    parser.add_argument(
        '--input',
        default='input_profiles.csv',
        help='Input CSV file with Profile_Link column (default: input_profiles.csv)'
    )

    parser.add_argument(
        '--output',
        default='processed_profiles_rapidapi.csv',
        help='Output CSV filename (default: processed_profiles_rapidapi.csv)'
    )

    parser.add_argument(
        '--api-key',
        help='RapidAPI key (or set RAPIDAPI_KEY environment variable)'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
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
        '--save-raw-data',
        action='store_true',
        default=True,
        help='Save all raw API responses for future reprocessing (default: True)'
    )

    parser.add_argument(
        '--no-save-raw-data',
        dest='save_raw_data',
        action='store_false',
        help='Do not save raw API responses'
    )

    args = parser.parse_args()

    # Get API key from args or environment
    api_key = args.api_key or os.environ.get('RAPIDAPI_KEY')

    if not api_key:
        logger.error("ERROR: RapidAPI key is required!")
        logger.error("Provide it via --api-key argument or RAPIDAPI_KEY environment variable")
        logger.error("\nTo get an API key:")
        logger.error("1. Visit https://rapidapi.com/freshdata-freshdata-default/api/fresh-linkedin-profile-data")
        logger.error("2. Click 'Subscribe to Test'")
        logger.error("3. Choose a plan (Basic plan has FREE tier - 50 requests/month)")
        logger.error("4. Copy your API key from the dashboard")
        sys.exit(1)

    # Process profiles
    try:
        process_profiles_from_csv(
            input_csv=args.input,
            output_csv=args.output,
            api_key=api_key,
            config_dir=args.config_dir,
            output_dir=args.output_dir,
            delay=args.delay,
            save_raw_data=args.save_raw_data
        )
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
